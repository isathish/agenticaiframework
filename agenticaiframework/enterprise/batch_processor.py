"""
Enterprise Batch Processor Module.

Provides batch processing, chunking, parallel execution,
checkpointing, and resumable batch jobs.

Example:
    # Create batch processor
    processor = create_batch_processor(chunk_size=100)
    
    # Process items in batches
    results = await processor.process(items, process_item)
    
    # Use decorator
    @batch_process(chunk_size=50)
    async def process_records(records):
        ...
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    Iterator,
    List,
    Optional,
    Tuple,
    TypeVar,
)

T = TypeVar('T')
R = TypeVar('R')


logger = logging.getLogger(__name__)


class BatchError(Exception):
    """Base batch error."""
    pass


class BatchAbortedError(BatchError):
    """Batch was aborted."""
    pass


class CheckpointError(BatchError):
    """Checkpoint error."""
    pass


class BatchState(str, Enum):
    """Batch job state."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


class ProcessingMode(str, Enum):
    """Processing mode."""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    STREAMING = "streaming"


@dataclass
class BatchConfig:
    """Batch processing configuration."""
    chunk_size: int = 100
    max_parallel: int = 4
    mode: ProcessingMode = ProcessingMode.PARALLEL
    checkpoint_interval: int = 0  # items between checkpoints, 0 = disabled
    retry_failed: bool = True
    max_retries: int = 3
    stop_on_error: bool = False


@dataclass
class ChunkResult(Generic[R]):
    """Result of processing a chunk."""
    chunk_index: int
    items_processed: int
    results: List[R]
    errors: List[Tuple[int, Exception]]
    duration: float


@dataclass
class BatchResult(Generic[R]):
    """Result of batch processing."""
    batch_id: str
    state: BatchState
    total_items: int
    processed_items: int
    successful_items: int
    failed_items: int
    results: List[R]
    errors: List[Tuple[int, Exception]]
    started_at: datetime
    completed_at: Optional[datetime]
    duration: float
    chunks_processed: int


@dataclass
class Checkpoint:
    """Batch checkpoint."""
    batch_id: str
    chunk_index: int
    items_processed: int
    timestamp: datetime
    state: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BatchStats:
    """Batch processing statistics."""
    total_batches: int = 0
    completed_batches: int = 0
    failed_batches: int = 0
    total_items_processed: int = 0
    total_items_failed: int = 0
    avg_processing_time: float = 0.0


class CheckpointStore(ABC):
    """Abstract checkpoint store."""
    
    @abstractmethod
    async def save(self, checkpoint: Checkpoint) -> None:
        """Save checkpoint."""
        pass
    
    @abstractmethod
    async def load(self, batch_id: str) -> Optional[Checkpoint]:
        """Load latest checkpoint."""
        pass
    
    @abstractmethod
    async def delete(self, batch_id: str) -> None:
        """Delete checkpoints for batch."""
        pass


class InMemoryCheckpointStore(CheckpointStore):
    """In-memory checkpoint store."""
    
    def __init__(self):
        self._checkpoints: Dict[str, Checkpoint] = {}
    
    async def save(self, checkpoint: Checkpoint) -> None:
        self._checkpoints[checkpoint.batch_id] = checkpoint
    
    async def load(self, batch_id: str) -> Optional[Checkpoint]:
        return self._checkpoints.get(batch_id)
    
    async def delete(self, batch_id: str) -> None:
        self._checkpoints.pop(batch_id, None)


def chunked(items: List[T], chunk_size: int) -> Iterator[List[T]]:
    """Split items into chunks."""
    for i in range(0, len(items), chunk_size):
        yield items[i:i + chunk_size]


class BatchProcessor(ABC, Generic[T, R]):
    """Abstract batch processor."""
    
    @abstractmethod
    async def process(
        self,
        items: List[T],
        processor: Callable[[T], R],
    ) -> BatchResult[R]:
        """Process items in batch."""
        pass
    
    @abstractmethod
    async def pause(self, batch_id: str) -> None:
        """Pause batch processing."""
        pass
    
    @abstractmethod
    async def resume(self, batch_id: str) -> BatchResult[R]:
        """Resume batch processing."""
        pass
    
    @abstractmethod
    async def abort(self, batch_id: str) -> None:
        """Abort batch processing."""
        pass
    
    @abstractmethod
    async def stats(self) -> BatchStats:
        """Get batch statistics."""
        pass


class SimpleBatchProcessor(BatchProcessor[T, R]):
    """
    Simple batch processor implementation.
    """
    
    def __init__(
        self,
        config: Optional[BatchConfig] = None,
        checkpoint_store: Optional[CheckpointStore] = None,
    ):
        self._config = config or BatchConfig()
        self._checkpoint_store = checkpoint_store or InMemoryCheckpointStore()
        self._active_batches: Dict[str, BatchState] = {}
        self._stats = BatchStats()
        self._paused_batches: Dict[str, Tuple[List[T], Callable, int]] = {}
    
    async def process(
        self,
        items: List[T],
        processor: Callable[[T], R],
    ) -> BatchResult[R]:
        batch_id = str(uuid.uuid4())
        self._active_batches[batch_id] = BatchState.RUNNING
        self._stats.total_batches += 1
        
        start_time = time.time()
        started_at = datetime.utcnow()
        
        results: List[R] = []
        errors: List[Tuple[int, Exception]] = []
        processed = 0
        successful = 0
        failed = 0
        chunk_index = 0
        
        # Check for checkpoint
        checkpoint = await self._checkpoint_store.load(batch_id)
        if checkpoint:
            chunk_index = checkpoint.chunk_index
            processed = checkpoint.items_processed
        
        try:
            chunks = list(chunked(items, self._config.chunk_size))
            
            for idx, chunk in enumerate(chunks):
                if idx < chunk_index:
                    continue  # Skip already processed chunks
                
                # Check if paused or aborted
                state = self._active_batches.get(batch_id)
                if state == BatchState.PAUSED:
                    self._paused_batches[batch_id] = (items, processor, idx)
                    break
                elif state == BatchState.ABORTED:
                    raise BatchAbortedError("Batch was aborted")
                
                # Process chunk
                chunk_result = await self._process_chunk(
                    chunk, processor, idx, processed
                )
                
                results.extend(chunk_result.results)
                errors.extend(chunk_result.errors)
                processed += chunk_result.items_processed
                successful += len(chunk_result.results)
                failed += len(chunk_result.errors)
                chunk_index = idx + 1
                
                # Checkpoint
                if self._config.checkpoint_interval > 0:
                    if processed % self._config.checkpoint_interval == 0:
                        await self._checkpoint_store.save(Checkpoint(
                            batch_id=batch_id,
                            chunk_index=chunk_index,
                            items_processed=processed,
                            timestamp=datetime.utcnow(),
                        ))
                
                # Stop on error
                if self._config.stop_on_error and errors:
                    break
            
            # Determine final state
            if self._active_batches.get(batch_id) == BatchState.PAUSED:
                final_state = BatchState.PAUSED
            elif errors and self._config.stop_on_error:
                final_state = BatchState.FAILED
            else:
                final_state = BatchState.COMPLETED
                self._stats.completed_batches += 1
            
        except BatchAbortedError:
            final_state = BatchState.ABORTED
        except Exception as e:
            final_state = BatchState.FAILED
            self._stats.failed_batches += 1
            errors.append((-1, e))
        
        duration = time.time() - start_time
        
        self._active_batches[batch_id] = final_state
        self._stats.total_items_processed += successful
        self._stats.total_items_failed += failed
        
        if self._stats.completed_batches > 0:
            self._stats.avg_processing_time = (
                (self._stats.avg_processing_time * (self._stats.completed_batches - 1) + duration)
                / self._stats.completed_batches
            )
        
        # Clean up checkpoint
        if final_state == BatchState.COMPLETED:
            await self._checkpoint_store.delete(batch_id)
        
        return BatchResult(
            batch_id=batch_id,
            state=final_state,
            total_items=len(items),
            processed_items=processed,
            successful_items=successful,
            failed_items=failed,
            results=results,
            errors=errors,
            started_at=started_at,
            completed_at=datetime.utcnow() if final_state != BatchState.PAUSED else None,
            duration=duration,
            chunks_processed=chunk_index,
        )
    
    async def _process_chunk(
        self,
        chunk: List[T],
        processor: Callable[[T], R],
        chunk_index: int,
        offset: int,
    ) -> ChunkResult[R]:
        """Process a single chunk."""
        start_time = time.time()
        results: List[R] = []
        errors: List[Tuple[int, Exception]] = []
        
        if self._config.mode == ProcessingMode.PARALLEL:
            # Parallel processing
            tasks = []
            for i, item in enumerate(chunk):
                task = self._process_item_with_retry(
                    item, processor, offset + i
                )
                tasks.append(task)
            
            # Limit parallelism
            sem = asyncio.Semaphore(self._config.max_parallel)
            
            async def limited_task(coro, index):
                async with sem:
                    return await coro, index
            
            limited_tasks = [limited_task(t, i) for i, t in enumerate(tasks)]
            
            for coro in asyncio.as_completed(limited_tasks):
                try:
                    result, _ = await coro
                    if isinstance(result, Exception):
                        errors.append((offset + len(results), result))
                    else:
                        results.append(result)
                except Exception as e:
                    errors.append((offset + len(results), e))
        
        else:
            # Sequential processing
            for i, item in enumerate(chunk):
                try:
                    result = await self._process_item_with_retry(
                        item, processor, offset + i
                    )
                    if isinstance(result, Exception):
                        errors.append((offset + i, result))
                    else:
                        results.append(result)
                except Exception as e:
                    errors.append((offset + i, e))
        
        return ChunkResult(
            chunk_index=chunk_index,
            items_processed=len(chunk),
            results=results,
            errors=errors,
            duration=time.time() - start_time,
        )
    
    async def _process_item_with_retry(
        self,
        item: T,
        processor: Callable[[T], R],
        index: int,
    ) -> R:
        """Process item with retry logic."""
        last_error = None
        
        for attempt in range(self._config.max_retries + 1):
            try:
                result = processor(item)
                if asyncio.iscoroutine(result):
                    return await result
                return result
            except Exception as e:
                last_error = e
                if not self._config.retry_failed:
                    break
                if attempt < self._config.max_retries:
                    await asyncio.sleep(0.1 * (attempt + 1))
        
        if last_error:
            raise last_error
        raise BatchError("Unknown error processing item")
    
    async def pause(self, batch_id: str) -> None:
        if batch_id in self._active_batches:
            self._active_batches[batch_id] = BatchState.PAUSED
    
    async def resume(self, batch_id: str) -> BatchResult[R]:
        if batch_id not in self._paused_batches:
            raise BatchError(f"No paused batch found: {batch_id}")
        
        items, processor, chunk_index = self._paused_batches.pop(batch_id)
        self._active_batches[batch_id] = BatchState.RUNNING
        
        # Process remaining items
        remaining = items[chunk_index * self._config.chunk_size:]
        return await self.process(remaining, processor)
    
    async def abort(self, batch_id: str) -> None:
        if batch_id in self._active_batches:
            self._active_batches[batch_id] = BatchState.ABORTED
            self._paused_batches.pop(batch_id, None)
    
    async def stats(self) -> BatchStats:
        return self._stats


class StreamingBatchProcessor(BatchProcessor[T, R]):
    """
    Streaming batch processor for large datasets.
    """
    
    def __init__(
        self,
        config: Optional[BatchConfig] = None,
        on_chunk_complete: Optional[Callable[[ChunkResult], None]] = None,
    ):
        self._config = config or BatchConfig(mode=ProcessingMode.STREAMING)
        self._on_chunk_complete = on_chunk_complete
        self._stats = BatchStats()
        self._active_batches: Dict[str, BatchState] = {}
    
    async def process(
        self,
        items: List[T],
        processor: Callable[[T], R],
    ) -> BatchResult[R]:
        batch_id = str(uuid.uuid4())
        self._active_batches[batch_id] = BatchState.RUNNING
        
        start_time = time.time()
        started_at = datetime.utcnow()
        
        results: List[R] = []
        errors: List[Tuple[int, Exception]] = []
        processed = 0
        chunk_index = 0
        
        for chunk in chunked(items, self._config.chunk_size):
            if self._active_batches.get(batch_id) == BatchState.ABORTED:
                break
            
            chunk_start = time.time()
            chunk_results = []
            chunk_errors = []
            
            for i, item in enumerate(chunk):
                try:
                    result = processor(item)
                    if asyncio.iscoroutine(result):
                        result = await result
                    chunk_results.append(result)
                except Exception as e:
                    chunk_errors.append((processed + i, e))
            
            results.extend(chunk_results)
            errors.extend(chunk_errors)
            processed += len(chunk)
            
            chunk_result = ChunkResult(
                chunk_index=chunk_index,
                items_processed=len(chunk),
                results=chunk_results,
                errors=chunk_errors,
                duration=time.time() - chunk_start,
            )
            
            if self._on_chunk_complete:
                self._on_chunk_complete(chunk_result)
            
            chunk_index += 1
            
            # Yield control
            await asyncio.sleep(0)
        
        final_state = (
            BatchState.ABORTED 
            if self._active_batches.get(batch_id) == BatchState.ABORTED
            else BatchState.COMPLETED
        )
        
        return BatchResult(
            batch_id=batch_id,
            state=final_state,
            total_items=len(items),
            processed_items=processed,
            successful_items=len(results),
            failed_items=len(errors),
            results=results,
            errors=errors,
            started_at=started_at,
            completed_at=datetime.utcnow(),
            duration=time.time() - start_time,
            chunks_processed=chunk_index,
        )
    
    async def pause(self, batch_id: str) -> None:
        pass  # Not supported in streaming mode
    
    async def resume(self, batch_id: str) -> BatchResult[R]:
        raise BatchError("Resume not supported in streaming mode")
    
    async def abort(self, batch_id: str) -> None:
        self._active_batches[batch_id] = BatchState.ABORTED
    
    async def stats(self) -> BatchStats:
        return self._stats


class BatchProcessorRegistry:
    """Registry for batch processors."""
    
    def __init__(self):
        self._processors: Dict[str, BatchProcessor] = {}
        self._default: Optional[str] = None
    
    def register(
        self,
        name: str,
        processor: BatchProcessor,
        default: bool = False,
    ) -> None:
        self._processors[name] = processor
        if default or self._default is None:
            self._default = name
    
    def get(self, name: Optional[str] = None) -> BatchProcessor:
        name = name or self._default
        if not name or name not in self._processors:
            raise BatchError(f"Processor not found: {name}")
        return self._processors[name]


# Global registry
_global_registry = BatchProcessorRegistry()


# Decorators
def batch_process(
    chunk_size: int = 100,
    mode: ProcessingMode = ProcessingMode.PARALLEL,
    max_parallel: int = 4,
) -> Callable:
    """
    Decorator to process items in batches.
    
    Example:
        @batch_process(chunk_size=50)
        async def process_records(records):
            ...
    """
    def decorator(func: Callable) -> Callable:
        config = BatchConfig(
            chunk_size=chunk_size,
            mode=mode,
            max_parallel=max_parallel,
        )
        processor = SimpleBatchProcessor(config)
        
        async def wrapper(items: List, *args, **kwargs):
            async def process_item(item):
                result = func(item, *args, **kwargs)
                if asyncio.iscoroutine(result):
                    return await result
                return result
            
            result = await processor.process(items, process_item)
            return result.results
        
        wrapper._processor = processor
        return wrapper
    
    return decorator


def chunked_processor(chunk_size: int = 100) -> Callable:
    """
    Decorator to make function process in chunks.
    
    Example:
        @chunked_processor(chunk_size=50)
        async def bulk_insert(items):
            ...
    """
    def decorator(func: Callable) -> Callable:
        async def wrapper(items: List, *args, **kwargs):
            results = []
            for chunk in chunked(items, chunk_size):
                result = func(chunk, *args, **kwargs)
                if asyncio.iscoroutine(result):
                    result = await result
                results.append(result)
            return results
        
        return wrapper
    
    return decorator


# Factory functions
def create_batch_processor(
    chunk_size: int = 100,
    max_parallel: int = 4,
    mode: ProcessingMode = ProcessingMode.PARALLEL,
    checkpoint_store: Optional[CheckpointStore] = None,
) -> SimpleBatchProcessor:
    """Create a batch processor."""
    config = BatchConfig(
        chunk_size=chunk_size,
        max_parallel=max_parallel,
        mode=mode,
    )
    return SimpleBatchProcessor(config, checkpoint_store)


def create_streaming_processor(
    chunk_size: int = 100,
    on_chunk_complete: Optional[Callable[[ChunkResult], None]] = None,
) -> StreamingBatchProcessor:
    """Create a streaming batch processor."""
    config = BatchConfig(
        chunk_size=chunk_size,
        mode=ProcessingMode.STREAMING,
    )
    return StreamingBatchProcessor(config, on_chunk_complete)


def create_batch_config(
    chunk_size: int = 100,
    max_parallel: int = 4,
    mode: ProcessingMode = ProcessingMode.PARALLEL,
    checkpoint_interval: int = 0,
    retry_failed: bool = True,
    max_retries: int = 3,
) -> BatchConfig:
    """Create a batch configuration."""
    return BatchConfig(
        chunk_size=chunk_size,
        max_parallel=max_parallel,
        mode=mode,
        checkpoint_interval=checkpoint_interval,
        retry_failed=retry_failed,
        max_retries=max_retries,
    )


def register_batch_processor(
    name: str,
    processor: BatchProcessor,
    default: bool = False,
) -> None:
    """Register processor in global registry."""
    _global_registry.register(name, processor, default)


def get_batch_processor(name: Optional[str] = None) -> BatchProcessor:
    """Get processor from global registry."""
    try:
        return _global_registry.get(name)
    except BatchError:
        processor = create_batch_processor()
        register_batch_processor("default", processor, default=True)
        return processor


__all__ = [
    # Exceptions
    "BatchError",
    "BatchAbortedError",
    "CheckpointError",
    # Enums
    "BatchState",
    "ProcessingMode",
    # Data classes
    "BatchConfig",
    "ChunkResult",
    "BatchResult",
    "Checkpoint",
    "BatchStats",
    # Checkpoint
    "CheckpointStore",
    "InMemoryCheckpointStore",
    # Processor
    "BatchProcessor",
    "SimpleBatchProcessor",
    "StreamingBatchProcessor",
    # Registry
    "BatchProcessorRegistry",
    # Utilities
    "chunked",
    # Decorators
    "batch_process",
    "chunked_processor",
    # Factory functions
    "create_batch_processor",
    "create_streaming_processor",
    "create_batch_config",
    "register_batch_processor",
    "get_batch_processor",
]
