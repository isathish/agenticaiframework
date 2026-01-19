"""
Human-in-the-Loop Manager Implementation.

Provides approval workflows, feedback collection, and intervention
mechanisms for human oversight of agent operations.
"""

import asyncio
import json
import logging
import threading
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from queue import Queue, Empty
from typing import Any, Dict, List, Optional, Callable, Union, Awaitable

logger = logging.getLogger(__name__)


class ApprovalStatus(Enum):
    """Status of an approval request."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMEOUT = "timeout"
    ESCALATED = "escalated"
    AUTO_APPROVED = "auto_approved"


class FeedbackType(Enum):
    """Types of feedback."""
    RATING = "rating"  # 1-5 stars
    THUMBS = "thumbs"  # up/down
    TEXT = "text"
    CORRECTION = "correction"
    FLAG = "flag"
    PREFERENCE = "preference"


class EscalationLevel(Enum):
    """Escalation severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ApprovalRequest:
    """Request for human approval."""
    id: str
    action: str
    details: Dict[str, Any]
    agent_id: str
    session_id: Optional[str]
    reason: str
    created_at: str
    expires_at: Optional[str] = None
    priority: int = 0
    context: Dict[str, Any] = field(default_factory=dict)
    status: ApprovalStatus = ApprovalStatus.PENDING
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "action": self.action,
            "details": self.details,
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "reason": self.reason,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "priority": self.priority,
            "context": self.context,
            "status": self.status.value,
        }
    
    def to_display(self) -> str:
        """Format for human display."""
        lines = [
            f"=== Approval Request: {self.id} ===",
            f"Action: {self.action}",
            f"Agent: {self.agent_id}",
            f"Reason: {self.reason}",
            f"Priority: {self.priority}",
            "",
            "Details:",
        ]
        
        for key, value in self.details.items():
            if isinstance(value, str) and len(value) > 100:
                value = value[:100] + "..."
            lines.append(f"  {key}: {value}")
        
        if self.expires_at:
            lines.append(f"\nExpires: {self.expires_at}")
        
        return "\n".join(lines)


@dataclass
class ApprovalDecision:
    """Human decision on an approval request."""
    request_id: str
    status: ApprovalStatus
    decided_by: str
    decided_at: str
    reason: Optional[str] = None
    modifications: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "status": self.status.value,
            "decided_by": self.decided_by,
            "decided_at": self.decided_at,
            "reason": self.reason,
            "modifications": self.modifications,
        }


@dataclass
class Feedback:
    """Human feedback on agent response."""
    id: str
    response_id: str
    feedback_type: FeedbackType
    value: Any  # rating (1-5), thumbs (up/down), text, etc.
    user_id: Optional[str]
    created_at: str
    context: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "response_id": self.response_id,
            "feedback_type": self.feedback_type.value,
            "value": self.value,
            "user_id": self.user_id,
            "created_at": self.created_at,
            "context": self.context,
        }


@dataclass
class EscalationTrigger:
    """Trigger condition for escalation."""
    name: str
    condition: Callable[[Dict[str, Any]], bool]
    level: EscalationLevel
    message: str
    auto_escalate: bool = True


@dataclass
class InterventionRequest:
    """Request for human intervention."""
    id: str
    reason: str
    level: EscalationLevel
    agent_id: str
    session_id: Optional[str]
    context: Dict[str, Any]
    created_at: str
    resolved: bool = False
    resolution: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "reason": self.reason,
            "level": self.level.value,
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "context": self.context,
            "created_at": self.created_at,
            "resolved": self.resolved,
            "resolution": self.resolution,
        }


class ApprovalHandler(ABC):
    """Abstract base class for approval handlers."""
    
    @abstractmethod
    def request_approval(
        self,
        request: ApprovalRequest,
    ) -> ApprovalDecision:
        """Request approval synchronously."""
        pass
    
    @abstractmethod
    async def request_approval_async(
        self,
        request: ApprovalRequest,
    ) -> ApprovalDecision:
        """Request approval asynchronously."""
        pass


class ConsoleApprovalHandler(ApprovalHandler):
    """
    Console-based approval handler for CLI interactions.
    
    Example:
        >>> handler = ConsoleApprovalHandler()
        >>> decision = handler.request_approval(request)
    """
    
    def __init__(self, timeout: int = 300):
        self.timeout = timeout
    
    def request_approval(self, request: ApprovalRequest) -> ApprovalDecision:
        """Request approval via console input."""
        print("\n" + "=" * 50)
        print(request.to_display())
        print("=" * 50)
        print("\nOptions: (a)pprove, (r)eject, (m)odify, (s)kip")
        
        try:
            response = input("Decision: ").strip().lower()
            
            if response in ("a", "approve", "y", "yes"):
                status = ApprovalStatus.APPROVED
                reason = None
            elif response in ("r", "reject", "n", "no"):
                reason = input("Reason for rejection (optional): ").strip() or None
                status = ApprovalStatus.REJECTED
            elif response in ("m", "modify"):
                print("Enter modifications as JSON:")
                mods_str = input().strip()
                try:
                    modifications = json.loads(mods_str)
                except json.JSONDecodeError:
                    modifications = {}
                status = ApprovalStatus.APPROVED
                reason = "Approved with modifications"
                return ApprovalDecision(
                    request_id=request.id,
                    status=status,
                    decided_by="console_user",
                    decided_at=datetime.now().isoformat(),
                    reason=reason,
                    modifications=modifications,
                )
            else:
                status = ApprovalStatus.TIMEOUT
                reason = "Skipped by user"
            
            return ApprovalDecision(
                request_id=request.id,
                status=status,
                decided_by="console_user",
                decided_at=datetime.now().isoformat(),
                reason=reason,
            )
            
        except (KeyboardInterrupt, EOFError):
            return ApprovalDecision(
                request_id=request.id,
                status=ApprovalStatus.TIMEOUT,
                decided_by="console_user",
                decided_at=datetime.now().isoformat(),
                reason="Interrupted",
            )
    
    async def request_approval_async(self, request: ApprovalRequest) -> ApprovalDecision:
        """Async version using thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.request_approval, request)


class CallbackApprovalHandler(ApprovalHandler):
    """
    Callback-based approval handler.
    
    Example:
        >>> def my_approval_callback(request):
        ...     # Custom approval logic
        ...     return ApprovalDecision(...)
        >>> 
        >>> handler = CallbackApprovalHandler(callback=my_approval_callback)
    """
    
    def __init__(
        self,
        callback: Optional[Callable[[ApprovalRequest], ApprovalDecision]] = None,
        async_callback: Optional[Callable[[ApprovalRequest], Awaitable[ApprovalDecision]]] = None,
    ):
        self.callback = callback
        self.async_callback = async_callback
    
    def request_approval(self, request: ApprovalRequest) -> ApprovalDecision:
        """Request approval via callback."""
        if self.callback:
            return self.callback(request)
        
        # Default: auto-approve
        return ApprovalDecision(
            request_id=request.id,
            status=ApprovalStatus.AUTO_APPROVED,
            decided_by="callback_handler",
            decided_at=datetime.now().isoformat(),
            reason="No callback configured, auto-approved",
        )
    
    async def request_approval_async(self, request: ApprovalRequest) -> ApprovalDecision:
        """Request approval via async callback."""
        if self.async_callback:
            return await self.async_callback(request)
        
        if self.callback:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self.callback, request)
        
        return ApprovalDecision(
            request_id=request.id,
            status=ApprovalStatus.AUTO_APPROVED,
            decided_by="callback_handler",
            decided_at=datetime.now().isoformat(),
        )


class QueueApprovalHandler(ApprovalHandler):
    """
    Queue-based approval handler for async workflows.
    
    Example:
        >>> handler = QueueApprovalHandler()
        >>> 
        >>> # Submit request
        >>> request_id = handler.submit_request(request)
        >>> 
        >>> # Later, process pending requests
        >>> pending = handler.get_pending()
        >>> for req in pending:
        ...     handler.resolve(req.id, ApprovalStatus.APPROVED)
    """
    
    def __init__(self, timeout: int = 3600):
        self.timeout = timeout
        self._pending: Dict[str, ApprovalRequest] = {}
        self._decisions: Dict[str, ApprovalDecision] = {}
        self._lock = threading.Lock()
        self._event_map: Dict[str, threading.Event] = {}
    
    def submit_request(self, request: ApprovalRequest) -> str:
        """Submit request to queue."""
        with self._lock:
            self._pending[request.id] = request
            self._event_map[request.id] = threading.Event()
        return request.id
    
    def get_pending(self) -> List[ApprovalRequest]:
        """Get all pending requests."""
        with self._lock:
            return list(self._pending.values())
    
    def resolve(
        self,
        request_id: str,
        status: ApprovalStatus,
        decided_by: str = "queue_handler",
        reason: Optional[str] = None,
        modifications: Dict = None,
    ) -> bool:
        """Resolve a pending request."""
        with self._lock:
            if request_id not in self._pending:
                return False
            
            decision = ApprovalDecision(
                request_id=request_id,
                status=status,
                decided_by=decided_by,
                decided_at=datetime.now().isoformat(),
                reason=reason,
                modifications=modifications or {},
            )
            
            self._decisions[request_id] = decision
            del self._pending[request_id]
            
            if request_id in self._event_map:
                self._event_map[request_id].set()
            
            return True
    
    def request_approval(self, request: ApprovalRequest) -> ApprovalDecision:
        """Submit and wait for approval."""
        self.submit_request(request)
        
        event = self._event_map.get(request.id)
        if event:
            event.wait(timeout=self.timeout)
        
        with self._lock:
            if request.id in self._decisions:
                return self._decisions.pop(request.id)
            
            # Timeout
            if request.id in self._pending:
                del self._pending[request.id]
            
            return ApprovalDecision(
                request_id=request.id,
                status=ApprovalStatus.TIMEOUT,
                decided_by="queue_handler",
                decided_at=datetime.now().isoformat(),
                reason="Request timed out",
            )
    
    async def request_approval_async(self, request: ApprovalRequest) -> ApprovalDecision:
        """Async version."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.request_approval, request)


class FeedbackCollector:
    """
    Collects and manages human feedback on agent responses.
    
    Example:
        >>> collector = FeedbackCollector()
        >>> 
        >>> # Collect rating
        >>> feedback = collector.collect_rating(
        ...     response_id="resp-123",
        ...     rating=4,
        ...     user_id="user-456"
        ... )
        >>> 
        >>> # Collect text feedback
        >>> collector.collect_text(
        ...     response_id="resp-123",
        ...     text="Very helpful response!"
        ... )
        >>> 
        >>> # Get feedback summary
        >>> summary = collector.get_summary("resp-123")
    """
    
    def __init__(self):
        self._feedback: List[Feedback] = []
        self._by_response: Dict[str, List[Feedback]] = {}
    
    def _create_feedback(
        self,
        response_id: str,
        feedback_type: FeedbackType,
        value: Any,
        user_id: Optional[str] = None,
        context: Dict = None,
    ) -> Feedback:
        """Create and store feedback."""
        feedback = Feedback(
            id=f"fb-{uuid.uuid4().hex[:8]}",
            response_id=response_id,
            feedback_type=feedback_type,
            value=value,
            user_id=user_id,
            created_at=datetime.now().isoformat(),
            context=context or {},
        )
        
        self._feedback.append(feedback)
        
        if response_id not in self._by_response:
            self._by_response[response_id] = []
        self._by_response[response_id].append(feedback)
        
        return feedback
    
    def collect_rating(
        self,
        response_id: str,
        rating: int,
        user_id: Optional[str] = None,
        context: Dict = None,
    ) -> Feedback:
        """Collect 1-5 star rating."""
        rating = max(1, min(5, rating))
        return self._create_feedback(
            response_id, FeedbackType.RATING, rating, user_id, context
        )
    
    def collect_thumbs(
        self,
        response_id: str,
        is_positive: bool,
        user_id: Optional[str] = None,
        context: Dict = None,
    ) -> Feedback:
        """Collect thumbs up/down."""
        return self._create_feedback(
            response_id, FeedbackType.THUMBS, "up" if is_positive else "down",
            user_id, context
        )
    
    def collect_text(
        self,
        response_id: str,
        text: str,
        user_id: Optional[str] = None,
        context: Dict = None,
    ) -> Feedback:
        """Collect text feedback."""
        return self._create_feedback(
            response_id, FeedbackType.TEXT, text, user_id, context
        )
    
    def collect_correction(
        self,
        response_id: str,
        original: str,
        corrected: str,
        user_id: Optional[str] = None,
        context: Dict = None,
    ) -> Feedback:
        """Collect correction feedback."""
        return self._create_feedback(
            response_id, FeedbackType.CORRECTION,
            {"original": original, "corrected": corrected},
            user_id, context
        )
    
    def collect_flag(
        self,
        response_id: str,
        flag_type: str,
        reason: str,
        user_id: Optional[str] = None,
        context: Dict = None,
    ) -> Feedback:
        """Collect flag (for inappropriate content, errors, etc.)."""
        return self._create_feedback(
            response_id, FeedbackType.FLAG,
            {"type": flag_type, "reason": reason},
            user_id, context
        )
    
    def get_feedback(self, response_id: str) -> List[Feedback]:
        """Get all feedback for a response."""
        return self._by_response.get(response_id, [])
    
    def get_summary(self, response_id: str) -> Dict[str, Any]:
        """Get feedback summary for a response."""
        feedbacks = self.get_feedback(response_id)
        
        ratings = [f.value for f in feedbacks if f.feedback_type == FeedbackType.RATING]
        thumbs = [f.value for f in feedbacks if f.feedback_type == FeedbackType.THUMBS]
        
        return {
            "response_id": response_id,
            "total_feedback": len(feedbacks),
            "average_rating": sum(ratings) / len(ratings) if ratings else None,
            "rating_count": len(ratings),
            "thumbs_up": thumbs.count("up"),
            "thumbs_down": thumbs.count("down"),
            "text_count": sum(1 for f in feedbacks if f.feedback_type == FeedbackType.TEXT),
            "correction_count": sum(1 for f in feedbacks if f.feedback_type == FeedbackType.CORRECTION),
            "flag_count": sum(1 for f in feedbacks if f.feedback_type == FeedbackType.FLAG),
        }
    
    def export(self) -> List[Dict[str, Any]]:
        """Export all feedback as dicts."""
        return [f.to_dict() for f in self._feedback]


class HumanInTheLoop:
    """
    Main human-in-the-loop manager for agent workflows.
    
    Example:
        >>> hitl = HumanInTheLoop(
        ...     agent_id="assistant",
        ...     approval_required_for=["tool_call", "external_api", "sensitive_data"],
        ...     approval_handler=ConsoleApprovalHandler()
        ... )
        >>> 
        >>> # Check if approval needed
        >>> if hitl.requires_approval("tool_call", {"tool": "send_email"}):
        ...     decision = hitl.request_approval(
        ...         action="tool_call",
        ...         details={"tool": "send_email", "to": "user@example.com"}
        ...     )
        ...     if not decision.status == ApprovalStatus.APPROVED:
        ...         raise PermissionError("Action not approved")
        >>> 
        >>> # Collect feedback
        >>> hitl.feedback.collect_thumbs("resp-123", is_positive=True)
        >>> 
        >>> # Request intervention
        >>> hitl.request_intervention(
        ...     reason="Agent is uncertain about response",
        ...     level=EscalationLevel.MEDIUM
        ... )
    """
    
    def __init__(
        self,
        agent_id: str = "agent",
        session_id: Optional[str] = None,
        approval_required_for: List[str] = None,
        approval_handler: Optional[ApprovalHandler] = None,
        auto_approve_after: Optional[int] = None,  # seconds
        notification_handler: Optional[Callable[[str, Dict], None]] = None,
    ):
        self.agent_id = agent_id
        self.session_id = session_id
        self.approval_required_for = set(approval_required_for or [])
        self.approval_handler = approval_handler or CallbackApprovalHandler()
        self.auto_approve_after = auto_approve_after
        self.notification_handler = notification_handler
        
        # Components
        self.feedback = FeedbackCollector()
        
        # State
        self._requests: Dict[str, ApprovalRequest] = {}
        self._decisions: Dict[str, ApprovalDecision] = {}
        self._interventions: Dict[str, InterventionRequest] = {}
        self._escalation_triggers: List[EscalationTrigger] = []
        
        # Callbacks
        self._on_approval_requested: List[Callable[[ApprovalRequest], None]] = []
        self._on_decision_made: List[Callable[[ApprovalDecision], None]] = []
        self._on_intervention: List[Callable[[InterventionRequest], None]] = []
    
    def requires_approval(self, action: str, details: Dict = None) -> bool:
        """Check if action requires approval."""
        if action in self.approval_required_for:
            return True
        
        # Check custom conditions
        for trigger in self._escalation_triggers:
            if trigger.auto_escalate:
                ctx = {"action": action, "details": details or {}}
                if trigger.condition(ctx):
                    return True
        
        return False
    
    def add_approval_requirement(self, action: str) -> None:
        """Add action that requires approval."""
        self.approval_required_for.add(action)
    
    def remove_approval_requirement(self, action: str) -> None:
        """Remove approval requirement."""
        self.approval_required_for.discard(action)
    
    def request_approval(
        self,
        action: str,
        details: Dict[str, Any],
        reason: str = "Action requires human approval",
        priority: int = 0,
        timeout: Optional[int] = None,
        context: Dict = None,
    ) -> ApprovalDecision:
        """
        Request human approval for an action.
        
        Args:
            action: Type of action
            details: Action details
            reason: Why approval is needed
            priority: Request priority (higher = more urgent)
            timeout: Approval timeout in seconds
            context: Additional context
        
        Returns:
            ApprovalDecision with status and details
        """
        # Create request
        expires_at = None
        if timeout or self.auto_approve_after:
            t = timeout or self.auto_approve_after
            expires_at = (datetime.now() + timedelta(seconds=t)).isoformat()
        
        request = ApprovalRequest(
            id=f"apr-{uuid.uuid4().hex[:8]}",
            action=action,
            details=details,
            agent_id=self.agent_id,
            session_id=self.session_id,
            reason=reason,
            created_at=datetime.now().isoformat(),
            expires_at=expires_at,
            priority=priority,
            context=context or {},
        )
        
        self._requests[request.id] = request
        self._notify_approval_requested(request)
        
        # Send notification
        if self.notification_handler:
            self.notification_handler("approval_requested", request.to_dict())
        
        # Get decision
        decision = self.approval_handler.request_approval(request)
        
        self._decisions[request.id] = decision
        request.status = decision.status
        self._notify_decision_made(decision)
        
        return decision
    
    async def request_approval_async(
        self,
        action: str,
        details: Dict[str, Any],
        reason: str = "Action requires human approval",
        priority: int = 0,
        timeout: Optional[int] = None,
        context: Dict = None,
    ) -> ApprovalDecision:
        """Async version of request_approval."""
        expires_at = None
        if timeout or self.auto_approve_after:
            t = timeout or self.auto_approve_after
            expires_at = (datetime.now() + timedelta(seconds=t)).isoformat()
        
        request = ApprovalRequest(
            id=f"apr-{uuid.uuid4().hex[:8]}",
            action=action,
            details=details,
            agent_id=self.agent_id,
            session_id=self.session_id,
            reason=reason,
            created_at=datetime.now().isoformat(),
            expires_at=expires_at,
            priority=priority,
            context=context or {},
        )
        
        self._requests[request.id] = request
        self._notify_approval_requested(request)
        
        if self.notification_handler:
            self.notification_handler("approval_requested", request.to_dict())
        
        decision = await self.approval_handler.request_approval_async(request)
        
        self._decisions[request.id] = decision
        request.status = decision.status
        self._notify_decision_made(decision)
        
        return decision
    
    def add_escalation_trigger(
        self,
        name: str,
        condition: Callable[[Dict[str, Any]], bool],
        level: EscalationLevel = EscalationLevel.MEDIUM,
        message: str = "Escalation triggered",
        auto_escalate: bool = True,
    ) -> None:
        """Add escalation trigger condition."""
        trigger = EscalationTrigger(
            name=name,
            condition=condition,
            level=level,
            message=message,
            auto_escalate=auto_escalate,
        )
        self._escalation_triggers.append(trigger)
    
    def check_escalation(self, context: Dict[str, Any]) -> Optional[EscalationTrigger]:
        """Check if any escalation triggers match."""
        for trigger in self._escalation_triggers:
            try:
                if trigger.condition(context):
                    return trigger
            except Exception as e:
                logger.error(f"Escalation trigger error: {e}")
        return None
    
    def request_intervention(
        self,
        reason: str,
        level: EscalationLevel = EscalationLevel.MEDIUM,
        context: Dict = None,
    ) -> InterventionRequest:
        """
        Request human intervention.
        
        Use when agent is uncertain, encounters edge case,
        or needs human guidance.
        """
        intervention = InterventionRequest(
            id=f"int-{uuid.uuid4().hex[:8]}",
            reason=reason,
            level=level,
            agent_id=self.agent_id,
            session_id=self.session_id,
            context=context or {},
            created_at=datetime.now().isoformat(),
        )
        
        self._interventions[intervention.id] = intervention
        self._notify_intervention(intervention)
        
        if self.notification_handler:
            self.notification_handler("intervention_requested", intervention.to_dict())
        
        return intervention
    
    def resolve_intervention(
        self,
        intervention_id: str,
        resolution: str,
    ) -> bool:
        """Resolve an intervention request."""
        if intervention_id not in self._interventions:
            return False
        
        intervention = self._interventions[intervention_id]
        intervention.resolved = True
        intervention.resolution = resolution
        
        return True
    
    def pause_agent(self, reason: str = "Paused by human") -> InterventionRequest:
        """Pause agent operation for human review."""
        return self.request_intervention(
            reason=reason,
            level=EscalationLevel.HIGH,
            context={"action": "pause"},
        )
    
    def get_pending_approvals(self) -> List[ApprovalRequest]:
        """Get pending approval requests."""
        return [r for r in self._requests.values() 
                if r.status == ApprovalStatus.PENDING]
    
    def get_pending_interventions(self) -> List[InterventionRequest]:
        """Get unresolved interventions."""
        return [i for i in self._interventions.values() if not i.resolved]
    
    def get_history(self) -> Dict[str, Any]:
        """Get HITL interaction history."""
        return {
            "approval_requests": [r.to_dict() for r in self._requests.values()],
            "decisions": [d.to_dict() for d in self._decisions.values()],
            "interventions": [i.to_dict() for i in self._interventions.values()],
            "feedback": self.feedback.export(),
        }
    
    # Callbacks
    def on_approval_requested(self, callback: Callable[[ApprovalRequest], None]) -> None:
        """Register callback for approval requests."""
        self._on_approval_requested.append(callback)
    
    def on_decision_made(self, callback: Callable[[ApprovalDecision], None]) -> None:
        """Register callback for decisions."""
        self._on_decision_made.append(callback)
    
    def on_intervention(self, callback: Callable[[InterventionRequest], None]) -> None:
        """Register callback for interventions."""
        self._on_intervention.append(callback)
    
    def _notify_approval_requested(self, request: ApprovalRequest) -> None:
        for callback in self._on_approval_requested:
            try:
                callback(request)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    def _notify_decision_made(self, decision: ApprovalDecision) -> None:
        for callback in self._on_decision_made:
            try:
                callback(decision)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    def _notify_intervention(self, intervention: InterventionRequest) -> None:
        for callback in self._on_intervention:
            try:
                callback(intervention)
            except Exception as e:
                logger.error(f"Callback error: {e}")


__all__ = [
    # Types
    "ApprovalStatus",
    "ApprovalRequest",
    "ApprovalDecision",
    "FeedbackType",
    "Feedback",
    "EscalationLevel",
    "EscalationTrigger",
    "InterventionRequest",
    # Handlers
    "ApprovalHandler",
    "ConsoleApprovalHandler",
    "CallbackApprovalHandler",
    "QueueApprovalHandler",
    # Feedback
    "FeedbackCollector",
    # Main class
    "HumanInTheLoop",
]
