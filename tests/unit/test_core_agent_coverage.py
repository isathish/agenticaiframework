"""
Comprehensive tests for core/agent.py to boost coverage.
Targets the Agent class methods and class methods.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime


class TestAgentClassAttributes:
    """Test Agent class-level attributes."""
    
    def test_role_templates_defined(self):
        """Test ROLE_TEMPLATES dict exists and has expected keys."""
        from agenticaiframework.core.agent import Agent
        
        assert hasattr(Agent, 'ROLE_TEMPLATES')
        assert isinstance(Agent.ROLE_TEMPLATES, dict)
        assert 'assistant' in Agent.ROLE_TEMPLATES
        assert 'analyst' in Agent.ROLE_TEMPLATES
        assert 'coder' in Agent.ROLE_TEMPLATES
        assert 'writer' in Agent.ROLE_TEMPLATES
        assert 'researcher' in Agent.ROLE_TEMPLATES
    
    def test_role_capabilities_defined(self):
        """Test ROLE_CAPABILITIES dict exists."""
        from agenticaiframework.core.agent import Agent
        
        assert hasattr(Agent, 'ROLE_CAPABILITIES')
        assert isinstance(Agent.ROLE_CAPABILITIES, dict)
        assert 'assistant' in Agent.ROLE_CAPABILITIES
        assert 'coder' in Agent.ROLE_CAPABILITIES
        
    def test_role_templates_values(self):
        """Test role templates have non-empty descriptions."""
        from agenticaiframework.core.agent import Agent
        
        for role, description in Agent.ROLE_TEMPLATES.items():
            assert isinstance(description, str)
            assert len(description) > 10
    
    def test_role_capabilities_values(self):
        """Test role capabilities are lists."""
        from agenticaiframework.core.agent import Agent
        
        for role, capabilities in Agent.ROLE_CAPABILITIES.items():
            assert isinstance(capabilities, list)
            assert len(capabilities) > 0


class TestAgentInit:
    """Test Agent __init__ method."""
    
    def test_basic_init(self):
        """Test basic agent initialization."""
        from agenticaiframework.core.agent import Agent
        
        agent = Agent(
            name="TestAgent",
            role="Test Role",
            capabilities=["test"],
            config={}
        )
        
        assert agent.name == "TestAgent"
        assert agent.role == "Test Role"
        assert agent.capabilities == ["test"]
        assert agent.status == "initialized"
    
    def test_init_sets_id(self):
        """Test agent ID is UUID."""
        from agenticaiframework.core.agent import Agent
        import uuid
        
        agent = Agent(
            name="TestAgent",
            role="Test Role",
            capabilities=["test"],
            config={}
        )
        
        # Should be valid UUID
        uuid.UUID(agent.id)
        assert len(agent.id) == 36  # UUID format
    
    def test_init_default_memory(self):
        """Test agent memory initialized as empty list."""
        from agenticaiframework.core.agent import Agent
        
        agent = Agent(
            name="TestAgent",
            role="Test Role",
            capabilities=["test"],
            config={}
        )
        
        assert isinstance(agent.memory, list)
        assert len(agent.memory) == 0
    
    def test_init_performance_metrics(self):
        """Test performance metrics initialized."""
        from agenticaiframework.core.agent import Agent
        
        agent = Agent(
            name="TestAgent",
            role="Test Role",
            capabilities=["test"],
            config={}
        )
        
        assert 'total_tasks' in agent.performance_metrics
        assert 'successful_tasks' in agent.performance_metrics
        assert 'failed_tasks' in agent.performance_metrics
        assert agent.performance_metrics['total_tasks'] == 0
    
    def test_init_security_context(self):
        """Test security context initialized."""
        from agenticaiframework.core.agent import Agent
        
        agent = Agent(
            name="TestAgent",
            role="Test Role",
            capabilities=["test"],
            config={}
        )
        
        assert 'created_at' in agent.security_context
        assert 'last_activity' in agent.security_context
        assert 'access_count' in agent.security_context
    
    def test_init_context_manager(self):
        """Test context manager initialized."""
        from agenticaiframework.core.agent import Agent
        
        agent = Agent(
            name="TestAgent",
            role="Test Role",
            capabilities=["test"],
            config={},
            max_context_tokens=8192
        )
        
        assert agent.context_manager is not None
    
    def test_init_with_config(self):
        """Test agent with custom config."""
        from agenticaiframework.core.agent import Agent
        
        config = {"llm": "test", "model": "gpt-4"}
        agent = Agent(
            name="TestAgent",
            role="Test Role",
            capabilities=["test"],
            config=config
        )
        
        assert agent.config == config


class TestAgentStateMethods:
    """Test Agent state management methods."""
    
    def test_start(self):
        """Test start method."""
        from agenticaiframework.core.agent import Agent
        
        agent = Agent(
            name="TestAgent",
            role="Test Role",
            capabilities=["test"],
            config={}
        )
        
        agent.start()
        assert agent.status == "running"
    
    def test_pause(self):
        """Test pause method."""
        from agenticaiframework.core.agent import Agent
        
        agent = Agent(
            name="TestAgent",
            role="Test Role",
            capabilities=["test"],
            config={}
        )
        
        agent.start()
        agent.pause()
        assert agent.status == "paused"
    
    def test_resume(self):
        """Test resume method."""
        from agenticaiframework.core.agent import Agent
        
        agent = Agent(
            name="TestAgent",
            role="Test Role",
            capabilities=["test"],
            config={}
        )
        
        agent.start()
        agent.pause()
        agent.resume()
        assert agent.status == "running"
    
    def test_stop(self):
        """Test stop method."""
        from agenticaiframework.core.agent import Agent
        
        agent = Agent(
            name="TestAgent",
            role="Test Role",
            capabilities=["test"],
            config={}
        )
        
        agent.start()
        agent.stop()
        assert agent.status == "stopped"
    
    def test_state_transitions(self):
        """Test all state transitions."""
        from agenticaiframework.core.agent import Agent
        
        agent = Agent(
            name="TestAgent",
            role="Test Role",
            capabilities=["test"],
            config={}
        )
        
        assert agent.status == "initialized"
        agent.start()
        assert agent.status == "running"
        agent.pause()
        assert agent.status == "paused"
        agent.resume()
        assert agent.status == "running"
        agent.stop()
        assert agent.status == "stopped"


class TestAgentContextMethods:
    """Test Agent context methods."""
    
    def test_add_context(self):
        """Test add_context method."""
        from agenticaiframework.core.agent import Agent
        
        agent = Agent(
            name="TestAgent",
            role="Test Role",
            capabilities=["test"],
            config={}
        )
        
        # Should not raise
        agent.add_context("Test context", importance=0.7)
    
    def test_add_context_default_importance(self):
        """Test add_context with default importance."""
        from agenticaiframework.core.agent import Agent
        
        agent = Agent(
            name="TestAgent",
            role="Test Role",
            capabilities=["test"],
            config={}
        )
        
        agent.add_context("Test context")  # Default importance=0.5
    
    def test_get_context_stats(self):
        """Test get_context_stats method."""
        from agenticaiframework.core.agent import Agent
        
        agent = Agent(
            name="TestAgent",
            role="Test Role",
            capabilities=["test"],
            config={}
        )
        
        stats = agent.get_context_stats()
        assert isinstance(stats, dict)


class TestAgentExecuteTask:
    """Test Agent execute_task method."""
    
    def test_execute_task_success(self):
        """Test execute_task with successful callable."""
        from agenticaiframework.core.agent import Agent
        
        agent = Agent(
            name="TestAgent",
            role="Test Role",
            capabilities=["test"],
            config={}
        )
        
        def test_task(x, y):
            return x + y
        
        result = agent.execute_task(test_task, 1, 2)
        assert result == 3
        assert agent.performance_metrics['successful_tasks'] == 1
    
    def test_execute_task_type_error(self):
        """Test execute_task with TypeError."""
        from agenticaiframework.core.agent import Agent
        
        agent = Agent(
            name="TestAgent",
            role="Test Role",
            capabilities=["test"],
            config={}
        )
        
        def test_task():
            raise TypeError("test error")
        
        result = agent.execute_task(test_task)
        assert result is None
        assert agent.performance_metrics['failed_tasks'] == 1
    
    def test_execute_task_value_error(self):
        """Test execute_task with ValueError."""
        from agenticaiframework.core.agent import Agent
        
        agent = Agent(
            name="TestAgent",
            role="Test Role",
            capabilities=["test"],
            config={}
        )
        
        def test_task():
            raise ValueError("test error")
        
        result = agent.execute_task(test_task)
        assert result is None
        assert agent.performance_metrics['failed_tasks'] == 1
    
    def test_execute_task_key_error(self):
        """Test execute_task with KeyError."""
        from agenticaiframework.core.agent import Agent
        
        agent = Agent(
            name="TestAgent",
            role="Test Role",
            capabilities=["test"],
            config={}
        )
        
        def test_task():
            d = {}
            return d["missing"]
        
        result = agent.execute_task(test_task)
        assert result is None
        assert agent.performance_metrics['failed_tasks'] == 1
    
    def test_execute_task_attribute_error(self):
        """Test execute_task with AttributeError."""
        from agenticaiframework.core.agent import Agent
        
        agent = Agent(
            name="TestAgent",
            role="Test Role",
            capabilities=["test"],
            config={}
        )
        
        def test_task():
            obj = None
            return obj.missing_attr
        
        result = agent.execute_task(test_task)
        assert result is None
        assert agent.performance_metrics['failed_tasks'] == 1
    
    def test_execute_task_generic_exception(self):
        """Test execute_task with generic exception."""
        from agenticaiframework.core.agent import Agent
        
        agent = Agent(
            name="TestAgent",
            role="Test Role",
            capabilities=["test"],
            config={}
        )
        
        def test_task():
            raise RuntimeError("generic error")
        
        result = agent.execute_task(test_task)
        assert result is None
        assert agent.performance_metrics['failed_tasks'] == 1
    
    def test_execute_task_updates_metrics(self):
        """Test execute_task updates metrics correctly."""
        from agenticaiframework.core.agent import Agent
        
        agent = Agent(
            name="TestAgent",
            role="Test Role",
            capabilities=["test"],
            config={}
        )
        
        def test_task():
            return "result"
        
        agent.execute_task(test_task)
        
        assert agent.performance_metrics['total_tasks'] == 1
        assert agent.performance_metrics['total_execution_time'] > 0
    
    def test_execute_task_with_kwargs(self):
        """Test execute_task with keyword arguments."""
        from agenticaiframework.core.agent import Agent
        
        agent = Agent(
            name="TestAgent",
            role="Test Role",
            capabilities=["test"],
            config={}
        )
        
        def test_task(a, b=10):
            return a + b
        
        result = agent.execute_task(test_task, 5, b=20)
        assert result == 25


class TestAgentToolMethods:
    """Test Agent tool-related methods."""
    
    @patch('agenticaiframework.tools.agent_tool_manager')
    def test_bind_tools(self, mock_manager):
        """Test bind_tools method."""
        from agenticaiframework.core.agent import Agent
        
        agent = Agent(
            name="TestAgent",
            role="Test Role",
            capabilities=["test"],
            config={}
        )
        
        agent.bind_tools(["ToolA", "ToolB"])
        # Should not raise
    
    @patch('agenticaiframework.tools.agent_tool_manager')
    def test_get_tool_schemas(self, mock_manager):
        """Test get_tool_schemas method."""
        from agenticaiframework.core.agent import Agent
        
        mock_manager.get_all_schemas.return_value = [{"name": "tool1"}]
        
        agent = Agent(
            name="TestAgent",
            role="Test Role",
            capabilities=["test"],
            config={}
        )
        
        schemas = agent.get_tool_schemas()
        assert isinstance(schemas, list)


class TestAgentGetToolsForRole:
    """Test Agent._get_tools_for_role class method."""
    
    def test_get_tools_analyst(self):
        """Test _get_tools_for_role for analyst."""
        from agenticaiframework.core.agent import Agent
        
        tools = Agent._get_tools_for_role("analyst")
        assert isinstance(tools, list)
        assert "SQLQueryTool" in tools or "DataVisualizationTool" in tools
    
    def test_get_tools_coder(self):
        """Test _get_tools_for_role for coder."""
        from agenticaiframework.core.agent import Agent
        
        tools = Agent._get_tools_for_role("coder")
        assert isinstance(tools, list)
    
    def test_get_tools_researcher(self):
        """Test _get_tools_for_role for researcher."""
        from agenticaiframework.core.agent import Agent
        
        tools = Agent._get_tools_for_role("researcher")
        assert isinstance(tools, list)
    
    def test_get_tools_unknown(self):
        """Test _get_tools_for_role for unknown role."""
        from agenticaiframework.core.agent import Agent
        
        tools = Agent._get_tools_for_role("unknown_role")
        assert tools == []
    
    def test_get_tools_assistant(self):
        """Test _get_tools_for_role for assistant."""
        from agenticaiframework.core.agent import Agent
        
        tools = Agent._get_tools_for_role("assistant")
        assert tools == []
    
    def test_get_tools_writer(self):
        """Test _get_tools_for_role for writer."""
        from agenticaiframework.core.agent import Agent
        
        tools = Agent._get_tools_for_role("writer")
        assert tools == []


class TestAgentFromConfig:
    """Test Agent.from_config class method."""
    
    @patch('agenticaiframework.llms.LLMManager.from_environment')
    @patch('agenticaiframework.guardrails.GuardrailPipeline.minimal')
    @patch('agenticaiframework.tracing.tracer')
    def test_from_config_minimal(self, mock_tracer, mock_pipeline, mock_llm):
        """Test from_config with minimal config."""
        from agenticaiframework.core.agent import Agent
        
        mock_llm.return_value = Mock()
        mock_pipeline.return_value = Mock()
        
        config = {"name": "TestBot"}
        agent = Agent.from_config(config)
        
        assert agent.name == "TestBot"
    
    @patch('agenticaiframework.llms.LLMManager.from_environment')
    @patch('agenticaiframework.guardrails.GuardrailPipeline.minimal')
    @patch('agenticaiframework.tracing.tracer')
    def test_from_config_with_role(self, mock_tracer, mock_pipeline, mock_llm):
        """Test from_config with role template."""
        from agenticaiframework.core.agent import Agent
        
        mock_llm.return_value = Mock()
        mock_pipeline.return_value = Mock()
        
        config = {"name": "AnalystBot", "role": "analyst"}
        agent = Agent.from_config(config)
        
        assert agent.name == "AnalystBot"
        assert "analyst" in agent.role.lower() or "data" in agent.role.lower()
    
    @patch('agenticaiframework.llms.LLMManager.from_environment')
    @patch('agenticaiframework.guardrails.GuardrailPipeline.minimal')
    @patch('agenticaiframework.tracing.tracer')
    def test_from_config_with_capabilities(self, mock_tracer, mock_pipeline, mock_llm):
        """Test from_config with custom capabilities."""
        from agenticaiframework.core.agent import Agent
        
        mock_llm.return_value = Mock()
        mock_pipeline.return_value = Mock()
        
        config = {
            "name": "TestBot",
            "role": "custom role",
            "capabilities": ["custom1", "custom2"]
        }
        agent = Agent.from_config(config)
        
        assert "custom1" in agent.capabilities
        assert "custom2" in agent.capabilities
    
    @patch('agenticaiframework.llms.LLMManager.from_environment')
    @patch('agenticaiframework.guardrails.GuardrailPipeline.minimal')
    @patch('agenticaiframework.tracing.tracer')
    def test_from_config_no_guardrails(self, mock_tracer, mock_pipeline, mock_llm):
        """Test from_config with guardrails disabled."""
        from agenticaiframework.core.agent import Agent
        
        mock_llm.return_value = Mock()
        mock_pipeline.return_value = Mock()
        
        config = {"name": "TestBot", "guardrails": False}
        agent = Agent.from_config(config)
        
        assert agent.name == "TestBot"
    
    @patch('agenticaiframework.llms.LLMManager.from_environment')
    @patch('agenticaiframework.guardrails.GuardrailPipeline.enterprise_defaults')
    @patch('agenticaiframework.tracing.tracer')
    def test_from_config_enterprise_guardrails(self, mock_tracer, mock_pipeline, mock_llm):
        """Test from_config with enterprise guardrails preset."""
        from agenticaiframework.core.agent import Agent
        
        mock_llm.return_value = Mock()
        mock_pipeline.return_value = Mock()
        
        config = {
            "name": "TestBot",
            "guardrails": {"preset": "enterprise"}
        }
        agent = Agent.from_config(config)
        
        assert agent.name == "TestBot"
    
    @patch('agenticaiframework.llms.LLMManager.from_environment')
    @patch('agenticaiframework.guardrails.GuardrailPipeline.safety_only')
    @patch('agenticaiframework.tracing.tracer')
    def test_from_config_safety_guardrails(self, mock_tracer, mock_pipeline, mock_llm):
        """Test from_config with safety guardrails preset."""
        from agenticaiframework.core.agent import Agent
        
        mock_llm.return_value = Mock()
        mock_pipeline.return_value = Mock()
        
        config = {
            "name": "TestBot",
            "guardrails": {"preset": "safety"}
        }
        agent = Agent.from_config(config)
        
        assert agent.name == "TestBot"
    
    @patch('agenticaiframework.llms.LLMManager.from_environment')
    @patch('agenticaiframework.guardrails.GuardrailPipeline.minimal')
    @patch('agenticaiframework.tracing.tracer')
    def test_from_config_no_tracing(self, mock_tracer, mock_pipeline, mock_llm):
        """Test from_config with tracing disabled."""
        from agenticaiframework.core.agent import Agent
        
        mock_llm.return_value = Mock()
        mock_pipeline.return_value = Mock()
        
        config = {"name": "TestBot", "tracing": False}
        agent = Agent.from_config(config)
        
        assert agent.name == "TestBot"
    
    @patch('agenticaiframework.llms.LLMManager.from_environment')
    @patch('agenticaiframework.guardrails.GuardrailPipeline.minimal')
    @patch('agenticaiframework.tracing.tracer')
    def test_from_config_no_auto_start(self, mock_tracer, mock_pipeline, mock_llm):
        """Test from_config with auto_start disabled."""
        from agenticaiframework.core.agent import Agent
        
        mock_llm.return_value = Mock()
        mock_pipeline.return_value = Mock()
        
        config = {"name": "TestBot", "auto_start": False}
        agent = Agent.from_config(config)
        
        assert agent.name == "TestBot"
        assert agent.status == "initialized"  # Not started
    
    @patch('agenticaiframework.llms.LLMManager.from_environment')
    @patch('agenticaiframework.guardrails.GuardrailPipeline.minimal')
    @patch('agenticaiframework.tracing.tracer')
    def test_from_config_with_llm_string(self, mock_tracer, mock_pipeline, mock_llm):
        """Test from_config with LLM as string."""
        from agenticaiframework.core.agent import Agent
        
        mock_llm_instance = Mock()
        mock_llm_instance.active_model = "test-model"
        mock_llm_instance.get_provider.return_value = Mock(config=Mock())
        mock_llm.return_value = mock_llm_instance
        mock_pipeline.return_value = Mock()
        
        config = {"name": "TestBot", "llm": "gpt-4o"}
        agent = Agent.from_config(config)
        
        assert agent.name == "TestBot"


class TestAgentQuick:
    """Test Agent.quick class method."""
    
    @patch('agenticaiframework.llms.LLMManager.from_environment')
    @patch('agenticaiframework.guardrails.GuardrailPipeline.minimal')
    @patch('agenticaiframework.tracing.tracer')
    @patch('agenticaiframework.tools.tool_registry')
    @patch('agenticaiframework.tools.agent_tool_manager')
    def test_quick_minimal(self, mock_tool_mgr, mock_registry, mock_tracer, mock_pipeline, mock_llm):
        """Test quick with minimal args."""
        from agenticaiframework.core.agent import Agent
        
        mock_llm.return_value = Mock(active_model=None)
        mock_pipeline.return_value = Mock()
        
        agent = Agent.quick("QuickBot")
        
        assert agent.name == "QuickBot"
        assert agent.status == "running"  # auto-started
    
    @patch('agenticaiframework.llms.LLMManager.from_environment')
    @patch('agenticaiframework.guardrails.GuardrailPipeline.minimal')
    @patch('agenticaiframework.tracing.tracer')
    @patch('agenticaiframework.tools.tool_registry')
    @patch('agenticaiframework.tools.agent_tool_manager')
    def test_quick_with_role(self, mock_tool_mgr, mock_registry, mock_tracer, mock_pipeline, mock_llm):
        """Test quick with role template."""
        from agenticaiframework.core.agent import Agent
        
        mock_llm.return_value = Mock(active_model=None)
        mock_pipeline.return_value = Mock()
        
        agent = Agent.quick("CoderBot", role="coder")
        
        assert agent.name == "CoderBot"
    
    @patch('agenticaiframework.llms.LLMManager.from_environment')
    @patch('agenticaiframework.guardrails.GuardrailPipeline.minimal')
    @patch('agenticaiframework.tracing.tracer')
    @patch('agenticaiframework.tools.tool_registry')
    @patch('agenticaiframework.tools.agent_tool_manager')
    def test_quick_custom_role(self, mock_tool_mgr, mock_registry, mock_tracer, mock_pipeline, mock_llm):
        """Test quick with custom role description."""
        from agenticaiframework.core.agent import Agent
        
        mock_llm.return_value = Mock(active_model=None)
        mock_pipeline.return_value = Mock()
        
        agent = Agent.quick("CustomBot", role="A custom role for testing")
        
        assert agent.name == "CustomBot"
    
    @patch('agenticaiframework.llms.LLMManager.from_environment')
    @patch('agenticaiframework.guardrails.GuardrailPipeline.minimal')
    @patch('agenticaiframework.tracing.tracer')
    @patch('agenticaiframework.tools.tool_registry')
    @patch('agenticaiframework.tools.agent_tool_manager')
    def test_quick_no_guardrails(self, mock_tool_mgr, mock_registry, mock_tracer, mock_pipeline, mock_llm):
        """Test quick with guardrails disabled."""
        from agenticaiframework.core.agent import Agent
        
        mock_llm.return_value = Mock(active_model=None)
        mock_pipeline.return_value = Mock()
        
        agent = Agent.quick("NoGuardsBot", guardrails=False)
        
        assert agent.name == "NoGuardsBot"
    
    @patch('agenticaiframework.llms.LLMManager.from_environment')
    @patch('agenticaiframework.guardrails.GuardrailPipeline.minimal')
    @patch('agenticaiframework.tracing.tracer')
    @patch('agenticaiframework.tools.tool_registry')
    @patch('agenticaiframework.tools.agent_tool_manager')
    def test_quick_no_tracing(self, mock_tool_mgr, mock_registry, mock_tracer, mock_pipeline, mock_llm):
        """Test quick with tracing disabled."""
        from agenticaiframework.core.agent import Agent
        
        mock_llm.return_value = Mock(active_model=None)
        mock_pipeline.return_value = Mock()
        
        agent = Agent.quick("NoTraceBot", tracing=False)
        
        assert agent.name == "NoTraceBot"
    
    @patch('agenticaiframework.llms.LLMManager.from_environment')
    @patch('agenticaiframework.guardrails.GuardrailPipeline.minimal')
    @patch('agenticaiframework.tracing.tracer')
    @patch('agenticaiframework.tools.tool_registry')
    @patch('agenticaiframework.tools.agent_tool_manager')
    def test_quick_with_tools(self, mock_tool_mgr, mock_registry, mock_tracer, mock_pipeline, mock_llm):
        """Test quick with tools specified."""
        from agenticaiframework.core.agent import Agent
        
        mock_llm.return_value = Mock(active_model=None)
        mock_pipeline.return_value = Mock()
        
        agent = Agent.quick("ToolBot", tools=["ToolA", "ToolB"])
        
        assert agent.name == "ToolBot"
        mock_tool_mgr.bind_tools.assert_called()
    
    @patch('agenticaiframework.llms.LLMManager.from_environment')
    @patch('agenticaiframework.guardrails.GuardrailPipeline.minimal')
    @patch('agenticaiframework.tracing.tracer')
    @patch('agenticaiframework.tools.tool_registry')
    @patch('agenticaiframework.tools.agent_tool_manager')
    def test_quick_with_auto_tools(self, mock_tool_mgr, mock_registry, mock_tracer, mock_pipeline, mock_llm):
        """Test quick with auto_tools enabled."""
        from agenticaiframework.core.agent import Agent
        
        mock_llm.return_value = Mock(active_model=None)
        mock_pipeline.return_value = Mock()
        
        agent = Agent.quick("AutoToolBot", role="analyst", auto_tools=True)
        
        assert agent.name == "AutoToolBot"
    
    @patch('agenticaiframework.llms.LLMManager.from_environment')
    @patch('agenticaiframework.guardrails.GuardrailPipeline.minimal')
    @patch('agenticaiframework.tracing.tracer')
    @patch('agenticaiframework.tools.tool_registry')
    @patch('agenticaiframework.tools.agent_tool_manager')
    def test_quick_with_provider(self, mock_tool_mgr, mock_registry, mock_tracer, mock_pipeline, mock_llm):
        """Test quick with provider specified."""
        from agenticaiframework.core.agent import Agent
        
        mock_llm.return_value = Mock(active_model=None)
        mock_pipeline.return_value = Mock()
        
        agent = Agent.quick("ProviderBot", provider="openai")
        
        assert agent.name == "ProviderBot"
    
    @patch('agenticaiframework.llms.LLMManager.from_environment')
    @patch('agenticaiframework.guardrails.GuardrailPipeline.minimal')
    @patch('agenticaiframework.tracing.tracer')
    @patch('agenticaiframework.tools.tool_registry')
    @patch('agenticaiframework.tools.agent_tool_manager')
    def test_quick_with_llm_and_model(self, mock_tool_mgr, mock_registry, mock_tracer, mock_pipeline, mock_llm):
        """Test quick with llm model specified."""
        from agenticaiframework.core.agent import Agent
        
        mock_llm_instance = Mock(active_model="test")
        mock_llm_instance.get_provider.return_value = Mock(config=Mock())
        mock_llm.return_value = mock_llm_instance
        mock_pipeline.return_value = Mock()
        
        agent = Agent.quick("LLMBot", llm="gpt-4o")
        
        assert agent.name == "LLMBot"


class TestAgentVersion:
    """Test Agent version attribute."""
    
    def test_version_exists(self):
        """Test version attribute exists."""
        from agenticaiframework.core.agent import Agent
        
        agent = Agent(
            name="TestAgent",
            role="Test Role",
            capabilities=["test"],
            config={}
        )
        
        assert hasattr(agent, 'version')
        assert agent.version == "2.0.0"


class TestAgentSupervisor:
    """Test Agent supervisor/orchestration attributes."""
    
    def test_supervisor_id_default(self):
        """Test supervisor_id is None by default."""
        from agenticaiframework.core.agent import Agent
        
        agent = Agent(
            name="TestAgent",
            role="Test Role",
            capabilities=["test"],
            config={}
        )
        
        assert agent.supervisor_id is None
    
    def test_supervisor_id_can_be_set(self):
        """Test supervisor_id can be set."""
        from agenticaiframework.core.agent import Agent
        
        agent = Agent(
            name="TestAgent",
            role="Test Role",
            capabilities=["test"],
            config={}
        )
        
        agent.supervisor_id = "supervisor-123"
        assert agent.supervisor_id == "supervisor-123"


class TestAgentErrorLog:
    """Test Agent error logging."""
    
    def test_error_log_initialized(self):
        """Test error_log is empty list."""
        from agenticaiframework.core.agent import Agent
        
        agent = Agent(
            name="TestAgent",
            role="Test Role",
            capabilities=["test"],
            config={}
        )
        
        assert isinstance(agent.error_log, list)
        assert len(agent.error_log) == 0


class TestAgentSecurityContextUpdates:
    """Test Agent security context updates."""
    
    def test_start_updates_security_context(self):
        """Test start() updates security context."""
        from agenticaiframework.core.agent import Agent
        
        agent = Agent(
            name="TestAgent",
            role="Test Role",
            capabilities=["test"],
            config={}
        )
        
        initial_activity = agent.security_context['last_activity']
        import time
        time.sleep(0.01)  # Small delay
        agent.start()
        
        # last_activity should be updated
        assert agent.security_context['last_activity'] is not None
    
    def test_resume_updates_security_context(self):
        """Test resume() updates security context."""
        from agenticaiframework.core.agent import Agent
        
        agent = Agent(
            name="TestAgent",
            role="Test Role",
            capabilities=["test"],
            config={}
        )
        
        agent.start()
        agent.pause()
        initial_activity = agent.security_context['last_activity']
        import time
        time.sleep(0.01)
        agent.resume()
        
        # last_activity should be updated
        assert agent.security_context['last_activity'] is not None
    
    def test_execute_task_updates_security_context(self):
        """Test execute_task updates security context."""
        from agenticaiframework.core.agent import Agent
        
        agent = Agent(
            name="TestAgent",
            role="Test Role",
            capabilities=["test"],
            config={}
        )
        
        initial_count = agent.security_context['access_count']
        
        def test_task():
            return "result"
        
        agent.execute_task(test_task)
        
        assert agent.security_context['access_count'] == initial_count + 1
