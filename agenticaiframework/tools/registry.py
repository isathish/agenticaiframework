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
