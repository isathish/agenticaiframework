"""
AgenticAI Python Package
Fully functional implementation of the Agentic Framework as described.

Enterprise Features:
- Agent Step Tracing & Latency Metrics
- Offline/Online Evaluation
- Cost vs Quality Scoring
- Security Risk Scoring
- Prompt Versioning
- Agent CI Pipelines
- Canary/A/B Testing
- Agent Builder UI API
- Workflow Designer API
- Admin Console API
- ITSM Integration (ServiceNow)
- Dev Tools (GitHub, Azure DevOps)
- Serverless Execution
- Multi-Region Support
- Tenant Isolation
- Audit Trails
- Policy Enforcement
- Data Masking
"""

# Core components
from .agents import Agent, AgentManager, ContextManager
from .prompts import Prompt, PromptManager
from .processes import Process
from .tasks import Task, TaskManager
from .mcp_tools import MCPTool, MCPToolManager
from .monitoring import MonitoringSystem
from .guardrails import Guardrail, GuardrailManager
from .evaluation import EvaluationSystem
from .knowledge import KnowledgeRetriever
from .llms import LLMManager, CircuitBreaker
from .communication import CommunicationManager
from .memory import MemoryManager, MemoryEntry
from .hub import Hub
from .configurations import ConfigurationManager

# Security components
from .security import (
    PromptInjectionDetector,
    InputValidator,
    RateLimiter,
    ContentFilter,
    AuditLogger,
    SecurityManager
)

# Enterprise: Tracing & Metrics
from .tracing import (
    AgentStepTracer,
    LatencyMetrics,
    Span,
    SpanContext,
    tracer,
    latency_metrics
)

# Enterprise: Advanced Evaluation
from .evaluation_advanced import (
    OfflineEvaluator,
    OnlineEvaluator,
    CostQualityScorer,
    SecurityRiskScorer,
    ABTestingFramework,
    EvaluationType,
    EvaluationResult,
    # New comprehensive evaluation types
    ModelQualityEvaluator,
    TaskEvaluator,
    ToolInvocationEvaluator,
    WorkflowEvaluator,
    MemoryEvaluator,
    RAGEvaluator,
    AutonomyEvaluator,
    PerformanceEvaluator,
    HITLEvaluator,
    BusinessOutcomeEvaluator
)

# Enterprise: Prompt Versioning
from .prompt_versioning import (
    PromptVersionManager,
    PromptLibrary,
    PromptVersion,
    PromptStatus,
    prompt_version_manager,
    prompt_library
)

# Enterprise: CI/CD
from .ci_cd import (
    AgentCIPipeline,
    AgentTestRunner,
    DeploymentManager,
    ReleaseManager,
    PipelineStage,
    PipelineStatus,
    StageType,
    create_agent_pipeline,
    test_runner,
    deployment_manager,
    release_manager
)

# Enterprise: Infrastructure
from .infrastructure import (
    MultiRegionManager,
    TenantManager,
    ServerlessExecutor,
    DistributedCoordinator,
    Region,
    Tenant,
    multi_region_manager,
    tenant_manager,
    serverless_executor,
    distributed_coordinator
)

# Enterprise: Compliance & Governance
from .compliance import (
    AuditTrailManager,
    PolicyEngine,
    DataMaskingEngine,
    AuditEvent,
    AuditEventType,
    AuditSeverity,
    Policy,
    PolicyType,
    MaskingRule,
    MaskingType,
    audit_trail,
    policy_engine,
    data_masking,
    audit_action,
    enforce_policy,
    mask_output
)

# Enterprise: Integrations
from .integrations import (
    IntegrationManager,
    WebhookManager,
    ServiceNowIntegration,
    GitHubIntegration,
    AzureDevOpsIntegration,
    SnowflakeConnector,
    DatabricksConnector,
    IntegrationConfig,
    IntegrationStatus,
    integration_manager,
    webhook_manager
)

# Enterprise: Visual Tools
from .visual_tools import (
    AgentBuilder,
    WorkflowDesigner,
    AdminConsole,
    ComponentType,
    ComponentDefinition,
    AgentBlueprint,
    WorkflowNode,
    WorkflowEdge,
    WorkflowDefinition,
    NodeType,
    agent_builder,
    workflow_designer,
    admin_console
)

# Exceptions
from .exceptions import (
    # Base exception
    AgenticAIError,
    # Circuit breaker exceptions
    CircuitBreakerError,
    CircuitBreakerOpenError,
    # Rate limiting exceptions
    RateLimitError,
    RateLimitExceededError,
    # Security exceptions
    SecurityError,
    InjectionDetectedError,
    ContentFilteredError,
    # Validation exceptions
    ValidationError,
    GuardrailViolationError,
    PromptRenderError,
    # Task exceptions
    TaskError,
    TaskExecutionError,
    TaskNotFoundError,
    # Agent exceptions
    AgentError,
    AgentNotFoundError,
    AgentExecutionError,
    # LLM exceptions
    LLMError,
    ModelNotFoundError,
    ModelInferenceError,
    # Memory exceptions
    AgenticMemoryError,
    MemoryExportError,
    # Knowledge exceptions
    KnowledgeError,
    KnowledgeRetrievalError,
    # Communication exceptions
    CommunicationError,
    ProtocolError,
    ProtocolNotFoundError,
    # Evaluation exceptions
    EvaluationError,
    CriterionEvaluationError,
)

__all__ = [
    # ========================================================================
    # Core Components
    # ========================================================================
    "Agent", "AgentManager", "ContextManager",
    "Prompt", "PromptManager",
    "Process",
    "Task", "TaskManager",
    "MCPTool", "MCPToolManager",
    "MonitoringSystem",
    "Guardrail", "GuardrailManager",
    "EvaluationSystem",
    "KnowledgeRetriever",
    "LLMManager", "CircuitBreaker",
    "CommunicationManager",
    "MemoryManager", "MemoryEntry",
    "Hub",
    "ConfigurationManager",
    
    # ========================================================================
    # Security Components
    # ========================================================================
    "PromptInjectionDetector",
    "InputValidator",
    "RateLimiter",
    "ContentFilter",
    "AuditLogger",
    "SecurityManager",
    
    # ========================================================================
    # Enterprise: Tracing & Metrics
    # ========================================================================
    "AgentStepTracer",
    "LatencyMetrics",
    "Span",
    "SpanContext",
    "tracer",
    "latency_metrics",
    
    # ========================================================================
    # Enterprise: Advanced Evaluation
    # ========================================================================
    "OfflineEvaluator",
    "OnlineEvaluator",
    "CostQualityScorer",
    "SecurityRiskScorer",
    "ABTestingFramework",
    "EvaluationType",
    "EvaluationResult",
    # Comprehensive 12-Tier Evaluation Framework
    "ModelQualityEvaluator",           # Level 1: Model-level quality assessment
    "TaskEvaluator",                   # Level 2: Task/skill-level evaluation
    "ToolInvocationEvaluator",         # Level 3: Tool & API invocation tracking
    "WorkflowEvaluator",               # Level 4: Workflow orchestration
    "MemoryEvaluator",                 # Level 5: Memory & context evaluation
    "RAGEvaluator",                    # Level 6: RAG (Retrieval-Augmented Generation)
    "AutonomyEvaluator",               # Level 7-8: Autonomy & planning
    "PerformanceEvaluator",            # Level 9: Performance & scalability
    "HITLEvaluator",                   # Level 11: Human-in-the-loop
    "BusinessOutcomeEvaluator",        # Level 12: Business outcomes & ROI
    # Supporting evaluation classes
    "CanaryDeploymentManager",
    
    # ========================================================================
    # Enterprise: Prompt Versioning
    # ========================================================================
    "PromptVersionManager",
    "PromptLibrary",
    "PromptVersion",
    "PromptStatus",
    "prompt_version_manager",
    "prompt_library",
    
    # ========================================================================
    # Enterprise: CI/CD
    # ========================================================================
    "AgentCIPipeline",
    "AgentTestRunner",
    "DeploymentManager",
    "ReleaseManager",
    "PipelineStage",
    "PipelineStatus",
    "StageType",
    "create_agent_pipeline",
    "test_runner",
    "deployment_manager",
    "release_manager",
    
    # ========================================================================
    # Enterprise: Infrastructure
    # ========================================================================
    "MultiRegionManager",
    "TenantManager",
    "ServerlessExecutor",
    "DistributedCoordinator",
    "Region",
    "Tenant",
    "multi_region_manager",
    "tenant_manager",
    "serverless_executor",
    "distributed_coordinator",
    
    # ========================================================================
    # Enterprise: Compliance & Governance
    # ========================================================================
    "AuditTrailManager",
    "PolicyEngine",
    "DataMaskingEngine",
    "AuditEvent",
    "AuditEventType",
    "AuditSeverity",
    "Policy",
    "PolicyType",
    "MaskingRule",
    "MaskingType",
    "audit_trail",
    "policy_engine",
    "data_masking",
    "audit_action",
    "enforce_policy",
    "mask_output",
    
    # ========================================================================
    # Enterprise: Integrations
    # ========================================================================
    "IntegrationManager",
    "WebhookManager",
    "ServiceNowIntegration",
    "GitHubIntegration",
    "AzureDevOpsIntegration",
    "SnowflakeConnector",
    "DatabricksConnector",
    "IntegrationConfig",
    "IntegrationStatus",
    "integration_manager",
    "webhook_manager",
    
    # ========================================================================
    # Enterprise: Visual Tools
    # ========================================================================
    "AgentBuilder",
    "WorkflowDesigner",
    "AdminConsole",
    "ComponentType",
    "ComponentDefinition",
    "AgentBlueprint",
    "WorkflowNode",
    "WorkflowEdge",
    "WorkflowDefinition",
    "NodeType",
    "agent_builder",
    "workflow_designer",
    "admin_console",
    
    # ========================================================================
    # Exceptions
    # ========================================================================
    # Base
    "AgenticAIError",
    # Circuit breaker
    "CircuitBreakerError",
    "CircuitBreakerOpenError",
    # Rate limiting
    "RateLimitError",
    "RateLimitExceededError",
    # Security
    "SecurityError",
    "InjectionDetectedError",
    "ContentFilteredError",
    # Validation
    "ValidationError",
    "GuardrailViolationError",
    "PromptRenderError",
    # Task
    "TaskError",
    "TaskExecutionError",
    "TaskNotFoundError",
    # Agent
    "AgentError",
    "AgentNotFoundError",
    "AgentExecutionError",
    # LLM
    "LLMError",
    "ModelNotFoundError",
    "ModelInferenceError",
    # Memory
    "AgenticMemoryError",
    "MemoryExportError",
    # Knowledge
    "KnowledgeError",
    "KnowledgeRetrievalError",
    # Communication
    "CommunicationError",
    "ProtocolError",
    "ProtocolNotFoundError",
    # Evaluation
    "EvaluationError",
    "CriterionEvaluationError",
]
