"""
Enterprise Multi-Tenancy Module.

Provides tenant isolation, context management, and tenant-aware
operations for multi-tenant applications.

Example:
    # Create tenant manager
    manager = create_tenant_manager()
    
    # Set tenant context
    with tenant_context("tenant_123"):
        # All operations scoped to tenant_123
        data = await fetch_data()
    
    # Tenant isolation decorator
    @tenant_isolated
    async def process_data(data: dict):
        tenant_id = get_current_tenant()
        ...
    
    # Tenant-aware repository
    repo = TenantAwareRepository(base_repo)
    items = await repo.find_all()  # Automatically filtered
"""

from __future__ import annotations

import asyncio
import logging
import threading
import uuid
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timedelta
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
    TypeVar,
    Union,
)

logger = logging.getLogger(__name__)

T = TypeVar('T')


class TenantError(Exception):
    """Tenant error."""
    pass


class TenantNotFoundError(TenantError):
    """Tenant not found."""
    pass


class TenantContextError(TenantError):
    """Tenant context error."""
    pass


class TenantIsolationError(TenantError):
    """Tenant isolation violation."""
    pass


class TenantStatus(str, Enum):
    """Tenant status."""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    PENDING = "pending"
    DELETED = "deleted"


class IsolationLevel(str, Enum):
    """Isolation levels."""
    SHARED = "shared"  # Shared resources with tenant column
    SCHEMA = "schema"  # Separate schema per tenant
    DATABASE = "database"  # Separate database per tenant


# Context variable for current tenant
_current_tenant: ContextVar[Optional[str]] = ContextVar(
    'current_tenant',
    default=None,
)


@dataclass
class Tenant:
    """Tenant entity."""
    id: str
    name: str
    status: TenantStatus = TenantStatus.ACTIVE
    plan: str = "free"
    metadata: Dict[str, Any] = field(default_factory=dict)
    settings: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
    
    # Limits and quotas
    max_users: int = 10
    max_storage_mb: int = 1000
    max_api_calls_per_hour: int = 1000
    
    # Isolation
    isolation_level: IsolationLevel = IsolationLevel.SHARED
    database_name: Optional[str] = None
    schema_name: Optional[str] = None


@dataclass
class TenantContext:
    """Tenant context with additional info."""
    tenant_id: str
    tenant: Optional[Tenant] = None
    user_id: Optional[str] = None
    roles: List[str] = field(default_factory=list)
    permissions: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TenantUsage:
    """Tenant usage statistics."""
    tenant_id: str
    users_count: int = 0
    storage_used_mb: float = 0.0
    api_calls_count: int = 0
    api_calls_window_start: datetime = field(default_factory=datetime.now)
    last_activity: Optional[datetime] = None


# Context management functions
def get_current_tenant() -> Optional[str]:
    """Get current tenant ID from context."""
    return _current_tenant.get()


def get_current_tenant_required() -> str:
    """Get current tenant ID, raise if not set."""
    tenant_id = _current_tenant.get()
    if not tenant_id:
        raise TenantContextError("No tenant in current context")
    return tenant_id


def set_current_tenant(tenant_id: Optional[str]) -> None:
    """Set current tenant ID."""
    _current_tenant.set(tenant_id)


@contextmanager
def tenant_context(tenant_id: str):
    """
    Context manager for tenant scope.
    
    Example:
        with tenant_context("tenant_123"):
            # All operations scoped to tenant
            ...
    """
    token = _current_tenant.set(tenant_id)
    try:
        yield tenant_id
    finally:
        _current_tenant.reset(token)


@asynccontextmanager
async def async_tenant_context(tenant_id: str):
    """Async context manager for tenant scope."""
    token = _current_tenant.set(tenant_id)
    try:
        yield tenant_id
    finally:
        _current_tenant.reset(token)


class TenantStore(ABC):
    """Abstract tenant store."""
    
    @abstractmethod
    async def get(self, tenant_id: str) -> Optional[Tenant]:
        """Get tenant by ID."""
        pass
    
    @abstractmethod
    async def create(self, tenant: Tenant) -> Tenant:
        """Create a tenant."""
        pass
    
    @abstractmethod
    async def update(self, tenant: Tenant) -> Tenant:
        """Update a tenant."""
        pass
    
    @abstractmethod
    async def delete(self, tenant_id: str) -> bool:
        """Delete a tenant."""
        pass
    
    @abstractmethod
    async def list_all(
        self,
        status: Optional[TenantStatus] = None,
    ) -> List[Tenant]:
        """List all tenants."""
        pass


class InMemoryTenantStore(TenantStore):
    """In-memory tenant store."""
    
    def __init__(self):
        self._tenants: Dict[str, Tenant] = {}
        self._lock = asyncio.Lock()
    
    async def get(self, tenant_id: str) -> Optional[Tenant]:
        return self._tenants.get(tenant_id)
    
    async def create(self, tenant: Tenant) -> Tenant:
        async with self._lock:
            if tenant.id in self._tenants:
                raise TenantError(f"Tenant already exists: {tenant.id}")
            self._tenants[tenant.id] = tenant
            return tenant
    
    async def update(self, tenant: Tenant) -> Tenant:
        async with self._lock:
            if tenant.id not in self._tenants:
                raise TenantNotFoundError(f"Tenant not found: {tenant.id}")
            tenant.updated_at = datetime.now()
            self._tenants[tenant.id] = tenant
            return tenant
    
    async def delete(self, tenant_id: str) -> bool:
        async with self._lock:
            return self._tenants.pop(tenant_id, None) is not None
    
    async def list_all(
        self,
        status: Optional[TenantStatus] = None,
    ) -> List[Tenant]:
        tenants = list(self._tenants.values())
        if status:
            tenants = [t for t in tenants if t.status == status]
        return tenants


class TenantManager:
    """
    Tenant lifecycle manager.
    """
    
    def __init__(
        self,
        store: TenantStore,
    ):
        self._store = store
        self._cache: Dict[str, Tenant] = {}
        self._usage: Dict[str, TenantUsage] = {}
    
    async def create_tenant(
        self,
        name: str,
        plan: str = "free",
        **kwargs: Any,
    ) -> Tenant:
        """Create a new tenant."""
        tenant = Tenant(
            id=str(uuid.uuid4()),
            name=name,
            plan=plan,
            **kwargs,
        )
        
        await self._store.create(tenant)
        self._cache[tenant.id] = tenant
        self._usage[tenant.id] = TenantUsage(tenant_id=tenant.id)
        
        logger.info(f"Created tenant: {tenant.name} ({tenant.id})")
        
        return tenant
    
    async def get_tenant(
        self,
        tenant_id: str,
        use_cache: bool = True,
    ) -> Optional[Tenant]:
        """Get tenant by ID."""
        if use_cache and tenant_id in self._cache:
            return self._cache[tenant_id]
        
        tenant = await self._store.get(tenant_id)
        
        if tenant:
            self._cache[tenant_id] = tenant
        
        return tenant
    
    async def get_tenant_required(self, tenant_id: str) -> Tenant:
        """Get tenant, raise if not found."""
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            raise TenantNotFoundError(f"Tenant not found: {tenant_id}")
        return tenant
    
    async def update_tenant(
        self,
        tenant_id: str,
        **updates: Any,
    ) -> Tenant:
        """Update tenant properties."""
        tenant = await self.get_tenant_required(tenant_id)
        
        for key, value in updates.items():
            if hasattr(tenant, key):
                setattr(tenant, key, value)
        
        tenant = await self._store.update(tenant)
        self._cache[tenant_id] = tenant
        
        return tenant
    
    async def suspend_tenant(self, tenant_id: str) -> Tenant:
        """Suspend a tenant."""
        return await self.update_tenant(
            tenant_id,
            status=TenantStatus.SUSPENDED,
        )
    
    async def activate_tenant(self, tenant_id: str) -> Tenant:
        """Activate a tenant."""
        return await self.update_tenant(
            tenant_id,
            status=TenantStatus.ACTIVE,
        )
    
    async def delete_tenant(
        self,
        tenant_id: str,
        soft: bool = True,
    ) -> bool:
        """Delete a tenant."""
        if soft:
            await self.update_tenant(
                tenant_id,
                status=TenantStatus.DELETED,
            )
            return True
        
        self._cache.pop(tenant_id, None)
        self._usage.pop(tenant_id, None)
        
        return await self._store.delete(tenant_id)
    
    async def is_active(self, tenant_id: str) -> bool:
        """Check if tenant is active."""
        tenant = await self.get_tenant(tenant_id)
        return tenant is not None and tenant.status == TenantStatus.ACTIVE
    
    async def get_usage(self, tenant_id: str) -> TenantUsage:
        """Get tenant usage."""
        if tenant_id not in self._usage:
            self._usage[tenant_id] = TenantUsage(tenant_id=tenant_id)
        return self._usage[tenant_id]
    
    async def check_quota(
        self,
        tenant_id: str,
        resource: str,
        amount: int = 1,
    ) -> bool:
        """Check if tenant has quota for resource."""
        tenant = await self.get_tenant_required(tenant_id)
        usage = await self.get_usage(tenant_id)
        
        if resource == "api_calls":
            # Reset window if needed
            window_duration = timedelta(hours=1)
            if datetime.now() - usage.api_calls_window_start > window_duration:
                usage.api_calls_count = 0
                usage.api_calls_window_start = datetime.now()
            
            return (usage.api_calls_count + amount) <= tenant.max_api_calls_per_hour
        
        elif resource == "storage":
            return (usage.storage_used_mb + amount) <= tenant.max_storage_mb
        
        elif resource == "users":
            return (usage.users_count + amount) <= tenant.max_users
        
        return True
    
    async def record_usage(
        self,
        tenant_id: str,
        resource: str,
        amount: int = 1,
    ) -> None:
        """Record resource usage."""
        usage = await self.get_usage(tenant_id)
        usage.last_activity = datetime.now()
        
        if resource == "api_calls":
            usage.api_calls_count += amount
        elif resource == "storage":
            usage.storage_used_mb += amount
        elif resource == "users":
            usage.users_count += amount


class TenantResolver:
    """
    Resolve tenant from various sources.
    """
    
    def __init__(
        self,
        manager: TenantManager,
        header_name: str = "X-Tenant-ID",
        query_param: str = "tenant_id",
    ):
        self._manager = manager
        self._header_name = header_name
        self._query_param = query_param
    
    async def resolve_from_header(
        self,
        headers: Dict[str, str],
    ) -> Optional[str]:
        """Resolve tenant from request headers."""
        tenant_id = headers.get(self._header_name)
        
        if tenant_id:
            if await self._manager.is_active(tenant_id):
                return tenant_id
        
        return None
    
    async def resolve_from_token(
        self,
        token_payload: Dict[str, Any],
    ) -> Optional[str]:
        """Resolve tenant from JWT token."""
        tenant_id = token_payload.get("tenant_id")
        
        if tenant_id:
            if await self._manager.is_active(tenant_id):
                return tenant_id
        
        return None
    
    async def resolve_from_domain(
        self,
        domain: str,
    ) -> Optional[str]:
        """Resolve tenant from subdomain."""
        # Extract subdomain
        parts = domain.split(".")
        if len(parts) >= 3:
            subdomain = parts[0]
            
            # Look up tenant by subdomain
            tenants = await self._manager._store.list_all(TenantStatus.ACTIVE)
            
            for tenant in tenants:
                if tenant.metadata.get("subdomain") == subdomain:
                    return tenant.id
        
        return None


class TenantAwareRepository(Generic[T]):
    """
    Wrapper to make repositories tenant-aware.
    """
    
    def __init__(
        self,
        repository: Any,
        tenant_field: str = "tenant_id",
    ):
        self._repository = repository
        self._tenant_field = tenant_field
    
    def _inject_tenant(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Inject tenant ID into kwargs."""
        tenant_id = get_current_tenant()
        if tenant_id:
            kwargs[self._tenant_field] = tenant_id
        return kwargs
    
    def _validate_tenant(self, item: Any) -> None:
        """Validate item belongs to current tenant."""
        tenant_id = get_current_tenant()
        if not tenant_id:
            return
        
        item_tenant = getattr(item, self._tenant_field, None)
        if item_tenant and item_tenant != tenant_id:
            raise TenantIsolationError(
                f"Item belongs to different tenant: {item_tenant}"
            )
    
    async def find_all(self, **kwargs: Any) -> List[T]:
        """Find all items for current tenant."""
        kwargs = self._inject_tenant(kwargs)
        return await self._repository.find_all(**kwargs)
    
    async def find_by_id(self, id: Any, **kwargs: Any) -> Optional[T]:
        """Find item by ID with tenant validation."""
        item = await self._repository.find_by_id(id, **kwargs)
        if item:
            self._validate_tenant(item)
        return item
    
    async def create(self, item: T, **kwargs: Any) -> T:
        """Create item with tenant ID."""
        tenant_id = get_current_tenant()
        if tenant_id:
            setattr(item, self._tenant_field, tenant_id)
        return await self._repository.create(item, **kwargs)
    
    async def update(self, item: T, **kwargs: Any) -> T:
        """Update item with tenant validation."""
        self._validate_tenant(item)
        return await self._repository.update(item, **kwargs)
    
    async def delete(self, id: Any, **kwargs: Any) -> bool:
        """Delete item with tenant validation."""
        item = await self.find_by_id(id)
        if item:
            self._validate_tenant(item)
            return await self._repository.delete(id, **kwargs)
        return False


class TenantMiddleware:
    """
    Middleware for tenant context injection.
    """
    
    def __init__(
        self,
        resolver: TenantResolver,
        required: bool = True,
    ):
        self._resolver = resolver
        self._required = required
    
    async def __call__(
        self,
        request: Any,
        call_next: Callable,
    ) -> Any:
        """Process request with tenant context."""
        # Try to resolve tenant
        tenant_id = await self._resolver.resolve_from_header(
            dict(request.headers)
        )
        
        if not tenant_id and self._required:
            raise TenantContextError("Tenant ID required")
        
        # Set tenant context
        if tenant_id:
            async with async_tenant_context(tenant_id):
                return await call_next(request)
        
        return await call_next(request)


# Decorators
def tenant_isolated(
    require_tenant: bool = True,
) -> Callable:
    """
    Decorator to ensure function runs in tenant context.
    
    Example:
        @tenant_isolated()
        async def process_order(order_id: str):
            tenant_id = get_current_tenant()
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            tenant_id = get_current_tenant()
            
            if require_tenant and not tenant_id:
                raise TenantContextError(
                    f"Tenant context required for {func.__name__}"
                )
            
            return await func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            tenant_id = get_current_tenant()
            
            if require_tenant and not tenant_id:
                raise TenantContextError(
                    f"Tenant context required for {func.__name__}"
                )
            
            return func(*args, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


def with_tenant(tenant_id: str) -> Callable:
    """
    Decorator to run function with specific tenant.
    
    Example:
        @with_tenant("tenant_123")
        async def admin_operation():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            async with async_tenant_context(tenant_id):
                return await func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            with tenant_context(tenant_id):
                return func(*args, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


def check_tenant_quota(
    resource: str,
    amount: int = 1,
) -> Callable:
    """
    Decorator to check tenant quota before execution.
    
    Example:
        @check_tenant_quota("api_calls")
        async def make_api_call():
            ...
    """
    def decorator(func: Callable) -> Callable:
        _manager: Optional[TenantManager] = None
        
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            nonlocal _manager
            
            tenant_id = get_current_tenant_required()
            
            if _manager is None:
                _manager = TenantManager(InMemoryTenantStore())
            
            if not await _manager.check_quota(tenant_id, resource, amount):
                raise TenantError(
                    f"Quota exceeded for {resource}"
                )
            
            result = await func(*args, **kwargs)
            
            await _manager.record_usage(tenant_id, resource, amount)
            
            return result
        
        return wrapper
    
    return decorator


# Factory functions
def create_tenant_manager(
    store: Optional[TenantStore] = None,
) -> TenantManager:
    """Create a tenant manager."""
    s = store or InMemoryTenantStore()
    return TenantManager(s)


def create_tenant_resolver(
    manager: TenantManager,
    header_name: str = "X-Tenant-ID",
) -> TenantResolver:
    """Create a tenant resolver."""
    return TenantResolver(manager, header_name)


def create_tenant_aware_repository(
    repository: Any,
    tenant_field: str = "tenant_id",
) -> TenantAwareRepository:
    """Create a tenant-aware repository wrapper."""
    return TenantAwareRepository(repository, tenant_field)


__all__ = [
    # Exceptions
    "TenantError",
    "TenantNotFoundError",
    "TenantContextError",
    "TenantIsolationError",
    # Enums
    "TenantStatus",
    "IsolationLevel",
    # Data classes
    "Tenant",
    "TenantContext",
    "TenantUsage",
    # Context functions
    "get_current_tenant",
    "get_current_tenant_required",
    "set_current_tenant",
    "tenant_context",
    "async_tenant_context",
    # Core classes
    "TenantStore",
    "InMemoryTenantStore",
    "TenantManager",
    "TenantResolver",
    "TenantAwareRepository",
    "TenantMiddleware",
    # Decorators
    "tenant_isolated",
    "with_tenant",
    "check_tenant_quota",
    # Factory functions
    "create_tenant_manager",
    "create_tenant_resolver",
    "create_tenant_aware_repository",
]
