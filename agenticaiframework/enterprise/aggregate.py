"""
Enterprise Aggregate Module.

Provides domain aggregates, aggregate root pattern,
and event sourcing foundations.

Example:
    # Define aggregate
    class OrderAggregate(AggregateRoot):
        def __init__(self, order_id: str):
            super().__init__(order_id)
            self.items = []
            self.status = "pending"
        
        def add_item(self, product_id: str, quantity: int):
            self.apply(ItemAddedEvent(
                order_id=self.id,
                product_id=product_id,
                quantity=quantity,
            ))
        
        def _on_item_added(self, event: ItemAddedEvent):
            self.items.append({"product_id": event.product_id, "quantity": event.quantity})
    
    # Use aggregate
    order = OrderAggregate("order_123")
    order.add_item("prod_1", 2)
    events = order.uncommitted_events
"""

from __future__ import annotations

import asyncio
import copy
import logging
import uuid
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
    Union,
)

logger = logging.getLogger(__name__)

T = TypeVar('T')
TEvent = TypeVar('TEvent', bound='DomainEvent')
TAggregate = TypeVar('TAggregate', bound='AggregateRoot')


class AggregateError(Exception):
    """Aggregate error."""
    pass


class ConcurrencyError(AggregateError):
    """Optimistic concurrency violation."""
    pass


class AggregateNotFoundError(AggregateError):
    """Aggregate not found."""
    pass


class InvalidOperationError(AggregateError):
    """Invalid operation on aggregate."""
    pass


@dataclass
class DomainEvent:
    """Base domain event."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    aggregate_id: str = ""
    aggregate_type: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    version: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def event_type(self) -> str:
        """Get event type name."""
        return type(self).__name__


@dataclass
class EventEnvelope:
    """Envelope wrapping a domain event with metadata."""
    event: DomainEvent
    sequence: int
    stream_id: str
    committed_at: datetime = field(default_factory=datetime.now)


class AggregateRoot(ABC):
    """
    Base class for aggregate roots.
    
    Aggregates are clusters of domain objects that can be
    treated as a single unit for data changes.
    """
    
    def __init__(self, aggregate_id: str):
        self._id = aggregate_id
        self._version = 0
        self._uncommitted_events: List[DomainEvent] = []
        self._event_handlers: Dict[str, Callable] = {}
        self._created_at = datetime.now()
        self._updated_at: Optional[datetime] = None
        
        # Register event handlers
        self._register_handlers()
    
    @property
    def id(self) -> str:
        """Get aggregate ID."""
        return self._id
    
    @property
    def version(self) -> int:
        """Get current version."""
        return self._version
    
    @property
    def uncommitted_events(self) -> List[DomainEvent]:
        """Get uncommitted events."""
        return list(self._uncommitted_events)
    
    @property
    def has_uncommitted_events(self) -> bool:
        """Check if there are uncommitted events."""
        return len(self._uncommitted_events) > 0
    
    def _register_handlers(self) -> None:
        """Register event handlers by convention."""
        for name in dir(self):
            if name.startswith("_on_"):
                method = getattr(self, name)
                if callable(method):
                    # Extract event name from method name
                    # _on_item_added -> ItemAddedEvent
                    event_name = "".join(
                        word.capitalize()
                        for word in name[4:].split("_")
                    )
                    self._event_handlers[event_name] = method
                    self._event_handlers[f"{event_name}Event"] = method
    
    def apply(self, event: DomainEvent) -> None:
        """
        Apply an event to the aggregate.
        
        This both updates state and adds to uncommitted events.
        """
        # Set event metadata
        event.aggregate_id = self._id
        event.aggregate_type = type(self).__name__
        event.version = self._version + 1
        
        # Apply state change
        self._apply_event(event)
        
        # Add to uncommitted
        self._uncommitted_events.append(event)
        self._version += 1
        self._updated_at = datetime.now()
    
    def _apply_event(self, event: DomainEvent) -> None:
        """Apply event to update internal state."""
        event_type = type(event).__name__
        handler = self._event_handlers.get(event_type)
        
        if handler:
            handler(event)
        else:
            # Try without 'Event' suffix
            event_type_short = event_type.replace("Event", "")
            handler = self._event_handlers.get(event_type_short)
            if handler:
                handler(event)
    
    def load_from_history(self, events: List[DomainEvent]) -> None:
        """
        Reconstitute aggregate from event history.
        """
        for event in events:
            self._apply_event(event)
            self._version = event.version
    
    def clear_uncommitted_events(self) -> List[DomainEvent]:
        """Clear and return uncommitted events."""
        events = self._uncommitted_events.copy()
        self._uncommitted_events.clear()
        return events


class Entity(ABC):
    """
    Base class for entities within an aggregate.
    """
    
    def __init__(self, entity_id: str):
        self._id = entity_id
    
    @property
    def id(self) -> str:
        """Get entity ID."""
        return self._id
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Entity):
            return False
        return self._id == other._id
    
    def __hash__(self) -> int:
        return hash(self._id)


class ValueObject(ABC):
    """
    Base class for value objects.
    
    Value objects are immutable and compared by their values.
    """
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ValueObject):
            return False
        return self.__dict__ == other.__dict__
    
    def __hash__(self) -> int:
        return hash(tuple(sorted(self.__dict__.items())))


@dataclass(frozen=True)
class Money(ValueObject):
    """Money value object."""
    amount: float
    currency: str = "USD"
    
    def __add__(self, other: 'Money') -> 'Money':
        if self.currency != other.currency:
            raise ValueError("Cannot add different currencies")
        return Money(self.amount + other.amount, self.currency)
    
    def __sub__(self, other: 'Money') -> 'Money':
        if self.currency != other.currency:
            raise ValueError("Cannot subtract different currencies")
        return Money(self.amount - other.amount, self.currency)
    
    def __mul__(self, multiplier: float) -> 'Money':
        return Money(self.amount * multiplier, self.currency)


@dataclass(frozen=True)
class Address(ValueObject):
    """Address value object."""
    street: str
    city: str
    state: str
    postal_code: str
    country: str = "USA"


# Event Store
class EventStore(ABC):
    """Abstract event store."""
    
    @abstractmethod
    async def append(
        self,
        stream_id: str,
        events: List[DomainEvent],
        expected_version: int,
    ) -> int:
        """Append events to stream."""
        pass
    
    @abstractmethod
    async def get_events(
        self,
        stream_id: str,
        from_version: int = 0,
    ) -> List[DomainEvent]:
        """Get events from stream."""
        pass
    
    @abstractmethod
    async def get_all_events(
        self,
        from_sequence: int = 0,
    ) -> List[EventEnvelope]:
        """Get all events across streams."""
        pass


class InMemoryEventStore(EventStore):
    """In-memory event store."""
    
    def __init__(self):
        self._streams: Dict[str, List[DomainEvent]] = {}
        self._all_events: List[EventEnvelope] = []
        self._sequence = 0
        self._lock = asyncio.Lock()
    
    async def append(
        self,
        stream_id: str,
        events: List[DomainEvent],
        expected_version: int,
    ) -> int:
        """Append events with optimistic concurrency."""
        async with self._lock:
            stream = self._streams.get(stream_id, [])
            current_version = len(stream)
            
            if current_version != expected_version:
                raise ConcurrencyError(
                    f"Expected version {expected_version}, "
                    f"but stream is at version {current_version}"
                )
            
            for event in events:
                stream.append(event)
                self._sequence += 1
                
                envelope = EventEnvelope(
                    event=event,
                    sequence=self._sequence,
                    stream_id=stream_id,
                )
                self._all_events.append(envelope)
            
            self._streams[stream_id] = stream
            
            return current_version + len(events)
    
    async def get_events(
        self,
        stream_id: str,
        from_version: int = 0,
    ) -> List[DomainEvent]:
        """Get events from stream."""
        stream = self._streams.get(stream_id, [])
        return stream[from_version:]
    
    async def get_all_events(
        self,
        from_sequence: int = 0,
    ) -> List[EventEnvelope]:
        """Get all events."""
        return [
            e for e in self._all_events
            if e.sequence > from_sequence
        ]


# Repository
class AggregateRepository(Generic[TAggregate]):
    """
    Repository for loading and saving aggregates.
    """
    
    def __init__(
        self,
        event_store: EventStore,
        aggregate_type: Type[TAggregate],
    ):
        self._event_store = event_store
        self._aggregate_type = aggregate_type
    
    async def get(
        self,
        aggregate_id: str,
    ) -> Optional[TAggregate]:
        """Load aggregate from events."""
        stream_id = self._stream_id(aggregate_id)
        events = await self._event_store.get_events(stream_id)
        
        if not events:
            return None
        
        aggregate = self._aggregate_type(aggregate_id)
        aggregate.load_from_history(events)
        
        return aggregate
    
    async def get_required(
        self,
        aggregate_id: str,
    ) -> TAggregate:
        """Load aggregate, raise if not found."""
        aggregate = await self.get(aggregate_id)
        
        if not aggregate:
            raise AggregateNotFoundError(
                f"{self._aggregate_type.__name__} not found: {aggregate_id}"
            )
        
        return aggregate
    
    async def save(
        self,
        aggregate: TAggregate,
    ) -> None:
        """Save aggregate uncommitted events."""
        if not aggregate.has_uncommitted_events:
            return
        
        stream_id = self._stream_id(aggregate.id)
        events = aggregate.uncommitted_events
        expected_version = aggregate.version - len(events)
        
        await self._event_store.append(
            stream_id,
            events,
            expected_version,
        )
        
        aggregate.clear_uncommitted_events()
    
    async def exists(self, aggregate_id: str) -> bool:
        """Check if aggregate exists."""
        stream_id = self._stream_id(aggregate_id)
        events = await self._event_store.get_events(stream_id, 0)
        return len(events) > 0
    
    def _stream_id(self, aggregate_id: str) -> str:
        """Generate stream ID."""
        return f"{self._aggregate_type.__name__}-{aggregate_id}"


# Aggregate Factory
class AggregateFactory(Generic[TAggregate]):
    """
    Factory for creating aggregates.
    """
    
    def __init__(
        self,
        aggregate_type: Type[TAggregate],
    ):
        self._aggregate_type = aggregate_type
    
    def create(
        self,
        aggregate_id: Optional[str] = None,
        **kwargs: Any,
    ) -> TAggregate:
        """Create a new aggregate."""
        aid = aggregate_id or str(uuid.uuid4())
        return self._aggregate_type(aid, **kwargs)
    
    def reconstitute(
        self,
        aggregate_id: str,
        events: List[DomainEvent],
    ) -> TAggregate:
        """Reconstitute aggregate from events."""
        aggregate = self._aggregate_type(aggregate_id)
        aggregate.load_from_history(events)
        return aggregate


# Decorators
def aggregate_command(
    validate: Optional[Callable[[TAggregate, Any], None]] = None,
) -> Callable:
    """
    Decorator for aggregate command methods.
    
    Example:
        @aggregate_command(validate=validate_can_add_item)
        def add_item(self, product_id: str, quantity: int):
            self.apply(ItemAddedEvent(...))
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self: AggregateRoot, *args: Any, **kwargs: Any) -> Any:
            if validate:
                validate(self, *args, **kwargs)
            return func(self, *args, **kwargs)
        
        return wrapper
    
    return decorator


def event_handler(
    event_type: Type[DomainEvent],
) -> Callable:
    """
    Decorator to mark event handler method.
    
    Example:
        @event_handler(ItemAddedEvent)
        def handle_item_added(self, event: ItemAddedEvent):
            self.items.append(event.item)
    """
    def decorator(func: Callable) -> Callable:
        func._handles_event = event_type
        return func
    
    return decorator


def domain_event(
    aggregate_type: Optional[str] = None,
) -> Callable:
    """
    Decorator to mark a class as a domain event.
    
    Example:
        @domain_event("Order")
        @dataclass
        class OrderCreatedEvent(DomainEvent):
            customer_id: str
    """
    def decorator(cls: type) -> type:
        if aggregate_type:
            cls._aggregate_type = aggregate_type
        return cls
    
    return decorator


# Factory functions
def create_event_store() -> InMemoryEventStore:
    """Create an in-memory event store."""
    return InMemoryEventStore()


def create_repository(
    aggregate_type: Type[TAggregate],
    event_store: Optional[EventStore] = None,
) -> AggregateRepository[TAggregate]:
    """Create an aggregate repository."""
    store = event_store or InMemoryEventStore()
    return AggregateRepository(store, aggregate_type)


def create_aggregate_factory(
    aggregate_type: Type[TAggregate],
) -> AggregateFactory[TAggregate]:
    """Create an aggregate factory."""
    return AggregateFactory(aggregate_type)


__all__ = [
    # Exceptions
    "AggregateError",
    "ConcurrencyError",
    "AggregateNotFoundError",
    "InvalidOperationError",
    # Base classes
    "DomainEvent",
    "EventEnvelope",
    "AggregateRoot",
    "Entity",
    "ValueObject",
    # Value objects
    "Money",
    "Address",
    # Event store
    "EventStore",
    "InMemoryEventStore",
    # Repository
    "AggregateRepository",
    "AggregateFactory",
    # Decorators
    "aggregate_command",
    "event_handler",
    "domain_event",
    # Factory functions
    "create_event_store",
    "create_repository",
    "create_aggregate_factory",
]
