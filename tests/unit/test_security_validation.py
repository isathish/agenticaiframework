"""
Tests for security validation module.
"""

import pytest
from unittest.mock import Mock, patch

from agenticaiframework.security.validation import InputValidator


class TestInputValidator:
    """Tests for InputValidator class."""
    
    def test_init(self):
        """Test initialization."""
        validator = InputValidator()
        assert len(validator.validators) == 0
        assert len(validator.sanitizers) == 0
    
    def test_register_validator(self):
        """Test registering a validator."""
        validator = InputValidator()
        
        def is_positive(x):
            return x > 0
        
        validator.register_validator("positive", is_positive)
        
        assert "positive" in validator.validators
    
    def test_register_sanitizer(self):
        """Test registering a sanitizer."""
        validator = InputValidator()
        
        def lowercase(x):
            return x.lower()
        
        validator.register_sanitizer("lowercase", lowercase)
        
        assert "lowercase" in validator.sanitizers
    
    def test_validate_with_specific_validator(self):
        """Test validation with specific validator."""
        validator = InputValidator()
        validator.register_validator("positive", lambda x: x > 0)
        
        assert validator.validate(5, "positive") is True
        assert validator.validate(-1, "positive") is False
    
    def test_validate_unknown_validator(self):
        """Test validation with unknown validator."""
        validator = InputValidator()
        
        assert validator.validate(5, "unknown") is False
    
    def test_validate_all_validators(self):
        """Test validation against all validators."""
        validator = InputValidator()
        validator.register_validator("positive", lambda x: x > 0)
        validator.register_validator("even", lambda x: x % 2 == 0)
        
        # Both pass
        assert validator.validate(4) is True
        
        # One fails
        assert validator.validate(3) is False
    
    def test_sanitize_with_specific_sanitizer(self):
        """Test sanitization with specific sanitizer."""
        validator = InputValidator()
        validator.register_sanitizer("lowercase", lambda x: x.lower())
        
        result = validator.sanitize("HELLO", "lowercase")
        assert result == "hello"
    
    def test_sanitize_unknown_sanitizer(self):
        """Test sanitization with unknown sanitizer returns original."""
        validator = InputValidator()
        
        result = validator.sanitize("hello", "unknown")
        assert result == "hello"
    
    def test_sanitize_all_sanitizers(self):
        """Test sanitization with all sanitizers."""
        validator = InputValidator()
        validator.register_sanitizer("trim", lambda x: x.strip())
        validator.register_sanitizer("lowercase", lambda x: x.lower())
        
        result = validator.sanitize("  HELLO  ")
        assert result == "hello"


class TestStaticValidators:
    """Tests for static validation methods."""
    
    def test_validate_string_length_valid(self):
        """Test string length validation - valid cases."""
        assert InputValidator.validate_string_length("hello", 1, 10) is True
        assert InputValidator.validate_string_length("", 0, 10) is True
        assert InputValidator.validate_string_length("x" * 100, 0, 100) is True
    
    def test_validate_string_length_invalid(self):
        """Test string length validation - invalid cases."""
        assert InputValidator.validate_string_length("hi", 5, 10) is False
        assert InputValidator.validate_string_length("hello world", 1, 5) is False
        assert InputValidator.validate_string_length(123, 0, 10) is False  # Not a string
    
    def test_validate_email_valid(self):
        """Test email validation - valid cases."""
        assert InputValidator.validate_email("user@example.com") is True
        assert InputValidator.validate_email("user.name@example.co.uk") is True
        assert InputValidator.validate_email("user+tag@example.org") is True
    
    def test_validate_email_invalid(self):
        """Test email validation - invalid cases."""
        assert InputValidator.validate_email("invalid") is False
        assert InputValidator.validate_email("@example.com") is False
        assert InputValidator.validate_email("user@") is False
        assert InputValidator.validate_email("user@.com") is False
        assert InputValidator.validate_email(123) is False  # Not a string
    
    def test_validate_alphanumeric_valid(self):
        """Test alphanumeric validation - valid cases."""
        assert InputValidator.validate_alphanumeric("hello123") is True
        assert InputValidator.validate_alphanumeric("ABC") is True
        assert InputValidator.validate_alphanumeric("123") is True
    
    def test_validate_alphanumeric_invalid(self):
        """Test alphanumeric validation - invalid cases."""
        assert InputValidator.validate_alphanumeric("hello world") is False
        assert InputValidator.validate_alphanumeric("hello@123") is False
        assert InputValidator.validate_alphanumeric("") is False
        assert InputValidator.validate_alphanumeric(123) is False  # Not a string


class TestStaticSanitizers:
    """Tests for static sanitization methods."""
    
    def test_sanitize_html_removes_tags(self):
        """Test HTML sanitization removes tags."""
        result = InputValidator.sanitize_html("<p>Hello</p>")
        assert result == "Hello"
    
    def test_sanitize_html_removes_complex_tags(self):
        """Test HTML sanitization removes complex tags."""
        result = InputValidator.sanitize_html('<script src="evil.js">alert("XSS")</script>')
        assert "script" not in result
        assert "<" not in result
    
    def test_sanitize_html_preserves_text(self):
        """Test HTML sanitization preserves text."""
        result = InputValidator.sanitize_html("Just plain text")
        assert result == "Just plain text"
    
    def test_sanitize_html_non_string(self):
        """Test HTML sanitization with non-string."""
        result = InputValidator.sanitize_html(123)
        assert result == 123
    
    def test_sanitize_sql(self):
        """Test SQL sanitization."""
        result = InputValidator.sanitize_sql("Robert'; DROP TABLE users;--")
        # Should escape or sanitize dangerous characters
        assert "'" not in result or "''" in result or result != "Robert'; DROP TABLE users;--"


class TestInputValidatorEdgeCases:
    """Edge case tests for InputValidator."""
    
    def test_empty_validators_validate_all(self):
        """Test validate with no validators registered."""
        validator = InputValidator()
        
        # Should return True (vacuously true - no validators to fail)
        assert validator.validate("anything") is True
    
    def test_empty_sanitizers_sanitize_all(self):
        """Test sanitize with no sanitizers registered."""
        validator = InputValidator()
        
        result = validator.sanitize("unchanged")
        assert result == "unchanged"
    
    def test_validator_chain(self):
        """Test chaining validators."""
        validator = InputValidator()
        validator.register_validator("length", lambda x: len(x) > 3)
        validator.register_validator("alpha", lambda x: x.isalpha())
        validator.register_validator("lower", lambda x: x.islower())
        
        assert validator.validate("hello") is True
        assert validator.validate("HI") is False  # Too short and uppercase
    
    def test_sanitizer_order(self):
        """Test sanitizers apply in order."""
        validator = InputValidator()
        
        # Order matters: trim first, then lowercase
        validator.register_sanitizer("trim", lambda x: x.strip())
        validator.register_sanitizer("lowercase", lambda x: x.lower())
        
        result = validator.sanitize("  HELLO  ")
        assert result == "hello"
