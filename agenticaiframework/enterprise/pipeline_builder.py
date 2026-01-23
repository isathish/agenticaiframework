"""
Enterprise Pipeline Builder Module.

Provides pipeline builder, fluent API, step chains,
parallel pipelines, and data transformation pipelines.

Example:
    # Create pipeline
    pipeline = (
        create_pipeline("data-processing")
        .add_step(validate_data)
        .add_step(transform_data)
        .add_step(save_data)
        .build()
    )
    
    # Execute pipeline
    result = await pipeline.execute(data)
    
    # Use decorator
    @pipeline_step(order=1)
    async def step_one(data):
        ...
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Tuple,
    TypeVar,
    Union,
)

T = TypeVar('T')
R = TypeVar('R')
Input = TypeVar('Input')
Output = TypeVar('Output')


logger = logging.getLogger(__name__)


class PipelineError(Exception):
    """Base pipeline error."""
    pass


class StepExecutionError(PipelineError):
    """Step execution failed."""
    
    def __init__(self, step_name: str, cause: Exception):
        super().__init__(f"Step '{step_name}' failed: {cause}")
        self.step_name = step_name
        self.cause = cause


class PipelineAbortedError(PipelineError):
    """Pipeline was aborted."""
    pass


class PipelineState(str, Enum):
    """Pipeline execution state."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


class StepState(str, Enum):
    """Step state."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class StepConfig:
    """Step configuration."""
    name: str
    timeout: Optional[float] = None
    retry_count: int = 0
    retry_delay: float = 1.0
    continue_on_error: bool = False
    condition: Optional[Callable[[Any], bool]] = None


@dataclass
class StepResult:
    """Step execution result."""
    name: str
    state: StepState
    input_data: Any
    output_data: Any
    error: Optional[Exception] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration: float = 0.0
    retries: int = 0


@dataclass
class PipelineResult:
    """Pipeline execution result."""
    pipeline_id: str
    state: PipelineState
    input_data: Any
    output_data: Any
    steps: List[StepResult]
    started_at: datetime
    completed_at: Optional[datetime]
    duration: float
    
    @property
    def is_success(self) -> bool:
        return self.state == PipelineState.COMPLETED
    
    @property
    def failed_steps(self) -> List[StepResult]:
        return [s for s in self.steps if s.state == StepState.FAILED]


@dataclass
class PipelineStats:
    """Pipeline statistics."""
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    avg_duration: float = 0.0


class Step(ABC, Generic[Input, Output]):
    """
    Abstract pipeline step.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Step name."""
        pass
    
    @abstractmethod
    async def execute(self, input_data: Input) -> Output:
        """Execute the step."""
        pass


class FunctionStep(Step[Input, Output]):
    """
    Function-based step.
    """
    
    def __init__(
        self,
        func: Callable[[Input], Output],
        config: Optional[StepConfig] = None,
    ):
        self._func = func
        self._config = config or StepConfig(name=func.__name__)
    
    @property
    def name(self) -> str:
        return self._config.name
    
    @property
    def config(self) -> StepConfig:
        return self._config
    
    async def execute(self, input_data: Input) -> Output:
        result = self._func(input_data)
        if asyncio.iscoroutine(result):
            return await result
        return result


class ConditionalStep(Step[Input, Output]):
    """
    Conditional step that executes based on condition.
    """
    
    def __init__(
        self,
        step: Step[Input, Output],
        condition: Callable[[Input], bool],
        else_step: Optional[Step[Input, Output]] = None,
    ):
        self._step = step
        self._condition = condition
        self._else_step = else_step
    
    @property
    def name(self) -> str:
        return f"conditional:{self._step.name}"
    
    async def execute(self, input_data: Input) -> Output:
        should_run = self._condition(input_data)
        
        if should_run:
            return await self._step.execute(input_data)
        elif self._else_step:
            return await self._else_step.execute(input_data)
        else:
            return input_data  # type: ignore


class ParallelStep(Step[Input, List[Output]]):
    """
    Parallel execution of multiple steps.
    """
    
    def __init__(self, steps: List[Step[Input, Output]]):
        self._steps = steps
    
    @property
    def name(self) -> str:
        return f"parallel:[{','.join(s.name for s in self._steps)}]"
    
    async def execute(self, input_data: Input) -> List[Output]:
        tasks = [step.execute(input_data) for step in self._steps]
        return await asyncio.gather(*tasks)


class BranchStep(Step[Input, Dict[str, Any]]):
    """
    Branch execution based on key function.
    """
    
    def __init__(
        self,
        branches: Dict[str, Step[Input, Any]],
        key_func: Callable[[Input], str],
        default: Optional[Step[Input, Any]] = None,
    ):
        self._branches = branches
        self._key_func = key_func
        self._default = default
    
    @property
    def name(self) -> str:
        return f"branch:[{','.join(self._branches.keys())}]"
    
    async def execute(self, input_data: Input) -> Dict[str, Any]:
        key = self._key_func(input_data)
        
        step = self._branches.get(key, self._default)
        if step:
            result = await step.execute(input_data)
            return {"branch": key, "result": result}
        
        return {"branch": key, "result": None}


class Pipeline(ABC, Generic[Input, Output]):
    """
    Abstract pipeline.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Pipeline name."""
        pass
    
    @abstractmethod
    async def execute(self, input_data: Input) -> PipelineResult:
        """Execute the pipeline."""
        pass


class SequentialPipeline(Pipeline[Input, Output]):
    """
    Sequential pipeline execution.
    """
    
    def __init__(
        self,
        name: str,
        steps: List[Step],
        on_step_complete: Optional[Callable[[StepResult], None]] = None,
        on_step_error: Optional[Callable[[StepResult], None]] = None,
    ):
        self._name = name
        self._steps = steps
        self._on_step_complete = on_step_complete
        self._on_step_error = on_step_error
        self._stats = PipelineStats()
        self._aborted = False
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def steps(self) -> List[Step]:
        return self._steps
    
    async def execute(self, input_data: Input) -> PipelineResult:
        pipeline_id = str(uuid.uuid4())
        start_time = time.time()
        started_at = datetime.utcnow()
        
        step_results: List[StepResult] = []
        current_data = input_data
        final_state = PipelineState.RUNNING
        
        self._stats.total_executions += 1
        self._aborted = False
        
        try:
            for step in self._steps:
                if self._aborted:
                    final_state = PipelineState.ABORTED
                    break
                
                step_result = await self._execute_step(step, current_data)
                step_results.append(step_result)
                
                # Callbacks
                if step_result.state == StepState.COMPLETED:
                    if self._on_step_complete:
                        self._on_step_complete(step_result)
                    current_data = step_result.output_data
                elif step_result.state == StepState.FAILED:
                    if self._on_step_error:
                        self._on_step_error(step_result)
                    
                    # Check if should continue
                    if hasattr(step, 'config') and step.config.continue_on_error:
                        continue
                    else:
                        final_state = PipelineState.FAILED
                        break
            
            if final_state == PipelineState.RUNNING:
                final_state = PipelineState.COMPLETED
                self._stats.successful_executions += 1
            else:
                self._stats.failed_executions += 1
                
        except Exception as e:
            final_state = PipelineState.FAILED
            self._stats.failed_executions += 1
            logger.error(f"Pipeline {self._name} failed: {e}")
        
        duration = time.time() - start_time
        
        # Update avg duration
        total = self._stats.successful_executions + self._stats.failed_executions
        self._stats.avg_duration = (
            (self._stats.avg_duration * (total - 1) + duration) / total
            if total > 0 else duration
        )
        
        return PipelineResult(
            pipeline_id=pipeline_id,
            state=final_state,
            input_data=input_data,
            output_data=current_data,
            steps=step_results,
            started_at=started_at,
            completed_at=datetime.utcnow(),
            duration=duration,
        )
    
    async def _execute_step(
        self,
        step: Step,
        input_data: Any,
    ) -> StepResult:
        """Execute a single step with retries."""
        step_name = step.name
        config = getattr(step, 'config', StepConfig(name=step_name))
        
        start_time = time.time()
        started_at = datetime.utcnow()
        retries = 0
        
        # Check condition
        if config.condition and not config.condition(input_data):
            return StepResult(
                name=step_name,
                state=StepState.SKIPPED,
                input_data=input_data,
                output_data=input_data,
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )
        
        last_error = None
        
        while retries <= config.retry_count:
            try:
                # Execute with timeout
                if config.timeout:
                    output = await asyncio.wait_for(
                        step.execute(input_data),
                        timeout=config.timeout,
                    )
                else:
                    output = await step.execute(input_data)
                
                return StepResult(
                    name=step_name,
                    state=StepState.COMPLETED,
                    input_data=input_data,
                    output_data=output,
                    started_at=started_at,
                    completed_at=datetime.utcnow(),
                    duration=time.time() - start_time,
                    retries=retries,
                )
                
            except Exception as e:
                last_error = e
                retries += 1
                
                if retries <= config.retry_count:
                    await asyncio.sleep(config.retry_delay)
        
        return StepResult(
            name=step_name,
            state=StepState.FAILED,
            input_data=input_data,
            output_data=None,
            error=last_error,
            started_at=started_at,
            completed_at=datetime.utcnow(),
            duration=time.time() - start_time,
            retries=retries - 1,
        )
    
    def abort(self) -> None:
        """Abort the pipeline."""
        self._aborted = True
    
    async def stats(self) -> PipelineStats:
        return self._stats


class PipelineBuilder(Generic[Input, Output]):
    """
    Fluent pipeline builder.
    """
    
    def __init__(self, name: str):
        self._name = name
        self._steps: List[Step] = []
        self._on_step_complete: Optional[Callable] = None
        self._on_step_error: Optional[Callable] = None
    
    def add_step(
        self,
        step: Union[Step, Callable],
        name: Optional[str] = None,
        timeout: Optional[float] = None,
        retry_count: int = 0,
        continue_on_error: bool = False,
    ) -> "PipelineBuilder":
        """Add a step to the pipeline."""
        if callable(step) and not isinstance(step, Step):
            config = StepConfig(
                name=name or step.__name__,
                timeout=timeout,
                retry_count=retry_count,
                continue_on_error=continue_on_error,
            )
            step = FunctionStep(step, config)
        
        self._steps.append(step)
        return self
    
    def then(
        self,
        func: Callable,
        **kwargs,
    ) -> "PipelineBuilder":
        """Add step using 'then' syntax."""
        return self.add_step(func, **kwargs)
    
    def parallel(
        self,
        *steps: Union[Step, Callable],
    ) -> "PipelineBuilder":
        """Add parallel steps."""
        converted: List[Step] = []
        for s in steps:
            if callable(s) and not isinstance(s, Step):
                converted.append(FunctionStep(s))
            else:
                converted.append(s)
        
        self._steps.append(ParallelStep(converted))
        return self
    
    def branch(
        self,
        branches: Dict[str, Union[Step, Callable]],
        key_func: Callable[[Any], str],
        default: Optional[Union[Step, Callable]] = None,
    ) -> "PipelineBuilder":
        """Add branching step."""
        converted: Dict[str, Step] = {}
        for k, v in branches.items():
            if callable(v) and not isinstance(v, Step):
                converted[k] = FunctionStep(v)
            else:
                converted[k] = v
        
        default_step = None
        if default:
            if callable(default) and not isinstance(default, Step):
                default_step = FunctionStep(default)
            else:
                default_step = default
        
        self._steps.append(BranchStep(converted, key_func, default_step))
        return self
    
    def conditional(
        self,
        condition: Callable[[Any], bool],
        step: Union[Step, Callable],
        else_step: Optional[Union[Step, Callable]] = None,
    ) -> "PipelineBuilder":
        """Add conditional step."""
        if callable(step) and not isinstance(step, Step):
            step = FunctionStep(step)
        
        else_converted = None
        if else_step:
            if callable(else_step) and not isinstance(else_step, Step):
                else_converted = FunctionStep(else_step)
            else:
                else_converted = else_step
        
        self._steps.append(ConditionalStep(step, condition, else_converted))
        return self
    
    def when(
        self,
        condition: Callable[[Any], bool],
        step: Union[Step, Callable],
    ) -> "PipelineBuilder":
        """Add conditional step (alias)."""
        return self.conditional(condition, step)
    
    def on_step_complete(self, callback: Callable[[StepResult], None]) -> "PipelineBuilder":
        """Set step completion callback."""
        self._on_step_complete = callback
        return self
    
    def on_step_error(self, callback: Callable[[StepResult], None]) -> "PipelineBuilder":
        """Set step error callback."""
        self._on_step_error = callback
        return self
    
    def build(self) -> SequentialPipeline:
        """Build the pipeline."""
        return SequentialPipeline(
            name=self._name,
            steps=self._steps,
            on_step_complete=self._on_step_complete,
            on_step_error=self._on_step_error,
        )


class PipelineComposer:
    """
    Compose multiple pipelines.
    """
    
    def __init__(self, name: str):
        self._name = name
        self._pipelines: List[Pipeline] = []
    
    def add(self, pipeline: Pipeline) -> "PipelineComposer":
        """Add pipeline to composition."""
        self._pipelines.append(pipeline)
        return self
    
    def sequence(self, *pipelines: Pipeline) -> "PipelineComposer":
        """Add pipelines in sequence."""
        self._pipelines.extend(pipelines)
        return self
    
    async def execute(self, input_data: Any) -> List[PipelineResult]:
        """Execute composed pipelines."""
        results = []
        current_data = input_data
        
        for pipeline in self._pipelines:
            result = await pipeline.execute(current_data)
            results.append(result)
            
            if result.state != PipelineState.COMPLETED:
                break
            
            current_data = result.output_data
        
        return results


class PipelineRegistry:
    """Registry for pipelines."""
    
    def __init__(self):
        self._pipelines: Dict[str, Pipeline] = {}
        self._default: Optional[str] = None
    
    def register(
        self,
        name: str,
        pipeline: Pipeline,
        default: bool = False,
    ) -> None:
        self._pipelines[name] = pipeline
        if default or self._default is None:
            self._default = name
    
    def get(self, name: Optional[str] = None) -> Pipeline:
        name = name or self._default
        if not name or name not in self._pipelines:
            raise PipelineError(f"Pipeline not found: {name}")
        return self._pipelines[name]


# Global registry
_global_registry = PipelineRegistry()


# Decorators
def pipeline_step(
    name: Optional[str] = None,
    order: int = 0,
    timeout: Optional[float] = None,
    retry_count: int = 0,
) -> Callable:
    """
    Decorator to mark function as pipeline step.
    
    Example:
        @pipeline_step(order=1)
        async def validate(data):
            ...
    """
    def decorator(func: Callable) -> Callable:
        func._step_config = StepConfig(
            name=name or func.__name__,
            timeout=timeout,
            retry_count=retry_count,
        )
        func._step_order = order
        return func
    
    return decorator


def step(func: Callable) -> FunctionStep:
    """
    Convert function to step.
    
    Example:
        my_step = step(lambda x: x * 2)
    """
    return FunctionStep(func)


# Factory functions
def create_pipeline(name: str) -> PipelineBuilder:
    """Create a pipeline builder."""
    return PipelineBuilder(name)


def create_step(
    func: Callable,
    name: Optional[str] = None,
    timeout: Optional[float] = None,
    retry_count: int = 0,
) -> FunctionStep:
    """Create a function step."""
    config = StepConfig(
        name=name or func.__name__,
        timeout=timeout,
        retry_count=retry_count,
    )
    return FunctionStep(func, config)


def create_parallel_step(*funcs: Callable) -> ParallelStep:
    """Create a parallel step."""
    steps = [FunctionStep(f) for f in funcs]
    return ParallelStep(steps)


def create_pipeline_composer(name: str) -> PipelineComposer:
    """Create a pipeline composer."""
    return PipelineComposer(name)


def register_pipeline(
    name: str,
    pipeline: Pipeline,
    default: bool = False,
) -> None:
    """Register pipeline in global registry."""
    _global_registry.register(name, pipeline, default)


def get_pipeline(name: Optional[str] = None) -> Pipeline:
    """Get pipeline from global registry."""
    return _global_registry.get(name)


__all__ = [
    # Exceptions
    "PipelineError",
    "StepExecutionError",
    "PipelineAbortedError",
    # Enums
    "PipelineState",
    "StepState",
    # Data classes
    "StepConfig",
    "StepResult",
    "PipelineResult",
    "PipelineStats",
    # Steps
    "Step",
    "FunctionStep",
    "ConditionalStep",
    "ParallelStep",
    "BranchStep",
    # Pipeline
    "Pipeline",
    "SequentialPipeline",
    "PipelineBuilder",
    "PipelineComposer",
    # Registry
    "PipelineRegistry",
    # Decorators
    "pipeline_step",
    "step",
    # Factory functions
    "create_pipeline",
    "create_step",
    "create_parallel_step",
    "create_pipeline_composer",
    "register_pipeline",
    "get_pipeline",
]
