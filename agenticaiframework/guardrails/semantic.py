"""
Semantic Guardrail for content understanding and validation.

Uses pattern matching and heuristics for semantic validation.
Can be extended with embedding-based similarity.
"""

import re
from typing import Dict, Any, List, Optional, Tuple


class SemanticGuardrail:
    """
    Semantic guardrail for content understanding and validation.
    
    Uses pattern matching and heuristics for semantic validation.
    Can be extended with embedding-based similarity.
    """
    
    def __init__(self, 
                 name: str,
                 allowed_topics: Optional[List[str]] = None,
                 blocked_topics: Optional[List[str]] = None,
                 required_topics: Optional[List[str]] = None,
                 similarity_threshold: float = 0.7):
        self.name = name
        self.allowed_topics = allowed_topics or []
        self.blocked_topics = blocked_topics or []
        self.required_topics = required_topics or []
        self.similarity_threshold = similarity_threshold
        
        # Build keyword patterns
        self._blocked_patterns = [
            re.compile(rf'\b{re.escape(topic)}\b', re.IGNORECASE)
            for topic in self.blocked_topics
        ]
        self._required_patterns = [
            re.compile(rf'\b{re.escape(topic)}\b', re.IGNORECASE)
            for topic in self.required_topics
        ]
    
    def validate(self, content: str) -> Tuple[bool, List[str]]:
        """
        Validate content semantically.
        
        Returns:
            Tuple of (is_valid, list of violation messages)
        """
        violations = []
        
        # Check blocked topics
        for i, pattern in enumerate(self._blocked_patterns):
            if pattern.search(content):
                violations.append(
                    f"Content contains blocked topic: '{self.blocked_topics[i]}'"
                )
        
        # Check required topics
        for i, pattern in enumerate(self._required_patterns):
            if not pattern.search(content):
                violations.append(
                    f"Content missing required topic: '{self.required_topics[i]}'"
                )
        
        return len(violations) == 0, violations
    
    def compute_topic_score(self, content: str, topic: str) -> float:
        """Compute relevance score for a topic in content."""
        content_lower = content.lower()
        topic_lower = topic.lower()
        
        # Direct match
        if topic_lower in content_lower:
            return 1.0
        
        # Word overlap
        topic_words = set(topic_lower.split())
        content_words = set(content_lower.split())
        
        if not topic_words:
            return 0.0
        
        overlap = len(topic_words & content_words)
        return overlap / len(topic_words)


__all__ = ['SemanticGuardrail']
