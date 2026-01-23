"""
Enterprise Timeout Module.

Provides request timeouts, deadline propagation, and cancellation tokens
for controlled execution with time limits.

Example:
    # Simple timeout
    @timeout(seconds=30)
    async def slow_operation():
        ...
    
    # Deadline propagation
    deadline = Deadline.from_now(seconds=60)
    async with deadline.scope():
        await operation1()  # Uses remaining time
        await operation2()  # Timeout if deadline passed
    
    # Cancellation tokens
    token = CancellationToken()
    task = asyncio.create_task(long_running(token))
    token.cancel()  # Graceful cancellation
"""

from __future__ import annotations

import asyncio
import time
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    TypeVar,
    Union,
)
from contextlib import asynccontextmanager, contextmanager
from functools import wraps
from enum import Enum
import logging

logger = logging.getLogger(__name__)

T = TypeVar("T")


class TimeoutError(Exception):
    """Operation timed out."""
    
    def __init__(
        self,
        message: str = "Operation timed out",
        elapsed: Optional[float] = None,
        deadline: Optional[float] = None,
    ):
        super().__init__(message)
        self.elapsed = elapsed
        self.deadline = deadline


class CancellationError(Exception):
    """Operation was cancelled."""
    pass


class DeadlineExceeded(TimeoutError):
    """Deadline has been exceeded."""
    pass


class TimeoutStrategy(str, Enum):
    """Timeout handling strategies."""
    CANCEL = "cancel"  # Cancel the operation
    INTERRUPT = "interrupt"  # Send interrupt signal
    IGNORE = "ignore"  # Log but don't raise


@dataclass
class TimeoutConfig:
    """Configuration for timeout behavior."""
    seconds: float
    strategy: TimeoutStrategy = TimeoutStrategy.CANCEL
    on_timeout: Optional[Callable[[float], None]] = None
    message: str = "Operation timed out"


class CancellationToken:
    """
    Token for cooperative cancellation.
    """
    
    def __init__(self):
        self._cancelled = False
        self._callbacks: List[Callable[[], None]] = []
        self._lock = threading.Lock()
    
    @property
    def is_cancelled(self) -> bool:
        """Check if cancellation was requested."""
        return self._cancelled
    
    def cancel(self) -> None:
        """Request cancellation."""
        with self._lock:
            if self._cancelled:
                return
            
            self._cancelled = True
            
            for callback in self._callbacks:
                try:
                    callback()
                except Exception as e:
                    logger.error(f"Cancellation callback error: {e}")
    
    def register_callback(self, callback: Callable[[], None]) -> None:
        """Register a callback for cancellation."""
        with self._lock:
            if self._cancelled:
                callback()
            else:
                self._callbacks.append(callback)
    
    def throw_if_cancelled(self) -> None:
        """Raise CancellationError if cancelled."""
        if self._cancelled:
            raise CancellationError("Operation was cancelled")
    
    async def wait_for_cancellation(self) -> None:
        """Wait until cancelled."""
        while not self._cancelled:
            await asyncio.sleep(0.1)
    
    @classmethod
    def create_linked(cls, *tokens: 'CancellationToken') -> 'CancellationToken':
        """Create a token that cancels when any parent cancels."""
        linked = cls()
        
        for token in tokens:
            token.register_callback(linked.cancel)
        
        return linked


class CancellationTokenSource:
    """
    Source for creating and managing cancellation tokens.
    """
    
    def __init__(self, timeout: Optional[float] = None):
        """
        Initialize token source.
        
        Args:
            timeout: Optional automatic cancellation timeout
        """
        self._token = CancellationToken()
        self._timeout = timeout
        self._timer: Optional[threading.Timer] = None
        
        if timeout:
            self._start_timer()
    
    @property
    def token(self) -> CancellationToken:
        """Get the cancellation token."""
        return self._token
    
    def _start_timer(self) -> None:
        """Start the timeout timer."""
        if self._timeout:
            self._timer = threading.Timer(self._timeout, self.cancel)
            self._timer.daemon = True
            self._timer.start()
    
    def cancel(self) -> None:
        """Cancel the token."""
        self._token.cancel()
        if self._timer:
            self._timer.cancel()
    
    def dispose(self) -> None:
        """Clean up resources."""
        if self._timer:
            self._timer.cancel()


@dataclass
class Deadline:
    """
    Represents a deadline for operation completion.
    """
    timestamp: float
    created_at: float = field(default_factory=time.time)
    
    @classmethod
    def from_now(cls, seconds: float) -> 'Deadline':
        """Create deadline from now."""
        return cls(timestamp=time.time() + seconds)
    
    @classmethod
    def from_timestamp(cls, timestamp: float) -> 'Deadline':
        """Create deadline from timestamp."""
        return cls(timestamp=timestamp)
    
    @property
    def is_exceeded(self) -> bool:
        """Check if deadline is exceeded."""
        return time.time() > self.timestamp
    
    @property
    def remaining(self) -> float:
        """Get remaining time in seconds."""
        return max(0, self.timestamp - time.time())
    
    @property
    def elapsed(self) -> float:
        """Get elapsed time since creation."""
        return time.time() - self.created_at
    
    def extend(self, seconds: float) -> 'Deadline':
        """Create a new deadline extended by seconds."""
        return Deadline(
            timestamp=self.timestamp + seconds,
            created_at=self.created_at,
        )
    
    def check(self) -> None:
        """Raise if deadline exceeded."""
        if self.is_exceeded:
            raise DeadlineExceeded(
                f"Deadline exceeded by {-self.remaining:.2f}s",
                elapsed=self.elapsed,
                deadline=self.timestamp,
            )
    
    @asynccontextmanager
    async def scope(self):
        """
        Context manager that enforces the deadline.
        
        Example:
            async with deadline.scope():
                await operation()
        """
        self.check()
        
        try:
            yield self
        except asyncio.TimeoutError:
            raise DeadlineExceeded(
                f"Deadline exceeded",
                elapsed=self.elapsed,
                deadline=self.timestamp,
            )
    
    async def run(self, coro: Any) -> Any:
        """
        Run a coroutine with this deadline.
        
        Args:
            coro: Coroutine to run
            
        Returns:
            Result of coroutine
        """
        self.check()
        
        try:
            return await asyncio.wait_for(coro, timeout=self.remaining)
        except asyncio.TimeoutError:
            raise DeadlineExceeded(
                f"Deadline exceeded",
                elapsed=self.elapsed,
                deadline=self.timestamp,
            )


# Context variable for deadline propagation
_deadline_context: Dict[int, Deadline] = {}


def get_current_deadline() -> Optional[Deadline]:
    """Get the current context deadline."""
    task = asyncio.current_task()
    if task:
        return _deadline_context.get(id(task))
    return None


def set_current_deadline(deadline: Deadline) -> None:
    """Set the current context deadline."""
    task = asyncio.current_task()
    if task:
        _deadline_context[id(task)] = deadline


def clear_current_deadline() -> None:
    """Clear the current context deadline."""
    task = asyncio.current_task()
    if task:
        _deadline_context.pop(id(task), None)


@asynccontextmanager
async def deadline_scope(seconds: float):
    """
    Create a deadline scope.
    
    Example:
        async with deadline_scope(30):
            await operation()
    """
    deadline = Deadline.from_now(seconds)
    
    # Propagate to nested calls
    old = get_current_deadline()
    
    # Use the shorter deadline
    if old and old.remaining < deadline.remaining:
        deadline = old
    
    set_current_deadline(deadline)
    
    try:
        async with deadline.scope():
            yield deadline
    finally:
        if old:
            set_current_deadline(old)
        else:
            clear_current_deadline()


def timeout(
    seconds: float,
    strategy: TimeoutStrategy = TimeoutStrategy.CANCEL,
    on_timeout: Optional[Callable[[float], None]] = None,
) -> Callable:
    """
    Decorator for function timeout.
    
    Example:
        @timeout(30)
        async def slow_operation():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.time()
            
            try:
                return await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=seconds,
                )
            except asyncio.TimeoutError:
                elapsed = time.time() - start
                
                if on_timeout:
                    on_timeout(elapsed)
                
                if strategy == TimeoutStrategy.IGNORE:
                    logger.warning(
                        f"{func.__name__} timed out after {elapsed:.2f}s"
                    )
                    return None
                
                raise TimeoutError(
                    f"{func.__name__} timed out after {elapsed:.2f}s",
                    elapsed=elapsed,
                    deadline=start + seconds,
                )
        
        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            import concurrent.futures
            
            start = time.time()
            
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(func, *args, **kwargs)
                try:
                    return future.result(timeout=seconds)
                except concurrent.futures.TimeoutError:
                    elapsed = time.time() - start
                    
                    if on_timeout:
                        on_timeout(elapsed)
                    
                    if strategy == TimeoutStrategy.IGNORE:
                        logger.warning(
                            f"{func.__name__} timed out after {elapsed:.2f}s"
                        )
                        return None
                    
                    raise TimeoutError(
                        f"{func.__name__} timed out after {elapsed:.2f}s",
                        elapsed=elapsed,
                    )
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


def with_deadline(seconds: float) -> Callable:
    """
    Decorator that enforces a deadline.
    
    Example:
        @with_deadline(60)
        async def operation():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            async with deadline_scope(seconds):
                return await func(*args, **kwargs)
        
        return wrapper
    
    return decorator


def with_cancellation(token_arg: str = "token") -> Callable:
    """
    Decorator that supports cancellation.
    
    Example:
        @with_cancellation()
        async def operation(token: CancellationToken):
            while not token.is_cancelled:
                await do_work()
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            token = kwargs.get(token_arg)
            
            if token and isinstance(token, CancellationToken):
                # Check before starting
                token.throw_if_cancelled()
            
            return await func(*args, **kwargs)
        
        return wrapper
    
    return decorator


class TimeoutBudget:
    """
    Budget for distributing timeout across operations.
    """
    
    def __init__(self, total_seconds: float):
        """
        Initialize timeout budget.
        
        Args:
            total_seconds: Total time budget
        """
        self.total_seconds = total_seconds
        self._start_time = time.time()
        self._used: Dict[str, float] = {}
    
    @property
    def remaining(self) -> float:
        """Get remaining budget."""
        elapsed = time.time() - self._start_time
        return max(0, self.total_seconds - elapsed)
    
    @property
    def is_exhausted(self) -> bool:
        """Check if budget is exhausted."""
        return self.remaining <= 0
    
    def allocate(self, operation: str, fraction: float = 0.5) -> float:
        """
        Allocate a portion of remaining budget.
        
        Args:
            operation: Operation name for tracking
            fraction: Fraction of remaining to allocate (0-1)
            
        Returns:
            Allocated timeout in seconds
        """
        if self.is_exhausted:
            raise TimeoutError("Timeout budget exhausted")
        
        allocated = self.remaining * fraction
        self._used[operation] = allocated
        return allocated
    
    def check(self) -> None:
        """Raise if budget exhausted."""
        if self.is_exhausted:
            raise TimeoutError(
                f"Timeout budget exhausted after {self.total_seconds}s",
                elapsed=time.time() - self._start_time,
            )
    
    @asynccontextmanager
    async def operation(self, name: str, fraction: float = 0.5):
        """
        Context manager for a budgeted operation.
        
        Example:
            async with budget.operation("api_call", 0.3):
                await api.call()
        """
        timeout_seconds = self.allocate(name, fraction)
        start = time.time()
        
        try:
            yield timeout_seconds
        finally:
            elapsed = time.time() - start
            self._used[name] = elapsed


class AdaptiveTimeout:
    """
    Adaptive timeout based on historical data.
    """
    
    def __init__(
        self,
        initial: float = 30.0,
        min_timeout: float = 5.0,
        max_timeout: float = 120.0,
        percentile: float = 95.0,
    ):
        """
        Initialize adaptive timeout.
        
        Args:
            initial: Initial timeout
            min_timeout: Minimum timeout
            max_timeout: Maximum timeout
            percentile: Target percentile for timeout calculation
        """
        self.initial = initial
        self.min_timeout = min_timeout
        self.max_timeout = max_timeout
        self.percentile = percentile
        
        self._latencies: List[float] = []
        self._current = initial
    
    @property
    def current(self) -> float:
        """Get current timeout value."""
        return self._current
    
    def record(self, latency: float) -> None:
        """Record a latency observation."""
        self._latencies.append(latency)
        
        # Keep last 100 observations
        if len(self._latencies) > 100:
            self._latencies.pop(0)
        
        self._recalculate()
    
    def _recalculate(self) -> None:
        """Recalculate timeout based on observations."""
        if len(self._latencies) < 10:
            return
        
        sorted_latencies = sorted(self._latencies)
        index = int(len(sorted_latencies) * self.percentile / 100)
        percentile_latency = sorted_latencies[min(index, len(sorted_latencies) - 1)]
        
        # Add margin
        new_timeout = percentile_latency * 1.5
        
        self._current = max(
            self.min_timeout,
            min(self.max_timeout, new_timeout),
        )
    
    def __call__(self) -> float:
        """Get current timeout."""
        return self._current


async def race(*coros: Any, return_when: str = "FIRST_COMPLETED") -> Any:
    """
    Race multiple coroutines, return first to complete.
    
    Example:
        result = await race(
            fetch_from_primary(),
            fetch_from_secondary(),
        )
    """
    tasks = [asyncio.create_task(coro) for coro in coros]
    
    try:
        done, pending = await asyncio.wait(
            tasks,
            return_when=asyncio.FIRST_COMPLETED,
        )
        
        # Cancel remaining
        for task in pending:
            task.cancel()
        
        # Return first result
        for task in done:
            return task.result()
            
    except Exception:
        # Cancel all on error
        for task in tasks:
            task.cancel()
        raise


__all__ = [
    # Exceptions
    "TimeoutError",
    "CancellationError",
    "DeadlineExceeded",
    # Enums
    "TimeoutStrategy",
    # Data classes
    "TimeoutConfig",
    "Deadline",
    # Cancellation
    "CancellationToken",
    "CancellationTokenSource",
    # Budget
    "TimeoutBudget",
    "AdaptiveTimeout",
    # Decorators
    "timeout",
    "with_deadline",
    "with_cancellation",
    # Context managers
    "deadline_scope",
    # Utility functions
    "get_current_deadline",
    "set_current_deadline",
    "clear_current_deadline",
    "race",
]
