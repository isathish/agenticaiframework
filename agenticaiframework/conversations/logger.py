"""
Agent Logging Implementation.

Structured logging for agent activities including
conversation logging, action tracking, and monitoring.
"""

import json
import logging
import sys
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable, TextIO
import traceback

logger = logging.getLogger(__name__)


class LogLevel(Enum):
    """Log severity levels."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    
    @property
    def numeric(self) -> int:
        return {
            "debug": 10,
            "info": 20,
            "warning": 30,
            "error": 40,
            "critical": 50,
        }[self.value]


@dataclass
class LogEntry:
    """A structured log entry."""
    id: str
    timestamp: str
    level: LogLevel
    message: str
    agent_id: str
    session_id: Optional[str] = None
    event_type: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    duration_ms: Optional[int] = None
    error: Optional[str] = None
    stack_trace: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "level": self.level.value,
            "message": self.message,
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "event_type": self.event_type,
            "data": self.data,
            "metadata": self.metadata,
            "duration_ms": self.duration_ms,
            "error": self.error,
            "stack_trace": self.stack_trace,
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())
    
    def to_formatted(self, include_data: bool = False) -> str:
        """Format as human-readable string."""
        parts = [
            f"[{self.timestamp}]",
            f"[{self.level.value.upper()}]",
            f"[{self.agent_id}]",
        ]
        
        if self.event_type:
            parts.append(f"[{self.event_type}]")
        
        parts.append(self.message)
        
        if self.duration_ms is not None:
            parts.append(f"({self.duration_ms}ms)")
        
        result = " ".join(parts)
        
        if include_data and self.data:
            result += f"\n  Data: {json.dumps(self.data)}"
        
        if self.error:
            result += f"\n  Error: {self.error}"
        
        return result


@dataclass
class LogConfig:
    """Logging configuration."""
    level: LogLevel = LogLevel.INFO
    format: str = "text"  # 'text', 'json', 'structured'
    output: str = "console"  # 'console', 'file', 'both'
    file_path: Optional[str] = None
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5
    include_stack_trace: bool = True
    include_data: bool = True
    async_logging: bool = False


class AgentLogger:
    """
    Structured logger for agent activities.
    
    Example:
        >>> log = AgentLogger(agent_id="assistant")
        >>> 
        >>> # Log events
        >>> log.info("Agent started")
        >>> log.debug("Processing request", data={"query": "..."})
        >>> 
        >>> # Log with timing
        >>> with log.timed("LLM call"):
        ...     response = llm.generate(prompt)
        >>> 
        >>> # Log errors
        >>> try:
        ...     risky_operation()
        >>> except Exception as e:
        ...     log.error("Operation failed", error=e)
    """
    
    _counter = 0
    _lock = threading.Lock()
    
    def __init__(
        self,
        agent_id: str,
        session_id: Optional[str] = None,
        config: Optional[LogConfig] = None,
    ):
        self.agent_id = agent_id
        self.session_id = session_id
        self.config = config or LogConfig()
        
        self._entries: List[LogEntry] = []
        self._handlers: List[Callable[[LogEntry], None]] = []
        self._file: Optional[TextIO] = None
        
        self._setup_output()
    
    def _setup_output(self) -> None:
        """Setup output destinations."""
        if self.config.output in ("file", "both") and self.config.file_path:
            Path(self.config.file_path).parent.mkdir(parents=True, exist_ok=True)
            self._file = open(self.config.file_path, "a")
    
    def __del__(self) -> None:
        """Clean up file handle on destruction."""
        if hasattr(self, '_file') and self._file:
            try:
                self._file.close()
            except Exception:
                pass
    
    def close(self) -> None:
        """Explicitly close the logger and release resources."""
        if self._file:
            self._file.close()
            self._file = None
    
    def _generate_id(self) -> str:
        """Generate unique log entry ID."""
        with self._lock:
            AgentLogger._counter += 1
            return f"log-{AgentLogger._counter:06d}"
    
    def _create_entry(
        self,
        level: LogLevel,
        message: str,
        event_type: Optional[str] = None,
        data: Optional[Dict] = None,
        error: Optional[Exception] = None,
        duration_ms: Optional[int] = None,
        **metadata,
    ) -> LogEntry:
        """Create log entry."""
        entry = LogEntry(
            id=self._generate_id(),
            timestamp=datetime.now().isoformat(),
            level=level,
            message=message,
            agent_id=self.agent_id,
            session_id=self.session_id,
            event_type=event_type,
            data=data or {},
            metadata=metadata,
            duration_ms=duration_ms,
        )
        
        if error:
            entry.error = str(error)
            if self.config.include_stack_trace:
                entry.stack_trace = traceback.format_exc()
        
        return entry
    
    def _should_log(self, level: LogLevel) -> bool:
        """Check if level should be logged."""
        return level.numeric >= self.config.level.numeric
    
    def _output(self, entry: LogEntry) -> None:
        """Output log entry."""
        if not self._should_log(entry.level):
            return
        
        self._entries.append(entry)
        
        # Format output
        if self.config.format == "json":
            output = entry.to_json()
        else:
            output = entry.to_formatted(include_data=self.config.include_data)
        
        # Write to console
        if self.config.output in ("console", "both"):
            stream = sys.stderr if entry.level.numeric >= LogLevel.ERROR.numeric else sys.stdout
            print(output, file=stream)
        
        # Write to file
        if self.config.output in ("file", "both") and self._file:
            self._file.write(output + "\n")
            self._file.flush()
        
        # Notify handlers
        for handler in self._handlers:
            try:
                handler(entry)
            except Exception:
                pass
    
    # Log methods
    def log(
        self,
        level: LogLevel,
        message: str,
        event_type: Optional[str] = None,
        data: Optional[Dict] = None,
        error: Optional[Exception] = None,
        **metadata,
    ) -> LogEntry:
        """Log message at specified level."""
        entry = self._create_entry(level, message, event_type, data, error, **metadata)
        self._output(entry)
        return entry
    
    def debug(self, message: str, **kwargs) -> LogEntry:
        """Log debug message."""
        return self.log(LogLevel.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs) -> LogEntry:
        """Log info message."""
        return self.log(LogLevel.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs) -> LogEntry:
        """Log warning message."""
        return self.log(LogLevel.WARNING, message, **kwargs)
    
    def error(self, message: str, error: Optional[Exception] = None, **kwargs) -> LogEntry:
        """Log error message."""
        return self.log(LogLevel.ERROR, message, error=error, **kwargs)
    
    def critical(self, message: str, error: Optional[Exception] = None, **kwargs) -> LogEntry:
        """Log critical message."""
        return self.log(LogLevel.CRITICAL, message, error=error, **kwargs)
    
    # Event logging
    def event(self, event_type: str, message: str, data: Optional[Dict] = None) -> LogEntry:
        """Log typed event."""
        return self.log(LogLevel.INFO, message, event_type=event_type, data=data)
    
    def llm_call(
        self,
        model: str,
        tokens_in: int,
        tokens_out: int,
        duration_ms: int,
        **kwargs,
    ) -> LogEntry:
        """Log LLM API call."""
        return self.log(
            LogLevel.INFO,
            f"LLM call to {model}",
            event_type="llm_call",
            data={
                "model": model,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "total_tokens": tokens_in + tokens_out,
                **kwargs,
            },
            duration_ms=duration_ms,
        )
    
    def tool_call(
        self,
        tool_name: str,
        success: bool,
        duration_ms: int,
        **kwargs,
    ) -> LogEntry:
        """Log tool invocation."""
        level = LogLevel.INFO if success else LogLevel.WARNING
        return self.log(
            level,
            f"Tool call: {tool_name}",
            event_type="tool_call",
            data={"tool_name": tool_name, "success": success, **kwargs},
            duration_ms=duration_ms,
        )
    
    def user_message(self, content: str, **kwargs) -> LogEntry:
        """Log user message."""
        return self.log(
            LogLevel.INFO,
            "User message received",
            event_type="user_message",
            data={"content_length": len(content), **kwargs},
        )
    
    def assistant_message(self, content: str, **kwargs) -> LogEntry:
        """Log assistant message."""
        return self.log(
            LogLevel.INFO,
            "Assistant response sent",
            event_type="assistant_message",
            data={"content_length": len(content), **kwargs},
        )
    
    # Timing context manager
    class _TimedContext:
        def __init__(self, logger: "AgentLogger", operation: str, **kwargs):
            self.logger = logger
            self.operation = operation
            self.kwargs = kwargs
            self.start_time: Optional[float] = None
        
        def __enter__(self):
            import time
            self.start_time = time.time()
            return self
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            import time
            duration_ms = int((time.time() - self.start_time) * 1000)
            
            if exc_type:
                self.logger.error(
                    f"{self.operation} failed",
                    event_type="timed_operation",
                    error=exc_val,
                    duration_ms=duration_ms,
                    **self.kwargs,
                )
            else:
                self.logger.info(
                    f"{self.operation} completed",
                    event_type="timed_operation",
                    duration_ms=duration_ms,
                    **self.kwargs,
                )
            
            return False
    
    def timed(self, operation: str, **kwargs) -> _TimedContext:
        """Context manager for timing operations."""
        return self._TimedContext(self, operation, **kwargs)
    
    # Handler management
    def add_handler(self, handler: Callable[[LogEntry], None]) -> None:
        """Add log handler."""
        self._handlers.append(handler)
    
    def remove_handler(self, handler: Callable[[LogEntry], None]) -> None:
        """Remove log handler."""
        if handler in self._handlers:
            self._handlers.remove(handler)
    
    # Query and export
    def get_entries(
        self,
        level: Optional[LogLevel] = None,
        event_type: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[LogEntry]:
        """Get log entries with optional filtering."""
        entries = self._entries
        
        if level:
            entries = [e for e in entries if e.level.numeric >= level.numeric]
        
        if event_type:
            entries = [e for e in entries if e.event_type == event_type]
        
        if limit:
            entries = entries[-limit:]
        
        return entries
    
    def export_json(self) -> str:
        """Export all entries as JSON."""
        return json.dumps([e.to_dict() for e in self._entries], indent=2)
    
    def clear(self) -> None:
        """Clear log entries."""
        self._entries.clear()
    
    def close(self) -> None:
        """Close file handles."""
        if self._file:
            self._file.close()
            self._file = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


class StructuredLogger(AgentLogger):
    """
    Extended structured logger with metrics and tracing.
    
    Adds support for:
    - Spans and traces
    - Metrics collection
    - Correlation IDs
    """
    
    def __init__(
        self,
        agent_id: str,
        session_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        config: Optional[LogConfig] = None,
    ):
        super().__init__(agent_id, session_id, config)
        self.trace_id = trace_id or f"trace-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self._spans: List[Dict] = []
        self._metrics: Dict[str, List[float]] = {}
    
    def start_span(self, name: str, **attributes) -> Dict:
        """Start a new span."""
        import time
        span = {
            "name": name,
            "trace_id": self.trace_id,
            "span_id": f"span-{len(self._spans):04d}",
            "start_time": time.time(),
            "attributes": attributes,
        }
        self._spans.append(span)
        return span
    
    def end_span(self, span: Dict, status: str = "ok") -> None:
        """End a span."""
        import time
        span["end_time"] = time.time()
        span["duration_ms"] = int((span["end_time"] - span["start_time"]) * 1000)
        span["status"] = status
        
        self.info(
            f"Span completed: {span['name']}",
            event_type="span",
            data=span,
        )
    
    def record_metric(self, name: str, value: float, unit: str = "") -> None:
        """Record a metric value."""
        if name not in self._metrics:
            self._metrics[name] = []
        self._metrics[name].append(value)
        
        self.debug(
            f"Metric: {name}={value}{unit}",
            event_type="metric",
            data={"name": name, "value": value, "unit": unit},
        )
    
    def get_metrics_summary(self) -> Dict[str, Dict]:
        """Get summary of recorded metrics."""
        summary = {}
        for name, values in self._metrics.items():
            if values:
                summary[name] = {
                    "count": len(values),
                    "sum": sum(values),
                    "avg": sum(values) / len(values),
                    "min": min(values),
                    "max": max(values),
                }
        return summary


class ConversationLogger(AgentLogger):
    """
    Specialized logger for conversation tracking.
    
    Example:
        >>> conv_log = ConversationLogger(agent_id="assistant", session_id="sess-123")
        >>> 
        >>> conv_log.log_turn(
        ...     user_input="What's the weather?",
        ...     assistant_output="It's sunny today!",
        ...     tokens_used=50,
        ...     duration_ms=1200
        ... )
    """
    
    def __init__(
        self,
        agent_id: str,
        session_id: str,
        config: Optional[LogConfig] = None,
    ):
        super().__init__(agent_id, session_id, config)
        self._turn_count = 0
    
    def log_turn(
        self,
        user_input: str,
        assistant_output: str,
        tokens_used: int = 0,
        duration_ms: int = 0,
        tool_calls: List[Dict] = None,
        **metadata,
    ) -> LogEntry:
        """Log a complete conversation turn."""
        self._turn_count += 1
        
        return self.log(
            LogLevel.INFO,
            f"Turn {self._turn_count} completed",
            event_type="conversation_turn",
            data={
                "turn_number": self._turn_count,
                "user_input_length": len(user_input),
                "assistant_output_length": len(assistant_output),
                "tokens_used": tokens_used,
                "tool_calls_count": len(tool_calls) if tool_calls else 0,
                "tool_calls": tool_calls or [],
                **metadata,
            },
            duration_ms=duration_ms,
        )
    
    def log_feedback(
        self,
        turn_number: int,
        rating: Optional[int] = None,
        feedback_text: Optional[str] = None,
        feedback_type: str = "general",
    ) -> LogEntry:
        """Log user feedback on a turn."""
        return self.log(
            LogLevel.INFO,
            f"Feedback received for turn {turn_number}",
            event_type="feedback",
            data={
                "turn_number": turn_number,
                "rating": rating,
                "feedback_text": feedback_text,
                "feedback_type": feedback_type,
            },
        )
    
    def log_session_start(self, **metadata) -> LogEntry:
        """Log session start."""
        return self.log(
            LogLevel.INFO,
            "Conversation session started",
            event_type="session_start",
            data=metadata,
        )
    
    def log_session_end(self, total_turns: int, total_duration_ms: int, **metadata) -> LogEntry:
        """Log session end."""
        return self.log(
            LogLevel.INFO,
            "Conversation session ended",
            event_type="session_end",
            data={
                "total_turns": total_turns,
                "total_duration_ms": total_duration_ms,
                **metadata,
            },
        )


__all__ = [
    "LogLevel",
    "LogEntry",
    "LogConfig",
    "AgentLogger",
    "StructuredLogger",
    "ConversationLogger",
]
