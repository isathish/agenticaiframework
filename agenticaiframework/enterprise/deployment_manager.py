"""
Enterprise Deployment Manager Module.

Continuous deployment, blue-green deployments,
rolling updates, and canary releases.

Example:
    # Create deployment manager
    deployer = create_deployment_manager()
    
    # Create deployment
    deployment = await deployer.create(
        name="api-v2",
        version="2.0.0",
        strategy=DeploymentStrategy.BLUE_GREEN,
    )
    
    # Deploy
    await deployer.deploy(deployment.id)
    
    # Rollback if needed
    await deployer.rollback(deployment.id)
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    Callable,
    Coroutine,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    Tuple,
    TypeVar,
    Union,
)

T = TypeVar('T')

logger = logging.getLogger(__name__)


class DeploymentError(Exception):
    """Deployment error."""
    pass


class DeploymentFailed(DeploymentError):
    """Deployment failed."""
    pass


class RollbackFailed(DeploymentError):
    """Rollback failed."""
    pass


class DeploymentStrategy(str, Enum):
    """Deployment strategy."""
    ROLLING = "rolling"
    BLUE_GREEN = "blue_green"
    CANARY = "canary"
    RECREATE = "recreate"
    A_B_TEST = "a_b_test"


class DeploymentStatus(str, Enum):
    """Deployment status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    CANCELLED = "cancelled"


class HealthCheckStatus(str, Enum):
    """Health check status."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class DeploymentTarget:
    """Deployment target."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    host: str = ""
    port: int = 0
    weight: int = 1
    health_endpoint: str = "/health"
    status: HealthCheckStatus = HealthCheckStatus.UNKNOWN
    version: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DeploymentConfig:
    """Deployment configuration."""
    name: str = ""
    version: str = ""
    strategy: DeploymentStrategy = DeploymentStrategy.ROLLING
    replicas: int = 3
    max_surge: int = 1
    max_unavailable: int = 0
    canary_percentage: int = 10
    health_check_interval: int = 10
    health_check_timeout: int = 5
    rollback_on_failure: bool = True
    auto_promote: bool = False
    promotion_delay: int = 300  # seconds
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Deployment:
    """Deployment."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    version: str = ""
    previous_version: Optional[str] = None
    strategy: DeploymentStrategy = DeploymentStrategy.ROLLING
    status: DeploymentStatus = DeploymentStatus.PENDING
    config: DeploymentConfig = field(default_factory=DeploymentConfig)
    targets: List[DeploymentTarget] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    rolled_back_at: Optional[datetime] = None
    progress: int = 0
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DeploymentEvent:
    """Deployment event."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    deployment_id: str = ""
    event_type: str = ""
    message: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DeploymentStats:
    """Deployment statistics."""
    total_deployments: int = 0
    successful_deployments: int = 0
    failed_deployments: int = 0
    rollbacks: int = 0
    avg_duration: float = 0.0


# Deployment store
class DeploymentStore(ABC):
    """Deployment storage."""
    
    @abstractmethod
    async def save(self, deployment: Deployment) -> None:
        pass
    
    @abstractmethod
    async def get(self, deployment_id: str) -> Optional[Deployment]:
        pass
    
    @abstractmethod
    async def delete(self, deployment_id: str) -> bool:
        pass
    
    @abstractmethod
    async def list_all(self) -> List[Deployment]:
        pass
    
    @abstractmethod
    async def add_event(self, event: DeploymentEvent) -> None:
        pass
    
    @abstractmethod
    async def get_events(self, deployment_id: str) -> List[DeploymentEvent]:
        pass


class InMemoryDeploymentStore(DeploymentStore):
    """In-memory deployment store."""
    
    def __init__(self):
        self._deployments: Dict[str, Deployment] = {}
        self._events: Dict[str, List[DeploymentEvent]] = {}
    
    async def save(self, deployment: Deployment) -> None:
        self._deployments[deployment.id] = deployment
    
    async def get(self, deployment_id: str) -> Optional[Deployment]:
        return self._deployments.get(deployment_id)
    
    async def delete(self, deployment_id: str) -> bool:
        if deployment_id in self._deployments:
            del self._deployments[deployment_id]
            return True
        return False
    
    async def list_all(self) -> List[Deployment]:
        return list(self._deployments.values())
    
    async def add_event(self, event: DeploymentEvent) -> None:
        if event.deployment_id not in self._events:
            self._events[event.deployment_id] = []
        self._events[event.deployment_id].append(event)
    
    async def get_events(self, deployment_id: str) -> List[DeploymentEvent]:
        return self._events.get(deployment_id, [])


# Health checker
class HealthChecker(ABC):
    """Health checker for targets."""
    
    @abstractmethod
    async def check(self, target: DeploymentTarget) -> HealthCheckStatus:
        pass


class HTTPHealthChecker(HealthChecker):
    """HTTP health checker."""
    
    def __init__(self, timeout: int = 5):
        self.timeout = timeout
    
    async def check(self, target: DeploymentTarget) -> HealthCheckStatus:
        try:
            # Simulated HTTP health check
            await asyncio.sleep(0.01)
            return HealthCheckStatus.HEALTHY
        except Exception:
            return HealthCheckStatus.UNHEALTHY


# Deployment strategies
class DeploymentStrategyImpl(ABC):
    """Deployment strategy implementation."""
    
    @abstractmethod
    async def deploy(
        self,
        deployment: Deployment,
        on_progress: Optional[Callable[[int], None]] = None,
    ) -> bool:
        pass
    
    @abstractmethod
    async def rollback(self, deployment: Deployment) -> bool:
        pass


class RollingDeployment(DeploymentStrategyImpl):
    """Rolling deployment strategy."""
    
    def __init__(self, health_checker: HealthChecker):
        self.health_checker = health_checker
    
    async def deploy(
        self,
        deployment: Deployment,
        on_progress: Optional[Callable[[int], None]] = None,
    ) -> bool:
        targets = deployment.targets
        total = len(targets)
        
        if total == 0:
            return True
        
        for idx, target in enumerate(targets):
            # Update target
            target.version = deployment.version
            target.status = HealthCheckStatus.UNKNOWN
            
            # Wait for health
            for _ in range(10):
                status = await self.health_checker.check(target)
                if status == HealthCheckStatus.HEALTHY:
                    target.status = status
                    break
                await asyncio.sleep(1)
            else:
                target.status = HealthCheckStatus.UNHEALTHY
                return False
            
            # Update progress
            progress = int((idx + 1) / total * 100)
            if on_progress:
                on_progress(progress)
        
        return True
    
    async def rollback(self, deployment: Deployment) -> bool:
        if not deployment.previous_version:
            return False
        
        for target in deployment.targets:
            target.version = deployment.previous_version
            target.status = HealthCheckStatus.UNKNOWN
            
            # Check health
            status = await self.health_checker.check(target)
            target.status = status
        
        return True


class BlueGreenDeployment(DeploymentStrategyImpl):
    """Blue-green deployment strategy."""
    
    def __init__(self, health_checker: HealthChecker):
        self.health_checker = health_checker
    
    async def deploy(
        self,
        deployment: Deployment,
        on_progress: Optional[Callable[[int], None]] = None,
    ) -> bool:
        # Deploy to "green" environment
        if on_progress:
            on_progress(10)
        
        # Prepare all targets
        for target in deployment.targets:
            target.version = deployment.version
            target.status = HealthCheckStatus.UNKNOWN
        
        if on_progress:
            on_progress(30)
        
        # Health check all targets
        for target in deployment.targets:
            status = await self.health_checker.check(target)
            target.status = status
            
            if status != HealthCheckStatus.HEALTHY:
                return False
        
        if on_progress:
            on_progress(70)
        
        # Switch traffic
        if on_progress:
            on_progress(100)
        
        return True
    
    async def rollback(self, deployment: Deployment) -> bool:
        if not deployment.previous_version:
            return False
        
        # Switch back to "blue"
        for target in deployment.targets:
            target.version = deployment.previous_version
        
        return True


class CanaryDeployment(DeploymentStrategyImpl):
    """Canary deployment strategy."""
    
    def __init__(
        self,
        health_checker: HealthChecker,
        canary_percentage: int = 10,
    ):
        self.health_checker = health_checker
        self.canary_percentage = canary_percentage
    
    async def deploy(
        self,
        deployment: Deployment,
        on_progress: Optional[Callable[[int], None]] = None,
    ) -> bool:
        targets = deployment.targets
        total = len(targets)
        
        if total == 0:
            return True
        
        # Calculate canary count
        canary_count = max(1, int(total * self.canary_percentage / 100))
        
        # Deploy canary
        canary_targets = targets[:canary_count]
        
        for target in canary_targets:
            target.version = deployment.version
            target.status = HealthCheckStatus.UNKNOWN
            
            status = await self.health_checker.check(target)
            target.status = status
            
            if status != HealthCheckStatus.HEALTHY:
                return False
        
        if on_progress:
            on_progress(30)
        
        # Monitor canary (simulated)
        await asyncio.sleep(0.1)
        
        if on_progress:
            on_progress(50)
        
        # Deploy rest
        remaining = targets[canary_count:]
        
        for idx, target in enumerate(remaining):
            target.version = deployment.version
            
            status = await self.health_checker.check(target)
            target.status = status
            
            if status != HealthCheckStatus.HEALTHY:
                return False
            
            progress = 50 + int((idx + 1) / len(remaining) * 50) if remaining else 100
            if on_progress:
                on_progress(progress)
        
        return True
    
    async def rollback(self, deployment: Deployment) -> bool:
        if not deployment.previous_version:
            return False
        
        for target in deployment.targets:
            target.version = deployment.previous_version
        
        return True


# Deployment manager
class DeploymentManager:
    """Deployment manager."""
    
    def __init__(
        self,
        store: Optional[DeploymentStore] = None,
        health_checker: Optional[HealthChecker] = None,
    ):
        self._store = store or InMemoryDeploymentStore()
        self._health_checker = health_checker or HTTPHealthChecker()
        self._strategies: Dict[DeploymentStrategy, DeploymentStrategyImpl] = {
            DeploymentStrategy.ROLLING: RollingDeployment(self._health_checker),
            DeploymentStrategy.BLUE_GREEN: BlueGreenDeployment(self._health_checker),
            DeploymentStrategy.CANARY: CanaryDeployment(self._health_checker),
            DeploymentStrategy.RECREATE: RollingDeployment(self._health_checker),
        }
        self._stats = DeploymentStats()
        self._listeners: List[Callable] = []
    
    async def create(
        self,
        name: str,
        version: str,
        strategy: DeploymentStrategy = DeploymentStrategy.ROLLING,
        targets: Optional[List[DeploymentTarget]] = None,
        config: Optional[DeploymentConfig] = None,
        **kwargs,
    ) -> Deployment:
        """Create deployment."""
        if config is None:
            config = DeploymentConfig(
                name=name,
                version=version,
                strategy=strategy,
            )
        
        deployment = Deployment(
            name=name,
            version=version,
            strategy=strategy,
            config=config,
            targets=targets or [],
            **kwargs,
        )
        
        await self._store.save(deployment)
        
        await self._add_event(deployment.id, "created", f"Deployment {name} v{version} created")
        
        self._stats.total_deployments += 1
        
        logger.info(f"Deployment created: {name} v{version}")
        
        return deployment
    
    async def deploy(
        self,
        deployment_id: str,
        on_progress: Optional[Callable[[int], None]] = None,
    ) -> bool:
        """Execute deployment."""
        deployment = await self._store.get(deployment_id)
        
        if not deployment:
            raise DeploymentError(f"Deployment not found: {deployment_id}")
        
        if deployment.status == DeploymentStatus.IN_PROGRESS:
            raise DeploymentError("Deployment already in progress")
        
        deployment.status = DeploymentStatus.IN_PROGRESS
        deployment.started_at = datetime.utcnow()
        await self._store.save(deployment)
        
        await self._add_event(deployment_id, "started", "Deployment started")
        
        # Get strategy
        strategy = self._strategies.get(deployment.strategy)
        
        if not strategy:
            deployment.status = DeploymentStatus.FAILED
            deployment.error = f"Unknown strategy: {deployment.strategy}"
            await self._store.save(deployment)
            raise DeploymentError(deployment.error)
        
        try:
            def update_progress(progress: int):
                deployment.progress = progress
                if on_progress:
                    on_progress(progress)
            
            success = await strategy.deploy(deployment, update_progress)
            
            if success:
                deployment.status = DeploymentStatus.COMPLETED
                deployment.completed_at = datetime.utcnow()
                self._stats.successful_deployments += 1
                
                await self._add_event(deployment_id, "completed", "Deployment completed successfully")
                
                logger.info(f"Deployment completed: {deployment.name}")
            else:
                deployment.status = DeploymentStatus.FAILED
                deployment.error = "Deployment failed"
                self._stats.failed_deployments += 1
                
                await self._add_event(deployment_id, "failed", "Deployment failed")
                
                if deployment.config.rollback_on_failure:
                    await self.rollback(deployment_id)
                
                logger.error(f"Deployment failed: {deployment.name}")
            
            await self._store.save(deployment)
            
            return success
        except Exception as e:
            deployment.status = DeploymentStatus.FAILED
            deployment.error = str(e)
            self._stats.failed_deployments += 1
            
            await self._store.save(deployment)
            await self._add_event(deployment_id, "error", str(e))
            
            if deployment.config.rollback_on_failure:
                await self.rollback(deployment_id)
            
            raise DeploymentFailed(str(e))
    
    async def rollback(self, deployment_id: str) -> bool:
        """Rollback deployment."""
        deployment = await self._store.get(deployment_id)
        
        if not deployment:
            raise DeploymentError(f"Deployment not found: {deployment_id}")
        
        await self._add_event(deployment_id, "rollback_started", "Rollback initiated")
        
        strategy = self._strategies.get(deployment.strategy)
        
        if not strategy:
            raise RollbackFailed(f"Unknown strategy: {deployment.strategy}")
        
        try:
            success = await strategy.rollback(deployment)
            
            if success:
                deployment.status = DeploymentStatus.ROLLED_BACK
                deployment.rolled_back_at = datetime.utcnow()
                self._stats.rollbacks += 1
                
                await self._add_event(deployment_id, "rollback_completed", "Rollback completed")
                
                logger.info(f"Rollback completed: {deployment.name}")
            else:
                await self._add_event(deployment_id, "rollback_failed", "Rollback failed")
                
                logger.error(f"Rollback failed: {deployment.name}")
            
            await self._store.save(deployment)
            
            return success
        except Exception as e:
            await self._add_event(deployment_id, "rollback_error", str(e))
            raise RollbackFailed(str(e))
    
    async def cancel(self, deployment_id: str) -> bool:
        """Cancel deployment."""
        deployment = await self._store.get(deployment_id)
        
        if not deployment:
            return False
        
        if deployment.status not in [DeploymentStatus.PENDING, DeploymentStatus.IN_PROGRESS]:
            return False
        
        deployment.status = DeploymentStatus.CANCELLED
        await self._store.save(deployment)
        
        await self._add_event(deployment_id, "cancelled", "Deployment cancelled")
        
        logger.info(f"Deployment cancelled: {deployment.name}")
        
        return True
    
    async def get(self, deployment_id: str) -> Optional[Deployment]:
        """Get deployment."""
        return await self._store.get(deployment_id)
    
    async def list_deployments(self) -> List[Deployment]:
        """List all deployments."""
        return await self._store.list_all()
    
    async def get_events(self, deployment_id: str) -> List[DeploymentEvent]:
        """Get deployment events."""
        return await self._store.get_events(deployment_id)
    
    async def _add_event(
        self,
        deployment_id: str,
        event_type: str,
        message: str,
    ) -> None:
        """Add deployment event."""
        event = DeploymentEvent(
            deployment_id=deployment_id,
            event_type=event_type,
            message=message,
        )
        
        await self._store.add_event(event)
        
        # Notify listeners
        for listener in self._listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    await listener(event)
                else:
                    listener(event)
            except Exception as e:
                logger.error(f"Listener error: {e}")
    
    def add_listener(self, listener: Callable) -> None:
        """Add event listener."""
        self._listeners.append(listener)
    
    def get_stats(self) -> DeploymentStats:
        """Get statistics."""
        return self._stats


# Factory functions
def create_deployment_manager() -> DeploymentManager:
    """Create deployment manager."""
    return DeploymentManager()


def create_deployment(
    name: str,
    version: str,
    strategy: DeploymentStrategy = DeploymentStrategy.ROLLING,
    **kwargs,
) -> Deployment:
    """Create deployment."""
    return Deployment(name=name, version=version, strategy=strategy, **kwargs)


def create_deployment_target(
    name: str,
    host: str,
    port: int,
    **kwargs,
) -> DeploymentTarget:
    """Create deployment target."""
    return DeploymentTarget(name=name, host=host, port=port, **kwargs)


def create_deployment_config(
    name: str,
    version: str,
    **kwargs,
) -> DeploymentConfig:
    """Create deployment config."""
    return DeploymentConfig(name=name, version=version, **kwargs)


__all__ = [
    # Exceptions
    "DeploymentError",
    "DeploymentFailed",
    "RollbackFailed",
    # Enums
    "DeploymentStrategy",
    "DeploymentStatus",
    "HealthCheckStatus",
    # Data classes
    "DeploymentTarget",
    "DeploymentConfig",
    "Deployment",
    "DeploymentEvent",
    "DeploymentStats",
    # Stores
    "DeploymentStore",
    "InMemoryDeploymentStore",
    # Health checkers
    "HealthChecker",
    "HTTPHealthChecker",
    # Strategies
    "DeploymentStrategyImpl",
    "RollingDeployment",
    "BlueGreenDeployment",
    "CanaryDeployment",
    # Manager
    "DeploymentManager",
    # Factory functions
    "create_deployment_manager",
    "create_deployment",
    "create_deployment_target",
    "create_deployment_config",
]
