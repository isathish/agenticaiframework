"""
Agentic Framework Configurations Module

This module provides mechanisms for defining and managing configurations within the Agentic Framework.
It supports fine-grained control over parameters, settings, and operational constraints for each component,
enabling customization to meet specific application requirements. Configurations can be static (set at deployment)
or dynamic (adjusted at runtime), with features for template-based setups, validation, versioning, and environment-specific profiles.
"""

from typing import Any, Dict, List, Optional, Callable, Set
from datetime import datetime
import time
import threading
import json
import os
import copy
import jsonschema
from jsonschema import ValidationError
import yaml
from pathlib import Path

# Custom exceptions for configuration management errors
class ConfigurationError(Exception):
    """Base exception for configuration-related errors."""
    pass

class ConfigurationNotFoundError(ConfigurationError):
    """Raised when a configuration is not found."""
    pass

class ConfigurationValidationError(ConfigurationError):
    """Raised when a configuration fails validation."""
    pass

class ConfigurationAccessDeniedError(ConfigurationError):
    """Raised when access to a configuration is denied due to security policies."""
    pass

# Base class for configuration management
class ConfigurationStore:
    """Base class for managing configurations in the Agentic Framework."""
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.active = False
        self.storage_type = config.get("storage_type", "memory")
        self.storage_path = config.get("storage_path", f"{name.lower()}_configs.json")
        self.security_enabled = config.get("security_enabled", True)
        self.access_control = config.get("access_control", {"read": ["all"], "write": ["all"]})
        self.performance_metrics = {
            "total_loads": 0,
            "successful_loads": 0,
            "failed_loads": 0,
            "total_saves": 0,
            "successful_saves": 0,
            "failed_saves": 0,
            "total_validations": 0,
            "successful_validations": 0,
            "failed_validations": 0,
            "average_load_time_ms": 0.0,
            "average_save_time_ms": 0.0,
            "average_validation_time_ms": 0.0
        }
        self.config_log: List[str] = []
        self.last_updated = time.time()
        self.lock = threading.Lock()
        self.configurations: Dict[str, Dict[str, Any]] = {}
        self.schemas: Dict[str, Dict[str, Any]] = config.get("schemas", {})
        self.environment_profiles = config.get("environment_profiles", {"default": {}})
        self.current_environment = config.get("current_environment", "default")

    def activate(self) -> None:
        """Activate the configuration store, loading configurations from storage if necessary."""
        with self.lock:
            self.active = True
            if self.storage_type == "file":
                self._load_from_file()
            elif self.storage_type == "memory":
                self.configurations = {}
            self.config_log.append(f"Configuration store {self.name} activated with storage type {self.storage_type} at {datetime.now().isoformat()}")
            self.last_updated = time.time()

    def deactivate(self) -> None:
        """Deactivate the configuration store, saving configurations to storage if necessary."""
        with self.lock:
            if self.storage_type == "file":
                self._save_to_file()
            self.active = False
            self.config_log.append(f"Configuration store {self.name} deactivated at {datetime.now().isoformat()}")
            self.last_updated = time.time()

    def _load_from_file(self) -> None:
        """Load configurations from a file."""
        try:
            if os.path.exists(self.storage_path):
                with open(self.storage_path, 'r') as f:
                    self.configurations = json.load(f)
                self.config_log.append(f"Loaded configurations from {self.storage_path} at {datetime.now().isoformat()}")
            else:
                self.configurations = {}
                self.config_log.append(f"No configuration file found at {self.storage_path}, starting with empty configurations at {datetime.now().isoformat()}")
        except Exception as e:
            self.config_log.append(f"Failed to load configurations from {self.storage_path}: {str(e)} at {datetime.now().isoformat()}")
            raise ConfigurationError(f"Error loading configurations from {self.storage_path}: {str(e)}")

    def _save_to_file(self) -> None:
        """Save configurations to a file."""
        try:
            # Ensure the directory exists
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            with open(self.storage_path, 'w') as f:
                json.dump(self.configurations, f, indent=2)
            self.config_log.append(f"Saved configurations to {self.storage_path} at {datetime.now().isoformat()}")
        except Exception as e:
            self.config_log.append(f"Failed to save configurations to {self.storage_path}: {str(e)} at {datetime.now().isoformat()}")
            raise ConfigurationError(f"Error saving configurations to {self.storage_path}: {str(e)}")

    def load_configuration(self, component_type: str, component_name: str, version: Optional[str] = None,
                           environment: Optional[str] = None, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Load a configuration for a specific component, applying environment-specific overrides."""
        if not self.active:
            raise ConfigurationError(f"Configuration store {self.name} is not active")
        role = context.get("role", "default") if context else "default"
        if not self.enforce_security("read", f"{component_type}/{component_name}", role):
            raise ConfigurationAccessDeniedError(f"Read access denied for configuration {component_type}/{component_name}")
        start_time = time.time()
        try:
            config_key = f"{component_type}/{component_name}/{version if version else 'default'}"
            if config_key in self.configurations:
                base_config = copy.deepcopy(self.configurations[config_key])
                env = environment if environment else self.current_environment
                if env in self.environment_profiles:
                    env_overrides = self.environment_profiles[env].get(config_key, {})
                    base_config.update(env_overrides)
                end_time = time.time()
                self.update_performance_metrics("load", start_time, end_time, success=True)
                self.config_log.append(f"Loaded configuration for {config_key} with environment {env} at {datetime.now().isoformat()}")
                return base_config
            else:
                end_time = time.time()
                self.update_performance_metrics("load", start_time, end_time, success=False)
                self.config_log.append(f"Configuration for {config_key} not found at {datetime.now().isoformat()}")
                raise ConfigurationNotFoundError(f"Configuration for {config_key} not found")
        except Exception as e:
            end_time = time.time()
            self.update_performance_metrics("load", start_time, end_time, success=False)
            self.config_log.append(f"Failed to load configuration for {config_key}: {str(e)} at {datetime.now().isoformat()}")
            raise ConfigurationError(f"Error loading configuration for {config_key}: {str(e)}")

    def save_configuration(self, component_type: str, component_name: str, config: Dict[str, Any], version: Optional[str] = None, context: Optional[Dict[str, Any]] = None) -> bool:
        """Save a configuration for a specific component."""
        if not self.active:
            raise ConfigurationError(f"Configuration store {self.name} is not active")
        role = context.get("role", "default") if context else "default"
        if not self.enforce_security("write", f"{component_type}/{component_name}", role):
            raise ConfigurationAccessDeniedError(f"Write access denied for configuration {component_type}/{component_name}")
        start_time = time.time()
        try:
            config_key = f"{component_type}/{component_name}/{version if version else 'default'}"
            with self.lock:
                self.configurations[config_key] = copy.deepcopy(config)
                if self.storage_type == "file":
                    self._save_to_file()
            end_time = time.time()
            self.update_performance_metrics("save", start_time, end_time, success=True)
            self.config_log.append(f"Saved configuration for {config_key} at {datetime.now().isoformat()}")
            return True
        except Exception as e:
            end_time = time.time()
            self.update_performance_metrics("save", start_time, end_time, success=False)
            self.config_log.append(f"Failed to save configuration for {config_key}: {str(e)} at {datetime.now().isoformat()}")
            raise ConfigurationError(f"Error saving configuration for {config_key}: {str(e)}")

    def validate_configuration(self, component_type: str, config: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> bool:
        """Validate a configuration against a schema for the component type."""
        if not self.active:
            raise ConfigurationError(f"Configuration store {self.name} is not active")
        role = context.get("role", "default") if context else "default"
        if not self.enforce_security("read", component_type, role):
            raise ConfigurationAccessDeniedError(f"Read access denied for validating configuration of {component_type}")
        start_time = time.time()
        try:
            if component_type in self.schemas:
                schema = self.schemas[component_type]
                jsonschema.validate(instance=config, schema=schema)
                end_time = time.time()
                self.update_performance_metrics("validation", start_time, end_time, success=True)
                self.config_log.append(f"Validated configuration for {component_type} at {datetime.now().isoformat()}")
                return True
            else:
                # If no schema is defined, consider validation successful
                end_time = time.time()
                self.update_performance_metrics("validation", start_time, end_time, success=True)
                self.config_log.append(f"No schema found for {component_type}, skipping validation at {datetime.now().isoformat()}")
                return True
        except ValidationError as e:
            end_time = time.time()
            self.update_performance_metrics("validation", start_time, end_time, success=False)
            self.config_log.append(f"Validation failed for {component_type}: {str(e)} at {datetime.now().isoformat()}")
            raise ConfigurationValidationError(f"Configuration validation failed for {component_type}: {str(e)}")
        except Exception as e:
            end_time = time.time()
            self.update_performance_metrics("validation", start_time, end_time, success=False)
            self.config_log.append(f"Failed to validate configuration for {component_type}: {str(e)} at {datetime.now().isoformat()}")
            raise ConfigurationError(f"Error validating configuration for {component_type}: {str(e)}")

    def set_environment(self, environment: str) -> None:
        """Set the current environment for configuration overrides."""
        with self.lock:
            self.current_environment = environment
            self.config_log.append(f"Set environment to {environment} at {datetime.now().isoformat()}")
            self.last_updated = time.time()

    def reload_configurations(self) -> None:
        """Reload configurations from storage, useful for dynamic updates without restart."""
        if not self.active:
            raise ConfigurationError(f"Configuration store {self.name} is not active")
        start_time = time.time()
        try:
            with self.lock:
                if self.storage_type == "file":
                    self._load_from_file()
                end_time = time.time()
                self.update_performance_metrics("load", start_time, end_time, success=True)
                self.config_log.append(f"Reloaded configurations at {datetime.now().isoformat()}")
        except Exception as e:
            end_time = time.time()
            self.update_performance_metrics("load", start_time, end_time, success=False)
            self.config_log.append(f"Failed to reload configurations: {str(e)} at {datetime.now().isoformat()}")
            raise ConfigurationError(f"Error reloading configurations: {str(e)}")

    def enforce_security(self, operation: str, resource: str, role: str = "default") -> bool:
        """Enforce security policies for the given operation and resource."""
        if not self.security_enabled:
            return True
        allowed_roles = self.access_control.get(operation, [])
        if "all" in allowed_roles or role in allowed_roles:
            self.config_log.append(f"Security check passed for {operation} on {resource} by role {role} at {datetime.now().isoformat()}")
            return True
        else:
            self.config_log.append(f"Security check failed for {operation} on {resource} by role {role} at {datetime.now().isoformat()}")
            return False

    def update_performance_metrics(self, operation: str, start_time: float, end_time: float, success: bool) -> None:
        """Update performance metrics based on operation result."""
        with self.lock:
            latency = (end_time - start_time) * 1000  # Convert to milliseconds
            if operation == "load":
                self.performance_metrics["total_loads"] += 1
                if success:
                    self.performance_metrics["successful_loads"] += 1
                else:
                    self.performance_metrics["failed_loads"] += 1
                total_time = self.performance_metrics["average_load_time_ms"] * (self.performance_metrics["total_loads"] - 1)
                self.performance_metrics["average_load_time_ms"] = (total_time + latency) / self.performance_metrics["total_loads"]
            elif operation == "save":
                self.performance_metrics["total_saves"] += 1
                if success:
                    self.performance_metrics["successful_saves"] += 1
                else:
                    self.performance_metrics["failed_saves"] += 1
                total_time = self.performance_metrics["average_save_time_ms"] * (self.performance_metrics["total_saves"] - 1)
                self.performance_metrics["average_save_time_ms"] = (total_time + latency) / self.performance_metrics["total_saves"]
            elif operation == "validation":
                self.performance_metrics["total_validations"] += 1
                if success:
                    self.performance_metrics["successful_validations"] += 1
                else:
                    self.performance_metrics["failed_validations"] += 1
                total_time = self.performance_metrics["average_validation_time_ms"] * (self.performance_metrics["total_validations"] - 1)
                self.performance_metrics["average_validation_time_ms"] = (total_time + latency) / self.performance_metrics["total_validations"]
            self.last_updated = time.time()

# Manager class for handling configurations across different component types
class ConfigurationManager:
    """Manages configurations for various component types in the Agentic Framework."""
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.stores: Dict[str, ConfigurationStore] = {}
        self.active = False
        self.lock = threading.Lock()
        self.performance_metrics = {
            "total_config_operations": 0,
            "successful_config_operations": 0,
            "failed_config_operations": 0,
            "average_operation_time_ms": 0.0
        }
        self.operation_log: List[str] = []
        self.last_operation = time.time()
        self.default_store_name = config.get("default_store", "DefaultConfigStore")

    def add_store(self, store: ConfigurationStore) -> None:
        """Add a configuration store to the manager."""
        with self.lock:
            self.stores[store.name] = store
            self.operation_log.append(f"Added configuration store {store.name} to manager {self.name} at {datetime.now().isoformat()}")
            self.last_operation = time.time()

    def remove_store(self, store_name: str) -> None:
        """Remove a configuration store from the manager."""
        with self.lock:
            if store_name in self.stores:
                store = self.stores[store_name]
                if store.active:
                    store.deactivate()
                del self.stores[store_name]
                self.operation_log.append(f"Removed configuration store {store_name} from manager {self.name} at {datetime.now().isoformat()}")
            else:
                self.operation_log.append(f"Configuration store {store_name} not found in manager {self.name} at {datetime.now().isoformat()}")
            self.last_operation = time.time()

    def activate(self) -> None:
        """Activate the configuration manager and all stores."""
        with self.lock:
            self.active = True
            for store_name, store in self.stores.items():
                try:
                    if not store.active:
                        store.activate()
                    self.operation_log.append(f"Activated configuration store {store_name} in manager {self.name} at {datetime.now().isoformat()}")
                except Exception as e:
                    self.operation_log.append(f"Failed to activate configuration store {store_name}: {str(e)} at {datetime.now().isoformat()}")
            self.last_operation = time.time()

    def deactivate(self) -> None:
        """Deactivate the configuration manager and all stores."""
        with self.lock:
            self.active = False
            for store_name, store in self.stores.items():
                try:
                    if store.active:
                        store.deactivate()
                    self.operation_log.append(f"Deactivated configuration store {store_name} in manager {self.name} at {datetime.now().isoformat()}")
                except Exception as e:
                    self.operation_log.append(f"Failed to deactivate configuration store {store_name}: {str(e)} at {datetime.now().isoformat()}")
            self.last_operation = time.time()

    def select_store(self, store_name: Optional[str] = None) -> ConfigurationStore:
        """Select a configuration store, defaulting to the configured default store if not specified."""
        if not self.active:
            raise ConfigurationError(f"Configuration Manager {self.name} is not active")
        with self.lock:
            store_name = store_name if store_name else self.default_store_name
            if store_name not in self.stores:
                raise ConfigurationError(f"Configuration store {store_name} not found in manager {self.name}")
            store = self.stores[store_name]
            if not store.active:
                raise ConfigurationError(f"Configuration store {store_name} is not active in manager {self.name}")
            return store

    def load_component_config(self, component_type: str, component_name: str, version: Optional[str] = None,
                              environment: Optional[str] = None, context: Optional[Dict[str, Any]] = None,
                              store_name: Optional[str] = None) -> Dict[str, Any]:
        """Load configuration for a specific component."""
        if not self.active:
            raise ConfigurationError(f"Configuration Manager {self.name} is not active")
        start_time = time.time()
        try:
            store = self.select_store(store_name)
            result = store.load_configuration(component_type, component_name, version, environment, context)
            end_time = time.time()
            self.performance_metrics["total_config_operations"] += 1
            self.performance_metrics["successful_config_operations"] += 1
            total_time = self.performance_metrics["average_operation_time_ms"] * (self.performance_metrics["total_config_operations"] - 1)
            self.performance_metrics["average_operation_time_ms"] = (total_time + (end_time - start_time) * 1000) / self.performance_metrics["total_config_operations"]
            self.operation_log.append(f"Loaded configuration for {component_type}/{component_name}/{version if version else 'default'} from store {store.name} at {datetime.now().isoformat()}")
            self.last_operation = time.time()
            return result
        except ConfigurationError as e:
            end_time = time.time()
            self.performance_metrics["total_config_operations"] += 1
            self.performance_metrics["failed_config_operations"] += 1
            total_time = self.performance_metrics["average_operation_time_ms"] * (self.performance_metrics["total_config_operations"] - 1)
            self.performance_metrics["average_operation_time_ms"] = (total_time + (end_time - start_time) * 1000) / self.performance_metrics["total_config_operations"]
            self.operation_log.append(f"Failed to load configuration for {component_type}/{component_name}/{version if version else 'default'}: {str(e)} at {datetime.now().isoformat()}")
            raise
        except Exception as e:
            end_time = time.time()
            self.performance_metrics["total_config_operations"] += 1
            self.performance_metrics["failed_config_operations"] += 1
            total_time = self.performance_metrics["average_operation_time_ms"] * (self.performance_metrics["total_config_operations"] - 1)
            self.performance_metrics["average_operation_time_ms"] = (total_time + (end_time - start_time) * 1000) / self.performance_metrics["total_config_operations"]
            self.operation_log.append(f"Unexpected error loading configuration for {component_type}/{component_name}/{version if version else 'default'}: {str(e)} at {datetime.now().isoformat()}")
            raise ConfigurationError(f"Unexpected error in manager {self.name} while loading configuration: {str(e)}")

    def save_component_config(self, component_type: str, component_name: str, config: Dict[str, Any], version: Optional[str] = None, context: Optional[Dict[str, Any]] = None, store_name: Optional[str] = None) -> bool:
        """Save configuration for a specific component."""
        if not self.active:
            raise ConfigurationError(f"Configuration Manager {self.name} is not active")
        start_time = time.time()
        try:
            store = self.select_store(store_name)
            result = store.save_configuration(component_type, component_name, version, config, context)
            end_time = time.time()
            self.performance_metrics["total_config_operations"] += 1
            self.performance_metrics["successful_config_operations"] += 1
            total_time = self.performance_metrics["average_operation_time_ms"] * (self.performance_metrics["total_config_operations"] - 1)
            self.performance_metrics["average_operation_time_ms"] = (total_time + (end_time - start_time) * 1000) / self.performance_metrics["total_config_operations"]
            self.operation_log.append(f"Saved configuration for {component_type}/{component_name}/{version if version else 'default'} to store {store.name} at {datetime.now().isoformat()}")
            self.last_operation = time.time()
            return result
        except ConfigurationError as e:
            end_time = time.time()
            self.performance_metrics["total_config_operations"] += 1
            self.performance_metrics["failed_config_operations"] += 1
            total_time = self.performance_metrics["average_operation_time_ms"] * (self.performance_metrics["total_config_operations"] - 1)
            self.performance_metrics["average_operation_time_ms"] = (total_time + (end_time - start_time) * 1000) / self.performance_metrics["total_config_operations"]
            self.operation_log.append(f"Failed to save configuration for {component_type}/{component_name}/{version if version else 'default'}: {str(e)} at {datetime.now().isoformat()}")
            raise
        except Exception as e:
            end_time = time.time()
            self.performance_metrics["total_config_operations"] += 1
            self.performance_metrics["failed_config_operations"] += 1
            total_time = self.performance_metrics["average_operation_time_ms"] * (self.performance_metrics["total_config_operations"] - 1)
            self.performance_metrics["average_operation_time_ms"] = (total_time + (end_time - start_time) * 1000) / self.performance_metrics["total_config_operations"]
            self.operation_log.append(f"Unexpected error saving configuration for {component_type}/{component_name}/{version if version else 'default'}: {str(e)} at {datetime.now().isoformat()}")
            raise ConfigurationError(f"Unexpected error in manager {self.name} while saving configuration: {str(e)}")

    def validate_component_config(self, component_type: str, config: Dict[str, Any],
                                  context: Optional[Dict[str, Any]] = None,
                                  store_name: Optional[str] = None) -> bool:
        """Validate a configuration for a specific component type."""
        if not self.active:
            raise ConfigurationError(f"Configuration Manager {self.name} is not active")
        start_time = time.time()
        try:
            store = self.select_store(store_name)
            result = store.validate_configuration(component_type, config, context)
            end_time = time.time()
            self.performance_metrics["total_config_operations"] += 1
            self.performance_metrics["successful_config_operations"] += 1
            total_time = self.performance_metrics["average_operation_time_ms"] * (self.performance_metrics["total_config_operations"] - 1)
            self.performance_metrics["average_operation_time_ms"] = (total_time + (end_time - start_time) * 1000) / self.performance_metrics["total_config_operations"]
            self.operation_log.append(f"Validated configuration for {component_type} using store {store.name} at {datetime.now().isoformat()}")
            self.last_operation = time.time()
            return result
        except ConfigurationValidationError as e:
            end_time = time.time()
            self.performance_metrics["total_config_operations"] += 1
            self.performance_metrics["failed_config_operations"] += 1
            total_time = self.performance_metrics["average_operation_time_ms"] * (self.performance_metrics["total_config_operations"] - 1)
            self.performance_metrics["average_operation_time_ms"] = (total_time + (end_time - start_time) * 1000) / self.performance_metrics["total_config_operations"]
            self.operation_log.append(f"Validation failed for {component_type}: {str(e)} at {datetime.now().isoformat()}")
            raise
        except ConfigurationError as e:
            end_time = time.time()
            self.performance_metrics["total_config_operations"] += 1
            self.performance_metrics["failed_config_operations"] += 1
            total_time = self.performance_metrics["average_operation_time_ms"] * (self.performance_metrics["total_config_operations"] - 1)
            self.performance_metrics["average_operation_time_ms"] = (total_time + (end_time - start_time) * 1000) / self.performance_metrics["total_config_operations"]
            self.operation_log.append(f"Failed to validate configuration for {component_type}: {str(e)} at {datetime.now().isoformat()}")
            raise
        except Exception as e:
            end_time = time.time()
            self.performance_metrics["total_config_operations"] += 1
            self.performance_metrics["failed_config_operations"] += 1
            total_time = self.performance_metrics["average_operation_time_ms"] * (self.performance_metrics["total_config_operations"] - 1)
            self.performance_metrics["average_operation_time_ms"] = (total_time + (end_time - start_time) * 1000) / self.performance_metrics["total_config_operations"]
            self.operation_log.append(f"Unexpected error validating configuration for {component_type}: {str(e)} at {datetime.now().isoformat()}")
            raise ConfigurationError(f"Unexpected error in manager {self.name} while validating configuration for {component_type}: {str(e)}")

    def set_environment(self, environment: str, store_name: Optional[str] = None) -> None:
        """Set the current environment for configuration overrides in the specified or default store."""
        if not self.active:
            raise ConfigurationError(f"Configuration Manager {self.name} is not active")
        start_time = time.time()
        try:
            store = self.select_store(store_name)
            store.set_environment(environment)
            end_time = time.time()
            self.performance_metrics["total_config_operations"] += 1
            self.performance_metrics["successful_config_operations"] += 1
            total_time = self.performance_metrics["average_operation_time_ms"] * (self.performance_metrics["total_config_operations"] - 1)
            self.performance_metrics["average_operation_time_ms"] = (total_time + (end_time - start_time) * 1000) / self.performance_metrics["total_config_operations"]
            self.operation_log.append(f"Set environment to {environment} in store {store.name} at {datetime.now().isoformat()}")
            self.last_operation = time.time()
        except ConfigurationError as e:
            end_time = time.time()
            self.performance_metrics["total_config_operations"] += 1
            self.performance_metrics["failed_config_operations"] += 1
            total_time = self.performance_metrics["average_operation_time_ms"] * (self.performance_metrics["total_config_operations"] - 1)
            self.performance_metrics["average_operation_time_ms"] = (total_time + (end_time - start_time) * 1000) / self.performance_metrics["total_config_operations"]
            self.operation_log.append(f"Failed to set environment to {environment}: {str(e)} at {datetime.now().isoformat()}")
            raise
        except Exception as e:
            end_time = time.time()
            self.performance_metrics["total_config_operations"] += 1
            self.performance_metrics["failed_config_operations"] += 1
            total_time = self.performance_metrics["average_operation_time_ms"] * (self.performance_metrics["total_config_operations"] - 1)
            self.performance_metrics["average_operation_time_ms"] = (total_time + (end_time - start_time) * 1000) / self.performance_metrics["total_config_operations"]
            self.operation_log.append(f"Unexpected error setting environment to {environment}: {str(e)} at {datetime.now().isoformat()}")
            raise ConfigurationError(f"Unexpected error in manager {self.name} while setting environment: {str(e)}")

    def reload_all_configurations(self, store_name: Optional[str] = None) -> None:
        """Reload configurations from storage for the specified or default store."""
        if not self.active:
            raise ConfigurationError(f"Configuration Manager {self.name} is not active")
        start_time = time.time()
        try:
            store = self.select_store(store_name)
            store.reload_configurations()
            end_time = time.time()
            self.performance_metrics["total_config_operations"] += 1
            self.performance_metrics["successful_config_operations"] += 1
            total_time = self.performance_metrics["average_operation_time_ms"] * (self.performance_metrics["total_config_operations"] - 1)
            self.performance_metrics["average_operation_time_ms"] = (total_time + (end_time - start_time) * 1000) / self.performance_metrics["total_config_operations"]
            self.operation_log.append(f"Reloaded all configurations in store {store.name} at {datetime.now().isoformat()}")
            self.last_operation = time.time()
        except ConfigurationError as e:
            end_time = time.time()
            self.performance_metrics["total_config_operations"] += 1
            self.performance_metrics["failed_config_operations"] += 1
            total_time = self.performance_metrics["average_operation_time_ms"] * (self.performance_metrics["total_config_operations"] - 1)
            self.performance_metrics["average_operation_time_ms"] = (total_time + (end_time - start_time) * 1000) / self.performance_metrics["total_config_operations"]
            self.operation_log.append(f"Failed to reload configurations: {str(e)} at {datetime.now().isoformat()}")
            raise
        except Exception as e:
            end_time = time.time()
            self.performance_metrics["total_config_operations"] += 1
            self.performance_metrics["failed_config_operations"] += 1
            total_time = self.performance_metrics["average_operation_time_ms"] * (self.performance_metrics["total_config_operations"] - 1)
            self.performance_metrics["average_operation_time_ms"] = (total_time + (end_time - start_time) * 1000) / self.performance_metrics["total_config_operations"]
            self.operation_log.append(f"Unexpected error reloading configurations: {str(e)} at {datetime.now().isoformat()}")
            raise ConfigurationError(f"Unexpected error in manager {self.name} while reloading configurations: {str(e)}")

    def get_performance_metrics(self, store_name: Optional[str] = None) -> Dict[str, Any]:
        """Get aggregated performance metrics for the specified or all stores."""
        with self.lock:
            if store_name:
                store = self.select_store(store_name)
                return {
                    "manager_metrics": self.performance_metrics,
                    "store_metrics": {store_name: store.performance_metrics}
                }
            else:
                return {
                    "manager_metrics": self.performance_metrics,
                    "store_metrics": {name: store.performance_metrics for name, store in self.stores.items()}
                }

# Example usage and initialization
def initialize_configuration_manager(config: Dict[str, Any]) -> ConfigurationManager:
    """Initialize a Configuration Manager with a default store."""
    manager = ConfigurationManager("DefaultConfigManager", config)
    
    # Add a default configuration store with schemas and environment profiles
    store_config = config.get("default_store", {
        "storage_type": "file",
        "storage_path": "configurations.json",
        "schemas": {
            "Agent": {
                "type": "object",
                "properties": {
                    "type": {"type": "string"},
                    "capabilities": {"type": "array", "items": {"type": "string"}},
                    "execution_limits": {"type": "object"},
                    "security_settings": {"type": "object"}
                },
                "required": ["type", "capabilities"]
            },
            "MCPTool": {
                "type": "object",
                "properties": {
                    "api_keys": {"type": "object"},
                    "rate_limits": {"type": "object"},
                    "operational_modes": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["api_keys"]
            },
            "Monitoring": {
                "type": "object",
                "properties": {
                    "metrics_collection": {"type": "boolean"},
                    "event_tracing": {"type": "boolean"},
                    "logging_levels": {"type": "string"},
                    "alert_thresholds": {"type": "object"}
                },
                "required": ["metrics_collection", "logging_levels"]
            },
            "Knowledge": {
                "type": "object",
                "properties": {
                    "source_prioritization": {"type": "array", "items": {"type": "string"}},
                    "indexing_strategies": {"type": "object"},
                    "caching_policies": {"type": "object"},
                    "access_controls": {"type": "object"}
                },
                "required": ["source_prioritization"]
            },
            "Evaluation": {
                "type": "object",
                "properties": {
                    "criteria_definitions": {"type": "object"},
                    "test_case_selection": {"type": "array", "items": {"type": "string"}},
                    "sampling_rates": {"type": "number"},
                    "reporting_formats": {"type": "string"}
                },
                "required": ["criteria_definitions"]
            },
            "Guardrail": {
                "type": "object",
                "properties": {
                    "policy_definitions": {"type": "object"},
                    "validation_rules": {"type": "array", "items": {"type": "object"}},
                    "content_filters": {"type": "object"},
                    "rate_limits": {"type": "object"}
                },
                "required": ["policy_definitions", "validation_rules"]
            },
            "Memory": {
                "type": "object",
                "properties": {
                    "retention_policies": {"type": "object"},
                    "storage_backends": {"type": "array", "items": {"type": "string"}},
                    "indexing_methods": {"type": "object"},
                    "encryption_settings": {"type": "object"}
                },
                "required": ["retention_policies", "storage_backends"]
            }
        },
        "environment_profiles": {
            "development": {
                "Agent/GeneralAgent/default": {"execution_limits": {"max_tasks": 10}, "debug": True},
                "Monitoring/SystemMonitor/default": {"logging_levels": "DEBUG"}
            },
            "staging": {
                "Agent/GeneralAgent/default": {"execution_limits": {"max_tasks": 50}, "debug": False},
                "Monitoring/SystemMonitor/default": {"logging_levels": "INFO"}
            },
            "production": {
                "Agent/GeneralAgent/default": {"execution_limits": {"max_tasks": 100}, "debug": False},
                "Monitoring/SystemMonitor/default": {"logging_levels": "WARNING"}
            }
        },
        "current_environment": "development"
    })
    
    manager.add_store(ConfigurationStore("DefaultConfigStore", store_config))
    
    return manager

if __name__ == "__main__":
    # Example configuration
    config_manager_config = {
        "default_store": {
            "storage_type": "file",
            "storage_path": "configurations.json",
            "security_enabled": True,
            "schemas": {
                "Agent": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string"},
                        "capabilities": {"type": "array", "items": {"type": "string"}},
                        "execution_limits": {"type": "object"},
                        "security_settings": {"type": "object"}
                    },
                    "required": ["type", "capabilities"]
                }
            },
            "environment_profiles": {
                "development": {
                    "Agent/GeneralAgent/default": {"execution_limits": {"max_tasks": 10}, "debug": True}
                },
                "staging": {
                    "Agent/GeneralAgent/default": {"execution_limits": {"max_tasks": 50}, "debug": False}
                },
                "production": {
                    "Agent/GeneralAgent/default": {"execution_limits": {"max_tasks": 100}, "debug": False}
                }
            },
            "current_environment": "development"
        }
    }
    
    # Initialize manager
    config_manager = initialize_configuration_manager(config_manager_config)
    
    # Activate manager and stores
    config_manager.activate()
    
    try:
        # Example saving a configuration
        agent_config = {
            "type": "general",
            "capabilities": ["task_execution", "decision_making"],
            "execution_limits": {"max_tasks": 20},
            "security_settings": {"auth": "basic"}
        }
        result = config_manager.save_component_config("Agent", "GeneralAgent", "1.0.0", agent_config, {"role": "default"})
        print(f"Save configuration result: {result}")
        
        # Example validating a configuration
        is_valid = config_manager.validate_component_config("Agent", agent_config, {"role": "default"})
        print(f"Configuration validation result: {is_valid}")
        
        # Example loading a configuration with environment override
        loaded_config = config_manager.load_component_config("Agent", "GeneralAgent", "1.0.0", environment="development", context={"role": "default"})
        print(f"Loaded configuration: {loaded_config}")
        
        # Example setting a different environment
        config_manager.set_environment("staging")
        loaded_config_staging = config_manager.load_component_config("Agent", "GeneralAgent", "1.0.0", context={"role": "default"})
        print(f"Loaded configuration in staging environment: {loaded_config_staging}")
        
        # Example reloading configurations
        config_manager.reload_all_configurations()
        print("Configurations reloaded")
    except ConfigurationError as e:
        print(f"Configuration error: {e}")
    finally:
        # Deactivate manager and stores
        config_manager.deactivate()
