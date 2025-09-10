from typing import Callable, List
import time


class Process:
    def __init__(self, name: str, strategy: str = "sequential"):
        self.name = name
        self.strategy = strategy  # sequential, parallel, hybrid
        self.tasks: List[Callable] = []
        self.status = "initialized"

    def add_task(self, task_callable: Callable, *args, **kwargs):
        self.tasks.append((task_callable, args, kwargs))
        self._log(f"Added task {task_callable.__name__}")

    def execute(self):
        self.status = "running"
        self._log(f"Executing process '{self.name}' with strategy '{self.strategy}'")
        results = []
        if self.strategy == "sequential":
            for task_callable, args, kwargs in self.tasks:
                results.append(task_callable(*args, **kwargs))
        elif self.strategy == "parallel":
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor() as executor:
                futures = [executor.submit(task_callable, *args, **kwargs) for task_callable, args, kwargs in self.tasks]
                results = [f.result() for f in futures]
        elif self.strategy == "hybrid":
            # Simple hybrid: first half sequential, second half parallel
            half = len(self.tasks) // 2
            for task_callable, args, kwargs in self.tasks[:half]:
                results.append(task_callable(*args, **kwargs))
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor() as executor:
                futures = [executor.submit(task_callable, *args, **kwargs) for task_callable, args, kwargs in self.tasks[half:]]
                results.extend([f.result() for f in futures])
        self.status = "completed"
        return results

    def _log(self, message: str):
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [Process:{self.name}] {message}")
