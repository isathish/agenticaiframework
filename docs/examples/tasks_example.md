# Tasks Example

This example demonstrates how to create, register, and execute a custom task using the `TaskManager` and `Task` classes from the `agenticaiframework` package.

---

## Configuration
No special configuration is required. Ensure `agenticaiframework` is installed and accessible in your Python environment.

---

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

---

## Step-by-Step Execution

1. **Import** `TaskManager` and `Task` from `agenticaiframework.tasks`.
2. **Instantiate** the task manager.
3. **Define** a custom task class inheriting from `Task` and implement the `run` method.
4. **Create** an instance of the custom task.
5. **Register** the task with the manager.
6. **Execute** the task by calling its `run` method with arguments.
7. **List** all registered tasks.
8. **Retrieve** a specific task by name.

---

## Expected Input
No user input is required; the script uses hardcoded values for demonstration.

---

## Expected Output

```
[YYYY-MM-DD HH:MM:SS] [Task:AdditionTask] Running task 'AdditionTask'
[YYYY-MM-DD HH:MM:SS] [Task:AdditionTask] Task 'AdditionTask' completed successfully
Task Result: 12
[YYYY-MM-DD HH:MM:SS] [TaskManager] Registered task 'AdditionTask' with ID <UUID>
Registered Tasks: ['AdditionTask']
Retrieved Task: AdditionTask
```

---

## How to Run

```bash
python examples/tasks_example.py
