"""
Agents Module for Agentic Framework SDK

This module defines the core functionality for agents, which are autonomous entities capable of
performing tasks, making decisions, and interacting with other components. Agents can operate
independently or collaboratively, adapting to dynamic environments and varying workloads.
"""

from typing import List, Dict, Any, Optional
import time

class AgentError(Exception):
    """Exception raised for errors related to agent operations."""
    pass

class Agent:
    """
    Base class for an agent in the Agentic Framework.
    Agents can be specialized for specific domains or generalized for multiple purposes.
    """
    def __init__(self, name: str, role: Optional[str] = None, capabilities: Optional[List[str]] = None,
                 domain: Optional[str] = None, active: bool = False, version: str = "1.0.0", supported_modalities: Optional[List[str]] = None):
        """
        Initialize an agent with a name, role, capabilities, and other metadata.
        
        Args:
            name (str): The unique identifier for the agent.
            role (str, optional): The role or responsibility of the agent.
            capabilities (list, optional): List of capabilities or skills the agent possesses.
            domain (str, optional): The specific domain or area of expertise for the agent.
            active (bool, optional): Whether the agent is active by default. Defaults to False.
            version (str, optional): Version of the agent for tracking and upgrades.
            supported_modalities (list, optional): List of modalities the agent supports. Defaults to ["text"].
        """
        self.name = name
        self.role = role or "General Agent"
        self.capabilities = capabilities or []
        self.domain = domain or "general"
        self.active = active
        self.version = version
        self.status = "initialized"
        self.creation_time = time.time()
        self.last_updated = self.creation_time
        self.supported_modalities = supported_modalities or ["text"]  # Default modality support
        self.performance_metrics = {"tasks_completed": 0, "success_rate": 0.0, "avg_response_time": 0.0}
        self.security_context = {"authenticated": False, "authorization_level": "basic"}
        self.memory = {"short_term": {}, "long_term": {}}

    def start(self) -> str:
        """Start the agent's operation."""
        if self.active:
            return f"Agent {self.name} is already active"
        self.active = True
        self.status = "running"
        return f"Agent {self.name} started with role: {self.role}"

    def stop(self) -> str:
        """Stop the agent's operation."""
        if not self.active:
            return f"Agent {self.name} is already stopped"
        self.active = False
        self.status = "stopped"
        return f"Agent {self.name} stopped"

    def pause(self) -> str:
        """Pause the agent's operation."""
        if not self.active:
            return f"Agent {self.name} is not active"
        self.status = "paused"
        return f"Agent {self.name} paused"

    def resume(self) -> str:
        """Resume the agent's operation."""
        if not self.active:
            return f"Agent {self.name} is not active"
        if self.status != "paused":
            return f"Agent {self.name} is not paused"
        self.status = "running"
        return f"Agent {self.name} resumed"

    def retire(self) -> str:
        """Retire the agent, marking it as no longer usable."""
        self.active = False
        self.status = "retired"
        return f"Agent {self.name} retired"

    def perform_task(self, task: Any, modality: str = "text") -> str:
        """
        Perform a given task based on the agent's capabilities and supported modalities.
        
        Args:
            task (Any): The task to be performed, can be a string or structured data.
            modality (str, optional): The modality of the task input/output. Defaults to "text".
            
        Returns:
            str: Result of the task execution.
        """
        if not self.active:
            return f"Agent {self.name} is not active"
        if modality not in self.supported_modalities:
            return f"Agent {self.name} does not support modality: {modality}"
        start_time = time.time()
        result = f"Task {task} performed by {self.name} using modality {modality}"
        end_time = time.time()
        self._update_performance_metrics(start_time, end_time, success=True)
        return result

    def add_modality_support(self, modality: str) -> str:
        """
        Add support for a new modality to the agent.
        
        Args:
            modality (str): The modality to add (e.g., "image", "voice").
            
        Returns:
            str: Result of the operation.
        """
        if modality not in self.supported_modalities:
            self.supported_modalities.append(modality)
            return f"Added modality support for {modality} to agent {self.name}"
        return f"Modality {modality} already supported by agent {self.name}"

    def update_capabilities(self, capabilities: List[str]) -> str:
        """
        Update the agent's capabilities.
        
        Args:
            capabilities (List[str]): List of new capabilities to add or update.
            
        Returns:
            str: Result of the operation.
        """
        new_caps = [cap for cap in capabilities if cap not in self.capabilities]
        self.capabilities.extend(new_caps)
        self.last_updated = time.time()
        return f"Updated capabilities for agent {self.name}: added {len(new_caps)} new capabilities"

    def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """
        Authenticate the agent with provided credentials.
        
        Args:
            credentials (Dict[str, Any]): Credentials for authentication.
            
        Returns:
            bool: True if authentication successful, False otherwise.
        """
        # Placeholder for actual authentication logic
        self.security_context["authenticated"] = True
        self.security_context["authorization_level"] = credentials.get("level", "basic")
        return True

    def _update_performance_metrics(self, start_time: float, end_time: float, success: bool) -> None:
        """
        Update performance metrics based on task execution.
        
        Args:
            start_time (float): Start time of task execution.
            end_time (float): End time of task execution.
            success (bool): Whether the task was successful.
        """
        self.performance_metrics["tasks_completed"] += 1
        response_time = end_time - start_time
        total_tasks = self.performance_metrics["tasks_completed"]
        prev_avg = self.performance_metrics["avg_response_time"]
        self.performance_metrics["avg_response_time"] = (prev_avg * (total_tasks - 1) + response_time) / total_tasks
        if success:
            prev_successes = self.performance_metrics["success_rate"] * (total_tasks - 1)
            self.performance_metrics["success_rate"] = (prev_successes + 1) / total_tasks
        else:
            self.performance_metrics["success_rate"] = prev_successes / total_tasks

    def adapt_behavior(self, feedback: Dict[str, Any]) -> str:
        """
        Adapt the agent's behavior based on feedback or environmental changes.
        
        Args:
            feedback (Dict[str, Any]): Feedback data to guide adaptation.
            
        Returns:
            str: Result of the adaptation operation.
        """
        # Placeholder for adaptation logic
        self.last_updated = time.time()
        return f"Agent {self.name} adapted behavior based on feedback: {feedback.get('summary', 'general update')}"

    def store_memory(self, key: str, value: Any, memory_type: str = "short_term") -> str:
        """
        Store information in the agent's memory.
        
        Args:
            key (str): Key for the memory entry.
            value (Any): Value to store.
            memory_type (str, optional): Type of memory ('short_term' or 'long_term'). Defaults to 'short_term'.
            
        Returns:
            str: Result of the operation.
        """
        if memory_type not in self.memory:
            return f"Invalid memory type {memory_type} for agent {self.name}"
        self.memory[memory_type][key] = value
        return f"Stored {key} in {memory_type} memory of agent {self.name}"

    def retrieve_memory(self, key: str, memory_type: str = "short_term") -> Any:
        """
        Retrieve information from the agent's memory.
        
        Args:
            key (str): Key for the memory entry to retrieve.
            memory_type (str, optional): Type of memory to search in. Defaults to 'short_term'.
            
        Returns:
            Any: Retrieved value or None if not found.
        """
        if memory_type not in self.memory:
            return None
        return self.memory[memory_type].get(key)

class AgentManager:
    """
    Manager class for handling multiple agents in the Agentic Framework.
    Provides functionality for agent discovery, lifecycle management, and coordination.
    """
    def __init__(self, name: str, active: bool = True):
        """
        Initialize an agent manager with a name and activation status.
        
        Args:
            name (str): The unique identifier for the agent manager.
            active (bool, optional): Whether the manager is active by default. Defaults to True.
        """
        self.name = name
        self.active = active
        self.agents: Dict[str, Agent] = {}
        self.discovery_metadata = {}
        self.communication_channels = {}

    def add_agent(self, agent: Agent, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Add an agent to the manager's registry.
        
        Args:
            agent (Agent): The agent to add.
            metadata (Dict[str, Any], optional): Additional metadata for discovery and indexing.
            
        Returns:
            str: Result of the operation.
        """
        if not self.active:
            return f"Agent Manager {self.name} is not active"
        self.agents[agent.name] = agent
        if metadata:
            self.discovery_metadata[agent.name] = metadata
        else:
            self.discovery_metadata[agent.name] = {
                "role": agent.role,
                "capabilities": agent.capabilities,
                "domain": agent.domain,
                "version": agent.version
            }
        return f"Agent {agent.name} added to manager {self.name} with metadata"

    def register_agent(self, agent: Agent, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Register an agent to the manager's registry. Alias for add_agent.
        
        Args:
            agent (Agent): The agent to register.
            metadata (Dict[str, Any], optional): Additional metadata for discovery and indexing.
            
        Returns:
            str: Result of the operation.
        """
        return self.add_agent(agent, metadata)

    def remove_agent(self, agent_name: str) -> str:
        """
        Remove an agent from the manager's registry.
        
        Args:
            agent_name (str): Name of the agent to remove.
            
        Returns:
            str: Result of the operation.
        """
        if not self.active:
            return f"Agent Manager {self.name} is not active"
        if agent_name in self.agents:
            agent = self.agents.pop(agent_name)
            self.discovery_metadata.pop(agent_name, None)
            self.communication_channels.pop(agent_name, None)
            return f"Agent {agent_name} removed from manager {self.name}"
        return f"Agent {agent_name} not found in manager {self.name}"

    def discover_agents(self, criteria: Optional[Dict[str, Any]] = None) -> List[Agent]:
        """
        Discover agents based on specific criteria such as capability, role, or domain.
        
        Args:
            criteria (Dict[str, Any], optional): Criteria to filter agents (e.g., {"capability": "text_analysis"}).
            
        Returns:
            List[Agent]: List of matching agents.
        """
        if not self.active:
            return []
        if not criteria:
            return list(self.agents.values())
        
        matching_agents = []
        for agent_name, metadata in self.discovery_metadata.items():
            matches_all_criteria = True
            for key, value in criteria.items():
                if key == "capability":
                    if value not in metadata.get("capabilities", []):
                        matches_all_criteria = False
                        break
                elif key in metadata:
                    if metadata[key] != value:
                        matches_all_criteria = False
                        break
                else:
                    matches_all_criteria = False
                    break
            if matches_all_criteria:
                matching_agents.append(self.agents[agent_name])
        return matching_agents

    def start_all(self) -> str:
        """
        Start all agents managed by this manager.
        
        Returns:
            str: Result of the operation.
        """
        if not self.active:
            return f"Agent Manager {self.name} is not active"
        started_count = 0
        for agent in self.agents.values():
            if not agent.active:
                agent.start()
                started_count += 1
        return f"Started {started_count} agents"

    def stop_all(self) -> str:
        """
        Stop all agents managed by this manager.
        
        Returns:
            str: Result of the operation.
        """
        if not self.active:
            return f"Agent Manager {self.name} is not active"
        stopped_count = 0
        for agent in self.agents.values():
            if agent.active:
                agent.stop()
                stopped_count += 1
        return f"Stopped {stopped_count} agents"

    def start_agent(self, agent_name: str) -> str:
        """
        Start a specific agent.
        
        Args:
            agent_name (str): The name of the agent to start.
            
        Returns:
            str: Result of the start operation.
        """
        if not self.active:
            return f"Agent Manager {self.name} is not active"
        if agent_name in self.agents:
            return self.agents[agent_name].start()
        return f"Agent {agent_name} not found in manager {self.name}"

    def stop_agent(self, agent_name: str) -> str:
        """
        Stop a specific agent.
        
        Args:
            agent_name (str): The name of the agent to stop.
            
        Returns:
            str: Result of the stop operation.
        """
        if not self.active:
            return f"Agent Manager {self.name} is not active"
        if agent_name in self.agents:
            return self.agents[agent_name].stop()
        return f"Agent {agent_name} not found in manager {self.name}"

    def pause_agent(self, agent_name: str) -> str:
        """
        Pause a specific agent.
        
        Args:
            agent_name (str): The name of the agent to pause.
            
        Returns:
            str: Result of the pause operation.
        """
        if not self.active:
            return f"Agent Manager {self.name} is not active"
        if agent_name in self.agents:
            return self.agents[agent_name].pause()
        return f"Agent {agent_name} not found in manager {self.name}"

    def resume_agent(self, agent_name: str) -> str:
        """
        Resume a specific agent.
        
        Args:
            agent_name (str): The name of the agent to resume.
            
        Returns:
            str: Result of the resume operation.
        """
        if not self.active:
            return f"Agent Manager {self.name} is not active"
        if agent_name in self.agents:
            return self.agents[agent_name].resume()
        return f"Agent {agent_name} not found in manager {self.name}"

    def coordinate_task(self, task: Any, agent_names: Optional[List[str]] = None,
                        criteria: Optional[Dict[str, Any]] = None) -> str:
        """
        Coordinate a task among specified agents or select based on criteria.
        
        Args:
            task (Any): The task to coordinate.
            agent_names (List[str], optional): List of specific agent names to assign the task to.
            criteria (Dict[str, Any], optional): Criteria to select agents if no names provided.
            
        Returns:
            str: Result of the coordination operation.
        """
        if not self.active:
            return f"Agent Manager {self.name} is not active"
        if agent_names:
            selected_agents = [self.agents.get(name) for name in agent_names if name in self.agents]
        else:
            selected_agents = self.discover_agents(criteria or {})
            if not selected_agents:
                return "No suitable agents found for task coordination based on criteria"
        
        if not selected_agents:
            return "No suitable agents found for task coordination"
        
        results = []
        for agent in selected_agents:
            if agent.active:
                results.append(agent.perform_task(task))
            else:
                results.append(f"Agent {agent.name} is not active")
        return f"Task coordinated among {len(selected_agents)} agents: {results}"

    def setup_communication_channel(self, agent_name: str, channel_type: str, config: Dict[str, Any]) -> str:
        """
        Setup a communication channel for an agent.
        
        Args:
            agent_name (str): Name of the agent.
            channel_type (str): Type of communication channel (e.g., "message_queue", "websocket").
            config (Dict[str, Any]): Configuration for the channel.
            
        Returns:
            str: Result of the operation.
        """
        if not self.active:
            return f"Agent Manager {self.name} is not active"
        if agent_name not in self.agents:
            return f"Agent {agent_name} not found in manager {self.name}"
        self.communication_channels[agent_name] = {"type": channel_type, "config": config}
        return f"Communication channel {channel_type} set up for agent {agent_name}"

    def send_message(self, from_agent: str, to_agent: str, message: Any) -> str:
        """
        Send a message from one agent to another.
        
        Args:
            from_agent (str): Name of the sending agent.
            to_agent (str): Name of the receiving agent.
            message (Any): Message content to send.
            
        Returns:
            str: Result of the operation.
        """
        if not self.active:
            return f"Agent Manager {self.name} is not active"
        if from_agent not in self.agents:
            return f"Sender agent {from_agent} not found in manager {self.name}"
        if to_agent not in self.agents:
            return f"Receiver agent {to_agent} not found in manager {self.name}"
        # Placeholder for actual message transmission logic
        return f"Message sent from {from_agent} to {to_agent}: {str(message)[:50]}..."

    def monitor_performance(self, agent_name: str) -> Dict[str, Any]:
        """
        Monitor the performance of a specific agent.
        
        Args:
            agent_name (str): Name of the agent to monitor.
            
        Returns:
            Dict[str, Any]: Performance metrics of the agent.
        """
        if not self.active:
            return {"error": f"Agent Manager {self.name} is not active"}
        if agent_name not in self.agents:
            return {"error": f"Agent {agent_name} not found in manager {self.name}"}
        return self.agents[agent_name].performance_metrics

    def update_agent_version(self, agent_name: str, new_version: str) -> str:
        """
        Update the version of a specific agent.
        
        Args:
            agent_name (str): Name of the agent to update.
            new_version (str): New version string.
            
        Returns:
            str: Result of the operation.
        """
        if not self.active:
            return f"Agent Manager {self.name} is not active"
        if agent_name not in self.agents:
            return f"Agent {agent_name} not found in manager {self.name}"
        agent = self.agents[agent_name]
        old_version = agent.version
        agent.version = new_version
        agent.last_updated = time.time()
        self.discovery_metadata[agent_name]["version"] = new_version
        return f"Agent {agent_name} updated from version {old_version} to {new_version}"
