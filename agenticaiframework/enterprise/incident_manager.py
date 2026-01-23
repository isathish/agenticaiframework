"""
Enterprise Incident Manager Module.

Incident tracking, escalation workflows,
on-call management, and incident response.

Example:
    # Create incident manager
    incidents = create_incident_manager()
    
    # Create incident
    incident = await incidents.create(
        title="Database connection failure",
        severity=Severity.HIGH,
        affected_services=["api", "web"],
    )
    
    # Update status
    await incidents.update_status(
        incident_id=incident.id,
        status=IncidentStatus.INVESTIGATING,
    )
    
    # Add timeline entry
    await incidents.add_timeline_entry(
        incident_id=incident.id,
        message="Root cause identified: connection pool exhausted",
    )
    
    # Resolve incident
    await incidents.resolve(
        incident_id=incident.id,
        resolution="Increased connection pool size",
    )
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Union,
)

logger = logging.getLogger(__name__)


class IncidentError(Exception):
    """Incident error."""
    pass


class Severity(str, Enum):
    """Incident severity."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentStatus(str, Enum):
    """Incident status."""
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    INVESTIGATING = "investigating"
    IDENTIFIED = "identified"
    MONITORING = "monitoring"
    RESOLVED = "resolved"
    CLOSED = "closed"


class EscalationLevel(str, Enum):
    """Escalation level."""
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    MANAGEMENT = "management"
    EXECUTIVE = "executive"


class TimelineEntryType(str, Enum):
    """Timeline entry type."""
    STATUS_CHANGE = "status_change"
    COMMENT = "comment"
    ESCALATION = "escalation"
    ASSIGNMENT = "assignment"
    ACTION = "action"
    NOTIFICATION = "notification"


@dataclass
class TimelineEntry:
    """Incident timeline entry."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    entry_type: TimelineEntryType = TimelineEntryType.COMMENT
    message: str = ""
    author: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Responder:
    """Incident responder."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    email: str = ""
    role: str = ""
    escalation_level: EscalationLevel = EscalationLevel.L1
    on_call: bool = False
    notification_methods: List[str] = field(default_factory=list)


@dataclass
class EscalationPolicy:
    """Escalation policy."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    levels: Dict[EscalationLevel, List[str]] = field(default_factory=dict)
    escalation_timeout: int = 30  # minutes
    auto_escalate: bool = True
    notify_all_levels: bool = False


@dataclass
class Incident:
    """Incident."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: str = ""
    severity: Severity = Severity.MEDIUM
    status: IncidentStatus = IncidentStatus.OPEN
    affected_services: List[str] = field(default_factory=list)
    tags: Dict[str, str] = field(default_factory=dict)
    assignee: Optional[str] = None
    escalation_level: EscalationLevel = EscalationLevel.L1
    timeline: List[TimelineEntry] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    resolution: str = ""
    root_cause: str = ""
    impact: str = ""
    customer_impact: bool = False
    public: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def duration(self) -> Optional[timedelta]:
        if self.resolved_at:
            return self.resolved_at - self.created_at
        return datetime.utcnow() - self.created_at
    
    @property
    def time_to_acknowledge(self) -> Optional[timedelta]:
        if self.acknowledged_at:
            return self.acknowledged_at - self.created_at
        return None
    
    @property
    def time_to_resolve(self) -> Optional[timedelta]:
        if self.resolved_at:
            return self.resolved_at - self.created_at
        return None


@dataclass
class IncidentStats:
    """Incident statistics."""
    total: int = 0
    open: int = 0
    resolved: int = 0
    by_severity: Dict[str, int] = field(default_factory=dict)
    by_status: Dict[str, int] = field(default_factory=dict)
    avg_time_to_resolve: Optional[float] = None
    avg_time_to_acknowledge: Optional[float] = None


@dataclass
class PostMortem:
    """Incident post-mortem."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    title: str = ""
    summary: str = ""
    timeline: List[TimelineEntry] = field(default_factory=list)
    root_cause: str = ""
    contributing_factors: List[str] = field(default_factory=list)
    lessons_learned: List[str] = field(default_factory=list)
    action_items: List[Dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    author: str = ""


# Incident store
class IncidentStore(ABC):
    """Incident storage."""
    
    @abstractmethod
    async def save(self, incident: Incident) -> None:
        pass
    
    @abstractmethod
    async def get(self, incident_id: str) -> Optional[Incident]:
        pass
    
    @abstractmethod
    async def list_incidents(
        self,
        status: Optional[List[IncidentStatus]] = None,
        severity: Optional[List[Severity]] = None,
        limit: int = 100,
    ) -> List[Incident]:
        pass
    
    @abstractmethod
    async def delete(self, incident_id: str) -> bool:
        pass


class InMemoryIncidentStore(IncidentStore):
    """In-memory incident store."""
    
    def __init__(self):
        self._incidents: Dict[str, Incident] = {}
    
    async def save(self, incident: Incident) -> None:
        self._incidents[incident.id] = incident
    
    async def get(self, incident_id: str) -> Optional[Incident]:
        return self._incidents.get(incident_id)
    
    async def list_incidents(
        self,
        status: Optional[List[IncidentStatus]] = None,
        severity: Optional[List[Severity]] = None,
        limit: int = 100,
    ) -> List[Incident]:
        results = []
        
        for incident in self._incidents.values():
            if status and incident.status not in status:
                continue
            if severity and incident.severity not in severity:
                continue
            results.append(incident)
        
        results.sort(key=lambda i: i.created_at, reverse=True)
        return results[:limit]
    
    async def delete(self, incident_id: str) -> bool:
        if incident_id in self._incidents:
            del self._incidents[incident_id]
            return True
        return False


# Responder store
class ResponderStore(ABC):
    """Responder storage."""
    
    @abstractmethod
    async def save(self, responder: Responder) -> None:
        pass
    
    @abstractmethod
    async def get(self, responder_id: str) -> Optional[Responder]:
        pass
    
    @abstractmethod
    async def get_on_call(self, level: EscalationLevel) -> List[Responder]:
        pass
    
    @abstractmethod
    async def list_all(self) -> List[Responder]:
        pass


class InMemoryResponderStore(ResponderStore):
    """In-memory responder store."""
    
    def __init__(self):
        self._responders: Dict[str, Responder] = {}
    
    async def save(self, responder: Responder) -> None:
        self._responders[responder.id] = responder
    
    async def get(self, responder_id: str) -> Optional[Responder]:
        return self._responders.get(responder_id)
    
    async def get_on_call(self, level: EscalationLevel) -> List[Responder]:
        return [
            r for r in self._responders.values()
            if r.on_call and r.escalation_level == level
        ]
    
    async def list_all(self) -> List[Responder]:
        return list(self._responders.values())


# Notifier
class Notifier(ABC):
    """Notification interface."""
    
    @abstractmethod
    async def notify(
        self,
        incident: Incident,
        responders: List[Responder],
        message: str,
    ) -> None:
        pass


class LogNotifier(Notifier):
    """Log-based notifier for testing."""
    
    async def notify(
        self,
        incident: Incident,
        responders: List[Responder],
        message: str,
    ) -> None:
        for responder in responders:
            logger.info(
                f"Notification to {responder.name} ({responder.email}): "
                f"[{incident.severity.value.upper()}] {incident.title} - {message}"
            )


# Incident manager
class IncidentManager:
    """Incident manager."""
    
    def __init__(
        self,
        incident_store: Optional[IncidentStore] = None,
        responder_store: Optional[ResponderStore] = None,
        notifier: Optional[Notifier] = None,
    ):
        self._incident_store = incident_store or InMemoryIncidentStore()
        self._responder_store = responder_store or InMemoryResponderStore()
        self._notifier = notifier or LogNotifier()
        self._escalation_policies: Dict[str, EscalationPolicy] = {}
        self._listeners: List[Callable] = []
    
    async def create(
        self,
        title: str,
        severity: Union[str, Severity] = Severity.MEDIUM,
        description: str = "",
        affected_services: Optional[List[str]] = None,
        tags: Optional[Dict[str, str]] = None,
        customer_impact: bool = False,
        **metadata,
    ) -> Incident:
        """Create incident."""
        if isinstance(severity, str):
            severity = Severity(severity)
        
        incident = Incident(
            title=title,
            description=description,
            severity=severity,
            affected_services=affected_services or [],
            tags=tags or {},
            customer_impact=customer_impact,
            metadata=metadata,
        )
        
        # Add creation timeline entry
        incident.timeline.append(TimelineEntry(
            entry_type=TimelineEntryType.STATUS_CHANGE,
            message=f"Incident created with severity {severity.value}",
        ))
        
        await self._incident_store.save(incident)
        
        logger.info(f"Incident created: {incident.id} - {title}")
        
        # Notify on-call responders
        await self._notify_on_call(incident, "New incident created")
        
        # Notify listeners
        await self._notify_listeners("created", incident)
        
        return incident
    
    async def get(self, incident_id: str) -> Optional[Incident]:
        """Get incident."""
        return await self._incident_store.get(incident_id)
    
    async def update_status(
        self,
        incident_id: str,
        status: Union[str, IncidentStatus],
        message: str = "",
        author: str = "",
    ) -> Optional[Incident]:
        """Update incident status."""
        if isinstance(status, str):
            status = IncidentStatus(status)
        
        incident = await self._incident_store.get(incident_id)
        
        if not incident:
            return None
        
        old_status = incident.status
        incident.status = status
        
        if status == IncidentStatus.ACKNOWLEDGED and not incident.acknowledged_at:
            incident.acknowledged_at = datetime.utcnow()
        elif status == IncidentStatus.RESOLVED and not incident.resolved_at:
            incident.resolved_at = datetime.utcnow()
        elif status == IncidentStatus.CLOSED and not incident.closed_at:
            incident.closed_at = datetime.utcnow()
        
        incident.timeline.append(TimelineEntry(
            entry_type=TimelineEntryType.STATUS_CHANGE,
            message=message or f"Status changed from {old_status.value} to {status.value}",
            author=author,
        ))
        
        await self._incident_store.save(incident)
        
        logger.info(f"Incident {incident_id} status: {old_status.value} -> {status.value}")
        
        await self._notify_listeners("status_changed", incident)
        
        return incident
    
    async def add_timeline_entry(
        self,
        incident_id: str,
        message: str,
        entry_type: TimelineEntryType = TimelineEntryType.COMMENT,
        author: str = "",
        **metadata,
    ) -> Optional[TimelineEntry]:
        """Add timeline entry."""
        incident = await self._incident_store.get(incident_id)
        
        if not incident:
            return None
        
        entry = TimelineEntry(
            entry_type=entry_type,
            message=message,
            author=author,
            metadata=metadata,
        )
        
        incident.timeline.append(entry)
        
        await self._incident_store.save(incident)
        
        return entry
    
    async def assign(
        self,
        incident_id: str,
        assignee: str,
        author: str = "",
    ) -> Optional[Incident]:
        """Assign incident."""
        incident = await self._incident_store.get(incident_id)
        
        if not incident:
            return None
        
        old_assignee = incident.assignee
        incident.assignee = assignee
        
        incident.timeline.append(TimelineEntry(
            entry_type=TimelineEntryType.ASSIGNMENT,
            message=f"Assigned to {assignee}" + (f" from {old_assignee}" if old_assignee else ""),
            author=author,
        ))
        
        await self._incident_store.save(incident)
        
        return incident
    
    async def escalate(
        self,
        incident_id: str,
        level: Union[str, EscalationLevel],
        reason: str = "",
        author: str = "",
    ) -> Optional[Incident]:
        """Escalate incident."""
        if isinstance(level, str):
            level = EscalationLevel(level)
        
        incident = await self._incident_store.get(incident_id)
        
        if not incident:
            return None
        
        old_level = incident.escalation_level
        incident.escalation_level = level
        
        incident.timeline.append(TimelineEntry(
            entry_type=TimelineEntryType.ESCALATION,
            message=f"Escalated from {old_level.value} to {level.value}" + (f": {reason}" if reason else ""),
            author=author,
        ))
        
        await self._incident_store.save(incident)
        
        # Notify new level responders
        responders = await self._responder_store.get_on_call(level)
        await self._notifier.notify(incident, responders, f"Incident escalated to {level.value}")
        
        logger.info(f"Incident {incident_id} escalated to {level.value}")
        
        await self._notify_listeners("escalated", incident)
        
        return incident
    
    async def resolve(
        self,
        incident_id: str,
        resolution: str,
        root_cause: str = "",
        author: str = "",
    ) -> Optional[Incident]:
        """Resolve incident."""
        incident = await self._incident_store.get(incident_id)
        
        if not incident:
            return None
        
        incident.status = IncidentStatus.RESOLVED
        incident.resolved_at = datetime.utcnow()
        incident.resolution = resolution
        incident.root_cause = root_cause
        
        incident.timeline.append(TimelineEntry(
            entry_type=TimelineEntryType.STATUS_CHANGE,
            message=f"Incident resolved: {resolution}",
            author=author,
        ))
        
        await self._incident_store.save(incident)
        
        logger.info(f"Incident {incident_id} resolved")
        
        await self._notify_listeners("resolved", incident)
        
        return incident
    
    async def close(
        self,
        incident_id: str,
        author: str = "",
    ) -> Optional[Incident]:
        """Close incident."""
        incident = await self._incident_store.get(incident_id)
        
        if not incident:
            return None
        
        incident.status = IncidentStatus.CLOSED
        incident.closed_at = datetime.utcnow()
        
        incident.timeline.append(TimelineEntry(
            entry_type=TimelineEntryType.STATUS_CHANGE,
            message="Incident closed",
            author=author,
        ))
        
        await self._incident_store.save(incident)
        
        await self._notify_listeners("closed", incident)
        
        return incident
    
    async def list_incidents(
        self,
        status: Optional[List[IncidentStatus]] = None,
        severity: Optional[List[Severity]] = None,
        limit: int = 100,
    ) -> List[Incident]:
        """List incidents."""
        return await self._incident_store.list_incidents(status, severity, limit)
    
    async def get_open_incidents(self) -> List[Incident]:
        """Get open incidents."""
        return await self._incident_store.list_incidents(
            status=[
                IncidentStatus.OPEN,
                IncidentStatus.ACKNOWLEDGED,
                IncidentStatus.INVESTIGATING,
                IncidentStatus.IDENTIFIED,
                IncidentStatus.MONITORING,
            ]
        )
    
    async def add_responder(
        self,
        name: str,
        email: str,
        level: EscalationLevel = EscalationLevel.L1,
        on_call: bool = False,
        **kwargs,
    ) -> Responder:
        """Add responder."""
        responder = Responder(
            name=name,
            email=email,
            escalation_level=level,
            on_call=on_call,
            **kwargs,
        )
        
        await self._responder_store.save(responder)
        
        return responder
    
    async def set_on_call(
        self,
        responder_id: str,
        on_call: bool,
    ) -> Optional[Responder]:
        """Set responder on-call status."""
        responder = await self._responder_store.get(responder_id)
        
        if responder:
            responder.on_call = on_call
            await self._responder_store.save(responder)
        
        return responder
    
    async def get_stats(self, period_days: int = 30) -> IncidentStats:
        """Get incident statistics."""
        all_incidents = await self._incident_store.list_incidents(limit=10000)
        
        cutoff = datetime.utcnow() - timedelta(days=period_days)
        incidents = [i for i in all_incidents if i.created_at >= cutoff]
        
        stats = IncidentStats(
            total=len(incidents),
        )
        
        resolved_times = []
        ack_times = []
        
        for incident in incidents:
            # By status
            status = incident.status.value
            stats.by_status[status] = stats.by_status.get(status, 0) + 1
            
            if incident.status == IncidentStatus.RESOLVED or incident.status == IncidentStatus.CLOSED:
                stats.resolved += 1
            else:
                stats.open += 1
            
            # By severity
            severity = incident.severity.value
            stats.by_severity[severity] = stats.by_severity.get(severity, 0) + 1
            
            # Times
            if incident.time_to_resolve:
                resolved_times.append(incident.time_to_resolve.total_seconds())
            if incident.time_to_acknowledge:
                ack_times.append(incident.time_to_acknowledge.total_seconds())
        
        if resolved_times:
            stats.avg_time_to_resolve = sum(resolved_times) / len(resolved_times)
        if ack_times:
            stats.avg_time_to_acknowledge = sum(ack_times) / len(ack_times)
        
        return stats
    
    async def create_post_mortem(
        self,
        incident_id: str,
        summary: str = "",
        root_cause: str = "",
        lessons_learned: Optional[List[str]] = None,
        action_items: Optional[List[Dict[str, Any]]] = None,
        author: str = "",
    ) -> Optional[PostMortem]:
        """Create post-mortem for incident."""
        incident = await self._incident_store.get(incident_id)
        
        if not incident:
            return None
        
        post_mortem = PostMortem(
            incident_id=incident_id,
            title=f"Post-Mortem: {incident.title}",
            summary=summary or incident.description,
            timeline=incident.timeline.copy(),
            root_cause=root_cause or incident.root_cause,
            lessons_learned=lessons_learned or [],
            action_items=action_items or [],
            author=author,
        )
        
        return post_mortem
    
    def add_listener(self, listener: Callable) -> None:
        """Add event listener."""
        self._listeners.append(listener)
    
    async def _notify_on_call(self, incident: Incident, message: str) -> None:
        """Notify on-call responders."""
        responders = await self._responder_store.get_on_call(incident.escalation_level)
        
        if responders:
            await self._notifier.notify(incident, responders, message)
    
    async def _notify_listeners(self, event: str, incident: Incident) -> None:
        """Notify listeners."""
        for listener in self._listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    await listener(event, incident)
                else:
                    listener(event, incident)
            except Exception as e:
                logger.error(f"Listener error: {e}")


# Factory functions
def create_incident_manager() -> IncidentManager:
    """Create incident manager."""
    return IncidentManager()


def create_incident(
    title: str,
    severity: Severity = Severity.MEDIUM,
    **kwargs,
) -> Incident:
    """Create incident."""
    return Incident(title=title, severity=severity, **kwargs)


def create_responder(
    name: str,
    email: str,
    **kwargs,
) -> Responder:
    """Create responder."""
    return Responder(name=name, email=email, **kwargs)


__all__ = [
    # Exceptions
    "IncidentError",
    # Enums
    "Severity",
    "IncidentStatus",
    "EscalationLevel",
    "TimelineEntryType",
    # Data classes
    "TimelineEntry",
    "Responder",
    "EscalationPolicy",
    "Incident",
    "IncidentStats",
    "PostMortem",
    # Stores
    "IncidentStore",
    "InMemoryIncidentStore",
    "ResponderStore",
    "InMemoryResponderStore",
    # Notifier
    "Notifier",
    "LogNotifier",
    # Manager
    "IncidentManager",
    # Factory functions
    "create_incident_manager",
    "create_incident",
    "create_responder",
]
