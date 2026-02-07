"""
Process module for managing execution workflows.

Supports sequential, parallel, and hybrid execution strategies
with bounded thread pools and proper resource management.
"""

from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

logger = logging.getLogger(__name__)

# Default max workers capped at CPU count + 4 (like Python 3.13 default)
_DEFAULT_MAX_WORKERS = min(32, (os.cpu_count() or 1) + 4)


class Process:
    """Process with sequential, parallel, or hybrid task execution."""

    __slots__ = ("name", "strategy", "tasks", "status", "max_workers")

    def __init__(
        self,
        name: str,
        strategy: str = "sequential",
        max_workers: int | None = None,
    ):
        self.name = name
        self.strategy = strategy
        self.tasks: list[tuple[Callable[..., Any], tuple, dict]] = []
        self.status = "initialized"
        self.max_workers = max_workers or _DEFAULT_MAX_WORKERS

    def add_task(self, task_callable: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        self.tasks.append((task_callable, args, kwargs))
        logger.info("[Process:%s] Added task %s", self.name, task_callable.__name__)

    def add_step(self, step_callable: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        """Alias for add_task."""
        self.add_task(step_callable, *args, **kwargs)

    def execute(self) -> list[Any]:
        self.status = "running"
        logger.info(
            "[Process:%s] Executing with strategy '%s' (max_workers=%d)",
            self.name, self.strategy, self.max_workers,
        )
        results: list[Any] = []
        try:
            if self.strategy == "sequential":
                results = self._run_sequential(self.tasks)
            elif self.strategy == "parallel":
                results = self._run_parallel(self.tasks)
            elif self.strategy == "hybrid":
                half = len(self.tasks) // 2
                results = self._run_sequential(self.tasks[:half])
                results.extend(self._run_parallel(self.tasks[half:]))
            self.status = "completed"
        except Exception:
            self.status = "failed"
            logger.exception("[Process:%s] Execution failed", self.name)
            raise
        return results

    # ---- internal helpers ------------------------------------------------

    @staticmethod
    def _run_sequential(
        tasks: list[tuple[Callable[..., Any], tuple, dict]],
    ) -> list[Any]:
        return [fn(*a, **kw) for fn, a, kw in tasks]

    def _run_parallel(
        self,
        tasks: list[tuple[Callable[..., Any], tuple, dict]],
    ) -> list[Any]:
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = [pool.submit(fn, *a, **kw) for fn, a, kw in tasks]
            return [f.result() for f in futures]
