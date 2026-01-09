"""
LLM Package.

LLM management with advanced features:
- Model registration and management
- Retry mechanisms with exponential backoff
- Circuit breaker pattern
- Rate limiting
- Token usage tracking
- Response caching
- Model fallback chain
- SLM (Small Language Models) support
- RLM (Reasoning Language Models) support
- Multi-modal capabilities
- Streaming support
"""

from .types import (
    ModelTier,
    ModelCapability,
    ModelConfig,
)
from .circuit_breaker import CircuitBreaker
from .manager import LLMManager
from .registry import MODEL_REGISTRY
from .router import ModelRouter

__all__ = [
    # Types
    'ModelTier',
    'ModelCapability',
    'ModelConfig',
    # Classes
    'CircuitBreaker',
    'LLMManager',
    'ModelRouter',
    # Registry
    'MODEL_REGISTRY',
]
