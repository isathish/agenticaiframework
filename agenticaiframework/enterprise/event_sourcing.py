"""
Enterprise Event Sourcing Module.

Provides event sourcing patterns, event store, event replay,
and snapshot management for building event-driven systems.

Example:
    # Create event store
    store = create_event_store()
    
    # Append events
    await store.append("order-123", [
        OrderCreated(order_id="123", amount=100),
        OrderPaid(order_id="123"),
    ])
    
    # Load events
    events = await store.load("order-123")
    
    # Replay to rebuild state
    state = await replay(events, Order())
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Generic,
    Iterator,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
)

logger = logging.getLogger(__name__)

T = TypeVar('T')
E = TypeVar('E', bound='Event')
S = TypeVar('S', bound='AggregateRoot')


class EventSourcingError(Exception):
    """Event sourcing error."""
    pass


class StreamNotFoundError(EventSourcingError):
    """Stream not found."""
    pass


class ConcurrencyError(EventSourcingError):
    """Concurrency conflict."""
    pass


class EventValidationError(EventSourcingError):
    """Event validation failed."""
    pass


class StreamState(str, Enum):
    """Stream state."""
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


@dataclass
class EventMetadata:
    """Event metadata."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    version: int = 0
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    user_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Event:
    """Base event class."""
    _metadata: EventMetadata = field(default_factory=EventMetadata)
    
    @property
    def event_type(self) -> str:
        return self.__class__.__name__
    
    @property
    def event_id(self) -> str:
        return self._metadata.event_id
    
    @property
    def timestamp(self) -> datetime:
        return self._metadata.timestamp
    
    @property
    def version(self) -> int:
        return self._metadata.version
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = {}
        for key, value in self.__dict__.items():
            if key.startswith('_'):
                continue
            data[key] = value
        return data


@dataclass
class StoredEvent:
    """Stored event wrapper."""
    stream_id: str
    event_id: str
    event_type: str
    event_data: Dict[str, Any]
    metadata: EventMetadata
    global_position: int = 0
    stream_position: int = 0
    checksum: Optional[str] = None


@dataclass
class StreamInfo:
    """Stream information."""
    stream_id: str
    version: int = 0
    event_count: int = 0
    state: StreamState = StreamState.ACTIVE
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Snapshot:
    """Aggregate snapshot."""
    stream_id: str
    snapshot_id: str
    version: int
    state: Dict[str, Any]
    aggregate_type: str
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class EventStore(ABC):
    """Abstract event store."""
    
    @abstractmethod
    async def append(
        self,
        stream_id: str,
        events: List[Event],
        expected_version: Optional[int] = None,
    ) -> int:
        """Append events to stream."""
        pass
    
    @abstractmethod
    async def load(
        self,
        stream_id: str,
        from_version: int = 0,
        to_version: Optional[int] = None,
    ) -> List[StoredEvent]:
        """Load events from stream."""
        pass
    
    @abstractmethod
    async def load_all(
        self,
        from_position: int = 0,
        batch_size: int = 100,
    ) -> List[StoredEvent]:
        """Load all events."""
        pass
    
    @abstractmethod
    async def get_stream_info(
        self,
        stream_id: str,
    ) -> Optional[StreamInfo]:
        """Get stream information."""
        pass


class InMemoryEventStore(EventStore):
    """In-memory event store."""
    
    def __init__(self):
        self._streams: Dict[str, List[StoredEvent]] = {}
        self._all_events: List[StoredEvent] = []
        self._stream_info: Dict[str, StreamInfo] = {}
        self._lock = asyncio.Lock()
        self._global_position = 0
    
    async def append(
        self,
        stream_id: str,
        events: List[Event],
        expected_version: Optional[int] = None,
    ) -> int:
        async with self._lock:
            # Get or create stream
            if stream_id not in self._streams:
                self._streams[stream_id] = []
                self._stream_info[stream_id] = StreamInfo(stream_id=stream_id)
            
            stream = self._streams[stream_id]
            info = self._stream_info[stream_id]
            current_version = info.version
            
            # Check expected version
            if expected_version is not None and current_version != expected_version:
                raise ConcurrencyError(
                    f"Expected version {expected_version}, "
                    f"but current is {current_version}"
                )
            
            # Append events
            for event in events:
                current_version += 1
                self._global_position += 1
                
                event._metadata.version = current_version
                
                # Create checksum
                event_data = event.to_dict()
                checksum = hashlib.sha256(
                    json.dumps(event_data, sort_keys=True, default=str).encode()
                ).hexdigest()[:16]
                
                stored = StoredEvent(
                    stream_id=stream_id,
                    event_id=event.event_id,
                    event_type=event.event_type,
                    event_data=event_data,
                    metadata=event._metadata,
                    global_position=self._global_position,
                    stream_position=current_version,
                    checksum=checksum,
                )
                
                stream.append(stored)
                self._all_events.append(stored)
            
            # Update stream info
            info.version = current_version
            info.event_count = len(stream)
            info.updated_at = datetime.now()
            
            return current_version
    
    async def load(
        self,
        stream_id: str,
        from_version: int = 0,
        to_version: Optional[int] = None,
    ) -> List[StoredEvent]:
        stream = self._streams.get(stream_id, [])
        
        events = [
            e for e in stream
            if e.stream_position > from_version
            and (to_version is None or e.stream_position <= to_version)
        ]
        
        return events
    
    async def load_all(
        self,
        from_position: int = 0,
        batch_size: int = 100,
    ) -> List[StoredEvent]:
        events = [
            e for e in self._all_events
            if e.global_position > from_position
        ]
        
        return events[:batch_size]
    
    async def get_stream_info(
        self,
        stream_id: str,
    ) -> Optional[StreamInfo]:
        return self._stream_info.get(stream_id)


class SnapshotStore(ABC):
    """Abstract snapshot store."""
    
    @abstractmethod
    async def save(self, snapshot: Snapshot) -> None:
        """Save snapshot."""
        pass
    
    @abstractmethod
    async def load(
        self,
        stream_id: str,
        max_version: Optional[int] = None,
    ) -> Optional[Snapshot]:
        """Load latest snapshot."""
        pass
    
    @abstractmethod
    async def delete(self, stream_id: str) -> None:
        """Delete snapshots."""
        pass


class InMemorySnapshotStore(SnapshotStore):
    """In-memory snapshot store."""
    
    def __init__(self):
        self._snapshots: Dict[str, List[Snapshot]] = {}
        self._lock = asyncio.Lock()
    
    async def save(self, snapshot: Snapshot) -> None:
        async with self._lock:
            if snapshot.stream_id not in self._snapshots:
                self._snapshots[snapshot.stream_id] = []
            
            self._snapshots[snapshot.stream_id].append(snapshot)
    
    async def load(
        self,
        stream_id: str,
        max_version: Optional[int] = None,
    ) -> Optional[Snapshot]:
        snapshots = self._snapshots.get(stream_id, [])
        
        if not snapshots:
            return None
        
        if max_version is not None:
            valid = [s for s in snapshots if s.version <= max_version]
            if not valid:
                return None
            return max(valid, key=lambda s: s.version)
        
        return max(snapshots, key=lambda s: s.version)
    
    async def delete(self, stream_id: str) -> None:
        async with self._lock:
            self._snapshots.pop(stream_id, None)


class AggregateRoot(ABC):
    """Base aggregate root class."""
    
    def __init__(self):
        self._version: int = 0
        self._pending_events: List[Event] = []
    
    @property
    def version(self) -> int:
        return self._version
    
    @abstractmethod
    def apply(self, event: Event) -> None:
        """Apply event to state."""
        pass
    
    def raise_event(self, event: Event) -> None:
        """Raise a new domain event."""
        self.apply(event)
        self._pending_events.append(event)
    
    def load_from_events(self, events: List[StoredEvent]) -> None:
        """Load state from events."""
        for stored in events:
            # Reconstruct event (simplified)
            event = Event()
            event._metadata = stored.metadata
            self.apply(event)
            self._version = stored.stream_position
    
    def get_pending_events(self) -> List[Event]:
        """Get pending events."""
        return self._pending_events.copy()
    
    def clear_pending_events(self) -> None:
        """Clear pending events."""
        self._pending_events.clear()
    
    def to_snapshot(self) -> Dict[str, Any]:
        """Convert to snapshot state."""
        return {}
    
    def from_snapshot(self, state: Dict[str, Any]) -> None:
        """Restore from snapshot state."""
        pass


class EventPublisher(ABC):
    """Abstract event publisher."""
    
    @abstractmethod
    async def publish(
        self,
        event: StoredEvent,
    ) -> None:
        """Publish event."""
        pass


class InMemoryEventPublisher(EventPublisher):
    """In-memory event publisher."""
    
    def __init__(self):
        self._handlers: Dict[str, List[Callable]] = {}
        self._all_handlers: List[Callable] = []
    
    def subscribe(
        self,
        event_type: str,
        handler: Callable[[StoredEvent], Awaitable[None]],
    ) -> None:
        """Subscribe to event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        
        self._handlers[event_type].append(handler)
    
    def subscribe_all(
        self,
        handler: Callable[[StoredEvent], Awaitable[None]],
    ) -> None:
        """Subscribe to all events."""
        self._all_handlers.append(handler)
    
    async def publish(self, event: StoredEvent) -> None:
        """Publish event to subscribers."""
        # Type-specific handlers
        handlers = self._handlers.get(event.event_type, [])
        for handler in handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(f"Handler error: {e}")
        
        # All event handlers
        for handler in self._all_handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(f"Handler error: {e}")


class EventProcessor:
    """
    Event processor for replaying and projecting.
    """
    
    def __init__(
        self,
        event_store: EventStore,
        publisher: Optional[EventPublisher] = None,
    ):
        self._store = event_store
        self._publisher = publisher or InMemoryEventPublisher()
    
    async def replay(
        self,
        stream_id: str,
        aggregate: AggregateRoot,
        to_version: Optional[int] = None,
    ) -> AggregateRoot:
        """Replay events to rebuild aggregate state."""
        events = await self._store.load(
            stream_id,
            from_version=aggregate.version,
            to_version=to_version,
        )
        
        aggregate.load_from_events(events)
        
        return aggregate
    
    async def replay_all(
        self,
        handler: Callable[[StoredEvent], Awaitable[None]],
        from_position: int = 0,
        batch_size: int = 100,
    ) -> int:
        """Replay all events."""
        position = from_position
        processed = 0
        
        while True:
            events = await self._store.load_all(
                from_position=position,
                batch_size=batch_size,
            )
            
            if not events:
                break
            
            for event in events:
                await handler(event)
                position = event.global_position
                processed += 1
        
        return processed


class Repository(Generic[S]):
    """
    Event-sourced repository.
    """
    
    def __init__(
        self,
        aggregate_type: Type[S],
        event_store: EventStore,
        snapshot_store: Optional[SnapshotStore] = None,
        publisher: Optional[EventPublisher] = None,
        snapshot_interval: int = 100,
    ):
        self._aggregate_type = aggregate_type
        self._store = event_store
        self._snapshots = snapshot_store or InMemorySnapshotStore()
        self._publisher = publisher or InMemoryEventPublisher()
        self._snapshot_interval = snapshot_interval
    
    async def load(
        self,
        stream_id: str,
    ) -> Optional[S]:
        """Load aggregate from events."""
        info = await self._store.get_stream_info(stream_id)
        
        if not info:
            return None
        
        aggregate = self._aggregate_type()
        
        # Try to load from snapshot
        snapshot = await self._snapshots.load(stream_id)
        
        if snapshot:
            aggregate.from_snapshot(snapshot.state)
            aggregate._version = snapshot.version
        
        # Load remaining events
        events = await self._store.load(
            stream_id,
            from_version=aggregate.version,
        )
        
        aggregate.load_from_events(events)
        
        return aggregate
    
    async def save(
        self,
        stream_id: str,
        aggregate: S,
    ) -> None:
        """Save aggregate events."""
        pending = aggregate.get_pending_events()
        
        if not pending:
            return
        
        # Append events
        new_version = await self._store.append(
            stream_id,
            pending,
            expected_version=aggregate.version,
        )
        
        aggregate._version = new_version
        aggregate.clear_pending_events()
        
        # Publish events
        events = await self._store.load(
            stream_id,
            from_version=new_version - len(pending),
            to_version=new_version,
        )
        
        for event in events:
            await self._publisher.publish(event)
        
        # Create snapshot if needed
        if new_version % self._snapshot_interval == 0:
            await self._create_snapshot(stream_id, aggregate)
    
    async def _create_snapshot(
        self,
        stream_id: str,
        aggregate: S,
    ) -> None:
        """Create a snapshot."""
        snapshot = Snapshot(
            stream_id=stream_id,
            snapshot_id=str(uuid.uuid4()),
            version=aggregate.version,
            state=aggregate.to_snapshot(),
            aggregate_type=aggregate.__class__.__name__,
        )
        
        await self._snapshots.save(snapshot)
        logger.debug(f"Created snapshot for {stream_id} at version {aggregate.version}")


class Projector(ABC):
    """Abstract projector for building read models."""
    
    @abstractmethod
    async def project(self, event: StoredEvent) -> None:
        """Project event to read model."""
        pass
    
    @abstractmethod
    async def get_position(self) -> int:
        """Get current projection position."""
        pass
    
    @abstractmethod
    async def set_position(self, position: int) -> None:
        """Set projection position."""
        pass


class InMemoryProjector(Projector):
    """Base in-memory projector."""
    
    def __init__(self):
        self._position = 0
        self._handlers: Dict[str, Callable] = {}
    
    def when(
        self,
        event_type: str,
        handler: Callable[[StoredEvent], Awaitable[None]],
    ) -> "InMemoryProjector":
        """Register event handler."""
        self._handlers[event_type] = handler
        return self
    
    async def project(self, event: StoredEvent) -> None:
        handler = self._handlers.get(event.event_type)
        
        if handler:
            await handler(event)
        
        self._position = event.global_position
    
    async def get_position(self) -> int:
        return self._position
    
    async def set_position(self, position: int) -> None:
        self._position = position


class ProjectionManager:
    """
    Manages multiple projections.
    """
    
    def __init__(
        self,
        event_store: EventStore,
    ):
        self._store = event_store
        self._projectors: Dict[str, Projector] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    def register(
        self,
        name: str,
        projector: Projector,
    ) -> None:
        """Register a projector."""
        self._projectors[name] = projector
    
    async def start(
        self,
        poll_interval: float = 1.0,
    ) -> None:
        """Start projection processing."""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(
            self._process_loop(poll_interval)
        )
    
    async def stop(self) -> None:
        """Stop projection processing."""
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
    
    async def _process_loop(
        self,
        poll_interval: float,
    ) -> None:
        """Event processing loop."""
        while self._running:
            try:
                for name, projector in self._projectors.items():
                    position = await projector.get_position()
                    events = await self._store.load_all(
                        from_position=position,
                        batch_size=100,
                    )
                    
                    for event in events:
                        try:
                            await projector.project(event)
                        except Exception as e:
                            logger.error(
                                f"Projection error in {name}: {e}"
                            )
                
                await asyncio.sleep(poll_interval)
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Process loop error: {e}")
                await asyncio.sleep(poll_interval)
    
    async def rebuild(
        self,
        projector_name: str,
    ) -> int:
        """Rebuild a projection from scratch."""
        projector = self._projectors.get(projector_name)
        
        if not projector:
            return 0
        
        await projector.set_position(0)
        
        processed = 0
        position = 0
        
        while True:
            events = await self._store.load_all(
                from_position=position,
                batch_size=100,
            )
            
            if not events:
                break
            
            for event in events:
                await projector.project(event)
                position = event.global_position
                processed += 1
        
        return processed


# Decorators
def event_handler(
    event_type: str,
) -> Callable:
    """
    Decorator to mark event handler.
    
    Example:
        @event_handler("OrderCreated")
        async def handle_order_created(event):
            ...
    """
    def decorator(func: Callable) -> Callable:
        func._event_type = event_type
        return func
    
    return decorator


def sourced(
    stream_id_arg: str = "stream_id",
    aggregate_type: Optional[Type[AggregateRoot]] = None,
) -> Callable:
    """
    Decorator for event-sourced operations.
    
    Example:
        @sourced("order_id", Order)
        async def create_order(order_id: str, order: Order):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return await func(*args, **kwargs)
        
        wrapper._sourced = True
        wrapper._stream_id_arg = stream_id_arg
        wrapper._aggregate_type = aggregate_type
        
        return wrapper
    
    return decorator


# Factory functions
def create_event_store() -> EventStore:
    """Create an event store."""
    return InMemoryEventStore()


def create_snapshot_store() -> SnapshotStore:
    """Create a snapshot store."""
    return InMemorySnapshotStore()


def create_event_publisher() -> InMemoryEventPublisher:
    """Create an event publisher."""
    return InMemoryEventPublisher()


def create_repository(
    aggregate_type: Type[S],
    event_store: Optional[EventStore] = None,
    snapshot_store: Optional[SnapshotStore] = None,
    snapshot_interval: int = 100,
) -> Repository[S]:
    """Create a repository."""
    return Repository(
        aggregate_type,
        event_store or InMemoryEventStore(),
        snapshot_store,
        snapshot_interval=snapshot_interval,
    )


def create_projector() -> InMemoryProjector:
    """Create a projector."""
    return InMemoryProjector()


def create_projection_manager(
    event_store: Optional[EventStore] = None,
) -> ProjectionManager:
    """Create a projection manager."""
    return ProjectionManager(event_store or InMemoryEventStore())


__all__ = [
    # Exceptions
    "EventSourcingError",
    "StreamNotFoundError",
    "ConcurrencyError",
    "EventValidationError",
    # Enums
    "StreamState",
    # Data classes
    "EventMetadata",
    "Event",
    "StoredEvent",
    "StreamInfo",
    "Snapshot",
    # Abstract classes
    "EventStore",
    "SnapshotStore",
    "AggregateRoot",
    "EventPublisher",
    "Projector",
    # Implementations
    "InMemoryEventStore",
    "InMemorySnapshotStore",
    "InMemoryEventPublisher",
    "InMemoryProjector",
    # Core classes
    "EventProcessor",
    "Repository",
    "ProjectionManager",
    # Decorators
    "event_handler",
    "sourced",
    # Factory functions
    "create_event_store",
    "create_snapshot_store",
    "create_event_publisher",
    "create_repository",
    "create_projector",
    "create_projection_manager",
]
