"""
Enterprise Transform Module.

Provides data transformation pipelines, field mapping,
and data conversion utilities.

Example:
    # Create transformer
    transformer = create_transformer()
    
    # Define transformation
    transformer.add_step("parse", parse_json)
    transformer.add_step("validate", validate_schema)
    transformer.add_step("enrich", add_metadata)
    
    result = await transformer.transform(raw_data)
    
    # With decorator
    @transform_pipeline(
        parse_json,
        validate_schema,
        normalize_fields,
    )
    async def process_data(data: dict) -> dict:
        return data
    
    # Field mapping
    mapper = create_field_mapper({
        "firstName": "first_name",
        "lastName": "last_name",
    })
    normalized = mapper.map(camel_case_data)
"""

from __future__ import annotations

import asyncio
import copy
import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from functools import wraps
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
)

logger = logging.getLogger(__name__)

T = TypeVar('T')
S = TypeVar('S')
R = TypeVar('R')


class TransformError(Exception):
    """Transform error."""
    pass


class ValidationError(TransformError):
    """Validation error during transform."""
    pass


class MappingError(TransformError):
    """Field mapping error."""
    pass


class TransformType(str, Enum):
    """Transform types."""
    MAP = "map"
    FILTER = "filter"
    REDUCE = "reduce"
    FLATTEN = "flatten"
    GROUP = "group"
    SORT = "sort"
    CUSTOM = "custom"


class CaseStyle(str, Enum):
    """Naming case styles."""
    SNAKE = "snake_case"
    CAMEL = "camelCase"
    PASCAL = "PascalCase"
    KEBAB = "kebab-case"
    UPPER_SNAKE = "UPPER_SNAKE_CASE"


@dataclass
class TransformStep:
    """A step in transformation pipeline."""
    name: str
    func: Callable
    transform_type: TransformType = TransformType.CUSTOM
    enabled: bool = True
    stop_on_error: bool = True
    timeout: Optional[float] = None


@dataclass
class TransformResult(Generic[T]):
    """Result of transformation."""
    data: T
    original: Any
    steps_executed: List[str] = field(default_factory=list)
    duration_ms: float = 0.0
    errors: List[str] = field(default_factory=list)


@dataclass
class FieldMapping:
    """Field mapping configuration."""
    source: str
    target: str
    transform: Optional[Callable] = None
    default: Any = None
    required: bool = False


@dataclass
class TransformStats:
    """Transform statistics."""
    total_transforms: int = 0
    successful: int = 0
    failed: int = 0
    avg_duration_ms: float = 0.0


class Transformer(ABC):
    """Abstract transformer."""
    
    @abstractmethod
    async def transform(self, data: Any) -> Any:
        """Transform data."""
        pass


class Pipeline:
    """
    Transformation pipeline with multiple steps.
    """
    
    def __init__(
        self,
        name: str = "pipeline",
        parallel: bool = False,
    ):
        self._name = name
        self._steps: List[TransformStep] = []
        self._parallel = parallel
        self._stats = TransformStats()
    
    def add_step(
        self,
        name: str,
        func: Callable,
        transform_type: TransformType = TransformType.CUSTOM,
        enabled: bool = True,
        **kwargs: Any,
    ) -> "Pipeline":
        """Add a step to the pipeline."""
        step = TransformStep(
            name=name,
            func=func,
            transform_type=transform_type,
            enabled=enabled,
            **kwargs,
        )
        self._steps.append(step)
        return self
    
    def insert_step(
        self,
        index: int,
        name: str,
        func: Callable,
        **kwargs: Any,
    ) -> "Pipeline":
        """Insert a step at specific index."""
        step = TransformStep(name=name, func=func, **kwargs)
        self._steps.insert(index, step)
        return self
    
    def remove_step(self, name: str) -> bool:
        """Remove a step by name."""
        for i, step in enumerate(self._steps):
            if step.name == name:
                self._steps.pop(i)
                return True
        return False
    
    async def transform(
        self,
        data: Any,
        context: Optional[Dict[str, Any]] = None,
    ) -> TransformResult:
        """Run transformation pipeline."""
        import time
        
        start = time.time()
        original = copy.deepcopy(data)
        current = data
        executed = []
        errors = []
        
        self._stats.total_transforms += 1
        
        for step in self._steps:
            if not step.enabled:
                continue
            
            try:
                if asyncio.iscoroutinefunction(step.func):
                    if step.timeout:
                        current = await asyncio.wait_for(
                            step.func(current),
                            timeout=step.timeout,
                        )
                    else:
                        current = await step.func(current)
                else:
                    current = step.func(current)
                
                executed.append(step.name)
                
            except Exception as e:
                errors.append(f"{step.name}: {str(e)}")
                
                if step.stop_on_error:
                    self._stats.failed += 1
                    raise TransformError(
                        f"Transform failed at step '{step.name}': {e}"
                    )
        
        duration_ms = (time.time() - start) * 1000
        
        self._stats.successful += 1
        self._stats.avg_duration_ms = (
            (self._stats.avg_duration_ms * (self._stats.successful - 1) + duration_ms)
            / self._stats.successful
        )
        
        return TransformResult(
            data=current,
            original=original,
            steps_executed=executed,
            duration_ms=duration_ms,
            errors=errors,
        )
    
    def get_stats(self) -> TransformStats:
        """Get pipeline statistics."""
        return self._stats
    
    def __or__(self, other: "Pipeline") -> "Pipeline":
        """Compose pipelines with | operator."""
        combined = Pipeline(f"{self._name}|{other._name}")
        combined._steps = self._steps + other._steps
        return combined


class FieldMapper:
    """
    Map fields between different naming conventions.
    """
    
    def __init__(
        self,
        mappings: Optional[Dict[str, str]] = None,
        transforms: Optional[Dict[str, Callable]] = None,
    ):
        self._mappings = mappings or {}
        self._transforms = transforms or {}
    
    def add_mapping(
        self,
        source: str,
        target: str,
        transform: Optional[Callable] = None,
    ) -> "FieldMapper":
        """Add a field mapping."""
        self._mappings[source] = target
        if transform:
            self._transforms[target] = transform
        return self
    
    def map(
        self,
        data: Dict[str, Any],
        strict: bool = False,
    ) -> Dict[str, Any]:
        """
        Map fields in a dictionary.
        """
        result = {}
        
        for key, value in data.items():
            # Get mapped key name
            target_key = self._mappings.get(key, key)
            
            # Apply transform if exists
            if target_key in self._transforms:
                value = self._transforms[target_key](value)
            
            # Handle nested dicts
            if isinstance(value, dict):
                value = self.map(value, strict)
            elif isinstance(value, list):
                value = [
                    self.map(item, strict) if isinstance(item, dict) else item
                    for item in value
                ]
            
            result[target_key] = value
        
        return result
    
    def reverse(self) -> "FieldMapper":
        """Create reverse mapper."""
        return FieldMapper(
            mappings={v: k for k, v in self._mappings.items()},
        )


class CaseConverter:
    """
    Convert between naming conventions.
    """
    
    @staticmethod
    def to_snake_case(s: str) -> str:
        """Convert to snake_case."""
        s = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', s)
        s = re.sub(r'([a-z\d])([A-Z])', r'\1_\2', s)
        return s.replace('-', '_').lower()
    
    @staticmethod
    def to_camel_case(s: str) -> str:
        """Convert to camelCase."""
        components = re.split(r'[-_]', s)
        return components[0].lower() + ''.join(
            x.title() for x in components[1:]
        )
    
    @staticmethod
    def to_pascal_case(s: str) -> str:
        """Convert to PascalCase."""
        components = re.split(r'[-_]', s)
        return ''.join(x.title() for x in components)
    
    @staticmethod
    def to_kebab_case(s: str) -> str:
        """Convert to kebab-case."""
        return CaseConverter.to_snake_case(s).replace('_', '-')
    
    @staticmethod
    def to_upper_snake_case(s: str) -> str:
        """Convert to UPPER_SNAKE_CASE."""
        return CaseConverter.to_snake_case(s).upper()
    
    @classmethod
    def convert(cls, s: str, to_style: CaseStyle) -> str:
        """Convert string to target style."""
        converters = {
            CaseStyle.SNAKE: cls.to_snake_case,
            CaseStyle.CAMEL: cls.to_camel_case,
            CaseStyle.PASCAL: cls.to_pascal_case,
            CaseStyle.KEBAB: cls.to_kebab_case,
            CaseStyle.UPPER_SNAKE: cls.to_upper_snake_case,
        }
        return converters[to_style](s)
    
    @classmethod
    def convert_keys(
        cls,
        data: Dict[str, Any],
        to_style: CaseStyle,
    ) -> Dict[str, Any]:
        """Convert all keys in dict to target style."""
        result = {}
        
        for key, value in data.items():
            new_key = cls.convert(key, to_style)
            
            if isinstance(value, dict):
                value = cls.convert_keys(value, to_style)
            elif isinstance(value, list):
                value = [
                    cls.convert_keys(item, to_style)
                    if isinstance(item, dict) else item
                    for item in value
                ]
            
            result[new_key] = value
        
        return result


class TypeConverter:
    """
    Convert between data types.
    """
    
    _converters: Dict[Tuple[type, type], Callable] = {}
    
    @classmethod
    def register(
        cls,
        from_type: type,
        to_type: type,
        converter: Callable,
    ) -> None:
        """Register a type converter."""
        cls._converters[(from_type, to_type)] = converter
    
    @classmethod
    def convert(
        cls,
        value: Any,
        to_type: type,
    ) -> Any:
        """Convert value to target type."""
        from_type = type(value)
        
        if from_type == to_type:
            return value
        
        # Check registered converters
        key = (from_type, to_type)
        if key in cls._converters:
            return cls._converters[key](value)
        
        # Default conversions
        try:
            if to_type == str:
                return str(value)
            elif to_type == int:
                return int(value)
            elif to_type == float:
                return float(value)
            elif to_type == bool:
                return bool(value)
            elif to_type == list:
                return list(value)
            elif to_type == dict:
                return dict(value)
            else:
                return to_type(value)
        except (ValueError, TypeError) as e:
            raise TransformError(f"Cannot convert {from_type} to {to_type}: {e}")


class DataTransformer:
    """
    High-level data transformer with common operations.
    """
    
    def __init__(self, data: Any):
        self._data = data
    
    def map(self, func: Callable[[Any], Any]) -> "DataTransformer":
        """Map function over data."""
        if isinstance(self._data, list):
            self._data = [func(item) for item in self._data]
        elif isinstance(self._data, dict):
            self._data = {k: func(v) for k, v in self._data.items()}
        else:
            self._data = func(self._data)
        return self
    
    def filter(self, predicate: Callable[[Any], bool]) -> "DataTransformer":
        """Filter data by predicate."""
        if isinstance(self._data, list):
            self._data = [item for item in self._data if predicate(item)]
        elif isinstance(self._data, dict):
            self._data = {k: v for k, v in self._data.items() if predicate(v)}
        return self
    
    def flatten(self, depth: int = 1) -> "DataTransformer":
        """Flatten nested lists."""
        if isinstance(self._data, list):
            self._data = self._flatten_list(self._data, depth)
        return self
    
    def _flatten_list(self, lst: List, depth: int) -> List:
        """Recursively flatten list."""
        if depth == 0:
            return lst
        
        result = []
        for item in lst:
            if isinstance(item, list):
                result.extend(self._flatten_list(item, depth - 1))
            else:
                result.append(item)
        return result
    
    def group_by(self, key: Union[str, Callable]) -> "DataTransformer":
        """Group list items by key."""
        if not isinstance(self._data, list):
            return self
        
        groups: Dict[Any, List] = {}
        
        for item in self._data:
            if callable(key):
                k = key(item)
            else:
                k = item.get(key) if isinstance(item, dict) else getattr(item, key, None)
            
            if k not in groups:
                groups[k] = []
            groups[k].append(item)
        
        self._data = groups
        return self
    
    def sort(
        self,
        key: Optional[Union[str, Callable]] = None,
        reverse: bool = False,
    ) -> "DataTransformer":
        """Sort data."""
        if isinstance(self._data, list):
            if key:
                if isinstance(key, str):
                    sort_key = lambda x: (
                        x.get(key) if isinstance(x, dict)
                        else getattr(x, key, None)
                    )
                else:
                    sort_key = key
                self._data = sorted(self._data, key=sort_key, reverse=reverse)
            else:
                self._data = sorted(self._data, reverse=reverse)
        return self
    
    def unique(self, key: Optional[Union[str, Callable]] = None) -> "DataTransformer":
        """Remove duplicates."""
        if isinstance(self._data, list):
            seen = set()
            result = []
            
            for item in self._data:
                if key:
                    if callable(key):
                        k = key(item)
                    else:
                        k = item.get(key) if isinstance(item, dict) else getattr(item, key, None)
                else:
                    k = json.dumps(item, sort_keys=True) if isinstance(item, dict) else item
                
                if k not in seen:
                    seen.add(k)
                    result.append(item)
            
            self._data = result
        return self
    
    def pick(self, *keys: str) -> "DataTransformer":
        """Pick specific keys from dict."""
        if isinstance(self._data, dict):
            self._data = {k: v for k, v in self._data.items() if k in keys}
        elif isinstance(self._data, list):
            self._data = [
                {k: v for k, v in item.items() if k in keys}
                if isinstance(item, dict) else item
                for item in self._data
            ]
        return self
    
    def omit(self, *keys: str) -> "DataTransformer":
        """Omit specific keys from dict."""
        if isinstance(self._data, dict):
            self._data = {k: v for k, v in self._data.items() if k not in keys}
        elif isinstance(self._data, list):
            self._data = [
                {k: v for k, v in item.items() if k not in keys}
                if isinstance(item, dict) else item
                for item in self._data
            ]
        return self
    
    def get(self) -> Any:
        """Get transformed data."""
        return self._data


class JSONPathTransformer:
    """
    Transform data using JSONPath-like expressions.
    """
    
    def get(
        self,
        data: Dict[str, Any],
        path: str,
        default: Any = None,
    ) -> Any:
        """Get value at path."""
        parts = path.replace('[', '.').replace(']', '').split('.')
        current = data
        
        for part in parts:
            if not part:
                continue
            
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list):
                try:
                    current = current[int(part)]
                except (IndexError, ValueError):
                    return default
            else:
                return default
            
            if current is None:
                return default
        
        return current
    
    def set(
        self,
        data: Dict[str, Any],
        path: str,
        value: Any,
    ) -> Dict[str, Any]:
        """Set value at path."""
        result = copy.deepcopy(data)
        parts = path.replace('[', '.').replace(']', '').split('.')
        current = result
        
        for i, part in enumerate(parts[:-1]):
            if not part:
                continue
            
            if isinstance(current, dict):
                if part not in current:
                    # Create nested structure
                    next_part = parts[i + 1]
                    if next_part.isdigit():
                        current[part] = []
                    else:
                        current[part] = {}
                current = current[part]
            elif isinstance(current, list):
                idx = int(part)
                while len(current) <= idx:
                    current.append({})
                current = current[idx]
        
        # Set final value
        final = parts[-1]
        if isinstance(current, dict):
            current[final] = value
        elif isinstance(current, list):
            idx = int(final)
            while len(current) <= idx:
                current.append(None)
            current[idx] = value
        
        return result
    
    def delete(
        self,
        data: Dict[str, Any],
        path: str,
    ) -> Dict[str, Any]:
        """Delete value at path."""
        result = copy.deepcopy(data)
        parts = path.replace('[', '.').replace(']', '').split('.')
        current = result
        
        for part in parts[:-1]:
            if not part:
                continue
            
            if isinstance(current, dict):
                current = current.get(part, {})
            elif isinstance(current, list):
                try:
                    current = current[int(part)]
                except (IndexError, ValueError):
                    return result
        
        # Delete final key
        final = parts[-1]
        if isinstance(current, dict) and final in current:
            del current[final]
        elif isinstance(current, list):
            try:
                del current[int(final)]
            except (IndexError, ValueError):
                pass
        
        return result


# Decorators
def transform_pipeline(
    *transforms: Callable,
) -> Callable:
    """
    Decorator to create a transform pipeline.
    
    Example:
        @transform_pipeline(parse_json, validate, normalize)
        async def process(data: dict) -> dict:
            return data
    """
    def decorator(func: Callable) -> Callable:
        pipeline = Pipeline()
        
        for i, transform in enumerate(transforms):
            pipeline.add_step(f"step_{i}", transform)
        
        @wraps(func)
        async def wrapper(data: Any) -> Any:
            result = await pipeline.transform(data)
            return await func(result.data) if asyncio.iscoroutinefunction(func) else func(result.data)
        
        return wrapper
    
    return decorator


def field_transform(
    field: str,
    transform_func: Callable,
) -> Callable:
    """
    Decorator to transform a specific field.
    
    Example:
        @field_transform("email", str.lower)
        def process_user(user: dict) -> dict:
            return user
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(data: Any, *args: Any, **kwargs: Any) -> Any:
            if isinstance(data, dict) and field in data:
                data = dict(data)
                data[field] = transform_func(data[field])
            return func(data, *args, **kwargs)
        
        return wrapper
    
    return decorator


def convert_case(
    to_style: CaseStyle,
) -> Callable:
    """
    Decorator to convert case of dict keys.
    
    Example:
        @convert_case(CaseStyle.SNAKE)
        def api_handler(data: dict) -> dict:
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(data: Any, *args: Any, **kwargs: Any) -> Any:
            if isinstance(data, dict):
                data = CaseConverter.convert_keys(data, to_style)
            return func(data, *args, **kwargs)
        
        return wrapper
    
    return decorator


# Factory functions
def create_pipeline(name: str = "pipeline") -> Pipeline:
    """Create a transformation pipeline."""
    return Pipeline(name)


def create_field_mapper(
    mappings: Optional[Dict[str, str]] = None,
) -> FieldMapper:
    """Create a field mapper."""
    return FieldMapper(mappings)


def create_transformer(data: Any) -> DataTransformer:
    """Create a data transformer."""
    return DataTransformer(data)


def create_jsonpath_transformer() -> JSONPathTransformer:
    """Create a JSONPath transformer."""
    return JSONPathTransformer()


# Utility functions
def transform(data: Any) -> DataTransformer:
    """Quick transform utility."""
    return DataTransformer(data)


def to_snake_case(data: Dict[str, Any]) -> Dict[str, Any]:
    """Convert dict keys to snake_case."""
    return CaseConverter.convert_keys(data, CaseStyle.SNAKE)


def to_camel_case(data: Dict[str, Any]) -> Dict[str, Any]:
    """Convert dict keys to camelCase."""
    return CaseConverter.convert_keys(data, CaseStyle.CAMEL)


__all__ = [
    # Exceptions
    "TransformError",
    "ValidationError",
    "MappingError",
    # Enums
    "TransformType",
    "CaseStyle",
    # Data classes
    "TransformStep",
    "TransformResult",
    "FieldMapping",
    "TransformStats",
    # Core classes
    "Transformer",
    "Pipeline",
    "FieldMapper",
    "CaseConverter",
    "TypeConverter",
    "DataTransformer",
    "JSONPathTransformer",
    # Decorators
    "transform_pipeline",
    "field_transform",
    "convert_case",
    # Factory functions
    "create_pipeline",
    "create_field_mapper",
    "create_transformer",
    "create_jsonpath_transformer",
    # Utility functions
    "transform",
    "to_snake_case",
    "to_camel_case",
]
