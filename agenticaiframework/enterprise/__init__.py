"""
Enterprise Module - Minimal Code Patterns for Production AI Applications.

This module provides enterprise-grade decorators, factories, and blueprints
that enable developers to create complete AI applications with minimal code.

Features:
- Decorators: @agent, @workflow, @tool, @guardrail, @pipeline
- Factories: AgentFactory, WorkflowFactory, SDLCFactory
- Blueprints: Pre-built agents for common SDLC phases
- Adapters: Unified interfaces for cloud providers
- Presets: Enterprise configurations for common scenarios

Quick Start:
    >>> from agenticaiframework.enterprise import create_sdlc_pipeline, agent, workflow
    >>> 
    >>> # Create complete SDLC pipeline in 3 lines
    >>> pipeline = create_sdlc_pipeline("my-project")
    >>> result = await pipeline.run("Build an e-commerce platform")
    >>> print(result.artifacts)
    
    >>> # Or use decorators for custom agents
    >>> @agent(role="analyst", model="gpt-4o")
    >>> class MyAnalyst:
    ...     async def analyze(self, data: str) -> dict:
    ...         return await self.invoke(f"Analyze: {data}")
"""

__version__ = "1.0.0"

# Decorators
from .decorators import (
    agent,
    workflow,
    tool,
    guardrail,
    pipeline,
    step,
    retry,
    timeout,
    trace,
    cache,
    validate,
    authorize,
)

# Factories
from .factories import (
    AgentFactory,
    WorkflowFactory,
    PipelineFactory,
    ToolFactory,
    create_agent,
    create_workflow,
    create_pipeline,
)

# Blueprints (Pre-built agents)
from .blueprints import (
    # SDLC Agents
    RequirementsAgent,
    DesignAgent,
    DevelopmentAgent,
    TestingAgent,
    SecurityAgent,
    DeploymentAgent,
    DocumentationAgent,
    ReviewAgent,
    # Other common agents
    AnalystAgent,
    ResearcherAgent,
    WriterAgent,
    # Blueprints helpers
    get_blueprint,
    list_blueprints,
)

# SDLC Pipeline (Complete solution)
from .sdlc import (
    SDLCPipeline,
    SDLCPhase,
    SDLCArtifact,
    SDLCConfig,
    SDLCResult,
    create_sdlc_pipeline,
)

# Adapters
from .adapters import (
    StorageAdapter,
    LLMAdapter,
    VectorDBAdapter,
    CacheAdapter,
    # Cloud-specific
    AzureAdapter,
    AWSAdapter,
    GCPAdapter,
    get_adapter,
)

# Presets
from .presets import (
    EnterprisePreset,
    StartupPreset,
    DevelopmentPreset,
    ProductionPreset,
    TestingPreset,
    MinimalPreset,
    load_preset,
    list_presets,
    auto_preset,
)

__all__ = [
    # Decorators
    "agent",
    "workflow",
    "tool",
    "guardrail",
    "pipeline",
    "step",
    "retry",
    "timeout",
    "trace",
    "cache",
    "validate",
    "authorize",
    # Factories
    "AgentFactory",
    "WorkflowFactory",
    "PipelineFactory",
    "ToolFactory",
    "create_agent",
    "create_workflow",
    "create_pipeline",
    # Blueprints
    "RequirementsAgent",
    "DesignAgent",
    "DevelopmentAgent",
    "TestingAgent",
    "SecurityAgent",
    "DeploymentAgent",
    "DocumentationAgent",
    "ReviewAgent",
    "AnalystAgent",
    "ResearcherAgent",
    "WriterAgent",
    "get_blueprint",
    "list_blueprints",
    # SDLC
    "SDLCPipeline",
    "SDLCPhase",
    "SDLCArtifact",
    "SDLCConfig",
    "SDLCResult",
    "create_sdlc_pipeline",
    # Adapters
    "StorageAdapter",
    "LLMAdapter",
    "VectorDBAdapter",
    "CacheAdapter",
    "AzureAdapter",
    "AWSAdapter",
    "GCPAdapter",
    "get_adapter",
    # Presets
    "EnterprisePreset",
    "StartupPreset",
    "DevelopmentPreset",
    "ProductionPreset",
    "TestingPreset",
    "MinimalPreset",
    "load_preset",
    "list_presets",
    "auto_preset",
]
