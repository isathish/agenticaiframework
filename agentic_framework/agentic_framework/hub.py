"""
Agentic Framework Hub Module

This module provides a centralized repository and management layer for various components within the Agentic Framework.
It supports hubs for Agents, Prompts, MCP Tools, Guardrails, and LLMs, enabling discoverability, version control,
and streamlined access. The Hub ensures that components are organized, easily retrievable, and consistently maintained
across the framework.
"""

from typing import Any, Dict, List, Optional, Callable, Set
from datetime import datetime
import time
import threading
import json
import os
import sqlite3
from pathlib import Path
import copy

# Custom exceptions for hub management errors
class HubError(Exception):
    """Base exception for hub-related errors."""
    pass

class ComponentNotFoundError(HubError):
    """Raised when a component is not found in the hub."""
    pass

class ComponentVersionError(HubError):
    """Raised when there is an issue with component versioning."""
    pass

class HubAccessDeniedError(HubError):
    """Raised when access to a hub or component is denied due to security policies."""
    pass

# Base class for hub repositories
class HubRepository:
    """Base class for managing a specific type of component in the Agentic Framework Hub."""
    def __init__(self, name: str, component_type: str, config: Dict[str, Any]):
        self.name = name
        self.component_type = component_type
        self.config = config
        self.active = False
        self.db_path = config.get("db_path", f"{component_type.lower()}_hub.db")
        self.security_enabled = config.get("security_enabled", True)
        self.access_control = config.get("access_control", {"read": ["all"], "write": ["all"], "deploy": ["all"]})
        self.performance_metrics = {
            "total_registrations": 0,
            "successful_registrations": 0,
            "failed_registrations": 0,
            "total_retrievals": 0,
            "successful_retrievals": 0,
            "failed_retrievals": 0,
            "total_searches": 0,
            "successful_searches": 0,
            "failed_searches": 0,
            "average_registration_time_ms": 0.0,
            "average_retrieval_time_ms": 0.0,
            "average_search_time_ms": 0.0
        }
        self.hub_log: List[str] = []
        self.last_updated = time.time()
        self.lock = threading.Lock()
        self.conn = None
        self.cursor = None
        self.table_name = f"{component_type.lower()}_components"

    def activate(self) -> None:
        """Activate the hub repository by connecting to the SQLite database."""
        with self.lock:
            try:
                self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
                self.cursor = self.conn.cursor()
                # Create table if not exists
                self.cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.table_name} (
                        name TEXT,
                        version TEXT,
                        config TEXT,
                        metadata TEXT,
                        timestamp REAL,
                        PRIMARY KEY (name, version)
                    )
                """)
                self.conn.commit()
                self.active = True
                self.hub_log.append(f"Hub repository {self.name} for {self.component_type} activated with DB {self.db_path} at {datetime.now().isoformat()}")
            except Exception as e:
                self.hub_log.append(f"Failed to activate hub repository {self.name}: {str(e)} at {datetime.now().isoformat()}")
                raise HubError(f"Failed to connect to hub database for {self.component_type}: {str(e)}")
            finally:
                self.last_updated = time.time()

    def deactivate(self) -> None:
        """Deactivate the hub repository by closing the database connection."""
        with self.lock:
            if self.conn:
                self.conn.close()
                self.conn = None
                self.cursor = None
            self.active = False
            self.hub_log.append(f"Hub repository {self.name} for {self.component_type} deactivated at {datetime.now().isoformat()}")
            self.last_updated = time.time()

    def register_component(self, name: str, version: str, config: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None,
                           context: Optional[Dict[str, Any]] = None) -> bool:
        """Register a component with its configuration and metadata in the hub."""
        if not self.active:
            raise HubError(f"Hub repository {self.name} for {self.component_type} is not active")
        role = context.get("role", "default") if context else "default"
        if not self.enforce_security("write", name, role):
            raise HubAccessDeniedError(f"Write access denied for component {name} in {self.component_type} hub")
        start_time = time.time()
        try:
            timestamp = time.time()
            config_json = json.dumps(config)
            metadata_json = json.dumps(metadata or {})
            with self.lock:
                self.cursor.execute(f"""
                    INSERT OR REPLACE INTO {self.table_name} (name, version, config, metadata, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                """, (name, version, config_json, metadata_json, timestamp))
                self.conn.commit()
            end_time = time.time()
            self.update_performance_metrics("registration", start_time, end_time, success=True)
            self.hub_log.append(f"Registered {self.component_type} component {name} version {version} at {datetime.now().isoformat()}")
            return True
        except Exception as e:
            end_time = time.time()
            self.update_performance_metrics("registration", start_time, end_time, success=False)
            self.hub_log.append(f"Failed to register {self.component_type} component {name} version {version}: {str(e)} at {datetime.now().isoformat()}")
            raise HubError(f"Error registering {self.component_type} component {name} version {version}: {str(e)}")

    def retrieve_component(self, name: str, version: Optional[str] = None,
                           context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Retrieve a component's configuration and metadata by name and optional version."""
        if not self.active:
            raise HubError(f"Hub repository {self.name} for {self.component_type} is not active")
        role = context.get("role", "default") if context else "default"
        if not self.enforce_security("read", name, role):
            raise HubAccessDeniedError(f"Read access denied for component {name} in {self.component_type} hub")
        start_time = time.time()
        try:
            with self.lock:
                if version:
                    self.cursor.execute(f"""
                        SELECT config, metadata FROM {self.table_name}
                        WHERE name = ? AND version = ?
                    """, (name, version))
                else:
                    self.cursor.execute(f"""
                        SELECT config, metadata FROM {self.table_name}
                        WHERE name = ?
                        ORDER BY timestamp DESC
                        LIMIT 1
                    """, (name,))
                result = self.cursor.fetchone()
            if result:
                config = json.loads(result[0])
                metadata = json.loads(result[1])
                end_time = time.time()
                self.update_performance_metrics("retrieval", start_time, end_time, success=True)
                self.hub_log.append(f"Retrieved {self.component_type} component {name} version {version if version else 'latest'} at {datetime.now().isoformat()}")
                return {"config": config, "metadata": metadata}
            else:
                end_time = time.time()
                self.update_performance_metrics("retrieval", start_time, end_time, success=False)
                self.hub_log.append(f"{self.component_type} component {name} version {version if version else 'any'} not found at {datetime.now().isoformat()}")
                raise ComponentNotFoundError(f"{self.component_type} component {name} version {version if version else 'any'} not found")
        except Exception as e:
            end_time = time.time()
            self.update_performance_metrics("retrieval", start_time, end_time, success=False)
            self.hub_log.append(f"Failed to retrieve {self.component_type} component {name} version {version if version else 'any'}: {str(e)} at {datetime.now().isoformat()}")
            raise HubError(f"Error retrieving {self.component_type} component {name} version {version if version else 'any'}: {str(e)}")

    def search_components(self, query: Dict[str, Any], limit: int = 10,
                          context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Search for components based on metadata or other criteria."""
        if not self.active:
            raise HubError(f"Hub repository {self.name} for {self.component_type} is not active")
        role = context.get("role", "default") if context else "default"
        start_time = time.time()
        try:
            results = []
            with self.lock:
                self.cursor.execute(f"SELECT name, version, metadata FROM {self.table_name}")
                rows = self.cursor.fetchall()
                for row in rows:
                    name, version, metadata_json = row
                    if self.enforce_security("read", name, role):
                        metadata = json.loads(metadata_json) if metadata_json else {}
                        match = True
                        for q_key, q_value in query.items():
                            if q_key in metadata and metadata[q_key] != q_value:
                                match = False
                                break
                        if match:
                            results.append({"name": name, "version": version, "metadata": metadata})
                    if len(results) >= limit:
                        break
            end_time = time.time()
            self.update_performance_metrics("search", start_time, end_time, success=True)
            self.hub_log.append(f"Searched {self.component_type} components with query {query} at {datetime.now().isoformat()}")
            return results
        except Exception as e:
            end_time = time.time()
            self.update_performance_metrics("search", start_time, end_time, success=False)
            self.hub_log.append(f"Failed to search {self.component_type} components: {str(e)} at {datetime.now().isoformat()}")
            raise HubError(f"Error searching {self.component_type} components: {str(e)}")

    def list_versions(self, name: str, context: Optional[Dict[str, Any]] = None) -> List[str]:
        """List all available versions of a component."""
        if not self.active:
            raise HubError(f"Hub repository {self.name} for {self.component_type} is not active")
        role = context.get("role", "default") if context else "default"
        if not self.enforce_security("read", name, role):
            raise HubAccessDeniedError(f"Read access denied for component {name} in {self.component_type} hub")
        start_time = time.time()
        try:
            with self.lock:
                self.cursor.execute(f"""
                    SELECT version FROM {self.table_name}
                    WHERE name = ?
                    ORDER BY timestamp DESC
                """, (name,))
                versions = [row[0] for row in self.cursor.fetchall()]
            end_time = time.time()
            self.update_performance_metrics("search", start_time, end_time, success=True)
            self.hub_log.append(f"Listed versions for {self.component_type} component {name} at {datetime.now().isoformat()}")
            return versions
        except Exception as e:
            end_time = time.time()
            self.update_performance_metrics("search", start_time, end_time, success=False)
            self.hub_log.append(f"Failed to list versions for {self.component_type} component {name}: {str(e)} at {datetime.now().isoformat()}")
            raise HubError(f"Error listing versions for {self.component_type} component {name}: {str(e)}")

    def remove_component(self, name: str, version: Optional[str] = None,
                         context: Optional[Dict[str, Any]] = None) -> bool:
        """Remove a component or a specific version from the hub."""
        if not self.active:
            raise HubError(f"Hub repository {self.name} for {self.component_type} is not active")
        role = context.get("role", "default") if context else "default"
        if not self.enforce_security("write", name, role):
            raise HubAccessDeniedError(f"Write access denied for component {name} in {self.component_type} hub")
        start_time = time.time()
        try:
            with self.lock:
                if version:
                    self.cursor.execute(f"""
                        DELETE FROM {self.table_name}
                        WHERE name = ? AND version = ?
                    """, (name, version))
                else:
                    self.cursor.execute(f"""
                        DELETE FROM {self.table_name}
                        WHERE name = ?
                    """, (name,))
                self.conn.commit()
                removed_count = self.cursor.rowcount
            end_time = time.time()
            if removed_count > 0:
                self.update_performance_metrics("registration", start_time, end_time, success=True)
                self.hub_log.append(f"Removed {self.component_type} component {name} version {version if version else 'all'} at {datetime.now().isoformat()}")
                return True
            else:
                self.update_performance_metrics("registration", start_time, end_time, success=False)
                self.hub_log.append(f"No versions found to remove for {self.component_type} component {name} version {version if version else 'all'} at {datetime.now().isoformat()}")
                return False
        except Exception as e:
            end_time = time.time()
            self.update_performance_metrics("registration", start_time, end_time, success=False)
            self.hub_log.append(f"Failed to remove {self.component_type} component {name} version {version if version else 'all'}: {str(e)} at {datetime.now().isoformat()}")
            raise HubError(f"Error removing {self.component_type} component {name} version {version if version else 'all'}: {str(e)}")

    def enforce_security(self, operation: str, component_name: str, role: str = "default") -> bool:
        """Enforce security policies for the given operation and component."""
        if not self.security_enabled:
            return True
        allowed_roles = self.access_control.get(operation, [])
        if "all" in allowed_roles or role in allowed_roles:
            self.hub_log.append(f"Security check passed for {operation} on {self.component_type} component {component_name} by role {role} at {datetime.now().isoformat()}")
            return True
        else:
            self.hub_log.append(f"Security check failed for {operation} on {self.component_type} component {component_name} by role {role} at {datetime.now().isoformat()}")
            return False

    def update_performance_metrics(self, operation: str, start_time: float, end_time: float, success: bool) -> None:
        """Update performance metrics based on operation result."""
        with self.lock:
            latency = (end_time - start_time) * 1000  # Convert to milliseconds
            if operation == "registration":
                self.performance_metrics["total_registrations"] += 1
                if success:
                    self.performance_metrics["successful_registrations"] += 1
                else:
                    self.performance_metrics["failed_registrations"] += 1
                total_time = self.performance_metrics["average_registration_time_ms"] * (self.performance_metrics["total_registrations"] - 1)
                self.performance_metrics["average_registration_time_ms"] = (total_time + latency) / self.performance_metrics["total_registrations"]
            elif operation == "retrieval":
                self.performance_metrics["total_retrievals"] += 1
                if success:
                    self.performance_metrics["successful_retrievals"] += 1
                else:
                    self.performance_metrics["failed_retrievals"] += 1
                total_time = self.performance_metrics["average_retrieval_time_ms"] * (self.performance_metrics["total_retrievals"] - 1)
                self.performance_metrics["average_retrieval_time_ms"] = (total_time + latency) / self.performance_metrics["total_retrievals"]
            elif operation == "search":
                self.performance_metrics["total_searches"] += 1
                if success:
                    self.performance_metrics["successful_searches"] += 1
                else:
                    self.performance_metrics["failed_searches"] += 1
                total_time = self.performance_metrics["average_search_time_ms"] * (self.performance_metrics["total_searches"] - 1)
                self.performance_metrics["average_search_time_ms"] = (total_time + latency) / self.performance_metrics["total_searches"]
            self.last_updated = time.time()

# Specific Hub implementations for different component types
class AgentHub(HubRepository):
    """Hub for managing Agent components."""
    def __init__(self, config: Dict[str, Any]):
        super().__init__("AgentHub", "Agent", config)

class PromptHub(HubRepository):
    """Hub for managing Prompt components."""
    def __init__(self, config: Dict[str, Any]):
        super().__init__("PromptHub", "Prompt", config)

class MCPToolHub(HubRepository):
    """Hub for managing MCP Tool components."""
    def __init__(self, config: Dict[str, Any]):
        super().__init__("MCPToolHub", "MCPTool", config)

class GuardrailHub(HubRepository):
    """Hub for managing Guardrail components."""
    def __init__(self, config: Dict[str, Any]):
        super().__init__("GuardrailHub", "Guardrail", config)

class LLMHub(HubRepository):
    """Hub for managing LLM components."""
    def __init__(self, config: Dict[str, Any]):
        super().__init__("LLMHub", "LLM", config)

# Manager class for coordinating multiple hubs
class HubManager:
    """Manages multiple hubs for different component types in the Agentic Framework."""
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.hubs: Dict[str, HubRepository] = {}
        self.active = False
        self.lock = threading.Lock()
        self.performance_metrics = {
            "total_hub_operations": 0,
            "successful_hub_operations": 0,
            "failed_hub_operations": 0,
            "average_operation_time_ms": 0.0
        }
        self.operation_log: List[str] = []
        self.last_operation = time.time()

    def add_hub(self, hub: HubRepository) -> None:
        """Add a hub to the manager."""
        with self.lock:
            self.hubs[hub.component_type] = hub
            self.operation_log.append(f"Added hub for {hub.component_type} to manager {self.name} at {datetime.now().isoformat()}")
            self.last_operation = time.time()

    def remove_hub(self, component_type: str) -> None:
        """Remove a hub from the manager."""
        with self.lock:
            if component_type in self.hubs:
                hub = self.hubs[component_type]
                if hub.active:
                    hub.deactivate()
                del self.hubs[component_type]
                self.operation_log.append(f"Removed hub for {component_type} from manager {self.name} at {datetime.now().isoformat()}")
            else:
                self.operation_log.append(f"Hub for {component_type} not found in manager {self.name} at {datetime.now().isoformat()}")
            self.last_operation = time.time()

    def activate(self) -> None:
        """Activate the hub manager and all hubs."""
        with self.lock:
            self.active = True
            for component_type, hub in self.hubs.items():
                try:
                    if not hub.active:
                        hub.activate()
                    self.operation_log.append(f"Activated hub for {component_type} in manager {self.name} at {datetime.now().isoformat()}")
                except Exception as e:
                    self.operation_log.append(f"Failed to activate hub for {component_type}: {str(e)} at {datetime.now().isoformat()}")
            self.last_operation = time.time()

    def deactivate(self) -> None:
        """Deactivate the hub manager and all hubs."""
        with self.lock:
            self.active = False
            for component_type, hub in self.hubs.items():
                try:
                    if hub.active:
                        hub.deactivate()
                    self.operation_log.append(f"Deactivated hub for {component_type} in manager {self.name} at {datetime.now().isoformat()}")
                except Exception as e:
                    self.operation_log.append(f"Failed to deactivate hub for {component_type}: {str(e)} at {datetime.now().isoformat()}")
            self.last_operation = time.time()

    def register_component(self, component_type: str, name: str, version: str, config: Dict[str, Any],
                           metadata: Optional[Dict[str, Any]] = None, context: Optional[Dict[str, Any]] = None) -> bool:
        """Register a component in the appropriate hub."""
        if not self.active:
            raise HubError(f"Hub Manager {self.name} is not active")
        with self.lock:
            start_time = time.time()
            try:
                if component_type not in self.hubs:
                    raise HubError(f"No hub found for component type {component_type} in manager {self.name}")
                hub = self.hubs[component_type]
                if not hub.active:
                    raise HubError(f"Hub for {component_type} is not active in manager {self.name}")
                
                result = hub.register_component(name, version, config, metadata, context)
                end_time = time.time()
                self.performance_metrics["total_hub_operations"] += 1
                self.performance_metrics["successful_hub_operations"] += 1
                total_time = self.performance_metrics["average_operation_time_ms"] * (self.performance_metrics["total_hub_operations"] - 1)
                self.performance_metrics["average_operation_time_ms"] = (total_time + (end_time - start_time) * 1000) / self.performance_metrics["total_hub_operations"]
                self.operation_log.append(f"Registered {component_type} component {name} version {version} at {datetime.now().isoformat()}")
                self.last_operation = time.time()
                return result
            except HubError as e:
                end_time = time.time()
                self.performance_metrics["total_hub_operations"] += 1
                self.performance_metrics["failed_hub_operations"] += 1
                total_time = self.performance_metrics["average_operation_time_ms"] * (self.performance_metrics["total_hub_operations"] - 1)
                self.performance_metrics["average_operation_time_ms"] = (total_time + (end_time - start_time) * 1000) / self.performance_metrics["total_hub_operations"]
                self.operation_log.append(f"Failed to register {component_type} component {name} version {version}: {str(e)} at {datetime.now().isoformat()}")
                raise
            except Exception as e:
                end_time = time.time()
                self.performance_metrics["total_hub_operations"] += 1
                self.performance_metrics["failed_hub_operations"] += 1
                total_time = self.performance_metrics["average_operation_time_ms"] * (self.performance_metrics["total_hub_operations"] - 1)
                self.performance_metrics["average_operation_time_ms"] = (total_time + (end_time - start_time) * 1000) / self.performance_metrics["total_hub_operations"]
                self.operation_log.append(f"Unexpected error registering {component_type} component {name} version {version}: {str(e)} at {datetime.now().isoformat()}")
                raise HubError(f"Unexpected error in manager {self.name} while registering {component_type} component {name} version {version}: {str(e)}")

    def retrieve_component(self, component_type: str, name: str, version: Optional[str] = None,
                           context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Retrieve a component from the appropriate hub."""
        if not self.active:
            raise HubError(f"Hub Manager {self.name} is not active")
        with self.lock:
            start_time = time.time()
            try:
                if component_type not in self.hubs:
                    raise HubError(f"No hub found for component type {component_type} in manager {self.name}")
                hub = self.hubs[component_type]
                if not hub.active:
                    raise HubError(f"Hub for {component_type} is not active in manager {self.name}")
                
                result = hub.retrieve_component(name, version, context)
                end_time = time.time()
                self.performance_metrics["total_hub_operations"] += 1
                self.performance_metrics["successful_hub_operations"] += 1
                total_time = self.performance_metrics["average_operation_time_ms"] * (self.performance_metrics["total_hub_operations"] - 1)
                self.performance_metrics["average_operation_time_ms"] = (total_time + (end_time - start_time) * 1000) / self.performance_metrics["total_hub_operations"]
                self.operation_log.append(f"Retrieved {component_type} component {name} version {version if version else 'latest'} at {datetime.now().isoformat()}")
                self.last_operation = time.time()
                return result
            except ComponentNotFoundError as e:
                end_time = time.time()
                self.performance_metrics["total_hub_operations"] += 1
                self.performance_metrics["failed_hub_operations"] += 1
                total_time = self.performance_metrics["average_operation_time_ms"] * (self.performance_metrics["total_hub_operations"] - 1)
                self.performance_metrics["average_operation_time_ms"] = (total_time + (end_time - start_time) * 1000) / self.performance_metrics["total_hub_operations"]
                self.operation_log.append(f"{component_type} component {name} version {version if version else 'any'} not found: {str(e)} at {datetime.now().isoformat()}")
                raise
            except HubError as e:
                end_time = time.time()
                self.performance_metrics["total_hub_operations"] += 1
                self.performance_metrics["failed_hub_operations"] += 1
                total_time = self.performance_metrics["average_operation_time_ms"] * (self.performance_metrics["total_hub_operations"] - 1)
                self.performance_metrics["average_operation_time_ms"] = (total_time + (end_time - start_time) * 1000) / self.performance_metrics["total_hub_operations"]
                self.operation_log.append(f"Failed to retrieve {component_type} component {name} version {version if version else 'any'}: {str(e)} at {datetime.now().isoformat()}")
                raise
            except Exception as e:
                end_time = time.time()
                self.performance_metrics["total_hub_operations"] += 1
                self.performance_metrics["failed_hub_operations"] += 1
                total_time = self.performance_metrics["average_operation_time_ms"] * (self.performance_metrics["total_hub_operations"] - 1)
                self.performance_metrics["average_operation_time_ms"] = (total_time + (end_time - start_time) * 1000) / self.performance_metrics["total_hub_operations"]
                self.operation_log.append(f"Unexpected error retrieving {component_type} component {name} version {version if version else 'any'}: {str(e)} at {datetime.now().isoformat()}")
                raise HubError(f"Unexpected error in manager {self.name} while retrieving {component_type} component {name} version {version if version else 'any'}: {str(e)}")

    def search_components(self, component_type: str, query: Dict[str, Any], limit: int = 10,
                          context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Search for components in the appropriate hub."""
        if not self.active:
            raise HubError(f"Hub Manager {self.name} is not active")
        with self.lock:
            start_time = time.time()
            try:
                if component_type not in self.hubs:
                    raise HubError(f"No hub found for component type {component_type} in manager {self.name}")
                hub = self.hubs[component_type]
                if not hub.active:
                    raise HubError(f"Hub for {component_type} is not active in manager {self.name}")
                
                result = hub.search_components(query, limit, context)
                end_time = time.time()
                self.performance_metrics["total_hub_operations"] += 1
                self.performance_metrics["successful_hub_operations"] += 1
                total_time = self.performance_metrics["average_operation_time_ms"] * (self.performance_metrics["total_hub_operations"] - 1)
                self.performance_metrics["average_operation_time_ms"] = (total_time + (end_time - start_time) * 1000) / self.performance_metrics["total_hub_operations"]
                self.operation_log.append(f"Searched {component_type} components with query {query} at {datetime.now().isoformat()}")
                self.last_operation = time.time()
                return result
            except HubError as e:
                end_time = time.time()
                self.performance_metrics["total_hub_operations"] += 1
                self.performance_metrics["failed_hub_operations"] += 1
                total_time = self.performance_metrics["average_operation_time_ms"] * (self.performance_metrics["total_hub_operations"] - 1)
                self.performance_metrics["average_operation_time_ms"] = (total_time + (end_time - start_time) * 1000) / self.performance_metrics["total_hub_operations"]
                self.operation_log.append(f"Failed to search {component_type} components: {str(e)} at {datetime.now().isoformat()}")
                raise
            except Exception as e:
                end_time = time.time()
                self.performance_metrics["total_hub_operations"] += 1
                self.performance_metrics["failed_hub_operations"] += 1
                total_time = self.performance_metrics["average_operation_time_ms"] * (self.performance_metrics["total_hub_operations"] - 1)
                self.performance_metrics["average_operation_time_ms"] = (total_time + (end_time - start_time) * 1000) / self.performance_metrics["total_hub_operations"]
                self.operation_log.append(f"Unexpected error searching {component_type} components: {str(e)} at {datetime.now().isoformat()}")
                raise HubError(f"Unexpected error in manager {self.name} while searching {component_type} components: {str(e)}")

    def list_component_versions(self, component_type: str, name: str,
                                context: Optional[Dict[str, Any]] = None) -> List[str]:
        """List all versions of a component in the appropriate hub."""
        if not self.active:
            raise HubError(f"Hub Manager {self.name} is not active")
        with self.lock:
            start_time = time.time()
            try:
                if component_type not in self.hubs:
                    raise HubError(f"No hub found for component type {component_type} in manager {self.name}")
                hub = self.hubs[component_type]
                if not hub.active:
                    raise HubError(f"Hub for {component_type} is not active in manager {self.name}")
                
                result = hub.list_versions(name, context)
                end_time = time.time()
                self.performance_metrics["total_hub_operations"] += 1
                self.performance_metrics["successful_hub_operations"] += 1
                total_time = self.performance_metrics["average_operation_time_ms"] * (self.performance_metrics["total_hub_operations"] - 1)
                self.performance_metrics["average_operation_time_ms"] = (total_time + (end_time - start_time) * 1000) / self.performance_metrics["total_hub_operations"]
                self.operation_log.append(f"Listed versions for {component_type} component {name} at {datetime.now().isoformat()}")
                self.last_operation = time.time()
                return result
            except HubError as e:
                end_time = time.time()
                self.performance_metrics["total_hub_operations"] += 1
                self.performance_metrics["failed_hub_operations"] += 1
                total_time = self.performance_metrics["average_operation_time_ms"] * (self.performance_metrics["total_hub_operations"] - 1)
                self.performance_metrics["average_operation_time_ms"] = (total_time + (end_time - start_time) * 1000) / self.performance_metrics["total_hub_operations"]
                self.operation_log.append(f"Failed to list versions for {component_type} component {name}: {str(e)} at {datetime.now().isoformat()}")
                raise
            except Exception as e:
                end_time = time.time()
                self.performance_metrics["total_hub_operations"] += 1
                self.performance_metrics["failed_hub_operations"] += 1
                total_time = self.performance_metrics["average_operation_time_ms"] * (self.performance_metrics["total_hub_operations"] - 1)
                self.performance_metrics["average_operation_time_ms"] = (total_time + (end_time - start_time) * 1000) / self.performance_metrics["total_hub_operations"]
                self.operation_log.append(f"Unexpected error listing versions for {component_type} component {name}: {str(e)} at {datetime.now().isoformat()}")
                raise HubError(f"Unexpected error in manager {self.name} while listing versions for {component_type} component {name}: {str(e)}")

    def remove_component(self, component_type: str, name: str, version: Optional[str] = None,
                         context: Optional[Dict[str, Any]] = None) -> bool:
        """Remove a component or specific version from the appropriate hub."""
        if not self.active:
            raise HubError(f"Hub Manager {self.name} is not active")
        with self.lock:
            start_time = time.time()
            try:
                if component_type not in self.hubs:
                    raise HubError(f"No hub found for component type {component_type} in manager {self.name}")
                hub = self.hubs[component_type]
                if not hub.active:
                    raise HubError(f"Hub for {component_type} is not active in manager {self.name}")
                
                result = hub.remove_component(name, version, context)
                end_time = time.time()
                self.performance_metrics["total_hub_operations"] += 1
                self.performance_metrics["successful_hub_operations"] += 1
                total_time = self.performance_metrics["average_operation_time_ms"] * (self.performance_metrics["total_hub_operations"] - 1)
                self.performance_metrics["average_operation_time_ms"] = (total_time + (end_time - start_time) * 1000) / self.performance_metrics["total_hub_operations"]
                self.operation_log.append(f"Removed {component_type} component {name} version {version if version else 'all'} at {datetime.now().isoformat()}")
                self.last_operation = time.time()
                return result
            except HubError as e:
                end_time = time.time()
                self.performance_metrics["total_hub_operations"] += 1
                self.performance_metrics["failed_hub_operations"] += 1
                total_time = self.performance_metrics["average_operation_time_ms"] * (self.performance_metrics["total_hub_operations"] - 1)
                self.performance_metrics["average_operation_time_ms"] = (total_time + (end_time - start_time) * 1000) / self.performance_metrics["total_hub_operations"]
                self.operation_log.append(f"Failed to remove {component_type} component {name} version {version if version else 'all'}: {str(e)} at {datetime.now().isoformat()}")
                raise
            except Exception as e:
                end_time = time.time()
                self.performance_metrics["total_hub_operations"] += 1
                self.performance_metrics["failed_hub_operations"] += 1
                total_time = self.performance_metrics["average_operation_time_ms"] * (self.performance_metrics["total_hub_operations"] - 1)
                self.performance_metrics["average_operation_time_ms"] = (total_time + (end_time - start_time) * 1000) / self.performance_metrics["total_hub_operations"]
                self.operation_log.append(f"Unexpected error removing {component_type} component {name} version {version if version else 'all'}: {str(e)} at {datetime.now().isoformat()}")
                raise HubError(f"Unexpected error in manager {self.name} while removing {component_type} component {name} version {version if version else 'all'}: {str(e)}")

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get aggregated performance metrics for all hubs."""
        with self.lock:
            aggregated_metrics = {
                "manager_metrics": self.performance_metrics,
                "hub_metrics": {component_type: hub.performance_metrics for component_type, hub in self.hubs.items()}
            }
            return aggregated_metrics

# Example usage and initialization
def initialize_hub_manager(config: Dict[str, Any]) -> HubManager:
    """Initialize a Hub Manager with all supported hub types."""
    manager = HubManager("DefaultHubManager", config)
    
    # Add various hubs with their configurations
    agent_config = config.get("agent_hub", {"db_path": "agent_hub.db"})
    prompt_config = config.get("prompt_hub", {"db_path": "prompt_hub.db"})
    tool_config = config.get("mcp_tool_hub", {"db_path": "mcp_tool_hub.db"})
    guardrail_config = config.get("guardrail_hub", {"db_path": "guardrail_hub.db"})
    llm_config = config.get("llm_hub", {"db_path": "llm_hub.db"})
    
    manager.add_hub(AgentHub(agent_config))
    manager.add_hub(PromptHub(prompt_config))
    manager.add_hub(MCPToolHub(tool_config))
    manager.add_hub(GuardrailHub(guardrail_config))
    manager.add_hub(LLMHub(llm_config))
    
    return manager

if __name__ == "__main__":
    # Example configuration
    hub_config = {
        "agent_hub": {"db_path": "agent_hub.db", "security_enabled": True},
        "prompt_hub": {"db_path": "prompt_hub.db", "security_enabled": True},
        "mcp_tool_hub": {"db_path": "mcp_tool_hub.db", "security_enabled": True},
        "guardrail_hub": {"db_path": "guardrail_hub.db", "security_enabled": True},
        "llm_hub": {"db_path": "llm_hub.db", "security_enabled": True}
    }
    
    # Initialize manager
    hub_manager = initialize_hub_manager(hub_config)
    
    # Activate manager and hubs
    hub_manager.activate()
    
    try:
        # Example registration of an Agent component
        agent_config = {"type": "general", "capabilities": ["task_execution", "decision_making"]}
        result = hub_manager.register_component("Agent", "GeneralAgent", "1.0.0", agent_config, {"domain": "general"}, {"role": "default"})
        print(f"Agent registration result: {result}")
        
        # Example retrieval of an Agent component
        agent_data = hub_manager.retrieve_component("Agent", "GeneralAgent", "1.0.0", {"role": "default"})
        print(f"Retrieved Agent data: {agent_data}")
        
        # Example search for Agent components
        search_results = hub_manager.search_components("Agent", {"domain": "general"}, limit=5, context={"role": "default"})
        print(f"Agent search results: {search_results}")
        
        # Example listing versions of an Agent component
        versions = hub_manager.list_component_versions("Agent", "GeneralAgent", {"role": "default"})
        print(f"Agent versions: {versions}")
    except HubError as e:
        print(f"Hub error: {e}")
    finally:
        # Deactivate manager and hubs
        hub_manager.deactivate()
