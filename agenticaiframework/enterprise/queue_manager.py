"""
Enterprise Queue Manager Module.

Message queues, job queues, priority queues,
and distributed task processing.

Example:
    # Create queue manager
    queues = create_queue_manager()
    
    # Create queue
    queue = await queues.create_queue("tasks", priority=True)
    
    # Enqueue messages
    await queues.enqueue("tasks", {"action": "process", "data": "..."})
    
    # Dequeue messages
    message = await queues.dequeue("tasks")
    
    # Acknowledge processing
    await queues.ack("tasks", message.id)
"""

from __future__ import annotations

import asyncio
import heapq
import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    Callable,
    Coroutine,
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


class QueueError(Exception):
    """Queue error."""
    pass


class QueueNotFound(QueueError):
    """Queue not found."""
    pass


class MessageNotFound(QueueError):
    """Message not found."""
    pass


class QueueFull(QueueError):
    """Queue is full."""
    pass


class QueueType(str, Enum):
    """Queue type."""
    FIFO = "fifo"
    LIFO = "lifo"
    PRIORITY = "priority"
    DELAYED = "delayed"


class MessageStatus(str, Enum):
    """Message status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


class Priority(str, Enum):
    """Message priority."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


PRIORITY_VALUES = {
    Priority.CRITICAL: 0,
    Priority.HIGH: 1,
    Priority.NORMAL: 2,
    Priority.LOW: 3,
}


@dataclass
class Message:
    """Queue message."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    queue_name: str = ""
    body: Any = None
    priority: Priority = Priority.NORMAL
    status: MessageStatus = MessageStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    visibility_timeout: int = 30  # seconds
    ttl: int = 86400  # 1 day
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __lt__(self, other: "Message") -> bool:
        """Priority comparison."""
        self_priority = PRIORITY_VALUES.get(self.priority, 2)
        other_priority = PRIORITY_VALUES.get(other.priority, 2)
        
        if self_priority != other_priority:
            return self_priority < other_priority
        
        return self.created_at < other.created_at


@dataclass
class Queue:
    """Queue definition."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    queue_type: QueueType = QueueType.FIFO
    max_size: int = 0  # 0 = unlimited
    created_at: datetime = field(default_factory=datetime.utcnow)
    default_visibility_timeout: int = 30
    default_ttl: int = 86400
    dead_letter_queue: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QueueStats:
    """Queue statistics."""
    queue_name: str = ""
    pending_count: int = 0
    processing_count: int = 0
    completed_count: int = 0
    failed_count: int = 0
    dead_letter_count: int = 0
    avg_processing_time: float = 0.0


@dataclass
class QueueManagerStats:
    """Queue manager statistics."""
    total_queues: int = 0
    total_messages: int = 0
    total_processed: int = 0
    total_failed: int = 0


# Queue store
class QueueStore(ABC):
    """Queue storage backend."""
    
    @abstractmethod
    async def create_queue(self, queue: Queue) -> None:
        pass
    
    @abstractmethod
    async def get_queue(self, name: str) -> Optional[Queue]:
        pass
    
    @abstractmethod
    async def delete_queue(self, name: str) -> bool:
        pass
    
    @abstractmethod
    async def list_queues(self) -> List[Queue]:
        pass
    
    @abstractmethod
    async def enqueue(self, message: Message) -> None:
        pass
    
    @abstractmethod
    async def dequeue(self, queue_name: str, count: int = 1) -> List[Message]:
        pass
    
    @abstractmethod
    async def ack(self, queue_name: str, message_id: str) -> bool:
        pass
    
    @abstractmethod
    async def nack(self, queue_name: str, message_id: str, requeue: bool = True) -> bool:
        pass
    
    @abstractmethod
    async def get_stats(self, queue_name: str) -> QueueStats:
        pass


class InMemoryQueueStore(QueueStore):
    """In-memory queue store."""
    
    def __init__(self):
        self._queues: Dict[str, Queue] = {}
        self._messages: Dict[str, Dict[str, Message]] = {}
        self._pending: Dict[str, deque] = {}
        self._priority_pending: Dict[str, List[Tuple[int, float, Message]]] = {}
        self._processing: Dict[str, Dict[str, Message]] = {}
        self._completed: Dict[str, int] = {}
        self._failed: Dict[str, int] = {}
        self._processing_times: Dict[str, List[float]] = {}
    
    async def create_queue(self, queue: Queue) -> None:
        self._queues[queue.name] = queue
        self._messages[queue.name] = {}
        self._pending[queue.name] = deque()
        self._priority_pending[queue.name] = []
        self._processing[queue.name] = {}
        self._completed[queue.name] = 0
        self._failed[queue.name] = 0
        self._processing_times[queue.name] = []
    
    async def get_queue(self, name: str) -> Optional[Queue]:
        return self._queues.get(name)
    
    async def delete_queue(self, name: str) -> bool:
        if name in self._queues:
            del self._queues[name]
            self._messages.pop(name, None)
            self._pending.pop(name, None)
            self._priority_pending.pop(name, None)
            self._processing.pop(name, None)
            self._completed.pop(name, None)
            self._failed.pop(name, None)
            return True
        return False
    
    async def list_queues(self) -> List[Queue]:
        return list(self._queues.values())
    
    async def enqueue(self, message: Message) -> None:
        queue = self._queues.get(message.queue_name)
        if not queue:
            raise QueueNotFound(f"Queue not found: {message.queue_name}")
        
        # Check max size
        if queue.max_size > 0:
            current_size = len(self._messages.get(message.queue_name, {}))
            if current_size >= queue.max_size:
                raise QueueFull(f"Queue is full: {message.queue_name}")
        
        self._messages[message.queue_name][message.id] = message
        
        if queue.queue_type == QueueType.PRIORITY:
            priority_val = PRIORITY_VALUES.get(message.priority, 2)
            heapq.heappush(
                self._priority_pending[message.queue_name],
                (priority_val, time.time(), message)
            )
        elif queue.queue_type == QueueType.LIFO:
            self._pending[message.queue_name].append(message)
        else:
            self._pending[message.queue_name].append(message)
    
    async def dequeue(self, queue_name: str, count: int = 1) -> List[Message]:
        queue = self._queues.get(queue_name)
        if not queue:
            raise QueueNotFound(f"Queue not found: {queue_name}")
        
        messages = []
        now = datetime.utcnow()
        
        for _ in range(count):
            message = None
            
            if queue.queue_type == QueueType.PRIORITY:
                pq = self._priority_pending.get(queue_name, [])
                while pq:
                    _, _, msg = heapq.heappop(pq)
                    if msg.id in self._messages.get(queue_name, {}):
                        message = msg
                        break
            elif queue.queue_type == QueueType.LIFO:
                pending = self._pending.get(queue_name)
                if pending:
                    message = pending.pop()
            else:
                pending = self._pending.get(queue_name)
                if pending:
                    message = pending.popleft()
            
            if message:
                message.status = MessageStatus.PROCESSING
                message.started_at = now
                message.updated_at = now
                
                self._processing[queue_name][message.id] = message
                messages.append(message)
        
        return messages
    
    async def ack(self, queue_name: str, message_id: str) -> bool:
        processing = self._processing.get(queue_name, {})
        
        if message_id in processing:
            message = processing.pop(message_id)
            message.status = MessageStatus.COMPLETED
            message.completed_at = datetime.utcnow()
            
            # Track processing time
            if message.started_at:
                duration = (message.completed_at - message.started_at).total_seconds()
                self._processing_times[queue_name].append(duration)
                # Keep only last 100
                if len(self._processing_times[queue_name]) > 100:
                    self._processing_times[queue_name] = self._processing_times[queue_name][-100:]
            
            # Remove from messages
            self._messages[queue_name].pop(message_id, None)
            self._completed[queue_name] = self._completed.get(queue_name, 0) + 1
            
            return True
        
        return False
    
    async def nack(self, queue_name: str, message_id: str, requeue: bool = True) -> bool:
        processing = self._processing.get(queue_name, {})
        
        if message_id in processing:
            message = processing.pop(message_id)
            
            if requeue and message.retry_count < message.max_retries:
                message.retry_count += 1
                message.status = MessageStatus.PENDING
                message.started_at = None
                message.updated_at = datetime.utcnow()
                
                # Re-enqueue
                queue = self._queues.get(queue_name)
                if queue and queue.queue_type == QueueType.PRIORITY:
                    priority_val = PRIORITY_VALUES.get(message.priority, 2)
                    heapq.heappush(
                        self._priority_pending[queue_name],
                        (priority_val, time.time(), message)
                    )
                else:
                    self._pending[queue_name].append(message)
            else:
                message.status = MessageStatus.FAILED
                message.completed_at = datetime.utcnow()
                
                # Move to dead letter queue
                queue = self._queues.get(queue_name)
                if queue and queue.dead_letter_queue:
                    dlq_message = Message(
                        queue_name=queue.dead_letter_queue,
                        body=message.body,
                        priority=message.priority,
                        status=MessageStatus.DEAD_LETTER,
                        metadata={**message.metadata, "original_queue": queue_name},
                    )
                    
                    if queue.dead_letter_queue in self._messages:
                        self._messages[queue.dead_letter_queue][dlq_message.id] = dlq_message
                        self._pending[queue.dead_letter_queue].append(dlq_message)
                
                self._messages[queue_name].pop(message_id, None)
                self._failed[queue_name] = self._failed.get(queue_name, 0) + 1
            
            return True
        
        return False
    
    async def get_stats(self, queue_name: str) -> QueueStats:
        pending_count = len(self._pending.get(queue_name, [])) + len(self._priority_pending.get(queue_name, []))
        processing_count = len(self._processing.get(queue_name, {}))
        
        times = self._processing_times.get(queue_name, [])
        avg_time = sum(times) / len(times) if times else 0.0
        
        return QueueStats(
            queue_name=queue_name,
            pending_count=pending_count,
            processing_count=processing_count,
            completed_count=self._completed.get(queue_name, 0),
            failed_count=self._failed.get(queue_name, 0),
            avg_processing_time=avg_time,
        )


# Message handler type
MessageHandler = Callable[[Message], Coroutine[Any, Any, Any]]


# Queue manager
class QueueManager:
    """Queue manager."""
    
    def __init__(
        self,
        store: Optional[QueueStore] = None,
        max_concurrent: int = 10,
    ):
        self._store = store or InMemoryQueueStore()
        self._handlers: Dict[str, MessageHandler] = {}
        self._workers: Dict[str, asyncio.Task] = {}
        self._running = False
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._stats = QueueManagerStats()
    
    async def create_queue(
        self,
        name: str,
        queue_type: QueueType = QueueType.FIFO,
        max_size: int = 0,
        dead_letter_queue: Optional[str] = None,
        **kwargs,
    ) -> Queue:
        """Create queue."""
        queue = Queue(
            name=name,
            queue_type=queue_type,
            max_size=max_size,
            dead_letter_queue=dead_letter_queue,
            **kwargs,
        )
        
        await self._store.create_queue(queue)
        self._stats.total_queues += 1
        
        logger.info(f"Queue created: {name} (type={queue_type.value})")
        
        return queue
    
    async def get_queue(self, name: str) -> Optional[Queue]:
        """Get queue."""
        return await self._store.get_queue(name)
    
    async def delete_queue(self, name: str) -> bool:
        """Delete queue."""
        result = await self._store.delete_queue(name)
        
        if result:
            self._stats.total_queues = max(0, self._stats.total_queues - 1)
            
            # Stop worker
            if name in self._workers:
                self._workers[name].cancel()
                del self._workers[name]
        
        return result
    
    async def list_queues(self) -> List[Queue]:
        """List queues."""
        return await self._store.list_queues()
    
    async def enqueue(
        self,
        queue_name: str,
        body: Any,
        priority: Priority = Priority.NORMAL,
        delay: int = 0,
        **kwargs,
    ) -> Message:
        """Enqueue message."""
        scheduled_at = None
        if delay > 0:
            scheduled_at = datetime.utcnow() + timedelta(seconds=delay)
        
        message = Message(
            queue_name=queue_name,
            body=body,
            priority=priority,
            scheduled_at=scheduled_at,
            **kwargs,
        )
        
        await self._store.enqueue(message)
        self._stats.total_messages += 1
        
        return message
    
    async def enqueue_batch(
        self,
        queue_name: str,
        messages: List[Dict[str, Any]],
    ) -> List[Message]:
        """Enqueue multiple messages."""
        results = []
        
        for msg_data in messages:
            body = msg_data.get("body")
            priority = msg_data.get("priority", Priority.NORMAL)
            
            message = await self.enqueue(queue_name, body, priority)
            results.append(message)
        
        return results
    
    async def dequeue(
        self,
        queue_name: str,
        count: int = 1,
    ) -> List[Message]:
        """Dequeue messages."""
        return await self._store.dequeue(queue_name, count)
    
    async def ack(self, queue_name: str, message_id: str) -> bool:
        """Acknowledge message."""
        result = await self._store.ack(queue_name, message_id)
        
        if result:
            self._stats.total_processed += 1
        
        return result
    
    async def nack(
        self,
        queue_name: str,
        message_id: str,
        requeue: bool = True,
    ) -> bool:
        """Negative acknowledge message."""
        result = await self._store.nack(queue_name, message_id, requeue)
        
        if result and not requeue:
            self._stats.total_failed += 1
        
        return result
    
    def register_handler(self, queue_name: str, handler: MessageHandler) -> None:
        """Register message handler."""
        self._handlers[queue_name] = handler
        logger.info(f"Handler registered for queue: {queue_name}")
    
    async def _process_queue(self, queue_name: str) -> None:
        """Process queue messages."""
        handler = self._handlers.get(queue_name)
        if not handler:
            return
        
        while self._running:
            try:
                messages = await self.dequeue(queue_name, count=1)
                
                for message in messages:
                    async with self._semaphore:
                        try:
                            await handler(message)
                            await self.ack(queue_name, message.id)
                        except Exception as e:
                            logger.error(f"Handler error: {queue_name} - {e}")
                            await self.nack(queue_name, message.id)
                
                if not messages:
                    await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Queue processing error: {queue_name} - {e}")
                await asyncio.sleep(1)
    
    async def start_worker(self, queue_name: str) -> None:
        """Start queue worker."""
        if queue_name in self._workers:
            return
        
        self._running = True
        self._workers[queue_name] = asyncio.create_task(self._process_queue(queue_name))
        logger.info(f"Worker started for queue: {queue_name}")
    
    async def stop_worker(self, queue_name: str) -> None:
        """Stop queue worker."""
        if queue_name in self._workers:
            self._workers[queue_name].cancel()
            
            try:
                await self._workers[queue_name]
            except asyncio.CancelledError:
                pass
            
            del self._workers[queue_name]
            logger.info(f"Worker stopped for queue: {queue_name}")
    
    async def start_all_workers(self) -> None:
        """Start all registered workers."""
        self._running = True
        
        for queue_name in self._handlers:
            await self.start_worker(queue_name)
    
    async def stop_all_workers(self) -> None:
        """Stop all workers."""
        self._running = False
        
        for queue_name in list(self._workers.keys()):
            await self.stop_worker(queue_name)
    
    async def get_queue_stats(self, queue_name: str) -> QueueStats:
        """Get queue statistics."""
        return await self._store.get_stats(queue_name)
    
    def get_stats(self) -> QueueManagerStats:
        """Get manager statistics."""
        return self._stats


# Factory functions
def create_queue_manager(max_concurrent: int = 10) -> QueueManager:
    """Create queue manager."""
    return QueueManager(max_concurrent=max_concurrent)


def create_queue(
    name: str,
    queue_type: QueueType = QueueType.FIFO,
    **kwargs,
) -> Queue:
    """Create queue definition."""
    return Queue(name=name, queue_type=queue_type, **kwargs)


def create_message(
    queue_name: str,
    body: Any,
    priority: Priority = Priority.NORMAL,
    **kwargs,
) -> Message:
    """Create message."""
    return Message(queue_name=queue_name, body=body, priority=priority, **kwargs)


__all__ = [
    # Exceptions
    "QueueError",
    "QueueNotFound",
    "MessageNotFound",
    "QueueFull",
    # Enums
    "QueueType",
    "MessageStatus",
    "Priority",
    # Data classes
    "Message",
    "Queue",
    "QueueStats",
    "QueueManagerStats",
    # Stores
    "QueueStore",
    "InMemoryQueueStore",
    # Manager
    "QueueManager",
    # Factory functions
    "create_queue_manager",
    "create_queue",
    "create_message",
]
