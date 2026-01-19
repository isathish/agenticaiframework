"""
Workflow Memory Management.

Provides memory management for workflow execution:
- Step results and outputs
- Context passing between steps
- Workflow checkpoints
- Execution history
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from .manager import MemoryManager

logger = logging.getLogger(__name__)


class StepResultType(Enum):
    """Type of step result."""
    OUTPUT = "output"
    ERROR = "error"
    SKIP = "skip"
    PENDING = "pending"


@dataclass
class StepResult:
    """Result from a workflow step."""
    step_id: str
    step_name: str
    result_type: StepResultType
    output: Any = None
    error: Optional[str] = None
    duration_ms: int = 0
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "step_name": self.step_name,
            "result_type": self.result_type.value,
            "output": self.output,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StepResult":
        return cls(
            step_id=data["step_id"],
            step_name=data["step_name"],
            result_type=StepResultType(data["result_type"]),
            output=data.get("output"),
            error=data.get("error"),
            duration_ms=data.get("duration_ms", 0),
            started_at=data.get("started_at", datetime.now().isoformat()),
            completed_at=data.get("completed_at"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class WorkflowContext:
    """Shared context passed between workflow steps."""
    workflow_id: str
    variables: Dict[str, Any] = field(default_factory=dict)
    step_outputs: Dict[str, Any] = field(default_factory=dict)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "variables": self.variables,
            "step_outputs": self.step_outputs,
            "errors": self.errors,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowContext":
        return cls(
            workflow_id=data["workflow_id"],
            variables=data.get("variables", {}),
            step_outputs=data.get("step_outputs", {}),
            errors=data.get("errors", []),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
        )


@dataclass
class WorkflowMemoryCheckpoint:
    """Checkpoint of workflow memory state."""
    checkpoint_id: str
    workflow_id: str
    current_step: int
    context: WorkflowContext
    step_results: List[StepResult]
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "workflow_id": self.workflow_id,
            "current_step": self.current_step,
            "context": self.context.to_dict(),
            "step_results": [r.to_dict() for r in self.step_results],
            "created_at": self.created_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowMemoryCheckpoint":
        return cls(
            checkpoint_id=data["checkpoint_id"],
            workflow_id=data["workflow_id"],
            current_step=data["current_step"],
            context=WorkflowContext.from_dict(data["context"]),
            step_results=[StepResult.from_dict(r) for r in data.get("step_results", [])],
            created_at=data.get("created_at", datetime.now().isoformat()),
        )


@dataclass
class WorkflowExecutionRecord:
    """Record of a complete workflow execution."""
    execution_id: str
    workflow_id: str
    workflow_name: str
    status: str  # completed, failed, cancelled
    total_steps: int
    completed_steps: int
    started_at: str
    completed_at: str
    total_duration_ms: int
    final_output: Any = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "workflow_id": self.workflow_id,
            "workflow_name": self.workflow_name,
            "status": self.status,
            "total_steps": self.total_steps,
            "completed_steps": self.completed_steps,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "total_duration_ms": self.total_duration_ms,
            "final_output": self.final_output,
            "error": self.error,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowExecutionRecord":
        return cls(
            execution_id=data["execution_id"],
            workflow_id=data["workflow_id"],
            workflow_name=data["workflow_name"],
            status=data["status"],
            total_steps=data["total_steps"],
            completed_steps=data["completed_steps"],
            started_at=data["started_at"],
            completed_at=data["completed_at"],
            total_duration_ms=data["total_duration_ms"],
            final_output=data.get("final_output"),
            error=data.get("error"),
        )


class WorkflowMemoryManager:
    """
    Manages memory for workflow execution.
    
    Example:
        >>> wf_memory = WorkflowMemoryManager()
        >>> 
        >>> # Create workflow context
        >>> ctx = wf_memory.create_context("wf-123")
        >>> 
        >>> # Set variables
        >>> wf_memory.set_variable("wf-123", "input", "data")
        >>> 
        >>> # Record step result
        >>> wf_memory.record_step_result("wf-123", "step-1", "process", output=result)
        >>> 
        >>> # Create checkpoint
        >>> wf_memory.checkpoint("wf-123", current_step=3)
        >>> 
        >>> # Pass output to next step
        >>> prev_output = wf_memory.get_step_output("wf-123", "step-1")
    """
    
    def __init__(
        self,
        memory_manager: MemoryManager = None,
        max_checkpoints_per_workflow: int = 10,
        max_execution_history: int = 100,
    ):
        self.memory = memory_manager or MemoryManager()
        self.max_checkpoints = max_checkpoints_per_workflow
        self.max_history = max_execution_history
        
        # In-memory caches
        self._contexts: Dict[str, WorkflowContext] = {}
        self._step_results: Dict[str, List[StepResult]] = {}  # workflow_id -> results
        self._checkpoints: Dict[str, List[WorkflowMemoryCheckpoint]] = {}
        self._history: List[WorkflowExecutionRecord] = []
    
    def _key(self, workflow_id: str, suffix: str) -> str:
        """Generate memory key."""
        return f"workflow:{workflow_id}:{suffix}"
    
    # =========================================================================
    # Context Management
    # =========================================================================
    
    def create_context(
        self,
        workflow_id: str,
        initial_variables: Dict[str, Any] = None,
    ) -> WorkflowContext:
        """Create a new workflow context."""
        ctx = WorkflowContext(
            workflow_id=workflow_id,
            variables=initial_variables or {},
        )
        
        self._contexts[workflow_id] = ctx
        self._step_results[workflow_id] = []
        self._checkpoints[workflow_id] = []
        
        self.memory.store_short_term(
            self._key(workflow_id, "context"),
            ctx.to_dict(),
            ttl=3600,
            priority=6,
        )
        
        return ctx
    
    def get_context(self, workflow_id: str) -> Optional[WorkflowContext]:
        """Get workflow context."""
        if workflow_id in self._contexts:
            return self._contexts[workflow_id]
        
        data = self.memory.retrieve(self._key(workflow_id, "context"))
        if data:
            ctx = WorkflowContext.from_dict(data)
            self._contexts[workflow_id] = ctx
            return ctx
        
        return None
    
    def set_variable(
        self,
        workflow_id: str,
        key: str,
        value: Any,
    ) -> bool:
        """Set a workflow variable."""
        ctx = self.get_context(workflow_id)
        if not ctx:
            return False
        
        ctx.variables[key] = value
        ctx.updated_at = datetime.now().isoformat()
        
        self.memory.store_short_term(
            self._key(workflow_id, "context"),
            ctx.to_dict(),
            ttl=3600,
            priority=6,
        )
        
        return True
    
    def get_variable(
        self,
        workflow_id: str,
        key: str,
        default: Any = None,
    ) -> Any:
        """Get a workflow variable."""
        ctx = self.get_context(workflow_id)
        if not ctx:
            return default
        return ctx.variables.get(key, default)
    
    def get_all_variables(self, workflow_id: str) -> Dict[str, Any]:
        """Get all workflow variables."""
        ctx = self.get_context(workflow_id)
        if not ctx:
            return {}
        return ctx.variables.copy()
    
    # =========================================================================
    # Step Results
    # =========================================================================
    
    def record_step_result(
        self,
        workflow_id: str,
        step_id: str,
        step_name: str,
        output: Any = None,
        error: str = None,
        duration_ms: int = 0,
        metadata: Dict = None,
    ) -> StepResult:
        """Record a step result."""
        result_type = StepResultType.OUTPUT if output is not None else (
            StepResultType.ERROR if error else StepResultType.PENDING
        )
        
        result = StepResult(
            step_id=step_id,
            step_name=step_name,
            result_type=result_type,
            output=output,
            error=error,
            duration_ms=duration_ms,
            completed_at=datetime.now().isoformat() if output or error else None,
            metadata=metadata or {},
        )
        
        if workflow_id not in self._step_results:
            self._step_results[workflow_id] = []
        
        self._step_results[workflow_id].append(result)
        
        # Also update context
        ctx = self.get_context(workflow_id)
        if ctx and output is not None:
            ctx.step_outputs[step_id] = output
            if error:
                ctx.errors.append({"step_id": step_id, "error": error})
            ctx.updated_at = datetime.now().isoformat()
            self.memory.store_short_term(
                self._key(workflow_id, "context"),
                ctx.to_dict(),
                ttl=3600,
            )
        
        # Persist results
        self.memory.store_short_term(
            self._key(workflow_id, "results"),
            [r.to_dict() for r in self._step_results[workflow_id]],
            ttl=3600,
        )
        
        return result
    
    def get_step_output(
        self,
        workflow_id: str,
        step_id: str,
    ) -> Optional[Any]:
        """Get output from a specific step."""
        ctx = self.get_context(workflow_id)
        if ctx:
            return ctx.step_outputs.get(step_id)
        return None
    
    def get_all_step_results(self, workflow_id: str) -> List[StepResult]:
        """Get all step results for a workflow."""
        if workflow_id in self._step_results:
            return self._step_results[workflow_id]
        
        data = self.memory.retrieve(self._key(workflow_id, "results"), [])
        results = [StepResult.from_dict(r) for r in data]
        self._step_results[workflow_id] = results
        return results
    
    def get_last_step_result(self, workflow_id: str) -> Optional[StepResult]:
        """Get the last step result."""
        results = self.get_all_step_results(workflow_id)
        return results[-1] if results else None
    
    # =========================================================================
    # Context Passing (Step Chaining)
    # =========================================================================
    
    def pass_output_to_next(
        self,
        workflow_id: str,
        from_step: str,
        to_step: str,
        transform: callable = None,
    ) -> Any:
        """
        Pass output from one step to another.
        
        Args:
            workflow_id: Workflow ID
            from_step: Source step ID
            to_step: Target step ID
            transform: Optional transform function
            
        Returns:
            The passed value
        """
        output = self.get_step_output(workflow_id, from_step)
        
        if transform and output is not None:
            output = transform(output)
        
        # Store as input for next step
        self.set_variable(workflow_id, f"_input_{to_step}", output)
        
        return output
    
    def get_step_input(self, workflow_id: str, step_id: str) -> Optional[Any]:
        """Get prepared input for a step."""
        return self.get_variable(workflow_id, f"_input_{step_id}")
    
    def aggregate_outputs(
        self,
        workflow_id: str,
        step_ids: List[str],
        aggregator: callable = None,
    ) -> Any:
        """Aggregate outputs from multiple steps."""
        ctx = self.get_context(workflow_id)
        if not ctx:
            return None
        
        outputs = [ctx.step_outputs.get(sid) for sid in step_ids]
        outputs = [o for o in outputs if o is not None]
        
        if aggregator:
            return aggregator(outputs)
        
        return outputs
    
    # =========================================================================
    # Checkpoints
    # =========================================================================
    
    def checkpoint(
        self,
        workflow_id: str,
        current_step: int,
    ) -> WorkflowMemoryCheckpoint:
        """Create a memory checkpoint."""
        import uuid
        
        ctx = self.get_context(workflow_id)
        results = self.get_all_step_results(workflow_id)
        
        checkpoint = WorkflowMemoryCheckpoint(
            checkpoint_id=f"chk-{uuid.uuid4().hex[:8]}",
            workflow_id=workflow_id,
            current_step=current_step,
            context=ctx or WorkflowContext(workflow_id=workflow_id),
            step_results=results,
        )
        
        if workflow_id not in self._checkpoints:
            self._checkpoints[workflow_id] = []
        
        self._checkpoints[workflow_id].append(checkpoint)
        
        # Limit checkpoints
        while len(self._checkpoints[workflow_id]) > self.max_checkpoints:
            self._checkpoints[workflow_id].pop(0)
        
        # Persist
        self.memory.store_long_term(
            self._key(workflow_id, "checkpoints"),
            [c.to_dict() for c in self._checkpoints[workflow_id]],
            priority=7,
        )
        
        return checkpoint
    
    def get_latest_checkpoint(
        self,
        workflow_id: str,
    ) -> Optional[WorkflowMemoryCheckpoint]:
        """Get the latest checkpoint."""
        if workflow_id in self._checkpoints and self._checkpoints[workflow_id]:
            return self._checkpoints[workflow_id][-1]
        
        data = self.memory.retrieve(self._key(workflow_id, "checkpoints"), [])
        if data:
            checkpoints = [WorkflowMemoryCheckpoint.from_dict(c) for c in data]
            self._checkpoints[workflow_id] = checkpoints
            return checkpoints[-1] if checkpoints else None
        
        return None
    
    def restore_from_checkpoint(
        self,
        workflow_id: str,
        checkpoint_id: str = None,
    ) -> Optional[WorkflowMemoryCheckpoint]:
        """Restore workflow memory from checkpoint."""
        checkpoints = self._checkpoints.get(workflow_id, [])
        if not checkpoints:
            data = self.memory.retrieve(self._key(workflow_id, "checkpoints"), [])
            checkpoints = [WorkflowMemoryCheckpoint.from_dict(c) for c in data]
        
        if checkpoint_id:
            checkpoint = next((c for c in checkpoints if c.checkpoint_id == checkpoint_id), None)
        else:
            checkpoint = checkpoints[-1] if checkpoints else None
        
        if checkpoint:
            self._contexts[workflow_id] = checkpoint.context
            self._step_results[workflow_id] = checkpoint.step_results
            
            # Re-persist
            self.memory.store_short_term(
                self._key(workflow_id, "context"),
                checkpoint.context.to_dict(),
                ttl=3600,
            )
            self.memory.store_short_term(
                self._key(workflow_id, "results"),
                [r.to_dict() for r in checkpoint.step_results],
                ttl=3600,
            )
        
        return checkpoint
    
    # =========================================================================
    # Execution History
    # =========================================================================
    
    def record_execution(
        self,
        workflow_id: str,
        workflow_name: str,
        status: str,
        total_steps: int,
        completed_steps: int,
        started_at: str,
        total_duration_ms: int,
        final_output: Any = None,
        error: str = None,
    ) -> WorkflowExecutionRecord:
        """Record a workflow execution."""
        import uuid
        
        record = WorkflowExecutionRecord(
            execution_id=f"exec-{uuid.uuid4().hex[:8]}",
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            status=status,
            total_steps=total_steps,
            completed_steps=completed_steps,
            started_at=started_at,
            completed_at=datetime.now().isoformat(),
            total_duration_ms=total_duration_ms,
            final_output=final_output,
            error=error,
        )
        
        self._history.append(record)
        
        # Limit history
        while len(self._history) > self.max_history:
            self._history.pop(0)
        
        # Persist
        self.memory.store_long_term(
            "workflow:execution_history",
            [r.to_dict() for r in self._history],
            priority=6,
        )
        
        return record
    
    def get_execution_history(
        self,
        workflow_id: str = None,
        status: str = None,
        last_n: int = None,
    ) -> List[WorkflowExecutionRecord]:
        """Get execution history."""
        if not self._history:
            data = self.memory.retrieve("workflow:execution_history", [])
            self._history = [WorkflowExecutionRecord.from_dict(r) for r in data]
        
        history = self._history
        
        if workflow_id:
            history = [r for r in history if r.workflow_id == workflow_id]
        
        if status:
            history = [r for r in history if r.status == status]
        
        if last_n:
            history = history[-last_n:]
        
        return history
    
    # =========================================================================
    # Cleanup
    # =========================================================================
    
    def cleanup_workflow(self, workflow_id: str):
        """Clean up memory for a completed workflow."""
        self._contexts.pop(workflow_id, None)
        self._step_results.pop(workflow_id, None)
        self._checkpoints.pop(workflow_id, None)
        
        # Remove from persistent storage
        self.memory.retrieve(self._key(workflow_id, "context"))
        self.memory.retrieve(self._key(workflow_id, "results"))
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        return {
            "active_workflows": len(self._contexts),
            "total_checkpoints": sum(len(c) for c in self._checkpoints.values()),
            "execution_history_size": len(self._history),
        }


__all__ = [
    "StepResultType",
    "StepResult",
    "WorkflowContext",
    "WorkflowMemoryCheckpoint",
    "WorkflowExecutionRecord",
    "WorkflowMemoryManager",
]
