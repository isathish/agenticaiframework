"""
Enterprise Dead Letter Queue Module.

Provides dead letter queue patterns, failed message handling,
poison message detection, and retry management.

Example:
    # Create dead letter queue
    dlq = create_dead_letter_queue()
    
    # Add failed message
    await dlq.add(message, error=exception)
    
    # Reprocess messages
    async for message in dlq.drain():
        try:
            await process(message)
        except Exception as e:
            await dlq.add(message, error=e)
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
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


logger = logging.getLogger(__name__)


class DeadLetterError(Exception):
    """Dead letter error."""
    pass


class PoisonMessageError(DeadLetterError):
    """Poison message error - message cannot be processed."""
    pass


class MaxRetriesExceeded(DeadLetterError):
    """Maximum retries exceeded."""
    pass


class FailureReason(str, Enum):
    """Failure reason categories."""
    PROCESSING_ERROR = "processing_error"
    VALIDATION_ERROR = "validation_error"
    TIMEOUT = "timeout"
    SERIALIZATION_ERROR = "serialization_error"
    NETWORK_ERROR = "network_error"
    AUTHORIZATION_ERROR = "authorization_error"
    RESOURCE_NOT_FOUND = "resource_not_found"
    POISON_MESSAGE = "poison_message"
    UNKNOWN = "unknown"


class MessageStatus(str, Enum):
    """Dead letter message status."""
    PENDING = "pending"
    REPROCESSING = "reprocessing"
    RESOLVED = "resolved"
    DISCARDED = "discarded"
    ARCHIVED = "archived"


@dataclass
class FailureContext:
    """Context about a message failure."""
    reason: FailureReason
    error_type: str
    error_message: str
    stack_trace: Optional[str] = None
    attempt_number: int = 1
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DeadLetterMessage:
    """A message in the dead letter queue."""
    id: str
    original_topic: str
    payload: Any
    failures: List[FailureContext] = field(default_factory=list)
    status: MessageStatus = MessageStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    retry_count: int = 0
    max_retries: int = 3
    next_retry_at: Optional[datetime] = None
    headers: Dict[str, str] = field(default_factory=dict)
    
    @property
    def is_poison(self) -> bool:
        """Check if message is a poison message."""
        return self.retry_count >= self.max_retries
    
    @property
    def last_failure(self) -> Optional[FailureContext]:
        """Get the last failure context."""
        return self.failures[-1] if self.failures else None
    
    def add_failure(self, context: FailureContext) -> None:
        """Add a failure context."""
        self.failures.append(context)
        self.retry_count += 1
        self.updated_at = datetime.now()


@dataclass
class RetryPolicy:
    """Retry policy configuration."""
    max_retries: int = 3
    initial_delay: float = 1.0
    max_delay: float = 3600.0
    multiplier: float = 2.0
    jitter: bool = True
    
    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for attempt."""
        import random
        
        delay = min(
            self.initial_delay * (self.multiplier ** attempt),
            self.max_delay,
        )
        
        if self.jitter:
            delay = delay * (0.5 + random.random())
        
        return delay


@dataclass
class DeadLetterStats:
    """Dead letter queue statistics."""
    total_messages: int = 0
    pending_count: int = 0
    reprocessing_count: int = 0
    resolved_count: int = 0
    discarded_count: int = 0
    poison_count: int = 0
    by_reason: Dict[str, int] = field(default_factory=dict)
    by_topic: Dict[str, int] = field(default_factory=dict)


class DeadLetterStore(ABC):
    """
    Abstract dead letter storage.
    """
    
    @abstractmethod
    async def save(self, message: DeadLetterMessage) -> None:
        """Save a dead letter message."""
        pass
    
    @abstractmethod
    async def get(self, message_id: str) -> Optional[DeadLetterMessage]:
        """Get a message by ID."""
        pass
    
    @abstractmethod
    async def list_pending(
        self,
        topic: Optional[str] = None,
        limit: int = 100,
    ) -> List[DeadLetterMessage]:
        """List pending messages."""
        pass
    
    @abstractmethod
    async def list_ready_for_retry(
        self,
        limit: int = 100,
    ) -> List[DeadLetterMessage]:
        """List messages ready for retry."""
        pass
    
    @abstractmethod
    async def update_status(
        self,
        message_id: str,
        status: MessageStatus,
    ) -> None:
        """Update message status."""
        pass
    
    @abstractmethod
    async def delete(self, message_id: str) -> None:
        """Delete a message."""
        pass
    
    @abstractmethod
    async def get_stats(self) -> DeadLetterStats:
        """Get queue statistics."""
        pass


class InMemoryDeadLetterStore(DeadLetterStore):
    """
    In-memory dead letter store.
    """
    
    def __init__(self):
        self._messages: Dict[str, DeadLetterMessage] = {}
    
    async def save(self, message: DeadLetterMessage) -> None:
        self._messages[message.id] = message
    
    async def get(self, message_id: str) -> Optional[DeadLetterMessage]:
        return self._messages.get(message_id)
    
    async def list_pending(
        self,
        topic: Optional[str] = None,
        limit: int = 100,
    ) -> List[DeadLetterMessage]:
        messages = [
            m for m in self._messages.values()
            if m.status == MessageStatus.PENDING
            and (topic is None or m.original_topic == topic)
        ]
        return sorted(messages, key=lambda m: m.created_at)[:limit]
    
    async def list_ready_for_retry(
        self,
        limit: int = 100,
    ) -> List[DeadLetterMessage]:
        now = datetime.now()
        messages = [
            m for m in self._messages.values()
            if m.status == MessageStatus.PENDING
            and not m.is_poison
            and (m.next_retry_at is None or m.next_retry_at <= now)
        ]
        return sorted(messages, key=lambda m: m.created_at)[:limit]
    
    async def update_status(
        self,
        message_id: str,
        status: MessageStatus,
    ) -> None:
        if message_id in self._messages:
            self._messages[message_id].status = status
            self._messages[message_id].updated_at = datetime.now()
    
    async def delete(self, message_id: str) -> None:
        self._messages.pop(message_id, None)
    
    async def get_stats(self) -> DeadLetterStats:
        stats = DeadLetterStats()
        
        for message in self._messages.values():
            stats.total_messages += 1
            
            if message.status == MessageStatus.PENDING:
                stats.pending_count += 1
            elif message.status == MessageStatus.REPROCESSING:
                stats.reprocessing_count += 1
            elif message.status == MessageStatus.RESOLVED:
                stats.resolved_count += 1
            elif message.status == MessageStatus.DISCARDED:
                stats.discarded_count += 1
            
            if message.is_poison:
                stats.poison_count += 1
            
            # By reason
            if message.last_failure:
                reason = message.last_failure.reason.value
                stats.by_reason[reason] = stats.by_reason.get(reason, 0) + 1
            
            # By topic
            topic = message.original_topic
            stats.by_topic[topic] = stats.by_topic.get(topic, 0) + 1
        
        return stats


class FailureClassifier:
    """
    Classifies failures into categories.
    """
    
    def __init__(self):
        self._rules: List[tuple] = []
    
    def add_rule(
        self,
        exception_type: Type[Exception],
        reason: FailureReason,
    ) -> None:
        """Add classification rule."""
        self._rules.append((exception_type, reason))
    
    def classify(self, error: Exception) -> FailureReason:
        """Classify an exception."""
        for exc_type, reason in self._rules:
            if isinstance(error, exc_type):
                return reason
        
        # Default classifications
        error_name = type(error).__name__.lower()
        
        if 'timeout' in error_name:
            return FailureReason.TIMEOUT
        elif 'validation' in error_name:
            return FailureReason.VALIDATION_ERROR
        elif 'auth' in error_name or 'permission' in error_name:
            return FailureReason.AUTHORIZATION_ERROR
        elif 'notfound' in error_name or 'not_found' in error_name:
            return FailureReason.RESOURCE_NOT_FOUND
        elif 'connection' in error_name or 'network' in error_name:
            return FailureReason.NETWORK_ERROR
        elif 'serial' in error_name or 'json' in error_name:
            return FailureReason.SERIALIZATION_ERROR
        
        return FailureReason.UNKNOWN


class DeadLetterQueue:
    """
    Dead letter queue for failed messages.
    """
    
    def __init__(
        self,
        store: DeadLetterStore,
        retry_policy: Optional[RetryPolicy] = None,
        classifier: Optional[FailureClassifier] = None,
    ):
        self._store = store
        self._retry_policy = retry_policy or RetryPolicy()
        self._classifier = classifier or FailureClassifier()
        self._handlers: Dict[FailureReason, List[Callable]] = defaultdict(list)
    
    async def add(
        self,
        payload: Any,
        topic: str,
        error: Exception,
        headers: Optional[Dict[str, str]] = None,
        message_id: Optional[str] = None,
    ) -> DeadLetterMessage:
        """Add a failed message to the queue."""
        import traceback
        
        reason = self._classifier.classify(error)
        
        failure = FailureContext(
            reason=reason,
            error_type=type(error).__name__,
            error_message=str(error),
            stack_trace=traceback.format_exc(),
        )
        
        # Check if message already exists
        existing = None
        if message_id:
            existing = await self._store.get(message_id)
        
        if existing:
            existing.add_failure(failure)
            self._schedule_retry(existing)
            await self._store.save(existing)
            message = existing
        else:
            message = DeadLetterMessage(
                id=message_id or str(uuid.uuid4()),
                original_topic=topic,
                payload=payload,
                failures=[failure],
                max_retries=self._retry_policy.max_retries,
                headers=headers or {},
            )
            self._schedule_retry(message)
            await self._store.save(message)
        
        # Notify handlers
        await self._notify_handlers(message, failure)
        
        logger.warning(
            f"Added to dead letter queue: {message.id} "
            f"(reason={reason.value}, retries={message.retry_count})"
        )
        
        return message
    
    def _schedule_retry(self, message: DeadLetterMessage) -> None:
        """Schedule retry for message."""
        if message.is_poison:
            message.next_retry_at = None
        else:
            delay = self._retry_policy.calculate_delay(message.retry_count)
            message.next_retry_at = datetime.now() + timedelta(seconds=delay)
    
    async def _notify_handlers(
        self,
        message: DeadLetterMessage,
        failure: FailureContext,
    ) -> None:
        """Notify failure handlers."""
        handlers = self._handlers.get(failure.reason, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(message, failure)
                else:
                    handler(message, failure)
            except Exception as e:
                logger.error(f"Handler error: {e}")
    
    def on_failure(
        self,
        reason: FailureReason,
        handler: Callable,
    ) -> Callable[[], None]:
        """Register failure handler."""
        self._handlers[reason].append(handler)
        
        def unregister():
            self._handlers[reason].remove(handler)
        
        return unregister
    
    async def get(self, message_id: str) -> Optional[DeadLetterMessage]:
        """Get a dead letter message."""
        return await self._store.get(message_id)
    
    async def resolve(self, message_id: str) -> None:
        """Mark message as resolved."""
        await self._store.update_status(message_id, MessageStatus.RESOLVED)
        logger.info(f"Resolved dead letter message: {message_id}")
    
    async def discard(self, message_id: str) -> None:
        """Discard a message."""
        await self._store.update_status(message_id, MessageStatus.DISCARDED)
        logger.info(f"Discarded dead letter message: {message_id}")
    
    async def archive(self, message_id: str) -> None:
        """Archive a message."""
        await self._store.update_status(message_id, MessageStatus.ARCHIVED)
        logger.info(f"Archived dead letter message: {message_id}")
    
    async def list_pending(
        self,
        topic: Optional[str] = None,
        limit: int = 100,
    ) -> List[DeadLetterMessage]:
        """List pending messages."""
        return await self._store.list_pending(topic, limit)
    
    async def list_poison(
        self,
        limit: int = 100,
    ) -> List[DeadLetterMessage]:
        """List poison messages."""
        pending = await self._store.list_pending(limit=limit * 2)
        return [m for m in pending if m.is_poison][:limit]
    
    async def drain(
        self,
        limit: int = 100,
    ) -> AsyncIterator[DeadLetterMessage]:
        """Drain messages ready for retry."""
        messages = await self._store.list_ready_for_retry(limit)
        for message in messages:
            message.status = MessageStatus.REPROCESSING
            await self._store.save(message)
            yield message
    
    async def stats(self) -> DeadLetterStats:
        """Get queue statistics."""
        return await self._store.get_stats()


class DeadLetterProcessor:
    """
    Processes dead letter queue messages.
    """
    
    def __init__(
        self,
        queue: DeadLetterQueue,
        handler: Callable[[DeadLetterMessage], Any],
        batch_size: int = 10,
        poll_interval: float = 5.0,
    ):
        self._queue = queue
        self._handler = handler
        self._batch_size = batch_size
        self._poll_interval = poll_interval
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    async def start(self) -> None:
        """Start the processor."""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._process_loop())
        logger.info("Dead letter processor started")
    
    async def stop(self) -> None:
        """Stop the processor."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Dead letter processor stopped")
    
    async def _process_loop(self) -> None:
        """Main processing loop."""
        while self._running:
            try:
                processed = 0
                async for message in self._queue.drain(self._batch_size):
                    try:
                        if asyncio.iscoroutinefunction(self._handler):
                            await self._handler(message)
                        else:
                            self._handler(message)
                        
                        await self._queue.resolve(message.id)
                        processed += 1
                    except Exception as e:
                        await self._queue.add(
                            message.payload,
                            message.original_topic,
                            e,
                            message.headers,
                            message.id,
                        )
                
                if processed == 0:
                    await asyncio.sleep(self._poll_interval)
                    
            except Exception as e:
                logger.error(f"Processing error: {e}")
                await asyncio.sleep(self._poll_interval)


class PoisonMessageHandler:
    """
    Handles poison messages.
    """
    
    def __init__(
        self,
        queue: DeadLetterQueue,
    ):
        self._queue = queue
        self._handlers: List[Callable] = []
    
    def register(
        self,
        handler: Callable[[DeadLetterMessage], Any],
    ) -> None:
        """Register a poison message handler."""
        self._handlers.append(handler)
    
    async def process(self) -> int:
        """Process poison messages."""
        poison = await self._queue.list_poison()
        processed = 0
        
        for message in poison:
            for handler in self._handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(message)
                    else:
                        handler(message)
                except Exception as e:
                    logger.error(f"Poison handler error: {e}")
            
            await self._queue.archive(message.id)
            processed += 1
        
        return processed


class DeadLetterRegistry:
    """
    Registry for dead letter queues.
    """
    
    def __init__(self):
        self._queues: Dict[str, DeadLetterQueue] = {}
    
    def register(self, name: str, queue: DeadLetterQueue) -> None:
        """Register a queue."""
        self._queues[name] = queue
    
    def get(self, name: str) -> DeadLetterQueue:
        """Get a queue."""
        if name not in self._queues:
            raise DeadLetterError(f"Queue not found: {name}")
        return self._queues[name]
    
    def list(self) -> List[str]:
        """List registered queues."""
        return list(self._queues.keys())


# Global registry
_global_registry = DeadLetterRegistry()


# Decorators
def on_dead_letter(
    reason: FailureReason,
    queue_name: Optional[str] = None,
) -> Callable:
    """
    Decorator to handle dead letter failures.
    
    Example:
        @on_dead_letter(FailureReason.PROCESSING_ERROR)
        async def handle_processing_error(message, failure):
            ...
    """
    def decorator(func: Callable) -> Callable:
        func._dlq_reason = reason
        func._dlq_name = queue_name
        return func
    
    return decorator


def retry_on_failure(
    max_retries: int = 3,
    queue: Optional[DeadLetterQueue] = None,
) -> Callable:
    """
    Decorator to automatically retry and dead letter on failure.
    
    Example:
        @retry_on_failure(max_retries=3)
        async def process_message(message):
            ...
    """
    def decorator(func: Callable) -> Callable:
        async def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    if asyncio.iscoroutinefunction(func):
                        return await func(*args, **kwargs)
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        if queue:
                            await queue.add(
                                args[0] if args else kwargs,
                                "unknown",
                                e,
                            )
                        raise
        
        return wrapper
    
    return decorator


# Factory functions
def create_dead_letter_queue(
    store: Optional[DeadLetterStore] = None,
    max_retries: int = 3,
    initial_delay: float = 1.0,
) -> DeadLetterQueue:
    """Create a dead letter queue."""
    return DeadLetterQueue(
        store=store or InMemoryDeadLetterStore(),
        retry_policy=RetryPolicy(
            max_retries=max_retries,
            initial_delay=initial_delay,
        ),
    )


def create_dead_letter_processor(
    queue: DeadLetterQueue,
    handler: Callable[[DeadLetterMessage], Any],
    batch_size: int = 10,
) -> DeadLetterProcessor:
    """Create a dead letter processor."""
    return DeadLetterProcessor(
        queue=queue,
        handler=handler,
        batch_size=batch_size,
    )


def create_poison_handler(
    queue: DeadLetterQueue,
) -> PoisonMessageHandler:
    """Create a poison message handler."""
    return PoisonMessageHandler(queue)


def create_retry_policy(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 3600.0,
) -> RetryPolicy:
    """Create a retry policy."""
    return RetryPolicy(
        max_retries=max_retries,
        initial_delay=initial_delay,
        max_delay=max_delay,
    )


def create_failure_classifier() -> FailureClassifier:
    """Create a failure classifier."""
    return FailureClassifier()


def register_queue(name: str, queue: DeadLetterQueue) -> None:
    """Register queue in global registry."""
    _global_registry.register(name, queue)


def get_queue(name: str) -> DeadLetterQueue:
    """Get queue from global registry."""
    return _global_registry.get(name)


__all__ = [
    # Exceptions
    "DeadLetterError",
    "PoisonMessageError",
    "MaxRetriesExceeded",
    # Enums
    "FailureReason",
    "MessageStatus",
    # Data classes
    "FailureContext",
    "DeadLetterMessage",
    "RetryPolicy",
    "DeadLetterStats",
    # Store
    "DeadLetterStore",
    "InMemoryDeadLetterStore",
    # Classifier
    "FailureClassifier",
    # Queue
    "DeadLetterQueue",
    "DeadLetterProcessor",
    "PoisonMessageHandler",
    # Registry
    "DeadLetterRegistry",
    # Decorators
    "on_dead_letter",
    "retry_on_failure",
    # Factory functions
    "create_dead_letter_queue",
    "create_dead_letter_processor",
    "create_poison_handler",
    "create_retry_policy",
    "create_failure_classifier",
    "register_queue",
    "get_queue",
]
