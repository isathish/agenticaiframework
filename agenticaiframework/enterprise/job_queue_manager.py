"""
Enterprise Job Queue Manager Module.

Async job execution, worker pools, priority queues,
job scheduling, and retry management.

Example:
    # Create job queue manager
    jobs = create_job_queue_manager()
    
    # Define job handler
    @jobs.handler("send_email")
    async def send_email(job: Job):
        await email_service.send(job.payload["to"], job.payload["subject"])
    
    # Submit job
    job = await jobs.submit(
        queue="send_email",
        payload={"to": "user@example.com", "subject": "Hello"},
    )
    
    # Start workers
    await jobs.start_workers(queue="send_email", count=5)
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
import traceback
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from heapq import heappop, heappush
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    TypeVar,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


class JobError(Exception):
    """Job error."""
    pass


class JobNotFoundError(JobError):
    """Job not found error."""
    pass


class QueueNotFoundError(JobError):
    """Queue not found error."""
    pass


class JobStatus(str, Enum):
    """Job status."""
    PENDING = "pending"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"
    DEAD = "dead"


class JobPriority(int, Enum):
    """Job priority."""
    LOW = 10
    NORMAL = 50
    HIGH = 80
    CRITICAL = 100


class RetryStrategy(str, Enum):
    """Retry strategy."""
    FIXED = "fixed"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    CUSTOM = "custom"


@dataclass
class RetryPolicy:
    """Retry policy."""
    max_retries: int = 3
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 300.0
    retry_on_exceptions: List[str] = field(default_factory=list)


@dataclass
class Job:
    """Job."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    queue: str = ""
    
    # Payload
    payload: Dict[str, Any] = field(default_factory=dict)
    
    # Status
    status: JobStatus = JobStatus.PENDING
    
    # Priority and scheduling
    priority: int = JobPriority.NORMAL
    scheduled_at: Optional[datetime] = None
    delay_seconds: float = 0.0
    
    # Progress
    progress: float = 0.0
    progress_message: str = ""
    
    # Result
    result: Any = None
    error_message: str = ""
    error_traceback: str = ""
    
    # Retry
    attempt: int = 0
    max_retries: int = 3
    next_retry_at: Optional[datetime] = None
    
    # Timing
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0
    
    # Metadata
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __lt__(self, other: "Job") -> bool:
        """Compare for priority queue."""
        return self.priority > other.priority  # Higher priority first


@dataclass
class QueueConfig:
    """Queue configuration."""
    name: str = ""
    
    # Workers
    max_workers: int = 5
    min_workers: int = 1
    
    # Concurrency
    max_concurrent_jobs: int = 10
    
    # Timeouts
    job_timeout_seconds: float = 300.0
    poll_interval_seconds: float = 1.0
    
    # Retry
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    
    # Dead letter
    dead_letter_queue: Optional[str] = None
    
    # Metadata
    description: str = ""


@dataclass
class Worker:
    """Worker."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    queue: str = ""
    
    # Status
    status: str = "idle"  # idle, busy, stopped
    current_job_id: Optional[str] = None
    
    # Statistics
    jobs_processed: int = 0
    jobs_failed: int = 0
    
    # Timing
    started_at: datetime = field(default_factory=datetime.utcnow)
    last_job_at: Optional[datetime] = None
    
    # Task
    task: Optional[asyncio.Task] = None


@dataclass
class QueueStats:
    """Queue statistics."""
    queue_name: str = ""
    
    pending_jobs: int = 0
    running_jobs: int = 0
    completed_jobs: int = 0
    failed_jobs: int = 0
    
    workers_count: int = 0
    active_workers: int = 0
    
    avg_wait_time_seconds: float = 0.0
    avg_processing_time_seconds: float = 0.0
    throughput_per_minute: float = 0.0


@dataclass
class JobQueueStats:
    """Overall job queue statistics."""
    total_queues: int = 0
    total_jobs: int = 0
    pending_jobs: int = 0
    running_jobs: int = 0
    total_workers: int = 0


# Job store
class JobStore(ABC):
    """Job storage."""
    
    @abstractmethod
    async def save(self, job: Job) -> None:
        pass
    
    @abstractmethod
    async def get(self, job_id: str) -> Optional[Job]:
        pass
    
    @abstractmethod
    async def get_pending(self, queue: str, limit: int) -> List[Job]:
        pass
    
    @abstractmethod
    async def get_scheduled(self, before: datetime) -> List[Job]:
        pass
    
    @abstractmethod
    async def count_by_status(self, queue: str, status: JobStatus) -> int:
        pass


class InMemoryJobStore(JobStore):
    """In-memory job store."""
    
    def __init__(self, max_jobs: int = 100000):
        self._jobs: Dict[str, Job] = {}
        self._queues: Dict[str, List[str]] = defaultdict(list)
        self._max_jobs = max_jobs
    
    async def save(self, job: Job) -> None:
        self._jobs[job.id] = job
        
        if job.id not in self._queues[job.queue]:
            self._queues[job.queue].append(job.id)
        
        # Cleanup old completed jobs
        if len(self._jobs) > self._max_jobs:
            self._cleanup_old_jobs()
    
    async def get(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)
    
    async def get_pending(self, queue: str, limit: int) -> List[Job]:
        job_ids = self._queues.get(queue, [])
        jobs = []
        
        for jid in job_ids:
            job = self._jobs.get(jid)
            if job and job.status == JobStatus.PENDING:
                jobs.append(job)
                if len(jobs) >= limit:
                    break
        
        return sorted(jobs, key=lambda j: j.priority, reverse=True)
    
    async def get_scheduled(self, before: datetime) -> List[Job]:
        jobs = []
        
        for job in self._jobs.values():
            if job.status == JobStatus.SCHEDULED:
                if job.scheduled_at and job.scheduled_at <= before:
                    jobs.append(job)
        
        return jobs
    
    async def count_by_status(self, queue: str, status: JobStatus) -> int:
        job_ids = self._queues.get(queue, [])
        count = 0
        
        for jid in job_ids:
            job = self._jobs.get(jid)
            if job and job.status == status:
                count += 1
        
        return count
    
    def _cleanup_old_jobs(self) -> None:
        completed = [
            j for j in self._jobs.values()
            if j.status in (JobStatus.COMPLETED, JobStatus.DEAD, JobStatus.CANCELLED)
        ]
        
        completed.sort(key=lambda j: j.completed_at or j.created_at)
        
        to_remove = len(self._jobs) - (self._max_jobs // 2)
        
        for job in completed[:to_remove]:
            self._jobs.pop(job.id, None)
            if job.id in self._queues.get(job.queue, []):
                self._queues[job.queue].remove(job.id)


# Job handler
JobHandler = Callable[[Job], Any]


# Job queue
class JobQueue:
    """Job queue."""
    
    def __init__(
        self,
        config: QueueConfig,
        store: JobStore,
    ):
        self._config = config
        self._store = store
        
        self._handlers: Dict[str, JobHandler] = {}
        self._workers: Dict[str, Worker] = {}
        
        self._running = False
        self._job_semaphore = asyncio.Semaphore(config.max_concurrent_jobs)
        
        # Priority queue for pending jobs
        self._priority_queue: List[Job] = []
        self._queue_lock = asyncio.Lock()
        
        # Statistics
        self._completed_count = 0
        self._failed_count = 0
        self._processing_times: List[float] = []
        self._wait_times: List[float] = []
    
    @property
    def name(self) -> str:
        return self._config.name
    
    async def submit(
        self,
        payload: Dict[str, Any],
        priority: int = JobPriority.NORMAL,
        delay_seconds: float = 0.0,
        scheduled_at: Optional[datetime] = None,
        **kwargs,
    ) -> Job:
        """Submit a job."""
        job = Job(
            queue=self._config.name,
            payload=payload,
            priority=priority,
            delay_seconds=delay_seconds,
            scheduled_at=scheduled_at,
            max_retries=self._config.retry_policy.max_retries,
            **kwargs,
        )
        
        if scheduled_at:
            job.status = JobStatus.SCHEDULED
        elif delay_seconds > 0:
            job.scheduled_at = datetime.utcnow() + timedelta(seconds=delay_seconds)
            job.status = JobStatus.SCHEDULED
        
        await self._store.save(job)
        
        if job.status == JobStatus.PENDING:
            async with self._queue_lock:
                heappush(self._priority_queue, job)
        
        return job
    
    async def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID."""
        return await self._store.get(job_id)
    
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a job."""
        job = await self._store.get(job_id)
        
        if not job:
            return False
        
        if job.status in (JobStatus.PENDING, JobStatus.SCHEDULED, JobStatus.RETRYING):
            job.status = JobStatus.CANCELLED
            job.completed_at = datetime.utcnow()
            await self._store.save(job)
            return True
        
        return False
    
    def register_handler(self, handler: JobHandler) -> None:
        """Register job handler."""
        self._handlers[self._config.name] = handler
    
    async def start_workers(self, count: Optional[int] = None) -> List[Worker]:
        """Start worker tasks."""
        count = count or self._config.min_workers
        count = min(count, self._config.max_workers)
        
        self._running = True
        workers = []
        
        for _ in range(count):
            worker = Worker(queue=self._config.name)
            worker.task = asyncio.create_task(self._worker_loop(worker))
            self._workers[worker.id] = worker
            workers.append(worker)
        
        logger.info(f"Started {count} workers for queue: {self._config.name}")
        
        return workers
    
    async def stop_workers(self) -> None:
        """Stop all workers."""
        self._running = False
        
        for worker in self._workers.values():
            if worker.task:
                worker.task.cancel()
                try:
                    await worker.task
                except asyncio.CancelledError:
                    pass
            worker.status = "stopped"
        
        logger.info(f"Stopped workers for queue: {self._config.name}")
    
    async def scale_workers(self, count: int) -> None:
        """Scale workers to specified count."""
        current = len(self._workers)
        
        if count > current:
            # Add workers
            for _ in range(count - current):
                worker = Worker(queue=self._config.name)
                worker.task = asyncio.create_task(self._worker_loop(worker))
                self._workers[worker.id] = worker
        
        elif count < current:
            # Remove workers
            workers_to_remove = list(self._workers.values())[count:]
            for worker in workers_to_remove:
                if worker.task:
                    worker.task.cancel()
                self._workers.pop(worker.id, None)
    
    async def get_stats(self) -> QueueStats:
        """Get queue statistics."""
        pending = await self._store.count_by_status(self._config.name, JobStatus.PENDING)
        running = await self._store.count_by_status(self._config.name, JobStatus.RUNNING)
        
        active_workers = len([w for w in self._workers.values() if w.status == "busy"])
        
        avg_wait = sum(self._wait_times) / len(self._wait_times) if self._wait_times else 0
        avg_proc = sum(self._processing_times) / len(self._processing_times) if self._processing_times else 0
        
        return QueueStats(
            queue_name=self._config.name,
            pending_jobs=pending,
            running_jobs=running,
            completed_jobs=self._completed_count,
            failed_jobs=self._failed_count,
            workers_count=len(self._workers),
            active_workers=active_workers,
            avg_wait_time_seconds=avg_wait,
            avg_processing_time_seconds=avg_proc,
        )
    
    async def _worker_loop(self, worker: Worker) -> None:
        """Worker loop."""
        while self._running:
            try:
                job = await self._get_next_job()
                
                if not job:
                    await asyncio.sleep(self._config.poll_interval_seconds)
                    continue
                
                worker.status = "busy"
                worker.current_job_id = job.id
                
                await self._process_job(job, worker)
                
                worker.status = "idle"
                worker.current_job_id = None
                worker.last_job_at = datetime.utcnow()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker error: {e}")
                await asyncio.sleep(1)
    
    async def _get_next_job(self) -> Optional[Job]:
        """Get next job to process."""
        # Check scheduled jobs
        scheduled = await self._store.get_scheduled(datetime.utcnow())
        for job in scheduled:
            job.status = JobStatus.PENDING
            await self._store.save(job)
            async with self._queue_lock:
                heappush(self._priority_queue, job)
        
        # Get from priority queue
        async with self._queue_lock:
            if self._priority_queue:
                return heappop(self._priority_queue)
        
        # Fallback to store
        pending = await self._store.get_pending(self._config.name, 1)
        return pending[0] if pending else None
    
    async def _process_job(self, job: Job, worker: Worker) -> None:
        """Process a job."""
        handler = self._handlers.get(self._config.name)
        
        if not handler:
            logger.error(f"No handler for queue: {self._config.name}")
            return
        
        job.status = JobStatus.RUNNING
        job.started_at = datetime.utcnow()
        job.attempt += 1
        await self._store.save(job)
        
        wait_time = (job.started_at - job.created_at).total_seconds()
        self._wait_times.append(wait_time)
        if len(self._wait_times) > 1000:
            self._wait_times = self._wait_times[-1000:]
        
        start_time = time.monotonic()
        
        try:
            async with self._job_semaphore:
                if asyncio.iscoroutinefunction(handler):
                    result = await asyncio.wait_for(
                        handler(job),
                        timeout=self._config.job_timeout_seconds,
                    )
                else:
                    result = handler(job)
            
            job.status = JobStatus.COMPLETED
            job.result = result
            job.completed_at = datetime.utcnow()
            
            worker.jobs_processed += 1
            self._completed_count += 1
            
        except asyncio.TimeoutError:
            await self._handle_failure(
                job, worker, f"Job timed out after {self._config.job_timeout_seconds}s"
            )
        
        except Exception as e:
            await self._handle_failure(job, worker, str(e), traceback.format_exc())
        
        finally:
            job.duration_seconds = time.monotonic() - start_time
            self._processing_times.append(job.duration_seconds)
            if len(self._processing_times) > 1000:
                self._processing_times = self._processing_times[-1000:]
            
            await self._store.save(job)
    
    async def _handle_failure(
        self,
        job: Job,
        worker: Worker,
        error_message: str,
        error_traceback: str = "",
    ) -> None:
        """Handle job failure."""
        job.error_message = error_message
        job.error_traceback = error_traceback
        
        worker.jobs_failed += 1
        
        if job.attempt < job.max_retries:
            # Schedule retry
            delay = self._calculate_retry_delay(job.attempt)
            job.status = JobStatus.RETRYING
            job.next_retry_at = datetime.utcnow() + timedelta(seconds=delay)
            job.scheduled_at = job.next_retry_at
            
            logger.warning(
                f"Job {job.id} failed, retrying in {delay}s (attempt {job.attempt})"
            )
        else:
            # Move to dead letter or mark as dead
            job.status = JobStatus.DEAD
            job.completed_at = datetime.utcnow()
            
            self._failed_count += 1
            
            logger.error(f"Job {job.id} failed permanently after {job.attempt} attempts")
    
    def _calculate_retry_delay(self, attempt: int) -> float:
        """Calculate retry delay."""
        policy = self._config.retry_policy
        
        if policy.strategy == RetryStrategy.FIXED:
            delay = policy.base_delay_seconds
        
        elif policy.strategy == RetryStrategy.LINEAR:
            delay = policy.base_delay_seconds * attempt
        
        elif policy.strategy == RetryStrategy.EXPONENTIAL:
            delay = policy.base_delay_seconds * (2 ** (attempt - 1))
        
        else:
            delay = policy.base_delay_seconds
        
        # Add jitter
        jitter = random.uniform(0, delay * 0.1)
        delay = delay + jitter
        
        return min(delay, policy.max_delay_seconds)


# Job queue manager
class JobQueueManager:
    """Job queue manager."""
    
    def __init__(
        self,
        store: Optional[JobStore] = None,
    ):
        self._store = store or InMemoryJobStore()
        self._queues: Dict[str, JobQueue] = {}
        self._handlers: Dict[str, JobHandler] = {}
        self._listeners: List[Callable] = []
    
    async def create_queue(
        self,
        name: str,
        max_workers: int = 5,
        max_concurrent_jobs: int = 10,
        job_timeout_seconds: float = 300.0,
        retry_policy: Optional[RetryPolicy] = None,
        **kwargs,
    ) -> JobQueue:
        """Create a job queue."""
        config = QueueConfig(
            name=name,
            max_workers=max_workers,
            max_concurrent_jobs=max_concurrent_jobs,
            job_timeout_seconds=job_timeout_seconds,
            retry_policy=retry_policy or RetryPolicy(),
            **kwargs,
        )
        
        queue = JobQueue(config, self._store)
        self._queues[name] = queue
        
        # Register any pre-registered handlers
        if name in self._handlers:
            queue.register_handler(self._handlers[name])
        
        logger.info(f"Queue created: {name}")
        
        return queue
    
    async def get_queue(self, name: str) -> Optional[JobQueue]:
        """Get queue by name."""
        return self._queues.get(name)
    
    async def list_queues(self) -> List[str]:
        """List queue names."""
        return list(self._queues.keys())
    
    async def delete_queue(self, name: str) -> bool:
        """Delete a queue."""
        queue = self._queues.pop(name, None)
        
        if queue:
            await queue.stop_workers()
            return True
        
        return False
    
    def handler(self, queue_name: str) -> Callable:
        """Decorator to register job handler."""
        def decorator(func: JobHandler) -> JobHandler:
            self._handlers[queue_name] = func
            
            queue = self._queues.get(queue_name)
            if queue:
                queue.register_handler(func)
            
            return func
        
        return decorator
    
    async def submit(
        self,
        queue: str,
        payload: Dict[str, Any],
        priority: int = JobPriority.NORMAL,
        delay_seconds: float = 0.0,
        scheduled_at: Optional[datetime] = None,
        **kwargs,
    ) -> Job:
        """Submit a job to a queue."""
        job_queue = self._queues.get(queue)
        
        if not job_queue:
            # Auto-create queue
            job_queue = await self.create_queue(queue)
        
        return await job_queue.submit(
            payload=payload,
            priority=priority,
            delay_seconds=delay_seconds,
            scheduled_at=scheduled_at,
            **kwargs,
        )
    
    async def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID."""
        return await self._store.get(job_id)
    
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a job."""
        job = await self._store.get(job_id)
        
        if not job:
            return False
        
        queue = self._queues.get(job.queue)
        
        if queue:
            return await queue.cancel_job(job_id)
        
        return False
    
    async def start_workers(
        self,
        queue: str,
        count: Optional[int] = None,
    ) -> List[Worker]:
        """Start workers for a queue."""
        job_queue = self._queues.get(queue)
        
        if not job_queue:
            raise QueueNotFoundError(f"Queue not found: {queue}")
        
        return await job_queue.start_workers(count)
    
    async def stop_workers(self, queue: str) -> None:
        """Stop workers for a queue."""
        job_queue = self._queues.get(queue)
        
        if job_queue:
            await job_queue.stop_workers()
    
    async def start_all(self) -> None:
        """Start workers for all queues."""
        for queue in self._queues.values():
            await queue.start_workers()
    
    async def stop_all(self) -> None:
        """Stop all workers."""
        for queue in self._queues.values():
            await queue.stop_workers()
    
    async def get_queue_stats(self, queue: str) -> Optional[QueueStats]:
        """Get queue statistics."""
        job_queue = self._queues.get(queue)
        
        if job_queue:
            return await job_queue.get_stats()
        
        return None
    
    async def get_stats(self) -> JobQueueStats:
        """Get overall statistics."""
        total_jobs = 0
        pending_jobs = 0
        running_jobs = 0
        total_workers = 0
        
        for queue in self._queues.values():
            stats = await queue.get_stats()
            pending_jobs += stats.pending_jobs
            running_jobs += stats.running_jobs
            total_workers += stats.workers_count
        
        return JobQueueStats(
            total_queues=len(self._queues),
            total_jobs=total_jobs,
            pending_jobs=pending_jobs,
            running_jobs=running_jobs,
            total_workers=total_workers,
        )
    
    def add_listener(self, listener: Callable) -> None:
        """Add event listener."""
        self._listeners.append(listener)


# Factory functions
def create_job_queue_manager() -> JobQueueManager:
    """Create job queue manager."""
    return JobQueueManager()


def create_job(
    queue: str,
    payload: Dict[str, Any],
    **kwargs,
) -> Job:
    """Create a job."""
    return Job(queue=queue, payload=payload, **kwargs)


def create_retry_policy(
    max_retries: int = 3,
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL,
    base_delay_seconds: float = 1.0,
) -> RetryPolicy:
    """Create retry policy."""
    return RetryPolicy(
        max_retries=max_retries,
        strategy=strategy,
        base_delay_seconds=base_delay_seconds,
    )


__all__ = [
    # Exceptions
    "JobError",
    "JobNotFoundError",
    "QueueNotFoundError",
    # Enums
    "JobStatus",
    "JobPriority",
    "RetryStrategy",
    # Data classes
    "RetryPolicy",
    "Job",
    "QueueConfig",
    "Worker",
    "QueueStats",
    "JobQueueStats",
    # Store
    "JobStore",
    "InMemoryJobStore",
    # Queue
    "JobQueue",
    # Manager
    "JobQueueManager",
    # Factory functions
    "create_job_queue_manager",
    "create_job",
    "create_retry_policy",
]
