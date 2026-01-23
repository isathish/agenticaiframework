"""
Enterprise Log Aggregator Module.

Centralized logging, log search,
retention policies, and log analysis.

Example:
    # Create log aggregator
    aggregator = create_log_aggregator()
    
    # Log events
    aggregator.log("User logged in", level=LogLevel.INFO, user_id="123")
    aggregator.error("Database connection failed", error=e)
    
    # Search logs
    results = await aggregator.search(
        query="error",
        level=LogLevel.ERROR,
        start_time=datetime.now() - timedelta(hours=1),
    )
    
    # Export logs
    await aggregator.export("json", output_path="/logs/export.json")
"""

from __future__ import annotations

import asyncio
import functools
import gzip
import json
import logging
import os
import re
import uuid
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Callable,
    Deque,
    Dict,
    Generic,
    Iterator,
    List,
    Optional,
    Pattern,
    Set,
    TextIO,
    Tuple,
    TypeVar,
    Union,
)

T = TypeVar('T')


logger = logging.getLogger(__name__)


class LoggingError(Exception):
    """Logging error."""
    pass


class LogLevel(str, Enum):
    """Log levels."""
    TRACE = "trace"
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class LogFormat(str, Enum):
    """Log formats."""
    JSON = "json"
    TEXT = "text"
    CSV = "csv"
    NDJSON = "ndjson"


LOG_LEVEL_VALUES = {
    LogLevel.TRACE: 5,
    LogLevel.DEBUG: 10,
    LogLevel.INFO: 20,
    LogLevel.WARNING: 30,
    LogLevel.ERROR: 40,
    LogLevel.CRITICAL: 50,
}


@dataclass
class LogEntry:
    """Log entry."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    level: LogLevel = LogLevel.INFO
    message: str = ""
    logger_name: str = "default"
    source: Optional[str] = None
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    host: Optional[str] = None
    service: Optional[str] = None
    environment: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    exception: Optional[str] = None
    stack_trace: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "level": self.level.value,
            "message": self.message,
            "logger_name": self.logger_name,
            "source": self.source,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "host": self.host,
            "service": self.service,
            "environment": self.environment,
            "context": self.context,
            "exception": self.exception,
            "stack_trace": self.stack_trace,
            "tags": self.tags,
        }
    
    def to_text(self) -> str:
        """Convert to text format."""
        ctx = " ".join(f"{k}={v}" for k, v in self.context.items())
        return f"{self.timestamp.isoformat()} [{self.level.value.upper()}] {self.message} {ctx}".strip()


@dataclass
class LogQuery:
    """Log query parameters."""
    query: Optional[str] = None
    level: Optional[LogLevel] = None
    min_level: Optional[LogLevel] = None
    logger_name: Optional[str] = None
    service: Optional[str] = None
    trace_id: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    tags: Optional[List[str]] = None
    context_filter: Optional[Dict[str, Any]] = None
    limit: int = 100
    offset: int = 0


@dataclass
class LogStats:
    """Log statistics."""
    total_entries: int = 0
    entries_by_level: Dict[str, int] = field(default_factory=dict)
    entries_by_service: Dict[str, int] = field(default_factory=dict)
    entries_by_logger: Dict[str, int] = field(default_factory=dict)
    oldest_entry: Optional[datetime] = None
    newest_entry: Optional[datetime] = None
    error_rate: float = 0.0


@dataclass
class RetentionPolicy:
    """Log retention policy."""
    name: str = "default"
    max_age_days: int = 30
    max_size_bytes: int = 1073741824  # 1GB
    compress_after_days: int = 7
    delete_after_days: Optional[int] = None
    archive_path: Optional[str] = None


# Log storage
class LogStorage(ABC):
    """Abstract log storage."""
    
    @abstractmethod
    async def write(self, entry: LogEntry) -> None:
        """Write log entry."""
        pass
    
    @abstractmethod
    async def write_batch(self, entries: List[LogEntry]) -> None:
        """Write batch of entries."""
        pass
    
    @abstractmethod
    async def search(self, query: LogQuery) -> List[LogEntry]:
        """Search logs."""
        pass
    
    @abstractmethod
    async def count(self, query: Optional[LogQuery] = None) -> int:
        """Count entries."""
        pass
    
    @abstractmethod
    async def delete_before(self, before: datetime) -> int:
        """Delete old entries."""
        pass


class InMemoryLogStorage(LogStorage):
    """In-memory log storage."""
    
    def __init__(self, max_entries: int = 100000):
        self._entries: Deque[LogEntry] = deque(maxlen=max_entries)
        self._max_entries = max_entries
    
    async def write(self, entry: LogEntry) -> None:
        self._entries.append(entry)
    
    async def write_batch(self, entries: List[LogEntry]) -> None:
        for entry in entries:
            self._entries.append(entry)
    
    async def search(self, query: LogQuery) -> List[LogEntry]:
        results = []
        
        for entry in reversed(self._entries):
            if not self._matches_query(entry, query):
                continue
            
            results.append(entry)
            
            if len(results) >= query.offset + query.limit:
                break
        
        return results[query.offset:query.offset + query.limit]
    
    def _matches_query(self, entry: LogEntry, query: LogQuery) -> bool:
        """Check if entry matches query."""
        if query.level and entry.level != query.level:
            return False
        
        if query.min_level:
            entry_val = LOG_LEVEL_VALUES.get(entry.level, 0)
            min_val = LOG_LEVEL_VALUES.get(query.min_level, 0)
            if entry_val < min_val:
                return False
        
        if query.logger_name and entry.logger_name != query.logger_name:
            return False
        
        if query.service and entry.service != query.service:
            return False
        
        if query.trace_id and entry.trace_id != query.trace_id:
            return False
        
        if query.start_time and entry.timestamp < query.start_time:
            return False
        
        if query.end_time and entry.timestamp > query.end_time:
            return False
        
        if query.tags:
            if not all(tag in entry.tags for tag in query.tags):
                return False
        
        if query.query:
            if query.query.lower() not in entry.message.lower():
                return False
        
        if query.context_filter:
            for key, value in query.context_filter.items():
                if entry.context.get(key) != value:
                    return False
        
        return True
    
    async def count(self, query: Optional[LogQuery] = None) -> int:
        if not query:
            return len(self._entries)
        
        count = 0
        for entry in self._entries:
            if self._matches_query(entry, query):
                count += 1
        return count
    
    async def delete_before(self, before: datetime) -> int:
        old_len = len(self._entries)
        self._entries = deque(
            (e for e in self._entries if e.timestamp >= before),
            maxlen=self._max_entries,
        )
        return old_len - len(self._entries)


class FileLogStorage(LogStorage):
    """File-based log storage."""
    
    def __init__(
        self,
        base_path: str = "/var/log/app",
        format: LogFormat = LogFormat.NDJSON,
        rotate_size_mb: int = 100,
    ):
        self._base_path = Path(base_path)
        self._base_path.mkdir(parents=True, exist_ok=True)
        self._format = format
        self._rotate_size = rotate_size_mb * 1024 * 1024
        self._current_file: Optional[TextIO] = None
        self._current_path: Optional[Path] = None
    
    def _get_current_file(self) -> TextIO:
        """Get current log file."""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        path = self._base_path / f"app-{today}.log"
        
        if self._current_path != path:
            if self._current_file:
                self._current_file.close()
            self._current_path = path
            self._current_file = open(path, "a")
        
        # Check rotation
        if path.exists() and path.stat().st_size > self._rotate_size:
            self._rotate_file(path)
        
        return self._current_file
    
    def _rotate_file(self, path: Path) -> None:
        """Rotate log file."""
        if self._current_file:
            self._current_file.close()
        
        # Rename with timestamp
        rotated = path.with_suffix(f".{datetime.utcnow().strftime('%H%M%S')}.log")
        path.rename(rotated)
        
        # Compress old file
        with open(rotated, "rb") as f_in:
            with gzip.open(f"{rotated}.gz", "wb") as f_out:
                f_out.writelines(f_in)
        rotated.unlink()
        
        self._current_file = open(path, "a")
    
    async def write(self, entry: LogEntry) -> None:
        f = self._get_current_file()
        
        if self._format == LogFormat.JSON:
            line = json.dumps(entry.to_dict())
        elif self._format == LogFormat.NDJSON:
            line = json.dumps(entry.to_dict())
        else:
            line = entry.to_text()
        
        f.write(line + "\n")
        f.flush()
    
    async def write_batch(self, entries: List[LogEntry]) -> None:
        for entry in entries:
            await self.write(entry)
    
    async def search(self, query: LogQuery) -> List[LogEntry]:
        results = []
        
        # Search through log files
        for log_file in sorted(self._base_path.glob("*.log"), reverse=True):
            with open(log_file) as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        entry = LogEntry(
                            id=data.get("id", ""),
                            timestamp=datetime.fromisoformat(data["timestamp"]),
                            level=LogLevel(data["level"]),
                            message=data["message"],
                            logger_name=data.get("logger_name", ""),
                            context=data.get("context", {}),
                            tags=data.get("tags", []),
                        )
                        
                        if self._matches_query(entry, query):
                            results.append(entry)
                            if len(results) >= query.limit:
                                return results
                    except:
                        continue
        
        return results
    
    def _matches_query(self, entry: LogEntry, query: LogQuery) -> bool:
        """Check if entry matches query."""
        if query.query and query.query.lower() not in entry.message.lower():
            return False
        if query.level and entry.level != query.level:
            return False
        if query.start_time and entry.timestamp < query.start_time:
            return False
        if query.end_time and entry.timestamp > query.end_time:
            return False
        return True
    
    async def count(self, query: Optional[LogQuery] = None) -> int:
        results = await self.search(LogQuery(limit=100000) if not query else query)
        return len(results)
    
    async def delete_before(self, before: datetime) -> int:
        deleted = 0
        
        for log_file in self._base_path.glob("*.log*"):
            try:
                # Parse date from filename
                date_str = log_file.stem.split("-", 1)[1].split(".")[0]
                file_date = datetime.strptime(date_str, "%Y-%m-%d")
                
                if file_date < before:
                    log_file.unlink()
                    deleted += 1
            except:
                continue
        
        return deleted


# Log aggregator
class LogAggregator:
    """
    Centralized log aggregation service.
    """
    
    def __init__(
        self,
        storage: Optional[LogStorage] = None,
        service_name: str = "app",
        environment: str = "development",
        min_level: LogLevel = LogLevel.DEBUG,
    ):
        self._storage = storage or InMemoryLogStorage()
        self._service = service_name
        self._environment = environment
        self._min_level = min_level
        self._default_context: Dict[str, Any] = {}
        self._processors: List[Callable[[LogEntry], LogEntry]] = []
        self._filters: List[Callable[[LogEntry], bool]] = []
        self._handlers: List[Callable[[LogEntry], None]] = []
        self._batch: List[LogEntry] = []
        self._batch_size = 100
        self._batch_timeout = 5.0
        self._running = False
        self._flush_task: Optional[asyncio.Task] = None
        self._retention = RetentionPolicy()
        
        # Get host info
        import socket
        self._host = socket.gethostname()
    
    def set_context(self, **kwargs) -> None:
        """Set default context."""
        self._default_context.update(kwargs)
    
    def add_processor(
        self,
        processor: Callable[[LogEntry], LogEntry],
    ) -> None:
        """Add log processor."""
        self._processors.append(processor)
    
    def add_filter(
        self,
        filter_fn: Callable[[LogEntry], bool],
    ) -> None:
        """Add log filter."""
        self._filters.append(filter_fn)
    
    def add_handler(
        self,
        handler: Callable[[LogEntry], None],
    ) -> None:
        """Add log handler."""
        self._handlers.append(handler)
    
    def _create_entry(
        self,
        message: str,
        level: LogLevel,
        **kwargs,
    ) -> LogEntry:
        """Create log entry."""
        entry = LogEntry(
            message=message,
            level=level,
            host=self._host,
            service=self._service,
            environment=self._environment,
            context={**self._default_context, **kwargs.pop("context", {})},
            **kwargs,
        )
        
        # Apply processors
        for processor in self._processors:
            entry = processor(entry)
        
        return entry
    
    def _should_log(self, entry: LogEntry) -> bool:
        """Check if entry should be logged."""
        # Check level
        entry_val = LOG_LEVEL_VALUES.get(entry.level, 0)
        min_val = LOG_LEVEL_VALUES.get(self._min_level, 0)
        
        if entry_val < min_val:
            return False
        
        # Apply filters
        for filter_fn in self._filters:
            if not filter_fn(entry):
                return False
        
        return True
    
    async def _write_entry(self, entry: LogEntry) -> None:
        """Write entry to storage."""
        await self._storage.write(entry)
        
        # Call handlers
        for handler in self._handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(entry)
                else:
                    handler(entry)
            except Exception as e:
                logger.error(f"Handler error: {e}")
    
    def log(
        self,
        message: str,
        level: LogLevel = LogLevel.INFO,
        **kwargs,
    ) -> None:
        """
        Log message.
        
        Args:
            message: Log message
            level: Log level
            **kwargs: Additional context
        """
        entry = self._create_entry(message, level, **kwargs)
        
        if not self._should_log(entry):
            return
        
        # Add to batch
        self._batch.append(entry)
        
        # Flush if batch is full
        if len(self._batch) >= self._batch_size:
            asyncio.create_task(self._flush_batch())
    
    def trace(self, message: str, **kwargs) -> None:
        """Log trace message."""
        self.log(message, LogLevel.TRACE, **kwargs)
    
    def debug(self, message: str, **kwargs) -> None:
        """Log debug message."""
        self.log(message, LogLevel.DEBUG, **kwargs)
    
    def info(self, message: str, **kwargs) -> None:
        """Log info message."""
        self.log(message, LogLevel.INFO, **kwargs)
    
    def warning(self, message: str, **kwargs) -> None:
        """Log warning message."""
        self.log(message, LogLevel.WARNING, **kwargs)
    
    def error(
        self,
        message: str,
        exception: Optional[Exception] = None,
        **kwargs,
    ) -> None:
        """Log error message."""
        if exception:
            import traceback
            kwargs["exception"] = str(exception)
            kwargs["stack_trace"] = traceback.format_exc()
        
        self.log(message, LogLevel.ERROR, **kwargs)
    
    def critical(self, message: str, **kwargs) -> None:
        """Log critical message."""
        self.log(message, LogLevel.CRITICAL, **kwargs)
    
    async def _flush_batch(self) -> None:
        """Flush log batch."""
        if not self._batch:
            return
        
        batch = self._batch.copy()
        self._batch.clear()
        
        await self._storage.write_batch(batch)
    
    async def search(
        self,
        query: Optional[str] = None,
        level: Optional[LogLevel] = None,
        min_level: Optional[LogLevel] = None,
        service: Optional[str] = None,
        trace_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[LogEntry]:
        """
        Search logs.
        
        Args:
            query: Search query
            level: Filter by level
            min_level: Minimum level
            service: Filter by service
            trace_id: Filter by trace ID
            start_time: Start time
            end_time: End time
            tags: Filter by tags
            limit: Max results
            offset: Results offset
            
        Returns:
            List of log entries
        """
        log_query = LogQuery(
            query=query,
            level=level,
            min_level=min_level,
            service=service,
            trace_id=trace_id,
            start_time=start_time,
            end_time=end_time,
            tags=tags,
            limit=limit,
            offset=offset,
        )
        
        # Flush pending logs first
        await self._flush_batch()
        
        return await self._storage.search(log_query)
    
    async def export(
        self,
        format: LogFormat = LogFormat.JSON,
        output_path: Optional[str] = None,
        query: Optional[LogQuery] = None,
    ) -> str:
        """
        Export logs.
        
        Args:
            format: Export format
            output_path: Output path
            query: Query filter
            
        Returns:
            Export path or data
        """
        entries = await self._storage.search(
            query or LogQuery(limit=100000)
        )
        
        if format == LogFormat.JSON:
            data = json.dumps(
                [e.to_dict() for e in entries],
                indent=2,
            )
        elif format == LogFormat.NDJSON:
            data = "\n".join(json.dumps(e.to_dict()) for e in entries)
        elif format == LogFormat.CSV:
            lines = ["timestamp,level,message,service"]
            for e in entries:
                msg = e.message.replace(",", ";")
                lines.append(f"{e.timestamp.isoformat()},{e.level.value},{msg},{e.service}")
            data = "\n".join(lines)
        else:
            data = "\n".join(e.to_text() for e in entries)
        
        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w") as f:
                f.write(data)
            return output_path
        
        return data
    
    async def get_stats(self) -> LogStats:
        """Get log statistics."""
        entries = await self._storage.search(LogQuery(limit=10000))
        
        stats = LogStats(total_entries=len(entries))
        
        error_count = 0
        
        for entry in entries:
            level_key = entry.level.value
            stats.entries_by_level[level_key] = (
                stats.entries_by_level.get(level_key, 0) + 1
            )
            
            if entry.service:
                stats.entries_by_service[entry.service] = (
                    stats.entries_by_service.get(entry.service, 0) + 1
                )
            
            stats.entries_by_logger[entry.logger_name] = (
                stats.entries_by_logger.get(entry.logger_name, 0) + 1
            )
            
            if entry.level in (LogLevel.ERROR, LogLevel.CRITICAL):
                error_count += 1
            
            if not stats.oldest_entry or entry.timestamp < stats.oldest_entry:
                stats.oldest_entry = entry.timestamp
            if not stats.newest_entry or entry.timestamp > stats.newest_entry:
                stats.newest_entry = entry.timestamp
        
        if stats.total_entries > 0:
            stats.error_rate = error_count / stats.total_entries * 100
        
        return stats
    
    async def start(self) -> None:
        """Start background tasks."""
        self._running = True
        self._flush_task = asyncio.create_task(self._background_flush())
    
    async def stop(self) -> None:
        """Stop and flush."""
        self._running = False
        await self._flush_batch()
        if self._flush_task:
            self._flush_task.cancel()
    
    async def _background_flush(self) -> None:
        """Background flush loop."""
        while self._running:
            try:
                await asyncio.sleep(self._batch_timeout)
                await self._flush_batch()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Flush error: {e}")
    
    async def apply_retention(self) -> int:
        """Apply retention policy."""
        cutoff = datetime.utcnow() - timedelta(days=self._retention.max_age_days)
        return await self._storage.delete_before(cutoff)


# Decorator for logging
def logged(
    level: LogLevel = LogLevel.INFO,
    message: Optional[str] = None,
) -> Callable:
    """
    Decorator to log function calls.
    
    Args:
        level: Log level
        message: Log message template
        
    Returns:
        Decorator
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            aggregator = _global_aggregator
            
            if aggregator:
                msg = message or f"Called {func.__name__}"
                aggregator.log(msg, level, function=func.__name__)
            
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                return func(*args, **kwargs)
            except Exception as e:
                if aggregator:
                    aggregator.error(f"{func.__name__} failed", exception=e)
                raise
        
        return wrapper
    
    return decorator


# Global aggregator
_global_aggregator: Optional[LogAggregator] = None


def set_global_aggregator(aggregator: LogAggregator) -> None:
    """Set global aggregator."""
    global _global_aggregator
    _global_aggregator = aggregator


def get_global_aggregator() -> Optional[LogAggregator]:
    """Get global aggregator."""
    return _global_aggregator


# Factory functions
def create_log_aggregator(
    service_name: str = "app",
    environment: str = "development",
    min_level: LogLevel = LogLevel.DEBUG,
) -> LogAggregator:
    """Create log aggregator."""
    aggregator = LogAggregator(
        service_name=service_name,
        environment=environment,
        min_level=min_level,
    )
    set_global_aggregator(aggregator)
    return aggregator


def create_file_storage(
    path: str,
    format: LogFormat = LogFormat.NDJSON,
) -> FileLogStorage:
    """Create file storage."""
    return FileLogStorage(path, format)


__all__ = [
    # Exceptions
    "LoggingError",
    # Enums
    "LogLevel",
    "LogFormat",
    # Data classes
    "LogEntry",
    "LogQuery",
    "LogStats",
    "RetentionPolicy",
    # Storage
    "LogStorage",
    "InMemoryLogStorage",
    "FileLogStorage",
    # Aggregator
    "LogAggregator",
    # Decorator
    "logged",
    # Global
    "set_global_aggregator",
    "get_global_aggregator",
    # Factory functions
    "create_log_aggregator",
    "create_file_storage",
]
