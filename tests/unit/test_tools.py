"""
Comprehensive tests for the Tools Framework.

Tests:
- BaseTool and AsyncBaseTool
- ToolRegistry and registration
- ToolExecutor execution
- AgentToolManager integration
- MCP compatibility
"""

import pytest
import asyncio
from unittest.mock import Mock, patch

from agenticaiframework.tools import (
    # Base classes
    BaseTool,
    AsyncBaseTool,
    ToolResult,
    ToolConfig,
    ToolStatus,
    # Registry
    ToolCategory,
    ToolMetadata,
    ToolRegistry,
    register_tool,
    # Executor
    ExecutionContext,
    ExecutionPlan,
    ToolExecutor,
    # Agent Integration
    AgentToolBinding,
    AgentToolManager,
    # MCP
    MCPToolAdapter,
    MCPBridge,
    wrap_mcp_tool,
    convert_to_mcp,
)
from agenticaiframework import Agent


# =============================================================================
# Test Fixtures
# =============================================================================

class SimpleTool(BaseTool):
    """Simple test tool."""
    
    def __init__(self, config=None):
        super().__init__(config or ToolConfig(
            name="SimpleTool",
            description="A simple test tool"
        ))
    
    def _execute(self, value: int) -> int:
        return value * 2


class FailingTool(BaseTool):
    """Tool that always fails."""
    
    def __init__(self, config=None):
        super().__init__(config or ToolConfig(
            name="FailingTool",
            description="A tool that fails",
            retry_count=1
        ))
    
    def _execute(self, **kwargs):
        raise ValueError("Tool failed")


class AsyncTestTool(AsyncBaseTool):
    """Async test tool."""
    
    def __init__(self, config=None):
        super().__init__(config or ToolConfig(
            name="AsyncTestTool",
            description="An async test tool"
        ))
    
    async def _execute_async(self, value: int) -> int:
        await asyncio.sleep(0.01)
        return value * 3


@pytest.fixture
def registry():
    """Create a fresh registry for each test."""
    reg = ToolRegistry.__new__(ToolRegistry)
    reg._initialized = False
    reg.__init__()
    reg.clear()
    return reg


@pytest.fixture
def executor(registry):
    """Create executor with test registry."""
    return ToolExecutor(registry=registry)


@pytest.fixture
def agent():
    """Create a test agent."""
    return Agent(
        name="TestAgent",
        role="Testing",
        capabilities=["test"],
        config={}
    )


@pytest.fixture
def agent_tool_manager(registry, executor):
    """Create agent tool manager with test instances."""
    return AgentToolManager(registry=registry, executor=executor)


# =============================================================================
# BaseTool Tests
# =============================================================================

class TestBaseTool:
    """Tests for BaseTool class."""
    
    def test_tool_creation(self):
        """Test tool can be created."""
        tool = SimpleTool()
        assert tool.name == "SimpleTool"
        assert tool.description == "A simple test tool"
    
    def test_tool_execution(self):
        """Test tool executes correctly."""
        tool = SimpleTool()
        result = tool.execute(value=5)
        
        assert result.is_success
        assert result.data == 10
        assert result.status == ToolStatus.SUCCESS
    
    def test_tool_execution_time_tracked(self):
        """Test execution time is tracked."""
        tool = SimpleTool()
        result = tool.execute(value=1)
        
        assert result.execution_time >= 0
    
    def test_tool_caching(self):
        """Test result caching."""
        tool = SimpleTool()
        
        result1 = tool.execute(value=5)
        result2 = tool.execute(value=5)
        
        assert result1.data == result2.data
        assert result2.metadata.get('cached') is True
    
    def test_tool_cache_disabled(self):
        """Test caching can be disabled."""
        config = ToolConfig(name="NoCacheTool", cache_enabled=False)
        tool = SimpleTool(config)
        
        result1 = tool.execute(value=5)
        result2 = tool.execute(value=5)
        
        assert result2.metadata.get('cached') is not True
    
    def test_tool_clear_cache(self):
        """Test cache clearing."""
        tool = SimpleTool()
        tool.execute(value=5)
        
        assert len(tool._cache) > 0
        tool.clear_cache()
        assert len(tool._cache) == 0
    
    def test_tool_stats(self):
        """Test tool statistics."""
        tool = SimpleTool()
        tool.execute(value=1)
        tool.execute(value=2)
        
        stats = tool.get_stats()
        
        assert stats['execution_count'] == 2
        assert stats['error_count'] == 0
        assert stats['success_rate'] == 1.0
    
    def test_tool_error_handling(self):
        """Test error handling."""
        tool = FailingTool()
        result = tool.execute()
        
        assert not result.is_success
        assert result.status == ToolStatus.ERROR
        assert "Tool failed" in result.error
    
    def test_tool_hooks(self):
        """Test hook callbacks."""
        tool = SimpleTool()
        before_called = []
        after_called = []
        
        tool.add_hook('before_execute', lambda x: before_called.append(x))
        tool.add_hook('after_execute', lambda x: after_called.append(x))
        
        tool.execute(value=5)
        
        assert len(before_called) == 1
        assert len(after_called) == 1


class TestAsyncBaseTool:
    """Tests for AsyncBaseTool class."""
    
    def test_async_tool_sync_execution(self):
        """Test async tool can execute synchronously."""
        tool = AsyncTestTool()
        result = tool.execute(value=5)
        
        assert result.is_success
        assert result.data == 15
    
    def test_async_tool_async_execution(self):
        """Test async tool executes asynchronously."""
        import asyncio
        
        async def run_test():
            tool = AsyncTestTool()
            result = await tool.execute_async(value=5)
            return result
        
        result = asyncio.run(run_test())
        
        assert result.is_success
        assert result.data == 15


# =============================================================================
# ToolResult Tests
# =============================================================================

class TestToolResult:
    """Tests for ToolResult class."""
    
    def test_result_creation(self):
        """Test result can be created."""
        result = ToolResult(
            tool_name="TestTool",
            status=ToolStatus.SUCCESS,
            data={"key": "value"}
        )
        
        assert result.tool_name == "TestTool"
        assert result.is_success
    
    def test_result_to_dict(self):
        """Test result serialization."""
        result = ToolResult(
            tool_name="TestTool",
            status=ToolStatus.SUCCESS,
            data=42
        )
        
        result_dict = result.to_dict()
        
        assert result_dict['tool_name'] == "TestTool"
        assert result_dict['status'] == "success"
        assert result_dict['data'] == 42


# =============================================================================
# ToolRegistry Tests
# =============================================================================

class TestToolRegistry:
    """Tests for ToolRegistry class."""
    
    def test_register_tool(self, registry):
        """Test tool registration."""
        registry.register(SimpleTool, category=ToolCategory.CUSTOM)
        
        assert "SimpleTool" in registry.list_tools()
    
    def test_get_tool_instance(self, registry):
        """Test getting tool instance."""
        registry.register(SimpleTool)
        
        tool = registry.get_tool("SimpleTool")
        
        assert tool is not None
        assert isinstance(tool, SimpleTool)
    
    def test_get_tool_cached(self, registry):
        """Test tool instances are cached."""
        registry.register(SimpleTool)
        
        tool1 = registry.get_tool("SimpleTool")
        tool2 = registry.get_tool("SimpleTool")
        
        assert tool1 is tool2
    
    def test_get_tool_not_cached(self, registry):
        """Test getting uncached tool instances."""
        registry.register(SimpleTool)
        
        tool1 = registry.get_tool("SimpleTool", use_cache=False)
        tool2 = registry.get_tool("SimpleTool", use_cache=False)
        
        assert tool1 is not tool2
    
    def test_list_by_category(self, registry):
        """Test listing tools by category."""
        registry.register(SimpleTool, category=ToolCategory.CUSTOM)
        registry.register(AsyncTestTool, category=ToolCategory.AI_ML)
        
        by_category = registry.list_by_category()
        
        assert "custom" in by_category
        assert "ai_ml" in by_category
    
    def test_search_tools(self, registry):
        """Test tool search."""
        registry.register(SimpleTool)
        
        results = registry.search_tools("simple")
        
        assert "SimpleTool" in results
    
    def test_unregister_tool(self, registry):
        """Test tool unregistration."""
        registry.register(SimpleTool)
        assert "SimpleTool" in registry.list_tools()
        
        registry.unregister("SimpleTool")
        assert "SimpleTool" not in registry.list_tools()
    
    def test_get_metadata(self, registry):
        """Test getting tool metadata."""
        metadata = ToolMetadata(
            name="SimpleTool",
            description="Test tool",
            category=ToolCategory.CUSTOM,
            tags=["test", "demo"]
        )
        registry.register(SimpleTool, metadata=metadata)
        
        retrieved = registry.get_metadata("SimpleTool")
        
        assert retrieved.tags == ["test", "demo"]


# =============================================================================
# ToolExecutor Tests
# =============================================================================

class TestToolExecutor:
    """Tests for ToolExecutor class."""
    
    def test_execute_tool(self, registry, executor):
        """Test tool execution."""
        registry.register(SimpleTool)
        
        result = executor.execute("SimpleTool", value=5)
        
        assert result.is_success
        assert result.data == 10
    
    def test_execute_with_context(self, registry, executor, agent):
        """Test execution with context."""
        registry.register(SimpleTool)
        
        context = ExecutionContext(
            agent_id=agent.id,
            agent_name=agent.name
        )
        
        result = executor.execute("SimpleTool", context, value=5)
        
        assert result.metadata['agent_id'] == agent.id
    
    def test_execute_nonexistent_tool(self, executor):
        """Test executing nonexistent tool."""
        result = executor.execute("NonexistentTool")
        
        assert not result.is_success
        assert "not found" in result.error.lower()
    
    def test_execute_batch_sequential(self, registry, executor):
        """Test sequential batch execution."""
        registry.register(SimpleTool)
        
        plan = ExecutionPlan(
            tool_calls=[
                {'tool': 'SimpleTool', 'params': {'value': 1}},
                {'tool': 'SimpleTool', 'params': {'value': 2}},
            ],
            parallel=False
        )
        
        results = executor.execute_batch(plan)
        
        assert len(results) == 2
        assert results[0].data == 2
        assert results[1].data == 4
    
    def test_execute_batch_parallel(self, registry, executor):
        """Test parallel batch execution."""
        registry.register(SimpleTool)
        
        plan = ExecutionPlan(
            tool_calls=[
                {'tool': 'SimpleTool', 'params': {'value': 1}},
                {'tool': 'SimpleTool', 'params': {'value': 2}},
            ],
            parallel=True
        )
        
        results = executor.execute_batch(plan)
        
        assert len(results) == 2
        assert all(r.is_success for r in results)
    
    def test_execution_history(self, registry, executor):
        """Test execution history tracking."""
        registry.register(SimpleTool)
        
        executor.execute("SimpleTool", value=1)
        executor.execute("SimpleTool", value=2)
        
        history = executor.get_history()
        
        assert len(history) >= 2
    
    def test_executor_stats(self, registry, executor):
        """Test executor statistics."""
        registry.register(SimpleTool)
        
        executor.execute("SimpleTool", value=1)
        
        stats = executor.get_stats()
        
        assert stats['total_executions'] >= 1


# =============================================================================
# AgentToolManager Tests
# =============================================================================

class TestAgentToolManager:
    """Tests for AgentToolManager class."""
    
    def test_bind_tools(self, registry, agent_tool_manager, agent):
        """Test binding tools to agent."""
        registry.register(SimpleTool)
        
        binding = agent_tool_manager.bind_tools(agent, ["SimpleTool"])
        
        assert "SimpleTool" in binding.tools
    
    def test_unbind_tools(self, registry, agent_tool_manager, agent):
        """Test unbinding tools from agent."""
        registry.register(SimpleTool)
        
        agent_tool_manager.bind_tools(agent, ["SimpleTool"])
        agent_tool_manager.unbind_tools(agent, ["SimpleTool"])
        
        tools = agent_tool_manager.get_agent_tools(agent)
        assert "SimpleTool" not in tools
    
    def test_can_use_tool(self, registry, agent_tool_manager, agent):
        """Test checking tool authorization."""
        registry.register(SimpleTool)
        
        agent_tool_manager.bind_tools(agent, ["SimpleTool"])
        
        assert agent_tool_manager.can_use_tool(agent, "SimpleTool")
        assert not agent_tool_manager.can_use_tool(agent, "OtherTool")
    
    def test_execute_tool_through_agent(self, registry, agent_tool_manager, agent):
        """Test executing tool through agent."""
        registry.register(SimpleTool)
        
        agent_tool_manager.bind_tools(agent, ["SimpleTool"])
        result = agent_tool_manager.execute_tool(agent, "SimpleTool", value=5)
        
        assert result.is_success
        assert result.data == 10
    
    def test_execute_unauthorized_tool(self, registry, agent_tool_manager, agent):
        """Test executing unauthorized tool fails."""
        registry.register(SimpleTool)
        
        # Don't bind tool
        result = agent_tool_manager.execute_tool(agent, "SimpleTool", value=5)
        
        assert not result.is_success
        assert "not authorized" in result.error.lower()
    
    def test_discover_tools(self, registry, agent_tool_manager, agent):
        """Test tool discovery."""
        registry.register(SimpleTool)
        registry.register(AsyncTestTool)
        
        agent_tool_manager.bind_tools(agent, ["SimpleTool"])
        
        discovered = agent_tool_manager.discover_tools(agent)
        
        assert len(discovered) >= 2
        
        simple_info = next(d for d in discovered if d['name'] == 'SimpleTool')
        assert simple_info['bound'] is True
    
    def test_get_tool_schema(self, registry, agent_tool_manager):
        """Test getting MCP schema."""
        metadata = ToolMetadata(
            name="SimpleTool",
            description="A simple tool",
            category=ToolCategory.CUSTOM,
            input_schema={'type': 'object', 'properties': {'value': {'type': 'integer'}}}
        )
        registry.register(SimpleTool, metadata=metadata)
        
        schema = agent_tool_manager.get_tool_schema("SimpleTool")
        
        assert schema['name'] == "SimpleTool"
        assert 'parameters' in schema


# =============================================================================
# MCP Compatibility Tests
# =============================================================================

class TestMCPCompatibility:
    """Tests for MCP protocol compatibility."""
    
    def test_convert_to_mcp(self):
        """Test converting BaseTool to MCP adapter."""
        tool = SimpleTool()
        adapter = convert_to_mcp(tool)
        
        assert adapter.name == "SimpleTool"
        assert hasattr(adapter, 'execute')
    
    def test_mcp_adapter_execute(self):
        """Test MCP adapter execution."""
        tool = SimpleTool()
        adapter = convert_to_mcp(tool)
        
        result = adapter.execute(value=5)
        
        assert result == 10
    
    def test_mcp_adapter_schema(self):
        """Test MCP adapter schema generation."""
        tool = SimpleTool()
        adapter = convert_to_mcp(tool)
        
        schema = adapter.to_mcp_schema()
        
        assert 'name' in schema
        assert 'description' in schema
        assert 'inputSchema' in schema
    
    def test_mcp_bridge_execute(self, registry):
        """Test MCP bridge execution."""
        registry.register(SimpleTool)
        bridge = MCPBridge(registry=registry)
        
        response = bridge.execute_mcp_call("SimpleTool", {"value": 5})
        
        assert response['isError'] is False
        assert "10" in response['content'][0]['text']
    
    def test_mcp_bridge_error(self, registry):
        """Test MCP bridge error handling."""
        bridge = MCPBridge(registry=registry)
        
        response = bridge.execute_mcp_call("NonexistentTool", {})
        
        assert response['isError'] is True


# =============================================================================
# Integration Tests
# =============================================================================

class TestToolsIntegration:
    """Integration tests for tools framework."""
    
    def test_full_workflow(self, registry, agent):
        """Test complete tool workflow."""
        # Register tools
        registry.register(SimpleTool, category=ToolCategory.CUSTOM)
        
        # Create executor and manager
        executor = ToolExecutor(registry=registry)
        manager = AgentToolManager(registry=registry, executor=executor)
        
        # Bind tools to agent
        manager.bind_tools(agent, ["SimpleTool"])
        
        # Execute through agent
        result = manager.execute_tool(agent, "SimpleTool", value=10)
        
        assert result.is_success
        assert result.data == 20
        
        # Check stats
        usage = manager.get_usage_stats(agent.id)
        assert usage.get("SimpleTool") == 1
    
    def test_async_workflow(self, registry, agent):
        """Test async tool workflow."""
        import asyncio
        
        registry.register(AsyncTestTool)
        
        executor = ToolExecutor(registry=registry)
        manager = AgentToolManager(registry=registry, executor=executor)
        
        manager.bind_tools(agent, ["AsyncTestTool"])
        
        async def run_test():
            return await manager.execute_tool_async(agent, "AsyncTestTool", value=5)
        
        result = asyncio.run(run_test())
        
        assert result.is_success
        assert result.data == 15
