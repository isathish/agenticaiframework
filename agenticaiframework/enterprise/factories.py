"""
Enterprise Factories - One-liner creation of complex AI components.

Factory classes and functions that create fully-configured AI components
with minimal code.

Usage:
    >>> from agenticaiframework.enterprise import create_agent, create_pipeline
    >>> 
    >>> # One-liner agent creation
    >>> analyst = create_agent("analyst", model="gpt-4o")
    >>> 
    >>> # One-liner SDLC pipeline
    >>> pipeline = create_pipeline("sdlc", project="my-app")
    >>> result = await pipeline.run("Build an API server")
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, Union

logger = logging.getLogger(__name__)


# =============================================================================
# Factory Base
# =============================================================================

class FactoryRegistry:
    """Registry for all factory instances."""
    
    _agents: Dict[str, Type] = {}
    _workflows: Dict[str, Type] = {}
    _tools: Dict[str, Callable] = {}
    _pipelines: Dict[str, Type] = {}
    
    @classmethod
    def register_agent(cls, name: str, agent_class: Type):
        cls._agents[name.lower()] = agent_class
    
    @classmethod
    def register_workflow(cls, name: str, workflow_class: Type):
        cls._workflows[name.lower()] = workflow_class
    
    @classmethod
    def register_tool(cls, name: str, tool_func: Callable):
        cls._tools[name.lower()] = tool_func
    
    @classmethod
    def register_pipeline(cls, name: str, pipeline_class: Type):
        cls._pipelines[name.lower()] = pipeline_class
    
    @classmethod
    def get_agent(cls, name: str) -> Optional[Type]:
        return cls._agents.get(name.lower())
    
    @classmethod
    def get_workflow(cls, name: str) -> Optional[Type]:
        return cls._workflows.get(name.lower())
    
    @classmethod
    def get_tool(cls, name: str) -> Optional[Callable]:
        return cls._tools.get(name.lower())
    
    @classmethod
    def get_pipeline(cls, name: str) -> Optional[Type]:
        return cls._pipelines.get(name.lower())


# =============================================================================
# Agent Factory
# =============================================================================

class AgentFactory:
    """
    Factory for creating pre-configured agents.
    
    Usage:
        >>> # Create from template
        >>> analyst = AgentFactory.create("analyst")
        >>> 
        >>> # Create with custom config
        >>> agent = AgentFactory.create(
        ...     "custom",
        ...     role="data engineer",
        ...     model="gpt-4o",
        ...     tools=["sql_query", "chart_generator"],
        ... )
        >>> 
        >>> # Register custom template
        >>> AgentFactory.register("my_agent", MyAgentClass)
    """
    
    # Built-in agent templates
    TEMPLATES = {
        "assistant": {
            "role": "A helpful AI assistant",
            "model": "gpt-4o",
            "capabilities": ["chat", "reasoning"],
        },
        "analyst": {
            "role": "A data analyst that examines data and provides insights",
            "model": "gpt-4o",
            "capabilities": ["data-analysis", "visualization"],
        },
        "coder": {
            "role": "A programming expert that writes production-quality code",
            "model": "gpt-4o",
            "capabilities": ["code-generation", "debugging", "code-review"],
        },
        "researcher": {
            "role": "A research assistant that finds and synthesizes information",
            "model": "gpt-4o",
            "capabilities": ["search", "summarization"],
        },
        "writer": {
            "role": "A creative writer that produces engaging content",
            "model": "gpt-4o",
            "capabilities": ["writing", "editing"],
        },
        "reviewer": {
            "role": "A code/document reviewer that provides quality feedback",
            "model": "gpt-4o",
            "capabilities": ["review", "analysis"],
        },
        # SDLC specific
        "requirements": {
            "role": "A requirements analyst that extracts and organizes software requirements",
            "model": "gpt-4o",
            "capabilities": ["requirements-analysis", "user-stories"],
        },
        "design": {
            "role": "A software architect that designs systems and databases",
            "model": "gpt-4o",
            "capabilities": ["architecture", "database-design", "api-design"],
        },
        "development": {
            "role": "A senior developer that generates production-quality code",
            "model": "gpt-4o",
            "capabilities": ["code-generation", "refactoring"],
        },
        "testing": {
            "role": "A QA engineer that creates test strategies and test cases",
            "model": "gpt-4o",
            "capabilities": ["test-strategy", "test-generation"],
        },
        "security": {
            "role": "A security analyst that identifies vulnerabilities",
            "model": "gpt-4o",
            "capabilities": ["security-analysis", "vulnerability-detection"],
        },
        "deployment": {
            "role": "A DevOps engineer that handles deployment and infrastructure",
            "model": "gpt-4o",
            "capabilities": ["deployment", "infrastructure"],
        },
        "documentation": {
            "role": "A technical writer that creates comprehensive documentation",
            "model": "gpt-4o",
            "capabilities": ["documentation", "api-docs"],
        },
    }
    
    @classmethod
    def create(
        cls,
        template: str = "assistant",
        *,
        name: Optional[str] = None,
        role: Optional[str] = None,
        model: Optional[str] = None,
        provider: str = "azure",
        tools: Optional[List[str]] = None,
        guardrails: Optional[List[str]] = None,
        memory: bool = True,
        tracing: bool = True,
        **kwargs,
    ) -> Any:
        """
        Create an agent from a template or custom configuration.
        
        Args:
            template: Template name or "custom"
            name: Agent name (defaults to template name)
            role: Override role description
            model: Override model
            provider: LLM provider
            tools: Tool names to bind
            guardrails: Guardrail names to apply
            memory: Enable memory
            tracing: Enable tracing
            
        Returns:
            Configured agent instance
        """
        from ..core import Agent
        
        # Get template config
        template_config = cls.TEMPLATES.get(template.lower(), cls.TEMPLATES["assistant"])
        
        # Merge with overrides
        agent_name = name or template.title()
        agent_role = role or template_config["role"]
        agent_model = model or template_config["model"]
        capabilities = template_config.get("capabilities", ["general"])
        
        # Build config
        config = {
            "model": agent_model,
            "provider": provider,
            "tools": tools or [],
            "guardrails": guardrails or [],
            "memory": memory,
            "tracing": tracing,
            **kwargs,
        }
        
        # Create agent using quick factory
        agent = Agent.quick(
            name=agent_name,
            role=agent_role,
            llm=agent_model,
            provider=provider,
            tools=tools,
            guardrails=bool(guardrails),
            tracing=tracing,
        )
        
        logger.info(f"Created agent: {agent_name} (template={template})")
        return agent
    
    @classmethod
    def register(cls, name: str, agent_class: Type):
        """Register a custom agent template."""
        FactoryRegistry.register_agent(name, agent_class)
    
    @classmethod
    def list_templates(cls) -> List[str]:
        """List available templates."""
        return list(cls.TEMPLATES.keys())


# =============================================================================
# Workflow Factory
# =============================================================================

class WorkflowFactory:
    """
    Factory for creating pre-configured workflows.
    
    Usage:
        >>> # Create data pipeline
        >>> pipeline = WorkflowFactory.create("etl", source="db", target="warehouse")
        >>> 
        >>> # Create SDLC workflow
        >>> sdlc = WorkflowFactory.create("sdlc", project="my-app")
    """
    
    TEMPLATES = {
        "sequential": {
            "type": "sequential",
            "parallel": False,
        },
        "parallel": {
            "type": "parallel",
            "parallel": True,
        },
        "etl": {
            "type": "etl",
            "stages": ["extract", "transform", "load"],
            "parallel": False,
        },
        "sdlc": {
            "type": "sdlc",
            "stages": ["requirements", "design", "development", "testing", "deployment"],
            "parallel": False,
        },
        "review": {
            "type": "review",
            "stages": ["analyze", "review", "approve"],
            "parallel": False,
        },
    }
    
    @classmethod
    def create(
        cls,
        template: str = "sequential",
        *,
        name: Optional[str] = None,
        stages: Optional[List[str]] = None,
        parallel: Optional[bool] = None,
        save_artifacts: bool = True,
        **kwargs,
    ) -> Any:
        """
        Create a workflow from a template.
        
        Args:
            template: Template name
            name: Workflow name
            stages: Override stages
            parallel: Override parallel execution
            save_artifacts: Save intermediate artifacts
            
        Returns:
            Configured workflow instance
        """
        from ..workflows import SequentialWorkflow, ParallelWorkflow
        
        template_config = cls.TEMPLATES.get(template.lower(), cls.TEMPLATES["sequential"])
        
        workflow_name = name or f"{template}-workflow"
        is_parallel = parallel if parallel is not None else template_config.get("parallel", False)
        workflow_stages = stages or template_config.get("stages", [])
        
        # Create workflow
        WorkflowClass = ParallelWorkflow if is_parallel else SequentialWorkflow
        
        workflow = WorkflowClass(
            name=workflow_name,
            **kwargs,
        )
        
        # Store stages for reference
        workflow._factory_stages = workflow_stages
        
        logger.info(f"Created workflow: {workflow_name} (template={template})")
        return workflow
    
    @classmethod
    def register(cls, name: str, workflow_class: Type):
        """Register a custom workflow template."""
        FactoryRegistry.register_workflow(name, workflow_class)


# =============================================================================
# Pipeline Factory
# =============================================================================

class PipelineFactory:
    """
    Factory for creating complete pipelines.
    
    Usage:
        >>> # Create SDLC pipeline with all agents pre-configured
        >>> pipeline = PipelineFactory.create_sdlc(
        ...     project="e-commerce",
        ...     description="Build an online store",
        ... )
        >>> result = await pipeline.run()
    """
    
    @classmethod
    def create_sdlc(
        cls,
        project: str,
        description: str = "",
        *,
        phases: Optional[List[str]] = None,
        model: str = "gpt-4o",
        provider: str = "azure",
        storage: bool = True,
        tracing: bool = True,
        **kwargs,
    ):
        """
        Create a complete SDLC pipeline.
        
        Args:
            project: Project name
            description: Project description
            phases: SDLC phases to include
            model: LLM model for all agents
            provider: LLM provider
            storage: Enable artifact storage
            tracing: Enable tracing
            
        Returns:
            Configured SDLC pipeline
        """
        from .sdlc import SDLCPipeline
        
        default_phases = [
            "requirements",
            "design", 
            "development",
            "testing",
            "security",
            "deployment",
            "documentation",
        ]
        
        pipeline = SDLCPipeline(
            project_name=project,
            description=description,
            phases=phases or default_phases,
            model=model,
            provider=provider,
            enable_storage=storage,
            enable_tracing=tracing,
            **kwargs,
        )
        
        logger.info(f"Created SDLC pipeline: {project}")
        return pipeline
    
    @classmethod
    def create_data_pipeline(
        cls,
        name: str,
        *,
        source: str,
        target: str,
        transformations: Optional[List[str]] = None,
        **kwargs,
    ):
        """Create a data processing pipeline."""
        # Simplified implementation
        return WorkflowFactory.create(
            "etl",
            name=name,
            source=source,
            target=target,
            **kwargs,
        )
    
    @classmethod
    def create_review_pipeline(
        cls,
        name: str,
        *,
        reviewers: int = 2,
        auto_approve: bool = False,
        **kwargs,
    ):
        """Create a code review pipeline."""
        return WorkflowFactory.create(
            "review",
            name=name,
            reviewers=reviewers,
            auto_approve=auto_approve,
            **kwargs,
        )


# =============================================================================
# Tool Factory
# =============================================================================

class ToolFactory:
    """
    Factory for creating and discovering tools.
    
    Usage:
        >>> # Create a tool
        >>> search_tool = ToolFactory.create("web_search")
        >>> 
        >>> # Create from function
        >>> my_tool = ToolFactory.from_function(my_function, name="my_tool")
    """
    
    BUILTIN_TOOLS = {
        "web_search": {
            "description": "Search the web for information",
            "parameters": {"query": "string"},
        },
        "calculator": {
            "description": "Perform mathematical calculations",
            "parameters": {"expression": "string"},
        },
        "file_read": {
            "description": "Read file contents",
            "parameters": {"path": "string"},
        },
        "file_write": {
            "description": "Write content to a file",
            "parameters": {"path": "string", "content": "string"},
        },
        "http_request": {
            "description": "Make HTTP requests",
            "parameters": {"url": "string", "method": "string"},
        },
        "sql_query": {
            "description": "Execute SQL queries",
            "parameters": {"query": "string", "database": "string"},
        },
    }
    
    @classmethod
    def create(
        cls,
        name: str,
        *,
        description: Optional[str] = None,
        implementation: Optional[Callable] = None,
        **kwargs,
    ) -> Callable:
        """
        Create a tool by name.
        
        Args:
            name: Tool name (built-in or registered)
            description: Override description
            implementation: Custom implementation
            
        Returns:
            Tool function
        """
        from .decorators import tool
        
        # Check if it's a builtin tool
        tool_config = cls.BUILTIN_TOOLS.get(name.lower())
        
        if tool_config and implementation:
            # Wrap custom implementation with tool decorator
            @tool(
                name=name,
                description=description or tool_config["description"],
            )
            async def wrapped(*args, **kw):
                return await implementation(*args, **kw) if asyncio.iscoroutinefunction(implementation) else implementation(*args, **kw)
            return wrapped
        
        # Return placeholder if no implementation
        @tool(
            name=name,
            description=description or f"Tool: {name}",
        )
        async def placeholder_tool(*args, **kw):
            raise NotImplementedError(f"Tool {name} requires an implementation")
        
        return placeholder_tool
    
    @classmethod
    def from_function(
        cls,
        func: Callable,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Callable:
        """
        Create a tool from an existing function.
        
        Args:
            func: Function to wrap
            name: Tool name
            description: Tool description
            
        Returns:
            Tool function
        """
        from .decorators import tool
        
        @tool(
            name=name or func.__name__,
            description=description or func.__doc__ or "",
        )
        async def wrapped(*args, **kwargs):
            import asyncio
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            return func(*args, **kwargs)
        
        return wrapped
    
    @classmethod
    def register(cls, name: str, tool_func: Callable):
        """Register a custom tool."""
        FactoryRegistry.register_tool(name, tool_func)


# =============================================================================
# Convenience Functions
# =============================================================================

def create_agent(
    template: str = "assistant",
    **kwargs,
) -> Any:
    """
    Create an agent with one line.
    
    Args:
        template: Agent template name
        **kwargs: Additional configuration
        
    Returns:
        Configured agent
        
    Example:
        >>> analyst = create_agent("analyst", model="gpt-4o")
        >>> coder = create_agent("coder", tools=["github"])
    """
    return AgentFactory.create(template, **kwargs)


def create_workflow(
    template: str = "sequential",
    **kwargs,
) -> Any:
    """
    Create a workflow with one line.
    
    Args:
        template: Workflow template name
        **kwargs: Additional configuration
        
    Returns:
        Configured workflow
        
    Example:
        >>> pipeline = create_workflow("etl", stages=["extract", "transform", "load"])
    """
    return WorkflowFactory.create(template, **kwargs)


def create_pipeline(
    pipeline_type: str = "sdlc",
    **kwargs,
) -> Any:
    """
    Create a pipeline with one line.
    
    Args:
        pipeline_type: Pipeline type (sdlc, data, review)
        **kwargs: Additional configuration
        
    Returns:
        Configured pipeline
        
    Example:
        >>> sdlc = create_pipeline("sdlc", project="my-app")
        >>> result = await sdlc.run("Build an API server")
    """
    if pipeline_type.lower() == "sdlc":
        return PipelineFactory.create_sdlc(**kwargs)
    elif pipeline_type.lower() == "data":
        return PipelineFactory.create_data_pipeline(**kwargs)
    elif pipeline_type.lower() == "review":
        return PipelineFactory.create_review_pipeline(**kwargs)
    else:
        # Default to workflow factory
        return WorkflowFactory.create(pipeline_type, **kwargs)


# Import asyncio for type checking in ToolFactory
import asyncio
