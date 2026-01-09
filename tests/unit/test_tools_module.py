"""
Comprehensive tests for tools module.

Tests for:
- BaseTool and AsyncBaseTool
- ToolRegistry
- ToolExecutor
"""

import pytest
import time
from unittest.mock import Mock, patch


class TestToolConfig:
    """Tests for ToolConfig."""
    
    def test_config_creation(self):
        """Test ToolConfig creation."""
        from agenticaiframework.tools.base import ToolConfig
        
        config = ToolConfig(
            name="test_tool",
            description="A test tool",
            timeout=60.0
        )
        
        assert config.name == "test_tool"
        assert config.timeout == 60.0
    
    def test_config_defaults(self):
        """Test ToolConfig default values."""
        from agenticaiframework.tools.base import ToolConfig
        
        config = ToolConfig(name="test")
        
        assert config.version == "1.0.0"
        assert config.timeout == 30.0
        assert config.retry_count == 3


class TestToolResult:
    """Tests for ToolResult."""
    
    def test_result_success(self):
        """Test ToolResult with success."""
        from agenticaiframework.tools.base import ToolResult, ToolStatus
        
        result = ToolResult(
            tool_name="test",
            status=ToolStatus.SUCCESS,
            data={"key": "value"}
        )
        
        assert result.is_success
        assert result.data["key"] == "value"
    
    def test_result_error(self):
        """Test ToolResult with error."""
        from agenticaiframework.tools.base import ToolResult, ToolStatus
        
        result = ToolResult(
            tool_name="test",
            status=ToolStatus.ERROR,
            error="Something went wrong"
        )
        
        assert not result.is_success
        assert result.error == "Something went wrong"
    
    def test_result_to_dict(self):
        """Test ToolResult to_dict method."""
        from agenticaiframework.tools.base import ToolResult, ToolStatus
        
        result = ToolResult(
            tool_name="test",
            status=ToolStatus.SUCCESS,
            data="test_data"
        )
        
        d = result.to_dict()
        assert d['tool_name'] == "test"
        assert d['status'] == "success"


class TestToolStatus:
    """Tests for ToolStatus enum."""
    
    def test_status_values(self):
        """Test ToolStatus values."""
        from agenticaiframework.tools.base import ToolStatus
        
        assert ToolStatus.SUCCESS.value == "success"
        assert ToolStatus.ERROR.value == "error"
        assert ToolStatus.PENDING.value == "pending"
        assert ToolStatus.TIMEOUT.value == "timeout"


class TestBaseTool:
    """Tests for BaseTool."""
    
    def test_concrete_tool(self):
        """Test creating a concrete tool."""
        from agenticaiframework.tools.base import BaseTool, ToolConfig
        
        class ConcreteTool(BaseTool):
            def _execute(self, **kwargs):
                return {"result": kwargs.get("input", "default")}
        
        tool = ConcreteTool()
        assert tool is not None
        assert tool.name == "ConcreteTool"
    
    def test_tool_execute(self):
        """Test tool execution."""
        from agenticaiframework.tools.base import BaseTool, ToolConfig
        
        class ConcreteTool(BaseTool):
            def _execute(self, **kwargs):
                return {"result": kwargs.get("input", "default")}
        
        tool = ConcreteTool()
        result = tool.execute(input="test")
        
        assert result.is_success
        assert result.data["result"] == "test"
    
    def test_tool_with_config(self):
        """Test tool with custom config."""
        from agenticaiframework.tools.base import BaseTool, ToolConfig
        
        config = ToolConfig(name="MyTool", description="A custom tool")
        
        class ConcreteTool(BaseTool):
            def _execute(self, **kwargs):
                return {}
        
        tool = ConcreteTool(config=config)
        assert tool.name == "MyTool"
        assert tool.description == "A custom tool"


class TestToolRegistry:
    """Tests for ToolRegistry."""
    
    def test_register_tool(self):
        """Test registering a tool."""
        from agenticaiframework.tools.registry import ToolRegistry, ToolCategory
        from agenticaiframework.tools.base import BaseTool
        
        # Create fresh registry instance by resetting singleton
        ToolRegistry._instance = None
        registry = ToolRegistry()
        
        class TestTool(BaseTool):
            def _execute(self, **kwargs):
                return {"result": "test"}
        
        registry.register(TestTool, category=ToolCategory.FILE_DOCUMENT)
        
        assert "TestTool" in registry._tools
    
    def test_get_tool_class(self):
        """Test getting tool class."""
        from agenticaiframework.tools.registry import ToolRegistry, ToolCategory
        from agenticaiframework.tools.base import BaseTool
        
        ToolRegistry._instance = None
        registry = ToolRegistry()
        
        class GetToolTest(BaseTool):
            def _execute(self, **kwargs):
                return {}
        
        registry.register(GetToolTest, category=ToolCategory.FILE_DOCUMENT)
        
        tool_class = registry.get_tool_class("GetToolTest")
        assert tool_class is GetToolTest
    
    def test_get_nonexistent_tool_class(self):
        """Test getting nonexistent tool class."""
        from agenticaiframework.tools.registry import ToolRegistry
        
        ToolRegistry._instance = None
        registry = ToolRegistry()
        
        tool_class = registry.get_tool_class("Nonexistent")
        assert tool_class is None
    
    def test_list_tools(self):
        """Test listing tools."""
        from agenticaiframework.tools.registry import ToolRegistry, ToolCategory
        from agenticaiframework.tools.base import BaseTool
        
        ToolRegistry._instance = None
        registry = ToolRegistry()
        
        class ListTool1(BaseTool):
            def _execute(self, **kwargs):
                return {}
        
        class ListTool2(BaseTool):
            def _execute(self, **kwargs):
                return {}
        
        registry.register(ListTool1, category=ToolCategory.FILE_DOCUMENT)
        registry.register(ListTool2, category=ToolCategory.WEB_SCRAPING)
        
        tools = registry.list_tools()
        assert len(tools) >= 2
    
    def test_list_by_category(self):
        """Test listing tools by category."""
        from agenticaiframework.tools.registry import ToolRegistry, ToolCategory
        from agenticaiframework.tools.base import BaseTool
        
        ToolRegistry._instance = None
        registry = ToolRegistry()
        
        class CatTool1(BaseTool):
            def _execute(self, **kwargs):
                return {}
        
        class CatTool2(BaseTool):
            def _execute(self, **kwargs):
                return {}
        
        registry.register(CatTool1, category=ToolCategory.FILE_DOCUMENT)
        registry.register(CatTool2, category=ToolCategory.DATABASE)
        
        # list_by_category returns dict grouped by category
        tools_by_cat = registry.list_by_category()
        assert "file_document" in tools_by_cat
        assert "CatTool1" in tools_by_cat["file_document"]


class TestToolCategory:
    """Tests for ToolCategory enum."""
    
    def test_categories(self):
        """Test ToolCategory values."""
        from agenticaiframework.tools.registry import ToolCategory
        
        assert ToolCategory.FILE_DOCUMENT.value == "file_document"
        assert ToolCategory.WEB_SCRAPING.value == "web_scraping"
        assert ToolCategory.DATABASE.value == "database"
        assert ToolCategory.AI_ML.value == "ai_ml"


class TestToolMetadata:
    """Tests for ToolMetadata."""
    
    def test_metadata_creation(self):
        """Test ToolMetadata creation."""
        from agenticaiframework.tools.registry import ToolMetadata, ToolCategory
        
        metadata = ToolMetadata(
            name="TestTool",
            description="A test tool",
            category=ToolCategory.FILE_DOCUMENT,
            version="1.0.0"
        )
        
        assert metadata.name == "TestTool"
        assert metadata.category == ToolCategory.FILE_DOCUMENT
    
    def test_metadata_defaults(self):
        """Test ToolMetadata defaults."""
        from agenticaiframework.tools.registry import ToolMetadata, ToolCategory
        
        metadata = ToolMetadata(
            name="Test",
            description="Test",
            category=ToolCategory.CUSTOM
        )
        
        assert metadata.version == "1.0.0"
        assert metadata.tags == []


class TestExecutionContext:
    """Tests for ExecutionContext."""
    
    def test_context_creation(self):
        """Test ExecutionContext creation."""
        from agenticaiframework.tools.executor import ExecutionContext
        
        context = ExecutionContext(
            agent_id="agent1",
            session_id="session1"
        )
        
        assert context.agent_id == "agent1"
        assert context.session_id == "session1"
    
    def test_context_defaults(self):
        """Test ExecutionContext defaults."""
        from agenticaiframework.tools.executor import ExecutionContext
        
        context = ExecutionContext()
        
        assert context.timeout == 30.0
        assert context.max_retries == 3


class TestExecutionPlan:
    """Tests for ExecutionPlan."""
    
    def test_plan_creation(self):
        """Test ExecutionPlan creation."""
        from agenticaiframework.tools.executor import ExecutionPlan
        
        plan = ExecutionPlan(
            tool_calls=[
                {"tool": "tool1", "args": {"a": 1}},
                {"tool": "tool2", "args": {"b": 2}}
            ]
        )
        
        assert len(plan.tool_calls) == 2
    
    def test_plan_defaults(self):
        """Test ExecutionPlan defaults."""
        from agenticaiframework.tools.executor import ExecutionPlan
        
        plan = ExecutionPlan(tool_calls=[])
        
        assert plan.parallel is False
        assert plan.stop_on_error is True


class TestToolExecutor:
    """Tests for ToolExecutor."""
    
    def test_executor_init(self):
        """Test executor initialization."""
        from agenticaiframework.tools.executor import ToolExecutor
        
        executor = ToolExecutor()
        assert executor is not None
    
    def test_executor_with_custom_registry(self):
        """Test executor with custom registry."""
        from agenticaiframework.tools.executor import ToolExecutor
        from agenticaiframework.tools.registry import ToolRegistry
        
        ToolRegistry._instance = None
        registry = ToolRegistry()
        executor = ToolExecutor(registry=registry)
        
        assert executor.registry is registry


class TestToolsIntegration:
    """Integration tests for tools module."""
    
    def test_tool_lifecycle(self):
        """Test complete tool lifecycle."""
        from agenticaiframework.tools.base import BaseTool, ToolConfig
        
        class LifecycleTool(BaseTool):
            def _execute(self, **kwargs):
                return {"processed": True, "input": kwargs.get("data")}
        
        tool = LifecycleTool()
        result = tool.execute(data="test_data")
        
        assert result.is_success
        assert result.data["processed"] is True
        assert result.data["input"] == "test_data"
    
    def test_tool_caching(self):
        """Test tool result caching."""
        from agenticaiframework.tools.base import BaseTool, ToolConfig
        
        call_count = [0]
        
        class CachingTool(BaseTool):
            def _execute(self, **kwargs):
                call_count[0] += 1
                return {"count": call_count[0]}
        
        tool = CachingTool()
        
        result1 = tool.execute(key="value")
        result2 = tool.execute(key="value")
        
        # Second call should use cache
        if tool.config.cache_enabled:
            assert result1.data == result2.data
