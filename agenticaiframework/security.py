"""
Security module for the Agentic AI Framework.

Provides comprehensive security features including:
- Prompt injection detection and prevention
- Input sanitization and validation
- Content filtering
- Rate limiting
- Authentication and authorization
- Audit logging
- Encryption utilities
"""

import re
import time
import hashlib
import json
from typing import Any, Dict, List, Optional, Callable, Set
from collections import defaultdict
from datetime import datetime, timedelta
import uuid


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


class InputValidator:
    """Validates and sanitizes user inputs."""
    
    def __init__(self):
        self.validators: Dict[str, Callable[[Any], bool]] = {}
        self.sanitizers: Dict[str, Callable[[Any], Any]] = {}
        
    def register_validator(self, name: str, validator_fn: Callable[[Any], bool]):
        """Register a custom validation function."""
        self.validators[name] = validator_fn
        
    def register_sanitizer(self, name: str, sanitizer_fn: Callable[[Any], Any]):
        """Register a custom sanitization function."""
        self.sanitizers[name] = sanitizer_fn
        
    def validate(self, data: Any, validator_name: str = None) -> bool:
        """
        Validate data using specified validator or all validators.
        
        Args:
            data: Data to validate
            validator_name: Specific validator to use, or None for all
            
        Returns:
            True if validation passes, False otherwise
        """
        if validator_name:
            if validator_name in self.validators:
                return self.validators[validator_name](data)
            return False
        
        # Validate against all validators
        return all(validator(data) for validator in self.validators.values())
    
    def sanitize(self, data: Any, sanitizer_name: str = None) -> Any:
        """
        Sanitize data using specified sanitizer or all sanitizers.
        
        Args:
            data: Data to sanitize
            sanitizer_name: Specific sanitizer to use, or None for all
            
        Returns:
            Sanitized data
        """
        if sanitizer_name:
            if sanitizer_name in self.sanitizers:
                return self.sanitizers[sanitizer_name](data)
            return data
        
        # Apply all sanitizers
        result = data
        for sanitizer in self.sanitizers.values():
            result = sanitizer(result)
        return result
    
    @staticmethod
    def validate_string_length(text: str, min_length: int = 0, max_length: int = 10000) -> bool:
        """Validate string length."""
        if not isinstance(text, str):
            return False
        return min_length <= len(text) <= max_length
    
    @staticmethod
    def sanitize_html(text: str) -> str:
        """Remove HTML tags from text."""
        if not isinstance(text, str):
            return text
        return re.sub(r'<[^>]+>', '', text)
    
    @staticmethod
    def sanitize_sql(text: str) -> str:
        """Remove potential SQL injection patterns."""
        if not isinstance(text, str):
            return text
        # Remove common SQL keywords and special characters
        dangerous_patterns = [
            r';', r'--', r'/\*', r'\*/', r'xp_', r'sp_', 
            r'DROP', r'DELETE', r'INSERT', r'UPDATE', r'CREATE', r'ALTER'
        ]
        result = text
        for pattern in dangerous_patterns:
            result = re.sub(pattern, '', result, flags=re.IGNORECASE)
        return result


class RateLimiter:
    """Rate limiting to prevent abuse."""
    
    def __init__(self, max_requests: int = 100, time_window: int = 60):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum number of requests allowed
            time_window: Time window in seconds
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests: Dict[str, List[float]] = defaultdict(list)
        
    def is_allowed(self, identifier: str) -> bool:
        """
        Check if request is allowed for the given identifier.
        
        Args:
            identifier: Unique identifier (e.g., user_id, IP address)
            
        Returns:
            True if request is allowed, False if rate limit exceeded
        """
        current_time = time.time()
        cutoff_time = current_time - self.time_window
        
        # Remove old requests outside the time window
        self.requests[identifier] = [
            req_time for req_time in self.requests[identifier]
            if req_time > cutoff_time
        ]
        
        # Check if limit exceeded
        if len(self.requests[identifier]) >= self.max_requests:
            return False
        
        # Add current request
        self.requests[identifier].append(current_time)
        return True
    
    def get_remaining_requests(self, identifier: str) -> int:
        """Get the number of remaining requests for identifier."""
        current_time = time.time()
        cutoff_time = current_time - self.time_window
        
        # Count valid requests
        valid_requests = [
            req_time for req_time in self.requests.get(identifier, [])
            if req_time > cutoff_time
        ]
        
        return max(0, self.max_requests - len(valid_requests))
    
    def reset(self, identifier: str = None):
        """Reset rate limit for identifier or all identifiers."""
        if identifier:
            self.requests.pop(identifier, None)
        else:
            self.requests.clear()


class ContentFilter:
    """Filter inappropriate or sensitive content."""
    
    def __init__(self):
        self.blocked_words: Set[str] = set()
        self.blocked_patterns: List[re.Pattern] = []
        self.custom_filters: List[Callable[[str], bool]] = []
        
    def add_blocked_word(self, word: str):
        """Add a word to the blocked list."""
        self.blocked_words.add(word.lower())
        
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


class AuditLogger:
    """Audit logging for security events."""
    
    def __init__(self, max_entries: int = 10000):
        self.max_entries = max_entries
        self.logs: List[Dict[str, Any]] = []
        
    def log(self, event_type: str, details: Dict[str, Any], severity: str = 'info'):
        """
        Log a security event.
        
        Args:
            event_type: Type of event (e.g., 'access', 'injection_detected')
            details: Event details
            severity: Severity level ('info', 'warning', 'error', 'critical')
        """
        entry = {
            'id': str(uuid.uuid4()),
            'timestamp': datetime.now().isoformat(),
            'event_type': event_type,
            'severity': severity,
            'details': details
        }
        
        self.logs.append(entry)
        
        # Rotate logs if needed
        if len(self.logs) > self.max_entries:
            self.logs = self.logs[-self.max_entries:]
            
    def query(self, 
              event_type: str = None, 
              severity: str = None,
              start_time: datetime = None,
              end_time: datetime = None) -> List[Dict[str, Any]]:
        """
        Query audit logs with filters.
        
        Args:
            event_type: Filter by event type
            severity: Filter by severity
            start_time: Filter by start time
            end_time: Filter by end time
            
        Returns:
            Filtered list of log entries
        """
        results = self.logs
        
        if event_type:
            results = [log for log in results if log['event_type'] == event_type]
            
        if severity:
            results = [log for log in results if log['severity'] == severity]
            
        if start_time:
            results = [log for log in results 
                      if datetime.fromisoformat(log['timestamp']) >= start_time]
            
        if end_time:
            results = [log for log in results 
                      if datetime.fromisoformat(log['timestamp']) <= end_time]
            
        return results
    
    def export_logs(self, filepath: str):
        """Export logs to a JSON file."""
        with open(filepath, 'w') as f:
            json.dump(self.logs, f, indent=2)
            
    def clear_logs(self):
        """Clear all logs."""
        self.logs.clear()


class SecurityManager:
    """Centralized security management."""
    
    def __init__(self):
        self.injection_detector = PromptInjectionDetector()
        self.input_validator = InputValidator()
        self.rate_limiter = RateLimiter()
        self.content_filter = ContentFilter()
        self.audit_logger = AuditLogger()
        
    def validate_input(self, text: str, user_id: str = None) -> Dict[str, Any]:
        """
        Comprehensive input validation.
        
        Returns:
            Dict with 'is_valid', 'errors', and 'sanitized_text'
        """
        errors = []
        
        # Check rate limit
        if user_id and not self.rate_limiter.is_allowed(user_id):
            errors.append('Rate limit exceeded')
            self.audit_logger.log(
                'rate_limit_exceeded',
                {'user_id': user_id},
                severity='warning'
            )
            
        # Check for prompt injection
        injection_result = self.injection_detector.detect(text)
        if injection_result['is_injection']:
            errors.append('Potential prompt injection detected')
            self.audit_logger.log(
                'injection_detected',
                {
                    'user_id': user_id,
                    'confidence': injection_result['confidence'],
                    'patterns': injection_result['matched_patterns']
                },
                severity='error'
            )
            
        # Check content filter
        if not self.content_filter.is_allowed(text):
            errors.append('Content blocked by filter')
            self.audit_logger.log(
                'content_blocked',
                {'user_id': user_id},
                severity='warning'
            )
            
        # Sanitize text
        sanitized = self.input_validator.sanitize_html(text)
        sanitized = self.input_validator.sanitize_sql(sanitized)
        
        return {
            'is_valid': len(errors) == 0,
            'errors': errors,
            'sanitized_text': sanitized
        }
    
    def get_security_metrics(self) -> Dict[str, Any]:
        """Get security metrics and statistics."""
        injection_logs = self.injection_detector.get_detection_log()
        
        return {
            'total_injections_detected': len(injection_logs),
            'total_audit_entries': len(self.audit_logger.logs),
            'recent_injections': injection_logs[-10:] if injection_logs else []
        }
