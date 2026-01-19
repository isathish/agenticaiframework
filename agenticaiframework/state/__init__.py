"""
State Management Module for AgenticAI Framework.

Provides comprehensive state management for:
- Agents (checkpointing, persistence, recovery)
- Workflows (state tracking, pause/resume)
- Orchestration (coordination state, multi-agent state)
- Knowledge Base (indexing progress, sync status)
- Tools (execution state, caching)
- Speech (session state, streaming state)

Example:
    >>> from agenticaiframework.state import StateManager, AgentStateStore
    >>> 
    >>> # Create state manager
    >>> state = StateManager(persistence="redis")
    >>> 
    >>> # Save agent state
    >>> state.save_agent_state(agent.id, agent.get_state())
    >>> 
    >>> # Checkpoint workflow
    >>> state.checkpoint_workflow(workflow_id, step=5, data=results)
    >>> 
    >>> # Recover on failure
    >>> state.recover_agent(agent.id)
"""

from .manager import (
    StateManager,
    StateBackend,
    MemoryBackend,
    FileBackend,
    RedisBackend,
    StateConfig,
)

from .agent_state import (
    AgentStateStore,
    AgentSnapshot,
    AgentCheckpoint,
    AgentRecoveryManager,
)

from .workflow_state import (
    WorkflowStateManager,
    WorkflowState,
    WorkflowCheckpoint,
    StepState,
    WorkflowStatus,
)

from .orchestration_state import (
    OrchestrationStateManager,
    TeamState,
    AgentCoordinationState,
    TaskQueueState,
)

from .knowledge_state import (
    KnowledgeStateManager,
    IndexingProgress,
    IndexingStatus,
    SyncStatus,
    SourceState,
    KnowledgeBaseState,
)

from .tool_state import (
    ToolStateManager,
    ToolExecution,
    ToolExecutionStatus,
    ToolCacheEntry,
    RetryState,
    ToolStats,
)

from .speech_state import (
    SpeechStateManager,
    AudioSessionStatus,
    StreamingMode,
    TranscriptionStatus,
    AudioChunk,
    TranscriptionResult,
    STTState,
    TTSState,
    VoiceConversationState,
)

__all__ = [
    # Core Manager
    "StateManager",
    "StateBackend",
    "MemoryBackend",
    "FileBackend",
    "RedisBackend",
    "StateConfig",
    # Agent State
    "AgentStateStore",
    "AgentSnapshot",
    "AgentCheckpoint",
    "AgentRecoveryManager",
    # Workflow State
    "WorkflowStateManager",
    "WorkflowState",
    "WorkflowCheckpoint",
    "StepState",
    "WorkflowStatus",
    # Orchestration State
    "OrchestrationStateManager",
    "TeamState",
    "AgentCoordinationState",
    "TaskQueueState",
    # Knowledge State
    "KnowledgeStateManager",
    "IndexingProgress",
    "IndexingStatus",
    "SyncStatus",
    "SourceState",
    "KnowledgeBaseState",
    # Tool State
    "ToolStateManager",
    "ToolExecution",
    "ToolExecutionStatus",
    "ToolCacheEntry",
    "RetryState",
    "ToolStats",
    # Speech State
    "SpeechStateManager",
    "AudioSessionStatus",
    "StreamingMode",
    "TranscriptionStatus",
    "AudioChunk",
    "TranscriptionResult",
    "STTState",
    "TTSState",
    "VoiceConversationState",
]
