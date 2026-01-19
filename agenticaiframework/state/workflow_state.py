"""
Workflow State Management.

Provides state tracking, pause/resume, and checkpointing for workflows.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable

from .manager import StateManager, StateType

logger = logging.getLogger(__name__)


class WorkflowStatus(Enum):
    """Workflow execution status."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    WAITING = "waiting"  # Waiting for input/approval


@dataclass
class StepState:
    """State of a single workflow step."""
    step_id: str
    step_index: int
    name: str
    status: WorkflowStatus
    input_data: Any = None
    output_data: Any = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_ms: int = 0
    retries: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "step_index": self.step_index,
            "name": self.name,
            "status": self.status.value,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_ms": self.duration_ms,
            "retries": self.retries,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StepState":
        return cls(
            step_id=data["step_id"],
            step_index=data["step_index"],
            name=data["name"],
            status=WorkflowStatus(data["status"]),
            input_data=data.get("input_data"),
            output_data=data.get("output_data"),
            error=data.get("error"),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            duration_ms=data.get("duration_ms", 0),
            retries=data.get("retries", 0),
            metadata=data.get("metadata", {}),
        )


@dataclass
class WorkflowState:
    """Complete workflow state."""
    workflow_id: str
    name: str
    status: WorkflowStatus
    current_step: int
    total_steps: int
    steps: List[StepState]
    input_data: Any = None
    output_data: Any = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    paused_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "name": self.name,
            "status": self.status.value,
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "steps": [s.to_dict() for s in self.steps],
            "input_data": self.input_data,
            "output_data": self.output_data,
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "paused_at": self.paused_at,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowState":
        return cls(
            workflow_id=data["workflow_id"],
            name=data["name"],
            status=WorkflowStatus(data["status"]),
            current_step=data["current_step"],
            total_steps=data["total_steps"],
            steps=[StepState.from_dict(s) for s in data.get("steps", [])],
            input_data=data.get("input_data"),
            output_data=data.get("output_data"),
            error=data.get("error"),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            paused_at=data.get("paused_at"),
            metadata=data.get("metadata", {}),
        )
    
    @property
    def progress(self) -> float:
        """Get workflow progress as percentage."""
        if self.total_steps == 0:
            return 0.0
        completed = sum(1 for s in self.steps if s.status == WorkflowStatus.COMPLETED)
        return (completed / self.total_steps) * 100


@dataclass
class WorkflowCheckpoint:
    """Checkpoint for workflow resumption."""
    workflow_id: str
    checkpoint_id: str
    step_index: int
    state_snapshot: Dict[str, Any]
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "checkpoint_id": self.checkpoint_id,
            "step_index": self.step_index,
            "state_snapshot": self.state_snapshot,
            "created_at": self.created_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowCheckpoint":
        return cls(
            workflow_id=data["workflow_id"],
            checkpoint_id=data["checkpoint_id"],
            step_index=data["step_index"],
            state_snapshot=data["state_snapshot"],
            created_at=data.get("created_at", datetime.now().isoformat()),
        )


class WorkflowStateManager:
    """
    Manages workflow state with persistence and recovery.
    
    Example:
        >>> manager = WorkflowStateManager()
        >>> 
        >>> # Create workflow
        >>> state = manager.create_workflow("my-workflow", steps=["step1", "step2"])
        >>> 
        >>> # Update step
        >>> manager.start_step(state.workflow_id, 0)
        >>> manager.complete_step(state.workflow_id, 0, result=data)
        >>> 
        >>> # Pause/Resume
        >>> manager.pause(state.workflow_id)
        >>> manager.resume(state.workflow_id)
        >>> 
        >>> # Checkpoint for recovery
        >>> manager.checkpoint(state.workflow_id)
    """
    
    def __init__(
        self,
        state_manager: StateManager = None,
        auto_checkpoint: bool = True,
        checkpoint_on_step: bool = True,
    ):
        self.state_manager = state_manager or StateManager()
        self.auto_checkpoint = auto_checkpoint
        self.checkpoint_on_step = checkpoint_on_step
        
        self._on_step_complete: List[Callable] = []
        self._on_workflow_complete: List[Callable] = []
        self._on_error: List[Callable] = []
    
    def create_workflow(
        self,
        name: str,
        steps: List[str],
        input_data: Any = None,
        metadata: Dict = None,
    ) -> WorkflowState:
        """Create a new workflow."""
        import uuid
        workflow_id = f"wf-{uuid.uuid4().hex[:8]}"
        
        step_states = [
            StepState(
                step_id=f"{workflow_id}-step{i}",
                step_index=i,
                name=step_name,
                status=WorkflowStatus.PENDING,
            )
            for i, step_name in enumerate(steps)
        ]
        
        state = WorkflowState(
            workflow_id=workflow_id,
            name=name,
            status=WorkflowStatus.PENDING,
            current_step=0,
            total_steps=len(steps),
            steps=step_states,
            input_data=input_data,
            metadata=metadata or {},
        )
        
        self._save_state(state)
        return state
    
    def _save_state(self, state: WorkflowState) -> bool:
        """Save workflow state."""
        return self.state_manager.save(
            f"workflow:{state.workflow_id}",
            state.to_dict(),
            StateType.WORKFLOW,
        )
    
    def get_state(self, workflow_id: str) -> Optional[WorkflowState]:
        """Get workflow state."""
        data = self.state_manager.get(f"workflow:{workflow_id}")
        if data:
            return WorkflowState.from_dict(data)
        return None
    
    def start_workflow(self, workflow_id: str) -> Optional[WorkflowState]:
        """Start workflow execution."""
        state = self.get_state(workflow_id)
        if not state:
            return None
        
        state.status = WorkflowStatus.RUNNING
        state.started_at = datetime.now().isoformat()
        self._save_state(state)
        return state
    
    def start_step(
        self,
        workflow_id: str,
        step_index: int,
        input_data: Any = None,
    ) -> Optional[StepState]:
        """Start a workflow step."""
        state = self.get_state(workflow_id)
        if not state or step_index >= len(state.steps):
            return None
        
        step = state.steps[step_index]
        step.status = WorkflowStatus.RUNNING
        step.started_at = datetime.now().isoformat()
        step.input_data = input_data
        
        state.current_step = step_index
        state.status = WorkflowStatus.RUNNING
        
        self._save_state(state)
        return step
    
    def complete_step(
        self,
        workflow_id: str,
        step_index: int,
        output_data: Any = None,
        metadata: Dict = None,
    ) -> Optional[StepState]:
        """Complete a workflow step."""
        state = self.get_state(workflow_id)
        if not state or step_index >= len(state.steps):
            return None
        
        step = state.steps[step_index]
        step.status = WorkflowStatus.COMPLETED
        step.completed_at = datetime.now().isoformat()
        step.output_data = output_data
        
        if step.started_at:
            started = datetime.fromisoformat(step.started_at)
            completed = datetime.fromisoformat(step.completed_at)
            step.duration_ms = int((completed - started).total_seconds() * 1000)
        
        if metadata:
            step.metadata.update(metadata)
        
        # Check if workflow is complete
        all_complete = all(s.status == WorkflowStatus.COMPLETED for s in state.steps)
        if all_complete:
            state.status = WorkflowStatus.COMPLETED
            state.completed_at = datetime.now().isoformat()
            state.output_data = output_data
            
            for callback in self._on_workflow_complete:
                try:
                    callback(state)
                except Exception as e:
                    logger.error(f"Workflow complete callback error: {e}")
        else:
            state.current_step = step_index + 1
        
        self._save_state(state)
        
        # Checkpoint on step completion
        if self.checkpoint_on_step:
            self.checkpoint(workflow_id)
        
        # Notify callbacks
        for callback in self._on_step_complete:
            try:
                callback(state, step)
            except Exception as e:
                logger.error(f"Step complete callback error: {e}")
        
        return step
    
    def fail_step(
        self,
        workflow_id: str,
        step_index: int,
        error: str,
    ) -> Optional[StepState]:
        """Mark a step as failed."""
        state = self.get_state(workflow_id)
        if not state or step_index >= len(state.steps):
            return None
        
        step = state.steps[step_index]
        step.status = WorkflowStatus.FAILED
        step.error = error
        step.completed_at = datetime.now().isoformat()
        step.retries += 1
        
        state.status = WorkflowStatus.FAILED
        state.error = f"Step {step_index} ({step.name}) failed: {error}"
        
        self._save_state(state)
        
        # Checkpoint on failure
        self.checkpoint(workflow_id)
        
        # Notify callbacks
        for callback in self._on_error:
            try:
                callback(state, step, error)
            except Exception as e:
                logger.error(f"Error callback error: {e}")
        
        return step
    
    def retry_step(
        self,
        workflow_id: str,
        step_index: int,
        max_retries: int = 3,
    ) -> bool:
        """Retry a failed step."""
        state = self.get_state(workflow_id)
        if not state or step_index >= len(state.steps):
            return False
        
        step = state.steps[step_index]
        if step.retries >= max_retries:
            return False
        
        step.status = WorkflowStatus.PENDING
        step.error = None
        state.status = WorkflowStatus.RUNNING
        
        self._save_state(state)
        return True
    
    def pause(self, workflow_id: str) -> Optional[WorkflowState]:
        """Pause workflow execution."""
        state = self.get_state(workflow_id)
        if not state:
            return None
        
        state.status = WorkflowStatus.PAUSED
        state.paused_at = datetime.now().isoformat()
        
        # Checkpoint before pause
        self.checkpoint(workflow_id)
        
        self._save_state(state)
        return state
    
    def resume(self, workflow_id: str) -> Optional[WorkflowState]:
        """Resume paused workflow."""
        state = self.get_state(workflow_id)
        if not state or state.status != WorkflowStatus.PAUSED:
            return None
        
        state.status = WorkflowStatus.RUNNING
        state.paused_at = None
        
        self._save_state(state)
        return state
    
    def cancel(self, workflow_id: str) -> Optional[WorkflowState]:
        """Cancel workflow execution."""
        state = self.get_state(workflow_id)
        if not state:
            return None
        
        state.status = WorkflowStatus.CANCELLED
        state.completed_at = datetime.now().isoformat()
        
        self._save_state(state)
        return state
    
    def checkpoint(self, workflow_id: str) -> Optional[WorkflowCheckpoint]:
        """Create a checkpoint for workflow recovery."""
        state = self.get_state(workflow_id)
        if not state:
            return None
        
        checkpoint = WorkflowCheckpoint(
            workflow_id=workflow_id,
            checkpoint_id=f"cp-{workflow_id}-{state.current_step}",
            step_index=state.current_step,
            state_snapshot=state.to_dict(),
        )
        
        self.state_manager.save(
            f"checkpoint:workflow:{workflow_id}:step{state.current_step}",
            checkpoint.to_dict(),
            StateType.WORKFLOW,
        )
        
        return checkpoint
    
    def recover(
        self,
        workflow_id: str,
        from_step: int = None,
    ) -> Optional[WorkflowState]:
        """Recover workflow from checkpoint."""
        # Find checkpoint
        if from_step is not None:
            key = f"checkpoint:workflow:{workflow_id}:step{from_step}"
        else:
            # Get latest checkpoint
            checkpoints = self.state_manager.list(f"checkpoint:workflow:{workflow_id}")
            if not checkpoints:
                return self.get_state(workflow_id)
            key = sorted(checkpoints)[-1]
        
        data = self.state_manager.get(key)
        if not data:
            return None
        
        checkpoint = WorkflowCheckpoint.from_dict(data)
        state = WorkflowState.from_dict(checkpoint.state_snapshot)
        
        # Reset failed steps from checkpoint point
        for i in range(checkpoint.step_index, len(state.steps)):
            if state.steps[i].status == WorkflowStatus.FAILED:
                state.steps[i].status = WorkflowStatus.PENDING
                state.steps[i].error = None
        
        state.status = WorkflowStatus.RUNNING
        state.error = None
        state.metadata["recovered_from"] = checkpoint.checkpoint_id
        state.metadata["recovered_at"] = datetime.now().isoformat()
        
        self._save_state(state)
        return state
    
    def list_checkpoints(self, workflow_id: str) -> List[WorkflowCheckpoint]:
        """List all checkpoints for a workflow."""
        keys = self.state_manager.list(f"checkpoint:workflow:{workflow_id}")
        checkpoints = []
        for key in keys:
            data = self.state_manager.get(key)
            if data:
                checkpoints.append(WorkflowCheckpoint.from_dict(data))
        return sorted(checkpoints, key=lambda x: x.step_index)
    
    def get_progress(self, workflow_id: str) -> Dict[str, Any]:
        """Get workflow progress summary."""
        state = self.get_state(workflow_id)
        if not state:
            return {"error": "Workflow not found"}
        
        completed = sum(1 for s in state.steps if s.status == WorkflowStatus.COMPLETED)
        failed = sum(1 for s in state.steps if s.status == WorkflowStatus.FAILED)
        
        return {
            "workflow_id": workflow_id,
            "name": state.name,
            "status": state.status.value,
            "progress": state.progress,
            "current_step": state.current_step,
            "total_steps": state.total_steps,
            "completed_steps": completed,
            "failed_steps": failed,
            "started_at": state.started_at,
            "completed_at": state.completed_at,
        }
    
    def list_workflows(
        self,
        status: WorkflowStatus = None,
    ) -> List[WorkflowState]:
        """List all workflows, optionally filtered by status."""
        keys = self.state_manager.list("workflow:")
        workflows = []
        
        for key in keys:
            if key.startswith("checkpoint:"):
                continue
            data = self.state_manager.get(key)
            if data:
                state = WorkflowState.from_dict(data)
                if status is None or state.status == status:
                    workflows.append(state)
        
        return workflows
    
    # Callbacks
    def on_step_complete(self, callback: Callable[[WorkflowState, StepState], None]) -> None:
        """Register step completion callback."""
        self._on_step_complete.append(callback)
    
    def on_workflow_complete(self, callback: Callable[[WorkflowState], None]) -> None:
        """Register workflow completion callback."""
        self._on_workflow_complete.append(callback)
    
    def on_error(self, callback: Callable[[WorkflowState, StepState, str], None]) -> None:
        """Register error callback."""
        self._on_error.append(callback)


__all__ = [
    "WorkflowStatus",
    "StepState",
    "WorkflowState",
    "WorkflowCheckpoint",
    "WorkflowStateManager",
]
