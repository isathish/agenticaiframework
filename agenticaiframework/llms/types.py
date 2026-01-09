"""
LLM Types.

Common types, enums, and dataclasses for LLM management.
"""

from enum import Enum
from typing import Dict, Any, List
from dataclasses import dataclass, field


class ModelTier(Enum):
    """Model tier classification for intelligent routing."""
    SLM = "slm"           # Small Language Models (< 10B params) - Fast, cheap, simple tasks
    MLM = "mlm"           # Medium Language Models (10B-100B params) - Balanced
    LLM = "llm"           # Large Language Models (100B+ params) - Complex tasks
    RLM = "rlm"           # Reasoning Language Models - Chain-of-thought, complex reasoning
    MULTI_MODAL = "mm"    # Multi-modal models - Text + Vision/Audio


class ModelCapability(Enum):
    """Model capabilities for routing decisions."""
    TEXT_GENERATION = "text_generation"
    CODE_GENERATION = "code_generation"
    REASONING = "reasoning"
    CHAIN_OF_THOUGHT = "chain_of_thought"
    FUNCTION_CALLING = "function_calling"
    VISION = "vision"
    AUDIO = "audio"
    EMBEDDINGS = "embeddings"
    STRUCTURED_OUTPUT = "structured_output"
    LONG_CONTEXT = "long_context"


@dataclass
class ModelConfig:
    """Configuration for a registered model."""
    name: str
    tier: ModelTier = ModelTier.LLM
    capabilities: List[ModelCapability] = field(default_factory=list)
    max_tokens: int = 4096
    context_window: int = 8192
    supports_streaming: bool = False
    supports_json_mode: bool = False
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0
    latency_ms_avg: float = 1000.0
    provider: str = "unknown"
    version: str = "1.0"
    metadata: Dict[str, Any] = field(default_factory=dict)


__all__ = [
    'ModelTier',
    'ModelCapability',
    'ModelConfig',
]
