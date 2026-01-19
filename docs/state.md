---
title: State Management
description: Complete guide to AgenticAI Framework's 7 specialized state managers
---

# 🔄 State Management

AgenticAI Framework provides **7 dedicated state managers** for complete control over agent lifecycles, workflow execution, conversations, and system state.

---

## 🎯 Quick Navigation

<div class="grid cards" markdown>

-   :robot:{ .lg } **AgentStateManager**

    ---

    Agent lifecycle and runtime state

    [:octicons-arrow-right-24: Jump to section](#agentstatemanager)

-   :arrows_counterclockwise:{ .lg } **WorkflowStateManager**

    ---

    Workflow execution tracking

    [:octicons-arrow-right-24: Jump to section](#workflowstatemanager)

-   :speech_balloon:{ .lg } **ConversationStateManager**

    ---

    Conversation context and history

    [:octicons-arrow-right-24: Jump to section](#conversationstatemanager)

-   :clipboard:{ .lg } **TaskStateManager**

    ---

    Task tracking and progress

    [:octicons-arrow-right-24: Jump to section](#taskstatemanager)

-   :window:{ .lg } **ContextStateManager**

    ---

    Context window management

    [:octicons-arrow-right-24: Jump to section](#contextstatemanager)

-   :hammer_and_wrench:{ .lg } **ToolStateManager**

    ---

    Tool execution states

    [:octicons-arrow-right-24: Jump to section](#toolstatemanager)

-   :floppy_disk:{ .lg } **MemoryStateManager**

    ---

    Memory system states

    [:octicons-arrow-right-24: Jump to section](#memorystatemanager)

</div>

---

## 📊 State Manager Comparison

| Manager | Scope | Key States | Use Case |
|---------|-------|------------|----------|
| **AgentStateManager** | Per-agent | idle, running, paused, error | Agent lifecycle |
| **WorkflowStateManager** | Per-workflow | pending, active, completed, failed | Workflow orchestration |
| **ConversationStateManager** | Per-conversation | active, paused, ended | Chat sessions |
| **TaskStateManager** | Per-task | queued, running, completed, failed | Task execution |
| **ContextStateManager** | Per-context | open, full, compressed | Context windows |
| **ToolStateManager** | Per-tool | ready, executing, cooldown | Tool management |
| **MemoryStateManager** | Per-memory | syncing, synced, stale | Memory operations |

---

## AgentStateManager

The **AgentStateManager** controls agent lifecycle, runtime state, and operational modes.

### Basic Usage

```python
from agenticaiframework import AgentStateManager, AgentState

# Initialize state manager
state_manager = AgentStateManager(agent_id="researcher_01")

# Get current state
current_state = state_manager.get_state()
print(f"Agent state: {current_state}")  # AgentState.IDLE

# Transition to new state
state_manager.transition_to(AgentState.RUNNING)

# Check if transition is valid
can_pause = state_manager.can_transition_to(AgentState.PAUSED)
```

### Agent Lifecycle States

```python
from agenticaiframework import AgentState

# Available states
class AgentState:
    INITIALIZING = "initializing"  # Agent is starting up
    IDLE = "idle"                  # Ready to receive tasks
    RUNNING = "running"            # Executing a task
    PAUSED = "paused"              # Temporarily suspended
    WAITING = "waiting"            # Waiting for external input
    ERROR = "error"                # Error state
    TERMINATED = "terminated"      # Shut down
```

### State Transitions

```python
# Define valid transitions
state_manager = AgentStateManager(
    agent_id="agent_01",
    transitions={
        AgentState.IDLE: [AgentState.RUNNING, AgentState.TERMINATED],
        AgentState.RUNNING: [AgentState.IDLE, AgentState.PAUSED, AgentState.ERROR],
        AgentState.PAUSED: [AgentState.RUNNING, AgentState.IDLE],
        AgentState.ERROR: [AgentState.IDLE, AgentState.TERMINATED],
    }
)

# Transition with callback
state_manager.on_transition(
    from_state=AgentState.RUNNING,
    to_state=AgentState.IDLE,
    callback=lambda: print("Task completed!")
)
```

### State Persistence

```python
# Enable state persistence
state_manager = AgentStateManager(
    agent_id="agent_01",
    persist=True,
    persist_path="./state_data"
)

# Save current state
state_manager.save()

# Restore state on startup
state_manager.restore()

# Get state history
history = state_manager.get_history(last_n=10)
for entry in history:
    print(f"{entry.timestamp}: {entry.from_state} -> {entry.to_state}")
```

---

## WorkflowStateManager

The **WorkflowStateManager** tracks workflow execution, step progress, and branching decisions.

### Basic Usage

```python
from agenticaiframework import WorkflowStateManager, WorkflowState

# Initialize for workflow
workflow_state = WorkflowStateManager(workflow_id="content_pipeline")

# Start workflow
workflow_state.start()
print(f"State: {workflow_state.get_state()}")  # WorkflowState.ACTIVE

# Update step progress
workflow_state.update_step(
    step_name="research",
    status="completed",
    progress=100
)

# Get workflow status
status = workflow_state.get_status()
print(f"Current step: {status.current_step}")
print(f"Progress: {status.overall_progress}%")
```

### Workflow States

```python
class WorkflowState:
    PENDING = "pending"        # Not started
    ACTIVE = "active"          # Currently running
    PAUSED = "paused"          # Temporarily paused
    WAITING = "waiting"        # Waiting for input/approval
    COMPLETED = "completed"    # Successfully finished
    FAILED = "failed"          # Failed with error
    CANCELLED = "cancelled"    # Manually cancelled
```

### Step Tracking

```python
# Register workflow steps
workflow_state.register_steps([
    {"name": "research", "order": 1, "required": True},
    {"name": "analysis", "order": 2, "required": True},
    {"name": "writing", "order": 3, "required": True},
    {"name": "review", "order": 4, "required": False},
])

# Start a step
workflow_state.start_step("research")

# Complete a step
workflow_state.complete_step(
    step_name="research",
    output=research_data,
    metrics={"duration_ms": 5000}
)

# Skip optional step
workflow_state.skip_step("review", reason="Time constraints")

# Get step status
step_status = workflow_state.get_step_status("research")
```

### Parallel Step Execution

```python
# Track parallel steps
workflow_state.start_parallel_steps(["analysis_a", "analysis_b", "analysis_c"])

# Complete individual parallel step
workflow_state.complete_step("analysis_a", output=result_a)

# Check if all parallel steps completed
if workflow_state.are_parallel_steps_complete():
    workflow_state.proceed_to_next()
```

---

## ConversationStateManager

The **ConversationStateManager** manages conversation context, turn tracking, and session state.

### Basic Usage

```python
from agenticaiframework import ConversationStateManager, ConversationState

# Initialize conversation
conv_state = ConversationStateManager(conversation_id="chat_001")

# Start conversation
conv_state.start()

# Add message
conv_state.add_message(
    role="user",
    content="Hello, I need help with Python",
    metadata={"intent": "help_request"}
)

# Add response
conv_state.add_message(
    role="assistant",
    content="I'd be happy to help with Python! What do you need?",
    metadata={"tokens": 15}
)

# Get conversation context
context = conv_state.get_context(last_n_turns=5)
```

### Conversation States

```python
class ConversationState:
    ACTIVE = "active"          # Ongoing conversation
    PAUSED = "paused"          # User stepped away
    WAITING = "waiting"        # Waiting for user response
    ENDED = "ended"            # Conversation concluded
    TRANSFERRED = "transferred"  # Handed off to another agent
```

### Turn Management

```python
# Track turn count
turn = conv_state.get_current_turn()
print(f"Current turn: {turn}")

# Set turn timeout
conv_state.set_turn_timeout(seconds=300)

# Handle timeout
if conv_state.is_turn_timed_out():
    conv_state.send_reminder("Are you still there?")

# End conversation
conv_state.end(
    reason="user_goodbye",
    summary="Helped user with Python list comprehensions"
)
```

### Context Summarization

```python
# Get conversation summary
summary = conv_state.get_summary()
print(f"Topic: {summary.main_topic}")
print(f"Turns: {summary.turn_count}")
print(f"Key points: {summary.key_points}")

# Compress old context
conv_state.compress_context(
    keep_last_n=5,
    summarize_older=True
)
```

---

## TaskStateManager

The **TaskStateManager** provides granular control over task execution, queuing, and progress tracking.

### Basic Usage

```python
from agenticaiframework import TaskStateManager, TaskState

# Initialize task state
task_state = TaskStateManager()

# Create and queue task
task_id = task_state.create_task(
    name="data_analysis",
    priority=1,  # Higher = more priority
    payload={"data_source": "sales.csv"}
)

# Start task
task_state.start_task(task_id)

# Update progress
task_state.update_progress(task_id, progress=50, status_message="Processing...")

# Complete task
task_state.complete_task(task_id, result=analysis_results)
```

### Task States

```python
class TaskState:
    QUEUED = "queued"          # Waiting in queue
    SCHEDULED = "scheduled"    # Scheduled for future
    RUNNING = "running"        # Currently executing
    PAUSED = "paused"          # Temporarily paused
    COMPLETED = "completed"    # Successfully finished
    FAILED = "failed"          # Failed with error
    CANCELLED = "cancelled"    # Manually cancelled
    RETRYING = "retrying"      # Being retried after failure
```

### Task Queue Management

```python
# Get queue status
queue = task_state.get_queue_status()
print(f"Queued: {queue.queued_count}")
print(f"Running: {queue.running_count}")
print(f"Completed: {queue.completed_count}")

# Get next task by priority
next_task = task_state.get_next_task()

# Reorder queue
task_state.reprioritize(task_id, new_priority=10)

# Cancel task
task_state.cancel_task(task_id, reason="No longer needed")
```

### Task Dependencies

```python
# Create task with dependencies
task_state.create_task(
    name="generate_report",
    dependencies=["data_analysis", "data_cleaning"],
    payload={"format": "pdf"}
)

# Check if dependencies are met
if task_state.are_dependencies_met("generate_report"):
    task_state.start_task("generate_report")

# Get dependent tasks
dependents = task_state.get_dependents("data_analysis")
```

### Retry Logic

```python
# Configure retry policy
task_state.set_retry_policy(
    task_id=task_id,
    max_retries=3,
    retry_delay_seconds=60,
    backoff_multiplier=2.0
)

# Handle failure with retry
try:
    result = execute_task(task)
    task_state.complete_task(task_id, result)
except Exception as e:
    task_state.fail_task(task_id, error=str(e))
    
    if task_state.should_retry(task_id):
        task_state.schedule_retry(task_id)
```

---

## ContextStateManager

The **ContextStateManager** handles context window management, token tracking, and context compression.

### Basic Usage

```python
from agenticaiframework import ContextStateManager, ContextState

# Initialize context manager
context_state = ContextStateManager(max_tokens=8192)

# Add to context
context_state.add(
    content="User request: Help with Python",
    token_count=8,
    priority="high"
)

# Check context status
status = context_state.get_status()
print(f"Used tokens: {status.used_tokens}/{status.max_tokens}")
print(f"State: {status.state}")  # ContextState.OPEN or ContextState.FULL
```

### Context States

```python
class ContextState:
    OPEN = "open"              # Space available
    NEAR_FULL = "near_full"    # >80% capacity
    FULL = "full"              # At capacity
    COMPRESSED = "compressed"  # Has been compressed
    OVERFLOW = "overflow"      # Exceeded limits
```

### Token Management

```python
# Reserve tokens for response
context_state.reserve_tokens(
    purpose="response",
    count=1000
)

# Get available tokens
available = context_state.get_available_tokens()
print(f"Available for content: {available}")

# Estimate token count
estimated = context_state.estimate_tokens("Sample text content")
```

### Context Compression

```python
# Auto-compress when near full
context_state = ContextStateManager(
    max_tokens=8192,
    auto_compress=True,
    compress_threshold=0.8  # Compress at 80%
)

# Manual compression
context_state.compress(
    strategy="summarize",  # Options: summarize, truncate, prioritize
    target_ratio=0.5  # Compress to 50% of current
)

# Priority-based compression
context_state.compress_by_priority(
    keep_priorities=["high", "critical"],
    summarize_priorities=["medium"],
    drop_priorities=["low"]
)
```

### Context Snapshots

```python
# Create snapshot
snapshot_id = context_state.create_snapshot(name="before_task")

# Restore snapshot
context_state.restore_snapshot(snapshot_id)

# List snapshots
snapshots = context_state.list_snapshots()
```

---

## ToolStateManager

The **ToolStateManager** tracks tool availability, execution states, and rate limiting.

### Basic Usage

```python
from agenticaiframework import ToolStateManager, ToolState

# Initialize tool state
tool_state = ToolStateManager()

# Register tool
tool_state.register_tool(
    name="web_search",
    rate_limit=10,  # 10 calls per minute
    cooldown_seconds=0
)

# Check tool availability
if tool_state.is_available("web_search"):
    tool_state.start_execution("web_search")
    result = execute_search(query)
    tool_state.end_execution("web_search", success=True)
```

### Tool States

```python
class ToolState:
    READY = "ready"            # Available for use
    EXECUTING = "executing"    # Currently running
    COOLDOWN = "cooldown"      # Rate limit cooldown
    DISABLED = "disabled"      # Manually disabled
    ERROR = "error"            # In error state
    UNAVAILABLE = "unavailable"  # External service down
```

### Rate Limiting

```python
# Configure rate limiting
tool_state.set_rate_limit(
    tool_name="api_call",
    max_calls=100,
    window_seconds=60,
    burst_allowed=10
)

# Check rate limit
remaining = tool_state.get_remaining_calls("api_call")
print(f"Remaining calls: {remaining}")

# Wait for rate limit reset
if not tool_state.is_available("api_call"):
    wait_time = tool_state.get_reset_time("api_call")
    print(f"Wait {wait_time} seconds")
```

### Tool Health Monitoring

```python
# Set health check
tool_state.set_health_check(
    tool_name="external_api",
    check_interval=60,
    check_function=lambda: ping_api()
)

# Get tool health
health = tool_state.get_health("external_api")
print(f"Status: {health.status}")
print(f"Last check: {health.last_check}")
print(f"Uptime: {health.uptime_percent}%")

# Disable unhealthy tool
if not health.is_healthy:
    tool_state.disable("external_api", reason="Health check failed")
```

---

## MemoryStateManager

The **MemoryStateManager** controls memory system states, synchronization, and consistency.

### Basic Usage

```python
from agenticaiframework import MemoryStateManager, MemoryState

# Initialize memory state
memory_state = MemoryStateManager(memory_id="main_memory")

# Get current state
current = memory_state.get_state()
print(f"Memory state: {current}")  # MemoryState.SYNCED

# Start sync operation
memory_state.start_sync()
# ... perform sync
memory_state.end_sync(success=True)
```

### Memory States

```python
class MemoryState:
    INITIALIZING = "initializing"  # Memory starting up
    SYNCED = "synced"              # Fully synchronized
    SYNCING = "syncing"            # Sync in progress
    STALE = "stale"                # Needs synchronization
    CORRUPTED = "corrupted"        # Data corruption detected
    RECOVERING = "recovering"      # Recovery in progress
```

### Sync Management

```python
# Configure auto-sync
memory_state = MemoryStateManager(
    memory_id="main",
    auto_sync=True,
    sync_interval=300  # 5 minutes
)

# Check sync status
sync_status = memory_state.get_sync_status()
print(f"Last sync: {sync_status.last_sync_time}")
print(f"Pending changes: {sync_status.pending_changes}")

# Force sync
memory_state.force_sync()
```

### Consistency Checks

```python
# Run consistency check
result = memory_state.check_consistency()
if not result.is_consistent:
    print(f"Issues found: {result.issues}")
    memory_state.repair(result.issues)

# Verify memory integrity
integrity = memory_state.verify_integrity()
print(f"Integrity score: {integrity.score}")
```

### Recovery Operations

```python
# Handle corruption
if memory_state.get_state() == MemoryState.CORRUPTED:
    # Start recovery
    memory_state.start_recovery()
    
    # Attempt recovery from backup
    success = memory_state.recover_from_backup(
        backup_path="./backups/memory_latest.bak"
    )
    
    if success:
        memory_state.end_recovery(success=True)
    else:
        memory_state.reset_to_clean_state()
```

---

## 🔧 State Persistence

### Centralized State Store

```python
from agenticaiframework import StateStore

# Initialize centralized store
store = StateStore(
    backend="redis",
    config={"host": "localhost", "port": 6379}
)

# Register state managers
store.register(agent_state)
store.register(workflow_state)
store.register(task_state)

# Auto-persist all states
store.enable_auto_persist(interval=60)

# Restore all states on startup
store.restore_all()
```

### State Snapshots

```python
# Create global snapshot
snapshot = store.create_snapshot(name="before_deployment")

# Restore from snapshot
store.restore_snapshot(snapshot.id)

# Export state for debugging
store.export("./debug/state_dump.json")
```

---

## 📚 API Reference

For complete API documentation, see:

- [AgentStateManager API](API_REFERENCE.md#agentstatemanager)
- [WorkflowStateManager API](API_REFERENCE.md#workflowstatemanager)
- [ConversationStateManager API](API_REFERENCE.md#conversationstatemanager)
- [TaskStateManager API](API_REFERENCE.md#taskstatemanager)
- [ContextStateManager API](API_REFERENCE.md#contextstatemanager)
- [ToolStateManager API](API_REFERENCE.md#toolstatemanager)
- [MemoryStateManager API](API_REFERENCE.md#memorystatemanager)
