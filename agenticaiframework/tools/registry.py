"""
Tool Registry for managing and discovering tools.

Provides centralized tool management for agents and workflows.
"""

import logging
from typing import Dict, List, Optional, Type, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

from .base import BaseTool, ToolConfig, ToolResult, ToolStatus

logger = logging.getLogger(__name__)


class ToolCategory(Enum):
    """Categories of tools."""
    FILE_DOCUMENT = "file_document"
    WEB_SCRAPING = "web_scraping"
    DATABASE = "database"
    AI_ML = "ai_ml"
    CUSTOM = "custom"


@dataclass
class ToolMetadata:
    """Metadata about a registered tool."""
    name: str
    description: str
    category: ToolCategory
    version: str = "1.0.0"
    author: str = ""
    tags: List[str] = field(default_factory=list)
    required_permissions: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    examples: List[Dict[str, Any]] = field(default_factory=list)


class ToolRegistry:
    """
    Centralized registry for managing tools.
    
    Features:
    - Tool registration and discovery
    - Category-based organization
    - Permission management
    - Tool instantiation
    """
    
    _instance: Optional['ToolRegistry'] = None
    
    def __new__(cls) -> 'ToolRegistry':
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._tools: Dict[str, Type[BaseTool]] = {}
        self._metadata: Dict[str, ToolMetadata] = {}
        self._instances: Dict[str, BaseTool] = {}
        self._hooks: Dict[str, List[Callable]] = {
            'on_register': [],
            'on_execute': [],
            'on_error': [],
        }
        self._initialized = True
        logger.info("ToolRegistry initialized")
    
    def register(
        self,
        tool_class: Type[BaseTool],
        metadata: Optional[ToolMetadata] = None,
        category: ToolCategory = ToolCategory.CUSTOM,
    ) -> None:
        """
        Register a tool class.
        
        Args:
            tool_class: The tool class to register
            metadata: Optional metadata about the tool
            category: Tool category
        """
        name = tool_class.__name__
        
        if name in self._tools:
            logger.warning("Tool %s already registered, overwriting", name)
        
        self._tools[name] = tool_class
        
        # Create metadata if not provided
        if metadata is None:
            metadata = ToolMetadata(
                name=name,
                description=tool_class.__doc__ or "",
                category=category,
            )
        
        self._metadata[name] = metadata
        
        # Run hooks
        for hook in self._hooks.get('on_register', []):
            try:
                hook(name, tool_class, metadata)
            except Exception as e:
                logger.error("Hook error: %s", e)
        
        logger.info("Registered tool: %s", name)
    
    def register_decorator(
        self,
        category: ToolCategory = ToolCategory.CUSTOM,
        **kwargs
    ) -> Callable:
        """
        Decorator for registering tool classes.
        
        Usage:
            @registry.register_decorator(category=ToolCategory.FILE_DOCUMENT)
            class MyTool(BaseTool):
                ...
        """
        def decorator(cls: Type[BaseTool]) -> Type[BaseTool]:
            metadata = ToolMetadata(
                name=cls.__name__,
                description=cls.__doc__ or "",
                category=category,
                **kwargs
            )
            self.register(cls, metadata, category)
            return cls
        return decorator
    
    def get_tool_class(self, name: str) -> Optional[Type[BaseTool]]:
        """Get a registered tool class by name."""
        return self._tools.get(name)
    
    def get_tool(
        self,
        name: str,
        config: Optional[ToolConfig] = None,
        use_cache: bool = True,
    ) -> Optional[BaseTool]:
        """
        Get a tool instance.
        
        Args:
            name: Tool name
            config: Optional configuration
            use_cache: Whether to cache and reuse instances
            
        Returns:
            Tool instance or None
        """
        if use_cache and name in self._instances:
            return self._instances[name]
        
        tool_class = self._tools.get(name)
        if tool_class is None:
            logger.warning("Tool not found: %s", name)
            return None
        
        try:
            instance = tool_class(config) if config else tool_class()
            
            if use_cache:
                self._instances[name] = instance
            
            return instance
        except Exception as e:
            logger.error("Failed to instantiate tool %s: %s", name, e)
            return None
    
    def get_metadata(self, name: str) -> Optional[ToolMetadata]:
        """Get metadata for a registered tool."""
        return self._metadata.get(name)
    
    def list_tools(
        self,
        category: Optional[ToolCategory] = None,
        tags: Optional[List[str]] = None,
    ) -> List[str]:
        """
        List registered tools.
        
        Args:
            category: Filter by category
            tags: Filter by tags (any match)
            
        Returns:
            List of tool names
        """
        result = []
        
        for name, metadata in self._metadata.items():
            if category and metadata.category != category:
                continue
            
            if tags:
                if not any(tag in metadata.tags for tag in tags):
                    continue
            
            result.append(name)
        
        return result
    
    def list_by_category(self) -> Dict[str, List[str]]:
        """List all tools grouped by category."""
        result: Dict[str, List[str]] = {}
        
        for name, metadata in self._metadata.items():
            category = metadata.category.value
            if category not in result:
                result[category] = []
            result[category].append(name)
        
        return result
    
    def search_tools(self, query: str) -> List[str]:
        """
        Search tools by name or description.
        
        Args:
            query: Search query
            
        Returns:
            List of matching tool names
        """
        query = query.lower()
        result = []
        
        for name, metadata in self._metadata.items():
            if (query in name.lower() or 
                query in metadata.description.lower() or
                any(query in tag.lower() for tag in metadata.tags)):
                result.append(name)
        
        return result
    
    def unregister(self, name: str) -> bool:
        """
        Unregister a tool.
        
        Args:
            name: Tool name
            
        Returns:
            True if tool was removed
        """
        if name in self._tools:
            del self._tools[name]
            self._metadata.pop(name, None)
            self._instances.pop(name, None)
            logger.info("Unregistered tool: %s", name)
            return True
        return False
    
    def add_hook(self, event: str, callback: Callable) -> None:
        """Add a hook callback for registry events."""
        if event in self._hooks:
            self._hooks[event].append(callback)
    
    def clear(self) -> None:
        """Clear all registered tools."""
        self._tools.clear()
        self._metadata.clear()
        self._instances.clear()
        logger.info("ToolRegistry cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        return {
            'total_tools': len(self._tools),
            'cached_instances': len(self._instances),
            'by_category': {
                cat.value: len(self.list_tools(category=cat))
                for cat in ToolCategory
            },
        }

    def discover(
        self,
        package: str = "agenticaiframework.tools",
        recursive: bool = True,
        register: bool = True,
    ) -> List[str]:
        """
        Auto-discover and register tools from a package.
        
        Scans the specified package for classes that inherit from BaseTool
        and optionally registers them.
        
        Args:
            package: Package path to scan (e.g., 'agenticaiframework.tools')
            recursive: Scan subpackages recursively
            register: Automatically register discovered tools
            
        Returns:
            List of discovered tool class names
            
        Example:
            >>> # Discover all built-in tools
            >>> tools = tool_registry.discover()
            >>> print(f"Found {len(tools)} tools")
            
            >>> # Discover custom tools package
            >>> tools = tool_registry.discover("myapp.tools")
        """
        import importlib
        import pkgutil
        import inspect
        
        discovered = []
        
        try:
            pkg = importlib.import_module(package)
        except ImportError as e:
            logger.warning("Cannot import package %s: %s", package, e)
            return discovered
        
        # Get package path
        pkg_path = getattr(pkg, '__path__', None)
        if pkg_path is None:
            # Not a package, just a module
            discovered.extend(
                self._discover_from_module(pkg, register)
            )
            return discovered
        
        # Iterate through submodules
        for importer, modname, ispkg in pkgutil.walk_packages(
            pkg_path,
            prefix=package + ".",
            onerror=lambda x: None,
        ):
            if not recursive and ispkg:
                continue
            
            try:
                module = importlib.import_module(modname)
                discovered.extend(
                    self._discover_from_module(module, register)
                )
            except Exception as e:
                logger.debug("Cannot import %s: %s", modname, e)
        
        if discovered:
            logger.info("Discovered %d tools from %s", len(discovered), package)
        
        return discovered
    
    def _discover_from_module(
        self,
        module,
        register: bool = True,
    ) -> List[str]:
        """Discover tools from a module."""
        import inspect
        
        discovered = []
        
        for name, obj in inspect.getmembers(module, inspect.isclass):
            # Check if it's a BaseTool subclass (but not BaseTool itself)
            if (
                issubclass(obj, BaseTool)
                and obj is not BaseTool
                and not getattr(obj, '__abstract__', False)
                and obj.__module__ == module.__name__  # Defined in this module
            ):
                if register and name not in self._tools:
                    try:
                        self.register(obj)
                        discovered.append(name)
                    except Exception as e:
                        logger.debug("Cannot register %s: %s", name, e)
                elif not register:
                    discovered.append(name)
        
        return discovered
    
    def discover_and_bind(
        self,
        agent,
        package: str = "agenticaiframework.tools",
        by_category: Optional[List[ToolCategory]] = None,
        by_tags: Optional[List[str]] = None,
        by_role: Optional[str] = None,
    ) -> List[str]:
        """
        Discover tools and bind to an agent based on criteria.
        
        Args:
            agent: Agent to bind tools to
            package: Package to discover from
            by_category: Filter by categories
            by_tags: Filter by tags
            by_role: Bind tools appropriate for role
            
        Returns:
            List of bound tool names
        """
        from .agent_tools import agent_tool_manager
        
        # Ensure tools are discovered
        self.discover(package)
        
        # Get tools to bind
        tools_to_bind = []
        
        if by_role:
            role_tools = self._get_tools_for_role(by_role)
            tools_to_bind.extend(role_tools)
        
        if by_category:
            for cat in by_category:
                tools_to_bind.extend(self.list_tools(category=cat))
        
        if by_tags:
            tools_to_bind.extend(self.list_tools(tags=by_tags))
        
        # Remove duplicates
        tools_to_bind = list(set(tools_to_bind))
        
        # Bind to agent
        if tools_to_bind:
            agent_tool_manager.bind_tools(agent, tools_to_bind)
        
        return tools_to_bind
    
    def _get_tools_for_role(self, role: str) -> List[str]:
        """Get recommended tools for a role."""
        role_tools = {
            "analyst": ["SQLQueryTool", "DataVisualizationTool", "CSVReadTool"],
            "coder": ["CodeInterpreterTool", "JavaScriptCodeInterpreterTool", "FileReadTool", "FileWriteTool"],
            "researcher": ["WebSearchTool", "PDFReadTool", "WebScraperTool"],
            "assistant": ["CalculatorTool", "WebSearchTool"],
            "writer": ["FileWriteTool", "MarkdownTool"],
            "data_scientist": ["CodeInterpreterTool", "DataVisualizationTool", "SQLQueryTool"],
        }
        
        tools = role_tools.get(role.lower(), [])
        # Filter to only registered tools
        return [t for t in tools if t in self._tools]


# Global registry instance
tool_registry = ToolRegistry()


def register_tool(
    category: ToolCategory = ToolCategory.CUSTOM,
    **kwargs
) -> Callable:
    """
    Decorator for registering tools with the global registry.
    
    Usage:
        @register_tool(category=ToolCategory.FILE_DOCUMENT)
        class MyTool(BaseTool):
            ...
    """
    return tool_registry.register_decorator(category, **kwargs)


__all__ = [
    'ToolCategory',
    'ToolMetadata',
    'ToolRegistry',
    'tool_registry',
    'register_tool',
]
