"""
Extended Coverage Tests for Enterprise Modules.

Focuses on improving coverage for modules with lower test coverage:
- ci_cd.py (36%)
- integrations.py (40%)
- prompt_versioning.py (31%)
- evaluation_advanced.py (52%)
- infrastructure.py (53%)
"""

import pytest
import time
from unittest.mock import MagicMock, patch


# =============================================================================
# CI/CD Module Extended Coverage
# =============================================================================
@pytest.mark.skip(reason="CI/CD module was removed from the package")
class TestCICDExtendedCoverage:
    """Extended coverage tests for CI/CD module."""
    
    def test_pipeline_full_execution(self):
        """Test full pipeline execution flow."""
        from agenticaiframework import AgentCIPipeline, PipelineStage, StageType
        
        pipeline = AgentCIPipeline(name="test_pipeline")
        
        # Add multiple stages
        stage1 = PipelineStage(
            name="build",
            stage_type=StageType.BUILD,
            commands=["echo build"],
            timeout_seconds=60
        )
        stage2 = PipelineStage(
            name="test",
            stage_type=StageType.TEST,
            commands=["echo test"],
            timeout_seconds=120
        )
        
        pipeline.add_stage(stage1)
        pipeline.add_stage(stage2)
        
        assert len(pipeline.stages) == 2
        assert "build" in pipeline.stage_order
        assert "test" in pipeline.stage_order
    
    def test_pipeline_stage_removal(self):
        """Test removing a stage from pipeline."""
        from agenticaiframework import AgentCIPipeline, PipelineStage, StageType
        
        pipeline = AgentCIPipeline(name="removal_test")
        
        stage = PipelineStage(
            name="temp_stage",
            stage_type=StageType.BUILD,
            commands=["echo temp"]
        )
        pipeline.add_stage(stage)
        assert "temp_stage" in pipeline.stages
        
        pipeline.remove_stage("temp_stage")
        assert "temp_stage" not in pipeline.stages
    
    def test_pipeline_set_environment(self):
        """Test setting pipeline environment variables."""
        from agenticaiframework import AgentCIPipeline
        
        pipeline = AgentCIPipeline(name="env_test")
        pipeline.set_environment({"API_KEY": "test", "DEBUG": "true"})
        
        assert pipeline.environment["API_KEY"] == "test"
        assert pipeline.environment["DEBUG"] == "true"
    
    def test_deployment_manager_deploy_and_rollback(self):
        """Test deployment and rollback flow."""
        from agenticaiframework import deployment_manager
        
        # Register a new environment
        deployment_manager.register_environment(
            name="staging_test",
            config={"url": "https://staging.example.com", "region": "us-east"}
        )
        
        # Deploy
        deploy_result = deployment_manager.deploy(
            environment="staging_test",
            version="1.0.0",
            artifacts={"app": "myapp.zip"},
            deployer="test_user"
        )
        
        assert deploy_result["status"] == "deployed"
        assert deploy_result["version"] == "1.0.0"
    
    def test_deployment_health_check(self):
        """Test deployment health check."""
        from agenticaiframework import deployment_manager
        
        # Ensure environment exists
        if "health_test" not in deployment_manager.environments:
            deployment_manager.register_environment(
                name="health_test",
                config={"url": "https://health.example.com"}
            )
            deployment_manager.deploy(
                environment="health_test",
                version="1.0.0"
            )
        
        health = deployment_manager.check_health("health_test")
        assert "status" in health
    
    def test_release_manager_publish(self):
        """Test release creation and publishing."""
        from agenticaiframework import release_manager
        
        # Create a new version
        release = release_manager.create_release(
            version="2.0.0",
            release_notes="Major release with new features",
            changes=[{"type": "feature", "description": "New API"}]
        )
        
        assert release["version"] == "2.0.0"
        assert release["status"] == "draft"
    
    def test_pipeline_stage_dataclass(self):
        """Test PipelineStage dataclass attributes."""
        from agenticaiframework import PipelineStage, StageType
        
        stage = PipelineStage(
            name="full_stage",
            stage_type=StageType.SECURITY_SCAN,
            commands=["security-scan", "--all"],
            timeout_seconds=600,
            continue_on_failure=True,
            dependencies=["build"],
            environment={"SCAN_LEVEL": "deep"},
            artifacts=["report.json"]
        )
        
        assert stage.name == "full_stage"
        assert stage.stage_type == StageType.SECURITY_SCAN
        assert stage.timeout_seconds == 600
        assert stage.continue_on_failure is True
        assert "build" in stage.dependencies


# =============================================================================
# Prompt Versioning Extended Coverage
# =============================================================================
class TestPromptVersioningExtendedCoverage:
    """Extended coverage tests for prompt versioning module."""
    
    def test_prompt_version_manager_create_prompt(self):
        """Test creating versioned prompts."""
        from agenticaiframework import PromptVersionManager
        
        manager = PromptVersionManager()
        
        prompt = manager.create_prompt(
            name="greeting_prompt",
            template="Hello, {name}! Welcome to {service}.",
            metadata={"author": "test", "category": "greetings"}
        )
        
        assert prompt is not None
        assert prompt.name == "greeting_prompt"
    
    def test_prompt_version_manager_get_prompt(self):
        """Test retrieving prompts."""
        from agenticaiframework import PromptVersionManager
        
        manager = PromptVersionManager()
        
        # Create first
        created = manager.create_prompt(
            name="retrieval_test",
            template="Test template"
        )
        
        # Retrieve
        prompt = manager.get_prompt(created.prompt_id)
        assert prompt is not None
        assert prompt.template == "Test template"
    
    def test_prompt_version_manager_update_prompt(self):
        """Test creating new version of prompts."""
        from agenticaiframework import PromptVersionManager
        
        manager = PromptVersionManager()
        
        # Create initial
        created = manager.create_prompt(
            name="version_test",
            template="Version 1"
        )
        
        # Create new version
        new_version = manager.create_version(
            prompt_id=created.prompt_id,
            template="Version 2",
            created_by="test_user"
        )
        
        assert new_version is not None
        assert new_version.template == "Version 2"
    
    def test_prompt_library_register_component(self):
        """Test prompt library register and compose operations."""
        from agenticaiframework import PromptLibrary
        
        library = PromptLibrary()
        
        # Register component
        library.register_component(
            name="lib_component",
            content="Library component: {content}",
            category="general",
            description="A test component"
        )
        
        component = library.components.get("lib_component")
        assert component is not None
        assert component["category"] == "general"


# =============================================================================
# Evaluation Advanced Extended Coverage
# =============================================================================
class TestEvaluationAdvancedExtendedCoverage:
    """Extended coverage tests for advanced evaluation module."""
    
    def test_offline_evaluator_scorer_registration(self):
        """Test registering custom scorers."""
        from agenticaiframework import OfflineEvaluator
        
        evaluator = OfflineEvaluator()
        
        def custom_scorer(expected, actual):
            return 1.0 if expected == actual else 0.0
        
        evaluator.register_scorer("custom", custom_scorer)
        
        assert "custom" in evaluator.scorers
    
    def test_online_evaluator_alert_setup(self):
        """Test online evaluator alert configuration."""
        from agenticaiframework import OnlineEvaluator
        
        evaluator = OnlineEvaluator(window_size=500)
        
        # Set alert threshold
        evaluator.set_alert_threshold("response_length", 0.3)
        
        assert "response_length" in evaluator.alert_thresholds
        assert evaluator.alert_thresholds["response_length"] == 0.3
    
    def test_online_evaluator_record(self):
        """Test recording online evaluations."""
        from agenticaiframework import OnlineEvaluator
        
        evaluator = OnlineEvaluator()
        
        result = evaluator.record(
            input_data="test input",
            output="test output",
            context={"latency_ms": 150}
        )
        
        assert result is not None
        assert result.actual_output == "test output"
    
    def test_cost_quality_scorer_budget(self):
        """Test budget tracking in cost quality scorer."""
        from agenticaiframework import CostQualityScorer
        
        scorer = CostQualityScorer()
        
        # Set budget
        scorer.set_budget("project_budget", 100.0)
        
        # Record executions
        scorer.record_execution(
            model_name="gpt-4",
            input_tokens=1000,
            output_tokens=2000,
            quality_score=0.9,
            budget_name="project_budget"
        )
        
        spent = scorer.get_budget_spent("project_budget")
        assert spent > 0
    
    def test_security_risk_scorer_pii_detection(self):
        """Test PII detection in security risk scorer."""
        from agenticaiframework import SecurityRiskScorer
        
        scorer = SecurityRiskScorer()
        
        # Test with PII content
        assessment = scorer.assess_risk(
            output_text="Contact me at john@example.com or call 555-123-4567"
        )
        
        assert "pii_detected" in assessment
        assert len(assessment["pii_detected"]) > 0
    
    def test_ab_testing_record_result(self):
        """Test recording A/B test results."""
        from agenticaiframework import ABTestingFramework
        
        ab = ABTestingFramework()
        
        # Create experiment
        ab.create_experiment(
            name="ab_record_test",
            variants=["control", "variant_a"]
        )
        
        # Record results
        ab.record_result(
            experiment_name="ab_record_test",
            variant="control",
            metrics={"conversion": 0.1, "latency": 200},
            user_id="user_001"
        )
        
        ab.record_result(
            experiment_name="ab_record_test",
            variant="variant_a",
            metrics={"conversion": 0.15, "latency": 180},
            user_id="user_002"
        )
        
        # Check results stored
        results = ab.experiment_results["ab_record_test"]
        assert len(results) == 2


# =============================================================================
# Infrastructure Extended Coverage
# =============================================================================
class TestInfrastructureExtendedCoverage:
    """Extended coverage tests for infrastructure module."""
    
    def test_multi_region_routing_modes(self):
        """Test different routing modes."""
        from agenticaiframework import MultiRegionManager, Region, RegionConfig
        
        manager = MultiRegionManager()
        
        # Register regions
        manager.register_region(RegionConfig(
            region=Region.US_EAST,
            endpoint="https://us-east.example.com",
            is_primary=True,
            weight=2.0
        ))
        manager.register_region(RegionConfig(
            region=Region.US_WEST,
            endpoint="https://us-west.example.com",
            is_primary=False,
            weight=1.0
        ))
        
        # Test latency routing (default)
        region = manager.get_region()
        assert region is not None
        
        # Test round-robin
        manager.set_routing_mode("round-robin")
        region = manager.get_region()
        assert region is not None
        
        # Test weighted
        manager.set_routing_mode("weighted")
        region = manager.get_region()
        assert region is not None
        
        # Test primary-only
        manager.set_routing_mode("primary-only")
        region = manager.get_region()
        assert region == Region.US_EAST
    
    def test_tenant_manager_quota_operations(self):
        """Test tenant quota checking and consumption."""
        from agenticaiframework import tenant_manager
        
        # Create tenant
        tenant = tenant_manager.create_tenant(
            name="Quota Test Corp",
            tier="standard"
        )
        
        # Check quota
        has_quota = tenant_manager.check_quota(
            tenant.tenant_id,
            "requests_per_day",
            1
        )
        assert has_quota is True
        
        # Consume quota
        consumed = tenant_manager.consume_quota(
            tenant.tenant_id,
            "requests_per_day",
            1
        )
        assert consumed is True
        
        # Get usage
        usage = tenant_manager.get_usage(tenant.tenant_id)
        assert usage["usage"]["requests_per_day"] == 1
    
    def test_serverless_executor_deploy_invoke(self):
        """Test function deployment and invocation."""
        from agenticaiframework import ServerlessExecutor
        
        executor = ServerlessExecutor()
        
        # Define handler (takes event and context)
        def echo_handler(event, context=None):
            return {"echo": event.get("message", "no message")}
        
        # Deploy
        func = executor.deploy_function(
            name="echo_test_func",
            handler=echo_handler,
            runtime="python3.9",
            memory_mb=128,
            timeout_seconds=30
        )
        
        assert func is not None
        
        # Invoke
        result = executor.invoke(
            func.function_id,
            {"message": "hello"}
        )
        
        assert result.output_data["echo"] == "hello"
    
    def test_distributed_coordinator_leader_election(self):
        """Test leader election mechanism."""
        from agenticaiframework import DistributedCoordinator
        
        coord1 = DistributedCoordinator(node_id="node_1")
        coord2 = DistributedCoordinator(node_id="node_2")
        
        # Elect leader
        leader = coord1.elect_leader()
        assert leader is not None


# =============================================================================
# Integrations Extended Coverage
# =============================================================================
class TestIntegrationsExtendedCoverage:
    """Extended coverage tests for integrations module."""
    
    def test_webhook_manager_event_handling(self):
        """Test webhook event handler registration."""
        from agenticaiframework import WebhookManager
        
        wm = WebhookManager()
        
        events_received = []
        
        def handler(event_type, payload):
            events_received.append((event_type, payload))
            return {"handled": True}
        
        wm.add_event_handler("task.complete", handler)
        
        # Register incoming webhook
        webhook = wm.register_incoming_webhook(
            name="event_test",
            allowed_events=["task.complete"]
        )
        
        # Process event
        result = wm.process_incoming(
            webhook["id"],
            "task.complete",
            {"task_id": "123"}
        )
        
        assert result["handlers_executed"] == 1
        assert len(events_received) == 1
    
    def test_webhook_manager_signature_verification(self):
        """Test webhook signature verification."""
        from agenticaiframework import WebhookManager
        import hmac
        import hashlib
        
        wm = WebhookManager()
        
        secret = "test_secret_key"
        webhook = wm.register_incoming_webhook(
            name="sig_test",
            secret=secret
        )
        
        payload = '{"data": "test"}'
        expected_sig = hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Verify correct signature
        result = wm.verify_signature(
            webhook["id"],
            payload,
            f"sha256={expected_sig}"
        )
        
        assert result is True
    
    def test_integration_manager_add_integration(self):
        """Test adding integrations through manager."""
        from agenticaiframework import integration_manager
        
        config = integration_manager.add_integration(
            name="test_github_int",
            integration_type="github",
            endpoint="https://api.github.com",
            auth_type="api_key",
            credentials={"api_key": "test_key"}
        )
        
        assert config is not None
        assert config.name == "test_github_int"
    
    def test_github_integration_operations(self):
        """Test GitHub integration operations."""
        from agenticaiframework import GitHubIntegration, IntegrationConfig, IntegrationStatus
        
        config = IntegrationConfig(
            integration_id="gh_001",
            name="GitHub Test",
            integration_type="github",
            endpoint="https://api.github.com",
            auth_type="api_key",
            credentials={"api_key": "test_token"},
            settings={},
            status=IntegrationStatus.PENDING,
            created_at=time.time()
        )
        
        github = GitHubIntegration(config)
        
        # Connect (simulated)
        connected = github.connect()
        assert connected is True
        
        # Create issue
        issue = github.create_issue(
            owner="testorg",
            repo="testrepo",
            title="Test Issue",
            body="This is a test issue"
        )
        
        assert issue["title"] == "Test Issue"
        assert "html_url" in issue


# =============================================================================
# Tracing Extended Coverage
# =============================================================================
class TestTracingExtendedCoverage:
    """Extended coverage tests for tracing module."""
    
    def test_tracer_full_workflow(self):
        """Test complete tracing workflow."""
        from agenticaiframework import AgentStepTracer
        
        tracer = AgentStepTracer()
        
        # Start trace - returns SpanContext
        context = tracer.start_trace(name="full_workflow_test")
        
        assert context is not None
        
        # Start child span using context
        child_context = tracer.start_span("child_operation", context)
        
        # End spans
        tracer.end_span(child_context)
        tracer.end_span(context)
        
        # Get trace
        trace = tracer.get_trace(context.trace_id)
        assert trace is not None
    
    def test_latency_metrics_recording(self):
        """Test latency metrics recording and percentiles."""
        from agenticaiframework import LatencyMetrics
        
        metrics = LatencyMetrics()
        
        # Record multiple latencies
        for i in range(100):
            metrics.record("test_operation", i + 1)
        
        # Get percentile (singular)
        p50 = metrics.get_percentile("test_operation", 50)
        p95 = metrics.get_percentile("test_operation", 95)
        
        assert p50 is not None
        assert p95 is not None


# =============================================================================
# Compliance Extended Coverage
# =============================================================================
class TestComplianceExtendedCoverage:
    """Extended coverage tests for compliance module."""
    
    def test_audit_trail_query_operations(self):
        """Test querying audit trail."""
        from agenticaiframework import AuditTrailManager, AuditEventType, AuditSeverity
        
        manager = AuditTrailManager()
        
        # Log multiple events
        for i in range(5):
            manager.log(
                event_type=AuditEventType.ACCESS,
                actor=f"user_{i}",
                resource=f"resource_{i}",
                action="read"
            )
        
        # Query by actor
        events = manager.query(actor="user_0")
        assert len(events) >= 1
    
    def test_policy_engine_priorities(self):
        """Test policy priority handling."""
        from agenticaiframework import PolicyEngine
        
        engine = PolicyEngine()
        
        # Create policies with different priorities
        engine.create_allow_policy("low_priority", ".*", ".*", priority=10)
        engine.create_deny_policy("high_priority", "secret/.*", ".*", priority=100)
        
        # Test - high priority deny should win
        result = engine.evaluate("secret/data.txt", "read")
        assert result["allowed"] is False
        
        # Test - should allow when not matching deny
        result = engine.evaluate("public/data.txt", "read")
        assert result["allowed"] is True
    
    def test_data_masking_custom_rules(self):
        """Test adding custom masking rules."""
        from agenticaiframework import DataMaskingEngine, MaskingType, MaskingRule
        
        engine = DataMaskingEngine()
        
        # Add custom rule
        custom_rule = MaskingRule(
            rule_id="custom_secret",
            name="Secret Pattern",
            pattern=r"SECRET-\w+",
            data_type="secret",
            masking_type=MaskingType.FULL,
            replacement="[SECRET_REDACTED]"
        )
        engine.add_rule(custom_rule)
        
        text = "The code is SECRET-ABC123"
        masked_text, detections = engine.mask(text)
        
        assert "SECRET-ABC123" not in masked_text
        assert "[SECRET_REDACTED]" in masked_text
