"""
Enterprise Canary Deployment Module.

Provides canary deployments, feature rollout, and A/B testing
for gradual, risk-controlled releases.

Example:
    # Create canary deployer
    canary = create_canary_deployer()
    
    # Start canary deployment
    deployment = await canary.deploy(
        name="v2.0",
        target_percent=10,
        health_threshold=0.99
    )
    
    # Monitor and promote
    if await deployment.is_healthy():
        await canary.promote(deployment, percent=50)
    
    # With decorators
    @canary_route(percent=10)
    async def new_handler():
        ...
"""

from __future__ import annotations

import asyncio
import logging
import random
import uuid
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
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

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CanaryError(Exception):
    """Canary deployment error."""
    pass


class PromotionError(CanaryError):
    """Promotion error."""
    pass


class RollbackError(CanaryError):
    """Rollback error."""
    pass


class DeploymentState(str, Enum):
    """Deployment state."""
    PENDING = "pending"
    DEPLOYING = "deploying"
    ACTIVE = "active"
    PROMOTING = "promoting"
    ROLLING_BACK = "rolling_back"
    COMPLETED = "completed"
    FAILED = "failed"


class HealthStatus(str, Enum):
    """Health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class TrafficStrategy(str, Enum):
    """Traffic routing strategy."""
    RANDOM = "random"
    WEIGHTED = "weighted"
    HEADER_BASED = "header_based"
    COOKIE_BASED = "cookie_based"
    USER_SEGMENT = "user_segment"


@dataclass
class CanaryConfig:
    """Canary deployment configuration."""
    initial_percent: float = 5.0
    increment_percent: float = 10.0
    max_percent: float = 100.0
    health_threshold: float = 0.99
    min_requests: int = 100
    evaluation_period_seconds: int = 300
    auto_promote: bool = False
    auto_rollback: bool = True


@dataclass
class HealthMetrics:
    """Health metrics for canary."""
    success_rate: float = 1.0
    error_rate: float = 0.0
    latency_p50_ms: float = 0.0
    latency_p99_ms: float = 0.0
    request_count: int = 0
    error_count: int = 0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class CanaryDeployment:
    """Canary deployment record."""
    deployment_id: str
    name: str
    version: str
    state: DeploymentState
    traffic_percent: float
    health_status: HealthStatus = HealthStatus.UNKNOWN
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    baseline_version: Optional[str] = None
    metrics: Optional[HealthMetrics] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TrafficRule:
    """Traffic routing rule."""
    rule_id: str
    source_version: str
    target_version: str
    percent: float
    conditions: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0


class MetricsCollector(ABC):
    """Abstract metrics collector."""
    
    @abstractmethod
    async def collect(
        self,
        version: str,
        period_seconds: int,
    ) -> HealthMetrics:
        """Collect metrics for a version."""
        pass
    
    @abstractmethod
    async def record_request(
        self,
        version: str,
        success: bool,
        latency_ms: float,
    ) -> None:
        """Record a request."""
        pass


class InMemoryMetricsCollector(MetricsCollector):
    """In-memory metrics collector."""
    
    def __init__(self):
        self._requests: Dict[str, List[Dict[str, Any]]] = {}
        self._lock = asyncio.Lock()
    
    async def collect(
        self,
        version: str,
        period_seconds: int,
    ) -> HealthMetrics:
        cutoff = datetime.now() - timedelta(seconds=period_seconds)
        
        requests = self._requests.get(version, [])
        recent = [r for r in requests if r["timestamp"] > cutoff]
        
        if not recent:
            return HealthMetrics()
        
        success_count = sum(1 for r in recent if r["success"])
        error_count = len(recent) - success_count
        latencies = sorted(r["latency_ms"] for r in recent)
        
        p50_idx = len(latencies) // 2
        p99_idx = int(len(latencies) * 0.99)
        
        return HealthMetrics(
            success_rate=success_count / len(recent) if recent else 1.0,
            error_rate=error_count / len(recent) if recent else 0.0,
            latency_p50_ms=latencies[p50_idx] if latencies else 0.0,
            latency_p99_ms=latencies[min(p99_idx, len(latencies) - 1)] if latencies else 0.0,
            request_count=len(recent),
            error_count=error_count,
        )
    
    async def record_request(
        self,
        version: str,
        success: bool,
        latency_ms: float,
    ) -> None:
        async with self._lock:
            if version not in self._requests:
                self._requests[version] = []
            
            self._requests[version].append({
                "timestamp": datetime.now(),
                "success": success,
                "latency_ms": latency_ms,
            })
            
            # Keep last 10000 requests per version
            if len(self._requests[version]) > 10000:
                self._requests[version] = self._requests[version][-10000:]


class DeploymentStore(ABC):
    """Abstract deployment store."""
    
    @abstractmethod
    async def save(
        self,
        deployment: CanaryDeployment,
    ) -> None:
        """Save deployment."""
        pass
    
    @abstractmethod
    async def get(
        self,
        deployment_id: str,
    ) -> Optional[CanaryDeployment]:
        """Get deployment by ID."""
        pass
    
    @abstractmethod
    async def get_active(self) -> List[CanaryDeployment]:
        """Get active deployments."""
        pass
    
    @abstractmethod
    async def delete(
        self,
        deployment_id: str,
    ) -> bool:
        """Delete deployment."""
        pass


class InMemoryDeploymentStore(DeploymentStore):
    """In-memory deployment store."""
    
    def __init__(self):
        self._deployments: Dict[str, CanaryDeployment] = {}
        self._lock = asyncio.Lock()
    
    async def save(
        self,
        deployment: CanaryDeployment,
    ) -> None:
        async with self._lock:
            self._deployments[deployment.deployment_id] = deployment
    
    async def get(
        self,
        deployment_id: str,
    ) -> Optional[CanaryDeployment]:
        return self._deployments.get(deployment_id)
    
    async def get_active(self) -> List[CanaryDeployment]:
        active_states = {
            DeploymentState.DEPLOYING,
            DeploymentState.ACTIVE,
            DeploymentState.PROMOTING,
        }
        
        return [
            d for d in self._deployments.values()
            if d.state in active_states
        ]
    
    async def delete(
        self,
        deployment_id: str,
    ) -> bool:
        async with self._lock:
            if deployment_id in self._deployments:
                del self._deployments[deployment_id]
                return True
            return False


class TrafficRouter:
    """
    Traffic router for canary deployments.
    """
    
    def __init__(
        self,
        strategy: TrafficStrategy = TrafficStrategy.WEIGHTED,
    ):
        self._strategy = strategy
        self._rules: Dict[str, TrafficRule] = {}
        self._lock = asyncio.Lock()
    
    async def add_rule(self, rule: TrafficRule) -> None:
        """Add a routing rule."""
        async with self._lock:
            self._rules[rule.rule_id] = rule
    
    async def remove_rule(self, rule_id: str) -> None:
        """Remove a routing rule."""
        async with self._lock:
            self._rules.pop(rule_id, None)
    
    async def update_rule(
        self,
        rule_id: str,
        percent: float,
    ) -> None:
        """Update rule traffic percentage."""
        async with self._lock:
            if rule_id in self._rules:
                self._rules[rule_id].percent = percent
    
    def route(
        self,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Route request to a version."""
        if not self._rules:
            return None
        
        rules = sorted(
            self._rules.values(),
            key=lambda r: r.priority,
            reverse=True,
        )
        
        if self._strategy == TrafficStrategy.WEIGHTED:
            return self._weighted_route(rules)
        
        elif self._strategy == TrafficStrategy.HEADER_BASED:
            return self._header_route(rules, context)
        
        elif self._strategy == TrafficStrategy.RANDOM:
            return self._random_route(rules)
        
        return rules[0].target_version if rules else None
    
    def _weighted_route(
        self,
        rules: List[TrafficRule],
    ) -> str:
        """Weighted random routing."""
        rand = random.random() * 100
        cumulative = 0.0
        
        for rule in rules:
            cumulative += rule.percent
            if rand < cumulative:
                return rule.target_version
        
        # Default to first rule
        return rules[0].source_version if rules else ""
    
    def _random_route(
        self,
        rules: List[TrafficRule],
    ) -> str:
        """Pure random routing."""
        rule = random.choice(rules)
        return rule.target_version
    
    def _header_route(
        self,
        rules: List[TrafficRule],
        context: Optional[Dict[str, Any]],
    ) -> str:
        """Header-based routing."""
        if context:
            headers = context.get("headers", {})
            
            for rule in rules:
                required_headers = rule.conditions.get("headers", {})
                
                if all(
                    headers.get(k) == v
                    for k, v in required_headers.items()
                ):
                    return rule.target_version
        
        # Default routing
        return self._weighted_route(rules)


class HealthEvaluator:
    """
    Health evaluator for canary deployments.
    """
    
    def __init__(
        self,
        collector: MetricsCollector,
        config: Optional[CanaryConfig] = None,
    ):
        self._collector = collector
        self._config = config or CanaryConfig()
    
    async def evaluate(
        self,
        canary_version: str,
        baseline_version: Optional[str] = None,
    ) -> Tuple[HealthStatus, HealthMetrics]:
        """Evaluate canary health."""
        canary_metrics = await self._collector.collect(
            canary_version,
            self._config.evaluation_period_seconds,
        )
        
        # Not enough data
        if canary_metrics.request_count < self._config.min_requests:
            return HealthStatus.UNKNOWN, canary_metrics
        
        # Check against threshold
        if canary_metrics.success_rate >= self._config.health_threshold:
            status = HealthStatus.HEALTHY
        elif canary_metrics.success_rate >= self._config.health_threshold * 0.9:
            status = HealthStatus.DEGRADED
        else:
            status = HealthStatus.UNHEALTHY
        
        # Compare with baseline if available
        if baseline_version:
            baseline_metrics = await self._collector.collect(
                baseline_version,
                self._config.evaluation_period_seconds,
            )
            
            if baseline_metrics.request_count >= self._config.min_requests:
                # Compare latencies
                if canary_metrics.latency_p99_ms > baseline_metrics.latency_p99_ms * 1.5:
                    status = HealthStatus.DEGRADED
                
                # Compare error rates
                if canary_metrics.error_rate > baseline_metrics.error_rate * 2:
                    status = HealthStatus.UNHEALTHY
        
        return status, canary_metrics


class CanaryDeployer:
    """
    Canary deployment manager.
    """
    
    def __init__(
        self,
        store: DeploymentStore,
        router: TrafficRouter,
        evaluator: HealthEvaluator,
        config: Optional[CanaryConfig] = None,
    ):
        self._store = store
        self._router = router
        self._evaluator = evaluator
        self._config = config or CanaryConfig()
        self._monitor_task: Optional[asyncio.Task] = None
    
    async def deploy(
        self,
        name: str,
        version: str,
        baseline_version: Optional[str] = None,
        initial_percent: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CanaryDeployment:
        """Start a canary deployment."""
        percent = initial_percent or self._config.initial_percent
        
        deployment = CanaryDeployment(
            deployment_id=str(uuid.uuid4()),
            name=name,
            version=version,
            state=DeploymentState.DEPLOYING,
            traffic_percent=percent,
            baseline_version=baseline_version,
            metadata=metadata or {},
        )
        
        await self._store.save(deployment)
        
        # Add traffic rule
        rule = TrafficRule(
            rule_id=f"canary-{deployment.deployment_id}",
            source_version=baseline_version or "stable",
            target_version=version,
            percent=percent,
        )
        await self._router.add_rule(rule)
        
        deployment.state = DeploymentState.ACTIVE
        deployment.started_at = datetime.now()
        await self._store.save(deployment)
        
        logger.info(
            f"Canary deployment started: {name} @ {percent}%"
        )
        
        return deployment
    
    async def promote(
        self,
        deployment_id: str,
        percent: Optional[float] = None,
    ) -> CanaryDeployment:
        """Promote canary to higher traffic."""
        deployment = await self._store.get(deployment_id)
        
        if not deployment:
            raise CanaryError(f"Deployment not found: {deployment_id}")
        
        new_percent = percent or min(
            deployment.traffic_percent + self._config.increment_percent,
            self._config.max_percent,
        )
        
        # Check health before promotion
        status, metrics = await self._evaluator.evaluate(
            deployment.version,
            deployment.baseline_version,
        )
        
        if status == HealthStatus.UNHEALTHY:
            raise PromotionError(
                f"Cannot promote unhealthy canary: {status}"
            )
        
        deployment.state = DeploymentState.PROMOTING
        deployment.traffic_percent = new_percent
        deployment.health_status = status
        deployment.metrics = metrics
        
        # Update traffic rule
        rule_id = f"canary-{deployment_id}"
        await self._router.update_rule(rule_id, new_percent)
        
        if new_percent >= self._config.max_percent:
            deployment.state = DeploymentState.COMPLETED
            deployment.completed_at = datetime.now()
        else:
            deployment.state = DeploymentState.ACTIVE
        
        await self._store.save(deployment)
        
        logger.info(
            f"Canary promoted: {deployment.name} @ {new_percent}%"
        )
        
        return deployment
    
    async def rollback(
        self,
        deployment_id: str,
        reason: Optional[str] = None,
    ) -> CanaryDeployment:
        """Rollback a canary deployment."""
        deployment = await self._store.get(deployment_id)
        
        if not deployment:
            raise CanaryError(f"Deployment not found: {deployment_id}")
        
        deployment.state = DeploymentState.ROLLING_BACK
        await self._store.save(deployment)
        
        # Remove traffic rule
        rule_id = f"canary-{deployment_id}"
        await self._router.remove_rule(rule_id)
        
        deployment.state = DeploymentState.FAILED
        deployment.completed_at = datetime.now()
        
        if reason:
            deployment.metadata["rollback_reason"] = reason
        
        await self._store.save(deployment)
        
        logger.warning(
            f"Canary rolled back: {deployment.name} - {reason or 'manual'}"
        )
        
        return deployment
    
    async def get_deployment(
        self,
        deployment_id: str,
    ) -> Optional[CanaryDeployment]:
        """Get deployment by ID."""
        return await self._store.get(deployment_id)
    
    async def get_active_deployments(self) -> List[CanaryDeployment]:
        """Get all active deployments."""
        return await self._store.get_active()
    
    async def check_health(
        self,
        deployment_id: str,
    ) -> Tuple[HealthStatus, HealthMetrics]:
        """Check deployment health."""
        deployment = await self._store.get(deployment_id)
        
        if not deployment:
            raise CanaryError(f"Deployment not found: {deployment_id}")
        
        return await self._evaluator.evaluate(
            deployment.version,
            deployment.baseline_version,
        )
    
    async def start_monitoring(
        self,
        interval_seconds: int = 60,
    ) -> None:
        """Start automatic monitoring."""
        async def monitor_loop():
            while True:
                try:
                    active = await self.get_active_deployments()
                    
                    for deployment in active:
                        status, metrics = await self.check_health(
                            deployment.deployment_id
                        )
                        
                        deployment.health_status = status
                        deployment.metrics = metrics
                        await self._store.save(deployment)
                        
                        # Auto-rollback on unhealthy
                        if (
                            self._config.auto_rollback
                            and status == HealthStatus.UNHEALTHY
                        ):
                            await self.rollback(
                                deployment.deployment_id,
                                reason="auto_rollback: unhealthy",
                            )
                        
                        # Auto-promote on healthy
                        elif (
                            self._config.auto_promote
                            and status == HealthStatus.HEALTHY
                            and deployment.traffic_percent < self._config.max_percent
                        ):
                            await self.promote(deployment.deployment_id)
                
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Monitor error: {e}")
                
                await asyncio.sleep(interval_seconds)
        
        self._monitor_task = asyncio.create_task(monitor_loop())
    
    async def stop_monitoring(self) -> None:
        """Stop automatic monitoring."""
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass


# Global state for decorator routing
_canary_routes: Dict[str, Tuple[Callable, float]] = {}


# Decorators
def canary_route(
    percent: float = 10.0,
    version: Optional[str] = None,
) -> Callable:
    """
    Decorator to mark function as canary route.
    
    Example:
        @canary_route(percent=10)
        async def new_handler():
            ...
    """
    def decorator(func: Callable) -> Callable:
        route_version = version or func.__name__
        _canary_routes[route_version] = (func, percent)
        
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return await func(*args, **kwargs)
        
        return wrapper
    
    return decorator


def with_canary(
    stable_fn: Callable,
    canary_fn: Callable,
    percent: float = 10.0,
) -> Callable:
    """
    Decorator for A/B routing between stable and canary.
    
    Example:
        handler = with_canary(stable_handler, new_handler, percent=20)
    """
    @wraps(canary_fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        if random.random() * 100 < percent:
            return await canary_fn(*args, **kwargs)
        return await stable_fn(*args, **kwargs)
    
    return wrapper


def feature_flag(
    flag_name: str,
    percent: float = 0.0,
) -> Callable:
    """
    Decorator for feature flag based routing.
    
    Example:
        @feature_flag("new_checkout", percent=5)
        async def checkout():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            if random.random() * 100 < percent:
                return await func(*args, **kwargs)
            return None  # Feature disabled
        
        return wrapper
    
    return decorator


# Factory functions
def create_canary_deployer(
    config: Optional[CanaryConfig] = None,
) -> CanaryDeployer:
    """Create a canary deployer."""
    store = InMemoryDeploymentStore()
    router = TrafficRouter()
    collector = InMemoryMetricsCollector()
    evaluator = HealthEvaluator(collector, config)
    
    return CanaryDeployer(store, router, evaluator, config)


def create_traffic_router(
    strategy: TrafficStrategy = TrafficStrategy.WEIGHTED,
) -> TrafficRouter:
    """Create a traffic router."""
    return TrafficRouter(strategy)


def create_health_evaluator(
    collector: Optional[MetricsCollector] = None,
    config: Optional[CanaryConfig] = None,
) -> HealthEvaluator:
    """Create a health evaluator."""
    c = collector or InMemoryMetricsCollector()
    return HealthEvaluator(c, config)


def create_canary_config(
    initial_percent: float = 5.0,
    increment_percent: float = 10.0,
    health_threshold: float = 0.99,
    auto_promote: bool = False,
    auto_rollback: bool = True,
) -> CanaryConfig:
    """Create canary configuration."""
    return CanaryConfig(
        initial_percent=initial_percent,
        increment_percent=increment_percent,
        health_threshold=health_threshold,
        auto_promote=auto_promote,
        auto_rollback=auto_rollback,
    )


__all__ = [
    # Exceptions
    "CanaryError",
    "PromotionError",
    "RollbackError",
    # Enums
    "DeploymentState",
    "HealthStatus",
    "TrafficStrategy",
    # Data classes
    "CanaryConfig",
    "HealthMetrics",
    "CanaryDeployment",
    "TrafficRule",
    # Collectors
    "MetricsCollector",
    "InMemoryMetricsCollector",
    # Stores
    "DeploymentStore",
    "InMemoryDeploymentStore",
    # Core classes
    "TrafficRouter",
    "HealthEvaluator",
    "CanaryDeployer",
    # Decorators
    "canary_route",
    "with_canary",
    "feature_flag",
    # Factory functions
    "create_canary_deployer",
    "create_traffic_router",
    "create_health_evaluator",
    "create_canary_config",
]
