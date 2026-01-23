"""
Enterprise Analytics Engine Module.

Event tracking, funnels, cohorts,
user behavior analytics, and reporting.

Example:
    # Create analytics engine
    analytics = create_analytics_engine()
    
    # Track events
    await analytics.track(
        user_id="user_123",
        event="page_view",
        properties={"page": "/checkout"},
    )
    
    # Identify user
    await analytics.identify(
        user_id="user_123",
        traits={"plan": "pro", "company": "Acme"},
    )
    
    # Define funnel
    funnel = await analytics.create_funnel(
        name="checkout_funnel",
        steps=["add_to_cart", "checkout_start", "payment", "purchase"],
    )
    
    # Get funnel analysis
    results = await analytics.analyze_funnel("checkout_funnel")
"""

from __future__ import annotations

import asyncio
import json
import logging
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


class AnalyticsError(Exception):
    """Analytics error."""
    pass


class EventType(str, Enum):
    """Event type."""
    TRACK = "track"
    IDENTIFY = "identify"
    PAGE = "page"
    SCREEN = "screen"
    GROUP = "group"
    ALIAS = "alias"


class AggregationType(str, Enum):
    """Aggregation type."""
    COUNT = "count"
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    UNIQUE = "unique"


class TimeGranularity(str, Enum):
    """Time granularity."""
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"


@dataclass
class Event:
    """Analytics event."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: EventType = EventType.TRACK
    user_id: str = ""
    anonymous_id: str = ""
    event_name: str = ""
    properties: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    session_id: str = ""
    
    @property
    def resolved_id(self) -> str:
        """Get resolved user ID."""
        return self.user_id or self.anonymous_id


@dataclass
class UserProfile:
    """User profile."""
    id: str = ""
    anonymous_ids: List[str] = field(default_factory=list)
    traits: Dict[str, Any] = field(default_factory=dict)
    first_seen: datetime = field(default_factory=datetime.utcnow)
    last_seen: datetime = field(default_factory=datetime.utcnow)
    event_count: int = 0
    groups: List[str] = field(default_factory=list)


@dataclass
class Funnel:
    """Funnel definition."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    steps: List[str] = field(default_factory=list)
    conversion_window: int = 86400 * 7  # 7 days in seconds
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class FunnelStep:
    """Funnel step result."""
    name: str = ""
    entered: int = 0
    converted: int = 0
    dropped: int = 0
    conversion_rate: float = 0.0
    avg_time_to_convert: float = 0.0


@dataclass
class FunnelAnalysis:
    """Funnel analysis result."""
    funnel_id: str = ""
    funnel_name: str = ""
    steps: List[FunnelStep] = field(default_factory=list)
    overall_conversion: float = 0.0
    total_entries: int = 0
    total_completions: int = 0
    period_start: datetime = field(default_factory=datetime.utcnow)
    period_end: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Cohort:
    """Cohort definition."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    definition: Dict[str, Any] = field(default_factory=dict)
    user_ids: Set[str] = field(default_factory=set)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class MetricDefinition:
    """Metric definition."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    event_name: str = ""
    aggregation: AggregationType = AggregationType.COUNT
    property_name: str = ""
    filters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MetricResult:
    """Metric result."""
    metric_id: str = ""
    metric_name: str = ""
    value: float = 0.0
    previous_value: float = 0.0
    change_percent: float = 0.0
    period_start: datetime = field(default_factory=datetime.utcnow)
    period_end: datetime = field(default_factory=datetime.utcnow)


@dataclass
class TimeSeriesPoint:
    """Time series data point."""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    value: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SegmentResult:
    """Segment analysis result."""
    segment_name: str = ""
    user_count: int = 0
    event_count: int = 0
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AnalyticsStats:
    """Analytics statistics."""
    total_events: int = 0
    total_users: int = 0
    events_today: int = 0
    active_users_24h: int = 0
    by_event: Dict[str, int] = field(default_factory=dict)


# Event store
class EventStore(ABC):
    """Event storage."""
    
    @abstractmethod
    async def save(self, event: Event) -> None:
        """Save event."""
        pass
    
    @abstractmethod
    async def query(
        self,
        event_name: Optional[str] = None,
        user_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        properties: Optional[Dict[str, Any]] = None,
        limit: int = 1000,
    ) -> List[Event]:
        """Query events."""
        pass
    
    @abstractmethod
    async def count(
        self,
        event_name: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> int:
        """Count events."""
        pass


class InMemoryEventStore(EventStore):
    """In-memory event store."""
    
    def __init__(self):
        self._events: List[Event] = []
    
    async def save(self, event: Event) -> None:
        self._events.append(event)
    
    async def query(
        self,
        event_name: Optional[str] = None,
        user_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        properties: Optional[Dict[str, Any]] = None,
        limit: int = 1000,
    ) -> List[Event]:
        results = []
        
        for event in self._events:
            if event_name and event.event_name != event_name:
                continue
            if user_id and event.resolved_id != user_id:
                continue
            if start_time and event.timestamp < start_time:
                continue
            if end_time and event.timestamp > end_time:
                continue
            if properties:
                match = True
                for k, v in properties.items():
                    if event.properties.get(k) != v:
                        match = False
                        break
                if not match:
                    continue
            
            results.append(event)
            
            if len(results) >= limit:
                break
        
        return results
    
    async def count(
        self,
        event_name: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> int:
        events = await self.query(
            event_name=event_name,
            start_time=start_time,
            end_time=end_time,
            limit=1000000,
        )
        return len(events)


# User store
class UserStore(ABC):
    """User storage."""
    
    @abstractmethod
    async def save(self, user: UserProfile) -> None:
        """Save user."""
        pass
    
    @abstractmethod
    async def get(self, user_id: str) -> Optional[UserProfile]:
        """Get user."""
        pass
    
    @abstractmethod
    async def list(
        self,
        traits: Optional[Dict[str, Any]] = None,
    ) -> List[UserProfile]:
        """List users."""
        pass


class InMemoryUserStore(UserStore):
    """In-memory user store."""
    
    def __init__(self):
        self._users: Dict[str, UserProfile] = {}
    
    async def save(self, user: UserProfile) -> None:
        self._users[user.id] = user
    
    async def get(self, user_id: str) -> Optional[UserProfile]:
        return self._users.get(user_id)
    
    async def list(
        self,
        traits: Optional[Dict[str, Any]] = None,
    ) -> List[UserProfile]:
        users = list(self._users.values())
        if traits:
            users = [
                u for u in users
                if all(u.traits.get(k) == v for k, v in traits.items())
            ]
        return users


# Analytics engine
class AnalyticsEngine:
    """Analytics engine."""
    
    def __init__(
        self,
        event_store: Optional[EventStore] = None,
        user_store: Optional[UserStore] = None,
    ):
        self._events = event_store or InMemoryEventStore()
        self._users = user_store or InMemoryUserStore()
        self._funnels: Dict[str, Funnel] = {}
        self._cohorts: Dict[str, Cohort] = {}
        self._metrics: Dict[str, MetricDefinition] = {}
        self._stats = AnalyticsStats()
        self._hooks: Dict[str, List[Callable]] = {}
    
    # Event tracking
    async def track(
        self,
        event: str,
        user_id: str = "",
        anonymous_id: str = "",
        properties: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None,
        **kwargs,
    ) -> Event:
        """Track event."""
        event_obj = Event(
            type=EventType.TRACK,
            user_id=user_id,
            anonymous_id=anonymous_id or str(uuid.uuid4()),
            event_name=event,
            properties=properties or {},
            context=context or {},
            timestamp=timestamp or datetime.utcnow(),
            **kwargs,
        )
        
        await self._events.save(event_obj)
        
        # Update stats
        self._stats.total_events += 1
        self._stats.by_event[event] = self._stats.by_event.get(event, 0) + 1
        
        # Update user
        if user_id:
            await self._update_user(user_id, anonymous_id)
        
        # Fire hooks
        await self._fire_hook("event.tracked", event_obj)
        
        return event_obj
    
    async def identify(
        self,
        user_id: str,
        traits: Optional[Dict[str, Any]] = None,
        anonymous_id: str = "",
        **kwargs,
    ) -> UserProfile:
        """Identify user."""
        user = await self._users.get(user_id)
        
        if not user:
            user = UserProfile(id=user_id)
            self._stats.total_users += 1
        
        if traits:
            user.traits.update(traits)
        
        if anonymous_id and anonymous_id not in user.anonymous_ids:
            user.anonymous_ids.append(anonymous_id)
        
        user.last_seen = datetime.utcnow()
        await self._users.save(user)
        
        # Track identify event
        await self.track(
            event="$identify",
            user_id=user_id,
            properties=traits,
        )
        
        return user
    
    async def page(
        self,
        name: str,
        user_id: str = "",
        properties: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Event:
        """Track page view."""
        props = properties or {}
        props["page_name"] = name
        
        return await self.track(
            event="$pageview",
            user_id=user_id,
            properties=props,
            **kwargs,
        )
    
    async def screen(
        self,
        name: str,
        user_id: str = "",
        properties: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Event:
        """Track screen view."""
        props = properties or {}
        props["screen_name"] = name
        
        return await self.track(
            event="$screen",
            user_id=user_id,
            properties=props,
            **kwargs,
        )
    
    async def group(
        self,
        user_id: str,
        group_id: str,
        traits: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Associate user with group."""
        user = await self._users.get(user_id)
        if user and group_id not in user.groups:
            user.groups.append(group_id)
            await self._users.save(user)
    
    async def alias(
        self,
        previous_id: str,
        user_id: str,
    ) -> None:
        """Alias user ID."""
        user = await self._users.get(user_id)
        if user and previous_id not in user.anonymous_ids:
            user.anonymous_ids.append(previous_id)
            await self._users.save(user)
    
    async def _update_user(
        self,
        user_id: str,
        anonymous_id: str = "",
    ) -> None:
        """Update user profile."""
        user = await self._users.get(user_id)
        
        if not user:
            user = UserProfile(id=user_id)
            self._stats.total_users += 1
        
        user.event_count += 1
        user.last_seen = datetime.utcnow()
        
        if anonymous_id and anonymous_id not in user.anonymous_ids:
            user.anonymous_ids.append(anonymous_id)
        
        await self._users.save(user)
    
    # Querying
    async def query_events(
        self,
        event_name: Optional[str] = None,
        user_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        properties: Optional[Dict[str, Any]] = None,
        limit: int = 1000,
    ) -> List[Event]:
        """Query events."""
        return await self._events.query(
            event_name=event_name,
            user_id=user_id,
            start_time=start_time,
            end_time=end_time,
            properties=properties,
            limit=limit,
        )
    
    async def count_events(
        self,
        event_name: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> int:
        """Count events."""
        return await self._events.count(
            event_name=event_name,
            start_time=start_time,
            end_time=end_time,
        )
    
    async def get_user(self, user_id: str) -> Optional[UserProfile]:
        """Get user profile."""
        return await self._users.get(user_id)
    
    async def get_user_events(
        self,
        user_id: str,
        limit: int = 100,
    ) -> List[Event]:
        """Get user events."""
        return await self._events.query(
            user_id=user_id,
            limit=limit,
        )
    
    # Funnels
    async def create_funnel(
        self,
        name: str,
        steps: List[str],
        conversion_window: int = 86400 * 7,
        **kwargs,
    ) -> Funnel:
        """Create funnel."""
        funnel = Funnel(
            name=name,
            steps=steps,
            conversion_window=conversion_window,
            **kwargs,
        )
        self._funnels[name] = funnel
        return funnel
    
    async def analyze_funnel(
        self,
        name: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> FunnelAnalysis:
        """Analyze funnel."""
        funnel = self._funnels.get(name)
        if not funnel:
            raise AnalyticsError(f"Funnel not found: {name}")
        
        start = start_time or (datetime.utcnow() - timedelta(days=30))
        end = end_time or datetime.utcnow()
        
        # Get events for each step
        step_events: Dict[str, List[Event]] = {}
        for step in funnel.steps:
            events = await self._events.query(
                event_name=step,
                start_time=start,
                end_time=end,
            )
            step_events[step] = events
        
        # Build user journeys
        user_journeys: Dict[str, Dict[str, datetime]] = defaultdict(dict)
        for step, events in step_events.items():
            for event in events:
                user_id = event.resolved_id
                if step not in user_journeys[user_id]:
                    user_journeys[user_id][step] = event.timestamp
        
        # Calculate funnel
        step_results: List[FunnelStep] = []
        prev_users: Set[str] = set()
        
        for i, step in enumerate(funnel.steps):
            step_users = set()
            
            for user_id, journey in user_journeys.items():
                if step not in journey:
                    continue
                
                # Check if previous steps completed
                if i > 0:
                    prev_step = funnel.steps[i - 1]
                    if prev_step not in journey:
                        continue
                    # Check time window
                    time_diff = (journey[step] - journey[prev_step]).total_seconds()
                    if time_diff > funnel.conversion_window or time_diff < 0:
                        continue
                
                step_users.add(user_id)
            
            entered = len(step_users) if i == 0 else len(prev_users)
            converted = len(step_users)
            dropped = entered - converted
            
            step_results.append(FunnelStep(
                name=step,
                entered=entered,
                converted=converted,
                dropped=dropped,
                conversion_rate=converted / entered if entered > 0 else 0,
            ))
            
            prev_users = step_users
        
        total_entries = step_results[0].entered if step_results else 0
        total_completions = step_results[-1].converted if step_results else 0
        
        return FunnelAnalysis(
            funnel_id=funnel.id,
            funnel_name=funnel.name,
            steps=step_results,
            overall_conversion=total_completions / total_entries if total_entries > 0 else 0,
            total_entries=total_entries,
            total_completions=total_completions,
            period_start=start,
            period_end=end,
        )
    
    # Cohorts
    async def create_cohort(
        self,
        name: str,
        definition: Dict[str, Any],
        **kwargs,
    ) -> Cohort:
        """Create cohort."""
        cohort = Cohort(
            name=name,
            definition=definition,
            **kwargs,
        )
        
        # Populate cohort
        await self._populate_cohort(cohort)
        
        self._cohorts[name] = cohort
        return cohort
    
    async def _populate_cohort(self, cohort: Cohort) -> None:
        """Populate cohort based on definition."""
        definition = cohort.definition
        
        # Event-based cohort
        if "event" in definition:
            events = await self._events.query(
                event_name=definition["event"],
                properties=definition.get("properties"),
            )
            for event in events:
                if event.resolved_id:
                    cohort.user_ids.add(event.resolved_id)
        
        # Trait-based cohort
        elif "traits" in definition:
            users = await self._users.list(traits=definition["traits"])
            for user in users:
                cohort.user_ids.add(user.id)
    
    async def get_cohort(self, name: str) -> Optional[Cohort]:
        """Get cohort."""
        return self._cohorts.get(name)
    
    # Metrics
    async def define_metric(
        self,
        name: str,
        event_name: str,
        aggregation: AggregationType = AggregationType.COUNT,
        property_name: str = "",
        filters: Optional[Dict[str, Any]] = None,
    ) -> MetricDefinition:
        """Define metric."""
        metric = MetricDefinition(
            name=name,
            event_name=event_name,
            aggregation=aggregation,
            property_name=property_name,
            filters=filters or {},
        )
        self._metrics[name] = metric
        return metric
    
    async def compute_metric(
        self,
        name: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> MetricResult:
        """Compute metric."""
        metric = self._metrics.get(name)
        if not metric:
            raise AnalyticsError(f"Metric not found: {name}")
        
        events = await self._events.query(
            event_name=metric.event_name,
            start_time=start_time,
            end_time=end_time,
            properties=metric.filters if metric.filters else None,
        )
        
        value = 0.0
        
        if metric.aggregation == AggregationType.COUNT:
            value = len(events)
        
        elif metric.aggregation == AggregationType.SUM:
            value = sum(
                float(e.properties.get(metric.property_name, 0))
                for e in events
            )
        
        elif metric.aggregation == AggregationType.AVG:
            values = [
                float(e.properties.get(metric.property_name, 0))
                for e in events
            ]
            value = sum(values) / len(values) if values else 0
        
        elif metric.aggregation == AggregationType.MIN:
            values = [
                float(e.properties.get(metric.property_name, 0))
                for e in events
            ]
            value = min(values) if values else 0
        
        elif metric.aggregation == AggregationType.MAX:
            values = [
                float(e.properties.get(metric.property_name, 0))
                for e in events
            ]
            value = max(values) if values else 0
        
        elif metric.aggregation == AggregationType.UNIQUE:
            unique = set(e.resolved_id for e in events)
            value = len(unique)
        
        return MetricResult(
            metric_id=metric.id,
            metric_name=metric.name,
            value=value,
            period_start=start_time or datetime.utcnow() - timedelta(days=30),
            period_end=end_time or datetime.utcnow(),
        )
    
    # Time series
    async def time_series(
        self,
        event_name: str,
        granularity: TimeGranularity = TimeGranularity.DAY,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[TimeSeriesPoint]:
        """Get time series data."""
        events = await self._events.query(
            event_name=event_name,
            start_time=start_time,
            end_time=end_time,
        )
        
        # Group by time bucket
        buckets: Dict[str, int] = defaultdict(int)
        
        for event in events:
            if granularity == TimeGranularity.HOUR:
                key = event.timestamp.strftime("%Y-%m-%d %H:00")
            elif granularity == TimeGranularity.DAY:
                key = event.timestamp.strftime("%Y-%m-%d")
            elif granularity == TimeGranularity.WEEK:
                key = event.timestamp.strftime("%Y-W%W")
            elif granularity == TimeGranularity.MONTH:
                key = event.timestamp.strftime("%Y-%m")
            else:
                key = event.timestamp.strftime("%Y")
            
            buckets[key] += 1
        
        points = []
        for key, count in sorted(buckets.items()):
            points.append(TimeSeriesPoint(
                timestamp=datetime.strptime(
                    key,
                    "%Y-%m-%d %H:00" if granularity == TimeGranularity.HOUR
                    else "%Y-%m-%d" if granularity == TimeGranularity.DAY
                    else "%Y-W%W" if granularity == TimeGranularity.WEEK
                    else "%Y-%m" if granularity == TimeGranularity.MONTH
                    else "%Y"
                ),
                value=count,
            ))
        
        return points
    
    # Stats
    def get_stats(self) -> AnalyticsStats:
        """Get statistics."""
        return self._stats
    
    # Hooks
    def on(self, event: str, handler: Callable) -> None:
        """Register event handler."""
        if event not in self._hooks:
            self._hooks[event] = []
        self._hooks[event].append(handler)
    
    async def _fire_hook(self, event: str, data: Any) -> None:
        """Fire event hooks."""
        for handler in self._hooks.get(event, []):
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(data)
                else:
                    handler(data)
            except Exception as e:
                logger.error(f"Hook error for {event}: {e}")


# Factory functions
def create_analytics_engine(
    event_store: Optional[EventStore] = None,
    user_store: Optional[UserStore] = None,
) -> AnalyticsEngine:
    """Create analytics engine."""
    return AnalyticsEngine(
        event_store=event_store,
        user_store=user_store,
    )


def create_funnel(
    name: str,
    steps: List[str],
    **kwargs,
) -> Funnel:
    """Create funnel."""
    return Funnel(name=name, steps=steps, **kwargs)


def create_cohort(
    name: str,
    definition: Dict[str, Any],
    **kwargs,
) -> Cohort:
    """Create cohort."""
    return Cohort(name=name, definition=definition, **kwargs)


def create_metric(
    name: str,
    event_name: str,
    aggregation: AggregationType = AggregationType.COUNT,
    **kwargs,
) -> MetricDefinition:
    """Create metric definition."""
    return MetricDefinition(
        name=name,
        event_name=event_name,
        aggregation=aggregation,
        **kwargs,
    )


__all__ = [
    # Exceptions
    "AnalyticsError",
    # Enums
    "EventType",
    "AggregationType",
    "TimeGranularity",
    # Data classes
    "Event",
    "UserProfile",
    "Funnel",
    "FunnelStep",
    "FunnelAnalysis",
    "Cohort",
    "MetricDefinition",
    "MetricResult",
    "TimeSeriesPoint",
    "SegmentResult",
    "AnalyticsStats",
    # Stores
    "EventStore",
    "InMemoryEventStore",
    "UserStore",
    "InMemoryUserStore",
    # Engine
    "AnalyticsEngine",
    # Factory functions
    "create_analytics_engine",
    "create_funnel",
    "create_cohort",
    "create_metric",
]
