---
tags:
  - examples
  - processes
  - workflows
---

# Process Example

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
