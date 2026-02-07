---
title: API Reference
description: Complete API reference for AgenticAI Framework v2.0
tags:
  - api
  - reference
---

# :material-api: API Reference

Complete API reference for **AgenticAI Framework v2.0**.

---

## Core Classes

### Agent

```python
from agenticaiframework import Agent
```

**Constructor**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | required | Agent name |
| `role` | `str` | required | Role description |
| `capabilities` | `list[str]` | required | Agent capabilities |
| `config` | `dict[str, Any]` | required | Configuration dictionary |
| `max_context_tokens` | `int` | `4096` | Maximum context window tokens |

**Factory Methods**

| Method | Description |
|--------|-------------|
| `Agent.quick(name, *, role, llm, provider, tools, auto_tools, guardrails, tracing)` | Create with sensible defaults |
| `Agent.from_config(config_dict)` | Create from configuration dictionary |

**Instance Methods**

| Method | Returns | Description |
|--------|---------|-------------|
| `execute(task)` | `AgentResult` | Execute a task |
| `invoke(prompt)` | `str` | Quick invocation with a prompt string |

**Role Templates**: `assistant`, `analyst`, `coder`, `writer`, `researcher`

---

### Task

```python
from agenticaiframework import Task
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `description` | `str` | required | Task description |
| `agent` | `Agent` | `None` | Assigned agent |
| `expected_output` | `str` | `None` | Expected output description |
| `priority` | `int` | `0` | Task priority (higher = more important) |

---

### Process

```python
from agenticaiframework import Process
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | required | Process name |
| `strategy` | `str` | `"sequential"` | `"sequential"`, `"parallel"`, `"hybrid"` |
| `max_workers` | `int` or `None` | `None` | Thread pool size |

**Methods**

| Method | Returns | Description |
|--------|---------|-------------|
| `add_task(callable, *args, **kwargs)` | `None` | Add a task |
| `add_step(callable, *args, **kwargs)` | `None` | Alias for `add_task` |
| `execute()` | `list[Any]` | Run all tasks |

**Attributes** (via `__slots__`): `name`, `strategy`, `tasks`, `status`, `max_workers`

---

### Hub

```python
from agenticaiframework import Hub
```

| Method | Returns | Description |
|--------|---------|-------------|
| `register(category, name, item)` | `None` | Register a component |
| `get(category, name)` | `Any` | Retrieve a component |
| `list_items(category)` | `dict` | List all items in a category |
| `remove(category, name)` | `None` | Remove a component |
| `register_service(name, service)` | `None` | Register a service |
| `get_service(name)` | `Any` | Retrieve a service |

**Valid categories**: `agents`, `prompts`, `tools`, `guardrails`, `llms`, `services`

---

### MonitoringSystem

```python
from agenticaiframework import MonitoringSystem
```

| Method | Returns | Description |
|--------|---------|-------------|
| `record_metric(name, value)` | `None` | Record a numeric metric |
| `get_metric(name)` | `list` | Get values for a metric |
| `get_metrics()` | `dict` | Get all metrics |
| `log_event(event_type, details)` | `None` | Log a structured event |
| `get_events()` | `list[dict]` | Get all events |
| `log_message(message)` | `None` | Log a message |
| `get_logs()` | `list[str]` | Get all log messages |
| `get_gc_stats()` | `dict` | Get GC statistics |
| `force_gc()` | `int` | Force garbage collection |
| `clear()` | `None` | Reset all data |

---

### KnowledgeRetriever

```python
from agenticaiframework import KnowledgeRetriever
```

| Method | Returns | Description |
|--------|---------|-------------|
| `register_source(name, retrieval_fn)` | `None` | Register a retrieval source |
| `add_knowledge(key, content)` | `None` | Add static knowledge |
| `retrieve(source, query, use_cache=True)` | `Any` | Query a source |
| `clear_cache()` | `None` | Clear the LRU cache |

---

### Workflow

```python
from agenticaiframework import Workflow
```

| Method | Returns | Description |
|--------|---------|-------------|
| `add_step(name, callable, *args, **kwargs)` | `None` | Add a workflow step |
| `run()` | `list[Any]` | Execute the workflow |

---

### Configurations

```python
from agenticaiframework import Configurations
```

| Method | Returns | Description |
|--------|---------|-------------|
| `set(key, value)` | `None` | Set a configuration value |
| `get(key, default=None)` | `Any` | Get a configuration value |

---

## MCP Tools

### MCPTool

```python
from agenticaiframework.mcp_tools import MCPTool
```

| Attribute | Type | Description |
|-----------|------|-------------|
| `id` | `str` | Unique tool identifier |
| `name` | `str` | Human-readable name |
| `capability` | `str` | Tool description |
| `execute_fn` | `Callable` | Function to invoke |

Uses `__slots__`.

### MCPToolManager

```python
from agenticaiframework.mcp_tools import MCPToolManager
```

| Method | Returns | Description |
|--------|---------|-------------|
| `register_tool(tool)` | `None` | Register an MCPTool |
| `execute_tool(tool_id, **kwargs)` | `Any` | Execute by ID |
| `execute_tool_by_name(name, **kwargs)` | `Any` | Execute by name |
| `list_tools()` | `list[MCPTool]` | List all tools |
| `remove_tool(tool_id)` | `None` | Remove a tool |

---

## Orchestration

### AgentTeam

```python
from agenticaiframework.orchestration import AgentTeam
```

| Method | Returns | Description |
|--------|---------|-------------|
| `add_member(agent)` | `None` | Add an agent to the team |
| `remove_member(agent_id)` | `None` | Remove an agent |

### AgentSupervisor

```python
from agenticaiframework.orchestration import AgentSupervisor
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Supervisor name |
| `agents` | `list[Agent]` | Managed agents |

---

## Security

### InputValidator

```python
from agenticaiframework.security import InputValidator
```

| Method | Returns | Description |
|--------|---------|-------------|
| `validate(text)` | `tuple[bool, str]` | Validate and sanitise input |

### PIIMasker

```python
from agenticaiframework.compliance import PIIMasker
```

| Method | Returns | Description |
|--------|---------|-------------|
| `mask(text)` | `str` | Mask PII in text |

---

## Tracing

### TracingManager

```python
from agenticaiframework.tracing import TracingManager
```

| Method | Returns | Description |
|--------|---------|-------------|
| `span(name)` | context manager | Create a tracing span |

---

## Memory

### MemoryManager

```python
from agenticaiframework.memory import MemoryManager
```

| Method | Returns | Description |
|--------|---------|-------------|
| `store(content, metadata)` | `None` | Store a memory |
| `search(query, top_k)` | `list` | Search memories |

---

## Exceptions

```python
from agenticaiframework.exceptions import (
    AgenticAIError, # Base exception
    ConfigurationError, # Configuration issues
    ProcessExecutionError, # Process execution failures
    AgentError, # Agent-related errors
    AgentNotFoundError, # Agent not found
    AgentExecutionError, # Agent execution failures
)
```

---

## Related Documentation

- [Quick Start](quick-start.md) — get started in 5 minutes
- [Usage Guide](USAGE.md) — everyday patterns
- [Configuration](CONFIGURATION.md) — framework configuration
- [Best Practices](best-practices.md) — production patterns
