"""
Core State Management System.

Provides unified state management with pluggable backends.
"""

import json
import os
import time
import logging
import threading
import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable, TypeVar, Generic

logger = logging.getLogger(__name__)

T = TypeVar('T')


class StateType(Enum):
    """Types of state that can be managed."""
    AGENT = "agent"
    WORKFLOW = "workflow"
    ORCHESTRATION = "orchestration"
    KNOWLEDGE = "knowledge"
    TOOL = "tool"
    SPEECH = "speech"
    SESSION = "session"
    CUSTOM = "custom"


@dataclass
class StateConfig:
    """Configuration for state management."""
    backend: str = "memory"  # memory, file, redis, postgres
    persist_path: Optional[str] = None
    auto_checkpoint: bool = True
    checkpoint_interval: int = 60  # seconds
    max_checkpoints: int = 10
    compression: bool = False
    encryption: bool = False
    encryption_key: Optional[str] = None
    ttl: Optional[int] = None  # Time-to-live in seconds
    redis_url: Optional[str] = None
    postgres_url: Optional[str] = None


@dataclass
class StateEntry:
    """A single state entry."""
    key: str
    value: Any
    state_type: StateType
    version: int = 1
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    checksum: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def compute_checksum(self) -> str:
        """Compute checksum of the value."""
        value_str = json.dumps(self.value, sort_keys=True, default=str)
        return hashlib.sha256(value_str.encode()).hexdigest()[:16]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "state_type": self.state_type.value,
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "checksum": self.checksum,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StateEntry":
        return cls(
            key=data["key"],
            value=data["value"],
            state_type=StateType(data["state_type"]),
            version=data.get("version", 1),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            checksum=data.get("checksum"),
            metadata=data.get("metadata", {}),
        )


class StateBackend(ABC):
    """Abstract base class for state storage backends."""
    
    @abstractmethod
    def get(self, key: str) -> Optional[StateEntry]:
        """Get state by key."""
        pass
    
    @abstractmethod
    def set(self, key: str, entry: StateEntry) -> bool:
        """Set state by key."""
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete state by key."""
        pass
    
    @abstractmethod
    def exists(self, key: str) -> bool:
        """Check if key exists."""
        pass
    
    @abstractmethod
    def list_keys(self, prefix: Optional[str] = None) -> List[str]:
        """List all keys with optional prefix filter."""
        pass
    
    @abstractmethod
    def clear(self) -> bool:
        """Clear all state."""
        pass
    
    def get_many(self, keys: List[str]) -> Dict[str, StateEntry]:
        """Get multiple states by keys."""
        result = {}
        for key in keys:
            entry = self.get(key)
            if entry:
                result[key] = entry
        return result
    
    def set_many(self, entries: Dict[str, StateEntry]) -> bool:
        """Set multiple states."""
        for key, entry in entries.items():
            if not self.set(key, entry):
                return False
        return True


class MemoryBackend(StateBackend):
    """In-memory state storage."""
    
    def __init__(self, config: StateConfig = None):
        self.config = config or StateConfig()
        self._store: Dict[str, StateEntry] = {}
        self._lock = threading.RLock()
    
    def get(self, key: str) -> Optional[StateEntry]:
        with self._lock:
            entry = self._store.get(key)
            if entry and self.config.ttl:
                updated = datetime.fromisoformat(entry.updated_at)
                if (datetime.now() - updated).total_seconds() > self.config.ttl:
                    del self._store[key]
                    return None
            return entry
    
    def set(self, key: str, entry: StateEntry) -> bool:
        with self._lock:
            entry.updated_at = datetime.now().isoformat()
            entry.checksum = entry.compute_checksum()
            self._store[key] = entry
            return True
    
    def delete(self, key: str) -> bool:
        with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False
    
    def exists(self, key: str) -> bool:
        return key in self._store
    
    def list_keys(self, prefix: Optional[str] = None) -> List[str]:
        with self._lock:
            if prefix:
                return [k for k in self._store.keys() if k.startswith(prefix)]
            return list(self._store.keys())
    
    def clear(self) -> bool:
        with self._lock:
            self._store.clear()
            return True


class FileBackend(StateBackend):
    """File-based state storage with JSON serialization."""
    
    def __init__(self, config: StateConfig = None):
        self.config = config or StateConfig()
        self.base_path = Path(self.config.persist_path or "./state")
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
    
    def _key_to_path(self, key: str) -> Path:
        """Convert key to file path."""
        # Replace invalid chars and create directory structure
        safe_key = key.replace("/", "__").replace(":", "_")
        return self.base_path / f"{safe_key}.json"
    
    def get(self, key: str) -> Optional[StateEntry]:
        path = self._key_to_path(key)
        with self._lock:
            if not path.exists():
                return None
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                entry = StateEntry.from_dict(data)
                
                # Check TTL
                if self.config.ttl:
                    updated = datetime.fromisoformat(entry.updated_at)
                    if (datetime.now() - updated).total_seconds() > self.config.ttl:
                        path.unlink()
                        return None
                
                return entry
            except Exception as e:
                logger.error(f"Failed to read state {key}: {e}")
                return None
    
    def set(self, key: str, entry: StateEntry) -> bool:
        path = self._key_to_path(key)
        with self._lock:
            try:
                entry.updated_at = datetime.now().isoformat()
                entry.checksum = entry.compute_checksum()
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(entry.to_dict(), f, indent=2, default=str)
                return True
            except Exception as e:
                logger.error(f"Failed to write state {key}: {e}")
                return False
    
    def delete(self, key: str) -> bool:
        path = self._key_to_path(key)
        with self._lock:
            try:
                if path.exists():
                    path.unlink()
                    return True
                return False
            except Exception as e:
                logger.error(f"Failed to delete state {key}: {e}")
                return False
    
    def exists(self, key: str) -> bool:
        return self._key_to_path(key).exists()
    
    def list_keys(self, prefix: Optional[str] = None) -> List[str]:
        with self._lock:
            keys = []
            for path in self.base_path.glob("*.json"):
                key = path.stem.replace("__", "/").replace("_", ":")
                if prefix is None or key.startswith(prefix):
                    keys.append(key)
            return keys
    
    def clear(self) -> bool:
        with self._lock:
            try:
                for path in self.base_path.glob("*.json"):
                    path.unlink()
                return True
            except Exception as e:
                logger.error(f"Failed to clear state: {e}")
                return False


class RedisBackend(StateBackend):
    """Redis-based state storage for distributed systems."""
    
    def __init__(self, config: StateConfig = None):
        self.config = config or StateConfig()
        self._client = None
        self._connect()
    
    def _connect(self):
        """Connect to Redis."""
        try:
            import redis
            url = self.config.redis_url or os.getenv("REDIS_URL", "redis://localhost:6379")
            self._client = redis.from_url(url)
            self._client.ping()
        except ImportError:
            raise ImportError("Redis backend requires: pip install redis")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}")
            self._client = None
    
    def _serialize(self, entry: StateEntry) -> str:
        """Serialize entry to JSON."""
        return json.dumps(entry.to_dict(), default=str)
    
    def _deserialize(self, data: str) -> StateEntry:
        """Deserialize entry from JSON."""
        return StateEntry.from_dict(json.loads(data))
    
    def get(self, key: str) -> Optional[StateEntry]:
        if not self._client:
            return None
        try:
            data = self._client.get(f"state:{key}")
            if data:
                return self._deserialize(data)
            return None
        except Exception as e:
            logger.error(f"Redis get failed: {e}")
            return None
    
    def set(self, key: str, entry: StateEntry) -> bool:
        if not self._client:
            return False
        try:
            entry.updated_at = datetime.now().isoformat()
            entry.checksum = entry.compute_checksum()
            data = self._serialize(entry)
            if self.config.ttl:
                self._client.setex(f"state:{key}", self.config.ttl, data)
            else:
                self._client.set(f"state:{key}", data)
            return True
        except Exception as e:
            logger.error(f"Redis set failed: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        if not self._client:
            return False
        try:
            return self._client.delete(f"state:{key}") > 0
        except Exception as e:
            logger.error(f"Redis delete failed: {e}")
            return False
    
    def exists(self, key: str) -> bool:
        if not self._client:
            return False
        try:
            return self._client.exists(f"state:{key}") > 0
        except Exception as e:
            return False
    
    def list_keys(self, prefix: Optional[str] = None) -> List[str]:
        if not self._client:
            return []
        try:
            pattern = f"state:{prefix}*" if prefix else "state:*"
            keys = self._client.keys(pattern)
            return [k.decode().replace("state:", "") for k in keys]
        except Exception as e:
            logger.error(f"Redis list_keys failed: {e}")
            return []
    
    def clear(self) -> bool:
        if not self._client:
            return False
        try:
            keys = self._client.keys("state:*")
            if keys:
                self._client.delete(*keys)
            return True
        except Exception as e:
            logger.error(f"Redis clear failed: {e}")
            return False


class StateManager:
    """
    Unified State Manager for the framework.
    
    Provides centralized state management with:
    - Multiple backend support (memory, file, redis)
    - Automatic checkpointing
    - State versioning
    - State recovery
    - TTL support
    
    Example:
        >>> state = StateManager(backend="file", persist_path="./state")
        >>> 
        >>> # Save agent state
        >>> state.save("agent:123", {"status": "running", "memory": [...]})
        >>> 
        >>> # Get state
        >>> agent_state = state.get("agent:123")
        >>> 
        >>> # Checkpoint
        >>> state.checkpoint("workflow:abc", step=5)
    """
    
    BACKENDS = {
        "memory": MemoryBackend,
        "file": FileBackend,
        "redis": RedisBackend,
    }
    
    def __init__(
        self,
        backend: str = "memory",
        persist_path: str = None,
        config: StateConfig = None,
        **kwargs,
    ):
        self.config = config or StateConfig(
            backend=backend,
            persist_path=persist_path,
            **kwargs,
        )
        
        # Initialize backend
        backend_class = self.BACKENDS.get(backend, MemoryBackend)
        self.backend = backend_class(self.config)
        
        # Checkpoint management
        self._checkpoint_timer = None
        self._on_checkpoint: List[Callable] = []
        self._on_recovery: List[Callable] = []
        
        # Start auto-checkpoint if enabled
        if self.config.auto_checkpoint:
            self._start_auto_checkpoint()
    
    def _start_auto_checkpoint(self):
        """Start automatic checkpointing."""
        def checkpoint_loop():
            while True:
                time.sleep(self.config.checkpoint_interval)
                self._trigger_checkpoint()
        
        self._checkpoint_timer = threading.Thread(
            target=checkpoint_loop,
            daemon=True,
        )
        self._checkpoint_timer.start()
    
    def _trigger_checkpoint(self):
        """Trigger checkpoint callbacks."""
        for callback in self._on_checkpoint:
            try:
                callback()
            except Exception as e:
                logger.error(f"Checkpoint callback error: {e}")
    
    # Core Operations
    def save(
        self,
        key: str,
        value: Any,
        state_type: StateType = StateType.CUSTOM,
        metadata: Dict = None,
    ) -> bool:
        """Save state."""
        existing = self.backend.get(key)
        version = existing.version + 1 if existing else 1
        
        entry = StateEntry(
            key=key,
            value=value,
            state_type=state_type,
            version=version,
            metadata=metadata or {},
        )
        
        return self.backend.set(key, entry)
    
    def get(self, key: str) -> Optional[Any]:
        """Get state value."""
        entry = self.backend.get(key)
        return entry.value if entry else None
    
    def get_entry(self, key: str) -> Optional[StateEntry]:
        """Get full state entry with metadata."""
        return self.backend.get(key)
    
    def delete(self, key: str) -> bool:
        """Delete state."""
        return self.backend.delete(key)
    
    def exists(self, key: str) -> bool:
        """Check if state exists."""
        return self.backend.exists(key)
    
    def list(self, prefix: str = None, state_type: StateType = None) -> List[str]:
        """List state keys."""
        keys = self.backend.list_keys(prefix)
        
        if state_type:
            filtered = []
            for key in keys:
                entry = self.backend.get(key)
                if entry and entry.state_type == state_type:
                    filtered.append(key)
            return filtered
        
        return keys
    
    # Agent State Operations
    def save_agent_state(
        self,
        agent_id: str,
        state: Dict[str, Any],
        checkpoint: bool = False,
    ) -> bool:
        """Save agent state."""
        key = f"agent:{agent_id}"
        success = self.save(key, state, StateType.AGENT)
        
        if checkpoint and success:
            self._create_checkpoint(key, state)
        
        return success
    
    def get_agent_state(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get agent state."""
        return self.get(f"agent:{agent_id}")
    
    def recover_agent(self, agent_id: str, checkpoint_version: int = None) -> Optional[Dict]:
        """Recover agent from checkpoint."""
        if checkpoint_version:
            key = f"checkpoint:agent:{agent_id}:v{checkpoint_version}"
        else:
            # Get latest checkpoint
            checkpoints = self.list(f"checkpoint:agent:{agent_id}")
            if not checkpoints:
                return None
            key = sorted(checkpoints)[-1]
        
        checkpoint = self.get(key)
        if checkpoint:
            # Restore to main state
            self.save_agent_state(agent_id, checkpoint)
            for callback in self._on_recovery:
                callback(agent_id, checkpoint)
        
        return checkpoint
    
    # Workflow State Operations
    def save_workflow_state(
        self,
        workflow_id: str,
        state: Dict[str, Any],
        step: int = None,
    ) -> bool:
        """Save workflow state with optional step tracking."""
        if step is not None:
            state["current_step"] = step
        return self.save(f"workflow:{workflow_id}", state, StateType.WORKFLOW)
    
    def get_workflow_state(self, workflow_id: str) -> Optional[Dict]:
        """Get workflow state."""
        return self.get(f"workflow:{workflow_id}")
    
    def checkpoint_workflow(
        self,
        workflow_id: str,
        step: int,
        data: Any = None,
    ) -> bool:
        """Create workflow checkpoint at a step."""
        state = {
            "step": step,
            "data": data,
            "timestamp": datetime.now().isoformat(),
        }
        key = f"checkpoint:workflow:{workflow_id}:step{step}"
        return self.save(key, state, StateType.WORKFLOW)
    
    def resume_workflow(self, workflow_id: str) -> Optional[Dict]:
        """Get latest workflow checkpoint for resumption."""
        checkpoints = self.list(f"checkpoint:workflow:{workflow_id}")
        if not checkpoints:
            return None
        
        # Get latest by step number
        latest = sorted(checkpoints, key=lambda x: int(x.split("step")[-1]))[-1]
        return self.get(latest)
    
    # Orchestration State Operations
    def save_team_state(
        self,
        team_id: str,
        agents: List[str],
        coordination: Dict = None,
    ) -> bool:
        """Save orchestration team state."""
        state = {
            "agents": agents,
            "coordination": coordination or {},
            "updated_at": datetime.now().isoformat(),
        }
        return self.save(f"orchestration:{team_id}", state, StateType.ORCHESTRATION)
    
    def get_team_state(self, team_id: str) -> Optional[Dict]:
        """Get orchestration team state."""
        return self.get(f"orchestration:{team_id}")
    
    # Knowledge State Operations
    def save_knowledge_state(
        self,
        kb_id: str,
        progress: float = 0.0,
        indexed_count: int = 0,
        total_count: int = 0,
        status: str = "idle",
    ) -> bool:
        """Save knowledge base indexing state."""
        state = {
            "progress": progress,
            "indexed_count": indexed_count,
            "total_count": total_count,
            "status": status,
            "updated_at": datetime.now().isoformat(),
        }
        return self.save(f"knowledge:{kb_id}", state, StateType.KNOWLEDGE)
    
    def get_knowledge_state(self, kb_id: str) -> Optional[Dict]:
        """Get knowledge base state."""
        return self.get(f"knowledge:{kb_id}")
    
    # Tool State Operations
    def save_tool_state(
        self,
        tool_id: str,
        execution_id: str,
        status: str,
        result: Any = None,
        error: str = None,
    ) -> bool:
        """Save tool execution state."""
        state = {
            "execution_id": execution_id,
            "status": status,
            "result": result,
            "error": error,
            "timestamp": datetime.now().isoformat(),
        }
        return self.save(f"tool:{tool_id}:{execution_id}", state, StateType.TOOL)
    
    def get_tool_state(self, tool_id: str, execution_id: str) -> Optional[Dict]:
        """Get tool execution state."""
        return self.get(f"tool:{tool_id}:{execution_id}")
    
    def cache_tool_result(
        self,
        tool_id: str,
        input_hash: str,
        result: Any,
        ttl: int = 3600,
    ) -> bool:
        """Cache tool result for reuse."""
        state = {
            "result": result,
            "cached_at": datetime.now().isoformat(),
            "ttl": ttl,
        }
        return self.save(f"cache:tool:{tool_id}:{input_hash}", state, StateType.TOOL)
    
    def get_cached_tool_result(self, tool_id: str, input_hash: str) -> Optional[Any]:
        """Get cached tool result if still valid."""
        entry = self.get_entry(f"cache:tool:{tool_id}:{input_hash}")
        if not entry:
            return None
        
        # Check TTL
        cached_at = datetime.fromisoformat(entry.value.get("cached_at", ""))
        ttl = entry.value.get("ttl", 3600)
        if (datetime.now() - cached_at).total_seconds() > ttl:
            self.delete(f"cache:tool:{tool_id}:{input_hash}")
            return None
        
        return entry.value.get("result")
    
    # Speech State Operations
    def save_speech_session(
        self,
        session_id: str,
        audio_format: str = None,
        language: str = None,
        transcript_so_far: str = "",
    ) -> bool:
        """Save speech session state."""
        state = {
            "audio_format": audio_format,
            "language": language,
            "transcript": transcript_so_far,
            "started_at": datetime.now().isoformat(),
        }
        return self.save(f"speech:{session_id}", state, StateType.SPEECH)
    
    def update_speech_transcript(self, session_id: str, transcript: str) -> bool:
        """Update speech session transcript."""
        state = self.get(f"speech:{session_id}")
        if state:
            state["transcript"] = transcript
            state["updated_at"] = datetime.now().isoformat()
            return self.save(f"speech:{session_id}", state, StateType.SPEECH)
        return False
    
    def get_speech_session(self, session_id: str) -> Optional[Dict]:
        """Get speech session state."""
        return self.get(f"speech:{session_id}")
    
    # Checkpoint Management
    def _create_checkpoint(self, key: str, state: Any) -> bool:
        """Create a checkpoint."""
        entry = self.get_entry(key)
        if not entry:
            return False
        
        checkpoint_key = f"checkpoint:{key}:v{entry.version}"
        
        # Cleanup old checkpoints
        checkpoints = self.list(f"checkpoint:{key}")
        if len(checkpoints) >= self.config.max_checkpoints:
            oldest = sorted(checkpoints)[0]
            self.delete(oldest)
        
        return self.save(checkpoint_key, state, entry.state_type)
    
    def list_checkpoints(self, key: str) -> List[Dict]:
        """List all checkpoints for a key."""
        checkpoints = []
        for ck in self.list(f"checkpoint:{key}"):
            entry = self.get_entry(ck)
            if entry:
                checkpoints.append({
                    "key": ck,
                    "version": entry.version,
                    "created_at": entry.created_at,
                })
        return sorted(checkpoints, key=lambda x: x.get("version", 0))
    
    def restore_checkpoint(self, checkpoint_key: str, target_key: str) -> bool:
        """Restore a checkpoint to a key."""
        checkpoint = self.get(checkpoint_key)
        if checkpoint:
            entry = self.get_entry(checkpoint_key)
            return self.save(target_key, checkpoint, entry.state_type if entry else StateType.CUSTOM)
        return False
    
    # Callbacks
    def on_checkpoint(self, callback: Callable) -> None:
        """Register checkpoint callback."""
        self._on_checkpoint.append(callback)
    
    def on_recovery(self, callback: Callable[[str, Dict], None]) -> None:
        """Register recovery callback."""
        self._on_recovery.append(callback)
    
    # Cleanup
    def cleanup_expired(self) -> int:
        """Clean up expired state entries."""
        if not self.config.ttl:
            return 0
        
        count = 0
        for key in self.list():
            entry = self.get_entry(key)
            if entry:
                updated = datetime.fromisoformat(entry.updated_at)
                if (datetime.now() - updated).total_seconds() > self.config.ttl:
                    self.delete(key)
                    count += 1
        return count
    
    def get_stats(self) -> Dict[str, Any]:
        """Get state manager statistics."""
        all_keys = self.list()
        by_type = {}
        
        for key in all_keys:
            entry = self.get_entry(key)
            if entry:
                type_name = entry.state_type.value
                by_type[type_name] = by_type.get(type_name, 0) + 1
        
        return {
            "total_entries": len(all_keys),
            "by_type": by_type,
            "backend": self.config.backend,
            "checkpoints": len([k for k in all_keys if k.startswith("checkpoint:")]),
        }


__all__ = [
    "StateType",
    "StateConfig",
    "StateEntry",
    "StateBackend",
    "MemoryBackend",
    "FileBackend",
    "RedisBackend",
    "StateManager",
]
