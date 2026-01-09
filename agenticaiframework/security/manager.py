"""
Centralized Security Manager.

Provides a unified interface for all security features.
"""

import logging
from typing import Any, Dict

from .injection import PromptInjectionDetector
from .validation import InputValidator
from .rate_limiting import RateLimiter
from .filtering import ContentFilter
from .audit import AuditLogger

logger = logging.getLogger(__name__)


class SecurityManager:
    """Centralized security management."""
    
    def __init__(self,
                 max_requests: int = 100,
                 time_window: int = 60,
                 max_audit_entries: int = 10000):
        """
        Initialize security manager.
        
        Args:
            max_requests: Rate limit max requests
            time_window: Rate limit time window in seconds
            max_audit_entries: Maximum audit log entries
        """
        self.injection_detector = PromptInjectionDetector()
        self.input_validator = InputValidator()
        self.rate_limiter = RateLimiter(max_requests, time_window)
        self.content_filter = ContentFilter()
        self.audit_logger = AuditLogger(max_audit_entries)
        
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
        
        # Log validation
        self.audit_logger.log(
            'input_validation',
            {
                'user_id': user_id,
                'is_valid': len(errors) == 0,
                'errors': errors
            },
            severity='info' if len(errors) == 0 else 'warning'
        )
        
        return {
            'is_valid': len(errors) == 0,
            'errors': errors,
            'sanitized_text': sanitized
        }
    
    def validate_and_sanitize(self, text: str, user_id: str = None) -> str:
        """
        Validate and return sanitized text, raising exception if invalid.
        
        Args:
            text: Input text to validate
            user_id: Optional user identifier
            
        Returns:
            Sanitized text if valid
            
        Raises:
            ValueError: If validation fails
        """
        result = self.validate_input(text, user_id)
        if not result['is_valid']:
            raise ValueError(f"Validation failed: {', '.join(result['errors'])}")
        return result['sanitized_text']
    
    def check_rate_limit(self, user_id: str) -> bool:
        """Check if user has exceeded rate limit."""
        return self.rate_limiter.is_allowed(user_id)
    
    def get_remaining_requests(self, user_id: str) -> int:
        """Get remaining requests for user."""
        return self.rate_limiter.get_remaining_requests(user_id)
    
    def detect_injection(self, text: str) -> Dict[str, Any]:
        """Detect prompt injection in text."""
        return self.injection_detector.detect(text)
    
    def filter_content(self, text: str) -> str:
        """Filter content and return sanitized text."""
        return self.content_filter.filter_text(text)
    
    def get_security_metrics(self) -> Dict[str, Any]:
        """Get security metrics and statistics."""
        injection_logs = self.injection_detector.get_detection_log()
        audit_summary = self.audit_logger.get_summary()
        
        return {
            'total_injections_detected': len(injection_logs),
            'total_audit_entries': audit_summary.get('total_entries', 0),
            'audit_summary': audit_summary,
            'recent_injections': injection_logs[-10:] if injection_logs else []
        }
    
    def export_audit_logs(self, filepath: str):
        """Export audit logs to file."""
        self.audit_logger.export_logs(filepath)
    
    def reset_rate_limits(self, user_id: str = None):
        """Reset rate limits for user or all users."""
        self.rate_limiter.reset(user_id)
