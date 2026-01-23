"""
Enterprise Connection Pool Module.

Provides connection pooling for LLM clients and other resources,
with support for load balancing and health checking.

Example:
    # LLM client pool
    pool = LLMClientPool(
        clients=[
            OpenAIClient(api_key="key1"),
            OpenAIClient(api_key="key2"),
        ],
        max_concurrent=10,
    )
    
    async with pool.acquire() as client:
        response = await client.complete(prompt)
    
    # Generic resource pool
    pool = ResourcePool(
        factory=create_connection,
        max_size=20,
        min_size=5,
    )
"""

from __future__ import annotations

import asyncio
import time
import random
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    TypeVar,
    Union,
)
from contextlib import asynccontextmanager
from enum import Enum
import logging

logger = logging.getLogger(__name__)

T = TypeVar("T")


class PoolExhausted(Exception):
    """Raised when pool has no available resources."""
    pass


class ResourceError(Exception):
    """Raised when resource operation fails."""
    pass


class PoolState(str, Enum):
    """Pool states."""
    CREATED = "created"
    RUNNING = "running"
    DRAINING = "draining"
    CLOSED = "closed"


class LoadBalanceStrategy(str, Enum):
    """Load balancing strategies."""
    ROUND_ROBIN = "round_robin"
    RANDOM = "random"
    LEAST_CONNECTIONS = "least_connections"
    WEIGHTED = "weighted"
    LEAST_LATENCY = "least_latency"


@dataclass
class PoolStats:
    """Statistics for a resource pool."""
    total_acquired: int = 0
    total_released: int = 0
    total_created: int = 0
    total_destroyed: int = 0
    current_size: int = 0
    in_use: int = 0
    available: int = 0
    wait_time_total: float = 0.0
    wait_count: int = 0
    
    @property
    def average_wait_time(self) -> float:
        """Calculate average wait time."""
        return self.wait_time_total / self.wait_count if self.wait_count > 0 else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_acquired": self.total_acquired,
            "total_released": self.total_released,
            "total_created": self.total_created,
            "total_destroyed": self.total_destroyed,
            "current_size": self.current_size,
            "in_use": self.in_use,
            "available": self.available,
            "average_wait_time": self.average_wait_time,
        }


@dataclass
class PooledResource(Generic[T]):
    """Wrapper for pooled resources with metadata."""
    resource: T
    created_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    use_count: int = 0
    is_healthy: bool = True
    latency_sum: float = 0.0
    request_count: int = 0
    
    @property
    def age(self) -> float:
        """Get resource age in seconds."""
        return time.time() - self.created_at
    
    @property
    def idle_time(self) -> float:
        """Get idle time in seconds."""
        return time.time() - self.last_used
    
    @property
    def average_latency(self) -> float:
        """Get average request latency."""
        return self.latency_sum / self.request_count if self.request_count > 0 else 0.0
    
    def touch(self) -> None:
        """Update last used time."""
        self.last_used = time.time()
        self.use_count += 1
    
    def record_latency(self, latency: float) -> None:
        """Record request latency."""
        self.latency_sum += latency
        self.request_count += 1


class ResourceFactory(ABC, Generic[T]):
    """Abstract factory for creating pooled resources."""
    
    @abstractmethod
    async def create(self) -> T:
        """Create a new resource."""
        pass
    
    @abstractmethod
    async def destroy(self, resource: T) -> None:
        """Destroy a resource."""
        pass
    
    async def validate(self, resource: T) -> bool:
        """Validate resource is still healthy."""
        return True
    
    async def reset(self, resource: T) -> T:
        """Reset resource state before returning to pool."""
        return resource


class CallableFactory(ResourceFactory[T]):
    """Factory using callable functions."""
    
    def __init__(
        self,
        create_func: Callable[[], Union[T, Any]],
        destroy_func: Optional[Callable[[T], None]] = None,
        validate_func: Optional[Callable[[T], bool]] = None,
        reset_func: Optional[Callable[[T], T]] = None,
    ):
        self.create_func = create_func
        self.destroy_func = destroy_func
        self.validate_func = validate_func
        self.reset_func = reset_func
    
    async def create(self) -> T:
        """Create using factory function."""
        if asyncio.iscoroutinefunction(self.create_func):
            return await self.create_func()
        return self.create_func()
    
    async def destroy(self, resource: T) -> None:
        """Destroy resource."""
        if self.destroy_func:
            if asyncio.iscoroutinefunction(self.destroy_func):
                await self.destroy_func(resource)
            else:
                self.destroy_func(resource)
    
    async def validate(self, resource: T) -> bool:
        """Validate resource."""
        if self.validate_func:
            if asyncio.iscoroutinefunction(self.validate_func):
                return await self.validate_func(resource)
            return self.validate_func(resource)
        return True
    
    async def reset(self, resource: T) -> T:
        """Reset resource."""
        if self.reset_func:
            if asyncio.iscoroutinefunction(self.reset_func):
                return await self.reset_func(resource)
            return self.reset_func(resource)
        return resource


class ResourcePool(Generic[T]):
    """
    Generic resource pool with connection management.
    """
    
    def __init__(
        self,
        factory: ResourceFactory[T],
        max_size: int = 10,
        min_size: int = 1,
        max_idle_time: float = 300.0,
        max_lifetime: float = 3600.0,
        acquire_timeout: float = 30.0,
        validate_on_acquire: bool = True,
        validate_on_release: bool = False,
    ):
        """
        Initialize resource pool.
        
        Args:
            factory: Factory for creating resources
            max_size: Maximum pool size
            min_size: Minimum pool size (pre-created)
            max_idle_time: Maximum idle time before eviction
            max_lifetime: Maximum resource lifetime
            acquire_timeout: Timeout for acquiring resource
            validate_on_acquire: Validate before giving to caller
            validate_on_release: Validate when returning to pool
        """
        self.factory = factory
        self.max_size = max_size
        self.min_size = min_size
        self.max_idle_time = max_idle_time
        self.max_lifetime = max_lifetime
        self.acquire_timeout = acquire_timeout
        self.validate_on_acquire = validate_on_acquire
        self.validate_on_release = validate_on_release
        
        self._pool: List[PooledResource[T]] = []
        self._in_use: Set[PooledResource[T]] = set()
        self._state = PoolState.CREATED
        self._stats = PoolStats()
        self._lock = asyncio.Lock()
        self._available = asyncio.Condition()
        self._maintenance_task: Optional[asyncio.Task] = None
    
    @property
    def state(self) -> PoolState:
        """Get pool state."""
        return self._state
    
    @property
    def stats(self) -> PoolStats:
        """Get pool statistics."""
        self._stats.current_size = len(self._pool) + len(self._in_use)
        self._stats.in_use = len(self._in_use)
        self._stats.available = len(self._pool)
        return self._stats
    
    async def start(self) -> None:
        """Start the pool and pre-create minimum resources."""
        async with self._lock:
            if self._state != PoolState.CREATED:
                return
            
            self._state = PoolState.RUNNING
            
            # Pre-create minimum resources
            for _ in range(self.min_size):
                resource = await self._create_resource()
                self._pool.append(resource)
            
            # Start maintenance task
            self._maintenance_task = asyncio.create_task(self._maintenance_loop())
            
            logger.info(f"Pool started with {len(self._pool)} resources")
    
    async def close(self) -> None:
        """Close the pool and destroy all resources."""
        async with self._lock:
            if self._state == PoolState.CLOSED:
                return
            
            self._state = PoolState.DRAINING
            
            # Cancel maintenance
            if self._maintenance_task:
                self._maintenance_task.cancel()
                self._maintenance_task = None
            
            # Wait for in-use resources with timeout
            wait_start = time.time()
            while self._in_use and time.time() - wait_start < 30:
                await asyncio.sleep(0.1)
            
            # Destroy all resources
            for pooled in self._pool + list(self._in_use):
                await self._destroy_resource(pooled)
            
            self._pool.clear()
            self._in_use.clear()
            self._state = PoolState.CLOSED
            
            logger.info("Pool closed")
    
    async def _create_resource(self) -> PooledResource[T]:
        """Create a new pooled resource."""
        resource = await self.factory.create()
        pooled = PooledResource(resource=resource)
        self._stats.total_created += 1
        return pooled
    
    async def _destroy_resource(self, pooled: PooledResource[T]) -> None:
        """Destroy a pooled resource."""
        try:
            await self.factory.destroy(pooled.resource)
        except Exception as e:
            logger.error(f"Error destroying resource: {e}")
        self._stats.total_destroyed += 1
    
    async def _maintenance_loop(self) -> None:
        """Background maintenance loop."""
        while self._state == PoolState.RUNNING:
            try:
                await asyncio.sleep(60)  # Run every minute
                await self._cleanup_idle()
                await self._ensure_min_size()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Maintenance error: {e}")
    
    async def _cleanup_idle(self) -> None:
        """Remove idle and expired resources."""
        async with self._lock:
            to_remove = []
            
            for pooled in self._pool:
                if pooled.idle_time > self.max_idle_time:
                    to_remove.append(pooled)
                elif pooled.age > self.max_lifetime:
                    to_remove.append(pooled)
            
            for pooled in to_remove:
                if len(self._pool) > self.min_size:
                    self._pool.remove(pooled)
                    await self._destroy_resource(pooled)
    
    async def _ensure_min_size(self) -> None:
        """Ensure pool has minimum resources."""
        async with self._lock:
            while len(self._pool) < self.min_size:
                try:
                    resource = await self._create_resource()
                    self._pool.append(resource)
                except Exception as e:
                    logger.error(f"Error creating resource: {e}")
                    break
    
    async def acquire(self) -> T:
        """
        Acquire a resource from the pool.
        
        Returns:
            Resource from pool
            
        Raises:
            PoolExhausted: If no resources available and at max size
        """
        wait_start = time.time()
        
        async with self._available:
            while True:
                if self._state != PoolState.RUNNING:
                    raise PoolExhausted("Pool is not running")
                
                # Try to get from pool
                while self._pool:
                    pooled = self._pool.pop(0)
                    
                    # Validate if required
                    if self.validate_on_acquire:
                        if not await self.factory.validate(pooled.resource):
                            await self._destroy_resource(pooled)
                            continue
                    
                    # Check lifetime
                    if pooled.age > self.max_lifetime:
                        await self._destroy_resource(pooled)
                        continue
                    
                    pooled.touch()
                    self._in_use.add(pooled)
                    self._stats.total_acquired += 1
                    self._stats.wait_count += 1
                    self._stats.wait_time_total += time.time() - wait_start
                    return pooled.resource
                
                # Check if we can create a new one
                current_size = len(self._pool) + len(self._in_use)
                if current_size < self.max_size:
                    pooled = await self._create_resource()
                    pooled.touch()
                    self._in_use.add(pooled)
                    self._stats.total_acquired += 1
                    return pooled.resource
                
                # Wait for a resource to become available
                elapsed = time.time() - wait_start
                remaining = self.acquire_timeout - elapsed
                
                if remaining <= 0:
                    raise PoolExhausted(
                        f"Timeout waiting for resource after {self.acquire_timeout}s"
                    )
                
                try:
                    await asyncio.wait_for(
                        self._available.wait(),
                        timeout=remaining,
                    )
                except asyncio.TimeoutError:
                    raise PoolExhausted(
                        f"Timeout waiting for resource after {self.acquire_timeout}s"
                    )
    
    async def release(self, resource: T) -> None:
        """
        Release a resource back to the pool.
        
        Args:
            resource: Resource to release
        """
        async with self._available:
            # Find the pooled resource
            pooled = None
            for p in self._in_use:
                if p.resource is resource:
                    pooled = p
                    break
            
            if pooled is None:
                logger.warning("Released resource not found in pool")
                return
            
            self._in_use.remove(pooled)
            
            # Validate if required
            if self.validate_on_release:
                if not await self.factory.validate(pooled.resource):
                    await self._destroy_resource(pooled)
                    self._available.notify_all()
                    return
            
            # Reset and return to pool
            try:
                pooled.resource = await self.factory.reset(pooled.resource)
            except Exception as e:
                logger.error(f"Error resetting resource: {e}")
                await self._destroy_resource(pooled)
                self._available.notify_all()
                return
            
            pooled.is_healthy = True
            self._pool.append(pooled)
            self._stats.total_released += 1
            self._available.notify()
    
    @asynccontextmanager
    async def connection(self):
        """
        Context manager for acquiring/releasing resources.
        
        Example:
            async with pool.connection() as resource:
                await resource.do_something()
        """
        resource = await self.acquire()
        try:
            yield resource
        finally:
            await self.release(resource)
    
    async def __aenter__(self) -> 'ResourcePool[T]':
        """Enter async context."""
        await self.start()
        return self
    
    async def __aexit__(self, *args) -> None:
        """Exit async context."""
        await self.close()


class LoadBalancedPool(Generic[T]):
    """
    Pool with multiple resources and load balancing.
    """
    
    def __init__(
        self,
        resources: List[T],
        strategy: LoadBalanceStrategy = LoadBalanceStrategy.ROUND_ROBIN,
        weights: Optional[List[float]] = None,
        max_concurrent_per_resource: int = 10,
    ):
        """
        Initialize load balanced pool.
        
        Args:
            resources: List of resources to balance between
            strategy: Load balancing strategy
            weights: Weights for weighted balancing
            max_concurrent_per_resource: Max concurrent uses per resource
        """
        self.resources = [
            PooledResource(resource=r) for r in resources
        ]
        self.strategy = strategy
        self.weights = weights or [1.0] * len(resources)
        self.max_concurrent = max_concurrent_per_resource
        
        self._current_index = 0
        self._concurrent_counts: Dict[int, int] = {
            i: 0 for i in range(len(resources))
        }
        self._lock = asyncio.Lock()
        self._stats = PoolStats()
    
    @property
    def stats(self) -> PoolStats:
        """Get pool statistics."""
        return self._stats
    
    def _get_next_round_robin(self) -> int:
        """Get next resource index using round robin."""
        for _ in range(len(self.resources)):
            index = self._current_index
            self._current_index = (self._current_index + 1) % len(self.resources)
            
            if self._concurrent_counts[index] < self.max_concurrent:
                if self.resources[index].is_healthy:
                    return index
        
        raise PoolExhausted("All resources at capacity or unhealthy")
    
    def _get_next_random(self) -> int:
        """Get next resource index randomly."""
        available = [
            i for i in range(len(self.resources))
            if self._concurrent_counts[i] < self.max_concurrent
            and self.resources[i].is_healthy
        ]
        
        if not available:
            raise PoolExhausted("All resources at capacity or unhealthy")
        
        return random.choice(available)
    
    def _get_next_least_connections(self) -> int:
        """Get resource with least connections."""
        available = [
            (i, self._concurrent_counts[i])
            for i in range(len(self.resources))
            if self._concurrent_counts[i] < self.max_concurrent
            and self.resources[i].is_healthy
        ]
        
        if not available:
            raise PoolExhausted("All resources at capacity or unhealthy")
        
        return min(available, key=lambda x: x[1])[0]
    
    def _get_next_weighted(self) -> int:
        """Get resource using weighted random selection."""
        available = [
            (i, self.weights[i])
            for i in range(len(self.resources))
            if self._concurrent_counts[i] < self.max_concurrent
            and self.resources[i].is_healthy
        ]
        
        if not available:
            raise PoolExhausted("All resources at capacity or unhealthy")
        
        total = sum(w for _, w in available)
        r = random.uniform(0, total)
        
        cumulative = 0
        for i, w in available:
            cumulative += w
            if r <= cumulative:
                return i
        
        return available[-1][0]
    
    def _get_next_least_latency(self) -> int:
        """Get resource with lowest average latency."""
        available = [
            (i, self.resources[i].average_latency)
            for i in range(len(self.resources))
            if self._concurrent_counts[i] < self.max_concurrent
            and self.resources[i].is_healthy
        ]
        
        if not available:
            raise PoolExhausted("All resources at capacity or unhealthy")
        
        return min(available, key=lambda x: x[1])[0]
    
    def _get_next_index(self) -> int:
        """Get next resource index based on strategy."""
        if self.strategy == LoadBalanceStrategy.ROUND_ROBIN:
            return self._get_next_round_robin()
        elif self.strategy == LoadBalanceStrategy.RANDOM:
            return self._get_next_random()
        elif self.strategy == LoadBalanceStrategy.LEAST_CONNECTIONS:
            return self._get_next_least_connections()
        elif self.strategy == LoadBalanceStrategy.WEIGHTED:
            return self._get_next_weighted()
        elif self.strategy == LoadBalanceStrategy.LEAST_LATENCY:
            return self._get_next_least_latency()
        else:
            return self._get_next_round_robin()
    
    async def acquire(self) -> Tuple[T, int]:
        """
        Acquire a resource from the pool.
        
        Returns:
            Tuple of (resource, index) for tracking
        """
        async with self._lock:
            index = self._get_next_index()
            self._concurrent_counts[index] += 1
            self.resources[index].touch()
            self._stats.total_acquired += 1
            return self.resources[index].resource, index
    
    async def release(self, index: int, latency: Optional[float] = None) -> None:
        """
        Release a resource back to the pool.
        
        Args:
            index: Resource index from acquire
            latency: Optional latency measurement
        """
        async with self._lock:
            self._concurrent_counts[index] -= 1
            if latency is not None:
                self.resources[index].record_latency(latency)
            self._stats.total_released += 1
    
    async def mark_unhealthy(self, index: int) -> None:
        """Mark a resource as unhealthy."""
        async with self._lock:
            self.resources[index].is_healthy = False
    
    async def mark_healthy(self, index: int) -> None:
        """Mark a resource as healthy."""
        async with self._lock:
            self.resources[index].is_healthy = True
    
    @asynccontextmanager
    async def connection(self):
        """Context manager for acquiring/releasing."""
        start = time.time()
        resource, index = await self.acquire()
        try:
            yield resource
        finally:
            latency = time.time() - start
            await self.release(index, latency)


@dataclass
class LLMClientConfig:
    """Configuration for LLM client."""
    name: str
    client: Any
    weight: float = 1.0
    max_concurrent: int = 10
    timeout: float = 30.0
    retry_on_fail: bool = True


class LLMClientPool:
    """
    Specialized pool for LLM clients with load balancing.
    """
    
    def __init__(
        self,
        clients: List[LLMClientConfig],
        strategy: LoadBalanceStrategy = LoadBalanceStrategy.LEAST_LATENCY,
        fallback_on_error: bool = True,
    ):
        """
        Initialize LLM client pool.
        
        Args:
            clients: List of client configurations
            strategy: Load balancing strategy
            fallback_on_error: Try other clients on error
        """
        self.clients = clients
        self.strategy = strategy
        self.fallback_on_error = fallback_on_error
        
        self._pool = LoadBalancedPool(
            resources=[c.client for c in clients],
            strategy=strategy,
            weights=[c.weight for c in clients],
            max_concurrent_per_resource=max(c.max_concurrent for c in clients),
        )
        self._failed_attempts: Dict[int, int] = {
            i: 0 for i in range(len(clients))
        }
    
    @asynccontextmanager
    async def acquire(self):
        """Acquire an LLM client."""
        async with self._pool.connection() as client:
            yield client
    
    async def complete(
        self,
        prompt: str,
        **kwargs: Any,
    ) -> Any:
        """
        Complete a prompt using a pooled client.
        
        Args:
            prompt: Prompt to complete
            **kwargs: Additional arguments for completion
            
        Returns:
            Completion result
        """
        tried_indices: Set[int] = set()
        last_error: Optional[Exception] = None
        
        while len(tried_indices) < len(self.clients):
            start = time.time()
            client, index = await self._pool.acquire()
            tried_indices.add(index)
            
            try:
                config = self.clients[index]
                
                # Call completion
                if hasattr(client, "complete"):
                    if asyncio.iscoroutinefunction(client.complete):
                        result = await asyncio.wait_for(
                            client.complete(prompt, **kwargs),
                            timeout=config.timeout,
                        )
                    else:
                        result = client.complete(prompt, **kwargs)
                elif hasattr(client, "chat"):
                    if asyncio.iscoroutinefunction(client.chat):
                        result = await asyncio.wait_for(
                            client.chat(prompt, **kwargs),
                            timeout=config.timeout,
                        )
                    else:
                        result = client.chat(prompt, **kwargs)
                else:
                    raise AttributeError(
                        f"Client has no 'complete' or 'chat' method"
                    )
                
                latency = time.time() - start
                await self._pool.release(index, latency)
                self._failed_attempts[index] = 0
                return result
                
            except Exception as e:
                latency = time.time() - start
                await self._pool.release(index, latency)
                last_error = e
                self._failed_attempts[index] += 1
                
                # Mark unhealthy after multiple failures
                if self._failed_attempts[index] >= 3:
                    await self._pool.mark_unhealthy(index)
                
                if not self.fallback_on_error:
                    raise
                
                logger.warning(
                    f"Client {self.clients[index].name} failed: {e}. "
                    f"Trying fallback..."
                )
        
        # All clients failed
        raise last_error or ResourceError("All LLM clients failed")


def create_pool(
    factory: Callable[[], T],
    destroy: Optional[Callable[[T], None]] = None,
    validate: Optional[Callable[[T], bool]] = None,
    **kwargs: Any,
) -> ResourcePool[T]:
    """
    Create a resource pool with callable factory.
    
    Args:
        factory: Function to create resources
        destroy: Optional function to destroy resources
        validate: Optional function to validate resources
        **kwargs: Additional pool arguments
        
    Returns:
        Configured resource pool
    """
    return ResourcePool(
        factory=CallableFactory(
            create_func=factory,
            destroy_func=destroy,
            validate_func=validate,
        ),
        **kwargs,
    )


__all__ = [
    # Exceptions
    "PoolExhausted",
    "ResourceError",
    # Enums
    "PoolState",
    "LoadBalanceStrategy",
    # Data classes
    "PoolStats",
    "PooledResource",
    "LLMClientConfig",
    # Factory classes
    "ResourceFactory",
    "CallableFactory",
    # Pool classes
    "ResourcePool",
    "LoadBalancedPool",
    "LLMClientPool",
    # Factory function
    "create_pool",
]
