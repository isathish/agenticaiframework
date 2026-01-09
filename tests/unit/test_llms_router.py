"""
Tests for llms/router.py - Model Router.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch

from agenticaiframework.llms.router import ModelRouter
from agenticaiframework.llms.types import ModelTier, ModelCapability, ModelConfig


class MockLLMManager:
    """Mock LLM Manager for testing."""
    
    def __init__(self, models=None, metadata=None):
        self._models = models or []
        self.model_metadata = metadata or {}
        self.active_model = "default-model"
    
    def list_models(self):
        return self._models


class TestModelRouter:
    """Tests for ModelRouter class."""
    
    def test_init(self):
        """Test router initialization."""
        manager = MockLLMManager()
        router = ModelRouter(manager)
        
        assert router.llm_manager == manager
        assert router.routing_history == []
    
    def test_route_no_models(self):
        """Test routing with no models available."""
        manager = MockLLMManager(models=[])
        router = ModelRouter(manager)
        
        result = router.route("Test prompt")
        
        # Should return active model as fallback
        assert result == "default-model"
    
    def test_route_simple_prompt(self):
        """Test routing with simple short prompt."""
        manager = MockLLMManager(
            models=["gpt-4o-mini"],
            metadata={
                "gpt-4o-mini": {
                    "tier": "slm",
                    "capabilities": [],
                    "max_tokens": 4096,
                    "context_window": 8192,
                    "cost_per_1k_input": 0.0001,
                    "cost_per_1k_output": 0.0002,
                    "latency_ms_avg": 500,
                    "provider": "openai"
                }
            }
        )
        router = ModelRouter(manager)
        
        result = router.route("Short prompt")
        
        assert result == "gpt-4o-mini"
    
    def test_route_records_history(self):
        """Test that routing records history."""
        manager = MockLLMManager(
            models=["model1"],
            metadata={
                "model1": {
                    "tier": "llm",
                    "capabilities": [],
                    "cost_per_1k_input": 0.001,
                    "cost_per_1k_output": 0.002,
                    "latency_ms_avg": 1000,
                }
            }
        )
        router = ModelRouter(manager)
        
        router.route("Test prompt")
        
        assert len(router.routing_history) == 1
        history = router.routing_history[0]
        assert 'timestamp' in history
        assert history['prompt_length'] == len("Test prompt")
        assert history['selected_model'] == "model1"
    
    def test_route_with_required_capabilities(self):
        """Test routing with required capabilities."""
        manager = MockLLMManager(
            models=["model1", "model2"],
            metadata={
                "model1": {
                    "tier": "llm",
                    "capabilities": ["text_generation"],
                    "cost_per_1k_input": 0.001,
                    "cost_per_1k_output": 0.002,
                    "latency_ms_avg": 1000,
                },
                "model2": {
                    "tier": "llm",
                    "capabilities": ["text_generation", "code_generation"],
                    "cost_per_1k_input": 0.002,
                    "cost_per_1k_output": 0.004,
                    "latency_ms_avg": 1000,
                }
            }
        )
        router = ModelRouter(manager)
        
        result = router.route(
            "Write code",
            required_capabilities=[ModelCapability.CODE_GENERATION]
        )
        
        # Only model2 has code capability
        assert result == "model2"
    
    def test_route_with_preferred_tier(self):
        """Test routing with preferred tier."""
        manager = MockLLMManager(
            models=["slm-model", "llm-model"],
            metadata={
                "slm-model": {
                    "tier": "slm",
                    "capabilities": [],
                    "cost_per_1k_input": 0.0001,
                    "cost_per_1k_output": 0.0002,
                    "latency_ms_avg": 500,
                },
                "llm-model": {
                    "tier": "llm",
                    "capabilities": [],
                    "cost_per_1k_input": 0.001,
                    "cost_per_1k_output": 0.002,
                    "latency_ms_avg": 1000,
                }
            }
        )
        router = ModelRouter(manager)
        
        result = router.route(
            "Test prompt",
            preferred_tier=ModelTier.SLM
        )
        
        assert result == "slm-model"
    
    def test_route_with_max_cost(self):
        """Test routing with maximum cost constraint."""
        manager = MockLLMManager(
            models=["cheap", "expensive"],
            metadata={
                "cheap": {
                    "tier": "slm",
                    "capabilities": [],
                    "cost_per_1k_input": 0.0001,
                    "cost_per_1k_output": 0.0002,
                    "latency_ms_avg": 500,
                },
                "expensive": {
                    "tier": "llm",
                    "capabilities": [],
                    "cost_per_1k_input": 0.01,
                    "cost_per_1k_output": 0.02,
                    "latency_ms_avg": 1000,
                }
            }
        )
        router = ModelRouter(manager)
        
        # Only cheap model should be under max_cost
        result = router.route("Test", max_cost=0.001)
        
        assert result == "cheap"
    
    def test_route_with_max_latency(self):
        """Test routing with maximum latency constraint."""
        manager = MockLLMManager(
            models=["fast", "slow"],
            metadata={
                "fast": {
                    "tier": "slm",
                    "capabilities": [],
                    "cost_per_1k_input": 0.001,
                    "cost_per_1k_output": 0.002,
                    "latency_ms_avg": 200,
                },
                "slow": {
                    "tier": "llm",
                    "capabilities": [],
                    "cost_per_1k_input": 0.001,
                    "cost_per_1k_output": 0.002,
                    "latency_ms_avg": 2000,
                }
            }
        )
        router = ModelRouter(manager)
        
        result = router.route("Test", max_latency_ms=500)
        
        assert result == "fast"
    
    def test_route_prefer_reasoning(self):
        """Test routing with reasoning preference."""
        manager = MockLLMManager(
            models=["standard", "reasoning"],
            metadata={
                "standard": {
                    "tier": "llm",
                    "capabilities": [],
                    "cost_per_1k_input": 0.001,
                    "cost_per_1k_output": 0.002,
                    "latency_ms_avg": 1000,
                },
                "reasoning": {
                    "tier": "rlm",
                    "capabilities": [],
                    "cost_per_1k_input": 0.01,
                    "cost_per_1k_output": 0.02,
                    "latency_ms_avg": 2000,
                }
            }
        )
        router = ModelRouter(manager)
        
        result = router.route("Complex problem", prefer_reasoning=True)
        
        assert result == "reasoning"
    
    def test_route_slm_preferred_for_short_prompts(self):
        """Test SLM is preferred for short prompts."""
        manager = MockLLMManager(
            models=["slm", "llm"],
            metadata={
                "slm": {
                    "tier": "slm",
                    "capabilities": [],
                    "cost_per_1k_input": 0.001,
                    "cost_per_1k_output": 0.002,
                    "latency_ms_avg": 500,
                },
                "llm": {
                    "tier": "llm",
                    "capabilities": [],
                    "cost_per_1k_input": 0.001,
                    "cost_per_1k_output": 0.002,
                    "latency_ms_avg": 500,
                }
            }
        )
        router = ModelRouter(manager)
        
        # Short prompt (< 500 chars) should prefer SLM
        result = router.route("Hi")
        
        assert result == "slm"
    
    def test_get_model_config_from_metadata(self):
        """Test getting model config from metadata."""
        manager = MockLLMManager(
            models=["test-model"],
            metadata={
                "test-model": {
                    "tier": "llm",
                    "capabilities": ["text_generation"],
                    "max_tokens": 8000,
                    "context_window": 16000,
                    "cost_per_1k_input": 0.005,
                    "cost_per_1k_output": 0.01,
                    "latency_ms_avg": 800,
                    "provider": "openai"
                }
            }
        )
        router = ModelRouter(manager)
        
        config = router._get_model_config("test-model")
        
        assert config is not None
        assert config.name == "test-model"
        assert config.tier == ModelTier.LLM
        assert config.max_tokens == 8000
        assert config.context_window == 16000
    
    def test_get_model_config_not_found(self):
        """Test getting config for unknown model."""
        manager = MockLLMManager(models=[], metadata={})
        router = ModelRouter(manager)
        
        config = router._get_model_config("unknown-model")
        
        assert config is None
    
    def test_route_no_candidates_after_filtering(self):
        """Test routing when all models filtered out."""
        manager = MockLLMManager(
            models=["model1"],
            metadata={
                "model1": {
                    "tier": "llm",
                    "capabilities": [],
                    "cost_per_1k_input": 1.0,  # Very expensive
                    "cost_per_1k_output": 2.0,
                    "latency_ms_avg": 1000,
                }
            }
        )
        router = ModelRouter(manager)
        
        # Max cost so low that no model qualifies
        result = router.route("Test", max_cost=0.001)
        
        # Should return fallback (active model)
        assert result == "default-model"
    
    def test_route_history_includes_capabilities(self):
        """Test routing history includes capability values."""
        manager = MockLLMManager(
            models=["model1"],
            metadata={
                "model1": {
                    "tier": "llm",
                    "capabilities": ["text_generation"],
                    "cost_per_1k_input": 0.001,
                    "cost_per_1k_output": 0.002,
                    "latency_ms_avg": 1000,
                }
            }
        )
        router = ModelRouter(manager)
        
        router.route(
            "Test",
            required_capabilities=[ModelCapability.TEXT_GENERATION]
        )
        
        history = router.routing_history[0]
        assert history['required_capabilities'] == ['text_generation']
    
    def test_route_history_includes_tier(self):
        """Test routing history includes tier value."""
        manager = MockLLMManager(
            models=["model1"],
            metadata={
                "model1": {
                    "tier": "slm",
                    "capabilities": [],
                    "cost_per_1k_input": 0.001,
                    "cost_per_1k_output": 0.002,
                    "latency_ms_avg": 1000,
                }
            }
        )
        router = ModelRouter(manager)
        
        router.route("Test", preferred_tier=ModelTier.SLM)
        
        history = router.routing_history[0]
        assert history['preferred_tier'] == 'slm'


class TestModelRouterScoring:
    """Tests for model scoring logic."""
    
    def test_cost_affects_score(self):
        """Test that cost affects model score."""
        manager = MockLLMManager(
            models=["cheap", "expensive"],
            metadata={
                "cheap": {
                    "tier": "llm",
                    "capabilities": [],
                    "cost_per_1k_input": 0.001,
                    "cost_per_1k_output": 0.001,
                    "latency_ms_avg": 1000,
                },
                "expensive": {
                    "tier": "llm",
                    "capabilities": [],
                    "cost_per_1k_input": 0.1,
                    "cost_per_1k_output": 0.1,
                    "latency_ms_avg": 1000,
                }
            }
        )
        router = ModelRouter(manager)
        
        # With same latency, cheaper model should be selected
        result = router.route("Test" * 200)  # Long enough to not prefer SLM
        
        assert result == "cheap"
    
    def test_latency_affects_score(self):
        """Test that latency affects model score."""
        manager = MockLLMManager(
            models=["fast", "slow"],
            metadata={
                "fast": {
                    "tier": "llm",
                    "capabilities": [],
                    "cost_per_1k_input": 0.001,
                    "cost_per_1k_output": 0.001,
                    "latency_ms_avg": 100,
                },
                "slow": {
                    "tier": "llm",
                    "capabilities": [],
                    "cost_per_1k_input": 0.001,
                    "cost_per_1k_output": 0.001,
                    "latency_ms_avg": 5000,
                }
            }
        )
        router = ModelRouter(manager)
        
        # With same cost, faster model should score higher
        result = router.route("Test" * 200)
        
        assert result == "fast"


class TestModelRouterEdgeCases:
    """Edge case tests for model router."""
    
    def test_empty_prompt(self):
        """Test routing with empty prompt."""
        manager = MockLLMManager(
            models=["model1"],
            metadata={
                "model1": {
                    "tier": "slm",
                    "capabilities": [],
                    "cost_per_1k_input": 0.001,
                    "cost_per_1k_output": 0.001,
                    "latency_ms_avg": 500,
                }
            }
        )
        router = ModelRouter(manager)
        
        result = router.route("")
        
        assert result == "model1"
    
    def test_very_long_prompt(self):
        """Test routing with very long prompt."""
        manager = MockLLMManager(
            models=["model1"],
            metadata={
                "model1": {
                    "tier": "llm",
                    "capabilities": [],
                    "cost_per_1k_input": 0.001,
                    "cost_per_1k_output": 0.001,
                    "latency_ms_avg": 1000,
                }
            }
        )
        router = ModelRouter(manager)
        
        long_prompt = "a" * 10000
        result = router.route(long_prompt)
        
        assert result == "model1"
    
    def test_multiple_routes_accumulate_history(self):
        """Test multiple routes accumulate in history."""
        manager = MockLLMManager(
            models=["model1"],
            metadata={
                "model1": {
                    "tier": "llm",
                    "capabilities": [],
                    "cost_per_1k_input": 0.001,
                    "cost_per_1k_output": 0.001,
                    "latency_ms_avg": 1000,
                }
            }
        )
        router = ModelRouter(manager)
        
        router.route("Prompt 1")
        router.route("Prompt 2")
        router.route("Prompt 3")
        
        assert len(router.routing_history) == 3
    
    def test_default_capabilities_empty(self):
        """Test default empty capabilities."""
        manager = MockLLMManager(
            models=["model1"],
            metadata={
                "model1": {
                    "tier": "llm",
                    "capabilities": [],
                    "cost_per_1k_input": 0.001,
                    "cost_per_1k_output": 0.001,
                    "latency_ms_avg": 1000,
                }
            }
        )
        router = ModelRouter(manager)
        
        # Should work with default None capabilities
        result = router.route("Test")
        
        assert result == "model1"
