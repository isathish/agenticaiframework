"""
Agent Step Tracing and Latency Metrics module.

Provides comprehensive observability features:
- Distributed tracing with span hierarchy
- Step-by-step execution tracking
- Latency metrics and percentile calculations
- Context propagation
- Trace export (OpenTelemetry compatible)
"""

import uuid
import time
import logging
import threading
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
import json
import statistics

logger = logging.getLogger(__name__)


@dataclass
class SpanContext:
    """Context for distributed tracing."""
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    baggage: Dict[str, str] = field(default_factory=dict)


@dataclass
class Span:
    """Represents a single span in a trace."""
    span_id: str
    trace_id: str
    name: str
    parent_span_id: Optional[str]
    start_time: float
    end_time: Optional[float] = None
    status: str = "OK"
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    
    @property
    def duration_ms(self) -> Optional[float]:
        """Get span duration in milliseconds."""
        if self.end_time is None:
            return None
        return (self.end_time - self.start_time) * 1000
    
    def add_event(self, name: str, attributes: Dict[str, Any] = None):
        """Add an event to the span."""
        self.events.append({
            'name': name,
            'timestamp': time.time(),
            'attributes': attributes or {}
        })
    
    def set_attribute(self, key: str, value: Any):
        """Set a span attribute."""
        self.attributes[key] = value
    
    def set_status(self, status: str, description: str = None):
        """Set span status."""
        self.status = status
        if description:
            self.attributes['status_description'] = description
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert span to dictionary."""
        return {
            'span_id': self.span_id,
            'trace_id': self.trace_id,
            'name': self.name,
            'parent_span_id': self.parent_span_id,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'duration_ms': self.duration_ms,
            'status': self.status,
            'attributes': self.attributes,
            'events': self.events
        }


class AgentStepTracer:
    """
    Comprehensive agent step tracing system.
    
    Features:
    - Distributed tracing with trace/span hierarchy
    - Automatic context propagation
    - Step-by-step execution tracking
    - Error tracking and correlation
    - Export to various backends
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern for global tracer."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        self._initialized = True
        
        self.traces: Dict[str, List[Span]] = defaultdict(list)
        self.active_spans: Dict[str, Span] = {}
        self._context_var = threading.local()
        self.exporters: List[Callable[[Span], None]] = []
        self.sampling_rate: float = 1.0
        self.max_traces: int = 10000
        
        # Statistics
        self.stats = {
            'total_traces': 0,
            'total_spans': 0,
            'error_spans': 0
        }
    
    def set_sampling_rate(self, rate: float):
        """Set trace sampling rate (0.0 to 1.0)."""
        self.sampling_rate = max(0.0, min(1.0, rate))
    
    def add_exporter(self, exporter: Callable[[Span], None]):
        """Add a span exporter."""
        self.exporters.append(exporter)
    
    def _should_sample(self) -> bool:
        """Determine if trace should be sampled."""
        import random
        return random.random() < self.sampling_rate
    
    def start_trace(self, name: str = "root") -> SpanContext:
        """Start a new trace."""
        if not self._should_sample():
            return None
        
        trace_id = str(uuid.uuid4())
        span_id = str(uuid.uuid4())
        
        context = SpanContext(
            trace_id=trace_id,
            span_id=span_id
        )
        
        span = Span(
            span_id=span_id,
            trace_id=trace_id,
            name=name,
            parent_span_id=None,
            start_time=time.time()
        )
        
        self.traces[trace_id].append(span)
        self.active_spans[span_id] = span
        self._set_current_context(context)
        
        self.stats['total_traces'] += 1
        self.stats['total_spans'] += 1
        
        self._cleanup_old_traces()
        
        logger.debug("Started trace %s with root span %s", trace_id, span_id)
        return context
    
    def start_span(self, name: str, parent_context: SpanContext = None) -> SpanContext:
        """Start a new span."""
        parent = parent_context or self._get_current_context()
        
        if parent is None:
            return self.start_trace(name)
        
        span_id = str(uuid.uuid4())
        
        span = Span(
            span_id=span_id,
            trace_id=parent.trace_id,
            name=name,
            parent_span_id=parent.span_id,
            start_time=time.time()
        )
        
        self.traces[parent.trace_id].append(span)
        self.active_spans[span_id] = span
        
        context = SpanContext(
            trace_id=parent.trace_id,
            span_id=span_id,
            parent_span_id=parent.span_id,
            baggage=parent.baggage.copy()
        )
        
        self._set_current_context(context)
        self.stats['total_spans'] += 1
        
        logger.debug("Started span %s (parent: %s)", span_id, parent.span_id)
        return context
    
    def end_span(self, context: SpanContext = None, status: str = "OK", error: Exception = None):
        """End a span."""
        ctx = context or self._get_current_context()
        if ctx is None:
            return
        
        span = self.active_spans.get(ctx.span_id)
        if span:
            span.end_time = time.time()
            span.status = status
            
            if error:
                span.set_status("ERROR", str(error))
                span.set_attribute('error.type', type(error).__name__)
                span.set_attribute('error.message', str(error))
                self.stats['error_spans'] += 1
            
            # Export span
            for exporter in self.exporters:
                try:
                    exporter(span)
                except Exception as e:
                    logger.error("Exporter failed: %s", e)
            
            del self.active_spans[ctx.span_id]
            
            # Restore parent context
            if ctx.parent_span_id:
                parent_ctx = SpanContext(
                    trace_id=ctx.trace_id,
                    span_id=ctx.parent_span_id,
                    baggage=ctx.baggage
                )
                self._set_current_context(parent_ctx)
            else:
                self._clear_current_context()
        
        logger.debug("Ended span %s with status %s", ctx.span_id, status)
    
    @contextmanager
    def trace_step(self, name: str, attributes: Dict[str, Any] = None):
        """Context manager for tracing a step."""
        context = self.start_span(name)
        
        if context and attributes:
            span = self.active_spans.get(context.span_id)
            if span:
                for key, value in attributes.items():
                    span.set_attribute(key, value)
        
        try:
            yield context
            self.end_span(context, status="OK")
        except Exception as e:
            self.end_span(context, status="ERROR", error=e)
            raise
    
    def add_event(self, name: str, attributes: Dict[str, Any] = None):
        """Add event to current span."""
        context = self._get_current_context()
        if context:
            span = self.active_spans.get(context.span_id)
            if span:
                span.add_event(name, attributes)
    
    def set_attribute(self, key: str, value: Any):
        """Set attribute on current span."""
        context = self._get_current_context()
        if context:
            span = self.active_spans.get(context.span_id)
            if span:
                span.set_attribute(key, value)
    
    def get_trace(self, trace_id: str) -> List[Dict[str, Any]]:
        """Get all spans for a trace."""
        return [span.to_dict() for span in self.traces.get(trace_id, [])]
    
    def get_trace_tree(self, trace_id: str) -> Dict[str, Any]:
        """Get trace as a hierarchical tree."""
        spans = self.traces.get(trace_id, [])
        if not spans:
            return {}
        
        span_map = {s.span_id: s.to_dict() for s in spans}
        
        # Build tree
        root = None
        for span_dict in span_map.values():
            span_dict['children'] = []
            if span_dict['parent_span_id'] is None:
                root = span_dict
        
        for span_dict in span_map.values():
            parent_id = span_dict['parent_span_id']
            if parent_id and parent_id in span_map:
                span_map[parent_id]['children'].append(span_dict)
        
        return root or {}
    
    def _get_current_context(self) -> Optional[SpanContext]:
        """Get current span context."""
        return getattr(self._context_var, 'context', None)
    
    def _set_current_context(self, context: SpanContext):
        """Set current span context."""
        self._context_var.context = context
    
    def _clear_current_context(self):
        """Clear current span context."""
        self._context_var.context = None
    
    def _cleanup_old_traces(self):
        """Clean up old traces to prevent memory growth."""
        if len(self.traces) > self.max_traces:
            # Remove oldest traces
            sorted_traces = sorted(
                self.traces.keys(),
                key=lambda t: min(s.start_time for s in self.traces[t]) if self.traces[t] else 0
            )
            for trace_id in sorted_traces[:len(self.traces) - self.max_traces]:
                del self.traces[trace_id]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get tracer statistics."""
        return {
            **self.stats,
            'active_traces': len(self.traces),
            'active_spans': len(self.active_spans),
            'sampling_rate': self.sampling_rate
        }


class LatencyMetrics:
    """
    Comprehensive latency metrics collection and analysis.
    
    Features:
    - Histogram-based latency tracking
    - Percentile calculations (p50, p90, p95, p99)
    - SLA monitoring
    - Anomaly detection
    - Time-window aggregations
    """
    
    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        self.metrics: Dict[str, List[float]] = defaultdict(list)
        self.timestamps: Dict[str, List[float]] = defaultdict(list)
        self.sla_thresholds: Dict[str, float] = {}
        self.sla_violations: Dict[str, int] = defaultdict(int)
        
        # Aggregated stats
        self.total_counts: Dict[str, int] = defaultdict(int)
        self.total_sums: Dict[str, float] = defaultdict(float)
        
        self._lock = threading.Lock()
    
    def record(self, metric_name: str, latency_ms: float):
        """Record a latency measurement."""
        with self._lock:
            self.metrics[metric_name].append(latency_ms)
            self.timestamps[metric_name].append(time.time())
            self.total_counts[metric_name] += 1
            self.total_sums[metric_name] += latency_ms
            
            # Maintain window size
            if len(self.metrics[metric_name]) > self.window_size:
                self.metrics[metric_name].pop(0)
                self.timestamps[metric_name].pop(0)
            
            # Check SLA
            if metric_name in self.sla_thresholds:
                if latency_ms > self.sla_thresholds[metric_name]:
                    self.sla_violations[metric_name] += 1
                    logger.warning(
                        "SLA violation for %s: %.2fms > %.2fms threshold",
                        metric_name, latency_ms, self.sla_thresholds[metric_name]
                    )
    
    @contextmanager
    def measure(self, metric_name: str):
        """Context manager to measure latency."""
        start = time.time()
        try:
            yield
        finally:
            latency_ms = (time.time() - start) * 1000
            self.record(metric_name, latency_ms)
    
    def set_sla_threshold(self, metric_name: str, threshold_ms: float):
        """Set SLA threshold for a metric."""
        self.sla_thresholds[metric_name] = threshold_ms
    
    def get_percentile(self, metric_name: str, percentile: float) -> Optional[float]:
        """Get percentile value for a metric."""
        values = self.metrics.get(metric_name, [])
        if not values:
            return None
        
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile / 100)
        return sorted_values[min(index, len(sorted_values) - 1)]
    
    def get_stats(self, metric_name: str) -> Dict[str, Any]:
        """Get comprehensive stats for a metric."""
        values = self.metrics.get(metric_name, [])
        if not values:
            return {'error': 'No data'}
        
        return {
            'count': len(values),
            'total_count': self.total_counts[metric_name],
            'min': min(values),
            'max': max(values),
            'mean': statistics.mean(values),
            'median': statistics.median(values),
            'stdev': statistics.stdev(values) if len(values) > 1 else 0,
            'p50': self.get_percentile(metric_name, 50),
            'p90': self.get_percentile(metric_name, 90),
            'p95': self.get_percentile(metric_name, 95),
            'p99': self.get_percentile(metric_name, 99),
            'sla_threshold': self.sla_thresholds.get(metric_name),
            'sla_violations': self.sla_violations.get(metric_name, 0),
            'sla_compliance_rate': self._calculate_sla_compliance(metric_name)
        }
    
    def _calculate_sla_compliance(self, metric_name: str) -> Optional[float]:
        """Calculate SLA compliance rate."""
        if metric_name not in self.sla_thresholds:
            return None
        
        total = self.total_counts[metric_name]
        if total == 0:
            return 100.0
        
        violations = self.sla_violations.get(metric_name, 0)
        return ((total - violations) / total) * 100
    
    def get_time_series(self, metric_name: str, 
                        bucket_seconds: int = 60) -> List[Dict[str, Any]]:
        """Get time-series data with bucketed aggregations."""
        values = self.metrics.get(metric_name, [])
        timestamps = self.timestamps.get(metric_name, [])
        
        if not values:
            return []
        
        # Bucket data
        buckets: Dict[int, List[float]] = defaultdict(list)
        for ts, val in zip(timestamps, values):
            bucket = int(ts // bucket_seconds) * bucket_seconds
            buckets[bucket].append(val)
        
        # Aggregate buckets
        result = []
        for bucket_ts in sorted(buckets.keys()):
            bucket_values = buckets[bucket_ts]
            result.append({
                'timestamp': bucket_ts,
                'count': len(bucket_values),
                'mean': statistics.mean(bucket_values),
                'min': min(bucket_values),
                'max': max(bucket_values),
                'p95': sorted(bucket_values)[int(len(bucket_values) * 0.95)] if bucket_values else 0
            })
        
        return result
    
    def detect_anomalies(self, metric_name: str, 
                         z_threshold: float = 3.0) -> List[Dict[str, Any]]:
        """Detect latency anomalies using z-score."""
        values = self.metrics.get(metric_name, [])
        timestamps = self.timestamps.get(metric_name, [])
        
        if len(values) < 10:
            return []
        
        mean = statistics.mean(values)
        stdev = statistics.stdev(values)
        
        if stdev == 0:
            return []
        
        anomalies = []
        for i, (val, ts) in enumerate(zip(values, timestamps)):
            z_score = abs(val - mean) / stdev
            if z_score > z_threshold:
                anomalies.append({
                    'index': i,
                    'timestamp': ts,
                    'value': val,
                    'z_score': z_score,
                    'mean': mean,
                    'stdev': stdev
                })
        
        return anomalies
    
    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get stats for all metrics."""
        return {name: self.get_stats(name) for name in self.metrics.keys()}
    
    def export_prometheus(self) -> str:
        """Export metrics in Prometheus format."""
        lines = []
        
        for metric_name, values in self.metrics.items():
            if not values:
                continue
            
            safe_name = metric_name.replace('.', '_').replace('-', '_')
            
            # Histogram buckets
            buckets = [10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000]
            for bucket in buckets:
                count = sum(1 for v in values if v <= bucket)
                lines.append(f'{safe_name}_bucket{{le="{bucket}"}} {count}')
            
            lines.append(f'{safe_name}_bucket{{le="+Inf"}} {len(values)}')
            lines.append(f'{safe_name}_sum {sum(values)}')
            lines.append(f'{safe_name}_count {len(values)}')
        
        return '\n'.join(lines)


# Global instances
tracer = AgentStepTracer()
latency_metrics = LatencyMetrics()
