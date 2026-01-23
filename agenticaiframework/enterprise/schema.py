"""
Enterprise Schema Module.

Provides schema validation, type checking, and data
structure verification capabilities.

Example:
    # Define schema
    UserSchema = Schema({
        "name": String(required=True, min_length=1),
        "age": Integer(min=0, max=150),
        "email": Email(required=True),
        "tags": Array(String()),
    })
    
    # Validate data
    result = UserSchema.validate(data)
    if result.is_valid:
        process(result.data)
    else:
        handle_errors(result.errors)
    
    # With decorator
    @validate_schema(UserSchema)
    def create_user(data: dict) -> User:
        return User(**data)
    
    # Schema from dataclass
    @dataclass_schema
    class User:
        name: str
        age: int = 0
"""

from __future__ import annotations

import re
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, fields as dataclass_fields
from datetime import datetime, date
from enum import Enum
from functools import wraps
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
    get_type_hints,
)

logger = logging.getLogger(__name__)

T = TypeVar('T')


class SchemaError(Exception):
    """Schema error."""
    pass


class ValidationError(SchemaError):
    """Validation error."""
    
    def __init__(
        self,
        message: str,
        path: Optional[str] = None,
        value: Any = None,
    ):
        self.message = message
        self.path = path
        self.value = value
        super().__init__(message)


class SchemaType(str, Enum):
    """Schema types."""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"
    ANY = "any"
    NULL = "null"
    DATE = "date"
    DATETIME = "datetime"
    EMAIL = "email"
    URL = "url"
    UUID = "uuid"
    ENUM = "enum"


@dataclass
class ValidationResult:
    """Validation result."""
    is_valid: bool
    data: Any = None
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def merge(self, other: "ValidationResult") -> "ValidationResult":
        """Merge with another result."""
        return ValidationResult(
            is_valid=self.is_valid and other.is_valid,
            data=other.data if other.is_valid else self.data,
            errors=self.errors + other.errors,
            warnings=self.warnings + other.warnings,
        )


@dataclass
class FieldInfo:
    """Field information."""
    name: str
    type: "SchemaField"
    required: bool = True
    default: Any = None
    description: Optional[str] = None


class SchemaField(ABC):
    """Abstract schema field."""
    
    def __init__(
        self,
        required: bool = False,
        default: Any = None,
        nullable: bool = False,
        description: Optional[str] = None,
    ):
        self.required = required
        self.default = default
        self.nullable = nullable
        self.description = description
    
    @abstractmethod
    def validate(
        self,
        value: Any,
        path: str = "",
    ) -> ValidationResult:
        """Validate value."""
        pass
    
    def _check_null(
        self,
        value: Any,
        path: str,
    ) -> Optional[ValidationResult]:
        """Check for null value."""
        if value is None:
            if self.nullable:
                return ValidationResult(is_valid=True, data=None)
            
            if self.required:
                return ValidationResult(
                    is_valid=False,
                    errors=[ValidationError(
                        f"Required field is null",
                        path=path,
                        value=value,
                    )],
                )
            
            return ValidationResult(is_valid=True, data=self.default)
        
        return None


class String(SchemaField):
    """String schema field."""
    
    def __init__(
        self,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
        pattern: Optional[str] = None,
        choices: Optional[List[str]] = None,
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self.min_length = min_length
        self.max_length = max_length
        self.pattern = re.compile(pattern) if pattern else None
        self.choices = choices
    
    def validate(
        self,
        value: Any,
        path: str = "",
    ) -> ValidationResult:
        """Validate string."""
        null_result = self._check_null(value, path)
        if null_result:
            return null_result
        
        if not isinstance(value, str):
            return ValidationResult(
                is_valid=False,
                errors=[ValidationError(
                    f"Expected string, got {type(value).__name__}",
                    path=path,
                    value=value,
                )],
            )
        
        errors = []
        
        if self.min_length is not None and len(value) < self.min_length:
            errors.append(ValidationError(
                f"String length {len(value)} is less than minimum {self.min_length}",
                path=path,
                value=value,
            ))
        
        if self.max_length is not None and len(value) > self.max_length:
            errors.append(ValidationError(
                f"String length {len(value)} exceeds maximum {self.max_length}",
                path=path,
                value=value,
            ))
        
        if self.pattern and not self.pattern.match(value):
            errors.append(ValidationError(
                f"String does not match pattern",
                path=path,
                value=value,
            ))
        
        if self.choices and value not in self.choices:
            errors.append(ValidationError(
                f"Value not in allowed choices: {self.choices}",
                path=path,
                value=value,
            ))
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            data=value,
            errors=errors,
        )


class Integer(SchemaField):
    """Integer schema field."""
    
    def __init__(
        self,
        min: Optional[int] = None,
        max: Optional[int] = None,
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self.min = min
        self.max = max
    
    def validate(
        self,
        value: Any,
        path: str = "",
    ) -> ValidationResult:
        """Validate integer."""
        null_result = self._check_null(value, path)
        if null_result:
            return null_result
        
        # Allow string conversion
        if isinstance(value, str):
            try:
                value = int(value)
            except ValueError:
                return ValidationResult(
                    is_valid=False,
                    errors=[ValidationError(
                        f"Cannot convert '{value}' to integer",
                        path=path,
                        value=value,
                    )],
                )
        
        if not isinstance(value, int) or isinstance(value, bool):
            return ValidationResult(
                is_valid=False,
                errors=[ValidationError(
                    f"Expected integer, got {type(value).__name__}",
                    path=path,
                    value=value,
                )],
            )
        
        errors = []
        
        if self.min is not None and value < self.min:
            errors.append(ValidationError(
                f"Value {value} is less than minimum {self.min}",
                path=path,
                value=value,
            ))
        
        if self.max is not None and value > self.max:
            errors.append(ValidationError(
                f"Value {value} exceeds maximum {self.max}",
                path=path,
                value=value,
            ))
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            data=value,
            errors=errors,
        )


class Float(SchemaField):
    """Float schema field."""
    
    def __init__(
        self,
        min: Optional[float] = None,
        max: Optional[float] = None,
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self.min = min
        self.max = max
    
    def validate(
        self,
        value: Any,
        path: str = "",
    ) -> ValidationResult:
        """Validate float."""
        null_result = self._check_null(value, path)
        if null_result:
            return null_result
        
        # Allow string/int conversion
        if isinstance(value, (str, int)) and not isinstance(value, bool):
            try:
                value = float(value)
            except ValueError:
                return ValidationResult(
                    is_valid=False,
                    errors=[ValidationError(
                        f"Cannot convert '{value}' to float",
                        path=path,
                        value=value,
                    )],
                )
        
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return ValidationResult(
                is_valid=False,
                errors=[ValidationError(
                    f"Expected float, got {type(value).__name__}",
                    path=path,
                    value=value,
                )],
            )
        
        errors = []
        
        if self.min is not None and value < self.min:
            errors.append(ValidationError(
                f"Value {value} is less than minimum {self.min}",
                path=path,
                value=value,
            ))
        
        if self.max is not None and value > self.max:
            errors.append(ValidationError(
                f"Value {value} exceeds maximum {self.max}",
                path=path,
                value=value,
            ))
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            data=float(value),
            errors=errors,
        )


class Boolean(SchemaField):
    """Boolean schema field."""
    
    def validate(
        self,
        value: Any,
        path: str = "",
    ) -> ValidationResult:
        """Validate boolean."""
        null_result = self._check_null(value, path)
        if null_result:
            return null_result
        
        # Allow string conversion
        if isinstance(value, str):
            if value.lower() in ('true', '1', 'yes', 'on'):
                value = True
            elif value.lower() in ('false', '0', 'no', 'off'):
                value = False
            else:
                return ValidationResult(
                    is_valid=False,
                    errors=[ValidationError(
                        f"Cannot convert '{value}' to boolean",
                        path=path,
                        value=value,
                    )],
                )
        
        if not isinstance(value, bool):
            return ValidationResult(
                is_valid=False,
                errors=[ValidationError(
                    f"Expected boolean, got {type(value).__name__}",
                    path=path,
                    value=value,
                )],
            )
        
        return ValidationResult(is_valid=True, data=value)


class Array(SchemaField):
    """Array schema field."""
    
    def __init__(
        self,
        items: Optional[SchemaField] = None,
        min_items: Optional[int] = None,
        max_items: Optional[int] = None,
        unique: bool = False,
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self.items = items
        self.min_items = min_items
        self.max_items = max_items
        self.unique = unique
    
    def validate(
        self,
        value: Any,
        path: str = "",
    ) -> ValidationResult:
        """Validate array."""
        null_result = self._check_null(value, path)
        if null_result:
            return null_result
        
        if not isinstance(value, list):
            return ValidationResult(
                is_valid=False,
                errors=[ValidationError(
                    f"Expected array, got {type(value).__name__}",
                    path=path,
                    value=value,
                )],
            )
        
        errors = []
        validated_items = []
        
        if self.min_items is not None and len(value) < self.min_items:
            errors.append(ValidationError(
                f"Array has {len(value)} items, minimum is {self.min_items}",
                path=path,
                value=value,
            ))
        
        if self.max_items is not None and len(value) > self.max_items:
            errors.append(ValidationError(
                f"Array has {len(value)} items, maximum is {self.max_items}",
                path=path,
                value=value,
            ))
        
        if self.unique and len(value) != len(set(str(v) for v in value)):
            errors.append(ValidationError(
                "Array items must be unique",
                path=path,
                value=value,
            ))
        
        # Validate each item
        if self.items:
            for i, item in enumerate(value):
                item_path = f"{path}[{i}]"
                result = self.items.validate(item, item_path)
                
                if not result.is_valid:
                    errors.extend(result.errors)
                else:
                    validated_items.append(result.data)
        else:
            validated_items = value
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            data=validated_items,
            errors=errors,
        )


class Object(SchemaField):
    """Object schema field."""
    
    def __init__(
        self,
        properties: Optional[Dict[str, SchemaField]] = None,
        additional_properties: bool = True,
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self.properties = properties or {}
        self.additional_properties = additional_properties
    
    def validate(
        self,
        value: Any,
        path: str = "",
    ) -> ValidationResult:
        """Validate object."""
        null_result = self._check_null(value, path)
        if null_result:
            return null_result
        
        if not isinstance(value, dict):
            return ValidationResult(
                is_valid=False,
                errors=[ValidationError(
                    f"Expected object, got {type(value).__name__}",
                    path=path,
                    value=value,
                )],
            )
        
        errors = []
        validated_data = {}
        
        # Validate defined properties
        for prop_name, prop_schema in self.properties.items():
            prop_path = f"{path}.{prop_name}" if path else prop_name
            prop_value = value.get(prop_name)
            
            if prop_value is None and prop_name not in value:
                if prop_schema.required:
                    errors.append(ValidationError(
                        f"Missing required property: {prop_name}",
                        path=prop_path,
                    ))
                elif prop_schema.default is not None:
                    validated_data[prop_name] = prop_schema.default
            else:
                result = prop_schema.validate(prop_value, prop_path)
                
                if not result.is_valid:
                    errors.extend(result.errors)
                else:
                    validated_data[prop_name] = result.data
        
        # Handle additional properties
        for key in value:
            if key not in self.properties:
                if not self.additional_properties:
                    errors.append(ValidationError(
                        f"Additional property not allowed: {key}",
                        path=f"{path}.{key}" if path else key,
                    ))
                else:
                    validated_data[key] = value[key]
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            data=validated_data,
            errors=errors,
        )


class Email(String):
    """Email schema field."""
    
    EMAIL_PATTERN = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    def __init__(self, **kwargs: Any):
        super().__init__(pattern=self.EMAIL_PATTERN, **kwargs)


class URL(String):
    """URL schema field."""
    
    URL_PATTERN = r'^https?://[^\s/$.?#].[^\s]*$'
    
    def __init__(self, **kwargs: Any):
        super().__init__(pattern=self.URL_PATTERN, **kwargs)


class UUID(String):
    """UUID schema field."""
    
    UUID_PATTERN = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    
    def __init__(self, **kwargs: Any):
        super().__init__(pattern=self.UUID_PATTERN, **kwargs)


class DateTime(SchemaField):
    """DateTime schema field."""
    
    def __init__(
        self,
        format: str = "%Y-%m-%dT%H:%M:%S",
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self.format = format
    
    def validate(
        self,
        value: Any,
        path: str = "",
    ) -> ValidationResult:
        """Validate datetime."""
        null_result = self._check_null(value, path)
        if null_result:
            return null_result
        
        if isinstance(value, datetime):
            return ValidationResult(is_valid=True, data=value)
        
        if isinstance(value, str):
            try:
                parsed = datetime.strptime(value, self.format)
                return ValidationResult(is_valid=True, data=parsed)
            except ValueError:
                return ValidationResult(
                    is_valid=False,
                    errors=[ValidationError(
                        f"Invalid datetime format, expected: {self.format}",
                        path=path,
                        value=value,
                    )],
                )
        
        return ValidationResult(
            is_valid=False,
            errors=[ValidationError(
                f"Expected datetime, got {type(value).__name__}",
                path=path,
                value=value,
            )],
        )


class Enum_(SchemaField):
    """Enum schema field."""
    
    def __init__(
        self,
        values: List[Any],
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self.values = values
    
    def validate(
        self,
        value: Any,
        path: str = "",
    ) -> ValidationResult:
        """Validate enum value."""
        null_result = self._check_null(value, path)
        if null_result:
            return null_result
        
        if value not in self.values:
            return ValidationResult(
                is_valid=False,
                errors=[ValidationError(
                    f"Value must be one of: {self.values}",
                    path=path,
                    value=value,
                )],
            )
        
        return ValidationResult(is_valid=True, data=value)


class Any_(SchemaField):
    """Any type schema field."""
    
    def validate(
        self,
        value: Any,
        path: str = "",
    ) -> ValidationResult:
        """Accept any value."""
        return ValidationResult(is_valid=True, data=value)


class Schema:
    """
    Main schema class for validating data structures.
    """
    
    def __init__(
        self,
        properties: Dict[str, SchemaField],
        additional_properties: bool = True,
        strict: bool = False,
    ):
        self._properties = properties
        self._additional_properties = additional_properties
        self._strict = strict
        self._object = Object(
            properties=properties,
            additional_properties=additional_properties,
        )
    
    def validate(
        self,
        data: Any,
    ) -> ValidationResult:
        """Validate data against schema."""
        return self._object.validate(data)
    
    def is_valid(self, data: Any) -> bool:
        """Check if data is valid."""
        return self.validate(data).is_valid
    
    def validate_or_raise(self, data: Any) -> Any:
        """Validate and raise on error."""
        result = self.validate(data)
        
        if not result.is_valid:
            error_messages = [e.message for e in result.errors]
            raise SchemaError(f"Validation failed: {'; '.join(error_messages)}")
        
        return result.data
    
    @classmethod
    def from_dict(cls, schema_dict: Dict[str, Any]) -> "Schema":
        """Create schema from dictionary."""
        properties = {}
        
        for name, field_def in schema_dict.items():
            if isinstance(field_def, SchemaField):
                properties[name] = field_def
            elif isinstance(field_def, dict):
                properties[name] = cls._field_from_dict(field_def)
            elif isinstance(field_def, type):
                properties[name] = cls._field_from_type(field_def)
        
        return cls(properties)
    
    @classmethod
    def _field_from_dict(cls, field_def: Dict[str, Any]) -> SchemaField:
        """Create field from dictionary definition."""
        field_type = field_def.get('type', 'any')
        
        type_map = {
            'string': String,
            'integer': Integer,
            'float': Float,
            'boolean': Boolean,
            'array': Array,
            'object': Object,
            'email': Email,
            'url': URL,
            'uuid': UUID,
            'datetime': DateTime,
        }
        
        field_cls = type_map.get(field_type, Any_)
        
        # Extract kwargs
        kwargs = {k: v for k, v in field_def.items() if k != 'type'}
        
        return field_cls(**kwargs)
    
    @classmethod
    def _field_from_type(cls, python_type: type) -> SchemaField:
        """Create field from Python type."""
        type_map = {
            str: String,
            int: Integer,
            float: Float,
            bool: Boolean,
            list: Array,
            dict: Object,
            datetime: DateTime,
        }
        
        return type_map.get(python_type, Any_)()


class SchemaBuilder:
    """
    Fluent schema builder.
    """
    
    def __init__(self):
        self._properties: Dict[str, SchemaField] = {}
        self._additional = True
    
    def string(
        self,
        name: str,
        **kwargs: Any,
    ) -> "SchemaBuilder":
        """Add string field."""
        self._properties[name] = String(**kwargs)
        return self
    
    def integer(
        self,
        name: str,
        **kwargs: Any,
    ) -> "SchemaBuilder":
        """Add integer field."""
        self._properties[name] = Integer(**kwargs)
        return self
    
    def float(
        self,
        name: str,
        **kwargs: Any,
    ) -> "SchemaBuilder":
        """Add float field."""
        self._properties[name] = Float(**kwargs)
        return self
    
    def boolean(
        self,
        name: str,
        **kwargs: Any,
    ) -> "SchemaBuilder":
        """Add boolean field."""
        self._properties[name] = Boolean(**kwargs)
        return self
    
    def array(
        self,
        name: str,
        items: Optional[SchemaField] = None,
        **kwargs: Any,
    ) -> "SchemaBuilder":
        """Add array field."""
        self._properties[name] = Array(items=items, **kwargs)
        return self
    
    def object(
        self,
        name: str,
        properties: Optional[Dict[str, SchemaField]] = None,
        **kwargs: Any,
    ) -> "SchemaBuilder":
        """Add object field."""
        self._properties[name] = Object(properties=properties, **kwargs)
        return self
    
    def email(
        self,
        name: str,
        **kwargs: Any,
    ) -> "SchemaBuilder":
        """Add email field."""
        self._properties[name] = Email(**kwargs)
        return self
    
    def field(
        self,
        name: str,
        schema_field: SchemaField,
    ) -> "SchemaBuilder":
        """Add custom field."""
        self._properties[name] = schema_field
        return self
    
    def no_additional_properties(self) -> "SchemaBuilder":
        """Disallow additional properties."""
        self._additional = False
        return self
    
    def build(self) -> Schema:
        """Build the schema."""
        return Schema(self._properties, self._additional)


# Decorators
def validate_schema(
    schema: Schema,
    on_error: Optional[Callable] = None,
) -> Callable:
    """
    Decorator to validate function arguments.
    
    Example:
        @validate_schema(UserSchema)
        def create_user(data: dict) -> User:
            return User(**data)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(data: Any, *args: Any, **kwargs: Any) -> Any:
            result = schema.validate(data)
            
            if not result.is_valid:
                if on_error:
                    return on_error(result.errors)
                raise SchemaError(
                    f"Validation failed: {result.errors[0].message}"
                )
            
            return func(result.data, *args, **kwargs)
        
        return wrapper
    
    return decorator


def dataclass_schema(cls: Type[T]) -> Type[T]:
    """
    Decorator to create schema from dataclass.
    
    Example:
        @dataclass_schema
        @dataclass
        class User:
            name: str
            age: int = 0
    """
    type_map = {
        str: String,
        int: Integer,
        float: Float,
        bool: Boolean,
        list: Array,
        dict: Object,
        datetime: DateTime,
    }
    
    properties = {}
    
    for f in dataclass_fields(cls):
        field_type = f.type
        
        # Handle Optional
        if hasattr(field_type, '__origin__'):
            if field_type.__origin__ is Union:
                # Get non-None type
                args = [a for a in field_type.__args__ if a is not type(None)]
                if args:
                    field_type = args[0]
        
        schema_field_cls = type_map.get(field_type, Any_)
        
        required = f.default is f.default_factory
        default = f.default if f.default is not f.default_factory else None
        
        properties[f.name] = schema_field_cls(
            required=required,
            default=default,
        )
    
    cls._schema = Schema(properties)
    
    original_init = cls.__init__
    
    @wraps(original_init)
    def validated_init(self, **kwargs):
        result = cls._schema.validate(kwargs)
        if not result.is_valid:
            raise SchemaError(result.errors[0].message)
        return original_init(self, **result.data)
    
    cls.__init__ = validated_init
    
    return cls


# Factory functions
def create_schema(
    properties: Dict[str, SchemaField],
    **kwargs: Any,
) -> Schema:
    """Create a schema."""
    return Schema(properties, **kwargs)


def create_schema_builder() -> SchemaBuilder:
    """Create a schema builder."""
    return SchemaBuilder()


def schema_from_dict(schema_dict: Dict[str, Any]) -> Schema:
    """Create schema from dictionary."""
    return Schema.from_dict(schema_dict)


__all__ = [
    # Exceptions
    "SchemaError",
    "ValidationError",
    # Enums
    "SchemaType",
    # Data classes
    "ValidationResult",
    "FieldInfo",
    # Schema fields
    "SchemaField",
    "String",
    "Integer",
    "Float",
    "Boolean",
    "Array",
    "Object",
    "Email",
    "URL",
    "UUID",
    "DateTime",
    "Enum_",
    "Any_",
    # Core classes
    "Schema",
    "SchemaBuilder",
    # Decorators
    "validate_schema",
    "dataclass_schema",
    # Factory functions
    "create_schema",
    "create_schema_builder",
    "schema_from_dict",
]
