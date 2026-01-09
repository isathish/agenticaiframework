"""
Tenant Manager.

Manages tenant isolation and multi-tenancy with:
- Tenant provisioning
- Resource isolation
- Quota management
- Usage tracking
"""

import uuid
import time
import logging
import threading
from typing import Dict, Any, List, Optional
from collections import defaultdict

from .types import Region, Tenant

logger = logging.getLogger(__name__)


class TenantManager:
    """
    Manages tenant isolation and multi-tenancy.
    
    Features:
    - Tenant provisioning
    - Resource isolation
    - Quota management
    - Usage tracking
    """
    
    def __init__(self):
        self.tenants: Dict[str, Tenant] = {}
        self.usage: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._context = threading.local()
        self._lock = threading.Lock()
        
        # Default quotas by tier
        self.tier_quotas = {
            'free': {'requests_per_day': 100, 'agents': 1, 'storage_mb': 100},
            'standard': {'requests_per_day': 10000, 'agents': 10, 'storage_mb': 1000},
            'premium': {'requests_per_day': 100000, 'agents': 100, 'storage_mb': 10000},
            'enterprise': {'requests_per_day': -1, 'agents': -1, 'storage_mb': -1}  # unlimited
        }
    
    def create_tenant(self,
                     name: str,
                     tier: str = "free",
                     custom_quota: Dict[str, int] = None,
                     metadata: Dict[str, Any] = None,
                     region: Region = None,
                     isolation_level: str = "shared") -> Tenant:
        """
        Create a new tenant.
        
        Args:
            name: Tenant name
            tier: Pricing tier
            custom_quota: Override default quotas
            metadata: Additional metadata
            region: Preferred region
            isolation_level: Isolation type
        """
        tenant_id = str(uuid.uuid4())
        
        # Get quota based on tier
        quota = self.tier_quotas.get(tier, self.tier_quotas['free']).copy()
        if custom_quota:
            quota.update(custom_quota)
        
        tenant = Tenant(
            tenant_id=tenant_id,
            name=name,
            tier=tier,
            quota=quota,
            metadata=metadata or {},
            created_at=time.time(),
            region=region,
            isolation_level=isolation_level
        )
        
        with self._lock:
            self.tenants[tenant_id] = tenant
        
        logger.info("Created tenant '%s' (id=%s, tier=%s)", name, tenant_id, tier)
        
        return tenant
    
    def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        """Get tenant by ID."""
        return self.tenants.get(tenant_id)
    
    def set_current_tenant(self, tenant_id: str):
        """Set current tenant context."""
        if tenant_id not in self.tenants:
            raise ValueError(f"Tenant '{tenant_id}' not found")
        self._context.tenant_id = tenant_id
    
    def get_current_tenant(self) -> Optional[str]:
        """Get current tenant context."""
        return getattr(self._context, 'tenant_id', None)
    
    def clear_tenant_context(self):
        """Clear tenant context."""
        if hasattr(self._context, 'tenant_id'):
            del self._context.tenant_id
    
    def check_quota(self, tenant_id: str, resource: str, amount: int = 1) -> bool:
        """Check if tenant has quota for resource."""
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            return False
        
        quota_limit = tenant.quota.get(resource, 0)
        if quota_limit == -1:  # Unlimited
            return True
        
        current_usage = self.usage[tenant_id][resource]
        return (current_usage + amount) <= quota_limit
    
    def consume_quota(self, tenant_id: str, resource: str, amount: int = 1) -> bool:
        """Consume tenant quota."""
        if not self.check_quota(tenant_id, resource, amount):
            return False
        
        with self._lock:
            self.usage[tenant_id][resource] += amount
        
        return True
    
    def get_usage(self, tenant_id: str) -> Dict[str, Any]:
        """Get tenant usage."""
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            return {}
        
        return {
            'tenant_id': tenant_id,
            'tier': tenant.tier,
            'quota': tenant.quota,
            'usage': dict(self.usage[tenant_id]),
            'utilization': {
                resource: (self.usage[tenant_id][resource] / limit * 100) 
                if limit > 0 else 0
                for resource, limit in tenant.quota.items()
            }
        }
    
    def update_tier(self, tenant_id: str, new_tier: str):
        """Update tenant tier."""
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            raise ValueError(f"Tenant '{tenant_id}' not found")
        
        tenant.tier = new_tier
        tenant.quota = self.tier_quotas.get(new_tier, self.tier_quotas['free']).copy()
        
        logger.info("Updated tenant %s to tier %s", tenant_id, new_tier)
    
    def suspend_tenant(self, tenant_id: str, reason: str = None):
        """Suspend a tenant."""
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            raise ValueError(f"Tenant '{tenant_id}' not found")
        
        tenant.status = "suspended"
        tenant.metadata['suspension_reason'] = reason
        tenant.metadata['suspended_at'] = time.time()
        
        logger.warning("Suspended tenant %s: %s", tenant_id, reason)
    
    def list_tenants(self, 
                    status: str = None,
                    tier: str = None) -> List[Dict[str, Any]]:
        """List tenants with optional filtering."""
        results = []
        
        for tenant in self.tenants.values():
            if status and tenant.status != status:
                continue
            if tier and tenant.tier != tier:
                continue
            
            results.append({
                'tenant_id': tenant.tenant_id,
                'name': tenant.name,
                'tier': tenant.tier,
                'status': tenant.status,
                'isolation_level': tenant.isolation_level,
                'region': tenant.region.value if tenant.region else None,
                'created_at': tenant.created_at
            })
        
        return results


__all__ = ['TenantManager']
