"""
Enterprise Chain Module.

Provides LLM chain composition, sequential processing,
and chain-of-thought patterns for agent operations.

Example:
    # Build a chain
    chain = (
        Chain()
        .prompt("Analyze this: {input}")
        .llm(openai_client)
        .parse(json_parser)
        .transform(lambda x: x["result"])
    )
    
    result = await chain.run(input="some text")
    
    # Decorators
    @chain_step(name="preprocess")
    async def preprocess(data):
        ...
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import (
    Any,
    AsyncIterator,
    Awaitable,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    TypeVar,
    Union,
)
from datetime import datetime
from functools import wraps
from enum import Enum
import logging
import time
import traceback

logger = logging.getLogger(__name__)

T = TypeVar('T')
R = TypeVar('R')
InputType = TypeVar('InputType')
OutputType = TypeVar('OutputType')


class ChainError(Exception):
    """Chain execution error."""
    pass


class ChainStepError(ChainError):
    """Error in a chain step."""
    
    def __init__(
        self,
        message: str,
        step_name: str,
        step_index: int,
        original: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.step_name = step_name
        self.step_index = step_index
        self.original = original


class ChainStatus(str, Enum):
    """Chain execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class StepResult:
    """Result of a chain step."""
    step_name: str
    step_index: int
    input_data: Any
    output_data: Any
    duration_ms: float
    success: bool
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_name": self.step_name,
            "step_index": self.step_index,
            "duration_ms": round(self.duration_ms, 2),
            "success": self.success,
            "error": self.error,
        }


@dataclass
class ChainResult:
    """Result of chain execution."""
    status: ChainStatus
    output: Any
    steps: List[StepResult] = field(default_factory=list)
    total_duration_ms: float = 0.0
    error: Optional[str] = None
    
    @property
    def success(self) -> bool:
        """Check if chain succeeded."""
        return self.status == ChainStatus.COMPLETED
    
    @property
    def step_count(self) -> int:
        """Get number of steps executed."""
        return len(self.steps)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "output": str(self.output)[:200] if self.output else None,
            "steps": [s.to_dict() for s in self.steps],
            "total_duration_ms": round(self.total_duration_ms, 2),
            "error": self.error,
        }


class ChainStep(ABC, Generic[T, R]):
    """Abstract chain step."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Get step name."""
        pass
    
    @abstractmethod
    async def execute(self, input_data: T) -> R:
        """Execute the step."""
        pass


class FunctionStep(ChainStep[T, R]):
    """Step that executes a function."""
    
    def __init__(
        self,
        func: Callable[[T], Union[R, Awaitable[R]]],
        step_name: Optional[str] = None,
    ):
        self._func = func
        self._name = step_name or func.__name__
    
    @property
    def name(self) -> str:
        return self._name
    
    async def execute(self, input_data: T) -> R:
        """Execute the function."""
        if asyncio.iscoroutinefunction(self._func):
            return await self._func(input_data)
        return self._func(input_data)


class PromptStep(ChainStep[Dict[str, Any], str]):
    """Step that formats a prompt template."""
    
    def __init__(
        self,
        template: str,
        step_name: str = "prompt",
    ):
        self._template = template
        self._name = step_name
    
    @property
    def name(self) -> str:
        return self._name
    
    async def execute(self, input_data: Dict[str, Any]) -> str:
        """Format the prompt template."""
        if isinstance(input_data, dict):
            return self._template.format(**input_data)
        return self._template.format(input=input_data)


class LLMStep(ChainStep[str, str]):
    """Step that calls an LLM."""
    
    def __init__(
        self,
        llm_client: Any,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        step_name: str = "llm",
    ):
        self._client = llm_client
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._name = step_name
    
    @property
    def name(self) -> str:
        return self._name
    
    async def execute(self, input_data: str) -> str:
        """Call the LLM."""
        # Generic LLM call pattern
        if hasattr(self._client, 'chat'):
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": input_data}],
                temperature=self._temperature,
                max_tokens=self._max_tokens,
            )
            return response.choices[0].message.content
        
        if hasattr(self._client, 'generate'):
            response = await self._client.generate(
                prompt=input_data,
                temperature=self._temperature,
                max_tokens=self._max_tokens,
            )
            return response
        
        raise ChainError(f"Unsupported LLM client: {type(self._client)}")


class ParseStep(ChainStep[str, Any]):
    """Step that parses output."""
    
    def __init__(
        self,
        parser: Callable[[str], Any],
        step_name: str = "parse",
    ):
        self._parser = parser
        self._name = step_name
    
    @property
    def name(self) -> str:
        return self._name
    
    async def execute(self, input_data: str) -> Any:
        """Parse the input."""
        if asyncio.iscoroutinefunction(self._parser):
            return await self._parser(input_data)
        return self._parser(input_data)


class BranchStep(ChainStep[T, R]):
    """Step that branches based on a condition."""
    
    def __init__(
        self,
        condition: Callable[[T], bool],
        if_true: ChainStep[T, R],
        if_false: ChainStep[T, R],
        step_name: str = "branch",
    ):
        self._condition = condition
        self._if_true = if_true
        self._if_false = if_false
        self._name = step_name
    
    @property
    def name(self) -> str:
        return self._name
    
    async def execute(self, input_data: T) -> R:
        """Execute the appropriate branch."""
        if asyncio.iscoroutinefunction(self._condition):
            result = await self._condition(input_data)
        else:
            result = self._condition(input_data)
        
        if result:
            return await self._if_true.execute(input_data)
        return await self._if_false.execute(input_data)


class MapStep(ChainStep[List[T], List[R]]):
    """Step that maps over a list."""
    
    def __init__(
        self,
        step: ChainStep[T, R],
        parallel: bool = True,
        step_name: str = "map",
    ):
        self._step = step
        self._parallel = parallel
        self._name = step_name
    
    @property
    def name(self) -> str:
        return self._name
    
    async def execute(self, input_data: List[T]) -> List[R]:
        """Map the step over the list."""
        if self._parallel:
            tasks = [self._step.execute(item) for item in input_data]
            return await asyncio.gather(*tasks)
        
        results = []
        for item in input_data:
            result = await self._step.execute(item)
            results.append(result)
        return results


class ReduceStep(ChainStep[List[T], R]):
    """Step that reduces a list to a single value."""
    
    def __init__(
        self,
        reducer: Callable[[R, T], R],
        initial: R,
        step_name: str = "reduce",
    ):
        self._reducer = reducer
        self._initial = initial
        self._name = step_name
    
    @property
    def name(self) -> str:
        return self._name
    
    async def execute(self, input_data: List[T]) -> R:
        """Reduce the list."""
        result = self._initial
        
        for item in input_data:
            if asyncio.iscoroutinefunction(self._reducer):
                result = await self._reducer(result, item)
            else:
                result = self._reducer(result, item)
        
        return result


class Chain(Generic[InputType, OutputType]):
    """
    LLM chain for sequential processing.
    """
    
    def __init__(
        self,
        name: str = "chain",
        steps: Optional[List[ChainStep]] = None,
    ):
        """
        Initialize chain.
        
        Args:
            name: Chain name
            steps: Initial steps
        """
        self._name = name
        self._steps: List[ChainStep] = list(steps) if steps else []
        self._on_step: Optional[Callable[[StepResult], None]] = None
        self._on_error: Optional[Callable[[ChainStepError], None]] = None
    
    @property
    def name(self) -> str:
        return self._name
    
    def add(self, step: ChainStep) -> 'Chain':
        """Add a step to the chain."""
        self._steps.append(step)
        return self
    
    def prompt(
        self,
        template: str,
        name: str = "prompt",
    ) -> 'Chain':
        """Add a prompt formatting step."""
        return self.add(PromptStep(template, name))
    
    def llm(
        self,
        client: Any,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        name: str = "llm",
    ) -> 'Chain':
        """Add an LLM call step."""
        return self.add(LLMStep(client, model, temperature, max_tokens, name))
    
    def parse(
        self,
        parser: Callable[[str], Any],
        name: str = "parse",
    ) -> 'Chain':
        """Add a parsing step."""
        return self.add(ParseStep(parser, name))
    
    def transform(
        self,
        func: Callable[[Any], Any],
        name: Optional[str] = None,
    ) -> 'Chain':
        """Add a transformation step."""
        return self.add(FunctionStep(func, name))
    
    def branch(
        self,
        condition: Callable[[Any], bool],
        if_true: ChainStep,
        if_false: ChainStep,
        name: str = "branch",
    ) -> 'Chain':
        """Add a branching step."""
        return self.add(BranchStep(condition, if_true, if_false, name))
    
    def map(
        self,
        step: ChainStep,
        parallel: bool = True,
        name: str = "map",
    ) -> 'Chain':
        """Add a map step."""
        return self.add(MapStep(step, parallel, name))
    
    def on_step(
        self,
        callback: Callable[[StepResult], None],
    ) -> 'Chain':
        """Set step callback."""
        self._on_step = callback
        return self
    
    def on_error(
        self,
        callback: Callable[[ChainStepError], None],
    ) -> 'Chain':
        """Set error callback."""
        self._on_error = callback
        return self
    
    async def run(
        self,
        input_data: Any = None,
        **kwargs: Any,
    ) -> ChainResult:
        """
        Run the chain.
        
        Args:
            input_data: Initial input (or pass as kwargs)
            **kwargs: Named inputs
            
        Returns:
            Chain result
        """
        if input_data is None and kwargs:
            input_data = kwargs
        
        start_time = time.time()
        steps_results = []
        current_data = input_data
        
        for i, step in enumerate(self._steps):
            step_start = time.time()
            
            try:
                output = await step.execute(current_data)
                step_duration = (time.time() - step_start) * 1000
                
                result = StepResult(
                    step_name=step.name,
                    step_index=i,
                    input_data=current_data,
                    output_data=output,
                    duration_ms=step_duration,
                    success=True,
                )
                
                steps_results.append(result)
                
                if self._on_step:
                    self._on_step(result)
                
                current_data = output
                
            except Exception as e:
                step_duration = (time.time() - step_start) * 1000
                
                error = ChainStepError(
                    str(e),
                    step_name=step.name,
                    step_index=i,
                    original=e,
                )
                
                if self._on_error:
                    self._on_error(error)
                
                result = StepResult(
                    step_name=step.name,
                    step_index=i,
                    input_data=current_data,
                    output_data=None,
                    duration_ms=step_duration,
                    success=False,
                    error=str(e),
                )
                
                steps_results.append(result)
                
                return ChainResult(
                    status=ChainStatus.FAILED,
                    output=None,
                    steps=steps_results,
                    total_duration_ms=(time.time() - start_time) * 1000,
                    error=str(error),
                )
        
        return ChainResult(
            status=ChainStatus.COMPLETED,
            output=current_data,
            steps=steps_results,
            total_duration_ms=(time.time() - start_time) * 1000,
        )
    
    async def stream(
        self,
        input_data: Any = None,
        **kwargs: Any,
    ) -> AsyncIterator[StepResult]:
        """
        Stream chain execution.
        
        Yields step results as they complete.
        """
        if input_data is None and kwargs:
            input_data = kwargs
        
        current_data = input_data
        
        for i, step in enumerate(self._steps):
            step_start = time.time()
            
            try:
                output = await step.execute(current_data)
                step_duration = (time.time() - step_start) * 1000
                
                result = StepResult(
                    step_name=step.name,
                    step_index=i,
                    input_data=current_data,
                    output_data=output,
                    duration_ms=step_duration,
                    success=True,
                )
                
                yield result
                current_data = output
                
            except Exception as e:
                step_duration = (time.time() - step_start) * 1000
                
                result = StepResult(
                    step_name=step.name,
                    step_index=i,
                    input_data=current_data,
                    output_data=None,
                    duration_ms=step_duration,
                    success=False,
                    error=str(e),
                )
                
                yield result
                break
    
    def __or__(self, other: ChainStep) -> 'Chain':
        """Pipe operator to add steps."""
        return self.add(other)
    
    def __rshift__(self, func: Callable) -> 'Chain':
        """Right shift to add transform."""
        return self.transform(func)


class ParallelChain:
    """
    Execute multiple chains in parallel.
    """
    
    def __init__(self, chains: Optional[List[Chain]] = None):
        self._chains = list(chains) if chains else []
    
    def add(self, chain: Chain) -> 'ParallelChain':
        """Add a chain."""
        self._chains.append(chain)
        return self
    
    async def run(
        self,
        input_data: Any,
        merge: Optional[Callable[[List[Any]], Any]] = None,
    ) -> List[ChainResult]:
        """Run all chains in parallel."""
        tasks = [chain.run(input_data) for chain in self._chains]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        chain_results = []
        for result in results:
            if isinstance(result, Exception):
                chain_results.append(ChainResult(
                    status=ChainStatus.FAILED,
                    output=None,
                    error=str(result),
                ))
            else:
                chain_results.append(result)
        
        return chain_results


class SequentialChain:
    """
    Execute chains sequentially, passing output to next chain.
    """
    
    def __init__(self, chains: Optional[List[Chain]] = None):
        self._chains = list(chains) if chains else []
    
    def add(self, chain: Chain) -> 'SequentialChain':
        """Add a chain."""
        self._chains.append(chain)
        return self
    
    async def run(self, input_data: Any) -> ChainResult:
        """Run chains sequentially."""
        current_data = input_data
        all_steps = []
        start_time = time.time()
        
        for chain in self._chains:
            result = await chain.run(current_data)
            all_steps.extend(result.steps)
            
            if not result.success:
                return ChainResult(
                    status=ChainStatus.FAILED,
                    output=None,
                    steps=all_steps,
                    total_duration_ms=(time.time() - start_time) * 1000,
                    error=result.error,
                )
            
            current_data = result.output
        
        return ChainResult(
            status=ChainStatus.COMPLETED,
            output=current_data,
            steps=all_steps,
            total_duration_ms=(time.time() - start_time) * 1000,
        )


def chain_step(
    name: Optional[str] = None,
) -> Callable:
    """
    Decorator to create a chain step from a function.
    
    Example:
        @chain_step(name="preprocess")
        async def preprocess(data):
            return processed_data
    """
    def decorator(func: Callable) -> FunctionStep:
        step_name = name or func.__name__
        return FunctionStep(func, step_name)
    
    return decorator


def create_chain(
    *steps: Union[ChainStep, Callable],
    name: str = "chain",
) -> Chain:
    """
    Factory function to create a chain.
    
    Example:
        chain = create_chain(
            preprocess,
            analyze,
            format_output,
            name="analysis_chain",
        )
    """
    chain = Chain(name=name)
    
    for step in steps:
        if isinstance(step, ChainStep):
            chain.add(step)
        elif callable(step):
            chain.add(FunctionStep(step))
    
    return chain


__all__ = [
    # Exceptions
    "ChainError",
    "ChainStepError",
    # Enums
    "ChainStatus",
    # Data classes
    "StepResult",
    "ChainResult",
    # Steps
    "ChainStep",
    "FunctionStep",
    "PromptStep",
    "LLMStep",
    "ParseStep",
    "BranchStep",
    "MapStep",
    "ReduceStep",
    # Chains
    "Chain",
    "ParallelChain",
    "SequentialChain",
    # Decorators
    "chain_step",
    # Factory
    "create_chain",
]
