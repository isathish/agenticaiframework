"""
Enterprise Throttle Manager Module.

Advanced request throttling, adaptive rate limiting,
backpressure management, and traffic shaping.

Example:
    # Create throttle manager
    throttler = create_throttle_manager()
    
    # Create throttle rule
    await throttler.create_rule(
        name="api_requests",
        limit=1000,
        window_seconds=60,
        algorithm=ThrottleAlgorithm.SLIDING_WINDOW,
    )
    
    # Check request
    allowed = await throttler.check("api_requests", client_id="user123")
    
    # Acquire with backoff
    async with throttler.acquire("api_requests", client_id="user123"):
        # Make request
        pass
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
)

logger = logging.getLogger(__name__)


class ThrottleError(Exception):
    """Throttle error."""
    pass


class RateLimitExceededError(ThrottleError):
    """Rate limit exceeded error."""
    pass


class ThrottleAlgorithm(str, Enum):
    """Throttle algorithm."""
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
    DEGRADE = "degrade"


class BackoffStrategy(str, Enum):
    """Backoff strategy."""
    FIXED = "fixed"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    JITTER = "jitter"


@dataclass
class ThrottleRule:
    """Throttle rule."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    
    # Limits
    limit: int = 100
    window_seconds: float = 60.0
    burst_limit: Optional[int] = None
    
    # Algorithm
    algorithm: ThrottleAlgorithm = ThrottleAlgorithm.SLIDING_WINDOW
    
    # Actions
    action: ThrottleAction = ThrottleAction.REJECT
    
    # Backoff
    backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL
    backoff_base_seconds: float = 1.0
    backoff_max_seconds: float = 60.0
    
    # Scope
    per_client: bool = True
    client_id_header: str = "X-Client-ID"
    
    # Configuration
    enabled: bool = True
    priority: int = 0
    
    # Metadata
    description: str = ""
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ThrottleState:
    """Throttle state for a client/rule."""
    rule_name: str = ""
    client_id: str = ""
    
    # Counters
    request_count: int = 0
    tokens: float = 0.0
    
    # Timing
    window_start: float = 0.0
    last_request: float = 0.0
    last_refill: float = 0.0
    
    # History (for sliding window)
    request_times: deque = field(default_factory=deque)
    
    # Backoff
    consecutive_throttles: int = 0
    next_allowed_time: float = 0.0


@dataclass
class ThrottleResult:
    """Throttle check result."""
    allowed: bool = True
    rule_name: str = ""
    client_id: str = ""
    
    # Current state
    remaining: int = 0
    limit: int = 0
    reset_at: float = 0.0
    
    # Wait time
    retry_after_seconds: float = 0.0
    
    # Headers
    headers: Dict[str, str] = field(default_factory=dict)


@dataclass
class ThrottleStats:
    """Throttle statistics."""
    total_rules: int = 0
    total_requests: int = 0
    allowed_requests: int = 0
    throttled_requests: int = 0
    throttle_rate: float = 0.0


@dataclass
class ClientStats:
    """Client throttle statistics."""
    client_id: str = ""
    total_requests: int = 0
    throttled_requests: int = 0
    last_request_at: Optional[datetime] = None
    avg_requests_per_minute: float = 0.0


# Throttle algorithm implementations
class ThrottleAlgorithmImpl(ABC):
    """Throttle algorithm implementation."""
    
    @abstractmethod
    def check(
        self,
        state: ThrottleState,
        rule: ThrottleRule,
        now: float,
    ) -> Tuple[bool, int]:
        """Check if request is allowed. Returns (allowed, remaining)."""
        pass
    
    @abstractmethod
    def consume(
        self,
        state: ThrottleState,
        rule: ThrottleRule,
        now: float,
        count: int = 1,
    ) -> None:
        """Consume from limit."""
        pass


class FixedWindowAlgorithm(ThrottleAlgorithmImpl):
    """Fixed window algorithm."""
    
    def check(
        self,
        state: ThrottleState,
        rule: ThrottleRule,
        now: float,
    ) -> Tuple[bool, int]:
        window_start = int(now / rule.window_seconds) * rule.window_seconds
        
        if state.window_start != window_start:
            state.window_start = window_start
            state.request_count = 0
        
        remaining = rule.limit - state.request_count
        allowed = remaining > 0
        
        return allowed, max(0, remaining)
    
    def consume(
        self,
        state: ThrottleState,
        rule: ThrottleRule,
        now: float,
        count: int = 1,
    ) -> None:
        window_start = int(now / rule.window_seconds) * rule.window_seconds
        
        if state.window_start != window_start:
            state.window_start = window_start
            state.request_count = 0
        
        state.request_count += count
        state.last_request = now


class SlidingWindowAlgorithm(ThrottleAlgorithmImpl):
    """Sliding window algorithm."""
    
    def check(
        self,
        state: ThrottleState,
        rule: ThrottleRule,
        now: float,
    ) -> Tuple[bool, int]:
        # Remove expired entries
        cutoff = now - rule.window_seconds
        while state.request_times and state.request_times[0] < cutoff:
            state.request_times.popleft()
        
        remaining = rule.limit - len(state.request_times)
        allowed = remaining > 0
        
        return allowed, max(0, remaining)
    
    def consume(
        self,
        state: ThrottleState,
        rule: ThrottleRule,
        now: float,
        count: int = 1,
    ) -> None:
        for _ in range(count):
            state.request_times.append(now)
        state.last_request = now


class TokenBucketAlgorithm(ThrottleAlgorithmImpl):
    """Token bucket algorithm."""
    
    def check(
        self,
        state: ThrottleState,
        rule: ThrottleRule,
        now: float,
    ) -> Tuple[bool, int]:
        self._refill(state, rule, now)
        
        allowed = state.tokens >= 1.0
        remaining = int(state.tokens)
        
        return allowed, remaining
    
    def consume(
        self,
        state: ThrottleState,
        rule: ThrottleRule,
        now: float,
        count: int = 1,
    ) -> None:
        self._refill(state, rule, now)
        state.tokens = max(0, state.tokens - count)
        state.last_request = now
    
    def _refill(
        self,
        state: ThrottleState,
        rule: ThrottleRule,
        now: float,
    ) -> None:
        if state.last_refill == 0:
            state.tokens = float(rule.burst_limit or rule.limit)
            state.last_refill = now
            return
        
        elapsed = now - state.last_refill
        refill_rate = rule.limit / rule.window_seconds
        new_tokens = elapsed * refill_rate
        
        max_tokens = float(rule.burst_limit or rule.limit)
        state.tokens = min(max_tokens, state.tokens + new_tokens)
        state.last_refill = now


class LeakyBucketAlgorithm(ThrottleAlgorithmImpl):
    """Leaky bucket algorithm."""
    
    def check(
        self,
        state: ThrottleState,
        rule: ThrottleRule,
        now: float,
    ) -> Tuple[bool, int]:
        self._drain(state, rule, now)
        
        max_bucket = rule.burst_limit or rule.limit
        allowed = state.request_count < max_bucket
        remaining = max_bucket - state.request_count
        
        return allowed, max(0, remaining)
    
    def consume(
        self,
        state: ThrottleState,
        rule: ThrottleRule,
        now: float,
        count: int = 1,
    ) -> None:
        self._drain(state, rule, now)
        state.request_count += count
        state.last_request = now
    
    def _drain(
        self,
        state: ThrottleState,
        rule: ThrottleRule,
        now: float,
    ) -> None:
        if state.last_request == 0:
            state.request_count = 0
            return
        
        elapsed = now - state.last_request
        drain_rate = rule.limit / rule.window_seconds
        drained = int(elapsed * drain_rate)
        
        state.request_count = max(0, state.request_count - drained)


class AdaptiveAlgorithm(ThrottleAlgorithmImpl):
    """Adaptive algorithm that adjusts based on system load."""
    
    def __init__(self, load_factor_fn: Optional[Callable[[], float]] = None):
        self._load_factor_fn = load_factor_fn or (lambda: 0.5)
        self._base_algorithm = SlidingWindowAlgorithm()
    
    def check(
        self,
        state: ThrottleState,
        rule: ThrottleRule,
        now: float,
    ) -> Tuple[bool, int]:
        load_factor = self._load_factor_fn()
        
        # Reduce limit based on load
        adjusted_limit = int(rule.limit * (1.0 - load_factor * 0.5))
        adjusted_rule = ThrottleRule(
            limit=max(1, adjusted_limit),
            window_seconds=rule.window_seconds,
        )
        
        return self._base_algorithm.check(state, adjusted_rule, now)
    
    def consume(
        self,
        state: ThrottleState,
        rule: ThrottleRule,
        now: float,
        count: int = 1,
    ) -> None:
        self._base_algorithm.consume(state, rule, now, count)


# Backoff calculator
class BackoffCalculator:
    """Backoff calculator."""
    
    @staticmethod
    def calculate(
        strategy: BackoffStrategy,
        attempt: int,
        base_seconds: float,
        max_seconds: float,
    ) -> float:
        """Calculate backoff delay."""
        if strategy == BackoffStrategy.FIXED:
            delay = base_seconds
        
        elif strategy == BackoffStrategy.LINEAR:
            delay = base_seconds * attempt
        
        elif strategy == BackoffStrategy.EXPONENTIAL:
            delay = base_seconds * (2 ** (attempt - 1))
        
        elif strategy == BackoffStrategy.JITTER:
            base_delay = base_seconds * (2 ** (attempt - 1))
            jitter = random.uniform(0, base_delay * 0.5)
            delay = base_delay + jitter
        
        else:
            delay = base_seconds
        
        return min(delay, max_seconds)


# Throttle state store
class ThrottleStateStore(ABC):
    """Throttle state storage."""
    
    @abstractmethod
    async def get(self, key: str) -> Optional[ThrottleState]:
        pass
    
    @abstractmethod
    async def set(self, key: str, state: ThrottleState) -> None:
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> None:
        pass


class InMemoryStateStore(ThrottleStateStore):
    """In-memory state store."""
    
    def __init__(self, max_entries: int = 100000):
        self._states: Dict[str, ThrottleState] = {}
        self._max_entries = max_entries
        self._access_times: Dict[str, float] = {}
    
    async def get(self, key: str) -> Optional[ThrottleState]:
        state = self._states.get(key)
        if state:
            self._access_times[key] = time.monotonic()
        return state
    
    async def set(self, key: str, state: ThrottleState) -> None:
        if len(self._states) >= self._max_entries:
            self._evict_oldest()
        
        self._states[key] = state
        self._access_times[key] = time.monotonic()
    
    async def delete(self, key: str) -> None:
        self._states.pop(key, None)
        self._access_times.pop(key, None)
    
    def _evict_oldest(self) -> None:
        if not self._access_times:
            return
        
        oldest_key = min(self._access_times, key=self._access_times.get)
        self._states.pop(oldest_key, None)
        self._access_times.pop(oldest_key, None)


# Throttle manager
class ThrottleManager:
    """Throttle manager."""
    
    def __init__(
        self,
        state_store: Optional[ThrottleStateStore] = None,
        load_factor_fn: Optional[Callable[[], float]] = None,
    ):
        self._state_store = state_store or InMemoryStateStore()
        
        self._rules: Dict[str, ThrottleRule] = {}
        
        self._algorithms: Dict[ThrottleAlgorithm, ThrottleAlgorithmImpl] = {
            ThrottleAlgorithm.FIXED_WINDOW: FixedWindowAlgorithm(),
            ThrottleAlgorithm.SLIDING_WINDOW: SlidingWindowAlgorithm(),
            ThrottleAlgorithm.TOKEN_BUCKET: TokenBucketAlgorithm(),
            ThrottleAlgorithm.LEAKY_BUCKET: LeakyBucketAlgorithm(),
            ThrottleAlgorithm.ADAPTIVE: AdaptiveAlgorithm(load_factor_fn),
        }
        
        # Statistics
        self._total_requests = 0
        self._allowed_requests = 0
        self._throttled_requests = 0
        
        self._client_stats: Dict[str, ClientStats] = {}
        self._listeners: List[Callable] = []
    
    async def create_rule(
        self,
        name: str,
        limit: int,
        window_seconds: float = 60.0,
        algorithm: Union[str, ThrottleAlgorithm] = ThrottleAlgorithm.SLIDING_WINDOW,
        action: ThrottleAction = ThrottleAction.REJECT,
        burst_limit: Optional[int] = None,
        per_client: bool = True,
        **kwargs,
    ) -> ThrottleRule:
        """Create throttle rule."""
        if isinstance(algorithm, str):
            algorithm = ThrottleAlgorithm(algorithm)
        
        rule = ThrottleRule(
            name=name,
            limit=limit,
            window_seconds=window_seconds,
            algorithm=algorithm,
            action=action,
            burst_limit=burst_limit,
            per_client=per_client,
            **kwargs,
        )
        
        self._rules[name] = rule
        
        logger.info(f"Throttle rule created: {name} ({limit}/{window_seconds}s)")
        
        return rule
    
    async def get_rule(self, name: str) -> Optional[ThrottleRule]:
        """Get throttle rule."""
        return self._rules.get(name)
    
    async def list_rules(
        self,
        enabled_only: bool = True,
    ) -> List[ThrottleRule]:
        """List throttle rules."""
        rules = list(self._rules.values())
        
        if enabled_only:
            rules = [r for r in rules if r.enabled]
        
        return sorted(rules, key=lambda r: r.priority, reverse=True)
    
    async def update_rule(
        self,
        name: str,
        **updates,
    ) -> Optional[ThrottleRule]:
        """Update throttle rule."""
        rule = self._rules.get(name)
        
        if not rule:
            return None
        
        for key, value in updates.items():
            if hasattr(rule, key):
                setattr(rule, key, value)
        
        return rule
    
    async def delete_rule(self, name: str) -> bool:
        """Delete throttle rule."""
        return self._rules.pop(name, None) is not None
    
    async def check(
        self,
        rule_name: str,
        client_id: str = "default",
        consume: bool = True,
    ) -> ThrottleResult:
        """Check if request is allowed."""
        rule = self._rules.get(rule_name)
        
        if not rule or not rule.enabled:
            return ThrottleResult(allowed=True, rule_name=rule_name)
        
        now = time.monotonic()
        
        # Get state
        state_key = f"{rule_name}:{client_id}" if rule.per_client else rule_name
        state = await self._state_store.get(state_key)
        
        if not state:
            state = ThrottleState(rule_name=rule_name, client_id=client_id)
        
        # Check backoff
        if state.next_allowed_time > now:
            wait_time = state.next_allowed_time - now
            return self._make_result(
                allowed=False,
                rule=rule,
                client_id=client_id,
                remaining=0,
                retry_after=wait_time,
            )
        
        # Get algorithm
        algorithm = self._algorithms.get(rule.algorithm)
        
        if not algorithm:
            return ThrottleResult(allowed=True, rule_name=rule_name)
        
        # Check limit
        allowed, remaining = algorithm.check(state, rule, now)
        
        # Update stats
        self._total_requests += 1
        self._update_client_stats(client_id)
        
        if allowed:
            if consume:
                algorithm.consume(state, rule, now)
            
            state.consecutive_throttles = 0
            self._allowed_requests += 1
        else:
            state.consecutive_throttles += 1
            self._throttled_requests += 1
            
            # Calculate backoff
            retry_after = BackoffCalculator.calculate(
                rule.backoff_strategy,
                state.consecutive_throttles,
                rule.backoff_base_seconds,
                rule.backoff_max_seconds,
            )
            
            state.next_allowed_time = now + retry_after
        
        await self._state_store.set(state_key, state)
        
        # Calculate reset time
        reset_at = self._calculate_reset_time(rule, now)
        
        result = self._make_result(
            allowed=allowed,
            rule=rule,
            client_id=client_id,
            remaining=remaining,
            retry_after=0 if allowed else retry_after,
            reset_at=reset_at,
        )
        
        if not allowed:
            await self._notify("throttled", result)
        
        return result
    
    @asynccontextmanager
    async def acquire(
        self,
        rule_name: str,
        client_id: str = "default",
        max_wait_seconds: float = 30.0,
    ):
        """Acquire throttle slot with waiting."""
        start_time = time.monotonic()
        
        while True:
            result = await self.check(rule_name, client_id, consume=True)
            
            if result.allowed:
                yield result
                return
            
            elapsed = time.monotonic() - start_time
            
            if elapsed >= max_wait_seconds:
                raise RateLimitExceededError(
                    f"Rate limit exceeded for {rule_name}: {result.retry_after_seconds}s"
                )
            
            wait_time = min(result.retry_after_seconds, max_wait_seconds - elapsed)
            
            if wait_time > 0:
                await asyncio.sleep(wait_time)
    
    async def reset(
        self,
        rule_name: str,
        client_id: Optional[str] = None,
    ) -> bool:
        """Reset throttle state."""
        if client_id:
            key = f"{rule_name}:{client_id}"
            await self._state_store.delete(key)
        else:
            # Would need to track all keys for this
            pass
        
        return True
    
    async def get_client_state(
        self,
        rule_name: str,
        client_id: str,
    ) -> Optional[ThrottleState]:
        """Get client throttle state."""
        rule = self._rules.get(rule_name)
        
        if not rule:
            return None
        
        state_key = f"{rule_name}:{client_id}" if rule.per_client else rule_name
        return await self._state_store.get(state_key)
    
    async def get_stats(self) -> ThrottleStats:
        """Get statistics."""
        throttle_rate = 0.0
        if self._total_requests > 0:
            throttle_rate = self._throttled_requests / self._total_requests * 100
        
        return ThrottleStats(
            total_rules=len(self._rules),
            total_requests=self._total_requests,
            allowed_requests=self._allowed_requests,
            throttled_requests=self._throttled_requests,
            throttle_rate=throttle_rate,
        )
    
    async def get_client_stats(
        self,
        client_id: str,
    ) -> Optional[ClientStats]:
        """Get client statistics."""
        return self._client_stats.get(client_id)
    
    async def get_top_clients(
        self,
        limit: int = 10,
        by: str = "total_requests",
    ) -> List[ClientStats]:
        """Get top clients by usage."""
        clients = list(self._client_stats.values())
        
        return sorted(
            clients,
            key=lambda c: getattr(c, by, 0),
            reverse=True,
        )[:limit]
    
    def _make_result(
        self,
        allowed: bool,
        rule: ThrottleRule,
        client_id: str,
        remaining: int,
        retry_after: float = 0.0,
        reset_at: float = 0.0,
    ) -> ThrottleResult:
        """Make throttle result."""
        headers = {
            "X-RateLimit-Limit": str(rule.limit),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(int(reset_at)),
        }
        
        if not allowed:
            headers["Retry-After"] = str(int(retry_after))
        
        return ThrottleResult(
            allowed=allowed,
            rule_name=rule.name,
            client_id=client_id,
            remaining=remaining,
            limit=rule.limit,
            reset_at=reset_at,
            retry_after_seconds=retry_after,
            headers=headers,
        )
    
    def _calculate_reset_time(
        self,
        rule: ThrottleRule,
        now: float,
    ) -> float:
        """Calculate reset time."""
        if rule.algorithm == ThrottleAlgorithm.FIXED_WINDOW:
            window_start = int(now / rule.window_seconds) * rule.window_seconds
            return window_start + rule.window_seconds
        else:
            return now + rule.window_seconds
    
    def _update_client_stats(self, client_id: str) -> None:
        """Update client statistics."""
        if client_id not in self._client_stats:
            self._client_stats[client_id] = ClientStats(client_id=client_id)
        
        stats = self._client_stats[client_id]
        stats.total_requests += 1
        stats.last_request_at = datetime.utcnow()
    
    async def _notify(self, event: str, data: Any) -> None:
        """Notify listeners."""
        for listener in self._listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    await listener(event, data)
                else:
                    listener(event, data)
            except Exception as e:
                logger.error(f"Listener error: {e}")
    
    def add_listener(self, listener: Callable) -> None:
        """Add event listener."""
        self._listeners.append(listener)


# Factory functions
def create_throttle_manager(
    load_factor_fn: Optional[Callable[[], float]] = None,
) -> ThrottleManager:
    """Create throttle manager."""
    return ThrottleManager(load_factor_fn=load_factor_fn)


def create_throttle_rule(
    name: str,
    limit: int,
    window_seconds: float = 60.0,
    **kwargs,
) -> ThrottleRule:
    """Create throttle rule."""
    return ThrottleRule(
        name=name,
        limit=limit,
        window_seconds=window_seconds,
        **kwargs,
    )


__all__ = [
    # Exceptions
    "ThrottleError",
    "RateLimitExceededError",
    # Enums
    "ThrottleAlgorithm",
    "ThrottleAction",
    "BackoffStrategy",
    # Data classes
    "ThrottleRule",
    "ThrottleState",
    "ThrottleResult",
    "ThrottleStats",
    "ClientStats",
    # Algorithms
    "ThrottleAlgorithmImpl",
    "FixedWindowAlgorithm",
    "SlidingWindowAlgorithm",
    "TokenBucketAlgorithm",
    "LeakyBucketAlgorithm",
    "AdaptiveAlgorithm",
    # Components
    "BackoffCalculator",
    # Store
    "ThrottleStateStore",
    "InMemoryStateStore",
    # Manager
    "ThrottleManager",
    # Factory functions
    "create_throttle_manager",
    "create_throttle_rule",
]
