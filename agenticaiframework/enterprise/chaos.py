"""
Enterprise Chaos Engineering Module.

Provides fault injection, resilience testing, and chaos
experiments for validating system robustness.

Example:
    # Create chaos engine
    chaos = create_chaos_engine()
    
    # Define experiment
    experiment = chaos.experiment("database-failure")
    experiment.inject(LatencyFault(latency_ms=500))
    experiment.inject(FailureFault(failure_rate=0.1))
    
    # Run experiment
    async with experiment.run():
        # System operates under chaos
        await test_system_resilience()
    
    # With decorators
    @chaos_test(LatencyFault(100), duration_seconds=30)
    async def test_under_latency():
        ...
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
import uuid
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
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

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ChaosError(Exception):
    """Chaos engineering error."""
    pass


class InjectedFault(ChaosError):
    """Injected fault exception."""
    pass


class FaultType(str, Enum):
    """Type of fault."""
    LATENCY = "latency"
    FAILURE = "failure"
    EXCEPTION = "exception"
    TIMEOUT = "timeout"
    RESOURCE = "resource"
    PARTITION = "partition"
    CORRUPTION = "corruption"


class ExperimentState(str, Enum):
    """Experiment state."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    ABORTED = "aborted"


class TargetType(str, Enum):
    """Target type for fault injection."""
    SERVICE = "service"
    METHOD = "method"
    ENDPOINT = "endpoint"
    RESOURCE = "resource"


@dataclass
class FaultConfig:
    """Base fault configuration."""
    fault_type: FaultType
    probability: float = 1.0  # 0.0 to 1.0
    duration_seconds: Optional[float] = None
    target: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def should_inject(self) -> bool:
        """Determine if fault should be injected."""
        return random.random() < self.probability


@dataclass
class LatencyFault(FaultConfig):
    """Latency injection fault."""
    latency_ms: int = 100
    jitter_ms: int = 0
    
    def __post_init__(self):
        self.fault_type = FaultType.LATENCY
    
    def get_delay(self) -> float:
        """Get delay in seconds."""
        jitter = random.randint(-self.jitter_ms, self.jitter_ms)
        return (self.latency_ms + jitter) / 1000


@dataclass
class FailureFault(FaultConfig):
    """Failure injection fault."""
    failure_rate: float = 0.1
    exception_class: type = InjectedFault
    message: str = "Injected failure"
    
    def __post_init__(self):
        self.fault_type = FaultType.FAILURE
        self.probability = self.failure_rate


@dataclass
class TimeoutFault(FaultConfig):
    """Timeout injection fault."""
    timeout_seconds: float = 30.0
    
    def __post_init__(self):
        self.fault_type = FaultType.TIMEOUT


@dataclass
class ResourceFault(FaultConfig):
    """Resource exhaustion fault."""
    resource_type: str = "memory"  # memory, cpu, disk, connections
    usage_percent: float = 90.0
    
    def __post_init__(self):
        self.fault_type = FaultType.RESOURCE


@dataclass
class PartitionFault(FaultConfig):
    """Network partition fault."""
    partition_targets: List[str] = field(default_factory=list)
    bidirectional: bool = True
    
    def __post_init__(self):
        self.fault_type = FaultType.PARTITION


@dataclass
class CorruptionFault(FaultConfig):
    """Data corruption fault."""
    corruption_rate: float = 0.1
    corruption_type: str = "bit_flip"  # bit_flip, truncate, garbage
    
    def __post_init__(self):
        self.fault_type = FaultType.CORRUPTION


@dataclass
class ExperimentResult:
    """Result of a chaos experiment."""
    experiment_id: str
    name: str
    state: ExperimentState
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_seconds: float = 0
    faults_injected: int = 0
    errors_observed: int = 0
    hypothesis_validated: bool = False
    observations: List[str] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)


class Fault(ABC):
    """Abstract fault injector."""
    
    @abstractmethod
    async def inject(self) -> None:
        """Inject the fault."""
        pass
    
    @abstractmethod
    async def recover(self) -> None:
        """Recover from the fault."""
        pass
    
    @property
    @abstractmethod
    def config(self) -> FaultConfig:
        """Get fault configuration."""
        pass


class LatencyInjector(Fault):
    """Latency fault injector."""
    
    def __init__(self, config: LatencyFault):
        self._config = config
        self._active = False
    
    @property
    def config(self) -> FaultConfig:
        return self._config
    
    async def inject(self) -> None:
        if self._config.should_inject():
            delay = self._config.get_delay()
            await asyncio.sleep(delay)
            self._active = True
    
    async def recover(self) -> None:
        self._active = False


class FailureInjector(Fault):
    """Failure fault injector."""
    
    def __init__(self, config: FailureFault):
        self._config = config
        self._active = False
    
    @property
    def config(self) -> FaultConfig:
        return self._config
    
    async def inject(self) -> None:
        if self._config.should_inject():
            self._active = True
            raise self._config.exception_class(self._config.message)
    
    async def recover(self) -> None:
        self._active = False


class TimeoutInjector(Fault):
    """Timeout fault injector."""
    
    def __init__(self, config: TimeoutFault):
        self._config = config
        self._active = False
    
    @property
    def config(self) -> FaultConfig:
        return self._config
    
    async def inject(self) -> None:
        if self._config.should_inject():
            self._active = True
            await asyncio.sleep(self._config.timeout_seconds)
    
    async def recover(self) -> None:
        self._active = False


class FaultRegistry:
    """Registry for active faults."""
    
    def __init__(self):
        self._faults: Dict[str, Fault] = {}
        self._targets: Dict[str, List[str]] = {}  # target -> fault_ids
        self._lock = asyncio.Lock()
    
    async def register(
        self,
        fault_id: str,
        fault: Fault,
        target: Optional[str] = None,
    ) -> None:
        """Register a fault."""
        async with self._lock:
            self._faults[fault_id] = fault
            
            if target:
                if target not in self._targets:
                    self._targets[target] = []
                self._targets[target].append(fault_id)
    
    async def unregister(self, fault_id: str) -> None:
        """Unregister a fault."""
        async with self._lock:
            if fault_id in self._faults:
                del self._faults[fault_id]
            
            for target, fault_ids in self._targets.items():
                if fault_id in fault_ids:
                    fault_ids.remove(fault_id)
    
    def get_faults_for_target(self, target: str) -> List[Fault]:
        """Get faults for a target."""
        fault_ids = self._targets.get(target, [])
        return [self._faults[fid] for fid in fault_ids if fid in self._faults]
    
    def get_all_faults(self) -> List[Fault]:
        """Get all registered faults."""
        return list(self._faults.values())


class Experiment:
    """
    Chaos experiment definition and runner.
    """
    
    def __init__(
        self,
        name: str,
        hypothesis: Optional[str] = None,
    ):
        self._id = str(uuid.uuid4())
        self._name = name
        self._hypothesis = hypothesis
        self._faults: List[Fault] = []
        self._state = ExperimentState.PENDING
        self._started_at: Optional[datetime] = None
        self._ended_at: Optional[datetime] = None
        self._observations: List[str] = []
        self._metrics: Dict[str, float] = {}
        self._steady_state_checks: List[Callable[[], bool]] = []
    
    @property
    def id(self) -> str:
        return self._id
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def state(self) -> ExperimentState:
        return self._state
    
    def inject(self, fault_config: FaultConfig) -> "Experiment":
        """Add a fault to inject."""
        if isinstance(fault_config, LatencyFault):
            self._faults.append(LatencyInjector(fault_config))
        elif isinstance(fault_config, FailureFault):
            self._faults.append(FailureInjector(fault_config))
        elif isinstance(fault_config, TimeoutFault):
            self._faults.append(TimeoutInjector(fault_config))
        else:
            # Generic handler
            logger.warning(f"Unknown fault type: {fault_config.fault_type}")
        
        return self
    
    def add_steady_state_check(
        self,
        check: Callable[[], bool],
    ) -> "Experiment":
        """Add steady state hypothesis check."""
        self._steady_state_checks.append(check)
        return self
    
    def observe(self, observation: str) -> None:
        """Record an observation."""
        self._observations.append(
            f"[{datetime.now().isoformat()}] {observation}"
        )
    
    def record_metric(self, name: str, value: float) -> None:
        """Record a metric."""
        self._metrics[name] = value
    
    async def _inject_all(self) -> int:
        """Inject all faults."""
        count = 0
        
        for fault in self._faults:
            try:
                await fault.inject()
                count += 1
            except InjectedFault:
                count += 1
                raise
            except Exception as e:
                logger.error(f"Fault injection error: {e}")
        
        return count
    
    async def _recover_all(self) -> None:
        """Recover from all faults."""
        for fault in self._faults:
            try:
                await fault.recover()
            except Exception as e:
                logger.error(f"Fault recovery error: {e}")
    
    def _check_steady_state(self) -> bool:
        """Check steady state hypothesis."""
        for check in self._steady_state_checks:
            try:
                if not check():
                    return False
            except Exception:
                return False
        
        return True
    
    @asynccontextmanager
    async def run(
        self,
        duration_seconds: Optional[float] = None,
    ):
        """
        Run the experiment.
        
        Example:
            async with experiment.run():
                await test_system()
        """
        self._state = ExperimentState.RUNNING
        self._started_at = datetime.now()
        faults_injected = 0
        errors_observed = 0
        
        logger.info(f"Starting chaos experiment: {self._name}")
        
        try:
            # Check initial steady state
            initial_steady = self._check_steady_state()
            self.observe(f"Initial steady state: {initial_steady}")
            
            yield self
            
            # The experiment runs within this context
            
        except InjectedFault as e:
            faults_injected += 1
            self.observe(f"Injected fault observed: {e}")
        
        except Exception as e:
            errors_observed += 1
            self.observe(f"Error observed: {e}")
            raise
        
        finally:
            # Recover
            await self._recover_all()
            
            self._ended_at = datetime.now()
            self._state = ExperimentState.COMPLETED
            
            # Check final steady state
            final_steady = self._check_steady_state()
            self.observe(f"Final steady state: {final_steady}")
            
            duration = (self._ended_at - self._started_at).total_seconds()
            
            logger.info(
                f"Experiment {self._name} completed in {duration:.2f}s, "
                f"faults: {faults_injected}, errors: {errors_observed}"
            )
    
    def get_result(self) -> ExperimentResult:
        """Get experiment result."""
        duration = 0.0
        if self._started_at and self._ended_at:
            duration = (self._ended_at - self._started_at).total_seconds()
        
        return ExperimentResult(
            experiment_id=self._id,
            name=self._name,
            state=self._state,
            started_at=self._started_at or datetime.now(),
            ended_at=self._ended_at,
            duration_seconds=duration,
            faults_injected=len(self._faults),
            observations=self._observations.copy(),
            metrics=self._metrics.copy(),
            hypothesis_validated=self._check_steady_state(),
        )


class ChaosEngine:
    """
    Chaos engineering engine.
    """
    
    def __init__(self):
        self._registry = FaultRegistry()
        self._experiments: Dict[str, Experiment] = {}
        self._enabled = True
    
    @property
    def enabled(self) -> bool:
        return self._enabled
    
    def enable(self) -> None:
        """Enable chaos engineering."""
        self._enabled = True
        logger.info("Chaos engineering enabled")
    
    def disable(self) -> None:
        """Disable chaos engineering."""
        self._enabled = False
        logger.info("Chaos engineering disabled")
    
    def experiment(
        self,
        name: str,
        hypothesis: Optional[str] = None,
    ) -> Experiment:
        """Create a new experiment."""
        exp = Experiment(name, hypothesis)
        self._experiments[exp.id] = exp
        return exp
    
    async def register_fault(
        self,
        fault_config: FaultConfig,
        target: Optional[str] = None,
    ) -> str:
        """Register a global fault."""
        fault_id = str(uuid.uuid4())
        
        if isinstance(fault_config, LatencyFault):
            fault = LatencyInjector(fault_config)
        elif isinstance(fault_config, FailureFault):
            fault = FailureInjector(fault_config)
        elif isinstance(fault_config, TimeoutFault):
            fault = TimeoutInjector(fault_config)
        else:
            raise ChaosError(f"Unknown fault type: {fault_config.fault_type}")
        
        await self._registry.register(fault_id, fault, target)
        
        return fault_id
    
    async def unregister_fault(self, fault_id: str) -> None:
        """Unregister a fault."""
        await self._registry.unregister(fault_id)
    
    async def inject_for_target(self, target: str) -> None:
        """Inject faults for a target."""
        if not self._enabled:
            return
        
        faults = self._registry.get_faults_for_target(target)
        
        for fault in faults:
            await fault.inject()
    
    def get_experiment(self, experiment_id: str) -> Optional[Experiment]:
        """Get experiment by ID."""
        return self._experiments.get(experiment_id)
    
    def list_experiments(self) -> List[Experiment]:
        """List all experiments."""
        return list(self._experiments.values())


class SteadyStateProbe:
    """
    Probe for steady state verification.
    """
    
    def __init__(
        self,
        name: str,
        check_fn: Callable[[], bool],
        tolerance: float = 0.0,
    ):
        self._name = name
        self._check_fn = check_fn
        self._tolerance = tolerance
        self._baseline: Optional[float] = None
    
    def establish_baseline(self) -> None:
        """Establish baseline measurement."""
        try:
            result = self._check_fn()
            if isinstance(result, (int, float)):
                self._baseline = result
        except Exception as e:
            logger.error(f"Baseline error: {e}")
    
    def check(self) -> bool:
        """Check steady state."""
        try:
            result = self._check_fn()
            
            if isinstance(result, bool):
                return result
            
            if isinstance(result, (int, float)) and self._baseline:
                deviation = abs(result - self._baseline) / self._baseline
                return deviation <= self._tolerance
            
            return bool(result)
        
        except Exception as e:
            logger.error(f"Probe error: {e}")
            return False


class GameDay:
    """
    Coordinated chaos game day.
    """
    
    def __init__(
        self,
        name: str,
        engine: ChaosEngine,
    ):
        self._name = name
        self._engine = engine
        self._experiments: List[Experiment] = []
        self._schedule: List[Tuple[float, Experiment]] = []
        self._results: List[ExperimentResult] = []
    
    def add_experiment(
        self,
        experiment: Experiment,
        delay_seconds: float = 0,
    ) -> "GameDay":
        """Add experiment to game day."""
        self._experiments.append(experiment)
        self._schedule.append((delay_seconds, experiment))
        return self
    
    async def run(self) -> List[ExperimentResult]:
        """Run all experiments."""
        logger.info(f"Starting game day: {self._name}")
        
        for delay, experiment in self._schedule:
            if delay > 0:
                await asyncio.sleep(delay)
            
            try:
                async with experiment.run():
                    # Allow some time for the experiment
                    await asyncio.sleep(1)
                
                self._results.append(experiment.get_result())
            
            except Exception as e:
                logger.error(f"Experiment {experiment.name} failed: {e}")
                self._results.append(experiment.get_result())
        
        logger.info(f"Game day {self._name} completed")
        
        return self._results


# Global engine
_global_engine = ChaosEngine()


# Decorators
def chaos_test(
    *fault_configs: FaultConfig,
    duration_seconds: Optional[float] = None,
) -> Callable:
    """
    Decorator for chaos testing.
    
    Example:
        @chaos_test(LatencyFault(100), FailureFault(0.1))
        async def test_resilience():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not _global_engine.enabled:
                return await func(*args, **kwargs)
            
            experiment = _global_engine.experiment(func.__name__)
            
            for config in fault_configs:
                experiment.inject(config)
            
            async with experiment.run(duration_seconds):
                return await func(*args, **kwargs)
        
        return wrapper
    
    return decorator


def with_fault(
    fault_config: FaultConfig,
    target: Optional[str] = None,
) -> Callable:
    """
    Decorator to inject fault during function execution.
    
    Example:
        @with_fault(LatencyFault(500))
        async def slow_operation():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not _global_engine.enabled:
                return await func(*args, **kwargs)
            
            fault_id = await _global_engine.register_fault(
                fault_config,
                target or func.__name__,
            )
            
            try:
                await _global_engine.inject_for_target(
                    target or func.__name__
                )
                return await func(*args, **kwargs)
            finally:
                await _global_engine.unregister_fault(fault_id)
        
        return wrapper
    
    return decorator


def resilient(
    fallback: Optional[Callable] = None,
) -> Callable:
    """
    Decorator to mark function as resilient to chaos.
    
    Example:
        @resilient(fallback=lambda: "default")
        async def critical_operation():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await func(*args, **kwargs)
            except InjectedFault:
                if fallback:
                    if asyncio.iscoroutinefunction(fallback):
                        return await fallback()
                    return fallback()
                raise
        
        return wrapper
    
    return decorator


# Factory functions
def create_chaos_engine() -> ChaosEngine:
    """Create a chaos engine."""
    return ChaosEngine()


def create_experiment(
    name: str,
    hypothesis: Optional[str] = None,
) -> Experiment:
    """Create a chaos experiment."""
    return Experiment(name, hypothesis)


def create_game_day(
    name: str,
    engine: Optional[ChaosEngine] = None,
) -> GameDay:
    """Create a game day."""
    return GameDay(name, engine or _global_engine)


def create_latency_fault(
    latency_ms: int = 100,
    probability: float = 1.0,
    jitter_ms: int = 0,
) -> LatencyFault:
    """Create a latency fault."""
    return LatencyFault(
        latency_ms=latency_ms,
        probability=probability,
        jitter_ms=jitter_ms,
    )


def create_failure_fault(
    failure_rate: float = 0.1,
    message: str = "Injected failure",
) -> FailureFault:
    """Create a failure fault."""
    return FailureFault(
        failure_rate=failure_rate,
        message=message,
    )


def create_timeout_fault(
    timeout_seconds: float = 30.0,
    probability: float = 1.0,
) -> TimeoutFault:
    """Create a timeout fault."""
    return TimeoutFault(
        timeout_seconds=timeout_seconds,
        probability=probability,
    )


def get_global_engine() -> ChaosEngine:
    """Get global chaos engine."""
    return _global_engine


__all__ = [
    # Exceptions
    "ChaosError",
    "InjectedFault",
    # Enums
    "FaultType",
    "ExperimentState",
    "TargetType",
    # Fault configs
    "FaultConfig",
    "LatencyFault",
    "FailureFault",
    "TimeoutFault",
    "ResourceFault",
    "PartitionFault",
    "CorruptionFault",
    # Data classes
    "ExperimentResult",
    # Fault injectors
    "Fault",
    "LatencyInjector",
    "FailureInjector",
    "TimeoutInjector",
    # Core classes
    "FaultRegistry",
    "Experiment",
    "ChaosEngine",
    "SteadyStateProbe",
    "GameDay",
    # Decorators
    "chaos_test",
    "with_fault",
    "resilient",
    # Factory functions
    "create_chaos_engine",
    "create_experiment",
    "create_game_day",
    "create_latency_fault",
    "create_failure_fault",
    "create_timeout_fault",
    "get_global_engine",
]
