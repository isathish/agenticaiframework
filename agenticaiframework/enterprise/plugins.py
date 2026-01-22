"""
Enterprise Plugin System - Extensible plugin architecture.

Enables modular extension of the framework through plugins
that can add new agents, tools, workflows, and more.

Features:
- Plugin discovery and loading
- Plugin lifecycle management
- Plugin dependencies
- Hot reload support
- Plugin marketplace
"""

import asyncio
import importlib
import importlib.util
import inspect
import logging
import os
import sys
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

logger = logging.getLogger(__name__)

T = TypeVar("T")


# =============================================================================
# Plugin Status
# =============================================================================

class PluginStatus(Enum):
    """Plugin status states."""
    DISCOVERED = "discovered"
    LOADED = "loaded"
    INITIALIZED = "initialized"
    ACTIVE = "active"
    DISABLED = "disabled"
    FAILED = "failed"
    UNLOADED = "unloaded"


# =============================================================================
# Plugin Metadata
# =============================================================================

@dataclass
class PluginMetadata:
    """Plugin metadata and configuration."""
    name: str
    version: str
    description: str = ""
    author: str = ""
    email: str = ""
    url: str = ""
    license: str = ""
    
    # Dependencies
    dependencies: List[str] = field(default_factory=list)
    python_requires: str = ">=3.9"
    
    # Configuration
    config_schema: Optional[Dict] = None
    default_config: Dict = field(default_factory=dict)
    
    # Capabilities
    provides_agents: bool = False
    provides_tools: bool = False
    provides_workflows: bool = False
    provides_adapters: bool = False
    provides_middleware: bool = False
    
    # Tags for discovery
    tags: List[str] = field(default_factory=list)


# =============================================================================
# Plugin Base Class
# =============================================================================

class Plugin(ABC):
    """
    Base class for all plugins.
    
    Usage:
        >>> class MyPlugin(Plugin):
        ...     metadata = PluginMetadata(
        ...         name="my-plugin",
        ...         version="1.0.0",
        ...         description="A sample plugin",
        ...     )
        ...     
        ...     async def initialize(self, config: Dict):
        ...         self.config = config
        ...     
        ...     async def activate(self):
        ...         # Register agents, tools, etc.
        ...         pass
        ...     
        ...     async def deactivate(self):
        ...         # Cleanup
        ...         pass
    """
    
    metadata: PluginMetadata
    status: PluginStatus = PluginStatus.DISCOVERED
    config: Dict = {}
    
    @abstractmethod
    async def initialize(self, config: Dict[str, Any]):
        """Initialize the plugin with configuration."""
        pass
    
    @abstractmethod
    async def activate(self):
        """Activate the plugin and register components."""
        pass
    
    @abstractmethod
    async def deactivate(self):
        """Deactivate and cleanup the plugin."""
        pass
    
    def get_agents(self) -> List[Type]:
        """Get agents provided by this plugin."""
        return []
    
    def get_tools(self) -> List[Type]:
        """Get tools provided by this plugin."""
        return []
    
    def get_workflows(self) -> List[Type]:
        """Get workflows provided by this plugin."""
        return []
    
    def get_middleware(self) -> List[Type]:
        """Get middleware provided by this plugin."""
        return []


# =============================================================================
# Plugin Registry
# =============================================================================

@dataclass
class PluginInfo:
    """Information about a registered plugin."""
    plugin: Plugin
    module: Any
    path: Optional[Path]
    status: PluginStatus = PluginStatus.DISCOVERED
    loaded_at: Optional[datetime] = None
    error: Optional[str] = None


class PluginRegistry:
    """
    Registry for managing plugins.
    
    Usage:
        >>> registry = PluginRegistry()
        >>> registry.discover("./plugins")
        >>> await registry.load_all()
        >>> await registry.activate_all()
    """
    
    def __init__(self):
        self._plugins: Dict[str, PluginInfo] = {}
        self._hooks: Dict[str, List[Callable]] = {}
        self._lock = asyncio.Lock()
    
    def register(self, plugin: Plugin, module: Any = None, path: Path = None):
        """Register a plugin."""
        name = plugin.metadata.name
        
        self._plugins[name] = PluginInfo(
            plugin=plugin,
            module=module,
            path=path,
            status=PluginStatus.DISCOVERED,
        )
        
        logger.info(f"Registered plugin: {name} v{plugin.metadata.version}")
    
    def unregister(self, name: str):
        """Unregister a plugin."""
        if name in self._plugins:
            del self._plugins[name]
            logger.info(f"Unregistered plugin: {name}")
    
    def get(self, name: str) -> Optional[Plugin]:
        """Get a plugin by name."""
        info = self._plugins.get(name)
        return info.plugin if info else None
    
    def get_all(self) -> List[Plugin]:
        """Get all registered plugins."""
        return [info.plugin for info in self._plugins.values()]
    
    def get_by_tag(self, tag: str) -> List[Plugin]:
        """Get plugins by tag."""
        return [
            info.plugin
            for info in self._plugins.values()
            if tag in info.plugin.metadata.tags
        ]
    
    def get_active(self) -> List[Plugin]:
        """Get all active plugins."""
        return [
            info.plugin
            for info in self._plugins.values()
            if info.status == PluginStatus.ACTIVE
        ]
    
    def discover(self, path: str):
        """
        Discover plugins in a directory.
        
        Looks for:
        - Python packages with plugin.py
        - Python files with Plugin subclass
        - plugin.json/plugin.yaml configs
        """
        plugin_path = Path(path)
        
        if not plugin_path.exists():
            logger.warning(f"Plugin path does not exist: {path}")
            return
        
        # Add to Python path
        if str(plugin_path) not in sys.path:
            sys.path.insert(0, str(plugin_path))
        
        for item in plugin_path.iterdir():
            try:
                if item.is_dir():
                    self._discover_package(item)
                elif item.suffix == ".py":
                    self._discover_file(item)
            except Exception as e:
                logger.error(f"Error discovering plugin {item}: {e}")
    
    def _discover_package(self, path: Path):
        """Discover plugin from package directory."""
        plugin_file = path / "plugin.py"
        init_file = path / "__init__.py"
        
        target = plugin_file if plugin_file.exists() else init_file
        
        if target.exists():
            self._load_plugin_from_file(target, path)
    
    def _discover_file(self, path: Path):
        """Discover plugin from single file."""
        if path.name.startswith("_"):
            return
        
        self._load_plugin_from_file(path, path.parent)
    
    def _load_plugin_from_file(self, path: Path, plugin_path: Path):
        """Load a plugin from a Python file."""
        spec = importlib.util.spec_from_file_location(
            path.stem,
            path,
        )
        
        if not spec or not spec.loader:
            return
        
        module = importlib.util.module_from_spec(spec)
        
        try:
            spec.loader.exec_module(module)
        except Exception as e:
            logger.error(f"Error loading module {path}: {e}")
            return
        
        # Find Plugin subclasses
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, Plugin) and obj is not Plugin:
                try:
                    plugin = obj()
                    self.register(plugin, module, plugin_path)
                except Exception as e:
                    logger.error(f"Error instantiating plugin {name}: {e}")
    
    async def load(self, name: str, config: Dict = None):
        """Load and initialize a specific plugin."""
        info = self._plugins.get(name)
        
        if not info:
            raise PluginError(f"Plugin not found: {name}")
        
        if info.status in (PluginStatus.LOADED, PluginStatus.ACTIVE):
            return
        
        # Check dependencies
        for dep in info.plugin.metadata.dependencies:
            if dep not in self._plugins:
                raise PluginError(f"Missing dependency: {dep}")
            
            dep_info = self._plugins[dep]
            if dep_info.status not in (PluginStatus.LOADED, PluginStatus.ACTIVE):
                await self.load(dep, config)
        
        try:
            # Merge config with defaults
            plugin_config = {
                **info.plugin.metadata.default_config,
                **(config or {}),
            }
            
            await info.plugin.initialize(plugin_config)
            info.status = PluginStatus.LOADED
            info.loaded_at = datetime.now()
            
            logger.info(f"Loaded plugin: {name}")
            
        except Exception as e:
            info.status = PluginStatus.FAILED
            info.error = str(e)
            raise PluginError(f"Failed to load plugin {name}: {e}")
    
    async def load_all(self, config: Dict = None):
        """Load all discovered plugins."""
        for name in list(self._plugins.keys()):
            try:
                await self.load(name, config)
            except PluginError as e:
                logger.error(f"Error loading plugin: {e}")
    
    async def activate(self, name: str):
        """Activate a loaded plugin."""
        info = self._plugins.get(name)
        
        if not info:
            raise PluginError(f"Plugin not found: {name}")
        
        if info.status == PluginStatus.ACTIVE:
            return
        
        if info.status != PluginStatus.LOADED:
            raise PluginError(f"Plugin not loaded: {name}")
        
        try:
            await info.plugin.activate()
            info.status = PluginStatus.ACTIVE
            
            # Trigger hooks
            await self._trigger_hook("plugin.activated", info.plugin)
            
            logger.info(f"Activated plugin: {name}")
            
        except Exception as e:
            info.status = PluginStatus.FAILED
            info.error = str(e)
            raise PluginError(f"Failed to activate plugin {name}: {e}")
    
    async def activate_all(self):
        """Activate all loaded plugins."""
        for name, info in self._plugins.items():
            if info.status == PluginStatus.LOADED:
                try:
                    await self.activate(name)
                except PluginError as e:
                    logger.error(f"Error activating plugin: {e}")
    
    async def deactivate(self, name: str):
        """Deactivate an active plugin."""
        info = self._plugins.get(name)
        
        if not info:
            raise PluginError(f"Plugin not found: {name}")
        
        if info.status != PluginStatus.ACTIVE:
            return
        
        try:
            await info.plugin.deactivate()
            info.status = PluginStatus.LOADED
            
            await self._trigger_hook("plugin.deactivated", info.plugin)
            
            logger.info(f"Deactivated plugin: {name}")
            
        except Exception as e:
            info.error = str(e)
            raise PluginError(f"Failed to deactivate plugin {name}: {e}")
    
    async def deactivate_all(self):
        """Deactivate all active plugins."""
        for name, info in self._plugins.items():
            if info.status == PluginStatus.ACTIVE:
                try:
                    await self.deactivate(name)
                except PluginError as e:
                    logger.error(f"Error deactivating plugin: {e}")
    
    async def reload(self, name: str):
        """Hot reload a plugin."""
        info = self._plugins.get(name)
        
        if not info:
            raise PluginError(f"Plugin not found: {name}")
        
        was_active = info.status == PluginStatus.ACTIVE
        config = info.plugin.config
        
        # Deactivate if active
        if was_active:
            await self.deactivate(name)
        
        # Reload module
        if info.module:
            importlib.reload(info.module)
            
            # Re-find plugin class
            for obj_name, obj in inspect.getmembers(info.module, inspect.isclass):
                if issubclass(obj, Plugin) and obj is not Plugin:
                    info.plugin = obj()
                    break
        
        # Re-load and activate
        await self.load(name, config)
        
        if was_active:
            await self.activate(name)
        
        logger.info(f"Reloaded plugin: {name}")
    
    def on_hook(self, hook_name: str):
        """Decorator to register a plugin hook."""
        def decorator(fn: Callable):
            if hook_name not in self._hooks:
                self._hooks[hook_name] = []
            self._hooks[hook_name].append(fn)
            return fn
        return decorator
    
    async def _trigger_hook(self, hook_name: str, *args, **kwargs):
        """Trigger all handlers for a hook."""
        handlers = self._hooks.get(hook_name, [])
        
        for handler in handlers:
            try:
                result = handler(*args, **kwargs)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Hook handler error: {e}")


# =============================================================================
# Plugin Loader
# =============================================================================

class PluginLoader:
    """
    Loads plugins from various sources.
    
    Supports:
    - Local directories
    - Git repositories
    - PyPI packages
    - URLs
    """
    
    def __init__(self, registry: PluginRegistry):
        self.registry = registry
        self.cache_dir = Path.home() / ".agenticai" / "plugins"
    
    async def load_from_path(self, path: str):
        """Load plugins from a local path."""
        self.registry.discover(path)
    
    async def load_from_git(self, url: str, ref: str = "main"):
        """Load plugins from a git repository."""
        import subprocess
        
        # Create cache directory
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Clone or update repo
        repo_name = url.split("/")[-1].replace(".git", "")
        repo_path = self.cache_dir / repo_name
        
        if repo_path.exists():
            subprocess.run(
                ["git", "-C", str(repo_path), "pull"],
                check=True,
            )
        else:
            subprocess.run(
                ["git", "clone", url, str(repo_path)],
                check=True,
            )
        
        subprocess.run(
            ["git", "-C", str(repo_path), "checkout", ref],
            check=True,
        )
        
        self.registry.discover(str(repo_path))
    
    async def load_from_pip(self, package: str):
        """Load plugins from a pip package."""
        import subprocess
        
        # Install package
        subprocess.run(
            [sys.executable, "-m", "pip", "install", package],
            check=True,
        )
        
        # Try to import and discover plugins
        try:
            module = importlib.import_module(package)
            module_path = Path(module.__file__).parent
            self.registry.discover(str(module_path))
        except ImportError as e:
            raise PluginError(f"Failed to import package: {e}")


# =============================================================================
# Plugin Manager
# =============================================================================

class PluginManager:
    """
    High-level plugin management.
    
    Usage:
        >>> manager = PluginManager()
        >>> 
        >>> # Load plugins
        >>> await manager.load_from("./plugins")
        >>> await manager.load_from("https://github.com/user/plugin.git")
        >>> 
        >>> # Activate all
        >>> await manager.activate_all()
        >>> 
        >>> # Get components
        >>> agents = manager.get_all_agents()
        >>> tools = manager.get_all_tools()
    """
    
    def __init__(self, config: Dict = None):
        self.registry = PluginRegistry()
        self.loader = PluginLoader(self.registry)
        self.config = config or {}
    
    async def load_from(self, source: str, **kwargs):
        """Load plugins from any source."""
        if source.startswith("http") or source.endswith(".git"):
            await self.loader.load_from_git(source, **kwargs)
        elif "==" in source or source.startswith("pip:"):
            package = source.replace("pip:", "")
            await self.loader.load_from_pip(package)
        else:
            await self.loader.load_from_path(source)
        
        # Load discovered plugins
        await self.registry.load_all(self.config)
    
    async def activate_all(self):
        """Activate all loaded plugins."""
        await self.registry.activate_all()
    
    async def deactivate_all(self):
        """Deactivate all plugins."""
        await self.registry.deactivate_all()
    
    def get_all_agents(self) -> List[Type]:
        """Get all agents from active plugins."""
        agents = []
        for plugin in self.registry.get_active():
            agents.extend(plugin.get_agents())
        return agents
    
    def get_all_tools(self) -> List[Type]:
        """Get all tools from active plugins."""
        tools = []
        for plugin in self.registry.get_active():
            tools.extend(plugin.get_tools())
        return tools
    
    def get_all_workflows(self) -> List[Type]:
        """Get all workflows from active plugins."""
        workflows = []
        for plugin in self.registry.get_active():
            workflows.extend(plugin.get_workflows())
        return workflows
    
    def get_all_middleware(self) -> List[Type]:
        """Get all middleware from active plugins."""
        middleware = []
        for plugin in self.registry.get_active():
            middleware.extend(plugin.get_middleware())
        return middleware


# =============================================================================
# Decorators
# =============================================================================

def plugin(
    name: str,
    version: str,
    description: str = "",
    **kwargs,
):
    """
    Decorator to create a simple plugin.
    
    Usage:
        >>> @plugin("my-plugin", "1.0.0", description="A plugin")
        ... class MyPlugin:
        ...     def activate(self):
        ...         pass
    """
    def decorator(cls):
        # Create metadata
        metadata = PluginMetadata(
            name=name,
            version=version,
            description=description,
            **kwargs,
        )
        
        # Create plugin class
        class WrappedPlugin(Plugin):
            metadata = metadata
            
            def __init__(self):
                self._impl = cls()
            
            async def initialize(self, config):
                self.config = config
                if hasattr(self._impl, "initialize"):
                    result = self._impl.initialize(config)
                    if asyncio.iscoroutine(result):
                        await result
            
            async def activate(self):
                if hasattr(self._impl, "activate"):
                    result = self._impl.activate()
                    if asyncio.iscoroutine(result):
                        await result
            
            async def deactivate(self):
                if hasattr(self._impl, "deactivate"):
                    result = self._impl.deactivate()
                    if asyncio.iscoroutine(result):
                        await result
            
            def get_agents(self):
                if hasattr(self._impl, "get_agents"):
                    return self._impl.get_agents()
                return []
            
            def get_tools(self):
                if hasattr(self._impl, "get_tools"):
                    return self._impl.get_tools()
                return []
        
        # Auto-register
        global_plugin_registry.register(WrappedPlugin())
        
        return cls
    return decorator


# =============================================================================
# Global Registry
# =============================================================================

global_plugin_registry = PluginRegistry()


def get_plugin_registry() -> PluginRegistry:
    """Get the global plugin registry."""
    return global_plugin_registry


def register_plugin(plugin: Plugin):
    """Register a plugin in the global registry."""
    global_plugin_registry.register(plugin)


def get_plugin(name: str) -> Optional[Plugin]:
    """Get a plugin by name."""
    return global_plugin_registry.get(name)


# =============================================================================
# Errors
# =============================================================================

class PluginError(Exception):
    """Plugin-related error."""
    pass
