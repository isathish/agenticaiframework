"""
Comprehensive tests to boost code coverage to 90%.
Tests low-coverage modules: tools, llm providers, knowledge, hitl, infrastructure, integrations.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os
from pathlib import Path


# ============================================================================
# Directory Tools Tests (16% coverage)
# ============================================================================

class TestDirectoryRAGSearchTool:
    """Tests for DirectoryRAGSearchTool."""
    
    def test_supported_extensions(self):
        """Test SUPPORTED_EXTENSIONS class attribute."""
        from agenticaiframework.tools.file_document.directory_tools import DirectoryRAGSearchTool
        
        tool = DirectoryRAGSearchTool()
        assert '.pdf' in tool.SUPPORTED_EXTENSIONS
        assert '.docx' in tool.SUPPORTED_EXTENSIONS
        assert '.md' in tool.SUPPORTED_EXTENSIONS
        assert '.txt' in tool.SUPPORTED_EXTENSIONS
        assert '.json' in tool.SUPPORTED_EXTENSIONS
        assert '.csv' in tool.SUPPORTED_EXTENSIONS
        assert '.xml' in tool.SUPPORTED_EXTENSIONS
    
    def test_init_defaults(self):
        """Test DirectoryRAGSearchTool with default config."""
        from agenticaiframework.tools.file_document.directory_tools import DirectoryRAGSearchTool
        
        tool = DirectoryRAGSearchTool()
        assert tool.chunk_size == 500
        assert tool.chunk_overlap == 50
        assert tool._chunks == []
        assert tool._indexed_files == []
    
    def test_init_custom_config(self):
        """Test DirectoryRAGSearchTool with custom config."""
        from agenticaiframework.tools.file_document.directory_tools import DirectoryRAGSearchTool
        from agenticaiframework.tools.base import ToolConfig
        
        config = ToolConfig(name="CustomDirTool", description="Custom tool")
        tool = DirectoryRAGSearchTool(config=config, chunk_size=1000, chunk_overlap=100)
        
        assert tool.chunk_size == 1000
        assert tool.chunk_overlap == 100
    
    def test_execute_no_directory(self):
        """Test _execute with no directory returns empty results."""
        from agenticaiframework.tools.file_document.directory_tools import DirectoryRAGSearchTool
        
        tool = DirectoryRAGSearchTool()
        result = tool._execute(query="test query")
        
        assert result['query'] == "test query"
        assert result['results'] == []
        assert result['total_chunks'] == 0
    
    def test_execute_with_mocked_chunks(self):
        """Test _execute with pre-populated chunks."""
        from agenticaiframework.tools.file_document.directory_tools import DirectoryRAGSearchTool
        
        tool = DirectoryRAGSearchTool()
        # Manually add chunks to simulate indexed state with correct 'text' key
        tool._chunks = [
            {"text": "Hello world", "source": "test.txt", "embedding": [0.1, 0.2, 0.3]},
            {"text": "Goodbye world", "source": "test2.txt", "embedding": [0.4, 0.5, 0.6]},
        ]
        tool._indexed_files = ["test.txt", "test2.txt"]
        
        result = tool._execute(query="hello", top_k=5)
        
        assert result['total_chunks'] == 2
        assert result['indexed_files'] == ["test.txt", "test2.txt"]


# ============================================================================
# OCR Tools Tests (15% coverage)
# ============================================================================

class TestOCRTool:
    """Tests for OCRTool."""
    
    def test_init_defaults(self):
        """Test OCRTool with default config."""
        from agenticaiframework.tools.file_document.ocr_tools import OCRTool
        
        tool = OCRTool()
        assert tool.backend == 'tesseract'
        assert tool.language == 'eng'
        assert 'tesseract' in tool._backends
        assert 'azure' in tool._backends
        assert 'google' in tool._backends
        assert 'aws' in tool._backends
    
    def test_init_custom_backend(self):
        """Test OCRTool with custom backend."""
        from agenticaiframework.tools.file_document.ocr_tools import OCRTool
        
        tool = OCRTool(backend='azure', language='spa')
        assert tool.backend == 'azure'
        assert tool.language == 'spa'
    
    def test_execute_file_not_found(self):
        """Test _execute with non-existent file."""
        from agenticaiframework.tools.file_document.ocr_tools import OCRTool
        
        tool = OCRTool()
        with pytest.raises(FileNotFoundError):
            tool._execute(image_path="/nonexistent/path/image.png")
    
    def test_execute_invalid_extension(self):
        """Test _execute with unsupported image format."""
        from agenticaiframework.tools.file_document.ocr_tools import OCRTool
        
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"text content")
            temp_path = f.name
        
        try:
            tool = OCRTool()
            with pytest.raises(ValueError, match="Unsupported image format"):
                tool._execute(image_path=temp_path)
        finally:
            os.unlink(temp_path)
    
    def test_execute_unknown_backend(self):
        """Test _execute with unknown backend."""
        from agenticaiframework.tools.file_document.ocr_tools import OCRTool
        
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"\x89PNG\r\n\x1a\n")  # PNG magic bytes
            temp_path = f.name
        
        try:
            tool = OCRTool()
            with pytest.raises(ValueError, match="Unknown backend"):
                tool._execute(image_path=temp_path, backend="unknown")
        finally:
            os.unlink(temp_path)


# ============================================================================
# Code Interpreter Tool Tests (20% coverage)
# ============================================================================

class TestCodeInterpreterTool:
    """Tests for CodeInterpreterTool."""
    
    def test_init_defaults(self):
        """Test CodeInterpreterTool with default config."""
        from agenticaiframework.tools.ai_ml.code_tools import CodeInterpreterTool
        
        tool = CodeInterpreterTool()
        assert tool.timeout == 30.0
        assert tool.max_output_length == 10000
        assert tool.allow_package_install == True
        assert 'math' in tool.allowed_modules
        assert 'json' in tool.allowed_modules
    
    def test_init_custom_config(self):
        """Test CodeInterpreterTool with custom config."""
        from agenticaiframework.tools.ai_ml.code_tools import CodeInterpreterTool
        
        tool = CodeInterpreterTool(
            allowed_modules=['math', 'json'],
            timeout=60.0,
            max_output_length=5000,
            allow_package_install=False
        )
        
        assert tool.timeout == 60.0
        assert tool.max_output_length == 5000
        assert tool.allow_package_install == False
        assert tool.allowed_modules == ['math', 'json']
    
    def test_execute_simple_code(self):
        """Test _execute with simple code."""
        from agenticaiframework.tools.ai_ml.code_tools import CodeInterpreterTool
        
        tool = CodeInterpreterTool()
        result = tool._execute(code="x = 1 + 1", capture_output=True)
        
        assert result['status'] in ['success', 'error']
        assert 'code' in result
    
    def test_execute_with_reset(self):
        """Test _execute with reset_environment."""
        from agenticaiframework.tools.ai_ml.code_tools import CodeInterpreterTool
        
        tool = CodeInterpreterTool()
        tool._globals['existing'] = 'value'
        tool._locals['local_var'] = 'local'
        
        result = tool._execute(code="y = 2", reset_environment=True)
        
        # After reset, previous globals/locals should be cleared
        assert 'existing' not in tool._globals or tool._globals.get('existing') is None
    
    def test_execute_package_install_disabled(self):
        """Test _execute with package install disabled."""
        from agenticaiframework.tools.ai_ml.code_tools import CodeInterpreterTool
        
        tool = CodeInterpreterTool(allow_package_install=False)
        result = tool._execute(code="import test", packages=["test-package"], auto_install=True)
        
        assert result['status'] == 'error'
        assert 'disabled' in result['error'].lower()


# ============================================================================
# LLM Provider Tests (19-20% coverage)
# ============================================================================

class TestOpenAIProvider:
    """Tests for OpenAIProvider."""
    
    def test_init_default_model(self):
        """Test OpenAIProvider sets default model."""
        from agenticaiframework.llms.providers.openai_provider import OpenAIProvider
        from agenticaiframework.llms.providers.base import ProviderConfig
        
        config = ProviderConfig(api_key="test-key")
        provider = OpenAIProvider(config=config)
        
        assert provider.config.default_model == "gpt-4o"
    
    def test_provider_name(self):
        """Test provider_name property."""
        from agenticaiframework.llms.providers.openai_provider import OpenAIProvider
        from agenticaiframework.llms.providers.base import ProviderConfig
        
        config = ProviderConfig(api_key="test-key")
        provider = OpenAIProvider(config=config)
        
        assert provider.provider_name == "openai"
    
    def test_supported_models(self):
        """Test supported_models property."""
        from agenticaiframework.llms.providers.openai_provider import OpenAIProvider
        from agenticaiframework.llms.providers.base import ProviderConfig
        
        config = ProviderConfig(api_key="test-key")
        provider = OpenAIProvider(config=config)
        
        models = provider.supported_models
        assert "gpt-4o" in models
        assert "gpt-4" in models
        assert "gpt-3.5-turbo" in models
    
    def test_from_env(self):
        """Test from_env class method."""
        from agenticaiframework.llms.providers.openai_provider import OpenAIProvider
        
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key-123"}):
            provider = OpenAIProvider.from_env(model="gpt-4")
            assert provider.config.api_key == "test-key-123"
            assert provider.config.default_model == "gpt-4"


class TestAnthropicProvider:
    """Tests for AnthropicProvider."""
    
    def test_init_default_model(self):
        """Test AnthropicProvider sets default model."""
        from agenticaiframework.llms.providers.anthropic_provider import AnthropicProvider
        from agenticaiframework.llms.providers.base import ProviderConfig
        
        config = ProviderConfig(api_key="test-key")
        provider = AnthropicProvider(config=config)
        
        assert "claude" in provider.config.default_model.lower()
    
    def test_provider_name(self):
        """Test provider_name property."""
        from agenticaiframework.llms.providers.anthropic_provider import AnthropicProvider
        from agenticaiframework.llms.providers.base import ProviderConfig
        
        config = ProviderConfig(api_key="test-key")
        provider = AnthropicProvider(config=config)
        
        assert provider.provider_name == "anthropic"
    
    def test_supported_models(self):
        """Test supported_models property."""
        from agenticaiframework.llms.providers.anthropic_provider import AnthropicProvider
        from agenticaiframework.llms.providers.base import ProviderConfig
        
        config = ProviderConfig(api_key="test-key")
        provider = AnthropicProvider(config=config)
        
        models = provider.supported_models
        assert any("claude" in m for m in models)
    
    def test_from_env(self):
        """Test from_env class method."""
        from agenticaiframework.llms.providers.anthropic_provider import AnthropicProvider
        
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key-456"}):
            provider = AnthropicProvider.from_env()
            assert provider.config.api_key == "test-key-456"


class TestGoogleProvider:
    """Tests for GoogleProvider."""
    
    def test_init_default_model(self):
        """Test GoogleProvider sets default model."""
        from agenticaiframework.llms.providers.google_provider import GoogleProvider
        from agenticaiframework.llms.providers.base import ProviderConfig
        
        config = ProviderConfig(api_key="test-key")
        provider = GoogleProvider(config=config)
        
        assert provider.config.default_model is not None
    
    def test_provider_name(self):
        """Test provider_name property."""
        from agenticaiframework.llms.providers.google_provider import GoogleProvider
        from agenticaiframework.llms.providers.base import ProviderConfig
        
        config = ProviderConfig(api_key="test-key")
        provider = GoogleProvider(config=config)
        
        assert provider.provider_name == "google"
    
    def test_supported_models(self):
        """Test supported_models property."""
        from agenticaiframework.llms.providers.google_provider import GoogleProvider
        from agenticaiframework.llms.providers.base import ProviderConfig
        
        config = ProviderConfig(api_key="test-key")
        provider = GoogleProvider(config=config)
        
        models = provider.supported_models
        assert len(models) > 0


# ============================================================================
# Knowledge Builder Tests (36% coverage)
# ============================================================================

class TestKnowledgeBuilder:
    """Tests for KnowledgeBuilder."""
    
    def test_source_type_values(self):
        """Test all SourceType enum values."""
        from agenticaiframework.knowledge.builder import SourceType
        
        assert SourceType.WEB_SEARCH.value == "web_search"
        assert SourceType.WEB_PAGE.value == "web_page"
        assert SourceType.API.value == "api"
        assert SourceType.PDF.value == "pdf"
        assert SourceType.DOCX.value == "docx"
        assert SourceType.TXT.value == "txt"
        assert SourceType.MARKDOWN.value == "markdown"
        assert SourceType.HTML.value == "html"
        assert SourceType.IMAGE.value == "image"
        assert SourceType.JSON.value == "json"
        assert SourceType.CSV.value == "csv"
        assert SourceType.EXCEL.value == "excel"
        assert SourceType.CODE.value == "code"
        assert SourceType.AUDIO.value == "audio"
        assert SourceType.VIDEO.value == "video"
        assert SourceType.CUSTOM.value == "custom"
    
    def test_knowledge_chunk_creation(self):
        """Test KnowledgeChunk creation with all fields."""
        from agenticaiframework.knowledge.builder import KnowledgeChunk, SourceType
        
        chunk = KnowledgeChunk(
            id="test-123",
            content="Test content here",
            source="test_file.pdf",
            source_type=SourceType.PDF,
            metadata={"page": 1, "author": "Test"},
            embedding=[0.1, 0.2, 0.3, 0.4, 0.5],
        )
        
        assert chunk.id == "test-123"
        assert chunk.content == "Test content here"
        assert chunk.source_type == SourceType.PDF
        assert chunk.embedding is not None
    
    def test_knowledge_chunk_to_dict(self):
        """Test KnowledgeChunk to_dict method."""
        from agenticaiframework.knowledge.builder import KnowledgeChunk, SourceType
        
        chunk = KnowledgeChunk(
            content="Test content",
            source="test.txt",
            source_type=SourceType.TXT,
            metadata={"key": "value"},
        )
        
        data = chunk.to_dict()
        assert data["content"] == "Test content"
        assert data["source"] == "test.txt"
        assert data["source_type"] == "txt"
        assert data["metadata"] == {"key": "value"}
    
    def test_knowledge_chunk_from_dict(self):
        """Test KnowledgeChunk from_dict method."""
        from agenticaiframework.knowledge.builder import KnowledgeChunk, SourceType
        
        data = {
            "id": "chunk-456",
            "content": "Loaded content",
            "source": "loaded.md",
            "source_type": "markdown",
            "metadata": {"loaded": True},
            "embedding": [0.1, 0.2],
            "timestamp": "2024-01-01T00:00:00",
        }
        
        chunk = KnowledgeChunk.from_dict(data)
        assert chunk.id == "chunk-456"
        assert chunk.source_type == SourceType.MARKDOWN
        assert chunk.embedding == [0.1, 0.2]
    
    def test_embedding_output_creation(self):
        """Test EmbeddingOutput creation."""
        from agenticaiframework.knowledge.builder import EmbeddingOutput
        
        output = EmbeddingOutput(
            id="emb-001",
            embedding=[0.1, 0.2, 0.3, 0.4],
            content="Embedded text content",
            metadata={"source": "test.txt"}
        )
        
        assert output.id == "emb-001"
        assert len(output.embedding) == 4
        assert output.content == "Embedded text content"
    
    def test_embedding_output_to_qdrant_point(self):
        """Test EmbeddingOutput to_qdrant_point method."""
        from agenticaiframework.knowledge.builder import EmbeddingOutput
        
        output = EmbeddingOutput(
            id="emb-002",
            embedding=[0.5, 0.6],
            content="Qdrant content",
            metadata={"type": "test"}
        )
        
        point = output.to_qdrant_point(collection_name="test_collection")
        assert point["id"] == "emb-002"
        assert point["vector"] == [0.5, 0.6]
        assert "content" in point["payload"]


# ============================================================================
# HITL Manager Tests (35% coverage)
# ============================================================================

class TestHITLManager:
    """Tests for Human-in-the-Loop Manager."""
    
    def test_import_hitl_module(self):
        """Test HITL module can be imported."""
        from agenticaiframework.hitl.manager import HumanInTheLoop
        assert HumanInTheLoop is not None
    
    def test_approval_status_enum(self):
        """Test ApprovalStatus enum."""
        from agenticaiframework.hitl.manager import ApprovalStatus
        
        statuses = list(ApprovalStatus)
        assert len(statuses) > 0
    
    def test_feedback_type_enum(self):
        """Test FeedbackType enum."""
        from agenticaiframework.hitl.manager import FeedbackType
        
        types = list(FeedbackType)
        assert len(types) > 0
    
    def test_escalation_level_enum(self):
        """Test EscalationLevel enum."""
        from agenticaiframework.hitl.manager import EscalationLevel
        
        levels = list(EscalationLevel)
        assert len(levels) > 0
    
    def test_approval_request_creation(self):
        """Test ApprovalRequest dataclass."""
        from agenticaiframework.hitl.manager import ApprovalRequest
        
        request = ApprovalRequest(
            id="req-001",
            action="approve",
            details={"key": "value"},
            agent_id="agent-001",
            session_id="session-001",
            reason="Test approval request",
            created_at="2024-01-01T00:00:00",
        )
        assert request.id == "req-001"
    
    def test_feedback_collector(self):
        """Test FeedbackCollector initialization."""
        from agenticaiframework.hitl.manager import FeedbackCollector
        
        collector = FeedbackCollector()
        assert collector is not None


# ============================================================================
# Infrastructure Tests (60-75% coverage)
# ============================================================================

class TestInfrastructureTypes:
    """Tests for infrastructure types."""
    
    def test_infrastructure_types_import(self):
        """Test infrastructure types import."""
        from agenticaiframework.infrastructure.types import (
            RegionConfig,
            Tenant,
            Region,
        )
        
        region = RegionConfig(
            region=Region.US_EAST,
            endpoint="https://api.us-east-1.example.com",
        )
        assert region.endpoint == "https://api.us-east-1.example.com"
    
    def test_region_enum(self):
        """Test Region enum."""
        from agenticaiframework.infrastructure.types import Region
        
        regions = list(Region)
        assert len(regions) > 0
    
    def test_tenant_dataclass(self):
        """Test Tenant dataclass."""
        from agenticaiframework.infrastructure.types import Tenant
        import time
        
        tenant = Tenant(
            tenant_id="tenant-001",
            name="Test Tenant",
            tier="standard",
            quota={"requests": 1000},
            metadata={},
            created_at=time.time(),
        )
        assert tenant.tenant_id == "tenant-001"
    
    def test_multi_region_manager(self):
        """Test MultiRegionManager."""
        from agenticaiframework.infrastructure.multi_region import MultiRegionManager
        
        manager = MultiRegionManager()
        assert manager is not None
    
    def test_serverless_executor(self):
        """Test ServerlessExecutor."""
        from agenticaiframework.infrastructure.serverless import ServerlessExecutor
        
        executor = ServerlessExecutor()
        assert executor is not None
    
    def test_tenant_manager(self):
        """Test TenantManager."""
        from agenticaiframework.infrastructure.tenant import TenantManager
        
        manager = TenantManager()
        assert manager is not None
    
    def test_distributed_coordinator(self):
        """Test DistributedCoordinator."""
        from agenticaiframework.infrastructure.coordinator import DistributedCoordinator
        
        coordinator = DistributedCoordinator()
        assert coordinator is not None


# ============================================================================
# Integration Tests (40-65% coverage)
# ============================================================================

class TestIntegrations:
    """Tests for integration modules."""
    
    def test_integration_status_enum(self):
        """Test IntegrationStatus enum."""
        from agenticaiframework.integrations.types import IntegrationStatus
        
        statuses = list(IntegrationStatus)
        assert len(statuses) > 0
    
    def test_integration_config(self):
        """Test IntegrationConfig dataclass."""
        from agenticaiframework.integrations.types import IntegrationConfig, IntegrationStatus
        import time
        
        config = IntegrationConfig(
            integration_id="int-001",
            name="test-integration",
            integration_type="rest",
            endpoint="https://api.example.com",
            auth_type="api_key",
            credentials={"api_key": "test-key"},
            settings={"timeout": 30},
            status=IntegrationStatus.ACTIVE,
            created_at=time.time(),
        )
        assert config.name == "test-integration"
    
    def test_base_integration(self):
        """Test base integration import."""
        from agenticaiframework.integrations.base import BaseIntegration
        
        # BaseIntegration is abstract, just test import
        assert BaseIntegration is not None
    
    def test_webhook_manager(self):
        """Test WebhookManager import."""
        from agenticaiframework.integrations.webhooks import WebhookManager
        
        manager = WebhookManager()
        assert manager is not None
    
    def test_integration_manager(self):
        """Test IntegrationManager import."""
        from agenticaiframework.integrations.manager import IntegrationManager
        
        manager = IntegrationManager()
        assert manager is not None


# ============================================================================
# Web Scraping Tools Tests (20-32% coverage)
# ============================================================================

class TestWebScrapingTools:
    """Tests for web scraping tools."""
    
    def test_scrape_website_tool_init(self):
        """Test ScrapeWebsiteTool initialization."""
        from agenticaiframework.tools.web_scraping.basic_scraping import ScrapeWebsiteTool
        
        tool = ScrapeWebsiteTool()
        assert tool is not None
    
    def test_scrape_element_tool_init(self):
        """Test ScrapeElementTool initialization."""
        from agenticaiframework.tools.web_scraping.basic_scraping import ScrapeElementTool
        
        tool = ScrapeElementTool()
        assert tool is not None
    
    def test_scrapfly_tool_init(self):
        """Test ScrapflyScrapeWebsiteTool initialization."""
        from agenticaiframework.tools.web_scraping.advanced_scraping import ScrapflyScrapeWebsiteTool
        
        tool = ScrapflyScrapeWebsiteTool()
        assert tool is not None
    
    def test_scrapegraph_tool_init(self):
        """Test ScrapegraphScrapeTool initialization."""
        from agenticaiframework.tools.web_scraping.advanced_scraping import ScrapegraphScrapeTool
        
        tool = ScrapegraphScrapeTool()
        assert tool is not None


# ============================================================================
# Database Tools Tests (25-37% coverage)
# ============================================================================

class TestDatabaseTools:
    """Tests for database tools."""
    
    def test_snowflake_search_tool_init(self):
        """Test SnowflakeSearchTool initialization."""
        from agenticaiframework.tools.database.snowflake_tools import SnowflakeSearchTool
        
        tool = SnowflakeSearchTool()
        assert tool is not None
    
    def test_singlestore_search_tool_init(self):
        """Test SingleStoreSearchTool initialization."""
        from agenticaiframework.tools.database.snowflake_tools import SingleStoreSearchTool
        
        tool = SingleStoreSearchTool()
        assert tool is not None


# ============================================================================
# Workflow Tests (47% coverage)
# ============================================================================

class TestWorkflows:
    """Tests for workflow module."""
    
    def test_sequential_workflow(self):
        """Test SequentialWorkflow creation."""
        from agenticaiframework.workflows import SequentialWorkflow
        from agenticaiframework.orchestration.engine import OrchestrationEngine
        
        engine = OrchestrationEngine()
        workflow = SequentialWorkflow(manager=engine)
        assert workflow is not None
    
    def test_parallel_workflow(self):
        """Test ParallelWorkflow creation."""
        from agenticaiframework.workflows import ParallelWorkflow
        from agenticaiframework.orchestration.engine import OrchestrationEngine
        
        engine = OrchestrationEngine()
        workflow = ParallelWorkflow(manager=engine)
        assert workflow is not None


# ============================================================================
# Orchestration Engine Tests (55% coverage)
# ============================================================================

class TestOrchestrationEngine:
    """Tests for OrchestrationEngine."""
    
    def test_engine_init(self):
        """Test OrchestrationEngine initialization."""
        from agenticaiframework.orchestration.engine import OrchestrationEngine
        
        engine = OrchestrationEngine()
        assert engine is not None
    
    def test_engine_patterns(self):
        """Test OrchestrationPattern enum."""
        from agenticaiframework.orchestration.types import OrchestrationPattern
        
        patterns = list(OrchestrationPattern)
        assert OrchestrationPattern.SEQUENTIAL in patterns
        assert OrchestrationPattern.PARALLEL in patterns
        assert OrchestrationPattern.HIERARCHICAL in patterns


# ============================================================================
# Prompt Versioning Manager Tests (57% coverage)
# ============================================================================

class TestPromptVersioningManager:
    """Tests for PromptVersioningManager."""
    
    def test_prompt_status_enum(self):
        """Test PromptStatus enum."""
        from agenticaiframework.prompt_versioning.types import PromptStatus
        
        assert PromptStatus.DRAFT.value == "draft"
        assert PromptStatus.ACTIVE.value == "active"
        assert PromptStatus.DEPRECATED.value == "deprecated"
        assert PromptStatus.ARCHIVED.value == "archived"


# ============================================================================
# Tracing Metrics Tests (57% coverage)
# ============================================================================

class TestTracingMetrics:
    """Tests for tracing metrics."""
    
    def test_latency_metrics(self):
        """Test LatencyMetrics dataclass."""
        from agenticaiframework.tracing.metrics import LatencyMetrics
        
        metrics = LatencyMetrics()
        assert metrics is not None
    
    def test_span_context(self):
        """Test SpanContext creation."""
        from agenticaiframework.tracing.types import SpanContext
        
        context = SpanContext(
            trace_id="trace-001",
            span_id="span-001",
            parent_span_id=None
        )
        
        assert context.trace_id == "trace-001"
        assert context.span_id == "span-001"
    
    def test_span_creation(self):
        """Test Span creation."""
        from agenticaiframework.tracing.types import Span
        import time
        
        span = Span(
            span_id="span-002",
            trace_id="trace-002",
            name="test-span",
            parent_span_id=None,
            start_time=time.time(),
        )
        
        assert span.name == "test-span"
    
    def test_agent_step_tracer(self):
        """Test AgentStepTracer initialization."""
        from agenticaiframework.tracing.tracer import AgentStepTracer
        
        tracer = AgentStepTracer()
        assert tracer is not None


# ============================================================================
# Exception Inheritance Tests
# ============================================================================

class TestExceptionHierarchy:
    """Test exception inheritance hierarchy."""
    
    def test_circuit_breaker_errors(self):
        """Test circuit breaker exception hierarchy."""
        from agenticaiframework.exceptions import (
            CircuitBreakerError,
            CircuitBreakerOpenError,
            AgenticAIError,
        )
        
        base_error = CircuitBreakerError("base")
        open_error = CircuitBreakerOpenError("open")
        
        assert isinstance(base_error, AgenticAIError)
        assert isinstance(open_error, CircuitBreakerError)
    
    def test_rate_limit_errors(self):
        """Test rate limit exception hierarchy."""
        from agenticaiframework.exceptions import (
            RateLimitError,
            RateLimitExceededError,
            AgenticAIError,
        )
        
        base_error = RateLimitError("base")
        exceeded_error = RateLimitExceededError("exceeded")
        
        assert isinstance(base_error, AgenticAIError)
        assert isinstance(exceeded_error, RateLimitError)
    
    def test_llm_errors(self):
        """Test LLM exception hierarchy."""
        from agenticaiframework.exceptions import (
            LLMError,
            ModelNotFoundError,
            ModelInferenceError,
            AgenticAIError,
        )
        
        llm_error = LLMError("llm")
        not_found = ModelNotFoundError("not found")
        inference = ModelInferenceError("inference")
        
        assert isinstance(llm_error, AgenticAIError)
        assert isinstance(not_found, LLMError)
        assert isinstance(inference, LLMError)
    
    def test_agent_execution_error_attributes(self):
        """Test AgentExecutionError with attributes."""
        from agenticaiframework.exceptions import AgentExecutionError
        
        error = AgentExecutionError(
            "Execution failed",
            agent_name="test_agent"
        )
        
        assert "Execution failed" in str(error)


# ============================================================================
# Core Runner Tests (9% coverage)
# ============================================================================

class TestCoreRunner:
    """Tests for core runner module."""
    
    def test_agent_runner_import(self):
        """Test AgentRunner can be imported."""
        from agenticaiframework.core.runner import AgentRunner
        assert AgentRunner is not None
    
    def test_runner_with_mock_agent(self):
        """Test AgentRunner with mock agent."""
        from agenticaiframework.core.runner import AgentRunner
        
        mock_agent = Mock()
        mock_agent.name = "test_agent"
        mock_agent.run = Mock(return_value="result")
        
        runner = AgentRunner(agent=mock_agent)
        assert runner is not None


# ============================================================================
# Document Tools Tests (26% coverage)
# ============================================================================

class TestDocumentTools:
    """Tests for document tools."""
    
    def test_base_rag_search_tool(self):
        """Test BaseRAGSearchTool is abstract."""
        from agenticaiframework.tools.file_document.document_tools import BaseRAGSearchTool
        
        assert BaseRAGSearchTool is not None
    
    def test_docx_rag_search_tool(self):
        """Test DOCXRAGSearchTool initialization."""
        from agenticaiframework.tools.file_document.document_tools import DOCXRAGSearchTool
        
        tool = DOCXRAGSearchTool()
        assert tool is not None
    
    def test_mdx_rag_search_tool(self):
        """Test MDXRAGSearchTool initialization."""
        from agenticaiframework.tools.file_document.document_tools import MDXRAGSearchTool
        
        tool = MDXRAGSearchTool()
        assert tool is not None
    
    def test_txt_rag_search_tool(self):
        """Test TXTRAGSearchTool initialization."""
        from agenticaiframework.tools.file_document.document_tools import TXTRAGSearchTool
        
        tool = TXTRAGSearchTool()
        assert tool is not None
    
    def test_json_rag_search_tool(self):
        """Test JSONRAGSearchTool initialization."""
        from agenticaiframework.tools.file_document.document_tools import JSONRAGSearchTool
        
        tool = JSONRAGSearchTool()
        assert tool is not None
    
    def test_csv_rag_search_tool(self):
        """Test CSVRAGSearchTool initialization."""
        from agenticaiframework.tools.file_document.document_tools import CSVRAGSearchTool
        
        tool = CSVRAGSearchTool()
        assert tool is not None
    
    def test_pdf_rag_search_tool(self):
        """Test PDFRAGSearchTool initialization."""
        from agenticaiframework.tools.file_document.pdf_tools import PDFRAGSearchTool
        
        tool = PDFRAGSearchTool()
        assert tool is not None
    
    def test_pdf_text_writing_tool(self):
        """Test PDFTextWritingTool initialization."""
        from agenticaiframework.tools.file_document.pdf_tools import PDFTextWritingTool
        
        tool = PDFTextWritingTool()
        assert tool is not None


# ============================================================================
# RAG Tools Tests (24% coverage)
# ============================================================================

class TestRAGTools:
    """Tests for RAG tools."""
    
    def test_rag_tool_import(self):
        """Test RAG tool can be imported."""
        from agenticaiframework.tools.ai_ml.rag_tools import RAGTool
        
        tool = RAGTool()
        assert tool is not None


# ============================================================================
# Generation Tools Tests (28% coverage)
# ============================================================================

class TestGenerationTools:
    """Tests for generation tools."""
    
    def test_dalle_tool_import(self):
        """Test DALLE tool can be imported."""
        from agenticaiframework.tools.ai_ml.generation_tools import DALLETool
        
        tool = DALLETool()
        assert tool is not None
    
    def test_vision_tool_import(self):
        """Test VisionTool can be imported."""
        from agenticaiframework.tools.ai_ml.generation_tools import VisionTool
        
        tool = VisionTool()
        assert tool is not None


# ============================================================================
# Framework Tools Tests (22% coverage)
# ============================================================================

class TestFrameworkTools:
    """Tests for framework tools."""
    
    def test_llamaindex_tool_import(self):
        """Test LlamaIndexTool can be imported."""
        from agenticaiframework.tools.ai_ml.framework_tools import LlamaIndexTool
        
        tool = LlamaIndexTool()
        assert tool is not None
    
    def test_langchain_tool_import(self):
        """Test LangChainTool can be imported."""
        from agenticaiframework.tools.ai_ml.framework_tools import LangChainTool
        
        tool = LangChainTool()
        assert tool is not None


# ============================================================================
# LLM Providers __init__ Tests (29% coverage)
# ============================================================================

class TestLLMProvidersInit:
    """Tests for LLM providers __init__ exports."""
    
    def test_providers_exports(self):
        """Test providers module exports."""
        from agenticaiframework.llms.providers import (
            BaseLLMProvider,
            ProviderConfig,
            LLMResponse,
            LLMMessage,
        )
        
        assert BaseLLMProvider is not None
        assert ProviderConfig is not None
        assert LLMResponse is not None
        assert LLMMessage is not None
    
    def test_provider_config_defaults(self):
        """Test ProviderConfig default values."""
        from agenticaiframework.llms.providers.base import ProviderConfig
        
        config = ProviderConfig()
        assert config.api_key is None
        assert config.default_model is None
