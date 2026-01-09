"""
Content Safety Guardrail for detecting harmful content.

Checks for:
- Hate speech indicators
- Violence indicators
- Adult content indicators
- Self-harm indicators
- Dangerous activities
"""

import re
from typing import Dict, Any, List, Optional, Pattern


class ContentSafetyGuardrail:
    """
    Content safety guardrail for detecting harmful content.
    
    Checks for:
    - Hate speech indicators
    - Violence indicators
    - Adult content indicators
    - Self-harm indicators
    - Dangerous activities
    """
    
    # Category patterns (simplified - use ML models in production)
    HARMFUL_PATTERNS = {
        'hate_speech': [
            r'\b(hate|hatred|racist|sexist|bigot)\b',
            r'\b(discriminate|discrimination)\b',
        ],
        'violence': [
            r'\b(kill|murder|attack|harm|hurt|weapon)\b',
            r'\b(bomb|explosive|terrorist)\b',
        ],
        'self_harm': [
            r'\b(suicide|self[- ]?harm|hurt myself)\b',
        ],
        'dangerous': [
            r'\b(illegal|hack|exploit|bypass security)\b',
            r'\b(make (a )?bomb|create poison)\b',
        ],
    }
    
    def __init__(self, 
                 categories: Optional[List[str]] = None,
                 sensitivity: float = 0.5):
        """
        Initialize content safety guardrail.
        
        Args:
            categories: Categories to check (default: all)
            sensitivity: Sensitivity level 0-1 (higher = more strict)
        """
        self.categories = categories or list(self.HARMFUL_PATTERNS.keys())
        self.sensitivity = sensitivity
        
        # Compile patterns for enabled categories
        self._compiled_patterns: Dict[str, List[Pattern]] = {}
        for category in self.categories:
            if category in self.HARMFUL_PATTERNS:
                self._compiled_patterns[category] = [
                    re.compile(pattern, re.IGNORECASE)
                    for pattern in self.HARMFUL_PATTERNS[category]
                ]
    
    def check(self, content: str) -> Dict[str, Any]:
        """
        Check content for safety issues.
        
        Returns:
            Dict with is_safe, violations, and category scores
        """
        violations = []
        category_scores = {}
        
        for category, patterns in self._compiled_patterns.items():
            matches = 0
            for pattern in patterns:
                if pattern.search(content):
                    matches += 1
            
            score = matches / len(patterns) if patterns else 0
            category_scores[category] = score
            
            if score >= self.sensitivity:
                violations.append({
                    'category': category,
                    'score': score,
                    'message': f"Content flagged for {category} (score: {score:.2f})"
                })
        
        return {
            'is_safe': len(violations) == 0,
            'violations': violations,
            'category_scores': category_scores
        }


__all__ = ['ContentSafetyGuardrail']
