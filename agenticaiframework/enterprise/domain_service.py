"""
Enterprise Domain Service Module.

Provides domain service patterns for cross-aggregate operations,
business logic orchestration, and domain invariant enforcement.

Example:
    # Define a domain service
    @domain_service
    class TransferService:
        async def transfer(
            self,
            from_account: Account,
            to_account: Account,
            amount: Money,
        ) -> TransferResult:
            from_account.withdraw(amount)
            to_account.deposit(amount)
            return TransferResult(success=True)
    
    # Use domain service
    service = create_domain_service(TransferService)
    result = await service.transfer(from_acc, to_acc, amount)
"""

from __future__ import annotations

import asyncio
import functools
import inspect
import logging
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
    Tuple,
    Type,
    TypeVar,
)

T = TypeVar('T')
S = TypeVar('S', bound='DomainServiceBase')


logger = logging.getLogger(__name__)


class DomainServiceError(Exception):
    """Domain service error."""
    pass


class ValidationError(DomainServiceError):
    """Validation error."""
    pass


class AuthorizationError(DomainServiceError):
    """Authorization error."""
    pass


class OperationError(DomainServiceError):
    """Operation error."""
    pass


class ServiceState(str, Enum):
    """Service state."""
    CREATED = "created"
    INITIALIZED = "initialized"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass
class ServiceContext:
    """Context for service execution."""
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None
    correlation_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ServiceResult(Generic[T]):
    """Result of a service operation."""
    success: bool
    value: Optional[T] = None
    error: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    execution_time_ms: float = 0.0
    
    @classmethod
    def ok(cls, value: T) -> "ServiceResult[T]":
        """Create success result."""
        return cls(success=True, value=value)
    
    @classmethod
    def fail(cls, error: str) -> "ServiceResult[T]":
        """Create failure result."""
        return cls(success=False, error=error)


@dataclass
class ServiceMetrics:
    """Service execution metrics."""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_time_ms: float = 0.0
    last_call_at: Optional[datetime] = None
    
    @property
    def success_rate(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.successful_calls / self.total_calls * 100
    
    @property
    def average_time_ms(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.total_time_ms / self.total_calls


class DomainServiceBase(ABC):
    """
    Base class for domain services.
    """
    
    def __init__(self):
        self._state = ServiceState.CREATED
        self._metrics = ServiceMetrics()
        self._validators: List[Callable] = []
        self._pre_hooks: List[Callable] = []
        self._post_hooks: List[Callable] = []
    
    @property
    def state(self) -> ServiceState:
        """Get service state."""
        return self._state
    
    @property
    def metrics(self) -> ServiceMetrics:
        """Get service metrics."""
        return self._metrics
    
    def add_validator(self, validator: Callable) -> None:
        """Add a validator."""
        self._validators.append(validator)
    
    def add_pre_hook(self, hook: Callable) -> None:
        """Add pre-execution hook."""
        self._pre_hooks.append(hook)
    
    def add_post_hook(self, hook: Callable) -> None:
        """Add post-execution hook."""
        self._post_hooks.append(hook)
    
    async def validate(self, *args: Any, **kwargs: Any) -> List[str]:
        """Run validators and return errors."""
        errors = []
        for validator in self._validators:
            try:
                if asyncio.iscoroutinefunction(validator):
                    result = await validator(*args, **kwargs)
                else:
                    result = validator(*args, **kwargs)
                
                if result is not True and result:
                    if isinstance(result, list):
                        errors.extend(result)
                    else:
                        errors.append(str(result))
            except Exception as e:
                errors.append(str(e))
        
        return errors
    
    async def _run_pre_hooks(
        self,
        context: ServiceContext,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Run pre-execution hooks."""
        for hook in self._pre_hooks:
            if asyncio.iscoroutinefunction(hook):
                await hook(context, *args, **kwargs)
            else:
                hook(context, *args, **kwargs)
    
    async def _run_post_hooks(
        self,
        context: ServiceContext,
        result: Any,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Run post-execution hooks."""
        for hook in self._post_hooks:
            if asyncio.iscoroutinefunction(hook):
                await hook(context, result, *args, **kwargs)
            else:
                hook(context, result, *args, **kwargs)
    
    def _record_call(
        self,
        success: bool,
        execution_time_ms: float,
    ) -> None:
        """Record a service call."""
        self._metrics.total_calls += 1
        self._metrics.total_time_ms += execution_time_ms
        self._metrics.last_call_at = datetime.now()
        
        if success:
            self._metrics.successful_calls += 1
        else:
            self._metrics.failed_calls += 1


class DomainService(DomainServiceBase):
    """
    Standard domain service.
    
    Example:
        class PaymentService(DomainService):
            async def process_payment(self, order: Order) -> PaymentResult:
                # Business logic here
                return PaymentResult(success=True)
    """
    
    async def execute(
        self,
        operation: str,
        context: Optional[ServiceContext] = None,
        *args: Any,
        **kwargs: Any,
    ) -> ServiceResult:
        """Execute a named operation."""
        context = context or ServiceContext()
        start_time = datetime.now()
        
        try:
            # Get the operation method
            method = getattr(self, operation, None)
            if not method:
                raise OperationError(f"Unknown operation: {operation}")
            
            # Validate
            errors = await self.validate(*args, **kwargs)
            if errors:
                raise ValidationError(", ".join(errors))
            
            # Pre-hooks
            await self._run_pre_hooks(context, *args, **kwargs)
            
            # Execute
            if asyncio.iscoroutinefunction(method):
                result = await method(*args, **kwargs)
            else:
                result = method(*args, **kwargs)
            
            # Post-hooks
            await self._run_post_hooks(context, result, *args, **kwargs)
            
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            self._record_call(True, execution_time)
            
            return ServiceResult.ok(result)
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            self._record_call(False, execution_time)
            
            logger.error(f"Service error: {e}")
            return ServiceResult.fail(str(e))


class SagaService(DomainServiceBase):
    """
    Saga pattern service for long-running transactions.
    
    Example:
        class OrderSaga(SagaService):
            async def create_order(self, data: dict) -> Order:
                # Step 1: Create order
                order = Order.create(data)
                self.add_compensation(self.cancel_order, order.id)
                
                # Step 2: Reserve inventory
                await self.reserve_inventory(order)
                self.add_compensation(self.release_inventory, order.id)
                
                # Step 3: Process payment
                await self.process_payment(order)
                
                return order
    """
    
    def __init__(self):
        super().__init__()
        self._compensations: List[Tuple[Callable, tuple, dict]] = []
    
    def add_compensation(
        self,
        action: Callable,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Add a compensation action."""
        self._compensations.append((action, args, kwargs))
    
    async def compensate(self) -> None:
        """Execute compensation actions in reverse order."""
        for action, args, kwargs in reversed(self._compensations):
            try:
                if asyncio.iscoroutinefunction(action):
                    await action(*args, **kwargs)
                else:
                    action(*args, **kwargs)
            except Exception as e:
                logger.error(f"Compensation failed: {e}")
        
        self._compensations.clear()
    
    async def execute_saga(
        self,
        operation: str,
        *args: Any,
        **kwargs: Any,
    ) -> ServiceResult:
        """Execute a saga operation with automatic compensation on failure."""
        self._compensations.clear()
        
        try:
            method = getattr(self, operation, None)
            if not method:
                raise OperationError(f"Unknown operation: {operation}")
            
            if asyncio.iscoroutinefunction(method):
                result = await method(*args, **kwargs)
            else:
                result = method(*args, **kwargs)
            
            return ServiceResult.ok(result)
            
        except Exception as e:
            logger.error(f"Saga failed, compensating: {e}")
            await self.compensate()
            return ServiceResult.fail(str(e))


class PolicyService(DomainServiceBase):
    """
    Policy-based domain service.
    
    Example:
        class DiscountPolicy(PolicyService):
            def apply_discount(self, order: Order) -> Order:
                for policy in self.get_policies():
                    if policy.applies_to(order):
                        order = policy.apply(order)
                return order
    """
    
    def __init__(self):
        super().__init__()
        self._policies: List[Any] = []
    
    def add_policy(self, policy: Any) -> None:
        """Add a policy."""
        self._policies.append(policy)
    
    def get_policies(self) -> List[Any]:
        """Get all policies."""
        return list(self._policies)
    
    def clear_policies(self) -> None:
        """Clear all policies."""
        self._policies.clear()


class SpecificationService(DomainServiceBase):
    """
    Specification-based domain service.
    
    Example:
        class OrderValidationService(SpecificationService):
            async def validate_order(self, order: Order) -> bool:
                return await self.check_all(order)
    """
    
    def __init__(self):
        super().__init__()
        self._specifications: Dict[str, Any] = {}
    
    def add_specification(
        self,
        name: str,
        specification: Any,
    ) -> None:
        """Add a specification."""
        self._specifications[name] = specification
    
    async def check(
        self,
        name: str,
        candidate: Any,
    ) -> bool:
        """Check a single specification."""
        spec = self._specifications.get(name)
        if not spec:
            return True
        
        return spec.is_satisfied_by(candidate)
    
    async def check_all(self, candidate: Any) -> bool:
        """Check all specifications."""
        for spec in self._specifications.values():
            if not spec.is_satisfied_by(candidate):
                return False
        return True
    
    async def get_violations(
        self,
        candidate: Any,
    ) -> List[str]:
        """Get all specification violations."""
        violations = []
        for name, spec in self._specifications.items():
            if not spec.is_satisfied_by(candidate):
                violations.append(name)
        return violations


class EventPublishingService(DomainServiceBase):
    """
    Domain service that publishes events.
    
    Example:
        class OrderService(EventPublishingService):
            async def create_order(self, data: dict) -> Order:
                order = Order.create(data)
                self.publish_event(OrderCreated(order.id))
                return order
    """
    
    def __init__(self, publisher: Optional[Callable] = None):
        super().__init__()
        self._publisher = publisher
        self._pending_events: List[Any] = []
    
    def set_publisher(self, publisher: Callable) -> None:
        """Set event publisher."""
        self._publisher = publisher
    
    def publish_event(self, event: Any) -> None:
        """Queue an event for publishing."""
        self._pending_events.append(event)
    
    async def flush_events(self) -> None:
        """Publish all pending events."""
        if not self._publisher:
            logger.warning("No event publisher configured")
            return
        
        for event in self._pending_events:
            if asyncio.iscoroutinefunction(self._publisher):
                await self._publisher(event)
            else:
                self._publisher(event)
        
        self._pending_events.clear()
    
    def get_pending_events(self) -> List[Any]:
        """Get pending events."""
        return list(self._pending_events)


class ServiceFactory(Generic[S]):
    """
    Factory for creating domain services.
    """
    
    def __init__(
        self,
        service_class: Type[S],
        dependencies: Optional[Dict[str, Any]] = None,
    ):
        self._service_class = service_class
        self._dependencies = dependencies or {}
    
    def create(self, **kwargs: Any) -> S:
        """Create a service instance."""
        all_deps = {**self._dependencies, **kwargs}
        return self._service_class(**all_deps)
    
    def with_dependency(
        self,
        name: str,
        dependency: Any,
    ) -> "ServiceFactory[S]":
        """Add a dependency."""
        deps = dict(self._dependencies)
        deps[name] = dependency
        return ServiceFactory(self._service_class, deps)


class ServiceLocator:
    """
    Service locator for domain services.
    """
    
    def __init__(self):
        self._services: Dict[Type, Any] = {}
        self._factories: Dict[Type, ServiceFactory] = {}
    
    def register(
        self,
        service_class: Type[S],
        instance: Optional[S] = None,
    ) -> None:
        """Register a service or factory."""
        if instance:
            self._services[service_class] = instance
        else:
            self._factories[service_class] = ServiceFactory(service_class)
    
    def register_factory(
        self,
        service_class: Type[S],
        factory: ServiceFactory[S],
    ) -> None:
        """Register a factory."""
        self._factories[service_class] = factory
    
    def get(self, service_class: Type[S]) -> S:
        """Get or create a service."""
        if service_class in self._services:
            return self._services[service_class]
        
        if service_class in self._factories:
            return self._factories[service_class].create()
        
        raise DomainServiceError(f"Service not registered: {service_class}")
    
    def resolve(self, service_class: Type[S]) -> S:
        """Resolve a service (alias for get)."""
        return self.get(service_class)


class ServiceRegistry:
    """
    Global registry for domain services.
    """
    
    def __init__(self):
        self._services: Dict[str, Type] = {}
        self._instances: Dict[str, Any] = {}
    
    def register(
        self,
        name: str,
        service_class: Type,
    ) -> None:
        """Register a service class."""
        self._services[name] = service_class
    
    def get_class(self, name: str) -> Optional[Type]:
        """Get a service class."""
        return self._services.get(name)
    
    def create(self, name: str, **kwargs: Any) -> Any:
        """Create a service instance."""
        service_class = self._services.get(name)
        if not service_class:
            raise DomainServiceError(f"Unknown service: {name}")
        return service_class(**kwargs)
    
    def get_or_create(self, name: str, **kwargs: Any) -> Any:
        """Get existing or create new instance."""
        if name not in self._instances:
            self._instances[name] = self.create(name, **kwargs)
        return self._instances[name]


# Global registry
_global_registry = ServiceRegistry()


# Decorators
def domain_service(cls: Type[S]) -> Type[S]:
    """
    Class decorator to mark as domain service.
    
    Example:
        @domain_service
        class PaymentService:
            async def process(self, payment: Payment) -> bool:
                ...
    """
    cls._is_domain_service = True
    _global_registry.register(cls.__name__, cls)
    return cls


def service_method(func: Callable) -> Callable:
    """
    Decorator to mark a method as service method with metrics.
    
    Example:
        class OrderService:
            @service_method
            async def create_order(self, data: dict) -> Order:
                ...
    """
    @functools.wraps(func)
    async def wrapper(self, *args, **kwargs):
        start = datetime.now()
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(self, *args, **kwargs)
            else:
                result = func(self, *args, **kwargs)
            
            if hasattr(self, '_record_call'):
                elapsed = (datetime.now() - start).total_seconds() * 1000
                self._record_call(True, elapsed)
            
            return result
        except Exception as e:
            if hasattr(self, '_record_call'):
                elapsed = (datetime.now() - start).total_seconds() * 1000
                self._record_call(False, elapsed)
            raise
    
    return wrapper


def validates(*validators: Callable) -> Callable:
    """
    Decorator to add validators to a service method.
    
    Example:
        class OrderService:
            @validates(validate_order_data, validate_customer)
            async def create_order(self, data: dict) -> Order:
                ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            errors = []
            for validator in validators:
                try:
                    if asyncio.iscoroutinefunction(validator):
                        result = await validator(*args, **kwargs)
                    else:
                        result = validator(*args, **kwargs)
                    
                    if result is not True and result:
                        if isinstance(result, list):
                            errors.extend(result)
                        else:
                            errors.append(str(result))
                except Exception as e:
                    errors.append(str(e))
            
            if errors:
                raise ValidationError(", ".join(errors))
            
            if asyncio.iscoroutinefunction(func):
                return await func(self, *args, **kwargs)
            return func(self, *args, **kwargs)
        
        return wrapper
    
    return decorator


def requires_authorization(permission: str) -> Callable:
    """
    Decorator to require authorization.
    
    Example:
        class OrderService:
            @requires_authorization("orders:create")
            async def create_order(self, data: dict) -> Order:
                ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(self, *args, context: Optional[ServiceContext] = None, **kwargs):
            # In real implementation, check authorization
            if context and not context.user_id:
                raise AuthorizationError(f"Authorization required: {permission}")
            
            if asyncio.iscoroutinefunction(func):
                return await func(self, *args, context=context, **kwargs)
            return func(self, *args, context=context, **kwargs)
        
        return wrapper
    
    return decorator


# Factory functions
def create_domain_service(
    service_class: Type[S],
    **dependencies: Any,
) -> S:
    """Create a domain service."""
    return service_class(**dependencies)


def create_service_factory(
    service_class: Type[S],
    dependencies: Optional[Dict[str, Any]] = None,
) -> ServiceFactory[S]:
    """Create a service factory."""
    return ServiceFactory(service_class, dependencies)


def create_service_locator() -> ServiceLocator:
    """Create a service locator."""
    return ServiceLocator()


def create_service_context(
    user_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    **metadata: Any,
) -> ServiceContext:
    """Create a service context."""
    return ServiceContext(
        user_id=user_id,
        tenant_id=tenant_id,
        metadata=metadata,
    )


def get_service(name: str, **kwargs: Any) -> Any:
    """Get service from global registry."""
    return _global_registry.get_or_create(name, **kwargs)


def register_service(
    name: str,
    service_class: Type,
) -> None:
    """Register service in global registry."""
    _global_registry.register(name, service_class)


__all__ = [
    # Exceptions
    "DomainServiceError",
    "ValidationError",
    "AuthorizationError",
    "OperationError",
    # Enums
    "ServiceState",
    # Data classes
    "ServiceContext",
    "ServiceResult",
    "ServiceMetrics",
    # Base classes
    "DomainServiceBase",
    "DomainService",
    "SagaService",
    "PolicyService",
    "SpecificationService",
    "EventPublishingService",
    # Factory and Locator
    "ServiceFactory",
    "ServiceLocator",
    "ServiceRegistry",
    # Decorators
    "domain_service",
    "service_method",
    "validates",
    "requires_authorization",
    # Factory functions
    "create_domain_service",
    "create_service_factory",
    "create_service_locator",
    "create_service_context",
    "get_service",
    "register_service",
]
