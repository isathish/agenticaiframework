"""
Agent implementation with context engineering and security features.
"""

import uuid
import time
import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from ..context import ContextManager, ContextType
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

    def bind_tools(self, tool_names: List[str], permissions: Optional[set] = None) -> None:
        """Bind tools to this agent using the tool manager."""
        from ..tools import agent_tool_manager
        agent_tool_manager.bind_tools(self, tool_names, permissions=permissions)

    def execute_tool(self, tool_name: str, **kwargs) -> Any:
        """Execute a bound tool on behalf of this agent."""
        from ..tools import agent_tool_manager
        return agent_tool_manager.execute_tool(self, tool_name, **kwargs)

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Get MCP-compatible schemas for this agent's tools."""
        from ..tools import agent_tool_manager
        return agent_tool_manager.get_all_schemas(self)

    def run(
        self,
        prompt: str,
        *,
        llm: Optional[Any] = None,
        llm_kwargs: Optional[Dict[str, Any]] = None,
        knowledge: Optional[Any] = None,
        knowledge_query: Optional[str] = None,
        guardrails: Optional[List[Any]] = None,
        guardrail_manager: Optional[Any] = None,
        guardrail_pipeline: Optional[Any] = None,
        tools: Optional[List[str]] = None,
        tool_inputs: Optional[Dict[str, Dict[str, Any]]] = None,
        auto_bind_tools: bool = True,
        monitor: Optional[Any] = None,
        trace: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
        return_full: bool = True,
    ) -> Any:
        """
        Run an agentic execution cycle with LLMs, guardrails, tools, and tracing.

        Returns:
            Dict with execution details when return_full=True, otherwise the response string.
        """
        from ..tracing import tracer as global_tracer
        from ..guardrails import guardrail_manager as global_guardrail_manager

        metadata = metadata or {}
        llm_kwargs = llm_kwargs or {}

        llm_manager = llm or self.config.get('llm') or self.config.get('llm_manager')
        knowledge_retriever = knowledge or self.config.get('knowledge')
        monitor = monitor or self.config.get('monitor') or self.config.get('monitoring')
        guardrail_manager = guardrail_manager or self.config.get('guardrail_manager')
        guardrail_pipeline = guardrail_pipeline or self.config.get('guardrail_pipeline')
        guardrails = guardrails or self.config.get('guardrails') or []
        if guardrail_manager is None and guardrail_pipeline is None and not guardrails:
            guardrail_manager = global_guardrail_manager

        tracer = self.config.get('tracer') or global_tracer
        policy_manager = self.config.get('policy_manager')
        trace_context = tracer.start_trace(f"agent.run:{self.name}") if trace else None
        trace_id = trace_context.trace_id if trace_context else None

        start_time = time.time()
        self.performance_metrics['total_tasks'] += 1

        guardrail_report: Dict[str, Any] = {}
        tool_results: List[Dict[str, Any]] = []
        knowledge_results: List[Dict[str, Any]] = []

        def _trace_step(step_name: str):
            return tracer.trace_step(step_name, attributes={
                'agent_id': self.id,
                'agent_name': self.name,
                'trace_id': trace_id,
            }) if trace else nullcontext()

        from contextlib import contextmanager

        @contextmanager
        def nullcontext():
            yield None

        def _finalize(payload: Any, status: str = "OK", error: Optional[Exception] = None) -> Any:
            if trace_context is not None:
                tracer.end_span(trace_context, status=status, error=error)
            return payload

        try:
            with _trace_step('guardrails.input'):
                if guardrail_pipeline is not None:
                    guardrail_report = guardrail_pipeline.execute(prompt, context=metadata)
                    if not guardrail_report.get('is_valid', True):
                        return _finalize({
                            'status': 'blocked',
                            'reason': 'guardrail_pipeline',
                            'guardrail_report': guardrail_report,
                            'trace_id': trace_id,
                        }, status="ERROR")
                elif guardrail_manager is not None:
                    guardrail_report = guardrail_manager.enforce_guardrails(prompt, fail_fast=True)
                    if not guardrail_report.get('is_valid', True):
                        return _finalize({
                            'status': 'blocked',
                            'reason': 'guardrail_manager',
                            'guardrail_report': guardrail_report,
                            'trace_id': trace_id,
                        }, status="ERROR")
                elif guardrails:
                    violations = []
                    for guardrail in guardrails:
                        if hasattr(guardrail, 'validate') and not guardrail.validate(prompt):
                            violations.append(getattr(guardrail, 'name', str(guardrail)))
                    guardrail_report = {
                        'is_valid': len(violations) == 0,
                        'violations': violations,
                    }
                    if violations:
                        return _finalize({
                            'status': 'blocked',
                            'reason': 'guardrails',
                            'guardrail_report': guardrail_report,
                            'trace_id': trace_id,
                        }, status="ERROR")

            with _trace_step('knowledge.retrieve'):
                if knowledge_retriever is not None:
                    query = knowledge_query or prompt
                    knowledge_results = knowledge_retriever.retrieve(query)
                    if knowledge_results:
                        knowledge_text = "\n".join(
                            f"- {str(item)[:300]}" for item in knowledge_results[:5]
                        )
                        self.context_manager.add_context(
                            f"Knowledge retrieved:\n{knowledge_text}",
                            metadata={'query': query},
                            importance=0.7,
                            context_type=ContextType.KNOWLEDGE,
                        )

            with _trace_step('tools.execute'):
                if tools:
                    from ..tools import agent_tool_manager
                    if auto_bind_tools:
                        agent_tool_manager.bind_tools(self, tools)
                    for tool_name in tools:
                        if policy_manager is not None:
                            policy_result = policy_manager.evaluate_policies(
                                self.id,
                                action=tool_name,
                                resource=tool_name,
                                context={'agent_id': self.id, 'tool_name': tool_name},
                            )
                            if not policy_result.get('allowed', True):
                                tool_results.append({
                                    'tool_name': tool_name,
                                    'status': 'blocked',
                                    'policy': policy_result,
                                })
                                continue
                        params = (tool_inputs or {}).get(tool_name, {})
                        tool_result = agent_tool_manager.execute_tool(self, tool_name, **params)
                        tool_results.append(tool_result.to_dict())
                        if tool_result.is_success:
                            self.context_manager.add_context(
                                f"Tool {tool_name} result: {str(tool_result.data)[:500]}",
                                metadata={'tool': tool_name},
                                importance=0.6,
                                context_type=ContextType.TOOL_RESULT,
                            )

            with _trace_step('llm.generate'):
                if llm_manager is None:
                    return _finalize({
                        'status': 'error',
                        'error': 'No LLM manager provided',
                        'trace_id': trace_id,
                    }, status="ERROR")

                context_summary = self.context_manager.get_context_summary()
                prompt_parts = []
                if context_summary and context_summary != "No context available.":
                    prompt_parts.append(f"Context:\n{context_summary}")
                if knowledge_results:
                    knowledge_preview = "\n".join(
                        f"- {str(item)[:300]}" for item in knowledge_results[:5]
                    )
                    prompt_parts.append(f"Knowledge:\n{knowledge_preview}")
                if tool_results:
                    tool_preview = "\n".join(
                        f"- {r.get('tool_name')}: {str(r.get('data'))[:300]}"
                        for r in tool_results
                    )
                    prompt_parts.append(f"Tool Results:\n{tool_preview}")

                prompt_parts.append(f"User Prompt:\n{prompt}")
                final_prompt = "\n\n".join(prompt_parts)

                response = llm_manager.generate(final_prompt, **llm_kwargs)
                if response is None:
                    return _finalize({
                        'status': 'error',
                        'error': 'LLM generation failed',
                        'trace_id': trace_id,
                    }, status="ERROR")

            with _trace_step('guardrails.output'):
                if guardrail_pipeline is not None:
                    output_report = guardrail_pipeline.execute(response, context=metadata)
                    if not output_report.get('is_valid', True):
                        return _finalize({
                            'status': 'blocked',
                            'reason': 'guardrail_pipeline_output',
                            'guardrail_report': output_report,
                            'trace_id': trace_id,
                        }, status="ERROR")
                elif guardrail_manager is not None:
                    output_report = guardrail_manager.enforce_guardrails(response, fail_fast=True)
                    if not output_report.get('is_valid', True):
                        return _finalize({
                            'status': 'blocked',
                            'reason': 'guardrail_manager_output',
                            'guardrail_report': output_report,
                            'trace_id': trace_id,
                        }, status="ERROR")

            self.context_manager.add_context(
                prompt,
                metadata={'source': 'user'},
                importance=0.5,
                context_type=ContextType.USER,
            )
            self.context_manager.add_context(
                response,
                metadata={'source': 'assistant'},
                importance=0.6,
                context_type=ContextType.ASSISTANT,
            )

            if monitor is not None:
                monitor.record_metric('agent.last_execution_seconds', time.time() - start_time)
                monitor.log_event('agent.execution', {
                    'agent_id': self.id,
                    'agent_name': self.name,
                    'trace_id': trace_id,
                    'tools_used': tools or [],
                })

            self.performance_metrics['successful_tasks'] += 1
            return _finalize({
                'status': 'success',
                'response': response,
                'guardrail_report': guardrail_report,
                'tool_results': tool_results,
                'knowledge_results': knowledge_results,
                'trace_id': trace_id,
                'latency_seconds': time.time() - start_time,
            } if return_full else response)

        except Exception as e:  # noqa: BLE001
            self.performance_metrics['failed_tasks'] += 1
            self._log_error(f"Agent run failed: {e}", e)
            return _finalize({
                'status': 'error',
                'error': str(e),
                'trace_id': trace_id,
            }, status="ERROR", error=e)
    
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
