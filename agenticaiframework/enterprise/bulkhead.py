"""
Enterprise Bulkhead Module.

Provides bulkhead pattern implementation for isolating failures
and preventing cascading failures across services.

Example:
    # Thread pool bulkhead
    bulkhead = ThreadPoolBulkhead(
        name="external_api",
        max_concurrent=10,
        max_wait=5.0,
    )
    
    async with bulkhead.acquire():
        await call_external_api()
    
    # Semaphore bulkhead
    @bulkhead(max_concurrent=5)
    async def limited_operation():
        ...
"""

from __future__ import annotations

import asyncio
import threading
import time
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
)
from contextlib import asynccontextmanager, contextmanager
from functools import wraps
from enum import Enum
import logging

logger = logging.getLogger(__name__)

T = TypeVar("T")


class BulkheadFullError(Exception):
    """Bulkhead is at capacity."""
    
    def __init__(
        self,
        message: str = "Bulkhead full",
        bulkhead_name: str = "",
        current: int = 0,
        max_concurrent: int = 0,
    ):
        super().__init__(message)
        self.bulkhead_name = bulkhead_name
        self.current = current
        self.max_concurrent = max_concurrent


class BulkheadTimeoutError(BulkheadFullError):
    """Timed out waiting for bulkhead capacity."""
    pass


class BulkheadType(str, Enum):
    """Types of bulkhead isolation."""
    SEMAPHORE = "semaphore"
    THREAD_POOL = "thread_pool"
    PROCESS_POOL = "process_pool"


@dataclass
class BulkheadStats:
    """Statistics for a bulkhead."""
    name: str
    total_acquired: int = 0
    total_rejected: int = 0
    total_timeout: int = 0
    current_active: int = 0
    max_concurrent: int = 0
    max_wait_queue: int = 0
    current_waiting: int = 0
    total_wait_time: float = 0.0
    
    @property
    def rejection_rate(self) -> float:
        """Calculate rejection rate."""
        total = self.total_acquired + self.total_rejected
        return (self.total_rejected / total * 100) if total > 0 else 0.0
    
    @property
    def average_wait_time(self) -> float:
        """Calculate average wait time."""
        return self.total_wait_time / self.total_acquired if self.total_acquired > 0 else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "total_acquired": self.total_acquired,
            "total_rejected": self.total_rejected,
            "total_timeout": self.total_timeout,
            "current_active": self.current_active,
            "max_concurrent": self.max_concurrent,
            "current_waiting": self.current_waiting,
            "rejection_rate": self.rejection_rate,
            "average_wait_time": self.average_wait_time,
        }


class Bulkhead(ABC):
    """Abstract bulkhead interface."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Get bulkhead name."""
        pass
    
    @property
    @abstractmethod
    def stats(self) -> BulkheadStats:
        """Get bulkhead statistics."""
        pass
    
    @abstractmethod
    async def acquire(self, timeout: Optional[float] = None) -> bool:
        """Acquire a slot in the bulkhead."""
        pass
    
    @abstractmethod
    async def release(self) -> None:
        """Release a slot in the bulkhead."""
        pass
    
    @abstractmethod
    def try_acquire(self) -> bool:
        """Try to acquire without waiting."""
        pass


class SemaphoreBulkhead(Bulkhead):
    """
    Semaphore-based bulkhead for limiting concurrent operations.
    """
    
    def __init__(
        self,
        name: str,
        max_concurrent: int = 10,
        max_wait_queue: int = 100,
    ):
        """
        Initialize semaphore bulkhead.
        
        Args:
            name: Bulkhead name for identification
            max_concurrent: Maximum concurrent operations
            max_wait_queue: Maximum waiting queue size
        """
        self._name = name
        self._max_concurrent = max_concurrent
        self._max_wait_queue = max_wait_queue
        
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._stats = BulkheadStats(
            name=name,
            max_concurrent=max_concurrent,
            max_wait_queue=max_wait_queue,
        )
        self._waiting = 0
        self._lock = asyncio.Lock()
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def stats(self) -> BulkheadStats:
        return self._stats
    
    @property
    def available(self) -> int:
        """Get available slots."""
        return self._semaphore._value
    
    async def acquire(self, timeout: Optional[float] = None) -> bool:
        """
        Acquire a slot.
        
        Args:
            timeout: Maximum wait time
            
        Returns:
            True if acquired
            
        Raises:
            BulkheadFullError: If queue is full
            BulkheadTimeoutError: If timeout exceeded
        """
        async with self._lock:
            if self._waiting >= self._max_wait_queue:
                self._stats.total_rejected += 1
                raise BulkheadFullError(
                    f"Bulkhead {self._name} wait queue full",
                    bulkhead_name=self._name,
                    current=self._stats.current_active,
                    max_concurrent=self._max_concurrent,
                )
            self._waiting += 1
            self._stats.current_waiting = self._waiting
        
        start = time.time()
        
        try:
            if timeout:
                try:
                    await asyncio.wait_for(
                        self._semaphore.acquire(),
                        timeout=timeout,
                    )
                except asyncio.TimeoutError:
                    self._stats.total_timeout += 1
                    raise BulkheadTimeoutError(
                        f"Timeout waiting for bulkhead {self._name}",
                        bulkhead_name=self._name,
                    )
            else:
                await self._semaphore.acquire()
            
            wait_time = time.time() - start
            self._stats.total_wait_time += wait_time
            self._stats.total_acquired += 1
            self._stats.current_active += 1
            
            return True
            
        finally:
            async with self._lock:
                self._waiting -= 1
                self._stats.current_waiting = self._waiting
    
    async def release(self) -> None:
        """Release a slot."""
        self._semaphore.release()
        self._stats.current_active -= 1
    
    def try_acquire(self) -> bool:
        """Try to acquire without waiting."""
        if self._semaphore._value > 0:
            self._semaphore._value -= 1
            self._stats.total_acquired += 1
            self._stats.current_active += 1
            return True
        
        self._stats.total_rejected += 1
        return False
    
    @asynccontextmanager
    async def __call__(self, timeout: Optional[float] = None):
        """
        Context manager for acquiring/releasing.
        
        Example:
            async with bulkhead():
                await operation()
        """
        await self.acquire(timeout)
        try:
            yield
        finally:
            await self.release()


class ThreadPoolBulkhead(Bulkhead):
    """
    Thread pool-based bulkhead for CPU-bound isolation.
    """
    
    def __init__(
        self,
        name: str,
        max_concurrent: int = 10,
        max_wait_queue: int = 100,
    ):
        """
        Initialize thread pool bulkhead.
        
        Args:
            name: Bulkhead name
            max_concurrent: Maximum concurrent threads
            max_wait_queue: Maximum waiting queue size
        """
        from concurrent.futures import ThreadPoolExecutor
        
        self._name = name
        self._max_concurrent = max_concurrent
        self._max_wait_queue = max_wait_queue
        
        self._executor = ThreadPoolExecutor(max_workers=max_concurrent)
        self._semaphore = threading.Semaphore(max_concurrent)
        self._stats = BulkheadStats(
            name=name,
            max_concurrent=max_concurrent,
            max_wait_queue=max_wait_queue,
        )
        self._waiting = 0
        self._lock = threading.Lock()
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def stats(self) -> BulkheadStats:
        return self._stats
    
    async def acquire(self, timeout: Optional[float] = None) -> bool:
        """Acquire a slot."""
        with self._lock:
            if self._waiting >= self._max_wait_queue:
                self._stats.total_rejected += 1
                raise BulkheadFullError(
                    f"Bulkhead {self._name} wait queue full",
                    bulkhead_name=self._name,
                )
            self._waiting += 1
        
        start = time.time()
        
        try:
            acquired = self._semaphore.acquire(
                blocking=True,
                timeout=timeout,
            )
            
            if not acquired:
                self._stats.total_timeout += 1
                raise BulkheadTimeoutError(
                    f"Timeout waiting for bulkhead {self._name}",
                    bulkhead_name=self._name,
                )
            
            self._stats.total_wait_time += time.time() - start
            self._stats.total_acquired += 1
            self._stats.current_active += 1
            
            return True
            
        finally:
            with self._lock:
                self._waiting -= 1
    
    async def release(self) -> None:
        """Release a slot."""
        self._semaphore.release()
        self._stats.current_active -= 1
    
    def try_acquire(self) -> bool:
        """Try to acquire without waiting."""
        if self._semaphore.acquire(blocking=False):
            self._stats.total_acquired += 1
            self._stats.current_active += 1
            return True
        
        self._stats.total_rejected += 1
        return False
    
    async def execute(
        self,
        func: Callable[..., T],
        *args: Any,
        timeout: Optional[float] = None,
        **kwargs: Any,
    ) -> T:
        """
        Execute function in thread pool with bulkhead.
        
        Args:
            func: Function to execute
            *args: Positional arguments
            timeout: Timeout for execution
            **kwargs: Keyword arguments
            
        Returns:
            Function result
        """
        await self.acquire(timeout)
        
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self._executor,
                lambda: func(*args, **kwargs),
            )
            return result
        finally:
            await self.release()
    
    def shutdown(self) -> None:
        """Shutdown the thread pool."""
        self._executor.shutdown(wait=True)


class BulkheadRegistry:
    """
    Registry for managing multiple bulkheads.
    """
    
    _instance: Optional['BulkheadRegistry'] = None
    
    def __init__(self):
        self._bulkheads: Dict[str, Bulkhead] = {}
        self._lock = asyncio.Lock()
    
    @classmethod
    def instance(cls) -> 'BulkheadRegistry':
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    async def get_or_create(
        self,
        name: str,
        bulkhead_type: BulkheadType = BulkheadType.SEMAPHORE,
        max_concurrent: int = 10,
        max_wait_queue: int = 100,
    ) -> Bulkhead:
        """
        Get or create a bulkhead.
        
        Args:
            name: Bulkhead name
            bulkhead_type: Type of bulkhead
            max_concurrent: Maximum concurrent operations
            max_wait_queue: Maximum waiting queue size
            
        Returns:
            Bulkhead instance
        """
        async with self._lock:
            if name in self._bulkheads:
                return self._bulkheads[name]
            
            if bulkhead_type == BulkheadType.SEMAPHORE:
                bulkhead = SemaphoreBulkhead(name, max_concurrent, max_wait_queue)
            elif bulkhead_type == BulkheadType.THREAD_POOL:
                bulkhead = ThreadPoolBulkhead(name, max_concurrent, max_wait_queue)
            else:
                bulkhead = SemaphoreBulkhead(name, max_concurrent, max_wait_queue)
            
            self._bulkheads[name] = bulkhead
            return bulkhead
    
    def get(self, name: str) -> Optional[Bulkhead]:
        """Get bulkhead by name."""
        return self._bulkheads.get(name)
    
    def get_all_stats(self) -> Dict[str, BulkheadStats]:
        """Get statistics for all bulkheads."""
        return {name: bh.stats for name, bh in self._bulkheads.items()}
    
    async def remove(self, name: str) -> bool:
        """Remove a bulkhead."""
        async with self._lock:
            if name in self._bulkheads:
                del self._bulkheads[name]
                return True
            return False


def bulkhead(
    name: Optional[str] = None,
    max_concurrent: int = 10,
    max_wait_queue: int = 100,
    timeout: Optional[float] = None,
) -> Callable:
    """
    Decorator for bulkhead isolation.
    
    Example:
        @bulkhead(name="external_api", max_concurrent=5)
        async def call_api():
            ...
    """
    def decorator(func: Callable) -> Callable:
        bulkhead_name = name or func.__name__
        _bulkhead: Optional[SemaphoreBulkhead] = None
        
        def get_bulkhead() -> SemaphoreBulkhead:
            nonlocal _bulkhead
            if _bulkhead is None:
                _bulkhead = SemaphoreBulkhead(
                    bulkhead_name,
                    max_concurrent,
                    max_wait_queue,
                )
            return _bulkhead
        
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            bh = get_bulkhead()
            async with bh(timeout):
                return await func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            bh = get_bulkhead()
            
            # For sync functions, use threading semaphore
            if not bh._semaphore.acquire(blocking=True, timeout=timeout):
                raise BulkheadTimeoutError(
                    f"Timeout waiting for bulkhead {bulkhead_name}"
                )
            
            try:
                return func(*args, **kwargs)
            finally:
                bh._semaphore.release()
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


class BulkheadGroup:
    """
    Group of bulkheads for complex isolation patterns.
    """
    
    def __init__(self, name: str):
        """
        Initialize bulkhead group.
        
        Args:
            name: Group name
        """
        self.name = name
        self._bulkheads: Dict[str, Bulkhead] = {}
    
    def add(self, category: str, bulkhead: Bulkhead) -> 'BulkheadGroup':
        """Add a bulkhead to the group."""
        self._bulkheads[category] = bulkhead
        return self
    
    def get(self, category: str) -> Optional[Bulkhead]:
        """Get bulkhead by category."""
        return self._bulkheads.get(category)
    
    @asynccontextmanager
    async def acquire_all(self, timeout: Optional[float] = None):
        """
        Acquire all bulkheads in the group.
        
        Example:
            async with group.acquire_all():
                await complex_operation()
        """
        acquired: List[Bulkhead] = []
        
        try:
            for bh in self._bulkheads.values():
                await bh.acquire(timeout)
                acquired.append(bh)
            yield
        finally:
            for bh in reversed(acquired):
                await bh.release()
    
    @asynccontextmanager
    async def acquire_category(self, category: str, timeout: Optional[float] = None):
        """
        Acquire specific category bulkhead.
        
        Example:
            async with group.acquire_category("database"):
                await db.query()
        """
        bh = self._bulkheads.get(category)
        if not bh:
            yield
            return
        
        await bh.acquire(timeout)
        try:
            yield
        finally:
            await bh.release()
    
    def get_stats(self) -> Dict[str, BulkheadStats]:
        """Get statistics for all bulkheads in group."""
        return {cat: bh.stats for cat, bh in self._bulkheads.items()}


class AdaptiveBulkhead(Bulkhead):
    """
    Bulkhead that adapts capacity based on success rate.
    """
    
    def __init__(
        self,
        name: str,
        initial_concurrent: int = 10,
        min_concurrent: int = 1,
        max_concurrent: int = 50,
        success_threshold: float = 0.95,
        failure_threshold: float = 0.50,
    ):
        """
        Initialize adaptive bulkhead.
        
        Args:
            name: Bulkhead name
            initial_concurrent: Starting concurrency
            min_concurrent: Minimum concurrency
            max_concurrent: Maximum concurrency
            success_threshold: Success rate to increase
            failure_threshold: Success rate to decrease
        """
        self._name = name
        self._current_limit = initial_concurrent
        self._min = min_concurrent
        self._max = max_concurrent
        self._success_threshold = success_threshold
        self._failure_threshold = failure_threshold
        
        self._semaphore = asyncio.Semaphore(initial_concurrent)
        self._stats = BulkheadStats(
            name=name,
            max_concurrent=initial_concurrent,
        )
        self._recent_results: List[bool] = []
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def stats(self) -> BulkheadStats:
        return self._stats
    
    @property
    def current_limit(self) -> int:
        """Get current concurrency limit."""
        return self._current_limit
    
    async def acquire(self, timeout: Optional[float] = None) -> bool:
        """Acquire a slot."""
        if timeout:
            try:
                await asyncio.wait_for(
                    self._semaphore.acquire(),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                self._stats.total_timeout += 1
                raise BulkheadTimeoutError(f"Timeout for {self._name}")
        else:
            await self._semaphore.acquire()
        
        self._stats.total_acquired += 1
        self._stats.current_active += 1
        return True
    
    async def release(self, success: bool = True) -> None:
        """
        Release a slot and record result.
        
        Args:
            success: Whether the operation was successful
        """
        self._semaphore.release()
        self._stats.current_active -= 1
        
        # Record result
        self._recent_results.append(success)
        if len(self._recent_results) > 100:
            self._recent_results.pop(0)
        
        # Adapt
        await self._adapt()
    
    def try_acquire(self) -> bool:
        """Try to acquire without waiting."""
        if self._semaphore._value > 0:
            self._semaphore._value -= 1
            self._stats.total_acquired += 1
            self._stats.current_active += 1
            return True
        return False
    
    async def _adapt(self) -> None:
        """Adapt concurrency based on results."""
        if len(self._recent_results) < 10:
            return
        
        success_rate = sum(self._recent_results) / len(self._recent_results)
        
        if success_rate >= self._success_threshold:
            # Increase capacity
            if self._current_limit < self._max:
                self._current_limit += 1
                self._semaphore._value += 1
                self._stats.max_concurrent = self._current_limit
                logger.info(f"Bulkhead {self._name} increased to {self._current_limit}")
        
        elif success_rate <= self._failure_threshold:
            # Decrease capacity
            if self._current_limit > self._min:
                self._current_limit -= 1
                # Don't decrease semaphore value below 0
                if self._semaphore._value > 0:
                    self._semaphore._value -= 1
                self._stats.max_concurrent = self._current_limit
                logger.info(f"Bulkhead {self._name} decreased to {self._current_limit}")
    
    @asynccontextmanager
    async def __call__(self, timeout: Optional[float] = None):
        """Context manager with success tracking."""
        await self.acquire(timeout)
        success = True
        try:
            yield
        except Exception:
            success = False
            raise
        finally:
            await self.release(success)


__all__ = [
    # Exceptions
    "BulkheadFullError",
    "BulkheadTimeoutError",
    # Enums
    "BulkheadType",
    # Data classes
    "BulkheadStats",
    # Bulkhead classes
    "Bulkhead",
    "SemaphoreBulkhead",
    "ThreadPoolBulkhead",
    "AdaptiveBulkhead",
    # Registry
    "BulkheadRegistry",
    # Group
    "BulkheadGroup",
    # Decorator
    "bulkhead",
]
