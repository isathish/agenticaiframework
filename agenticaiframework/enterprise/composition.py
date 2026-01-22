"""
Enterprise Agent Composition - Reusable agent components.

Provides composable agent building blocks that can be
combined to create complex multi-agent systems.

Features:
- Component-based agents
- Mixins and traits
- Agent pipelines
- Dynamic composition
- Hot swapping
"""

import asyncio
import functools
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import (
    Any, Callable, Dict, Generic, List, Optional, 
    Set, Type, TypeVar, Union,
)
import uuid

logger = logging.getLogger(__name__)


# =============================================================================
# Types
# =============================================================================

T = TypeVar("T")
R = TypeVar("R")
AgentT = TypeVar("AgentT", bound="ComposableAgent")


# =============================================================================
# Component Base
# =============================================================================

class ComponentStatus(Enum):
    """Status of a component."""
    INACTIVE = "inactive"
    ACTIVE = "active"
    ERROR = "error"
    DISABLED = "disabled"


@dataclass
class ComponentMetadata:
    """Metadata for a component."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    tags: List[str] = field(default_factory=list)


class Component(ABC):
    """
    Base class for composable components.
    
    Usage:
        >>> class MyComponent(Component):
        ...     async def process(self, input: str) -> str:
        ...         return f"Processed: {input}"
    """
    
    def __init__(self, name: str = None):
        self.metadata = ComponentMetadata(name=name or self.__class__.__name__)
        self.status = ComponentStatus.INACTIVE
        self._initialized = False
    
    async def initialize(self):
        """Initialize the component."""
        self._initialized = True
        self.status = ComponentStatus.ACTIVE
    
    async def shutdown(self):
        """Shutdown the component."""
        self._initialized = False
        self.status = ComponentStatus.INACTIVE
    
    @abstractmethod
    async def process(self, input: Any) -> Any:
        """Process input and return output."""
        pass
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.metadata.name})"


# =============================================================================
# Traits/Mixins
# =============================================================================

class MemoryTrait:
    """Mixin that adds memory to an agent."""
    
    _memory: List[Dict[str, Any]]
    _memory_limit: int
    
    def init_memory(self, limit: int = 100):
        """Initialize memory."""
        self._memory = []
        self._memory_limit = limit
    
    def remember(self, key: str, value: Any):
        """Store a memory."""
        self._memory.append({
            "key": key,
            "value": value,
            "timestamp": datetime.now(),
        })
        
        if len(self._memory) > self._memory_limit:
            self._memory = self._memory[-self._memory_limit:]
    
    def recall(self, key: str = None) -> List[Any]:
        """Recall memories."""
        if key:
            return [m["value"] for m in self._memory if m["key"] == key]
        return [m["value"] for m in self._memory]
    
    def forget(self, key: str = None):
        """Forget memories."""
        if key:
            self._memory = [m for m in self._memory if m["key"] != key]
        else:
            self._memory = []


class ToolsTrait:
    """Mixin that adds tools to an agent."""
    
    _tools: Dict[str, Callable]
    
    def init_tools(self):
        """Initialize tools."""
        self._tools = {}
    
    def register_tool(self, name: str, func: Callable):
        """Register a tool."""
        self._tools[name] = func
    
    def get_tool(self, name: str) -> Optional[Callable]:
        """Get a tool by name."""
        return self._tools.get(name)
    
    async def call_tool(self, name: str, **kwargs) -> Any:
        """Call a tool."""
        tool = self._tools.get(name)
        if not tool:
            raise ValueError(f"Tool not found: {name}")
        
        if asyncio.iscoroutinefunction(tool):
            return await tool(**kwargs)
        return tool(**kwargs)
    
    @property
    def available_tools(self) -> List[str]:
        """List available tools."""
        return list(self._tools.keys())


class ObservableTrait:
    """Mixin that adds observability to an agent."""
    
    _observers: List[Callable]
    _events: List[Dict[str, Any]]
    
    def init_observable(self):
        """Initialize observability."""
        self._observers = []
        self._events = []
    
    def add_observer(self, callback: Callable):
        """Add an observer."""
        self._observers.append(callback)
    
    def remove_observer(self, callback: Callable):
        """Remove an observer."""
        if callback in self._observers:
            self._observers.remove(callback)
    
    async def emit(self, event_type: str, data: Any = None):
        """Emit an event to observers."""
        event = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.now(),
        }
        
        self._events.append(event)
        
        for observer in self._observers:
            try:
                if asyncio.iscoroutinefunction(observer):
                    await observer(event)
                else:
                    observer(event)
            except Exception as e:
                logger.error(f"Observer error: {e}")


class ReflectionTrait:
    """Mixin that adds self-reflection to an agent."""
    
    _reflections: List[str]
    
    def init_reflection(self):
        """Initialize reflection."""
        self._reflections = []
    
    async def reflect(self, context: str) -> str:
        """Reflect on the current state/context."""
        reflection = f"Reflecting on: {context}"
        self._reflections.append(reflection)
        return reflection
    
    def get_reflections(self) -> List[str]:
        """Get all reflections."""
        return list(self._reflections)


# =============================================================================
# Composable Agent
# =============================================================================

class ComposableAgent(Component):
    """
    Base class for composable agents.
    
    Usage:
        >>> class MyAgent(ComposableAgent, MemoryTrait, ToolsTrait):
        ...     def __init__(self):
        ...         super().__init__("my-agent")
        ...         self.init_memory()
        ...         self.init_tools()
        ...     
        ...     async def process(self, input: str) -> str:
        ...         self.remember("input", input)
        ...         return f"Result: {input}"
    """
    
    def __init__(self, name: str = None, **config):
        super().__init__(name)
        self.config = config
        self._components: Dict[str, Component] = {}
        self._pipeline: List[str] = []
    
    def add_component(self, name: str, component: Component) -> "ComposableAgent":
        """Add a sub-component."""
        self._components[name] = component
        return self
    
    def remove_component(self, name: str) -> "ComposableAgent":
        """Remove a sub-component."""
        if name in self._components:
            del self._components[name]
        return self
    
    def get_component(self, name: str) -> Optional[Component]:
        """Get a sub-component."""
        return self._components.get(name)
    
    def set_pipeline(self, *component_names: str) -> "ComposableAgent":
        """Set the processing pipeline."""
        self._pipeline = list(component_names)
        return self
    
    async def process(self, input: Any) -> Any:
        """Process through the component pipeline."""
        result = input
        
        for name in self._pipeline:
            component = self._components.get(name)
            if component:
                result = await component.process(result)
        
        return result
    
    async def process_with(self, input: Any, *component_names: str) -> Any:
        """Process through specific components."""
        result = input
        
        for name in component_names:
            component = self._components.get(name)
            if component:
                result = await component.process(result)
        
        return result


# =============================================================================
# Pre-built Components
# =============================================================================

class InputValidator(Component):
    """Component that validates input."""
    
    def __init__(self, schema: Dict[str, Any] = None):
        super().__init__("validator")
        self.schema = schema or {}
    
    async def process(self, input: Any) -> Any:
        """Validate and pass through input."""
        # Simple validation
        if self.schema.get("required") and not input:
            raise ValueError("Input is required")
        
        if self.schema.get("type") == "str" and not isinstance(input, str):
            raise TypeError("Input must be a string")
        
        return input


class OutputFormatter(Component):
    """Component that formats output."""
    
    def __init__(self, format: str = "text"):
        super().__init__("formatter")
        self.format = format
    
    async def process(self, input: Any) -> Any:
        """Format output."""
        if self.format == "json":
            import json
            return json.dumps(input, indent=2, default=str)
        elif self.format == "uppercase":
            return str(input).upper()
        elif self.format == "markdown":
            return f"```\n{input}\n```"
        
        return str(input)


class LoggingComponent(Component):
    """Component that logs input/output."""
    
    def __init__(self, log_input: bool = True, log_output: bool = True):
        super().__init__("logger")
        self.log_input = log_input
        self.log_output = log_output
    
    async def process(self, input: Any) -> Any:
        if self.log_input:
            logger.info(f"Input: {input}")
        
        output = input  # Pass through
        
        if self.log_output:
            logger.info(f"Output: {output}")
        
        return output


class TransformComponent(Component):
    """Component that transforms data."""
    
    def __init__(self, transform_func: Callable):
        super().__init__("transform")
        self._transform = transform_func
    
    async def process(self, input: Any) -> Any:
        if asyncio.iscoroutinefunction(self._transform):
            return await self._transform(input)
        return self._transform(input)


class FilterComponent(Component):
    """Component that filters data."""
    
    def __init__(self, predicate: Callable[[Any], bool]):
        super().__init__("filter")
        self._predicate = predicate
    
    async def process(self, input: Any) -> Any:
        if asyncio.iscoroutinefunction(self._predicate):
            should_pass = await self._predicate(input)
        else:
            should_pass = self._predicate(input)
        
        if should_pass:
            return input
        return None


class CacheComponent(Component):
    """Component that caches results."""
    
    def __init__(self, ttl_seconds: int = 300):
        super().__init__("cache")
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, tuple] = {}
    
    async def process(self, input: Any) -> Any:
        import hashlib
        
        key = hashlib.sha256(str(input).encode()).hexdigest()
        
        if key in self._cache:
            value, timestamp = self._cache[key]
            if (datetime.now() - timestamp).total_seconds() < self.ttl_seconds:
                return value
        
        # Cache miss - return None to indicate processing needed
        return None
    
    def store(self, input: Any, output: Any):
        """Store result in cache."""
        import hashlib
        key = hashlib.sha256(str(input).encode()).hexdigest()
        self._cache[key] = (output, datetime.now())


# =============================================================================
# Agent Pipeline
# =============================================================================

class AgentPipeline:
    """
    Pipeline of agents that process sequentially.
    
    Usage:
        >>> pipeline = (
        ...     AgentPipeline()
        ...     .add(analyzer)
        ...     .add(reviewer)
        ...     .add(formatter)
        ... )
        >>> result = await pipeline.run("input data")
    """
    
    def __init__(self, name: str = "pipeline"):
        self.name = name
        self._agents: List[ComposableAgent] = []
        self._error_handler: Optional[Callable] = None
    
    def add(self, agent: ComposableAgent) -> "AgentPipeline":
        """Add an agent to the pipeline."""
        self._agents.append(agent)
        return self
    
    def on_error(self, handler: Callable) -> "AgentPipeline":
        """Set error handler."""
        self._error_handler = handler
        return self
    
    async def run(self, input: Any) -> Any:
        """Run the pipeline."""
        result = input
        
        for agent in self._agents:
            try:
                result = await agent.process(result)
            except Exception as e:
                if self._error_handler:
                    result = await self._error_handler(e, result, agent)
                else:
                    raise
        
        return result
    
    async def run_parallel(self, input: Any) -> List[Any]:
        """Run all agents in parallel with same input."""
        tasks = [agent.process(input) for agent in self._agents]
        return await asyncio.gather(*tasks)


# =============================================================================
# Agent Factory with Composition
# =============================================================================

class ComposableAgentFactory:
    """
    Factory for creating composed agents.
    
    Usage:
        >>> factory = ComposableAgentFactory()
        >>> 
        >>> agent = factory.create("my-agent") \\
        ...     .with_memory(limit=100) \\
        ...     .with_tools({"search": search_func}) \\
        ...     .with_component("validator", InputValidator()) \\
        ...     .build()
    """
    
    def create(self, name: str) -> "AgentBuilder":
        """Create a new agent builder."""
        return AgentBuilder(name)


class AgentBuilder:
    """Builder for composable agents."""
    
    def __init__(self, name: str):
        self._name = name
        self._memory_limit: Optional[int] = None
        self._tools: Dict[str, Callable] = {}
        self._components: Dict[str, Component] = {}
        self._pipeline: List[str] = []
        self._config: Dict[str, Any] = {}
        self._base_class: Type = ComposableAgent
        self._mixins: List[Type] = []
    
    def with_memory(self, limit: int = 100) -> "AgentBuilder":
        """Add memory trait."""
        self._memory_limit = limit
        if MemoryTrait not in self._mixins:
            self._mixins.append(MemoryTrait)
        return self
    
    def with_tools(self, tools: Dict[str, Callable]) -> "AgentBuilder":
        """Add tools trait with tools."""
        self._tools = tools
        if ToolsTrait not in self._mixins:
            self._mixins.append(ToolsTrait)
        return self
    
    def with_observable(self) -> "AgentBuilder":
        """Add observable trait."""
        if ObservableTrait not in self._mixins:
            self._mixins.append(ObservableTrait)
        return self
    
    def with_reflection(self) -> "AgentBuilder":
        """Add reflection trait."""
        if ReflectionTrait not in self._mixins:
            self._mixins.append(ReflectionTrait)
        return self
    
    def with_component(self, name: str, component: Component) -> "AgentBuilder":
        """Add a component."""
        self._components[name] = component
        return self
    
    def with_pipeline(self, *component_names: str) -> "AgentBuilder":
        """Set the pipeline."""
        self._pipeline = list(component_names)
        return self
    
    def with_config(self, **config) -> "AgentBuilder":
        """Add configuration."""
        self._config.update(config)
        return self
    
    def build(self) -> ComposableAgent:
        """Build the composed agent."""
        # Create dynamic class with mixins
        bases = tuple([self._base_class] + self._mixins)
        
        class ComposedAgent(*bases):
            pass
        
        # Create instance
        agent = ComposedAgent(self._name, **self._config)
        
        # Initialize traits
        if MemoryTrait in self._mixins:
            agent.init_memory(self._memory_limit or 100)
        
        if ToolsTrait in self._mixins:
            agent.init_tools()
            for name, func in self._tools.items():
                agent.register_tool(name, func)
        
        if ObservableTrait in self._mixins:
            agent.init_observable()
        
        if ReflectionTrait in self._mixins:
            agent.init_reflection()
        
        # Add components
        for name, component in self._components.items():
            agent.add_component(name, component)
        
        # Set pipeline
        if self._pipeline:
            agent.set_pipeline(*self._pipeline)
        
        return agent


# =============================================================================
# Decorators
# =============================================================================

def component(name: str = None):
    """
    Decorator to create a component from a function.
    
    Usage:
        >>> @component("preprocessor")
        ... async def preprocess(input: str) -> str:
        ...     return input.strip().lower()
    """
    def decorator(func: Callable) -> Component:
        class FunctionComponent(Component):
            async def process(self, input: Any) -> Any:
                if asyncio.iscoroutinefunction(func):
                    return await func(input)
                return func(input)
        
        return FunctionComponent(name or func.__name__)
    
    return decorator


def composable(**traits):
    """
    Decorator to create a composable agent class.
    
    Usage:
        >>> @composable(memory=True, tools=True)
        ... class MyAgent(ComposableAgent):
        ...     async def process(self, input):
        ...         return f"Result: {input}"
    """
    def decorator(cls: Type[ComposableAgent]) -> Type[ComposableAgent]:
        original_init = cls.__init__
        
        @functools.wraps(original_init)
        def new_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            
            if traits.get("memory"):
                MemoryTrait.init_memory(self, traits.get("memory_limit", 100))
            
            if traits.get("tools"):
                ToolsTrait.init_tools(self)
            
            if traits.get("observable"):
                ObservableTrait.init_observable(self)
            
            if traits.get("reflection"):
                ReflectionTrait.init_reflection(self)
        
        cls.__init__ = new_init
        
        # Add trait methods
        if traits.get("memory"):
            for method in ["remember", "recall", "forget"]:
                setattr(cls, method, getattr(MemoryTrait, method))
        
        if traits.get("tools"):
            for method in ["register_tool", "get_tool", "call_tool", "available_tools"]:
                attr = getattr(ToolsTrait, method)
                if isinstance(attr, property):
                    setattr(cls, method, attr)
                else:
                    setattr(cls, method, attr)
        
        return cls
    
    return decorator


# =============================================================================
# Helper Functions
# =============================================================================

def create_pipeline(*agents: ComposableAgent, name: str = "pipeline") -> AgentPipeline:
    """Create a pipeline from agents."""
    pipeline = AgentPipeline(name)
    for agent in agents:
        pipeline.add(agent)
    return pipeline


def compose(*components: Component) -> ComposableAgent:
    """Compose components into an agent."""
    agent = ComposableAgent("composed")
    
    for i, comp in enumerate(components):
        name = comp.metadata.name or f"component_{i}"
        agent.add_component(name, comp)
        agent._pipeline.append(name)
    
    return agent
