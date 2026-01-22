"""
Enterprise Events - Pub/Sub event system for component communication.

Events provide a decoupled way for components to communicate and react
to changes in the system.

Features:
- Event publishing
- Event subscription
- Event filtering
- Async event handlers
- Event history
- Event replay
"""

import asyncio
import functools
import logging
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
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
    Type,
    TypeVar,
    Union,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


# =============================================================================
# Event Types
# =============================================================================

class EventType(Enum):
    """Standard event types."""
    # Agent events
    AGENT_CREATED = "agent.created"
    AGENT_STARTED = "agent.started"
    AGENT_COMPLETED = "agent.completed"
    AGENT_FAILED = "agent.failed"
    AGENT_STEP = "agent.step"
    
    # Workflow events
    WORKFLOW_STARTED = "workflow.started"
    WORKFLOW_COMPLETED = "workflow.completed"
    WORKFLOW_FAILED = "workflow.failed"
    WORKFLOW_STEP = "workflow.step"
    
    # Tool events
    TOOL_CALLED = "tool.called"
    TOOL_COMPLETED = "tool.completed"
    TOOL_FAILED = "tool.failed"
    
    # LLM events
    LLM_REQUEST = "llm.request"
    LLM_RESPONSE = "llm.response"
    LLM_ERROR = "llm.error"
    LLM_STREAMING = "llm.streaming"
    
    # Storage events
    ARTIFACT_SAVED = "artifact.saved"
    ARTIFACT_LOADED = "artifact.loaded"
    
    # System events
    SYSTEM_ERROR = "system.error"
    SYSTEM_WARNING = "system.warning"
    SYSTEM_INFO = "system.info"
    
    # Custom events
    CUSTOM = "custom"


@dataclass
class Event:
    """An event in the system."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: Union[EventType, str] = EventType.CUSTOM
    source: str = ""
    data: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    correlation_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value if isinstance(self.type, EventType) else self.type,
            "source": self.source,
            "data": self.data,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
            "correlation_id": self.correlation_id,
        }


# =============================================================================
# Event Handler Types
# =============================================================================

EventHandler = Callable[[Event], Awaitable[None]]
EventFilter = Callable[[Event], bool]


@dataclass
class Subscription:
    """A subscription to events."""
    id: str
    event_types: Set[Union[EventType, str]]
    handler: EventHandler
    filter_fn: Optional[EventFilter] = None
    priority: int = 0
    once: bool = False
    
    def matches(self, event: Event) -> bool:
        """Check if event matches subscription."""
        # Check type
        event_type = event.type.value if isinstance(event.type, EventType) else event.type
        
        if self.event_types:
            type_match = False
            for sub_type in self.event_types:
                sub_type_value = sub_type.value if isinstance(sub_type, EventType) else sub_type
                if sub_type_value == event_type or sub_type_value == "*":
                    type_match = True
                    break
            
            if not type_match:
                return False
        
        # Check filter
        if self.filter_fn and not self.filter_fn(event):
            return False
        
        return True


# =============================================================================
# Event Bus
# =============================================================================

class EventBus:
    """
    Central event bus for pub/sub communication.
    
    Usage:
        >>> bus = EventBus()
        >>> 
        >>> @bus.subscribe(EventType.AGENT_COMPLETED)
        >>> async def on_agent_complete(event: Event):
        ...     print(f"Agent completed: {event.data}")
        >>> 
        >>> await bus.publish(Event(
        ...     type=EventType.AGENT_COMPLETED,
        ...     source="my-agent",
        ...     data={"result": "success"},
        ... ))
    """
    
    def __init__(
        self,
        max_history: int = 1000,
        enable_history: bool = True,
    ):
        self._subscriptions: List[Subscription] = []
        self._history: List[Event] = []
        self.max_history = max_history
        self.enable_history = enable_history
        self._lock = asyncio.Lock()
    
    def subscribe(
        self,
        *event_types: Union[EventType, str],
        filter_fn: Optional[EventFilter] = None,
        priority: int = 0,
        once: bool = False,
    ):
        """
        Decorator to subscribe to events.
        
        Args:
            event_types: Event types to subscribe to
            filter_fn: Optional filter function
            priority: Handler priority (higher = earlier)
            once: Only trigger once then unsubscribe
        """
        def decorator(handler: EventHandler) -> EventHandler:
            sub = Subscription(
                id=str(uuid.uuid4()),
                event_types=set(event_types) if event_types else {"*"},
                handler=handler,
                filter_fn=filter_fn,
                priority=priority,
                once=once,
            )
            self._subscriptions.append(sub)
            self._subscriptions.sort(key=lambda s: -s.priority)
            return handler
        return decorator
    
    def add_handler(
        self,
        handler: EventHandler,
        *event_types: Union[EventType, str],
        filter_fn: Optional[EventFilter] = None,
        priority: int = 0,
        once: bool = False,
    ) -> str:
        """Add an event handler programmatically."""
        sub = Subscription(
            id=str(uuid.uuid4()),
            event_types=set(event_types) if event_types else {"*"},
            handler=handler,
            filter_fn=filter_fn,
            priority=priority,
            once=once,
        )
        self._subscriptions.append(sub)
        self._subscriptions.sort(key=lambda s: -s.priority)
        return sub.id
    
    def remove_handler(self, subscription_id: str) -> bool:
        """Remove a handler by subscription ID."""
        for i, sub in enumerate(self._subscriptions):
            if sub.id == subscription_id:
                self._subscriptions.pop(i)
                return True
        return False
    
    async def publish(
        self,
        event: Event,
        wait: bool = True,
    ):
        """
        Publish an event to all subscribers.
        
        Args:
            event: Event to publish
            wait: Wait for all handlers to complete
        """
        # Store in history
        if self.enable_history:
            async with self._lock:
                self._history.append(event)
                if len(self._history) > self.max_history:
                    self._history = self._history[-self.max_history:]
        
        # Find matching subscriptions
        to_remove = []
        handlers = []
        
        for sub in self._subscriptions:
            if sub.matches(event):
                handlers.append(sub.handler)
                if sub.once:
                    to_remove.append(sub.id)
        
        # Remove one-time handlers
        for sub_id in to_remove:
            self.remove_handler(sub_id)
        
        # Execute handlers
        if wait:
            for handler in handlers:
                try:
                    await handler(event)
                except Exception as e:
                    logger.error(f"Event handler error: {e}")
        else:
            for handler in handlers:
                asyncio.create_task(self._safe_call(handler, event))
    
    async def _safe_call(self, handler: EventHandler, event: Event):
        """Safely call a handler."""
        try:
            await handler(event)
        except Exception as e:
            logger.error(f"Event handler error: {e}")
    
    def emit(
        self,
        event_type: Union[EventType, str],
        source: str = "",
        data: Any = None,
        correlation_id: Optional[str] = None,
        **metadata,
    ) -> Event:
        """
        Create and schedule an event for publishing.
        
        Returns the event (which will be published asynchronously).
        """
        event = Event(
            type=event_type,
            source=source,
            data=data,
            metadata=metadata,
            correlation_id=correlation_id,
        )
        
        asyncio.create_task(self.publish(event, wait=False))
        return event
    
    async def emit_and_wait(
        self,
        event_type: Union[EventType, str],
        source: str = "",
        data: Any = None,
        correlation_id: Optional[str] = None,
        **metadata,
    ) -> Event:
        """Create and publish an event, waiting for handlers."""
        event = Event(
            type=event_type,
            source=source,
            data=data,
            metadata=metadata,
            correlation_id=correlation_id,
        )
        
        await self.publish(event, wait=True)
        return event
    
    def get_history(
        self,
        event_type: Optional[Union[EventType, str]] = None,
        source: Optional[str] = None,
        limit: int = 100,
    ) -> List[Event]:
        """Get event history with optional filtering."""
        events = self._history
        
        if event_type:
            type_value = event_type.value if isinstance(event_type, EventType) else event_type
            events = [e for e in events if (
                (e.type.value if isinstance(e.type, EventType) else e.type) == type_value
            )]
        
        if source:
            events = [e for e in events if e.source == source]
        
        return events[-limit:]
    
    async def replay(
        self,
        events: List[Event],
        delay: float = 0.0,
    ):
        """Replay a list of events."""
        for event in events:
            await self.publish(event)
            if delay > 0:
                await asyncio.sleep(delay)
    
    def clear_history(self):
        """Clear event history."""
        self._history.clear()
    
    def clear_handlers(self):
        """Clear all handlers."""
        self._subscriptions.clear()


# =============================================================================
# Event Aggregator
# =============================================================================

class EventAggregator:
    """
    Aggregates events over a time window.
    
    Usage:
        >>> aggregator = EventAggregator(window_seconds=60)
        >>> 
        >>> @aggregator.on_aggregate(EventType.AGENT_COMPLETED)
        >>> async def on_batch(events: List[Event]):
        ...     print(f"Received {len(events)} completions")
    """
    
    def __init__(
        self,
        bus: EventBus,
        window_seconds: float = 60.0,
        max_batch_size: int = 100,
    ):
        self.bus = bus
        self.window_seconds = window_seconds
        self.max_batch_size = max_batch_size
        
        self._buffers: Dict[str, List[Event]] = defaultdict(list)
        self._handlers: Dict[str, List[Callable]] = defaultdict(list)
        self._timers: Dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()
    
    def on_aggregate(
        self,
        *event_types: Union[EventType, str],
    ):
        """Decorator to handle aggregated events."""
        def decorator(handler: Callable[[List[Event]], Awaitable[None]]):
            for event_type in event_types:
                type_key = event_type.value if isinstance(event_type, EventType) else event_type
                self._handlers[type_key].append(handler)
                
                # Subscribe to events
                @self.bus.subscribe(event_type)
                async def on_event(event: Event, key=type_key):
                    await self._add_to_buffer(key, event)
            
            return handler
        return decorator
    
    async def _add_to_buffer(self, type_key: str, event: Event):
        """Add event to buffer and potentially flush."""
        async with self._lock:
            self._buffers[type_key].append(event)
            
            # Check if we should flush
            if len(self._buffers[type_key]) >= self.max_batch_size:
                await self._flush(type_key)
            elif type_key not in self._timers or self._timers[type_key].done():
                # Start timer
                self._timers[type_key] = asyncio.create_task(
                    self._timer_flush(type_key)
                )
    
    async def _timer_flush(self, type_key: str):
        """Flush after timer expires."""
        await asyncio.sleep(self.window_seconds)
        async with self._lock:
            await self._flush(type_key)
    
    async def _flush(self, type_key: str):
        """Flush buffer to handlers."""
        events = self._buffers[type_key]
        self._buffers[type_key] = []
        
        if events:
            for handler in self._handlers[type_key]:
                try:
                    await handler(events)
                except Exception as e:
                    logger.error(f"Aggregation handler error: {e}")


# =============================================================================
# Event Store
# =============================================================================

class EventStore(ABC):
    """Abstract event store for event sourcing."""
    
    @abstractmethod
    async def append(self, event: Event) -> str:
        """Append an event to the store."""
        pass
    
    @abstractmethod
    async def get(self, event_id: str) -> Optional[Event]:
        """Get an event by ID."""
        pass
    
    @abstractmethod
    async def query(
        self,
        event_type: Optional[str] = None,
        source: Optional[str] = None,
        correlation_id: Optional[str] = None,
        after: Optional[datetime] = None,
        before: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Event]:
        """Query events with filters."""
        pass


class InMemoryEventStore(EventStore):
    """In-memory event store."""
    
    def __init__(self, max_events: int = 10000):
        self._events: Dict[str, Event] = {}
        self._order: List[str] = []
        self.max_events = max_events
        self._lock = asyncio.Lock()
    
    async def append(self, event: Event) -> str:
        async with self._lock:
            self._events[event.id] = event
            self._order.append(event.id)
            
            # Evict old events
            while len(self._order) > self.max_events:
                old_id = self._order.pop(0)
                del self._events[old_id]
        
        return event.id
    
    async def get(self, event_id: str) -> Optional[Event]:
        return self._events.get(event_id)
    
    async def query(
        self,
        event_type: Optional[str] = None,
        source: Optional[str] = None,
        correlation_id: Optional[str] = None,
        after: Optional[datetime] = None,
        before: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Event]:
        results = []
        
        for event_id in reversed(self._order):
            if len(results) >= limit:
                break
            
            event = self._events.get(event_id)
            if not event:
                continue
            
            # Apply filters
            if event_type:
                type_value = event.type.value if isinstance(event.type, EventType) else event.type
                if type_value != event_type:
                    continue
            
            if source and event.source != source:
                continue
            
            if correlation_id and event.correlation_id != correlation_id:
                continue
            
            if after and event.timestamp <= after:
                continue
            
            if before and event.timestamp >= before:
                continue
            
            results.append(event)
        
        return results


# =============================================================================
# Typed Events
# =============================================================================

class TypedEvent(Generic[T]):
    """
    Typed event for type-safe event handling.
    
    Usage:
        >>> user_created = TypedEvent[UserData]("user.created")
        >>> 
        >>> @user_created.handler
        >>> async def on_user_created(data: UserData):
        ...     print(f"User created: {data.name}")
        >>> 
        >>> await user_created.emit(UserData(name="John"))
    """
    
    def __init__(self, event_type: str, bus: Optional[EventBus] = None):
        self.event_type = event_type
        self.bus = bus or global_event_bus
        self._handlers: List[Callable[[T], Awaitable[None]]] = []
    
    def handler(self, fn: Callable[[T], Awaitable[None]]) -> Callable[[T], Awaitable[None]]:
        """Decorator to register a typed handler."""
        self._handlers.append(fn)
        
        @self.bus.subscribe(self.event_type)
        async def wrapper(event: Event):
            await fn(event.data)
        
        return fn
    
    async def emit(
        self,
        data: T,
        source: str = "",
        correlation_id: Optional[str] = None,
        **metadata,
    ):
        """Emit a typed event."""
        await self.bus.emit_and_wait(
            self.event_type,
            source=source,
            data=data,
            correlation_id=correlation_id,
            **metadata,
        )


# =============================================================================
# Global Event Bus
# =============================================================================

global_event_bus = EventBus()


def on_event(*event_types: Union[EventType, str]):
    """Global decorator for subscribing to events."""
    return global_event_bus.subscribe(*event_types)


async def emit_event(
    event_type: Union[EventType, str],
    source: str = "",
    data: Any = None,
    **metadata,
):
    """Emit an event on the global bus."""
    return await global_event_bus.emit_and_wait(
        event_type,
        source=source,
        data=data,
        **metadata,
    )


# Convenience functions for common events
async def emit_agent_started(agent_name: str, **data):
    """Emit agent started event."""
    await emit_event(EventType.AGENT_STARTED, source=agent_name, data=data)


async def emit_agent_completed(agent_name: str, result: Any, **data):
    """Emit agent completed event."""
    await emit_event(
        EventType.AGENT_COMPLETED,
        source=agent_name,
        data={"result": result, **data},
    )


async def emit_agent_failed(agent_name: str, error: str, **data):
    """Emit agent failed event."""
    await emit_event(
        EventType.AGENT_FAILED,
        source=agent_name,
        data={"error": error, **data},
    )


async def emit_tool_called(tool_name: str, args: Dict, **data):
    """Emit tool called event."""
    await emit_event(
        EventType.TOOL_CALLED,
        source=tool_name,
        data={"args": args, **data},
    )


async def emit_llm_request(model: str, prompt: str, **data):
    """Emit LLM request event."""
    await emit_event(
        EventType.LLM_REQUEST,
        source=model,
        data={"prompt": prompt[:500], **data},  # Truncate for logging
    )
