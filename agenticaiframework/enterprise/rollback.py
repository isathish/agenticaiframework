"""
Enterprise Rollback Module.

Provides rollback strategies, version management, deployment recovery,
and automated rollback capabilities.

Example:
    # Create rollback manager
    manager = create_rollback_manager()
    
    # Register deployment
    await manager.register(
        name="api-service",
        version="2.0.0",
        artifacts={"image": "api:2.0.0"},
    )
    
    # Rollback to previous version
    result = await manager.rollback("api-service")
    
    # Or rollback to specific version
    result = await manager.rollback_to("api-service", "1.0.0")
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    TypeVar,
)

logger = logging.getLogger(__name__)

T = TypeVar('T')


class RollbackError(Exception):
    """Rollback error."""
    pass


class VersionNotFoundError(RollbackError):
    """Version not found."""
    pass


class RollbackFailedError(RollbackError):
    """Rollback failed."""
    pass


class NoVersionToRollbackError(RollbackError):
    """No previous version to rollback to."""
    pass


class RollbackStrategy(str, Enum):
    """Rollback strategy."""
    IMMEDIATE = "immediate"  # Instant rollback
    GRADUAL = "gradual"  # Gradual traffic shift
    CANARY = "canary"  # Canary-style rollback
    RECREATE = "recreate"  # Delete and recreate


class RollbackTrigger(str, Enum):
    """Rollback trigger."""
    MANUAL = "manual"
    HEALTH_CHECK = "health_check"
    METRIC_THRESHOLD = "metric_threshold"
    ERROR_RATE = "error_rate"
    LATENCY = "latency"
    SCHEDULED = "scheduled"


class VersionState(str, Enum):
    """Version state."""
    PENDING = "pending"
    DEPLOYING = "deploying"
    ACTIVE = "active"
    INACTIVE = "inactive"
    ROLLING_BACK = "rolling_back"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"
    DELETED = "deleted"


@dataclass
class RollbackPolicy:
    """Rollback policy configuration."""
    strategy: RollbackStrategy = RollbackStrategy.IMMEDIATE
    max_rollback_versions: int = 10
    auto_rollback_on_failure: bool = True
    health_check_interval_seconds: int = 10
    health_check_timeout_seconds: int = 30
    error_rate_threshold: float = 0.1
    latency_threshold_ms: float = 1000.0
    min_healthy_instances: int = 1
    rollback_timeout_seconds: int = 300


@dataclass
class VersionArtifacts:
    """Version artifacts."""
    image: Optional[str] = None
    config: Dict[str, Any] = field(default_factory=dict)
    env_vars: Dict[str, str] = field(default_factory=dict)
    files: List[str] = field(default_factory=list)
    checksum: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DeploymentVersion:
    """Deployment version."""
    version_id: str
    version: str
    artifacts: VersionArtifacts
    state: VersionState = VersionState.PENDING
    deployed_at: Optional[datetime] = None
    deactivated_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DeploymentHistory:
    """Deployment history."""
    deployment_name: str
    versions: List[DeploymentVersion] = field(default_factory=list)
    current_version: Optional[str] = None
    previous_version: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class RollbackContext:
    """Rollback context."""
    deployment_name: str
    from_version: str
    to_version: str
    trigger: RollbackTrigger
    strategy: RollbackStrategy
    started_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RollbackResult:
    """Rollback result."""
    success: bool
    deployment_name: str
    from_version: str
    to_version: str
    trigger: RollbackTrigger
    strategy: RollbackStrategy
    started_at: datetime
    completed_at: datetime = field(default_factory=datetime.now)
    duration_ms: float = 0.0
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthStatus:
    """Health status."""
    healthy: bool
    error_rate: float = 0.0
    avg_latency_ms: float = 0.0
    instance_count: int = 0
    healthy_instances: int = 0
    message: str = ""
    checked_at: datetime = field(default_factory=datetime.now)


class VersionStore(ABC):
    """Abstract version store."""
    
    @abstractmethod
    async def save_history(self, history: DeploymentHistory) -> None:
        """Save deployment history."""
        pass
    
    @abstractmethod
    async def get_history(
        self,
        deployment_name: str,
    ) -> Optional[DeploymentHistory]:
        """Get deployment history."""
        pass
    
    @abstractmethod
    async def list_histories(self) -> List[DeploymentHistory]:
        """List all deployment histories."""
        pass
    
    @abstractmethod
    async def delete_history(self, deployment_name: str) -> None:
        """Delete deployment history."""
        pass


class InMemoryVersionStore(VersionStore):
    """In-memory version store."""
    
    def __init__(self):
        self._histories: Dict[str, DeploymentHistory] = {}
        self._lock = asyncio.Lock()
    
    async def save_history(self, history: DeploymentHistory) -> None:
        async with self._lock:
            history.updated_at = datetime.now()
            self._histories[history.deployment_name] = history
    
    async def get_history(
        self,
        deployment_name: str,
    ) -> Optional[DeploymentHistory]:
        return self._histories.get(deployment_name)
    
    async def list_histories(self) -> List[DeploymentHistory]:
        return list(self._histories.values())
    
    async def delete_history(self, deployment_name: str) -> None:
        async with self._lock:
            self._histories.pop(deployment_name, None)


class HealthMonitor(ABC):
    """Abstract health monitor."""
    
    @abstractmethod
    async def check_health(
        self,
        deployment_name: str,
        version: str,
    ) -> HealthStatus:
        """Check health of a version."""
        pass


class DefaultHealthMonitor(HealthMonitor):
    """Default health monitor implementation."""
    
    def __init__(self):
        self._health_data: Dict[str, HealthStatus] = {}
    
    async def check_health(
        self,
        deployment_name: str,
        version: str,
    ) -> HealthStatus:
        key = f"{deployment_name}:{version}"
        
        return self._health_data.get(key, HealthStatus(
            healthy=True,
            error_rate=0.0,
            avg_latency_ms=50.0,
            instance_count=1,
            healthy_instances=1,
        ))
    
    def set_health(
        self,
        deployment_name: str,
        version: str,
        status: HealthStatus,
    ) -> None:
        """Set health status for testing."""
        key = f"{deployment_name}:{version}"
        self._health_data[key] = status


class RollbackExecutor(ABC):
    """Abstract rollback executor."""
    
    @abstractmethod
    async def execute(
        self,
        context: RollbackContext,
        from_artifacts: VersionArtifacts,
        to_artifacts: VersionArtifacts,
    ) -> bool:
        """Execute rollback."""
        pass


class DefaultRollbackExecutor(RollbackExecutor):
    """Default rollback executor."""
    
    async def execute(
        self,
        context: RollbackContext,
        from_artifacts: VersionArtifacts,
        to_artifacts: VersionArtifacts,
    ) -> bool:
        # Simulate rollback execution
        logger.info(
            f"Executing rollback: {context.deployment_name} "
            f"{context.from_version} -> {context.to_version}"
        )
        
        if context.strategy == RollbackStrategy.IMMEDIATE:
            await asyncio.sleep(0.1)  # Simulate instant switch
        
        elif context.strategy == RollbackStrategy.GRADUAL:
            # Gradual traffic shift
            for percent in range(10, 101, 10):
                logger.debug(f"Traffic shift: {percent}%")
                await asyncio.sleep(0.05)
        
        elif context.strategy == RollbackStrategy.CANARY:
            # Canary-style rollback
            await asyncio.sleep(0.2)
        
        elif context.strategy == RollbackStrategy.RECREATE:
            # Delete and recreate
            await asyncio.sleep(0.3)
        
        return True


class RollbackManager:
    """
    Rollback manager for deployment versions.
    """
    
    def __init__(
        self,
        store: Optional[VersionStore] = None,
        monitor: Optional[HealthMonitor] = None,
        executor: Optional[RollbackExecutor] = None,
        policy: Optional[RollbackPolicy] = None,
    ):
        self._store = store or InMemoryVersionStore()
        self._monitor = monitor or DefaultHealthMonitor()
        self._executor = executor or DefaultRollbackExecutor()
        self._policy = policy or RollbackPolicy()
        self._callbacks: Dict[str, List[Callable]] = {
            "before_rollback": [],
            "after_rollback": [],
            "on_failure": [],
        }
        self._monitoring_tasks: Dict[str, asyncio.Task] = {}
    
    async def register(
        self,
        name: str,
        version: str,
        artifacts: Optional[Dict[str, Any]] = None,
        auto_activate: bool = True,
    ) -> DeploymentVersion:
        """Register a new version."""
        history = await self._store.get_history(name)
        
        if not history:
            history = DeploymentHistory(deployment_name=name)
        
        # Create version
        dep_version = DeploymentVersion(
            version_id=f"v-{uuid.uuid4().hex[:8]}",
            version=version,
            artifacts=VersionArtifacts(**(artifacts or {})),
            state=VersionState.PENDING,
        )
        
        history.versions.append(dep_version)
        
        # Maintain max versions
        if len(history.versions) > self._policy.max_rollback_versions:
            # Remove oldest versions
            excess = len(history.versions) - self._policy.max_rollback_versions
            history.versions = history.versions[excess:]
        
        if auto_activate:
            await self._activate_version(history, dep_version)
        
        await self._store.save_history(history)
        
        logger.info(f"Registered version {version} for {name}")
        
        return dep_version
    
    async def _activate_version(
        self,
        history: DeploymentHistory,
        version: DeploymentVersion,
    ) -> None:
        """Activate a version."""
        # Deactivate current version
        if history.current_version:
            for v in history.versions:
                if v.version == history.current_version and v.state == VersionState.ACTIVE:
                    v.state = VersionState.INACTIVE
                    v.deactivated_at = datetime.now()
        
        # Activate new version
        history.previous_version = history.current_version
        history.current_version = version.version
        version.state = VersionState.ACTIVE
        version.deployed_at = datetime.now()
    
    async def rollback(
        self,
        deployment_name: str,
        trigger: RollbackTrigger = RollbackTrigger.MANUAL,
    ) -> RollbackResult:
        """Rollback to previous version."""
        history = await self._store.get_history(deployment_name)
        
        if not history:
            raise VersionNotFoundError(
                f"No history for deployment: {deployment_name}"
            )
        
        if not history.previous_version:
            raise NoVersionToRollbackError(
                f"No previous version for {deployment_name}"
            )
        
        return await self.rollback_to(
            deployment_name,
            history.previous_version,
            trigger,
        )
    
    async def rollback_to(
        self,
        deployment_name: str,
        target_version: str,
        trigger: RollbackTrigger = RollbackTrigger.MANUAL,
    ) -> RollbackResult:
        """Rollback to a specific version."""
        history = await self._store.get_history(deployment_name)
        
        if not history:
            raise VersionNotFoundError(
                f"No history for deployment: {deployment_name}"
            )
        
        # Find target version
        target = None
        current = None
        
        for v in history.versions:
            if v.version == target_version:
                target = v
            if v.version == history.current_version:
                current = v
        
        if not target:
            raise VersionNotFoundError(
                f"Version not found: {target_version}"
            )
        
        if not current:
            raise RollbackError(f"No current version for {deployment_name}")
        
        context = RollbackContext(
            deployment_name=deployment_name,
            from_version=current.version,
            to_version=target.version,
            trigger=trigger,
            strategy=self._policy.strategy,
        )
        
        # Execute callbacks
        for callback in self._callbacks["before_rollback"]:
            await callback(context)
        
        # Mark as rolling back
        current.state = VersionState.ROLLING_BACK
        await self._store.save_history(history)
        
        try:
            # Execute rollback
            success = await asyncio.wait_for(
                self._executor.execute(
                    context,
                    current.artifacts,
                    target.artifacts,
                ),
                timeout=self._policy.rollback_timeout_seconds,
            )
            
            if success:
                # Update states
                current.state = VersionState.ROLLED_BACK
                current.deactivated_at = datetime.now()
                target.state = VersionState.ACTIVE
                target.deployed_at = datetime.now()
                
                history.previous_version = history.current_version
                history.current_version = target.version
                
                await self._store.save_history(history)
                
                result = RollbackResult(
                    success=True,
                    deployment_name=deployment_name,
                    from_version=current.version,
                    to_version=target.version,
                    trigger=trigger,
                    strategy=self._policy.strategy,
                    started_at=context.started_at,
                    completed_at=datetime.now(),
                    duration_ms=(datetime.now() - context.started_at).total_seconds() * 1000,
                    message="Rollback successful",
                )
                
                # Execute callbacks
                for callback in self._callbacks["after_rollback"]:
                    await callback(result)
                
                logger.info(
                    f"Rollback complete: {deployment_name} "
                    f"{current.version} -> {target.version}"
                )
                
                return result
            else:
                raise RollbackFailedError("Executor returned failure")
        
        except Exception as e:
            current.state = VersionState.FAILED
            await self._store.save_history(history)
            
            result = RollbackResult(
                success=False,
                deployment_name=deployment_name,
                from_version=current.version,
                to_version=target.version,
                trigger=trigger,
                strategy=self._policy.strategy,
                started_at=context.started_at,
                completed_at=datetime.now(),
                duration_ms=(datetime.now() - context.started_at).total_seconds() * 1000,
                message=f"Rollback failed: {str(e)}",
            )
            
            # Execute failure callbacks
            for callback in self._callbacks["on_failure"]:
                await callback(result)
            
            raise
    
    async def start_monitoring(
        self,
        deployment_name: str,
        check_interval: Optional[int] = None,
    ) -> None:
        """Start health monitoring for auto-rollback."""
        if not self._policy.auto_rollback_on_failure:
            return
        
        if deployment_name in self._monitoring_tasks:
            return
        
        task = asyncio.create_task(
            self._monitor_loop(
                deployment_name,
                check_interval or self._policy.health_check_interval_seconds,
            )
        )
        self._monitoring_tasks[deployment_name] = task
    
    async def stop_monitoring(self, deployment_name: str) -> None:
        """Stop health monitoring."""
        if deployment_name in self._monitoring_tasks:
            self._monitoring_tasks[deployment_name].cancel()
            del self._monitoring_tasks[deployment_name]
    
    async def _monitor_loop(
        self,
        deployment_name: str,
        interval: int,
    ) -> None:
        """Health monitoring loop."""
        consecutive_failures = 0
        
        while True:
            try:
                history = await self._store.get_history(deployment_name)
                
                if not history or not history.current_version:
                    await asyncio.sleep(interval)
                    continue
                
                health = await self._monitor.check_health(
                    deployment_name,
                    history.current_version,
                )
                
                # Check health thresholds
                should_rollback = False
                trigger = RollbackTrigger.HEALTH_CHECK
                
                if not health.healthy:
                    consecutive_failures += 1
                    if consecutive_failures >= 3:
                        should_rollback = True
                
                elif health.error_rate > self._policy.error_rate_threshold:
                    trigger = RollbackTrigger.ERROR_RATE
                    should_rollback = True
                
                elif health.avg_latency_ms > self._policy.latency_threshold_ms:
                    trigger = RollbackTrigger.LATENCY
                    should_rollback = True
                
                elif health.healthy_instances < self._policy.min_healthy_instances:
                    should_rollback = True
                
                else:
                    consecutive_failures = 0
                
                if should_rollback and history.previous_version:
                    logger.warning(
                        f"Auto-rollback triggered for {deployment_name}: {trigger}"
                    )
                    
                    try:
                        await self.rollback(deployment_name, trigger)
                    except NoVersionToRollbackError:
                        pass
                
                await asyncio.sleep(interval)
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitor error: {e}")
                await asyncio.sleep(interval)
    
    def on_before_rollback(
        self,
        callback: Callable[[RollbackContext], Awaitable[None]],
    ) -> None:
        """Register before rollback callback."""
        self._callbacks["before_rollback"].append(callback)
    
    def on_after_rollback(
        self,
        callback: Callable[[RollbackResult], Awaitable[None]],
    ) -> None:
        """Register after rollback callback."""
        self._callbacks["after_rollback"].append(callback)
    
    def on_failure(
        self,
        callback: Callable[[RollbackResult], Awaitable[None]],
    ) -> None:
        """Register failure callback."""
        self._callbacks["on_failure"].append(callback)
    
    async def get_history(
        self,
        deployment_name: str,
    ) -> Optional[DeploymentHistory]:
        """Get deployment history."""
        return await self._store.get_history(deployment_name)
    
    async def get_versions(
        self,
        deployment_name: str,
    ) -> List[DeploymentVersion]:
        """Get all versions for a deployment."""
        history = await self._store.get_history(deployment_name)
        return history.versions if history else []
    
    async def get_current_version(
        self,
        deployment_name: str,
    ) -> Optional[DeploymentVersion]:
        """Get current active version."""
        history = await self._store.get_history(deployment_name)
        
        if not history or not history.current_version:
            return None
        
        for v in history.versions:
            if v.version == history.current_version:
                return v
        
        return None


class TransactionRollback:
    """
    Transaction-style rollback context.
    """
    
    def __init__(
        self,
        manager: RollbackManager,
        deployment_name: str,
        version: str,
    ):
        self._manager = manager
        self._deployment_name = deployment_name
        self._version = version
        self._committed = False
    
    async def __aenter__(self) -> DeploymentVersion:
        return await self._manager.register(
            self._deployment_name,
            self._version,
            auto_activate=True,
        )
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None and not self._committed:
            # Rollback on exception
            try:
                await self._manager.rollback(
                    self._deployment_name,
                    RollbackTrigger.MANUAL,
                )
            except NoVersionToRollbackError:
                pass
    
    def commit(self) -> None:
        """Commit the transaction (prevent rollback)."""
        self._committed = True


# Decorators
def with_rollback(
    deployment_name: str,
    version: Optional[str] = None,
    manager: Optional[RollbackManager] = None,
) -> Callable:
    """
    Decorator that rolls back on failure.
    
    Example:
        @with_rollback("my-service", version="2.0.0")
        async def deploy():
            ...
    """
    _manager = manager or RollbackManager()
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            ver = version or kwargs.get("version", "1.0.0")
            
            async with TransactionRollback(
                _manager,
                deployment_name,
                ver,
            ) as txn:
                result = await func(*args, **kwargs)
                # If no exception, implicitly commit
                return result
        
        return wrapper
    
    return decorator


def auto_rollback(
    deployment_name: str,
    manager: Optional[RollbackManager] = None,
) -> Callable:
    """
    Decorator that enables auto-rollback monitoring.
    
    Example:
        @auto_rollback("my-service")
        async def run_service():
            ...
    """
    _manager = manager or RollbackManager()
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            await _manager.start_monitoring(deployment_name)
            
            try:
                return await func(*args, **kwargs)
            finally:
                await _manager.stop_monitoring(deployment_name)
        
        return wrapper
    
    return decorator


def rollback_on_error(
    errors: Optional[List[type]] = None,
    manager: Optional[RollbackManager] = None,
) -> Callable:
    """
    Decorator that rolls back on specific errors.
    
    Example:
        @rollback_on_error(errors=[ValueError, RuntimeError])
        async def risky_operation(deployment_name: str):
            ...
    """
    _manager = manager or RollbackManager()
    _errors = tuple(errors or [Exception])
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            deployment_name = kwargs.get("deployment_name") or (
                args[0] if args else None
            )
            
            try:
                return await func(*args, **kwargs)
            except _errors:
                if deployment_name:
                    try:
                        await _manager.rollback(
                            deployment_name,
                            RollbackTrigger.MANUAL,
                        )
                    except (NoVersionToRollbackError, VersionNotFoundError):
                        pass
                raise
        
        return wrapper
    
    return decorator


# Factory functions
def create_rollback_manager(
    strategy: RollbackStrategy = RollbackStrategy.IMMEDIATE,
    max_versions: int = 10,
    auto_rollback: bool = True,
    error_rate_threshold: float = 0.1,
) -> RollbackManager:
    """Create a rollback manager."""
    policy = RollbackPolicy(
        strategy=strategy,
        max_rollback_versions=max_versions,
        auto_rollback_on_failure=auto_rollback,
        error_rate_threshold=error_rate_threshold,
    )
    
    return RollbackManager(policy=policy)


def create_rollback_policy(
    strategy: RollbackStrategy = RollbackStrategy.IMMEDIATE,
    max_versions: int = 10,
    auto_rollback: bool = True,
) -> RollbackPolicy:
    """Create a rollback policy."""
    return RollbackPolicy(
        strategy=strategy,
        max_rollback_versions=max_versions,
        auto_rollback_on_failure=auto_rollback,
    )


def create_health_monitor() -> DefaultHealthMonitor:
    """Create a health monitor."""
    return DefaultHealthMonitor()


__all__ = [
    # Exceptions
    "RollbackError",
    "VersionNotFoundError",
    "RollbackFailedError",
    "NoVersionToRollbackError",
    # Enums
    "RollbackStrategy",
    "RollbackTrigger",
    "VersionState",
    # Data classes
    "RollbackPolicy",
    "VersionArtifacts",
    "DeploymentVersion",
    "DeploymentHistory",
    "RollbackContext",
    "RollbackResult",
    "HealthStatus",
    # Abstract classes
    "VersionStore",
    "HealthMonitor",
    "RollbackExecutor",
    # Implementations
    "InMemoryVersionStore",
    "DefaultHealthMonitor",
    "DefaultRollbackExecutor",
    # Core classes
    "RollbackManager",
    "TransactionRollback",
    # Decorators
    "with_rollback",
    "auto_rollback",
    "rollback_on_error",
    # Factory functions
    "create_rollback_manager",
    "create_rollback_policy",
    "create_health_monitor",
]
