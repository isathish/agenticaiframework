"""
Enterprise Saga Pattern Module.

Provides saga orchestration for distributed transactions,
compensation handling, and eventual consistency.

Example:
    # Define saga
    saga = Saga("order_saga")
    
    saga.step("reserve_inventory", reserve_inventory, compensate_inventory)
    saga.step("process_payment", process_payment, refund_payment)
    saga.step("ship_order", ship_order, cancel_shipment)
    
    # Execute saga
    result = await saga.execute(order_data)
    
    # With decorator
    @saga_step(name="reserve", compensate=compensate_reserve)
    async def reserve_inventory(context: SagaContext):
        ...
"""

from __future__ import annotations

import asyncio
import logging
import traceback
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
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
    Tuple,
    TypeVar,
    Union,
)

logger = logging.getLogger(__name__)

T = TypeVar('T')


class SagaError(Exception):
    """Saga error."""
    pass


class SagaExecutionError(SagaError):
    """Saga execution failed."""
    
    def __init__(
        self,
        message: str,
        step_name: str,
        original_error: Exception,
    ):
        super().__init__(message)
        self.step_name = step_name
        self.original_error = original_error


class CompensationError(SagaError):
    """Compensation failed."""
    
    def __init__(
        self,
        message: str,
        failed_compensations: List[Tuple[str, Exception]],
    ):
        super().__init__(message)
        self.failed_compensations = failed_compensations


class SagaStatus(str, Enum):
    """Saga execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"
    FAILED = "failed"
    PARTIALLY_COMPENSATED = "partially_compensated"


class StepStatus(str, Enum):
    """Step execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"
    COMPENSATION_FAILED = "compensation_failed"
    SKIPPED = "skipped"


StepFunction = Callable[['SagaContext'], Awaitable[Any]]
CompensateFunction = Callable[['SagaContext'], Awaitable[None]]


@dataclass
class StepResult:
    """Result of step execution."""
    step_name: str
    status: StepStatus
    output: Any = None
    error: Optional[Exception] = None
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    duration_ms: float = 0.0


@dataclass
class SagaResult:
    """Result of saga execution."""
    saga_id: str
    saga_name: str
    status: SagaStatus
    steps: List[StepResult] = field(default_factory=list)
    output: Any = None
    error: Optional[Exception] = None
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    duration_ms: float = 0.0


@dataclass
class SagaContext:
    """
    Context passed between saga steps.
    """
    saga_id: str
    saga_name: str
    input_data: Any
    step_outputs: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_output(self, step_name: str) -> Any:
        """Get output from a previous step."""
        return self.step_outputs.get(step_name)
    
    def set_metadata(self, key: str, value: Any) -> None:
        """Set metadata value."""
        self.metadata[key] = value
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get metadata value."""
        return self.metadata.get(key, default)


@dataclass
class SagaStep:
    """Definition of a saga step."""
    name: str
    execute: StepFunction
    compensate: Optional[CompensateFunction] = None
    timeout_seconds: float = 30.0
    retry_count: int = 0
    retry_delay_seconds: float = 1.0
    condition: Optional[Callable[[SagaContext], bool]] = None


class SagaStore(ABC):
    """Abstract saga state store."""
    
    @abstractmethod
    async def save(self, saga_id: str, state: Dict[str, Any]) -> None:
        """Save saga state."""
        pass
    
    @abstractmethod
    async def load(self, saga_id: str) -> Optional[Dict[str, Any]]:
        """Load saga state."""
        pass
    
    @abstractmethod
    async def delete(self, saga_id: str) -> bool:
        """Delete saga state."""
        pass


class InMemorySagaStore(SagaStore):
    """In-memory saga store."""
    
    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}
    
    async def save(self, saga_id: str, state: Dict[str, Any]) -> None:
        self._store[saga_id] = state
    
    async def load(self, saga_id: str) -> Optional[Dict[str, Any]]:
        return self._store.get(saga_id)
    
    async def delete(self, saga_id: str) -> bool:
        return self._store.pop(saga_id, None) is not None


class Saga:
    """
    Saga orchestrator for distributed transactions.
    
    Example:
        saga = Saga("order_saga")
        saga.step("reserve", reserve_fn, compensate_fn)
        saga.step("pay", pay_fn, refund_fn)
        
        result = await saga.execute(order_data)
    """
    
    def __init__(
        self,
        name: str,
        store: Optional[SagaStore] = None,
    ):
        self._name = name
        self._steps: List[SagaStep] = []
        self._store = store or InMemorySagaStore()
        self._hooks: Dict[str, List[Callable]] = {
            "before_step": [],
            "after_step": [],
            "on_compensate": [],
            "on_complete": [],
            "on_error": [],
        }
    
    @property
    def name(self) -> str:
        return self._name
    
    def step(
        self,
        name: str,
        execute: StepFunction,
        compensate: Optional[CompensateFunction] = None,
        timeout_seconds: float = 30.0,
        retry_count: int = 0,
        condition: Optional[Callable[[SagaContext], bool]] = None,
    ) -> 'Saga':
        """Add a step to the saga."""
        step = SagaStep(
            name=name,
            execute=execute,
            compensate=compensate,
            timeout_seconds=timeout_seconds,
            retry_count=retry_count,
            condition=condition,
        )
        self._steps.append(step)
        return self
    
    def on_before_step(
        self,
        callback: Callable[[str, SagaContext], Awaitable[None]],
    ) -> 'Saga':
        """Add before step hook."""
        self._hooks["before_step"].append(callback)
        return self
    
    def on_after_step(
        self,
        callback: Callable[[str, StepResult, SagaContext], Awaitable[None]],
    ) -> 'Saga':
        """Add after step hook."""
        self._hooks["after_step"].append(callback)
        return self
    
    def on_compensate(
        self,
        callback: Callable[[str, SagaContext], Awaitable[None]],
    ) -> 'Saga':
        """Add compensation hook."""
        self._hooks["on_compensate"].append(callback)
        return self
    
    async def execute(
        self,
        input_data: Any,
        saga_id: Optional[str] = None,
    ) -> SagaResult:
        """Execute the saga."""
        saga_id = saga_id or str(uuid.uuid4())
        start_time = datetime.now()
        
        context = SagaContext(
            saga_id=saga_id,
            saga_name=self._name,
            input_data=input_data,
        )
        
        result = SagaResult(
            saga_id=saga_id,
            saga_name=self._name,
            status=SagaStatus.RUNNING,
            started_at=start_time,
        )
        
        completed_steps: List[SagaStep] = []
        
        try:
            # Execute each step
            for step in self._steps:
                # Check condition
                if step.condition and not step.condition(context):
                    step_result = StepResult(
                        step_name=step.name,
                        status=StepStatus.SKIPPED,
                    )
                    result.steps.append(step_result)
                    continue
                
                # Execute step
                step_result = await self._execute_step(step, context)
                result.steps.append(step_result)
                
                if step_result.status == StepStatus.COMPLETED:
                    context.step_outputs[step.name] = step_result.output
                    completed_steps.append(step)
                else:
                    # Step failed, start compensation
                    raise SagaExecutionError(
                        f"Step {step.name} failed",
                        step.name,
                        step_result.error or Exception("Unknown error"),
                    )
            
            # All steps completed
            result.status = SagaStatus.COMPLETED
            result.output = context.step_outputs
            
            # Run completion hooks
            for hook in self._hooks["on_complete"]:
                await hook(result, context)
        
        except SagaExecutionError as e:
            logger.error(f"Saga {self._name} failed at step {e.step_name}")
            
            # Run error hooks
            for hook in self._hooks["on_error"]:
                await hook(e, context)
            
            # Compensate completed steps in reverse order
            compensation_result = await self._compensate(
                completed_steps,
                context,
            )
            
            result.status = compensation_result
            result.error = e
        
        # Finalize result
        result.completed_at = datetime.now()
        result.duration_ms = (
            result.completed_at - result.started_at
        ).total_seconds() * 1000
        
        # Persist final state
        await self._store.save(saga_id, {
            "status": result.status.value,
            "steps": [
                {
                    "name": s.step_name,
                    "status": s.status.value,
                }
                for s in result.steps
            ],
        })
        
        return result
    
    async def _execute_step(
        self,
        step: SagaStep,
        context: SagaContext,
    ) -> StepResult:
        """Execute a single step with retry."""
        start_time = datetime.now()
        
        result = StepResult(
            step_name=step.name,
            status=StepStatus.RUNNING,
            started_at=start_time,
        )
        
        # Run before hooks
        for hook in self._hooks["before_step"]:
            await hook(step.name, context)
        
        attempts = step.retry_count + 1
        last_error: Optional[Exception] = None
        
        for attempt in range(attempts):
            try:
                # Execute with timeout
                output = await asyncio.wait_for(
                    step.execute(context),
                    timeout=step.timeout_seconds,
                )
                
                result.status = StepStatus.COMPLETED
                result.output = output
                last_error = None
                break
            
            except asyncio.TimeoutError:
                last_error = asyncio.TimeoutError(
                    f"Step {step.name} timed out after {step.timeout_seconds}s"
                )
                logger.warning(
                    f"Step {step.name} timed out (attempt {attempt + 1}/{attempts})"
                )
            
            except Exception as e:
                last_error = e
                logger.warning(
                    f"Step {step.name} failed: {e} (attempt {attempt + 1}/{attempts})"
                )
            
            # Wait before retry
            if attempt < attempts - 1:
                await asyncio.sleep(step.retry_delay_seconds)
        
        if last_error:
            result.status = StepStatus.FAILED
            result.error = last_error
        
        # Finalize timing
        result.completed_at = datetime.now()
        result.duration_ms = (
            result.completed_at - result.started_at
        ).total_seconds() * 1000
        
        # Run after hooks
        for hook in self._hooks["after_step"]:
            await hook(step.name, result, context)
        
        return result
    
    async def _compensate(
        self,
        steps: List[SagaStep],
        context: SagaContext,
    ) -> SagaStatus:
        """Compensate completed steps in reverse order."""
        failed_compensations: List[Tuple[str, Exception]] = []
        
        # Reverse order compensation
        for step in reversed(steps):
            if not step.compensate:
                continue
            
            # Run compensation hooks
            for hook in self._hooks["on_compensate"]:
                await hook(step.name, context)
            
            try:
                await step.compensate(context)
                logger.info(f"Compensated step: {step.name}")
            
            except Exception as e:
                logger.error(f"Compensation failed for {step.name}: {e}")
                failed_compensations.append((step.name, e))
        
        if failed_compensations:
            return SagaStatus.PARTIALLY_COMPENSATED
        
        return SagaStatus.COMPENSATED


class SagaOrchestrator:
    """
    Orchestrates multiple sagas.
    """
    
    def __init__(
        self,
        store: Optional[SagaStore] = None,
    ):
        self._sagas: Dict[str, Saga] = {}
        self._store = store or InMemorySagaStore()
        self._running: Dict[str, asyncio.Task] = {}
    
    def register(self, saga: Saga) -> None:
        """Register a saga."""
        self._sagas[saga.name] = saga
    
    async def start(
        self,
        saga_name: str,
        input_data: Any,
    ) -> str:
        """Start a saga execution."""
        saga = self._sagas.get(saga_name)
        
        if not saga:
            raise SagaError(f"Saga not found: {saga_name}")
        
        saga_id = str(uuid.uuid4())
        
        task = asyncio.create_task(saga.execute(input_data, saga_id))
        self._running[saga_id] = task
        
        return saga_id
    
    async def wait(self, saga_id: str) -> SagaResult:
        """Wait for saga completion."""
        task = self._running.get(saga_id)
        
        if not task:
            raise SagaError(f"Saga not running: {saga_id}")
        
        return await task
    
    async def get_status(self, saga_id: str) -> Optional[SagaStatus]:
        """Get saga status."""
        state = await self._store.load(saga_id)
        
        if state:
            return SagaStatus(state["status"])
        
        return None
    
    async def cancel(self, saga_id: str) -> bool:
        """Cancel a running saga."""
        task = self._running.get(saga_id)
        
        if task and not task.done():
            task.cancel()
            del self._running[saga_id]
            return True
        
        return False


class SagaBuilder:
    """
    Fluent builder for sagas.
    """
    
    def __init__(self, name: str):
        self._name = name
        self._steps: List[SagaStep] = []
        self._store: Optional[SagaStore] = None
    
    def with_store(self, store: SagaStore) -> 'SagaBuilder':
        """Set saga store."""
        self._store = store
        return self
    
    def step(
        self,
        name: str,
        execute: StepFunction,
    ) -> 'SagaStepBuilder':
        """Start building a step."""
        return SagaStepBuilder(self, name, execute)
    
    def _add_step(self, step: SagaStep) -> None:
        """Add step (internal)."""
        self._steps.append(step)
    
    def build(self) -> Saga:
        """Build the saga."""
        saga = Saga(self._name, self._store)
        
        for step in self._steps:
            saga._steps.append(step)
        
        return saga


class SagaStepBuilder:
    """Builder for saga steps."""
    
    def __init__(
        self,
        parent: SagaBuilder,
        name: str,
        execute: StepFunction,
    ):
        self._parent = parent
        self._name = name
        self._execute = execute
        self._compensate: Optional[CompensateFunction] = None
        self._timeout = 30.0
        self._retry_count = 0
        self._condition: Optional[Callable] = None
    
    def compensate(
        self,
        compensate_fn: CompensateFunction,
    ) -> 'SagaStepBuilder':
        """Set compensation function."""
        self._compensate = compensate_fn
        return self
    
    def timeout(self, seconds: float) -> 'SagaStepBuilder':
        """Set timeout."""
        self._timeout = seconds
        return self
    
    def retry(self, count: int) -> 'SagaStepBuilder':
        """Set retry count."""
        self._retry_count = count
        return self
    
    def when(
        self,
        condition: Callable[[SagaContext], bool],
    ) -> 'SagaStepBuilder':
        """Set execution condition."""
        self._condition = condition
        return self
    
    def next(
        self,
        name: str,
        execute: StepFunction,
    ) -> 'SagaStepBuilder':
        """Add next step."""
        self._finalize()
        return SagaStepBuilder(self._parent, name, execute)
    
    def build(self) -> Saga:
        """Build the saga."""
        self._finalize()
        return self._parent.build()
    
    def _finalize(self) -> None:
        """Finalize current step."""
        step = SagaStep(
            name=self._name,
            execute=self._execute,
            compensate=self._compensate,
            timeout_seconds=self._timeout,
            retry_count=self._retry_count,
            condition=self._condition,
        )
        self._parent._add_step(step)


# Decorators
def saga_step(
    name: str,
    compensate: Optional[CompensateFunction] = None,
    timeout: float = 30.0,
    retry: int = 0,
) -> Callable:
    """
    Decorator to define a saga step.
    
    Example:
        @saga_step("reserve_inventory", compensate=release_inventory)
        async def reserve_inventory(context: SagaContext):
            ...
    """
    def decorator(func: StepFunction) -> SagaStep:
        return SagaStep(
            name=name,
            execute=func,
            compensate=compensate,
            timeout_seconds=timeout,
            retry_count=retry,
        )
    
    return decorator


def compensates(step_name: str) -> Callable:
    """
    Decorator to mark a function as compensation.
    
    Example:
        @compensates("reserve_inventory")
        async def release_inventory(context: SagaContext):
            ...
    """
    def decorator(func: CompensateFunction) -> CompensateFunction:
        func._compensates_step = step_name
        return func
    
    return decorator


def transactional_saga(
    name: str,
    store: Optional[SagaStore] = None,
) -> Callable:
    """
    Decorator to wrap a function in a saga.
    
    Example:
        @transactional_saga("process_order")
        async def process_order(order: dict):
            yield step("validate", validate_order)
            yield step("reserve", reserve_inventory, release_inventory)
            yield step("charge", charge_payment, refund_payment)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> SagaResult:
            saga = Saga(name, store)
            
            # Get steps from generator
            gen = func(*args, **kwargs)
            
            for step_def in gen:
                if isinstance(step_def, SagaStep):
                    saga._steps.append(step_def)
                elif isinstance(step_def, tuple):
                    saga.step(*step_def)
            
            # Execute with first arg as input
            input_data = args[0] if args else kwargs
            return await saga.execute(input_data)
        
        return wrapper
    
    return decorator


# Factory functions
def create_saga(
    name: str,
    store: Optional[SagaStore] = None,
) -> Saga:
    """Create a saga."""
    return Saga(name, store)


def create_saga_builder(name: str) -> SagaBuilder:
    """Create a saga builder."""
    return SagaBuilder(name)


def create_saga_orchestrator(
    store: Optional[SagaStore] = None,
) -> SagaOrchestrator:
    """Create a saga orchestrator."""
    return SagaOrchestrator(store)


__all__ = [
    # Exceptions
    "SagaError",
    "SagaExecutionError",
    "CompensationError",
    # Enums
    "SagaStatus",
    "StepStatus",
    # Data classes
    "StepResult",
    "SagaResult",
    "SagaContext",
    "SagaStep",
    # Core classes
    "SagaStore",
    "InMemorySagaStore",
    "Saga",
    "SagaOrchestrator",
    "SagaBuilder",
    "SagaStepBuilder",
    # Decorators
    "saga_step",
    "compensates",
    "transactional_saga",
    # Factory functions
    "create_saga",
    "create_saga_builder",
    "create_saga_orchestrator",
]
