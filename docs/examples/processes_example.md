---
title: Processes Example
description: Create and execute sequential, parallel, and DAG processes with Process class
tags:
  - examples
  - processes
  - workflows
---

# ⚙️ Process Example

!!! tip "12 Workflow Types"
    Part of **380+ modules** with sequential, parallel, DAG, and consensus-based orchestration. See [Processes Documentation](../processes.md).

```python
from agenticaiframework.processes import Process

# Example: Using the Process class
# ---------------------------------
# This example demonstrates how to:
# 1. Create a Process with a specific strategy
# 2. Add steps to the process
# 3. Execute the process
#
# Expected Output:
# - Logs showing the execution of each step in sequence

if __name__ == "__main__":
    # Create a process
    process = Process(name="ExampleProcess", strategy="sequential")

    # Define some example steps
    def step_one():
        print("Step One executed.")

    def step_two():
        print("Step Two executed.")

    # Add steps to the process
    process.add_step(step_one)
    process.add_step(step_two)

    # Execute the process
    process.execute()

```
