"""
Enterprise Job Scheduler Module.

Cron-based job scheduling, task queuing,
distributed execution, and job management.

Example:
    # Create scheduler
    scheduler = create_job_scheduler()
    
    # Schedule recurring job
    @scheduler.cron("0 */6 * * *")  # Every 6 hours
    async def sync_data():
        await perform_sync()
    
    # Schedule one-time job
    job_id = await scheduler.schedule(
        cleanup_old_records,
        run_at=datetime.now() + timedelta(hours=1),
    )
    
    # Start scheduler
    await scheduler.start()
    
    # Queue job
    await scheduler.enqueue(process_item, item_id=123)
"""

from __future__ import annotations

import asyncio
import functools
import logging
import re
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from heapq import heappush, heappop
from typing import (
    Any,
    Callable,
    Coroutine,
    Dict,
    Generic,
    Iterator,
    List,
    Optional,
    Set,
    Tuple,
    TypeVar,
)

T = TypeVar('T')


logger = logging.getLogger(__name__)


class SchedulerError(Exception):
    """Scheduler error."""
    pass


class JobNotFoundError(SchedulerError):
    """Job not found."""
    pass


class JobExecutionError(SchedulerError):
    """Job execution error."""
    pass


class QueueFullError(SchedulerError):
    """Queue is full."""
    pass


class JobStatus(str, Enum):
    """Job status."""
    PENDING = "pending"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class JobPriority(int, Enum):
    """Job priority."""
    LOW = 0
    NORMAL = 50
    HIGH = 75
    CRITICAL = 100


class TriggerType(str, Enum):
    """Trigger types."""
    ONCE = "once"
    CRON = "cron"
    INTERVAL = "interval"
    DELAYED = "delayed"


@dataclass
class JobResult:
    """Job execution result."""
    success: bool
    result: Any = None
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class Job:
    """Scheduled job."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    func: Optional[Callable] = None
    args: Tuple = field(default_factory=tuple)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    trigger_type: TriggerType = TriggerType.ONCE
    trigger_value: str = ""
    status: JobStatus = JobStatus.PENDING
    priority: JobPriority = JobPriority.NORMAL
    next_run: Optional[datetime] = None
    last_run: Optional[datetime] = None
    run_count: int = 0
    max_retries: int = 3
    retry_count: int = 0
    retry_delay: timedelta = field(default_factory=lambda: timedelta(seconds=60))
    timeout: Optional[timedelta] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    results: List[JobResult] = field(default_factory=list)
    
    def __lt__(self, other: "Job") -> bool:
        """Compare by priority and next run time."""
        if self.priority != other.priority:
            return self.priority.value > other.priority.value
        
        if self.next_run and other.next_run:
            return self.next_run < other.next_run
        
        return False


@dataclass
class QueuedTask:
    """Queued task."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    func: Optional[Callable] = None
    args: Tuple = field(default_factory=tuple)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    priority: JobPriority = JobPriority.NORMAL
    status: JobStatus = JobStatus.PENDING
    queued_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Any = None
    error: Optional[str] = None
    
    def __lt__(self, other: "QueuedTask") -> bool:
        if self.priority != other.priority:
            return self.priority.value > other.priority.value
        return self.queued_at < other.queued_at


@dataclass
class SchedulerStats:
    """Scheduler statistics."""
    total_jobs: int = 0
    running_jobs: int = 0
    completed_jobs: int = 0
    failed_jobs: int = 0
    queued_tasks: int = 0
    processed_tasks: int = 0


# Cron parser
class CronExpression:
    """Cron expression parser."""
    
    def __init__(self, expression: str):
        self._expression = expression
        parts = expression.split()
        
        if len(parts) != 5:
            raise ValueError(f"Invalid cron expression: {expression}")
        
        self._minute = self._parse_field(parts[0], 0, 59)
        self._hour = self._parse_field(parts[1], 0, 23)
        self._day = self._parse_field(parts[2], 1, 31)
        self._month = self._parse_field(parts[3], 1, 12)
        self._weekday = self._parse_field(parts[4], 0, 6)
    
    def _parse_field(
        self,
        field: str,
        min_val: int,
        max_val: int,
    ) -> Set[int]:
        """Parse cron field."""
        values = set()
        
        for part in field.split(","):
            if part == "*":
                values.update(range(min_val, max_val + 1))
            elif "/" in part:
                # Step values
                base, step = part.split("/")
                step = int(step)
                
                if base == "*":
                    start = min_val
                else:
                    start = int(base)
                
                values.update(range(start, max_val + 1, step))
            elif "-" in part:
                # Range
                start, end = part.split("-")
                values.update(range(int(start), int(end) + 1))
            else:
                values.add(int(part))
        
        return values
    
    def next_run(self, after: Optional[datetime] = None) -> datetime:
        """Get next run time."""
        now = after or datetime.utcnow()
        current = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
        
        for _ in range(366 * 24 * 60):  # Max 1 year search
            if (
                current.minute in self._minute and
                current.hour in self._hour and
                current.day in self._day and
                current.month in self._month and
                current.weekday() in self._weekday
            ):
                return current
            
            current += timedelta(minutes=1)
        
        raise ValueError("Could not find next run time")


# Job store interface
class JobStore(ABC):
    """Abstract job store."""
    
    @abstractmethod
    async def add(self, job: Job) -> None:
        """Add job."""
        pass
    
    @abstractmethod
    async def get(self, job_id: str) -> Optional[Job]:
        """Get job by ID."""
        pass
    
    @abstractmethod
    async def update(self, job: Job) -> None:
        """Update job."""
        pass
    
    @abstractmethod
    async def delete(self, job_id: str) -> bool:
        """Delete job."""
        pass
    
    @abstractmethod
    async def get_due_jobs(self, before: datetime) -> List[Job]:
        """Get jobs due for execution."""
        pass
    
    @abstractmethod
    async def get_all(self) -> List[Job]:
        """Get all jobs."""
        pass


class InMemoryJobStore(JobStore):
    """In-memory job store."""
    
    def __init__(self):
        self._jobs: Dict[str, Job] = {}
    
    async def add(self, job: Job) -> None:
        self._jobs[job.id] = job
    
    async def get(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)
    
    async def update(self, job: Job) -> None:
        self._jobs[job.id] = job
    
    async def delete(self, job_id: str) -> bool:
        if job_id in self._jobs:
            del self._jobs[job_id]
            return True
        return False
    
    async def get_due_jobs(self, before: datetime) -> List[Job]:
        due = []
        
        for job in self._jobs.values():
            if (
                job.status == JobStatus.SCHEDULED and
                job.next_run and
                job.next_run <= before
            ):
                due.append(job)
        
        return sorted(due)
    
    async def get_all(self) -> List[Job]:
        return list(self._jobs.values())


# Task queue
class TaskQueue:
    """Task queue for async processing."""
    
    def __init__(
        self,
        max_size: int = 10000,
        workers: int = 4,
    ):
        self._max_size = max_size
        self._workers = workers
        self._queue: List[QueuedTask] = []
        self._processing: Dict[str, QueuedTask] = {}
        self._completed: List[QueuedTask] = []
        self._worker_tasks: List[asyncio.Task] = []
        self._running = False
        self._lock = asyncio.Lock()
    
    async def enqueue(
        self,
        func: Callable,
        *args,
        priority: JobPriority = JobPriority.NORMAL,
        **kwargs,
    ) -> str:
        """Add task to queue."""
        if len(self._queue) >= self._max_size:
            raise QueueFullError("Task queue is full")
        
        task = QueuedTask(
            func=func,
            args=args,
            kwargs=kwargs,
            priority=priority,
        )
        
        async with self._lock:
            heappush(self._queue, task)
        
        return task.id
    
    async def start(self) -> None:
        """Start queue workers."""
        self._running = True
        
        for i in range(self._workers):
            task = asyncio.create_task(self._worker(i))
            self._worker_tasks.append(task)
    
    async def stop(self) -> None:
        """Stop queue workers."""
        self._running = False
        
        for task in self._worker_tasks:
            task.cancel()
        
        self._worker_tasks.clear()
    
    async def _worker(self, worker_id: int) -> None:
        """Worker loop."""
        while self._running:
            try:
                task = await self._get_task()
                
                if task:
                    await self._process_task(task)
                else:
                    await asyncio.sleep(0.1)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")
    
    async def _get_task(self) -> Optional[QueuedTask]:
        """Get next task from queue."""
        async with self._lock:
            if self._queue:
                return heappop(self._queue)
        return None
    
    async def _process_task(self, task: QueuedTask) -> None:
        """Process a task."""
        task.status = JobStatus.RUNNING
        task.started_at = datetime.utcnow()
        self._processing[task.id] = task
        
        try:
            if asyncio.iscoroutinefunction(task.func):
                result = await task.func(*task.args, **task.kwargs)
            else:
                result = task.func(*task.args, **task.kwargs)
            
            task.result = result
            task.status = JobStatus.COMPLETED
            
        except Exception as e:
            task.error = str(e)
            task.status = JobStatus.FAILED
            logger.error(f"Task {task.id} failed: {e}")
        
        finally:
            task.completed_at = datetime.utcnow()
            del self._processing[task.id]
            self._completed.append(task)
    
    def pending_count(self) -> int:
        """Get pending task count."""
        return len(self._queue)
    
    def processing_count(self) -> int:
        """Get processing task count."""
        return len(self._processing)
    
    def get_task(self, task_id: str) -> Optional[QueuedTask]:
        """Get task by ID."""
        for task in self._queue:
            if task.id == task_id:
                return task
        
        if task_id in self._processing:
            return self._processing[task_id]
        
        for task in self._completed:
            if task.id == task_id:
                return task
        
        return None


# Job scheduler
class JobScheduler:
    """
    Job scheduler service.
    """
    
    def __init__(
        self,
        store: Optional[JobStore] = None,
        check_interval: float = 1.0,
        max_concurrent: int = 10,
    ):
        self._store = store or InMemoryJobStore()
        self._check_interval = check_interval
        self._max_concurrent = max_concurrent
        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None
        self._running_jobs: Dict[str, asyncio.Task] = {}
        self._queue = TaskQueue()
        self._hooks: Dict[str, List[Callable]] = defaultdict(list)
    
    async def schedule(
        self,
        func: Callable,
        *args,
        run_at: Optional[datetime] = None,
        name: Optional[str] = None,
        priority: JobPriority = JobPriority.NORMAL,
        **kwargs,
    ) -> str:
        """
        Schedule a one-time job.
        
        Args:
            func: Function to execute
            *args: Function arguments
            run_at: When to run (default: now)
            name: Job name
            priority: Job priority
            **kwargs: Function keyword arguments
            
        Returns:
            Job ID
        """
        job = Job(
            name=name or func.__name__,
            func=func,
            args=args,
            kwargs=kwargs,
            trigger_type=TriggerType.ONCE,
            priority=priority,
            next_run=run_at or datetime.utcnow(),
            status=JobStatus.SCHEDULED,
        )
        
        await self._store.add(job)
        
        logger.info(f"Scheduled job {job.name} ({job.id})")
        
        return job.id
    
    async def schedule_interval(
        self,
        func: Callable,
        interval: timedelta,
        *args,
        name: Optional[str] = None,
        start_at: Optional[datetime] = None,
        **kwargs,
    ) -> str:
        """
        Schedule a recurring interval job.
        
        Args:
            func: Function to execute
            interval: Interval between runs
            *args: Function arguments
            name: Job name
            start_at: When to start
            **kwargs: Function keyword arguments
            
        Returns:
            Job ID
        """
        job = Job(
            name=name or func.__name__,
            func=func,
            args=args,
            kwargs=kwargs,
            trigger_type=TriggerType.INTERVAL,
            trigger_value=str(interval.total_seconds()),
            priority=JobPriority.NORMAL,
            next_run=start_at or datetime.utcnow(),
            status=JobStatus.SCHEDULED,
        )
        
        await self._store.add(job)
        
        return job.id
    
    async def schedule_cron(
        self,
        func: Callable,
        expression: str,
        *args,
        name: Optional[str] = None,
        **kwargs,
    ) -> str:
        """
        Schedule a cron job.
        
        Args:
            func: Function to execute
            expression: Cron expression
            *args: Function arguments
            name: Job name
            **kwargs: Function keyword arguments
            
        Returns:
            Job ID
        """
        cron = CronExpression(expression)
        
        job = Job(
            name=name or func.__name__,
            func=func,
            args=args,
            kwargs=kwargs,
            trigger_type=TriggerType.CRON,
            trigger_value=expression,
            priority=JobPriority.NORMAL,
            next_run=cron.next_run(),
            status=JobStatus.SCHEDULED,
        )
        
        await self._store.add(job)
        
        return job.id
    
    def cron(
        self,
        expression: str,
        name: Optional[str] = None,
    ) -> Callable:
        """
        Decorator to schedule cron job.
        
        Args:
            expression: Cron expression
            name: Job name
            
        Returns:
            Decorator
        """
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                return await func(*args, **kwargs)
            
            # Schedule on scheduler start
            asyncio.create_task(
                self.schedule_cron(func, expression, name=name or func.__name__)
            )
            
            return wrapper
        
        return decorator
    
    def interval(
        self,
        seconds: Optional[int] = None,
        minutes: Optional[int] = None,
        hours: Optional[int] = None,
    ) -> Callable:
        """
        Decorator to schedule interval job.
        
        Args:
            seconds: Interval seconds
            minutes: Interval minutes
            hours: Interval hours
            
        Returns:
            Decorator
        """
        total_seconds = (seconds or 0) + (minutes or 0) * 60 + (hours or 0) * 3600
        interval = timedelta(seconds=total_seconds)
        
        def decorator(func: Callable) -> Callable:
            asyncio.create_task(
                self.schedule_interval(func, interval, name=func.__name__)
            )
            return func
        
        return decorator
    
    async def cancel(self, job_id: str) -> bool:
        """
        Cancel a job.
        
        Args:
            job_id: Job ID
            
        Returns:
            True if cancelled
        """
        job = await self._store.get(job_id)
        
        if not job:
            return False
        
        job.status = JobStatus.CANCELLED
        await self._store.update(job)
        
        if job_id in self._running_jobs:
            self._running_jobs[job_id].cancel()
        
        logger.info(f"Cancelled job {job.name} ({job_id})")
        
        return True
    
    async def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID."""
        return await self._store.get(job_id)
    
    async def get_jobs(self) -> List[Job]:
        """Get all jobs."""
        return await self._store.get_all()
    
    async def start(self) -> None:
        """Start scheduler."""
        self._running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        await self._queue.start()
        
        logger.info("Job scheduler started")
    
    async def stop(self) -> None:
        """Stop scheduler."""
        self._running = False
        
        if self._scheduler_task:
            self._scheduler_task.cancel()
        
        for task in self._running_jobs.values():
            task.cancel()
        
        await self._queue.stop()
        
        logger.info("Job scheduler stopped")
    
    async def _scheduler_loop(self) -> None:
        """Main scheduler loop."""
        while self._running:
            try:
                await self._check_due_jobs()
                await asyncio.sleep(self._check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
    
    async def _check_due_jobs(self) -> None:
        """Check for due jobs."""
        now = datetime.utcnow()
        due_jobs = await self._store.get_due_jobs(now)
        
        for job in due_jobs:
            if len(self._running_jobs) >= self._max_concurrent:
                break
            
            if job.id not in self._running_jobs:
                task = asyncio.create_task(self._execute_job(job))
                self._running_jobs[job.id] = task
    
    async def _execute_job(self, job: Job) -> None:
        """Execute a job."""
        job.status = JobStatus.RUNNING
        job.last_run = datetime.utcnow()
        await self._store.update(job)
        
        await self._trigger("job_started", job)
        
        result = JobResult(
            success=False,
            started_at=datetime.utcnow(),
        )
        
        try:
            import time
            start = time.perf_counter()
            
            if job.timeout:
                coro = job.func(*job.args, **job.kwargs)
                if asyncio.iscoroutine(coro):
                    output = await asyncio.wait_for(
                        coro,
                        timeout=job.timeout.total_seconds(),
                    )
                else:
                    output = coro
            else:
                if asyncio.iscoroutinefunction(job.func):
                    output = await job.func(*job.args, **job.kwargs)
                else:
                    output = job.func(*job.args, **job.kwargs)
            
            result.success = True
            result.result = output
            result.execution_time_ms = (time.perf_counter() - start) * 1000
            
            job.status = JobStatus.COMPLETED
            job.run_count += 1
            
            await self._trigger("job_completed", job, result)
            
        except Exception as e:
            result.error = str(e)
            job.retry_count += 1
            
            if job.retry_count < job.max_retries:
                job.status = JobStatus.RETRYING
                job.next_run = datetime.utcnow() + job.retry_delay
            else:
                job.status = JobStatus.FAILED
            
            await self._trigger("job_failed", job, result)
            
            logger.error(f"Job {job.name} failed: {e}")
        
        finally:
            result.completed_at = datetime.utcnow()
            job.results.append(result)
            
            # Schedule next run for recurring jobs
            if job.status == JobStatus.COMPLETED:
                if job.trigger_type == TriggerType.INTERVAL:
                    interval = timedelta(seconds=float(job.trigger_value))
                    job.next_run = datetime.utcnow() + interval
                    job.status = JobStatus.SCHEDULED
                
                elif job.trigger_type == TriggerType.CRON:
                    cron = CronExpression(job.trigger_value)
                    job.next_run = cron.next_run()
                    job.status = JobStatus.SCHEDULED
            
            await self._store.update(job)
            
            if job.id in self._running_jobs:
                del self._running_jobs[job.id]
    
    async def enqueue(
        self,
        func: Callable,
        *args,
        priority: JobPriority = JobPriority.NORMAL,
        **kwargs,
    ) -> str:
        """
        Add task to queue.
        
        Args:
            func: Function to execute
            *args: Function arguments
            priority: Task priority
            **kwargs: Function keyword arguments
            
        Returns:
            Task ID
        """
        return await self._queue.enqueue(
            func, *args, priority=priority, **kwargs
        )
    
    def on(
        self,
        event: str,
        handler: Callable,
    ) -> None:
        """Add event handler."""
        self._hooks[event].append(handler)
    
    async def _trigger(
        self,
        event: str,
        *args,
        **kwargs,
    ) -> None:
        """Trigger event handlers."""
        for handler in self._hooks[event]:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(*args, **kwargs)
                else:
                    handler(*args, **kwargs)
            except Exception as e:
                logger.error(f"Event handler error: {e}")
    
    async def get_stats(self) -> SchedulerStats:
        """Get scheduler statistics."""
        jobs = await self._store.get_all()
        
        stats = SchedulerStats(
            total_jobs=len(jobs),
            running_jobs=len(self._running_jobs),
            queued_tasks=self._queue.pending_count(),
        )
        
        for job in jobs:
            if job.status == JobStatus.COMPLETED:
                stats.completed_jobs += 1
            elif job.status == JobStatus.FAILED:
                stats.failed_jobs += 1
        
        return stats


# Factory functions
def create_job_scheduler(
    check_interval: float = 1.0,
    max_concurrent: int = 10,
) -> JobScheduler:
    """Create job scheduler."""
    return JobScheduler(
        check_interval=check_interval,
        max_concurrent=max_concurrent,
    )


def create_task_queue(
    max_size: int = 10000,
    workers: int = 4,
) -> TaskQueue:
    """Create task queue."""
    return TaskQueue(max_size=max_size, workers=workers)


__all__ = [
    # Exceptions
    "SchedulerError",
    "JobNotFoundError",
    "JobExecutionError",
    "QueueFullError",
    # Enums
    "JobStatus",
    "JobPriority",
    "TriggerType",
    # Data classes
    "JobResult",
    "Job",
    "QueuedTask",
    "SchedulerStats",
    # Cron
    "CronExpression",
    # Store
    "JobStore",
    "InMemoryJobStore",
    # Queue
    "TaskQueue",
    # Scheduler
    "JobScheduler",
    # Factory functions
    "create_job_scheduler",
    "create_task_queue",
]
