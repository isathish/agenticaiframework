"""
Agent Supervisor implementing Erlang/OTP-style supervision trees.
"""

import uuid
import time
import logging
from collections import defaultdict
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from .types import SupervisionStrategy, AgentRole, AgentState
from .models import TaskAssignment, AgentHandoff, SupervisionConfig

if TYPE_CHECKING:
    from ..core.agent import Agent

logger = logging.getLogger(__name__)


class AgentSupervisor:
    """
    Supervisor for managing agents at any level in a hierarchy.
    
    Implements supervision trees similar to Erlang/OTP for fault-tolerant
    agent management. Can supervise individual agents or other supervisors.
    
    Features:
    - Hierarchical supervision (supervisors can supervise supervisors)
    - Multiple supervision strategies
    - Automatic failure recovery
    - Health monitoring
    - Task delegation
    - Load balancing
    """
    
    def __init__(self,
                 name: str,
                 config: Optional[SupervisionConfig] = None,
                 parent_supervisor: Optional['AgentSupervisor'] = None):
        """
        Initialize the supervisor.
        
        Args:
            name: Supervisor name
            config: Supervision configuration
            parent_supervisor: Parent supervisor (for hierarchical supervision)
        """
        self.id = str(uuid.uuid4())
        self.name = name
        self.config = config or SupervisionConfig()
        self.parent_supervisor = parent_supervisor
        
        # Supervised entities
        self.agents: Dict[str, 'Agent'] = {}
        self.child_supervisors: Dict[str, 'AgentSupervisor'] = {}
        
        # Task management
        self.task_queue: List[TaskAssignment] = []
        self.active_tasks: Dict[str, TaskAssignment] = {}
        self.completed_tasks: List[TaskAssignment] = []
        
        # Handoff tracking
        self.handoffs: List[AgentHandoff] = []
        
        # State tracking
        self.restart_counts: Dict[str, int] = defaultdict(int)
        self.restart_times: Dict[str, List[float]] = defaultdict(list)
        self.agent_states: Dict[str, AgentState] = {}
        
        # Metrics
        self.metrics = {
            'tasks_delegated': 0,
            'tasks_completed': 0,
            'tasks_failed': 0,
            'restarts': 0,
            'escalations': 0,
            'handoffs': 0
        }
        
        self.status = "running"
        self.created_at = datetime.now()
        
        logger.info("Supervisor '%s' initialized with strategy %s", 
                   name, self.config.strategy.value)
    
    def add_agent(self, agent: 'Agent', role: AgentRole = AgentRole.WORKER) -> None:
        """Add an agent under this supervisor's control."""
        self.agents[agent.id] = agent
        self.agent_states[agent.id] = AgentState.IDLE
        agent.role = role
        agent.supervisor_id = self.id
        logger.info("Agent '%s' added to supervisor '%s'", agent.name, self.name)
    
    def remove_agent(self, agent_id: str) -> None:
        """Remove an agent from supervision."""
        if agent_id in self.agents:
            agent = self.agents[agent_id]
            agent.stop()
            del self.agents[agent_id]
            self.agent_states.pop(agent_id, None)
            logger.info("Agent removed from supervisor '%s'", self.name)
    
    def add_child_supervisor(self, supervisor: 'AgentSupervisor') -> None:
        """Add a child supervisor (for hierarchical supervision)."""
        supervisor.parent_supervisor = self
        self.child_supervisors[supervisor.id] = supervisor
        logger.info("Child supervisor '%s' added to '%s'", supervisor.name, self.name)
    
    def get_all_agents(self, recursive: bool = True) -> List['Agent']:
        """Get all agents, optionally including those under child supervisors."""
        agents = list(self.agents.values())
        
        if recursive:
            for child in self.child_supervisors.values():
                agents.extend(child.get_all_agents(recursive=True))
        
        return agents
    
    def get_available_agents(self, capability: Optional[str] = None) -> List['Agent']:
        """Get agents that are available for work."""
        available = []
        
        for agent_id, agent in self.agents.items():
            state = self.agent_states.get(agent_id, AgentState.IDLE)
            if state == AgentState.IDLE:
                if capability is None or capability in agent.capabilities:
                    available.append(agent)
        
        return available
    
    def delegate_task(self,
                     task_callable: Callable,
                     args: tuple = (),
                     kwargs: Optional[Dict[str, Any]] = None,
                     priority: int = 0,
                     required_capability: Optional[str] = None,
                     preferred_agent_id: Optional[str] = None,
                     deadline: Optional[datetime] = None) -> str:
        """
        Delegate a task to an appropriate agent.
        
        Returns:
            Task ID
        """
        kwargs = kwargs or {}
        
        task = TaskAssignment(
            task_id=str(uuid.uuid4()),
            agent_id="",
            task_callable=task_callable,
            args=args,
            kwargs=kwargs,
            priority=priority,
            deadline=deadline
        )
        
        agent = self._select_agent(required_capability, preferred_agent_id)
        
        if agent:
            task.agent_id = agent.id
            self._assign_task(task, agent)
        else:
            self.task_queue.append(task)
            self.task_queue.sort(key=lambda t: -t.priority)
            logger.warning("No available agent, task queued: %s", task.task_id)
        
        self.metrics['tasks_delegated'] += 1
        return task.task_id
    
    def _select_agent(self,
                     required_capability: Optional[str],
                     preferred_agent_id: Optional[str]) -> Optional['Agent']:
        """Select best agent for a task."""
        if preferred_agent_id and preferred_agent_id in self.agents:
            agent = self.agents[preferred_agent_id]
            if self.agent_states.get(agent.id) == AgentState.IDLE:
                return agent
        
        available = self.get_available_agents(required_capability)
        
        if not available:
            for child in self.child_supervisors.values():
                available = child.get_available_agents(required_capability)
                if available:
                    break
        
        if not available:
            return None
        
        def agent_score(agent):
            metrics = agent.get_performance_metrics()
            return metrics.get('success_rate', 0.5) - (metrics.get('total_tasks', 0) * 0.01)
        
        return max(available, key=agent_score)
    
    def _assign_task(self, task: TaskAssignment, agent: 'Agent') -> None:
        """Assign task to agent and execute."""
        task.agent_id = agent.id
        task.status = "assigned"
        task.started_at = datetime.now()
        
        self.active_tasks[task.task_id] = task
        self.agent_states[agent.id] = AgentState.BUSY
        
        try:
            result = agent.execute_task(task.task_callable, *task.args, **task.kwargs)
            task.result = result
            task.status = "completed"
            task.completed_at = datetime.now()
            self.metrics['tasks_completed'] += 1
            
        except Exception as e:  # noqa: BLE001
            task.error = str(e)
            task.status = "failed"
            task.completed_at = datetime.now()
            self.metrics['tasks_failed'] += 1
            self._handle_agent_failure(agent, task, e)
        
        finally:
            self.agent_states[agent.id] = AgentState.IDLE
            self.active_tasks.pop(task.task_id, None)
            self.completed_tasks.append(task)
            self._process_queue()
    
    def _process_queue(self) -> None:
        """Process queued tasks."""
        if not self.task_queue:
            return
        
        available = self.get_available_agents()
        
        while self.task_queue and available:
            task = self.task_queue.pop(0)
            agent = available.pop(0)
            self._assign_task(task, agent)
    
    def _handle_agent_failure(self, agent: 'Agent', task: TaskAssignment, error: Exception) -> None:
        """Handle agent failure based on supervision strategy."""
        logger.error("Agent '%s' failed on task %s: %s", agent.name, task.task_id, error)
        
        strategy = self.config.strategy
        
        if strategy == SupervisionStrategy.IGNORE:
            return
        
        if strategy == SupervisionStrategy.ESCALATE:
            if self.parent_supervisor:
                self.parent_supervisor.handle_escalation(self, agent, task, error)
                self.metrics['escalations'] += 1
            return
        
        if not self._can_restart(agent.id):
            logger.error("Agent '%s' exceeded restart limit, escalating", agent.name)
            if self.parent_supervisor:
                self.parent_supervisor.handle_escalation(self, agent, task, error)
            return
        
        if strategy == SupervisionStrategy.ONE_FOR_ONE:
            self._restart_agent(agent)
        elif strategy == SupervisionStrategy.ONE_FOR_ALL:
            for a in self.agents.values():
                self._restart_agent(a)
        elif strategy == SupervisionStrategy.REST_FOR_ONE:
            restart = False
            for a in self.agents.values():
                if a.id == agent.id:
                    restart = True
                if restart:
                    self._restart_agent(a)
        
        if task.can_retry:
            task.retries += 1
            task.status = "pending"
            self.task_queue.insert(0, task)
    
    def _can_restart(self, agent_id: str) -> bool:
        """Check if agent can be restarted within limits."""
        now = time.time()
        window = self.config.restart_window
        
        self.restart_times[agent_id] = [
            t for t in self.restart_times[agent_id]
            if now - t < window
        ]
        
        return len(self.restart_times[agent_id]) < self.config.max_restarts
    
    def _restart_agent(self, agent: 'Agent') -> None:
        """Restart an agent."""
        logger.info("Restarting agent '%s'", agent.name)
        
        self.restart_times[agent.id].append(time.time())
        self.restart_counts[agent.id] += 1
        self.metrics['restarts'] += 1
        
        backoff = self.config.get_backoff(self.restart_counts[agent.id])
        time.sleep(backoff)
        
        self.agent_states[agent.id] = AgentState.RECOVERING
        agent.stop()
        agent.start()
        self.agent_states[agent.id] = AgentState.IDLE
    
    def handle_escalation(self, 
                         child_supervisor: 'AgentSupervisor',
                         agent: 'Agent',
                         task: TaskAssignment,
                         error: Exception) -> None:
        """Handle escalation from child supervisor."""
        logger.warning("Escalation from '%s' for agent '%s'", 
                      child_supervisor.name, agent.name)
        
        available = self.get_available_agents()
        
        if available:
            task.retries = 0
            self._assign_task(task, available[0])
        elif self.parent_supervisor:
            self.parent_supervisor.handle_escalation(self, agent, task, error)
    
    def handoff(self,
               from_agent: 'Agent',
               to_agent: 'Agent',
               context: Dict[str, Any],
               reason: str = "") -> str:
        """Perform a handoff from one agent to another."""
        handoff = AgentHandoff(
            handoff_id=str(uuid.uuid4()),
            from_agent_id=from_agent.id,
            to_agent_id=to_agent.id,
            context=context,
            reason=reason
        )
        
        try:
            for ctx_key, ctx_value in context.items():
                if isinstance(ctx_value, str):
                    to_agent.add_context(
                        f"Handoff from {from_agent.name} [{ctx_key}]: {ctx_value}",
                        importance=0.7
                    )
            
            handoff.success = True
            self.metrics['handoffs'] += 1
            
        except Exception as e:  # noqa: BLE001
            logger.error("Handoff failed: %s", e)
            handoff.success = False
        
        self.handoffs.append(handoff)
        return handoff.handoff_id
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of all supervised entities."""
        status = {
            'supervisor': {
                'id': self.id,
                'name': self.name,
                'status': self.status,
                'uptime': (datetime.now() - self.created_at).total_seconds()
            },
            'agents': {},
            'child_supervisors': {},
            'metrics': self.metrics.copy()
        }
        
        for agent_id, agent in self.agents.items():
            metrics = agent.get_performance_metrics()
            status['agents'][agent_id] = {
                'name': agent.name,
                'state': self.agent_states.get(agent_id, AgentState.IDLE).value,
                'success_rate': metrics.get('success_rate', 0),
                'total_tasks': metrics.get('total_tasks', 0),
                'restarts': self.restart_counts.get(agent_id, 0)
            }
        
        for child_id, child in self.child_supervisors.items():
            status['child_supervisors'][child_id] = child.get_health_status()
        
        return status
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get supervisor metrics."""
        return {
            **self.metrics,
            'total_agents': len(self.agents),
            'child_supervisors': len(self.child_supervisors),
            'queued_tasks': len(self.task_queue),
            'active_tasks': len(self.active_tasks),
            'completed_tasks': len(self.completed_tasks),
            'total_handoffs': len(self.handoffs)
        }
