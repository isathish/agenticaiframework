"""
MCP (Model Context Protocol) tool management.

Thread-safe registry for MCP-compatible tools.
"""

from __future__ import annotations

import logging
import threading
import uuid
from typing import Any, Callable

logger = logging.getLogger(__name__)


class MCPTool:
    """Represents a single MCP tool."""

    __slots__ = ("id", "name", "capability", "execute_fn", "config", "version")

    def __init__(
        self,
        name: str,
        capability: str,
        execute_fn: Callable[..., Any],
        config: dict[str, Any] | None = None,
    ):
        self.id = str(uuid.uuid4())
        self.name = name
        self.capability = capability
        self.execute_fn = execute_fn
        self.config = config or {}
        self.version = "1.0.0"

    def execute(self, *args: Any, **kwargs: Any) -> Any:
        return self.execute_fn(*args, **kwargs)


class MCPToolManager:
    """Thread-safe MCP tool registry."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.tools: dict[str, MCPTool] = {}

    def register_tool(self, tool: MCPTool) -> None:
        with self._lock:
            self.tools[tool.id] = tool
        logger.info("[MCPToolManager] Registered '%s' (id=%s)", tool.name, tool.id)

    def get_tool(self, tool_id: str) -> MCPTool | None:
        with self._lock:
            return self.tools.get(tool_id)

    def list_tools(self) -> list[MCPTool]:
        with self._lock:
            return list(self.tools.values())

    def remove_tool(self, tool_id: str) -> None:
        with self._lock:
            if tool_id in self.tools:
                del self.tools[tool_id]
                logger.info("[MCPToolManager] Removed tool %s", tool_id)

    def execute_tool(self, tool_id: str, *args: Any, **kwargs: Any) -> Any:
        tool = self.get_tool(tool_id)
        if tool:
            logger.info("[MCPToolManager] Executing '%s'", tool.name)
            return tool.execute(*args, **kwargs)
        logger.warning("[MCPToolManager] Tool %s not found", tool_id)
        return None

    def execute_tool_by_name(self, tool_name: str, *args: Any, **kwargs: Any) -> Any:
        """Execute a tool by its name instead of ID."""
        with self._lock:
            tool = next((t for t in self.tools.values() if t.name == tool_name), None)
        if tool:
            logger.info("[MCPToolManager] Executing '%s'", tool.name)
            return tool.execute(*args, **kwargs)
        logger.warning("[MCPToolManager] Tool '%s' not found", tool_name)
        return None
