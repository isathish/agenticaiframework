"""
Enterprise Resource Manager Module.

Resource optimization, pool management, garbage collection,
memory management, and resource lifecycle management.

Example:
    # Create resource manager
    rm = create_resource_manager()
    
    # Register resource pool
    await rm.create_pool(
        name="db_connections",
        resource_type="connection",
        min_size=5,
        max_size=50,
    )
    
    # Acquire resource
    async with rm.acquire("db_connections") as conn:
        # Use connection
        pass
    
    # Get pool stats
    stats = await rm.get_pool_stats("db_connections")
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
import weakref
from abc import ABC, abstractmethod
from collections import defaultdict
from contextlib import asynccontextmanager
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
    TypeVar,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ResourceError(Exception):
    """Resource error."""
    pass


class PoolExhaustedError(ResourceError):
    """Pool exhausted error."""
    pass


class ResourceNotFoundError(ResourceError):
    """Resource not found error."""
    pass


class ResourceState(str, Enum):
    """Resource state."""
    AVAILABLE = "available"
    IN_USE = "in_use"
    UNHEALTHY = "unhealthy"
    EXPIRED = "expired"
    DISPOSED = "disposed"


class PoolStrategy(str, Enum):
    """Pool strategy."""
    FIFO = "fifo"
    LIFO = "lifo"
    ROUND_ROBIN = "round_robin"
    LEAST_USED = "least_used"
    RANDOM = "random"


class ScalingPolicy(str, Enum):
    """Scaling policy."""
    STATIC = "static"
    DYNAMIC = "dynamic"
    AGGRESSIVE = "aggressive"
    CONSERVATIVE = "conservative"


@dataclass
class ResourceMetadata:
    """Resource metadata."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_used_at: Optional[datetime] = None
    use_count: int = 0
    state: ResourceState = ResourceState.AVAILABLE
    ttl_seconds: Optional[int] = None
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class PoolConfig:
    """Pool configuration."""
    name: str = ""
    resource_type: str = ""
    
    # Size
    min_size: int = 1
    max_size: int = 10
    initial_size: int = 1
    
    # Timeouts
    acquire_timeout_seconds: float = 30.0
    idle_timeout_seconds: float = 300.0
    max_lifetime_seconds: float = 3600.0
    
    # Health
    health_check_interval_seconds: float = 60.0
    max_unhealthy_count: int = 3
    
    # Strategy
    strategy: PoolStrategy = PoolStrategy.FIFO
    scaling_policy: ScalingPolicy = ScalingPolicy.DYNAMIC
    
    # Callbacks
    validate_on_acquire: bool = True
    validate_on_release: bool = False


@dataclass
class PoolStats:
    """Pool statistics."""
    name: str = ""
    resource_type: str = ""
    
    # Counts
    total_resources: int = 0
    available_resources: int = 0
    in_use_resources: int = 0
    unhealthy_resources: int = 0
    
    # Metrics
    total_acquisitions: int = 0
    total_releases: int = 0
    total_timeouts: int = 0
    total_failures: int = 0
    
    # Timing
    avg_wait_time_ms: float = 0.0
    avg_usage_time_ms: float = 0.0
    max_wait_time_ms: float = 0.0
    
    # Utilization
    utilization_percent: float = 0.0
    peak_utilization_percent: float = 0.0


@dataclass
class ResourceUsage:
    """Resource usage record."""
    resource_id: str
    acquired_at: datetime
    released_at: Optional[datetime] = None
    duration_ms: float = 0.0
    error: Optional[str] = None


@dataclass
class GCResult:
    """Garbage collection result."""
    collected_count: int = 0
    freed_bytes: int = 0
    duration_ms: float = 0.0
    errors: List[str] = field(default_factory=list)


# Resource factory
class ResourceFactory(ABC, Generic[T]):
    """Resource factory."""
    
    @abstractmethod
    async def create(self) -> T:
        """Create resource."""
        pass
    
    @abstractmethod
    async def destroy(self, resource: T) -> None:
        """Destroy resource."""
        pass
    
    @abstractmethod
    async def validate(self, resource: T) -> bool:
        """Validate resource."""
        pass
    
    async def reset(self, resource: T) -> T:
        """Reset resource for reuse."""
        return resource


class GenericResourceFactory(ResourceFactory[Any]):
    """Generic resource factory."""
    
    def __init__(
        self,
        creator: Callable[[], Any],
        destroyer: Optional[Callable[[Any], None]] = None,
        validator: Optional[Callable[[Any], bool]] = None,
    ):
        self._creator = creator
        self._destroyer = destroyer
        self._validator = validator
    
    async def create(self) -> Any:
        if asyncio.iscoroutinefunction(self._creator):
            return await self._creator()
        return self._creator()
    
    async def destroy(self, resource: Any) -> None:
        if self._destroyer:
            if asyncio.iscoroutinefunction(self._destroyer):
                await self._destroyer(resource)
            else:
                self._destroyer(resource)
    
    async def validate(self, resource: Any) -> bool:
        if self._validator:
            if asyncio.iscoroutinefunction(self._validator):
                return await self._validator(resource)
            return self._validator(resource)
        return True


# Resource wrapper
@dataclass
class ManagedResource(Generic[T]):
    """Managed resource wrapper."""
    resource: T
    metadata: ResourceMetadata = field(default_factory=ResourceMetadata)
    pool_name: str = ""
    
    def mark_used(self) -> None:
        """Mark resource as used."""
        self.metadata.last_used_at = datetime.utcnow()
        self.metadata.use_count += 1
        self.metadata.state = ResourceState.IN_USE
    
    def mark_available(self) -> None:
        """Mark resource as available."""
        self.metadata.state = ResourceState.AVAILABLE
    
    def mark_unhealthy(self) -> None:
        """Mark resource as unhealthy."""
        self.metadata.state = ResourceState.UNHEALTHY
    
    def is_expired(self) -> bool:
        """Check if resource is expired."""
        if self.metadata.ttl_seconds:
            age = (datetime.utcnow() - self.metadata.created_at).total_seconds()
            return age > self.metadata.ttl_seconds
        return False
    
    def is_idle_timeout(self, timeout_seconds: float) -> bool:
        """Check if idle timeout exceeded."""
        if self.metadata.last_used_at:
            idle = (datetime.utcnow() - self.metadata.last_used_at).total_seconds()
            return idle > timeout_seconds
        return False


# Resource pool
class ResourcePool(Generic[T]):
    """Resource pool."""
    
    def __init__(
        self,
        config: PoolConfig,
        factory: ResourceFactory[T],
    ):
        self._config = config
        self._factory = factory
        
        self._resources: Dict[str, ManagedResource[T]] = {}
        self._available: asyncio.Queue[str] = asyncio.Queue()
        self._in_use: Set[str] = set()
        
        self._lock = asyncio.Lock()
        self._initialized = False
        
        # Stats
        self._stats = PoolStats(
            name=config.name,
            resource_type=config.resource_type,
        )
        self._wait_times: List[float] = []
        self._usage_times: List[float] = []
        
        # Background tasks
        self._health_check_task: Optional[asyncio.Task] = None
    
    async def initialize(self) -> None:
        """Initialize pool."""
        if self._initialized:
            return
        
        async with self._lock:
            for _ in range(self._config.initial_size):
                await self._create_resource()
            
            self._initialized = True
            
            # Start health check
            self._health_check_task = asyncio.create_task(self._health_check_loop())
        
        logger.info(f"Pool initialized: {self._config.name}")
    
    async def acquire(self, timeout: Optional[float] = None) -> ManagedResource[T]:
        """Acquire resource from pool."""
        timeout = timeout or self._config.acquire_timeout_seconds
        start_time = time.monotonic()
        
        try:
            # Try to get available resource
            while True:
                try:
                    resource_id = await asyncio.wait_for(
                        self._available.get(),
                        timeout=timeout,
                    )
                    
                    managed = self._resources.get(resource_id)
                    
                    if not managed:
                        continue
                    
                    # Validate resource
                    if self._config.validate_on_acquire:
                        if not await self._factory.validate(managed.resource):
                            await self._dispose_resource(resource_id)
                            continue
                    
                    # Check expiry
                    if managed.is_expired():
                        await self._dispose_resource(resource_id)
                        continue
                    
                    # Mark as in use
                    managed.mark_used()
                    self._in_use.add(resource_id)
                    
                    wait_time = (time.monotonic() - start_time) * 1000
                    self._record_wait_time(wait_time)
                    
                    self._stats.total_acquisitions += 1
                    
                    return managed
                    
                except asyncio.QueueEmpty:
                    # Try to scale up
                    async with self._lock:
                        if len(self._resources) < self._config.max_size:
                            await self._create_resource()
                            continue
                    
                    raise PoolExhaustedError(f"Pool exhausted: {self._config.name}")
                    
        except asyncio.TimeoutError:
            self._stats.total_timeouts += 1
            raise PoolExhaustedError(
                f"Acquire timeout after {timeout}s: {self._config.name}"
            )
    
    async def release(self, resource: ManagedResource[T]) -> None:
        """Release resource back to pool."""
        resource_id = resource.metadata.id
        
        if resource_id not in self._in_use:
            return
        
        self._in_use.discard(resource_id)
        
        # Validate on release
        if self._config.validate_on_release:
            if not await self._factory.validate(resource.resource):
                await self._dispose_resource(resource_id)
                return
        
        # Reset resource
        try:
            resource.resource = await self._factory.reset(resource.resource)
        except Exception as e:
            logger.error(f"Reset failed: {e}")
            await self._dispose_resource(resource_id)
            return
        
        # Mark available
        resource.mark_available()
        await self._available.put(resource_id)
        
        self._stats.total_releases += 1
    
    async def dispose(self, resource: ManagedResource[T]) -> None:
        """Dispose resource (remove from pool)."""
        await self._dispose_resource(resource.metadata.id)
    
    async def shutdown(self) -> None:
        """Shutdown pool."""
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        
        async with self._lock:
            for resource_id in list(self._resources.keys()):
                await self._dispose_resource(resource_id)
        
        logger.info(f"Pool shutdown: {self._config.name}")
    
    def get_stats(self) -> PoolStats:
        """Get pool statistics."""
        stats = PoolStats(
            name=self._config.name,
            resource_type=self._config.resource_type,
            total_resources=len(self._resources),
            available_resources=self._available.qsize(),
            in_use_resources=len(self._in_use),
            unhealthy_resources=len([
                r for r in self._resources.values()
                if r.metadata.state == ResourceState.UNHEALTHY
            ]),
            total_acquisitions=self._stats.total_acquisitions,
            total_releases=self._stats.total_releases,
            total_timeouts=self._stats.total_timeouts,
            total_failures=self._stats.total_failures,
        )
        
        if self._wait_times:
            stats.avg_wait_time_ms = sum(self._wait_times) / len(self._wait_times)
            stats.max_wait_time_ms = max(self._wait_times)
        
        if self._usage_times:
            stats.avg_usage_time_ms = sum(self._usage_times) / len(self._usage_times)
        
        if len(self._resources) > 0:
            stats.utilization_percent = (len(self._in_use) / len(self._resources)) * 100
        
        return stats
    
    async def _create_resource(self) -> ManagedResource[T]:
        """Create new resource."""
        try:
            resource = await self._factory.create()
            
            managed = ManagedResource(
                resource=resource,
                metadata=ResourceMetadata(
                    ttl_seconds=int(self._config.max_lifetime_seconds)
                    if self._config.max_lifetime_seconds
                    else None,
                ),
                pool_name=self._config.name,
            )
            
            self._resources[managed.metadata.id] = managed
            await self._available.put(managed.metadata.id)
            
            return managed
            
        except Exception as e:
            self._stats.total_failures += 1
            logger.error(f"Resource creation failed: {e}")
            raise
    
    async def _dispose_resource(self, resource_id: str) -> None:
        """Dispose resource."""
        managed = self._resources.pop(resource_id, None)
        
        if managed:
            managed.metadata.state = ResourceState.DISPOSED
            
            try:
                await self._factory.destroy(managed.resource)
            except Exception as e:
                logger.error(f"Resource destruction failed: {e}")
            
            self._in_use.discard(resource_id)
    
    async def _health_check_loop(self) -> None:
        """Health check loop."""
        while True:
            try:
                await asyncio.sleep(self._config.health_check_interval_seconds)
                await self._run_health_check()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")
    
    async def _run_health_check(self) -> None:
        """Run health check."""
        async with self._lock:
            # Check idle resources
            for resource_id, managed in list(self._resources.items()):
                if managed.metadata.state != ResourceState.AVAILABLE:
                    continue
                
                # Check idle timeout
                if managed.is_idle_timeout(self._config.idle_timeout_seconds):
                    # Don't go below min size
                    if len(self._resources) > self._config.min_size:
                        await self._dispose_resource(resource_id)
                        continue
                
                # Validate
                if not await self._factory.validate(managed.resource):
                    managed.mark_unhealthy()
            
            # Scale up if needed
            while len(self._resources) < self._config.min_size:
                await self._create_resource()
    
    def _record_wait_time(self, ms: float) -> None:
        """Record wait time."""
        self._wait_times.append(ms)
        if len(self._wait_times) > 1000:
            self._wait_times = self._wait_times[-1000:]


# Garbage collector
class GarbageCollector:
    """Garbage collector."""
    
    def __init__(
        self,
        collect_interval_seconds: float = 60.0,
        weak_refs_enabled: bool = True,
    ):
        self._interval = collect_interval_seconds
        self._weak_refs = weak_refs_enabled
        
        self._tracked: Dict[str, weakref.ref] = {}
        self._finalizers: Dict[str, Callable] = {}
        self._collected_count = 0
        
        self._task: Optional[asyncio.Task] = None
    
    def track(
        self,
        obj: Any,
        finalizer: Optional[Callable[[Any], None]] = None,
    ) -> str:
        """Track object for garbage collection."""
        obj_id = str(uuid.uuid4())
        
        if self._weak_refs:
            self._tracked[obj_id] = weakref.ref(obj)
        
        if finalizer:
            self._finalizers[obj_id] = finalizer
        
        return obj_id
    
    def untrack(self, obj_id: str) -> None:
        """Untrack object."""
        self._tracked.pop(obj_id, None)
        self._finalizers.pop(obj_id, None)
    
    async def collect(self) -> GCResult:
        """Run garbage collection."""
        start_time = time.monotonic()
        result = GCResult()
        
        dead_refs = []
        
        for obj_id, ref in list(self._tracked.items()):
            obj = ref()
            
            if obj is None:
                dead_refs.append(obj_id)
        
        for obj_id in dead_refs:
            self._tracked.pop(obj_id, None)
            
            finalizer = self._finalizers.pop(obj_id, None)
            if finalizer:
                try:
                    if asyncio.iscoroutinefunction(finalizer):
                        await finalizer(None)
                    else:
                        finalizer(None)
                except Exception as e:
                    result.errors.append(str(e))
            
            result.collected_count += 1
        
        result.duration_ms = (time.monotonic() - start_time) * 1000
        self._collected_count += result.collected_count
        
        if result.collected_count > 0:
            logger.info(f"GC collected {result.collected_count} objects")
        
        return result
    
    async def start(self) -> None:
        """Start automatic collection."""
        if self._task:
            return
        
        self._task = asyncio.create_task(self._collect_loop())
    
    async def stop(self) -> None:
        """Stop automatic collection."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
    
    async def _collect_loop(self) -> None:
        """Collection loop."""
        while True:
            try:
                await asyncio.sleep(self._interval)
                await self.collect()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"GC error: {e}")


# Resource manager
class ResourceManager:
    """Resource manager."""
    
    def __init__(
        self,
        gc_enabled: bool = True,
        gc_interval_seconds: float = 60.0,
    ):
        self._pools: Dict[str, ResourcePool] = {}
        self._factories: Dict[str, ResourceFactory] = {}
        
        self._gc_enabled = gc_enabled
        self._gc = GarbageCollector(gc_interval_seconds) if gc_enabled else None
        
        self._usage_history: List[ResourceUsage] = []
        self._listeners: List[Callable] = []
    
    async def create_pool(
        self,
        name: str,
        resource_type: str,
        factory: Optional[ResourceFactory] = None,
        creator: Optional[Callable] = None,
        destroyer: Optional[Callable] = None,
        validator: Optional[Callable] = None,
        min_size: int = 1,
        max_size: int = 10,
        **kwargs,
    ) -> ResourcePool:
        """Create resource pool."""
        if name in self._pools:
            raise ResourceError(f"Pool already exists: {name}")
        
        # Create factory
        if factory:
            resource_factory = factory
        elif creator:
            resource_factory = GenericResourceFactory(creator, destroyer, validator)
        else:
            raise ResourceError("Factory or creator required")
        
        self._factories[name] = resource_factory
        
        # Create config
        config = PoolConfig(
            name=name,
            resource_type=resource_type,
            min_size=min_size,
            max_size=max_size,
            **kwargs,
        )
        
        # Create pool
        pool = ResourcePool(config, resource_factory)
        await pool.initialize()
        
        self._pools[name] = pool
        
        logger.info(f"Pool created: {name}")
        
        return pool
    
    async def get_pool(self, name: str) -> Optional[ResourcePool]:
        """Get pool by name."""
        return self._pools.get(name)
    
    async def list_pools(self) -> List[str]:
        """List pool names."""
        return list(self._pools.keys())
    
    @asynccontextmanager
    async def acquire(
        self,
        pool_name: str,
        timeout: Optional[float] = None,
    ):
        """Acquire resource from pool."""
        pool = self._pools.get(pool_name)
        
        if not pool:
            raise ResourceNotFoundError(f"Pool not found: {pool_name}")
        
        managed = await pool.acquire(timeout)
        usage = ResourceUsage(
            resource_id=managed.metadata.id,
            acquired_at=datetime.utcnow(),
        )
        
        try:
            yield managed.resource
        except Exception as e:
            usage.error = str(e)
            raise
        finally:
            usage.released_at = datetime.utcnow()
            usage.duration_ms = (
                (usage.released_at - usage.acquired_at).total_seconds() * 1000
            )
            
            self._usage_history.append(usage)
            if len(self._usage_history) > 10000:
                self._usage_history = self._usage_history[-10000:]
            
            await pool.release(managed)
    
    async def get_pool_stats(self, pool_name: str) -> Optional[PoolStats]:
        """Get pool statistics."""
        pool = self._pools.get(pool_name)
        return pool.get_stats() if pool else None
    
    async def get_all_stats(self) -> Dict[str, PoolStats]:
        """Get all pool statistics."""
        return {name: pool.get_stats() for name, pool in self._pools.items()}
    
    async def resize_pool(
        self,
        pool_name: str,
        min_size: Optional[int] = None,
        max_size: Optional[int] = None,
    ) -> bool:
        """Resize pool."""
        pool = self._pools.get(pool_name)
        
        if not pool:
            return False
        
        if min_size is not None:
            pool._config.min_size = min_size
        
        if max_size is not None:
            pool._config.max_size = max_size
        
        logger.info(f"Pool resized: {pool_name}")
        
        return True
    
    async def drain_pool(self, pool_name: str) -> int:
        """Drain pool (remove all available resources)."""
        pool = self._pools.get(pool_name)
        
        if not pool:
            return 0
        
        drained = 0
        
        async with pool._lock:
            while not pool._available.empty():
                try:
                    resource_id = pool._available.get_nowait()
                    await pool._dispose_resource(resource_id)
                    drained += 1
                except asyncio.QueueEmpty:
                    break
        
        logger.info(f"Pool drained: {pool_name} ({drained} resources)")
        
        return drained
    
    async def shutdown_pool(self, pool_name: str) -> bool:
        """Shutdown pool."""
        pool = self._pools.pop(pool_name, None)
        
        if pool:
            await pool.shutdown()
            self._factories.pop(pool_name, None)
            return True
        
        return False
    
    async def collect_garbage(self) -> Optional[GCResult]:
        """Run garbage collection."""
        if self._gc:
            return await self._gc.collect()
        return None
    
    async def start(self) -> None:
        """Start resource manager."""
        if self._gc:
            await self._gc.start()
    
    async def shutdown(self) -> None:
        """Shutdown resource manager."""
        if self._gc:
            await self._gc.stop()
        
        for pool_name in list(self._pools.keys()):
            await self.shutdown_pool(pool_name)
        
        logger.info("Resource manager shutdown complete")
    
    def get_usage_history(
        self,
        pool_name: Optional[str] = None,
        limit: int = 100,
    ) -> List[ResourceUsage]:
        """Get usage history."""
        history = self._usage_history
        
        if pool_name:
            pool = self._pools.get(pool_name)
            if pool:
                resource_ids = set(pool._resources.keys())
                history = [u for u in history if u.resource_id in resource_ids]
        
        return history[-limit:]
    
    def add_listener(self, listener: Callable) -> None:
        """Add event listener."""
        self._listeners.append(listener)


# Factory functions
def create_resource_manager(
    gc_enabled: bool = True,
    gc_interval_seconds: float = 60.0,
) -> ResourceManager:
    """Create resource manager."""
    return ResourceManager(
        gc_enabled=gc_enabled,
        gc_interval_seconds=gc_interval_seconds,
    )


def create_pool_config(
    name: str,
    resource_type: str,
    **kwargs,
) -> PoolConfig:
    """Create pool configuration."""
    return PoolConfig(name=name, resource_type=resource_type, **kwargs)


def create_resource_factory(
    creator: Callable[[], Any],
    destroyer: Optional[Callable[[Any], None]] = None,
    validator: Optional[Callable[[Any], bool]] = None,
) -> ResourceFactory:
    """Create resource factory."""
    return GenericResourceFactory(creator, destroyer, validator)


__all__ = [
    # Exceptions
    "ResourceError",
    "PoolExhaustedError",
    "ResourceNotFoundError",
    # Enums
    "ResourceState",
    "PoolStrategy",
    "ScalingPolicy",
    # Data classes
    "ResourceMetadata",
    "PoolConfig",
    "PoolStats",
    "ResourceUsage",
    "GCResult",
    # Factory
    "ResourceFactory",
    "GenericResourceFactory",
    # Resource
    "ManagedResource",
    # Pool
    "ResourcePool",
    # Garbage collector
    "GarbageCollector",
    # Manager
    "ResourceManager",
    # Factory functions
    "create_resource_manager",
    "create_pool_config",
    "create_resource_factory",
]
