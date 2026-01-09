"""
Input Validation and Sanitization.

Provides tools for validating and sanitizing user inputs.
"""

import re
import logging
from typing import Any, Dict, Callable

logger = logging.getLogger(__name__)


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
    def validate_email(email: str) -> bool:
        """Validate email format."""
        if not isinstance(email, str):
            return False
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    @staticmethod
    def validate_alphanumeric(text: str) -> bool:
        """Validate text contains only alphanumeric characters."""
        if not isinstance(text, str):
            return False
        return text.isalnum()
    
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
    
    @staticmethod
    def sanitize_path(path: str) -> str:
        """Sanitize file path to prevent directory traversal."""
        if not isinstance(path, str):
            return path
        # Remove directory traversal patterns
        dangerous_patterns = [r'\.\./', r'\.\.\\', r'%2e%2e/', r'%2e%2e\\']
        result = path
        for pattern in dangerous_patterns:
            result = re.sub(pattern, '', result, flags=re.IGNORECASE)
        return result
