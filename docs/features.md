---
title: Feature Catalogue
description: Every AgenticAI Framework module grouped by lifecycle stage - build, coordinate, remember, retrieve, protect, evaluate, observe, operate, enterprise and internals - with a link to each guide.
tags:
  - getting-started
  - reference
---

# Feature Catalogue

A list of what is in the package, grouped by the stage of an agent system's life it serves. Each entry names the module, states what it does in one line and links to the guide that covers it. Counts come from the current release: 455 modules, 237 of them under `agenticaiframework.enterprise`, 45 standard-library-only modules under `agenticaiframework._internal`, 430 top-level exports, 0 runtime dependencies.

## Build

Define agents, give them work to do and the prompts, tools and models they need.

| Module | What it does | Guide |
|---|---|---|
| `agenticaiframework.core` | `Agent`, `Agent.quick`, `Agent.from_config`, `AgentManager`, `AgentRunner` (ReAct and native tool-calling loops), `AgentInput`, `AgentOutput`, `AgentStep`, `AgentThought`, `AgentStatus`, `StepType` | [Agents](agents.md) |
| `agenticaiframework.tasks` | `Task(name, objective, executor, inputs)` with `run()`; `TaskManager` registers tasks and runs them in order | [Tasks](tasks.md) |
| `agenticaiframework.processes` | `Process(name, strategy="sequential"\|"parallel", max_workers)` runs callables directly or on a thread pool | [Processes](processes.md) |
| `agenticaiframework.workflows` | `SequentialWorkflow`, `ParallelWorkflow` chain agent invocations | [Agents](agents.md) |
| `agenticaiframework.prompts` | `Prompt`, `PromptManager` for templates with variable substitution and `PromptRenderError` | [Prompts](prompts.md) |
| `agenticaiframework.prompt_versioning` | `PromptVersionManager` with versions, activation, rendering and an audit log; `PromptLibrary` | [Prompts](prompts.md) |
| `agenticaiframework.tools` | `BaseTool`, `AsyncBaseTool`, `ToolConfig`, `ToolResult`, `ToolRegistry` with `discover()` for 46 built-in tools, `AgentToolManager` binding tools to agents | [Tools](tools.md) |
| `agenticaiframework.tools` (MCP) | `MCPServer`, `MCPClient`, `MCPBridge`, `MCPToolAdapter` implementing the Model Context Protocol on stdio | [MCP Tools](mcp_tools.md) |
| `agenticaiframework.mcp_tools` | `MCPTool(name, capability, execute_fn)` function wrappers and `MCPToolManager` | [MCP Tools](mcp_tools.md) |
| `agenticaiframework.llms` | `LLMManager` (providers, fallback chain, cache, per-provider `CircuitBreaker`), `ModelRouter`, `MODEL_REGISTRY` with 17 models, `ModelConfig`, `ModelTier`, `ModelCapability` | [LLMs](llms.md) |
| `agenticaiframework.llms.providers` | `OpenAIProvider`, `AnthropicProvider`, `GoogleProvider` on standard-library REST clients; `LLMMessage`, `LLMResponse`, `ProviderConfig` | [LLMs](llms.md) |
| `agenticaiframework.speech` | `SpeechProcessor` with `OpenAISTT`/`OpenAITTS`, `AzureSTT`/`AzureTTS`, `GoogleSTT`/`GoogleTTS`, `ElevenLabsTTS`, `WhisperLocalSTT`; `STTResult`, `TTSResult`, `AudioFormat`, `VoiceConfig` | [Speech](speech.md) |
| `agenticaiframework.formatting` | `OutputFormatter` with JSON, Markdown, HTML, plain-text, code and table formatters | [Agents](agents.md) |
| `agenticaiframework.conversations` | `ConversationManager`, `SessionManager`, `ConversationLogger`, `StructuredLogger`, `Message`, `Turn` | [Agents](agents.md) |
| `agenticaiframework.config` | `configure()`, `get_config()`, `is_configured()`, `reset_config()`, `FrameworkConfig` | [Configuration](CONFIGURATION.md) |
| `agenticaiframework.configurations` | `ConfigurationManager` key/value store with validation | [Configuration reference](configuration-reference.md) |
| `agenticaiframework.hub` | `Hub` registry for agents, tools and services by name | [Hub](hub.md) |
| `agenticaiframework.framework` | `AgenticFramework` facade bundling managers for one application | [Architecture](architecture.md) |
| `agenticaiframework.exceptions` | `AgenticAIError` hierarchy: `AgentError`, `TaskError`, `LLMError`, `GuardrailViolationError`, `RateLimitError`, `KnowledgeError`, `ProtocolError` and others | [API reference](API_REFERENCE.md) |

## Coordinate

Run several agents on one problem.

| Module | What it does | Guide |
|---|---|---|
| `agenticaiframework.orchestration` | `AgentTeam(name, goal, roles)`, `TeamRole`, `AgentSupervisor`, `SupervisionConfig`, `SupervisionStrategy`, `AgentHandoff`, `TaskAssignment` | [Orchestration](orchestration.md) |
| `agenticaiframework.orchestration` (engine) | `OrchestrationEngine.orchestrate(agents, task_callable, pattern=...)` with `OrchestrationPattern` `SEQUENTIAL`, `PARALLEL`, `HIERARCHICAL`, `SWARM`, `CONSENSUS`, `PIPELINE`, `BROADCAST`, `ROUND_ROBIN`, `PRIORITY`, `ADAPTIVE` | [Orchestration](orchestration.md) |
| `agenticaiframework.communication` | `AgentChannel` in-process routing with `MessageType`; `AgentCommunicationManager`, `RemoteAgentClient`, `RemoteAgentServer` | [Communication](communication.md) |
| `agenticaiframework.communication.protocols` | `HTTPProtocol`, `WebSocketProtocol`, `MQTTProtocol`, `SSEProtocol`, `STDIOProtocol` on the standard library | [Communication](communication.md) |
| `agenticaiframework.hitl` | `HumanInTheLoop`, `ApprovalRequest`, `ApprovalDecision`, `ApprovalStatus`, `CallbackApprovalHandler`, `ConsoleApprovalHandler`, `QueueApprovalHandler`, `EscalationTrigger`, `FeedbackCollector` | [Agents - Human-in-the-loop](agents.md#human-in-the-loop) |
| `agenticaiframework.infrastructure` | `DistributedCoordinator`, `ServerlessExecutor`, `MultiRegionManager`, `TenantManager` | [Infrastructure](infrastructure.md) |

## Remember

Keep conversation, working memory, facts and execution state between calls and between processes.

| Module | What it does | Guide |
|---|---|---|
| `agenticaiframework.memory` | `MemoryManager` tiered store with `store`, `retrieve`, `search`, TTL and priority | [Memory](memory.md) |
| `agenticaiframework.memory` (specialised) | `AgentMemoryManager` (turns, working memory, facts, episodes), `WorkflowMemoryManager`, `OrchestrationMemoryManager`, `KnowledgeMemoryManager`, `ToolMemoryManager`, `SpeechMemoryManager` | [Memory](memory.md) |
| `agenticaiframework.state` | `AgentStateStore`, `AgentCheckpoint`, `AgentSnapshot`, `AgentRecoveryManager`, `RetryState` | [State](state.md) |
| `agenticaiframework.state` (domain managers) | `WorkflowStateManager`, `OrchestrationStateManager`, `KnowledgeStateManager`, `ToolStateManager`, `SpeechStateManager` | [State](state.md) |
| `agenticaiframework.state` (backends) | `StateBackend` interface with `MemoryBackend`, `FileBackend`, `RedisBackend` | [State](state.md) |
| `agenticaiframework.context` | `ContextManager`, `ContextWindow`, `ContextItem`, `ContextType`, `ContextPriority`, `ContextCompressionStrategy`, `SemanticContextIndex` | [Context](context.md) |

## Retrieve

Load documents, embed them and give agents something to search.

| Module | What it does | Guide |
|---|---|---|
| `agenticaiframework.knowledge` | `KnowledgeRetriever.register_source(name, fn)` and `retrieve(query, use_cache=True)` with an LRU cache | [Knowledge](knowledge.md) |
| `agenticaiframework.knowledge.builder` | `KnowledgeBuilder(embedding_provider, embedding_model, chunk_size, chunk_overlap)` with `add_text`, `add_from_directory`; `KnowledgeChunk` | [Knowledge](knowledge.md) |
| `agenticaiframework.knowledge` (loaders) | `TextLoader`, `MarkdownLoader`, `PDFLoader`, `DocxLoader`, `CSVLoader`, `JSONLoader`, `WebLoader`, `WebSearchLoader`, `APILoader`, `ImageLoader` | [Knowledge](knowledge.md) |
| `agenticaiframework.knowledge` (embeddings) | `OpenAIEmbedding`, `AzureOpenAIEmbedding`, `CohereEmbedding`, `HuggingFaceEmbedding`, `EmbeddingProvider` | [Knowledge](knowledge.md) |
| `agenticaiframework.knowledge.vector_db` | `InMemoryVectorDB`, `ChromaClient`, `QdrantClient`, `PineconeClient`, `VectorDBClient`, `VectorDBConfig`, `create_vector_db_tool` | [Knowledge](knowledge.md) |
| `agenticaiframework.tools` (RAG tools) | `PDFRAGSearchTool`, `DOCXRAGSearchTool`, `CSVRAGSearchTool`, `JSONRAGSearchTool`, `DirectoryRAGSearchTool`, `PostgreSQLRAGSearchTool`, `MySQLRAGSearchTool`, `MongoDBVectorSearchTool` | [Tools](tools.md) |

## Protect

Validate what goes into and comes out of a model, and keep a record.

| Module | What it does | Guide |
|---|---|---|
| `agenticaiframework.guardrails` | `GuardrailManager` with `create_standard_guardrails`, `register_guardrail`, `enforce_guardrails`; `Guardrail`, `GuardrailViolation`, `GuardrailSeverity` | [Guardrails](guardrails.md) |
| `agenticaiframework.guardrails` (checks) | `PIIDetectionGuardrail`, `PromptInjectionGuardrail`, `InputLengthGuardrail`, `ContentSafetyGuardrail`, `OutputFormatGuardrail`, `ToolUseGuardrail`, `SemanticGuardrail`, `ChainOfThoughtGuardrail` | [Guardrails](guardrails.md) |
| `agenticaiframework.guardrails` (pipelines and policies) | `GuardrailPipeline.minimal()`, `.safety_only()`, `.enterprise_defaults()`; `AgentPolicyManager`, `AgentPolicy`, `BehaviorPolicy`, `ResourcePolicy`, `SafetyPolicy` | [Guardrails](guardrails.md) |
| `agenticaiframework.security` | `InputValidator`, `PromptInjectionDetector`, `PIIFilter`, `ProfanityFilter`, `ContentFilter`, `RateLimiter`, `TieredRateLimiter`, `AuditLogger`, `SecurityManager` | [Security](security.md) |
| `agenticaiframework.compliance` | `DataMaskingEngine.mask()` and `detect_pii()`, `MaskingRule`; `AuditTrailManager` hash-chained log with `log`, `query`, `verify_integrity`; `PolicyEngine`, `Policy`, `PolicyType` | [Compliance](compliance.md) |

## Evaluate

Score outputs, retrieval, tool use, cost and drift; compare variants.

| Module | What it does | Guide |
|---|---|---|
| `agenticaiframework.evaluation` (quality) | `ModelQualityEvaluator.evaluate_response(model_name, prompt, response, ground_truth=)`, `ModelTierEvaluator`, `TaskEvaluator` | [Evaluation](evaluation.md) |
| `agenticaiframework.evaluation` (pipeline) | `RAGEvaluator`, `ToolInvocationEvaluator`, `WorkflowEvaluator`, `MemoryEvaluator`, `AutonomyEvaluator`, `PerformanceEvaluator` | [Evaluation](evaluation.md) |
| `agenticaiframework.evaluation` (risk and cost) | `SecurityRiskScorer.assess_risk(input_text=, output_text=)`, `CostQualityScorer.record_execution()` and `get_cost_summary()` | [Evaluation](evaluation.md) |
| `agenticaiframework.evaluation` (drift and outcomes) | `PromptDriftDetector`, `DriftAlert`, `HITLEvaluator`, `BusinessOutcomeEvaluator` | [Evaluation](evaluation.md) |
| `agenticaiframework.evaluation` (experiments) | `ABTestingFramework`, `CanaryDeploymentManager`, `OfflineEvaluator`, `OnlineEvaluator`, `EvaluationResult`, `EvaluationType` | [Evaluation](evaluation.md) |

## Observe

See what ran, how long it took and what it cost.

| Module | What it does | Guide |
|---|---|---|
| `agenticaiframework.tracing` | `AgentStepTracer` with `start_trace`, `start_span`, `set_attribute`, `end_span`, `get_trace_tree`; `Span`, `SpanContext`, `LatencyMetrics` | [Tracing](tracing.md) |
| `agenticaiframework.monitoring` | `MonitoringSystem.record_metric`, `log_event`, `get_metrics`, `get_events` | [Monitoring](monitoring.md) |
| `agenticaiframework.enterprise.tracing_otel` | Span exporters including `OTLPExporter` (OTLP/HTTP JSON) | [Tracing](tracing.md) |
| `agenticaiframework.enterprise.metrics`, `.alerting`, `.alert_manager` | Prometheus and Datadog metric formats, alert rules and notification channels | [Monitoring](monitoring.md) |
| `agenticaiframework.conversations` | `ConversationLogger`, `AgentLogger`, `StructuredLogger`, `LogEntry`, `LogLevel` | [Agents](agents.md) |

## Operate

Run the system in production.

| Module | What it does | Guide |
|---|---|---|
| `agenticaiframework.infrastructure` | `ServerlessExecutor`, `ServerlessFunction`, `MultiRegionManager`, `Region`, `RegionConfig`, `Tenant`, `TenantManager` | [Infrastructure](infrastructure.md) |
| `agenticaiframework.integrations` | `GitHubIntegration`, `AzureDevOpsIntegration`, `ServiceNowIntegration`, `DatabricksConnector`, `SnowflakeConnector`, `WebhookManager`, `IntegrationManager` | [Integration](integration.md) |
| `agenticaiframework.llms` (resilience) | Per-provider `CircuitBreaker`, fallback chains, response cache, retry counts | [LLMs](llms.md), [Performance](performance.md) |
| Deployment guidance | Containers, serverless, multi-region, configuration by environment | [Deployment](deployment.md), [Best practices](best-practices.md) |

## Enterprise

`agenticaiframework.enterprise` holds 237 self-contained modules. The groups below name representative modules; the full list is in [Enterprise](enterprise.md).

| Group | Modules |
|---|---|
| Messaging and CQRS | `event_bus` (`InMemoryEventBus`), `command_bus`, `query_bus`, `cqrs`, `event_sourcing`, `event_store`, `outbox`, `saga`, `saga_orchestrator`, `pubsub`, `message_broker`, `dead_letter`, `stream_processing` |
| Resilience | `circuit_breaker` (`CircuitBreaker`), `bulkhead`, `retry`, `retry_policy`, `timeout`, `fallback`, `rate_limiter`, `throttle`, `quota`, `load_balancer`, `health_check`, `chaos` |
| Deployment | `blue_green`, `canary`, `rollback`, `deployment_manager`, `release_manager`, `feature_flags`, `feature_toggle`, `environment_manager`, `config_server` |
| Data | `database`, `repository`, `unit_of_work`, `migration`, `data_pipeline`, `data_lineage`, `data_validator`, `schema_registry`, `vector_database`, `graph_database`, `timeseries_database`, `feature_store` |
| Security | `rbac`, `permission_engine`, `oauth_provider`, `secrets_manager`, `secret_vault`, `encryption`, `encryption_service`, `data_masking`, `data_privacy_manager`, `audit_trail`, `compliance_engine` |
| Multi-tenancy | `tenant`, `tenant_manager`, `multitenancy`, `session_manager`, `license_manager`, `subscription_manager` |
| Observability | `tracing_otel`, `metrics`, `metrics_collector`, `alert_manager`, `alerting`, `log_aggregator`, `health_monitor`, `profiler`, `sla_manager`, `incident_manager`, `oncall_manager`, `runbook_manager` |
| AI infrastructure | `ml_inference`, `embeddings`, `rag`, `knowledge_manager`, `summarization`, `json_mode`, `function_call`, `streaming`, `ranking`, `recommendation_engine`, `analytics_engine` |
| Domain-driven design | `aggregate`, `aggregate_root`, `entity`, `value_object`, `domain_events`, `domain_service`, `bounded_context`, `specification`, `factories`, `projection` |
| Integration | `api_gateway`, `gateway`, `api_versioning`, `api_lifecycle_manager`, `graphql_manager`, `grpc_manager`, `webhook`, `webhook_receiver`, `sse_manager`, `websocket`, `service_discovery`, `service_registry`, `mesh` |
| Cloud adapters | `adapters` (S3, Azure Blob, Cosmos DB, Service Bus, GCS, Redis, Azure OpenAI), `secrets` (Azure Key Vault) |
| Business services | `payment_gateway`, `invoice_generator`, `tax_calculator`, `order_processing`, `inventory_manager`, `shipping_service`, `booking_engine`, `loyalty_program`, `survey_engine`, `voting_system`, `calendar_service` |
| Documents and media | `pdf_generator`, `document_generator`, `document_converter`, `excel_service`, `report_builder`, `report_generator`, `barcode_generator`, `qr_generator`, `image_processor`, `audio_processor`, `video_processor` |

## Internals

`agenticaiframework._internal` contains the standard-library implementations that make the zero-dependency install possible. They are not public API.

| Module | Replaces |
|---|---|
| `http`, `http_server`, `h2`, `ws`, `mqtt`, `smtp`, `graphql` | HTTP/1.1 and HTTP/2 client, HTTP server, WebSocket, MQTT, SMTP and GraphQL clients |
| `aes`, `aes_gcm`, `fernet`, `ec`, `jwt`, `pem` | AES-CBC/GCM, Fernet tokens, elliptic-curve signing, JWT encode/verify, PEM parsing |
| `pdf`, `docx`, `html`, `yaml`, `msgpack`, `schema`, `tokenizer` | PDF read/write, DOCX text extraction, HTML parsing, YAML, MessagePack, JSON-schema validation, token counting |
| `redis_resp`, `vector_store`, `array`, `cron`, `healthcheck`, `duckduckgo` | Redis RESP protocol, in-memory vector index, numeric arrays, cron expressions, health probes, web search |
| `clients.openai_rest`, `clients.anthropic_rest`, `clients.gemini_rest`, `clients.cohere_rest` | Provider SDKs |
| `clients.postgres_wire`, `clients.mysql_wire`, `clients.snowflake_rest`, `clients.mongo_data_api`, `clients.cosmos_rest`, `clients.qdrant_rest`, `clients.weaviate_rest` | Database drivers and vector store clients |
| `clients.aws_sigv4`, `clients.s3_rest`, `clients.azure_blob_rest`, `clients.azure_servicebus_rest`, `clients.gcp_rest`, `clients.twilio_rest` | Cloud SDKs |

See [Architecture](architecture.md) for how these layers fit together and [Installation and Usage](USAGE.md) for the third-party packages that are used when installed.

## Related

- [Quick Start](quick-start.md)
- [Architecture](architecture.md)
- [Framework comparison](comparison.md)
- [API reference](API_REFERENCE.md)
- [Examples](EXAMPLES.md)
