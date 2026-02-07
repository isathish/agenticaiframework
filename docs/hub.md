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
