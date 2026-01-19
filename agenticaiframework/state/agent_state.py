"""
Agent State Management.

Provides checkpointing, snapshots, and recovery for agents.
"""

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable

from .manager import StateManager, StateType, StateConfig

logger = logging.getLogger(__name__)


class AgentStatus(Enum):
    """Agent lifecycle status."""
    CREATED = "created"
    INITIALIZED = "initialized"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    FAILED = "failed"
    RECOVERING = "recovering"


@dataclass
class AgentSnapshot:
    """
    Complete snapshot of agent state.
    
    Captures all state needed to restore an agent.
    """
    agent_id: str
    name: str
    status: AgentStatus
    config: Dict[str, Any]
    memory: List[Any]
    context: List[Any]
    conversation_history: List[Dict]
    tool_states: Dict[str, Any]
    metadata: Dict[str, Any]
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    version: int = 1
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "status": self.status.value,
            "config": self.config,
            "memory": self.memory,
            "context": self.context,
            "conversation_history": self.conversation_history,
            "tool_states": self.tool_states,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "version": self.version,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentSnapshot":
        return cls(
            agent_id=data["agent_id"],
            name=data["name"],
            status=AgentStatus(data["status"]),
            config=data.get("config", {}),
            memory=data.get("memory", []),
            context=data.get("context", []),
            conversation_history=data.get("conversation_history", []),
            tool_states=data.get("tool_states", {}),
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", datetime.now().isoformat()),
            version=data.get("version", 1),
        )
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)
    
    @classmethod
    def from_json(cls, json_str: str) -> "AgentSnapshot":
        return cls.from_dict(json.loads(json_str))


@dataclass
class AgentCheckpoint:
    """
    Lightweight checkpoint for agent state.
    
    Used for frequent checkpointing without full snapshot overhead.
    """
    agent_id: str
    checkpoint_id: str
    step: int
    status: AgentStatus
    memory_size: int
    context_summary: str
    last_action: Optional[str]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "checkpoint_id": self.checkpoint_id,
            "step": self.step,
            "status": self.status.value,
            "memory_size": self.memory_size,
            "context_summary": self.context_summary,
            "last_action": self.last_action,
            "timestamp": self.timestamp,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentCheckpoint":
        return cls(
            agent_id=data["agent_id"],
            checkpoint_id=data["checkpoint_id"],
            step=data["step"],
            status=AgentStatus(data["status"]),
            memory_size=data["memory_size"],
            context_summary=data.get("context_summary", ""),
            last_action=data.get("last_action"),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
        )


class AgentStateStore:
    """
    State store for agents with checkpointing and recovery.
    
    Example:
        >>> store = AgentStateStore()
        >>> 
        >>> # Save agent state
        >>> store.save(agent.id, agent.get_snapshot())
        >>> 
        >>> # Create checkpoint
        >>> store.checkpoint(agent.id, step=10)
        >>> 
        >>> # Recover from failure
        >>> snapshot = store.recover(agent.id)
        >>> agent.restore(snapshot)
    """
    
    def __init__(
        self,
        state_manager: StateManager = None,
        auto_checkpoint: bool = True,
        checkpoint_interval: int = 30,
        max_checkpoints: int = 10,
    ):
        self.state_manager = state_manager or StateManager()
        self.auto_checkpoint = auto_checkpoint
        self.checkpoint_interval = checkpoint_interval
        self.max_checkpoints = max_checkpoints
        
        self._step_counters: Dict[str, int] = {}
        self._last_checkpoint: Dict[str, float] = {}
    
    def save(self, agent_id: str, snapshot: AgentSnapshot) -> bool:
        """Save agent snapshot."""
        return self.state_manager.save(
            f"agent:{agent_id}",
            snapshot.to_dict(),
            StateType.AGENT,
        )
    
    def load(self, agent_id: str) -> Optional[AgentSnapshot]:
        """Load agent snapshot."""
        data = self.state_manager.get(f"agent:{agent_id}")
        if data:
            return AgentSnapshot.from_dict(data)
        return None
    
    def delete(self, agent_id: str) -> bool:
        """Delete agent state."""
        # Delete main state
        self.state_manager.delete(f"agent:{agent_id}")
        
        # Delete checkpoints
        for key in self.state_manager.list(f"checkpoint:agent:{agent_id}"):
            self.state_manager.delete(key)
        
        return True
    
    def checkpoint(
        self,
        agent_id: str,
        step: int = None,
        status: AgentStatus = None,
        memory_size: int = 0,
        context_summary: str = "",
        last_action: str = None,
    ) -> AgentCheckpoint:
        """Create a checkpoint."""
        if step is None:
            step = self._step_counters.get(agent_id, 0) + 1
            self._step_counters[agent_id] = step
        
        checkpoint = AgentCheckpoint(
            agent_id=agent_id,
            checkpoint_id=f"cp-{agent_id}-{step}",
            step=step,
            status=status or AgentStatus.RUNNING,
            memory_size=memory_size,
            context_summary=context_summary,
            last_action=last_action,
        )
        
        # Save checkpoint
        self.state_manager.save(
            f"checkpoint:agent:{agent_id}:step{step}",
            checkpoint.to_dict(),
            StateType.AGENT,
        )
        
        self._last_checkpoint[agent_id] = time.time()
        
        # Cleanup old checkpoints
        self._cleanup_old_checkpoints(agent_id)
        
        return checkpoint
    
    def _cleanup_old_checkpoints(self, agent_id: str) -> None:
        """Remove old checkpoints beyond max limit."""
        checkpoints = self.list_checkpoints(agent_id)
        if len(checkpoints) > self.max_checkpoints:
            to_delete = checkpoints[:-self.max_checkpoints]
            for cp in to_delete:
                self.state_manager.delete(f"checkpoint:agent:{agent_id}:step{cp['step']}")
    
    def list_checkpoints(self, agent_id: str) -> List[Dict]:
        """List all checkpoints for an agent."""
        keys = self.state_manager.list(f"checkpoint:agent:{agent_id}")
        checkpoints = []
        for key in keys:
            data = self.state_manager.get(key)
            if data:
                checkpoints.append(data)
        return sorted(checkpoints, key=lambda x: x.get("step", 0))
    
    def get_latest_checkpoint(self, agent_id: str) -> Optional[AgentCheckpoint]:
        """Get the most recent checkpoint."""
        checkpoints = self.list_checkpoints(agent_id)
        if checkpoints:
            return AgentCheckpoint.from_dict(checkpoints[-1])
        return None
    
    def recover(self, agent_id: str, from_step: int = None) -> Optional[AgentSnapshot]:
        """
        Recover agent state from checkpoint or snapshot.
        
        Args:
            agent_id: Agent ID
            from_step: Specific step to recover from (None = latest)
        """
        # First try to load full snapshot
        snapshot = self.load(agent_id)
        
        # If specific step requested, check checkpoints
        if from_step is not None:
            key = f"checkpoint:agent:{agent_id}:step{from_step}"
            checkpoint_data = self.state_manager.get(key)
            if checkpoint_data:
                # Merge checkpoint into snapshot
                if snapshot:
                    snapshot.status = AgentStatus(checkpoint_data.get("status", "running"))
                    snapshot.metadata["recovered_from_step"] = from_step
        
        if snapshot:
            snapshot.status = AgentStatus.RECOVERING
            snapshot.metadata["recovery_timestamp"] = datetime.now().isoformat()
        
        return snapshot
    
    def should_checkpoint(self, agent_id: str) -> bool:
        """Check if agent should create a checkpoint."""
        if not self.auto_checkpoint:
            return False
        
        last = self._last_checkpoint.get(agent_id, 0)
        return (time.time() - last) >= self.checkpoint_interval
    
    def get_agent_ids(self) -> List[str]:
        """Get all stored agent IDs."""
        keys = self.state_manager.list("agent:")
        return [k.replace("agent:", "") for k in keys if not k.startswith("checkpoint:")]


class AgentRecoveryManager:
    """
    Manages agent recovery and failure handling.
    
    Example:
        >>> recovery = AgentRecoveryManager()
        >>> 
        >>> # Register failure
        >>> recovery.on_failure(agent_id, error)
        >>> 
        >>> # Attempt recovery
        >>> if recovery.can_recover(agent_id):
        ...     snapshot = recovery.recover(agent_id)
    """
    
    def __init__(
        self,
        state_store: AgentStateStore = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        backoff_multiplier: float = 2.0,
    ):
        self.state_store = state_store or AgentStateStore()
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.backoff_multiplier = backoff_multiplier
        
        self._failure_counts: Dict[str, int] = {}
        self._last_failures: Dict[str, datetime] = {}
        self._recovery_callbacks: List[Callable] = []
    
    def on_failure(
        self,
        agent_id: str,
        error: Exception,
        context: Dict = None,
    ) -> None:
        """Record agent failure."""
        self._failure_counts[agent_id] = self._failure_counts.get(agent_id, 0) + 1
        self._last_failures[agent_id] = datetime.now()
        
        logger.error(f"Agent {agent_id} failed: {error}")
        
        # Auto-checkpoint on failure if possible
        try:
            self.state_store.checkpoint(
                agent_id,
                status=AgentStatus.FAILED,
                context_summary=str(error),
                last_action=context.get("last_action") if context else None,
            )
        except Exception as e:
            logger.error(f"Failed to checkpoint on failure: {e}")
    
    def can_recover(self, agent_id: str) -> bool:
        """Check if agent can be recovered."""
        failures = self._failure_counts.get(agent_id, 0)
        return failures < self.max_retries
    
    def get_retry_delay(self, agent_id: str) -> float:
        """Get delay before next retry (with exponential backoff)."""
        failures = self._failure_counts.get(agent_id, 0)
        return self.retry_delay * (self.backoff_multiplier ** failures)
    
    def recover(
        self,
        agent_id: str,
        from_step: int = None,
    ) -> Optional[AgentSnapshot]:
        """
        Attempt to recover an agent.
        
        Returns snapshot if recovery is possible, None otherwise.
        """
        if not self.can_recover(agent_id):
            logger.error(f"Agent {agent_id} exceeded max recovery attempts")
            return None
        
        # Wait for backoff delay
        delay = self.get_retry_delay(agent_id)
        logger.info(f"Waiting {delay:.1f}s before recovery attempt for {agent_id}")
        time.sleep(delay)
        
        # Attempt recovery
        snapshot = self.state_store.recover(agent_id, from_step)
        
        if snapshot:
            snapshot.status = AgentStatus.RECOVERING
            for callback in self._recovery_callbacks:
                try:
                    callback(agent_id, snapshot)
                except Exception as e:
                    logger.error(f"Recovery callback error: {e}")
        
        return snapshot
    
    def reset_failures(self, agent_id: str) -> None:
        """Reset failure count for agent (on successful recovery)."""
        self._failure_counts[agent_id] = 0
        if agent_id in self._last_failures:
            del self._last_failures[agent_id]
    
    def on_recovery(self, callback: Callable[[str, AgentSnapshot], None]) -> None:
        """Register recovery callback."""
        self._recovery_callbacks.append(callback)
    
    def get_failure_stats(self, agent_id: str = None) -> Dict[str, Any]:
        """Get failure statistics."""
        if agent_id:
            return {
                "agent_id": agent_id,
                "failure_count": self._failure_counts.get(agent_id, 0),
                "last_failure": self._last_failures.get(agent_id, None),
                "can_recover": self.can_recover(agent_id),
                "next_retry_delay": self.get_retry_delay(agent_id),
            }
        
        return {
            "total_failures": sum(self._failure_counts.values()),
            "agents_with_failures": list(self._failure_counts.keys()),
            "failure_counts": dict(self._failure_counts),
        }


__all__ = [
    "AgentStatus",
    "AgentSnapshot",
    "AgentCheckpoint",
    "AgentStateStore",
    "AgentRecoveryManager",
]
