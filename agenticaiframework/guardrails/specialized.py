"""
Specialized Guardrails Module.

Provides easy imports for specialized guardrail types and convenience classes.
"""

from .content_safety import ContentSafetyGuardrail
from .semantic import SemanticGuardrail
from .output_format import OutputFormatGuardrail
from .chain_of_thought import ChainOfThoughtGuardrail
from .tool_use import ToolUseGuardrail
from .core import Guardrail
from .types import GuardrailType, GuardrailAction


class PromptInjectionGuardrail(Guardrail):
    """
    Guardrail for detecting prompt injection attacks.
    
    Detects common injection patterns:
    - Ignore previous instructions
    - System prompt leakage attempts
    - Jailbreak patterns
    - Role manipulation
    """
    
    INJECTION_PATTERNS = [
        r"ignore\s+(previous|all|above)\s+instructions",
        r"disregard\s+(previous|all|your)\s+(instructions|rules)",
        r"forget\s+(everything|all|your)\s+(instructions|rules|training)",
        r"you\s+are\s+now\s+(in)?\s*(DAN|jailbreak|unrestricted)",
        r"pretend\s+(you\s+are|to\s+be)\s+(a|an)?\s*(evil|malicious|unrestricted)",
        r"system\s*prompt\s*[:=]",
        r"<\|system\|>",
        r"\[INST\]",
        r"###\s*instruction",
        r"act\s+as\s+(if\s+you\s+are|a)\s*(unrestricted|evil|DAN)",
        r"bypass\s+(your|the)\s*(filters|safety|restrictions)",
        r"reveal\s+(your|the)\s*(system|initial)\s*prompt",
    ]
    
    def __init__(self, name: str = "prompt_injection"):
        import re
        self._patterns = [re.compile(p, re.IGNORECASE) for p in self.INJECTION_PATTERNS]
        
        # Create the validation function
        def validate_fn(data):
            if not isinstance(data, str):
                return True
            for pattern in self._patterns:
                if pattern.search(data):
                    return False
            return True
        
        super().__init__(
            name=name,
            validation_fn=validate_fn,
            policy={"type": "security", "description": "Detects prompt injection attacks"},
            severity="critical",
        )
    
    def check(self, data: str) -> dict:
        """Check with detailed results."""
        if not isinstance(data, str):
            return {"is_safe": True, "violations": []}
        
        violations = []
        for pattern in self._patterns:
            match = pattern.search(data)
            if match:
                violations.append({
                    "type": "prompt_injection",
                    "pattern": pattern.pattern,
                    "match": match.group()[:50],
                })
        
        return {
            "is_safe": len(violations) == 0,
            "violations": violations,
        }


class InputLengthGuardrail(Guardrail):
    """
    Guardrail for input length validation.
    
    Prevents:
    - Empty inputs
    - Excessively long inputs (token/context attacks)
    """
    
    def __init__(
        self,
        name: str = "input_length",
        min_length: int = 1,
        max_length: int = 50000,
    ):
        self.min_length = min_length
        self.max_length = max_length
        
        # Create the validation function
        def validate_fn(data):
            if not isinstance(data, str):
                return True
            length = len(data)
            return self.min_length <= length <= self.max_length
        
        super().__init__(
            name=name,
            validation_fn=validate_fn,
            policy={"type": "format", "description": f"Validates input length ({min_length}-{max_length} chars)"},
            severity="medium",
        )
    
    def check(self, data: str) -> dict:
        """Check with detailed results."""
        if not isinstance(data, str):
            return {"is_safe": True, "violations": []}
        
        length = len(data)
        violations = []
        
        if length < self.min_length:
            violations.append({
                "type": "input_too_short",
                "length": length,
                "min_required": self.min_length,
            })
        
        if length > self.max_length:
            violations.append({
                "type": "input_too_long",
                "length": length,
                "max_allowed": self.max_length,
            })
        
        return {
            "is_safe": len(violations) == 0,
            "violations": violations,
        }


class PIIDetectionGuardrail(Guardrail):
    """
    Guardrail for detecting Personally Identifiable Information (PII).
    
    Detects:
    - Email addresses
    - Phone numbers
    - Social Security Numbers
    - Credit card numbers
    - IP addresses
    """
    
    PII_PATTERNS = {
        "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        "phone_us": r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
        "ssn": r"\b\d{3}[-]?\d{2}[-]?\d{4}\b",
        "credit_card": r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
        "ip_address": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
    }
    
    def __init__(
        self,
        name: str = "pii_detection",
        detect_types: list = None,
    ):
        import re
        
        types_to_detect = detect_types or list(self.PII_PATTERNS.keys())
        self._patterns = {
            pii_type: re.compile(pattern)
            for pii_type, pattern in self.PII_PATTERNS.items()
            if pii_type in types_to_detect
        }
        
        # Create the validation function
        def validate_fn(data):
            if not isinstance(data, str):
                return True
            for pattern in self._patterns.values():
                if pattern.search(data):
                    return False
            return True
        
        super().__init__(
            name=name,
            validation_fn=validate_fn,
            policy={"type": "compliance", "description": "Detects PII in input/output"},
            severity="high",
        )
    
    def check(self, data: str) -> dict:
        """Check with detailed results."""
        if not isinstance(data, str):
            return {"is_safe": True, "violations": [], "pii_found": []}
        
        pii_found = []
        for pii_type, pattern in self._patterns.items():
            matches = pattern.findall(data)
            for match in matches:
                pii_found.append({
                    "type": pii_type,
                    "value_preview": match[:4] + "***" if len(match) > 4 else "***",
                })
        
        return {
            "is_safe": len(pii_found) == 0,
            "violations": [{"type": "pii_detected", "count": len(pii_found)}] if pii_found else [],
            "pii_found": pii_found,
        }


__all__ = [
    # From other modules
    "ContentSafetyGuardrail",
    "SemanticGuardrail",
    "OutputFormatGuardrail",
    "ChainOfThoughtGuardrail",
    "ToolUseGuardrail",
    # Local definitions
    "PromptInjectionGuardrail",
    "InputLengthGuardrail",
    "PIIDetectionGuardrail",
]
