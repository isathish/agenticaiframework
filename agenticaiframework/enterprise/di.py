"""
Enterprise Dependency Injection - IoC container for agent components.

Provides automatic wiring of dependencies, scoped lifetimes, and 
easy testability through dependency injection.

Features:
- Constructor injection
- Decorator-based registration
- Scopes (singleton, transient, scoped)
- Factory functions
- Auto-wiring
- Named dependencies
"""

import asyncio
import functools
import inspect
import threading
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
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
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

T = TypeVar("T")


# =============================================================================
# Lifetimes
# =============================================================================

class Lifetime(Enum):
    """Dependency lifetime scopes."""
    TRANSIENT = "transient"      # New instance every time
    SINGLETON = "singleton"       # Single instance for container
    SCOPED = "scoped"            # One instance per scope


# =============================================================================
# Registration
# =============================================================================

@dataclass
class Registration:
    """A dependency registration."""
    service_type: Type
    implementation: Union[Type, Callable]
    lifetime: Lifetime
    name: Optional[str] = None
    factory: Optional[Callable] = None
    instance: Optional[Any] = None


# =============================================================================
# Container
# =============================================================================

class Container:
    """
    Dependency injection container.
    
    Usage:
        >>> container = Container()
        >>> 
        >>> @container.register(Lifetime.SINGLETON)
        >>> class ConfigService:
        ...     def __init__(self):
        ...         self.debug = True
        >>> 
        >>> @container.register(Lifetime.TRANSIENT)
        >>> class AgentService:
        ...     def __init__(self, config: ConfigService):
        ...         self.config = config
        >>> 
        >>> agent = container.resolve(AgentService)
    """
    
    def __init__(self, parent: Optional["Container"] = None):
        self._registrations: Dict[str, Registration] = {}
        self._singletons: Dict[str, Any] = {}
        self._parent = parent
        self._lock = threading.RLock()
    
    def _get_key(self, service_type: Type, name: Optional[str] = None) -> str:
        """Get registration key."""
        type_name = f"{service_type.__module__}.{service_type.__qualname__}"
        if name:
            return f"{type_name}:{name}"
        return type_name
    
    def register(
        self,
        lifetime: Lifetime = Lifetime.TRANSIENT,
        name: Optional[str] = None,
        interface: Optional[Type] = None,
    ):
        """
        Decorator to register a class.
        
        Args:
            lifetime: Dependency lifetime
            name: Optional name for multiple implementations
            interface: Optional interface type to register as
        """
        def decorator(cls: Type[T]) -> Type[T]:
            service_type = interface or cls
            key = self._get_key(service_type, name)
            
            with self._lock:
                self._registrations[key] = Registration(
                    service_type=service_type,
                    implementation=cls,
                    lifetime=lifetime,
                    name=name,
                )
            
            return cls
        return decorator
    
    def register_instance(
        self,
        service_type: Type[T],
        instance: T,
        name: Optional[str] = None,
    ):
        """Register an existing instance as singleton."""
        key = self._get_key(service_type, name)
        
        with self._lock:
            self._registrations[key] = Registration(
                service_type=service_type,
                implementation=type(instance),
                lifetime=Lifetime.SINGLETON,
                name=name,
                instance=instance,
            )
            self._singletons[key] = instance
    
    def register_factory(
        self,
        service_type: Type[T],
        factory: Callable[..., T],
        lifetime: Lifetime = Lifetime.TRANSIENT,
        name: Optional[str] = None,
    ):
        """Register a factory function."""
        key = self._get_key(service_type, name)
        
        with self._lock:
            self._registrations[key] = Registration(
                service_type=service_type,
                implementation=factory,
                lifetime=lifetime,
                name=name,
                factory=factory,
            )
    
    def register_type(
        self,
        service_type: Type,
        implementation: Type,
        lifetime: Lifetime = Lifetime.TRANSIENT,
        name: Optional[str] = None,
    ):
        """Register an implementation for an interface."""
        key = self._get_key(service_type, name)
        
        with self._lock:
            self._registrations[key] = Registration(
                service_type=service_type,
                implementation=implementation,
                lifetime=lifetime,
                name=name,
            )
    
    def resolve(
        self,
        service_type: Type[T],
        name: Optional[str] = None,
    ) -> T:
        """
        Resolve a dependency.
        
        Args:
            service_type: Type to resolve
            name: Optional name for named dependencies
            
        Returns:
            Instance of the requested type
        """
        key = self._get_key(service_type, name)
        
        # Check for existing singleton
        if key in self._singletons:
            return self._singletons[key]
        
        # Check parent
        if self._parent and key not in self._registrations:
            return self._parent.resolve(service_type, name)
        
        # Get registration
        registration = self._registrations.get(key)
        
        if not registration:
            # Try auto-registration
            if inspect.isclass(service_type) and not inspect.isabstract(service_type):
                self.register_type(service_type, service_type, Lifetime.TRANSIENT)
                registration = self._registrations[key]
            else:
                raise DependencyError(f"No registration for {service_type.__name__}")
        
        return self._create_instance(registration)
    
    def _create_instance(self, registration: Registration) -> Any:
        """Create an instance from a registration."""
        key = self._get_key(registration.service_type, registration.name)
        
        # Return existing singleton
        if registration.lifetime == Lifetime.SINGLETON:
            if registration.instance:
                self._singletons[key] = registration.instance
                return registration.instance
            
            if key in self._singletons:
                return self._singletons[key]
        
        # Use factory if provided
        if registration.factory:
            deps = self._resolve_dependencies(registration.factory)
            instance = registration.factory(**deps)
        else:
            # Create via constructor
            impl = registration.implementation
            deps = self._resolve_dependencies(impl)
            instance = impl(**deps)
        
        # Store singleton
        if registration.lifetime == Lifetime.SINGLETON:
            with self._lock:
                self._singletons[key] = instance
        
        return instance
    
    def _resolve_dependencies(
        self,
        target: Union[Type, Callable],
    ) -> Dict[str, Any]:
        """Resolve constructor/function dependencies."""
        deps = {}
        
        try:
            hints = get_type_hints(target)
        except Exception:
            hints = {}
        
        sig = inspect.signature(target)
        
        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue
            
            if param_name in hints:
                param_type = hints[param_name]
                
                # Handle Optional types
                origin = get_origin(param_type)
                if origin is Union:
                    args = get_args(param_type)
                    non_none = [a for a in args if a is not type(None)]
                    if non_none:
                        param_type = non_none[0]
                
                # Try to resolve
                try:
                    deps[param_name] = self.resolve(param_type)
                except DependencyError:
                    if param.default is param.empty:
                        raise
        
        return deps
    
    def create_scope(self) -> "Scope":
        """Create a new dependency scope."""
        return Scope(self)
    
    def get_all(self, service_type: Type[T]) -> List[T]:
        """Get all implementations of a type."""
        instances = []
        type_name = f"{service_type.__module__}.{service_type.__qualname__}"
        
        for key, reg in self._registrations.items():
            if key.startswith(type_name):
                instances.append(self._create_instance(reg))
        
        return instances
    
    def is_registered(
        self,
        service_type: Type,
        name: Optional[str] = None,
    ) -> bool:
        """Check if a type is registered."""
        key = self._get_key(service_type, name)
        return key in self._registrations


class Scope:
    """
    A dependency scope for scoped lifetimes.
    
    Usage:
        >>> with container.create_scope() as scope:
        ...     db = scope.resolve(DatabaseConnection)
        ...     # Same instance within scope
    """
    
    def __init__(self, container: Container):
        self._container = container
        self._scoped: Dict[str, Any] = {}
    
    def __enter__(self) -> "Scope":
        return self
    
    def __exit__(self, *args):
        self._dispose()
    
    async def __aenter__(self) -> "Scope":
        return self
    
    async def __aexit__(self, *args):
        self._dispose()
    
    def resolve(
        self,
        service_type: Type[T],
        name: Optional[str] = None,
    ) -> T:
        """Resolve a dependency within this scope."""
        key = self._container._get_key(service_type, name)
        
        # Check scoped cache
        if key in self._scoped:
            return self._scoped[key]
        
        # Get registration
        registration = self._container._registrations.get(key)
        
        if registration and registration.lifetime == Lifetime.SCOPED:
            instance = self._container._create_instance(registration)
            self._scoped[key] = instance
            return instance
        
        return self._container.resolve(service_type, name)
    
    def _dispose(self):
        """Dispose scoped instances."""
        for instance in self._scoped.values():
            if hasattr(instance, "dispose"):
                instance.dispose()
            elif hasattr(instance, "close"):
                instance.close()
        self._scoped.clear()


# =============================================================================
# Decorators
# =============================================================================

def inject(fn: Callable) -> Callable:
    """
    Decorator to inject dependencies into a function.
    
    Usage:
        >>> @inject
        >>> def process(config: ConfigService, data: str):
        ...     return config.process(data)
    """
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        container = get_container()
        deps = container._resolve_dependencies(fn)
        
        # Don't override explicit args
        for key in list(deps.keys()):
            if key in kwargs:
                del deps[key]
        
        return fn(*args, **deps, **kwargs)
    
    return wrapper


def inject_async(fn: Callable) -> Callable:
    """Async version of inject decorator."""
    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        container = get_container()
        deps = container._resolve_dependencies(fn)
        
        for key in list(deps.keys()):
            if key in kwargs:
                del deps[key]
        
        return await fn(*args, **deps, **kwargs)
    
    return wrapper


# =============================================================================
# Service Provider Interface
# =============================================================================

class ServiceProvider(ABC):
    """Base class for service providers."""
    
    @abstractmethod
    def register(self, container: Container):
        """Register services in the container."""
        pass


class ServiceCollection:
    """
    Builder for configuring services.
    
    Usage:
        >>> services = ServiceCollection()
        >>> services.add_singleton(ConfigService)
        >>> services.add_transient(AgentService)
        >>> container = services.build()
    """
    
    def __init__(self):
        self._registrations: List[tuple] = []
    
    def add_singleton(
        self,
        service_type: Type[T],
        implementation: Optional[Type[T]] = None,
        name: Optional[str] = None,
    ) -> "ServiceCollection":
        """Add a singleton service."""
        self._registrations.append((
            service_type,
            implementation or service_type,
            Lifetime.SINGLETON,
            name,
        ))
        return self
    
    def add_transient(
        self,
        service_type: Type[T],
        implementation: Optional[Type[T]] = None,
        name: Optional[str] = None,
    ) -> "ServiceCollection":
        """Add a transient service."""
        self._registrations.append((
            service_type,
            implementation or service_type,
            Lifetime.TRANSIENT,
            name,
        ))
        return self
    
    def add_scoped(
        self,
        service_type: Type[T],
        implementation: Optional[Type[T]] = None,
        name: Optional[str] = None,
    ) -> "ServiceCollection":
        """Add a scoped service."""
        self._registrations.append((
            service_type,
            implementation or service_type,
            Lifetime.SCOPED,
            name,
        ))
        return self
    
    def add_factory(
        self,
        service_type: Type[T],
        factory: Callable[..., T],
        lifetime: Lifetime = Lifetime.TRANSIENT,
        name: Optional[str] = None,
    ) -> "ServiceCollection":
        """Add a factory registration."""
        self._registrations.append((
            service_type,
            factory,
            lifetime,
            name,
            True,  # is_factory
        ))
        return self
    
    def add_instance(
        self,
        service_type: Type[T],
        instance: T,
        name: Optional[str] = None,
    ) -> "ServiceCollection":
        """Add an existing instance."""
        self._registrations.append((
            service_type,
            instance,
            Lifetime.SINGLETON,
            name,
            False,  # is_factory
            True,   # is_instance
        ))
        return self
    
    def add_provider(self, provider: ServiceProvider) -> "ServiceCollection":
        """Add a service provider."""
        self._registrations.append(("provider", provider))
        return self
    
    def build(self) -> Container:
        """Build the container from registrations."""
        container = Container()
        
        for reg in self._registrations:
            if reg[0] == "provider":
                reg[1].register(container)
            elif len(reg) > 5 and reg[5]:  # is_instance
                container.register_instance(reg[0], reg[1], reg[3])
            elif len(reg) > 4 and reg[4]:  # is_factory
                container.register_factory(reg[0], reg[1], reg[2], reg[3])
            else:
                container.register_type(reg[0], reg[1], reg[2], reg[3])
        
        return container


# =============================================================================
# Errors
# =============================================================================

class DependencyError(Exception):
    """Error resolving dependency."""
    pass


# =============================================================================
# Global Container
# =============================================================================

_global_container: Optional[Container] = None
_lock = threading.Lock()


def get_container() -> Container:
    """Get the global container."""
    global _global_container
    
    if _global_container is None:
        with _lock:
            if _global_container is None:
                _global_container = Container()
    
    return _global_container


def set_container(container: Container):
    """Set the global container."""
    global _global_container
    _global_container = container


def reset_container():
    """Reset the global container."""
    global _global_container
    _global_container = None


# Convenience functions
def singleton(name: Optional[str] = None, interface: Optional[Type] = None):
    """Register as singleton in global container."""
    return get_container().register(Lifetime.SINGLETON, name, interface)


def transient(name: Optional[str] = None, interface: Optional[Type] = None):
    """Register as transient in global container."""
    return get_container().register(Lifetime.TRANSIENT, name, interface)


def scoped(name: Optional[str] = None, interface: Optional[Type] = None):
    """Register as scoped in global container."""
    return get_container().register(Lifetime.SCOPED, name, interface)


def resolve(service_type: Type[T], name: Optional[str] = None) -> T:
    """Resolve from global container."""
    return get_container().resolve(service_type, name)


# =============================================================================
# Pre-built Service Providers
# =============================================================================

class CoreServicesProvider(ServiceProvider):
    """Core framework services."""
    
    def register(self, container: Container):
        from ..config import ConfigManager
        from ..monitoring import MonitoringManager
        
        container.register_type(ConfigManager, ConfigManager, Lifetime.SINGLETON)
        container.register_type(MonitoringManager, MonitoringManager, Lifetime.SINGLETON)


class LLMServicesProvider(ServiceProvider):
    """LLM-related services."""
    
    def __init__(self, model: str = "gpt-4o"):
        self.model = model
    
    def register(self, container: Container):
        # Register LLM factory
        container.register_factory(
            type(None),  # Will be replaced with actual LLM interface
            lambda: self._create_llm(),
            Lifetime.SINGLETON,
            "llm",
        )
    
    def _create_llm(self):
        from ..llms import create_llm
        return create_llm(self.model)


# =============================================================================
# Context Manager Integration
# =============================================================================

@contextmanager
def scope():
    """Context manager for dependency scope."""
    container = get_container()
    with container.create_scope() as s:
        yield s


@asynccontextmanager
async def async_scope():
    """Async context manager for dependency scope."""
    container = get_container()
    async with container.create_scope() as s:
        yield s
