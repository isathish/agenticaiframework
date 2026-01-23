"""
Enterprise Projection Module.

Provides event projections, read models, and materialized
views for CQRS/Event Sourcing patterns.

Example:
    # Define a projection
    class OrderSummaryProjection(Projection):
        def __init__(self):
            self.orders = {}
        
        @handles(OrderCreatedEvent)
        def on_order_created(self, event: OrderCreatedEvent):
            self.orders[event.order_id] = {"status": "created"}
        
        @handles(OrderShippedEvent)
        def on_order_shipped(self, event: OrderShippedEvent):
            self.orders[event.order_id]["status"] = "shipped"
    
    # Run projector
    projector = create_projector(event_store)
    projector.register(OrderSummaryProjection())
    await projector.run()
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
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
    Type,
    TypeVar,
)

logger = logging.getLogger(__name__)

T = TypeVar('T')
TEvent = TypeVar('TEvent')


class ProjectionError(Exception):
    """Projection error."""
    pass


class ProjectionNotFoundError(ProjectionError):
    """Projection not found."""
    pass


class ProjectionStatus(str, Enum):
    """Projection status."""
    STOPPED = "stopped"
    RUNNING = "running"
    CATCHING_UP = "catching_up"
    LIVE = "live"
    ERROR = "error"


@dataclass
class ProjectionPosition:
    """Tracks projection position in event stream."""
    projection_name: str
    last_sequence: int = 0
    last_processed_at: Optional[datetime] = None
    events_processed: int = 0


@dataclass
class ProjectionStats:
    """Projection statistics."""
    projection_name: str
    status: ProjectionStatus
    position: int = 0
    events_processed: int = 0
    errors: int = 0
    last_event_at: Optional[datetime] = None
    lag: int = 0  # Events behind


class EventEnvelope:
    """Envelope wrapping an event with metadata."""
    
    def __init__(
        self,
        event: Any,
        sequence: int,
        stream_id: str,
        timestamp: Optional[datetime] = None,
    ):
        self.event = event
        self.sequence = sequence
        self.stream_id = stream_id
        self.timestamp = timestamp or datetime.now()
    
    @property
    def event_type(self) -> str:
        """Get event type name."""
        return type(self.event).__name__


class EventStore(ABC):
    """Abstract event store interface for projections."""
    
    @abstractmethod
    async def get_all_events(
        self,
        from_sequence: int = 0,
        batch_size: int = 100,
    ) -> List[EventEnvelope]:
        """Get all events from sequence."""
        pass
    
    @abstractmethod
    async def get_latest_sequence(self) -> int:
        """Get latest event sequence number."""
        pass


class InMemoryEventStore(EventStore):
    """Simple in-memory event store."""
    
    def __init__(self):
        self._events: List[EventEnvelope] = []
        self._sequence = 0
    
    async def append(
        self,
        event: Any,
        stream_id: str,
    ) -> int:
        """Append an event."""
        self._sequence += 1
        envelope = EventEnvelope(
            event=event,
            sequence=self._sequence,
            stream_id=stream_id,
        )
        self._events.append(envelope)
        return self._sequence
    
    async def get_all_events(
        self,
        from_sequence: int = 0,
        batch_size: int = 100,
    ) -> List[EventEnvelope]:
        """Get events from sequence."""
        events = [
            e for e in self._events
            if e.sequence > from_sequence
        ]
        return events[:batch_size]
    
    async def get_latest_sequence(self) -> int:
        """Get latest sequence."""
        return self._sequence


class Projection(ABC):
    """
    Base class for projections.
    
    Projections transform events into read models.
    """
    
    def __init__(self):
        self._handlers: Dict[str, Callable] = {}
        self._name = type(self).__name__
        self._register_handlers()
    
    @property
    def name(self) -> str:
        """Get projection name."""
        return self._name
    
    def _register_handlers(self) -> None:
        """Register event handlers from decorated methods."""
        for name in dir(self):
            method = getattr(self, name)
            if hasattr(method, "_handles_event"):
                event_type = method._handles_event
                if isinstance(event_type, type):
                    event_name = event_type.__name__
                else:
                    event_name = str(event_type)
                self._handlers[event_name] = method
    
    def handles(self, event_type: str) -> bool:
        """Check if projection handles event type."""
        return event_type in self._handlers
    
    async def apply(self, event: Any) -> None:
        """Apply an event to the projection."""
        event_type = type(event).__name__
        handler = self._handlers.get(event_type)
        
        if handler:
            if asyncio.iscoroutinefunction(handler):
                await handler(event)
            else:
                handler(event)
    
    def reset(self) -> None:
        """Reset projection state (for rebuilding)."""
        pass


class ReadModel(ABC):
    """
    Abstract base for read models.
    """
    
    @abstractmethod
    def get_state(self) -> Dict[str, Any]:
        """Get current state."""
        pass


class MaterializedView(Projection, ReadModel):
    """
    Materialized view combining projection and read model.
    """
    
    def __init__(self):
        super().__init__()
        self._state: Dict[str, Any] = {}
    
    def get_state(self) -> Dict[str, Any]:
        """Get current state."""
        return self._state.copy()
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get value by key."""
        return self._state.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set value by key."""
        self._state[key] = value
    
    def delete(self, key: str) -> None:
        """Delete value by key."""
        self._state.pop(key, None)
    
    def reset(self) -> None:
        """Reset state."""
        self._state.clear()


class PositionStore(ABC):
    """Abstract store for projection positions."""
    
    @abstractmethod
    async def get_position(
        self,
        projection_name: str,
    ) -> ProjectionPosition:
        """Get projection position."""
        pass
    
    @abstractmethod
    async def save_position(
        self,
        position: ProjectionPosition,
    ) -> None:
        """Save projection position."""
        pass


class InMemoryPositionStore(PositionStore):
    """In-memory position store."""
    
    def __init__(self):
        self._positions: Dict[str, ProjectionPosition] = {}
    
    async def get_position(
        self,
        projection_name: str,
    ) -> ProjectionPosition:
        return self._positions.get(
            projection_name,
            ProjectionPosition(projection_name),
        )
    
    async def save_position(
        self,
        position: ProjectionPosition,
    ) -> None:
        self._positions[position.projection_name] = position


class Projector:
    """
    Runs projections against event stream.
    """
    
    def __init__(
        self,
        event_store: EventStore,
        position_store: Optional[PositionStore] = None,
        batch_size: int = 100,
        poll_interval: float = 1.0,
    ):
        self._event_store = event_store
        self._position_store = position_store or InMemoryPositionStore()
        self._batch_size = batch_size
        self._poll_interval = poll_interval
        self._projections: Dict[str, Projection] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._stats: Dict[str, ProjectionStats] = {}
    
    def register(self, projection: Projection) -> 'Projector':
        """Register a projection."""
        self._projections[projection.name] = projection
        self._stats[projection.name] = ProjectionStats(
            projection_name=projection.name,
            status=ProjectionStatus.STOPPED,
        )
        return self
    
    def unregister(self, projection_name: str) -> bool:
        """Unregister a projection."""
        if projection_name in self._projections:
            del self._projections[projection_name]
            del self._stats[projection_name]
            return True
        return False
    
    async def start(self) -> None:
        """Start the projector."""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        
        logger.info("Projector started")
    
    async def stop(self) -> None:
        """Stop the projector."""
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        logger.info("Projector stopped")
    
    async def _run_loop(self) -> None:
        """Main processing loop."""
        while self._running:
            try:
                processed = await self._process_batch()
                
                if processed == 0:
                    # No events, wait before polling again
                    await asyncio.sleep(self._poll_interval)
            
            except asyncio.CancelledError:
                break
            
            except Exception as e:
                logger.error(f"Projector error: {e}")
                await asyncio.sleep(self._poll_interval)
    
    async def _process_batch(self) -> int:
        """Process a batch of events for all projections."""
        total_processed = 0
        
        for projection in self._projections.values():
            processed = await self._process_projection(projection)
            total_processed += processed
        
        return total_processed
    
    async def _process_projection(
        self,
        projection: Projection,
    ) -> int:
        """Process events for a single projection."""
        position = await self._position_store.get_position(projection.name)
        stats = self._stats[projection.name]
        
        stats.status = ProjectionStatus.RUNNING
        
        events = await self._event_store.get_all_events(
            from_sequence=position.last_sequence,
            batch_size=self._batch_size,
        )
        
        if not events:
            stats.status = ProjectionStatus.LIVE
            return 0
        
        stats.status = ProjectionStatus.CATCHING_UP
        
        for envelope in events:
            try:
                if projection.handles(envelope.event_type):
                    await projection.apply(envelope.event)
                
                position.last_sequence = envelope.sequence
                position.events_processed += 1
                position.last_processed_at = datetime.now()
                
                stats.events_processed += 1
                stats.position = envelope.sequence
                stats.last_event_at = envelope.timestamp
            
            except Exception as e:
                logger.error(
                    f"Error applying event {envelope.event_type} "
                    f"to {projection.name}: {e}"
                )
                stats.errors += 1
                stats.status = ProjectionStatus.ERROR
        
        # Save position
        await self._position_store.save_position(position)
        
        # Update lag
        latest = await self._event_store.get_latest_sequence()
        stats.lag = latest - position.last_sequence
        
        if stats.lag == 0:
            stats.status = ProjectionStatus.LIVE
        
        return len(events)
    
    async def rebuild(
        self,
        projection_name: str,
    ) -> None:
        """Rebuild a projection from scratch."""
        projection = self._projections.get(projection_name)
        
        if not projection:
            raise ProjectionNotFoundError(
                f"Projection not found: {projection_name}"
            )
        
        # Reset projection
        projection.reset()
        
        # Reset position
        position = ProjectionPosition(projection_name)
        await self._position_store.save_position(position)
        
        # Process all events
        while True:
            processed = await self._process_projection(projection)
            if processed == 0:
                break
        
        logger.info(f"Rebuilt projection: {projection_name}")
    
    def get_stats(
        self,
        projection_name: Optional[str] = None,
    ) -> Union[ProjectionStats, Dict[str, ProjectionStats]]:
        """Get projection statistics."""
        if projection_name:
            return self._stats.get(projection_name)
        return self._stats.copy()
    
    async def catch_up(
        self,
        projection_name: Optional[str] = None,
    ) -> None:
        """Catch up projection(s) to current position."""
        if projection_name:
            projections = [self._projections[projection_name]]
        else:
            projections = list(self._projections.values())
        
        for projection in projections:
            while True:
                processed = await self._process_projection(projection)
                if processed < self._batch_size:
                    break


class ProjectionGroup:
    """
    Groups related projections together.
    """
    
    def __init__(self, name: str):
        self._name = name
        self._projections: List[Projection] = []
    
    @property
    def name(self) -> str:
        return self._name
    
    def add(self, projection: Projection) -> 'ProjectionGroup':
        """Add projection to group."""
        self._projections.append(projection)
        return self
    
    def get_projections(self) -> List[Projection]:
        """Get all projections."""
        return self._projections.copy()
    
    async def apply(self, event: Any) -> None:
        """Apply event to all projections."""
        for projection in self._projections:
            await projection.apply(event)
    
    def reset_all(self) -> None:
        """Reset all projections."""
        for projection in self._projections:
            projection.reset()


class LiveProjection(Projection):
    """
    Projection that receives events in real-time.
    """
    
    def __init__(self):
        super().__init__()
        self._subscribers: List[Callable[[Any], None]] = []
    
    def subscribe(
        self,
        callback: Callable[[Any], None],
    ) -> Callable[[], None]:
        """Subscribe to projection updates."""
        self._subscribers.append(callback)
        
        def unsubscribe():
            self._subscribers.remove(callback)
        
        return unsubscribe
    
    async def apply(self, event: Any) -> None:
        """Apply event and notify subscribers."""
        await super().apply(event)
        
        for subscriber in self._subscribers:
            try:
                if asyncio.iscoroutinefunction(subscriber):
                    await subscriber(event)
                else:
                    subscriber(event)
            except Exception as e:
                logger.error(f"Subscriber error: {e}")


# Decorators
def handles(
    event_type: Type,
) -> Callable:
    """
    Decorator to mark a method as handling an event type.
    
    Example:
        @handles(OrderCreatedEvent)
        def on_order_created(self, event):
            ...
    """
    def decorator(func: Callable) -> Callable:
        func._handles_event = event_type
        return func
    
    return decorator


def projection(
    name: Optional[str] = None,
) -> Callable:
    """
    Decorator to define a projection class.
    
    Example:
        @projection("order_summary")
        class OrderSummaryProjection(Projection):
            ...
    """
    def decorator(cls: type) -> type:
        if name:
            cls._name = name
        return cls
    
    return decorator


def read_model(
    cache_ttl: Optional[int] = None,
) -> Callable:
    """
    Decorator to mark a class as a read model.
    
    Example:
        @read_model(cache_ttl=60)
        class OrderListModel(ReadModel):
            ...
    """
    def decorator(cls: type) -> type:
        cls._cache_ttl = cache_ttl
        return cls
    
    return decorator


# Factory functions
def create_projector(
    event_store: EventStore,
    position_store: Optional[PositionStore] = None,
    batch_size: int = 100,
) -> Projector:
    """Create a projector."""
    return Projector(
        event_store,
        position_store,
        batch_size,
    )


def create_position_store() -> InMemoryPositionStore:
    """Create an in-memory position store."""
    return InMemoryPositionStore()


def create_projection_group(name: str) -> ProjectionGroup:
    """Create a projection group."""
    return ProjectionGroup(name)


__all__ = [
    # Exceptions
    "ProjectionError",
    "ProjectionNotFoundError",
    # Enums
    "ProjectionStatus",
    # Data classes
    "ProjectionPosition",
    "ProjectionStats",
    "EventEnvelope",
    # Store interfaces
    "EventStore",
    "InMemoryEventStore",
    "PositionStore",
    "InMemoryPositionStore",
    # Projection classes
    "Projection",
    "ReadModel",
    "MaterializedView",
    "LiveProjection",
    "ProjectionGroup",
    # Projector
    "Projector",
    # Decorators
    "handles",
    "projection",
    "read_model",
    # Factory functions
    "create_projector",
    "create_position_store",
    "create_projection_group",
]
