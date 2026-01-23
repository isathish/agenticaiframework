"""
Enterprise Config Manager Module.

Dynamic configuration, environment variables,
secrets management, and feature toggles.

Example:
    # Create config manager
    config = create_config_manager()
    
    # Load configuration
    await config.load_from_env()
    await config.load_from_file("config.yaml")
    
    # Get values
    db_url = config.get("database.url")
    timeout = config.get_int("api.timeout", default=30)
    
    # Watch for changes
    config.watch("api.enabled", callback=on_config_change)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Callable,
    Coroutine,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    Tuple,
    TypeVar,
    Union,
)

T = TypeVar('T')

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Configuration error."""
    pass


class ConfigNotFound(ConfigError):
    """Configuration not found."""
    pass


class ConfigValidationError(ConfigError):
    """Configuration validation error."""
    pass


class ConfigSource(str, Enum):
    """Configuration source."""
    DEFAULT = "default"
    ENVIRONMENT = "environment"
    FILE = "file"
    REMOTE = "remote"
    RUNTIME = "runtime"


class ConfigFormat(str, Enum):
    """Configuration format."""
    JSON = "json"
    YAML = "yaml"
    INI = "ini"
    ENV = "env"
    TOML = "toml"


@dataclass
class ConfigValue:
    """Configuration value."""
    key: str = ""
    value: Any = None
    source: ConfigSource = ConfigSource.DEFAULT
    format_type: Optional[str] = None
    encrypted: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    version: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConfigSchema:
    """Configuration schema."""
    key: str = ""
    value_type: str = "string"  # string, int, float, bool, list, dict
    required: bool = False
    default: Any = None
    description: str = ""
    validation: Optional[str] = None  # regex pattern
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    allowed_values: Optional[List[Any]] = None
    sensitive: bool = False


@dataclass
class ConfigChange:
    """Configuration change."""
    key: str = ""
    old_value: Any = None
    new_value: Any = None
    source: ConfigSource = ConfigSource.RUNTIME
    changed_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ConfigStats:
    """Configuration statistics."""
    total_keys: int = 0
    env_keys: int = 0
    file_keys: int = 0
    runtime_keys: int = 0
    watchers_count: int = 0


# Config store
class ConfigStore(ABC):
    """Configuration storage backend."""
    
    @abstractmethod
    async def get(self, key: str) -> Optional[ConfigValue]:
        pass
    
    @abstractmethod
    async def set(self, key: str, value: ConfigValue) -> None:
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        pass
    
    @abstractmethod
    async def list_keys(self, prefix: str = "") -> List[str]:
        pass
    
    @abstractmethod
    async def get_all(self) -> Dict[str, ConfigValue]:
        pass


class InMemoryConfigStore(ConfigStore):
    """In-memory configuration store."""
    
    def __init__(self):
        self._values: Dict[str, ConfigValue] = {}
    
    async def get(self, key: str) -> Optional[ConfigValue]:
        return self._values.get(key)
    
    async def set(self, key: str, value: ConfigValue) -> None:
        self._values[key] = value
    
    async def delete(self, key: str) -> bool:
        if key in self._values:
            del self._values[key]
            return True
        return False
    
    async def list_keys(self, prefix: str = "") -> List[str]:
        if not prefix:
            return list(self._values.keys())
        return [k for k in self._values.keys() if k.startswith(prefix)]
    
    async def get_all(self) -> Dict[str, ConfigValue]:
        return dict(self._values)


# Config loader
class ConfigLoader(ABC):
    """Configuration loader."""
    
    @abstractmethod
    async def load(self) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    def get_source(self) -> ConfigSource:
        pass


class EnvConfigLoader(ConfigLoader):
    """Environment variable loader."""
    
    def __init__(
        self,
        prefix: str = "",
        lowercase: bool = True,
        separator: str = "_",
    ):
        self.prefix = prefix
        self.lowercase = lowercase
        self.separator = separator
    
    async def load(self) -> Dict[str, Any]:
        values = {}
        
        for key, value in os.environ.items():
            if self.prefix and not key.startswith(self.prefix):
                continue
            
            # Remove prefix
            config_key = key
            if self.prefix:
                config_key = key[len(self.prefix):].lstrip(self.separator)
            
            # Convert to lowercase
            if self.lowercase:
                config_key = config_key.lower()
            
            # Replace separator with dot
            config_key = config_key.replace(self.separator, ".")
            
            values[config_key] = value
        
        return values
    
    def get_source(self) -> ConfigSource:
        return ConfigSource.ENVIRONMENT


class FileConfigLoader(ConfigLoader):
    """File configuration loader."""
    
    def __init__(
        self,
        path: Union[str, Path],
        format_type: Optional[ConfigFormat] = None,
    ):
        self.path = Path(path)
        self.format_type = format_type or self._detect_format()
    
    def _detect_format(self) -> ConfigFormat:
        """Detect format from extension."""
        ext = self.path.suffix.lower()
        
        if ext in [".json"]:
            return ConfigFormat.JSON
        elif ext in [".yaml", ".yml"]:
            return ConfigFormat.YAML
        elif ext in [".ini", ".cfg"]:
            return ConfigFormat.INI
        elif ext in [".env"]:
            return ConfigFormat.ENV
        elif ext in [".toml"]:
            return ConfigFormat.TOML
        else:
            return ConfigFormat.JSON
    
    def _flatten_dict(
        self,
        data: Dict[str, Any],
        prefix: str = "",
    ) -> Dict[str, Any]:
        """Flatten nested dictionary."""
        result = {}
        
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            
            if isinstance(value, dict):
                result.update(self._flatten_dict(value, full_key))
            else:
                result[full_key] = value
        
        return result
    
    async def load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {}
        
        content = self.path.read_text()
        
        if self.format_type == ConfigFormat.JSON:
            data = json.loads(content)
        elif self.format_type == ConfigFormat.YAML:
            try:
                import yaml
                data = yaml.safe_load(content)
            except ImportError:
                # Simple YAML-like parser
                data = {}
                for line in content.split("\n"):
                    if ":" in line and not line.strip().startswith("#"):
                        key, value = line.split(":", 1)
                        data[key.strip()] = value.strip()
        elif self.format_type == ConfigFormat.ENV:
            data = {}
            for line in content.split("\n"):
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    data[key.strip()] = value.strip().strip("\"'")
        else:
            data = json.loads(content)
        
        return self._flatten_dict(data) if isinstance(data, dict) else {}
    
    def get_source(self) -> ConfigSource:
        return ConfigSource.FILE


# Change callback type
ConfigCallback = Callable[[ConfigChange], Coroutine[Any, Any, None]]


# Config manager
class ConfigManager:
    """Configuration manager."""
    
    def __init__(
        self,
        store: Optional[ConfigStore] = None,
        validate: bool = True,
    ):
        self._store = store or InMemoryConfigStore()
        self._schemas: Dict[str, ConfigSchema] = {}
        self._watchers: Dict[str, List[ConfigCallback]] = {}
        self._validate = validate
        self._loaders: List[ConfigLoader] = []
        self._stats = ConfigStats()
    
    def add_loader(self, loader: ConfigLoader) -> None:
        """Add configuration loader."""
        self._loaders.append(loader)
    
    def add_schema(self, schema: ConfigSchema) -> None:
        """Add configuration schema."""
        self._schemas[schema.key] = schema
    
    def define(
        self,
        key: str,
        value_type: str = "string",
        required: bool = False,
        default: Any = None,
        description: str = "",
        **kwargs,
    ) -> ConfigSchema:
        """Define configuration schema."""
        schema = ConfigSchema(
            key=key,
            value_type=value_type,
            required=required,
            default=default,
            description=description,
            **kwargs,
        )
        
        self._schemas[key] = schema
        
        return schema
    
    def _convert_value(self, value: Any, value_type: str) -> Any:
        """Convert value to type."""
        if value is None:
            return None
        
        if value_type == "string":
            return str(value)
        elif value_type == "int":
            return int(value)
        elif value_type == "float":
            return float(value)
        elif value_type == "bool":
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.lower() in ("true", "yes", "1", "on")
            return bool(value)
        elif value_type == "list":
            if isinstance(value, list):
                return value
            if isinstance(value, str):
                return [v.strip() for v in value.split(",")]
            return [value]
        elif value_type == "dict":
            if isinstance(value, dict):
                return value
            if isinstance(value, str):
                return json.loads(value)
            return {"value": value}
        else:
            return value
    
    def _validate_value(self, key: str, value: Any) -> None:
        """Validate configuration value."""
        schema = self._schemas.get(key)
        if not schema:
            return
        
        # Type conversion
        try:
            value = self._convert_value(value, schema.value_type)
        except (ValueError, TypeError, json.JSONDecodeError) as e:
            raise ConfigValidationError(f"Invalid type for {key}: {e}")
        
        # Required check
        if schema.required and value is None:
            raise ConfigValidationError(f"Required config missing: {key}")
        
        # Min/max check
        if schema.min_value is not None and value is not None:
            if isinstance(value, (int, float)) and value < schema.min_value:
                raise ConfigValidationError(
                    f"Value for {key} is below minimum: {value} < {schema.min_value}"
                )
        
        if schema.max_value is not None and value is not None:
            if isinstance(value, (int, float)) and value > schema.max_value:
                raise ConfigValidationError(
                    f"Value for {key} is above maximum: {value} > {schema.max_value}"
                )
        
        # Allowed values check
        if schema.allowed_values is not None and value is not None:
            if value not in schema.allowed_values:
                raise ConfigValidationError(
                    f"Value for {key} not allowed: {value} not in {schema.allowed_values}"
                )
        
        # Regex validation
        if schema.validation and value is not None:
            if isinstance(value, str) and not re.match(schema.validation, value):
                raise ConfigValidationError(
                    f"Value for {key} doesn't match pattern: {schema.validation}"
                )
    
    async def load_all(self) -> None:
        """Load configuration from all loaders."""
        for loader in self._loaders:
            try:
                values = await loader.load()
                source = loader.get_source()
                
                for key, value in values.items():
                    await self.set(key, value, source=source)
                
                logger.info(f"Loaded {len(values)} config values from {source.value}")
            except Exception as e:
                logger.error(f"Failed to load config: {e}")
    
    async def load_from_env(self, prefix: str = "") -> int:
        """Load configuration from environment."""
        loader = EnvConfigLoader(prefix=prefix)
        values = await loader.load()
        
        for key, value in values.items():
            await self.set(key, value, source=ConfigSource.ENVIRONMENT)
        
        self._stats.env_keys += len(values)
        
        return len(values)
    
    async def load_from_file(
        self,
        path: Union[str, Path],
        format_type: Optional[ConfigFormat] = None,
    ) -> int:
        """Load configuration from file."""
        loader = FileConfigLoader(path, format_type)
        values = await loader.load()
        
        for key, value in values.items():
            await self.set(key, value, source=ConfigSource.FILE)
        
        self._stats.file_keys += len(values)
        
        return len(values)
    
    async def get(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        """Get configuration value."""
        config_value = await self._store.get(key)
        
        if config_value is not None:
            return config_value.value
        
        # Check schema default
        schema = self._schemas.get(key)
        if schema and schema.default is not None:
            return schema.default
        
        return default
    
    def get_sync(self, key: str, default: Any = None) -> Any:
        """Get configuration value synchronously."""
        return asyncio.get_event_loop().run_until_complete(
            self.get(key, default)
        )
    
    async def get_int(self, key: str, default: int = 0) -> int:
        """Get integer configuration value."""
        value = await self.get(key)
        if value is None:
            return default
        return int(value)
    
    async def get_float(self, key: str, default: float = 0.0) -> float:
        """Get float configuration value."""
        value = await self.get(key)
        if value is None:
            return default
        return float(value)
    
    async def get_bool(self, key: str, default: bool = False) -> bool:
        """Get boolean configuration value."""
        value = await self.get(key)
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("true", "yes", "1", "on")
        return bool(value)
    
    async def get_list(self, key: str, default: Optional[List] = None) -> List:
        """Get list configuration value."""
        value = await self.get(key)
        if value is None:
            return default or []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            return [v.strip() for v in value.split(",")]
        return [value]
    
    async def get_dict(self, key: str, default: Optional[Dict] = None) -> Dict:
        """Get dict configuration value."""
        value = await self.get(key)
        if value is None:
            return default or {}
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            return json.loads(value)
        return {"value": value}
    
    async def set(
        self,
        key: str,
        value: Any,
        source: ConfigSource = ConfigSource.RUNTIME,
    ) -> None:
        """Set configuration value."""
        # Validate
        if self._validate:
            self._validate_value(key, value)
        
        # Get old value
        old_config = await self._store.get(key)
        old_value = old_config.value if old_config else None
        
        # Create new value
        config_value = ConfigValue(
            key=key,
            value=value,
            source=source,
            version=(old_config.version + 1) if old_config else 1,
        )
        
        await self._store.set(key, config_value)
        self._stats.total_keys = len(await self._store.list_keys())
        
        if source == ConfigSource.RUNTIME:
            self._stats.runtime_keys += 1
        
        # Notify watchers
        if key in self._watchers and value != old_value:
            change = ConfigChange(
                key=key,
                old_value=old_value,
                new_value=value,
                source=source,
            )
            
            for callback in self._watchers[key]:
                try:
                    await callback(change)
                except Exception as e:
                    logger.error(f"Watcher callback error: {e}")
    
    async def delete(self, key: str) -> bool:
        """Delete configuration value."""
        old_config = await self._store.get(key)
        result = await self._store.delete(key)
        
        if result and key in self._watchers:
            change = ConfigChange(
                key=key,
                old_value=old_config.value if old_config else None,
                new_value=None,
            )
            
            for callback in self._watchers[key]:
                try:
                    await callback(change)
                except Exception as e:
                    logger.error(f"Watcher callback error: {e}")
        
        return result
    
    def watch(
        self,
        key: str,
        callback: ConfigCallback,
    ) -> None:
        """Watch configuration changes."""
        if key not in self._watchers:
            self._watchers[key] = []
        
        self._watchers[key].append(callback)
        self._stats.watchers_count += 1
    
    def unwatch(
        self,
        key: str,
        callback: Optional[ConfigCallback] = None,
    ) -> None:
        """Stop watching configuration changes."""
        if key not in self._watchers:
            return
        
        if callback:
            self._watchers[key] = [c for c in self._watchers[key] if c != callback]
            self._stats.watchers_count -= 1
        else:
            count = len(self._watchers[key])
            del self._watchers[key]
            self._stats.watchers_count -= count
    
    async def list_keys(self, prefix: str = "") -> List[str]:
        """List all configuration keys."""
        return await self._store.list_keys(prefix)
    
    async def get_all(self) -> Dict[str, Any]:
        """Get all configuration values."""
        config_values = await self._store.get_all()
        return {k: v.value for k, v in config_values.items()}
    
    async def export_json(self) -> str:
        """Export configuration as JSON."""
        values = await self.get_all()
        return json.dumps(values, indent=2, default=str)
    
    def get_stats(self) -> ConfigStats:
        """Get statistics."""
        return self._stats


# Factory functions
def create_config_manager(validate: bool = True) -> ConfigManager:
    """Create config manager."""
    return ConfigManager(validate=validate)


def create_config_schema(
    key: str,
    value_type: str = "string",
    **kwargs,
) -> ConfigSchema:
    """Create config schema."""
    return ConfigSchema(key=key, value_type=value_type, **kwargs)


def create_env_loader(
    prefix: str = "",
    **kwargs,
) -> EnvConfigLoader:
    """Create environment loader."""
    return EnvConfigLoader(prefix=prefix, **kwargs)


def create_file_loader(
    path: Union[str, Path],
    **kwargs,
) -> FileConfigLoader:
    """Create file loader."""
    return FileConfigLoader(path, **kwargs)


__all__ = [
    # Exceptions
    "ConfigError",
    "ConfigNotFound",
    "ConfigValidationError",
    # Enums
    "ConfigSource",
    "ConfigFormat",
    # Data classes
    "ConfigValue",
    "ConfigSchema",
    "ConfigChange",
    "ConfigStats",
    # Stores
    "ConfigStore",
    "InMemoryConfigStore",
    # Loaders
    "ConfigLoader",
    "EnvConfigLoader",
    "FileConfigLoader",
    # Manager
    "ConfigManager",
    # Factory functions
    "create_config_manager",
    "create_config_schema",
    "create_env_loader",
    "create_file_loader",
]
