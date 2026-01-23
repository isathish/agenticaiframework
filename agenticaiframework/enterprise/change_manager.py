"""
Enterprise Change Manager Module.

Change request management, approval workflows,
change tracking, and rollback management.

Example:
    # Create change manager
    changes = create_change_manager()
    
    # Create change request
    request = await changes.create(
        title="Update database schema",
        description="Add new user preferences table",
        change_type=ChangeType.STANDARD,
        affected_systems=["database", "api"],
    )
    
    # Submit for approval
    await changes.submit(request.id)
    
    # Approve change
    await changes.approve(request.id, approver="admin@example.com")
    
    # Implement change
    await changes.implement(request.id)
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


class ChangeError(Exception):
    """Change management error."""
    pass


class ApprovalRequired(ChangeError):
    """Approval required."""
    pass


class ChangeType(str, Enum):
    """Change type."""
    STANDARD = "standard"
    NORMAL = "normal"
    EMERGENCY = "emergency"
    EXPEDITED = "expedited"


class ChangeStatus(str, Enum):
    """Change status."""
    DRAFT = "draft"
    SUBMITTED = "submitted"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    CANCELLED = "cancelled"


class ChangeRisk(str, Enum):
    """Change risk level."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ApprovalStatus(str, Enum):
    """Approval status."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ABSTAINED = "abstained"


@dataclass
class Approval:
    """Change approval."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    approver: str = ""
    status: ApprovalStatus = ApprovalStatus.PENDING
    comments: str = ""
    approved_at: Optional[datetime] = None
    required: bool = True


@dataclass
class ChangeHistoryEntry:
    """Change history entry."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: ChangeStatus = ChangeStatus.DRAFT
    message: str = ""
    author: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RollbackPlan:
    """Rollback plan."""
    steps: List[str] = field(default_factory=list)
    estimated_duration: int = 0  # minutes
    requires_downtime: bool = False
    tested: bool = False
    test_date: Optional[datetime] = None


@dataclass
class ImplementationPlan:
    """Implementation plan."""
    steps: List[str] = field(default_factory=list)
    estimated_duration: int = 0  # minutes
    requires_downtime: bool = False
    maintenance_window: Optional[Tuple[datetime, datetime]] = None
    pre_checks: List[str] = field(default_factory=list)
    post_checks: List[str] = field(default_factory=list)


@dataclass
class ChangeRequest:
    """Change request."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: str = ""
    change_type: ChangeType = ChangeType.STANDARD
    status: ChangeStatus = ChangeStatus.DRAFT
    risk: ChangeRisk = ChangeRisk.LOW
    
    # Ownership
    requester: str = ""
    owner: str = ""
    
    # Affected areas
    affected_systems: List[str] = field(default_factory=list)
    affected_services: List[str] = field(default_factory=list)
    
    # Planning
    implementation_plan: ImplementationPlan = field(default_factory=ImplementationPlan)
    rollback_plan: RollbackPlan = field(default_factory=RollbackPlan)
    
    # Scheduling
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    
    # Approvals
    approvals: List[Approval] = field(default_factory=list)
    required_approvers: int = 1
    
    # History
    history: List[ChangeHistoryEntry] = field(default_factory=list)
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    submitted_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Metadata
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_approved(self) -> bool:
        approved_count = sum(
            1 for a in self.approvals
            if a.status == ApprovalStatus.APPROVED
        )
        return approved_count >= self.required_approvers
    
    @property
    def pending_approvals(self) -> List[Approval]:
        return [a for a in self.approvals if a.status == ApprovalStatus.PENDING]


@dataclass
class ChangeStats:
    """Change statistics."""
    total: int = 0
    by_status: Dict[str, int] = field(default_factory=dict)
    by_type: Dict[str, int] = field(default_factory=dict)
    by_risk: Dict[str, int] = field(default_factory=dict)
    success_rate: float = 0.0
    avg_implementation_time: Optional[float] = None


# Change store
class ChangeStore(ABC):
    """Change request storage."""
    
    @abstractmethod
    async def save(self, change: ChangeRequest) -> None:
        pass
    
    @abstractmethod
    async def get(self, change_id: str) -> Optional[ChangeRequest]:
        pass
    
    @abstractmethod
    async def list_changes(
        self,
        status: Optional[List[ChangeStatus]] = None,
        change_type: Optional[List[ChangeType]] = None,
        limit: int = 100,
    ) -> List[ChangeRequest]:
        pass
    
    @abstractmethod
    async def delete(self, change_id: str) -> bool:
        pass


class InMemoryChangeStore(ChangeStore):
    """In-memory change store."""
    
    def __init__(self):
        self._changes: Dict[str, ChangeRequest] = {}
    
    async def save(self, change: ChangeRequest) -> None:
        self._changes[change.id] = change
    
    async def get(self, change_id: str) -> Optional[ChangeRequest]:
        return self._changes.get(change_id)
    
    async def list_changes(
        self,
        status: Optional[List[ChangeStatus]] = None,
        change_type: Optional[List[ChangeType]] = None,
        limit: int = 100,
    ) -> List[ChangeRequest]:
        results = []
        
        for change in self._changes.values():
            if status and change.status not in status:
                continue
            if change_type and change.change_type not in change_type:
                continue
            results.append(change)
        
        results.sort(key=lambda c: c.created_at, reverse=True)
        return results[:limit]
    
    async def delete(self, change_id: str) -> bool:
        if change_id in self._changes:
            del self._changes[change_id]
            return True
        return False


# Approval policy
@dataclass
class ApprovalPolicy:
    """Approval policy."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    required_approvers: int = 1
    approver_roles: List[str] = field(default_factory=list)
    auto_approve_low_risk: bool = False
    emergency_bypass: bool = False
    timeout_hours: int = 72


# Change manager
class ChangeManager:
    """Change manager."""
    
    def __init__(
        self,
        change_store: Optional[ChangeStore] = None,
    ):
        self._change_store = change_store or InMemoryChangeStore()
        self._policies: Dict[str, ApprovalPolicy] = {}
        self._listeners: List[Callable] = []
        self._default_policy = ApprovalPolicy(
            name="default",
            required_approvers=1,
        )
    
    async def create(
        self,
        title: str,
        description: str = "",
        change_type: Union[str, ChangeType] = ChangeType.STANDARD,
        risk: Union[str, ChangeRisk] = ChangeRisk.LOW,
        requester: str = "",
        owner: str = "",
        affected_systems: Optional[List[str]] = None,
        affected_services: Optional[List[str]] = None,
        implementation_steps: Optional[List[str]] = None,
        rollback_steps: Optional[List[str]] = None,
        **metadata,
    ) -> ChangeRequest:
        """Create change request."""
        if isinstance(change_type, str):
            change_type = ChangeType(change_type)
        if isinstance(risk, str):
            risk = ChangeRisk(risk)
        
        change = ChangeRequest(
            title=title,
            description=description,
            change_type=change_type,
            risk=risk,
            requester=requester,
            owner=owner or requester,
            affected_systems=affected_systems or [],
            affected_services=affected_services or [],
            metadata=metadata,
        )
        
        if implementation_steps:
            change.implementation_plan.steps = implementation_steps
        
        if rollback_steps:
            change.rollback_plan.steps = rollback_steps
        
        # Add history entry
        change.history.append(ChangeHistoryEntry(
            status=ChangeStatus.DRAFT,
            message="Change request created",
            author=requester,
        ))
        
        await self._change_store.save(change)
        
        logger.info(f"Change request created: {change.id} - {title}")
        
        await self._notify_listeners("created", change)
        
        return change
    
    async def get(self, change_id: str) -> Optional[ChangeRequest]:
        """Get change request."""
        return await self._change_store.get(change_id)
    
    async def update(
        self,
        change_id: str,
        author: str = "",
        **updates,
    ) -> Optional[ChangeRequest]:
        """Update change request."""
        change = await self._change_store.get(change_id)
        
        if not change:
            return None
        
        if change.status not in (ChangeStatus.DRAFT, ChangeStatus.REJECTED):
            raise ChangeError("Can only update draft or rejected changes")
        
        for key, value in updates.items():
            if hasattr(change, key):
                setattr(change, key, value)
        
        change.history.append(ChangeHistoryEntry(
            status=change.status,
            message=f"Change updated: {', '.join(updates.keys())}",
            author=author,
        ))
        
        await self._change_store.save(change)
        
        return change
    
    async def submit(
        self,
        change_id: str,
        author: str = "",
    ) -> Optional[ChangeRequest]:
        """Submit change for approval."""
        change = await self._change_store.get(change_id)
        
        if not change:
            return None
        
        if change.status != ChangeStatus.DRAFT:
            raise ChangeError("Can only submit draft changes")
        
        # Get approval policy
        policy = self._get_policy(change)
        
        # Check for auto-approve
        if policy.auto_approve_low_risk and change.risk == ChangeRisk.LOW:
            change.status = ChangeStatus.APPROVED
            change.approved_at = datetime.utcnow()
            
            change.history.append(ChangeHistoryEntry(
                status=ChangeStatus.APPROVED,
                message="Auto-approved (low risk)",
                author="system",
            ))
        else:
            change.status = ChangeStatus.PENDING_APPROVAL
            change.required_approvers = policy.required_approvers
        
        change.submitted_at = datetime.utcnow()
        
        change.history.append(ChangeHistoryEntry(
            status=change.status,
            message="Change submitted for approval",
            author=author,
        ))
        
        await self._change_store.save(change)
        
        await self._notify_listeners("submitted", change)
        
        return change
    
    async def add_approver(
        self,
        change_id: str,
        approver: str,
        required: bool = True,
    ) -> Optional[ChangeRequest]:
        """Add approver to change."""
        change = await self._change_store.get(change_id)
        
        if not change:
            return None
        
        approval = Approval(
            approver=approver,
            required=required,
        )
        
        change.approvals.append(approval)
        
        await self._change_store.save(change)
        
        return change
    
    async def approve(
        self,
        change_id: str,
        approver: str,
        comments: str = "",
    ) -> Optional[ChangeRequest]:
        """Approve change."""
        change = await self._change_store.get(change_id)
        
        if not change:
            return None
        
        if change.status != ChangeStatus.PENDING_APPROVAL:
            raise ChangeError("Change is not pending approval")
        
        # Find or create approval
        approval = None
        for a in change.approvals:
            if a.approver == approver:
                approval = a
                break
        
        if not approval:
            approval = Approval(approver=approver)
            change.approvals.append(approval)
        
        approval.status = ApprovalStatus.APPROVED
        approval.comments = comments
        approval.approved_at = datetime.utcnow()
        
        change.history.append(ChangeHistoryEntry(
            status=change.status,
            message=f"Approved by {approver}" + (f": {comments}" if comments else ""),
            author=approver,
        ))
        
        # Check if fully approved
        if change.is_approved:
            change.status = ChangeStatus.APPROVED
            change.approved_at = datetime.utcnow()
            
            change.history.append(ChangeHistoryEntry(
                status=ChangeStatus.APPROVED,
                message="All required approvals received",
                author="system",
            ))
        
        await self._change_store.save(change)
        
        if change.is_approved:
            await self._notify_listeners("approved", change)
        
        return change
    
    async def reject(
        self,
        change_id: str,
        approver: str,
        reason: str = "",
    ) -> Optional[ChangeRequest]:
        """Reject change."""
        change = await self._change_store.get(change_id)
        
        if not change:
            return None
        
        if change.status != ChangeStatus.PENDING_APPROVAL:
            raise ChangeError("Change is not pending approval")
        
        # Find or create approval
        approval = None
        for a in change.approvals:
            if a.approver == approver:
                approval = a
                break
        
        if not approval:
            approval = Approval(approver=approver)
            change.approvals.append(approval)
        
        approval.status = ApprovalStatus.REJECTED
        approval.comments = reason
        approval.approved_at = datetime.utcnow()
        
        change.status = ChangeStatus.REJECTED
        
        change.history.append(ChangeHistoryEntry(
            status=ChangeStatus.REJECTED,
            message=f"Rejected by {approver}: {reason}",
            author=approver,
        ))
        
        await self._change_store.save(change)
        
        await self._notify_listeners("rejected", change)
        
        return change
    
    async def schedule(
        self,
        change_id: str,
        start_time: datetime,
        end_time: Optional[datetime] = None,
        author: str = "",
    ) -> Optional[ChangeRequest]:
        """Schedule change implementation."""
        change = await self._change_store.get(change_id)
        
        if not change:
            return None
        
        if change.status != ChangeStatus.APPROVED:
            raise ApprovalRequired("Change must be approved before scheduling")
        
        change.status = ChangeStatus.SCHEDULED
        change.scheduled_start = start_time
        change.scheduled_end = end_time or start_time + timedelta(hours=2)
        
        change.history.append(ChangeHistoryEntry(
            status=ChangeStatus.SCHEDULED,
            message=f"Scheduled for {start_time.isoformat()}",
            author=author,
        ))
        
        await self._change_store.save(change)
        
        await self._notify_listeners("scheduled", change)
        
        return change
    
    async def implement(
        self,
        change_id: str,
        author: str = "",
    ) -> Optional[ChangeRequest]:
        """Start change implementation."""
        change = await self._change_store.get(change_id)
        
        if not change:
            return None
        
        if change.status not in (ChangeStatus.APPROVED, ChangeStatus.SCHEDULED):
            raise ChangeError("Change must be approved or scheduled to implement")
        
        # Check for emergency bypass
        policy = self._get_policy(change)
        if change.change_type != ChangeType.EMERGENCY or not policy.emergency_bypass:
            if not change.is_approved:
                raise ApprovalRequired("Change requires approval before implementation")
        
        change.status = ChangeStatus.IN_PROGRESS
        change.actual_start = datetime.utcnow()
        
        change.history.append(ChangeHistoryEntry(
            status=ChangeStatus.IN_PROGRESS,
            message="Implementation started",
            author=author,
        ))
        
        await self._change_store.save(change)
        
        await self._notify_listeners("started", change)
        
        return change
    
    async def complete(
        self,
        change_id: str,
        notes: str = "",
        author: str = "",
    ) -> Optional[ChangeRequest]:
        """Complete change implementation."""
        change = await self._change_store.get(change_id)
        
        if not change:
            return None
        
        if change.status != ChangeStatus.IN_PROGRESS:
            raise ChangeError("Change must be in progress to complete")
        
        change.status = ChangeStatus.COMPLETED
        change.actual_end = datetime.utcnow()
        change.completed_at = datetime.utcnow()
        
        change.history.append(ChangeHistoryEntry(
            status=ChangeStatus.COMPLETED,
            message=f"Implementation completed" + (f": {notes}" if notes else ""),
            author=author,
        ))
        
        await self._change_store.save(change)
        
        await self._notify_listeners("completed", change)
        
        return change
    
    async def fail(
        self,
        change_id: str,
        reason: str,
        author: str = "",
    ) -> Optional[ChangeRequest]:
        """Mark change as failed."""
        change = await self._change_store.get(change_id)
        
        if not change:
            return None
        
        if change.status != ChangeStatus.IN_PROGRESS:
            raise ChangeError("Change must be in progress to fail")
        
        change.status = ChangeStatus.FAILED
        change.actual_end = datetime.utcnow()
        
        change.history.append(ChangeHistoryEntry(
            status=ChangeStatus.FAILED,
            message=f"Implementation failed: {reason}",
            author=author,
        ))
        
        await self._change_store.save(change)
        
        await self._notify_listeners("failed", change)
        
        return change
    
    async def rollback(
        self,
        change_id: str,
        reason: str = "",
        author: str = "",
    ) -> Optional[ChangeRequest]:
        """Rollback change."""
        change = await self._change_store.get(change_id)
        
        if not change:
            return None
        
        if change.status not in (ChangeStatus.IN_PROGRESS, ChangeStatus.FAILED, ChangeStatus.COMPLETED):
            raise ChangeError("Cannot rollback change in current state")
        
        change.status = ChangeStatus.ROLLED_BACK
        
        change.history.append(ChangeHistoryEntry(
            status=ChangeStatus.ROLLED_BACK,
            message=f"Change rolled back" + (f": {reason}" if reason else ""),
            author=author,
        ))
        
        await self._change_store.save(change)
        
        await self._notify_listeners("rolled_back", change)
        
        return change
    
    async def cancel(
        self,
        change_id: str,
        reason: str = "",
        author: str = "",
    ) -> Optional[ChangeRequest]:
        """Cancel change."""
        change = await self._change_store.get(change_id)
        
        if not change:
            return None
        
        if change.status in (ChangeStatus.COMPLETED, ChangeStatus.CANCELLED):
            raise ChangeError("Cannot cancel completed or already cancelled change")
        
        change.status = ChangeStatus.CANCELLED
        
        change.history.append(ChangeHistoryEntry(
            status=ChangeStatus.CANCELLED,
            message=f"Change cancelled" + (f": {reason}" if reason else ""),
            author=author,
        ))
        
        await self._change_store.save(change)
        
        await self._notify_listeners("cancelled", change)
        
        return change
    
    async def list_changes(
        self,
        status: Optional[List[ChangeStatus]] = None,
        change_type: Optional[List[ChangeType]] = None,
        limit: int = 100,
    ) -> List[ChangeRequest]:
        """List changes."""
        return await self._change_store.list_changes(status, change_type, limit)
    
    async def get_pending_approvals(self) -> List[ChangeRequest]:
        """Get changes pending approval."""
        return await self._change_store.list_changes(
            status=[ChangeStatus.PENDING_APPROVAL]
        )
    
    async def get_scheduled_changes(self) -> List[ChangeRequest]:
        """Get scheduled changes."""
        return await self._change_store.list_changes(
            status=[ChangeStatus.SCHEDULED]
        )
    
    def set_policy(self, policy: ApprovalPolicy) -> None:
        """Set approval policy."""
        self._policies[policy.name] = policy
    
    def _get_policy(self, change: ChangeRequest) -> ApprovalPolicy:
        """Get policy for change."""
        # Could be extended to select policy based on change type, risk, etc.
        return self._policies.get("default", self._default_policy)
    
    async def get_stats(self, period_days: int = 30) -> ChangeStats:
        """Get change statistics."""
        all_changes = await self._change_store.list_changes(limit=10000)
        
        cutoff = datetime.utcnow() - timedelta(days=period_days)
        changes = [c for c in all_changes if c.created_at >= cutoff]
        
        stats = ChangeStats(total=len(changes))
        
        completed = 0
        failed = 0
        impl_times = []
        
        for change in changes:
            # By status
            status = change.status.value
            stats.by_status[status] = stats.by_status.get(status, 0) + 1
            
            # By type
            ctype = change.change_type.value
            stats.by_type[ctype] = stats.by_type.get(ctype, 0) + 1
            
            # By risk
            risk = change.risk.value
            stats.by_risk[risk] = stats.by_risk.get(risk, 0) + 1
            
            # Success tracking
            if change.status == ChangeStatus.COMPLETED:
                completed += 1
                if change.actual_start and change.actual_end:
                    impl_times.append((change.actual_end - change.actual_start).total_seconds())
            elif change.status == ChangeStatus.FAILED:
                failed += 1
        
        total_impl = completed + failed
        if total_impl > 0:
            stats.success_rate = completed / total_impl * 100
        
        if impl_times:
            stats.avg_implementation_time = sum(impl_times) / len(impl_times)
        
        return stats
    
    def add_listener(self, listener: Callable) -> None:
        """Add event listener."""
        self._listeners.append(listener)
    
    async def _notify_listeners(self, event: str, change: ChangeRequest) -> None:
        """Notify listeners."""
        for listener in self._listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    await listener(event, change)
                else:
                    listener(event, change)
            except Exception as e:
                logger.error(f"Listener error: {e}")


# Factory functions
def create_change_manager() -> ChangeManager:
    """Create change manager."""
    return ChangeManager()


def create_change_request(
    title: str,
    **kwargs,
) -> ChangeRequest:
    """Create change request."""
    return ChangeRequest(title=title, **kwargs)


def create_approval_policy(
    name: str,
    required_approvers: int = 1,
    **kwargs,
) -> ApprovalPolicy:
    """Create approval policy."""
    return ApprovalPolicy(name=name, required_approvers=required_approvers, **kwargs)


__all__ = [
    # Exceptions
    "ChangeError",
    "ApprovalRequired",
    # Enums
    "ChangeType",
    "ChangeStatus",
    "ChangeRisk",
    "ApprovalStatus",
    # Data classes
    "Approval",
    "ChangeHistoryEntry",
    "RollbackPlan",
    "ImplementationPlan",
    "ChangeRequest",
    "ChangeStats",
    "ApprovalPolicy",
    # Stores
    "ChangeStore",
    "InMemoryChangeStore",
    # Manager
    "ChangeManager",
    # Factory functions
    "create_change_manager",
    "create_change_request",
    "create_approval_policy",
]
