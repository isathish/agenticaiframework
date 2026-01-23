"""
Enterprise Logging Facade Module.

Provides structured logging, context enrichment, log aggregation,
formatters, and log routing.

Example:
    # Create logger
    log = create_logger("my-service")
    
    # Structured logging
    log.info("User logged in", user_id=123, ip="192.168.1.1")
    
    # Context enrichment
    with log.context(request_id="abc-123"):
        log.info("Processing request")
    
    # Use decorator
    @logged()
    async def process_data(data):
        return transform(data)
"""

from __future__ import annotations

import asyncio
import contextvars
import functools
import json
import logging
import sys
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from io import StringIO
from typing import (
    Any,
    Callable,
    ContextManager,
    Dict,
    List,
    Optional,
    TextIO,
    Type,
    TypeVar,
    Union,
)

T = TypeVar('T')


# Context variable for log context
_log_context: contextvars.ContextVar[Dict[str, Any]] = contextvars.ContextVar(
    'log_context', default={}
)


class LogLevel(str, Enum):
    """Log level."""
    TRACE = "trace"
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    
    def to_python_level(self) -> int:
        """Convert to Python logging level."""
        mapping = {
            LogLevel.TRACE: 5,
            LogLevel.DEBUG: logging.DEBUG,
            LogLevel.INFO: logging.INFO,
            LogLevel.WARNING: logging.WARNING,
            LogLevel.ERROR: logging.ERROR,
            LogLevel.CRITICAL: logging.CRITICAL,
        }
        return mapping[self]


class OutputFormat(str, Enum):
    """Log output format."""
    TEXT = "text"
    JSON = "json"
    COMPACT = "compact"
    PRETTY = "pretty"


@dataclass
class LogRecord:
    """Structured log record."""
    timestamp: datetime
    level: LogLevel
    message: str
    logger_name: str
    context: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)
    exception: Optional[str] = None
    stack_trace: Optional[str] = None
    source_file: Optional[str] = None
    source_line: Optional[int] = None
    function_name: Optional[str] = None
    thread_id: Optional[int] = None
    process_id: Optional[int] = None


@dataclass
class LoggerConfig:
    """Logger configuration."""
    name: str
    level: LogLevel = LogLevel.INFO
    format: OutputFormat = OutputFormat.TEXT
    include_timestamp: bool = True
    include_level: bool = True
    include_source: bool = False
    include_thread: bool = False
    include_process: bool = False
    propagate: bool = True


class LogFormatter(ABC):
    """Abstract log formatter."""
    
    @abstractmethod
    def format(self, record: LogRecord) -> str:
        """Format a log record."""
        pass


class TextFormatter(LogFormatter):
    """Plain text formatter."""
    
    def __init__(
        self,
        template: Optional[str] = None,
        timestamp_format: str = "%Y-%m-%d %H:%M:%S",
    ):
        self._template = template or "{timestamp} [{level}] {name}: {message}"
        self._timestamp_format = timestamp_format
    
    def format(self, record: LogRecord) -> str:
        parts = {
            "timestamp": record.timestamp.strftime(self._timestamp_format),
            "level": record.level.value.upper(),
            "name": record.logger_name,
            "message": record.message,
        }
        
        result = self._template.format(**parts)
        
        # Add extra fields
        if record.extra:
            extra_str = " ".join(f"{k}={v}" for k, v in record.extra.items())
            result = f"{result} | {extra_str}"
        
        # Add context
        if record.context:
            ctx_str = " ".join(f"{k}={v}" for k, v in record.context.items())
            result = f"{result} | ctx: {ctx_str}"
        
        # Add exception
        if record.exception:
            result = f"{result}\n{record.exception}"
        
        return result


class JsonFormatter(LogFormatter):
    """JSON formatter."""
    
    def __init__(self, pretty: bool = False):
        self._pretty = pretty
    
    def format(self, record: LogRecord) -> str:
        data = {
            "timestamp": record.timestamp.isoformat(),
            "level": record.level.value,
            "logger": record.logger_name,
            "message": record.message,
        }
        
        if record.context:
            data["context"] = record.context
        
        if record.extra:
            data["extra"] = record.extra
        
        if record.exception:
            data["exception"] = record.exception
            if record.stack_trace:
                data["stack_trace"] = record.stack_trace
        
        if record.source_file:
            data["source"] = {
                "file": record.source_file,
                "line": record.source_line,
                "function": record.function_name,
            }
        
        if self._pretty:
            return json.dumps(data, indent=2, default=str)
        return json.dumps(data, default=str)


class CompactFormatter(LogFormatter):
    """Compact formatter."""
    
    def format(self, record: LogRecord) -> str:
        level_char = record.level.value[0].upper()
        return f"{level_char} {record.message}"


class LogHandler(ABC):
    """Abstract log handler."""
    
    @abstractmethod
    def handle(self, record: LogRecord) -> None:
        """Handle a log record."""
        pass
    
    def flush(self) -> None:
        """Flush the handler."""
        pass
    
    def close(self) -> None:
        """Close the handler."""
        pass


class StreamHandler(LogHandler):
    """Stream handler."""
    
    def __init__(
        self,
        stream: Optional[TextIO] = None,
        formatter: Optional[LogFormatter] = None,
    ):
        self._stream = stream or sys.stdout
        self._formatter = formatter or TextFormatter()
    
    def handle(self, record: LogRecord) -> None:
        formatted = self._formatter.format(record)
        self._stream.write(formatted + "\n")
    
    def flush(self) -> None:
        self._stream.flush()


class FileHandler(LogHandler):
    """File handler."""
    
    def __init__(
        self,
        filename: str,
        formatter: Optional[LogFormatter] = None,
        mode: str = "a",
        encoding: str = "utf-8",
    ):
        self._filename = filename
        self._formatter = formatter or TextFormatter()
        self._file = open(filename, mode, encoding=encoding)
    
    def handle(self, record: LogRecord) -> None:
        formatted = self._formatter.format(record)
        self._file.write(formatted + "\n")
    
    def flush(self) -> None:
        self._file.flush()
    
    def close(self) -> None:
        self._file.close()


class BufferingHandler(LogHandler):
    """Handler that buffers records."""
    
    def __init__(
        self,
        capacity: int = 1000,
        target: Optional[LogHandler] = None,
        flush_level: LogLevel = LogLevel.ERROR,
    ):
        self._capacity = capacity
        self._target = target
        self._flush_level = flush_level
        self._buffer: List[LogRecord] = []
    
    def handle(self, record: LogRecord) -> None:
        self._buffer.append(record)
        
        if len(self._buffer) >= self._capacity:
            self.flush()
        elif record.level.to_python_level() >= self._flush_level.to_python_level():
            self.flush()
    
    def flush(self) -> None:
        if self._target:
            for record in self._buffer:
                self._target.handle(record)
            self._target.flush()
        self._buffer.clear()


class FilteringHandler(LogHandler):
    """Handler with filtering."""
    
    def __init__(
        self,
        target: LogHandler,
        filter_fn: Callable[[LogRecord], bool],
    ):
        self._target = target
        self._filter = filter_fn
    
    def handle(self, record: LogRecord) -> None:
        if self._filter(record):
            self._target.handle(record)
    
    def flush(self) -> None:
        self._target.flush()
    
    def close(self) -> None:
        self._target.close()


class AsyncHandler(LogHandler):
    """Async handler for non-blocking logging."""
    
    def __init__(self, target: LogHandler, queue_size: int = 10000):
        self._target = target
        self._queue: asyncio.Queue[Optional[LogRecord]] = asyncio.Queue(maxsize=queue_size)
        self._task: Optional[asyncio.Task] = None
        self._running = False
    
    async def start(self) -> None:
        """Start async processing."""
        self._running = True
        self._task = asyncio.create_task(self._process_queue())
    
    async def stop(self) -> None:
        """Stop async processing."""
        self._running = False
        await self._queue.put(None)
        if self._task:
            await self._task
    
    def handle(self, record: LogRecord) -> None:
        try:
            self._queue.put_nowait(record)
        except asyncio.QueueFull:
            # Drop record if queue is full
            pass
    
    async def _process_queue(self) -> None:
        while self._running:
            record = await self._queue.get()
            if record is None:
                break
            self._target.handle(record)
    
    def flush(self) -> None:
        self._target.flush()
    
    def close(self) -> None:
        self._target.close()


class LoggerContext:
    """Context manager for adding context to logs."""
    
    def __init__(self, **context):
        self._context = context
        self._token: Optional[contextvars.Token] = None
    
    def __enter__(self) -> "LoggerContext":
        current = _log_context.get().copy()
        current.update(self._context)
        self._token = _log_context.set(current)
        return self
    
    def __exit__(self, *args) -> None:
        if self._token:
            _log_context.reset(self._token)


class Logger:
    """
    Structured logger with context support.
    """
    
    def __init__(self, name: str, config: Optional[LoggerConfig] = None):
        self._name = name
        self._config = config or LoggerConfig(name=name)
        self._handlers: List[LogHandler] = []
        self._level = self._config.level
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def level(self) -> LogLevel:
        return self._level
    
    @level.setter
    def level(self, value: LogLevel) -> None:
        self._level = value
    
    def add_handler(self, handler: LogHandler) -> None:
        """Add a handler."""
        self._handlers.append(handler)
    
    def remove_handler(self, handler: LogHandler) -> None:
        """Remove a handler."""
        self._handlers.remove(handler)
    
    def context(self, **kwargs) -> LoggerContext:
        """Create a context manager for adding context."""
        return LoggerContext(**kwargs)
    
    def _should_log(self, level: LogLevel) -> bool:
        """Check if should log at level."""
        return level.to_python_level() >= self._level.to_python_level()
    
    def _create_record(
        self,
        level: LogLevel,
        message: str,
        exception: Optional[Exception] = None,
        **extra,
    ) -> LogRecord:
        """Create a log record."""
        # Get caller info
        source_file = None
        source_line = None
        function_name = None
        
        if self._config.include_source:
            import inspect
            frame = inspect.currentframe()
            if frame:
                # Go up the stack to find the actual caller
                for _ in range(3):
                    if frame.f_back:
                        frame = frame.f_back
                source_file = frame.f_code.co_filename
                source_line = frame.f_lineno
                function_name = frame.f_code.co_name
        
        # Get exception info
        exc_str = None
        stack_trace = None
        if exception:
            exc_str = str(exception)
            stack_trace = traceback.format_exc()
        
        return LogRecord(
            timestamp=datetime.utcnow(),
            level=level,
            message=message,
            logger_name=self._name,
            context=_log_context.get().copy(),
            extra=extra,
            exception=exc_str,
            stack_trace=stack_trace,
            source_file=source_file,
            source_line=source_line,
            function_name=function_name,
        )
    
    def _log(
        self,
        level: LogLevel,
        message: str,
        exception: Optional[Exception] = None,
        **extra,
    ) -> None:
        """Log a message."""
        if not self._should_log(level):
            return
        
        record = self._create_record(level, message, exception, **extra)
        
        for handler in self._handlers:
            handler.handle(record)
    
    def trace(self, message: str, **extra) -> None:
        """Log trace message."""
        self._log(LogLevel.TRACE, message, **extra)
    
    def debug(self, message: str, **extra) -> None:
        """Log debug message."""
        self._log(LogLevel.DEBUG, message, **extra)
    
    def info(self, message: str, **extra) -> None:
        """Log info message."""
        self._log(LogLevel.INFO, message, **extra)
    
    def warning(self, message: str, **extra) -> None:
        """Log warning message."""
        self._log(LogLevel.WARNING, message, **extra)
    
    def error(self, message: str, exception: Optional[Exception] = None, **extra) -> None:
        """Log error message."""
        self._log(LogLevel.ERROR, message, exception, **extra)
    
    def critical(self, message: str, exception: Optional[Exception] = None, **extra) -> None:
        """Log critical message."""
        self._log(LogLevel.CRITICAL, message, exception, **extra)
    
    def exception(self, message: str, exception: Exception, **extra) -> None:
        """Log exception with stack trace."""
        self.error(message, exception=exception, **extra)
    
    def bind(self, **context) -> "BoundLogger":
        """Create a bound logger with context."""
        return BoundLogger(self, context)


class BoundLogger:
    """Logger with bound context."""
    
    def __init__(self, logger: Logger, context: Dict[str, Any]):
        self._logger = logger
        self._context = context
    
    def _merge_extra(self, extra: Dict[str, Any]) -> Dict[str, Any]:
        merged = self._context.copy()
        merged.update(extra)
        return merged
    
    def trace(self, message: str, **extra) -> None:
        self._logger.trace(message, **self._merge_extra(extra))
    
    def debug(self, message: str, **extra) -> None:
        self._logger.debug(message, **self._merge_extra(extra))
    
    def info(self, message: str, **extra) -> None:
        self._logger.info(message, **self._merge_extra(extra))
    
    def warning(self, message: str, **extra) -> None:
        self._logger.warning(message, **self._merge_extra(extra))
    
    def error(self, message: str, exception: Optional[Exception] = None, **extra) -> None:
        self._logger.error(message, exception=exception, **self._merge_extra(extra))
    
    def critical(self, message: str, exception: Optional[Exception] = None, **extra) -> None:
        self._logger.critical(message, exception=exception, **self._merge_extra(extra))
    
    def bind(self, **context) -> "BoundLogger":
        merged = self._context.copy()
        merged.update(context)
        return BoundLogger(self._logger, merged)


class LoggerFactory:
    """Factory for creating loggers."""
    
    def __init__(self):
        self._loggers: Dict[str, Logger] = {}
        self._default_config = LoggerConfig(name="default")
        self._default_handlers: List[LogHandler] = []
    
    def set_default_config(self, config: LoggerConfig) -> None:
        """Set default configuration."""
        self._default_config = config
    
    def add_default_handler(self, handler: LogHandler) -> None:
        """Add default handler for all loggers."""
        self._default_handlers.append(handler)
    
    def get_logger(self, name: str) -> Logger:
        """Get or create logger."""
        if name not in self._loggers:
            config = LoggerConfig(
                name=name,
                level=self._default_config.level,
                format=self._default_config.format,
            )
            logger = Logger(name, config)
            
            # Add default handlers
            for handler in self._default_handlers:
                logger.add_handler(handler)
            
            self._loggers[name] = logger
        
        return self._loggers[name]
    
    def configure_all(self, level: LogLevel) -> None:
        """Configure all loggers."""
        for logger in self._loggers.values():
            logger.level = level


# Global factory
_global_factory = LoggerFactory()


# Decorators
def logged(
    level: LogLevel = LogLevel.DEBUG,
    include_args: bool = True,
    include_result: bool = False,
    logger_name: Optional[str] = None,
) -> Callable:
    """
    Decorator to log function calls.
    
    Example:
        @logged()
        async def process_data(data):
            return data
    """
    def decorator(func: Callable) -> Callable:
        name = logger_name or func.__module__
        log = get_logger(name)
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            extra = {}
            if include_args:
                extra["args"] = str(args)[:100]
                extra["kwargs"] = str(kwargs)[:100]
            
            log._log(level, f"Entering {func.__name__}", **extra)
            
            try:
                result = await func(*args, **kwargs)
                
                if include_result:
                    log._log(level, f"Exiting {func.__name__}", result=str(result)[:100])
                else:
                    log._log(level, f"Exiting {func.__name__}")
                
                return result
                
            except Exception as e:
                log.error(f"Error in {func.__name__}", exception=e)
                raise
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            extra = {}
            if include_args:
                extra["args"] = str(args)[:100]
                extra["kwargs"] = str(kwargs)[:100]
            
            log._log(level, f"Entering {func.__name__}", **extra)
            
            try:
                result = func(*args, **kwargs)
                
                if include_result:
                    log._log(level, f"Exiting {func.__name__}", result=str(result)[:100])
                else:
                    log._log(level, f"Exiting {func.__name__}")
                
                return result
                
            except Exception as e:
                log.error(f"Error in {func.__name__}", exception=e)
                raise
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


def with_context(**context) -> Callable:
    """
    Decorator to add context to all logs in function.
    
    Example:
        @with_context(component="auth")
        async def authenticate(user):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            with LoggerContext(**context):
                return await func(*args, **kwargs)
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            with LoggerContext(**context):
                return func(*args, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


# Factory functions
def create_logger(
    name: str,
    level: LogLevel = LogLevel.INFO,
    format: OutputFormat = OutputFormat.TEXT,
) -> Logger:
    """Create a logger."""
    config = LoggerConfig(name=name, level=level, format=format)
    logger = Logger(name, config)
    
    # Add default stream handler
    formatter = TextFormatter() if format == OutputFormat.TEXT else JsonFormatter()
    logger.add_handler(StreamHandler(formatter=formatter))
    
    return logger


def create_text_formatter(
    template: Optional[str] = None,
    timestamp_format: str = "%Y-%m-%d %H:%M:%S",
) -> TextFormatter:
    """Create text formatter."""
    return TextFormatter(template, timestamp_format)


def create_json_formatter(pretty: bool = False) -> JsonFormatter:
    """Create JSON formatter."""
    return JsonFormatter(pretty)


def create_stream_handler(
    stream: Optional[TextIO] = None,
    formatter: Optional[LogFormatter] = None,
) -> StreamHandler:
    """Create stream handler."""
    return StreamHandler(stream, formatter)


def create_file_handler(
    filename: str,
    formatter: Optional[LogFormatter] = None,
) -> FileHandler:
    """Create file handler."""
    return FileHandler(filename, formatter)


def get_logger(name: str) -> Logger:
    """Get logger from global factory."""
    return _global_factory.get_logger(name)


def configure_logging(
    level: LogLevel = LogLevel.INFO,
    format: OutputFormat = OutputFormat.TEXT,
) -> None:
    """Configure global logging."""
    formatter = TextFormatter() if format == OutputFormat.TEXT else JsonFormatter()
    _global_factory.add_default_handler(StreamHandler(formatter=formatter))
    _global_factory.set_default_config(LoggerConfig(name="default", level=level, format=format))


__all__ = [
    # Enums
    "LogLevel",
    "OutputFormat",
    # Data classes
    "LogRecord",
    "LoggerConfig",
    # Formatters
    "LogFormatter",
    "TextFormatter",
    "JsonFormatter",
    "CompactFormatter",
    # Handlers
    "LogHandler",
    "StreamHandler",
    "FileHandler",
    "BufferingHandler",
    "FilteringHandler",
    "AsyncHandler",
    # Context
    "LoggerContext",
    # Logger
    "Logger",
    "BoundLogger",
    "LoggerFactory",
    # Decorators
    "logged",
    "with_context",
    # Factory functions
    "create_logger",
    "create_text_formatter",
    "create_json_formatter",
    "create_stream_handler",
    "create_file_handler",
    "get_logger",
    "configure_logging",
]
