"""
Enterprise Event Bus Module.

Provides event bus patterns for async event distribution,
pub/sub messaging, and event-driven architectures.

Example:
    # Create event bus
    bus = create_event_bus()
    
    # Subscribe to events
    @bus.subscribe(OrderCreated)
    async def on_order_created(event: OrderCreated):
        print(f"Order created: {event.order_id}")
    
    # Publish events
    await bus.publish(OrderCreated(order_id="123"))
"""

from __future__ import annotations

import asyncio
import logging
import uuid
import weakref
from abc import ABC, abstractmethod
from collections import defaultdict
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

T = TypeVar('T')
E = TypeVar('E')


logger = logging.getLogger(__name__)


class EventBusError(Exception):
    """Event bus error."""
    pass


class PublishError(EventBusError):
    """Publish error."""
    pass


class SubscriptionError(EventBusError):
    """Subscription error."""
    pass


class DeliveryMode(str, Enum):
    """Event delivery mode."""
    AT_MOST_ONCE = "at_most_once"
    AT_LEAST_ONCE = "at_least_once"
    EXACTLY_ONCE = "exactly_once"


class EventPriority(int, Enum):
    """Event priority."""
    LOW = 0
    NORMAL = 5
    HIGH = 10
    CRITICAL = 20


class SubscriptionState(str, Enum):
    """Subscription state."""
    ACTIVE = "active"
    PAUSED = "paused"
    CANCELLED = "cancelled"


@dataclass
class EventEnvelope:
    """Envelope wrapping an event."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = ""
    payload: Any = None
    timestamp: datetime = field(default_factory=datetime.now)
    priority: EventPriority = EventPriority.NORMAL
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    retries: int = 0


@dataclass
class SubscriptionInfo:
    """Subscription information."""
    id: str
    event_type: Type
    handler: Callable
    priority: int = 0
    filter: Optional[Callable[[Any], bool]] = None
    state: SubscriptionState = SubscriptionState.ACTIVE
    created_at: datetime = field(default_factory=datetime.now)
    call_count: int = 0


@dataclass
class PublishResult:
    """Result of publishing an event."""
    event_id: str
    success: bool
    delivered_to: int = 0
    failed: int = 0
    errors: List[str] = field(default_factory=list)


@dataclass
class BusStatistics:
    """Event bus statistics."""
    events_published: int = 0
    events_delivered: int = 0
    events_failed: int = 0
    subscriptions_count: int = 0
    active_handlers: int = 0


class EventHandler(ABC, Generic[E]):
    """
    Abstract event handler.
    """
    
    @abstractmethod
    async def handle(self, event: E) -> None:
        """Handle an event."""
        pass
    
    @property
    def event_type(self) -> Type[E]:
        """Get the event type this handler handles."""
        raise NotImplementedError


class Subscription:
    """
    Event subscription.
    """
    
    def __init__(
        self,
        info: SubscriptionInfo,
        unsubscribe: Callable[[], None],
    ):
        self._info = info
        self._unsubscribe = unsubscribe
    
    @property
    def id(self) -> str:
        return self._info.id
    
    @property
    def state(self) -> SubscriptionState:
        return self._info.state
    
    def pause(self) -> None:
        """Pause subscription."""
        self._info.state = SubscriptionState.PAUSED
    
    def resume(self) -> None:
        """Resume subscription."""
        self._info.state = SubscriptionState.ACTIVE
    
    def cancel(self) -> None:
        """Cancel subscription."""
        self._info.state = SubscriptionState.CANCELLED
        self._unsubscribe()


class EventBus(ABC):
    """
    Abstract event bus.
    """
    
    @abstractmethod
    async def publish(
        self,
        event: Any,
        priority: EventPriority = EventPriority.NORMAL,
    ) -> PublishResult:
        """Publish an event."""
        pass
    
    @abstractmethod
    def subscribe(
        self,
        event_type: Type[E],
        handler: Callable[[E], Any],
        priority: int = 0,
    ) -> Subscription:
        """Subscribe to an event type."""
        pass
    
    @abstractmethod
    def unsubscribe(self, subscription_id: str) -> None:
        """Unsubscribe from events."""
        pass


class InMemoryEventBus(EventBus):
    """
    In-memory event bus implementation.
    """
    
    def __init__(
        self,
        delivery_mode: DeliveryMode = DeliveryMode.AT_LEAST_ONCE,
        max_retries: int = 3,
    ):
        self._subscriptions: Dict[Type, List[SubscriptionInfo]] = defaultdict(list)
        self._all_subscriptions: List[SubscriptionInfo] = []
        self._delivery_mode = delivery_mode
        self._max_retries = max_retries
        self._statistics = BusStatistics()
        self._middleware: List[Callable] = []
    
    @property
    def statistics(self) -> BusStatistics:
        return self._statistics
    
    def add_middleware(
        self,
        middleware: Callable[[Any, Callable], Any],
    ) -> None:
        """Add middleware to the bus."""
        self._middleware.append(middleware)
    
    async def publish(
        self,
        event: Any,
        priority: EventPriority = EventPriority.NORMAL,
    ) -> PublishResult:
        """Publish an event to all subscribers."""
        event_type = type(event)
        event_id = str(uuid.uuid4())
        
        envelope = EventEnvelope(
            event_id=event_id,
            event_type=event_type.__name__,
            payload=event,
            priority=priority,
        )
        
        # Apply middleware
        processed_event = event
        for middleware in self._middleware:
            if asyncio.iscoroutinefunction(middleware):
                processed_event = await middleware(processed_event, lambda e: e)
            else:
                processed_event = middleware(processed_event, lambda e: e)
        
        # Get matching subscriptions
        handlers = self._get_handlers(event_type)
        
        # Sort by priority
        handlers.sort(key=lambda h: h.priority, reverse=True)
        
        delivered = 0
        failed = 0
        errors: List[str] = []
        
        for handler_info in handlers:
            if handler_info.state != SubscriptionState.ACTIVE:
                continue
            
            # Apply filter
            if handler_info.filter and not handler_info.filter(processed_event):
                continue
            
            try:
                handler = handler_info.handler
                if asyncio.iscoroutinefunction(handler):
                    await handler(processed_event)
                else:
                    handler(processed_event)
                
                handler_info.call_count += 1
                delivered += 1
                
            except Exception as e:
                failed += 1
                errors.append(str(e))
                logger.error(f"Handler error: {e}")
        
        self._statistics.events_published += 1
        self._statistics.events_delivered += delivered
        self._statistics.events_failed += failed
        
        return PublishResult(
            event_id=event_id,
            success=failed == 0,
            delivered_to=delivered,
            failed=failed,
            errors=errors,
        )
    
    async def publish_many(
        self,
        events: List[Any],
        priority: EventPriority = EventPriority.NORMAL,
    ) -> List[PublishResult]:
        """Publish multiple events."""
        results = []
        for event in events:
            result = await self.publish(event, priority)
            results.append(result)
        return results
    
    def subscribe(
        self,
        event_type: Type[E],
        handler: Callable[[E], Any],
        priority: int = 0,
        filter: Optional[Callable[[E], bool]] = None,
    ) -> Subscription:
        """Subscribe to an event type."""
        subscription_id = str(uuid.uuid4())
        
        info = SubscriptionInfo(
            id=subscription_id,
            event_type=event_type,
            handler=handler,
            priority=priority,
            filter=filter,
        )
        
        self._subscriptions[event_type].append(info)
        self._all_subscriptions.append(info)
        self._statistics.subscriptions_count += 1
        
        return Subscription(info, lambda: self.unsubscribe(subscription_id))
    
    def subscribe_all(
        self,
        handler: Callable[[Any], Any],
        priority: int = 0,
    ) -> Subscription:
        """Subscribe to all events."""
        subscription_id = str(uuid.uuid4())
        
        info = SubscriptionInfo(
            id=subscription_id,
            event_type=object,  # Match all
            handler=handler,
            priority=priority,
        )
        
        self._all_subscriptions.append(info)
        self._statistics.subscriptions_count += 1
        
        return Subscription(info, lambda: self.unsubscribe(subscription_id))
    
    def unsubscribe(self, subscription_id: str) -> None:
        """Unsubscribe from events."""
        for event_type, handlers in self._subscriptions.items():
            self._subscriptions[event_type] = [
                h for h in handlers if h.id != subscription_id
            ]
        
        self._all_subscriptions = [
            h for h in self._all_subscriptions if h.id != subscription_id
        ]
        
        self._statistics.subscriptions_count = len(self._all_subscriptions)
    
    def _get_handlers(
        self,
        event_type: Type,
    ) -> List[SubscriptionInfo]:
        """Get handlers for an event type."""
        handlers = list(self._subscriptions.get(event_type, []))
        
        # Add handlers for parent types
        for parent in event_type.__mro__[1:]:
            handlers.extend(self._subscriptions.get(parent, []))
        
        # Add wildcard handlers
        handlers.extend(
            h for h in self._all_subscriptions
            if h.event_type == object
        )
        
        return handlers
    
    def clear(self) -> None:
        """Clear all subscriptions."""
        self._subscriptions.clear()
        self._all_subscriptions.clear()
        self._statistics.subscriptions_count = 0


class AsyncEventBus(InMemoryEventBus):
    """
    Async event bus with background processing.
    """
    
    def __init__(
        self,
        max_queue_size: int = 1000,
        workers: int = 4,
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        self._workers: List[asyncio.Task] = []
        self._running = False
        self._num_workers = workers
    
    async def start(self) -> None:
        """Start the event bus."""
        if self._running:
            return
        
        self._running = True
        
        for _ in range(self._num_workers):
            task = asyncio.create_task(self._worker())
            self._workers.append(task)
        
        logger.info(f"Event bus started with {self._num_workers} workers")
    
    async def stop(self) -> None:
        """Stop the event bus."""
        if not self._running:
            return
        
        self._running = False
        
        # Cancel workers
        for worker in self._workers:
            worker.cancel()
        
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        
        logger.info("Event bus stopped")
    
    async def _worker(self) -> None:
        """Worker task for processing events."""
        while self._running:
            try:
                envelope = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=1.0,
                )
                
                await super().publish(
                    envelope.payload,
                    envelope.priority,
                )
                
                self._queue.task_done()
                
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker error: {e}")
    
    async def emit(
        self,
        event: Any,
        priority: EventPriority = EventPriority.NORMAL,
    ) -> str:
        """Emit an event for async processing."""
        event_id = str(uuid.uuid4())
        
        envelope = EventEnvelope(
            event_id=event_id,
            event_type=type(event).__name__,
            payload=event,
            priority=priority,
        )
        
        await self._queue.put(envelope)
        return event_id
    
    async def emit_sync(
        self,
        event: Any,
        priority: EventPriority = EventPriority.NORMAL,
    ) -> PublishResult:
        """Emit and wait for processing."""
        return await super().publish(event, priority)
    
    @property
    def queue_size(self) -> int:
        return self._queue.qsize()


class TopicEventBus(EventBus):
    """
    Topic-based event bus.
    """
    
    def __init__(self):
        self._topics: Dict[str, List[SubscriptionInfo]] = defaultdict(list)
        self._statistics = BusStatistics()
    
    async def publish(
        self,
        event: Any,
        priority: EventPriority = EventPriority.NORMAL,
        topic: Optional[str] = None,
    ) -> PublishResult:
        """Publish to a topic."""
        topic = topic or type(event).__name__
        event_id = str(uuid.uuid4())
        
        handlers = self._topics.get(topic, [])
        delivered = 0
        failed = 0
        errors: List[str] = []
        
        for handler_info in handlers:
            if handler_info.state != SubscriptionState.ACTIVE:
                continue
            
            try:
                handler = handler_info.handler
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
                
                delivered += 1
                
            except Exception as e:
                failed += 1
                errors.append(str(e))
        
        return PublishResult(
            event_id=event_id,
            success=failed == 0,
            delivered_to=delivered,
            failed=failed,
            errors=errors,
        )
    
    def subscribe(
        self,
        event_type: Type[E],
        handler: Callable[[E], Any],
        priority: int = 0,
        topic: Optional[str] = None,
    ) -> Subscription:
        """Subscribe to a topic."""
        topic = topic or event_type.__name__
        subscription_id = str(uuid.uuid4())
        
        info = SubscriptionInfo(
            id=subscription_id,
            event_type=event_type,
            handler=handler,
            priority=priority,
        )
        
        self._topics[topic].append(info)
        
        return Subscription(info, lambda: self._unsubscribe(topic, subscription_id))
    
    def subscribe_topic(
        self,
        topic: str,
        handler: Callable[[Any], Any],
        priority: int = 0,
    ) -> Subscription:
        """Subscribe to a topic by name."""
        subscription_id = str(uuid.uuid4())
        
        info = SubscriptionInfo(
            id=subscription_id,
            event_type=object,
            handler=handler,
            priority=priority,
        )
        
        self._topics[topic].append(info)
        
        return Subscription(info, lambda: self._unsubscribe(topic, subscription_id))
    
    def unsubscribe(self, subscription_id: str) -> None:
        """Unsubscribe from all topics."""
        for topic in self._topics:
            self._unsubscribe(topic, subscription_id)
    
    def _unsubscribe(self, topic: str, subscription_id: str) -> None:
        """Unsubscribe from a topic."""
        self._topics[topic] = [
            h for h in self._topics[topic] if h.id != subscription_id
        ]


class EventBusDecorator(EventBus):
    """
    Decorator for event bus.
    """
    
    def __init__(self, bus: EventBus):
        self._bus = bus
    
    async def publish(
        self,
        event: Any,
        priority: EventPriority = EventPriority.NORMAL,
    ) -> PublishResult:
        return await self._bus.publish(event, priority)
    
    def subscribe(
        self,
        event_type: Type[E],
        handler: Callable[[E], Any],
        priority: int = 0,
    ) -> Subscription:
        return self._bus.subscribe(event_type, handler, priority)
    
    def unsubscribe(self, subscription_id: str) -> None:
        self._bus.unsubscribe(subscription_id)


class LoggingEventBus(EventBusDecorator):
    """
    Event bus with logging.
    """
    
    async def publish(
        self,
        event: Any,
        priority: EventPriority = EventPriority.NORMAL,
    ) -> PublishResult:
        logger.info(f"Publishing event: {type(event).__name__}")
        result = await super().publish(event, priority)
        logger.info(f"Published to {result.delivered_to} handlers")
        return result
    
    def subscribe(
        self,
        event_type: Type[E],
        handler: Callable[[E], Any],
        priority: int = 0,
    ) -> Subscription:
        logger.info(f"Subscribing to: {event_type.__name__}")
        return super().subscribe(event_type, handler, priority)


class EventBusRegistry:
    """
    Registry for event buses.
    """
    
    def __init__(self):
        self._buses: Dict[str, EventBus] = {}
        self._default: Optional[str] = None
    
    def register(
        self,
        name: str,
        bus: EventBus,
        default: bool = False,
    ) -> None:
        """Register an event bus."""
        self._buses[name] = bus
        if default or self._default is None:
            self._default = name
    
    def get(self, name: Optional[str] = None) -> EventBus:
        """Get an event bus."""
        name = name or self._default
        if not name or name not in self._buses:
            raise EventBusError(f"Event bus not found: {name}")
        return self._buses[name]
    
    def default(self) -> Optional[EventBus]:
        """Get default bus."""
        if self._default:
            return self._buses.get(self._default)
        return None


# Global registry
_global_registry = EventBusRegistry()


# Decorators
def event_handler(event_type: Type[E]) -> Callable:
    """
    Decorator to create an event handler.
    
    Example:
        @event_handler(OrderCreated)
        async def handle_order_created(event: OrderCreated):
            print(f"Order: {event.order_id}")
    """
    def decorator(func: Callable[[E], Any]) -> Callable[[E], Any]:
        func._event_type = event_type
        return func
    
    return decorator


def subscribe(
    event_type: Type[E],
    bus_name: Optional[str] = None,
    priority: int = 0,
) -> Callable:
    """
    Decorator to subscribe a function to an event.
    
    Example:
        @subscribe(OrderCreated)
        async def on_order_created(event: OrderCreated):
            ...
    """
    def decorator(func: Callable[[E], Any]) -> Callable[[E], Any]:
        bus = _global_registry.get(bus_name)
        bus.subscribe(event_type, func, priority)
        return func
    
    return decorator


def on_event(bus: EventBus, priority: int = 0) -> Callable:
    """
    Decorator factory for subscribing to bus.
    
    Example:
        bus = create_event_bus()
        
        @on_event(bus)(OrderCreated)
        async def handle(event):
            ...
    """
    def event_decorator(event_type: Type[E]) -> Callable:
        def decorator(func: Callable[[E], Any]) -> Callable[[E], Any]:
            bus.subscribe(event_type, func, priority)
            return func
        return decorator
    
    return event_decorator


# Factory functions
def create_event_bus(
    delivery_mode: DeliveryMode = DeliveryMode.AT_LEAST_ONCE,
    max_retries: int = 3,
) -> InMemoryEventBus:
    """Create an in-memory event bus."""
    return InMemoryEventBus(delivery_mode, max_retries)


def create_async_event_bus(
    max_queue_size: int = 1000,
    workers: int = 4,
) -> AsyncEventBus:
    """Create an async event bus."""
    return AsyncEventBus(max_queue_size=max_queue_size, workers=workers)


def create_topic_event_bus() -> TopicEventBus:
    """Create a topic-based event bus."""
    return TopicEventBus()


def create_logging_event_bus(
    bus: Optional[EventBus] = None,
) -> LoggingEventBus:
    """Create a logging event bus."""
    if bus is None:
        bus = create_event_bus()
    return LoggingEventBus(bus)


def register_event_bus(
    name: str,
    bus: EventBus,
    default: bool = False,
) -> None:
    """Register event bus in global registry."""
    _global_registry.register(name, bus, default)


def get_event_bus(name: Optional[str] = None) -> EventBus:
    """Get event bus from global registry."""
    return _global_registry.get(name)


__all__ = [
    # Exceptions
    "EventBusError",
    "PublishError",
    "SubscriptionError",
    # Enums
    "DeliveryMode",
    "EventPriority",
    "SubscriptionState",
    # Data classes
    "EventEnvelope",
    "SubscriptionInfo",
    "PublishResult",
    "BusStatistics",
    # Core classes
    "EventHandler",
    "Subscription",
    # Event buses
    "EventBus",
    "InMemoryEventBus",
    "AsyncEventBus",
    "TopicEventBus",
    # Decorators (class)
    "EventBusDecorator",
    "LoggingEventBus",
    # Registry
    "EventBusRegistry",
    # Decorators (function)
    "event_handler",
    "subscribe",
    "on_event",
    # Factory functions
    "create_event_bus",
    "create_async_event_bus",
    "create_topic_event_bus",
    "create_logging_event_bus",
    "register_event_bus",
    "get_event_bus",
]
