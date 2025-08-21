"""
Unit Tests for Agentic Framework Core Components

This module contains unit tests for the core components of the Agentic Framework,
including Agents, Prompts, Process, Tasks, MCP Tools, Monitoring, Guardrails,
Evaluation, Knowledge Retrieval, LLMs, Communication Protocols, Memory, Hub,
Configurations, and Security.
"""

import unittest
from agentic_framework.agents import Agent, AgentManager
from agentic_framework.prompts import PromptTemplate, PromptChain
from agentic_framework.process import ProcessScheduler, ProcessError
from agentic_framework.tasks import Task, TaskManager
from agentic_framework.mcp_tools import MCPTool, ToolChain, ToolRegistry
from agentic_framework.monitoring import Monitor, EventTracer, AlertManager, Dashboard, AnomalyDetector
from agentic_framework.guardrails import ValidationGuardrail, PolicyEnforcer
from agentic_framework.evaluation import EvaluationMetric, AutomatedTester, HumanReviewEvaluator
from agentic_framework.knowledge import KnowledgeBase, RAGRetriever, SemanticSearchRetriever
from agentic_framework.llms import LLMInterface, LLMSelector, LLMPromptEngineer
from agentic_framework.communication import StreamtableHTTPProtocol, SecureCommunicationProtocol, ProtocolSelector
from agentic_framework.memory import ShortTermMemory, LongTermMemory
from agentic_framework.hub import AgentHub, PromptHub
from agentic_framework.configurations import BaseConfiguration, AgentConfiguration, ToolConfiguration, MonitoringConfiguration, KnowledgeConfiguration, EvaluationConfiguration, GuardrailConfiguration, MemoryConfiguration, ConfigurationManager, ConfigurationError
from agentic_framework.security import SecurityManager

class TestAgents(unittest.TestCase):
    def setUp(self):
        self.agent = Agent(name="test-agent")
        self.manager = AgentManager(name="test-manager")
    
    def test_agent_initialization(self):
        self.assertEqual(self.agent.name, "test-agent")
        self.assertTrue(self.agent.active)
    
    def test_agent_start_stop(self):
        result = self.agent.start()
        self.assertEqual(result, "Agent test-agent started")
        result = self.agent.stop()
        self.assertEqual(result, "Agent test-agent stopped")
    
    def test_agent_manager(self):
        self.manager.add_agent(self.agent)
        self.assertIn("test-agent", self.manager.agents)
        result = self.manager.start_all()
        self.assertEqual(result, "Started 1 agents")
    
    def test_agent_task_performance(self):
        result = self.agent.perform_task("test-task")
        self.assertEqual(result, "Task test-task performed by test-agent")
    
    def test_agent_coordination(self):
        self.manager.add_agent(Agent(name="agent2"))
        result = self.manager.coordinate_task("coordinated-task")
        self.assertTrue("Task coordinated among" in result)

class TestPrompts(unittest.TestCase):
    def setUp(self):
        self.template = PromptTemplate(name="test-template")
        self.chain = PromptChain(name="test-chain")
    
    def test_prompt_template(self):
        self.template.set_structure("Test structure with {placeholder}")
        result = self.template.generate({"placeholder": "value"})
        self.assertEqual(result, "Test structure with value")
    
    def test_prompt_chain(self):
        self.chain.add_prompt(self.template)
        self.assertEqual(len(self.chain.prompts), 1)
        result = self.chain.execute({"placeholder": "chain-value"})
        self.assertTrue("Test structure with chain-value" in result)

class TestProcess(unittest.TestCase):
    def setUp(self):
        self.scheduler = ProcessScheduler(name="test-scheduler")
    
    def test_process_scheduler_sequential(self):
        result = self.scheduler.schedule_sequential(["task1", "task2"])
        self.assertEqual(result, "Scheduled 2 tasks sequentially")
    
    def test_process_scheduler_parallel(self):
        result = self.scheduler.schedule_parallel(["task1", "task2"])
        self.assertEqual(result, "Scheduled 2 tasks in parallel")
    
    def test_process_scheduler_hybrid(self):
        result = self.scheduler.schedule_hybrid(["task1", "task2"])
        self.assertEqual(result, "Scheduled 2 tasks in hybrid mode")
    
    def test_process_error(self):
        with self.assertRaises(ProcessError):
            raise ProcessError("Test error")

class TestTasks(unittest.TestCase):
    def setUp(self):
        self.task = Task(name="test-task", description="Test task description")
        self.manager = TaskManager(name="test-task-manager")
    
    def test_task_initialization(self):
        self.assertEqual(self.task.name, "test-task")
        self.assertEqual(self.task.status, "pending")
    
    def test_task_execution(self):
        result = self.task.execute()
        self.assertEqual(result, "Task test-task executed with status: pending")
        self.assertEqual(self.task.status, "completed")
    
    def test_task_manager(self):
        self.manager.add_task(self.task)
        self.assertIn("test-task", self.manager.tasks)
        result = self.manager.prioritize_tasks()
        self.assertEqual(result, "Tasks prioritized: 1 tasks")
        result = self.manager.orchestrate_tasks()
        self.assertTrue("Orchestrated 1 tasks" in result)

class TestMCPTools(unittest.TestCase):
    def setUp(self):
        self.tool = MCPTool(name="test-tool")
        self.chain = ToolChain(name="test-tool-chain")
        self.registry = ToolRegistry(name="test-registry")
    
    def test_mcp_tool(self):
        result = self.tool.execute("test-operation")
        self.assertEqual(result, "Tool test-tool executed operation: test-operation")
    
    def test_tool_chain(self):
        self.chain.add_tool(self.tool)
        self.assertEqual(len(self.chain.tools), 1)
        result = self.chain.execute_chain("test-chain-op")
        self.assertTrue("Executed tool test-tool with test-chain-op" in result)
    
    def test_tool_registry(self):
        self.registry.register_tool(self.tool)
        self.assertIn("test-tool", self.registry.tools)
        found_tool = self.registry.find_tool("test-tool")
        self.assertEqual(found_tool.name, "test-tool")

class TestMonitoring(unittest.TestCase):
    def setUp(self):
        self.monitor = Monitor(name="test-monitor")
        self.tracer = EventTracer(name="test-tracer")
        self.alert_manager = AlertManager(name="test-alert-manager")
        self.dashboard = Dashboard(name="test-dashboard")
        self.anomaly_detector = AnomalyDetector(name="test-anomaly-detector")
    
    def test_monitor_metrics(self):
        result = self.monitor.collect_metrics("test-metric", 100)
        self.assertEqual(result, "Collected metric test-metric with value 100")
        self.assertEqual(len(self.monitor.metrics), 1)
    
    def test_event_tracer(self):
        result = self.tracer.trace_event("test-event", {"key": "value"})
        self.assertEqual(result, "Tracing event test-event with data {'key': 'value'}")
        self.assertEqual(len(self.tracer.events), 1)
    
    def test_alert_manager(self):
        result = self.alert_manager.set_threshold("error_rate", 0.5)
        self.assertEqual(result, "Threshold for error_rate set to 0.5")
        alert_result = self.alert_manager.check_alerts({"error_rate": 0.6})
        self.assertTrue("Alert triggered for error_rate: 0.6 exceeds threshold 0.5" in alert_result)
    
    def test_dashboard(self):
        result = self.dashboard.update_view("test-metric", 200)
        self.assertEqual(result, "Dashboard updated: test-metric = 200")
        self.assertEqual(self.dashboard.views["test-metric"], 200)
    
    def test_anomaly_detector(self):
        for i in range(15):
            self.anomaly_detector.history.append({"metric": "test", "value": 10 + i})
        result = self.anomaly_detector.detect_anomalies(window_size=10, threshold=1.5)
        self.assertTrue(isinstance(result, list))

class TestGuardrails(unittest.TestCase):
    def setUp(self):
        self.guardrail = ValidationGuardrail(name="test-guardrail")
        self.enforcer = PolicyEnforcer(name="test-enforcer")
    
    def test_validation_guardrail(self):
        result = self.guardrail.validate_input("test-input", {"format": "string"})
        self.assertEqual(result, "Input test-input validated against {'format': 'string'}")
        result = self.guardrail.validate_output("test-output", {"format": "string"})
        self.assertEqual(result, "Output test-output validated against {'format': 'string'}")
    
    def test_policy_enforcer(self):
        result = self.enforcer.enforce_policy("test-policy", {"rule": "allow"})
        self.assertEqual(result, "Policy test-policy enforced with {'rule': 'allow'}")
        check_result = self.enforcer.check_compliance("test-action", {"rule": "allow"})
        self.assertTrue("Action test-action is compliant with {'rule': 'allow'}" in check_result)

class TestEvaluation(unittest.TestCase):
    def setUp(self):
        self.metric = EvaluationMetric(name="test-metric")
        self.tester = AutomatedTester(name="test-tester")
        self.reviewer = HumanReviewEvaluator(name="test-reviewer")
    
    def test_evaluation_metric(self):
        result = self.metric.calculate_score([1, 2, 3, 4, 5])
        self.assertEqual(result, 3.0)
    
    def test_automated_tester(self):
        result = self.tester.run_tests(["test1", "test2"])
        self.assertEqual(result, "Ran 2 tests with results: ['test1: pass', 'test2: pass']")
    
    def test_human_reviewer(self):
        result = self.reviewer.review_output("test-output", {"clarity": 5, "accuracy": 4})
        self.assertTrue("Reviewed test-output with scores {'clarity': 5, 'accuracy': 4}" in result)

class TestKnowledge(unittest.TestCase):
    def setUp(self):
        self.base = KnowledgeBase(name="test-base")
        self.rag = RAGRetriever(name="test-rag")
        self.semantic = SemanticSearchRetriever(name="test-semantic")
    
    def test_knowledge_base(self):
        self.base.add_document("doc1", "content1")
        self.assertIn("doc1", self.base.documents)
        result = self.base.retrieve("doc1")
        self.assertEqual(result, "content1")
    
    def test_rag_retriever(self):
        result = self.rag.retrieve_and_generate("test-query", {"source": "internal"})
        self.assertTrue("Retrieved documents for test-query from internal" in result)
        self.assertTrue("Generated response based on retrieved documents" in result)
    
    def test_semantic_search(self):
        result = self.semantic.search("test-query", {"method": "embedding"})
        self.assertEqual(result, "Semantic search results for test-query using embedding: ['doc1', 'doc2']")

class TestLLMs(unittest.TestCase):
    def setUp(self):
        self.interface = LLMInterface(name="test-llm")
        self.selector = LLMSelector(name="test-selector")
        self.engineer = LLMPromptEngineer(name="test-engineer")
    
    def test_llm_interface(self):
        result = self.interface.generate_response("test-prompt")
        self.assertEqual(result, "Generated response for test-prompt using test-llm")
    
    def test_llm_selector(self):
        result = self.selector.select_model({"task": "text-generation"})
        self.assertEqual(result.name, "text-model")
    
    def test_llm_prompt_engineer(self):
        result = self.engineer.optimize_prompt("raw-prompt", {"goal": "clarity"})
        self.assertEqual(result, "Optimized prompt: raw-prompt for clarity")

class TestCommunication(unittest.TestCase):
    def setUp(self):
        self.http_protocol = StreamtableHTTPProtocol(name="test-http")
        self.secure_protocol = SecureCommunicationProtocol(name="test-secure")
        self.selector = ProtocolSelector(name="test-selector")
    
    def test_streamtable_http(self):
        result = self.http_protocol.stream_data("test-data", {"target": "server"})
        self.assertEqual(result, "Streaming test-data to server via HTTP")
    
    def test_secure_protocol(self):
        result = self.secure_protocol.encrypt_data("test-data")
        self.assertEqual(result, "Encrypted test-data with AES-256")
        result = self.secure_protocol.authenticate("test-user", {"method": "token"})
        self.assertEqual(result, "Authenticated test-user with token")
    
    def test_protocol_selector(self):
        result = self.selector.select_protocol({"requirement": "low-latency"})
        self.assertEqual(result.name, "websocket")

class TestMemory(unittest.TestCase):
    def setUp(self):
        self.short_term = ShortTermMemory(name="test-short-term")
        self.long_term = LongTermMemory(name="test-long-term")
    
    def test_short_term_memory(self):
        result = self.short_term.store("key1", "value1")
        self.assertEqual(result, "Stored key1 in short-term memory test-short-term")
        result = self.short_term.retrieve("key1")
        self.assertEqual(result, "value1")
        result = self.short_term.clear_expired()
        self.assertTrue("Cleared expired entries from test-short-term" in result)
    
    def test_long_term_memory(self):
        result = self.long_term.store("key2", "value2", {"category": "test"})
        self.assertEqual(result, "Stored key2 in long-term memory test-long-term with metadata {'category': 'test'}")
        result = self.long_term.retrieve("key2")
        self.assertEqual(result, "value2")
        result = self.long_term.search({"category": "test"})
        self.assertTrue("Found 1 entries matching {'category': 'test'}" in result)

class TestHub(unittest.TestCase):
    def setUp(self):
        self.agent_hub = AgentHub(name="test-agent-hub")
        self.prompt_hub = PromptHub(name="test-prompt-hub")
        self.agent = Agent(name="hub-agent")
        self.prompt = PromptTemplate(name="hub-prompt")
    
    def test_agent_hub(self):
        result = self.agent_hub.register_agent(self.agent, {"domain": "test"})
        self.assertTrue("Registered agent hub-agent with metadata {'domain': 'test'}" in result)
        search_result = self.agent_hub.search_agents({"domain": "test"})
        self.assertTrue("Found 1 agents matching {'domain': 'test'}" in search_result)
        domain_result = self.agent_hub.get_agents_by_domain("test")
        self.assertTrue("Found 1 agents in domain test" in domain_result)
        capability_result = self.agent_hub.get_agents_by_capability("task_execution")
        self.assertTrue("Found 1 agents with capability task_execution" in capability_result)
    
    def test_prompt_hub(self):
        result = self.prompt_hub.register_prompt(self.prompt, {"use_case": "testing"})
        self.assertTrue("Registered prompt hub-prompt with metadata {'use_case': 'testing'}" in result)
        search_result = self.prompt_hub.search_prompts({"use_case": "testing"})
        self.assertTrue("Found 1 prompts matching {'use_case': 'testing'}" in search_result)
        category_result = self.prompt_hub.get_prompts_by_category("testing")
        self.assertTrue("Found 1 prompts in category testing" in category_result)

class TestConfigurations(unittest.TestCase):
    def setUp(self):
        self.base_config = BaseConfiguration(name="test-base-config")
        self.agent_config = AgentConfiguration(name="test-agent-config")
        self.tool_config = ToolConfiguration(name="test-tool-config")
        self.monitoring_config = MonitoringConfiguration(name="test-monitoring-config")
        self.knowledge_config = KnowledgeConfiguration(name="test-knowledge-config")
        self.evaluation_config = EvaluationConfiguration(name="test-evaluation-config")
        self.guardrail_config = GuardrailConfiguration(name="test-guardrail-config")
        self.memory_config = MemoryConfiguration(name="test-memory-config")
        self.manager = ConfigurationManager(name="test-config-manager")
    
    def test_base_configuration(self):
        result = self.base_config.set_setting("key", "value")
        self.assertEqual(result, "Set key to value in test-base-config")
        value = self.base_config.get_setting("key")
        self.assertEqual(value, "value")
        validation_result = self.base_config.validate()
        self.assertEqual(validation_result, "Configuration test-base-config validated successfully")
        reload_result = self.base_config.reload({"new_key": "new_value"})
        self.assertTrue("Configuration test-base-config reloaded with 2 settings" in reload_result)
        env_result = self.base_config.set_environment("test-env")
        self.assertEqual(env_result, "Environment set to test-env for test-base-config")
    
    def test_agent_configuration(self):
        result = self.agent_config.set_role("specialist")
        self.assertEqual(result, "Set role to specialist in test-agent-config")
        cap_result = self.agent_config.add_capability("special_task")
        self.assertEqual(cap_result, "Added capability special_task to test-agent-config")
        limit_result = self.agent_config.set_execution_limit(200)
        self.assertEqual(limit_result, "Set execution_limit to 200 in test-agent-config")
        sec_result = self.agent_config.set_security_level("high")
        self.assertEqual(sec_result, "Set security_level to high in test-agent-config")
    
    def test_tool_configuration(self):
        api_result = self.tool_config.set_api_key("test-key")
        self.assertEqual(api_result, "Set api_key to test-key in test-tool-config")
        auth_result = self.tool_config.set_auth_method("oauth")
        self.assertEqual(auth_result, "Set auth_method to oauth in test-tool-config")
        rate_result = self.tool_config.set_rate_limit(500)
        self.assertEqual(rate_result, "Set rate_limit to 500 in test-tool-config")
        mode_result = self.tool_config.set_operational_mode("async")
        self.assertEqual(mode_result, "Set operational_mode to async in test-tool-config")
        dep_result = self.tool_config.add_dependency("dep1")
        self.assertEqual(dep_result, "Added dependency dep1 to test-tool-config")
        comp_result = self.tool_config.set_compatibility("tool1", "1.0")
        self.assertEqual(comp_result, "Set compatibility for tool1 to version 1.0 in test-tool-config")
    
    def test_monitoring_configuration(self):
        metrics_result = self.monitoring_config.enable_metrics_collection(True)
        self.assertEqual(metrics_result, "Set metrics_collection to True in test-monitoring-config")
        tracing_result = self.monitoring_config.enable_event_tracing(True)
        self.assertEqual(tracing_result, "Set event_tracing to True in test-monitoring-config")
        log_result = self.monitoring_config.set_logging_level("debug")
        self.assertEqual(log_result, "Set logging_level to debug in test-monitoring-config")
        threshold_result = self.monitoring_config.set_alert_threshold("error_rate", 0.2)
        self.assertEqual(threshold_result, "Set alert threshold for error_rate to 0.2 in test-monitoring-config")
        int_result = self.monitoring_config.add_integration("prometheus", {"host": "localhost"})
        self.assertEqual(int_result, "Added integration with prometheus to test-monitoring-config")
    
    def test_knowledge_configuration(self):
        source_result = self.knowledge_config.set_source_prioritization(["external", "internal"])
        self.assertEqual(source_result, "Set source_prioritization to ['external', 'internal'] in test-knowledge-config")
        index_result = self.knowledge_config.set_indexing_strategy("full-text")
        self.assertEqual(index_result, "Set indexing_strategy to full-text in test-knowledge-config")
        cache_policy_result = self.knowledge_config.set_caching_policy("FIFO")
        self.assertEqual(cache_policy_result, "Set caching_policy to FIFO in test-knowledge-config")
        cache_size_result = self.knowledge_config.set_cache_size(500)
        self.assertEqual(cache_size_result, "Set cache_size to 500 in test-knowledge-config")
        access_result = self.knowledge_config.set_access_control("source1", "read-only")
        self.assertEqual(access_result, "Set access control for source1 to read-only in test-knowledge-config")
    
    def test_evaluation_configuration(self):
        criteria_result = self.evaluation_config.set_criteria("precision", 0.85)
        self.assertEqual(criteria_result, "Set evaluation criteria for precision to 0.85 in test-evaluation-config")
        selection_result = self.evaluation_config.set_test_case_selection("priority")
        self.assertEqual(selection_result, "Set test_case_selection to priority in test-evaluation-config")
        rate_result = self.evaluation_config.set_sampling_rate(0.2)
        self.assertEqual(rate_result, "Set sampling_rate to 0.2 in test-evaluation-config")
        format_result = self.evaluation_config.set_reporting_format("csv")
        self.assertEqual(format_result, "Set reporting_format to csv in test-evaluation-config")
        mode_result = self.evaluation_config.enable_mode("automated")
        self.assertTrue("Evaluation mode automated already enabled" in mode_result)
    
    def test_guardrail_configuration(self):
        policy_result = self.guardrail_config.add_policy_definition("policy1", {"allow": True})
        self.assertEqual(policy_result, "Added policy definition policy1 to test-guardrail-config")
        rule_result = self.guardrail_config.add_validation_rule("rule1")
        self.assertEqual(rule_result, "Added validation rule rule1 to test-guardrail-config")
        filter_result = self.guardrail_config.add_content_filter("prohibited")
        self.assertEqual(filter_result, "Added content filter prohibited to test-guardrail-config")
        rate_result = self.guardrail_config.set_rate_limit(200)
        self.assertEqual(rate_result, "Set rate_limit to 200 in test-guardrail-config")
    
    def test_memory_configuration(self):
        retention_result = self.memory_config.set_retention_policy("size_based")
        self.assertEqual(retention_result, "Set retention_policy to size_based in test-memory-config")
        backend_result = self.memory_config.set_storage_backend("disk")
        self.assertEqual(backend_result, "Set storage_backend to disk in test-memory-config")
        index_result = self.memory_config.set_indexing_method("tree")
        self.assertEqual(index_result, "Set indexing_method to tree in test-memory-config")
        encrypt_result = self.memory_config.enable_encryption(True)
        self.assertEqual(encrypt_result, "Set encryption to True in test-memory-config")
        tier_result = self.memory_config.configure_tiered_storage("fast", {"speed": "high"})
        self.assertEqual(tier_result, "Configured tiered storage fast in test-memory-config")
    
    def test_configuration_manager(self):
        result = self.manager.add_configuration(self.base_config)
        self.assertEqual(result, "Added configuration test-base-config to test-config-manager")
        config = self.manager.get_configuration("test-base-config")
        self.assertEqual(config.name, "test-base-config")
        list_result = self.manager.list_configurations()
        self.assertEqual(list_result, ["test-base-config"])
        template_result = self.manager.apply_template("test-template", "test-base-config")
        self.assertEqual(template_result, "Applied template test-template to test-base-config")
        validate_result = self.manager.validate_all()
        self.assertEqual(len(validate_result), 1)
        self.assertTrue("validated successfully" in validate_result[0])
        remove_result = self.manager.remove_configuration("test-base-config")
        self.assertEqual(remove_result, "Removed configuration test-base-config from test-config-manager")

class TestSecurity(unittest.TestCase):
    def setUp(self):
        self.security = SecurityManager(name="test-security")
    
    def test_security_manager(self):
        result = self.security.authenticate_user("test-user", "test-pass")
        self.assertEqual(result, "User test-user authenticated successfully")
        token_result = self.security.generate_token("test-user", {"role": "admin"})
        self.assertTrue("Generated token for test-user with payload {'role': 'admin'}" in token_result)
        encrypt_result = self.security.encrypt_data("test-data", "test-key")
        self.assertEqual(encrypt_result, "Encrypted test-data with key test-key")
        decrypt_result = self.security.decrypt_data("encrypted-test-data", "test-key")
        self.assertEqual(decrypt_result, "Decrypted encrypted-test-data with key test-key")
        policy_result = self.security.enforce_access_policy("test-user", "read", "resource1")
        self.assertTrue("Access policy enforced for test-user on resource1 with action read" in policy_result)

if __name__ == '__main__':
    unittest.main()
