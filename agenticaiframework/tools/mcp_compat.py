"""
MCP (Model Context Protocol) Compatibility Layer.

Provides compatibility with MCP tools and protocols.
"""

import logging
import uuid
import time
from typing import Dict, List, Optional, Any, Callable

from .base import BaseTool, ToolResult, ToolConfig, ToolStatus
from .registry import ToolRegistry, tool_registry

logger = logging.getLogger(__name__)


class MCPToolAdapter:
    """
    Adapter to make BaseTool compatible with MCP protocol.
    
    Wraps BaseTool instances to provide MCP-compatible interface.
    """
    
    def __init__(self, tool: BaseTool):
        self.tool = tool
        self.id = str(uuid.uuid4())
        self.name = tool.name
        self.capability = tool.description
        self.config = tool.config.extra_config
        self.version = tool.config.version
    
    def execute(self, *args, **kwargs) -> Any:
        """Execute with MCP-compatible interface."""
        result = self.tool.execute(**kwargs)
        
        if result.is_success:
            return result.data
        else:
            raise RuntimeError(result.error)
    
    def to_mcp_schema(self) -> Dict[str, Any]:
        """Convert to MCP tool schema."""
        return {
            'name': self.name,
            'description': self.capability,
            'inputSchema': {
                'type': 'object',
                'properties': {},
            },
        }


class MCPBridge:
    """
    Bridge between BaseTool system and MCP protocol.
    
    Features:
    - Convert BaseTools to MCP format
    - Convert MCP tools to BaseTools
    - Protocol translation
    """
    
    def __init__(self, registry: Optional[ToolRegistry] = None):
        self.registry = registry or tool_registry
        self._adapters: Dict[str, MCPToolAdapter] = {}
    
    def create_mcp_tool(self, tool_name: str) -> Optional[MCPToolAdapter]:
        """
        Create an MCP-compatible adapter for a registered tool.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            MCPToolAdapter or None
        """
        tool = self.registry.get_tool(tool_name)
        if tool is None:
            return None
        
        adapter = MCPToolAdapter(tool)
        self._adapters[adapter.id] = adapter
        
        return adapter
    
    def get_mcp_tools(self) -> List[MCPToolAdapter]:
        """Get all MCP-compatible tool adapters."""
        adapters = []
        
        for name in self.registry.list_tools():
            adapter = self.create_mcp_tool(name)
            if adapter:
                adapters.append(adapter)
        
        return adapters
    
    def get_mcp_schemas(self) -> List[Dict[str, Any]]:
        """Get MCP schemas for all registered tools."""
        return [adapter.to_mcp_schema() for adapter in self.get_mcp_tools()]
    
    def execute_mcp_call(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute a tool using MCP call format.
        
        Args:
            tool_name: Name of the tool
            arguments: MCP-formatted arguments
            
        Returns:
            MCP-formatted response
        """
        tool = self.registry.get_tool(tool_name)
        if tool is None:
            return {
                'content': [{'type': 'text', 'text': f'Tool not found: {tool_name}'}],
                'isError': True,
            }
        
        try:
            result = tool.execute(**arguments)
            
            if result.is_success:
                return {
                    'content': [{'type': 'text', 'text': str(result.data)}],
                    'isError': False,
                }
            else:
                return {
                    'content': [{'type': 'text', 'text': result.error}],
                    'isError': True,
                }
                
        except Exception as e:
            return {
                'content': [{'type': 'text', 'text': str(e)}],
                'isError': True,
            }


class LegacyMCPToolWrapper(BaseTool):
    """
    Wrapper to convert legacy MCPTool to BaseTool interface.
    
    Allows using existing MCPTool instances with the new tool system.
    """
    
    def __init__(
        self,
        mcp_tool: Any,  # MCPTool instance
        config: Optional[ToolConfig] = None,
    ):
        self._mcp_tool = mcp_tool
        
        # Create config from MCPTool
        if config is None:
            config = ToolConfig(
                name=mcp_tool.name,
                description=mcp_tool.capability,
                version=getattr(mcp_tool, 'version', '1.0.0'),
            )
        
        super().__init__(config)
    
    def _execute(self, **kwargs) -> Any:
        """Execute the wrapped MCPTool."""
        return self._mcp_tool.execute(**kwargs)


def wrap_mcp_tool(mcp_tool: Any) -> BaseTool:
    """
    Convenience function to wrap an MCPTool.
    
    Args:
        mcp_tool: Legacy MCPTool instance
        
    Returns:
        BaseTool wrapper
    """
    return LegacyMCPToolWrapper(mcp_tool)


def convert_to_mcp(tool: BaseTool) -> MCPToolAdapter:
    """
    Convenience function to convert BaseTool to MCP format.
    
    Args:
        tool: BaseTool instance
        
    Returns:
        MCPToolAdapter instance
    """
    return MCPToolAdapter(tool)


# Global bridge instance
mcp_bridge = MCPBridge()


__all__ = [
    'MCPToolAdapter',
    'MCPBridge',
    'LegacyMCPToolWrapper',
    'wrap_mcp_tool',
    'convert_to_mcp',
    'mcp_bridge',
]
