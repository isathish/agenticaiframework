"""
Enterprise Approval System Module.

Multi-level approvals, routing, escalation,
delegation, and approval management.

Example:
    # Create approval system
    approvals = create_approval_system()
    
    # Define approval workflow
    workflow = await approvals.create_workflow(
        name="Expense Approval",
        levels=[
            {"role": "manager", "threshold": 1000},
            {"role": "director", "threshold": 5000},
            {"role": "cfo", "threshold": float("inf")},
        ],
    )
    
    # Submit for approval
    request = await approvals.submit(
        workflow_id=workflow.id,
        requester_id="user_123",
        title="Conference Travel",
        amount=2500,
        data={"purpose": "Tech conference"},
    )
    
    # Approve
    await approvals.approve(request.id, approver_id="manager_456", comments="Approved")
"""

from __future__ import annotations

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


class ApprovalError(Exception):
    """Approval error."""
    pass


class RequestNotFoundError(ApprovalError):
    """Request not found."""
    pass


class ApprovalNotAllowedError(ApprovalError):
    """Approval not allowed."""
    pass


class ApprovalStatus(str, Enum):
    """Approval status."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"
    DELEGATED = "delegated"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class RequestStatus(str, Enum):
    """Request status."""
    DRAFT = "draft"
    SUBMITTED = "submitted"
    IN_PROGRESS = "in_progress"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class EscalationReason(str, Enum):
    """Escalation reason."""
    TIMEOUT = "timeout"
    MANUAL = "manual"
    THRESHOLD = "threshold"
    POLICY = "policy"


@dataclass
class ApprovalLevel:
    """Approval level."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    order: int = 0
    name: str = ""
    role: str = ""
    approvers: List[str] = field(default_factory=list)
    required_count: int = 1  # How many approvers needed
    threshold: float = float("inf")  # Amount threshold
    timeout_hours: int = 72
    auto_approve: bool = False
    auto_escalate: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ApprovalWorkflow:
    """Approval workflow."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    levels: List[ApprovalLevel] = field(default_factory=list)
    require_sequential: bool = True
    allow_delegation: bool = True
    allow_recall: bool = True
    notify_on_action: bool = True
    created_by: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ApprovalAction:
    """Approval action."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    level_id: str = ""
    approver_id: str = ""
    status: ApprovalStatus = ApprovalStatus.PENDING
    comments: str = ""
    delegated_to: Optional[str] = None
    delegated_by: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ApprovalRequest:
    """Approval request."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    workflow_id: str = ""
    workflow_name: str = ""
    status: RequestStatus = RequestStatus.DRAFT
    requester_id: str = ""
    title: str = ""
    description: str = ""
    amount: float = 0.0
    data: Dict[str, Any] = field(default_factory=dict)
    current_level: int = 0
    actions: List[ApprovalAction] = field(default_factory=list)
    attachments: List[str] = field(default_factory=list)
    due_date: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    final_status: Optional[ApprovalStatus] = None
    final_comments: str = ""
    correlation_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ApprovalStats:
    """Approval statistics."""
    total_requests: int = 0
    pending_requests: int = 0
    approved_requests: int = 0
    rejected_requests: int = 0
    average_approval_time_hours: float = 0.0


# Workflow store
class WorkflowStore(ABC):
    """Workflow storage."""
    
    @abstractmethod
    async def save(self, workflow: ApprovalWorkflow) -> None:
        pass
    
    @abstractmethod
    async def get(self, workflow_id: str) -> Optional[ApprovalWorkflow]:
        pass
    
    @abstractmethod
    async def list(self) -> List[ApprovalWorkflow]:
        pass


class InMemoryWorkflowStore(WorkflowStore):
    """In-memory workflow store."""
    
    def __init__(self):
        self._workflows: Dict[str, ApprovalWorkflow] = {}
    
    async def save(self, workflow: ApprovalWorkflow) -> None:
        self._workflows[workflow.id] = workflow
    
    async def get(self, workflow_id: str) -> Optional[ApprovalWorkflow]:
        return self._workflows.get(workflow_id)
    
    async def list(self) -> List[ApprovalWorkflow]:
        return list(self._workflows.values())


# Request store
class RequestStore(ABC):
    """Request storage."""
    
    @abstractmethod
    async def save(self, request: ApprovalRequest) -> None:
        pass
    
    @abstractmethod
    async def get(self, request_id: str) -> Optional[ApprovalRequest]:
        pass
    
    @abstractmethod
    async def query(
        self,
        status: Optional[RequestStatus] = None,
        requester_id: Optional[str] = None,
        approver_id: Optional[str] = None,
    ) -> List[ApprovalRequest]:
        pass


class InMemoryRequestStore(RequestStore):
    """In-memory request store."""
    
    def __init__(self):
        self._requests: Dict[str, ApprovalRequest] = {}
    
    async def save(self, request: ApprovalRequest) -> None:
        self._requests[request.id] = request
    
    async def get(self, request_id: str) -> Optional[ApprovalRequest]:
        return self._requests.get(request_id)
    
    async def query(
        self,
        status: Optional[RequestStatus] = None,
        requester_id: Optional[str] = None,
        approver_id: Optional[str] = None,
    ) -> List[ApprovalRequest]:
        results = list(self._requests.values())
        
        if status:
            results = [r for r in results if r.status == status]
        
        if requester_id:
            results = [r for r in results if r.requester_id == requester_id]
        
        if approver_id:
            results = [
                r for r in results
                if any(a.approver_id == approver_id for a in r.actions)
            ]
        
        return sorted(results, key=lambda r: r.created_at, reverse=True)


# Approval system
class ApprovalSystem:
    """Approval system."""
    
    def __init__(
        self,
        workflow_store: Optional[WorkflowStore] = None,
        request_store: Optional[RequestStore] = None,
    ):
        self._workflows = workflow_store or InMemoryWorkflowStore()
        self._requests = request_store or InMemoryRequestStore()
        self._stats = ApprovalStats()
        self._approval_times: List[float] = []
    
    async def create_workflow(
        self,
        name: str,
        levels: List[Dict[str, Any]] = None,
        description: str = "",
        created_by: str = "",
        **kwargs,
    ) -> ApprovalWorkflow:
        """Create approval workflow."""
        workflow = ApprovalWorkflow(
            name=name,
            description=description,
            created_by=created_by,
            **kwargs,
        )
        
        # Add levels
        if levels:
            for i, level_def in enumerate(levels):
                level = ApprovalLevel(
                    order=i,
                    name=level_def.get("name", f"Level {i + 1}"),
                    role=level_def.get("role", ""),
                    approvers=level_def.get("approvers", []),
                    required_count=level_def.get("required_count", 1),
                    threshold=level_def.get("threshold", float("inf")),
                    timeout_hours=level_def.get("timeout_hours", 72),
                )
                workflow.levels.append(level)
        
        await self._workflows.save(workflow)
        
        logger.info(f"Approval workflow created: {name}")
        
        return workflow
    
    async def get_workflow(self, workflow_id: str) -> Optional[ApprovalWorkflow]:
        """Get workflow."""
        return await self._workflows.get(workflow_id)
    
    async def submit(
        self,
        workflow_id: str,
        requester_id: str,
        title: str,
        amount: float = 0.0,
        description: str = "",
        data: Dict[str, Any] = None,
        **kwargs,
    ) -> ApprovalRequest:
        """Submit approval request."""
        workflow = await self._workflows.get(workflow_id)
        if not workflow:
            raise ApprovalError(f"Workflow not found: {workflow_id}")
        
        request = ApprovalRequest(
            workflow_id=workflow_id,
            workflow_name=workflow.name,
            requester_id=requester_id,
            title=title,
            description=description,
            amount=amount,
            data=data or {},
            status=RequestStatus.SUBMITTED,
            submitted_at=datetime.utcnow(),
            **kwargs,
        )
        
        # Determine starting level based on amount
        request.current_level = self._get_starting_level(workflow, amount)
        
        # Create pending actions for current level
        current_level = workflow.levels[request.current_level]
        self._create_level_actions(request, current_level)
        
        await self._requests.save(request)
        
        self._stats.total_requests += 1
        self._stats.pending_requests += 1
        
        logger.info(f"Approval request submitted: {title}")
        
        return request
    
    def _get_starting_level(
        self,
        workflow: ApprovalWorkflow,
        amount: float,
    ) -> int:
        """Get starting approval level based on amount."""
        for i, level in enumerate(workflow.levels):
            if amount <= level.threshold:
                return i
        return len(workflow.levels) - 1
    
    def _create_level_actions(
        self,
        request: ApprovalRequest,
        level: ApprovalLevel,
    ) -> None:
        """Create pending actions for level."""
        for approver_id in level.approvers:
            request.actions.append(ApprovalAction(
                level_id=level.id,
                approver_id=approver_id,
                status=ApprovalStatus.PENDING,
            ))
    
    async def get_request(
        self,
        request_id: str,
    ) -> Optional[ApprovalRequest]:
        """Get request."""
        return await self._requests.get(request_id)
    
    async def approve(
        self,
        request_id: str,
        approver_id: str,
        comments: str = "",
    ) -> ApprovalRequest:
        """Approve request."""
        request = await self._requests.get(request_id)
        if not request:
            raise RequestNotFoundError(f"Request not found: {request_id}")
        
        if request.status not in (RequestStatus.SUBMITTED, RequestStatus.IN_PROGRESS):
            raise ApprovalNotAllowedError(f"Request cannot be approved: {request.status}")
        
        workflow = await self._workflows.get(request.workflow_id)
        if not workflow:
            raise ApprovalError("Workflow not found")
        
        # Find and update action
        action = self._find_pending_action(request, approver_id)
        if not action:
            raise ApprovalNotAllowedError("No pending approval for this user")
        
        action.status = ApprovalStatus.APPROVED
        action.comments = comments
        action.completed_at = datetime.utcnow()
        
        # Check if level is complete
        current_level = workflow.levels[request.current_level]
        level_approved = self._is_level_approved(request, current_level)
        
        if level_approved:
            # Move to next level or complete
            if request.current_level < len(workflow.levels) - 1:
                request.current_level += 1
                request.status = RequestStatus.IN_PROGRESS
                next_level = workflow.levels[request.current_level]
                self._create_level_actions(request, next_level)
            else:
                request.status = RequestStatus.APPROVED
                request.completed_at = datetime.utcnow()
                request.final_status = ApprovalStatus.APPROVED
                request.final_comments = comments
                
                self._stats.pending_requests -= 1
                self._stats.approved_requests += 1
                
                # Track approval time
                if request.submitted_at:
                    hours = (request.completed_at - request.submitted_at).total_seconds() / 3600
                    self._approval_times.append(hours)
                    self._stats.average_approval_time_hours = sum(self._approval_times) / len(self._approval_times)
        
        await self._requests.save(request)
        
        logger.info(f"Request approved by {approver_id}: {request.title}")
        
        return request
    
    def _find_pending_action(
        self,
        request: ApprovalRequest,
        approver_id: str,
    ) -> Optional[ApprovalAction]:
        """Find pending action for approver."""
        for action in request.actions:
            if action.approver_id == approver_id and action.status == ApprovalStatus.PENDING:
                return action
        return None
    
    def _is_level_approved(
        self,
        request: ApprovalRequest,
        level: ApprovalLevel,
    ) -> bool:
        """Check if level has enough approvals."""
        approved_count = sum(
            1 for a in request.actions
            if a.level_id == level.id and a.status == ApprovalStatus.APPROVED
        )
        return approved_count >= level.required_count
    
    async def reject(
        self,
        request_id: str,
        approver_id: str,
        comments: str = "",
    ) -> ApprovalRequest:
        """Reject request."""
        request = await self._requests.get(request_id)
        if not request:
            raise RequestNotFoundError(f"Request not found: {request_id}")
        
        if request.status not in (RequestStatus.SUBMITTED, RequestStatus.IN_PROGRESS):
            raise ApprovalNotAllowedError(f"Request cannot be rejected: {request.status}")
        
        action = self._find_pending_action(request, approver_id)
        if not action:
            raise ApprovalNotAllowedError("No pending approval for this user")
        
        action.status = ApprovalStatus.REJECTED
        action.comments = comments
        action.completed_at = datetime.utcnow()
        
        request.status = RequestStatus.REJECTED
        request.completed_at = datetime.utcnow()
        request.final_status = ApprovalStatus.REJECTED
        request.final_comments = comments
        
        await self._requests.save(request)
        
        self._stats.pending_requests -= 1
        self._stats.rejected_requests += 1
        
        logger.info(f"Request rejected by {approver_id}: {request.title}")
        
        return request
    
    async def delegate(
        self,
        request_id: str,
        approver_id: str,
        delegate_to: str,
        comments: str = "",
    ) -> ApprovalRequest:
        """Delegate approval."""
        request = await self._requests.get(request_id)
        if not request:
            raise RequestNotFoundError(f"Request not found: {request_id}")
        
        workflow = await self._workflows.get(request.workflow_id)
        if not workflow or not workflow.allow_delegation:
            raise ApprovalNotAllowedError("Delegation not allowed")
        
        action = self._find_pending_action(request, approver_id)
        if not action:
            raise ApprovalNotAllowedError("No pending approval for this user")
        
        action.status = ApprovalStatus.DELEGATED
        action.delegated_to = delegate_to
        action.delegated_by = approver_id
        action.comments = comments
        action.completed_at = datetime.utcnow()
        
        # Create new action for delegate
        request.actions.append(ApprovalAction(
            level_id=action.level_id,
            approver_id=delegate_to,
            status=ApprovalStatus.PENDING,
        ))
        
        await self._requests.save(request)
        
        logger.info(f"Request delegated from {approver_id} to {delegate_to}")
        
        return request
    
    async def escalate(
        self,
        request_id: str,
        reason: EscalationReason = EscalationReason.MANUAL,
        comments: str = "",
    ) -> ApprovalRequest:
        """Escalate request to next level."""
        request = await self._requests.get(request_id)
        if not request:
            raise RequestNotFoundError(f"Request not found: {request_id}")
        
        workflow = await self._workflows.get(request.workflow_id)
        if not workflow:
            raise ApprovalError("Workflow not found")
        
        if request.current_level >= len(workflow.levels) - 1:
            raise ApprovalNotAllowedError("Already at highest level")
        
        # Mark current actions as escalated
        current_level = workflow.levels[request.current_level]
        for action in request.actions:
            if action.level_id == current_level.id and action.status == ApprovalStatus.PENDING:
                action.status = ApprovalStatus.ESCALATED
                action.comments = f"Escalated: {reason.value}"
                action.completed_at = datetime.utcnow()
        
        # Move to next level
        request.current_level += 1
        request.status = RequestStatus.IN_PROGRESS
        
        next_level = workflow.levels[request.current_level]
        self._create_level_actions(request, next_level)
        
        await self._requests.save(request)
        
        logger.info(f"Request escalated: {request.title}")
        
        return request
    
    async def cancel(
        self,
        request_id: str,
        comments: str = "",
    ) -> ApprovalRequest:
        """Cancel request."""
        request = await self._requests.get(request_id)
        if not request:
            raise RequestNotFoundError(f"Request not found: {request_id}")
        
        if request.status in (RequestStatus.APPROVED, RequestStatus.REJECTED):
            raise ApprovalNotAllowedError("Cannot cancel completed request")
        
        request.status = RequestStatus.CANCELLED
        request.completed_at = datetime.utcnow()
        request.final_status = ApprovalStatus.CANCELLED
        request.final_comments = comments
        
        await self._requests.save(request)
        
        self._stats.pending_requests -= 1
        
        logger.info(f"Request cancelled: {request.title}")
        
        return request
    
    async def get_pending_approvals(
        self,
        approver_id: str,
    ) -> List[ApprovalRequest]:
        """Get pending approvals for user."""
        requests = await self._requests.query(status=RequestStatus.SUBMITTED)
        requests.extend(await self._requests.query(status=RequestStatus.IN_PROGRESS))
        
        pending = []
        for request in requests:
            if self._find_pending_action(request, approver_id):
                pending.append(request)
        
        return pending
    
    async def query_requests(
        self,
        status: Optional[RequestStatus] = None,
        requester_id: Optional[str] = None,
    ) -> List[ApprovalRequest]:
        """Query requests."""
        return await self._requests.query(status=status, requester_id=requester_id)
    
    def get_stats(self) -> ApprovalStats:
        """Get statistics."""
        return self._stats


# Factory functions
def create_approval_system() -> ApprovalSystem:
    """Create approval system."""
    return ApprovalSystem()


def create_workflow(
    name: str,
    **kwargs,
) -> ApprovalWorkflow:
    """Create workflow."""
    return ApprovalWorkflow(name=name, **kwargs)


def create_level(
    name: str,
    role: str,
    **kwargs,
) -> ApprovalLevel:
    """Create approval level."""
    return ApprovalLevel(name=name, role=role, **kwargs)


__all__ = [
    # Exceptions
    "ApprovalError",
    "RequestNotFoundError",
    "ApprovalNotAllowedError",
    # Enums
    "ApprovalStatus",
    "RequestStatus",
    "EscalationReason",
    # Data classes
    "ApprovalLevel",
    "ApprovalWorkflow",
    "ApprovalAction",
    "ApprovalRequest",
    "ApprovalStats",
    # Stores
    "WorkflowStore",
    "InMemoryWorkflowStore",
    "RequestStore",
    "InMemoryRequestStore",
    # System
    "ApprovalSystem",
    # Factory functions
    "create_approval_system",
    "create_workflow",
    "create_level",
]
