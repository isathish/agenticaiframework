"""
Agentic Framework MCP Tools Module

This module provides classes and utilities for managing MCP (Model Context Protocol) Tools within the Agentic Framework.
MCP Tools are modular extensions that enhance agent capabilities by providing specialized functions, integrations,
and utilities. They allow agents to interact with external systems, perform domain-specific operations, and extend
their core functionality without modifying the agent's base code.

Key Features:
- MCP Tools Discovery: Identifying and managing available MCP tools.
- Tool Registration: Adding new tools with proper metadata and configuration.
- Tool Invocation: Mechanisms for agents to call tools synchronously or asynchronously.
- Tool Chaining: Combining multiple tools in a sequence or parallel to accomplish complex tasks.
- Tool Configuration: Setting parameters, authentication, and operational constraints.
- Tool Versioning: Managing different versions of tools for testing and upgrades.
- Tool Security: Ensuring safe execution with sandboxing and permission controls.
- Tool Performance Monitoring: Tracking execution time and resource usage.
- Tool Adaptability: Dynamically enabling or reconfiguring tools based on context.
- Tool Integration: Connecting tools with external APIs and services.
"""

from typing import Any, Dict, List, Optional, Callable, Set, Tuple
from datetime import datetime
import time
import threading
import uuid
import json
import os
from abc import ABC, abstractmethod

# Custom exceptions for MCP Tools
class ToolError(Exception):
    """Exception raised for errors related to MCP Tools operations."""
    pass

class ToolInvocationError(ToolError):
    """Exception raised when a tool invocation fails."""
    pass

class ToolRegistrationError(ToolError):
    """Exception raised when tool registration fails."""
    pass

class ToolSecurityError(ToolError):
    """Exception raised for security-related issues in tool operations."""
    pass

class MCPTool(ABC):
    """
    Abstract base class for MCP Tools in the Agentic Framework.
    MCP Tools are modular extensions that provide specialized functionality to agents.
    """
    def __init__(self, name: str, version: str = "1.0.0", description: str = "",
                 config: Optional[Dict[str, Any]] = None):
        """
        Initialize an MCP Tool with basic metadata and configuration.
        
        Args:
            name (str): The name of the tool.
            version (str): The version of the tool (default: "1.0.0").
            description (str): A brief description of the tool's purpose.
            config (Dict[str, Any], optional): Configuration parameters for the tool.
        """
        self.name = name
        self.version = version
        self.description = description
        self.config = config or {}
        self.tool_id = str(uuid.uuid4())
        self.active = False
        self.last_used = 0.0
        self.usage_count = 0
        self.performance_metrics = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "average_execution_time": 0.0
        }
        self.security_settings = {
            "sandbox_enabled": True,
            "permissions": set(),
            "input_validation": True,
            "output_validation": True
        }
        self.lock = threading.Lock()

    @abstractmethod
    def execute(self, input_data: Any, context: Optional[Dict[str, Any]] = None) -> Any:
        """
        Execute the tool's primary function with the provided input data and context.
        
        Args:
            input_data (Any): The input data for the tool to process.
            context (Dict[str, Any], optional): Additional contextual information for execution.
        
        Returns:
            Any: The result of the tool's execution.
        
        Raises:
            ToolInvocationError: If the tool execution fails.
        """
        pass

    def activate(self) -> bool:
        """
        Activate the tool for use.
        
        Returns:
            bool: True if activation was successful, False otherwise.
        """
        with self.lock:
            if not self.active:
                self.active = True
                self.last_used = time.time()
                return True
            return False

    def deactivate(self) -> bool:
        """
        Deactivate the tool to prevent further use.
        
        Returns:
            bool: True if deactivation was successful, False otherwise.
        """
        with self.lock:
            if self.active:
                self.active = False
                return True
            return False

    def update_config(self, new_config: Dict[str, Any]) -> bool:
        """
        Update the tool's configuration parameters.
        
        Args:
            new_config (Dict[str, Any]): The new configuration to apply.
        
        Returns:
            bool: True if the configuration update was successful.
        """
        with self.lock:
            self.config.update(new_config)
            return True

    def set_security_settings(self, settings: Dict[str, Any]) -> bool:
        """
        Update the security settings for the tool.
        
        Args:
            settings (Dict[str, Any]): Security settings to apply.
        
        Returns:
            bool: True if the security settings were updated successfully.
        """
        with self.lock:
            self.security_settings.update(settings)
            return True

    def validate_input(self, input_data: Any) -> bool:
        """
        Validate the input data before execution if input validation is enabled.
        
        Args:
            input_data (Any): The input data to validate.
        
        Returns:
            bool: True if the input is valid, False otherwise.
        """
        if not self.security_settings.get("input_validation", False):
            return True
        # Basic validation logic (can be overridden by subclasses)
        return input_data is not None

    def validate_output(self, output_data: Any) -> bool:
        """
        Validate the output data after execution if output validation is enabled.
        
        Args:
            output_data (Any): The output data to validate.
        
        Returns:
            bool: True if the output is valid, False otherwise.
        """
        if not self.security_settings.get("output_validation", False):
            return True
        # Basic validation logic (can be overridden by subclasses)
        return output_data is not None

    def _update_performance_metrics(self, start_time: float, end_time: float, success: bool) -> None:
        """
        Update performance metrics based on execution results.
        
        Args:
            start_time (float): The start time of the execution.
            end_time (float): The end time of the execution.
            success (bool): Whether the execution was successful.
        """
        with self.lock:
            execution_time = end_time - start_time
            self.performance_metrics["total_executions"] += 1
            if success:
                self.performance_metrics["successful_executions"] += 1
            else:
                self.performance_metrics["failed_executions"] += 1
            total_time = self.performance_metrics["average_execution_time"] * (self.performance_metrics["total_executions"] - 1)
            self.performance_metrics["average_execution_time"] = (total_time + execution_time) / self.performance_metrics["total_executions"]
            self.last_used = end_time
            self.usage_count += 1

    def get_monitoring_data(self) -> Dict[str, Any]:
        """
        Retrieve monitoring data for this tool.
        
        Returns:
            Dict[str, Any]: A dictionary containing monitoring metrics and status.
        """
        return {
            "tool_id": self.tool_id,
            "name": self.name,
            "version": self.version,
            "active": self.active,
            "last_used": datetime.fromtimestamp(self.last_used).isoformat() if self.last_used > 0 else "Never",
            "usage_count": self.usage_count,
            "performance_metrics": self.performance_metrics.copy(),
            "security_settings": self.security_settings.copy()
        }


class SimpleMCPTool(MCPTool):
    """
    A simple implementation of an MCP Tool for basic operations or testing purposes.
    """
    def __init__(self, name: str, version: str = "1.0.0", description: str = "",
                 config: Optional[Dict[str, Any]] = None,
                 operation: Optional[Callable[[Any, Optional[Dict[str, Any]]], Any]] = None):
        """
        Initialize a Simple MCP Tool with an optional custom operation.
        
        Args:
            name (str): The name of the tool.
            version (str): The version of the tool.
            description (str): A brief description of the tool's purpose.
            config (Dict[str, Any], optional): Configuration parameters for the tool.
            operation (Callable, optional): A custom operation to execute.
        """
        super().__init__(name, version, description, config)
        self.operation = operation or (lambda x, ctx: f"Processed {x} by {self.name}")

    def execute(self, input_data: Any, context: Optional[Dict[str, Any]] = None) -> Any:
        """
        Execute the tool's operation with the provided input data.
        
        Args:
            input_data (Any): The input data for the tool to process.
            context (Dict[str, Any], optional): Additional contextual information.
        
        Returns:
            Any: The result of the tool's execution.
        """
        if not self.active:
            raise ToolInvocationError(f"Tool {self.name} is not active")
        if not self.validate_input(input_data):
            raise ToolInvocationError(f"Input validation failed for tool {self.name}")
        start_time = time.time()
        try:
            result = self.operation(input_data, context)
            end_time = time.time()
            if not self.validate_output(result):
                raise ToolInvocationError(f"Output validation failed for tool {self.name}")
            self._update_performance_metrics(start_time, end_time, success=True)
            return result
        except Exception as e:
            end_time = time.time()
            self._update_performance_metrics(start_time, end_time, success=False)
            raise ToolInvocationError(f"Error executing tool {self.name}: {str(e)}")


class MCPToolManager:
    """
    Manages MCP Tools within the Agentic Framework, including discovery, registration,
    invocation, chaining, versioning, security, and performance monitoring.
    """
    def __init__(self, name: str = "MCP Tool Manager", max_concurrent: int = 10):
        """
        Initialize the MCP Tool Manager.
        
        Args:
            name (str): The name of the manager.
            max_concurrent (int): Maximum number of concurrent tool executions.
        """
        self.name = name
        self.max_concurrent = max_concurrent
        self.tools: Dict[str, MCPTool] = {}
        self.tool_versions: Dict[str, List[str]] = {}
        self.running_tools: List[MCPTool] = []
        self.active = False
        self.tool_log: List[str] = []
        self.performance_metrics = {
            "total_tool_executions": 0,
            "successful_tool_executions": 0,
            "failed_tool_executions": 0,
            "average_tool_execution_time": 0.0
        }
        self.last_updated = 0.0
        self.lock = threading.Lock()

    def activate(self) -> bool:
        """
        Activate the MCP Tool Manager.
        
        Returns:
            bool: True if activation was successful.
        """
        with self.lock:
            self.active = True
            self.last_updated = time.time()
            return True

    def deactivate(self) -> bool:
        """
        Deactivate the MCP Tool Manager and all managed tools.
        
        Returns:
            bool: True if deactivation was successful.
        """
        with self.lock:
            for tool in self.tools.values():
                tool.deactivate()
            self.active = False
            self.last_updated = time.time()
            return True

    def register_tool(self, tool: MCPTool, overwrite: bool = False) -> bool:
        """
        Register a new MCP Tool with the manager.
        
        Args:
            tool (MCPTool): The tool to register.
            overwrite (bool): Whether to overwrite an existing tool with the same name and version.
        
        Returns:
            bool: True if registration was successful.
        
        Raises:
            ToolRegistrationError: If registration fails due to conflicts.
        """
        if not self.active:
            raise ToolRegistrationError(f"Tool Manager {self.name} is not active")
        tool_key = f"{tool.name}:{tool.version}"
        with self.lock:
            if tool_key in self.tools and not overwrite:
                raise ToolRegistrationError(f"Tool {tool.name} version {tool.version} already registered in manager {self.name}")
            self.tools[tool_key] = tool
            if tool.name not in self.tool_versions:
                self.tool_versions[tool.name] = []
            if tool.version not in self.tool_versions[tool.name]:
                self.tool_versions[tool.name].append(tool.version)
                self.tool_versions[tool.name].sort()
            self.tool_log.append(f"Tool {tool.name} version {tool.version} registered at {datetime.now().isoformat()}")
            self.last_updated = time.time()
            return True

    def discover_tools(self, criteria: Optional[Dict[str, Any]] = None) -> List[MCPTool]:
        """
        Discover available MCP Tools based on optional criteria.
        
        Args:
            criteria (Dict[str, Any], optional): Criteria to filter tools (e.g., name, version, capabilities).
        
        Returns:
            List[MCPTool]: List of matching MCP Tools.
        """
        if not self.active:
            return []
        with self.lock:
            if not criteria:
                return list(self.tools.values())
            matching_tools = []
            for tool in self.tools.values():
                matches = True
                for key, value in criteria.items():
                    if key == "name" and tool.name != value:
                        matches = False
                    elif key == "version" and tool.version != value:
                        matches = False
                    elif key == "active" and tool.active != value:
                        matches = False
                    # Additional criteria can be added here
                if matches:
                    matching_tools.append(tool)
            return matching_tools

    def invoke_tool(self, tool_name: str, tool_version: Optional[str] = None,
                    input_data: Any = None, context: Optional[Dict[str, Any]] = None,
                    async_mode: bool = False) -> Any:
        """
        Invoke a specific MCP Tool with the provided input data.
        
        Args:
            tool_name (str): The name of the tool to invoke.
            tool_version (str, optional): The version of the tool to use. If None, uses the latest.
            input_data (Any): The input data for the tool.
            context (Dict[str, Any], optional): Additional context for execution.
            async_mode (bool): Whether to execute the tool asynchronously.
        
        Returns:
            Any: The result of the tool's execution.
        
        Raises:
            ToolInvocationError: If the tool invocation fails.
        """
        if not self.active:
            raise ToolInvocationError(f"Tool Manager {self.name} is not active")
        with self.lock:
            if tool_name not in self.tool_versions:
                raise ToolInvocationError(f"Tool {tool_name} not found in manager {self.name}")
            if tool_version is None:
                tool_version = self.tool_versions[tool_name][-1]  # Use latest version
            tool_key = f"{tool_name}:{tool_version}"
            if tool_key not in self.tools:
                raise ToolInvocationError(f"Tool {tool_name} version {tool_version} not found in manager {self.name}")
            tool = self.tools[tool_key]
            if not tool.active:
                tool.activate()
            if len(self.running_tools) >= self.max_concurrent:
                raise ToolInvocationError(f"Concurrency limit reached in manager {self.name} for tool {tool_name}")
            self.running_tools.append(tool)
            start_time = time.time()
            try:
                if async_mode:
                    # Placeholder for async execution (e.g., threading or asyncio)
                    result = tool.execute(input_data, context)
                else:
                    result = tool.execute(input_data, context)
                end_time = time.time()
                self.performance_metrics["total_tool_executions"] += 1
                self.performance_metrics["successful_tool_executions"] += 1
                total_time = self.performance_metrics["average_tool_execution_time"] * (self.performance_metrics["total_tool_executions"] - 1)
                self.performance_metrics["average_tool_execution_time"] = (total_time + (end_time - start_time)) / self.performance_metrics["total_tool_executions"]
                self.tool_log.append(f"Tool {tool_name} version {tool_version} invoked successfully at {datetime.now().isoformat()}")
                return result
            except Exception as e:
                end_time = time.time()
                self.performance_metrics["total_tool_executions"] += 1
                self.performance_metrics["failed_tool_executions"] += 1
                total_time = self.performance_metrics["average_tool_execution_time"] * (self.performance_metrics["total_tool_executions"] - 1)
                self.performance_metrics["average_tool_execution_time"] = (total_time + (end_time - start_time)) / self.performance_metrics["total_tool_executions"]
                self.tool_log.append(f"Tool {tool_name} version {tool_version} invocation failed: {str(e)} at {datetime.now().isoformat()}")
                raise ToolInvocationError(f"Error invoking tool {tool_name} version {tool_version}: {str(e)}")
            finally:
                if tool in self.running_tools:
                    self.running_tools.remove(tool)
                self.last_updated = time.time()

    def chain_tools(self, chain_definition: List[Tuple[str, Optional[str], Dict[str, Any]]],
                    initial_input: Any, context: Optional[Dict[str, Any]] = None,
                    parallel_mode: bool = False) -> List[Any]:
        """
        Execute a chain of MCP Tools in sequence or parallel.
        
        Args:
            chain_definition (List[Tuple[str, Optional[str], Dict[str, Any]]]): List of tuples defining
                the tool name, version (optional), and specific config overrides for each tool in the chain.
            initial_input (Any): The initial input data for the first tool.
            context (Dict[str, Any], optional): Additional context for execution.
            parallel_mode (bool): Whether to execute tools in parallel if possible.
        
        Returns:
            List[Any]: List of results from each tool in the chain.
        """
        if not self.active:
            raise ToolInvocationError(f"Tool Manager {self.name} is not active")
        results = []
        current_input = initial_input
        if parallel_mode:
            # Placeholder for parallel execution logic
            # For now, execute sequentially even if parallel_mode is True
            self.tool_log.append(f"Parallel tool chaining requested but executed sequentially at {datetime.now().isoformat()}")
        for tool_name, tool_version, config_override in chain_definition:
            tool_key = f"{tool_name}:{tool_version if tool_version else self.tool_versions.get(tool_name, ['1.0.0'])[-1]}"
            with self.lock:
                if tool_key not in self.tools:
                    raise ToolInvocationError(f"Tool {tool_name} version {tool_version} not found for chaining in manager {self.name}")
                tool = self.tools[tool_key]
                if config_override:
                    tool.update_config(config_override)
            try:
                result = self.invoke_tool(tool_name, tool_version, current_input, context)
                results.append(result)
                current_input = result  # Output of one tool becomes input for the next in sequence
            except ToolInvocationError as e:
                results.append(f"Error: {str(e)}")
                self.tool_log.append(f"Tool chain interrupted due to error in {tool_name}: {str(e)} at {datetime.now().isoformat()}")
                break
        self.last_updated = time.time()
        return results

    def update_tool_version(self, tool_name: str, old_version: str, new_version: str,
                            new_tool: Optional[MCPTool] = None) -> bool:
        """
        Update the version of an existing tool or register a new tool instance for the new version.
        
        Args:
            tool_name (str): The name of the tool to update.
            old_version (str): The old version to replace or deprecate.
            new_version (str): The new version to introduce.
            new_tool (MCPTool, optional): A new tool instance for the new version. If None, updates metadata only.
        
        Returns:
            bool: True if the version update was successful.
        """
        if not self.active:
            raise ToolRegistrationError(f"Tool Manager {self.name} is not active")
        old_key = f"{tool_name}:{old_version}"
        new_key = f"{tool_name}:{new_version}"
        with self.lock:
            if old_key not in self.tools:
                raise ToolRegistrationError(f"Tool {tool_name} version {old_version} not found in manager {self.name}")
            if new_key in self.tools:
                raise ToolRegistrationError(f"Tool {tool_name} version {new_version} already exists in manager {self.name}")
            if new_tool:
                self.tools[new_key] = new_tool
            else:
                self.tools[new_key] = self.tools[old_key]
                self.tools[new_key].version = new_version
            if new_version not in self.tool_versions[tool_name]:
                self.tool_versions[tool_name].append(new_version)
                self.tool_versions[tool_name].sort()
            self.tool_log.append(f"Tool {tool_name} updated from version {old_version} to {new_version} at {datetime.now().isoformat()}")
            self.last_updated = time.time()
            return True

    def configure_tool(self, tool_name: str, tool_version: Optional[str] = None,
                       config: Dict[str, Any] = None, security_settings: Optional[Dict[str, Any]] = None) -> bool:
        """
        Configure an existing MCP Tool with new settings.
        
        Args:
            tool_name (str): The name of the tool to configure.
            tool_version (str, optional): The version of the tool. If None, uses the latest.
            config (Dict[str, Any]): Configuration parameters to update.
            security_settings (Dict[str, Any], optional): Security settings to update.
        
        Returns:
            bool: True if configuration was successful.
        """
        if not self.active:
            return False
        with self.lock:
            if tool_name not in self.tool_versions:
                return False
            if tool_version is None:
                tool_version = self.tool_versions[tool_name][-1]
            tool_key = f"{tool_name}:{tool_version}"
            if tool_key not in self.tools:
                return False
            tool = self.tools[tool_key]
            if config:
                tool.update_config(config)
            if security_settings:
                tool.set_security_settings(security_settings)
            self.tool_log.append(f"Tool {tool_name} version {tool_version} configured at {datetime.now().isoformat()}")
            self.last_updated = time.time()
            return True

    def adapt_tools(self, context: Dict[str, Any]) -> List[str]:
        """
        Dynamically adapt tool configurations or availability based on context.
        
        Args:
            context (Dict[str, Any]): Contextual data for adaptation (e.g., workload, environment).
        
        Returns:
            List[str]: List of adaptation actions taken.
        """
        if not self.active:
            return [f"Tool Manager {self.name} is not active"]
        actions = []
        with self.lock:
            workload = context.get("workload", "normal")
            for tool in self.tools.values():
                if workload == "high" and tool.active:
                    if tool.performance_metrics.get("average_execution_time", 0.0) > 1.0:  # Arbitrary threshold
                        tool.deactivate()
                        actions.append(f"Deactivated tool {tool.name} due to high workload and slow performance")
                elif workload == "low" and not tool.active:
                    tool.activate()
                    actions.append(f"Activated tool {tool.name} due to low workload")
                # Additional adaptation logic can be added here
            self.tool_log.extend(actions)
            self.last_updated = time.time()
        return actions

    def get_monitoring_data(self) -> Dict[str, Any]:
        """
        Retrieve comprehensive monitoring data for all managed tools.
        
        Returns:
            Dict[str, Any]: A dictionary containing monitoring metrics and status for the manager and tools.
        """
        with self.lock:
            tool_data = [tool.get_monitoring_data() for tool in self.tools.values()]
            return {
                "manager_name": self.name,
                "active": self.active,
                "total_tools": len(self.tools),
                "active_tools": sum(1 for tool in self.tools.values() if tool.active),
                "running_tools": len(self.running_tools),
                "performance_metrics": self.performance_metrics.copy(),
                "last_updated": datetime.fromtimestamp(self.last_updated).isoformat() if self.last_updated > 0 else "Never",
                "tool_log": self.tool_log[-10:],  # Last 10 log entries
                "tools": tool_data
            }


# Example usage and testing
if __name__ == "__main__":
    # Create a tool manager
    tool_manager = MCPToolManager("TestToolManager")
    tool_manager.activate()

    # Create and register some simple tools
    echo_tool = SimpleMCPTool("EchoTool", "1.0.0", "A tool that echoes input")
    transform_tool = SimpleMCPTool("TransformTool", "1.0.0", "A tool that transforms input",
                                   operation=lambda x, ctx: f"Transformed: {x.upper() if isinstance(x, str) else x}")
    tool_manager.register_tool(echo_tool)
    tool_manager.register_tool(transform_tool)

    # Activate tools
    echo_tool.activate()
    transform_tool.activate()

    # Invoke individual tools
    try:
        echo_result = tool_manager.invoke_tool("EchoTool", input_data="Hello, World!")
        print(f"Echo Tool Result: {echo_result}")
    except ToolInvocationError as e:
        print(f"Echo Tool Error: {e}")

    try:
        transform_result = tool_manager.invoke_tool("TransformTool", input_data="Hello, World!")
        print(f"Transform Tool Result: {transform_result}")
    except ToolInvocationError as e:
        print(f"Transform Tool Error: {e}")

    # Chain tools
    chain_def = [
        ("EchoTool", "1.0.0", {}),
        ("TransformTool", "1.0.0", {})
    ]
    try:
        chain_results = tool_manager.chain_tools(chain_def, initial_input="Hello, Chaining!")
        print(f"Chain Results: {chain_results}")
    except ToolInvocationError as e:
        print(f"Chain Error: {e}")

    # Get monitoring data
    monitoring_data = tool_manager.get_monitoring_data()
    print(f"Monitoring Data: {json.dumps(monitoring_data, indent=2)[:500]}... (truncated)")
