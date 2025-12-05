"""
Agent management module with advanced context engineering capabilities.

Provides:
- Agent lifecycle management
- Context window tracking and management
- Token counting and optimization
- Context compression and pruning
- Performance monitoring
"""

import uuid
import time
from typing import Any, Dict, List, Optional, Callable, Tuple
from collections import deque
from datetime import datetime
import json


class ContextManager:
    """Manages agent context window, token tracking, and context optimization."""
    
    def __init__(self, max_tokens: int = 4096, compression_threshold: float = 0.8):
        """
        Initialize context manager.
        
        Args:
            max_tokens: Maximum context window size in tokens
            compression_threshold: Threshold (0-1) at which to trigger compression
        """
        self.max_tokens = max_tokens
        self.compression_threshold = compression_threshold
        self.current_tokens = 0
        self.context_history: deque = deque(maxlen=1000)
        self.important_context: List[Dict[str, Any]] = []
        self.compression_stats = {
            'total_compressions': 0,
            'tokens_saved': 0
        }
        
    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.
        Uses simple heuristic: ~4 characters per token.
        For production, use tiktoken or similar.
        """
        if not text:
            return 0
        # Simple estimation: word count * 1.3
        return max(1, int(len(text.split()) * 1.3))
    
    def add_context(self, content: str, metadata: Dict[str, Any] = None, importance: float = 0.5):
        """
        Add content to context with importance weighting.
        
        Args:
            content: Context content
            metadata: Additional metadata
            importance: Importance score (0-1), higher = more important
        """
        tokens = self.estimate_tokens(content)
        
        context_item = {
            'id': str(uuid.uuid4()),
            'content': content,
            'tokens': tokens,
            'importance': importance,
            'timestamp': datetime.now().isoformat(),
            'metadata': metadata or {}
        }
        
        self.context_history.append(context_item)
        self.current_tokens += tokens
        
        # Mark as important if high importance score
        if importance >= 0.8:
            self.important_context.append(context_item)
        
        # Check if compression needed
        if self.current_tokens > self.max_tokens * self.compression_threshold:
            self._compress_context()
    
    def _compress_context(self):
        """Compress context by removing less important items."""
        if not self.context_history:
            return
        
        # Sort by importance (keep important items)
        sorted_context = sorted(
            self.context_history,
            key=lambda x: x['importance'],
            reverse=True
        )
        
        # Keep top items that fit in budget
        target_tokens = int(self.max_tokens * 0.6)  # Leave 40% buffer
        kept_items = []
        tokens_used = 0
        
        for item in sorted_context:
            if tokens_used + item['tokens'] <= target_tokens:
                kept_items.append(item)
                tokens_used += item['tokens']
            else:
                self.compression_stats['tokens_saved'] += item['tokens']
        
        # Update context
        tokens_removed = self.current_tokens - tokens_used
        self.context_history = deque(kept_items, maxlen=1000)
        self.current_tokens = tokens_used
        self.compression_stats['total_compressions'] += 1
        
        print(f"[ContextManager] Compressed context: removed {tokens_removed} tokens, "
              f"kept {len(kept_items)} items")
    
    def get_context_summary(self) -> str:
        """Get a summary of current context."""
        items = list(self.context_history)
        if not items:
            return "No context available."
        
        summary_parts = []
        for item in items[-10:]:  # Last 10 items
            summary_parts.append(f"- {item['content'][:100]}")
        
        return "\n".join(summary_parts)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get context statistics."""
        return {
            'current_tokens': self.current_tokens,
            'max_tokens': self.max_tokens,
            'utilization': self.current_tokens / self.max_tokens if self.max_tokens > 0 else 0,
            'context_items': len(self.context_history),
            'important_items': len(self.important_context),
            'compression_stats': self.compression_stats
        }
    
    def clear_context(self):
        """Clear all context."""
        self.context_history.clear()
        self.important_context.clear()
        self.current_tokens = 0


class Agent:
    """
    Enhanced Agent with context engineering and security features.
    
    Features:
    - Context window management
    - Token tracking and optimization
    - Performance monitoring
    - Error handling and recovery
    """
    
    def __init__(self, 
                 name: str, 
                 role: str, 
                 capabilities: List[str], 
                 config: Dict[str, Any],
                 max_context_tokens: int = 4096):
        self.id = str(uuid.uuid4())
        self.name = name
        self.role = role
        self.capabilities = capabilities
        self.config = config
        self.status = "initialized"
        self.memory = []
        self.version = "2.0.0"
        
        # Context management
        self.context_manager = ContextManager(max_tokens=max_context_tokens)
        
        # Performance tracking
        self.performance_metrics = {
            'total_tasks': 0,
            'successful_tasks': 0,
            'failed_tasks': 0,
            'total_execution_time': 0.0,
            'average_execution_time': 0.0
        }
        
        # Error tracking
        self.error_log: List[Dict[str, Any]] = []
        
        # Security context
        self.security_context = {
            'created_at': datetime.now().isoformat(),
            'last_activity': datetime.now().isoformat(),
            'access_count': 0
        }

    def start(self):
        """Start the agent."""
        self.status = "running"
        self.security_context['last_activity'] = datetime.now().isoformat()
        self._log(f"Agent {self.name} started.")

    def pause(self):
        """Pause the agent."""
        self.status = "paused"
        self._log(f"Agent {self.name} paused.")

    def resume(self):
        """Resume the agent."""
        self.status = "running"
        self.security_context['last_activity'] = datetime.now().isoformat()
        self._log(f"Agent {self.name} resumed.")

    def stop(self):
        """Stop the agent."""
        self.status = "stopped"
        self._log(f"Agent {self.name} stopped.")
    
    def add_context(self, content: str, importance: float = 0.5):
        """
        Add context to the agent's context manager.
        
        Args:
            content: Context content
            importance: Importance score (0-1)
        """
        self.context_manager.add_context(content, importance=importance)
        self._log(f"Added context with importance {importance}")
    
    def get_context_stats(self) -> Dict[str, Any]:
        """Get context statistics."""
        return self.context_manager.get_stats()

    def execute_task(self, task_callable: Callable, *args, **kwargs) -> Any:
        """
        Execute a task with error handling and performance tracking.
        
        Args:
            task_callable: Callable task to execute
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Task result or None on error
        """
        start_time = time.time()
        self.performance_metrics['total_tasks'] += 1
        self.security_context['access_count'] += 1
        self.security_context['last_activity'] = datetime.now().isoformat()
        
        self._log(f"Executing task with args: {args}, kwargs: {kwargs}")
        
        try:
            result = task_callable(*args, **kwargs)
            self.performance_metrics['successful_tasks'] += 1
            
            # Add task to context
            self.context_manager.add_context(
                f"Task executed: {task_callable.__name__}",
                metadata={'args': str(args)[:100], 'kwargs': str(kwargs)[:100]},
                importance=0.5
            )
            
            return result
            
        except Exception as e:
            self.performance_metrics['failed_tasks'] += 1
            self._log_error(f"Task execution failed: {str(e)}", e)
            return None
            
        finally:
            execution_time = time.time() - start_time
            self.performance_metrics['total_execution_time'] += execution_time
            
            # Update average
            if self.performance_metrics['total_tasks'] > 0:
                self.performance_metrics['average_execution_time'] = (
                    self.performance_metrics['total_execution_time'] / 
                    self.performance_metrics['total_tasks']
                )
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get agent performance metrics."""
        success_rate = 0.0
        if self.performance_metrics['total_tasks'] > 0:
            success_rate = (
                self.performance_metrics['successful_tasks'] / 
                self.performance_metrics['total_tasks']
            )
        
        return {
            **self.performance_metrics,
            'success_rate': success_rate,
            'error_count': len(self.error_log)
        }
    
    def _log_error(self, message: str, exception: Exception = None):
        """Log an error with details."""
        error_entry = {
            'timestamp': datetime.now().isoformat(),
            'message': message,
            'exception_type': type(exception).__name__ if exception else None,
            'exception_details': str(exception) if exception else None
        }
        self.error_log.append(error_entry)
        self._log(f"ERROR: {message}")
    
    def get_error_log(self) -> List[Dict[str, Any]]:
        """Get agent error log."""
        return self.error_log

    def _log(self, message: str):
        """Log a message."""
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [Agent:{self.name}] {message}")


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
        self.agents: Dict[str, Agent] = {}
        self.manager_metrics = {
            'total_agents_registered': 0,
            'total_agents_removed': 0,
            'total_broadcasts': 0
        }

    def register_agent(self, agent: Agent):
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

    def remove_agent(self, agent_id: str):
        """Remove an agent by ID."""
        if agent_id in self.agents:
            agent = self.agents[agent_id]
            agent.stop()
            del self.agents[agent_id]
            self.manager_metrics['total_agents_removed'] += 1
            print(f"Removed agent with ID {agent_id}")

    def broadcast(self, message: str, importance: float = 0.5):
        """
        Broadcast a message to all agents.
        
        Args:
            message: Message to broadcast
            importance: Importance score for context management
        """
        self.manager_metrics['total_broadcasts'] += 1
        for agent in self.agents.values():
            agent._log(f"Broadcast message: {message}")
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
    
    def stop_all_agents(self):
        """Stop all agents."""
        for agent in self.agents.values():
            agent.stop()
        print(f"Stopped all {len(self.agents)} agents")
