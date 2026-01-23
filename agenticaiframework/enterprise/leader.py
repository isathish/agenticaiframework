"""
Enterprise Leader Election Module.

Provides leader election, distributed locks, and coordination
primitives for distributed systems.

Example:
    # Create leader elector
    elector = create_leader_elector("my-service")
    
    # Participate in election
    async with elector.campaign() as leadership:
        if leadership.is_leader:
            # I'm the leader
            await do_leader_work()
    
    # Distributed lock
    lock = create_distributed_lock("resource_123")
    async with lock.acquire():
        # Exclusive access to resource
        ...
    
    # With decorator
    @leader_only(elector)
    async def leader_task():
        ...
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
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
    TypeVar,
)

logger = logging.getLogger(__name__)

T = TypeVar('T')


class LeaderError(Exception):
    """Leader election error."""
    pass


class LockError(Exception):
    """Distributed lock error."""
    pass


class LockAcquisitionError(LockError):
    """Failed to acquire lock."""
    pass


class LeadershipState(str, Enum):
    """Leadership state."""
    FOLLOWER = "follower"
    CANDIDATE = "candidate"
    LEADER = "leader"


class LockState(str, Enum):
    """Lock state."""
    UNLOCKED = "unlocked"
    LOCKED = "locked"
    WAITING = "waiting"


@dataclass
class LeaderInfo:
    """Information about the current leader."""
    leader_id: str
    node_id: str
    elected_at: datetime
    term: int
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Leadership:
    """Leadership context."""
    is_leader: bool
    leader_id: Optional[str] = None
    term: int = 0
    since: Optional[datetime] = None
    
    def assert_leader(self) -> None:
        """Assert that we are the leader."""
        if not self.is_leader:
            raise LeaderError("Not the leader")


@dataclass
class LockInfo:
    """Distributed lock information."""
    lock_id: str
    resource_id: str
    holder_id: str
    acquired_at: datetime
    ttl_seconds: int
    expires_at: datetime


@dataclass
class ElectionConfig:
    """Leader election configuration."""
    election_timeout_ms: int = 5000
    heartbeat_interval_ms: int = 1000
    lease_duration_seconds: int = 30


class LeaderStore(ABC):
    """Abstract leader state store."""
    
    @abstractmethod
    async def try_acquire_leadership(
        self,
        election_name: str,
        node_id: str,
        ttl_seconds: int,
    ) -> bool:
        """Try to acquire leadership."""
        pass
    
    @abstractmethod
    async def renew_leadership(
        self,
        election_name: str,
        node_id: str,
        ttl_seconds: int,
    ) -> bool:
        """Renew leadership lease."""
        pass
    
    @abstractmethod
    async def release_leadership(
        self,
        election_name: str,
        node_id: str,
    ) -> bool:
        """Release leadership."""
        pass
    
    @abstractmethod
    async def get_leader(
        self,
        election_name: str,
    ) -> Optional[LeaderInfo]:
        """Get current leader."""
        pass


class InMemoryLeaderStore(LeaderStore):
    """In-memory leader store (single-node only)."""
    
    def __init__(self):
        self._leaders: Dict[str, LeaderInfo] = {}
        self._lock = asyncio.Lock()
        self._terms: Dict[str, int] = {}
    
    async def try_acquire_leadership(
        self,
        election_name: str,
        node_id: str,
        ttl_seconds: int,
    ) -> bool:
        async with self._lock:
            current = self._leaders.get(election_name)
            
            # Check if current leader's lease expired
            if current:
                if current.elected_at + timedelta(seconds=ttl_seconds) > datetime.now():
                    return current.node_id == node_id
            
            # Acquire leadership
            term = self._terms.get(election_name, 0) + 1
            self._terms[election_name] = term
            
            self._leaders[election_name] = LeaderInfo(
                leader_id=f"{election_name}-leader",
                node_id=node_id,
                elected_at=datetime.now(),
                term=term,
            )
            
            return True
    
    async def renew_leadership(
        self,
        election_name: str,
        node_id: str,
        ttl_seconds: int,
    ) -> bool:
        async with self._lock:
            current = self._leaders.get(election_name)
            
            if current and current.node_id == node_id:
                current.elected_at = datetime.now()
                return True
            
            return False
    
    async def release_leadership(
        self,
        election_name: str,
        node_id: str,
    ) -> bool:
        async with self._lock:
            current = self._leaders.get(election_name)
            
            if current and current.node_id == node_id:
                del self._leaders[election_name]
                return True
            
            return False
    
    async def get_leader(
        self,
        election_name: str,
    ) -> Optional[LeaderInfo]:
        return self._leaders.get(election_name)


class LeaderElector:
    """
    Leader election coordinator.
    """
    
    def __init__(
        self,
        election_name: str,
        store: LeaderStore,
        node_id: Optional[str] = None,
        config: Optional[ElectionConfig] = None,
    ):
        self._election_name = election_name
        self._store = store
        self._node_id = node_id or f"{os.getpid()}-{uuid.uuid4().hex[:8]}"
        self._config = config or ElectionConfig()
        self._state = LeadershipState.FOLLOWER
        self._leadership: Optional[Leadership] = None
        self._callbacks: List[Callable[[Leadership], None]] = []
        self._running = False
        self._heartbeat_task: Optional[asyncio.Task] = None
    
    @property
    def node_id(self) -> str:
        return self._node_id
    
    @property
    def state(self) -> LeadershipState:
        return self._state
    
    @property
    def is_leader(self) -> bool:
        return self._state == LeadershipState.LEADER
    
    async def start(self) -> None:
        """Start participating in election."""
        if self._running:
            return
        
        self._running = True
        self._heartbeat_task = asyncio.create_task(self._election_loop())
        
        logger.info(f"Node {self._node_id} started leader election")
    
    async def stop(self) -> None:
        """Stop participating in election."""
        self._running = False
        
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        
        if self._state == LeadershipState.LEADER:
            await self._store.release_leadership(
                self._election_name,
                self._node_id,
            )
        
        self._state = LeadershipState.FOLLOWER
        
        logger.info(f"Node {self._node_id} stopped leader election")
    
    async def _election_loop(self) -> None:
        """Main election loop."""
        while self._running:
            try:
                if self._state == LeadershipState.LEADER:
                    # Renew lease
                    renewed = await self._store.renew_leadership(
                        self._election_name,
                        self._node_id,
                        self._config.lease_duration_seconds,
                    )
                    
                    if not renewed:
                        logger.warning(f"Lost leadership: {self._node_id}")
                        self._state = LeadershipState.FOLLOWER
                        self._leadership = None
                        self._notify_callbacks()
                else:
                    # Try to acquire leadership
                    acquired = await self._store.try_acquire_leadership(
                        self._election_name,
                        self._node_id,
                        self._config.lease_duration_seconds,
                    )
                    
                    if acquired:
                        logger.info(f"Acquired leadership: {self._node_id}")
                        self._state = LeadershipState.LEADER
                        
                        leader_info = await self._store.get_leader(
                            self._election_name
                        )
                        
                        self._leadership = Leadership(
                            is_leader=True,
                            leader_id=self._node_id,
                            term=leader_info.term if leader_info else 0,
                            since=datetime.now(),
                        )
                        
                        self._notify_callbacks()
                
                # Sleep for heartbeat interval
                await asyncio.sleep(
                    self._config.heartbeat_interval_ms / 1000
                )
            
            except asyncio.CancelledError:
                break
            
            except Exception as e:
                logger.error(f"Election error: {e}")
                await asyncio.sleep(1)
    
    def on_leadership_change(
        self,
        callback: Callable[[Leadership], None],
    ) -> Callable[[], None]:
        """Register callback for leadership changes."""
        self._callbacks.append(callback)
        
        def unregister():
            self._callbacks.remove(callback)
        
        return unregister
    
    def _notify_callbacks(self) -> None:
        """Notify registered callbacks."""
        leadership = self._leadership or Leadership(is_leader=False)
        
        for callback in self._callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(leadership))
                else:
                    callback(leadership)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    @asynccontextmanager
    async def campaign(self):
        """
        Context manager for leader campaign.
        
        Example:
            async with elector.campaign() as leadership:
                if leadership.is_leader:
                    await do_leader_work()
        """
        await self.start()
        
        try:
            # Wait briefly for initial election
            await asyncio.sleep(0.1)
            
            yield self._leadership or Leadership(is_leader=False)
        
        finally:
            await self.stop()
    
    async def wait_for_leadership(
        self,
        timeout: Optional[float] = None,
    ) -> bool:
        """Wait until this node becomes leader."""
        start = time.time()
        
        while True:
            if self.is_leader:
                return True
            
            if timeout and (time.time() - start) > timeout:
                return False
            
            await asyncio.sleep(0.1)


# Distributed Lock
class LockStore(ABC):
    """Abstract lock store."""
    
    @abstractmethod
    async def acquire(
        self,
        resource_id: str,
        holder_id: str,
        ttl_seconds: int,
    ) -> bool:
        """Acquire lock."""
        pass
    
    @abstractmethod
    async def release(
        self,
        resource_id: str,
        holder_id: str,
    ) -> bool:
        """Release lock."""
        pass
    
    @abstractmethod
    async def extend(
        self,
        resource_id: str,
        holder_id: str,
        ttl_seconds: int,
    ) -> bool:
        """Extend lock TTL."""
        pass
    
    @abstractmethod
    async def get_lock_info(
        self,
        resource_id: str,
    ) -> Optional[LockInfo]:
        """Get lock information."""
        pass


class InMemoryLockStore(LockStore):
    """In-memory lock store."""
    
    def __init__(self):
        self._locks: Dict[str, LockInfo] = {}
        self._lock = asyncio.Lock()
    
    async def acquire(
        self,
        resource_id: str,
        holder_id: str,
        ttl_seconds: int,
    ) -> bool:
        async with self._lock:
            current = self._locks.get(resource_id)
            
            # Check if lock is held by another
            if current:
                if current.expires_at > datetime.now():
                    return current.holder_id == holder_id
            
            # Acquire lock
            now = datetime.now()
            self._locks[resource_id] = LockInfo(
                lock_id=str(uuid.uuid4()),
                resource_id=resource_id,
                holder_id=holder_id,
                acquired_at=now,
                ttl_seconds=ttl_seconds,
                expires_at=now + timedelta(seconds=ttl_seconds),
            )
            
            return True
    
    async def release(
        self,
        resource_id: str,
        holder_id: str,
    ) -> bool:
        async with self._lock:
            current = self._locks.get(resource_id)
            
            if current and current.holder_id == holder_id:
                del self._locks[resource_id]
                return True
            
            return False
    
    async def extend(
        self,
        resource_id: str,
        holder_id: str,
        ttl_seconds: int,
    ) -> bool:
        async with self._lock:
            current = self._locks.get(resource_id)
            
            if current and current.holder_id == holder_id:
                current.expires_at = datetime.now() + timedelta(seconds=ttl_seconds)
                current.ttl_seconds = ttl_seconds
                return True
            
            return False
    
    async def get_lock_info(
        self,
        resource_id: str,
    ) -> Optional[LockInfo]:
        return self._locks.get(resource_id)


class DistributedLock:
    """
    Distributed lock for exclusive resource access.
    """
    
    def __init__(
        self,
        resource_id: str,
        store: LockStore,
        holder_id: Optional[str] = None,
        ttl_seconds: int = 30,
        retry_interval_ms: int = 100,
        max_retries: int = 100,
    ):
        self._resource_id = resource_id
        self._store = store
        self._holder_id = holder_id or f"{os.getpid()}-{uuid.uuid4().hex[:8]}"
        self._ttl_seconds = ttl_seconds
        self._retry_interval = retry_interval_ms / 1000
        self._max_retries = max_retries
        self._held = False
        self._extend_task: Optional[asyncio.Task] = None
    
    @property
    def resource_id(self) -> str:
        return self._resource_id
    
    @property
    def is_held(self) -> bool:
        return self._held
    
    async def try_acquire(self) -> bool:
        """Try to acquire lock without blocking."""
        acquired = await self._store.acquire(
            self._resource_id,
            self._holder_id,
            self._ttl_seconds,
        )
        
        if acquired:
            self._held = True
            self._start_extend_task()
        
        return acquired
    
    async def acquire_with_timeout(
        self,
        timeout_seconds: float,
    ) -> bool:
        """Acquire lock with timeout."""
        start = time.time()
        attempts = 0
        
        while True:
            if await self.try_acquire():
                return True
            
            if time.time() - start > timeout_seconds:
                return False
            
            attempts += 1
            if attempts >= self._max_retries:
                return False
            
            await asyncio.sleep(self._retry_interval)
    
    async def release(self) -> bool:
        """Release the lock."""
        self._stop_extend_task()
        
        if not self._held:
            return False
        
        released = await self._store.release(
            self._resource_id,
            self._holder_id,
        )
        
        self._held = not released
        
        return released
    
    def _start_extend_task(self) -> None:
        """Start automatic lock extension."""
        async def extend_loop():
            interval = self._ttl_seconds / 3
            
            while self._held:
                try:
                    await asyncio.sleep(interval)
                    
                    if self._held:
                        await self._store.extend(
                            self._resource_id,
                            self._holder_id,
                            self._ttl_seconds,
                        )
                
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Lock extend error: {e}")
        
        self._extend_task = asyncio.create_task(extend_loop())
    
    def _stop_extend_task(self) -> None:
        """Stop automatic lock extension."""
        if self._extend_task:
            self._extend_task.cancel()
            self._extend_task = None
    
    @asynccontextmanager
    async def acquire(self, timeout: Optional[float] = None):
        """
        Context manager for lock acquisition.
        
        Example:
            async with lock.acquire():
                # Exclusive access
                ...
        """
        if timeout:
            acquired = await self.acquire_with_timeout(timeout)
        else:
            # Keep trying
            while not await self.try_acquire():
                await asyncio.sleep(self._retry_interval)
            acquired = True
        
        if not acquired:
            raise LockAcquisitionError(
                f"Failed to acquire lock: {self._resource_id}"
            )
        
        try:
            yield self
        finally:
            await self.release()


class Semaphore:
    """
    Distributed semaphore for limiting concurrent access.
    """
    
    def __init__(
        self,
        resource_id: str,
        max_permits: int,
        store: LockStore,
        ttl_seconds: int = 30,
    ):
        self._resource_id = resource_id
        self._max_permits = max_permits
        self._store = store
        self._ttl_seconds = ttl_seconds
        self._holder_id = f"{os.getpid()}-{uuid.uuid4().hex[:8]}"
        self._acquired_slots: List[str] = []
    
    async def acquire(self, permits: int = 1) -> bool:
        """Acquire permits."""
        for i in range(permits):
            slot = f"{self._resource_id}:{i}"
            
            for attempt in range(self._max_permits):
                slot = f"{self._resource_id}:{(i + attempt) % self._max_permits}"
                
                acquired = await self._store.acquire(
                    slot,
                    self._holder_id,
                    self._ttl_seconds,
                )
                
                if acquired:
                    self._acquired_slots.append(slot)
                    break
            else:
                # Couldn't acquire, release what we got
                await self.release()
                return False
        
        return True
    
    async def release(self) -> None:
        """Release all acquired permits."""
        for slot in self._acquired_slots:
            await self._store.release(slot, self._holder_id)
        
        self._acquired_slots.clear()


# Decorators
def leader_only(
    elector: LeaderElector,
) -> Callable:
    """
    Decorator to run function only on leader.
    
    Example:
        @leader_only(elector)
        async def leader_task():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not elector.is_leader:
                logger.debug(f"Skipping {func.__name__}: not leader")
                return None
            
            return await func(*args, **kwargs)
        
        return wrapper
    
    return decorator


def with_lock(
    lock: DistributedLock,
    timeout: Optional[float] = None,
) -> Callable:
    """
    Decorator to acquire lock before function.
    
    Example:
        @with_lock(lock, timeout=10.0)
        async def exclusive_operation():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            async with lock.acquire(timeout):
                return await func(*args, **kwargs)
        
        return wrapper
    
    return decorator


def coordinated(
    resource_id: str,
    store: Optional[LockStore] = None,
) -> Callable:
    """
    Decorator for coordinated (locked) execution.
    
    Example:
        @coordinated("shared-resource")
        async def update_resource():
            ...
    """
    def decorator(func: Callable) -> Callable:
        _store = store or InMemoryLockStore()
        _lock = DistributedLock(resource_id, _store)
        
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            async with _lock.acquire():
                return await func(*args, **kwargs)
        
        return wrapper
    
    return decorator


# Factory functions
def create_leader_elector(
    election_name: str,
    store: Optional[LeaderStore] = None,
    node_id: Optional[str] = None,
) -> LeaderElector:
    """Create a leader elector."""
    s = store or InMemoryLeaderStore()
    return LeaderElector(election_name, s, node_id)


def create_distributed_lock(
    resource_id: str,
    store: Optional[LockStore] = None,
    ttl_seconds: int = 30,
) -> DistributedLock:
    """Create a distributed lock."""
    s = store or InMemoryLockStore()
    return DistributedLock(resource_id, s, ttl_seconds=ttl_seconds)


def create_semaphore(
    resource_id: str,
    max_permits: int,
    store: Optional[LockStore] = None,
) -> Semaphore:
    """Create a distributed semaphore."""
    s = store or InMemoryLockStore()
    return Semaphore(resource_id, max_permits, s)


__all__ = [
    # Exceptions
    "LeaderError",
    "LockError",
    "LockAcquisitionError",
    # Enums
    "LeadershipState",
    "LockState",
    # Data classes
    "LeaderInfo",
    "Leadership",
    "LockInfo",
    "ElectionConfig",
    # Stores
    "LeaderStore",
    "InMemoryLeaderStore",
    "LockStore",
    "InMemoryLockStore",
    # Core classes
    "LeaderElector",
    "DistributedLock",
    "Semaphore",
    # Decorators
    "leader_only",
    "with_lock",
    "coordinated",
    # Factory functions
    "create_leader_elector",
    "create_distributed_lock",
    "create_semaphore",
]
