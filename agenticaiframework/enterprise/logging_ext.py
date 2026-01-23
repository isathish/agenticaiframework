"""
Enterprise Logging Extension Module.

Provides structured logging, log aggregation, correlation IDs,
and advanced logging patterns for agent operations.

Example:
    # Structured logging
    logger = get_structured_logger("agent")
    logger.info("Processing request", request_id=req_id, user=user)
    
    # Context logging
    with log_context(request_id="123", user="alice"):
        logger.info("Handled request")  # Automatically includes context
    
    # Decorators
    @log_calls(level="INFO")
    async def process_request():
        ...
"""

from __future__ import annotations

import asyncio
import contextvars
import json
import logging
import sys
import time
import traceback
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    TextIO,
    TypeVar,
    Union,
)
from datetime import datetime
from functools import wraps
from contextlib import contextmanager
from enum import Enum

T = TypeVar('T')

# Context variable for log context
_log_context: contextvars.ContextVar[Dict[str, Any]] = contextvars.ContextVar(
    'log_context',
    default={},
)

# Context variable for correlation ID
_correlation_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    'correlation_id',
    default=None,
)


class LogLevel(str, Enum):
    """Log levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    
    def to_int(self) -> int:
        """Convert to logging level int."""
        return {
            LogLevel.DEBUG: logging.DEBUG,
            LogLevel.INFO: logging.INFO,
            LogLevel.WARNING: logging.WARNING,
            LogLevel.ERROR: logging.ERROR,
            LogLevel.CRITICAL: logging.CRITICAL,
        }[self]


@dataclass
class LogRecord:
    """A structured log record."""
    timestamp: str
    level: str
    logger: str
    message: str
    correlation_id: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    exception: Optional[str] = None
    duration_ms: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = asdict(self)
        # Remove None values
        return {k: v for k, v in result.items() if v is not None}
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())


class LogFormatter(ABC):
    """Abstract log formatter."""
    
    @abstractmethod
    def format(self, record: LogRecord) -> str:
        """Format a log record."""
        pass


class JSONFormatter(LogFormatter):
    """JSON log formatter."""
    
    def __init__(self, indent: Optional[int] = None):
        self.indent = indent
    
    def format(self, record: LogRecord) -> str:
        """Format as JSON."""
        return json.dumps(record.to_dict(), indent=self.indent, default=str)


class TextFormatter(LogFormatter):
    """Human-readable text formatter."""
    
    def __init__(
        self,
        format_string: str = "{timestamp} [{level}] {logger}: {message}",
        include_context: bool = True,
    ):
        self.format_string = format_string
        self.include_context = include_context
    
    def format(self, record: LogRecord) -> str:
        """Format as text."""
        base = self.format_string.format(**record.to_dict())
        
        if self.include_context and record.context:
            context_str = " ".join(f"{k}={v}" for k, v in record.context.items())
            base = f"{base} [{context_str}]"
        
        if record.exception:
            base = f"{base}\n{record.exception}"
        
        return base


class ColorFormatter(TextFormatter):
    """Colored text formatter for terminals."""
    
    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"
    
    def format(self, record: LogRecord) -> str:
        """Format with colors."""
        base = super().format(record)
        color = self.COLORS.get(record.level, "")
        return f"{color}{base}{self.RESET}"


class LogSink(ABC):
    """Abstract log sink/output."""
    
    @abstractmethod
    def write(self, record: LogRecord) -> None:
        """Write a log record."""
        pass
    
    def flush(self) -> None:
        """Flush the sink."""
        pass
    
    def close(self) -> None:
        """Close the sink."""
        pass


class ConsoleSink(LogSink):
    """Console log sink."""
    
    def __init__(
        self,
        formatter: Optional[LogFormatter] = None,
        stream: TextIO = sys.stderr,
    ):
        self.formatter = formatter or TextFormatter()
        self.stream = stream
    
    def write(self, record: LogRecord) -> None:
        """Write to console."""
        self.stream.write(self.formatter.format(record) + "\n")
        self.stream.flush()


class FileSink(LogSink):
    """File log sink with rotation support."""
    
    def __init__(
        self,
        filepath: str,
        formatter: Optional[LogFormatter] = None,
        max_size_mb: float = 10.0,
        backup_count: int = 5,
    ):
        self.filepath = filepath
        self.formatter = formatter or JSONFormatter()
        self.max_size_mb = max_size_mb
        self.backup_count = backup_count
        self._file: Optional[TextIO] = None
        self._current_size = 0
    
    def _open(self) -> None:
        """Open the log file."""
        self._file = open(self.filepath, "a", encoding="utf-8")
    
    def _should_rotate(self) -> bool:
        """Check if rotation is needed."""
        return self._current_size >= self.max_size_mb * 1024 * 1024
    
    def _rotate(self) -> None:
        """Rotate log files."""
        if self._file:
            self._file.close()
        
        import os
        import shutil
        
        # Rotate existing files
        for i in range(self.backup_count - 1, 0, -1):
            src = f"{self.filepath}.{i}"
            dst = f"{self.filepath}.{i + 1}"
            if os.path.exists(src):
                shutil.move(src, dst)
        
        # Move current file
        if os.path.exists(self.filepath):
            shutil.move(self.filepath, f"{self.filepath}.1")
        
        self._current_size = 0
        self._open()
    
    def write(self, record: LogRecord) -> None:
        """Write to file."""
        if self._file is None:
            self._open()
        
        if self._should_rotate():
            self._rotate()
        
        line = self.formatter.format(record) + "\n"
        self._file.write(line)
        self._current_size += len(line.encode())
    
    def flush(self) -> None:
        """Flush the file."""
        if self._file:
            self._file.flush()
    
    def close(self) -> None:
        """Close the file."""
        if self._file:
            self._file.close()
            self._file = None


class MemorySink(LogSink):
    """In-memory log sink for testing."""
    
    def __init__(self, max_records: int = 1000):
        self.records: List[LogRecord] = []
        self.max_records = max_records
    
    def write(self, record: LogRecord) -> None:
        """Store in memory."""
        self.records.append(record)
        if len(self.records) > self.max_records:
            self.records = self.records[-self.max_records:]
    
    def clear(self) -> None:
        """Clear records."""
        self.records.clear()
    
    def search(
        self,
        level: Optional[str] = None,
        message_contains: Optional[str] = None,
        context_key: Optional[str] = None,
    ) -> List[LogRecord]:
        """Search records."""
        results = self.records
        
        if level:
            results = [r for r in results if r.level == level]
        
        if message_contains:
            results = [r for r in results if message_contains in r.message]
        
        if context_key:
            results = [r for r in results if context_key in r.context]
        
        return results


class AggregateSink(LogSink):
    """Aggregate multiple sinks."""
    
    def __init__(self, sinks: Optional[List[LogSink]] = None):
        self.sinks = sinks or []
    
    def add(self, sink: LogSink) -> 'AggregateSink':
        """Add a sink."""
        self.sinks.append(sink)
        return self
    
    def write(self, record: LogRecord) -> None:
        """Write to all sinks."""
        for sink in self.sinks:
            try:
                sink.write(record)
            except Exception:
                pass  # Don't fail on sink errors
    
    def flush(self) -> None:
        """Flush all sinks."""
        for sink in self.sinks:
            sink.flush()
    
    def close(self) -> None:
        """Close all sinks."""
        for sink in self.sinks:
            sink.close()


class FilteredSink(LogSink):
    """Sink with filtering."""
    
    def __init__(
        self,
        sink: LogSink,
        min_level: LogLevel = LogLevel.DEBUG,
        include_loggers: Optional[List[str]] = None,
        exclude_loggers: Optional[List[str]] = None,
    ):
        self.sink = sink
        self.min_level = min_level
        self.include_loggers = include_loggers
        self.exclude_loggers = exclude_loggers
    
    def _should_log(self, record: LogRecord) -> bool:
        """Check if record should be logged."""
        # Check level
        level = LogLevel(record.level)
        if level.to_int() < self.min_level.to_int():
            return False
        
        # Check logger inclusion
        if self.include_loggers:
            if not any(record.logger.startswith(l) for l in self.include_loggers):
                return False
        
        # Check logger exclusion
        if self.exclude_loggers:
            if any(record.logger.startswith(l) for l in self.exclude_loggers):
                return False
        
        return True
    
    def write(self, record: LogRecord) -> None:
        """Write if passes filter."""
        if self._should_log(record):
            self.sink.write(record)


class StructuredLogger:
    """
    Structured logger with context support.
    """
    
    def __init__(
        self,
        name: str,
        sink: Optional[LogSink] = None,
        min_level: LogLevel = LogLevel.DEBUG,
    ):
        """
        Initialize structured logger.
        
        Args:
            name: Logger name
            sink: Log sink
            min_level: Minimum log level
        """
        self.name = name
        self.sink = sink or ConsoleSink(TextFormatter())
        self.min_level = min_level
    
    def _create_record(
        self,
        level: LogLevel,
        message: str,
        exc_info: Optional[Exception] = None,
        duration_ms: Optional[float] = None,
        **kwargs: Any,
    ) -> LogRecord:
        """Create a log record."""
        # Get context
        context = {**_log_context.get(), **kwargs}
        
        # Get correlation ID
        correlation_id = _correlation_id.get()
        
        # Format exception
        exception = None
        if exc_info:
            exception = "".join(traceback.format_exception(
                type(exc_info), exc_info, exc_info.__traceback__
            ))
        
        return LogRecord(
            timestamp=datetime.now().isoformat(),
            level=level.value,
            logger=self.name,
            message=message,
            correlation_id=correlation_id,
            context=context,
            exception=exception,
            duration_ms=duration_ms,
        )
    
    def _log(
        self,
        level: LogLevel,
        message: str,
        exc_info: Optional[Exception] = None,
        **kwargs: Any,
    ) -> None:
        """Log a message."""
        if level.to_int() < self.min_level.to_int():
            return
        
        record = self._create_record(level, message, exc_info, **kwargs)
        self.sink.write(record)
    
    def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message."""
        self._log(LogLevel.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs: Any) -> None:
        """Log info message."""
        self._log(LogLevel.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message."""
        self._log(LogLevel.WARNING, message, **kwargs)
    
    def error(self, message: str, exc_info: Optional[Exception] = None, **kwargs: Any) -> None:
        """Log error message."""
        self._log(LogLevel.ERROR, message, exc_info, **kwargs)
    
    def critical(self, message: str, exc_info: Optional[Exception] = None, **kwargs: Any) -> None:
        """Log critical message."""
        self._log(LogLevel.CRITICAL, message, exc_info, **kwargs)
    
    def exception(self, message: str, exc: Exception, **kwargs: Any) -> None:
        """Log exception."""
        self.error(message, exc_info=exc, **kwargs)
    
    @contextmanager
    def timed(self, operation: str, level: LogLevel = LogLevel.INFO, **kwargs: Any):
        """
        Context manager to log operation duration.
        
        Example:
            with logger.timed("process_request"):
                process()
        """
        start = time.time()
        try:
            yield
        finally:
            duration_ms = (time.time() - start) * 1000
            record = self._create_record(
                level,
                f"{operation} completed",
                duration_ms=duration_ms,
                **kwargs,
            )
            self.sink.write(record)
    
    def child(self, name: str) -> 'StructuredLogger':
        """Create a child logger."""
        return StructuredLogger(
            f"{self.name}.{name}",
            self.sink,
            self.min_level,
        )


# Logger registry
_loggers: Dict[str, StructuredLogger] = {}
_default_sink: Optional[LogSink] = None
_default_level: LogLevel = LogLevel.INFO


def configure_logging(
    sink: Optional[LogSink] = None,
    level: LogLevel = LogLevel.INFO,
) -> None:
    """
    Configure global logging settings.
    
    Args:
        sink: Default sink for new loggers
        level: Default minimum level
    """
    global _default_sink, _default_level
    _default_sink = sink
    _default_level = level


def get_structured_logger(name: str) -> StructuredLogger:
    """
    Get or create a structured logger.
    
    Args:
        name: Logger name
        
    Returns:
        StructuredLogger instance
    """
    if name not in _loggers:
        sink = _default_sink or ConsoleSink(ColorFormatter())
        _loggers[name] = StructuredLogger(name, sink, _default_level)
    
    return _loggers[name]


@contextmanager
def log_context(**kwargs: Any):
    """
    Context manager to add logging context.
    
    Example:
        with log_context(request_id="123", user="alice"):
            logger.info("Processing")  # Includes request_id and user
    """
    current = _log_context.get()
    new_context = {**current, **kwargs}
    token = _log_context.set(new_context)
    try:
        yield
    finally:
        _log_context.reset(token)


@contextmanager
def correlation_context(correlation_id: Optional[str] = None):
    """
    Context manager for correlation ID.
    
    Example:
        with correlation_context("req-123"):
            logger.info("Request received")  # Includes correlation_id
    """
    if correlation_id is None:
        correlation_id = str(uuid.uuid4())
    
    token = _correlation_id.set(correlation_id)
    try:
        yield correlation_id
    finally:
        _correlation_id.reset(token)


def get_correlation_id() -> Optional[str]:
    """Get current correlation ID."""
    return _correlation_id.get()


def set_correlation_id(correlation_id: str) -> None:
    """Set correlation ID."""
    _correlation_id.set(correlation_id)


def log_calls(
    level: Union[str, LogLevel] = LogLevel.INFO,
    include_args: bool = False,
    include_result: bool = False,
    logger_name: Optional[str] = None,
) -> Callable:
    """
    Decorator to log function calls.
    
    Example:
        @log_calls(level="INFO", include_args=True)
        async def process_request(data):
            ...
    """
    if isinstance(level, str):
        level = LogLevel(level)
    
    def decorator(func: Callable) -> Callable:
        log_name = logger_name or func.__module__
        logger = get_structured_logger(log_name)
        
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            extra = {"function": func.__name__}
            
            if include_args:
                extra["args"] = str(args)[:100]
                extra["kwargs"] = str(kwargs)[:100]
            
            logger._log(level, f"Calling {func.__name__}", **extra)
            
            start = time.time()
            try:
                result = await func(*args, **kwargs)
                
                duration_ms = (time.time() - start) * 1000
                result_extra = {"duration_ms": duration_ms}
                
                if include_result:
                    result_extra["result"] = str(result)[:100]
                
                logger._log(level, f"Completed {func.__name__}", **result_extra)
                return result
                
            except Exception as e:
                duration_ms = (time.time() - start) * 1000
                logger.exception(
                    f"Failed {func.__name__}",
                    e,
                    duration_ms=duration_ms,
                    function=func.__name__,
                )
                raise
        
        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            extra = {"function": func.__name__}
            
            if include_args:
                extra["args"] = str(args)[:100]
                extra["kwargs"] = str(kwargs)[:100]
            
            logger._log(level, f"Calling {func.__name__}", **extra)
            
            start = time.time()
            try:
                result = func(*args, **kwargs)
                
                duration_ms = (time.time() - start) * 1000
                result_extra = {"duration_ms": duration_ms}
                
                if include_result:
                    result_extra["result"] = str(result)[:100]
                
                logger._log(level, f"Completed {func.__name__}", **result_extra)
                return result
                
            except Exception as e:
                duration_ms = (time.time() - start) * 1000
                logger.exception(
                    f"Failed {func.__name__}",
                    e,
                    duration_ms=duration_ms,
                    function=func.__name__,
                )
                raise
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


def log_errors(
    logger_name: Optional[str] = None,
    reraise: bool = True,
) -> Callable:
    """
    Decorator to log exceptions.
    
    Example:
        @log_errors()
        async def risky_operation():
            ...
    """
    def decorator(func: Callable) -> Callable:
        log_name = logger_name or func.__module__
        logger = get_structured_logger(log_name)
        
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.exception(
                    f"Exception in {func.__name__}",
                    e,
                    function=func.__name__,
                )
                if reraise:
                    raise
                return None
        
        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.exception(
                    f"Exception in {func.__name__}",
                    e,
                    function=func.__name__,
                )
                if reraise:
                    raise
                return None
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


class StandardLibraryAdapter(logging.Handler):
    """
    Adapter to use structured logger with standard library logging.
    """
    
    def __init__(self, sink: LogSink, level: int = logging.DEBUG):
        super().__init__(level)
        self.sink = sink
    
    def emit(self, record: logging.LogRecord) -> None:
        """Emit a standard library log record."""
        log_record = LogRecord(
            timestamp=datetime.fromtimestamp(record.created).isoformat(),
            level=record.levelname,
            logger=record.name,
            message=record.getMessage(),
            correlation_id=_correlation_id.get(),
            context=_log_context.get(),
            exception=self.format_exception(record) if record.exc_info else None,
        )
        self.sink.write(log_record)
    
    def format_exception(self, record: logging.LogRecord) -> str:
        """Format exception info."""
        if record.exc_info:
            return "".join(traceback.format_exception(*record.exc_info))
        return ""


def setup_stdlib_integration(sink: Optional[LogSink] = None) -> None:
    """
    Integrate structured logging with standard library.
    
    This redirects all standard library logging to the structured sink.
    """
    sink = sink or ConsoleSink(JSONFormatter())
    handler = StandardLibraryAdapter(sink)
    
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)


__all__ = [
    # Enums
    "LogLevel",
    # Data classes
    "LogRecord",
    # Formatters
    "LogFormatter",
    "JSONFormatter",
    "TextFormatter",
    "ColorFormatter",
    # Sinks
    "LogSink",
    "ConsoleSink",
    "FileSink",
    "MemorySink",
    "AggregateSink",
    "FilteredSink",
    # Logger
    "StructuredLogger",
    # Configuration
    "configure_logging",
    "get_structured_logger",
    # Context
    "log_context",
    "correlation_context",
    "get_correlation_id",
    "set_correlation_id",
    # Decorators
    "log_calls",
    "log_errors",
    # Integration
    "StandardLibraryAdapter",
    "setup_stdlib_integration",
]
