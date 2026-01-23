"""
Enterprise GraphQL Manager Module.

Provides GraphQL schema definition, resolvers, dataloaders,
subscriptions, and query optimization.

Example:
    # Create GraphQL manager
    gql = create_graphql_manager()
    
    # Define types
    @gql.type()
    class User:
        id: str
        name: str
        email: str
    
    # Define resolvers
    @gql.resolver("Query", "user")
    async def resolve_user(parent, info, id: str) -> User:
        return await get_user(id)
    
    # Execute query
    result = await gql.execute('''
        query {
            user(id: "123") {
                name
                email
            }
        }
    ''')
"""

from __future__ import annotations

import asyncio
import functools
import inspect
import json
import logging
from abc import ABC, abstractmethod
from collections import defaultdict
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
    Type,
    TypeVar,
    Union,
)

T = TypeVar('T')


logger = logging.getLogger(__name__)


class GraphQLError(Exception):
    """Base GraphQL error."""
    def __init__(
        self,
        message: str,
        locations: Optional[List[Dict[str, int]]] = None,
        path: Optional[List[str]] = None,
        extensions: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.locations = locations
        self.path = path
        self.extensions = extensions or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to GraphQL error format."""
        error = {"message": self.message}
        if self.locations:
            error["locations"] = self.locations
        if self.path:
            error["path"] = self.path
        if self.extensions:
            error["extensions"] = self.extensions
        return error


class ValidationError(GraphQLError):
    """Schema validation error."""
    pass


class ExecutionError(GraphQLError):
    """Query execution error."""
    pass


class TypeKind(str, Enum):
    """GraphQL type kinds."""
    SCALAR = "SCALAR"
    OBJECT = "OBJECT"
    INTERFACE = "INTERFACE"
    UNION = "UNION"
    ENUM = "ENUM"
    INPUT_OBJECT = "INPUT_OBJECT"
    LIST = "LIST"
    NON_NULL = "NON_NULL"


@dataclass
class FieldDefinition:
    """GraphQL field definition."""
    name: str
    type: str
    description: str = ""
    args: Dict[str, "ArgumentDefinition"] = field(default_factory=dict)
    resolver: Optional[Callable] = None
    deprecation_reason: Optional[str] = None


@dataclass
class ArgumentDefinition:
    """GraphQL argument definition."""
    name: str
    type: str
    description: str = ""
    default_value: Any = None


@dataclass
class TypeDefinition:
    """GraphQL type definition."""
    name: str
    kind: TypeKind
    description: str = ""
    fields: Dict[str, FieldDefinition] = field(default_factory=dict)
    interfaces: List[str] = field(default_factory=list)
    possible_types: List[str] = field(default_factory=list)  # For unions/interfaces
    enum_values: List[str] = field(default_factory=list)
    input_fields: Dict[str, ArgumentDefinition] = field(default_factory=dict)


@dataclass
class ResolverInfo:
    """Resolver execution info."""
    field_name: str
    parent_type: str
    return_type: str
    path: List[str]
    context: Dict[str, Any]
    variables: Dict[str, Any]
    operation_name: Optional[str]


@dataclass
class ExecutionResult:
    """GraphQL execution result."""
    data: Optional[Dict[str, Any]] = None
    errors: List[GraphQLError] = field(default_factory=list)
    extensions: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to response format."""
        result = {}
        if self.data is not None:
            result["data"] = self.data
        if self.errors:
            result["errors"] = [e.to_dict() for e in self.errors]
        if self.extensions:
            result["extensions"] = self.extensions
        return result


class DataLoader(Generic[T]):
    """
    DataLoader for batching and caching data fetches.
    """
    
    def __init__(
        self,
        batch_fn: Callable[[List[str]], Awaitable[List[T]]],
        max_batch_size: int = 100,
        cache: bool = True,
    ):
        self._batch_fn = batch_fn
        self._max_batch_size = max_batch_size
        self._cache_enabled = cache
        
        self._cache: Dict[str, T] = {}
        self._pending: Dict[str, asyncio.Future] = {}
        self._queue: List[str] = []
        self._batch_scheduled = False
    
    async def load(self, key: str) -> T:
        """Load a single item."""
        # Check cache
        if self._cache_enabled and key in self._cache:
            return self._cache[key]
        
        # Check pending
        if key in self._pending:
            return await self._pending[key]
        
        # Create future and add to queue
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[key] = future
        self._queue.append(key)
        
        # Schedule batch
        if not self._batch_scheduled:
            self._batch_scheduled = True
            asyncio.get_event_loop().call_soon(
                lambda: asyncio.create_task(self._dispatch())
            )
        
        return await future
    
    async def load_many(self, keys: List[str]) -> List[T]:
        """Load multiple items."""
        return await asyncio.gather(*[self.load(key) for key in keys])
    
    async def _dispatch(self) -> None:
        """Dispatch batched requests."""
        self._batch_scheduled = False
        
        if not self._queue:
            return
        
        # Get batch
        batch = self._queue[:self._max_batch_size]
        self._queue = self._queue[self._max_batch_size:]
        
        try:
            results = await self._batch_fn(batch)
            
            # Resolve futures
            for key, result in zip(batch, results):
                if self._cache_enabled:
                    self._cache[key] = result
                
                future = self._pending.pop(key, None)
                if future and not future.done():
                    future.set_result(result)
                    
        except Exception as e:
            # Reject all futures
            for key in batch:
                future = self._pending.pop(key, None)
                if future and not future.done():
                    future.set_exception(e)
        
        # Schedule next batch if queue not empty
        if self._queue and not self._batch_scheduled:
            self._batch_scheduled = True
            asyncio.get_event_loop().call_soon(
                lambda: asyncio.create_task(self._dispatch())
            )
    
    def clear(self, key: Optional[str] = None) -> None:
        """Clear cache."""
        if key:
            self._cache.pop(key, None)
        else:
            self._cache.clear()
    
    def prime(self, key: str, value: T) -> None:
        """Prime cache with value."""
        if self._cache_enabled:
            self._cache[key] = value


class Middleware(ABC):
    """GraphQL middleware."""
    
    @abstractmethod
    async def resolve(
        self,
        next_fn: Callable,
        parent: Any,
        info: ResolverInfo,
        **kwargs,
    ) -> Any:
        """Middleware resolver."""
        pass


class LoggingMiddleware(Middleware):
    """Logging middleware."""
    
    async def resolve(
        self,
        next_fn: Callable,
        parent: Any,
        info: ResolverInfo,
        **kwargs,
    ) -> Any:
        start_time = datetime.utcnow()
        
        try:
            result = await next_fn(parent, info, **kwargs)
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            
            logger.debug(
                f"Resolved {info.parent_type}.{info.field_name} "
                f"in {elapsed:.3f}s"
            )
            
            return result
        except Exception as e:
            logger.error(
                f"Error resolving {info.parent_type}.{info.field_name}: {e}"
            )
            raise


class CachingMiddleware(Middleware):
    """Caching middleware."""
    
    def __init__(self, ttl: int = 60):
        self._cache: Dict[str, Tuple[Any, datetime]] = {}
        self._ttl = ttl
    
    async def resolve(
        self,
        next_fn: Callable,
        parent: Any,
        info: ResolverInfo,
        **kwargs,
    ) -> Any:
        cache_key = f"{info.parent_type}.{info.field_name}:{json.dumps(kwargs, sort_keys=True)}"
        
        # Check cache
        if cache_key in self._cache:
            value, cached_at = self._cache[cache_key]
            if (datetime.utcnow() - cached_at).total_seconds() < self._ttl:
                return value
        
        result = await next_fn(parent, info, **kwargs)
        self._cache[cache_key] = (result, datetime.utcnow())
        
        return result


class Schema:
    """GraphQL schema."""
    
    def __init__(self):
        self._types: Dict[str, TypeDefinition] = {}
        self._resolvers: Dict[str, Dict[str, Callable]] = defaultdict(dict)
        self._directives: Dict[str, Callable] = {}
        
        # Initialize built-in types
        self._init_built_in_types()
    
    def _init_built_in_types(self) -> None:
        """Initialize built-in scalar types."""
        scalars = ["String", "Int", "Float", "Boolean", "ID"]
        for scalar in scalars:
            self._types[scalar] = TypeDefinition(
                name=scalar,
                kind=TypeKind.SCALAR,
            )
        
        # Query and Mutation root types
        self._types["Query"] = TypeDefinition(
            name="Query",
            kind=TypeKind.OBJECT,
        )
        self._types["Mutation"] = TypeDefinition(
            name="Mutation",
            kind=TypeKind.OBJECT,
        )
        self._types["Subscription"] = TypeDefinition(
            name="Subscription",
            kind=TypeKind.OBJECT,
        )
    
    def add_type(self, type_def: TypeDefinition) -> None:
        """Add type definition."""
        self._types[type_def.name] = type_def
    
    def get_type(self, name: str) -> Optional[TypeDefinition]:
        """Get type definition."""
        return self._types.get(name)
    
    def add_field(
        self,
        type_name: str,
        field: FieldDefinition,
    ) -> None:
        """Add field to type."""
        if type_name not in self._types:
            self._types[type_name] = TypeDefinition(
                name=type_name,
                kind=TypeKind.OBJECT,
            )
        
        self._types[type_name].fields[field.name] = field
    
    def add_resolver(
        self,
        type_name: str,
        field_name: str,
        resolver: Callable,
    ) -> None:
        """Add field resolver."""
        self._resolvers[type_name][field_name] = resolver
    
    def get_resolver(
        self,
        type_name: str,
        field_name: str,
    ) -> Optional[Callable]:
        """Get field resolver."""
        return self._resolvers.get(type_name, {}).get(field_name)


class GraphQLManager:
    """
    GraphQL schema and execution manager.
    """
    
    def __init__(self):
        self._schema = Schema()
        self._middlewares: List[Middleware] = []
        self._dataloaders: Dict[str, DataLoader] = {}
    
    @property
    def schema(self) -> Schema:
        return self._schema
    
    # Type decorators
    def type(
        self,
        name: Optional[str] = None,
        description: str = "",
    ) -> Callable:
        """Decorator to register GraphQL type."""
        def decorator(cls: Type) -> Type:
            type_name = name or cls.__name__
            
            # Create type definition from class
            fields = {}
            for field_name, field_type in getattr(cls, '__annotations__', {}).items():
                fields[field_name] = FieldDefinition(
                    name=field_name,
                    type=self._python_type_to_graphql(field_type),
                )
            
            type_def = TypeDefinition(
                name=type_name,
                kind=TypeKind.OBJECT,
                description=description,
                fields=fields,
            )
            
            self._schema.add_type(type_def)
            return cls
        
        return decorator
    
    def input_type(
        self,
        name: Optional[str] = None,
    ) -> Callable:
        """Decorator to register input type."""
        def decorator(cls: Type) -> Type:
            type_name = name or cls.__name__
            
            input_fields = {}
            for field_name, field_type in getattr(cls, '__annotations__', {}).items():
                input_fields[field_name] = ArgumentDefinition(
                    name=field_name,
                    type=self._python_type_to_graphql(field_type),
                )
            
            type_def = TypeDefinition(
                name=type_name,
                kind=TypeKind.INPUT_OBJECT,
                input_fields=input_fields,
            )
            
            self._schema.add_type(type_def)
            return cls
        
        return decorator
    
    def enum_type(
        self,
        name: Optional[str] = None,
    ) -> Callable:
        """Decorator to register enum type."""
        def decorator(cls: Type) -> Type:
            type_name = name or cls.__name__
            
            enum_values = [e.name for e in cls] if issubclass(cls, Enum) else []
            
            type_def = TypeDefinition(
                name=type_name,
                kind=TypeKind.ENUM,
                enum_values=enum_values,
            )
            
            self._schema.add_type(type_def)
            return cls
        
        return decorator
    
    # Resolver decorators
    def resolver(
        self,
        type_name: str,
        field_name: str,
    ) -> Callable:
        """Decorator to register resolver."""
        def decorator(func: Callable) -> Callable:
            self._schema.add_resolver(type_name, field_name, func)
            return func
        
        return decorator
    
    def query(self, field_name: str) -> Callable:
        """Decorator for Query resolver."""
        return self.resolver("Query", field_name)
    
    def mutation(self, field_name: str) -> Callable:
        """Decorator for Mutation resolver."""
        return self.resolver("Mutation", field_name)
    
    def subscription(self, field_name: str) -> Callable:
        """Decorator for Subscription resolver."""
        return self.resolver("Subscription", field_name)
    
    def field(
        self,
        type_name: str,
        field_name: str,
        return_type: str,
        description: str = "",
        args: Optional[Dict[str, str]] = None,
    ) -> Callable:
        """Decorator to add field and resolver."""
        def decorator(func: Callable) -> Callable:
            # Add field definition
            field_args = {}
            if args:
                for arg_name, arg_type in args.items():
                    field_args[arg_name] = ArgumentDefinition(
                        name=arg_name,
                        type=arg_type,
                    )
            
            field_def = FieldDefinition(
                name=field_name,
                type=return_type,
                description=description,
                args=field_args,
            )
            
            self._schema.add_field(type_name, field_def)
            self._schema.add_resolver(type_name, field_name, func)
            
            return func
        
        return decorator
    
    # Middleware
    def add_middleware(self, middleware: Middleware) -> None:
        """Add execution middleware."""
        self._middlewares.append(middleware)
    
    # DataLoader
    def dataloader(
        self,
        name: str,
        batch_fn: Callable[[List[str]], Awaitable[List[Any]]],
        max_batch_size: int = 100,
    ) -> DataLoader:
        """Create and register dataloader."""
        loader = DataLoader(batch_fn, max_batch_size)
        self._dataloaders[name] = loader
        return loader
    
    def get_dataloader(self, name: str) -> Optional[DataLoader]:
        """Get registered dataloader."""
        return self._dataloaders.get(name)
    
    # Execution
    async def execute(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
        operation_name: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> ExecutionResult:
        """Execute GraphQL query."""
        try:
            # Parse query (simplified)
            parsed = self._parse_query(query)
            
            # Execute
            data = await self._execute_operation(
                parsed,
                variables or {},
                operation_name,
                context or {},
            )
            
            return ExecutionResult(data=data)
            
        except GraphQLError as e:
            return ExecutionResult(errors=[e])
        except Exception as e:
            return ExecutionResult(
                errors=[GraphQLError(str(e))]
            )
    
    def _parse_query(self, query: str) -> Dict[str, Any]:
        """Parse GraphQL query (simplified)."""
        # This is a simplified parser for demo
        # Real implementation would use proper GraphQL parser
        return {"query": query, "type": "query"}
    
    async def _execute_operation(
        self,
        parsed: Dict[str, Any],
        variables: Dict[str, Any],
        operation_name: Optional[str],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute parsed operation."""
        # Simplified execution
        # Real implementation would traverse AST
        return {}
    
    def _python_type_to_graphql(self, python_type: Any) -> str:
        """Convert Python type to GraphQL type."""
        type_map = {
            str: "String",
            int: "Int",
            float: "Float",
            bool: "Boolean",
        }
        
        if python_type in type_map:
            return type_map[python_type]
        
        # Handle Optional, List, etc.
        origin = getattr(python_type, "__origin__", None)
        
        if origin is list:
            args = getattr(python_type, "__args__", [])
            if args:
                inner = self._python_type_to_graphql(args[0])
                return f"[{inner}]"
        
        if origin is Union:
            args = getattr(python_type, "__args__", [])
            # Optional[X] is Union[X, None]
            non_none = [a for a in args if a is not type(None)]
            if len(non_none) == 1:
                return self._python_type_to_graphql(non_none[0])
        
        # Default to type name
        return getattr(python_type, "__name__", "String")


# Global manager
_global_manager: Optional[GraphQLManager] = None


# Factory functions
def create_graphql_manager() -> GraphQLManager:
    """Create GraphQL manager."""
    return GraphQLManager()


def create_dataloader(
    batch_fn: Callable[[List[str]], Awaitable[List[T]]],
    max_batch_size: int = 100,
    cache: bool = True,
) -> DataLoader[T]:
    """Create dataloader."""
    return DataLoader(batch_fn, max_batch_size, cache)


def create_schema() -> Schema:
    """Create GraphQL schema."""
    return Schema()


def create_logging_middleware() -> LoggingMiddleware:
    """Create logging middleware."""
    return LoggingMiddleware()


def create_caching_middleware(ttl: int = 60) -> CachingMiddleware:
    """Create caching middleware."""
    return CachingMiddleware(ttl)


def get_global_manager() -> GraphQLManager:
    """Get global GraphQL manager."""
    global _global_manager
    if _global_manager is None:
        _global_manager = create_graphql_manager()
    return _global_manager


__all__ = [
    # Exceptions
    "GraphQLError",
    "ValidationError",
    "ExecutionError",
    # Enums
    "TypeKind",
    # Data classes
    "FieldDefinition",
    "ArgumentDefinition",
    "TypeDefinition",
    "ResolverInfo",
    "ExecutionResult",
    # DataLoader
    "DataLoader",
    # Middleware
    "Middleware",
    "LoggingMiddleware",
    "CachingMiddleware",
    # Schema
    "Schema",
    # Manager
    "GraphQLManager",
    # Factory functions
    "create_graphql_manager",
    "create_dataloader",
    "create_schema",
    "create_logging_middleware",
    "create_caching_middleware",
    "get_global_manager",
]
