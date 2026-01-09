#!/usr/bin/env python3
"""Test script to verify all tools import correctly."""

import sys
sys.path.insert(0, '.')

try:
    print("Testing Tools Framework imports...")
    
    # Test base imports
    from agenticaiframework.tools import (
        BaseTool, AsyncBaseTool, ToolResult, ToolConfig, ToolStatus
    )
    print("✅ Base classes imported")
    
    # Test registry imports
    from agenticaiframework.tools import (
        ToolCategory, ToolMetadata, ToolRegistry, tool_registry, register_tool
    )
    print("✅ Registry classes imported")
    
    # Test executor imports
    from agenticaiframework.tools import (
        ExecutionContext, ExecutionPlan, ToolExecutor, tool_executor
    )
    print("✅ Executor classes imported")
    
    # Test agent integration imports
    from agenticaiframework.tools import (
        AgentToolBinding, AgentToolManager, agent_tool_manager
    )
    print("✅ Agent integration classes imported")
    
    # Test MCP compatibility imports
    from agenticaiframework.tools import (
        MCPToolAdapter, MCPBridge, LegacyMCPToolWrapper,
        wrap_mcp_tool, convert_to_mcp, mcp_bridge
    )
    print("✅ MCP compatibility classes imported")
    
    # Test file/document tools
    from agenticaiframework.tools import (
        FileReadTool, FileWriteTool, DirectoryReadTool,
        OCRTool, PDFTextWritingTool, PDFRAGSearchTool,
        DOCXRAGSearchTool, MDXRAGSearchTool, XMLRAGSearchTool,
        TXTRAGSearchTool, JSONRAGSearchTool, CSVRAGSearchTool,
        DirectoryRAGSearchTool
    )
    print("✅ File & Document tools imported (14 tools)")
    
    # Test web scraping tools
    from agenticaiframework.tools import (
        ScrapeWebsiteTool, ScrapeElementTool, ScrapflyScrapeWebsiteTool,
        SeleniumScraperTool, ScrapegraphScrapeTool, SpiderScraperTool,
        BrowserbaseWebLoaderTool, HyperbrowserLoadTool, StagehandTool,
        FirecrawlCrawlWebsiteTool, FirecrawlScrapeWebsiteTool,
        OxylabsScraperTool, BrightDataTool
    )
    print("✅ Web Scraping tools imported (13 tools)")
    
    # Test database tools
    from agenticaiframework.tools import (
        MySQLRAGSearchTool, PostgreSQLRAGSearchTool, SnowflakeSearchTool,
        NL2SQLTool, QdrantVectorSearchTool, WeaviateVectorSearchTool,
        MongoDBVectorSearchTool, SingleStoreSearchTool
    )
    print("✅ Database tools imported (8 tools)")
    
    # Test AI/ML tools
    from agenticaiframework.tools import (
        DALLETool, VisionTool, AIMindTool,
        LlamaIndexTool, LangChainTool, RAGTool, CodeInterpreterTool
    )
    print("✅ AI/ML tools imported (7 tools)")
    
    # Test main package exports
    from agenticaiframework import (
        BaseTool, FileReadTool, DALLETool,
        tool_registry, tool_executor, agent_tool_manager, mcp_bridge
    )
    print("✅ Main package exports work")
    
    print("\n" + "="*50)
    print("✅ All tools and integration components imported!")
    print("="*50)
    
    # Summary
    tools = [
        # Base (5)
        "BaseTool", "AsyncBaseTool", "ToolResult", "ToolConfig", "ToolStatus",
        # Registry (5)
        "ToolCategory", "ToolMetadata", "ToolRegistry", "tool_registry", "register_tool",
        # Executor (4)
        "ExecutionContext", "ExecutionPlan", "ToolExecutor", "tool_executor",
        # Agent Integration (3)
        "AgentToolBinding", "AgentToolManager", "agent_tool_manager",
        # MCP Compatibility (6)
        "MCPToolAdapter", "MCPBridge", "LegacyMCPToolWrapper",
        "wrap_mcp_tool", "convert_to_mcp", "mcp_bridge",
        # File & Document (14)
        "FileReadTool", "FileWriteTool", "DirectoryReadTool", "OCRTool",
        "PDFTextWritingTool", "PDFRAGSearchTool", "DOCXRAGSearchTool",
        "MDXRAGSearchTool", "XMLRAGSearchTool", "TXTRAGSearchTool",
        "JSONRAGSearchTool", "CSVRAGSearchTool", "DirectoryRAGSearchTool",
        # Web Scraping (13)
        "ScrapeWebsiteTool", "ScrapeElementTool", "ScrapflyScrapeWebsiteTool",
        "SeleniumScraperTool", "ScrapegraphScrapeTool", "SpiderScraperTool",
        "BrowserbaseWebLoaderTool", "HyperbrowserLoadTool", "StagehandTool",
        "FirecrawlCrawlWebsiteTool", "FirecrawlScrapeWebsiteTool",
        "OxylabsScraperTool", "BrightDataTool",
        # Database (8)
        "MySQLRAGSearchTool", "PostgreSQLRAGSearchTool", "SnowflakeSearchTool",
        "NL2SQLTool", "QdrantVectorSearchTool", "WeaviateVectorSearchTool",
        "MongoDBVectorSearchTool", "SingleStoreSearchTool",
        # AI/ML (7)
        "DALLETool", "VisionTool", "AIMindTool", "LlamaIndexTool",
        "LangChainTool", "RAGTool", "CodeInterpreterTool"
    ]
    
    print(f"\nTotal exports available: {len(tools)}")
    print("  • Base classes: 5")
    print("  • Registry: 5")
    print("  • Executor: 4")
    print("  • Agent Integration: 3")
    print("  • MCP Compatibility: 6")
    print("  • File & Document Tools: 14")
    print("  • Web Scraping Tools: 13")
    print("  • Database Tools: 8")
    print("  • AI/ML Tools: 7")
    
except Exception as e:
    print(f"❌ Import error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
