"""
Enterprise Discovery Module.

Provides service discovery, registration, and health
monitoring for distributed systems.

Example:
    # Create service registry
    registry = create_service_registry()
    
    # Register a service
    await registry.register(
        name="api-service",
        address="localhost",
        port=8080,
        health_check="/health",
    )
    
    # Discover services
    services = await registry.discover("api-service")
    service = await registry.get_healthy("api-service")
    
    # With decorator
    @discoverable("worker-service")
    class WorkerService:
        ...
    
    # Client-side load balancing
    lb = create_load_balancer("api-service", strategy="round_robin")
    endpoint = await lb.next()
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import random
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
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

logger = logging.getLogger(__name__)

T = TypeVar('T')


class DiscoveryError(Exception):
    """Discovery error."""
    pass


class ServiceNotFoundError(DiscoveryError):
    """Service not found."""
    pass


class RegistrationError(DiscoveryError):
    """Registration error."""
    pass


class ServiceStatus(str, Enum):
    """Service status."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    STARTING = "starting"
    STOPPING = "stopping"
    MAINTENANCE = "maintenance"


class LoadBalanceStrategy(str, Enum):
    """Load balancing strategies."""
    ROUND_ROBIN = "round_robin"
    RANDOM = "random"
    LEAST_CONNECTIONS = "least_connections"
    WEIGHTED = "weighted"
    IP_HASH = "ip_hash"


@dataclass
class ServiceInstance:
    """Service instance."""
    id: str
    name: str
    address: str
    port: int
    status: ServiceStatus = ServiceStatus.UNKNOWN
    version: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    weight: int = 100
    health_check_path: Optional[str] = None
    last_heartbeat: Optional[datetime] = None
    registered_at: datetime = field(default_factory=datetime.now)
    
    @property
    def endpoint(self) -> str:
        """Get endpoint URL."""
        return f"http://{self.address}:{self.port}"
    
    def is_healthy(self) -> bool:
        """Check if service is healthy."""
        return self.status == ServiceStatus.HEALTHY


@dataclass
class ServiceDefinition:
    """Service definition."""
    name: str
    version: Optional[str] = None
    description: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    health_check_interval: int = 30
    ttl_seconds: int = 60


@dataclass
class HealthCheckResult:
    """Health check result."""
    healthy: bool
    message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    latency_ms: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DiscoveryStats:
    """Discovery statistics."""
    total_services: int = 0
    healthy_services: int = 0
    unhealthy_services: int = 0
    registrations: int = 0
    deregistrations: int = 0
    discoveries: int = 0


class ServiceRegistry(ABC):
    """Abstract service registry."""
    
    @abstractmethod
    async def register(
        self,
        instance: ServiceInstance,
    ) -> str:
        """Register a service instance."""
        pass
    
    @abstractmethod
    async def deregister(
        self,
        instance_id: str,
    ) -> bool:
        """Deregister a service instance."""
        pass
    
    @abstractmethod
    async def discover(
        self,
        name: str,
        tags: Optional[List[str]] = None,
    ) -> List[ServiceInstance]:
        """Discover service instances."""
        pass
    
    @abstractmethod
    async def get_instance(
        self,
        instance_id: str,
    ) -> Optional[ServiceInstance]:
        """Get instance by ID."""
        pass
    
    @abstractmethod
    async def heartbeat(
        self,
        instance_id: str,
    ) -> bool:
        """Send heartbeat for instance."""
        pass


class InMemoryServiceRegistry(ServiceRegistry):
    """In-memory service registry."""
    
    def __init__(
        self,
        ttl_seconds: int = 60,
    ):
        self._services: Dict[str, ServiceInstance] = {}
        self._by_name: Dict[str, Set[str]] = {}
        self._ttl_seconds = ttl_seconds
        self._stats = DiscoveryStats()
        self._cleanup_task: Optional[asyncio.Task] = None
    
    async def register(
        self,
        instance: ServiceInstance,
    ) -> str:
        """Register instance."""
        if not instance.id:
            instance.id = str(uuid.uuid4())
        
        instance.last_heartbeat = datetime.now()
        instance.registered_at = datetime.now()
        
        self._services[instance.id] = instance
        
        if instance.name not in self._by_name:
            self._by_name[instance.name] = set()
        self._by_name[instance.name].add(instance.id)
        
        self._stats.registrations += 1
        self._stats.total_services = len(self._services)
        
        logger.info(
            f"Registered service: {instance.name} at {instance.endpoint}"
        )
        
        return instance.id
    
    async def deregister(
        self,
        instance_id: str,
    ) -> bool:
        """Deregister instance."""
        instance = self._services.pop(instance_id, None)
        
        if instance:
            if instance.name in self._by_name:
                self._by_name[instance.name].discard(instance_id)
            
            self._stats.deregistrations += 1
            self._stats.total_services = len(self._services)
            
            logger.info(f"Deregistered service: {instance.name}")
            return True
        
        return False
    
    async def discover(
        self,
        name: str,
        tags: Optional[List[str]] = None,
    ) -> List[ServiceInstance]:
        """Discover services by name."""
        self._stats.discoveries += 1
        
        instance_ids = self._by_name.get(name, set())
        instances = []
        
        for instance_id in instance_ids:
            instance = self._services.get(instance_id)
            
            if instance:
                # Filter by tags
                if tags:
                    if not all(tag in instance.tags for tag in tags):
                        continue
                
                instances.append(instance)
        
        return instances
    
    async def get_instance(
        self,
        instance_id: str,
    ) -> Optional[ServiceInstance]:
        """Get instance by ID."""
        return self._services.get(instance_id)
    
    async def heartbeat(
        self,
        instance_id: str,
    ) -> bool:
        """Update heartbeat."""
        instance = self._services.get(instance_id)
        
        if instance:
            instance.last_heartbeat = datetime.now()
            instance.status = ServiceStatus.HEALTHY
            return True
        
        return False
    
    async def get_healthy(
        self,
        name: str,
    ) -> List[ServiceInstance]:
        """Get healthy instances only."""
        instances = await self.discover(name)
        return [i for i in instances if i.is_healthy()]
    
    async def update_status(
        self,
        instance_id: str,
        status: ServiceStatus,
    ) -> bool:
        """Update instance status."""
        instance = self._services.get(instance_id)
        
        if instance:
            instance.status = status
            return True
        
        return False
    
    async def start_cleanup(
        self,
        interval: int = 30,
    ) -> None:
        """Start cleanup task."""
        async def cleanup_loop():
            while True:
                try:
                    await asyncio.sleep(interval)
                    await self._cleanup_expired()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Cleanup error: {e}")
        
        self._cleanup_task = asyncio.create_task(cleanup_loop())
    
    async def stop_cleanup(self) -> None:
        """Stop cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
    
    async def _cleanup_expired(self) -> int:
        """Remove expired instances."""
        cutoff = datetime.now() - timedelta(seconds=self._ttl_seconds)
        expired = []
        
        for instance_id, instance in self._services.items():
            if instance.last_heartbeat and instance.last_heartbeat < cutoff:
                expired.append(instance_id)
        
        for instance_id in expired:
            await self.deregister(instance_id)
        
        return len(expired)
    
    def get_stats(self) -> DiscoveryStats:
        """Get statistics."""
        healthy = sum(
            1 for s in self._services.values()
            if s.is_healthy()
        )
        
        self._stats.healthy_services = healthy
        self._stats.unhealthy_services = len(self._services) - healthy
        
        return self._stats


class HealthChecker:
    """
    Health checker for service instances.
    """
    
    def __init__(
        self,
        timeout_seconds: float = 5.0,
    ):
        self._timeout = timeout_seconds
    
    async def check(
        self,
        instance: ServiceInstance,
    ) -> HealthCheckResult:
        """Check health of an instance."""
        start = time.time()
        
        if not instance.health_check_path:
            return HealthCheckResult(
                healthy=True,
                message="No health check configured",
            )
        
        try:
            # Simulate HTTP health check
            # In real implementation, use aiohttp or httpx
            await asyncio.sleep(0.01)  # Simulate network call
            
            latency_ms = (time.time() - start) * 1000
            
            return HealthCheckResult(
                healthy=True,
                message="OK",
                latency_ms=latency_ms,
            )
        
        except asyncio.TimeoutError:
            return HealthCheckResult(
                healthy=False,
                message="Health check timed out",
                latency_ms=self._timeout * 1000,
            )
        
        except Exception as e:
            return HealthCheckResult(
                healthy=False,
                message=str(e),
                latency_ms=(time.time() - start) * 1000,
            )
    
    async def check_all(
        self,
        instances: List[ServiceInstance],
    ) -> Dict[str, HealthCheckResult]:
        """Check all instances."""
        results = {}
        
        tasks = [self.check(instance) for instance in instances]
        check_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for instance, result in zip(instances, check_results):
            if isinstance(result, Exception):
                results[instance.id] = HealthCheckResult(
                    healthy=False,
                    message=str(result),
                )
            else:
                results[instance.id] = result
        
        return results


class LoadBalancer:
    """
    Client-side load balancer.
    """
    
    def __init__(
        self,
        service_name: str,
        registry: ServiceRegistry,
        strategy: LoadBalanceStrategy = LoadBalanceStrategy.ROUND_ROBIN,
    ):
        self._service_name = service_name
        self._registry = registry
        self._strategy = strategy
        self._index = 0
        self._connections: Dict[str, int] = {}
    
    async def next(
        self,
        client_ip: Optional[str] = None,
    ) -> Optional[ServiceInstance]:
        """Get next instance using load balancing."""
        instances = await self._registry.discover(self._service_name)
        healthy = [i for i in instances if i.is_healthy()]
        
        if not healthy:
            return None
        
        if self._strategy == LoadBalanceStrategy.ROUND_ROBIN:
            return self._round_robin(healthy)
        
        elif self._strategy == LoadBalanceStrategy.RANDOM:
            return self._random(healthy)
        
        elif self._strategy == LoadBalanceStrategy.WEIGHTED:
            return self._weighted(healthy)
        
        elif self._strategy == LoadBalanceStrategy.LEAST_CONNECTIONS:
            return self._least_connections(healthy)
        
        elif self._strategy == LoadBalanceStrategy.IP_HASH:
            return self._ip_hash(healthy, client_ip)
        
        return healthy[0]
    
    def _round_robin(
        self,
        instances: List[ServiceInstance],
    ) -> ServiceInstance:
        """Round robin selection."""
        instance = instances[self._index % len(instances)]
        self._index += 1
        return instance
    
    def _random(
        self,
        instances: List[ServiceInstance],
    ) -> ServiceInstance:
        """Random selection."""
        return random.choice(instances)
    
    def _weighted(
        self,
        instances: List[ServiceInstance],
    ) -> ServiceInstance:
        """Weighted random selection."""
        total_weight = sum(i.weight for i in instances)
        r = random.uniform(0, total_weight)
        
        current = 0
        for instance in instances:
            current += instance.weight
            if current >= r:
                return instance
        
        return instances[-1]
    
    def _least_connections(
        self,
        instances: List[ServiceInstance],
    ) -> ServiceInstance:
        """Select instance with least connections."""
        return min(
            instances,
            key=lambda i: self._connections.get(i.id, 0),
        )
    
    def _ip_hash(
        self,
        instances: List[ServiceInstance],
        client_ip: Optional[str],
    ) -> ServiceInstance:
        """Consistent hash based on client IP."""
        if not client_ip:
            return self._round_robin(instances)
        
        hash_val = int(hashlib.md5(client_ip.encode()).hexdigest(), 16)
        index = hash_val % len(instances)
        return instances[index]
    
    def mark_connected(self, instance_id: str) -> None:
        """Mark connection to instance."""
        self._connections[instance_id] = self._connections.get(instance_id, 0) + 1
    
    def mark_disconnected(self, instance_id: str) -> None:
        """Mark disconnection from instance."""
        if instance_id in self._connections:
            self._connections[instance_id] = max(0, self._connections[instance_id] - 1)


class ServiceDiscoveryClient:
    """
    High-level service discovery client.
    """
    
    def __init__(
        self,
        registry: ServiceRegistry,
        health_checker: Optional[HealthChecker] = None,
    ):
        self._registry = registry
        self._health_checker = health_checker or HealthChecker()
        self._load_balancers: Dict[str, LoadBalancer] = {}
        self._cache: Dict[str, Tuple[List[ServiceInstance], datetime]] = {}
        self._cache_ttl = timedelta(seconds=30)
    
    async def register(
        self,
        name: str,
        address: str,
        port: int,
        **kwargs: Any,
    ) -> str:
        """Register a service."""
        instance = ServiceInstance(
            id=str(uuid.uuid4()),
            name=name,
            address=address,
            port=port,
            status=ServiceStatus.HEALTHY,
            **kwargs,
        )
        return await self._registry.register(instance)
    
    async def deregister(self, instance_id: str) -> bool:
        """Deregister a service."""
        return await self._registry.deregister(instance_id)
    
    async def discover(
        self,
        name: str,
        healthy_only: bool = True,
        use_cache: bool = True,
    ) -> List[ServiceInstance]:
        """Discover services."""
        # Check cache
        if use_cache and name in self._cache:
            instances, cached_at = self._cache[name]
            if datetime.now() - cached_at < self._cache_ttl:
                if healthy_only:
                    return [i for i in instances if i.is_healthy()]
                return instances
        
        instances = await self._registry.discover(name)
        
        # Update cache
        self._cache[name] = (instances, datetime.now())
        
        if healthy_only:
            return [i for i in instances if i.is_healthy()]
        
        return instances
    
    async def get_one(
        self,
        name: str,
        strategy: LoadBalanceStrategy = LoadBalanceStrategy.ROUND_ROBIN,
    ) -> Optional[ServiceInstance]:
        """Get one healthy instance using load balancing."""
        if name not in self._load_balancers:
            self._load_balancers[name] = LoadBalancer(
                name,
                self._registry,
                strategy,
            )
        
        return await self._load_balancers[name].next()
    
    async def check_health(
        self,
        name: str,
    ) -> Dict[str, HealthCheckResult]:
        """Check health of all instances of a service."""
        instances = await self.discover(name, healthy_only=False)
        return await self._health_checker.check_all(instances)
    
    async def watch(
        self,
        name: str,
        callback: Callable[[List[ServiceInstance]], None],
        interval: int = 10,
    ) -> asyncio.Task:
        """Watch for service changes."""
        async def watch_loop():
            last_instances: Set[str] = set()
            
            while True:
                try:
                    instances = await self.discover(name, use_cache=False)
                    current_ids = {i.id for i in instances}
                    
                    if current_ids != last_instances:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(instances)
                        else:
                            callback(instances)
                        last_instances = current_ids
                    
                    await asyncio.sleep(interval)
                
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Watch error: {e}")
                    await asyncio.sleep(interval)
        
        return asyncio.create_task(watch_loop())


class ServiceRegistration:
    """
    Context manager for service registration.
    """
    
    def __init__(
        self,
        client: ServiceDiscoveryClient,
        name: str,
        address: str,
        port: int,
        heartbeat_interval: int = 30,
        **kwargs: Any,
    ):
        self._client = client
        self._name = name
        self._address = address
        self._port = port
        self._kwargs = kwargs
        self._heartbeat_interval = heartbeat_interval
        self._instance_id: Optional[str] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
    
    async def __aenter__(self) -> str:
        self._instance_id = await self._client.register(
            self._name,
            self._address,
            self._port,
            **self._kwargs,
        )
        
        # Start heartbeat
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        
        return self._instance_id
    
    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[Exception],
        exc_tb: Any,
    ) -> None:
        # Stop heartbeat
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        
        # Deregister
        if self._instance_id:
            await self._client.deregister(self._instance_id)
    
    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeats."""
        while True:
            try:
                await asyncio.sleep(self._heartbeat_interval)
                if self._instance_id:
                    await self._client._registry.heartbeat(self._instance_id)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")


# Decorators
def discoverable(
    name: str,
    address: str = "localhost",
    port: int = 8080,
    **kwargs: Any,
) -> Callable:
    """
    Decorator to make a class discoverable.
    
    Example:
        @discoverable("api-service", port=8080)
        class ApiService:
            ...
    """
    def decorator(cls: type) -> type:
        cls._discovery_name = name
        cls._discovery_address = address
        cls._discovery_port = port
        cls._discovery_metadata = kwargs
        return cls
    
    return decorator


def with_service(
    service_name: str,
    strategy: LoadBalanceStrategy = LoadBalanceStrategy.ROUND_ROBIN,
) -> Callable:
    """
    Decorator to inject a service endpoint.
    
    Example:
        @with_service("user-service")
        async def call_user_api(service: ServiceInstance):
            ...
    """
    _client: Optional[ServiceDiscoveryClient] = None
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            nonlocal _client
            
            if _client is None:
                _client = ServiceDiscoveryClient(InMemoryServiceRegistry())
            
            instance = await _client.get_one(service_name, strategy)
            
            if not instance:
                raise ServiceNotFoundError(
                    f"No healthy instance found for: {service_name}"
                )
            
            return await func(instance, *args, **kwargs)
        
        return wrapper
    
    return decorator


# Factory functions
def create_service_registry(
    ttl_seconds: int = 60,
) -> InMemoryServiceRegistry:
    """Create a service registry."""
    return InMemoryServiceRegistry(ttl_seconds)


def create_discovery_client(
    registry: Optional[ServiceRegistry] = None,
) -> ServiceDiscoveryClient:
    """Create a discovery client."""
    reg = registry or InMemoryServiceRegistry()
    return ServiceDiscoveryClient(reg)


def create_load_balancer(
    service_name: str,
    registry: Optional[ServiceRegistry] = None,
    strategy: LoadBalanceStrategy = LoadBalanceStrategy.ROUND_ROBIN,
) -> LoadBalancer:
    """Create a load balancer."""
    reg = registry or InMemoryServiceRegistry()
    return LoadBalancer(service_name, reg, strategy)


def create_health_checker(
    timeout_seconds: float = 5.0,
) -> HealthChecker:
    """Create a health checker."""
    return HealthChecker(timeout_seconds)


__all__ = [
    # Exceptions
    "DiscoveryError",
    "ServiceNotFoundError",
    "RegistrationError",
    # Enums
    "ServiceStatus",
    "LoadBalanceStrategy",
    # Data classes
    "ServiceInstance",
    "ServiceDefinition",
    "HealthCheckResult",
    "DiscoveryStats",
    # Core classes
    "ServiceRegistry",
    "InMemoryServiceRegistry",
    "HealthChecker",
    "LoadBalancer",
    "ServiceDiscoveryClient",
    "ServiceRegistration",
    # Decorators
    "discoverable",
    "with_service",
    # Factory functions
    "create_service_registry",
    "create_discovery_client",
    "create_load_balancer",
    "create_health_checker",
]
