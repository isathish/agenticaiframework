"""
Enterprise Health Check Module.

Provides health checks, readiness/liveness probes,
dependency checks, and health aggregation.

Example:
    # Create health checker
    health = create_health_checker()
    
    # Add checks
    health.add("database", database_check)
    health.add("redis", redis_check)
    
    # Get health status
    status = await health.check()
    print(f"Healthy: {status.is_healthy}")
"""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Type,
    TypeVar,
)

T = TypeVar('T')


logger = logging.getLogger(__name__)


class HealthCheckError(Exception):
    """Health check error."""
    pass


class HealthStatus(str, Enum):
    """Health status."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class CheckType(str, Enum):
    """Check type."""
    LIVENESS = "liveness"
    READINESS = "readiness"
    STARTUP = "startup"


@dataclass
class CheckResult:
    """Result of a health check."""
    name: str
    status: HealthStatus
    message: Optional[str] = None
    duration_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    details: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class HealthReport:
    """Aggregated health report."""
    status: HealthStatus
    checks: List[CheckResult]
    timestamp: datetime = field(default_factory=datetime.now)
    duration_ms: float = 0.0
    
    @property
    def is_healthy(self) -> bool:
        return self.status == HealthStatus.HEALTHY
    
    @property
    def healthy_checks(self) -> List[CheckResult]:
        return [c for c in self.checks if c.status == HealthStatus.HEALTHY]
    
    @property
    def unhealthy_checks(self) -> List[CheckResult]:
        return [c for c in self.checks if c.status == HealthStatus.UNHEALTHY]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "timestamp": self.timestamp.isoformat(),
            "duration_ms": self.duration_ms,
            "checks": [
                {
                    "name": c.name,
                    "status": c.status.value,
                    "message": c.message,
                    "duration_ms": c.duration_ms,
                    "details": c.details,
                }
                for c in self.checks
            ],
        }


class HealthCheck(ABC):
    """
    Abstract health check.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Check name."""
        pass
    
    @abstractmethod
    async def check(self) -> CheckResult:
        """Execute health check."""
        pass


class FunctionHealthCheck(HealthCheck):
    """
    Health check from a function.
    """
    
    def __init__(
        self,
        name: str,
        check_fn: Callable[[], Any],
        timeout: float = 5.0,
    ):
        self._name = name
        self._check_fn = check_fn
        self._timeout = timeout
    
    @property
    def name(self) -> str:
        return self._name
    
    async def check(self) -> CheckResult:
        start = time.perf_counter()
        
        try:
            if asyncio.iscoroutinefunction(self._check_fn):
                result = await asyncio.wait_for(
                    self._check_fn(),
                    timeout=self._timeout,
                )
            else:
                result = self._check_fn()
            
            duration = (time.perf_counter() - start) * 1000
            
            # Interpret result
            if isinstance(result, bool):
                status = HealthStatus.HEALTHY if result else HealthStatus.UNHEALTHY
                message = None
            elif isinstance(result, tuple) and len(result) >= 2:
                status = HealthStatus.HEALTHY if result[0] else HealthStatus.UNHEALTHY
                message = result[1]
            elif isinstance(result, dict):
                status = (
                    HealthStatus.HEALTHY
                    if result.get("healthy", True)
                    else HealthStatus.UNHEALTHY
                )
                message = result.get("message")
            else:
                status = HealthStatus.HEALTHY
                message = str(result) if result else None
            
            return CheckResult(
                name=self._name,
                status=status,
                message=message,
                duration_ms=duration,
            )
            
        except asyncio.TimeoutError:
            duration = (time.perf_counter() - start) * 1000
            return CheckResult(
                name=self._name,
                status=HealthStatus.UNHEALTHY,
                message="Check timed out",
                duration_ms=duration,
                error="TimeoutError",
            )
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            return CheckResult(
                name=self._name,
                status=HealthStatus.UNHEALTHY,
                message=str(e),
                duration_ms=duration,
                error=type(e).__name__,
            )


class HttpHealthCheck(HealthCheck):
    """
    HTTP endpoint health check.
    """
    
    def __init__(
        self,
        name: str,
        url: str,
        expected_status: int = 200,
        timeout: float = 5.0,
    ):
        self._name = name
        self._url = url
        self._expected_status = expected_status
        self._timeout = timeout
    
    @property
    def name(self) -> str:
        return self._name
    
    async def check(self) -> CheckResult:
        import aiohttp
        
        start = time.perf_counter()
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self._url,
                    timeout=aiohttp.ClientTimeout(total=self._timeout),
                ) as response:
                    duration = (time.perf_counter() - start) * 1000
                    
                    if response.status == self._expected_status:
                        return CheckResult(
                            name=self._name,
                            status=HealthStatus.HEALTHY,
                            message=f"HTTP {response.status}",
                            duration_ms=duration,
                            details={"url": self._url, "status": response.status},
                        )
                    else:
                        return CheckResult(
                            name=self._name,
                            status=HealthStatus.UNHEALTHY,
                            message=f"Expected {self._expected_status}, got {response.status}",
                            duration_ms=duration,
                            details={"url": self._url, "status": response.status},
                        )
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            return CheckResult(
                name=self._name,
                status=HealthStatus.UNHEALTHY,
                message=str(e),
                duration_ms=duration,
                error=type(e).__name__,
            )


class TcpHealthCheck(HealthCheck):
    """
    TCP port health check.
    """
    
    def __init__(
        self,
        name: str,
        host: str,
        port: int,
        timeout: float = 5.0,
    ):
        self._name = name
        self._host = host
        self._port = port
        self._timeout = timeout
    
    @property
    def name(self) -> str:
        return self._name
    
    async def check(self) -> CheckResult:
        start = time.perf_counter()
        
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, self._port),
                timeout=self._timeout,
            )
            writer.close()
            await writer.wait_closed()
            
            duration = (time.perf_counter() - start) * 1000
            return CheckResult(
                name=self._name,
                status=HealthStatus.HEALTHY,
                message=f"TCP connection successful",
                duration_ms=duration,
                details={"host": self._host, "port": self._port},
            )
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            return CheckResult(
                name=self._name,
                status=HealthStatus.UNHEALTHY,
                message=str(e),
                duration_ms=duration,
                error=type(e).__name__,
            )


class MemoryHealthCheck(HealthCheck):
    """
    Memory usage health check.
    """
    
    def __init__(
        self,
        name: str = "memory",
        warning_threshold: float = 0.8,
        critical_threshold: float = 0.9,
    ):
        self._name = name
        self._warning_threshold = warning_threshold
        self._critical_threshold = critical_threshold
    
    @property
    def name(self) -> str:
        return self._name
    
    async def check(self) -> CheckResult:
        import psutil
        
        start = time.perf_counter()
        
        try:
            memory = psutil.virtual_memory()
            usage = memory.percent / 100
            
            duration = (time.perf_counter() - start) * 1000
            
            if usage >= self._critical_threshold:
                status = HealthStatus.UNHEALTHY
                message = f"Critical memory usage: {memory.percent}%"
            elif usage >= self._warning_threshold:
                status = HealthStatus.DEGRADED
                message = f"High memory usage: {memory.percent}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"Memory usage: {memory.percent}%"
            
            return CheckResult(
                name=self._name,
                status=status,
                message=message,
                duration_ms=duration,
                details={
                    "total": memory.total,
                    "available": memory.available,
                    "percent": memory.percent,
                },
            )
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            return CheckResult(
                name=self._name,
                status=HealthStatus.UNKNOWN,
                message=str(e),
                duration_ms=duration,
                error=type(e).__name__,
            )


class DiskHealthCheck(HealthCheck):
    """
    Disk usage health check.
    """
    
    def __init__(
        self,
        name: str = "disk",
        path: str = "/",
        warning_threshold: float = 0.8,
        critical_threshold: float = 0.9,
    ):
        self._name = name
        self._path = path
        self._warning_threshold = warning_threshold
        self._critical_threshold = critical_threshold
    
    @property
    def name(self) -> str:
        return self._name
    
    async def check(self) -> CheckResult:
        import psutil
        
        start = time.perf_counter()
        
        try:
            disk = psutil.disk_usage(self._path)
            usage = disk.percent / 100
            
            duration = (time.perf_counter() - start) * 1000
            
            if usage >= self._critical_threshold:
                status = HealthStatus.UNHEALTHY
                message = f"Critical disk usage: {disk.percent}%"
            elif usage >= self._warning_threshold:
                status = HealthStatus.DEGRADED
                message = f"High disk usage: {disk.percent}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"Disk usage: {disk.percent}%"
            
            return CheckResult(
                name=self._name,
                status=status,
                message=message,
                duration_ms=duration,
                details={
                    "path": self._path,
                    "total": disk.total,
                    "free": disk.free,
                    "percent": disk.percent,
                },
            )
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            return CheckResult(
                name=self._name,
                status=HealthStatus.UNKNOWN,
                message=str(e),
                duration_ms=duration,
                error=type(e).__name__,
            )


class HealthChecker:
    """
    Health checker that aggregates multiple checks.
    """
    
    def __init__(self):
        self._checks: Dict[str, HealthCheck] = {}
        self._liveness_checks: Set[str] = set()
        self._readiness_checks: Set[str] = set()
        self._startup_checks: Set[str] = set()
        self._cache: Optional[HealthReport] = None
        self._cache_ttl: Optional[float] = None
        self._cache_time: Optional[float] = None
    
    def add(
        self,
        name: str,
        check: Any,
        check_type: CheckType = CheckType.READINESS,
        timeout: float = 5.0,
    ) -> HealthChecker:
        """Add a health check."""
        if isinstance(check, HealthCheck):
            self._checks[name] = check
        elif callable(check):
            self._checks[name] = FunctionHealthCheck(name, check, timeout)
        else:
            raise ValueError(f"Invalid check type: {type(check)}")
        
        if check_type == CheckType.LIVENESS:
            self._liveness_checks.add(name)
        elif check_type == CheckType.READINESS:
            self._readiness_checks.add(name)
        elif check_type == CheckType.STARTUP:
            self._startup_checks.add(name)
        
        return self
    
    def add_liveness(
        self,
        name: str,
        check: Any,
        timeout: float = 5.0,
    ) -> HealthChecker:
        """Add a liveness check."""
        return self.add(name, check, CheckType.LIVENESS, timeout)
    
    def add_readiness(
        self,
        name: str,
        check: Any,
        timeout: float = 5.0,
    ) -> HealthChecker:
        """Add a readiness check."""
        return self.add(name, check, CheckType.READINESS, timeout)
    
    def add_startup(
        self,
        name: str,
        check: Any,
        timeout: float = 5.0,
    ) -> HealthChecker:
        """Add a startup check."""
        return self.add(name, check, CheckType.STARTUP, timeout)
    
    def set_cache_ttl(self, seconds: float) -> HealthChecker:
        """Set cache TTL for health check results."""
        self._cache_ttl = seconds
        return self
    
    async def check(
        self,
        check_names: Optional[List[str]] = None,
    ) -> HealthReport:
        """Run health checks."""
        # Check cache
        if (
            self._cache
            and self._cache_ttl
            and self._cache_time
            and (time.time() - self._cache_time) < self._cache_ttl
        ):
            return self._cache
        
        start = time.perf_counter()
        
        # Determine which checks to run
        if check_names:
            checks_to_run = {
                name: self._checks[name]
                for name in check_names
                if name in self._checks
            }
        else:
            checks_to_run = self._checks
        
        # Run checks in parallel
        tasks = [
            check.check()
            for check in checks_to_run.values()
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        check_results = []
        for result in results:
            if isinstance(result, Exception):
                check_results.append(CheckResult(
                    name="unknown",
                    status=HealthStatus.UNHEALTHY,
                    error=str(result),
                ))
            else:
                check_results.append(result)
        
        # Determine overall status
        statuses = [r.status for r in check_results]
        
        if all(s == HealthStatus.HEALTHY for s in statuses):
            overall_status = HealthStatus.HEALTHY
        elif any(s == HealthStatus.UNHEALTHY for s in statuses):
            overall_status = HealthStatus.UNHEALTHY
        elif any(s == HealthStatus.DEGRADED for s in statuses):
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.UNKNOWN
        
        duration = (time.perf_counter() - start) * 1000
        
        report = HealthReport(
            status=overall_status,
            checks=check_results,
            duration_ms=duration,
        )
        
        # Update cache
        self._cache = report
        self._cache_time = time.time()
        
        return report
    
    async def liveness(self) -> HealthReport:
        """Run liveness checks."""
        return await self.check(list(self._liveness_checks))
    
    async def readiness(self) -> HealthReport:
        """Run readiness checks."""
        return await self.check(list(self._readiness_checks))
    
    async def startup(self) -> HealthReport:
        """Run startup checks."""
        return await self.check(list(self._startup_checks))


class HealthServer:
    """
    HTTP server for health endpoints.
    """
    
    def __init__(
        self,
        checker: HealthChecker,
        host: str = "0.0.0.0",
        port: int = 8080,
    ):
        self._checker = checker
        self._host = host
        self._port = port
        self._server = None
    
    async def start(self) -> None:
        """Start health server."""
        from aiohttp import web
        
        app = web.Application()
        app.router.add_get("/health", self._health_handler)
        app.router.add_get("/health/live", self._liveness_handler)
        app.router.add_get("/health/ready", self._readiness_handler)
        
        runner = web.AppRunner(app)
        await runner.setup()
        
        self._server = web.TCPSite(runner, self._host, self._port)
        await self._server.start()
        
        logger.info(f"Health server started on {self._host}:{self._port}")
    
    async def stop(self) -> None:
        """Stop health server."""
        if self._server:
            await self._server.stop()
    
    async def _health_handler(self, request):
        from aiohttp import web
        
        report = await self._checker.check()
        status = 200 if report.is_healthy else 503
        return web.json_response(report.to_dict(), status=status)
    
    async def _liveness_handler(self, request):
        from aiohttp import web
        
        report = await self._checker.liveness()
        status = 200 if report.is_healthy else 503
        return web.json_response(report.to_dict(), status=status)
    
    async def _readiness_handler(self, request):
        from aiohttp import web
        
        report = await self._checker.readiness()
        status = 200 if report.is_healthy else 503
        return web.json_response(report.to_dict(), status=status)


class HealthMonitor:
    """
    Continuous health monitoring.
    """
    
    def __init__(
        self,
        checker: HealthChecker,
        interval: float = 30.0,
    ):
        self._checker = checker
        self._interval = interval
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._callbacks: List[Callable[[HealthReport], Any]] = []
        self._last_report: Optional[HealthReport] = None
    
    def on_check(
        self,
        callback: Callable[[HealthReport], Any],
    ) -> None:
        """Register callback for health check results."""
        self._callbacks.append(callback)
    
    async def start(self) -> None:
        """Start monitoring."""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("Health monitoring started")
    
    async def stop(self) -> None:
        """Stop monitoring."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Health monitoring stopped")
    
    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                report = await self._checker.check()
                self._last_report = report
                
                # Notify callbacks
                for callback in self._callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(report)
                        else:
                            callback(report)
                    except Exception as e:
                        logger.error(f"Callback error: {e}")
                
                await asyncio.sleep(self._interval)
                
            except Exception as e:
                logger.error(f"Monitor error: {e}")
                await asyncio.sleep(self._interval)
    
    @property
    def last_report(self) -> Optional[HealthReport]:
        """Get last health report."""
        return self._last_report


class HealthRegistry:
    """
    Registry for health checkers.
    """
    
    def __init__(self):
        self._checkers: Dict[str, HealthChecker] = {}
        self._default: Optional[str] = None
    
    def register(
        self,
        name: str,
        checker: HealthChecker,
        default: bool = False,
    ) -> None:
        """Register a checker."""
        self._checkers[name] = checker
        if default or self._default is None:
            self._default = name
    
    def get(self, name: Optional[str] = None) -> HealthChecker:
        """Get a checker."""
        name = name or self._default
        if not name or name not in self._checkers:
            raise HealthCheckError(f"Checker not found: {name}")
        return self._checkers[name]


# Global registry
_global_registry = HealthRegistry()


# Decorators
def health_check(
    name: str,
    check_type: CheckType = CheckType.READINESS,
) -> Callable:
    """
    Decorator for health check functions.
    
    Example:
        @health_check("database")
        async def check_database():
            return await db.ping()
    """
    def decorator(func: Callable) -> Callable:
        func._health_check_name = name
        func._health_check_type = check_type
        return func
    
    return decorator


def liveness_check(name: str) -> Callable:
    """Decorator for liveness check."""
    return health_check(name, CheckType.LIVENESS)


def readiness_check(name: str) -> Callable:
    """Decorator for readiness check."""
    return health_check(name, CheckType.READINESS)


# Factory functions
def create_health_checker() -> HealthChecker:
    """Create a health checker."""
    return HealthChecker()


def create_health_server(
    checker: HealthChecker,
    host: str = "0.0.0.0",
    port: int = 8080,
) -> HealthServer:
    """Create a health server."""
    return HealthServer(checker, host, port)


def create_health_monitor(
    checker: HealthChecker,
    interval: float = 30.0,
) -> HealthMonitor:
    """Create a health monitor."""
    return HealthMonitor(checker, interval)


def create_http_check(
    name: str,
    url: str,
    expected_status: int = 200,
) -> HttpHealthCheck:
    """Create an HTTP health check."""
    return HttpHealthCheck(name, url, expected_status)


def create_tcp_check(
    name: str,
    host: str,
    port: int,
) -> TcpHealthCheck:
    """Create a TCP health check."""
    return TcpHealthCheck(name, host, port)


def create_memory_check(
    warning_threshold: float = 0.8,
    critical_threshold: float = 0.9,
) -> MemoryHealthCheck:
    """Create a memory health check."""
    return MemoryHealthCheck(
        warning_threshold=warning_threshold,
        critical_threshold=critical_threshold,
    )


def create_disk_check(
    path: str = "/",
    warning_threshold: float = 0.8,
    critical_threshold: float = 0.9,
) -> DiskHealthCheck:
    """Create a disk health check."""
    return DiskHealthCheck(
        path=path,
        warning_threshold=warning_threshold,
        critical_threshold=critical_threshold,
    )


def register_checker(
    name: str,
    checker: HealthChecker,
    default: bool = False,
) -> None:
    """Register checker in global registry."""
    _global_registry.register(name, checker, default)


def get_checker(name: Optional[str] = None) -> HealthChecker:
    """Get checker from global registry."""
    return _global_registry.get(name)


__all__ = [
    # Exceptions
    "HealthCheckError",
    # Enums
    "HealthStatus",
    "CheckType",
    # Data classes
    "CheckResult",
    "HealthReport",
    # Checks
    "HealthCheck",
    "FunctionHealthCheck",
    "HttpHealthCheck",
    "TcpHealthCheck",
    "MemoryHealthCheck",
    "DiskHealthCheck",
    # Checker
    "HealthChecker",
    "HealthServer",
    "HealthMonitor",
    # Registry
    "HealthRegistry",
    # Decorators
    "health_check",
    "liveness_check",
    "readiness_check",
    # Factory functions
    "create_health_checker",
    "create_health_server",
    "create_health_monitor",
    "create_http_check",
    "create_tcp_check",
    "create_memory_check",
    "create_disk_check",
    "register_checker",
    "get_checker",
]
