# Memory Management Example

This guide provides a **professional, step-by-step walkthrough** of using the `MemoryManager` in the `agenticaiframework` package to efficiently store, retrieve, inspect, and clear different types of memory. It is designed for developers building intelligent agents that require persistent or temporary state management.

---

## Prerequisites & Configuration

- **Installation**: Ensure `agenticaiframework` is installed and accessible in your Python environment.
- **No additional configuration** is required for this example.
- **Python Version**: Compatible with Python 3.8+.

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

1. **Import the Class**  
   Import `MemoryManager` from `agenticaiframework.memory`.

2. **Instantiate the Manager**  
   Create an instance of `MemoryManager` to handle all memory operations.

3. **Store Data**  
   Use `store_short_term` to save temporary key-value pairs (e.g., user session data).

4. **Retrieve Data**  
   Access stored values using `retrieve` by providing the key.

5. **Inspect Stored Keys**  
   Combine keys from `short_term`, `long_term`, and `external` memory to get a complete view of stored data.

6. **Clear Memory**  
   Use `clear_short_term`, `clear_long_term`, and `clear_external` to remove stored data when no longer needed.

> **Best Practice:** Always clear sensitive data from memory after use to prevent leaks in long-running applications.

---

## Expected Input

No user input is required; the script uses hardcoded values for demonstration purposes. In production, these values could come from user interactions, API calls, or other runtime events.

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

Run the example from the project root:

```bash
python examples/memory_example.py
```

If installed as a package, you can also run it from anywhere:

```bash
python -m examples.memory_example
```

> **Tip:** Use logging or print statements to verify memory operations during development.
