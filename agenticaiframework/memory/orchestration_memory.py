"""
Orchestration Memory Management.

Provides shared memory for multi-agent orchestration:
- Team shared memory
- Agent-to-agent communication history
- Task handoff memory
- Coordination context
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from .manager import MemoryManager

logger = logging.getLogger(__name__)


class MessagePriority(Enum):
    """Priority of inter-agent messages."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class AgentMessage:
    """Message between agents."""
    message_id: str
    from_agent: str
    to_agent: str  # or "broadcast" for all
    content: Any
    priority: MessagePriority = MessagePriority.NORMAL
    message_type: str = "general"  # general, task, result, query, response
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    read: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "content": self.content,
            "priority": self.priority.value,
            "message_type": self.message_type,
            "timestamp": self.timestamp,
            "read": self.read,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentMessage":
        return cls(
            message_id=data["message_id"],
            from_agent=data["from_agent"],
            to_agent=data["to_agent"],
            content=data["content"],
            priority=MessagePriority(data.get("priority", "normal")),
            message_type=data.get("message_type", "general"),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            read=data.get("read", False),
            metadata=data.get("metadata", {}),
        )


@dataclass
class TaskHandoff:
    """Record of task handoff between agents."""
    handoff_id: str
    task_id: str
    from_agent: str
    to_agent: str
    task_description: str
    context: Dict[str, Any]
    reason: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    acknowledged: bool = False
    completed: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "handoff_id": self.handoff_id,
            "task_id": self.task_id,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "task_description": self.task_description,
            "context": self.context,
            "reason": self.reason,
            "timestamp": self.timestamp,
            "acknowledged": self.acknowledged,
            "completed": self.completed,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskHandoff":
        return cls(
            handoff_id=data["handoff_id"],
            task_id=data["task_id"],
            from_agent=data["from_agent"],
            to_agent=data["to_agent"],
            task_description=data["task_description"],
            context=data.get("context", {}),
            reason=data.get("reason", ""),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            acknowledged=data.get("acknowledged", False),
            completed=data.get("completed", False),
        )


@dataclass
class SharedContext:
    """Shared context for a team of agents."""
    team_id: str
    goal: str
    variables: Dict[str, Any] = field(default_factory=dict)
    knowledge: List[str] = field(default_factory=list)  # Shared facts/knowledge
    constraints: List[str] = field(default_factory=list)
    progress: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "team_id": self.team_id,
            "goal": self.goal,
            "variables": self.variables,
            "knowledge": self.knowledge,
            "constraints": self.constraints,
            "progress": self.progress,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SharedContext":
        return cls(
            team_id=data["team_id"],
            goal=data.get("goal", ""),
            variables=data.get("variables", {}),
            knowledge=data.get("knowledge", []),
            constraints=data.get("constraints", []),
            progress=data.get("progress", {}),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
        )


@dataclass
class AgentContribution:
    """Record of an agent's contribution to team task."""
    contribution_id: str
    agent_id: str
    task_id: str
    contribution_type: str  # analysis, decision, action, result
    content: Any
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "contribution_id": self.contribution_id,
            "agent_id": self.agent_id,
            "task_id": self.task_id,
            "contribution_type": self.contribution_type,
            "content": self.content,
            "timestamp": self.timestamp,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentContribution":
        return cls(
            contribution_id=data["contribution_id"],
            agent_id=data["agent_id"],
            task_id=data["task_id"],
            contribution_type=data["contribution_type"],
            content=data["content"],
            timestamp=data.get("timestamp", datetime.now().isoformat()),
        )


class OrchestrationMemoryManager:
    """
    Manages shared memory for multi-agent orchestration.
    
    Example:
        >>> orch_memory = OrchestrationMemoryManager()
        >>> 
        >>> # Create team context
        >>> ctx = orch_memory.create_team_context("team-1", goal="Solve problem")
        >>> 
        >>> # Send message between agents
        >>> orch_memory.send_message("agent-1", "agent-2", "Please analyze this")
        >>> 
        >>> # Record task handoff
        >>> orch_memory.record_handoff("agent-1", "agent-2", "task-1", context={...})
        >>> 
        >>> # Share knowledge with team
        >>> orch_memory.add_shared_knowledge("team-1", "User prefers detailed answers")
    """
    
    def __init__(
        self,
        memory_manager: MemoryManager = None,
        max_messages_per_agent: int = 100,
        max_handoffs: int = 500,
    ):
        self.memory = memory_manager or MemoryManager()
        self.max_messages = max_messages_per_agent
        self.max_handoffs = max_handoffs
        
        # In-memory storage
        self._contexts: Dict[str, SharedContext] = {}
        self._messages: Dict[str, List[AgentMessage]] = {}  # agent_id -> messages
        self._handoffs: List[TaskHandoff] = []
        self._contributions: Dict[str, List[AgentContribution]] = {}  # task_id -> contributions
    
    def _key(self, prefix: str, id: str) -> str:
        """Generate memory key."""
        return f"orchestration:{prefix}:{id}"
    
    # =========================================================================
    # Team Context
    # =========================================================================
    
    def create_team_context(
        self,
        team_id: str,
        goal: str,
        initial_variables: Dict = None,
        constraints: List[str] = None,
    ) -> SharedContext:
        """Create shared context for a team."""
        ctx = SharedContext(
            team_id=team_id,
            goal=goal,
            variables=initial_variables or {},
            constraints=constraints or [],
        )
        
        self._contexts[team_id] = ctx
        
        self.memory.store_short_term(
            self._key("context", team_id),
            ctx.to_dict(),
            ttl=7200,  # 2 hours
            priority=7,
        )
        
        return ctx
    
    def get_team_context(self, team_id: str) -> Optional[SharedContext]:
        """Get team shared context."""
        if team_id in self._contexts:
            return self._contexts[team_id]
        
        data = self.memory.retrieve(self._key("context", team_id))
        if data:
            ctx = SharedContext.from_dict(data)
            self._contexts[team_id] = ctx
            return ctx
        
        return None
    
    def update_team_variable(
        self,
        team_id: str,
        key: str,
        value: Any,
    ) -> bool:
        """Update a shared variable."""
        ctx = self.get_team_context(team_id)
        if not ctx:
            return False
        
        ctx.variables[key] = value
        ctx.updated_at = datetime.now().isoformat()
        
        self.memory.store_short_term(
            self._key("context", team_id),
            ctx.to_dict(),
            ttl=7200,
        )
        
        return True
    
    def get_team_variable(
        self,
        team_id: str,
        key: str,
        default: Any = None,
    ) -> Any:
        """Get a shared variable."""
        ctx = self.get_team_context(team_id)
        if not ctx:
            return default
        return ctx.variables.get(key, default)
    
    def add_shared_knowledge(
        self,
        team_id: str,
        knowledge: str,
    ) -> bool:
        """Add knowledge to team's shared context."""
        ctx = self.get_team_context(team_id)
        if not ctx:
            return False
        
        if knowledge not in ctx.knowledge:
            ctx.knowledge.append(knowledge)
            ctx.updated_at = datetime.now().isoformat()
            
            self.memory.store_short_term(
                self._key("context", team_id),
                ctx.to_dict(),
                ttl=7200,
            )
        
        return True
    
    def update_progress(
        self,
        team_id: str,
        task_id: str,
        progress: Dict[str, Any],
    ) -> bool:
        """Update task progress in shared context."""
        ctx = self.get_team_context(team_id)
        if not ctx:
            return False
        
        ctx.progress[task_id] = {
            **ctx.progress.get(task_id, {}),
            **progress,
            "updated_at": datetime.now().isoformat(),
        }
        ctx.updated_at = datetime.now().isoformat()
        
        self.memory.store_short_term(
            self._key("context", team_id),
            ctx.to_dict(),
            ttl=7200,
        )
        
        return True
    
    # =========================================================================
    # Inter-Agent Messaging
    # =========================================================================
    
    def send_message(
        self,
        from_agent: str,
        to_agent: str,
        content: Any,
        priority: str = "normal",
        message_type: str = "general",
        metadata: Dict = None,
    ) -> AgentMessage:
        """Send a message between agents."""
        import uuid
        
        message = AgentMessage(
            message_id=f"msg-{uuid.uuid4().hex[:8]}",
            from_agent=from_agent,
            to_agent=to_agent,
            content=content,
            priority=MessagePriority(priority),
            message_type=message_type,
            metadata=metadata or {},
        )
        
        # Store in receiver's inbox
        if to_agent not in self._messages:
            self._messages[to_agent] = []
        
        self._messages[to_agent].append(message)
        
        # Limit messages
        while len(self._messages[to_agent]) > self.max_messages:
            self._messages[to_agent].pop(0)
        
        # Persist
        self.memory.store_short_term(
            self._key("inbox", to_agent),
            [m.to_dict() for m in self._messages[to_agent]],
            ttl=3600,
        )
        
        return message
    
    def broadcast_message(
        self,
        from_agent: str,
        team_id: str,
        agent_ids: List[str],
        content: Any,
        priority: str = "normal",
        message_type: str = "broadcast",
    ) -> List[AgentMessage]:
        """Broadcast message to all team members."""
        messages = []
        for agent_id in agent_ids:
            if agent_id != from_agent:
                msg = self.send_message(
                    from_agent=from_agent,
                    to_agent=agent_id,
                    content=content,
                    priority=priority,
                    message_type=message_type,
                    metadata={"team_id": team_id, "broadcast": True},
                )
                messages.append(msg)
        return messages
    
    def get_messages(
        self,
        agent_id: str,
        unread_only: bool = False,
        message_type: str = None,
        from_agent: str = None,
    ) -> List[AgentMessage]:
        """Get messages for an agent."""
        if agent_id not in self._messages:
            data = self.memory.retrieve(self._key("inbox", agent_id), [])
            self._messages[agent_id] = [AgentMessage.from_dict(m) for m in data]
        
        messages = self._messages[agent_id]
        
        if unread_only:
            messages = [m for m in messages if not m.read]
        
        if message_type:
            messages = [m for m in messages if m.message_type == message_type]
        
        if from_agent:
            messages = [m for m in messages if m.from_agent == from_agent]
        
        return messages
    
    def mark_read(self, agent_id: str, message_id: str) -> bool:
        """Mark a message as read."""
        messages = self._messages.get(agent_id, [])
        for msg in messages:
            if msg.message_id == message_id:
                msg.read = True
                self.memory.store_short_term(
                    self._key("inbox", agent_id),
                    [m.to_dict() for m in messages],
                    ttl=3600,
                )
                return True
        return False
    
    def get_unread_count(self, agent_id: str) -> int:
        """Get count of unread messages."""
        messages = self.get_messages(agent_id, unread_only=True)
        return len(messages)
    
    # =========================================================================
    # Task Handoffs
    # =========================================================================
    
    def record_handoff(
        self,
        from_agent: str,
        to_agent: str,
        task_id: str,
        task_description: str,
        context: Dict[str, Any],
        reason: str = "",
    ) -> TaskHandoff:
        """Record a task handoff between agents."""
        import uuid
        
        handoff = TaskHandoff(
            handoff_id=f"ho-{uuid.uuid4().hex[:8]}",
            task_id=task_id,
            from_agent=from_agent,
            to_agent=to_agent,
            task_description=task_description,
            context=context,
            reason=reason,
        )
        
        self._handoffs.append(handoff)
        
        # Limit handoffs
        while len(self._handoffs) > self.max_handoffs:
            self._handoffs.pop(0)
        
        # Persist
        self.memory.store_long_term(
            "orchestration:handoffs",
            [h.to_dict() for h in self._handoffs],
            priority=6,
        )
        
        # Also send notification message
        self.send_message(
            from_agent=from_agent,
            to_agent=to_agent,
            content={
                "type": "handoff",
                "handoff_id": handoff.handoff_id,
                "task": task_description,
            },
            priority="high",
            message_type="task",
        )
        
        return handoff
    
    def acknowledge_handoff(self, handoff_id: str, agent_id: str) -> bool:
        """Acknowledge receiving a handoff."""
        for handoff in self._handoffs:
            if handoff.handoff_id == handoff_id and handoff.to_agent == agent_id:
                handoff.acknowledged = True
                self.memory.store_long_term(
                    "orchestration:handoffs",
                    [h.to_dict() for h in self._handoffs],
                )
                return True
        return False
    
    def complete_handoff(self, handoff_id: str) -> bool:
        """Mark handoff as completed."""
        for handoff in self._handoffs:
            if handoff.handoff_id == handoff_id:
                handoff.completed = True
                self.memory.store_long_term(
                    "orchestration:handoffs",
                    [h.to_dict() for h in self._handoffs],
                )
                return True
        return False
    
    def get_pending_handoffs(self, agent_id: str) -> List[TaskHandoff]:
        """Get pending handoffs for an agent."""
        return [
            h for h in self._handoffs
            if h.to_agent == agent_id and not h.completed
        ]
    
    def get_handoff_history(
        self,
        agent_id: str = None,
        task_id: str = None,
    ) -> List[TaskHandoff]:
        """Get handoff history."""
        if not self._handoffs:
            data = self.memory.retrieve("orchestration:handoffs", [])
            self._handoffs = [TaskHandoff.from_dict(h) for h in data]
        
        handoffs = self._handoffs
        
        if agent_id:
            handoffs = [h for h in handoffs if h.from_agent == agent_id or h.to_agent == agent_id]
        
        if task_id:
            handoffs = [h for h in handoffs if h.task_id == task_id]
        
        return handoffs
    
    # =========================================================================
    # Agent Contributions
    # =========================================================================
    
    def record_contribution(
        self,
        agent_id: str,
        task_id: str,
        contribution_type: str,
        content: Any,
    ) -> AgentContribution:
        """Record an agent's contribution to a task."""
        import uuid
        
        contribution = AgentContribution(
            contribution_id=f"contrib-{uuid.uuid4().hex[:8]}",
            agent_id=agent_id,
            task_id=task_id,
            contribution_type=contribution_type,
            content=content,
        )
        
        if task_id not in self._contributions:
            self._contributions[task_id] = []
        
        self._contributions[task_id].append(contribution)
        
        # Persist
        self.memory.store_short_term(
            self._key("contributions", task_id),
            [c.to_dict() for c in self._contributions[task_id]],
            ttl=7200,
        )
        
        return contribution
    
    def get_task_contributions(
        self,
        task_id: str,
        agent_id: str = None,
    ) -> List[AgentContribution]:
        """Get all contributions for a task."""
        if task_id not in self._contributions:
            data = self.memory.retrieve(self._key("contributions", task_id), [])
            self._contributions[task_id] = [AgentContribution.from_dict(c) for c in data]
        
        contributions = self._contributions[task_id]
        
        if agent_id:
            contributions = [c for c in contributions if c.agent_id == agent_id]
        
        return contributions
    
    def aggregate_contributions(
        self,
        task_id: str,
        contribution_type: str = None,
    ) -> List[Any]:
        """Aggregate all contributions for a task."""
        contributions = self.get_task_contributions(task_id)
        
        if contribution_type:
            contributions = [c for c in contributions if c.contribution_type == contribution_type]
        
        return [c.content for c in contributions]
    
    # =========================================================================
    # Stats & Cleanup
    # =========================================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """Get orchestration memory statistics."""
        total_messages = sum(len(msgs) for msgs in self._messages.values())
        unread = sum(
            len([m for m in msgs if not m.read])
            for msgs in self._messages.values()
        )
        
        return {
            "active_teams": len(self._contexts),
            "total_messages": total_messages,
            "unread_messages": unread,
            "total_handoffs": len(self._handoffs),
            "pending_handoffs": len([h for h in self._handoffs if not h.completed]),
            "tasks_with_contributions": len(self._contributions),
        }
    
    def cleanup_team(self, team_id: str):
        """Clean up memory for a team."""
        self._contexts.pop(team_id, None)
        # Note: Messages and handoffs are kept for history


__all__ = [
    "MessagePriority",
    "AgentMessage",
    "TaskHandoff",
    "SharedContext",
    "AgentContribution",
    "OrchestrationMemoryManager",
]
