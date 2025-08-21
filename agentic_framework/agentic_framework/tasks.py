"""
Tasks Module for Agentic Framework SDK

This module defines tasks, which are work units assigned to agents. Tasks specify objectives,
inputs, execution logic, and expected outputs for an agent or group of agents.
"""

from typing import List, Dict, Any, Optional, Callable
import time
from datetime import datetime

class TaskError(Exception):
    """
    Custom exception class for task-related errors in the Agentic Framework.
    """
    def __init__(self, message: str, task_name: str):
        """
        Initialize a task error with a message and the name of the task.
        
        Args:
            message (str): The error message.
            task_name (str): The name of the task where the error occurred.
        """
        super().__init__(f"Task {task_name} Error: {message}")
        self.task_name = task_name

class Task:
    """
    Base class for a task in the Agentic Framework.
    Tasks represent specific objectives or work units to be performed by agents.
    """
    def __init__(self, name: str, objective: str, inputs: Optional[Dict[str, Any]] = None,
                 expected_output: Optional[str] = None, dependencies: Optional[List[str]] = None,
                 priority: int = 0, version: str = "1.0.0", metadata: Optional[Dict[str, Any]] = None):
        """
        Initialize a task with a name, objective, inputs, expected output, and other metadata.
        
        Args:
            name (str): The unique identifier for the task.
            objective (str): The goal or purpose of the task.
            inputs (Dict[str, Any], optional): Input data or parameters for the task.
            expected_output (str, optional): Description of the expected result.
            dependencies (List[str], optional): List of task names this task depends on.
            priority (int, optional): Priority level for the task (higher number = higher priority). Defaults to 0.
            version (str, optional): Version of the task for tracking.
            metadata (Dict[str, Any], optional): Additional metadata for discovery and categorization.
        """
        self.name = name
        self.objective = objective
        self.inputs = inputs or {}
        self.expected_output = expected_output or "Task completed"
        self.dependencies = dependencies or []
        self.priority = priority
        self.version = version
        self.metadata = metadata or {}
        self.status = "pending"
        self.result = None
        self.execution_log = []
        self.creation_time = time.time()
        self.last_updated = self.creation_time
        self.start_time = None
        self.end_time = None
        self.assigned_agent = None

    def execute(self, agent: Optional[Any] = None) -> str:
        """
        Execute the task, potentially with a specific agent.
        
        Args:
            agent (Any, optional): The agent assigned to perform the task.
            
        Returns:
            str: Result of the task execution.
        """
        if self.status == "in_progress":
            return f"Task {self.name} is already in progress"
        if self.status == "completed":
            return f"Task {self.name} is already completed with result: {self.result}"
        
        self.status = "in_progress"
        self.start_time = time.time()
        self.assigned_agent = agent
        self.execution_log.append(f"Task {self.name} started at {datetime.fromtimestamp(self.start_time).isoformat()}")
        
        try:
            # Placeholder for actual task execution logic
            if agent:
                self.result = f"Task {self.name} executed by {getattr(agent, 'name', 'Unnamed Agent')}"
            else:
                self.result = f"Task {self.name} executed without specific agent"
            self.status = "completed"
            self.end_time = time.time()
            self.execution_log.append(f"Task {self.name} completed at {datetime.fromtimestamp(self.end_time).isoformat()}")
        except Exception as e:
            self.status = "failed"
            self.result = f"Error: {str(e)}"
            self.execution_log.append(f"Task {self.name} failed with error: {str(e)} at {datetime.now().isoformat()}")
            self.end_time = time.time()
            raise TaskError(str(e), self.name)
        
        return self.result

    def validate(self, validation_criteria: Optional[Callable[[str], bool]] = None) -> bool:
        """
        Validate the task's result against the expected output or custom criteria.
        
        Args:
            validation_criteria (Callable[[str], bool], optional): Custom validation function for the result.
            
        Returns:
            bool: True if the result meets expectations, False otherwise.
        """
        if self.status != "completed":
            self.execution_log.append(f"Validation failed: Task {self.name} not completed (status: {self.status})")
            return False
        
        if validation_criteria:
            is_valid = validation_criteria(self.result)
        else:
            is_valid = self.result is not None and (self.expected_output in self.result or self.expected_output == "Task completed")
        
        self.execution_log.append(f"Validation {'successful' if is_valid else 'failed'} for task {self.name}")
        return is_valid

    def update_version(self, new_version: str) -> str:
        """
        Update the version of the task.
        
        Args:
            new_version (str): New version string.
            
        Returns:
            str: Result of the operation.
        """
        old_version = self.version
        self.version = new_version
        self.last_updated = time.time()
        return f"Task {self.name} updated from version {old_version} to {new_version}"

    def adapt(self, feedback: Dict[str, Any]) -> str:
        """
        Adapt the task based on feedback or changing conditions.
        
        Args:
            feedback (Dict[str, Any]): Feedback data to guide adaptation.
            
        Returns:
            str: Result of the adaptation operation.
        """
        # Placeholder for adaptation logic
        self.last_updated = time.time()
        self.execution_log.append(f"Task {self.name} adapted based on feedback: {feedback.get('summary', 'general update')}")
        return f"Task {self.name} adapted based on feedback: {feedback.get('summary', 'general update')}"

    def get_monitoring_data(self) -> Dict[str, Any]:
        """
        Retrieve monitoring data for the task.
        
        Returns:
            Dict[str, Any]: Monitoring data including status, execution times, and logs.
        """
        return {
            "name": self.name,
            "objective": self.objective,
            "status": self.status,
            "priority": self.priority,
            "version": self.version,
            "dependencies": self.dependencies,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": (self.end_time - self.start_time) if self.start_time and self.end_time else 0.0,
            "assigned_agent": getattr(self.assigned_agent, 'name', None) if self.assigned_agent else None,
            "result": self.result,
            "log_entries": len(self.execution_log),
            "last_updated": self.last_updated
        }

class TaskManager:
    """
    Manager class for handling tasks in the Agentic Framework.
    Provides functionality for task assignment, prioritization, and orchestration.
    """
    def __init__(self, name: str, active: bool = True, max_concurrent: int = 10):
        """
        Initialize a task manager with a name, activation status, and concurrency limit.
        
        Args:
            name (str): The unique identifier for the task manager.
            active (bool, optional): Whether the manager is active by default. Defaults to True.
            max_concurrent (int, optional): Maximum number of concurrent tasks. Defaults to 10.
        """
        self.name = name
        self.active = active
        self.max_concurrent = max_concurrent
        self.tasks: Dict[str, Task] = {}
        self.discovery_metadata: Dict[str, Dict[str, Any]] = {}
        self.running_tasks: List[Task] = []
        self.performance_metrics = {"total_tasks": 0, "completed_tasks": 0, "avg_execution_time": 0.0, "success_rate": 0.0}
        self.task_log = []
        self.creation_time = time.time()
        self.last_updated = self.creation_time

    def add_task(self, task: Task, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Add a task to the manager with optional metadata for discovery.
        
        Args:
            task (Task): The task to add.
            metadata (Dict[str, Any], optional): Additional metadata for discovery and categorization.
            
        Returns:
            str: Result of the addition operation.
        """
        if not self.active:
            return f"Task Manager {self.name} is not active"
        self.tasks[task.name] = task
        if metadata:
            self.discovery_metadata[task.name] = metadata
        else:
            self.discovery_metadata[task.name] = {
                "objective": task.objective,
                "priority": task.priority,
                "version": task.version,
                "dependencies": task.dependencies,
                "category": "general"
            }
        self.performance_metrics["total_tasks"] += 1
        self.last_updated = time.time()
        self.task_log.append(f"Task {task.name} added to manager {self.name} at {datetime.now().isoformat()}")
        return f"Task {task.name} added to manager {self.name}"

    def remove_task(self, task_name: str) -> str:
        """
        Remove a task from the manager's registry.
        
        Args:
            task_name (str): Name of the task to remove.
            
        Returns:
            str: Result of the operation.
        """
        if not self.active:
            return f"Task Manager {self.name} is not active"
        if task_name in self.tasks:
            task = self.tasks.pop(task_name)
            self.discovery_metadata.pop(task_name, None)
            self.last_updated = time.time()
            self.task_log.append(f"Task {task_name} removed from manager {self.name} at {datetime.now().isoformat()}")
            if task.status == "completed":
                self.performance_metrics["completed_tasks"] -= 1
            self.performance_metrics["total_tasks"] -= 1
            return f"Task {task_name} removed from manager {self.name}"
        return f"Task {task_name} not found in manager {self.name}"

    def discover_tasks(self, criteria: Optional[Dict[str, Any]] = None) -> List[Task]:
        """
        Discover tasks based on specific criteria such as category or priority.
        
        Args:
            criteria (Dict[str, Any], optional): Criteria to filter tasks (e.g., {"category": "data_processing"}).
            
        Returns:
            List[Task]: List of matching tasks.
        """
        if not self.active:
            return []
        if not criteria:
            return list(self.tasks.values())
        
        matching_tasks = []
        for task_name, metadata in self.discovery_metadata.items():
            matches_all_criteria = True
            for key, value in criteria.items():
                if key in metadata:
                    if metadata[key] != value:
                        matches_all_criteria = False
                        break
                else:
                    matches_all_criteria = False
                    break
            if matches_all_criteria:
                matching_tasks.append(self.tasks[task_name])
        return matching_tasks

    def get_task(self, task_name: str) -> Optional[Task]:
        """
        Retrieve a specific task by name.
        
        Args:
            task_name (str): Name of the task to retrieve.
            
        Returns:
            Optional[Task]: The task if found, None otherwise.
        """
        if not self.active:
            return None
        return self.tasks.get(task_name)

    def prioritize_tasks(self) -> List[Task]:
        """
        Sort tasks based on their priority levels and dependencies.
        
        Returns:
            List[Task]: Sorted list of tasks by priority (highest to lowest) if active, empty list otherwise.
        """
        if not self.active:
            return []
        # First, create a dependency graph to ensure tasks with dependencies are ordered correctly
        task_list = list(self.tasks.values())
        sorted_tasks = []
        visited = set()
        def topological_sort(task: Task, stack: List[Task]):
            if task.name in visited:
                return
            visited.add(task.name)
            for dep_name in task.dependencies:
                if dep_name in self.tasks and dep_name not in visited:
                    topological_sort(self.tasks[dep_name], stack)
            stack.append(task)
        
        for task in task_list:
            if task.name not in visited:
                topological_sort(task, sorted_tasks)
        
        # Then sort by priority within the topological order constraints
        return sorted(sorted_tasks, key=lambda t: t.priority, reverse=True)

    def assign_task(self, task_name: str, agent: Any, agent_manager: Optional[Any] = None) -> str:
        """
        Assign a specific task to an agent, optionally using an agent manager for capability matching.
        
        Args:
            task_name (str): The name of the task to assign.
            agent (Any): The agent to assign the task to.
            agent_manager (Any, optional): Agent manager to validate agent capabilities if provided.
            
        Returns:
            str: Result of the assignment operation.
        """
        if not self.active:
            return f"Task Manager {self.name} is not active"
        if task_name not in self.tasks:
            return f"Task {task_name} not found in manager {self.name}"
        
        task = self.tasks[task_name]
        if agent_manager:
            # Placeholder for capability matching logic
            if not getattr(agent, "active", False):
                return f"Agent {getattr(agent, 'name', 'Unnamed')} is not active for task {task_name}"
        else:
            if not getattr(agent, "active", False):
                return f"Agent {getattr(agent, 'name', 'Unnamed')} is not active for task {task_name}"
        
        if len(self.running_tasks) >= self.max_concurrent:
            return f"Task {task_name} queued due to concurrency limit"
        
        self.running_tasks.append(task)
        try:
            result = task.execute(agent)
            self.task_log.append(f"Task {task_name} assigned to agent {getattr(agent, 'name', 'Unnamed')} and executed at {datetime.now().isoformat()}")
            return result
        except TaskError as e:
            self.task_log.append(f"Task {task_name} execution failed: {str(e)} at {datetime.now().isoformat()}")
            return f"Error executing task {task_name}: {str(e)}"
        finally:
            if task in self.running_tasks:
                self.running_tasks.remove(task)

    def orchestrate_tasks(self, agent_manager: Optional[Any] = None) -> List[str]:
        """
        Orchestrate execution of tasks, assigning them to agents based on priority, dependencies, and capabilities.
        
        Args:
            agent_manager (Any, optional): Manager to use for agent selection based on capabilities.
            
        Returns:
            List[str]: List of execution results or error message if not active.
        """
        if not self.active:
            return [f"Task Manager {self.name} is not active"]
        
        prioritized_tasks = self.prioritize_tasks()
        results = []
        completed_tasks = set()
        
        for task in prioritized_tasks:
            if all(dep in completed_tasks for dep in task.dependencies):
                if agent_manager and agent_manager.active:
                    # Discover agents based on task requirements (placeholder for capability matching)
                    agents = agent_manager.discover_agents(criteria={"capability": "general_task_execution"})
                    if agents and len(self.running_tasks) < self.max_concurrent:
                        selected_agent = next((agent for agent in agents if agent.active), None)
                        if selected_agent:
                            self.running_tasks.append(task)
                            try:
                                result = task.execute(selected_agent)
                                results.append(result)
                                completed_tasks.add(task.name)
                                self.task_log.append(f"Task {task.name} orchestrated to agent {selected_agent.name} at {datetime.now().isoformat()}")
                            except TaskError as e:
                                results.append(f"Error in task {task.name}: {str(e)}")
                                self.task_log.append(f"Task {task.name} failed during orchestration: {str(e)} at {datetime.now().isoformat()}")
                            finally:
                                if task in self.running_tasks:
                                    self.running_tasks.remove(task)
                        else:
                            results.append(f"No active agent available for task {task.name}")
                            self.task_log.append(f"No active agent found for task {task.name} at {datetime.now().isoformat()}")
                    else:
                        results.append(f"Task {task.name} queued due to concurrency limit or no agents")
                        self.task_log.append(f"Task {task.name} queued due to concurrency or agent availability at {datetime.now().isoformat()}")
                else:
                    if len(self.running_tasks) < self.max_concurrent:
                        self.running_tasks.append(task)
                        try:
                            result = task.execute()
                            results.append(result)
                            completed_tasks.add(task.name)
                            self.task_log.append(f"Task {task.name} executed without agent at {datetime.now().isoformat()}")
                        except TaskError as e:
                            results.append(f"Error in task {task.name}: {str(e)}")
                            self.task_log.append(f"Task {task.name} failed during orchestration: {str(e)} at {datetime.now().isoformat()}")
                        finally:
                            if task in self.running_tasks:
                                self.running_tasks.remove(task)
                    else:
                        results.append(f"Task {task.name} queued due to concurrency limit")
                        self.task_log.append(f"Task {task.name} queued due to concurrency limit at {datetime.now().isoformat()}")
            else:
                results.append(f"Task {task.name} skipped due to unmet dependencies")
                self.task_log.append(f"Task {task.name} skipped due to dependencies at {datetime.now().isoformat()}")
        
        self._update_performance_metrics()
        self.last_updated = time.time()
        return results

    def monitor_task_execution(self, task_name: str) -> Dict[str, Any]:
        """
        Monitor the execution status and details of a specific task.
        
        Args:
            task_name (str): Name of the task to monitor.
            
        Returns:
            Dict[str, Any]: Monitoring data for the task.
        """
        if not self.active:
            return {"error": f"Task Manager {self.name} is not active"}
        if task_name not in self.tasks:
            return {"error": f"Task {task_name} not found in manager {self.name}"}
        return self.tasks[task_name].get_monitoring_data()

    def adapt_task(self, task_name: str, feedback: Dict[str, Any]) -> str:
        """
        Adapt a specific task based on feedback or changing conditions.
        
        Args:
            task_name (str): Name of the task to adapt.
            feedback (Dict[str, Any]): Feedback data to guide adaptation.
            
        Returns:
            str: Result of the adaptation operation.
        """
        if not self.active:
            return f"Task Manager {self.name} is not active"
        if task_name not in self.tasks:
            return f"Task {task_name} not found in manager {self.name}"
        task = self.tasks[task_name]
        result = task.adapt(feedback)
        self.task_log.append(f"Task {task_name} adapted based on feedback at {datetime.now().isoformat()}")
        self.last_updated = time.time()
        return result

    def validate_task_completion(self, task_name: str, validation_criteria: Optional[Callable[[str], bool]] = None) -> bool:
        """
        Validate the completion of a specific task against expected output or custom criteria.
        
        Args:
            task_name (str): Name of the task to validate.
            validation_criteria (Callable[[str], bool], optional): Custom validation function for the result.
            
        Returns:
            bool: True if the task meets expectations, False otherwise.
        """
        if not self.active:
            return False
        if task_name not in self.tasks:
            return False
        task = self.tasks[task_name]
        is_valid = task.validate(validation_criteria)
        self.task_log.append(f"Task {task_name} validation {'successful' if is_valid else 'failed'} at {datetime.now().isoformat()}")
        return is_valid

    def get_task_log(self, task_name: Optional[str] = None) -> List[str]:
        """
        Retrieve the execution log for a specific task or all tasks.
        
        Args:
            task_name (str, optional): Name of the task to get logs for. If None, returns manager logs.
            
        Returns:
            List[str]: List of log entries.
        """
        if not self.active:
            return [f"Task Manager {self.name} is not active"]
        if task_name:
            if task_name in self.tasks:
                return self.tasks[task_name].execution_log
            return [f"Task {task_name} not found in manager {self.name}"]
        return self.task_log

    def _update_performance_metrics(self) -> None:
        """Update performance metrics based on task execution results."""
        total_tasks = self.performance_metrics["total_tasks"]
        if total_tasks == 0:
            return
        
        completed_tasks = sum(1 for task in self.tasks.values() if task.status == "completed")
        self.performance_metrics["completed_tasks"] = completed_tasks
        self.performance_metrics["success_rate"] = completed_tasks / total_tasks if total_tasks > 0 else 0.0
        
        total_duration = 0.0
        completed_count = 0
        for task in self.tasks.values():
            if task.status == "completed" and task.start_time and task.end_time:
                total_duration += task.end_time - task.start_time
                completed_count += 1
        self.performance_metrics["avg_execution_time"] = total_duration / completed_count if completed_count > 0 else 0.0

    def get_monitoring_data(self) -> Dict[str, Any]:
        """
        Retrieve monitoring data for the task manager and its tasks.
        
        Returns:
            Dict[str, Any]: Monitoring data including status, metrics, and running tasks.
        """
        task_data = [task.get_monitoring_data() for task in self.tasks.values()]
        return {
            "name": self.name,
            "active": self.active,
            "total_tasks": self.performance_metrics["total_tasks"],
            "completed_tasks": self.performance_metrics["completed_tasks"],
            "running_tasks": len(self.running_tasks),
            "max_concurrent": self.max_concurrent,
            "success_rate": self.performance_metrics["success_rate"],
            "avg_execution_time": self.performance_metrics["avg_execution_time"],
            "tasks": task_data,
            "log_entries": len(self.task_log),
            "last_updated": self.last_updated
        }
