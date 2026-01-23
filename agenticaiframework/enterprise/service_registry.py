"""
Enterprise Service Registry Module.

Provides service discovery, health checks, load balancing,
service registration, and failover capabilities.

Example:
    # Create service registry
    registry = create_service_registry()
    
    # Register service
    await registry.register(ServiceInstance(
        service_name="user-service",
        host="localhost",
        port=8080,
        health_check_url="/health",
    ))
    
    # Discover service
    instance = await registry.discover("user-service")
    url = f"http://{instance.host}:{instance.port}/api/users"
    
    # Use decorator
    @service_client("user-service")
    async def get_user(client: ServiceClient, user_id: str):
        return await client.get(f"/users/{user_id}")
"""

from __future__ import annotations

import asyncio
import functools
import hashlib
import logging
import random
import threading
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    Tuple,
    TypeVar,
)

T = TypeVar('T')


logger = logging.getLogger(__name__)


class RegistryError(Exception):
    """Base registry error."""
    pass


class ServiceNotFoundError(RegistryError):
    """Service not found."""
    pass


class NoHealthyInstanceError(RegistryError):
    """No healthy instance available."""
    pass


class ServiceStatus(str, Enum):
    """Service instance status."""
    STARTING = "starting"
    UP = "up"
    DOWN = "down"
    OUT_OF_SERVICE = "out_of_service"
    UNKNOWN = "unknown"


class LoadBalanceStrategy(str, Enum):
    """Load balance strategy."""
    ROUND_ROBIN = "round_robin"
    RANDOM = "random"
    LEAST_CONNECTIONS = "least_connections"
    WEIGHTED = "weighted"
    IP_HASH = "ip_hash"


@dataclass
class HealthCheckConfig:
    """Health check configuration."""
    enabled: bool = True
    path: str = "/health"
    interval_seconds: int = 30
    timeout_seconds: int = 5
    healthy_threshold: int = 2
    unhealthy_threshold: int = 3
    protocol: str = "http"


@dataclass
class ServiceMetadata:
    """Service metadata."""
    version: str = "1.0.0"
    environment: str = "development"
    region: str = "default"
    zone: str = "default"
    tags: Dict[str, str] = field(default_factory=dict)
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class ServiceInstance:
    """Service instance."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    host: str = "localhost"
    port: int = 8080
    secure: bool = False
    status: ServiceStatus = ServiceStatus.STARTING
    metadata: ServiceMetadata = field(default_factory=ServiceMetadata)
    health_check: HealthCheckConfig = field(default_factory=HealthCheckConfig)
    weight: int = 100
    registered_at: datetime = field(default_factory=datetime.utcnow)
    last_heartbeat: datetime = field(default_factory=datetime.utcnow)
    last_health_check: Optional[datetime] = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    active_connections: int = 0
    
    @property
    def base_url(self) -> str:
        """Get base URL."""
        protocol = "https" if self.secure else "http"
        return f"{protocol}://{self.host}:{self.port}"
    
    @property
    def health_url(self) -> str:
        """Get health check URL."""
        return f"{self.base_url}{self.health_check.path}"
    
    @property
    def is_healthy(self) -> bool:
        """Check if instance is healthy."""
        return self.status == ServiceStatus.UP


@dataclass
class ServiceDefinition:
    """Service definition."""
    name: str
    instances: List[ServiceInstance] = field(default_factory=list)
    load_balance_strategy: LoadBalanceStrategy = LoadBalanceStrategy.ROUND_ROBIN
    health_check: HealthCheckConfig = field(default_factory=HealthCheckConfig)
    metadata: ServiceMetadata = field(default_factory=ServiceMetadata)
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def healthy_instances(self) -> List[ServiceInstance]:
        """Get healthy instances."""
        return [i for i in self.instances if i.is_healthy]


class HealthChecker(ABC):
    """Abstract health checker."""
    
    @abstractmethod
    async def check(self, instance: ServiceInstance) -> bool:
        """Check instance health."""
        pass


class HttpHealthChecker(HealthChecker):
    """HTTP health checker."""
    
    def __init__(self, timeout: float = 5.0):
        self._timeout = timeout
    
    async def check(self, instance: ServiceInstance) -> bool:
        """Check HTTP health endpoint."""
        try:
            # Simulate HTTP health check
            import aiohttp
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    instance.health_url,
                    timeout=aiohttp.ClientTimeout(total=self._timeout)
                ) as response:
                    return response.status == 200
        except ImportError:
            # Fallback without aiohttp
            await asyncio.sleep(0.1)
            return instance.status == ServiceStatus.UP
        except Exception as e:
            logger.debug(f"Health check failed for {instance.id}: {e}")
            return False


class TcpHealthChecker(HealthChecker):
    """TCP health checker."""
    
    def __init__(self, timeout: float = 5.0):
        self._timeout = timeout
    
    async def check(self, instance: ServiceInstance) -> bool:
        """Check TCP connection."""
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(instance.host, instance.port),
                timeout=self._timeout
            )
            writer.close()
            await writer.wait_closed()
            return True
        except Exception:
            return False


class LoadBalancer(ABC):
    """Abstract load balancer."""
    
    @abstractmethod
    def select(
        self,
        instances: List[ServiceInstance],
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[ServiceInstance]:
        """Select an instance."""
        pass


class RoundRobinBalancer(LoadBalancer):
    """Round-robin load balancer."""
    
    def __init__(self):
        self._counters: Dict[str, int] = {}
        self._lock = threading.Lock()
    
    def select(
        self,
        instances: List[ServiceInstance],
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[ServiceInstance]:
        if not instances:
            return None
        
        # Get service name from first instance
        service_name = instances[0].service_name
        
        with self._lock:
            counter = self._counters.get(service_name, 0)
            instance = instances[counter % len(instances)]
            self._counters[service_name] = counter + 1
            
        return instance


class RandomBalancer(LoadBalancer):
    """Random load balancer."""
    
    def select(
        self,
        instances: List[ServiceInstance],
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[ServiceInstance]:
        if not instances:
            return None
        return random.choice(instances)


class WeightedBalancer(LoadBalancer):
    """Weighted load balancer."""
    
    def select(
        self,
        instances: List[ServiceInstance],
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[ServiceInstance]:
        if not instances:
            return None
        
        total_weight = sum(i.weight for i in instances)
        if total_weight == 0:
            return random.choice(instances)
        
        r = random.randint(1, total_weight)
        cumulative = 0
        
        for instance in instances:
            cumulative += instance.weight
            if r <= cumulative:
                return instance
        
        return instances[-1]


class LeastConnectionsBalancer(LoadBalancer):
    """Least connections load balancer."""
    
    def select(
        self,
        instances: List[ServiceInstance],
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[ServiceInstance]:
        if not instances:
            return None
        
        return min(instances, key=lambda i: i.active_connections)


class IpHashBalancer(LoadBalancer):
    """IP hash load balancer."""
    
    def select(
        self,
        instances: List[ServiceInstance],
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[ServiceInstance]:
        if not instances:
            return None
        
        ip = (context or {}).get('client_ip', 'default')
        hash_val = int(hashlib.md5(ip.encode()).hexdigest(), 16)
        
        return instances[hash_val % len(instances)]


class RegistryStore(ABC):
    """Abstract registry store."""
    
    @abstractmethod
    async def get_service(self, name: str) -> Optional[ServiceDefinition]:
        """Get service definition."""
        pass
    
    @abstractmethod
    async def save_service(self, service: ServiceDefinition) -> None:
        """Save service definition."""
        pass
    
    @abstractmethod
    async def delete_service(self, name: str) -> None:
        """Delete service."""
        pass
    
    @abstractmethod
    async def list_services(self) -> List[str]:
        """List service names."""
        pass
    
    @abstractmethod
    async def get_instance(
        self,
        service_name: str,
        instance_id: str,
    ) -> Optional[ServiceInstance]:
        """Get instance."""
        pass
    
    @abstractmethod
    async def save_instance(self, instance: ServiceInstance) -> None:
        """Save instance."""
        pass
    
    @abstractmethod
    async def delete_instance(
        self,
        service_name: str,
        instance_id: str,
    ) -> None:
        """Delete instance."""
        pass


class InMemoryRegistryStore(RegistryStore):
    """In-memory registry store."""
    
    def __init__(self):
        self._services: Dict[str, ServiceDefinition] = {}
        self._lock = threading.Lock()
    
    async def get_service(self, name: str) -> Optional[ServiceDefinition]:
        with self._lock:
            return self._services.get(name)
    
    async def save_service(self, service: ServiceDefinition) -> None:
        with self._lock:
            self._services[service.name] = service
    
    async def delete_service(self, name: str) -> None:
        with self._lock:
            self._services.pop(name, None)
    
    async def list_services(self) -> List[str]:
        with self._lock:
            return list(self._services.keys())
    
    async def get_instance(
        self,
        service_name: str,
        instance_id: str,
    ) -> Optional[ServiceInstance]:
        with self._lock:
            service = self._services.get(service_name)
            if not service:
                return None
            
            for instance in service.instances:
                if instance.id == instance_id:
                    return instance
            
            return None
    
    async def save_instance(self, instance: ServiceInstance) -> None:
        with self._lock:
            if instance.service_name not in self._services:
                self._services[instance.service_name] = ServiceDefinition(
                    name=instance.service_name
                )
            
            service = self._services[instance.service_name]
            
            # Update or add instance
            for i, existing in enumerate(service.instances):
                if existing.id == instance.id:
                    service.instances[i] = instance
                    return
            
            service.instances.append(instance)
    
    async def delete_instance(
        self,
        service_name: str,
        instance_id: str,
    ) -> None:
        with self._lock:
            service = self._services.get(service_name)
            if service:
                service.instances = [
                    i for i in service.instances
                    if i.id != instance_id
                ]


class ServiceRegistry:
    """
    Service registry for service discovery and load balancing.
    """
    
    def __init__(
        self,
        store: Optional[RegistryStore] = None,
        health_checker: Optional[HealthChecker] = None,
        default_strategy: LoadBalanceStrategy = LoadBalanceStrategy.ROUND_ROBIN,
    ):
        self._store = store or InMemoryRegistryStore()
        self._health_checker = health_checker or HttpHealthChecker()
        self._default_strategy = default_strategy
        
        self._balancers: Dict[LoadBalanceStrategy, LoadBalancer] = {
            LoadBalanceStrategy.ROUND_ROBIN: RoundRobinBalancer(),
            LoadBalanceStrategy.RANDOM: RandomBalancer(),
            LoadBalanceStrategy.WEIGHTED: WeightedBalancer(),
            LoadBalanceStrategy.LEAST_CONNECTIONS: LeastConnectionsBalancer(),
            LoadBalanceStrategy.IP_HASH: IpHashBalancer(),
        }
        
        self._health_check_task: Optional[asyncio.Task] = None
        self._event_handlers: Dict[str, List[Callable]] = {}
    
    @property
    def store(self) -> RegistryStore:
        return self._store
    
    # Registration
    async def register(
        self,
        instance: ServiceInstance,
    ) -> ServiceInstance:
        """Register a service instance."""
        instance.status = ServiceStatus.STARTING
        instance.registered_at = datetime.utcnow()
        instance.last_heartbeat = datetime.utcnow()
        
        await self._store.save_instance(instance)
        
        # Perform initial health check
        if await self._health_checker.check(instance):
            instance.status = ServiceStatus.UP
            await self._store.save_instance(instance)
        
        logger.info(
            f"Registered service instance: {instance.service_name}/{instance.id}"
        )
        
        await self._emit("register", instance)
        
        return instance
    
    async def deregister(
        self,
        service_name: str,
        instance_id: str,
    ) -> None:
        """Deregister a service instance."""
        instance = await self._store.get_instance(service_name, instance_id)
        
        if instance:
            await self._store.delete_instance(service_name, instance_id)
            
            logger.info(
                f"Deregistered service instance: {service_name}/{instance_id}"
            )
            
            await self._emit("deregister", instance)
    
    async def heartbeat(
        self,
        service_name: str,
        instance_id: str,
    ) -> None:
        """Send heartbeat for instance."""
        instance = await self._store.get_instance(service_name, instance_id)
        
        if instance:
            instance.last_heartbeat = datetime.utcnow()
            await self._store.save_instance(instance)
    
    # Discovery
    async def discover(
        self,
        service_name: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ServiceInstance:
        """Discover a healthy service instance."""
        service = await self._store.get_service(service_name)
        
        if not service:
            raise ServiceNotFoundError(f"Service not found: {service_name}")
        
        healthy = service.healthy_instances
        
        if not healthy:
            raise NoHealthyInstanceError(
                f"No healthy instances for: {service_name}"
            )
        
        strategy = service.load_balance_strategy
        balancer = self._balancers.get(strategy, self._balancers[self._default_strategy])
        
        instance = balancer.select(healthy, context)
        
        if not instance:
            raise NoHealthyInstanceError(
                f"Failed to select instance for: {service_name}"
            )
        
        return instance
    
    async def discover_all(
        self,
        service_name: str,
        healthy_only: bool = True,
    ) -> List[ServiceInstance]:
        """Discover all service instances."""
        service = await self._store.get_service(service_name)
        
        if not service:
            return []
        
        if healthy_only:
            return service.healthy_instances
        
        return list(service.instances)
    
    async def get_service(self, name: str) -> Optional[ServiceDefinition]:
        """Get service definition."""
        return await self._store.get_service(name)
    
    async def list_services(self) -> List[str]:
        """List all service names."""
        return await self._store.list_services()
    
    # Health checking
    async def start_health_checks(
        self,
        interval: float = 30.0,
    ) -> None:
        """Start background health checking."""
        if self._health_check_task:
            return
        
        async def health_check_loop():
            while True:
                await asyncio.sleep(interval)
                await self._check_all_instances()
        
        self._health_check_task = asyncio.create_task(health_check_loop())
    
    async def stop_health_checks(self) -> None:
        """Stop background health checking."""
        if self._health_check_task:
            self._health_check_task.cancel()
            self._health_check_task = None
    
    async def _check_all_instances(self) -> None:
        """Check health of all instances."""
        services = await self._store.list_services()
        
        for service_name in services:
            service = await self._store.get_service(service_name)
            if not service:
                continue
            
            for instance in service.instances:
                await self._check_instance_health(instance)
    
    async def _check_instance_health(
        self,
        instance: ServiceInstance,
    ) -> None:
        """Check health of single instance."""
        if not instance.health_check.enabled:
            return
        
        is_healthy = await self._health_checker.check(instance)
        instance.last_health_check = datetime.utcnow()
        
        if is_healthy:
            instance.consecutive_successes += 1
            instance.consecutive_failures = 0
            
            if (
                instance.status != ServiceStatus.UP and
                instance.consecutive_successes >= instance.health_check.healthy_threshold
            ):
                old_status = instance.status
                instance.status = ServiceStatus.UP
                
                logger.info(
                    f"Instance became healthy: {instance.service_name}/{instance.id}"
                )
                await self._emit("healthy", instance, old_status)
        else:
            instance.consecutive_failures += 1
            instance.consecutive_successes = 0
            
            if (
                instance.status == ServiceStatus.UP and
                instance.consecutive_failures >= instance.health_check.unhealthy_threshold
            ):
                old_status = instance.status
                instance.status = ServiceStatus.DOWN
                
                logger.warning(
                    f"Instance became unhealthy: {instance.service_name}/{instance.id}"
                )
                await self._emit("unhealthy", instance, old_status)
        
        await self._store.save_instance(instance)
    
    # Events
    def on(
        self,
        event: str,
        handler: Callable,
    ) -> None:
        """Register event handler."""
        if event not in self._event_handlers:
            self._event_handlers[event] = []
        self._event_handlers[event].append(handler)
    
    async def _emit(self, event: str, *args) -> None:
        """Emit event."""
        handlers = self._event_handlers.get(event, [])
        
        for handler in handlers:
            try:
                result = handler(*args)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Event handler error: {e}")


# Global registry
_global_registry: Optional[ServiceRegistry] = None


class ServiceClient:
    """
    Service client for making requests to discovered services.
    """
    
    def __init__(
        self,
        service_name: str,
        registry: Optional[ServiceRegistry] = None,
    ):
        self._service_name = service_name
        self._registry = registry or get_global_registry()
    
    async def get_instance(
        self,
        context: Optional[Dict[str, Any]] = None,
    ) -> ServiceInstance:
        """Get a service instance."""
        return await self._registry.discover(self._service_name, context)
    
    async def get_url(
        self,
        path: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Get URL for path."""
        instance = await self.get_instance(context)
        return f"{instance.base_url}{path}"


# Decorators
def service_client(
    service_name: str,
    inject_as: str = "client",
) -> Callable:
    """
    Decorator to inject service client.
    
    Example:
        @service_client("user-service")
        async def get_users(client: ServiceClient):
            url = await client.get_url("/api/users")
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            client = ServiceClient(service_name)
            kwargs[inject_as] = client
            return await func(*args, **kwargs)
        
        return wrapper
    
    return decorator


def with_service_discovery(
    service_name: str,
    inject_as: str = "instance",
) -> Callable:
    """
    Decorator to inject discovered service instance.
    
    Example:
        @with_service_discovery("user-service")
        async def call_user_service(instance: ServiceInstance):
            url = f"{instance.base_url}/api/users"
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            registry = get_global_registry()
            instance = await registry.discover(service_name)
            kwargs[inject_as] = instance
            return await func(*args, **kwargs)
        
        return wrapper
    
    return decorator


# Factory functions
def create_service_registry(
    store: Optional[RegistryStore] = None,
    health_checker: Optional[HealthChecker] = None,
    default_strategy: LoadBalanceStrategy = LoadBalanceStrategy.ROUND_ROBIN,
) -> ServiceRegistry:
    """Create service registry."""
    return ServiceRegistry(store, health_checker, default_strategy)


def create_service_instance(
    service_name: str,
    host: str = "localhost",
    port: int = 8080,
    secure: bool = False,
    weight: int = 100,
    version: str = "1.0.0",
    tags: Optional[Dict[str, str]] = None,
) -> ServiceInstance:
    """Create service instance."""
    return ServiceInstance(
        service_name=service_name,
        host=host,
        port=port,
        secure=secure,
        weight=weight,
        metadata=ServiceMetadata(version=version, tags=tags or {}),
    )


def create_health_check_config(
    path: str = "/health",
    interval_seconds: int = 30,
    timeout_seconds: int = 5,
    healthy_threshold: int = 2,
    unhealthy_threshold: int = 3,
) -> HealthCheckConfig:
    """Create health check configuration."""
    return HealthCheckConfig(
        path=path,
        interval_seconds=interval_seconds,
        timeout_seconds=timeout_seconds,
        healthy_threshold=healthy_threshold,
        unhealthy_threshold=unhealthy_threshold,
    )


def create_http_health_checker(timeout: float = 5.0) -> HttpHealthChecker:
    """Create HTTP health checker."""
    return HttpHealthChecker(timeout)


def create_tcp_health_checker(timeout: float = 5.0) -> TcpHealthChecker:
    """Create TCP health checker."""
    return TcpHealthChecker(timeout)


def create_in_memory_store() -> InMemoryRegistryStore:
    """Create in-memory registry store."""
    return InMemoryRegistryStore()


def get_global_registry() -> ServiceRegistry:
    """Get global service registry."""
    global _global_registry
    if _global_registry is None:
        _global_registry = create_service_registry()
    return _global_registry


__all__ = [
    # Exceptions
    "RegistryError",
    "ServiceNotFoundError",
    "NoHealthyInstanceError",
    # Enums
    "ServiceStatus",
    "LoadBalanceStrategy",
    # Data classes
    "HealthCheckConfig",
    "ServiceMetadata",
    "ServiceInstance",
    "ServiceDefinition",
    # Health checkers
    "HealthChecker",
    "HttpHealthChecker",
    "TcpHealthChecker",
    # Load balancers
    "LoadBalancer",
    "RoundRobinBalancer",
    "RandomBalancer",
    "WeightedBalancer",
    "LeastConnectionsBalancer",
    "IpHashBalancer",
    # Store
    "RegistryStore",
    "InMemoryRegistryStore",
    # Registry
    "ServiceRegistry",
    # Client
    "ServiceClient",
    # Decorators
    "service_client",
    "with_service_discovery",
    # Factory functions
    "create_service_registry",
    "create_service_instance",
    "create_health_check_config",
    "create_http_health_checker",
    "create_tcp_health_checker",
    "create_in_memory_store",
    "get_global_registry",
]
