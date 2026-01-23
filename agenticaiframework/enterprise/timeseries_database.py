"""
Enterprise Time Series Database Module.

Time series storage, aggregation, downsampling,
and analytics for metrics and IoT data.

Example:
    # Create time series database
    tsdb = create_timeseries_database()
    
    # Write data points
    await tsdb.write(
        metric="cpu_usage",
        value=75.5,
        tags={"host": "server1"},
    )
    
    # Query time range
    results = await tsdb.query(
        metric="cpu_usage",
        start=datetime.now() - timedelta(hours=1),
        end=datetime.now(),
        aggregation="avg",
        interval="5m",
    )
    
    # Downsampling
    await tsdb.downsample(
        metric="cpu_usage",
        from_interval="1m",
        to_interval="1h",
        aggregation="avg",
    )
"""

from __future__ import annotations

import asyncio
import bisect
import functools
import logging
import statistics
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
    Iterator,
    List,
    Optional,
    Set,
    Tuple,
    TypeVar,
    Union,
)

T = TypeVar('T')


logger = logging.getLogger(__name__)


class TimeSeriesError(Exception):
    """Time series error."""
    pass


class MetricNotFoundError(TimeSeriesError):
    """Metric not found."""
    pass


class Aggregation(str, Enum):
    """Aggregation functions."""
    AVG = "avg"
    SUM = "sum"
    MIN = "min"
    MAX = "max"
    COUNT = "count"
    FIRST = "first"
    LAST = "last"
    MEDIAN = "median"
    STDDEV = "stddev"
    PERCENTILE_50 = "p50"
    PERCENTILE_90 = "p90"
    PERCENTILE_95 = "p95"
    PERCENTILE_99 = "p99"


class RetentionPolicy(str, Enum):
    """Retention policies."""
    RAW = "raw"
    HOUR = "1h"
    DAY = "1d"
    WEEK = "1w"
    MONTH = "1mo"
    YEAR = "1y"


@dataclass
class DataPoint:
    """Single data point."""
    timestamp: datetime
    value: float
    tags: Dict[str, str] = field(default_factory=dict)
    
    def __lt__(self, other: "DataPoint") -> bool:
        return self.timestamp < other.timestamp


@dataclass
class Series:
    """Time series."""
    metric: str
    tags: Dict[str, str] = field(default_factory=dict)
    points: List[DataPoint] = field(default_factory=list)
    
    @property
    def key(self) -> str:
        """Get series key."""
        tag_str = ",".join(f"{k}={v}" for k, v in sorted(self.tags.items()))
        return f"{self.metric}{{{tag_str}}}" if tag_str else self.metric


@dataclass
class QueryResult:
    """Query result."""
    series: List[Series] = field(default_factory=list)
    execution_time_ms: float = 0.0
    
    def __iter__(self) -> Iterator[Series]:
        return iter(self.series)
    
    def __len__(self) -> int:
        return len(self.series)


@dataclass
class AggregatedPoint:
    """Aggregated data point."""
    timestamp: datetime
    value: float
    count: int = 1
    min_value: float = 0.0
    max_value: float = 0.0
    sum_value: float = 0.0


@dataclass
class MetricMetadata:
    """Metric metadata."""
    name: str
    description: str = ""
    unit: str = ""
    type: str = "gauge"  # gauge, counter, histogram
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class RetentionConfig:
    """Retention configuration."""
    raw_retention: timedelta = field(default_factory=lambda: timedelta(days=7))
    aggregation_intervals: List[Tuple[str, timedelta]] = field(
        default_factory=lambda: [
            ("1h", timedelta(days=30)),
            ("1d", timedelta(days=365)),
        ]
    )


@dataclass
class TimeSeriesStats:
    """Time series statistics."""
    total_metrics: int = 0
    total_series: int = 0
    total_points: int = 0
    oldest_point: Optional[datetime] = None
    newest_point: Optional[datetime] = None
    storage_bytes: int = 0


# Time series backend
class TimeSeriesBackend(ABC):
    """Abstract time series backend."""
    
    @abstractmethod
    async def write(
        self,
        metric: str,
        value: float,
        timestamp: datetime,
        tags: Dict[str, str],
    ) -> None:
        """Write data point."""
        pass
    
    @abstractmethod
    async def write_batch(
        self,
        points: List[Tuple[str, float, datetime, Dict[str, str]]],
    ) -> int:
        """Write batch of points."""
        pass
    
    @abstractmethod
    async def query(
        self,
        metric: str,
        start: datetime,
        end: datetime,
        tags: Optional[Dict[str, str]],
    ) -> List[DataPoint]:
        """Query data points."""
        pass
    
    @abstractmethod
    async def aggregate(
        self,
        metric: str,
        start: datetime,
        end: datetime,
        aggregation: Aggregation,
        interval: timedelta,
        tags: Optional[Dict[str, str]],
    ) -> List[AggregatedPoint]:
        """Aggregate data points."""
        pass
    
    @abstractmethod
    async def get_metrics(self) -> List[str]:
        """Get all metric names."""
        pass
    
    @abstractmethod
    async def get_stats(self) -> TimeSeriesStats:
        """Get statistics."""
        pass


class InMemoryTimeSeriesBackend(TimeSeriesBackend):
    """In-memory time series backend."""
    
    def __init__(self, max_points_per_series: int = 100000):
        self._data: Dict[str, Dict[str, List[DataPoint]]] = defaultdict(
            lambda: defaultdict(list)
        )
        self._metadata: Dict[str, MetricMetadata] = {}
        self._max_points = max_points_per_series
    
    def _get_series_key(self, tags: Dict[str, str]) -> str:
        """Get series key from tags."""
        return ",".join(f"{k}={v}" for k, v in sorted(tags.items())) or "_"
    
    async def write(
        self,
        metric: str,
        value: float,
        timestamp: datetime,
        tags: Dict[str, str],
    ) -> None:
        series_key = self._get_series_key(tags)
        points = self._data[metric][series_key]
        
        point = DataPoint(timestamp=timestamp, value=value, tags=tags)
        
        # Insert in sorted order
        bisect.insort(points, point)
        
        # Trim if needed
        if len(points) > self._max_points:
            self._data[metric][series_key] = points[-self._max_points:]
    
    async def write_batch(
        self,
        points: List[Tuple[str, float, datetime, Dict[str, str]]],
    ) -> int:
        count = 0
        for metric, value, timestamp, tags in points:
            await self.write(metric, value, timestamp, tags)
            count += 1
        return count
    
    async def query(
        self,
        metric: str,
        start: datetime,
        end: datetime,
        tags: Optional[Dict[str, str]],
    ) -> List[DataPoint]:
        results = []
        
        if metric not in self._data:
            return results
        
        for series_key, points in self._data[metric].items():
            for point in points:
                if start <= point.timestamp <= end:
                    if tags is None or all(
                        point.tags.get(k) == v for k, v in tags.items()
                    ):
                        results.append(point)
        
        return sorted(results, key=lambda p: p.timestamp)
    
    async def aggregate(
        self,
        metric: str,
        start: datetime,
        end: datetime,
        aggregation: Aggregation,
        interval: timedelta,
        tags: Optional[Dict[str, str]],
    ) -> List[AggregatedPoint]:
        points = await self.query(metric, start, end, tags)
        
        if not points:
            return []
        
        # Group by interval
        buckets: Dict[datetime, List[float]] = defaultdict(list)
        
        for point in points:
            # Round down to interval
            bucket_time = datetime.fromtimestamp(
                (point.timestamp.timestamp() // interval.total_seconds())
                * interval.total_seconds()
            )
            buckets[bucket_time].append(point.value)
        
        # Aggregate each bucket
        results = []
        
        for bucket_time, values in sorted(buckets.items()):
            agg_value = self._aggregate_values(values, aggregation)
            
            results.append(AggregatedPoint(
                timestamp=bucket_time,
                value=agg_value,
                count=len(values),
                min_value=min(values),
                max_value=max(values),
                sum_value=sum(values),
            ))
        
        return results
    
    def _aggregate_values(
        self,
        values: List[float],
        aggregation: Aggregation,
    ) -> float:
        """Apply aggregation to values."""
        if not values:
            return 0.0
        
        if aggregation == Aggregation.AVG:
            return statistics.mean(values)
        elif aggregation == Aggregation.SUM:
            return sum(values)
        elif aggregation == Aggregation.MIN:
            return min(values)
        elif aggregation == Aggregation.MAX:
            return max(values)
        elif aggregation == Aggregation.COUNT:
            return float(len(values))
        elif aggregation == Aggregation.FIRST:
            return values[0]
        elif aggregation == Aggregation.LAST:
            return values[-1]
        elif aggregation == Aggregation.MEDIAN:
            return statistics.median(values)
        elif aggregation == Aggregation.STDDEV:
            return statistics.stdev(values) if len(values) > 1 else 0.0
        elif aggregation == Aggregation.PERCENTILE_50:
            return self._percentile(values, 50)
        elif aggregation == Aggregation.PERCENTILE_90:
            return self._percentile(values, 90)
        elif aggregation == Aggregation.PERCENTILE_95:
            return self._percentile(values, 95)
        elif aggregation == Aggregation.PERCENTILE_99:
            return self._percentile(values, 99)
        
        return 0.0
    
    def _percentile(self, values: List[float], p: int) -> float:
        """Calculate percentile."""
        sorted_values = sorted(values)
        k = (len(sorted_values) - 1) * p / 100
        f = int(k)
        c = f + 1 if f < len(sorted_values) - 1 else f
        
        return sorted_values[f] + (k - f) * (sorted_values[c] - sorted_values[f])
    
    async def get_metrics(self) -> List[str]:
        return list(self._data.keys())
    
    async def get_stats(self) -> TimeSeriesStats:
        total_points = 0
        oldest = None
        newest = None
        
        for metric_data in self._data.values():
            for points in metric_data.values():
                total_points += len(points)
                
                if points:
                    if oldest is None or points[0].timestamp < oldest:
                        oldest = points[0].timestamp
                    if newest is None or points[-1].timestamp > newest:
                        newest = points[-1].timestamp
        
        return TimeSeriesStats(
            total_metrics=len(self._data),
            total_series=sum(
                len(series) for series in self._data.values()
            ),
            total_points=total_points,
            oldest_point=oldest,
            newest_point=newest,
            storage_bytes=total_points * 24,  # Estimate
        )
    
    async def delete_before(self, metric: str, before: datetime) -> int:
        """Delete points before timestamp."""
        deleted = 0
        
        if metric in self._data:
            for series_key, points in self._data[metric].items():
                original_count = len(points)
                self._data[metric][series_key] = [
                    p for p in points if p.timestamp >= before
                ]
                deleted += original_count - len(self._data[metric][series_key])
        
        return deleted


# Time series database
class TimeSeriesDatabase:
    """
    Time series database service.
    """
    
    def __init__(
        self,
        backend: Optional[TimeSeriesBackend] = None,
        retention: Optional[RetentionConfig] = None,
    ):
        self._backend = backend or InMemoryTimeSeriesBackend()
        self._retention = retention or RetentionConfig()
        self._metadata: Dict[str, MetricMetadata] = {}
    
    async def write(
        self,
        metric: str,
        value: float,
        timestamp: Optional[datetime] = None,
        **tags,
    ) -> None:
        """
        Write a data point.
        
        Args:
            metric: Metric name
            value: Value
            timestamp: Timestamp (default: now)
            **tags: Tags
        """
        ts = timestamp or datetime.utcnow()
        await self._backend.write(metric, value, ts, tags)
    
    async def write_batch(
        self,
        metric: str,
        points: List[Tuple[datetime, float]],
        **tags,
    ) -> int:
        """
        Write batch of points.
        
        Args:
            metric: Metric name
            points: List of (timestamp, value) tuples
            **tags: Tags for all points
            
        Returns:
            Number of points written
        """
        batch = [(metric, value, ts, tags) for ts, value in points]
        return await self._backend.write_batch(batch)
    
    async def query(
        self,
        metric: str,
        start: datetime,
        end: Optional[datetime] = None,
        aggregation: Optional[Aggregation] = None,
        interval: Optional[str] = None,
        **tags,
    ) -> QueryResult:
        """
        Query time series data.
        
        Args:
            metric: Metric name
            start: Start time
            end: End time (default: now)
            aggregation: Aggregation function
            interval: Aggregation interval (e.g., "5m", "1h")
            **tags: Tag filters
            
        Returns:
            Query result
        """
        import time
        start_time = time.perf_counter()
        
        end_time = end or datetime.utcnow()
        tag_filter = tags if tags else None
        
        if aggregation and interval:
            interval_td = self._parse_interval(interval)
            agg_points = await self._backend.aggregate(
                metric, start, end_time, aggregation, interval_td, tag_filter
            )
            
            series = Series(
                metric=metric,
                tags=tags,
                points=[
                    DataPoint(timestamp=ap.timestamp, value=ap.value)
                    for ap in agg_points
                ],
            )
            result_series = [series]
        else:
            points = await self._backend.query(metric, start, end_time, tag_filter)
            
            # Group by tags
            series_map: Dict[str, Series] = {}
            
            for point in points:
                key = ",".join(f"{k}={v}" for k, v in sorted(point.tags.items()))
                
                if key not in series_map:
                    series_map[key] = Series(metric=metric, tags=point.tags)
                
                series_map[key].points.append(point)
            
            result_series = list(series_map.values())
        
        return QueryResult(
            series=result_series,
            execution_time_ms=(time.perf_counter() - start_time) * 1000,
        )
    
    def _parse_interval(self, interval: str) -> timedelta:
        """Parse interval string."""
        unit = interval[-1]
        value = int(interval[:-1])
        
        if unit == "s":
            return timedelta(seconds=value)
        elif unit == "m":
            return timedelta(minutes=value)
        elif unit == "h":
            return timedelta(hours=value)
        elif unit == "d":
            return timedelta(days=value)
        elif unit == "w":
            return timedelta(weeks=value)
        
        raise ValueError(f"Invalid interval: {interval}")
    
    async def downsample(
        self,
        metric: str,
        from_interval: str,
        to_interval: str,
        aggregation: Aggregation = Aggregation.AVG,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> int:
        """
        Downsample data.
        
        Args:
            metric: Metric name
            from_interval: Source interval
            to_interval: Target interval
            aggregation: Aggregation function
            start: Start time
            end: End time
            
        Returns:
            Number of points created
        """
        end_time = end or datetime.utcnow()
        start_time = start or (end_time - timedelta(days=30))
        
        to_interval_td = self._parse_interval(to_interval)
        
        agg_points = await self._backend.aggregate(
            metric, start_time, end_time, aggregation, to_interval_td, None
        )
        
        # Write aggregated points with different metric name
        downsampled_metric = f"{metric}:{to_interval}"
        
        count = 0
        for point in agg_points:
            await self._backend.write(
                downsampled_metric,
                point.value,
                point.timestamp,
                {},
            )
            count += 1
        
        return count
    
    async def get_metrics(self) -> List[str]:
        """Get all metric names."""
        return await self._backend.get_metrics()
    
    async def get_stats(self) -> TimeSeriesStats:
        """Get database statistics."""
        return await self._backend.get_stats()
    
    async def register_metric(
        self,
        name: str,
        description: str = "",
        unit: str = "",
        metric_type: str = "gauge",
        tags: Optional[List[str]] = None,
    ) -> MetricMetadata:
        """
        Register metric metadata.
        
        Args:
            name: Metric name
            description: Description
            unit: Unit of measurement
            metric_type: Type (gauge, counter, histogram)
            tags: Expected tag keys
            
        Returns:
            Metric metadata
        """
        metadata = MetricMetadata(
            name=name,
            description=description,
            unit=unit,
            type=metric_type,
            tags=tags or [],
        )
        
        self._metadata[name] = metadata
        return metadata
    
    async def get_metric_metadata(
        self,
        name: str,
    ) -> Optional[MetricMetadata]:
        """Get metric metadata."""
        return self._metadata.get(name)
    
    async def apply_retention(self) -> Dict[str, int]:
        """
        Apply retention policy.
        
        Returns:
            Dict of metric -> deleted points count
        """
        if not isinstance(self._backend, InMemoryTimeSeriesBackend):
            return {}
        
        deleted: Dict[str, int] = {}
        cutoff = datetime.utcnow() - self._retention.raw_retention
        
        for metric in await self._backend.get_metrics():
            count = await self._backend.delete_before(metric, cutoff)
            if count > 0:
                deleted[metric] = count
        
        return deleted


# Helper classes
class MetricRecorder:
    """
    Helper for recording metrics.
    
    Example:
        recorder = MetricRecorder(tsdb, "api_requests")
        recorder.increment()
        recorder.record(1.5)
    """
    
    def __init__(
        self,
        tsdb: TimeSeriesDatabase,
        metric: str,
        **default_tags,
    ):
        self._tsdb = tsdb
        self._metric = metric
        self._default_tags = default_tags
        self._value = 0.0
    
    async def record(self, value: float, **extra_tags) -> None:
        """Record value."""
        tags = {**self._default_tags, **extra_tags}
        await self._tsdb.write(self._metric, value, **tags)
    
    async def increment(self, delta: float = 1.0, **extra_tags) -> None:
        """Increment counter."""
        self._value += delta
        await self.record(self._value, **extra_tags)
    
    async def gauge(self, value: float, **extra_tags) -> None:
        """Set gauge value."""
        self._value = value
        await self.record(value, **extra_tags)


# Decorators
def record_timing(
    tsdb: TimeSeriesDatabase,
    metric: str,
    **tags,
):
    """
    Decorator to record function timing.
    
    Args:
        tsdb: Time series database
        metric: Metric name
        **tags: Tags
    """
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            import time
            start = time.perf_counter()
            try:
                return await func(*args, **kwargs)
            finally:
                duration = (time.perf_counter() - start) * 1000
                await tsdb.write(metric, duration, **tags)
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            import time
            start = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                duration = (time.perf_counter() - start) * 1000
                asyncio.create_task(tsdb.write(metric, duration, **tags))
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


# Factory functions
def create_timeseries_database(
    backend: Optional[TimeSeriesBackend] = None,
    retention: Optional[RetentionConfig] = None,
) -> TimeSeriesDatabase:
    """Create time series database."""
    return TimeSeriesDatabase(backend=backend, retention=retention)


def create_in_memory_backend(
    max_points: int = 100000,
) -> InMemoryTimeSeriesBackend:
    """Create in-memory backend."""
    return InMemoryTimeSeriesBackend(max_points_per_series=max_points)


def create_metric_recorder(
    tsdb: TimeSeriesDatabase,
    metric: str,
    **tags,
) -> MetricRecorder:
    """Create metric recorder."""
    return MetricRecorder(tsdb, metric, **tags)


__all__ = [
    # Exceptions
    "TimeSeriesError",
    "MetricNotFoundError",
    # Enums
    "Aggregation",
    "RetentionPolicy",
    # Data classes
    "DataPoint",
    "Series",
    "QueryResult",
    "AggregatedPoint",
    "MetricMetadata",
    "RetentionConfig",
    "TimeSeriesStats",
    # Backend
    "TimeSeriesBackend",
    "InMemoryTimeSeriesBackend",
    # Main class
    "TimeSeriesDatabase",
    # Helpers
    "MetricRecorder",
    # Decorators
    "record_timing",
    # Factory functions
    "create_timeseries_database",
    "create_in_memory_backend",
    "create_metric_recorder",
]
