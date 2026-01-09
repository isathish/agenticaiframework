"""
Agentic Context Engine (ACE) - Advanced Context Management.

This module provides intelligent context management for AI agents including:
- Context window tracking and management
- Token counting and optimization
- Context compression and pruning
- Semantic context understanding
- Context retrieval strategies
- Memory-aware context management
"""

from .types import (
    ContextType,
    ContextPriority,
    ContextRetrievalStrategy,
)
from .items import ContextItem
from .index import SemanticContextIndex
from .window import ContextWindow
from .compression import ContextCompressionStrategy
from .manager import ContextManager

__all__ = [
    # Types and enums
    "ContextType",
    "ContextPriority", 
    "ContextRetrievalStrategy",
    # Core classes
    "ContextItem",
    "SemanticContextIndex",
    "ContextWindow",
    "ContextCompressionStrategy",
    "ContextManager",
]
