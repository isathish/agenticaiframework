"""
Comprehensive tests for evaluation module.

Tests for:
- PromptDriftDetector
- ModelTierEvaluator
- CanaryDeploymentManager
"""

import pytest
import time
from unittest.mock import Mock, patch


class TestPromptDriftDetector:
    """Tests for PromptDriftDetector."""
    
    def test_init(self):
        """Test detector initialization."""
        from agenticaiframework.evaluation.drift import PromptDriftDetector
        
        detector = PromptDriftDetector(window_size=50)
        assert detector.window_size == 50
    
    def test_init_with_thresholds(self):
        """Test initialization with custom thresholds."""
        from agenticaiframework.evaluation.drift import PromptDriftDetector
        
        thresholds = {'quality_score': 5.0, 'latency_ms': 10.0}
        detector = PromptDriftDetector(drift_thresholds=thresholds)
        
        assert detector.drift_thresholds['quality_score'] == 5.0


class TestDriftTypes:
    """Tests for drift types and alerts."""
    
    def test_drift_type_enum(self):
        """Test DriftType enum."""
        from agenticaiframework.evaluation.drift import DriftType
        
        assert DriftType.QUALITY_DEGRADATION.value == "quality_degradation"
        assert DriftType.LATENCY_INCREASE.value == "latency_increase"
        assert DriftType.BEHAVIOR_SHIFT.value == "behavior_shift"
    
    def test_drift_severity_enum(self):
        """Test DriftSeverity enum."""
        from agenticaiframework.evaluation.drift import DriftSeverity
        
        assert DriftSeverity.LOW.value == "low"
        assert DriftSeverity.HIGH.value == "high"
        assert DriftSeverity.CRITICAL.value == "critical"
    
    def test_drift_alert_creation(self):
        """Test DriftAlert dataclass."""
        from agenticaiframework.evaluation.drift import DriftAlert, DriftType, DriftSeverity
        
        alert = DriftAlert(
            alert_id="a1",
            drift_type=DriftType.QUALITY_DEGRADATION,
            severity=DriftSeverity.HIGH,
            prompt_id="p1",
            metric_name="quality_score",
            baseline_value=0.9,
            current_value=0.7,
            deviation_percent=22.2,
            detected_at=time.time()
        )
        
        assert alert.drift_type == DriftType.QUALITY_DEGRADATION
        assert alert.severity == DriftSeverity.HIGH
        assert alert.baseline_value == 0.9


class TestModelTierEvaluator:
    """Tests for ModelTierEvaluator."""
    
    def test_init(self):
        """Test evaluator initialization."""
        from agenticaiframework.evaluation.model_tier import ModelTierEvaluator
        
        evaluator = ModelTierEvaluator()
        assert 'slm' in evaluator.tier_benchmarks
        assert 'llm' in evaluator.tier_benchmarks
    
    def test_tier_benchmarks(self):
        """Test tier benchmarks are set correctly."""
        from agenticaiframework.evaluation.model_tier import ModelTierEvaluator
        
        evaluator = ModelTierEvaluator()
        
        assert evaluator.tier_benchmarks['slm']['expected_latency_ms'] == 300
        assert evaluator.tier_benchmarks['llm']['min_quality_threshold'] == 0.85
    
    def test_evaluate_slm(self):
        """Test SLM evaluation."""
        from agenticaiframework.evaluation.model_tier import ModelTierEvaluator
        
        evaluator = ModelTierEvaluator()
        
        result = evaluator.evaluate_model(
            model_name="small-model",
            tier="slm",
            response="Short response",
            latency_ms=200,
            input_tokens=50,
            output_tokens=30,
            cost=0.0001
        )
        
        assert result['tier'] == 'slm'
        assert 'metrics' in result
        assert 'scores' in result
        assert result['metrics']['latency_ms'] == 200
    
    def test_evaluate_llm(self):
        """Test LLM evaluation."""
        from agenticaiframework.evaluation.model_tier import ModelTierEvaluator
        
        evaluator = ModelTierEvaluator()
        
        result = evaluator.evaluate_model(
            model_name="large-model",
            tier="llm",
            response="A longer and more detailed response",
            latency_ms=1200,
            input_tokens=200,
            output_tokens=150,
            cost=0.005
        )
        
        assert result['tier'] == 'llm'
        assert result['metrics']['total_tokens'] == 350
    
    def test_evaluate_rlm(self):
        """Test RLM evaluation with reasoning steps."""
        from agenticaiframework.evaluation.model_tier import ModelTierEvaluator
        
        evaluator = ModelTierEvaluator()
        
        result = evaluator.evaluate_model(
            model_name="reasoning-model",
            tier="rlm",
            response="Reasoned response",
            latency_ms=5000,
            input_tokens=500,
            output_tokens=300,
            cost=0.015,
            reasoning_steps=["Step 1", "Step 2", "Step 3"]
        )
        
        assert result['tier'] == 'rlm'
    
    def test_evaluate_unknown_tier(self):
        """Test evaluation with unknown tier falls back to LLM."""
        from agenticaiframework.evaluation.model_tier import ModelTierEvaluator
        
        evaluator = ModelTierEvaluator()
        
        result = evaluator.evaluate_model(
            model_name="unknown-model",
            tier="unknown_tier",
            response="Response",
            latency_ms=1000,
            input_tokens=100,
            output_tokens=50,
            cost=0.001
        )
        
        # Should still produce valid result
        assert 'metrics' in result


class TestCanaryDeploymentManager:
    """Tests for CanaryDeploymentManager."""
    
    def test_init(self):
        """Test manager initialization."""
        from agenticaiframework.evaluation.canary import CanaryDeploymentManager
        
        manager = CanaryDeploymentManager()
        assert manager.deployments == {}
    
    def test_create_deployment(self):
        """Test creating deployment."""
        from agenticaiframework.evaluation.canary import CanaryDeploymentManager
        
        manager = CanaryDeploymentManager()
        
        deployment = manager.create_deployment(
            name="test_deployment",
            baseline_version="v1.0",
            canary_version="v1.1"
        )
        
        assert deployment['name'] == "test_deployment"
        assert deployment['baseline_version'] == "v1.0"
        assert deployment['canary_version'] == "v1.1"
        assert deployment['status'] == 'active'
    
    def test_create_deployment_with_traffic_steps(self):
        """Test creating deployment with custom traffic steps."""
        from agenticaiframework.evaluation.canary import CanaryDeploymentManager
        
        manager = CanaryDeploymentManager()
        
        deployment = manager.create_deployment(
            name="custom_traffic",
            baseline_version="v1",
            canary_version="v2",
            traffic_steps=[0.1, 0.5, 1.0]
        )
        
        assert deployment['traffic_steps'] == [0.1, 0.5, 1.0]
        assert deployment['current_traffic'] == 0.1
    
    def test_route_request(self):
        """Test routing requests."""
        from agenticaiframework.evaluation.canary import CanaryDeploymentManager
        
        manager = CanaryDeploymentManager()
        
        manager.create_deployment(
            name="routing_test",
            baseline_version="v1",
            canary_version="v2",
            traffic_steps=[0.5]  # 50% canary
        )
        
        # Route many requests
        canary_count = 0
        total = 100
        for _ in range(total):
            result = manager.route_request("routing_test")
            if result == 'canary':
                canary_count += 1
        
        # Should be roughly 50%
        assert 30 <= canary_count <= 70
    
    def test_route_request_nonexistent(self):
        """Test routing to nonexistent deployment."""
        from agenticaiframework.evaluation.canary import CanaryDeploymentManager
        
        manager = CanaryDeploymentManager()
        
        result = manager.route_request("nonexistent")
        assert result == 'baseline'
    
    def test_record_result(self):
        """Test recording results."""
        from agenticaiframework.evaluation.canary import CanaryDeploymentManager
        
        manager = CanaryDeploymentManager()
        
        manager.create_deployment(
            name="record_test",
            baseline_version="v1",
            canary_version="v2"
        )
        
        manager.record_result(
            deployment_name="record_test",
            version="canary",
            success=True,
            latency_ms=100
        )
        
        deployment = manager.deployments["record_test"]
        assert deployment['metrics']['canary']['success'] == 1


class TestEvaluationIntegration:
    """Integration tests for evaluation module."""
    
    def test_drift_types_and_severity(self):
        """Test drift types with severity."""
        from agenticaiframework.evaluation.drift import DriftType, DriftSeverity, DriftAlert
        
        # Create alerts of different severities
        alerts = []
        for severity in [DriftSeverity.LOW, DriftSeverity.HIGH, DriftSeverity.CRITICAL]:
            alert = DriftAlert(
                alert_id=f"alert_{severity.value}",
                drift_type=DriftType.QUALITY_DEGRADATION,
                severity=severity,
                prompt_id="p1",
                metric_name="quality",
                baseline_value=0.9,
                current_value=0.7,
                deviation_percent=22.0,
                detected_at=time.time()
            )
            alerts.append(alert)
        
        assert len(alerts) == 3
        assert alerts[2].severity == DriftSeverity.CRITICAL
    
    def test_model_tier_comparison(self):
        """Test comparing different model tiers."""
        from agenticaiframework.evaluation.model_tier import ModelTierEvaluator
        
        evaluator = ModelTierEvaluator()
        
        # Evaluate same response on different tiers
        slm_result = evaluator.evaluate_model(
            model_name="small",
            tier="slm",
            response="Response",
            latency_ms=200,
            input_tokens=50,
            output_tokens=50,
            cost=0.0001
        )
        
        llm_result = evaluator.evaluate_model(
            model_name="large",
            tier="llm",
            response="Response",
            latency_ms=2000,  # Much higher latency
            input_tokens=50,
            output_tokens=50,
            cost=0.005
        )
        
        # SLM should have better latency score (capped at 1.0 if within expected)
        # With 200ms for SLM (expected 300) and 2000ms for LLM (expected 1500)
        assert slm_result['scores']['latency'] >= llm_result['scores']['latency']
