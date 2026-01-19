"""
High-impact comprehensive tests for the largest low-coverage modules.
Targets: core/agent.py, communication, formatting, hitl, conversations.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import time
import json


# ============================================================================
# Core Agent Tests (20% coverage - 726 lines)
# ============================================================================

class TestAgentClassAttributes:
    """Tests for Agent class attributes."""
    
    def test_role_templates_exist(self):
        """Test ROLE_TEMPLATES class attribute."""
        from agenticaiframework.core.agent import Agent
        
        assert "assistant" in Agent.ROLE_TEMPLATES
        assert "analyst" in Agent.ROLE_TEMPLATES
        assert "coder" in Agent.ROLE_TEMPLATES
        assert "writer" in Agent.ROLE_TEMPLATES
        assert "researcher" in Agent.ROLE_TEMPLATES
    
    def test_role_capabilities_exist(self):
        """Test ROLE_CAPABILITIES class attribute."""
        from agenticaiframework.core.agent import Agent
        
        assert "assistant" in Agent.ROLE_CAPABILITIES
        assert "chat" in Agent.ROLE_CAPABILITIES["assistant"]
        assert "tool-use" in Agent.ROLE_CAPABILITIES["assistant"]


class TestAgentInit:
    """Tests for Agent initialization."""
    
    def test_agent_init_basic(self):
        """Test Agent basic initialization."""
        from agenticaiframework.core.agent import Agent
        
        agent = Agent(
            name="TestAgent",
            role="A helpful assistant",
            capabilities=["chat"],
            config={},
        )
        
        assert agent.name == "TestAgent"
        assert agent.role == "A helpful assistant"
        assert agent.capabilities == ["chat"]
        assert agent.status == "initialized"
        assert agent.version == "2.0.0"
    
    def test_agent_init_with_max_tokens(self):
        """Test Agent initialization with max_context_tokens."""
        from agenticaiframework.core.agent import Agent
        
        agent = Agent(
            name="TestAgent",
            role="Assistant",
            capabilities=["chat"],
            config={},
            max_context_tokens=8192,
        )
        
        assert agent.context_manager is not None
    
    def test_agent_has_performance_metrics(self):
        """Test Agent has performance metrics initialized."""
        from agenticaiframework.core.agent import Agent
        
        agent = Agent(
            name="MetricsAgent",
            role="Assistant",
            capabilities=["chat"],
            config={},
        )
        
        assert "total_tasks" in agent.performance_metrics
        assert "successful_tasks" in agent.performance_metrics
        assert "failed_tasks" in agent.performance_metrics
        assert agent.performance_metrics["total_tasks"] == 0
    
    def test_agent_has_security_context(self):
        """Test Agent has security context initialized."""
        from agenticaiframework.core.agent import Agent
        
        agent = Agent(
            name="SecureAgent",
            role="Assistant",
            capabilities=["chat"],
            config={},
        )
        
        assert "created_at" in agent.security_context
        assert "access_count" in agent.security_context
        assert agent.security_context["access_count"] == 0
    
    def test_agent_has_uuid(self):
        """Test Agent has a unique ID."""
        from agenticaiframework.core.agent import Agent
        
        agent1 = Agent("Agent1", "Role", ["cap"], {})
        agent2 = Agent("Agent2", "Role", ["cap"], {})
        
        assert agent1.id != agent2.id
        assert len(agent1.id) == 36  # UUID format


class TestAgentMethods:
    """Tests for Agent methods."""
    
    def test_agent_error_log_empty(self):
        """Test Agent error_log is initially empty."""
        from agenticaiframework.core.agent import Agent
        
        agent = Agent("Agent", "Role", ["cap"], {})
        assert agent.error_log == []
    
    def test_agent_memory_empty(self):
        """Test Agent memory is initially empty."""
        from agenticaiframework.core.agent import Agent
        
        agent = Agent("Agent", "Role", ["cap"], {})
        assert agent.memory == []


# ============================================================================
# Communication Manager Tests (29% coverage)
# ============================================================================

class TestCommunicationManager:
    """Tests for communication manager module."""
    
    def test_communication_manager_import(self):
        """Test AgentCommunicationManager can be imported."""
        from agenticaiframework.communication.manager import AgentCommunicationManager
        assert AgentCommunicationManager is not None


# ============================================================================
# Communication Protocols Tests (20% coverage)
# ============================================================================

class TestCommunicationProtocols:
    """Tests for communication protocols module."""
    
    def test_protocols_import(self):
        """Test protocols module can be imported."""
        from agenticaiframework.communication import protocols
        assert protocols is not None


# ============================================================================
# Communication Remote Agent Tests (26% coverage)
# ============================================================================

class TestRemoteAgent:
    """Tests for remote agent module."""
    
    def test_remote_agent_import(self):
        """Test remote agent module can be imported."""
        from agenticaiframework.communication import remote_agent
        assert remote_agent is not None


# ============================================================================
# Formatting Tests (30% coverage - 425 lines)
# ============================================================================

class TestFormattingFormatter:
    """Tests for formatting module."""
    
    def test_formatter_import(self):
        """Test formatter module can be imported."""
        from agenticaiframework.formatting import formatter
        assert formatter is not None


# ============================================================================
# Conversations Manager Tests (34% coverage - 304 lines)
# ============================================================================

class TestConversationsManager:
    """Tests for conversations manager module."""
    
    def test_conversations_manager_import(self):
        """Test conversations manager can be imported."""
        from agenticaiframework.conversations import manager
        assert manager is not None


# ============================================================================
# HITL Manager Extended Tests (36% coverage - 312 lines)
# ============================================================================

class TestHITLManagerExtended:
    """Extended tests for HITL manager."""
    
    def test_human_in_the_loop_init(self):
        """Test HumanInTheLoop initialization."""
        from agenticaiframework.hitl.manager import HumanInTheLoop
        
        hitl = HumanInTheLoop()
        assert hitl is not None
    
    def test_console_approval_handler_init(self):
        """Test ConsoleApprovalHandler initialization."""
        from agenticaiframework.hitl.manager import ConsoleApprovalHandler
        
        handler = ConsoleApprovalHandler()
        assert handler is not None
    
    def test_approval_decision_dataclass(self):
        """Test ApprovalDecision dataclass."""
        from agenticaiframework.hitl.manager import ApprovalDecision, ApprovalStatus
        
        decision = ApprovalDecision(
            request_id="req-001",
            status=ApprovalStatus.APPROVED,
            decided_by="admin",
            decided_at="2024-01-01T00:00:00",
        )
        
        assert decision.status == ApprovalStatus.APPROVED
    
    def test_feedback_dataclass(self):
        """Test Feedback dataclass."""
        from agenticaiframework.hitl.manager import Feedback, FeedbackType
        
        feedback = Feedback(
            id="fb-001",
            response_id="resp-001",
            feedback_type=FeedbackType.RATING,
            value=5,
            user_id="user-001",
            created_at="2024-01-01T00:00:00",
        )
        
        assert feedback.value == 5
    
    def test_escalation_trigger_dataclass(self):
        """Test EscalationTrigger dataclass."""
        from agenticaiframework.hitl.manager import EscalationTrigger, EscalationLevel
        
        trigger = EscalationTrigger(
            name="high_risk_trigger",
            condition=lambda x: x.get("risk") == "high",
            level=EscalationLevel.HIGH,
            message="High risk detected",
        )
        
        assert trigger.name == "high_risk_trigger"
    
    def test_intervention_request_dataclass(self):
        """Test InterventionRequest dataclass."""
        from agenticaiframework.hitl.manager import InterventionRequest, EscalationLevel
        
        request = InterventionRequest(
            id="int-001",
            reason="User requested assistance",
            level=EscalationLevel.LOW,
            agent_id="agent-001",
            session_id="session-001",
            context={"action": "purchase"},
            created_at="2024-01-01T00:00:00",
        )
        
        assert request.reason == "User requested assistance"


# ============================================================================
# Infrastructure Extended Tests
# ============================================================================

class TestInfrastructureExtended:
    """Extended tests for infrastructure module."""
    
    def test_serverless_function_dataclass(self):
        """Test ServerlessFunction dataclass."""
        from agenticaiframework.infrastructure.types import ServerlessFunction
        import time
        
        func = ServerlessFunction(
            function_id="func-001",
            name="test-function",
            handler=lambda x: x,
            runtime="python3.11",
            memory_mb=256,
            timeout_seconds=30,
            environment={"ENV": "test"},
            metadata={"version": "1.0"},
            created_at=time.time(),
        )
        
        assert func.name == "test-function"
    
    def test_function_invocation_dataclass(self):
        """Test FunctionInvocation dataclass."""
        from agenticaiframework.infrastructure.types import FunctionInvocation
        import time
        
        now = time.time()
        invocation = FunctionInvocation(
            invocation_id="inv-001",
            function_id="func-001",
            input_data={"key": "value"},
            output_data={"result": "success"},
            status="completed",
            start_time=now,
            end_time=now + 0.5,
            memory_used_mb=128.0,
            billed_duration_ms=500.0,
        )
        
        assert invocation.function_id == "func-001"


# ============================================================================
# Tool Executor Extended Tests
# ============================================================================

class TestToolExecutorExtended:
    """Extended tests for tool executor."""
    
    def test_execution_context_all_fields(self):
        """Test ExecutionContext with all fields."""
        from agenticaiframework.tools.executor import ExecutionContext
        
        ctx = ExecutionContext(
            agent_id="agent-001",
            session_id="session-001",
            timeout=30.0,
            max_retries=3,
        )
        
        assert ctx.timeout == 30.0
        assert ctx.max_retries == 3


# ============================================================================
# LLM Manager Tests
# ============================================================================

class TestLLMManager:
    """Tests for LLM manager."""
    
    def test_llm_manager_init(self):
        """Test LLMManager initialization."""
        from agenticaiframework.llms.manager import LLMManager
        
        manager = LLMManager()
        assert manager is not None
    
    def test_model_router_init(self):
        """Test ModelRouter initialization."""
        from agenticaiframework.llms.router import ModelRouter
        from agenticaiframework.llms.manager import LLMManager
        
        llm_manager = LLMManager()
        router = ModelRouter(llm_manager=llm_manager)
        assert router is not None


# ============================================================================
# Guardrails Extended Tests
# ============================================================================

class TestGuardrailsExtended:
    """Extended tests for guardrails."""
    
    def test_guardrail_pipeline_minimal(self):
        """Test GuardrailPipeline.minimal() factory."""
        from agenticaiframework.guardrails import GuardrailPipeline
        
        pipeline = GuardrailPipeline.minimal()
        assert pipeline is not None
    
    def test_guardrail_manager_init(self):
        """Test GuardrailManager initialization."""
        from agenticaiframework.guardrails import GuardrailManager
        
        manager = GuardrailManager()
        assert manager is not None


# ============================================================================
# Knowledge Vector DB Extended Tests
# ============================================================================

class TestKnowledgeVectorDB:
    """Tests for knowledge vector DB."""
    
    def test_vector_db_type_all_values(self):
        """Test all VectorDBType enum values."""
        from agenticaiframework.knowledge.vector_db import VectorDBType
        
        types = list(VectorDBType)
        assert VectorDBType.MEMORY in types
        assert VectorDBType.QDRANT in types
        assert VectorDBType.PINECONE in types
    
    def test_in_memory_vector_db_init(self):
        """Test InMemoryVectorDB initialization."""
        from agenticaiframework.knowledge.vector_db import InMemoryVectorDB, VectorDBConfig, VectorDBType
        
        config = VectorDBConfig(db_type=VectorDBType.MEMORY, dimension=384)
        db = InMemoryVectorDB(config=config)
        
        assert db is not None
    
    def test_in_memory_vector_db_insert_search(self):
        """Test InMemoryVectorDB insert and search."""
        from agenticaiframework.knowledge.vector_db import InMemoryVectorDB, VectorDBConfig, VectorDBType
        
        config = VectorDBConfig(db_type=VectorDBType.MEMORY, dimension=3, collection_name="test")
        db = InMemoryVectorDB(config=config)
        db.connect()
        db.create_collection("test", 3)
        
        # Insert vectors
        db.insert(
            vectors=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]],
            ids=["v1", "v2"],
            payloads=[{"text": "hello"}, {"text": "world"}],
        )
        
        # Search
        results = db.search(
            query_vector=[0.1, 0.2, 0.3],
            limit=2,
        )
        
        assert len(results) > 0


# ============================================================================
# Memory Manager Extended Tests
# ============================================================================

class TestMemoryManagerExtended:
    """Extended tests for memory manager."""
    
    def test_memory_manager_init(self):
        """Test MemoryManager initialization."""
        from agenticaiframework.memory.manager import MemoryManager
        
        manager = MemoryManager()
        assert manager is not None
    
    def test_memory_entry_all_fields(self):
        """Test MemoryEntry with all fields."""
        from agenticaiframework.memory.types import MemoryEntry
        
        entry = MemoryEntry(
            key="test-key",
            value="test-value",
            metadata={"source": "test"},
        )
        
        assert entry.key == "test-key"
        assert entry.value == "test-value"


# ============================================================================
# Orchestration Extended Tests
# ============================================================================

class TestOrchestrationExtended:
    """Extended tests for orchestration."""
    
    def test_orchestration_engine_init(self):
        """Test OrchestrationEngine initialization."""
        from agenticaiframework.orchestration.engine import OrchestrationEngine
        
        engine = OrchestrationEngine()
        assert engine is not None
    
    def test_agent_supervisor_init(self):
        """Test AgentSupervisor initialization."""
        from agenticaiframework.orchestration.supervisor import AgentSupervisor
        
        supervisor = AgentSupervisor(name="TestSupervisor")
        assert supervisor.name == "TestSupervisor"


# ============================================================================
# Prompt Versioning Extended Tests
# ============================================================================

class TestPromptVersioningExtended:
    """Extended tests for prompt versioning."""
    
    def test_prompt_version_content_hash(self):
        """Test PromptVersion content_hash property."""
        from agenticaiframework.prompt_versioning.types import PromptVersion, PromptStatus
        import time
        
        version = PromptVersion(
            prompt_id="prompt-001",
            version="1.0.0",
            name="Test Prompt",
            template="Hello {{name}}!",
            variables=["name"],
            status=PromptStatus.ACTIVE,
            created_at=time.time(),
            created_by="test_user",
        )
        
        hash1 = version.content_hash
        assert isinstance(hash1, str)
        assert len(hash1) == 12


# ============================================================================
# Security Extended Tests
# ============================================================================

class TestSecurityExtended:
    """Extended tests for security module."""
    
    def test_rate_limiter_with_burst(self):
        """Test RateLimiter with burst requests."""
        from agenticaiframework.security.rate_limiting import RateLimiter
        
        limiter = RateLimiter(max_requests=5, time_window=1.0)
        
        # All requests should be allowed
        for i in range(5):
            assert limiter.is_allowed("client-1") == True
        
        # 6th request should be denied
        assert limiter.is_allowed("client-1") == False
    
    def test_injection_detector_safe_input(self):
        """Test PromptInjectionDetector with safe input."""
        from agenticaiframework.security.injection import PromptInjectionDetector
        
        detector = PromptInjectionDetector()
        result = detector.detect("Hello, how are you today?")
        
        assert result is not None


# ============================================================================
# Tracing Extended Tests
# ============================================================================

class TestTracingExtended:
    """Extended tests for tracing module."""
    
    def test_span_duration_ms(self):
        """Test Span duration_ms property."""
        from agenticaiframework.tracing.types import Span
        import time
        
        start = time.time()
        span = Span(
            span_id="span-001",
            trace_id="trace-001",
            name="test-span",
            parent_span_id=None,
            start_time=start,
            end_time=start + 1.5,  # 1.5 seconds later
        )
        
        duration = span.duration_ms
        assert duration is not None
        assert duration >= 1500  # At least 1500 ms
    
    def test_agent_step_tracer_init(self):
        """Test AgentStepTracer initialization."""
        from agenticaiframework.tracing.tracer import AgentStepTracer
        
        tracer = AgentStepTracer()
        assert tracer is not None


# ============================================================================
# Workflows Extended Tests
# ============================================================================

class TestWorkflowsExtended:
    """Extended tests for workflows."""
    
    def test_sequential_workflow_init(self):
        """Test SequentialWorkflow initialization."""
        from agenticaiframework.workflows import SequentialWorkflow
        from agenticaiframework.orchestration.engine import OrchestrationEngine
        
        engine = OrchestrationEngine()
        workflow = SequentialWorkflow(manager=engine)
        
        assert workflow is not None
    
    def test_parallel_workflow_init(self):
        """Test ParallelWorkflow initialization."""
        from agenticaiframework.workflows import ParallelWorkflow
        from agenticaiframework.orchestration.engine import OrchestrationEngine
        
        engine = OrchestrationEngine()
        workflow = ParallelWorkflow(manager=engine)
        
        assert workflow is not None
