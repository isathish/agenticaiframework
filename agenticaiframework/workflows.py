"""
Workflow helpers for coordinating agent execution.

Supports sequential and parallel execution patterns with bounded
thread pools and modern asyncio best practices.
"""

from __future__ import annotations

import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Sequence

from .core import AgentManager

logger = logging.getLogger(__name__)

_DEFAULT_MAX_WORKERS = min(32, (os.cpu_count() or 1) + 4)


def _resolve_agent(manager: AgentManager, agent_key: str):
    """Resolve an agent by ID or name, raising ValueError if not found."""
    agent = manager.get_agent(agent_key)
    if agent is None:
        agent = manager.get_agent_by_name(agent_key)
    if agent is None:
        raise ValueError(f"Agent not found: {agent_key}")
    return agent


class SequentialWorkflow:
    """Sequential agent workflow execution."""

    __slots__ = ("manager",)

    def __init__(self, manager: AgentManager):
        self.manager = manager

    def execute_sequential(
        self,
        data: Any,
        agent_chain: Sequence[str],
        task_callable: Callable[[Any], Any],
    ) -> Any:
        """Execute a workflow sequentially through a chain of agents."""
        result = data
        for agent_key in agent_chain:
            agent = _resolve_agent(self.manager, agent_key)
            result = agent.execute_task(task_callable, result)
        return result


class ParallelWorkflow:
    """Parallel agent workflow execution."""

    __slots__ = ("manager",)

    def __init__(self, manager: AgentManager):
        self.manager = manager

    async def execute_parallel(
        self,
        data: Any,
        agent_names: Sequence[str],
        task_callable: Callable[[Any], Any],
    ) -> list[Any]:
        """Execute a workflow in parallel using asyncio."""
        loop = asyncio.get_running_loop()
        tasks = [
            loop.run_in_executor(
                None,
                _resolve_agent(self.manager, key).execute_task,
                task_callable,
                data,
            )
            for key in agent_names
        ]
        return list(await asyncio.gather(*tasks))

    def execute_parallel_sync(
        self,
        data: Any,
        agent_names: Sequence[str],
        task_callable: Callable[[Any], Any],
        max_workers: int | None = None,
    ) -> list[Any]:
        """Execute a workflow in parallel using threads (sync)."""
        workers = max_workers or _DEFAULT_MAX_WORKERS
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [
                executor.submit(
                    _resolve_agent(self.manager, key).execute_task,
                    task_callable,
                    data,
                )
                for key in agent_names
            ]
            return [f.result() for f in futures]


__all__ = [
    "SequentialWorkflow",
    "ParallelWorkflow",
]
