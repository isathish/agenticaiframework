import agenticaiframework as aif
from agenticaiframework import tasks

# Example: Creating and running tasks
# ------------------------------------
# This example demonstrates how to:
# 1. Create a Task with a specific objective and executor function
# 2. Run the task and capture the result
# 3. Register the task with TaskManager
# 4. List and retrieve tasks
#
# Expected Output:
# - Logs showing task execution start and completion
# - Task result printed to console
# - Confirmation of task registration and listing

if __name__ == "__main__":
    # Define a simple executor function
    def add_numbers(a: int, b: int) -> int:
        return a + b

    # Create a task
    task = tasks.Task(
        name="AdditionTask",
        objective="Add two numbers together",
        executor=add_numbers,
        inputs={"a": 5, "b": 7}
    )

    # Run the task
    result = task.run()
    print("Task Result:", result)

    # Create a TaskManager and register the task
    manager = tasks.TaskManager()
    manager.register_task(task)

    # List all tasks
    tasks_list = manager.list_tasks()
    print("Registered Tasks:", [t.name for t in tasks_list])

    # Retrieve the task by ID
    retrieved_task = manager.get_task(task.id)
    print("Retrieved Task:", retrieved_task.name if retrieved_task else "Not found")
