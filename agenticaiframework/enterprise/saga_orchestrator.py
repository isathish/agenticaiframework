"""
Enterprise Saga Orchestrator Module.

Provides saga orchestration, distributed transactions,
compensating actions, and rollback management.

Example:
    # Define saga
    saga = (
        create_saga("order-saga")
        .step("reserve_inventory", reserve_inventory, compensate=release_inventory)
        .step("process_payment", process_payment, compensate=refund_payment)
        .step("ship_order", ship_order, compensate=cancel_shipment)
        .build()
    )
    
    # Execute saga
    result = await saga.execute(order_data)
"""

from __future__ import annotations

import asyncio
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
    Generic,
    List,
    Optional,
    Set,
    Type,
    TypeVar,
)

T = TypeVar('T')
R = TypeVar('R')


logger = logging.getLogger(__name__)


class SagaError(Exception):
    """Saga error."""
    pass


class SagaExecutionError(SagaError):
    """Saga execution error."""
    pass


class CompensationError(SagaError):
    """Compensation error."""
    pass


class SagaTimeoutError(SagaError):
    """Saga timeout error."""
    pass


class SagaStatus(str, Enum):
    """Saga execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


class StepStatus(str, Enum):
    """Step execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"
    SKIPPED = "skipped"


@dataclass
class StepResult:
    """Result of a saga step."""
    step_name: str
    status: StepStatus
    result: Optional[Any] = None
    error: Optional[str] = None
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    duration_ms: Optional[float] = None


@dataclass
class SagaContext:
    """Saga execution context."""
    saga_id: str
    data: Dict[str, Any] = field(default_factory=dict)
    results: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, self.results.get(key, default))
    
    def set(self, key: str, value: Any) -> None:
        self.results[key] = value


@dataclass
class SagaExecution:
    """Saga execution record."""
    execution_id: str
    saga_name: str
    status: SagaStatus = SagaStatus.PENDING
    context: SagaContext = field(default_factory=lambda: SagaContext(saga_id=""))
    step_results: List[StepResult] = field(default_factory=list)
    current_step: int = 0
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    
    @property
    def duration_ms(self) -> Optional[float]:
        if self.completed_at:
            delta = self.completed_at - self.started_at
            return delta.total_seconds() * 1000
        return None


@dataclass
class SagaStep:
    """Definition of a saga step."""
    name: str
    action: Callable[[SagaContext], Any]
    compensate: Optional[Callable[[SagaContext], Any]] = None
    retry_count: int = 0
    timeout: Optional[float] = None
    condition: Optional[Callable[[SagaContext], bool]] = None


class SagaDefinition:
    """
    Definition of a saga with steps.
    """
    
    def __init__(self, name: str):
        self.name = name
        self.steps: List[SagaStep] = []
        self.timeout: Optional[float] = None
        self.on_success: Optional[Callable[[SagaContext], Any]] = None
        self.on_failure: Optional[Callable[[SagaContext, Exception], Any]] = None
    
    def add_step(self, step: SagaStep) -> SagaDefinition:
        """Add a step to the saga."""
        self.steps.append(step)
        return self
    
    def set_timeout(self, timeout: float) -> SagaDefinition:
        """Set saga timeout."""
        self.timeout = timeout
        return self


class SagaBuilder:
    """
    Builder for saga definitions.
    """
    
    def __init__(self, name: str):
        self._definition = SagaDefinition(name)
    
    def step(
        self,
        name: str,
        action: Callable[[SagaContext], Any],
        compensate: Optional[Callable[[SagaContext], Any]] = None,
        retry_count: int = 0,
        timeout: Optional[float] = None,
        condition: Optional[Callable[[SagaContext], bool]] = None,
    ) -> SagaBuilder:
        """Add a step."""
        self._definition.add_step(SagaStep(
            name=name,
            action=action,
            compensate=compensate,
            retry_count=retry_count,
            timeout=timeout,
            condition=condition,
        ))
        return self
    
    def timeout(self, seconds: float) -> SagaBuilder:
        """Set saga timeout."""
        self._definition.set_timeout(seconds)
        return self
    
    def on_success(
        self,
        handler: Callable[[SagaContext], Any],
    ) -> SagaBuilder:
        """Set success handler."""
        self._definition.on_success = handler
        return self
    
    def on_failure(
        self,
        handler: Callable[[SagaContext, Exception], Any],
    ) -> SagaBuilder:
        """Set failure handler."""
        self._definition.on_failure = handler
        return self
    
    def build(self) -> Saga:
        """Build the saga."""
        return Saga(self._definition)


class SagaStore(ABC):
    """
    Abstract saga state store.
    """
    
    @abstractmethod
    async def save(self, execution: SagaExecution) -> None:
        """Save saga execution."""
        pass
    
    @abstractmethod
    async def load(self, execution_id: str) -> Optional[SagaExecution]:
        """Load saga execution."""
        pass
    
    @abstractmethod
    async def list_pending(self) -> List[SagaExecution]:
        """List pending saga executions."""
        pass


class InMemorySagaStore(SagaStore):
    """
    In-memory saga store.
    """
    
    def __init__(self):
        self._executions: Dict[str, SagaExecution] = {}
    
    async def save(self, execution: SagaExecution) -> None:
        self._executions[execution.execution_id] = execution
    
    async def load(self, execution_id: str) -> Optional[SagaExecution]:
        return self._executions.get(execution_id)
    
    async def list_pending(self) -> List[SagaExecution]:
        return [
            e for e in self._executions.values()
            if e.status in (SagaStatus.PENDING, SagaStatus.RUNNING)
        ]


class Saga:
    """
    Saga orchestrator for distributed transactions.
    """
    
    def __init__(
        self,
        definition: SagaDefinition,
        store: Optional[SagaStore] = None,
    ):
        self._definition = definition
        self._store = store or InMemorySagaStore()
    
    @property
    def name(self) -> str:
        return self._definition.name
    
    async def execute(
        self,
        data: Dict[str, Any],
        execution_id: Optional[str] = None,
    ) -> SagaExecution:
        """Execute the saga."""
        execution_id = execution_id or str(uuid.uuid4())
        
        context = SagaContext(
            saga_id=execution_id,
            data=data,
        )
        
        execution = SagaExecution(
            execution_id=execution_id,
            saga_name=self.name,
            context=context,
        )
        
        await self._store.save(execution)
        
        try:
            execution.status = SagaStatus.RUNNING
            await self._store.save(execution)
            
            # Execute with timeout if specified
            if self._definition.timeout:
                await asyncio.wait_for(
                    self._execute_steps(execution),
                    timeout=self._definition.timeout,
                )
            else:
                await self._execute_steps(execution)
            
            execution.status = SagaStatus.COMPLETED
            execution.completed_at = datetime.now()
            
            # Call success handler
            if self._definition.on_success:
                try:
                    if asyncio.iscoroutinefunction(self._definition.on_success):
                        await self._definition.on_success(context)
                    else:
                        self._definition.on_success(context)
                except Exception as e:
                    logger.error(f"Success handler error: {e}")
            
        except asyncio.TimeoutError:
            execution.status = SagaStatus.TIMED_OUT
            execution.error = "Saga timed out"
            await self._compensate(execution)
            
        except Exception as e:
            execution.error = str(e)
            execution.status = SagaStatus.COMPENSATING
            await self._store.save(execution)
            
            await self._compensate(execution)
            
            # Call failure handler
            if self._definition.on_failure:
                try:
                    if asyncio.iscoroutinefunction(self._definition.on_failure):
                        await self._definition.on_failure(context, e)
                    else:
                        self._definition.on_failure(context, e)
                except Exception as handler_error:
                    logger.error(f"Failure handler error: {handler_error}")
        
        await self._store.save(execution)
        return execution
    
    async def _execute_steps(self, execution: SagaExecution) -> None:
        """Execute saga steps."""
        for i, step in enumerate(self._definition.steps):
            execution.current_step = i
            
            # Check condition
            if step.condition:
                try:
                    should_run = step.condition(execution.context)
                    if asyncio.iscoroutine(should_run):
                        should_run = await should_run
                    
                    if not should_run:
                        result = StepResult(
                            step_name=step.name,
                            status=StepStatus.SKIPPED,
                        )
                        execution.step_results.append(result)
                        continue
                except Exception as e:
                    raise SagaExecutionError(
                        f"Condition check failed for step {step.name}: {e}"
                    )
            
            result = StepResult(
                step_name=step.name,
                status=StepStatus.RUNNING,
            )
            execution.step_results.append(result)
            await self._store.save(execution)
            
            # Execute with retries
            last_error = None
            attempts = step.retry_count + 1
            
            for attempt in range(attempts):
                try:
                    # Execute with timeout if specified
                    if step.timeout:
                        step_result = await asyncio.wait_for(
                            self._execute_action(step.action, execution.context),
                            timeout=step.timeout,
                        )
                    else:
                        step_result = await self._execute_action(
                            step.action,
                            execution.context,
                        )
                    
                    result.status = StepStatus.COMPLETED
                    result.result = step_result
                    result.completed_at = datetime.now()
                    result.duration_ms = (
                        (result.completed_at - result.started_at).total_seconds()
                        * 1000
                    )
                    
                    # Store result in context
                    execution.context.results[step.name] = step_result
                    
                    await self._store.save(execution)
                    break
                    
                except Exception as e:
                    last_error = e
                    logger.warning(
                        f"Step {step.name} attempt {attempt + 1} failed: {e}"
                    )
                    if attempt < attempts - 1:
                        await asyncio.sleep(0.1 * (2 ** attempt))
            
            if last_error and result.status != StepStatus.COMPLETED:
                result.status = StepStatus.FAILED
                result.error = str(last_error)
                result.completed_at = datetime.now()
                raise SagaExecutionError(
                    f"Step {step.name} failed: {last_error}"
                )
    
    async def _execute_action(
        self,
        action: Callable[[SagaContext], Any],
        context: SagaContext,
    ) -> Any:
        """Execute an action."""
        if asyncio.iscoroutinefunction(action):
            return await action(context)
        return action(context)
    
    async def _compensate(self, execution: SagaExecution) -> None:
        """Execute compensating actions."""
        execution.status = SagaStatus.COMPENSATING
        await self._store.save(execution)
        
        # Compensate in reverse order
        completed_steps = [
            (i, r) for i, r in enumerate(execution.step_results)
            if r.status == StepStatus.COMPLETED
        ]
        
        compensation_errors = []
        
        for i, result in reversed(completed_steps):
            step = self._definition.steps[i]
            
            if not step.compensate:
                continue
            
            result.status = StepStatus.COMPENSATING
            await self._store.save(execution)
            
            try:
                await self._execute_action(step.compensate, execution.context)
                result.status = StepStatus.COMPENSATED
            except Exception as e:
                compensation_errors.append(f"{step.name}: {e}")
                logger.error(f"Compensation failed for {step.name}: {e}")
        
        if compensation_errors:
            execution.status = SagaStatus.FAILED
            execution.error = (
                f"Compensation failed: {'; '.join(compensation_errors)}"
            )
        else:
            execution.status = SagaStatus.COMPENSATED
        
        execution.completed_at = datetime.now()
        await self._store.save(execution)


class SagaCoordinator:
    """
    Coordinator for managing multiple sagas.
    """
    
    def __init__(self, store: Optional[SagaStore] = None):
        self._store = store or InMemorySagaStore()
        self._sagas: Dict[str, Saga] = {}
    
    def register(self, saga: Saga) -> None:
        """Register a saga."""
        self._sagas[saga.name] = saga
    
    def get(self, name: str) -> Saga:
        """Get a saga by name."""
        if name not in self._sagas:
            raise SagaError(f"Saga not found: {name}")
        return self._sagas[name]
    
    async def execute(
        self,
        saga_name: str,
        data: Dict[str, Any],
    ) -> SagaExecution:
        """Execute a saga by name."""
        saga = self.get(saga_name)
        return await saga.execute(data)
    
    async def recover_pending(self) -> List[SagaExecution]:
        """Recover and resume pending sagas."""
        pending = await self._store.list_pending()
        results = []
        
        for execution in pending:
            saga = self._sagas.get(execution.saga_name)
            if not saga:
                logger.error(f"Saga not found for recovery: {execution.saga_name}")
                continue
            
            # Resume from current step
            try:
                await saga._execute_steps(execution)
                execution.status = SagaStatus.COMPLETED
            except Exception as e:
                execution.error = str(e)
                await saga._compensate(execution)
            
            await self._store.save(execution)
            results.append(execution)
        
        return results


class ParallelSaga:
    """
    Saga with parallel step execution.
    """
    
    def __init__(self, name: str):
        self.name = name
        self._parallel_groups: List[List[SagaStep]] = []
        self._store = InMemorySagaStore()
    
    def parallel(self, *steps: SagaStep) -> ParallelSaga:
        """Add parallel steps."""
        self._parallel_groups.append(list(steps))
        return self
    
    async def execute(
        self,
        data: Dict[str, Any],
    ) -> SagaExecution:
        """Execute parallel saga."""
        execution_id = str(uuid.uuid4())
        context = SagaContext(saga_id=execution_id, data=data)
        
        execution = SagaExecution(
            execution_id=execution_id,
            saga_name=self.name,
            context=context,
        )
        
        try:
            execution.status = SagaStatus.RUNNING
            completed_groups = []
            
            for group in self._parallel_groups:
                # Execute group in parallel
                tasks = []
                for step in group:
                    task = self._execute_step(step, context)
                    tasks.append(task)
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Check for failures
                for i, result in enumerate(results):
                    step = group[i]
                    if isinstance(result, Exception):
                        execution.error = str(result)
                        # Compensate completed groups
                        for completed_group in reversed(completed_groups):
                            await self._compensate_group(completed_group, context)
                        execution.status = SagaStatus.COMPENSATED
                        execution.completed_at = datetime.now()
                        return execution
                    
                    context.results[step.name] = result
                    execution.step_results.append(StepResult(
                        step_name=step.name,
                        status=StepStatus.COMPLETED,
                        result=result,
                    ))
                
                completed_groups.append(group)
            
            execution.status = SagaStatus.COMPLETED
            execution.completed_at = datetime.now()
            
        except Exception as e:
            execution.error = str(e)
            execution.status = SagaStatus.FAILED
        
        return execution
    
    async def _execute_step(
        self,
        step: SagaStep,
        context: SagaContext,
    ) -> Any:
        """Execute a step."""
        if asyncio.iscoroutinefunction(step.action):
            return await step.action(context)
        return step.action(context)
    
    async def _compensate_group(
        self,
        group: List[SagaStep],
        context: SagaContext,
    ) -> None:
        """Compensate a group of steps."""
        tasks = []
        for step in group:
            if step.compensate:
                if asyncio.iscoroutinefunction(step.compensate):
                    tasks.append(step.compensate(context))
                else:
                    tasks.append(asyncio.coroutine(step.compensate)(context))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


class SagaRegistry:
    """
    Registry for sagas.
    """
    
    def __init__(self):
        self._sagas: Dict[str, Saga] = {}
    
    def register(self, saga: Saga) -> None:
        """Register a saga."""
        self._sagas[saga.name] = saga
    
    def get(self, name: str) -> Saga:
        """Get a saga."""
        if name not in self._sagas:
            raise SagaError(f"Saga not found: {name}")
        return self._sagas[name]
    
    def list(self) -> List[str]:
        """List registered saga names."""
        return list(self._sagas.keys())


# Global registry
_global_registry = SagaRegistry()


# Decorators
def saga_step(
    name: str,
    compensate: Optional[Callable] = None,
    retry_count: int = 0,
    timeout: Optional[float] = None,
) -> Callable:
    """
    Decorator for saga steps.
    
    Example:
        @saga_step("reserve_inventory", compensate=release_inventory)
        async def reserve_inventory(ctx):
            ...
    """
    def decorator(func: Callable) -> SagaStep:
        return SagaStep(
            name=name,
            action=func,
            compensate=compensate,
            retry_count=retry_count,
            timeout=timeout,
        )
    
    return decorator


def compensating(step_name: str) -> Callable:
    """
    Decorator for compensation handlers.
    
    Example:
        @compensating("reserve_inventory")
        async def release_inventory(ctx):
            ...
    """
    def decorator(func: Callable) -> Callable:
        func._compensates = step_name
        return func
    
    return decorator


# Factory functions
def create_saga(name: str) -> SagaBuilder:
    """Create a saga builder."""
    return SagaBuilder(name)


def create_parallel_saga(name: str) -> ParallelSaga:
    """Create a parallel saga."""
    return ParallelSaga(name)


def create_saga_store() -> InMemorySagaStore:
    """Create a saga store."""
    return InMemorySagaStore()


def create_saga_coordinator(
    store: Optional[SagaStore] = None,
) -> SagaCoordinator:
    """Create a saga coordinator."""
    return SagaCoordinator(store)


def create_step(
    name: str,
    action: Callable[[SagaContext], Any],
    compensate: Optional[Callable[[SagaContext], Any]] = None,
) -> SagaStep:
    """Create a saga step."""
    return SagaStep(
        name=name,
        action=action,
        compensate=compensate,
    )


def register_saga(saga: Saga) -> None:
    """Register saga in global registry."""
    _global_registry.register(saga)


def get_saga(name: str) -> Saga:
    """Get saga from global registry."""
    return _global_registry.get(name)


__all__ = [
    # Exceptions
    "SagaError",
    "SagaExecutionError",
    "CompensationError",
    "SagaTimeoutError",
    # Enums
    "SagaStatus",
    "StepStatus",
    # Data classes
    "StepResult",
    "SagaContext",
    "SagaExecution",
    "SagaStep",
    # Definition
    "SagaDefinition",
    "SagaBuilder",
    # Store
    "SagaStore",
    "InMemorySagaStore",
    # Saga
    "Saga",
    "SagaCoordinator",
    "ParallelSaga",
    # Registry
    "SagaRegistry",
    # Decorators
    "saga_step",
    "compensating",
    # Factory functions
    "create_saga",
    "create_parallel_saga",
    "create_saga_store",
    "create_saga_coordinator",
    "create_step",
    "register_saga",
    "get_saga",
]
