"""
Enterprise Task Scheduler Module.

Provides task scheduling, cron expressions, recurring jobs,
job dependencies, and distributed task scheduling.

Example:
    # Create scheduler
    scheduler = create_task_scheduler()
    
    # Schedule tasks
    scheduler.schedule_at(process_report, datetime(2024, 1, 1, 9, 0))
    scheduler.schedule_cron(cleanup_job, "0 0 * * *")  # Daily at midnight
    
    # Use decorator
    @scheduled(cron="*/5 * * * *")  # Every 5 minutes
    async def periodic_task():
        ...
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    TypeVar,
)

T = TypeVar('T')


logger = logging.getLogger(__name__)


class SchedulerError(Exception):
    """Base scheduler error."""
    pass


class JobNotFoundError(SchedulerError):
    """Job not found."""
    pass


class CronParseError(SchedulerError):
    """Invalid cron expression."""
    pass


class JobState(str, Enum):
    """Job state."""
    PENDING = "pending"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class TriggerType(str, Enum):
    """Trigger type."""
    ONCE = "once"
    INTERVAL = "interval"
    CRON = "cron"
    DEPENDENCY = "dependency"


@dataclass
class CronExpression:
    """Parsed cron expression."""
    minute: Set[int]
    hour: Set[int]
    day: Set[int]
    month: Set[int]
    day_of_week: Set[int]
    
    @classmethod
    def parse(cls, expression: str) -> "CronExpression":
        """Parse cron expression."""
        parts = expression.strip().split()
        if len(parts) != 5:
            raise CronParseError(f"Invalid cron expression: {expression}")
        
        def parse_field(field: str, min_val: int, max_val: int) -> Set[int]:
            result = set()
            
            for part in field.split(','):
                if part == '*':
                    result.update(range(min_val, max_val + 1))
                elif '-' in part:
                    start, end = part.split('-')
                    result.update(range(int(start), int(end) + 1))
                elif '/' in part:
                    base, step = part.split('/')
                    if base == '*':
                        start = min_val
                    else:
                        start = int(base)
                    result.update(range(start, max_val + 1, int(step)))
                else:
                    result.add(int(part))
            
            return result
        
        return cls(
            minute=parse_field(parts[0], 0, 59),
            hour=parse_field(parts[1], 0, 23),
            day=parse_field(parts[2], 1, 31),
            month=parse_field(parts[3], 1, 12),
            day_of_week=parse_field(parts[4], 0, 6),
        )
    
    def matches(self, dt: datetime) -> bool:
        """Check if datetime matches cron expression."""
        return (
            dt.minute in self.minute
            and dt.hour in self.hour
            and dt.day in self.day
            and dt.month in self.month
            and dt.weekday() in self.day_of_week
        )
    
    def next_run(self, after: Optional[datetime] = None) -> datetime:
        """Calculate next run time."""
        if after is None:
            after = datetime.now()
        
        # Start from next minute
        dt = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
        
        # Find next matching time (max 1 year search)
        max_iterations = 365 * 24 * 60
        
        for _ in range(max_iterations):
            if self.matches(dt):
                return dt
            dt += timedelta(minutes=1)
        
        raise SchedulerError("Could not find next run time")


@dataclass
class JobConfig:
    """Job configuration."""
    max_retries: int = 0
    retry_delay: float = 60.0
    timeout: Optional[float] = None
    priority: int = 0
    tags: List[str] = field(default_factory=list)


@dataclass
class JobExecution:
    """Job execution record."""
    execution_id: str
    job_id: str
    state: JobState
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Any = None
    error: Optional[str] = None
    retries: int = 0


@dataclass
class Job:
    """Scheduled job."""
    id: str
    name: str
    func: Callable
    args: Tuple
    kwargs: Dict
    trigger_type: TriggerType
    state: JobState
    config: JobConfig
    
    # Scheduling
    next_run: Optional[datetime] = None
    interval: Optional[float] = None  # seconds
    cron: Optional[CronExpression] = None
    dependencies: List[str] = field(default_factory=list)
    
    # Execution history
    last_run: Optional[datetime] = None
    run_count: int = 0
    error_count: int = 0


@dataclass
class SchedulerStats:
    """Scheduler statistics."""
    total_jobs: int = 0
    active_jobs: int = 0
    paused_jobs: int = 0
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0


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
    async def delete(self, job_id: str) -> None:
        """Delete job."""
        pass
    
    @abstractmethod
    async def get_due_jobs(self, before: datetime) -> List[Job]:
        """Get jobs due for execution."""
        pass
    
    @abstractmethod
    async def all(self) -> List[Job]:
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
    
    async def delete(self, job_id: str) -> None:
        self._jobs.pop(job_id, None)
    
    async def get_due_jobs(self, before: datetime) -> List[Job]:
        due = []
        for job in self._jobs.values():
            if (
                job.state == JobState.SCHEDULED
                and job.next_run
                and job.next_run <= before
            ):
                due.append(job)
        return sorted(due, key=lambda j: (j.config.priority, j.next_run))
    
    async def all(self) -> List[Job]:
        return list(self._jobs.values())


class TaskScheduler(ABC):
    """Abstract task scheduler."""
    
    @abstractmethod
    async def schedule_at(
        self,
        func: Callable,
        run_at: datetime,
        *args,
        name: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Schedule task to run at specific time."""
        pass
    
    @abstractmethod
    async def schedule_interval(
        self,
        func: Callable,
        interval: float,
        *args,
        name: Optional[str] = None,
        start_immediately: bool = False,
        **kwargs,
    ) -> str:
        """Schedule task to run at interval."""
        pass
    
    @abstractmethod
    async def schedule_cron(
        self,
        func: Callable,
        cron: str,
        *args,
        name: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Schedule task with cron expression."""
        pass
    
    @abstractmethod
    async def cancel(self, job_id: str) -> None:
        """Cancel a scheduled job."""
        pass
    
    @abstractmethod
    async def pause(self, job_id: str) -> None:
        """Pause a job."""
        pass
    
    @abstractmethod
    async def resume(self, job_id: str) -> None:
        """Resume a paused job."""
        pass
    
    @abstractmethod
    async def start(self) -> None:
        """Start the scheduler."""
        pass
    
    @abstractmethod
    async def shutdown(self, wait: bool = True) -> None:
        """Shutdown the scheduler."""
        pass
    
    @abstractmethod
    async def stats(self) -> SchedulerStats:
        """Get scheduler statistics."""
        pass


class SimpleTaskScheduler(TaskScheduler):
    """
    Simple task scheduler implementation.
    """
    
    def __init__(
        self,
        store: Optional[JobStore] = None,
        check_interval: float = 1.0,
    ):
        self._store = store or InMemoryJobStore()
        self._check_interval = check_interval
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._stats = SchedulerStats()
        self._executions: Dict[str, JobExecution] = {}
    
    async def schedule_at(
        self,
        func: Callable,
        run_at: datetime,
        *args,
        name: Optional[str] = None,
        config: Optional[JobConfig] = None,
        **kwargs,
    ) -> str:
        job_id = str(uuid.uuid4())
        
        job = Job(
            id=job_id,
            name=name or func.__name__,
            func=func,
            args=args,
            kwargs=kwargs,
            trigger_type=TriggerType.ONCE,
            state=JobState.SCHEDULED,
            config=config or JobConfig(),
            next_run=run_at,
        )
        
        await self._store.add(job)
        self._stats.total_jobs += 1
        self._stats.active_jobs += 1
        
        return job_id
    
    async def schedule_interval(
        self,
        func: Callable,
        interval: float,
        *args,
        name: Optional[str] = None,
        start_immediately: bool = False,
        config: Optional[JobConfig] = None,
        **kwargs,
    ) -> str:
        job_id = str(uuid.uuid4())
        
        next_run = datetime.now()
        if not start_immediately:
            next_run += timedelta(seconds=interval)
        
        job = Job(
            id=job_id,
            name=name or func.__name__,
            func=func,
            args=args,
            kwargs=kwargs,
            trigger_type=TriggerType.INTERVAL,
            state=JobState.SCHEDULED,
            config=config or JobConfig(),
            next_run=next_run,
            interval=interval,
        )
        
        await self._store.add(job)
        self._stats.total_jobs += 1
        self._stats.active_jobs += 1
        
        return job_id
    
    async def schedule_cron(
        self,
        func: Callable,
        cron: str,
        *args,
        name: Optional[str] = None,
        config: Optional[JobConfig] = None,
        **kwargs,
    ) -> str:
        job_id = str(uuid.uuid4())
        cron_expr = CronExpression.parse(cron)
        
        job = Job(
            id=job_id,
            name=name or func.__name__,
            func=func,
            args=args,
            kwargs=kwargs,
            trigger_type=TriggerType.CRON,
            state=JobState.SCHEDULED,
            config=config or JobConfig(),
            next_run=cron_expr.next_run(),
            cron=cron_expr,
        )
        
        await self._store.add(job)
        self._stats.total_jobs += 1
        self._stats.active_jobs += 1
        
        return job_id
    
    async def schedule_after(
        self,
        func: Callable,
        dependencies: List[str],
        *args,
        name: Optional[str] = None,
        config: Optional[JobConfig] = None,
        **kwargs,
    ) -> str:
        """Schedule task to run after dependencies complete."""
        job_id = str(uuid.uuid4())
        
        job = Job(
            id=job_id,
            name=name or func.__name__,
            func=func,
            args=args,
            kwargs=kwargs,
            trigger_type=TriggerType.DEPENDENCY,
            state=JobState.PENDING,
            config=config or JobConfig(),
            dependencies=dependencies,
        )
        
        await self._store.add(job)
        self._stats.total_jobs += 1
        
        return job_id
    
    async def cancel(self, job_id: str) -> None:
        job = await self._store.get(job_id)
        if not job:
            raise JobNotFoundError(f"Job not found: {job_id}")
        
        job.state = JobState.CANCELLED
        await self._store.update(job)
        self._stats.active_jobs -= 1
    
    async def pause(self, job_id: str) -> None:
        job = await self._store.get(job_id)
        if not job:
            raise JobNotFoundError(f"Job not found: {job_id}")
        
        job.state = JobState.PAUSED
        await self._store.update(job)
        self._stats.active_jobs -= 1
        self._stats.paused_jobs += 1
    
    async def resume(self, job_id: str) -> None:
        job = await self._store.get(job_id)
        if not job:
            raise JobNotFoundError(f"Job not found: {job_id}")
        
        job.state = JobState.SCHEDULED
        await self._store.update(job)
        self._stats.active_jobs += 1
        self._stats.paused_jobs -= 1
    
    async def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID."""
        return await self._store.get(job_id)
    
    async def list_jobs(self) -> List[Job]:
        """List all jobs."""
        return await self._store.all()
    
    async def start(self) -> None:
        """Start the scheduler."""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Scheduler started")
    
    async def shutdown(self, wait: bool = True) -> None:
        """Shutdown the scheduler."""
        self._running = False
        
        if self._task:
            if wait:
                # Wait for current execution
                await asyncio.sleep(self._check_interval)
            
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        logger.info("Scheduler shutdown")
    
    async def stats(self) -> SchedulerStats:
        return self._stats
    
    async def _run_loop(self) -> None:
        """Main scheduler loop."""
        while self._running:
            try:
                now = datetime.now()
                
                # Get due jobs
                due_jobs = await self._store.get_due_jobs(now)
                
                # Execute due jobs
                for job in due_jobs:
                    await self._execute_job(job)
                
                # Check dependency jobs
                await self._check_dependency_jobs()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
            
            await asyncio.sleep(self._check_interval)
    
    async def _execute_job(self, job: Job) -> None:
        """Execute a job."""
        execution_id = str(uuid.uuid4())
        
        execution = JobExecution(
            execution_id=execution_id,
            job_id=job.id,
            state=JobState.RUNNING,
            started_at=datetime.now(),
        )
        self._executions[execution_id] = execution
        
        job.state = JobState.RUNNING
        await self._store.update(job)
        
        self._stats.total_executions += 1
        
        try:
            # Execute with timeout
            if job.config.timeout:
                coro = job.func(*job.args, **job.kwargs)
                if asyncio.iscoroutine(coro):
                    result = await asyncio.wait_for(coro, timeout=job.config.timeout)
                else:
                    result = coro
            else:
                result = job.func(*job.args, **job.kwargs)
                if asyncio.iscoroutine(result):
                    result = await result
            
            execution.state = JobState.COMPLETED
            execution.result = result
            execution.completed_at = datetime.now()
            
            job.state = JobState.COMPLETED
            job.last_run = datetime.now()
            job.run_count += 1
            
            self._stats.successful_executions += 1
            
        except Exception as e:
            execution.state = JobState.FAILED
            execution.error = str(e)
            execution.completed_at = datetime.now()
            
            job.error_count += 1
            self._stats.failed_executions += 1
            
            logger.error(f"Job {job.name} failed: {e}")
        
        # Schedule next run for recurring jobs
        if job.trigger_type == TriggerType.INTERVAL and job.interval:
            job.next_run = datetime.now() + timedelta(seconds=job.interval)
            job.state = JobState.SCHEDULED
        elif job.trigger_type == TriggerType.CRON and job.cron:
            job.next_run = job.cron.next_run()
            job.state = JobState.SCHEDULED
        elif job.trigger_type == TriggerType.ONCE:
            self._stats.active_jobs -= 1
        
        await self._store.update(job)
    
    async def _check_dependency_jobs(self) -> None:
        """Check and schedule dependency jobs."""
        all_jobs = await self._store.all()
        
        for job in all_jobs:
            if job.trigger_type != TriggerType.DEPENDENCY:
                continue
            if job.state != JobState.PENDING:
                continue
            
            # Check if all dependencies completed
            all_done = True
            for dep_id in job.dependencies:
                dep_job = await self._store.get(dep_id)
                if not dep_job or dep_job.state != JobState.COMPLETED:
                    all_done = False
                    break
            
            if all_done:
                job.state = JobState.SCHEDULED
                job.next_run = datetime.now()
                await self._store.update(job)


class SchedulerRegistry:
    """Registry for task schedulers."""
    
    def __init__(self):
        self._schedulers: Dict[str, TaskScheduler] = {}
        self._default: Optional[str] = None
    
    def register(
        self,
        name: str,
        scheduler: TaskScheduler,
        default: bool = False,
    ) -> None:
        self._schedulers[name] = scheduler
        if default or self._default is None:
            self._default = name
    
    def get(self, name: Optional[str] = None) -> TaskScheduler:
        name = name or self._default
        if not name or name not in self._schedulers:
            raise SchedulerError(f"Scheduler not found: {name}")
        return self._schedulers[name]


# Global registry
_global_registry = SchedulerRegistry()


# Decorators
def scheduled(
    cron: Optional[str] = None,
    interval: Optional[float] = None,
    run_at: Optional[datetime] = None,
    scheduler_name: Optional[str] = None,
) -> Callable:
    """
    Decorator to schedule function.
    
    Example:
        @scheduled(cron="0 0 * * *")
        async def daily_cleanup():
            ...
        
        @scheduled(interval=300)
        async def health_check():
            ...
    """
    def decorator(func: Callable) -> Callable:
        func._scheduled = {
            "cron": cron,
            "interval": interval,
            "run_at": run_at,
            "scheduler_name": scheduler_name,
        }
        return func
    
    return decorator


def every(
    seconds: Optional[float] = None,
    minutes: Optional[float] = None,
    hours: Optional[float] = None,
) -> Callable:
    """
    Decorator for interval scheduling.
    
    Example:
        @every(minutes=5)
        async def periodic_task():
            ...
    """
    interval = 0.0
    if seconds:
        interval += seconds
    if minutes:
        interval += minutes * 60
    if hours:
        interval += hours * 3600
    
    return scheduled(interval=interval)


# Factory functions
def create_task_scheduler(
    store: Optional[JobStore] = None,
    check_interval: float = 1.0,
) -> SimpleTaskScheduler:
    """Create a task scheduler."""
    return SimpleTaskScheduler(store, check_interval)


def create_job_config(
    max_retries: int = 0,
    retry_delay: float = 60.0,
    timeout: Optional[float] = None,
    priority: int = 0,
    tags: Optional[List[str]] = None,
) -> JobConfig:
    """Create a job configuration."""
    return JobConfig(
        max_retries=max_retries,
        retry_delay=retry_delay,
        timeout=timeout,
        priority=priority,
        tags=tags or [],
    )


def parse_cron(expression: str) -> CronExpression:
    """Parse a cron expression."""
    return CronExpression.parse(expression)


def register_scheduler(
    name: str,
    scheduler: TaskScheduler,
    default: bool = False,
) -> None:
    """Register scheduler in global registry."""
    _global_registry.register(name, scheduler, default)


def get_scheduler(name: Optional[str] = None) -> TaskScheduler:
    """Get scheduler from global registry."""
    try:
        return _global_registry.get(name)
    except SchedulerError:
        scheduler = create_task_scheduler()
        register_scheduler("default", scheduler, default=True)
        return scheduler


__all__ = [
    # Exceptions
    "SchedulerError",
    "JobNotFoundError",
    "CronParseError",
    # Enums
    "JobState",
    "TriggerType",
    # Data classes
    "CronExpression",
    "JobConfig",
    "JobExecution",
    "Job",
    "SchedulerStats",
    # Store
    "JobStore",
    "InMemoryJobStore",
    # Scheduler
    "TaskScheduler",
    "SimpleTaskScheduler",
    # Registry
    "SchedulerRegistry",
    # Decorators
    "scheduled",
    "every",
    # Factory functions
    "create_task_scheduler",
    "create_job_config",
    "parse_cron",
    "register_scheduler",
    "get_scheduler",
]
