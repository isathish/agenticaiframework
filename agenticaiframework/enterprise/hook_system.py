"""
Enterprise Hook System Module.

Provides hook system, pre/post hooks, aspect-oriented programming,
interceptors, and advice patterns.

Example:
    # Create hook manager
    hooks = create_hook_manager()
    
    # Register hooks
    hooks.before("save", validate_data)
    hooks.after("save", log_result)
    
    # Use decorator
    @hookable("process")
    async def process_data(data):
        return transform(data)
    
    # Register interceptor
    @intercept("process")
    async def log_interceptor(ctx, next):
        print(f"Before: {ctx.args}")
        result = await next()
        print(f"After: {result}")
        return result
"""

from __future__ import annotations

import asyncio
import functools
import inspect
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    Tuple,
    TypeVar,
    Union,
)

T = TypeVar('T')
R = TypeVar('R')


logger = logging.getLogger(__name__)


class HookError(Exception):
    """Base hook error."""
    pass


class HookPhase(str, Enum):
    """Hook execution phase."""
    BEFORE = "before"
    AFTER = "after"
    AROUND = "around"
    ON_ERROR = "on_error"
    ON_SUCCESS = "on_success"


class AdviceType(str, Enum):
    """Aspect-oriented advice type."""
    BEFORE = "before"
    AFTER = "after"
    AROUND = "around"
    AFTER_RETURNING = "after_returning"
    AFTER_THROWING = "after_throwing"


@dataclass
class HookContext:
    """Context passed to hooks."""
    name: str
    phase: HookPhase
    args: Tuple[Any, ...]
    kwargs: Dict[str, Any]
    result: Any = None
    error: Optional[Exception] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    @property
    def elapsed_ms(self) -> Optional[float]:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds() * 1000
        return None


@dataclass
class HookConfig:
    """Hook configuration."""
    priority: int = 100
    enabled: bool = True
    async_mode: bool = True
    stop_on_error: bool = False
    timeout: Optional[float] = None


@dataclass
class HookInfo:
    """Hook registration info."""
    name: str
    phase: HookPhase
    handler: Callable
    config: HookConfig
    registered_at: datetime = field(default_factory=datetime.utcnow)


# Type aliases
HookHandler = Callable[[HookContext], Awaitable[Any]]
InterceptorHandler = Callable[[HookContext, Callable], Awaitable[Any]]


class Hook(ABC):
    """Abstract hook."""
    
    @abstractmethod
    async def execute(self, ctx: HookContext) -> Any:
        """Execute the hook."""
        pass


class FunctionHook(Hook):
    """Hook wrapping a function."""
    
    def __init__(self, handler: Callable, config: Optional[HookConfig] = None):
        self._handler = handler
        self._config = config or HookConfig()
    
    async def execute(self, ctx: HookContext) -> Any:
        if asyncio.iscoroutinefunction(self._handler):
            return await self._handler(ctx)
        else:
            return self._handler(ctx)


class Interceptor(ABC):
    """
    Abstract interceptor for around advice.
    """
    
    @abstractmethod
    async def intercept(
        self,
        ctx: HookContext,
        next_fn: Callable[[], Awaitable[Any]],
    ) -> Any:
        """Intercept execution."""
        pass


class FunctionInterceptor(Interceptor):
    """Interceptor wrapping a function."""
    
    def __init__(self, handler: InterceptorHandler):
        self._handler = handler
    
    async def intercept(
        self,
        ctx: HookContext,
        next_fn: Callable[[], Awaitable[Any]],
    ) -> Any:
        return await self._handler(ctx, next_fn)


class LoggingInterceptor(Interceptor):
    """Interceptor that logs execution."""
    
    def __init__(self, logger_name: Optional[str] = None):
        self._logger = logging.getLogger(logger_name or __name__)
    
    async def intercept(
        self,
        ctx: HookContext,
        next_fn: Callable[[], Awaitable[Any]],
    ) -> Any:
        self._logger.info(f"Entering: {ctx.name}")
        try:
            result = await next_fn()
            self._logger.info(f"Exiting: {ctx.name} (success)")
            return result
        except Exception as e:
            self._logger.error(f"Exiting: {ctx.name} (error: {e})")
            raise


class TimingInterceptor(Interceptor):
    """Interceptor that tracks timing."""
    
    async def intercept(
        self,
        ctx: HookContext,
        next_fn: Callable[[], Awaitable[Any]],
    ) -> Any:
        ctx.start_time = datetime.utcnow()
        try:
            result = await next_fn()
            return result
        finally:
            ctx.end_time = datetime.utcnow()
            logger.debug(f"{ctx.name} took {ctx.elapsed_ms:.2f}ms")


class HookChain:
    """
    Chain of hooks for a specific point.
    """
    
    def __init__(self, name: str):
        self._name = name
        self._before: List[HookInfo] = []
        self._after: List[HookInfo] = []
        self._around: List[Interceptor] = []
        self._on_error: List[HookInfo] = []
        self._on_success: List[HookInfo] = []
    
    @property
    def name(self) -> str:
        return self._name
    
    def add_before(self, handler: Callable, config: Optional[HookConfig] = None) -> None:
        """Add before hook."""
        cfg = config or HookConfig()
        self._before.append(HookInfo(
            name=self._name,
            phase=HookPhase.BEFORE,
            handler=handler,
            config=cfg,
        ))
        self._before.sort(key=lambda h: h.config.priority)
    
    def add_after(self, handler: Callable, config: Optional[HookConfig] = None) -> None:
        """Add after hook."""
        cfg = config or HookConfig()
        self._after.append(HookInfo(
            name=self._name,
            phase=HookPhase.AFTER,
            handler=handler,
            config=cfg,
        ))
        self._after.sort(key=lambda h: h.config.priority)
    
    def add_around(self, interceptor: Interceptor) -> None:
        """Add around interceptor."""
        self._around.append(interceptor)
    
    def add_on_error(self, handler: Callable, config: Optional[HookConfig] = None) -> None:
        """Add error hook."""
        cfg = config or HookConfig()
        self._on_error.append(HookInfo(
            name=self._name,
            phase=HookPhase.ON_ERROR,
            handler=handler,
            config=cfg,
        ))
    
    def add_on_success(self, handler: Callable, config: Optional[HookConfig] = None) -> None:
        """Add success hook."""
        cfg = config or HookConfig()
        self._on_success.append(HookInfo(
            name=self._name,
            phase=HookPhase.ON_SUCCESS,
            handler=handler,
            config=cfg,
        ))
    
    async def execute(
        self,
        func: Callable,
        args: Tuple[Any, ...],
        kwargs: Dict[str, Any],
    ) -> Any:
        """Execute function with hooks."""
        ctx = HookContext(
            name=self._name,
            phase=HookPhase.BEFORE,
            args=args,
            kwargs=kwargs,
        )
        
        # Execute before hooks
        for hook_info in self._before:
            if hook_info.config.enabled:
                await self._execute_handler(hook_info.handler, ctx)
        
        # Build interceptor chain
        async def execute_core() -> Any:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)
        
        next_fn = execute_core
        for interceptor in reversed(self._around):
            current_interceptor = interceptor
            current_next = next_fn
            
            async def make_next(i=current_interceptor, n=current_next):
                return await i.intercept(ctx, n)
            
            next_fn = make_next
        
        try:
            ctx.phase = HookPhase.AROUND
            result = await next_fn()
            ctx.result = result
            
            # Execute success hooks
            ctx.phase = HookPhase.ON_SUCCESS
            for hook_info in self._on_success:
                if hook_info.config.enabled:
                    await self._execute_handler(hook_info.handler, ctx)
            
        except Exception as e:
            ctx.error = e
            
            # Execute error hooks
            ctx.phase = HookPhase.ON_ERROR
            for hook_info in self._on_error:
                if hook_info.config.enabled:
                    await self._execute_handler(hook_info.handler, ctx)
            
            raise
        
        finally:
            # Execute after hooks
            ctx.phase = HookPhase.AFTER
            for hook_info in self._after:
                if hook_info.config.enabled:
                    await self._execute_handler(hook_info.handler, ctx)
        
        return ctx.result
    
    async def _execute_handler(self, handler: Callable, ctx: HookContext) -> Any:
        """Execute a hook handler."""
        if asyncio.iscoroutinefunction(handler):
            return await handler(ctx)
        else:
            return handler(ctx)


class HookManager:
    """
    Manager for all hooks.
    """
    
    def __init__(self):
        self._chains: Dict[str, HookChain] = {}
        self._global_interceptors: List[Interceptor] = []
    
    def _get_or_create_chain(self, name: str) -> HookChain:
        """Get or create hook chain."""
        if name not in self._chains:
            chain = HookChain(name)
            # Add global interceptors
            for interceptor in self._global_interceptors:
                chain.add_around(interceptor)
            self._chains[name] = chain
        return self._chains[name]
    
    def before(
        self,
        name: str,
        handler: Callable,
        config: Optional[HookConfig] = None,
    ) -> None:
        """Register before hook."""
        chain = self._get_or_create_chain(name)
        chain.add_before(handler, config)
    
    def after(
        self,
        name: str,
        handler: Callable,
        config: Optional[HookConfig] = None,
    ) -> None:
        """Register after hook."""
        chain = self._get_or_create_chain(name)
        chain.add_after(handler, config)
    
    def around(self, name: str, interceptor: Interceptor) -> None:
        """Register around interceptor."""
        chain = self._get_or_create_chain(name)
        chain.add_around(interceptor)
    
    def on_error(
        self,
        name: str,
        handler: Callable,
        config: Optional[HookConfig] = None,
    ) -> None:
        """Register error hook."""
        chain = self._get_or_create_chain(name)
        chain.add_on_error(handler, config)
    
    def on_success(
        self,
        name: str,
        handler: Callable,
        config: Optional[HookConfig] = None,
    ) -> None:
        """Register success hook."""
        chain = self._get_or_create_chain(name)
        chain.add_on_success(handler, config)
    
    def add_global_interceptor(self, interceptor: Interceptor) -> None:
        """Add global interceptor to all chains."""
        self._global_interceptors.append(interceptor)
        for chain in self._chains.values():
            chain.add_around(interceptor)
    
    async def execute(
        self,
        name: str,
        func: Callable,
        args: Tuple[Any, ...] = (),
        kwargs: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Execute function with hooks."""
        chain = self._get_or_create_chain(name)
        return await chain.execute(func, args, kwargs or {})
    
    def wrap(self, name: str) -> Callable:
        """Create wrapper for a hook point."""
        def wrapper(func: Callable) -> Callable:
            @functools.wraps(func)
            async def wrapped(*args, **kwargs):
                return await self.execute(name, func, args, kwargs)
            return wrapped
        return wrapper
    
    def get_chain(self, name: str) -> Optional[HookChain]:
        """Get hook chain."""
        return self._chains.get(name)


class Aspect:
    """
    Aspect for aspect-oriented programming.
    """
    
    def __init__(self, name: str):
        self._name = name
        self._pointcuts: List[str] = []
        self._before: List[Callable] = []
        self._after: List[Callable] = []
        self._around: List[InterceptorHandler] = []
        self._after_returning: List[Callable] = []
        self._after_throwing: List[Callable] = []
    
    @property
    def name(self) -> str:
        return self._name
    
    def pointcut(self, pattern: str) -> "Aspect":
        """Add pointcut pattern."""
        self._pointcuts.append(pattern)
        return self
    
    def before_advice(self, handler: Callable) -> "Aspect":
        """Add before advice."""
        self._before.append(handler)
        return self
    
    def after_advice(self, handler: Callable) -> "Aspect":
        """Add after advice."""
        self._after.append(handler)
        return self
    
    def around_advice(self, handler: InterceptorHandler) -> "Aspect":
        """Add around advice."""
        self._around.append(handler)
        return self
    
    def after_returning_advice(self, handler: Callable) -> "Aspect":
        """Add after returning advice."""
        self._after_returning.append(handler)
        return self
    
    def after_throwing_advice(self, handler: Callable) -> "Aspect":
        """Add after throwing advice."""
        self._after_throwing.append(handler)
        return self
    
    def matches(self, name: str) -> bool:
        """Check if name matches any pointcut."""
        import fnmatch
        return any(fnmatch.fnmatch(name, p) for p in self._pointcuts)
    
    def apply_to(self, hooks: HookManager, name: str) -> None:
        """Apply aspect to hook manager."""
        if not self.matches(name):
            return
        
        for handler in self._before:
            hooks.before(name, handler)
        
        for handler in self._after:
            hooks.after(name, handler)
        
        for handler in self._around:
            hooks.around(name, FunctionInterceptor(handler))
        
        for handler in self._after_returning:
            hooks.on_success(name, handler)
        
        for handler in self._after_throwing:
            hooks.on_error(name, handler)


class AspectWeaver:
    """
    Weaves aspects into target objects.
    """
    
    def __init__(self, hooks: HookManager):
        self._hooks = hooks
        self._aspects: List[Aspect] = []
    
    def add_aspect(self, aspect: Aspect) -> None:
        """Add aspect."""
        self._aspects.append(aspect)
    
    def weave(self, target: Any, prefix: str = "") -> Any:
        """Weave aspects into target object."""
        for name in dir(target):
            if name.startswith('_'):
                continue
            
            attr = getattr(target, name)
            if not callable(attr):
                continue
            
            hook_name = f"{prefix}{name}" if prefix else name
            
            # Apply aspects
            for aspect in self._aspects:
                aspect.apply_to(self._hooks, hook_name)
            
            # Wrap method
            wrapped = self._hooks.wrap(hook_name)(attr)
            setattr(target, name, wrapped)
        
        return target


# Global registry
_global_hooks: Optional[HookManager] = None


# Decorators
def hookable(name: Optional[str] = None) -> Callable:
    """
    Decorator to make function hookable.
    
    Example:
        @hookable("process")
        async def process_data(data):
            return data
    """
    def decorator(func: Callable) -> Callable:
        hook_name = name or func.__name__
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            hooks = get_global_hooks()
            return await hooks.execute(hook_name, func, args, kwargs)
        
        wrapper._hook_name = hook_name
        return wrapper
    
    return decorator


def before(name: str, priority: int = 100) -> Callable:
    """
    Decorator to register before hook.
    
    Example:
        @before("save")
        async def validate(ctx):
            ...
    """
    def decorator(func: Callable) -> Callable:
        hooks = get_global_hooks()
        hooks.before(name, func, HookConfig(priority=priority))
        return func
    
    return decorator


def after(name: str, priority: int = 100) -> Callable:
    """
    Decorator to register after hook.
    
    Example:
        @after("save")
        async def log_result(ctx):
            ...
    """
    def decorator(func: Callable) -> Callable:
        hooks = get_global_hooks()
        hooks.after(name, func, HookConfig(priority=priority))
        return func
    
    return decorator


def intercept(name: str) -> Callable:
    """
    Decorator to register interceptor.
    
    Example:
        @intercept("process")
        async def log_interceptor(ctx, next):
            result = await next()
            return result
    """
    def decorator(func: InterceptorHandler) -> Callable:
        hooks = get_global_hooks()
        hooks.around(name, FunctionInterceptor(func))
        return func
    
    return decorator


def on_error(name: str) -> Callable:
    """
    Decorator to register error hook.
    
    Example:
        @on_error("save")
        async def handle_error(ctx):
            logger.error(ctx.error)
    """
    def decorator(func: Callable) -> Callable:
        hooks = get_global_hooks()
        hooks.on_error(name, func)
        return func
    
    return decorator


def on_success(name: str) -> Callable:
    """
    Decorator to register success hook.
    """
    def decorator(func: Callable) -> Callable:
        hooks = get_global_hooks()
        hooks.on_success(name, func)
        return func
    
    return decorator


# Factory functions
def create_hook_manager() -> HookManager:
    """Create a hook manager."""
    return HookManager()


def create_hook_config(
    priority: int = 100,
    enabled: bool = True,
    async_mode: bool = True,
    stop_on_error: bool = False,
    timeout: Optional[float] = None,
) -> HookConfig:
    """Create hook configuration."""
    return HookConfig(
        priority=priority,
        enabled=enabled,
        async_mode=async_mode,
        stop_on_error=stop_on_error,
        timeout=timeout,
    )


def create_aspect(name: str) -> Aspect:
    """Create an aspect."""
    return Aspect(name)


def create_aspect_weaver(hooks: Optional[HookManager] = None) -> AspectWeaver:
    """Create aspect weaver."""
    return AspectWeaver(hooks or get_global_hooks())


def create_logging_interceptor(logger_name: Optional[str] = None) -> LoggingInterceptor:
    """Create logging interceptor."""
    return LoggingInterceptor(logger_name)


def create_timing_interceptor() -> TimingInterceptor:
    """Create timing interceptor."""
    return TimingInterceptor()


def get_global_hooks() -> HookManager:
    """Get global hook manager."""
    global _global_hooks
    if _global_hooks is None:
        _global_hooks = create_hook_manager()
    return _global_hooks


__all__ = [
    # Exceptions
    "HookError",
    # Enums
    "HookPhase",
    "AdviceType",
    # Data classes
    "HookContext",
    "HookConfig",
    "HookInfo",
    # Hook
    "Hook",
    "FunctionHook",
    # Interceptor
    "Interceptor",
    "FunctionInterceptor",
    "LoggingInterceptor",
    "TimingInterceptor",
    # Chain
    "HookChain",
    # Manager
    "HookManager",
    # Aspect
    "Aspect",
    "AspectWeaver",
    # Decorators
    "hookable",
    "before",
    "after",
    "intercept",
    "on_error",
    "on_success",
    # Factory functions
    "create_hook_manager",
    "create_hook_config",
    "create_aspect",
    "create_aspect_weaver",
    "create_logging_interceptor",
    "create_timing_interceptor",
    "get_global_hooks",
]
