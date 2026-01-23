"""
Enterprise Retry Module.

Provides exponential backoff, jitter, and configurable retry policies
for resilient operations.

Example:
    @retry(max_attempts=3, backoff=exponential_backoff(base=1.0))
    async def call_api(data: dict) -> dict:
        return await api.request(data)
    
    # Custom policy
    policy = RetryPolicy(
        max_attempts=5,
        backoff=ExponentialBackoff(base=1.0, max_delay=60.0),
        retry_on=(ConnectionError, TimeoutError),
    )
    
    async with Retrier(policy) as retrier:
        result = await retrier.execute(risky_operation)
"""

from __future__ import annotations

import asyncio
import random
import time
import logging
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
    Tuple,
    Type,
    TypeVar,
    Union,
)
from functools import wraps
from enum import Enum

logger = logging.getLogger(__name__)

T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])


class RetryExhausted(Exception):
    """Raised when all retry attempts are exhausted."""
    
    def __init__(
        self,
        message: str = "All retry attempts exhausted",
        attempts: int = 0,
        last_exception: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.attempts = attempts
        self.last_exception = last_exception


@dataclass
class RetryAttempt:
    """Information about a retry attempt."""
    attempt_number: int
    start_time: float
    end_time: Optional[float] = None
    success: bool = False
    exception: Optional[Exception] = None
    delay_before: float = 0.0
    
    @property
    def duration(self) -> Optional[float]:
        """Get attempt duration in seconds."""
        if self.end_time:
            return self.end_time - self.start_time
        return None


@dataclass
class RetryStats:
    """Statistics for retry operations."""
    total_attempts: int = 0
    successful_attempts: int = 0
    failed_attempts: int = 0
    total_delay: float = 0.0
    attempts: List[RetryAttempt] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_attempts": self.total_attempts,
            "successful_attempts": self.successful_attempts,
            "failed_attempts": self.failed_attempts,
            "total_delay": self.total_delay,
            "success_rate": self.successful_attempts / max(1, self.total_attempts),
        }


class BackoffStrategy(ABC):
    """Abstract base class for backoff strategies."""
    
    @abstractmethod
    def get_delay(self, attempt: int) -> float:
        """
        Get delay in seconds for a given attempt number.
        
        Args:
            attempt: Current attempt number (1-based)
            
        Returns:
            Delay in seconds before next retry
        """
        pass
    
    def with_jitter(self, jitter_factor: float = 0.1) -> 'JitteredBackoff':
        """Add jitter to this backoff strategy."""
        return JitteredBackoff(self, jitter_factor)


class ConstantBackoff(BackoffStrategy):
    """Constant delay between retries."""
    
    def __init__(self, delay: float = 1.0):
        """
        Initialize constant backoff.
        
        Args:
            delay: Constant delay in seconds
        """
        self.delay = delay
    
    def get_delay(self, attempt: int) -> float:
        """Get constant delay."""
        return self.delay


class LinearBackoff(BackoffStrategy):
    """Linear increase in delay between retries."""
    
    def __init__(
        self,
        initial: float = 1.0,
        increment: float = 1.0,
        max_delay: float = 60.0,
    ):
        """
        Initialize linear backoff.
        
        Args:
            initial: Initial delay in seconds
            increment: Delay increment per attempt
            max_delay: Maximum delay cap
        """
        self.initial = initial
        self.increment = increment
        self.max_delay = max_delay
    
    def get_delay(self, attempt: int) -> float:
        """Get linear delay."""
        delay = self.initial + (attempt - 1) * self.increment
        return min(delay, self.max_delay)


class ExponentialBackoff(BackoffStrategy):
    """Exponential increase in delay between retries."""
    
    def __init__(
        self,
        base: float = 1.0,
        multiplier: float = 2.0,
        max_delay: float = 60.0,
    ):
        """
        Initialize exponential backoff.
        
        Args:
            base: Base delay in seconds
            multiplier: Multiplier per attempt
            max_delay: Maximum delay cap
        """
        self.base = base
        self.multiplier = multiplier
        self.max_delay = max_delay
    
    def get_delay(self, attempt: int) -> float:
        """Get exponential delay."""
        delay = self.base * (self.multiplier ** (attempt - 1))
        return min(delay, self.max_delay)


class FibonacciBackoff(BackoffStrategy):
    """Fibonacci sequence delay between retries."""
    
    def __init__(
        self,
        base: float = 1.0,
        max_delay: float = 60.0,
    ):
        """
        Initialize Fibonacci backoff.
        
        Args:
            base: Base unit in seconds
            max_delay: Maximum delay cap
        """
        self.base = base
        self.max_delay = max_delay
        self._cache: Dict[int, int] = {1: 1, 2: 1}
    
    def _fibonacci(self, n: int) -> int:
        """Calculate Fibonacci number with caching."""
        if n in self._cache:
            return self._cache[n]
        result = self._fibonacci(n - 1) + self._fibonacci(n - 2)
        self._cache[n] = result
        return result
    
    def get_delay(self, attempt: int) -> float:
        """Get Fibonacci delay."""
        delay = self.base * self._fibonacci(attempt)
        return min(delay, self.max_delay)


class JitteredBackoff(BackoffStrategy):
    """Backoff with random jitter."""
    
    def __init__(
        self,
        base_strategy: BackoffStrategy,
        jitter_factor: float = 0.1,
    ):
        """
        Initialize jittered backoff.
        
        Args:
            base_strategy: Underlying backoff strategy
            jitter_factor: Jitter as fraction of delay (0-1)
        """
        self.base_strategy = base_strategy
        self.jitter_factor = jitter_factor
    
    def get_delay(self, attempt: int) -> float:
        """Get delay with jitter."""
        base_delay = self.base_strategy.get_delay(attempt)
        jitter = base_delay * self.jitter_factor * random.random()
        return base_delay + jitter


class DecorrelatedJitterBackoff(BackoffStrategy):
    """
    Decorrelated jitter backoff (AWS recommended).
    
    Each delay is randomly chosen between base and 3x the previous delay.
    """
    
    def __init__(
        self,
        base: float = 1.0,
        max_delay: float = 60.0,
    ):
        """
        Initialize decorrelated jitter backoff.
        
        Args:
            base: Base delay in seconds
            max_delay: Maximum delay cap
        """
        self.base = base
        self.max_delay = max_delay
        self._last_delay: float = base
    
    def get_delay(self, attempt: int) -> float:
        """Get decorrelated jitter delay."""
        if attempt == 1:
            self._last_delay = self.base
            return self.base
        
        delay = random.uniform(self.base, self._last_delay * 3)
        delay = min(delay, self.max_delay)
        self._last_delay = delay
        return delay


@dataclass
class RetryPolicy:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    backoff: BackoffStrategy = field(default_factory=lambda: ExponentialBackoff())
    retry_on: Tuple[Type[Exception], ...] = (Exception,)
    retry_if: Optional[Callable[[Exception], bool]] = None
    on_retry: Optional[Callable[[int, Exception, float], None]] = None
    on_success: Optional[Callable[[int], None]] = None
    on_failure: Optional[Callable[[int, Exception], None]] = None
    timeout: Optional[float] = None
    
    def should_retry(self, exception: Exception, attempt: int) -> bool:
        """Check if operation should be retried."""
        if attempt >= self.max_attempts:
            return False
        
        if not isinstance(exception, self.retry_on):
            return False
        
        if self.retry_if is not None:
            return self.retry_if(exception)
        
        return True


class Retrier:
    """
    Retrier for executing operations with retry logic.
    """
    
    def __init__(
        self,
        policy: Optional[RetryPolicy] = None,
        **kwargs: Any,
    ):
        """
        Initialize retrier.
        
        Args:
            policy: Retry policy to use
            **kwargs: Override policy attributes
        """
        self.policy = policy or RetryPolicy()
        
        # Apply overrides
        for key, value in kwargs.items():
            if hasattr(self.policy, key):
                setattr(self.policy, key, value)
        
        self._stats = RetryStats()
    
    @property
    def stats(self) -> RetryStats:
        """Get retry statistics."""
        return self._stats
    
    async def execute(
        self,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        Execute function with retry logic.
        
        Args:
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Function result
            
        Raises:
            RetryExhausted: If all attempts fail
        """
        last_exception: Optional[Exception] = None
        
        for attempt in range(1, self.policy.max_attempts + 1):
            attempt_info = RetryAttempt(
                attempt_number=attempt,
                start_time=time.time(),
            )
            
            try:
                # Execute with optional timeout
                if asyncio.iscoroutinefunction(func):
                    if self.policy.timeout:
                        result = await asyncio.wait_for(
                            func(*args, **kwargs),
                            timeout=self.policy.timeout,
                        )
                    else:
                        result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                # Success
                attempt_info.end_time = time.time()
                attempt_info.success = True
                self._stats.attempts.append(attempt_info)
                self._stats.total_attempts += 1
                self._stats.successful_attempts += 1
                
                if self.policy.on_success:
                    self.policy.on_success(attempt)
                
                return result
            
            except Exception as e:
                attempt_info.end_time = time.time()
                attempt_info.exception = e
                self._stats.attempts.append(attempt_info)
                self._stats.total_attempts += 1
                self._stats.failed_attempts += 1
                last_exception = e
                
                if not self.policy.should_retry(e, attempt):
                    if self.policy.on_failure:
                        self.policy.on_failure(attempt, e)
                    raise
                
                # Calculate delay
                delay = self.policy.backoff.get_delay(attempt)
                self._stats.total_delay += delay
                
                if self.policy.on_retry:
                    self.policy.on_retry(attempt, e, delay)
                
                logger.warning(
                    f"Attempt {attempt} failed: {e}. "
                    f"Retrying in {delay:.2f}s..."
                )
                
                await asyncio.sleep(delay)
        
        # All attempts exhausted
        if self.policy.on_failure:
            self.policy.on_failure(self.policy.max_attempts, last_exception)
        
        raise RetryExhausted(
            f"Failed after {self.policy.max_attempts} attempts",
            attempts=self.policy.max_attempts,
            last_exception=last_exception,
        )
    
    def execute_sync(
        self,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        Execute function synchronously with retry logic.
        
        Args:
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Function result
        """
        last_exception: Optional[Exception] = None
        
        for attempt in range(1, self.policy.max_attempts + 1):
            attempt_info = RetryAttempt(
                attempt_number=attempt,
                start_time=time.time(),
            )
            
            try:
                result = func(*args, **kwargs)
                
                attempt_info.end_time = time.time()
                attempt_info.success = True
                self._stats.attempts.append(attempt_info)
                self._stats.total_attempts += 1
                self._stats.successful_attempts += 1
                
                if self.policy.on_success:
                    self.policy.on_success(attempt)
                
                return result
            
            except Exception as e:
                attempt_info.end_time = time.time()
                attempt_info.exception = e
                self._stats.attempts.append(attempt_info)
                self._stats.total_attempts += 1
                self._stats.failed_attempts += 1
                last_exception = e
                
                if not self.policy.should_retry(e, attempt):
                    if self.policy.on_failure:
                        self.policy.on_failure(attempt, e)
                    raise
                
                delay = self.policy.backoff.get_delay(attempt)
                self._stats.total_delay += delay
                
                if self.policy.on_retry:
                    self.policy.on_retry(attempt, e, delay)
                
                logger.warning(
                    f"Attempt {attempt} failed: {e}. "
                    f"Retrying in {delay:.2f}s..."
                )
                
                time.sleep(delay)
        
        if self.policy.on_failure:
            self.policy.on_failure(self.policy.max_attempts, last_exception)
        
        raise RetryExhausted(
            f"Failed after {self.policy.max_attempts} attempts",
            attempts=self.policy.max_attempts,
            last_exception=last_exception,
        )
    
    async def __aenter__(self) -> 'Retrier':
        """Enter async context."""
        return self
    
    async def __aexit__(self, *args) -> None:
        """Exit async context."""
        pass
    
    def __enter__(self) -> 'Retrier':
        """Enter sync context."""
        return self
    
    def __exit__(self, *args) -> None:
        """Exit sync context."""
        pass


def retry(
    max_attempts: int = 3,
    backoff: Optional[BackoffStrategy] = None,
    retry_on: Tuple[Type[Exception], ...] = (Exception,),
    retry_if: Optional[Callable[[Exception], bool]] = None,
    on_retry: Optional[Callable[[int, Exception, float], None]] = None,
    timeout: Optional[float] = None,
) -> Callable[[F], F]:
    """
    Decorator for adding retry logic to functions.
    
    Args:
        max_attempts: Maximum number of attempts
        backoff: Backoff strategy (default: exponential)
        retry_on: Exception types to retry
        retry_if: Function to determine if exception should be retried
        on_retry: Callback on each retry
        timeout: Timeout per attempt in seconds
        
    Returns:
        Decorated function
        
    Example:
        @retry(max_attempts=3, retry_on=(ConnectionError,))
        async def fetch_data(url: str) -> dict:
            return await http.get(url)
    """
    if backoff is None:
        backoff = ExponentialBackoff()
    
    policy = RetryPolicy(
        max_attempts=max_attempts,
        backoff=backoff,
        retry_on=retry_on,
        retry_if=retry_if,
        on_retry=on_retry,
        timeout=timeout,
    )
    
    def decorator(func: F) -> F:
        retrier = Retrier(policy)
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await retrier.execute(func, *args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            return retrier.execute_sync(func, *args, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


def retry_with_backoff(
    backoff_type: str = "exponential",
    **kwargs: Any,
) -> Callable[[F], F]:
    """
    Decorator with named backoff type.
    
    Args:
        backoff_type: One of "constant", "linear", "exponential", "fibonacci"
        **kwargs: Arguments for the backoff and retry policy
        
    Returns:
        Decorated function
    """
    backoff_map = {
        "constant": ConstantBackoff,
        "linear": LinearBackoff,
        "exponential": ExponentialBackoff,
        "fibonacci": FibonacciBackoff,
    }
    
    backoff_cls = backoff_map.get(backoff_type, ExponentialBackoff)
    
    # Extract backoff-specific args
    backoff_args = {}
    if "base" in kwargs:
        backoff_args["base"] = kwargs.pop("base")
    if "max_delay" in kwargs:
        backoff_args["max_delay"] = kwargs.pop("max_delay")
    if "delay" in kwargs and backoff_type == "constant":
        backoff_args["delay"] = kwargs.pop("delay")
    if "multiplier" in kwargs and backoff_type == "exponential":
        backoff_args["multiplier"] = kwargs.pop("multiplier")
    
    backoff = backoff_cls(**backoff_args)
    
    # Add jitter if requested
    if kwargs.pop("jitter", False):
        jitter_factor = kwargs.pop("jitter_factor", 0.1)
        backoff = backoff.with_jitter(jitter_factor)
    
    return retry(backoff=backoff, **kwargs)


# Convenience backoff factory functions
def constant_backoff(delay: float = 1.0) -> ConstantBackoff:
    """Create constant backoff."""
    return ConstantBackoff(delay)


def linear_backoff(
    initial: float = 1.0,
    increment: float = 1.0,
    max_delay: float = 60.0,
) -> LinearBackoff:
    """Create linear backoff."""
    return LinearBackoff(initial, increment, max_delay)


def exponential_backoff(
    base: float = 1.0,
    multiplier: float = 2.0,
    max_delay: float = 60.0,
) -> ExponentialBackoff:
    """Create exponential backoff."""
    return ExponentialBackoff(base, multiplier, max_delay)


def fibonacci_backoff(
    base: float = 1.0,
    max_delay: float = 60.0,
) -> FibonacciBackoff:
    """Create Fibonacci backoff."""
    return FibonacciBackoff(base, max_delay)


def decorrelated_jitter_backoff(
    base: float = 1.0,
    max_delay: float = 60.0,
) -> DecorrelatedJitterBackoff:
    """Create decorrelated jitter backoff."""
    return DecorrelatedJitterBackoff(base, max_delay)


class RetryMiddleware:
    """
    Middleware for adding retry support to agent pipelines.
    """
    
    def __init__(
        self,
        policy: Optional[RetryPolicy] = None,
        **kwargs: Any,
    ):
        """
        Initialize middleware.
        
        Args:
            policy: Retry policy to use
            **kwargs: Override policy attributes
        """
        self.retrier = Retrier(policy, **kwargs)
    
    async def __call__(
        self,
        context: Dict[str, Any],
        next_handler: Callable[[Dict[str, Any]], Any],
    ) -> Any:
        """Process request with retry logic."""
        context["retry_stats"] = {}
        
        result = await self.retrier.execute(next_handler, context)
        
        context["retry_stats"] = self.retrier.stats.to_dict()
        
        return result


# Predefined retry policies
class RetryPolicies:
    """Collection of predefined retry policies."""
    
    @staticmethod
    def default() -> RetryPolicy:
        """Default retry policy (3 attempts, exponential backoff)."""
        return RetryPolicy(
            max_attempts=3,
            backoff=ExponentialBackoff(base=1.0, max_delay=30.0),
        )
    
    @staticmethod
    def aggressive() -> RetryPolicy:
        """Aggressive retry (5 attempts, short delays)."""
        return RetryPolicy(
            max_attempts=5,
            backoff=ExponentialBackoff(base=0.5, multiplier=1.5, max_delay=10.0),
        )
    
    @staticmethod
    def conservative() -> RetryPolicy:
        """Conservative retry (3 attempts, longer delays)."""
        return RetryPolicy(
            max_attempts=3,
            backoff=ExponentialBackoff(base=2.0, multiplier=2.0, max_delay=60.0),
        )
    
    @staticmethod
    def network() -> RetryPolicy:
        """Policy optimized for network operations."""
        return RetryPolicy(
            max_attempts=5,
            backoff=DecorrelatedJitterBackoff(base=1.0, max_delay=30.0),
            retry_on=(ConnectionError, TimeoutError, OSError),
        )
    
    @staticmethod
    def api() -> RetryPolicy:
        """Policy for API calls (handles rate limits)."""
        def should_retry(e: Exception) -> bool:
            # Retry on specific HTTP status codes
            if hasattr(e, "status_code"):
                return e.status_code in (429, 500, 502, 503, 504)
            return True
        
        return RetryPolicy(
            max_attempts=5,
            backoff=ExponentialBackoff(base=1.0, max_delay=60.0).with_jitter(0.2),
            retry_if=should_retry,
        )
    
    @staticmethod
    def no_retry() -> RetryPolicy:
        """No retry policy."""
        return RetryPolicy(max_attempts=1)


__all__ = [
    # Exceptions
    "RetryExhausted",
    # Data classes
    "RetryAttempt",
    "RetryStats",
    "RetryPolicy",
    # Backoff strategies
    "BackoffStrategy",
    "ConstantBackoff",
    "LinearBackoff",
    "ExponentialBackoff",
    "FibonacciBackoff",
    "JitteredBackoff",
    "DecorrelatedJitterBackoff",
    # Retrier
    "Retrier",
    # Middleware
    "RetryMiddleware",
    # Decorator
    "retry",
    "retry_with_backoff",
    # Factory functions
    "constant_backoff",
    "linear_backoff",
    "exponential_backoff",
    "fibonacci_backoff",
    "decorrelated_jitter_backoff",
    # Predefined policies
    "RetryPolicies",
]
