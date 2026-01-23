"""
Enterprise Validation Module.

Provides input/output validation, schema validation, and sanitization
for secure and reliable agent interactions.

Example:
    # Schema validation
    @validate_input(UserSchema)
    @validate_output(ResponseSchema)
    async def process_user(data: dict) -> dict:
        return {"id": data["id"], "status": "processed"}
    
    # Field validation
    validator = Validator()
    validator.add_rule("email", EmailRule())
    validator.add_rule("age", RangeRule(min=0, max=150))
    
    result = validator.validate(data)
"""

from __future__ import annotations

import re
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Pattern,
    Set,
    Type,
    TypeVar,
    Union,
)
from functools import wraps
import logging

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ValidationError(Exception):
    """Validation error with details."""
    
    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Any = None,
        errors: Optional[List['ValidationError']] = None,
    ):
        super().__init__(message)
        self.field = field
        self.value = value
        self.errors = errors or []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {"message": str(self)}
        if self.field:
            result["field"] = self.field
        if self.errors:
            result["errors"] = [e.to_dict() for e in self.errors]
        return result


@dataclass
class ValidationResult:
    """Result of validation operation."""
    valid: bool
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    sanitized_data: Optional[Any] = None
    
    def __bool__(self) -> bool:
        return self.valid
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "valid": self.valid,
            "errors": [e.to_dict() for e in self.errors],
            "warnings": self.warnings,
        }


class ValidationRule(ABC):
    """Abstract validation rule."""
    
    @abstractmethod
    def validate(self, value: Any, field_name: str = "") -> ValidationResult:
        """Validate a value."""
        pass
    
    def sanitize(self, value: Any) -> Any:
        """Sanitize value (optional)."""
        return value


class RequiredRule(ValidationRule):
    """Validates that a value is present."""
    
    def __init__(self, message: str = "Field is required"):
        self.message = message
    
    def validate(self, value: Any, field_name: str = "") -> ValidationResult:
        if value is None or value == "" or (isinstance(value, (list, dict)) and len(value) == 0):
            return ValidationResult(
                valid=False,
                errors=[ValidationError(self.message, field_name, value)],
            )
        return ValidationResult(valid=True, sanitized_data=value)


class TypeRule(ValidationRule):
    """Validates value type."""
    
    def __init__(
        self,
        expected_type: Type,
        coerce: bool = False,
        message: Optional[str] = None,
    ):
        self.expected_type = expected_type
        self.coerce = coerce
        self.message = message
    
    def validate(self, value: Any, field_name: str = "") -> ValidationResult:
        if value is None:
            return ValidationResult(valid=True, sanitized_data=value)
        
        if isinstance(value, self.expected_type):
            return ValidationResult(valid=True, sanitized_data=value)
        
        if self.coerce:
            try:
                coerced = self.expected_type(value)
                return ValidationResult(valid=True, sanitized_data=coerced)
            except (ValueError, TypeError):
                pass
        
        message = self.message or f"Expected {self.expected_type.__name__}, got {type(value).__name__}"
        return ValidationResult(
            valid=False,
            errors=[ValidationError(message, field_name, value)],
        )


class StringRule(ValidationRule):
    """Validates string values."""
    
    def __init__(
        self,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
        pattern: Optional[Union[str, Pattern]] = None,
        strip: bool = True,
        lowercase: bool = False,
        uppercase: bool = False,
    ):
        self.min_length = min_length
        self.max_length = max_length
        self.pattern = re.compile(pattern) if isinstance(pattern, str) else pattern
        self.strip = strip
        self.lowercase = lowercase
        self.uppercase = uppercase
    
    def validate(self, value: Any, field_name: str = "") -> ValidationResult:
        if value is None:
            return ValidationResult(valid=True, sanitized_data=value)
        
        if not isinstance(value, str):
            return ValidationResult(
                valid=False,
                errors=[ValidationError(f"Expected string, got {type(value).__name__}", field_name, value)],
            )
        
        # Sanitize
        sanitized = self.sanitize(value)
        errors = []
        
        if self.min_length and len(sanitized) < self.min_length:
            errors.append(ValidationError(
                f"Minimum length is {self.min_length}",
                field_name,
                value,
            ))
        
        if self.max_length and len(sanitized) > self.max_length:
            errors.append(ValidationError(
                f"Maximum length is {self.max_length}",
                field_name,
                value,
            ))
        
        if self.pattern and not self.pattern.match(sanitized):
            errors.append(ValidationError(
                f"Value does not match required pattern",
                field_name,
                value,
            ))
        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            sanitized_data=sanitized,
        )
    
    def sanitize(self, value: Any) -> str:
        if not isinstance(value, str):
            return value
        
        result = value
        if self.strip:
            result = result.strip()
        if self.lowercase:
            result = result.lower()
        if self.uppercase:
            result = result.upper()
        return result


class RangeRule(ValidationRule):
    """Validates numeric ranges."""
    
    def __init__(
        self,
        min: Optional[float] = None,
        max: Optional[float] = None,
        exclusive_min: bool = False,
        exclusive_max: bool = False,
    ):
        self.min = min
        self.max = max
        self.exclusive_min = exclusive_min
        self.exclusive_max = exclusive_max
    
    def validate(self, value: Any, field_name: str = "") -> ValidationResult:
        if value is None:
            return ValidationResult(valid=True, sanitized_data=value)
        
        if not isinstance(value, (int, float)):
            return ValidationResult(
                valid=False,
                errors=[ValidationError(f"Expected number, got {type(value).__name__}", field_name, value)],
            )
        
        errors = []
        
        if self.min is not None:
            if self.exclusive_min and value <= self.min:
                errors.append(ValidationError(f"Value must be greater than {self.min}", field_name, value))
            elif not self.exclusive_min and value < self.min:
                errors.append(ValidationError(f"Value must be at least {self.min}", field_name, value))
        
        if self.max is not None:
            if self.exclusive_max and value >= self.max:
                errors.append(ValidationError(f"Value must be less than {self.max}", field_name, value))
            elif not self.exclusive_max and value > self.max:
                errors.append(ValidationError(f"Value must be at most {self.max}", field_name, value))
        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            sanitized_data=value,
        )


class EmailRule(ValidationRule):
    """Validates email addresses."""
    
    EMAIL_PATTERN = re.compile(
        r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    )
    
    def __init__(self, normalize: bool = True):
        self.normalize = normalize
    
    def validate(self, value: Any, field_name: str = "") -> ValidationResult:
        if value is None or value == "":
            return ValidationResult(valid=True, sanitized_data=value)
        
        if not isinstance(value, str):
            return ValidationResult(
                valid=False,
                errors=[ValidationError("Email must be a string", field_name, value)],
            )
        
        sanitized = value.strip().lower() if self.normalize else value
        
        if not self.EMAIL_PATTERN.match(sanitized):
            return ValidationResult(
                valid=False,
                errors=[ValidationError("Invalid email format", field_name, value)],
            )
        
        return ValidationResult(valid=True, sanitized_data=sanitized)


class URLRule(ValidationRule):
    """Validates URLs."""
    
    URL_PATTERN = re.compile(
        r'^https?://[^\s<>"\{\}\|\\^\[\]`]+$'
    )
    
    def __init__(self, allowed_schemes: Optional[List[str]] = None):
        self.allowed_schemes = allowed_schemes or ["http", "https"]
    
    def validate(self, value: Any, field_name: str = "") -> ValidationResult:
        if value is None or value == "":
            return ValidationResult(valid=True, sanitized_data=value)
        
        if not isinstance(value, str):
            return ValidationResult(
                valid=False,
                errors=[ValidationError("URL must be a string", field_name, value)],
            )
        
        sanitized = value.strip()
        
        # Check scheme
        scheme = sanitized.split("://")[0] if "://" in sanitized else ""
        if scheme not in self.allowed_schemes:
            return ValidationResult(
                valid=False,
                errors=[ValidationError(f"URL scheme must be one of: {self.allowed_schemes}", field_name, value)],
            )
        
        if not self.URL_PATTERN.match(sanitized):
            return ValidationResult(
                valid=False,
                errors=[ValidationError("Invalid URL format", field_name, value)],
            )
        
        return ValidationResult(valid=True, sanitized_data=sanitized)


class EnumRule(ValidationRule):
    """Validates against allowed values."""
    
    def __init__(
        self,
        allowed: List[Any],
        case_insensitive: bool = False,
    ):
        self.allowed = allowed
        self.case_insensitive = case_insensitive
    
    def validate(self, value: Any, field_name: str = "") -> ValidationResult:
        if value is None:
            return ValidationResult(valid=True, sanitized_data=value)
        
        check_value = value.lower() if self.case_insensitive and isinstance(value, str) else value
        check_allowed = [a.lower() if self.case_insensitive and isinstance(a, str) else a for a in self.allowed]
        
        if check_value not in check_allowed:
            return ValidationResult(
                valid=False,
                errors=[ValidationError(f"Value must be one of: {self.allowed}", field_name, value)],
            )
        
        return ValidationResult(valid=True, sanitized_data=value)


class ListRule(ValidationRule):
    """Validates list values."""
    
    def __init__(
        self,
        item_rule: Optional[ValidationRule] = None,
        min_items: Optional[int] = None,
        max_items: Optional[int] = None,
        unique: bool = False,
    ):
        self.item_rule = item_rule
        self.min_items = min_items
        self.max_items = max_items
        self.unique = unique
    
    def validate(self, value: Any, field_name: str = "") -> ValidationResult:
        if value is None:
            return ValidationResult(valid=True, sanitized_data=value)
        
        if not isinstance(value, list):
            return ValidationResult(
                valid=False,
                errors=[ValidationError(f"Expected list, got {type(value).__name__}", field_name, value)],
            )
        
        errors = []
        sanitized = []
        
        if self.min_items and len(value) < self.min_items:
            errors.append(ValidationError(f"Minimum {self.min_items} items required", field_name, value))
        
        if self.max_items and len(value) > self.max_items:
            errors.append(ValidationError(f"Maximum {self.max_items} items allowed", field_name, value))
        
        if self.unique:
            try:
                if len(value) != len(set(value)):
                    errors.append(ValidationError("Items must be unique", field_name, value))
            except TypeError:
                pass  # Unhashable items
        
        if self.item_rule:
            for i, item in enumerate(value):
                result = self.item_rule.validate(item, f"{field_name}[{i}]")
                if not result.valid:
                    errors.extend(result.errors)
                sanitized.append(result.sanitized_data if result.sanitized_data is not None else item)
        else:
            sanitized = value
        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            sanitized_data=sanitized,
        )


class DictRule(ValidationRule):
    """Validates dictionary values."""
    
    def __init__(
        self,
        schema: Optional[Dict[str, ValidationRule]] = None,
        allow_extra: bool = True,
        remove_extra: bool = False,
    ):
        self.schema = schema or {}
        self.allow_extra = allow_extra
        self.remove_extra = remove_extra
    
    def validate(self, value: Any, field_name: str = "") -> ValidationResult:
        if value is None:
            return ValidationResult(valid=True, sanitized_data=value)
        
        if not isinstance(value, dict):
            return ValidationResult(
                valid=False,
                errors=[ValidationError(f"Expected dict, got {type(value).__name__}", field_name, value)],
            )
        
        errors = []
        sanitized = {}
        
        # Validate schema fields
        for key, rule in self.schema.items():
            field_value = value.get(key)
            result = rule.validate(field_value, f"{field_name}.{key}" if field_name else key)
            if not result.valid:
                errors.extend(result.errors)
            sanitized[key] = result.sanitized_data if result.sanitized_data is not None else field_value
        
        # Handle extra fields
        extra_keys = set(value.keys()) - set(self.schema.keys())
        if extra_keys:
            if not self.allow_extra:
                errors.append(ValidationError(f"Unexpected fields: {extra_keys}", field_name, value))
            elif not self.remove_extra:
                for key in extra_keys:
                    sanitized[key] = value[key]
        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            sanitized_data=sanitized,
        )


class CustomRule(ValidationRule):
    """Custom validation using a function."""
    
    def __init__(
        self,
        validator: Callable[[Any], bool],
        message: str = "Validation failed",
        sanitizer: Optional[Callable[[Any], Any]] = None,
    ):
        self.validator = validator
        self.message = message
        self.sanitizer = sanitizer
    
    def validate(self, value: Any, field_name: str = "") -> ValidationResult:
        try:
            if not self.validator(value):
                return ValidationResult(
                    valid=False,
                    errors=[ValidationError(self.message, field_name, value)],
                )
        except Exception as e:
            return ValidationResult(
                valid=False,
                errors=[ValidationError(str(e), field_name, value)],
            )
        
        sanitized = self.sanitizer(value) if self.sanitizer else value
        return ValidationResult(valid=True, sanitized_data=sanitized)


class Validator:
    """
    Composite validator for multiple fields.
    """
    
    def __init__(self):
        self._rules: Dict[str, List[ValidationRule]] = {}
        self._required_fields: Set[str] = set()
    
    def add_rule(self, field: str, rule: ValidationRule) -> 'Validator':
        """Add a validation rule for a field."""
        if field not in self._rules:
            self._rules[field] = []
        self._rules[field].append(rule)
        return self
    
    def require(self, *fields: str) -> 'Validator':
        """Mark fields as required."""
        self._required_fields.update(fields)
        return self
    
    def validate(self, data: Dict[str, Any]) -> ValidationResult:
        """
        Validate data against all rules.
        
        Args:
            data: Dictionary to validate
            
        Returns:
            ValidationResult with combined errors
        """
        all_errors = []
        sanitized = {}
        
        # Check required fields
        for field in self._required_fields:
            if field not in data or data[field] is None:
                all_errors.append(ValidationError(f"Field is required", field))
        
        # Validate each field
        for field, rules in self._rules.items():
            value = data.get(field)
            
            for rule in rules:
                result = rule.validate(value, field)
                if not result.valid:
                    all_errors.extend(result.errors)
                else:
                    value = result.sanitized_data
            
            sanitized[field] = value
        
        # Include non-validated fields
        for key, value in data.items():
            if key not in sanitized:
                sanitized[key] = value
        
        return ValidationResult(
            valid=len(all_errors) == 0,
            errors=all_errors,
            sanitized_data=sanitized,
        )


class Schema:
    """
    Declarative schema for validation.
    """
    
    def __init__(self, fields: Dict[str, Any]):
        """
        Initialize schema.
        
        Args:
            fields: Dictionary mapping field names to types or rules
        """
        self._fields = fields
        self._validator = self._build_validator()
    
    def _build_validator(self) -> Validator:
        """Build validator from schema definition."""
        validator = Validator()
        
        for field, spec in self._fields.items():
            if isinstance(spec, ValidationRule):
                validator.add_rule(field, spec)
            elif isinstance(spec, type):
                validator.add_rule(field, TypeRule(spec))
            elif isinstance(spec, dict):
                # Nested schema
                validator.add_rule(field, DictRule(
                    schema={k: TypeRule(v) if isinstance(v, type) else v 
                            for k, v in spec.items()}
                ))
        
        return validator
    
    def validate(self, data: Dict[str, Any]) -> ValidationResult:
        """Validate data against schema."""
        return self._validator.validate(data)


def validate_input(
    schema: Union[Schema, Dict[str, Any], Type],
    raise_on_error: bool = True,
) -> Callable:
    """
    Decorator for input validation.
    
    Example:
        @validate_input({"name": StringRule(min_length=1)})
        async def create_user(data: dict) -> dict:
            return {"id": 1, "name": data["name"]}
    """
    def decorator(func: Callable) -> Callable:
        if isinstance(schema, Schema):
            validator = schema
        elif isinstance(schema, dict):
            validator = Schema(schema)
        else:
            validator = Schema({"data": TypeRule(schema)})
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Find the data argument
            data = kwargs.get("data") or (args[0] if args else {})
            
            result = validator.validate(data)
            if not result.valid:
                if raise_on_error:
                    raise ValidationError(
                        "Input validation failed",
                        errors=result.errors,
                    )
                return result
            
            # Replace with sanitized data
            if "data" in kwargs:
                kwargs["data"] = result.sanitized_data
            elif args:
                args = (result.sanitized_data,) + args[1:]
            
            return await func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            data = kwargs.get("data") or (args[0] if args else {})
            
            result = validator.validate(data)
            if not result.valid:
                if raise_on_error:
                    raise ValidationError(
                        "Input validation failed",
                        errors=result.errors,
                    )
                return result
            
            if "data" in kwargs:
                kwargs["data"] = result.sanitized_data
            elif args:
                args = (result.sanitized_data,) + args[1:]
            
            return func(*args, **kwargs)
        
        import asyncio
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


def validate_output(
    schema: Union[Schema, Dict[str, Any]],
    raise_on_error: bool = True,
) -> Callable:
    """
    Decorator for output validation.
    
    Example:
        @validate_output({"id": TypeRule(int), "name": StringRule()})
        async def get_user(user_id: int) -> dict:
            return {"id": user_id, "name": "John"}
    """
    def decorator(func: Callable) -> Callable:
        if isinstance(schema, Schema):
            validator = schema
        else:
            validator = Schema(schema)
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            
            validation = validator.validate(result)
            if not validation.valid:
                if raise_on_error:
                    raise ValidationError(
                        "Output validation failed",
                        errors=validation.errors,
                    )
                logger.error(f"Output validation failed: {validation.errors}")
            
            return validation.sanitized_data or result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            
            validation = validator.validate(result)
            if not validation.valid:
                if raise_on_error:
                    raise ValidationError(
                        "Output validation failed",
                        errors=validation.errors,
                    )
                logger.error(f"Output validation failed: {validation.errors}")
            
            return validation.sanitized_data or result
        
        import asyncio
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


__all__ = [
    # Exceptions
    "ValidationError",
    # Data classes
    "ValidationResult",
    # Rules
    "ValidationRule",
    "RequiredRule",
    "TypeRule",
    "StringRule",
    "RangeRule",
    "EmailRule",
    "URLRule",
    "EnumRule",
    "ListRule",
    "DictRule",
    "CustomRule",
    # Validators
    "Validator",
    "Schema",
    # Decorators
    "validate_input",
    "validate_output",
]
