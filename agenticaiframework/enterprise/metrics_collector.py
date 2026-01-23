"""
Enterprise Metrics Collector Module.

Provides metrics collection, counters, gauges, histograms,
timers, and metric exporters.

Example:
    # Create metrics collector
    metrics = create_metrics_collector()
    
    # Record metrics
    metrics.counter("requests_total").inc()
    metrics.gauge("active_connections").set(42)
    metrics.histogram("response_time").observe(0.125)
    
    # Use decorator
    @timed("process_duration")
    async def process_data(data):
        return transform(data)
"""

from __future__ import annotations

import asyncio
import functools
import statistics
import threading
import time
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


class MetricType(str, Enum):
    """Metric type."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"
    TIMER = "timer"


@dataclass
class MetricLabels:
    """Metric labels."""
    labels: Dict[str, str] = field(default_factory=dict)
    
    def __hash__(self) -> int:
        return hash(tuple(sorted(self.labels.items())))
    
    def __eq__(self, other: object) -> bool:
        if isinstance(other, MetricLabels):
            return self.labels == other.labels
        return False
    
    def key(self) -> str:
        return ",".join(f"{k}={v}" for k, v in sorted(self.labels.items()))


@dataclass
class MetricValue:
    """Metric value with timestamp."""
    value: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    labels: MetricLabels = field(default_factory=MetricLabels)


@dataclass
class MetricInfo:
    """Metric information."""
    name: str
    type: MetricType
    description: str = ""
    unit: str = ""
    labels: List[str] = field(default_factory=list)


@dataclass
class HistogramBuckets:
    """Histogram bucket configuration."""
    boundaries: List[float] = field(default_factory=lambda: [
        0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0
    ])


@dataclass
class SummaryQuantiles:
    """Summary quantile configuration."""
    quantiles: List[float] = field(default_factory=lambda: [0.5, 0.9, 0.95, 0.99])
    max_age: timedelta = field(default_factory=lambda: timedelta(minutes=10))


class Metric(ABC):
    """Abstract metric."""
    
    def __init__(
        self,
        name: str,
        description: str = "",
        labels: Optional[List[str]] = None,
    ):
        self._name = name
        self._description = description
        self._label_names = labels or []
        self._lock = threading.Lock()
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def description(self) -> str:
        return self._description
    
    @property
    @abstractmethod
    def type(self) -> MetricType:
        """Metric type."""
        pass
    
    @abstractmethod
    def collect(self) -> List[MetricValue]:
        """Collect metric values."""
        pass


class Counter(Metric):
    """
    Counter metric (monotonically increasing).
    """
    
    def __init__(
        self,
        name: str,
        description: str = "",
        labels: Optional[List[str]] = None,
    ):
        super().__init__(name, description, labels)
        self._values: Dict[MetricLabels, float] = defaultdict(float)
    
    @property
    def type(self) -> MetricType:
        return MetricType.COUNTER
    
    def inc(self, value: float = 1.0, **labels) -> None:
        """Increment counter."""
        if value < 0:
            raise ValueError("Counter can only be incremented")
        
        label_key = MetricLabels(labels)
        with self._lock:
            self._values[label_key] += value
    
    def get(self, **labels) -> float:
        """Get counter value."""
        label_key = MetricLabels(labels)
        return self._values.get(label_key, 0.0)
    
    def labels(self, **labels) -> "LabeledCounter":
        """Create labeled counter."""
        return LabeledCounter(self, labels)
    
    def collect(self) -> List[MetricValue]:
        with self._lock:
            return [
                MetricValue(value=v, labels=k)
                for k, v in self._values.items()
            ]


class LabeledCounter:
    """Counter with pre-set labels."""
    
    def __init__(self, counter: Counter, labels: Dict[str, str]):
        self._counter = counter
        self._labels = labels
    
    def inc(self, value: float = 1.0) -> None:
        self._counter.inc(value, **self._labels)
    
    def get(self) -> float:
        return self._counter.get(**self._labels)


class Gauge(Metric):
    """
    Gauge metric (can go up and down).
    """
    
    def __init__(
        self,
        name: str,
        description: str = "",
        labels: Optional[List[str]] = None,
    ):
        super().__init__(name, description, labels)
        self._values: Dict[MetricLabels, float] = defaultdict(float)
    
    @property
    def type(self) -> MetricType:
        return MetricType.GAUGE
    
    def set(self, value: float, **labels) -> None:
        """Set gauge value."""
        label_key = MetricLabels(labels)
        with self._lock:
            self._values[label_key] = value
    
    def inc(self, value: float = 1.0, **labels) -> None:
        """Increment gauge."""
        label_key = MetricLabels(labels)
        with self._lock:
            self._values[label_key] += value
    
    def dec(self, value: float = 1.0, **labels) -> None:
        """Decrement gauge."""
        label_key = MetricLabels(labels)
        with self._lock:
            self._values[label_key] -= value
    
    def get(self, **labels) -> float:
        """Get gauge value."""
        label_key = MetricLabels(labels)
        return self._values.get(label_key, 0.0)
    
    def labels(self, **labels) -> "LabeledGauge":
        """Create labeled gauge."""
        return LabeledGauge(self, labels)
    
    def collect(self) -> List[MetricValue]:
        with self._lock:
            return [
                MetricValue(value=v, labels=k)
                for k, v in self._values.items()
            ]


class LabeledGauge:
    """Gauge with pre-set labels."""
    
    def __init__(self, gauge: Gauge, labels: Dict[str, str]):
        self._gauge = gauge
        self._labels = labels
    
    def set(self, value: float) -> None:
        self._gauge.set(value, **self._labels)
    
    def inc(self, value: float = 1.0) -> None:
        self._gauge.inc(value, **self._labels)
    
    def dec(self, value: float = 1.0) -> None:
        self._gauge.dec(value, **self._labels)
    
    def get(self) -> float:
        return self._gauge.get(**self._labels)


class Histogram(Metric):
    """
    Histogram metric (distribution of values).
    """
    
    def __init__(
        self,
        name: str,
        description: str = "",
        labels: Optional[List[str]] = None,
        buckets: Optional[HistogramBuckets] = None,
    ):
        super().__init__(name, description, labels)
        self._buckets = (buckets or HistogramBuckets()).boundaries
        self._bucket_counts: Dict[MetricLabels, Dict[float, int]] = defaultdict(
            lambda: {b: 0 for b in self._buckets}
        )
        self._sums: Dict[MetricLabels, float] = defaultdict(float)
        self._counts: Dict[MetricLabels, int] = defaultdict(int)
    
    @property
    def type(self) -> MetricType:
        return MetricType.HISTOGRAM
    
    def observe(self, value: float, **labels) -> None:
        """Observe a value."""
        label_key = MetricLabels(labels)
        with self._lock:
            self._sums[label_key] += value
            self._counts[label_key] += 1
            
            for bucket in self._buckets:
                if value <= bucket:
                    self._bucket_counts[label_key][bucket] += 1
    
    def get_count(self, **labels) -> int:
        """Get observation count."""
        label_key = MetricLabels(labels)
        return self._counts.get(label_key, 0)
    
    def get_sum(self, **labels) -> float:
        """Get sum of observations."""
        label_key = MetricLabels(labels)
        return self._sums.get(label_key, 0.0)
    
    def get_bucket_counts(self, **labels) -> Dict[float, int]:
        """Get bucket counts."""
        label_key = MetricLabels(labels)
        return dict(self._bucket_counts.get(label_key, {}))
    
    def labels(self, **labels) -> "LabeledHistogram":
        """Create labeled histogram."""
        return LabeledHistogram(self, labels)
    
    def collect(self) -> List[MetricValue]:
        results = []
        with self._lock:
            for label_key in self._counts.keys():
                # Sum
                results.append(MetricValue(
                    value=self._sums[label_key],
                    labels=MetricLabels({**label_key.labels, "_type": "sum"})
                ))
                # Count
                results.append(MetricValue(
                    value=float(self._counts[label_key]),
                    labels=MetricLabels({**label_key.labels, "_type": "count"})
                ))
                # Buckets
                for bucket, count in self._bucket_counts[label_key].items():
                    results.append(MetricValue(
                        value=float(count),
                        labels=MetricLabels({**label_key.labels, "_type": "bucket", "le": str(bucket)})
                    ))
        return results


class LabeledHistogram:
    """Histogram with pre-set labels."""
    
    def __init__(self, histogram: Histogram, labels: Dict[str, str]):
        self._histogram = histogram
        self._labels = labels
    
    def observe(self, value: float) -> None:
        self._histogram.observe(value, **self._labels)
    
    def time(self) -> "Timer":
        """Create a timer for this histogram."""
        return Timer(lambda v: self.observe(v))


class Summary(Metric):
    """
    Summary metric (streaming quantiles).
    """
    
    def __init__(
        self,
        name: str,
        description: str = "",
        labels: Optional[List[str]] = None,
        quantiles: Optional[SummaryQuantiles] = None,
    ):
        super().__init__(name, description, labels)
        self._quantiles = (quantiles or SummaryQuantiles()).quantiles
        self._max_age = (quantiles or SummaryQuantiles()).max_age
        self._observations: Dict[MetricLabels, List[Tuple[datetime, float]]] = defaultdict(list)
    
    @property
    def type(self) -> MetricType:
        return MetricType.SUMMARY
    
    def observe(self, value: float, **labels) -> None:
        """Observe a value."""
        label_key = MetricLabels(labels)
        now = datetime.utcnow()
        
        with self._lock:
            # Add observation
            self._observations[label_key].append((now, value))
            
            # Clean old observations
            cutoff = now - self._max_age
            self._observations[label_key] = [
                (t, v) for t, v in self._observations[label_key]
                if t >= cutoff
            ]
    
    def get_quantiles(self, **labels) -> Dict[float, float]:
        """Get quantile values."""
        label_key = MetricLabels(labels)
        observations = self._observations.get(label_key, [])
        
        if not observations:
            return {q: 0.0 for q in self._quantiles}
        
        values = sorted([v for _, v in observations])
        result = {}
        
        for q in self._quantiles:
            idx = int(len(values) * q)
            idx = min(idx, len(values) - 1)
            result[q] = values[idx]
        
        return result
    
    def labels(self, **labels) -> "LabeledSummary":
        """Create labeled summary."""
        return LabeledSummary(self, labels)
    
    def collect(self) -> List[MetricValue]:
        results = []
        with self._lock:
            for label_key, observations in self._observations.items():
                if not observations:
                    continue
                
                values = [v for _, v in observations]
                
                # Count
                results.append(MetricValue(
                    value=float(len(values)),
                    labels=MetricLabels({**label_key.labels, "_type": "count"})
                ))
                
                # Sum
                results.append(MetricValue(
                    value=sum(values),
                    labels=MetricLabels({**label_key.labels, "_type": "sum"})
                ))
                
                # Quantiles
                sorted_values = sorted(values)
                for q in self._quantiles:
                    idx = int(len(sorted_values) * q)
                    idx = min(idx, len(sorted_values) - 1)
                    results.append(MetricValue(
                        value=sorted_values[idx],
                        labels=MetricLabels({**label_key.labels, "_type": "quantile", "quantile": str(q)})
                    ))
        
        return results


class LabeledSummary:
    """Summary with pre-set labels."""
    
    def __init__(self, summary: Summary, labels: Dict[str, str]):
        self._summary = summary
        self._labels = labels
    
    def observe(self, value: float) -> None:
        self._summary.observe(value, **self._labels)


class Timer:
    """
    Timer for measuring durations.
    """
    
    def __init__(self, callback: Callable[[float], None]):
        self._callback = callback
        self._start: Optional[float] = None
    
    def __enter__(self) -> "Timer":
        self._start = time.perf_counter()
        return self
    
    def __exit__(self, *args) -> None:
        if self._start is not None:
            duration = time.perf_counter() - self._start
            self._callback(duration)


class MetricExporter(ABC):
    """Abstract metric exporter."""
    
    @abstractmethod
    def export(self, metrics: List[Metric]) -> str:
        """Export metrics."""
        pass


class PrometheusExporter(MetricExporter):
    """Prometheus format exporter."""
    
    def export(self, metrics: List[Metric]) -> str:
        lines = []
        
        for metric in metrics:
            # Type and help
            lines.append(f"# HELP {metric.name} {metric.description}")
            lines.append(f"# TYPE {metric.name} {metric.type.value}")
            
            # Values
            for value in metric.collect():
                label_str = ""
                if value.labels.labels:
                    label_pairs = ",".join(
                        f'{k}="{v}"' for k, v in value.labels.labels.items()
                        if not k.startswith("_")
                    )
                    if label_pairs:
                        label_str = f"{{{label_pairs}}}"
                
                lines.append(f"{metric.name}{label_str} {value.value}")
            
            lines.append("")
        
        return "\n".join(lines)


class JsonExporter(MetricExporter):
    """JSON format exporter."""
    
    def export(self, metrics: List[Metric]) -> str:
        import json
        
        data = []
        for metric in metrics:
            metric_data = {
                "name": metric.name,
                "type": metric.type.value,
                "description": metric.description,
                "values": [
                    {
                        "value": v.value,
                        "timestamp": v.timestamp.isoformat(),
                        "labels": v.labels.labels,
                    }
                    for v in metric.collect()
                ]
            }
            data.append(metric_data)
        
        return json.dumps(data, indent=2)


class MetricsCollector:
    """
    Metrics collector and registry.
    """
    
    def __init__(self):
        self._metrics: Dict[str, Metric] = {}
        self._lock = threading.Lock()
    
    def counter(
        self,
        name: str,
        description: str = "",
        labels: Optional[List[str]] = None,
    ) -> Counter:
        """Get or create counter."""
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = Counter(name, description, labels)
            return self._metrics[name]  # type: ignore
    
    def gauge(
        self,
        name: str,
        description: str = "",
        labels: Optional[List[str]] = None,
    ) -> Gauge:
        """Get or create gauge."""
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = Gauge(name, description, labels)
            return self._metrics[name]  # type: ignore
    
    def histogram(
        self,
        name: str,
        description: str = "",
        labels: Optional[List[str]] = None,
        buckets: Optional[HistogramBuckets] = None,
    ) -> Histogram:
        """Get or create histogram."""
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = Histogram(name, description, labels, buckets)
            return self._metrics[name]  # type: ignore
    
    def summary(
        self,
        name: str,
        description: str = "",
        labels: Optional[List[str]] = None,
        quantiles: Optional[SummaryQuantiles] = None,
    ) -> Summary:
        """Get or create summary."""
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = Summary(name, description, labels, quantiles)
            return self._metrics[name]  # type: ignore
    
    def get_all(self) -> List[Metric]:
        """Get all metrics."""
        with self._lock:
            return list(self._metrics.values())
    
    def export(self, exporter: MetricExporter) -> str:
        """Export all metrics."""
        return exporter.export(self.get_all())
    
    def clear(self) -> None:
        """Clear all metrics."""
        with self._lock:
            self._metrics.clear()


# Global collector
_global_collector: Optional[MetricsCollector] = None


# Decorators
def counted(
    name: str,
    description: str = "",
    labels: Optional[Dict[str, str]] = None,
) -> Callable:
    """
    Decorator to count function calls.
    
    Example:
        @counted("api_calls")
        async def handle_request():
            ...
    """
    def decorator(func: Callable) -> Callable:
        collector = get_global_collector()
        counter = collector.counter(name, description)
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            counter.inc(**(labels or {}))
            return await func(*args, **kwargs)
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            counter.inc(**(labels or {}))
            return func(*args, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


def timed(
    name: str,
    description: str = "",
    labels: Optional[Dict[str, str]] = None,
) -> Callable:
    """
    Decorator to time function execution.
    
    Example:
        @timed("process_duration")
        async def process_data(data):
            ...
    """
    def decorator(func: Callable) -> Callable:
        collector = get_global_collector()
        histogram = collector.histogram(name, description)
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                return await func(*args, **kwargs)
            finally:
                duration = time.perf_counter() - start
                histogram.observe(duration, **(labels or {}))
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                duration = time.perf_counter() - start
                histogram.observe(duration, **(labels or {}))
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


def track_in_progress(
    name: str,
    description: str = "",
    labels: Optional[Dict[str, str]] = None,
) -> Callable:
    """
    Decorator to track in-progress operations.
    
    Example:
        @track_in_progress("active_requests")
        async def handle_request():
            ...
    """
    def decorator(func: Callable) -> Callable:
        collector = get_global_collector()
        gauge = collector.gauge(name, description)
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            gauge.inc(**(labels or {}))
            try:
                return await func(*args, **kwargs)
            finally:
                gauge.dec(**(labels or {}))
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            gauge.inc(**(labels or {}))
            try:
                return func(*args, **kwargs)
            finally:
                gauge.dec(**(labels or {}))
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


# Factory functions
def create_metrics_collector() -> MetricsCollector:
    """Create a metrics collector."""
    return MetricsCollector()


def create_counter(
    name: str,
    description: str = "",
    labels: Optional[List[str]] = None,
) -> Counter:
    """Create a counter."""
    return Counter(name, description, labels)


def create_gauge(
    name: str,
    description: str = "",
    labels: Optional[List[str]] = None,
) -> Gauge:
    """Create a gauge."""
    return Gauge(name, description, labels)


def create_histogram(
    name: str,
    description: str = "",
    labels: Optional[List[str]] = None,
    buckets: Optional[List[float]] = None,
) -> Histogram:
    """Create a histogram."""
    bucket_config = HistogramBuckets(buckets) if buckets else None
    return Histogram(name, description, labels, bucket_config)


def create_prometheus_exporter() -> PrometheusExporter:
    """Create Prometheus exporter."""
    return PrometheusExporter()


def create_json_exporter() -> JsonExporter:
    """Create JSON exporter."""
    return JsonExporter()


def get_global_collector() -> MetricsCollector:
    """Get global metrics collector."""
    global _global_collector
    if _global_collector is None:
        _global_collector = create_metrics_collector()
    return _global_collector


__all__ = [
    # Enums
    "MetricType",
    # Data classes
    "MetricLabels",
    "MetricValue",
    "MetricInfo",
    "HistogramBuckets",
    "SummaryQuantiles",
    # Metrics
    "Metric",
    "Counter",
    "LabeledCounter",
    "Gauge",
    "LabeledGauge",
    "Histogram",
    "LabeledHistogram",
    "Summary",
    "LabeledSummary",
    "Timer",
    # Exporters
    "MetricExporter",
    "PrometheusExporter",
    "JsonExporter",
    # Collector
    "MetricsCollector",
    # Decorators
    "counted",
    "timed",
    "track_in_progress",
    # Factory functions
    "create_metrics_collector",
    "create_counter",
    "create_gauge",
    "create_histogram",
    "create_prometheus_exporter",
    "create_json_exporter",
    "get_global_collector",
]
