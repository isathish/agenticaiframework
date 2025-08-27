# Memory Example

This example demonstrates how to use the `MemoryManager` in the `agenticaiframework` package to store, retrieve, list, and clear memory.

---

## Configuration
No special configuration is required. Ensure `agenticaiframework` is installed and accessible in your Python environment.

---

## Code

```python
from agenticaiframework.memory import MemoryManager

if __name__ == "__main__":
    memory = MemoryManager()

    # Store values
    memory.store_short_term("user_name", "Alice")
    memory.store_short_term("last_query", "What is the capital of France?")

    # Retrieve values
    print("Retrieved User Name:", memory.retrieve("user_name"))
    print("Retrieved Last Query:", memory.retrieve("last_query"))

    # List stored keys
    keys = list(memory.short_term.keys()) + list(memory.long_term.keys()) + list(memory.external.keys())
    print("Stored Keys:", keys)

    # Clear memory
    memory.clear_short_term()
    memory.clear_long_term()
    memory.clear_external()
    print("Memory cleared. Keys now:", list(memory.short_term.keys()) + list(memory.long_term.keys()) + list(memory.external.keys()))
```

---

## Step-by-Step Execution

1. **Import** `MemoryManager` from `agenticaiframework.memory`.
2. **Instantiate** the memory manager.
3. **Store** short-term memory entries using `store_short_term`.
4. **Retrieve** stored values using `retrieve`.
5. **List** all stored keys from short-term, long-term, and external memory.
6. **Clear** all memory types using `clear_short_term`, `clear_long_term`, and `clear_external`.

---

## Expected Input
No user input is required; the script uses hardcoded values for demonstration.

---

## Expected Output

```
[YYYY-MM-DD HH:MM:SS] [MemoryManager] Stored short-term memory: user_name
[YYYY-MM-DD HH:MM:SS] [MemoryManager] Stored short-term memory: last_query
Retrieved User Name: Alice
Retrieved Last Query: What is the capital of France?
Stored Keys: ['user_name', 'last_query']
[YYYY-MM-DD HH:MM:SS] [MemoryManager] Cleared short-term memory
[YYYY-MM-DD HH:MM:SS] [MemoryManager] Cleared long-term memory
[YYYY-MM-DD HH:MM:SS] [MemoryManager] Cleared external memory
Memory cleared. Keys now: []
```

---

## How to Run

```bash
python examples/memory_example.py
