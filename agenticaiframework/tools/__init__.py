"""
AgenticAI Framework - Tools Package.

Comprehensive collection of tools for AI agents:
- File & Document tools
- Web Scraping & Browsing tools
- Database & Data tools
- AI & Machine Learning tools
- Agent Integration & Registry
- MCP Protocol Compatibility
"""

# Base classes and types
from .base import (
    BaseTool,
    AsyncBaseTool,
    ToolResult,
    ToolConfig,
    ToolStatus,
)

# Registry and discovery
from .registry import (
    ToolCategory,
    ToolMetadata,
    ToolRegistry,
    tool_registry,
    register_tool,
)

# Executor for running tools
from .executor import (
    ExecutionContext,
    ExecutionPlan,
    ToolExecutor,
    tool_executor,
)

# Agent integration
from .agent_integration import (
    AgentToolBinding,
    AgentToolManager,
    agent_tool_manager,
)

# MCP compatibility
from .mcp_compat import (
    MCPToolAdapter,
    MCPBridge,
    LegacyMCPToolWrapper,
    wrap_mcp_tool,
    convert_to_mcp,
    mcp_bridge,
)

# File & Document Tools
from .file_document import (
    # Core file operations
    FileReadTool,
    FileWriteTool,
    DirectoryReadTool,
    OCRTool,
    PDFTextWritingTool,
    # RAG Search tools
    PDFRAGSearchTool,
    DOCXRAGSearchTool,
    MDXRAGSearchTool,
    XMLRAGSearchTool,
    TXTRAGSearchTool,
    JSONRAGSearchTool,
    CSVRAGSearchTool,
    DirectoryRAGSearchTool,
)

# Web Scraping & Browsing Tools
from .web_scraping import (
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
)

# Database & Data Tools
from .database import (
    MySQLRAGSearchTool,
    PostgreSQLRAGSearchTool,
    SnowflakeSearchTool,
    NL2SQLTool,
    QdrantVectorSearchTool,
    WeaviateVectorSearchTool,
    MongoDBVectorSearchTool,
    SingleStoreSearchTool,
)

# AI & Machine Learning Tools
from .ai_ml import (
    DALLETool,
    VisionTool,
    AIMindTool,
    LlamaIndexTool,
    LangChainTool,
    RAGTool,
    CodeInterpreterTool,
)

__all__ = [
    # Base classes
    'BaseTool',
    'AsyncBaseTool',
    'ToolResult',
    'ToolConfig',
    'ToolStatus',
    
    # Registry
    'ToolCategory',
    'ToolMetadata',
    'ToolRegistry',
    'tool_registry',
    'register_tool',
    
    # Executor
    'ExecutionContext',
    'ExecutionPlan',
    'ToolExecutor',
    'tool_executor',
    
    # Agent Integration
    'AgentToolBinding',
    'AgentToolManager',
    'agent_tool_manager',
    
    # MCP Compatibility
    'MCPToolAdapter',
    'MCPBridge',
    'LegacyMCPToolWrapper',
    'wrap_mcp_tool',
    'convert_to_mcp',
    'mcp_bridge',
    
    # File & Document Tools
    'FileReadTool',
    'FileWriteTool',
    'DirectoryReadTool',
    'OCRTool',
    'PDFTextWritingTool',
    'PDFRAGSearchTool',
    'DOCXRAGSearchTool',
    'MDXRAGSearchTool',
    'XMLRAGSearchTool',
    'TXTRAGSearchTool',
    'JSONRAGSearchTool',
    'CSVRAGSearchTool',
    'DirectoryRAGSearchTool',
    
    # Web Scraping & Browsing Tools
    'ScrapeWebsiteTool',
    'ScrapeElementTool',
    'ScrapflyScrapeWebsiteTool',
    'SeleniumScraperTool',
    'ScrapegraphScrapeTool',
    'SpiderScraperTool',
    'BrowserbaseWebLoaderTool',
    'HyperbrowserLoadTool',
    'StagehandTool',
    'FirecrawlCrawlWebsiteTool',
    'FirecrawlScrapeWebsiteTool',
    'OxylabsScraperTool',
    'BrightDataTool',
    
    # Database & Data Tools
    'MySQLRAGSearchTool',
    'PostgreSQLRAGSearchTool',
    'SnowflakeSearchTool',
    'NL2SQLTool',
    'QdrantVectorSearchTool',
    'WeaviateVectorSearchTool',
    'MongoDBVectorSearchTool',
    'SingleStoreSearchTool',
    
    # AI & Machine Learning Tools
    'DALLETool',
    'VisionTool',
    'AIMindTool',
    'LlamaIndexTool',
    'LangChainTool',
    'RAGTool',
    'CodeInterpreterTool',
]
