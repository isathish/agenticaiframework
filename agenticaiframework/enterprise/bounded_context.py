"""
Enterprise Bounded Context Module.

Provides bounded context patterns for DDD architectures,
context mapping, anti-corruption layers, and context integration.

Example:
    # Define a bounded context
    context = create_bounded_context("orders")
    context.register_aggregate(Order)
    context.register_service(OrderService)
    
    # Define context map
    map = create_context_map()
    map.add_relationship(
        upstream="inventory",
        downstream="orders",
        pattern=IntegrationPattern.ANTICORRUPTION_LAYER
    )
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
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
)

T = TypeVar('T')


class BoundedContextError(Exception):
    """Bounded context error."""
    pass


class IntegrationError(BoundedContextError):
    """Integration error."""
    pass


class TranslationError(BoundedContextError):
    """Translation error."""
    pass


class IntegrationPattern(str, Enum):
    """Integration patterns between contexts."""
    SHARED_KERNEL = "shared_kernel"
    CUSTOMER_SUPPLIER = "customer_supplier"
    CONFORMIST = "conformist"
    ANTICORRUPTION_LAYER = "anticorruption_layer"
    OPEN_HOST_SERVICE = "open_host_service"
    PUBLISHED_LANGUAGE = "published_language"
    SEPARATE_WAYS = "separate_ways"
    BIG_BALL_OF_MUD = "big_ball_of_mud"


class RelationshipType(str, Enum):
    """Relationship types."""
    UPSTREAM = "upstream"
    DOWNSTREAM = "downstream"
    PARTNERSHIP = "partnership"
    CONFORMIST = "conformist"


@dataclass
class ContextRelationship:
    """Relationship between bounded contexts."""
    upstream_context: str
    downstream_context: str
    pattern: IntegrationPattern
    description: Optional[str] = None
    shared_types: List[str] = field(default_factory=list)


@dataclass
class ContextMetadata:
    """Bounded context metadata."""
    name: str
    description: Optional[str] = None
    team: Optional[str] = None
    version: str = "1.0.0"
    created_at: datetime = field(default_factory=datetime.now)
    dependencies: List[str] = field(default_factory=list)


class Translator(ABC, Generic[T]):
    """
    Translator for converting between contexts.
    """
    
    @abstractmethod
    def translate_to_local(self, external: Any) -> T:
        """Translate external model to local model."""
        pass
    
    @abstractmethod
    def translate_to_external(self, local: T) -> Any:
        """Translate local model to external model."""
        pass


class SimpleTranslator(Translator[T]):
    """
    Simple translator with mapping functions.
    """
    
    def __init__(
        self,
        to_local: Callable[[Any], T],
        to_external: Callable[[T], Any],
    ):
        self._to_local = to_local
        self._to_external = to_external
    
    def translate_to_local(self, external: Any) -> T:
        try:
            return self._to_local(external)
        except Exception as e:
            raise TranslationError(f"Failed to translate to local: {e}") from e
    
    def translate_to_external(self, local: T) -> Any:
        try:
            return self._to_external(local)
        except Exception as e:
            raise TranslationError(f"Failed to translate to external: {e}") from e


class AntiCorruptionLayer(ABC):
    """
    Anti-corruption layer for isolating contexts.
    """
    
    @abstractmethod
    async def request(self, operation: str, data: Any) -> Any:
        """Make a request to external context."""
        pass


class DefaultAntiCorruptionLayer(AntiCorruptionLayer):
    """
    Default anti-corruption layer implementation.
    """
    
    def __init__(self):
        self._translators: Dict[str, Translator] = {}
        self._adapters: Dict[str, Callable] = {}
    
    def register_translator(
        self,
        type_name: str,
        translator: Translator,
    ) -> None:
        """Register a translator for a type."""
        self._translators[type_name] = translator
    
    def register_adapter(
        self,
        operation: str,
        adapter: Callable,
    ) -> None:
        """Register an adapter for an operation."""
        self._adapters[operation] = adapter
    
    async def request(self, operation: str, data: Any) -> Any:
        adapter = self._adapters.get(operation)
        if not adapter:
            raise IntegrationError(f"No adapter for operation: {operation}")
        
        return await adapter(data)
    
    def translate(self, type_name: str, data: Any, to_local: bool = True) -> Any:
        """Translate data using registered translator."""
        translator = self._translators.get(type_name)
        if not translator:
            raise TranslationError(f"No translator for type: {type_name}")
        
        if to_local:
            return translator.translate_to_local(data)
        else:
            return translator.translate_to_external(data)


class OpenHostService(ABC):
    """
    Open host service for exposing context capabilities.
    """
    
    @abstractmethod
    def get_operations(self) -> List[str]:
        """Get available operations."""
        pass
    
    @abstractmethod
    async def execute(self, operation: str, data: Any) -> Any:
        """Execute an operation."""
        pass


class DefaultOpenHostService(OpenHostService):
    """
    Default open host service implementation.
    """
    
    def __init__(self, context: "BoundedContext"):
        self._context = context
        self._operations: Dict[str, Callable] = {}
    
    def register_operation(
        self,
        name: str,
        handler: Callable,
    ) -> None:
        """Register an operation."""
        self._operations[name] = handler
    
    def get_operations(self) -> List[str]:
        return list(self._operations.keys())
    
    async def execute(self, operation: str, data: Any) -> Any:
        handler = self._operations.get(operation)
        if not handler:
            raise IntegrationError(f"Unknown operation: {operation}")
        
        return await handler(data)


class SharedKernel:
    """
    Shared kernel between contexts.
    """
    
    def __init__(self, name: str):
        self._name = name
        self._types: Dict[str, Type] = {}
        self._contexts: Set[str] = set()
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def contexts(self) -> Set[str]:
        return self._contexts.copy()
    
    def add_type(self, type_class: Type) -> None:
        """Add a shared type."""
        self._types[type_class.__name__] = type_class
    
    def get_type(self, name: str) -> Optional[Type]:
        """Get a shared type."""
        return self._types.get(name)
    
    def join(self, context_name: str) -> None:
        """Add a context to the kernel."""
        self._contexts.add(context_name)
    
    def leave(self, context_name: str) -> None:
        """Remove a context from the kernel."""
        self._contexts.discard(context_name)


class PublishedLanguage:
    """
    Published language for context communication.
    """
    
    def __init__(self, name: str, version: str = "1.0.0"):
        self._name = name
        self._version = version
        self._schemas: Dict[str, Dict[str, Any]] = {}
        self._examples: Dict[str, Any] = {}
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def version(self) -> str:
        return self._version
    
    def define_schema(
        self,
        name: str,
        schema: Dict[str, Any],
        example: Optional[Any] = None,
    ) -> None:
        """Define a schema."""
        self._schemas[name] = schema
        if example:
            self._examples[name] = example
    
    def get_schema(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a schema."""
        return self._schemas.get(name)
    
    def get_example(self, name: str) -> Optional[Any]:
        """Get an example."""
        return self._examples.get(name)
    
    def validate(self, name: str, data: Any) -> bool:
        """Validate data against schema."""
        schema = self._schemas.get(name)
        if not schema:
            return False
        
        # Simple validation - check required fields
        required = schema.get("required", [])
        if isinstance(data, dict):
            return all(field in data for field in required)
        return False


class BoundedContext:
    """
    Bounded context implementation.
    """
    
    def __init__(
        self,
        name: str,
        description: Optional[str] = None,
    ):
        self._metadata = ContextMetadata(name=name, description=description)
        self._aggregates: Dict[str, Type] = {}
        self._services: Dict[str, Any] = {}
        self._repositories: Dict[str, Any] = {}
        self._events: Dict[str, Type] = {}
        self._acl: Optional[AntiCorruptionLayer] = None
        self._host_service: Optional[OpenHostService] = None
        self._shared_kernels: Dict[str, SharedKernel] = {}
    
    @property
    def name(self) -> str:
        return self._metadata.name
    
    @property
    def metadata(self) -> ContextMetadata:
        return self._metadata
    
    def register_aggregate(self, aggregate_class: Type) -> None:
        """Register an aggregate."""
        self._aggregates[aggregate_class.__name__] = aggregate_class
    
    def register_service(
        self,
        service_class: Type,
        instance: Optional[Any] = None,
    ) -> None:
        """Register a service."""
        self._services[service_class.__name__] = instance or service_class
    
    def register_repository(
        self,
        repository_class: Type,
        instance: Optional[Any] = None,
    ) -> None:
        """Register a repository."""
        self._repositories[repository_class.__name__] = instance or repository_class
    
    def register_event(self, event_class: Type) -> None:
        """Register an event."""
        self._events[event_class.__name__] = event_class
    
    def get_aggregate(self, name: str) -> Optional[Type]:
        """Get an aggregate by name."""
        return self._aggregates.get(name)
    
    def get_service(self, name: str) -> Optional[Any]:
        """Get a service by name."""
        return self._services.get(name)
    
    def get_repository(self, name: str) -> Optional[Any]:
        """Get a repository by name."""
        return self._repositories.get(name)
    
    def set_acl(self, acl: AntiCorruptionLayer) -> None:
        """Set anti-corruption layer."""
        self._acl = acl
    
    def get_acl(self) -> Optional[AntiCorruptionLayer]:
        """Get anti-corruption layer."""
        return self._acl
    
    def set_host_service(self, service: OpenHostService) -> None:
        """Set open host service."""
        self._host_service = service
    
    def get_host_service(self) -> Optional[OpenHostService]:
        """Get open host service."""
        return self._host_service
    
    def join_shared_kernel(self, kernel: SharedKernel) -> None:
        """Join a shared kernel."""
        kernel.join(self.name)
        self._shared_kernels[kernel.name] = kernel
    
    def leave_shared_kernel(self, kernel_name: str) -> None:
        """Leave a shared kernel."""
        kernel = self._shared_kernels.pop(kernel_name, None)
        if kernel:
            kernel.leave(self.name)
    
    def add_dependency(self, context_name: str) -> None:
        """Add a dependency on another context."""
        if context_name not in self._metadata.dependencies:
            self._metadata.dependencies.append(context_name)


class ContextMap:
    """
    Context map showing relationships between bounded contexts.
    """
    
    def __init__(self):
        self._contexts: Dict[str, BoundedContext] = {}
        self._relationships: List[ContextRelationship] = []
        self._shared_kernels: Dict[str, SharedKernel] = {}
        self._published_languages: Dict[str, PublishedLanguage] = {}
    
    def add_context(self, context: BoundedContext) -> None:
        """Add a bounded context."""
        self._contexts[context.name] = context
    
    def get_context(self, name: str) -> Optional[BoundedContext]:
        """Get a bounded context."""
        return self._contexts.get(name)
    
    def add_relationship(
        self,
        upstream: str,
        downstream: str,
        pattern: IntegrationPattern,
        description: Optional[str] = None,
        shared_types: Optional[List[str]] = None,
    ) -> None:
        """Add a relationship between contexts."""
        relationship = ContextRelationship(
            upstream_context=upstream,
            downstream_context=downstream,
            pattern=pattern,
            description=description,
            shared_types=shared_types or [],
        )
        self._relationships.append(relationship)
    
    def get_relationships(
        self,
        context_name: Optional[str] = None,
    ) -> List[ContextRelationship]:
        """Get relationships, optionally filtered by context."""
        if context_name is None:
            return list(self._relationships)
        
        return [
            r for r in self._relationships
            if r.upstream_context == context_name
            or r.downstream_context == context_name
        ]
    
    def get_upstream(self, context_name: str) -> List[str]:
        """Get upstream contexts."""
        return [
            r.upstream_context for r in self._relationships
            if r.downstream_context == context_name
        ]
    
    def get_downstream(self, context_name: str) -> List[str]:
        """Get downstream contexts."""
        return [
            r.downstream_context for r in self._relationships
            if r.upstream_context == context_name
        ]
    
    def add_shared_kernel(self, kernel: SharedKernel) -> None:
        """Add a shared kernel."""
        self._shared_kernels[kernel.name] = kernel
    
    def add_published_language(self, language: PublishedLanguage) -> None:
        """Add a published language."""
        self._published_languages[language.name] = language
    
    def get_all_contexts(self) -> List[BoundedContext]:
        """Get all contexts."""
        return list(self._contexts.values())
    
    def visualize(self) -> str:
        """Generate text visualization of context map."""
        lines = ["Context Map:", "=" * 40]
        
        # List contexts
        lines.append("\nContexts:")
        for name, context in self._contexts.items():
            lines.append(f"  - {name}: {context.metadata.description or 'No description'}")
        
        # List relationships
        lines.append("\nRelationships:")
        for rel in self._relationships:
            lines.append(
                f"  {rel.upstream_context} --> {rel.downstream_context} "
                f"[{rel.pattern.value}]"
            )
        
        # List shared kernels
        if self._shared_kernels:
            lines.append("\nShared Kernels:")
            for name, kernel in self._shared_kernels.items():
                lines.append(f"  - {name}: {', '.join(kernel.contexts)}")
        
        return "\n".join(lines)


class ContextIntegration:
    """
    Context integration helper.
    """
    
    def __init__(
        self,
        source: BoundedContext,
        target: BoundedContext,
        pattern: IntegrationPattern,
    ):
        self._source = source
        self._target = target
        self._pattern = pattern
        self._translators: Dict[str, Translator] = {}
    
    def register_translator(
        self,
        type_name: str,
        translator: Translator,
    ) -> None:
        """Register a translator."""
        self._translators[type_name] = translator
    
    async def send(self, operation: str, data: Any) -> Any:
        """Send data to target context."""
        # Use ACL if available
        target_acl = self._target.get_acl()
        if target_acl:
            return await target_acl.request(operation, data)
        
        # Use host service if available
        host_service = self._target.get_host_service()
        if host_service:
            return await host_service.execute(operation, data)
        
        raise IntegrationError(
            f"No integration mechanism available for context: {self._target.name}"
        )
    
    def translate(self, type_name: str, data: Any, to_target: bool = True) -> Any:
        """Translate data between contexts."""
        translator = self._translators.get(type_name)
        if not translator:
            raise TranslationError(f"No translator for type: {type_name}")
        
        if to_target:
            return translator.translate_to_external(data)
        else:
            return translator.translate_to_local(data)


class ContextRegistry:
    """
    Global registry for bounded contexts.
    """
    
    def __init__(self):
        self._contexts: Dict[str, BoundedContext] = {}
        self._map = ContextMap()
    
    def register(self, context: BoundedContext) -> None:
        """Register a context."""
        self._contexts[context.name] = context
        self._map.add_context(context)
    
    def get(self, name: str) -> Optional[BoundedContext]:
        """Get a context by name."""
        return self._contexts.get(name)
    
    def get_map(self) -> ContextMap:
        """Get the context map."""
        return self._map
    
    def all(self) -> List[BoundedContext]:
        """Get all contexts."""
        return list(self._contexts.values())


# Global registry
_global_registry = ContextRegistry()


# Decorators
def bounded_context(
    name: str,
    description: Optional[str] = None,
) -> Callable[[Type], Type]:
    """
    Class decorator to define a bounded context module.
    
    Example:
        @bounded_context("orders", "Order management context")
        class OrderContext:
            pass
    """
    def decorator(cls: Type) -> Type:
        context = BoundedContext(name, description)
        cls._bounded_context = context
        _global_registry.register(context)
        return cls
    
    return decorator


def context_aggregate(cls: Type) -> Type:
    """
    Class decorator to mark aggregate in context.
    
    Example:
        @context_aggregate
        class Order(AggregateRoot):
            pass
    """
    cls._is_context_aggregate = True
    return cls


def context_service(cls: Type) -> Type:
    """
    Class decorator to mark service in context.
    
    Example:
        @context_service
        class OrderService:
            pass
    """
    cls._is_context_service = True
    return cls


def translate(
    from_type: Type,
    to_type: Type,
) -> Callable[[Callable], Callable]:
    """
    Decorator to create a translator function.
    
    Example:
        @translate(ExternalOrder, Order)
        def translate_order(external: ExternalOrder) -> Order:
            return Order(...)
    """
    def decorator(func: Callable) -> Callable:
        func._translates_from = from_type
        func._translates_to = to_type
        return func
    
    return decorator


# Factory functions
def create_bounded_context(
    name: str,
    description: Optional[str] = None,
) -> BoundedContext:
    """Create a bounded context."""
    context = BoundedContext(name, description)
    _global_registry.register(context)
    return context


def create_context_map() -> ContextMap:
    """Create a context map."""
    return ContextMap()


def create_acl() -> DefaultAntiCorruptionLayer:
    """Create an anti-corruption layer."""
    return DefaultAntiCorruptionLayer()


def create_host_service(
    context: BoundedContext,
) -> DefaultOpenHostService:
    """Create an open host service."""
    service = DefaultOpenHostService(context)
    context.set_host_service(service)
    return service


def create_shared_kernel(name: str) -> SharedKernel:
    """Create a shared kernel."""
    return SharedKernel(name)


def create_published_language(
    name: str,
    version: str = "1.0.0",
) -> PublishedLanguage:
    """Create a published language."""
    return PublishedLanguage(name, version)


def create_translator(
    to_local: Callable[[Any], T],
    to_external: Callable[[T], Any],
) -> SimpleTranslator[T]:
    """Create a simple translator."""
    return SimpleTranslator(to_local, to_external)


def create_integration(
    source: BoundedContext,
    target: BoundedContext,
    pattern: IntegrationPattern,
) -> ContextIntegration:
    """Create a context integration."""
    return ContextIntegration(source, target, pattern)


def get_context(name: str) -> Optional[BoundedContext]:
    """Get context from global registry."""
    return _global_registry.get(name)


def get_context_map() -> ContextMap:
    """Get global context map."""
    return _global_registry.get_map()


__all__ = [
    # Exceptions
    "BoundedContextError",
    "IntegrationError",
    "TranslationError",
    # Enums
    "IntegrationPattern",
    "RelationshipType",
    # Data classes
    "ContextRelationship",
    "ContextMetadata",
    # Translators
    "Translator",
    "SimpleTranslator",
    # Anti-corruption layer
    "AntiCorruptionLayer",
    "DefaultAntiCorruptionLayer",
    # Open host service
    "OpenHostService",
    "DefaultOpenHostService",
    # Shared kernel
    "SharedKernel",
    # Published language
    "PublishedLanguage",
    # Bounded context
    "BoundedContext",
    # Context map
    "ContextMap",
    "ContextIntegration",
    # Registry
    "ContextRegistry",
    # Decorators
    "bounded_context",
    "context_aggregate",
    "context_service",
    "translate",
    # Factory functions
    "create_bounded_context",
    "create_context_map",
    "create_acl",
    "create_host_service",
    "create_shared_kernel",
    "create_published_language",
    "create_translator",
    "create_integration",
    "get_context",
    "get_context_map",
]
