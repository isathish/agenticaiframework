"""
Enterprise Health Monitor Module.

System health checks, probes, dashboards,
and availability monitoring.

Example:
    # Create health monitor
    monitor = create_health_monitor()
    
    # Register health checks
    @monitor.check("database")
    async def check_database():
        await db.ping()
        return HealthResult(status=HealthStatus.HEALTHY)
    
    # Register dependency
    monitor.register_dependency(
        "redis",
        url="redis://localhost:6379",
        check_type=CheckType.TCP,
    )
    
    # Run health check
    result = await monitor.check_health()
    
    # Get readiness/liveness probes
    ready = await monitor.readiness_probe()
    alive = await monitor.liveness_probe()
"""

from __future__ import annotations

import asyncio
import functools
import logging
import socket
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    Tuple,
    TypeVar,
    Union,
)
from urllib.parse import urlparse

T = TypeVar('T')


logger = logging.getLogger(__name__)


class HealthError(Exception):
    """Health check error."""
    pass


class CheckTimeoutError(HealthError):
    """Check timeout error."""
    pass


class HealthStatus(str, Enum):
    """Health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class CheckType(str, Enum):
    """Health check type."""
    HTTP = "http"
    TCP = "tcp"
    EXEC = "exec"
    GRPC = "grpc"
    DNS = "dns"
    CUSTOM = "custom"


class SeverityLevel(str, Enum):
    """Severity level."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class HealthResult:
    """Health check result."""
    status: HealthStatus = HealthStatus.UNKNOWN
    message: Optional[str] = None
    latency_ms: float = 0.0
    checked_at: datetime = field(default_factory=datetime.utcnow)
    details: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class ComponentHealth:
    """Component health status."""
    name: str
    status: HealthStatus = HealthStatus.UNKNOWN
    result: Optional[HealthResult] = None
    check_type: CheckType = CheckType.CUSTOM
    severity: SeverityLevel = SeverityLevel.MEDIUM
    last_healthy: Optional[datetime] = None
    consecutive_failures: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DependencyConfig:
    """Dependency configuration."""
    name: str
    url: Optional[str] = None
    check_type: CheckType = CheckType.TCP
    timeout_seconds: float = 5.0
    interval_seconds: float = 30.0
    severity: SeverityLevel = SeverityLevel.MEDIUM
    required: bool = True
    headers: Dict[str, str] = field(default_factory=dict)
    expected_status: int = 200
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SystemHealth:
    """Overall system health."""
    status: HealthStatus = HealthStatus.UNKNOWN
    components: Dict[str, ComponentHealth] = field(default_factory=dict)
    healthy_count: int = 0
    unhealthy_count: int = 0
    degraded_count: int = 0
    checked_at: datetime = field(default_factory=datetime.utcnow)
    uptime_seconds: float = 0.0
    version: Optional[str] = None


@dataclass
class HealthMetrics:
    """Health metrics."""
    total_checks: int = 0
    successful_checks: int = 0
    failed_checks: int = 0
    average_latency_ms: float = 0.0
    uptime_percentage: float = 100.0
    last_outage: Optional[datetime] = None
    last_recovery: Optional[datetime] = None


# Health checker interface
class HealthChecker(ABC):
    """Abstract health checker."""
    
    @abstractmethod
    async def check(self, config: DependencyConfig) -> HealthResult:
        """Perform health check."""
        pass


class TCPHealthChecker(HealthChecker):
    """TCP health checker."""
    
    async def check(self, config: DependencyConfig) -> HealthResult:
        """Check TCP connectivity."""
        start = time.perf_counter()
        
        try:
            parsed = urlparse(config.url or "")
            host = parsed.hostname or "localhost"
            port = parsed.port or 80
            
            loop = asyncio.get_event_loop()
            
            # Create socket with timeout
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(config.timeout_seconds)
            
            await loop.run_in_executor(
                None,
                lambda: sock.connect((host, port))
            )
            sock.close()
            
            latency = (time.perf_counter() - start) * 1000
            
            return HealthResult(
                status=HealthStatus.HEALTHY,
                message=f"TCP connection successful",
                latency_ms=latency,
            )
            
        except socket.timeout:
            return HealthResult(
                status=HealthStatus.UNHEALTHY,
                message="Connection timeout",
                error="timeout",
                latency_ms=(time.perf_counter() - start) * 1000,
            )
        except Exception as e:
            return HealthResult(
                status=HealthStatus.UNHEALTHY,
                message=str(e),
                error=str(e),
                latency_ms=(time.perf_counter() - start) * 1000,
            )


class HTTPHealthChecker(HealthChecker):
    """HTTP health checker."""
    
    async def check(self, config: DependencyConfig) -> HealthResult:
        """Check HTTP endpoint."""
        start = time.perf_counter()
        
        try:
            # Simple HTTP check without external dependencies
            parsed = urlparse(config.url or "http://localhost")
            host = parsed.hostname or "localhost"
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            path = parsed.path or "/"
            
            # Basic HTTP request
            request = f"GET {path} HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n"
            
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=config.timeout_seconds,
            )
            
            writer.write(request.encode())
            await writer.drain()
            
            response = await asyncio.wait_for(
                reader.read(1024),
                timeout=config.timeout_seconds,
            )
            
            writer.close()
            await writer.wait_closed()
            
            latency = (time.perf_counter() - start) * 1000
            
            # Parse status code
            status_line = response.decode().split("\r\n")[0]
            status_code = int(status_line.split()[1])
            
            if status_code == config.expected_status:
                return HealthResult(
                    status=HealthStatus.HEALTHY,
                    message=f"HTTP {status_code}",
                    latency_ms=latency,
                    details={"status_code": status_code},
                )
            else:
                return HealthResult(
                    status=HealthStatus.DEGRADED,
                    message=f"Unexpected status: {status_code}",
                    latency_ms=latency,
                    details={"status_code": status_code},
                )
                
        except asyncio.TimeoutError:
            return HealthResult(
                status=HealthStatus.UNHEALTHY,
                message="Request timeout",
                error="timeout",
                latency_ms=(time.perf_counter() - start) * 1000,
            )
        except Exception as e:
            return HealthResult(
                status=HealthStatus.UNHEALTHY,
                message=str(e),
                error=str(e),
                latency_ms=(time.perf_counter() - start) * 1000,
            )


class DNSHealthChecker(HealthChecker):
    """DNS health checker."""
    
    async def check(self, config: DependencyConfig) -> HealthResult:
        """Check DNS resolution."""
        start = time.perf_counter()
        
        try:
            parsed = urlparse(config.url or "")
            hostname = parsed.hostname or config.url
            
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: socket.gethostbyname(hostname)
            )
            
            latency = (time.perf_counter() - start) * 1000
            
            return HealthResult(
                status=HealthStatus.HEALTHY,
                message=f"Resolved to {result}",
                latency_ms=latency,
                details={"resolved_ip": result},
            )
            
        except socket.gaierror as e:
            return HealthResult(
                status=HealthStatus.UNHEALTHY,
                message=f"DNS resolution failed: {e}",
                error=str(e),
                latency_ms=(time.perf_counter() - start) * 1000,
            )


# Health monitor
class HealthMonitor:
    """
    Health monitoring service.
    """
    
    def __init__(
        self,
        version: Optional[str] = None,
        startup_time: Optional[datetime] = None,
    ):
        self._version = version
        self._startup_time = startup_time or datetime.utcnow()
        self._components: Dict[str, ComponentHealth] = {}
        self._dependencies: Dict[str, DependencyConfig] = {}
        self._custom_checks: Dict[str, Callable] = {}
        self._checkers: Dict[CheckType, HealthChecker] = {
            CheckType.TCP: TCPHealthChecker(),
            CheckType.HTTP: HTTPHealthChecker(),
            CheckType.DNS: DNSHealthChecker(),
        }
        self._metrics = HealthMetrics()
        self._monitoring_task: Optional[asyncio.Task] = None
        self._running = False
        self._hooks: Dict[str, List[Callable]] = {}
    
    def check(
        self,
        name: str,
        severity: SeverityLevel = SeverityLevel.MEDIUM,
        required: bool = True,
    ) -> Callable:
        """
        Decorator to register health check.
        
        Args:
            name: Check name
            severity: Severity level
            required: Whether component is required
            
        Returns:
            Decorator
        """
        def decorator(func: Callable) -> Callable:
            self._custom_checks[name] = func
            self._components[name] = ComponentHealth(
                name=name,
                check_type=CheckType.CUSTOM,
                severity=severity,
            )
            return func
        
        return decorator
    
    def register_dependency(
        self,
        name: str,
        url: Optional[str] = None,
        check_type: CheckType = CheckType.TCP,
        timeout_seconds: float = 5.0,
        interval_seconds: float = 30.0,
        severity: SeverityLevel = SeverityLevel.MEDIUM,
        required: bool = True,
        **kwargs,
    ) -> None:
        """
        Register external dependency.
        
        Args:
            name: Dependency name
            url: Dependency URL
            check_type: Check type
            timeout_seconds: Check timeout
            interval_seconds: Check interval
            severity: Severity level
            required: Whether dependency is required
            **kwargs: Additional config
        """
        config = DependencyConfig(
            name=name,
            url=url,
            check_type=check_type,
            timeout_seconds=timeout_seconds,
            interval_seconds=interval_seconds,
            severity=severity,
            required=required,
            **kwargs,
        )
        
        self._dependencies[name] = config
        self._components[name] = ComponentHealth(
            name=name,
            check_type=check_type,
            severity=severity,
        )
    
    def register_checker(
        self,
        check_type: CheckType,
        checker: HealthChecker,
    ) -> None:
        """Register custom checker."""
        self._checkers[check_type] = checker
    
    async def check_health(
        self,
        components: Optional[List[str]] = None,
    ) -> SystemHealth:
        """
        Check system health.
        
        Args:
            components: Specific components to check
            
        Returns:
            System health status
        """
        health = SystemHealth(
            version=self._version,
            uptime_seconds=(datetime.utcnow() - self._startup_time).total_seconds(),
        )
        
        components_to_check = (
            components
            if components
            else list(self._components.keys())
        )
        
        # Run all checks in parallel
        tasks = []
        names = []
        
        for name in components_to_check:
            if name in self._custom_checks:
                tasks.append(self._run_custom_check(name))
                names.append(name)
            elif name in self._dependencies:
                tasks.append(self._run_dependency_check(name))
                names.append(name)
        
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for name, result in zip(names, results):
                if isinstance(result, Exception):
                    component = self._components.get(name, ComponentHealth(name=name))
                    component.status = HealthStatus.UNHEALTHY
                    component.result = HealthResult(
                        status=HealthStatus.UNHEALTHY,
                        error=str(result),
                    )
                    component.consecutive_failures += 1
                else:
                    component = result
                
                health.components[name] = component
                
                if component.status == HealthStatus.HEALTHY:
                    health.healthy_count += 1
                elif component.status == HealthStatus.DEGRADED:
                    health.degraded_count += 1
                else:
                    health.unhealthy_count += 1
        
        # Determine overall status
        if health.unhealthy_count > 0:
            # Check if any critical components are unhealthy
            critical_unhealthy = any(
                c.severity == SeverityLevel.CRITICAL and c.status == HealthStatus.UNHEALTHY
                for c in health.components.values()
            )
            if critical_unhealthy:
                health.status = HealthStatus.UNHEALTHY
            else:
                health.status = HealthStatus.DEGRADED
        elif health.degraded_count > 0:
            health.status = HealthStatus.DEGRADED
        elif health.healthy_count > 0:
            health.status = HealthStatus.HEALTHY
        else:
            health.status = HealthStatus.UNKNOWN
        
        # Update metrics
        self._metrics.total_checks += 1
        if health.status == HealthStatus.HEALTHY:
            self._metrics.successful_checks += 1
        else:
            self._metrics.failed_checks += 1
        
        await self._trigger("health_checked", health)
        
        return health
    
    async def _run_custom_check(self, name: str) -> ComponentHealth:
        """Run custom health check."""
        component = self._components.get(name, ComponentHealth(name=name))
        check_func = self._custom_checks[name]
        
        start = time.perf_counter()
        
        try:
            if asyncio.iscoroutinefunction(check_func):
                result = await check_func()
            else:
                result = check_func()
            
            if isinstance(result, HealthResult):
                component.result = result
                component.status = result.status
            elif isinstance(result, bool):
                component.result = HealthResult(
                    status=HealthStatus.HEALTHY if result else HealthStatus.UNHEALTHY,
                    latency_ms=(time.perf_counter() - start) * 1000,
                )
                component.status = component.result.status
            else:
                component.result = HealthResult(
                    status=HealthStatus.HEALTHY,
                    latency_ms=(time.perf_counter() - start) * 1000,
                    details={"result": result},
                )
                component.status = HealthStatus.HEALTHY
            
            if component.status == HealthStatus.HEALTHY:
                component.last_healthy = datetime.utcnow()
                component.consecutive_failures = 0
            else:
                component.consecutive_failures += 1
                
        except Exception as e:
            component.result = HealthResult(
                status=HealthStatus.UNHEALTHY,
                error=str(e),
                latency_ms=(time.perf_counter() - start) * 1000,
            )
            component.status = HealthStatus.UNHEALTHY
            component.consecutive_failures += 1
        
        self._components[name] = component
        return component
    
    async def _run_dependency_check(self, name: str) -> ComponentHealth:
        """Run dependency health check."""
        component = self._components.get(name, ComponentHealth(name=name))
        config = self._dependencies[name]
        
        checker = self._checkers.get(config.check_type)
        
        if not checker:
            component.result = HealthResult(
                status=HealthStatus.UNKNOWN,
                message=f"No checker for {config.check_type}",
            )
            component.status = HealthStatus.UNKNOWN
            return component
        
        try:
            result = await asyncio.wait_for(
                checker.check(config),
                timeout=config.timeout_seconds + 1,
            )
            
            component.result = result
            component.status = result.status
            
            if component.status == HealthStatus.HEALTHY:
                component.last_healthy = datetime.utcnow()
                component.consecutive_failures = 0
            else:
                component.consecutive_failures += 1
                
        except asyncio.TimeoutError:
            component.result = HealthResult(
                status=HealthStatus.UNHEALTHY,
                error="Check timeout",
            )
            component.status = HealthStatus.UNHEALTHY
            component.consecutive_failures += 1
        except Exception as e:
            component.result = HealthResult(
                status=HealthStatus.UNHEALTHY,
                error=str(e),
            )
            component.status = HealthStatus.UNHEALTHY
            component.consecutive_failures += 1
        
        self._components[name] = component
        return component
    
    async def readiness_probe(self) -> Tuple[bool, Dict[str, Any]]:
        """
        Kubernetes readiness probe.
        
        Returns:
            (is_ready, details)
        """
        health = await self.check_health()
        
        # Ready if healthy or degraded
        is_ready = health.status in (HealthStatus.HEALTHY, HealthStatus.DEGRADED)
        
        details = {
            "status": health.status.value,
            "healthy_components": health.healthy_count,
            "unhealthy_components": health.unhealthy_count,
        }
        
        return is_ready, details
    
    async def liveness_probe(self) -> Tuple[bool, Dict[str, Any]]:
        """
        Kubernetes liveness probe.
        
        Returns:
            (is_alive, details)
        """
        # Basic liveness - just check that the service is running
        is_alive = True
        
        details = {
            "status": "alive",
            "uptime_seconds": (datetime.utcnow() - self._startup_time).total_seconds(),
            "version": self._version,
        }
        
        return is_alive, details
    
    async def startup_probe(self) -> Tuple[bool, Dict[str, Any]]:
        """
        Kubernetes startup probe.
        
        Returns:
            (is_started, details)
        """
        # Check critical dependencies
        health = await self.check_health()
        
        critical_healthy = all(
            c.status == HealthStatus.HEALTHY
            for c in health.components.values()
            if c.severity == SeverityLevel.CRITICAL
        )
        
        details = {
            "status": "started" if critical_healthy else "starting",
            "critical_dependencies_healthy": critical_healthy,
        }
        
        return critical_healthy, details
    
    async def start_monitoring(
        self,
        interval_seconds: float = 30.0,
    ) -> None:
        """Start background monitoring."""
        self._running = True
        self._monitoring_task = asyncio.create_task(
            self._monitoring_loop(interval_seconds)
        )
        logger.info("Health monitoring started")
    
    async def stop_monitoring(self) -> None:
        """Stop background monitoring."""
        self._running = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
        logger.info("Health monitoring stopped")
    
    async def _monitoring_loop(self, interval: float) -> None:
        """Background monitoring loop."""
        while self._running:
            try:
                health = await self.check_health()
                
                # Trigger alerts for unhealthy components
                for name, component in health.components.items():
                    if (
                        component.status == HealthStatus.UNHEALTHY and
                        component.consecutive_failures >= 3
                    ):
                        await self._trigger("component_unhealthy", component)
                
                await asyncio.sleep(interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitoring error: {e}")
                await asyncio.sleep(interval)
    
    def get_component(self, name: str) -> Optional[ComponentHealth]:
        """Get component health."""
        return self._components.get(name)
    
    def get_metrics(self) -> HealthMetrics:
        """Get health metrics."""
        if self._metrics.total_checks > 0:
            self._metrics.uptime_percentage = (
                self._metrics.successful_checks / self._metrics.total_checks * 100
            )
        return self._metrics
    
    def on(self, event: str, handler: Callable) -> None:
        """Add event handler."""
        if event not in self._hooks:
            self._hooks[event] = []
        self._hooks[event].append(handler)
    
    async def _trigger(self, event: str, *args, **kwargs) -> None:
        """Trigger event."""
        for handler in self._hooks.get(event, []):
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(*args, **kwargs)
                else:
                    handler(*args, **kwargs)
            except Exception as e:
                logger.error(f"Hook error: {e}")


# Factory functions
def create_health_monitor(
    version: Optional[str] = None,
) -> HealthMonitor:
    """Create health monitor."""
    return HealthMonitor(version=version)


def create_health_result(
    status: HealthStatus = HealthStatus.HEALTHY,
    message: Optional[str] = None,
    **kwargs,
) -> HealthResult:
    """Create health result."""
    return HealthResult(status=status, message=message, **kwargs)


__all__ = [
    # Exceptions
    "HealthError",
    "CheckTimeoutError",
    # Enums
    "HealthStatus",
    "CheckType",
    "SeverityLevel",
    # Data classes
    "HealthResult",
    "ComponentHealth",
    "DependencyConfig",
    "SystemHealth",
    "HealthMetrics",
    # Checkers
    "HealthChecker",
    "TCPHealthChecker",
    "HTTPHealthChecker",
    "DNSHealthChecker",
    # Monitor
    "HealthMonitor",
    # Factory functions
    "create_health_monitor",
    "create_health_result",
]
