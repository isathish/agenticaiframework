---
tags:
  - examples
  - tasks
  - execution
---

# Task Manager Example

```python
from agenticaiframework.tasks import Task, TaskManager

# Example: Using the Task and TaskManager
# ----------------------------------------
# This example demonstrates how to:
# 1. Create tasks
# 2. Register tasks with TaskManager
# 3. Execute tasks
#
# Expected Output:
# - Logs showing task execution results

if __name__ == "__main__":
    # Create a task manager
    task_manager = TaskManager()

    # Define some example tasks
    def greet_task(name):
        return f"Hello, {name}!"

    def sum_task(a, b):
        return a + b

    # Create Task objects
    task1 = Task(name="GreetTask", objective="Greet a user", executor=greet_task, inputs={"name": "Alice"})
    task2 = Task(name="SumTask", objective="Sum two numbers", executor=sum_task, inputs={"a": 5, "b": 7})

    # Register tasks
    task_manager.register_task(task1)
    task_manager.register_task(task2)

    # Execute tasks
    for task in task_manager.list_tasks():
        result = task_manager.execute_task(task.name)
        print(f"Task '{task.name}' result:", result)

```
