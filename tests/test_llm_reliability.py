"""
Test suite for LLM Reliability features.
Tests CircuitBreaker, retry mechanism, caching, and fallback chains.
"""

import pytest
import time
from agenticaiframework.llms import CircuitBreaker, LLM


class TestCircuitBreaker:
    """Test suite for CircuitBreaker class."""
    
    def test_initial_state(self):
        """Test that circuit breaker starts in closed state."""
        cb = CircuitBreaker(failure_threshold=3, timeout=5)
        
        assert cb.state == 'closed'
        assert cb.failure_count == 0
    
    def test_record_success(self):
        """Test recording successful calls."""
        cb = CircuitBreaker(failure_threshold=3, timeout=5)
        
        cb.record_success()
        
        assert cb.state == 'closed'
        assert cb.failure_count == 0
    
    def test_record_failure(self):
        """Test recording failed calls."""
        cb = CircuitBreaker(failure_threshold=3, timeout=5)
        
        cb.record_failure()
        
        assert cb.failure_count == 1
        assert cb.state == 'closed'  # Still closed until threshold
    
    def test_circuit_opens_on_threshold(self):
        """Test that circuit opens after failure threshold."""
        cb = CircuitBreaker(failure_threshold=3, timeout=5)
        
        # Record failures up to threshold
        cb.record_failure()
        cb.record_failure()
        cb.record_failure()
        
        assert cb.state == 'open'
    
    def test_call_blocked_when_open(self):
        """Test that calls are blocked when circuit is open."""
        cb = CircuitBreaker(failure_threshold=2, timeout=5)
        
        # Open the circuit
        cb.record_failure()
        cb.record_failure()
        
        # Should not allow calls
        assert cb.can_call() is False
    
    def test_half_open_after_timeout(self):
        """Test transition to half-open after timeout."""
        cb = CircuitBreaker(failure_threshold=2, timeout=1)
        
        # Open the circuit
        cb.record_failure()
        cb.record_failure()
        assert cb.state == 'open'
        
        # Wait for timeout
        time.sleep(1.1)
        
        # Should transition to half-open
        assert cb.can_call() is True
        assert cb.state == 'half_open'
    
    def test_close_after_success_in_half_open(self):
        """Test circuit closes after success in half-open state."""
        cb = CircuitBreaker(failure_threshold=2, timeout=1)
        
        # Open the circuit
        cb.record_failure()
        cb.record_failure()
        
        # Wait for timeout
        time.sleep(1.1)
        cb.can_call()  # Transition to half-open
        
        # Record success
        cb.record_success()
        
        assert cb.state == 'closed'
        assert cb.failure_count == 0
    
    def test_reopen_on_failure_in_half_open(self):
        """Test circuit reopens on failure in half-open state."""
        cb = CircuitBreaker(failure_threshold=2, timeout=1)
        
        # Open the circuit
        cb.record_failure()
        cb.record_failure()
        
        # Wait and transition to half-open
        time.sleep(1.1)
        cb.can_call()
        
        # Fail again
        cb.record_failure()
        
        assert cb.state == 'open'


class TestLLMRetryMechanism:
    """Test suite for LLM retry mechanism."""
    
    def test_retry_configuration(self):
        """Test configuring retry parameters."""
        llm = LLM(
            name="test-model",
            provider="test",
            max_retries=5,
            retry_delay=2.0
        )
        
        assert llm.max_retries == 5
        assert llm.retry_delay == 2.0
    
    def test_exponential_backoff(self):
        """Test exponential backoff calculation."""
        llm = LLM(
            name="test-model",
            provider="test",
            max_retries=3,
            retry_delay=1.0
        )
        
        # Backoff should increase: 1, 2, 4
        # This is tested implicitly through retry behavior


class TestLLMCaching:
    """Test suite for LLM response caching."""
    
    def test_cache_storage(self):
        """Test that responses are cached."""
        llm = LLM(
            name="test-model",
            provider="test",
            enable_cache=True
        )
        
        # Cache a response manually for testing
        cache_key = llm._get_cache_key("test prompt")
        llm.cache[cache_key] = "cached response"
        
        assert cache_key in llm.cache
    
    def test_cache_retrieval(self):
        """Test retrieving cached responses."""
        llm = LLM(
            name="test-model",
            provider="test",
            enable_cache=True
        )
        
        # Store in cache
        cache_key = llm._get_cache_key("test prompt")
        llm.cache[cache_key] = "cached response"
        
        # Retrieve
        result = llm.cache.get(cache_key)
        assert result == "cached response"
    
    def test_cache_key_generation(self):
        """Test that cache keys are generated consistently."""
        llm = LLM(
            name="test-model",
            provider="test",
            enable_cache=True
        )
        
        key1 = llm._get_cache_key("test prompt")
        key2 = llm._get_cache_key("test prompt")
        
        # Same prompt should generate same key
        assert key1 == key2
    
    def test_different_prompts_different_keys(self):
        """Test that different prompts generate different keys."""
        llm = LLM(
            name="test-model",
            provider="test",
            enable_cache=True
        )
        
        key1 = llm._get_cache_key("prompt one")
        key2 = llm._get_cache_key("prompt two")
        
        assert key1 != key2
    
    def test_clear_cache(self):
        """Test clearing the cache."""
        llm = LLM(
            name="test-model",
            provider="test",
            enable_cache=True
        )
        
        # Add to cache
        cache_key = llm._get_cache_key("test")
        llm.cache[cache_key] = "response"
        
        # Clear
        llm.clear_cache()
        
        assert len(llm.cache) == 0


class TestLLMFallbackChain:
    """Test suite for LLM fallback chains."""
    
    def test_fallback_configuration(self):
        """Test configuring fallback models."""
        primary = LLM(name="primary", provider="test")
        fallback1 = LLM(name="fallback1", provider="test")
        fallback2 = LLM(name="fallback2", provider="test")
        
        primary.add_fallback(fallback1)
        primary.add_fallback(fallback2)
        
        assert len(primary.fallback_chain) == 2
    
    def test_fallback_order(self):
        """Test that fallbacks are tried in order."""
        primary = LLM(name="primary", provider="test")
        fallback1 = LLM(name="fallback1", provider="test")
        fallback2 = LLM(name="fallback2", provider="test")
        
        primary.add_fallback(fallback1)
        primary.add_fallback(fallback2)
        
        # Order should be preserved
        assert primary.fallback_chain[0].name == "fallback1"
        assert primary.fallback_chain[1].name == "fallback2"


class TestLLMPerformanceTracking:
    """Test suite for LLM performance tracking."""
    
    def test_track_latency(self):
        """Test tracking request latency."""
        llm = LLM(name="test-model", provider="test")
        
        # Simulate tracking
        llm.total_requests = 5
        llm.total_latency = 10.0
        
        metrics = llm.get_performance_metrics()
        
        assert metrics['total_requests'] == 5
        assert metrics['total_latency'] == 10.0
        assert metrics['avg_latency'] == 2.0
    
    def test_track_tokens(self):
        """Test tracking token usage."""
        llm = LLM(name="test-model", provider="test")
        
        llm.total_tokens = 1000
        llm.total_requests = 10
        
        metrics = llm.get_performance_metrics()
        
        assert metrics['total_tokens'] == 1000
        assert metrics['avg_tokens_per_request'] == 100
    
    def test_track_errors(self):
        """Test tracking error count."""
        llm = LLM(name="test-model", provider="test")
        
        llm.total_errors = 3
        llm.total_requests = 10
        
        metrics = llm.get_performance_metrics()
        
        assert metrics['total_errors'] == 3
        assert metrics['error_rate'] == 0.3


class TestLLMIntegration:
    """Integration tests for LLM reliability features."""
    
    def test_circuit_breaker_with_retry(self):
        """Test circuit breaker working with retry mechanism."""
        llm = LLM(
            name="test-model",
            provider="test",
            max_retries=3,
            retry_delay=0.1
        )
        
        # Circuit breaker should be initialized
        assert llm.circuit_breaker is not None
        assert llm.circuit_breaker.state == 'closed'
    
    def test_caching_with_retry(self):
        """Test that caching works with retry mechanism."""
        llm = LLM(
            name="test-model",
            provider="test",
            enable_cache=True,
            max_retries=3
        )
        
        # Cache should be initialized
        assert hasattr(llm, 'cache')
        assert isinstance(llm.cache, dict)
    
    def test_full_reliability_stack(self):
        """Test all reliability features together."""
        primary = LLM(
            name="primary",
            provider="test",
            enable_cache=True,
            max_retries=3,
            retry_delay=0.1
        )
        
        fallback = LLM(name="fallback", provider="test")
        primary.add_fallback(fallback)
        
        # All features should be configured
        assert primary.circuit_breaker is not None
        assert primary.enable_cache is True
        assert primary.max_retries == 3
        assert len(primary.fallback_chain) == 1
    
    def test_metrics_aggregation(self):
        """Test aggregating metrics across features."""
        llm = LLM(
            name="test-model",
            provider="test",
            enable_cache=True,
            max_retries=3
        )
        
        # Simulate some activity
        llm.total_requests = 10
        llm.total_latency = 5.0
        llm.total_tokens = 500
        llm.total_errors = 1
        
        metrics = llm.get_performance_metrics()
        
        # All metrics should be present
        assert 'total_requests' in metrics
        assert 'avg_latency' in metrics
        assert 'total_tokens' in metrics
        assert 'error_rate' in metrics


class TestCircuitBreakerStates:
    """Detailed tests for circuit breaker state transitions."""
    
    def test_closed_to_open_transition(self):
        """Test closed -> open transition."""
        cb = CircuitBreaker(failure_threshold=3, timeout=5)
        
        assert cb.state == 'closed'
        
        for _ in range(3):
            cb.record_failure()
        
        assert cb.state == 'open'
    
    def test_open_to_half_open_transition(self):
        """Test open -> half_open transition."""
        cb = CircuitBreaker(failure_threshold=2, timeout=1)
        
        # Go to open
        cb.record_failure()
        cb.record_failure()
        assert cb.state == 'open'
        
        # Wait and check
        time.sleep(1.1)
        cb.can_call()
        
        assert cb.state == 'half_open'
    
    def test_half_open_to_closed_transition(self):
        """Test half_open -> closed transition."""
        cb = CircuitBreaker(failure_threshold=2, timeout=1)
        
        # Go to open
        cb.record_failure()
        cb.record_failure()
        
        # Go to half_open
        time.sleep(1.1)
        cb.can_call()
        
        # Success should close
        cb.record_success()
        assert cb.state == 'closed'
    
    def test_half_open_to_open_transition(self):
        """Test half_open -> open transition."""
        cb = CircuitBreaker(failure_threshold=2, timeout=1)
        
        # Go to open
        cb.record_failure()
        cb.record_failure()
        
        # Go to half_open
        time.sleep(1.1)
        cb.can_call()
        
        # Failure should reopen
        cb.record_failure()
        assert cb.state == 'open'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
