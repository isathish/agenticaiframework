"""
Agentic Framework Memory Module

This module provides implementations for memory management within the Agentic Framework.
It supports short-term, long-term, and external memory types to enable agents to retain, recall,
and utilize information across interactions. The module includes mechanisms for memory indexing,
retrieval, lifecycle management, security, and synchronization.
"""

from typing import Any, Dict, List, Optional, Callable, Set
from datetime import datetime
import time
import threading
import json
import os
import sqlite3
from pathlib import Path
import pickle
import numpy as np
from collections import defaultdict

# Custom exceptions for memory management errors
class MemoryError(Exception):
    """Base exception for memory-related errors."""
    pass

class MemoryNotFoundError(MemoryError):
    """Raised when a memory item is not found."""
    pass

class MemoryAccessDeniedError(MemoryError):
    """Raised when access to memory is denied due to security policies."""
    pass

class MemoryStorageFullError(MemoryError):
    """Raised when memory storage capacity is exceeded."""
    pass

# Base class for memory storage
class MemoryStorage:
    """Base class for different types of memory storage in the Agentic Framework."""
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.active = False
        self.capacity = config.get("capacity", 1000)  # Maximum number of items
        self.retention_policy = config.get("retention_policy", "time_based")
        self.retention_period = config.get("retention_period", 86400)  # 24 hours in seconds
        self.security_enabled = config.get("security_enabled", True)
        self.encryption_method = config.get("encryption_method", "AES")
        self.access_control = config.get("access_control", {"read": ["all"], "write": ["all"]})
        self.performance_metrics = {
            "total_stores": 0,
            "successful_stores": 0,
            "failed_stores": 0,
            "total_retrievals": 0,
            "successful_retrievals": 0,
            "failed_retrievals": 0,
            "average_store_time_ms": 0.0,
            "average_retrieval_time_ms": 0.0
        }
        self.memory_log: List[str] = []
        self.last_updated = time.time()
        self.lock = threading.Lock()

    def activate(self) -> None:
        """Activate the memory storage for use."""
        with self.lock:
            self.active = True
            self.memory_log.append(f"Memory storage {self.name} activated at {datetime.now().isoformat()}")
            self.last_updated = time.time()

    def deactivate(self) -> None:
        """Deactivate the memory storage."""
        with self.lock:
            self.active = False
            self.memory_log.append(f"Memory storage {self.name} deactivated at {datetime.now().isoformat()}")
            self.last_updated = time.time()

    def store(self, key: str, value: Any, metadata: Optional[Dict[str, Any]] = None,
              context: Optional[Dict[str, Any]] = None) -> bool:
        """Store a memory item with a key, value, and optional metadata."""
        raise NotImplementedError(f"Store method not implemented for memory storage {self.name}")

    def retrieve(self, key: str, context: Optional[Dict[str, Any]] = None) -> Any:
        """Retrieve a memory item by key."""
        raise NotImplementedError(f"Retrieve method not implemented for memory storage {self.name}")

    def search(self, query: Dict[str, Any], limit: int = 10, context: Optional[Dict[str, Any]] = None) -> List[Any]:
        """Search memory items based on a query dictionary."""
        raise NotImplementedError(f"Search method not implemented for memory storage {self.name}")

    def delete(self, key: str, context: Optional[Dict[str, Any]] = None) -> bool:
        """Delete a memory item by key."""
        raise NotImplementedError(f"Delete method not implemented for memory storage {self.name}")

    def enforce_security(self, operation: str, key: str, role: str = "default") -> bool:
        """Enforce security policies for the given operation and key."""
        if not self.security_enabled:
            return True
        # Check access control based on operation and role
        allowed_roles = self.access_control.get(operation, [])
        if "all" in allowed_roles or role in allowed_roles:
            self.memory_log.append(f"Security check passed for {operation} on key {key} by role {role} at {datetime.now().isoformat()}")
            return True
        else:
            self.memory_log.append(f"Security check failed for {operation} on key {key} by role {role} at {datetime.now().isoformat()}")
            raise MemoryAccessDeniedError(f"Access denied for {operation} on key {key} by role {role}")

    def update_performance_metrics(self, operation: str, start_time: float, end_time: float, success: bool) -> None:
        """Update performance metrics based on operation result."""
        with self.lock:
            latency = (end_time - start_time) * 1000  # Convert to milliseconds
            if operation == "store":
                self.performance_metrics["total_stores"] += 1
                if success:
                    self.performance_metrics["successful_stores"] += 1
                else:
                    self.performance_metrics["failed_stores"] += 1
                total_time = self.performance_metrics["average_store_time_ms"] * (self.performance_metrics["total_stores"] - 1)
                self.performance_metrics["average_store_time_ms"] = (total_time + latency) / self.performance_metrics["total_stores"]
            elif operation == "retrieve":
                self.performance_metrics["total_retrievals"] += 1
                if success:
                    self.performance_metrics["successful_retrievals"] += 1
                else:
                    self.performance_metrics["failed_retrievals"] += 1
                total_time = self.performance_metrics["average_retrieval_time_ms"] * (self.performance_metrics["total_retrievals"] - 1)
                self.performance_metrics["average_retrieval_time_ms"] = (total_time + latency) / self.performance_metrics["total_retrievals"]
            self.last_updated = time.time()

    def apply_retention_policy(self) -> int:
        """Apply retention policy to remove expired items. Returns number of items removed."""
        raise NotImplementedError(f"Retention policy application not implemented for memory storage {self.name}")

# Implementation of Short-term Memory Storage
class ShortTermMemoryStorage(MemoryStorage):
    """Implementation of short-term memory storage for temporary data."""
    def __init__(self, config: Dict[str, Any]):
        super().__init__("ShortTermMemory", config)
        self.memory: Dict[str, Dict[str, Any]] = {}
        self.retention_period = config.get("retention_period", 3600)  # 1 hour default for short-term

    def store(self, key: str, value: Any, metadata: Optional[Dict[str, Any]] = None,
              context: Optional[Dict[str, Any]] = None) -> bool:
        """Store a memory item in short-term memory."""
        if not self.active:
            raise MemoryError(f"Short-term memory storage {self.name} is not active")
        if len(self.memory) >= self.capacity:
            raise MemoryStorageFullError(f"Short-term memory storage {self.name} capacity exceeded")
        role = context.get("role", "default") if context else "default"
        if not self.enforce_security("write", key, role):
            raise MemoryAccessDeniedError(f"Write access denied for key {key} in short-term memory")
        start_time = time.time()
        try:
            timestamp = time.time()
            item = {
                "value": value,
                "metadata": metadata or {},
                "timestamp": timestamp,
                "context": context or {}
            }
            self.memory[key] = item
            end_time = time.time()
            self.update_performance_metrics("store", start_time, end_time, success=True)
            self.memory_log.append(f"Stored key {key} in short-term memory at {datetime.now().isoformat()}")
            return True
        except Exception as e:
            end_time = time.time()
            self.update_performance_metrics("store", start_time, end_time, success=False)
            self.memory_log.append(f"Failed to store key {key} in short-term memory: {str(e)} at {datetime.now().isoformat()}")
            raise MemoryError(f"Error storing key {key} in short-term memory: {str(e)}")

    def retrieve(self, key: str, context: Optional[Dict[str, Any]] = None) -> Any:
        """Retrieve a memory item from short-term memory by key."""
        if not self.active:
            raise MemoryError(f"Short-term memory storage {self.name} is not active")
        role = context.get("role", "default") if context else "default"
        if not self.enforce_security("read", key, role):
            raise MemoryAccessDeniedError(f"Read access denied for key {key} in short-term memory")
        start_time = time.time()
        try:
            if key in self.memory:
                item = self.memory[key]
                end_time = time.time()
                self.update_performance_metrics("retrieve", start_time, end_time, success=True)
                self.memory_log.append(f"Retrieved key {key} from short-term memory at {datetime.now().isoformat()}")
                return item["value"]
            else:
                end_time = time.time()
                self.update_performance_metrics("retrieve", start_time, end_time, success=False)
                self.memory_log.append(f"Key {key} not found in short-term memory at {datetime.now().isoformat()}")
                raise MemoryNotFoundError(f"Key {key} not found in short-term memory")
        except Exception as e:
            end_time = time.time()
            self.update_performance_metrics("retrieve", start_time, end_time, success=False)
            self.memory_log.append(f"Failed to retrieve key {key} from short-term memory: {str(e)} at {datetime.now().isoformat()}")
            raise MemoryError(f"Error retrieving key {key} from short-term memory: {str(e)}")

    def search(self, query: Dict[str, Any], limit: int = 10, context: Optional[Dict[str, Any]] = None) -> List[Any]:
        """Search short-term memory items based on a query dictionary."""
        if not self.active:
            raise MemoryError(f"Short-term memory storage {self.name} is not active")
        role = context.get("role", "default") if context else "default"
        start_time = time.time()
        try:
            results = []
            for key, item in self.memory.items():
                if self.enforce_security("read", key, role):
                    match = True
                    for q_key, q_value in query.items():
                        if q_key in item["metadata"] and item["metadata"][q_key] != q_value:
                            match = False
                            break
                        elif q_key in item["context"] and item["context"][q_key] != q_value:
                            match = False
                            break
                    if match:
                        results.append({"key": key, "value": item["value"], "metadata": item["metadata"]})
                if len(results) >= limit:
                    break
            end_time = time.time()
            self.update_performance_metrics("retrieve", start_time, end_time, success=True)
            self.memory_log.append(f"Searched short-term memory with query {query} at {datetime.now().isoformat()}")
            return results
        except Exception as e:
            end_time = time.time()
            self.update_performance_metrics("retrieve", start_time, end_time, success=False)
            self.memory_log.append(f"Failed to search short-term memory: {str(e)} at {datetime.now().isoformat()}")
            raise MemoryError(f"Error searching short-term memory: {str(e)}")

    def delete(self, key: str, context: Optional[Dict[str, Any]] = None) -> bool:
        """Delete a memory item from short-term memory by key."""
        if not self.active:
            raise MemoryError(f"Short-term memory storage {self.name} is not active")
        role = context.get("role", "default") if context else "default"
        if not self.enforce_security("write", key, role):
            raise MemoryAccessDeniedError(f"Write access denied for key {key} in short-term memory")
        start_time = time.time()
        try:
            if key in self.memory:
                del self.memory[key]
                end_time = time.time()
                self.update_performance_metrics("store", start_time, end_time, success=True)
                self.memory_log.append(f"Deleted key {key} from short-term memory at {datetime.now().isoformat()}")
                return True
            else:
                end_time = time.time()
                self.update_performance_metrics("store", start_time, end_time, success=False)
                self.memory_log.append(f"Key {key} not found for deletion in short-term memory at {datetime.now().isoformat()}")
                return False
        except Exception as e:
            end_time = time.time()
            self.update_performance_metrics("store", start_time, end_time, success=False)
            self.memory_log.append(f"Failed to delete key {key} from short-term memory: {str(e)} at {datetime.now().isoformat()}")
            raise MemoryError(f"Error deleting key {key} from short-term memory: {str(e)}")

    def apply_retention_policy(self) -> int:
        """Apply retention policy to remove expired items from short-term memory."""
        if not self.active:
            raise MemoryError(f"Short-term memory storage {self.name} is not active")
        with self.lock:
            current_time = time.time()
            initial_count = len(self.memory)
            expired_keys = [
                key for key, item in self.memory.items()
                if self.retention_policy == "time_based" and (current_time - item["timestamp"]) > self.retention_period
            ]
            for key in expired_keys:
                del self.memory[key]
            removed_count = initial_count - len(self.memory)
            if removed_count > 0:
                self.memory_log.append(f"Applied retention policy, removed {removed_count} items from short-term memory at {datetime.now().isoformat()}")
            return removed_count

# Implementation of Long-term Memory Storage
class LongTermMemoryStorage(MemoryStorage):
    """Implementation of long-term memory storage for persistent data using SQLite."""
    def __init__(self, config: Dict[str, Any]):
        super().__init__("LongTermMemory", config)
        self.db_path = config.get("db_path", "long_term_memory.db")
        self.retention_period = config.get("retention_period", 31536000)  # 1 year default for long-term
        self.conn = None
        self.cursor = None
        self.index_table = "memory_index"

    def activate(self) -> None:
        """Activate the long-term memory storage by connecting to SQLite database."""
        with self.lock:
            try:
                self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
                self.cursor = self.conn.cursor()
                # Create table if not exists
                self.cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.index_table} (
                        key TEXT PRIMARY KEY,
                        value BLOB,
                        metadata TEXT,
                        timestamp REAL,
                        context TEXT
                    )
                """)
                self.conn.commit()
                self.active = True
                self.memory_log.append(f"Long-term memory storage {self.name} activated with DB {self.db_path} at {datetime.now().isoformat()}")
            except Exception as e:
                self.memory_log.append(f"Failed to activate long-term memory storage: {str(e)} at {datetime.now().isoformat()}")
                raise MemoryError(f"Failed to connect to long-term memory database: {str(e)}")
            finally:
                self.last_updated = time.time()

    def deactivate(self) -> None:
        """Deactivate the long-term memory storage by closing database connection."""
        with self.lock:
            if self.conn:
                self.conn.close()
                self.conn = None
                self.cursor = None
            self.active = False
            self.memory_log.append(f"Long-term memory storage {self.name} deactivated at {datetime.now().isoformat()}")
            self.last_updated = time.time()

    def store(self, key: str, value: Any, metadata: Optional[Dict[str, Any]] = None,
              context: Optional[Dict[str, Any]] = None) -> bool:
        """Store a memory item in long-term memory."""
        if not self.active:
            raise MemoryError(f"Long-term memory storage {self.name} is not active")
        role = context.get("role", "default") if context else "default"
        if not self.enforce_security("write", key, role):
            raise MemoryAccessDeniedError(f"Write access denied for key {key} in long-term memory")
        start_time = time.time()
        try:
            timestamp = time.time()
            value_blob = pickle.dumps(value)
            metadata_json = json.dumps(metadata or {})
            context_json = json.dumps(context or {})
            with self.lock:
                self.cursor.execute(f"""
                    INSERT OR REPLACE INTO {self.index_table} (key, value, metadata, timestamp, context)
                    VALUES (?, ?, ?, ?, ?)
                """, (key, value_blob, metadata_json, timestamp, context_json))
                self.conn.commit()
            end_time = time.time()
            self.update_performance_metrics("store", start_time, end_time, success=True)
            self.memory_log.append(f"Stored key {key} in long-term memory at {datetime.now().isoformat()}")
            return True
        except Exception as e:
            end_time = time.time()
            self.update_performance_metrics("store", start_time, end_time, success=False)
            self.memory_log.append(f"Failed to store key {key} in long-term memory: {str(e)} at {datetime.now().isoformat()}")
            raise MemoryError(f"Error storing key {key} in long-term memory: {str(e)}")

    def retrieve(self, key: str, context: Optional[Dict[str, Any]] = None) -> Any:
        """Retrieve a memory item from long-term memory by key."""
        if not self.active:
            raise MemoryError(f"Long-term memory storage {self.name} is not active")
        role = context.get("role", "default") if context else "default"
        if not self.enforce_security("read", key, role):
            raise MemoryAccessDeniedError(f"Read access denied for key {key} in long-term memory")
        start_time = time.time()
        try:
            with self.lock:
                self.cursor.execute(f"SELECT value FROM {self.index_table} WHERE key = ?", (key,))
                result = self.cursor.fetchone()
            if result:
                value = pickle.loads(result[0])
                end_time = time.time()
                self.update_performance_metrics("retrieve", start_time, end_time, success=True)
                self.memory_log.append(f"Retrieved key {key} from long-term memory at {datetime.now().isoformat()}")
                return value
            else:
                end_time = time.time()
                self.update_performance_metrics("retrieve", start_time, end_time, success=False)
                self.memory_log.append(f"Key {key} not found in long-term memory at {datetime.now().isoformat()}")
                raise MemoryNotFoundError(f"Key {key} not found in long-term memory")
        except Exception as e:
            end_time = time.time()
            self.update_performance_metrics("retrieve", start_time, end_time, success=False)
            self.memory_log.append(f"Failed to retrieve key {key} from long-term memory: {str(e)} at {datetime.now().isoformat()}")
            raise MemoryError(f"Error retrieving key {key} from long-term memory: {str(e)}")

    def search(self, query: Dict[str, Any], limit: int = 10, context: Optional[Dict[str, Any]] = None) -> List[Any]:
        """Search long-term memory items based on a query dictionary."""
        if not self.active:
            raise MemoryError(f"Long-term memory storage {self.name} is not active")
        role = context.get("role", "default") if context else "default"
        start_time = time.time()
        try:
            results = []
            with self.lock:
                self.cursor.execute(f"SELECT key, value, metadata FROM {self.index_table}")
                rows = self.cursor.fetchall()
                for row in rows:
                    key, value_blob, metadata_json = row
                    if self.enforce_security("read", key, role):
                        metadata = json.loads(metadata_json) if metadata_json else {}
                        match = True
                        for q_key, q_value in query.items():
                            if q_key in metadata and metadata[q_key] != q_value:
                                match = False
                                break
                        if match:
                            value = pickle.loads(value_blob)
                            results.append({"key": key, "value": value, "metadata": metadata})
                    if len(results) >= limit:
                        break
            end_time = time.time()
            self.update_performance_metrics("retrieve", start_time, end_time, success=True)
            self.memory_log.append(f"Searched long-term memory with query {query} at {datetime.now().isoformat()}")
            return results
        except Exception as e:
            end_time = time.time()
            self.update_performance_metrics("retrieve", start_time, end_time, success=False)
            self.memory_log.append(f"Failed to search long-term memory: {str(e)} at {datetime.now().isoformat()}")
            raise MemoryError(f"Error searching long-term memory: {str(e)}")

    def delete(self, key: str, context: Optional[Dict[str, Any]] = None) -> bool:
        """Delete a memory item from long-term memory by key."""
        if not self.active:
            raise MemoryError(f"Long-term memory storage {self.name} is not active")
        role = context.get("role", "default") if context else "default"
        if not self.enforce_security("write", key, role):
            raise MemoryAccessDeniedError(f"Write access denied for key {key} in long-term memory")
        start_time = time.time()
        try:
            with self.lock:
                self.cursor.execute(f"DELETE FROM {self.index_table} WHERE key = ?", (key,))
                self.conn.commit()
                if self.cursor.rowcount > 0:
                    end_time = time.time()
                    self.update_performance_metrics("store", start_time, end_time, success=True)
                    self.memory_log.append(f"Deleted key {key} from long-term memory at {datetime.now().isoformat()}")
                    return True
                else:
                    end_time = time.time()
                    self.update_performance_metrics("store", start_time, end_time, success=False)
                    self.memory_log.append(f"Key {key} not found for deletion in long-term memory at {datetime.now().isoformat()}")
                    return False
        except Exception as e:
            end_time = time.time()
            self.update_performance_metrics("store", start_time, end_time, success=False)
            self.memory_log.append(f"Failed to delete key {key} from long-term memory: {str(e)} at {datetime.now().isoformat()}")
            raise MemoryError(f"Error deleting key {key} from long-term memory: {str(e)}")

    def apply_retention_policy(self) -> int:
        """Apply retention policy to remove expired items from long-term memory."""
        if not self.active:
            raise MemoryError(f"Long-term memory storage {self.name} is not active")
        with self.lock:
            current_time = time.time()
            try:
                self.cursor.execute(f"""
                    DELETE FROM {self.index_table}
                    WHERE timestamp < ?
                """, (current_time - self.retention_period,))
                self.conn.commit()
                removed_count = self.cursor.rowcount
                if removed_count > 0:
                    self.memory_log.append(f"Applied retention policy, removed {removed_count} items from long-term memory at {datetime.now().isoformat()}")
                return removed_count
            except Exception as e:
                self.memory_log.append(f"Failed to apply retention policy in long-term memory: {str(e)} at {datetime.now().isoformat()}")
                raise MemoryError(f"Error applying retention policy in long-term memory: {str(e)}")

# Implementation of External Memory Storage (placeholder for cloud or distributed storage)
class ExternalMemoryStorage(MemoryStorage):
    """Implementation of external memory storage for offloading large datasets or shared knowledge."""
    def __init__(self, config: Dict[str, Any]):
        super().__init__("ExternalMemory", config)
        self.endpoint = config.get("endpoint", "https://api.external.storage")
        self.credentials = config.get("credentials", {"api_key": "placeholder"})
        self.retention_period = config.get("retention_period", 63072000)  # 2 years default for external
        self.storage_client = None

    def activate(self) -> None:
        """Activate the external memory storage by connecting to the external service."""
        with self.lock:
            try:
                # Placeholder for connecting to external storage API
                self.active = True
                self.memory_log.append(f"External memory storage {self.name} activated with endpoint {self.endpoint} at {datetime.now().isoformat()}")
            except Exception as e:
                self.memory_log.append(f"Failed to activate external memory storage: {str(e)} at {datetime.now().isoformat()}")
                raise MemoryError(f"Failed to connect to external memory storage: {str(e)}")
            finally:
                self.last_updated = time.time()

    def deactivate(self) -> None:
        """Deactivate the external memory storage."""
        with self.lock:
            self.active = False
            self.memory_log.append(f"External memory storage {self.name} deactivated at {datetime.now().isoformat()}")
            self.last_updated = time.time()

    def store(self, key: str, value: Any, metadata: Optional[Dict[str, Any]] = None,
              context: Optional[Dict[str, Any]] = None) -> bool:
        """Store a memory item in external memory."""
        if not self.active:
            raise MemoryError(f"External memory storage {self.name} is not active")
        role = context.get("role", "default") if context else "default"
        if not self.enforce_security("write", key, role):
            raise MemoryAccessDeniedError(f"Write access denied for key {key} in external memory")
        start_time = time.time()
        try:
            # Simulate storing data in external storage
            end_time = time.time()
            self.update_performance_metrics("store", start_time, end_time, success=True)
            self.memory_log.append(f"Stored key {key} in external memory at {datetime.now().isoformat()}")
            return True
        except Exception as e:
            end_time = time.time()
            self.update_performance_metrics("store", start_time, end_time, success=False)
            self.memory_log.append(f"Failed to store key {key} in external memory: {str(e)} at {datetime.now().isoformat()}")
            raise MemoryError(f"Error storing key {key} in external memory: {str(e)}")

    def retrieve(self, key: str, context: Optional[Dict[str, Any]] = None) -> Any:
        """Retrieve a memory item from external memory by key."""
        if not self.active:
            raise MemoryError(f"External memory storage {self.name} is not active")
        role = context.get("role", "default") if context else "default"
        if not self.enforce_security("read", key, role):
            raise MemoryAccessDeniedError(f"Read access denied for key {key} in external memory")
        start_time = time.time()
        try:
            # Simulate retrieving data from external storage
            dummy_value = f"Value for {key} from external storage"
            end_time = time.time()
            self.update_performance_metrics("retrieve", start_time, end_time, success=True)
            self.memory_log.append(f"Retrieved key {key} from external memory at {datetime.now().isoformat()}")
            return dummy_value
        except Exception as e:
            end_time = time.time()
            self.update_performance_metrics("retrieve", start_time, end_time, success=False)
            self.memory_log.append(f"Failed to retrieve key {key} from external memory: {str(e)} at {datetime.now().isoformat()}")
            raise MemoryError(f"Error retrieving key {key} from external memory: {str(e)}")

    def search(self, query: Dict[str, Any], limit: int = 10, context: Optional[Dict[str, Any]] = None) -> List[Any]:
        """Search external memory items based on a query dictionary."""
        if not self.active:
            raise MemoryError(f"External memory storage {self.name} is not active")
        role = context.get("role", "default") if context else "default"
        start_time = time.time()
        try:
            # Simulate searching data in external storage
            dummy_results = [
                {"key": f"key_{i}", "value": f"Value {i} from external storage", "metadata": query}
                for i in range(min(limit, 5))
            ]
            end_time = time.time()
            self.update_performance_metrics("retrieve", start_time, end_time, success=True)
            self.memory_log.append(f"Searched external memory with query {query} at {datetime.now().isoformat()}")
            return dummy_results
        except Exception as e:
            end_time = time.time()
            self.update_performance_metrics("retrieve", start_time, end_time, success=False)
            self.memory_log.append(f"Failed to search external memory: {str(e)} at {datetime.now().isoformat()}")
            raise MemoryError(f"Error searching external memory: {str(e)}")

    def delete(self, key: str, context: Optional[Dict[str, Any]] = None) -> bool:
        """Delete a memory item from external memory by key."""
        if not self.active:
            raise MemoryError(f"External memory storage {self.name} is not active")
        role = context.get("role", "default") if context else "default"
        if not self.enforce_security("write", key, role):
            raise MemoryAccessDeniedError(f"Write access denied for key {key} in external memory")
        start_time = time.time()
        try:
            # Simulate deleting data from external storage
            end_time = time.time()
            self.update_performance_metrics("store", start_time, end_time, success=True)
            self.memory_log.append(f"Deleted key {key} from external memory at {datetime.now().isoformat()}")
            return True
        except Exception as e:
            end_time = time.time()
            self.update_performance_metrics("store", start_time, end_time, success=False)
            self.memory_log.append(f"Failed to delete key {key} from external memory: {str(e)} at {datetime.now().isoformat()}")
            raise MemoryError(f"Error deleting key {key} from external memory: {str(e)}")

    def apply_retention_policy(self) -> int:
        """Apply retention policy to remove expired items from external memory."""
        if not self.active:
            raise MemoryError(f"External memory storage {self.name} is not active")
        with self.lock:
            try:
                # Simulate applying retention policy in external storage
                removed_count = 0  # Placeholder value
                if removed_count > 0:
                    self.memory_log.append(f"Applied retention policy, removed {removed_count} items from external memory at {datetime.now().isoformat()}")
                return removed_count
            except Exception as e:
                self.memory_log.append(f"Failed to apply retention policy in external memory: {str(e)} at {datetime.now().isoformat()}")
                raise MemoryError(f"Error applying retention policy in external memory: {str(e)}")

# Implementation of Semantic Index for memory retrieval
class SemanticIndex:
    """Implementation of a semantic index for efficient memory retrieval using embeddings."""
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.dimension = config.get("embedding_dimension", 128)
        self.index = defaultdict(list)  # Simple in-memory index for demonstration
        self.embeddings: Dict[str, np.ndarray] = {}
        self.active = False
        self.lock = threading.Lock()
        self.performance_metrics = {
            "total_indexing": 0,
            "successful_indexing": 0,
            "failed_indexing": 0,
            "total_searches": 0,
            "successful_searches": 0,
            "failed_searches": 0,
            "average_indexing_time_ms": 0.0,
            "average_search_time_ms": 0.0
        }
        self.index_log: List[str] = []
        self.last_updated = time.time()

    def activate(self) -> None:
        """Activate the semantic index."""
        with self.lock:
            self.active = True
            self.index_log.append(f"Semantic index {self.name} activated at {datetime.now().isoformat()}")
            self.last_updated = time.time()

    def deactivate(self) -> None:
        """Deactivate the semantic index."""
        with self.lock:
            self.active = False
            self.index_log.append(f"Semantic index {self.name} deactivated at {datetime.now().isoformat()}")
            self.last_updated = time.time()

    def add(self, key: str, embedding: np.ndarray, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Add an item to the semantic index with its embedding."""
        if not self.active:
            raise MemoryError(f"Semantic index {self.name} is not active")
        if embedding.shape[0] != self.dimension:
            raise MemoryError(f"Embedding dimension mismatch for key {key}: expected {self.dimension}, got {embedding.shape[0]}")
        start_time = time.time()
        try:
            with self.lock:
                self.embeddings[key] = embedding
                self.index[key].append(metadata or {})
            end_time = time.time()
            self.performance_metrics["total_indexing"] += 1
            self.performance_metrics["successful_indexing"] += 1
            total_time = self.performance_metrics["average_indexing_time_ms"] * (self.performance_metrics["total_indexing"] - 1)
            self.performance_metrics["average_indexing_time_ms"] = (total_time + (end_time - start_time) * 1000) / self.performance_metrics["total_indexing"]
            self.index_log.append(f"Added key {key} to semantic index at {datetime.now().isoformat()}")
            self.last_updated = time.time()
            return True
        except Exception as e:
            end_time = time.time()
            self.performance_metrics["total_indexing"] += 1
            self.performance_metrics["failed_indexing"] += 1
            total_time = self.performance_metrics["average_indexing_time_ms"] * (self.performance_metrics["total_indexing"] - 1)
            self.performance_metrics["average_indexing_time_ms"] = (total_time + (end_time - start_time) * 1000) / self.performance_metrics["total_indexing"]
            self.index_log.append(f"Failed to add key {key} to semantic index: {str(e)} at {datetime.now().isoformat()}")
            raise MemoryError(f"Error adding key {key} to semantic index: {str(e)}")

    def search_similar(self, query_embedding: np.ndarray, limit: int = 10) -> List[Dict[str, Any]]:
        """Search for items similar to the query embedding."""
        if not self.active:
            raise MemoryError(f"Semantic index {self.name} is not active")
        if query_embedding.shape[0] != self.dimension:
            raise MemoryError(f"Query embedding dimension mismatch: expected {self.dimension}, got {query_embedding.shape[0]}")
        start_time = time.time()
        try:
            with self.lock:
                similarities = []
                for key, embedding in self.embeddings.items():
                    # Compute cosine similarity
                    similarity = np.dot(embedding, query_embedding) / (np.linalg.norm(embedding) * np.linalg.norm(query_embedding))
                    similarities.append({"key": key, "similarity": similarity, "metadata": self.index[key][0] if self.index[key] else {}})
                similarities.sort(key=lambda x: x["similarity"], reverse=True)
                results = similarities[:limit]
            end_time = time.time()
            self.performance_metrics["total_searches"] += 1
            self.performance_metrics["successful_searches"] += 1
            total_time = self.performance_metrics["average_search_time_ms"] * (self.performance_metrics["total_searches"] - 1)
            self.performance_metrics["average_search_time_ms"] = (total_time + (end_time - start_time) * 1000) / self.performance_metrics["total_searches"]
            self.index_log.append(f"Searched semantic index for similar items at {datetime.now().isoformat()}")
            self.last_updated = time.time()
            return results
        except Exception as e:
            end_time = time.time()
            self.performance_metrics["total_searches"] += 1
            self.performance_metrics["failed_searches"] += 1
            total_time = self.performance_metrics["average_search_time_ms"] * (self.performance_metrics["total_searches"] - 1)
            self.performance_metrics["average_search_time_ms"] = (total_time + (end_time - start_time) * 1000) / self.performance_metrics["total_searches"]
            self.index_log.append(f"Failed to search semantic index: {str(e)} at {datetime.now().isoformat()}")
            raise MemoryError(f"Error searching semantic index: {str(e)}")

    def remove(self, key: str) -> bool:
        """Remove an item from the semantic index."""
        if not self.active:
            raise MemoryError(f"Semantic index {self.name} is not active")
        start_time = time.time()
        try:
            with self.lock:
                if key in self.embeddings:
                    del self.embeddings[key]
                    del self.index[key]
                    end_time = time.time()
                    self.performance_metrics["total_indexing"] += 1
                    self.performance_metrics["successful_indexing"] += 1
                    total_time = self.performance_metrics["average_indexing_time_ms"] * (self.performance_metrics["total_indexing"] - 1)
                    self.performance_metrics["average_indexing_time_ms"] = (total_time + (end_time - start_time) * 1000) / self.performance_metrics["total_indexing"]
                    self.index_log.append(f"Removed key {key} from semantic index at {datetime.now().isoformat()}")
                    self.last_updated = time.time()
                    return True
                else:
                    end_time = time.time()
                    self.performance_metrics["total_indexing"] += 1
                    self.performance_metrics["failed_indexing"] += 1
                    total_time = self.performance_metrics["average_indexing_time_ms"] * (self.performance_metrics["total_indexing"] - 1)
                    self.performance_metrics["average_indexing_time_ms"] = (total_time + (end_time - start_time) * 1000) / self.performance_metrics["total_indexing"]
                    self.index_log.append(f"Key {key} not found in semantic index for removal at {datetime.now().isoformat()}")
                    return False
        except Exception as e:
            end_time = time.time()
            self.performance_metrics["total_indexing"] += 1
            self.performance_metrics["failed_indexing"] += 1
            total_time = self.performance_metrics["average_indexing_time_ms"] * (self.performance_metrics["total_indexing"] - 1)
            self.performance_metrics["average_indexing_time_ms"] = (total_time + (end_time - start_time) * 1000) / self.performance_metrics["total_indexing"]
            self.index_log.append(f"Failed to remove key {key} from semantic index: {str(e)} at {datetime.now().isoformat()}")
            raise MemoryError(f"Error removing key {key} from semantic index: {str(e)}")

# Manager class for handling multiple memory storage types
class MemoryManager:
    """Manages multiple memory storage types and semantic indexing for efficient memory operations."""
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.storages: Dict[str, MemoryStorage] = {}
        self.semantic_index: Optional[SemanticIndex] = None
        self.active = False
        self.lock = threading.Lock()
        self.performance_metrics = {
            "total_memory_operations": 0,
            "successful_memory_operations": 0,
            "failed_memory_operations": 0,
            "average_operation_time_ms": 0.0
        }
        self.operation_log: List[str] = []
        self.last_operation = time.time()
        self.memory_selection_strategy = config.get("selection_strategy", "tiered")
        self.memory_tiers = config.get("memory_tiers", {
            "ShortTermMemory": 1,
            "LongTermMemory": 2,
            "ExternalMemory": 3
        })

    def add_storage(self, storage: MemoryStorage) -> None:
        """Add a memory storage to the manager."""
        with self.lock:
            self.storages[storage.name] = storage
            self.operation_log.append(f"Added storage {storage.name} to manager {self.name} at {datetime.now().isoformat()}")
            self.last_operation = time.time()

    def remove_storage(self, storage_name: str) -> None:
        """Remove a memory storage from the manager."""
        with self.lock:
            if storage_name in self.storages:
                storage = self.storages[storage_name]
                if storage.active:
                    storage.deactivate()
                del self.storages[storage_name]
                self.operation_log.append(f"Removed storage {storage_name} from manager {self.name} at {datetime.now().isoformat()}")
            else:
                self.operation_log.append(f"Storage {storage_name} not found in manager {self.name} at {datetime.now().isoformat()}")
            self.last_operation = time.time()

    def set_semantic_index(self, index: SemanticIndex) -> None:
        """Set the semantic index for the manager."""
        with self.lock:
            self.semantic_index = index
            self.operation_log.append(f"Set semantic index {index.name} for manager {self.name} at {datetime.now().isoformat()}")
            self.last_operation = time.time()

    def activate(self) -> None:
        """Activate the memory manager and all storages."""
        with self.lock:
            self.active = True
            for storage_name, storage in self.storages.items():
                try:
                    if not storage.active:
                        storage.activate()
                    self.operation_log.append(f"Activated storage {storage_name} in manager {self.name} at {datetime.now().isoformat()}")
                except Exception as e:
                    self.operation_log.append(f"Failed to activate storage {storage_name}: {str(e)} at {datetime.now().isoformat()}")
            if self.semantic_index and not self.semantic_index.active:
                self.semantic_index.activate()
                self.operation_log.append(f"Activated semantic index in manager {self.name} at {datetime.now().isoformat()}")
            self.last_operation = time.time()

    def deactivate(self) -> None:
        """Deactivate the memory manager and all storages."""
        with self.lock:
            self.active = False
            for storage_name, storage in self.storages.items():
                try:
                    if storage.active:
                        storage.deactivate()
                    self.operation_log.append(f"Deactivated storage {storage_name} in manager {self.name} at {datetime.now().isoformat()}")
                except Exception as e:
                    self.operation_log.append(f"Failed to deactivate storage {storage_name}: {str(e)} at {datetime.now().isoformat()}")
            if self.semantic_index and self.semantic_index.active:
                self.semantic_index.deactivate()
                self.operation_log.append(f"Deactivated semantic index in manager {self.name} at {datetime.now().isoformat()}")
            self.last_operation = time.time()

    def select_storage(self, context: Dict[str, Any], operation: str = "store") -> MemoryStorage:
        """Select the most appropriate storage based on context and strategy."""
        if not self.active:
            raise MemoryError(f"Memory Manager {self.name} is not active")
        with self.lock:
            if not self.storages:
                raise MemoryError(f"No storages available in manager {self.name}")
            if self.memory_selection_strategy == "tiered":
                available_storages = [s for s in self.storages.values() if s.active]
                if not available_storages:
                    raise MemoryError(f"No active storages available in manager {self.name}")
                selected_storage = min(available_storages, key=lambda s: self.memory_tiers.get(s.name, 999))
                self.operation_log.append(f"Selected storage {selected_storage.name} based on tier for {operation} at {datetime.now().isoformat()}")
                return selected_storage
            else:
                # Placeholder for other selection strategies (e.g., latency-based, capacity-based)
                for storage in self.storages.values():
                    if storage.active:
                        self.operation_log.append(f"Selected storage {storage.name} based on default for {operation} at {datetime.now().isoformat()}")
                        return storage
                raise MemoryError(f"No suitable storage selected in manager {self.name}")

    def store_memory(self, key: str, value: Any, metadata: Optional[Dict[str, Any]] = None,
                     context: Optional[Dict[str, Any]] = None, storage_name: Optional[str] = None,
                     embedding: Optional[np.ndarray] = None) -> bool:
        """Store a memory item in the selected or specified storage."""
        if not self.active:
            raise MemoryError(f"Memory Manager {self.name} is not active")
        with self.lock:
            start_time = time.time()
            try:
                if storage_name:
                    if storage_name not in self.storages:
                        raise MemoryError(f"Specified storage {storage_name} not found in manager {self.name}")
                    selected_storage = self.storages[storage_name]
                    if not selected_storage.active:
                        raise MemoryError(f"Specified storage {storage_name} is not active in manager {self.name}")
                else:
                    selected_storage = self.select_storage(context or {}, "store")
                
                result = selected_storage.store(key, value, metadata, context)
                if embedding is not None and self.semantic_index and self.semantic_index.active:
                    self.semantic_index.add(key, embedding, metadata)
                
                end_time = time.time()
                self.performance_metrics["total_memory_operations"] += 1
                self.performance_metrics["successful_memory_operations"] += 1
                total_time = self.performance_metrics["average_operation_time_ms"] * (self.performance_metrics["total_memory_operations"] - 1)
                self.performance_metrics["average_operation_time_ms"] = (total_time + (end_time - start_time) * 1000) / self.performance_metrics["total_memory_operations"]
                self.operation_log.append(f"Stored memory key {key} using {selected_storage.name} at {datetime.now().isoformat()}")
                self.last_operation = time.time()
                return result
            except MemoryError as e:
                end_time = time.time()
                self.performance_metrics["total_memory_operations"] += 1
                self.performance_metrics["failed_memory_operations"] += 1
                total_time = self.performance_metrics["average_operation_time_ms"] * (self.performance_metrics["total_memory_operations"] - 1)
                self.performance_metrics["average_operation_time_ms"] = (total_time + (end_time - start_time) * 1000) / self.performance_metrics["total_memory_operations"]
                self.operation_log.append(f"Failed to store memory key {key}: {str(e)} at {datetime.now().isoformat()}")
                raise
            except Exception as e:
                end_time = time.time()
                self.performance_metrics["total_memory_operations"] += 1
                self.performance_metrics["failed_memory_operations"] += 1
                total_time = self.performance_metrics["average_operation_time_ms"] * (self.performance_metrics["total_memory_operations"] - 1)
                self.performance_metrics["average_operation_time_ms"] = (total_time + (end_time - start_time) * 1000) / self.performance_metrics["total_memory_operations"]
                self.operation_log.append(f"Unexpected error storing memory key {key}: {str(e)} at {datetime.now().isoformat()}")
                raise MemoryError(f"Unexpected error in manager {self.name} while storing memory key {key}: {str(e)}")

    def retrieve_memory(self, key: str, context: Optional[Dict[str, Any]] = None,
                        storage_name: Optional[str] = None) -> Any:
        """Retrieve a memory item from the selected or specified storage."""
        if not self.active:
            raise MemoryError(f"Memory Manager {self.name} is not active")
        with self.lock:
            start_time = time.time()
            try:
                if storage_name:
                    if storage_name not in self.storages:
                        raise MemoryError(f"Specified storage {storage_name} not found in manager {self.name}")
                    selected_storage = self.storages[storage_name]
                    if not selected_storage.active:
                        raise MemoryError(f"Specified storage {storage_name} is not active in manager {self.name}")
                else:
                    selected_storage = self.select_storage(context or {}, "retrieve")
                
                result = selected_storage.retrieve(key, context)
                end_time = time.time()
                self.performance_metrics["total_memory_operations"] += 1
                self.performance_metrics["successful_memory_operations"] += 1
                total_time = self.performance_metrics["average_operation_time_ms"] * (self.performance_metrics["total_memory_operations"] - 1)
                self.performance_metrics["average_operation_time_ms"] = (total_time + (end_time - start_time) * 1000) / self.performance_metrics["total_memory_operations"]
                self.operation_log.append(f"Retrieved memory key {key} using {selected_storage.name} at {datetime.now().isoformat()}")
                self.last_operation = time.time()
                return result
            except MemoryNotFoundError as e:
                end_time = time.time()
                self.performance_metrics["total_memory_operations"] += 1
                self.performance_metrics["failed_memory_operations"] += 1
                total_time = self.performance_metrics["average_operation_time_ms"] * (self.performance_metrics["total_memory_operations"] - 1)
                self.performance_metrics["average_operation_time_ms"] = (total_time + (end_time - start_time) * 1000) / self.performance_metrics["total_memory_operations"]
                self.operation_log.append(f"Memory key {key} not found: {str(e)} at {datetime.now().isoformat()}")
                raise
            except MemoryError as e:
                end_time = time.time()
                self.performance_metrics["total_memory_operations"] += 1
                self.performance_metrics["failed_memory_operations"] += 1
                total_time = self.performance_metrics["average_operation_time_ms"] * (self.performance_metrics["total_memory_operations"] - 1)
                self.performance_metrics["average_operation_time_ms"] = (total_time + (end_time - start_time) * 1000) / self.performance_metrics["total_memory_operations"]
                self.operation_log.append(f"Failed to retrieve memory key {key}: {str(e)} at {datetime.now().isoformat()}")
                raise
            except Exception as e:
                end_time = time.time()
                self.performance_metrics["total_memory_operations"] += 1
                self.performance_metrics["failed_memory_operations"] += 1
                total_time = self.performance_metrics["average_operation_time_ms"] * (self.performance_metrics["total_memory_operations"] - 1)
                self.performance_metrics["average_operation_time_ms"] = (total_time + (end_time - start_time) * 1000) / self.performance_metrics["total_memory_operations"]
                self.operation_log.append(f"Unexpected error retrieving memory key {key}: {str(e)} at {datetime.now().isoformat()}")
                raise MemoryError(f"Unexpected error in manager {self.name} while retrieving memory key {key}: {str(e)}")

    def search_memory(self, query: Dict[str, Any], limit: int = 10, context: Optional[Dict[str, Any]] = None,
                      storage_name: Optional[str] = None) -> List[Any]:
        """Search memory items in the selected or specified storage."""
        if not self.active:
            raise MemoryError(f"Memory Manager {self.name} is not active")
        with self.lock:
            start_time = time.time()
            try:
                if storage_name:
                    if storage_name not in self.storages:
                        raise MemoryError(f"Specified storage {storage_name} not found in manager {self.name}")
                    selected_storage = self.storages[storage_name]
                    if not selected_storage.active:
                        raise MemoryError(f"Specified storage {storage_name} is not active in manager {self.name}")
                else:
                    selected_storage = self.select_storage(context or {}, "search")
                
                result = selected_storage.search(query, limit, context)
                end_time = time.time()
                self.performance_metrics["total_memory_operations"] += 1
                self.performance_metrics["successful_memory_operations"] += 1
                total_time = self.performance_metrics["average_operation_time_ms"] * (self.performance_metrics["total_memory_operations"] - 1)
                self.performance_metrics["average_operation_time_ms"] = (total_time + (end_time - start_time) * 1000) / self.performance_metrics["total_memory_operations"]
                self.operation_log.append(f"Searched memory with query {query} using {selected_storage.name} at {datetime.now().isoformat()}")
                self.last_operation = time.time()
                return result
            except MemoryError as e:
                end_time = time.time()
                self.performance_metrics["total_memory_operations"] += 1
                self.performance_metrics["failed_memory_operations"] += 1
                total_time = self.performance_metrics["average_operation_time_ms"] * (self.performance_metrics["total_memory_operations"] - 1)
                self.performance_metrics["average_operation_time_ms"] = (total_time + (end_time - start_time) * 1000) / self.performance_metrics["total_memory_operations"]
                self.operation_log.append(f"Failed to search memory with query {query}: {str(e)} at {datetime.now().isoformat()}")
                raise
            except Exception as e:
                end_time = time.time()
                self.performance_metrics["total_memory_operations"] += 1
                self.performance_metrics["failed_memory_operations"] += 1
                total_time = self.performance_metrics["average_operation_time_ms"] * (self.performance_metrics["total_memory_operations"] - 1)
                self.performance_metrics["average_operation_time_ms"] = (total_time + (end_time - start_time) * 1000) / self.performance_metrics["total_memory_operations"]
                self.operation_log.append(f"Unexpected error searching memory with query {query}: {str(e)} at {datetime.now().isoformat()}")
                raise MemoryError(f"Unexpected error in manager {self.name} while searching memory: {str(e)}")

    def search_semantic(self, query_embedding: np.ndarray, limit: int = 10, context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Search memory items using semantic similarity."""
        if not self.active:
            raise MemoryError(f"Memory Manager {self.name} is not active")
        if not self.semantic_index or not self.semantic_index.active:
            raise MemoryError(f"Semantic index is not active or not set in manager {self.name}")
        with self.lock:
            start_time = time.time()
            try:
                results = self.semantic_index.search_similar(query_embedding, limit)
                end_time = time.time()
                self.performance_metrics["total_memory_operations"] += 1
                self.performance_metrics["successful_memory_operations"] += 1
                total_time = self.performance_metrics["average_operation_time_ms"] * (self.performance_metrics["total_memory_operations"] - 1)
                self.performance_metrics["average_operation_time_ms"] = (total_time + (end_time - start_time) * 1000) / self.performance_metrics["total_memory_operations"]
                self.operation_log.append(f"Semantic search performed at {datetime.now().isoformat()}")
                self.last_operation = time.time()
                return results
            except MemoryError as e:
                end_time = time.time()
                self.performance_metrics["total_memory_operations"] += 1
                self.performance_metrics["failed_memory_operations"] += 1
                total_time = self.performance_metrics["average_operation_time_ms"] * (self.performance_metrics["total_memory_operations"] - 1)
                self.performance_metrics["average_operation_time_ms"] = (total_time + (end_time - start_time) * 1000) / self.performance_metrics["total_memory_operations"]
                self.operation_log.append(f"Failed semantic search: {str(e)} at {datetime.now().isoformat()}")
                raise
            except Exception as e:
                end_time = time.time()
                self.performance_metrics["total_memory_operations"] += 1
                self.performance_metrics["failed_memory_operations"] += 1
                total_time = self.performance_metrics["average_operation_time_ms"] * (self.performance_metrics["total_memory_operations"] - 1)
                self.performance_metrics["average_operation_time_ms"] = (total_time + (end_time - start_time) * 1000) / self.performance_metrics["total_memory_operations"]
                self.operation_log.append(f"Unexpected error in semantic search: {str(e)} at {datetime.now().isoformat()}")
                raise MemoryError(f"Unexpected error in manager {self.name} during semantic search: {str(e)}")

    def delete_memory(self, key: str, context: Optional[Dict[str, Any]] = None,
                      storage_name: Optional[str] = None) -> bool:
        """Delete a memory item from the selected or specified storage."""
        if not self.active:
            raise MemoryError(f"Memory Manager {self.name} is not active")
        with self.lock:
            start_time = time.time()
            try:
                if storage_name:
                    if storage_name not in self.storages:
                        raise MemoryError(f"Specified storage {storage_name} not found in manager {self.name}")
                    selected_storage = self.storages[storage_name]
                    if not selected_storage.active:
                        raise MemoryError(f"Specified storage {storage_name} is not active in manager {self.name}")
                else:
                    selected_storage = self.select_storage(context or {}, "delete")
                
                result = selected_storage.delete(key, context)
                if self.semantic_index and self.semantic_index.active:
                    self.semantic_index.remove(key)
                end_time = time.time()
                self.performance_metrics["total_memory_operations"] += 1
                self.performance_metrics["successful_memory_operations"] += 1
                total_time = self.performance_metrics["average_operation_time_ms"] * (self.performance_metrics["total_memory_operations"] - 1)
                self.performance_metrics["average_operation_time_ms"] = (total_time + (end_time - start_time) * 1000) / self.performance_metrics["total_memory_operations"]
                self.operation_log.append(f"Deleted memory key {key} using {selected_storage.name} at {datetime.now().isoformat()}")
                self.last_operation = time.time()
                return result
            except MemoryError as e:
                end_time = time.time()
                self.performance_metrics["total_memory_operations"] += 1
                self.performance_metrics["failed_memory_operations"] += 1
                total_time = self.performance_metrics["average_operation_time_ms"] * (self.performance_metrics["total_memory_operations"] - 1)
                self.performance_metrics["average_operation_time_ms"] = (total_time + (end_time - start_time) * 1000) / self.performance_metrics["total_memory_operations"]
                self.operation_log.append(f"Failed to delete memory key {key}: {str(e)} at {datetime.now().isoformat()}")
                raise
            except Exception as e:
                end_time = time.time()
                self.performance_metrics["total_memory_operations"] += 1
                self.performance_metrics["failed_memory_operations"] += 1
                total_time = self.performance_metrics["average_operation_time_ms"] * (self.performance_metrics["total_memory_operations"] - 1)
                self.performance_metrics["average_operation_time_ms"] = (total_time + (end_time - start_time) * 1000) / self.performance_metrics["total_memory_operations"]
                self.operation_log.append(f"Unexpected error deleting memory key {key}: {str(e)} at {datetime.now().isoformat()}")
                raise MemoryError(f"Unexpected error in manager {self.name} while deleting memory key {key}: {str(e)}")

    def apply_retention_policies(self) -> Dict[str, int]:
        """Apply retention policies across all storages."""
        if not self.active:
            raise MemoryError(f"Memory Manager {self.name} is not active")
        with self.lock:
            results = {}
            for storage_name, storage in self.storages.items():
                if storage.active:
                    try:
                        removed_count = storage.apply_retention_policy()
                        results[storage_name] = removed_count
                        self.operation_log.append(f"Applied retention policy on {storage_name}, removed {removed_count} items at {datetime.now().isoformat()}")
                    except Exception as e:
                        self.operation_log.append(f"Failed to apply retention policy on {storage_name}: {str(e)} at {datetime.now().isoformat()}")
            self.last_operation = time.time()
            return results

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get aggregated performance metrics for all storages and semantic index."""
        with self.lock:
            aggregated_metrics = {
                "manager_metrics": self.performance_metrics,
                "storage_metrics": {name: storage.performance_metrics for name, storage in self.storages.items()}
            }
            if self.semantic_index:
                aggregated_metrics["semantic_index_metrics"] = self.semantic_index.performance_metrics
            return aggregated_metrics

# Example usage and initialization
def initialize_memory_manager(config: Dict[str, Any]) -> MemoryManager:
    """Initialize a Memory Manager with all supported memory storage types."""
    manager = MemoryManager("DefaultMemoryManager", config)
    
    # Add various memory storages with their configurations
    short_term_config = config.get("short_term", {"capacity": 1000, "retention_period": 3600})
    long_term_config = config.get("long_term", {"db_path": "long_term_memory.db", "retention_period": 31536000})
    external_config = config.get("external", {"endpoint": "https://api.external.storage", "retention_period": 63072000})
    semantic_config = config.get("semantic_index", {"embedding_dimension": 128})
    
    manager.add_storage(ShortTermMemoryStorage(short_term_config))
    manager.add_storage(LongTermMemoryStorage(long_term_config))
    manager.add_storage(ExternalMemoryStorage(external_config))
    manager.set_semantic_index(SemanticIndex("DefaultSemanticIndex", semantic_config))
    
    return manager

if __name__ == "__main__":
    # Example configuration
    memory_config = {
        "selection_strategy": "tiered",
        "memory_tiers": {
            "ShortTermMemory": 1,
            "LongTermMemory": 2,
            "ExternalMemory": 3
        },
        "short_term": {"capacity": 1000, "retention_period": 3600, "security_enabled": False},
        "long_term": {"db_path": "long_term_memory.db", "retention_period": 31536000, "security_enabled": True},
        "external": {"endpoint": "https://api.external.storage", "retention_period": 63072000, "security_enabled": True},
        "semantic_index": {"embedding_dimension": 128}
    }
    
    # Initialize manager
    mem_manager = initialize_memory_manager(memory_config)
    
    # Activate manager and storages
    mem_manager.activate()
    
    try:
        # Example store operation
        result = mem_manager.store_memory("test_key", "test_value", {"category": "test"}, {"role": "default"})
        print(f"Store result: {result}")
        
        # Example store with embedding
        embedding = np.random.rand(128)
        result = mem_manager.store_memory("semantic_key", "semantic_value", {"category": "semantic"}, {"role": "default"}, embedding=embedding)
        print(f"Store with embedding result: {result}")
        
        # Example retrieve operation
        value = mem_manager.retrieve_memory("test_key", {"role": "default"})
        print(f"Retrieved value: {value}")
        
        # Example search operation
        search_results = mem_manager.search_memory({"category": "test"}, limit=5, context={"role": "default"})
        print(f"Search results: {search_results}")
        
        # Example semantic search
        query_embedding = np.random.rand(128)
        semantic_results = mem_manager.search_semantic(query_embedding, limit=5)
        print(f"Semantic search results: {semantic_results}")
        
        # Apply retention policies
        retention_results = mem_manager.apply_retention_policies()
        print(f"Retention policy results: {retention_results}")
    except MemoryError as e:
        print(f"Memory error: {e}")
    finally:
        # Deactivate manager and storages
        mem_manager.deactivate()
