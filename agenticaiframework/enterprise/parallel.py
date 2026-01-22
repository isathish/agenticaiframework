"""
Enterprise Parallel Execution - Concurrent step execution with dependencies.

Provides parallel execution engine for workflow steps
with dependency resolution and resource management.

Features:
- DAG-based execution
- Dependency resolution
- Resource pools
- Concurrency limits
- Progress tracking
"""

import asyncio
import logging
import time
import threading
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any, Awaitable, Callable, Dict, Generic, List, 
    Optional, Set, Tuple, TypeVar, Union,
)
import uuid

logger = logging.getLogger(__name__)


# =============================================================================
# Types
# =============================================================================

T = TypeVar("T")
R = TypeVar("R")


class TaskStatus(Enum):
    """Status of a task."""
    PENDING = "pending"
    WAITING = "waiting"  # Waiting for dependencies
    READY = "ready"  # Dependencies satisfied
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class TaskPriority(Enum):
    """Priority of a task."""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


# =============================================================================
# Task Definition
# =============================================================================

@dataclass
class ParallelTask(Generic[T]):
    """A task for parallel execution."""
    id: str
    name: str
    
    # Execution
    func: Callable[..., Awaitable[T]]
    args: tuple = field(default_factory=tuple)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    
    # Dependencies
    depends_on: List[str] = field(default_factory=list)
    
    # Configuration
    priority: TaskPriority = TaskPriority.NORMAL
    timeout_seconds: Optional[float] = None
    retry_count: int = 0
    retry_delay: float = 1.0
    
    # Resource requirements
    resource_pool: Optional[str] = None
    resource_count: int = 1
    
    # State
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[T] = None
    error: Optional[Exception] = None
    
    # Timing
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def duration(self) -> Optional[float]:
        """Get task duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    @property
    def is_terminal(self) -> bool:
        """Check if task is in terminal state."""
        return self.status in (
            TaskStatus.COMPLETED, 
            TaskStatus.FAILED, 
            TaskStatus.CANCELLED,
            TaskStatus.SKIPPED,
        )


@dataclass
class TaskResult(Generic[T]):
    """Result of a task execution."""
    task_id: str
    task_name: str
    status: TaskStatus
    
    result: Optional[T] = None
    error: Optional[str] = None
    
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    
    retry_attempts: int = 0


# =============================================================================
# Resource Pool
# =============================================================================

class ResourcePool:
    """
    Pool of limited resources for task execution.
    
    Usage:
        >>> pool = ResourcePool("llm", capacity=5)
        >>> 
        >>> async with pool.acquire(count=1) as resources:
        ...     # Use resources
        ...     pass
    """
    
    def __init__(self, name: str, capacity: int):
        self.name = name
        self.capacity = capacity
        
        self._semaphore = asyncio.Semaphore(capacity)
        self._in_use = 0
        self._lock = asyncio.Lock()
    
    @property
    def available(self) -> int:
        """Get available resource count."""
        return self.capacity - self._in_use
    
    async def acquire(self, count: int = 1) -> "ResourceContext":
        """Acquire resources from the pool."""
        return ResourceContext(self, count)
    
    async def _acquire(self, count: int):
        """Internal acquire."""
        for _ in range(count):
            await self._semaphore.acquire()
        
        async with self._lock:
            self._in_use += count
    
    async def _release(self, count: int):
        """Internal release."""
        for _ in range(count):
            self._semaphore.release()
        
        async with self._lock:
            self._in_use -= count


class ResourceContext:
    """Context manager for resource acquisition."""
    
    def __init__(self, pool: ResourcePool, count: int):
        self.pool = pool
        self.count = count
    
    async def __aenter__(self):
        await self.pool._acquire(self.count)
        return self
    
    async def __aexit__(self, *args):
        await self.pool._release(self.count)


# =============================================================================
# DAG Executor
# =============================================================================

class DAGExecutor:
    """
    Executes tasks in parallel based on dependencies.
    
    Usage:
        >>> executor = DAGExecutor(max_concurrency=10)
        >>> 
        >>> # Add tasks
        >>> executor.add_task(ParallelTask(
        ...     id="task-1",
        ...     name="First Task",
        ...     func=my_async_func,
        ... ))
        >>> 
        >>> executor.add_task(ParallelTask(
        ...     id="task-2",
        ...     name="Second Task",
        ...     func=my_other_func,
        ...     depends_on=["task-1"],
        ... ))
        >>> 
        >>> # Execute
        >>> results = await executor.execute()
    """
    
    def __init__(
        self,
        max_concurrency: int = 10,
        resource_pools: Dict[str, ResourcePool] = None,
        on_task_complete: Callable[[ParallelTask], None] = None,
        on_task_error: Callable[[ParallelTask, Exception], None] = None,
    ):
        self.max_concurrency = max_concurrency
        self.resource_pools = resource_pools or {}
        self.on_task_complete = on_task_complete
        self.on_task_error = on_task_error
        
        self._tasks: Dict[str, ParallelTask] = {}
        self._results: Dict[str, TaskResult] = {}
        
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._lock = asyncio.Lock()
    
    def add_task(self, task: ParallelTask) -> "DAGExecutor":
        """Add a task to the executor."""
        self._tasks[task.id] = task
        return self
    
    def add_tasks(self, tasks: List[ParallelTask]) -> "DAGExecutor":
        """Add multiple tasks."""
        for task in tasks:
            self.add_task(task)
        return self
    
    def add_resource_pool(self, name: str, capacity: int) -> "DAGExecutor":
        """Add a resource pool."""
        self.resource_pools[name] = ResourcePool(name, capacity)
        return self
    
    def get_execution_order(self) -> List[List[str]]:
        """Get the execution order (levels of parallelizable tasks)."""
        levels = []
        remaining = set(self._tasks.keys())
        completed = set()
        
        while remaining:
            # Find tasks with all dependencies satisfied
            ready = []
            for task_id in remaining:
                task = self._tasks[task_id]
                if all(dep in completed for dep in task.depends_on):
                    ready.append(task_id)
            
            if not ready:
                # Circular dependency
                raise ValueError(f"Circular dependency detected: {remaining}")
            
            levels.append(ready)
            completed.update(ready)
            remaining -= set(ready)
        
        return levels
    
    def validate(self) -> List[str]:
        """Validate the DAG. Returns list of errors."""
        errors = []
        
        # Check for missing dependencies
        for task in self._tasks.values():
            for dep in task.depends_on:
                if dep not in self._tasks:
                    errors.append(f"Task {task.id} depends on unknown task {dep}")
        
        # Check for circular dependencies
        try:
            self.get_execution_order()
        except ValueError as e:
            errors.append(str(e))
        
        return errors
    
    async def execute(
        self,
        fail_fast: bool = False,
        timeout_seconds: float = None,
    ) -> Dict[str, TaskResult]:
        """Execute all tasks."""
        errors = self.validate()
        if errors:
            raise ValueError(f"Invalid DAG: {errors}")
        
        self._semaphore = asyncio.Semaphore(self.max_concurrency)
        self._results = {}
        
        # Reset task states
        for task in self._tasks.values():
            task.status = TaskStatus.PENDING
            task.result = None
            task.error = None
        
        # Get execution order
        levels = self.get_execution_order()
        
        try:
            if timeout_seconds:
                await asyncio.wait_for(
                    self._execute_levels(levels, fail_fast),
                    timeout=timeout_seconds,
                )
            else:
                await self._execute_levels(levels, fail_fast)
        except asyncio.TimeoutError:
            # Mark remaining tasks as cancelled
            for task in self._tasks.values():
                if not task.is_terminal:
                    task.status = TaskStatus.CANCELLED
        
        return self._results
    
    async def _execute_levels(self, levels: List[List[str]], fail_fast: bool):
        """Execute tasks level by level."""
        for level in levels:
            # Execute all tasks in this level concurrently
            tasks = [
                self._execute_task(self._tasks[task_id], fail_fast)
                for task_id in level
            ]
            
            await asyncio.gather(*tasks, return_exceptions=not fail_fast)
            
            # Check for failures if fail_fast
            if fail_fast:
                for task_id in level:
                    if self._tasks[task_id].status == TaskStatus.FAILED:
                        raise RuntimeError(f"Task {task_id} failed")
    
    async def _execute_task(self, task: ParallelTask, fail_fast: bool):
        """Execute a single task."""
        # Check dependencies
        for dep_id in task.depends_on:
            dep_task = self._tasks[dep_id]
            if dep_task.status == TaskStatus.FAILED:
                task.status = TaskStatus.SKIPPED
                self._results[task.id] = TaskResult(
                    task_id=task.id,
                    task_name=task.name,
                    status=TaskStatus.SKIPPED,
                    error=f"Dependency {dep_id} failed",
                )
                return
        
        # Acquire semaphore
        async with self._semaphore:
            # Acquire resource pool if needed
            if task.resource_pool and task.resource_pool in self.resource_pools:
                pool = self.resource_pools[task.resource_pool]
                async with pool.acquire(task.resource_count):
                    await self._run_task(task)
            else:
                await self._run_task(task)
    
    async def _run_task(self, task: ParallelTask):
        """Run the task with retries."""
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        
        attempt = 0
        last_error = None
        
        while attempt <= task.retry_count:
            try:
                # Execute with timeout if specified
                if task.timeout_seconds:
                    result = await asyncio.wait_for(
                        task.func(*task.args, **task.kwargs),
                        timeout=task.timeout_seconds,
                    )
                else:
                    result = await task.func(*task.args, **task.kwargs)
                
                task.status = TaskStatus.COMPLETED
                task.result = result
                task.completed_at = datetime.now()
                
                self._results[task.id] = TaskResult(
                    task_id=task.id,
                    task_name=task.name,
                    status=TaskStatus.COMPLETED,
                    result=result,
                    started_at=task.started_at,
                    completed_at=task.completed_at,
                    duration_seconds=task.duration,
                    retry_attempts=attempt,
                )
                
                if self.on_task_complete:
                    self.on_task_complete(task)
                
                return
                
            except Exception as e:
                last_error = e
                attempt += 1
                
                if attempt <= task.retry_count:
                    logger.warning(f"Task {task.id} failed, retrying ({attempt}/{task.retry_count})")
                    await asyncio.sleep(task.retry_delay * attempt)
        
        # All retries failed
        task.status = TaskStatus.FAILED
        task.error = last_error
        task.completed_at = datetime.now()
        
        self._results[task.id] = TaskResult(
            task_id=task.id,
            task_name=task.name,
            status=TaskStatus.FAILED,
            error=str(last_error),
            started_at=task.started_at,
            completed_at=task.completed_at,
            duration_seconds=task.duration,
            retry_attempts=task.retry_count,
        )
        
        if self.on_task_error:
            self.on_task_error(task, last_error)
        
        logger.error(f"Task {task.id} failed after {task.retry_count + 1} attempts: {last_error}")


# =============================================================================
# Parallel Map
# =============================================================================

async def parallel_map(
    func: Callable[[T], Awaitable[R]],
    items: List[T],
    max_concurrency: int = 10,
    return_exceptions: bool = False,
) -> List[R]:
    """
    Execute a function on multiple items in parallel.
    
    Usage:
        >>> async def process(item):
        ...     return item * 2
        >>> 
        >>> results = await parallel_map(process, [1, 2, 3, 4, 5])
    """
    semaphore = asyncio.Semaphore(max_concurrency)
    
    async def bounded_call(item: T) -> R:
        async with semaphore:
            return await func(item)
    
    tasks = [bounded_call(item) for item in items]
    return await asyncio.gather(*tasks, return_exceptions=return_exceptions)


async def parallel_batch(
    func: Callable[[List[T]], Awaitable[List[R]]],
    items: List[T],
    batch_size: int = 10,
    max_concurrency: int = 5,
) -> List[R]:
    """
    Execute a function on batches of items in parallel.
    
    Usage:
        >>> async def process_batch(items):
        ...     return [item * 2 for item in items]
        >>> 
        >>> results = await parallel_batch(process_batch, range(100), batch_size=10)
    """
    # Create batches
    batches = [items[i:i + batch_size] for i in range(0, len(items), batch_size)]
    
    # Process batches in parallel
    batch_results = await parallel_map(func, batches, max_concurrency)
    
    # Flatten results
    return [item for batch in batch_results for item in batch]


# =============================================================================
# Parallel Step Decorator
# =============================================================================

def parallel_step(
    depends_on: List[str] = None,
    timeout: float = None,
    retries: int = 0,
    priority: TaskPriority = TaskPriority.NORMAL,
):
    """
    Decorator to mark a function as a parallel step.
    
    Usage:
        >>> @parallel_step(depends_on=["step_1"])
        ... async def step_2(context):
        ...     return "result"
    """
    def decorator(func: Callable) -> Callable:
        func._parallel_step = True
        func._depends_on = depends_on or []
        func._timeout = timeout
        func._retries = retries
        func._priority = priority
        
        return func
    
    return decorator


def collect_parallel_steps(obj: Any) -> List[ParallelTask]:
    """Collect parallel steps from an object's methods."""
    tasks = []
    
    for name in dir(obj):
        if name.startswith("_"):
            continue
        
        method = getattr(obj, name)
        
        if callable(method) and getattr(method, "_parallel_step", False):
            task = ParallelTask(
                id=name,
                name=name,
                func=method,
                depends_on=method._depends_on,
                timeout_seconds=method._timeout,
                retry_count=method._retries,
                priority=method._priority,
            )
            tasks.append(task)
    
    return tasks


# =============================================================================
# Progress Tracker
# =============================================================================

@dataclass
class ExecutionProgress:
    """Progress of parallel execution."""
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    running_tasks: int = 0
    pending_tasks: int = 0
    
    started_at: Optional[datetime] = None
    estimated_completion: Optional[datetime] = None
    
    @property
    def progress_percent(self) -> float:
        if self.total_tasks == 0:
            return 0.0
        return (self.completed_tasks / self.total_tasks) * 100
    
    @property
    def is_complete(self) -> bool:
        return self.completed_tasks + self.failed_tasks == self.total_tasks


class ProgressTracker:
    """Tracks progress of parallel execution."""
    
    def __init__(self, executor: DAGExecutor):
        self.executor = executor
        self._callbacks: List[Callable[[ExecutionProgress], None]] = []
    
    def on_progress(self, callback: Callable[[ExecutionProgress], None]):
        """Register a progress callback."""
        self._callbacks.append(callback)
    
    def get_progress(self) -> ExecutionProgress:
        """Get current progress."""
        tasks = list(self.executor._tasks.values())
        
        return ExecutionProgress(
            total_tasks=len(tasks),
            completed_tasks=sum(1 for t in tasks if t.status == TaskStatus.COMPLETED),
            failed_tasks=sum(1 for t in tasks if t.status == TaskStatus.FAILED),
            running_tasks=sum(1 for t in tasks if t.status == TaskStatus.RUNNING),
            pending_tasks=sum(1 for t in tasks if t.status in (TaskStatus.PENDING, TaskStatus.WAITING, TaskStatus.READY)),
        )
    
    def _notify(self):
        """Notify callbacks of progress."""
        progress = self.get_progress()
        for callback in self._callbacks:
            try:
                callback(progress)
            except Exception as e:
                logger.error(f"Progress callback failed: {e}")


# =============================================================================
# Helper Functions
# =============================================================================

def create_dag() -> DAGExecutor:
    """Create a new DAG executor."""
    return DAGExecutor()


def task(
    id: str,
    func: Callable,
    depends_on: List[str] = None,
    **kwargs,
) -> ParallelTask:
    """Create a parallel task."""
    return ParallelTask(
        id=id,
        name=kwargs.get("name", id),
        func=func,
        depends_on=depends_on or [],
        **{k: v for k, v in kwargs.items() if k != "name"},
    )


async def run_parallel(
    *funcs: Callable[[], Awaitable[T]],
    max_concurrency: int = 10,
) -> List[T]:
    """
    Run multiple async functions in parallel.
    
    Usage:
        >>> async def func1(): return 1
        >>> async def func2(): return 2
        >>> 
        >>> results = await run_parallel(func1, func2)
    """
    semaphore = asyncio.Semaphore(max_concurrency)
    
    async def bounded(func):
        async with semaphore:
            return await func()
    
    return await asyncio.gather(*[bounded(f) for f in funcs])


async def run_with_timeout(
    func: Callable[[], Awaitable[T]],
    timeout_seconds: float,
    default: T = None,
) -> T:
    """Run a function with timeout."""
    try:
        return await asyncio.wait_for(func(), timeout=timeout_seconds)
    except asyncio.TimeoutError:
        return default
