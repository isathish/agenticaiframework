"""
Enterprise Distributed Tracing - OpenTelemetry integration.

Provides distributed tracing for multi-agent workflows
with OpenTelemetry integration.

Features:
- OpenTelemetry spans
- Trace context propagation
- Agent/workflow correlation
- Performance metrics
- Export to various backends
"""

import asyncio
import functools
import logging
import os
import time
import threading
from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union
import uuid

logger = logging.getLogger(__name__)


# =============================================================================
# Types
# =============================================================================

T = TypeVar("T")


class SpanKind(Enum):
    """Kind of span."""
    INTERNAL = "internal"
    CLIENT = "client"
    SERVER = "server"
    PRODUCER = "producer"
    CONSUMER = "consumer"


class SpanStatus(Enum):
    """Status of a span."""
    UNSET = "unset"
    OK = "ok"
    ERROR = "error"


# =============================================================================
# Span and Trace
# =============================================================================

@dataclass
class SpanContext:
    """Context for a span."""
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    
    # Flags
    sampled: bool = True
    
    def to_dict(self) -> Dict:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "sampled": self.sampled,
        }
    
    def to_header(self) -> str:
        """Convert to W3C traceparent header."""
        sampled = "01" if self.sampled else "00"
        return f"00-{self.trace_id}-{self.span_id}-{sampled}"
    
    @classmethod
    def from_header(cls, header: str) -> Optional["SpanContext"]:
        """Parse W3C traceparent header."""
        try:
            parts = header.split("-")
            if len(parts) >= 4:
                return cls(
                    trace_id=parts[1],
                    span_id=parts[2],
                    sampled=parts[3] == "01",
                )
        except Exception:
            pass
        return None


@dataclass
class SpanEvent:
    """Event within a span."""
    name: str
    timestamp: datetime = field(default_factory=datetime.now)
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Span:
    """A trace span."""
    name: str
    context: SpanContext
    
    # Kind and status
    kind: SpanKind = SpanKind.INTERNAL
    status: SpanStatus = SpanStatus.UNSET
    status_message: Optional[str] = None
    
    # Timing
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    
    # Attributes
    attributes: Dict[str, Any] = field(default_factory=dict)
    
    # Events and links
    events: List[SpanEvent] = field(default_factory=list)
    links: List[SpanContext] = field(default_factory=list)
    
    # Resource info
    service_name: str = "agenticai"
    
    @property
    def duration_ms(self) -> Optional[float]:
        """Duration in milliseconds."""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds() * 1000
        return None
    
    @property
    def is_recording(self) -> bool:
        """Check if span is still recording."""
        return self.end_time is None
    
    def set_attribute(self, key: str, value: Any):
        """Set a span attribute."""
        self.attributes[key] = value
    
    def set_attributes(self, attributes: Dict[str, Any]):
        """Set multiple attributes."""
        self.attributes.update(attributes)
    
    def add_event(self, name: str, attributes: Dict[str, Any] = None):
        """Add an event to the span."""
        self.events.append(SpanEvent(
            name=name,
            attributes=attributes or {},
        ))
    
    def set_status(self, status: SpanStatus, message: str = None):
        """Set span status."""
        self.status = status
        self.status_message = message
    
    def end(self, end_time: datetime = None):
        """End the span."""
        self.end_time = end_time or datetime.now()
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "trace_id": self.context.trace_id,
            "span_id": self.context.span_id,
            "parent_span_id": self.context.parent_span_id,
            "kind": self.kind.value,
            "status": self.status.value,
            "status_message": self.status_message,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "attributes": self.attributes,
            "events": [
                {"name": e.name, "timestamp": e.timestamp.isoformat(), "attributes": e.attributes}
                for e in self.events
            ],
            "service_name": self.service_name,
        }


# =============================================================================
# Span Exporter
# =============================================================================

class SpanExporter(ABC):
    """Abstract interface for span export."""
    
    @abstractmethod
    def export(self, spans: List[Span]) -> bool:
        """Export spans. Returns True on success."""
        pass
    
    @abstractmethod
    def shutdown(self):
        """Shutdown the exporter."""
        pass


class ConsoleExporter(SpanExporter):
    """Export spans to console."""
    
    def __init__(self, pretty: bool = True):
        self.pretty = pretty
    
    def export(self, spans: List[Span]) -> bool:
        import json
        
        for span in spans:
            if self.pretty:
                print(f"[TRACE] {span.name} ({span.duration_ms:.2f}ms)")
                print(f"  trace_id: {span.context.trace_id}")
                print(f"  span_id: {span.context.span_id}")
                if span.context.parent_span_id:
                    print(f"  parent: {span.context.parent_span_id}")
                for key, value in span.attributes.items():
                    print(f"  {key}: {value}")
            else:
                print(json.dumps(span.to_dict()))
        
        return True
    
    def shutdown(self):
        pass


class InMemoryExporter(SpanExporter):
    """Store spans in memory (for testing)."""
    
    def __init__(self, max_spans: int = 10000):
        self.max_spans = max_spans
        self._spans: List[Span] = []
        self._lock = threading.Lock()
    
    @property
    def spans(self) -> List[Span]:
        return list(self._spans)
    
    def export(self, spans: List[Span]) -> bool:
        with self._lock:
            self._spans.extend(spans)
            
            if len(self._spans) > self.max_spans:
                self._spans = self._spans[-self.max_spans // 2:]
        
        return True
    
    def clear(self):
        with self._lock:
            self._spans = []
    
    def shutdown(self):
        pass


class OTLPExporter(SpanExporter):
    """Export spans via OTLP (OpenTelemetry Protocol)."""
    
    def __init__(
        self,
        endpoint: str = None,
        headers: Dict[str, str] = None,
    ):
        self.endpoint = endpoint or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
        self.headers = headers or {}
    
    def export(self, spans: List[Span]) -> bool:
        try:
            import requests
            
            # Convert spans to OTLP format
            otlp_spans = []
            for span in spans:
                otlp_spans.append({
                    "traceId": span.context.trace_id,
                    "spanId": span.context.span_id,
                    "parentSpanId": span.context.parent_span_id,
                    "name": span.name,
                    "kind": span.kind.value,
                    "startTimeUnixNano": int(span.start_time.timestamp() * 1e9),
                    "endTimeUnixNano": int(span.end_time.timestamp() * 1e9) if span.end_time else None,
                    "attributes": [
                        {"key": k, "value": {"stringValue": str(v)}}
                        for k, v in span.attributes.items()
                    ],
                    "status": {"code": span.status.value},
                })
            
            payload = {
                "resourceSpans": [{
                    "resource": {
                        "attributes": [
                            {"key": "service.name", "value": {"stringValue": spans[0].service_name if spans else "agenticai"}},
                        ],
                    },
                    "scopeSpans": [{
                        "spans": otlp_spans,
                    }],
                }],
            }
            
            response = requests.post(
                f"{self.endpoint}/v1/traces",
                json=payload,
                headers={"Content-Type": "application/json", **self.headers},
                timeout=10,
            )
            
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Failed to export spans: {e}")
            return False
    
    def shutdown(self):
        pass


# =============================================================================
# Tracer
# =============================================================================

class Tracer:
    """
    Main tracing interface.
    
    Usage:
        >>> tracer = Tracer()
        >>> 
        >>> with tracer.span("my-operation") as span:
        ...     span.set_attribute("key", "value")
        ...     # Do work
    """
    
    def __init__(
        self,
        service_name: str = "agenticai",
        exporter: SpanExporter = None,
        sample_rate: float = 1.0,
    ):
        self.service_name = service_name
        self.exporter = exporter or InMemoryExporter()
        self.sample_rate = sample_rate
        
        self._current_span: threading.local = threading.local()
        self._pending_spans: List[Span] = []
        self._lock = threading.Lock()
    
    @property
    def current_span(self) -> Optional[Span]:
        """Get the current span."""
        return getattr(self._current_span, "span", None)
    
    def _generate_id(self, length: int = 16) -> str:
        """Generate a random ID."""
        return uuid.uuid4().hex[:length * 2]
    
    def _should_sample(self) -> bool:
        """Determine if this trace should be sampled."""
        import random
        return random.random() < self.sample_rate
    
    @contextmanager
    def span(
        self,
        name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: Dict[str, Any] = None,
    ):
        """Create a new span."""
        parent = self.current_span
        sampled = self._should_sample() if not parent else parent.context.sampled
        
        if parent:
            context = SpanContext(
                trace_id=parent.context.trace_id,
                span_id=self._generate_id(8),
                parent_span_id=parent.context.span_id,
                sampled=sampled,
            )
        else:
            context = SpanContext(
                trace_id=self._generate_id(16),
                span_id=self._generate_id(8),
                sampled=sampled,
            )
        
        span = Span(
            name=name,
            context=context,
            kind=kind,
            service_name=self.service_name,
            attributes=attributes or {},
        )
        
        # Set as current
        prev_span = self.current_span
        self._current_span.span = span
        
        try:
            yield span
            span.set_status(SpanStatus.OK)
        except Exception as e:
            span.set_status(SpanStatus.ERROR, str(e))
            span.add_event("exception", {
                "exception.type": type(e).__name__,
                "exception.message": str(e),
            })
            raise
        finally:
            span.end()
            self._current_span.span = prev_span
            
            if context.sampled:
                self._record_span(span)
    
    async def span_async(
        self,
        name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: Dict[str, Any] = None,
    ):
        """Async context manager for spans."""
        with self.span(name, kind, attributes) as span:
            yield span
    
    def _record_span(self, span: Span):
        """Record a span for export."""
        with self._lock:
            self._pending_spans.append(span)
            
            # Batch export
            if len(self._pending_spans) >= 100:
                self._flush()
    
    def _flush(self):
        """Flush pending spans to exporter."""
        with self._lock:
            if self._pending_spans:
                self.exporter.export(self._pending_spans)
                self._pending_spans = []
    
    def flush(self):
        """Force flush pending spans."""
        self._flush()
    
    def shutdown(self):
        """Shutdown the tracer."""
        self._flush()
        self.exporter.shutdown()


# =============================================================================
# Global Tracer
# =============================================================================

_global_tracer: Optional[Tracer] = None


def get_tracer(service_name: str = None) -> Tracer:
    """Get the global tracer."""
    global _global_tracer
    
    if _global_tracer is None:
        _global_tracer = Tracer(service_name=service_name or "agenticai")
    
    return _global_tracer


def set_tracer(tracer: Tracer):
    """Set the global tracer."""
    global _global_tracer
    _global_tracer = tracer


def configure_tracing(
    service_name: str = "agenticai",
    exporter: SpanExporter = None,
    sample_rate: float = 1.0,
) -> Tracer:
    """Configure the global tracer."""
    tracer = Tracer(
        service_name=service_name,
        exporter=exporter,
        sample_rate=sample_rate,
    )
    set_tracer(tracer)
    return tracer


# =============================================================================
# Decorators
# =============================================================================

def trace(
    name: str = None,
    kind: SpanKind = SpanKind.INTERNAL,
    attributes: Dict[str, Any] = None,
):
    """
    Decorator to trace a function.
    
    Usage:
        >>> @trace("my-function")
        ... def my_function():
        ...     pass
    """
    def decorator(func: Callable) -> Callable:
        span_name = name or func.__name__
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            tracer = get_tracer()
            with tracer.span(span_name, kind, attributes) as span:
                span.set_attribute("function.name", func.__name__)
                span.set_attribute("function.args_count", len(args))
                return func(*args, **kwargs)
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            tracer = get_tracer()
            with tracer.span(span_name, kind, attributes) as span:
                span.set_attribute("function.name", func.__name__)
                span.set_attribute("function.args_count", len(args))
                return await func(*args, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


def trace_agent(agent_name: str = None):
    """
    Decorator to trace an agent.
    
    Usage:
        >>> @trace_agent("my-agent")
        ... class MyAgent:
        ...     async def run(self):
        ...         pass
    """
    def decorator(cls):
        name = agent_name or cls.__name__
        
        original_run = cls.run if hasattr(cls, "run") else None
        
        if original_run:
            @functools.wraps(original_run)
            async def traced_run(self, *args, **kwargs):
                tracer = get_tracer()
                with tracer.span(f"agent:{name}", SpanKind.SERVER) as span:
                    span.set_attribute("agent.name", name)
                    span.set_attribute("agent.class", cls.__name__)
                    
                    result = await original_run(self, *args, **kwargs)
                    
                    if hasattr(result, "__len__"):
                        span.set_attribute("agent.output_length", len(result))
                    
                    return result
            
            cls.run = traced_run
        
        return cls
    
    return decorator


# =============================================================================
# Context Propagation
# =============================================================================

def inject_context(carrier: Dict[str, str]):
    """Inject trace context into a carrier (e.g., HTTP headers)."""
    tracer = get_tracer()
    span = tracer.current_span
    
    if span:
        carrier["traceparent"] = span.context.to_header()


def extract_context(carrier: Dict[str, str]) -> Optional[SpanContext]:
    """Extract trace context from a carrier."""
    traceparent = carrier.get("traceparent")
    
    if traceparent:
        return SpanContext.from_header(traceparent)
    
    return None


def with_context(parent_context: SpanContext):
    """
    Create a child span from an external context.
    
    Usage:
        >>> context = extract_context(request.headers)
        >>> with with_context(context).span("handler") as span:
        ...     pass
    """
    tracer = get_tracer()
    
    # Create a temporary parent span
    parent = Span(
        name="external-parent",
        context=parent_context,
    )
    
    # Set as current temporarily
    tracer._current_span.span = parent
    
    return tracer


# =============================================================================
# Agent-Specific Tracing
# =============================================================================

class AgentTracer:
    """
    Agent-specific tracing utilities.
    
    Usage:
        >>> tracer = AgentTracer("my-agent")
        >>> 
        >>> with tracer.step("thinking") as span:
        ...     # Agent thinking
        ...     pass
        >>> 
        >>> with tracer.tool_call("search", {"query": "..."}) as span:
        ...     # Tool execution
        ...     pass
    """
    
    def __init__(self, agent_name: str, tracer: Tracer = None):
        self.agent_name = agent_name
        self._tracer = tracer or get_tracer()
    
    @contextmanager
    def step(self, step_name: str, attributes: Dict[str, Any] = None):
        """Trace an agent step."""
        attrs = {"agent.name": self.agent_name, "step.name": step_name}
        if attributes:
            attrs.update(attributes)
        
        with self._tracer.span(f"{self.agent_name}:{step_name}", attributes=attrs) as span:
            yield span
    
    @contextmanager
    def tool_call(self, tool_name: str, args: Dict[str, Any] = None):
        """Trace a tool call."""
        attrs = {
            "agent.name": self.agent_name,
            "tool.name": tool_name,
        }
        if args:
            attrs["tool.args"] = str(args)[:1000]
        
        with self._tracer.span(f"tool:{tool_name}", kind=SpanKind.CLIENT, attributes=attrs) as span:
            yield span
    
    @contextmanager
    def llm_call(self, model: str, prompt_tokens: int = None):
        """Trace an LLM call."""
        attrs = {
            "agent.name": self.agent_name,
            "llm.model": model,
        }
        if prompt_tokens:
            attrs["llm.prompt_tokens"] = prompt_tokens
        
        with self._tracer.span(f"llm:{model}", kind=SpanKind.CLIENT, attributes=attrs) as span:
            yield span
    
    def record_tokens(self, input_tokens: int, output_tokens: int):
        """Record token usage on current span."""
        span = self._tracer.current_span
        if span:
            span.set_attribute("llm.input_tokens", input_tokens)
            span.set_attribute("llm.output_tokens", output_tokens)
            span.set_attribute("llm.total_tokens", input_tokens + output_tokens)


# =============================================================================
# Helper Functions
# =============================================================================

def start_span(name: str, **kwargs) -> Span:
    """Start a new span."""
    tracer = get_tracer()
    return tracer.span(name, **kwargs).__enter__()


def end_span(span: Span):
    """End a span."""
    span.end()
    tracer = get_tracer()
    tracer._record_span(span)


def current_trace_id() -> Optional[str]:
    """Get the current trace ID."""
    tracer = get_tracer()
    span = tracer.current_span
    return span.context.trace_id if span else None


def current_span_id() -> Optional[str]:
    """Get the current span ID."""
    tracer = get_tracer()
    span = tracer.current_span
    return span.context.span_id if span else None
