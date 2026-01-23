"""
Enterprise Queue Module.

Provides message queue producers/consumers, job handling,
and async task processing for distributed systems.

Example:
    # Create queue
    queue = create_queue("memory")
    
    # Producer
    await queue.enqueue("task_queue", {"action": "process", "data": ...})
    
    # Consumer with decorator
    @consumer("task_queue")
    async def process_task(message: Message):
        ...
    
    # Job scheduling
    @job(schedule="*/5 * * * *")  # Every 5 minutes
    async def periodic_task():
        ...
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
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
    TypeVar,
    Union,
)

logger = logging.getLogger(__name__)

T = TypeVar('T')


class QueueError(Exception):
    """Base queue error."""
    pass


class MessageStatus(str, Enum):
    """Message status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD = "dead"
    DELAYED = "delayed"


class Priority(int, Enum):
    """Message priority levels."""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class Message:
    """Queue message."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    queue: str = ""
    payload: Any = None
    priority: Priority = Priority.NORMAL
    status: MessageStatus = MessageStatus.PENDING
    attempts: int = 0
    max_attempts: int = 3
    created_at: datetime = field(default_factory=datetime.now)
    scheduled_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "queue": self.queue,
            "payload": self.payload,
            "priority": self.priority.value,
            "status": self.status.value,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "created_at": self.created_at.isoformat(),
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "error": self.error,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """Create from dictionary."""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            queue=data.get("queue", ""),
            payload=data.get("payload"),
            priority=Priority(data.get("priority", 1)),
            status=MessageStatus(data.get("status", "pending")),
            attempts=data.get("attempts", 0),
            max_attempts=data.get("max_attempts", 3),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            scheduled_at=datetime.fromisoformat(data["scheduled_at"]) if data.get("scheduled_at") else None,
            processed_at=datetime.fromisoformat(data["processed_at"]) if data.get("processed_at") else None,
            error=data.get("error"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class QueueStats:
    """Queue statistics."""
    name: str
    pending: int = 0
    processing: int = 0
    completed: int = 0
    failed: int = 0
    dead: int = 0
    total_processed: int = 0
    avg_processing_time_ms: float = 0.0


class Queue(ABC):
    """Abstract queue interface."""
    
    @abstractmethod
    async def enqueue(
        self,
        queue_name: str,
        payload: Any,
        priority: Priority = Priority.NORMAL,
        delay: Optional[timedelta] = None,
        **metadata: Any,
    ) -> Message:
        """Add a message to the queue."""
        pass
    
    @abstractmethod
    async def dequeue(
        self,
        queue_name: str,
        timeout: Optional[float] = None,
    ) -> Optional[Message]:
        """Get next message from queue."""
        pass
    
    @abstractmethod
    async def ack(self, message: Message) -> None:
        """Acknowledge message processing."""
        pass
    
    @abstractmethod
    async def nack(
        self,
        message: Message,
        error: Optional[str] = None,
        requeue: bool = True,
    ) -> None:
        """Negative acknowledge (failed processing)."""
        pass
    
    @abstractmethod
    async def get_stats(self, queue_name: str) -> QueueStats:
        """Get queue statistics."""
        pass


class InMemoryQueue(Queue):
    """In-memory queue implementation."""
    
    def __init__(self):
        self._queues: Dict[str, asyncio.PriorityQueue] = {}
        self._processing: Dict[str, Message] = {}
        self._completed: Dict[str, List[Message]] = {}
        self._failed: Dict[str, List[Message]] = {}
        self._stats: Dict[str, Dict[str, int]] = {}
    
    def _get_queue(self, name: str) -> asyncio.PriorityQueue:
        """Get or create a queue."""
        if name not in self._queues:
            self._queues[name] = asyncio.PriorityQueue()
            self._completed[name] = []
            self._failed[name] = []
            self._stats[name] = {"total": 0, "processing_time": 0.0}
        return self._queues[name]
    
    async def enqueue(
        self,
        queue_name: str,
        payload: Any,
        priority: Priority = Priority.NORMAL,
        delay: Optional[timedelta] = None,
        **metadata: Any,
    ) -> Message:
        """Add a message to the queue."""
        message = Message(
            queue=queue_name,
            payload=payload,
            priority=priority,
            metadata=metadata,
        )
        
        if delay:
            message.scheduled_at = datetime.now() + delay
            message.status = MessageStatus.DELAYED
            # Schedule delayed delivery
            asyncio.create_task(self._delayed_enqueue(message, delay))
        else:
            queue = self._get_queue(queue_name)
            # Priority queue uses (priority, timestamp, message) for ordering
            # Lower priority value = higher priority in PriorityQueue
            await queue.put((
                -priority.value,  # Negative for proper ordering
                time.time(),
                message,
            ))
        
        logger.debug(f"Enqueued message {message.id} to {queue_name}")
        return message
    
    async def _delayed_enqueue(self, message: Message, delay: timedelta) -> None:
        """Enqueue message after delay."""
        await asyncio.sleep(delay.total_seconds())
        message.status = MessageStatus.PENDING
        queue = self._get_queue(message.queue)
        await queue.put((
            -message.priority.value,
            time.time(),
            message,
        ))
    
    async def dequeue(
        self,
        queue_name: str,
        timeout: Optional[float] = None,
    ) -> Optional[Message]:
        """Get next message from queue."""
        queue = self._get_queue(queue_name)
        
        try:
            if timeout:
                _, _, message = await asyncio.wait_for(
                    queue.get(),
                    timeout=timeout,
                )
            else:
                _, _, message = queue.get_nowait()
            
            message.status = MessageStatus.PROCESSING
            message.attempts += 1
            self._processing[message.id] = message
            
            return message
            
        except asyncio.TimeoutError:
            return None
        except asyncio.QueueEmpty:
            return None
    
    async def ack(self, message: Message) -> None:
        """Acknowledge message processing."""
        message.status = MessageStatus.COMPLETED
        message.processed_at = datetime.now()
        
        if message.id in self._processing:
            del self._processing[message.id]
        
        self._completed[message.queue].append(message)
        
        # Update stats
        processing_time = (message.processed_at - message.created_at).total_seconds() * 1000
        stats = self._stats.get(message.queue, {"total": 0, "processing_time": 0.0})
        stats["total"] += 1
        stats["processing_time"] = (
            (stats["processing_time"] * (stats["total"] - 1) + processing_time)
            / stats["total"]
        )
        
        logger.debug(f"Acked message {message.id}")
    
    async def nack(
        self,
        message: Message,
        error: Optional[str] = None,
        requeue: bool = True,
    ) -> None:
        """Negative acknowledge."""
        message.error = error
        
        if message.id in self._processing:
            del self._processing[message.id]
        
        if requeue and message.attempts < message.max_attempts:
            # Requeue with exponential backoff
            delay = timedelta(seconds=2 ** message.attempts)
            await self.enqueue(
                message.queue,
                message.payload,
                message.priority,
                delay=delay,
                **message.metadata,
            )
        else:
            message.status = MessageStatus.DEAD
            self._failed[message.queue].append(message)
        
        logger.debug(f"Nacked message {message.id}: {error}")
    
    async def get_stats(self, queue_name: str) -> QueueStats:
        """Get queue statistics."""
        queue = self._get_queue(queue_name)
        processing = sum(1 for m in self._processing.values() if m.queue == queue_name)
        stats_data = self._stats.get(queue_name, {"total": 0, "processing_time": 0.0})
        
        return QueueStats(
            name=queue_name,
            pending=queue.qsize(),
            processing=processing,
            completed=len(self._completed.get(queue_name, [])),
            failed=len(self._failed.get(queue_name, [])),
            total_processed=stats_data["total"],
            avg_processing_time_ms=stats_data["processing_time"],
        )


class Consumer:
    """Message consumer that processes queue messages."""
    
    def __init__(
        self,
        queue: Queue,
        queue_name: str,
        handler: Callable[[Message], Awaitable[None]],
        concurrency: int = 1,
        poll_interval: float = 1.0,
    ):
        self._queue = queue
        self._queue_name = queue_name
        self._handler = handler
        self._concurrency = concurrency
        self._poll_interval = poll_interval
        self._running = False
        self._tasks: List[asyncio.Task] = []
    
    async def start(self) -> None:
        """Start consuming messages."""
        self._running = True
        
        for i in range(self._concurrency):
            task = asyncio.create_task(self._consume_loop(i))
            self._tasks.append(task)
        
        logger.info(f"Started consumer for {self._queue_name} with {self._concurrency} workers")
    
    async def stop(self) -> None:
        """Stop consuming messages."""
        self._running = False
        
        for task in self._tasks:
            task.cancel()
        
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        
        logger.info(f"Stopped consumer for {self._queue_name}")
    
    async def _consume_loop(self, worker_id: int) -> None:
        """Main consume loop."""
        while self._running:
            try:
                message = await self._queue.dequeue(
                    self._queue_name,
                    timeout=self._poll_interval,
                )
                
                if message:
                    await self._process_message(message)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Consumer error: {e}")
                await asyncio.sleep(self._poll_interval)
    
    async def _process_message(self, message: Message) -> None:
        """Process a single message."""
        try:
            await self._handler(message)
            await self._queue.ack(message)
        except Exception as e:
            logger.error(f"Message processing failed: {e}")
            await self._queue.nack(message, str(e))


class Producer:
    """Message producer for sending to queues."""
    
    def __init__(self, queue: Queue):
        self._queue = queue
    
    async def send(
        self,
        queue_name: str,
        payload: Any,
        priority: Priority = Priority.NORMAL,
        delay: Optional[timedelta] = None,
        **metadata: Any,
    ) -> Message:
        """Send a message to a queue."""
        return await self._queue.enqueue(
            queue_name,
            payload,
            priority,
            delay,
            **metadata,
        )
    
    async def send_batch(
        self,
        queue_name: str,
        payloads: List[Any],
        priority: Priority = Priority.NORMAL,
    ) -> List[Message]:
        """Send multiple messages."""
        messages = []
        for payload in payloads:
            msg = await self.send(queue_name, payload, priority)
            messages.append(msg)
        return messages


@dataclass
class Job:
    """Scheduled job definition."""
    id: str
    name: str
    handler: Callable[[], Awaitable[None]]
    schedule: str  # Cron expression
    enabled: bool = True
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    run_count: int = 0
    error_count: int = 0


class JobScheduler:
    """Simple job scheduler."""
    
    def __init__(self):
        self._jobs: Dict[str, Job] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    def add_job(
        self,
        name: str,
        handler: Callable[[], Awaitable[None]],
        schedule: str,
    ) -> Job:
        """Add a scheduled job."""
        job = Job(
            id=str(uuid.uuid4()),
            name=name,
            handler=handler,
            schedule=schedule,
        )
        self._jobs[name] = job
        return job
    
    async def start(self) -> None:
        """Start the scheduler."""
        self._running = True
        self._task = asyncio.create_task(self._scheduler_loop())
        logger.info("Job scheduler started")
    
    async def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Job scheduler stopped")
    
    async def _scheduler_loop(self) -> None:
        """Main scheduler loop."""
        while self._running:
            try:
                for job in self._jobs.values():
                    if job.enabled and self._should_run(job):
                        await self._run_job(job)
                
                await asyncio.sleep(60)  # Check every minute
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
    
    def _should_run(self, job: Job) -> bool:
        """Check if job should run based on cron schedule."""
        # Simplified: just check if interval has passed
        # In production, use a proper cron parser
        if job.last_run is None:
            return True
        
        # Parse simple interval from schedule (e.g., "*/5" = every 5 minutes)
        if job.schedule.startswith("*/"):
            try:
                interval = int(job.schedule[2:].split()[0])
                elapsed = (datetime.now() - job.last_run).total_seconds()
                return elapsed >= interval * 60
            except (ValueError, IndexError):
                pass
        
        return False
    
    async def _run_job(self, job: Job) -> None:
        """Execute a job."""
        try:
            job.last_run = datetime.now()
            await job.handler()
            job.run_count += 1
            logger.info(f"Job {job.name} completed")
        except Exception as e:
            job.error_count += 1
            logger.error(f"Job {job.name} failed: {e}")


# Global instances
_queue_instance: Optional[Queue] = None
_scheduler_instance: Optional[JobScheduler] = None
_consumers: Dict[str, Callable] = {}


def consumer(
    queue_name: str,
    concurrency: int = 1,
    poll_interval: float = 1.0,
) -> Callable:
    """
    Decorator to register a consumer handler.
    
    Example:
        @consumer("tasks")
        async def process_task(message: Message):
            ...
    """
    def decorator(func: Callable[[Message], Awaitable[None]]) -> Callable:
        _consumers[queue_name] = {
            "handler": func,
            "concurrency": concurrency,
            "poll_interval": poll_interval,
        }
        return func
    
    return decorator


def job(schedule: str, name: Optional[str] = None) -> Callable:
    """
    Decorator to register a scheduled job.
    
    Example:
        @job("*/5 * * * *")  # Every 5 minutes
        async def cleanup_task():
            ...
    """
    def decorator(func: Callable[[], Awaitable[None]]) -> Callable:
        job_name = name or func.__name__
        
        if _scheduler_instance:
            _scheduler_instance.add_job(job_name, func, schedule)
        
        return func
    
    return decorator


def create_queue(provider: str = "memory", **kwargs: Any) -> Queue:
    """
    Factory function to create a queue.
    """
    global _queue_instance
    
    if provider == "memory":
        _queue_instance = InMemoryQueue()
    else:
        raise ValueError(f"Unknown queue provider: {provider}")
    
    return _queue_instance


def create_producer(queue: Optional[Queue] = None) -> Producer:
    """Create a producer."""
    return Producer(queue or _queue_instance or create_queue())


def create_consumer(
    queue_name: str,
    handler: Callable[[Message], Awaitable[None]],
    queue: Optional[Queue] = None,
    **kwargs: Any,
) -> Consumer:
    """Create a consumer."""
    return Consumer(
        queue or _queue_instance or create_queue(),
        queue_name,
        handler,
        **kwargs,
    )


def create_scheduler() -> JobScheduler:
    """Create a job scheduler."""
    global _scheduler_instance
    _scheduler_instance = JobScheduler()
    return _scheduler_instance


__all__ = [
    # Exceptions
    "QueueError",
    # Enums
    "MessageStatus",
    "Priority",
    # Data classes
    "Message",
    "QueueStats",
    "Job",
    # Queue
    "Queue",
    "InMemoryQueue",
    # Consumer/Producer
    "Consumer",
    "Producer",
    # Scheduler
    "JobScheduler",
    # Decorators
    "consumer",
    "job",
    # Factory
    "create_queue",
    "create_producer",
    "create_consumer",
    "create_scheduler",
]
