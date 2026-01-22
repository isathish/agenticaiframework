"""
Enterprise Utilities - Common patterns and helpers for production AI applications.

This module provides utility functions, decorators, and classes that are used
across the enterprise module for consistent behavior.

Features:
- Async context managers
- Streaming support
- Batch processing
- Progress tracking
- Cancellation tokens
- Retry with exponential backoff
- Circuit breaker pattern
- Rate limiting
- Connection pooling
"""

import asyncio
import functools
import hashlib
import json
import logging
import os
import random
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    AsyncGenerator,
    AsyncIterator,
    Awaitable,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")
R = TypeVar("R")


# =============================================================================
# Async Context Managers
# =============================================================================

class AsyncContextMixin:
    """Mixin for async context manager support."""
    
    async def __aenter__(self):
        """Enter async context."""
        await self._setup()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context."""
        await self._cleanup()
        return False
    
    async def _setup(self):
        """Override to add setup logic."""
        pass
    
    async def _cleanup(self):
        """Override to add cleanup logic."""
        pass


# =============================================================================
# Streaming Support
# =============================================================================

@dataclass
class StreamChunk:
    """A chunk of streamed data."""
    content: str
    index: int
    is_final: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class StreamingResponse:
    """Async iterator for streaming responses."""
    
    def __init__(self, generator: AsyncGenerator[str, None]):
        self._generator = generator
        self._chunks: List[str] = []
        self._complete = False
    
    def __aiter__(self):
        return self
    
    async def __anext__(self) -> StreamChunk:
        try:
            content = await self._generator.__anext__()
            self._chunks.append(content)
            return StreamChunk(
                content=content,
                index=len(self._chunks) - 1,
                is_final=False,
            )
        except StopAsyncIteration:
            self._complete = True
            raise
    
    @property
    def complete_response(self) -> str:
        """Get the complete accumulated response."""
        return "".join(self._chunks)
    
    @property
    def is_complete(self) -> bool:
        return self._complete


async def stream_response(
    client: Any,
    messages: List[Dict],
    model: str,
    **kwargs,
) -> AsyncGenerator[str, None]:
    """
    Stream responses from an LLM client.
    
    Args:
        client: LLM client (OpenAI, Azure, etc.)
        messages: Chat messages
        model: Model name
        **kwargs: Additional parameters
        
    Yields:
        Content chunks as they arrive
    """
    params = {
        "model": model,
        "messages": messages,
        "stream": True,
        **kwargs,
    }
    
    response = await asyncio.to_thread(
        lambda: client.chat.completions.create(**params)
    )
    
    for chunk in response:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


# =============================================================================
# Batch Processing
# =============================================================================

@dataclass
class BatchResult(Generic[T]):
    """Result from batch processing."""
    results: List[T]
    errors: List[Tuple[int, Exception]]
    total: int
    successful: int
    failed: int
    duration_seconds: float


class BatchProcessor(Generic[T, R]):
    """
    Process multiple items in batches.
    
    Usage:
        >>> processor = BatchProcessor(
        ...     process_fn=my_async_function,
        ...     batch_size=10,
        ...     max_concurrency=5,
        ... )
        >>> results = await processor.process(items)
    """
    
    def __init__(
        self,
        process_fn: Callable[[T], Awaitable[R]],
        batch_size: int = 10,
        max_concurrency: int = 5,
        retry_on_error: bool = True,
        max_retries: int = 3,
    ):
        self.process_fn = process_fn
        self.batch_size = batch_size
        self.max_concurrency = max_concurrency
        self.retry_on_error = retry_on_error
        self.max_retries = max_retries
        self._semaphore = asyncio.Semaphore(max_concurrency)
    
    async def _process_item(
        self,
        index: int,
        item: T,
    ) -> Tuple[int, Optional[R], Optional[Exception]]:
        """Process a single item with retry logic."""
        async with self._semaphore:
            for attempt in range(self.max_retries):
                try:
                    result = await self.process_fn(item)
                    return (index, result, None)
                except Exception as e:
                    if attempt == self.max_retries - 1 or not self.retry_on_error:
                        return (index, None, e)
                    await asyncio.sleep(2 ** attempt)
    
    async def process(
        self,
        items: List[T],
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> BatchResult[R]:
        """
        Process all items in batches.
        
        Args:
            items: Items to process
            progress_callback: Optional callback(completed, total)
            
        Returns:
            BatchResult with all results and errors
        """
        start_time = time.time()
        results: List[Optional[R]] = [None] * len(items)
        errors: List[Tuple[int, Exception]] = []
        
        # Process in batches
        for batch_start in range(0, len(items), self.batch_size):
            batch_end = min(batch_start + self.batch_size, len(items))
            batch = items[batch_start:batch_end]
            
            # Create tasks for this batch
            tasks = [
                self._process_item(batch_start + i, item)
                for i, item in enumerate(batch)
            ]
            
            # Wait for batch to complete
            batch_results = await asyncio.gather(*tasks)
            
            # Collect results
            for index, result, error in batch_results:
                if error:
                    errors.append((index, error))
                else:
                    results[index] = result
            
            if progress_callback:
                progress_callback(batch_end, len(items))
        
        duration = time.time() - start_time
        successful = len(items) - len(errors)
        
        return BatchResult(
            results=[r for r in results if r is not None],
            errors=errors,
            total=len(items),
            successful=successful,
            failed=len(errors),
            duration_seconds=duration,
        )


# =============================================================================
# Progress Tracking
# =============================================================================

@dataclass
class ProgressInfo:
    """Progress information for long-running operations."""
    current: int
    total: int
    percentage: float
    message: str
    elapsed_seconds: float
    estimated_remaining_seconds: Optional[float]
    metadata: Dict[str, Any] = field(default_factory=dict)


class ProgressTracker:
    """
    Track progress of long-running operations.
    
    Usage:
        >>> tracker = ProgressTracker(total=100)
        >>> for i in range(100):
        ...     # do work
        ...     await tracker.update(i + 1, "Processing item")
    """
    
    def __init__(
        self,
        total: int,
        callback: Optional[Callable[[ProgressInfo], None]] = None,
    ):
        self.total = total
        self.current = 0
        self.callback = callback
        self._start_time = time.time()
        self._last_update = 0.0
    
    async def update(
        self,
        current: int,
        message: str = "",
        **metadata,
    ):
        """Update progress."""
        self.current = current
        elapsed = time.time() - self._start_time
        
        # Calculate ETA
        if current > 0:
            rate = current / elapsed
            remaining = (self.total - current) / rate if rate > 0 else None
        else:
            remaining = None
        
        info = ProgressInfo(
            current=current,
            total=self.total,
            percentage=(current / self.total) * 100 if self.total > 0 else 0,
            message=message,
            elapsed_seconds=elapsed,
            estimated_remaining_seconds=remaining,
            metadata=metadata,
        )
        
        if self.callback:
            self.callback(info)
        
        # Yield to event loop occasionally
        now = time.time()
        if now - self._last_update > 0.1:
            await asyncio.sleep(0)
            self._last_update = now


# =============================================================================
# Cancellation Support
# =============================================================================

class CancellationToken:
    """
    Token for cancelling long-running operations.
    
    Usage:
        >>> token = CancellationToken()
        >>> task = asyncio.create_task(long_operation(token))
        >>> # Later...
        >>> token.cancel("User requested cancellation")
    """
    
    def __init__(self):
        self._cancelled = False
        self._reason: Optional[str] = None
        self._callbacks: List[Callable[[], None]] = []
    
    @property
    def is_cancelled(self) -> bool:
        return self._cancelled
    
    @property
    def cancellation_reason(self) -> Optional[str]:
        return self._reason
    
    def cancel(self, reason: str = "Cancelled"):
        """Cancel the operation."""
        self._cancelled = True
        self._reason = reason
        
        for callback in self._callbacks:
            try:
                callback()
            except Exception:
                pass
    
    def on_cancel(self, callback: Callable[[], None]):
        """Register a cancellation callback."""
        self._callbacks.append(callback)
        if self._cancelled:
            callback()
    
    def check(self):
        """Check if cancelled and raise if so."""
        if self._cancelled:
            raise CancelledException(self._reason or "Operation cancelled")


class CancelledException(Exception):
    """Exception raised when an operation is cancelled."""
    pass


# =============================================================================
# Retry with Exponential Backoff
# =============================================================================

@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)


def retry_with_backoff(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
):
    """
    Decorator for retry with exponential backoff.
    
    Args:
        max_attempts: Maximum retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay cap
        exponential_base: Exponential multiplier
        jitter: Add random jitter to prevent thundering herd
        retryable_exceptions: Exceptions that trigger retry
        
    Usage:
        >>> @retry_with_backoff(max_attempts=5, base_delay=0.5)
        >>> async def flaky_operation():
        ...     # May fail sometimes
        ...     pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    
                    if attempt == max_attempts - 1:
                        raise
                    
                    # Calculate delay
                    delay = min(
                        base_delay * (exponential_base ** attempt),
                        max_delay,
                    )
                    
                    # Add jitter
                    if jitter:
                        delay *= (0.5 + random.random())
                    
                    logger.warning(
                        f"Attempt {attempt + 1}/{max_attempts} failed: {e}. "
                        f"Retrying in {delay:.2f}s"
                    )
                    
                    await asyncio.sleep(delay)
            
            raise last_exception
        
        return wrapper
    return decorator


# =============================================================================
# Circuit Breaker Pattern
# =============================================================================

class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5
    success_threshold: int = 2
    timeout_seconds: float = 30.0
    half_open_max_calls: int = 3


class CircuitBreaker:
    """
    Circuit breaker for fault tolerance.
    
    Prevents cascading failures by stopping calls to failing services.
    
    Usage:
        >>> breaker = CircuitBreaker(failure_threshold=5, timeout_seconds=30)
        >>> 
        >>> @breaker
        >>> async def call_external_service():
        ...     # May fail
        ...     pass
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout_seconds: float = 30.0,
        half_open_max_calls: int = 3,
        name: str = "default",
    ):
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout_seconds = timeout_seconds
        self.half_open_max_calls = half_open_max_calls
        self.name = name
        
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0
        self._lock = asyncio.Lock()
    
    @property
    def state(self) -> CircuitState:
        return self._state
    
    @property
    def is_closed(self) -> bool:
        return self._state == CircuitState.CLOSED
    
    @property
    def is_open(self) -> bool:
        return self._state == CircuitState.OPEN
    
    async def _check_state(self):
        """Check and potentially transition state."""
        async with self._lock:
            if self._state == CircuitState.OPEN:
                # Check if timeout has passed
                if self._last_failure_time:
                    elapsed = time.time() - self._last_failure_time
                    if elapsed >= self.timeout_seconds:
                        self._state = CircuitState.HALF_OPEN
                        self._half_open_calls = 0
                        self._success_count = 0
                        logger.info(f"Circuit {self.name}: OPEN -> HALF_OPEN")
    
    async def _record_success(self):
        """Record a successful call."""
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    logger.info(f"Circuit {self.name}: HALF_OPEN -> CLOSED")
            else:
                self._failure_count = 0
    
    async def _record_failure(self):
        """Record a failed call."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                logger.warning(f"Circuit {self.name}: HALF_OPEN -> OPEN")
            elif self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(f"Circuit {self.name}: CLOSED -> OPEN")
    
    def __call__(self, func: Callable) -> Callable:
        """Use as decorator."""
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            await self._check_state()
            
            if self._state == CircuitState.OPEN:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker {self.name} is OPEN"
                )
            
            if self._state == CircuitState.HALF_OPEN:
                async with self._lock:
                    if self._half_open_calls >= self.half_open_max_calls:
                        raise CircuitBreakerOpenError(
                            f"Circuit breaker {self.name} half-open limit reached"
                        )
                    self._half_open_calls += 1
            
            try:
                result = await func(*args, **kwargs)
                await self._record_success()
                return result
            except Exception as e:
                await self._record_failure()
                raise
        
        return wrapper


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass


# =============================================================================
# Rate Limiting
# =============================================================================

@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    requests_per_second: float = 10.0
    burst_size: int = 20
    per_key: bool = False


class RateLimiter:
    """
    Token bucket rate limiter.
    
    Usage:
        >>> limiter = RateLimiter(requests_per_second=10, burst_size=20)
        >>> 
        >>> async def make_request():
        ...     async with limiter:
        ...         # Rate limited operation
        ...         pass
    """
    
    def __init__(
        self,
        requests_per_second: float = 10.0,
        burst_size: int = 20,
    ):
        self.rate = requests_per_second
        self.burst_size = burst_size
        self._tokens = float(burst_size)
        self._last_update = time.time()
        self._lock = asyncio.Lock()
    
    async def acquire(self, tokens: int = 1) -> float:
        """
        Acquire tokens, waiting if necessary.
        
        Returns the time waited.
        """
        async with self._lock:
            # Refill tokens
            now = time.time()
            elapsed = now - self._last_update
            self._tokens = min(
                self.burst_size,
                self._tokens + elapsed * self.rate,
            )
            self._last_update = now
            
            # Check if we have enough tokens
            if self._tokens >= tokens:
                self._tokens -= tokens
                return 0.0
            
            # Calculate wait time
            needed = tokens - self._tokens
            wait_time = needed / self.rate
            
            # Wait and consume
            await asyncio.sleep(wait_time)
            self._tokens = 0
            self._last_update = time.time()
            
            return wait_time
    
    async def __aenter__(self):
        await self.acquire()
        return self
    
    async def __aexit__(self, *args):
        pass


class KeyedRateLimiter:
    """Rate limiter with per-key limits."""
    
    def __init__(
        self,
        requests_per_second: float = 10.0,
        burst_size: int = 20,
    ):
        self.rate = requests_per_second
        self.burst_size = burst_size
        self._limiters: Dict[str, RateLimiter] = {}
        self._lock = asyncio.Lock()
    
    async def acquire(self, key: str, tokens: int = 1) -> float:
        """Acquire tokens for a specific key."""
        async with self._lock:
            if key not in self._limiters:
                self._limiters[key] = RateLimiter(self.rate, self.burst_size)
        
        return await self._limiters[key].acquire(tokens)


# =============================================================================
# Connection Pooling
# =============================================================================

class ConnectionPool(Generic[T]):
    """
    Generic async connection pool.
    
    Usage:
        >>> pool = ConnectionPool(
        ...     create_fn=create_connection,
        ...     max_size=10,
        ... )
        >>> 
        >>> async with pool.acquire() as conn:
        ...     await conn.execute(...)
    """
    
    def __init__(
        self,
        create_fn: Callable[[], Awaitable[T]],
        close_fn: Optional[Callable[[T], Awaitable[None]]] = None,
        validate_fn: Optional[Callable[[T], Awaitable[bool]]] = None,
        max_size: int = 10,
        min_size: int = 1,
        max_idle_seconds: float = 300.0,
    ):
        self._create_fn = create_fn
        self._close_fn = close_fn
        self._validate_fn = validate_fn
        self.max_size = max_size
        self.min_size = min_size
        self.max_idle_seconds = max_idle_seconds
        
        self._pool: asyncio.Queue[Tuple[T, float]] = asyncio.Queue(maxsize=max_size)
        self._size = 0
        self._lock = asyncio.Lock()
        self._closed = False
    
    async def _create_connection(self) -> T:
        """Create a new connection."""
        conn = await self._create_fn()
        async with self._lock:
            self._size += 1
        return conn
    
    async def _close_connection(self, conn: T):
        """Close a connection."""
        if self._close_fn:
            await self._close_fn(conn)
        async with self._lock:
            self._size -= 1
    
    async def _validate_connection(self, conn: T) -> bool:
        """Validate a connection is still usable."""
        if self._validate_fn:
            return await self._validate_fn(conn)
        return True
    
    @asynccontextmanager
    async def acquire(self) -> AsyncGenerator[T, None]:
        """Acquire a connection from the pool."""
        if self._closed:
            raise RuntimeError("Pool is closed")
        
        conn = None
        
        # Try to get from pool
        while not self._pool.empty():
            try:
                conn, timestamp = self._pool.get_nowait()
                
                # Check if too old
                if time.time() - timestamp > self.max_idle_seconds:
                    await self._close_connection(conn)
                    conn = None
                    continue
                
                # Validate
                if not await self._validate_connection(conn):
                    await self._close_connection(conn)
                    conn = None
                    continue
                
                break
            except asyncio.QueueEmpty:
                break
        
        # Create new if needed
        if conn is None:
            async with self._lock:
                if self._size >= self.max_size:
                    # Wait for one to become available
                    conn, _ = await self._pool.get()
                else:
                    conn = await self._create_connection()
        
        try:
            yield conn
        finally:
            # Return to pool
            if not self._closed:
                try:
                    self._pool.put_nowait((conn, time.time()))
                except asyncio.QueueFull:
                    await self._close_connection(conn)
    
    async def close(self):
        """Close all connections in the pool."""
        self._closed = True
        
        while not self._pool.empty():
            try:
                conn, _ = self._pool.get_nowait()
                await self._close_connection(conn)
            except asyncio.QueueEmpty:
                break


# =============================================================================
# Caching with TTL
# =============================================================================

@dataclass
class CacheEntry(Generic[T]):
    """A cache entry with metadata."""
    value: T
    created_at: float
    expires_at: Optional[float]
    hits: int = 0


class AsyncCache(Generic[T]):
    """
    Async cache with TTL support.
    
    Usage:
        >>> cache = AsyncCache(default_ttl=300)
        >>> await cache.set("key", "value")
        >>> value = await cache.get("key")
    """
    
    def __init__(
        self,
        default_ttl: Optional[float] = None,
        max_size: int = 1000,
    ):
        self.default_ttl = default_ttl
        self.max_size = max_size
        self._cache: Dict[str, CacheEntry[T]] = {}
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[T]:
        """Get value from cache."""
        async with self._lock:
            entry = self._cache.get(key)
            
            if entry is None:
                return None
            
            # Check expiration
            if entry.expires_at and time.time() > entry.expires_at:
                del self._cache[key]
                return None
            
            entry.hits += 1
            return entry.value
    
    async def set(
        self,
        key: str,
        value: T,
        ttl: Optional[float] = None,
    ):
        """Set value in cache."""
        async with self._lock:
            # Evict if at max size
            if len(self._cache) >= self.max_size and key not in self._cache:
                # Remove oldest entry
                oldest_key = min(
                    self._cache.keys(),
                    key=lambda k: self._cache[k].created_at,
                )
                del self._cache[oldest_key]
            
            ttl = ttl or self.default_ttl
            expires_at = time.time() + ttl if ttl else None
            
            self._cache[key] = CacheEntry(
                value=value,
                created_at=time.time(),
                expires_at=expires_at,
            )
    
    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    async def clear(self):
        """Clear all cached values."""
        async with self._lock:
            self._cache.clear()
    
    def cache_key(self, *args, **kwargs) -> str:
        """Generate cache key from arguments."""
        data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True)
        return hashlib.md5(data.encode()).hexdigest()


def cached(
    ttl: Optional[float] = 300,
    key_fn: Optional[Callable[..., str]] = None,
):
    """
    Decorator for caching async function results.
    
    Args:
        ttl: Time to live in seconds
        key_fn: Function to generate cache key
        
    Usage:
        >>> @cached(ttl=60)
        >>> async def expensive_operation(x: int) -> str:
        ...     # Expensive computation
        ...     return result
    """
    cache: AsyncCache[Any] = AsyncCache(default_ttl=ttl)
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate key
            if key_fn:
                key = key_fn(*args, **kwargs)
            else:
                key = cache.cache_key(*args, **kwargs)
            
            # Check cache
            cached_value = await cache.get(key)
            if cached_value is not None:
                return cached_value
            
            # Execute and cache
            result = await func(*args, **kwargs)
            await cache.set(key, result)
            return result
        
        # Expose cache for manual operations
        wrapper.cache = cache
        return wrapper
    
    return decorator


# =============================================================================
# Structured Logging
# =============================================================================

@dataclass
class LogContext:
    """Context for structured logging."""
    operation: str
    request_id: Optional[str] = None
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class StructuredLogger:
    """
    Structured logger for enterprise applications.
    
    Usage:
        >>> logger = StructuredLogger("my-service")
        >>> logger.info("Operation complete", duration=1.5, items=100)
    """
    
    def __init__(self, name: str):
        self._logger = logging.getLogger(name)
        self._context: Optional[LogContext] = None
    
    def set_context(self, context: LogContext):
        """Set logging context."""
        self._context = context
    
    def _format_message(
        self,
        message: str,
        **extra,
    ) -> Dict[str, Any]:
        """Format message with context."""
        data = {
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
            **extra,
        }
        
        if self._context:
            data.update({
                "operation": self._context.operation,
                "request_id": self._context.request_id,
                "user_id": self._context.user_id,
                "tenant_id": self._context.tenant_id,
                **self._context.metadata,
            })
        
        return data
    
    def debug(self, message: str, **extra):
        data = self._format_message(message, level="DEBUG", **extra)
        self._logger.debug(json.dumps(data))
    
    def info(self, message: str, **extra):
        data = self._format_message(message, level="INFO", **extra)
        self._logger.info(json.dumps(data))
    
    def warning(self, message: str, **extra):
        data = self._format_message(message, level="WARNING", **extra)
        self._logger.warning(json.dumps(data))
    
    def error(self, message: str, **extra):
        data = self._format_message(message, level="ERROR", **extra)
        self._logger.error(json.dumps(data))
    
    def critical(self, message: str, **extra):
        data = self._format_message(message, level="CRITICAL", **extra)
        self._logger.critical(json.dumps(data))


# =============================================================================
# Health Checks
# =============================================================================

class HealthStatus(Enum):
    """Health check status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class HealthCheckResult:
    """Result of a health check."""
    name: str
    status: HealthStatus
    message: str = ""
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class HealthChecker:
    """
    Health checker for monitoring component status.
    
    Usage:
        >>> checker = HealthChecker()
        >>> checker.register("database", check_database_health)
        >>> result = await checker.check_all()
    """
    
    def __init__(self):
        self._checks: Dict[str, Callable[[], Awaitable[HealthCheckResult]]] = {}
    
    def register(
        self,
        name: str,
        check_fn: Callable[[], Awaitable[HealthCheckResult]],
    ):
        """Register a health check."""
        self._checks[name] = check_fn
    
    async def check(self, name: str) -> HealthCheckResult:
        """Run a specific health check."""
        if name not in self._checks:
            return HealthCheckResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=f"Health check '{name}' not found",
            )
        
        start = time.time()
        try:
            result = await self._checks[name]()
            result.duration_ms = (time.time() - start) * 1000
            return result
        except Exception as e:
            return HealthCheckResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=str(e),
                duration_ms=(time.time() - start) * 1000,
            )
    
    async def check_all(self) -> Dict[str, HealthCheckResult]:
        """Run all health checks."""
        results = {}
        for name in self._checks:
            results[name] = await self.check(name)
        return results
    
    async def is_healthy(self) -> bool:
        """Check if all components are healthy."""
        results = await self.check_all()
        return all(r.status == HealthStatus.HEALTHY for r in results.values())


# =============================================================================
# Metrics Collection
# =============================================================================

@dataclass
class MetricValue:
    """A metric value."""
    name: str
    value: float
    timestamp: float
    labels: Dict[str, str] = field(default_factory=dict)


class MetricsCollector:
    """
    Metrics collector for monitoring.
    
    Usage:
        >>> metrics = MetricsCollector()
        >>> metrics.increment("requests_total", labels={"method": "GET"})
        >>> metrics.gauge("queue_size", 42)
        >>> metrics.histogram("request_duration", 0.5)
    """
    
    def __init__(self):
        self._counters: Dict[str, float] = defaultdict(float)
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = defaultdict(list)
        self._lock = asyncio.Lock()
    
    def _make_key(self, name: str, labels: Dict[str, str]) -> str:
        """Make a unique key for a metric."""
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"
    
    async def increment(
        self,
        name: str,
        value: float = 1.0,
        labels: Optional[Dict[str, str]] = None,
    ):
        """Increment a counter."""
        key = self._make_key(name, labels or {})
        async with self._lock:
            self._counters[key] += value
    
    async def gauge(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
    ):
        """Set a gauge value."""
        key = self._make_key(name, labels or {})
        async with self._lock:
            self._gauges[key] = value
    
    async def histogram(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
    ):
        """Record a histogram value."""
        key = self._make_key(name, labels or {})
        async with self._lock:
            self._histograms[key].append(value)
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get all metrics."""
        async with self._lock:
            return {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histograms": {
                    k: {
                        "count": len(v),
                        "sum": sum(v),
                        "min": min(v) if v else 0,
                        "max": max(v) if v else 0,
                        "avg": sum(v) / len(v) if v else 0,
                    }
                    for k, v in self._histograms.items()
                },
            }


# Global instances
metrics = MetricsCollector()
health_checker = HealthChecker()
