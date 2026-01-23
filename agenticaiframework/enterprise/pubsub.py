"""
Enterprise Pub/Sub Module.

Provides event publishing, subscriptions, and topic-based
messaging for decoupled communication between components.

Example:
    # Create pubsub
    pubsub = create_pubsub()
    
    # Subscribe to events
    @subscribe("user.created")
    async def on_user_created(event: Event):
        print(f"New user: {event.data}")
    
    # Publish events
    await pubsub.publish("user.created", {"id": 1, "name": "John"})
    
    # Pattern matching
    @subscribe("order.*")  # Matches order.created, order.updated, etc.
    async def on_order_event(event: Event):
        ...
"""

from __future__ import annotations

import asyncio
import fnmatch
import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import (
    Any,
    Awaitable,
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


class PubSubError(Exception):
    """Pub/Sub error."""
    pass


class DeliveryMode(str, Enum):
    """Message delivery modes."""
    AT_MOST_ONCE = "at_most_once"
    AT_LEAST_ONCE = "at_least_once"
    EXACTLY_ONCE = "exactly_once"


class EventType(str, Enum):
    """Common event types."""
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Event:
    """Event message."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    topic: str = ""
    type: str = ""
    data: Any = None
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = ""
    correlation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "topic": self.topic,
            "type": self.type,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "correlation_id": self.correlation_id,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Event':
        """Create from dictionary."""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            topic=data.get("topic", ""),
            type=data.get("type", ""),
            data=data.get("data"),
            timestamp=datetime.fromisoformat(data["timestamp"]) if data.get("timestamp") else datetime.now(),
            source=data.get("source", ""),
            correlation_id=data.get("correlation_id"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class Subscription:
    """Subscription to a topic."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    pattern: str = ""
    handler: Callable[[Event], Awaitable[None]] = field(default=lambda e: asyncio.sleep(0))
    active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    event_count: int = 0
    last_event: Optional[datetime] = None


@dataclass
class Topic:
    """Topic definition."""
    name: str
    description: str = ""
    schema: Optional[Dict[str, Any]] = None
    retention_hours: int = 24
    created_at: datetime = field(default_factory=datetime.now)
    message_count: int = 0


@dataclass
class PubSubStats:
    """Pub/Sub statistics."""
    topics: int = 0
    subscriptions: int = 0
    events_published: int = 0
    events_delivered: int = 0
    events_failed: int = 0


class PubSub(ABC):
    """Abstract pub/sub interface."""
    
    @abstractmethod
    async def publish(
        self,
        topic: str,
        data: Any,
        event_type: str = "",
        **metadata: Any,
    ) -> Event:
        """Publish an event."""
        pass
    
    @abstractmethod
    async def subscribe(
        self,
        pattern: str,
        handler: Callable[[Event], Awaitable[None]],
    ) -> Subscription:
        """Subscribe to events matching pattern."""
        pass
    
    @abstractmethod
    async def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe from events."""
        pass
    
    @abstractmethod
    async def create_topic(
        self,
        name: str,
        description: str = "",
        schema: Optional[Dict[str, Any]] = None,
    ) -> Topic:
        """Create a topic."""
        pass
    
    @abstractmethod
    async def delete_topic(self, name: str) -> bool:
        """Delete a topic."""
        pass
    
    @abstractmethod
    async def get_stats(self) -> PubSubStats:
        """Get statistics."""
        pass


class InMemoryPubSub(PubSub):
    """In-memory pub/sub implementation."""
    
    def __init__(self, delivery_mode: DeliveryMode = DeliveryMode.AT_LEAST_ONCE):
        self._topics: Dict[str, Topic] = {}
        self._subscriptions: Dict[str, Subscription] = {}
        self._events: List[Event] = []
        self._delivery_mode = delivery_mode
        self._delivered_ids: Set[str] = set()
        self._stats = PubSubStats()
    
    async def publish(
        self,
        topic: str,
        data: Any,
        event_type: str = "",
        **metadata: Any,
    ) -> Event:
        """Publish an event."""
        event = Event(
            topic=topic,
            type=event_type,
            data=data,
            metadata=metadata,
        )
        
        self._events.append(event)
        self._stats.events_published += 1
        
        # Update topic stats
        if topic in self._topics:
            self._topics[topic].message_count += 1
        
        # Deliver to subscribers
        await self._deliver(event)
        
        logger.debug(f"Published event {event.id} to {topic}")
        return event
    
    async def _deliver(self, event: Event) -> None:
        """Deliver event to matching subscribers."""
        for sub in self._subscriptions.values():
            if not sub.active:
                continue
            
            if self._matches(event.topic, sub.pattern):
                # Check for exactly-once delivery
                delivery_id = f"{event.id}:{sub.id}"
                
                if self._delivery_mode == DeliveryMode.EXACTLY_ONCE:
                    if delivery_id in self._delivered_ids:
                        continue
                    self._delivered_ids.add(delivery_id)
                
                try:
                    await sub.handler(event)
                    sub.event_count += 1
                    sub.last_event = datetime.now()
                    self._stats.events_delivered += 1
                except Exception as e:
                    self._stats.events_failed += 1
                    logger.error(f"Handler error for {sub.pattern}: {e}")
                    
                    if self._delivery_mode == DeliveryMode.AT_LEAST_ONCE:
                        # Retry logic could go here
                        pass
    
    def _matches(self, topic: str, pattern: str) -> bool:
        """Check if topic matches pattern."""
        # Support wildcards: * for single level, # for multi-level
        pattern = pattern.replace("#", "**")
        return fnmatch.fnmatch(topic, pattern)
    
    async def subscribe(
        self,
        pattern: str,
        handler: Callable[[Event], Awaitable[None]],
    ) -> Subscription:
        """Subscribe to events."""
        sub = Subscription(
            pattern=pattern,
            handler=handler,
        )
        
        self._subscriptions[sub.id] = sub
        self._stats.subscriptions += 1
        
        logger.debug(f"Subscribed to {pattern}")
        return sub
    
    async def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe from events."""
        if subscription_id in self._subscriptions:
            del self._subscriptions[subscription_id]
            self._stats.subscriptions -= 1
            return True
        return False
    
    async def create_topic(
        self,
        name: str,
        description: str = "",
        schema: Optional[Dict[str, Any]] = None,
    ) -> Topic:
        """Create a topic."""
        topic = Topic(
            name=name,
            description=description,
            schema=schema,
        )
        
        self._topics[name] = topic
        self._stats.topics += 1
        
        return topic
    
    async def delete_topic(self, name: str) -> bool:
        """Delete a topic."""
        if name in self._topics:
            del self._topics[name]
            self._stats.topics -= 1
            return True
        return False
    
    async def get_stats(self) -> PubSubStats:
        """Get statistics."""
        return self._stats
    
    async def get_events(
        self,
        topic: Optional[str] = None,
        limit: int = 100,
    ) -> List[Event]:
        """Get recent events."""
        events = self._events
        
        if topic:
            events = [e for e in events if e.topic == topic]
        
        return events[-limit:]


class EventBus:
    """
    Event bus for local pub/sub within an application.
    """
    
    def __init__(self):
        self._handlers: Dict[str, List[Callable[[Event], Awaitable[None]]]] = {}
        self._middleware: List[Callable[[Event], Awaitable[Event]]] = []
    
    def on(
        self,
        event_type: str,
        handler: Callable[[Event], Awaitable[None]],
    ) -> None:
        """Register an event handler."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
    
    def off(
        self,
        event_type: str,
        handler: Optional[Callable[[Event], Awaitable[None]]] = None,
    ) -> None:
        """Remove an event handler."""
        if event_type in self._handlers:
            if handler:
                self._handlers[event_type] = [
                    h for h in self._handlers[event_type] if h != handler
                ]
            else:
                del self._handlers[event_type]
    
    def use(self, middleware: Callable[[Event], Awaitable[Event]]) -> None:
        """Add middleware."""
        self._middleware.append(middleware)
    
    async def emit(
        self,
        event_type: str,
        data: Any = None,
        **kwargs: Any,
    ) -> Event:
        """Emit an event."""
        event = Event(
            topic=event_type,
            type=event_type,
            data=data,
            **kwargs,
        )
        
        # Apply middleware
        for mw in self._middleware:
            event = await mw(event)
        
        # Call handlers
        handlers = self._handlers.get(event_type, [])
        handlers.extend(self._handlers.get("*", []))  # Wildcard handlers
        
        for handler in handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(f"Event handler error: {e}")
        
        return event
    
    async def emit_async(
        self,
        event_type: str,
        data: Any = None,
        **kwargs: Any,
    ) -> Event:
        """Emit an event asynchronously (fire and forget)."""
        event = Event(
            topic=event_type,
            type=event_type,
            data=data,
            **kwargs,
        )
        
        async def deliver():
            for mw in self._middleware:
                event = await mw(event)
            
            handlers = self._handlers.get(event_type, [])
            handlers.extend(self._handlers.get("*", []))
            
            await asyncio.gather(*[h(event) for h in handlers], return_exceptions=True)
        
        asyncio.create_task(deliver())
        return event


class Channel:
    """
    Broadcast channel for fan-out messaging.
    """
    
    def __init__(self, name: str):
        self.name = name
        self._listeners: List[asyncio.Queue] = []
    
    async def broadcast(self, data: Any) -> int:
        """Broadcast data to all listeners."""
        for queue in self._listeners:
            await queue.put(data)
        return len(self._listeners)
    
    async def listen(self) -> 'ChannelListener':
        """Create a new listener."""
        queue: asyncio.Queue = asyncio.Queue()
        self._listeners.append(queue)
        return ChannelListener(self, queue)
    
    def _remove_listener(self, queue: asyncio.Queue) -> None:
        """Remove a listener."""
        if queue in self._listeners:
            self._listeners.remove(queue)


class ChannelListener:
    """Listener for a channel."""
    
    def __init__(self, channel: Channel, queue: asyncio.Queue):
        self._channel = channel
        self._queue = queue
    
    async def receive(self, timeout: Optional[float] = None) -> Any:
        """Receive next message."""
        if timeout:
            return await asyncio.wait_for(self._queue.get(), timeout)
        return await self._queue.get()
    
    def close(self) -> None:
        """Stop listening."""
        self._channel._remove_listener(self._queue)
    
    def __aiter__(self):
        return self
    
    async def __anext__(self) -> Any:
        try:
            return await self._queue.get()
        except asyncio.CancelledError:
            raise StopAsyncIteration


# Global instances
_pubsub_instance: Optional[PubSub] = None
_event_bus_instance: Optional[EventBus] = None
_subscriptions: Dict[str, Callable] = {}


def subscribe(
    pattern: str,
    pubsub: Optional[PubSub] = None,
) -> Callable:
    """
    Decorator to subscribe to events.
    
    Example:
        @subscribe("user.created")
        async def on_user_created(event: Event):
            ...
    """
    def decorator(func: Callable[[Event], Awaitable[None]]) -> Callable:
        _subscriptions[pattern] = func
        
        async def register():
            ps = pubsub or _pubsub_instance
            if ps:
                await ps.subscribe(pattern, func)
        
        # Schedule registration
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(register())
        except RuntimeError:
            # No running loop, will register later
            pass
        
        return func
    
    return decorator


def on_event(event_type: str) -> Callable:
    """
    Decorator to handle events on the event bus.
    
    Example:
        @on_event("task.completed")
        async def handle_task_completed(event: Event):
            ...
    """
    def decorator(func: Callable[[Event], Awaitable[None]]) -> Callable:
        bus = _event_bus_instance
        if bus:
            bus.on(event_type, func)
        return func
    
    return decorator


def create_pubsub(
    provider: str = "memory",
    delivery_mode: DeliveryMode = DeliveryMode.AT_LEAST_ONCE,
    **kwargs: Any,
) -> PubSub:
    """
    Factory function to create a pub/sub instance.
    """
    global _pubsub_instance
    
    if provider == "memory":
        _pubsub_instance = InMemoryPubSub(delivery_mode)
    else:
        raise ValueError(f"Unknown pubsub provider: {provider}")
    
    return _pubsub_instance


def create_event_bus() -> EventBus:
    """Create an event bus."""
    global _event_bus_instance
    _event_bus_instance = EventBus()
    return _event_bus_instance


def create_channel(name: str) -> Channel:
    """Create a broadcast channel."""
    return Channel(name)


async def publish(
    topic: str,
    data: Any,
    **kwargs: Any,
) -> Event:
    """Publish an event using the global pub/sub."""
    pubsub = _pubsub_instance or create_pubsub()
    return await pubsub.publish(topic, data, **kwargs)


async def emit(event_type: str, data: Any = None, **kwargs: Any) -> Event:
    """Emit an event on the global event bus."""
    bus = _event_bus_instance or create_event_bus()
    return await bus.emit(event_type, data, **kwargs)


__all__ = [
    # Exceptions
    "PubSubError",
    # Enums
    "DeliveryMode",
    "EventType",
    # Data classes
    "Event",
    "Subscription",
    "Topic",
    "PubSubStats",
    # PubSub
    "PubSub",
    "InMemoryPubSub",
    # EventBus
    "EventBus",
    # Channel
    "Channel",
    "ChannelListener",
    # Decorators
    "subscribe",
    "on_event",
    # Factory
    "create_pubsub",
    "create_event_bus",
    "create_channel",
    # Helpers
    "publish",
    "emit",
]
