"""
Comprehensive tests for tools modules to achieve 90% coverage.
Focus on web_scraping, database, file_document tools.
Uses correct class names based on actual module implementations.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from typing import Dict, Any, List
import json


# ============================================================================
# Web Scraping Tools Tests
# ============================================================================

class TestBasicScrapingTools:
    """Tests for basic scraping tools."""
    
    def test_scrape_website_tool_init(self):
        """Test ScrapeWebsiteTool initialization."""
        from agenticaiframework.tools.web_scraping.basic_scraping import ScrapeWebsiteTool
        
        tool = ScrapeWebsiteTool()
        assert tool is not None
        assert tool.user_agent is not None
    
    def test_scrape_website_tool_custom_user_agent(self):
        """Test ScrapeWebsiteTool with custom user agent."""
        from agenticaiframework.tools.web_scraping.basic_scraping import ScrapeWebsiteTool
        
        custom_ua = "CustomBot/1.0"
        tool = ScrapeWebsiteTool(user_agent=custom_ua)
        assert tool.user_agent == custom_ua
    
    def test_scrape_element_tool_init(self):
        """Test ScrapeElementTool initialization."""
        from agenticaiframework.tools.web_scraping.basic_scraping import ScrapeElementTool
        
        tool = ScrapeElementTool()
        assert tool is not None


class TestAdvancedScrapingTools:
    """Tests for advanced scraping tools."""
    
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
    
    def test_spider_scraper_tool_init(self):
        """Test SpiderScraperTool initialization."""
        from agenticaiframework.tools.web_scraping.advanced_scraping import SpiderScraperTool
        
        tool = SpiderScraperTool()
        assert tool is not None
    
    def test_oxylabs_tool_init(self):
        """Test OxylabsScraperTool initialization."""
        from agenticaiframework.tools.web_scraping.advanced_scraping import OxylabsScraperTool
        
        tool = OxylabsScraperTool()
        assert tool is not None
    
    def test_brightdata_tool_init(self):
        """Test BrightDataTool initialization."""
        from agenticaiframework.tools.web_scraping.advanced_scraping import BrightDataTool
        
        tool = BrightDataTool()
        assert tool is not None


class TestBrowserTools:
    """Tests for browser automation tools."""
    
    def test_browserbase_tool_init(self):
        """Test BrowserbaseWebLoaderTool initialization."""
        from agenticaiframework.tools.web_scraping.browser_tools import BrowserbaseWebLoaderTool
        
        tool = BrowserbaseWebLoaderTool()
        assert tool is not None
    
    def test_hyperbrowser_tool_init(self):
        """Test HyperbrowserLoadTool initialization."""
        from agenticaiframework.tools.web_scraping.browser_tools import HyperbrowserLoadTool
        
        tool = HyperbrowserLoadTool()
        assert tool is not None
    
    def test_stagehand_tool_init(self):
        """Test StagehandTool initialization."""
        from agenticaiframework.tools.web_scraping.browser_tools import StagehandTool
        
        tool = StagehandTool()
        assert tool is not None


class TestSeleniumTools:
    """Tests for Selenium tools."""
    
    def test_selenium_scraper_tool_init(self):
        """Test SeleniumScraperTool initialization."""
        from agenticaiframework.tools.web_scraping.selenium_tools import SeleniumScraperTool
        
        tool = SeleniumScraperTool()
        assert tool is not None


class TestFirecrawlTools:
    """Tests for Firecrawl tools."""
    
    def test_firecrawl_crawl_tool_init(self):
        """Test FirecrawlCrawlWebsiteTool initialization."""
        from agenticaiframework.tools.web_scraping.firecrawl_tools import FirecrawlCrawlWebsiteTool
        
        tool = FirecrawlCrawlWebsiteTool()
        assert tool is not None
    
    def test_firecrawl_scrape_tool_init(self):
        """Test FirecrawlScrapeWebsiteTool initialization."""
        from agenticaiframework.tools.web_scraping.firecrawl_tools import FirecrawlScrapeWebsiteTool
        
        tool = FirecrawlScrapeWebsiteTool()
        assert tool is not None


# ============================================================================
# Database Tools Tests
# ============================================================================

class TestSQLTools:
    """Tests for SQL database tools."""
    
    def test_mysql_rag_tool_init(self):
        """Test MySQLRAGSearchTool initialization."""
        from agenticaiframework.tools.database.sql_tools import MySQLRAGSearchTool
        
        tool = MySQLRAGSearchTool(
            host="localhost",
            port=3306,
            database="testdb",
            user="testuser"
        )
        assert tool is not None
        assert tool.host == "localhost"
        assert tool.port == 3306
    
    def test_postgresql_rag_tool_init(self):
        """Test PostgreSQLRAGSearchTool initialization."""
        from agenticaiframework.tools.database.sql_tools import PostgreSQLRAGSearchTool
        
        tool = PostgreSQLRAGSearchTool(
            host="localhost",
            port=5432,
            database="testdb",
            user="testuser"
        )
        assert tool is not None
        assert tool.port == 5432
    
    def test_nl2sql_tool_init(self):
        """Test NL2SQLTool initialization."""
        from agenticaiframework.tools.database.sql_tools import NL2SQLTool
        
        tool = NL2SQLTool()
        assert tool is not None
    
    def test_base_sql_tool_properties(self):
        """Test BaseSQLTool properties."""
        from agenticaiframework.tools.database.sql_tools import MySQLRAGSearchTool
        
        tool = MySQLRAGSearchTool(host="testhost", database="testdb", user="user")
        assert tool._connection is None
        tool.close()  # Should not raise


class TestVectorTools:
    """Tests for vector database tools."""
    
    def test_qdrant_tool_init(self):
        """Test QdrantVectorSearchTool initialization."""
        from agenticaiframework.tools.database.vector_tools import QdrantVectorSearchTool
        
        tool = QdrantVectorSearchTool()
        assert tool is not None
    
    def test_weaviate_tool_init(self):
        """Test WeaviateVectorSearchTool initialization."""
        from agenticaiframework.tools.database.vector_tools import WeaviateVectorSearchTool
        
        tool = WeaviateVectorSearchTool()
        assert tool is not None
    
    def test_mongodb_vector_tool_init(self):
        """Test MongoDBVectorSearchTool initialization."""
        from agenticaiframework.tools.database.vector_tools import MongoDBVectorSearchTool
        
        tool = MongoDBVectorSearchTool()
        assert tool is not None


class TestSnowflakeTools:
    """Tests for Snowflake tools."""
    
    def test_snowflake_search_tool_init(self):
        """Test SnowflakeSearchTool initialization."""
        from agenticaiframework.tools.database.snowflake_tools import SnowflakeSearchTool
        
        tool = SnowflakeSearchTool()
        assert tool is not None
    
    def test_singlestore_tool_init(self):
        """Test SingleStoreSearchTool initialization."""
        from agenticaiframework.tools.database.snowflake_tools import SingleStoreSearchTool
        
        tool = SingleStoreSearchTool()
        assert tool is not None


# ============================================================================
# File Document Tools Tests  
# ============================================================================

class TestDocumentTools:
    """Tests for document tools."""
    
    def test_docx_rag_tool_init(self):
        """Test DOCXRAGSearchTool initialization."""
        from agenticaiframework.tools.file_document.document_tools import DOCXRAGSearchTool
        
        tool = DOCXRAGSearchTool()
        assert tool is not None
    
    def test_mdx_rag_tool_init(self):
        """Test MDXRAGSearchTool initialization."""
        from agenticaiframework.tools.file_document.document_tools import MDXRAGSearchTool
        
        tool = MDXRAGSearchTool()
        assert tool is not None
    
    def test_xml_rag_tool_init(self):
        """Test XMLRAGSearchTool initialization."""
        from agenticaiframework.tools.file_document.document_tools import XMLRAGSearchTool
        
        tool = XMLRAGSearchTool()
        assert tool is not None
    
    def test_txt_rag_tool_init(self):
        """Test TXTRAGSearchTool initialization."""
        from agenticaiframework.tools.file_document.document_tools import TXTRAGSearchTool
        
        tool = TXTRAGSearchTool()
        assert tool is not None
    
    def test_json_rag_tool_init(self):
        """Test JSONRAGSearchTool initialization."""
        from agenticaiframework.tools.file_document.document_tools import JSONRAGSearchTool
        
        tool = JSONRAGSearchTool()
        assert tool is not None
    
    def test_csv_rag_tool_init(self):
        """Test CSVRAGSearchTool initialization."""
        from agenticaiframework.tools.file_document.document_tools import CSVRAGSearchTool
        
        tool = CSVRAGSearchTool()
        assert tool is not None


class TestDirectoryTools:
    """Tests for directory tools."""
    
    def test_directory_rag_tool_init(self):
        """Test DirectoryRAGSearchTool initialization."""
        from agenticaiframework.tools.file_document.directory_tools import DirectoryRAGSearchTool
        
        tool = DirectoryRAGSearchTool()
        assert tool is not None


class TestFileTools:
    """Tests for file tools."""
    
    def test_file_read_tool_init(self):
        """Test FileReadTool initialization."""
        from agenticaiframework.tools.file_document.file_tools import FileReadTool
        
        tool = FileReadTool()
        assert tool is not None
    
    def test_file_write_tool_init(self):
        """Test FileWriteTool initialization."""
        from agenticaiframework.tools.file_document.file_tools import FileWriteTool
        
        tool = FileWriteTool()
        assert tool is not None
    
    def test_directory_read_tool_init(self):
        """Test DirectoryReadTool initialization."""
        from agenticaiframework.tools.file_document.file_tools import DirectoryReadTool
        
        tool = DirectoryReadTool()
        assert tool is not None


class TestPDFTools:
    """Tests for PDF tools."""
    
    def test_pdf_rag_tool_init(self):
        """Test PDFRAGSearchTool initialization."""
        from agenticaiframework.tools.file_document.pdf_tools import PDFRAGSearchTool
        
        tool = PDFRAGSearchTool()
        assert tool is not None
    
    def test_pdf_text_writing_tool_init(self):
        """Test PDFTextWritingTool initialization."""
        from agenticaiframework.tools.file_document.pdf_tools import PDFTextWritingTool
        
        tool = PDFTextWritingTool()
        assert tool is not None


class TestOCRTools:
    """Tests for OCR tools."""
    
    def test_ocr_tool_init(self):
        """Test OCRTool initialization."""
        from agenticaiframework.tools.file_document.ocr_tools import OCRTool
        
        tool = OCRTool()
        assert tool is not None


# ============================================================================
# AI/ML Tools Tests
# ============================================================================

class TestAIMLCodeTools:
    """Tests for AI/ML code tools."""
    
    def test_code_interpreter_tool_init(self):
        """Test CodeInterpreterTool initialization."""
        from agenticaiframework.tools.ai_ml.code_tools import CodeInterpreterTool
        
        tool = CodeInterpreterTool()
        assert tool is not None
    
    def test_js_code_interpreter_tool_init(self):
        """Test JavaScriptCodeInterpreterTool initialization."""
        from agenticaiframework.tools.ai_ml.code_tools import JavaScriptCodeInterpreterTool
        
        tool = JavaScriptCodeInterpreterTool()
        assert tool is not None


class TestAIMLGenerationTools:
    """Tests for AI/ML generation tools."""
    
    def test_dalle_tool_init(self):
        """Test DALLETool initialization."""
        from agenticaiframework.tools.ai_ml.generation_tools import DALLETool
        
        tool = DALLETool()
        assert tool is not None
    
    def test_vision_tool_init(self):
        """Test VisionTool initialization."""
        from agenticaiframework.tools.ai_ml.generation_tools import VisionTool
        
        tool = VisionTool()
        assert tool is not None


class TestRAGTools:
    """Tests for RAG tools."""
    
    def test_rag_tool_init(self):
        """Test RAGTool initialization."""
        from agenticaiframework.tools.ai_ml.rag_tools import RAGTool
        
        tool = RAGTool()
        assert tool is not None
    
    def test_ai_mind_tool_init(self):
        """Test AIMindTool initialization."""
        from agenticaiframework.tools.ai_ml.rag_tools import AIMindTool
        
        tool = AIMindTool()
        assert tool is not None


class TestFrameworkTools:
    """Tests for framework tools."""
    
    def test_langchain_tool_init(self):
        """Test LangChainTool initialization."""
        from agenticaiframework.tools.ai_ml.framework_tools import LangChainTool
        
        tool = LangChainTool()
        assert tool is not None
    
    def test_llamaindex_tool_init(self):
        """Test LlamaIndexTool initialization."""
        from agenticaiframework.tools.ai_ml.framework_tools import LlamaIndexTool
        
        tool = LlamaIndexTool()
        assert tool is not None


# ============================================================================
# Tool Base Classes Tests
# ============================================================================

class TestToolBase:
    """Tests for tool base classes."""
    
    def test_tool_config(self):
        """Test ToolConfig."""
        from agenticaiframework.tools.base import ToolConfig
        
        config = ToolConfig(
            name="TestTool",
            description="A test tool",
            timeout=60.0,
            retry_count=5
        )
        assert config.name == "TestTool"
        assert config.description == "A test tool"
        assert config.timeout == 60.0
        assert config.retry_count == 5
    
    def test_tool_config_defaults(self):
        """Test ToolConfig defaults."""
        from agenticaiframework.tools.base import ToolConfig
        
        config = ToolConfig(name="test")
        assert config.name == "test"
        # Check default values exist
        assert hasattr(config, 'timeout')
        assert hasattr(config, 'retry_count')
    
    def test_tool_result(self):
        """Test ToolResult."""
        from agenticaiframework.tools.base import ToolResult, ToolStatus
        
        result = ToolResult(
            tool_name="test_tool",
            status=ToolStatus.SUCCESS,
            data={"key": "value"},
            error=None
        )
        assert result.is_success is True
        assert result.data == {"key": "value"}
        assert result.tool_name == "test_tool"
        
        # Test to_dict method
        result_dict = result.to_dict()
        assert result_dict['tool_name'] == "test_tool"
        assert result_dict['status'] == "success"
    
    def test_tool_status_enum(self):
        """Test ToolStatus enum."""
        from agenticaiframework.tools.base import ToolStatus
        
        assert ToolStatus.SUCCESS is not None
        assert ToolStatus.ERROR is not None
        assert ToolStatus.PENDING is not None
        assert ToolStatus.TIMEOUT is not None


class TestToolRegistry:
    """Tests for tool registry."""
    
    def test_tool_registry_init(self):
        """Test ToolRegistry initialization."""
        from agenticaiframework.tools.registry import ToolRegistry
        
        registry = ToolRegistry()
        assert registry is not None
    
    def test_tool_category_enum(self):
        """Test ToolCategory enum."""
        from agenticaiframework.tools.registry import ToolCategory
        
        assert ToolCategory is not None
    
    def test_tool_metadata(self):
        """Test ToolMetadata."""
        from agenticaiframework.tools.registry import ToolMetadata
        
        metadata = ToolMetadata(
            name="test_tool",
            description="A test tool",
            category="testing"
        )
        assert metadata.name == "test_tool"


class TestToolExecutor:
    """Tests for tool executor."""
    
    def test_tool_executor_init(self):
        """Test ToolExecutor initialization."""
        from agenticaiframework.tools.executor import ToolExecutor
        
        executor = ToolExecutor()
        assert executor is not None
    
    def test_execution_context(self):
        """Test ExecutionContext."""
        from agenticaiframework.tools.executor import ExecutionContext
        
        context = ExecutionContext()
        assert context is not None
    
    def test_execution_plan(self):
        """Test ExecutionPlan."""
        from agenticaiframework.tools.executor import ExecutionPlan
        
        plan = ExecutionPlan(
            tool_calls=[{"tool_name": "test", "args": {}}],
            parallel=False,
            stop_on_error=True
        )
        assert plan is not None
        assert len(plan.tool_calls) == 1


# ============================================================================
# MCP Compatibility Tests
# ============================================================================

class TestMCPCompatibility:
    """Tests for MCP compatibility layer."""
    
    def test_mcp_tool_adapter_init(self):
        """Test MCPToolAdapter initialization."""
        from agenticaiframework.tools.mcp_compat import MCPToolAdapter
        from agenticaiframework.tools.base import BaseTool, ToolConfig
        
        # Create a mock tool to adapt
        class MockTool(BaseTool):
            def _execute(self, **kwargs):
                return {"result": "success"}
        
        mock_tool = MockTool(ToolConfig(name="mock", description="Mock tool"))
        adapter = MCPToolAdapter(tool=mock_tool)
        assert adapter is not None
    
    def test_mcp_bridge_init(self):
        """Test MCPBridge initialization."""
        from agenticaiframework.tools.mcp_compat import MCPBridge
        
        bridge = MCPBridge()
        assert bridge is not None
    
    def test_legacy_mcp_tool_wrapper_init(self):
        """Test LegacyMCPToolWrapper initialization."""
        from agenticaiframework.tools.mcp_compat import LegacyMCPToolWrapper
        from unittest.mock import Mock
        
        # Create a mock MCP tool
        mock_mcp_tool = Mock()
        mock_mcp_tool.name = "test_mcp_tool"
        mock_mcp_tool.description = "A mock MCP tool"
        
        wrapper = LegacyMCPToolWrapper(mcp_tool=mock_mcp_tool)
        assert wrapper is not None


# ============================================================================
# Agent Integration Tests
# ============================================================================

class TestAgentIntegration:
    """Tests for agent integration tools."""
    
    def test_agent_tool_binding_init(self):
        """Test AgentToolBinding initialization."""
        from agenticaiframework.tools.agent_integration import AgentToolBinding
        
        binding = AgentToolBinding(
            agent_id="test_agent_id",
            agent_name="test_agent"
        )
        assert binding is not None
        assert binding.agent_id == "test_agent_id"
        assert binding.agent_name == "test_agent"
    
    def test_agent_tool_manager_init(self):
        """Test AgentToolManager initialization."""
        from agenticaiframework.tools.agent_integration import AgentToolManager
        
        manager = AgentToolManager()
        assert manager is not None
