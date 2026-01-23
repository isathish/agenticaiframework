"""
Enterprise Aggregate Root Module.

Provides aggregate root pattern for maintaining consistency,
invariants, and domain event management.

Example:
    # Define an aggregate root
    class Order(AggregateRoot):
        def __init__(self, order_id: str):
            super().__init__(order_id)
            self.items = []
            self.status = "pending"
        
        def add_item(self, item: OrderItem):
            if self.status != "pending":
                raise DomainError("Cannot add items to non-pending order")
            self.items.append(item)
            self.raise_event(ItemAdded(item))
        
        def submit(self):
            if not self.items:
                raise DomainError("Cannot submit empty order")
            self.status = "submitted"
            self.raise_event(OrderSubmitted(self.id))
"""

from __future__ import annotations

import copy
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
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

ID = TypeVar('ID')
E = TypeVar('E')
A = TypeVar('A', bound='AggregateRoot')


class AggregateError(Exception):
    """Aggregate error."""
    pass


class InvariantViolationError(AggregateError):
    """Invariant violation error."""
    pass


class ConcurrencyError(AggregateError):
    """Concurrency conflict error."""
    pass


class AggregateState(str, Enum):
    """Aggregate state."""
    NEW = "new"
    PERSISTED = "persisted"
    MODIFIED = "modified"
    DELETED = "deleted"


@dataclass
class DomainEvent:
    """Base domain event."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    occurred_at: datetime = field(default_factory=datetime.now)
    aggregate_id: Optional[str] = None
    aggregate_type: Optional[str] = None


@dataclass
class AggregateMetadata:
    """Aggregate metadata."""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    version: int = 0
    deleted_at: Optional[datetime] = None


class InvariantChecker:
    """
    Invariant checker for aggregates.
    """
    
    def __init__(self):
        self._invariants: List[tuple] = []  # (name, check_func, message)
    
    def add(
        self,
        name: str,
        check: Callable[[Any], bool],
        message: str,
    ) -> "InvariantChecker":
        """Add an invariant."""
        self._invariants.append((name, check, message))
        return self
    
    def check_all(self, aggregate: Any) -> List[str]:
        """Check all invariants and return violations."""
        violations = []
        for name, check, message in self._invariants:
            try:
                if not check(aggregate):
                    violations.append(f"{name}: {message}")
            except Exception as e:
                violations.append(f"{name}: Check failed - {e}")
        return violations
    
    def assert_all(self, aggregate: Any) -> None:
        """Assert all invariants or raise error."""
        violations = self.check_all(aggregate)
        if violations:
            raise InvariantViolationError(
                f"Invariant violations: {', '.join(violations)}"
            )


class AggregateRoot(ABC):
    """
    Base aggregate root class.
    
    Aggregates are consistency boundaries that encapsulate
    domain logic and raise domain events.
    """
    
    def __init__(self, id: Any):
        self._id = id
        self._metadata = AggregateMetadata()
        self._events: List[DomainEvent] = []
        self._state = AggregateState.NEW
        self._invariant_checker = InvariantChecker()
        self._setup_invariants()
    
    @property
    def id(self) -> Any:
        """Get aggregate ID."""
        return self._id
    
    @property
    def version(self) -> int:
        """Get aggregate version."""
        return self._metadata.version
    
    @property
    def is_new(self) -> bool:
        """Check if aggregate is new."""
        return self._state == AggregateState.NEW
    
    @property
    def is_deleted(self) -> bool:
        """Check if aggregate is deleted."""
        return self._state == AggregateState.DELETED
    
    def _setup_invariants(self) -> None:
        """Override to set up invariants."""
        pass
    
    def add_invariant(
        self,
        name: str,
        check: Callable[["AggregateRoot"], bool],
        message: str,
    ) -> None:
        """Add an invariant."""
        self._invariant_checker.add(name, check, message)
    
    def check_invariants(self) -> None:
        """Check all invariants."""
        self._invariant_checker.assert_all(self)
    
    def raise_event(self, event: DomainEvent) -> None:
        """Raise a domain event."""
        event.aggregate_id = str(self._id)
        event.aggregate_type = self.__class__.__name__
        self._events.append(event)
    
    def get_events(self) -> List[DomainEvent]:
        """Get pending domain events."""
        return list(self._events)
    
    def clear_events(self) -> List[DomainEvent]:
        """Clear and return pending events."""
        events = self._events
        self._events = []
        return events
    
    def mark_persisted(self, new_version: int) -> None:
        """Mark as persisted with new version."""
        self._metadata.version = new_version
        self._metadata.updated_at = datetime.now()
        self._state = AggregateState.PERSISTED
    
    def mark_modified(self) -> None:
        """Mark as modified."""
        if self._state != AggregateState.NEW:
            self._state = AggregateState.MODIFIED
        self._metadata.updated_at = datetime.now()
    
    def mark_deleted(self) -> None:
        """Mark as deleted."""
        self._state = AggregateState.DELETED
        self._metadata.deleted_at = datetime.now()
    
    def check_version(self, expected: int) -> bool:
        """Check version for optimistic locking."""
        return self._metadata.version == expected
    
    def assert_version(self, expected: int) -> None:
        """Assert version matches."""
        if not self.check_version(expected):
            raise ConcurrencyError(
                f"Version mismatch: expected {expected}, "
                f"got {self._metadata.version}"
            )
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, AggregateRoot):
            return False
        return self._id == other._id
    
    def __hash__(self) -> int:
        return hash(self._id)


class EventSourcedAggregate(AggregateRoot):
    """
    Event-sourced aggregate root.
    
    State is derived from replaying events.
    """
    
    def __init__(self, id: Any):
        super().__init__(id)
        self._event_version = 0
    
    def apply_event(self, event: DomainEvent) -> None:
        """Apply an event to update state."""
        handler_name = f"_apply_{type(event).__name__}"
        handler = getattr(self, handler_name, None)
        
        if handler:
            handler(event)
        
        self._event_version += 1
    
    def raise_event(self, event: DomainEvent) -> None:
        """Raise and apply an event."""
        self.apply_event(event)
        super().raise_event(event)
    
    @classmethod
    def reconstitute(
        cls,
        id: Any,
        events: List[DomainEvent],
    ) -> "EventSourcedAggregate":
        """Reconstitute aggregate from events."""
        aggregate = cls(id)
        aggregate._state = AggregateState.PERSISTED
        
        for event in events:
            aggregate.apply_event(event)
        
        aggregate._events.clear()  # Clear events used for reconstitution
        return aggregate
    
    @property
    def event_version(self) -> int:
        """Get event version."""
        return self._event_version


class AggregateFactory(Generic[A]):
    """
    Factory for creating aggregates.
    """
    
    def __init__(
        self,
        aggregate_class: Type[A],
        id_generator: Optional[Callable[[], Any]] = None,
    ):
        self._aggregate_class = aggregate_class
        self._id_generator = id_generator or (lambda: str(uuid.uuid4()))
    
    def create(self, **kwargs: Any) -> A:
        """Create a new aggregate."""
        aggregate_id = self._id_generator()
        return self._aggregate_class(aggregate_id, **kwargs)
    
    def create_with_id(self, id: Any, **kwargs: Any) -> A:
        """Create aggregate with specific ID."""
        return self._aggregate_class(id, **kwargs)


class AggregateBuilder(Generic[A]):
    """
    Builder for aggregates.
    """
    
    def __init__(self, aggregate_class: Type[A]):
        self._aggregate_class = aggregate_class
        self._id: Optional[Any] = None
        self._properties: Dict[str, Any] = {}
    
    def with_id(self, id: Any) -> "AggregateBuilder[A]":
        """Set aggregate ID."""
        self._id = id
        return self
    
    def with_property(
        self,
        name: str,
        value: Any,
    ) -> "AggregateBuilder[A]":
        """Set a property."""
        self._properties[name] = value
        return self
    
    def with_properties(
        self,
        **kwargs: Any,
    ) -> "AggregateBuilder[A]":
        """Set multiple properties."""
        self._properties.update(kwargs)
        return self
    
    def build(self) -> A:
        """Build the aggregate."""
        if self._id is None:
            self._id = str(uuid.uuid4())
        
        aggregate = self._aggregate_class(self._id)
        
        for name, value in self._properties.items():
            setattr(aggregate, name, value)
        
        return aggregate


class AggregateRepository(ABC, Generic[A]):
    """
    Repository for aggregates.
    """
    
    @abstractmethod
    async def get(self, id: Any) -> Optional[A]:
        """Get aggregate by ID."""
        pass
    
    @abstractmethod
    async def save(self, aggregate: A) -> None:
        """Save aggregate."""
        pass
    
    @abstractmethod
    async def delete(self, aggregate: A) -> None:
        """Delete aggregate."""
        pass


class InMemoryAggregateRepository(AggregateRepository[A]):
    """
    In-memory aggregate repository.
    """
    
    def __init__(self, event_publisher: Optional[Callable[[DomainEvent], None]] = None):
        self._aggregates: Dict[Any, A] = {}
        self._event_publisher = event_publisher
    
    async def get(self, id: Any) -> Optional[A]:
        return self._aggregates.get(id)
    
    async def save(self, aggregate: A) -> None:
        # Check optimistic locking
        if aggregate.id in self._aggregates:
            existing = self._aggregates[aggregate.id]
            if aggregate.version != existing.version:
                raise ConcurrencyError("Aggregate was modified by another process")
        
        # Increment version
        new_version = aggregate.version + 1
        
        # Publish events
        if self._event_publisher:
            for event in aggregate.get_events():
                self._event_publisher(event)
        
        # Clear events and save
        aggregate.clear_events()
        aggregate.mark_persisted(new_version)
        
        self._aggregates[aggregate.id] = aggregate
    
    async def delete(self, aggregate: A) -> None:
        aggregate.mark_deleted()
        self._aggregates.pop(aggregate.id, None)


class EventSourcedRepository(AggregateRepository[EventSourcedAggregate]):
    """
    Repository for event-sourced aggregates.
    """
    
    def __init__(
        self,
        event_store: Any,  # EventStore from event_sourcing module
        aggregate_class: Type[EventSourcedAggregate],
    ):
        self._event_store = event_store
        self._aggregate_class = aggregate_class
    
    async def get(self, id: Any) -> Optional[EventSourcedAggregate]:
        # Load events from store
        events = await self._event_store.load(str(id))
        
        if not events:
            return None
        
        return self._aggregate_class.reconstitute(id, events)
    
    async def save(self, aggregate: EventSourcedAggregate) -> None:
        events = aggregate.get_events()
        
        if events:
            # Check version for optimistic locking
            expected_version = aggregate.event_version - len(events)
            
            await self._event_store.append(
                str(aggregate.id),
                events,
                expected_version=expected_version,
            )
        
        aggregate.clear_events()
        aggregate.mark_persisted(aggregate.event_version)
    
    async def delete(self, aggregate: EventSourcedAggregate) -> None:
        aggregate.mark_deleted()
        # Optionally append deletion event
        # await self._event_store.delete(str(aggregate.id))


class AggregateSnapshot:
    """
    Snapshot of aggregate state.
    """
    
    def __init__(
        self,
        aggregate_id: str,
        aggregate_type: str,
        version: int,
        state: Dict[str, Any],
        created_at: Optional[datetime] = None,
    ):
        self.aggregate_id = aggregate_id
        self.aggregate_type = aggregate_type
        self.version = version
        self.state = state
        self.created_at = created_at or datetime.now()


class SnapshotStore(ABC):
    """
    Store for aggregate snapshots.
    """
    
    @abstractmethod
    async def save(self, snapshot: AggregateSnapshot) -> None:
        """Save snapshot."""
        pass
    
    @abstractmethod
    async def get(self, aggregate_id: str) -> Optional[AggregateSnapshot]:
        """Get latest snapshot."""
        pass


class InMemorySnapshotStore(SnapshotStore):
    """
    In-memory snapshot store.
    """
    
    def __init__(self):
        self._snapshots: Dict[str, AggregateSnapshot] = {}
    
    async def save(self, snapshot: AggregateSnapshot) -> None:
        self._snapshots[snapshot.aggregate_id] = snapshot
    
    async def get(self, aggregate_id: str) -> Optional[AggregateSnapshot]:
        return self._snapshots.get(aggregate_id)


class AggregateManager:
    """
    Manager for aggregate lifecycle.
    """
    
    def __init__(self):
        self._factories: Dict[Type, AggregateFactory] = {}
        self._repositories: Dict[Type, AggregateRepository] = {}
    
    def register_factory(
        self,
        aggregate_class: Type[A],
        factory: AggregateFactory[A],
    ) -> None:
        """Register a factory."""
        self._factories[aggregate_class] = factory
    
    def register_repository(
        self,
        aggregate_class: Type[A],
        repository: AggregateRepository[A],
    ) -> None:
        """Register a repository."""
        self._repositories[aggregate_class] = repository
    
    def create(
        self,
        aggregate_class: Type[A],
        **kwargs: Any,
    ) -> A:
        """Create aggregate using registered factory."""
        factory = self._factories.get(aggregate_class)
        if not factory:
            raise AggregateError(f"No factory registered for {aggregate_class}")
        return factory.create(**kwargs)
    
    async def get(
        self,
        aggregate_class: Type[A],
        id: Any,
    ) -> Optional[A]:
        """Get aggregate using registered repository."""
        repository = self._repositories.get(aggregate_class)
        if not repository:
            raise AggregateError(f"No repository registered for {aggregate_class}")
        return await repository.get(id)
    
    async def save(
        self,
        aggregate: AggregateRoot,
    ) -> None:
        """Save aggregate using registered repository."""
        repository = self._repositories.get(type(aggregate))
        if not repository:
            raise AggregateError(f"No repository registered for {type(aggregate)}")
        await repository.save(aggregate)


# Decorators
def aggregate(cls: Type[A]) -> Type[A]:
    """
    Class decorator to mark as aggregate root.
    
    Example:
        @aggregate
        class Order(AggregateRoot):
            pass
    """
    cls._is_aggregate_root = True
    return cls


def invariant(
    message: str,
) -> Callable[[Callable[[A], bool]], Callable[[A], bool]]:
    """
    Method decorator to define invariant.
    
    Example:
        class Order(AggregateRoot):
            @invariant("Order must have items")
            def has_items(self) -> bool:
                return len(self.items) > 0
    """
    def decorator(func: Callable[[A], bool]) -> Callable[[A], bool]:
        func._invariant = True
        func._invariant_message = message
        return func
    
    return decorator


def domain_event(cls: Type) -> Type:
    """
    Class decorator to mark as domain event.
    
    Example:
        @domain_event
        @dataclass
        class OrderCreated(DomainEvent):
            order_id: str
    """
    cls._is_domain_event = True
    return cls


def apply_event(event_type: Type[DomainEvent]):
    """
    Method decorator to mark as event applier.
    
    Example:
        class Order(EventSourcedAggregate):
            @apply_event(OrderCreated)
            def _on_created(self, event: OrderCreated):
                self.status = "created"
    """
    def decorator(func: Callable) -> Callable:
        func._applies_event = event_type
        return func
    
    return decorator


# Factory functions
def create_aggregate_factory(
    aggregate_class: Type[A],
    id_generator: Optional[Callable[[], Any]] = None,
) -> AggregateFactory[A]:
    """Create an aggregate factory."""
    return AggregateFactory(aggregate_class, id_generator)


def create_aggregate_builder(
    aggregate_class: Type[A],
) -> AggregateBuilder[A]:
    """Create an aggregate builder."""
    return AggregateBuilder(aggregate_class)


def create_aggregate_repository(
    event_publisher: Optional[Callable[[DomainEvent], None]] = None,
) -> InMemoryAggregateRepository:
    """Create an in-memory aggregate repository."""
    return InMemoryAggregateRepository(event_publisher)


def create_event_sourced_repository(
    event_store: Any,
    aggregate_class: Type[EventSourcedAggregate],
) -> EventSourcedRepository:
    """Create an event-sourced repository."""
    return EventSourcedRepository(event_store, aggregate_class)


def create_snapshot_store() -> InMemorySnapshotStore:
    """Create a snapshot store."""
    return InMemorySnapshotStore()


def create_aggregate_manager() -> AggregateManager:
    """Create an aggregate manager."""
    return AggregateManager()


def create_invariant_checker() -> InvariantChecker:
    """Create an invariant checker."""
    return InvariantChecker()


__all__ = [
    # Exceptions
    "AggregateError",
    "InvariantViolationError",
    "ConcurrencyError",
    # Enums
    "AggregateState",
    # Data classes
    "DomainEvent",
    "AggregateMetadata",
    "AggregateSnapshot",
    # Core classes
    "InvariantChecker",
    "AggregateRoot",
    "EventSourcedAggregate",
    # Factory and Builder
    "AggregateFactory",
    "AggregateBuilder",
    # Repositories
    "AggregateRepository",
    "InMemoryAggregateRepository",
    "EventSourcedRepository",
    # Snapshots
    "SnapshotStore",
    "InMemorySnapshotStore",
    # Manager
    "AggregateManager",
    # Decorators
    "aggregate",
    "invariant",
    "domain_event",
    "apply_event",
    # Factory functions
    "create_aggregate_factory",
    "create_aggregate_builder",
    "create_aggregate_repository",
    "create_event_sourced_repository",
    "create_snapshot_store",
    "create_aggregate_manager",
    "create_invariant_checker",
]
