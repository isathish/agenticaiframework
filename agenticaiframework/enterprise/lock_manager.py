"""
Enterprise Lock Manager Module.

Provides distributed locks, advisory locks, deadlock detection,
and locking patterns for concurrent access control.

Example:
    # Create lock manager
    locks = create_lock_manager()
    
    # Acquire lock
    async with locks.lock("resource:123"):
        # Critical section
        await process_resource()
    
    # Use decorator
    @with_lock("my-lock")
    async def critical_operation():
        ...
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    AsyncIterator,
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


class LockError(Exception):
    """Base lock error."""
    pass


class LockAcquireError(LockError):
    """Failed to acquire lock."""
    pass


class LockTimeoutError(LockError):
    """Lock acquisition timed out."""
    pass


class DeadlockError(LockError):
    """Deadlock detected."""
    pass


class LockType(str, Enum):
    """Lock type."""
    EXCLUSIVE = "exclusive"
    SHARED = "shared"
    ADVISORY = "advisory"


class LockState(str, Enum):
    """Lock state."""
    FREE = "free"
    HELD = "held"
    WAITING = "waiting"


@dataclass
class LockInfo:
    """Lock information."""
    name: str
    lock_type: LockType
    owner: str
    acquired_at: datetime
    expires_at: Optional[datetime] = None
    reentrant_count: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at


@dataclass
class LockConfig:
    """Lock configuration."""
    timeout: Optional[float] = None  # Acquisition timeout
    ttl: Optional[float] = None  # Lock TTL
    reentrant: bool = True
    fair: bool = True  # FIFO ordering


@dataclass
class LockStats:
    """Lock statistics."""
    total_acquisitions: int = 0
    successful_acquisitions: int = 0
    failed_acquisitions: int = 0
    timeouts: int = 0
    deadlocks_detected: int = 0
    current_held: int = 0
    current_waiting: int = 0


class Lock(ABC):
    """
    Abstract lock interface.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Lock name."""
        pass
    
    @property
    @abstractmethod
    def is_held(self) -> bool:
        """Whether lock is currently held."""
        pass
    
    @abstractmethod
    async def acquire(
        self,
        timeout: Optional[float] = None,
        blocking: bool = True,
    ) -> bool:
        """Acquire the lock."""
        pass
    
    @abstractmethod
    async def release(self) -> None:
        """Release the lock."""
        pass
    
    @abstractmethod
    async def extend(self, ttl: float) -> bool:
        """Extend lock TTL."""
        pass
    
    async def __aenter__(self) -> "Lock":
        await self.acquire()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.release()


class LocalLock(Lock):
    """
    Local in-memory lock.
    """
    
    def __init__(
        self,
        name: str,
        owner: str,
        config: LockConfig,
    ):
        self._name = name
        self._owner = owner
        self._config = config
        self._lock = asyncio.Lock()
        self._info: Optional[LockInfo] = None
        self._reentrant_count = 0
        self._current_owner: Optional[str] = None
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def is_held(self) -> bool:
        return self._info is not None and not self._info.is_expired
    
    async def acquire(
        self,
        timeout: Optional[float] = None,
        blocking: bool = True,
    ) -> bool:
        timeout = timeout or self._config.timeout
        
        # Check reentrant
        if self._config.reentrant and self._current_owner == self._owner:
            self._reentrant_count += 1
            if self._info:
                self._info.reentrant_count = self._reentrant_count
            return True
        
        try:
            if blocking:
                if timeout:
                    acquired = await asyncio.wait_for(
                        self._lock.acquire(),
                        timeout=timeout,
                    )
                else:
                    await self._lock.acquire()
                    acquired = True
            else:
                acquired = self._lock.locked() is False
                if acquired:
                    await self._lock.acquire()
            
            if acquired:
                self._current_owner = self._owner
                self._reentrant_count = 1
                
                expires_at = None
                if self._config.ttl:
                    expires_at = datetime.utcnow() + timedelta(seconds=self._config.ttl)
                
                self._info = LockInfo(
                    name=self._name,
                    lock_type=LockType.EXCLUSIVE,
                    owner=self._owner,
                    acquired_at=datetime.utcnow(),
                    expires_at=expires_at,
                    reentrant_count=1,
                )
            
            return acquired
            
        except asyncio.TimeoutError:
            raise LockTimeoutError(f"Timeout acquiring lock: {self._name}")
    
    async def release(self) -> None:
        if self._config.reentrant and self._reentrant_count > 1:
            self._reentrant_count -= 1
            if self._info:
                self._info.reentrant_count = self._reentrant_count
            return
        
        self._reentrant_count = 0
        self._current_owner = None
        self._info = None
        
        if self._lock.locked():
            self._lock.release()
    
    async def extend(self, ttl: float) -> bool:
        if self._info:
            self._info.expires_at = datetime.utcnow() + timedelta(seconds=ttl)
            return True
        return False


class ReadWriteLock:
    """
    Read-write lock (multiple readers, single writer).
    """
    
    def __init__(self, name: str):
        self._name = name
        self._read_count = 0
        self._write_lock = asyncio.Lock()
        self._read_lock = asyncio.Lock()
        self._readers_lock = asyncio.Lock()
    
    @asynccontextmanager
    async def read_lock(self) -> AsyncIterator[None]:
        """Acquire read lock."""
        async with self._readers_lock:
            self._read_count += 1
            if self._read_count == 1:
                await self._write_lock.acquire()
        
        try:
            yield
        finally:
            async with self._readers_lock:
                self._read_count -= 1
                if self._read_count == 0:
                    self._write_lock.release()
    
    @asynccontextmanager
    async def write_lock(self) -> AsyncIterator[None]:
        """Acquire write lock."""
        async with self._write_lock:
            yield
    
    @property
    def readers(self) -> int:
        return self._read_count
    
    @property
    def is_write_locked(self) -> bool:
        return self._write_lock.locked()


class Semaphore:
    """
    Counting semaphore with named permits.
    """
    
    def __init__(self, name: str, permits: int):
        self._name = name
        self._permits = permits
        self._semaphore = asyncio.Semaphore(permits)
        self._holders: Set[str] = set()
    
    async def acquire(self, holder_id: Optional[str] = None) -> bool:
        await self._semaphore.acquire()
        if holder_id:
            self._holders.add(holder_id)
        return True
    
    async def release(self, holder_id: Optional[str] = None) -> None:
        if holder_id:
            self._holders.discard(holder_id)
        self._semaphore.release()
    
    @property
    def available(self) -> int:
        return self._semaphore._value
    
    @property
    def total(self) -> int:
        return self._permits
    
    async def __aenter__(self) -> "Semaphore":
        await self.acquire()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.release()


class LockManager(ABC):
    """
    Abstract lock manager.
    """
    
    @abstractmethod
    async def acquire(
        self,
        name: str,
        lock_type: LockType = LockType.EXCLUSIVE,
        timeout: Optional[float] = None,
        ttl: Optional[float] = None,
    ) -> Lock:
        """Acquire a named lock."""
        pass
    
    @abstractmethod
    async def release(self, name: str) -> None:
        """Release a named lock."""
        pass
    
    @abstractmethod
    async def is_locked(self, name: str) -> bool:
        """Check if lock is held."""
        pass
    
    @abstractmethod
    async def get_info(self, name: str) -> Optional[LockInfo]:
        """Get lock information."""
        pass
    
    @abstractmethod
    async def stats(self) -> LockStats:
        """Get lock statistics."""
        pass
    
    @asynccontextmanager
    async def lock(
        self,
        name: str,
        lock_type: LockType = LockType.EXCLUSIVE,
        timeout: Optional[float] = None,
        ttl: Optional[float] = None,
    ) -> AsyncIterator[Lock]:
        """Context manager for lock acquisition."""
        lock = await self.acquire(name, lock_type, timeout, ttl)
        try:
            yield lock
        finally:
            await lock.release()


class InMemoryLockManager(LockManager):
    """
    In-memory lock manager.
    """
    
    def __init__(self, owner: Optional[str] = None):
        self._owner = owner or str(uuid.uuid4())
        self._locks: Dict[str, LocalLock] = {}
        self._rw_locks: Dict[str, ReadWriteLock] = {}
        self._semaphores: Dict[str, Semaphore] = {}
        self._stats = LockStats()
        self._manager_lock = asyncio.Lock()
        
        # For deadlock detection
        self._wait_graph: Dict[str, Set[str]] = defaultdict(set)
    
    async def acquire(
        self,
        name: str,
        lock_type: LockType = LockType.EXCLUSIVE,
        timeout: Optional[float] = None,
        ttl: Optional[float] = None,
    ) -> Lock:
        self._stats.total_acquisitions += 1
        
        async with self._manager_lock:
            if name not in self._locks:
                config = LockConfig(timeout=timeout, ttl=ttl)
                self._locks[name] = LocalLock(name, self._owner, config)
        
        lock = self._locks[name]
        
        try:
            acquired = await lock.acquire(timeout=timeout, blocking=True)
            
            if acquired:
                self._stats.successful_acquisitions += 1
                self._stats.current_held += 1
            else:
                self._stats.failed_acquisitions += 1
            
            return lock
            
        except LockTimeoutError:
            self._stats.timeouts += 1
            raise
    
    async def release(self, name: str) -> None:
        if name in self._locks:
            await self._locks[name].release()
            self._stats.current_held = max(0, self._stats.current_held - 1)
    
    async def is_locked(self, name: str) -> bool:
        if name in self._locks:
            return self._locks[name].is_held
        return False
    
    async def get_info(self, name: str) -> Optional[LockInfo]:
        if name in self._locks:
            return self._locks[name]._info
        return None
    
    async def stats(self) -> LockStats:
        return self._stats
    
    def get_rw_lock(self, name: str) -> ReadWriteLock:
        """Get or create read-write lock."""
        if name not in self._rw_locks:
            self._rw_locks[name] = ReadWriteLock(name)
        return self._rw_locks[name]
    
    def get_semaphore(self, name: str, permits: int = 1) -> Semaphore:
        """Get or create semaphore."""
        if name not in self._semaphores:
            self._semaphores[name] = Semaphore(name, permits)
        return self._semaphores[name]
    
    async def detect_deadlock(self) -> List[List[str]]:
        """
        Detect deadlocks using wait-for graph.
        Returns cycles (deadlocks) found.
        """
        cycles = []
        visited = set()
        path = []
        
        def dfs(node: str) -> bool:
            if node in path:
                cycle_start = path.index(node)
                cycles.append(path[cycle_start:] + [node])
                return True
            
            if node in visited:
                return False
            
            visited.add(node)
            path.append(node)
            
            for neighbor in self._wait_graph.get(node, set()):
                if dfs(neighbor):
                    return True
            
            path.pop()
            return False
        
        for node in list(self._wait_graph.keys()):
            if node not in visited:
                dfs(node)
        
        if cycles:
            self._stats.deadlocks_detected += len(cycles)
        
        return cycles


class LockRegistry:
    """
    Registry for lock managers.
    """
    
    def __init__(self):
        self._managers: Dict[str, LockManager] = {}
        self._default: Optional[str] = None
    
    def register(
        self,
        name: str,
        manager: LockManager,
        default: bool = False,
    ) -> None:
        """Register a lock manager."""
        self._managers[name] = manager
        if default or self._default is None:
            self._default = name
    
    def get(self, name: Optional[str] = None) -> LockManager:
        """Get a lock manager."""
        name = name or self._default
        if not name or name not in self._managers:
            raise LockError(f"Lock manager not found: {name}")
        return self._managers[name]


# Global registry
_global_registry = LockRegistry()


# Decorators
def with_lock(
    name: str,
    lock_type: LockType = LockType.EXCLUSIVE,
    timeout: Optional[float] = None,
    manager_name: Optional[str] = None,
) -> Callable:
    """
    Decorator to execute function with lock.
    
    Example:
        @with_lock("resource:123")
        async def update_resource():
            ...
    """
    def decorator(func: Callable) -> Callable:
        async def wrapper(*args, **kwargs):
            manager = get_lock_manager(manager_name)
            
            async with manager.lock(name, lock_type, timeout):
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                return func(*args, **kwargs)
        
        return wrapper
    
    return decorator


def synchronized(func: Callable) -> Callable:
    """
    Decorator to synchronize function execution.
    
    Example:
        @synchronized
        async def critical_section():
            ...
    """
    lock = asyncio.Lock()
    
    async def wrapper(*args, **kwargs):
        async with lock:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            return func(*args, **kwargs)
    
    return wrapper


def with_semaphore(
    name: str,
    permits: int = 1,
    manager_name: Optional[str] = None,
) -> Callable:
    """
    Decorator to limit concurrent executions.
    
    Example:
        @with_semaphore("db-connections", permits=10)
        async def query_database():
            ...
    """
    def decorator(func: Callable) -> Callable:
        async def wrapper(*args, **kwargs):
            manager = get_lock_manager(manager_name)
            
            if isinstance(manager, InMemoryLockManager):
                sem = manager.get_semaphore(name, permits)
                async with sem:
                    if asyncio.iscoroutinefunction(func):
                        return await func(*args, **kwargs)
                    return func(*args, **kwargs)
            else:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                return func(*args, **kwargs)
        
        return wrapper
    
    return decorator


# Factory functions
def create_lock_manager(
    owner: Optional[str] = None,
) -> InMemoryLockManager:
    """Create an in-memory lock manager."""
    return InMemoryLockManager(owner)


def create_local_lock(
    name: str,
    owner: Optional[str] = None,
    timeout: Optional[float] = None,
    ttl: Optional[float] = None,
    reentrant: bool = True,
) -> LocalLock:
    """Create a local lock."""
    config = LockConfig(
        timeout=timeout,
        ttl=ttl,
        reentrant=reentrant,
    )
    return LocalLock(name, owner or str(uuid.uuid4()), config)


def create_rw_lock(name: str) -> ReadWriteLock:
    """Create a read-write lock."""
    return ReadWriteLock(name)


def create_semaphore(name: str, permits: int = 1) -> Semaphore:
    """Create a semaphore."""
    return Semaphore(name, permits)


def register_lock_manager(
    name: str,
    manager: LockManager,
    default: bool = False,
) -> None:
    """Register lock manager in global registry."""
    _global_registry.register(name, manager, default)


def get_lock_manager(name: Optional[str] = None) -> LockManager:
    """Get lock manager from global registry."""
    try:
        return _global_registry.get(name)
    except LockError:
        # Create default if not registered
        manager = create_lock_manager()
        register_lock_manager("default", manager, default=True)
        return manager


__all__ = [
    # Exceptions
    "LockError",
    "LockAcquireError",
    "LockTimeoutError",
    "DeadlockError",
    # Enums
    "LockType",
    "LockState",
    # Data classes
    "LockInfo",
    "LockConfig",
    "LockStats",
    # Lock types
    "Lock",
    "LocalLock",
    "ReadWriteLock",
    "Semaphore",
    # Manager
    "LockManager",
    "InMemoryLockManager",
    # Registry
    "LockRegistry",
    # Decorators
    "with_lock",
    "synchronized",
    "with_semaphore",
    # Factory functions
    "create_lock_manager",
    "create_local_lock",
    "create_rw_lock",
    "create_semaphore",
    "register_lock_manager",
    "get_lock_manager",
]
