"""
Orchestration State Management.

Provides state tracking for multi-agent orchestration, teams, and coordination.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from .manager import StateManager, StateType

logger = logging.getLogger(__name__)


class CoordinationMode(Enum):
    """Coordination mode for multi-agent teams."""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    HIERARCHICAL = "hierarchical"
    CONSENSUS = "consensus"
    BROADCAST = "broadcast"


class AgentCoordinationStatus(Enum):
    """Status of an agent in coordination."""
    AVAILABLE = "available"
    ASSIGNED = "assigned"
    WORKING = "working"
    WAITING = "waiting"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AgentCoordinationState:
    """State of an agent in orchestration context."""
    agent_id: str
    name: str
    role: str
    status: AgentCoordinationStatus
    current_task: Optional[str] = None
    task_queue: List[str] = field(default_factory=list)
    completed_tasks: List[str] = field(default_factory=list)
    last_activity: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "role": self.role,
            "status": self.status.value,
            "current_task": self.current_task,
            "task_queue": self.task_queue,
            "completed_tasks": self.completed_tasks,
            "last_activity": self.last_activity,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentCoordinationState":
        return cls(
            agent_id=data["agent_id"],
            name=data["name"],
            role=data["role"],
            status=AgentCoordinationStatus(data["status"]),
            current_task=data.get("current_task"),
            task_queue=data.get("task_queue", []),
            completed_tasks=data.get("completed_tasks", []),
            last_activity=data.get("last_activity", datetime.now().isoformat()),
            metadata=data.get("metadata", {}),
        )


@dataclass
class TaskQueueState:
    """State of the task queue in orchestration."""
    queue_id: str
    pending: List[Dict[str, Any]] = field(default_factory=list)
    in_progress: List[Dict[str, Any]] = field(default_factory=list)
    completed: List[Dict[str, Any]] = field(default_factory=list)
    failed: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "queue_id": self.queue_id,
            "pending": self.pending,
            "in_progress": self.in_progress,
            "completed": self.completed,
            "failed": self.failed,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskQueueState":
        return cls(
            queue_id=data["queue_id"],
            pending=data.get("pending", []),
            in_progress=data.get("in_progress", []),
            completed=data.get("completed", []),
            failed=data.get("failed", []),
        )
    
    @property
    def total_tasks(self) -> int:
        return len(self.pending) + len(self.in_progress) + len(self.completed) + len(self.failed)
    
    @property
    def completion_rate(self) -> float:
        if self.total_tasks == 0:
            return 0.0
        return len(self.completed) / self.total_tasks


@dataclass
class TeamState:
    """State of an agent team."""
    team_id: str
    name: str
    mode: CoordinationMode
    supervisor_id: Optional[str]
    agents: Dict[str, AgentCoordinationState]
    task_queue: TaskQueueState
    shared_context: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "team_id": self.team_id,
            "name": self.name,
            "mode": self.mode.value,
            "supervisor_id": self.supervisor_id,
            "agents": {k: v.to_dict() for k, v in self.agents.items()},
            "task_queue": self.task_queue.to_dict(),
            "shared_context": self.shared_context,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TeamState":
        return cls(
            team_id=data["team_id"],
            name=data["name"],
            mode=CoordinationMode(data["mode"]),
            supervisor_id=data.get("supervisor_id"),
            agents={k: AgentCoordinationState.from_dict(v) for k, v in data.get("agents", {}).items()},
            task_queue=TaskQueueState.from_dict(data.get("task_queue", {"queue_id": data["team_id"]})),
            shared_context=data.get("shared_context", {}),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            metadata=data.get("metadata", {}),
        )
    
    @property
    def available_agents(self) -> List[AgentCoordinationState]:
        """Get agents that are available for work."""
        return [a for a in self.agents.values() if a.status == AgentCoordinationStatus.AVAILABLE]
    
    @property
    def busy_agents(self) -> List[AgentCoordinationState]:
        """Get agents currently working."""
        return [a for a in self.agents.values() if a.status == AgentCoordinationStatus.WORKING]


class OrchestrationStateManager:
    """
    Manages state for multi-agent orchestration.
    
    Example:
        >>> orch = OrchestrationStateManager()
        >>> 
        >>> # Create team
        >>> team = orch.create_team("research-team", mode="parallel")
        >>> 
        >>> # Add agents
        >>> orch.add_agent(team.team_id, agent_id="agent1", name="Researcher")
        >>> 
        >>> # Assign tasks
        >>> orch.assign_task(team.team_id, "agent1", task={"type": "search"})
        >>> 
        >>> # Track coordination
        >>> orch.update_agent_status(team.team_id, "agent1", "working")
    """
    
    def __init__(self, state_manager: StateManager = None):
        self.state_manager = state_manager or StateManager()
    
    def _save_team(self, team: TeamState) -> bool:
        """Save team state."""
        team.updated_at = datetime.now().isoformat()
        return self.state_manager.save(
            f"orchestration:{team.team_id}",
            team.to_dict(),
            StateType.ORCHESTRATION,
        )
    
    def create_team(
        self,
        name: str,
        mode: str = "sequential",
        supervisor_id: str = None,
        metadata: Dict = None,
    ) -> TeamState:
        """Create a new agent team."""
        import uuid
        team_id = f"team-{uuid.uuid4().hex[:8]}"
        
        team = TeamState(
            team_id=team_id,
            name=name,
            mode=CoordinationMode(mode),
            supervisor_id=supervisor_id,
            agents={},
            task_queue=TaskQueueState(queue_id=team_id),
            metadata=metadata or {},
        )
        
        self._save_team(team)
        return team
    
    def get_team(self, team_id: str) -> Optional[TeamState]:
        """Get team state."""
        data = self.state_manager.get(f"orchestration:{team_id}")
        if data:
            return TeamState.from_dict(data)
        return None
    
    def delete_team(self, team_id: str) -> bool:
        """Delete team."""
        return self.state_manager.delete(f"orchestration:{team_id}")
    
    def list_teams(self) -> List[TeamState]:
        """List all teams."""
        keys = self.state_manager.list("orchestration:")
        teams = []
        for key in keys:
            data = self.state_manager.get(key)
            if data:
                teams.append(TeamState.from_dict(data))
        return teams
    
    # Agent Management
    def add_agent(
        self,
        team_id: str,
        agent_id: str,
        name: str,
        role: str = "worker",
    ) -> Optional[AgentCoordinationState]:
        """Add agent to team."""
        team = self.get_team(team_id)
        if not team:
            return None
        
        agent_state = AgentCoordinationState(
            agent_id=agent_id,
            name=name,
            role=role,
            status=AgentCoordinationStatus.AVAILABLE,
        )
        
        team.agents[agent_id] = agent_state
        self._save_team(team)
        return agent_state
    
    def remove_agent(self, team_id: str, agent_id: str) -> bool:
        """Remove agent from team."""
        team = self.get_team(team_id)
        if not team or agent_id not in team.agents:
            return False
        
        del team.agents[agent_id]
        self._save_team(team)
        return True
    
    def update_agent_status(
        self,
        team_id: str,
        agent_id: str,
        status: str,
        current_task: str = None,
    ) -> bool:
        """Update agent status."""
        team = self.get_team(team_id)
        if not team or agent_id not in team.agents:
            return False
        
        agent = team.agents[agent_id]
        agent.status = AgentCoordinationStatus(status)
        agent.last_activity = datetime.now().isoformat()
        if current_task is not None:
            agent.current_task = current_task
        
        self._save_team(team)
        return True
    
    def get_agent_state(
        self,
        team_id: str,
        agent_id: str,
    ) -> Optional[AgentCoordinationState]:
        """Get agent coordination state."""
        team = self.get_team(team_id)
        if team:
            return team.agents.get(agent_id)
        return None
    
    # Task Management
    def add_task(
        self,
        team_id: str,
        task_id: str,
        task_data: Dict,
        priority: int = 0,
    ) -> bool:
        """Add task to team queue."""
        team = self.get_team(team_id)
        if not team:
            return False
        
        task = {
            "task_id": task_id,
            "data": task_data,
            "priority": priority,
            "created_at": datetime.now().isoformat(),
        }
        
        team.task_queue.pending.append(task)
        # Sort by priority (higher first)
        team.task_queue.pending.sort(key=lambda x: x.get("priority", 0), reverse=True)
        
        self._save_team(team)
        return True
    
    def assign_task(
        self,
        team_id: str,
        agent_id: str,
        task_id: str = None,
    ) -> Optional[Dict]:
        """Assign task to agent (or next pending task if task_id is None)."""
        team = self.get_team(team_id)
        if not team or agent_id not in team.agents:
            return None
        
        agent = team.agents[agent_id]
        
        # Find task
        task = None
        if task_id:
            for i, t in enumerate(team.task_queue.pending):
                if t["task_id"] == task_id:
                    task = team.task_queue.pending.pop(i)
                    break
        else:
            if team.task_queue.pending:
                task = team.task_queue.pending.pop(0)
        
        if not task:
            return None
        
        # Assign to agent
        task["assigned_to"] = agent_id
        task["assigned_at"] = datetime.now().isoformat()
        team.task_queue.in_progress.append(task)
        
        agent.current_task = task["task_id"]
        agent.status = AgentCoordinationStatus.WORKING
        agent.last_activity = datetime.now().isoformat()
        
        self._save_team(team)
        return task
    
    def complete_task(
        self,
        team_id: str,
        agent_id: str,
        task_id: str,
        result: Any = None,
    ) -> bool:
        """Mark task as completed."""
        team = self.get_team(team_id)
        if not team:
            return False
        
        # Find and move task
        task = None
        for i, t in enumerate(team.task_queue.in_progress):
            if t["task_id"] == task_id:
                task = team.task_queue.in_progress.pop(i)
                break
        
        if not task:
            return False
        
        task["completed_at"] = datetime.now().isoformat()
        task["result"] = result
        team.task_queue.completed.append(task)
        
        # Update agent
        if agent_id in team.agents:
            agent = team.agents[agent_id]
            agent.current_task = None
            agent.completed_tasks.append(task_id)
            agent.status = AgentCoordinationStatus.AVAILABLE
            agent.last_activity = datetime.now().isoformat()
        
        self._save_team(team)
        return True
    
    def fail_task(
        self,
        team_id: str,
        agent_id: str,
        task_id: str,
        error: str,
    ) -> bool:
        """Mark task as failed."""
        team = self.get_team(team_id)
        if not team:
            return False
        
        # Find and move task
        task = None
        for i, t in enumerate(team.task_queue.in_progress):
            if t["task_id"] == task_id:
                task = team.task_queue.in_progress.pop(i)
                break
        
        if not task:
            return False
        
        task["failed_at"] = datetime.now().isoformat()
        task["error"] = error
        team.task_queue.failed.append(task)
        
        # Update agent
        if agent_id in team.agents:
            agent = team.agents[agent_id]
            agent.current_task = None
            agent.status = AgentCoordinationStatus.AVAILABLE
            agent.last_activity = datetime.now().isoformat()
        
        self._save_team(team)
        return True
    
    # Shared Context
    def update_shared_context(
        self,
        team_id: str,
        key: str,
        value: Any,
    ) -> bool:
        """Update shared context for team."""
        team = self.get_team(team_id)
        if not team:
            return False
        
        team.shared_context[key] = value
        self._save_team(team)
        return True
    
    def get_shared_context(
        self,
        team_id: str,
        key: str = None,
    ) -> Optional[Any]:
        """Get shared context (all or specific key)."""
        team = self.get_team(team_id)
        if not team:
            return None
        
        if key:
            return team.shared_context.get(key)
        return team.shared_context
    
    # Status and Stats
    def get_team_status(self, team_id: str) -> Optional[Dict[str, Any]]:
        """Get team status summary."""
        team = self.get_team(team_id)
        if not team:
            return None
        
        return {
            "team_id": team_id,
            "name": team.name,
            "mode": team.mode.value,
            "total_agents": len(team.agents),
            "available_agents": len(team.available_agents),
            "busy_agents": len(team.busy_agents),
            "pending_tasks": len(team.task_queue.pending),
            "in_progress_tasks": len(team.task_queue.in_progress),
            "completed_tasks": len(team.task_queue.completed),
            "failed_tasks": len(team.task_queue.failed),
            "completion_rate": team.task_queue.completion_rate,
            "updated_at": team.updated_at,
        }
    
    def get_all_agent_statuses(self, team_id: str) -> List[Dict]:
        """Get status of all agents in team."""
        team = self.get_team(team_id)
        if not team:
            return []
        
        return [
            {
                "agent_id": a.agent_id,
                "name": a.name,
                "role": a.role,
                "status": a.status.value,
                "current_task": a.current_task,
                "completed_count": len(a.completed_tasks),
                "queue_size": len(a.task_queue),
                "last_activity": a.last_activity,
            }
            for a in team.agents.values()
        ]


__all__ = [
    "CoordinationMode",
    "AgentCoordinationStatus",
    "AgentCoordinationState",
    "TaskQueueState",
    "TeamState",
    "OrchestrationStateManager",
]
