"""
Agent Teams for coordinated multi-agent collaboration.
"""

import uuid
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from .models import TeamRole

if TYPE_CHECKING:
    from ..core.agent import Agent

logger = logging.getLogger(__name__)


class AgentTeam:
    """
    A coordinated group of agents working together.
    
    Teams enable structured collaboration with defined roles,
    shared goals, and coordinated execution.
    
    Features:
    - Role-based agent assignment
    - Shared team context
    - Coordinated task execution
    - Team-level metrics
    """
    
    def __init__(self,
                 name: str,
                 goal: str,
                 roles: Optional[List[TeamRole]] = None):
        """
        Initialize agent team.
        
        Args:
            name: Team name
            goal: Team goal/objective
            roles: Defined roles in the team
        """
        self.id = str(uuid.uuid4())
        self.name = name
        self.goal = goal
        self.roles = roles or []
        
        # Team members
        self.members: Dict[str, 'Agent'] = {}
        self.role_assignments: Dict[str, str] = {}  # agent_id -> role_name
        
        # Shared context
        self.shared_context: Dict[str, Any] = {}
        self.message_history: List[Dict[str, Any]] = []
        
        # Execution state
        self.current_task: Optional[str] = None
        self.task_results: Dict[str, Any] = {}
        
        # Metrics
        self.metrics = {
            'tasks_completed': 0,
            'messages_exchanged': 0,
            'collaboration_score': 0.0
        }
        
        self.created_at = datetime.now()
        self.status = "active"
    
    def add_role(self, role: TeamRole) -> None:
        """Add a role to the team."""
        self.roles.append(role)
    
    def add_member(self, agent: 'Agent', role_name: str) -> None:
        """Add an agent to the team with a specific role."""
        role = next((r for r in self.roles if r.name == role_name), None)
        if role:
            current_in_role = sum(
                1 for r in self.role_assignments.values() if r == role_name
            )
            if current_in_role >= role.max_agents:
                raise ValueError(f"Role '{role_name}' has max agents")
        
        self.members[agent.id] = agent
        self.role_assignments[agent.id] = role_name
        
        agent.add_context(
            f"Joined team '{self.name}' with goal: {self.goal}. Role: {role_name}",
            importance=0.9
        )
    
    def remove_member(self, agent_id: str) -> None:
        """Remove an agent from the team."""
        if agent_id in self.members:
            del self.members[agent_id]
            self.role_assignments.pop(agent_id, None)
    
    def get_members_by_role(self, role_name: str) -> List['Agent']:
        """Get all agents with a specific role."""
        return [
            self.members[agent_id]
            for agent_id, role in self.role_assignments.items()
            if role == role_name and agent_id in self.members
        ]
    
    def broadcast_message(self, sender: 'Agent', message: str, importance: float = 0.5) -> None:
        """Broadcast a message to all team members."""
        msg_record = {
            'sender_id': sender.id,
            'sender_name': sender.name,
            'message': message,
            'timestamp': datetime.now().isoformat()
        }
        self.message_history.append(msg_record)
        
        for member in self.members.values():
            if member.id != sender.id:
                member.add_context(
                    f"[Team:{self.name}] {sender.name}: {message}",
                    importance=importance
                )
        
        self.metrics['messages_exchanged'] += 1
    
    def share_context(self, key: str, value: Any, sender: Optional['Agent'] = None) -> None:
        """Share context with all team members."""
        self.shared_context[key] = value
        
        sender_info = f" (from {sender.name})" if sender else ""
        for member in self.members.values():
            if sender is None or member.id != sender.id:
                member.add_context(
                    f"[Team Context{sender_info}] {key}: {str(value)[:200]}",
                    importance=0.6
                )
    
    def execute_collaborative(self,
                             task_name: str,
                             task_plan: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Execute a collaborative task with the team.
        
        Args:
            task_name: Name of the task
            task_plan: List of steps with role assignments
                      [{'role': 'researcher', 'action': callable, 'args': {}}]
        
        Returns:
            Results from all steps
        """
        self.current_task = task_name
        results = {}
        
        for i, step in enumerate(task_plan):
            role_name = step.get('role')
            action = step.get('action')
            args = step.get('args', {})
            
            agents = self.get_members_by_role(role_name)
            if not agents:
                results[f"step_{i}"] = {'error': f"No agent for role '{role_name}'"}
                continue
            
            agent = agents[0]
            
            try:
                if callable(action):
                    result = agent.execute_task(action, **args)
                    results[f"step_{i}"] = {'success': True, 'result': result}
                else:
                    results[f"step_{i}"] = {'success': True, 'result': action}
                
                self.share_context(f"step_{i}_result", result, agent)
                
            except Exception as e:  # noqa: BLE001
                results[f"step_{i}"] = {'success': False, 'error': str(e)}
        
        self.task_results[task_name] = results
        self.metrics['tasks_completed'] += 1
        self.current_task = None
        
        return results
    
    def get_team_status(self) -> Dict[str, Any]:
        """Get team status and metrics."""
        return {
            'id': self.id,
            'name': self.name,
            'goal': self.goal,
            'status': self.status,
            'member_count': len(self.members),
            'roles': [r.name for r in self.roles],
            'current_task': self.current_task,
            'metrics': self.metrics,
            'members': [
                {
                    'id': agent.id,
                    'name': agent.name,
                    'role': self.role_assignments.get(agent.id),
                    'status': agent.status
                }
                for agent in self.members.values()
            ]
        }
