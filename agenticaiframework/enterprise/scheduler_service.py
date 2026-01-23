"""
Enterprise Scheduler Service Module.

Job scheduling, cron expressions, recurring tasks,
and task automation.

Example:
    # Create scheduler
    scheduler = create_scheduler()
    
    # Schedule recurring job
    job = scheduler.schedule(
        name="daily_report",
        cron="0 9 * * *",  # Every day at 9 AM
        handler=generate_report,
    )
    
    # Schedule one-time job
    scheduler.run_once(
        name="cleanup",
        run_at=datetime.now() + timedelta(hours=1),
        handler=cleanup_files,
    )
    
    # Start scheduler
    await scheduler.start()
"""

from __future__ import annotations

import asyncio
import hashlib
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


class SchedulerError(Exception):
    """Scheduler error."""
    pass


class JobStatus(str, Enum):
    """Job status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class JobType(str, Enum):
    """Job type."""
    ONE_TIME = "one_time"
    RECURRING = "recurring"
    INTERVAL = "interval"
    CRON = "cron"


class JobPriority(str, Enum):
    """Job priority."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class CronExpression:
    """Parsed cron expression."""
    minute: str = "*"
    hour: str = "*"
    day_of_month: str = "*"
    month: str = "*"
    day_of_week: str = "*"
    raw: str = "* * * * *"
    
    @classmethod
    def parse(cls, expression: str) -> "CronExpression":
        """Parse cron expression."""
        parts = expression.strip().split()
        
        if len(parts) == 5:
            return cls(
                minute=parts[0],
                hour=parts[1],
                day_of_month=parts[2],
                month=parts[3],
                day_of_week=parts[4],
                raw=expression,
            )
        elif len(parts) == 6:
            # With seconds
            return cls(
                minute=parts[1],
                hour=parts[2],
                day_of_month=parts[3],
                month=parts[4],
                day_of_week=parts[5],
                raw=expression,
            )
        else:
            raise ValueError(f"Invalid cron expression: {expression}")
    
    def _match_field(self, field: str, value: int, max_val: int) -> bool:
        """Check if value matches field."""
        if field == "*":
            return True
        
        # Handle ranges
        if "-" in field:
            start, end = map(int, field.split("-"))
            return start <= value <= end
        
        # Handle steps
        if "/" in field:
            base, step = field.split("/")
            step = int(step)
            if base == "*":
                return value % step == 0
            return (value - int(base)) % step == 0
        
        # Handle lists
        if "," in field:
            values = [int(v) for v in field.split(",")]
            return value in values
        
        # Direct match
        try:
            return value == int(field)
        except ValueError:
            return False
    
    def matches(self, dt: datetime) -> bool:
        """Check if datetime matches expression."""
        return (
            self._match_field(self.minute, dt.minute, 59) and
            self._match_field(self.hour, dt.hour, 23) and
            self._match_field(self.day_of_month, dt.day, 31) and
            self._match_field(self.month, dt.month, 12) and
            self._match_field(self.day_of_week, dt.weekday(), 6)
        )
    
    def next_run(self, from_dt: Optional[datetime] = None) -> datetime:
        """Get next run time."""
        if from_dt is None:
            from_dt = datetime.utcnow()
        
        # Start from next minute
        dt = from_dt.replace(second=0, microsecond=0) + timedelta(minutes=1)
        
        # Search for next matching time
        for _ in range(525600):  # Max 1 year of minutes
            if self.matches(dt):
                return dt
            dt += timedelta(minutes=1)
        
        raise ValueError("Could not find next run time within 1 year")


@dataclass
class Job:
    """Scheduled job."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    job_type: JobType = JobType.ONE_TIME
    status: JobStatus = JobStatus.PENDING
    priority: JobPriority = JobPriority.NORMAL
    cron: Optional[str] = None
    interval: Optional[int] = None  # seconds
    run_at: Optional[datetime] = None
    handler_name: str = ""
    args: Tuple = ()
    kwargs: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    next_run: Optional[datetime] = None
    last_run: Optional[datetime] = None
    run_count: int = 0
    max_runs: Optional[int] = None
    timeout: int = 300  # seconds
    retry_count: int = 0
    max_retries: int = 3
    retry_delay: int = 60  # seconds
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class JobExecution:
    """Job execution record."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    job_id: str = ""
    job_name: str = ""
    status: JobStatus = JobStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration: float = 0.0
    result: Any = None
    error: Optional[str] = None
    retry_count: int = 0


@dataclass
class SchedulerStats:
    """Scheduler statistics."""
    total_jobs: int = 0
    active_jobs: int = 0
    paused_jobs: int = 0
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    running_tasks: int = 0


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
    async def delete(self, job_id: str) -> bool:
        pass
    
    @abstractmethod
    async def list_pending(self) -> List[Job]:
        pass
    
    @abstractmethod
    async def list_all(self) -> List[Job]:
        pass


class InMemoryJobStore(JobStore):
    """In-memory job store."""
    
    def __init__(self):
        self._jobs: Dict[str, Job] = {}
    
    async def save(self, job: Job) -> None:
        self._jobs[job.id] = job
    
    async def get(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)
    
    async def delete(self, job_id: str) -> bool:
        if job_id in self._jobs:
            del self._jobs[job_id]
            return True
        return False
    
    async def list_pending(self) -> List[Job]:
        now = datetime.utcnow()
        pending = []
        
        for job in self._jobs.values():
            if job.status != JobStatus.PENDING and job.status != JobStatus.COMPLETED:
                continue
            
            if job.next_run and job.next_run <= now:
                pending.append(job)
        
        return sorted(pending, key=lambda j: (
            JobPriority.CRITICAL if j.priority == JobPriority.CRITICAL else
            JobPriority.HIGH if j.priority == JobPriority.HIGH else
            JobPriority.NORMAL if j.priority == JobPriority.NORMAL else
            JobPriority.LOW,
            j.next_run or datetime.max
        ))
    
    async def list_all(self) -> List[Job]:
        return list(self._jobs.values())


# Execution store
class ExecutionStore(ABC):
    """Execution storage."""
    
    @abstractmethod
    async def save(self, execution: JobExecution) -> None:
        pass
    
    @abstractmethod
    async def get(self, execution_id: str) -> Optional[JobExecution]:
        pass
    
    @abstractmethod
    async def list_by_job(self, job_id: str, limit: int = 100) -> List[JobExecution]:
        pass


class InMemoryExecutionStore(ExecutionStore):
    """In-memory execution store."""
    
    def __init__(self, max_history: int = 1000):
        self._executions: Dict[str, JobExecution] = {}
        self._by_job: Dict[str, List[str]] = {}
        self._max_history = max_history
    
    async def save(self, execution: JobExecution) -> None:
        self._executions[execution.id] = execution
        
        if execution.job_id not in self._by_job:
            self._by_job[execution.job_id] = []
        
        self._by_job[execution.job_id].append(execution.id)
        
        # Trim history
        if len(self._executions) > self._max_history:
            oldest = list(self._executions.keys())[0]
            del self._executions[oldest]
    
    async def get(self, execution_id: str) -> Optional[JobExecution]:
        return self._executions.get(execution_id)
    
    async def list_by_job(self, job_id: str, limit: int = 100) -> List[JobExecution]:
        ids = self._by_job.get(job_id, [])[-limit:]
        return [self._executions[eid] for eid in ids if eid in self._executions]


# Handler type
JobHandler = Callable[..., Coroutine[Any, Any, Any]]


# Scheduler
class Scheduler:
    """Job scheduler."""
    
    def __init__(
        self,
        job_store: Optional[JobStore] = None,
        execution_store: Optional[ExecutionStore] = None,
        max_concurrent: int = 10,
    ):
        self._job_store = job_store or InMemoryJobStore()
        self._execution_store = execution_store or InMemoryExecutionStore()
        self._handlers: Dict[str, JobHandler] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._stats = SchedulerStats()
        self._running_jobs: Set[str] = set()
    
    def register_handler(self, name: str, handler: JobHandler) -> None:
        """Register job handler."""
        self._handlers[name] = handler
        logger.info(f"Handler registered: {name}")
    
    async def schedule(
        self,
        name: str,
        handler: Optional[JobHandler] = None,
        cron: Optional[str] = None,
        interval: Optional[int] = None,
        run_at: Optional[datetime] = None,
        args: Tuple = (),
        kwargs: Optional[Dict[str, Any]] = None,
        priority: JobPriority = JobPriority.NORMAL,
        max_runs: Optional[int] = None,
        **extra,
    ) -> Job:
        """Schedule a job."""
        handler_name = name
        
        if handler:
            self._handlers[name] = handler
        
        if not self._handlers.get(handler_name):
            raise SchedulerError(f"Handler not found: {handler_name}")
        
        # Determine job type and next run
        if cron:
            job_type = JobType.CRON
            expr = CronExpression.parse(cron)
            next_run = expr.next_run()
        elif interval:
            job_type = JobType.INTERVAL
            next_run = datetime.utcnow() + timedelta(seconds=interval)
        elif run_at:
            job_type = JobType.ONE_TIME
            next_run = run_at
        else:
            job_type = JobType.ONE_TIME
            next_run = datetime.utcnow()
        
        job = Job(
            name=name,
            job_type=job_type,
            status=JobStatus.PENDING,
            priority=priority,
            cron=cron,
            interval=interval,
            run_at=run_at,
            handler_name=handler_name,
            args=args,
            kwargs=kwargs or {},
            next_run=next_run,
            max_runs=max_runs,
            **extra,
        )
        
        await self._job_store.save(job)
        self._stats.total_jobs += 1
        self._stats.active_jobs += 1
        
        logger.info(f"Job scheduled: {name} (type={job_type.value}, next_run={next_run})")
        
        return job
    
    async def run_once(
        self,
        name: str,
        handler: Optional[JobHandler] = None,
        run_at: Optional[datetime] = None,
        delay: int = 0,
        args: Tuple = (),
        kwargs: Optional[Dict[str, Any]] = None,
        **extra,
    ) -> Job:
        """Schedule one-time job."""
        if not run_at:
            run_at = datetime.utcnow() + timedelta(seconds=delay)
        
        return await self.schedule(
            name=name,
            handler=handler,
            run_at=run_at,
            args=args,
            kwargs=kwargs,
            max_runs=1,
            **extra,
        )
    
    async def cancel(self, job_id: str) -> bool:
        """Cancel job."""
        job = await self._job_store.get(job_id)
        if not job:
            return False
        
        job.status = JobStatus.CANCELLED
        job.updated_at = datetime.utcnow()
        await self._job_store.save(job)
        
        self._stats.active_jobs = max(0, self._stats.active_jobs - 1)
        
        logger.info(f"Job cancelled: {job.name}")
        return True
    
    async def pause(self, job_id: str) -> bool:
        """Pause job."""
        job = await self._job_store.get(job_id)
        if not job:
            return False
        
        job.status = JobStatus.PAUSED
        job.updated_at = datetime.utcnow()
        await self._job_store.save(job)
        
        self._stats.active_jobs = max(0, self._stats.active_jobs - 1)
        self._stats.paused_jobs += 1
        
        logger.info(f"Job paused: {job.name}")
        return True
    
    async def resume(self, job_id: str) -> bool:
        """Resume job."""
        job = await self._job_store.get(job_id)
        if not job or job.status != JobStatus.PAUSED:
            return False
        
        job.status = JobStatus.PENDING
        job.updated_at = datetime.utcnow()
        await self._job_store.save(job)
        
        self._stats.active_jobs += 1
        self._stats.paused_jobs = max(0, self._stats.paused_jobs - 1)
        
        logger.info(f"Job resumed: {job.name}")
        return True
    
    async def _execute_job(self, job: Job) -> JobExecution:
        """Execute job."""
        execution = JobExecution(
            job_id=job.id,
            job_name=job.name,
            status=JobStatus.RUNNING,
            started_at=datetime.utcnow(),
        )
        
        handler = self._handlers.get(job.handler_name)
        if not handler:
            execution.status = JobStatus.FAILED
            execution.error = f"Handler not found: {job.handler_name}"
            execution.completed_at = datetime.utcnow()
            await self._execution_store.save(execution)
            return execution
        
        try:
            async with asyncio.timeout(job.timeout):
                result = await handler(*job.args, **job.kwargs)
                execution.result = result
                execution.status = JobStatus.COMPLETED
                self._stats.successful_executions += 1
        except asyncio.TimeoutError:
            execution.status = JobStatus.FAILED
            execution.error = "Timeout"
            self._stats.failed_executions += 1
        except Exception as e:
            execution.status = JobStatus.FAILED
            execution.error = str(e)
            self._stats.failed_executions += 1
            logger.error(f"Job execution failed: {job.name} - {e}")
        finally:
            execution.completed_at = datetime.utcnow()
            execution.duration = (execution.completed_at - execution.started_at).total_seconds()
            self._stats.total_executions += 1
        
        await self._execution_store.save(execution)
        return execution
    
    async def _update_next_run(self, job: Job) -> None:
        """Update next run time."""
        job.run_count += 1
        job.last_run = datetime.utcnow()
        
        # Check max runs
        if job.max_runs and job.run_count >= job.max_runs:
            job.status = JobStatus.COMPLETED
            job.next_run = None
            self._stats.active_jobs = max(0, self._stats.active_jobs - 1)
        elif job.job_type == JobType.CRON and job.cron:
            expr = CronExpression.parse(job.cron)
            job.next_run = expr.next_run()
            job.status = JobStatus.PENDING
        elif job.job_type == JobType.INTERVAL and job.interval:
            job.next_run = datetime.utcnow() + timedelta(seconds=job.interval)
            job.status = JobStatus.PENDING
        else:
            job.status = JobStatus.COMPLETED
            job.next_run = None
            self._stats.active_jobs = max(0, self._stats.active_jobs - 1)
        
        job.updated_at = datetime.utcnow()
        await self._job_store.save(job)
    
    async def _process_job(self, job: Job) -> None:
        """Process a single job."""
        async with self._semaphore:
            if job.id in self._running_jobs:
                return
            
            self._running_jobs.add(job.id)
            self._stats.running_tasks += 1
            
            try:
                job.status = JobStatus.RUNNING
                await self._job_store.save(job)
                
                execution = await self._execute_job(job)
                
                # Handle retries
                if execution.status == JobStatus.FAILED and job.retry_count < job.max_retries:
                    job.retry_count += 1
                    job.next_run = datetime.utcnow() + timedelta(seconds=job.retry_delay)
                    job.status = JobStatus.PENDING
                    await self._job_store.save(job)
                    logger.info(f"Job retry scheduled: {job.name} (attempt {job.retry_count})")
                else:
                    await self._update_next_run(job)
            finally:
                self._running_jobs.discard(job.id)
                self._stats.running_tasks = max(0, self._stats.running_tasks - 1)
    
    async def _run_loop(self) -> None:
        """Main scheduler loop."""
        while self._running:
            try:
                pending = await self._job_store.list_pending()
                
                for job in pending:
                    if not self._running:
                        break
                    
                    asyncio.create_task(self._process_job(job))
                
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
                await asyncio.sleep(5)
    
    async def start(self) -> None:
        """Start scheduler."""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Scheduler started")
    
    async def stop(self) -> None:
        """Stop scheduler."""
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        logger.info("Scheduler stopped")
    
    async def list_jobs(self) -> List[Job]:
        """List all jobs."""
        return await self._job_store.list_all()
    
    async def get_job(self, job_id: str) -> Optional[Job]:
        """Get job."""
        return await self._job_store.get(job_id)
    
    async def get_executions(self, job_id: str, limit: int = 100) -> List[JobExecution]:
        """Get job executions."""
        return await self._execution_store.list_by_job(job_id, limit)
    
    def get_stats(self) -> SchedulerStats:
        """Get statistics."""
        return self._stats
    
    @property
    def is_running(self) -> bool:
        """Check if running."""
        return self._running


# Factory functions
def create_scheduler(max_concurrent: int = 10) -> Scheduler:
    """Create scheduler."""
    return Scheduler(max_concurrent=max_concurrent)


def create_job(
    name: str,
    cron: Optional[str] = None,
    interval: Optional[int] = None,
    **kwargs,
) -> Job:
    """Create job."""
    job_type = JobType.CRON if cron else JobType.INTERVAL if interval else JobType.ONE_TIME
    return Job(name=name, job_type=job_type, cron=cron, interval=interval, **kwargs)


def parse_cron(expression: str) -> CronExpression:
    """Parse cron expression."""
    return CronExpression.parse(expression)


__all__ = [
    # Exceptions
    "SchedulerError",
    # Enums
    "JobStatus",
    "JobType",
    "JobPriority",
    # Data classes
    "CronExpression",
    "Job",
    "JobExecution",
    "SchedulerStats",
    # Stores
    "JobStore",
    "InMemoryJobStore",
    "ExecutionStore",
    "InMemoryExecutionStore",
    # Scheduler
    "Scheduler",
    # Factory functions
    "create_scheduler",
    "create_job",
    "parse_cron",
]
