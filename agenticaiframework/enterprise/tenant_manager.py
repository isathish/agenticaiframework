"""
Enterprise Tenant Manager Module.

Provides multi-tenancy, tenant isolation, data partitioning,
tenant-aware operations, and resource quotas.

Example:
    # Create tenant manager
    tenants = create_tenant_manager()
    
    # Register tenant
    tenant = await tenants.create("acme-corp", TenantConfig(
        name="Acme Corporation",
        tier=TenantTier.ENTERPRISE,
    ))
    
    # Use tenant context
    async with tenants.tenant_context("acme-corp"):
        data = await repository.get_all()  # Automatically filtered
    
    # Use decorator
    @tenant_aware
    async def get_orders(tenant_id: str):
        ...
"""

from __future__ import annotations

import asyncio
import contextvars
import functools
import logging
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
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
)

T = TypeVar('T')


logger = logging.getLogger(__name__)


# Context variable for current tenant
_current_tenant: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    'current_tenant', default=None
)


class TenantError(Exception):
    """Base tenant error."""
    pass


class TenantNotFoundError(TenantError):
    """Tenant not found."""
    pass


class TenantQuotaExceededError(TenantError):
    """Tenant quota exceeded."""
    pass


class TenantSuspendedError(TenantError):
    """Tenant is suspended."""
    pass


class TenantTier(str, Enum):
    """Tenant tier levels."""
    FREE = "free"
    BASIC = "basic"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class TenantStatus(str, Enum):
    """Tenant status."""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    PENDING = "pending"
    DELETED = "deleted"


class IsolationLevel(str, Enum):
    """Data isolation level."""
    SHARED = "shared"  # Shared tables with tenant_id column
    SCHEMA = "schema"  # Separate schemas per tenant
    DATABASE = "database"  # Separate databases per tenant


@dataclass
class ResourceQuota:
    """Resource quota configuration."""
    max_users: int = 100
    max_storage_mb: int = 1000
    max_api_calls_per_day: int = 10000
    max_concurrent_connections: int = 10
    custom_limits: Dict[str, int] = field(default_factory=dict)


@dataclass
class TenantConfig:
    """Tenant configuration."""
    name: str
    tier: TenantTier = TenantTier.FREE
    quota: ResourceQuota = field(default_factory=ResourceQuota)
    isolation_level: IsolationLevel = IsolationLevel.SHARED
    settings: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TenantUsage:
    """Tenant resource usage."""
    users: int = 0
    storage_mb: float = 0.0
    api_calls_today: int = 0
    concurrent_connections: int = 0
    custom_usage: Dict[str, int] = field(default_factory=dict)
    last_updated: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Tenant:
    """Tenant entity."""
    id: str
    config: TenantConfig
    status: TenantStatus = TenantStatus.ACTIVE
    usage: TenantUsage = field(default_factory=TenantUsage)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    suspended_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    
    @property
    def name(self) -> str:
        return self.config.name
    
    @property
    def tier(self) -> TenantTier:
        return self.config.tier
    
    @property
    def is_active(self) -> bool:
        return self.status == TenantStatus.ACTIVE


class TenantStore(ABC):
    """Abstract tenant store."""
    
    @abstractmethod
    async def get(self, tenant_id: str) -> Optional[Tenant]:
        """Get tenant by ID."""
        pass
    
    @abstractmethod
    async def save(self, tenant: Tenant) -> None:
        """Save tenant."""
        pass
    
    @abstractmethod
    async def delete(self, tenant_id: str) -> None:
        """Delete tenant."""
        pass
    
    @abstractmethod
    async def list(
        self,
        status: Optional[TenantStatus] = None,
        tier: Optional[TenantTier] = None,
    ) -> List[Tenant]:
        """List tenants."""
        pass
    
    @abstractmethod
    async def exists(self, tenant_id: str) -> bool:
        """Check if tenant exists."""
        pass


class InMemoryTenantStore(TenantStore):
    """In-memory tenant store."""
    
    def __init__(self):
        self._tenants: Dict[str, Tenant] = {}
        self._lock = threading.Lock()
    
    async def get(self, tenant_id: str) -> Optional[Tenant]:
        with self._lock:
            return self._tenants.get(tenant_id)
    
    async def save(self, tenant: Tenant) -> None:
        with self._lock:
            tenant.updated_at = datetime.utcnow()
            self._tenants[tenant.id] = tenant
    
    async def delete(self, tenant_id: str) -> None:
        with self._lock:
            self._tenants.pop(tenant_id, None)
    
    async def list(
        self,
        status: Optional[TenantStatus] = None,
        tier: Optional[TenantTier] = None,
    ) -> List[Tenant]:
        with self._lock:
            tenants = list(self._tenants.values())
            
            if status:
                tenants = [t for t in tenants if t.status == status]
            
            if tier:
                tenants = [t for t in tenants if t.tier == tier]
            
            return tenants
    
    async def exists(self, tenant_id: str) -> bool:
        with self._lock:
            return tenant_id in self._tenants


class TenantContext:
    """
    Context manager for tenant scope.
    """
    
    def __init__(self, tenant_id: str, manager: "TenantManager"):
        self._tenant_id = tenant_id
        self._manager = manager
        self._token: Optional[contextvars.Token] = None
    
    async def __aenter__(self) -> "TenantContext":
        # Verify tenant exists and is active
        tenant = await self._manager.get(self._tenant_id)
        
        if not tenant:
            raise TenantNotFoundError(f"Tenant not found: {self._tenant_id}")
        
        if tenant.status == TenantStatus.SUSPENDED:
            raise TenantSuspendedError(f"Tenant is suspended: {self._tenant_id}")
        
        if tenant.status != TenantStatus.ACTIVE:
            raise TenantError(f"Tenant is not active: {self._tenant_id}")
        
        self._token = _current_tenant.set(self._tenant_id)
        return self
    
    async def __aexit__(self, *args) -> None:
        if self._token:
            _current_tenant.reset(self._token)
    
    def __enter__(self) -> "TenantContext":
        self._token = _current_tenant.set(self._tenant_id)
        return self
    
    def __exit__(self, *args) -> None:
        if self._token:
            _current_tenant.reset(self._token)


class QuotaEnforcer:
    """
    Enforces tenant quotas.
    """
    
    def __init__(self, manager: "TenantManager"):
        self._manager = manager
    
    async def check_quota(
        self,
        tenant_id: str,
        resource: str,
        amount: int = 1,
    ) -> bool:
        """Check if quota allows the operation."""
        tenant = await self._manager.get(tenant_id)
        
        if not tenant:
            return False
        
        quota = tenant.config.quota
        usage = tenant.usage
        
        checks = {
            "users": (usage.users + amount <= quota.max_users),
            "storage": (usage.storage_mb + amount <= quota.max_storage_mb),
            "api_calls": (usage.api_calls_today + amount <= quota.max_api_calls_per_day),
            "connections": (usage.concurrent_connections + amount <= quota.max_concurrent_connections),
        }
        
        if resource in checks:
            return checks[resource]
        
        # Check custom limits
        if resource in quota.custom_limits:
            current = usage.custom_usage.get(resource, 0)
            return current + amount <= quota.custom_limits[resource]
        
        return True  # No limit defined
    
    async def record_usage(
        self,
        tenant_id: str,
        resource: str,
        amount: int = 1,
    ) -> None:
        """Record resource usage."""
        tenant = await self._manager.get(tenant_id)
        
        if not tenant:
            return
        
        if resource == "users":
            tenant.usage.users += amount
        elif resource == "storage":
            tenant.usage.storage_mb += amount
        elif resource == "api_calls":
            tenant.usage.api_calls_today += amount
        elif resource == "connections":
            tenant.usage.concurrent_connections += amount
        else:
            if resource not in tenant.usage.custom_usage:
                tenant.usage.custom_usage[resource] = 0
            tenant.usage.custom_usage[resource] += amount
        
        tenant.usage.last_updated = datetime.utcnow()
        await self._manager.store.save(tenant)
    
    async def reset_daily_counters(self) -> None:
        """Reset daily counters for all tenants."""
        tenants = await self._manager.list()
        
        for tenant in tenants:
            tenant.usage.api_calls_today = 0
            await self._manager.store.save(tenant)


class TenantManager:
    """
    Manager for multi-tenant operations.
    """
    
    def __init__(self, store: Optional[TenantStore] = None):
        self._store = store or InMemoryTenantStore()
        self._quota_enforcer = QuotaEnforcer(self)
        self._tier_configs: Dict[TenantTier, ResourceQuota] = self._default_tier_configs()
    
    @property
    def store(self) -> TenantStore:
        return self._store
    
    @property
    def quota_enforcer(self) -> QuotaEnforcer:
        return self._quota_enforcer
    
    def _default_tier_configs(self) -> Dict[TenantTier, ResourceQuota]:
        """Default tier configurations."""
        return {
            TenantTier.FREE: ResourceQuota(
                max_users=5,
                max_storage_mb=100,
                max_api_calls_per_day=1000,
                max_concurrent_connections=2,
            ),
            TenantTier.BASIC: ResourceQuota(
                max_users=25,
                max_storage_mb=1000,
                max_api_calls_per_day=10000,
                max_concurrent_connections=5,
            ),
            TenantTier.PROFESSIONAL: ResourceQuota(
                max_users=100,
                max_storage_mb=10000,
                max_api_calls_per_day=100000,
                max_concurrent_connections=20,
            ),
            TenantTier.ENTERPRISE: ResourceQuota(
                max_users=1000000,
                max_storage_mb=1000000,
                max_api_calls_per_day=10000000,
                max_concurrent_connections=1000,
            ),
        }
    
    def set_tier_config(self, tier: TenantTier, quota: ResourceQuota) -> None:
        """Set quota configuration for a tier."""
        self._tier_configs[tier] = quota
    
    async def create(
        self,
        tenant_id: str,
        config: TenantConfig,
    ) -> Tenant:
        """Create a new tenant."""
        if await self._store.exists(tenant_id):
            raise TenantError(f"Tenant already exists: {tenant_id}")
        
        # Apply tier defaults if not specified
        if config.quota == ResourceQuota():
            config.quota = self._tier_configs.get(config.tier, ResourceQuota())
        
        tenant = Tenant(
            id=tenant_id,
            config=config,
            status=TenantStatus.ACTIVE,
        )
        
        await self._store.save(tenant)
        logger.info(f"Created tenant: {tenant_id}")
        
        return tenant
    
    async def get(self, tenant_id: str) -> Optional[Tenant]:
        """Get tenant by ID."""
        return await self._store.get(tenant_id)
    
    async def update(
        self,
        tenant_id: str,
        config: Optional[TenantConfig] = None,
        status: Optional[TenantStatus] = None,
    ) -> Optional[Tenant]:
        """Update tenant."""
        tenant = await self._store.get(tenant_id)
        
        if not tenant:
            return None
        
        if config:
            tenant.config = config
        
        if status:
            old_status = tenant.status
            tenant.status = status
            
            if status == TenantStatus.SUSPENDED:
                tenant.suspended_at = datetime.utcnow()
            elif status == TenantStatus.DELETED:
                tenant.deleted_at = datetime.utcnow()
            
            logger.info(f"Tenant {tenant_id} status changed: {old_status} -> {status}")
        
        await self._store.save(tenant)
        return tenant
    
    async def delete(self, tenant_id: str, soft: bool = True) -> None:
        """Delete tenant."""
        if soft:
            await self.update(tenant_id, status=TenantStatus.DELETED)
        else:
            await self._store.delete(tenant_id)
            logger.info(f"Deleted tenant: {tenant_id}")
    
    async def suspend(self, tenant_id: str, reason: str = "") -> Optional[Tenant]:
        """Suspend tenant."""
        tenant = await self.update(tenant_id, status=TenantStatus.SUSPENDED)
        if tenant:
            logger.warning(f"Suspended tenant {tenant_id}: {reason}")
        return tenant
    
    async def activate(self, tenant_id: str) -> Optional[Tenant]:
        """Activate tenant."""
        return await self.update(tenant_id, status=TenantStatus.ACTIVE)
    
    async def list(
        self,
        status: Optional[TenantStatus] = None,
        tier: Optional[TenantTier] = None,
    ) -> List[Tenant]:
        """List tenants."""
        return await self._store.list(status, tier)
    
    def tenant_context(self, tenant_id: str) -> TenantContext:
        """Create tenant context."""
        return TenantContext(tenant_id, self)
    
    async def check_quota(
        self,
        tenant_id: str,
        resource: str,
        amount: int = 1,
    ) -> bool:
        """Check if operation is within quota."""
        return await self._quota_enforcer.check_quota(tenant_id, resource, amount)
    
    async def record_usage(
        self,
        tenant_id: str,
        resource: str,
        amount: int = 1,
    ) -> None:
        """Record resource usage."""
        await self._quota_enforcer.record_usage(tenant_id, resource, amount)
    
    async def upgrade_tier(
        self,
        tenant_id: str,
        new_tier: TenantTier,
    ) -> Optional[Tenant]:
        """Upgrade tenant tier."""
        tenant = await self._store.get(tenant_id)
        
        if not tenant:
            return None
        
        tenant.config.tier = new_tier
        tenant.config.quota = self._tier_configs.get(new_tier, tenant.config.quota)
        
        await self._store.save(tenant)
        logger.info(f"Upgraded tenant {tenant_id} to tier: {new_tier}")
        
        return tenant


# Global manager
_global_manager: Optional[TenantManager] = None


def get_current_tenant() -> Optional[str]:
    """Get current tenant ID from context."""
    return _current_tenant.get()


def require_tenant() -> str:
    """Get current tenant ID or raise error."""
    tenant_id = _current_tenant.get()
    if not tenant_id:
        raise TenantError("No tenant in context")
    return tenant_id


# Decorators
def tenant_aware(func: Callable) -> Callable:
    """
    Decorator to make function tenant-aware.
    
    Example:
        @tenant_aware
        async def get_data(tenant_id: str):
            ...
    """
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        tenant_id = get_current_tenant()
        
        if tenant_id and 'tenant_id' not in kwargs:
            kwargs['tenant_id'] = tenant_id
        
        return await func(*args, **kwargs)
    
    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        tenant_id = get_current_tenant()
        
        if tenant_id and 'tenant_id' not in kwargs:
            kwargs['tenant_id'] = tenant_id
        
        return func(*args, **kwargs)
    
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper


def require_tenant_context(func: Callable) -> Callable:
    """
    Decorator to require tenant context.
    
    Example:
        @require_tenant_context
        async def tenant_only_operation():
            ...
    """
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        tenant_id = get_current_tenant()
        
        if not tenant_id:
            raise TenantError("Operation requires tenant context")
        
        return await func(*args, **kwargs)
    
    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        tenant_id = get_current_tenant()
        
        if not tenant_id:
            raise TenantError("Operation requires tenant context")
        
        return func(*args, **kwargs)
    
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper


def check_quota(resource: str, amount: int = 1) -> Callable:
    """
    Decorator to check quota before operation.
    
    Example:
        @check_quota("api_calls")
        async def api_endpoint():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            tenant_id = get_current_tenant()
            
            if tenant_id:
                manager = get_global_manager()
                
                if not await manager.check_quota(tenant_id, resource, amount):
                    raise TenantQuotaExceededError(
                        f"Quota exceeded for {resource}"
                    )
                
                await manager.record_usage(tenant_id, resource, amount)
            
            return await func(*args, **kwargs)
        
        return async_wrapper
    
    return decorator


# Factory functions
def create_tenant_manager(
    store: Optional[TenantStore] = None,
) -> TenantManager:
    """Create a tenant manager."""
    return TenantManager(store)


def create_tenant_config(
    name: str,
    tier: TenantTier = TenantTier.FREE,
    settings: Optional[Dict[str, Any]] = None,
) -> TenantConfig:
    """Create tenant configuration."""
    return TenantConfig(
        name=name,
        tier=tier,
        settings=settings or {},
    )


def create_resource_quota(
    max_users: int = 100,
    max_storage_mb: int = 1000,
    max_api_calls_per_day: int = 10000,
    **custom_limits,
) -> ResourceQuota:
    """Create resource quota."""
    return ResourceQuota(
        max_users=max_users,
        max_storage_mb=max_storage_mb,
        max_api_calls_per_day=max_api_calls_per_day,
        custom_limits=custom_limits,
    )


def create_in_memory_store() -> InMemoryTenantStore:
    """Create in-memory tenant store."""
    return InMemoryTenantStore()


def get_global_manager() -> TenantManager:
    """Get global tenant manager."""
    global _global_manager
    if _global_manager is None:
        _global_manager = create_tenant_manager()
    return _global_manager


__all__ = [
    # Exceptions
    "TenantError",
    "TenantNotFoundError",
    "TenantQuotaExceededError",
    "TenantSuspendedError",
    # Enums
    "TenantTier",
    "TenantStatus",
    "IsolationLevel",
    # Data classes
    "ResourceQuota",
    "TenantConfig",
    "TenantUsage",
    "Tenant",
    # Store
    "TenantStore",
    "InMemoryTenantStore",
    # Context
    "TenantContext",
    # Quota
    "QuotaEnforcer",
    # Manager
    "TenantManager",
    # Helpers
    "get_current_tenant",
    "require_tenant",
    # Decorators
    "tenant_aware",
    "require_tenant_context",
    "check_quota",
    # Factory functions
    "create_tenant_manager",
    "create_tenant_config",
    "create_resource_quota",
    "create_in_memory_store",
    "get_global_manager",
]
