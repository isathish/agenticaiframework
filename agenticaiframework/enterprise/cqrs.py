"""
Enterprise CQRS Pattern Module.

Provides Command Query Responsibility Segregation pattern,
command/query handlers, and read/write model separation.

Example:
    # Define commands and queries
    @command_handler(CreateOrderCommand)
    async def handle_create_order(cmd: CreateOrderCommand):
        ...
    
    @query_handler(GetOrderQuery)
    async def handle_get_order(query: GetOrderQuery):
        ...
    
    # Use the bus
    bus = create_cqrs_bus()
    await bus.execute(CreateOrderCommand(customer_id="123"))
    order = await bus.query(GetOrderQuery(order_id="456"))
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from functools import wraps
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    Type,
    TypeVar,
    Union,
)

logger = logging.getLogger(__name__)

TCommand = TypeVar('TCommand', bound='Command')
TQuery = TypeVar('TQuery', bound='Query')
TResult = TypeVar('TResult')


class CQRSError(Exception):
    """CQRS error."""
    pass


class HandlerNotFoundError(CQRSError):
    """Handler not registered."""
    pass


class CommandError(CQRSError):
    """Command execution error."""
    pass


class QueryError(CQRSError):
    """Query execution error."""
    pass


class CommandStatus(str, Enum):
    """Command execution status."""
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"


# Base message classes
@dataclass
class Command:
    """Base command class."""
    command_id: str = field(default_factory=lambda: "")
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.command_id:
            import uuid
            self.command_id = str(uuid.uuid4())


@dataclass
class Query:
    """Base query class."""
    query_id: str = field(default_factory=lambda: "")
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.query_id:
            import uuid
            self.query_id = str(uuid.uuid4())


@dataclass
class CommandResult(Generic[TResult]):
    """Result of command execution."""
    success: bool
    data: Optional[TResult] = None
    error: Optional[str] = None
    command_id: str = ""
    executed_at: datetime = field(default_factory=datetime.now)


@dataclass
class QueryResult(Generic[TResult]):
    """Result of query execution."""
    success: bool
    data: Optional[TResult] = None
    error: Optional[str] = None
    query_id: str = ""
    executed_at: datetime = field(default_factory=datetime.now)
    cached: bool = False


# Handler types
CommandHandler = Callable[[TCommand], Any]
QueryHandler = Callable[[TQuery], Any]


class CommandHandlerBase(ABC, Generic[TCommand, TResult]):
    """Abstract command handler."""
    
    @abstractmethod
    async def handle(self, command: TCommand) -> TResult:
        """Handle command."""
        pass


class QueryHandlerBase(ABC, Generic[TQuery, TResult]):
    """Abstract query handler."""
    
    @abstractmethod
    async def handle(self, query: TQuery) -> TResult:
        """Handle query."""
        pass


# Handler registries
class CommandRegistry:
    """Registry for command handlers."""
    
    def __init__(self):
        self._handlers: Dict[Type[Command], CommandHandler] = {}
    
    def register(
        self,
        command_type: Type[Command],
        handler: CommandHandler,
    ) -> None:
        """Register a command handler."""
        self._handlers[command_type] = handler
        logger.debug(f"Registered handler for {command_type.__name__}")
    
    def get(
        self,
        command_type: Type[Command],
    ) -> Optional[CommandHandler]:
        """Get handler for command type."""
        return self._handlers.get(command_type)
    
    def has(self, command_type: Type[Command]) -> bool:
        """Check if handler exists."""
        return command_type in self._handlers


class QueryRegistry:
    """Registry for query handlers."""
    
    def __init__(self):
        self._handlers: Dict[Type[Query], QueryHandler] = {}
    
    def register(
        self,
        query_type: Type[Query],
        handler: QueryHandler,
    ) -> None:
        """Register a query handler."""
        self._handlers[query_type] = handler
        logger.debug(f"Registered handler for {query_type.__name__}")
    
    def get(
        self,
        query_type: Type[Query],
    ) -> Optional[QueryHandler]:
        """Get handler for query type."""
        return self._handlers.get(query_type)
    
    def has(self, query_type: Type[Query]) -> bool:
        """Check if handler exists."""
        return query_type in self._handlers


# Middleware
class CommandMiddleware(ABC):
    """Abstract command middleware."""
    
    @abstractmethod
    async def execute(
        self,
        command: Command,
        next_handler: Callable[[Command], Any],
    ) -> Any:
        """Execute middleware."""
        pass


class QueryMiddleware(ABC):
    """Abstract query middleware."""
    
    @abstractmethod
    async def execute(
        self,
        query: Query,
        next_handler: Callable[[Query], Any],
    ) -> Any:
        """Execute middleware."""
        pass


class LoggingCommandMiddleware(CommandMiddleware):
    """Logging middleware for commands."""
    
    async def execute(
        self,
        command: Command,
        next_handler: Callable[[Command], Any],
    ) -> Any:
        command_type = type(command).__name__
        logger.info(f"Executing command: {command_type}")
        
        start = datetime.now()
        
        try:
            result = await next_handler(command)
            duration = (datetime.now() - start).total_seconds() * 1000
            logger.info(f"Command {command_type} completed in {duration:.2f}ms")
            return result
        
        except Exception as e:
            duration = (datetime.now() - start).total_seconds() * 1000
            logger.error(f"Command {command_type} failed in {duration:.2f}ms: {e}")
            raise


class ValidationCommandMiddleware(CommandMiddleware):
    """Validation middleware for commands."""
    
    def __init__(
        self,
        validators: Optional[Dict[Type[Command], Callable[[Command], None]]] = None,
    ):
        self._validators = validators or {}
    
    def add_validator(
        self,
        command_type: Type[Command],
        validator: Callable[[Command], None],
    ) -> None:
        """Add a validator."""
        self._validators[command_type] = validator
    
    async def execute(
        self,
        command: Command,
        next_handler: Callable[[Command], Any],
    ) -> Any:
        validator = self._validators.get(type(command))
        
        if validator:
            if asyncio.iscoroutinefunction(validator):
                await validator(command)
            else:
                validator(command)
        
        return await next_handler(command)


class CachingQueryMiddleware(QueryMiddleware):
    """Caching middleware for queries."""
    
    def __init__(
        self,
        ttl_seconds: int = 60,
    ):
        self._cache: Dict[str, Any] = {}
        self._timestamps: Dict[str, datetime] = {}
        self._ttl = ttl_seconds
    
    def _cache_key(self, query: Query) -> str:
        """Generate cache key from query."""
        import hashlib
        import json
        
        data = {
            "type": type(query).__name__,
            "data": {
                k: v for k, v in query.__dict__.items()
                if not k.startswith("_") and k not in ("query_id", "timestamp", "metadata")
            },
        }
        
        return hashlib.md5(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()
    
    async def execute(
        self,
        query: Query,
        next_handler: Callable[[Query], Any],
    ) -> Any:
        key = self._cache_key(query)
        
        # Check cache
        if key in self._cache:
            timestamp = self._timestamps.get(key)
            if timestamp:
                age = (datetime.now() - timestamp).total_seconds()
                if age < self._ttl:
                    logger.debug(f"Cache hit for {type(query).__name__}")
                    return self._cache[key]
        
        # Execute query
        result = await next_handler(query)
        
        # Cache result
        self._cache[key] = result
        self._timestamps[key] = datetime.now()
        
        return result
    
    def invalidate(self, query_type: Optional[Type[Query]] = None) -> None:
        """Invalidate cache."""
        if query_type:
            prefix = query_type.__name__
            keys_to_remove = [
                k for k in self._cache
                if k.startswith(prefix)
            ]
            for key in keys_to_remove:
                del self._cache[key]
                self._timestamps.pop(key, None)
        else:
            self._cache.clear()
            self._timestamps.clear()


# Buses
class CommandBus:
    """
    Command bus for dispatching commands.
    """
    
    def __init__(
        self,
        registry: Optional[CommandRegistry] = None,
    ):
        self._registry = registry or CommandRegistry()
        self._middleware: List[CommandMiddleware] = []
    
    def register(
        self,
        command_type: Type[Command],
        handler: CommandHandler,
    ) -> None:
        """Register a command handler."""
        self._registry.register(command_type, handler)
    
    def use(self, middleware: CommandMiddleware) -> 'CommandBus':
        """Add middleware."""
        self._middleware.append(middleware)
        return self
    
    async def execute(
        self,
        command: Command,
    ) -> CommandResult:
        """Execute a command."""
        command_type = type(command)
        handler = self._registry.get(command_type)
        
        if not handler:
            raise HandlerNotFoundError(
                f"No handler for command: {command_type.__name__}"
            )
        
        # Build middleware chain
        async def final_handler(cmd: Command) -> Any:
            if asyncio.iscoroutinefunction(handler):
                return await handler(cmd)
            return handler(cmd)
        
        chain = final_handler
        
        for middleware in reversed(self._middleware):
            chain = self._wrap_middleware(middleware, chain)
        
        try:
            result = await chain(command)
            
            return CommandResult(
                success=True,
                data=result,
                command_id=command.command_id,
            )
        
        except Exception as e:
            return CommandResult(
                success=False,
                error=str(e),
                command_id=command.command_id,
            )
    
    def _wrap_middleware(
        self,
        middleware: CommandMiddleware,
        next_handler: Callable[[Command], Any],
    ) -> Callable[[Command], Any]:
        """Wrap handler with middleware."""
        async def wrapped(cmd: Command) -> Any:
            return await middleware.execute(cmd, next_handler)
        return wrapped


class QueryBus:
    """
    Query bus for dispatching queries.
    """
    
    def __init__(
        self,
        registry: Optional[QueryRegistry] = None,
    ):
        self._registry = registry or QueryRegistry()
        self._middleware: List[QueryMiddleware] = []
    
    def register(
        self,
        query_type: Type[Query],
        handler: QueryHandler,
    ) -> None:
        """Register a query handler."""
        self._registry.register(query_type, handler)
    
    def use(self, middleware: QueryMiddleware) -> 'QueryBus':
        """Add middleware."""
        self._middleware.append(middleware)
        return self
    
    async def query(
        self,
        query: Query,
    ) -> QueryResult:
        """Execute a query."""
        query_type = type(query)
        handler = self._registry.get(query_type)
        
        if not handler:
            raise HandlerNotFoundError(
                f"No handler for query: {query_type.__name__}"
            )
        
        # Build middleware chain
        async def final_handler(q: Query) -> Any:
            if asyncio.iscoroutinefunction(handler):
                return await handler(q)
            return handler(q)
        
        chain = final_handler
        
        for middleware in reversed(self._middleware):
            chain = self._wrap_middleware(middleware, chain)
        
        try:
            result = await chain(query)
            
            return QueryResult(
                success=True,
                data=result,
                query_id=query.query_id,
            )
        
        except Exception as e:
            return QueryResult(
                success=False,
                error=str(e),
                query_id=query.query_id,
            )
    
    def _wrap_middleware(
        self,
        middleware: QueryMiddleware,
        next_handler: Callable[[Query], Any],
    ) -> Callable[[Query], Any]:
        """Wrap handler with middleware."""
        async def wrapped(q: Query) -> Any:
            return await middleware.execute(q, next_handler)
        return wrapped


class CQRSBus:
    """
    Combined CQRS bus for commands and queries.
    """
    
    def __init__(
        self,
        command_bus: Optional[CommandBus] = None,
        query_bus: Optional[QueryBus] = None,
    ):
        self._command_bus = command_bus or CommandBus()
        self._query_bus = query_bus or QueryBus()
    
    @property
    def commands(self) -> CommandBus:
        """Get command bus."""
        return self._command_bus
    
    @property
    def queries(self) -> QueryBus:
        """Get query bus."""
        return self._query_bus
    
    async def execute(self, command: Command) -> CommandResult:
        """Execute a command."""
        return await self._command_bus.execute(command)
    
    async def query(self, query: Query) -> QueryResult:
        """Execute a query."""
        return await self._query_bus.query(query)


# Read/Write Models
class WriteModel(ABC):
    """Abstract write model (aggregate)."""
    
    @abstractmethod
    def apply_command(self, command: Command) -> List[Any]:
        """Apply command and return events."""
        pass


class ReadModel(ABC):
    """Abstract read model (projection)."""
    
    @abstractmethod
    def apply_event(self, event: Any) -> None:
        """Apply event to update state."""
        pass


class ReadModelStore(ABC):
    """Abstract read model store."""
    
    @abstractmethod
    async def save(self, key: str, model: ReadModel) -> None:
        """Save read model."""
        pass
    
    @abstractmethod
    async def get(self, key: str) -> Optional[ReadModel]:
        """Get read model."""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete read model."""
        pass


class InMemoryReadModelStore(ReadModelStore):
    """In-memory read model store."""
    
    def __init__(self):
        self._store: Dict[str, ReadModel] = {}
    
    async def save(self, key: str, model: ReadModel) -> None:
        self._store[key] = model
    
    async def get(self, key: str) -> Optional[ReadModel]:
        return self._store.get(key)
    
    async def delete(self, key: str) -> bool:
        return self._store.pop(key, None) is not None


# Global registries
_command_registry = CommandRegistry()
_query_registry = QueryRegistry()


# Decorators
def command_handler(
    command_type: Type[Command],
) -> Callable:
    """
    Decorator to register a command handler.
    
    Example:
        @command_handler(CreateOrderCommand)
        async def handle_create_order(cmd: CreateOrderCommand):
            ...
    """
    def decorator(func: CommandHandler) -> CommandHandler:
        _command_registry.register(command_type, func)
        return func
    
    return decorator


def query_handler(
    query_type: Type[Query],
) -> Callable:
    """
    Decorator to register a query handler.
    
    Example:
        @query_handler(GetOrderQuery)
        async def handle_get_order(query: GetOrderQuery):
            ...
    """
    def decorator(func: QueryHandler) -> QueryHandler:
        _query_registry.register(query_type, func)
        return func
    
    return decorator


def validate_command(
    validator: Callable[[Command], None],
) -> Callable:
    """
    Decorator to add validation to command handler.
    
    Example:
        @validate_command(validate_create_order)
        @command_handler(CreateOrderCommand)
        async def handle_create_order(cmd):
            ...
    """
    def decorator(func: CommandHandler) -> CommandHandler:
        @wraps(func)
        async def wrapper(command: Command) -> Any:
            if asyncio.iscoroutinefunction(validator):
                await validator(command)
            else:
                validator(command)
            
            if asyncio.iscoroutinefunction(func):
                return await func(command)
            return func(command)
        
        return wrapper
    
    return decorator


# Factory functions
def create_command_bus() -> CommandBus:
    """Create a command bus with global registry."""
    return CommandBus(_command_registry)


def create_query_bus() -> QueryBus:
    """Create a query bus with global registry."""
    return QueryBus(_query_registry)


def create_cqrs_bus() -> CQRSBus:
    """Create a CQRS bus with global registries."""
    return CQRSBus(
        CommandBus(_command_registry),
        QueryBus(_query_registry),
    )


def create_logging_middleware() -> LoggingCommandMiddleware:
    """Create logging middleware."""
    return LoggingCommandMiddleware()


def create_validation_middleware() -> ValidationCommandMiddleware:
    """Create validation middleware."""
    return ValidationCommandMiddleware()


def create_caching_middleware(
    ttl_seconds: int = 60,
) -> CachingQueryMiddleware:
    """Create caching middleware."""
    return CachingQueryMiddleware(ttl_seconds)


__all__ = [
    # Exceptions
    "CQRSError",
    "HandlerNotFoundError",
    "CommandError",
    "QueryError",
    # Enums
    "CommandStatus",
    # Base classes
    "Command",
    "Query",
    "CommandResult",
    "QueryResult",
    # Handler bases
    "CommandHandlerBase",
    "QueryHandlerBase",
    # Registries
    "CommandRegistry",
    "QueryRegistry",
    # Middleware
    "CommandMiddleware",
    "QueryMiddleware",
    "LoggingCommandMiddleware",
    "ValidationCommandMiddleware",
    "CachingQueryMiddleware",
    # Buses
    "CommandBus",
    "QueryBus",
    "CQRSBus",
    # Models
    "WriteModel",
    "ReadModel",
    "ReadModelStore",
    "InMemoryReadModelStore",
    # Decorators
    "command_handler",
    "query_handler",
    "validate_command",
    # Factory functions
    "create_command_bus",
    "create_query_bus",
    "create_cqrs_bus",
    "create_logging_middleware",
    "create_validation_middleware",
    "create_caching_middleware",
]
