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
    logger.info(f"{t.id}: {t.name} - {t.capability}")
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
