"""
Enterprise Snapshot Module.

Provides state snapshotting, restore capabilities,
and versioning for event-sourced aggregates.

Example:
    # Create snapshot store
    store = create_snapshot_store()
    
    # Save snapshot
    await store.save_snapshot(
        aggregate_id="order_123",
        aggregate_type="Order",
        state=order.get_state(),
        version=order.version,
    )
    
    # Load snapshot
    snapshot = await store.get_latest(
        aggregate_id="order_123",
        aggregate_type="Order",
    )
    
    # With snapshotting aggregate
    @snapshotable(interval=100)
    class OrderAggregate(AggregateRoot):
        ...
"""

from __future__ import annotations

import asyncio
import copy
import gzip
import hashlib
import json
import logging
import pickle
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
    Type,
    TypeVar,
)

logger = logging.getLogger(__name__)

T = TypeVar('T')


class SnapshotError(Exception):
    """Snapshot error."""
    pass


class SnapshotNotFoundError(SnapshotError):
    """Snapshot not found."""
    pass


class SnapshotCorruptedError(SnapshotError):
    """Snapshot data is corrupted."""
    pass


class CompressionType(str, Enum):
    """Snapshot compression types."""
    NONE = "none"
    GZIP = "gzip"


class SerializationType(str, Enum):
    """Snapshot serialization types."""
    JSON = "json"
    PICKLE = "pickle"


@dataclass
class Snapshot:
    """Represents a snapshot of aggregate state."""
    id: str
    aggregate_id: str
    aggregate_type: str
    version: int
    state: Dict[str, Any]
    created_at: datetime = field(default_factory=datetime.now)
    checksum: Optional[str] = None
    compression: CompressionType = CompressionType.NONE
    serialization: SerializationType = SerializationType.JSON
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def verify_checksum(self) -> bool:
        """Verify snapshot checksum."""
        if not self.checksum:
            return True
        
        computed = self._compute_checksum(self.state)
        return computed == self.checksum
    
    @staticmethod
    def _compute_checksum(state: Dict[str, Any]) -> str:
        """Compute checksum of state."""
        state_bytes = json.dumps(state, sort_keys=True, default=str).encode()
        return hashlib.sha256(state_bytes).hexdigest()


@dataclass
class SnapshotConfig:
    """Snapshot configuration."""
    interval: int = 100  # Events between snapshots
    max_snapshots: int = 5  # Max snapshots to keep
    compression: CompressionType = CompressionType.GZIP
    serialization: SerializationType = SerializationType.JSON
    verify_checksums: bool = True
    auto_cleanup: bool = True


@dataclass
class SnapshotStats:
    """Snapshot statistics."""
    total_snapshots: int = 0
    total_size_bytes: int = 0
    last_snapshot_at: Optional[datetime] = None
    snapshots_by_type: Dict[str, int] = field(default_factory=dict)


class SnapshotStore(ABC):
    """Abstract snapshot store."""
    
    @abstractmethod
    async def save(self, snapshot: Snapshot) -> str:
        """Save a snapshot."""
        pass
    
    @abstractmethod
    async def get_latest(
        self,
        aggregate_id: str,
        aggregate_type: str,
    ) -> Optional[Snapshot]:
        """Get latest snapshot for aggregate."""
        pass
    
    @abstractmethod
    async def get_by_version(
        self,
        aggregate_id: str,
        aggregate_type: str,
        version: int,
    ) -> Optional[Snapshot]:
        """Get snapshot by specific version."""
        pass
    
    @abstractmethod
    async def list_snapshots(
        self,
        aggregate_id: str,
        aggregate_type: str,
    ) -> List[Snapshot]:
        """List all snapshots for aggregate."""
        pass
    
    @abstractmethod
    async def delete(self, snapshot_id: str) -> bool:
        """Delete a snapshot."""
        pass


class InMemorySnapshotStore(SnapshotStore):
    """In-memory snapshot store."""
    
    def __init__(self):
        self._snapshots: Dict[str, Snapshot] = {}
        self._by_aggregate: Dict[str, List[str]] = {}
        self._lock = asyncio.Lock()
    
    async def save(self, snapshot: Snapshot) -> str:
        """Save snapshot."""
        async with self._lock:
            self._snapshots[snapshot.id] = snapshot
            
            key = f"{snapshot.aggregate_type}:{snapshot.aggregate_id}"
            
            if key not in self._by_aggregate:
                self._by_aggregate[key] = []
            
            self._by_aggregate[key].append(snapshot.id)
            
            return snapshot.id
    
    async def get_latest(
        self,
        aggregate_id: str,
        aggregate_type: str,
    ) -> Optional[Snapshot]:
        """Get latest snapshot."""
        key = f"{aggregate_type}:{aggregate_id}"
        snapshot_ids = self._by_aggregate.get(key, [])
        
        if not snapshot_ids:
            return None
        
        # Get latest by version
        snapshots = [
            self._snapshots[sid]
            for sid in snapshot_ids
            if sid in self._snapshots
        ]
        
        if not snapshots:
            return None
        
        return max(snapshots, key=lambda s: s.version)
    
    async def get_by_version(
        self,
        aggregate_id: str,
        aggregate_type: str,
        version: int,
    ) -> Optional[Snapshot]:
        """Get snapshot by version."""
        key = f"{aggregate_type}:{aggregate_id}"
        snapshot_ids = self._by_aggregate.get(key, [])
        
        for sid in snapshot_ids:
            snapshot = self._snapshots.get(sid)
            if snapshot and snapshot.version == version:
                return snapshot
        
        return None
    
    async def list_snapshots(
        self,
        aggregate_id: str,
        aggregate_type: str,
    ) -> List[Snapshot]:
        """List all snapshots."""
        key = f"{aggregate_type}:{aggregate_id}"
        snapshot_ids = self._by_aggregate.get(key, [])
        
        return [
            self._snapshots[sid]
            for sid in snapshot_ids
            if sid in self._snapshots
        ]
    
    async def delete(self, snapshot_id: str) -> bool:
        """Delete snapshot."""
        async with self._lock:
            snapshot = self._snapshots.pop(snapshot_id, None)
            
            if snapshot:
                key = f"{snapshot.aggregate_type}:{snapshot.aggregate_id}"
                if key in self._by_aggregate:
                    self._by_aggregate[key] = [
                        sid for sid in self._by_aggregate[key]
                        if sid != snapshot_id
                    ]
                return True
            
            return False


class SnapshotSerializer:
    """Serializes and deserializes snapshot state."""
    
    def __init__(
        self,
        serialization: SerializationType = SerializationType.JSON,
        compression: CompressionType = CompressionType.NONE,
    ):
        self._serialization = serialization
        self._compression = compression
    
    def serialize(self, state: Dict[str, Any]) -> bytes:
        """Serialize state to bytes."""
        if self._serialization == SerializationType.JSON:
            data = json.dumps(state, default=str).encode()
        else:
            data = pickle.dumps(state)
        
        if self._compression == CompressionType.GZIP:
            data = gzip.compress(data)
        
        return data
    
    def deserialize(self, data: bytes) -> Dict[str, Any]:
        """Deserialize bytes to state."""
        if self._compression == CompressionType.GZIP:
            data = gzip.decompress(data)
        
        if self._serialization == SerializationType.JSON:
            return json.loads(data.decode())
        else:
            return pickle.loads(data)


class SnapshotManager:
    """
    Manages snapshots for aggregates.
    """
    
    def __init__(
        self,
        store: SnapshotStore,
        config: Optional[SnapshotConfig] = None,
    ):
        self._store = store
        self._config = config or SnapshotConfig()
        self._serializer = SnapshotSerializer(
            self._config.serialization,
            self._config.compression,
        )
    
    async def should_snapshot(
        self,
        aggregate_id: str,
        aggregate_type: str,
        current_version: int,
    ) -> bool:
        """Check if aggregate should be snapshotted."""
        latest = await self._store.get_latest(aggregate_id, aggregate_type)
        
        if not latest:
            return current_version >= self._config.interval
        
        events_since_snapshot = current_version - latest.version
        return events_since_snapshot >= self._config.interval
    
    async def create_snapshot(
        self,
        aggregate_id: str,
        aggregate_type: str,
        version: int,
        state: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Snapshot:
        """Create a new snapshot."""
        import uuid
        
        checksum = Snapshot._compute_checksum(state)
        
        snapshot = Snapshot(
            id=str(uuid.uuid4()),
            aggregate_id=aggregate_id,
            aggregate_type=aggregate_type,
            version=version,
            state=state,
            checksum=checksum,
            compression=self._config.compression,
            serialization=self._config.serialization,
            metadata=metadata or {},
        )
        
        await self._store.save(snapshot)
        
        # Cleanup old snapshots if needed
        if self._config.auto_cleanup:
            await self._cleanup_old_snapshots(aggregate_id, aggregate_type)
        
        logger.debug(
            f"Created snapshot for {aggregate_type}:{aggregate_id} "
            f"at version {version}"
        )
        
        return snapshot
    
    async def load_snapshot(
        self,
        aggregate_id: str,
        aggregate_type: str,
        version: Optional[int] = None,
    ) -> Optional[Snapshot]:
        """Load a snapshot."""
        if version:
            snapshot = await self._store.get_by_version(
                aggregate_id,
                aggregate_type,
                version,
            )
        else:
            snapshot = await self._store.get_latest(
                aggregate_id,
                aggregate_type,
            )
        
        if snapshot and self._config.verify_checksums:
            if not snapshot.verify_checksum():
                raise SnapshotCorruptedError(
                    f"Snapshot {snapshot.id} checksum verification failed"
                )
        
        return snapshot
    
    async def _cleanup_old_snapshots(
        self,
        aggregate_id: str,
        aggregate_type: str,
    ) -> int:
        """Remove old snapshots beyond max limit."""
        snapshots = await self._store.list_snapshots(
            aggregate_id,
            aggregate_type,
        )
        
        if len(snapshots) <= self._config.max_snapshots:
            return 0
        
        # Sort by version descending
        snapshots.sort(key=lambda s: s.version, reverse=True)
        
        # Delete oldest
        to_delete = snapshots[self._config.max_snapshots:]
        deleted = 0
        
        for snapshot in to_delete:
            if await self._store.delete(snapshot.id):
                deleted += 1
        
        return deleted
    
    async def restore_to_version(
        self,
        aggregate_id: str,
        aggregate_type: str,
        target_version: int,
    ) -> Optional[Snapshot]:
        """Find best snapshot for restoring to version."""
        snapshots = await self._store.list_snapshots(
            aggregate_id,
            aggregate_type,
        )
        
        # Find snapshot with version <= target_version
        valid_snapshots = [
            s for s in snapshots
            if s.version <= target_version
        ]
        
        if not valid_snapshots:
            return None
        
        # Return closest to target version
        return max(valid_snapshots, key=lambda s: s.version)


class SnapshotableAggregate(ABC):
    """
    Mixin for aggregates that support snapshotting.
    """
    
    @abstractmethod
    def get_state(self) -> Dict[str, Any]:
        """Get current state for snapshotting."""
        pass
    
    @abstractmethod
    def restore_state(self, state: Dict[str, Any]) -> None:
        """Restore state from snapshot."""
        pass
    
    @property
    @abstractmethod
    def id(self) -> str:
        """Get aggregate ID."""
        pass
    
    @property
    @abstractmethod
    def version(self) -> int:
        """Get current version."""
        pass


class SnapshotRepository(Generic[T]):
    """
    Repository with snapshot support.
    """
    
    def __init__(
        self,
        aggregate_type: Type[T],
        event_store: Any,
        snapshot_manager: SnapshotManager,
    ):
        self._aggregate_type = aggregate_type
        self._event_store = event_store
        self._snapshot_manager = snapshot_manager
    
    async def get(self, aggregate_id: str) -> Optional[T]:
        """Load aggregate with snapshot optimization."""
        aggregate_type_name = self._aggregate_type.__name__
        
        # Try to load from snapshot
        snapshot = await self._snapshot_manager.load_snapshot(
            aggregate_id,
            aggregate_type_name,
        )
        
        if snapshot:
            # Create aggregate and restore state
            aggregate = self._aggregate_type(aggregate_id)
            aggregate.restore_state(snapshot.state)
            
            # Apply events after snapshot
            events = await self._event_store.get_events(
                f"{aggregate_type_name}-{aggregate_id}",
                from_version=snapshot.version,
            )
            
            for event in events:
                aggregate._apply_event(event)
            
            return aggregate
        
        # No snapshot, load from all events
        events = await self._event_store.get_events(
            f"{aggregate_type_name}-{aggregate_id}",
        )
        
        if not events:
            return None
        
        aggregate = self._aggregate_type(aggregate_id)
        aggregate.load_from_history(events)
        
        return aggregate
    
    async def save(self, aggregate: T) -> None:
        """Save aggregate and create snapshot if needed."""
        aggregate_type_name = self._aggregate_type.__name__
        
        # Save events
        events = aggregate.uncommitted_events
        if events:
            await self._event_store.append(
                f"{aggregate_type_name}-{aggregate.id}",
                events,
                aggregate.version - len(events),
            )
            aggregate.clear_uncommitted_events()
        
        # Check if snapshot is needed
        if await self._snapshot_manager.should_snapshot(
            aggregate.id,
            aggregate_type_name,
            aggregate.version,
        ):
            await self._snapshot_manager.create_snapshot(
                aggregate.id,
                aggregate_type_name,
                aggregate.version,
                aggregate.get_state(),
            )


class PointInTimeRestore:
    """
    Restore aggregate to a point in time.
    """
    
    def __init__(
        self,
        event_store: Any,
        snapshot_store: SnapshotStore,
    ):
        self._event_store = event_store
        self._snapshot_store = snapshot_store
    
    async def restore_to_timestamp(
        self,
        aggregate_id: str,
        aggregate_type: Type[T],
        timestamp: datetime,
    ) -> Optional[T]:
        """Restore aggregate to specific timestamp."""
        aggregate_type_name = aggregate_type.__name__
        stream_id = f"{aggregate_type_name}-{aggregate_id}"
        
        # Get all events up to timestamp
        all_events = await self._event_store.get_events(stream_id)
        
        events = [
            e for e in all_events
            if e.timestamp <= timestamp
        ]
        
        if not events:
            return None
        
        aggregate = aggregate_type(aggregate_id)
        aggregate.load_from_history(events)
        
        return aggregate
    
    async def restore_to_version(
        self,
        aggregate_id: str,
        aggregate_type: Type[T],
        version: int,
    ) -> Optional[T]:
        """Restore aggregate to specific version."""
        aggregate_type_name = aggregate_type.__name__
        stream_id = f"{aggregate_type_name}-{aggregate_id}"
        
        # Try snapshot first
        snapshot = await self._snapshot_store.get_by_version(
            aggregate_id,
            aggregate_type_name,
            version,
        )
        
        if snapshot:
            aggregate = aggregate_type(aggregate_id)
            aggregate.restore_state(snapshot.state)
            return aggregate
        
        # Load events up to version
        all_events = await self._event_store.get_events(stream_id)
        events = [e for e in all_events if e.version <= version]
        
        if not events:
            return None
        
        aggregate = aggregate_type(aggregate_id)
        aggregate.load_from_history(events)
        
        return aggregate


# Decorators
def snapshotable(
    interval: int = 100,
    max_snapshots: int = 5,
) -> Callable:
    """
    Decorator to make an aggregate snapshotable.
    
    Example:
        @snapshotable(interval=100)
        class OrderAggregate(AggregateRoot):
            ...
    """
    def decorator(cls: type) -> type:
        cls._snapshot_interval = interval
        cls._snapshot_max = max_snapshots
        
        # Add get_state if not present
        if not hasattr(cls, "get_state"):
            def get_state(self) -> Dict[str, Any]:
                return {
                    k: copy.deepcopy(v)
                    for k, v in self.__dict__.items()
                    if not k.startswith("_")
                }
            cls.get_state = get_state
        
        # Add restore_state if not present
        if not hasattr(cls, "restore_state"):
            def restore_state(self, state: Dict[str, Any]) -> None:
                for key, value in state.items():
                    setattr(self, key, copy.deepcopy(value))
            cls.restore_state = restore_state
        
        return cls
    
    return decorator


def with_snapshots(
    manager: SnapshotManager,
) -> Callable:
    """
    Decorator to add automatic snapshotting to save operation.
    
    Example:
        @with_snapshots(snapshot_manager)
        async def save(aggregate):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(aggregate: Any, *args: Any, **kwargs: Any) -> Any:
            result = await func(aggregate, *args, **kwargs)
            
            # Check and create snapshot
            if await manager.should_snapshot(
                aggregate.id,
                type(aggregate).__name__,
                aggregate.version,
            ):
                await manager.create_snapshot(
                    aggregate.id,
                    type(aggregate).__name__,
                    aggregate.version,
                    aggregate.get_state(),
                )
            
            return result
        
        return wrapper
    
    return decorator


# Factory functions
def create_snapshot_store() -> InMemorySnapshotStore:
    """Create an in-memory snapshot store."""
    return InMemorySnapshotStore()


def create_snapshot_manager(
    store: Optional[SnapshotStore] = None,
    config: Optional[SnapshotConfig] = None,
) -> SnapshotManager:
    """Create a snapshot manager."""
    s = store or InMemorySnapshotStore()
    return SnapshotManager(s, config)


def create_snapshot_config(
    interval: int = 100,
    max_snapshots: int = 5,
    compression: CompressionType = CompressionType.GZIP,
) -> SnapshotConfig:
    """Create a snapshot configuration."""
    return SnapshotConfig(
        interval=interval,
        max_snapshots=max_snapshots,
        compression=compression,
    )


__all__ = [
    # Exceptions
    "SnapshotError",
    "SnapshotNotFoundError",
    "SnapshotCorruptedError",
    # Enums
    "CompressionType",
    "SerializationType",
    # Data classes
    "Snapshot",
    "SnapshotConfig",
    "SnapshotStats",
    # Core classes
    "SnapshotStore",
    "InMemorySnapshotStore",
    "SnapshotSerializer",
    "SnapshotManager",
    "SnapshotableAggregate",
    "SnapshotRepository",
    "PointInTimeRestore",
    # Decorators
    "snapshotable",
    "with_snapshots",
    # Factory functions
    "create_snapshot_store",
    "create_snapshot_manager",
    "create_snapshot_config",
]
