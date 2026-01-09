"""
Content Filtering for inappropriate or sensitive content.

Provides filtering functionality to block unwanted content.
"""

import re
import logging
from typing import Set, List, Callable

logger = logging.getLogger(__name__)


class ContentFilter:
    """Filter inappropriate or sensitive content."""
    
    def __init__(self):
        self.blocked_words: Set[str] = set()
        self.blocked_patterns: List[re.Pattern] = []
        self.custom_filters: List[Callable[[str], bool]] = []
        
    def add_blocked_word(self, word: str):
        """Add a word to the blocked list."""
        self.blocked_words.add(word.lower())
        
    def add_blocked_words(self, words: List[str]):
        """Add multiple words to the blocked list."""
        for word in words:
            self.add_blocked_word(word)
        
    def add_blocked_pattern(self, pattern: str):
        """Add a regex pattern to block."""
        self.blocked_patterns.append(re.compile(pattern, re.IGNORECASE))
        
    def add_custom_filter(self, filter_fn: Callable[[str], bool]):
        """Add a custom filter function that returns True if content should be blocked."""
        self.custom_filters.append(filter_fn)
        
    def is_allowed(self, text: str) -> bool:
        """
        Check if text passes all filters.
        
        Returns:
            True if content is allowed, False if blocked
        """
        if not isinstance(text, str):
            return False
        
        text_lower = text.lower()
        
        # Check blocked words
        for word in self.blocked_words:
            if word in text_lower:
                return False
        
        # Check blocked patterns
        for pattern in self.blocked_patterns:
            if pattern.search(text):
                return False
        
        # Check custom filters
        for filter_fn in self.custom_filters:
            if filter_fn(text):
                return False
        
        return True
    
    def filter_text(self, text: str, replacement: str = '[FILTERED]') -> str:
        """Remove or replace blocked content."""
        if not isinstance(text, str):
            return text
        
        result = text
        
        # Replace blocked words
        for word in self.blocked_words:
            result = re.sub(rf'\b{re.escape(word)}\b', replacement, result, flags=re.IGNORECASE)
        
        # Replace blocked patterns
        for pattern in self.blocked_patterns:
            result = pattern.sub(replacement, result)
        
        return result
    
    def get_violations(self, text: str) -> List[str]:
        """
        Get list of violations found in text.
        
        Returns:
            List of matched blocked words and patterns
        """
        violations = []
        text_lower = text.lower() if isinstance(text, str) else ''
        
        # Check blocked words
        for word in self.blocked_words:
            if word in text_lower:
                violations.append(f"Blocked word: {word}")
        
        # Check blocked patterns
        for pattern in self.blocked_patterns:
            if pattern.search(text):
                violations.append(f"Blocked pattern: {pattern.pattern}")
        
        return violations
    
    def clear_filters(self):
        """Clear all filters."""
        self.blocked_words.clear()
        self.blocked_patterns.clear()
        self.custom_filters.clear()


class ProfanityFilter(ContentFilter):
    """Specialized filter for profanity and offensive content."""
    
    # Basic list - in production, use a comprehensive library
    DEFAULT_BLOCKED_WORDS = [
        # This is a placeholder - actual implementation would use a proper profanity library
    ]
    
    def __init__(self, use_defaults: bool = True):
        super().__init__()
        if use_defaults:
            self.add_blocked_words(self.DEFAULT_BLOCKED_WORDS)


class PIIFilter(ContentFilter):
    """Filter for Personally Identifiable Information (PII)."""
    
    PII_PATTERNS = [
        # Social Security Number patterns
        r'\b\d{3}-\d{2}-\d{4}\b',
        r'\b\d{9}\b',
        # Credit card patterns
        r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',
        # Email (for detection, not necessarily blocking)
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        # Phone numbers
        r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b',
        r'\b\(\d{3}\)\s?\d{3}[-.\s]?\d{4}\b',
    ]
    
    def __init__(self, detect_email: bool = False, detect_phone: bool = True):
        super().__init__()
        
        # Add SSN and credit card patterns (always blocked)
        self.add_blocked_pattern(r'\b\d{3}-\d{2}-\d{4}\b')  # SSN
        self.add_blocked_pattern(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b')  # Credit card
        
        if detect_phone:
            self.add_blocked_pattern(r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b')
            self.add_blocked_pattern(r'\b\(\d{3}\)\s?\d{3}[-.\s]?\d{4}\b')
        
        if detect_email:
            self.add_blocked_pattern(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
