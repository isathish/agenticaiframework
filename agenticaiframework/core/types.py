"""
Agentic Execution Types.

Provides structured input/output types for agentic execution:
- AgentInput: Structured input for agent runs
- AgentStep: Represents a single step in agentic execution
- AgentOutput: Structured output from agent runs
- AgentThought: Reasoning step (for ReAct-style agents)
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class StepType(Enum):
    """Type of agent execution step."""
    INPUT = "input"
    THOUGHT = "thought"
    OBSERVATION = "observation"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    KNOWLEDGE = "knowledge"
    GUARDRAIL = "guardrail"
    LLM_CALL = "llm_call"
    OUTPUT = "output"
    ERROR = "error"


class AgentStatus(Enum):
    """Status of agent execution."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    BLOCKED = "blocked"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class AgentStep:
    """Represents a single step in the agentic execution."""
    step_type: StepType
    name: str
    content: Any
    timestamp: datetime = field(default_factory=datetime.now)
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'step_type': self.step_type.value,
            'name': self.name,
            'content': self.content,
            'timestamp': self.timestamp.isoformat(),
            'duration_ms': self.duration_ms,
            'metadata': self.metadata,
        }


@dataclass
class AgentThought:
    """Represents a reasoning/thought step (ReAct-style)."""
    thought: str
    action: Optional[str] = None
    action_input: Optional[Dict[str, Any]] = None
    observation: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'thought': self.thought,
            'action': self.action,
            'action_input': self.action_input,
            'observation': self.observation,
        }


@dataclass
class AgentInput:
    """Structured input for agent execution."""
    prompt: str
    system_prompt: Optional[str] = None
    tools: Optional[List[str]] = None
    tool_inputs: Optional[Dict[str, Dict[str, Any]]] = None
    knowledge_query: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    max_iterations: int = 10
    stop_sequences: Optional[List[str]] = None
    temperature: float = 0.7
    stream: bool = False
    stop_on_tool_error: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'prompt': self.prompt,
            'system_prompt': self.system_prompt,
            'tools': self.tools,
            'tool_inputs': self.tool_inputs,
            'knowledge_query': self.knowledge_query,
            'context': self.context,
            'max_iterations': self.max_iterations,
            'stop_sequences': self.stop_sequences,
            'temperature': self.temperature,
            'stream': self.stream,
            'stop_on_tool_error': self.stop_on_tool_error,
        }


@dataclass
class AgentOutput:
    """Structured output from agent execution."""
    status: AgentStatus
    response: Optional[str] = None
    steps: List[AgentStep] = field(default_factory=list)
    thoughts: List[AgentThought] = field(default_factory=list)
    tool_results: List[Dict[str, Any]] = field(default_factory=list)
    knowledge_results: List[Dict[str, Any]] = field(default_factory=list)
    guardrail_report: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    trace_id: Optional[str] = None
    latency_seconds: float = 0.0
    token_usage: Dict[str, int] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_success(self) -> bool:
        return self.status == AgentStatus.SUCCESS
    
    @property
    def is_error(self) -> bool:
        return self.status == AgentStatus.ERROR
    
    @property
    def is_blocked(self) -> bool:
        return self.status == AgentStatus.BLOCKED
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'status': self.status.value,
            'response': self.response,
            'steps': [s.to_dict() for s in self.steps],
            'thoughts': [t.to_dict() for t in self.thoughts],
            'tool_results': self.tool_results,
            'knowledge_results': self.knowledge_results,
            'guardrail_report': self.guardrail_report,
            'error': self.error,
            'trace_id': self.trace_id,
            'latency_seconds': self.latency_seconds,
            'token_usage': self.token_usage,
            'metadata': self.metadata,
        }
    
    def __str__(self) -> str:
        if self.is_success:
            return self.response or ""
        elif self.is_error:
            return f"Error: {self.error}"
        elif self.is_blocked:
            return f"Blocked: {self.guardrail_report}"
        return f"Status: {self.status.value}"
    
    def __repr__(self) -> str:
        return f"AgentOutput(status={self.status.value}, response={self.response[:50] if self.response else None}...)"


__all__ = [
    'StepType',
    'AgentStatus',
    'AgentStep',
    'AgentThought',
    'AgentInput',
    'AgentOutput',
]
