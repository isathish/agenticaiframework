"""
Process Module for Agentic Framework SDK

This module defines the execution strategies and orchestration of workflows within the framework.
It determines how tasks are executed, whether sequentially, in parallel, or through a hybrid approach,
ensuring alignment with operational flow, resource allocation, and performance goals.
"""

from typing import List, Dict, Any, Optional, Callable
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

class ProcessError(Exception):
    """
    Custom exception class for process-related errors in the Agentic Framework.
    """
    def __init__(self, message: str, process_name: str):
        """
        Initialize a process error with a message and the name of the process.
        
        Args:
            message (str): The error message.
            process_name (str): The name of the process where the error occurred.
        """
        super().__init__(f"Process {process_name} Error: {message}")
        self.process_name = process_name

class Process:
    """
    Base class for defining a process in the Agentic Framework.
    A process determines the execution strategy for tasks and workflows.
    """
    def __init__(self, name: str, execution_type: str = "sequential", version: str = "1.0.0"):
        """
        Initialize a process with a name, execution type, and version.
        
        Args:
            name (str): The unique identifier for the process.
            execution_type (str, optional): The type of execution strategy 
                ('sequential', 'parallel', 'hybrid'). Defaults to 'sequential'.
            version (str, optional): Version of the process for tracking.
        """
        self.name = name
        self.execution_type = execution_type
        self.version = version
        self.tasks: List[Any] = []
        self.status = "idle"
        self.performance_metrics = {"execution_time": 0.0, "success_rate": 0.0, "tasks_completed": 0}
        self.creation_time = time.time()
        self.last_updated = self.creation_time
        self.error_log = []
        self.resources = {"cpu": 0.0, "memory": 0.0}  # Placeholder for resource usage tracking

    def add_task(self, task: Any, dependencies: Optional[List[str]] = None) -> str:
        """
        Add a task to the process workflow with optional dependencies.
        
        Args:
            task (Any): The task to be added to the process.
            dependencies (List[str], optional): List of task names this task depends on.
            
        Returns:
            str: Result of the operation.
        """
        task_info = {"task": task, "dependencies": dependencies or [], "status": "pending", "result": None}
        self.tasks.append(task_info)
        self.last_updated = time.time()
        return f"Task added to process {self.name} with {len(dependencies or [])} dependencies"

    def execute(self, resources: Optional[Dict[str, float]] = None) -> str:
        """
        Execute the process based on the defined execution type.
        
        Args:
            resources (Dict[str, float], optional): Available resources for execution (e.g., {"cpu": 1.0, "memory": 2.0}).
            
        Returns:
            str: Result of the process execution.
        """
        if self.status == "running":
            return f"Process {self.name} is already running"
        self.status = "running"
        self.resources = resources or {"cpu": 1.0, "memory": 1.0}
        start_time = time.time()
        
        if not self.tasks:
            self.status = "completed"
            end_time = time.time()
            self.performance_metrics["execution_time"] = end_time - start_time
            return f"Process {self.name} completed: No tasks to execute"
        
        try:
            if self.execution_type == "sequential":
                result = self._execute_sequential()
            elif self.execution_type == "parallel":
                result = self._execute_parallel()
            else:  # hybrid
                result = self._execute_hybrid()
        except Exception as e:
            self.status = "failed"
            self.error_log.append(f"Execution error: {str(e)}")
            end_time = time.time()
            self.performance_metrics["execution_time"] = end_time - start_time
            return f"Process {self.name} failed: {str(e)}"
        
        self.status = "completed"
        end_time = time.time()
        self.performance_metrics["execution_time"] = end_time - start_time
        self._update_performance_metrics()
        return result

    def _execute_sequential(self) -> str:
        """
        Execute tasks one after another, respecting dependencies.
        
        Returns:
            str: Result of sequential execution.
        """
        results = []
        completed_tasks = set()
        
        for task_info in self.tasks:
            task_name = getattr(task_info["task"], "name", f"Task-{len(results)+1}")
            if all(dep in completed_tasks for dep in task_info["dependencies"]):
                try:
                    # Placeholder for actual task execution
                    task_info["status"] = "completed"
                    task_info["result"] = f"Task {task_name} executed in sequence"
                    results.append(task_info["result"])
                    completed_tasks.add(task_name)
                except Exception as e:
                    task_info["status"] = "failed"
                    task_info["result"] = f"Error: {str(e)}"
                    self.error_log.append(f"Task {task_name} failed: {str(e)}")
                    results.append(task_info["result"])
            else:
                task_info["status"] = "skipped"
                task_info["result"] = f"Skipped due to unmet dependencies"
                results.append(task_info["result"])
        
        return f"Process {self.name} completed sequentially: {len(results)} tasks processed"

    def _execute_parallel(self) -> str:
        """
        Execute tasks simultaneously, respecting dependencies.
        
        Returns:
            str: Result of parallel execution.
        """
        results = []
        completed_tasks = set()
        pending_tasks = self.tasks.copy()
        
        with ThreadPoolExecutor(max_workers=len(self.tasks)) as executor:
            while pending_tasks:
                futures = {}
                to_remove = []
                for task_info in pending_tasks:
                    task_name = getattr(task_info["task"], "name", f"Task-{len(results)+1}")
                    if all(dep in completed_tasks for dep in task_info["dependencies"]):
                        # Placeholder for actual task execution
                        futures[executor.submit(lambda t: f"Task {getattr(t, 'name', 'Unnamed')} executed in parallel", task_info["task"])] = task_info
                        to_remove.append(task_info)
                
                for task_info in to_remove:
                    pending_tasks.remove(task_info)
                
                for future in as_completed(futures):
                    task_info = futures[future]
                    task_name = getattr(task_info["task"], "name", f"Task-{len(results)+1}")
                    try:
                        task_info["result"] = future.result()
                        task_info["status"] = "completed"
                        completed_tasks.add(task_name)
                    except Exception as e:
                        task_info["result"] = f"Error: {str(e)}"
                        task_info["status"] = "failed"
                        self.error_log.append(f"Task {task_name} failed: {str(e)}")
                    results.append(task_info["result"])
                
                # Handle tasks that couldn't be executed due to dependencies
                if not futures and pending_tasks:
                    for task_info in pending_tasks:
                        task_name = getattr(task_info["task"], "name", f"Task-{len(results)+1}")
                        task_info["status"] = "skipped"
                        task_info["result"] = f"Skipped due to unmet dependencies"
                        results.append(task_info["result"])
                    pending_tasks.clear()
        
        return f"Process {self.name} completed in parallel: {len(results)} tasks processed"

    def _execute_hybrid(self) -> str:
        """
        Execute tasks using a combination of sequential and parallel strategies based on dependencies.
        
        Returns:
            str: Result of hybrid execution.
        """
        results = []
        completed_tasks = set()
        pending_tasks = self.tasks.copy()
        
        while pending_tasks:
            parallel_batch = []
            to_remove = []
            for task_info in pending_tasks:
                task_name = getattr(task_info["task"], "name", f"Task-{len(results)+1}")
                if all(dep in completed_tasks for dep in task_info["dependencies"]):
                    parallel_batch.append(task_info)
                    to_remove.append(task_info)
            
            if parallel_batch:
                with ThreadPoolExecutor(max_workers=len(parallel_batch)) as executor:
                    futures = {executor.submit(lambda t: f"Task {getattr(t, 'name', 'Unnamed')} executed in hybrid mode", task_info["task"]): task_info for task_info in parallel_batch}
                    for future in as_completed(futures):
                        task_info = futures[future]
                        task_name = getattr(task_info["task"], "name", f"Task-{len(results)+1}")
                        try:
                            task_info["result"] = future.result()
                            task_info["status"] = "completed"
                            completed_tasks.add(task_name)
                        except Exception as e:
                            task_info["result"] = f"Error: {str(e)}"
                            task_info["status"] = "failed"
                            self.error_log.append(f"Task {task_name} failed: {str(e)}")
                        results.append(task_info["result"])
                for task_info in to_remove:
                    if task_info in pending_tasks:
                        pending_tasks.remove(task_info)
            else:
                # If no tasks can be executed in parallel due to dependencies, mark remaining as skipped
                for task_info in pending_tasks:
                    task_name = getattr(task_info["task"], "name", f"Task-{len(results)+1}")
                    task_info["status"] = "skipped"
                    task_info["result"] = f"Skipped due to unmet dependencies"
                    results.append(task_info["result"])
                pending_tasks.clear()
        
        return f"Process {self.name} completed with hybrid strategy: {len(results)} tasks processed"

    def update_version(self, new_version: str) -> str:
        """
        Update the version of the process.
        
        Args:
            new_version (str): New version string.
            
        Returns:
            str: Result of the operation.
        """
        old_version = self.version
        self.version = new_version
        self.last_updated = time.time()
        return f"Process {self.name} updated from version {old_version} to {new_version}"

    def _update_performance_metrics(self) -> None:
        """Update performance metrics based on task execution results."""
        total_tasks = len(self.tasks)
        if total_tasks == 0:
            return
        completed_tasks = sum(1 for task_info in self.tasks if task_info["status"] == "completed")
        self.performance_metrics["tasks_completed"] = completed_tasks
        self.performance_metrics["success_rate"] = completed_tasks / total_tasks if total_tasks > 0 else 0.0

    def retry_failed_tasks(self, max_retries: int = 1) -> str:
        """
        Retry execution of failed tasks up to a maximum number of retries.
        
        Args:
            max_retries (int, optional): Maximum number of retries for failed tasks. Defaults to 1.
            
        Returns:
            str: Result of the retry operation.
        """
        if self.status != "completed" and self.status != "failed":
            return f"Process {self.name} is not in a state to retry tasks (current status: {self.status})"
        
        failed_tasks = [task_info for task_info in self.tasks if task_info["status"] == "failed"]
        if not failed_tasks:
            return f"No failed tasks to retry in process {self.name}"
        
        retry_count = 0
        for task_info in failed_tasks:
            if retry_count >= max_retries:
                break
            try:
                # Placeholder for actual task retry logic
                task_name = getattr(task_info["task"], "name", f"Task-{self.tasks.index(task_info)+1}")
                task_info["status"] = "completed"
                task_info["result"] = f"Task {task_name} retried successfully"
                retry_count += 1
            except Exception as e:
                task_info["result"] = f"Retry failed: {str(e)}"
                self.error_log.append(f"Retry for task in {self.name} failed: {str(e)}")
        
        self._update_performance_metrics()
        return f"Retried {retry_count} failed tasks in process {self.name}"

    def get_monitoring_data(self) -> Dict[str, Any]:
        """
        Retrieve monitoring data for the process.
        
        Returns:
            Dict[str, Any]: Monitoring data including status, metrics, and errors.
        """
        return {
            "name": self.name,
            "status": self.status,
            "execution_type": self.execution_type,
            "version": self.version,
            "tasks_count": len(self.tasks),
            "completed_tasks": self.performance_metrics["tasks_completed"],
            "success_rate": self.performance_metrics["success_rate"],
            "execution_time": self.performance_metrics["execution_time"],
            "errors": len(self.error_log),
            "last_updated": self.last_updated,
            "resources": self.resources
        }

class ProcessScheduler:
    """
    Class for scheduling and managing process execution in the Agentic Framework.
    Handles resource-aware scheduling and execution strategies.
    """
    def __init__(self, name: str, active: bool = True, max_concurrent: int = 5):
        """
        Initialize a process scheduler with a name, activation status, and concurrency limit.
        
        Args:
            name (str): The unique identifier for the scheduler.
            active (bool, optional): Whether the scheduler is active by default. Defaults to True.
            max_concurrent (int, optional): Maximum number of concurrent processes. Defaults to 5.
        """
        self.name = name
        self.active = active
        self.max_concurrent = max_concurrent
        self.processes: List[Process] = []
        self.running_processes: List[Process] = []
        self.event_listeners: Dict[str, Callable] = {}
        self.resources = {"cpu": 4.0, "memory": 16.0}  # Placeholder for total available resources
        self.performance_metrics = {"total_executions": 0, "avg_execution_time": 0.0, "success_rate": 0.0}
        self.creation_time = time.time()
        self.last_updated = self.creation_time

    def add_process(self, process: Process) -> str:
        """
        Add a process to the scheduler for management.
        
        Args:
            process (Process): The process to add.
            
        Returns:
            str: Result of the addition operation.
        """
        if not self.active:
            return f"Process Scheduler {self.name} is not active"
        self.processes.append(process)
        self.last_updated = time.time()
        return f"Process {process.name} added to scheduler {self.name}"

    def remove_process(self, process_name: str) -> str:
        """
        Remove a process from the scheduler.
        
        Args:
            process_name (str): Name of the process to remove.
            
        Returns:
            str: Result of the operation.
        """
        if not self.active:
            return f"Process Scheduler {self.name} is not active"
        for i, process in enumerate(self.processes):
            if process.name == process_name:
                self.processes.pop(i)
                self.last_updated = time.time()
                return f"Process {process_name} removed from scheduler {self.name}"
        return f"Process {process_name} not found in scheduler {self.name}"

    def schedule_sequential(self, process_names: Optional[List[str]] = None) -> str:
        """
        Schedule processes to run sequentially.
        
        Args:
            process_names (List[str], optional): Specific process names to schedule. If None, all processes are scheduled.
            
        Returns:
            str: Result of the scheduling operation.
        """
        if not self.active:
            return f"Process Scheduler {self.name} is not active"
        target_processes = [p for p in self.processes if process_names is None or p.name in process_names]
        if not target_processes:
            return f"No processes to schedule sequentially in {self.name}"
        
        results = []
        for process in target_processes:
            if len(self.running_processes) >= self.max_concurrent:
                results.append(f"Process {process.name} queued due to concurrency limit")
                continue
            try:
                self.running_processes.append(process)
                result = process.execute(self._allocate_resources(process))
                results.append(result)
                self.running_processes.remove(process)
                self.performance_metrics["total_executions"] += 1
            except ProcessError as e:
                results.append(f"Error in process {process.name}: {str(e)}")
                self.running_processes.remove(process)
        
        self._update_performance_metrics()
        self.last_updated = time.time()
        return f"Scheduled {len(target_processes)} processes sequentially in {self.name}: {len(results)} results"

    def schedule_parallel(self, process_names: Optional[List[str]] = None) -> str:
        """
        Schedule processes to run in parallel, respecting concurrency limits.
        
        Args:
            process_names (List[str], optional): Specific process names to schedule. If None, all processes are scheduled.
            
        Returns:
            str: Result of the scheduling operation.
        """
        if not self.active:
            return f"Process Scheduler {self.name} is not active"
        target_processes = [p for p in self.processes if process_names is None or p.name in process_names]
        if not target_processes:
            return f"No processes to schedule in parallel in {self.name}"
        
        results = []
        with ThreadPoolExecutor(max_workers=self.max_concurrent) as executor:
            futures = {}
            for process in target_processes:
                if len(self.running_processes) >= self.max_concurrent:
                    results.append(f"Process {process.name} queued due to concurrency limit")
                    continue
                self.running_processes.append(process)
                futures[executor.submit(process.execute, self._allocate_resources(process))] = process
            
            for future in as_completed(futures):
                process = futures[future]
                try:
                    result = future.result()
                    results.append(result)
                    self.performance_metrics["total_executions"] += 1
                except ProcessError as e:
                    results.append(f"Error in process {process.name}: {str(e)}")
                finally:
                    if process in self.running_processes:
                        self.running_processes.remove(process)
        
        self._update_performance_metrics()
        self.last_updated = time.time()
        return f"Scheduled {len(target_processes)} processes in parallel in {self.name}: {len(results)} results"

    def schedule_hybrid(self, process_names: Optional[List[str]] = None) -> str:
        """
        Schedule processes using a hybrid strategy, grouping by dependencies and resource needs.
        
        Args:
            process_names (List[str], optional): Specific process names to schedule. If None, all processes are scheduled.
            
        Returns:
            str: Result of the scheduling operation.
        """
        if not self.active:
            return f"Process Scheduler {self.name} is not active"
        target_processes = [p for p in self.processes if process_names is None or p.name in process_names]
        if not target_processes:
            return f"No processes to schedule with hybrid strategy in {self.name}"
        
        results = []
        # Placeholder for dependency and resource-based grouping logic
        sequential_groups = [target_processes[i:i+2] for i in range(0, len(target_processes), 2)]
        
        for group in sequential_groups:
            if len(group) == 1:
                if len(self.running_processes) < self.max_concurrent:
                    self.running_processes.append(group[0])
                    try:
                        result = group[0].execute(self._allocate_resources(group[0]))
                        results.append(result)
                        self.performance_metrics["total_executions"] += 1
                    except ProcessError as e:
                        results.append(f"Error in process {group[0].name}: {str(e)}")
                    finally:
                        if group[0] in self.running_processes:
                            self.running_processes.remove(group[0])
                else:
                    results.append(f"Process {group[0].name} queued due to concurrency limit")
            else:
                with ThreadPoolExecutor(max_workers=min(len(group), self.max_concurrent - len(self.running_processes))) as executor:
                    futures = {}
                    for process in group:
                        if len(self.running_processes) < self.max_concurrent:
                            self.running_processes.append(process)
                            futures[executor.submit(process.execute, self._allocate_resources(process))] = process
                        else:
                            results.append(f"Process {process.name} queued due to concurrency limit")
                    
                    for future in as_completed(futures):
                        process = futures[future]
                        try:
                            result = future.result()
                            results.append(result)
                            self.performance_metrics["total_executions"] += 1
                        except ProcessError as e:
                            results.append(f"Error in process {process.name}: {str(e)}")
                        finally:
                            if process in self.running_processes:
                                self.running_processes.remove(process)
        
        self._update_performance_metrics()
        self.last_updated = time.time()
        return f"Scheduled {len(target_processes)} processes with hybrid strategy in {self.name}: {len(results)} results"

    def execute_conditional(self, process_name: str, condition: bool) -> str:
        """
        Execute a specific process based on a condition.
        
        Args:
            process_name (str): The name of the process to execute.
            condition (bool): The condition to check before execution.
            
        Returns:
            str: Result of the conditional execution.
        """
        if not self.active:
            return f"Process Scheduler {self.name} is not active"
        if not condition:
            return f"Condition not met for process {process_name}"
        for process in self.processes:
            if process.name == process_name:
                if len(self.running_processes) >= self.max_concurrent:
                    return f"Process {process_name} queued due to concurrency limit"
                self.running_processes.append(process)
                try:
                    result = process.execute(self._allocate_resources(process))
                    self.performance_metrics["total_executions"] += 1
                    self._update_performance_metrics()
                    return result
                except ProcessError as e:
                    return f"Error in conditional execution of {process_name}: {str(e)}"
                finally:
                    if process in self.running_processes:
                        self.running_processes.remove(process)
        return f"Process {process_name} not found in scheduler {self.name}"

    def execute_event_driven(self, event: str, process_name: str) -> str:
        """
        Execute a specific process based on an event trigger.
        
        Args:
            event (str): The event that triggers the execution.
            process_name (str): The name of the process to execute.
            
        Returns:
            str: Result of the event-driven execution.
        """
        if not self.active:
            return f"Process Scheduler {self.name} is not active"
        for process in self.processes:
            if process.name == process_name:
                if len(self.running_processes) >= self.max_concurrent:
                    return f"Process {process_name} queued due to concurrency limit"
                self.running_processes.append(process)
                try:
                    result = process.execute(self._allocate_resources(process))
                    self.performance_metrics["total_executions"] += 1
                    self._update_performance_metrics()
                    return f"Event {event} triggered execution of {process_name}: {result}"
                except ProcessError as e:
                    return f"Error in event-driven execution of {process_name}: {str(e)}"
                finally:
                    if process in self.running_processes:
                        self.running_processes.remove(process)
        return f"Process {process_name} not found in scheduler {self.name}"

    def execute_iterative(self, process_name: str, condition_func: Callable[[], bool], max_iterations: int = 10) -> str:
        """
        Execute a specific process iteratively until a condition is met or max iterations reached.
        
        Args:
            process_name (str): The name of the process to execute.
            condition_func (Callable[[], bool]): Function that returns False to stop iteration.
            max_iterations (int, optional): Maximum number of iterations. Defaults to 10.
            
        Returns:
            str: Result of the iterative execution.
        """
        if not self.active:
            return f"Process Scheduler {self.name} is not active"
        for process in self.processes:
            if process.name == process_name:
                iteration = 0
                results = []
                while iteration < max_iterations and condition_func():
                    if len(self.running_processes) >= self.max_concurrent:
                        return f"Process {process_name} queued due to concurrency limit on iteration {iteration+1}"
                    self.running_processes.append(process)
                    try:
                        result = process.execute(self._allocate_resources(process))
                        results.append(f"Iteration {iteration+1}: {result}")
                        self.performance_metrics["total_executions"] += 1
                    except ProcessError as e:
                        results.append(f"Iteration {iteration+1} error: {str(e)}")
                        return f"Error in iterative execution of {process_name}: {str(e)}"
                    finally:
                        if process in self.running_processes:
                            self.running_processes.remove(process)
                    iteration += 1
                self._update_performance_metrics()
                return f"Iterative execution of {process_name} completed after {iteration} iterations: {results}"
        return f"Process {process_name} not found in scheduler {self.name}"

    def register_event_listener(self, event_type: str, callback: Callable[[str], None]) -> str:
        """
        Register a callback function to be called when a specific event type occurs.
        
        Args:
            event_type (str): Type of event to listen for.
            callback (Callable[[str], None]): Callback function to execute on event.
            
        Returns:
            str: Result of the registration operation.
        """
        if not self.active:
            return f"Process Scheduler {self.name} is not active"
        self.event_listeners[event_type] = callback
        return f"Event listener for {event_type} registered in scheduler {self.name}"

    def trigger_event(self, event_type: str, event_data: str) -> str:
        """
        Trigger an event, executing the registered callback if available.
        
        Args:
            event_type (str): Type of event to trigger.
            event_data (str): Data associated with the event.
            
        Returns:
            str: Result of the event trigger operation.
        """
        if not self.active:
            return f"Process Scheduler {self.name} is not active"
        if event_type in self.event_listeners:
            try:
                self.event_listeners[event_type](event_data)
                return f"Event {event_type} triggered with data {event_data} in scheduler {self.name}"
            except Exception as e:
                return f"Error triggering event {event_type}: {str(e)}"
        return f"No listener registered for event {event_type} in scheduler {self.name}"

    def _allocate_resources(self, process: Process) -> Dict[str, float]:
        """
        Allocate resources for a process based on availability and requirements.
        
        Args:
            process (Process): The process to allocate resources for.
            
        Returns:
            Dict[str, float]: Allocated resources for the process.
        """
        # Placeholder for resource allocation logic
        allocated = {"cpu": min(1.0, self.resources["cpu"]), "memory": min(2.0, self.resources["memory"])}
        self.resources["cpu"] -= allocated["cpu"]
        self.resources["memory"] -= allocated["memory"]
        return allocated

    def _update_performance_metrics(self) -> None:
        """Update performance metrics based on process execution results."""
        total_executions = self.performance_metrics["total_executions"]
        if total_executions == 0:
            return
        
        total_execution_time = sum(p.performance_metrics["execution_time"] for p in self.processes if p.status == "completed")
        total_successes = sum(1 for p in self.processes if p.status == "completed")
        
        prev_avg_time = self.performance_metrics["avg_execution_time"]
        self.performance_metrics["avg_execution_time"] = (prev_avg_time * (total_executions - 1) + total_execution_time) / total_executions if total_executions > 0 else 0.0
        prev_successes = self.performance_metrics["success_rate"] * (total_executions - 1)
        self.performance_metrics["success_rate"] = (prev_successes + total_successes) / total_executions if total_executions > 0 else 0.0

    def get_monitoring_data(self) -> Dict[str, Any]:
        """
        Retrieve monitoring data for the scheduler and its processes.
        
        Returns:
            Dict[str, Any]: Monitoring data including status, metrics, and running processes.
        """
        process_data = [p.get_monitoring_data() for p in self.processes]
        return {
            "name": self.name,
            "active": self.active,
            "total_processes": len(self.processes),
            "running_processes": len(self.running_processes),
            "max_concurrent": self.max_concurrent,
            "total_executions": self.performance_metrics["total_executions"],
            "avg_execution_time": self.performance_metrics["avg_execution_time"],
            "success_rate": self.performance_metrics["success_rate"],
            "available_resources": self.resources,
            "processes": process_data,
            "last_updated": self.last_updated
        }

    def recover_failed_processes(self, max_retries: int = 1) -> str:
        """
        Attempt to recover failed processes by retrying them.
        
        Args:
            max_retries (int, optional): Maximum number of retries for failed processes. Defaults to 1.
            
        Returns:
            str: Result of the recovery operation.
        """
        if not self.active:
            return f"Process Scheduler {self.name} is not active"
        failed_processes = [p for p in self.processes if p.status == "failed"]
        if not failed_processes:
            return f"No failed processes to recover in scheduler {self.name}"
        
        retry_count = 0
        for process in failed_processes:
            if retry_count >= max_retries:
                break
            if len(self.running_processes) >= self.max_concurrent:
                break
            self.running_processes.append(process)
            try:
                result = process.retry_failed_tasks(max_retries=1)
                if "successfully" in result:
                    retry_count += 1
                    process.status = "completed"
                    self.performance_metrics["total_executions"] += 1
            except ProcessError as e:
                process.error_log.append(f"Recovery failed: {str(e)}")
            finally:
                if process in self.running_processes:
                    self.running_processes.remove(process)
        
        self._update_performance_metrics()
        self.last_updated = time.time()
        return f"Recovered {retry_count} failed processes in scheduler {self.name}"
