"""
Enterprise Batch Processing Module.

Provides batch processing, job queues, and parallel execution
for handling large volumes of requests efficiently.

Example:
    # Batch processor
    processor = BatchProcessor(
        handler=process_item,
        batch_size=100,
        max_concurrent=5,
    )
    
    results = await processor.process(items)
    
    # Job queue
    queue = JobQueue(workers=4)
    job_id = await queue.submit(my_task, arg1, arg2)
    result = await queue.get_result(job_id)
"""

from __future__ import annotations

import asyncio
import uuid
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Sequence,
    TypeVar,
    Union,
)
from enum import Enum
import logging

logger = logging.getLogger(__name__)

T = TypeVar("T")
R = TypeVar("R")


class JobStatus(str, Enum):
    """Job execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class BatchError(Exception):
    """Batch processing error."""
    pass


class JobError(Exception):
    """Job execution error."""
    
    def __init__(self, message: str, job_id: str, original: Optional[Exception] = None):
        super().__init__(message)
        self.job_id = job_id
        self.original = original


@dataclass
class BatchResult(Generic[T, R]):
    """Result of batch processing."""
    successful: List[R] = field(default_factory=list)
    failed: List[tuple[T, Exception]] = field(default_factory=list)
    total: int = 0
    duration: float = 0.0
    
    @property
    def success_count(self) -> int:
        """Number of successful items."""
        return len(self.successful)
    
    @property
    def failure_count(self) -> int:
        """Number of failed items."""
        return len(self.failed)
    
    @property
    def success_rate(self) -> float:
        """Success rate as percentage."""
        return (self.success_count / self.total * 100) if self.total > 0 else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total": self.total,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "success_rate": self.success_rate,
            "duration": self.duration,
        }


@dataclass
class Job(Generic[T]):
    """Represents a queued job."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    func: Optional[Callable[..., T]] = None
    args: tuple = field(default_factory=tuple)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    status: JobStatus = JobStatus.PENDING
    result: Optional[T] = None
    error: Optional[Exception] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    retries: int = 0
    max_retries: int = 3
    priority: int = 0
    
    @property
    def duration(self) -> Optional[float]:
        """Job duration in seconds."""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None
    
    @property
    def wait_time(self) -> Optional[float]:
        """Time spent waiting in queue."""
        if self.started_at:
            return self.started_at - self.created_at
        return None


class BatchStrategy(ABC):
    """Strategy for batching items."""
    
    @abstractmethod
    def create_batches(self, items: Sequence[T]) -> List[List[T]]:
        """Create batches from items."""
        pass


class SizeBatchStrategy(BatchStrategy, Generic[T]):
    """Batch by fixed size."""
    
    def __init__(self, batch_size: int = 100):
        self.batch_size = batch_size
    
    def create_batches(self, items: Sequence[T]) -> List[List[T]]:
        """Create fixed-size batches."""
        batches = []
        for i in range(0, len(items), self.batch_size):
            batches.append(list(items[i:i + self.batch_size]))
        return batches


class DynamicBatchStrategy(BatchStrategy, Generic[T]):
    """Batch with dynamic sizing based on memory/complexity."""
    
    def __init__(
        self,
        min_size: int = 10,
        max_size: int = 1000,
        size_func: Optional[Callable[[T], int]] = None,
        max_batch_weight: int = 10000,
    ):
        self.min_size = min_size
        self.max_size = max_size
        self.size_func = size_func or (lambda x: 1)
        self.max_batch_weight = max_batch_weight
    
    def create_batches(self, items: Sequence[T]) -> List[List[T]]:
        """Create dynamically sized batches."""
        batches = []
        current_batch = []
        current_weight = 0
        
        for item in items:
            weight = self.size_func(item)
            
            if current_weight + weight > self.max_batch_weight:
                if current_batch:
                    batches.append(current_batch)
                current_batch = [item]
                current_weight = weight
            else:
                current_batch.append(item)
                current_weight += weight
            
            if len(current_batch) >= self.max_size:
                batches.append(current_batch)
                current_batch = []
                current_weight = 0
        
        if current_batch:
            batches.append(current_batch)
        
        return batches


class BatchProcessor(Generic[T, R]):
    """
    Process items in batches with concurrency control.
    """
    
    def __init__(
        self,
        handler: Callable[[T], R],
        batch_size: int = 100,
        max_concurrent: int = 5,
        continue_on_error: bool = True,
        retry_failed: bool = False,
        max_retries: int = 3,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ):
        """
        Initialize batch processor.
        
        Args:
            handler: Function to process each item
            batch_size: Number of items per batch
            max_concurrent: Maximum concurrent batches
            continue_on_error: Continue processing on errors
            retry_failed: Retry failed items
            max_retries: Maximum retry attempts
            progress_callback: Called with (completed, total)
        """
        self.handler = handler
        self.batch_size = batch_size
        self.max_concurrent = max_concurrent
        self.continue_on_error = continue_on_error
        self.retry_failed = retry_failed
        self.max_retries = max_retries
        self.progress_callback = progress_callback
        
        self._strategy = SizeBatchStrategy(batch_size)
    
    async def process(self, items: Sequence[T]) -> BatchResult[T, R]:
        """
        Process items in batches.
        
        Args:
            items: Items to process
            
        Returns:
            BatchResult with successful and failed items
        """
        start = time.time()
        result = BatchResult(total=len(items))
        
        if not items:
            return result
        
        batches = self._strategy.create_batches(items)
        semaphore = asyncio.Semaphore(self.max_concurrent)
        completed = 0
        
        async def process_batch(batch: List[T]) -> List[tuple[bool, Union[R, tuple[T, Exception]]]]:
            async with semaphore:
                batch_results = []
                for item in batch:
                    try:
                        if asyncio.iscoroutinefunction(self.handler):
                            r = await self.handler(item)
                        else:
                            r = self.handler(item)
                        batch_results.append((True, r))
                    except Exception as e:
                        if not self.continue_on_error:
                            raise
                        batch_results.append((False, (item, e)))
                return batch_results
        
        # Process all batches
        tasks = [process_batch(batch) for batch in batches]
        
        for coro in asyncio.as_completed(tasks):
            try:
                batch_results = await coro
                for success, data in batch_results:
                    if success:
                        result.successful.append(data)
                    else:
                        result.failed.append(data)
                    completed += 1
                    
                if self.progress_callback:
                    self.progress_callback(completed, result.total)
                    
            except Exception as e:
                logger.error(f"Batch processing error: {e}")
                if not self.continue_on_error:
                    raise
        
        # Retry failed items
        if self.retry_failed and result.failed:
            await self._retry_failed(result)
        
        result.duration = time.time() - start
        return result
    
    async def _retry_failed(self, result: BatchResult[T, R]) -> None:
        """Retry failed items."""
        retries = 0
        
        while result.failed and retries < self.max_retries:
            retries += 1
            failed_items = [item for item, _ in result.failed]
            result.failed.clear()
            
            batches = self._strategy.create_batches(failed_items)
            semaphore = asyncio.Semaphore(self.max_concurrent)
            
            async def process_item(item: T) -> tuple[bool, Union[R, tuple[T, Exception]]]:
                async with semaphore:
                    try:
                        if asyncio.iscoroutinefunction(self.handler):
                            r = await self.handler(item)
                        else:
                            r = self.handler(item)
                        return (True, r)
                    except Exception as e:
                        return (False, (item, e))
            
            for batch in batches:
                tasks = [process_item(item) for item in batch]
                batch_results = await asyncio.gather(*tasks)
                
                for success, data in batch_results:
                    if success:
                        result.successful.append(data)
                    else:
                        result.failed.append(data)
            
            logger.info(
                f"Retry {retries}: {len(result.failed)} still failing"
            )


class JobQueue:
    """
    Async job queue with worker pool.
    """
    
    def __init__(
        self,
        workers: int = 4,
        max_queue_size: int = 1000,
    ):
        """
        Initialize job queue.
        
        Args:
            workers: Number of worker tasks
            max_queue_size: Maximum queue size
        """
        self.workers = workers
        self.max_queue_size = max_queue_size
        
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue(max_queue_size)
        self._jobs: Dict[str, Job] = {}
        self._worker_tasks: List[asyncio.Task] = []
        self._running = False
        self._results: Dict[str, asyncio.Event] = {}
    
    async def start(self) -> None:
        """Start the job queue workers."""
        if self._running:
            return
        
        self._running = True
        self._worker_tasks = [
            asyncio.create_task(self._worker(i))
            for i in range(self.workers)
        ]
        logger.info(f"Job queue started with {self.workers} workers")
    
    async def stop(self, wait: bool = True) -> None:
        """Stop the job queue."""
        self._running = False
        
        if wait:
            # Wait for pending jobs
            await self._queue.join()
        
        # Cancel workers
        for task in self._worker_tasks:
            task.cancel()
        
        await asyncio.gather(*self._worker_tasks, return_exceptions=True)
        self._worker_tasks.clear()
        logger.info("Job queue stopped")
    
    async def _worker(self, worker_id: int) -> None:
        """Worker task that processes jobs."""
        while self._running:
            try:
                _, job_id = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=1.0,
                )
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            
            job = self._jobs.get(job_id)
            if not job:
                self._queue.task_done()
                continue
            
            job.status = JobStatus.RUNNING
            job.started_at = time.time()
            
            try:
                if asyncio.iscoroutinefunction(job.func):
                    result = await job.func(*job.args, **job.kwargs)
                else:
                    result = job.func(*job.args, **job.kwargs)
                
                job.result = result
                job.status = JobStatus.COMPLETED
                
            except Exception as e:
                job.error = e
                
                if job.retries < job.max_retries:
                    job.retries += 1
                    job.status = JobStatus.RETRYING
                    await self._queue.put((-job.priority, job.id))
                else:
                    job.status = JobStatus.FAILED
                    logger.error(f"Job {job.id} failed: {e}")
            
            finally:
                job.completed_at = time.time()
                
                # Signal completion
                if job.id in self._results:
                    self._results[job.id].set()
                
                self._queue.task_done()
    
    async def submit(
        self,
        func: Callable[..., T],
        *args: Any,
        priority: int = 0,
        max_retries: int = 3,
        **kwargs: Any,
    ) -> str:
        """
        Submit a job to the queue.
        
        Args:
            func: Function to execute
            *args: Positional arguments
            priority: Job priority (higher = more urgent)
            max_retries: Maximum retry attempts
            **kwargs: Keyword arguments
            
        Returns:
            Job ID for tracking
        """
        job = Job(
            func=func,
            args=args,
            kwargs=kwargs,
            priority=priority,
            max_retries=max_retries,
        )
        
        self._jobs[job.id] = job
        self._results[job.id] = asyncio.Event()
        
        await self._queue.put((-priority, job.id))
        return job.id
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID."""
        return self._jobs.get(job_id)
    
    async def wait(self, job_id: str, timeout: Optional[float] = None) -> Job:
        """
        Wait for job completion.
        
        Args:
            job_id: Job ID to wait for
            timeout: Maximum wait time
            
        Returns:
            Completed job
        """
        if job_id not in self._results:
            raise JobError(f"Job {job_id} not found", job_id)
        
        if timeout:
            await asyncio.wait_for(
                self._results[job_id].wait(),
                timeout=timeout,
            )
        else:
            await self._results[job_id].wait()
        
        return self._jobs[job_id]
    
    async def get_result(self, job_id: str, timeout: Optional[float] = None) -> T:
        """
        Wait for and return job result.
        
        Args:
            job_id: Job ID
            timeout: Maximum wait time
            
        Returns:
            Job result
            
        Raises:
            JobError: If job failed
        """
        job = await self.wait(job_id, timeout)
        
        if job.status == JobStatus.FAILED:
            raise JobError(
                f"Job {job_id} failed",
                job_id,
                job.error,
            )
        
        return job.result
    
    async def cancel(self, job_id: str) -> bool:
        """
        Cancel a pending job.
        
        Args:
            job_id: Job ID to cancel
            
        Returns:
            True if cancelled, False if not found or already completed
        """
        job = self._jobs.get(job_id)
        if not job:
            return False
        
        if job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
            return False
        
        job.status = JobStatus.CANCELLED
        job.completed_at = time.time()
        
        if job_id in self._results:
            self._results[job_id].set()
        
        return True
    
    @property
    def pending_count(self) -> int:
        """Number of pending jobs."""
        return self._queue.qsize()
    
    @property
    def running_count(self) -> int:
        """Number of running jobs."""
        return sum(
            1 for job in self._jobs.values()
            if job.status == JobStatus.RUNNING
        )


class ParallelExecutor:
    """
    Execute functions in parallel with concurrency limits.
    """
    
    def __init__(
        self,
        max_concurrent: int = 10,
        timeout: Optional[float] = None,
    ):
        """
        Initialize parallel executor.
        
        Args:
            max_concurrent: Maximum concurrent executions
            timeout: Default timeout per execution
        """
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self._semaphore = asyncio.Semaphore(max_concurrent)
    
    async def map(
        self,
        func: Callable[[T], R],
        items: Sequence[T],
    ) -> List[R]:
        """
        Apply function to items in parallel.
        
        Args:
            func: Function to apply
            items: Items to process
            
        Returns:
            List of results in same order
        """
        async def execute(item: T, index: int) -> tuple[int, R]:
            async with self._semaphore:
                if asyncio.iscoroutinefunction(func):
                    result = await func(item)
                else:
                    result = func(item)
                return index, result
        
        tasks = [execute(item, i) for i, item in enumerate(items)]
        results = await asyncio.gather(*tasks)
        
        # Sort by original index
        sorted_results = sorted(results, key=lambda x: x[0])
        return [r for _, r in sorted_results]
    
    async def execute_many(
        self,
        tasks: List[tuple[Callable, tuple, Dict]],
    ) -> List[Any]:
        """
        Execute multiple different functions in parallel.
        
        Args:
            tasks: List of (func, args, kwargs) tuples
            
        Returns:
            List of results
        """
        async def execute(
            func: Callable,
            args: tuple,
            kwargs: Dict,
            index: int,
        ) -> tuple[int, Any]:
            async with self._semaphore:
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                return index, result
        
        coros = [
            execute(func, args, kwargs, i)
            for i, (func, args, kwargs) in enumerate(tasks)
        ]
        
        if self.timeout:
            results = await asyncio.wait_for(
                asyncio.gather(*coros),
                timeout=self.timeout * len(tasks),
            )
        else:
            results = await asyncio.gather(*coros)
        
        sorted_results = sorted(results, key=lambda x: x[0])
        return [r for _, r in sorted_results]


def batch(
    batch_size: int = 100,
    max_concurrent: int = 5,
    continue_on_error: bool = True,
) -> Callable:
    """
    Decorator for batch processing functions.
    
    Example:
        @batch(batch_size=50)
        async def process_items(items):
            return [process(item) for item in items]
    """
    def decorator(func: Callable) -> Callable:
        async def wrapper(items: Sequence[T], **kwargs: Any) -> BatchResult:
            processor = BatchProcessor(
                handler=func,
                batch_size=batch_size,
                max_concurrent=max_concurrent,
                continue_on_error=continue_on_error,
            )
            return await processor.process(items)
        
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    
    return decorator


def parallel(max_concurrent: int = 10) -> Callable:
    """
    Decorator for parallel execution.
    
    Example:
        @parallel(max_concurrent=5)
        async def fetch_urls(urls):
            return [await fetch(url) for url in urls]
    """
    def decorator(func: Callable) -> Callable:
        executor = ParallelExecutor(max_concurrent=max_concurrent)
        
        async def wrapper(items: Sequence[T]) -> List[R]:
            return await executor.map(func, items)
        
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    
    return decorator


__all__ = [
    # Enums
    "JobStatus",
    # Exceptions
    "BatchError",
    "JobError",
    # Data classes
    "BatchResult",
    "Job",
    # Strategies
    "BatchStrategy",
    "SizeBatchStrategy",
    "DynamicBatchStrategy",
    # Processors
    "BatchProcessor",
    "JobQueue",
    "ParallelExecutor",
    # Decorators
    "batch",
    "parallel",
]
