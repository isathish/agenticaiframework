"""
Prompt Injection Detection and Prevention.

Provides protection against prompt injection attacks.
"""

import re
import logging
from typing import Any, Dict, List
from datetime import datetime

logger = logging.getLogger(__name__)


class PromptInjectionDetector:
    """Detects and prevents prompt injection attacks."""
    
    # Common prompt injection patterns
    INJECTION_PATTERNS = [
        r'ignore\s+(previous|all|above|prior)\s+(instructions|prompts|commands)',
        r'disregard\s+(previous|all|above|prior)\s+(instructions|prompts|commands)',
        r'forget\s+(previous|all|above|prior)\s+(instructions|prompts|commands)',
        r'new\s+instructions?:',
        r'system\s*:',
        r'<\s*\|im_start\|',
        r'<\s*\|im_end\|',
        r'reset\s+(context|conversation|chat)',
        r'you\s+are\s+now',
        r'act\s+as\s+(a\s+)?(different|new)',
        r'pretend\s+(to\s+be|you\s+are)',
        r'roleplay\s+as',
        r'jailbreak',
        r'sudo\s+mode',
        r'developer\s+mode',
        r'god\s+mode',
    ]
    
    def __init__(self):
        self.patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.INJECTION_PATTERNS]
        self.custom_patterns: List[re.Pattern] = []
        self.detection_log: List[Dict[str, Any]] = []
        
    def add_custom_pattern(self, pattern: str):
        """Add a custom regex pattern for injection detection."""
        self.custom_patterns.append(re.compile(pattern, re.IGNORECASE))
        
    def detect(self, text: str) -> Dict[str, Any]:
        """
        Detect potential prompt injection attempts.
        
        Returns:
            Dict with 'is_injection', 'confidence', 'matched_patterns', and 'sanitized_text'
        """
        if not text or not isinstance(text, str):
            return {
                'is_injection': False,
                'confidence': 0.0,
                'matched_patterns': [],
                'sanitized_text': text
            }
        
        matched_patterns = []
        
        # Check against known patterns
        for pattern in self.patterns + self.custom_patterns:
            if pattern.search(text):
                matched_patterns.append(pattern.pattern)
        
        # Calculate confidence based on number of matches
        confidence = min(len(matched_patterns) * 0.3, 1.0)
        is_injection = confidence > 0.3
        
        # Log detection
        if is_injection:
            self.detection_log.append({
                'timestamp': datetime.now().isoformat(),
                'text': text[:100],  # Log first 100 chars
                'matched_patterns': matched_patterns,
                'confidence': confidence
            })
        
        return {
            'is_injection': is_injection,
            'confidence': confidence,
            'matched_patterns': matched_patterns,
            'sanitized_text': self._sanitize(text) if is_injection else text
        }
    
    def _sanitize(self, text: str) -> str:
        """Remove potentially malicious content from text."""
        sanitized = text
        
        # Remove matched injection patterns
        for pattern in self.patterns + self.custom_patterns:
            sanitized = pattern.sub('[FILTERED]', sanitized)
        
        return sanitized
    
    def get_detection_log(self) -> List[Dict[str, Any]]:
        """Retrieve the detection log."""
        return self.detection_log
    
    def clear_detection_log(self):
        """Clear the detection log."""
        self.detection_log.clear()
