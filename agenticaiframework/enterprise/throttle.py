"""
Enterprise Throttle Module.

Provides request throttling, rate control, backpressure,
and adaptive load management.

Example:
    # Create throttle
    throttle = create_throttle(rate=100, period=60)  # 100 requests per minute
    
    # Check if allowed
    if await throttle.acquire():
        # Process request
        ...
    else:
        # Rate limited
        ...
    
    # With decorator
    @throttled(rate=10, period=1)  # 10 per second
    async def api_call():
        ...
    
    # Adaptive throttle
    adaptive = create_adaptive_throttle(
        min_rate=10,
        max_rate=1000,
        target_latency_ms=100
    )
"""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from typing import (
    Any,
    Callable,
    Deque,
    Dict,
    Generic,
    List,
    Optional,
    Tuple,
    TypeVar,
)

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ThrottleError(Exception):
    """Throttle error."""
    pass


class RateLimitExceeded(ThrottleError):
    """Rate limit exceeded."""
    pass


class ThrottleStrategy(str, Enum):
    """Throttle strategies."""
    FIXED_WINDOW = "fixed_window"
    SLIDING_WINDOW = "sliding_window"
    TOKEN_BUCKET = "token_bucket"
    LEAKY_BUCKET = "leaky_bucket"
    ADAPTIVE = "adaptive"


class ThrottleAction(str, Enum):
    """Action when throttled."""
    REJECT = "reject"
    QUEUE = "queue"
    DELAY = "delay"


@dataclass
class ThrottleConfig:
    """Throttle configuration."""
    rate: int  # Requests per period
    period: float = 1.0  # Period in seconds
    burst: int = 0  # Extra burst capacity
    strategy: ThrottleStrategy = ThrottleStrategy.SLIDING_WINDOW
    action: ThrottleAction = ThrottleAction.REJECT
    queue_size: int = 100


@dataclass
class ThrottleStats:
    """Throttle statistics."""
    total_requests: int = 0
    allowed_requests: int = 0
    throttled_requests: int = 0
    current_rate: float = 0.0
    avg_wait_time_ms: float = 0.0


@dataclass
class ThrottleResult:
    """Result of throttle check."""
    allowed: bool
    wait_time: float = 0.0
    remaining: int = 0
    reset_at: Optional[datetime] = None
    retry_after: Optional[float] = None


class Throttle(ABC):
    """Abstract throttle interface."""
    
    @abstractmethod
    async def acquire(self, count: int = 1) -> ThrottleResult:
        """Try to acquire tokens."""
        pass
    
    @abstractmethod
    async def release(self, count: int = 1) -> None:
        """Release tokens (if applicable)."""
        pass
    
    @abstractmethod
    def get_stats(self) -> ThrottleStats:
        """Get throttle statistics."""
        pass
    
    @abstractmethod
    def reset(self) -> None:
        """Reset the throttle."""
        pass


class FixedWindowThrottle(Throttle):
    """Fixed window rate limiting."""
    
    def __init__(self, config: ThrottleConfig):
        self._config = config
        self._window_start = time.time()
        self._count = 0
        self._stats = ThrottleStats()
    
    async def acquire(self, count: int = 1) -> ThrottleResult:
        """Check if request is allowed."""
        now = time.time()
        self._stats.total_requests += 1
        
        # Check if window has expired
        if now - self._window_start >= self._config.period:
            self._window_start = now
            self._count = 0
        
        # Check rate limit
        limit = self._config.rate + self._config.burst
        
        if self._count + count <= limit:
            self._count += count
            self._stats.allowed_requests += 1
            
            return ThrottleResult(
                allowed=True,
                remaining=limit - self._count,
                reset_at=datetime.fromtimestamp(self._window_start + self._config.period),
            )
        
        self._stats.throttled_requests += 1
        wait_time = self._config.period - (now - self._window_start)
        
        return ThrottleResult(
            allowed=False,
            remaining=0,
            reset_at=datetime.fromtimestamp(self._window_start + self._config.period),
            retry_after=wait_time,
            wait_time=wait_time,
        )
    
    async def release(self, count: int = 1) -> None:
        """Release is no-op for fixed window."""
        pass
    
    def get_stats(self) -> ThrottleStats:
        """Get statistics."""
        return self._stats
    
    def reset(self) -> None:
        """Reset the throttle."""
        self._window_start = time.time()
        self._count = 0


class SlidingWindowThrottle(Throttle):
    """Sliding window rate limiting."""
    
    def __init__(self, config: ThrottleConfig):
        self._config = config
        self._requests: Deque[float] = deque()
        self._stats = ThrottleStats()
    
    async def acquire(self, count: int = 1) -> ThrottleResult:
        """Check if request is allowed."""
        now = time.time()
        self._stats.total_requests += 1
        
        # Remove expired entries
        cutoff = now - self._config.period
        while self._requests and self._requests[0] < cutoff:
            self._requests.popleft()
        
        # Check rate limit
        limit = self._config.rate + self._config.burst
        
        if len(self._requests) + count <= limit:
            for _ in range(count):
                self._requests.append(now)
            
            self._stats.allowed_requests += 1
            
            return ThrottleResult(
                allowed=True,
                remaining=limit - len(self._requests),
            )
        
        self._stats.throttled_requests += 1
        
        # Calculate wait time
        wait_time = 0.0
        if self._requests:
            oldest = self._requests[0]
            wait_time = max(0, self._config.period - (now - oldest))
        
        return ThrottleResult(
            allowed=False,
            remaining=0,
            retry_after=wait_time,
            wait_time=wait_time,
        )
    
    async def release(self, count: int = 1) -> None:
        """Release is no-op for sliding window."""
        pass
    
    def get_stats(self) -> ThrottleStats:
        """Get statistics."""
        self._stats.current_rate = len(self._requests) / self._config.period
        return self._stats
    
    def reset(self) -> None:
        """Reset the throttle."""
        self._requests.clear()


class TokenBucketThrottle(Throttle):
    """Token bucket rate limiting."""
    
    def __init__(self, config: ThrottleConfig):
        self._config = config
        self._tokens = float(config.rate + config.burst)
        self._max_tokens = float(config.rate + config.burst)
        self._refill_rate = config.rate / config.period
        self._last_refill = time.time()
        self._stats = ThrottleStats()
        self._lock = asyncio.Lock()
    
    async def acquire(self, count: int = 1) -> ThrottleResult:
        """Try to acquire tokens."""
        async with self._lock:
            self._stats.total_requests += 1
            self._refill()
            
            if self._tokens >= count:
                self._tokens -= count
                self._stats.allowed_requests += 1
                
                return ThrottleResult(
                    allowed=True,
                    remaining=int(self._tokens),
                )
            
            self._stats.throttled_requests += 1
            
            # Calculate wait time for tokens
            needed = count - self._tokens
            wait_time = needed / self._refill_rate
            
            return ThrottleResult(
                allowed=False,
                remaining=0,
                retry_after=wait_time,
                wait_time=wait_time,
            )
    
    async def release(self, count: int = 1) -> None:
        """Return tokens to bucket."""
        async with self._lock:
            self._tokens = min(self._max_tokens, self._tokens + count)
    
    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self._last_refill
        self._last_refill = now
        
        refill = elapsed * self._refill_rate
        self._tokens = min(self._max_tokens, self._tokens + refill)
    
    def get_stats(self) -> ThrottleStats:
        """Get statistics."""
        self._stats.current_rate = self._max_tokens - self._tokens
        return self._stats
    
    def reset(self) -> None:
        """Reset the throttle."""
        self._tokens = self._max_tokens
        self._last_refill = time.time()


class LeakyBucketThrottle(Throttle):
    """Leaky bucket rate limiting (smooth output rate)."""
    
    def __init__(self, config: ThrottleConfig):
        self._config = config
        self._queue: Deque[Tuple[float, asyncio.Event]] = deque()
        self._leak_rate = config.rate / config.period  # requests per second
        self._last_leak = time.time()
        self._stats = ThrottleStats()
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    async def start(self) -> None:
        """Start the leaky bucket processor."""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._leak_loop())
    
    async def stop(self) -> None:
        """Stop the leaky bucket processor."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
    
    async def _leak_loop(self) -> None:
        """Process queue at fixed rate."""
        interval = 1.0 / self._leak_rate
        
        while self._running:
            try:
                if self._queue:
                    _, event = self._queue.popleft()
                    event.set()
                
                await asyncio.sleep(interval)
                
            except asyncio.CancelledError:
                break
    
    async def acquire(self, count: int = 1) -> ThrottleResult:
        """Queue request for processing."""
        self._stats.total_requests += 1
        
        # Check queue size
        if len(self._queue) >= self._config.queue_size:
            self._stats.throttled_requests += 1
            return ThrottleResult(
                allowed=False,
                remaining=0,
                wait_time=len(self._queue) / self._leak_rate,
            )
        
        # Add to queue and wait
        event = asyncio.Event()
        self._queue.append((time.time(), event))
        
        if self._config.action == ThrottleAction.QUEUE:
            await event.wait()
            self._stats.allowed_requests += 1
            return ThrottleResult(allowed=True, remaining=self._config.queue_size - len(self._queue))
        
        self._stats.allowed_requests += 1
        return ThrottleResult(
            allowed=True,
            remaining=self._config.queue_size - len(self._queue),
            wait_time=len(self._queue) / self._leak_rate,
        )
    
    async def release(self, count: int = 1) -> None:
        """Release is no-op for leaky bucket."""
        pass
    
    def get_stats(self) -> ThrottleStats:
        """Get statistics."""
        self._stats.current_rate = self._leak_rate
        return self._stats
    
    def reset(self) -> None:
        """Reset the throttle."""
        self._queue.clear()


class AdaptiveThrottle(Throttle):
    """
    Adaptive throttle that adjusts rate based on latency.
    """
    
    def __init__(
        self,
        min_rate: int = 10,
        max_rate: int = 1000,
        target_latency_ms: float = 100.0,
        adjustment_factor: float = 0.1,
    ):
        self._min_rate = min_rate
        self._max_rate = max_rate
        self._current_rate = (min_rate + max_rate) // 2
        self._target_latency = target_latency_ms
        self._adjustment_factor = adjustment_factor
        
        self._latencies: Deque[float] = deque(maxlen=100)
        self._inner_throttle = TokenBucketThrottle(ThrottleConfig(
            rate=self._current_rate,
            period=1.0,
        ))
        self._stats = ThrottleStats()
    
    async def acquire(self, count: int = 1) -> ThrottleResult:
        """Acquire with adaptive rate adjustment."""
        result = await self._inner_throttle.acquire(count)
        self._stats.total_requests += 1
        
        if result.allowed:
            self._stats.allowed_requests += 1
        else:
            self._stats.throttled_requests += 1
        
        return result
    
    async def release(self, count: int = 1) -> None:
        """Release tokens."""
        await self._inner_throttle.release(count)
    
    def record_latency(self, latency_ms: float) -> None:
        """Record a latency measurement and adjust rate."""
        self._latencies.append(latency_ms)
        
        if len(self._latencies) < 10:
            return
        
        avg_latency = sum(self._latencies) / len(self._latencies)
        
        # Adjust rate based on latency
        if avg_latency > self._target_latency:
            # Too slow, reduce rate
            adjustment = int(self._current_rate * self._adjustment_factor)
            self._current_rate = max(self._min_rate, self._current_rate - adjustment)
        else:
            # Fast enough, increase rate
            adjustment = int(self._current_rate * self._adjustment_factor)
            self._current_rate = min(self._max_rate, self._current_rate + adjustment)
        
        # Update inner throttle
        self._inner_throttle = TokenBucketThrottle(ThrottleConfig(
            rate=self._current_rate,
            period=1.0,
        ))
        
        logger.debug(f"Adjusted rate to {self._current_rate} (avg latency: {avg_latency:.1f}ms)")
    
    def get_stats(self) -> ThrottleStats:
        """Get statistics."""
        self._stats.current_rate = float(self._current_rate)
        
        if self._latencies:
            self._stats.avg_wait_time_ms = sum(self._latencies) / len(self._latencies)
        
        return self._stats
    
    def reset(self) -> None:
        """Reset the throttle."""
        self._latencies.clear()
        self._current_rate = (self._min_rate + self._max_rate) // 2
        self._inner_throttle.reset()


class ConcurrencyLimiter:
    """Limit concurrent operations."""
    
    def __init__(self, max_concurrent: int):
        self._max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._current = 0
        self._stats = ThrottleStats()
    
    async def acquire(self) -> bool:
        """Acquire a slot."""
        self._stats.total_requests += 1
        
        acquired = await asyncio.wait_for(
            self._semaphore.acquire(),
            timeout=None,
        )
        
        if acquired:
            self._current += 1
            self._stats.allowed_requests += 1
        
        return acquired
    
    async def release(self) -> None:
        """Release a slot."""
        self._semaphore.release()
        self._current = max(0, self._current - 1)
    
    @property
    def current(self) -> int:
        """Get current concurrent count."""
        return self._current
    
    @property
    def available(self) -> int:
        """Get available slots."""
        return self._max_concurrent - self._current
    
    def get_stats(self) -> ThrottleStats:
        """Get statistics."""
        self._stats.current_rate = float(self._current)
        return self._stats


class BackpressureController:
    """
    Backpressure controller for flow control.
    """
    
    def __init__(
        self,
        low_watermark: int = 100,
        high_watermark: int = 1000,
    ):
        self._low_watermark = low_watermark
        self._high_watermark = high_watermark
        self._queue_size = 0
        self._paused = False
        self._on_pause: Optional[Callable] = None
        self._on_resume: Optional[Callable] = None
    
    @property
    def is_paused(self) -> bool:
        """Check if backpressure is active."""
        return self._paused
    
    def on_pause(self, callback: Callable) -> None:
        """Set pause callback."""
        self._on_pause = callback
    
    def on_resume(self, callback: Callable) -> None:
        """Set resume callback."""
        self._on_resume = callback
    
    def update(self, queue_size: int) -> None:
        """Update queue size and check thresholds."""
        self._queue_size = queue_size
        
        if not self._paused and queue_size >= self._high_watermark:
            self._paused = True
            logger.warning(f"Backpressure activated (queue size: {queue_size})")
            
            if self._on_pause:
                self._on_pause()
        
        elif self._paused and queue_size <= self._low_watermark:
            self._paused = False
            logger.info(f"Backpressure released (queue size: {queue_size})")
            
            if self._on_resume:
                self._on_resume()
    
    def check(self) -> bool:
        """Check if processing should continue."""
        return not self._paused


# Decorators
def throttled(
    rate: int,
    period: float = 1.0,
    strategy: ThrottleStrategy = ThrottleStrategy.SLIDING_WINDOW,
    on_throttled: Optional[Callable] = None,
) -> Callable:
    """
    Decorator to throttle function calls.
    
    Example:
        @throttled(rate=10, period=1)
        async def api_call():
            ...
    """
    config = ThrottleConfig(rate=rate, period=period, strategy=strategy)
    
    if strategy == ThrottleStrategy.TOKEN_BUCKET:
        throttle = TokenBucketThrottle(config)
    elif strategy == ThrottleStrategy.FIXED_WINDOW:
        throttle = FixedWindowThrottle(config)
    else:
        throttle = SlidingWindowThrottle(config)
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = await throttle.acquire()
            
            if not result.allowed:
                if on_throttled:
                    return on_throttled(result)
                raise RateLimitExceeded(f"Rate limit exceeded. Retry after {result.retry_after:.2f}s")
            
            return await func(*args, **kwargs)
        
        return wrapper
    
    return decorator


def concurrent_limit(max_concurrent: int) -> Callable:
    """
    Decorator to limit concurrent executions.
    
    Example:
        @concurrent_limit(5)
        async def process_item(item):
            ...
    """
    limiter = ConcurrencyLimiter(max_concurrent)
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            await limiter.acquire()
            try:
                return await func(*args, **kwargs)
            finally:
                await limiter.release()
        
        return wrapper
    
    return decorator


# Factory functions
def create_throttle(
    rate: int,
    period: float = 1.0,
    strategy: ThrottleStrategy = ThrottleStrategy.SLIDING_WINDOW,
    **kwargs: Any,
) -> Throttle:
    """Create a throttle."""
    config = ThrottleConfig(rate=rate, period=period, strategy=strategy, **kwargs)
    
    if strategy == ThrottleStrategy.FIXED_WINDOW:
        return FixedWindowThrottle(config)
    elif strategy == ThrottleStrategy.TOKEN_BUCKET:
        return TokenBucketThrottle(config)
    elif strategy == ThrottleStrategy.LEAKY_BUCKET:
        return LeakyBucketThrottle(config)
    else:
        return SlidingWindowThrottle(config)


def create_adaptive_throttle(
    min_rate: int = 10,
    max_rate: int = 1000,
    target_latency_ms: float = 100.0,
    **kwargs: Any,
) -> AdaptiveThrottle:
    """Create an adaptive throttle."""
    return AdaptiveThrottle(min_rate, max_rate, target_latency_ms, **kwargs)


def create_concurrency_limiter(max_concurrent: int) -> ConcurrencyLimiter:
    """Create a concurrency limiter."""
    return ConcurrencyLimiter(max_concurrent)


def create_backpressure_controller(
    low_watermark: int = 100,
    high_watermark: int = 1000,
) -> BackpressureController:
    """Create a backpressure controller."""
    return BackpressureController(low_watermark, high_watermark)


__all__ = [
    # Exceptions
    "ThrottleError",
    "RateLimitExceeded",
    # Enums
    "ThrottleStrategy",
    "ThrottleAction",
    # Data classes
    "ThrottleConfig",
    "ThrottleStats",
    "ThrottleResult",
    # Core classes
    "Throttle",
    "FixedWindowThrottle",
    "SlidingWindowThrottle",
    "TokenBucketThrottle",
    "LeakyBucketThrottle",
    "AdaptiveThrottle",
    "ConcurrencyLimiter",
    "BackpressureController",
    # Decorators
    "throttled",
    "concurrent_limit",
    # Factory
    "create_throttle",
    "create_adaptive_throttle",
    "create_concurrency_limiter",
    "create_backpressure_controller",
]
