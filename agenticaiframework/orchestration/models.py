"""
Data models for agent orchestration.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from .types import SupervisionStrategy


@dataclass
class TaskAssignment:
    """Represents a task assigned to an agent."""
    task_id: str
    agent_id: str
    task_callable: Optional[Callable]
    args: Tuple = field(default_factory=tuple)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    deadline: Optional[datetime] = None
    dependencies: List[str] = field(default_factory=list)
    status: str = "pending"
    result: Any = None
    error: Optional[str] = None
    assigned_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retries: int = 0
    max_retries: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def duration(self) -> Optional[float]:
        """Get task duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    @property
    def is_complete(self) -> bool:
        """Check if task is complete."""
        return self.status in ("completed", "failed")
    
    @property
    def can_retry(self) -> bool:
        """Check if task can be retried."""
        return self.retries < self.max_retries


@dataclass
class AgentHandoff:
    """Represents a handoff between agents."""
    handoff_id: str
    from_agent_id: str
    to_agent_id: str
    context: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    reason: str = ""
    success: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'handoff_id': self.handoff_id,
            'from_agent_id': self.from_agent_id,
            'to_agent_id': self.to_agent_id,
            'context': self.context,
            'timestamp': self.timestamp.isoformat(),
            'reason': self.reason,
            'success': self.success,
        }


@dataclass 
class SupervisionConfig:
    """Configuration for agent supervision."""
    strategy: SupervisionStrategy = SupervisionStrategy.ONE_FOR_ONE
    max_restarts: int = 3
    restart_window: float = 60.0  # seconds
    backoff_multiplier: float = 2.0
    initial_backoff: float = 1.0
    max_backoff: float = 60.0
    health_check_interval: float = 30.0
    timeout: float = 300.0
    
    def get_backoff(self, restart_count: int) -> float:
        """Calculate backoff time for given restart count."""
        return min(
            self.initial_backoff * (self.backoff_multiplier ** restart_count),
            self.max_backoff
        )


@dataclass
class TeamRole:
    """Role definition within a team."""
    name: str
    description: str
    required_capabilities: List[str] = field(default_factory=list)
    max_agents: int = 1
    min_agents: int = 1
    
    def is_valid_count(self, count: int) -> bool:
        """Check if agent count is valid for this role."""
        return self.min_agents <= count <= self.max_agents
