import uuid
import time
from typing import Any, Dict, List, Optional, Callable


class Agent:
    def __init__(self, name: str, role: str, capabilities: List[str], config: Dict[str, Any]):
        self.id = str(uuid.uuid4())
        self.name = name
        self.role = role
        self.capabilities = capabilities
        self.config = config
        self.status = "initialized"
        self.memory = []
        self.version = "1.0.0"

    def start(self):
        self.status = "running"
        self._log(f"Agent {self.name} started.")

    def pause(self):
        self.status = "paused"
        self._log(f"Agent {self.name} paused.")

    def resume(self):
        self.status = "running"
        self._log(f"Agent {self.name} resumed.")

    def stop(self):
        self.status = "stopped"
        self._log(f"Agent {self.name} stopped.")

    def execute_task(self, task_callable: Callable, *args, **kwargs):
        self._log(f"Executing task with args: {args}, kwargs: {kwargs}")
        return task_callable(*args, **kwargs)

    def _log(self, message: str):
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [Agent:{self.name}] {message}")


class AgentManager:
    def __init__(self):
        self.agents: Dict[str, Agent] = {}

    def register_agent(self, agent: Agent):
        self.agents[agent.id] = agent
        print(f"Registered agent {agent.name} with ID {agent.id}")

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        return self.agents.get(agent_id)

    def list_agents(self) -> List[Agent]:
        return list(self.agents.values())

    def remove_agent(self, agent_id: str):
        if agent_id in self.agents:
            del self.agents[agent_id]
            print(f"Removed agent with ID {agent_id}")

    def broadcast(self, message: str):
        for agent in self.agents.values():
            agent._log(f"Broadcast message: {message}")
