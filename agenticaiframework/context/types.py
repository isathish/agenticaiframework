"""
Context types and enums for the Agentic Context Engine.
"""

from enum import Enum


class ContextType(Enum):
    """Types of context for intelligent management."""
    SYSTEM = "system"           # System prompts, instructions
    USER = "user"               # User messages, queries
    ASSISTANT = "assistant"     # AI responses
    TOOL_CALL = "tool_call"     # Tool invocations
    TOOL_RESULT = "tool_result" # Tool outputs
    MEMORY = "memory"           # Retrieved memories
    KNOWLEDGE = "knowledge"     # RAG retrieved knowledge
    THOUGHT = "thought"         # Chain-of-thought reasoning
    OBSERVATION = "observation" # Environment observations
    PLAN = "plan"               # Planning context
    FEEDBACK = "feedback"       # User/system feedback
    ERROR = "error"             # Error context
    METADATA = "metadata"       # Context metadata


class ContextPriority(Enum):
    """Priority levels for context retention."""
    CRITICAL = 100    # Never evict (system prompts, core instructions)
    HIGH = 75         # Evict last (important context)
    MEDIUM = 50       # Default priority
    LOW = 25          # Evict first (verbose outputs)
    EPHEMERAL = 0     # Evict immediately after use


class ContextRetrievalStrategy(Enum):
    """Strategies for context retrieval."""
    RECENCY = "recency"           # Most recent first
    RELEVANCE = "relevance"       # Most relevant to query
    IMPORTANCE = "importance"     # Highest priority first
    HYBRID = "hybrid"             # Combined scoring
    TEMPORAL = "temporal"         # Time-based windowing
    SEMANTIC = "semantic"         # Semantic similarity
