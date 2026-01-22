"""
Enterprise RBAC - Role-Based Access Control.

Provides fine-grained access control for agents, tools,
resources, and operations.

Features:
- Role management
- Permission policies
- Resource-level access
- Inheritance support
- Policy evaluation
"""

import asyncio
import functools
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Type

logger = logging.getLogger(__name__)


# =============================================================================
# Actions and Resources
# =============================================================================

class Action(Enum):
    """Standard RBAC actions."""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    EXECUTE = "execute"
    MANAGE = "manage"
    
    # Agent-specific
    RUN_AGENT = "run_agent"
    CONFIGURE_AGENT = "configure_agent"
    VIEW_AGENT = "view_agent"
    
    # Tool-specific
    USE_TOOL = "use_tool"
    REGISTER_TOOL = "register_tool"
    
    # LLM-specific
    CALL_LLM = "call_llm"
    CONFIGURE_LLM = "configure_llm"
    
    # Workflow-specific
    RUN_WORKFLOW = "run_workflow"
    VIEW_WORKFLOW = "view_workflow"
    
    # Admin
    MANAGE_USERS = "manage_users"
    MANAGE_ROLES = "manage_roles"
    MANAGE_POLICIES = "manage_policies"
    VIEW_AUDIT = "view_audit"
    
    # Wildcard
    ALL = "*"


class ResourceType(Enum):
    """Standard resource types."""
    AGENT = "agent"
    TOOL = "tool"
    WORKFLOW = "workflow"
    LLM = "llm"
    MEMORY = "memory"
    SECRET = "secret"
    CONFIG = "config"
    AUDIT = "audit"
    USER = "user"
    ROLE = "role"
    POLICY = "policy"
    ALL = "*"


# =============================================================================
# Permission
# =============================================================================

@dataclass
class Permission:
    """A permission grant or denial."""
    action: Action
    resource_type: ResourceType
    resource_id: Optional[str] = None  # None means all resources of type
    conditions: Dict[str, Any] = field(default_factory=dict)
    
    def matches(
        self,
        action: Action,
        resource_type: ResourceType,
        resource_id: Optional[str] = None,
    ) -> bool:
        """Check if permission matches the request."""
        # Check action
        if self.action != Action.ALL and self.action != action:
            return False
        
        # Check resource type
        if self.resource_type != ResourceType.ALL and self.resource_type != resource_type:
            return False
        
        # Check resource ID
        if self.resource_id and self.resource_id != resource_id:
            return False
        
        return True


# =============================================================================
# Role
# =============================================================================

@dataclass
class Role:
    """A role with permissions."""
    name: str
    description: str = ""
    permissions: List[Permission] = field(default_factory=list)
    parent_roles: List[str] = field(default_factory=list)  # Inheritance
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def has_permission(
        self,
        action: Action,
        resource_type: ResourceType,
        resource_id: Optional[str] = None,
    ) -> bool:
        """Check if role has the specified permission."""
        for perm in self.permissions:
            if perm.matches(action, resource_type, resource_id):
                return True
        return False


# =============================================================================
# Built-in Roles
# =============================================================================

ROLE_ADMIN = Role(
    name="admin",
    description="Full administrative access",
    permissions=[
        Permission(Action.ALL, ResourceType.ALL),
    ],
)

ROLE_OPERATOR = Role(
    name="operator",
    description="Operational access to agents and workflows",
    permissions=[
        Permission(Action.RUN_AGENT, ResourceType.AGENT),
        Permission(Action.VIEW_AGENT, ResourceType.AGENT),
        Permission(Action.RUN_WORKFLOW, ResourceType.WORKFLOW),
        Permission(Action.VIEW_WORKFLOW, ResourceType.WORKFLOW),
        Permission(Action.USE_TOOL, ResourceType.TOOL),
        Permission(Action.CALL_LLM, ResourceType.LLM),
        Permission(Action.READ, ResourceType.MEMORY),
        Permission(Action.READ, ResourceType.CONFIG),
    ],
)

ROLE_DEVELOPER = Role(
    name="developer",
    description="Development access",
    permissions=[
        Permission(Action.ALL, ResourceType.AGENT),
        Permission(Action.ALL, ResourceType.TOOL),
        Permission(Action.ALL, ResourceType.WORKFLOW),
        Permission(Action.CALL_LLM, ResourceType.LLM),
        Permission(Action.CONFIGURE_LLM, ResourceType.LLM),
        Permission(Action.ALL, ResourceType.MEMORY),
        Permission(Action.READ, ResourceType.CONFIG),
    ],
)

ROLE_VIEWER = Role(
    name="viewer",
    description="Read-only access",
    permissions=[
        Permission(Action.VIEW_AGENT, ResourceType.AGENT),
        Permission(Action.VIEW_WORKFLOW, ResourceType.WORKFLOW),
        Permission(Action.READ, ResourceType.CONFIG),
    ],
)

ROLE_AGENT = Role(
    name="agent",
    description="Permissions for AI agents",
    permissions=[
        Permission(Action.USE_TOOL, ResourceType.TOOL),
        Permission(Action.CALL_LLM, ResourceType.LLM),
        Permission(Action.READ, ResourceType.MEMORY),
        Permission(Action.UPDATE, ResourceType.MEMORY),
    ],
)

BUILTIN_ROLES = {
    "admin": ROLE_ADMIN,
    "operator": ROLE_OPERATOR,
    "developer": ROLE_DEVELOPER,
    "viewer": ROLE_VIEWER,
    "agent": ROLE_AGENT,
}


# =============================================================================
# Principal (User/Agent)
# =============================================================================

@dataclass
class Principal:
    """A user or agent with roles."""
    id: str
    name: str
    principal_type: str = "user"  # user, agent, service
    roles: List[str] = field(default_factory=list)
    direct_permissions: List[Permission] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Policy
# =============================================================================

@dataclass
class Policy:
    """An access control policy."""
    name: str
    description: str = ""
    
    # Matching criteria
    principals: List[str] = field(default_factory=list)  # Principal IDs or "*"
    roles: List[str] = field(default_factory=list)  # Role names
    actions: List[Action] = field(default_factory=list)
    resource_types: List[ResourceType] = field(default_factory=list)
    resource_ids: List[str] = field(default_factory=list)
    
    # Conditions
    conditions: Dict[str, Any] = field(default_factory=dict)
    
    # Effect
    allow: bool = True
    priority: int = 0  # Higher priority policies evaluated first
    
    def matches(
        self,
        principal: Principal,
        action: Action,
        resource_type: ResourceType,
        resource_id: Optional[str] = None,
    ) -> bool:
        """Check if policy matches the request."""
        # Check principal
        if self.principals and "*" not in self.principals:
            if principal.id not in self.principals:
                return False
        
        # Check roles
        if self.roles:
            if not any(r in principal.roles for r in self.roles):
                return False
        
        # Check action
        if self.actions and Action.ALL not in self.actions:
            if action not in self.actions:
                return False
        
        # Check resource type
        if self.resource_types and ResourceType.ALL not in self.resource_types:
            if resource_type not in self.resource_types:
                return False
        
        # Check resource ID
        if self.resource_ids and resource_id:
            if resource_id not in self.resource_ids:
                return False
        
        return True


# =============================================================================
# Access Decision
# =============================================================================

@dataclass
class AccessDecision:
    """Result of an access control decision."""
    allowed: bool
    reason: str = ""
    matched_policy: Optional[str] = None
    matched_role: Optional[str] = None
    evaluated_at: datetime = field(default_factory=datetime.now)


# =============================================================================
# RBAC Manager
# =============================================================================

class RBACManager:
    """
    Role-Based Access Control manager.
    
    Usage:
        >>> rbac = RBACManager()
        >>> 
        >>> # Create user
        >>> user = Principal(id="user-1", name="John", roles=["developer"])
        >>> rbac.add_principal(user)
        >>> 
        >>> # Check access
        >>> decision = rbac.check_access(
        ...     principal=user,
        ...     action=Action.RUN_AGENT,
        ...     resource_type=ResourceType.AGENT,
        ...     resource_id="agent-123",
        ... )
        >>> 
        >>> if decision.allowed:
        ...     run_agent()
    """
    
    def __init__(self):
        self._roles: Dict[str, Role] = dict(BUILTIN_ROLES)
        self._principals: Dict[str, Principal] = {}
        self._policies: List[Policy] = []
        self._lock = asyncio.Lock()
    
    # Role management
    def add_role(self, role: Role):
        """Add or update a role."""
        self._roles[role.name] = role
    
    def get_role(self, name: str) -> Optional[Role]:
        """Get a role by name."""
        return self._roles.get(name)
    
    def delete_role(self, name: str):
        """Delete a role."""
        if name in BUILTIN_ROLES:
            raise ValueError(f"Cannot delete built-in role: {name}")
        if name in self._roles:
            del self._roles[name]
    
    def list_roles(self) -> List[Role]:
        """List all roles."""
        return list(self._roles.values())
    
    # Principal management
    def add_principal(self, principal: Principal):
        """Add or update a principal."""
        self._principals[principal.id] = principal
    
    def get_principal(self, id: str) -> Optional[Principal]:
        """Get a principal by ID."""
        return self._principals.get(id)
    
    def delete_principal(self, id: str):
        """Delete a principal."""
        if id in self._principals:
            del self._principals[id]
    
    def assign_role(self, principal_id: str, role_name: str):
        """Assign a role to a principal."""
        principal = self._principals.get(principal_id)
        if principal and role_name not in principal.roles:
            principal.roles.append(role_name)
    
    def revoke_role(self, principal_id: str, role_name: str):
        """Revoke a role from a principal."""
        principal = self._principals.get(principal_id)
        if principal and role_name in principal.roles:
            principal.roles.remove(role_name)
    
    # Policy management
    def add_policy(self, policy: Policy):
        """Add a policy."""
        self._policies.append(policy)
        self._policies.sort(key=lambda p: -p.priority)
    
    def delete_policy(self, name: str):
        """Delete a policy by name."""
        self._policies = [p for p in self._policies if p.name != name]
    
    def list_policies(self) -> List[Policy]:
        """List all policies."""
        return list(self._policies)
    
    # Access control
    def check_access(
        self,
        principal: Principal,
        action: Action,
        resource_type: ResourceType,
        resource_id: Optional[str] = None,
        context: Dict[str, Any] = None,
    ) -> AccessDecision:
        """
        Check if principal has access.
        
        Evaluation order:
        1. Explicit deny policies
        2. Explicit allow policies
        3. Role-based permissions
        4. Direct permissions
        5. Default deny
        """
        # Check policies first (in priority order)
        for policy in self._policies:
            if policy.matches(principal, action, resource_type, resource_id):
                # Check conditions
                if self._evaluate_conditions(policy.conditions, context):
                    return AccessDecision(
                        allowed=policy.allow,
                        reason=f"Policy '{policy.name}' {'allows' if policy.allow else 'denies'} access",
                        matched_policy=policy.name,
                    )
        
        # Check role-based permissions
        for role_name in principal.roles:
            role = self._roles.get(role_name)
            
            if role:
                # Check parent roles recursively
                all_roles = self._get_role_hierarchy(role_name)
                
                for r_name in all_roles:
                    r = self._roles.get(r_name)
                    if r and r.has_permission(action, resource_type, resource_id):
                        return AccessDecision(
                            allowed=True,
                            reason=f"Role '{r_name}' grants permission",
                            matched_role=r_name,
                        )
        
        # Check direct permissions
        for perm in principal.direct_permissions:
            if perm.matches(action, resource_type, resource_id):
                return AccessDecision(
                    allowed=True,
                    reason="Direct permission grants access",
                )
        
        # Default deny
        return AccessDecision(
            allowed=False,
            reason="No matching permission found",
        )
    
    def _get_role_hierarchy(self, role_name: str, visited: Set[str] = None) -> List[str]:
        """Get role and all parent roles."""
        if visited is None:
            visited = set()
        
        if role_name in visited:
            return []
        
        visited.add(role_name)
        result = [role_name]
        
        role = self._roles.get(role_name)
        if role:
            for parent in role.parent_roles:
                result.extend(self._get_role_hierarchy(parent, visited))
        
        return result
    
    def _evaluate_conditions(
        self,
        conditions: Dict[str, Any],
        context: Dict[str, Any] = None,
    ) -> bool:
        """Evaluate policy conditions."""
        if not conditions:
            return True
        
        context = context or {}
        
        for key, expected in conditions.items():
            actual = context.get(key)
            
            if isinstance(expected, dict):
                # Complex condition
                if "eq" in expected and actual != expected["eq"]:
                    return False
                if "ne" in expected and actual == expected["ne"]:
                    return False
                if "in" in expected and actual not in expected["in"]:
                    return False
                if "contains" in expected and expected["contains"] not in str(actual):
                    return False
            else:
                # Simple equality
                if actual != expected:
                    return False
        
        return True
    
    def require_permission(
        self,
        action: Action,
        resource_type: ResourceType,
        resource_id: Optional[str] = None,
    ):
        """
        Decorator to require permission for a function.
        
        Usage:
            >>> @rbac.require_permission(Action.RUN_AGENT, ResourceType.AGENT)
            >>> async def run_agent(principal: Principal, agent_id: str):
            ...     ...
        """
        def decorator(fn: Callable):
            @functools.wraps(fn)
            async def wrapper(principal: Principal, *args, **kwargs):
                decision = self.check_access(
                    principal=principal,
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id or kwargs.get("resource_id"),
                )
                
                if not decision.allowed:
                    raise PermissionError(
                        f"Access denied: {decision.reason}"
                    )
                
                return await fn(principal, *args, **kwargs)
            
            return wrapper
        return decorator


# =============================================================================
# Current Principal Context
# =============================================================================

import contextvars

_current_principal: contextvars.ContextVar[Optional[Principal]] = contextvars.ContextVar(
    "current_principal",
    default=None,
)


def get_current_principal() -> Optional[Principal]:
    """Get the current principal from context."""
    return _current_principal.get()


def set_current_principal(principal: Principal):
    """Set the current principal in context."""
    _current_principal.set(principal)


class PrincipalContext:
    """Context manager for setting current principal."""
    
    def __init__(self, principal: Principal):
        self.principal = principal
        self._token = None
    
    def __enter__(self):
        self._token = _current_principal.set(self.principal)
        return self
    
    def __exit__(self, *args):
        _current_principal.reset(self._token)
    
    async def __aenter__(self):
        return self.__enter__()
    
    async def __aexit__(self, *args):
        self.__exit__(*args)


# =============================================================================
# Global RBAC Manager
# =============================================================================

_global_rbac: Optional[RBACManager] = None


def get_rbac_manager() -> RBACManager:
    """Get the global RBAC manager."""
    global _global_rbac
    
    if _global_rbac is None:
        _global_rbac = RBACManager()
    
    return _global_rbac


def set_rbac_manager(rbac: RBACManager):
    """Set the global RBAC manager."""
    global _global_rbac
    _global_rbac = rbac


# Convenience functions
def check_access(
    action: Action,
    resource_type: ResourceType,
    resource_id: Optional[str] = None,
) -> bool:
    """Check access for current principal."""
    principal = get_current_principal()
    
    if not principal:
        return False
    
    decision = get_rbac_manager().check_access(
        principal=principal,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
    )
    
    return decision.allowed


def require_access(
    action: Action,
    resource_type: ResourceType,
    resource_id: Optional[str] = None,
):
    """Decorator requiring access for current principal."""
    def decorator(fn: Callable):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            if not check_access(action, resource_type, resource_id):
                raise PermissionError(f"Access denied for {action.value} on {resource_type.value}")
            return await fn(*args, **kwargs)
        return wrapper
    return decorator
