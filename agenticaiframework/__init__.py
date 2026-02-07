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

__version__ = "2.0.16"
__author__ = "Sathishkumar Nagarajan"
__license__ = "MIT"

# ---------------------------------------------------------------------------
# Lazy import registry: maps symbol name → (submodule, real_name | None)
# When real_name is None, it is the same as the symbol name.
# ---------------------------------------------------------------------------
import importlib as _importlib

_LAZY_IMPORTS: dict[str, tuple[str, str | None]] = {
    # --- config (always eagerly loaded for configure() convenience) ---
    # keep config eager so `aaf.configure(...)` works immediately
}

# Eagerly import only the global configuration helpers (tiny module)
from .config import (  # noqa: E402
    FrameworkConfig,
    configure,
    get_config,
    is_configured,
    reset_config,
)

# Build the lazy-import map programmatically
def _register(module: str, names: list[str], renames: dict[str, str] | None = None) -> None:
    renames = renames or {}
    for name in names:
        real = renames.get(name)
        _LAZY_IMPORTS[name] = (module, real)

_register(".core", [
    "Agent", "AgentManager", "AgentInput", "AgentOutput", "AgentStep",
    "AgentThought", "AgentStatus", "StepType", "AgentRunner",
])
_register(".context", [
    "ContextManager", "ContextType", "ContextPriority",
    "ContextRetrievalStrategy", "ContextItem", "SemanticContextIndex",
    "ContextWindow", "ContextCompressionStrategy",
])
_register(".orchestration", [
    "OrchestrationPattern", "SupervisionStrategy", "AgentRole", "AgentState",
    "TaskAssignment", "AgentHandoff", "SupervisionConfig", "AgentSupervisor",
    "TeamRole", "AgentTeam", "OrchestrationEngine", "orchestration_engine",
])
_register(".prompts", ["Prompt", "PromptManager"])
_register(".processes", ["Process"])
_register(".tasks", ["Task", "TaskManager"])
_register(".workflows", ["SequentialWorkflow", "ParallelWorkflow"])
_register(".framework", ["AgenticFramework"])
_register(".mcp_tools", ["MCPTool", "MCPToolManager"])
_register(".monitoring", ["MonitoringSystem"])
_register(".guardrails", [
    "Guardrail", "GuardrailManager", "GuardrailType", "GuardrailSeverity",
    "GuardrailAction", "GuardrailViolation", "GuardrailRule",
    "SemanticGuardrail", "ContentSafetyGuardrail", "OutputFormatGuardrail",
    "ChainOfThoughtGuardrail", "ToolUseGuardrail", "GuardrailPipeline",
    "PolicyScope", "PolicyEnforcement", "AgentPolicy", "BehaviorPolicy",
    "ResourcePolicy", "SafetyPolicy", "AgentPolicyManager",
    "guardrail_manager", "agent_policy_manager", "default_safety_policy",
])
_register(".evaluation_base", ["EvaluationSystem"])
_register(".knowledge", [
    "KnowledgeRetriever", "KnowledgeBuilder", "SourceType", "KnowledgeChunk",
    "EmbeddingOutput", "EmbeddingProvider", "OpenAIEmbedding",
    "AzureOpenAIEmbedding", "HuggingFaceEmbedding", "CohereEmbedding",
    "SourceLoader", "TextLoader", "PDFLoader", "ImageLoader", "WebLoader",
    "WebSearchLoader", "APILoader", "VectorDBType", "UnifiedVectorDBTool",
    "create_vector_db_tool",
])
_register(".llms", [
    "LLMManager", "CircuitBreaker", "ModelTier", "ModelCapability",
    "ModelConfig", "ModelRouter", "MODEL_REGISTRY",
])
_register(".communication", [
    "CommunicationManager", "ProtocolType", "ProtocolConfig",
    "CommunicationProtocol", "STDIOProtocol", "HTTPProtocol", "SSEProtocol",
    "MQTTProtocol", "WebSocketProtocol", "AgentChannel", "AgentMessage",
    "MessageType", "RemoteAgentClient", "RemoteAgentServer", "AgentEndpoint",
    "AgentCommunicationManager",
])
_register(".memory", [
    "MemoryManager", "MemoryEntry", "MemoryStats", "memory_manager",
    "MemoryType", "ConversationTurn", "Episode", "Fact", "WorkingMemoryItem",
    "AgentMemoryManager", "StepResultType", "StepResult", "WorkflowContext",
    "WorkflowMemoryCheckpoint", "WorkflowExecutionRecord", "WorkflowMemoryManager",
    "MessagePriority", "TaskHandoff", "SharedContext", "AgentContribution",
    "OrchestrationMemoryManager", "EmbeddingCache", "QueryResult",
    "RetrievalRecord", "DocumentMemory", "KnowledgeMemoryManager",
    "ToolResultCache", "ToolExecutionMemory", "ToolPattern",
    "ToolPerformanceStats", "ToolMemoryManager", "TranscriptionMemory",
    "SynthesisMemory", "VoiceProfile", "VoiceConversationMemory", "AudioCache",
    "SpeechMemoryManager",
], renames={"OrchestrationAgentMessage": "AgentMessage"})
# OrchestrationAgentMessage is an alias for memory.AgentMessage
_LAZY_IMPORTS["OrchestrationAgentMessage"] = (".memory", "AgentMessage")

_register(".tools", [
    "BaseTool", "AsyncBaseTool", "ToolResult", "ToolConfig", "ToolStatus",
    "ToolCategory", "ToolMetadata", "ToolRegistry", "tool_registry",
    "register_tool", "ExecutionContext", "ExecutionPlan", "ToolExecutor",
    "tool_executor", "AgentToolBinding", "AgentToolManager", "agent_tool_manager",
    "MCPToolAdapter", "MCPBridge", "LegacyMCPToolWrapper", "wrap_mcp_tool",
    "convert_to_mcp", "mcp_bridge",
    "FileReadTool", "FileWriteTool", "DirectoryReadTool", "OCRTool",
    "PDFTextWritingTool", "PDFRAGSearchTool", "DOCXRAGSearchTool",
    "MDXRAGSearchTool", "XMLRAGSearchTool", "TXTRAGSearchTool",
    "JSONRAGSearchTool", "CSVRAGSearchTool", "DirectoryRAGSearchTool",
    "ScrapeWebsiteTool", "ScrapeElementTool", "ScrapflyScrapeWebsiteTool",
    "SeleniumScraperTool", "ScrapegraphScrapeTool", "SpiderScraperTool",
    "BrowserbaseWebLoaderTool", "HyperbrowserLoadTool", "StagehandTool",
    "FirecrawlCrawlWebsiteTool", "FirecrawlScrapeWebsiteTool",
    "OxylabsScraperTool", "BrightDataTool",
    "MySQLRAGSearchTool", "PostgreSQLRAGSearchTool", "SnowflakeSearchTool",
    "NL2SQLTool", "QdrantVectorSearchTool", "WeaviateVectorSearchTool",
    "MongoDBVectorSearchTool", "SingleStoreSearchTool",
    "DALLETool", "VisionTool", "AIMindTool", "LlamaIndexTool",
    "LangChainTool", "RAGTool", "CodeInterpreterTool",
    "JavaScriptCodeInterpreterTool",
])
_register(".hub", ["Hub"])
_register(".configurations", ["ConfigurationManager"])
_register(".security", [
    "PromptInjectionDetector", "InputValidator", "RateLimiter",
    "TieredRateLimiter", "ContentFilter", "ProfanityFilter", "PIIFilter",
    "AuditLogger", "SecurityManager", "security_manager",
    "injection_detector", "input_validator", "rate_limiter",
    "content_filter", "audit_logger",
])
_register(".tracing", [
    "AgentStepTracer", "LatencyMetrics", "Span", "SpanContext",
    "tracer", "latency_metrics",
])
_register(".evaluation", [
    "EvaluationType", "EvaluationResult", "OfflineEvaluator", "OnlineEvaluator",
    "CostQualityScorer", "SecurityRiskScorer", "ABTestingFramework",
    "CanaryDeploymentManager", "ModelQualityEvaluator", "ModelTierEvaluator",
    "model_tier_evaluator", "TaskEvaluator", "ToolInvocationEvaluator",
    "WorkflowEvaluator", "MemoryEvaluator", "RAGEvaluator",
    "AutonomyEvaluator", "PerformanceEvaluator", "HITLEvaluator",
    "BusinessOutcomeEvaluator", "DriftType", "DriftSeverity", "DriftAlert",
    "PromptDriftDetector", "prompt_drift_detector",
])
_register(".prompt_versioning", [
    "PromptVersionManager", "PromptLibrary", "PromptVersion",
    "PromptStatus", "PromptAuditEntry", "prompt_version_manager",
    "prompt_library",
])
_register(".infrastructure", [
    "MultiRegionManager", "TenantManager", "ServerlessExecutor",
    "DistributedCoordinator", "Region", "RegionConfig", "Tenant",
    "ServerlessFunction", "FunctionInvocation", "multi_region_manager",
    "tenant_manager", "serverless_executor", "distributed_coordinator",
])
_register(".compliance", [
    "AuditTrailManager", "PolicyEngine", "DataMaskingEngine", "AuditEvent",
    "AuditEventType", "AuditSeverity", "Policy", "PolicyType",
    "MaskingRule", "MaskingType", "audit_trail", "policy_engine",
    "data_masking", "audit_action", "enforce_policy", "mask_output",
])
_register(".integrations", [
    "IntegrationManager", "WebhookManager", "ServiceNowIntegration",
    "GitHubIntegration", "AzureDevOpsIntegration", "SnowflakeConnector",
    "DatabricksConnector", "IntegrationConfig", "IntegrationStatus",
    "integration_manager", "webhook_manager",
])
_register(".formatting", [
    "OutputFormatter", "FormatType", "FormattedOutput", "CodeBlock",
    "TableFormat", "MarkdownFormatter", "CodeFormatter", "JSONFormatter",
    "HTMLFormatter", "TableFormatter", "PlainTextFormatter",
])
_register(".conversations", [
    "ConversationManager", "SessionManager", "Message", "MessageRole",
    "Turn", "Session", "ConversationConfig", "AgentLogger",
    "StructuredLogger", "ConversationLogger", "LogLevel", "LogEntry",
    "LogConfig",
], renames={"ConversationMessageType": "MessageType"})
_LAZY_IMPORTS["ConversationMessageType"] = (".conversations", "MessageType")

_register(".speech", [
    "SpeechProcessor", "VoiceConfig", "STTResult", "TTSResult", "AudioFormat",
    "OpenAISTT", "OpenAITTS", "AzureSTT", "AzureTTS", "GoogleSTT",
    "GoogleTTS", "ElevenLabsTTS", "WhisperLocalSTT",
])
_register(".hitl", [
    "HumanInTheLoop", "ApprovalStatus", "ApprovalRequest", "ApprovalDecision",
    "FeedbackCollector", "Feedback", "FeedbackType", "EscalationLevel",
    "InterventionRequest", "ConsoleApprovalHandler", "CallbackApprovalHandler",
    "QueueApprovalHandler",
])
_register(".state", [
    "StateManager", "StateBackend", "MemoryBackend", "FileBackend",
    "RedisBackend", "StateConfig", "AgentStateStore", "AgentSnapshot",
    "AgentCheckpoint", "AgentRecoveryManager", "WorkflowStateManager",
    "WorkflowState", "WorkflowCheckpoint", "StepState", "WorkflowStatus",
    "OrchestrationStateManager", "TeamState", "AgentCoordinationState",
    "TaskQueueState", "KnowledgeStateManager", "IndexingProgress",
    "IndexingStatus", "SyncStatus", "SourceState", "KnowledgeBaseState",
    "ToolStateManager", "ToolExecution", "ToolExecutionStatus",
    "ToolCacheEntry", "RetryState", "ToolStats", "SpeechStateManager",
    "AudioSessionStatus", "StreamingMode", "TranscriptionStatus",
    "AudioChunk", "TranscriptionResult", "STTState", "TTSState",
    "VoiceConversationState",
])
_register(".exceptions", [
    "AgenticAIError", "CircuitBreakerError", "CircuitBreakerOpenError",
    "RateLimitError", "RateLimitExceededError", "SecurityError",
    "InjectionDetectedError", "ContentFilteredError", "ValidationError",
    "GuardrailViolationError", "PromptRenderError", "TaskError",
    "TaskExecutionError", "TaskNotFoundError", "AgentError",
    "AgentNotFoundError", "AgentExecutionError", "LLMError",
    "ModelNotFoundError", "ModelInferenceError", "AgenticMemoryError",
    "MemoryExportError", "KnowledgeError", "KnowledgeRetrievalError",
    "CommunicationError", "ProtocolError", "ProtocolNotFoundError",
    "EvaluationError", "CriterionEvaluationError",
])

# Clean up helper
del _register

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
    
    # ========================================================================
    # Enterprise Module (Minimal Code Patterns)
    # ========================================================================
    "enterprise",
]

# Enterprise submodule is lazy-loaded via __getattr__
# Special handling: 'enterprise' is a subpackage, not a symbol
def __getattr__(name: str):  # noqa: F811 - intentional override
    """Lazy-load symbols on first access for fast startup."""
    if name == "enterprise":
        mod = _importlib.import_module(".enterprise", __package__)
        globals()["enterprise"] = mod
        return mod
    if name in _LAZY_IMPORTS:
        module_path, real_name = _LAZY_IMPORTS[name]
        module = _importlib.import_module(module_path, __package__)
        attr = getattr(module, real_name or name)
        globals()[name] = attr
        return attr
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
