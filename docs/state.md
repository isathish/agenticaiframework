# State Management

<div class="hero-section">
<h2 class="hero-title">🔄 Comprehensive State Management</h2>
<p class="hero-subtitle">Production-ready state management with persistence, recovery, and real-time tracking for agents, workflows, and orchestration</p>
</div>

<div class="stats-grid">
<div class="stat-item">
<div class="stat-number">6</div>
<div class="stat-label">State Managers</div>
</div>
<div class="stat-item">
<div class="stat-number">3</div>
<div class="stat-label">Backend Options</div>
</div>
<div class="stat-item">
<div class="stat-number">Auto</div>
<div class="stat-label">Recovery</div>
</div>
<div class="stat-item">
<div class="stat-number">Real-time</div>
<div class="stat-label">Checkpointing</div>
</div>
</div>

---

## Overview

AgenticAI Framework provides **6 specialized state managers** for complete control over agent lifecycles, workflow execution, and system state with multiple persistence backends.

```python
from agenticaiframework.state import (
    StateManager,           # Core state management
    AgentStateStore,        # Agent state & snapshots
    WorkflowStateManager,   # Workflow execution state
    OrchestrationStateManager,  # Multi-agent coordination
    KnowledgeStateManager,  # Knowledge base state
    ToolStateManager,       # Tool execution state
    SpeechStateManager,     # Speech session state
)
```

---

## State Manager Architecture

<div class="feature-grid">
<div class="feature-card">
<h3>🎛️ StateManager</h3>
<h4>Core State Engine</h4>
<p>Central state management with pluggable backends</p>
</div>
<div class="feature-card">
<h3>🤖 AgentStateStore</h3>
<h4>Agent Lifecycle</h4>
<p>Snapshots, checkpoints, and recovery for agents</p>
</div>
<div class="feature-card">
<h3>🔄 WorkflowStateManager</h3>
<h4>Workflow Tracking</h4>
<p>Step-by-step execution state and checkpoints</p>
</div>
<div class="feature-card">
<h3>🎭 OrchestrationStateManager</h3>
<h4>Team Coordination</h4>
<p>Multi-agent state and task queue management</p>
</div>
<div class="feature-card">
<h3>📚 KnowledgeStateManager</h3>
<h4>Knowledge Base</h4>
<p>Indexing progress and sync status tracking</p>
</div>
<div class="feature-card">
<h3>🛠️ ToolStateManager</h3>
<h4>Tool Execution</h4>
<p>Execution state, caching, and retry management</p>
</div>
</div>

---

## Core StateManager

The central state management engine with pluggable persistence backends.

### Initialization

```python
from agenticaiframework.state import (
    StateManager,
    StateConfig,
    MemoryBackend,
    FileBackend,
    RedisBackend,
)

# In-memory state (development)
state_manager = StateManager(
    config=StateConfig(
        backend="memory",
        auto_save=True,
        save_interval=30,
    )
)

# File-based state (single instance)
state_manager = StateManager(
    config=StateConfig(
        backend="file",
        file_path="./state/app_state.json",
        auto_save=True,
    )
)

# Redis state (production/distributed)
state_manager = StateManager(
    config=StateConfig(
        backend="redis",
        redis_url="redis://localhost:6379",
        key_prefix="agenticai:",
        ttl=3600,
    )
)
```

### Basic Operations

```python
# Save state
await state_manager.save("agent:researcher", {
    "status": "running",
    "current_task": "analyze_data",
    "progress": 0.45,
})

# Get state
agent_state = await state_manager.get("agent:researcher")
print(f"Status: {agent_state['status']}")

# Update partial state
await state_manager.update("agent:researcher", {
    "progress": 0.75,
})

# Delete state
await state_manager.delete("agent:researcher")

# List all keys
keys = await state_manager.list_keys("agent:*")
```

### State Subscriptions

```python
# Subscribe to state changes
async def on_state_change(key: str, old_value: dict, new_value: dict):
    print(f"State changed for {key}")
    print(f"  Old: {old_value}")
    print(f"  New: {new_value}")

state_manager.subscribe("agent:*", on_state_change)

# Unsubscribe
state_manager.unsubscribe("agent:*", on_state_change)
```

---

## AgentStateStore

Manages agent snapshots, checkpoints, and recovery.

### Creating Agent Snapshots

```python
from agenticaiframework.state import (
    AgentStateStore,
    AgentSnapshot,
    AgentCheckpoint,
)

# Initialize agent state store
agent_store = AgentStateStore(
    persistence="redis",
    redis_url="redis://localhost:6379",
)

# Create a snapshot of agent state
snapshot = AgentSnapshot(
    agent_id="researcher_01",
    timestamp=datetime.now(),
    memory_state=agent.memory.export(),
    tool_state=agent.tools.get_state(),
    conversation_history=agent.conversation_history,
    metadata={
        "version": "1.0",
        "task_count": 42,
    }
)

# Save snapshot
await agent_store.save_snapshot(snapshot)

# List available snapshots
snapshots = await agent_store.list_snapshots("researcher_01")
for snap in snapshots:
    print(f"Snapshot: {snap.timestamp} - {snap.metadata}")
```

### Checkpointing

```python
# Create checkpoint during long-running tasks
checkpoint = AgentCheckpoint(
    agent_id="researcher_01",
    checkpoint_id="task_step_5",
    step=5,
    state={
        "current_task": "data_analysis",
        "intermediate_results": results,
        "tokens_used": 15000,
    },
    recoverable=True,
)

await agent_store.save_checkpoint(checkpoint)

# Resume from checkpoint
checkpoint = await agent_store.get_checkpoint(
    agent_id="researcher_01",
    checkpoint_id="task_step_5"
)

if checkpoint:
    agent.restore_from_checkpoint(checkpoint.state)
```

### Agent Recovery

```python
from agenticaiframework.state import AgentRecoveryManager

recovery_manager = AgentRecoveryManager(
    agent_store=agent_store,
    auto_recover=True,
    max_recovery_attempts=3,
)

# Register agent for recovery
recovery_manager.register(agent)

# Manual recovery
try:
    result = await agent.run(task)
except Exception as e:
    # Attempt recovery
    recovered = await recovery_manager.recover(
        agent_id=agent.id,
        from_checkpoint="latest",
    )
    
    if recovered:
        print("Agent recovered successfully")
        result = await agent.resume()
```

---

## WorkflowStateManager

Tracks workflow execution, steps, and enables pause/resume.

### Workflow State Tracking

```python
from agenticaiframework.state import (
    WorkflowStateManager,
    WorkflowState,
    WorkflowStatus,
    StepState,
)

# Initialize workflow state manager
workflow_state = WorkflowStateManager(
    persistence="redis",
    checkpoint_interval=5,  # Checkpoint every 5 steps
)

# Create workflow state
state = WorkflowState(
    workflow_id="research_pipeline",
    status=WorkflowStatus.PENDING,
    total_steps=10,
    current_step=0,
    context={},
)

await workflow_state.create(state)

# Update step progress
await workflow_state.update_step(
    workflow_id="research_pipeline",
    step=StepState(
        step_number=1,
        name="data_collection",
        status="completed",
        result={"documents": 150},
        duration_ms=5400,
    )
)

# Get current state
current = await workflow_state.get("research_pipeline")
print(f"Progress: {current.current_step}/{current.total_steps}")
```

### Workflow Checkpointing

```python
from agenticaiframework.state import WorkflowCheckpoint

# Create checkpoint
checkpoint = WorkflowCheckpoint(
    workflow_id="research_pipeline",
    checkpoint_id="step_5_complete",
    step=5,
    state=current_state,
    context=workflow_context,
    timestamp=datetime.now(),
)

await workflow_state.checkpoint(checkpoint)

# List checkpoints
checkpoints = await workflow_state.list_checkpoints("research_pipeline")

# Resume from checkpoint
await workflow_state.resume_from(
    workflow_id="research_pipeline",
    checkpoint_id="step_5_complete"
)
```

### Pause and Resume

```python
# Pause workflow
await workflow_state.pause("research_pipeline")
status = await workflow_state.get_status("research_pipeline")
print(f"Status: {status}")  # WorkflowStatus.PAUSED

# Resume workflow
await workflow_state.resume("research_pipeline")

# Cancel workflow
await workflow_state.cancel(
    workflow_id="research_pipeline",
    reason="User requested cancellation"
)
```

---

## OrchestrationStateManager

Manages multi-agent coordination and team state.

### Team State Management

```python
from agenticaiframework.state import (
    OrchestrationStateManager,
    TeamState,
    AgentCoordinationState,
    TaskQueueState,
)

# Initialize orchestration state
orch_state = OrchestrationStateManager(
    persistence="redis",
    sync_interval=1.0,
)

# Create team state
team_state = TeamState(
    team_id="research_team",
    agents={
        "researcher": AgentCoordinationState(
            agent_id="researcher",
            status="idle",
            capabilities=["research", "analysis"],
            current_task=None,
        ),
        "writer": AgentCoordinationState(
            agent_id="writer",
            status="idle",
            capabilities=["writing", "editing"],
            current_task=None,
        ),
    },
    task_queue=TaskQueueState(
        pending=[],
        in_progress=[],
        completed=[],
    ),
)

await orch_state.create_team(team_state)
```

### Agent Coordination

```python
# Update agent status
await orch_state.update_agent_status(
    team_id="research_team",
    agent_id="researcher",
    status="working",
    current_task="task_001",
)

# Get team overview
team = await orch_state.get_team("research_team")
for agent_id, agent_state in team.agents.items():
    print(f"{agent_id}: {agent_state.status}")

# Get available agents
available = await orch_state.get_available_agents(
    team_id="research_team",
    capability="research"
)
```

### Task Queue Management

```python
# Add task to queue
await orch_state.enqueue_task(
    team_id="research_team",
    task={
        "id": "task_002",
        "type": "analysis",
        "priority": "high",
        "data": {"topic": "AI trends"},
    }
)

# Assign task to agent
await orch_state.assign_task(
    team_id="research_team",
    task_id="task_002",
    agent_id="researcher",
)

# Complete task
await orch_state.complete_task(
    team_id="research_team",
    task_id="task_002",
    result={"analysis": "..."},
)

# Get queue status
queue = await orch_state.get_queue_status("research_team")
print(f"Pending: {len(queue.pending)}")
print(f"In Progress: {len(queue.in_progress)}")
print(f"Completed: {len(queue.completed)}")
```

---

## KnowledgeStateManager

Tracks knowledge base indexing and synchronization.

### Indexing Progress

```python
from agenticaiframework.state import (
    KnowledgeStateManager,
    IndexingProgress,
    IndexingStatus,
    SyncStatus,
)

# Initialize knowledge state manager
kb_state = KnowledgeStateManager(
    persistence="redis",
)

# Track indexing progress
progress = IndexingProgress(
    knowledge_base_id="company_docs",
    status=IndexingStatus.IN_PROGRESS,
    total_documents=1000,
    processed_documents=450,
    failed_documents=5,
    started_at=datetime.now(),
)

await kb_state.update_indexing_progress(progress)

# Check progress
current = await kb_state.get_indexing_progress("company_docs")
print(f"Progress: {current.processed_documents}/{current.total_documents}")
print(f"Failed: {current.failed_documents}")
```

### Source Synchronization

```python
from agenticaiframework.state import SourceState

# Track source sync status
source_state = SourceState(
    source_id="confluence_docs",
    knowledge_base_id="company_docs",
    sync_status=SyncStatus.SYNCING,
    last_sync=datetime.now() - timedelta(hours=1),
    documents_synced=250,
    documents_pending=50,
)

await kb_state.update_source_state(source_state)

# Get all sources for knowledge base
sources = await kb_state.get_sources("company_docs")
for source in sources:
    print(f"{source.source_id}: {source.sync_status}")
```

### Knowledge Base State

```python
from agenticaiframework.state import KnowledgeBaseState

# Get overall knowledge base state
kb_overview = await kb_state.get_knowledge_base_state("company_docs")

print(f"Total Documents: {kb_overview.total_documents}")
print(f"Total Embeddings: {kb_overview.total_embeddings}")
print(f"Last Updated: {kb_overview.last_updated}")
print(f"Storage Size: {kb_overview.storage_size_mb}MB")
```

---

## ToolStateManager

Manages tool execution state and caching.

### Tool Execution Tracking

```python
from agenticaiframework.state import (
    ToolStateManager,
    ToolExecution,
    ToolExecutionStatus,
)

# Initialize tool state manager
tool_state = ToolStateManager(
    persistence="redis",
    cache_results=True,
    cache_ttl=3600,
)

# Track tool execution
execution = ToolExecution(
    execution_id="exec_001",
    tool_name="search_web",
    status=ToolExecutionStatus.RUNNING,
    started_at=datetime.now(),
    parameters={"query": "AI news"},
)

await tool_state.start_execution(execution)

# Update execution
await tool_state.complete_execution(
    execution_id="exec_001",
    result={"results": [...]},
    duration_ms=1500,
)

# Get execution history
history = await tool_state.get_execution_history(
    tool_name="search_web",
    limit=100,
)
```

### Result Caching

```python
from agenticaiframework.state import ToolCacheEntry

# Cache tool result
cache_entry = ToolCacheEntry(
    tool_name="search_web",
    parameters_hash="abc123",
    result={"results": [...]},
    created_at=datetime.now(),
    ttl=3600,
)

await tool_state.cache_result(cache_entry)

# Check cache before execution
cached = await tool_state.get_cached_result(
    tool_name="search_web",
    parameters={"query": "AI news"},
)

if cached:
    print("Using cached result")
    result = cached.result
else:
    result = await tool.execute({"query": "AI news"})
```

### Retry Management

```python
from agenticaiframework.state import RetryState

# Track retry state
retry_state = RetryState(
    execution_id="exec_002",
    attempts=2,
    max_attempts=5,
    last_error="Connection timeout",
    next_retry_at=datetime.now() + timedelta(seconds=30),
    backoff_factor=2.0,
)

await tool_state.update_retry_state(retry_state)

# Get tools needing retry
pending_retries = await tool_state.get_pending_retries()
for retry in pending_retries:
    if retry.next_retry_at <= datetime.now():
        await retry_tool(retry)
```

### Tool Statistics

```python
from agenticaiframework.state import ToolStats

# Get tool statistics
stats = await tool_state.get_tool_stats("search_web")

print(f"Total Executions: {stats.total_executions}")
print(f"Success Rate: {stats.success_rate:.2%}")
print(f"Avg Duration: {stats.avg_duration_ms}ms")
print(f"Cache Hit Rate: {stats.cache_hit_rate:.2%}")
print(f"Error Rate: {stats.error_rate:.2%}")
```

---

## SpeechStateManager

Manages speech session state for STT/TTS operations.

### Session Management

```python
from agenticaiframework.state import (
    SpeechStateManager,
    AudioSessionStatus,
    StreamingMode,
)

# Initialize speech state manager
speech_state = SpeechStateManager(
    persistence="redis",
)

# Create audio session
session_id = await speech_state.create_session(
    session_type="voice_conversation",
    streaming_mode=StreamingMode.BIDIRECTIONAL,
    config={
        "stt_provider": "openai",
        "tts_provider": "elevenlabs",
        "language": "en-US",
    }
)

# Update session status
await speech_state.update_session_status(
    session_id=session_id,
    status=AudioSessionStatus.ACTIVE,
)
```

### STT State Tracking

```python
from agenticaiframework.state import STTState, TranscriptionStatus

# Track STT state
stt_state = STTState(
    session_id=session_id,
    status=TranscriptionStatus.TRANSCRIBING,
    audio_received_bytes=45000,
    transcription_progress=0.6,
    interim_transcript="Hello, I would like to...",
)

await speech_state.update_stt_state(stt_state)

# Get current STT state
current_stt = await speech_state.get_stt_state(session_id)
print(f"Progress: {current_stt.transcription_progress:.0%}")
print(f"Interim: {current_stt.interim_transcript}")
```

### TTS State Tracking

```python
from agenticaiframework.state import TTSState

# Track TTS state
tts_state = TTSState(
    session_id=session_id,
    text_queue=["Hello! How can I help you today?"],
    audio_generated_bytes=12000,
    audio_played_bytes=8000,
    is_speaking=True,
)

await speech_state.update_tts_state(tts_state)

# Check if speaking
current_tts = await speech_state.get_tts_state(session_id)
if current_tts.is_speaking:
    print("Agent is currently speaking...")
```

### Voice Conversation State

```python
from agenticaiframework.state import VoiceConversationState

# Track full conversation state
conversation_state = VoiceConversationState(
    session_id=session_id,
    turn_count=5,
    current_speaker="user",
    stt_state=stt_state,
    tts_state=tts_state,
    transcript=[
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi! How can I help?"},
        # ...
    ]
)

await speech_state.update_conversation_state(conversation_state)

# End session
await speech_state.end_session(
    session_id=session_id,
    reason="user_ended",
)
```

---

## Persistence Backends

### Memory Backend (Development)

```python
from agenticaiframework.state import MemoryBackend

backend = MemoryBackend()

# Fast, no persistence
# Data lost on restart
# Best for: Development, testing
```

### File Backend (Single Instance)

```python
from agenticaiframework.state import FileBackend

backend = FileBackend(
    base_path="./state",
    format="json",  # or "msgpack" for better performance
    compression=True,
)

# Persists to local files
# Best for: Single instance, small deployments
```

### Redis Backend (Production)

```python
from agenticaiframework.state import RedisBackend

backend = RedisBackend(
    url="redis://localhost:6379",
    db=0,
    key_prefix="agenticai:",
    connection_pool_size=10,
)

# Distributed, high performance
# Supports pub/sub for state sync
# Best for: Production, multi-instance
```

---

## Best Practices

<div class="feature-grid">
<div class="feature-card">
<h3>🔄 Checkpoint Regularly</h3>
<p>Create checkpoints at logical boundaries in long-running tasks to enable recovery without losing progress.</p>
</div>
<div class="feature-card">
<h3>🗄️ Choose Right Backend</h3>
<p>Use memory for dev, file for single instance, Redis for distributed production deployments.</p>
</div>
<div class="feature-card">
<h3>🧹 Clean Old State</h3>
<p>Implement TTLs and cleanup routines to prevent unbounded state growth.</p>
</div>
<div class="feature-card">
<h3>📊 Monitor State Size</h3>
<p>Track state storage size and set alerts for unusual growth patterns.</p>
</div>
</div>

---

## Next Steps

<div class="feature-grid">
<div class="feature-card">
<h3><a href="memory.md">💾 Memory</a></h3>
<p>Learn about memory management for agents</p>
</div>
<div class="feature-card">
<h3><a href="orchestration.md">🎭 Orchestration</a></h3>
<p>Multi-agent team coordination</p>
</div>
<div class="feature-card">
<h3><a href="monitoring.md">📊 Monitoring</a></h3>
<p>Set up observability for your agents</p>
</div>
<div class="feature-card">
<h3><a href="tracing.md">🔍 Tracing</a></h3>
<p>Debug agent execution flows</p>
</div>
</div>
