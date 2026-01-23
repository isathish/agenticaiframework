"""
Enterprise Event Store Module.

Provides event store abstraction, event persistence,
snapshots, and event sourcing support.

Example:
    # Create event store
    store = create_event_store()
    
    # Append events
    await store.append(
        stream_id="order-123",
        events=[OrderCreated(order_id="123")],
    )
    
    # Read events
    events = await store.read("order-123")
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
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
    Type,
    TypeVar,
)

T = TypeVar('T')
E = TypeVar('E', bound='DomainEvent')


logger = logging.getLogger(__name__)


class EventStoreError(Exception):
    """Event store error."""
    pass


class ConcurrencyError(EventStoreError):
    """Optimistic concurrency error."""
    pass


class StreamNotFoundError(EventStoreError):
    """Stream not found error."""
    pass


class EventReadDirection(str, Enum):
    """Event read direction."""
    FORWARD = "forward"
    BACKWARD = "backward"


class StreamState(str, Enum):
    """Stream state."""
    ACTIVE = "active"
    DELETED = "deleted"
    ARCHIVED = "archived"


@dataclass
class EventMetadata:
    """Event metadata."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    user_id: Optional[str] = None
    custom: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DomainEvent:
    """Base domain event."""
    event_type: str = ""
    
    def __post_init__(self):
        if not self.event_type:
            self.event_type = type(self).__name__


@dataclass
class RecordedEvent:
    """Recorded event with metadata."""
    stream_id: str
    event_number: int
    event_type: str
    data: Any
    metadata: EventMetadata
    global_position: int = 0
    
    @property
    def event_id(self) -> str:
        return self.metadata.event_id
    
    @property
    def timestamp(self) -> datetime:
        return self.metadata.timestamp


@dataclass
class StreamMetadata:
    """Stream metadata."""
    stream_id: str
    version: int = 0
    state: StreamState = StreamState.ACTIVE
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    custom: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EventSlice:
    """Slice of events from a stream."""
    events: List[RecordedEvent]
    from_version: int
    to_version: int
    is_end: bool = False
    next_version: Optional[int] = None


@dataclass
class AppendResult:
    """Result of appending events."""
    stream_id: str
    version: int
    events_count: int
    global_positions: List[int]


@dataclass
class Snapshot:
    """Aggregate snapshot."""
    stream_id: str
    version: int
    state: Any
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class EventSerializer(ABC):
    """
    Event serializer interface.
    """
    
    @abstractmethod
    def serialize(self, event: Any) -> bytes:
        """Serialize event to bytes."""
        pass
    
    @abstractmethod
    def deserialize(self, data: bytes, event_type: str) -> Any:
        """Deserialize bytes to event."""
        pass


class JsonEventSerializer(EventSerializer):
    """
    JSON event serializer.
    """
    
    def __init__(self):
        self._type_map: Dict[str, Type] = {}
    
    def register_type(self, event_type: str, cls: Type) -> None:
        """Register event type mapping."""
        self._type_map[event_type] = cls
    
    def serialize(self, event: Any) -> bytes:
        if hasattr(event, '__dict__'):
            data = event.__dict__.copy()
        else:
            data = event
        return json.dumps(data, default=str).encode('utf-8')
    
    def deserialize(self, data: bytes, event_type: str) -> Any:
        parsed = json.loads(data.decode('utf-8'))
        
        if event_type in self._type_map:
            cls = self._type_map[event_type]
            return cls(**parsed)
        
        return parsed


class EventStore(ABC):
    """
    Abstract event store.
    """
    
    @abstractmethod
    async def append(
        self,
        stream_id: str,
        events: List[Any],
        expected_version: Optional[int] = None,
        metadata: Optional[EventMetadata] = None,
    ) -> AppendResult:
        """Append events to a stream."""
        pass
    
    @abstractmethod
    async def read(
        self,
        stream_id: str,
        from_version: int = 0,
        max_count: int = 1000,
        direction: EventReadDirection = EventReadDirection.FORWARD,
    ) -> EventSlice:
        """Read events from a stream."""
        pass
    
    @abstractmethod
    async def read_all(
        self,
        from_position: int = 0,
        max_count: int = 1000,
        direction: EventReadDirection = EventReadDirection.FORWARD,
    ) -> EventSlice:
        """Read all events across streams."""
        pass
    
    @abstractmethod
    async def get_stream_metadata(
        self,
        stream_id: str,
    ) -> Optional[StreamMetadata]:
        """Get stream metadata."""
        pass
    
    @abstractmethod
    async def delete_stream(
        self,
        stream_id: str,
        expected_version: Optional[int] = None,
    ) -> None:
        """Delete a stream."""
        pass


class InMemoryEventStore(EventStore):
    """
    In-memory event store implementation.
    """
    
    def __init__(self, serializer: Optional[EventSerializer] = None):
        self._streams: Dict[str, List[RecordedEvent]] = defaultdict(list)
        self._metadata: Dict[str, StreamMetadata] = {}
        self._global_position = 0
        self._serializer = serializer or JsonEventSerializer()
        self._subscribers: List[Callable] = []
        self._lock = asyncio.Lock()
    
    async def append(
        self,
        stream_id: str,
        events: List[Any],
        expected_version: Optional[int] = None,
        metadata: Optional[EventMetadata] = None,
    ) -> AppendResult:
        async with self._lock:
            stream = self._streams[stream_id]
            current_version = len(stream)
            
            # Optimistic concurrency check
            if expected_version is not None:
                if expected_version != current_version:
                    raise ConcurrencyError(
                        f"Expected version {expected_version}, "
                        f"but stream is at version {current_version}"
                    )
            
            global_positions = []
            base_metadata = metadata or EventMetadata()
            
            for i, event in enumerate(events):
                self._global_position += 1
                
                event_metadata = EventMetadata(
                    event_id=str(uuid.uuid4()),
                    correlation_id=base_metadata.correlation_id,
                    causation_id=base_metadata.causation_id,
                    user_id=base_metadata.user_id,
                )
                
                event_type = (
                    event.event_type
                    if hasattr(event, 'event_type')
                    else type(event).__name__
                )
                
                recorded = RecordedEvent(
                    stream_id=stream_id,
                    event_number=current_version + i,
                    event_type=event_type,
                    data=event,
                    metadata=event_metadata,
                    global_position=self._global_position,
                )
                
                stream.append(recorded)
                global_positions.append(self._global_position)
            
            # Update stream metadata
            if stream_id not in self._metadata:
                self._metadata[stream_id] = StreamMetadata(
                    stream_id=stream_id,
                )
            
            self._metadata[stream_id].version = len(stream)
            self._metadata[stream_id].updated_at = datetime.now()
            
            # Notify subscribers
            for subscriber in self._subscribers:
                for recorded in stream[-len(events):]:
                    try:
                        if asyncio.iscoroutinefunction(subscriber):
                            await subscriber(recorded)
                        else:
                            subscriber(recorded)
                    except Exception as e:
                        logger.error(f"Subscriber error: {e}")
            
            return AppendResult(
                stream_id=stream_id,
                version=len(stream),
                events_count=len(events),
                global_positions=global_positions,
            )
    
    async def read(
        self,
        stream_id: str,
        from_version: int = 0,
        max_count: int = 1000,
        direction: EventReadDirection = EventReadDirection.FORWARD,
    ) -> EventSlice:
        stream = self._streams.get(stream_id, [])
        
        if direction == EventReadDirection.FORWARD:
            events = stream[from_version:from_version + max_count]
            to_version = from_version + len(events) - 1 if events else from_version
            is_end = from_version + max_count >= len(stream)
            next_version = (
                from_version + len(events)
                if not is_end
                else None
            )
        else:
            start = max(0, from_version - max_count + 1)
            events = list(reversed(stream[start:from_version + 1]))
            to_version = start
            is_end = start == 0
            next_version = start - 1 if not is_end else None
        
        return EventSlice(
            events=events,
            from_version=from_version,
            to_version=to_version,
            is_end=is_end,
            next_version=next_version,
        )
    
    async def read_all(
        self,
        from_position: int = 0,
        max_count: int = 1000,
        direction: EventReadDirection = EventReadDirection.FORWARD,
    ) -> EventSlice:
        # Collect all events across streams
        all_events: List[RecordedEvent] = []
        for events in self._streams.values():
            all_events.extend(events)
        
        # Sort by global position
        all_events.sort(key=lambda e: e.global_position)
        
        if direction == EventReadDirection.FORWARD:
            filtered = [
                e for e in all_events
                if e.global_position >= from_position
            ][:max_count]
        else:
            filtered = [
                e for e in all_events
                if e.global_position <= from_position
            ][-max_count:]
            filtered.reverse()
        
        return EventSlice(
            events=filtered,
            from_version=from_position,
            to_version=(
                filtered[-1].global_position
                if filtered
                else from_position
            ),
            is_end=len(filtered) < max_count,
        )
    
    async def get_stream_metadata(
        self,
        stream_id: str,
    ) -> Optional[StreamMetadata]:
        return self._metadata.get(stream_id)
    
    async def delete_stream(
        self,
        stream_id: str,
        expected_version: Optional[int] = None,
    ) -> None:
        if stream_id not in self._streams:
            return
        
        if expected_version is not None:
            current_version = len(self._streams[stream_id])
            if expected_version != current_version:
                raise ConcurrencyError(
                    f"Expected version {expected_version}, "
                    f"but stream is at version {current_version}"
                )
        
        if stream_id in self._metadata:
            self._metadata[stream_id].state = StreamState.DELETED
        
        del self._streams[stream_id]
    
    def subscribe(
        self,
        handler: Callable[[RecordedEvent], Any],
    ) -> Callable[[], None]:
        """Subscribe to new events."""
        self._subscribers.append(handler)
        
        def unsubscribe():
            self._subscribers.remove(handler)
        
        return unsubscribe


class SnapshotStore(ABC):
    """
    Abstract snapshot store.
    """
    
    @abstractmethod
    async def save(self, snapshot: Snapshot) -> None:
        """Save a snapshot."""
        pass
    
    @abstractmethod
    async def load(
        self,
        stream_id: str,
        max_version: Optional[int] = None,
    ) -> Optional[Snapshot]:
        """Load a snapshot."""
        pass
    
    @abstractmethod
    async def delete(self, stream_id: str) -> None:
        """Delete snapshots for a stream."""
        pass


class InMemorySnapshotStore(SnapshotStore):
    """
    In-memory snapshot store.
    """
    
    def __init__(self):
        self._snapshots: Dict[str, List[Snapshot]] = defaultdict(list)
    
    async def save(self, snapshot: Snapshot) -> None:
        self._snapshots[snapshot.stream_id].append(snapshot)
        # Keep only latest N snapshots
        self._snapshots[snapshot.stream_id] = (
            self._snapshots[snapshot.stream_id][-10:]
        )
    
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
            return valid[-1] if valid else None
        
        return snapshots[-1]
    
    async def delete(self, stream_id: str) -> None:
        self._snapshots.pop(stream_id, None)


class EventStreamReader:
    """
    Helper for reading event streams.
    """
    
    def __init__(
        self,
        store: EventStore,
        stream_id: str,
    ):
        self._store = store
        self._stream_id = stream_id
    
    async def read_all(self) -> List[RecordedEvent]:
        """Read all events from stream."""
        events = []
        version = 0
        
        while True:
            slice = await self._store.read(
                self._stream_id,
                from_version=version,
            )
            events.extend(slice.events)
            
            if slice.is_end:
                break
            
            version = slice.next_version or 0
        
        return events
    
    async def __aiter__(self) -> AsyncIterator[RecordedEvent]:
        """Iterate over events."""
        version = 0
        
        while True:
            slice = await self._store.read(
                self._stream_id,
                from_version=version,
            )
            
            for event in slice.events:
                yield event
            
            if slice.is_end:
                break
            
            version = slice.next_version or 0


class EventSourcedRepository(Generic[T]):
    """
    Repository for event-sourced aggregates.
    """
    
    def __init__(
        self,
        event_store: EventStore,
        snapshot_store: Optional[SnapshotStore] = None,
        snapshot_interval: int = 100,
    ):
        self._event_store = event_store
        self._snapshot_store = snapshot_store
        self._snapshot_interval = snapshot_interval
        self._factory: Optional[Callable[[], T]] = None
        self._apply_map: Dict[str, Callable[[T, Any], None]] = {}
    
    def set_factory(self, factory: Callable[[], T]) -> None:
        """Set aggregate factory."""
        self._factory = factory
    
    def register_apply(
        self,
        event_type: str,
        handler: Callable[[T, Any], None],
    ) -> None:
        """Register event apply handler."""
        self._apply_map[event_type] = handler
    
    async def load(self, stream_id: str) -> Optional[T]:
        """Load aggregate from events."""
        if not self._factory:
            raise EventStoreError("No factory registered")
        
        # Try to load from snapshot
        snapshot = None
        from_version = 0
        
        if self._snapshot_store:
            snapshot = await self._snapshot_store.load(stream_id)
            if snapshot:
                aggregate = snapshot.state
                from_version = snapshot.version
            else:
                aggregate = self._factory()
        else:
            aggregate = self._factory()
        
        # Apply events
        slice = await self._event_store.read(
            stream_id,
            from_version=from_version,
        )
        
        if not slice.events and not snapshot:
            return None
        
        for event in slice.events:
            handler = self._apply_map.get(event.event_type)
            if handler:
                handler(aggregate, event.data)
        
        return aggregate
    
    async def save(
        self,
        stream_id: str,
        aggregate: T,
        events: List[Any],
        expected_version: Optional[int] = None,
    ) -> AppendResult:
        """Save aggregate with new events."""
        result = await self._event_store.append(
            stream_id,
            events,
            expected_version=expected_version,
        )
        
        # Create snapshot if needed
        if (
            self._snapshot_store
            and result.version % self._snapshot_interval == 0
        ):
            snapshot = Snapshot(
                stream_id=stream_id,
                version=result.version,
                state=aggregate,
            )
            await self._snapshot_store.save(snapshot)
        
        return result


class Subscription:
    """
    Event subscription for catching up with events.
    """
    
    def __init__(
        self,
        store: EventStore,
        handler: Callable[[RecordedEvent], Any],
        from_position: int = 0,
    ):
        self._store = store
        self._handler = handler
        self._position = from_position
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    async def start(self) -> None:
        """Start subscription."""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._run())
    
    async def stop(self) -> None:
        """Stop subscription."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
    
    async def _run(self) -> None:
        """Run subscription loop."""
        while self._running:
            try:
                slice = await self._store.read_all(
                    from_position=self._position,
                    max_count=100,
                )
                
                for event in slice.events:
                    try:
                        if asyncio.iscoroutinefunction(self._handler):
                            await self._handler(event)
                        else:
                            self._handler(event)
                        self._position = event.global_position + 1
                    except Exception as e:
                        logger.error(f"Subscription handler error: {e}")
                
                if slice.is_end:
                    await asyncio.sleep(0.1)
                    
            except Exception as e:
                logger.error(f"Subscription error: {e}")
                await asyncio.sleep(1.0)
    
    @property
    def position(self) -> int:
        """Get current position."""
        return self._position


class EventStoreRegistry:
    """
    Registry for event stores.
    """
    
    def __init__(self):
        self._stores: Dict[str, EventStore] = {}
        self._default: Optional[str] = None
    
    def register(
        self,
        name: str,
        store: EventStore,
        default: bool = False,
    ) -> None:
        """Register an event store."""
        self._stores[name] = store
        if default or self._default is None:
            self._default = name
    
    def get(self, name: Optional[str] = None) -> EventStore:
        """Get an event store."""
        name = name or self._default
        if not name or name not in self._stores:
            raise EventStoreError(f"Event store not found: {name}")
        return self._stores[name]


# Global registry
_global_registry = EventStoreRegistry()


# Decorators
def event_type(type_name: str) -> Callable:
    """
    Decorator to specify event type name.
    
    Example:
        @event_type("OrderCreated")
        class OrderCreated:
            order_id: str
    """
    def decorator(cls: Type) -> Type:
        cls.event_type = type_name
        return cls
    
    return decorator


def applies(event_type: str) -> Callable:
    """
    Decorator for event apply handlers.
    
    Example:
        @applies("OrderCreated")
        def apply_order_created(self, event):
            self.status = "created"
    """
    def decorator(func: Callable) -> Callable:
        func._applies_event_type = event_type
        return func
    
    return decorator


# Factory functions
def create_event_store() -> InMemoryEventStore:
    """Create an in-memory event store."""
    return InMemoryEventStore()


def create_snapshot_store() -> InMemorySnapshotStore:
    """Create an in-memory snapshot store."""
    return InMemorySnapshotStore()


def create_event_serializer() -> JsonEventSerializer:
    """Create a JSON event serializer."""
    return JsonEventSerializer()


def create_event_sourced_repository(
    event_store: Optional[EventStore] = None,
    snapshot_store: Optional[SnapshotStore] = None,
) -> EventSourcedRepository:
    """Create an event-sourced repository."""
    return EventSourcedRepository(
        event_store=event_store or create_event_store(),
        snapshot_store=snapshot_store,
    )


def create_subscription(
    store: EventStore,
    handler: Callable[[RecordedEvent], Any],
    from_position: int = 0,
) -> Subscription:
    """Create an event subscription."""
    return Subscription(store, handler, from_position)


def create_stream_reader(
    store: EventStore,
    stream_id: str,
) -> EventStreamReader:
    """Create a stream reader."""
    return EventStreamReader(store, stream_id)


def register_store(
    name: str,
    store: EventStore,
    default: bool = False,
) -> None:
    """Register store in global registry."""
    _global_registry.register(name, store, default)


def get_store(name: Optional[str] = None) -> EventStore:
    """Get store from global registry."""
    return _global_registry.get(name)


__all__ = [
    # Exceptions
    "EventStoreError",
    "ConcurrencyError",
    "StreamNotFoundError",
    # Enums
    "EventReadDirection",
    "StreamState",
    # Data classes
    "EventMetadata",
    "DomainEvent",
    "RecordedEvent",
    "StreamMetadata",
    "EventSlice",
    "AppendResult",
    "Snapshot",
    # Serializers
    "EventSerializer",
    "JsonEventSerializer",
    # Event Store
    "EventStore",
    "InMemoryEventStore",
    # Snapshot Store
    "SnapshotStore",
    "InMemorySnapshotStore",
    # Utilities
    "EventStreamReader",
    "EventSourcedRepository",
    "Subscription",
    # Registry
    "EventStoreRegistry",
    # Decorators
    "event_type",
    "applies",
    # Factory functions
    "create_event_store",
    "create_snapshot_store",
    "create_event_serializer",
    "create_event_sourced_repository",
    "create_subscription",
    "create_stream_reader",
    "register_store",
    "get_store",
]
