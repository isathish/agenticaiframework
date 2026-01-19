"""
Tool State Management.

Provides state tracking for tool execution, caching, and retries.
"""

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .manager import StateManager, StateType

logger = logging.getLogger(__name__)


class ToolExecutionStatus(Enum):
    """Status of tool execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


@dataclass
class ToolExecution:
    """Single tool execution record."""
    execution_id: str
    tool_name: str
    status: ToolExecutionStatus
    args: Dict[str, Any]
    result: Any = None
    error: Optional[str] = None
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    duration_ms: int = 0
    retry_count: int = 0
    agent_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "tool_name": self.tool_name,
            "status": self.status.value,
            "args": self.args,
            "result": self.result,
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_ms": self.duration_ms,
            "retry_count": self.retry_count,
            "agent_id": self.agent_id,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolExecution":
        return cls(
            execution_id=data["execution_id"],
            tool_name=data["tool_name"],
            status=ToolExecutionStatus(data["status"]),
            args=data.get("args", {}),
            result=data.get("result"),
            error=data.get("error"),
            started_at=data.get("started_at", datetime.now().isoformat()),
            completed_at=data.get("completed_at"),
            duration_ms=data.get("duration_ms", 0),
            retry_count=data.get("retry_count", 0),
            agent_id=data.get("agent_id"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ToolCacheEntry:
    """Cached tool result."""
    cache_key: str
    tool_name: str
    args_hash: str
    result: Any
    cached_at: str = field(default_factory=lambda: datetime.now().isoformat())
    expires_at: Optional[str] = None
    hit_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "cache_key": self.cache_key,
            "tool_name": self.tool_name,
            "args_hash": self.args_hash,
            "result": self.result,
            "cached_at": self.cached_at,
            "expires_at": self.expires_at,
            "hit_count": self.hit_count,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolCacheEntry":
        return cls(
            cache_key=data["cache_key"],
            tool_name=data["tool_name"],
            args_hash=data["args_hash"],
            result=data.get("result"),
            cached_at=data.get("cached_at", datetime.now().isoformat()),
            expires_at=data.get("expires_at"),
            hit_count=data.get("hit_count", 0),
        )
    
    @property
    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        return datetime.fromisoformat(self.expires_at) < datetime.now()


@dataclass
class RetryState:
    """Retry state for failed executions."""
    execution_id: str
    tool_name: str
    attempt: int
    max_attempts: int
    next_retry_at: str
    backoff_seconds: float
    last_error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "tool_name": self.tool_name,
            "attempt": self.attempt,
            "max_attempts": self.max_attempts,
            "next_retry_at": self.next_retry_at,
            "backoff_seconds": self.backoff_seconds,
            "last_error": self.last_error,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RetryState":
        return cls(
            execution_id=data["execution_id"],
            tool_name=data["tool_name"],
            attempt=data.get("attempt", 0),
            max_attempts=data.get("max_attempts", 3),
            next_retry_at=data.get("next_retry_at", datetime.now().isoformat()),
            backoff_seconds=data.get("backoff_seconds", 1.0),
            last_error=data.get("last_error"),
        )
    
    @property
    def can_retry(self) -> bool:
        return self.attempt < self.max_attempts
    
    @property
    def is_ready(self) -> bool:
        return datetime.fromisoformat(self.next_retry_at) <= datetime.now()


@dataclass
class ToolStats:
    """Statistics for a tool."""
    tool_name: str
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    total_duration_ms: int = 0
    avg_duration_ms: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0
    last_executed: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "total_executions": self.total_executions,
            "successful_executions": self.successful_executions,
            "failed_executions": self.failed_executions,
            "total_duration_ms": self.total_duration_ms,
            "avg_duration_ms": self.avg_duration_ms,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "last_executed": self.last_executed,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolStats":
        return cls(
            tool_name=data["tool_name"],
            total_executions=data.get("total_executions", 0),
            successful_executions=data.get("successful_executions", 0),
            failed_executions=data.get("failed_executions", 0),
            total_duration_ms=data.get("total_duration_ms", 0),
            avg_duration_ms=data.get("avg_duration_ms", 0.0),
            cache_hits=data.get("cache_hits", 0),
            cache_misses=data.get("cache_misses", 0),
            last_executed=data.get("last_executed"),
        )


class ToolStateManager:
    """
    Manages state for tool execution, caching, and retries.
    
    Example:
        >>> tool_state = ToolStateManager()
        >>> 
        >>> # Start execution
        >>> exec = tool_state.start_execution("search", {"query": "AI"})
        >>> 
        >>> # Complete execution
        >>> tool_state.complete_execution(exec.execution_id, result={"items": [...]})
        >>> 
        >>> # Use caching
        >>> cached = tool_state.get_cached_result("search", {"query": "AI"})
        >>> if not cached:
        ...     result = run_search(...)
        ...     tool_state.cache_result("search", {"query": "AI"}, result)
    """
    
    def __init__(
        self,
        state_manager: StateManager = None,
        default_cache_ttl: int = 3600,  # 1 hour
        default_max_retries: int = 3,
        default_backoff_base: float = 2.0,
    ):
        self.state_manager = state_manager or StateManager()
        self.default_cache_ttl = default_cache_ttl
        self.default_max_retries = default_max_retries
        self.default_backoff_base = default_backoff_base
    
    def _hash_args(self, args: Dict[str, Any]) -> str:
        """Create hash from arguments."""
        import json
        args_str = json.dumps(args, sort_keys=True, default=str)
        return hashlib.sha256(args_str.encode()).hexdigest()[:16]
    
    # Execution Tracking
    def start_execution(
        self,
        tool_name: str,
        args: Dict[str, Any],
        agent_id: str = None,
        metadata: Dict = None,
    ) -> ToolExecution:
        """Start a tool execution."""
        import uuid
        execution_id = f"exec-{uuid.uuid4().hex[:8]}"
        
        execution = ToolExecution(
            execution_id=execution_id,
            tool_name=tool_name,
            status=ToolExecutionStatus.RUNNING,
            args=args,
            agent_id=agent_id,
            metadata=metadata or {},
        )
        
        self.state_manager.save(
            f"tool_exec:{execution_id}",
            execution.to_dict(),
            StateType.TOOL,
        )
        
        return execution
    
    def complete_execution(
        self,
        execution_id: str,
        result: Any,
        cache: bool = False,
        cache_ttl: int = None,
    ) -> bool:
        """Mark execution as completed."""
        data = self.state_manager.get(f"tool_exec:{execution_id}")
        if not data:
            return False
        
        execution = ToolExecution.from_dict(data)
        execution.status = ToolExecutionStatus.COMPLETED
        execution.result = result
        execution.completed_at = datetime.now().isoformat()
        
        # Calculate duration
        started = datetime.fromisoformat(execution.started_at)
        duration = (datetime.now() - started).total_seconds() * 1000
        execution.duration_ms = int(duration)
        
        self.state_manager.save(
            f"tool_exec:{execution_id}",
            execution.to_dict(),
            StateType.TOOL,
        )
        
        # Update stats
        self._update_stats(execution.tool_name, success=True, duration_ms=execution.duration_ms)
        
        # Cache result if requested
        if cache:
            self.cache_result(
                execution.tool_name,
                execution.args,
                result,
                ttl=cache_ttl or self.default_cache_ttl,
            )
        
        return True
    
    def fail_execution(
        self,
        execution_id: str,
        error: str,
        schedule_retry: bool = False,
    ) -> Optional[RetryState]:
        """Mark execution as failed."""
        data = self.state_manager.get(f"tool_exec:{execution_id}")
        if not data:
            return None
        
        execution = ToolExecution.from_dict(data)
        execution.status = ToolExecutionStatus.FAILED
        execution.error = error
        execution.completed_at = datetime.now().isoformat()
        
        # Calculate duration
        started = datetime.fromisoformat(execution.started_at)
        duration = (datetime.now() - started).total_seconds() * 1000
        execution.duration_ms = int(duration)
        
        self.state_manager.save(
            f"tool_exec:{execution_id}",
            execution.to_dict(),
            StateType.TOOL,
        )
        
        # Update stats
        self._update_stats(execution.tool_name, success=False, duration_ms=execution.duration_ms)
        
        # Schedule retry if requested
        if schedule_retry:
            return self._schedule_retry(execution, error)
        
        return None
    
    def cancel_execution(self, execution_id: str) -> bool:
        """Cancel an execution."""
        data = self.state_manager.get(f"tool_exec:{execution_id}")
        if not data:
            return False
        
        execution = ToolExecution.from_dict(data)
        if execution.status in [ToolExecutionStatus.COMPLETED, ToolExecutionStatus.FAILED]:
            return False
        
        execution.status = ToolExecutionStatus.CANCELLED
        execution.completed_at = datetime.now().isoformat()
        
        self.state_manager.save(
            f"tool_exec:{execution_id}",
            execution.to_dict(),
            StateType.TOOL,
        )
        
        return True
    
    def get_execution(self, execution_id: str) -> Optional[ToolExecution]:
        """Get execution by ID."""
        data = self.state_manager.get(f"tool_exec:{execution_id}")
        if data:
            return ToolExecution.from_dict(data)
        return None
    
    def get_pending_executions(self, tool_name: str = None) -> List[ToolExecution]:
        """Get all pending/running executions."""
        keys = self.state_manager.list("tool_exec:")
        executions = []
        
        for key in keys:
            data = self.state_manager.get(key)
            if data:
                execution = ToolExecution.from_dict(data)
                if execution.status in [ToolExecutionStatus.PENDING, ToolExecutionStatus.RUNNING]:
                    if tool_name is None or execution.tool_name == tool_name:
                        executions.append(execution)
        
        return executions
    
    # Caching
    def cache_result(
        self,
        tool_name: str,
        args: Dict[str, Any],
        result: Any,
        ttl: int = None,
    ) -> str:
        """Cache tool result."""
        args_hash = self._hash_args(args)
        cache_key = f"tool_cache:{tool_name}:{args_hash}"
        
        expires_at = None
        if ttl:
            expires_at = (datetime.now() + timedelta(seconds=ttl)).isoformat()
        
        entry = ToolCacheEntry(
            cache_key=cache_key,
            tool_name=tool_name,
            args_hash=args_hash,
            result=result,
            expires_at=expires_at,
        )
        
        self.state_manager.save(cache_key, entry.to_dict(), StateType.TOOL)
        return cache_key
    
    def get_cached_result(
        self,
        tool_name: str,
        args: Dict[str, Any],
    ) -> Optional[Any]:
        """Get cached result if available."""
        args_hash = self._hash_args(args)
        cache_key = f"tool_cache:{tool_name}:{args_hash}"
        
        data = self.state_manager.get(cache_key)
        if not data:
            self._update_stats(tool_name, cache_miss=True)
            return None
        
        entry = ToolCacheEntry.from_dict(data)
        
        if entry.is_expired:
            self.state_manager.delete(cache_key)
            self._update_stats(tool_name, cache_miss=True)
            return None
        
        # Update hit count
        entry.hit_count += 1
        self.state_manager.save(cache_key, entry.to_dict(), StateType.TOOL)
        self._update_stats(tool_name, cache_hit=True)
        
        return entry.result
    
    def invalidate_cache(self, tool_name: str, args: Dict[str, Any] = None) -> int:
        """Invalidate cache entries."""
        if args:
            # Invalidate specific entry
            args_hash = self._hash_args(args)
            cache_key = f"tool_cache:{tool_name}:{args_hash}"
            return 1 if self.state_manager.delete(cache_key) else 0
        
        # Invalidate all entries for tool
        keys = self.state_manager.list(f"tool_cache:{tool_name}:")
        count = 0
        for key in keys:
            if self.state_manager.delete(key):
                count += 1
        return count
    
    def clear_expired_cache(self) -> int:
        """Clear all expired cache entries."""
        keys = self.state_manager.list("tool_cache:")
        count = 0
        
        for key in keys:
            data = self.state_manager.get(key)
            if data:
                entry = ToolCacheEntry.from_dict(data)
                if entry.is_expired:
                    if self.state_manager.delete(key):
                        count += 1
        
        return count
    
    # Retry Management
    def _schedule_retry(
        self,
        execution: ToolExecution,
        error: str,
    ) -> RetryState:
        """Schedule retry for failed execution."""
        attempt = execution.retry_count + 1
        
        # Exponential backoff
        backoff = self.default_backoff_base ** attempt
        next_retry = datetime.now() + timedelta(seconds=backoff)
        
        retry = RetryState(
            execution_id=execution.execution_id,
            tool_name=execution.tool_name,
            attempt=attempt,
            max_attempts=self.default_max_retries,
            next_retry_at=next_retry.isoformat(),
            backoff_seconds=backoff,
            last_error=error,
        )
        
        self.state_manager.save(
            f"tool_retry:{execution.execution_id}",
            retry.to_dict(),
            StateType.TOOL,
        )
        
        return retry
    
    def get_retry_state(self, execution_id: str) -> Optional[RetryState]:
        """Get retry state for execution."""
        data = self.state_manager.get(f"tool_retry:{execution_id}")
        if data:
            return RetryState.from_dict(data)
        return None
    
    def get_ready_retries(self) -> List[RetryState]:
        """Get all retry states that are ready to execute."""
        keys = self.state_manager.list("tool_retry:")
        ready = []
        
        for key in keys:
            data = self.state_manager.get(key)
            if data:
                retry = RetryState.from_dict(data)
                if retry.can_retry and retry.is_ready:
                    ready.append(retry)
        
        return ready
    
    def consume_retry(self, execution_id: str) -> Optional[ToolExecution]:
        """Consume retry and return execution for re-run."""
        retry = self.get_retry_state(execution_id)
        if not retry or not retry.can_retry or not retry.is_ready:
            return None
        
        # Get original execution
        data = self.state_manager.get(f"tool_exec:{execution_id}")
        if not data:
            return None
        
        execution = ToolExecution.from_dict(data)
        execution.status = ToolExecutionStatus.RETRYING
        execution.retry_count = retry.attempt
        execution.started_at = datetime.now().isoformat()
        execution.completed_at = None
        execution.result = None
        execution.error = None
        
        # Save updated execution
        self.state_manager.save(
            f"tool_exec:{execution_id}",
            execution.to_dict(),
            StateType.TOOL,
        )
        
        # Remove retry state
        self.state_manager.delete(f"tool_retry:{execution_id}")
        
        return execution
    
    def cancel_retry(self, execution_id: str) -> bool:
        """Cancel scheduled retry."""
        return self.state_manager.delete(f"tool_retry:{execution_id}")
    
    # Statistics
    def _update_stats(
        self,
        tool_name: str,
        success: bool = None,
        duration_ms: int = None,
        cache_hit: bool = False,
        cache_miss: bool = False,
    ):
        """Update tool statistics."""
        key = f"tool_stats:{tool_name}"
        data = self.state_manager.get(key)
        
        if data:
            stats = ToolStats.from_dict(data)
        else:
            stats = ToolStats(tool_name=tool_name)
        
        if success is not None:
            stats.total_executions += 1
            if success:
                stats.successful_executions += 1
            else:
                stats.failed_executions += 1
            
            if duration_ms:
                stats.total_duration_ms += duration_ms
                stats.avg_duration_ms = stats.total_duration_ms / stats.total_executions
            
            stats.last_executed = datetime.now().isoformat()
        
        if cache_hit:
            stats.cache_hits += 1
        if cache_miss:
            stats.cache_misses += 1
        
        self.state_manager.save(key, stats.to_dict(), StateType.TOOL)
    
    def get_stats(self, tool_name: str) -> Optional[ToolStats]:
        """Get statistics for a tool."""
        data = self.state_manager.get(f"tool_stats:{tool_name}")
        if data:
            return ToolStats.from_dict(data)
        return None
    
    def get_all_stats(self) -> List[ToolStats]:
        """Get statistics for all tools."""
        keys = self.state_manager.list("tool_stats:")
        stats = []
        
        for key in keys:
            data = self.state_manager.get(key)
            if data:
                stats.append(ToolStats.from_dict(data))
        
        return stats
    
    def reset_stats(self, tool_name: str = None) -> int:
        """Reset statistics."""
        if tool_name:
            return 1 if self.state_manager.delete(f"tool_stats:{tool_name}") else 0
        
        keys = self.state_manager.list("tool_stats:")
        count = 0
        for key in keys:
            if self.state_manager.delete(key):
                count += 1
        return count


__all__ = [
    "ToolExecutionStatus",
    "ToolExecution",
    "ToolCacheEntry",
    "RetryState",
    "ToolStats",
    "ToolStateManager",
]
