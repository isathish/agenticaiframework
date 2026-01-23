"""
Enterprise Command Bus Module.

Provides command bus patterns, command handlers, dispatching,
and middleware support for CQRS architectures.

Example:
    # Create command bus
    bus = create_command_bus()
    
    # Register handler
    @bus.handler(CreateOrderCommand)
    async def handle_create_order(command):
        return Order(id=command.order_id)
    
    # Dispatch command
    result = await bus.dispatch(CreateOrderCommand(order_id="123"))
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from functools import wraps
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Type,
    TypeVar,
    Union,
)

logger = logging.getLogger(__name__)

T = TypeVar('T')
C = TypeVar('C', bound='Command')
R = TypeVar('R')


class CommandBusError(Exception):
    """Command bus error."""
    pass


class HandlerNotFoundError(CommandBusError):
    """Handler not found."""
    pass


class CommandValidationError(CommandBusError):
    """Command validation failed."""
    pass


class CommandExecutionError(CommandBusError):
    """Command execution failed."""
    pass


class CommandState(str, Enum):
    """Command state."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class CommandMetadata:
    """Command metadata."""
    command_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    user_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Command:
    """Base command class."""
    _metadata: CommandMetadata = field(default_factory=CommandMetadata)
    
    @property
    def command_type(self) -> str:
        return self.__class__.__name__
    
    @property
    def command_id(self) -> str:
        return self._metadata.command_id
    
    def validate(self) -> List[str]:
        """Validate command. Returns list of errors."""
        return []


@dataclass
class CommandResult(Generic[R]):
    """Command execution result."""
    command_id: str
    command_type: str
    success: bool
    result: Optional[R] = None
    error: Optional[str] = None
    state: CommandState = CommandState.COMPLETED
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CommandContext:
    """Command execution context."""
    command: Command
    metadata: CommandMetadata
    started_at: datetime = field(default_factory=datetime.now)
    retries: int = 0
    extra: Dict[str, Any] = field(default_factory=dict)


# Handler type
CommandHandler = Callable[[C], Awaitable[R]]


class CommandMiddleware(ABC):
    """Abstract command middleware."""
    
    @abstractmethod
    async def execute(
        self,
        context: CommandContext,
        next_handler: Callable[[CommandContext], Awaitable[Any]],
    ) -> Any:
        """Execute middleware."""
        pass


class LoggingMiddleware(CommandMiddleware):
    """Logging middleware."""
    
    async def execute(
        self,
        context: CommandContext,
        next_handler: Callable[[CommandContext], Awaitable[Any]],
    ) -> Any:
        logger.info(
            f"Executing command: {context.command.command_type} "
            f"(id={context.command.command_id})"
        )
        
        try:
            result = await next_handler(context)
            
            logger.info(
                f"Command completed: {context.command.command_type}"
            )
            
            return result
        
        except Exception as e:
            logger.error(
                f"Command failed: {context.command.command_type} - {e}"
            )
            raise


class ValidationMiddleware(CommandMiddleware):
    """Validation middleware."""
    
    async def execute(
        self,
        context: CommandContext,
        next_handler: Callable[[CommandContext], Awaitable[Any]],
    ) -> Any:
        errors = context.command.validate()
        
        if errors:
            raise CommandValidationError(
                f"Validation failed: {', '.join(errors)}"
            )
        
        return await next_handler(context)


class RetryMiddleware(CommandMiddleware):
    """Retry middleware."""
    
    def __init__(
        self,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        exponential: bool = True,
    ):
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._exponential = exponential
    
    async def execute(
        self,
        context: CommandContext,
        next_handler: Callable[[CommandContext], Awaitable[Any]],
    ) -> Any:
        last_error = None
        
        for attempt in range(self._max_retries + 1):
            try:
                context.retries = attempt
                return await next_handler(context)
            
            except Exception as e:
                last_error = e
                
                if attempt < self._max_retries:
                    delay = self._retry_delay
                    
                    if self._exponential:
                        delay = self._retry_delay * (2 ** attempt)
                    
                    logger.warning(
                        f"Retry {attempt + 1}/{self._max_retries} "
                        f"for {context.command.command_type}"
                    )
                    
                    await asyncio.sleep(delay)
        
        raise last_error


class TimingMiddleware(CommandMiddleware):
    """Timing middleware."""
    
    async def execute(
        self,
        context: CommandContext,
        next_handler: Callable[[CommandContext], Awaitable[Any]],
    ) -> Any:
        start = datetime.now()
        
        try:
            return await next_handler(context)
        
        finally:
            duration = (datetime.now() - start).total_seconds() * 1000
            context.extra["duration_ms"] = duration


class TransactionMiddleware(CommandMiddleware):
    """Transaction middleware (simulated)."""
    
    def __init__(
        self,
        on_commit: Optional[Callable[[], Awaitable[None]]] = None,
        on_rollback: Optional[Callable[[Exception], Awaitable[None]]] = None,
    ):
        self._on_commit = on_commit
        self._on_rollback = on_rollback
    
    async def execute(
        self,
        context: CommandContext,
        next_handler: Callable[[CommandContext], Awaitable[Any]],
    ) -> Any:
        try:
            result = await next_handler(context)
            
            if self._on_commit:
                await self._on_commit()
            
            return result
        
        except Exception as e:
            if self._on_rollback:
                await self._on_rollback(e)
            
            raise


class HandlerRegistry:
    """
    Registry for command handlers.
    """
    
    def __init__(self):
        self._handlers: Dict[str, CommandHandler] = {}
        self._lock = asyncio.Lock()
    
    def register(
        self,
        command_type: Type[C],
        handler: CommandHandler[C, R],
    ) -> None:
        """Register a handler."""
        type_name = command_type.__name__
        self._handlers[type_name] = handler
        logger.debug(f"Registered handler for {type_name}")
    
    def get(
        self,
        command_type: str,
    ) -> Optional[CommandHandler]:
        """Get handler for command type."""
        return self._handlers.get(command_type)
    
    def has(self, command_type: str) -> bool:
        """Check if handler exists."""
        return command_type in self._handlers
    
    def list_handlers(self) -> List[str]:
        """List registered handlers."""
        return list(self._handlers.keys())


class CommandBus:
    """
    Command bus for dispatching commands.
    """
    
    def __init__(
        self,
        registry: Optional[HandlerRegistry] = None,
        middleware: Optional[List[CommandMiddleware]] = None,
    ):
        self._registry = registry or HandlerRegistry()
        self._middleware = middleware or []
        self._listeners: List[Callable[[CommandResult], Awaitable[None]]] = []
    
    def handler(
        self,
        command_type: Type[C],
    ) -> Callable[[CommandHandler[C, R]], CommandHandler[C, R]]:
        """Decorator to register a handler."""
        def decorator(func: CommandHandler[C, R]) -> CommandHandler[C, R]:
            self._registry.register(command_type, func)
            return func
        
        return decorator
    
    def register(
        self,
        command_type: Type[C],
        handler: CommandHandler[C, R],
    ) -> None:
        """Register a handler."""
        self._registry.register(command_type, handler)
    
    def add_middleware(
        self,
        middleware: CommandMiddleware,
    ) -> "CommandBus":
        """Add middleware."""
        self._middleware.append(middleware)
        return self
    
    def on_result(
        self,
        listener: Callable[[CommandResult], Awaitable[None]],
    ) -> None:
        """Register result listener."""
        self._listeners.append(listener)
    
    async def dispatch(
        self,
        command: C,
    ) -> CommandResult[R]:
        """Dispatch a command."""
        command_type = command.command_type
        
        handler = self._registry.get(command_type)
        
        if not handler:
            raise HandlerNotFoundError(
                f"No handler for command: {command_type}"
            )
        
        context = CommandContext(
            command=command,
            metadata=command._metadata,
        )
        
        # Build middleware chain
        async def execute_handler(ctx: CommandContext) -> Any:
            return await handler(ctx.command)
        
        chain = execute_handler
        
        for middleware in reversed(self._middleware):
            chain = self._wrap_middleware(middleware, chain)
        
        # Execute
        try:
            result_value = await chain(context)
            
            result = CommandResult[R](
                command_id=command.command_id,
                command_type=command_type,
                success=True,
                result=result_value,
                state=CommandState.COMPLETED,
                started_at=context.started_at,
                completed_at=datetime.now(),
                metadata=context.extra,
            )
        
        except Exception as e:
            result = CommandResult[R](
                command_id=command.command_id,
                command_type=command_type,
                success=False,
                error=str(e),
                state=CommandState.FAILED,
                started_at=context.started_at,
                completed_at=datetime.now(),
            )
        
        # Notify listeners
        for listener in self._listeners:
            try:
                await listener(result)
            except Exception as e:
                logger.error(f"Listener error: {e}")
        
        if not result.success:
            raise CommandExecutionError(result.error)
        
        return result
    
    def _wrap_middleware(
        self,
        middleware: CommandMiddleware,
        next_handler: Callable[[CommandContext], Awaitable[Any]],
    ) -> Callable[[CommandContext], Awaitable[Any]]:
        """Wrap middleware around handler."""
        async def wrapper(context: CommandContext) -> Any:
            return await middleware.execute(context, next_handler)
        
        return wrapper
    
    async def dispatch_many(
        self,
        commands: List[Command],
        parallel: bool = False,
    ) -> List[CommandResult]:
        """Dispatch multiple commands."""
        if parallel:
            tasks = [self.dispatch(cmd) for cmd in commands]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            return [
                r if isinstance(r, CommandResult) else CommandResult(
                    command_id=str(i),
                    command_type="unknown",
                    success=False,
                    error=str(r),
                    state=CommandState.FAILED,
                )
                for i, r in enumerate(results)
            ]
        else:
            results = []
            for cmd in commands:
                try:
                    result = await self.dispatch(cmd)
                    results.append(result)
                except Exception as e:
                    results.append(CommandResult(
                        command_id=cmd.command_id,
                        command_type=cmd.command_type,
                        success=False,
                        error=str(e),
                        state=CommandState.FAILED,
                    ))
            
            return results


class AsyncCommandBus:
    """
    Async command bus with queuing.
    """
    
    def __init__(
        self,
        command_bus: CommandBus,
        max_workers: int = 4,
    ):
        self._bus = command_bus
        self._queue: asyncio.Queue = asyncio.Queue()
        self._max_workers = max_workers
        self._workers: List[asyncio.Task] = []
        self._running = False
        self._results: Dict[str, CommandResult] = {}
    
    async def start(self) -> None:
        """Start workers."""
        if self._running:
            return
        
        self._running = True
        
        for i in range(self._max_workers):
            task = asyncio.create_task(self._worker(i))
            self._workers.append(task)
    
    async def stop(self) -> None:
        """Stop workers."""
        self._running = False
        
        for worker in self._workers:
            worker.cancel()
        
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
    
    async def _worker(self, worker_id: int) -> None:
        """Worker loop."""
        while self._running:
            try:
                command = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=1.0,
                )
                
                try:
                    result = await self._bus.dispatch(command)
                    self._results[command.command_id] = result
                except Exception as e:
                    self._results[command.command_id] = CommandResult(
                        command_id=command.command_id,
                        command_type=command.command_type,
                        success=False,
                        error=str(e),
                        state=CommandState.FAILED,
                    )
                
                self._queue.task_done()
            
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
    
    async def enqueue(self, command: Command) -> str:
        """Enqueue a command."""
        await self._queue.put(command)
        return command.command_id
    
    async def get_result(
        self,
        command_id: str,
        timeout: float = 30.0,
    ) -> Optional[CommandResult]:
        """Get result for command."""
        start = datetime.now()
        
        while (datetime.now() - start).total_seconds() < timeout:
            if command_id in self._results:
                return self._results.pop(command_id)
            
            await asyncio.sleep(0.1)
        
        return None


class CommandDispatcher:
    """
    Simple command dispatcher without middleware.
    """
    
    def __init__(self):
        self._handlers: Dict[str, CommandHandler] = {}
    
    def register(
        self,
        command_type: Type[C],
        handler: CommandHandler[C, R],
    ) -> None:
        """Register handler."""
        self._handlers[command_type.__name__] = handler
    
    async def dispatch(self, command: C) -> R:
        """Dispatch command."""
        handler = self._handlers.get(command.command_type)
        
        if not handler:
            raise HandlerNotFoundError(
                f"No handler for: {command.command_type}"
            )
        
        return await handler(command)


# Decorators
def command_handler(
    command_type: Type[C],
    bus: Optional[CommandBus] = None,
) -> Callable:
    """
    Decorator to register command handler.
    
    Example:
        @command_handler(CreateOrderCommand)
        async def handle_create_order(command):
            ...
    """
    def decorator(func: Callable) -> Callable:
        if bus:
            bus.register(command_type, func)
        
        func._command_type = command_type
        return func
    
    return decorator


def validates(
    *validators: Callable[[C], Optional[str]],
) -> Callable:
    """
    Decorator to add validators to command handler.
    
    Example:
        @validates(
            lambda cmd: "ID required" if not cmd.id else None,
        )
        async def handle_command(command):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(command: C, *args, **kwargs) -> Any:
            errors = []
            
            for validator in validators:
                error = validator(command)
                if error:
                    errors.append(error)
            
            if errors:
                raise CommandValidationError(
                    f"Validation failed: {', '.join(errors)}"
                )
            
            return await func(command, *args, **kwargs)
        
        return wrapper
    
    return decorator


def with_retry(
    max_retries: int = 3,
    delay: float = 1.0,
) -> Callable:
    """
    Decorator to add retry logic.
    
    Example:
        @with_retry(max_retries=3)
        async def handle_command(command):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_error = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    
                    if attempt < max_retries:
                        await asyncio.sleep(delay * (2 ** attempt))
            
            raise last_error
        
        return wrapper
    
    return decorator


# Factory functions
def create_command_bus(
    with_logging: bool = True,
    with_validation: bool = True,
    with_timing: bool = True,
) -> CommandBus:
    """Create a command bus with common middleware."""
    bus = CommandBus()
    
    if with_timing:
        bus.add_middleware(TimingMiddleware())
    
    if with_logging:
        bus.add_middleware(LoggingMiddleware())
    
    if with_validation:
        bus.add_middleware(ValidationMiddleware())
    
    return bus


def create_async_command_bus(
    max_workers: int = 4,
) -> AsyncCommandBus:
    """Create an async command bus."""
    return AsyncCommandBus(
        create_command_bus(),
        max_workers=max_workers,
    )


def create_command_dispatcher() -> CommandDispatcher:
    """Create a simple command dispatcher."""
    return CommandDispatcher()


def create_retry_middleware(
    max_retries: int = 3,
    delay: float = 1.0,
) -> RetryMiddleware:
    """Create retry middleware."""
    return RetryMiddleware(max_retries, delay)


__all__ = [
    # Exceptions
    "CommandBusError",
    "HandlerNotFoundError",
    "CommandValidationError",
    "CommandExecutionError",
    # Enums
    "CommandState",
    # Data classes
    "CommandMetadata",
    "Command",
    "CommandResult",
    "CommandContext",
    # Abstract classes
    "CommandMiddleware",
    # Middleware implementations
    "LoggingMiddleware",
    "ValidationMiddleware",
    "RetryMiddleware",
    "TimingMiddleware",
    "TransactionMiddleware",
    # Core classes
    "HandlerRegistry",
    "CommandBus",
    "AsyncCommandBus",
    "CommandDispatcher",
    # Decorators
    "command_handler",
    "validates",
    "with_retry",
    # Factory functions
    "create_command_bus",
    "create_async_command_bus",
    "create_command_dispatcher",
    "create_retry_middleware",
]
