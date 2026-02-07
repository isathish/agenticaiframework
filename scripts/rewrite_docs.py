#!/usr/bin/env python3
"""Rewrite documentation files with accurate v2.0 API content."""
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs"


def write_processes():
    (DOCS / "processes.md").write_text("""\
---
title: Processes
description: Execute multi-step workflows with sequential, parallel, and hybrid strategies using bounded thread pools
tags:
  - processes
  - workflows
  - parallel
  - concurrency
---

# :material-cog-transfer: Processes

**Execute multi-step workflows with sequential, parallel, and hybrid strategies.**

Thread-safe task execution with bounded `ThreadPoolExecutor` and automatic resource management.

!!! tip "v2.0 Improvements"
    Processes now use **bounded thread pools** (`min(32, cpu_count + 4)` workers),
    `__slots__` for lower memory overhead, and proper structured logging.

---

## Overview

The `Process` class orchestrates callable tasks using one of three execution strategies:

| Strategy | Description | Best For |
|----------|-------------|----------|
| `sequential` | Tasks run one after another in the order added | Pipelines where each step depends on the previous |
| `parallel` | All tasks run concurrently via `ThreadPoolExecutor` | Independent I/O-bound or CPU-bound work |
| `hybrid` | First half sequentially, second half in parallel | Mixed dependency / fan-out patterns |

---

## Sequential Execution

Tasks run one at a time in insertion order. The result list preserves that order.

```python
from agenticaiframework import Process

def extract(url: str) -> dict:
    return {"url": url, "data": "..."}

def transform(record: dict) -> dict:
    record["cleaned"] = True
    return record

pipeline = Process(name="etl", strategy="sequential")
pipeline.add_task(extract, "https://example.com/data.json")
pipeline.add_task(transform, {"url": "...", "data": "raw"})

results = pipeline.execute()
# results is a list of return values in task order
```

---

## Parallel Execution

All tasks are submitted to a `ThreadPoolExecutor` and run concurrently. The
default worker count is `min(32, os.cpu_count() + 4)`, matching the Python 3.13
default, and can be overridden via `max_workers`.

```python
import time
from agenticaiframework import Process

def fetch(url: str) -> str:
    time.sleep(0.5)  # simulate network I/O
    return f"fetched:{url}"

urls = [
    "https://api.example.com/a",
    "https://api.example.com/b",
    "https://api.example.com/c",
]

proc = Process(name="fetch_all", strategy="parallel", max_workers=8)
for url in urls:
    proc.add_task(fetch, url)

results = proc.execute()  # completes in ~0.5 s instead of ~1.5 s
```

!!! warning "Thread Safety"
    Tasks submitted to the parallel executor **must be thread-safe**.
    Avoid mutating shared state without synchronisation.

---

## Hybrid Execution

The first half of the task list runs sequentially; the second half runs in
parallel. Useful when initial steps produce data that later steps consume
independently.

```python
from agenticaiframework import Process

def load_config() -> dict:
    return {"batch_size": 100}

def validate_config(cfg: dict) -> bool:
    return "batch_size" in cfg

def process_shard(shard_id: int) -> str:
    return f"shard-{shard_id} done"

proc = Process(name="pipeline", strategy="hybrid")
proc.add_task(load_config)
proc.add_task(validate_config, {"batch_size": 100})
proc.add_task(process_shard, 1)
proc.add_task(process_shard, 2)

# load_config + validate_config run sequentially,
# then process_shard(1) + process_shard(2) run in parallel
results = proc.execute()
```

---

## Process Lifecycle

Every `Process` instance transitions through these states:

```text
initialized  ──▶  running  ──▶  completed
                      │
                      └──▶  failed  (on unhandled exception)
```

Check the current state via `process.status`.

---

## API Reference

### `Process`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | required | Human-readable process identifier |
| `strategy` | `str` | `"sequential"` | One of `"sequential"`, `"parallel"`, `"hybrid"` |
| `max_workers` | `int` or `None` | `None` | Thread pool size (defaults to `min(32, cpu_count + 4)`) |

**Attributes** (via `__slots__`): `name`, `strategy`, `tasks`, `status`, `max_workers`

#### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `add_task(callable, *args, **kwargs)` | `None` | Append a callable with its arguments |
| `add_step(callable, *args, **kwargs)` | `None` | Alias for `add_task` |
| `execute()` | `list[Any]` | Run all tasks and return results in order |

---

## Best Practices

!!! success "Do"
    - Keep tasks as **pure functions** — accept input, return output, no side effects.
    - Use `sequential` when order or data dependencies matter.
    - Use `parallel` for independent I/O-bound work (API calls, file reads).
    - Set `max_workers` explicitly for CPU-bound loads to avoid over-subscription.
    - Handle exceptions inside tasks when partial failure is acceptable.

!!! danger "Don't"
    - Mutate shared mutable state from parallel tasks without a lock.
    - Use `parallel` strategy for tasks that must run in order.
    - Ignore the return value of `execute()` — it contains all task results.

---

## Related Documentation

- [Orchestration](orchestration.md) — multi-agent orchestration engine
- [Tasks](tasks.md) — individual task definitions
- [Agents](agents.md) — agent lifecycle
- [Performance](performance.md) — tuning thread pools and concurrency
""")
    print("  ✓ processes.md")


def write_monitoring():
    (DOCS / "monitoring.md").write_text("""\
---
title: Monitoring
description: Real-time metrics, event logging, and garbage collection management for production workloads
tags:
  - monitoring
  - metrics
  - logging
  - observability
---

# :material-chart-line: Monitoring

**Real-time metrics collection, structured event logging, and garbage collection management.**

Thread-safe monitoring with bounded collections, `__slots__`, and structured logging throughout.

!!! tip "v2.0 Improvements"
    MonitoringSystem now uses `deque(maxlen)` for bounded metric storage,
    `threading.Lock` for thread safety, `__slots__` for memory efficiency,
    and built-in GC statistics / forced collection helpers.

---

## Overview

The `MonitoringSystem` class provides a centralised monitoring hub for your
agents, processes, and workflows:

| Feature | Description |
|---------|-------------|
| **Metrics** | Record and retrieve named numeric metrics with bounded history |
| **Events** | Log structured events with type classification |
| **Messages** | Append free-form log messages |
| **GC Management** | Inspect garbage collector stats and force collection |
| **Thread Safety** | All public methods are protected by `threading.Lock` |

---

## Quick Start

```python
from agenticaiframework import MonitoringSystem

monitor = MonitoringSystem()

# Record metrics
monitor.record_metric("latency_ms", 42.5)
monitor.record_metric("latency_ms", 38.1)
monitor.record_metric("tokens_used", 1500)

# Log events
monitor.log_event("agent_started", {"agent": "researcher", "model": "gpt-4o"})
monitor.log_event("task_completed", {"task": "summarise", "duration": 1.2})

# Log messages
monitor.log_message("Pipeline initialised successfully")

# Retrieve data
all_metrics = monitor.get_metrics()       # dict of all metrics
latency = monitor.get_metric("latency_ms")  # list of latency values
events = monitor.get_events()              # list of all events
logs = monitor.get_logs()                  # list of all messages
```

---

## Metrics

Metrics are stored per-name in bounded `deque` collections so memory usage stays
constant regardless of how long the system runs.

```python
monitor.record_metric("request_count", 1)
monitor.record_metric("request_count", 2)

values = monitor.get_metric("request_count")  # [1, 2]
```

---

## Event Logging

Events capture structured information with a type label and arbitrary details:

```python
monitor.log_event("error", {
    "component": "llm_client",
    "message": "Rate limit exceeded",
    "retry_after": 30,
})

errors = [e for e in monitor.get_events() if e["type"] == "error"]
```

---

## Garbage Collection Management

The monitoring system exposes helpers for Python's garbage collector:

```python
# Get GC statistics (generation counts, thresholds)
gc_stats = monitor.get_gc_stats()

# Force a garbage collection cycle
collected = monitor.force_gc()
```

!!! info "When to use `force_gc()`"
    Use sparingly — only when you have evidence of memory pressure (e.g. after
    disposing a large batch of agents). Python's automatic GC handles most cases.

---

## Clearing Data

Reset all collected monitoring data:

```python
monitor.clear()
```

---

## API Reference

### `MonitoringSystem`

Uses `__slots__` for memory efficiency. All methods are thread-safe.

#### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `record_metric(name, value)` | `None` | Record a numeric metric value |
| `get_metric(name)` | `list` | Retrieve all recorded values for a metric |
| `get_metrics()` | `dict` | Retrieve all metrics as `{name: [values]}` |
| `log_event(event_type, details)` | `None` | Log a structured event |
| `get_events()` | `list[dict]` | Retrieve all logged events |
| `log_message(message)` | `None` | Append a free-form log message |
| `get_logs()` | `list[str]` | Retrieve all log messages |
| `get_gc_stats()` | `dict` | Get garbage collector statistics |
| `force_gc()` | `int` | Force GC and return number of collected objects |
| `clear()` | `None` | Reset all metrics, events, and logs |

---

## Integration with Tracing

MonitoringSystem works alongside the [Tracing](tracing.md) module. Use
monitoring for **aggregate metrics** and tracing for **per-request spans**.

```python
from agenticaiframework import MonitoringSystem
from agenticaiframework.tracing import TracingManager

monitor = MonitoringSystem()
tracer = TracingManager()

# Record high-level metrics
monitor.record_metric("requests_total", 1)

# Trace individual request flow
with tracer.span("handle_request"):
    pass  # your logic here
```

---

## Best Practices

!!! success "Do"
    - Use `record_metric()` for numeric KPIs (latency, token count, error rate).
    - Use `log_event()` for discrete occurrences with structured context.
    - Review `get_gc_stats()` periodically in long-running services.
    - Call `clear()` between test runs to avoid data bleed.

!!! danger "Don't"
    - Store unbounded data in metric names — the collection is bounded, but creating
      millions of unique metric keys will still consume memory.
    - Call `force_gc()` in hot paths — it pauses the interpreter.

---

## Related Documentation

- [Tracing](tracing.md) — distributed tracing and spans
- [Performance](performance.md) — tuning and benchmarking
- [Infrastructure](infrastructure.md) — deployment and scaling
""")
    print("  ✓ monitoring.md")


def write_hub():
    (DOCS / "hub.md").write_text("""\
---
title: Hub
description: Central registry for agents, prompts, tools, guardrails, LLMs, and services
tags:
  - hub
  - registry
  - discovery
---

# :material-hub: Hub

**Central registry for agents, prompts, tools, guardrails, LLMs, and services.**

Thread-safe component registration and discovery with category validation.

!!! tip "v2.0 Improvements"
    Hub now validates categories against a `frozenset`, uses `threading.Lock`
    for thread safety, and provides `list_items()` / `remove()` helpers.

---

## Overview

The `Hub` acts as a service locator — a single place to register, discover,
and retrieve framework components at runtime.

**Supported categories** (validated via `frozenset`):

| Category | Description |
|----------|-------------|
| `agents` | Agent instances |
| `prompts` | Prompt templates |
| `tools` | Tool definitions |
| `guardrails` | Guardrail validators |
| `llms` | LLM provider instances |
| `services` | Arbitrary service objects |

---

## Quick Start

```python
from agenticaiframework import Hub

hub = Hub()

# Register components
hub.register("agents", "researcher", researcher_agent)
hub.register("tools", "web_search", search_tool)
hub.register("llms", "gpt4o", openai_client)

# Retrieve
agent = hub.get("agents", "researcher")
tool = hub.get("tools", "web_search")

# List all items in a category
all_agents = hub.list_items("agents")  # dict of {name: item}

# Remove
hub.remove("tools", "web_search")
```

---

## Service Registration

The Hub provides convenience methods for services that don't fit a specific
component category:

```python
hub.register_service("database", db_connection)
hub.register_service("cache", redis_client)

db = hub.get_service("database")
cache = hub.get_service("cache")
```

These are equivalent to `hub.register("services", name, service)` and
`hub.get("services", name)`.

---

## Category Validation

Attempting to register or retrieve from an invalid category raises a
`ValueError`:

```python
hub.register("invalid_category", "item", obj)
# ValueError: Invalid category 'invalid_category'.
# Valid: agents, guardrails, llms, prompts, services, tools
```

---

## Thread Safety

All Hub operations are protected by `threading.Lock`, making it safe to
register and retrieve components from multiple threads:

```python
import threading
from agenticaiframework import Hub

hub = Hub()

def register_agent(name, agent):
    hub.register("agents", name, agent)

threads = [
    threading.Thread(target=register_agent, args=(f"agent_{i}", obj))
    for i, obj in enumerate(agent_list)
]
for t in threads:
    t.start()
for t in threads:
    t.join()
```

---

## API Reference

### `Hub`

#### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `register(category, name, item)` | `None` | Register an item under a category |
| `get(category, name)` | `Any` | Retrieve an item by category and name |
| `list_items(category)` | `dict` | List all items in a category |
| `remove(category, name)` | `None` | Remove an item from a category |
| `register_service(name, service)` | `None` | Shortcut for `register("services", ...)` |
| `get_service(name)` | `Any` | Shortcut for `get("services", ...)` |

#### Internal

| Attribute | Type | Description |
|-----------|------|-------------|
| `_CATEGORIES` | `frozenset` | Valid category names |
| `_registry` | `dict[str, dict]` | Internal storage |
| `_lock` | `threading.Lock` | Thread synchronisation |

---

## Best Practices

!!! success "Do"
    - Register components early during application startup.
    - Use the Hub for dependency injection in multi-agent systems.
    - Use `list_items()` for admin / debugging views.
    - Clean up with `remove()` when agents are disposed.

!!! danger "Don't"
    - Use the Hub as a general-purpose key-value store — it's for framework components.
    - Bypass the Hub by passing components directly between agents (breaks discoverability).

---

## Related Documentation

- [Agents](agents.md) — agent lifecycle and registration
- [Tools](tools.md) — tool definitions
- [Guardrails](guardrails.md) — input/output validation
- [Configuration](CONFIGURATION.md) — framework configuration
""")
    print("  ✓ hub.md")


def write_knowledge():
    (DOCS / "knowledge.md").write_text("""\
---
title: Knowledge
description: Knowledge retrieval with LRU caching, pluggable sources, and thread-safe operations
tags:
  - knowledge
  - retrieval
  - caching
  - rag
---

# :material-book-open-variant: Knowledge

**Pluggable knowledge retrieval with LRU caching and thread-safe operations.**

Register custom retrieval functions, query them by name, and benefit from
automatic caching via an `OrderedDict`-based LRU cache.

!!! tip "v2.0 Improvements"
    KnowledgeRetriever now uses an `OrderedDict` LRU cache (max 1024 entries),
    `threading.Lock` for thread safety, and structured logging.

---

## Overview

The `KnowledgeRetriever` class provides a unified interface for knowledge
retrieval across multiple sources:

| Feature | Description |
|---------|-------------|
| **Pluggable sources** | Register any callable as a retrieval function |
| **LRU cache** | Automatic caching with bounded `OrderedDict` (max 1024) |
| **Direct storage** | Add key-value knowledge entries directly |
| **Thread safety** | All operations protected by `threading.Lock` |

---

## Quick Start

```python
from agenticaiframework import KnowledgeRetriever

retriever = KnowledgeRetriever()

# Register a retrieval source
def search_docs(query: str) -> str:
    # Your retrieval logic (vector DB, API, file search, etc.)
    return f"Result for: {query}"

retriever.register_source("docs", search_docs)

# Query the source
result = retriever.retrieve("docs", "How do I configure agents?")

# Results are cached automatically — second call is instant
cached = retriever.retrieve("docs", "How do I configure agents?")
```

---

## Registering Sources

A source is any callable that accepts a query string and returns a result:

```python
# Simple function
def search_wiki(query: str) -> str:
    return wiki_api.search(query)

retriever.register_source("wiki", search_wiki)

# Lambda
retriever.register_source("echo", lambda q: f"Echo: {q}")

# Class method
class VectorDB:
    def search(self, query: str) -> list[dict]:
        return self.index.query(query, top_k=5)

db = VectorDB()
retriever.register_source("vectors", db.search)
```

---

## Direct Knowledge Storage

Add static knowledge entries directly without a retrieval function:

```python
retriever.add_knowledge("company_name", "Acme Corp")
retriever.add_knowledge("max_tokens", "4096")
```

---

## LRU Cache

The cache uses `OrderedDict` with a maximum of 1024 entries. When the limit is
reached, the least recently used entry is evicted.

```python
# Check cache contents
cache = retriever.cache

# Clear the cache (e.g. after updating source data)
retriever.clear_cache()
```

!!! info "Cache Key"
    The cache key is `(source_name, query)` — so the same query to different
    sources produces separate cache entries.

---

## Bypassing the Cache

Pass `use_cache=False` to skip the cache for a specific query:

```python
# Always fetch fresh data
fresh = retriever.retrieve("docs", "latest updates", use_cache=False)
```

---

## API Reference

### `KnowledgeRetriever`

#### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `register_source(name, retrieval_fn)` | `None` | Register a named retrieval function |
| `add_knowledge(key, content)` | `None` | Add a static knowledge entry |
| `retrieve(source, query, use_cache=True)` | `Any` | Query a source with optional caching |
| `clear_cache()` | `None` | Clear the LRU cache |

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| `cache` | `OrderedDict` | Current cache contents |

#### Internal

| Attribute | Type | Description |
|-----------|------|-------------|
| `_sources` | `dict` | Registered retrieval functions |
| `_knowledge` | `dict` | Direct knowledge entries |
| `_cache` | `OrderedDict` | LRU cache (max 1024) |
| `_lock` | `threading.Lock` | Thread synchronisation |

---

## Integration with RAG

Combine KnowledgeRetriever with an LLM for retrieval-augmented generation:

```python
from agenticaiframework import KnowledgeRetriever

retriever = KnowledgeRetriever()
retriever.register_source("docs", doc_search_fn)

# Retrieve context
context = retriever.retrieve("docs", user_question)

# Build prompt with context
prompt = f"Context: {context}\\n\\nQuestion: {user_question}\\nAnswer:"
```

---

## Best Practices

!!! success "Do"
    - Register sources during application startup.
    - Use `clear_cache()` when underlying data changes.
    - Use `use_cache=False` for time-sensitive queries.
    - Keep retrieval functions fast — they block the calling thread.

!!! danger "Don't"
    - Register sources with the same name (the second overwrites the first).
    - Store large binary blobs via `add_knowledge()` — use object storage instead.
    - Forget to call `clear_cache()` after data updates.

---

## Related Documentation

- [Memory](memory.md) — persistent agent memory
- [Agents](agents.md) — agent lifecycle
- [Tools](tools.md) — tool definitions for agents
- [Hub](hub.md) — component registry
""")
    print("  ✓ knowledge.md")


def write_mcp_tools():
    (DOCS / "mcp_tools.md").write_text("""\
---
title: MCP Tools
description: Model Context Protocol tool registration, execution, and lifecycle management
tags:
  - mcp
  - tools
  - model-context-protocol
---

# :material-tools: MCP Tools

**Model Context Protocol (MCP) tool registration, execution, and lifecycle management.**

Define tools with `MCPTool`, manage them with `MCPToolManager`, and execute
them by name or ID — all thread-safe.

!!! tip "v2.0 Improvements"
    `MCPTool` uses `__slots__` for memory efficiency. `MCPToolManager` uses
    `threading.Lock` for thread safety and provides `remove_tool()` cleanup.

---

## Overview

| Class | Purpose |
|-------|---------|
| `MCPTool` | Data class representing a single tool (id, name, capability, execute function) |
| `MCPToolManager` | Registry that stores, lists, and executes tools |

---

## Quick Start

```python
from agenticaiframework.mcp_tools import MCPTool, MCPToolManager

# Define a tool
def calculate_sum(a: int, b: int) -> int:
    return a + b

tool = MCPTool(
    id="sum_tool",
    name="Calculator Sum",
    capability="Adds two numbers together",
    execute_fn=calculate_sum,
)

# Register and execute
manager = MCPToolManager()
manager.register_tool(tool)

result = manager.execute_tool("sum_tool", a=5, b=3)   # 8
result = manager.execute_tool_by_name("Calculator Sum", a=10, b=20)  # 30
```

---

## Defining Tools

Each `MCPTool` has four attributes (stored via `__slots__`):

| Attribute | Type | Description |
|-----------|------|-------------|
| `id` | `str` | Unique identifier |
| `name` | `str` | Human-readable name |
| `capability` | `str` | Description of what the tool does |
| `execute_fn` | `Callable` | The function to invoke |

```python
import httpx
from agenticaiframework.mcp_tools import MCPTool

def web_search(query: str) -> list[dict]:
    resp = httpx.get("https://api.search.example/v1", params={"q": query})
    return resp.json()["results"]

search_tool = MCPTool(
    id="web_search",
    name="Web Search",
    capability="Search the web for information",
    execute_fn=web_search,
)
```

---

## Managing Tools

### Register

```python
manager = MCPToolManager()
manager.register_tool(tool)
```

### List

```python
tools = manager.list_tools()  # list of MCPTool objects
for t in tools:
    print(f"{t.id}: {t.name} - {t.capability}")
```

### Execute by ID

```python
result = manager.execute_tool("web_search", query="Python async patterns")
```

### Execute by Name

```python
result = manager.execute_tool_by_name("Web Search", query="Python async patterns")
```

### Remove

```python
manager.remove_tool("web_search")
```

---

## Thread Safety

All `MCPToolManager` operations are protected by `threading.Lock`:

```python
import threading
from agenticaiframework.mcp_tools import MCPTool, MCPToolManager

manager = MCPToolManager()

def register_in_thread(tool):
    manager.register_tool(tool)

tools = [MCPTool(id=f"t{i}", name=f"Tool {i}", capability="...", execute_fn=lambda: i) for i in range(10)]
threads = [threading.Thread(target=register_in_thread, args=(t,)) for t in tools]
for t in threads:
    t.start()
for t in threads:
    t.join()

assert len(manager.list_tools()) == 10
```

---

## API Reference

### `MCPTool`

| Attribute | Type | Description |
|-----------|------|-------------|
| `id` | `str` | Unique tool identifier |
| `name` | `str` | Human-readable name |
| `capability` | `str` | Tool description |
| `execute_fn` | `Callable` | Function to invoke |

Uses `__slots__` — no `__dict__` overhead.

### `MCPToolManager`

| Method | Returns | Description |
|--------|---------|-------------|
| `register_tool(tool)` | `None` | Register an `MCPTool` instance |
| `execute_tool(tool_id, **kwargs)` | `Any` | Execute a tool by its ID |
| `execute_tool_by_name(name, **kwargs)` | `Any` | Execute a tool by its name |
| `list_tools()` | `list[MCPTool]` | List all registered tools |
| `remove_tool(tool_id)` | `None` | Remove a tool by ID |

---

## Best Practices

!!! success "Do"
    - Use descriptive `capability` strings — LLMs use them for tool selection.
    - Use unique, stable `id` values (e.g. snake_case identifiers).
    - Handle exceptions inside `execute_fn` or wrap calls in try/except.
    - Clean up with `remove_tool()` when tools are no longer needed.

!!! danger "Don't"
    - Register multiple tools with the same `id` (last one wins).
    - Use long-blocking operations in `execute_fn` without timeouts.
    - Forget that `execute_fn` runs synchronously on the calling thread.

---

## Related Documentation

- [Tools](tools.md) — general tool framework
- [Hub](hub.md) — component registry
- [Agents](agents.md) — agent lifecycle
- [Integration](integration.md) — third-party integrations
""")
    print("  ✓ mcp_tools.md")


def write_usage():
    (DOCS / "USAGE.md").write_text("""\
---
title: Usage Guide
description: Comprehensive usage guide for AgenticAI Framework v2.0
tags:
  - usage
  - guide
  - tutorial
---

# :material-book-open: Usage Guide

This guide covers everyday patterns for building AI agent systems with
**AgenticAI Framework v2.0**.

---

## Installation

```bash
pip install agenticaiframework
```

**Requirements**: Python >= 3.10

---

## Core Imports

```python
from agenticaiframework import (
    Agent,
    Task,
    Process,
    Hub,
    MonitoringSystem,
    KnowledgeRetriever,
    Workflow,
)
```

---

## Creating Agents

```python
from agenticaiframework import Agent

agent = Agent(
    name="researcher",
    role="Research Assistant",
    goal="Find and summarise relevant information",
    backstory="Expert researcher with deep analytical skills",
)
```

---

## Defining Tasks

```python
from agenticaiframework import Task

task = Task(
    description="Summarise the latest AI research papers",
    agent=agent,
    expected_output="A concise summary of 3-5 key papers",
)
```

---

## Running Processes

### Sequential

```python
from agenticaiframework import Process

proc = Process(name="research_pipeline", strategy="sequential")
proc.add_task(fetch_papers, "arxiv")
proc.add_task(summarise, papers)
results = proc.execute()
```

### Parallel

```python
proc = Process(name="multi_fetch", strategy="parallel", max_workers=4)
for source in ["arxiv", "scholar", "semantic"]:
    proc.add_task(fetch_papers, source)
results = proc.execute()
```

---

## Using the Hub

```python
from agenticaiframework import Hub

hub = Hub()

# Register components
hub.register("agents", "researcher", agent)
hub.register("tools", "search", search_tool)

# Retrieve
researcher = hub.get("agents", "researcher")
```

---

## Knowledge Retrieval

```python
from agenticaiframework import KnowledgeRetriever

retriever = KnowledgeRetriever()
retriever.register_source("docs", my_search_function)

result = retriever.retrieve("docs", "How to configure agents?")
# Cached automatically on second call
```

---

## Monitoring

```python
from agenticaiframework import MonitoringSystem

monitor = MonitoringSystem()
monitor.record_metric("latency_ms", 42.5)
monitor.log_event("task_completed", {"task": "summarise"})

metrics = monitor.get_metrics()
events = monitor.get_events()
gc_stats = monitor.get_gc_stats()
```

---

## MCP Tools

```python
from agenticaiframework.mcp_tools import MCPTool, MCPToolManager

tool = MCPTool(
    id="calculator",
    name="Calculator",
    capability="Perform arithmetic operations",
    execute_fn=lambda a, b: a + b,
)

manager = MCPToolManager()
manager.register_tool(tool)
result = manager.execute_tool("calculator", a=5, b=3)
```

---

## Workflows

```python
from agenticaiframework import Workflow

workflow = Workflow(name="data_pipeline")
workflow.add_step("extract", extract_fn)
workflow.add_step("transform", transform_fn)
workflow.add_step("load", load_fn)

results = workflow.run()
```

---

## Configuration

```python
from agenticaiframework import Configurations

config = Configurations()
config.set("llm.provider", "openai")
config.set("llm.model", "gpt-4o")
config.set("llm.temperature", 0.7)

provider = config.get("llm.provider")
```

---

## Guardrails

```python
from agenticaiframework.guardrails import InputGuardrail, OutputGuardrail

# Validate inputs before agent processing
input_guard = InputGuardrail(
    name="length_check",
    validator=lambda text: len(text) < 10000,
    error_message="Input too long",
)

# Validate outputs before returning to user
output_guard = OutputGuardrail(
    name="pii_check",
    validator=lambda text: "SSN" not in text,
    error_message="Output contains PII",
)
```

---

## Error Handling

```python
from agenticaiframework.exceptions import (
    AgenticAIError,
    ConfigurationError,
    ProcessExecutionError,
)

try:
    results = process.execute()
except ProcessExecutionError as e:
    logger.error("Process failed: %s", e)
except AgenticAIError as e:
    logger.error("Framework error: %s", e)
```

---

## Logging

The framework uses Python's built-in `logging` module. Configure the log
level to control output:

```python
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agenticaiframework")
logger.setLevel(logging.DEBUG)
```

---

## Best Practices

1. **Use structured logging** — the framework logs via `logging`, not `print()`.
2. **Register components in the Hub** — enables discovery and dependency injection.
3. **Set `max_workers` explicitly** for parallel processes.
4. **Clear caches** after data changes (`retriever.clear_cache()`).
5. **Handle exceptions** at the process level for graceful degradation.
6. **Use `__slots__`** in custom classes for memory-efficient agents.

---

## Related Documentation

- [Quick Start](quick-start.md) — get started in 5 minutes
- [Configuration](CONFIGURATION.md) — framework configuration
- [API Reference](API_REFERENCE.md) — full API docs
- [Examples](EXAMPLES.md) — code samples
- [Best Practices](best-practices.md) — production patterns
""")
    print("  ✓ USAGE.md")


if __name__ == "__main__":
    print("Rewriting documentation files...")
    write_processes()
    write_monitoring()
    write_hub()
    write_knowledge()
    write_mcp_tools()
    write_usage()
    print("Done! 6 files rewritten.")
