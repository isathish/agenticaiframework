"""
Agent Manager for managing multiple agents.
"""

import logging
from typing import Any, Dict, List, Optional

from .agent import Agent

logger = logging.getLogger(__name__)


class AgentManager:
    """
    Manages multiple agents with enhanced monitoring and coordination.
    
    Features:
    - Agent lifecycle management
    - Performance monitoring across agents
    - Context coordination
    - Health checks
    """
    
    def __init__(self):
        """Initialize the agent manager."""
        self.agents: Dict[str, Agent] = {}
        self.manager_metrics = {
            'total_agents_registered': 0,
            'total_agents_removed': 0,
            'total_broadcasts': 0
        }

    def register_agent(self, agent: Agent) -> None:
        """Register an agent with the manager."""
        self.agents[agent.id] = agent
        self.manager_metrics['total_agents_registered'] += 1
        print(f"Registered agent {agent.name} with ID {agent.id}")

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Get an agent by ID."""
        return self.agents.get(agent_id)

    def list_agents(self) -> List[Agent]:
        """List all registered agents."""
        return list(self.agents.values())

    def remove_agent(self, agent_id: str) -> None:
        """Remove an agent by ID."""
        if agent_id in self.agents:
            agent = self.agents[agent_id]
            agent.stop()
            del self.agents[agent_id]
            self.manager_metrics['total_agents_removed'] += 1
            print(f"Removed agent with ID {agent_id}")

    def broadcast(self, message: str, importance: float = 0.5) -> None:
        """
        Broadcast a message to all agents.
        
        Args:
            message: Message to broadcast
            importance: Importance score for context management
        """
        self.manager_metrics['total_broadcasts'] += 1
        for agent in self.agents.values():
            agent.log(f"Broadcast message: {message}")
            agent.add_context(f"Broadcast: {message}", importance=importance)
    
    def get_agent_by_name(self, name: str) -> Optional[Agent]:
        """Get an agent by name."""
        for agent in self.agents.values():
            if agent.name == name:
                return agent
        return None
    
    def get_agents_by_capability(self, capability: str) -> List[Agent]:
        """Get all agents with a specific capability."""
        return [
            agent for agent in self.agents.values()
            if capability in agent.capabilities
        ]
    
    def get_active_agents(self) -> List[Agent]:
        """Get all running agents."""
        return [
            agent for agent in self.agents.values()
            if agent.status == "running"
        ]
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on all agents.
        
        Returns:
            Dict with health status for each agent
        """
        health_status = {}
        
        for agent_id, agent in self.agents.items():
            metrics = agent.get_performance_metrics()
            context_stats = agent.get_context_stats()
            
            health_status[agent_id] = {
                'name': agent.name,
                'status': agent.status,
                'success_rate': metrics['success_rate'],
                'total_tasks': metrics['total_tasks'],
                'error_count': metrics['error_count'],
                'context_utilization': context_stats['utilization']
            }
        
        return health_status
    
    def get_aggregate_metrics(self) -> Dict[str, Any]:
        """Get aggregated metrics across all agents."""
        total_tasks = 0
        total_successful = 0
        total_failed = 0
        total_errors = 0
        
        for agent in self.agents.values():
            metrics = agent.get_performance_metrics()
            total_tasks += metrics['total_tasks']
            total_successful += metrics['successful_tasks']
            total_failed += metrics['failed_tasks']
            total_errors += metrics['error_count']
        
        return {
            'total_agents': len(self.agents),
            'active_agents': len(self.get_active_agents()),
            'total_tasks': total_tasks,
            'total_successful': total_successful,
            'total_failed': total_failed,
            'total_errors': total_errors,
            'overall_success_rate': total_successful / total_tasks if total_tasks > 0 else 0.0,
            **self.manager_metrics
        }
    
    def stop_all_agents(self) -> None:
        """Stop all agents."""
        for agent in self.agents.values():
            agent.stop()
        print(f"Stopped all {len(self.agents)} agents")
