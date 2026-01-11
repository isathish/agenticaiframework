"""
Agent Step Tracer.

Comprehensive agent step tracing system with:
- Distributed tracing with trace/span hierarchy
- Automatic context propagation
- Step-by-step execution tracking
- Error tracking and correlation
- Export to various backends
"""

import uuid
import time
import random
import logging
import threading
from typing import Dict, Any, List, Optional, Callable
from collections import defaultdict
from contextlib import contextmanager

from .types import SpanContext, Span

logger = logging.getLogger(__name__)


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
            
            for exporter in self.exporters:
                try:
                    exporter(span)
                except Exception as e:  # noqa: BLE001
                    logger.error("Exporter failed: %s", e)
            
            del self.active_spans[ctx.span_id]
            
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
    
    def list_traces(self, limit: int = 100) -> List[Dict[str, Any]]:
        """List recent traces with summary information."""
        result = []
        trace_ids = list(self.traces.keys())[-limit:]  # Get most recent
        
        for trace_id in reversed(trace_ids):  # Most recent first
            spans = self.traces.get(trace_id, [])
            if not spans:
                continue
            
            root_span = next((s for s in spans if s.parent_span_id is None), spans[0])
            
            # Calculate total duration
            min_start = min(s.start_time for s in spans)
            max_end = max(s.end_time or s.start_time for s in spans)
            duration_ms = int((max_end - min_start) * 1000)
            
            # Determine overall status
            has_error = any(s.status == "ERROR" for s in spans)
            
            result.append({
                "trace_id": trace_id,
                "operation": root_span.name,
                "status": "error" if has_error else "success",
                "start_time": root_span.start_time,
                "duration_ms": duration_ms,
                "spans_count": len(spans),
                "metadata": root_span.attributes,
            })
        
        return result

    def get_trace_tree(self, trace_id: str) -> Dict[str, Any]:
        """Get trace as a hierarchical tree."""
        spans = self.traces.get(trace_id, [])
        if not spans:
            return {}
        
        span_map = {s.span_id: s.to_dict() for s in spans}
        
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


__all__ = ['AgentStepTracer']
