"""
Enterprise Circuit Breaker Module.

Implements the circuit breaker pattern for resilient API calls with
support for half-open states, failure thresholds, and recovery.

Example:
    breaker = CircuitBreaker(
        failure_threshold=5,
        recovery_timeout=30.0
    )
    
    @breaker
    async def call_external_api(data: dict) -> dict:
        return await api.request(data)
    
    # Or use decorator directly
    @circuit_breaker(failure_threshold=3)
    async def risky_operation():
        ...
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
    Tuple,
    Type,
    TypeVar,
    Union,
)
from functools import wraps
from enum import Enum
from collections import deque
import logging
import random

logger = logging.getLogger(__name__)

T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])


class CircuitState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation, requests pass through
    OPEN = "open"          # Failing, requests are blocked
    HALF_OPEN = "half_open"  # Testing, limited requests allowed


class CircuitBreakerOpen(Exception):
    """Raised when circuit breaker is open."""
    
    def __init__(
        self,
        message: str = "Circuit breaker is open",
        circuit_name: Optional[str] = None,
        time_remaining: Optional[float] = None,
    ):
        super().__init__(message)
        self.circuit_name = circuit_name
        self.time_remaining = time_remaining


@dataclass
class CircuitStats:
    """Statistics for a circuit breaker."""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    last_state_change: float = field(default_factory=time.time)
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    
    @property
    def failure_rate(self) -> float:
        """Calculate failure rate."""
        if self.total_calls == 0:
            return 0.0
        return self.failed_calls / self.total_calls
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_calls == 0:
            return 0.0
        return self.successful_calls / self.total_calls
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "rejected_calls": self.rejected_calls,
            "failure_rate": self.failure_rate,
            "success_rate": self.success_rate,
            "consecutive_failures": self.consecutive_failures,
            "consecutive_successes": self.consecutive_successes,
            "last_failure_time": self.last_failure_time,
            "last_success_time": self.last_success_time,
            "last_state_change": self.last_state_change,
        }


@dataclass
class CircuitEvent:
    """Event from circuit breaker state changes."""
    circuit_name: str
    event_type: str  # "state_change", "success", "failure", "rejected"
    timestamp: float
    previous_state: Optional[CircuitState] = None
    current_state: Optional[CircuitState] = None
    error: Optional[Exception] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class CircuitBreakerListener(ABC):
    """Listener for circuit breaker events."""
    
    @abstractmethod
    def on_event(self, event: CircuitEvent) -> None:
        """Handle circuit breaker event."""
        pass


class LoggingListener(CircuitBreakerListener):
    """Listener that logs circuit breaker events."""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
    
    def on_event(self, event: CircuitEvent) -> None:
        """Log circuit breaker event."""
        if event.event_type == "state_change":
            self.logger.warning(
                f"Circuit '{event.circuit_name}' state changed: "
                f"{event.previous_state} -> {event.current_state}"
            )
        elif event.event_type == "failure":
            self.logger.error(
                f"Circuit '{event.circuit_name}' recorded failure: {event.error}"
            )
        elif event.event_type == "rejected":
            self.logger.warning(
                f"Circuit '{event.circuit_name}' rejected request"
            )


class FailureDetector(ABC):
    """Abstract failure detector for determining what counts as failure."""
    
    @abstractmethod
    def is_failure(self, error: Exception) -> bool:
        """Check if exception should count as a failure."""
        pass


class DefaultFailureDetector(FailureDetector):
    """Default failure detector - all exceptions are failures."""
    
    def __init__(
        self,
        include: Optional[Tuple[Type[Exception], ...]] = None,
        exclude: Optional[Tuple[Type[Exception], ...]] = None,
    ):
        """
        Initialize detector.
        
        Args:
            include: Only count these exception types as failures
            exclude: Never count these exception types as failures
        """
        self.include = include
        self.exclude = exclude or ()
    
    def is_failure(self, error: Exception) -> bool:
        """Check if exception is a failure."""
        if isinstance(error, self.exclude):
            return False
        if self.include is not None:
            return isinstance(error, self.include)
        return True


class CircuitBreaker:
    """
    Circuit breaker for protecting against cascading failures.
    
    The circuit breaker has three states:
    - CLOSED: Normal operation, all requests pass through
    - OPEN: Failure threshold exceeded, all requests are blocked
    - HALF_OPEN: Recovery testing, limited requests allowed
    """
    
    def __init__(
        self,
        name: str = "default",
        failure_threshold: int = 5,
        success_threshold: int = 3,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
        failure_detector: Optional[FailureDetector] = None,
        listeners: Optional[List[CircuitBreakerListener]] = None,
        fallback: Optional[Callable[..., Any]] = None,
    ):
        """
        Initialize circuit breaker.
        
        Args:
            name: Circuit breaker name for identification
            failure_threshold: Failures before opening circuit
            success_threshold: Successes in half-open before closing
            recovery_timeout: Seconds before trying half-open
            half_open_max_calls: Max concurrent calls in half-open
            failure_detector: Custom failure detection logic
            listeners: Event listeners
            fallback: Fallback function when circuit is open
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.failure_detector = failure_detector or DefaultFailureDetector()
        self.listeners = listeners or []
        self.fallback = fallback
        
        self._state = CircuitState.CLOSED
        self._stats = CircuitStats()
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0
        self._lock = asyncio.Lock()
        self._sync_lock = threading.Lock()
    
    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state
    
    @property
    def stats(self) -> CircuitStats:
        """Get circuit statistics."""
        return self._stats
    
    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self._state == CircuitState.CLOSED
    
    @property
    def is_open(self) -> bool:
        """Check if circuit is open (blocking requests)."""
        return self._state == CircuitState.OPEN
    
    @property
    def is_half_open(self) -> bool:
        """Check if circuit is half-open (testing recovery)."""
        return self._state == CircuitState.HALF_OPEN
    
    def _emit_event(self, event: CircuitEvent) -> None:
        """Emit event to all listeners."""
        for listener in self.listeners:
            try:
                listener.on_event(event)
            except Exception as e:
                logger.error(f"Error in circuit breaker listener: {e}")
    
    def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to a new state."""
        if self._state == new_state:
            return
        
        old_state = self._state
        self._state = new_state
        self._stats.last_state_change = time.time()
        
        if new_state == CircuitState.HALF_OPEN:
            self._half_open_calls = 0
        
        self._emit_event(CircuitEvent(
            circuit_name=self.name,
            event_type="state_change",
            timestamp=time.time(),
            previous_state=old_state,
            current_state=new_state,
        ))
        
        logger.info(f"Circuit '{self.name}': {old_state.value} -> {new_state.value}")
    
    def _should_allow_request(self) -> bool:
        """Check if request should be allowed."""
        if self._state == CircuitState.CLOSED:
            return True
        
        if self._state == CircuitState.OPEN:
            # Check if recovery timeout has elapsed
            if self._last_failure_time is not None:
                elapsed = time.time() - self._last_failure_time
                if elapsed >= self.recovery_timeout:
                    self._transition_to(CircuitState.HALF_OPEN)
                    return True
            return False
        
        if self._state == CircuitState.HALF_OPEN:
            # Allow limited calls in half-open state
            return self._half_open_calls < self.half_open_max_calls
        
        return False
    
    def _record_success(self) -> None:
        """Record a successful call."""
        self._stats.total_calls += 1
        self._stats.successful_calls += 1
        self._stats.consecutive_successes += 1
        self._stats.consecutive_failures = 0
        self._stats.last_success_time = time.time()
        
        if self._state == CircuitState.HALF_OPEN:
            if self._stats.consecutive_successes >= self.success_threshold:
                self._transition_to(CircuitState.CLOSED)
    
    def _record_failure(self, error: Exception) -> None:
        """Record a failed call."""
        self._stats.total_calls += 1
        self._stats.failed_calls += 1
        self._stats.consecutive_failures += 1
        self._stats.consecutive_successes = 0
        self._stats.last_failure_time = time.time()
        self._last_failure_time = time.time()
        
        self._emit_event(CircuitEvent(
            circuit_name=self.name,
            event_type="failure",
            timestamp=time.time(),
            current_state=self._state,
            error=error,
        ))
        
        if self._state == CircuitState.CLOSED:
            if self._stats.consecutive_failures >= self.failure_threshold:
                self._transition_to(CircuitState.OPEN)
        elif self._state == CircuitState.HALF_OPEN:
            self._transition_to(CircuitState.OPEN)
    
    def _record_rejected(self) -> None:
        """Record a rejected call."""
        self._stats.rejected_calls += 1
        
        self._emit_event(CircuitEvent(
            circuit_name=self.name,
            event_type="rejected",
            timestamp=time.time(),
            current_state=self._state,
        ))
    
    async def execute(
        self,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        Execute function through circuit breaker.
        
        Args:
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Function result
            
        Raises:
            CircuitBreakerOpen: If circuit is open
        """
        async with self._lock:
            if not self._should_allow_request():
                self._record_rejected()
                
                if self.fallback:
                    return await self._call_fallback(*args, **kwargs)
                
                time_remaining = None
                if self._last_failure_time:
                    time_remaining = max(
                        0,
                        self.recovery_timeout - (time.time() - self._last_failure_time)
                    )
                
                raise CircuitBreakerOpen(
                    f"Circuit breaker '{self.name}' is open",
                    circuit_name=self.name,
                    time_remaining=time_remaining,
                )
            
            if self._state == CircuitState.HALF_OPEN:
                self._half_open_calls += 1
        
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            async with self._lock:
                self._record_success()
            
            return result
        
        except Exception as e:
            async with self._lock:
                if self.failure_detector.is_failure(e):
                    self._record_failure(e)
            
            if self.fallback:
                return await self._call_fallback(*args, **kwargs)
            
            raise
    
    async def _call_fallback(self, *args: Any, **kwargs: Any) -> Any:
        """Call fallback function."""
        if asyncio.iscoroutinefunction(self.fallback):
            return await self.fallback(*args, **kwargs)
        return self.fallback(*args, **kwargs)
    
    def execute_sync(
        self,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        Execute function synchronously through circuit breaker.
        
        Args:
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Function result
        """
        with self._sync_lock:
            if not self._should_allow_request():
                self._record_rejected()
                
                if self.fallback:
                    return self.fallback(*args, **kwargs)
                
                raise CircuitBreakerOpen(
                    f"Circuit breaker '{self.name}' is open",
                    circuit_name=self.name,
                )
            
            if self._state == CircuitState.HALF_OPEN:
                self._half_open_calls += 1
        
        try:
            result = func(*args, **kwargs)
            
            with self._sync_lock:
                self._record_success()
            
            return result
        
        except Exception as e:
            with self._sync_lock:
                if self.failure_detector.is_failure(e):
                    self._record_failure(e)
            
            if self.fallback:
                return self.fallback(*args, **kwargs)
            
            raise
    
    def reset(self) -> None:
        """Reset circuit breaker to closed state."""
        self._state = CircuitState.CLOSED
        self._stats = CircuitStats()
        self._last_failure_time = None
        self._half_open_calls = 0
        logger.info(f"Circuit '{self.name}' manually reset to closed")
    
    def force_open(self) -> None:
        """Force circuit to open state."""
        self._transition_to(CircuitState.OPEN)
        self._last_failure_time = time.time()
        logger.info(f"Circuit '{self.name}' manually forced open")
    
    def __call__(self, func: F) -> F:
        """Use circuit breaker as a decorator."""
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await self.execute(func, *args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            return self.execute_sync(func, *args, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper


class SlidingWindowCircuitBreaker(CircuitBreaker):
    """
    Circuit breaker with sliding window failure rate calculation.
    
    Uses a time-based sliding window to calculate failure rate,
    providing more accurate failure detection for variable load.
    """
    
    def __init__(
        self,
        name: str = "default",
        window_size: float = 60.0,
        failure_rate_threshold: float = 0.5,
        minimum_calls: int = 10,
        **kwargs: Any,
    ):
        """
        Initialize sliding window circuit breaker.
        
        Args:
            name: Circuit breaker name
            window_size: Sliding window duration in seconds
            failure_rate_threshold: Failure rate to trigger open (0-1)
            minimum_calls: Minimum calls before evaluating failure rate
            **kwargs: Additional arguments for base class
        """
        super().__init__(name=name, **kwargs)
        self.window_size = window_size
        self.failure_rate_threshold = failure_rate_threshold
        self.minimum_calls = minimum_calls
        
        self._call_history: deque = deque()
    
    def _cleanup_old_calls(self) -> None:
        """Remove calls outside the sliding window."""
        cutoff = time.time() - self.window_size
        while self._call_history and self._call_history[0][0] < cutoff:
            self._call_history.popleft()
    
    def _get_failure_rate(self) -> float:
        """Calculate failure rate within sliding window."""
        self._cleanup_old_calls()
        
        if len(self._call_history) < self.minimum_calls:
            return 0.0
        
        failures = sum(1 for _, success in self._call_history if not success)
        return failures / len(self._call_history)
    
    def _record_success(self) -> None:
        """Record a successful call."""
        super()._record_success()
        self._call_history.append((time.time(), True))
    
    def _record_failure(self, error: Exception) -> None:
        """Record a failed call."""
        self._call_history.append((time.time(), False))
        
        self._stats.total_calls += 1
        self._stats.failed_calls += 1
        self._stats.consecutive_failures += 1
        self._stats.consecutive_successes = 0
        self._stats.last_failure_time = time.time()
        self._last_failure_time = time.time()
        
        self._emit_event(CircuitEvent(
            circuit_name=self.name,
            event_type="failure",
            timestamp=time.time(),
            current_state=self._state,
            error=error,
        ))
        
        if self._state == CircuitState.CLOSED:
            if self._get_failure_rate() >= self.failure_rate_threshold:
                self._transition_to(CircuitState.OPEN)
        elif self._state == CircuitState.HALF_OPEN:
            self._transition_to(CircuitState.OPEN)


class CountBasedCircuitBreaker(CircuitBreaker):
    """
    Circuit breaker with count-based failure detection.
    
    Tracks the last N calls and opens when failure count exceeds threshold.
    """
    
    def __init__(
        self,
        name: str = "default",
        ring_size: int = 100,
        failure_count_threshold: int = 50,
        **kwargs: Any,
    ):
        """
        Initialize count-based circuit breaker.
        
        Args:
            name: Circuit breaker name
            ring_size: Number of calls to track
            failure_count_threshold: Failures to trigger open
            **kwargs: Additional arguments for base class
        """
        super().__init__(name=name, **kwargs)
        self.ring_size = ring_size
        self.failure_count_threshold = failure_count_threshold
        
        self._ring: deque = deque(maxlen=ring_size)
    
    def _get_failure_count(self) -> int:
        """Count failures in ring buffer."""
        return sum(1 for success in self._ring if not success)
    
    def _record_success(self) -> None:
        """Record a successful call."""
        super()._record_success()
        self._ring.append(True)
    
    def _record_failure(self, error: Exception) -> None:
        """Record a failed call."""
        self._ring.append(False)
        
        self._stats.total_calls += 1
        self._stats.failed_calls += 1
        self._stats.consecutive_failures += 1
        self._stats.consecutive_successes = 0
        self._stats.last_failure_time = time.time()
        self._last_failure_time = time.time()
        
        self._emit_event(CircuitEvent(
            circuit_name=self.name,
            event_type="failure",
            timestamp=time.time(),
            current_state=self._state,
            error=error,
        ))
        
        if self._state == CircuitState.CLOSED:
            if (len(self._ring) >= self.ring_size and 
                self._get_failure_count() >= self.failure_count_threshold):
                self._transition_to(CircuitState.OPEN)
        elif self._state == CircuitState.HALF_OPEN:
            self._transition_to(CircuitState.OPEN)


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    name: str = "default"
    failure_threshold: int = 5
    success_threshold: int = 3
    recovery_timeout: float = 30.0
    half_open_max_calls: int = 3
    
    def create(self) -> CircuitBreaker:
        """Create circuit breaker from config."""
        return CircuitBreaker(
            name=self.name,
            failure_threshold=self.failure_threshold,
            success_threshold=self.success_threshold,
            recovery_timeout=self.recovery_timeout,
            half_open_max_calls=self.half_open_max_calls,
        )


class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers."""
    
    _instance: Optional['CircuitBreakerRegistry'] = None
    
    def __init__(self):
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._lock = threading.Lock()
    
    @classmethod
    def get_instance(cls) -> 'CircuitBreakerRegistry':
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def register(
        self,
        name: str,
        breaker: Optional[CircuitBreaker] = None,
        **kwargs: Any,
    ) -> CircuitBreaker:
        """
        Register a circuit breaker.
        
        Args:
            name: Circuit breaker name
            breaker: Existing breaker or None to create new
            **kwargs: Arguments for creating new breaker
            
        Returns:
            Registered circuit breaker
        """
        with self._lock:
            if breaker is None:
                breaker = CircuitBreaker(name=name, **kwargs)
            self._breakers[name] = breaker
            return breaker
    
    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker by name."""
        with self._lock:
            return self._breakers.get(name)
    
    def get_or_create(self, name: str, **kwargs: Any) -> CircuitBreaker:
        """Get existing or create new circuit breaker."""
        with self._lock:
            if name not in self._breakers:
                self._breakers[name] = CircuitBreaker(name=name, **kwargs)
            return self._breakers[name]
    
    def remove(self, name: str) -> Optional[CircuitBreaker]:
        """Remove and return circuit breaker."""
        with self._lock:
            return self._breakers.pop(name, None)
    
    def list_all(self) -> Dict[str, CircuitStats]:
        """List all circuit breakers with their stats."""
        with self._lock:
            return {
                name: breaker.stats
                for name, breaker in self._breakers.items()
            }
    
    def reset_all(self) -> None:
        """Reset all circuit breakers."""
        with self._lock:
            for breaker in self._breakers.values():
                breaker.reset()


def circuit_breaker(
    name: Optional[str] = None,
    failure_threshold: int = 5,
    success_threshold: int = 3,
    recovery_timeout: float = 30.0,
    fallback: Optional[Callable[..., Any]] = None,
    exclude: Optional[Tuple[Type[Exception], ...]] = None,
) -> Callable[[F], F]:
    """
    Decorator for applying circuit breaker to a function.
    
    Args:
        name: Circuit breaker name (uses function name if not provided)
        failure_threshold: Failures before opening circuit
        success_threshold: Successes needed to close
        recovery_timeout: Seconds before testing recovery
        fallback: Fallback function when circuit is open
        exclude: Exception types to not count as failures
        
    Returns:
        Decorated function
        
    Example:
        @circuit_breaker(failure_threshold=3, recovery_timeout=60)
        async def call_external_api(data: dict) -> dict:
            return await api.request(data)
    """
    def decorator(func: F) -> F:
        circuit_name = name or func.__name__
        
        failure_detector = DefaultFailureDetector(exclude=exclude)
        
        breaker = CircuitBreaker(
            name=circuit_name,
            failure_threshold=failure_threshold,
            success_threshold=success_threshold,
            recovery_timeout=recovery_timeout,
            failure_detector=failure_detector,
            fallback=fallback,
        )
        
        # Register in global registry
        CircuitBreakerRegistry.get_instance().register(circuit_name, breaker)
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await breaker.execute(func, *args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            return breaker.execute_sync(func, *args, **kwargs)
        
        wrapper = async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
        wrapper.circuit_breaker = breaker  # Attach breaker for access
        
        return wrapper
    
    return decorator


def with_fallback(fallback_func: Callable[..., Any]) -> Callable[[F], F]:
    """
    Decorator to add fallback to an existing circuit-breaker decorated function.
    
    Args:
        fallback_func: Function to call when circuit is open or on failure
        
    Returns:
        Decorated function
    """
    def decorator(func: F) -> F:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                return func(*args, **kwargs)
            except CircuitBreakerOpen:
                if asyncio.iscoroutinefunction(fallback_func):
                    return await fallback_func(*args, **kwargs)
                return fallback_func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except CircuitBreakerOpen:
                return fallback_func(*args, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


class CircuitBreakerMiddleware:
    """
    Middleware for applying circuit breaker in agent pipelines.
    """
    
    def __init__(
        self,
        breaker: CircuitBreaker,
        key_func: Optional[Callable[[Dict[str, Any]], str]] = None,
    ):
        """
        Initialize middleware.
        
        Args:
            breaker: Circuit breaker to use
            key_func: Optional function to get key for per-key breaking
        """
        self.breaker = breaker
        self.key_func = key_func
        self._per_key_breakers: Dict[str, CircuitBreaker] = {}
    
    def _get_breaker(self, context: Dict[str, Any]) -> CircuitBreaker:
        """Get circuit breaker for context."""
        if self.key_func is None:
            return self.breaker
        
        key = self.key_func(context)
        if key not in self._per_key_breakers:
            self._per_key_breakers[key] = CircuitBreaker(
                name=f"{self.breaker.name}:{key}",
                failure_threshold=self.breaker.failure_threshold,
                success_threshold=self.breaker.success_threshold,
                recovery_timeout=self.breaker.recovery_timeout,
            )
        return self._per_key_breakers[key]
    
    async def __call__(
        self,
        context: Dict[str, Any],
        next_handler: Callable[[Dict[str, Any]], Any],
    ) -> Any:
        """Process request through circuit breaker."""
        breaker = self._get_breaker(context)
        
        # Add circuit state to context
        context["circuit_state"] = breaker.state.value
        context["circuit_stats"] = breaker.stats.to_dict()
        
        return await breaker.execute(next_handler, context)


# Global registry instance
_registry = CircuitBreakerRegistry()


def get_circuit_breaker(name: str) -> Optional[CircuitBreaker]:
    """Get a registered circuit breaker by name."""
    return _registry.get(name)


def get_or_create_circuit_breaker(name: str, **kwargs: Any) -> CircuitBreaker:
    """Get or create a circuit breaker."""
    return _registry.get_or_create(name, **kwargs)


def get_all_circuit_stats() -> Dict[str, Dict[str, Any]]:
    """Get statistics for all circuit breakers."""
    return {
        name: stats.to_dict()
        for name, stats in _registry.list_all().items()
    }


def reset_all_circuits() -> None:
    """Reset all circuit breakers to closed state."""
    _registry.reset_all()


__all__ = [
    # Exceptions
    "CircuitBreakerOpen",
    # Enums
    "CircuitState",
    # Data classes
    "CircuitStats",
    "CircuitEvent",
    "CircuitBreakerConfig",
    # Base classes
    "CircuitBreakerListener",
    "LoggingListener",
    "FailureDetector",
    "DefaultFailureDetector",
    # Circuit breakers
    "CircuitBreaker",
    "SlidingWindowCircuitBreaker",
    "CountBasedCircuitBreaker",
    # Registry
    "CircuitBreakerRegistry",
    # Middleware
    "CircuitBreakerMiddleware",
    # Decorators
    "circuit_breaker",
    "with_fallback",
    # Functions
    "get_circuit_breaker",
    "get_or_create_circuit_breaker",
    "get_all_circuit_stats",
    "reset_all_circuits",
]
