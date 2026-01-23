"""
Enterprise Fallback Module.

Provides fallback chains, degraded mode handling, and backup providers
for resilient agent operations.

Example:
    # Fallback chain
    chain = FallbackChain([
        openai_handler,
        anthropic_handler,
        local_handler,
    ])
    result = await chain.execute(request)
    
    # Degraded mode
    @with_degraded_mode(fallback_value=cached_response)
    async def get_response(query: str) -> str:
        return await llm.complete(query)
"""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Type,
    TypeVar,
    Union,
)
from functools import wraps
from enum import Enum
import logging

logger = logging.getLogger(__name__)

T = TypeVar("T")
R = TypeVar("R")


class FallbackError(Exception):
    """All fallbacks exhausted."""
    
    def __init__(self, message: str, errors: Optional[List[Exception]] = None):
        super().__init__(message)
        self.errors = errors or []


class DegradedModeError(Exception):
    """Degraded mode operation failed."""
    pass


class FallbackReason(str, Enum):
    """Reasons for fallback activation."""
    PRIMARY_FAILED = "primary_failed"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    CIRCUIT_OPEN = "circuit_open"
    HEALTH_CHECK_FAILED = "health_check_failed"
    MANUAL = "manual"


class OperationMode(str, Enum):
    """System operation modes."""
    NORMAL = "normal"
    DEGRADED = "degraded"
    MAINTENANCE = "maintenance"
    EMERGENCY = "emergency"


@dataclass
class FallbackResult(Generic[T]):
    """Result from fallback execution."""
    value: T
    handler_index: int
    handler_name: str
    attempts: int
    total_latency: float
    reason: Optional[FallbackReason] = None
    errors: List[Exception] = field(default_factory=list)
    
    @property
    def used_fallback(self) -> bool:
        """Check if fallback was used."""
        return self.handler_index > 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "handler_name": self.handler_name,
            "handler_index": self.handler_index,
            "attempts": self.attempts,
            "total_latency": self.total_latency,
            "used_fallback": self.used_fallback,
            "reason": self.reason.value if self.reason else None,
            "error_count": len(self.errors),
        }


@dataclass
class FallbackHandler:
    """Configuration for a fallback handler."""
    handler: Callable
    name: str
    timeout: float = 30.0
    retry_count: int = 1
    enabled: bool = True
    conditions: Optional[List[Callable[[Exception], bool]]] = None
    
    def should_use_for(self, error: Exception) -> bool:
        """Check if this handler should be used for the given error."""
        if not self.conditions:
            return True
        return any(cond(error) for cond in self.conditions)


class FallbackChain(Generic[T, R]):
    """
    Chain of fallback handlers executed in order.
    """
    
    def __init__(
        self,
        handlers: List[Union[Callable, FallbackHandler]],
        timeout: float = 30.0,
        continue_on_success: bool = False,
    ):
        """
        Initialize fallback chain.
        
        Args:
            handlers: List of handlers or handler configs
            timeout: Default timeout per handler
            continue_on_success: Run all handlers even on success
        """
        self._handlers: List[FallbackHandler] = []
        
        for i, h in enumerate(handlers):
            if isinstance(h, FallbackHandler):
                self._handlers.append(h)
            else:
                self._handlers.append(FallbackHandler(
                    handler=h,
                    name=getattr(h, "__name__", f"handler_{i}"),
                    timeout=timeout,
                ))
        
        self.continue_on_success = continue_on_success
    
    async def execute(self, *args: Any, **kwargs: Any) -> FallbackResult[R]:
        """
        Execute the fallback chain.
        
        Args:
            *args: Positional arguments for handlers
            **kwargs: Keyword arguments for handlers
            
        Returns:
            FallbackResult with value and execution info
        """
        start = time.time()
        errors: List[Exception] = []
        attempts = 0
        last_error: Optional[Exception] = None
        
        for i, fh in enumerate(self._handlers):
            if not fh.enabled:
                continue
            
            # Check conditions
            if last_error and not fh.should_use_for(last_error):
                continue
            
            for retry in range(fh.retry_count):
                attempts += 1
                
                try:
                    if asyncio.iscoroutinefunction(fh.handler):
                        result = await asyncio.wait_for(
                            fh.handler(*args, **kwargs),
                            timeout=fh.timeout,
                        )
                    else:
                        result = fh.handler(*args, **kwargs)
                    
                    return FallbackResult(
                        value=result,
                        handler_index=i,
                        handler_name=fh.name,
                        attempts=attempts,
                        total_latency=time.time() - start,
                        reason=FallbackReason.PRIMARY_FAILED if i > 0 else None,
                        errors=errors,
                    )
                    
                except asyncio.TimeoutError as e:
                    last_error = e
                    errors.append(e)
                    logger.warning(f"Handler {fh.name} timed out")
                    
                except Exception as e:
                    last_error = e
                    errors.append(e)
                    logger.warning(f"Handler {fh.name} failed: {e}")
        
        raise FallbackError(
            f"All {len(self._handlers)} handlers failed after {attempts} attempts",
            errors=errors,
        )
    
    def add_handler(
        self,
        handler: Union[Callable, FallbackHandler],
        position: Optional[int] = None,
    ) -> 'FallbackChain':
        """Add a handler to the chain."""
        if isinstance(handler, FallbackHandler):
            fh = handler
        else:
            fh = FallbackHandler(
                handler=handler,
                name=getattr(handler, "__name__", f"handler_{len(self._handlers)}"),
            )
        
        if position is not None:
            self._handlers.insert(position, fh)
        else:
            self._handlers.append(fh)
        
        return self
    
    def remove_handler(self, name: str) -> bool:
        """Remove a handler by name."""
        for i, fh in enumerate(self._handlers):
            if fh.name == name:
                del self._handlers[i]
                return True
        return False


class DegradedModeManager:
    """
    Manages degraded mode operations for the system.
    """
    
    def __init__(self):
        self._mode = OperationMode.NORMAL
        self._fallback_values: Dict[str, Any] = {}
        self._mode_listeners: List[Callable[[OperationMode], None]] = []
        self._feature_flags: Dict[str, bool] = {}
    
    @property
    def mode(self) -> OperationMode:
        """Current operation mode."""
        return self._mode
    
    @property
    def is_degraded(self) -> bool:
        """Check if system is in degraded mode."""
        return self._mode != OperationMode.NORMAL
    
    def set_mode(self, mode: OperationMode) -> None:
        """Set the operation mode."""
        old_mode = self._mode
        self._mode = mode
        
        if old_mode != mode:
            logger.info(f"Operation mode changed: {old_mode.value} -> {mode.value}")
            for listener in self._mode_listeners:
                try:
                    listener(mode)
                except Exception as e:
                    logger.error(f"Mode listener error: {e}")
    
    def add_mode_listener(self, listener: Callable[[OperationMode], None]) -> None:
        """Add a listener for mode changes."""
        self._mode_listeners.append(listener)
    
    def set_fallback_value(self, key: str, value: Any) -> None:
        """Set a fallback value for degraded mode."""
        self._fallback_values[key] = value
    
    def get_fallback_value(self, key: str, default: Any = None) -> Any:
        """Get a fallback value."""
        return self._fallback_values.get(key, default)
    
    def set_feature(self, feature: str, enabled: bool) -> None:
        """Enable or disable a feature."""
        self._feature_flags[feature] = enabled
    
    def is_feature_enabled(self, feature: str, default: bool = True) -> bool:
        """Check if a feature is enabled."""
        if self._mode == OperationMode.EMERGENCY:
            return False  # All features disabled in emergency
        
        return self._feature_flags.get(feature, default)


# Global degraded mode manager
_degraded_manager = DegradedModeManager()


def get_degraded_manager() -> DegradedModeManager:
    """Get the global degraded mode manager."""
    return _degraded_manager


def with_fallback(
    fallback: Callable[..., T],
    catch: Optional[List[Type[Exception]]] = None,
) -> Callable:
    """
    Decorator to add a fallback handler.
    
    Example:
        @with_fallback(lambda x: "default")
        async def get_value(x: str) -> str:
            return await risky_operation(x)
    """
    catch_types = tuple(catch) if catch else (Exception,)
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
            try:
                return await func(*args, **kwargs)
            except catch_types as e:
                logger.warning(f"Using fallback for {func.__name__}: {e}")
                if asyncio.iscoroutinefunction(fallback):
                    return await fallback(*args, **kwargs)
                return fallback(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            try:
                return func(*args, **kwargs)
            except catch_types as e:
                logger.warning(f"Using fallback for {func.__name__}: {e}")
                return fallback(*args, **kwargs)
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


def with_degraded_mode(
    fallback_value: Any = None,
    fallback_func: Optional[Callable] = None,
    key: Optional[str] = None,
) -> Callable:
    """
    Decorator for degraded mode handling.
    
    Example:
        @with_degraded_mode(fallback_value="cached_response")
        async def get_response(query: str) -> str:
            return await llm.complete(query)
    """
    def decorator(func: Callable) -> Callable:
        func_key = key or func.__name__
        
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            manager = get_degraded_manager()
            
            if manager.is_degraded:
                # Return fallback
                if fallback_func:
                    if asyncio.iscoroutinefunction(fallback_func):
                        return await fallback_func(*args, **kwargs)
                    return fallback_func(*args, **kwargs)
                
                cached = manager.get_fallback_value(func_key)
                if cached is not None:
                    return cached
                
                return fallback_value
            
            try:
                result = await func(*args, **kwargs)
                # Cache result for degraded mode
                manager.set_fallback_value(func_key, result)
                return result
            except Exception as e:
                # Try fallback
                cached = manager.get_fallback_value(func_key)
                if cached is not None:
                    logger.warning(f"Using cached value for {func_key}: {e}")
                    return cached
                
                if fallback_value is not None:
                    return fallback_value
                
                raise
        
        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            manager = get_degraded_manager()
            
            if manager.is_degraded:
                if fallback_func:
                    return fallback_func(*args, **kwargs)
                
                cached = manager.get_fallback_value(func_key)
                if cached is not None:
                    return cached
                
                return fallback_value
            
            try:
                result = func(*args, **kwargs)
                manager.set_fallback_value(func_key, result)
                return result
            except Exception as e:
                cached = manager.get_fallback_value(func_key)
                if cached is not None:
                    logger.warning(f"Using cached value for {func_key}: {e}")
                    return cached
                
                if fallback_value is not None:
                    return fallback_value
                
                raise
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


def require_feature(feature: str, fallback: Any = None) -> Callable:
    """
    Decorator to require a feature flag.
    
    Example:
        @require_feature("advanced_mode")
        async def advanced_operation():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            if not get_degraded_manager().is_feature_enabled(feature):
                if fallback is not None:
                    return fallback
                raise DegradedModeError(f"Feature {feature} is disabled")
            return await func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            if not get_degraded_manager().is_feature_enabled(feature):
                if fallback is not None:
                    return fallback
                raise DegradedModeError(f"Feature {feature} is disabled")
            return func(*args, **kwargs)
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


class BackupProvider(ABC, Generic[T]):
    """Abstract backup data provider."""
    
    @abstractmethod
    async def get(self, key: str) -> Optional[T]:
        """Get backup data."""
        pass
    
    @abstractmethod
    async def set(self, key: str, value: T) -> None:
        """Store backup data."""
        pass


class InMemoryBackupProvider(BackupProvider[T]):
    """In-memory backup provider."""
    
    def __init__(self):
        self._data: Dict[str, T] = {}
    
    async def get(self, key: str) -> Optional[T]:
        return self._data.get(key)
    
    async def set(self, key: str, value: T) -> None:
        self._data[key] = value


class FileBackupProvider(BackupProvider[T]):
    """File-based backup provider."""
    
    def __init__(self, directory: str):
        import os
        import json
        self.directory = directory
        os.makedirs(directory, exist_ok=True)
    
    async def get(self, key: str) -> Optional[T]:
        import os
        import json
        
        path = os.path.join(self.directory, f"{key}.json")
        if not os.path.exists(path):
            return None
        
        with open(path, "r") as f:
            return json.load(f)
    
    async def set(self, key: str, value: T) -> None:
        import os
        import json
        
        path = os.path.join(self.directory, f"{key}.json")
        with open(path, "w") as f:
            json.dump(value, f)


class FallbackProvider(Generic[T]):
    """
    Provider with primary and backup sources.
    """
    
    def __init__(
        self,
        primary: Callable[[str], T],
        backup: BackupProvider[T],
        cache_on_success: bool = True,
    ):
        """
        Initialize fallback provider.
        
        Args:
            primary: Primary data source
            backup: Backup data provider
            cache_on_success: Cache primary results to backup
        """
        self.primary = primary
        self.backup = backup
        self.cache_on_success = cache_on_success
    
    async def get(self, key: str) -> T:
        """
        Get data from primary or backup.
        
        Args:
            key: Data key
            
        Returns:
            Data from primary or backup
        """
        try:
            if asyncio.iscoroutinefunction(self.primary):
                result = await self.primary(key)
            else:
                result = self.primary(key)
            
            if self.cache_on_success:
                await self.backup.set(key, result)
            
            return result
            
        except Exception as e:
            logger.warning(f"Primary failed, using backup: {e}")
            
            backup_result = await self.backup.get(key)
            if backup_result is not None:
                return backup_result
            
            raise


__all__ = [
    # Exceptions
    "FallbackError",
    "DegradedModeError",
    # Enums
    "FallbackReason",
    "OperationMode",
    # Data classes
    "FallbackResult",
    "FallbackHandler",
    # Main classes
    "FallbackChain",
    "DegradedModeManager",
    # Backup providers
    "BackupProvider",
    "InMemoryBackupProvider",
    "FileBackupProvider",
    "FallbackProvider",
    # Decorators
    "with_fallback",
    "with_degraded_mode",
    "require_feature",
    # Utility functions
    "get_degraded_manager",
]
