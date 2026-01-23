"""
Enterprise Service Discovery Module.

Service registration, discovery, health checking,
and load balancing for microservices.

Example:
    # Create service registry
    registry = create_service_registry()
    
    # Register service
    instance = await registry.register(
        service="user-service",
        host="10.0.0.1",
        port=8080,
        metadata={"version": "1.0.0"},
    )
    
    # Discover services
    instances = await registry.discover("user-service")
    
    # Get healthy instance
    instance = await registry.get_instance(
        "user-service",
        strategy="round_robin",
    )
    
    # Health check
    health = await registry.check_health(instance.id)
"""

from __future__ import annotations

import asyncio
import functools
import logging
import random
import time
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    Iterator,
    List,
    Optional,
    Set,
    Tuple,
    TypeVar,
)

T = TypeVar('T')


logger = logging.getLogger(__name__)


class ServiceDiscoveryError(Exception):
    """Service discovery error."""
    pass


class ServiceNotFoundError(ServiceDiscoveryError):
    """Service not found."""
    pass


class NoHealthyInstanceError(ServiceDiscoveryError):
    """No healthy instances available."""
    pass


class RegistrationError(ServiceDiscoveryError):
    """Registration error."""
    pass


class InstanceStatus(str, Enum):
    """Instance status."""
    STARTING = "starting"
    UP = "up"
    DOWN = "down"
    OUT_OF_SERVICE = "out_of_service"
    UNKNOWN = "unknown"


class HealthStatus(str, Enum):
    """Health status."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class LoadBalanceStrategy(str, Enum):
    """Load balancing strategy."""
    ROUND_ROBIN = "round_robin"
    RANDOM = "random"
    LEAST_CONNECTIONS = "least_connections"
    WEIGHTED = "weighted"
    IP_HASH = "ip_hash"


@dataclass
class ServiceInstance:
    """Service instance."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    service: str = ""
    host: str = ""
    port: int = 0
    status: InstanceStatus = InstanceStatus.UP
    health: HealthStatus = HealthStatus.UNKNOWN
    weight: int = 100
    metadata: Dict[str, Any] = field(default_factory=dict)
    registered_at: datetime = field(default_factory=datetime.utcnow)
    last_heartbeat: datetime = field(default_factory=datetime.utcnow)
    last_health_check: Optional[datetime] = None
    active_connections: int = 0
    
    @property
    def address(self) -> str:
        """Get address."""
        return f"{self.host}:{self.port}"
    
    @property
    def uri(self) -> str:
        """Get URI."""
        scheme = self.metadata.get("scheme", "http")
        return f"{scheme}://{self.host}:{self.port}"
    
    def is_healthy(self) -> bool:
        """Check if healthy."""
        return (
            self.status == InstanceStatus.UP and
            self.health in (HealthStatus.HEALTHY, HealthStatus.UNKNOWN)
        )


@dataclass
class ServiceDefinition:
    """Service definition."""
    name: str
    description: str = ""
    version: str = "1.0.0"
    instances: List[ServiceInstance] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def healthy_instances(self) -> List[ServiceInstance]:
        """Get healthy instances."""
        return [i for i in self.instances if i.is_healthy()]
    
    def instance_count(self) -> int:
        """Get instance count."""
        return len(self.instances)


@dataclass
class HealthCheckConfig:
    """Health check configuration."""
    enabled: bool = True
    interval: timedelta = field(default_factory=lambda: timedelta(seconds=30))
    timeout: timedelta = field(default_factory=lambda: timedelta(seconds=5))
    healthy_threshold: int = 2
    unhealthy_threshold: int = 3
    path: str = "/health"


@dataclass
class HealthCheckResult:
    """Health check result."""
    status: HealthStatus
    latency_ms: float = 0.0
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    checked_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class RegistryStats:
    """Registry statistics."""
    total_services: int = 0
    total_instances: int = 0
    healthy_instances: int = 0
    unhealthy_instances: int = 0
    services_by_status: Dict[str, int] = field(default_factory=dict)


# Health checker interface
class HealthChecker(ABC):
    """Abstract health checker."""
    
    @abstractmethod
    async def check(
        self,
        instance: ServiceInstance,
        config: HealthCheckConfig,
    ) -> HealthCheckResult:
        """Check instance health."""
        pass


class HTTPHealthChecker(HealthChecker):
    """HTTP health checker."""
    
    async def check(
        self,
        instance: ServiceInstance,
        config: HealthCheckConfig,
    ) -> HealthCheckResult:
        """Check health via HTTP."""
        # Mock implementation
        start = time.perf_counter()
        
        # Simulate health check
        await asyncio.sleep(0.01)
        
        latency = (time.perf_counter() - start) * 1000
        
        return HealthCheckResult(
            status=HealthStatus.HEALTHY,
            latency_ms=latency,
            message="OK",
        )


class TCPHealthChecker(HealthChecker):
    """TCP health checker."""
    
    async def check(
        self,
        instance: ServiceInstance,
        config: HealthCheckConfig,
    ) -> HealthCheckResult:
        """Check health via TCP connection."""
        start = time.perf_counter()
        
        try:
            # Try to open connection
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(instance.host, instance.port),
                timeout=config.timeout.total_seconds(),
            )
            writer.close()
            await writer.wait_closed()
            
            latency = (time.perf_counter() - start) * 1000
            
            return HealthCheckResult(
                status=HealthStatus.HEALTHY,
                latency_ms=latency,
            )
            
        except Exception as e:
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message=str(e),
            )


# Load balancer
class LoadBalancer:
    """Load balancer."""
    
    def __init__(self):
        self._round_robin_index: Dict[str, int] = defaultdict(int)
    
    def select(
        self,
        service: str,
        instances: List[ServiceInstance],
        strategy: LoadBalanceStrategy = LoadBalanceStrategy.ROUND_ROBIN,
        client_ip: Optional[str] = None,
    ) -> Optional[ServiceInstance]:
        """
        Select instance using strategy.
        
        Args:
            service: Service name
            instances: Available instances
            strategy: Load balance strategy
            client_ip: Client IP for IP_HASH
            
        Returns:
            Selected instance or None
        """
        if not instances:
            return None
        
        # Filter healthy
        healthy = [i for i in instances if i.is_healthy()]
        
        if not healthy:
            return None
        
        if strategy == LoadBalanceStrategy.RANDOM:
            return random.choice(healthy)
        
        elif strategy == LoadBalanceStrategy.ROUND_ROBIN:
            idx = self._round_robin_index[service] % len(healthy)
            self._round_robin_index[service] += 1
            return healthy[idx]
        
        elif strategy == LoadBalanceStrategy.LEAST_CONNECTIONS:
            return min(healthy, key=lambda i: i.active_connections)
        
        elif strategy == LoadBalanceStrategy.WEIGHTED:
            total = sum(i.weight for i in healthy)
            r = random.uniform(0, total)
            
            cumulative = 0
            for instance in healthy:
                cumulative += instance.weight
                if r <= cumulative:
                    return instance
            
            return healthy[-1]
        
        elif strategy == LoadBalanceStrategy.IP_HASH:
            if client_ip:
                idx = hash(client_ip) % len(healthy)
                return healthy[idx]
            return random.choice(healthy)
        
        return healthy[0]


# Service registry
class ServiceRegistry:
    """
    Service registry.
    """
    
    def __init__(
        self,
        health_check_config: Optional[HealthCheckConfig] = None,
        heartbeat_interval: timedelta = timedelta(seconds=30),
        instance_timeout: timedelta = timedelta(seconds=90),
    ):
        self._services: Dict[str, ServiceDefinition] = {}
        self._instances: Dict[str, ServiceInstance] = {}
        self._health_config = health_check_config or HealthCheckConfig()
        self._heartbeat_interval = heartbeat_interval
        self._instance_timeout = instance_timeout
        self._health_checker: HealthChecker = HTTPHealthChecker()
        self._load_balancer = LoadBalancer()
        self._health_check_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._hooks: Dict[str, List[Callable]] = defaultdict(list)
    
    async def register(
        self,
        service: str,
        host: str,
        port: int,
        metadata: Optional[Dict[str, Any]] = None,
        weight: int = 100,
    ) -> ServiceInstance:
        """
        Register service instance.
        
        Args:
            service: Service name
            host: Host address
            port: Port number
            metadata: Instance metadata
            weight: Load balancing weight
            
        Returns:
            Registered instance
        """
        # Create or get service
        if service not in self._services:
            self._services[service] = ServiceDefinition(name=service)
        
        svc = self._services[service]
        
        # Check for existing instance
        for instance in svc.instances:
            if instance.host == host and instance.port == port:
                # Update existing
                instance.status = InstanceStatus.UP
                instance.last_heartbeat = datetime.utcnow()
                instance.metadata.update(metadata or {})
                
                await self._trigger("instance_updated", service, instance)
                return instance
        
        # Create new instance
        instance = ServiceInstance(
            service=service,
            host=host,
            port=port,
            metadata=metadata or {},
            weight=weight,
        )
        
        svc.instances.append(instance)
        self._instances[instance.id] = instance
        
        await self._trigger("instance_registered", service, instance)
        
        logger.info(f"Registered {service} at {instance.address}")
        
        return instance
    
    async def deregister(
        self,
        instance_id: str,
    ) -> bool:
        """
        Deregister service instance.
        
        Args:
            instance_id: Instance ID
            
        Returns:
            True if deregistered
        """
        if instance_id not in self._instances:
            return False
        
        instance = self._instances[instance_id]
        service = instance.service
        
        if service in self._services:
            self._services[service].instances = [
                i for i in self._services[service].instances
                if i.id != instance_id
            ]
        
        del self._instances[instance_id]
        
        await self._trigger("instance_deregistered", service, instance)
        
        logger.info(f"Deregistered {service} instance {instance_id}")
        
        return True
    
    async def discover(
        self,
        service: str,
        healthy_only: bool = True,
    ) -> List[ServiceInstance]:
        """
        Discover service instances.
        
        Args:
            service: Service name
            healthy_only: Return only healthy instances
            
        Returns:
            List of instances
        """
        if service not in self._services:
            return []
        
        instances = self._services[service].instances
        
        if healthy_only:
            return [i for i in instances if i.is_healthy()]
        
        return list(instances)
    
    async def get_instance(
        self,
        service: str,
        strategy: LoadBalanceStrategy = LoadBalanceStrategy.ROUND_ROBIN,
        client_ip: Optional[str] = None,
    ) -> ServiceInstance:
        """
        Get single instance using load balancing.
        
        Args:
            service: Service name
            strategy: Load balancing strategy
            client_ip: Client IP for IP_HASH
            
        Returns:
            Selected instance
            
        Raises:
            NoHealthyInstanceError: If no healthy instances
        """
        instances = await self.discover(service, healthy_only=True)
        
        if not instances:
            raise NoHealthyInstanceError(f"No healthy instances for {service}")
        
        instance = self._load_balancer.select(
            service, instances, strategy, client_ip
        )
        
        if not instance:
            raise NoHealthyInstanceError(f"No healthy instances for {service}")
        
        return instance
    
    async def heartbeat(self, instance_id: str) -> bool:
        """
        Send heartbeat for instance.
        
        Args:
            instance_id: Instance ID
            
        Returns:
            True if successful
        """
        if instance_id not in self._instances:
            return False
        
        instance = self._instances[instance_id]
        instance.last_heartbeat = datetime.utcnow()
        instance.status = InstanceStatus.UP
        
        return True
    
    async def check_health(
        self,
        instance_id: str,
    ) -> HealthCheckResult:
        """
        Check instance health.
        
        Args:
            instance_id: Instance ID
            
        Returns:
            Health check result
        """
        if instance_id not in self._instances:
            return HealthCheckResult(
                status=HealthStatus.UNKNOWN,
                message="Instance not found",
            )
        
        instance = self._instances[instance_id]
        
        result = await self._health_checker.check(
            instance, self._health_config
        )
        
        instance.health = result.status
        instance.last_health_check = result.checked_at
        
        if result.status == HealthStatus.UNHEALTHY:
            await self._trigger("instance_unhealthy", instance.service, instance)
        
        return result
    
    async def set_status(
        self,
        instance_id: str,
        status: InstanceStatus,
    ) -> bool:
        """Set instance status."""
        if instance_id not in self._instances:
            return False
        
        self._instances[instance_id].status = status
        return True
    
    def get_service(self, name: str) -> Optional[ServiceDefinition]:
        """Get service definition."""
        return self._services.get(name)
    
    def list_services(self) -> List[str]:
        """List all services."""
        return list(self._services.keys())
    
    async def get_stats(self) -> RegistryStats:
        """Get registry statistics."""
        stats = RegistryStats(
            total_services=len(self._services),
        )
        
        for svc in self._services.values():
            stats.total_instances += len(svc.instances)
            
            for instance in svc.instances:
                if instance.is_healthy():
                    stats.healthy_instances += 1
                else:
                    stats.unhealthy_instances += 1
                
                status = instance.status.value
                stats.services_by_status[status] = (
                    stats.services_by_status.get(status, 0) + 1
                )
        
        return stats
    
    def on(
        self,
        event: str,
        handler: Callable,
    ) -> None:
        """Add event handler."""
        self._hooks[event].append(handler)
    
    async def _trigger(
        self,
        event: str,
        *args,
        **kwargs,
    ) -> None:
        """Trigger event handlers."""
        for handler in self._hooks[event]:
            if asyncio.iscoroutinefunction(handler):
                await handler(*args, **kwargs)
            else:
                handler(*args, **kwargs)
    
    async def start_background_tasks(self) -> None:
        """Start background tasks."""
        if self._health_config.enabled:
            self._health_check_task = asyncio.create_task(
                self._health_check_loop()
            )
        
        self._cleanup_task = asyncio.create_task(
            self._cleanup_loop()
        )
    
    async def stop_background_tasks(self) -> None:
        """Stop background tasks."""
        if self._health_check_task:
            self._health_check_task.cancel()
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
    
    async def _health_check_loop(self) -> None:
        """Health check loop."""
        while True:
            try:
                await asyncio.sleep(
                    self._health_config.interval.total_seconds()
                )
                
                for instance in list(self._instances.values()):
                    await self.check_health(instance.id)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")
    
    async def _cleanup_loop(self) -> None:
        """Cleanup expired instances."""
        while True:
            try:
                await asyncio.sleep(60)
                
                now = datetime.utcnow()
                timeout = self._instance_timeout
                
                expired = []
                
                for instance in self._instances.values():
                    if now - instance.last_heartbeat > timeout:
                        expired.append(instance.id)
                
                for instance_id in expired:
                    await self.deregister(instance_id)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup error: {e}")


# Service client helper
class ServiceClient:
    """
    Helper for calling discovered services.
    
    Example:
        client = ServiceClient(registry)
        result = await client.call("user-service", "/users/123")
    """
    
    def __init__(
        self,
        registry: ServiceRegistry,
        strategy: LoadBalanceStrategy = LoadBalanceStrategy.ROUND_ROBIN,
    ):
        self._registry = registry
        self._strategy = strategy
    
    async def get_uri(
        self,
        service: str,
        path: str = "",
    ) -> str:
        """Get service URI."""
        instance = await self._registry.get_instance(
            service, self._strategy
        )
        
        uri = instance.uri
        if path:
            uri = f"{uri}/{path.lstrip('/')}"
        
        return uri
    
    async def call(
        self,
        service: str,
        path: str = "",
        method: str = "GET",
        **kwargs,
    ) -> Any:
        """
        Call service (mock implementation).
        
        Args:
            service: Service name
            path: Request path
            method: HTTP method
            **kwargs: Additional arguments
            
        Returns:
            Mock response
        """
        uri = await self.get_uri(service, path)
        
        # Mock HTTP call
        return {
            "uri": uri,
            "method": method,
            "status": 200,
        }


# Decorators
def discoverable(
    registry: ServiceRegistry,
    service: str,
    host: str = "localhost",
    port: int = 8080,
):
    """
    Decorator to auto-register service.
    
    Args:
        registry: Service registry
        service: Service name
        host: Host address
        port: Port number
    """
    def decorator(cls):
        original_init = cls.__init__
        
        @functools.wraps(original_init)
        def new_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            
            asyncio.create_task(
                registry.register(service, host, port)
            )
        
        cls.__init__ = new_init
        return cls
    
    return decorator


# Factory functions
def create_service_registry(
    health_check_enabled: bool = True,
    health_check_interval: int = 30,
    instance_timeout: int = 90,
) -> ServiceRegistry:
    """Create service registry."""
    return ServiceRegistry(
        health_check_config=HealthCheckConfig(
            enabled=health_check_enabled,
            interval=timedelta(seconds=health_check_interval),
        ),
        instance_timeout=timedelta(seconds=instance_timeout),
    )


def create_service_client(
    registry: ServiceRegistry,
    strategy: LoadBalanceStrategy = LoadBalanceStrategy.ROUND_ROBIN,
) -> ServiceClient:
    """Create service client."""
    return ServiceClient(registry=registry, strategy=strategy)


__all__ = [
    # Exceptions
    "ServiceDiscoveryError",
    "ServiceNotFoundError",
    "NoHealthyInstanceError",
    "RegistrationError",
    # Enums
    "InstanceStatus",
    "HealthStatus",
    "LoadBalanceStrategy",
    # Data classes
    "ServiceInstance",
    "ServiceDefinition",
    "HealthCheckConfig",
    "HealthCheckResult",
    "RegistryStats",
    # Health checkers
    "HealthChecker",
    "HTTPHealthChecker",
    "TCPHealthChecker",
    # Load balancer
    "LoadBalancer",
    # Registry
    "ServiceRegistry",
    # Client
    "ServiceClient",
    # Decorators
    "discoverable",
    # Factory functions
    "create_service_registry",
    "create_service_client",
]
