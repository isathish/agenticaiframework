"""
Enterprise Outbox Pattern Module.

Provides transactional outbox pattern for reliable messaging,
event publishing, and eventual consistency.

Example:
    # Create outbox
    outbox = create_outbox()
    
    # Store event in transaction
    async with transaction():
        await save_order(order)
        await outbox.store(OrderCreatedEvent(order_id=order.id))
    
    # Relay worker publishes events
    relay = create_outbox_relay(outbox, publisher)
    await relay.start()
    
    # With decorator
    @with_outbox(outbox)
    async def create_order(order: Order):
        await save_order(order)
        return OrderCreatedEvent(order_id=order.id)
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
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
    TypeVar,
)

logger = logging.getLogger(__name__)

T = TypeVar('T')


class OutboxError(Exception):
    """Outbox error."""
    pass


class PublishError(OutboxError):
    """Publish failed."""
    pass


class OutboxStatus(str, Enum):
    """Outbox entry status."""
    PENDING = "pending"
    PROCESSING = "processing"
    PUBLISHED = "published"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


@dataclass
class OutboxEntry:
    """Outbox entry representing an event to be published."""
    id: str
    event_type: str
    payload: Dict[str, Any]
    status: OutboxStatus = OutboxStatus.PENDING
    aggregate_id: Optional[str] = None
    aggregate_type: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    processed_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 5
    next_retry_at: Optional[datetime] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "event_type": self.event_type,
            "payload": self.payload,
            "status": self.status.value,
            "aggregate_id": self.aggregate_id,
            "aggregate_type": self.aggregate_type,
            "created_at": self.created_at.isoformat(),
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "retry_count": self.retry_count,
            "metadata": self.metadata,
        }


@dataclass
class OutboxStats:
    """Outbox statistics."""
    total_entries: int = 0
    pending: int = 0
    processing: int = 0
    published: int = 0
    failed: int = 0
    dead_letter: int = 0
    last_published_at: Optional[datetime] = None


class OutboxStore(ABC):
    """Abstract outbox store."""
    
    @abstractmethod
    async def save(self, entry: OutboxEntry) -> None:
        """Save outbox entry."""
        pass
    
    @abstractmethod
    async def get_pending(
        self,
        limit: int = 100,
    ) -> List[OutboxEntry]:
        """Get pending entries."""
        pass
    
    @abstractmethod
    async def mark_processing(
        self,
        entry_id: str,
    ) -> bool:
        """Mark entry as processing."""
        pass
    
    @abstractmethod
    async def mark_published(
        self,
        entry_id: str,
    ) -> bool:
        """Mark entry as published."""
        pass
    
    @abstractmethod
    async def mark_failed(
        self,
        entry_id: str,
        error: str,
    ) -> bool:
        """Mark entry as failed."""
        pass
    
    @abstractmethod
    async def get_stats(self) -> OutboxStats:
        """Get outbox statistics."""
        pass


class InMemoryOutboxStore(OutboxStore):
    """In-memory outbox store."""
    
    def __init__(self):
        self._entries: Dict[str, OutboxEntry] = {}
        self._lock = asyncio.Lock()
    
    async def save(self, entry: OutboxEntry) -> None:
        async with self._lock:
            self._entries[entry.id] = entry
    
    async def get_pending(
        self,
        limit: int = 100,
    ) -> List[OutboxEntry]:
        now = datetime.now()
        pending = []
        
        for entry in self._entries.values():
            if entry.status == OutboxStatus.PENDING:
                pending.append(entry)
            elif entry.status == OutboxStatus.FAILED:
                if entry.next_retry_at and entry.next_retry_at <= now:
                    if entry.retry_count < entry.max_retries:
                        pending.append(entry)
        
        # Sort by created_at
        pending.sort(key=lambda e: e.created_at)
        
        return pending[:limit]
    
    async def mark_processing(
        self,
        entry_id: str,
    ) -> bool:
        async with self._lock:
            entry = self._entries.get(entry_id)
            if entry:
                entry.status = OutboxStatus.PROCESSING
                return True
            return False
    
    async def mark_published(
        self,
        entry_id: str,
    ) -> bool:
        async with self._lock:
            entry = self._entries.get(entry_id)
            if entry:
                entry.status = OutboxStatus.PUBLISHED
                entry.processed_at = datetime.now()
                return True
            return False
    
    async def mark_failed(
        self,
        entry_id: str,
        error: str,
    ) -> bool:
        async with self._lock:
            entry = self._entries.get(entry_id)
            if entry:
                entry.status = OutboxStatus.FAILED
                entry.error_message = error
                entry.retry_count += 1
                
                # Calculate next retry with exponential backoff
                delay = min(60 * (2 ** entry.retry_count), 3600)  # Max 1 hour
                entry.next_retry_at = datetime.now() + timedelta(seconds=delay)
                
                # Move to dead letter if max retries exceeded
                if entry.retry_count >= entry.max_retries:
                    entry.status = OutboxStatus.DEAD_LETTER
                
                return True
            return False
    
    async def get_stats(self) -> OutboxStats:
        stats = OutboxStats(total_entries=len(self._entries))
        
        for entry in self._entries.values():
            if entry.status == OutboxStatus.PENDING:
                stats.pending += 1
            elif entry.status == OutboxStatus.PROCESSING:
                stats.processing += 1
            elif entry.status == OutboxStatus.PUBLISHED:
                stats.published += 1
                if entry.processed_at:
                    if not stats.last_published_at or entry.processed_at > stats.last_published_at:
                        stats.last_published_at = entry.processed_at
            elif entry.status == OutboxStatus.FAILED:
                stats.failed += 1
            elif entry.status == OutboxStatus.DEAD_LETTER:
                stats.dead_letter += 1
        
        return stats
    
    async def get_dead_letters(
        self,
        limit: int = 100,
    ) -> List[OutboxEntry]:
        """Get dead letter entries."""
        dead_letters = [
            e for e in self._entries.values()
            if e.status == OutboxStatus.DEAD_LETTER
        ]
        return dead_letters[:limit]
    
    async def retry_dead_letter(
        self,
        entry_id: str,
    ) -> bool:
        """Retry a dead letter entry."""
        async with self._lock:
            entry = self._entries.get(entry_id)
            if entry and entry.status == OutboxStatus.DEAD_LETTER:
                entry.status = OutboxStatus.PENDING
                entry.retry_count = 0
                entry.next_retry_at = None
                entry.error_message = None
                return True
            return False


class EventPublisher(ABC):
    """Abstract event publisher."""
    
    @abstractmethod
    async def publish(
        self,
        event_type: str,
        payload: Dict[str, Any],
        metadata: Dict[str, Any],
    ) -> None:
        """Publish an event."""
        pass


class LoggingPublisher(EventPublisher):
    """Publisher that logs events (for testing)."""
    
    async def publish(
        self,
        event_type: str,
        payload: Dict[str, Any],
        metadata: Dict[str, Any],
    ) -> None:
        logger.info(f"Published event: {event_type}")
        logger.debug(f"Payload: {json.dumps(payload)}")


class CallbackPublisher(EventPublisher):
    """Publisher that calls a callback."""
    
    def __init__(
        self,
        callback: Callable[[str, Dict[str, Any], Dict[str, Any]], None],
    ):
        self._callback = callback
    
    async def publish(
        self,
        event_type: str,
        payload: Dict[str, Any],
        metadata: Dict[str, Any],
    ) -> None:
        if asyncio.iscoroutinefunction(self._callback):
            await self._callback(event_type, payload, metadata)
        else:
            self._callback(event_type, payload, metadata)


class Outbox:
    """
    Transactional outbox for reliable event publishing.
    """
    
    def __init__(
        self,
        store: OutboxStore,
    ):
        self._store = store
    
    async def store(
        self,
        event_type: str,
        payload: Dict[str, Any],
        aggregate_id: Optional[str] = None,
        aggregate_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> OutboxEntry:
        """Store an event in the outbox."""
        entry = OutboxEntry(
            id=str(uuid.uuid4()),
            event_type=event_type,
            payload=payload,
            aggregate_id=aggregate_id,
            aggregate_type=aggregate_type,
            metadata=metadata or {},
        )
        
        await self._store.save(entry)
        
        logger.debug(f"Stored outbox entry: {entry.id}")
        
        return entry
    
    async def store_event(
        self,
        event: Any,
    ) -> OutboxEntry:
        """Store an event object in the outbox."""
        event_type = type(event).__name__
        
        if hasattr(event, "to_dict"):
            payload = event.to_dict()
        elif hasattr(event, "__dict__"):
            payload = {
                k: v for k, v in event.__dict__.items()
                if not k.startswith("_")
            }
        else:
            payload = {"data": str(event)}
        
        aggregate_id = getattr(event, "aggregate_id", None)
        aggregate_type = getattr(event, "aggregate_type", None)
        
        return await self.store(
            event_type=event_type,
            payload=payload,
            aggregate_id=aggregate_id,
            aggregate_type=aggregate_type,
        )
    
    async def get_stats(self) -> OutboxStats:
        """Get outbox statistics."""
        return await self._store.get_stats()


class OutboxRelay:
    """
    Relay worker that publishes outbox entries.
    """
    
    def __init__(
        self,
        outbox: Outbox,
        publisher: EventPublisher,
        batch_size: int = 100,
        poll_interval_seconds: float = 1.0,
    ):
        self._outbox = outbox
        self._publisher = publisher
        self._batch_size = batch_size
        self._poll_interval = poll_interval_seconds
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    async def start(self) -> None:
        """Start the relay worker."""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._relay_loop())
        
        logger.info("Outbox relay started")
    
    async def stop(self) -> None:
        """Stop the relay worker."""
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        logger.info("Outbox relay stopped")
    
    async def _relay_loop(self) -> None:
        """Main relay loop."""
        while self._running:
            try:
                await self._process_batch()
                await asyncio.sleep(self._poll_interval)
            
            except asyncio.CancelledError:
                break
            
            except Exception as e:
                logger.error(f"Relay error: {e}")
                await asyncio.sleep(self._poll_interval)
    
    async def _process_batch(self) -> int:
        """Process a batch of outbox entries."""
        entries = await self._outbox._store.get_pending(self._batch_size)
        
        if not entries:
            return 0
        
        published = 0
        
        for entry in entries:
            try:
                # Mark as processing
                await self._outbox._store.mark_processing(entry.id)
                
                # Publish
                await self._publisher.publish(
                    entry.event_type,
                    entry.payload,
                    entry.metadata,
                )
                
                # Mark as published
                await self._outbox._store.mark_published(entry.id)
                published += 1
                
                logger.debug(f"Published entry: {entry.id}")
            
            except Exception as e:
                logger.error(f"Failed to publish entry {entry.id}: {e}")
                await self._outbox._store.mark_failed(entry.id, str(e))
        
        return published
    
    async def process_once(self) -> int:
        """Process one batch (for manual triggering)."""
        return await self._process_batch()


class OutboxPoller:
    """
    Polls outbox and processes entries on demand.
    """
    
    def __init__(
        self,
        outbox: Outbox,
        publisher: EventPublisher,
    ):
        self._outbox = outbox
        self._publisher = publisher
    
    async def poll_and_publish(
        self,
        limit: int = 100,
    ) -> int:
        """Poll and publish pending entries."""
        entries = await self._outbox._store.get_pending(limit)
        
        published = 0
        
        for entry in entries:
            try:
                await self._outbox._store.mark_processing(entry.id)
                
                await self._publisher.publish(
                    entry.event_type,
                    entry.payload,
                    entry.metadata,
                )
                
                await self._outbox._store.mark_published(entry.id)
                published += 1
            
            except Exception as e:
                await self._outbox._store.mark_failed(entry.id, str(e))
        
        return published


class TransactionalOutbox:
    """
    High-level outbox with transactional support.
    """
    
    def __init__(
        self,
        store: OutboxStore,
        publisher: EventPublisher,
    ):
        self._outbox = Outbox(store)
        self._relay = OutboxRelay(self._outbox, publisher)
        self._pending_events: List[Any] = []
    
    async def add_event(self, event: Any) -> None:
        """Add event to pending (will be stored on commit)."""
        self._pending_events.append(event)
    
    async def commit(self) -> List[OutboxEntry]:
        """Commit pending events to outbox."""
        entries = []
        
        for event in self._pending_events:
            entry = await self._outbox.store_event(event)
            entries.append(entry)
        
        self._pending_events.clear()
        
        return entries
    
    async def rollback(self) -> None:
        """Rollback pending events."""
        self._pending_events.clear()
    
    async def start_relay(self) -> None:
        """Start the relay worker."""
        await self._relay.start()
    
    async def stop_relay(self) -> None:
        """Stop the relay worker."""
        await self._relay.stop()
    
    async def __aenter__(self) -> 'TransactionalOutbox':
        return self
    
    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[Exception],
        exc_tb: Any,
    ) -> None:
        if exc_type:
            await self.rollback()
        else:
            await self.commit()


# Decorators
def with_outbox(
    outbox: Outbox,
) -> Callable:
    """
    Decorator to store function result in outbox.
    
    Example:
        @with_outbox(outbox)
        async def create_order(order: Order) -> OrderCreatedEvent:
            await save_order(order)
            return OrderCreatedEvent(order_id=order.id)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = await func(*args, **kwargs)
            
            if result is not None:
                await outbox.store_event(result)
            
            return result
        
        return wrapper
    
    return decorator


def outbox_event(
    event_type: Optional[str] = None,
) -> Callable:
    """
    Decorator to mark a class as an outbox event.
    
    Example:
        @outbox_event("order_created")
        @dataclass
        class OrderCreatedEvent:
            order_id: str
    """
    def decorator(cls: type) -> type:
        cls._outbox_event_type = event_type or cls.__name__
        return cls
    
    return decorator


def transactional(
    outbox: TransactionalOutbox,
) -> Callable:
    """
    Decorator for transactional operations with outbox.
    
    Example:
        @transactional(outbox)
        async def process_order(order: Order):
            await save_order(order)
            await outbox.add_event(OrderCreatedEvent(order.id))
            # Automatically committed on success, rolled back on error
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            async with outbox:
                return await func(*args, **kwargs)
        
        return wrapper
    
    return decorator


# Factory functions
def create_outbox(
    store: Optional[OutboxStore] = None,
) -> Outbox:
    """Create an outbox."""
    s = store or InMemoryOutboxStore()
    return Outbox(s)


def create_outbox_relay(
    outbox: Outbox,
    publisher: EventPublisher,
    batch_size: int = 100,
    poll_interval: float = 1.0,
) -> OutboxRelay:
    """Create an outbox relay."""
    return OutboxRelay(outbox, publisher, batch_size, poll_interval)


def create_transactional_outbox(
    store: Optional[OutboxStore] = None,
    publisher: Optional[EventPublisher] = None,
) -> TransactionalOutbox:
    """Create a transactional outbox."""
    s = store or InMemoryOutboxStore()
    p = publisher or LoggingPublisher()
    return TransactionalOutbox(s, p)


def create_callback_publisher(
    callback: Callable[[str, Dict[str, Any], Dict[str, Any]], None],
) -> CallbackPublisher:
    """Create a callback publisher."""
    return CallbackPublisher(callback)


__all__ = [
    # Exceptions
    "OutboxError",
    "PublishError",
    # Enums
    "OutboxStatus",
    # Data classes
    "OutboxEntry",
    "OutboxStats",
    # Core classes
    "OutboxStore",
    "InMemoryOutboxStore",
    "EventPublisher",
    "LoggingPublisher",
    "CallbackPublisher",
    "Outbox",
    "OutboxRelay",
    "OutboxPoller",
    "TransactionalOutbox",
    # Decorators
    "with_outbox",
    "outbox_event",
    "transactional",
    # Factory functions
    "create_outbox",
    "create_outbox_relay",
    "create_transactional_outbox",
    "create_callback_publisher",
]
