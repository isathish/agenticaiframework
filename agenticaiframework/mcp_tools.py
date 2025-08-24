from typing import Any, Dict, List, Callable, Optional
import uuid
import time


class MCPTool:
    def __init__(self, name: str, capability: str, execute_fn: Callable, config: Dict[str, Any] = None):
        self.id = str(uuid.uuid4())
        self.name = name
        self.capability = capability
        self.execute_fn = execute_fn
        self.config = config or {}
        self.version = "1.0.0"

    def execute(self, *args, **kwargs):
        return self.execute_fn(*args, **kwargs)


class MCPToolManager:
    def __init__(self):
        self.tools: Dict[str, MCPTool] = {}

    def register_tool(self, tool: MCPTool):
        self.tools[tool.id] = tool
        self._log(f"Registered MCP tool '{tool.name}' with ID {tool.id}")

    def get_tool(self, tool_id: str) -> Optional[MCPTool]:
        return self.tools.get(tool_id)

    def list_tools(self) -> List[MCPTool]:
        return list(self.tools.values())

    def remove_tool(self, tool_id: str):
        if tool_id in self.tools:
            del self.tools[tool_id]
            self._log(f"Removed MCP tool with ID {tool_id}")

    def execute_tool(self, tool_id: str, *args, **kwargs):
        tool = self.get_tool(tool_id)
        if tool:
            self._log(f"Executing MCP tool '{tool.name}'")
            return tool.execute(*args, **kwargs)
        else:
            self._log(f"Tool with ID {tool_id} not found")
            return None

    def _log(self, message: str):
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [MCPToolManager] {message}")
