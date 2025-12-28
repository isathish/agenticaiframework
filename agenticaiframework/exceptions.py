"""
Custom exception classes for the AgenticAI Framework.

Provides a comprehensive exception hierarchy for:
- Circuit breaker errors
- Rate limiting errors
- Security/injection errors
- Validation errors
- Task execution errors
- Agent lifecycle errors
"""


class AgenticAIError(Exception):
    """Base exception for all AgenticAI Framework errors."""
    
    def __init__(self, message: str = None, details: dict = None):
        self.message = message or "An error occurred in AgenticAI Framework"
        self.details = details or {}
        super().__init__(self.message)


# Circuit Breaker Exceptions
class CircuitBreakerError(AgenticAIError):
    """Base exception for circuit breaker related errors."""


class CircuitBreakerOpenError(CircuitBreakerError):
    """Raised when circuit breaker is in OPEN state and rejecting requests."""
    
    def __init__(self, message: str = None, recovery_timeout: int = None):
        self.recovery_timeout = recovery_timeout
        super().__init__(
            message or "Circuit breaker is OPEN - requests are being rejected",
            details={'recovery_timeout': recovery_timeout}
        )


# Rate Limiting Exceptions
class RateLimitError(AgenticAIError):
    """Base exception for rate limiting errors."""


class RateLimitExceededError(RateLimitError):
    """Raised when rate limit has been exceeded."""
    
    def __init__(self, message: str = None, identifier: str = None, retry_after: int = None):
        self.identifier = identifier
        self.retry_after = retry_after
        super().__init__(
            message or f"Rate limit exceeded for '{identifier}'",
            details={'identifier': identifier, 'retry_after': retry_after}
        )


# Security Exceptions
class SecurityError(AgenticAIError):
    """Base exception for security related errors."""


class InjectionDetectedError(SecurityError):
    """Raised when prompt injection is detected."""
    
    def __init__(self, message: str = None, confidence: float = None, patterns: list = None):
        self.confidence = confidence
        self.patterns = patterns or []
        super().__init__(
            message or "Potential prompt injection detected",
            details={'confidence': confidence, 'patterns': patterns}
        )


class ContentFilteredError(SecurityError):
    """Raised when content is blocked by filters."""
    
    def __init__(self, message: str = None, reason: str = None):
        self.reason = reason
        super().__init__(
            message or "Content blocked by security filter",
            details={'reason': reason}
        )


# Validation Exceptions
class ValidationError(AgenticAIError):
    """Base exception for validation errors."""


class GuardrailViolationError(ValidationError):
    """Raised when a guardrail validation fails."""
    
    def __init__(self, message: str = None, guardrail_name: str = None, severity: str = None):
        self.guardrail_name = guardrail_name
        self.severity = severity
        super().__init__(
            message or f"Guardrail '{guardrail_name}' validation failed",
            details={'guardrail_name': guardrail_name, 'severity': severity}
        )


class PromptRenderError(ValidationError):
    """Raised when prompt rendering fails."""
    
    def __init__(self, message: str = None, missing_variable: str = None):
        self.missing_variable = missing_variable
        super().__init__(
            message or f"Failed to render prompt: missing variable '{missing_variable}'",
            details={'missing_variable': missing_variable}
        )


# Task Exceptions
class TaskError(AgenticAIError):
    """Base exception for task related errors."""


class TaskExecutionError(TaskError):
    """Raised when task execution fails."""
    
    def __init__(self, message: str = None, task_name: str = None, original_error: Exception = None):
        self.task_name = task_name
        self.original_error = original_error
        super().__init__(
            message or f"Task '{task_name}' execution failed",
            details={
                'task_name': task_name,
                'original_error': str(original_error) if original_error else None
            }
        )


class TaskNotFoundError(TaskError):
    """Raised when a task cannot be found."""
    
    def __init__(self, message: str = None, task_id: str = None):
        self.task_id = task_id
        super().__init__(
            message or f"Task '{task_id}' not found",
            details={'task_id': task_id}
        )


# Agent Exceptions
class AgentError(AgenticAIError):
    """Base exception for agent related errors."""


class AgentNotFoundError(AgentError):
    """Raised when an agent cannot be found."""
    
    def __init__(self, message: str = None, agent_id: str = None):
        self.agent_id = agent_id
        super().__init__(
            message or f"Agent '{agent_id}' not found",
            details={'agent_id': agent_id}
        )


class AgentExecutionError(AgentError):
    """Raised when agent task execution fails."""
    
    def __init__(self, message: str = None, agent_name: str = None, original_error: Exception = None):
        self.agent_name = agent_name
        self.original_error = original_error
        super().__init__(
            message or f"Agent '{agent_name}' execution failed",
            details={
                'agent_name': agent_name,
                'original_error': str(original_error) if original_error else None
            }
        )


# LLM Exceptions
class LLMError(AgenticAIError):
    """Base exception for LLM related errors."""


class ModelNotFoundError(LLMError):
    """Raised when a model cannot be found."""
    
    def __init__(self, message: str = None, model_name: str = None):
        self.model_name = model_name
        super().__init__(
            message or f"Model '{model_name}' not found",
            details={'model_name': model_name}
        )


class ModelInferenceError(LLMError):
    """Raised when model inference fails."""
    
    def __init__(self, message: str = None, model_name: str = None, original_error: Exception = None):
        self.model_name = model_name
        self.original_error = original_error
        super().__init__(
            message or f"Inference failed for model '{model_name}'",
            details={
                'model_name': model_name,
                'original_error': str(original_error) if original_error else None
            }
        )


# Memory Exceptions
class AgenticMemoryError(AgenticAIError):
    """Base exception for memory related errors."""


class MemoryExportError(AgenticMemoryError):
    """Raised when memory export fails."""
    
    def __init__(self, message: str = None, filepath: str = None, original_error: Exception = None):
        self.filepath = filepath
        self.original_error = original_error
        super().__init__(
            message or f"Failed to export memory to '{filepath}'",
            details={
                'filepath': filepath,
                'original_error': str(original_error) if original_error else None
            }
        )


# Knowledge Exceptions
class KnowledgeError(AgenticAIError):
    """Base exception for knowledge retrieval errors."""


class KnowledgeRetrievalError(KnowledgeError):
    """Raised when knowledge retrieval fails."""
    
    def __init__(self, message: str = None, source_name: str = None, original_error: Exception = None):
        self.source_name = source_name
        self.original_error = original_error
        super().__init__(
            message or f"Failed to retrieve knowledge from source '{source_name}'",
            details={
                'source_name': source_name,
                'original_error': str(original_error) if original_error else None
            }
        )


# Communication Exceptions
class CommunicationError(AgenticAIError):
    """Base exception for communication errors."""


class ProtocolError(CommunicationError):
    """Raised when communication protocol fails."""
    
    def __init__(self, message: str = None, protocol_name: str = None, original_error: Exception = None):
        self.protocol_name = protocol_name
        self.original_error = original_error
        super().__init__(
            message or f"Protocol '{protocol_name}' communication failed",
            details={
                'protocol_name': protocol_name,
                'original_error': str(original_error) if original_error else None
            }
        )


class ProtocolNotFoundError(CommunicationError):
    """Raised when a protocol is not found."""
    
    def __init__(self, message: str = None, protocol_name: str = None):
        self.protocol_name = protocol_name
        super().__init__(
            message or f"Protocol '{protocol_name}' not found",
            details={'protocol_name': protocol_name}
        )


# Evaluation Exceptions
class EvaluationError(AgenticAIError):
    """Base exception for evaluation errors."""


class CriterionEvaluationError(EvaluationError):
    """Raised when evaluation criterion fails."""
    
    def __init__(self, message: str = None, criterion_name: str = None, original_error: Exception = None):
        self.criterion_name = criterion_name
        self.original_error = original_error
        super().__init__(
            message or f"Evaluation criterion '{criterion_name}' failed",
            details={
                'criterion_name': criterion_name,
                'original_error': str(original_error) if original_error else None
            }
        )
