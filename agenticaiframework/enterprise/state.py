"""
Enterprise State Management - Workflow state persistence and recovery.

Provides persistent state management for long-running
workflows with checkpointing and recovery.

Features:
- Workflow checkpoints
- State persistence
- Recovery from failures
- Transaction support
- State versioning
"""

import asyncio
import hashlib
import json
import logging
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar
import uuid

logger = logging.getLogger(__name__)


# =============================================================================
# State Types
# =============================================================================

T = TypeVar("T")


class StateStatus(Enum):
    """Status of a state entry."""
    ACTIVE = "active"
    CHECKPOINTED = "checkpointed"
    COMPLETED = "completed"
    FAILED = "failed"
    SUSPENDED = "suspended"
    EXPIRED = "expired"


@dataclass
class StateMetadata:
    """Metadata for state."""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    version: int = 1
    checksum: Optional[str] = None
    
    # Context
    workflow_id: Optional[str] = None
    step_id: Optional[str] = None
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    
    # Expiration
    expires_at: Optional[datetime] = None
    ttl_seconds: Optional[int] = None


@dataclass
class StateEntry(Generic[T]):
    """A state entry."""
    key: str
    value: T
    status: StateStatus = StateStatus.ACTIVE
    metadata: StateMetadata = field(default_factory=StateMetadata)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "key": self.key,
            "value": self._serialize_value(),
            "status": self.status.value,
            "metadata": {
                "created_at": self.metadata.created_at.isoformat(),
                "updated_at": self.metadata.updated_at.isoformat(),
                "version": self.metadata.version,
                "checksum": self.metadata.checksum,
                "workflow_id": self.metadata.workflow_id,
                "step_id": self.metadata.step_id,
                "tenant_id": self.metadata.tenant_id,
                "expires_at": self.metadata.expires_at.isoformat() if self.metadata.expires_at else None,
            },
        }
    
    def _serialize_value(self) -> Any:
        """Serialize value for storage."""
        if hasattr(self.value, "to_dict"):
            return self.value.to_dict()
        elif hasattr(self.value, "__dict__"):
            return self.value.__dict__
        return self.value
    
    @classmethod
    def from_dict(cls, data: Dict) -> "StateEntry":
        """Create from dictionary."""
        metadata = StateMetadata(
            created_at=datetime.fromisoformat(data["metadata"]["created_at"]),
            updated_at=datetime.fromisoformat(data["metadata"]["updated_at"]),
            version=data["metadata"]["version"],
            checksum=data["metadata"].get("checksum"),
            workflow_id=data["metadata"].get("workflow_id"),
            step_id=data["metadata"].get("step_id"),
            tenant_id=data["metadata"].get("tenant_id"),
            expires_at=datetime.fromisoformat(data["metadata"]["expires_at"]) if data["metadata"].get("expires_at") else None,
        )
        
        return cls(
            key=data["key"],
            value=data["value"],
            status=StateStatus(data["status"]),
            metadata=metadata,
        )


# =============================================================================
# State Store
# =============================================================================

class StateStore(ABC):
    """Abstract interface for state storage."""
    
    @abstractmethod
    async def get(self, key: str) -> Optional[StateEntry]:
        """Get state by key."""
        pass
    
    @abstractmethod
    async def set(self, key: str, value: Any, **kwargs) -> StateEntry:
        """Set state."""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete state."""
        pass
    
    @abstractmethod
    async def list(self, prefix: str = None) -> List[StateEntry]:
        """List states."""
        pass
    
    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if state exists."""
        pass


class InMemoryStateStore(StateStore):
    """In-memory state store."""
    
    def __init__(self):
        self._store: Dict[str, StateEntry] = {}
        self._lock = threading.RLock()
    
    async def get(self, key: str) -> Optional[StateEntry]:
        with self._lock:
            entry = self._store.get(key)
            
            if entry and entry.metadata.expires_at:
                if datetime.now() > entry.metadata.expires_at:
                    del self._store[key]
                    return None
            
            return entry
    
    async def set(self, key: str, value: Any, **kwargs) -> StateEntry:
        with self._lock:
            existing = self._store.get(key)
            version = existing.metadata.version + 1 if existing else 1
            
            # Calculate checksum
            value_str = json.dumps(value, default=str)
            checksum = hashlib.sha256(value_str.encode()).hexdigest()[:16]
            
            # Handle TTL
            ttl = kwargs.get("ttl_seconds")
            expires_at = None
            if ttl:
                expires_at = datetime.now() + timedelta(seconds=ttl)
            
            metadata = StateMetadata(
                created_at=existing.metadata.created_at if existing else datetime.now(),
                updated_at=datetime.now(),
                version=version,
                checksum=checksum,
                workflow_id=kwargs.get("workflow_id"),
                step_id=kwargs.get("step_id"),
                tenant_id=kwargs.get("tenant_id"),
                user_id=kwargs.get("user_id"),
                expires_at=expires_at,
                ttl_seconds=ttl,
            )
            
            entry = StateEntry(
                key=key,
                value=value,
                status=kwargs.get("status", StateStatus.ACTIVE),
                metadata=metadata,
            )
            
            self._store[key] = entry
            return entry
    
    async def delete(self, key: str) -> bool:
        with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False
    
    async def list(self, prefix: str = None) -> List[StateEntry]:
        with self._lock:
            entries = list(self._store.values())
            
            if prefix:
                entries = [e for e in entries if e.key.startswith(prefix)]
            
            # Filter expired
            now = datetime.now()
            entries = [
                e for e in entries
                if not e.metadata.expires_at or e.metadata.expires_at > now
            ]
            
            return entries
    
    async def exists(self, key: str) -> bool:
        entry = await self.get(key)
        return entry is not None


class FileStateStore(StateStore):
    """File-based state store."""
    
    def __init__(self, directory: str = ".state"):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
    
    def _key_to_path(self, key: str) -> Path:
        """Convert key to file path."""
        safe_key = key.replace("/", "__")
        return self.directory / f"{safe_key}.json"
    
    async def get(self, key: str) -> Optional[StateEntry]:
        path = self._key_to_path(key)
        
        if not path.exists():
            return None
        
        try:
            with open(path, "r") as f:
                data = json.load(f)
            
            entry = StateEntry.from_dict(data)
            
            # Check expiration
            if entry.metadata.expires_at and datetime.now() > entry.metadata.expires_at:
                path.unlink()
                return None
            
            return entry
        except Exception as e:
            logger.error(f"Failed to load state {key}: {e}")
            return None
    
    async def set(self, key: str, value: Any, **kwargs) -> StateEntry:
        with self._lock:
            existing = await self.get(key)
            version = existing.metadata.version + 1 if existing else 1
            
            # Calculate checksum
            value_str = json.dumps(value, default=str)
            checksum = hashlib.sha256(value_str.encode()).hexdigest()[:16]
            
            # Handle TTL
            ttl = kwargs.get("ttl_seconds")
            expires_at = None
            if ttl:
                expires_at = datetime.now() + timedelta(seconds=ttl)
            
            metadata = StateMetadata(
                created_at=existing.metadata.created_at if existing else datetime.now(),
                updated_at=datetime.now(),
                version=version,
                checksum=checksum,
                workflow_id=kwargs.get("workflow_id"),
                step_id=kwargs.get("step_id"),
                tenant_id=kwargs.get("tenant_id"),
                user_id=kwargs.get("user_id"),
                expires_at=expires_at,
                ttl_seconds=ttl,
            )
            
            entry = StateEntry(
                key=key,
                value=value,
                status=kwargs.get("status", StateStatus.ACTIVE),
                metadata=metadata,
            )
            
            path = self._key_to_path(key)
            with open(path, "w") as f:
                json.dump(entry.to_dict(), f, indent=2)
            
            return entry
    
    async def delete(self, key: str) -> bool:
        path = self._key_to_path(key)
        if path.exists():
            path.unlink()
            return True
        return False
    
    async def list(self, prefix: str = None) -> List[StateEntry]:
        entries = []
        
        for path in self.directory.glob("*.json"):
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                entry = StateEntry.from_dict(data)
                
                if prefix and not entry.key.startswith(prefix):
                    continue
                
                # Filter expired
                if entry.metadata.expires_at and datetime.now() > entry.metadata.expires_at:
                    path.unlink()
                    continue
                
                entries.append(entry)
            except Exception:
                continue
        
        return entries
    
    async def exists(self, key: str) -> bool:
        path = self._key_to_path(key)
        return path.exists()


# =============================================================================
# Checkpoint Manager
# =============================================================================

@dataclass
class Checkpoint:
    """A workflow checkpoint."""
    id: str
    workflow_id: str
    step_id: str
    
    # State
    state: Dict[str, Any]
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    status: StateStatus = StateStatus.CHECKPOINTED
    
    # Recovery info
    can_resume: bool = True
    resume_instructions: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "step_id": self.step_id,
            "state": self.state,
            "created_at": self.created_at.isoformat(),
            "status": self.status.value,
            "can_resume": self.can_resume,
            "resume_instructions": self.resume_instructions,
        }


class CheckpointManager:
    """
    Manages workflow checkpoints.
    
    Usage:
        >>> manager = CheckpointManager()
        >>> 
        >>> # Create checkpoint
        >>> checkpoint = await manager.create(
        ...     workflow_id="wf-1",
        ...     step_id="step-1",
        ...     state={"key": "value"},
        ... )
        >>> 
        >>> # Later, recover
        >>> checkpoint = await manager.get_latest("wf-1")
        >>> state = checkpoint.state
    """
    
    def __init__(self, store: StateStore = None):
        self.store = store or InMemoryStateStore()
    
    async def create(
        self,
        workflow_id: str,
        step_id: str,
        state: Dict[str, Any],
        **kwargs,
    ) -> Checkpoint:
        """Create a checkpoint."""
        checkpoint = Checkpoint(
            id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            step_id=step_id,
            state=state,
            **kwargs,
        )
        
        key = f"checkpoint:{workflow_id}:{checkpoint.id}"
        await self.store.set(key, checkpoint.to_dict())
        
        # Update latest pointer
        await self.store.set(f"checkpoint:{workflow_id}:latest", checkpoint.id)
        
        logger.info(f"Created checkpoint {checkpoint.id} for workflow {workflow_id}")
        return checkpoint
    
    async def get(self, workflow_id: str, checkpoint_id: str) -> Optional[Checkpoint]:
        """Get a specific checkpoint."""
        key = f"checkpoint:{workflow_id}:{checkpoint_id}"
        entry = await self.store.get(key)
        
        if entry:
            return self._from_dict(entry.value)
        return None
    
    async def get_latest(self, workflow_id: str) -> Optional[Checkpoint]:
        """Get the latest checkpoint for a workflow."""
        # Get latest pointer
        pointer = await self.store.get(f"checkpoint:{workflow_id}:latest")
        
        if not pointer:
            return None
        
        return await self.get(workflow_id, pointer.value)
    
    async def list(self, workflow_id: str) -> List[Checkpoint]:
        """List all checkpoints for a workflow."""
        entries = await self.store.list(prefix=f"checkpoint:{workflow_id}:")
        
        checkpoints = []
        for entry in entries:
            if ":latest" not in entry.key:
                checkpoints.append(self._from_dict(entry.value))
        
        return sorted(checkpoints, key=lambda c: c.created_at, reverse=True)
    
    async def delete(self, workflow_id: str, checkpoint_id: str) -> bool:
        """Delete a checkpoint."""
        key = f"checkpoint:{workflow_id}:{checkpoint_id}"
        return await self.store.delete(key)
    
    async def cleanup(self, workflow_id: str, keep_count: int = 5) -> int:
        """Cleanup old checkpoints, keeping the most recent ones."""
        checkpoints = await self.list(workflow_id)
        
        if len(checkpoints) <= keep_count:
            return 0
        
        to_delete = checkpoints[keep_count:]
        
        for checkpoint in to_delete:
            await self.delete(workflow_id, checkpoint.id)
        
        return len(to_delete)
    
    def _from_dict(self, data: Dict) -> Checkpoint:
        """Create checkpoint from dict."""
        return Checkpoint(
            id=data["id"],
            workflow_id=data["workflow_id"],
            step_id=data["step_id"],
            state=data["state"],
            created_at=datetime.fromisoformat(data["created_at"]),
            status=StateStatus(data["status"]),
            can_resume=data.get("can_resume", True),
            resume_instructions=data.get("resume_instructions"),
        )


# =============================================================================
# State Manager
# =============================================================================

class StateManager:
    """
    High-level state management.
    
    Usage:
        >>> state = StateManager()
        >>> 
        >>> # Set state
        >>> await state.set("my-key", {"data": "value"})
        >>> 
        >>> # Get state
        >>> value = await state.get("my-key")
        >>> 
        >>> # With context
        >>> with state.scope("workflow:123") as scoped:
        ...     await scoped.set("step-data", {"done": True})
    """
    
    def __init__(self, store: StateStore = None):
        self.store = store or InMemoryStateStore()
        self.checkpoints = CheckpointManager(self.store)
        
        self._prefix: Optional[str] = None
    
    def _key(self, key: str) -> str:
        """Get prefixed key."""
        if self._prefix:
            return f"{self._prefix}:{key}"
        return key
    
    async def get(self, key: str, default: Any = None) -> Any:
        """Get state value."""
        entry = await self.store.get(self._key(key))
        
        if entry:
            return entry.value
        return default
    
    async def set(self, key: str, value: Any, **kwargs) -> StateEntry:
        """Set state value."""
        return await self.store.set(self._key(key), value, **kwargs)
    
    async def delete(self, key: str) -> bool:
        """Delete state."""
        return await self.store.delete(self._key(key))
    
    async def exists(self, key: str) -> bool:
        """Check if state exists."""
        return await self.store.exists(self._key(key))
    
    async def list(self, prefix: str = None) -> List[StateEntry]:
        """List states."""
        full_prefix = self._key(prefix) if prefix else self._prefix
        return await self.store.list(full_prefix)
    
    def scope(self, prefix: str) -> "ScopedStateManager":
        """Create a scoped state manager."""
        return ScopedStateManager(self, prefix)
    
    async def transaction(self) -> "StateTransaction":
        """Start a transaction."""
        return StateTransaction(self)
    
    # Checkpoint helpers
    async def checkpoint(
        self,
        workflow_id: str,
        step_id: str,
        state: Dict[str, Any],
    ) -> Checkpoint:
        """Create a checkpoint."""
        return await self.checkpoints.create(workflow_id, step_id, state)
    
    async def restore(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Restore from the latest checkpoint."""
        checkpoint = await self.checkpoints.get_latest(workflow_id)
        
        if checkpoint:
            logger.info(f"Restoring workflow {workflow_id} from checkpoint {checkpoint.id}")
            return checkpoint.state
        
        return None


class ScopedStateManager:
    """Scoped state manager for namespaced access."""
    
    def __init__(self, manager: StateManager, prefix: str):
        self._manager = manager
        self._prefix = prefix
    
    def __enter__(self) -> "ScopedStateManager":
        return self
    
    def __exit__(self, *args):
        pass
    
    async def get(self, key: str, default: Any = None) -> Any:
        full_key = f"{self._prefix}:{key}"
        return await self._manager.get(full_key, default)
    
    async def set(self, key: str, value: Any, **kwargs) -> StateEntry:
        full_key = f"{self._prefix}:{key}"
        return await self._manager.set(full_key, value, **kwargs)
    
    async def delete(self, key: str) -> bool:
        full_key = f"{self._prefix}:{key}"
        return await self._manager.delete(full_key)


class StateTransaction:
    """Transaction for atomic state updates."""
    
    def __init__(self, manager: StateManager):
        self._manager = manager
        self._operations: List[tuple] = []
        self._rollback: List[tuple] = []
    
    async def __aenter__(self) -> "StateTransaction":
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            await self.rollback()
        else:
            await self.commit()
    
    async def set(self, key: str, value: Any, **kwargs):
        """Queue a set operation."""
        # Store current value for rollback
        current = await self._manager.get(key)
        self._rollback.append(("set", key, current))
        
        self._operations.append(("set", key, value, kwargs))
    
    async def delete(self, key: str):
        """Queue a delete operation."""
        # Store current value for rollback
        current = await self._manager.get(key)
        self._rollback.append(("set", key, current))
        
        self._operations.append(("delete", key))
    
    async def commit(self):
        """Commit all operations."""
        for op in self._operations:
            if op[0] == "set":
                await self._manager.set(op[1], op[2], **op[3])
            elif op[0] == "delete":
                await self._manager.delete(op[1])
        
        self._operations = []
        self._rollback = []
    
    async def rollback(self):
        """Rollback all operations."""
        for op in reversed(self._rollback):
            if op[0] == "set":
                if op[2] is not None:
                    await self._manager.set(op[1], op[2])
                else:
                    await self._manager.delete(op[1])
        
        self._operations = []
        self._rollback = []


# =============================================================================
# Global State Manager
# =============================================================================

_global_state: Optional[StateManager] = None


def get_state_manager() -> StateManager:
    """Get the global state manager."""
    global _global_state
    
    if _global_state is None:
        _global_state = StateManager()
    
    return _global_state


def set_state_manager(manager: StateManager):
    """Set the global state manager."""
    global _global_state
    _global_state = manager


# Convenience functions
async def get_state(key: str, default: Any = None) -> Any:
    """Get state from global manager."""
    return await get_state_manager().get(key, default)


async def set_state(key: str, value: Any, **kwargs) -> StateEntry:
    """Set state in global manager."""
    return await get_state_manager().set(key, value, **kwargs)


async def delete_state(key: str) -> bool:
    """Delete state from global manager."""
    return await get_state_manager().delete(key)


# =============================================================================
# Decorator for Stateful Functions
# =============================================================================

def stateful(key_func: Callable = None, ttl_seconds: int = None):
    """
    Decorator to persist function state.
    
    Usage:
        >>> @stateful(key_func=lambda x: f"func:{x}")
        ... async def my_func(x):
        ...     # State is persisted
        ...     pass
    """
    def decorator(func: Callable) -> Callable:
        async def wrapper(*args, **kwargs):
            # Generate key
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                key = f"func:{func.__name__}:{hash((args, tuple(kwargs.items())))}"
            
            # Check for existing state
            state = await get_state_manager().get(key)
            
            if state and "result" in state:
                return state["result"]
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Save state
            await get_state_manager().set(
                key,
                {"result": result, "args": args, "kwargs": kwargs},
                ttl_seconds=ttl_seconds,
            )
            
            return result
        
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    
    return decorator
