"""
Human-in-the-Loop Module for Agent Workflows.

Provides mechanisms for human oversight, approval, feedback,
and intervention in agent operations.

Features:
- Approval workflows for sensitive operations
- Human feedback collection
- Escalation and intervention triggers
- Review queues and notifications
- Audit trail for human decisions

Example:
    >>> from agenticaiframework.hitl import (
    ...     HumanInTheLoop, ApprovalRequest, FeedbackCollector
    ... )
    >>> 
    >>> # Create HITL manager
    >>> hitl = HumanInTheLoop(
    ...     approval_required_for=["tool_call", "external_api"],
    ...     notification_handler=my_notifier
    ... )
    >>> 
    >>> # Request approval
    >>> approved = await hitl.request_approval(
    ...     action="send_email",
    ...     details={"to": "user@example.com", "subject": "..."}
    ... )
    >>> 
    >>> # Collect feedback
    >>> feedback = hitl.collect_feedback(
    ...     response_id="resp-123",
    ...     prompt="Was this response helpful?"
    ... )
"""

from .manager import (
    # Types
    ApprovalStatus,
    ApprovalRequest,
    ApprovalDecision,
    FeedbackType,
    Feedback,
    EscalationLevel,
    EscalationTrigger,
    InterventionRequest,
    # Handlers
    ApprovalHandler,
    ConsoleApprovalHandler,
    CallbackApprovalHandler,
    QueueApprovalHandler,
    # Feedback
    FeedbackCollector,
    # Main class
    HumanInTheLoop,
)

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
