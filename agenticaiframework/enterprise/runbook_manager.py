"""
Enterprise Runbook Manager Module.

Automated runbook execution, procedure management,
step-by-step workflows, and execution history.

Example:
    # Create runbook manager
    runbooks = create_runbook_manager()
    
    # Create runbook
    runbook = await runbooks.create(
        name="Deploy Application",
        description="Standard deployment procedure",
    )
    
    # Add steps
    await runbooks.add_step(
        runbook.id,
        name="Pull latest code",
        command="git pull origin main",
    )
    
    # Execute runbook
    execution = await runbooks.execute(runbook.id)
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Union,
)

logger = logging.getLogger(__name__)


class RunbookError(Exception):
    """Runbook error."""
    pass


class StepExecutionError(RunbookError):
    """Step execution error."""
    pass


class RunbookStatus(str, Enum):
    """Runbook status."""
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class StepType(str, Enum):
    """Step type."""
    COMMAND = "command"  # Shell command
    SCRIPT = "script"  # Script execution
    HTTP = "http"  # HTTP request
    MANUAL = "manual"  # Manual step requiring confirmation
    APPROVAL = "approval"  # Requires approval to continue
    WAIT = "wait"  # Wait for condition
    PARALLEL = "parallel"  # Run steps in parallel
    CONDITIONAL = "conditional"  # Conditional execution


class ExecutionStatus(str, Enum):
    """Execution status."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class StepResult(str, Enum):
    """Step result."""
    SUCCESS = "success"
    FAILURE = "failure"
    SKIPPED = "skipped"
    TIMEOUT = "timeout"


@dataclass
class Step:
    """Runbook step."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    step_type: StepType = StepType.COMMAND
    order: int = 0
    
    # Execution
    command: str = ""
    script: str = ""
    working_directory: str = ""
    environment: Dict[str, str] = field(default_factory=dict)
    
    # HTTP
    url: str = ""
    method: str = "GET"
    headers: Dict[str, str] = field(default_factory=dict)
    body: str = ""
    
    # Control
    timeout_seconds: int = 300
    retry_count: int = 0
    retry_delay_seconds: int = 5
    continue_on_failure: bool = False
    
    # Conditions
    condition: str = ""  # Expression to evaluate
    skip_if: str = ""
    
    # Validation
    expected_exit_code: int = 0
    success_pattern: str = ""
    failure_pattern: str = ""
    
    # Parallel steps
    parallel_steps: List[str] = field(default_factory=list)
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Runbook:
    """Runbook."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    status: RunbookStatus = RunbookStatus.DRAFT
    
    # Steps
    steps: List[Step] = field(default_factory=list)
    
    # Configuration
    version: str = "1.0.0"
    category: str = ""
    tags: List[str] = field(default_factory=list)
    
    # Execution settings
    timeout_seconds: int = 3600
    require_approval: bool = False
    notify_on_completion: bool = True
    notify_on_failure: bool = True
    
    # Parameters
    parameters: Dict[str, Any] = field(default_factory=dict)
    parameter_schema: Dict[str, Any] = field(default_factory=dict)
    
    # Authors
    author: str = ""
    maintainers: List[str] = field(default_factory=list)
    
    # Dates
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StepExecution:
    """Step execution record."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    step_id: str = ""
    step_name: str = ""
    status: ExecutionStatus = ExecutionStatus.PENDING
    result: Optional[StepResult] = None
    
    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0
    
    # Output
    stdout: str = ""
    stderr: str = ""
    exit_code: Optional[int] = None
    
    # Retry
    attempt: int = 1
    
    # Error
    error_message: str = ""


@dataclass
class Execution:
    """Runbook execution."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    runbook_id: str = ""
    runbook_name: str = ""
    status: ExecutionStatus = ExecutionStatus.PENDING
    
    # Steps
    step_executions: List[StepExecution] = field(default_factory=list)
    current_step: int = 0
    
    # Parameters
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0
    
    # Executor
    executed_by: str = ""
    approved_by: str = ""
    
    # Results
    success: bool = False
    error_message: str = ""
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RunbookStats:
    """Runbook statistics."""
    total_runbooks: int = 0
    active: int = 0
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    avg_duration_seconds: float = 0.0


# Runbook store
class RunbookStore(ABC):
    """Runbook storage."""
    
    @abstractmethod
    async def save(self, runbook: Runbook) -> None:
        pass
    
    @abstractmethod
    async def get(self, runbook_id: str) -> Optional[Runbook]:
        pass
    
    @abstractmethod
    async def list_all(self) -> List[Runbook]:
        pass
    
    @abstractmethod
    async def delete(self, runbook_id: str) -> bool:
        pass


class InMemoryRunbookStore(RunbookStore):
    """In-memory runbook store."""
    
    def __init__(self):
        self._runbooks: Dict[str, Runbook] = {}
    
    async def save(self, runbook: Runbook) -> None:
        self._runbooks[runbook.id] = runbook
    
    async def get(self, runbook_id: str) -> Optional[Runbook]:
        return self._runbooks.get(runbook_id)
    
    async def list_all(self) -> List[Runbook]:
        return list(self._runbooks.values())
    
    async def delete(self, runbook_id: str) -> bool:
        if runbook_id in self._runbooks:
            del self._runbooks[runbook_id]
            return True
        return False


# Execution store
class ExecutionStore(ABC):
    """Execution storage."""
    
    @abstractmethod
    async def save(self, execution: Execution) -> None:
        pass
    
    @abstractmethod
    async def get(self, execution_id: str) -> Optional[Execution]:
        pass
    
    @abstractmethod
    async def list_by_runbook(self, runbook_id: str) -> List[Execution]:
        pass
    
    @abstractmethod
    async def list_all(self) -> List[Execution]:
        pass


class InMemoryExecutionStore(ExecutionStore):
    """In-memory execution store."""
    
    def __init__(self, max_executions: int = 10000):
        self._executions: Dict[str, Execution] = {}
        self._by_runbook: Dict[str, List[str]] = {}
        self._max = max_executions
    
    async def save(self, execution: Execution) -> None:
        self._executions[execution.id] = execution
        
        if execution.runbook_id not in self._by_runbook:
            self._by_runbook[execution.runbook_id] = []
        
        if execution.id not in self._by_runbook[execution.runbook_id]:
            self._by_runbook[execution.runbook_id].append(execution.id)
        
        # Trim old executions
        if len(self._executions) > self._max:
            oldest = list(self._executions.keys())[0]
            del self._executions[oldest]
    
    async def get(self, execution_id: str) -> Optional[Execution]:
        return self._executions.get(execution_id)
    
    async def list_by_runbook(self, runbook_id: str) -> List[Execution]:
        exec_ids = self._by_runbook.get(runbook_id, [])
        execs = [self._executions[eid] for eid in exec_ids if eid in self._executions]
        return sorted(execs, key=lambda e: e.started_at or datetime.min, reverse=True)
    
    async def list_all(self) -> List[Execution]:
        return list(self._executions.values())


# Step executor
class StepExecutor(ABC):
    """Step executor."""
    
    @abstractmethod
    async def execute(
        self,
        step: Step,
        parameters: Dict[str, Any],
    ) -> StepExecution:
        pass


class DefaultStepExecutor(StepExecutor):
    """Default step executor."""
    
    def __init__(self, dry_run: bool = False):
        self._dry_run = dry_run
    
    async def execute(
        self,
        step: Step,
        parameters: Dict[str, Any],
    ) -> StepExecution:
        """Execute step."""
        execution = StepExecution(
            step_id=step.id,
            step_name=step.name,
            status=ExecutionStatus.RUNNING,
            started_at=datetime.utcnow(),
        )
        
        try:
            if step.step_type == StepType.COMMAND:
                await self._execute_command(step, parameters, execution)
            
            elif step.step_type == StepType.SCRIPT:
                await self._execute_script(step, parameters, execution)
            
            elif step.step_type == StepType.MANUAL:
                execution.result = StepResult.SUCCESS
                execution.stdout = "Manual step completed"
            
            elif step.step_type == StepType.WAIT:
                await asyncio.sleep(step.timeout_seconds)
                execution.result = StepResult.SUCCESS
            
            else:
                execution.result = StepResult.SUCCESS
            
            execution.status = ExecutionStatus.COMPLETED
            
        except asyncio.TimeoutError:
            execution.status = ExecutionStatus.FAILED
            execution.result = StepResult.TIMEOUT
            execution.error_message = f"Step timed out after {step.timeout_seconds}s"
        
        except Exception as e:
            execution.status = ExecutionStatus.FAILED
            execution.result = StepResult.FAILURE
            execution.error_message = str(e)
        
        finally:
            execution.completed_at = datetime.utcnow()
            if execution.started_at:
                execution.duration_seconds = (
                    execution.completed_at - execution.started_at
                ).total_seconds()
        
        return execution
    
    async def _execute_command(
        self,
        step: Step,
        parameters: Dict[str, Any],
        execution: StepExecution,
    ) -> None:
        """Execute shell command."""
        command = self._substitute_parameters(step.command, parameters)
        
        if self._dry_run:
            execution.stdout = f"[DRY RUN] Would execute: {command}"
            execution.result = StepResult.SUCCESS
            return
        
        try:
            process = await asyncio.wait_for(
                asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=step.working_directory or None,
                    env=step.environment or None,
                ),
                timeout=step.timeout_seconds,
            )
            
            stdout, stderr = await process.communicate()
            
            execution.stdout = stdout.decode("utf-8", errors="replace")
            execution.stderr = stderr.decode("utf-8", errors="replace")
            execution.exit_code = process.returncode
            
            if process.returncode == step.expected_exit_code:
                execution.result = StepResult.SUCCESS
            else:
                execution.result = StepResult.FAILURE
                execution.error_message = f"Exit code {process.returncode} != {step.expected_exit_code}"
        
        except Exception as e:
            execution.result = StepResult.FAILURE
            execution.error_message = str(e)
    
    async def _execute_script(
        self,
        step: Step,
        parameters: Dict[str, Any],
        execution: StepExecution,
    ) -> None:
        """Execute script."""
        script = self._substitute_parameters(step.script, parameters)
        
        if self._dry_run:
            execution.stdout = f"[DRY RUN] Would execute script:\n{script[:200]}"
            execution.result = StepResult.SUCCESS
            return
        
        # Write to temp file and execute
        import tempfile
        
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".sh",
            delete=False,
        ) as f:
            f.write(script)
            script_path = f.name
        
        try:
            process = await asyncio.create_subprocess_shell(
                f"bash {script_path}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=step.timeout_seconds,
            )
            
            execution.stdout = stdout.decode("utf-8", errors="replace")
            execution.stderr = stderr.decode("utf-8", errors="replace")
            execution.exit_code = process.returncode
            execution.result = StepResult.SUCCESS if process.returncode == 0 else StepResult.FAILURE
        
        finally:
            import os
            os.unlink(script_path)
    
    def _substitute_parameters(
        self,
        text: str,
        parameters: Dict[str, Any],
    ) -> str:
        """Substitute parameters in text."""
        result = text
        for key, value in parameters.items():
            result = result.replace(f"${{{key}}}", str(value))
            result = result.replace(f"${key}", str(value))
        return result


# Runbook manager
class RunbookManager:
    """Runbook manager."""
    
    def __init__(
        self,
        runbook_store: Optional[RunbookStore] = None,
        execution_store: Optional[ExecutionStore] = None,
        step_executor: Optional[StepExecutor] = None,
    ):
        self._runbook_store = runbook_store or InMemoryRunbookStore()
        self._execution_store = execution_store or InMemoryExecutionStore()
        self._step_executor = step_executor or DefaultStepExecutor()
        self._listeners: List[Callable] = []
    
    async def create(
        self,
        name: str,
        description: str = "",
        category: str = "",
        author: str = "",
        **kwargs,
    ) -> Runbook:
        """Create runbook."""
        runbook = Runbook(
            name=name,
            description=description,
            category=category,
            author=author,
            **kwargs,
        )
        
        await self._runbook_store.save(runbook)
        
        logger.info(f"Runbook created: {name}")
        
        return runbook
    
    async def get(self, runbook_id: str) -> Optional[Runbook]:
        """Get runbook."""
        return await self._runbook_store.get(runbook_id)
    
    async def list_runbooks(
        self,
        status: Optional[RunbookStatus] = None,
        category: Optional[str] = None,
    ) -> List[Runbook]:
        """List runbooks."""
        runbooks = await self._runbook_store.list_all()
        
        if status:
            runbooks = [r for r in runbooks if r.status == status]
        if category:
            runbooks = [r for r in runbooks if r.category == category]
        
        return sorted(runbooks, key=lambda r: r.name)
    
    async def update(
        self,
        runbook_id: str,
        **updates,
    ) -> Optional[Runbook]:
        """Update runbook."""
        runbook = await self._runbook_store.get(runbook_id)
        
        if not runbook:
            return None
        
        for key, value in updates.items():
            if hasattr(runbook, key):
                setattr(runbook, key, value)
        
        runbook.updated_at = datetime.utcnow()
        
        await self._runbook_store.save(runbook)
        
        logger.info(f"Runbook updated: {runbook.name}")
        
        return runbook
    
    async def add_step(
        self,
        runbook_id: str,
        name: str,
        step_type: Union[str, StepType] = StepType.COMMAND,
        command: str = "",
        **kwargs,
    ) -> Optional[Step]:
        """Add step to runbook."""
        runbook = await self._runbook_store.get(runbook_id)
        
        if not runbook:
            return None
        
        if isinstance(step_type, str):
            step_type = StepType(step_type)
        
        step = Step(
            name=name,
            step_type=step_type,
            command=command,
            order=len(runbook.steps),
            **kwargs,
        )
        
        runbook.steps.append(step)
        runbook.updated_at = datetime.utcnow()
        
        await self._runbook_store.save(runbook)
        
        logger.info(f"Step added to {runbook.name}: {name}")
        
        return step
    
    async def remove_step(
        self,
        runbook_id: str,
        step_id: str,
    ) -> bool:
        """Remove step from runbook."""
        runbook = await self._runbook_store.get(runbook_id)
        
        if not runbook:
            return False
        
        runbook.steps = [s for s in runbook.steps if s.id != step_id]
        
        # Reorder
        for i, step in enumerate(runbook.steps):
            step.order = i
        
        runbook.updated_at = datetime.utcnow()
        await self._runbook_store.save(runbook)
        
        return True
    
    async def reorder_steps(
        self,
        runbook_id: str,
        step_ids: List[str],
    ) -> Optional[Runbook]:
        """Reorder steps."""
        runbook = await self._runbook_store.get(runbook_id)
        
        if not runbook:
            return None
        
        step_map = {s.id: s for s in runbook.steps}
        runbook.steps = []
        
        for i, step_id in enumerate(step_ids):
            if step_id in step_map:
                step = step_map[step_id]
                step.order = i
                runbook.steps.append(step)
        
        runbook.updated_at = datetime.utcnow()
        await self._runbook_store.save(runbook)
        
        return runbook
    
    async def activate(self, runbook_id: str) -> Optional[Runbook]:
        """Activate runbook."""
        return await self.update(runbook_id, status=RunbookStatus.ACTIVE)
    
    async def deprecate(self, runbook_id: str) -> Optional[Runbook]:
        """Deprecate runbook."""
        return await self.update(runbook_id, status=RunbookStatus.DEPRECATED)
    
    async def execute(
        self,
        runbook_id: str,
        parameters: Optional[Dict[str, Any]] = None,
        executed_by: str = "",
        dry_run: bool = False,
    ) -> Optional[Execution]:
        """Execute runbook."""
        runbook = await self._runbook_store.get(runbook_id)
        
        if not runbook:
            return None
        
        if runbook.status != RunbookStatus.ACTIVE:
            raise RunbookError(f"Runbook is not active: {runbook.status}")
        
        # Merge parameters
        merged_params = {**runbook.parameters, **(parameters or {})}
        
        execution = Execution(
            runbook_id=runbook_id,
            runbook_name=runbook.name,
            status=ExecutionStatus.RUNNING,
            parameters=merged_params,
            started_at=datetime.utcnow(),
            executed_by=executed_by,
        )
        
        await self._execution_store.save(execution)
        
        logger.info(f"Executing runbook: {runbook.name}")
        
        # Use dry run executor if needed
        executor = (
            DefaultStepExecutor(dry_run=True) if dry_run
            else self._step_executor
        )
        
        try:
            for i, step in enumerate(runbook.steps):
                execution.current_step = i
                
                # Check skip condition
                if step.skip_if:
                    # Simple parameter check
                    if self._evaluate_condition(step.skip_if, merged_params):
                        step_exec = StepExecution(
                            step_id=step.id,
                            step_name=step.name,
                            status=ExecutionStatus.SKIPPED,
                            result=StepResult.SKIPPED,
                        )
                        execution.step_executions.append(step_exec)
                        continue
                
                # Execute with retries
                step_exec = None
                for attempt in range(step.retry_count + 1):
                    step_exec = await executor.execute(step, merged_params)
                    step_exec.attempt = attempt + 1
                    
                    if step_exec.result == StepResult.SUCCESS:
                        break
                    
                    if attempt < step.retry_count:
                        await asyncio.sleep(step.retry_delay_seconds)
                
                execution.step_executions.append(step_exec)
                
                # Check result
                if step_exec.result != StepResult.SUCCESS:
                    if not step.continue_on_failure:
                        execution.status = ExecutionStatus.FAILED
                        execution.error_message = f"Step '{step.name}' failed"
                        break
                
                await self._execution_store.save(execution)
            
            if execution.status == ExecutionStatus.RUNNING:
                execution.status = ExecutionStatus.COMPLETED
                execution.success = True
        
        except Exception as e:
            execution.status = ExecutionStatus.FAILED
            execution.error_message = str(e)
        
        finally:
            execution.completed_at = datetime.utcnow()
            execution.duration_seconds = (
                execution.completed_at - execution.started_at
            ).total_seconds()
            
            await self._execution_store.save(execution)
            await self._notify("execution_complete", execution)
        
        logger.info(f"Runbook completed: {runbook.name} - {execution.status}")
        
        return execution
    
    async def cancel_execution(
        self,
        execution_id: str,
    ) -> Optional[Execution]:
        """Cancel execution."""
        execution = await self._execution_store.get(execution_id)
        
        if not execution:
            return None
        
        if execution.status not in (
            ExecutionStatus.RUNNING,
            ExecutionStatus.PAUSED,
            ExecutionStatus.WAITING_APPROVAL,
        ):
            return execution
        
        execution.status = ExecutionStatus.CANCELLED
        execution.completed_at = datetime.utcnow()
        
        await self._execution_store.save(execution)
        
        logger.info(f"Execution cancelled: {execution_id}")
        
        return execution
    
    async def get_execution(
        self,
        execution_id: str,
    ) -> Optional[Execution]:
        """Get execution."""
        return await self._execution_store.get(execution_id)
    
    async def get_execution_history(
        self,
        runbook_id: str,
        limit: int = 50,
    ) -> List[Execution]:
        """Get execution history."""
        executions = await self._execution_store.list_by_runbook(runbook_id)
        return executions[:limit]
    
    async def get_stats(self) -> RunbookStats:
        """Get statistics."""
        runbooks = await self._runbook_store.list_all()
        executions = await self._execution_store.list_all()
        
        stats = RunbookStats(
            total_runbooks=len(runbooks),
            active=len([r for r in runbooks if r.status == RunbookStatus.ACTIVE]),
            total_executions=len(executions),
        )
        
        durations = []
        for e in executions:
            if e.status == ExecutionStatus.COMPLETED:
                if e.success:
                    stats.successful_executions += 1
                else:
                    stats.failed_executions += 1
                durations.append(e.duration_seconds)
            elif e.status == ExecutionStatus.FAILED:
                stats.failed_executions += 1
        
        if durations:
            stats.avg_duration_seconds = sum(durations) / len(durations)
        
        return stats
    
    def _evaluate_condition(
        self,
        condition: str,
        parameters: Dict[str, Any],
    ) -> bool:
        """Evaluate simple condition."""
        # Simple parameter existence check
        if condition.startswith("!"):
            return parameters.get(condition[1:]) is None
        return parameters.get(condition) is not None
    
    def add_listener(self, listener: Callable) -> None:
        """Add event listener."""
        self._listeners.append(listener)
    
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


# Factory functions
def create_runbook_manager(
    dry_run: bool = False,
) -> RunbookManager:
    """Create runbook manager."""
    executor = DefaultStepExecutor(dry_run=dry_run)
    return RunbookManager(step_executor=executor)


def create_runbook(name: str, **kwargs) -> Runbook:
    """Create runbook."""
    return Runbook(name=name, **kwargs)


def create_step(
    name: str,
    command: str = "",
    **kwargs,
) -> Step:
    """Create step."""
    return Step(name=name, command=command, **kwargs)


__all__ = [
    # Exceptions
    "RunbookError",
    "StepExecutionError",
    # Enums
    "RunbookStatus",
    "StepType",
    "ExecutionStatus",
    "StepResult",
    # Data classes
    "Step",
    "Runbook",
    "StepExecution",
    "Execution",
    "RunbookStats",
    # Stores
    "RunbookStore",
    "InMemoryRunbookStore",
    "ExecutionStore",
    "InMemoryExecutionStore",
    # Executors
    "StepExecutor",
    "DefaultStepExecutor",
    # Manager
    "RunbookManager",
    # Factory functions
    "create_runbook_manager",
    "create_runbook",
    "create_step",
]
