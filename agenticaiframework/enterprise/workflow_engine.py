"""
Enterprise Workflow Engine Module.

Provides workflow engine, state machines, transitions,
workflow versioning, and workflow orchestration.

Example:
    # Create workflow
    workflow = (
        create_workflow("order-process")
        .add_state("pending")
        .add_state("processing")
        .add_state("completed")
        .add_transition("pending", "processing", on="start")
        .add_transition("processing", "completed", on="finish")
        .build()
    )
    
    # Execute workflow
    instance = await workflow.start(order_data)
    await instance.trigger("start")
"""

from __future__ import annotations

import asyncio
import logging
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
    Set,
    Tuple,
    TypeVar,
)

T = TypeVar('T')


logger = logging.getLogger(__name__)


class WorkflowError(Exception):
    """Base workflow error."""
    pass


class InvalidTransitionError(WorkflowError):
    """Invalid state transition."""
    pass


class WorkflowAbortedError(WorkflowError):
    """Workflow was aborted."""
    pass


class StateNotFoundError(WorkflowError):
    """State not found."""
    pass


class WorkflowState(str, Enum):
    """Workflow instance state."""
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


class StateType(str, Enum):
    """State type."""
    INITIAL = "initial"
    NORMAL = "normal"
    FINAL = "final"


@dataclass
class State:
    """Workflow state."""
    name: str
    state_type: StateType = StateType.NORMAL
    on_enter: Optional[Callable] = None
    on_exit: Optional[Callable] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Transition:
    """State transition."""
    source: str
    target: str
    event: str
    guard: Optional[Callable[..., bool]] = None
    action: Optional[Callable] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowConfig:
    """Workflow configuration."""
    name: str
    version: str = "1.0"
    description: str = ""
    timeout: Optional[float] = None
    max_transitions: int = 1000


@dataclass
class WorkflowContext:
    """Workflow execution context."""
    instance_id: str
    workflow_name: str
    data: Dict[str, Any] = field(default_factory=dict)
    history: List[Tuple[str, str, datetime]] = field(default_factory=list)
    
    def set(self, key: str, value: Any) -> None:
        self.data[key] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)


@dataclass
class WorkflowStats:
    """Workflow statistics."""
    total_instances: int = 0
    active_instances: int = 0
    completed_instances: int = 0
    failed_instances: int = 0
    avg_duration: float = 0.0


class StateMachine:
    """
    Finite state machine implementation.
    """
    
    def __init__(self, name: str):
        self._name = name
        self._states: Dict[str, State] = {}
        self._transitions: Dict[str, List[Transition]] = {}
        self._initial: Optional[str] = None
        self._finals: Set[str] = set()
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def initial_state(self) -> Optional[str]:
        return self._initial
    
    @property
    def final_states(self) -> Set[str]:
        return self._finals
    
    def add_state(
        self,
        name: str,
        state_type: StateType = StateType.NORMAL,
        on_enter: Optional[Callable] = None,
        on_exit: Optional[Callable] = None,
    ) -> "StateMachine":
        state = State(
            name=name,
            state_type=state_type,
            on_enter=on_enter,
            on_exit=on_exit,
        )
        self._states[name] = state
        
        if state_type == StateType.INITIAL:
            self._initial = name
        elif state_type == StateType.FINAL:
            self._finals.add(name)
        
        return self
    
    def add_transition(
        self,
        source: str,
        target: str,
        event: str,
        guard: Optional[Callable[..., bool]] = None,
        action: Optional[Callable] = None,
    ) -> "StateMachine":
        transition = Transition(
            source=source,
            target=target,
            event=event,
            guard=guard,
            action=action,
        )
        
        if source not in self._transitions:
            self._transitions[source] = []
        
        self._transitions[source].append(transition)
        return self
    
    def get_state(self, name: str) -> Optional[State]:
        return self._states.get(name)
    
    def get_transitions(self, state: str) -> List[Transition]:
        return self._transitions.get(state, [])
    
    def can_transition(
        self,
        current: str,
        event: str,
        context: Optional[WorkflowContext] = None,
    ) -> bool:
        transitions = self.get_transitions(current)
        
        for trans in transitions:
            if trans.event != event:
                continue
            
            if trans.guard:
                try:
                    if asyncio.iscoroutinefunction(trans.guard):
                        return False  # Can't check async guards synchronously
                    if not trans.guard(context):
                        continue
                except Exception:
                    continue
            
            return True
        
        return False


class WorkflowInstance:
    """
    Workflow instance (execution).
    """
    
    def __init__(
        self,
        instance_id: str,
        state_machine: StateMachine,
        context: WorkflowContext,
    ):
        self._id = instance_id
        self._machine = state_machine
        self._context = context
        self._current_state = state_machine.initial_state
        self._workflow_state = WorkflowState.CREATED
        self._started_at: Optional[datetime] = None
        self._completed_at: Optional[datetime] = None
        self._transition_count = 0
    
    @property
    def id(self) -> str:
        return self._id
    
    @property
    def current_state(self) -> Optional[str]:
        return self._current_state
    
    @property
    def workflow_state(self) -> WorkflowState:
        return self._workflow_state
    
    @property
    def context(self) -> WorkflowContext:
        return self._context
    
    @property
    def is_completed(self) -> bool:
        return self._workflow_state in (
            WorkflowState.COMPLETED,
            WorkflowState.FAILED,
            WorkflowState.ABORTED,
        )
    
    async def start(self) -> None:
        """Start the workflow."""
        if self._workflow_state != WorkflowState.CREATED:
            raise WorkflowError("Workflow already started")
        
        self._workflow_state = WorkflowState.RUNNING
        self._started_at = datetime.utcnow()
        
        # Execute on_enter for initial state
        if self._current_state:
            state = self._machine.get_state(self._current_state)
            if state and state.on_enter:
                await self._execute_callback(state.on_enter)
    
    async def trigger(self, event: str) -> bool:
        """Trigger an event."""
        if self._workflow_state != WorkflowState.RUNNING:
            raise WorkflowError(f"Workflow is not running: {self._workflow_state}")
        
        if not self._current_state:
            raise WorkflowError("No current state")
        
        transitions = self._machine.get_transitions(self._current_state)
        
        for trans in transitions:
            if trans.event != event:
                continue
            
            # Check guard
            if trans.guard:
                try:
                    result = await self._execute_callback(trans.guard, self._context)
                    if not result:
                        continue
                except Exception:
                    continue
            
            # Execute transition
            await self._execute_transition(trans)
            return True
        
        return False
    
    async def _execute_transition(self, transition: Transition) -> None:
        """Execute a transition."""
        source_state = self._machine.get_state(transition.source)
        target_state = self._machine.get_state(transition.target)
        
        # Exit source state
        if source_state and source_state.on_exit:
            await self._execute_callback(source_state.on_exit, self._context)
        
        # Execute transition action
        if transition.action:
            await self._execute_callback(transition.action, self._context)
        
        # Update state
        self._current_state = transition.target
        self._transition_count += 1
        self._context.history.append((
            transition.source,
            transition.target,
            datetime.utcnow(),
        ))
        
        # Enter target state
        if target_state and target_state.on_enter:
            await self._execute_callback(target_state.on_enter, self._context)
        
        # Check if final
        if target_state and target_state.state_type == StateType.FINAL:
            self._workflow_state = WorkflowState.COMPLETED
            self._completed_at = datetime.utcnow()
    
    async def _execute_callback(self, callback: Callable, *args) -> Any:
        """Execute a callback."""
        if asyncio.iscoroutinefunction(callback):
            return await callback(*args)
        return callback(*args)
    
    async def pause(self) -> None:
        """Pause the workflow."""
        if self._workflow_state == WorkflowState.RUNNING:
            self._workflow_state = WorkflowState.PAUSED
    
    async def resume(self) -> None:
        """Resume the workflow."""
        if self._workflow_state == WorkflowState.PAUSED:
            self._workflow_state = WorkflowState.RUNNING
    
    async def abort(self) -> None:
        """Abort the workflow."""
        if self._workflow_state in (WorkflowState.RUNNING, WorkflowState.PAUSED):
            self._workflow_state = WorkflowState.ABORTED
            self._completed_at = datetime.utcnow()
    
    def available_events(self) -> List[str]:
        """Get available events from current state."""
        if not self._current_state:
            return []
        
        transitions = self._machine.get_transitions(self._current_state)
        return [t.event for t in transitions]


class Workflow:
    """
    Workflow definition and factory.
    """
    
    def __init__(
        self,
        config: WorkflowConfig,
        state_machine: StateMachine,
    ):
        self._config = config
        self._machine = state_machine
        self._instances: Dict[str, WorkflowInstance] = {}
        self._stats = WorkflowStats()
    
    @property
    def name(self) -> str:
        return self._config.name
    
    @property
    def version(self) -> str:
        return self._config.version
    
    async def start(
        self,
        data: Optional[Dict[str, Any]] = None,
        instance_id: Optional[str] = None,
    ) -> WorkflowInstance:
        """Start a new workflow instance."""
        instance_id = instance_id or str(uuid.uuid4())
        
        context = WorkflowContext(
            instance_id=instance_id,
            workflow_name=self._config.name,
            data=data or {},
        )
        
        instance = WorkflowInstance(instance_id, self._machine, context)
        self._instances[instance_id] = instance
        
        await instance.start()
        
        self._stats.total_instances += 1
        self._stats.active_instances += 1
        
        return instance
    
    def get_instance(self, instance_id: str) -> Optional[WorkflowInstance]:
        """Get workflow instance."""
        return self._instances.get(instance_id)
    
    def list_instances(
        self,
        state: Optional[WorkflowState] = None,
    ) -> List[WorkflowInstance]:
        """List workflow instances."""
        instances = list(self._instances.values())
        
        if state:
            instances = [i for i in instances if i.workflow_state == state]
        
        return instances
    
    async def stats(self) -> WorkflowStats:
        return self._stats


class WorkflowBuilder:
    """
    Fluent workflow builder.
    """
    
    def __init__(self, name: str):
        self._name = name
        self._version = "1.0"
        self._description = ""
        self._states: Dict[str, State] = {}
        self._transitions: List[Transition] = []
        self._initial: Optional[str] = None
        self._finals: Set[str] = set()
    
    def version(self, version: str) -> "WorkflowBuilder":
        self._version = version
        return self
    
    def description(self, description: str) -> "WorkflowBuilder":
        self._description = description
        return self
    
    def add_state(
        self,
        name: str,
        initial: bool = False,
        final: bool = False,
        on_enter: Optional[Callable] = None,
        on_exit: Optional[Callable] = None,
    ) -> "WorkflowBuilder":
        if initial:
            state_type = StateType.INITIAL
            self._initial = name
        elif final:
            state_type = StateType.FINAL
            self._finals.add(name)
        else:
            state_type = StateType.NORMAL
        
        self._states[name] = State(
            name=name,
            state_type=state_type,
            on_enter=on_enter,
            on_exit=on_exit,
        )
        return self
    
    def initial(self, name: str) -> "WorkflowBuilder":
        """Set initial state."""
        return self.add_state(name, initial=True)
    
    def final(self, name: str) -> "WorkflowBuilder":
        """Add final state."""
        return self.add_state(name, final=True)
    
    def add_transition(
        self,
        source: str,
        target: str,
        on: Optional[str] = None,
        event: Optional[str] = None,
        guard: Optional[Callable[..., bool]] = None,
        action: Optional[Callable] = None,
    ) -> "WorkflowBuilder":
        event_name = on or event or f"{source}_to_{target}"
        
        self._transitions.append(Transition(
            source=source,
            target=target,
            event=event_name,
            guard=guard,
            action=action,
        ))
        return self
    
    def on(
        self,
        event: str,
        source: str,
        target: str,
        guard: Optional[Callable[..., bool]] = None,
        action: Optional[Callable] = None,
    ) -> "WorkflowBuilder":
        """Add transition on event."""
        return self.add_transition(source, target, event=event, guard=guard, action=action)
    
    def build(self) -> Workflow:
        """Build the workflow."""
        # Create state machine
        machine = StateMachine(self._name)
        
        # Add states
        for state in self._states.values():
            machine.add_state(
                state.name,
                state.state_type,
                state.on_enter,
                state.on_exit,
            )
        
        # Add transitions
        for trans in self._transitions:
            machine.add_transition(
                trans.source,
                trans.target,
                trans.event,
                trans.guard,
                trans.action,
            )
        
        config = WorkflowConfig(
            name=self._name,
            version=self._version,
            description=self._description,
        )
        
        return Workflow(config, machine)


class WorkflowEngine:
    """
    Workflow engine for managing multiple workflows.
    """
    
    def __init__(self):
        self._workflows: Dict[str, Workflow] = {}
        self._instances: Dict[str, Tuple[str, WorkflowInstance]] = {}
    
    def register(self, workflow: Workflow) -> None:
        """Register a workflow."""
        key = f"{workflow.name}:{workflow.version}"
        self._workflows[key] = workflow
    
    def get_workflow(
        self,
        name: str,
        version: Optional[str] = None,
    ) -> Optional[Workflow]:
        """Get workflow by name and version."""
        if version:
            return self._workflows.get(f"{name}:{version}")
        
        # Get latest version
        matching = [
            (k, w) for k, w in self._workflows.items()
            if k.startswith(f"{name}:")
        ]
        
        if matching:
            # Sort by version and get latest
            matching.sort(key=lambda x: x[1].version, reverse=True)
            return matching[0][1]
        
        return None
    
    async def start_workflow(
        self,
        name: str,
        data: Optional[Dict[str, Any]] = None,
        version: Optional[str] = None,
    ) -> WorkflowInstance:
        """Start a workflow."""
        workflow = self.get_workflow(name, version)
        if not workflow:
            raise WorkflowError(f"Workflow not found: {name}")
        
        instance = await workflow.start(data)
        self._instances[instance.id] = (name, instance)
        
        return instance
    
    def get_instance(self, instance_id: str) -> Optional[WorkflowInstance]:
        """Get workflow instance."""
        if instance_id in self._instances:
            return self._instances[instance_id][1]
        return None
    
    def list_workflows(self) -> List[Workflow]:
        """List all registered workflows."""
        return list(self._workflows.values())


class WorkflowRegistry:
    """Registry for workflow engines."""
    
    def __init__(self):
        self._engines: Dict[str, WorkflowEngine] = {}
        self._default: Optional[str] = None
    
    def register(
        self,
        name: str,
        engine: WorkflowEngine,
        default: bool = False,
    ) -> None:
        self._engines[name] = engine
        if default or self._default is None:
            self._default = name
    
    def get(self, name: Optional[str] = None) -> WorkflowEngine:
        name = name or self._default
        if not name or name not in self._engines:
            raise WorkflowError(f"Engine not found: {name}")
        return self._engines[name]


# Global registry
_global_registry = WorkflowRegistry()


# Decorators
def workflow(name: str, version: str = "1.0") -> Callable:
    """
    Decorator to define workflow from class.
    
    Example:
        @workflow("order-process")
        class OrderWorkflow:
            initial = "pending"
            
            @on_enter("pending")
            async def enter_pending(self, ctx):
                ...
    """
    def decorator(cls):
        builder = WorkflowBuilder(name).version(version)
        
        # Extract states and transitions from class
        if hasattr(cls, 'initial'):
            builder.initial(cls.initial)
        
        if hasattr(cls, 'states'):
            for state_name in cls.states:
                builder.add_state(state_name)
        
        if hasattr(cls, 'finals'):
            for state_name in cls.finals:
                builder.final(state_name)
        
        if hasattr(cls, 'transitions'):
            for trans in cls.transitions:
                builder.add_transition(**trans)
        
        cls._workflow = builder.build()
        return cls
    
    return decorator


def on_enter(state: str) -> Callable:
    """Decorator to mark state enter handler."""
    def decorator(func: Callable) -> Callable:
        func._on_enter_state = state
        return func
    return decorator


def on_exit(state: str) -> Callable:
    """Decorator to mark state exit handler."""
    def decorator(func: Callable) -> Callable:
        func._on_exit_state = state
        return func
    return decorator


# Factory functions
def create_workflow(name: str) -> WorkflowBuilder:
    """Create a workflow builder."""
    return WorkflowBuilder(name)


def create_workflow_engine() -> WorkflowEngine:
    """Create a workflow engine."""
    return WorkflowEngine()


def create_state_machine(name: str) -> StateMachine:
    """Create a state machine."""
    return StateMachine(name)


def register_engine(
    name: str,
    engine: WorkflowEngine,
    default: bool = False,
) -> None:
    """Register engine in global registry."""
    _global_registry.register(name, engine, default)


def get_engine(name: Optional[str] = None) -> WorkflowEngine:
    """Get engine from global registry."""
    try:
        return _global_registry.get(name)
    except WorkflowError:
        engine = create_workflow_engine()
        register_engine("default", engine, default=True)
        return engine


__all__ = [
    # Exceptions
    "WorkflowError",
    "InvalidTransitionError",
    "WorkflowAbortedError",
    "StateNotFoundError",
    # Enums
    "WorkflowState",
    "StateType",
    # Data classes
    "State",
    "Transition",
    "WorkflowConfig",
    "WorkflowContext",
    "WorkflowStats",
    # State Machine
    "StateMachine",
    # Workflow
    "WorkflowInstance",
    "Workflow",
    "WorkflowBuilder",
    "WorkflowEngine",
    # Registry
    "WorkflowRegistry",
    # Decorators
    "workflow",
    "on_enter",
    "on_exit",
    # Factory functions
    "create_workflow",
    "create_workflow_engine",
    "create_state_machine",
    "register_engine",
    "get_engine",
]
