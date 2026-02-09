"""
Agent implementation with context engineering and security features.
"""

import os
import uuid
import time
import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Union

from agenticaiframework.context.manager import ContextManager, ContextType
from agenticaiframework.exceptions import AgentExecutionError  # noqa: F401

logger = logging.getLogger(__name__)


class Agent:
    """
    Enhanced Agent with context engineering and security features.
    
    Features:
    - Context window management
    - Token tracking and optimization
    - Performance monitoring
    - Error handling and recovery
    - Quick factory methods for zero-config setup
    
    Quick Start:
        >>> # One-line agent with auto-configured LLM
        >>> agent = Agent.quick("Assistant")
        >>> output = agent.invoke("Hello!")
        
        >>> # From configuration dictionary
        >>> agent = Agent.from_config({"name": "Bot", "llm": "gpt-4o"})
    """
    
    # Default role templates for quick setup
    ROLE_TEMPLATES = {
        "assistant": "A helpful AI assistant that provides accurate, concise responses.",
        "analyst": "A data analyst that examines information and provides insights.",
        "coder": "A programming assistant that writes and reviews code.",
        "writer": "A creative writer that produces engaging content.",
        "researcher": "A research assistant that finds and synthesizes information.",
    }
    
    # Default capabilities by role
    ROLE_CAPABILITIES = {
        "assistant": ["chat", "reasoning", "tool-use"],
        "analyst": ["data-analysis", "visualization", "tool-use"],
        "coder": ["code-generation", "code-review", "debugging", "tool-use"],
        "writer": ["writing", "editing", "summarization"],
        "researcher": ["search", "summarization", "reasoning"],
    }

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
        self.context_manager = ContextManager(max_tokens=max_context_tokens) # TODO can be customized further.
        
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

    @classmethod
    def quick(
        cls,
        name: str,
        *,
        role: str = "assistant",
        llm: Optional[str] = None,
        provider: Optional[str] = None,
        tools: Optional[List[str]] = None,
        auto_tools: bool = False,
        guardrails: bool = True,
        tracing: bool = True,
        **kwargs,
    ) -> 'Agent':
        """
        Create an agent with minimal configuration and sensible defaults.
        
        Automatically:
        - Configures LLM from environment variables
        - Sets up default guardrails (if enabled)
        - Enables tracing (if enabled)
        - Auto-binds tools based on role (if auto_tools=True)
        
        Args:
            name: Agent name
            role: Role template ('assistant', 'analyst', 'coder', 'writer', 'researcher')
                  or custom role description
            llm: LLM model name (e.g., 'gpt-4o', 'claude-sonnet-4-20250514')
            provider: Preferred provider ('openai', 'anthropic', 'google')
            tools: List of tool names to bind
            auto_tools: Auto-discover and bind tools by role
            guardrails: Enable default guardrails
            tracing: Enable execution tracing
            **kwargs: Additional config options
            
        Returns:
            Configured Agent instance
            
        Example:
            >>> # Minimal setup - uses env vars for LLM
            >>> agent = Agent.quick("Assistant")
            >>> output = agent.invoke("Hello!")
            
            >>> # With specific provider
            >>> agent = Agent.quick("Coder", role="coder", provider="anthropic")
            
            >>> # With tools
            >>> agent = Agent.quick("DataBot", tools=["WebSearchTool", "CalculatorTool"])
        """
        from ..llms import LLMManager
        from ..guardrails import GuardrailPipeline
        from ..tracing import tracer
        from ..tools import tool_registry, agent_tool_manager
        
        # Determine role description and capabilities
        role_lower = role.lower()
        if role_lower in cls.ROLE_TEMPLATES:
            role_description = cls.ROLE_TEMPLATES[role_lower]
            capabilities = cls.ROLE_CAPABILITIES.get(role_lower, ["general"])
        else:
            role_description = role
            capabilities = kwargs.pop("capabilities", ["general"])
        
        # Build config
        config: Dict[str, Any] = {}
        
        # Auto-configure LLM
        llm_manager = LLMManager.from_environment(
            auto_select=True,
            preferred_provider=provider,
        )
        
        # Override with specific model if provided
        if llm and llm_manager.active_model:
            # Try to find the model in the active provider
            active_provider = llm_manager.get_provider(llm_manager.active_model)
            if active_provider:
                active_provider.config.default_model = llm
        
        config['llm'] = llm_manager
        
        # Setup guardrails
        if guardrails:
            pipeline = GuardrailPipeline.minimal()
            config['guardrail_pipeline'] = pipeline
        
        # Setup tracing
        if tracing:
            config['tracer'] = tracer
        
        # Merge additional config
        config.update(kwargs)
        
        # Create agent
        agent = cls(
            name=name,
            role=role_description,
            capabilities=capabilities,
            config=config,
        )
        
        # Bind tools
        if tools:
            agent_tool_manager.bind_tools(agent, tools)
        
        # Auto-bind tools by role
        if auto_tools:
            role_tools = cls._get_tools_for_role(role_lower)
            if role_tools:
                agent_tool_manager.bind_tools(agent, role_tools)
        
        agent.start()
        return agent

    @classmethod
    def from_config(
        cls,
        config: Dict[str, Any],
    ) -> 'Agent':
        """
        Create an agent from a configuration dictionary.
        
        Supports configuration from files (YAML, JSON) or programmatic config.
        
        Args:
            config: Configuration dictionary with keys:
                - name (required): Agent name
                - role: Role description or template
                - capabilities: List of capabilities
                - llm: LLM configuration (model name, provider, or dict)
                - tools: List of tool names
                - guardrails: Guardrail configuration
                - max_context_tokens: Context window size
                - **other: Passed to agent config
                
        Returns:
            Configured Agent instance
            
        Example:
            >>> config = {
            ...     "name": "DataAnalyst",
            ...     "role": "analyst",
            ...     "llm": {"provider": "openai", "model": "gpt-4o"},
            ...     "tools": ["SQLTool", "ChartTool"],
            ...     "guardrails": {"preset": "enterprise"},
            ... }
            >>> agent = Agent.from_config(config)
            
            >>> # Or from YAML file
            >>> import yaml
            >>> with open("agent.yaml") as f:
            ...     config = yaml.safe_load(f)
            >>> agent = Agent.from_config(config)
        """
        from ..llms import LLMManager
        from ..llms.providers import get_provider
        from ..guardrails import GuardrailPipeline
        from ..tracing import tracer
        from ..tools import agent_tool_manager
        
        # Extract required fields
        name = config.get("name", "Agent")
        role = config.get("role", "assistant")
        capabilities = config.get("capabilities", [])
        max_tokens = config.get("max_context_tokens", 4096)
        
        # Handle role templates
        role_lower = role.lower()
        if role_lower in cls.ROLE_TEMPLATES and not capabilities:
            role_description = cls.ROLE_TEMPLATES[role_lower]
            capabilities = cls.ROLE_CAPABILITIES.get(role_lower, ["general"])
        else:
            role_description = role
        
        # Build agent config
        agent_config: Dict[str, Any] = {}
        
        # Configure LLM
        llm_config = config.get("llm")
        if llm_config:
            if isinstance(llm_config, str):
                # Simple model name - auto-detect provider
                llm_manager = LLMManager.from_environment()
                if llm_manager.active_model:
                    provider = llm_manager.get_provider(llm_manager.active_model)
                    if provider:
                        provider.config.default_model = llm_config
                agent_config['llm'] = llm_manager
            elif isinstance(llm_config, dict):
                # Detailed config
                provider_name = llm_config.get("provider")
                model = llm_config.get("model")
                api_key = llm_config.get("api_key")
                
                if provider_name:
                    provider = get_provider(provider_name, model=model, api_key=api_key)
                    llm_manager = LLMManager()
                    llm_manager.register_provider(provider)
                    llm_manager.set_active_model(provider_name)
                    agent_config['llm'] = llm_manager
                else:
                    # Auto-detect
                    agent_config['llm'] = LLMManager.from_environment()
        else:
            # Default: auto-detect from environment
            agent_config['llm'] = LLMManager.from_environment()
        
        # Configure guardrails
        guardrails_config = config.get("guardrails", True)
        if guardrails_config:
            if isinstance(guardrails_config, bool):
                agent_config['guardrail_pipeline'] = GuardrailPipeline.minimal()
            elif isinstance(guardrails_config, dict):
                preset = guardrails_config.get("preset", "minimal")
                if preset == "enterprise":
                    agent_config['guardrail_pipeline'] = GuardrailPipeline.enterprise_defaults()
                elif preset == "safety":
                    agent_config['guardrail_pipeline'] = GuardrailPipeline.safety_only()
                else:
                    agent_config['guardrail_pipeline'] = GuardrailPipeline.minimal()
        
        # Enable tracing by default
        if config.get("tracing", True):
            agent_config['tracer'] = tracer
        
        # Merge extra config
        for key in ["monitor", "knowledge", "policy_manager"]:
            if key in config:
                agent_config[key] = config[key]
        
        # Create agent
        agent = cls(
            name=name,
            role=role_description,
            capabilities=capabilities,
            config=agent_config,
            max_context_tokens=max_tokens,
        )
        
        # Bind tools
        tools = config.get("tools", [])
        if tools:
            agent_tool_manager.bind_tools(agent, tools)
        
        # Auto-start if specified
        if config.get("auto_start", True):
            agent.start()
        
        return agent

    @classmethod
    def _get_tools_for_role(cls, role: str) -> List[str]:
        """Get default tools for a role."""
        role_tools = {
            "analyst": ["SQLQueryTool", "DataVisualizationTool"],
            "coder": ["CodeInterpreterTool", "GitHubTool", "FileSystemTool"],
            "researcher": ["WebSearchTool", "PDFReaderTool"],
            "assistant": [],
            "writer": [],
        }
        return role_tools.get(role, [])

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
        # TODO how are tokens still being used without LLM calls?
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

    def invoke(
        self,
        prompt: str,
        *,
        system_prompt: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        tools: Optional[List[str]] = None,
        tool_inputs: Optional[Dict[str, Dict[str, Any]]] = None,
        knowledge_query: Optional[str] = None,
        max_iterations: int = 10,
        temperature: float = 0.7,
        stop_on_tool_error: bool = False,
    ) -> 'AgentOutput':
        """
         Agent invoke API for structured agentic execution.
        
        Features:
        - Structured AgentInput/AgentOutput
        - ReAct-style thought/action/observation loop
        - Multi-step tool execution
        - Step-by-step tracing
        
        Args:
            prompt: The user prompt/question
            system_prompt: Custom system prompt (optional)
            context: Additional context dictionary
            tools: List of tool names to use
            tool_inputs: Pre-set tool parameters
            knowledge_query: Custom query for knowledge retrieval
            max_iterations: Maximum ReAct iterations
            temperature: LLM temperature
            stop_on_tool_error: Stop on first tool error
        
        Returns:
            AgentOutput with response, steps, thoughts, and metadata
        
        Example:
            >>> agent = Agent("assistant", "helper", [], {})
            >>> output = agent.invoke("What is 2+2?", tools=["calculator"])
            >>> print(output.response)
            >>> for step in output.steps:
            ...     print(f"{step.step_type}: {step.name}")
        """
        from .types import AgentInput, AgentOutput
        from .runner import AgentRunner
        
        agent_input = AgentInput(
            prompt=prompt,
            system_prompt=system_prompt,
            context=context,
            tools=tools,
            tool_inputs=tool_inputs,
            knowledge_query=knowledge_query,
            max_iterations=max_iterations,
            temperature=temperature,
            stop_on_tool_error=stop_on_tool_error,
        )
        
        runner = AgentRunner(
            agent=self,
            llm_manager=self.config.get('llm') or self.config.get('llm_manager'),
            knowledge=self.config.get('knowledge'),
            guardrail_manager=self.config.get('guardrail_manager'),
            guardrail_pipeline=self.config.get('guardrail_pipeline'),
            policy_manager=self.config.get('policy_manager'),
            monitor=self.config.get('monitor'),
            tracer=self.config.get('tracer'),
        )
        
        return runner.run(agent_input)

    def stream(
        self,
        prompt: str,
        *,
        system_prompt: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        tools: Optional[List[str]] = None,
        on_step: Optional[Callable[['AgentStep'], None]] = None,
        on_thought: Optional[Callable[['AgentThought'], None]] = None,
        **kwargs,
    ): #TODO Not really streaming yet
        """
        Streaming invoke - yields steps as they happen.
        
        Args:
            prompt: User prompt
            system_prompt: Custom system prompt
            context: Additional context
            tools: Tool names to use
            on_step: Callback for each step
            on_thought: Callback for each thought
            **kwargs: Additional arguments for invoke()
        
        Yields:
            AgentStep objects as they are generated
        
        Example:
            >>> for step in agent.stream("Analyze data"):
            ...     print(f"{step.step_type}: {step.name}")
        """
        # For now, run invoke and yield steps
        # Future: implement true streaming with async generators
        output = self.invoke(
            prompt,
            system_prompt=system_prompt,
            context=context,
            tools=tools,
            **kwargs,
        )
        
        for step in output.steps:
            if on_step:
                on_step(step)
            yield step
        
        for thought in output.thoughts:
            if on_thought:
                on_thought(thought)

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
    
    # =========================================================================
    # INTEGRATION METHODS: Workflow, Orchestration, Agents, Knowledge, Policies
    # =========================================================================
    
    def call_workflow(
        self,
        workflow: Any,
        input_data: Any = None,
        **kwargs,
    ) -> Any:
        """
        Execute a workflow from this agent.
        
        Args:
            workflow: Workflow instance (Process, SequentialWorkflow, etc.) or workflow config dict
            input_data: Initial input for the workflow
            **kwargs: Additional workflow parameters
            
        Returns:
            Workflow execution result
            
        Example:
            >>> from agenticaiframework import Process
            >>> workflow = Process(name="analysis", strategy="sequential")
            >>> workflow.add_step(lambda x: f"Step 1: {x}")
            >>> workflow.add_step(lambda x: f"Step 2: {x}")
            >>> result = agent.call_workflow(workflow)
        """
        from ..processes import Process
        from ..workflows import SequentialWorkflow, ParallelWorkflow
        
        self._log(f"Executing workflow: {getattr(workflow, 'name', str(type(workflow)))}")
        
        if isinstance(workflow, Process):
            # Execute Process directly
            return workflow.execute()
        
        elif isinstance(workflow, (SequentialWorkflow, ParallelWorkflow)):
            # Execute workflow with this agent's manager if available
            if isinstance(workflow, SequentialWorkflow):
                agent_chain = kwargs.get('agent_chain', [self.name])
                task_callable = kwargs.get('task_callable', lambda x: x)
                return workflow.execute_sequential(input_data, agent_chain, task_callable)
            else:
                agent_names = kwargs.get('agent_names', [self.name])
                task_callable = kwargs.get('task_callable', lambda x: x)
                return workflow.execute_parallel_sync(input_data, agent_names, task_callable)
        
        elif isinstance(workflow, dict):
            # Workflow defined as config dict
            workflow_name = workflow.get('name', 'unnamed_workflow')
            steps = workflow.get('steps', [])
            strategy = workflow.get('strategy', 'sequential')
            
            process = Process(name=workflow_name, strategy=strategy)
            for step in steps:
                if callable(step):
                    process.add_step(step)
                elif isinstance(step, dict):
                    step_fn = step.get('fn') or step.get('callable') or step.get('action')
                    if callable(step_fn):
                        process.add_step(step_fn)
            
            return process.execute()
        
        else:
            # Try to call execute() if available
            if hasattr(workflow, 'execute'):
                return workflow.execute()
            raise ValueError(f"Unknown workflow type: {type(workflow)}")
    
    def call_orchestration(
        self,
        agents: List['Agent'],
        task: Callable,
        pattern: str = "sequential",
        aggregator: Optional[Callable] = None,
        **kwargs,
    ) -> Any:
        """
        Orchestrate multiple agents to execute a task.
        
        Args:
            agents: List of agents to orchestrate
            task: Task callable to execute
            pattern: Orchestration pattern - 'sequential', 'parallel', 'hierarchical', 
                     'pipeline', 'consensus'
            aggregator: Function to aggregate results
            **kwargs: Additional parameters
            
        Returns:
            Orchestration result
            
        Example:
            >>> analyst = Agent.quick("Analyst", role="analyst")
            >>> writer = Agent.quick("Writer", role="writer")
            >>> result = agent.call_orchestration(
            ...     agents=[analyst, writer],
            ...     task=lambda: "Process this data",
            ...     pattern="pipeline"
            ... )
        """
        from ..orchestration import OrchestrationEngine, OrchestrationPattern
        
        # Map pattern string to enum
        pattern_map = {
            'sequential': OrchestrationPattern.SEQUENTIAL,
            'parallel': OrchestrationPattern.PARALLEL,
            'hierarchical': OrchestrationPattern.HIERARCHICAL,
            'pipeline': OrchestrationPattern.PIPELINE,
            'consensus': OrchestrationPattern.CONSENSUS,
        }
        
        pattern_enum = pattern_map.get(pattern.lower(), OrchestrationPattern.SEQUENTIAL)
        
        engine = OrchestrationEngine(default_pattern=pattern_enum)
        
        self._log(f"Orchestrating {len(agents)} agents with pattern: {pattern}")
        
        return engine.orchestrate(
            agents=agents,
            task_callable=task,
            pattern=pattern_enum,
            aggregator=aggregator,
            **kwargs,
        )
    
    def call_agent(
        self,
        agent: 'Agent',
        prompt: str,
        wait: bool = True,
        **kwargs,
    ) -> Any:
        """
        Delegate a task to another agent.
        
        Args:
            agent: The agent to delegate to
            prompt: The prompt/task to send
            wait: Whether to wait for completion
            **kwargs: Additional parameters for the agent
            
        Returns:
            The agent's response
            
        Example:
            >>> researcher = Agent.quick("Researcher", role="researcher")
            >>> result = agent.call_agent(
            ...     researcher,
            ...     "Research AI trends for 2024"
            ... )
        """
        self._log(f"Delegating task to agent: {agent.name}")
        
        # Record handoff
        handoff_record = {
            'from_agent': self.name,
            'to_agent': agent.name,
            'prompt': prompt[:200],
            'timestamp': datetime.now().isoformat(),
        }
        
        # Add context about delegation
        self.context_manager.add_context(
            f"Delegated task to {agent.name}: {prompt[:100]}...",
            importance=0.6,
        )
        
        # Execute on target agent
        result = agent.run(prompt, **kwargs)
        
        # Add result to context
        if isinstance(result, dict) and 'response' in result:
            self.context_manager.add_context(
                f"Response from {agent.name}: {str(result.get('response', ''))[:200]}...",
                importance=0.7,
            )
        
        return result
    
    def handoff_to(
        self,
        agent: 'Agent',
        context: Optional[Dict[str, Any]] = None,
        reason: str = "",
    ) -> 'Agent':
        """
        Handoff execution to another agent, transferring context.
        
        Args:
            agent: Agent to handoff to
            context: Additional context to transfer
            reason: Reason for handoff
            
        Returns:
            The target agent (for chaining)
            
        Example:
            >>> specialist = Agent.quick("Specialist", role="coder")
            >>> agent.handoff_to(specialist, reason="Need code expertise")
        """
        self._log(f"Handing off to agent: {agent.name}. Reason: {reason}")
        
        # Transfer context
        context_summary = self.context_manager.get_context_summary()
        agent.add_context(
            f"Handoff from {self.name}:\n{context_summary}",
            importance=0.8,
        )
        
        if context:
            for key, value in context.items():
                agent.add_context(f"{key}: {value}", importance=0.6)
        
        if reason:
            agent.add_context(f"Handoff reason: {reason}", importance=0.7)
        
        # Record handoff (for tracking)
        from ..orchestration import AgentHandoff
        handoff = AgentHandoff(
            handoff_id=str(uuid.uuid4()),
            from_agent_id=self.id,
            to_agent_id=agent.id,
            reason=reason,
            context=context or {},
        )
        
        return agent
    
    def query_knowledge(
        self,
        query: str,
        sources: Optional[List[str]] = None,
        max_results: int = 5,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """
        Query knowledge bases.
        
        Args:
            query: The search query
            sources: Specific sources to query (None = all)
            max_results: Maximum results to return
            **kwargs: Additional parameters
            
        Returns:
            List of knowledge results
            
        Example:
            >>> results = agent.query_knowledge("machine learning best practices")
            >>> for item in results:
            ...     print(item['content'])
        """
        from ..knowledge import KnowledgeRetriever
        
        self._log(f"Querying knowledge: {query[:50]}...")
        
        # Get or create knowledge retriever
        knowledge = self.config.get('knowledge')
        if knowledge is None:
            knowledge = KnowledgeRetriever()
            self.config['knowledge'] = knowledge
        
        results = knowledge.retrieve(query)
        
        # Filter by sources if specified
        if sources:
            results = [r for r in results if r.get('source') in sources]
        
        # Limit results
        results = results[:max_results]
        
        # Add to context
        if results:
            knowledge_text = "\n".join(
                f"- {str(item.get('content', item))[:200]}" 
                for item in results
            )
            self.context_manager.add_context(
                f"Knowledge for '{query}':\n{knowledge_text}",
                importance=0.7,
                context_type=ContextType.KNOWLEDGE,
            )
        
        return results
    
    def add_knowledge(
        self,
        key: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Add knowledge to the agent's knowledge base.
        
        Args:
            key: Knowledge key/identifier
            content: The knowledge content
            metadata: Optional metadata
            
        Example:
            >>> agent.add_knowledge("company_policy", "All code must be reviewed...")
        """
        from ..knowledge import KnowledgeRetriever
        
        knowledge = self.config.get('knowledge')
        if knowledge is None:
            knowledge = KnowledgeRetriever()
            self.config['knowledge'] = knowledge
        
        knowledge.add_knowledge(key, content)
        self._log(f"Added knowledge: {key}")
    
    def check_policy(
        self,
        action: str,
        resource: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Check if an action is allowed by policies.
        
        Args:
            action: The action to check (e.g., 'execute_tool', 'access_data')
            resource: The resource being accessed
            context: Additional context for evaluation
            
        Returns:
            Policy evaluation result with 'allowed' boolean
            
        Example:
            >>> result = agent.check_policy("execute", "code_interpreter")
            >>> if result['allowed']:
            ...     agent.execute_tool("code_interpreter", code="print('hi')")
        """
        from ..compliance import PolicyEngine
        
        self._log(f"Checking policy: {action} on {resource}")
        
        policy_manager = self.config.get('policy_manager')
        if policy_manager is None:
            policy_manager = PolicyEngine()
            self.config['policy_manager'] = policy_manager
        
        result = policy_manager.evaluate(
            resource=resource,
            action=action,
            context=context or {},
            actor=self.id,
        )
        
        return result
    
    def apply_guardrails(
        self,
        content: str,
        direction: str = "input",
        fail_fast: bool = True,
    ) -> Dict[str, Any]:
        """
        Apply guardrails to content.
        
        Args:
            content: The content to validate
            direction: 'input' or 'output' guardrails
            fail_fast: Stop on first failure
            
        Returns:
            Guardrail validation result
            
        Example:
            >>> result = agent.apply_guardrails("user message here", direction="input")
            >>> if result['is_valid']:
            ...     # Process the message
        """
        from ..guardrails import guardrail_manager, GuardrailPipeline
        
        self._log(f"Applying {direction} guardrails")
        
        # Get guardrail pipeline from config or use default
        pipeline = self.config.get('guardrail_pipeline')
        manager = self.config.get('guardrail_manager')
        
        if pipeline is not None:
            result = pipeline.execute(content, context={'direction': direction})
        elif manager is not None:
            result = manager.enforce_guardrails(content, fail_fast=fail_fast)
        else:
            # Use global guardrail manager
            result = guardrail_manager.enforce_guardrails(content, fail_fast=fail_fast)
        
        return result
    
    def delegate_to_team(
        self,
        team: Any,  # AgentTeam
        task: str,
        coordinator_role: Optional[str] = None,
        **kwargs,
    ) -> Any:
        """
        Delegate a task to an agent team.
        
        Args:
            team: The AgentTeam to delegate to
            task: The task description
            coordinator_role: Which role should coordinate
            **kwargs: Additional parameters
            
        Returns:
            Team execution result
            
        Example:
            >>> from agenticaiframework.orchestration import AgentTeam
            >>> team = AgentTeam(name="Research Team", goal="Research topics")
            >>> result = agent.delegate_to_team(team, "Research AI trends")
        """
        self._log(f"Delegating to team: {team.name}")
        
        # Add task to team context
        team.shared_context['task'] = task
        team.shared_context['delegated_by'] = self.name
        
        # Send message to team
        team.message_history.append({
            'from': self.name,
            'type': 'task_delegation',
            'content': task,
            'timestamp': datetime.now().isoformat(),
        })
        
        # Execute team task if method available
        if hasattr(team, 'execute_task'):
            return team.execute_task(task, coordinator=coordinator_role, **kwargs)
        
        # Otherwise, run through all team members
        results = []
        for member in team.members.values():
            result = member.run(task, **kwargs)
            results.append({
                'agent': member.name,
                'role': team.role_assignments.get(member.id),
                'result': result,
            })
        
        return {
            'team': team.name,
            'task': task,
            'results': results,
        }
    
    def with_supervisor(
        self,
        supervisor: Any,  # AgentSupervisor
    ) -> 'Agent':
        """
        Attach this agent to a supervisor.
        
        Args:
            supervisor: The AgentSupervisor to attach to
            
        Returns:
            Self for chaining
            
        Example:
            >>> from agenticaiframework.orchestration import AgentSupervisor
            >>> supervisor = AgentSupervisor(name="Manager")
            >>> agent.with_supervisor(supervisor)
        """
        supervisor.add_agent(self)
        self.supervisor_id = supervisor.id
        self._log(f"Attached to supervisor: {supervisor.name}")
        return self
    
    def add_tool(self, tool: Any) -> 'Agent':
        """
        Add a tool to this agent.
        
        Args:
            tool: Tool instance to add
            
        Returns:
            Self for chaining
            
        Example:
            >>> from agenticaiframework.tools import PythonCodeExecutor
            >>> agent.add_tool(PythonCodeExecutor())
        """
        from ..tools import tool_registry, agent_tool_manager
        
        tool_name = getattr(tool, 'name', type(tool).__name__)
        
        # Register tool if not already registered
        if not tool_registry.get_tool_class(tool_name):
            tool_registry.register(type(tool))
        
        # Bind to this agent
        agent_tool_manager.bind_tools(self, [tool_name])
        
        self._log(f"Added tool: {tool_name}")
        return self
    
    def with_guardrails(
        self,
        pipeline: Any = None,
        preset: str = "minimal",
    ) -> 'Agent':
        """
        Configure guardrails for this agent.
        
        Args:
            pipeline: GuardrailPipeline instance, or None to use preset
            preset: Preset name if no pipeline given - 'minimal', 'safety', 'enterprise'
            
        Returns:
            Self for chaining
            
        Example:
            >>> agent.with_guardrails(preset="enterprise")
            >>> # or
            >>> from agenticaiframework.guardrails import GuardrailPipeline
            >>> agent.with_guardrails(GuardrailPipeline.safety_only())
        """
        from ..guardrails import GuardrailPipeline
        
        if pipeline is not None:
            self.config['guardrail_pipeline'] = pipeline
        else:
            if preset == "enterprise":
                self.config['guardrail_pipeline'] = GuardrailPipeline.enterprise_defaults()
            elif preset == "safety":
                self.config['guardrail_pipeline'] = GuardrailPipeline.safety_only()
            else:
                self.config['guardrail_pipeline'] = GuardrailPipeline.minimal()
        
        self._log(f"Configured guardrails: {preset}")
        return self
    
    def with_knowledge(self, knowledge: Any) -> 'Agent':
        """
        Attach a knowledge retriever to this agent.
        
        Args:
            knowledge: KnowledgeRetriever instance
            
        Returns:
            Self for chaining
        """
        self.config['knowledge'] = knowledge
        self._log("Knowledge retriever attached")
        return self
    
    def with_policy(self, policy_engine: Any) -> 'Agent':
        """
        Attach a policy engine to this agent.
        
        Args:
            policy_engine: PolicyEngine instance
            
        Returns:
            Self for chaining
        """
        self.config['policy_manager'] = policy_engine
        self._log("Policy engine attached")
        return self
    
    # ========================================================================
    # REMOTE AGENT COMMUNICATION
    # ========================================================================
    
    def connect_remote(
        self,
        agent_id: str,
        url: Optional[str] = None,
        protocol: str = "http",
        host: str = "localhost",
        port: int = 8080,
        path: str = "/agent",
        auth_token: Optional[str] = None,
    ) -> 'Agent':
        """
        Connect to a remote agent for communication.
        
        Args:
            agent_id: Identifier for the remote agent
            url: Full URL (parses host/port/protocol)
            protocol: 'http', 'https', 'sse', 'mqtt', 'websocket'
            host: Agent host
            port: Agent port
            path: API path
            auth_token: Authentication token
            
        Returns:
            Self for chaining
            
        Example:
            >>> agent.connect_remote("analyzer", url="https://analyzer.example.com/agent")
            >>> agent.connect_remote("iot-bot", protocol="mqtt", host="mqtt.example.com")
        """
        from ..communication import AgentCommunicationManager, ProtocolType
        
        # Get or create communication manager
        if 'comm_manager' not in self.config:
            self.config['comm_manager'] = AgentCommunicationManager(agent_id=self.id)
        
        manager = self.config['comm_manager']
        
        # Map protocol string to enum
        protocol_map = {
            'http': ProtocolType.HTTP,
            'https': ProtocolType.HTTPS,
            'sse': ProtocolType.SSE,
            'mqtt': ProtocolType.MQTT,
            'websocket': ProtocolType.WEBSOCKET,
            'ws': ProtocolType.WEBSOCKET,
            'stdio': ProtocolType.STDIO,
        }
        proto_type = protocol_map.get(protocol.lower(), ProtocolType.HTTP)
        
        manager.register_agent(
            agent_id=agent_id,
            url=url,
            protocol=proto_type,
            host=host,
            port=port,
            path=path,
            auth_token=auth_token,
        )
        
        self._log(f"Connected to remote agent: {agent_id}")
        return self
    
    def send_to_agent(
        self,
        agent_id: str,
        message: Union[str, Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        """
        Send a message to a remote or local agent.
        
        Args:
            agent_id: Target agent identifier
            message: Message content (prompt or structured data)
            context: Additional context to send
            timeout: Response timeout
            
        Returns:
            Agent response
            
        Example:
            >>> response = agent.send_to_agent("analyzer", "Analyze this data")
            >>> response = agent.send_to_agent("coder", {"task": "refactor", "code": code})
        """
        if 'comm_manager' not in self.config:
            return {"error": f"No agents connected. Use connect_remote() first."}
        
        manager = self.config['comm_manager']
        return manager.send(agent_id, message, context, timeout)
    
    def stream_from_agent(
        self,
        agent_id: str,
        message: Union[str, Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
    ):
        """
        Stream response from a remote agent.
        
        Args:
            agent_id: Target agent identifier
            message: Message content
            context: Additional context
            
        Yields:
            Response chunks
            
        Example:
            >>> for chunk in agent.stream_from_agent("writer", "Write a story"):
            ...     print(chunk, end="")
        """
        if 'comm_manager' not in self.config:
            yield {"error": "No agents connected"}
            return
        
        manager = self.config['comm_manager']
        for chunk in manager.stream(agent_id, message, context):
            yield chunk
    
    def broadcast_to_agents(
        self,
        message: Union[str, Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
        exclude: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Broadcast a message to all connected agents.
        
        Args:
            message: Message content
            context: Additional context
            exclude: Agent IDs to exclude
            
        Returns:
            Responses from all agents
        """
        if 'comm_manager' not in self.config:
            return {"error": "No agents connected"}
        
        manager = self.config['comm_manager']
        return manager.broadcast(message, context, exclude)
    
    def as_server(
        self,
        framework: str = "flask",
        host: str = "0.0.0.0",
        port: int = 8080,
    ):
        """
        Expose this agent as a remote service.
        
        Args:
            framework: 'flask' or 'fastapi'
            host: Server host
            port: Server port
            
        Returns:
            Web application instance (Flask or FastAPI)
            
        Example:
            >>> # Flask
            >>> app = agent.as_server("flask")
            >>> app.run(port=8080)
            
            >>> # FastAPI
            >>> app = agent.as_server("fastapi")
            >>> uvicorn.run(app, port=8080)
        """
        from ..communication import RemoteAgentServer
        
        server = RemoteAgentServer(self, agent_id=self.id)
        
        if framework.lower() == "fastapi":
            return server.create_fastapi_app()
        else:
            return server.create_flask_app()
    
    # ========================================================================
    # KNOWLEDGE BASE BUILDING
    # ========================================================================
    
    def create_knowledge_from(
        self,
        sources: Union[str, List[str]],
        embedding_provider: str = "openai",
        embedding_model: Optional[str] = None,
        **kwargs,
    ) -> 'Agent':
        """
        Create knowledge base from various sources.
        
        Sources can be:
        - File paths: "docs/manual.pdf", "data/info.txt"
        - URLs: "https://example.com/article"
        - Web search: "search:machine learning best practices"
        - API: "api:https://api.example.com/data"
        
        Args:
            sources: Source or list of sources
            embedding_provider: 'openai', 'azure', 'huggingface', 'cohere'
            embedding_model: Specific model name
            **kwargs: Additional options for loaders
            
        Returns:
            Self for chaining
            
        Example:
            >>> agent.create_knowledge_from([
            ...     "docs/manual.pdf",
            ...     "https://example.com/docs",
            ...     "search:best practices",
            ... ])
        """
        from ..knowledge import KnowledgeBuilder
        
        # Get or create knowledge builder
        if 'knowledge_builder' not in self.config:
            self.config['knowledge_builder'] = KnowledgeBuilder(
                embedding_provider=embedding_provider,
                embedding_model=embedding_model,
            )
        
        builder = self.config['knowledge_builder']
        
        # Normalize to list
        if isinstance(sources, str):
            sources = [sources]
        
        # Add each source
        for source in sources:
            try:
                builder.add(source, **kwargs)
            except Exception as e:
                self._log(f"Failed to add source {source}: {e}")
        
        self._log(f"Added {len(sources)} sources to knowledge base")
        return self
    
    def add_knowledge_from_web_search(
        self,
        query: str,
        num_results: int = 5,
        fetch_content: bool = True,
    ) -> 'Agent':
        """
        Add knowledge from web search results.
        
        Args:
            query: Search query
            num_results: Number of search results
            fetch_content: Whether to fetch full page content
            
        Returns:
            Self for chaining
        """
        from ..knowledge import KnowledgeBuilder
        
        if 'knowledge_builder' not in self.config:
            self.config['knowledge_builder'] = KnowledgeBuilder()
        
        builder = self.config['knowledge_builder']
        builder.add_from_web_search(query, num_results, fetch_content)
        
        self._log(f"Added web search results for: {query}")
        return self
    
    def add_knowledge_from_api(
        self,
        url: str,
        method: str = "GET",
        headers: Optional[Dict] = None,
        data: Optional[Dict] = None,
        json_path: Optional[str] = None,
    ) -> 'Agent':
        """
        Add knowledge from an API endpoint.
        
        Args:
            url: API URL
            method: HTTP method
            headers: Request headers
            data: Request body
            json_path: JSON path to extract (e.g., "data.items")
            
        Returns:
            Self for chaining
        """
        from ..knowledge import KnowledgeBuilder
        
        if 'knowledge_builder' not in self.config:
            self.config['knowledge_builder'] = KnowledgeBuilder()
        
        builder = self.config['knowledge_builder']
        builder.add_from_api(url, method, headers, data, json_path)
        
        self._log(f"Added API data from: {url}")
        return self
    
    def add_knowledge_from_image(
        self,
        image_path: str,
        ocr_provider: str = "openai_vision",
        vision_prompt: Optional[str] = None,
    ) -> 'Agent':
        """
        Add knowledge from an image using OCR or vision models.
        
        Args:
            image_path: Path to image file
            ocr_provider: 'pytesseract' or 'openai_vision'
            vision_prompt: Custom prompt for vision model
            
        Returns:
            Self for chaining
        """
        from ..knowledge import KnowledgeBuilder
        
        if 'knowledge_builder' not in self.config:
            self.config['knowledge_builder'] = KnowledgeBuilder()
        
        builder = self.config['knowledge_builder']
        builder.add_from_image(image_path, ocr_provider, vision_prompt)
        
        self._log(f"Added image content from: {image_path}")
        return self
    
    def get_knowledge_embeddings(self) -> List[Any]:
        """
        Get embeddings from built knowledge base.
        
        Returns:
            List of EmbeddingOutput objects ready for vector database
            
        Example:
            >>> embeddings = agent.get_knowledge_embeddings()
            >>> for emb in embeddings:
            ...     # Store in Qdrant
            ...     qdrant_client.upsert(emb.to_qdrant_point())
            ...     # Or Pinecone
            ...     pinecone_index.upsert([emb.to_pinecone_vector()])
        """
        if 'knowledge_builder' not in self.config:
            return []
        
        builder = self.config['knowledge_builder']
        return builder.get_embeddings()
    
    def store_knowledge_in_vector_db(
        self,
        db_type: str = "memory",
        collection_name: str = "knowledge",
        **db_config,
    ) -> 'Agent':
        """
        Store knowledge embeddings in a vector database.
        
        Args:
            db_type: 'qdrant', 'pinecone', 'chroma', 'memory'
            collection_name: Collection/index name
            **db_config: Database-specific configuration
            
        Returns:
            Self for chaining
            
        Example:
            >>> agent.create_knowledge_from(["docs/"])
            >>> agent.store_knowledge_in_vector_db(
            ...     db_type="qdrant",
            ...     host="localhost",
            ...     port=6333,
            ...     collection_name="my_knowledge"
            ... )
        """
        from ..knowledge import UnifiedVectorDBTool
        
        embeddings = self.get_knowledge_embeddings()
        if not embeddings:
            self._log("No embeddings to store")
            return self
        
        # Create vector DB tool
        db_tool = UnifiedVectorDBTool(
            db_type=db_type,
            collection_name=collection_name,
            **db_config,
        )
        
        # Insert embeddings
        vectors = [e.embedding for e in embeddings]
        ids = [e.id for e in embeddings]
        payloads = [{"content": e.content, **e.metadata} for e in embeddings]
        
        result = db_tool.insert(vectors, ids, payloads)
        
        if result.success:
            self._log(f"Stored {len(embeddings)} embeddings in {db_type}")
            # Store reference to DB tool for queries
            self.config['vector_db'] = db_tool
        else:
            self._log(f"Failed to store embeddings: {result.error}")
        
        return self
    
    def search_knowledge(
        self,
        query: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Search knowledge base using semantic similarity.
        
        Args:
            query: Search query
            limit: Number of results
            
        Returns:
            List of matching documents with scores
        """
        if 'vector_db' not in self.config:
            return []
        
        # Generate query embedding
        if 'knowledge_builder' not in self.config:
            return []
        
        builder = self.config['knowledge_builder']
        query_embedding = builder.embedding.embed(query)
        
        # Search
        db = self.config['vector_db']
        result = db.search(query_embedding, limit)
        
        if result.success:
            return result.result.get("matches", [])
        return []

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
    # =========================================================================
    # Output Formatting Methods
    # =========================================================================
    
    def with_formatter(self, format_type: str = "markdown") -> "Agent":
        """
        Enable output formatting for agent responses.
        
        Args:
            format_type: Default format ('markdown', 'code', 'json', 'html', 'table')
        
        Example:
            >>> agent = Agent.quick("Assistant").with_formatter("markdown")
            >>> result = agent.format_response("Hello World", template="heading")
        """
        try:
            from ..formatting import OutputFormatter, FormatType
            self.config['formatter'] = OutputFormatter()
            self.config['default_format'] = format_type
            self._log(f"Output formatter enabled with default: {format_type}")
        except ImportError:
            self._log("Warning: Formatting module not available")
        return self
    
    def format_response(
        self,
        content: Any,
        format_type: str = None,
        **options
    ) -> str:
        """
        Format agent response in specified format.
        
        Args:
            content: Content to format
            format_type: 'markdown', 'code', 'json', 'html', 'table', 'plain'
            **options: Format-specific options
        
        Returns:
            Formatted string
        """
        if 'formatter' not in self.config:
            self.with_formatter()
        
        from ..formatting import FormatType
        
        formatter = self.config['formatter']
        fmt = format_type or self.config.get('default_format', 'plain')
        
        format_map = {
            'markdown': FormatType.MARKDOWN,
            'code': FormatType.CODE,
            'json': FormatType.JSON,
            'html': FormatType.HTML,
            'table': FormatType.TABLE,
            'plain': FormatType.PLAIN,
        }
        
        result = formatter.format(content, format_map.get(fmt, FormatType.PLAIN), **options)
        return result.formatted
    
    def format_as_markdown(self, content: Any, **options) -> str:
        """Format as Markdown."""
        return self.format_response(content, "markdown", **options)
    
    def format_as_code(self, code: str, language: str = "", **options) -> str:
        """Format as code block."""
        options['language'] = language
        return self.format_response(code, "code", **options)
    
    def format_as_table(self, data: List[Dict], **options) -> str:
        """Format data as table."""
        return self.format_response(data, "table", **options)
    
    def format_as_json(self, data: Any, indent: int = 2) -> str:
        """Format as pretty JSON."""
        return self.format_response(data, "json", indent=indent)

    # =========================================================================
    # Conversation & Logging Methods
    # =========================================================================
    
    def with_conversation(
        self,
        session_id: str = None,
        system_message: str = None,
        persist: bool = False,
        persist_path: str = None,
    ) -> "Agent":
        """
        Enable conversation history tracking.
        
        Args:
            session_id: Session identifier
            system_message: System prompt
            persist: Auto-save conversations
            persist_path: Path for saving conversations
        
        Example:
            >>> agent = Agent.quick("Assistant").with_conversation(
            ...     system_message="You are a helpful assistant."
            ... )
            >>> agent.chat("Hello!")
            >>> agent.chat("What did I just say?")
        """
        try:
            from ..conversations import ConversationManager, ConversationConfig
            
            config = ConversationConfig(
                persist=persist,
                persist_path=persist_path,
            )
            
            conv = ConversationManager(
                agent_id=self.id,
                session_id=session_id,
                config=config,
            )
            
            if system_message:
                conv.set_system_message(system_message)
            
            self.config['conversation'] = conv
            self._log(f"Conversation tracking enabled (session: {conv.session.id})")
        except ImportError:
            self._log("Warning: Conversation module not available")
        return self
    
    def chat(self, message: str, **kwargs) -> str:
        """
        Send message and get response with conversation tracking.
        
        Args:
            message: User message
            **kwargs: Additional options
        
        Returns:
            Assistant response
        """
        if 'conversation' not in self.config:
            self.with_conversation()
        
        conv = self.config['conversation']
        conv.add_user_message(message)
        
        # Get response from LLM
        if 'llm' in self.config:
            messages = conv.get_messages_for_llm()
            response = self.config['llm'].generate(messages, **kwargs)
            response_text = response if isinstance(response, str) else str(response)
        else:
            response_text = self.run(message, **kwargs)
        
        conv.add_assistant_message(response_text)
        return response_text
    
    def get_conversation_history(self, limit: int = None) -> List[Dict]:
        """Get conversation history."""
        if 'conversation' not in self.config:
            return []
        return [m.to_dict() for m in self.config['conversation'].get_history(limit)]
    
    def export_conversation(self, format: str = "markdown") -> str:
        """
        Export conversation in specified format.
        
        Args:
            format: 'markdown', 'json', 'html'
        """
        if 'conversation' not in self.config:
            return ""
        
        conv = self.config['conversation']
        if format == "markdown":
            return conv.export_markdown()
        elif format == "json":
            return conv.export_json()
        elif format == "html":
            return conv.export_html()
        return conv.export_json()
    
    def clear_conversation(self, keep_system: bool = True) -> None:
        """Clear conversation history."""
        if 'conversation' in self.config:
            self.config['conversation'].clear(keep_system)
    
    def with_logging(
        self,
        level: str = "info",
        output: str = "console",
        file_path: str = None,
    ) -> "Agent":
        """
        Enable structured logging.
        
        Args:
            level: 'debug', 'info', 'warning', 'error'
            output: 'console', 'file', 'both'
            file_path: Log file path
        """
        try:
            from ..conversations import AgentLogger, LogConfig, LogLevel
            
            level_map = {
                'debug': LogLevel.DEBUG,
                'info': LogLevel.INFO,
                'warning': LogLevel.WARNING,
                'error': LogLevel.ERROR,
            }
            
            config = LogConfig(
                level=level_map.get(level, LogLevel.INFO),
                output=output,
                file_path=file_path,
            )
            
            self.config['logger'] = AgentLogger(
                agent_id=self.id,
                config=config,
            )
            self._log(f"Structured logging enabled (level: {level})")
        except ImportError:
            self._log("Warning: Logging module not available")
        return self
    
    def log_event(self, event_type: str, message: str, data: Dict = None) -> None:
        """Log a structured event."""
        if 'logger' in self.config:
            self.config['logger'].event(event_type, message, data)
        else:
            self._log(f"[{event_type}] {message}")

    # =========================================================================
    # Speech (STT/TTS) Methods
    # =========================================================================
    
    def with_speech(
        self,
        stt_provider: str = "openai",
        tts_provider: str = "openai",
        voice_id: str = "alloy",
        **provider_config,
    ) -> "Agent":
        """
        Enable speech capabilities (STT and TTS).
        
        Args:
            stt_provider: 'openai', 'azure', 'google', 'whisper_local'
            tts_provider: 'openai', 'azure', 'google', 'elevenlabs'
            voice_id: Voice identifier
            **provider_config: Provider-specific configuration
        
        Example:
            >>> agent = Agent.quick("Assistant").with_speech(
            ...     stt_provider="openai",
            ...     tts_provider="elevenlabs",
            ...     elevenlabs_api_key="..."
            ... )
            >>> text = agent.listen("question.mp3")
            >>> agent.speak("Here's my answer", save_to="answer.mp3")
        """
        try:
            from ..speech import SpeechProcessor, VoiceConfig
            
            voice = VoiceConfig(voice_id=voice_id)
            
            self.config['speech'] = SpeechProcessor(
                stt_provider=stt_provider,
                tts_provider=tts_provider,
                voice=voice,
                **provider_config,
            )
            self._log(f"Speech enabled (STT: {stt_provider}, TTS: {tts_provider})")
        except ImportError:
            self._log("Warning: Speech module not available")
        return self
    
    def listen(self, audio: Union[str, bytes], language: str = None) -> str:
        """
        Transcribe audio to text.
        
        Args:
            audio: Audio file path or bytes
            language: Language code (e.g., 'en', 'es')
        
        Returns:
            Transcribed text
        """
        if 'speech' not in self.config:
            raise ValueError("Speech not enabled. Call with_speech() first.")
        
        result = self.config['speech'].transcribe(audio, language)
        return result.text
    
    def speak(
        self,
        text: str,
        save_to: str = None,
        voice_id: str = None,
    ):
        """
        Convert text to speech.
        
        Args:
            text: Text to speak
            save_to: Optional file path to save audio
            voice_id: Override voice ID
        
        Returns:
            TTSResult with audio data
        """
        if 'speech' not in self.config:
            raise ValueError("Speech not enabled. Call with_speech() first.")
        
        from ..speech import VoiceConfig
        
        voice = None
        if voice_id:
            voice = VoiceConfig(voice_id=voice_id)
        
        result = self.config['speech'].synthesize(text, voice)
        
        if save_to:
            result.save(save_to)
        
        return result
    
    def voice_chat(
        self,
        audio_input: Union[str, bytes],
        save_response_to: str = None,
    ) -> tuple:
        """
        Complete voice conversation turn.
        
        Args:
            audio_input: User's audio message
            save_response_to: Path to save response audio
        
        Returns:
            Tuple of (transcribed_input, response_text, response_audio)
        """
        if 'speech' not in self.config:
            raise ValueError("Speech not enabled. Call with_speech() first.")
        
        # Transcribe input
        user_text = self.listen(audio_input)
        
        # Get response
        response_text = self.chat(user_text)
        
        # Synthesize response
        response_audio = self.speak(response_text, save_to=save_response_to)
        
        return user_text, response_text, response_audio

    # =========================================================================
    # Human-in-the-Loop Methods
    # =========================================================================
    
    def with_human_oversight(
        self,
        approval_required_for: List[str] = None,
        auto_approve_after: int = None,
        handler: str = "console",
    ) -> "Agent":
        """
        Enable human-in-the-loop oversight.
        
        Args:
            approval_required_for: Actions requiring approval
                (e.g., ['tool_call', 'external_api', 'send_email'])
            auto_approve_after: Seconds before auto-approval (None = never)
            handler: 'console', 'callback', 'queue'
        
        Example:
            >>> agent = Agent.quick("Assistant").with_human_oversight(
            ...     approval_required_for=["send_email", "delete_file"],
            ...     handler="console"
            ... )
        """
        try:
            from ..hitl import (
                HumanInTheLoop,
                ConsoleApprovalHandler,
                CallbackApprovalHandler,
                QueueApprovalHandler,
            )
            
            handlers = {
                'console': ConsoleApprovalHandler(),
                'callback': CallbackApprovalHandler(),
                'queue': QueueApprovalHandler(),
            }
            
            self.config['hitl'] = HumanInTheLoop(
                agent_id=self.id,
                approval_required_for=approval_required_for or [],
                approval_handler=handlers.get(handler, handlers['callback']),
                auto_approve_after=auto_approve_after,
            )
            self._log(f"Human oversight enabled (handler: {handler})")
        except ImportError:
            self._log("Warning: HITL module not available")
        return self
    
    def requires_approval(self, action: str, details: Dict = None) -> bool:
        """Check if action requires human approval."""
        if 'hitl' not in self.config:
            return False
        return self.config['hitl'].requires_approval(action, details)
    
    def request_approval(
        self,
        action: str,
        details: Dict,
        reason: str = "Action requires approval",
        timeout: int = None,
    ) -> bool:
        """
        Request human approval for an action.
        
        Args:
            action: Action type
            details: Action details to review
            reason: Why approval is needed
            timeout: Timeout in seconds
        
        Returns:
            True if approved, False otherwise
        """
        if 'hitl' not in self.config:
            self.with_human_oversight()
        
        from ..hitl import ApprovalStatus
        
        decision = self.config['hitl'].request_approval(
            action=action,
            details=details,
            reason=reason,
            timeout=timeout,
        )
        
        return decision.status == ApprovalStatus.APPROVED
    
    def collect_feedback(
        self,
        response_id: str,
        feedback_type: str = "thumbs",
        value: Any = None,
    ):
        """
        Collect human feedback on a response.
        
        Args:
            response_id: ID of the response
            feedback_type: 'rating', 'thumbs', 'text', 'correction', 'flag'
            value: Feedback value
        """
        if 'hitl' not in self.config:
            self.with_human_oversight()
        
        collector = self.config['hitl'].feedback
        
        if feedback_type == "rating":
            return collector.collect_rating(response_id, value)
        elif feedback_type == "thumbs":
            return collector.collect_thumbs(response_id, value)
        elif feedback_type == "text":
            return collector.collect_text(response_id, value)
        else:
            return collector.collect_text(response_id, str(value))
    
    def request_human_help(self, reason: str, context: Dict = None):
        """
        Request human intervention/help.
        
        Use when agent is uncertain or needs guidance.
        """
        if 'hitl' not in self.config:
            self.with_human_oversight()
        
        from ..hitl import EscalationLevel
        
        return self.config['hitl'].request_intervention(
            reason=reason,
            level=EscalationLevel.MEDIUM,
            context=context or {},
        )
    
    def pause_for_review(self, reason: str = "Paused for human review"):
        """Pause agent operation for human review."""
        if 'hitl' not in self.config:
            self.with_human_oversight()
        
        return self.config['hitl'].pause_agent(reason)
    
    def get_feedback_summary(self, response_id: str) -> Dict:
        """Get feedback summary for a response."""
        if 'hitl' not in self.config:
            return {}
        return self.config['hitl'].feedback.get_summary(response_id)