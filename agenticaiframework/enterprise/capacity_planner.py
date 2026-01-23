"""
Enterprise Capacity Planner Module.

Resource capacity planning, forecasting, scaling
recommendations, and capacity alerts.

Example:
    # Create capacity planner
    planner = create_capacity_planner()
    
    # Define resource
    await planner.add_resource(
        name="api_servers",
        resource_type=ResourceType.COMPUTE,
        capacity=100,
        unit="instances",
    )
    
    # Record usage
    await planner.record_usage(
        resource_name="api_servers",
        usage=75,
    )
    
    # Get forecast
    forecast = await planner.forecast(
        resource_name="api_servers",
        days_ahead=30,
    )
"""

from __future__ import annotations

import asyncio
import logging
import math
import statistics
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
    Union,
)

logger = logging.getLogger(__name__)


class CapacityError(Exception):
    """Capacity error."""
    pass


class ResourceType(str, Enum):
    """Resource type."""
    COMPUTE = "compute"
    MEMORY = "memory"
    STORAGE = "storage"
    NETWORK = "network"
    DATABASE = "database"
    CACHE = "cache"
    QUEUE = "queue"
    API = "api"
    CUSTOM = "custom"


class ScalingDirection(str, Enum):
    """Scaling direction."""
    UP = "up"
    DOWN = "down"
    NONE = "none"


class AlertLevel(str, Enum):
    """Alert level."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class ForecastMethod(str, Enum):
    """Forecast method."""
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    MOVING_AVERAGE = "moving_average"


@dataclass
class Resource:
    """Resource definition."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    resource_type: ResourceType = ResourceType.COMPUTE
    capacity: float = 100.0
    unit: str = "units"
    
    # Thresholds
    warning_threshold: float = 70.0
    critical_threshold: float = 90.0
    
    # Scaling
    min_capacity: float = 1.0
    max_capacity: float = 1000.0
    scale_step: float = 10.0
    
    # Metadata
    description: str = ""
    tags: Dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UsageRecord:
    """Usage record."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    resource_id: str = ""
    usage: float = 0.0
    utilization: float = 0.0  # Percentage
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CapacityForecast:
    """Capacity forecast."""
    resource_id: str = ""
    resource_name: str = ""
    current_usage: float = 0.0
    current_capacity: float = 0.0
    current_utilization: float = 0.0
    
    # Predictions
    predicted_usage: float = 0.0
    predicted_utilization: float = 0.0
    forecast_date: datetime = field(default_factory=datetime.utcnow)
    
    # Capacity planning
    days_until_warning: Optional[int] = None
    days_until_critical: Optional[int] = None
    days_until_full: Optional[int] = None
    
    # Recommendations
    scaling_direction: ScalingDirection = ScalingDirection.NONE
    recommended_capacity: float = 0.0
    
    # Confidence
    confidence: float = 0.0
    method: ForecastMethod = ForecastMethod.LINEAR


@dataclass
class ScalingRecommendation:
    """Scaling recommendation."""
    resource_id: str = ""
    resource_name: str = ""
    current_capacity: float = 0.0
    recommended_capacity: float = 0.0
    direction: ScalingDirection = ScalingDirection.NONE
    urgency: AlertLevel = AlertLevel.INFO
    reason: str = ""
    estimated_cost_change: Optional[float] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class CapacityAlert:
    """Capacity alert."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    resource_id: str = ""
    resource_name: str = ""
    level: AlertLevel = AlertLevel.WARNING
    utilization: float = 0.0
    threshold: float = 0.0
    message: str = ""
    triggered_at: datetime = field(default_factory=datetime.utcnow)
    acknowledged: bool = False


@dataclass
class CapacityStats:
    """Capacity statistics."""
    total_resources: int = 0
    healthy: int = 0
    warning: int = 0
    critical: int = 0
    avg_utilization: float = 0.0
    total_capacity: float = 0.0
    total_usage: float = 0.0


# Resource store
class ResourceStore(ABC):
    """Resource storage."""
    
    @abstractmethod
    async def save(self, resource: Resource) -> None:
        pass
    
    @abstractmethod
    async def get(self, resource_id: str) -> Optional[Resource]:
        pass
    
    @abstractmethod
    async def get_by_name(self, name: str) -> Optional[Resource]:
        pass
    
    @abstractmethod
    async def list_all(self) -> List[Resource]:
        pass
    
    @abstractmethod
    async def delete(self, resource_id: str) -> bool:
        pass


class InMemoryResourceStore(ResourceStore):
    """In-memory resource store."""
    
    def __init__(self):
        self._resources: Dict[str, Resource] = {}
        self._by_name: Dict[str, str] = {}
    
    async def save(self, resource: Resource) -> None:
        self._resources[resource.id] = resource
        self._by_name[resource.name] = resource.id
    
    async def get(self, resource_id: str) -> Optional[Resource]:
        return self._resources.get(resource_id)
    
    async def get_by_name(self, name: str) -> Optional[Resource]:
        resource_id = self._by_name.get(name)
        if resource_id:
            return self._resources.get(resource_id)
        return None
    
    async def list_all(self) -> List[Resource]:
        return list(self._resources.values())
    
    async def delete(self, resource_id: str) -> bool:
        resource = self._resources.get(resource_id)
        if resource:
            del self._resources[resource_id]
            self._by_name.pop(resource.name, None)
            return True
        return False


# Usage store
class UsageStore(ABC):
    """Usage storage."""
    
    @abstractmethod
    async def save(self, record: UsageRecord) -> None:
        pass
    
    @abstractmethod
    async def list_by_resource(
        self,
        resource_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> List[UsageRecord]:
        pass
    
    @abstractmethod
    async def get_latest(self, resource_id: str) -> Optional[UsageRecord]:
        pass


class InMemoryUsageStore(UsageStore):
    """In-memory usage store."""
    
    def __init__(self, max_records: int = 1000000):
        self._records: Dict[str, UsageRecord] = {}
        self._by_resource: Dict[str, List[str]] = {}
        self._max_records = max_records
    
    async def save(self, record: UsageRecord) -> None:
        self._records[record.id] = record
        
        if record.resource_id not in self._by_resource:
            self._by_resource[record.resource_id] = []
        
        self._by_resource[record.resource_id].append(record.id)
        
        # Trim old records
        if len(self._records) > self._max_records:
            oldest = list(self._records.keys())[0]
            del self._records[oldest]
    
    async def list_by_resource(
        self,
        resource_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> List[UsageRecord]:
        record_ids = self._by_resource.get(resource_id, [])
        records = []
        
        for record_id in record_ids:
            record = self._records.get(record_id)
            if record:
                if start_date <= record.timestamp <= end_date:
                    records.append(record)
        
        return sorted(records, key=lambda r: r.timestamp)
    
    async def get_latest(self, resource_id: str) -> Optional[UsageRecord]:
        record_ids = self._by_resource.get(resource_id, [])
        if not record_ids:
            return None
        
        latest = None
        for record_id in record_ids:
            record = self._records.get(record_id)
            if record:
                if latest is None or record.timestamp > latest.timestamp:
                    latest = record
        
        return latest


# Forecaster
class Forecaster:
    """Usage forecaster."""
    
    @staticmethod
    def linear_forecast(
        data_points: List[Tuple[datetime, float]],
        target_date: datetime,
    ) -> Tuple[float, float]:
        """Linear regression forecast."""
        if len(data_points) < 2:
            if data_points:
                return data_points[-1][1], 0.5
            return 0.0, 0.0
        
        # Convert to numeric
        base_time = data_points[0][0]
        x = [(p[0] - base_time).total_seconds() for p in data_points]
        y = [p[1] for p in data_points]
        
        n = len(x)
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(xi * yi for xi, yi in zip(x, y))
        sum_x2 = sum(xi ** 2 for xi in x)
        
        denom = n * sum_x2 - sum_x ** 2
        if denom == 0:
            return y[-1], 0.5
        
        slope = (n * sum_xy - sum_x * sum_y) / denom
        intercept = (sum_y - slope * sum_x) / n
        
        target_x = (target_date - base_time).total_seconds()
        prediction = intercept + slope * target_x
        
        # Calculate R-squared for confidence
        y_mean = sum_y / n
        ss_tot = sum((yi - y_mean) ** 2 for yi in y)
        ss_res = sum((yi - (intercept + slope * xi)) ** 2 for xi, yi in zip(x, y))
        
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        confidence = max(0, min(1, r_squared))
        
        return max(0, prediction), confidence
    
    @staticmethod
    def moving_average_forecast(
        data_points: List[Tuple[datetime, float]],
        window: int = 7,
    ) -> Tuple[float, float]:
        """Moving average forecast."""
        if not data_points:
            return 0.0, 0.0
        
        values = [p[1] for p in data_points]
        
        if len(values) <= window:
            return statistics.mean(values), 0.5
        
        ma = statistics.mean(values[-window:])
        
        # Trend
        prev_ma = statistics.mean(values[-window * 2:-window]) if len(values) >= window * 2 else ma
        trend = ma - prev_ma
        
        prediction = ma + trend
        
        # Confidence based on variance
        variance = statistics.variance(values[-window:]) if len(values) >= window else 0
        confidence = max(0, 1 - (variance / (ma + 1)))
        
        return max(0, prediction), min(1, confidence)
    
    @staticmethod
    def exponential_forecast(
        data_points: List[Tuple[datetime, float]],
        alpha: float = 0.3,
    ) -> Tuple[float, float]:
        """Exponential smoothing forecast."""
        if not data_points:
            return 0.0, 0.0
        
        values = [p[1] for p in data_points]
        
        # Simple exponential smoothing
        smoothed = values[0]
        for v in values[1:]:
            smoothed = alpha * v + (1 - alpha) * smoothed
        
        # Double exponential for trend
        if len(values) > 1:
            trend = values[-1] - values[-2]
            prediction = smoothed + trend
        else:
            prediction = smoothed
        
        confidence = 0.7  # Default for exponential
        
        return max(0, prediction), confidence


# Capacity planner
class CapacityPlanner:
    """Capacity planner."""
    
    def __init__(
        self,
        resource_store: Optional[ResourceStore] = None,
        usage_store: Optional[UsageStore] = None,
    ):
        self._resource_store = resource_store or InMemoryResourceStore()
        self._usage_store = usage_store or InMemoryUsageStore()
        self._alert_handlers: List[Callable] = []
        self._alerts: List[CapacityAlert] = []
        self._triggered_alerts: set = set()
    
    async def add_resource(
        self,
        name: str,
        resource_type: Union[str, ResourceType] = ResourceType.COMPUTE,
        capacity: float = 100.0,
        unit: str = "units",
        warning_threshold: float = 70.0,
        critical_threshold: float = 90.0,
        **kwargs,
    ) -> Resource:
        """Add resource to track."""
        if isinstance(resource_type, str):
            resource_type = ResourceType(resource_type)
        
        resource = Resource(
            name=name,
            resource_type=resource_type,
            capacity=capacity,
            unit=unit,
            warning_threshold=warning_threshold,
            critical_threshold=critical_threshold,
            **kwargs,
        )
        
        await self._resource_store.save(resource)
        
        logger.info(f"Resource added: {name} (capacity: {capacity} {unit})")
        
        return resource
    
    async def get_resource(self, name: str) -> Optional[Resource]:
        """Get resource by name."""
        return await self._resource_store.get_by_name(name)
    
    async def list_resources(self) -> List[Resource]:
        """List all resources."""
        return await self._resource_store.list_all()
    
    async def update_capacity(
        self,
        resource_name: str,
        new_capacity: float,
    ) -> Optional[Resource]:
        """Update resource capacity."""
        resource = await self._resource_store.get_by_name(resource_name)
        
        if not resource:
            return None
        
        resource.capacity = max(resource.min_capacity, min(resource.max_capacity, new_capacity))
        await self._resource_store.save(resource)
        
        logger.info(f"Capacity updated: {resource_name} -> {resource.capacity}")
        
        return resource
    
    async def record_usage(
        self,
        resource_name: str,
        usage: float,
        timestamp: Optional[datetime] = None,
        **metadata,
    ) -> Optional[UsageRecord]:
        """Record usage."""
        resource = await self._resource_store.get_by_name(resource_name)
        
        if not resource:
            return None
        
        utilization = (usage / resource.capacity * 100) if resource.capacity > 0 else 0
        
        record = UsageRecord(
            resource_id=resource.id,
            usage=usage,
            utilization=utilization,
            timestamp=timestamp or datetime.utcnow(),
            metadata=metadata,
        )
        
        await self._usage_store.save(record)
        
        # Check thresholds
        await self._check_thresholds(resource, utilization)
        
        return record
    
    async def get_current_usage(
        self,
        resource_name: str,
    ) -> Optional[UsageRecord]:
        """Get current usage."""
        resource = await self._resource_store.get_by_name(resource_name)
        
        if not resource:
            return None
        
        return await self._usage_store.get_latest(resource.id)
    
    async def get_usage_history(
        self,
        resource_name: str,
        days: int = 30,
    ) -> List[UsageRecord]:
        """Get usage history."""
        resource = await self._resource_store.get_by_name(resource_name)
        
        if not resource:
            return []
        
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        return await self._usage_store.list_by_resource(
            resource.id,
            start_date,
            end_date,
        )
    
    async def forecast(
        self,
        resource_name: str,
        days_ahead: int = 30,
        method: ForecastMethod = ForecastMethod.LINEAR,
    ) -> Optional[CapacityForecast]:
        """Forecast capacity."""
        resource = await self._resource_store.get_by_name(resource_name)
        
        if not resource:
            return None
        
        # Get historical data
        history = await self.get_usage_history(resource_name, days=90)
        
        if not history:
            return CapacityForecast(
                resource_id=resource.id,
                resource_name=resource.name,
                current_capacity=resource.capacity,
            )
        
        current = history[-1]
        data_points = [(r.timestamp, r.usage) for r in history]
        
        target_date = datetime.utcnow() + timedelta(days=days_ahead)
        
        # Forecast
        if method == ForecastMethod.LINEAR:
            predicted, confidence = Forecaster.linear_forecast(data_points, target_date)
        elif method == ForecastMethod.MOVING_AVERAGE:
            predicted, confidence = Forecaster.moving_average_forecast(data_points)
        else:
            predicted, confidence = Forecaster.exponential_forecast(data_points)
        
        predicted_util = (predicted / resource.capacity * 100) if resource.capacity > 0 else 0
        
        # Calculate days until thresholds
        growth_rate = self._calculate_growth_rate(history)
        
        days_until_warning = self._days_until_threshold(
            current.usage,
            growth_rate,
            resource.capacity * resource.warning_threshold / 100,
        )
        
        days_until_critical = self._days_until_threshold(
            current.usage,
            growth_rate,
            resource.capacity * resource.critical_threshold / 100,
        )
        
        days_until_full = self._days_until_threshold(
            current.usage,
            growth_rate,
            resource.capacity,
        )
        
        # Scaling recommendation
        scaling_direction = ScalingDirection.NONE
        recommended_capacity = resource.capacity
        
        if predicted_util > resource.critical_threshold:
            scaling_direction = ScalingDirection.UP
            # Recommend capacity to bring utilization to 70%
            recommended_capacity = (predicted / 70) * 100
        elif predicted_util < 30 and current.utilization < 30:
            scaling_direction = ScalingDirection.DOWN
            recommended_capacity = (predicted / 70) * 100
        
        return CapacityForecast(
            resource_id=resource.id,
            resource_name=resource.name,
            current_usage=current.usage,
            current_capacity=resource.capacity,
            current_utilization=current.utilization,
            predicted_usage=predicted,
            predicted_utilization=predicted_util,
            forecast_date=target_date,
            days_until_warning=days_until_warning,
            days_until_critical=days_until_critical,
            days_until_full=days_until_full,
            scaling_direction=scaling_direction,
            recommended_capacity=recommended_capacity,
            confidence=confidence,
            method=method,
        )
    
    async def get_scaling_recommendations(self) -> List[ScalingRecommendation]:
        """Get scaling recommendations."""
        resources = await self._resource_store.list_all()
        recommendations = []
        
        for resource in resources:
            forecast = await self.forecast(resource.name, days_ahead=30)
            
            if forecast and forecast.scaling_direction != ScalingDirection.NONE:
                urgency = AlertLevel.INFO
                
                if forecast.predicted_utilization > 90:
                    urgency = AlertLevel.CRITICAL
                elif forecast.predicted_utilization > 70:
                    urgency = AlertLevel.WARNING
                
                reason = (
                    f"Predicted {forecast.predicted_utilization:.1f}% utilization "
                    f"in 30 days (current: {forecast.current_utilization:.1f}%)"
                )
                
                recommendations.append(ScalingRecommendation(
                    resource_id=resource.id,
                    resource_name=resource.name,
                    current_capacity=resource.capacity,
                    recommended_capacity=forecast.recommended_capacity,
                    direction=forecast.scaling_direction,
                    urgency=urgency,
                    reason=reason,
                ))
        
        return recommendations
    
    async def get_stats(self) -> CapacityStats:
        """Get capacity statistics."""
        resources = await self._resource_store.list_all()
        
        stats = CapacityStats(total_resources=len(resources))
        
        utilizations = []
        
        for resource in resources:
            latest = await self._usage_store.get_latest(resource.id)
            
            stats.total_capacity += resource.capacity
            
            if latest:
                stats.total_usage += latest.usage
                utilizations.append(latest.utilization)
                
                if latest.utilization >= resource.critical_threshold:
                    stats.critical += 1
                elif latest.utilization >= resource.warning_threshold:
                    stats.warning += 1
                else:
                    stats.healthy += 1
            else:
                stats.healthy += 1
        
        if utilizations:
            stats.avg_utilization = sum(utilizations) / len(utilizations)
        
        return stats
    
    def add_alert_handler(self, handler: Callable) -> None:
        """Add alert handler."""
        self._alert_handlers.append(handler)
    
    def get_alerts(self, include_acknowledged: bool = False) -> List[CapacityAlert]:
        """Get alerts."""
        if include_acknowledged:
            return self._alerts.copy()
        return [a for a in self._alerts if not a.acknowledged]
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge alert."""
        for alert in self._alerts:
            if alert.id == alert_id:
                alert.acknowledged = True
                return True
        return False
    
    def _calculate_growth_rate(self, history: List[UsageRecord]) -> float:
        """Calculate daily growth rate."""
        if len(history) < 2:
            return 0.0
        
        first = history[0]
        last = history[-1]
        
        days = (last.timestamp - first.timestamp).total_seconds() / 86400
        
        if days <= 0:
            return 0.0
        
        if first.usage <= 0:
            return 0.0
        
        return (last.usage - first.usage) / days
    
    def _days_until_threshold(
        self,
        current: float,
        growth_rate: float,
        threshold: float,
    ) -> Optional[int]:
        """Calculate days until threshold."""
        if growth_rate <= 0:
            return None
        
        if current >= threshold:
            return 0
        
        days = (threshold - current) / growth_rate
        return max(0, int(days))
    
    async def _check_thresholds(
        self,
        resource: Resource,
        utilization: float,
    ) -> None:
        """Check thresholds and trigger alerts."""
        level = None
        threshold = 0.0
        
        if utilization >= resource.critical_threshold:
            level = AlertLevel.CRITICAL
            threshold = resource.critical_threshold
        elif utilization >= resource.warning_threshold:
            level = AlertLevel.WARNING
            threshold = resource.warning_threshold
        
        if level:
            alert_key = f"{resource.id}:{level.value}"
            
            if alert_key not in self._triggered_alerts:
                self._triggered_alerts.add(alert_key)
                
                alert = CapacityAlert(
                    resource_id=resource.id,
                    resource_name=resource.name,
                    level=level,
                    utilization=utilization,
                    threshold=threshold,
                    message=f"Resource '{resource.name}' at {utilization:.1f}% "
                            f"(threshold: {threshold}%)",
                )
                
                self._alerts.append(alert)
                await self._notify_alert(alert)
        else:
            # Clear alerts
            to_remove = [k for k in self._triggered_alerts if k.startswith(f"{resource.id}:")]
            for k in to_remove:
                self._triggered_alerts.discard(k)
    
    async def _notify_alert(self, alert: CapacityAlert) -> None:
        """Notify alert handlers."""
        log_level = logging.ERROR if alert.level == AlertLevel.CRITICAL else logging.WARNING
        logger.log(log_level, f"Capacity alert: {alert.message}")
        
        for handler in self._alert_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(alert)
                else:
                    handler(alert)
            except Exception as e:
                logger.error(f"Alert handler error: {e}")


# Factory functions
def create_capacity_planner() -> CapacityPlanner:
    """Create capacity planner."""
    return CapacityPlanner()


def create_resource(name: str, capacity: float, **kwargs) -> Resource:
    """Create resource."""
    return Resource(name=name, capacity=capacity, **kwargs)


__all__ = [
    # Exceptions
    "CapacityError",
    # Enums
    "ResourceType",
    "ScalingDirection",
    "AlertLevel",
    "ForecastMethod",
    # Data classes
    "Resource",
    "UsageRecord",
    "CapacityForecast",
    "ScalingRecommendation",
    "CapacityAlert",
    "CapacityStats",
    # Stores
    "ResourceStore",
    "InMemoryResourceStore",
    "UsageStore",
    "InMemoryUsageStore",
    # Utilities
    "Forecaster",
    # Manager
    "CapacityPlanner",
    # Factory functions
    "create_capacity_planner",
    "create_resource",
]
