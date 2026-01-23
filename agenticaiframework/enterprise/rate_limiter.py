"""
Enterprise Rate Limiting Module.

Provides token bucket, sliding window, and leaky bucket rate limiters
with support for distributed limiting via Redis.

Example:
    # Simple token bucket
    limiter = TokenBucketLimiter(rate=10, capacity=100)
    
    @rate_limit(limiter)
    async def call_llm(prompt: str) -> str:
        return await llm.complete(prompt)
    
    # Sliding window
    sliding = SlidingWindowLimiter(limit=100, window_seconds=60)
    
    # Distributed with Redis
    distributed = RedisRateLimiter(
        redis_url="redis://localhost:6379",
        key_prefix="myapp",
        limit=1000,
        window_seconds=3600
    )
"""

from __future__ import annotations

import asyncio
import time
import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    TypeVar,
    Union,
)
from functools import wraps
from enum import Enum
from collections import defaultdict
import threading
import logging

logger = logging.getLogger(__name__)

T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded."""
    
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: Optional[float] = None,
        limit: Optional[int] = None,
        remaining: int = 0,
    ):
        super().__init__(message)
        self.retry_after = retry_after
        self.limit = limit
        self.remaining = remaining


class LimiterType(str, Enum):
    """Type of rate limiter."""
    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"
    LEAKY_BUCKET = "leaky_bucket"
    FIXED_WINDOW = "fixed_window"
    CONCURRENT = "concurrent"


@dataclass
class RateLimitInfo:
    """Information about current rate limit status."""
    limit: int
    remaining: int
    reset_at: float
    retry_after: Optional[float] = None
    
    @property
    def is_limited(self) -> bool:
        """Check if currently rate limited."""
        return self.remaining <= 0
    
    def to_headers(self) -> Dict[str, str]:
        """Convert to HTTP rate limit headers."""
        headers = {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(self.remaining),
            "X-RateLimit-Reset": str(int(self.reset_at)),
        }
        if self.retry_after is not None:
            headers["Retry-After"] = str(int(self.retry_after))
        return headers


class RateLimiter(ABC):
    """Abstract base class for rate limiters."""
    
    @abstractmethod
    async def acquire(self, key: str = "default", tokens: int = 1) -> bool:
        """
        Try to acquire tokens.
        
        Args:
            key: Identifier for the rate limit bucket
            tokens: Number of tokens to acquire
            
        Returns:
            True if tokens acquired, False otherwise
        """
        pass
    
    @abstractmethod
    async def get_info(self, key: str = "default") -> RateLimitInfo:
        """Get current rate limit information."""
        pass
    
    async def wait_and_acquire(
        self,
        key: str = "default",
        tokens: int = 1,
        timeout: Optional[float] = None,
    ) -> bool:
        """
        Wait until tokens are available and acquire them.
        
        Args:
            key: Identifier for the rate limit bucket
            tokens: Number of tokens to acquire
            timeout: Maximum time to wait in seconds
            
        Returns:
            True if tokens acquired, False if timeout
        """
        start = time.time()
        while True:
            if await self.acquire(key, tokens):
                return True
            
            info = await self.get_info(key)
            if timeout is not None:
                elapsed = time.time() - start
                if elapsed >= timeout:
                    return False
                wait_time = min(
                    info.retry_after or 0.1,
                    timeout - elapsed
                )
            else:
                wait_time = info.retry_after or 0.1
            
            await asyncio.sleep(wait_time)


class TokenBucketLimiter(RateLimiter):
    """
    Token bucket rate limiter.
    
    Tokens are added at a constant rate up to a maximum capacity.
    Requests consume tokens; if insufficient tokens, request is denied.
    """
    
    def __init__(
        self,
        rate: float,
        capacity: int,
        initial_tokens: Optional[int] = None,
    ):
        """
        Initialize token bucket.
        
        Args:
            rate: Tokens added per second
            capacity: Maximum token capacity
            initial_tokens: Starting tokens (defaults to capacity)
        """
        self.rate = rate
        self.capacity = capacity
        self._buckets: Dict[str, Dict[str, float]] = {}
        self._initial_tokens = initial_tokens if initial_tokens is not None else capacity
        self._lock = asyncio.Lock()
    
    def _get_bucket(self, key: str) -> Dict[str, float]:
        """Get or create bucket for key."""
        if key not in self._buckets:
            self._buckets[key] = {
                "tokens": float(self._initial_tokens),
                "last_update": time.time(),
            }
        return self._buckets[key]
    
    def _refill(self, bucket: Dict[str, float]) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - bucket["last_update"]
        bucket["tokens"] = min(
            self.capacity,
            bucket["tokens"] + elapsed * self.rate
        )
        bucket["last_update"] = now
    
    async def acquire(self, key: str = "default", tokens: int = 1) -> bool:
        """Try to acquire tokens from bucket."""
        async with self._lock:
            bucket = self._get_bucket(key)
            self._refill(bucket)
            
            if bucket["tokens"] >= tokens:
                bucket["tokens"] -= tokens
                return True
            return False
    
    async def get_info(self, key: str = "default") -> RateLimitInfo:
        """Get rate limit info for key."""
        async with self._lock:
            bucket = self._get_bucket(key)
            self._refill(bucket)
            
            tokens_needed = max(0, 1 - bucket["tokens"])
            retry_after = tokens_needed / self.rate if tokens_needed > 0 else None
            
            return RateLimitInfo(
                limit=self.capacity,
                remaining=int(bucket["tokens"]),
                reset_at=time.time() + (self.capacity - bucket["tokens"]) / self.rate,
                retry_after=retry_after,
            )


class SlidingWindowLimiter(RateLimiter):
    """
    Sliding window rate limiter.
    
    Limits requests within a rolling time window by tracking
    request timestamps.
    """
    
    def __init__(
        self,
        limit: int,
        window_seconds: float,
    ):
        """
        Initialize sliding window limiter.
        
        Args:
            limit: Maximum requests per window
            window_seconds: Window duration in seconds
        """
        self.limit = limit
        self.window_seconds = window_seconds
        self._windows: Dict[str, List[float]] = defaultdict(list)
        self._lock = asyncio.Lock()
    
    def _cleanup(self, timestamps: List[float]) -> List[float]:
        """Remove expired timestamps."""
        cutoff = time.time() - self.window_seconds
        return [ts for ts in timestamps if ts > cutoff]
    
    async def acquire(self, key: str = "default", tokens: int = 1) -> bool:
        """Try to acquire within sliding window."""
        async with self._lock:
            self._windows[key] = self._cleanup(self._windows[key])
            
            if len(self._windows[key]) + tokens <= self.limit:
                now = time.time()
                for _ in range(tokens):
                    self._windows[key].append(now)
                return True
            return False
    
    async def get_info(self, key: str = "default") -> RateLimitInfo:
        """Get rate limit info for key."""
        async with self._lock:
            self._windows[key] = self._cleanup(self._windows[key])
            timestamps = self._windows[key]
            
            remaining = max(0, self.limit - len(timestamps))
            
            if timestamps:
                oldest = min(timestamps)
                reset_at = oldest + self.window_seconds
                retry_after = reset_at - time.time() if remaining == 0 else None
            else:
                reset_at = time.time() + self.window_seconds
                retry_after = None
            
            return RateLimitInfo(
                limit=self.limit,
                remaining=remaining,
                reset_at=reset_at,
                retry_after=retry_after,
            )


class LeakyBucketLimiter(RateLimiter):
    """
    Leaky bucket rate limiter.
    
    Requests are queued and processed at a constant rate.
    The bucket has a maximum capacity; overflow is rejected.
    """
    
    def __init__(
        self,
        rate: float,
        capacity: int,
    ):
        """
        Initialize leaky bucket.
        
        Args:
            rate: Requests processed per second
            capacity: Maximum queue size
        """
        self.rate = rate
        self.capacity = capacity
        self._buckets: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()
    
    def _get_bucket(self, key: str) -> Dict[str, Any]:
        """Get or create bucket for key."""
        if key not in self._buckets:
            self._buckets[key] = {
                "level": 0.0,
                "last_leak": time.time(),
            }
        return self._buckets[key]
    
    def _leak(self, bucket: Dict[str, Any]) -> None:
        """Leak water from bucket based on elapsed time."""
        now = time.time()
        elapsed = now - bucket["last_leak"]
        leaked = elapsed * self.rate
        bucket["level"] = max(0, bucket["level"] - leaked)
        bucket["last_leak"] = now
    
    async def acquire(self, key: str = "default", tokens: int = 1) -> bool:
        """Try to add to leaky bucket."""
        async with self._lock:
            bucket = self._get_bucket(key)
            self._leak(bucket)
            
            if bucket["level"] + tokens <= self.capacity:
                bucket["level"] += tokens
                return True
            return False
    
    async def get_info(self, key: str = "default") -> RateLimitInfo:
        """Get rate limit info for key."""
        async with self._lock:
            bucket = self._get_bucket(key)
            self._leak(bucket)
            
            remaining = max(0, int(self.capacity - bucket["level"]))
            retry_after = bucket["level"] / self.rate if remaining == 0 else None
            
            return RateLimitInfo(
                limit=self.capacity,
                remaining=remaining,
                reset_at=time.time() + bucket["level"] / self.rate,
                retry_after=retry_after,
            )


class FixedWindowLimiter(RateLimiter):
    """
    Fixed window rate limiter.
    
    Limits requests within fixed time windows (e.g., per minute, per hour).
    """
    
    def __init__(
        self,
        limit: int,
        window_seconds: float,
    ):
        """
        Initialize fixed window limiter.
        
        Args:
            limit: Maximum requests per window
            window_seconds: Window duration in seconds
        """
        self.limit = limit
        self.window_seconds = window_seconds
        self._windows: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()
    
    def _get_window_key(self) -> int:
        """Get current window identifier."""
        return int(time.time() // self.window_seconds)
    
    async def acquire(self, key: str = "default", tokens: int = 1) -> bool:
        """Try to acquire within fixed window."""
        async with self._lock:
            window_key = self._get_window_key()
            
            if key not in self._windows or self._windows[key]["window"] != window_key:
                self._windows[key] = {"window": window_key, "count": 0}
            
            if self._windows[key]["count"] + tokens <= self.limit:
                self._windows[key]["count"] += tokens
                return True
            return False
    
    async def get_info(self, key: str = "default") -> RateLimitInfo:
        """Get rate limit info for key."""
        async with self._lock:
            window_key = self._get_window_key()
            
            if key not in self._windows or self._windows[key]["window"] != window_key:
                count = 0
            else:
                count = self._windows[key]["count"]
            
            remaining = max(0, self.limit - count)
            window_end = (window_key + 1) * self.window_seconds
            retry_after = window_end - time.time() if remaining == 0 else None
            
            return RateLimitInfo(
                limit=self.limit,
                remaining=remaining,
                reset_at=window_end,
                retry_after=retry_after,
            )


class ConcurrentLimiter(RateLimiter):
    """
    Concurrent request limiter.
    
    Limits the number of simultaneous in-flight requests.
    """
    
    def __init__(self, limit: int):
        """
        Initialize concurrent limiter.
        
        Args:
            limit: Maximum concurrent requests
        """
        self.limit = limit
        self._semaphores: Dict[str, asyncio.Semaphore] = {}
        self._counts: Dict[str, int] = defaultdict(int)
        self._lock = asyncio.Lock()
    
    def _get_semaphore(self, key: str) -> asyncio.Semaphore:
        """Get or create semaphore for key."""
        if key not in self._semaphores:
            self._semaphores[key] = asyncio.Semaphore(self.limit)
        return self._semaphores[key]
    
    async def acquire(self, key: str = "default", tokens: int = 1) -> bool:
        """Try to acquire concurrent slot."""
        semaphore = self._get_semaphore(key)
        
        for _ in range(tokens):
            if not semaphore.locked() or semaphore._value > 0:
                await semaphore.acquire()
                async with self._lock:
                    self._counts[key] += 1
            else:
                return False
        return True
    
    async def release(self, key: str = "default", tokens: int = 1) -> None:
        """Release concurrent slots."""
        semaphore = self._get_semaphore(key)
        for _ in range(tokens):
            semaphore.release()
            async with self._lock:
                self._counts[key] = max(0, self._counts[key] - 1)
    
    async def get_info(self, key: str = "default") -> RateLimitInfo:
        """Get rate limit info for key."""
        async with self._lock:
            count = self._counts.get(key, 0)
            remaining = max(0, self.limit - count)
            
            return RateLimitInfo(
                limit=self.limit,
                remaining=remaining,
                reset_at=time.time(),  # Resets when requests complete
                retry_after=0.1 if remaining == 0 else None,
            )


class RedisRateLimiter(RateLimiter):
    """
    Distributed rate limiter using Redis.
    
    Uses Redis for distributed rate limiting across multiple instances.
    """
    
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        key_prefix: str = "ratelimit",
        limit: int = 100,
        window_seconds: float = 60,
        algorithm: LimiterType = LimiterType.SLIDING_WINDOW,
    ):
        """
        Initialize Redis rate limiter.
        
        Args:
            redis_url: Redis connection URL
            key_prefix: Prefix for Redis keys
            limit: Maximum requests per window
            window_seconds: Window duration in seconds
            algorithm: Rate limiting algorithm to use
        """
        self.redis_url = redis_url
        self.key_prefix = key_prefix
        self.limit = limit
        self.window_seconds = window_seconds
        self.algorithm = algorithm
        self._redis = None
    
    async def _get_redis(self):
        """Get Redis connection lazily."""
        if self._redis is None:
            try:
                import redis.asyncio as redis
                self._redis = redis.from_url(self.redis_url)
            except ImportError:
                raise ImportError(
                    "redis package required for RedisRateLimiter. "
                    "Install with: pip install redis"
                )
        return self._redis
    
    def _make_key(self, key: str) -> str:
        """Create Redis key."""
        return f"{self.key_prefix}:{key}"
    
    async def acquire(self, key: str = "default", tokens: int = 1) -> bool:
        """Try to acquire using Redis."""
        redis = await self._get_redis()
        redis_key = self._make_key(key)
        now = time.time()
        
        if self.algorithm == LimiterType.SLIDING_WINDOW:
            # Sliding window using sorted set
            window_start = now - self.window_seconds
            
            async with redis.pipeline(transaction=True) as pipe:
                # Remove old entries
                await pipe.zremrangebyscore(redis_key, 0, window_start)
                # Count current
                await pipe.zcard(redis_key)
                # Add new entries
                for i in range(tokens):
                    await pipe.zadd(redis_key, {f"{now}:{i}": now})
                # Set expiry
                await pipe.expire(redis_key, int(self.window_seconds) + 1)
                results = await pipe.execute()
            
            current_count = results[1]
            if current_count + tokens <= self.limit:
                return True
            
            # Remove the entries we just added
            async with redis.pipeline(transaction=True) as pipe:
                for i in range(tokens):
                    await pipe.zrem(redis_key, f"{now}:{i}")
                await pipe.execute()
            return False
        
        elif self.algorithm == LimiterType.FIXED_WINDOW:
            # Fixed window using INCR
            window_key = f"{redis_key}:{int(now // self.window_seconds)}"
            
            async with redis.pipeline(transaction=True) as pipe:
                await pipe.incrby(window_key, tokens)
                await pipe.expire(window_key, int(self.window_seconds) + 1)
                results = await pipe.execute()
            
            count = results[0]
            if count <= self.limit:
                return True
            
            # Revert
            await redis.decrby(window_key, tokens)
            return False
        
        else:
            raise ValueError(f"Unsupported algorithm for Redis: {self.algorithm}")
    
    async def get_info(self, key: str = "default") -> RateLimitInfo:
        """Get rate limit info from Redis."""
        redis = await self._get_redis()
        redis_key = self._make_key(key)
        now = time.time()
        
        if self.algorithm == LimiterType.SLIDING_WINDOW:
            window_start = now - self.window_seconds
            
            async with redis.pipeline(transaction=True) as pipe:
                await pipe.zremrangebyscore(redis_key, 0, window_start)
                await pipe.zcard(redis_key)
                await pipe.zrange(redis_key, 0, 0, withscores=True)
                results = await pipe.execute()
            
            count = results[1]
            oldest = results[2]
            
            remaining = max(0, self.limit - count)
            
            if oldest:
                reset_at = oldest[0][1] + self.window_seconds
                retry_after = reset_at - now if remaining == 0 else None
            else:
                reset_at = now + self.window_seconds
                retry_after = None
            
            return RateLimitInfo(
                limit=self.limit,
                remaining=remaining,
                reset_at=reset_at,
                retry_after=retry_after,
            )
        
        elif self.algorithm == LimiterType.FIXED_WINDOW:
            window_num = int(now // self.window_seconds)
            window_key = f"{redis_key}:{window_num}"
            
            count = await redis.get(window_key)
            count = int(count) if count else 0
            
            remaining = max(0, self.limit - count)
            window_end = (window_num + 1) * self.window_seconds
            retry_after = window_end - now if remaining == 0 else None
            
            return RateLimitInfo(
                limit=self.limit,
                remaining=remaining,
                reset_at=window_end,
                retry_after=retry_after,
            )
        
        else:
            raise ValueError(f"Unsupported algorithm for Redis: {self.algorithm}")


class CompositeRateLimiter(RateLimiter):
    """
    Composite rate limiter combining multiple limiters.
    
    All limiters must allow for a request to proceed.
    """
    
    def __init__(self, limiters: List[RateLimiter]):
        """
        Initialize composite limiter.
        
        Args:
            limiters: List of rate limiters to combine
        """
        self.limiters = limiters
    
    async def acquire(self, key: str = "default", tokens: int = 1) -> bool:
        """Try to acquire from all limiters."""
        # Check all limiters first
        for limiter in self.limiters:
            if not await limiter.acquire(key, tokens):
                return False
        return True
    
    async def get_info(self, key: str = "default") -> RateLimitInfo:
        """Get combined rate limit info (most restrictive)."""
        infos = []
        for limiter in self.limiters:
            infos.append(await limiter.get_info(key))
        
        # Return most restrictive
        min_remaining = min(info.remaining for info in infos)
        max_retry = max(
            (info.retry_after or 0 for info in infos),
            default=None
        )
        earliest_reset = min(info.reset_at for info in infos)
        
        return RateLimitInfo(
            limit=min(info.limit for info in infos),
            remaining=min_remaining,
            reset_at=earliest_reset,
            retry_after=max_retry if max_retry else None,
        )


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    limiter: RateLimiter
    key_func: Optional[Callable[..., str]] = None
    tokens_func: Optional[Callable[..., int]] = None
    on_limited: Optional[Callable[[RateLimitInfo], None]] = None
    wait: bool = False
    timeout: Optional[float] = None


def rate_limit(
    limiter: RateLimiter,
    key_func: Optional[Callable[..., str]] = None,
    tokens_func: Optional[Callable[..., int]] = None,
    wait: bool = False,
    timeout: Optional[float] = None,
) -> Callable[[F], F]:
    """
    Decorator for rate limiting functions.
    
    Args:
        limiter: Rate limiter to use
        key_func: Function to extract rate limit key from args
        tokens_func: Function to calculate tokens from args
        wait: Whether to wait for tokens if rate limited
        timeout: Maximum wait time if wait=True
        
    Returns:
        Decorated function
        
    Example:
        limiter = TokenBucketLimiter(rate=1.0, capacity=10)
        
        @rate_limit(limiter, key_func=lambda user_id, **_: user_id)
        async def call_api(user_id: str, data: dict):
            ...
    """
    def decorator(func: F) -> F:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            key = key_func(*args, **kwargs) if key_func else "default"
            tokens = tokens_func(*args, **kwargs) if tokens_func else 1
            
            if wait:
                acquired = await limiter.wait_and_acquire(key, tokens, timeout)
            else:
                acquired = await limiter.acquire(key, tokens)
            
            if not acquired:
                info = await limiter.get_info(key)
                raise RateLimitExceeded(
                    f"Rate limit exceeded for key '{key}'",
                    retry_after=info.retry_after,
                    limit=info.limit,
                    remaining=info.remaining,
                )
            
            return await func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            return asyncio.run(async_wrapper(*args, **kwargs))
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


class RateLimitMiddleware:
    """
    Middleware for rate limiting in agent pipelines.
    """
    
    def __init__(
        self,
        limiter: RateLimiter,
        key_func: Optional[Callable[[Dict[str, Any]], str]] = None,
    ):
        """
        Initialize middleware.
        
        Args:
            limiter: Rate limiter to use
            key_func: Function to extract key from request context
        """
        self.limiter = limiter
        self.key_func = key_func or (lambda ctx: ctx.get("user_id", "default"))
    
    async def __call__(
        self,
        context: Dict[str, Any],
        next_handler: Callable[[Dict[str, Any]], Any],
    ) -> Any:
        """Process request with rate limiting."""
        key = self.key_func(context)
        
        if not await self.limiter.acquire(key):
            info = await self.limiter.get_info(key)
            raise RateLimitExceeded(
                f"Rate limit exceeded for key '{key}'",
                retry_after=info.retry_after,
                limit=info.limit,
                remaining=info.remaining,
            )
        
        # Add rate limit info to context
        context["rate_limit_info"] = await self.limiter.get_info(key)
        
        return await next_handler(context)


class AdaptiveRateLimiter(RateLimiter):
    """
    Adaptive rate limiter that adjusts limits based on response times.
    
    Increases limits when responses are fast, decreases when slow.
    """
    
    def __init__(
        self,
        base_limit: int,
        window_seconds: float,
        min_limit: int = 1,
        max_limit: Optional[int] = None,
        target_latency: float = 1.0,
        adjustment_factor: float = 0.1,
    ):
        """
        Initialize adaptive limiter.
        
        Args:
            base_limit: Starting limit
            window_seconds: Window duration
            min_limit: Minimum allowed limit
            max_limit: Maximum allowed limit
            target_latency: Target response time in seconds
            adjustment_factor: How much to adjust limits (0-1)
        """
        self.base_limit = base_limit
        self.window_seconds = window_seconds
        self.min_limit = min_limit
        self.max_limit = max_limit or base_limit * 10
        self.target_latency = target_latency
        self.adjustment_factor = adjustment_factor
        
        self._current_limit = base_limit
        self._latencies: List[float] = []
        self._inner_limiter = SlidingWindowLimiter(base_limit, window_seconds)
        self._lock = asyncio.Lock()
    
    async def record_latency(self, latency: float) -> None:
        """Record a response latency for adaptation."""
        async with self._lock:
            self._latencies.append(latency)
            
            # Adapt every 10 requests
            if len(self._latencies) >= 10:
                avg_latency = sum(self._latencies) / len(self._latencies)
                self._latencies.clear()
                
                if avg_latency < self.target_latency * 0.8:
                    # Responses are fast, increase limit
                    self._current_limit = min(
                        self.max_limit,
                        int(self._current_limit * (1 + self.adjustment_factor))
                    )
                elif avg_latency > self.target_latency * 1.2:
                    # Responses are slow, decrease limit
                    self._current_limit = max(
                        self.min_limit,
                        int(self._current_limit * (1 - self.adjustment_factor))
                    )
                
                # Update inner limiter
                self._inner_limiter.limit = self._current_limit
    
    async def acquire(self, key: str = "default", tokens: int = 1) -> bool:
        """Try to acquire with adaptive limit."""
        return await self._inner_limiter.acquire(key, tokens)
    
    async def get_info(self, key: str = "default") -> RateLimitInfo:
        """Get current rate limit info."""
        return await self._inner_limiter.get_info(key)


# Convenience factory functions
def create_limiter(
    limiter_type: LimiterType,
    **kwargs: Any,
) -> RateLimiter:
    """
    Create a rate limiter by type.
    
    Args:
        limiter_type: Type of limiter to create
        **kwargs: Arguments for the limiter
        
    Returns:
        Configured rate limiter
    """
    if limiter_type == LimiterType.TOKEN_BUCKET:
        return TokenBucketLimiter(
            rate=kwargs.get("rate", 1.0),
            capacity=kwargs.get("capacity", 10),
        )
    elif limiter_type == LimiterType.SLIDING_WINDOW:
        return SlidingWindowLimiter(
            limit=kwargs.get("limit", 100),
            window_seconds=kwargs.get("window_seconds", 60),
        )
    elif limiter_type == LimiterType.LEAKY_BUCKET:
        return LeakyBucketLimiter(
            rate=kwargs.get("rate", 1.0),
            capacity=kwargs.get("capacity", 10),
        )
    elif limiter_type == LimiterType.FIXED_WINDOW:
        return FixedWindowLimiter(
            limit=kwargs.get("limit", 100),
            window_seconds=kwargs.get("window_seconds", 60),
        )
    elif limiter_type == LimiterType.CONCURRENT:
        return ConcurrentLimiter(
            limit=kwargs.get("limit", 10),
        )
    else:
        raise ValueError(f"Unknown limiter type: {limiter_type}")


# Global rate limiter registry
_limiters: Dict[str, RateLimiter] = {}
_limiters_lock = threading.Lock()


def register_limiter(name: str, limiter: RateLimiter) -> None:
    """Register a named rate limiter."""
    with _limiters_lock:
        _limiters[name] = limiter


def get_limiter(name: str) -> Optional[RateLimiter]:
    """Get a registered rate limiter by name."""
    with _limiters_lock:
        return _limiters.get(name)


def per_user(limit: int = 100, window_seconds: float = 60) -> Callable[[F], F]:
    """
    Decorator for per-user rate limiting.
    
    Expects 'user_id' as first argument or keyword argument.
    """
    limiter = SlidingWindowLimiter(limit=limit, window_seconds=window_seconds)
    
    def key_func(*args, **kwargs):
        if args:
            return str(args[0])
        return kwargs.get("user_id", "anonymous")
    
    return rate_limit(limiter, key_func=key_func)


def per_ip(limit: int = 100, window_seconds: float = 60) -> Callable[[F], F]:
    """
    Decorator for per-IP rate limiting.
    
    Expects 'ip' or 'client_ip' in keyword arguments.
    """
    limiter = SlidingWindowLimiter(limit=limit, window_seconds=window_seconds)
    
    def key_func(*args, **kwargs):
        return kwargs.get("ip", kwargs.get("client_ip", "unknown"))
    
    return rate_limit(limiter, key_func=key_func)


def global_limit(limit: int = 1000, window_seconds: float = 60) -> Callable[[F], F]:
    """
    Decorator for global rate limiting across all users.
    """
    limiter = SlidingWindowLimiter(limit=limit, window_seconds=window_seconds)
    return rate_limit(limiter)


__all__ = [
    # Exceptions
    "RateLimitExceeded",
    # Enums
    "LimiterType",
    # Data classes
    "RateLimitInfo",
    "RateLimitConfig",
    # Base class
    "RateLimiter",
    # Limiter implementations
    "TokenBucketLimiter",
    "SlidingWindowLimiter",
    "LeakyBucketLimiter",
    "FixedWindowLimiter",
    "ConcurrentLimiter",
    "RedisRateLimiter",
    "CompositeRateLimiter",
    "AdaptiveRateLimiter",
    # Middleware
    "RateLimitMiddleware",
    # Decorator
    "rate_limit",
    # Factory
    "create_limiter",
    # Registry
    "register_limiter",
    "get_limiter",
    # Convenience decorators
    "per_user",
    "per_ip",
    "global_limit",
]
