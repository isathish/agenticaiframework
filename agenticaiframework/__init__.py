"""
AgenticAI Python Package
Fully functional implementation of the Agentic Framework as described.

Enterprise Features:
- Agent Step Tracing & Latency Metrics
- Offline/Online Evaluation
- Cost vs Quality Scoring
- Security Risk Scoring
- Prompt Versioning
- Canary/A/B Testing
- ITSM Integration (ServiceNow)
- Dev Tools (GitHub, Azure DevOps)
- Serverless Execution
- Multi-Region Support
- Tenant Isolation
- Audit Trails
- Policy Enforcement
- Data Masking

Quick Start:
    >>> import agenticaiframework as aaf
    >>> 
    >>> # Configure once at startup (optional - auto-configures from env)
    >>> aaf.configure(provider="openai", guardrails="minimal")
    >>> 
    >>> # Create agent with one line
    >>> agent = aaf.Agent.quick("Assistant")
    >>> 
    >>> # Run with structured output
    >>> output = agent.invoke("Hello, world!")
    >>> print(output.response)
"""

__version__ = "1.2.16"
__author__ = "AgenticAI Framework Contributors"
__license__ = "MIT"

# Global configuration (import first)
from .config import (
    FrameworkConfig,
    configure,
    get_config,
    is_configured,
    reset_config,
)

# Core components (modular imports)
from .core import (
    Agent,
    AgentManager,
    AgentInput,
    AgentOutput,
    AgentStep,
    AgentThought,
    AgentStatus,
    StepType,
    AgentRunner,
)

# ACE - Agentic Context Engine (modular imports)
from .context import (
    ContextManager,
    ContextType,
    ContextPriority,
    ContextRetrievalStrategy,
    ContextItem,
    SemanticContextIndex,
    ContextWindow,
    ContextCompressionStrategy
)

# Agent Orchestration Framework (modular imports)
from .orchestration import (
    OrchestrationPattern,
    SupervisionStrategy,
    AgentRole,
    AgentState,
    TaskAssignment,
    AgentHandoff,
    SupervisionConfig,
    AgentSupervisor,
    TeamRole,
    AgentTeam,
    OrchestrationEngine,
    orchestration_engine
)
from .prompts import Prompt, PromptManager
from .processes import Process
from .tasks import Task, TaskManager
from .workflows import SequentialWorkflow, ParallelWorkflow
from .framework import AgenticFramework
from .mcp_tools import MCPTool, MCPToolManager
from .monitoring import MonitoringSystem

# Guardrails (modular imports)
from .guardrails import (
    Guardrail, 
    GuardrailManager,
    # Guardrail types and enums
    GuardrailType,
    GuardrailSeverity,
    GuardrailAction,
    GuardrailViolation,
    GuardrailRule,
    # Specialized guardrails
    SemanticGuardrail,
    ContentSafetyGuardrail,
    OutputFormatGuardrail,
    ChainOfThoughtGuardrail,
    ToolUseGuardrail,
    GuardrailPipeline,
    # Agent Policies
    PolicyScope,
    PolicyEnforcement,
    AgentPolicy,
    BehaviorPolicy,
    ResourcePolicy,
    SafetyPolicy,
    AgentPolicyManager,
    # Global instances
    guardrail_manager,
    agent_policy_manager,
    default_safety_policy
)
from .evaluation_base import EvaluationSystem
# Knowledge - Retriever, Builder, and Vector DB
from .knowledge import (
    # Legacy retriever
    KnowledgeRetriever,
    # Knowledge Builder
    KnowledgeBuilder,
    SourceType,
    KnowledgeChunk,
    EmbeddingOutput,
    # Embedding Providers
    EmbeddingProvider,
    OpenAIEmbedding,
    AzureOpenAIEmbedding,
    HuggingFaceEmbedding,
    CohereEmbedding,
    # Source Loaders
    SourceLoader,
    TextLoader,
    PDFLoader,
    ImageLoader,
    WebLoader,
    WebSearchLoader,
    APILoader,
    # Vector DB
    VectorDBType,
    UnifiedVectorDBTool,
    create_vector_db_tool,
)
from .llms import (
    LLMManager, 
    CircuitBreaker,
    ModelTier,
    ModelCapability,
    ModelConfig,
    ModelRouter,
    MODEL_REGISTRY
)
from .communication import CommunicationManager
# Multi-Protocol Communication (new)
from .communication import (
    # Protocol Types
    ProtocolType,
    ProtocolConfig,
    # Protocols
    CommunicationProtocol,
    STDIOProtocol,
    HTTPProtocol,
    SSEProtocol,
    MQTTProtocol,
    WebSocketProtocol,
    # Channel & Messages
    AgentChannel,
    AgentMessage,
    MessageType,
    # Remote Agent
    RemoteAgentClient,
    RemoteAgentServer,
    AgentEndpoint,
    # Manager
    AgentCommunicationManager,
)

# Memory Management (modular imports)
from .memory import (
    # Core
    MemoryManager,
    MemoryEntry,
    MemoryStats,
    memory_manager,
    # Agent Memory
    MemoryType,
    ConversationTurn,
    Episode,
    Fact,
    WorkingMemoryItem,
    AgentMemoryManager,
    # Workflow Memory
    StepResultType,
    StepResult,
    WorkflowContext,
    WorkflowMemoryCheckpoint,
    WorkflowExecutionRecord,
    WorkflowMemoryManager,
    # Orchestration Memory
    MessagePriority,
    AgentMessage as OrchestrationAgentMessage,
    TaskHandoff,
    SharedContext,
    AgentContribution,
    OrchestrationMemoryManager,
    # Knowledge Memory
    EmbeddingCache,
    QueryResult,
    RetrievalRecord,
    DocumentMemory,
    KnowledgeMemoryManager,
    # Tool Memory
    ToolResultCache,
    ToolExecutionMemory,
    ToolPattern,
    ToolPerformanceStats,
    ToolMemoryManager,
    # Speech Memory
    TranscriptionMemory,
    SynthesisMemory,
    VoiceProfile,
    VoiceConversationMemory,
    AudioCache,
    SpeechMemoryManager,
)

# Tools Framework (35+ tools across 4 categories)
from .tools import (
    # Base classes
    BaseTool,
    AsyncBaseTool,
    ToolResult,
    ToolConfig,
    ToolStatus,
    # Registry & Discovery
    ToolCategory,
    ToolMetadata,
    ToolRegistry,
    tool_registry,
    register_tool,
    # Executor
    ExecutionContext,
    ExecutionPlan,
    ToolExecutor,
    tool_executor,
    # Agent Integration
    AgentToolBinding,
    AgentToolManager,
    agent_tool_manager,
    # MCP Compatibility
    MCPToolAdapter,
    MCPBridge,
    LegacyMCPToolWrapper,
    wrap_mcp_tool,
    convert_to_mcp,
    mcp_bridge,
    # File & Document Tools
    FileReadTool,
    FileWriteTool,
    DirectoryReadTool,
    OCRTool,
    PDFTextWritingTool,
    PDFRAGSearchTool,
    DOCXRAGSearchTool,
    MDXRAGSearchTool,
    XMLRAGSearchTool,
    TXTRAGSearchTool,
    JSONRAGSearchTool,
    CSVRAGSearchTool,
    DirectoryRAGSearchTool,
    # Web Scraping Tools
    ScrapeWebsiteTool,
    ScrapeElementTool,
    ScrapflyScrapeWebsiteTool,
    SeleniumScraperTool,
    ScrapegraphScrapeTool,
    SpiderScraperTool,
    BrowserbaseWebLoaderTool,
    HyperbrowserLoadTool,
    StagehandTool,
    FirecrawlCrawlWebsiteTool,
    FirecrawlScrapeWebsiteTool,
    OxylabsScraperTool,
    BrightDataTool,
    # Database Tools
    MySQLRAGSearchTool,
    PostgreSQLRAGSearchTool,
    SnowflakeSearchTool,
    NL2SQLTool,
    QdrantVectorSearchTool,
    WeaviateVectorSearchTool,
    MongoDBVectorSearchTool,
    SingleStoreSearchTool,
    # AI/ML Tools
    DALLETool,
    VisionTool,
    AIMindTool,
    LlamaIndexTool,
    LangChainTool,
    RAGTool,
    CodeInterpreterTool,
    JavaScriptCodeInterpreterTool,
)
from .hub import Hub
from .configurations import ConfigurationManager

# Security components (modular imports)
from .security import (
    PromptInjectionDetector,
    InputValidator,
    RateLimiter,
    TieredRateLimiter,
    ContentFilter,
    ProfanityFilter,
    PIIFilter,
    AuditLogger,
    SecurityManager,
    security_manager,
    injection_detector,
    input_validator,
    rate_limiter,
    content_filter,
    audit_logger
)

# Enterprise: Tracing & Metrics (modular imports)
from .tracing import (
    AgentStepTracer,
    LatencyMetrics,
    Span,
    SpanContext,
    tracer,
    latency_metrics
)

# Enterprise: Advanced Evaluation (modular imports)
from .evaluation import (
    # Types
    EvaluationType,
    EvaluationResult,
    # Core evaluators
    OfflineEvaluator,
    OnlineEvaluator,
    # Quality and cost
    CostQualityScorer,
    SecurityRiskScorer,
    # Testing frameworks
    ABTestingFramework,
    CanaryDeploymentManager,
    # Model evaluation
    ModelQualityEvaluator,
    ModelTierEvaluator,
    model_tier_evaluator,
    # Task and tool evaluation
    TaskEvaluator,
    ToolInvocationEvaluator,
    # System evaluation
    WorkflowEvaluator,
    MemoryEvaluator,
    RAGEvaluator,
    # Autonomy and performance
    AutonomyEvaluator,
    PerformanceEvaluator,
    # Human and business
    HITLEvaluator,
    BusinessOutcomeEvaluator,
    # Drift detection
    DriftType,
    DriftSeverity,
    DriftAlert,
    PromptDriftDetector,
    prompt_drift_detector,
)

# Enterprise: Prompt Versioning (modular imports)
from .prompt_versioning import (
    PromptVersionManager,
    PromptLibrary,
    PromptVersion,
    PromptStatus,
    PromptAuditEntry,
    prompt_version_manager,
    prompt_library
)

# Enterprise: Infrastructure (modular imports)
from .infrastructure import (
    MultiRegionManager,
    TenantManager,
    ServerlessExecutor,
    DistributedCoordinator,
    Region,
    RegionConfig,
    Tenant,
    ServerlessFunction,
    FunctionInvocation,
    multi_region_manager,
    tenant_manager,
    serverless_executor,
    distributed_coordinator
)

# Enterprise: Compliance & Governance (modular imports)
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

# Enterprise: Integrations (modular imports)
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

# Output Formatting (modular imports)
from .formatting import (
    OutputFormatter,
    FormatType,
    FormattedOutput,
    CodeBlock,
    TableFormat,
    MarkdownFormatter,
    CodeFormatter,
    JSONFormatter,
    HTMLFormatter,
    TableFormatter,
    PlainTextFormatter,
)

# Conversations & Logging (modular imports)
from .conversations import (
    ConversationManager,
    SessionManager,
    Message,
    MessageRole,
    MessageType as ConversationMessageType,
    Turn,
    Session,
    ConversationConfig,
    AgentLogger,
    StructuredLogger,
    ConversationLogger,
    LogLevel,
    LogEntry,
    LogConfig,
)

# Speech - STT/TTS (modular imports)
from .speech import (
    SpeechProcessor,
    VoiceConfig,
    STTResult,
    TTSResult,
    AudioFormat,
    OpenAISTT,
    OpenAITTS,
    AzureSTT,
    AzureTTS,
    GoogleSTT,
    GoogleTTS,
    ElevenLabsTTS,
    WhisperLocalSTT,
)

# Human-in-the-Loop (modular imports)
from .hitl import (
    HumanInTheLoop,
    ApprovalStatus,
    ApprovalRequest,
    ApprovalDecision,
    FeedbackCollector,
    Feedback,
    FeedbackType,
    EscalationLevel,
    InterventionRequest,
    ConsoleApprovalHandler,
    CallbackApprovalHandler,
    QueueApprovalHandler,
)

# State Management (modular imports)
from .state import (
    # Core State Manager
    StateManager,
    StateBackend,
    MemoryBackend,
    FileBackend,
    RedisBackend,
    StateConfig,
    # Agent State
    AgentStateStore,
    AgentSnapshot,
    AgentCheckpoint,
    AgentRecoveryManager,
    # Workflow State
    WorkflowStateManager,
    WorkflowState,
    WorkflowCheckpoint,
    StepState,
    WorkflowStatus,
    # Orchestration State
    OrchestrationStateManager,
    TeamState,
    AgentCoordinationState,
    TaskQueueState,
    # Knowledge State
    KnowledgeStateManager,
    IndexingProgress,
    IndexingStatus,
    SyncStatus,
    SourceState,
    KnowledgeBaseState,
    # Tool State
    ToolStateManager,
    ToolExecution,
    ToolExecutionStatus,
    ToolCacheEntry,
    RetryState,
    ToolStats,
    # Speech State
    SpeechStateManager,
    AudioSessionStatus,
    StreamingMode,
    TranscriptionStatus,
    AudioChunk,
    TranscriptionResult,
    STTState,
    TTSState,
    VoiceConversationState,
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
    # Global Configuration
    # ========================================================================
    "FrameworkConfig", "configure", "get_config", "is_configured", "reset_config",
    
    # ========================================================================
    # Core Components
    # ========================================================================
    "Agent", "AgentManager", "ContextManager",
    "AgentInput", "AgentOutput", "AgentStep", "AgentThought",
    "AgentStatus", "StepType", "AgentRunner",
    "Prompt", "PromptManager",
    "Process",
    "Task", "TaskManager",
    "SequentialWorkflow", "ParallelWorkflow",
    "AgenticFramework",
    "MCPTool", "MCPToolManager",
    "MonitoringSystem",
    "Guardrail", "GuardrailManager",
    "EvaluationSystem",
    "KnowledgeRetriever",
    "LLMManager", "CircuitBreaker",
    "CommunicationManager",
    "Hub",
    "ConfigurationManager",
    
    # ========================================================================
    # Memory Management
    # ========================================================================
    # Core
    "MemoryManager",
    "MemoryEntry",
    "MemoryStats",
    "memory_manager",
    # Agent Memory
    "MemoryType",
    "ConversationTurn",
    "Episode",
    "Fact",
    "WorkingMemoryItem",
    "AgentMemoryManager",
    # Workflow Memory
    "StepResultType",
    "StepResult",
    "WorkflowContext",
    "WorkflowMemoryCheckpoint",
    "WorkflowExecutionRecord",
    "WorkflowMemoryManager",
    # Orchestration Memory
    "MessagePriority",
    "OrchestrationAgentMessage",
    "TaskHandoff",
    "SharedContext",
    "AgentContribution",
    "OrchestrationMemoryManager",
    # Knowledge Memory
    "EmbeddingCache",
    "QueryResult",
    "RetrievalRecord",
    "DocumentMemory",
    "KnowledgeMemoryManager",
    # Tool Memory
    "ToolResultCache",
    "ToolExecutionMemory",
    "ToolPattern",
    "ToolPerformanceStats",
    "ToolMemoryManager",
    # Speech Memory
    "TranscriptionMemory",
    "SynthesisMemory",
    "VoiceProfile",
    "VoiceConversationMemory",
    "AudioCache",
    "SpeechMemoryManager",
    
    # ========================================================================
    # Multi-Protocol Communication (NEW)
    # ========================================================================
    # Protocol Types
    "ProtocolType",
    "ProtocolConfig",
    # Protocol Implementations
    "CommunicationProtocol",
    "STDIOProtocol",
    "HTTPProtocol",
    "SSEProtocol",
    "MQTTProtocol",
    "WebSocketProtocol",
    # Messages
    "AgentChannel",
    "AgentMessage",
    "MessageType",
    # Remote Agent
    "RemoteAgentClient",
    "RemoteAgentServer",
    "AgentEndpoint",
    "AgentCommunicationManager",
    
    # ========================================================================
    # Knowledge Builder & Vector DB (NEW)
    # ========================================================================
    # Knowledge Builder
    "KnowledgeBuilder",
    "SourceType",
    "KnowledgeChunk",
    "EmbeddingOutput",
    # Embedding Providers
    "EmbeddingProvider",
    "OpenAIEmbedding",
    "AzureOpenAIEmbedding",
    "HuggingFaceEmbedding",
    "CohereEmbedding",
    # Source Loaders
    "SourceLoader",
    "TextLoader",
    "PDFLoader",
    "ImageLoader",
    "WebLoader",
    "WebSearchLoader",
    "APILoader",
    # Vector DB
    "VectorDBType",
    "UnifiedVectorDBTool",
    "create_vector_db_tool",
    
    # ========================================================================
    # Tools Framework (35+ Tools)
    # ========================================================================
    # Base classes
    "BaseTool",
    "AsyncBaseTool",
    "ToolResult",
    "ToolConfig",
    "ToolStatus",
    # Tool Registry & Discovery
    "ToolCategory",
    "ToolMetadata",
    "ToolRegistry",
    "tool_registry",
    "register_tool",
    # Tool Executor
    "ExecutionContext",
    "ExecutionPlan",
    "ToolExecutor",
    "tool_executor",
    # Agent-Tool Integration
    "AgentToolBinding",
    "AgentToolManager",
    "agent_tool_manager",
    # MCP Compatibility
    "MCPToolAdapter",
    "MCPBridge",
    "LegacyMCPToolWrapper",
    "wrap_mcp_tool",
    "convert_to_mcp",
    "mcp_bridge",
    # File & Document Tools
    "FileReadTool",
    "FileWriteTool",
    "DirectoryReadTool",
    "OCRTool",
    "PDFTextWritingTool",
    "PDFRAGSearchTool",
    "DOCXRAGSearchTool",
    "MDXRAGSearchTool",
    "XMLRAGSearchTool",
    "TXTRAGSearchTool",
    "JSONRAGSearchTool",
    "CSVRAGSearchTool",
    "DirectoryRAGSearchTool",
    # Web Scraping Tools
    "ScrapeWebsiteTool",
    "ScrapeElementTool",
    "ScrapflyScrapeWebsiteTool",
    "SeleniumScraperTool",
    "ScrapegraphScrapeTool",
    "SpiderScraperTool",
    "BrowserbaseWebLoaderTool",
    "HyperbrowserLoadTool",
    "StagehandTool",
    "FirecrawlCrawlWebsiteTool",
    "FirecrawlScrapeWebsiteTool",
    "OxylabsScraperTool",
    "BrightDataTool",
    # Database Tools
    "MySQLRAGSearchTool",
    "PostgreSQLRAGSearchTool",
    "SnowflakeSearchTool",
    "NL2SQLTool",
    "QdrantVectorSearchTool",
    "WeaviateVectorSearchTool",
    "MongoDBVectorSearchTool",
    "SingleStoreSearchTool",
    # AI/ML Tools
    "DALLETool",
    "VisionTool",
    "AIMindTool",
    "LlamaIndexTool",
    "LangChainTool",
    "RAGTool",
    "CodeInterpreterTool",
    "JavaScriptCodeInterpreterTool",
    
    # ========================================================================
    # ACE - Agentic Context Engine
    # ========================================================================
    "ContextType",                     # Context type classification
    "ContextPriority",                 # Priority levels for retention
    "ContextRetrievalStrategy",        # Retrieval strategies
    "ContextItem",                     # Rich context item
    "SemanticContextIndex",            # Semantic similarity index
    "ContextWindow",                   # Sliding window management
    "ContextCompressionStrategy",      # Compression strategies
    
    # ========================================================================
    # Agent Orchestration Framework
    # ========================================================================
    "OrchestrationPattern",            # Orchestration patterns
    "SupervisionStrategy",             # Supervision strategies
    "AgentRole",                       # Roles agents can play
    "AgentState",                      # Extended agent states
    "TaskAssignment",                  # Task assignment tracking
    "AgentHandoff",                    # Handoff between agents
    "SupervisionConfig",               # Supervision configuration
    "AgentSupervisor",                 # Hierarchical supervisor
    "TeamRole",                        # Team role definition
    "AgentTeam",                       # Coordinated agent team
    "OrchestrationEngine",             # Central orchestration engine
    "orchestration_engine",            # Global orchestration engine
    
    # ========================================================================
    # Enhanced Guardrails
    # ========================================================================
    "GuardrailType",                   # Types of guardrails
    "GuardrailSeverity",               # Severity levels
    "GuardrailAction",                 # Actions on violation
    "GuardrailViolation",              # Violation details
    "GuardrailRule",                   # Rule within guardrail
    "SemanticGuardrail",               # Semantic validation
    "ContentSafetyGuardrail",          # Content safety checks
    "OutputFormatGuardrail",           # Output format validation
    "ChainOfThoughtGuardrail",         # CoT reasoning validation
    "ToolUseGuardrail",                # Tool invocation validation
    "GuardrailPipeline",               # Pipeline for chaining guardrails
    
    # ========================================================================
    # Agent Policy Framework
    # ========================================================================
    "PolicyScope",                     # Policy application scope
    "PolicyEnforcement",               # Enforcement strictness
    "AgentPolicy",                     # Policy definition
    "BehaviorPolicy",                  # Agent behavior constraints
    "ResourcePolicy",                  # Resource access control
    "SafetyPolicy",                    # Safety constraints
    "AgentPolicyManager",              # Centralized policy management
    "guardrail_manager",               # Global guardrail manager
    "agent_policy_manager",            # Global policy manager
    "default_safety_policy",           # Default safety policy
    
    # ========================================================================
    # SLM/RLM Model Support (2026)
    # ========================================================================
    "ModelTier",              # Model tier classification (SLM, MLM, LLM, RLM)
    "ModelCapability",        # Model capability flags
    "ModelConfig",            # Model configuration
    "ModelRouter",            # Intelligent model routing
    "MODEL_REGISTRY",         # Pre-configured model definitions
    
    # ========================================================================
    # Security Components
    # ========================================================================
    "PromptInjectionDetector",
    "InputValidator",
    "RateLimiter",
    "TieredRateLimiter",
    "ContentFilter",
    "ProfanityFilter",
    "PIIFilter",
    "AuditLogger",
    "SecurityManager",
    "security_manager",
    "injection_detector",
    "input_validator",
    "rate_limiter",
    "content_filter",
    "audit_logger",
    
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
    # Enterprise: Prompt Drift Detection
    # ========================================================================
    "PromptDriftDetector",             # Detects prompt effectiveness degradation
    "DriftType",                       # Types of drift (quality, latency, cost, etc.)
    "DriftSeverity",                   # Alert severity levels
    "DriftAlert",                      # Drift alert dataclass
    "prompt_drift_detector",           # Global instance
    
    # ========================================================================
    # Enterprise: Model Tier Evaluation (SLM/RLM)
    # ========================================================================
    "ModelTierEvaluator",              # Tier-specific model evaluation
    "model_tier_evaluator",            # Global instance
    
    # ========================================================================
    # Enterprise: Prompt Versioning
    # ========================================================================
    "PromptVersionManager",
    "PromptLibrary",
    "PromptVersion",
    "PromptStatus",
    "PromptAuditEntry",
    "prompt_version_manager",
    "prompt_library",
    
    # ========================================================================
    # Enterprise: Infrastructure
    # ========================================================================
    "MultiRegionManager",
    "TenantManager",
    "ServerlessExecutor",
    "DistributedCoordinator",
    "Region",
    "RegionConfig",
    "Tenant",
    "ServerlessFunction",
    "FunctionInvocation",
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
    # Output Formatting
    # ========================================================================
    "OutputFormatter",
    "FormatType",
    "FormattedOutput",
    "CodeBlock",
    "TableFormat",
    "MarkdownFormatter",
    "CodeFormatter",
    "JSONFormatter",
    "HTMLFormatter",
    "TableFormatter",
    "PlainTextFormatter",
    
    # ========================================================================
    # Conversations & Logging
    # ========================================================================
    "ConversationManager",
    "SessionManager",
    "Message",
    "MessageRole",
    "ConversationMessageType",
    "Turn",
    "Session",
    "ConversationConfig",
    "AgentLogger",
    "StructuredLogger",
    "ConversationLogger",
    "LogLevel",
    "LogEntry",
    "LogConfig",
    
    # ========================================================================
    # Speech - STT/TTS
    # ========================================================================
    "SpeechProcessor",
    "VoiceConfig",
    "STTResult",
    "TTSResult",
    "AudioFormat",
    "OpenAISTT",
    "OpenAITTS",
    "AzureSTT",
    "AzureTTS",
    "GoogleSTT",
    "GoogleTTS",
    "ElevenLabsTTS",
    "WhisperLocalSTT",
    
    # ========================================================================
    # Human-in-the-Loop
    # ========================================================================
    "HumanInTheLoop",
    "ApprovalStatus",
    "ApprovalRequest",
    "ApprovalDecision",
    "FeedbackCollector",
    "Feedback",
    "FeedbackType",
    "EscalationLevel",
    "InterventionRequest",
    "ConsoleApprovalHandler",
    "CallbackApprovalHandler",
    "QueueApprovalHandler",
    
    # ========================================================================
    # State Management
    # ========================================================================
    # Core State Manager
    "StateManager",
    "StateBackend",
    "MemoryBackend",
    "FileBackend",
    "RedisBackend",
    "StateConfig",
    # Agent State
    "AgentStateStore",
    "AgentSnapshot",
    "AgentCheckpoint",
    "AgentRecoveryManager",
    # Workflow State
    "WorkflowStateManager",
    "WorkflowState",
    "WorkflowCheckpoint",
    "StepState",
    "WorkflowStatus",
    # Orchestration State
    "OrchestrationStateManager",
    "TeamState",
    "AgentCoordinationState",
    "TaskQueueState",
    # Knowledge State
    "KnowledgeStateManager",
    "IndexingProgress",
    "IndexingStatus",
    "SyncStatus",
    "SourceState",
    "KnowledgeBaseState",
    # Tool State
    "ToolStateManager",
    "ToolExecution",
    "ToolExecutionStatus",
    "ToolCacheEntry",
    "RetryState",
    "ToolStats",
    # Speech State
    "SpeechStateManager",
    "AudioSessionStatus",
    "StreamingMode",
    "TranscriptionStatus",
    "AudioChunk",
    "TranscriptionResult",
    "STTState",
    "TTSState",
    "VoiceConversationState",
    
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
