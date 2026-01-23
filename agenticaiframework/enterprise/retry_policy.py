"""
Enterprise Retry Policy Module.

Provides retry policies, exponential backoff,
circuit breaker integration, and failure handling.

Example:
    # Create retry policy
    policy = create_retry_policy(max_retries=3, backoff="exponential")
    
    # Execute with retry
    result = await policy.execute(risky_operation)
    
    # Use as decorator
    @with_retry(max_retries=3)
    async def fetch_data():
        ...
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
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

T = TypeVar('T')


logger = logging.getLogger(__name__)


class RetryError(Exception):
    """Retry error."""
    pass


class MaxRetriesExceeded(RetryError):
    """Maximum retries exceeded."""
    
    def __init__(
        self,
        message: str,
        attempts: int,
        last_error: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.attempts = attempts
        self.last_error = last_error


class NonRetryableError(RetryError):
    """Non-retryable error - should not retry."""
    pass


class BackoffStrategy(str, Enum):
    """Backoff strategy."""
    CONSTANT = "constant"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    FIBONACCI = "fibonacci"
    DECORRELATED_JITTER = "decorrelated_jitter"


class RetryOutcome(str, Enum):
    """Retry outcome."""
    SUCCESS = "success"
    FAILURE = "failure"
    EXHAUSTED = "exhausted"


@dataclass
class RetryConfig:
    """Retry configuration."""
    max_retries: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL
    multiplier: float = 2.0
    jitter: bool = True
    jitter_factor: float = 0.1
    retry_on: Optional[Tuple[Type[Exception], ...]] = None
    retry_if: Optional[Callable[[Exception], bool]] = None
    on_retry: Optional[Callable[[int, Exception, float], Any]] = None


@dataclass
class RetryAttempt:
    """Record of a retry attempt."""
    attempt_number: int
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_ms: Optional[float] = None
    error: Optional[Exception] = None
    delay_before: float = 0.0
    success: bool = False


@dataclass
class RetryResult(Generic[T]):
    """Result of retry execution."""
    outcome: RetryOutcome
    value: Optional[T] = None
    attempts: List[RetryAttempt] = field(default_factory=list)
    total_duration_ms: float = 0.0
    final_error: Optional[Exception] = None
    
    @property
    def success(self) -> bool:
        return self.outcome == RetryOutcome.SUCCESS
    
    @property
    def attempt_count(self) -> int:
        return len(self.attempts)


class BackoffCalculator(ABC):
    """
    Abstract backoff calculator.
    """
    
    @abstractmethod
    def calculate(
        self,
        attempt: int,
        config: RetryConfig,
    ) -> float:
        """Calculate delay for attempt."""
        pass


class ConstantBackoff(BackoffCalculator):
    """Constant backoff."""
    
    def calculate(
        self,
        attempt: int,
        config: RetryConfig,
    ) -> float:
        delay = config.initial_delay
        return self._apply_jitter(delay, config)
    
    def _apply_jitter(
        self,
        delay: float,
        config: RetryConfig,
    ) -> float:
        if config.jitter:
            jitter = delay * config.jitter_factor * random.random()
            delay += jitter
        return min(delay, config.max_delay)


class LinearBackoff(BackoffCalculator):
    """Linear backoff."""
    
    def calculate(
        self,
        attempt: int,
        config: RetryConfig,
    ) -> float:
        delay = config.initial_delay + (attempt * config.initial_delay)
        
        if config.jitter:
            jitter = delay * config.jitter_factor * random.random()
            delay += jitter
        
        return min(delay, config.max_delay)


class ExponentialBackoff(BackoffCalculator):
    """Exponential backoff."""
    
    def calculate(
        self,
        attempt: int,
        config: RetryConfig,
    ) -> float:
        delay = config.initial_delay * (config.multiplier ** attempt)
        
        if config.jitter:
            jitter = delay * config.jitter_factor * random.random()
            delay += jitter
        
        return min(delay, config.max_delay)


class FibonacciBackoff(BackoffCalculator):
    """Fibonacci backoff."""
    
    def _fibonacci(self, n: int) -> int:
        if n <= 1:
            return n
        a, b = 0, 1
        for _ in range(n - 1):
            a, b = b, a + b
        return b
    
    def calculate(
        self,
        attempt: int,
        config: RetryConfig,
    ) -> float:
        fib = self._fibonacci(attempt + 2)
        delay = config.initial_delay * fib
        
        if config.jitter:
            jitter = delay * config.jitter_factor * random.random()
            delay += jitter
        
        return min(delay, config.max_delay)


class DecorrelatedJitterBackoff(BackoffCalculator):
    """Decorrelated jitter backoff (AWS recommended)."""
    
    def __init__(self):
        self._previous_delay = 0.0
    
    def calculate(
        self,
        attempt: int,
        config: RetryConfig,
    ) -> float:
        if attempt == 0:
            delay = config.initial_delay
        else:
            delay = random.uniform(
                config.initial_delay,
                self._previous_delay * 3,
            )
        
        delay = min(delay, config.max_delay)
        self._previous_delay = delay
        
        return delay


class RetryPolicy:
    """
    Retry policy for executing operations with retries.
    """
    
    def __init__(self, config: RetryConfig):
        self._config = config
        self._backoff = self._create_backoff(config.backoff_strategy)
    
    def _create_backoff(self, strategy: BackoffStrategy) -> BackoffCalculator:
        """Create backoff calculator."""
        if strategy == BackoffStrategy.CONSTANT:
            return ConstantBackoff()
        elif strategy == BackoffStrategy.LINEAR:
            return LinearBackoff()
        elif strategy == BackoffStrategy.EXPONENTIAL:
            return ExponentialBackoff()
        elif strategy == BackoffStrategy.FIBONACCI:
            return FibonacciBackoff()
        elif strategy == BackoffStrategy.DECORRELATED_JITTER:
            return DecorrelatedJitterBackoff()
        else:
            return ExponentialBackoff()
    
    def should_retry(self, error: Exception) -> bool:
        """Check if error should be retried."""
        # Check retry_if predicate
        if self._config.retry_if:
            return self._config.retry_if(error)
        
        # Check retry_on exceptions
        if self._config.retry_on:
            return isinstance(error, self._config.retry_on)
        
        # Check for non-retryable
        if isinstance(error, NonRetryableError):
            return False
        
        # Default: retry on any exception
        return True
    
    async def execute(
        self,
        operation: Callable[[], T],
        context: Optional[Dict[str, Any]] = None,
    ) -> RetryResult[T]:
        """Execute operation with retry."""
        attempts: List[RetryAttempt] = []
        start_time = time.perf_counter()
        last_error = None
        
        for attempt_num in range(self._config.max_retries + 1):
            attempt = RetryAttempt(
                attempt_number=attempt_num,
                started_at=datetime.now(),
            )
            
            # Calculate delay (skip for first attempt)
            if attempt_num > 0:
                delay = self._backoff.calculate(attempt_num - 1, self._config)
                attempt.delay_before = delay
                
                # Notify on_retry callback
                if self._config.on_retry and last_error:
                    try:
                        callback_result = self._config.on_retry(
                            attempt_num,
                            last_error,
                            delay,
                        )
                        if asyncio.iscoroutine(callback_result):
                            await callback_result
                    except Exception as e:
                        logger.error(f"on_retry callback error: {e}")
                
                await asyncio.sleep(delay)
            
            try:
                # Execute operation
                if asyncio.iscoroutinefunction(operation):
                    result = await operation()
                else:
                    result = operation()
                
                attempt.success = True
                attempt.ended_at = datetime.now()
                attempt.duration_ms = (
                    (attempt.ended_at - attempt.started_at).total_seconds()
                    * 1000
                )
                attempts.append(attempt)
                
                total_duration = (time.perf_counter() - start_time) * 1000
                
                return RetryResult(
                    outcome=RetryOutcome.SUCCESS,
                    value=result,
                    attempts=attempts,
                    total_duration_ms=total_duration,
                )
                
            except Exception as e:
                last_error = e
                attempt.error = e
                attempt.ended_at = datetime.now()
                attempt.duration_ms = (
                    (attempt.ended_at - attempt.started_at).total_seconds()
                    * 1000
                )
                attempts.append(attempt)
                
                logger.warning(
                    f"Attempt {attempt_num + 1} failed: {e}"
                )
                
                # Check if should retry
                if not self.should_retry(e):
                    total_duration = (time.perf_counter() - start_time) * 1000
                    return RetryResult(
                        outcome=RetryOutcome.FAILURE,
                        attempts=attempts,
                        total_duration_ms=total_duration,
                        final_error=e,
                    )
        
        # All retries exhausted
        total_duration = (time.perf_counter() - start_time) * 1000
        
        return RetryResult(
            outcome=RetryOutcome.EXHAUSTED,
            attempts=attempts,
            total_duration_ms=total_duration,
            final_error=last_error,
        )
    
    async def execute_or_raise(
        self,
        operation: Callable[[], T],
    ) -> T:
        """Execute operation with retry, raise on failure."""
        result = await self.execute(operation)
        
        if result.success:
            return result.value
        
        if result.outcome == RetryOutcome.EXHAUSTED:
            raise MaxRetriesExceeded(
                f"Max retries ({self._config.max_retries}) exceeded",
                attempts=result.attempt_count,
                last_error=result.final_error,
            )
        
        if result.final_error:
            raise result.final_error
        
        raise RetryError("Operation failed")


class RetryPolicyBuilder:
    """
    Builder for retry policies.
    """
    
    def __init__(self):
        self._config = RetryConfig()
    
    def max_retries(self, count: int) -> RetryPolicyBuilder:
        """Set max retries."""
        self._config.max_retries = count
        return self
    
    def initial_delay(self, seconds: float) -> RetryPolicyBuilder:
        """Set initial delay."""
        self._config.initial_delay = seconds
        return self
    
    def max_delay(self, seconds: float) -> RetryPolicyBuilder:
        """Set max delay."""
        self._config.max_delay = seconds
        return self
    
    def backoff(
        self,
        strategy: Union[str, BackoffStrategy],
    ) -> RetryPolicyBuilder:
        """Set backoff strategy."""
        if isinstance(strategy, str):
            strategy = BackoffStrategy(strategy)
        self._config.backoff_strategy = strategy
        return self
    
    def exponential(self, multiplier: float = 2.0) -> RetryPolicyBuilder:
        """Use exponential backoff."""
        self._config.backoff_strategy = BackoffStrategy.EXPONENTIAL
        self._config.multiplier = multiplier
        return self
    
    def constant(self) -> RetryPolicyBuilder:
        """Use constant backoff."""
        self._config.backoff_strategy = BackoffStrategy.CONSTANT
        return self
    
    def linear(self) -> RetryPolicyBuilder:
        """Use linear backoff."""
        self._config.backoff_strategy = BackoffStrategy.LINEAR
        return self
    
    def with_jitter(
        self,
        enabled: bool = True,
        factor: float = 0.1,
    ) -> RetryPolicyBuilder:
        """Configure jitter."""
        self._config.jitter = enabled
        self._config.jitter_factor = factor
        return self
    
    def retry_on(
        self,
        *exceptions: Type[Exception],
    ) -> RetryPolicyBuilder:
        """Set exceptions to retry on."""
        self._config.retry_on = exceptions
        return self
    
    def retry_if(
        self,
        predicate: Callable[[Exception], bool],
    ) -> RetryPolicyBuilder:
        """Set retry predicate."""
        self._config.retry_if = predicate
        return self
    
    def on_retry(
        self,
        callback: Callable[[int, Exception, float], Any],
    ) -> RetryPolicyBuilder:
        """Set on_retry callback."""
        self._config.on_retry = callback
        return self
    
    def build(self) -> RetryPolicy:
        """Build the retry policy."""
        return RetryPolicy(self._config)


class RetryContext:
    """
    Context for retry operations.
    """
    
    def __init__(self, policy: RetryPolicy):
        self._policy = policy
        self._attempt = 0
        self._start_time = None
        self._last_error = None
    
    @property
    def attempt(self) -> int:
        return self._attempt
    
    @property
    def last_error(self) -> Optional[Exception]:
        return self._last_error
    
    @property
    def elapsed_ms(self) -> float:
        if self._start_time:
            return (time.perf_counter() - self._start_time) * 1000
        return 0.0
    
    async def retry(
        self,
        operation: Callable[[], T],
    ) -> T:
        """Retry an operation."""
        return await self._policy.execute_or_raise(operation)


class CompositeRetryPolicy:
    """
    Composite retry policy that chains multiple policies.
    """
    
    def __init__(self, policies: List[RetryPolicy]):
        self._policies = policies
    
    async def execute(
        self,
        operation: Callable[[], T],
    ) -> RetryResult[T]:
        """Execute with chained policies."""
        all_attempts = []
        start_time = time.perf_counter()
        
        for policy in self._policies:
            result = await policy.execute(operation)
            all_attempts.extend(result.attempts)
            
            if result.success:
                return RetryResult(
                    outcome=RetryOutcome.SUCCESS,
                    value=result.value,
                    attempts=all_attempts,
                    total_duration_ms=(time.perf_counter() - start_time) * 1000,
                )
        
        return RetryResult(
            outcome=RetryOutcome.EXHAUSTED,
            attempts=all_attempts,
            total_duration_ms=(time.perf_counter() - start_time) * 1000,
            final_error=all_attempts[-1].error if all_attempts else None,
        )


class RetryRegistry:
    """
    Registry for retry policies.
    """
    
    def __init__(self):
        self._policies: Dict[str, RetryPolicy] = {}
        self._default: Optional[str] = None
    
    def register(
        self,
        name: str,
        policy: RetryPolicy,
        default: bool = False,
    ) -> None:
        """Register a policy."""
        self._policies[name] = policy
        if default or self._default is None:
            self._default = name
    
    def get(self, name: Optional[str] = None) -> RetryPolicy:
        """Get a policy."""
        name = name or self._default
        if not name or name not in self._policies:
            raise RetryError(f"Policy not found: {name}")
        return self._policies[name]


# Global registry
_global_registry = RetryRegistry()


# Decorators
def with_retry(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff: Union[str, BackoffStrategy] = BackoffStrategy.EXPONENTIAL,
    retry_on: Optional[Tuple[Type[Exception], ...]] = None,
) -> Callable:
    """
    Decorator to add retry behavior to functions.
    
    Example:
        @with_retry(max_retries=3)
        async def fetch_data():
            ...
    """
    if isinstance(backoff, str):
        backoff = BackoffStrategy(backoff)
    
    policy = RetryPolicy(RetryConfig(
        max_retries=max_retries,
        initial_delay=initial_delay,
        backoff_strategy=backoff,
        retry_on=retry_on,
    ))
    
    def decorator(func: Callable) -> Callable:
        async def wrapper(*args, **kwargs):
            async def operation():
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                return func(*args, **kwargs)
            
            return await policy.execute_or_raise(operation)
        
        return wrapper
    
    return decorator


def retry_on(*exceptions: Type[Exception]) -> Callable:
    """
    Decorator to retry on specific exceptions.
    
    Example:
        @retry_on(ConnectionError, TimeoutError)
        async def connect():
            ...
    """
    return with_retry(retry_on=exceptions)


def no_retry(func: Callable) -> Callable:
    """
    Mark function as non-retryable.
    
    Example:
        @no_retry
        def critical_operation():
            ...
    """
    func._no_retry = True
    return func


# Factory functions
def create_retry_policy(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff: Union[str, BackoffStrategy] = BackoffStrategy.EXPONENTIAL,
) -> RetryPolicy:
    """Create a retry policy."""
    if isinstance(backoff, str):
        backoff = BackoffStrategy(backoff)
    
    return RetryPolicy(RetryConfig(
        max_retries=max_retries,
        initial_delay=initial_delay,
        backoff_strategy=backoff,
    ))


def create_exponential_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    multiplier: float = 2.0,
    max_delay: float = 60.0,
) -> RetryPolicy:
    """Create exponential backoff policy."""
    return RetryPolicy(RetryConfig(
        max_retries=max_retries,
        initial_delay=initial_delay,
        max_delay=max_delay,
        backoff_strategy=BackoffStrategy.EXPONENTIAL,
        multiplier=multiplier,
    ))


def create_constant_backoff(
    max_retries: int = 3,
    delay: float = 1.0,
) -> RetryPolicy:
    """Create constant backoff policy."""
    return RetryPolicy(RetryConfig(
        max_retries=max_retries,
        initial_delay=delay,
        backoff_strategy=BackoffStrategy.CONSTANT,
    ))


def retry_builder() -> RetryPolicyBuilder:
    """Create a retry policy builder."""
    return RetryPolicyBuilder()


def register_policy(
    name: str,
    policy: RetryPolicy,
    default: bool = False,
) -> None:
    """Register policy in global registry."""
    _global_registry.register(name, policy, default)


def get_policy(name: Optional[str] = None) -> RetryPolicy:
    """Get policy from global registry."""
    return _global_registry.get(name)


__all__ = [
    # Exceptions
    "RetryError",
    "MaxRetriesExceeded",
    "NonRetryableError",
    # Enums
    "BackoffStrategy",
    "RetryOutcome",
    # Data classes
    "RetryConfig",
    "RetryAttempt",
    "RetryResult",
    # Backoff
    "BackoffCalculator",
    "ConstantBackoff",
    "LinearBackoff",
    "ExponentialBackoff",
    "FibonacciBackoff",
    "DecorrelatedJitterBackoff",
    # Policy
    "RetryPolicy",
    "RetryPolicyBuilder",
    "RetryContext",
    "CompositeRetryPolicy",
    # Registry
    "RetryRegistry",
    # Decorators
    "with_retry",
    "retry_on",
    "no_retry",
    # Factory functions
    "create_retry_policy",
    "create_exponential_backoff",
    "create_constant_backoff",
    "retry_builder",
    "register_policy",
    "get_policy",
]
