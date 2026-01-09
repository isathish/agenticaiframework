"""
Orchestration Engine for agent coordination.
"""

import uuid
import logging
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from .types import OrchestrationPattern
from .supervisor import AgentSupervisor
from .teams import AgentTeam

if TYPE_CHECKING:
    from ..core.agent import Agent

logger = logging.getLogger(__name__)


class OrchestrationEngine:
    """
    Central engine for agent orchestration.
    
    Provides various orchestration patterns and coordinates
    complex multi-agent workflows.
    
    Features:
    - Multiple orchestration patterns
    - Workflow management
    - Dynamic agent selection
    - Result aggregation
    - Failure recovery
    """
    
    def __init__(self, default_pattern: OrchestrationPattern = OrchestrationPattern.SEQUENTIAL):
        self.default_pattern = default_pattern
        self.supervisors: Dict[str, AgentSupervisor] = {}
        self.teams: Dict[str, AgentTeam] = {}
        self.workflows: Dict[str, Dict[str, Any]] = {}
        
        self.execution_history: List[Dict[str, Any]] = []
        self.metrics = {
            'orchestrations_completed': 0,
            'orchestrations_failed': 0,
            'total_agent_invocations': 0
        }
    
    def register_supervisor(self, supervisor: AgentSupervisor) -> None:
        """Register a supervisor with the engine."""
        self.supervisors[supervisor.id] = supervisor
    
    def register_team(self, team: AgentTeam) -> None:
        """Register a team with the engine."""
        self.teams[team.id] = team
    
    def orchestrate(self,
                   agents: List['Agent'],
                   task_callable: Callable,
                   pattern: Optional[OrchestrationPattern] = None,
                   aggregator: Optional[Callable[[List[Any]], Any]] = None,
                   **kwargs) -> Any:
        """
        Orchestrate agents to execute a task.
        
        Args:
            agents: List of agents to orchestrate
            task_callable: Task to execute
            pattern: Orchestration pattern to use
            aggregator: Function to aggregate results
            **kwargs: Additional arguments for task
            
        Returns:
            Orchestration result
        """
        pattern = pattern or self.default_pattern
        
        execution = {
            'id': str(uuid.uuid4()),
            'pattern': pattern.value,
            'agent_count': len(agents),
            'started_at': datetime.now().isoformat(),
            'status': 'running'
        }
        
        try:
            result = self._execute_pattern(agents, task_callable, pattern, **kwargs)
            
            if aggregator and isinstance(result, list):
                result = aggregator(result)
            
            execution['status'] = 'completed'
            execution['result'] = str(result)[:200] if result else None
            self.metrics['orchestrations_completed'] += 1
            
        except Exception as e:  # noqa: BLE001
            execution['status'] = 'failed'
            execution['error'] = str(e)
            self.metrics['orchestrations_failed'] += 1
            raise
        
        finally:
            execution['completed_at'] = datetime.now().isoformat()
            self.execution_history.append(execution)
        
        return result
    
    def _execute_pattern(self,
                        agents: List['Agent'],
                        task_callable: Callable,
                        pattern: OrchestrationPattern,
                        **kwargs) -> Any:
        """Execute the specified orchestration pattern."""
        pattern_methods = {
            OrchestrationPattern.SEQUENTIAL: self._sequential,
            OrchestrationPattern.PARALLEL: self._parallel,
            OrchestrationPattern.HIERARCHICAL: self._hierarchical,
            OrchestrationPattern.PIPELINE: self._pipeline,
            OrchestrationPattern.BROADCAST: self._parallel,
            OrchestrationPattern.CONSENSUS: self._consensus,
            OrchestrationPattern.ROUND_ROBIN: self._round_robin,
            OrchestrationPattern.SWARM: self._swarm,
        }
        
        method = pattern_methods.get(pattern, self._sequential)
        return method(agents, task_callable, **kwargs)
    
    def _sequential(self, agents: List['Agent'], task_callable: Callable, **kwargs) -> List[Any]:
        """Execute task sequentially through agents."""
        results = []
        for agent in agents:
            result = agent.execute_task(task_callable, **kwargs)
            results.append(result)
            self.metrics['total_agent_invocations'] += 1
        return results
    
    def _parallel(self, agents: List['Agent'], task_callable: Callable, **kwargs) -> List[Any]:
        """Execute task in parallel across agents."""
        results = []
        with ThreadPoolExecutor(max_workers=len(agents)) as executor:
            futures = {
                executor.submit(agent.execute_task, task_callable, **kwargs): agent
                for agent in agents
            }
            
            for future in as_completed(futures):
                results.append(future.result())
                self.metrics['total_agent_invocations'] += 1
        
        return results
    
    def _hierarchical(self, agents: List['Agent'], task_callable: Callable, **kwargs) -> Any:
        """Execute with first agent as manager, rest as workers."""
        if not agents:
            return None
        
        manager = agents[0]
        workers = agents[1:]
        
        worker_results = []
        for worker in workers:
            result = worker.execute_task(task_callable, **kwargs)
            worker_results.append(result)
            self.metrics['total_agent_invocations'] += 1
        
        manager.add_context(f"Worker results: {worker_results}", importance=0.7)
        self.metrics['total_agent_invocations'] += 1
        
        return {'manager': manager.name, 'worker_results': worker_results}
    
    def _pipeline(self, agents: List['Agent'], task_callable: Callable, **kwargs) -> Any:
        """Execute as pipeline - output of one becomes input of next."""
        result = kwargs.get('input')
        
        for agent in agents:
            result = agent.execute_task(task_callable, result, **kwargs)
            self.metrics['total_agent_invocations'] += 1
        
        return result
    
    def _consensus(self, agents: List['Agent'], task_callable: Callable, **kwargs) -> Any:
        """Execute and reach consensus on result."""
        results = self._parallel(agents, task_callable, **kwargs)
        
        if not results:
            return None
        
        result_counts = Counter(str(r) for r in results)
        most_common = result_counts.most_common(1)
        
        if most_common:
            consensus_str = most_common[0][0]
            for r in results:
                if str(r) == consensus_str:
                    return r
        
        return results[0] if results else None
    
    def _round_robin(self, agents: List['Agent'], task_callable: Callable, **kwargs) -> Any:
        """Assign task to agents in round-robin fashion."""
        def get_load(agent):
            metrics = agent.get_performance_metrics()
            return metrics.get('total_tasks', 0)
        
        agent = min(agents, key=get_load)
        result = agent.execute_task(task_callable, **kwargs)
        self.metrics['total_agent_invocations'] += 1
        
        return result
    
    def _swarm(self, agents: List['Agent'], task_callable: Callable, **kwargs) -> List[Any]:
        """Swarm intelligence - agents work together emergently."""
        shared_context = {'swarm_size': len(agents), 'iteration': 0}
        
        results = []
        for agent in agents:
            agent.add_context(f"Swarm context: {shared_context}", importance=0.6)
            result = agent.execute_task(task_callable, **kwargs)
            results.append(result)
            shared_context['iteration'] += 1
            self.metrics['total_agent_invocations'] += 1
        
        return results
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get orchestration metrics."""
        return {
            **self.metrics,
            'registered_supervisors': len(self.supervisors),
            'registered_teams': len(self.teams),
            'execution_history_size': len(self.execution_history)
        }


# Global instance
orchestration_engine = OrchestrationEngine()
