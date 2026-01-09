"""
Tests for AI/ML tools module.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from agenticaiframework.tools.base import ToolConfig


class TestCodeTools:
    """Tests for code-related AI tools."""
    
    def test_code_tools_import(self):
        """Test that code tools can be imported."""
        from agenticaiframework.tools.ai_ml.code_tools import CodeInterpreterTool
        assert CodeInterpreterTool is not None
    
    def test_code_interpreter_init(self):
        """Test CodeInterpreterTool initialization."""
        from agenticaiframework.tools.ai_ml.code_tools import CodeInterpreterTool
        tool = CodeInterpreterTool()
        assert tool.config.name == "CodeInterpreterTool"
    
    def test_code_interpreter_custom_config(self):
        """Test CodeInterpreterTool with custom config."""
        from agenticaiframework.tools.ai_ml.code_tools import CodeInterpreterTool
        config = ToolConfig(name="CustomCodeInterpreter", description="Custom code interpreter")
        tool = CodeInterpreterTool(config=config)
        assert tool.config.name == "CustomCodeInterpreter"


class TestFrameworkTools:
    """Tests for framework integration tools."""
    
    def test_framework_tools_import(self):
        """Test that framework tools can be imported."""
        from agenticaiframework.tools.ai_ml.framework_tools import (
            LlamaIndexTool,
            LangChainTool,
        )
        assert LlamaIndexTool is not None
        assert LangChainTool is not None
    
    def test_llamaindex_init(self):
        """Test LlamaIndexTool initialization."""
        from agenticaiframework.tools.ai_ml.framework_tools import LlamaIndexTool
        tool = LlamaIndexTool()
        assert tool.config.name == "LlamaIndexTool"
    
    def test_langchain_init(self):
        """Test LangChainTool initialization."""
        from agenticaiframework.tools.ai_ml.framework_tools import LangChainTool
        tool = LangChainTool()
        assert tool.config.name == "LangChainTool"
    
    def test_framework_tools_have_description(self):
        """Test framework tools have descriptions."""
        from agenticaiframework.tools.ai_ml.framework_tools import (
            LangChainTool,
            LlamaIndexTool,
        )
        
        langchain = LangChainTool()
        llamaindex = LlamaIndexTool()
        
        assert langchain.config.description is not None
        assert llamaindex.config.description is not None


class TestGenerationTools:
    """Tests for generation tools."""
    
    def test_generation_tools_import(self):
        """Test that generation tools can be imported."""
        from agenticaiframework.tools.ai_ml.generation_tools import (
            DALLETool,
            VisionTool,
        )
        assert DALLETool is not None
        assert VisionTool is not None
    
    def test_dalle_init(self):
        """Test DALLETool initialization."""
        from agenticaiframework.tools.ai_ml.generation_tools import DALLETool
        tool = DALLETool()
        assert tool.config.name == "DALLETool"
    
    def test_vision_init(self):
        """Test VisionTool initialization."""
        from agenticaiframework.tools.ai_ml.generation_tools import VisionTool
        tool = VisionTool()
        assert tool.config.name == "VisionTool"


class TestRAGTools:
    """Tests for RAG (Retrieval-Augmented Generation) tools."""
    
    def test_rag_tools_import(self):
        """Test that RAG tools can be imported."""
        from agenticaiframework.tools.ai_ml.rag_tools import (
            RAGTool,
            AIMindTool,
        )
        assert RAGTool is not None
        assert AIMindTool is not None
    
    def test_rag_tool_init(self):
        """Test RAGTool initialization."""
        from agenticaiframework.tools.ai_ml.rag_tools import RAGTool
        tool = RAGTool()
        assert tool.config.name == "RAGTool"
    
    def test_aimind_init(self):
        """Test AIMindTool initialization."""
        from agenticaiframework.tools.ai_ml.rag_tools import AIMindTool
        tool = AIMindTool()
        assert tool.config.name == "AIMindTool"
    
    def test_rag_tools_have_default_timeout(self):
        """Test RAG tools have default timeout."""
        from agenticaiframework.tools.ai_ml.rag_tools import RAGTool
        tool = RAGTool()
        assert tool.config.timeout == 30.0


class TestAIMLPackageInit:
    """Tests for AI/ML package initialization."""
    
    def test_package_exports(self):
        """Test that package exports main classes."""
        from agenticaiframework.tools.ai_ml import (
            CodeInterpreterTool,
            LangChainTool,
            LlamaIndexTool,
            DALLETool,
            VisionTool,
            RAGTool,
        )
        assert CodeInterpreterTool is not None
        assert LangChainTool is not None
        assert LlamaIndexTool is not None
        assert DALLETool is not None
        assert VisionTool is not None
        assert RAGTool is not None


class TestToolInheritance:
    """Tests for tool inheritance patterns."""
    
    def test_code_tools_inherit_base_tool(self):
        """Test code tools inherit from BaseTool."""
        from agenticaiframework.tools.ai_ml.code_tools import CodeInterpreterTool
        from agenticaiframework.tools.base import BaseTool
        
        tool = CodeInterpreterTool()
        assert isinstance(tool, BaseTool)
    
    def test_framework_tools_inherit_base_tool(self):
        """Test framework tools inherit from BaseTool."""
        from agenticaiframework.tools.ai_ml.framework_tools import LangChainTool
        from agenticaiframework.tools.base import BaseTool
        
        tool = LangChainTool()
        assert isinstance(tool, BaseTool)
    
    def test_vision_tools_inherit_base_tool(self):
        """Test vision tools inherit from BaseTool."""
        from agenticaiframework.tools.ai_ml.generation_tools import VisionTool
        from agenticaiframework.tools.base import BaseTool
        
        tool = VisionTool()
        assert isinstance(tool, BaseTool)
    
    def test_rag_tools_inherit_base_tool(self):
        """Test RAG tools inherit from BaseTool."""
        from agenticaiframework.tools.ai_ml.rag_tools import RAGTool
        from agenticaiframework.tools.base import BaseTool
        
        tool = RAGTool()
        assert isinstance(tool, BaseTool)
    
    def test_dalle_inherits_async_base(self):
        """Test DALLETool inherits from AsyncBaseTool."""
        from agenticaiframework.tools.ai_ml.generation_tools import DALLETool
        from agenticaiframework.tools.base import AsyncBaseTool
        
        tool = DALLETool()
        assert isinstance(tool, AsyncBaseTool)


class TestToolConfigOptions:
    """Tests for tool configuration options."""
    
    def test_tool_with_api_key(self):
        """Test tool with API key configuration."""
        from agenticaiframework.tools.ai_ml.generation_tools import DALLETool
        config = ToolConfig(name="DALLETool", api_key="test-api-key")
        tool = DALLETool(config=config)
        assert tool.config.api_key == "test-api-key"
    
    def test_tool_with_timeout(self):
        """Test tool with timeout configuration."""
        from agenticaiframework.tools.ai_ml.rag_tools import RAGTool
        config = ToolConfig(name="RAGTool", timeout=60.0)
        tool = RAGTool(config=config)
        assert tool.config.timeout == 60.0
    
    def test_tool_with_retry_count(self):
        """Test tool with retry configuration."""
        from agenticaiframework.tools.ai_ml.code_tools import CodeInterpreterTool
        config = ToolConfig(name="CodeInterpreterTool", retry_count=5)
        tool = CodeInterpreterTool(config=config)
        assert tool.config.retry_count == 5
