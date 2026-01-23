"""
Enterprise Blue-Green Deployment Module.

Provides blue-green deployment patterns, zero-downtime deployment,
traffic switching, and rollback capabilities.

Example:
    # Create blue-green deployer
    deployer = create_blue_green_deployer()
    
    # Deploy new version
    deployment = await deployer.deploy(
        name="api-service",
        version="2.0.0",
        replicas=3,
    )
    
    # Switch traffic
    await deployer.switch_traffic(deployment.deployment_id)
    
    # Rollback if needed
    await deployer.rollback(deployment.deployment_id)
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
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


class BlueGreenError(Exception):
    """Blue-green deployment error."""
    pass


class DeploymentNotFoundError(BlueGreenError):
    """Deployment not found."""
    pass


class SwitchFailedError(BlueGreenError):
    """Traffic switch failed."""
    pass


class EnvironmentColor(str, Enum):
    """Deployment environment color."""
    BLUE = "blue"
    GREEN = "green"


class DeploymentState(str, Enum):
    """Deployment state."""
    PENDING = "pending"
    DEPLOYING = "deploying"
    DEPLOYED = "deployed"
    SWITCHING = "switching"
    ACTIVE = "active"
    INACTIVE = "inactive"
    ROLLING_BACK = "rolling_back"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


class HealthCheckType(str, Enum):
    """Health check type."""
    HTTP = "http"
    TCP = "tcp"
    EXEC = "exec"
    GRPC = "grpc"


@dataclass
class HealthCheckConfig:
    """Health check configuration."""
    check_type: HealthCheckType = HealthCheckType.HTTP
    path: str = "/health"
    port: int = 8080
    interval_seconds: int = 10
    timeout_seconds: int = 5
    success_threshold: int = 3
    failure_threshold: int = 3


@dataclass
class EnvironmentConfig:
    """Environment configuration."""
    color: EnvironmentColor
    version: str
    replicas: int = 1
    resources: Dict[str, Any] = field(default_factory=dict)
    env_vars: Dict[str, str] = field(default_factory=dict)
    health_check: HealthCheckConfig = field(default_factory=HealthCheckConfig)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Environment:
    """Deployment environment."""
    environment_id: str
    color: EnvironmentColor
    version: str
    state: DeploymentState = DeploymentState.PENDING
    replicas: int = 1
    ready_replicas: int = 0
    traffic_weight: int = 0
    endpoint: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BlueGreenDeployment:
    """Blue-green deployment."""
    deployment_id: str
    name: str
    blue: Optional[Environment] = None
    green: Optional[Environment] = None
    active_color: Optional[EnvironmentColor] = None
    state: DeploymentState = DeploymentState.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def active_environment(self) -> Optional[Environment]:
        """Get active environment."""
        if self.active_color == EnvironmentColor.BLUE:
            return self.blue
        elif self.active_color == EnvironmentColor.GREEN:
            return self.green
        return None
    
    @property
    def inactive_environment(self) -> Optional[Environment]:
        """Get inactive environment."""
        if self.active_color == EnvironmentColor.BLUE:
            return self.green
        elif self.active_color == EnvironmentColor.GREEN:
            return self.blue
        return None


@dataclass
class SwitchResult:
    """Traffic switch result."""
    success: bool
    deployment_id: str
    from_color: EnvironmentColor
    to_color: EnvironmentColor
    from_version: str
    to_version: str
    switch_time: datetime = field(default_factory=datetime.now)
    message: str = ""


@dataclass
class RollbackResult:
    """Rollback result."""
    success: bool
    deployment_id: str
    from_version: str
    to_version: str
    rollback_time: datetime = field(default_factory=datetime.now)
    message: str = ""


class DeploymentStore(ABC):
    """Abstract deployment store."""
    
    @abstractmethod
    async def save(self, deployment: BlueGreenDeployment) -> None:
        """Save deployment."""
        pass
    
    @abstractmethod
    async def get(self, deployment_id: str) -> Optional[BlueGreenDeployment]:
        """Get deployment."""
        pass
    
    @abstractmethod
    async def get_by_name(self, name: str) -> Optional[BlueGreenDeployment]:
        """Get deployment by name."""
        pass
    
    @abstractmethod
    async def list_all(self) -> List[BlueGreenDeployment]:
        """List all deployments."""
        pass
    
    @abstractmethod
    async def delete(self, deployment_id: str) -> None:
        """Delete deployment."""
        pass


class InMemoryDeploymentStore(DeploymentStore):
    """In-memory deployment store."""
    
    def __init__(self):
        self._deployments: Dict[str, BlueGreenDeployment] = {}
        self._lock = asyncio.Lock()
    
    async def save(self, deployment: BlueGreenDeployment) -> None:
        async with self._lock:
            deployment.updated_at = datetime.now()
            self._deployments[deployment.deployment_id] = deployment
    
    async def get(self, deployment_id: str) -> Optional[BlueGreenDeployment]:
        return self._deployments.get(deployment_id)
    
    async def get_by_name(self, name: str) -> Optional[BlueGreenDeployment]:
        for deployment in self._deployments.values():
            if deployment.name == name:
                return deployment
        return None
    
    async def list_all(self) -> List[BlueGreenDeployment]:
        return list(self._deployments.values())
    
    async def delete(self, deployment_id: str) -> None:
        async with self._lock:
            self._deployments.pop(deployment_id, None)


class HealthChecker(ABC):
    """Abstract health checker."""
    
    @abstractmethod
    async def check(
        self,
        environment: Environment,
        config: HealthCheckConfig,
    ) -> bool:
        """Check environment health."""
        pass


class DefaultHealthChecker(HealthChecker):
    """Default health checker implementation."""
    
    async def check(
        self,
        environment: Environment,
        config: HealthCheckConfig,
    ) -> bool:
        """Simulate health check."""
        # In real implementation, perform actual health check
        # For now, assume healthy if we have ready replicas
        return environment.ready_replicas > 0


class InfrastructureProvider(ABC):
    """Abstract infrastructure provider."""
    
    @abstractmethod
    async def create_environment(
        self,
        config: EnvironmentConfig,
    ) -> Environment:
        """Create environment."""
        pass
    
    @abstractmethod
    async def delete_environment(
        self,
        environment_id: str,
    ) -> None:
        """Delete environment."""
        pass
    
    @abstractmethod
    async def scale(
        self,
        environment_id: str,
        replicas: int,
    ) -> None:
        """Scale environment."""
        pass
    
    @abstractmethod
    async def update_traffic(
        self,
        environment_id: str,
        weight: int,
    ) -> None:
        """Update traffic weight."""
        pass


class MockInfrastructureProvider(InfrastructureProvider):
    """Mock infrastructure provider for testing."""
    
    def __init__(self):
        self._environments: Dict[str, Environment] = {}
    
    async def create_environment(
        self,
        config: EnvironmentConfig,
    ) -> Environment:
        env = Environment(
            environment_id=f"env-{uuid.uuid4().hex[:8]}",
            color=config.color,
            version=config.version,
            replicas=config.replicas,
            ready_replicas=config.replicas,  # Simulate ready
            state=DeploymentState.DEPLOYED,
            endpoint=f"http://{config.color.value}.example.com",
        )
        self._environments[env.environment_id] = env
        return env
    
    async def delete_environment(
        self,
        environment_id: str,
    ) -> None:
        self._environments.pop(environment_id, None)
    
    async def scale(
        self,
        environment_id: str,
        replicas: int,
    ) -> None:
        if environment_id in self._environments:
            env = self._environments[environment_id]
            env.replicas = replicas
            env.ready_replicas = replicas
    
    async def update_traffic(
        self,
        environment_id: str,
        weight: int,
    ) -> None:
        if environment_id in self._environments:
            self._environments[environment_id].traffic_weight = weight


class TrafficSwitcher:
    """
    Traffic switcher for blue-green deployments.
    """
    
    def __init__(
        self,
        provider: InfrastructureProvider,
        gradual: bool = False,
        step_percent: int = 10,
        step_interval_seconds: int = 30,
    ):
        self._provider = provider
        self._gradual = gradual
        self._step_percent = step_percent
        self._step_interval = step_interval_seconds
    
    async def switch(
        self,
        from_env: Environment,
        to_env: Environment,
    ) -> SwitchResult:
        """Switch traffic between environments."""
        try:
            if self._gradual:
                # Gradual traffic switch
                for weight in range(self._step_percent, 101, self._step_percent):
                    await self._provider.update_traffic(
                        to_env.environment_id,
                        weight,
                    )
                    await self._provider.update_traffic(
                        from_env.environment_id,
                        100 - weight,
                    )
                    
                    to_env.traffic_weight = weight
                    from_env.traffic_weight = 100 - weight
                    
                    if weight < 100:
                        await asyncio.sleep(self._step_interval)
            else:
                # Instant switch
                await self._provider.update_traffic(
                    to_env.environment_id,
                    100,
                )
                await self._provider.update_traffic(
                    from_env.environment_id,
                    0,
                )
                
                to_env.traffic_weight = 100
                from_env.traffic_weight = 0
            
            return SwitchResult(
                success=True,
                deployment_id=to_env.environment_id,
                from_color=from_env.color,
                to_color=to_env.color,
                from_version=from_env.version,
                to_version=to_env.version,
                message="Traffic switched successfully",
            )
        
        except Exception as e:
            return SwitchResult(
                success=False,
                deployment_id=to_env.environment_id,
                from_color=from_env.color,
                to_color=to_env.color,
                from_version=from_env.version,
                to_version=to_env.version,
                message=f"Switch failed: {str(e)}",
            )


class BlueGreenDeployer:
    """
    Blue-green deployment manager.
    """
    
    def __init__(
        self,
        store: Optional[DeploymentStore] = None,
        provider: Optional[InfrastructureProvider] = None,
        health_checker: Optional[HealthChecker] = None,
        gradual_switch: bool = False,
        switch_step_percent: int = 10,
        health_check_retries: int = 30,
    ):
        self._store = store or InMemoryDeploymentStore()
        self._provider = provider or MockInfrastructureProvider()
        self._health_checker = health_checker or DefaultHealthChecker()
        self._switcher = TrafficSwitcher(
            self._provider,
            gradual=gradual_switch,
            step_percent=switch_step_percent,
        )
        self._health_check_retries = health_check_retries
    
    async def deploy(
        self,
        name: str,
        version: str,
        replicas: int = 1,
        env_vars: Optional[Dict[str, str]] = None,
        resources: Optional[Dict[str, Any]] = None,
        health_check: Optional[HealthCheckConfig] = None,
    ) -> BlueGreenDeployment:
        """Deploy a new version."""
        # Get existing deployment or create new
        deployment = await self._store.get_by_name(name)
        
        if deployment:
            # Determine target color
            if deployment.active_color == EnvironmentColor.BLUE:
                target_color = EnvironmentColor.GREEN
            else:
                target_color = EnvironmentColor.BLUE
        else:
            # New deployment, start with blue
            deployment = BlueGreenDeployment(
                deployment_id=f"bg-{uuid.uuid4().hex[:8]}",
                name=name,
                state=DeploymentState.PENDING,
            )
            target_color = EnvironmentColor.BLUE
        
        # Create environment config
        config = EnvironmentConfig(
            color=target_color,
            version=version,
            replicas=replicas,
            env_vars=env_vars or {},
            resources=resources or {},
            health_check=health_check or HealthCheckConfig(),
        )
        
        deployment.state = DeploymentState.DEPLOYING
        await self._store.save(deployment)
        
        try:
            # Create new environment
            environment = await self._provider.create_environment(config)
            
            # Wait for health check
            healthy = await self._wait_for_healthy(
                environment,
                config.health_check,
            )
            
            if not healthy:
                deployment.state = DeploymentState.FAILED
                await self._store.save(deployment)
                raise BlueGreenError(
                    f"Environment failed health check: {environment.environment_id}"
                )
            
            # Update deployment
            if target_color == EnvironmentColor.BLUE:
                deployment.blue = environment
            else:
                deployment.green = environment
            
            environment.state = DeploymentState.DEPLOYED
            deployment.state = DeploymentState.DEPLOYED
            
            # If first deployment, make it active
            if deployment.active_color is None:
                deployment.active_color = target_color
                environment.state = DeploymentState.ACTIVE
                environment.traffic_weight = 100
                await self._provider.update_traffic(
                    environment.environment_id,
                    100,
                )
                deployment.state = DeploymentState.ACTIVE
            
            await self._store.save(deployment)
            
            logger.info(
                f"Deployed {name} version {version} to {target_color.value}"
            )
            
            return deployment
        
        except Exception as e:
            deployment.state = DeploymentState.FAILED
            await self._store.save(deployment)
            raise
    
    async def _wait_for_healthy(
        self,
        environment: Environment,
        config: HealthCheckConfig,
    ) -> bool:
        """Wait for environment to be healthy."""
        for _ in range(self._health_check_retries):
            if await self._health_checker.check(environment, config):
                return True
            
            await asyncio.sleep(config.interval_seconds)
        
        return False
    
    async def switch_traffic(
        self,
        deployment_id: str,
    ) -> SwitchResult:
        """Switch traffic to inactive environment."""
        deployment = await self._store.get(deployment_id)
        
        if not deployment:
            raise DeploymentNotFoundError(
                f"Deployment not found: {deployment_id}"
            )
        
        active = deployment.active_environment
        inactive = deployment.inactive_environment
        
        if not active or not inactive:
            raise BlueGreenError(
                "Both environments must exist for traffic switch"
            )
        
        if inactive.state != DeploymentState.DEPLOYED:
            raise BlueGreenError(
                f"Inactive environment not ready: {inactive.state}"
            )
        
        deployment.state = DeploymentState.SWITCHING
        await self._store.save(deployment)
        
        # Switch traffic
        result = await self._switcher.switch(active, inactive)
        
        if result.success:
            # Update states
            active.state = DeploymentState.INACTIVE
            inactive.state = DeploymentState.ACTIVE
            
            # Update active color
            deployment.active_color = inactive.color
            deployment.state = DeploymentState.ACTIVE
            
            await self._store.save(deployment)
            
            logger.info(
                f"Switched traffic for {deployment.name}: "
                f"{active.version} -> {inactive.version}"
            )
        else:
            deployment.state = DeploymentState.FAILED
            await self._store.save(deployment)
        
        return result
    
    async def rollback(
        self,
        deployment_id: str,
    ) -> RollbackResult:
        """Rollback to previous version."""
        deployment = await self._store.get(deployment_id)
        
        if not deployment:
            raise DeploymentNotFoundError(
                f"Deployment not found: {deployment_id}"
            )
        
        active = deployment.active_environment
        inactive = deployment.inactive_environment
        
        if not active or not inactive:
            return RollbackResult(
                success=False,
                deployment_id=deployment_id,
                from_version=active.version if active else "",
                to_version="",
                message="No previous version to rollback to",
            )
        
        deployment.state = DeploymentState.ROLLING_BACK
        await self._store.save(deployment)
        
        # Switch back
        result = await self._switcher.switch(active, inactive)
        
        if result.success:
            active.state = DeploymentState.INACTIVE
            inactive.state = DeploymentState.ACTIVE
            deployment.active_color = inactive.color
            deployment.state = DeploymentState.ACTIVE
            
            await self._store.save(deployment)
            
            logger.info(
                f"Rolled back {deployment.name}: "
                f"{active.version} -> {inactive.version}"
            )
            
            return RollbackResult(
                success=True,
                deployment_id=deployment_id,
                from_version=active.version,
                to_version=inactive.version,
                message="Rollback successful",
            )
        else:
            deployment.state = DeploymentState.FAILED
            await self._store.save(deployment)
            
            return RollbackResult(
                success=False,
                deployment_id=deployment_id,
                from_version=active.version,
                to_version=inactive.version,
                message=f"Rollback failed: {result.message}",
            )
    
    async def get_deployment(
        self,
        deployment_id: str,
    ) -> Optional[BlueGreenDeployment]:
        """Get deployment by ID."""
        return await self._store.get(deployment_id)
    
    async def get_by_name(
        self,
        name: str,
    ) -> Optional[BlueGreenDeployment]:
        """Get deployment by name."""
        return await self._store.get_by_name(name)
    
    async def list_deployments(self) -> List[BlueGreenDeployment]:
        """List all deployments."""
        return await self._store.list_all()
    
    async def cleanup_inactive(
        self,
        deployment_id: str,
    ) -> None:
        """Clean up inactive environment."""
        deployment = await self._store.get(deployment_id)
        
        if not deployment:
            return
        
        inactive = deployment.inactive_environment
        
        if inactive:
            await self._provider.delete_environment(
                inactive.environment_id
            )
            
            if deployment.active_color == EnvironmentColor.BLUE:
                deployment.green = None
            else:
                deployment.blue = None
            
            await self._store.save(deployment)


class BlueGreenContext:
    """
    Context manager for blue-green deployment.
    """
    
    def __init__(
        self,
        deployer: BlueGreenDeployer,
        name: str,
        version: str,
        auto_switch: bool = False,
        cleanup_on_success: bool = False,
    ):
        self._deployer = deployer
        self._name = name
        self._version = version
        self._auto_switch = auto_switch
        self._cleanup_on_success = cleanup_on_success
        self._deployment: Optional[BlueGreenDeployment] = None
    
    async def __aenter__(self) -> BlueGreenDeployment:
        self._deployment = await self._deployer.deploy(
            self._name,
            self._version,
        )
        return self._deployment
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is None and self._deployment:
            if self._auto_switch:
                await self._deployer.switch_traffic(
                    self._deployment.deployment_id
                )
            
            if self._cleanup_on_success:
                await self._deployer.cleanup_inactive(
                    self._deployment.deployment_id
                )


# Decorators
def blue_green_deploy(
    name: str,
    deployer: Optional[BlueGreenDeployer] = None,
    auto_switch: bool = False,
) -> Callable:
    """
    Decorator for blue-green deployment.
    
    Example:
        @blue_green_deploy("my-service", auto_switch=True)
        async def deploy_service():
            ...
    """
    _deployer = deployer or BlueGreenDeployer()
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            version = kwargs.get("version", "1.0.0")
            
            async with BlueGreenContext(
                _deployer,
                name,
                version,
                auto_switch=auto_switch,
            ):
                return await func(*args, **kwargs)
        
        return wrapper
    
    return decorator


def with_rollback(
    name: str,
    deployer: Optional[BlueGreenDeployer] = None,
) -> Callable:
    """
    Decorator that rolls back on failure.
    
    Example:
        @with_rollback("my-service")
        async def risky_operation():
            ...
    """
    _deployer = deployer or BlueGreenDeployer()
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            deployment = await _deployer.get_by_name(name)
            
            try:
                return await func(*args, **kwargs)
            
            except Exception as e:
                if deployment:
                    await _deployer.rollback(deployment.deployment_id)
                raise
        
        return wrapper
    
    return decorator


# Factory functions
def create_blue_green_deployer(
    gradual_switch: bool = False,
    switch_step_percent: int = 10,
    health_check_retries: int = 30,
) -> BlueGreenDeployer:
    """Create a blue-green deployer."""
    return BlueGreenDeployer(
        gradual_switch=gradual_switch,
        switch_step_percent=switch_step_percent,
        health_check_retries=health_check_retries,
    )


def create_traffic_switcher(
    provider: Optional[InfrastructureProvider] = None,
    gradual: bool = False,
    step_percent: int = 10,
) -> TrafficSwitcher:
    """Create a traffic switcher."""
    return TrafficSwitcher(
        provider or MockInfrastructureProvider(),
        gradual=gradual,
        step_percent=step_percent,
    )


def create_health_checker() -> HealthChecker:
    """Create a health checker."""
    return DefaultHealthChecker()


__all__ = [
    # Exceptions
    "BlueGreenError",
    "DeploymentNotFoundError",
    "SwitchFailedError",
    # Enums
    "EnvironmentColor",
    "DeploymentState",
    "HealthCheckType",
    # Data classes
    "HealthCheckConfig",
    "EnvironmentConfig",
    "Environment",
    "BlueGreenDeployment",
    "SwitchResult",
    "RollbackResult",
    # Abstract classes
    "DeploymentStore",
    "HealthChecker",
    "InfrastructureProvider",
    # Implementations
    "InMemoryDeploymentStore",
    "DefaultHealthChecker",
    "MockInfrastructureProvider",
    # Core classes
    "TrafficSwitcher",
    "BlueGreenDeployer",
    "BlueGreenContext",
    # Decorators
    "blue_green_deploy",
    "with_rollback",
    # Factory functions
    "create_blue_green_deployer",
    "create_traffic_switcher",
    "create_health_checker",
]
