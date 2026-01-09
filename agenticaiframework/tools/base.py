"""
Base Tool Classes and Types.

Provides the foundation for all tools in the framework.
"""

import uuid
import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Callable
from enum import Enum

logger = logging.getLogger(__name__)


class ToolStatus(Enum):
    """Status of tool execution."""
    SUCCESS = "success"
    ERROR = "error"
    PENDING = "pending"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class ToolConfig:
    """Configuration for a tool."""
    name: str
    description: str = ""
    version: str = "1.0.0"
    timeout: float = 30.0
    retry_count: int = 3
    retry_delay: float = 1.0
    cache_enabled: bool = True
    cache_ttl: int = 3600
    rate_limit: Optional[int] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    extra_config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    """Result of tool execution."""
    tool_name: str
    status: ToolStatus
    data: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    result_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    
    @property
    def is_success(self) -> bool:
        """Check if execution was successful."""
        return self.status == ToolStatus.SUCCESS
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'result_id': self.result_id,
            'tool_name': self.tool_name,
            'status': self.status.value,
            'data': self.data,
            'error': self.error,
            'execution_time': self.execution_time,
            'metadata': self.metadata,
            'timestamp': self.timestamp,
        }


class BaseTool(ABC):
    """
    Abstract base class for all tools.
    
    Provides common functionality:
    - Configuration management
    - Execution with retry logic
    - Caching
    - Logging and metrics
    """
    
    def __init__(self, config: Optional[ToolConfig] = None):
        self.config = config or ToolConfig(name=self.__class__.__name__)
        self._cache: Dict[str, Any] = {}
        self._cache_timestamps: Dict[str, float] = {}
        self._execution_count = 0
        self._error_count = 0
        self._total_execution_time = 0.0
        self._hooks: Dict[str, List[Callable]] = {
            'before_execute': [],
            'after_execute': [],
            'on_error': [],
        }
    
    @property
    def name(self) -> str:
        """Get tool name."""
        return self.config.name
    
    @property
    def description(self) -> str:
        """Get tool description."""
        return self.config.description
    
    @abstractmethod
    def _execute(self, **kwargs) -> Any:
        """
        Execute the tool's main functionality.
        
        Must be implemented by subclasses.
        """
        pass
    
    def execute(self, **kwargs) -> ToolResult:
        """
        Execute the tool with retry logic and caching.
        
        Args:
            **kwargs: Tool-specific parameters
            
        Returns:
            ToolResult with execution results
        """
        start_time = time.time()
        cache_key = self._get_cache_key(**kwargs)
        
        # Check cache
        if self.config.cache_enabled and cache_key in self._cache:
            cached_time = self._cache_timestamps.get(cache_key, 0)
            if time.time() - cached_time < self.config.cache_ttl:
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.SUCCESS,
                    data=self._cache[cache_key],
                    metadata={'cached': True},
                    execution_time=time.time() - start_time,
                )
        
        # Run before hooks
        self._run_hooks('before_execute', kwargs)
        
        last_error = None
        for attempt in range(self.config.retry_count):
            try:
                result = self._execute(**kwargs)
                
                # Cache result
                if self.config.cache_enabled:
                    self._cache[cache_key] = result
                    self._cache_timestamps[cache_key] = time.time()
                
                execution_time = time.time() - start_time
                self._execution_count += 1
                self._total_execution_time += execution_time
                
                tool_result = ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.SUCCESS,
                    data=result,
                    execution_time=execution_time,
                    metadata={'attempt': attempt + 1},
                )
                
                # Run after hooks
                self._run_hooks('after_execute', tool_result)
                
                return tool_result
                
            except Exception as e:
                last_error = str(e)
                logger.warning(
                    "Tool %s attempt %d failed: %s",
                    self.name, attempt + 1, last_error
                )
                
                if attempt < self.config.retry_count - 1:
                    time.sleep(self.config.retry_delay)
        
        # All retries failed
        self._error_count += 1
        execution_time = time.time() - start_time
        
        error_result = ToolResult(
            tool_name=self.name,
            status=ToolStatus.ERROR,
            error=last_error,
            execution_time=execution_time,
            metadata={'attempts': self.config.retry_count},
        )
        
        # Run error hooks
        self._run_hooks('on_error', error_result)
        
        return error_result
    
    def _get_cache_key(self, **kwargs) -> str:
        """Generate cache key from parameters."""
        import hashlib
        import json
        
        key_data = json.dumps(kwargs, sort_keys=True, default=str)
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def add_hook(self, event: str, callback: Callable):
        """Add a hook callback for an event."""
        if event in self._hooks:
            self._hooks[event].append(callback)
    
    def _run_hooks(self, event: str, data: Any):
        """Run all hooks for an event."""
        for hook in self._hooks.get(event, []):
            try:
                hook(data)
            except Exception as e:
                logger.error("Hook error for %s: %s", event, e)
    
    def clear_cache(self):
        """Clear the tool's cache."""
        self._cache.clear()
        self._cache_timestamps.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get execution statistics."""
        return {
            'tool_name': self.name,
            'execution_count': self._execution_count,
            'error_count': self._error_count,
            'success_rate': (
                (self._execution_count - self._error_count) / self._execution_count
                if self._execution_count > 0 else 0
            ),
            'avg_execution_time': (
                self._total_execution_time / self._execution_count
                if self._execution_count > 0 else 0
            ),
            'cache_size': len(self._cache),
        }
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}')"


class AsyncBaseTool(BaseTool):
    """
    Async version of BaseTool for I/O-bound operations.
    """
    
    @abstractmethod
    async def _execute_async(self, **kwargs) -> Any:
        """Async execution method."""
        pass
    
    def _execute(self, **kwargs) -> Any:
        """Sync wrapper for async execution."""
        import asyncio
        
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running loop, create one
            return asyncio.run(self._execute_async(**kwargs))
        
        # Loop is running, use thread pool
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, self._execute_async(**kwargs))
            return future.result()
    
    async def execute_async(self, **kwargs) -> ToolResult:
        """Execute the tool asynchronously."""
        start_time = time.time()
        
        try:
            result = await self._execute_async(**kwargs)
            
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                data=result,
                execution_time=time.time() - start_time,
            )
        except Exception as e:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error=str(e),
                execution_time=time.time() - start_time,
            )


__all__ = [
    'ToolStatus',
    'ToolConfig',
    'ToolResult',
    'BaseTool',
    'AsyncBaseTool',
]
