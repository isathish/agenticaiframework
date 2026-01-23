"""
Enterprise Worker Pool Module.

Provides worker pool management, task distribution,
work stealing, priority queues, and parallel execution.

Example:
    # Create worker pool
    pool = create_worker_pool(num_workers=4)
    
    # Submit tasks
    result = await pool.submit(process_data, data)
    
    # Map over items
    results = await pool.map(process_item, items)
    
    # Use decorator
    @background_task()
    async def long_running_task():
        ...
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from heapq import heappush, heappop
from typing import (
    Any,
    Callable,
    Coroutine,
    Deque,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    Tuple,
    TypeVar,
)

T = TypeVar('T')
R = TypeVar('R')


logger = logging.getLogger(__name__)


class WorkerError(Exception):
    """Base worker error."""
    pass


class TaskCancelledError(WorkerError):
    """Task was cancelled."""
    pass


class PoolShutdownError(WorkerError):
    """Pool is shutting down."""
    pass


class TaskPriority(int, Enum):
    """Task priority levels."""
    LOW = 3
    NORMAL = 2
    HIGH = 1
    CRITICAL = 0


class TaskState(str, Enum):
    """Task state."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PoolState(str, Enum):
    """Pool state."""
    CREATED = "created"
    RUNNING = "running"
    DRAINING = "draining"
    SHUTDOWN = "shutdown"


@dataclass
class TaskConfig:
    """Task configuration."""
    priority: TaskPriority = TaskPriority.NORMAL
    timeout: Optional[float] = None
    retries: int = 0
    retry_delay: float = 1.0


@dataclass
class TaskResult(Generic[R]):
    """Task result."""
    task_id: str
    state: TaskState
    result: Optional[R] = None
    error: Optional[Exception] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration: float = 0.0
    retries: int = 0


@dataclass
class WorkerStats:
    """Worker statistics."""
    worker_id: str
    tasks_completed: int = 0
    tasks_failed: int = 0
    total_runtime: float = 0.0
    idle_time: float = 0.0
    current_task: Optional[str] = None


@dataclass
class PoolStats:
    """Pool statistics."""
    total_workers: int = 0
    active_workers: int = 0
    idle_workers: int = 0
    pending_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    cancelled_tasks: int = 0


@dataclass(order=True)
class PriorityTask:
    """Priority queue task."""
    priority: int
    submitted_at: float = field(compare=False)
    task_id: str = field(compare=False)
    func: Callable = field(compare=False)
    args: Tuple = field(compare=False)
    kwargs: Dict = field(compare=False)
    config: TaskConfig = field(compare=False)


class TaskQueue(ABC):
    """Abstract task queue."""
    
    @abstractmethod
    async def put(self, task: PriorityTask) -> None:
        """Add task to queue."""
        pass
    
    @abstractmethod
    async def get(self) -> PriorityTask:
        """Get next task from queue."""
        pass
    
    @abstractmethod
    def size(self) -> int:
        """Get queue size."""
        pass


class PriorityTaskQueue(TaskQueue):
    """Priority-based task queue."""
    
    def __init__(self):
        self._heap: List[PriorityTask] = []
        self._lock = asyncio.Lock()
        self._not_empty = asyncio.Condition(self._lock)
    
    async def put(self, task: PriorityTask) -> None:
        async with self._not_empty:
            heappush(self._heap, task)
            self._not_empty.notify()
    
    async def get(self) -> PriorityTask:
        async with self._not_empty:
            while not self._heap:
                await self._not_empty.wait()
            return heappop(self._heap)
    
    def size(self) -> int:
        return len(self._heap)


class FIFOTaskQueue(TaskQueue):
    """FIFO task queue."""
    
    def __init__(self):
        self._queue: Deque[PriorityTask] = deque()
        self._lock = asyncio.Lock()
        self._not_empty = asyncio.Condition(self._lock)
    
    async def put(self, task: PriorityTask) -> None:
        async with self._not_empty:
            self._queue.append(task)
            self._not_empty.notify()
    
    async def get(self) -> PriorityTask:
        async with self._not_empty:
            while not self._queue:
                await self._not_empty.wait()
            return self._queue.popleft()
    
    def size(self) -> int:
        return len(self._queue)


class Worker:
    """
    Worker that processes tasks from queue.
    """
    
    def __init__(
        self,
        worker_id: str,
        queue: TaskQueue,
        results: Dict[str, TaskResult],
    ):
        self._id = worker_id
        self._queue = queue
        self._results = results
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._current_task_id: Optional[str] = None
        self._stats = WorkerStats(worker_id=worker_id)
        self._idle_start = time.time()
    
    @property
    def id(self) -> str:
        return self._id
    
    @property
    def stats(self) -> WorkerStats:
        return self._stats
    
    @property
    def is_busy(self) -> bool:
        return self._current_task_id is not None
    
    async def start(self) -> None:
        """Start the worker."""
        self._running = True
        self._task = asyncio.create_task(self._run())
    
    async def stop(self) -> None:
        """Stop the worker."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
    
    async def _run(self) -> None:
        """Worker main loop."""
        while self._running:
            try:
                # Update idle time
                idle_duration = time.time() - self._idle_start
                self._stats.idle_time += idle_duration
                
                # Get next task
                priority_task = await self._queue.get()
                self._current_task_id = priority_task.task_id
                self._stats.current_task = priority_task.task_id
                
                # Execute task
                await self._execute_task(priority_task)
                
                self._current_task_id = None
                self._stats.current_task = None
                self._idle_start = time.time()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {self._id} error: {e}")
    
    async def _execute_task(self, task: PriorityTask) -> None:
        """Execute a single task."""
        task_id = task.task_id
        start_time = time.time()
        retries = 0
        
        result = TaskResult(
            task_id=task_id,
            state=TaskState.RUNNING,
            started_at=datetime.utcnow(),
        )
        self._results[task_id] = result
        
        while retries <= task.config.retries:
            try:
                # Execute with timeout
                if task.config.timeout:
                    coro = task.func(*task.args, **task.kwargs)
                    if asyncio.iscoroutine(coro):
                        output = await asyncio.wait_for(
                            coro,
                            timeout=task.config.timeout,
                        )
                    else:
                        output = coro
                else:
                    output = task.func(*task.args, **task.kwargs)
                    if asyncio.iscoroutine(output):
                        output = await output
                
                # Success
                result.state = TaskState.COMPLETED
                result.result = output
                result.completed_at = datetime.utcnow()
                result.duration = time.time() - start_time
                result.retries = retries
                
                self._stats.tasks_completed += 1
                self._stats.total_runtime += result.duration
                
                return
                
            except asyncio.TimeoutError:
                retries += 1
                if retries <= task.config.retries:
                    await asyncio.sleep(task.config.retry_delay)
                else:
                    result.state = TaskState.FAILED
                    result.error = asyncio.TimeoutError("Task timed out")
                    
            except Exception as e:
                retries += 1
                if retries <= task.config.retries:
                    await asyncio.sleep(task.config.retry_delay)
                else:
                    result.state = TaskState.FAILED
                    result.error = e
        
        result.completed_at = datetime.utcnow()
        result.duration = time.time() - start_time
        result.retries = retries
        
        self._stats.tasks_failed += 1


class WorkerPool(ABC):
    """Abstract worker pool."""
    
    @abstractmethod
    async def submit(
        self,
        func: Callable[..., R],
        *args,
        priority: TaskPriority = TaskPriority.NORMAL,
        **kwargs,
    ) -> TaskResult[R]:
        """Submit a task for execution."""
        pass
    
    @abstractmethod
    async def map(
        self,
        func: Callable[[T], R],
        items: List[T],
        priority: TaskPriority = TaskPriority.NORMAL,
    ) -> List[TaskResult[R]]:
        """Map function over items."""
        pass
    
    @abstractmethod
    async def shutdown(self, wait: bool = True) -> None:
        """Shutdown the pool."""
        pass
    
    @abstractmethod
    async def stats(self) -> PoolStats:
        """Get pool statistics."""
        pass


class AsyncWorkerPool(WorkerPool):
    """
    Async worker pool implementation.
    """
    
    def __init__(
        self,
        num_workers: int = 4,
        queue: Optional[TaskQueue] = None,
    ):
        self._num_workers = num_workers
        self._queue = queue or PriorityTaskQueue()
        self._workers: List[Worker] = []
        self._results: Dict[str, TaskResult] = {}
        self._state = PoolState.CREATED
        self._stats = PoolStats(total_workers=num_workers)
    
    async def start(self) -> None:
        """Start the worker pool."""
        if self._state != PoolState.CREATED:
            return
        
        self._state = PoolState.RUNNING
        
        for i in range(self._num_workers):
            worker = Worker(
                worker_id=f"worker-{i}",
                queue=self._queue,
                results=self._results,
            )
            self._workers.append(worker)
            await worker.start()
    
    async def submit(
        self,
        func: Callable[..., R],
        *args,
        priority: TaskPriority = TaskPriority.NORMAL,
        timeout: Optional[float] = None,
        retries: int = 0,
        **kwargs,
    ) -> TaskResult[R]:
        if self._state not in (PoolState.CREATED, PoolState.RUNNING):
            raise PoolShutdownError("Pool is shutting down")
        
        if self._state == PoolState.CREATED:
            await self.start()
        
        task_id = str(uuid.uuid4())
        config = TaskConfig(
            priority=priority,
            timeout=timeout,
            retries=retries,
        )
        
        priority_task = PriorityTask(
            priority=priority.value,
            submitted_at=time.time(),
            task_id=task_id,
            func=func,
            args=args,
            kwargs=kwargs,
            config=config,
        )
        
        # Create pending result
        self._results[task_id] = TaskResult(
            task_id=task_id,
            state=TaskState.PENDING,
        )
        
        await self._queue.put(priority_task)
        self._stats.pending_tasks += 1
        
        # Wait for completion
        while self._results[task_id].state in (TaskState.PENDING, TaskState.RUNNING):
            await asyncio.sleep(0.01)
        
        result = self._results[task_id]
        
        if result.state == TaskState.COMPLETED:
            self._stats.completed_tasks += 1
        elif result.state == TaskState.FAILED:
            self._stats.failed_tasks += 1
        
        self._stats.pending_tasks = max(0, self._stats.pending_tasks - 1)
        
        return result
    
    async def submit_nowait(
        self,
        func: Callable[..., R],
        *args,
        priority: TaskPriority = TaskPriority.NORMAL,
        timeout: Optional[float] = None,
        **kwargs,
    ) -> str:
        """Submit task without waiting for result."""
        if self._state == PoolState.CREATED:
            await self.start()
        
        task_id = str(uuid.uuid4())
        config = TaskConfig(priority=priority, timeout=timeout)
        
        priority_task = PriorityTask(
            priority=priority.value,
            submitted_at=time.time(),
            task_id=task_id,
            func=func,
            args=args,
            kwargs=kwargs,
            config=config,
        )
        
        self._results[task_id] = TaskResult(
            task_id=task_id,
            state=TaskState.PENDING,
        )
        
        await self._queue.put(priority_task)
        
        return task_id
    
    async def get_result(self, task_id: str, timeout: Optional[float] = None) -> TaskResult:
        """Get result for task ID."""
        start = time.time()
        
        while True:
            result = self._results.get(task_id)
            
            if result and result.state not in (TaskState.PENDING, TaskState.RUNNING):
                return result
            
            if timeout and (time.time() - start) > timeout:
                raise asyncio.TimeoutError()
            
            await asyncio.sleep(0.01)
    
    async def map(
        self,
        func: Callable[[T], R],
        items: List[T],
        priority: TaskPriority = TaskPriority.NORMAL,
    ) -> List[TaskResult[R]]:
        # Submit all tasks
        task_ids = []
        for item in items:
            task_id = await self.submit_nowait(func, item, priority=priority)
            task_ids.append(task_id)
        
        # Wait for all results
        results = []
        for task_id in task_ids:
            result = await self.get_result(task_id)
            results.append(result)
        
        return results
    
    async def cancel(self, task_id: str) -> bool:
        """Cancel a pending task."""
        result = self._results.get(task_id)
        
        if result and result.state == TaskState.PENDING:
            result.state = TaskState.CANCELLED
            self._stats.cancelled_tasks += 1
            return True
        
        return False
    
    async def shutdown(self, wait: bool = True) -> None:
        """Shutdown the pool."""
        self._state = PoolState.DRAINING
        
        if wait:
            # Wait for pending tasks
            while self._queue.size() > 0:
                await asyncio.sleep(0.1)
        
        self._state = PoolState.SHUTDOWN
        
        # Stop all workers
        for worker in self._workers:
            await worker.stop()
    
    async def stats(self) -> PoolStats:
        active = sum(1 for w in self._workers if w.is_busy)
        
        return PoolStats(
            total_workers=len(self._workers),
            active_workers=active,
            idle_workers=len(self._workers) - active,
            pending_tasks=self._queue.size(),
            completed_tasks=self._stats.completed_tasks,
            failed_tasks=self._stats.failed_tasks,
            cancelled_tasks=self._stats.cancelled_tasks,
        )


class WorkerPoolRegistry:
    """Registry for worker pools."""
    
    def __init__(self):
        self._pools: Dict[str, WorkerPool] = {}
        self._default: Optional[str] = None
    
    def register(
        self,
        name: str,
        pool: WorkerPool,
        default: bool = False,
    ) -> None:
        self._pools[name] = pool
        if default or self._default is None:
            self._default = name
    
    def get(self, name: Optional[str] = None) -> WorkerPool:
        name = name or self._default
        if not name or name not in self._pools:
            raise WorkerError(f"Pool not found: {name}")
        return self._pools[name]


# Global registry
_global_registry = WorkerPoolRegistry()


# Decorators
def background_task(
    priority: TaskPriority = TaskPriority.NORMAL,
    timeout: Optional[float] = None,
    pool_name: Optional[str] = None,
) -> Callable:
    """
    Decorator to run function as background task.
    
    Example:
        @background_task(priority=TaskPriority.HIGH)
        async def process_data(data):
            ...
    """
    def decorator(func: Callable) -> Callable:
        async def wrapper(*args, **kwargs):
            pool = get_worker_pool(pool_name)
            return await pool.submit(
                func, *args,
                priority=priority,
                timeout=timeout,
                **kwargs
            )
        
        wrapper._original = func
        return wrapper
    
    return decorator


def parallel(num_workers: int = 4) -> Callable:
    """
    Decorator to run function with parallel workers.
    
    Example:
        @parallel(num_workers=8)
        async def process_batch(items):
            ...
    """
    def decorator(func: Callable) -> Callable:
        pool = AsyncWorkerPool(num_workers=num_workers)
        
        async def wrapper(items: List, *args, **kwargs):
            if pool._state == PoolState.CREATED:
                await pool.start()
            
            async def process(item):
                return await func(item, *args, **kwargs)
            
            results = await pool.map(process, items)
            return [r.result for r in results if r.state == TaskState.COMPLETED]
        
        wrapper._pool = pool
        return wrapper
    
    return decorator


# Factory functions
def create_worker_pool(
    num_workers: int = 4,
    priority_queue: bool = True,
) -> AsyncWorkerPool:
    """Create a worker pool."""
    queue = PriorityTaskQueue() if priority_queue else FIFOTaskQueue()
    return AsyncWorkerPool(num_workers=num_workers, queue=queue)


def create_task_config(
    priority: TaskPriority = TaskPriority.NORMAL,
    timeout: Optional[float] = None,
    retries: int = 0,
    retry_delay: float = 1.0,
) -> TaskConfig:
    """Create a task configuration."""
    return TaskConfig(
        priority=priority,
        timeout=timeout,
        retries=retries,
        retry_delay=retry_delay,
    )


def register_worker_pool(
    name: str,
    pool: WorkerPool,
    default: bool = False,
) -> None:
    """Register pool in global registry."""
    _global_registry.register(name, pool, default)


def get_worker_pool(name: Optional[str] = None) -> WorkerPool:
    """Get pool from global registry."""
    try:
        return _global_registry.get(name)
    except WorkerError:
        pool = create_worker_pool()
        register_worker_pool("default", pool, default=True)
        return pool


__all__ = [
    # Exceptions
    "WorkerError",
    "TaskCancelledError",
    "PoolShutdownError",
    # Enums
    "TaskPriority",
    "TaskState",
    "PoolState",
    # Data classes
    "TaskConfig",
    "TaskResult",
    "WorkerStats",
    "PoolStats",
    "PriorityTask",
    # Queue
    "TaskQueue",
    "PriorityTaskQueue",
    "FIFOTaskQueue",
    # Worker
    "Worker",
    # Pool
    "WorkerPool",
    "AsyncWorkerPool",
    # Registry
    "WorkerPoolRegistry",
    # Decorators
    "background_task",
    "parallel",
    # Factory functions
    "create_worker_pool",
    "create_task_config",
    "register_worker_pool",
    "get_worker_pool",
]
