"""
Enterprise Config Server Module.

Provides configuration server, feature flags, dynamic config,
config sources, and hot reloading.

Example:
    # Create config server
    config = create_config_server()
    
    # Load from sources
    config.add_source(FileConfigSource("config.yaml"))
    config.add_source(EnvironmentConfigSource())
    
    # Get config values
    db_host = config.get("database.host", default="localhost")
    
    # Feature flags
    if config.is_enabled("new_feature"):
        use_new_feature()
    
    # Watch for changes
    @config.on_change("database.*")
    def handle_db_config_change(key, old, new):
        reconnect_database()
"""

from __future__ import annotations

import asyncio
import functools
import json
import logging
import os
import re
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Pattern,
    Set,
    Tuple,
    TypeVar,
    Union,
)

T = TypeVar('T')


logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Base configuration error."""
    pass


class ConfigNotFoundError(ConfigError):
    """Configuration key not found."""
    pass


class ConfigParseError(ConfigError):
    """Configuration parse error."""
    pass


class ConfigSourceType(str, Enum):
    """Configuration source type."""
    FILE = "file"
    ENVIRONMENT = "environment"
    REMOTE = "remote"
    MEMORY = "memory"


@dataclass
class ConfigValue:
    """Configuration value with metadata."""
    key: str
    value: Any
    source: str
    priority: int = 0
    updated_at: datetime = field(default_factory=datetime.utcnow)
    version: int = 1


@dataclass
class FeatureFlag:
    """Feature flag definition."""
    name: str
    enabled: bool = False
    description: str = ""
    conditions: Dict[str, Any] = field(default_factory=dict)
    percentage: float = 100.0
    variants: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ConfigSnapshot:
    """Configuration snapshot."""
    values: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    source: str = ""


# Type for change handlers
ChangeHandler = Callable[[str, Any, Any], None]


class ConfigSource(ABC):
    """Abstract configuration source."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Source name."""
        pass
    
    @property
    @abstractmethod
    def priority(self) -> int:
        """Source priority (higher = more important)."""
        pass
    
    @abstractmethod
    async def load(self) -> Dict[str, Any]:
        """Load configuration values."""
        pass
    
    async def watch(self, callback: Callable[[], Awaitable[None]]) -> None:
        """Watch for changes (optional)."""
        pass


class FileConfigSource(ConfigSource):
    """File-based configuration source."""
    
    def __init__(
        self,
        path: str,
        priority: int = 100,
        watch: bool = False,
    ):
        self._path = Path(path)
        self._priority = priority
        self._watch = watch
        self._last_modified: Optional[float] = None
    
    @property
    def name(self) -> str:
        return f"file:{self._path}"
    
    @property
    def priority(self) -> int:
        return self._priority
    
    async def load(self) -> Dict[str, Any]:
        if not self._path.exists():
            return {}
        
        content = self._path.read_text()
        self._last_modified = self._path.stat().st_mtime
        
        # Detect format
        if self._path.suffix in ('.yaml', '.yml'):
            try:
                import yaml
                return yaml.safe_load(content) or {}
            except ImportError:
                raise ConfigParseError("PyYAML required for YAML config files")
        
        elif self._path.suffix == '.json':
            return json.loads(content)
        
        elif self._path.suffix in ('.env', '.properties'):
            return self._parse_properties(content)
        
        else:
            # Try JSON first, then properties
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return self._parse_properties(content)
    
    async def watch(self, callback: Callable[[], Awaitable[None]]) -> None:
        if not self._watch:
            return
        
        while True:
            await asyncio.sleep(1)
            
            if self._path.exists():
                mtime = self._path.stat().st_mtime
                if self._last_modified and mtime > self._last_modified:
                    self._last_modified = mtime
                    await callback()
    
    def _parse_properties(self, content: str) -> Dict[str, Any]:
        """Parse properties/env file."""
        result = {}
        for line in content.split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                if '=' in line:
                    key, value = line.split('=', 1)
                    result[key.strip()] = value.strip()
        return result


class EnvironmentConfigSource(ConfigSource):
    """Environment variable configuration source."""
    
    def __init__(
        self,
        prefix: str = "",
        priority: int = 200,
        separator: str = "__",
    ):
        self._prefix = prefix
        self._priority = priority
        self._separator = separator
    
    @property
    def name(self) -> str:
        return f"env:{self._prefix or 'all'}"
    
    @property
    def priority(self) -> int:
        return self._priority
    
    async def load(self) -> Dict[str, Any]:
        result = {}
        
        for key, value in os.environ.items():
            if self._prefix and not key.startswith(self._prefix):
                continue
            
            # Remove prefix
            config_key = key[len(self._prefix):] if self._prefix else key
            
            # Convert separator to dots
            config_key = config_key.replace(self._separator, '.')
            config_key = config_key.lower()
            
            result[config_key] = self._parse_value(value)
        
        return result
    
    def _parse_value(self, value: str) -> Any:
        """Parse string value to appropriate type."""
        # Boolean
        if value.lower() in ('true', 'yes', '1'):
            return True
        if value.lower() in ('false', 'no', '0'):
            return False
        
        # Number
        try:
            if '.' in value:
                return float(value)
            return int(value)
        except ValueError:
            pass
        
        # JSON
        if value.startswith('[') or value.startswith('{'):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                pass
        
        return value


class MemoryConfigSource(ConfigSource):
    """In-memory configuration source."""
    
    def __init__(self, values: Optional[Dict[str, Any]] = None, priority: int = 50):
        self._values = values or {}
        self._priority = priority
    
    @property
    def name(self) -> str:
        return "memory"
    
    @property
    def priority(self) -> int:
        return self._priority
    
    async def load(self) -> Dict[str, Any]:
        return self._values.copy()
    
    def set(self, key: str, value: Any) -> None:
        """Set a value."""
        self._values[key] = value
    
    def delete(self, key: str) -> None:
        """Delete a value."""
        self._values.pop(key, None)


class RemoteConfigSource(ConfigSource):
    """Remote configuration source."""
    
    def __init__(
        self,
        url: str,
        priority: int = 150,
        headers: Optional[Dict[str, str]] = None,
        poll_interval: int = 60,
    ):
        self._url = url
        self._priority = priority
        self._headers = headers or {}
        self._poll_interval = poll_interval
    
    @property
    def name(self) -> str:
        return f"remote:{self._url}"
    
    @property
    def priority(self) -> int:
        return self._priority
    
    async def load(self) -> Dict[str, Any]:
        try:
            import aiohttp
            
            async with aiohttp.ClientSession() as session:
                async with session.get(self._url, headers=self._headers) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.warning(f"Failed to load remote config: {response.status}")
                        return {}
                        
        except ImportError:
            logger.warning("aiohttp required for remote config")
            return {}
        except Exception as e:
            logger.error(f"Error loading remote config: {e}")
            return {}
    
    async def watch(self, callback: Callable[[], Awaitable[None]]) -> None:
        while True:
            await asyncio.sleep(self._poll_interval)
            await callback()


class ConfigServer:
    """
    Configuration server with multiple sources and hot reload.
    """
    
    def __init__(self):
        self._sources: List[ConfigSource] = []
        self._values: Dict[str, ConfigValue] = {}
        self._feature_flags: Dict[str, FeatureFlag] = {}
        self._change_handlers: List[Tuple[Pattern, ChangeHandler]] = []
        self._lock = threading.Lock()
        self._watch_tasks: List[asyncio.Task] = []
        self._loaded = False
    
    def add_source(self, source: ConfigSource) -> None:
        """Add a configuration source."""
        self._sources.append(source)
        # Sort by priority (descending)
        self._sources.sort(key=lambda s: s.priority, reverse=True)
    
    async def load(self) -> None:
        """Load configuration from all sources."""
        all_values: Dict[str, ConfigValue] = {}
        
        # Load from lowest to highest priority
        for source in reversed(self._sources):
            try:
                values = await source.load()
                
                # Flatten nested values
                flattened = self._flatten(values)
                
                for key, value in flattened.items():
                    all_values[key] = ConfigValue(
                        key=key,
                        value=value,
                        source=source.name,
                        priority=source.priority,
                    )
                    
            except Exception as e:
                logger.error(f"Error loading from {source.name}: {e}")
        
        # Detect changes
        with self._lock:
            for key, new_val in all_values.items():
                old_val = self._values.get(key)
                
                if old_val is None or old_val.value != new_val.value:
                    self._notify_change(key, old_val.value if old_val else None, new_val.value)
            
            self._values = all_values
        
        self._loaded = True
        logger.info(f"Loaded {len(all_values)} configuration values")
    
    async def start_watching(self) -> None:
        """Start watching sources for changes."""
        for source in self._sources:
            task = asyncio.create_task(source.watch(self.load))
            self._watch_tasks.append(task)
    
    def stop_watching(self) -> None:
        """Stop watching sources."""
        for task in self._watch_tasks:
            task.cancel()
        self._watch_tasks.clear()
    
    def get(
        self,
        key: str,
        default: T = None,
        type_: Optional[type] = None,
    ) -> T:
        """Get configuration value."""
        with self._lock:
            config_val = self._values.get(key)
            
            if config_val is None:
                return default
            
            value = config_val.value
            
            if type_ and not isinstance(value, type_):
                try:
                    value = type_(value)
                except (ValueError, TypeError):
                    return default
            
            return value
    
    def get_int(self, key: str, default: int = 0) -> int:
        """Get integer configuration value."""
        return self.get(key, default, int)
    
    def get_float(self, key: str, default: float = 0.0) -> float:
        """Get float configuration value."""
        return self.get(key, default, float)
    
    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get boolean configuration value."""
        value = self.get(key, default)
        
        if isinstance(value, bool):
            return value
        
        if isinstance(value, str):
            return value.lower() in ('true', 'yes', '1', 'on')
        
        return bool(value)
    
    def get_list(self, key: str, default: Optional[List] = None) -> List:
        """Get list configuration value."""
        value = self.get(key, default or [])
        
        if isinstance(value, list):
            return value
        
        if isinstance(value, str):
            return [v.strip() for v in value.split(',')]
        
        return [value]
    
    def get_section(self, prefix: str) -> Dict[str, Any]:
        """Get all values under a prefix."""
        result = {}
        prefix_dot = f"{prefix}."
        
        with self._lock:
            for key, config_val in self._values.items():
                if key.startswith(prefix_dot):
                    sub_key = key[len(prefix_dot):]
                    result[sub_key] = config_val.value
                elif key == prefix:
                    return config_val.value
        
        return result
    
    def set(self, key: str, value: Any, source: str = "runtime") -> None:
        """Set a configuration value at runtime."""
        with self._lock:
            old_val = self._values.get(key)
            
            self._values[key] = ConfigValue(
                key=key,
                value=value,
                source=source,
                priority=999,  # Runtime values have highest priority
            )
            
            self._notify_change(key, old_val.value if old_val else None, value)
    
    def on_change(self, pattern: str) -> Callable:
        """Decorator to register change handler."""
        regex = re.compile(pattern.replace('.', '\\.').replace('*', '.*'))
        
        def decorator(func: ChangeHandler) -> ChangeHandler:
            self._change_handlers.append((regex, func))
            return func
        
        return decorator
    
    def add_change_handler(self, pattern: str, handler: ChangeHandler) -> None:
        """Add a change handler."""
        regex = re.compile(pattern.replace('.', '\\.').replace('*', '.*'))
        self._change_handlers.append((regex, handler))
    
    # Feature flags
    def add_feature_flag(
        self,
        name: str,
        enabled: bool = False,
        description: str = "",
        percentage: float = 100.0,
    ) -> FeatureFlag:
        """Add a feature flag."""
        flag = FeatureFlag(
            name=name,
            enabled=enabled,
            description=description,
            percentage=percentage,
        )
        self._feature_flags[name] = flag
        return flag
    
    def is_enabled(
        self,
        name: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Check if feature flag is enabled."""
        # Check config first
        config_key = f"features.{name}"
        config_val = self.get(config_key)
        
        if config_val is not None:
            return self.get_bool(config_key, False)
        
        # Check feature flags
        flag = self._feature_flags.get(name)
        
        if not flag:
            return False
        
        if not flag.enabled:
            return False
        
        # Check percentage rollout
        if flag.percentage < 100.0:
            import random
            if random.random() * 100 > flag.percentage:
                return False
        
        # Check conditions
        if flag.conditions and context:
            for key, expected in flag.conditions.items():
                if context.get(key) != expected:
                    return False
        
        return True
    
    def get_feature_variant(
        self,
        name: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Get feature flag variant."""
        flag = self._feature_flags.get(name)
        
        if not flag or not flag.variants:
            return None
        
        if not self.is_enabled(name, context):
            return None
        
        # Simple random variant selection
        import random
        return random.choice(list(flag.variants.keys()))
    
    def list_feature_flags(self) -> List[FeatureFlag]:
        """List all feature flags."""
        return list(self._feature_flags.values())
    
    def snapshot(self) -> ConfigSnapshot:
        """Create a configuration snapshot."""
        with self._lock:
            values = {k: v.value for k, v in self._values.items()}
        
        return ConfigSnapshot(values=values)
    
    def restore(self, snapshot: ConfigSnapshot) -> None:
        """Restore from a snapshot."""
        with self._lock:
            for key, value in snapshot.values.items():
                self._values[key] = ConfigValue(
                    key=key,
                    value=value,
                    source="snapshot",
                )
    
    def _flatten(
        self,
        data: Dict[str, Any],
        prefix: str = "",
    ) -> Dict[str, Any]:
        """Flatten nested dictionary."""
        result = {}
        
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            
            if isinstance(value, dict):
                result.update(self._flatten(value, full_key))
            else:
                result[full_key] = value
        
        return result
    
    def _notify_change(self, key: str, old_value: Any, new_value: Any) -> None:
        """Notify change handlers."""
        for pattern, handler in self._change_handlers:
            if pattern.match(key):
                try:
                    handler(key, old_value, new_value)
                except Exception as e:
                    logger.error(f"Error in change handler: {e}")


# Global server
_global_server: Optional[ConfigServer] = None


# Decorators
def config_value(
    key: str,
    default: Any = None,
    type_: Optional[type] = None,
) -> Callable:
    """
    Decorator to inject config value as function argument.
    
    Example:
        @config_value("database.host", default="localhost")
        def connect(db_host: str):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            server = get_global_server()
            value = server.get(key, default, type_)
            
            # Get first parameter name
            import inspect
            sig = inspect.signature(func)
            params = list(sig.parameters.keys())
            
            if params and params[0] not in kwargs:
                kwargs[params[0]] = value
            
            return func(*args, **kwargs)
        
        return wrapper
    
    return decorator


def feature_flag(name: str, default: bool = False) -> Callable:
    """
    Decorator to conditionally execute based on feature flag.
    
    Example:
        @feature_flag("new_feature")
        def use_new_feature():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            server = get_global_server()
            
            if server.is_enabled(name):
                return func(*args, **kwargs)
            elif default:
                return func(*args, **kwargs)
            
            return None
        
        return wrapper
    
    return decorator


# Factory functions
def create_config_server() -> ConfigServer:
    """Create a configuration server."""
    return ConfigServer()


def create_file_source(
    path: str,
    priority: int = 100,
    watch: bool = False,
) -> FileConfigSource:
    """Create file configuration source."""
    return FileConfigSource(path, priority, watch)


def create_env_source(
    prefix: str = "",
    priority: int = 200,
) -> EnvironmentConfigSource:
    """Create environment configuration source."""
    return EnvironmentConfigSource(prefix, priority)


def create_memory_source(
    values: Optional[Dict[str, Any]] = None,
    priority: int = 50,
) -> MemoryConfigSource:
    """Create memory configuration source."""
    return MemoryConfigSource(values, priority)


def create_remote_source(
    url: str,
    priority: int = 150,
    headers: Optional[Dict[str, str]] = None,
) -> RemoteConfigSource:
    """Create remote configuration source."""
    return RemoteConfigSource(url, priority, headers)


def create_feature_flag(
    name: str,
    enabled: bool = False,
    percentage: float = 100.0,
) -> FeatureFlag:
    """Create a feature flag."""
    return FeatureFlag(name=name, enabled=enabled, percentage=percentage)


def get_global_server() -> ConfigServer:
    """Get global configuration server."""
    global _global_server
    if _global_server is None:
        _global_server = create_config_server()
    return _global_server


__all__ = [
    # Exceptions
    "ConfigError",
    "ConfigNotFoundError",
    "ConfigParseError",
    # Enums
    "ConfigSourceType",
    # Data classes
    "ConfigValue",
    "FeatureFlag",
    "ConfigSnapshot",
    # Sources
    "ConfigSource",
    "FileConfigSource",
    "EnvironmentConfigSource",
    "MemoryConfigSource",
    "RemoteConfigSource",
    # Server
    "ConfigServer",
    # Decorators
    "config_value",
    "feature_flag",
    # Factory functions
    "create_config_server",
    "create_file_source",
    "create_env_source",
    "create_memory_source",
    "create_remote_source",
    "create_feature_flag",
    "get_global_server",
]
