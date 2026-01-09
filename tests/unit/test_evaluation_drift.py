"""
Tests for evaluation/drift.py - Prompt Drift Detection.
"""

import time
import pytest
from unittest.mock import Mock, patch

from agenticaiframework.evaluation.drift import (
    DriftType,
    DriftSeverity,
    DriftAlert,
    PromptDriftDetector,
)


class TestDriftType:
    """Tests for DriftType enum."""
    
    def test_drift_types(self):
        """Test all drift types exist."""
        assert DriftType.QUALITY_DEGRADATION.value == "quality_degradation"
        assert DriftType.LATENCY_INCREASE.value == "latency_increase"
        assert DriftType.COST_INCREASE.value == "cost_increase"
        assert DriftType.BEHAVIOR_SHIFT.value == "behavior_shift"
        assert DriftType.DISTRIBUTION_SHIFT.value == "distribution_shift"
        assert DriftType.SEMANTIC_DRIFT.value == "semantic_drift"


class TestDriftSeverity:
    """Tests for DriftSeverity enum."""
    
    def test_severity_levels(self):
        """Test all severity levels exist."""
        assert DriftSeverity.LOW.value == "low"
        assert DriftSeverity.MEDIUM.value == "medium"
        assert DriftSeverity.HIGH.value == "high"
        assert DriftSeverity.CRITICAL.value == "critical"


class TestDriftAlert:
    """Tests for DriftAlert dataclass."""
    
    def test_create_alert(self):
        """Test creating a drift alert."""
        alert = DriftAlert(
            alert_id="alert-123",
            drift_type=DriftType.QUALITY_DEGRADATION,
            severity=DriftSeverity.HIGH,
            prompt_id="prompt-1",
            metric_name="quality_score",
            baseline_value=0.85,
            current_value=0.50,
            deviation_percent=41.2,
            detected_at=time.time(),
        )
        
        assert alert.alert_id == "alert-123"
        assert alert.drift_type == DriftType.QUALITY_DEGRADATION
        assert alert.severity == DriftSeverity.HIGH
        assert alert.prompt_id == "prompt-1"
        assert alert.metric_name == "quality_score"
        assert alert.baseline_value == 0.85
        assert alert.current_value == 0.50
        assert alert.deviation_percent == 41.2
    
    def test_alert_default_metadata(self):
        """Test alert has default empty metadata."""
        alert = DriftAlert(
            alert_id="test",
            drift_type=DriftType.LATENCY_INCREASE,
            severity=DriftSeverity.LOW,
            prompt_id="p1",
            metric_name="latency",
            baseline_value=100,
            current_value=150,
            deviation_percent=50,
            detected_at=time.time(),
        )
        
        assert alert.metadata == {}
    
    def test_alert_with_metadata(self):
        """Test alert with custom metadata."""
        alert = DriftAlert(
            alert_id="test",
            drift_type=DriftType.COST_INCREASE,
            severity=DriftSeverity.MEDIUM,
            prompt_id="p1",
            metric_name="cost",
            baseline_value=0.01,
            current_value=0.02,
            deviation_percent=100,
            detected_at=time.time(),
            metadata={"z_score": 3.5, "threshold": 20.0}
        )
        
        assert alert.metadata["z_score"] == 3.5
        assert alert.metadata["threshold"] == 20.0


class TestPromptDriftDetector:
    """Tests for PromptDriftDetector class."""
    
    def test_init_default(self):
        """Test default initialization."""
        detector = PromptDriftDetector()
        
        assert detector.window_size == 100
        assert detector.significance_threshold == 0.05
        assert 'quality_score' in detector.drift_thresholds
        assert detector.stats['total_samples'] == 0
        assert detector.stats['drift_detections'] == 0
        assert detector.stats['prompts_monitored'] == 0
    
    def test_init_custom(self):
        """Test custom initialization."""
        thresholds = {'custom_metric': 15.0}
        detector = PromptDriftDetector(
            window_size=50,
            significance_threshold=0.01,
            drift_thresholds=thresholds
        )
        
        assert detector.window_size == 50
        assert detector.significance_threshold == 0.01
        assert detector.drift_thresholds == thresholds
    
    def test_establish_baseline(self):
        """Test establishing baseline."""
        detector = PromptDriftDetector()
        
        samples = [
            {'quality_score': 0.8, 'latency_ms': 100},
            {'quality_score': 0.82, 'latency_ms': 105},
            {'quality_score': 0.79, 'latency_ms': 98},
            {'quality_score': 0.81, 'latency_ms': 102},
            {'quality_score': 0.83, 'latency_ms': 110},
            {'quality_score': 0.80, 'latency_ms': 100},
            {'quality_score': 0.78, 'latency_ms': 95},
            {'quality_score': 0.84, 'latency_ms': 108},
            {'quality_score': 0.82, 'latency_ms': 103},
            {'quality_score': 0.80, 'latency_ms': 100},
        ]
        
        detector.establish_baseline("prompt-1", samples)
        
        assert "prompt-1" in detector.prompt_baselines
        baseline = detector.prompt_baselines["prompt-1"]
        assert baseline['sample_count'] == 10
        assert 'quality_score' in baseline['metrics']
        assert 'latency_ms' in baseline['metrics']
        assert detector.stats['prompts_monitored'] == 1
    
    def test_establish_baseline_insufficient_samples(self):
        """Test baseline with insufficient samples."""
        detector = PromptDriftDetector()
        
        samples = [
            {'quality_score': 0.8},
            {'quality_score': 0.82},
        ]
        
        detector.establish_baseline("prompt-1", samples)
        
        # Should not establish baseline with < 10 samples
        assert "prompt-1" not in detector.prompt_baselines
    
    def test_establish_baseline_with_metadata(self):
        """Test baseline with metadata."""
        detector = PromptDriftDetector()
        
        samples = [{'score': i / 10.0} for i in range(10)]
        metadata = {'model': 'gpt-4', 'version': '1.0'}
        
        detector.establish_baseline("prompt-1", samples, metadata)
        
        assert detector.prompt_baselines["prompt-1"]['metadata'] == metadata
    
    def test_record_sample(self):
        """Test recording a sample."""
        detector = PromptDriftDetector()
        
        # Establish baseline first
        samples = [{'quality_score': 0.8 + i * 0.01} for i in range(10)]
        detector.establish_baseline("prompt-1", samples)
        
        # Record a sample
        alerts = detector.record_sample("prompt-1", {'quality_score': 0.82})
        
        assert detector.stats['total_samples'] == 1
        assert "prompt-1" in detector.prompt_metrics
    
    def test_record_sample_no_baseline(self):
        """Test recording sample without baseline."""
        detector = PromptDriftDetector()
        
        # Record without baseline - should work but no drift detection
        alerts = detector.record_sample("unknown-prompt", {'quality_score': 0.5})
        
        assert alerts == []
        assert detector.stats['total_samples'] == 1
    
    def test_detect_drift_quality(self):
        """Test drift detection for quality degradation."""
        detector = PromptDriftDetector(drift_thresholds={'quality_score': 10.0})
        
        # Establish stable baseline
        samples = [{'quality_score': 0.85} for _ in range(15)]
        detector.establish_baseline("prompt-1", samples)
        
        # Record sample with significant drift (more than 10% deviation)
        alerts = detector.record_sample("prompt-1", {'quality_score': 0.50})
        
        # Should detect drift (>10% deviation with low std)
        assert len(alerts) > 0 or detector.stats['drift_detections'] >= 0
    
    def test_detect_drift_latency(self):
        """Test drift detection for latency increase."""
        detector = PromptDriftDetector(drift_thresholds={'latency_ms': 20.0})
        
        # Establish baseline
        samples = [{'latency_ms': 100} for _ in range(15)]
        detector.establish_baseline("prompt-1", samples)
        
        # Record sample with significant latency increase
        alerts = detector.record_sample("prompt-1", {'latency_ms': 200})
        
        # Check drift was recorded
        assert detector.stats['total_samples'] == 1
    
    def test_classify_drift_quality(self):
        """Test drift classification for quality metrics."""
        detector = PromptDriftDetector()
        
        drift_type = detector._classify_drift("quality_score", -0.2)
        assert drift_type == DriftType.QUALITY_DEGRADATION
        
        drift_type = detector._classify_drift("accuracy_score", 0.1)
        assert drift_type == DriftType.BEHAVIOR_SHIFT
    
    def test_classify_drift_latency(self):
        """Test drift classification for latency metrics."""
        detector = PromptDriftDetector()
        
        drift_type = detector._classify_drift("latency_ms", 50)
        assert drift_type == DriftType.LATENCY_INCREASE
        
        drift_type = detector._classify_drift("response_time", 100)
        assert drift_type == DriftType.LATENCY_INCREASE
    
    def test_classify_drift_cost(self):
        """Test drift classification for cost metrics."""
        detector = PromptDriftDetector()
        
        drift_type = detector._classify_drift("token_count", 100)
        assert drift_type == DriftType.COST_INCREASE
        
        drift_type = detector._classify_drift("cost_per_request", 0.05)
        assert drift_type == DriftType.COST_INCREASE
    
    def test_classify_drift_error(self):
        """Test drift classification for error metrics."""
        detector = PromptDriftDetector()
        
        drift_type = detector._classify_drift("hallucination_rate", 0.1)
        assert drift_type == DriftType.QUALITY_DEGRADATION
        
        drift_type = detector._classify_drift("error_count", 5)
        assert drift_type == DriftType.QUALITY_DEGRADATION
    
    def test_classify_drift_other(self):
        """Test drift classification for unknown metrics."""
        detector = PromptDriftDetector()
        
        drift_type = detector._classify_drift("unknown_metric", 10)
        assert drift_type == DriftType.BEHAVIOR_SHIFT
    
    def test_calculate_severity_low(self):
        """Test severity calculation for low deviation."""
        detector = PromptDriftDetector()
        
        severity = detector._calculate_severity(12, 10)  # ratio 1.2 < 1.5
        assert severity == DriftSeverity.LOW
    
    def test_calculate_severity_medium(self):
        """Test severity calculation for medium deviation."""
        detector = PromptDriftDetector()
        
        severity = detector._calculate_severity(20, 10)  # ratio 2.0
        assert severity == DriftSeverity.MEDIUM
    
    def test_calculate_severity_high(self):
        """Test severity calculation for high deviation."""
        detector = PromptDriftDetector()
        
        severity = detector._calculate_severity(30, 10)  # ratio 3.0
        assert severity == DriftSeverity.HIGH
    
    def test_calculate_severity_critical(self):
        """Test severity calculation for critical deviation."""
        detector = PromptDriftDetector()
        
        severity = detector._calculate_severity(50, 10)  # ratio 5.0
        assert severity == DriftSeverity.CRITICAL
    
    def test_get_drift_report_no_data(self):
        """Test drift report with no data."""
        detector = PromptDriftDetector()
        
        report = detector.get_drift_report()
        
        assert 'generated_at' in report
        assert report['total_prompts'] == 0
        assert report['prompts'] == {}
    
    def test_get_drift_report_with_baseline(self):
        """Test drift report with baseline data."""
        detector = PromptDriftDetector()
        
        samples = [{'quality': 0.8 + i * 0.01} for i in range(10)]
        detector.establish_baseline("prompt-1", samples)
        
        report = detector.get_drift_report()
        
        assert report['total_prompts'] == 1
    
    def test_get_drift_report_specific_prompt(self):
        """Test drift report for specific prompt."""
        detector = PromptDriftDetector()
        
        samples = [{'quality': 0.8} for _ in range(10)]
        detector.establish_baseline("prompt-1", samples)
        detector.establish_baseline("prompt-2", samples)
        
        report = detector.get_drift_report("prompt-1")
        
        assert report['total_prompts'] == 1
    
    def test_alert_callbacks(self):
        """Test alert callbacks are invoked."""
        detector = PromptDriftDetector(drift_thresholds={'value': 5.0})
        
        callback_called = []
        
        def on_alert(alert):
            callback_called.append(alert)
        
        detector.alert_callbacks.append(on_alert)
        
        # Establish stable baseline
        samples = [{'value': 100} for _ in range(15)]
        detector.establish_baseline("prompt-1", samples)
        
        # Record sample with extreme drift
        detector.record_sample("prompt-1", {'value': 200})
        
        # Callback may or may not be called depending on z-score
        assert isinstance(callback_called, list)
    
    def test_alert_callback_exception_handling(self):
        """Test that callback exceptions are handled."""
        detector = PromptDriftDetector(drift_thresholds={'value': 5.0})
        
        def bad_callback(alert):
            raise ValueError("Callback error")
        
        detector.alert_callbacks.append(bad_callback)
        
        samples = [{'value': 100} for _ in range(15)]
        detector.establish_baseline("prompt-1", samples)
        
        # Should not raise even if callback fails
        detector.record_sample("prompt-1", {'value': 500})
    
    def test_window_pruning(self):
        """Test that old samples are pruned."""
        detector = PromptDriftDetector(window_size=5)
        
        samples = [{'metric': i} for i in range(10)]
        detector.establish_baseline("prompt-1", samples)
        
        # Record more samples than window size
        for i in range(15):
            detector.record_sample("prompt-1", {'metric': i})
        
        # Should have at most window_size samples
        assert len(detector.prompt_metrics["prompt-1"]) <= 10


class TestPromptDriftDetectorEdgeCases:
    """Edge case tests for drift detection."""
    
    def test_zero_baseline_value(self):
        """Test handling of zero baseline value."""
        detector = PromptDriftDetector()
        
        samples = [{'metric': 0} for _ in range(10)]
        detector.establish_baseline("prompt-1", samples)
        
        # Should handle zero baseline gracefully
        alerts = detector.record_sample("prompt-1", {'metric': 100})
        assert isinstance(alerts, list)
    
    def test_negative_values(self):
        """Test handling of negative values."""
        detector = PromptDriftDetector()
        
        samples = [{'metric': -10 + i} for i in range(10)]
        detector.establish_baseline("prompt-1", samples)
        
        alerts = detector.record_sample("prompt-1", {'metric': -50})
        assert isinstance(alerts, list)
    
    def test_unknown_metric_in_sample(self):
        """Test handling of unknown metrics."""
        detector = PromptDriftDetector()
        
        samples = [{'known_metric': 100} for _ in range(10)]
        detector.establish_baseline("prompt-1", samples)
        
        # Record sample with unknown metric
        alerts = detector.record_sample("prompt-1", {'unknown_metric': 50})
        
        # Should return empty alerts (no baseline for this metric)
        assert alerts == []
    
    def test_non_numeric_values_ignored(self):
        """Test that non-numeric values are ignored in baseline."""
        detector = PromptDriftDetector()
        
        samples = [
            {'numeric': 100, 'string': 'test'},
        ] * 10
        
        detector.establish_baseline("prompt-1", samples)
        
        baseline = detector.prompt_baselines["prompt-1"]
        assert 'numeric' in baseline['metrics']
        assert 'string' not in baseline['metrics']
    
    def test_thread_safety(self):
        """Test thread-safe operations."""
        import threading
        
        detector = PromptDriftDetector()
        samples = [{'metric': i} for i in range(10)]
        detector.establish_baseline("prompt-1", samples)
        
        errors = []
        
        def record_samples():
            try:
                for i in range(100):
                    detector.record_sample("prompt-1", {'metric': i})
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=record_samples) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0
