"""
Memory Package for the Agentic AI Framework.

Provides multi-tier memory management with TTL, eviction, and consolidation.
Includes specialized memory managers for:
- Agents (conversation, working, episodic, semantic memory)
- Workflows (step results, context passing, checkpoints)
- Orchestration (shared team memory, inter-agent messaging)
- Knowledge (embedding cache, query cache, retrieval history)
- Tools (result caching, execution history, patterns)
- Speech (transcription history, voice profiles, audio cache)
"""

from .types import MemoryEntry, MemoryStats
from .manager import MemoryManager

# Agent Memory
from .agent_memory import (
    MemoryType,
    ConversationTurn,
    Episode,
    Fact,
    WorkingMemoryItem,
    AgentMemoryManager,
)

# Workflow Memory
from .workflow_memory import (
    StepResultType,
    StepResult,
    WorkflowContext,
    WorkflowMemoryCheckpoint,
    WorkflowExecutionRecord,
    WorkflowMemoryManager,
)

# Orchestration Memory
from .orchestration_memory import (
    MessagePriority,
    AgentMessage,
    TaskHandoff,
    SharedContext,
    AgentContribution,
    OrchestrationMemoryManager,
)

# Knowledge Memory
from .knowledge_memory import (
    EmbeddingCache,
    QueryResult,
    RetrievalRecord,
    DocumentMemory,
    KnowledgeMemoryManager,
)

# Tool Memory
from .tool_memory import (
    ToolResultCache,
    ToolExecutionMemory,
    ToolPattern,
    ToolPerformanceStats,
    ToolMemoryManager,
)

# Speech Memory
from .speech_memory import (
    TranscriptionMemory,
    SynthesisMemory,
    VoiceProfile,
    VoiceConversationMemory,
    AudioCache,
    SpeechMemoryManager,
)

__all__ = [
    # Core Types
    'MemoryEntry',
    'MemoryStats',
    'MemoryManager',
    
    # Agent Memory
    'MemoryType',
    'ConversationTurn',
    'Episode',
    'Fact',
    'WorkingMemoryItem',
    'AgentMemoryManager',
    
    # Workflow Memory
    'StepResultType',
    'StepResult',
    'WorkflowContext',
    'WorkflowMemoryCheckpoint',
    'WorkflowExecutionRecord',
    'WorkflowMemoryManager',
    
    # Orchestration Memory
    'MessagePriority',
    'AgentMessage',
    'TaskHandoff',
    'SharedContext',
    'AgentContribution',
    'OrchestrationMemoryManager',
    
    # Knowledge Memory
    'EmbeddingCache',
    'QueryResult',
    'RetrievalRecord',
    'DocumentMemory',
    'KnowledgeMemoryManager',
    
    # Tool Memory
    'ToolResultCache',
    'ToolExecutionMemory',
    'ToolPattern',
    'ToolPerformanceStats',
    'ToolMemoryManager',
    
    # Speech Memory
    'TranscriptionMemory',
    'SynthesisMemory',
    'VoiceProfile',
    'VoiceConversationMemory',
    'AudioCache',
    'SpeechMemoryManager',
    
    # Global instance
    'memory_manager',
]

# Global instance for convenience
memory_manager = MemoryManager()
