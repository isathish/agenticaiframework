"""
Enterprise Router Module.

Provides intelligent request routing, load balancing, and A/B testing
for distributing requests across multiple backends.

Example:
    # Simple routing
    router = Router()
    router.add_route("openai", openai_handler, weight=0.7)
    router.add_route("anthropic", anthropic_handler, weight=0.3)
    
    result = await router.route(request)
    
    # A/B testing
    ab_router = ABTestRouter(
        control=openai_handler,
        variant=new_handler,
        variant_percentage=0.1,
    )
"""

from __future__ import annotations

import asyncio
import random
import hashlib
import time
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
    Type,
    TypeVar,
    Union,
)
from enum import Enum
import logging

logger = logging.getLogger(__name__)

T = TypeVar("T")
R = TypeVar("R")


class RoutingError(Exception):
    """Routing operation failed."""
    pass


class NoRouteError(RoutingError):
    """No route available for request."""
    pass


class RoutingStrategy(str, Enum):
    """Routing strategies."""
    RANDOM = "random"
    ROUND_ROBIN = "round_robin"
    WEIGHTED = "weighted"
    LEAST_LATENCY = "least_latency"
    LEAST_CONNECTIONS = "least_connections"
    CONSISTENT_HASH = "consistent_hash"
    PRIORITY = "priority"


@dataclass
class RouteStats:
    """Statistics for a route."""
    name: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_latency: float = 0.0
    current_connections: int = 0
    last_used: Optional[float] = None
    last_error: Optional[str] = None
    
    @property
    def average_latency(self) -> float:
        """Average latency in seconds."""
        if self.total_requests == 0:
            return 0.0
        return self.total_latency / self.total_requests
    
    @property
    def success_rate(self) -> float:
        """Success rate as percentage."""
        if self.total_requests == 0:
            return 100.0
        return (self.successful_requests / self.total_requests) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "average_latency": self.average_latency,
            "success_rate": self.success_rate,
            "current_connections": self.current_connections,
        }


@dataclass
class Route:
    """Definition of a route."""
    name: str
    handler: Callable
    weight: float = 1.0
    priority: int = 0
    enabled: bool = True
    max_connections: int = 100
    timeout: float = 30.0
    retry_on_fail: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Runtime state
    stats: RouteStats = field(default_factory=lambda: RouteStats(""))
    is_healthy: bool = True
    
    def __post_init__(self):
        self.stats = RouteStats(name=self.name)


class RouteSelector(ABC):
    """Abstract route selector."""
    
    @abstractmethod
    def select(self, routes: List[Route], context: Dict[str, Any]) -> Route:
        """Select a route from available routes."""
        pass


class RandomSelector(RouteSelector):
    """Random route selection."""
    
    def select(self, routes: List[Route], context: Dict[str, Any]) -> Route:
        available = [r for r in routes if r.enabled and r.is_healthy]
        if not available:
            raise NoRouteError("No available routes")
        return random.choice(available)


class RoundRobinSelector(RouteSelector):
    """Round-robin route selection."""
    
    def __init__(self):
        self._index = 0
        self._lock = asyncio.Lock()
    
    def select(self, routes: List[Route], context: Dict[str, Any]) -> Route:
        available = [r for r in routes if r.enabled and r.is_healthy]
        if not available:
            raise NoRouteError("No available routes")
        
        route = available[self._index % len(available)]
        self._index = (self._index + 1) % len(available)
        return route


class WeightedSelector(RouteSelector):
    """Weighted random route selection."""
    
    def select(self, routes: List[Route], context: Dict[str, Any]) -> Route:
        available = [r for r in routes if r.enabled and r.is_healthy]
        if not available:
            raise NoRouteError("No available routes")
        
        total_weight = sum(r.weight for r in available)
        r = random.uniform(0, total_weight)
        
        cumulative = 0
        for route in available:
            cumulative += route.weight
            if r <= cumulative:
                return route
        
        return available[-1]


class LeastLatencySelector(RouteSelector):
    """Select route with lowest average latency."""
    
    def select(self, routes: List[Route], context: Dict[str, Any]) -> Route:
        available = [r for r in routes if r.enabled and r.is_healthy]
        if not available:
            raise NoRouteError("No available routes")
        
        # Prefer routes with some history
        with_history = [r for r in available if r.stats.total_requests > 0]
        if not with_history:
            return random.choice(available)
        
        return min(with_history, key=lambda r: r.stats.average_latency)


class LeastConnectionsSelector(RouteSelector):
    """Select route with fewest active connections."""
    
    def select(self, routes: List[Route], context: Dict[str, Any]) -> Route:
        available = [r for r in routes if r.enabled and r.is_healthy]
        if not available:
            raise NoRouteError("No available routes")
        
        # Filter by max connections
        under_limit = [
            r for r in available 
            if r.stats.current_connections < r.max_connections
        ]
        if not under_limit:
            raise NoRouteError("All routes at connection limit")
        
        return min(under_limit, key=lambda r: r.stats.current_connections)


class ConsistentHashSelector(RouteSelector):
    """Consistent hash-based route selection."""
    
    def __init__(self, hash_key: str = "user_id"):
        self.hash_key = hash_key
    
    def select(self, routes: List[Route], context: Dict[str, Any]) -> Route:
        available = [r for r in routes if r.enabled and r.is_healthy]
        if not available:
            raise NoRouteError("No available routes")
        
        # Get hash key from context
        hash_value = context.get(self.hash_key, str(random.random()))
        
        # Hash to select route
        hash_int = int(hashlib.md5(str(hash_value).encode()).hexdigest(), 16)
        index = hash_int % len(available)
        
        return available[index]


class PrioritySelector(RouteSelector):
    """Select route by priority."""
    
    def select(self, routes: List[Route], context: Dict[str, Any]) -> Route:
        available = [r for r in routes if r.enabled and r.is_healthy]
        if not available:
            raise NoRouteError("No available routes")
        
        # Sort by priority (higher first)
        sorted_routes = sorted(available, key=lambda r: r.priority, reverse=True)
        return sorted_routes[0]


class Router(Generic[T, R]):
    """
    Intelligent request router with multiple strategies.
    """
    
    SELECTORS = {
        RoutingStrategy.RANDOM: RandomSelector,
        RoutingStrategy.ROUND_ROBIN: RoundRobinSelector,
        RoutingStrategy.WEIGHTED: WeightedSelector,
        RoutingStrategy.LEAST_LATENCY: LeastLatencySelector,
        RoutingStrategy.LEAST_CONNECTIONS: LeastConnectionsSelector,
        RoutingStrategy.CONSISTENT_HASH: ConsistentHashSelector,
        RoutingStrategy.PRIORITY: PrioritySelector,
    }
    
    def __init__(
        self,
        strategy: RoutingStrategy = RoutingStrategy.WEIGHTED,
        fallback_on_error: bool = True,
        max_retries: int = 3,
        health_check_interval: float = 60.0,
    ):
        """
        Initialize router.
        
        Args:
            strategy: Routing strategy
            fallback_on_error: Try next route on error
            max_retries: Maximum retry attempts
            health_check_interval: Seconds between health checks
        """
        self.strategy = strategy
        self.fallback_on_error = fallback_on_error
        self.max_retries = max_retries
        self.health_check_interval = health_check_interval
        
        self._routes: Dict[str, Route] = {}
        self._selector = self.SELECTORS[strategy]()
        self._health_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
    
    def add_route(
        self,
        name: str,
        handler: Callable[[T], R],
        weight: float = 1.0,
        priority: int = 0,
        **kwargs: Any,
    ) -> 'Router':
        """
        Add a route.
        
        Args:
            name: Route name
            handler: Handler function
            weight: Route weight for weighted routing
            priority: Route priority
            **kwargs: Additional route options
        """
        route = Route(
            name=name,
            handler=handler,
            weight=weight,
            priority=priority,
            **kwargs,
        )
        self._routes[name] = route
        return self
    
    def remove_route(self, name: str) -> bool:
        """Remove a route."""
        if name in self._routes:
            del self._routes[name]
            return True
        return False
    
    def enable_route(self, name: str) -> bool:
        """Enable a route."""
        if name in self._routes:
            self._routes[name].enabled = True
            return True
        return False
    
    def disable_route(self, name: str) -> bool:
        """Disable a route."""
        if name in self._routes:
            self._routes[name].enabled = False
            return True
        return False
    
    async def route(
        self,
        request: T,
        context: Optional[Dict[str, Any]] = None,
    ) -> R:
        """
        Route a request to an appropriate handler.
        
        Args:
            request: Request to route
            context: Optional routing context
            
        Returns:
            Response from handler
        """
        context = context or {}
        routes = list(self._routes.values())
        tried: Set[str] = set()
        last_error: Optional[Exception] = None
        
        for attempt in range(self.max_retries):
            # Select route
            available = [r for r in routes if r.name not in tried]
            if not available:
                break
            
            try:
                route = self._selector.select(available, context)
            except NoRouteError:
                break
            
            tried.add(route.name)
            
            # Execute handler
            start = time.time()
            route.stats.current_connections += 1
            
            try:
                if asyncio.iscoroutinefunction(route.handler):
                    result = await asyncio.wait_for(
                        route.handler(request),
                        timeout=route.timeout,
                    )
                else:
                    result = route.handler(request)
                
                # Update stats
                latency = time.time() - start
                route.stats.total_requests += 1
                route.stats.successful_requests += 1
                route.stats.total_latency += latency
                route.stats.last_used = time.time()
                
                return result
                
            except Exception as e:
                route.stats.total_requests += 1
                route.stats.failed_requests += 1
                route.stats.last_error = str(e)
                last_error = e
                
                logger.warning(f"Route {route.name} failed: {e}")
                
                if not self.fallback_on_error:
                    raise
                
            finally:
                route.stats.current_connections -= 1
        
        raise last_error or NoRouteError("All routes exhausted")
    
    def get_stats(self) -> Dict[str, RouteStats]:
        """Get statistics for all routes."""
        return {name: route.stats for name, route in self._routes.items()}
    
    async def start_health_checks(self) -> None:
        """Start background health checking."""
        if self._health_task:
            return
        
        self._health_task = asyncio.create_task(self._health_loop())
    
    async def stop_health_checks(self) -> None:
        """Stop background health checking."""
        if self._health_task:
            self._health_task.cancel()
            self._health_task = None
    
    async def _health_loop(self) -> None:
        """Background health check loop."""
        while True:
            try:
                await asyncio.sleep(self.health_check_interval)
                await self._check_health()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")
    
    async def _check_health(self) -> None:
        """Check health of all routes."""
        for route in self._routes.values():
            # Mark unhealthy if too many recent failures
            if route.stats.total_requests > 10:
                if route.stats.success_rate < 50:
                    route.is_healthy = False
                    logger.warning(f"Route {route.name} marked unhealthy")
                elif route.stats.success_rate > 80:
                    route.is_healthy = True


@dataclass
class ABTestResult:
    """Result of an A/B test request."""
    variant: str
    result: Any
    latency: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class ABTestRouter:
    """
    A/B testing router for comparing two handlers.
    """
    
    def __init__(
        self,
        control: Callable,
        variant: Callable,
        variant_percentage: float = 0.1,
        sticky_sessions: bool = True,
        session_key: str = "user_id",
    ):
        """
        Initialize A/B test router.
        
        Args:
            control: Control handler (A)
            variant: Variant handler (B)
            variant_percentage: Percentage of traffic to variant (0-1)
            sticky_sessions: Same user always gets same variant
            session_key: Key for session stickiness
        """
        self.control = control
        self.variant = variant
        self.variant_percentage = variant_percentage
        self.sticky_sessions = sticky_sessions
        self.session_key = session_key
        
        self._control_stats = RouteStats(name="control")
        self._variant_stats = RouteStats(name="variant")
        self._assignments: Dict[str, str] = {}
    
    def _get_variant(self, context: Dict[str, Any]) -> str:
        """Determine which variant to use."""
        if self.sticky_sessions and self.session_key in context:
            session_id = str(context[self.session_key])
            
            if session_id in self._assignments:
                return self._assignments[session_id]
            
            # Use hash for consistent assignment
            hash_int = int(hashlib.md5(session_id.encode()).hexdigest(), 16)
            is_variant = (hash_int % 100) < (self.variant_percentage * 100)
            variant = "variant" if is_variant else "control"
            
            self._assignments[session_id] = variant
            return variant
        
        return "variant" if random.random() < self.variant_percentage else "control"
    
    async def route(
        self,
        request: Any,
        context: Optional[Dict[str, Any]] = None,
    ) -> ABTestResult:
        """
        Route request to control or variant.
        
        Args:
            request: Request to route
            context: Optional context for assignment
            
        Returns:
            ABTestResult with variant info and result
        """
        context = context or {}
        variant = self._get_variant(context)
        
        handler = self.variant if variant == "variant" else self.control
        stats = self._variant_stats if variant == "variant" else self._control_stats
        
        start = time.time()
        
        try:
            if asyncio.iscoroutinefunction(handler):
                result = await handler(request)
            else:
                result = handler(request)
            
            latency = time.time() - start
            stats.total_requests += 1
            stats.successful_requests += 1
            stats.total_latency += latency
            
            return ABTestResult(
                variant=variant,
                result=result,
                latency=latency,
            )
            
        except Exception as e:
            stats.total_requests += 1
            stats.failed_requests += 1
            stats.last_error = str(e)
            raise
    
    def get_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get A/B test statistics."""
        return {
            "control": self._control_stats.to_dict(),
            "variant": self._variant_stats.to_dict(),
            "variant_percentage": self.variant_percentage,
            "total_assignments": len(self._assignments),
        }
    
    def analyze(self) -> Dict[str, Any]:
        """Analyze A/B test results."""
        c = self._control_stats
        v = self._variant_stats
        
        analysis = {
            "control": {
                "requests": c.total_requests,
                "success_rate": c.success_rate,
                "avg_latency": c.average_latency,
            },
            "variant": {
                "requests": v.total_requests,
                "success_rate": v.success_rate,
                "avg_latency": v.average_latency,
            },
        }
        
        # Calculate improvement
        if c.average_latency > 0:
            latency_improvement = ((c.average_latency - v.average_latency) / c.average_latency) * 100
            analysis["latency_improvement_pct"] = latency_improvement
        
        if c.success_rate > 0:
            success_improvement = v.success_rate - c.success_rate
            analysis["success_rate_improvement_pct"] = success_improvement
        
        return analysis


class CanaryRouter:
    """
    Canary deployment router for gradual rollouts.
    """
    
    def __init__(
        self,
        stable: Callable,
        canary: Callable,
        initial_percentage: float = 0.01,
        max_percentage: float = 1.0,
        increment_step: float = 0.05,
        error_threshold: float = 0.05,
    ):
        """
        Initialize canary router.
        
        Args:
            stable: Stable handler
            canary: Canary handler
            initial_percentage: Starting canary percentage
            max_percentage: Maximum canary percentage
            increment_step: Percentage to increment on success
            error_threshold: Error rate to trigger rollback
        """
        self.stable = stable
        self.canary = canary
        self.current_percentage = initial_percentage
        self.max_percentage = max_percentage
        self.increment_step = increment_step
        self.error_threshold = error_threshold
        
        self._stable_stats = RouteStats(name="stable")
        self._canary_stats = RouteStats(name="canary")
        self._is_rolled_back = False
    
    async def route(self, request: Any) -> Any:
        """Route request to stable or canary."""
        if self._is_rolled_back:
            use_canary = False
        else:
            use_canary = random.random() < self.current_percentage
        
        handler = self.canary if use_canary else self.stable
        stats = self._canary_stats if use_canary else self._stable_stats
        
        start = time.time()
        
        try:
            if asyncio.iscoroutinefunction(handler):
                result = await handler(request)
            else:
                result = handler(request)
            
            stats.total_requests += 1
            stats.successful_requests += 1
            stats.total_latency += time.time() - start
            
            return result
            
        except Exception as e:
            stats.total_requests += 1
            stats.failed_requests += 1
            
            # Check for rollback
            if use_canary and self._should_rollback():
                self.rollback()
            
            raise
    
    def _should_rollback(self) -> bool:
        """Check if canary should be rolled back."""
        if self._canary_stats.total_requests < 10:
            return False
        
        error_rate = self._canary_stats.failed_requests / self._canary_stats.total_requests
        return error_rate > self.error_threshold
    
    def rollback(self) -> None:
        """Rollback to stable."""
        self._is_rolled_back = True
        self.current_percentage = 0
        logger.warning("Canary rolled back due to high error rate")
    
    def promote(self) -> None:
        """Increment canary percentage."""
        if not self._is_rolled_back:
            self.current_percentage = min(
                self.current_percentage + self.increment_step,
                self.max_percentage,
            )
            logger.info(f"Canary promoted to {self.current_percentage * 100}%")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get canary statistics."""
        return {
            "stable": self._stable_stats.to_dict(),
            "canary": self._canary_stats.to_dict(),
            "current_percentage": self.current_percentage,
            "is_rolled_back": self._is_rolled_back,
        }


__all__ = [
    # Exceptions
    "RoutingError",
    "NoRouteError",
    # Enums
    "RoutingStrategy",
    # Data classes
    "RouteStats",
    "Route",
    "ABTestResult",
    # Selectors
    "RouteSelector",
    "RandomSelector",
    "RoundRobinSelector",
    "WeightedSelector",
    "LeastLatencySelector",
    "LeastConnectionsSelector",
    "ConsistentHashSelector",
    "PrioritySelector",
    # Routers
    "Router",
    "ABTestRouter",
    "CanaryRouter",
]
