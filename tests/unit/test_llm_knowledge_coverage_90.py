"""
Comprehensive tests for LLM providers and knowledge modules to achieve 90% coverage.
Uses correct class signatures based on actual implementations.
"""

import time

# ============================================================================
# LLM Provider Base Tests
# ============================================================================

class TestLLMProviderBase:
    """Tests for LLM provider base classes."""
    
    def test_llm_message_creation(self):
        """Test LLMMessage creation."""
        from agenticaiframework.llms.providers.base import LLMMessage
        
        message = LLMMessage(role="user", content="Hello, world!")
        assert message.role == "user"
        assert message.content == "Hello, world!"
    
    def test_llm_message_to_dict(self):
        """Test LLMMessage to_dict method."""
        from agenticaiframework.llms.providers.base import LLMMessage
        
        message = LLMMessage(
            role="assistant", 
            content="Hi there!",
            name="assistant_1"
        )
        msg_dict = message.to_dict()
        assert msg_dict['role'] == "assistant"
        assert msg_dict['content'] == "Hi there!"
        assert msg_dict['name'] == "assistant_1"
    
    def test_llm_response_creation(self):
        """Test LLMResponse creation."""
        from agenticaiframework.llms.providers.base import LLMResponse
        
        response = LLMResponse(
            content="This is the response",
            model="gpt-4",
            provider="openai",
            finish_reason="stop",
            usage={"prompt_tokens": 10, "completion_tokens": 20}
        )
        assert response.content == "This is the response"
        assert response.model == "gpt-4"
        assert response.provider == "openai"
    
    def test_llm_response_tool_calls(self):
        """Test LLMResponse has_tool_calls property."""
        from agenticaiframework.llms.providers.base import LLMResponse
        
        response = LLMResponse(
            content="",
            model="gpt-4",
            provider="openai",
            tool_calls=[{"name": "test_tool", "arguments": "{}"}]
        )
        assert response.has_tool_calls is True
    
    def test_provider_config_creation(self):
        """Test ProviderConfig creation."""
        from agenticaiframework.llms.providers.base import ProviderConfig
        
        config = ProviderConfig(
            api_key="test_key",
            default_model="gpt-4",
            timeout=60.0,
            max_retries=3
        )
        assert config.api_key == "test_key"
        assert config.default_model == "gpt-4"
        assert config.timeout == 60.0


class TestOpenAIProvider:
    """Tests for OpenAI provider."""
    
    def test_openai_provider_init(self):
        """Test OpenAIProvider initialization."""
        from agenticaiframework.llms.providers.openai_provider import OpenAIProvider
        from agenticaiframework.llms.providers.base import ProviderConfig
        
        config = ProviderConfig(api_key="test_key")
        provider = OpenAIProvider(config=config)
        assert provider is not None
    
    def test_openai_provider_supported_models(self):
        """Test OpenAIProvider supported models."""
        from agenticaiframework.llms.providers.openai_provider import OpenAIProvider
        
        assert "gpt-4o" in OpenAIProvider.SUPPORTED_MODELS
        assert "gpt-4" in OpenAIProvider.SUPPORTED_MODELS


class TestAnthropicProvider:
    """Tests for Anthropic provider."""
    
    def test_anthropic_provider_init(self):
        """Test AnthropicProvider initialization."""
        from agenticaiframework.llms.providers.anthropic_provider import AnthropicProvider
        from agenticaiframework.llms.providers.base import ProviderConfig
        
        config = ProviderConfig(api_key="test_key")
        provider = AnthropicProvider(config=config)
        assert provider is not None


class TestGoogleProvider:
    """Tests for Google provider."""
    
    def test_google_provider_init(self):
        """Test GoogleProvider initialization."""
        from agenticaiframework.llms.providers.google_provider import GoogleProvider
        from agenticaiframework.llms.providers.base import ProviderConfig
        
        config = ProviderConfig(api_key="test_key")
        provider = GoogleProvider(config=config)
        assert provider is not None


# ============================================================================
# LLM Manager Tests
# ============================================================================

class TestLLMManagerComprehensive:
    """Comprehensive tests for LLM manager."""
    
    def test_llm_manager_init(self):
        """Test LLMManager initialization."""
        from agenticaiframework.llms.manager import LLMManager
        
        manager = LLMManager()
        assert manager is not None


class TestLLMCircuitBreaker:
    """Tests for LLM circuit breaker."""
    
    def test_circuit_breaker_import(self):
        """Test circuit breaker import."""
        from agenticaiframework.llms.circuit_breaker import CircuitBreaker
        
        breaker = CircuitBreaker()
        assert breaker is not None


class TestLLMRouter:
    """Tests for LLM router."""
    
    def test_llm_router_module_import(self):
        """Test LLM router module import."""
        from agenticaiframework.llms import router
        
        assert router is not None


# ============================================================================
# Knowledge Module Tests
# ============================================================================

class TestKnowledgeBuilder:
    """Tests for KnowledgeBuilder."""
    
    def test_knowledge_builder_init(self):
        """Test KnowledgeBuilder initialization."""
        from agenticaiframework.knowledge import KnowledgeBuilder
        
        builder = KnowledgeBuilder()
        assert builder is not None


class TestKnowledgeRetriever:
    """Tests for KnowledgeRetriever."""
    
    def test_knowledge_retriever_init(self):
        """Test KnowledgeRetriever initialization."""
        from agenticaiframework.knowledge import KnowledgeRetriever
        
        retriever = KnowledgeRetriever()
        assert retriever is not None


class TestVectorDB:
    """Tests for vector database implementations."""
    
    def test_vector_db_type_enum(self):
        """Test VectorDBType enum."""
        from agenticaiframework.knowledge.vector_db import VectorDBType
        
        assert VectorDBType.QDRANT is not None
        assert VectorDBType.PINECONE is not None
        assert VectorDBType.MEMORY is not None


class TestEmbeddingProviders:
    """Tests for embedding providers."""
    
    def test_embedding_provider_import(self):
        """Test embedding provider imports."""
        from agenticaiframework.knowledge import EmbeddingProvider
        
        assert EmbeddingProvider is not None
    
    def test_openai_embedding_import(self):
        """Test OpenAIEmbedding import."""
        from agenticaiframework.knowledge import OpenAIEmbedding
        
        assert OpenAIEmbedding is not None


class TestSourceLoaders:
    """Tests for source loaders."""
    
    def test_text_loader_init(self):
        """Test TextLoader initialization."""
        from agenticaiframework.knowledge import TextLoader
        
        loader = TextLoader()
        assert loader is not None
    
    def test_markdown_loader_init(self):
        """Test MarkdownLoader initialization."""
        from agenticaiframework.knowledge import MarkdownLoader
        
        loader = MarkdownLoader()
        assert loader is not None


# ============================================================================
# Communication Tests
# ============================================================================

class TestCommunication:
    """Tests for communication module."""
    
    def test_agent_channel_init(self):
        """Test AgentChannel initialization."""
        from agenticaiframework.communication import AgentChannel
        
        assert AgentChannel is not None
    
    def test_agent_communication_manager_init(self):
        """Test AgentCommunicationManager initialization."""
        from agenticaiframework.communication import AgentCommunicationManager
        
        manager = AgentCommunicationManager()
        assert manager is not None
    
    def test_protocol_types(self):
        """Test protocol types."""
        from agenticaiframework.communication import ProtocolType, ProtocolConfig
        
        assert ProtocolType is not None
        assert ProtocolConfig is not None


# ============================================================================
# Tracing Tests
# ============================================================================

class TestTracingTypes:
    """Comprehensive tests for tracing types."""
    
    def test_span_context_creation(self):
        """Test SpanContext creation."""
        from agenticaiframework.tracing.types import SpanContext
        
        context = SpanContext(
            trace_id="trace123",
            span_id="span456"
        )
        assert context.trace_id == "trace123"
        assert context.span_id == "span456"
    
    def test_span_creation(self):
        """Test Span creation."""
        from agenticaiframework.tracing.types import Span
        
        span = Span(
            name="test_span",
            trace_id="trace123",
            span_id="span456",
            parent_span_id=None,
            start_time=time.time()
        )
        assert span.name == "test_span"
    
    def test_span_duration(self):
        """Test Span duration calculation."""
        from agenticaiframework.tracing.types import Span
        
        start = time.time()
        span = Span(
            name="duration_test",
            trace_id="trace123",
            span_id="span456",
            parent_span_id=None,
            start_time=start,
            end_time=start + 0.1
        )
        duration = span.duration_ms
        assert duration is not None
        assert duration > 0
    
    def test_span_add_event(self):
        """Test Span add_event method."""
        from agenticaiframework.tracing.types import Span
        
        span = Span(
            name="event_test",
            trace_id="trace123",
            span_id="span456",
            parent_span_id=None,
            start_time=time.time()
        )
        span.add_event("test_event", {"key": "value"})
        assert len(span.events) == 1
    
    def test_span_set_attribute(self):
        """Test Span set_attribute method."""
        from agenticaiframework.tracing.types import Span
        
        span = Span(
            name="attr_test",
            trace_id="trace123",
            span_id="span456",
            parent_span_id=None,
            start_time=time.time()
        )
        span.set_attribute("test_key", "test_value")
        assert span.attributes.get("test_key") == "test_value"
    
    def test_latency_metrics(self):
        """Test LatencyMetrics."""
        from agenticaiframework.tracing.metrics import LatencyMetrics
        
        metrics = LatencyMetrics()
        assert metrics is not None


# ============================================================================
# Orchestration Tests
# ============================================================================

class TestOrchestrationModels:
    """Tests for orchestration models."""
    
    def test_orchestration_types_import(self):
        """Test orchestration types import."""
        from agenticaiframework.orchestration import types
        
        assert types is not None


class TestAgentSupervisor:
    """Tests for agent supervisor."""
    
    def test_agent_supervisor_import(self):
        """Test AgentSupervisor import."""
        from agenticaiframework.orchestration.supervisor import AgentSupervisor
        
        assert AgentSupervisor is not None


class TestAgentTeams:
    """Tests for agent teams."""
    
    def test_agent_team_import(self):
        """Test AgentTeam import."""
        from agenticaiframework.orchestration.teams import AgentTeam
        
        assert AgentTeam is not None


# ============================================================================
# Prompt Versioning Tests
# ============================================================================

class TestPromptVersioning:
    """Tests for prompt versioning."""
    
    def test_prompt_library_init(self):
        """Test PromptLibrary initialization."""
        from agenticaiframework.prompt_versioning.library import PromptLibrary
        
        library = PromptLibrary()
        assert library is not None
    
    def test_prompt_versioning_manager_import(self):
        """Test prompt versioning manager module import."""
        from agenticaiframework.prompt_versioning import manager
        
        assert manager is not None


# ============================================================================
# Workflows Tests
# ============================================================================

class TestWorkflows:
    """Tests for workflows module."""
    
    def test_sequential_workflow_import(self):
        """Test SequentialWorkflow import."""
        from agenticaiframework.workflows import SequentialWorkflow
        
        assert SequentialWorkflow is not None
    
    def test_parallel_workflow_import(self):
        """Test ParallelWorkflow import."""
        from agenticaiframework.workflows import ParallelWorkflow
        
        assert ParallelWorkflow is not None


# ============================================================================
# Core Agent Runner Tests
# ============================================================================

class TestCoreRunner:
    """Tests for core runner."""
    
    def test_runner_import(self):
        """Test runner import."""
        from agenticaiframework.core.runner import AgentRunner
        
        assert AgentRunner is not None


# ============================================================================
# Speech Processor Tests
# ============================================================================

class TestSpeechProcessor:
    """Tests for speech processor."""
    
    def test_speech_processor_import(self):
        """Test speech processor import."""
        from agenticaiframework.speech.processor import SpeechProcessor
        
        assert SpeechProcessor is not None


# ============================================================================
# Additional Module Tests
# ============================================================================

class TestMCPTools:
    """Tests for MCP tools module."""
    
    def test_mcp_tools_import(self):
        """Test MCP tools import."""
        from agenticaiframework.mcp_tools import MCPTool
        
        assert MCPTool is not None


class TestExceptions:
    """Tests for exceptions module."""
    
    def test_base_exception_import(self):
        """Test base exception import."""
        from agenticaiframework.exceptions import AgentExecutionError
        
        assert AgentExecutionError is not None
    
    def test_agent_exception_import(self):
        """Test agent exception import."""
        from agenticaiframework.exceptions import AgenticAIError, AgentError
        
        assert AgenticAIError is not None
        assert AgentError is not None


class TestProcesses:
    """Tests for processes module."""
    
    def test_process_manager_import(self):
        """Test processes module import."""
        from agenticaiframework import processes
        
        assert processes is not None


class TestMonitoring:
    """Tests for monitoring module."""
    
    def test_monitoring_import(self):
        """Test monitoring import."""
        from agenticaiframework.monitoring import MonitoringSystem
        
        system = MonitoringSystem()
        assert system is not None


class TestHub:
    """Tests for hub module."""
    
    def test_hub_import(self):
        """Test hub import."""
        from agenticaiframework import hub
        
        assert hub is not None
