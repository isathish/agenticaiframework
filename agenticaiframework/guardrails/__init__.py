"""
AgenticAI Framework - Guardrails Package.

Comprehensive guardrail system for AI agents:
- Input/output validation
- Content filtering and safety
- Semantic validation
- Chain-of-thought validation
- Tool use validation
- Policy enforcement
"""

# Types and enums
from .types import (
    GuardrailType,
    GuardrailSeverity,
    GuardrailAction,
    GuardrailViolation,
    GuardrailRule,
)

# Core guardrails
from .core import Guardrail, GuardrailManager

# Specialized guardrails
from .semantic import SemanticGuardrail
from .content_safety import ContentSafetyGuardrail
from .output_format import OutputFormatGuardrail
from .chain_of_thought import ChainOfThoughtGuardrail
from .tool_use import ToolUseGuardrail

# Pipeline
from .pipeline import GuardrailPipeline

# Agent policies
from .policies import (
    PolicyScope,
    PolicyEnforcement,
    AgentPolicy,
    BehaviorPolicy,
    ResourcePolicy,
    SafetyPolicy,
    AgentPolicyManager,
)

# Re-export exception from main exceptions module
from ..exceptions import GuardrailViolationError

# Global instances
guardrail_manager = GuardrailManager()
agent_policy_manager = AgentPolicyManager()
default_safety_policy = SafetyPolicy()
agent_policy_manager.register_safety_policy("default", default_safety_policy)


__all__ = [
    # Types
    'GuardrailType',
    'GuardrailSeverity',
    'GuardrailAction',
    'GuardrailViolation',
    'GuardrailRule',
    
    # Core
    'Guardrail',
    'GuardrailManager',
    
    # Specialized guardrails
    'SemanticGuardrail',
    'ContentSafetyGuardrail',
    'OutputFormatGuardrail',
    'ChainOfThoughtGuardrail',
    'ToolUseGuardrail',
    
    # Pipeline
    'GuardrailPipeline',
    
    # Policies
    'PolicyScope',
    'PolicyEnforcement',
    'AgentPolicy',
    'BehaviorPolicy',
    'ResourcePolicy',
    'SafetyPolicy',
    'AgentPolicyManager',
    
    # Exception
    'GuardrailViolationError',
    
    # Global instances
    'guardrail_manager',
    'agent_policy_manager',
    'default_safety_policy',
]
