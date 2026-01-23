"""
Enterprise Request Router Module.

Smart request routing, circuit breaking, retry policies,
and traffic management.

Example:
    # Create request router
    router = create_request_router()
    
    # Add route
    await router.add_route(
        pattern="/api/users/*",
        target="user-service",
        weight=100,
    )
    
    # Route request
    target = await router.route("/api/users/123")
    
    # With circuit breaker
    async with router.protected_call("user-service") as call:
        result = await call()
"""

from __future__ import annotations

import asyncio
import fnmatch
import logging
import random
import time
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Pattern,
    Tuple,
)

logger = logging.getLogger(__name__)


class RoutingError(Exception):
    """Routing error."""
    pass


class NoRouteFoundError(RoutingError):
    """No route found error."""
    pass


class CircuitOpenError(RoutingError):
    """Circuit breaker open error."""
    pass


class RouteType(str, Enum):
    """Route type."""
    EXACT = "exact"
    PREFIX = "prefix"
    PATTERN = "pattern"
    REGEX = "regex"


class CircuitState(str, Enum):
    """Circuit breaker state."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class RetryStrategy(str, Enum):
    """Retry strategy."""
    FIXED = "fixed"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    FIBONACCI = "fibonacci"


class LoadBalanceStrategy(str, Enum):
    """Load balance strategy for multi-target routes."""
    ROUND_ROBIN = "round_robin"
    RANDOM = "random"
    WEIGHTED = "weighted"
    LEAST_LATENCY = "least_latency"


@dataclass
class RouteTarget:
    """Route target."""
    service: str = ""
    weight: int = 100
    
    # Metadata
    version: str = ""
    zone: str = ""
    
    # Statistics
    request_count: int = 0
    error_count: int = 0
    total_latency_ms: float = 0.0
    
    @property
    def avg_latency_ms(self) -> float:
        if self.request_count == 0:
            return 0.0
        return self.total_latency_ms / self.request_count
    
    @property
    def error_rate(self) -> float:
        if self.request_count == 0:
            return 0.0
        return self.error_count / self.request_count


@dataclass
class Route:
    """Route definition."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    # Pattern
    pattern: str = ""
    route_type: RouteType = RouteType.PREFIX
    
    # Targets
    targets: List[RouteTarget] = field(default_factory=list)
    lb_strategy: LoadBalanceStrategy = LoadBalanceStrategy.ROUND_ROBIN
    
    # Conditions
    methods: List[str] = field(default_factory=list)  # GET, POST, etc.
    headers: Dict[str, str] = field(default_factory=dict)
    
    # Priority
    priority: int = 0
    
    # Options
    strip_prefix: bool = False
    add_prefix: str = ""
    timeout_seconds: float = 30.0
    
    # Retry
    retry_enabled: bool = True
    max_retries: int = 3
    retry_strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    
    # Circuit breaker
    circuit_breaker_enabled: bool = True
    
    # State
    enabled: bool = True
    _rr_index: int = 0
    
    # Metadata
    name: str = ""
    description: str = ""
    tags: List[str] = field(default_factory=list)


@dataclass
class CircuitBreaker:
    """Circuit breaker."""
    name: str = ""
    
    # State
    state: CircuitState = CircuitState.CLOSED
    
    # Thresholds
    failure_threshold: int = 5
    success_threshold: int = 3
    
    # Timeouts
    timeout_seconds: float = 30.0
    
    # Counters
    failure_count: int = 0
    success_count: int = 0
    
    # Timing
    last_failure: Optional[datetime] = None
    opened_at: Optional[datetime] = None
    
    @property
    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN
    
    @property
    def is_half_open(self) -> bool:
        return self.state == CircuitState.HALF_OPEN


@dataclass
class RetryPolicy:
    """Retry policy."""
    max_retries: int = 3
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    base_delay_seconds: float = 0.1
    max_delay_seconds: float = 10.0
    
    # Retry conditions
    retry_on_status_codes: List[int] = field(default_factory=lambda: [502, 503, 504])
    retry_on_exceptions: List[str] = field(default_factory=list)


@dataclass
class RoutingContext:
    """Routing context."""
    path: str = ""
    method: str = "GET"
    headers: Dict[str, str] = field(default_factory=dict)
    query_params: Dict[str, str] = field(default_factory=dict)
    
    # Client info
    client_ip: str = ""
    client_id: str = ""
    
    # Metadata
    trace_id: str = ""
    span_id: str = ""


@dataclass
class RoutingResult:
    """Routing result."""
    route: Route
    target: RouteTarget
    
    # Transformed path
    transformed_path: str = ""
    
    # Timing
    routing_time_ms: float = 0.0


@dataclass
class RouterStats:
    """Router statistics."""
    total_routes: int = 0
    active_routes: int = 0
    
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    
    avg_routing_time_ms: float = 0.0
    
    circuits_open: int = 0


# Route matcher
class RouteMatcher(ABC):
    """Route matcher."""
    
    @abstractmethod
    def matches(self, route: Route, context: RoutingContext) -> bool:
        pass


class DefaultRouteMatcher(RouteMatcher):
    """Default route matcher."""
    
    def matches(self, route: Route, context: RoutingContext) -> bool:
        # Check if route is enabled
        if not route.enabled:
            return False
        
        # Check method
        if route.methods and context.method.upper() not in route.methods:
            return False
        
        # Check headers
        for key, value in route.headers.items():
            if context.headers.get(key) != value:
                return False
        
        # Check pattern
        return self._match_pattern(route, context.path)
    
    def _match_pattern(self, route: Route, path: str) -> bool:
        if route.route_type == RouteType.EXACT:
            return path == route.pattern
        
        elif route.route_type == RouteType.PREFIX:
            return path.startswith(route.pattern)
        
        elif route.route_type == RouteType.PATTERN:
            return fnmatch.fnmatch(path, route.pattern)
        
        return False


# Target selector
class TargetSelector(ABC):
    """Target selector for load balancing."""
    
    @abstractmethod
    def select(
        self,
        route: Route,
        context: RoutingContext,
    ) -> RouteTarget:
        pass


class RoundRobinSelector(TargetSelector):
    """Round robin target selector."""
    
    def select(self, route: Route, context: RoutingContext) -> RouteTarget:
        if not route.targets:
            raise NoRouteFoundError("No targets for route")
        
        index = route._rr_index % len(route.targets)
        route._rr_index += 1
        
        return route.targets[index]


class RandomSelector(TargetSelector):
    """Random target selector."""
    
    def select(self, route: Route, context: RoutingContext) -> RouteTarget:
        if not route.targets:
            raise NoRouteFoundError("No targets for route")
        
        return random.choice(route.targets)


class WeightedSelector(TargetSelector):
    """Weighted target selector."""
    
    def select(self, route: Route, context: RoutingContext) -> RouteTarget:
        if not route.targets:
            raise NoRouteFoundError("No targets for route")
        
        total = sum(t.weight for t in route.targets)
        
        if total == 0:
            return random.choice(route.targets)
        
        r = random.randint(1, total)
        cumulative = 0
        
        for target in route.targets:
            cumulative += target.weight
            if r <= cumulative:
                return target
        
        return route.targets[-1]


class LeastLatencySelector(TargetSelector):
    """Least latency target selector."""
    
    def select(self, route: Route, context: RoutingContext) -> RouteTarget:
        if not route.targets:
            raise NoRouteFoundError("No targets for route")
        
        # Filter targets with data
        with_data = [t for t in route.targets if t.request_count > 0]
        
        if not with_data:
            return random.choice(route.targets)
        
        return min(with_data, key=lambda t: t.avg_latency_ms)


# Request router
class RequestRouter:
    """Request router."""
    
    def __init__(self):
        self._routes: Dict[str, Route] = {}
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        self._matcher = DefaultRouteMatcher()
        
        self._selectors: Dict[LoadBalanceStrategy, TargetSelector] = {
            LoadBalanceStrategy.ROUND_ROBIN: RoundRobinSelector(),
            LoadBalanceStrategy.RANDOM: RandomSelector(),
            LoadBalanceStrategy.WEIGHTED: WeightedSelector(),
            LoadBalanceStrategy.LEAST_LATENCY: LeastLatencySelector(),
        }
        
        self._listeners: List[Callable] = []
        
        # Statistics
        self._total_requests = 0
        self._successful_requests = 0
        self._failed_requests = 0
        self._routing_times: List[float] = []
    
    async def add_route(
        self,
        pattern: str,
        target: str,
        route_type: RouteType = RouteType.PREFIX,
        weight: int = 100,
        **kwargs,
    ) -> Route:
        """Add a route."""
        route = Route(
            pattern=pattern,
            route_type=route_type,
            targets=[RouteTarget(service=target, weight=weight)],
            **kwargs,
        )
        
        self._routes[route.id] = route
        
        # Create circuit breaker for target
        if route.circuit_breaker_enabled:
            self._get_or_create_circuit_breaker(target)
        
        logger.info(f"Route added: {pattern} -> {target}")
        
        return route
    
    async def add_route_with_targets(
        self,
        pattern: str,
        targets: List[Dict[str, Any]],
        route_type: RouteType = RouteType.PREFIX,
        lb_strategy: LoadBalanceStrategy = LoadBalanceStrategy.ROUND_ROBIN,
        **kwargs,
    ) -> Route:
        """Add a route with multiple targets."""
        route_targets = [RouteTarget(**t) for t in targets]
        
        route = Route(
            pattern=pattern,
            route_type=route_type,
            targets=route_targets,
            lb_strategy=lb_strategy,
            **kwargs,
        )
        
        self._routes[route.id] = route
        
        # Create circuit breakers for targets
        if route.circuit_breaker_enabled:
            for target in route_targets:
                self._get_or_create_circuit_breaker(target.service)
        
        logger.info(f"Route added: {pattern} -> {len(targets)} targets")
        
        return route
    
    async def remove_route(self, route_id: str) -> bool:
        """Remove a route."""
        if route_id in self._routes:
            del self._routes[route_id]
            return True
        return False
    
    async def route(
        self,
        path: str,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> RoutingResult:
        """Route a request."""
        start_time = time.monotonic()
        self._total_requests += 1
        
        context = RoutingContext(
            path=path,
            method=method,
            headers=headers or {},
            **kwargs,
        )
        
        # Find matching route
        route = await self._find_route(context)
        
        if not route:
            self._failed_requests += 1
            raise NoRouteFoundError(f"No route found for: {path}")
        
        # Select target
        selector = self._selectors.get(
            route.lb_strategy,
            self._selectors[LoadBalanceStrategy.ROUND_ROBIN],
        )
        
        target = selector.select(route, context)
        
        # Check circuit breaker
        if route.circuit_breaker_enabled:
            cb = self._circuit_breakers.get(target.service)
            
            if cb and cb.is_open:
                # Check if we should transition to half-open
                if cb.opened_at:
                    elapsed = (datetime.utcnow() - cb.opened_at).total_seconds()
                    if elapsed >= cb.timeout_seconds:
                        cb.state = CircuitState.HALF_OPEN
                    else:
                        self._failed_requests += 1
                        raise CircuitOpenError(f"Circuit open for: {target.service}")
        
        # Transform path
        transformed_path = self._transform_path(route, path)
        
        routing_time = (time.monotonic() - start_time) * 1000
        self._routing_times.append(routing_time)
        
        if len(self._routing_times) > 1000:
            self._routing_times = self._routing_times[-1000:]
        
        self._successful_requests += 1
        
        return RoutingResult(
            route=route,
            target=target,
            transformed_path=transformed_path,
            routing_time_ms=routing_time,
        )
    
    async def record_success(self, service: str, latency_ms: float) -> None:
        """Record successful request."""
        cb = self._circuit_breakers.get(service)
        
        if cb:
            cb.success_count += 1
            cb.failure_count = 0
            
            if cb.state == CircuitState.HALF_OPEN:
                if cb.success_count >= cb.success_threshold:
                    cb.state = CircuitState.CLOSED
                    cb.opened_at = None
                    logger.info(f"Circuit closed for: {service}")
        
        # Update target stats
        for route in self._routes.values():
            for target in route.targets:
                if target.service == service:
                    target.request_count += 1
                    target.total_latency_ms += latency_ms
    
    async def record_failure(self, service: str) -> None:
        """Record failed request."""
        cb = self._circuit_breakers.get(service)
        
        if cb:
            cb.failure_count += 1
            cb.success_count = 0
            cb.last_failure = datetime.utcnow()
            
            if cb.failure_count >= cb.failure_threshold:
                cb.state = CircuitState.OPEN
                cb.opened_at = datetime.utcnow()
                logger.warning(f"Circuit opened for: {service}")
        
        # Update target stats
        for route in self._routes.values():
            for target in route.targets:
                if target.service == service:
                    target.request_count += 1
                    target.error_count += 1
    
    def protected_call(self, service: str):
        """Context manager for protected calls."""
        return CircuitBreakerContext(self, service)
    
    async def calculate_retry_delay(
        self,
        attempt: int,
        policy: RetryPolicy,
    ) -> float:
        """Calculate retry delay."""
        if policy.strategy == RetryStrategy.FIXED:
            delay = policy.base_delay_seconds
        
        elif policy.strategy == RetryStrategy.LINEAR:
            delay = policy.base_delay_seconds * attempt
        
        elif policy.strategy == RetryStrategy.EXPONENTIAL:
            delay = policy.base_delay_seconds * (2 ** (attempt - 1))
        
        elif policy.strategy == RetryStrategy.FIBONACCI:
            a, b = 1, 1
            for _ in range(attempt - 1):
                a, b = b, a + b
            delay = policy.base_delay_seconds * a
        
        else:
            delay = policy.base_delay_seconds
        
        # Add jitter
        jitter = delay * random.uniform(0, 0.1)
        delay = delay + jitter
        
        return min(delay, policy.max_delay_seconds)
    
    async def get_circuit_breaker_status(self, service: str) -> Optional[Dict[str, Any]]:
        """Get circuit breaker status."""
        cb = self._circuit_breakers.get(service)
        
        if not cb:
            return None
        
        return {
            "name": cb.name,
            "state": cb.state.value,
            "failure_count": cb.failure_count,
            "success_count": cb.success_count,
            "opened_at": cb.opened_at.isoformat() if cb.opened_at else None,
        }
    
    async def reset_circuit_breaker(self, service: str) -> bool:
        """Reset circuit breaker."""
        cb = self._circuit_breakers.get(service)
        
        if cb:
            cb.state = CircuitState.CLOSED
            cb.failure_count = 0
            cb.success_count = 0
            cb.opened_at = None
            logger.info(f"Circuit breaker reset for: {service}")
            return True
        
        return False
    
    async def get_stats(self) -> RouterStats:
        """Get router statistics."""
        avg_routing_time = (
            sum(self._routing_times) / len(self._routing_times)
            if self._routing_times else 0.0
        )
        
        circuits_open = sum(
            1 for cb in self._circuit_breakers.values()
            if cb.is_open
        )
        
        return RouterStats(
            total_routes=len(self._routes),
            active_routes=sum(1 for r in self._routes.values() if r.enabled),
            total_requests=self._total_requests,
            successful_requests=self._successful_requests,
            failed_requests=self._failed_requests,
            avg_routing_time_ms=avg_routing_time,
            circuits_open=circuits_open,
        )
    
    async def list_routes(self) -> List[Route]:
        """List all routes."""
        return list(self._routes.values())
    
    async def _find_route(self, context: RoutingContext) -> Optional[Route]:
        """Find matching route."""
        matching = [
            route for route in self._routes.values()
            if self._matcher.matches(route, context)
        ]
        
        if not matching:
            return None
        
        # Sort by priority (higher first)
        matching.sort(key=lambda r: r.priority, reverse=True)
        
        return matching[0]
    
    def _transform_path(self, route: Route, path: str) -> str:
        """Transform path based on route config."""
        result = path
        
        if route.strip_prefix and route.route_type == RouteType.PREFIX:
            result = path[len(route.pattern):] or "/"
        
        if route.add_prefix:
            result = route.add_prefix + result
        
        return result
    
    def _get_or_create_circuit_breaker(self, service: str) -> CircuitBreaker:
        """Get or create circuit breaker."""
        if service not in self._circuit_breakers:
            self._circuit_breakers[service] = CircuitBreaker(name=service)
        
        return self._circuit_breakers[service]
    
    def add_listener(self, listener: Callable) -> None:
        """Add event listener."""
        self._listeners.append(listener)


# Circuit breaker context manager
class CircuitBreakerContext:
    """Circuit breaker context manager."""
    
    def __init__(self, router: RequestRouter, service: str):
        self._router = router
        self._service = service
        self._start_time = 0.0
    
    async def __aenter__(self):
        cb = self._router._circuit_breakers.get(self._service)
        
        if cb and cb.is_open:
            if cb.opened_at:
                elapsed = (datetime.utcnow() - cb.opened_at).total_seconds()
                if elapsed >= cb.timeout_seconds:
                    cb.state = CircuitState.HALF_OPEN
                else:
                    raise CircuitOpenError(f"Circuit open for: {self._service}")
        
        self._start_time = time.monotonic()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        latency = (time.monotonic() - self._start_time) * 1000
        
        if exc_type is None:
            await self._router.record_success(self._service, latency)
        else:
            await self._router.record_failure(self._service)
        
        return False  # Don't suppress exceptions


# Factory functions
def create_request_router() -> RequestRouter:
    """Create request router."""
    return RequestRouter()


def create_route(
    pattern: str,
    target: str,
    **kwargs,
) -> Route:
    """Create a route."""
    return Route(
        pattern=pattern,
        targets=[RouteTarget(service=target)],
        **kwargs,
    )


def create_retry_policy(
    max_retries: int = 3,
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL,
    **kwargs,
) -> RetryPolicy:
    """Create retry policy."""
    return RetryPolicy(
        max_retries=max_retries,
        strategy=strategy,
        **kwargs,
    )


__all__ = [
    # Exceptions
    "RoutingError",
    "NoRouteFoundError",
    "CircuitOpenError",
    # Enums
    "RouteType",
    "CircuitState",
    "RetryStrategy",
    "LoadBalanceStrategy",
    # Data classes
    "RouteTarget",
    "Route",
    "CircuitBreaker",
    "RetryPolicy",
    "RoutingContext",
    "RoutingResult",
    "RouterStats",
    # Matcher
    "RouteMatcher",
    "DefaultRouteMatcher",
    # Selector
    "TargetSelector",
    "RoundRobinSelector",
    "RandomSelector",
    "WeightedSelector",
    "LeastLatencySelector",
    # Router
    "RequestRouter",
    "CircuitBreakerContext",
    # Factory functions
    "create_request_router",
    "create_route",
    "create_retry_policy",
]
