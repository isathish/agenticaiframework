"""
Enterprise Feature Flags - Runtime feature toggles.

Enables gradual rollouts, A/B testing, and runtime
configuration without code changes.

Features:
- Boolean flags
- Percentage rollouts
- User targeting
- A/B testing
- Analytics integration
"""

import asyncio
import hashlib
import json
import logging
import random
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# =============================================================================
# Flag Types
# =============================================================================

class FlagType(Enum):
    """Types of feature flags."""
    BOOLEAN = "boolean"
    STRING = "string"
    NUMBER = "number"
    JSON = "json"


class RolloutStrategy(Enum):
    """Flag rollout strategies."""
    ALL = "all"              # Enabled for everyone
    NONE = "none"            # Disabled for everyone
    PERCENTAGE = "percentage" # Enabled for percentage of users
    USER_LIST = "user_list"   # Enabled for specific users
    ATTRIBUTE = "attribute"   # Based on user attributes
    RANDOM = "random"         # Random per-request


@dataclass
class FlagVariant:
    """A variant for A/B testing."""
    name: str
    value: Any
    weight: float = 1.0  # Relative weight for distribution


@dataclass
class FeatureFlag:
    """A feature flag definition."""
    key: str
    name: str
    description: str = ""
    flag_type: FlagType = FlagType.BOOLEAN
    
    # Default value
    default_value: Any = False
    
    # Rollout
    enabled: bool = True
    strategy: RolloutStrategy = RolloutStrategy.ALL
    percentage: float = 100.0  # For percentage rollout
    user_list: List[str] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)
    
    # A/B Testing
    variants: List[FlagVariant] = field(default_factory=list)
    
    # Metadata
    tags: List[str] = field(default_factory=list)
    owner: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    
    # Targeting rules
    rules: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class FlagContext:
    """Context for evaluating feature flags."""
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    
    # Common attributes
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    locale: Optional[str] = None
    environment: str = "production"


@dataclass
class FlagEvaluation:
    """Result of a flag evaluation."""
    key: str
    value: Any
    variant: Optional[str] = None
    reason: str = ""
    is_default: bool = False
    evaluated_at: datetime = field(default_factory=datetime.now)


# =============================================================================
# Flag Backend
# =============================================================================

class FlagBackend(ABC):
    """Abstract interface for flag storage."""
    
    @abstractmethod
    async def get(self, key: str) -> Optional[FeatureFlag]:
        """Get a flag by key."""
        pass
    
    @abstractmethod
    async def set(self, flag: FeatureFlag):
        """Store a flag."""
        pass
    
    @abstractmethod
    async def delete(self, key: str):
        """Delete a flag."""
        pass
    
    @abstractmethod
    async def list(self, prefix: Optional[str] = None) -> List[FeatureFlag]:
        """List all flags."""
        pass


class InMemoryFlagBackend(FlagBackend):
    """In-memory flag backend."""
    
    def __init__(self):
        self._flags: Dict[str, FeatureFlag] = {}
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[FeatureFlag]:
        return self._flags.get(key)
    
    async def set(self, flag: FeatureFlag):
        async with self._lock:
            self._flags[flag.key] = flag
    
    async def delete(self, key: str):
        async with self._lock:
            if key in self._flags:
                del self._flags[key]
    
    async def list(self, prefix: Optional[str] = None) -> List[FeatureFlag]:
        flags = list(self._flags.values())
        
        if prefix:
            flags = [f for f in flags if f.key.startswith(prefix)]
        
        return flags


# =============================================================================
# Flag Evaluator
# =============================================================================

class FlagEvaluator:
    """
    Evaluates feature flags based on context.
    
    Usage:
        >>> evaluator = FlagEvaluator()
        >>> 
        >>> context = FlagContext(user_id="user-123")
        >>> result = await evaluator.evaluate("new-feature", context)
        >>> 
        >>> if result.value:
        ...     show_new_feature()
    """
    
    def __init__(self, backend: Optional[FlagBackend] = None):
        self.backend = backend or InMemoryFlagBackend()
        self._cache: Dict[str, tuple] = {}
        self._cache_ttl = 60  # seconds
    
    async def evaluate(
        self,
        key: str,
        context: Optional[FlagContext] = None,
    ) -> FlagEvaluation:
        """Evaluate a feature flag."""
        context = context or FlagContext()
        
        # Get flag
        flag = await self.backend.get(key)
        
        if not flag:
            return FlagEvaluation(
                key=key,
                value=False,
                reason="Flag not found",
                is_default=True,
            )
        
        # Check if expired
        if flag.expires_at and datetime.now() > flag.expires_at:
            return FlagEvaluation(
                key=key,
                value=flag.default_value,
                reason="Flag expired",
                is_default=True,
            )
        
        # Check if disabled
        if not flag.enabled:
            return FlagEvaluation(
                key=key,
                value=flag.default_value,
                reason="Flag disabled",
                is_default=True,
            )
        
        # Evaluate strategy
        return self._evaluate_strategy(flag, context)
    
    def _evaluate_strategy(
        self,
        flag: FeatureFlag,
        context: FlagContext,
    ) -> FlagEvaluation:
        """Evaluate flag based on strategy."""
        
        if flag.strategy == RolloutStrategy.ALL:
            return self._evaluate_all(flag, context)
        
        elif flag.strategy == RolloutStrategy.NONE:
            return FlagEvaluation(
                key=flag.key,
                value=flag.default_value,
                reason="Strategy: none",
                is_default=True,
            )
        
        elif flag.strategy == RolloutStrategy.PERCENTAGE:
            return self._evaluate_percentage(flag, context)
        
        elif flag.strategy == RolloutStrategy.USER_LIST:
            return self._evaluate_user_list(flag, context)
        
        elif flag.strategy == RolloutStrategy.ATTRIBUTE:
            return self._evaluate_attribute(flag, context)
        
        elif flag.strategy == RolloutStrategy.RANDOM:
            return self._evaluate_random(flag, context)
        
        else:
            return FlagEvaluation(
                key=flag.key,
                value=flag.default_value,
                reason="Unknown strategy",
                is_default=True,
            )
    
    def _evaluate_all(
        self,
        flag: FeatureFlag,
        context: FlagContext,
    ) -> FlagEvaluation:
        """Evaluate for 'all' strategy."""
        value, variant = self._get_value_and_variant(flag, context)
        
        return FlagEvaluation(
            key=flag.key,
            value=value,
            variant=variant,
            reason="Strategy: all",
        )
    
    def _evaluate_percentage(
        self,
        flag: FeatureFlag,
        context: FlagContext,
    ) -> FlagEvaluation:
        """Evaluate percentage-based rollout."""
        # Get consistent hash for user
        hash_key = f"{flag.key}:{context.user_id or context.session_id or ''}"
        hash_value = int(hashlib.md5(hash_key.encode()).hexdigest(), 16)
        percentage = (hash_value % 100) + 1
        
        if percentage <= flag.percentage:
            value, variant = self._get_value_and_variant(flag, context)
            return FlagEvaluation(
                key=flag.key,
                value=value,
                variant=variant,
                reason=f"Percentage rollout: {percentage}% <= {flag.percentage}%",
            )
        else:
            return FlagEvaluation(
                key=flag.key,
                value=flag.default_value,
                reason=f"Percentage rollout: {percentage}% > {flag.percentage}%",
                is_default=True,
            )
    
    def _evaluate_user_list(
        self,
        flag: FeatureFlag,
        context: FlagContext,
    ) -> FlagEvaluation:
        """Evaluate user list targeting."""
        if context.user_id and context.user_id in flag.user_list:
            value, variant = self._get_value_and_variant(flag, context)
            return FlagEvaluation(
                key=flag.key,
                value=value,
                variant=variant,
                reason="User in target list",
            )
        else:
            return FlagEvaluation(
                key=flag.key,
                value=flag.default_value,
                reason="User not in target list",
                is_default=True,
            )
    
    def _evaluate_attribute(
        self,
        flag: FeatureFlag,
        context: FlagContext,
    ) -> FlagEvaluation:
        """Evaluate attribute-based targeting."""
        for attr_key, attr_value in flag.attributes.items():
            ctx_value = context.attributes.get(attr_key)
            
            if isinstance(attr_value, list):
                if ctx_value not in attr_value:
                    break
            elif ctx_value != attr_value:
                break
        else:
            # All attributes matched
            value, variant = self._get_value_and_variant(flag, context)
            return FlagEvaluation(
                key=flag.key,
                value=value,
                variant=variant,
                reason="Attribute match",
            )
        
        return FlagEvaluation(
            key=flag.key,
            value=flag.default_value,
            reason="Attribute mismatch",
            is_default=True,
        )
    
    def _evaluate_random(
        self,
        flag: FeatureFlag,
        context: FlagContext,
    ) -> FlagEvaluation:
        """Evaluate random strategy."""
        if random.random() * 100 <= flag.percentage:
            value, variant = self._get_value_and_variant(flag, context)
            return FlagEvaluation(
                key=flag.key,
                value=value,
                variant=variant,
                reason="Random selection",
            )
        else:
            return FlagEvaluation(
                key=flag.key,
                value=flag.default_value,
                reason="Random rejection",
                is_default=True,
            )
    
    def _get_value_and_variant(
        self,
        flag: FeatureFlag,
        context: FlagContext,
    ) -> tuple:
        """Get value and variant for a matched flag."""
        if not flag.variants:
            # No variants, return true/default based on type
            if flag.flag_type == FlagType.BOOLEAN:
                return True, None
            else:
                return flag.default_value, None
        
        # Select variant based on weights
        total_weight = sum(v.weight for v in flag.variants)
        
        # Use consistent hash for variant selection
        hash_key = f"{flag.key}:variant:{context.user_id or context.session_id or ''}"
        hash_value = int(hashlib.md5(hash_key.encode()).hexdigest(), 16)
        selection = (hash_value % 1000) / 1000 * total_weight
        
        cumulative = 0
        for variant in flag.variants:
            cumulative += variant.weight
            if selection < cumulative:
                return variant.value, variant.name
        
        # Fallback to first variant
        return flag.variants[0].value, flag.variants[0].name


# =============================================================================
# Feature Flags Manager
# =============================================================================

class FeatureFlags:
    """
    High-level feature flags manager.
    
    Usage:
        >>> flags = FeatureFlags()
        >>> 
        >>> # Define a flag
        >>> await flags.create("new-checkout", 
        ...     description="New checkout flow",
        ...     strategy=RolloutStrategy.PERCENTAGE,
        ...     percentage=10,
        ... )
        >>> 
        >>> # Check flag
        >>> if await flags.is_enabled("new-checkout", user_id="user-123"):
        ...     show_new_checkout()
        >>> 
        >>> # A/B testing
        >>> variant = await flags.get_variant("button-color", user_id="user-123")
        >>> button_color = variant.value
    """
    
    def __init__(self, backend: Optional[FlagBackend] = None):
        self.backend = backend or InMemoryFlagBackend()
        self.evaluator = FlagEvaluator(self.backend)
        
        # Analytics
        self._evaluations: List[FlagEvaluation] = []
        self._max_evaluations = 10000
    
    async def create(
        self,
        key: str,
        name: Optional[str] = None,
        description: str = "",
        flag_type: FlagType = FlagType.BOOLEAN,
        default_value: Any = False,
        enabled: bool = True,
        strategy: RolloutStrategy = RolloutStrategy.ALL,
        percentage: float = 100.0,
        user_list: List[str] = None,
        variants: List[Dict] = None,
        tags: List[str] = None,
        **kwargs,
    ) -> FeatureFlag:
        """Create or update a feature flag."""
        flag = FeatureFlag(
            key=key,
            name=name or key,
            description=description,
            flag_type=flag_type,
            default_value=default_value,
            enabled=enabled,
            strategy=strategy,
            percentage=percentage,
            user_list=user_list or [],
            variants=[FlagVariant(**v) for v in (variants or [])],
            tags=tags or [],
            **kwargs,
        )
        
        await self.backend.set(flag)
        return flag
    
    async def get(self, key: str) -> Optional[FeatureFlag]:
        """Get a flag definition."""
        return await self.backend.get(key)
    
    async def delete(self, key: str):
        """Delete a flag."""
        await self.backend.delete(key)
    
    async def list(self, prefix: Optional[str] = None) -> List[FeatureFlag]:
        """List all flags."""
        return await self.backend.list(prefix)
    
    async def is_enabled(
        self,
        key: str,
        user_id: Optional[str] = None,
        **attributes,
    ) -> bool:
        """Check if a flag is enabled."""
        context = FlagContext(
            user_id=user_id,
            attributes=attributes,
        )
        
        result = await self.evaluator.evaluate(key, context)
        self._record_evaluation(result)
        
        return bool(result.value)
    
    async def get_value(
        self,
        key: str,
        default: Any = None,
        user_id: Optional[str] = None,
        **attributes,
    ) -> Any:
        """Get the value of a flag."""
        context = FlagContext(
            user_id=user_id,
            attributes=attributes,
        )
        
        result = await self.evaluator.evaluate(key, context)
        self._record_evaluation(result)
        
        if result.is_default and default is not None:
            return default
        
        return result.value
    
    async def get_variant(
        self,
        key: str,
        user_id: Optional[str] = None,
        **attributes,
    ) -> FlagEvaluation:
        """Get variant for A/B testing."""
        context = FlagContext(
            user_id=user_id,
            attributes=attributes,
        )
        
        result = await self.evaluator.evaluate(key, context)
        self._record_evaluation(result)
        
        return result
    
    async def enable(self, key: str):
        """Enable a flag."""
        flag = await self.backend.get(key)
        if flag:
            flag.enabled = True
            flag.updated_at = datetime.now()
            await self.backend.set(flag)
    
    async def disable(self, key: str):
        """Disable a flag."""
        flag = await self.backend.get(key)
        if flag:
            flag.enabled = False
            flag.updated_at = datetime.now()
            await self.backend.set(flag)
    
    async def set_percentage(self, key: str, percentage: float):
        """Update rollout percentage."""
        flag = await self.backend.get(key)
        if flag:
            flag.percentage = max(0, min(100, percentage))
            flag.updated_at = datetime.now()
            await self.backend.set(flag)
    
    def _record_evaluation(self, evaluation: FlagEvaluation):
        """Record evaluation for analytics."""
        self._evaluations.append(evaluation)
        
        if len(self._evaluations) > self._max_evaluations:
            self._evaluations = self._evaluations[-self._max_evaluations // 2:]
    
    def get_analytics(
        self,
        key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get flag evaluation analytics."""
        evaluations = self._evaluations
        
        if key:
            evaluations = [e for e in evaluations if e.key == key]
        
        if not evaluations:
            return {}
        
        # Calculate statistics
        total = len(evaluations)
        enabled = sum(1 for e in evaluations if e.value and not e.is_default)
        disabled = sum(1 for e in evaluations if not e.value or e.is_default)
        
        # Variant distribution
        variant_counts: Dict[str, int] = {}
        for e in evaluations:
            if e.variant:
                variant_counts[e.variant] = variant_counts.get(e.variant, 0) + 1
        
        return {
            "total_evaluations": total,
            "enabled_count": enabled,
            "disabled_count": disabled,
            "enabled_percentage": (enabled / total * 100) if total > 0 else 0,
            "variant_distribution": variant_counts,
        }


# =============================================================================
# Decorator
# =============================================================================

def feature_flag(
    key: str,
    default: Any = None,
    fallback: Callable = None,
):
    """
    Decorator to wrap function with feature flag check.
    
    Usage:
        >>> @feature_flag("new-algorithm", fallback=old_algorithm)
        >>> async def new_algorithm(data):
        ...     return process_with_new_algo(data)
    """
    import functools
    
    def decorator(fn: Callable):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            flags = get_feature_flags()
            
            # Extract user_id from kwargs if present
            user_id = kwargs.pop("_user_id", None)
            
            if await flags.is_enabled(key, user_id=user_id):
                return await fn(*args, **kwargs)
            elif fallback:
                return await fallback(*args, **kwargs) if asyncio.iscoroutinefunction(fallback) else fallback(*args, **kwargs)
            elif default is not None:
                return default
            else:
                return None
        
        return wrapper
    return decorator


# =============================================================================
# Global Feature Flags
# =============================================================================

_global_flags: Optional[FeatureFlags] = None
_lock = threading.Lock()


def get_feature_flags() -> FeatureFlags:
    """Get the global feature flags manager."""
    global _global_flags
    
    if _global_flags is None:
        with _lock:
            if _global_flags is None:
                _global_flags = FeatureFlags()
    
    return _global_flags


def set_feature_flags(flags: FeatureFlags):
    """Set the global feature flags manager."""
    global _global_flags
    _global_flags = flags


# Convenience functions
async def is_enabled(key: str, user_id: str = None, **attributes) -> bool:
    """Check if a flag is enabled."""
    return await get_feature_flags().is_enabled(key, user_id, **attributes)


async def get_flag_value(key: str, default: Any = None, **kwargs) -> Any:
    """Get a flag value."""
    return await get_feature_flags().get_value(key, default, **kwargs)


async def get_variant(key: str, user_id: str = None) -> FlagEvaluation:
    """Get variant for A/B testing."""
    return await get_feature_flags().get_variant(key, user_id)
