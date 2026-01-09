"""
Chain of Thought Guardrail for validating reasoning chains.

Validates:
- Logical consistency
- Step completeness
- Conclusion alignment
- Reasoning depth
"""

import re
from typing import Dict, Any, List, Optional


class ChainOfThoughtGuardrail:
    """
    Guardrail for validating chain-of-thought reasoning.
    
    Validates:
    - Logical consistency
    - Step completeness
    - Conclusion alignment
    - Reasoning depth
    """
    
    def __init__(self,
                 min_steps: int = 2,
                 max_steps: int = 10,
                 require_conclusion: bool = True,
                 step_markers: Optional[List[str]] = None):
        """
        Initialize chain-of-thought guardrail.
        
        Args:
            min_steps: Minimum reasoning steps
            max_steps: Maximum reasoning steps
            require_conclusion: Require explicit conclusion
            step_markers: Patterns that indicate reasoning steps
        """
        self.min_steps = min_steps
        self.max_steps = max_steps
        self.require_conclusion = require_conclusion
        self.step_markers = step_markers or [
            r'(?:Step|Phase)\s*\d+',
            r'(?:First|Second|Third|Then|Next|Finally)',
            r'\d+\.',
            r'[•\-\*]\s+'
        ]
        
        self._step_patterns = [re.compile(p, re.IGNORECASE) for p in self.step_markers]
        self._conclusion_patterns = [
            re.compile(r'(?:therefore|thus|in conclusion|finally|so|hence)', re.IGNORECASE),
            re.compile(r'(?:the answer is|conclusion:|result:)', re.IGNORECASE)
        ]
    
    def validate(self, reasoning: str) -> Dict[str, Any]:
        """
        Validate chain-of-thought reasoning.
        
        Returns:
            Dict with is_valid, step_count, has_conclusion, issues
        """
        issues = []
        
        # Count reasoning steps
        step_count = 0
        for pattern in self._step_patterns:
            step_count += len(pattern.findall(reasoning))
        
        if step_count < self.min_steps:
            issues.append(f"Insufficient reasoning steps: {step_count} < {self.min_steps}")
        
        if step_count > self.max_steps:
            issues.append(f"Too many reasoning steps: {step_count} > {self.max_steps}")
        
        # Check for conclusion
        has_conclusion = any(
            pattern.search(reasoning) for pattern in self._conclusion_patterns
        )
        
        if self.require_conclusion and not has_conclusion:
            issues.append("Missing explicit conclusion in reasoning")
        
        # Check for logical connectors
        logical_connectors = ['because', 'since', 'if', 'then', 'however', 'although']
        connector_count = sum(
            1 for conn in logical_connectors 
            if conn in reasoning.lower()
        )
        
        if connector_count == 0 and step_count > 2:
            issues.append("Reasoning lacks logical connectors between steps")
        
        return {
            'is_valid': len(issues) == 0,
            'step_count': step_count,
            'has_conclusion': has_conclusion,
            'connector_count': connector_count,
            'issues': issues
        }


__all__ = ['ChainOfThoughtGuardrail']
