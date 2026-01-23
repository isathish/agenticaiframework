"""
Enterprise Scheduler Module.

Provides job scheduling, cron-like execution, and task orchestration
for automated background operations.

Example:
    # Schedule recurring tasks
    scheduler = Scheduler()
    
    @scheduler.every(minutes=5)
    async def cleanup_cache():
        await cache.cleanup()
    
    @scheduler.cron("0 0 * * *")  # Daily at midnight
    async def daily_report():
        await generate_report()
    
    await scheduler.start()
"""

from __future__ import annotations

import asyncio
import time
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Union,
)
from datetime import datetime, timedelta
from functools import wraps
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class SchedulerError(Exception):
    """Scheduler operation failed."""
    pass


class JobNotFoundError(SchedulerError):
    """Job not found."""
    pass


class JobStatus(str, Enum):
    """Job execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class TriggerType(str, Enum):
    """Types of job triggers."""
    ONCE = "once"
    INTERVAL = "interval"
    CRON = "cron"
    DELAYED = "delayed"


@dataclass
class JobResult:
    """Result of a job execution."""
    job_id: str
    status: JobStatus
    result: Any = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    
    @property
    def duration(self) -> Optional[float]:
        """Execution duration in seconds."""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None


@dataclass
class JobStats:
    """Statistics for a scheduled job."""
    job_id: str
    name: str
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    total_duration: float = 0.0
    last_run: Optional[float] = None
    next_run: Optional[float] = None
    
    @property
    def success_rate(self) -> float:
        """Success rate percentage."""
        if self.total_runs == 0:
            return 100.0
        return (self.successful_runs / self.total_runs) * 100
    
    @property
    def average_duration(self) -> float:
        """Average execution duration."""
        if self.successful_runs == 0:
            return 0.0
        return self.total_duration / self.successful_runs
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "job_id": self.job_id,
            "name": self.name,
            "total_runs": self.total_runs,
            "successful_runs": self.successful_runs,
            "failed_runs": self.failed_runs,
            "success_rate": self.success_rate,
            "average_duration": self.average_duration,
            "last_run": self.last_run,
            "next_run": self.next_run,
        }


class Trigger(ABC):
    """Abstract trigger for job scheduling."""
    
    @property
    @abstractmethod
    def trigger_type(self) -> TriggerType:
        """Get trigger type."""
        pass
    
    @abstractmethod
    def get_next_run(self, from_time: Optional[float] = None) -> Optional[float]:
        """Get next run timestamp."""
        pass
    
    @abstractmethod
    def should_run(self, current_time: float) -> bool:
        """Check if job should run now."""
        pass


class OnceTrigger(Trigger):
    """Trigger that runs once at a specific time."""
    
    def __init__(self, run_at: float):
        """
        Initialize once trigger.
        
        Args:
            run_at: Unix timestamp to run at
        """
        self.run_at = run_at
        self._executed = False
    
    @property
    def trigger_type(self) -> TriggerType:
        return TriggerType.ONCE
    
    def get_next_run(self, from_time: Optional[float] = None) -> Optional[float]:
        if self._executed:
            return None
        return self.run_at
    
    def should_run(self, current_time: float) -> bool:
        if self._executed:
            return False
        if current_time >= self.run_at:
            self._executed = True
            return True
        return False


class IntervalTrigger(Trigger):
    """Trigger that runs at fixed intervals."""
    
    def __init__(
        self,
        seconds: float = 0,
        minutes: float = 0,
        hours: float = 0,
        days: float = 0,
        start_immediately: bool = False,
    ):
        """
        Initialize interval trigger.
        
        Args:
            seconds: Interval seconds
            minutes: Interval minutes
            hours: Interval hours
            days: Interval days
            start_immediately: Run immediately on start
        """
        self.interval = (
            seconds +
            minutes * 60 +
            hours * 3600 +
            days * 86400
        )
        self.start_immediately = start_immediately
        self._last_run: Optional[float] = None
        self._first_run = True
    
    @property
    def trigger_type(self) -> TriggerType:
        return TriggerType.INTERVAL
    
    def get_next_run(self, from_time: Optional[float] = None) -> Optional[float]:
        from_time = from_time or time.time()
        
        if self._first_run and self.start_immediately:
            return from_time
        
        if self._last_run is None:
            return from_time + self.interval
        
        return self._last_run + self.interval
    
    def should_run(self, current_time: float) -> bool:
        if self._first_run:
            self._first_run = False
            if self.start_immediately:
                self._last_run = current_time
                return True
            self._last_run = current_time
            return False
        
        if self._last_run is None:
            self._last_run = current_time
            return True
        
        if current_time >= self._last_run + self.interval:
            self._last_run = current_time
            return True
        
        return False


class CronTrigger(Trigger):
    """Trigger based on cron expression."""
    
    def __init__(self, expression: str):
        """
        Initialize cron trigger.
        
        Args:
            expression: Cron expression (minute hour day month weekday)
        """
        self.expression = expression
        self._parts = self._parse_expression(expression)
    
    @property
    def trigger_type(self) -> TriggerType:
        return TriggerType.CRON
    
    def _parse_expression(self, expr: str) -> Dict[str, List[int]]:
        """Parse cron expression."""
        parts = expr.strip().split()
        if len(parts) != 5:
            raise ValueError(f"Invalid cron expression: {expr}")
        
        def parse_field(field: str, min_val: int, max_val: int) -> List[int]:
            if field == "*":
                return list(range(min_val, max_val + 1))
            
            if "/" in field:
                base, step = field.split("/")
                step = int(step)
                if base == "*":
                    return list(range(min_val, max_val + 1, step))
                return list(range(int(base), max_val + 1, step))
            
            if "-" in field:
                start, end = field.split("-")
                return list(range(int(start), int(end) + 1))
            
            if "," in field:
                return [int(x) for x in field.split(",")]
            
            return [int(field)]
        
        return {
            "minute": parse_field(parts[0], 0, 59),
            "hour": parse_field(parts[1], 0, 23),
            "day": parse_field(parts[2], 1, 31),
            "month": parse_field(parts[3], 1, 12),
            "weekday": parse_field(parts[4], 0, 6),
        }
    
    def _matches(self, dt: datetime) -> bool:
        """Check if datetime matches cron expression."""
        return (
            dt.minute in self._parts["minute"] and
            dt.hour in self._parts["hour"] and
            dt.day in self._parts["day"] and
            dt.month in self._parts["month"] and
            dt.weekday() in self._parts["weekday"]
        )
    
    def get_next_run(self, from_time: Optional[float] = None) -> Optional[float]:
        from_time = from_time or time.time()
        dt = datetime.fromtimestamp(from_time)
        
        # Round up to next minute
        dt = dt.replace(second=0, microsecond=0)
        dt += timedelta(minutes=1)
        
        # Find next matching time (max 1 year ahead)
        for _ in range(525600):  # Minutes in a year
            if self._matches(dt):
                return dt.timestamp()
            dt += timedelta(minutes=1)
        
        return None
    
    def should_run(self, current_time: float) -> bool:
        dt = datetime.fromtimestamp(current_time)
        return self._matches(dt)


@dataclass
class ScheduledJob:
    """A scheduled job."""
    id: str
    name: str
    func: Callable
    trigger: Trigger
    args: tuple = field(default_factory=tuple)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    max_retries: int = 0
    retry_delay: float = 60.0
    timeout: Optional[float] = None
    on_success: Optional[Callable] = None
    on_failure: Optional[Callable] = None
    
    # Runtime state
    stats: JobStats = field(default_factory=lambda: JobStats("", ""))
    status: JobStatus = JobStatus.PENDING
    current_retries: int = 0
    
    def __post_init__(self):
        self.stats = JobStats(job_id=self.id, name=self.name)


class Scheduler:
    """
    Job scheduler for background task execution.
    """
    
    def __init__(
        self,
        tick_interval: float = 1.0,
        max_concurrent_jobs: int = 10,
    ):
        """
        Initialize scheduler.
        
        Args:
            tick_interval: Scheduler tick interval in seconds
            max_concurrent_jobs: Maximum concurrent job executions
        """
        self.tick_interval = tick_interval
        self.max_concurrent_jobs = max_concurrent_jobs
        
        self._jobs: Dict[str, ScheduledJob] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._semaphore = asyncio.Semaphore(max_concurrent_jobs)
        self._job_counter = 0
        self._lock = asyncio.Lock()
    
    @property
    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self._running
    
    def _generate_job_id(self) -> str:
        """Generate unique job ID."""
        self._job_counter += 1
        return f"job_{self._job_counter}"
    
    def add_job(
        self,
        func: Callable,
        trigger: Trigger,
        name: Optional[str] = None,
        job_id: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """
        Add a job to the scheduler.
        
        Args:
            func: Function to execute
            trigger: Job trigger
            name: Optional job name
            job_id: Optional job ID
            **kwargs: Additional job options
            
        Returns:
            Job ID
        """
        job_id = job_id or self._generate_job_id()
        name = name or getattr(func, "__name__", job_id)
        
        job = ScheduledJob(
            id=job_id,
            name=name,
            func=func,
            trigger=trigger,
            **kwargs,
        )
        
        self._jobs[job_id] = job
        logger.info(f"Added job {job_id}: {name}")
        
        return job_id
    
    def remove_job(self, job_id: str) -> bool:
        """Remove a job."""
        if job_id in self._jobs:
            del self._jobs[job_id]
            logger.info(f"Removed job {job_id}")
            return True
        return False
    
    def pause_job(self, job_id: str) -> bool:
        """Pause a job."""
        if job_id in self._jobs:
            self._jobs[job_id].enabled = False
            self._jobs[job_id].status = JobStatus.PAUSED
            return True
        return False
    
    def resume_job(self, job_id: str) -> bool:
        """Resume a paused job."""
        if job_id in self._jobs:
            self._jobs[job_id].enabled = True
            self._jobs[job_id].status = JobStatus.PENDING
            return True
        return False
    
    def get_job(self, job_id: str) -> Optional[ScheduledJob]:
        """Get job by ID."""
        return self._jobs.get(job_id)
    
    def list_jobs(self) -> List[ScheduledJob]:
        """List all jobs."""
        return list(self._jobs.values())
    
    def get_stats(self) -> Dict[str, JobStats]:
        """Get statistics for all jobs."""
        return {job_id: job.stats for job_id, job in self._jobs.items()}
    
    async def start(self) -> None:
        """Start the scheduler."""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Scheduler started")
    
    async def stop(self, wait: bool = True) -> None:
        """Stop the scheduler."""
        self._running = False
        
        if self._task:
            if wait:
                await self._task
            else:
                self._task.cancel()
        
        logger.info("Scheduler stopped")
    
    async def _run_loop(self) -> None:
        """Main scheduler loop."""
        while self._running:
            try:
                current_time = time.time()
                
                for job in self._jobs.values():
                    if not job.enabled:
                        continue
                    
                    if job.trigger.should_run(current_time):
                        asyncio.create_task(self._execute_job(job))
                
                await asyncio.sleep(self.tick_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
    
    async def _execute_job(self, job: ScheduledJob) -> JobResult:
        """Execute a job."""
        async with self._semaphore:
            job.status = JobStatus.RUNNING
            job.stats.last_run = time.time()
            started_at = time.time()
            
            try:
                if job.timeout:
                    if asyncio.iscoroutinefunction(job.func):
                        result = await asyncio.wait_for(
                            job.func(*job.args, **job.kwargs),
                            timeout=job.timeout,
                        )
                    else:
                        result = job.func(*job.args, **job.kwargs)
                else:
                    if asyncio.iscoroutinefunction(job.func):
                        result = await job.func(*job.args, **job.kwargs)
                    else:
                        result = job.func(*job.args, **job.kwargs)
                
                completed_at = time.time()
                
                job.status = JobStatus.COMPLETED
                job.stats.total_runs += 1
                job.stats.successful_runs += 1
                job.stats.total_duration += completed_at - started_at
                job.stats.next_run = job.trigger.get_next_run()
                job.current_retries = 0
                
                if job.on_success:
                    try:
                        if asyncio.iscoroutinefunction(job.on_success):
                            await job.on_success(result)
                        else:
                            job.on_success(result)
                    except Exception as e:
                        logger.error(f"Job {job.id} on_success callback error: {e}")
                
                return JobResult(
                    job_id=job.id,
                    status=JobStatus.COMPLETED,
                    result=result,
                    started_at=started_at,
                    completed_at=completed_at,
                )
                
            except Exception as e:
                completed_at = time.time()
                
                job.stats.total_runs += 1
                job.stats.failed_runs += 1
                
                # Retry logic
                if job.current_retries < job.max_retries:
                    job.current_retries += 1
                    job.status = JobStatus.PENDING
                    logger.warning(
                        f"Job {job.id} failed, retry {job.current_retries}/{job.max_retries}"
                    )
                    
                    # Schedule retry
                    await asyncio.sleep(job.retry_delay)
                    asyncio.create_task(self._execute_job(job))
                else:
                    job.status = JobStatus.FAILED
                    job.stats.next_run = job.trigger.get_next_run()
                    
                    if job.on_failure:
                        try:
                            if asyncio.iscoroutinefunction(job.on_failure):
                                await job.on_failure(e)
                            else:
                                job.on_failure(e)
                        except Exception as cb_error:
                            logger.error(f"Job {job.id} on_failure callback error: {cb_error}")
                
                logger.error(f"Job {job.id} failed: {e}")
                
                return JobResult(
                    job_id=job.id,
                    status=JobStatus.FAILED,
                    error=str(e),
                    started_at=started_at,
                    completed_at=completed_at,
                )
    
    async def run_job_now(self, job_id: str) -> JobResult:
        """Run a job immediately."""
        job = self._jobs.get(job_id)
        if not job:
            raise JobNotFoundError(f"Job {job_id} not found")
        
        return await self._execute_job(job)
    
    # Decorator methods
    def every(
        self,
        seconds: float = 0,
        minutes: float = 0,
        hours: float = 0,
        days: float = 0,
        start_immediately: bool = False,
        **kwargs: Any,
    ) -> Callable:
        """
        Decorator for interval-based scheduling.
        
        Example:
            @scheduler.every(minutes=5)
            async def task():
                ...
        """
        def decorator(func: Callable) -> Callable:
            trigger = IntervalTrigger(
                seconds=seconds,
                minutes=minutes,
                hours=hours,
                days=days,
                start_immediately=start_immediately,
            )
            self.add_job(func, trigger, **kwargs)
            return func
        
        return decorator
    
    def cron(self, expression: str, **kwargs: Any) -> Callable:
        """
        Decorator for cron-based scheduling.
        
        Example:
            @scheduler.cron("0 0 * * *")  # Daily at midnight
            async def daily_task():
                ...
        """
        def decorator(func: Callable) -> Callable:
            trigger = CronTrigger(expression)
            self.add_job(func, trigger, **kwargs)
            return func
        
        return decorator
    
    def once(self, run_at: Union[float, datetime], **kwargs: Any) -> Callable:
        """
        Decorator for one-time execution.
        
        Example:
            @scheduler.once(datetime(2024, 12, 31, 23, 59))
            async def new_year_task():
                ...
        """
        def decorator(func: Callable) -> Callable:
            timestamp = run_at.timestamp() if isinstance(run_at, datetime) else run_at
            trigger = OnceTrigger(timestamp)
            self.add_job(func, trigger, **kwargs)
            return func
        
        return decorator
    
    async def __aenter__(self) -> 'Scheduler':
        await self.start()
        return self
    
    async def __aexit__(self, *args) -> None:
        await self.stop()


def schedule(
    cron: Optional[str] = None,
    interval: Optional[float] = None,
    at: Optional[Union[float, datetime]] = None,
) -> Callable:
    """
    Standalone decorator for scheduling (requires global scheduler).
    
    Example:
        @schedule(cron="0 */6 * * *")
        async def every_6_hours():
            ...
    """
    def decorator(func: Callable) -> Callable:
        # Store scheduling info on function
        if cron:
            func._schedule_trigger = CronTrigger(cron)
        elif interval:
            func._schedule_trigger = IntervalTrigger(seconds=interval)
        elif at:
            timestamp = at.timestamp() if isinstance(at, datetime) else at
            func._schedule_trigger = OnceTrigger(timestamp)
        else:
            raise ValueError("Must specify cron, interval, or at")
        
        return func
    
    return decorator


__all__ = [
    # Exceptions
    "SchedulerError",
    "JobNotFoundError",
    # Enums
    "JobStatus",
    "TriggerType",
    # Data classes
    "JobResult",
    "JobStats",
    "ScheduledJob",
    # Triggers
    "Trigger",
    "OnceTrigger",
    "IntervalTrigger",
    "CronTrigger",
    # Main class
    "Scheduler",
    # Decorator
    "schedule",
]
