---
title: Tasks Example
description: Create, register, and execute custom tasks with TaskManager and Task classes
tags:
  - example
  - tasks
  - basic
  - tutorial
---

# ✅ Task Management Example

This guide provides a **professional, step-by-step walkthrough** for creating, registering, and executing a custom task using the `TaskManager` and `Task` classes from the `agenticaiframework` package.  
It is intended for developers who want to define reusable, modular units of work for their agents.

!!! success "Enterprise Workflow Support"
    Part of **380+ modules** with 12 workflow types including DAG orchestration and parallel execution. See [Tasks Documentation](../tasks.md).


## Prerequisites & Configuration

- **Installation**: Ensure `agenticaiframework` is installed and accessible in your Python environment.
- **No additional configuration** is required for this example.
- **Python Version**: Compatible with Python 3.8+.


## Code

```python
from agenticaiframework.tasks import TaskManager, Task

if __name__ == "__main__":
    task_manager = TaskManager()

    # Define a custom task
    class AdditionTask(Task):
        def run(self, a, b):
            result = a + b
            print(f"Task Result: {result}")
            return result

    # Create and register the task
    addition_task = AdditionTask(name="AdditionTask")
    task_manager.register_task(addition_task)

    # Execute the task
    addition_task.run(5, 7)

    # List registered tasks
    print("Registered Tasks:", [task.name for task in task_manager.tasks])

    # Retrieve a specific task
    retrieved_task = task_manager.get_task("AdditionTask")
    print("Retrieved Task:", retrieved_task.name)
```


## Step-by-Step Execution

1. **Import Required Classes**  
   Import `TaskManager` and `Task` from `agenticaiframework.tasks`.

2. **Instantiate the Task Manager**  
   Create an instance of `TaskManager` to handle task registration and execution.

3. **Define a Custom Task**  
   Create a class inheriting from `Task` and implement the `run` method with the desired logic.

4. **Create the Task Instance**  
   Instantiate your custom task with a unique name.

5. **Register the Task**  
   Use `register_task` to add the task to the manager's registry.

6. **Execute the Task**  
   Call the `run` method with the required arguments.

7. **List Registered Tasks**  
   Access the `tasks` list to see all registered tasks.

8. **Retrieve a Specific Task**  
   Use `get_task` to fetch a task by name.

> **Best Practice:** Keep tasks focused on a single responsibility to make them easier to test and reuse.


## Expected Input

No user input is required; the script uses hardcoded values for demonstration purposes. In production, task parameters could be dynamically generated from user input, workflows, or other runtime data.


## Expected Output

```
[YYYY-MM-DD HH:MM:SS] [Task:AdditionTask] Running task 'AdditionTask'
[YYYY-MM-DD HH:MM:SS] [Task:AdditionTask] Task 'AdditionTask' completed successfully
Task Result: 12
[YYYY-MM-DD HH:MM:SS] [TaskManager] Registered task 'AdditionTask' with ID <UUID>
Registered Tasks: ['AdditionTask']
Retrieved Task: AdditionTask
```


## How to Run

Run the example from the project root:

```bash
python examples/tasks_example.py
```

If installed as a package, you can also run it from anywhere:

```bash
python -m examples.tasks_example
```

> **Tip:** Combine `TaskManager` with `AgentManager` to assign and execute tasks dynamically within agents.
