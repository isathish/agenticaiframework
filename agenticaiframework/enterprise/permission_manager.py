"""
Enterprise Permission Manager Module.

Provides RBAC, ABAC, permission inheritance, role management,
and fine-grained access control.

Example:
    # Create permission manager
    perms = create_permission_manager()
    
    # Define roles and permissions
    perms.define_permission("users.read", "Read users")
    perms.define_permission("users.write", "Write users")
    
    perms.define_role("viewer", permissions=["users.read"])
    perms.define_role("editor", permissions=["users.read", "users.write"])
    
    # Assign role to user
    await perms.assign_role("user123", "editor")
    
    # Check permission
    if await perms.has_permission("user123", "users.write"):
        ...
    
    # Use decorator
    @require_permission("users.write")
    async def update_user(user_id: str, data: dict):
        ...
"""

from __future__ import annotations

import asyncio
import contextvars
import functools
import logging
import re
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
    Pattern,
    Set,
    Tuple,
    TypeVar,
    Union,
)

T = TypeVar('T')


logger = logging.getLogger(__name__)


# Context variable for current principal
_current_principal: contextvars.ContextVar[Optional["Principal"]] = contextvars.ContextVar(
    'current_principal', default=None
)


class PermissionError(Exception):
    """Base permission error."""
    pass


class AccessDeniedError(PermissionError):
    """Access denied."""
    pass


class RoleNotFoundError(PermissionError):
    """Role not found."""
    pass


class PermissionEffect(str, Enum):
    """Permission effect."""
    ALLOW = "allow"
    DENY = "deny"


class ConditionType(str, Enum):
    """Attribute condition type."""
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    CONTAINS = "contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    MATCHES = "matches"
    IN = "in"
    NOT_IN = "not_in"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"


@dataclass
class Permission:
    """Permission definition."""
    name: str
    description: str = ""
    resource: Optional[str] = None
    actions: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Condition:
    """Attribute-based condition."""
    attribute: str
    type: ConditionType
    value: Any
    
    def evaluate(self, context: Dict[str, Any]) -> bool:
        """Evaluate condition against context."""
        actual = context.get(self.attribute)
        
        if actual is None:
            return False
        
        if self.type == ConditionType.EQUALS:
            return actual == self.value
        elif self.type == ConditionType.NOT_EQUALS:
            return actual != self.value
        elif self.type == ConditionType.CONTAINS:
            return self.value in actual if hasattr(actual, '__contains__') else False
        elif self.type == ConditionType.STARTS_WITH:
            return str(actual).startswith(str(self.value))
        elif self.type == ConditionType.ENDS_WITH:
            return str(actual).endswith(str(self.value))
        elif self.type == ConditionType.MATCHES:
            return bool(re.match(str(self.value), str(actual)))
        elif self.type == ConditionType.IN:
            return actual in self.value if isinstance(self.value, (list, set, tuple)) else False
        elif self.type == ConditionType.NOT_IN:
            return actual not in self.value if isinstance(self.value, (list, set, tuple)) else True
        elif self.type == ConditionType.GREATER_THAN:
            return actual > self.value
        elif self.type == ConditionType.LESS_THAN:
            return actual < self.value
        
        return False


@dataclass
class Policy:
    """Access control policy."""
    name: str
    effect: PermissionEffect = PermissionEffect.ALLOW
    permissions: Set[str] = field(default_factory=set)
    conditions: List[Condition] = field(default_factory=list)
    priority: int = 0
    description: str = ""
    
    def matches(
        self,
        permission: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Check if policy matches."""
        # Check permission match (support wildcards)
        permission_match = False
        
        for perm in self.permissions:
            if perm == "*":
                permission_match = True
                break
            elif perm.endswith(".*"):
                prefix = perm[:-2]
                if permission.startswith(prefix):
                    permission_match = True
                    break
            elif perm == permission:
                permission_match = True
                break
        
        if not permission_match:
            return False
        
        # Check conditions
        if self.conditions and context:
            return all(c.evaluate(context) for c in self.conditions)
        
        return True


@dataclass
class Role:
    """Role definition."""
    name: str
    description: str = ""
    permissions: Set[str] = field(default_factory=set)
    policies: List[str] = field(default_factory=list)  # Policy names
    parent_roles: Set[str] = field(default_factory=set)  # Role inheritance
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Principal:
    """Security principal (user/service)."""
    id: str
    type: str = "user"  # user, service, api_key
    roles: Set[str] = field(default_factory=set)
    direct_permissions: Set[str] = field(default_factory=set)
    attributes: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RoleAssignment:
    """Role assignment to principal."""
    principal_id: str
    role_name: str
    scope: Optional[str] = None  # Resource scope
    expires_at: Optional[datetime] = None
    conditions: List[Condition] = field(default_factory=list)
    assigned_at: datetime = field(default_factory=datetime.utcnow)


class PermissionStore(ABC):
    """Abstract permission store."""
    
    @abstractmethod
    async def get_principal(self, principal_id: str) -> Optional[Principal]:
        """Get principal."""
        pass
    
    @abstractmethod
    async def save_principal(self, principal: Principal) -> None:
        """Save principal."""
        pass
    
    @abstractmethod
    async def get_role(self, role_name: str) -> Optional[Role]:
        """Get role."""
        pass
    
    @abstractmethod
    async def save_role(self, role: Role) -> None:
        """Save role."""
        pass
    
    @abstractmethod
    async def get_policy(self, policy_name: str) -> Optional[Policy]:
        """Get policy."""
        pass
    
    @abstractmethod
    async def save_policy(self, policy: Policy) -> None:
        """Save policy."""
        pass
    
    @abstractmethod
    async def get_assignments(self, principal_id: str) -> List[RoleAssignment]:
        """Get role assignments for principal."""
        pass
    
    @abstractmethod
    async def save_assignment(self, assignment: RoleAssignment) -> None:
        """Save role assignment."""
        pass
    
    @abstractmethod
    async def delete_assignment(self, principal_id: str, role_name: str) -> None:
        """Delete role assignment."""
        pass


class InMemoryPermissionStore(PermissionStore):
    """In-memory permission store."""
    
    def __init__(self):
        self._principals: Dict[str, Principal] = {}
        self._roles: Dict[str, Role] = {}
        self._policies: Dict[str, Policy] = {}
        self._assignments: Dict[str, List[RoleAssignment]] = {}
        self._permissions: Dict[str, Permission] = {}
        self._lock = threading.Lock()
    
    async def get_principal(self, principal_id: str) -> Optional[Principal]:
        with self._lock:
            return self._principals.get(principal_id)
    
    async def save_principal(self, principal: Principal) -> None:
        with self._lock:
            self._principals[principal.id] = principal
    
    async def get_role(self, role_name: str) -> Optional[Role]:
        with self._lock:
            return self._roles.get(role_name)
    
    async def save_role(self, role: Role) -> None:
        with self._lock:
            self._roles[role.name] = role
    
    async def get_policy(self, policy_name: str) -> Optional[Policy]:
        with self._lock:
            return self._policies.get(policy_name)
    
    async def save_policy(self, policy: Policy) -> None:
        with self._lock:
            self._policies[policy.name] = policy
    
    async def get_assignments(self, principal_id: str) -> List[RoleAssignment]:
        with self._lock:
            return list(self._assignments.get(principal_id, []))
    
    async def save_assignment(self, assignment: RoleAssignment) -> None:
        with self._lock:
            if assignment.principal_id not in self._assignments:
                self._assignments[assignment.principal_id] = []
            
            # Replace existing assignment for same role
            assignments = self._assignments[assignment.principal_id]
            self._assignments[assignment.principal_id] = [
                a for a in assignments if a.role_name != assignment.role_name
            ]
            self._assignments[assignment.principal_id].append(assignment)
    
    async def delete_assignment(self, principal_id: str, role_name: str) -> None:
        with self._lock:
            if principal_id in self._assignments:
                self._assignments[principal_id] = [
                    a for a in self._assignments[principal_id]
                    if a.role_name != role_name
                ]
    
    # Additional methods for permissions
    async def get_permission(self, name: str) -> Optional[Permission]:
        with self._lock:
            return self._permissions.get(name)
    
    async def save_permission(self, permission: Permission) -> None:
        with self._lock:
            self._permissions[permission.name] = permission
    
    async def list_roles(self) -> List[Role]:
        with self._lock:
            return list(self._roles.values())
    
    async def list_policies(self) -> List[Policy]:
        with self._lock:
            return list(self._policies.values())


class PermissionManager:
    """
    Manager for permissions, roles, and access control.
    """
    
    def __init__(self, store: Optional[PermissionStore] = None):
        self._store = store or InMemoryPermissionStore()
        self._permission_cache: Dict[str, Set[str]] = {}
        self._cache_ttl = timedelta(minutes=5)
        self._cache_updated: Dict[str, datetime] = {}
    
    @property
    def store(self) -> PermissionStore:
        return self._store
    
    # Permission management
    def define_permission(
        self,
        name: str,
        description: str = "",
        resource: Optional[str] = None,
        actions: Optional[Set[str]] = None,
    ) -> Permission:
        """Define a permission."""
        permission = Permission(
            name=name,
            description=description,
            resource=resource,
            actions=actions or set(),
        )
        
        asyncio.create_task(self._store.save_permission(permission))
        return permission
    
    # Role management
    async def define_role(
        self,
        name: str,
        description: str = "",
        permissions: Optional[List[str]] = None,
        parent_roles: Optional[List[str]] = None,
    ) -> Role:
        """Define a role."""
        role = Role(
            name=name,
            description=description,
            permissions=set(permissions or []),
            parent_roles=set(parent_roles or []),
        )
        
        await self._store.save_role(role)
        logger.info(f"Defined role: {name}")
        
        return role
    
    async def get_role(self, name: str) -> Optional[Role]:
        """Get role by name."""
        return await self._store.get_role(name)
    
    async def add_permission_to_role(
        self,
        role_name: str,
        permission: str,
    ) -> Optional[Role]:
        """Add permission to role."""
        role = await self._store.get_role(role_name)
        
        if not role:
            raise RoleNotFoundError(f"Role not found: {role_name}")
        
        role.permissions.add(permission)
        await self._store.save_role(role)
        
        # Invalidate cache
        self._invalidate_cache()
        
        return role
    
    async def remove_permission_from_role(
        self,
        role_name: str,
        permission: str,
    ) -> Optional[Role]:
        """Remove permission from role."""
        role = await self._store.get_role(role_name)
        
        if not role:
            return None
        
        role.permissions.discard(permission)
        await self._store.save_role(role)
        
        self._invalidate_cache()
        
        return role
    
    # Policy management
    async def define_policy(
        self,
        name: str,
        effect: PermissionEffect = PermissionEffect.ALLOW,
        permissions: Optional[List[str]] = None,
        conditions: Optional[List[Condition]] = None,
        priority: int = 0,
        description: str = "",
    ) -> Policy:
        """Define a policy."""
        policy = Policy(
            name=name,
            effect=effect,
            permissions=set(permissions or []),
            conditions=conditions or [],
            priority=priority,
            description=description,
        )
        
        await self._store.save_policy(policy)
        logger.info(f"Defined policy: {name}")
        
        return policy
    
    async def attach_policy_to_role(
        self,
        role_name: str,
        policy_name: str,
    ) -> Optional[Role]:
        """Attach policy to role."""
        role = await self._store.get_role(role_name)
        
        if not role:
            return None
        
        if policy_name not in role.policies:
            role.policies.append(policy_name)
            await self._store.save_role(role)
        
        return role
    
    # Principal management
    async def create_principal(
        self,
        principal_id: str,
        type: str = "user",
        attributes: Optional[Dict[str, Any]] = None,
    ) -> Principal:
        """Create a principal."""
        principal = Principal(
            id=principal_id,
            type=type,
            attributes=attributes or {},
        )
        
        await self._store.save_principal(principal)
        return principal
    
    async def get_principal(self, principal_id: str) -> Optional[Principal]:
        """Get principal."""
        return await self._store.get_principal(principal_id)
    
    # Role assignment
    async def assign_role(
        self,
        principal_id: str,
        role_name: str,
        scope: Optional[str] = None,
        expires_at: Optional[datetime] = None,
        conditions: Optional[List[Condition]] = None,
    ) -> RoleAssignment:
        """Assign role to principal."""
        role = await self._store.get_role(role_name)
        
        if not role:
            raise RoleNotFoundError(f"Role not found: {role_name}")
        
        assignment = RoleAssignment(
            principal_id=principal_id,
            role_name=role_name,
            scope=scope,
            expires_at=expires_at,
            conditions=conditions or [],
        )
        
        await self._store.save_assignment(assignment)
        
        # Invalidate cache for principal
        self._invalidate_cache(principal_id)
        
        logger.info(f"Assigned role {role_name} to {principal_id}")
        
        return assignment
    
    async def revoke_role(
        self,
        principal_id: str,
        role_name: str,
    ) -> None:
        """Revoke role from principal."""
        await self._store.delete_assignment(principal_id, role_name)
        self._invalidate_cache(principal_id)
        
        logger.info(f"Revoked role {role_name} from {principal_id}")
    
    async def get_roles(self, principal_id: str) -> List[str]:
        """Get effective roles for principal."""
        assignments = await self._store.get_assignments(principal_id)
        now = datetime.utcnow()
        
        roles = []
        for assignment in assignments:
            # Check expiration
            if assignment.expires_at and assignment.expires_at < now:
                continue
            
            roles.append(assignment.role_name)
        
        return roles
    
    # Permission resolution
    async def _resolve_role_permissions(
        self,
        role_name: str,
        visited: Optional[Set[str]] = None,
    ) -> Set[str]:
        """Resolve all permissions for a role (including inherited)."""
        if visited is None:
            visited = set()
        
        if role_name in visited:
            return set()  # Avoid circular reference
        
        visited.add(role_name)
        
        role = await self._store.get_role(role_name)
        
        if not role:
            return set()
        
        permissions = set(role.permissions)
        
        # Get permissions from parent roles
        for parent_name in role.parent_roles:
            parent_perms = await self._resolve_role_permissions(parent_name, visited)
            permissions.update(parent_perms)
        
        # Get permissions from policies
        for policy_name in role.policies:
            policy = await self._store.get_policy(policy_name)
            if policy and policy.effect == PermissionEffect.ALLOW:
                permissions.update(policy.permissions)
        
        return permissions
    
    async def get_permissions(
        self,
        principal_id: str,
    ) -> Set[str]:
        """Get all effective permissions for principal."""
        # Check cache
        cache_key = principal_id
        if cache_key in self._permission_cache:
            cache_time = self._cache_updated.get(cache_key, datetime.min)
            if datetime.utcnow() - cache_time < self._cache_ttl:
                return self._permission_cache[cache_key]
        
        permissions: Set[str] = set()
        
        # Get principal
        principal = await self._store.get_principal(principal_id)
        if principal:
            permissions.update(principal.direct_permissions)
        
        # Get roles
        roles = await self.get_roles(principal_id)
        
        for role_name in roles:
            role_perms = await self._resolve_role_permissions(role_name)
            permissions.update(role_perms)
        
        # Update cache
        self._permission_cache[cache_key] = permissions
        self._cache_updated[cache_key] = datetime.utcnow()
        
        return permissions
    
    async def has_permission(
        self,
        principal_id: str,
        permission: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Check if principal has permission."""
        permissions = await self.get_permissions(principal_id)
        
        # Check direct match
        if permission in permissions:
            return True
        
        # Check wildcard matches
        for perm in permissions:
            if perm == "*":
                return True
            if perm.endswith(".*"):
                prefix = perm[:-2]
                if permission.startswith(prefix):
                    return True
        
        # Check policies with deny effect
        roles = await self.get_roles(principal_id)
        
        for role_name in roles:
            role = await self._store.get_role(role_name)
            if not role:
                continue
            
            for policy_name in role.policies:
                policy = await self._store.get_policy(policy_name)
                if not policy:
                    continue
                
                if policy.effect == PermissionEffect.DENY:
                    if policy.matches(permission, context):
                        return False
        
        return permission in permissions
    
    async def check_permission(
        self,
        principal_id: str,
        permission: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Check permission and raise if denied."""
        if not await self.has_permission(principal_id, permission, context):
            raise AccessDeniedError(
                f"Access denied for {permission}"
            )
    
    def _invalidate_cache(self, principal_id: Optional[str] = None) -> None:
        """Invalidate permission cache."""
        if principal_id:
            self._permission_cache.pop(principal_id, None)
            self._cache_updated.pop(principal_id, None)
        else:
            self._permission_cache.clear()
            self._cache_updated.clear()


# Global manager
_global_manager: Optional[PermissionManager] = None


def get_current_principal() -> Optional[Principal]:
    """Get current principal from context."""
    return _current_principal.get()


def set_current_principal(principal: Principal) -> contextvars.Token:
    """Set current principal in context."""
    return _current_principal.set(principal)


# Decorators
def require_permission(permission: str) -> Callable:
    """
    Decorator to require permission.
    
    Example:
        @require_permission("users.write")
        async def update_user(user_id: str, data: dict):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            principal = get_current_principal()
            
            if not principal:
                raise AccessDeniedError("No principal in context")
            
            manager = get_global_manager()
            await manager.check_permission(principal.id, permission)
            
            return await func(*args, **kwargs)
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            principal = get_current_principal()
            
            if not principal:
                raise AccessDeniedError("No principal in context")
            
            return func(*args, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


def require_role(role_name: str) -> Callable:
    """
    Decorator to require role.
    
    Example:
        @require_role("admin")
        async def admin_only():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            principal = get_current_principal()
            
            if not principal:
                raise AccessDeniedError("No principal in context")
            
            manager = get_global_manager()
            roles = await manager.get_roles(principal.id)
            
            if role_name not in roles:
                raise AccessDeniedError(f"Role required: {role_name}")
            
            return await func(*args, **kwargs)
        
        return async_wrapper
    
    return decorator


def require_any_permission(*permissions: str) -> Callable:
    """
    Decorator to require any of the specified permissions.
    
    Example:
        @require_any_permission("users.read", "users.admin")
        async def view_users():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            principal = get_current_principal()
            
            if not principal:
                raise AccessDeniedError("No principal in context")
            
            manager = get_global_manager()
            
            for perm in permissions:
                if await manager.has_permission(principal.id, perm):
                    return await func(*args, **kwargs)
            
            raise AccessDeniedError(f"One of these permissions required: {permissions}")
        
        return async_wrapper
    
    return decorator


# Factory functions
def create_permission_manager(
    store: Optional[PermissionStore] = None,
) -> PermissionManager:
    """Create permission manager."""
    return PermissionManager(store)


def create_principal(
    principal_id: str,
    type: str = "user",
    attributes: Optional[Dict[str, Any]] = None,
) -> Principal:
    """Create a principal."""
    return Principal(
        id=principal_id,
        type=type,
        attributes=attributes or {},
    )


def create_role(
    name: str,
    permissions: Optional[List[str]] = None,
    parent_roles: Optional[List[str]] = None,
    description: str = "",
) -> Role:
    """Create a role."""
    return Role(
        name=name,
        description=description,
        permissions=set(permissions or []),
        parent_roles=set(parent_roles or []),
    )


def create_policy(
    name: str,
    effect: PermissionEffect = PermissionEffect.ALLOW,
    permissions: Optional[List[str]] = None,
    priority: int = 0,
) -> Policy:
    """Create a policy."""
    return Policy(
        name=name,
        effect=effect,
        permissions=set(permissions or []),
        priority=priority,
    )


def create_condition(
    attribute: str,
    type: ConditionType,
    value: Any,
) -> Condition:
    """Create a condition."""
    return Condition(attribute=attribute, type=type, value=value)


def create_in_memory_store() -> InMemoryPermissionStore:
    """Create in-memory permission store."""
    return InMemoryPermissionStore()


def get_global_manager() -> PermissionManager:
    """Get global permission manager."""
    global _global_manager
    if _global_manager is None:
        _global_manager = create_permission_manager()
    return _global_manager


__all__ = [
    # Exceptions
    "PermissionError",
    "AccessDeniedError",
    "RoleNotFoundError",
    # Enums
    "PermissionEffect",
    "ConditionType",
    # Data classes
    "Permission",
    "Condition",
    "Policy",
    "Role",
    "Principal",
    "RoleAssignment",
    # Store
    "PermissionStore",
    "InMemoryPermissionStore",
    # Manager
    "PermissionManager",
    # Context
    "get_current_principal",
    "set_current_principal",
    # Decorators
    "require_permission",
    "require_role",
    "require_any_permission",
    # Factory functions
    "create_permission_manager",
    "create_principal",
    "create_role",
    "create_policy",
    "create_condition",
    "create_in_memory_store",
    "get_global_manager",
]
