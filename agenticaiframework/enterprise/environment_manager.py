"""
Enterprise Environment Manager Module.

Environment management, promotion workflows,
configuration synchronization, and feature branches.

Example:
    # Create environment manager
    env_mgr = create_environment_manager()
    
    # Create environments
    await env_mgr.create_environment(
        name="development",
        tier=EnvironmentTier.DEV,
    )
    await env_mgr.create_environment(
        name="staging",
        tier=EnvironmentTier.STAGING,
    )
    await env_mgr.create_environment(
        name="production",
        tier=EnvironmentTier.PRODUCTION,
    )
    
    # Promote to next environment
    await env_mgr.promote("development", "staging")
    
    # Create feature environment
    await env_mgr.create_feature_env(
        name="feature-auth",
        base_env="development",
    )
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
)

logger = logging.getLogger(__name__)


class EnvironmentError(Exception):
    """Environment error."""
    pass


class EnvironmentNotFoundError(EnvironmentError):
    """Environment not found error."""
    pass


class PromotionError(EnvironmentError):
    """Promotion error."""
    pass


class EnvironmentTier(str, Enum):
    """Environment tier."""
    DEV = "dev"
    DEVELOPMENT = "development"
    TEST = "test"
    QA = "qa"
    STAGING = "staging"
    UAT = "uat"
    PREPROD = "preprod"
    PRODUCTION = "production"
    PROD = "prod"


class EnvironmentStatus(str, Enum):
    """Environment status."""
    CREATING = "creating"
    ACTIVE = "active"
    UPDATING = "updating"
    PROMOTING = "promoting"
    DEGRADED = "degraded"
    INACTIVE = "inactive"
    DELETING = "deleting"


class PromotionStatus(str, Enum):
    """Promotion status."""
    PENDING = "pending"
    APPROVED = "approved"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class ConfigScope(str, Enum):
    """Configuration scope."""
    APPLICATION = "application"
    SERVICE = "service"
    INFRASTRUCTURE = "infrastructure"
    SECRET = "secret"
    FEATURE = "feature"


@dataclass
class EnvironmentConfig:
    """Environment configuration."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    key: str = ""
    value: Any = None
    scope: ConfigScope = ConfigScope.APPLICATION
    
    # Metadata
    description: str = ""
    sensitive: bool = False
    encrypted: bool = False
    
    # Versioning
    version: int = 1
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Environment:
    """Environment."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    tier: EnvironmentTier = EnvironmentTier.DEV
    
    # Status
    status: EnvironmentStatus = EnvironmentStatus.CREATING
    
    # Configuration
    configs: Dict[str, EnvironmentConfig] = field(default_factory=dict)
    variables: Dict[str, str] = field(default_factory=dict)
    
    # Hierarchy
    parent_env: Optional[str] = None
    is_feature_env: bool = False
    base_branch: str = "main"
    feature_branch: str = ""
    
    # Resources
    resources: Dict[str, Any] = field(default_factory=dict)
    endpoints: Dict[str, str] = field(default_factory=dict)
    
    # Metadata
    description: str = ""
    owner: str = ""
    tags: List[str] = field(default_factory=list)
    labels: Dict[str, str] = field(default_factory=dict)
    
    # Constraints
    requires_approval: bool = False
    allowed_promoters: List[str] = field(default_factory=list)
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    last_promotion_at: Optional[datetime] = None


@dataclass
class PromotionRequest:
    """Promotion request."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    # Environments
    source_env: str = ""
    target_env: str = ""
    
    # Status
    status: PromotionStatus = PromotionStatus.PENDING
    
    # Details
    artifact_version: str = ""
    config_snapshot: Dict[str, Any] = field(default_factory=dict)
    
    # Approval
    requested_by: str = ""
    approved_by: Optional[str] = None
    
    # Notes
    notes: str = ""
    error_message: str = ""
    
    # Rollback
    rollback_snapshot: Dict[str, Any] = field(default_factory=dict)
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    approved_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class PromotionPipeline:
    """Promotion pipeline."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    
    # Stages (environment names in order)
    stages: List[str] = field(default_factory=list)
    
    # Configuration
    auto_promote: bool = False
    require_approval_at: List[str] = field(default_factory=list)
    
    # Metadata
    description: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ConfigDiff:
    """Configuration difference."""
    added: Dict[str, Any] = field(default_factory=dict)
    removed: Dict[str, Any] = field(default_factory=dict)
    modified: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    unchanged: int = 0


@dataclass
class EnvironmentStats:
    """Environment statistics."""
    total_environments: int = 0
    active_environments: int = 0
    feature_environments: int = 0
    pending_promotions: int = 0
    total_configs: int = 0


# Environment store
class EnvironmentStore(ABC):
    """Environment storage."""
    
    @abstractmethod
    async def save(self, environment: Environment) -> None:
        pass
    
    @abstractmethod
    async def get(self, env_id: str) -> Optional[Environment]:
        pass
    
    @abstractmethod
    async def get_by_name(self, name: str) -> Optional[Environment]:
        pass
    
    @abstractmethod
    async def list_all(self) -> List[Environment]:
        pass
    
    @abstractmethod
    async def delete(self, env_id: str) -> bool:
        pass


class InMemoryEnvironmentStore(EnvironmentStore):
    """In-memory environment store."""
    
    def __init__(self):
        self._environments: Dict[str, Environment] = {}
        self._by_name: Dict[str, str] = {}
    
    async def save(self, environment: Environment) -> None:
        self._environments[environment.id] = environment
        self._by_name[environment.name] = environment.id
    
    async def get(self, env_id: str) -> Optional[Environment]:
        return self._environments.get(env_id)
    
    async def get_by_name(self, name: str) -> Optional[Environment]:
        env_id = self._by_name.get(name)
        return self._environments.get(env_id) if env_id else None
    
    async def list_all(self) -> List[Environment]:
        return list(self._environments.values())
    
    async def delete(self, env_id: str) -> bool:
        env = self._environments.pop(env_id, None)
        if env:
            self._by_name.pop(env.name, None)
            return True
        return False


# Promotion store
class PromotionStore(ABC):
    """Promotion storage."""
    
    @abstractmethod
    async def save(self, promotion: PromotionRequest) -> None:
        pass
    
    @abstractmethod
    async def get(self, promotion_id: str) -> Optional[PromotionRequest]:
        pass
    
    @abstractmethod
    async def list_pending(self) -> List[PromotionRequest]:
        pass
    
    @abstractmethod
    async def list_by_env(self, env_name: str) -> List[PromotionRequest]:
        pass


class InMemoryPromotionStore(PromotionStore):
    """In-memory promotion store."""
    
    def __init__(self):
        self._promotions: Dict[str, PromotionRequest] = {}
        self._by_env: Dict[str, List[str]] = defaultdict(list)
    
    async def save(self, promotion: PromotionRequest) -> None:
        self._promotions[promotion.id] = promotion
        
        key = f"{promotion.source_env}:{promotion.target_env}"
        if promotion.id not in self._by_env[key]:
            self._by_env[key].append(promotion.id)
    
    async def get(self, promotion_id: str) -> Optional[PromotionRequest]:
        return self._promotions.get(promotion_id)
    
    async def list_pending(self) -> List[PromotionRequest]:
        return [
            p for p in self._promotions.values()
            if p.status == PromotionStatus.PENDING
        ]
    
    async def list_by_env(self, env_name: str) -> List[PromotionRequest]:
        result = []
        for key, ids in self._by_env.items():
            if env_name in key:
                for pid in ids:
                    p = self._promotions.get(pid)
                    if p:
                        result.append(p)
        return result


# Config synchronizer
class ConfigSynchronizer:
    """Configuration synchronizer."""
    
    async def sync_configs(
        self,
        source: Environment,
        target: Environment,
        overwrite: bool = False,
    ) -> ConfigDiff:
        """Synchronize configurations."""
        diff = ConfigDiff()
        
        source_keys = set(source.configs.keys())
        target_keys = set(target.configs.keys())
        
        # Added keys
        for key in source_keys - target_keys:
            diff.added[key] = source.configs[key].value
            if overwrite:
                target.configs[key] = EnvironmentConfig(
                    key=key,
                    value=source.configs[key].value,
                    scope=source.configs[key].scope,
                    sensitive=source.configs[key].sensitive,
                )
        
        # Removed keys
        for key in target_keys - source_keys:
            diff.removed[key] = target.configs[key].value
        
        # Modified keys
        for key in source_keys & target_keys:
            source_val = source.configs[key].value
            target_val = target.configs[key].value
            
            if source_val != target_val:
                diff.modified[key] = {
                    "source": source_val,
                    "target": target_val,
                }
                if overwrite:
                    target.configs[key].value = source_val
                    target.configs[key].version += 1
                    target.configs[key].updated_at = datetime.utcnow()
            else:
                diff.unchanged += 1
        
        return diff
    
    async def diff_environments(
        self,
        env1: Environment,
        env2: Environment,
    ) -> ConfigDiff:
        """Get difference between environments."""
        return await self.sync_configs(env1, env2, overwrite=False)


# Promoter
class Promoter(ABC):
    """Promotion handler."""
    
    @abstractmethod
    async def execute(
        self,
        source: Environment,
        target: Environment,
        request: PromotionRequest,
    ) -> bool:
        pass
    
    async def validate(
        self,
        source: Environment,
        target: Environment,
    ) -> List[str]:
        """Validate promotion. Returns list of issues."""
        return []
    
    async def rollback(
        self,
        target: Environment,
        snapshot: Dict[str, Any],
    ) -> bool:
        """Rollback promotion."""
        return True


class DefaultPromoter(Promoter):
    """Default promoter."""
    
    def __init__(self, synchronizer: ConfigSynchronizer):
        self._synchronizer = synchronizer
    
    async def execute(
        self,
        source: Environment,
        target: Environment,
        request: PromotionRequest,
    ) -> bool:
        """Execute promotion."""
        # Sync configurations
        await self._synchronizer.sync_configs(source, target, overwrite=True)
        
        # Sync variables
        target.variables.update(source.variables)
        
        # Update timestamps
        target.last_promotion_at = datetime.utcnow()
        target.updated_at = datetime.utcnow()
        
        return True
    
    async def validate(
        self,
        source: Environment,
        target: Environment,
    ) -> List[str]:
        """Validate promotion."""
        issues = []
        
        if source.status != EnvironmentStatus.ACTIVE:
            issues.append(f"Source environment not active: {source.name}")
        
        if target.status not in (EnvironmentStatus.ACTIVE, EnvironmentStatus.DEGRADED):
            issues.append(f"Target environment not active: {target.name}")
        
        # Check tier order
        tier_order = list(EnvironmentTier)
        source_idx = tier_order.index(source.tier) if source.tier in tier_order else -1
        target_idx = tier_order.index(target.tier) if target.tier in tier_order else -1
        
        if source_idx > target_idx:
            issues.append("Cannot promote from higher tier to lower tier")
        
        return issues


# Environment manager
class EnvironmentManager:
    """Environment manager."""
    
    def __init__(
        self,
        env_store: Optional[EnvironmentStore] = None,
        promotion_store: Optional[PromotionStore] = None,
        promoter: Optional[Promoter] = None,
    ):
        self._env_store = env_store or InMemoryEnvironmentStore()
        self._promotion_store = promotion_store or InMemoryPromotionStore()
        
        self._synchronizer = ConfigSynchronizer()
        self._promoter = promoter or DefaultPromoter(self._synchronizer)
        
        self._pipelines: Dict[str, PromotionPipeline] = {}
        self._listeners: List[Callable] = []
    
    async def create_environment(
        self,
        name: str,
        tier: Union[str, EnvironmentTier] = EnvironmentTier.DEV,
        description: str = "",
        owner: str = "",
        variables: Optional[Dict[str, str]] = None,
        requires_approval: bool = False,
        **kwargs,
    ) -> Environment:
        """Create environment."""
        if isinstance(tier, str):
            tier = EnvironmentTier(tier)
        
        # Check if exists
        existing = await self._env_store.get_by_name(name)
        if existing:
            raise EnvironmentError(f"Environment already exists: {name}")
        
        # Higher tiers require approval by default
        if tier in (EnvironmentTier.PRODUCTION, EnvironmentTier.PROD, EnvironmentTier.UAT):
            requires_approval = True
        
        environment = Environment(
            name=name,
            tier=tier,
            description=description,
            owner=owner,
            variables=variables or {},
            requires_approval=requires_approval,
            status=EnvironmentStatus.ACTIVE,
            **kwargs,
        )
        
        await self._env_store.save(environment)
        
        logger.info(f"Environment created: {name}")
        await self._notify("created", environment)
        
        return environment
    
    async def get_environment(
        self,
        name_or_id: str,
    ) -> Optional[Environment]:
        """Get environment."""
        env = await self._env_store.get(name_or_id)
        if env:
            return env
        return await self._env_store.get_by_name(name_or_id)
    
    async def list_environments(
        self,
        tier: Optional[EnvironmentTier] = None,
        status: Optional[EnvironmentStatus] = None,
        feature_only: bool = False,
    ) -> List[Environment]:
        """List environments."""
        envs = await self._env_store.list_all()
        
        if tier:
            envs = [e for e in envs if e.tier == tier]
        
        if status:
            envs = [e for e in envs if e.status == status]
        
        if feature_only:
            envs = [e for e in envs if e.is_feature_env]
        
        return sorted(envs, key=lambda e: (e.tier.value, e.name))
    
    async def update_environment(
        self,
        name: str,
        **updates,
    ) -> Optional[Environment]:
        """Update environment."""
        env = await self.get_environment(name)
        
        if not env:
            return None
        
        for key, value in updates.items():
            if hasattr(env, key):
                setattr(env, key, value)
        
        env.updated_at = datetime.utcnow()
        await self._env_store.save(env)
        
        return env
    
    async def delete_environment(
        self,
        name: str,
    ) -> bool:
        """Delete environment."""
        env = await self.get_environment(name)
        
        if not env:
            return False
        
        if env.tier in (EnvironmentTier.PRODUCTION, EnvironmentTier.PROD):
            raise EnvironmentError("Cannot delete production environment")
        
        return await self._env_store.delete(env.id)
    
    async def set_config(
        self,
        env_name: str,
        key: str,
        value: Any,
        scope: Union[str, ConfigScope] = ConfigScope.APPLICATION,
        sensitive: bool = False,
        description: str = "",
    ) -> Optional[EnvironmentConfig]:
        """Set configuration value."""
        env = await self.get_environment(env_name)
        
        if not env:
            return None
        
        if isinstance(scope, str):
            scope = ConfigScope(scope)
        
        if key in env.configs:
            config = env.configs[key]
            config.value = value
            config.version += 1
            config.updated_at = datetime.utcnow()
        else:
            config = EnvironmentConfig(
                key=key,
                value=value,
                scope=scope,
                sensitive=sensitive,
                description=description,
            )
            env.configs[key] = config
        
        env.updated_at = datetime.utcnow()
        await self._env_store.save(env)
        
        return config
    
    async def get_config(
        self,
        env_name: str,
        key: str,
    ) -> Optional[Any]:
        """Get configuration value."""
        env = await self.get_environment(env_name)
        
        if env and key in env.configs:
            return env.configs[key].value
        
        return None
    
    async def get_all_configs(
        self,
        env_name: str,
        scope: Optional[ConfigScope] = None,
    ) -> Dict[str, Any]:
        """Get all configurations."""
        env = await self.get_environment(env_name)
        
        if not env:
            return {}
        
        configs = env.configs
        
        if scope:
            configs = {k: v for k, v in configs.items() if v.scope == scope}
        
        return {k: v.value for k, v in configs.items() if not v.sensitive}
    
    async def promote(
        self,
        source_env: str,
        target_env: str,
        requested_by: str = "",
        notes: str = "",
    ) -> PromotionRequest:
        """Promote from source to target environment."""
        source = await self.get_environment(source_env)
        target = await self.get_environment(target_env)
        
        if not source:
            raise EnvironmentNotFoundError(f"Source not found: {source_env}")
        
        if not target:
            raise EnvironmentNotFoundError(f"Target not found: {target_env}")
        
        # Validate
        issues = await self._promoter.validate(source, target)
        if issues:
            raise PromotionError(f"Validation failed: {', '.join(issues)}")
        
        # Create snapshot for rollback
        rollback_snapshot = {
            "configs": {k: v.value for k, v in target.configs.items()},
            "variables": target.variables.copy(),
        }
        
        # Create promotion request
        request = PromotionRequest(
            source_env=source_env,
            target_env=target_env,
            requested_by=requested_by,
            notes=notes,
            config_snapshot={k: v.value for k, v in source.configs.items()},
            rollback_snapshot=rollback_snapshot,
        )
        
        # Check if approval required
        if target.requires_approval:
            request.status = PromotionStatus.PENDING
            await self._promotion_store.save(request)
            logger.info(f"Promotion pending approval: {source_env} -> {target_env}")
            return request
        
        # Execute immediately
        request.status = PromotionStatus.IN_PROGRESS
        
        try:
            source.status = EnvironmentStatus.PROMOTING
            target.status = EnvironmentStatus.UPDATING
            
            await self._env_store.save(source)
            await self._env_store.save(target)
            
            success = await self._promoter.execute(source, target, request)
            
            if success:
                request.status = PromotionStatus.COMPLETED
                request.completed_at = datetime.utcnow()
            else:
                request.status = PromotionStatus.FAILED
                request.error_message = "Promotion failed"
        
        except Exception as e:
            request.status = PromotionStatus.FAILED
            request.error_message = str(e)
            logger.error(f"Promotion failed: {e}")
        
        finally:
            source.status = EnvironmentStatus.ACTIVE
            target.status = EnvironmentStatus.ACTIVE
            
            await self._env_store.save(source)
            await self._env_store.save(target)
            await self._promotion_store.save(request)
        
        await self._notify("promoted", request)
        
        return request
    
    async def approve_promotion(
        self,
        promotion_id: str,
        approved_by: str,
    ) -> Optional[PromotionRequest]:
        """Approve pending promotion."""
        request = await self._promotion_store.get(promotion_id)
        
        if not request:
            return None
        
        if request.status != PromotionStatus.PENDING:
            raise PromotionError(f"Promotion not pending: {promotion_id}")
        
        request.approved_by = approved_by
        request.approved_at = datetime.utcnow()
        request.status = PromotionStatus.APPROVED
        
        await self._promotion_store.save(request)
        
        # Execute promotion
        source = await self.get_environment(request.source_env)
        target = await self.get_environment(request.target_env)
        
        if source and target:
            request.status = PromotionStatus.IN_PROGRESS
            
            try:
                success = await self._promoter.execute(source, target, request)
                
                if success:
                    request.status = PromotionStatus.COMPLETED
                    request.completed_at = datetime.utcnow()
                else:
                    request.status = PromotionStatus.FAILED
            
            except Exception as e:
                request.status = PromotionStatus.FAILED
                request.error_message = str(e)
            
            finally:
                await self._env_store.save(source)
                await self._env_store.save(target)
                await self._promotion_store.save(request)
        
        return request
    
    async def rollback_promotion(
        self,
        promotion_id: str,
    ) -> bool:
        """Rollback a promotion."""
        request = await self._promotion_store.get(promotion_id)
        
        if not request:
            return False
        
        target = await self.get_environment(request.target_env)
        
        if not target:
            return False
        
        # Restore from snapshot
        snapshot = request.rollback_snapshot
        
        if snapshot:
            # Restore configs
            for key, value in snapshot.get("configs", {}).items():
                if key in target.configs:
                    target.configs[key].value = value
                else:
                    target.configs[key] = EnvironmentConfig(key=key, value=value)
            
            # Restore variables
            target.variables = snapshot.get("variables", {})
            
            target.updated_at = datetime.utcnow()
            await self._env_store.save(target)
        
        request.status = PromotionStatus.ROLLED_BACK
        await self._promotion_store.save(request)
        
        logger.info(f"Promotion rolled back: {promotion_id}")
        
        return True
    
    async def create_feature_env(
        self,
        name: str,
        base_env: str,
        feature_branch: str = "",
        owner: str = "",
        ttl_hours: Optional[int] = None,
    ) -> Environment:
        """Create feature environment."""
        base = await self.get_environment(base_env)
        
        if not base:
            raise EnvironmentNotFoundError(f"Base environment not found: {base_env}")
        
        environment = Environment(
            name=name,
            tier=EnvironmentTier.DEV,
            status=EnvironmentStatus.ACTIVE,
            is_feature_env=True,
            parent_env=base.id,
            base_branch=base.name,
            feature_branch=feature_branch or name,
            owner=owner,
            description=f"Feature environment based on {base_env}",
        )
        
        # Copy configs from base
        for key, config in base.configs.items():
            environment.configs[key] = EnvironmentConfig(
                key=config.key,
                value=config.value,
                scope=config.scope,
                sensitive=config.sensitive,
            )
        
        # Copy variables
        environment.variables = base.variables.copy()
        
        await self._env_store.save(environment)
        
        logger.info(f"Feature environment created: {name}")
        
        return environment
    
    async def sync_feature_env(
        self,
        feature_env: str,
    ) -> ConfigDiff:
        """Sync feature environment with base."""
        env = await self.get_environment(feature_env)
        
        if not env or not env.is_feature_env:
            raise EnvironmentError(f"Not a feature environment: {feature_env}")
        
        base = await self._env_store.get(env.parent_env or "")
        
        if not base:
            raise EnvironmentNotFoundError("Base environment not found")
        
        return await self._synchronizer.sync_configs(base, env, overwrite=False)
    
    async def create_pipeline(
        self,
        name: str,
        stages: List[str],
        auto_promote: bool = False,
        require_approval_at: Optional[List[str]] = None,
    ) -> PromotionPipeline:
        """Create promotion pipeline."""
        pipeline = PromotionPipeline(
            name=name,
            stages=stages,
            auto_promote=auto_promote,
            require_approval_at=require_approval_at or [],
        )
        
        self._pipelines[pipeline.id] = pipeline
        
        return pipeline
    
    async def compare_environments(
        self,
        env1_name: str,
        env2_name: str,
    ) -> ConfigDiff:
        """Compare two environments."""
        env1 = await self.get_environment(env1_name)
        env2 = await self.get_environment(env2_name)
        
        if not env1 or not env2:
            raise EnvironmentNotFoundError("Environment not found")
        
        return await self._synchronizer.diff_environments(env1, env2)
    
    async def get_pending_promotions(self) -> List[PromotionRequest]:
        """Get pending promotions."""
        return await self._promotion_store.list_pending()
    
    async def get_stats(self) -> EnvironmentStats:
        """Get statistics."""
        envs = await self._env_store.list_all()
        pending = await self._promotion_store.list_pending()
        
        total_configs = sum(len(e.configs) for e in envs)
        
        return EnvironmentStats(
            total_environments=len(envs),
            active_environments=len([e for e in envs if e.status == EnvironmentStatus.ACTIVE]),
            feature_environments=len([e for e in envs if e.is_feature_env]),
            pending_promotions=len(pending),
            total_configs=total_configs,
        )
    
    async def _notify(self, event: str, data: Any) -> None:
        """Notify listeners."""
        for listener in self._listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    await listener(event, data)
                else:
                    listener(event, data)
            except Exception as e:
                logger.error(f"Listener error: {e}")
    
    def add_listener(self, listener: Callable) -> None:
        """Add event listener."""
        self._listeners.append(listener)


# Factory functions
def create_environment_manager() -> EnvironmentManager:
    """Create environment manager."""
    return EnvironmentManager()


def create_environment(
    name: str,
    tier: EnvironmentTier = EnvironmentTier.DEV,
    **kwargs,
) -> Environment:
    """Create environment object."""
    return Environment(name=name, tier=tier, **kwargs)


__all__ = [
    # Exceptions
    "EnvironmentError",
    "EnvironmentNotFoundError",
    "PromotionError",
    # Enums
    "EnvironmentTier",
    "EnvironmentStatus",
    "PromotionStatus",
    "ConfigScope",
    # Data classes
    "EnvironmentConfig",
    "Environment",
    "PromotionRequest",
    "PromotionPipeline",
    "ConfigDiff",
    "EnvironmentStats",
    # Stores
    "EnvironmentStore",
    "InMemoryEnvironmentStore",
    "PromotionStore",
    "InMemoryPromotionStore",
    # Components
    "ConfigSynchronizer",
    "Promoter",
    "DefaultPromoter",
    # Manager
    "EnvironmentManager",
    # Factory functions
    "create_environment_manager",
    "create_environment",
]
