"""
Tool Memory Management.

Provides memory for tool operations:
- Tool result caching
- Execution history
- Parameter patterns
- Performance tracking
"""

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from .manager import MemoryManager

logger = logging.getLogger(__name__)


@dataclass
class ToolResultCache:
    """Cached tool result."""
    cache_key: str
    tool_name: str
    args_hash: str
    result: Any
    execution_time_ms: int
    cached_at: str = field(default_factory=lambda: datetime.now().isoformat())
    expires_at: Optional[str] = None
    hit_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "cache_key": self.cache_key,
            "tool_name": self.tool_name,
            "args_hash": self.args_hash,
            "result": self.result,
            "execution_time_ms": self.execution_time_ms,
            "cached_at": self.cached_at,
            "expires_at": self.expires_at,
            "hit_count": self.hit_count,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolResultCache":
        return cls(
            cache_key=data["cache_key"],
            tool_name=data["tool_name"],
            args_hash=data["args_hash"],
            result=data["result"],
            execution_time_ms=data.get("execution_time_ms", 0),
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
class ToolExecutionMemory:
    """Memory of a tool execution."""
    execution_id: str
    tool_name: str
    args: Dict[str, Any]
    result: Any
    success: bool
    error: Optional[str]
    execution_time_ms: int
    agent_id: Optional[str]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "tool_name": self.tool_name,
            "args": self.args,
            "result": self.result,
            "success": self.success,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms,
            "agent_id": self.agent_id,
            "timestamp": self.timestamp,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolExecutionMemory":
        return cls(
            execution_id=data["execution_id"],
            tool_name=data["tool_name"],
            args=data.get("args", {}),
            result=data.get("result"),
            success=data.get("success", True),
            error=data.get("error"),
            execution_time_ms=data.get("execution_time_ms", 0),
            agent_id=data.get("agent_id"),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
        )


@dataclass
class ToolPattern:
    """Pattern of tool usage."""
    pattern_id: str
    tool_name: str
    common_args: Dict[str, Any]  # Frequently used argument patterns
    use_count: int
    avg_execution_time_ms: float
    success_rate: float
    last_used: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "tool_name": self.tool_name,
            "common_args": self.common_args,
            "use_count": self.use_count,
            "avg_execution_time_ms": self.avg_execution_time_ms,
            "success_rate": self.success_rate,
            "last_used": self.last_used,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolPattern":
        return cls(
            pattern_id=data["pattern_id"],
            tool_name=data["tool_name"],
            common_args=data.get("common_args", {}),
            use_count=data.get("use_count", 0),
            avg_execution_time_ms=data.get("avg_execution_time_ms", 0.0),
            success_rate=data.get("success_rate", 1.0),
            last_used=data.get("last_used", datetime.now().isoformat()),
        )


@dataclass
class ToolPerformanceStats:
    """Performance statistics for a tool."""
    tool_name: str
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    total_time_ms: int = 0
    min_time_ms: int = 0
    max_time_ms: int = 0
    avg_time_ms: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0
    last_execution: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "total_executions": self.total_executions,
            "successful_executions": self.successful_executions,
            "failed_executions": self.failed_executions,
            "total_time_ms": self.total_time_ms,
            "min_time_ms": self.min_time_ms,
            "max_time_ms": self.max_time_ms,
            "avg_time_ms": self.avg_time_ms,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "last_execution": self.last_execution,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolPerformanceStats":
        return cls(
            tool_name=data["tool_name"],
            total_executions=data.get("total_executions", 0),
            successful_executions=data.get("successful_executions", 0),
            failed_executions=data.get("failed_executions", 0),
            total_time_ms=data.get("total_time_ms", 0),
            min_time_ms=data.get("min_time_ms", 0),
            max_time_ms=data.get("max_time_ms", 0),
            avg_time_ms=data.get("avg_time_ms", 0.0),
            cache_hits=data.get("cache_hits", 0),
            cache_misses=data.get("cache_misses", 0),
            last_execution=data.get("last_execution"),
        )
    
    @property
    def success_rate(self) -> float:
        if self.total_executions == 0:
            return 0.0
        return self.successful_executions / self.total_executions
    
    @property
    def cache_hit_rate(self) -> float:
        total = self.cache_hits + self.cache_misses
        if total == 0:
            return 0.0
        return self.cache_hits / total


class ToolMemoryManager:
    """
    Manages memory for tool operations.
    
    Example:
        >>> tool_memory = ToolMemoryManager()
        >>> 
        >>> # Cache tool result
        >>> tool_memory.cache_result("search", {"query": "AI"}, results, exec_time=100)
        >>> 
        >>> # Get cached result
        >>> cached = tool_memory.get_cached_result("search", {"query": "AI"})
        >>> 
        >>> # Record execution
        >>> tool_memory.record_execution("search", args, result, success=True)
        >>> 
        >>> # Get performance stats
        >>> stats = tool_memory.get_performance_stats("search")
    """
    
    def __init__(
        self,
        memory_manager: MemoryManager = None,
        default_cache_ttl: int = 3600,  # 1 hour
        max_execution_history: int = 1000,
    ):
        self.memory = memory_manager or MemoryManager()
        self.default_cache_ttl = default_cache_ttl
        self.max_execution_history = max_execution_history
        
        # In-memory storage
        self._result_cache: Dict[str, ToolResultCache] = {}
        self._execution_history: List[ToolExecutionMemory] = []
        self._patterns: Dict[str, ToolPattern] = {}
        self._stats: Dict[str, ToolPerformanceStats] = {}
    
    def _hash_args(self, args: Dict[str, Any]) -> str:
        """Create hash from arguments."""
        import json
        args_str = json.dumps(args, sort_keys=True, default=str)
        return hashlib.sha256(args_str.encode()).hexdigest()[:16]
    
    def _cache_key(self, tool_name: str, args: Dict[str, Any]) -> str:
        """Generate cache key."""
        args_hash = self._hash_args(args)
        return f"tool:{tool_name}:{args_hash}"
    
    # =========================================================================
    # Result Caching
    # =========================================================================
    
    def cache_result(
        self,
        tool_name: str,
        args: Dict[str, Any],
        result: Any,
        execution_time_ms: int = 0,
        ttl: int = None,
    ) -> str:
        """Cache a tool result."""
        cache_key = self._cache_key(tool_name, args)
        
        expires_at = None
        if ttl or self.default_cache_ttl:
            ttl = ttl or self.default_cache_ttl
            expires_at = (datetime.now() + timedelta(seconds=ttl)).isoformat()
        
        entry = ToolResultCache(
            cache_key=cache_key,
            tool_name=tool_name,
            args_hash=self._hash_args(args),
            result=result,
            execution_time_ms=execution_time_ms,
            expires_at=expires_at,
        )
        
        self._result_cache[cache_key] = entry
        
        self.memory.store_short_term(
            f"toolmem:{cache_key}",
            entry.to_dict(),
            ttl=ttl or self.default_cache_ttl,
            priority=5,
        )
        
        return cache_key
    
    def get_cached_result(
        self,
        tool_name: str,
        args: Dict[str, Any],
    ) -> Optional[Any]:
        """Get cached result if available."""
        cache_key = self._cache_key(tool_name, args)
        
        # Check in-memory cache
        if cache_key in self._result_cache:
            entry = self._result_cache[cache_key]
            if not entry.is_expired:
                entry.hit_count += 1
                self._update_stats(tool_name, cache_hit=True)
                return entry.result
            else:
                del self._result_cache[cache_key]
        
        # Check persistent cache
        data = self.memory.retrieve(f"toolmem:{cache_key}")
        if data:
            entry = ToolResultCache.from_dict(data)
            if not entry.is_expired:
                entry.hit_count += 1
                self._result_cache[cache_key] = entry
                self._update_stats(tool_name, cache_hit=True)
                return entry.result
        
        self._update_stats(tool_name, cache_miss=True)
        return None
    
    def invalidate_cache(
        self,
        tool_name: str = None,
        args: Dict[str, Any] = None,
    ) -> int:
        """Invalidate cache entries."""
        if tool_name and args:
            # Invalidate specific entry
            cache_key = self._cache_key(tool_name, args)
            if cache_key in self._result_cache:
                del self._result_cache[cache_key]
                return 1
            return 0
        
        # Invalidate all entries for tool or all
        count = 0
        keys_to_remove = []
        
        for key, entry in self._result_cache.items():
            if tool_name is None or entry.tool_name == tool_name:
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self._result_cache[key]
            count += 1
        
        return count
    
    # =========================================================================
    # Execution History
    # =========================================================================
    
    def record_execution(
        self,
        tool_name: str,
        args: Dict[str, Any],
        result: Any,
        success: bool = True,
        error: str = None,
        execution_time_ms: int = 0,
        agent_id: str = None,
    ) -> ToolExecutionMemory:
        """Record a tool execution."""
        import uuid
        
        execution = ToolExecutionMemory(
            execution_id=f"exec-{uuid.uuid4().hex[:8]}",
            tool_name=tool_name,
            args=args,
            result=result,
            success=success,
            error=error,
            execution_time_ms=execution_time_ms,
            agent_id=agent_id,
        )
        
        self._execution_history.append(execution)
        
        # Limit history
        while len(self._execution_history) > self.max_execution_history:
            self._execution_history.pop(0)
        
        # Update stats
        self._update_stats(
            tool_name,
            execution_time=execution_time_ms,
            success=success,
        )
        
        # Update patterns
        self._update_patterns(tool_name, args, success, execution_time_ms)
        
        # Persist recent history
        self.memory.store_long_term(
            "toolmem:execution_history",
            [e.to_dict() for e in self._execution_history[-100:]],
            priority=5,
        )
        
        return execution
    
    def get_execution_history(
        self,
        tool_name: str = None,
        agent_id: str = None,
        success_only: bool = False,
        last_n: int = None,
    ) -> List[ToolExecutionMemory]:
        """Get execution history."""
        if not self._execution_history:
            data = self.memory.retrieve("toolmem:execution_history", [])
            self._execution_history = [ToolExecutionMemory.from_dict(e) for e in data]
        
        history = self._execution_history
        
        if tool_name:
            history = [e for e in history if e.tool_name == tool_name]
        
        if agent_id:
            history = [e for e in history if e.agent_id == agent_id]
        
        if success_only:
            history = [e for e in history if e.success]
        
        if last_n:
            history = history[-last_n:]
        
        return history
    
    def get_last_result(
        self,
        tool_name: str,
        agent_id: str = None,
    ) -> Optional[Any]:
        """Get the last result for a tool."""
        history = self.get_execution_history(
            tool_name=tool_name,
            agent_id=agent_id,
            success_only=True,
            last_n=1,
        )
        return history[0].result if history else None
    
    def get_similar_executions(
        self,
        tool_name: str,
        args: Dict[str, Any],
        top_k: int = 5,
    ) -> List[ToolExecutionMemory]:
        """Find similar past executions."""
        history = self.get_execution_history(tool_name=tool_name)
        
        # Simple similarity based on matching argument keys
        target_keys = set(args.keys())
        
        scored = []
        for exec in history:
            exec_keys = set(exec.args.keys())
            overlap = len(target_keys & exec_keys)
            
            # Also check value similarity for matching keys
            value_matches = 0
            for key in target_keys & exec_keys:
                if args.get(key) == exec.args.get(key):
                    value_matches += 1
            
            score = overlap + value_matches * 2
            scored.append((score, exec))
        
        scored.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in scored[:top_k]]
    
    # =========================================================================
    # Patterns
    # =========================================================================
    
    def _update_patterns(
        self,
        tool_name: str,
        args: Dict[str, Any],
        success: bool,
        execution_time_ms: int,
    ):
        """Update usage patterns for a tool."""
        args_hash = self._hash_args(args)
        pattern_id = f"{tool_name}:{args_hash}"
        
        if pattern_id in self._patterns:
            pattern = self._patterns[pattern_id]
            pattern.use_count += 1
            
            # Update running averages
            n = pattern.use_count
            pattern.avg_execution_time_ms = (
                (pattern.avg_execution_time_ms * (n - 1) + execution_time_ms) / n
            )
            
            if success:
                old_success = pattern.success_rate * (n - 1)
                pattern.success_rate = (old_success + 1) / n
            else:
                old_success = pattern.success_rate * (n - 1)
                pattern.success_rate = old_success / n
            
            pattern.last_used = datetime.now().isoformat()
        else:
            pattern = ToolPattern(
                pattern_id=pattern_id,
                tool_name=tool_name,
                common_args=args,
                use_count=1,
                avg_execution_time_ms=float(execution_time_ms),
                success_rate=1.0 if success else 0.0,
                last_used=datetime.now().isoformat(),
            )
            self._patterns[pattern_id] = pattern
        
        # Persist patterns
        self.memory.store_long_term(
            f"toolmem:pattern:{pattern_id}",
            pattern.to_dict(),
            priority=4,
        )
    
    def get_common_patterns(
        self,
        tool_name: str,
        top_k: int = 5,
    ) -> List[ToolPattern]:
        """Get most common usage patterns for a tool."""
        patterns = [p for p in self._patterns.values() if p.tool_name == tool_name]
        patterns.sort(key=lambda p: p.use_count, reverse=True)
        return patterns[:top_k]
    
    def suggest_args(
        self,
        tool_name: str,
        partial_args: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Suggest arguments based on common patterns."""
        patterns = self.get_common_patterns(tool_name, top_k=10)
        
        if not patterns:
            return {}
        
        # Find pattern with highest success rate and usage
        best_pattern = max(patterns, key=lambda p: p.success_rate * p.use_count)
        
        suggested = best_pattern.common_args.copy()
        
        # Override with any provided partial args
        if partial_args:
            suggested.update(partial_args)
        
        return suggested
    
    # =========================================================================
    # Performance Stats
    # =========================================================================
    
    def _update_stats(
        self,
        tool_name: str,
        execution_time: int = None,
        success: bool = None,
        cache_hit: bool = False,
        cache_miss: bool = False,
    ):
        """Update performance statistics."""
        if tool_name not in self._stats:
            self._stats[tool_name] = ToolPerformanceStats(tool_name=tool_name)
        
        stats = self._stats[tool_name]
        
        if execution_time is not None:
            stats.total_executions += 1
            stats.total_time_ms += execution_time
            stats.avg_time_ms = stats.total_time_ms / stats.total_executions
            
            if stats.min_time_ms == 0 or execution_time < stats.min_time_ms:
                stats.min_time_ms = execution_time
            if execution_time > stats.max_time_ms:
                stats.max_time_ms = execution_time
            
            stats.last_execution = datetime.now().isoformat()
            
            if success is not None:
                if success:
                    stats.successful_executions += 1
                else:
                    stats.failed_executions += 1
        
        if cache_hit:
            stats.cache_hits += 1
        if cache_miss:
            stats.cache_misses += 1
        
        # Persist stats
        self.memory.store_long_term(
            f"toolmem:stats:{tool_name}",
            stats.to_dict(),
            priority=6,
        )
    
    def get_performance_stats(
        self,
        tool_name: str,
    ) -> Optional[ToolPerformanceStats]:
        """Get performance statistics for a tool."""
        if tool_name in self._stats:
            return self._stats[tool_name]
        
        data = self.memory.retrieve(f"toolmem:stats:{tool_name}")
        if data:
            stats = ToolPerformanceStats.from_dict(data)
            self._stats[tool_name] = stats
            return stats
        
        return None
    
    def get_all_stats(self) -> List[ToolPerformanceStats]:
        """Get performance statistics for all tools."""
        return list(self._stats.values())
    
    def get_slow_tools(
        self,
        threshold_ms: int = 1000,
    ) -> List[Tuple[str, float]]:
        """Get tools with average execution time above threshold."""
        slow = []
        for stats in self._stats.values():
            if stats.avg_time_ms > threshold_ms:
                slow.append((stats.tool_name, stats.avg_time_ms))
        slow.sort(key=lambda x: x[1], reverse=True)
        return slow
    
    def get_failing_tools(
        self,
        threshold: float = 0.1,  # 10% failure rate
    ) -> List[Tuple[str, float]]:
        """Get tools with failure rate above threshold."""
        failing = []
        for stats in self._stats.values():
            failure_rate = 1 - stats.success_rate
            if failure_rate > threshold:
                failing.append((stats.tool_name, failure_rate))
        failing.sort(key=lambda x: x[1], reverse=True)
        return failing
    
    # =========================================================================
    # Cleanup
    # =========================================================================
    
    def cleanup_expired(self) -> int:
        """Clean up expired cache entries."""
        count = 0
        expired = [k for k, v in self._result_cache.items() if v.is_expired]
        for key in expired:
            del self._result_cache[key]
            count += 1
        return count
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        return {
            "cached_results": len(self._result_cache),
            "execution_history_size": len(self._execution_history),
            "patterns_tracked": len(self._patterns),
            "tools_tracked": len(self._stats),
        }


__all__ = [
    "ToolResultCache",
    "ToolExecutionMemory",
    "ToolPattern",
    "ToolPerformanceStats",
    "ToolMemoryManager",
]
