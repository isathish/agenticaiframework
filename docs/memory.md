---
title: Memory Management
description: Comprehensive guide to AgenticAI Framework's 7 specialized memory managers
---

# 💾 Memory Management

AgenticAI Framework provides **7 specialized memory managers** designed for different use cases, from general-purpose storage to specialized domain-specific memory systems.

---

## 🎯 Quick Navigation

<div class="grid cards" markdown>

-   :floppy_disk:{ .lg } **MemoryManager**

    ---

    General-purpose memory for any agent

    [:octicons-arrow-right-24: Jump to section](#memorymanager)

-   :robot:{ .lg } **AgentMemoryManager**

    ---

    Agent-specific context and state

    [:octicons-arrow-right-24: Jump to section](#agentmemorymanager)

-   :arrows_counterclockwise:{ .lg } **WorkflowMemoryManager**

    ---

    Workflow execution tracking

    [:octicons-arrow-right-24: Jump to section](#workflowmemorymanager)

-   :busts_in_silhouette:{ .lg } **OrchestrationMemoryManager**

    ---

    Multi-agent coordination

    [:octicons-arrow-right-24: Jump to section](#orchestrationmemorymanager)

-   :books:{ .lg } **KnowledgeMemoryManager**

    ---

    Knowledge base storage

    [:octicons-arrow-right-24: Jump to section](#knowledgememorymanager)

-   :hammer_and_wrench:{ .lg } **ToolMemoryManager**

    ---

    Tool execution history

    [:octicons-arrow-right-24: Jump to section](#toolmemorymanager)

-   :microphone:{ .lg } **SpeechMemoryManager**

    ---

    Voice interaction data

    [:octicons-arrow-right-24: Jump to section](#speechmemorymanager)

</div>

---

## 📊 Memory Manager Comparison

| Manager | Purpose | Key Features | Best For |
|---------|---------|--------------|----------|
| **MemoryManager** | General storage | Semantic search, compression | Single agents |
| **AgentMemoryManager** | Agent state | Context tracking, preferences | Agent persistence |
| **WorkflowMemoryManager** | Workflow state | Step tracking, branching | Complex workflows |
| **OrchestrationMemoryManager** | Multi-agent | Shared context, coordination | Agent teams |
| **KnowledgeMemoryManager** | Knowledge base | RAG, document storage | Information retrieval |
| **ToolMemoryManager** | Tool history | Execution logs, caching | Tool optimization |
| **SpeechMemoryManager** | Voice data | Transcripts, audio metadata | Voice applications |

---

## MemoryManager

The **MemoryManager** is the general-purpose memory solution for any agent. It provides semantic search, automatic compression, and flexible storage backends.

### Basic Usage

```python
from agenticaiframework import MemoryManager

# Initialize memory manager
memory = MemoryManager()

# Store a memory
memory.store(
    content="User prefers detailed technical explanations",
    metadata={
        "type": "preference",
        "user_id": "user_123",
        "category": "communication_style"
    }
)

# Search memories
results = memory.search("user preferences", top_k=5)
for result in results:
    print(f"Content: {result.content}")
    print(f"Similarity: {result.similarity:.2f}")
```

### Configuration Options

```python
memory = MemoryManager(
    # Storage backend
    backend="in-memory",  # Options: in-memory, redis, postgres, chromadb
    
    # Capacity settings
    max_entries=10000,
    max_tokens_per_entry=2048,
    
    # Compression settings
    enable_compression=True,
    compression_threshold=1000,  # Compress when > 1000 tokens
    
    # Semantic search settings
    embedding_model="text-embedding-3-small",
    similarity_threshold=0.7,
    
    # Persistence
    persist_path="./memory_data",
    auto_save=True,
    save_interval=300  # Save every 5 minutes
)
```

### Advanced Features

=== "Semantic Search"
    ```python
    # Semantic search with filters
    results = memory.search(
        query="technical explanations",
        top_k=10,
        filters={"user_id": "user_123"},
        threshold=0.75
    )
    ```

=== "Memory Compression"
    ```python
    # Enable automatic compression
    memory = MemoryManager(enable_compression=True)
    
    # Manual compression
    compressed = memory.compress(
        entries=old_memories,
        strategy="summarize"  # Options: summarize, extract_key_points, merge
    )
    ```

=== "Persistence"
    ```python
    # Save to disk
    memory.save("./checkpoints/memory_backup.pkl")
    
    # Load from disk
    memory = MemoryManager.load("./checkpoints/memory_backup.pkl")
    
    # Export to JSON
    memory.export_json("./exports/memory.json")
    ```

=== "Batch Operations"
    ```python
    # Batch store
    entries = [
        {"content": "Memory 1", "metadata": {"tag": "a"}},
        {"content": "Memory 2", "metadata": {"tag": "b"}},
        {"content": "Memory 3", "metadata": {"tag": "c"}},
    ]
    memory.store_batch(entries)
    
    # Batch delete
    memory.delete_batch(filters={"tag": "old"})
    ```

---

## AgentMemoryManager

The **AgentMemoryManager** is specialized for storing agent-specific context, preferences, and learned behaviors.

### Basic Usage

```python
from agenticaiframework import AgentMemoryManager

# Initialize for specific agent
agent_memory = AgentMemoryManager(agent_id="researcher_01")

# Store agent context
agent_memory.store_context(
    task_type="research",
    context={
        "topic": "AI safety",
        "depth": "comprehensive",
        "sources_used": ["arxiv", "google_scholar"]
    }
)

# Store learned preferences
agent_memory.store_preference(
    key="response_style",
    value="detailed_with_citations",
    confidence=0.9
)

# Retrieve agent context
context = agent_memory.get_context(task_type="research")
```

### Agent State Tracking

```python
# Track agent performance
agent_memory.record_performance(
    task_id="task_001",
    metrics={
        "accuracy": 0.95,
        "latency_ms": 1200,
        "tokens_used": 850
    }
)

# Get performance history
history = agent_memory.get_performance_history(
    task_type="research",
    last_n=10
)

# Get agent statistics
stats = agent_memory.get_statistics()
print(f"Total tasks: {stats.total_tasks}")
print(f"Average accuracy: {stats.avg_accuracy}")
```

### Skill Memory

```python
# Store learned skill
agent_memory.store_skill(
    skill_name="code_review",
    skill_data={
        "patterns_learned": ["security_checks", "performance_tips"],
        "success_rate": 0.92,
        "examples": [...]
    }
)

# Retrieve skill knowledge
skill = agent_memory.get_skill("code_review")
```

---

## WorkflowMemoryManager

The **WorkflowMemoryManager** tracks workflow execution state, step completions, and branching logic.

### Basic Usage

```python
from agenticaiframework import WorkflowMemoryManager

# Initialize for workflow
workflow_memory = WorkflowMemoryManager(workflow_id="content_pipeline")

# Record workflow step
workflow_memory.record_step(
    step_name="research",
    status="completed",
    input_data={"topic": "AI trends"},
    output_data=research_results,
    duration_ms=5000
)

# Get workflow status
status = workflow_memory.get_status()
print(f"Current step: {status.current_step}")
print(f"Completed: {status.completed_steps}")
print(f"Remaining: {status.remaining_steps}")
```

### Checkpoint Management

```python
# Create checkpoint
checkpoint_id = workflow_memory.create_checkpoint(
    name="after_research",
    data={
        "research_results": research_data,
        "next_step": "writing"
    }
)

# Restore from checkpoint
workflow_memory.restore_checkpoint(checkpoint_id)

# List all checkpoints
checkpoints = workflow_memory.list_checkpoints()
```

### Branching Workflows

```python
# Record branch decision
workflow_memory.record_branch(
    decision_point="content_type",
    selected_branch="technical_article",
    conditions={"audience": "developers"},
    alternatives=["blog_post", "whitepaper"]
)

# Get branch history
branches = workflow_memory.get_branch_history()
```

### Error Recovery

```python
# Record error
workflow_memory.record_error(
    step_name="api_call",
    error_type="RateLimitError",
    error_message="API rate limit exceeded",
    retry_count=3
)

# Get recovery suggestions
suggestions = workflow_memory.get_recovery_suggestions("api_call")
```

---

## OrchestrationMemoryManager

The **OrchestrationMemoryManager** enables memory sharing and coordination across multiple agents.

### Basic Usage

```python
from agenticaiframework import OrchestrationMemoryManager

# Initialize orchestration memory
orch_memory = OrchestrationMemoryManager(team_id="research_team")

# Share context across agents
orch_memory.share_context(
    from_agent="researcher",
    to_agents=["writer", "editor"],
    context={
        "findings": research_findings,
        "sources": source_list,
        "key_points": key_points
    }
)

# Get shared context
context = orch_memory.get_shared_context(agent_id="writer")
```

### Agent Coordination

```python
# Register agent availability
orch_memory.register_agent(
    agent_id="researcher",
    capabilities=["web_search", "data_analysis"],
    status="available"
)

# Find available agents
available = orch_memory.find_agents(
    capability="web_search",
    status="available"
)

# Update agent status
orch_memory.update_agent_status(
    agent_id="researcher",
    status="busy",
    current_task="market_research"
)
```

### Message Passing

```python
# Send message between agents
orch_memory.send_message(
    from_agent="leader",
    to_agent="researcher",
    message_type="task_assignment",
    content={
        "task": "Research competitor analysis",
        "priority": "high",
        "deadline": "2024-01-15"
    }
)

# Get pending messages
messages = orch_memory.get_messages(agent_id="researcher")
```

### Consensus Building

```python
# Record agent vote/opinion
orch_memory.record_vote(
    topic="approach_selection",
    agent_id="researcher",
    vote="option_a",
    confidence=0.8,
    reasoning="Based on data accuracy requirements"
)

# Get consensus
consensus = orch_memory.get_consensus("approach_selection")
print(f"Selected: {consensus.selected_option}")
print(f"Agreement: {consensus.agreement_level}")
```

---

## KnowledgeMemoryManager

The **KnowledgeMemoryManager** provides a powerful knowledge base with document storage, chunking, and RAG capabilities.

### Basic Usage

```python
from agenticaiframework import KnowledgeMemoryManager

# Initialize knowledge base
knowledge = KnowledgeMemoryManager()

# Add document
knowledge.add_document(
    content=document_text,
    source="company_policy.pdf",
    metadata={
        "category": "policies",
        "department": "HR",
        "version": "2.0"
    }
)

# Query knowledge base
results = knowledge.query(
    question="What is the vacation policy?",
    top_k=3
)

for result in results:
    print(f"Answer: {result.content}")
    print(f"Source: {result.source}")
    print(f"Confidence: {result.confidence:.2f}")
```

### Document Processing

```python
# Add multiple documents
knowledge.add_documents([
    {"content": doc1, "source": "file1.pdf"},
    {"content": doc2, "source": "file2.pdf"},
    {"content": doc3, "source": "file3.pdf"},
])

# Configure chunking
knowledge = KnowledgeMemoryManager(
    chunk_size=500,
    chunk_overlap=50,
    chunking_strategy="semantic"  # Options: fixed, semantic, sentence
)

# Add from file
knowledge.add_from_file("./documents/manual.pdf")

# Add from URL
knowledge.add_from_url("https://docs.example.com/api")
```

### RAG Integration

```python
# Configure RAG settings
knowledge = KnowledgeMemoryManager(
    embedding_model="text-embedding-3-large",
    retrieval_strategy="hybrid",  # Options: vector, keyword, hybrid
    rerank_model="cross-encoder"
)

# RAG query with context
context = knowledge.retrieve_context(
    query="How do I configure authentication?",
    top_k=5,
    include_metadata=True
)

# Generate answer with context
answer = agent.execute(
    prompt=f"Based on this context: {context}\n\nAnswer: {query}"
)
```

### Knowledge Categories

```python
# Create categories
knowledge.create_category("technical_docs", parent=None)
knowledge.create_category("api_reference", parent="technical_docs")

# Add to category
knowledge.add_document(
    content=api_doc,
    category="api_reference"
)

# Query specific category
results = knowledge.query(
    question="API authentication",
    category="api_reference"
)
```

---

## ToolMemoryManager

The **ToolMemoryManager** tracks tool execution history, caches results, and optimizes tool selection.

### Basic Usage

```python
from agenticaiframework import ToolMemoryManager

# Initialize tool memory
tool_memory = ToolMemoryManager()

# Record tool execution
tool_memory.record_execution(
    tool_name="web_search",
    input_params={"query": "AI trends 2024"},
    output=search_results,
    duration_ms=850,
    success=True
)

# Get execution history
history = tool_memory.get_history(tool_name="web_search", last_n=10)
```

### Result Caching

```python
# Configure caching
tool_memory = ToolMemoryManager(
    enable_caching=True,
    cache_ttl=3600,  # 1 hour
    max_cache_size=1000
)

# Check cache before execution
cached = tool_memory.get_cached_result(
    tool_name="web_search",
    input_params={"query": "AI trends"}
)

if cached:
    result = cached.output
else:
    result = execute_search("AI trends")
    tool_memory.cache_result(
        tool_name="web_search",
        input_params={"query": "AI trends"},
        output=result
    )
```

### Tool Analytics

```python
# Get tool performance metrics
metrics = tool_memory.get_tool_metrics("web_search")
print(f"Success rate: {metrics.success_rate:.2%}")
print(f"Avg latency: {metrics.avg_latency_ms}ms")
print(f"Total calls: {metrics.total_calls}")

# Get all tool statistics
all_stats = tool_memory.get_all_statistics()
for tool, stats in all_stats.items():
    print(f"{tool}: {stats.success_rate:.2%} success, {stats.avg_latency_ms}ms avg")
```

### Tool Optimization

```python
# Get tool recommendations
recommendations = tool_memory.get_recommendations(
    task_type="information_retrieval",
    based_on="success_rate"  # Options: success_rate, latency, cost
)

# Record tool failures for learning
tool_memory.record_failure(
    tool_name="api_call",
    error_type="RateLimitError",
    input_params=params,
    recovery_action="retry_with_backoff"
)
```

---

## SpeechMemoryManager

The **SpeechMemoryManager** handles voice interaction data, including transcripts, audio metadata, and conversation flow.

### Basic Usage

```python
from agenticaiframework import SpeechMemoryManager

# Initialize speech memory
speech_memory = SpeechMemoryManager()

# Store transcript
speech_memory.store_transcript(
    session_id="voice_001",
    speaker="user",
    text="What's the weather like today?",
    timestamp="2024-01-15T10:30:00Z",
    audio_metadata={
        "duration_ms": 2500,
        "sample_rate": 16000,
        "format": "wav"
    }
)

# Get conversation history
history = speech_memory.get_conversation(session_id="voice_001")
```

### Voice Profile Management

```python
# Store voice profile
speech_memory.store_voice_profile(
    user_id="user_123",
    profile={
        "voice_embedding": voice_embedding,
        "language": "en-US",
        "speaking_rate": 1.2,
        "preferred_tts_voice": "alloy"
    }
)

# Get voice profile
profile = speech_memory.get_voice_profile(user_id="user_123")
```

### Speech Analytics

```python
# Get speech metrics
metrics = speech_memory.get_session_metrics(session_id="voice_001")
print(f"Total duration: {metrics.total_duration_ms}ms")
print(f"User speaking time: {metrics.user_speaking_time_ms}ms")
print(f"Agent speaking time: {metrics.agent_speaking_time_ms}ms")
print(f"Turn count: {metrics.turn_count}")

# Get transcription accuracy
accuracy = speech_memory.get_transcription_accuracy(
    session_id="voice_001",
    ground_truth=expected_text
)
```

### Multi-Speaker Support

```python
# Record multi-speaker conversation
speech_memory.store_transcript(
    session_id="meeting_001",
    speaker="speaker_1",
    speaker_label="Alice",
    text="Let's discuss the project timeline.",
    timestamp="2024-01-15T14:00:00Z"
)

speech_memory.store_transcript(
    session_id="meeting_001",
    speaker="speaker_2",
    speaker_label="Bob",
    text="I think we need two more weeks.",
    timestamp="2024-01-15T14:00:05Z"
)

# Get speaker-segmented transcript
transcript = speech_memory.get_conversation(
    session_id="meeting_001",
    include_speaker_labels=True
)
```

---

## 🔧 Backend Configuration

### In-Memory (Default)

```python
memory = MemoryManager(backend="in-memory")
```

### Redis

```python
memory = MemoryManager(
    backend="redis",
    backend_config={
        "host": "localhost",
        "port": 6379,
        "db": 0,
        "password": "your_password"
    }
)
```

### PostgreSQL

```python
memory = MemoryManager(
    backend="postgres",
    backend_config={
        "host": "localhost",
        "port": 5432,
        "database": "agentic_memory",
        "user": "postgres",
        "password": "your_password"
    }
)
```

### ChromaDB

```python
memory = MemoryManager(
    backend="chromadb",
    backend_config={
        "persist_directory": "./chroma_data",
        "collection_name": "agent_memories"
    }
)
```

---

## 🏗️ Best Practices

### Memory Hygiene

```python
# Regular cleanup of old memories
memory.cleanup(
    older_than_days=30,
    keep_important=True
)

# Compress old memories
memory.compress_old(
    older_than_days=7,
    strategy="summarize"
)
```

### Memory Indexing

```python
# Add indexes for faster queries
memory.create_index("user_id")
memory.create_index("category")

# Query with index
results = memory.search(
    query="user preferences",
    filters={"user_id": "user_123"},  # Uses index
    top_k=10
)
```

### Memory Monitoring

```python
# Get memory statistics
stats = memory.get_statistics()
print(f"Total entries: {stats.total_entries}")
print(f"Storage size: {stats.storage_size_mb} MB")
print(f"Average entry size: {stats.avg_entry_size_tokens} tokens")

# Monitor memory health
health = memory.health_check()
if not health.is_healthy:
    print(f"Issues: {health.issues}")
```

---

## 📚 API Reference

For complete API documentation, see:

- [MemoryManager API](API_REFERENCE.md#memorymanager)
- [AgentMemoryManager API](API_REFERENCE.md#agentmemorymanager)
- [WorkflowMemoryManager API](API_REFERENCE.md#workflowmemorymanager)
- [OrchestrationMemoryManager API](API_REFERENCE.md#orchestrationmemorymanager)
- [KnowledgeMemoryManager API](API_REFERENCE.md#knowledgememorymanager)
- [ToolMemoryManager API](API_REFERENCE.md#toolmemorymanager)
- [SpeechMemoryManager API](API_REFERENCE.md#speechmemorymanager)
