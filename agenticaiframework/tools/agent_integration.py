"""
Agent-Tool Integration.

Provides seamless integration between agents and tools:
- Tool binding to agents
- Tool capability discovery
- MCP protocol compatibility
"""

import logging
from typing import Dict, List, Optional, Any, Set, TYPE_CHECKING
from dataclasses import dataclass, field

from .base import BaseTool, ToolResult, ToolConfig, ToolStatus
from .registry import ToolRegistry, tool_registry, ToolCategory, ToolMetadata
from .executor import ToolExecutor, tool_executor, ExecutionContext

if TYPE_CHECKING:
    from ..core.agent import Agent

logger = logging.getLogger(__name__)


@dataclass
class AgentToolBinding:
    """Binding between an agent and its tools."""
    agent_id: str
    agent_name: str
    tools: Set[str] = field(default_factory=set)
    permissions: Set[str] = field(default_factory=set)
    execution_limits: Dict[str, int] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class AgentToolManager:
    """
    Manages tool bindings and execution for agents.
    
    Features:
    - Bind/unbind tools to agents
    - Execute tools on behalf of agents
    - Track tool usage per agent
    - MCP protocol compatibility
    """
    
    def __init__(
        self,
        registry: Optional[ToolRegistry] = None,
        executor: Optional[ToolExecutor] = None,
    ):
        self.registry = registry or tool_registry
        self.executor = executor or tool_executor
        self._bindings: Dict[str, AgentToolBinding] = {}
        self._usage_stats: Dict[str, Dict[str, int]] = {}
    
    def bind_tools(
        self,
        agent: 'Agent',
        tool_names: List[str],
        permissions: Optional[Set[str]] = None,
    ) -> AgentToolBinding:
        """
        Bind tools to an agent.
        
        Args:
            agent: The agent to bind tools to
            tool_names: List of tool names to bind
            permissions: Optional permissions to grant
            
        Returns:
            AgentToolBinding instance
        """
        # Validate tools exist
        valid_tools = set()
        for name in tool_names:
            if self.registry.get_tool_class(name):
                valid_tools.add(name)
            else:
                logger.warning("Tool %s not found, skipping", name)
        
        binding = AgentToolBinding(
            agent_id=agent.id,
            agent_name=agent.name,
            tools=valid_tools,
            permissions=permissions or set(),
        )
        
        self._bindings[agent.id] = binding
        logger.info(
            "Bound %d tools to agent %s",
            len(valid_tools), agent.name
        )
        
        return binding
    
    def unbind_tools(
        self,
        agent: 'Agent',
        tool_names: Optional[List[str]] = None,
    ) -> None:
        """
        Unbind tools from an agent.
        
        Args:
            agent: The agent to unbind from
            tool_names: Specific tools to unbind (None = all)
        """
        if agent.id not in self._bindings:
            return
        
        binding = self._bindings[agent.id]
        
        if tool_names is None:
            binding.tools.clear()
        else:
            binding.tools -= set(tool_names)
        
        logger.info("Unbound tools from agent %s", agent.name)
    
    def bind_category(
        self,
        agent: 'Agent',
        category: ToolCategory,
        permissions: Optional[Set[str]] = None,
    ) -> AgentToolBinding:
        """
        Bind all tools from a category to an agent.
        
        Args:
            agent: The agent to bind tools to
            category: Tool category
            permissions: Optional permissions
            
        Returns:
            AgentToolBinding instance
        """
        tool_names = self.registry.list_tools(category=category)
        return self.bind_tools(agent, tool_names, permissions)
    
    def get_binding(self, agent_id: str) -> Optional[AgentToolBinding]:
        """Get tool binding for an agent."""
        return self._bindings.get(agent_id)
    
    def get_agent_tools(self, agent: 'Agent') -> List[str]:
        """Get list of tools bound to an agent."""
        binding = self._bindings.get(agent.id)
        return list(binding.tools) if binding else []
    
    def can_use_tool(self, agent: 'Agent', tool_name: str) -> bool:
        """Check if an agent can use a specific tool."""
        binding = self._bindings.get(agent.id)
        if not binding:
            return False
        return tool_name in binding.tools
    
    def execute_tool(
        self,
        agent: 'Agent',
        tool_name: str,
        **kwargs
    ) -> ToolResult:
        """
        Execute a tool on behalf of an agent.
        
        Args:
            agent: The agent executing the tool
            tool_name: Name of the tool
            **kwargs: Tool parameters
            
        Returns:
            ToolResult with execution results
        """
        # Check binding
        if not self.can_use_tool(agent, tool_name):
            return ToolResult(
                tool_name=tool_name,
                status=ToolStatus.ERROR,
                error=f"Agent {agent.name} not authorized for tool {tool_name}",
            )
        
        binding = self._bindings[agent.id]
        
        # Create execution context
        context = ExecutionContext(
            agent_id=agent.id,
            agent_name=agent.name,
            permissions=binding.permissions,
        )
        
        # Execute
        result = self.executor.execute(tool_name, context, **kwargs)
        
        # Track usage
        self._track_usage(agent.id, tool_name)
        
        return result
    
    async def execute_tool_async(
        self,
        agent: 'Agent',
        tool_name: str,
        **kwargs
    ) -> ToolResult:
        """Execute a tool asynchronously."""
        if not self.can_use_tool(agent, tool_name):
            return ToolResult(
                tool_name=tool_name,
                status=ToolStatus.ERROR,
                error=f"Agent {agent.name} not authorized for tool {tool_name}",
            )
        
        binding = self._bindings[agent.id]
        context = ExecutionContext(
            agent_id=agent.id,
            agent_name=agent.name,
            permissions=binding.permissions,
        )
        
        result = await self.executor.execute_async(tool_name, context, **kwargs)
        self._track_usage(agent.id, tool_name)
        
        return result
    
    def _track_usage(self, agent_id: str, tool_name: str) -> None:
        """Track tool usage statistics."""
        if agent_id not in self._usage_stats:
            self._usage_stats[agent_id] = {}
        
        if tool_name not in self._usage_stats[agent_id]:
            self._usage_stats[agent_id][tool_name] = 0
        
        self._usage_stats[agent_id][tool_name] += 1
    
    def get_usage_stats(
        self,
        agent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get tool usage statistics."""
        if agent_id:
            return self._usage_stats.get(agent_id, {})
        return self._usage_stats
    
    def discover_tools(
        self,
        agent: 'Agent',
        query: Optional[str] = None,
        category: Optional[ToolCategory] = None,
    ) -> List[Dict[str, Any]]:
        """
        Discover available tools for an agent.
        
        Args:
            agent: The agent discovering tools
            query: Optional search query
            category: Optional category filter
            
        Returns:
            List of tool info dictionaries
        """
        binding = self._bindings.get(agent.id)
        bound_tools = binding.tools if binding else set()
        
        if query:
            tool_names = self.registry.search_tools(query)
        elif category:
            tool_names = self.registry.list_tools(category=category)
        else:
            tool_names = self.registry.list_tools()
        
        result = []
        for name in tool_names:
            metadata = self.registry.get_metadata(name)
            result.append({
                'name': name,
                'description': metadata.description if metadata else '',
                'category': metadata.category.value if metadata else 'custom',
                'bound': name in bound_tools,
                'tags': metadata.tags if metadata else [],
            })
        
        return result
    
    def get_tool_schema(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        Get MCP-compatible schema for a tool.
        
        Returns schema suitable for LLM tool calling.
        """
        metadata = self.registry.get_metadata(tool_name)
        if not metadata:
            return None
        
        return {
            'name': metadata.name,
            'description': metadata.description,
            'parameters': metadata.input_schema or {
                'type': 'object',
                'properties': {},
            },
            'returns': metadata.output_schema or {
                'type': 'object',
            },
        }
    
    def get_all_schemas(self, agent: 'Agent') -> List[Dict[str, Any]]:
        """
        Get MCP-compatible schemas for all agent tools.
        
        Useful for sending to LLMs for function calling.
        """
        tool_names = self.get_agent_tools(agent)
        schemas = []
        
        for name in tool_names:
            schema = self.get_tool_schema(name)
            if schema:
                schemas.append(schema)
        
        return schemas


# Global instance
agent_tool_manager = AgentToolManager()


__all__ = [
    'AgentToolBinding',
    'AgentToolManager',
    'agent_tool_manager',
]
