"""
Model Registry.

Pre-configured model definitions for common providers (2026 pricing).
"""

from typing import Dict
from .types import ModelTier, ModelCapability, ModelConfig


# Pre-configured model definitions for common providers (2026 pricing)
MODEL_REGISTRY: Dict[str, ModelConfig] = {
    # OpenAI Models
    'gpt-4o': ModelConfig(
        name='gpt-4o', tier=ModelTier.LLM,
        capabilities=[ModelCapability.TEXT_GENERATION, ModelCapability.VISION,
                     ModelCapability.FUNCTION_CALLING, ModelCapability.STRUCTURED_OUTPUT],
        max_tokens=16384, context_window=128000, supports_streaming=True,
        supports_json_mode=True, cost_per_1k_input=0.0025, cost_per_1k_output=0.01,
        latency_ms_avg=800, provider='openai', version='2024-11'
    ),
    'gpt-4o-mini': ModelConfig(
        name='gpt-4o-mini', tier=ModelTier.SLM,
        capabilities=[ModelCapability.TEXT_GENERATION, ModelCapability.FUNCTION_CALLING],
        max_tokens=16384, context_window=128000, supports_streaming=True,
        supports_json_mode=True, cost_per_1k_input=0.00015, cost_per_1k_output=0.0006,
        latency_ms_avg=400, provider='openai', version='2024-07'
    ),
    'o1': ModelConfig(
        name='o1', tier=ModelTier.RLM,
        capabilities=[ModelCapability.REASONING, ModelCapability.CHAIN_OF_THOUGHT,
                     ModelCapability.CODE_GENERATION],
        max_tokens=100000, context_window=200000, supports_streaming=True,
        cost_per_1k_input=0.015, cost_per_1k_output=0.06,
        latency_ms_avg=5000, provider='openai', version='2024-12'
    ),
    'o1-mini': ModelConfig(
        name='o1-mini', tier=ModelTier.RLM,
        capabilities=[ModelCapability.REASONING, ModelCapability.CHAIN_OF_THOUGHT],
        max_tokens=65536, context_window=128000, supports_streaming=True,
        cost_per_1k_input=0.003, cost_per_1k_output=0.012,
        latency_ms_avg=2000, provider='openai', version='2024-09'
    ),
    'o3-mini': ModelConfig(
        name='o3-mini', tier=ModelTier.RLM,
        capabilities=[ModelCapability.REASONING, ModelCapability.CHAIN_OF_THOUGHT,
                     ModelCapability.CODE_GENERATION],
        max_tokens=100000, context_window=200000, supports_streaming=True,
        cost_per_1k_input=0.0011, cost_per_1k_output=0.0044,
        latency_ms_avg=1500, provider='openai', version='2025-01'
    ),
    
    # Anthropic Models
    'claude-4-opus': ModelConfig(
        name='claude-4-opus', tier=ModelTier.LLM,
        capabilities=[ModelCapability.TEXT_GENERATION, ModelCapability.VISION,
                     ModelCapability.REASONING, ModelCapability.CODE_GENERATION],
        max_tokens=8192, context_window=200000, supports_streaming=True,
        cost_per_1k_input=0.015, cost_per_1k_output=0.075,
        latency_ms_avg=2000, provider='anthropic', version='2025-02'
    ),
    'claude-4-sonnet': ModelConfig(
        name='claude-4-sonnet', tier=ModelTier.LLM,
        capabilities=[ModelCapability.TEXT_GENERATION, ModelCapability.VISION,
                     ModelCapability.FUNCTION_CALLING],
        max_tokens=8192, context_window=200000, supports_streaming=True,
        cost_per_1k_input=0.003, cost_per_1k_output=0.015,
        latency_ms_avg=1000, provider='anthropic', version='2025-02'
    ),
    'claude-3.5-haiku': ModelConfig(
        name='claude-3.5-haiku', tier=ModelTier.SLM,
        capabilities=[ModelCapability.TEXT_GENERATION, ModelCapability.FUNCTION_CALLING],
        max_tokens=8192, context_window=200000, supports_streaming=True,
        cost_per_1k_input=0.0008, cost_per_1k_output=0.004,
        latency_ms_avg=300, provider='anthropic', version='2024-10'
    ),
    
    # Google Models
    'gemini-2.0-flash': ModelConfig(
        name='gemini-2.0-flash', tier=ModelTier.LLM,
        capabilities=[ModelCapability.TEXT_GENERATION, ModelCapability.VISION,
                     ModelCapability.AUDIO, ModelCapability.FUNCTION_CALLING],
        max_tokens=8192, context_window=1000000, supports_streaming=True,
        supports_json_mode=True, cost_per_1k_input=0.0001, cost_per_1k_output=0.0004,
        latency_ms_avg=500, provider='google', version='2024-12'
    ),
    'gemini-2.0-flash-thinking': ModelConfig(
        name='gemini-2.0-flash-thinking', tier=ModelTier.RLM,
        capabilities=[ModelCapability.REASONING, ModelCapability.CHAIN_OF_THOUGHT],
        max_tokens=8192, context_window=1000000, supports_streaming=True,
        cost_per_1k_input=0.0, cost_per_1k_output=0.0,  # Free during preview
        latency_ms_avg=3000, provider='google', version='2024-12'
    ),
    'gemini-1.5-pro': ModelConfig(
        name='gemini-1.5-pro', tier=ModelTier.LLM,
        capabilities=[ModelCapability.TEXT_GENERATION, ModelCapability.VISION,
                     ModelCapability.LONG_CONTEXT],
        max_tokens=8192, context_window=2000000, supports_streaming=True,
        cost_per_1k_input=0.00125, cost_per_1k_output=0.005,
        latency_ms_avg=1500, provider='google', version='2024-05'
    ),
    
    # Small Language Models (SLM)
    'phi-4': ModelConfig(
        name='phi-4', tier=ModelTier.SLM,
        capabilities=[ModelCapability.TEXT_GENERATION, ModelCapability.REASONING],
        max_tokens=16384, context_window=16384, supports_streaming=True,
        cost_per_1k_input=0.0001, cost_per_1k_output=0.0004,
        latency_ms_avg=200, provider='microsoft', version='2024-12'
    ),
    'llama-3.3-70b': ModelConfig(
        name='llama-3.3-70b', tier=ModelTier.MLM,
        capabilities=[ModelCapability.TEXT_GENERATION, ModelCapability.CODE_GENERATION],
        max_tokens=8192, context_window=128000, supports_streaming=True,
        cost_per_1k_input=0.0008, cost_per_1k_output=0.0008,
        latency_ms_avg=600, provider='meta', version='2024-12'
    ),
    'mistral-small': ModelConfig(
        name='mistral-small', tier=ModelTier.SLM,
        capabilities=[ModelCapability.TEXT_GENERATION, ModelCapability.FUNCTION_CALLING],
        max_tokens=8192, context_window=32000, supports_streaming=True,
        cost_per_1k_input=0.0002, cost_per_1k_output=0.0006,
        latency_ms_avg=250, provider='mistral', version='2024-09'
    ),
    'qwen-2.5-72b': ModelConfig(
        name='qwen-2.5-72b', tier=ModelTier.MLM,
        capabilities=[ModelCapability.TEXT_GENERATION, ModelCapability.CODE_GENERATION,
                     ModelCapability.REASONING],
        max_tokens=8192, context_window=131072, supports_streaming=True,
        cost_per_1k_input=0.0004, cost_per_1k_output=0.0004,
        latency_ms_avg=500, provider='alibaba', version='2024-09'
    ),
    
    # DeepSeek Reasoning Models
    'deepseek-r1': ModelConfig(
        name='deepseek-r1', tier=ModelTier.RLM,
        capabilities=[ModelCapability.REASONING, ModelCapability.CHAIN_OF_THOUGHT,
                     ModelCapability.CODE_GENERATION],
        max_tokens=8192, context_window=64000, supports_streaming=True,
        cost_per_1k_input=0.00055, cost_per_1k_output=0.00219,
        latency_ms_avg=2500, provider='deepseek', version='2025-01'
    ),
    'deepseek-v3': ModelConfig(
        name='deepseek-v3', tier=ModelTier.LLM,
        capabilities=[ModelCapability.TEXT_GENERATION, ModelCapability.CODE_GENERATION],
        max_tokens=8192, context_window=64000, supports_streaming=True,
        cost_per_1k_input=0.00027, cost_per_1k_output=0.0011,
        latency_ms_avg=800, provider='deepseek', version='2024-12'
    ),
}


__all__ = ['MODEL_REGISTRY']
