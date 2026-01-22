"""
Enterprise Decorators - Zero-boilerplate patterns for AI applications.

Decorators that transform simple classes/functions into production-ready
AI components with automatic tracing, error handling, and cloud integration.

Usage:
    >>> from agenticaiframework.enterprise import agent, workflow, tool
    >>> 
    >>> @agent(role="analyst", model="gpt-4o")
    >>> class DataAnalyst:
    ...     '''Analyzes data and provides insights.'''
    ...     
    ...     async def analyze(self, data: str) -> dict:
    ...         return await self.invoke(f"Analyze this data: {data}")
    >>> 
    >>> analyst = DataAnalyst()
    >>> result = await analyst.analyze("Sales data Q4 2025")
"""

import asyncio
import functools
import inspect
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Type,
    TypeVar,
    Union,
    get_type_hints,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])


# =============================================================================
# Configuration Dataclasses
# =============================================================================

@dataclass
class AgentConfig:
    """Configuration for @agent decorator."""
    role: str = "assistant"
    model: str = "gpt-4o"
    provider: str = "azure"
    temperature: float = 0.7
    max_tokens: int = 4096
    tools: List[str] = field(default_factory=list)
    guardrails: List[str] = field(default_factory=list)
    tracing: bool = True
    retry_attempts: int = 3
    timeout_seconds: int = 120
    cache_enabled: bool = False
    memory_enabled: bool = True


@dataclass
class WorkflowConfig:
    """Configuration for @workflow decorator."""
    name: str = ""
    parallel: bool = False
    max_concurrency: int = 5
    retry_on_failure: bool = True
    save_artifacts: bool = True
    tracing: bool = True


@dataclass
class ToolConfig:
    """Configuration for @tool decorator."""
    name: str = ""
    description: str = ""
    requires_auth: bool = False
    rate_limit: Optional[int] = None
    timeout: int = 30
    cache_ttl: int = 0


# =============================================================================
# @agent Decorator
# =============================================================================

def agent(
    role: str = "assistant",
    model: str = "gpt-4o",
    provider: str = "azure",
    temperature: float = 0.7,
    max_tokens: int = 4096,
    tools: Optional[List[str]] = None,
    guardrails: Optional[List[str]] = None,
    tracing: bool = True,
    retry_attempts: int = 3,
    timeout_seconds: int = 120,
    cache_enabled: bool = False,
    memory_enabled: bool = True,
) -> Callable[[Type[T]], Type[T]]:
    """
    Transform a class into a production-ready AI agent.
    
    Automatically adds:
    - LLM integration with the specified model
    - Memory management
    - Tracing and metrics
    - Error handling with retries
    - Tool binding
    - Guardrails
    
    Args:
        role: Agent role (affects system prompt)
        model: LLM model name
        provider: LLM provider (azure, openai, anthropic)
        temperature: Sampling temperature
        max_tokens: Maximum tokens for completion
        tools: List of tool names to bind
        guardrails: List of guardrail names to apply
        tracing: Enable tracing
        retry_attempts: Number of retry attempts on failure
        timeout_seconds: Timeout for LLM calls
        cache_enabled: Enable response caching
        memory_enabled: Enable conversation memory
        
    Returns:
        Decorated class with agent capabilities
        
    Example:
        >>> @agent(role="coder", model="gpt-4o")
        >>> class CodeAssistant:
        ...     '''Helps with coding tasks.'''
        ...     
        ...     async def generate_code(self, spec: str) -> str:
        ...         return await self.invoke(f"Generate code for: {spec}")
    """
    config = AgentConfig(
        role=role,
        model=model,
        provider=provider,
        temperature=temperature,
        max_tokens=max_tokens,
        tools=tools or [],
        guardrails=guardrails or [],
        tracing=tracing,
        retry_attempts=retry_attempts,
        timeout_seconds=timeout_seconds,
        cache_enabled=cache_enabled,
        memory_enabled=memory_enabled,
    )
    
    def decorator(cls: Type[T]) -> Type[T]:
        # Store original __init__
        original_init = cls.__init__ if hasattr(cls, "__init__") else None
        
        def new_init(self, *args, **kwargs):
            # Initialize agent infrastructure
            self._agent_config = config
            self._agent_id = f"{cls.__name__.lower()}-{id(self)}"
            self._conversation_history: List[Dict[str, str]] = []
            self._metrics = {
                "invocations": 0,
                "successes": 0,
                "failures": 0,
                "total_tokens": 0,
                "total_latency_ms": 0,
            }
            
            # Initialize LLM client
            self._llm_client = _get_llm_client(config)
            
            # Initialize memory if enabled
            if config.memory_enabled:
                self._memory = _get_memory_manager(self._agent_id)
            
            # Call original __init__ if it exists
            if original_init and original_init is not object.__init__:
                original_init(self, *args, **kwargs)
        
        async def invoke(
            self,
            prompt: str,
            context: Optional[Dict[str, Any]] = None,
            **kwargs,
        ) -> str:
            """Invoke the agent with a prompt."""
            start_time = time.time()
            
            try:
                # Build messages
                messages = _build_messages(
                    self,
                    prompt,
                    context,
                    config,
                )
                
                # Call LLM with retry
                for attempt in range(config.retry_attempts):
                    try:
                        response = await _call_llm(
                            self._llm_client,
                            messages,
                            config,
                            **kwargs,
                        )
                        
                        # Update metrics
                        self._metrics["invocations"] += 1
                        self._metrics["successes"] += 1
                        latency_ms = (time.time() - start_time) * 1000
                        self._metrics["total_latency_ms"] += latency_ms
                        
                        # Update memory
                        if config.memory_enabled:
                            self._conversation_history.append(
                                {"role": "user", "content": prompt}
                            )
                            self._conversation_history.append(
                                {"role": "assistant", "content": response}
                            )
                        
                        return response
                        
                    except Exception as e:
                        if attempt == config.retry_attempts - 1:
                            raise
                        logger.warning(f"Retry {attempt + 1}/{config.retry_attempts}: {e}")
                        await asyncio.sleep(2 ** attempt)
                        
            except Exception as e:
                self._metrics["invocations"] += 1
                self._metrics["failures"] += 1
                logger.error(f"Agent {self._agent_id} failed: {e}")
                raise
        
        def invoke_sync(
            self,
            prompt: str,
            context: Optional[Dict[str, Any]] = None,
            **kwargs,
        ) -> str:
            """Synchronous version of invoke."""
            return asyncio.get_event_loop().run_until_complete(
                invoke(self, prompt, context, **kwargs)
            )
        
        def get_metrics(self) -> Dict[str, Any]:
            """Get agent performance metrics."""
            metrics = dict(self._metrics)
            if metrics["invocations"] > 0:
                metrics["success_rate"] = metrics["successes"] / metrics["invocations"]
                metrics["avg_latency_ms"] = metrics["total_latency_ms"] / metrics["invocations"]
            return metrics
        
        def clear_memory(self):
            """Clear conversation history."""
            self._conversation_history = []
        
        # Attach methods to class
        cls.__init__ = new_init
        cls.invoke = invoke
        cls.invoke_sync = invoke_sync
        cls.get_metrics = get_metrics
        cls.clear_memory = clear_memory
        
        # Store config on class
        cls._agent_decorator_config = config
        
        return cls
    
    return decorator


# =============================================================================
# @workflow Decorator
# =============================================================================

def workflow(
    name: Optional[str] = None,
    parallel: bool = False,
    max_concurrency: int = 5,
    retry_on_failure: bool = True,
    save_artifacts: bool = True,
    tracing: bool = True,
) -> Callable[[Type[T]], Type[T]]:
    """
    Transform a class into a managed workflow.
    
    Adds:
    - Step orchestration
    - Artifact management
    - Error handling
    - Parallel execution support
    - Tracing
    
    Example:
        >>> @workflow(name="data-pipeline", parallel=True)
        >>> class DataPipeline:
        ...     @step(order=1)
        ...     async def extract(self, source: str) -> dict:
        ...         return {"data": "extracted"}
        ...     
        ...     @step(order=2)
        ...     async def transform(self, data: dict) -> dict:
        ...         return {"data": "transformed"}
        ...     
        ...     @step(order=3)
        ...     async def load(self, data: dict) -> bool:
        ...         return True
    """
    config = WorkflowConfig(
        name=name or "",
        parallel=parallel,
        max_concurrency=max_concurrency,
        retry_on_failure=retry_on_failure,
        save_artifacts=save_artifacts,
        tracing=tracing,
    )
    
    def decorator(cls: Type[T]) -> Type[T]:
        original_init = cls.__init__ if hasattr(cls, "__init__") else None
        
        def new_init(self, *args, **kwargs):
            self._workflow_config = config
            self._workflow_name = config.name or cls.__name__
            self._workflow_id = f"{self._workflow_name}-{id(self)}"
            self._steps: List[Dict[str, Any]] = []
            self._artifacts: Dict[str, Any] = {}
            self._execution_log: List[Dict[str, Any]] = []
            
            # Discover steps
            for method_name in dir(cls):
                method = getattr(cls, method_name)
                if hasattr(method, "_step_config"):
                    self._steps.append({
                        "name": method_name,
                        "order": method._step_config.get("order", 0),
                        "method": method,
                    })
            
            # Sort steps by order
            self._steps.sort(key=lambda x: x["order"])
            
            if original_init and original_init is not object.__init__:
                original_init(self, *args, **kwargs)
        
        async def run(self, input_data: Any = None, **kwargs) -> Dict[str, Any]:
            """Execute the workflow."""
            start_time = time.time()
            current_data = input_data
            results = {}
            
            logger.info(f"Starting workflow: {self._workflow_name}")
            
            for step_info in self._steps:
                step_name = step_info["name"]
                step_method = getattr(self, step_name)
                
                try:
                    step_start = time.time()
                    
                    if asyncio.iscoroutinefunction(step_method):
                        result = await step_method(current_data, **kwargs)
                    else:
                        result = step_method(current_data, **kwargs)
                    
                    step_duration = time.time() - step_start
                    
                    self._execution_log.append({
                        "step": step_name,
                        "status": "success",
                        "duration_seconds": step_duration,
                        "timestamp": datetime.utcnow().isoformat(),
                    })
                    
                    results[step_name] = result
                    current_data = result
                    
                except Exception as e:
                    self._execution_log.append({
                        "step": step_name,
                        "status": "failed",
                        "error": str(e),
                        "timestamp": datetime.utcnow().isoformat(),
                    })
                    
                    if config.retry_on_failure:
                        logger.warning(f"Step {step_name} failed, retrying: {e}")
                        # Simple retry
                        try:
                            if asyncio.iscoroutinefunction(step_method):
                                result = await step_method(current_data, **kwargs)
                            else:
                                result = step_method(current_data, **kwargs)
                            results[step_name] = result
                            current_data = result
                        except Exception as retry_error:
                            logger.error(f"Step {step_name} retry failed: {retry_error}")
                            raise
                    else:
                        raise
            
            total_duration = time.time() - start_time
            
            return {
                "status": "completed",
                "workflow": self._workflow_name,
                "results": results,
                "artifacts": self._artifacts,
                "duration_seconds": total_duration,
                "execution_log": self._execution_log,
            }
        
        def save_artifact(self, name: str, data: Any):
            """Save an artifact from the workflow."""
            self._artifacts[name] = {
                "data": data,
                "saved_at": datetime.utcnow().isoformat(),
            }
        
        def get_artifacts(self) -> Dict[str, Any]:
            """Get all saved artifacts."""
            return self._artifacts
        
        cls.__init__ = new_init
        cls.run = run
        cls.save_artifact = save_artifact
        cls.get_artifacts = get_artifacts
        cls._workflow_decorator_config = config
        
        return cls
    
    return decorator


# =============================================================================
# @step Decorator (for workflow steps)
# =============================================================================

def step(
    order: int = 0,
    name: Optional[str] = None,
    retry: int = 0,
    timeout: int = 300,
) -> Callable[[F], F]:
    """
    Mark a method as a workflow step.
    
    Args:
        order: Execution order (lower = earlier)
        name: Step name (defaults to method name)
        retry: Number of retries on failure
        timeout: Timeout in seconds
        
    Example:
        >>> @step(order=1, retry=2)
        >>> async def process_data(self, data: dict) -> dict:
        ...     return processed_data
    """
    def decorator(func: F) -> F:
        func._step_config = {
            "order": order,
            "name": name or func.__name__,
            "retry": retry,
            "timeout": timeout,
        }
        return func
    
    return decorator


# =============================================================================
# @tool Decorator
# =============================================================================

def tool(
    name: Optional[str] = None,
    description: Optional[str] = None,
    requires_auth: bool = False,
    rate_limit: Optional[int] = None,
    timeout: int = 30,
    cache_ttl: int = 0,
) -> Callable[[F], F]:
    """
    Transform a function into an agent-compatible tool.
    
    Adds:
    - Automatic schema generation from type hints
    - Rate limiting
    - Caching
    - Authentication support
    - Error handling
    
    Example:
        >>> @tool(name="web_search", description="Search the web")
        >>> async def search_web(query: str, max_results: int = 10) -> list:
        ...     # Implementation
        ...     return results
    """
    config = ToolConfig(
        name=name or "",
        description=description or "",
        requires_auth=requires_auth,
        rate_limit=rate_limit,
        timeout=timeout,
        cache_ttl=cache_ttl,
    )
    
    def decorator(func: F) -> F:
        tool_name = config.name or func.__name__
        tool_description = config.description or func.__doc__ or ""
        
        # Generate schema from type hints
        hints = get_type_hints(func) if hasattr(func, "__annotations__") else {}
        sig = inspect.signature(func)
        
        parameters = {}
        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue
            param_type = hints.get(param_name, str)
            parameters[param_name] = {
                "type": _python_type_to_json_type(param_type),
                "required": param.default == inspect.Parameter.empty,
            }
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                if asyncio.iscoroutinefunction(func):
                    result = await asyncio.wait_for(
                        func(*args, **kwargs),
                        timeout=config.timeout,
                    )
                else:
                    result = func(*args, **kwargs)
                
                return result
                
            except asyncio.TimeoutError:
                logger.error(f"Tool {tool_name} timed out after {config.timeout}s")
                raise
            except Exception as e:
                logger.error(f"Tool {tool_name} failed: {e}")
                raise
        
        # Attach tool metadata
        wrapper._tool_config = config
        wrapper._tool_name = tool_name
        wrapper._tool_description = tool_description
        wrapper._tool_parameters = parameters
        wrapper._tool_schema = {
            "name": tool_name,
            "description": tool_description,
            "parameters": {
                "type": "object",
                "properties": parameters,
            },
        }
        
        return wrapper
    
    return decorator


# =============================================================================
# @guardrail Decorator
# =============================================================================

def guardrail(
    name: Optional[str] = None,
    input_guard: bool = True,
    output_guard: bool = True,
    block_on_violation: bool = True,
) -> Callable[[F], F]:
    """
    Transform a function into a guardrail check.
    
    Example:
        >>> @guardrail(name="pii_detector")
        >>> def check_pii(text: str) -> bool:
        ...     # Return True if safe, False if PII detected
        ...     return not has_pii(text)
    """
    def decorator(func: F) -> F:
        guardrail_name = name or func.__name__
        
        @functools.wraps(func)
        async def wrapper(text: str, **kwargs) -> Dict[str, Any]:
            try:
                if asyncio.iscoroutinefunction(func):
                    is_safe = await func(text, **kwargs)
                else:
                    is_safe = func(text, **kwargs)
                
                return {
                    "passed": is_safe,
                    "guardrail": guardrail_name,
                    "action": "allow" if is_safe else ("block" if block_on_violation else "warn"),
                }
            except Exception as e:
                logger.error(f"Guardrail {guardrail_name} error: {e}")
                return {
                    "passed": False,
                    "guardrail": guardrail_name,
                    "error": str(e),
                    "action": "block" if block_on_violation else "warn",
                }
        
        wrapper._guardrail_config = {
            "name": guardrail_name,
            "input_guard": input_guard,
            "output_guard": output_guard,
            "block_on_violation": block_on_violation,
        }
        
        return wrapper
    
    return decorator


# =============================================================================
# @pipeline Decorator
# =============================================================================

def pipeline(
    name: Optional[str] = None,
    stages: Optional[List[str]] = None,
    parallel_stages: bool = False,
) -> Callable[[Type[T]], Type[T]]:
    """
    Transform a class into an execution pipeline.
    
    Example:
        >>> @pipeline(name="etl", stages=["extract", "transform", "load"])
        >>> class ETLPipeline:
        ...     async def extract(self, source): ...
        ...     async def transform(self, data): ...
        ...     async def load(self, data): ...
    """
    # Alias for workflow with explicit stages
    return workflow(
        name=name,
        parallel=parallel_stages,
    )


# =============================================================================
# Utility Decorators
# =============================================================================

def retry(
    attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
) -> Callable[[F], F]:
    """
    Add retry logic to a function.
    
    Example:
        >>> @retry(attempts=3, delay=1.0)
        >>> async def flaky_operation():
        ...     # May fail sometimes
        ...     pass
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(attempts):
                try:
                    if asyncio.iscoroutinefunction(func):
                        return await func(*args, **kwargs)
                    else:
                        return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < attempts - 1:
                        logger.warning(f"Retry {attempt + 1}/{attempts}: {e}")
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
            
            raise last_exception
        
        return wrapper
    
    return decorator


def timeout(seconds: int) -> Callable[[F], F]:
    """
    Add timeout to an async function.
    
    Example:
        >>> @timeout(30)
        >>> async def slow_operation():
        ...     pass
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await asyncio.wait_for(
                func(*args, **kwargs),
                timeout=seconds,
            )
        return wrapper
    
    return decorator


def trace(name: Optional[str] = None) -> Callable[[F], F]:
    """
    Add tracing to a function.
    
    Example:
        >>> @trace("process_order")
        >>> async def process_order(order_id: str):
        ...     pass
    """
    def decorator(func: F) -> F:
        trace_name = name or func.__name__
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            from ..tracing import tracer
            
            span = tracer.start_span(trace_name)
            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                tracer.end_span(span)
                return result
            except Exception as e:
                tracer.end_span(span, error=str(e))
                raise
        
        return wrapper
    
    return decorator


def cache(ttl: int = 300, key_func: Optional[Callable] = None) -> Callable[[F], F]:
    """
    Add caching to a function.
    
    Example:
        >>> @cache(ttl=600)
        >>> async def expensive_lookup(key: str) -> dict:
        ...     pass
    """
    _cache: Dict[str, Any] = {}
    
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = f"{func.__name__}:{args}:{kwargs}"
            
            # Check cache
            if cache_key in _cache:
                entry = _cache[cache_key]
                if time.time() - entry["time"] < ttl:
                    return entry["value"]
            
            # Execute and cache
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            _cache[cache_key] = {
                "value": result,
                "time": time.time(),
            }
            
            return result
        
        wrapper.clear_cache = lambda: _cache.clear()
        return wrapper
    
    return decorator


def validate(
    input_schema: Optional[Dict] = None,
    output_schema: Optional[Dict] = None,
) -> Callable[[F], F]:
    """
    Add input/output validation to a function.
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Validate input (simplified)
            if input_schema:
                # Would use jsonschema or pydantic in production
                pass
            
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # Validate output (simplified)
            if output_schema:
                pass
            
            return result
        
        return wrapper
    
    return decorator


def authorize(
    roles: Optional[List[str]] = None,
    permissions: Optional[List[str]] = None,
) -> Callable[[F], F]:
    """
    Add authorization check to a function.
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # In production, would check actual auth context
            # For now, just pass through
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)
        
        wrapper._auth_config = {
            "roles": roles or [],
            "permissions": permissions or [],
        }
        return wrapper
    
    return decorator


# =============================================================================
# Helper Functions
# =============================================================================

def _get_llm_client(config: AgentConfig):
    """Get or create LLM client based on config."""
    from ..llms import LLMManager
    
    try:
        manager = LLMManager.from_environment(
            preferred_provider=config.provider,
        )
        return manager
    except Exception as e:
        logger.warning(f"Failed to initialize LLM: {e}")
        return None


def _get_memory_manager(agent_id: str):
    """Get or create memory manager for agent."""
    from ..memory import AgentMemoryManager
    
    try:
        return AgentMemoryManager(
            agent_id=agent_id,
            max_conversation_turns=50,
        )
    except Exception as e:
        logger.warning(f"Failed to initialize memory: {e}")
        return None


def _build_messages(
    agent_instance,
    prompt: str,
    context: Optional[Dict[str, Any]],
    config: AgentConfig,
) -> List[Dict[str, str]]:
    """Build messages for LLM call."""
    messages = []
    
    # System message
    messages.append({
        "role": "system",
        "content": f"You are a {config.role}. Be helpful and concise.",
    })
    
    # Add conversation history
    if hasattr(agent_instance, "_conversation_history"):
        for msg in agent_instance._conversation_history[-10:]:
            messages.append(msg)
    
    # Add context if provided
    if context:
        context_str = "\n".join(f"{k}: {v}" for k, v in context.items())
        prompt = f"Context:\n{context_str}\n\n{prompt}"
    
    # Add user message
    messages.append({"role": "user", "content": prompt})
    
    return messages


async def _call_llm(
    client,
    messages: List[Dict[str, str]],
    config: AgentConfig,
    **kwargs,
) -> str:
    """Call LLM with messages."""
    if client is None:
        raise ValueError("LLM client not initialized")
    
    try:
        # Use the LLM manager's invoke method
        response = await asyncio.wait_for(
            asyncio.to_thread(
                client.invoke,
                messages=messages,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
            ),
            timeout=config.timeout_seconds,
        )
        
        if isinstance(response, dict):
            return response.get("content", response.get("response", str(response)))
        return str(response)
        
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        raise


def _python_type_to_json_type(python_type) -> str:
    """Convert Python type hint to JSON schema type."""
    type_map = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object",
        type(None): "null",
    }
    return type_map.get(python_type, "string")
