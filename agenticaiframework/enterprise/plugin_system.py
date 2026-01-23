"""
Enterprise Plugin System Module.

Provides plugin architecture, extension points, plugin discovery,
lifecycle management, and plugin dependencies.

Example:
    # Create plugin manager
    plugins = create_plugin_manager()
    
    # Register plugin
    plugins.register(MyPlugin())
    
    # Load plugins from directory
    await plugins.load_from_directory("./plugins")
    
    # Use decorator
    @plugin(name="my-plugin", version="1.0")
    class MyPlugin:
        async def on_load(self):
            ...
"""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
import inspect
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    Type,
    TypeVar,
)

T = TypeVar('T')


logger = logging.getLogger(__name__)


class PluginError(Exception):
    """Base plugin error."""
    pass


class PluginNotFoundError(PluginError):
    """Plugin not found."""
    pass


class PluginLoadError(PluginError):
    """Plugin load failed."""
    pass


class DependencyError(PluginError):
    """Plugin dependency error."""
    pass


class PluginState(str, Enum):
    """Plugin state."""
    DISCOVERED = "discovered"
    LOADED = "loaded"
    INITIALIZED = "initialized"
    STARTED = "started"
    STOPPED = "stopped"
    UNLOADED = "unloaded"
    FAILED = "failed"


@dataclass
class PluginMetadata:
    """Plugin metadata."""
    name: str
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    dependencies: List[str] = field(default_factory=list)
    provides: List[str] = field(default_factory=list)
    priority: int = 100
    enabled: bool = True
    config_schema: Optional[Dict[str, Any]] = None


@dataclass
class PluginInfo:
    """Plugin information."""
    metadata: PluginMetadata
    state: PluginState
    instance: Optional[Any] = None
    loaded_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    error: Optional[str] = None


@dataclass
class ExtensionPoint:
    """Extension point definition."""
    name: str
    interface: Type
    multiple: bool = True  # Allow multiple implementations
    required: bool = False
    description: str = ""


class Plugin(ABC):
    """
    Abstract plugin base class.
    """
    
    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """Plugin metadata."""
        pass
    
    async def on_load(self) -> None:
        """Called when plugin is loaded."""
        pass
    
    async def on_unload(self) -> None:
        """Called when plugin is unloaded."""
        pass
    
    async def on_start(self) -> None:
        """Called when plugin is started."""
        pass
    
    async def on_stop(self) -> None:
        """Called when plugin is stopped."""
        pass
    
    def configure(self, config: Dict[str, Any]) -> None:
        """Configure the plugin."""
        pass


class SimplePlugin(Plugin):
    """
    Simple plugin implementation.
    """
    
    def __init__(
        self,
        name: str,
        version: str = "1.0.0",
        description: str = "",
        dependencies: Optional[List[str]] = None,
    ):
        self._metadata = PluginMetadata(
            name=name,
            version=version,
            description=description,
            dependencies=dependencies or [],
        )
    
    @property
    def metadata(self) -> PluginMetadata:
        return self._metadata


class ExtensionRegistry:
    """
    Registry for extension points and implementations.
    """
    
    def __init__(self):
        self._points: Dict[str, ExtensionPoint] = {}
        self._implementations: Dict[str, List[Any]] = {}
    
    def register_point(self, point: ExtensionPoint) -> None:
        """Register an extension point."""
        self._points[point.name] = point
        if point.name not in self._implementations:
            self._implementations[point.name] = []
    
    def register_implementation(
        self,
        point_name: str,
        implementation: Any,
    ) -> None:
        """Register an implementation for an extension point."""
        if point_name not in self._implementations:
            self._implementations[point_name] = []
        
        point = self._points.get(point_name)
        if point and not point.multiple:
            self._implementations[point_name] = [implementation]
        else:
            self._implementations[point_name].append(implementation)
    
    def get_implementations(self, point_name: str) -> List[Any]:
        """Get all implementations for an extension point."""
        return self._implementations.get(point_name, [])
    
    def get_implementation(self, point_name: str) -> Optional[Any]:
        """Get first implementation for an extension point."""
        impls = self._implementations.get(point_name, [])
        return impls[0] if impls else None
    
    def get_point(self, name: str) -> Optional[ExtensionPoint]:
        """Get extension point definition."""
        return self._points.get(name)
    
    def validate(self) -> List[str]:
        """Validate all required extension points have implementations."""
        errors = []
        for name, point in self._points.items():
            if point.required and not self._implementations.get(name):
                errors.append(f"Required extension point '{name}' has no implementation")
        return errors


class PluginDiscovery(ABC):
    """
    Abstract plugin discovery.
    """
    
    @abstractmethod
    async def discover(self) -> List[Type[Plugin]]:
        """Discover plugins."""
        pass


class DirectoryPluginDiscovery(PluginDiscovery):
    """
    Discover plugins from directory.
    """
    
    def __init__(
        self,
        directory: str,
        pattern: str = "*.py",
        recursive: bool = True,
    ):
        self._directory = Path(directory)
        self._pattern = pattern
        self._recursive = recursive
    
    async def discover(self) -> List[Type[Plugin]]:
        plugins: List[Type[Plugin]] = []
        
        if not self._directory.exists():
            return plugins
        
        if self._recursive:
            files = list(self._directory.rglob(self._pattern))
        else:
            files = list(self._directory.glob(self._pattern))
        
        for file_path in files:
            if file_path.name.startswith('_'):
                continue
            
            try:
                module_name = file_path.stem
                spec = importlib.util.spec_from_file_location(
                    module_name, file_path
                )
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    # Find Plugin subclasses
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        if issubclass(obj, Plugin) and obj is not Plugin:
                            plugins.append(obj)
                            
            except Exception as e:
                logger.error(f"Failed to load plugin from {file_path}: {e}")
        
        return plugins


class EntryPointPluginDiscovery(PluginDiscovery):
    """
    Discover plugins from entry points.
    """
    
    def __init__(self, group: str = "agenticai.plugins"):
        self._group = group
    
    async def discover(self) -> List[Type[Plugin]]:
        plugins: List[Type[Plugin]] = []
        
        try:
            from importlib.metadata import entry_points
            
            eps = entry_points()
            if hasattr(eps, 'select'):
                # Python 3.10+
                group_eps = eps.select(group=self._group)
            else:
                # Python 3.9
                group_eps = eps.get(self._group, [])
            
            for ep in group_eps:
                try:
                    plugin_class = ep.load()
                    if issubclass(plugin_class, Plugin):
                        plugins.append(plugin_class)
                except Exception as e:
                    logger.error(f"Failed to load entry point {ep.name}: {e}")
                    
        except ImportError:
            pass
        
        return plugins


class PluginManager:
    """
    Plugin manager for loading, managing, and coordinating plugins.
    """
    
    def __init__(self):
        self._plugins: Dict[str, PluginInfo] = {}
        self._extensions = ExtensionRegistry()
        self._discoveries: List[PluginDiscovery] = []
        self._started = False
    
    @property
    def extensions(self) -> ExtensionRegistry:
        return self._extensions
    
    def add_discovery(self, discovery: PluginDiscovery) -> None:
        """Add plugin discovery source."""
        self._discoveries.append(discovery)
    
    def register(self, plugin: Plugin) -> None:
        """Register a plugin instance."""
        name = plugin.metadata.name
        
        if name in self._plugins:
            raise PluginError(f"Plugin already registered: {name}")
        
        self._plugins[name] = PluginInfo(
            metadata=plugin.metadata,
            state=PluginState.LOADED,
            instance=plugin,
            loaded_at=datetime.utcnow(),
        )
    
    def register_class(self, plugin_class: Type[Plugin]) -> None:
        """Register a plugin class."""
        try:
            instance = plugin_class()
            self.register(instance)
        except Exception as e:
            raise PluginLoadError(f"Failed to instantiate plugin: {e}")
    
    async def discover(self) -> List[str]:
        """Discover and register plugins."""
        discovered = []
        
        for discovery in self._discoveries:
            plugin_classes = await discovery.discover()
            
            for plugin_class in plugin_classes:
                try:
                    instance = plugin_class()
                    name = instance.metadata.name
                    
                    if name not in self._plugins:
                        self._plugins[name] = PluginInfo(
                            metadata=instance.metadata,
                            state=PluginState.DISCOVERED,
                            instance=instance,
                        )
                        discovered.append(name)
                        
                except Exception as e:
                    logger.error(f"Failed to instantiate plugin: {e}")
        
        return discovered
    
    async def load_all(self) -> None:
        """Load all discovered plugins."""
        # Sort by priority and dependencies
        sorted_plugins = self._resolve_order()
        
        for name in sorted_plugins:
            await self.load(name)
    
    async def load(self, name: str) -> None:
        """Load a specific plugin."""
        info = self._plugins.get(name)
        if not info:
            raise PluginNotFoundError(f"Plugin not found: {name}")
        
        if info.state not in (PluginState.DISCOVERED, PluginState.UNLOADED):
            return
        
        # Check dependencies
        for dep in info.metadata.dependencies:
            if dep not in self._plugins:
                raise DependencyError(f"Missing dependency: {dep}")
            
            dep_info = self._plugins[dep]
            if dep_info.state not in (PluginState.LOADED, PluginState.STARTED):
                await self.load(dep)
        
        try:
            if info.instance:
                await info.instance.on_load()
            
            info.state = PluginState.LOADED
            info.loaded_at = datetime.utcnow()
            
            logger.info(f"Loaded plugin: {name}")
            
        except Exception as e:
            info.state = PluginState.FAILED
            info.error = str(e)
            raise PluginLoadError(f"Failed to load plugin {name}: {e}")
    
    async def unload(self, name: str) -> None:
        """Unload a plugin."""
        info = self._plugins.get(name)
        if not info:
            raise PluginNotFoundError(f"Plugin not found: {name}")
        
        if info.state == PluginState.STARTED:
            await self.stop(name)
        
        if info.instance:
            await info.instance.on_unload()
        
        info.state = PluginState.UNLOADED
        logger.info(f"Unloaded plugin: {name}")
    
    async def start_all(self) -> None:
        """Start all loaded plugins."""
        self._started = True
        
        sorted_plugins = self._resolve_order()
        
        for name in sorted_plugins:
            info = self._plugins.get(name)
            if info and info.state == PluginState.LOADED:
                await self.start(name)
    
    async def start(self, name: str) -> None:
        """Start a plugin."""
        info = self._plugins.get(name)
        if not info:
            raise PluginNotFoundError(f"Plugin not found: {name}")
        
        if info.state != PluginState.LOADED:
            return
        
        if info.instance:
            await info.instance.on_start()
        
        info.state = PluginState.STARTED
        info.started_at = datetime.utcnow()
        
        logger.info(f"Started plugin: {name}")
    
    async def stop(self, name: str) -> None:
        """Stop a plugin."""
        info = self._plugins.get(name)
        if not info:
            raise PluginNotFoundError(f"Plugin not found: {name}")
        
        if info.state != PluginState.STARTED:
            return
        
        if info.instance:
            await info.instance.on_stop()
        
        info.state = PluginState.STOPPED
        logger.info(f"Stopped plugin: {name}")
    
    async def stop_all(self) -> None:
        """Stop all plugins."""
        self._started = False
        
        # Stop in reverse order
        sorted_plugins = self._resolve_order()
        
        for name in reversed(sorted_plugins):
            info = self._plugins.get(name)
            if info and info.state == PluginState.STARTED:
                await self.stop(name)
    
    def get(self, name: str) -> Optional[Plugin]:
        """Get plugin instance."""
        info = self._plugins.get(name)
        return info.instance if info else None
    
    def get_info(self, name: str) -> Optional[PluginInfo]:
        """Get plugin info."""
        return self._plugins.get(name)
    
    def list_plugins(
        self,
        state: Optional[PluginState] = None,
    ) -> List[PluginInfo]:
        """List all plugins."""
        plugins = list(self._plugins.values())
        
        if state:
            plugins = [p for p in plugins if p.state == state]
        
        return plugins
    
    def _resolve_order(self) -> List[str]:
        """Resolve plugin loading order based on dependencies."""
        # Topological sort
        visited: Set[str] = set()
        order: List[str] = []
        
        def visit(name: str) -> None:
            if name in visited:
                return
            
            visited.add(name)
            info = self._plugins.get(name)
            
            if info:
                for dep in info.metadata.dependencies:
                    if dep in self._plugins:
                        visit(dep)
                
                order.append(name)
        
        # Sort by priority first
        sorted_names = sorted(
            self._plugins.keys(),
            key=lambda n: self._plugins[n].metadata.priority,
        )
        
        for name in sorted_names:
            visit(name)
        
        return order


class PluginContext:
    """
    Context passed to plugins.
    """
    
    def __init__(
        self,
        manager: PluginManager,
        config: Optional[Dict[str, Any]] = None,
    ):
        self._manager = manager
        self._config = config or {}
        self._data: Dict[str, Any] = {}
    
    @property
    def manager(self) -> PluginManager:
        return self._manager
    
    @property
    def extensions(self) -> ExtensionRegistry:
        return self._manager.extensions
    
    @property
    def config(self) -> Dict[str, Any]:
        return self._config
    
    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
    
    def get_plugin(self, name: str) -> Optional[Plugin]:
        return self._manager.get(name)


# Global registry
_global_manager: Optional[PluginManager] = None


# Decorators
def plugin(
    name: str,
    version: str = "1.0.0",
    description: str = "",
    dependencies: Optional[List[str]] = None,
    provides: Optional[List[str]] = None,
    priority: int = 100,
) -> Callable:
    """
    Decorator to define a plugin.
    
    Example:
        @plugin(name="my-plugin", version="1.0")
        class MyPlugin:
            async def on_load(self):
                ...
    """
    def decorator(cls):
        # Add metadata
        original_init = cls.__init__ if hasattr(cls, '__init__') else None
        
        def new_init(self, *args, **kwargs):
            if original_init:
                original_init(self, *args, **kwargs)
            
            self._metadata = PluginMetadata(
                name=name,
                version=version,
                description=description,
                dependencies=dependencies or [],
                provides=provides or [],
                priority=priority,
            )
        
        cls.__init__ = new_init
        
        @property
        def metadata_prop(self) -> PluginMetadata:
            return self._metadata
        
        cls.metadata = metadata_prop
        
        # Add lifecycle methods if not present
        if not hasattr(cls, 'on_load'):
            cls.on_load = lambda self: None
        if not hasattr(cls, 'on_unload'):
            cls.on_unload = lambda self: None
        if not hasattr(cls, 'on_start'):
            cls.on_start = lambda self: None
        if not hasattr(cls, 'on_stop'):
            cls.on_stop = lambda self: None
        
        return cls
    
    return decorator


def extension(point_name: str) -> Callable:
    """
    Decorator to mark class as extension implementation.
    
    Example:
        @extension("storage")
        class FileStorage:
            ...
    """
    def decorator(cls):
        cls._extension_point = point_name
        return cls
    
    return decorator


def provides(*capabilities: str) -> Callable:
    """
    Decorator to declare what a plugin provides.
    
    Example:
        @provides("database", "cache")
        class StoragePlugin(Plugin):
            ...
    """
    def decorator(cls):
        cls._provides = list(capabilities)
        return cls
    
    return decorator


# Factory functions
def create_plugin_manager() -> PluginManager:
    """Create a plugin manager."""
    return PluginManager()


def create_extension_point(
    name: str,
    interface: Type,
    multiple: bool = True,
    required: bool = False,
    description: str = "",
) -> ExtensionPoint:
    """Create an extension point."""
    return ExtensionPoint(
        name=name,
        interface=interface,
        multiple=multiple,
        required=required,
        description=description,
    )


def create_directory_discovery(
    directory: str,
    pattern: str = "*.py",
    recursive: bool = True,
) -> DirectoryPluginDiscovery:
    """Create directory plugin discovery."""
    return DirectoryPluginDiscovery(directory, pattern, recursive)


def create_entrypoint_discovery(
    group: str = "agenticai.plugins",
) -> EntryPointPluginDiscovery:
    """Create entry point plugin discovery."""
    return EntryPointPluginDiscovery(group)


def get_global_manager() -> PluginManager:
    """Get global plugin manager."""
    global _global_manager
    if _global_manager is None:
        _global_manager = create_plugin_manager()
    return _global_manager


__all__ = [
    # Exceptions
    "PluginError",
    "PluginNotFoundError",
    "PluginLoadError",
    "DependencyError",
    # Enums
    "PluginState",
    # Data classes
    "PluginMetadata",
    "PluginInfo",
    "ExtensionPoint",
    # Plugin
    "Plugin",
    "SimplePlugin",
    # Registry
    "ExtensionRegistry",
    # Discovery
    "PluginDiscovery",
    "DirectoryPluginDiscovery",
    "EntryPointPluginDiscovery",
    # Manager
    "PluginManager",
    "PluginContext",
    # Decorators
    "plugin",
    "extension",
    "provides",
    # Factory functions
    "create_plugin_manager",
    "create_extension_point",
    "create_directory_discovery",
    "create_entrypoint_discovery",
    "get_global_manager",
]
