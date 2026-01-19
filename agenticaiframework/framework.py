"""
Agentic Framework Runtime.

Provides a cohesive runtime for creating agents and coordinating tools,
knowledge, guardrails, LLMs, policies, tasks, workflows, and tracing.
"""

from typing import Any, Callable, Dict, List, Optional

from .core import Agent, AgentManager
from .tasks import Task, TaskManager
from .knowledge import KnowledgeRetriever
from .guardrails import Guardrail, GuardrailManager, AgentPolicyManager
from .llms import LLMManager
from .monitoring import MonitoringSystem
from .processes import Process
from .orchestration import OrchestrationEngine, orchestration_engine, OrchestrationPattern
from .tools import (
    ToolRegistry,
    ToolExecutor,
    AgentToolManager,
    tool_registry,
    tool_executor,
    agent_tool_manager,
    ToolCategory,
    ToolMetadata,
)
from .tracing import tracer


class AgenticFramework:
    """Unified runtime for agentic applications."""

    def __init__(
        self,
        *,
        agent_manager: Optional[AgentManager] = None,
        task_manager: Optional[TaskManager] = None,
        knowledge: Optional[KnowledgeRetriever] = None,
        guardrail_manager: Optional[GuardrailManager] = None,
        policy_manager: Optional[AgentPolicyManager] = None,
        llm_manager: Optional[LLMManager] = None,
        monitoring: Optional[MonitoringSystem] = None,
        registry: Optional[ToolRegistry] = None,
        executor: Optional[ToolExecutor] = None,
        agent_tooling: Optional[AgentToolManager] = None,
        orchestrator: Optional[OrchestrationEngine] = None,
    ):
        self.agent_manager = agent_manager or AgentManager()
        self.task_manager = task_manager or TaskManager()
        self.knowledge = knowledge or KnowledgeRetriever()
        self.guardrail_manager = guardrail_manager or GuardrailManager()
        self.policy_manager = policy_manager or AgentPolicyManager()
        self.llm_manager = llm_manager or LLMManager()
        self.monitoring = monitoring or MonitoringSystem()

        self.registry = registry or tool_registry
        self.executor = executor or tool_executor
        if agent_tooling is not None:
            self.agent_tooling = agent_tooling
        elif registry is not None or executor is not None:
            self.agent_tooling = AgentToolManager(self.registry, self.executor)
        else:
            self.agent_tooling = agent_tool_manager

        self.orchestrator = orchestrator or orchestration_engine
        self.tracer = tracer

    def create_agent(
        self,
        name: str,
        role: str,
        capabilities: List[str],
        config: Optional[Dict[str, Any]] = None,
        max_context_tokens: int = 4096,
        register: bool = True,
    ) -> Agent:
        """Create and optionally register an agent with runtime defaults."""
        config = {
            **(config or {}),
            'llm': self.llm_manager,
            'knowledge': self.knowledge,
            'guardrail_manager': self.guardrail_manager,
            'policy_manager': self.policy_manager,
            'monitor': self.monitoring,
            'tracer': self.tracer,
        }
        agent = Agent(
            name=name,
            role=role,
            capabilities=capabilities,
            config=config,
            max_context_tokens=max_context_tokens,
        )

        if register:
            self.agent_manager.register_agent(agent)

        return agent

    def register_tool(
        self,
        tool_class: type,
        metadata: Optional[ToolMetadata] = None,
        category: ToolCategory = ToolCategory.CUSTOM,
    ) -> None:
        """Register a tool class in the tool registry."""
        self.registry.register(tool_class, metadata=metadata, category=category)

    def bind_agent_tools(self, agent: Agent, tool_names: List[str], permissions: Optional[set] = None) -> None:
        """Bind tools to a specific agent."""
        self.agent_tooling.bind_tools(agent, tool_names, permissions=permissions)

    def add_guardrail(self, guardrail: Guardrail, priority: int = 0) -> None:
        """Add a guardrail to the runtime guardrail manager."""
        self.guardrail_manager.register_guardrail(guardrail, priority=priority)

    def add_knowledge(self, key: str, content: str) -> None:
        """Add knowledge to the internal knowledge base."""
        self.knowledge.add_knowledge(key, content)

    def register_knowledge_source(self, name: str, retrieval_fn: Callable[[str], List[Dict[str, Any]]]) -> None:
        """Register an external knowledge source."""
        self.knowledge.register_source(name, retrieval_fn)

    def register_llm(self, name: str, inference_fn: Callable[[str, Dict[str, Any]], str], metadata: Optional[Dict[str, Any]] = None) -> None:
        """Register an LLM model and optionally set active model if unset."""
        self.llm_manager.register_model(name, inference_fn, metadata)
        if self.llm_manager.active_model is None:
            self.llm_manager.set_active_model(name)

    def register_policy(self, policy: Any) -> None:
        """Register a policy with the policy manager."""
        self.policy_manager.register_policy(policy)

    def evaluate_policy(self, agent_id: str, action: str, resource: Optional[str] = None, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Evaluate policies for a specific action."""
        return self.policy_manager.evaluate_policies(agent_id, action, resource, context)

    def create_task(
        self,
        name: str,
        objective: str,
        executor: Callable,
        inputs: Optional[Dict[str, Any]] = None,
        register: bool = True,
    ) -> Task:
        """Create and optionally register a task."""
        task = Task(name=name, objective=objective, executor=executor, inputs=inputs or {})
        if register:
            self.task_manager.register_task(task)
        return task

    def execute_task(self, task_name_or_id: str) -> Any:
        """Execute a task by name or ID."""
        return self.task_manager.execute_task(task_name_or_id)

    def create_workflow(self, name: str, strategy: str = "sequential") -> Process:
        """Create a workflow process."""
        return Process(name=name, strategy=strategy)

    def run_workflow(self, process: Process) -> List[Any]:
        """Execute a workflow process and return results."""
        return process.execute()

    def run_orchestration(
        self,
        agents: List[Agent],
        task_callable: Callable,
        pattern: Optional[OrchestrationPattern] = None,
        **kwargs: Any,
    ) -> Any:
        """Run orchestration with the configured orchestration engine."""
        return self.orchestrator.orchestrate(agents, task_callable, pattern, **kwargs)

    def run_agent(
        self,
        agent: Agent,
        prompt: str,
        **kwargs: Any,
    ) -> Any:
        """Run an agentic execution cycle on the provided agent."""
        return agent.run(prompt, **kwargs)

    def generate(self, prompt: str, **kwargs: Any) -> Optional[str]:
        """Generate text using the active LLM."""
        return self.llm_manager.generate(prompt, **kwargs)


__all__ = [
    "AgenticFramework",
]
