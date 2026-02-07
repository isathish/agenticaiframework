"""
Task management module.

Thread-safe task registration, execution, and lifecycle tracking.
"""

from __future__ import annotations

import logging
import threading
import uuid
from typing import Any, Callable

from .exceptions import TaskExecutionError  # noqa: F401 - exported for library users

logger = logging.getLogger(__name__)


class Task:
    """Represents a single executable task."""

    __slots__ = ("id", "name", "objective", "executor", "inputs", "status", "result", "version")

    def __init__(
        self,
        name: str,
        objective: str,
        executor: Callable[..., Any],
        inputs: dict[str, Any] | None = None,
    ):
        self.id = str(uuid.uuid4())
        self.name = name
        self.objective = objective
        self.executor = executor
        self.inputs = inputs or {}
        self.status = "pending"
        self.result: Any = None
        self.version = "1.0.0"

    def run(self) -> Any:
        self.status = "running"
        logger.info("[Task:%s] Running", self.name)
        try:
            self.result = self.executor(**self.inputs)
            self.status = "completed"
            logger.info("[Task:%s] Completed successfully", self.name)
        except (TypeError, ValueError, KeyError, AttributeError) as e:
            self.status = "failed"
            logger.error("Task '%s' failed: %s", self.name, e)
        except Exception:  # noqa: BLE001
            self.status = "failed"
            logger.exception("Unexpected error in task '%s'", self.name)
        return self.result


class TaskManager:
    """Thread-safe task registry and executor."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.tasks: dict[str, Task] = {}

    def register_task(self, task: Task) -> None:
        with self._lock:
            self.tasks[task.id] = task
        logger.info("[TaskManager] Registered '%s' (id=%s)", task.name, task.id)

    def get_task(self, task_id: str) -> Task | None:
        with self._lock:
            return self.tasks.get(task_id)

    def list_tasks(self) -> list[Task]:
        with self._lock:
            return list(self.tasks.values())

    def remove_task(self, task_id: str) -> None:
        with self._lock:
            if task_id in self.tasks:
                del self.tasks[task_id]
                logger.info("[TaskManager] Removed task %s", task_id)

    def run_all(self) -> dict[str, Any]:
        with self._lock:
            snapshot = dict(self.tasks)
        return {tid: task.run() for tid, task in snapshot.items()}

    def execute_task(self, task_name_or_id: str) -> Any:
        """Execute a task by name or ID."""
        with self._lock:
            task = self.tasks.get(task_name_or_id)
            if not task:
                task = next((t for t in self.tasks.values() if t.name == task_name_or_id), None)
        if task:
            return task.run()
        logger.warning("[TaskManager] Task '%s' not found", task_name_or_id)
        return None
