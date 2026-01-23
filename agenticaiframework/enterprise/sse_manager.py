"""
Enterprise SSE (Server-Sent Events) Manager Module.

Provides server-sent events streaming, real-time push notifications,
event channels, and connection management.

Example:
    # Create SSE manager
    sse = create_sse_manager()
    
    # Create channel
    channel = await sse.create_channel("notifications")
    
    # Subscribe client
    @app.get("/events/{user_id}")
    async def events(user_id: str):
        async for event in sse.subscribe(f"user:{user_id}"):
            yield event.to_sse()
    
    # Publish event
    await sse.publish(
        channel="notifications",
        event="message",
        data={"text": "Hello!"},
    )
"""

from __future__ import annotations

import asyncio
import functools
import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import (
    Any,
    AsyncIterator,
    Awaitable,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    Tuple,
    TypeVar,
    Union,
)

T = TypeVar('T')


logger = logging.getLogger(__name__)


class SSEError(Exception):
    """SSE error."""
    pass


class ConnectionState(str, Enum):
    """Connection states."""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    RECONNECTING = "reconnecting"


@dataclass
class SSEEvent:
    """Server-sent event."""
    event: str = "message"
    data: Any = None
    id: Optional[str] = None
    retry: Optional[int] = None
    comment: Optional[str] = None
    
    def to_sse(self) -> str:
        """Convert to SSE format."""
        lines = []
        
        if self.comment:
            lines.append(f": {self.comment}")
        
        if self.id:
            lines.append(f"id: {self.id}")
        
        if self.event != "message":
            lines.append(f"event: {self.event}")
        
        if self.retry:
            lines.append(f"retry: {self.retry}")
        
        if self.data is not None:
            if isinstance(self.data, str):
                data_str = self.data
            else:
                data_str = json.dumps(self.data)
            
            # Split multiline data
            for line in data_str.split("\n"):
                lines.append(f"data: {line}")
        
        lines.append("")
        lines.append("")
        
        return "\n".join(lines)


@dataclass
class Subscription:
    """Client subscription."""
    id: str
    channel: str
    client_id: str
    queue: asyncio.Queue
    filters: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_event_id: Optional[str] = None


@dataclass
class Channel:
    """Event channel."""
    name: str
    description: str = ""
    max_subscribers: int = 10000
    history_size: int = 100
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ChannelStats:
    """Channel statistics."""
    name: str
    subscriber_count: int
    message_count: int
    bytes_sent: int
    created_at: datetime


@dataclass
class ConnectionInfo:
    """Client connection info."""
    client_id: str
    subscriptions: List[str]
    connected_at: datetime
    last_activity: datetime
    messages_received: int
    state: ConnectionState


class EventStore(ABC):
    """Abstract event store for history."""
    
    @abstractmethod
    async def store(self, channel: str, event: SSEEvent) -> None:
        """Store event."""
        pass
    
    @abstractmethod
    async def get_after(
        self,
        channel: str,
        after_id: str,
    ) -> List[SSEEvent]:
        """Get events after ID."""
        pass
    
    @abstractmethod
    async def get_recent(
        self,
        channel: str,
        limit: int = 100,
    ) -> List[SSEEvent]:
        """Get recent events."""
        pass


class InMemoryEventStore(EventStore):
    """In-memory event store."""
    
    def __init__(self, max_events: int = 1000):
        self._events: Dict[str, List[SSEEvent]] = defaultdict(list)
        self._max_events = max_events
    
    async def store(self, channel: str, event: SSEEvent) -> None:
        events = self._events[channel]
        events.append(event)
        
        # Trim if needed
        if len(events) > self._max_events:
            self._events[channel] = events[-self._max_events:]
    
    async def get_after(
        self,
        channel: str,
        after_id: str,
    ) -> List[SSEEvent]:
        events = self._events.get(channel, [])
        
        # Find index of after_id
        found_idx = -1
        for i, event in enumerate(events):
            if event.id == after_id:
                found_idx = i
                break
        
        if found_idx >= 0:
            return events[found_idx + 1:]
        return []
    
    async def get_recent(
        self,
        channel: str,
        limit: int = 100,
    ) -> List[SSEEvent]:
        events = self._events.get(channel, [])
        return events[-limit:]


class EventFilter(ABC):
    """Event filter."""
    
    @abstractmethod
    def matches(self, event: SSEEvent) -> bool:
        """Check if event matches filter."""
        pass


class EventTypeFilter(EventFilter):
    """Filter by event type."""
    
    def __init__(self, event_types: List[str]):
        self._event_types = set(event_types)
    
    def matches(self, event: SSEEvent) -> bool:
        return event.event in self._event_types


class DataFilter(EventFilter):
    """Filter by data content."""
    
    def __init__(self, predicate: Callable[[Any], bool]):
        self._predicate = predicate
    
    def matches(self, event: SSEEvent) -> bool:
        return self._predicate(event.data)


class SSEManager:
    """
    Server-Sent Events manager.
    """
    
    def __init__(
        self,
        event_store: Optional[EventStore] = None,
        heartbeat_interval: float = 30.0,
    ):
        self._event_store = event_store or InMemoryEventStore()
        self._heartbeat_interval = heartbeat_interval
        
        self._channels: Dict[str, Channel] = {}
        self._subscriptions: Dict[str, Subscription] = {}
        self._client_subscriptions: Dict[str, Set[str]] = defaultdict(set)
        self._channel_subscriptions: Dict[str, Set[str]] = defaultdict(set)
        
        self._stats: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {"messages": 0, "bytes": 0}
        )
        
        self._running = False
        self._heartbeat_task: Optional[asyncio.Task] = None
    
    async def start(self) -> None:
        """Start SSE manager."""
        if self._running:
            return
        
        self._running = True
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info("SSE Manager started")
    
    async def stop(self) -> None:
        """Stop SSE manager."""
        if not self._running:
            return
        
        self._running = False
        
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        
        # Close all subscriptions
        for sub_id in list(self._subscriptions.keys()):
            await self.unsubscribe(sub_id)
        
        logger.info("SSE Manager stopped")
    
    async def _heartbeat_loop(self) -> None:
        """Send heartbeats to all subscribers."""
        while self._running:
            await asyncio.sleep(self._heartbeat_interval)
            
            heartbeat = SSEEvent(
                comment="heartbeat",
            )
            
            for channel_name in self._channels:
                await self._broadcast_to_channel(channel_name, heartbeat)
    
    # Channel management
    async def create_channel(
        self,
        name: str,
        description: str = "",
        max_subscribers: int = 10000,
        history_size: int = 100,
    ) -> Channel:
        """Create event channel."""
        if name in self._channels:
            return self._channels[name]
        
        channel = Channel(
            name=name,
            description=description,
            max_subscribers=max_subscribers,
            history_size=history_size,
        )
        
        self._channels[name] = channel
        logger.debug(f"Created channel: {name}")
        
        return channel
    
    async def delete_channel(self, name: str) -> bool:
        """Delete channel."""
        if name not in self._channels:
            return False
        
        # Unsubscribe all clients from this channel
        for sub_id in list(self._channel_subscriptions.get(name, set())):
            await self.unsubscribe(sub_id)
        
        del self._channels[name]
        self._channel_subscriptions.pop(name, None)
        
        logger.debug(f"Deleted channel: {name}")
        return True
    
    def get_channel(self, name: str) -> Optional[Channel]:
        """Get channel by name."""
        return self._channels.get(name)
    
    def list_channels(self) -> List[Channel]:
        """List all channels."""
        return list(self._channels.values())
    
    # Subscription management
    async def subscribe(
        self,
        channel: str,
        client_id: Optional[str] = None,
        last_event_id: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[SSEEvent]:
        """
        Subscribe to channel and yield events.
        
        Usage:
            async for event in sse.subscribe("notifications"):
                yield event.to_sse()
        """
        # Create channel if not exists
        if channel not in self._channels:
            await self.create_channel(channel)
        
        # Check subscriber limit
        channel_obj = self._channels[channel]
        if len(self._channel_subscriptions.get(channel, set())) >= channel_obj.max_subscribers:
            raise SSEError(f"Channel {channel} has reached max subscribers")
        
        # Create subscription
        sub_id = str(uuid.uuid4())
        client_id = client_id or str(uuid.uuid4())
        
        subscription = Subscription(
            id=sub_id,
            channel=channel,
            client_id=client_id,
            queue=asyncio.Queue(),
            filters=filters or {},
            last_event_id=last_event_id,
        )
        
        self._subscriptions[sub_id] = subscription
        self._client_subscriptions[client_id].add(sub_id)
        self._channel_subscriptions[channel].add(sub_id)
        
        logger.debug(f"Client {client_id} subscribed to {channel}")
        
        try:
            # Replay missed events if last_event_id provided
            if last_event_id:
                missed = await self._event_store.get_after(channel, last_event_id)
                for event in missed:
                    yield event
            
            # Stream new events
            while self._running:
                try:
                    event = await asyncio.wait_for(
                        subscription.queue.get(),
                        timeout=self._heartbeat_interval,
                    )
                    subscription.last_event_id = event.id
                    yield event
                except asyncio.TimeoutError:
                    # Send heartbeat
                    yield SSEEvent(comment="heartbeat")
                    
        finally:
            await self.unsubscribe(sub_id)
    
    async def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe from channel."""
        if subscription_id not in self._subscriptions:
            return False
        
        subscription = self._subscriptions.pop(subscription_id)
        
        self._client_subscriptions[subscription.client_id].discard(subscription_id)
        if not self._client_subscriptions[subscription.client_id]:
            del self._client_subscriptions[subscription.client_id]
        
        self._channel_subscriptions[subscription.channel].discard(subscription_id)
        
        logger.debug(
            f"Client {subscription.client_id} unsubscribed from {subscription.channel}"
        )
        
        return True
    
    async def unsubscribe_client(self, client_id: str) -> int:
        """Unsubscribe client from all channels."""
        sub_ids = list(self._client_subscriptions.get(client_id, set()))
        count = 0
        
        for sub_id in sub_ids:
            if await self.unsubscribe(sub_id):
                count += 1
        
        return count
    
    # Publishing
    async def publish(
        self,
        channel: str,
        event: str = "message",
        data: Any = None,
        event_id: Optional[str] = None,
    ) -> int:
        """
        Publish event to channel.
        
        Returns number of subscribers that received the event.
        """
        if channel not in self._channels:
            await self.create_channel(channel)
        
        sse_event = SSEEvent(
            event=event,
            data=data,
            id=event_id or str(uuid.uuid4()),
        )
        
        # Store in history
        await self._event_store.store(channel, sse_event)
        
        # Broadcast
        count = await self._broadcast_to_channel(channel, sse_event)
        
        # Update stats
        self._stats[channel]["messages"] += 1
        self._stats[channel]["bytes"] += len(sse_event.to_sse())
        
        return count
    
    async def _broadcast_to_channel(
        self,
        channel: str,
        event: SSEEvent,
    ) -> int:
        """Broadcast event to channel subscribers."""
        sub_ids = self._channel_subscriptions.get(channel, set())
        count = 0
        
        for sub_id in sub_ids:
            subscription = self._subscriptions.get(sub_id)
            if subscription:
                try:
                    subscription.queue.put_nowait(event)
                    count += 1
                except asyncio.QueueFull:
                    logger.warning(
                        f"Queue full for subscription {sub_id}"
                    )
        
        return count
    
    async def broadcast(
        self,
        event: str = "message",
        data: Any = None,
        event_id: Optional[str] = None,
    ) -> int:
        """Broadcast event to all channels."""
        total = 0
        
        for channel in self._channels:
            count = await self.publish(channel, event, data, event_id)
            total += count
        
        return total
    
    # Statistics
    def get_channel_stats(self, channel: str) -> Optional[ChannelStats]:
        """Get channel statistics."""
        if channel not in self._channels:
            return None
        
        channel_obj = self._channels[channel]
        stats = self._stats.get(channel, {"messages": 0, "bytes": 0})
        
        return ChannelStats(
            name=channel,
            subscriber_count=len(self._channel_subscriptions.get(channel, set())),
            message_count=stats["messages"],
            bytes_sent=stats["bytes"],
            created_at=channel_obj.created_at,
        )
    
    def get_client_info(self, client_id: str) -> Optional[ConnectionInfo]:
        """Get client connection info."""
        sub_ids = self._client_subscriptions.get(client_id)
        if not sub_ids:
            return None
        
        subscriptions = [
            self._subscriptions[sub_id].channel
            for sub_id in sub_ids
            if sub_id in self._subscriptions
        ]
        
        # Get earliest subscription time
        connected_at = min(
            self._subscriptions[sub_id].created_at
            for sub_id in sub_ids
            if sub_id in self._subscriptions
        )
        
        return ConnectionInfo(
            client_id=client_id,
            subscriptions=subscriptions,
            connected_at=connected_at,
            last_activity=datetime.utcnow(),
            messages_received=0,
            state=ConnectionState.CONNECTED,
        )


class SSEClient:
    """
    SSE client for consuming events.
    """
    
    def __init__(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        reconnect_interval: float = 3.0,
    ):
        self._url = url
        self._headers = headers or {}
        self._reconnect_interval = reconnect_interval
        
        self._running = False
        self._last_event_id: Optional[str] = None
    
    async def connect(self) -> AsyncIterator[SSEEvent]:
        """Connect and stream events."""
        self._running = True
        
        while self._running:
            try:
                async for event in self._stream_events():
                    self._last_event_id = event.id
                    yield event
                    
            except Exception as e:
                logger.warning(f"SSE connection error: {e}")
                
                if self._running:
                    await asyncio.sleep(self._reconnect_interval)
    
    async def _stream_events(self) -> AsyncIterator[SSEEvent]:
        """Stream events from server (simplified)."""
        # In real implementation, would use httpx or aiohttp
        # This is a placeholder
        while self._running:
            await asyncio.sleep(1)
            yield SSEEvent(event="ping")
    
    def disconnect(self) -> None:
        """Disconnect from server."""
        self._running = False


# Decorators
def sse_endpoint(
    channel: str,
    content_type: str = "text/event-stream",
) -> Callable:
    """Decorator to create SSE endpoint."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Get SSE manager from context or create new one
            sse = kwargs.pop("sse_manager", None) or create_sse_manager()
            
            # Call original function to get client info
            result = await func(*args, **kwargs)
            client_id = result.get("client_id") if isinstance(result, dict) else None
            
            # Return event stream
            async def event_stream():
                async for event in sse.subscribe(channel, client_id=client_id):
                    yield event.to_sse()
            
            return event_stream()
        
        wrapper._sse_channel = channel
        wrapper._sse_content_type = content_type
        return wrapper
    
    return decorator


def on_event(event_type: str) -> Callable:
    """Decorator to handle specific event types."""
    def decorator(func: Callable) -> Callable:
        func._sse_event_type = event_type
        return func
    return decorator


# Factory functions
def create_sse_manager(
    heartbeat_interval: float = 30.0,
    event_store: Optional[EventStore] = None,
) -> SSEManager:
    """Create SSE manager."""
    return SSEManager(
        event_store=event_store,
        heartbeat_interval=heartbeat_interval,
    )


def create_sse_client(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    reconnect_interval: float = 3.0,
) -> SSEClient:
    """Create SSE client."""
    return SSEClient(
        url=url,
        headers=headers,
        reconnect_interval=reconnect_interval,
    )


def create_in_memory_store(max_events: int = 1000) -> InMemoryEventStore:
    """Create in-memory event store."""
    return InMemoryEventStore(max_events)


def create_event(
    event: str = "message",
    data: Any = None,
    event_id: Optional[str] = None,
) -> SSEEvent:
    """Create SSE event."""
    return SSEEvent(
        event=event,
        data=data,
        id=event_id,
    )


def create_event_type_filter(event_types: List[str]) -> EventTypeFilter:
    """Create event type filter."""
    return EventTypeFilter(event_types)


def create_data_filter(
    predicate: Callable[[Any], bool],
) -> DataFilter:
    """Create data filter."""
    return DataFilter(predicate)


__all__ = [
    # Exceptions
    "SSEError",
    # Enums
    "ConnectionState",
    # Data classes
    "SSEEvent",
    "Subscription",
    "Channel",
    "ChannelStats",
    "ConnectionInfo",
    # Event store
    "EventStore",
    "InMemoryEventStore",
    # Filters
    "EventFilter",
    "EventTypeFilter",
    "DataFilter",
    # Manager/Client
    "SSEManager",
    "SSEClient",
    # Decorators
    "sse_endpoint",
    "on_event",
    # Factory functions
    "create_sse_manager",
    "create_sse_client",
    "create_in_memory_store",
    "create_event",
    "create_event_type_filter",
    "create_data_filter",
]
