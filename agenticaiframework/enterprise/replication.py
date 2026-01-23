"""
Enterprise Replication Module.

Provides data replication, sync strategies, and conflict
resolution for distributed systems.

Example:
    # Create replicator
    replicator = create_replicator(
        strategy="async",
        replicas=["replica1", "replica2"]
    )
    
    # Replicate data
    await replicator.replicate("key", data)
    
    # With conflict resolution
    @conflict_resolver("last_write_wins")
    async def merge_updates(local, remote):
        ...
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
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
)

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ReplicationError(Exception):
    """Replication error."""
    pass


class ConflictError(ReplicationError):
    """Conflict during replication."""
    pass


class QuorumNotReachedError(ReplicationError):
    """Required quorum not reached."""
    pass


class ReplicationStrategy(str, Enum):
    """Replication strategy."""
    SYNC = "sync"  # Wait for all replicas
    ASYNC = "async"  # Fire and forget
    SEMI_SYNC = "semi_sync"  # Wait for quorum
    CHAIN = "chain"  # Chain replication


class ConflictResolution(str, Enum):
    """Conflict resolution strategy."""
    LAST_WRITE_WINS = "last_write_wins"
    FIRST_WRITE_WINS = "first_write_wins"
    MERGE = "merge"
    CUSTOM = "custom"


class ReplicaState(str, Enum):
    """Replica state."""
    ACTIVE = "active"
    SYNCING = "syncing"
    LAGGING = "lagging"
    OFFLINE = "offline"


@dataclass
class ReplicaInfo:
    """Information about a replica."""
    replica_id: str
    address: str
    state: ReplicaState = ReplicaState.ACTIVE
    lag_ms: int = 0
    last_sync: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReplicationConfig:
    """Replication configuration."""
    strategy: ReplicationStrategy = ReplicationStrategy.ASYNC
    min_replicas: int = 1
    max_lag_ms: int = 1000
    sync_timeout_seconds: float = 5.0
    retry_attempts: int = 3
    retry_delay_ms: int = 100


@dataclass
class ReplicatedData:
    """Data with replication metadata."""
    key: str
    value: Any
    version: int = 1
    timestamp: datetime = field(default_factory=datetime.now)
    source_replica: Optional[str] = None
    vector_clock: Dict[str, int] = field(default_factory=dict)
    checksum: Optional[str] = None
    
    def compute_checksum(self) -> str:
        """Compute checksum of the value."""
        content = str(self.value).encode()
        return hashlib.sha256(content).hexdigest()[:16]
    
    def increment_version(self, replica_id: str) -> None:
        """Increment version for replica."""
        self.version += 1
        self.vector_clock[replica_id] = self.vector_clock.get(replica_id, 0) + 1
        self.timestamp = datetime.now()
        self.checksum = self.compute_checksum()


@dataclass
class ConflictInfo:
    """Information about a conflict."""
    key: str
    local_data: ReplicatedData
    remote_data: ReplicatedData
    resolution: Optional[str] = None
    resolved_value: Optional[Any] = None


@dataclass
class ReplicationResult:
    """Result of replication operation."""
    success: bool
    key: str
    replicated_to: List[str]
    failed_replicas: List[str]
    version: int = 0
    latency_ms: float = 0
    error: Optional[str] = None


class ReplicaStore(ABC):
    """Abstract replica data store."""
    
    @abstractmethod
    async def get(self, key: str) -> Optional[ReplicatedData]:
        """Get data by key."""
        pass
    
    @abstractmethod
    async def set(
        self,
        key: str,
        data: ReplicatedData,
    ) -> bool:
        """Set data."""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete data."""
        pass
    
    @abstractmethod
    async def get_all_keys(self) -> List[str]:
        """Get all keys."""
        pass


class InMemoryReplicaStore(ReplicaStore):
    """In-memory replica store."""
    
    def __init__(self):
        self._data: Dict[str, ReplicatedData] = {}
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[ReplicatedData]:
        return self._data.get(key)
    
    async def set(
        self,
        key: str,
        data: ReplicatedData,
    ) -> bool:
        async with self._lock:
            self._data[key] = data
            return True
    
    async def delete(self, key: str) -> bool:
        async with self._lock:
            if key in self._data:
                del self._data[key]
                return True
            return False
    
    async def get_all_keys(self) -> List[str]:
        return list(self._data.keys())


class ConflictResolver(ABC):
    """Abstract conflict resolver."""
    
    @abstractmethod
    async def resolve(
        self,
        local: ReplicatedData,
        remote: ReplicatedData,
    ) -> ReplicatedData:
        """Resolve conflict between local and remote data."""
        pass


class LastWriteWinsResolver(ConflictResolver):
    """Last write wins conflict resolution."""
    
    async def resolve(
        self,
        local: ReplicatedData,
        remote: ReplicatedData,
    ) -> ReplicatedData:
        if remote.timestamp > local.timestamp:
            return remote
        return local


class FirstWriteWinsResolver(ConflictResolver):
    """First write wins conflict resolution."""
    
    async def resolve(
        self,
        local: ReplicatedData,
        remote: ReplicatedData,
    ) -> ReplicatedData:
        if remote.timestamp < local.timestamp:
            return remote
        return local


class VectorClockResolver(ConflictResolver):
    """Vector clock based conflict resolution."""
    
    async def resolve(
        self,
        local: ReplicatedData,
        remote: ReplicatedData,
    ) -> ReplicatedData:
        # Compare vector clocks
        local_dominates = True
        remote_dominates = True
        
        all_replicas = set(local.vector_clock.keys()) | set(remote.vector_clock.keys())
        
        for replica in all_replicas:
            local_v = local.vector_clock.get(replica, 0)
            remote_v = remote.vector_clock.get(replica, 0)
            
            if local_v < remote_v:
                local_dominates = False
            if remote_v < local_v:
                remote_dominates = False
        
        if remote_dominates and not local_dominates:
            return remote
        if local_dominates and not remote_dominates:
            return local
        
        # Concurrent updates - use timestamp as tiebreaker
        if remote.timestamp > local.timestamp:
            return remote
        return local


class MergeResolver(ConflictResolver):
    """Merge-based conflict resolution."""
    
    def __init__(
        self,
        merge_fn: Optional[Callable[[Any, Any], Any]] = None,
    ):
        self._merge_fn = merge_fn
    
    async def resolve(
        self,
        local: ReplicatedData,
        remote: ReplicatedData,
    ) -> ReplicatedData:
        if self._merge_fn:
            merged = self._merge_fn(local.value, remote.value)
        else:
            # Default: prefer remote
            merged = remote.value
        
        # Create new version with merged data
        result = ReplicatedData(
            key=local.key,
            value=merged,
            version=max(local.version, remote.version) + 1,
            timestamp=datetime.now(),
            vector_clock={**local.vector_clock, **remote.vector_clock},
        )
        result.checksum = result.compute_checksum()
        
        return result


class Replica:
    """
    A replica node.
    """
    
    def __init__(
        self,
        replica_id: str,
        store: ReplicaStore,
        resolver: Optional[ConflictResolver] = None,
    ):
        self._replica_id = replica_id
        self._store = store
        self._resolver = resolver or LastWriteWinsResolver()
        self._peers: Dict[str, "Replica"] = {}
    
    @property
    def replica_id(self) -> str:
        return self._replica_id
    
    def add_peer(self, peer: "Replica") -> None:
        """Add a peer replica."""
        self._peers[peer.replica_id] = peer
    
    def remove_peer(self, replica_id: str) -> None:
        """Remove a peer replica."""
        self._peers.pop(replica_id, None)
    
    async def write(
        self,
        key: str,
        value: Any,
    ) -> ReplicatedData:
        """Write data locally."""
        existing = await self._store.get(key)
        
        if existing:
            data = ReplicatedData(
                key=key,
                value=value,
                version=existing.version + 1,
                source_replica=self._replica_id,
                vector_clock=existing.vector_clock.copy(),
            )
        else:
            data = ReplicatedData(
                key=key,
                value=value,
                source_replica=self._replica_id,
            )
        
        data.increment_version(self._replica_id)
        await self._store.set(key, data)
        
        return data
    
    async def read(self, key: str) -> Optional[ReplicatedData]:
        """Read data locally."""
        return await self._store.get(key)
    
    async def receive_replication(
        self,
        data: ReplicatedData,
    ) -> bool:
        """Receive replicated data from peer."""
        existing = await self._store.get(data.key)
        
        if not existing:
            await self._store.set(data.key, data)
            return True
        
        # Check for conflict
        if data.version != existing.version:
            # Resolve conflict
            resolved = await self._resolver.resolve(existing, data)
            await self._store.set(data.key, resolved)
        else:
            await self._store.set(data.key, data)
        
        return True


class Replicator:
    """
    Data replicator.
    """
    
    def __init__(
        self,
        primary: Replica,
        replicas: List[Replica],
        config: Optional[ReplicationConfig] = None,
    ):
        self._primary = primary
        self._replicas = {r.replica_id: r for r in replicas}
        self._config = config or ReplicationConfig()
        self._stats = {
            "total_replications": 0,
            "successful": 0,
            "failed": 0,
        }
    
    @property
    def primary(self) -> Replica:
        return self._primary
    
    @property
    def replicas(self) -> Dict[str, Replica]:
        return self._replicas.copy()
    
    async def replicate(
        self,
        key: str,
        value: Any,
    ) -> ReplicationResult:
        """Replicate data to all replicas."""
        start = time.time()
        
        # Write to primary
        data = await self._primary.write(key, value)
        
        # Replicate based on strategy
        if self._config.strategy == ReplicationStrategy.SYNC:
            result = await self._sync_replicate(data)
        elif self._config.strategy == ReplicationStrategy.ASYNC:
            result = await self._async_replicate(data)
        elif self._config.strategy == ReplicationStrategy.SEMI_SYNC:
            result = await self._semi_sync_replicate(data)
        else:
            result = await self._async_replicate(data)
        
        result.latency_ms = (time.time() - start) * 1000
        
        self._stats["total_replications"] += 1
        if result.success:
            self._stats["successful"] += 1
        else:
            self._stats["failed"] += 1
        
        return result
    
    async def _sync_replicate(
        self,
        data: ReplicatedData,
    ) -> ReplicationResult:
        """Synchronous replication - wait for all."""
        replicated_to = []
        failed_replicas = []
        
        tasks = []
        for replica_id, replica in self._replicas.items():
            tasks.append(
                self._replicate_to(replica, data)
            )
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for replica_id, result in zip(self._replicas.keys(), results):
            if isinstance(result, Exception) or not result:
                failed_replicas.append(replica_id)
            else:
                replicated_to.append(replica_id)
        
        success = len(failed_replicas) == 0
        
        return ReplicationResult(
            success=success,
            key=data.key,
            replicated_to=replicated_to,
            failed_replicas=failed_replicas,
            version=data.version,
        )
    
    async def _async_replicate(
        self,
        data: ReplicatedData,
    ) -> ReplicationResult:
        """Asynchronous replication - fire and forget."""
        for replica in self._replicas.values():
            asyncio.create_task(self._replicate_to(replica, data))
        
        return ReplicationResult(
            success=True,
            key=data.key,
            replicated_to=[],  # Unknown yet
            failed_replicas=[],
            version=data.version,
        )
    
    async def _semi_sync_replicate(
        self,
        data: ReplicatedData,
    ) -> ReplicationResult:
        """Semi-synchronous replication - wait for quorum."""
        replicated_to = []
        failed_replicas = []
        
        required = self._config.min_replicas
        
        async def replicate_with_tracking(replica_id: str, replica: Replica):
            try:
                result = await asyncio.wait_for(
                    self._replicate_to(replica, data),
                    timeout=self._config.sync_timeout_seconds,
                )
                return replica_id, result
            except Exception:
                return replica_id, False
        
        tasks = [
            replicate_with_tracking(rid, r)
            for rid, r in self._replicas.items()
        ]
        
        # Wait for first `required` successful replications
        pending = set(asyncio.create_task(t) for t in tasks)
        
        while pending and len(replicated_to) < required:
            done, pending = await asyncio.wait(
                pending,
                return_when=asyncio.FIRST_COMPLETED,
            )
            
            for task in done:
                replica_id, success = task.result()
                if success:
                    replicated_to.append(replica_id)
                else:
                    failed_replicas.append(replica_id)
        
        # Cancel remaining
        for task in pending:
            task.cancel()
        
        success = len(replicated_to) >= required
        
        return ReplicationResult(
            success=success,
            key=data.key,
            replicated_to=replicated_to,
            failed_replicas=failed_replicas,
            version=data.version,
            error=None if success else "Quorum not reached",
        )
    
    async def _replicate_to(
        self,
        replica: Replica,
        data: ReplicatedData,
    ) -> bool:
        """Replicate data to a single replica."""
        for attempt in range(self._config.retry_attempts):
            try:
                return await replica.receive_replication(data)
            except Exception as e:
                logger.warning(
                    f"Replication to {replica.replica_id} failed: {e}"
                )
                if attempt < self._config.retry_attempts - 1:
                    await asyncio.sleep(
                        self._config.retry_delay_ms / 1000
                    )
        
        return False


class ReplicationGroup:
    """
    Group of replicas with automatic sync.
    """
    
    def __init__(
        self,
        group_id: str,
        replicas: List[Replica],
        config: Optional[ReplicationConfig] = None,
    ):
        self._group_id = group_id
        self._replicas = {r.replica_id: r for r in replicas}
        self._config = config or ReplicationConfig()
        self._primary_id: Optional[str] = None
        self._sync_task: Optional[asyncio.Task] = None
    
    @property
    def group_id(self) -> str:
        return self._group_id
    
    @property
    def primary(self) -> Optional[Replica]:
        if self._primary_id:
            return self._replicas.get(self._primary_id)
        return None
    
    def set_primary(self, replica_id: str) -> None:
        """Set primary replica."""
        if replica_id in self._replicas:
            self._primary_id = replica_id
    
    async def start_sync(
        self,
        interval_seconds: float = 10.0,
    ) -> None:
        """Start periodic sync."""
        async def sync_loop():
            while True:
                try:
                    await self.sync_all()
                except Exception as e:
                    logger.error(f"Sync error: {e}")
                
                await asyncio.sleep(interval_seconds)
        
        self._sync_task = asyncio.create_task(sync_loop())
    
    async def stop_sync(self) -> None:
        """Stop periodic sync."""
        if self._sync_task:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass
    
    async def sync_all(self) -> Dict[str, int]:
        """Sync all replicas."""
        if not self._primary_id:
            return {}
        
        primary = self._replicas[self._primary_id]
        synced = {}
        
        # Get all keys from primary
        keys = await primary._store.get_all_keys()
        
        for replica_id, replica in self._replicas.items():
            if replica_id == self._primary_id:
                continue
            
            count = 0
            for key in keys:
                data = await primary.read(key)
                if data:
                    await replica.receive_replication(data)
                    count += 1
            
            synced[replica_id] = count
        
        return synced


class AntiEntropy:
    """
    Anti-entropy protocol for replica synchronization.
    """
    
    def __init__(
        self,
        local: Replica,
        peers: List[Replica],
        resolver: Optional[ConflictResolver] = None,
    ):
        self._local = local
        self._peers = peers
        self._resolver = resolver or VectorClockResolver()
    
    async def sync_with_peer(
        self,
        peer: Replica,
    ) -> Dict[str, str]:
        """Sync with a peer using push-pull."""
        results = {"pushed": 0, "pulled": 0, "conflicts": 0}
        
        local_keys = set(await self._local._store.get_all_keys())
        peer_keys = set(await peer._store.get_all_keys())
        
        # Keys only in local - push
        for key in local_keys - peer_keys:
            data = await self._local.read(key)
            if data:
                await peer.receive_replication(data)
                results["pushed"] += 1
        
        # Keys only in peer - pull
        for key in peer_keys - local_keys:
            data = await peer.read(key)
            if data:
                await self._local.receive_replication(data)
                results["pulled"] += 1
        
        # Keys in both - check versions
        for key in local_keys & peer_keys:
            local_data = await self._local.read(key)
            peer_data = await peer.read(key)
            
            if local_data and peer_data:
                if local_data.version != peer_data.version:
                    # Conflict - resolve
                    resolved = await self._resolver.resolve(
                        local_data,
                        peer_data,
                    )
                    
                    await self._local._store.set(key, resolved)
                    await peer._store.set(key, resolved)
                    results["conflicts"] += 1
        
        return results
    
    async def run_round(self) -> Dict[str, Dict[str, str]]:
        """Run one round of anti-entropy."""
        results = {}
        
        for peer in self._peers:
            try:
                results[peer.replica_id] = await self.sync_with_peer(peer)
            except Exception as e:
                logger.error(f"Sync with {peer.replica_id} failed: {e}")
                results[peer.replica_id] = {"error": str(e)}
        
        return results


# Decorators
def replicated(
    replicator: Replicator,
    key_extractor: Callable[..., str],
) -> Callable:
    """
    Decorator for replicated writes.
    
    Example:
        @replicated(replicator, lambda user_id, data: user_id)
        async def update_user(user_id: str, data: dict):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = await func(*args, **kwargs)
            
            # Extract key and replicate
            key = key_extractor(*args, **kwargs)
            await replicator.replicate(key, result)
            
            return result
        
        return wrapper
    
    return decorator


def conflict_resolver(
    strategy: Union[ConflictResolution, str] = ConflictResolution.LAST_WRITE_WINS,
) -> Callable:
    """
    Decorator to create a conflict resolver.
    
    Example:
        @conflict_resolver("merge")
        def merge_documents(local, remote):
            return {**local, **remote}
    """
    def decorator(func: Callable) -> ConflictResolver:
        class CustomResolver(ConflictResolver):
            async def resolve(
                self,
                local: ReplicatedData,
                remote: ReplicatedData,
            ) -> ReplicatedData:
                merged = func(local.value, remote.value)
                
                return ReplicatedData(
                    key=local.key,
                    value=merged,
                    version=max(local.version, remote.version) + 1,
                    timestamp=datetime.now(),
                    vector_clock={**local.vector_clock, **remote.vector_clock},
                )
        
        return CustomResolver()
    
    return decorator


# Factory functions
def create_replica(
    replica_id: str,
    store: Optional[ReplicaStore] = None,
    resolver: Optional[ConflictResolver] = None,
) -> Replica:
    """Create a replica."""
    s = store or InMemoryReplicaStore()
    return Replica(replica_id, s, resolver)


def create_replicator(
    primary_id: str = "primary",
    replica_ids: Optional[List[str]] = None,
    strategy: ReplicationStrategy = ReplicationStrategy.ASYNC,
) -> Replicator:
    """Create a replicator."""
    primary = create_replica(primary_id)
    
    replicas = []
    for rid in (replica_ids or ["replica1", "replica2"]):
        replicas.append(create_replica(rid))
    
    config = ReplicationConfig(strategy=strategy)
    
    return Replicator(primary, replicas, config)


def create_conflict_resolver(
    strategy: Union[ConflictResolution, str] = ConflictResolution.LAST_WRITE_WINS,
    merge_fn: Optional[Callable[[Any, Any], Any]] = None,
) -> ConflictResolver:
    """Create a conflict resolver."""
    if isinstance(strategy, str):
        strategy = ConflictResolution(strategy)
    
    if strategy == ConflictResolution.LAST_WRITE_WINS:
        return LastWriteWinsResolver()
    elif strategy == ConflictResolution.FIRST_WRITE_WINS:
        return FirstWriteWinsResolver()
    elif strategy == ConflictResolution.MERGE:
        return MergeResolver(merge_fn)
    else:
        return LastWriteWinsResolver()


def create_replication_group(
    group_id: str,
    num_replicas: int = 3,
    primary_idx: int = 0,
) -> ReplicationGroup:
    """Create a replication group."""
    replicas = [
        create_replica(f"replica_{i}")
        for i in range(num_replicas)
    ]
    
    group = ReplicationGroup(group_id, replicas)
    group.set_primary(replicas[primary_idx].replica_id)
    
    return group


def create_anti_entropy(
    local: Replica,
    peers: List[Replica],
) -> AntiEntropy:
    """Create anti-entropy protocol."""
    return AntiEntropy(local, peers)


__all__ = [
    # Exceptions
    "ReplicationError",
    "ConflictError",
    "QuorumNotReachedError",
    # Enums
    "ReplicationStrategy",
    "ConflictResolution",
    "ReplicaState",
    # Data classes
    "ReplicaInfo",
    "ReplicationConfig",
    "ReplicatedData",
    "ConflictInfo",
    "ReplicationResult",
    # Stores
    "ReplicaStore",
    "InMemoryReplicaStore",
    # Resolvers
    "ConflictResolver",
    "LastWriteWinsResolver",
    "FirstWriteWinsResolver",
    "VectorClockResolver",
    "MergeResolver",
    # Core classes
    "Replica",
    "Replicator",
    "ReplicationGroup",
    "AntiEntropy",
    # Decorators
    "replicated",
    "conflict_resolver",
    # Factory functions
    "create_replica",
    "create_replicator",
    "create_conflict_resolver",
    "create_replication_group",
    "create_anti_entropy",
]
