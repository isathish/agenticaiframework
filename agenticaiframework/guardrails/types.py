"""
Guardrail types, enums, and data classes.

Provides:
- GuardrailType: Types of guardrails
- GuardrailSeverity: Severity levels
- GuardrailAction: Actions on violation
- GuardrailViolation: Violation details
- GuardrailRule: Rule definition
"""

from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class GuardrailType(Enum):
    """Types of guardrails for different validation scenarios."""
    INPUT = "input"
    OUTPUT = "output"
    CONTENT_SAFETY = "content_safety"
    PII_DETECTION = "pii_detection"
    PROMPT_INJECTION = "prompt_injection"
    SEMANTIC = "semantic"
    FORMAT = "format"
    CHAIN_OF_THOUGHT = "chain_of_thought"
    TOOL_USE = "tool_use"
    RATE_LIMIT = "rate_limit"
    COST = "cost"
    LATENCY = "latency"
    CUSTOM = "custom"


class GuardrailSeverity(Enum):
    """Severity levels for guardrail violations."""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class GuardrailAction(Enum):
    """Actions to take on guardrail violation."""
    LOG = "log"
    WARN = "warn"
    BLOCK = "block"
    MODIFY = "modify"
    ESCALATE = "escalate"
    RETRY = "retry"


@dataclass
class GuardrailViolation:
    """Detailed information about a guardrail violation."""
    guardrail_id: str
    guardrail_name: str
    guardrail_type: GuardrailType
    severity: GuardrailSeverity
    action: GuardrailAction
    timestamp: datetime
    message: str
    data_preview: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    remediation_applied: bool = False
    remediation_result: Optional[str] = None


@dataclass
class GuardrailRule:
    """A rule within a guardrail for complex validations."""
    rule_id: str
    name: str
    condition: Callable[[Any], bool]
    message: str
    severity: GuardrailSeverity = GuardrailSeverity.MEDIUM
    enabled: bool = True


__all__ = [
    'GuardrailType',
    'GuardrailSeverity',
    'GuardrailAction',
    'GuardrailViolation',
    'GuardrailRule',
]
