"""
Enterprise A/B Testing Module.

Experiment framework, variant assignment,
feature flags, and analytics integration.

Example:
    # Create A/B testing service
    ab = create_ab_testing()
    
    # Create experiment
    exp = await ab.create_experiment(
        name="checkout_flow",
        variants=["control", "variant_a", "variant_b"],
        traffic_split=[50, 25, 25],
    )
    
    # Get variant for user
    variant = await ab.get_variant(
        experiment="checkout_flow",
        user_id="user_123",
    )
    
    # Track conversion
    await ab.track_event(
        experiment="checkout_flow",
        user_id="user_123",
        event="purchase",
        value=99.99,
    )
    
    # Get results
    results = await ab.get_results("checkout_flow")
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import random
import uuid
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
    TypeVar,
    Union,
)

T = TypeVar('T')

logger = logging.getLogger(__name__)


class ExperimentError(Exception):
    """Experiment error."""
    pass


class ExperimentNotFoundError(ExperimentError):
    """Experiment not found."""
    pass


class ExperimentStatus(str, Enum):
    """Experiment status."""
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class AssignmentStrategy(str, Enum):
    """Assignment strategy."""
    RANDOM = "random"
    HASH = "hash"  # Deterministic based on user ID
    STICKY = "sticky"  # Remember assignment
    ROUND_ROBIN = "round_robin"


@dataclass
class Variant:
    """Experiment variant."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    weight: int = 50  # Traffic percentage
    config: Dict[str, Any] = field(default_factory=dict)
    is_control: bool = False


@dataclass
class Experiment:
    """Experiment."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    status: ExperimentStatus = ExperimentStatus.DRAFT
    variants: List[Variant] = field(default_factory=list)
    traffic_allocation: float = 100.0  # Percentage of users in experiment
    targeting: Dict[str, Any] = field(default_factory=dict)
    strategy: AssignmentStrategy = AssignmentStrategy.HASH
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    owner: str = ""
    hypothesis: str = ""
    metrics: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def is_active(self) -> bool:
        """Check if active."""
        if self.status != ExperimentStatus.RUNNING:
            return False
        
        now = datetime.utcnow()
        if self.start_date and now < self.start_date:
            return False
        if self.end_date and now > self.end_date:
            return False
        
        return True


@dataclass
class Assignment:
    """User variant assignment."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    experiment_id: str = ""
    experiment_name: str = ""
    user_id: str = ""
    variant_id: str = ""
    variant_name: str = ""
    assigned_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Event:
    """Experiment event."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    experiment_id: str = ""
    user_id: str = ""
    variant_id: str = ""
    event_name: str = ""
    value: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VariantStats:
    """Variant statistics."""
    variant_id: str = ""
    variant_name: str = ""
    participants: int = 0
    conversions: int = 0
    conversion_rate: float = 0.0
    total_value: float = 0.0
    avg_value: float = 0.0
    events: Dict[str, int] = field(default_factory=dict)


@dataclass
class ExperimentResults:
    """Experiment results."""
    experiment_id: str = ""
    experiment_name: str = ""
    status: ExperimentStatus = ExperimentStatus.RUNNING
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    total_participants: int = 0
    variants: List[VariantStats] = field(default_factory=list)
    winning_variant: Optional[str] = None
    confidence: float = 0.0
    is_significant: bool = False
    generated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class FeatureFlag:
    """Feature flag."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    enabled: bool = False
    targeting: Dict[str, Any] = field(default_factory=dict)
    percentage: float = 0.0  # Rollout percentage
    variants: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


# Experiment store
class ExperimentStore(ABC):
    """Experiment storage."""
    
    @abstractmethod
    async def save(self, experiment: Experiment) -> None:
        """Save experiment."""
        pass
    
    @abstractmethod
    async def get(self, experiment_id: str) -> Optional[Experiment]:
        """Get experiment."""
        pass
    
    @abstractmethod
    async def get_by_name(self, name: str) -> Optional[Experiment]:
        """Get by name."""
        pass
    
    @abstractmethod
    async def list(
        self,
        status: Optional[ExperimentStatus] = None,
    ) -> List[Experiment]:
        """List experiments."""
        pass
    
    @abstractmethod
    async def delete(self, experiment_id: str) -> bool:
        """Delete experiment."""
        pass


class InMemoryExperimentStore(ExperimentStore):
    """In-memory experiment store."""
    
    def __init__(self):
        self._experiments: Dict[str, Experiment] = {}
        self._by_name: Dict[str, str] = {}
    
    async def save(self, experiment: Experiment) -> None:
        experiment.updated_at = datetime.utcnow()
        self._experiments[experiment.id] = experiment
        self._by_name[experiment.name] = experiment.id
    
    async def get(self, experiment_id: str) -> Optional[Experiment]:
        return self._experiments.get(experiment_id)
    
    async def get_by_name(self, name: str) -> Optional[Experiment]:
        exp_id = self._by_name.get(name)
        if exp_id:
            return self._experiments.get(exp_id)
        return None
    
    async def list(
        self,
        status: Optional[ExperimentStatus] = None,
    ) -> List[Experiment]:
        experiments = list(self._experiments.values())
        if status:
            experiments = [e for e in experiments if e.status == status]
        return sorted(experiments, key=lambda e: e.created_at, reverse=True)
    
    async def delete(self, experiment_id: str) -> bool:
        exp = self._experiments.pop(experiment_id, None)
        if exp:
            self._by_name.pop(exp.name, None)
            return True
        return False


# Assignment store
class AssignmentStore(ABC):
    """Assignment storage."""
    
    @abstractmethod
    async def save(self, assignment: Assignment) -> None:
        """Save assignment."""
        pass
    
    @abstractmethod
    async def get(
        self,
        experiment_id: str,
        user_id: str,
    ) -> Optional[Assignment]:
        """Get assignment."""
        pass
    
    @abstractmethod
    async def list_by_experiment(
        self,
        experiment_id: str,
    ) -> List[Assignment]:
        """List by experiment."""
        pass


class InMemoryAssignmentStore(AssignmentStore):
    """In-memory assignment store."""
    
    def __init__(self):
        self._assignments: Dict[str, Assignment] = {}  # exp:user -> assignment
    
    async def save(self, assignment: Assignment) -> None:
        key = f"{assignment.experiment_id}:{assignment.user_id}"
        self._assignments[key] = assignment
    
    async def get(
        self,
        experiment_id: str,
        user_id: str,
    ) -> Optional[Assignment]:
        key = f"{experiment_id}:{user_id}"
        return self._assignments.get(key)
    
    async def list_by_experiment(
        self,
        experiment_id: str,
    ) -> List[Assignment]:
        return [
            a for a in self._assignments.values()
            if a.experiment_id == experiment_id
        ]


# Event store
class EventStore(ABC):
    """Event storage."""
    
    @abstractmethod
    async def save(self, event: Event) -> None:
        """Save event."""
        pass
    
    @abstractmethod
    async def list_by_experiment(
        self,
        experiment_id: str,
        event_name: Optional[str] = None,
    ) -> List[Event]:
        """List by experiment."""
        pass


class InMemoryEventStore(EventStore):
    """In-memory event store."""
    
    def __init__(self):
        self._events: List[Event] = []
    
    async def save(self, event: Event) -> None:
        self._events.append(event)
    
    async def list_by_experiment(
        self,
        experiment_id: str,
        event_name: Optional[str] = None,
    ) -> List[Event]:
        events = [e for e in self._events if e.experiment_id == experiment_id]
        if event_name:
            events = [e for e in events if e.event_name == event_name]
        return events


# A/B testing service
class ABTestingService:
    """A/B testing service."""
    
    def __init__(
        self,
        experiment_store: Optional[ExperimentStore] = None,
        assignment_store: Optional[AssignmentStore] = None,
        event_store: Optional[EventStore] = None,
    ):
        self._experiments = experiment_store or InMemoryExperimentStore()
        self._assignments = assignment_store or InMemoryAssignmentStore()
        self._events = event_store or InMemoryEventStore()
        self._feature_flags: Dict[str, FeatureFlag] = {}
    
    # Experiment management
    async def create_experiment(
        self,
        name: str,
        variants: Optional[List[str]] = None,
        traffic_split: Optional[List[int]] = None,
        description: str = "",
        **kwargs,
    ) -> Experiment:
        """Create experiment."""
        variant_objs: List[Variant] = []
        
        if variants:
            weights = traffic_split or [100 // len(variants)] * len(variants)
            for i, variant_name in enumerate(variants):
                variant_objs.append(Variant(
                    name=variant_name,
                    weight=weights[i] if i < len(weights) else 0,
                    is_control=(i == 0),
                ))
        else:
            # Default control/treatment
            variant_objs = [
                Variant(name="control", weight=50, is_control=True),
                Variant(name="treatment", weight=50),
            ]
        
        experiment = Experiment(
            name=name,
            description=description,
            variants=variant_objs,
            **kwargs,
        )
        
        await self._experiments.save(experiment)
        
        logger.info(f"Experiment created: {name}")
        
        return experiment
    
    async def get_experiment(
        self,
        experiment_id: Optional[str] = None,
        name: Optional[str] = None,
    ) -> Optional[Experiment]:
        """Get experiment."""
        if experiment_id:
            return await self._experiments.get(experiment_id)
        if name:
            return await self._experiments.get_by_name(name)
        return None
    
    async def list_experiments(
        self,
        status: Optional[ExperimentStatus] = None,
    ) -> List[Experiment]:
        """List experiments."""
        return await self._experiments.list(status)
    
    async def start_experiment(self, name: str) -> Optional[Experiment]:
        """Start experiment."""
        experiment = await self._experiments.get_by_name(name)
        if experiment:
            experiment.status = ExperimentStatus.RUNNING
            experiment.start_date = datetime.utcnow()
            await self._experiments.save(experiment)
            logger.info(f"Experiment started: {name}")
        return experiment
    
    async def stop_experiment(self, name: str) -> Optional[Experiment]:
        """Stop experiment."""
        experiment = await self._experiments.get_by_name(name)
        if experiment:
            experiment.status = ExperimentStatus.COMPLETED
            experiment.end_date = datetime.utcnow()
            await self._experiments.save(experiment)
            logger.info(f"Experiment stopped: {name}")
        return experiment
    
    async def pause_experiment(self, name: str) -> Optional[Experiment]:
        """Pause experiment."""
        experiment = await self._experiments.get_by_name(name)
        if experiment:
            experiment.status = ExperimentStatus.PAUSED
            await self._experiments.save(experiment)
        return experiment
    
    # Variant assignment
    async def get_variant(
        self,
        experiment: str,
        user_id: str,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Get variant for user."""
        exp = await self._experiments.get_by_name(experiment)
        if not exp or not exp.is_active:
            return None
        
        # Check existing assignment
        assignment = await self._assignments.get(exp.id, user_id)
        if assignment:
            return assignment.variant_name
        
        # Check if user is in experiment
        if exp.traffic_allocation < 100:
            hash_val = self._hash_user(exp.id, user_id)
            if hash_val > exp.traffic_allocation:
                return None
        
        # Check targeting
        if exp.targeting and attributes:
            if not self._match_targeting(exp.targeting, attributes):
                return None
        
        # Assign variant
        variant = self._assign_variant(exp, user_id)
        
        assignment = Assignment(
            experiment_id=exp.id,
            experiment_name=exp.name,
            user_id=user_id,
            variant_id=variant.id,
            variant_name=variant.name,
        )
        await self._assignments.save(assignment)
        
        return variant.name
    
    async def get_variant_config(
        self,
        experiment: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """Get variant config for user."""
        exp = await self._experiments.get_by_name(experiment)
        if not exp:
            return {}
        
        variant_name = await self.get_variant(experiment, user_id)
        if not variant_name:
            return {}
        
        for variant in exp.variants:
            if variant.name == variant_name:
                return variant.config
        
        return {}
    
    def _hash_user(self, experiment_id: str, user_id: str) -> float:
        """Hash user for deterministic assignment."""
        hash_input = f"{experiment_id}:{user_id}"
        hash_val = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
        return (hash_val % 100)
    
    def _assign_variant(self, experiment: Experiment, user_id: str) -> Variant:
        """Assign variant to user."""
        if experiment.strategy == AssignmentStrategy.RANDOM:
            total_weight = sum(v.weight for v in experiment.variants)
            rand = random.randint(1, total_weight)
            cumulative = 0
            for variant in experiment.variants:
                cumulative += variant.weight
                if rand <= cumulative:
                    return variant
        
        elif experiment.strategy == AssignmentStrategy.HASH:
            hash_val = self._hash_user(experiment.id, user_id)
            cumulative = 0
            for variant in experiment.variants:
                cumulative += variant.weight
                if hash_val < cumulative:
                    return variant
        
        return experiment.variants[0]
    
    def _match_targeting(
        self,
        targeting: Dict[str, Any],
        attributes: Dict[str, Any],
    ) -> bool:
        """Match targeting rules."""
        for key, value in targeting.items():
            if key not in attributes:
                return False
            
            attr_value = attributes[key]
            
            if isinstance(value, list):
                if attr_value not in value:
                    return False
            elif attr_value != value:
                return False
        
        return True
    
    # Event tracking
    async def track_event(
        self,
        experiment: str,
        user_id: str,
        event: str,
        value: float = 1.0,
        **kwargs,
    ) -> Event:
        """Track event."""
        exp = await self._experiments.get_by_name(experiment)
        if not exp:
            raise ExperimentNotFoundError(f"Experiment not found: {experiment}")
        
        assignment = await self._assignments.get(exp.id, user_id)
        
        event_obj = Event(
            experiment_id=exp.id,
            user_id=user_id,
            variant_id=assignment.variant_id if assignment else "",
            event_name=event,
            value=value,
            metadata=kwargs,
        )
        
        await self._events.save(event_obj)
        
        return event_obj
    
    async def track_conversion(
        self,
        experiment: str,
        user_id: str,
        value: float = 1.0,
    ) -> Event:
        """Track conversion."""
        return await self.track_event(
            experiment=experiment,
            user_id=user_id,
            event="conversion",
            value=value,
        )
    
    # Results
    async def get_results(self, experiment: str) -> ExperimentResults:
        """Get experiment results."""
        exp = await self._experiments.get_by_name(experiment)
        if not exp:
            raise ExperimentNotFoundError(f"Experiment not found: {experiment}")
        
        assignments = await self._assignments.list_by_experiment(exp.id)
        events = await self._events.list_by_experiment(exp.id)
        conversions = await self._events.list_by_experiment(exp.id, "conversion")
        
        # Calculate variant stats
        variant_stats: Dict[str, VariantStats] = {}
        
        for variant in exp.variants:
            variant_stats[variant.id] = VariantStats(
                variant_id=variant.id,
                variant_name=variant.name,
            )
        
        # Count participants
        for assignment in assignments:
            if assignment.variant_id in variant_stats:
                variant_stats[assignment.variant_id].participants += 1
        
        # Count events
        for event in events:
            if event.variant_id in variant_stats:
                stats = variant_stats[event.variant_id]
                stats.events[event.event_name] = stats.events.get(event.event_name, 0) + 1
                stats.total_value += event.value
        
        # Calculate conversion rates
        for conv in conversions:
            if conv.variant_id in variant_stats:
                variant_stats[conv.variant_id].conversions += 1
        
        for stats in variant_stats.values():
            if stats.participants > 0:
                stats.conversion_rate = stats.conversions / stats.participants
                stats.avg_value = stats.total_value / stats.participants
        
        # Find winner
        stats_list = list(variant_stats.values())
        winning = None
        if stats_list:
            winning = max(stats_list, key=lambda s: s.conversion_rate)
        
        return ExperimentResults(
            experiment_id=exp.id,
            experiment_name=exp.name,
            status=exp.status,
            start_date=exp.start_date,
            end_date=exp.end_date,
            total_participants=len(assignments),
            variants=stats_list,
            winning_variant=winning.variant_name if winning else None,
        )
    
    # Feature flags
    async def create_feature_flag(
        self,
        name: str,
        enabled: bool = False,
        percentage: float = 0.0,
        targeting: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> FeatureFlag:
        """Create feature flag."""
        flag = FeatureFlag(
            name=name,
            enabled=enabled,
            percentage=percentage,
            targeting=targeting or {},
            **kwargs,
        )
        self._feature_flags[name] = flag
        return flag
    
    async def is_enabled(
        self,
        flag_name: str,
        user_id: str = "",
        attributes: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Check if feature flag is enabled."""
        flag = self._feature_flags.get(flag_name)
        if not flag:
            return False
        
        if not flag.enabled:
            return False
        
        # Check targeting
        if flag.targeting and attributes:
            if not self._match_targeting(flag.targeting, attributes):
                return False
        
        # Check rollout percentage
        if flag.percentage < 100 and user_id:
            hash_val = self._hash_user(flag_name, user_id)
            if hash_val >= flag.percentage:
                return False
        
        return True
    
    async def get_feature_value(
        self,
        flag_name: str,
        user_id: str = "",
        default: Any = None,
    ) -> Any:
        """Get feature value."""
        flag = self._feature_flags.get(flag_name)
        if not flag or not flag.enabled:
            return default
        
        if flag.variants:
            # Multi-variate feature flag
            hash_val = self._hash_user(flag_name, user_id)
            cumulative = 0
            for name, config in flag.variants.items():
                weight = config.get("weight", 0)
                cumulative += weight
                if hash_val < cumulative:
                    return config.get("value", default)
        
        return default


# Factory functions
def create_ab_testing(
    experiment_store: Optional[ExperimentStore] = None,
    assignment_store: Optional[AssignmentStore] = None,
) -> ABTestingService:
    """Create A/B testing service."""
    return ABTestingService(
        experiment_store=experiment_store,
        assignment_store=assignment_store,
    )


def create_experiment(
    name: str,
    variants: Optional[List[str]] = None,
    traffic_split: Optional[List[int]] = None,
    **kwargs,
) -> Experiment:
    """Create experiment object."""
    variant_objs = []
    if variants:
        weights = traffic_split or [100 // len(variants)] * len(variants)
        for i, variant_name in enumerate(variants):
            variant_objs.append(Variant(
                name=variant_name,
                weight=weights[i] if i < len(weights) else 0,
                is_control=(i == 0),
            ))
    
    return Experiment(name=name, variants=variant_objs, **kwargs)


def create_variant(
    name: str,
    weight: int = 50,
    config: Optional[Dict[str, Any]] = None,
    **kwargs,
) -> Variant:
    """Create variant."""
    return Variant(
        name=name,
        weight=weight,
        config=config or {},
        **kwargs,
    )


def create_feature_flag(
    name: str,
    enabled: bool = False,
    percentage: float = 0.0,
    **kwargs,
) -> FeatureFlag:
    """Create feature flag."""
    return FeatureFlag(
        name=name,
        enabled=enabled,
        percentage=percentage,
        **kwargs,
    )


__all__ = [
    # Exceptions
    "ExperimentError",
    "ExperimentNotFoundError",
    # Enums
    "ExperimentStatus",
    "AssignmentStrategy",
    # Data classes
    "Variant",
    "Experiment",
    "Assignment",
    "Event",
    "VariantStats",
    "ExperimentResults",
    "FeatureFlag",
    # Stores
    "ExperimentStore",
    "InMemoryExperimentStore",
    "AssignmentStore",
    "InMemoryAssignmentStore",
    "EventStore",
    "InMemoryEventStore",
    # Service
    "ABTestingService",
    # Factory functions
    "create_ab_testing",
    "create_experiment",
    "create_variant",
    "create_feature_flag",
]
