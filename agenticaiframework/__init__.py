"""
AgenticAI Python Package
Fully functional implementation of the Agentic Framework as described.
"""

from .agents import Agent, AgentManager, ContextManager
from .prompts import Prompt, PromptManager
from .processes import Process
from .tasks import Task, TaskManager
from .mcp_tools import MCPTool, MCPToolManager
from .monitoring import MonitoringSystem
from .guardrails import Guardrail, GuardrailManager
from .evaluation import EvaluationSystem
from .knowledge import KnowledgeRetriever
from .llms import LLMManager, CircuitBreaker
from .communication import CommunicationManager
from .memory import MemoryManager, MemoryEntry
from .hub import Hub
from .configurations import ConfigurationManager
from .security import (
    PromptInjectionDetector,
    InputValidator,
    RateLimiter,
    ContentFilter,
    AuditLogger,
    SecurityManager
)
from .exceptions import (
    # Base exception
    AgenticAIError,
    # Circuit breaker exceptions
    CircuitBreakerError,
    CircuitBreakerOpenError,
    # Rate limiting exceptions
    RateLimitError,
    RateLimitExceededError,
    # Security exceptions
    SecurityError,
    InjectionDetectedError,
    ContentFilteredError,
    # Validation exceptions
    ValidationError,
    GuardrailViolationError,
    PromptRenderError,
    # Task exceptions
    TaskError,
    TaskExecutionError,
    TaskNotFoundError,
    # Agent exceptions
    AgentError,
    AgentNotFoundError,
    AgentExecutionError,
    # LLM exceptions
    LLMError,
    ModelNotFoundError,
    ModelInferenceError,
    # Memory exceptions
    AgenticMemoryError,
    MemoryExportError,
    # Knowledge exceptions
    KnowledgeError,
    KnowledgeRetrievalError,
    # Communication exceptions
    CommunicationError,
    ProtocolError,
    ProtocolNotFoundError,
    # Evaluation exceptions
    EvaluationError,
    CriterionEvaluationError,
)

__all__ = [
    # Core components
    "Agent", "AgentManager", "ContextManager",
    "Prompt", "PromptManager",
    "Process",
    "Task", "TaskManager",
    "MCPTool", "MCPToolManager",
    "MonitoringSystem",
    "Guardrail", "GuardrailManager",
    "EvaluationSystem",
    "KnowledgeRetriever",
    "LLMManager", "CircuitBreaker",
    "CommunicationManager",
    "MemoryManager", "MemoryEntry",
    "Hub",
    "ConfigurationManager",
    # Security components
    "PromptInjectionDetector",
    "InputValidator",
    "RateLimiter",
    "ContentFilter",
    "AuditLogger",
    "SecurityManager",
    # Exceptions - Base
    "AgenticAIError",
    # Exceptions - Circuit breaker
    "CircuitBreakerError",
    "CircuitBreakerOpenError",
    # Exceptions - Rate limiting
    "RateLimitError",
    "RateLimitExceededError",
    # Exceptions - Security
    "SecurityError",
    "InjectionDetectedError",
    "ContentFilteredError",
    # Exceptions - Validation
    "ValidationError",
    "GuardrailViolationError",
    "PromptRenderError",
    # Exceptions - Task
    "TaskError",
    "TaskExecutionError",
    "TaskNotFoundError",
    # Exceptions - Agent
    "AgentError",
    "AgentNotFoundError",
    "AgentExecutionError",
    # Exceptions - LLM
    "LLMError",
    "ModelNotFoundError",
    "ModelInferenceError",
    # Exceptions - Memory
    "AgenticMemoryError",
    "MemoryExportError",
    # Exceptions - Knowledge
    "KnowledgeError",
    "KnowledgeRetrievalError",
    # Exceptions - Communication
    "CommunicationError",
    "ProtocolError",
    "ProtocolNotFoundError",
    # Exceptions - Evaluation
    "EvaluationError",
    "CriterionEvaluationError",
]
