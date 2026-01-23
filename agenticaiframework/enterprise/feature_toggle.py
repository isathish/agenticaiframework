"""
Enterprise Feature Toggle Module.

Provides feature toggles, gradual rollout, kill switches,
and dynamic feature management.

Example:
    # Create feature manager
    manager = create_feature_manager()
    
    # Define a feature
    await manager.define("new-checkout", enabled=False)
    
    # Check feature
    if await manager.is_enabled("new-checkout", user_id="user123"):
        # New feature code
        ...
    
    # Or use decorator
    @feature_flag("new-checkout")
    async def new_checkout():
        ...
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import random
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from typing import (
    Any,
    Awaitable,
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


class FeatureError(Exception):
    """Feature toggle error."""
    pass


class FeatureNotFoundError(FeatureError):
    """Feature not found."""
    pass


class ToggleType(str, Enum):
    """Toggle type."""
    RELEASE = "release"  # Feature release toggle
    EXPERIMENT = "experiment"  # A/B testing
    OPS = "ops"  # Operational toggle (kill switch)
    PERMISSION = "permission"  # Permission-based access


class RolloutStrategy(str, Enum):
    """Rollout strategy."""
    ALL = "all"  # All users
    NONE = "none"  # No users
    PERCENTAGE = "percentage"  # Percentage rollout
    USER_ID = "user_id"  # Specific users
    USER_SEGMENT = "user_segment"  # User segments
    GRADUAL = "gradual"  # Gradual increase


class FeatureState(str, Enum):
    """Feature state."""
    ENABLED = "enabled"
    DISABLED = "disabled"
    CONDITIONAL = "conditional"
    ARCHIVED = "archived"


@dataclass
class RolloutConfig:
    """Rollout configuration."""
    strategy: RolloutStrategy = RolloutStrategy.ALL
    percentage: float = 100.0
    user_ids: Set[str] = field(default_factory=set)
    user_segments: Set[str] = field(default_factory=set)
    gradual_increment: float = 10.0
    gradual_interval_hours: int = 24
    sticky: bool = True  # Consistent experience for same user


@dataclass
class FeatureRule:
    """Feature evaluation rule."""
    rule_id: str
    condition: str  # JSON-like condition expression
    enabled: bool = True
    priority: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FeatureDefinition:
    """Feature definition."""
    feature_id: str
    name: str
    description: str = ""
    toggle_type: ToggleType = ToggleType.RELEASE
    state: FeatureState = FeatureState.DISABLED
    rollout: RolloutConfig = field(default_factory=RolloutConfig)
    rules: List[FeatureRule] = field(default_factory=list)
    default_value: Any = None
    variants: Dict[str, Any] = field(default_factory=dict)
    tags: Set[str] = field(default_factory=set)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EvaluationContext:
    """Context for feature evaluation."""
    user_id: Optional[str] = None
    user_segment: Optional[str] = None
    user_attributes: Dict[str, Any] = field(default_factory=dict)
    environment: str = "production"
    timestamp: datetime = field(default_factory=datetime.now)
    request_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EvaluationResult:
    """Feature evaluation result."""
    feature_name: str
    enabled: bool
    variant: Optional[str] = None
    value: Any = None
    reason: str = ""
    rule_id: Optional[str] = None
    evaluated_at: datetime = field(default_factory=datetime.now)


class FeatureStore(ABC):
    """Abstract feature store."""
    
    @abstractmethod
    async def save(self, feature: FeatureDefinition) -> None:
        """Save feature."""
        pass
    
    @abstractmethod
    async def get(self, name: str) -> Optional[FeatureDefinition]:
        """Get feature."""
        pass
    
    @abstractmethod
    async def list_all(self) -> List[FeatureDefinition]:
        """List all features."""
        pass
    
    @abstractmethod
    async def delete(self, name: str) -> None:
        """Delete feature."""
        pass


class InMemoryFeatureStore(FeatureStore):
    """In-memory feature store."""
    
    def __init__(self):
        self._features: Dict[str, FeatureDefinition] = {}
        self._lock = asyncio.Lock()
    
    async def save(self, feature: FeatureDefinition) -> None:
        async with self._lock:
            feature.updated_at = datetime.now()
            self._features[feature.name] = feature
    
    async def get(self, name: str) -> Optional[FeatureDefinition]:
        return self._features.get(name)
    
    async def list_all(self) -> List[FeatureDefinition]:
        return list(self._features.values())
    
    async def delete(self, name: str) -> None:
        async with self._lock:
            self._features.pop(name, None)


class RolloutTracker:
    """
    Tracks gradual rollout progress.
    """
    
    def __init__(self):
        self._rollout_state: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()
    
    async def get_percentage(self, feature_name: str) -> float:
        """Get current rollout percentage."""
        state = self._rollout_state.get(feature_name)
        return state.get("percentage", 0.0) if state else 0.0
    
    async def update_percentage(
        self,
        feature_name: str,
        percentage: float,
    ) -> None:
        """Update rollout percentage."""
        async with self._lock:
            if feature_name not in self._rollout_state:
                self._rollout_state[feature_name] = {}
            
            self._rollout_state[feature_name]["percentage"] = min(percentage, 100.0)
            self._rollout_state[feature_name]["updated_at"] = datetime.now()
    
    async def should_increment(
        self,
        feature_name: str,
        interval_hours: int,
    ) -> bool:
        """Check if rollout should be incremented."""
        state = self._rollout_state.get(feature_name)
        
        if not state:
            return True
        
        last_update = state.get("updated_at")
        
        if not last_update:
            return True
        
        elapsed = datetime.now() - last_update
        return elapsed >= timedelta(hours=interval_hours)


class StickyBucket:
    """
    Manages sticky bucketing for consistent user experience.
    """
    
    def __init__(self):
        self._buckets: Dict[str, Dict[str, bool]] = {}
        self._lock = asyncio.Lock()
    
    async def get_assignment(
        self,
        feature_name: str,
        user_id: str,
    ) -> Optional[bool]:
        """Get sticky assignment for user."""
        feature_buckets = self._buckets.get(feature_name, {})
        return feature_buckets.get(user_id)
    
    async def set_assignment(
        self,
        feature_name: str,
        user_id: str,
        enabled: bool,
    ) -> None:
        """Set sticky assignment for user."""
        async with self._lock:
            if feature_name not in self._buckets:
                self._buckets[feature_name] = {}
            
            self._buckets[feature_name][user_id] = enabled
    
    def clear_feature(self, feature_name: str) -> None:
        """Clear all assignments for a feature."""
        self._buckets.pop(feature_name, None)


class FeatureEvaluator:
    """
    Evaluates feature flags.
    """
    
    def __init__(
        self,
        rollout_tracker: Optional[RolloutTracker] = None,
        sticky_bucket: Optional[StickyBucket] = None,
    ):
        self._rollout_tracker = rollout_tracker or RolloutTracker()
        self._sticky = sticky_bucket or StickyBucket()
    
    async def evaluate(
        self,
        feature: FeatureDefinition,
        context: EvaluationContext,
    ) -> EvaluationResult:
        """Evaluate feature for context."""
        # Check if expired
        if feature.expires_at and datetime.now() > feature.expires_at:
            return EvaluationResult(
                feature_name=feature.name,
                enabled=False,
                reason="Feature expired",
            )
        
        # Check archived
        if feature.state == FeatureState.ARCHIVED:
            return EvaluationResult(
                feature_name=feature.name,
                enabled=False,
                reason="Feature archived",
            )
        
        # Check disabled
        if feature.state == FeatureState.DISABLED:
            return EvaluationResult(
                feature_name=feature.name,
                enabled=False,
                value=feature.default_value,
                reason="Feature disabled",
            )
        
        # Check enabled (always on)
        if feature.state == FeatureState.ENABLED:
            rollout = feature.rollout
            
            if rollout.strategy == RolloutStrategy.ALL:
                return EvaluationResult(
                    feature_name=feature.name,
                    enabled=True,
                    value=feature.default_value,
                    reason="Feature enabled for all",
                )
        
        # Evaluate conditional features
        return await self._evaluate_rollout(feature, context)
    
    async def _evaluate_rollout(
        self,
        feature: FeatureDefinition,
        context: EvaluationContext,
    ) -> EvaluationResult:
        """Evaluate rollout strategy."""
        rollout = feature.rollout
        
        if rollout.strategy == RolloutStrategy.NONE:
            return EvaluationResult(
                feature_name=feature.name,
                enabled=False,
                reason="Rollout set to none",
            )
        
        if rollout.strategy == RolloutStrategy.USER_ID:
            enabled = context.user_id in rollout.user_ids
            return EvaluationResult(
                feature_name=feature.name,
                enabled=enabled,
                reason=f"User ID {'in' if enabled else 'not in'} allow list",
            )
        
        if rollout.strategy == RolloutStrategy.USER_SEGMENT:
            enabled = context.user_segment in rollout.user_segments
            return EvaluationResult(
                feature_name=feature.name,
                enabled=enabled,
                reason=f"User segment {'in' if enabled else 'not in'} allow list",
            )
        
        if rollout.strategy == RolloutStrategy.PERCENTAGE:
            return await self._evaluate_percentage(
                feature,
                context,
                rollout.percentage,
            )
        
        if rollout.strategy == RolloutStrategy.GRADUAL:
            current_percentage = await self._rollout_tracker.get_percentage(
                feature.name
            )
            
            # Check if we should increment
            if await self._rollout_tracker.should_increment(
                feature.name,
                rollout.gradual_interval_hours,
            ):
                new_percentage = min(
                    current_percentage + rollout.gradual_increment,
                    100.0,
                )
                await self._rollout_tracker.update_percentage(
                    feature.name,
                    new_percentage,
                )
                current_percentage = new_percentage
            
            return await self._evaluate_percentage(
                feature,
                context,
                current_percentage,
            )
        
        # Default: enabled
        return EvaluationResult(
            feature_name=feature.name,
            enabled=True,
            reason="Default enabled",
        )
    
    async def _evaluate_percentage(
        self,
        feature: FeatureDefinition,
        context: EvaluationContext,
        percentage: float,
    ) -> EvaluationResult:
        """Evaluate percentage rollout."""
        if percentage >= 100.0:
            return EvaluationResult(
                feature_name=feature.name,
                enabled=True,
                reason="100% rollout",
            )
        
        if percentage <= 0.0:
            return EvaluationResult(
                feature_name=feature.name,
                enabled=False,
                reason="0% rollout",
            )
        
        # Check sticky assignment
        if feature.rollout.sticky and context.user_id:
            assignment = await self._sticky.get_assignment(
                feature.name,
                context.user_id,
            )
            
            if assignment is not None:
                return EvaluationResult(
                    feature_name=feature.name,
                    enabled=assignment,
                    reason="Sticky assignment",
                )
        
        # Calculate bucket
        if context.user_id:
            # Consistent bucketing based on user ID
            hash_input = f"{feature.name}:{context.user_id}"
            hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
            bucket = hash_value % 100
        else:
            # Random bucketing
            bucket = random.randint(0, 99)
        
        enabled = bucket < percentage
        
        # Save sticky assignment
        if feature.rollout.sticky and context.user_id:
            await self._sticky.set_assignment(
                feature.name,
                context.user_id,
                enabled,
            )
        
        return EvaluationResult(
            feature_name=feature.name,
            enabled=enabled,
            reason=f"Percentage rollout ({percentage}%): bucket {bucket}",
        )


class FeatureManager:
    """
    Feature toggle manager.
    """
    
    def __init__(
        self,
        store: Optional[FeatureStore] = None,
        evaluator: Optional[FeatureEvaluator] = None,
    ):
        self._store = store or InMemoryFeatureStore()
        self._evaluator = evaluator or FeatureEvaluator()
        self._listeners: List[Callable[[str, bool], Awaitable[None]]] = []
    
    async def define(
        self,
        name: str,
        enabled: bool = False,
        description: str = "",
        toggle_type: ToggleType = ToggleType.RELEASE,
        rollout: Optional[RolloutConfig] = None,
        default_value: Any = None,
        expires_at: Optional[datetime] = None,
        tags: Optional[Set[str]] = None,
    ) -> FeatureDefinition:
        """Define a new feature."""
        feature = FeatureDefinition(
            feature_id=f"feat-{uuid.uuid4().hex[:8]}",
            name=name,
            description=description,
            toggle_type=toggle_type,
            state=FeatureState.ENABLED if enabled else FeatureState.DISABLED,
            rollout=rollout or RolloutConfig(),
            default_value=default_value,
            expires_at=expires_at,
            tags=tags or set(),
        )
        
        await self._store.save(feature)
        logger.info(f"Defined feature: {name}")
        
        return feature
    
    async def enable(
        self,
        name: str,
        strategy: RolloutStrategy = RolloutStrategy.ALL,
        percentage: float = 100.0,
    ) -> None:
        """Enable a feature."""
        feature = await self._store.get(name)
        
        if not feature:
            raise FeatureNotFoundError(f"Feature not found: {name}")
        
        feature.state = FeatureState.ENABLED
        feature.rollout.strategy = strategy
        feature.rollout.percentage = percentage
        
        await self._store.save(feature)
        
        # Notify listeners
        for listener in self._listeners:
            await listener(name, True)
        
        logger.info(f"Enabled feature: {name}")
    
    async def disable(self, name: str) -> None:
        """Disable a feature (kill switch)."""
        feature = await self._store.get(name)
        
        if not feature:
            raise FeatureNotFoundError(f"Feature not found: {name}")
        
        feature.state = FeatureState.DISABLED
        
        await self._store.save(feature)
        
        # Notify listeners
        for listener in self._listeners:
            await listener(name, False)
        
        logger.info(f"Disabled feature: {name}")
    
    async def archive(self, name: str) -> None:
        """Archive a feature."""
        feature = await self._store.get(name)
        
        if not feature:
            return
        
        feature.state = FeatureState.ARCHIVED
        await self._store.save(feature)
    
    async def is_enabled(
        self,
        name: str,
        user_id: Optional[str] = None,
        user_segment: Optional[str] = None,
        **attributes: Any,
    ) -> bool:
        """Check if feature is enabled."""
        feature = await self._store.get(name)
        
        if not feature:
            return False
        
        context = EvaluationContext(
            user_id=user_id,
            user_segment=user_segment,
            user_attributes=attributes,
        )
        
        result = await self._evaluator.evaluate(feature, context)
        return result.enabled
    
    async def get_value(
        self,
        name: str,
        default: Any = None,
        user_id: Optional[str] = None,
        **attributes: Any,
    ) -> Any:
        """Get feature value."""
        feature = await self._store.get(name)
        
        if not feature:
            return default
        
        context = EvaluationContext(
            user_id=user_id,
            user_attributes=attributes,
        )
        
        result = await self._evaluator.evaluate(feature, context)
        
        if result.enabled:
            return result.value if result.value is not None else feature.default_value
        
        return default
    
    async def get_variant(
        self,
        name: str,
        user_id: Optional[str] = None,
        **attributes: Any,
    ) -> Optional[str]:
        """Get feature variant for A/B testing."""
        feature = await self._store.get(name)
        
        if not feature or not feature.variants:
            return None
        
        context = EvaluationContext(
            user_id=user_id,
            user_attributes=attributes,
        )
        
        result = await self._evaluator.evaluate(feature, context)
        return result.variant
    
    async def add_users(
        self,
        name: str,
        user_ids: List[str],
    ) -> None:
        """Add users to feature allowlist."""
        feature = await self._store.get(name)
        
        if not feature:
            raise FeatureNotFoundError(f"Feature not found: {name}")
        
        feature.rollout.user_ids.update(user_ids)
        await self._store.save(feature)
    
    async def remove_users(
        self,
        name: str,
        user_ids: List[str],
    ) -> None:
        """Remove users from feature allowlist."""
        feature = await self._store.get(name)
        
        if not feature:
            return
        
        feature.rollout.user_ids.difference_update(user_ids)
        await self._store.save(feature)
    
    async def set_percentage(
        self,
        name: str,
        percentage: float,
    ) -> None:
        """Set rollout percentage."""
        feature = await self._store.get(name)
        
        if not feature:
            raise FeatureNotFoundError(f"Feature not found: {name}")
        
        feature.rollout.percentage = min(max(percentage, 0.0), 100.0)
        feature.rollout.strategy = RolloutStrategy.PERCENTAGE
        
        await self._store.save(feature)
    
    async def get_feature(
        self,
        name: str,
    ) -> Optional[FeatureDefinition]:
        """Get feature definition."""
        return await self._store.get(name)
    
    async def list_features(
        self,
        tag: Optional[str] = None,
    ) -> List[FeatureDefinition]:
        """List all features."""
        features = await self._store.list_all()
        
        if tag:
            features = [f for f in features if tag in f.tags]
        
        return features
    
    def on_change(
        self,
        callback: Callable[[str, bool], Awaitable[None]],
    ) -> None:
        """Register change listener."""
        self._listeners.append(callback)


# Global manager
_global_manager: Optional[FeatureManager] = None


def get_global_manager() -> FeatureManager:
    """Get or create global feature manager."""
    global _global_manager
    
    if _global_manager is None:
        _global_manager = FeatureManager()
    
    return _global_manager


# Decorators
def feature_flag(
    name: str,
    default: Any = None,
    manager: Optional[FeatureManager] = None,
) -> Callable:
    """
    Decorator to wrap function with feature flag check.
    
    Example:
        @feature_flag("new-checkout")
        async def new_checkout():
            ...
    """
    _manager = manager or get_global_manager()
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            user_id = kwargs.get("user_id")
            
            if await _manager.is_enabled(name, user_id=user_id):
                return await func(*args, **kwargs)
            
            return default
        
        return wrapper
    
    return decorator


def feature_variant(
    name: str,
    variants: Dict[str, Callable],
    default: Optional[str] = None,
    manager: Optional[FeatureManager] = None,
) -> Callable:
    """
    Decorator for A/B testing variants.
    
    Example:
        @feature_variant("checkout-flow", {
            "control": checkout_v1,
            "treatment": checkout_v2,
        })
        async def checkout():
            ...
    """
    _manager = manager or get_global_manager()
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            user_id = kwargs.get("user_id")
            variant = await _manager.get_variant(name, user_id=user_id)
            
            variant_func = variants.get(variant or default or "")
            
            if variant_func:
                return await variant_func(*args, **kwargs)
            
            return await func(*args, **kwargs)
        
        return wrapper
    
    return decorator


def kill_switch(
    name: str,
    fallback: Optional[Callable] = None,
    manager: Optional[FeatureManager] = None,
) -> Callable:
    """
    Decorator for kill switch functionality.
    
    Example:
        @kill_switch("payment-processing")
        async def process_payment():
            ...
    """
    _manager = manager or get_global_manager()
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Kill switch is inverted - if enabled, feature is OFF
            if await _manager.is_enabled(name):
                if fallback:
                    return await fallback(*args, **kwargs)
                
                raise FeatureError(f"Feature killed: {name}")
            
            return await func(*args, **kwargs)
        
        return wrapper
    
    return decorator


# Factory functions
def create_feature_manager(
    store: Optional[FeatureStore] = None,
) -> FeatureManager:
    """Create a feature manager."""
    return FeatureManager(store=store)


def create_rollout_config(
    strategy: RolloutStrategy = RolloutStrategy.ALL,
    percentage: float = 100.0,
    sticky: bool = True,
) -> RolloutConfig:
    """Create a rollout config."""
    return RolloutConfig(
        strategy=strategy,
        percentage=percentage,
        sticky=sticky,
    )


def create_gradual_rollout(
    start_percentage: float = 0.0,
    increment: float = 10.0,
    interval_hours: int = 24,
) -> RolloutConfig:
    """Create a gradual rollout config."""
    return RolloutConfig(
        strategy=RolloutStrategy.GRADUAL,
        percentage=start_percentage,
        gradual_increment=increment,
        gradual_interval_hours=interval_hours,
    )


__all__ = [
    # Exceptions
    "FeatureError",
    "FeatureNotFoundError",
    # Enums
    "ToggleType",
    "RolloutStrategy",
    "FeatureState",
    # Data classes
    "RolloutConfig",
    "FeatureRule",
    "FeatureDefinition",
    "EvaluationContext",
    "EvaluationResult",
    # Abstract classes
    "FeatureStore",
    # Implementations
    "InMemoryFeatureStore",
    "RolloutTracker",
    "StickyBucket",
    "FeatureEvaluator",
    # Core classes
    "FeatureManager",
    # Decorators
    "feature_flag",
    "feature_variant",
    "kill_switch",
    # Factory functions
    "create_feature_manager",
    "create_rollout_config",
    "create_gradual_rollout",
    "get_global_manager",
]
