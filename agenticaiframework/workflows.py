"""
Workflow helpers for coordinating agent execution.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, List, Sequence

from .core import AgentManager


class SequentialWorkflow:
    """Sequential agent workflow execution."""

    def __init__(self, manager: AgentManager):
        self.manager = manager

    def execute_sequential(
        self,
        data: Any,
        agent_chain: Sequence[str],
        task_callable: Callable[[Any], Any],
    ) -> Any:
        """
        Execute a workflow sequentially through a chain of agents.

        Args:
            data: Initial input to the workflow
            agent_chain: Agent names or IDs in execution order
            task_callable: Task function to run per agent
        """
        result = data
        for agent_key in agent_chain:
            agent = self._get_agent(agent_key)
            result = agent.execute_task(task_callable, result)
        return result

    def _get_agent(self, agent_key: str):
        agent = self.manager.get_agent(agent_key)
        if agent is None:
            agent = self.manager.get_agent_by_name(agent_key)
        if agent is None:
            raise ValueError(f"Agent not found: {agent_key}")
        return agent


class ParallelWorkflow:
    """Parallel agent workflow execution."""

    def __init__(self, manager: AgentManager):
        self.manager = manager

    async def execute_parallel(
        self,
        data: Any,
        agent_names: Sequence[str],
        task_callable: Callable[[Any], Any],
    ) -> List[Any]:
        """Execute a workflow in parallel using asyncio."""
        loop = asyncio.get_event_loop()
        tasks = []

        for agent_key in agent_names:
            agent = self._get_agent(agent_key)
            tasks.append(loop.run_in_executor(None, agent.execute_task, task_callable, data))

        return await asyncio.gather(*tasks)

    def execute_parallel_sync(
        self,
        data: Any,
        agent_names: Sequence[str],
        task_callable: Callable[[Any], Any],
        max_workers: int = 4,
    ) -> List[Any]:
        """Execute a workflow in parallel using threads (sync)."""
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for agent_key in agent_names:
                agent = self._get_agent(agent_key)
                futures.append(executor.submit(agent.execute_task, task_callable, data))
            return [future.result() for future in futures]

    def _get_agent(self, agent_key: str):
        agent = self.manager.get_agent(agent_key)
        if agent is None:
            agent = self.manager.get_agent_by_name(agent_key)
        if agent is None:
            raise ValueError(f"Agent not found: {agent_key}")
        return agent


__all__ = [
    "SequentialWorkflow",
    "ParallelWorkflow",
]
