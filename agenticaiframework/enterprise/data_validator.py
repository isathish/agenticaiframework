"""
Enterprise Data Validator Module.

Schema validation, data sanitization, transformation,
and validation rules engine.

Example:
    # Create validator
    validator = create_validator()
    
    # Define schema
    schema = validator.schema({
        "name": {"type": "string", "required": True, "min_length": 1},
        "email": {"type": "string", "pattern": r"^[\w.-]+@[\w.-]+\.\w+$"},
        "age": {"type": "integer", "min": 0, "max": 150},
    })
    
    # Validate data
    result = await validator.validate(
        data={"name": "John", "email": "john@example.com", "age": 30},
        schema=schema,
    )
    
    if result.is_valid:
        print("Data is valid")
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Pattern,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
)

T = TypeVar('T')

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Validation error."""
    pass


class SchemaError(Exception):
    """Schema error."""
    pass


class ValidationType(str, Enum):
    """Validation type."""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"
    DATE = "date"
    DATETIME = "datetime"
    EMAIL = "email"
    URL = "url"
    UUID = "uuid"
    ANY = "any"


class SanitizeMode(str, Enum):
    """Sanitize mode."""
    NONE = "none"
    TRIM = "trim"
    LOWER = "lower"
    UPPER = "upper"
    STRIP_HTML = "strip_html"
    ESCAPE_HTML = "escape_html"


@dataclass
class FieldError:
    """Field validation error."""
    field: str = ""
    message: str = ""
    value: Any = None
    rule: str = ""
    path: str = ""


@dataclass
class ValidationResult:
    """Validation result."""
    is_valid: bool = True
    errors: List[FieldError] = field(default_factory=list)
    data: Any = None
    sanitized_data: Any = None
    duration: float = 0.0
    
    def add_error(
        self,
        field: str,
        message: str,
        value: Any = None,
        rule: str = "",
        path: str = "",
    ) -> None:
        """Add error."""
        self.errors.append(FieldError(
            field=field,
            message=message,
            value=value,
            rule=rule,
            path=path or field,
        ))
        self.is_valid = False
    
    def merge(self, other: ValidationResult) -> None:
        """Merge another result."""
        self.errors.extend(other.errors)
        if not other.is_valid:
            self.is_valid = False


@dataclass
class FieldSchema:
    """Field schema."""
    type: ValidationType = ValidationType.ANY
    required: bool = False
    nullable: bool = True
    default: Any = None
    
    # String constraints
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    pattern: Optional[str] = None
    
    # Numeric constraints
    min: Optional[float] = None
    max: Optional[float] = None
    
    # Array constraints
    min_items: Optional[int] = None
    max_items: Optional[int] = None
    items: Optional[Dict[str, Any]] = None
    unique: bool = False
    
    # Object constraints
    properties: Optional[Dict[str, Any]] = None
    
    # Enum
    enum: Optional[List[Any]] = None
    
    # Custom
    validator: Optional[Callable] = None
    sanitizer: Optional[Callable] = None
    sanitize_mode: SanitizeMode = SanitizeMode.NONE
    
    # Metadata
    description: str = ""
    example: Any = None


@dataclass
class Schema:
    """Validation schema."""
    fields: Dict[str, FieldSchema] = field(default_factory=dict)
    strict: bool = False  # Fail on unknown fields
    allow_extra: bool = True
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Schema:
        """Create from dictionary."""
        fields = {}
        
        for name, config in data.items():
            if isinstance(config, dict):
                field_type = config.get("type", "any")
                if isinstance(field_type, str):
                    field_type = ValidationType(field_type)
                
                fields[name] = FieldSchema(
                    type=field_type,
                    required=config.get("required", False),
                    nullable=config.get("nullable", True),
                    default=config.get("default"),
                    min_length=config.get("min_length"),
                    max_length=config.get("max_length"),
                    pattern=config.get("pattern"),
                    min=config.get("min"),
                    max=config.get("max"),
                    min_items=config.get("min_items"),
                    max_items=config.get("max_items"),
                    items=config.get("items"),
                    unique=config.get("unique", False),
                    properties=config.get("properties"),
                    enum=config.get("enum"),
                    description=config.get("description", ""),
                    example=config.get("example"),
                )
        
        return cls(fields=fields)


# Built-in validators
class BuiltinValidators:
    """Built-in validators."""
    
    EMAIL_PATTERN = re.compile(r'^[\w\.-]+@[\w\.-]+\.\w+$')
    URL_PATTERN = re.compile(
        r'^https?://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
        r'localhost|'
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)$',
        re.IGNORECASE
    )
    UUID_PATTERN = re.compile(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
        re.IGNORECASE
    )
    
    @classmethod
    def is_email(cls, value: str) -> bool:
        """Check if email."""
        return bool(cls.EMAIL_PATTERN.match(value))
    
    @classmethod
    def is_url(cls, value: str) -> bool:
        """Check if URL."""
        return bool(cls.URL_PATTERN.match(value))
    
    @classmethod
    def is_uuid(cls, value: str) -> bool:
        """Check if UUID."""
        return bool(cls.UUID_PATTERN.match(value))


# Sanitizers
class Sanitizers:
    """Built-in sanitizers."""
    
    HTML_TAGS = re.compile(r'<[^>]+>')
    
    @classmethod
    def trim(cls, value: str) -> str:
        """Trim whitespace."""
        return value.strip() if isinstance(value, str) else value
    
    @classmethod
    def lower(cls, value: str) -> str:
        """Convert to lowercase."""
        return value.lower() if isinstance(value, str) else value
    
    @classmethod
    def upper(cls, value: str) -> str:
        """Convert to uppercase."""
        return value.upper() if isinstance(value, str) else value
    
    @classmethod
    def strip_html(cls, value: str) -> str:
        """Strip HTML tags."""
        if isinstance(value, str):
            return cls.HTML_TAGS.sub('', value)
        return value
    
    @classmethod
    def escape_html(cls, value: str) -> str:
        """Escape HTML entities."""
        if isinstance(value, str):
            return (
                value
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&#x27;')
            )
        return value
    
    @classmethod
    def apply(cls, value: Any, mode: SanitizeMode) -> Any:
        """Apply sanitization."""
        if mode == SanitizeMode.TRIM:
            return cls.trim(value)
        elif mode == SanitizeMode.LOWER:
            return cls.lower(value)
        elif mode == SanitizeMode.UPPER:
            return cls.upper(value)
        elif mode == SanitizeMode.STRIP_HTML:
            return cls.strip_html(value)
        elif mode == SanitizeMode.ESCAPE_HTML:
            return cls.escape_html(value)
        return value


# Type coercer
class TypeCoercer:
    """Type coercion."""
    
    @classmethod
    def coerce(cls, value: Any, target_type: ValidationType) -> Any:
        """Coerce value to target type."""
        if value is None:
            return None
        
        try:
            if target_type == ValidationType.STRING:
                return str(value)
            
            elif target_type == ValidationType.INTEGER:
                if isinstance(value, str):
                    return int(float(value))
                return int(value)
            
            elif target_type == ValidationType.FLOAT:
                return float(value)
            
            elif target_type == ValidationType.NUMBER:
                if isinstance(value, (int, float, Decimal)):
                    return value
                return float(value)
            
            elif target_type == ValidationType.BOOLEAN:
                if isinstance(value, bool):
                    return value
                if isinstance(value, str):
                    return value.lower() in ('true', '1', 'yes', 'on')
                return bool(value)
            
            elif target_type == ValidationType.ARRAY:
                if isinstance(value, (list, tuple)):
                    return list(value)
                return [value]
            
            elif target_type == ValidationType.DATE:
                if isinstance(value, date):
                    return value
                if isinstance(value, str):
                    return datetime.fromisoformat(value).date()
                return value
            
            elif target_type == ValidationType.DATETIME:
                if isinstance(value, datetime):
                    return value
                if isinstance(value, str):
                    return datetime.fromisoformat(value)
                return value
            
        except (ValueError, TypeError):
            pass
        
        return value


# Field validator
class FieldValidator:
    """Field validator."""
    
    def validate(
        self,
        value: Any,
        field_schema: FieldSchema,
        field_name: str,
        path: str = "",
    ) -> ValidationResult:
        """Validate field value."""
        result = ValidationResult()
        path = path or field_name
        
        # Check required
        if value is None:
            if field_schema.required:
                result.add_error(field_name, "Field is required", None, "required", path)
                return result
            elif not field_schema.nullable:
                result.add_error(field_name, "Field cannot be null", None, "nullable", path)
                return result
            return result
        
        # Type validation
        type_valid = self._validate_type(value, field_schema.type, field_name, path, result)
        
        if not type_valid:
            return result
        
        # String validations
        if field_schema.type == ValidationType.STRING:
            self._validate_string(value, field_schema, field_name, path, result)
        
        # Numeric validations
        elif field_schema.type in (ValidationType.INTEGER, ValidationType.FLOAT, ValidationType.NUMBER):
            self._validate_number(value, field_schema, field_name, path, result)
        
        # Array validations
        elif field_schema.type == ValidationType.ARRAY:
            self._validate_array(value, field_schema, field_name, path, result)
        
        # Enum validation
        if field_schema.enum and value not in field_schema.enum:
            result.add_error(
                field_name,
                f"Value must be one of: {field_schema.enum}",
                value,
                "enum",
                path,
            )
        
        # Custom validator
        if field_schema.validator and result.is_valid:
            try:
                custom_result = field_schema.validator(value)
                if custom_result is False:
                    result.add_error(field_name, "Custom validation failed", value, "custom", path)
                elif isinstance(custom_result, str):
                    result.add_error(field_name, custom_result, value, "custom", path)
            except Exception as e:
                result.add_error(field_name, str(e), value, "custom", path)
        
        return result
    
    def _validate_type(
        self,
        value: Any,
        expected_type: ValidationType,
        field_name: str,
        path: str,
        result: ValidationResult,
    ) -> bool:
        """Validate type."""
        if expected_type == ValidationType.ANY:
            return True
        
        type_checks = {
            ValidationType.STRING: lambda v: isinstance(v, str),
            ValidationType.INTEGER: lambda v: isinstance(v, int) and not isinstance(v, bool),
            ValidationType.FLOAT: lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
            ValidationType.NUMBER: lambda v: isinstance(v, (int, float, Decimal)) and not isinstance(v, bool),
            ValidationType.BOOLEAN: lambda v: isinstance(v, bool),
            ValidationType.ARRAY: lambda v: isinstance(v, (list, tuple)),
            ValidationType.OBJECT: lambda v: isinstance(v, dict),
            ValidationType.EMAIL: lambda v: isinstance(v, str) and BuiltinValidators.is_email(v),
            ValidationType.URL: lambda v: isinstance(v, str) and BuiltinValidators.is_url(v),
            ValidationType.UUID: lambda v: isinstance(v, str) and BuiltinValidators.is_uuid(v),
            ValidationType.DATE: lambda v: isinstance(v, (date, str)),
            ValidationType.DATETIME: lambda v: isinstance(v, (datetime, str)),
        }
        
        checker = type_checks.get(expected_type)
        
        if checker and not checker(value):
            result.add_error(
                field_name,
                f"Expected type {expected_type.value}, got {type(value).__name__}",
                value,
                "type",
                path,
            )
            return False
        
        return True
    
    def _validate_string(
        self,
        value: str,
        schema: FieldSchema,
        field_name: str,
        path: str,
        result: ValidationResult,
    ) -> None:
        """Validate string."""
        if schema.min_length is not None and len(value) < schema.min_length:
            result.add_error(
                field_name,
                f"Length must be at least {schema.min_length}",
                value,
                "min_length",
                path,
            )
        
        if schema.max_length is not None and len(value) > schema.max_length:
            result.add_error(
                field_name,
                f"Length must be at most {schema.max_length}",
                value,
                "max_length",
                path,
            )
        
        if schema.pattern:
            if not re.match(schema.pattern, value):
                result.add_error(
                    field_name,
                    f"Value does not match pattern: {schema.pattern}",
                    value,
                    "pattern",
                    path,
                )
    
    def _validate_number(
        self,
        value: Union[int, float],
        schema: FieldSchema,
        field_name: str,
        path: str,
        result: ValidationResult,
    ) -> None:
        """Validate number."""
        if schema.min is not None and value < schema.min:
            result.add_error(
                field_name,
                f"Value must be at least {schema.min}",
                value,
                "min",
                path,
            )
        
        if schema.max is not None and value > schema.max:
            result.add_error(
                field_name,
                f"Value must be at most {schema.max}",
                value,
                "max",
                path,
            )
    
    def _validate_array(
        self,
        value: List[Any],
        schema: FieldSchema,
        field_name: str,
        path: str,
        result: ValidationResult,
    ) -> None:
        """Validate array."""
        if schema.min_items is not None and len(value) < schema.min_items:
            result.add_error(
                field_name,
                f"Array must have at least {schema.min_items} items",
                value,
                "min_items",
                path,
            )
        
        if schema.max_items is not None and len(value) > schema.max_items:
            result.add_error(
                field_name,
                f"Array must have at most {schema.max_items} items",
                value,
                "max_items",
                path,
            )
        
        if schema.unique:
            seen = set()
            for i, item in enumerate(value):
                key = str(item) if not isinstance(item, (str, int, float, bool)) else item
                if key in seen:
                    result.add_error(
                        field_name,
                        f"Duplicate item at index {i}",
                        item,
                        "unique",
                        f"{path}[{i}]",
                    )
                seen.add(key)


# Data validator
class DataValidator:
    """Data validator."""
    
    def __init__(self):
        self._field_validator = FieldValidator()
        self._schemas: Dict[str, Schema] = {}
    
    def schema(self, definition: Dict[str, Any]) -> Schema:
        """Create schema from definition."""
        return Schema.from_dict(definition)
    
    def register_schema(self, name: str, schema: Schema) -> None:
        """Register named schema."""
        self._schemas[name] = schema
    
    def get_schema(self, name: str) -> Optional[Schema]:
        """Get registered schema."""
        return self._schemas.get(name)
    
    async def validate(
        self,
        data: Dict[str, Any],
        schema: Union[str, Schema, Dict[str, Any]],
        coerce: bool = False,
        sanitize: bool = True,
    ) -> ValidationResult:
        """Validate data against schema."""
        start = time.time()
        result = ValidationResult(data=data)
        
        # Resolve schema
        if isinstance(schema, str):
            schema = self._schemas.get(schema)
            if not schema:
                result.add_error("_schema", f"Schema not found: {schema}")
                return result
        elif isinstance(schema, dict):
            schema = Schema.from_dict(schema)
        
        sanitized = {}
        
        # Validate each field
        for field_name, field_schema in schema.fields.items():
            value = data.get(field_name)
            
            # Apply default
            if value is None and field_schema.default is not None:
                value = field_schema.default
            
            # Coerce type
            if coerce and value is not None:
                value = TypeCoercer.coerce(value, field_schema.type)
            
            # Sanitize
            if sanitize and value is not None:
                if field_schema.sanitizer:
                    value = field_schema.sanitizer(value)
                elif field_schema.sanitize_mode != SanitizeMode.NONE:
                    value = Sanitizers.apply(value, field_schema.sanitize_mode)
            
            # Validate
            field_result = self._field_validator.validate(
                value, field_schema, field_name
            )
            
            result.merge(field_result)
            sanitized[field_name] = value
        
        # Check for unknown fields
        if schema.strict:
            for key in data:
                if key not in schema.fields:
                    result.add_error(key, "Unknown field", data[key], "strict")
        
        # Copy extra fields
        if schema.allow_extra:
            for key, value in data.items():
                if key not in sanitized:
                    sanitized[key] = value
        
        result.sanitized_data = sanitized
        result.duration = time.time() - start
        
        return result
    
    async def validate_many(
        self,
        items: List[Dict[str, Any]],
        schema: Union[str, Schema, Dict[str, Any]],
        **kwargs,
    ) -> List[ValidationResult]:
        """Validate multiple items."""
        results = []
        
        for item in items:
            result = await self.validate(item, schema, **kwargs)
            results.append(result)
        
        return results
    
    def validate_sync(
        self,
        data: Dict[str, Any],
        schema: Union[str, Schema, Dict[str, Any]],
        **kwargs,
    ) -> ValidationResult:
        """Synchronous validation."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.validate(data, schema, **kwargs))
        finally:
            loop.close()


# Validation decorator
def validated(
    schema: Union[str, Schema, Dict[str, Any]],
    validator: Optional[DataValidator] = None,
    arg_name: str = "data",
):
    """Decorator for validating function arguments."""
    def decorator(func: Callable) -> Callable:
        async def async_wrapper(*args, **kwargs):
            val = validator or DataValidator()
            data = kwargs.get(arg_name) or (args[0] if args else {})
            
            result = await val.validate(data, schema)
            
            if not result.is_valid:
                errors = "; ".join(f"{e.field}: {e.message}" for e in result.errors)
                raise ValidationError(f"Validation failed: {errors}")
            
            # Replace with sanitized data
            if arg_name in kwargs:
                kwargs[arg_name] = result.sanitized_data
            
            return await func(*args, **kwargs)
        
        def sync_wrapper(*args, **kwargs):
            val = validator or DataValidator()
            data = kwargs.get(arg_name) or (args[0] if args else {})
            
            result = val.validate_sync(data, schema)
            
            if not result.is_valid:
                errors = "; ".join(f"{e.field}: {e.message}" for e in result.errors)
                raise ValidationError(f"Validation failed: {errors}")
            
            if arg_name in kwargs:
                kwargs[arg_name] = result.sanitized_data
            
            return func(*args, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


# Factory functions
def create_validator() -> DataValidator:
    """Create data validator."""
    return DataValidator()


def create_schema(definition: Dict[str, Any]) -> Schema:
    """Create validation schema."""
    return Schema.from_dict(definition)


def create_field_schema(
    type: Union[str, ValidationType] = ValidationType.ANY,
    **kwargs,
) -> FieldSchema:
    """Create field schema."""
    if isinstance(type, str):
        type = ValidationType(type)
    return FieldSchema(type=type, **kwargs)


__all__ = [
    # Exceptions
    "ValidationError",
    "SchemaError",
    # Enums
    "ValidationType",
    "SanitizeMode",
    # Data classes
    "FieldError",
    "ValidationResult",
    "FieldSchema",
    "Schema",
    # Validators
    "BuiltinValidators",
    "Sanitizers",
    "TypeCoercer",
    "FieldValidator",
    "DataValidator",
    # Decorators
    "validated",
    # Factory functions
    "create_validator",
    "create_schema",
    "create_field_schema",
]
