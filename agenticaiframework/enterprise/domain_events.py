"""
Enterprise Domain Events Module.

Provides domain events patterns, event publishing, subscriptions,
and event-driven communication for DDD architectures.

Example:
    # Create event dispatcher
    dispatcher = create_event_dispatcher()
    
    # Subscribe to events
    @dispatcher.subscribe(OrderCreated)
    async def handle_order_created(event):
        print(f"Order created: {event.order_id}")
    
    # Publish event
    await dispatcher.publish(OrderCreated(order_id="123", amount=100.0))
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from functools import wraps
from typing import (
    Any,
    Awaitable,
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
E = TypeVar('E', bound='DomainEvent')


class DomainEventError(Exception):
    """Domain event error."""
    pass


class HandlerError(DomainEventError):
    """Handler error."""
    pass


class PublishError(DomainEventError):
    """Publish error."""
    pass


class EventPriority(str, Enum):
    """Event priority."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class EventState(str, Enum):
    """Event state."""
    PENDING = "pending"
    PUBLISHED = "published"
    HANDLED = "handled"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class EventMetadata:
    """Event metadata."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    aggregate_id: Optional[str] = None
    aggregate_type: Optional[str] = None
    user_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    version: int = 1
    priority: EventPriority = EventPriority.NORMAL
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DomainEvent:
    """Base domain event class."""
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
    def aggregate_id(self) -> Optional[str]:
        return self._metadata.aggregate_id
    
    def with_correlation(
        self,
        correlation_id: str,
    ) -> "DomainEvent":
        """Create copy with correlation ID."""
        self._metadata.correlation_id = correlation_id
        return self
    
    def with_causation(
        self,
        causation_id: str,
    ) -> "DomainEvent":
        """Create copy with causation ID."""
        self._metadata.causation_id = causation_id
        return self
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = {"event_type": self.event_type}
        for key, value in self.__dict__.items():
            if not key.startswith('_'):
                data[key] = value
        return data


@dataclass
class EventEnvelope:
    """Event envelope for transport."""
    event: DomainEvent
    metadata: EventMetadata
    state: EventState = EventState.PENDING
    attempts: int = 0
    last_error: Optional[str] = None
    handled_at: Optional[datetime] = None


@dataclass 
class HandlerResult:
    """Handler execution result."""
    event_id: str
    handler_name: str
    success: bool
    error: Optional[str] = None
    duration_ms: float = 0.0
    executed_at: datetime = field(default_factory=datetime.now)


# Handler type
EventHandler = Callable[[E], Awaitable[None]]


class EventHandler(ABC):
    """Abstract event handler."""
    
    @abstractmethod
    async def handle(self, event: DomainEvent) -> None:
        """Handle event."""
        pass
    
    @property
    def event_types(self) -> List[str]:
        """Event types this handler handles."""
        return []


class EventStore(ABC):
    """Abstract event store for persistence."""
    
    @abstractmethod
    async def store(self, envelope: EventEnvelope) -> None:
        """Store event."""
        pass
    
    @abstractmethod
    async def get(self, event_id: str) -> Optional[EventEnvelope]:
        """Get event by ID."""
        pass
    
    @abstractmethod
    async def get_by_aggregate(
        self,
        aggregate_id: str,
        from_version: int = 0,
    ) -> List[EventEnvelope]:
        """Get events for aggregate."""
        pass


class InMemoryEventStore(EventStore):
    """In-memory event store."""
    
    def __init__(self):
        self._events: Dict[str, EventEnvelope] = {}
        self._by_aggregate: Dict[str, List[str]] = {}
        self._lock = asyncio.Lock()
    
    async def store(self, envelope: EventEnvelope) -> None:
        async with self._lock:
            event_id = envelope.event.event_id
            self._events[event_id] = envelope
            
            agg_id = envelope.metadata.aggregate_id
            if agg_id:
                if agg_id not in self._by_aggregate:
                    self._by_aggregate[agg_id] = []
                self._by_aggregate[agg_id].append(event_id)
    
    async def get(self, event_id: str) -> Optional[EventEnvelope]:
        return self._events.get(event_id)
    
    async def get_by_aggregate(
        self,
        aggregate_id: str,
        from_version: int = 0,
    ) -> List[EventEnvelope]:
        event_ids = self._by_aggregate.get(aggregate_id, [])
        envelopes = [
            self._events[eid] for eid in event_ids
            if eid in self._events
        ]
        return [e for e in envelopes if e.metadata.version > from_version]


class EventSubscription:
    """
    Event subscription.
    """
    
    def __init__(
        self,
        event_type: Type[E],
        handler: Callable[[E], Awaitable[None]],
        priority: int = 0,
        filter_fn: Optional[Callable[[E], bool]] = None,
    ):
        self.subscription_id = str(uuid.uuid4())
        self.event_type = event_type
        self.handler = handler
        self.priority = priority
        self.filter_fn = filter_fn
        self.created_at = datetime.now()
        self.call_count = 0
    
    async def invoke(self, event: E) -> HandlerResult:
        """Invoke the handler."""
        start = datetime.now()
        
        try:
            # Apply filter
            if self.filter_fn and not self.filter_fn(event):
                return HandlerResult(
                    event_id=event.event_id,
                    handler_name=self.handler.__name__,
                    success=True,
                    duration_ms=0,
                )
            
            await self.handler(event)
            self.call_count += 1
            
            duration = (datetime.now() - start).total_seconds() * 1000
            
            return HandlerResult(
                event_id=event.event_id,
                handler_name=self.handler.__name__,
                success=True,
                duration_ms=duration,
            )
        
        except Exception as e:
            duration = (datetime.now() - start).total_seconds() * 1000
            
            return HandlerResult(
                event_id=event.event_id,
                handler_name=self.handler.__name__,
                success=False,
                error=str(e),
                duration_ms=duration,
            )


class EventDispatcher:
    """
    Domain event dispatcher.
    """
    
    def __init__(
        self,
        store: Optional[EventStore] = None,
        async_dispatch: bool = False,
    ):
        self._subscriptions: Dict[str, List[EventSubscription]] = {}
        self._all_handlers: List[EventSubscription] = []
        self._store = store
        self._async_dispatch = async_dispatch
        self._middleware: List[Callable] = []
        self._lock = asyncio.Lock()
    
    def subscribe(
        self,
        event_type: Type[E],
        priority: int = 0,
        filter_fn: Optional[Callable[[E], bool]] = None,
    ) -> Callable[[Callable[[E], Awaitable[None]]], Callable[[E], Awaitable[None]]]:
        """
        Decorator to subscribe to events.
        
        Example:
            @dispatcher.subscribe(OrderCreated)
            async def handle_order_created(event):
                ...
        """
        def decorator(
            func: Callable[[E], Awaitable[None]],
        ) -> Callable[[E], Awaitable[None]]:
            self.add_handler(event_type, func, priority, filter_fn)
            return func
        
        return decorator
    
    def add_handler(
        self,
        event_type: Type[E],
        handler: Callable[[E], Awaitable[None]],
        priority: int = 0,
        filter_fn: Optional[Callable[[E], bool]] = None,
    ) -> str:
        """Add event handler."""
        subscription = EventSubscription(
            event_type=event_type,
            handler=handler,
            priority=priority,
            filter_fn=filter_fn,
        )
        
        type_name = event_type.__name__
        
        if type_name not in self._subscriptions:
            self._subscriptions[type_name] = []
        
        self._subscriptions[type_name].append(subscription)
        
        # Sort by priority (higher first)
        self._subscriptions[type_name].sort(
            key=lambda s: s.priority,
            reverse=True,
        )
        
        logger.debug(f"Added handler for {type_name}")
        
        return subscription.subscription_id
    
    def subscribe_all(
        self,
        handler: Callable[[DomainEvent], Awaitable[None]],
        priority: int = 0,
    ) -> str:
        """Subscribe to all events."""
        subscription = EventSubscription(
            event_type=DomainEvent,
            handler=handler,
            priority=priority,
        )
        
        self._all_handlers.append(subscription)
        self._all_handlers.sort(key=lambda s: s.priority, reverse=True)
        
        return subscription.subscription_id
    
    def unsubscribe(self, subscription_id: str) -> None:
        """Unsubscribe handler."""
        for type_name, subs in self._subscriptions.items():
            self._subscriptions[type_name] = [
                s for s in subs if s.subscription_id != subscription_id
            ]
        
        self._all_handlers = [
            s for s in self._all_handlers
            if s.subscription_id != subscription_id
        ]
    
    async def publish(
        self,
        event: E,
        correlation_id: Optional[str] = None,
    ) -> List[HandlerResult]:
        """Publish event to handlers."""
        if correlation_id:
            event.with_correlation(correlation_id)
        
        # Store event if store is configured
        if self._store:
            envelope = EventEnvelope(
                event=event,
                metadata=event._metadata,
                state=EventState.PUBLISHED,
            )
            await self._store.store(envelope)
        
        # Get handlers
        handlers = self._subscriptions.get(event.event_type, [])
        all_handlers = handlers + self._all_handlers
        
        if not all_handlers:
            return []
        
        # Execute handlers
        if self._async_dispatch:
            tasks = [h.invoke(event) for h in all_handlers]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            return [
                r if isinstance(r, HandlerResult) else HandlerResult(
                    event_id=event.event_id,
                    handler_name="unknown",
                    success=False,
                    error=str(r),
                )
                for r in results
            ]
        else:
            results = []
            for handler in all_handlers:
                result = await handler.invoke(event)
                results.append(result)
            
            return results
    
    async def publish_many(
        self,
        events: List[DomainEvent],
        parallel: bool = False,
    ) -> Dict[str, List[HandlerResult]]:
        """Publish multiple events."""
        results: Dict[str, List[HandlerResult]] = {}
        
        if parallel:
            tasks = {
                event.event_id: self.publish(event)
                for event in events
            }
            
            for event_id, task in tasks.items():
                try:
                    results[event_id] = await task
                except Exception as e:
                    results[event_id] = [
                        HandlerResult(
                            event_id=event_id,
                            handler_name="unknown",
                            success=False,
                            error=str(e),
                        )
                    ]
        else:
            for event in events:
                results[event.event_id] = await self.publish(event)
        
        return results


class EventBus:
    """
    Event bus with queuing support.
    """
    
    def __init__(
        self,
        dispatcher: Optional[EventDispatcher] = None,
        max_workers: int = 4,
    ):
        self._dispatcher = dispatcher or EventDispatcher()
        self._queue: asyncio.Queue = asyncio.Queue()
        self._max_workers = max_workers
        self._workers: List[asyncio.Task] = []
        self._running = False
    
    @property
    def dispatcher(self) -> EventDispatcher:
        return self._dispatcher
    
    async def start(self) -> None:
        """Start the event bus."""
        if self._running:
            return
        
        self._running = True
        
        for i in range(self._max_workers):
            task = asyncio.create_task(self._worker(i))
            self._workers.append(task)
        
        logger.info(f"Event bus started with {self._max_workers} workers")
    
    async def stop(self) -> None:
        """Stop the event bus."""
        self._running = False
        
        for worker in self._workers:
            worker.cancel()
        
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
    
    async def _worker(self, worker_id: int) -> None:
        """Worker loop."""
        while self._running:
            try:
                event = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=1.0,
                )
                
                try:
                    await self._dispatcher.publish(event)
                except Exception as e:
                    logger.error(f"Worker {worker_id} error: {e}")
                
                self._queue.task_done()
            
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
    
    async def emit(self, event: DomainEvent) -> None:
        """Emit event to queue."""
        await self._queue.put(event)
    
    async def emit_sync(self, event: DomainEvent) -> List[HandlerResult]:
        """Emit and wait for handlers."""
        return await self._dispatcher.publish(event)


class AggregateEvents:
    """
    Mixin for aggregates to collect domain events.
    """
    
    def __init__(self):
        self._pending_events: List[DomainEvent] = []
    
    def raise_event(self, event: DomainEvent) -> None:
        """Raise a domain event."""
        self._pending_events.append(event)
    
    def get_pending_events(self) -> List[DomainEvent]:
        """Get pending events."""
        return self._pending_events.copy()
    
    def clear_events(self) -> None:
        """Clear pending events."""
        self._pending_events.clear()
    
    def pop_events(self) -> List[DomainEvent]:
        """Get and clear pending events."""
        events = self._pending_events.copy()
        self._pending_events.clear()
        return events


class EventPublisher:
    """
    Event publisher utility.
    """
    
    def __init__(
        self,
        dispatcher: EventDispatcher,
        default_correlation_id: Optional[str] = None,
    ):
        self._dispatcher = dispatcher
        self._correlation_id = default_correlation_id
    
    def with_correlation(
        self,
        correlation_id: str,
    ) -> "EventPublisher":
        """Create publisher with correlation ID."""
        return EventPublisher(self._dispatcher, correlation_id)
    
    async def publish(self, event: DomainEvent) -> List[HandlerResult]:
        """Publish event."""
        return await self._dispatcher.publish(
            event,
            correlation_id=self._correlation_id,
        )
    
    async def publish_from_aggregate(
        self,
        aggregate: AggregateEvents,
    ) -> Dict[str, List[HandlerResult]]:
        """Publish all events from aggregate."""
        events = aggregate.pop_events()
        return await self._dispatcher.publish_many(events)


# Global dispatcher
_global_dispatcher: Optional[EventDispatcher] = None


def get_global_dispatcher() -> EventDispatcher:
    """Get or create global dispatcher."""
    global _global_dispatcher
    
    if _global_dispatcher is None:
        _global_dispatcher = EventDispatcher()
    
    return _global_dispatcher


# Decorators
def event_handler(
    event_type: Type[E],
    priority: int = 0,
    dispatcher: Optional[EventDispatcher] = None,
) -> Callable:
    """
    Decorator to register event handler.
    
    Example:
        @event_handler(OrderCreated)
        async def handle_order_created(event):
            ...
    """
    _dispatcher = dispatcher or get_global_dispatcher()
    
    def decorator(func: Callable) -> Callable:
        _dispatcher.add_handler(event_type, func, priority)
        return func
    
    return decorator


def handles(
    *event_types: Type[DomainEvent],
) -> Callable:
    """
    Decorator to mark handler for multiple event types.
    
    Example:
        @handles(OrderCreated, OrderUpdated)
        async def handle_order_events(event):
            ...
    """
    def decorator(func: Callable) -> Callable:
        func._handles_events = event_types
        return func
    
    return decorator


def on_event(
    event_type: Type[E],
    filter_fn: Optional[Callable[[E], bool]] = None,
) -> Callable:
    """
    Decorator to filter events before handling.
    
    Example:
        @on_event(OrderCreated, filter_fn=lambda e: e.amount > 100)
        async def handle_large_orders(event):
            ...
    """
    def decorator(func: Callable) -> Callable:
        func._event_type = event_type
        func._event_filter = filter_fn
        return func
    
    return decorator


# Factory functions
def create_event_dispatcher(
    store: Optional[EventStore] = None,
    async_dispatch: bool = False,
) -> EventDispatcher:
    """Create an event dispatcher."""
    return EventDispatcher(
        store=store,
        async_dispatch=async_dispatch,
    )


def create_event_bus(
    max_workers: int = 4,
) -> EventBus:
    """Create an event bus."""
    return EventBus(max_workers=max_workers)


def create_event_store() -> EventStore:
    """Create an event store."""
    return InMemoryEventStore()


def create_event_publisher(
    dispatcher: Optional[EventDispatcher] = None,
) -> EventPublisher:
    """Create an event publisher."""
    return EventPublisher(
        dispatcher or get_global_dispatcher()
    )


__all__ = [
    # Exceptions
    "DomainEventError",
    "HandlerError",
    "PublishError",
    # Enums
    "EventPriority",
    "EventState",
    # Data classes
    "EventMetadata",
    "DomainEvent",
    "EventEnvelope",
    "HandlerResult",
    # Abstract classes
    "EventStore",
    # Implementations
    "InMemoryEventStore",
    "EventSubscription",
    # Core classes
    "EventDispatcher",
    "EventBus",
    "AggregateEvents",
    "EventPublisher",
    # Decorators
    "event_handler",
    "handles",
    "on_event",
    # Factory functions
    "create_event_dispatcher",
    "create_event_bus",
    "create_event_store",
    "create_event_publisher",
    "get_global_dispatcher",
]
