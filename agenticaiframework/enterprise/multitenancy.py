"""
Enterprise Multi-tenancy - Tenant isolation and configuration.

Provides multi-tenant support for SaaS applications with
tenant isolation, configuration, and resource management.

Features:
- Tenant isolation
- Per-tenant configuration
- Usage tracking
- Resource quotas
- Data isolation
"""

import asyncio
import contextvars
import functools
import logging
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, Generic, List, Optional, Set, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


# =============================================================================
# Tenant Models
# =============================================================================

class TenantStatus(Enum):
    """Tenant status states."""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    TRIAL = "trial"
    EXPIRED = "expired"
    DELETED = "deleted"


class TenantTier(Enum):
    """Tenant subscription tiers."""
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"
    CUSTOM = "custom"


@dataclass
class TenantQuota:
    """Quotas for a tenant."""
    max_agents: int = 10
    max_workflows: int = 100
    max_requests_per_day: int = 1000
    max_tokens_per_month: int = 1000000
    max_storage_mb: int = 1000
    max_users: int = 10
    
    # Feature flags
    enable_advanced_agents: bool = False
    enable_custom_models: bool = False
    enable_api_access: bool = True
    enable_audit_logs: bool = False
    enable_sso: bool = False


@dataclass
class TenantUsage:
    """Usage tracking for a tenant."""
    agents_count: int = 0
    workflows_count: int = 0
    requests_today: int = 0
    tokens_this_month: int = 0
    storage_used_mb: float = 0
    users_count: int = 0
    
    last_request_at: Optional[datetime] = None
    reset_daily_at: Optional[datetime] = None
    reset_monthly_at: Optional[datetime] = None


@dataclass
class Tenant:
    """A tenant in the multi-tenant system."""
    id: str
    name: str
    slug: str  # URL-safe identifier
    
    # Status
    status: TenantStatus = TenantStatus.ACTIVE
    tier: TenantTier = TenantTier.FREE
    
    # Configuration
    config: Dict[str, Any] = field(default_factory=dict)
    quota: TenantQuota = field(default_factory=TenantQuota)
    usage: TenantUsage = field(default_factory=TenantUsage)
    
    # Metadata
    owner_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    trial_ends_at: Optional[datetime] = None
    
    # Features
    features: Set[str] = field(default_factory=set)
    
    def is_active(self) -> bool:
        """Check if tenant is active."""
        return self.status == TenantStatus.ACTIVE
    
    def check_quota(self, resource: str, amount: int = 1) -> bool:
        """Check if quota allows the operation."""
        if resource == "agents":
            return self.usage.agents_count + amount <= self.quota.max_agents
        elif resource == "workflows":
            return self.usage.workflows_count + amount <= self.quota.max_workflows
        elif resource == "requests":
            return self.usage.requests_today + amount <= self.quota.max_requests_per_day
        elif resource == "tokens":
            return self.usage.tokens_this_month + amount <= self.quota.max_tokens_per_month
        elif resource == "storage":
            return self.usage.storage_used_mb + amount <= self.quota.max_storage_mb
        elif resource == "users":
            return self.usage.users_count + amount <= self.quota.max_users
        return True
    
    def has_feature(self, feature: str) -> bool:
        """Check if tenant has a feature."""
        return feature in self.features


# =============================================================================
# Tenant Store
# =============================================================================

class TenantStore(ABC):
    """Abstract interface for tenant storage."""
    
    @abstractmethod
    async def get(self, tenant_id: str) -> Optional[Tenant]:
        """Get a tenant by ID."""
        pass
    
    @abstractmethod
    async def get_by_slug(self, slug: str) -> Optional[Tenant]:
        """Get a tenant by slug."""
        pass
    
    @abstractmethod
    async def save(self, tenant: Tenant):
        """Save a tenant."""
        pass
    
    @abstractmethod
    async def delete(self, tenant_id: str):
        """Delete a tenant."""
        pass
    
    @abstractmethod
    async def list(
        self,
        status: Optional[TenantStatus] = None,
        tier: Optional[TenantTier] = None,
        limit: int = 100,
    ) -> List[Tenant]:
        """List tenants with optional filtering."""
        pass


class InMemoryTenantStore(TenantStore):
    """In-memory tenant store."""
    
    def __init__(self):
        self._tenants: Dict[str, Tenant] = {}
        self._by_slug: Dict[str, str] = {}
        self._lock = asyncio.Lock()
    
    async def get(self, tenant_id: str) -> Optional[Tenant]:
        return self._tenants.get(tenant_id)
    
    async def get_by_slug(self, slug: str) -> Optional[Tenant]:
        tenant_id = self._by_slug.get(slug)
        if tenant_id:
            return self._tenants.get(tenant_id)
        return None
    
    async def save(self, tenant: Tenant):
        async with self._lock:
            self._tenants[tenant.id] = tenant
            self._by_slug[tenant.slug] = tenant.id
    
    async def delete(self, tenant_id: str):
        async with self._lock:
            tenant = self._tenants.get(tenant_id)
            if tenant:
                del self._tenants[tenant_id]
                if tenant.slug in self._by_slug:
                    del self._by_slug[tenant.slug]
    
    async def list(
        self,
        status: Optional[TenantStatus] = None,
        tier: Optional[TenantTier] = None,
        limit: int = 100,
    ) -> List[Tenant]:
        tenants = list(self._tenants.values())
        
        if status:
            tenants = [t for t in tenants if t.status == status]
        
        if tier:
            tenants = [t for t in tenants if t.tier == tier]
        
        return tenants[:limit]


# =============================================================================
# Tenant Context
# =============================================================================

_current_tenant: contextvars.ContextVar[Optional[Tenant]] = contextvars.ContextVar(
    "current_tenant",
    default=None,
)


def get_current_tenant() -> Optional[Tenant]:
    """Get the current tenant from context."""
    return _current_tenant.get()


def set_current_tenant(tenant: Tenant):
    """Set the current tenant in context."""
    _current_tenant.set(tenant)


class TenantContext:
    """
    Context manager for tenant operations.
    
    Usage:
        >>> async with TenantContext(tenant):
        ...     # All operations within this block use the tenant
        ...     result = await agent.run("task")
    """
    
    def __init__(self, tenant: Tenant):
        self.tenant = tenant
        self._token = None
    
    def __enter__(self):
        self._token = _current_tenant.set(self.tenant)
        return self
    
    def __exit__(self, *args):
        _current_tenant.reset(self._token)
    
    async def __aenter__(self):
        return self.__enter__()
    
    async def __aexit__(self, *args):
        self.__exit__(*args)


# =============================================================================
# Tenant Manager
# =============================================================================

class TenantManager:
    """
    High-level tenant management.
    
    Usage:
        >>> manager = TenantManager()
        >>> 
        >>> # Create tenant
        >>> tenant = await manager.create(
        ...     name="Acme Corp",
        ...     slug="acme",
        ...     tier=TenantTier.PROFESSIONAL,
        ... )
        >>> 
        >>> # Use tenant context
        >>> async with manager.context(tenant.id):
        ...     await agent.run("task")
    """
    
    def __init__(self, store: Optional[TenantStore] = None):
        self.store = store or InMemoryTenantStore()
        
        # Tier quotas
        self._tier_quotas = {
            TenantTier.FREE: TenantQuota(
                max_agents=3,
                max_workflows=10,
                max_requests_per_day=100,
                max_tokens_per_month=10000,
                max_storage_mb=100,
                max_users=2,
            ),
            TenantTier.STARTER: TenantQuota(
                max_agents=10,
                max_workflows=50,
                max_requests_per_day=1000,
                max_tokens_per_month=100000,
                max_storage_mb=500,
                max_users=5,
                enable_api_access=True,
            ),
            TenantTier.PROFESSIONAL: TenantQuota(
                max_agents=50,
                max_workflows=500,
                max_requests_per_day=10000,
                max_tokens_per_month=1000000,
                max_storage_mb=5000,
                max_users=25,
                enable_advanced_agents=True,
                enable_api_access=True,
                enable_audit_logs=True,
            ),
            TenantTier.ENTERPRISE: TenantQuota(
                max_agents=1000,
                max_workflows=10000,
                max_requests_per_day=100000,
                max_tokens_per_month=10000000,
                max_storage_mb=100000,
                max_users=1000,
                enable_advanced_agents=True,
                enable_custom_models=True,
                enable_api_access=True,
                enable_audit_logs=True,
                enable_sso=True,
            ),
        }
    
    async def create(
        self,
        name: str,
        slug: str,
        tier: TenantTier = TenantTier.FREE,
        owner_id: Optional[str] = None,
        config: Dict[str, Any] = None,
        **metadata,
    ) -> Tenant:
        """Create a new tenant."""
        import uuid
        
        # Check slug uniqueness
        existing = await self.store.get_by_slug(slug)
        if existing:
            raise TenantError(f"Slug already exists: {slug}")
        
        # Get tier quota
        quota = self._tier_quotas.get(tier, TenantQuota())
        
        tenant = Tenant(
            id=str(uuid.uuid4()),
            name=name,
            slug=slug,
            tier=tier,
            owner_id=owner_id,
            config=config or {},
            quota=quota,
            metadata=metadata,
        )
        
        await self.store.save(tenant)
        logger.info(f"Created tenant: {name} ({slug})")
        
        return tenant
    
    async def get(self, tenant_id: str) -> Optional[Tenant]:
        """Get a tenant by ID."""
        return await self.store.get(tenant_id)
    
    async def get_by_slug(self, slug: str) -> Optional[Tenant]:
        """Get a tenant by slug."""
        return await self.store.get_by_slug(slug)
    
    async def update(self, tenant: Tenant):
        """Update a tenant."""
        tenant.updated_at = datetime.now()
        await self.store.save(tenant)
    
    async def delete(self, tenant_id: str):
        """Delete a tenant."""
        await self.store.delete(tenant_id)
    
    async def list(
        self,
        status: Optional[TenantStatus] = None,
        tier: Optional[TenantTier] = None,
        limit: int = 100,
    ) -> List[Tenant]:
        """List tenants."""
        return await self.store.list(status, tier, limit)
    
    async def suspend(self, tenant_id: str, reason: str = ""):
        """Suspend a tenant."""
        tenant = await self.store.get(tenant_id)
        if tenant:
            tenant.status = TenantStatus.SUSPENDED
            tenant.metadata["suspend_reason"] = reason
            tenant.metadata["suspended_at"] = datetime.now().isoformat()
            await self.store.save(tenant)
    
    async def activate(self, tenant_id: str):
        """Activate a tenant."""
        tenant = await self.store.get(tenant_id)
        if tenant:
            tenant.status = TenantStatus.ACTIVE
            await self.store.save(tenant)
    
    async def upgrade(self, tenant_id: str, tier: TenantTier):
        """Upgrade tenant tier."""
        tenant = await self.store.get(tenant_id)
        if tenant:
            tenant.tier = tier
            tenant.quota = self._tier_quotas.get(tier, tenant.quota)
            await self.store.save(tenant)
    
    async def track_usage(
        self,
        tenant_id: str,
        resource: str,
        amount: int = 1,
    ):
        """Track resource usage."""
        tenant = await self.store.get(tenant_id)
        if not tenant:
            return
        
        if resource == "requests":
            tenant.usage.requests_today += amount
            tenant.usage.last_request_at = datetime.now()
        elif resource == "tokens":
            tenant.usage.tokens_this_month += amount
        elif resource == "agents":
            tenant.usage.agents_count += amount
        elif resource == "workflows":
            tenant.usage.workflows_count += amount
        elif resource == "storage":
            tenant.usage.storage_used_mb += amount
        elif resource == "users":
            tenant.usage.users_count += amount
        
        await self.store.save(tenant)
    
    async def check_quota(
        self,
        tenant_id: str,
        resource: str,
        amount: int = 1,
    ) -> bool:
        """Check if quota allows the operation."""
        tenant = await self.store.get(tenant_id)
        if not tenant:
            return False
        return tenant.check_quota(resource, amount)
    
    def context(self, tenant_id: str):
        """Create a context manager for tenant operations."""
        return TenantContextManager(self, tenant_id)
    
    async def get_config(
        self,
        tenant_id: str,
        key: str,
        default: Any = None,
    ) -> Any:
        """Get tenant configuration value."""
        tenant = await self.store.get(tenant_id)
        if tenant:
            return tenant.config.get(key, default)
        return default
    
    async def set_config(
        self,
        tenant_id: str,
        key: str,
        value: Any,
    ):
        """Set tenant configuration value."""
        tenant = await self.store.get(tenant_id)
        if tenant:
            tenant.config[key] = value
            await self.store.save(tenant)


class TenantContextManager:
    """Async context manager for tenant operations."""
    
    def __init__(self, manager: TenantManager, tenant_id: str):
        self.manager = manager
        self.tenant_id = tenant_id
        self._token = None
    
    async def __aenter__(self):
        tenant = await self.manager.get(self.tenant_id)
        if not tenant:
            raise TenantError(f"Tenant not found: {self.tenant_id}")
        
        if not tenant.is_active():
            raise TenantError(f"Tenant is not active: {tenant.status.value}")
        
        self._token = _current_tenant.set(tenant)
        return tenant
    
    async def __aexit__(self, *args):
        _current_tenant.reset(self._token)


# =============================================================================
# Tenant Middleware
# =============================================================================

class TenantMiddleware:
    """
    Middleware for automatic tenant resolution.
    
    Can resolve tenant from:
    - Request header (X-Tenant-ID)
    - Subdomain
    - API key
    - JWT token
    """
    
    def __init__(
        self,
        manager: TenantManager,
        header_name: str = "X-Tenant-ID",
        subdomain_position: int = 0,  # 0 = first part of host
    ):
        self.manager = manager
        self.header_name = header_name
        self.subdomain_position = subdomain_position
    
    async def resolve_from_header(self, headers: Dict[str, str]) -> Optional[Tenant]:
        """Resolve tenant from request header."""
        tenant_id = headers.get(self.header_name)
        if tenant_id:
            return await self.manager.get(tenant_id)
        return None
    
    async def resolve_from_subdomain(self, host: str) -> Optional[Tenant]:
        """Resolve tenant from subdomain."""
        parts = host.split(".")
        if len(parts) > 2:
            slug = parts[self.subdomain_position]
            return await self.manager.get_by_slug(slug)
        return None
    
    async def resolve_from_api_key(self, api_key: str) -> Optional[Tenant]:
        """Resolve tenant from API key."""
        # API key format: tenant_id:secret
        if ":" in api_key:
            tenant_id = api_key.split(":")[0]
            return await self.manager.get(tenant_id)
        return None


# =============================================================================
# Tenant Isolation
# =============================================================================

class TenantIsolation(Generic[T]):
    """
    Provides tenant-isolated storage.
    
    Usage:
        >>> storage = TenantIsolation[Dict]()
        >>> 
        >>> with TenantContext(tenant_a):
        ...     storage.set("key", {"data": "a"})
        >>> 
        >>> with TenantContext(tenant_b):
        ...     storage.set("key", {"data": "b"})
        >>> 
        >>> # Data is isolated per tenant
    """
    
    def __init__(self):
        self._data: Dict[str, Dict[str, T]] = {}
        self._lock = threading.RLock()
    
    def get(self, key: str, default: T = None) -> Optional[T]:
        """Get a value for current tenant."""
        tenant = get_current_tenant()
        if not tenant:
            return default
        
        with self._lock:
            tenant_data = self._data.get(tenant.id, {})
            return tenant_data.get(key, default)
    
    def set(self, key: str, value: T):
        """Set a value for current tenant."""
        tenant = get_current_tenant()
        if not tenant:
            raise TenantError("No tenant context")
        
        with self._lock:
            if tenant.id not in self._data:
                self._data[tenant.id] = {}
            self._data[tenant.id][key] = value
    
    def delete(self, key: str):
        """Delete a value for current tenant."""
        tenant = get_current_tenant()
        if tenant and tenant.id in self._data:
            with self._lock:
                self._data[tenant.id].pop(key, None)
    
    def clear(self):
        """Clear all data for current tenant."""
        tenant = get_current_tenant()
        if tenant and tenant.id in self._data:
            with self._lock:
                self._data[tenant.id].clear()
    
    def clear_all(self, tenant_id: str):
        """Clear all data for a specific tenant."""
        with self._lock:
            if tenant_id in self._data:
                del self._data[tenant_id]


# =============================================================================
# Decorators
# =============================================================================

def require_tenant(fn: Callable) -> Callable:
    """Decorator that requires a tenant context."""
    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        tenant = get_current_tenant()
        if not tenant:
            raise TenantError("Tenant context required")
        return await fn(*args, **kwargs)
    return wrapper


def check_quota(resource: str, amount: int = 1):
    """Decorator to check quota before operation."""
    def decorator(fn: Callable):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            tenant = get_current_tenant()
            if tenant and not tenant.check_quota(resource, amount):
                raise QuotaExceededError(f"Quota exceeded for {resource}")
            return await fn(*args, **kwargs)
        return wrapper
    return decorator


def require_feature(feature: str):
    """Decorator to require a tenant feature."""
    def decorator(fn: Callable):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            tenant = get_current_tenant()
            if not tenant or not tenant.has_feature(feature):
                raise FeatureNotEnabledError(f"Feature not enabled: {feature}")
            return await fn(*args, **kwargs)
        return wrapper
    return decorator


# =============================================================================
# Errors
# =============================================================================

class TenantError(Exception):
    """Tenant-related error."""
    pass


class QuotaExceededError(TenantError):
    """Quota exceeded error."""
    pass


class FeatureNotEnabledError(TenantError):
    """Feature not enabled error."""
    pass


# =============================================================================
# Global Manager
# =============================================================================

_global_manager: Optional[TenantManager] = None
_lock = threading.Lock()


def get_tenant_manager() -> TenantManager:
    """Get the global tenant manager."""
    global _global_manager
    
    if _global_manager is None:
        with _lock:
            if _global_manager is None:
                _global_manager = TenantManager()
    
    return _global_manager


def set_tenant_manager(manager: TenantManager):
    """Set the global tenant manager."""
    global _global_manager
    _global_manager = manager


# Convenience functions
async def create_tenant(name: str, slug: str, **kwargs) -> Tenant:
    """Create a tenant using global manager."""
    return await get_tenant_manager().create(name, slug, **kwargs)


async def get_tenant(tenant_id: str) -> Optional[Tenant]:
    """Get a tenant using global manager."""
    return await get_tenant_manager().get(tenant_id)


def current_tenant() -> Optional[Tenant]:
    """Get the current tenant."""
    return get_current_tenant()
