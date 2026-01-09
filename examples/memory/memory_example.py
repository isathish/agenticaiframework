from agenticaiframework.memory import MemoryManager

# Example: Using MemoryManager to store and retrieve data
# ------------------------------------------------
# This example demonstrates how to:
# 1. Create a Memory instance
# 2. Store key-value pairs
# 3. Retrieve stored values
# 4. List all stored keys
# 5. Clear memory
#
# Expected Output:
# - Confirmation of stored values
# - Retrieved values printed to console
# - List of stored keys
# - Confirmation of memory clearance

if __name__ == "__main__":
    # Create a Memory instance
    memory = MemoryManager()

    # Store some values
    memory.store_short_term("user_name", "Alice")
    memory.store_short_term("last_query", "What is the capital of France?")

    # Retrieve stored values
    user_name = memory.retrieve("user_name")
    last_query = memory.retrieve("last_query")
    print("Retrieved User Name:", user_name)
    print("Retrieved Last Query:", last_query)

    # List all stored keys
    keys = list(memory.short_term.keys()) + list(memory.long_term.keys()) + list(memory.external.keys())
    print("Stored Keys:", keys)

    # Clear memory
    memory.clear_short_term()
    memory.clear_long_term()
    memory.clear_external()
    keys_after_clear = list(memory.short_term.keys()) + list(memory.long_term.keys()) + list(memory.external.keys())
    print("Memory cleared. Keys now:", keys_after_clear)
