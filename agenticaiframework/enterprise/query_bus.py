"""
Enterprise Query Bus Module.

Provides query bus patterns, query handlers, read models,
and caching support for CQRS architectures.

Example:
    # Create query bus
    bus = create_query_bus()
    
    # Register handler
    @bus.handler(GetOrderQuery)
    async def handle_get_order(query):
        return {"order_id": query.order_id, "status": "pending"}
    
    # Execute query
    result = await bus.query(GetOrderQuery(order_id="123"))
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
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
Q = TypeVar('Q', bound='Query')
R = TypeVar('R')


class QueryBusError(Exception):
    """Query bus error."""
    pass


class HandlerNotFoundError(QueryBusError):
    """Handler not found."""
    pass


class QueryExecutionError(QueryBusError):
    """Query execution failed."""
    pass


class CacheError(QueryBusError):
    """Cache error."""
    pass


class QueryType(str, Enum):
    """Query type."""
    READ = "read"
    LIST = "list"
    AGGREGATE = "aggregate"
    SEARCH = "search"


@dataclass
class QueryMetadata:
    """Query metadata."""
    query_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: Optional[str] = None
    user_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    cache_key: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Query:
    """Base query class."""
    _metadata: QueryMetadata = field(default_factory=QueryMetadata)
    
    @property
    def query_type(self) -> str:
        return self.__class__.__name__
    
    @property
    def query_id(self) -> str:
        return self._metadata.query_id
    
    def cache_key(self) -> str:
        """Generate cache key."""
        data = {}
        for key, value in self.__dict__.items():
            if not key.startswith('_'):
                data[key] = value
        
        key_str = f"{self.query_type}:{json.dumps(data, sort_keys=True, default=str)}"
        return hashlib.sha256(key_str.encode()).hexdigest()[:32]


@dataclass
class QueryResult(Generic[R]):
    """Query result."""
    query_id: str
    query_type: str
    success: bool
    data: Optional[R] = None
    error: Optional[str] = None
    from_cache: bool = False
    executed_at: datetime = field(default_factory=datetime.now)
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QueryContext:
    """Query execution context."""
    query: Query
    metadata: QueryMetadata
    started_at: datetime = field(default_factory=datetime.now)
    use_cache: bool = True
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CacheEntry:
    """Cache entry."""
    key: str
    value: Any
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    hit_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at


# Handler type
QueryHandler = Callable[[Q], Awaitable[R]]


class QueryCache(ABC):
    """Abstract query cache."""
    
    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Get cached value."""
        pass
    
    @abstractmethod
    async def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: Optional[int] = None,
    ) -> None:
        """Set cached value."""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete cached value."""
        pass
    
    @abstractmethod
    async def clear(self) -> None:
        """Clear all cached values."""
        pass


class InMemoryQueryCache(QueryCache):
    """In-memory query cache."""
    
    def __init__(self, max_size: int = 1000):
        self._cache: Dict[str, CacheEntry] = {}
        self._max_size = max_size
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[Any]:
        entry = self._cache.get(key)
        
        if entry is None:
            return None
        
        if entry.is_expired():
            async with self._lock:
                self._cache.pop(key, None)
            return None
        
        entry.hit_count += 1
        return entry.value
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: Optional[int] = None,
    ) -> None:
        async with self._lock:
            # Evict if at capacity
            if len(self._cache) >= self._max_size:
                await self._evict()
            
            expires_at = None
            if ttl_seconds:
                expires_at = datetime.now() + timedelta(seconds=ttl_seconds)
            
            self._cache[key] = CacheEntry(
                key=key,
                value=value,
                expires_at=expires_at,
            )
    
    async def delete(self, key: str) -> None:
        async with self._lock:
            self._cache.pop(key, None)
    
    async def clear(self) -> None:
        async with self._lock:
            self._cache.clear()
    
    async def _evict(self) -> None:
        """Evict least recently used entries."""
        # Remove expired first
        expired = [k for k, v in self._cache.items() if v.is_expired()]
        for key in expired:
            self._cache.pop(key, None)
        
        # Remove least used if still over capacity
        if len(self._cache) >= self._max_size:
            sorted_entries = sorted(
                self._cache.items(),
                key=lambda x: (x[1].hit_count, x[1].created_at),
            )
            
            to_remove = len(self._cache) - self._max_size + 1
            for key, _ in sorted_entries[:to_remove]:
                self._cache.pop(key, None)


class QueryMiddleware(ABC):
    """Abstract query middleware."""
    
    @abstractmethod
    async def execute(
        self,
        context: QueryContext,
        next_handler: Callable[[QueryContext], Awaitable[Any]],
    ) -> Any:
        """Execute middleware."""
        pass


class LoggingMiddleware(QueryMiddleware):
    """Logging middleware."""
    
    async def execute(
        self,
        context: QueryContext,
        next_handler: Callable[[QueryContext], Awaitable[Any]],
    ) -> Any:
        logger.debug(
            f"Executing query: {context.query.query_type}"
        )
        
        try:
            result = await next_handler(context)
            
            logger.debug(
                f"Query completed: {context.query.query_type}"
            )
            
            return result
        
        except Exception as e:
            logger.error(
                f"Query failed: {context.query.query_type} - {e}"
            )
            raise


class CachingMiddleware(QueryMiddleware):
    """Caching middleware."""
    
    def __init__(
        self,
        cache: QueryCache,
        default_ttl: int = 300,
    ):
        self._cache = cache
        self._default_ttl = default_ttl
    
    async def execute(
        self,
        context: QueryContext,
        next_handler: Callable[[QueryContext], Awaitable[Any]],
    ) -> Any:
        if not context.use_cache:
            return await next_handler(context)
        
        cache_key = context.query.cache_key()
        
        # Try cache
        cached = await self._cache.get(cache_key)
        
        if cached is not None:
            context.extra["from_cache"] = True
            return cached
        
        # Execute and cache
        result = await next_handler(context)
        
        ttl = context.metadata.metadata.get("cache_ttl", self._default_ttl)
        await self._cache.set(cache_key, result, ttl)
        
        return result


class TimingMiddleware(QueryMiddleware):
    """Timing middleware."""
    
    async def execute(
        self,
        context: QueryContext,
        next_handler: Callable[[QueryContext], Awaitable[Any]],
    ) -> Any:
        start = datetime.now()
        
        try:
            return await next_handler(context)
        
        finally:
            duration = (datetime.now() - start).total_seconds() * 1000
            context.extra["duration_ms"] = duration


class PaginationMiddleware(QueryMiddleware):
    """Pagination middleware."""
    
    def __init__(
        self,
        default_page_size: int = 20,
        max_page_size: int = 100,
    ):
        self._default_page_size = default_page_size
        self._max_page_size = max_page_size
    
    async def execute(
        self,
        context: QueryContext,
        next_handler: Callable[[QueryContext], Awaitable[Any]],
    ) -> Any:
        query = context.query
        
        # Extract pagination params
        page = getattr(query, 'page', 1) or 1
        page_size = getattr(query, 'page_size', self._default_page_size)
        page_size = min(page_size or self._default_page_size, self._max_page_size)
        
        context.extra["page"] = page
        context.extra["page_size"] = page_size
        context.extra["offset"] = (page - 1) * page_size
        
        return await next_handler(context)


class HandlerRegistry:
    """
    Registry for query handlers.
    """
    
    def __init__(self):
        self._handlers: Dict[str, QueryHandler] = {}
    
    def register(
        self,
        query_type: Type[Q],
        handler: QueryHandler[Q, R],
    ) -> None:
        """Register a handler."""
        type_name = query_type.__name__
        self._handlers[type_name] = handler
        logger.debug(f"Registered query handler for {type_name}")
    
    def get(
        self,
        query_type: str,
    ) -> Optional[QueryHandler]:
        """Get handler for query type."""
        return self._handlers.get(query_type)
    
    def has(self, query_type: str) -> bool:
        """Check if handler exists."""
        return query_type in self._handlers


class QueryBus:
    """
    Query bus for executing queries.
    """
    
    def __init__(
        self,
        registry: Optional[HandlerRegistry] = None,
        middleware: Optional[List[QueryMiddleware]] = None,
        cache: Optional[QueryCache] = None,
    ):
        self._registry = registry or HandlerRegistry()
        self._middleware = middleware or []
        self._cache = cache
    
    def handler(
        self,
        query_type: Type[Q],
    ) -> Callable[[QueryHandler[Q, R]], QueryHandler[Q, R]]:
        """Decorator to register a handler."""
        def decorator(func: QueryHandler[Q, R]) -> QueryHandler[Q, R]:
            self._registry.register(query_type, func)
            return func
        
        return decorator
    
    def register(
        self,
        query_type: Type[Q],
        handler: QueryHandler[Q, R],
    ) -> None:
        """Register a handler."""
        self._registry.register(query_type, handler)
    
    def add_middleware(
        self,
        middleware: QueryMiddleware,
    ) -> "QueryBus":
        """Add middleware."""
        self._middleware.append(middleware)
        return self
    
    def with_caching(
        self,
        cache: Optional[QueryCache] = None,
        default_ttl: int = 300,
    ) -> "QueryBus":
        """Enable caching."""
        self._cache = cache or InMemoryQueryCache()
        self.add_middleware(CachingMiddleware(self._cache, default_ttl))
        return self
    
    async def query(
        self,
        query: Q,
        use_cache: bool = True,
    ) -> QueryResult[R]:
        """Execute a query."""
        query_type = query.query_type
        
        handler = self._registry.get(query_type)
        
        if not handler:
            raise HandlerNotFoundError(
                f"No handler for query: {query_type}"
            )
        
        context = QueryContext(
            query=query,
            metadata=query._metadata,
            use_cache=use_cache,
        )
        
        # Build middleware chain
        async def execute_handler(ctx: QueryContext) -> Any:
            return await handler(ctx.query)
        
        chain = execute_handler
        
        for middleware in reversed(self._middleware):
            chain = self._wrap_middleware(middleware, chain)
        
        # Execute
        try:
            start = datetime.now()
            data = await chain(context)
            duration = (datetime.now() - start).total_seconds() * 1000
            
            return QueryResult[R](
                query_id=query.query_id,
                query_type=query_type,
                success=True,
                data=data,
                from_cache=context.extra.get("from_cache", False),
                executed_at=datetime.now(),
                duration_ms=context.extra.get("duration_ms", duration),
                metadata=context.extra,
            )
        
        except Exception as e:
            return QueryResult[R](
                query_id=query.query_id,
                query_type=query_type,
                success=False,
                error=str(e),
                executed_at=datetime.now(),
            )
    
    def _wrap_middleware(
        self,
        middleware: QueryMiddleware,
        next_handler: Callable[[QueryContext], Awaitable[Any]],
    ) -> Callable[[QueryContext], Awaitable[Any]]:
        """Wrap middleware around handler."""
        async def wrapper(context: QueryContext) -> Any:
            return await middleware.execute(context, next_handler)
        
        return wrapper
    
    async def invalidate_cache(
        self,
        query_type: Optional[Type[Q]] = None,
        key: Optional[str] = None,
    ) -> None:
        """Invalidate cache."""
        if not self._cache:
            return
        
        if key:
            await self._cache.delete(key)
        elif query_type is None:
            await self._cache.clear()


class ReadModel(ABC, Generic[T]):
    """
    Abstract read model.
    """
    
    @abstractmethod
    async def get(self, id: str) -> Optional[T]:
        """Get by ID."""
        pass
    
    @abstractmethod
    async def list(
        self,
        offset: int = 0,
        limit: int = 20,
        **filters: Any,
    ) -> List[T]:
        """List with pagination."""
        pass
    
    @abstractmethod
    async def count(self, **filters: Any) -> int:
        """Count items."""
        pass


class InMemoryReadModel(ReadModel[T]):
    """In-memory read model."""
    
    def __init__(self):
        self._data: Dict[str, T] = {}
        self._lock = asyncio.Lock()
    
    async def get(self, id: str) -> Optional[T]:
        return self._data.get(id)
    
    async def list(
        self,
        offset: int = 0,
        limit: int = 20,
        **filters: Any,
    ) -> List[T]:
        items = list(self._data.values())
        
        # Apply filters (simplified)
        for key, value in filters.items():
            items = [
                item for item in items
                if getattr(item, key, None) == value
            ]
        
        return items[offset:offset + limit]
    
    async def count(self, **filters: Any) -> int:
        if not filters:
            return len(self._data)
        
        return len(await self.list(0, len(self._data), **filters))
    
    async def add(self, id: str, item: T) -> None:
        """Add item."""
        async with self._lock:
            self._data[id] = item
    
    async def update(self, id: str, item: T) -> None:
        """Update item."""
        async with self._lock:
            self._data[id] = item
    
    async def remove(self, id: str) -> None:
        """Remove item."""
        async with self._lock:
            self._data.pop(id, None)


class QueryDispatcher:
    """
    Simple query dispatcher without middleware.
    """
    
    def __init__(self):
        self._handlers: Dict[str, QueryHandler] = {}
    
    def register(
        self,
        query_type: Type[Q],
        handler: QueryHandler[Q, R],
    ) -> None:
        """Register handler."""
        self._handlers[query_type.__name__] = handler
    
    async def dispatch(self, query: Q) -> R:
        """Dispatch query."""
        handler = self._handlers.get(query.query_type)
        
        if not handler:
            raise HandlerNotFoundError(
                f"No handler for: {query.query_type}"
            )
        
        return await handler(query)


# Decorators
def query_handler(
    query_type: Type[Q],
    bus: Optional[QueryBus] = None,
) -> Callable:
    """
    Decorator to register query handler.
    
    Example:
        @query_handler(GetOrderQuery)
        async def handle_get_order(query):
            ...
    """
    def decorator(func: Callable) -> Callable:
        if bus:
            bus.register(query_type, func)
        
        func._query_type = query_type
        return func
    
    return decorator


def cached(
    ttl_seconds: int = 300,
    key_fn: Optional[Callable[[Q], str]] = None,
) -> Callable:
    """
    Decorator to cache query results.
    
    Example:
        @cached(ttl_seconds=600)
        async def get_orders(query):
            ...
    """
    def decorator(func: Callable) -> Callable:
        cache: Dict[str, Any] = {}
        cache_times: Dict[str, datetime] = {}
        
        @wraps(func)
        async def wrapper(query: Q, *args, **kwargs) -> Any:
            key = key_fn(query) if key_fn else query.cache_key()
            
            # Check cache
            if key in cache:
                cached_time = cache_times[key]
                if (datetime.now() - cached_time).total_seconds() < ttl_seconds:
                    return cache[key]
            
            # Execute and cache
            result = await func(query, *args, **kwargs)
            cache[key] = result
            cache_times[key] = datetime.now()
            
            return result
        
        return wrapper
    
    return decorator


def paginated(
    default_page_size: int = 20,
    max_page_size: int = 100,
) -> Callable:
    """
    Decorator to add pagination support.
    
    Example:
        @paginated(default_page_size=50)
        async def list_orders(query, offset, limit):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(query: Q, *args, **kwargs) -> Any:
            page = getattr(query, 'page', 1) or 1
            page_size = getattr(query, 'page_size', default_page_size)
            page_size = min(page_size or default_page_size, max_page_size)
            
            offset = (page - 1) * page_size
            
            return await func(query, offset=offset, limit=page_size, *args, **kwargs)
        
        return wrapper
    
    return decorator


# Factory functions
def create_query_bus(
    with_caching: bool = False,
    with_logging: bool = True,
    with_timing: bool = True,
    cache_ttl: int = 300,
) -> QueryBus:
    """Create a query bus with common middleware."""
    bus = QueryBus()
    
    if with_timing:
        bus.add_middleware(TimingMiddleware())
    
    if with_logging:
        bus.add_middleware(LoggingMiddleware())
    
    if with_caching:
        bus.with_caching(default_ttl=cache_ttl)
    
    return bus


def create_query_cache(
    max_size: int = 1000,
) -> QueryCache:
    """Create a query cache."""
    return InMemoryQueryCache(max_size)


def create_read_model() -> InMemoryReadModel:
    """Create a read model."""
    return InMemoryReadModel()


def create_query_dispatcher() -> QueryDispatcher:
    """Create a simple query dispatcher."""
    return QueryDispatcher()


__all__ = [
    # Exceptions
    "QueryBusError",
    "HandlerNotFoundError",
    "QueryExecutionError",
    "CacheError",
    # Enums
    "QueryType",
    # Data classes
    "QueryMetadata",
    "Query",
    "QueryResult",
    "QueryContext",
    "CacheEntry",
    # Abstract classes
    "QueryCache",
    "QueryMiddleware",
    "ReadModel",
    # Middleware implementations
    "LoggingMiddleware",
    "CachingMiddleware",
    "TimingMiddleware",
    "PaginationMiddleware",
    # Core classes
    "InMemoryQueryCache",
    "HandlerRegistry",
    "QueryBus",
    "InMemoryReadModel",
    "QueryDispatcher",
    # Decorators
    "query_handler",
    "cached",
    "paginated",
    # Factory functions
    "create_query_bus",
    "create_query_cache",
    "create_read_model",
    "create_query_dispatcher",
]
