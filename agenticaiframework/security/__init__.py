"""
Security Package for the Agentic AI Framework.

Provides comprehensive security features including:
- Prompt injection detection and prevention
- Input sanitization and validation
- Content filtering
- Rate limiting
- Audit logging
"""

from .injection import PromptInjectionDetector
from .validation import InputValidator
from .rate_limiting import RateLimiter, TieredRateLimiter
from .filtering import ContentFilter, ProfanityFilter, PIIFilter
from .audit import AuditLogger
from .manager import SecurityManager

__all__ = [
    # Injection Detection
    'PromptInjectionDetector',
    
    # Validation
    'InputValidator',
    
    # Rate Limiting
    'RateLimiter',
    'TieredRateLimiter',
    
    # Content Filtering
    'ContentFilter',
    'ProfanityFilter',
    'PIIFilter',
    
    # Audit Logging
    'AuditLogger',
    
    # Security Manager
    'SecurityManager',
    
    # Global instances
    'security_manager',
    'injection_detector',
    'input_validator',
    'rate_limiter',
    'content_filter',
    'audit_logger',
]

# Global instances for convenience
security_manager = SecurityManager()
injection_detector = PromptInjectionDetector()
input_validator = InputValidator()
rate_limiter = RateLimiter()
content_filter = ContentFilter()
audit_logger = AuditLogger()
