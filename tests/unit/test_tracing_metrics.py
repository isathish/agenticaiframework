"""
Tests for tracing metrics module.
"""

import time
import pytest
from unittest.mock import Mock, patch

from agenticaiframework.tracing.metrics import LatencyMetrics


class TestLatencyMetrics:
    """Tests for LatencyMetrics class."""
    
    def test_init_default(self):
        """Test default initialization."""
        metrics = LatencyMetrics()
        assert metrics.window_size == 1000
        assert len(metrics.metrics) == 0
    
    def test_init_custom_window(self):
        """Test initialization with custom window size."""
        metrics = LatencyMetrics(window_size=100)
        assert metrics.window_size == 100
    
    def test_record_single(self):
        """Test recording a single latency measurement."""
        metrics = LatencyMetrics()
        metrics.record("api_call", 50.0)
        
        assert "api_call" in metrics.metrics
        assert len(metrics.metrics["api_call"]) == 1
        assert metrics.metrics["api_call"][0] == 50.0
        assert metrics.total_counts["api_call"] == 1
        assert metrics.total_sums["api_call"] == 50.0
    
    def test_record_multiple(self):
        """Test recording multiple latency measurements."""
        metrics = LatencyMetrics()
        
        for i in range(5):
            metrics.record("api_call", i * 10.0)
        
        assert len(metrics.metrics["api_call"]) == 5
        assert metrics.total_counts["api_call"] == 5
    
    def test_record_window_sliding(self):
        """Test that window slides when limit exceeded."""
        metrics = LatencyMetrics(window_size=5)
        
        for i in range(10):
            metrics.record("api_call", i * 10.0)
        
        # Only last 5 should be kept
        assert len(metrics.metrics["api_call"]) == 5
        assert metrics.metrics["api_call"][0] == 50.0  # First kept value
        # But total counts should be 10
        assert metrics.total_counts["api_call"] == 10
    
    def test_set_sla_threshold(self):
        """Test setting SLA threshold."""
        metrics = LatencyMetrics()
        metrics.set_sla_threshold("api_call", 100.0)
        
        assert metrics.sla_thresholds["api_call"] == 100.0
    
    def test_sla_violation_detection(self):
        """Test SLA violation detection."""
        metrics = LatencyMetrics()
        metrics.set_sla_threshold("api_call", 100.0)
        
        # Record under threshold
        metrics.record("api_call", 50.0)
        assert metrics.sla_violations["api_call"] == 0
        
        # Record over threshold
        metrics.record("api_call", 150.0)
        assert metrics.sla_violations["api_call"] == 1
    
    def test_get_percentile(self):
        """Test percentile calculation."""
        metrics = LatencyMetrics()
        
        # Record values 10, 20, 30, ..., 100
        for i in range(1, 11):
            metrics.record("api_call", i * 10.0)
        
        p50 = metrics.get_percentile("api_call", 50)
        assert p50 is not None
        assert 40 <= p50 <= 60
        
        p90 = metrics.get_percentile("api_call", 90)
        assert p90 is not None
        assert 80 <= p90 <= 100
    
    def test_get_percentile_empty(self):
        """Test percentile with no data."""
        metrics = LatencyMetrics()
        result = metrics.get_percentile("nonexistent", 50)
        assert result is None
    
    def test_get_stats(self):
        """Test getting comprehensive stats."""
        metrics = LatencyMetrics()
        
        metrics.record("api_call", 10.0)
        metrics.record("api_call", 20.0)
        metrics.record("api_call", 30.0)
        
        stats = metrics.get_stats("api_call")
        
        assert stats['count'] == 3
        assert stats['min'] == 10.0
    
    def test_get_stats_empty(self):
        """Test getting stats with no data."""
        metrics = LatencyMetrics()
        stats = metrics.get_stats("nonexistent")
        
        assert 'error' in stats
    
    def test_measure_context_manager(self):
        """Test measure context manager."""
        metrics = LatencyMetrics()
        
        with metrics.measure("test_operation"):
            time.sleep(0.01)  # Sleep for 10ms
        
        assert "test_operation" in metrics.metrics
        assert len(metrics.metrics["test_operation"]) == 1
        # Should be around 10ms or more
        assert metrics.metrics["test_operation"][0] >= 5
    
    def test_thread_safety(self):
        """Test thread safety of metrics."""
        import threading
        
        metrics = LatencyMetrics()
        
        def record_many():
            for i in range(100):
                metrics.record("concurrent", i)
        
        threads = [threading.Thread(target=record_many) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert metrics.total_counts["concurrent"] == 500
    
    def test_multiple_metrics(self):
        """Test recording multiple different metrics."""
        metrics = LatencyMetrics()
        
        metrics.record("api_call", 50.0)
        metrics.record("db_query", 100.0)
        metrics.record("cache_lookup", 5.0)
        
        assert len(metrics.metrics) == 3
        assert metrics.metrics["api_call"][0] == 50.0
        assert metrics.metrics["db_query"][0] == 100.0
        assert metrics.metrics["cache_lookup"][0] == 5.0


class TestLatencyMetricsEdgeCases:
    """Edge case tests for LatencyMetrics."""
    
    def test_record_zero_latency(self):
        """Test recording zero latency."""
        metrics = LatencyMetrics()
        metrics.record("instant", 0.0)
        
        assert metrics.metrics["instant"][0] == 0.0
    
    def test_record_very_high_latency(self):
        """Test recording very high latency."""
        metrics = LatencyMetrics()
        metrics.record("slow", 1000000.0)  # 1 million ms
        
        assert metrics.metrics["slow"][0] == 1000000.0
    
    def test_sla_threshold_exact_boundary(self):
        """Test SLA threshold at exact boundary."""
        metrics = LatencyMetrics()
        metrics.set_sla_threshold("api_call", 100.0)
        
        # Exactly at threshold - should not violate
        metrics.record("api_call", 100.0)
        assert metrics.sla_violations["api_call"] == 0
        
        # Just over threshold - should violate
        metrics.record("api_call", 100.01)
        assert metrics.sla_violations["api_call"] == 1
    
    def test_percentile_single_value(self):
        """Test percentile with single value."""
        metrics = LatencyMetrics()
        metrics.record("api_call", 50.0)
        
        assert metrics.get_percentile("api_call", 50) == 50.0
        assert metrics.get_percentile("api_call", 99) == 50.0
    
    def test_window_size_one(self):
        """Test with window size of 1."""
        metrics = LatencyMetrics(window_size=1)
        
        metrics.record("api_call", 10.0)
        metrics.record("api_call", 20.0)
        
        # Should only keep the last value
        assert len(metrics.metrics["api_call"]) == 1
        assert metrics.metrics["api_call"][0] == 20.0
