from typing import Any, Dict, List, Callable, Optional
import uuid
import time


class Task:
    def __init__(self, name: str, objective: str, executor: Callable, inputs: Dict[str, Any] = None):
        self.id = str(uuid.uuid4())
        self.name = name
        self.objective = objective
        self.executor = executor
        self.inputs = inputs or {}
        self.status = "pending"
        self.result = None
        self.version = "1.0.0"

    def run(self):
        self.status = "running"
        self._log(f"Running task '{self.name}'")
        try:
            self.result = self.executor(**self.inputs)
            self.status = "completed"
            self._log(f"Task '{self.name}' completed successfully")
        except Exception as e:
            self.status = "failed"
            self._log(f"Task '{self.name}' failed: {e}")
        return self.result

    def _log(self, message: str):
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [Task:{self.name}] {message}")


class TaskManager:
    def __init__(self):
        self.tasks: Dict[str, Task] = {}

    def register_task(self, task: Task):
        self.tasks[task.id] = task
        self._log(f"Registered task '{task.name}' with ID {task.id}")

    def get_task(self, task_id: str) -> Optional[Task]:
        return self.tasks.get(task_id)

    def list_tasks(self) -> List[Task]:
        return list(self.tasks.values())

    def remove_task(self, task_id: str):
        if task_id in self.tasks:
            del self.tasks[task_id]
            self._log(f"Removed task with ID {task_id}")

    def run_all(self):
        results = {}
        for task_id, task in self.tasks.items():
            results[task_id] = task.run()
        return results

    def _log(self, message: str):
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [TaskManager] {message}")
