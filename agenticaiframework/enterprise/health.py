"""
Enterprise Health Check Module.

Provides health check endpoints, liveness/readiness probes, and
dependency checks for production deployments.

Example:
    health = HealthChecker()
    health.add_check("database", check_database)
    health.add_check("redis", check_redis)
    health.add_check("llm_api", check_llm_endpoint)
    
    # Get health status
    status = await health.check_all()
    
    # Create FastAPI endpoints
    app = create_health_routes(health)
"""

from __future__ import annotations

import asyncio
import time
import socket
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
    Awaitable,
)
from functools import wraps
from enum import Enum
import logging
import json
import os

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Health status values."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class CheckType(str, Enum):
    """Types of health checks."""
    LIVENESS = "liveness"    # Is the service running?
    READINESS = "readiness"  # Is the service ready to accept traffic?
    STARTUP = "startup"      # Has the service started successfully?


@dataclass
class CheckResult:
    """Result of a health check."""
    name: str
    status: HealthStatus
    message: Optional[str] = None
    latency_ms: Optional[float] = None
    timestamp: float = field(default_factory=time.time)
    details: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_healthy(self) -> bool:
        """Check if result indicates healthy status."""
        return self.status == HealthStatus.HEALTHY
    
    @property
    def is_critical(self) -> bool:
        """Check if result indicates unhealthy status."""
        return self.status == HealthStatus.UNHEALTHY
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "latency_ms": self.latency_ms,
            "timestamp": self.timestamp,
            "details": self.details,
        }


@dataclass
class HealthReport:
    """Complete health report."""
    status: HealthStatus
    checks: List[CheckResult]
    timestamp: float = field(default_factory=time.time)
    version: Optional[str] = None
    uptime_seconds: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_healthy(self) -> bool:
        """Check if overall status is healthy."""
        return self.status == HealthStatus.HEALTHY
    
    @property
    def failed_checks(self) -> List[CheckResult]:
        """Get list of failed checks."""
        return [c for c in self.checks if not c.is_healthy]
    
    @property
    def healthy_checks(self) -> List[CheckResult]:
        """Get list of healthy checks."""
        return [c for c in self.checks if c.is_healthy]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "status": self.status.value,
            "checks": [c.to_dict() for c in self.checks],
            "timestamp": self.timestamp,
            "version": self.version,
            "uptime_seconds": self.uptime_seconds,
            "metadata": self.metadata,
        }
    
    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


class HealthCheck(ABC):
    """Abstract base class for health checks."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Check name."""
        pass
    
    @property
    def check_type(self) -> CheckType:
        """Check type (default: readiness)."""
        return CheckType.READINESS
    
    @property
    def critical(self) -> bool:
        """Whether this check is critical (affects overall status)."""
        return True
    
    @property
    def timeout(self) -> float:
        """Timeout for check in seconds."""
        return 5.0
    
    @abstractmethod
    async def check(self) -> CheckResult:
        """Execute health check."""
        pass


class FunctionHealthCheck(HealthCheck):
    """Health check from a function."""
    
    def __init__(
        self,
        name: str,
        check_func: Callable[[], Union[bool, Awaitable[bool], Dict[str, Any], Awaitable[Dict[str, Any]]]],
        check_type: CheckType = CheckType.READINESS,
        critical: bool = True,
        timeout: float = 5.0,
    ):
        self._name = name
        self._check_func = check_func
        self._check_type = check_type
        self._critical = critical
        self._timeout = timeout
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def check_type(self) -> CheckType:
        return self._check_type
    
    @property
    def critical(self) -> bool:
        return self._critical
    
    @property
    def timeout(self) -> float:
        return self._timeout
    
    async def check(self) -> CheckResult:
        """Execute health check function."""
        start = time.time()
        
        try:
            if asyncio.iscoroutinefunction(self._check_func):
                result = await asyncio.wait_for(
                    self._check_func(),
                    timeout=self._timeout
                )
            else:
                result = self._check_func()
            
            latency_ms = (time.time() - start) * 1000
            
            if isinstance(result, bool):
                return CheckResult(
                    name=self._name,
                    status=HealthStatus.HEALTHY if result else HealthStatus.UNHEALTHY,
                    latency_ms=latency_ms,
                )
            elif isinstance(result, dict):
                status = result.get("status", HealthStatus.HEALTHY)
                if isinstance(status, str):
                    status = HealthStatus(status)
                return CheckResult(
                    name=self._name,
                    status=status,
                    message=result.get("message"),
                    latency_ms=latency_ms,
                    details=result.get("details", {}),
                )
            else:
                return CheckResult(
                    name=self._name,
                    status=HealthStatus.HEALTHY if result else HealthStatus.UNHEALTHY,
                    latency_ms=latency_ms,
                )
        
        except asyncio.TimeoutError:
            return CheckResult(
                name=self._name,
                status=HealthStatus.UNHEALTHY,
                message=f"Check timed out after {self._timeout}s",
                latency_ms=self._timeout * 1000,
            )
        except Exception as e:
            latency_ms = (time.time() - start) * 1000
            return CheckResult(
                name=self._name,
                status=HealthStatus.UNHEALTHY,
                message=str(e),
                latency_ms=latency_ms,
                details={"error_type": type(e).__name__},
            )


class HTTPHealthCheck(HealthCheck):
    """Health check that calls an HTTP endpoint."""
    
    def __init__(
        self,
        name: str,
        url: str,
        method: str = "GET",
        expected_status: int = 200,
        timeout: float = 5.0,
        headers: Optional[Dict[str, str]] = None,
        critical: bool = True,
    ):
        self._name = name
        self.url = url
        self.method = method
        self.expected_status = expected_status
        self._timeout = timeout
        self.headers = headers or {}
        self._critical = critical
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def timeout(self) -> float:
        return self._timeout
    
    @property
    def critical(self) -> bool:
        return self._critical
    
    async def check(self) -> CheckResult:
        """Check HTTP endpoint health."""
        start = time.time()
        
        try:
            import aiohttp
            
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    self.method,
                    self.url,
                    headers=self.headers,
                    timeout=aiohttp.ClientTimeout(total=self._timeout),
                ) as response:
                    latency_ms = (time.time() - start) * 1000
                    
                    if response.status == self.expected_status:
                        return CheckResult(
                            name=self._name,
                            status=HealthStatus.HEALTHY,
                            latency_ms=latency_ms,
                            details={"status_code": response.status},
                        )
                    else:
                        return CheckResult(
                            name=self._name,
                            status=HealthStatus.UNHEALTHY,
                            message=f"Expected {self.expected_status}, got {response.status}",
                            latency_ms=latency_ms,
                            details={"status_code": response.status},
                        )
        
        except ImportError:
            # Fallback to urllib if aiohttp not available
            import urllib.request
            
            try:
                req = urllib.request.Request(self.url, headers=self.headers, method=self.method)
                with urllib.request.urlopen(req, timeout=self._timeout) as response:
                    latency_ms = (time.time() - start) * 1000
                    
                    if response.status == self.expected_status:
                        return CheckResult(
                            name=self._name,
                            status=HealthStatus.HEALTHY,
                            latency_ms=latency_ms,
                        )
                    else:
                        return CheckResult(
                            name=self._name,
                            status=HealthStatus.UNHEALTHY,
                            message=f"Expected {self.expected_status}, got {response.status}",
                            latency_ms=latency_ms,
                        )
            except Exception as e:
                latency_ms = (time.time() - start) * 1000
                return CheckResult(
                    name=self._name,
                    status=HealthStatus.UNHEALTHY,
                    message=str(e),
                    latency_ms=latency_ms,
                )
        
        except Exception as e:
            latency_ms = (time.time() - start) * 1000
            return CheckResult(
                name=self._name,
                status=HealthStatus.UNHEALTHY,
                message=str(e),
                latency_ms=latency_ms,
            )


class TCPHealthCheck(HealthCheck):
    """Health check that tests TCP connectivity."""
    
    def __init__(
        self,
        name: str,
        host: str,
        port: int,
        timeout: float = 5.0,
        critical: bool = True,
    ):
        self._name = name
        self.host = host
        self.port = port
        self._timeout = timeout
        self._critical = critical
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def timeout(self) -> float:
        return self._timeout
    
    @property
    def critical(self) -> bool:
        return self._critical
    
    async def check(self) -> CheckResult:
        """Check TCP connectivity."""
        start = time.time()
        
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=self._timeout,
            )
            writer.close()
            await writer.wait_closed()
            
            latency_ms = (time.time() - start) * 1000
            return CheckResult(
                name=self._name,
                status=HealthStatus.HEALTHY,
                latency_ms=latency_ms,
                details={"host": self.host, "port": self.port},
            )
        
        except asyncio.TimeoutError:
            return CheckResult(
                name=self._name,
                status=HealthStatus.UNHEALTHY,
                message=f"Connection timed out after {self._timeout}s",
                latency_ms=self._timeout * 1000,
                details={"host": self.host, "port": self.port},
            )
        except Exception as e:
            latency_ms = (time.time() - start) * 1000
            return CheckResult(
                name=self._name,
                status=HealthStatus.UNHEALTHY,
                message=str(e),
                latency_ms=latency_ms,
                details={"host": self.host, "port": self.port},
            )


class RedisHealthCheck(HealthCheck):
    """Health check for Redis connectivity."""
    
    def __init__(
        self,
        name: str = "redis",
        url: str = "redis://localhost:6379",
        timeout: float = 5.0,
        critical: bool = True,
    ):
        self._name = name
        self.url = url
        self._timeout = timeout
        self._critical = critical
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def timeout(self) -> float:
        return self._timeout
    
    @property
    def critical(self) -> bool:
        return self._critical
    
    async def check(self) -> CheckResult:
        """Check Redis connectivity."""
        start = time.time()
        
        try:
            import redis.asyncio as redis
            
            client = redis.from_url(self.url)
            await asyncio.wait_for(client.ping(), timeout=self._timeout)
            info = await client.info("server")
            await client.close()
            
            latency_ms = (time.time() - start) * 1000
            return CheckResult(
                name=self._name,
                status=HealthStatus.HEALTHY,
                latency_ms=latency_ms,
                details={
                    "redis_version": info.get("redis_version"),
                    "connected_clients": info.get("connected_clients"),
                },
            )
        
        except ImportError:
            return CheckResult(
                name=self._name,
                status=HealthStatus.UNKNOWN,
                message="redis package not installed",
            )
        except Exception as e:
            latency_ms = (time.time() - start) * 1000
            return CheckResult(
                name=self._name,
                status=HealthStatus.UNHEALTHY,
                message=str(e),
                latency_ms=latency_ms,
            )


class DatabaseHealthCheck(HealthCheck):
    """Health check for database connectivity."""
    
    def __init__(
        self,
        name: str = "database",
        connection_string: str = "",
        query: str = "SELECT 1",
        timeout: float = 5.0,
        critical: bool = True,
    ):
        self._name = name
        self.connection_string = connection_string
        self.query = query
        self._timeout = timeout
        self._critical = critical
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def timeout(self) -> float:
        return self._timeout
    
    @property
    def critical(self) -> bool:
        return self._critical
    
    async def check(self) -> CheckResult:
        """Check database connectivity."""
        start = time.time()
        
        try:
            # Try asyncpg for PostgreSQL
            if "postgresql" in self.connection_string or "postgres" in self.connection_string:
                try:
                    import asyncpg
                    conn = await asyncio.wait_for(
                        asyncpg.connect(self.connection_string),
                        timeout=self._timeout,
                    )
                    result = await conn.fetchval(self.query)
                    await conn.close()
                    
                    latency_ms = (time.time() - start) * 1000
                    return CheckResult(
                        name=self._name,
                        status=HealthStatus.HEALTHY,
                        latency_ms=latency_ms,
                    )
                except ImportError:
                    pass
            
            # Fallback to generic DB-API
            return CheckResult(
                name=self._name,
                status=HealthStatus.UNKNOWN,
                message="Database check requires asyncpg for PostgreSQL",
            )
        
        except Exception as e:
            latency_ms = (time.time() - start) * 1000
            return CheckResult(
                name=self._name,
                status=HealthStatus.UNHEALTHY,
                message=str(e),
                latency_ms=latency_ms,
            )


class DiskSpaceHealthCheck(HealthCheck):
    """Health check for disk space."""
    
    def __init__(
        self,
        name: str = "disk_space",
        path: str = "/",
        threshold_percent: float = 90.0,
        critical: bool = False,
    ):
        self._name = name
        self.path = path
        self.threshold_percent = threshold_percent
        self._critical = critical
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def critical(self) -> bool:
        return self._critical
    
    async def check(self) -> CheckResult:
        """Check disk space usage."""
        try:
            import shutil
            
            total, used, free = shutil.disk_usage(self.path)
            usage_percent = (used / total) * 100
            
            if usage_percent >= self.threshold_percent:
                return CheckResult(
                    name=self._name,
                    status=HealthStatus.DEGRADED,
                    message=f"Disk usage at {usage_percent:.1f}%",
                    details={
                        "total_gb": total / (1024**3),
                        "used_gb": used / (1024**3),
                        "free_gb": free / (1024**3),
                        "usage_percent": usage_percent,
                    },
                )
            
            return CheckResult(
                name=self._name,
                status=HealthStatus.HEALTHY,
                details={
                    "total_gb": total / (1024**3),
                    "used_gb": used / (1024**3),
                    "free_gb": free / (1024**3),
                    "usage_percent": usage_percent,
                },
            )
        
        except Exception as e:
            return CheckResult(
                name=self._name,
                status=HealthStatus.UNHEALTHY,
                message=str(e),
            )


class MemoryHealthCheck(HealthCheck):
    """Health check for memory usage."""
    
    def __init__(
        self,
        name: str = "memory",
        threshold_percent: float = 90.0,
        critical: bool = False,
    ):
        self._name = name
        self.threshold_percent = threshold_percent
        self._critical = critical
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def critical(self) -> bool:
        return self._critical
    
    async def check(self) -> CheckResult:
        """Check memory usage."""
        try:
            import psutil
            
            memory = psutil.virtual_memory()
            
            if memory.percent >= self.threshold_percent:
                return CheckResult(
                    name=self._name,
                    status=HealthStatus.DEGRADED,
                    message=f"Memory usage at {memory.percent:.1f}%",
                    details={
                        "total_gb": memory.total / (1024**3),
                        "available_gb": memory.available / (1024**3),
                        "used_percent": memory.percent,
                    },
                )
            
            return CheckResult(
                name=self._name,
                status=HealthStatus.HEALTHY,
                details={
                    "total_gb": memory.total / (1024**3),
                    "available_gb": memory.available / (1024**3),
                    "used_percent": memory.percent,
                },
            )
        
        except ImportError:
            return CheckResult(
                name=self._name,
                status=HealthStatus.UNKNOWN,
                message="psutil package not installed",
            )
        except Exception as e:
            return CheckResult(
                name=self._name,
                status=HealthStatus.UNHEALTHY,
                message=str(e),
            )


class HealthChecker:
    """
    Main health checker that manages multiple health checks.
    """
    
    def __init__(
        self,
        version: Optional[str] = None,
        include_details: bool = True,
    ):
        """
        Initialize health checker.
        
        Args:
            version: Application version string
            include_details: Whether to include detailed check info
        """
        self.version = version
        self.include_details = include_details
        self._checks: Dict[str, HealthCheck] = {}
        self._start_time = time.time()
        self._lock = asyncio.Lock()
    
    @property
    def uptime_seconds(self) -> float:
        """Get uptime in seconds."""
        return time.time() - self._start_time
    
    def add_check(
        self,
        name: str,
        check: Union[HealthCheck, Callable[[], Union[bool, Dict[str, Any]]]],
        check_type: CheckType = CheckType.READINESS,
        critical: bool = True,
        timeout: float = 5.0,
    ) -> 'HealthChecker':
        """
        Add a health check.
        
        Args:
            name: Check name
            check: HealthCheck instance or function
            check_type: Type of check
            critical: Whether check is critical
            timeout: Check timeout
            
        Returns:
            Self for chaining
        """
        if isinstance(check, HealthCheck):
            self._checks[name] = check
        else:
            self._checks[name] = FunctionHealthCheck(
                name=name,
                check_func=check,
                check_type=check_type,
                critical=critical,
                timeout=timeout,
            )
        return self
    
    def remove_check(self, name: str) -> Optional[HealthCheck]:
        """Remove a health check."""
        return self._checks.pop(name, None)
    
    def add_http_check(
        self,
        name: str,
        url: str,
        **kwargs: Any,
    ) -> 'HealthChecker':
        """Add HTTP health check."""
        self._checks[name] = HTTPHealthCheck(name=name, url=url, **kwargs)
        return self
    
    def add_tcp_check(
        self,
        name: str,
        host: str,
        port: int,
        **kwargs: Any,
    ) -> 'HealthChecker':
        """Add TCP health check."""
        self._checks[name] = TCPHealthCheck(name=name, host=host, port=port, **kwargs)
        return self
    
    def add_redis_check(
        self,
        name: str = "redis",
        url: str = "redis://localhost:6379",
        **kwargs: Any,
    ) -> 'HealthChecker':
        """Add Redis health check."""
        self._checks[name] = RedisHealthCheck(name=name, url=url, **kwargs)
        return self
    
    def add_disk_check(
        self,
        name: str = "disk_space",
        path: str = "/",
        threshold_percent: float = 90.0,
        **kwargs: Any,
    ) -> 'HealthChecker':
        """Add disk space health check."""
        self._checks[name] = DiskSpaceHealthCheck(
            name=name,
            path=path,
            threshold_percent=threshold_percent,
            **kwargs,
        )
        return self
    
    def add_memory_check(
        self,
        name: str = "memory",
        threshold_percent: float = 90.0,
        **kwargs: Any,
    ) -> 'HealthChecker':
        """Add memory health check."""
        self._checks[name] = MemoryHealthCheck(
            name=name,
            threshold_percent=threshold_percent,
            **kwargs,
        )
        return self
    
    async def check(self, name: str) -> CheckResult:
        """Run a specific health check."""
        if name not in self._checks:
            return CheckResult(
                name=name,
                status=HealthStatus.UNKNOWN,
                message=f"Check '{name}' not found",
            )
        return await self._checks[name].check()
    
    async def check_all(
        self,
        check_type: Optional[CheckType] = None,
    ) -> HealthReport:
        """
        Run all health checks.
        
        Args:
            check_type: Filter by check type
            
        Returns:
            Complete health report
        """
        checks_to_run = self._checks.values()
        
        if check_type:
            checks_to_run = [
                c for c in checks_to_run
                if c.check_type == check_type
            ]
        
        # Run all checks concurrently
        results = await asyncio.gather(
            *[check.check() for check in checks_to_run],
            return_exceptions=True,
        )
        
        # Process results
        check_results = []
        for i, result in enumerate(results):
            check = list(checks_to_run)[i]
            if isinstance(result, Exception):
                check_results.append(CheckResult(
                    name=check.name,
                    status=HealthStatus.UNHEALTHY,
                    message=str(result),
                ))
            else:
                check_results.append(result)
        
        # Determine overall status
        overall_status = self._calculate_overall_status(check_results)
        
        return HealthReport(
            status=overall_status,
            checks=check_results,
            version=self.version,
            uptime_seconds=self.uptime_seconds,
        )
    
    def _calculate_overall_status(
        self,
        results: List[CheckResult],
    ) -> HealthStatus:
        """Calculate overall health status from check results."""
        if not results:
            return HealthStatus.HEALTHY
        
        # Get critical checks
        critical_results = [
            r for r in results
            if self._checks.get(r.name, FunctionHealthCheck(r.name, lambda: True)).critical
        ]
        
        # Any critical unhealthy = unhealthy
        if any(r.status == HealthStatus.UNHEALTHY for r in critical_results):
            return HealthStatus.UNHEALTHY
        
        # Any degraded = degraded
        if any(r.status == HealthStatus.DEGRADED for r in results):
            return HealthStatus.DEGRADED
        
        # All healthy
        return HealthStatus.HEALTHY
    
    async def liveness(self) -> HealthReport:
        """Run liveness checks only."""
        return await self.check_all(check_type=CheckType.LIVENESS)
    
    async def readiness(self) -> HealthReport:
        """Run readiness checks only."""
        return await self.check_all(check_type=CheckType.READINESS)
    
    async def startup(self) -> HealthReport:
        """Run startup checks only."""
        return await self.check_all(check_type=CheckType.STARTUP)


def create_health_routes(
    health_checker: HealthChecker,
    prefix: str = "/health",
) -> Any:
    """
    Create FastAPI routes for health checks.
    
    Args:
        health_checker: HealthChecker instance
        prefix: URL prefix for health routes
        
    Returns:
        FastAPI router
    """
    try:
        from fastapi import APIRouter, Response
        from fastapi.responses import JSONResponse
    except ImportError:
        raise ImportError(
            "FastAPI required for health routes. "
            "Install with: pip install fastapi"
        )
    
    router = APIRouter(prefix=prefix, tags=["health"])
    
    @router.get("")
    @router.get("/")
    async def health():
        """Overall health status."""
        report = await health_checker.check_all()
        status_code = 200 if report.is_healthy else 503
        return JSONResponse(content=report.to_dict(), status_code=status_code)
    
    @router.get("/live")
    @router.get("/liveness")
    async def liveness():
        """Liveness probe for Kubernetes."""
        report = await health_checker.liveness()
        status_code = 200 if report.is_healthy else 503
        return JSONResponse(content=report.to_dict(), status_code=status_code)
    
    @router.get("/ready")
    @router.get("/readiness")
    async def readiness():
        """Readiness probe for Kubernetes."""
        report = await health_checker.readiness()
        status_code = 200 if report.is_healthy else 503
        return JSONResponse(content=report.to_dict(), status_code=status_code)
    
    @router.get("/startup")
    async def startup():
        """Startup probe for Kubernetes."""
        report = await health_checker.startup()
        status_code = 200 if report.is_healthy else 503
        return JSONResponse(content=report.to_dict(), status_code=status_code)
    
    @router.get("/checks/{check_name}")
    async def single_check(check_name: str):
        """Run a specific health check."""
        result = await health_checker.check(check_name)
        status_code = 200 if result.is_healthy else 503
        return JSONResponse(content=result.to_dict(), status_code=status_code)
    
    return router


class HealthCheckMiddleware:
    """
    Middleware for adding health check support to agents.
    """
    
    def __init__(
        self,
        health_checker: HealthChecker,
        fail_on_unhealthy: bool = False,
    ):
        """
        Initialize middleware.
        
        Args:
            health_checker: HealthChecker instance
            fail_on_unhealthy: Raise exception if unhealthy
        """
        self.health_checker = health_checker
        self.fail_on_unhealthy = fail_on_unhealthy
    
    async def __call__(
        self,
        context: Dict[str, Any],
        next_handler: Callable[[Dict[str, Any]], Any],
    ) -> Any:
        """Check health before processing."""
        report = await self.health_checker.check_all()
        
        context["health_status"] = report.status.value
        context["health_checks"] = {
            c.name: c.status.value for c in report.checks
        }
        
        if self.fail_on_unhealthy and not report.is_healthy:
            raise RuntimeError(
                f"System is unhealthy: {[c.name for c in report.failed_checks]}"
            )
        
        return await next_handler(context)


# Convenience functions
_default_checker: Optional[HealthChecker] = None


def get_health_checker() -> HealthChecker:
    """Get default health checker."""
    global _default_checker
    if _default_checker is None:
        _default_checker = HealthChecker()
    return _default_checker


def set_health_checker(checker: HealthChecker) -> None:
    """Set default health checker."""
    global _default_checker
    _default_checker = checker


def add_health_check(
    name: str,
    check: Union[HealthCheck, Callable[[], Union[bool, Dict[str, Any]]]],
    **kwargs: Any,
) -> None:
    """Add check to default health checker."""
    get_health_checker().add_check(name, check, **kwargs)


async def check_health() -> HealthReport:
    """Run all health checks."""
    return await get_health_checker().check_all()


def health_check(
    name: Optional[str] = None,
    check_type: CheckType = CheckType.READINESS,
    critical: bool = True,
    timeout: float = 5.0,
) -> Callable:
    """
    Decorator to register a function as a health check.
    
    Example:
        @health_check("database")
        async def check_db():
            return await db.ping()
    """
    def decorator(func: Callable) -> Callable:
        check_name = name or func.__name__
        add_health_check(
            check_name,
            func,
            check_type=check_type,
            critical=critical,
            timeout=timeout,
        )
        return func
    return decorator


__all__ = [
    # Enums
    "HealthStatus",
    "CheckType",
    # Data classes
    "CheckResult",
    "HealthReport",
    # Base classes
    "HealthCheck",
    # Implementations
    "FunctionHealthCheck",
    "HTTPHealthCheck",
    "TCPHealthCheck",
    "RedisHealthCheck",
    "DatabaseHealthCheck",
    "DiskSpaceHealthCheck",
    "MemoryHealthCheck",
    # Main checker
    "HealthChecker",
    # Middleware
    "HealthCheckMiddleware",
    # Route creation
    "create_health_routes",
    # Functions
    "get_health_checker",
    "set_health_checker",
    "add_health_check",
    "check_health",
    # Decorator
    "health_check",
]
