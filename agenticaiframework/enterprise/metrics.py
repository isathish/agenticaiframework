"""
Enterprise Metrics Export - Prometheus and StatsD support.

Provides metrics collection and export for monitoring
agent performance and system health.

Features:
- Counter, Gauge, Histogram metrics
- Prometheus format export
- StatsD integration
- Custom metric types
- Aggregation and rollup
"""

import asyncio
import logging
import socket
import threading
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
import uuid

logger = logging.getLogger(__name__)


# =============================================================================
# Metric Types
# =============================================================================

class MetricType(Enum):
    """Type of metric."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class MetricLabel:
    """Label for a metric."""
    name: str
    value: str


@dataclass
class MetricValue:
    """A metric value."""
    value: float
    timestamp: datetime = field(default_factory=datetime.now)
    labels: Dict[str, str] = field(default_factory=dict)


# =============================================================================
# Metric Classes
# =============================================================================

class Metric(ABC):
    """Abstract base for metrics."""
    
    def __init__(
        self,
        name: str,
        description: str = "",
        labels: List[str] = None,
    ):
        self.name = name
        self.description = description
        self.label_names = labels or []
        self._lock = threading.RLock()
    
    @property
    @abstractmethod
    def type(self) -> MetricType:
        pass
    
    @abstractmethod
    def collect(self) -> List[MetricValue]:
        """Collect metric values."""
        pass


class Counter(Metric):
    """
    Counter metric (monotonically increasing).
    
    Usage:
        >>> counter = Counter("requests_total", "Total requests")
        >>> counter.inc()
        >>> counter.inc(5)
    """
    
    def __init__(
        self,
        name: str,
        description: str = "",
        labels: List[str] = None,
    ):
        super().__init__(name, description, labels)
        self._values: Dict[tuple, float] = defaultdict(float)
    
    @property
    def type(self) -> MetricType:
        return MetricType.COUNTER
    
    def inc(self, value: float = 1.0, labels: Dict[str, str] = None):
        """Increment the counter."""
        key = self._label_key(labels)
        with self._lock:
            self._values[key] += value
    
    def _label_key(self, labels: Dict[str, str] = None) -> tuple:
        """Create a key from labels."""
        if not labels:
            return ()
        return tuple(sorted(labels.items()))
    
    def collect(self) -> List[MetricValue]:
        with self._lock:
            return [
                MetricValue(
                    value=value,
                    labels=dict(key),
                )
                for key, value in self._values.items()
            ]


class Gauge(Metric):
    """
    Gauge metric (can go up or down).
    
    Usage:
        >>> gauge = Gauge("temperature", "Current temperature")
        >>> gauge.set(72.5)
        >>> gauge.inc(1)
        >>> gauge.dec(0.5)
    """
    
    def __init__(
        self,
        name: str,
        description: str = "",
        labels: List[str] = None,
    ):
        super().__init__(name, description, labels)
        self._values: Dict[tuple, float] = {}
    
    @property
    def type(self) -> MetricType:
        return MetricType.GAUGE
    
    def set(self, value: float, labels: Dict[str, str] = None):
        """Set the gauge value."""
        key = self._label_key(labels)
        with self._lock:
            self._values[key] = value
    
    def inc(self, value: float = 1.0, labels: Dict[str, str] = None):
        """Increment the gauge."""
        key = self._label_key(labels)
        with self._lock:
            current = self._values.get(key, 0)
            self._values[key] = current + value
    
    def dec(self, value: float = 1.0, labels: Dict[str, str] = None):
        """Decrement the gauge."""
        self.inc(-value, labels)
    
    def _label_key(self, labels: Dict[str, str] = None) -> tuple:
        if not labels:
            return ()
        return tuple(sorted(labels.items()))
    
    def collect(self) -> List[MetricValue]:
        with self._lock:
            return [
                MetricValue(
                    value=value,
                    labels=dict(key),
                )
                for key, value in self._values.items()
            ]


class Histogram(Metric):
    """
    Histogram metric (distribution of values).
    
    Usage:
        >>> histogram = Histogram(
        ...     "request_duration_seconds",
        ...     "Request duration",
        ...     buckets=[0.1, 0.5, 1.0, 5.0],
        ... )
        >>> histogram.observe(0.35)
    """
    
    DEFAULT_BUCKETS = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
    
    def __init__(
        self,
        name: str,
        description: str = "",
        labels: List[str] = None,
        buckets: List[float] = None,
    ):
        super().__init__(name, description, labels)
        self.buckets = sorted(buckets or self.DEFAULT_BUCKETS)
        
        # Per-label-set buckets, sum, count
        self._bucket_counts: Dict[tuple, Dict[float, int]] = defaultdict(
            lambda: {b: 0 for b in self.buckets + [float("inf")]}
        )
        self._sums: Dict[tuple, float] = defaultdict(float)
        self._counts: Dict[tuple, int] = defaultdict(int)
    
    @property
    def type(self) -> MetricType:
        return MetricType.HISTOGRAM
    
    def observe(self, value: float, labels: Dict[str, str] = None):
        """Observe a value."""
        key = self._label_key(labels)
        with self._lock:
            self._sums[key] += value
            self._counts[key] += 1
            
            # Update buckets
            for bucket in self.buckets + [float("inf")]:
                if value <= bucket:
                    self._bucket_counts[key][bucket] += 1
    
    def _label_key(self, labels: Dict[str, str] = None) -> tuple:
        if not labels:
            return ()
        return tuple(sorted(labels.items()))
    
    def collect(self) -> List[MetricValue]:
        results = []
        
        with self._lock:
            for key in set(list(self._sums.keys()) + list(self._counts.keys())):
                labels = dict(key)
                
                # Bucket values (cumulative)
                cumulative = 0
                for bucket in self.buckets:
                    cumulative += self._bucket_counts[key].get(bucket, 0)
                    results.append(MetricValue(
                        value=cumulative,
                        labels={**labels, "le": str(bucket)},
                    ))
                
                # +Inf bucket
                cumulative += self._bucket_counts[key].get(float("inf"), 0)
                results.append(MetricValue(
                    value=cumulative,
                    labels={**labels, "le": "+Inf"},
                ))
                
                # Sum and count
                results.append(MetricValue(
                    value=self._sums[key],
                    labels={**labels, "_type": "sum"},
                ))
                results.append(MetricValue(
                    value=self._counts[key],
                    labels={**labels, "_type": "count"},
                ))
        
        return results


# =============================================================================
# Timer Context Manager
# =============================================================================

class Timer:
    """
    Timer for measuring durations.
    
    Usage:
        >>> histogram = Histogram("duration_seconds")
        >>> 
        >>> with Timer(histogram):
        ...     # Do work
        ...     pass
    """
    
    def __init__(self, histogram: Histogram, labels: Dict[str, str] = None):
        self.histogram = histogram
        self.labels = labels
        self._start: Optional[float] = None
    
    def __enter__(self) -> "Timer":
        self._start = time.perf_counter()
        return self
    
    def __exit__(self, *args):
        duration = time.perf_counter() - self._start
        self.histogram.observe(duration, self.labels)


# =============================================================================
# Metrics Registry
# =============================================================================

class MetricsRegistry:
    """
    Registry for metrics.
    
    Usage:
        >>> registry = MetricsRegistry()
        >>> 
        >>> counter = registry.counter("requests_total", "Total requests")
        >>> gauge = registry.gauge("active_connections", "Active connections")
    """
    
    def __init__(self, prefix: str = ""):
        self.prefix = prefix
        self._metrics: Dict[str, Metric] = {}
        self._lock = threading.RLock()
    
    def _prefixed_name(self, name: str) -> str:
        if self.prefix:
            return f"{self.prefix}_{name}"
        return name
    
    def counter(
        self,
        name: str,
        description: str = "",
        labels: List[str] = None,
    ) -> Counter:
        """Create or get a counter."""
        full_name = self._prefixed_name(name)
        
        with self._lock:
            if full_name in self._metrics:
                return self._metrics[full_name]
            
            counter = Counter(full_name, description, labels)
            self._metrics[full_name] = counter
            return counter
    
    def gauge(
        self,
        name: str,
        description: str = "",
        labels: List[str] = None,
    ) -> Gauge:
        """Create or get a gauge."""
        full_name = self._prefixed_name(name)
        
        with self._lock:
            if full_name in self._metrics:
                return self._metrics[full_name]
            
            gauge = Gauge(full_name, description, labels)
            self._metrics[full_name] = gauge
            return gauge
    
    def histogram(
        self,
        name: str,
        description: str = "",
        labels: List[str] = None,
        buckets: List[float] = None,
    ) -> Histogram:
        """Create or get a histogram."""
        full_name = self._prefixed_name(name)
        
        with self._lock:
            if full_name in self._metrics:
                return self._metrics[full_name]
            
            histogram = Histogram(full_name, description, labels, buckets)
            self._metrics[full_name] = histogram
            return histogram
    
    def collect(self) -> Dict[str, List[MetricValue]]:
        """Collect all metrics."""
        with self._lock:
            return {
                name: metric.collect()
                for name, metric in self._metrics.items()
            }
    
    def get_metric(self, name: str) -> Optional[Metric]:
        """Get a metric by name."""
        full_name = self._prefixed_name(name)
        return self._metrics.get(full_name)


# =============================================================================
# Exporters
# =============================================================================

class MetricsExporter(ABC):
    """Abstract interface for metrics export."""
    
    @abstractmethod
    def export(self, registry: MetricsRegistry):
        """Export metrics from registry."""
        pass


class PrometheusExporter(MetricsExporter):
    """
    Export metrics in Prometheus format.
    
    Usage:
        >>> exporter = PrometheusExporter()
        >>> text = exporter.format(registry)
        >>> # Serve at /metrics endpoint
    """
    
    def format(self, registry: MetricsRegistry) -> str:
        """Format metrics for Prometheus."""
        lines = []
        
        for name, metric in registry._metrics.items():
            # Add HELP and TYPE
            if metric.description:
                lines.append(f"# HELP {name} {metric.description}")
            lines.append(f"# TYPE {name} {metric.type.value}")
            
            # Add values
            for value in metric.collect():
                label_str = self._format_labels(value.labels)
                
                if metric.type == MetricType.HISTOGRAM:
                    if value.labels.get("_type") == "sum":
                        lines.append(f"{name}_sum{label_str} {value.value}")
                    elif value.labels.get("_type") == "count":
                        lines.append(f"{name}_count{label_str} {value.value}")
                    else:
                        lines.append(f"{name}_bucket{label_str} {value.value}")
                else:
                    lines.append(f"{name}{label_str} {value.value}")
        
        return "\n".join(lines)
    
    def _format_labels(self, labels: Dict[str, str]) -> str:
        """Format labels for Prometheus."""
        # Filter internal labels
        filtered = {k: v for k, v in labels.items() if not k.startswith("_")}
        
        if not filtered:
            return ""
        
        label_pairs = [f'{k}="{v}"' for k, v in filtered.items()]
        return "{" + ",".join(label_pairs) + "}"
    
    def export(self, registry: MetricsRegistry):
        """Export metrics (returns formatted string)."""
        return self.format(registry)


class StatsDExporter(MetricsExporter):
    """
    Export metrics to StatsD.
    
    Usage:
        >>> exporter = StatsDExporter("localhost", 8125)
        >>> exporter.export(registry)
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 8125,
        prefix: str = "",
    ):
        self.host = host
        self.port = port
        self.prefix = prefix
        self._socket: Optional[socket.socket] = None
    
    def _get_socket(self) -> socket.socket:
        if self._socket is None:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        return self._socket
    
    def _send(self, message: str):
        """Send a message to StatsD."""
        try:
            sock = self._get_socket()
            sock.sendto(message.encode(), (self.host, self.port))
        except Exception as e:
            logger.error(f"Failed to send to StatsD: {e}")
    
    def export(self, registry: MetricsRegistry):
        """Export all metrics to StatsD."""
        for name, metric in registry._metrics.items():
            full_name = f"{self.prefix}.{name}" if self.prefix else name
            
            for value in metric.collect():
                metric_name = full_name
                
                # Add labels as tags
                if value.labels:
                    tags = ",".join(f"{k}={v}" for k, v in value.labels.items() if not k.startswith("_"))
                    if tags:
                        metric_name = f"{metric_name},{tags}"
                
                # Format based on type
                if metric.type == MetricType.COUNTER:
                    self._send(f"{metric_name}:{value.value}|c")
                elif metric.type == MetricType.GAUGE:
                    self._send(f"{metric_name}:{value.value}|g")
                elif metric.type == MetricType.HISTOGRAM:
                    # StatsD timing
                    self._send(f"{metric_name}:{value.value}|ms")


# =============================================================================
# Global Registry
# =============================================================================

_global_registry: Optional[MetricsRegistry] = None


def get_metrics_registry(prefix: str = "agenticai") -> MetricsRegistry:
    """Get the global metrics registry."""
    global _global_registry
    
    if _global_registry is None:
        _global_registry = MetricsRegistry(prefix)
    
    return _global_registry


def set_metrics_registry(registry: MetricsRegistry):
    """Set the global metrics registry."""
    global _global_registry
    _global_registry = registry


# =============================================================================
# Pre-defined Agent Metrics
# =============================================================================

class AgentMetrics:
    """
    Pre-defined metrics for agent monitoring.
    
    Usage:
        >>> metrics = AgentMetrics()
        >>> 
        >>> metrics.agent_requests.inc(labels={"agent": "my-agent"})
        >>> metrics.agent_duration.observe(1.5, labels={"agent": "my-agent"})
    """
    
    def __init__(self, registry: MetricsRegistry = None):
        self.registry = registry or get_metrics_registry()
        
        # Request metrics
        self.agent_requests = self.registry.counter(
            "agent_requests_total",
            "Total agent requests",
            labels=["agent", "status"],
        )
        
        self.agent_errors = self.registry.counter(
            "agent_errors_total",
            "Total agent errors",
            labels=["agent", "error_type"],
        )
        
        # Duration metrics
        self.agent_duration = self.registry.histogram(
            "agent_duration_seconds",
            "Agent execution duration",
            labels=["agent"],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
        )
        
        # LLM metrics
        self.llm_requests = self.registry.counter(
            "llm_requests_total",
            "Total LLM requests",
            labels=["model", "agent"],
        )
        
        self.llm_tokens_input = self.registry.counter(
            "llm_tokens_input_total",
            "Total input tokens",
            labels=["model", "agent"],
        )
        
        self.llm_tokens_output = self.registry.counter(
            "llm_tokens_output_total",
            "Total output tokens",
            labels=["model", "agent"],
        )
        
        self.llm_duration = self.registry.histogram(
            "llm_duration_seconds",
            "LLM call duration",
            labels=["model"],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
        )
        
        # Tool metrics
        self.tool_calls = self.registry.counter(
            "tool_calls_total",
            "Total tool calls",
            labels=["tool", "agent"],
        )
        
        self.tool_errors = self.registry.counter(
            "tool_errors_total",
            "Total tool errors",
            labels=["tool", "agent"],
        )
        
        self.tool_duration = self.registry.histogram(
            "tool_duration_seconds",
            "Tool execution duration",
            labels=["tool"],
            buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0],
        )
        
        # Active agents gauge
        self.active_agents = self.registry.gauge(
            "active_agents",
            "Number of active agents",
            labels=["agent"],
        )
    
    def record_request(self, agent: str, status: str = "success"):
        """Record an agent request."""
        self.agent_requests.inc(labels={"agent": agent, "status": status})
    
    def record_error(self, agent: str, error_type: str):
        """Record an agent error."""
        self.agent_errors.inc(labels={"agent": agent, "error_type": error_type})
    
    def time_agent(self, agent: str) -> Timer:
        """Create a timer for agent execution."""
        return Timer(self.agent_duration, {"agent": agent})
    
    def record_llm_call(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        duration: float,
        agent: str = None,
    ):
        """Record an LLM call."""
        labels = {"model": model}
        if agent:
            labels["agent"] = agent
        
        self.llm_requests.inc(labels=labels)
        self.llm_tokens_input.inc(input_tokens, labels=labels)
        self.llm_tokens_output.inc(output_tokens, labels=labels)
        self.llm_duration.observe(duration, {"model": model})
    
    def record_tool_call(self, tool: str, agent: str, duration: float, error: bool = False):
        """Record a tool call."""
        labels = {"tool": tool, "agent": agent}
        
        self.tool_calls.inc(labels=labels)
        self.tool_duration.observe(duration, {"tool": tool})
        
        if error:
            self.tool_errors.inc(labels=labels)


# =============================================================================
# Decorator
# =============================================================================

def with_metrics(metric_name: str = None, labels: Dict[str, str] = None):
    """
    Decorator to add metrics to a function.
    
    Usage:
        >>> @with_metrics("my_function")
        ... async def my_function():
        ...     pass
    """
    def decorator(func: Callable) -> Callable:
        name = metric_name or func.__name__
        registry = get_metrics_registry()
        
        counter = registry.counter(f"{name}_total", f"Total calls to {name}")
        duration = registry.histogram(f"{name}_duration_seconds", f"Duration of {name}")
        errors = registry.counter(f"{name}_errors_total", f"Errors in {name}")
        
        async def async_wrapper(*args, **kwargs):
            counter.inc(labels=labels)
            start = time.perf_counter()
            
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                errors.inc(labels={**(labels or {}), "error_type": type(e).__name__})
                raise
            finally:
                elapsed = time.perf_counter() - start
                duration.observe(elapsed, labels=labels)
        
        def sync_wrapper(*args, **kwargs):
            counter.inc(labels=labels)
            start = time.perf_counter()
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                errors.inc(labels={**(labels or {}), "error_type": type(e).__name__})
                raise
            finally:
                elapsed = time.perf_counter() - start
                duration.observe(elapsed, labels=labels)
        
        if asyncio.iscoroutinefunction(func):
            async_wrapper.__name__ = func.__name__
            async_wrapper.__doc__ = func.__doc__
            return async_wrapper
        
        sync_wrapper.__name__ = func.__name__
        sync_wrapper.__doc__ = func.__doc__
        return sync_wrapper
    
    return decorator


# =============================================================================
# HTTP Server for Prometheus
# =============================================================================

async def start_metrics_server(host: str = "0.0.0.0", port: int = 9090):
    """
    Start a simple HTTP server for Prometheus scraping.
    
    Usage:
        >>> await start_metrics_server(port=9090)
    """
    from http.server import HTTPServer, BaseHTTPRequestHandler
    
    registry = get_metrics_registry()
    exporter = PrometheusExporter()
    
    class MetricsHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/metrics":
                content = exporter.format(registry)
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(content.encode())
            else:
                self.send_response(404)
                self.end_headers()
        
        def log_message(self, format, *args):
            pass  # Suppress logs
    
    server = HTTPServer((host, port), MetricsHandler)
    logger.info(f"Metrics server started on {host}:{port}")
    
    # Run in thread
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    
    return server
