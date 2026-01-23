---
tags:
  - examples
  - memory
  - storage
---

# Memory Manager Example

!!! success "7 Memory Managers"
    Part of **380+ modules** with Redis, PostgreSQL, SQLite, and vector store backends. See [Memory Documentation](../memory.md).

```python
from agenticaiframework.memory import MemoryManager

# Example: Using the MemoryManager
# ---------------------------------
# This example demonstrates how to:
# 1. Create a MemoryManager
# 2. Store and retrieve memory entries
#
# Expected Output:
# - Display of stored and retrieved memory entries

if __name__ == "__main__":
    # Create a memory manager
    memory_manager = MemoryManager()

    # Store some memory entries
    memory_manager.store("user_name", "Alice")
    memory_manager.store("last_login", "2025-09-10")

    # Retrieve and display memory entries
    print("User Name:", memory_manager.retrieve("user_name"))
    print("Last Login:", memory_manager.retrieve("last_login"))

```
