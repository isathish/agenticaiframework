"""
Unit Tests for Agentic Framework SDK

This module contains comprehensive unit tests for all core components of the Agentic Framework,
including Agents, Prompts, Process, Tasks, MCP Tools, Monitoring, Guardrails, Evaluation,
Knowledge Retrieval, LLMs, Communication, Memory, Hub, Configurations, and Security.
"""

import unittest
import sys
import os
import time
from typing import Dict, Any, Optional
import logging

# Adjust the path to import from the agentic_framework module
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agentic_framework.agents import Agent, AgentManager
from agentic_framework.prompts import Prompt, PromptTemplate, PromptManager
from agentic_framework.process import Process, ProcessScheduler
from agentic_framework.tasks import Task, TaskManager
from agentic_framework.mcp_tools import MCPTool, MCPToolManager
from agentic_framework.monitoring import PerformanceMonitor, EventTracer, AnomalyDetector
from agentic_framework.guardrails import ValidationGuardrail, PolicyEnforcer, RateLimiter
from agentic_framework.evaluation import AutomatedTester, HumanReviewEvaluator, EvaluationManager
from agentic_framework.knowledge import RAGRetriever, KnowledgeManager
from agentic_framework.llms import SimpleLLM, LLMSelector, LLMManager
from agentic_framework.communication import StreamtableHTTPProtocol, WebSocketProtocol, MessageQueueProtocol, CommunicationManager
from agentic_framework.memory import ShortTermMemoryStorage, LongTermMemoryStorage, ExternalMemoryStorage, SemanticIndex, MemoryManager
from agentic_framework.hub import AgentHub, PromptHub, MCPToolHub, GuardrailHub, LLMHub, HubManager
from agentic_framework.configurations import ConfigurationStore, ConfigurationManager
from agentic_framework.security import SecurityManager, SecurityLevel, SimpleAuthProvider, RoleBasedPolicy, SimpleEncryptionProvider, SandboxEnvironment, AuditLogger

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestAgenticFramework(unittest.TestCase):
    """Test suite for all components of the Agentic Framework SDK."""
    
    def setUp(self):
        """Set up common test fixtures before each test method."""
        self.security_manager = SecurityManager(secret_key="test_secret_key", security_level=SecurityLevel.LOW)
        self.agent_manager = AgentManager()
        self.prompt_manager = PromptManager()
        self.process_scheduler = ProcessScheduler()
        self.task_manager = TaskManager()
        self.tool_manager = MCPToolManager()
        self.performance_monitor = PerformanceMonitor()
        self.event_tracer = EventTracer()
        self.anomaly_detector = AnomalyDetector()
        self.evaluation_manager = EvaluationManager()
        self.knowledge_manager = KnowledgeManager()
        self.llm_manager = LLMManager(name="TestLLMManager")
        self.communication_manager = CommunicationManager()
        self.memory_manager = MemoryManager()
        self.hub_manager = HubManager()
        self.config_manager = ConfigurationManager()
        
        # Authenticate a test agent for security tests
        self.agent_credentials = {'username': 'agent:default', 'password': 'secure_password_123'}
        self.token = self.security_manager.authenticate_component(self.agent_credentials)
        
    def test_agents_module(self):
        """Test Agents module functionality."""
        # Test agent creation and registration
        agent = Agent(name="TestAgent", supported_modalities=["text", "image"])
        self.agent_manager.register_agent(agent)
        self.assertIn("TestAgent", self.agent_manager.agents)
        
        # Test agent lifecycle
        agent.start()
        self.assertTrue(agent.active)
        result = agent.perform_task("test_task", modality="text")
        self.assertTrue(result.startswith("Task test_task performed by TestAgent"))
        agent.stop()
        self.assertFalse(agent.active)
        
        # Test agent security access
        self.assertTrue(self.security_manager.check_access(self.token, "agent/TestAgent", "execute"))
        
        logger.info("Agents module test passed")
    
    def test_prompts_module(self):
        """Test Prompts module functionality."""
        # Test prompt template creation
        template = PromptTemplate(name="TestTemplate", 
                                 template_string="Hello, {name}! Perform {task}.")
        self.prompt_manager.register_template(template)
        self.assertIn("TestTemplate", self.prompt_manager.templates)
        
        # Test dynamic prompt generation
        prompt = self.prompt_manager.generate_prompt("TestTemplate", 
                                                    {"name": "Agent", "task": "test"})
        self.assertEqual(prompt.content, "Hello, Agent! Perform test.")
        
        logger.info("Prompts module test passed")
    
    def test_process_module(self):
        """Test Process module functionality."""
        # Test sequential process
        process = Process(process_type="sequential", tasks=["task1", "task2"])
        self.process_scheduler.register_process(process)
        self.assertIn(process.process_id, self.process_scheduler.processes)
        
        # Test process execution
        result = self.process_scheduler.execute_process(process.process_id)
        self.assertTrue(result["status"] == "completed")
        
        logger.info("Process module test passed")
    
    def test_tasks_module(self):
        """Test Tasks module functionality."""
        # Test task creation and assignment
        task = Task(task_id="TestTask", description="Test task description", 
                   required_capabilities=["text"])
        self.task_manager.register_task(task)
        self.assertIn("TestTask", self.task_manager.tasks)
        
        # Test task prioritization
        self.task_manager.prioritize_tasks()
        self.assertEqual(self.task_manager.task_queue[0].task_id, "TestTask")
        
        logger.info("Tasks module test passed")
    
    def test_mcp_tools_module(self):
        """Test MCP Tools module functionality."""
        # Test tool registration
        tool = MCPTool(name="TestTool", version="1.0", capabilities=["data_analysis"])
        self.tool_manager.register_tool(tool)
        self.assertIn("TestTool:1.0", self.tool_manager.tools)
        
        # Test tool invocation
        result = self.tool_manager.invoke_tool("TestTool", "1.0", {"data": "test"})
        self.assertEqual(result, "Processed data: test")
        
        logger.info("MCP Tools module test passed")
    
    def test_monitoring_module(self):
        """Test Monitoring and Observability module functionality."""
        # Test performance monitoring
        self.performance_monitor.start_monitoring("TestComponent")
        time.sleep(0.1)
        self.performance_monitor.stop_monitoring("TestComponent")
        self.assertIn("TestComponent", self.performance_monitor.performance_data)
        
        # Test event tracing
        self.event_tracer.trace_event("TestEvent", {"detail": "test"})
        self.assertGreater(len(self.event_tracer.events), 0)
        
        # Test anomaly detection
        self.anomaly_detector.add_data_point(100.0)
        anomaly = self.anomaly_detector.detect_anomaly(1000.0)
        self.assertTrue(anomaly)
        
        logger.info("Monitoring module test passed")
    
    def test_guardrails_module(self):
        """Test Guardrails module functionality."""
        # Test input validation
        guardrail = ValidationGuardrail(validation_rules={"max_length": 10})
        result = guardrail.validate_input("short")
        self.assertTrue(result["valid"])
        
        # Test policy enforcement
        enforcer = PolicyEnforcer(policies={"allow_all": True})
        self.assertTrue(enforcer.enforce_policy("test_action", {}))
        
        # Test rate limiting
        limiter = RateLimiter(rate_limit=5, time_window=1)
        for _ in range(5):
            self.assertTrue(limiter.check_rate_limit("test_user"))
        time.sleep(1)  # Reset window
        self.assertTrue(limiter.check_rate_limit("test_user"))
        
        logger.info("Guardrails module test passed")
    
    def test_evaluation_module(self):
        """Test Evaluation module functionality."""
        # Test automated testing
        tester = AutomatedTester(test_cases=[{"input": "test", "expected": "test"}])
        result = tester.run_tests(lambda x: x)
        self.assertTrue(result["success_rate"] > 0)
        
        # Test human review evaluator
        evaluator = HumanReviewEvaluator(criteria=["accuracy"])
        feedback = evaluator.collect_feedback("test_output", {"accuracy": 0.9})
        self.assertEqual(feedback["accuracy"], 0.9)
        
        logger.info("Evaluation module test passed")
    
    def test_knowledge_module(self):
        """Test Knowledge Retrieval module functionality."""
        # Test RAG retriever
        retriever = RAGRetriever(documents=["doc1", "doc2"])
        results = retriever.retrieve("query")
        self.assertGreater(len(results), 0)
        
        # Test knowledge manager
        self.knowledge_manager.add_knowledge_source("test_source", ["data1", "data2"])
        retrieved = self.knowledge_manager.retrieve_knowledge("test_query", source="test_source")
        self.assertIn("data1", retrieved)
        
        logger.info("Knowledge module test passed")
    
    def test_llms_module(self):
        """Test LLMs module functionality."""
        # Test simple LLM
        llm = SimpleLLM(name="TestLLM")
        response = llm.generate("test prompt")
        self.assertTrue(response["content"].startswith("Generated response for: test prompt"))
        
        # Test LLM manager
        self.llm_manager.register_llm(llm)
        response = self.llm_manager.generate_response("test prompt")
        self.assertTrue("content" in response)
        
        logger.info("LLMs module test passed")
    
    def test_communication_module(self):
        """Test Communication Protocols module functionality."""
        # Test Streamtable HTTP protocol
        http_protocol = StreamtableHTTPProtocol()
        http_protocol.connect()
        self.assertTrue(http_protocol.is_connected())
        http_protocol.send_data({"test": "data"})
        received = http_protocol.receive_data()
        self.assertEqual(received, {"test": "data"})
        
        # Test communication manager
        self.communication_manager.register_protocol(http_protocol)
        self.assertIn("streamtable_http", self.communication_manager.protocols)
        
        logger.info("Communication module test passed")
    
    def test_memory_module(self):
        """Test Memory module functionality."""
        # Test short-term memory
        short_term = ShortTermMemoryStorage()
        short_term.store("key1", "value1")
        self.assertEqual(short_term.retrieve("key1"), "value1")
        
        # Test long-term memory
        long_term = LongTermMemoryStorage()
        long_term.store("key2", "value2", metadata={"category": "test"})
        results = long_term.search_by_metadata({"category": "test"})
        self.assertIn("key2", results)
        
        # Test memory manager
        self.memory_manager.store("key3", "value3", memory_type="short_term")
        retrieved = self.memory_manager.retrieve("key3", memory_type="short_term")
        self.assertEqual(retrieved, "value3")
        
        logger.info("Memory module test passed")
    
    def test_hub_module(self):
        """Test Hub module functionality."""
        # Test agent hub
        agent_hub = AgentHub()
        agent_hub.register_agent("TestAgent", {"version": "1.0"})
        self.assertIn("TestAgent", agent_hub.agents)
        
        # Test hub manager
        self.hub_manager.register_hub(agent_hub, "agent_hub")
        discovered = self.hub_manager.discover_components("agent_hub", component_type="agent")
        self.assertIn("TestAgent", discovered)
        
        logger.info("Hub module test passed")
    
    def test_configurations_module(self):
        """Test Configurations module functionality."""
        # Test configuration store
        config_store = ConfigurationStore()
        config_store.register_schema("agent", {"type": "object", "properties": {"name": {"type": "string"}}})
        config_store.store_configuration("agent", "TestAgent", {"name": "TestAgentConfig"})
        loaded = config_store.load_configuration("agent", "TestAgent")
        self.assertEqual(loaded["name"], "TestAgentConfig")
        
        # Test configuration manager
        self.config_manager.register_component_type("agent")
        config = self.config_manager.get_component_config("agent", "TestAgent")
        self.assertIsInstance(config, dict)
        
        logger.info("Configurations module test passed")
    
    def test_security_module(self):
        """Test Security module functionality."""
        # Test authentication
        self.assertIsNotNone(self.token)
        self.assertTrue(self.security_manager.validate_session(self.token))
        
        # Test authorization
        self.assertTrue(self.security_manager.check_access(self.token, "task/123", "write"))
        self.assertFalse(self.security_manager.check_access(self.token, "admin/data", "delete"))
        
        # Test encryption
        data = b"test data"
        encrypted = self.security_manager.secure_data(data)
        decrypted = self.security_manager.access_secure_data(encrypted)
        self.assertEqual(decrypted, data)
        
        # Test sandbox execution
        result = self.security_manager.execute_in_sandbox(self.token, "read", "test_payload")
        self.assertTrue(result.startswith("Read result for"))
        
        logger.info("Security module test passed")

if __name__ == '__main__':
    unittest.main()
