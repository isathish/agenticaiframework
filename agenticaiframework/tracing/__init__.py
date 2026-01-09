"""
Tracing Package.

Agent Step Tracing and Latency Metrics:
- Distributed tracing with span hierarchy
- Step-by-step execution tracking
- Latency metrics and percentile calculations
- Context propagation
- Trace export (OpenTelemetry compatible)
"""

from .types import SpanContext, Span
from .tracer import AgentStepTracer
from .metrics import LatencyMetrics

# Global instances
tracer = AgentStepTracer()
latency_metrics = LatencyMetrics()

__all__ = [
    # Types
    'SpanContext',
    'Span',
    # Classes
    'AgentStepTracer',
    'LatencyMetrics',
    # Global instances
    'tracer',
    'latency_metrics',
]
