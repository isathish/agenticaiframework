"""
Enterprise Permission Engine Module.

Fine-grained permissions, RBAC/ABAC support,
policy evaluation, and access control.

Example:
    # Create permission engine
    perms = create_permission_engine()
    
    # Define roles
    await perms.create_role(
        name="admin",
        permissions=["users:*", "posts:*"],
    )
    
    # Assign role
    await perms.assign_role(user_id="user_123", role="admin")
    
    # Check permission
    allowed = await perms.check(
        user_id="user_123",
        resource="users",
        action="delete",
    )
    
    # ABAC policy
    await perms.create_policy(
        name="own_posts",
        condition="resource.owner_id == subject.id",
        actions=["edit", "delete"],
    )
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
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

T = TypeVar('T')

logger = logging.getLogger(__name__)


class PermissionError(Exception):
    """Permission error."""
    pass


class AccessDeniedError(PermissionError):
    """Access denied."""
    pass


class RoleNotFoundError(PermissionError):
    """Role not found."""
    pass


class PolicyNotFoundError(PermissionError):
    """Policy not found."""
    pass


class Effect(str, Enum):
    """Policy effect."""
    ALLOW = "allow"
    DENY = "deny"


class PolicyType(str, Enum):
    """Policy type."""
    RBAC = "rbac"
    ABAC = "abac"
    CUSTOM = "custom"


@dataclass
class Permission:
    """Permission."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    resource: str = ""
    action: str = ""
    effect: Effect = Effect.ALLOW
    conditions: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def pattern(self) -> str:
        """Get permission pattern."""
        return f"{self.resource}:{self.action}"
    
    def matches(self, resource: str, action: str) -> bool:
        """Check if matches resource:action."""
        # Exact match
        if self.resource == resource and self.action == action:
            return True
        
        # Wildcard match
        if self.resource == "*" or self.resource == resource:
            if self.action == "*" or self.action == action:
                return True
        
        # Pattern match with wildcards
        res_pattern = self.resource.replace("*", ".*")
        act_pattern = self.action.replace("*", ".*")
        
        if re.match(f"^{res_pattern}$", resource):
            if re.match(f"^{act_pattern}$", action):
                return True
        
        return False


@dataclass
class Role:
    """Role."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    permissions: List[Permission] = field(default_factory=list)
    permission_patterns: List[str] = field(default_factory=list)
    parent_roles: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def __post_init__(self):
        # Parse permission patterns
        for pattern in self.permission_patterns:
            if ":" in pattern:
                resource, action = pattern.split(":", 1)
                self.permissions.append(Permission(
                    resource=resource,
                    action=action,
                ))


@dataclass
class Policy:
    """ABAC policy."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    effect: Effect = Effect.ALLOW
    resources: List[str] = field(default_factory=list)
    actions: List[str] = field(default_factory=list)
    condition: str = ""  # Expression
    priority: int = 0
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def evaluate_condition(
        self,
        subject: Dict[str, Any],
        resource: Dict[str, Any],
        context: Dict[str, Any],
    ) -> bool:
        """Evaluate condition."""
        if not self.condition:
            return True
        
        try:
            # Simple expression evaluation
            env = {
                "subject": subject,
                "resource": resource,
                "context": context,
                "datetime": datetime,
            }
            return eval(self.condition, {"__builtins__": {}}, env)
        except Exception as e:
            logger.error(f"Condition evaluation error: {e}")
            return False


@dataclass
class Subject:
    """Permission subject (user)."""
    id: str = ""
    roles: List[str] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)
    direct_permissions: List[Permission] = field(default_factory=list)


@dataclass
class Resource:
    """Resource."""
    type: str = ""
    id: str = ""
    owner_id: str = ""
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AccessRequest:
    """Access request."""
    subject_id: str = ""
    resource_type: str = ""
    resource_id: str = ""
    action: str = ""
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AccessDecision:
    """Access decision."""
    allowed: bool = False
    effect: Effect = Effect.DENY
    matched_policies: List[str] = field(default_factory=list)
    matched_roles: List[str] = field(default_factory=list)
    reason: str = ""
    evaluated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class PermissionStats:
    """Permission statistics."""
    total_checks: int = 0
    allowed_count: int = 0
    denied_count: int = 0
    total_roles: int = 0
    total_policies: int = 0
    by_resource: Dict[str, int] = field(default_factory=dict)


# Role store
class RoleStore(ABC):
    """Role storage."""
    
    @abstractmethod
    async def save(self, role: Role) -> None:
        """Save role."""
        pass
    
    @abstractmethod
    async def get(self, role_id: str) -> Optional[Role]:
        """Get role."""
        pass
    
    @abstractmethod
    async def get_by_name(self, name: str) -> Optional[Role]:
        """Get by name."""
        pass
    
    @abstractmethod
    async def list(self) -> List[Role]:
        """List roles."""
        pass
    
    @abstractmethod
    async def delete(self, role_id: str) -> bool:
        """Delete role."""
        pass


class InMemoryRoleStore(RoleStore):
    """In-memory role store."""
    
    def __init__(self):
        self._roles: Dict[str, Role] = {}
        self._by_name: Dict[str, str] = {}
    
    async def save(self, role: Role) -> None:
        self._roles[role.id] = role
        self._by_name[role.name] = role.id
    
    async def get(self, role_id: str) -> Optional[Role]:
        return self._roles.get(role_id)
    
    async def get_by_name(self, name: str) -> Optional[Role]:
        role_id = self._by_name.get(name)
        if role_id:
            return self._roles.get(role_id)
        return None
    
    async def list(self) -> List[Role]:
        return list(self._roles.values())
    
    async def delete(self, role_id: str) -> bool:
        role = self._roles.pop(role_id, None)
        if role:
            self._by_name.pop(role.name, None)
            return True
        return False


# Policy store
class PolicyStore(ABC):
    """Policy storage."""
    
    @abstractmethod
    async def save(self, policy: Policy) -> None:
        """Save policy."""
        pass
    
    @abstractmethod
    async def get(self, policy_id: str) -> Optional[Policy]:
        """Get policy."""
        pass
    
    @abstractmethod
    async def list(
        self,
        resource: Optional[str] = None,
        action: Optional[str] = None,
    ) -> List[Policy]:
        """List policies."""
        pass
    
    @abstractmethod
    async def delete(self, policy_id: str) -> bool:
        """Delete policy."""
        pass


class InMemoryPolicyStore(PolicyStore):
    """In-memory policy store."""
    
    def __init__(self):
        self._policies: Dict[str, Policy] = {}
    
    async def save(self, policy: Policy) -> None:
        self._policies[policy.id] = policy
    
    async def get(self, policy_id: str) -> Optional[Policy]:
        return self._policies.get(policy_id)
    
    async def list(
        self,
        resource: Optional[str] = None,
        action: Optional[str] = None,
    ) -> List[Policy]:
        policies = []
        for policy in self._policies.values():
            if not policy.enabled:
                continue
            if resource and resource not in policy.resources and "*" not in policy.resources:
                continue
            if action and action not in policy.actions and "*" not in policy.actions:
                continue
            policies.append(policy)
        
        return sorted(policies, key=lambda p: p.priority, reverse=True)
    
    async def delete(self, policy_id: str) -> bool:
        return self._policies.pop(policy_id, None) is not None


# Subject store
class SubjectStore(ABC):
    """Subject storage."""
    
    @abstractmethod
    async def save(self, subject: Subject) -> None:
        """Save subject."""
        pass
    
    @abstractmethod
    async def get(self, subject_id: str) -> Optional[Subject]:
        """Get subject."""
        pass
    
    @abstractmethod
    async def add_role(self, subject_id: str, role: str) -> None:
        """Add role to subject."""
        pass
    
    @abstractmethod
    async def remove_role(self, subject_id: str, role: str) -> None:
        """Remove role from subject."""
        pass


class InMemorySubjectStore(SubjectStore):
    """In-memory subject store."""
    
    def __init__(self):
        self._subjects: Dict[str, Subject] = {}
    
    async def save(self, subject: Subject) -> None:
        self._subjects[subject.id] = subject
    
    async def get(self, subject_id: str) -> Optional[Subject]:
        return self._subjects.get(subject_id)
    
    async def add_role(self, subject_id: str, role: str) -> None:
        subject = self._subjects.get(subject_id)
        if subject and role not in subject.roles:
            subject.roles.append(role)
    
    async def remove_role(self, subject_id: str, role: str) -> None:
        subject = self._subjects.get(subject_id)
        if subject and role in subject.roles:
            subject.roles.remove(role)


# Permission engine
class PermissionEngine:
    """Permission engine."""
    
    def __init__(
        self,
        role_store: Optional[RoleStore] = None,
        policy_store: Optional[PolicyStore] = None,
        subject_store: Optional[SubjectStore] = None,
    ):
        self._roles = role_store or InMemoryRoleStore()
        self._policies = policy_store or InMemoryPolicyStore()
        self._subjects = subject_store or InMemorySubjectStore()
        self._stats = PermissionStats()
        self._hooks: Dict[str, List[Callable]] = {}
        self._cache: Dict[str, AccessDecision] = {}
    
    # Role management
    async def create_role(
        self,
        name: str,
        permissions: Optional[List[str]] = None,
        description: str = "",
        parent_roles: Optional[List[str]] = None,
        **kwargs,
    ) -> Role:
        """Create role."""
        role = Role(
            name=name,
            description=description,
            permission_patterns=permissions or [],
            parent_roles=parent_roles or [],
            **kwargs,
        )
        await self._roles.save(role)
        
        self._stats.total_roles += 1
        
        logger.info(f"Role created: {name}")
        
        return role
    
    async def get_role(
        self,
        role_id: Optional[str] = None,
        name: Optional[str] = None,
    ) -> Optional[Role]:
        """Get role."""
        if role_id:
            return await self._roles.get(role_id)
        if name:
            return await self._roles.get_by_name(name)
        return None
    
    async def list_roles(self) -> List[Role]:
        """List roles."""
        return await self._roles.list()
    
    async def update_role(self, role: Role) -> Role:
        """Update role."""
        await self._roles.save(role)
        self._cache.clear()
        return role
    
    async def delete_role(self, role_id: str) -> bool:
        """Delete role."""
        result = await self._roles.delete(role_id)
        if result:
            self._stats.total_roles -= 1
            self._cache.clear()
        return result
    
    # Policy management
    async def create_policy(
        self,
        name: str,
        resources: Optional[List[str]] = None,
        actions: Optional[List[str]] = None,
        condition: str = "",
        effect: Effect = Effect.ALLOW,
        priority: int = 0,
        **kwargs,
    ) -> Policy:
        """Create policy."""
        policy = Policy(
            name=name,
            resources=resources or ["*"],
            actions=actions or ["*"],
            condition=condition,
            effect=effect,
            priority=priority,
            **kwargs,
        )
        await self._policies.save(policy)
        
        self._stats.total_policies += 1
        
        logger.info(f"Policy created: {name}")
        
        return policy
    
    async def get_policy(self, policy_id: str) -> Optional[Policy]:
        """Get policy."""
        return await self._policies.get(policy_id)
    
    async def list_policies(
        self,
        resource: Optional[str] = None,
        action: Optional[str] = None,
    ) -> List[Policy]:
        """List policies."""
        return await self._policies.list(resource, action)
    
    async def delete_policy(self, policy_id: str) -> bool:
        """Delete policy."""
        result = await self._policies.delete(policy_id)
        if result:
            self._stats.total_policies -= 1
            self._cache.clear()
        return result
    
    # Subject management
    async def get_subject(self, subject_id: str) -> Optional[Subject]:
        """Get subject."""
        return await self._subjects.get(subject_id)
    
    async def assign_role(
        self,
        user_id: str,
        role: str,
    ) -> None:
        """Assign role to user."""
        subject = await self._subjects.get(user_id)
        if not subject:
            subject = Subject(id=user_id)
            await self._subjects.save(subject)
        
        await self._subjects.add_role(user_id, role)
        self._cache.clear()
        
        logger.info(f"Role assigned: {role} -> {user_id}")
    
    async def revoke_role(
        self,
        user_id: str,
        role: str,
    ) -> None:
        """Revoke role from user."""
        await self._subjects.remove_role(user_id, role)
        self._cache.clear()
        
        logger.info(f"Role revoked: {role} -> {user_id}")
    
    async def get_user_roles(self, user_id: str) -> List[str]:
        """Get user roles."""
        subject = await self._subjects.get(user_id)
        if subject:
            return subject.roles
        return []
    
    async def get_user_permissions(self, user_id: str) -> List[Permission]:
        """Get user permissions."""
        subject = await self._subjects.get(user_id)
        if not subject:
            return []
        
        permissions: List[Permission] = list(subject.direct_permissions)
        
        for role_name in subject.roles:
            role = await self._roles.get_by_name(role_name)
            if role:
                permissions.extend(role.permissions)
                # Include parent roles
                for parent in role.parent_roles:
                    parent_role = await self._roles.get_by_name(parent)
                    if parent_role:
                        permissions.extend(parent_role.permissions)
        
        return permissions
    
    # Permission checking
    async def check(
        self,
        user_id: str,
        resource: str,
        action: str,
        resource_data: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Check permission."""
        decision = await self.evaluate(
            user_id=user_id,
            resource=resource,
            action=action,
            resource_data=resource_data,
            context=context,
        )
        return decision.allowed
    
    async def evaluate(
        self,
        user_id: str,
        resource: str,
        action: str,
        resource_data: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> AccessDecision:
        """Evaluate access request."""
        self._stats.total_checks += 1
        
        # Check cache
        cache_key = f"{user_id}:{resource}:{action}"
        if cache_key in self._cache and not resource_data:
            return self._cache[cache_key]
        
        decision = AccessDecision()
        
        # Get subject
        subject = await self._subjects.get(user_id)
        subject_data = {"id": user_id}
        if subject:
            subject_data["roles"] = subject.roles
            subject_data.update(subject.attributes)
        
        # Check RBAC
        if subject:
            permissions = await self.get_user_permissions(user_id)
            for perm in permissions:
                if perm.matches(resource, action):
                    if perm.effect == Effect.DENY:
                        decision.allowed = False
                        decision.effect = Effect.DENY
                        decision.reason = "Explicit deny"
                        self._stats.denied_count += 1
                        return decision
                    
                    decision.allowed = True
                    decision.effect = Effect.ALLOW
                    decision.matched_roles = subject.roles
        
        # Check ABAC policies
        policies = await self._policies.list(resource, action)
        for policy in policies:
            if policy.evaluate_condition(
                subject=subject_data,
                resource=resource_data or {},
                context=context or {},
            ):
                decision.matched_policies.append(policy.name)
                
                if policy.effect == Effect.DENY:
                    decision.allowed = False
                    decision.effect = Effect.DENY
                    decision.reason = f"Policy: {policy.name}"
                    self._stats.denied_count += 1
                    return decision
                
                decision.allowed = True
                decision.effect = Effect.ALLOW
        
        # Update stats
        if decision.allowed:
            self._stats.allowed_count += 1
            self._stats.by_resource[resource] = (
                self._stats.by_resource.get(resource, 0) + 1
            )
        else:
            self._stats.denied_count += 1
            decision.reason = decision.reason or "No matching permission"
        
        # Cache result
        if not resource_data:
            self._cache[cache_key] = decision
        
        return decision
    
    async def require(
        self,
        user_id: str,
        resource: str,
        action: str,
        **kwargs,
    ) -> None:
        """Require permission (raises if denied)."""
        allowed = await self.check(
            user_id=user_id,
            resource=resource,
            action=action,
            **kwargs,
        )
        if not allowed:
            raise AccessDeniedError(
                f"Access denied: {user_id} cannot {action} {resource}"
            )
    
    # Decorator
    def requires(
        self,
        resource: str,
        action: str,
    ) -> Callable:
        """Permission decorator."""
        def decorator(func: Callable) -> Callable:
            async def wrapper(*args, user_id: str = "", **kwargs):
                await self.require(
                    user_id=user_id,
                    resource=resource,
                    action=action,
                )
                return await func(*args, **kwargs)
            return wrapper
        return decorator
    
    # Grant/revoke direct permissions
    async def grant(
        self,
        user_id: str,
        resource: str,
        action: str,
        effect: Effect = Effect.ALLOW,
    ) -> Permission:
        """Grant permission to user."""
        subject = await self._subjects.get(user_id)
        if not subject:
            subject = Subject(id=user_id)
        
        perm = Permission(
            resource=resource,
            action=action,
            effect=effect,
        )
        subject.direct_permissions.append(perm)
        await self._subjects.save(subject)
        
        self._cache.clear()
        
        logger.info(f"Permission granted: {resource}:{action} -> {user_id}")
        
        return perm
    
    async def deny(
        self,
        user_id: str,
        resource: str,
        action: str,
    ) -> Permission:
        """Deny permission to user."""
        return await self.grant(
            user_id=user_id,
            resource=resource,
            action=action,
            effect=Effect.DENY,
        )
    
    # Bulk operations
    async def check_bulk(
        self,
        user_id: str,
        checks: List[Dict[str, str]],
    ) -> Dict[str, bool]:
        """Bulk permission check."""
        results = {}
        for check in checks:
            key = f"{check['resource']}:{check['action']}"
            results[key] = await self.check(
                user_id=user_id,
                resource=check["resource"],
                action=check["action"],
            )
        return results
    
    # Stats
    def get_stats(self) -> PermissionStats:
        """Get statistics."""
        return self._stats
    
    def clear_cache(self) -> None:
        """Clear permission cache."""
        self._cache.clear()


# Factory functions
def create_permission_engine(
    role_store: Optional[RoleStore] = None,
    policy_store: Optional[PolicyStore] = None,
) -> PermissionEngine:
    """Create permission engine."""
    return PermissionEngine(
        role_store=role_store,
        policy_store=policy_store,
    )


def create_role(
    name: str,
    permissions: Optional[List[str]] = None,
    **kwargs,
) -> Role:
    """Create role."""
    return Role(
        name=name,
        permission_patterns=permissions or [],
        **kwargs,
    )


def create_policy(
    name: str,
    resources: Optional[List[str]] = None,
    actions: Optional[List[str]] = None,
    condition: str = "",
    **kwargs,
) -> Policy:
    """Create policy."""
    return Policy(
        name=name,
        resources=resources or ["*"],
        actions=actions or ["*"],
        condition=condition,
        **kwargs,
    )


def create_permission(
    resource: str,
    action: str,
    effect: Effect = Effect.ALLOW,
) -> Permission:
    """Create permission."""
    return Permission(
        resource=resource,
        action=action,
        effect=effect,
    )


__all__ = [
    # Exceptions
    "PermissionError",
    "AccessDeniedError",
    "RoleNotFoundError",
    "PolicyNotFoundError",
    # Enums
    "Effect",
    "PolicyType",
    # Data classes
    "Permission",
    "Role",
    "Policy",
    "Subject",
    "Resource",
    "AccessRequest",
    "AccessDecision",
    "PermissionStats",
    # Stores
    "RoleStore",
    "InMemoryRoleStore",
    "PolicyStore",
    "InMemoryPolicyStore",
    "SubjectStore",
    "InMemorySubjectStore",
    # Engine
    "PermissionEngine",
    # Factory functions
    "create_permission_engine",
    "create_role",
    "create_policy",
    "create_permission",
]
