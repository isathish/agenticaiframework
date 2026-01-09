"""
Agent implementation with context engineering and security features.
"""

import uuid
import time
import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from ..context import ContextManager
from ..exceptions import AgentExecutionError  # noqa: F401

logger = logging.getLogger(__name__)


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
        """
        Initialize an agent.
        
        Args:
            name: Agent name
            role: Agent role description
            capabilities: List of agent capabilities
            config: Configuration dictionary
            max_context_tokens: Maximum tokens for context window
        """
        self.id = str(uuid.uuid4())
        self.name = name
        self.role = role
        self.capabilities = capabilities
        self.config = config
        self.status = "initialized"
        self.memory: List[Any] = []
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
        
        # Orchestration attributes (set by supervisor)
        self.supervisor_id: Optional[str] = None

    def start(self) -> None:
        """Start the agent."""
        self.status = "running"
        self.security_context['last_activity'] = datetime.now().isoformat()
        self._log(f"Agent {self.name} started.")

    def pause(self) -> None:
        """Pause the agent."""
        self.status = "paused"
        self._log(f"Agent {self.name} paused.")

    def resume(self) -> None:
        """Resume the agent."""
        self.status = "running"
        self.security_context['last_activity'] = datetime.now().isoformat()
        self._log(f"Agent {self.name} resumed.")

    def stop(self) -> None:
        """Stop the agent."""
        self.status = "stopped"
        self._log(f"Agent {self.name} stopped.")
    
    def add_context(self, content: str, importance: float = 0.5) -> None:
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
            
        except (TypeError, ValueError, KeyError, AttributeError) as e:
            self.performance_metrics['failed_tasks'] += 1
            self._log_error(f"Task execution failed: {str(e)}", e)
            return None
        except Exception as e:  # noqa: BLE001
            self.performance_metrics['failed_tasks'] += 1
            self._log_error(f"Task execution failed with unexpected error: {str(e)}", e)
            return None
            
        finally:
            execution_time = time.time() - start_time
            self.performance_metrics['total_execution_time'] += execution_time
            
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
    
    def _log_error(self, message: str, exception: Optional[Exception] = None) -> None:
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

    def _log(self, message: str) -> None:
        """Log a message."""
        logger.info("[Agent:%s] %s", self.name, message)
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [Agent:{self.name}] {message}")
    
    def log(self, message: str) -> None:
        """Public method to log a message."""
        self._log(message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert agent to dictionary representation."""
        return {
            'id': self.id,
            'name': self.name,
            'role': self.role,
            'capabilities': self.capabilities,
            'status': self.status,
            'version': self.version,
            'metrics': self.get_performance_metrics(),
            'context_stats': self.get_context_stats(),
        }
