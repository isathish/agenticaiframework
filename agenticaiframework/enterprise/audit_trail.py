"""
Enterprise Audit Trail Module.

Complete audit logging with change tracking,
compliance reporting, and tamper detection.

Example:
    # Create audit trail
    audit = create_audit_trail()
    
    # Log action
    await audit.log(
        action="user.created",
        actor_id="admin-123",
        resource_type="user",
        resource_id="user-456",
        details={"email": "new@example.com"},
    )
    
    # Query audit logs
    logs = await audit.query(
        resource_type="user",
        start_time=datetime.now() - timedelta(days=7),
    )
    
    # Generate compliance report
    report = await audit.generate_report(
        report_type="access_log",
        start=start_date,
        end=end_date,
    )
"""

from __future__ import annotations

import asyncio
import functools
import hashlib
import json
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    Tuple,
    TypeVar,
    Union,
)

T = TypeVar('T')


logger = logging.getLogger(__name__)


class AuditError(Exception):
    """Audit error."""
    pass


class TamperDetectedError(AuditError):
    """Tamper detected in audit log."""
    pass


class AuditLevel(str, Enum):
    """Audit level."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ActionType(str, Enum):
    """Action type."""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    LOGIN = "login"
    LOGOUT = "logout"
    EXPORT = "export"
    IMPORT = "import"
    APPROVE = "approve"
    REJECT = "reject"
    CUSTOM = "custom"


class ComplianceStandard(str, Enum):
    """Compliance standards."""
    GDPR = "gdpr"
    HIPAA = "hipaa"
    SOC2 = "soc2"
    PCI_DSS = "pci_dss"
    SOX = "sox"
    ISO27001 = "iso27001"


@dataclass
class AuditEntry:
    """Audit log entry."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    action: str = ""
    action_type: ActionType = ActionType.CUSTOM
    level: AuditLevel = AuditLevel.INFO
    actor_id: str = ""
    actor_type: str = "user"
    actor_ip: Optional[str] = None
    actor_user_agent: Optional[str] = None
    resource_type: str = ""
    resource_id: str = ""
    resource_name: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    old_values: Optional[Dict[str, Any]] = None
    new_values: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    hash: Optional[str] = None
    previous_hash: Optional[str] = None
    
    def compute_hash(self, previous_hash: Optional[str] = None) -> str:
        """Compute entry hash for chain verification."""
        data = {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "action": self.action,
            "actor_id": self.actor_id,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "previous_hash": previous_hash,
        }
        content = json.dumps(data, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()


@dataclass
class ChangeRecord:
    """Change tracking record."""
    field: str
    old_value: Any
    new_value: Any
    changed_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class AuditQuery:
    """Audit query parameters."""
    action: Optional[str] = None
    action_type: Optional[ActionType] = None
    actor_id: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    level: Optional[AuditLevel] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    limit: int = 100
    offset: int = 0


@dataclass
class ComplianceReport:
    """Compliance report."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    report_type: str = ""
    standard: Optional[ComplianceStandard] = None
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: datetime = field(default_factory=datetime.utcnow)
    generated_at: datetime = field(default_factory=datetime.utcnow)
    total_entries: int = 0
    entries: List[AuditEntry] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    findings: List[str] = field(default_factory=list)


@dataclass
class AuditStats:
    """Audit statistics."""
    total_entries: int = 0
    entries_by_action: Dict[str, int] = field(default_factory=dict)
    entries_by_actor: Dict[str, int] = field(default_factory=dict)
    entries_by_resource: Dict[str, int] = field(default_factory=dict)
    entries_by_level: Dict[str, int] = field(default_factory=dict)
    oldest_entry: Optional[datetime] = None
    newest_entry: Optional[datetime] = None
    chain_valid: bool = True


# Storage interface
class AuditStorage(ABC):
    """Abstract audit storage."""
    
    @abstractmethod
    async def save(self, entry: AuditEntry) -> None:
        """Save audit entry."""
        pass
    
    @abstractmethod
    async def get(self, entry_id: str) -> Optional[AuditEntry]:
        """Get entry by ID."""
        pass
    
    @abstractmethod
    async def query(
        self,
        query: AuditQuery,
    ) -> List[AuditEntry]:
        """Query entries."""
        pass
    
    @abstractmethod
    async def get_last_hash(self) -> Optional[str]:
        """Get last entry hash."""
        pass
    
    @abstractmethod
    async def count(self, query: Optional[AuditQuery] = None) -> int:
        """Count entries."""
        pass


class InMemoryAuditStorage(AuditStorage):
    """In-memory audit storage."""
    
    def __init__(self):
        self._entries: List[AuditEntry] = []
    
    async def save(self, entry: AuditEntry) -> None:
        self._entries.append(entry)
    
    async def get(self, entry_id: str) -> Optional[AuditEntry]:
        for entry in self._entries:
            if entry.id == entry_id:
                return entry
        return None
    
    async def query(self, query: AuditQuery) -> List[AuditEntry]:
        results = []
        
        for entry in reversed(self._entries):
            if query.action and entry.action != query.action:
                continue
            if query.action_type and entry.action_type != query.action_type:
                continue
            if query.actor_id and entry.actor_id != query.actor_id:
                continue
            if query.resource_type and entry.resource_type != query.resource_type:
                continue
            if query.resource_id and entry.resource_id != query.resource_id:
                continue
            if query.level and entry.level != query.level:
                continue
            if query.start_time and entry.timestamp < query.start_time:
                continue
            if query.end_time and entry.timestamp > query.end_time:
                continue
            
            results.append(entry)
        
        start = query.offset
        end = query.offset + query.limit
        
        return results[start:end]
    
    async def get_last_hash(self) -> Optional[str]:
        if self._entries:
            return self._entries[-1].hash
        return None
    
    async def count(self, query: Optional[AuditQuery] = None) -> int:
        if not query:
            return len(self._entries)
        
        results = await self.query(
            AuditQuery(
                action=query.action,
                action_type=query.action_type,
                actor_id=query.actor_id,
                resource_type=query.resource_type,
                resource_id=query.resource_id,
                level=query.level,
                start_time=query.start_time,
                end_time=query.end_time,
                limit=1000000,
            )
        )
        return len(results)


# Change tracker
class ChangeTracker:
    """Track changes to objects."""
    
    def __init__(self):
        self._snapshots: Dict[str, Dict[str, Any]] = {}
    
    def snapshot(self, key: str, obj: Any) -> None:
        """Take snapshot of object."""
        if hasattr(obj, "__dict__"):
            self._snapshots[key] = dict(obj.__dict__)
        elif isinstance(obj, dict):
            self._snapshots[key] = dict(obj)
        else:
            self._snapshots[key] = {"value": obj}
    
    def get_changes(self, key: str, obj: Any) -> List[ChangeRecord]:
        """Get changes since snapshot."""
        if key not in self._snapshots:
            return []
        
        old = self._snapshots[key]
        
        if hasattr(obj, "__dict__"):
            new = dict(obj.__dict__)
        elif isinstance(obj, dict):
            new = dict(obj)
        else:
            new = {"value": obj}
        
        changes = []
        
        all_keys = set(old.keys()) | set(new.keys())
        
        for k in all_keys:
            old_val = old.get(k)
            new_val = new.get(k)
            
            if old_val != new_val:
                changes.append(ChangeRecord(
                    field=k,
                    old_value=old_val,
                    new_value=new_val,
                ))
        
        return changes
    
    def clear(self, key: Optional[str] = None) -> None:
        """Clear snapshots."""
        if key:
            self._snapshots.pop(key, None)
        else:
            self._snapshots.clear()


# Audit trail service
class AuditTrail:
    """
    Audit trail service.
    """
    
    def __init__(
        self,
        storage: Optional[AuditStorage] = None,
        enable_chain: bool = True,
        retention_days: int = 365,
    ):
        self._storage = storage or InMemoryAuditStorage()
        self._enable_chain = enable_chain
        self._retention_days = retention_days
        self._change_tracker = ChangeTracker()
        self._filters: List[Callable[[AuditEntry], bool]] = []
        self._hooks: Dict[str, List[Callable]] = {}
    
    async def log(
        self,
        action: str,
        actor_id: str,
        resource_type: str = "",
        resource_id: str = "",
        action_type: ActionType = ActionType.CUSTOM,
        level: AuditLevel = AuditLevel.INFO,
        details: Optional[Dict[str, Any]] = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> AuditEntry:
        """
        Log an audit entry.
        
        Args:
            action: Action name
            actor_id: Actor ID
            resource_type: Resource type
            resource_id: Resource ID
            action_type: Action type
            level: Audit level
            details: Additional details
            old_values: Old values for updates
            new_values: New values for updates
            metadata: Additional metadata
            **kwargs: Extra fields
            
        Returns:
            Audit entry
        """
        entry = AuditEntry(
            action=action,
            action_type=action_type,
            level=level,
            actor_id=actor_id,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            old_values=old_values,
            new_values=new_values,
            metadata=metadata or {},
        )
        
        # Add extra fields
        for key, value in kwargs.items():
            if hasattr(entry, key):
                setattr(entry, key, value)
            else:
                entry.metadata[key] = value
        
        # Apply filters
        for filter_fn in self._filters:
            if not filter_fn(entry):
                return entry
        
        # Compute chain hash
        if self._enable_chain:
            previous_hash = await self._storage.get_last_hash()
            entry.previous_hash = previous_hash
            entry.hash = entry.compute_hash(previous_hash)
        
        await self._storage.save(entry)
        
        # Trigger hooks
        await self._trigger_hooks("entry_logged", entry)
        
        logger.debug(f"Audit: {action} by {actor_id} on {resource_type}/{resource_id}")
        
        return entry
    
    async def log_create(
        self,
        actor_id: str,
        resource_type: str,
        resource_id: str,
        data: Dict[str, Any],
        **kwargs,
    ) -> AuditEntry:
        """Log create action."""
        return await self.log(
            action=f"{resource_type}.created",
            action_type=ActionType.CREATE,
            actor_id=actor_id,
            resource_type=resource_type,
            resource_id=resource_id,
            new_values=data,
            **kwargs,
        )
    
    async def log_read(
        self,
        actor_id: str,
        resource_type: str,
        resource_id: str,
        **kwargs,
    ) -> AuditEntry:
        """Log read action."""
        return await self.log(
            action=f"{resource_type}.read",
            action_type=ActionType.READ,
            actor_id=actor_id,
            resource_type=resource_type,
            resource_id=resource_id,
            **kwargs,
        )
    
    async def log_update(
        self,
        actor_id: str,
        resource_type: str,
        resource_id: str,
        old_data: Dict[str, Any],
        new_data: Dict[str, Any],
        **kwargs,
    ) -> AuditEntry:
        """Log update action."""
        return await self.log(
            action=f"{resource_type}.updated",
            action_type=ActionType.UPDATE,
            actor_id=actor_id,
            resource_type=resource_type,
            resource_id=resource_id,
            old_values=old_data,
            new_values=new_data,
            **kwargs,
        )
    
    async def log_delete(
        self,
        actor_id: str,
        resource_type: str,
        resource_id: str,
        data: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> AuditEntry:
        """Log delete action."""
        return await self.log(
            action=f"{resource_type}.deleted",
            action_type=ActionType.DELETE,
            actor_id=actor_id,
            resource_type=resource_type,
            resource_id=resource_id,
            old_values=data,
            **kwargs,
        )
    
    async def query(
        self,
        action: Optional[str] = None,
        action_type: Optional[ActionType] = None,
        actor_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        level: Optional[AuditLevel] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AuditEntry]:
        """
        Query audit entries.
        
        Args:
            action: Filter by action
            action_type: Filter by action type
            actor_id: Filter by actor
            resource_type: Filter by resource type
            resource_id: Filter by resource ID
            level: Filter by level
            start_time: Start time
            end_time: End time
            limit: Max results
            offset: Results offset
            
        Returns:
            List of audit entries
        """
        query = AuditQuery(
            action=action,
            action_type=action_type,
            actor_id=actor_id,
            resource_type=resource_type,
            resource_id=resource_id,
            level=level,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
            offset=offset,
        )
        
        return await self._storage.query(query)
    
    async def get_resource_history(
        self,
        resource_type: str,
        resource_id: str,
        limit: int = 100,
    ) -> List[AuditEntry]:
        """Get history for a resource."""
        return await self.query(
            resource_type=resource_type,
            resource_id=resource_id,
            limit=limit,
        )
    
    async def get_actor_activity(
        self,
        actor_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[AuditEntry]:
        """Get activity for an actor."""
        return await self.query(
            actor_id=actor_id,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )
    
    async def verify_chain(
        self,
        start_id: Optional[str] = None,
        limit: int = 1000,
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify audit chain integrity.
        
        Returns:
            (is_valid, first_invalid_id)
        """
        entries = await self._storage.query(
            AuditQuery(limit=limit)
        )
        
        if not entries:
            return True, None
        
        # Sort by timestamp
        entries = sorted(entries, key=lambda e: e.timestamp)
        
        previous_hash = None
        
        for entry in entries:
            if entry.previous_hash != previous_hash:
                return False, entry.id
            
            computed = entry.compute_hash(previous_hash)
            
            if entry.hash != computed:
                return False, entry.id
            
            previous_hash = entry.hash
        
        return True, None
    
    async def generate_report(
        self,
        report_type: str,
        start: datetime,
        end: datetime,
        standard: Optional[ComplianceStandard] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> ComplianceReport:
        """
        Generate compliance report.
        
        Args:
            report_type: Report type
            start: Start time
            end: End time
            standard: Compliance standard
            filters: Additional filters
            
        Returns:
            Compliance report
        """
        entries = await self.query(
            start_time=start,
            end_time=end,
            limit=10000,
        )
        
        # Apply additional filters
        if filters:
            filtered = []
            for entry in entries:
                match = True
                for key, value in filters.items():
                    if getattr(entry, key, None) != value:
                        match = False
                        break
                if match:
                    filtered.append(entry)
            entries = filtered
        
        # Generate summary
        summary = {
            "total_actions": len(entries),
            "actions_by_type": {},
            "actions_by_actor": {},
            "actions_by_resource": {},
        }
        
        for entry in entries:
            action_type = entry.action_type.value
            summary["actions_by_type"][action_type] = (
                summary["actions_by_type"].get(action_type, 0) + 1
            )
            
            summary["actions_by_actor"][entry.actor_id] = (
                summary["actions_by_actor"].get(entry.actor_id, 0) + 1
            )
            
            resource_key = f"{entry.resource_type}/{entry.resource_id}"
            summary["actions_by_resource"][resource_key] = (
                summary["actions_by_resource"].get(resource_key, 0) + 1
            )
        
        # Generate findings based on standard
        findings = []
        
        if standard == ComplianceStandard.GDPR:
            # Check for data access patterns
            data_access = [
                e for e in entries
                if e.action_type == ActionType.READ
            ]
            if len(data_access) > 1000:
                findings.append(
                    f"High volume of data access ({len(data_access)} reads)"
                )
            
            # Check for exports
            exports = [
                e for e in entries
                if e.action_type == ActionType.EXPORT
            ]
            if exports:
                findings.append(
                    f"Data exports detected: {len(exports)} exports"
                )
        
        elif standard == ComplianceStandard.HIPAA:
            # Check for after-hours access
            after_hours = [
                e for e in entries
                if e.timestamp.hour < 6 or e.timestamp.hour > 22
            ]
            if after_hours:
                findings.append(
                    f"After-hours access detected: {len(after_hours)} entries"
                )
        
        report = ComplianceReport(
            report_type=report_type,
            standard=standard,
            start_time=start,
            end_time=end,
            total_entries=len(entries),
            entries=entries[:100],  # First 100 entries
            summary=summary,
            findings=findings,
        )
        
        return report
    
    async def get_stats(self) -> AuditStats:
        """Get audit statistics."""
        all_entries = await self._storage.query(
            AuditQuery(limit=10000)
        )
        
        stats = AuditStats(
            total_entries=len(all_entries),
        )
        
        for entry in all_entries:
            stats.entries_by_action[entry.action] = (
                stats.entries_by_action.get(entry.action, 0) + 1
            )
            stats.entries_by_actor[entry.actor_id] = (
                stats.entries_by_actor.get(entry.actor_id, 0) + 1
            )
            stats.entries_by_resource[entry.resource_type] = (
                stats.entries_by_resource.get(entry.resource_type, 0) + 1
            )
            stats.entries_by_level[entry.level.value] = (
                stats.entries_by_level.get(entry.level.value, 0) + 1
            )
            
            if not stats.oldest_entry or entry.timestamp < stats.oldest_entry:
                stats.oldest_entry = entry.timestamp
            if not stats.newest_entry or entry.timestamp > stats.newest_entry:
                stats.newest_entry = entry.timestamp
        
        # Verify chain
        valid, _ = await self.verify_chain()
        stats.chain_valid = valid
        
        return stats
    
    def add_filter(
        self,
        filter_fn: Callable[[AuditEntry], bool],
    ) -> None:
        """Add entry filter."""
        self._filters.append(filter_fn)
    
    def on(
        self,
        event: str,
        handler: Callable,
    ) -> None:
        """Add event handler."""
        if event not in self._hooks:
            self._hooks[event] = []
        self._hooks[event].append(handler)
    
    async def _trigger_hooks(
        self,
        event: str,
        *args,
        **kwargs,
    ) -> None:
        """Trigger event hooks."""
        for handler in self._hooks.get(event, []):
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(*args, **kwargs)
                else:
                    handler(*args, **kwargs)
            except Exception as e:
                logger.error(f"Hook error: {e}")
    
    def track_changes(self, key: str, obj: Any) -> None:
        """Start tracking changes to an object."""
        self._change_tracker.snapshot(key, obj)
    
    def get_tracked_changes(self, key: str, obj: Any) -> List[ChangeRecord]:
        """Get tracked changes."""
        return self._change_tracker.get_changes(key, obj)


# Decorator for auditing
def audited(
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    get_resource_id: Optional[Callable] = None,
    get_actor_id: Optional[Callable] = None,
) -> Callable:
    """
    Decorator to auto-audit function calls.
    
    Args:
        action: Action name (default: function name)
        resource_type: Resource type
        get_resource_id: Function to extract resource ID
        get_actor_id: Function to extract actor ID
        
    Returns:
        Decorator
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            audit = _global_audit_trail
            
            if audit:
                actor_id = (
                    get_actor_id(*args, **kwargs)
                    if get_actor_id
                    else kwargs.get("actor_id", "unknown")
                )
                
                resource_id = (
                    get_resource_id(*args, **kwargs)
                    if get_resource_id
                    else kwargs.get("resource_id", "")
                )
                
                try:
                    if asyncio.iscoroutinefunction(func):
                        result = await func(*args, **kwargs)
                    else:
                        result = func(*args, **kwargs)
                    
                    await audit.log(
                        action=action or func.__name__,
                        actor_id=actor_id,
                        resource_type=resource_type or "",
                        resource_id=resource_id,
                        level=AuditLevel.INFO,
                        details={"status": "success"},
                    )
                    
                    return result
                    
                except Exception as e:
                    await audit.log(
                        action=action or func.__name__,
                        actor_id=actor_id,
                        resource_type=resource_type or "",
                        resource_id=resource_id,
                        level=AuditLevel.ERROR,
                        details={"status": "failed", "error": str(e)},
                    )
                    raise
            else:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                return func(*args, **kwargs)
        
        return wrapper
    
    return decorator


# Global audit trail
_global_audit_trail: Optional[AuditTrail] = None


def set_global_audit_trail(audit: AuditTrail) -> None:
    """Set global audit trail."""
    global _global_audit_trail
    _global_audit_trail = audit


def get_global_audit_trail() -> Optional[AuditTrail]:
    """Get global audit trail."""
    return _global_audit_trail


# Factory functions
def create_audit_trail(
    enable_chain: bool = True,
    retention_days: int = 365,
) -> AuditTrail:
    """Create audit trail."""
    audit = AuditTrail(
        enable_chain=enable_chain,
        retention_days=retention_days,
    )
    set_global_audit_trail(audit)
    return audit


def create_change_tracker() -> ChangeTracker:
    """Create change tracker."""
    return ChangeTracker()


__all__ = [
    # Exceptions
    "AuditError",
    "TamperDetectedError",
    # Enums
    "AuditLevel",
    "ActionType",
    "ComplianceStandard",
    # Data classes
    "AuditEntry",
    "ChangeRecord",
    "AuditQuery",
    "ComplianceReport",
    "AuditStats",
    # Storage
    "AuditStorage",
    "InMemoryAuditStorage",
    # Change tracking
    "ChangeTracker",
    # Audit trail
    "AuditTrail",
    # Decorator
    "audited",
    # Global
    "set_global_audit_trail",
    "get_global_audit_trail",
    # Factory functions
    "create_audit_trail",
    "create_change_tracker",
]
