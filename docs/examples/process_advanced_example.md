---
tags:
  - examples
  - processes
  - workflows
  - advanced
---

# Advanced Process Example

!!! tip "Enterprise Orchestration"
    Part of **380+ modules** with 12 workflow types including DAG, parallel, and consensus-based orchestration. See [Processes Documentation](../processes.md).

```python
from agenticaiframework.processes import Process

# Example: Advanced Process usage with Tasks
# -------------------------------------------
# This example demonstrates how to:
# 1. Create a Process
# 2. Add multiple Task callables to it
# 3. Execute them in sequence
#
# Expected Output:
# - Logs showing execution of each task in order

if __name__ == "__main__":
    # Create a process
    process = Process(name="AdvancedProcess", strategy="sequential")

    # Define some tasks
    def task_one():
        print("Task One executed.")

    def task_two():
        print("Task Two executed.")

    def task_three():
        print("Task Three executed.")

    # Add tasks to the process
    process.add_task(task_one)
    process.add_task(task_two)
    process.add_task(task_three)

    # Execute the process
    process.execute()

```
