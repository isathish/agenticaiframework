"""
Enterprise Audit Logging - Comprehensive audit trail.

Provides detailed logging of all agent activities, tool usage,
and data access for compliance and security purposes.

Features:
- Action logging
- Data access tracking
- Retention policies
- Export capabilities
- Compliance reports
"""

import asyncio
import functools
import hashlib
import json
import logging
import os
import threading
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# =============================================================================
# Audit Types
# =============================================================================

class AuditAction(Enum):
    """Standard audit actions."""
    # Agent actions
    AGENT_CREATED = "agent.created"
    AGENT_EXECUTED = "agent.executed"
    AGENT_COMPLETED = "agent.completed"
    AGENT_FAILED = "agent.failed"
    
    # Tool actions
    TOOL_CALLED = "tool.called"
    TOOL_COMPLETED = "tool.completed"
    TOOL_FAILED = "tool.failed"
    
    # Data actions
    DATA_READ = "data.read"
    DATA_WRITE = "data.write"
    DATA_DELETE = "data.delete"
    DATA_EXPORT = "data.export"
    
    # Auth actions
    AUTH_LOGIN = "auth.login"
    AUTH_LOGOUT = "auth.logout"
    AUTH_FAILED = "auth.failed"
    AUTH_TOKEN_CREATED = "auth.token_created"
    AUTH_TOKEN_REVOKED = "auth.token_revoked"
    
    # Config actions
    CONFIG_CHANGED = "config.changed"
    SECRET_ACCESSED = "secret.accessed"
    SECRET_ROTATED = "secret.rotated"
    
    # LLM actions
    LLM_REQUEST = "llm.request"
    LLM_RESPONSE = "llm.response"
    
    # Custom
    CUSTOM = "custom"


class AuditSeverity(Enum):
    """Audit entry severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class AuditEntry:
    """An audit log entry."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Action details
    action: AuditAction = AuditAction.CUSTOM
    action_name: str = ""
    severity: AuditSeverity = AuditSeverity.INFO
    
    # Actor
    actor_id: str = ""
    actor_type: str = "system"  # user, agent, system
    actor_name: str = ""
    
    # Target
    resource_type: str = ""
    resource_id: str = ""
    resource_name: str = ""
    
    # Context
    session_id: Optional[str] = None
    correlation_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    
    # Details
    details: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Outcome
    success: bool = True
    error: Optional[str] = None
    
    # Data changes (for write operations)
    old_value: Optional[str] = None  # Hashed for sensitive data
    new_value: Optional[str] = None  # Hashed for sensitive data
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "action": self.action.value if isinstance(self.action, AuditAction) else self.action,
            "action_name": self.action_name,
            "severity": self.severity.value,
            "actor_id": self.actor_id,
            "actor_type": self.actor_type,
            "actor_name": self.actor_name,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "resource_name": self.resource_name,
            "session_id": self.session_id,
            "correlation_id": self.correlation_id,
            "ip_address": self.ip_address,
            "details": self.details,
            "metadata": self.metadata,
            "success": self.success,
            "error": self.error,
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())


# =============================================================================
# Audit Backend Interface
# =============================================================================

class AuditBackend(ABC):
    """Abstract interface for audit backends."""
    
    @abstractmethod
    async def write(self, entry: AuditEntry):
        """Write an audit entry."""
        pass
    
    @abstractmethod
    async def query(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        action: Optional[AuditAction] = None,
        actor_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[AuditEntry]:
        """Query audit entries."""
        pass
    
    @abstractmethod
    async def count(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        action: Optional[AuditAction] = None,
    ) -> int:
        """Count audit entries matching criteria."""
        pass


# =============================================================================
# In-Memory Backend
# =============================================================================

class InMemoryAuditBackend(AuditBackend):
    """In-memory audit backend for development."""
    
    def __init__(self, max_entries: int = 100000):
        self._entries: List[AuditEntry] = []
        self.max_entries = max_entries
        self._lock = asyncio.Lock()
    
    async def write(self, entry: AuditEntry):
        async with self._lock:
            self._entries.append(entry)
            
            # Evict old entries
            if len(self._entries) > self.max_entries:
                self._entries = self._entries[-self.max_entries:]
    
    async def query(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        action: Optional[AuditAction] = None,
        actor_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[AuditEntry]:
        results = []
        
        for entry in reversed(self._entries):
            if len(results) >= limit:
                break
            
            if start_time and entry.timestamp < start_time:
                continue
            
            if end_time and entry.timestamp > end_time:
                continue
            
            if action and entry.action != action:
                continue
            
            if actor_id and entry.actor_id != actor_id:
                continue
            
            if resource_type and entry.resource_type != resource_type:
                continue
            
            if resource_id and entry.resource_id != resource_id:
                continue
            
            results.append(entry)
        
        return results
    
    async def count(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        action: Optional[AuditAction] = None,
    ) -> int:
        count = 0
        
        for entry in self._entries:
            if start_time and entry.timestamp < start_time:
                continue
            
            if end_time and entry.timestamp > end_time:
                continue
            
            if action and entry.action != action:
                continue
            
            count += 1
        
        return count


# =============================================================================
# File Backend
# =============================================================================

class FileAuditBackend(AuditBackend):
    """File-based audit backend with rotation."""
    
    def __init__(
        self,
        log_dir: str = "./audit_logs",
        max_file_size: int = 10 * 1024 * 1024,  # 10MB
        retention_days: int = 90,
    ):
        self.log_dir = Path(log_dir)
        self.max_file_size = max_file_size
        self.retention_days = retention_days
        
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._current_file: Optional[Path] = None
        self._lock = asyncio.Lock()
    
    def _get_current_file(self) -> Path:
        """Get current log file, rotating if needed."""
        today = datetime.now().strftime("%Y-%m-%d")
        base_file = self.log_dir / f"audit_{today}.jsonl"
        
        if not base_file.exists():
            return base_file
        
        # Check size for rotation
        if base_file.stat().st_size >= self.max_file_size:
            # Find next available sequence number
            seq = 1
            while True:
                seq_file = self.log_dir / f"audit_{today}_{seq:03d}.jsonl"
                if not seq_file.exists():
                    return seq_file
                seq += 1
        
        return base_file
    
    async def write(self, entry: AuditEntry):
        async with self._lock:
            log_file = self._get_current_file()
            
            with open(log_file, "a") as f:
                f.write(entry.to_json() + "\n")
    
    async def query(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        action: Optional[AuditAction] = None,
        actor_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[AuditEntry]:
        results = []
        
        # Get all log files in time range
        log_files = sorted(self.log_dir.glob("audit_*.jsonl"), reverse=True)
        
        for log_file in log_files:
            if len(results) >= limit:
                break
            
            with open(log_file, "r") as f:
                for line in f:
                    if len(results) >= limit:
                        break
                    
                    try:
                        data = json.loads(line)
                        entry = self._dict_to_entry(data)
                        
                        if self._matches_filter(
                            entry, start_time, end_time, action,
                            actor_id, resource_type, resource_id
                        ):
                            results.append(entry)
                    except json.JSONDecodeError:
                        continue
        
        return results
    
    async def count(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        action: Optional[AuditAction] = None,
    ) -> int:
        count = 0
        
        for log_file in self.log_dir.glob("audit_*.jsonl"):
            with open(log_file, "r") as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        entry = self._dict_to_entry(data)
                        
                        if self._matches_filter(
                            entry, start_time, end_time, action,
                            None, None, None
                        ):
                            count += 1
                    except json.JSONDecodeError:
                        continue
        
        return count
    
    def _dict_to_entry(self, data: Dict) -> AuditEntry:
        """Convert dict to AuditEntry."""
        return AuditEntry(
            id=data.get("id", ""),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            action=AuditAction(data["action"]) if data.get("action") in [a.value for a in AuditAction] else AuditAction.CUSTOM,
            action_name=data.get("action_name", ""),
            severity=AuditSeverity(data.get("severity", "info")),
            actor_id=data.get("actor_id", ""),
            actor_type=data.get("actor_type", "system"),
            actor_name=data.get("actor_name", ""),
            resource_type=data.get("resource_type", ""),
            resource_id=data.get("resource_id", ""),
            resource_name=data.get("resource_name", ""),
            session_id=data.get("session_id"),
            correlation_id=data.get("correlation_id"),
            details=data.get("details", {}),
            metadata=data.get("metadata", {}),
            success=data.get("success", True),
            error=data.get("error"),
        )
    
    def _matches_filter(
        self,
        entry: AuditEntry,
        start_time: Optional[datetime],
        end_time: Optional[datetime],
        action: Optional[AuditAction],
        actor_id: Optional[str],
        resource_type: Optional[str],
        resource_id: Optional[str],
    ) -> bool:
        """Check if entry matches filter criteria."""
        if start_time and entry.timestamp < start_time:
            return False
        
        if end_time and entry.timestamp > end_time:
            return False
        
        if action and entry.action != action:
            return False
        
        if actor_id and entry.actor_id != actor_id:
            return False
        
        if resource_type and entry.resource_type != resource_type:
            return False
        
        if resource_id and entry.resource_id != resource_id:
            return False
        
        return True
    
    async def cleanup(self):
        """Remove old log files based on retention policy."""
        cutoff = datetime.now() - timedelta(days=self.retention_days)
        
        for log_file in self.log_dir.glob("audit_*.jsonl"):
            try:
                # Extract date from filename
                date_str = log_file.stem.split("_")[1]
                file_date = datetime.strptime(date_str, "%Y-%m-%d")
                
                if file_date < cutoff:
                    log_file.unlink()
                    logger.info(f"Deleted old audit log: {log_file}")
            except (ValueError, IndexError):
                continue


# =============================================================================
# Audit Logger
# =============================================================================

class AuditLogger:
    """
    High-level audit logging interface.
    
    Usage:
        >>> audit = AuditLogger()
        >>> 
        >>> await audit.log_action(
        ...     action=AuditAction.AGENT_EXECUTED,
        ...     actor_id="user-123",
        ...     resource_type="agent",
        ...     resource_id="agent-456",
        ...     details={"input": "task description"},
        ... )
        >>> 
        >>> @audit.track
        >>> async def my_function(data: str):
        ...     return process(data)
    """
    
    def __init__(
        self,
        backend: Optional[AuditBackend] = None,
        default_actor_id: str = "system",
        default_actor_type: str = "system",
        session_id: Optional[str] = None,
    ):
        self.backend = backend or InMemoryAuditBackend()
        self.default_actor_id = default_actor_id
        self.default_actor_type = default_actor_type
        self.session_id = session_id or str(uuid.uuid4())
        
        self._correlation_id: Optional[str] = None
        self._context: Dict[str, Any] = {}
    
    def set_correlation_id(self, correlation_id: str):
        """Set correlation ID for request tracing."""
        self._correlation_id = correlation_id
    
    def set_context(self, **kwargs):
        """Set additional context for all entries."""
        self._context.update(kwargs)
    
    async def log(
        self,
        action: AuditAction,
        resource_type: str = "",
        resource_id: str = "",
        resource_name: str = "",
        actor_id: Optional[str] = None,
        actor_type: Optional[str] = None,
        actor_name: str = "",
        severity: AuditSeverity = AuditSeverity.INFO,
        success: bool = True,
        error: Optional[str] = None,
        details: Dict = None,
        **metadata,
    ):
        """Log an audit entry."""
        entry = AuditEntry(
            action=action,
            action_name=action.value if isinstance(action, AuditAction) else str(action),
            severity=severity,
            actor_id=actor_id or self.default_actor_id,
            actor_type=actor_type or self.default_actor_type,
            actor_name=actor_name,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
            session_id=self.session_id,
            correlation_id=self._correlation_id,
            details=details or {},
            metadata={**self._context, **metadata},
            success=success,
            error=error,
        )
        
        await self.backend.write(entry)
        return entry
    
    async def log_agent_execution(
        self,
        agent_name: str,
        agent_id: str,
        input_data: Any,
        output_data: Any = None,
        success: bool = True,
        error: str = None,
        duration_ms: float = None,
    ):
        """Log an agent execution."""
        await self.log(
            action=AuditAction.AGENT_COMPLETED if success else AuditAction.AGENT_FAILED,
            resource_type="agent",
            resource_id=agent_id,
            resource_name=agent_name,
            success=success,
            error=error,
            details={
                "input_summary": str(input_data)[:500],
                "output_summary": str(output_data)[:500] if output_data else None,
                "duration_ms": duration_ms,
            },
        )
    
    async def log_tool_call(
        self,
        tool_name: str,
        tool_id: str,
        args: Dict,
        result: Any = None,
        success: bool = True,
        error: str = None,
    ):
        """Log a tool call."""
        await self.log(
            action=AuditAction.TOOL_COMPLETED if success else AuditAction.TOOL_FAILED,
            resource_type="tool",
            resource_id=tool_id,
            resource_name=tool_name,
            success=success,
            error=error,
            details={
                "args": {k: str(v)[:100] for k, v in args.items()},
                "result_summary": str(result)[:500] if result else None,
            },
        )
    
    async def log_data_access(
        self,
        action: AuditAction,
        data_type: str,
        data_id: str,
        data_name: str = "",
        old_value: Any = None,
        new_value: Any = None,
    ):
        """Log data access/modification."""
        await self.log(
            action=action,
            resource_type=data_type,
            resource_id=data_id,
            resource_name=data_name,
            details={
                "old_value_hash": self._hash_value(old_value) if old_value else None,
                "new_value_hash": self._hash_value(new_value) if new_value else None,
            },
        )
    
    def _hash_value(self, value: Any) -> str:
        """Hash a value for audit logging."""
        value_str = json.dumps(value, default=str)
        return hashlib.sha256(value_str.encode()).hexdigest()[:16]
    
    def track(
        self,
        action: AuditAction = AuditAction.CUSTOM,
        resource_type: str = "function",
    ):
        """
        Decorator to automatically track function execution.
        
        Usage:
            >>> @audit.track(action=AuditAction.DATA_READ)
            >>> async def read_data(id: str):
            ...     return await db.get(id)
        """
        def decorator(fn: Callable):
            @functools.wraps(fn)
            async def wrapper(*args, **kwargs):
                start_time = datetime.now()
                success = True
                error = None
                result = None
                
                try:
                    result = await fn(*args, **kwargs)
                    return result
                except Exception as e:
                    success = False
                    error = str(e)
                    raise
                finally:
                    duration = (datetime.now() - start_time).total_seconds() * 1000
                    
                    await self.log(
                        action=action,
                        resource_type=resource_type,
                        resource_id=fn.__name__,
                        resource_name=fn.__name__,
                        success=success,
                        error=error,
                        details={
                            "args_count": len(args),
                            "kwargs_keys": list(kwargs.keys()),
                            "duration_ms": duration,
                        },
                    )
            
            return wrapper
        return decorator
    
    async def query(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        action: Optional[AuditAction] = None,
        actor_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[AuditEntry]:
        """Query audit logs."""
        return await self.backend.query(
            start_time=start_time,
            end_time=end_time,
            action=action,
            actor_id=actor_id,
            resource_type=resource_type,
            limit=limit,
        )
    
    async def export(
        self,
        start_time: datetime,
        end_time: datetime,
        format: str = "json",
    ) -> str:
        """Export audit logs in specified format."""
        entries = await self.backend.query(
            start_time=start_time,
            end_time=end_time,
            limit=100000,
        )
        
        if format == "json":
            return json.dumps([e.to_dict() for e in entries], indent=2)
        elif format == "csv":
            import csv
            import io
            
            output = io.StringIO()
            if entries:
                writer = csv.DictWriter(output, fieldnames=entries[0].to_dict().keys())
                writer.writeheader()
                for entry in entries:
                    writer.writerow(entry.to_dict())
            
            return output.getvalue()
        else:
            raise ValueError(f"Unsupported format: {format}")


# =============================================================================
# Global Audit Logger
# =============================================================================

_global_audit: Optional[AuditLogger] = None
_lock = threading.Lock()


def get_audit_logger() -> AuditLogger:
    """Get the global audit logger."""
    global _global_audit
    
    if _global_audit is None:
        with _lock:
            if _global_audit is None:
                _global_audit = AuditLogger()
    
    return _global_audit


def set_audit_logger(audit: AuditLogger):
    """Set the global audit logger."""
    global _global_audit
    _global_audit = audit


# Convenience functions
async def audit_log(action: AuditAction, **kwargs):
    """Log to global audit logger."""
    return await get_audit_logger().log(action, **kwargs)


def audit_track(action: AuditAction = AuditAction.CUSTOM, resource_type: str = "function"):
    """Track decorator using global audit logger."""
    return get_audit_logger().track(action, resource_type)
