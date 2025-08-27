# AgenticAI Framework — Memory Module Documentation

## Overview
The `memory` module provides mechanisms for agents to store, retrieve, and manage information across their lifecycle. It supports both short-term and long-term memory, enabling context-aware and stateful agent behavior.

---

## Key Class

### `Memory`
**Location:** `agenticaiframework/memory.py`

The `Memory` class is a simple key-value store for agent data.

**Core Methods:**
- `store(key, value)` — Store a value under a given key.
- `retrieve(key)` — Retrieve a value by key.
- `clear()` — Clear all stored data.

---

## Example Usage

```python
from agenticaiframework.memory import Memory

memory = Memory()
memory.store("user_name", "Alice")
print(memory.retrieve("user_name"))  # Output: Alice
memory.clear()
```

---

## Use Cases

- **Session Management** — Store user session data for conversational agents.
- **Context Retention** — Maintain context between multiple agent actions.
- **Caching** — Store frequently accessed data to improve performance.

---

## Extending Memory

You can implement custom memory backends by creating a new class in `memory.py`:

```python
class PersistentMemory:
    def __init__(self, storage_path):
        self.storage_path = storage_path
        self.data = {}

    def store(self, key, value):
        self.data[key] = value
        self._save()

    def retrieve(self, key):
        return self.data.get(key)

    def clear(self):
        self.data.clear()
        self._save()

    def _save(self):
        with open(self.storage_path, "w") as f:
            f.write(str(self.data))
```

---

## Best Practices

- Use in-memory storage for short-lived agents.
- Use persistent storage for long-running agents or when data must survive restarts.
- Avoid storing sensitive data unless encrypted.

---

## Related Documentation
- [Agents Module](agents.md)
- [Hub Module](hub.md)
- [Processes Module](processes.md)
