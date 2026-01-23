"""
Enterprise Audit Logger Module.

Provides immutable audit logging, compliance tracking,
tamper-proof logs, and audit trail management.

Example:
    # Create audit logger
    audit = create_audit_logger()
    
    # Log audit event
    await audit.log(
        action="user.login",
        actor="user123",
        resource="session",
        details={"ip": "192.168.1.1"},
    )
    
    # Query audit trail
    events = await audit.query(
        actor="user123",
        action="user.*",
        start_time=datetime.utcnow() - timedelta(days=7),
    )
    
    # Use decorator
    @audited("order.create")
    async def create_order(order_data: dict):
        ...
"""

from __future__ import annotations

import asyncio
import contextvars
import functools
import hashlib
import json
import logging
import threading
import uuid
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Awaitable,
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


logger = logging.getLogger(__name__)


# Context variable for audit context
_audit_context: contextvars.ContextVar[Dict[str, Any]] = contextvars.ContextVar(
    'audit_context', default={}
)


class AuditError(Exception):
    """Base audit error."""
    pass


class IntegrityError(AuditError):
    """Log integrity violation."""
    pass


class AuditSeverity(str, Enum):
    """Audit event severity."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AuditCategory(str, Enum):
    """Audit event category."""
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    DATA_ACCESS = "data_access"
    DATA_MODIFICATION = "data_modification"
    CONFIGURATION = "configuration"
    SECURITY = "security"
    COMPLIANCE = "compliance"
    SYSTEM = "system"
    BUSINESS = "business"


class AuditResult(str, Enum):
    """Audit event result."""
    SUCCESS = "success"
    FAILURE = "failure"
    ERROR = "error"
    DENIED = "denied"


@dataclass
class AuditEvent:
    """Immutable audit event."""
    id: str
    timestamp: datetime
    action: str
    actor: str
    result: AuditResult = AuditResult.SUCCESS
    severity: AuditSeverity = AuditSeverity.INFO
    category: AuditCategory = AuditCategory.BUSINESS
    resource: Optional[str] = None
    resource_id: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    correlation_id: Optional[str] = None
    session_id: Optional[str] = None
    tenant_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    # Integrity fields
    previous_hash: Optional[str] = None
    hash: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuditEvent":
        """Create from dictionary."""
        data = dict(data)
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        data['result'] = AuditResult(data.get('result', 'success'))
        data['severity'] = AuditSeverity(data.get('severity', 'info'))
        data['category'] = AuditCategory(data.get('category', 'business'))
        return cls(**data)
    
    def compute_hash(self) -> str:
        """Compute event hash for integrity."""
        data = {
            'id': self.id,
            'timestamp': self.timestamp.isoformat(),
            'action': self.action,
            'actor': self.actor,
            'result': self.result.value,
            'resource': self.resource,
            'resource_id': self.resource_id,
            'details': self.details,
            'previous_hash': self.previous_hash,
        }
        content = json.dumps(data, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()


@dataclass
class AuditQuery:
    """Audit log query parameters."""
    actor: Optional[str] = None
    action: Optional[str] = None  # Supports wildcards like "user.*"
    resource: Optional[str] = None
    resource_id: Optional[str] = None
    category: Optional[AuditCategory] = None
    severity: Optional[AuditSeverity] = None
    result: Optional[AuditResult] = None
    tenant_id: Optional[str] = None
    correlation_id: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    limit: int = 100
    offset: int = 0


@dataclass
class AuditStats:
    """Audit statistics."""
    total_events: int = 0
    events_by_category: Dict[str, int] = field(default_factory=dict)
    events_by_severity: Dict[str, int] = field(default_factory=dict)
    events_by_result: Dict[str, int] = field(default_factory=dict)
    events_by_actor: Dict[str, int] = field(default_factory=dict)
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None


class AuditStore(ABC):
    """Abstract audit store."""
    
    @abstractmethod
    async def append(self, event: AuditEvent) -> None:
        """Append event to store (immutable)."""
        pass
    
    @abstractmethod
    async def query(self, query: AuditQuery) -> List[AuditEvent]:
        """Query events."""
        pass
    
    @abstractmethod
    async def get(self, event_id: str) -> Optional[AuditEvent]:
        """Get event by ID."""
        pass
    
    @abstractmethod
    async def get_last_hash(self) -> Optional[str]:
        """Get hash of last event for chain integrity."""
        pass
    
    @abstractmethod
    async def verify_integrity(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Tuple[bool, List[str]]:
        """Verify log integrity."""
        pass


class InMemoryAuditStore(AuditStore):
    """In-memory audit store (for testing/development)."""
    
    def __init__(self, max_events: int = 100000):
        self._events: List[AuditEvent] = []
        self._events_by_id: Dict[str, AuditEvent] = {}
        self._max_events = max_events
        self._lock = threading.Lock()
    
    async def append(self, event: AuditEvent) -> None:
        with self._lock:
            self._events.append(event)
            self._events_by_id[event.id] = event
            
            # Trim if exceeded max
            if len(self._events) > self._max_events:
                removed = self._events[:len(self._events) - self._max_events]
                self._events = self._events[-self._max_events:]
                for e in removed:
                    self._events_by_id.pop(e.id, None)
    
    async def query(self, query: AuditQuery) -> List[AuditEvent]:
        with self._lock:
            results = []
            
            for event in reversed(self._events):  # Most recent first
                if self._matches(event, query):
                    results.append(event)
                    
                    if len(results) >= query.limit:
                        break
            
            return results
    
    def _matches(self, event: AuditEvent, query: AuditQuery) -> bool:
        """Check if event matches query."""
        if query.actor and event.actor != query.actor:
            return False
        
        if query.action:
            if query.action.endswith(".*"):
                prefix = query.action[:-2]
                if not event.action.startswith(prefix):
                    return False
            elif event.action != query.action:
                return False
        
        if query.resource and event.resource != query.resource:
            return False
        
        if query.resource_id and event.resource_id != query.resource_id:
            return False
        
        if query.category and event.category != query.category:
            return False
        
        if query.severity and event.severity != query.severity:
            return False
        
        if query.result and event.result != query.result:
            return False
        
        if query.tenant_id and event.tenant_id != query.tenant_id:
            return False
        
        if query.correlation_id and event.correlation_id != query.correlation_id:
            return False
        
        if query.start_time and event.timestamp < query.start_time:
            return False
        
        if query.end_time and event.timestamp > query.end_time:
            return False
        
        return True
    
    async def get(self, event_id: str) -> Optional[AuditEvent]:
        with self._lock:
            return self._events_by_id.get(event_id)
    
    async def get_last_hash(self) -> Optional[str]:
        with self._lock:
            if self._events:
                return self._events[-1].hash
            return None
    
    async def verify_integrity(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Tuple[bool, List[str]]:
        with self._lock:
            errors = []
            previous_hash = None
            
            for event in self._events:
                if start_time and event.timestamp < start_time:
                    previous_hash = event.hash
                    continue
                
                if end_time and event.timestamp > end_time:
                    break
                
                # Check chain integrity
                if previous_hash and event.previous_hash != previous_hash:
                    errors.append(
                        f"Chain broken at {event.id}: "
                        f"expected {previous_hash}, got {event.previous_hash}"
                    )
                
                # Verify hash
                computed = event.compute_hash()
                if event.hash != computed:
                    errors.append(
                        f"Hash mismatch at {event.id}: "
                        f"expected {computed}, got {event.hash}"
                    )
                
                previous_hash = event.hash
            
            return len(errors) == 0, errors


class FileAuditStore(AuditStore):
    """File-based audit store with append-only logs."""
    
    def __init__(
        self,
        log_dir: Path,
        rotate_size_mb: int = 100,
    ):
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._rotate_size = rotate_size_mb * 1024 * 1024
        self._current_file: Optional[Path] = None
        self._lock = threading.Lock()
    
    def _get_current_log_file(self) -> Path:
        """Get current log file, rotating if needed."""
        if self._current_file is None:
            self._current_file = self._log_dir / f"audit_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.jsonl"
        
        if self._current_file.exists():
            if self._current_file.stat().st_size > self._rotate_size:
                self._current_file = self._log_dir / f"audit_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.jsonl"
        
        return self._current_file
    
    async def append(self, event: AuditEvent) -> None:
        with self._lock:
            log_file = self._get_current_log_file()
            
            with open(log_file, 'a') as f:
                f.write(json.dumps(event.to_dict()) + '\n')
                f.flush()
    
    async def query(self, query: AuditQuery) -> List[AuditEvent]:
        results = []
        
        log_files = sorted(self._log_dir.glob("audit_*.jsonl"), reverse=True)
        
        for log_file in log_files:
            with open(log_file, 'r') as f:
                for line in f:
                    if line.strip():
                        event = AuditEvent.from_dict(json.loads(line))
                        
                        # Simple filtering
                        if query.start_time and event.timestamp < query.start_time:
                            continue
                        if query.end_time and event.timestamp > query.end_time:
                            continue
                        if query.actor and event.actor != query.actor:
                            continue
                        
                        results.append(event)
                        
                        if len(results) >= query.limit:
                            return results
        
        return results
    
    async def get(self, event_id: str) -> Optional[AuditEvent]:
        log_files = sorted(self._log_dir.glob("audit_*.jsonl"), reverse=True)
        
        for log_file in log_files:
            with open(log_file, 'r') as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        if data.get('id') == event_id:
                            return AuditEvent.from_dict(data)
        
        return None
    
    async def get_last_hash(self) -> Optional[str]:
        log_files = sorted(self._log_dir.glob("audit_*.jsonl"), reverse=True)
        
        if not log_files:
            return None
        
        # Get last line of most recent file
        with open(log_files[0], 'r') as f:
            last_line = None
            for line in f:
                if line.strip():
                    last_line = line
            
            if last_line:
                data = json.loads(last_line)
                return data.get('hash')
        
        return None
    
    async def verify_integrity(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Tuple[bool, List[str]]:
        errors = []
        previous_hash = None
        
        log_files = sorted(self._log_dir.glob("audit_*.jsonl"))
        
        for log_file in log_files:
            with open(log_file, 'r') as f:
                for line in f:
                    if line.strip():
                        event = AuditEvent.from_dict(json.loads(line))
                        
                        if previous_hash and event.previous_hash != previous_hash:
                            errors.append(f"Chain broken at {event.id}")
                        
                        computed = event.compute_hash()
                        if event.hash != computed:
                            errors.append(f"Hash mismatch at {event.id}")
                        
                        previous_hash = event.hash
        
        return len(errors) == 0, errors


class AuditContext:
    """Context manager for adding audit context."""
    
    def __init__(self, **context):
        self._context = context
        self._token: Optional[contextvars.Token] = None
    
    def __enter__(self) -> "AuditContext":
        current = dict(_audit_context.get())
        current.update(self._context)
        self._token = _audit_context.set(current)
        return self
    
    def __exit__(self, *args) -> None:
        if self._token:
            _audit_context.reset(self._token)


class AuditLogger:
    """
    Enterprise audit logger with tamper-proof logging.
    """
    
    def __init__(
        self,
        store: Optional[AuditStore] = None,
        enable_chain: bool = True,
    ):
        self._store = store or InMemoryAuditStore()
        self._enable_chain = enable_chain
        self._handlers: List[Callable[[AuditEvent], Awaitable[None]]] = []
    
    @property
    def store(self) -> AuditStore:
        return self._store
    
    def add_handler(
        self,
        handler: Callable[[AuditEvent], Awaitable[None]],
    ) -> None:
        """Add event handler."""
        self._handlers.append(handler)
    
    async def log(
        self,
        action: str,
        actor: str,
        result: AuditResult = AuditResult.SUCCESS,
        severity: AuditSeverity = AuditSeverity.INFO,
        category: AuditCategory = AuditCategory.BUSINESS,
        resource: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
        session_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuditEvent:
        """Log an audit event."""
        # Get context
        context = _audit_context.get()
        
        # Create event
        event = AuditEvent(
            id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            action=action,
            actor=actor,
            result=result,
            severity=severity,
            category=category,
            resource=resource,
            resource_id=resource_id,
            details=details or {},
            metadata=metadata or {},
            correlation_id=correlation_id or context.get('correlation_id'),
            session_id=session_id or context.get('session_id'),
            tenant_id=tenant_id or context.get('tenant_id'),
            ip_address=ip_address or context.get('ip_address'),
            user_agent=user_agent or context.get('user_agent'),
        )
        
        # Add chain integrity
        if self._enable_chain:
            event.previous_hash = await self._store.get_last_hash()
            event.hash = event.compute_hash()
        
        # Store event
        await self._store.append(event)
        
        # Notify handlers
        for handler in self._handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(f"Audit handler error: {e}")
        
        return event
    
    async def log_success(
        self,
        action: str,
        actor: str,
        **kwargs,
    ) -> AuditEvent:
        """Log successful action."""
        return await self.log(
            action=action,
            actor=actor,
            result=AuditResult.SUCCESS,
            **kwargs,
        )
    
    async def log_failure(
        self,
        action: str,
        actor: str,
        reason: str = "",
        **kwargs,
    ) -> AuditEvent:
        """Log failed action."""
        details = kwargs.pop('details', {})
        details['reason'] = reason
        
        return await self.log(
            action=action,
            actor=actor,
            result=AuditResult.FAILURE,
            details=details,
            **kwargs,
        )
    
    async def log_denied(
        self,
        action: str,
        actor: str,
        reason: str = "",
        **kwargs,
    ) -> AuditEvent:
        """Log denied action."""
        details = kwargs.pop('details', {})
        details['reason'] = reason
        
        return await self.log(
            action=action,
            actor=actor,
            result=AuditResult.DENIED,
            severity=AuditSeverity.WARNING,
            category=AuditCategory.AUTHORIZATION,
            details=details,
            **kwargs,
        )
    
    async def log_error(
        self,
        action: str,
        actor: str,
        error: str = "",
        **kwargs,
    ) -> AuditEvent:
        """Log error."""
        details = kwargs.pop('details', {})
        details['error'] = error
        
        return await self.log(
            action=action,
            actor=actor,
            result=AuditResult.ERROR,
            severity=AuditSeverity.ERROR,
            details=details,
            **kwargs,
        )
    
    async def query(
        self,
        actor: Optional[str] = None,
        action: Optional[str] = None,
        resource: Optional[str] = None,
        category: Optional[AuditCategory] = None,
        result: Optional[AuditResult] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        tenant_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[AuditEvent]:
        """Query audit events."""
        query = AuditQuery(
            actor=actor,
            action=action,
            resource=resource,
            category=category,
            result=result,
            start_time=start_time,
            end_time=end_time,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            limit=limit,
        )
        
        return await self._store.query(query)
    
    async def get_event(self, event_id: str) -> Optional[AuditEvent]:
        """Get specific event."""
        return await self._store.get(event_id)
    
    async def verify_integrity(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Tuple[bool, List[str]]:
        """Verify audit log integrity."""
        return await self._store.verify_integrity(start_time, end_time)
    
    async def get_stats(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> AuditStats:
        """Get audit statistics."""
        events = await self.query(
            start_time=start_time,
            end_time=end_time,
            limit=10000,
        )
        
        stats = AuditStats(
            total_events=len(events),
            period_start=start_time,
            period_end=end_time,
        )
        
        for event in events:
            cat = event.category.value
            stats.events_by_category[cat] = stats.events_by_category.get(cat, 0) + 1
            
            sev = event.severity.value
            stats.events_by_severity[sev] = stats.events_by_severity.get(sev, 0) + 1
            
            res = event.result.value
            stats.events_by_result[res] = stats.events_by_result.get(res, 0) + 1
            
            stats.events_by_actor[event.actor] = stats.events_by_actor.get(event.actor, 0) + 1
        
        return stats


# Global audit logger
_global_logger: Optional[AuditLogger] = None


# Decorators
def audited(
    action: str,
    category: AuditCategory = AuditCategory.BUSINESS,
    resource: Optional[str] = None,
    capture_args: bool = False,
    capture_result: bool = False,
) -> Callable:
    """
    Decorator to automatically audit function calls.
    
    Example:
        @audited("order.create", category=AuditCategory.DATA_MODIFICATION)
        async def create_order(order_data: dict):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            audit = get_global_logger()
            
            # Get actor from context
            context = _audit_context.get()
            actor = context.get('actor', 'system')
            
            details = {}
            if capture_args:
                details['args'] = str(args)[:500]
                details['kwargs'] = {k: str(v)[:100] for k, v in kwargs.items()}
            
            try:
                result = await func(*args, **kwargs)
                
                if capture_result:
                    details['result'] = str(result)[:500]
                
                await audit.log_success(
                    action=action,
                    actor=actor,
                    category=category,
                    resource=resource,
                    details=details,
                )
                
                return result
                
            except Exception as e:
                details['error'] = str(e)
                
                await audit.log_error(
                    action=action,
                    actor=actor,
                    category=category,
                    resource=resource,
                    error=str(e),
                    details=details,
                )
                
                raise
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


def audit_on_error(
    action: str,
    severity: AuditSeverity = AuditSeverity.ERROR,
) -> Callable:
    """
    Decorator to audit only on error.
    
    Example:
        @audit_on_error("payment.process")
        async def process_payment(payment_data: dict):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                audit = get_global_logger()
                context = _audit_context.get()
                
                await audit.log_error(
                    action=action,
                    actor=context.get('actor', 'system'),
                    severity=severity,
                    error=str(e),
                )
                
                raise
        
        return async_wrapper
    
    return decorator


# Factory functions
def create_audit_logger(
    store: Optional[AuditStore] = None,
    enable_chain: bool = True,
) -> AuditLogger:
    """Create audit logger."""
    return AuditLogger(store, enable_chain)


def create_in_memory_store(max_events: int = 100000) -> InMemoryAuditStore:
    """Create in-memory audit store."""
    return InMemoryAuditStore(max_events)


def create_file_store(
    log_dir: str,
    rotate_size_mb: int = 100,
) -> FileAuditStore:
    """Create file-based audit store."""
    return FileAuditStore(Path(log_dir), rotate_size_mb)


def create_audit_query(
    actor: Optional[str] = None,
    action: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = 100,
) -> AuditQuery:
    """Create audit query."""
    return AuditQuery(
        actor=actor,
        action=action,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
    )


def create_audit_context(**context) -> AuditContext:
    """Create audit context."""
    return AuditContext(**context)


def get_global_logger() -> AuditLogger:
    """Get global audit logger."""
    global _global_logger
    if _global_logger is None:
        _global_logger = create_audit_logger()
    return _global_logger


__all__ = [
    # Exceptions
    "AuditError",
    "IntegrityError",
    # Enums
    "AuditSeverity",
    "AuditCategory",
    "AuditResult",
    # Data classes
    "AuditEvent",
    "AuditQuery",
    "AuditStats",
    # Store
    "AuditStore",
    "InMemoryAuditStore",
    "FileAuditStore",
    # Context
    "AuditContext",
    # Logger
    "AuditLogger",
    # Decorators
    "audited",
    "audit_on_error",
    # Factory functions
    "create_audit_logger",
    "create_in_memory_store",
    "create_file_store",
    "create_audit_query",
    "create_audit_context",
    "get_global_logger",
]
