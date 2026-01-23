"""
Enterprise Specification Module.

Provides specification pattern implementation for encapsulating
business rules and criteria for DDD architectures.

Example:
    # Define specifications
    class ActiveUser(Specification[User]):
        def is_satisfied_by(self, user: User) -> bool:
            return user.status == "active"
    
    class PremiumUser(Specification[User]):
        def is_satisfied_by(self, user: User) -> bool:
            return user.tier == "premium"
    
    # Combine specifications
    active_premium = ActiveUser() & PremiumUser()
    
    # Filter users
    premium_users = [u for u in users if active_premium.is_satisfied_by(u)]
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import (
    Any,
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

T = TypeVar('T')
S = TypeVar('S', bound='Specification')


class SpecificationError(Exception):
    """Specification error."""
    pass


class Specification(ABC, Generic[T]):
    """
    Base specification class.
    
    Specifications encapsulate business rules that can be combined
    and reused for filtering, validation, and querying.
    """
    
    @abstractmethod
    def is_satisfied_by(self, candidate: T) -> bool:
        """Check if candidate satisfies this specification."""
        pass
    
    def and_(self, other: "Specification[T]") -> "AndSpecification[T]":
        """Combine with AND."""
        return AndSpecification(self, other)
    
    def or_(self, other: "Specification[T]") -> "OrSpecification[T]":
        """Combine with OR."""
        return OrSpecification(self, other)
    
    def not_(self) -> "NotSpecification[T]":
        """Negate this specification."""
        return NotSpecification(self)
    
    def __and__(self, other: "Specification[T]") -> "AndSpecification[T]":
        return self.and_(other)
    
    def __or__(self, other: "Specification[T]") -> "OrSpecification[T]":
        return self.or_(other)
    
    def __invert__(self) -> "NotSpecification[T]":
        return self.not_()
    
    def filter(self, candidates: List[T]) -> List[T]:
        """Filter candidates by this specification."""
        return [c for c in candidates if self.is_satisfied_by(c)]
    
    def count(self, candidates: List[T]) -> int:
        """Count candidates satisfying this specification."""
        return sum(1 for c in candidates if self.is_satisfied_by(c))
    
    def any(self, candidates: List[T]) -> bool:
        """Check if any candidate satisfies this specification."""
        return any(self.is_satisfied_by(c) for c in candidates)
    
    def all(self, candidates: List[T]) -> bool:
        """Check if all candidates satisfy this specification."""
        return all(self.is_satisfied_by(c) for c in candidates)
    
    def first(self, candidates: List[T]) -> Optional[T]:
        """Get first candidate satisfying this specification."""
        for c in candidates:
            if self.is_satisfied_by(c):
                return c
        return None


class AndSpecification(Specification[T]):
    """AND combination of specifications."""
    
    def __init__(self, *specs: Specification[T]):
        self._specs = specs
    
    def is_satisfied_by(self, candidate: T) -> bool:
        return all(s.is_satisfied_by(candidate) for s in self._specs)


class OrSpecification(Specification[T]):
    """OR combination of specifications."""
    
    def __init__(self, *specs: Specification[T]):
        self._specs = specs
    
    def is_satisfied_by(self, candidate: T) -> bool:
        return any(s.is_satisfied_by(candidate) for s in self._specs)


class NotSpecification(Specification[T]):
    """NOT (negation) of a specification."""
    
    def __init__(self, spec: Specification[T]):
        self._spec = spec
    
    def is_satisfied_by(self, candidate: T) -> bool:
        return not self._spec.is_satisfied_by(candidate)


class TrueSpecification(Specification[T]):
    """Specification that always returns True."""
    
    def is_satisfied_by(self, candidate: T) -> bool:
        return True


class FalseSpecification(Specification[T]):
    """Specification that always returns False."""
    
    def is_satisfied_by(self, candidate: T) -> bool:
        return False


class LambdaSpecification(Specification[T]):
    """
    Specification from a lambda/callable.
    
    Example:
        is_adult = LambdaSpecification(lambda u: u.age >= 18)
    """
    
    def __init__(
        self,
        predicate: Callable[[T], bool],
        name: Optional[str] = None,
    ):
        self._predicate = predicate
        self._name = name or "lambda"
    
    def is_satisfied_by(self, candidate: T) -> bool:
        return self._predicate(candidate)
    
    def __repr__(self) -> str:
        return f"LambdaSpecification({self._name})"


class AttributeSpecification(Specification[T]):
    """
    Specification checking an attribute value.
    
    Example:
        is_active = AttributeSpecification("status", "active")
    """
    
    def __init__(
        self,
        attribute: str,
        expected_value: Any,
    ):
        self._attribute = attribute
        self._expected = expected_value
    
    def is_satisfied_by(self, candidate: T) -> bool:
        value = getattr(candidate, self._attribute, None)
        return value == self._expected
    
    def __repr__(self) -> str:
        return f"AttributeSpecification({self._attribute}={self._expected!r})"


class ComparisonOperator(str, Enum):
    """Comparison operators."""
    EQ = "eq"
    NE = "ne"
    LT = "lt"
    LE = "le"
    GT = "gt"
    GE = "ge"
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"


class ComparisonSpecification(Specification[T]):
    """
    Specification with comparison operators.
    
    Example:
        high_value = ComparisonSpecification("amount", ComparisonOperator.GE, 1000)
    """
    
    def __init__(
        self,
        attribute: str,
        operator: ComparisonOperator,
        value: Any,
    ):
        self._attribute = attribute
        self._operator = operator
        self._value = value
    
    def is_satisfied_by(self, candidate: T) -> bool:
        actual = getattr(candidate, self._attribute, None)
        
        if self._operator == ComparisonOperator.EQ:
            return actual == self._value
        elif self._operator == ComparisonOperator.NE:
            return actual != self._value
        elif self._operator == ComparisonOperator.LT:
            return actual < self._value
        elif self._operator == ComparisonOperator.LE:
            return actual <= self._value
        elif self._operator == ComparisonOperator.GT:
            return actual > self._value
        elif self._operator == ComparisonOperator.GE:
            return actual >= self._value
        elif self._operator == ComparisonOperator.IN:
            return actual in self._value
        elif self._operator == ComparisonOperator.NOT_IN:
            return actual not in self._value
        elif self._operator == ComparisonOperator.CONTAINS:
            return self._value in actual
        elif self._operator == ComparisonOperator.STARTS_WITH:
            return str(actual).startswith(str(self._value))
        elif self._operator == ComparisonOperator.ENDS_WITH:
            return str(actual).endswith(str(self._value))
        
        return False


class RangeSpecification(Specification[T]):
    """
    Specification for range checking.
    
    Example:
        valid_age = RangeSpecification("age", min_value=18, max_value=65)
    """
    
    def __init__(
        self,
        attribute: str,
        min_value: Optional[Any] = None,
        max_value: Optional[Any] = None,
        inclusive: bool = True,
    ):
        self._attribute = attribute
        self._min = min_value
        self._max = max_value
        self._inclusive = inclusive
    
    def is_satisfied_by(self, candidate: T) -> bool:
        value = getattr(candidate, self._attribute, None)
        
        if value is None:
            return False
        
        if self._inclusive:
            if self._min is not None and value < self._min:
                return False
            if self._max is not None and value > self._max:
                return False
        else:
            if self._min is not None and value <= self._min:
                return False
            if self._max is not None and value >= self._max:
                return False
        
        return True


class DateRangeSpecification(Specification[T]):
    """
    Specification for date range checking.
    
    Example:
        recent = DateRangeSpecification("created_at", days_ago=30)
    """
    
    def __init__(
        self,
        attribute: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        days_ago: Optional[int] = None,
    ):
        self._attribute = attribute
        self._start = start
        self._end = end
        
        if days_ago is not None:
            from datetime import timedelta
            self._start = datetime.now() - timedelta(days=days_ago)
    
    def is_satisfied_by(self, candidate: T) -> bool:
        value = getattr(candidate, self._attribute, None)
        
        if value is None:
            return False
        
        if self._start is not None and value < self._start:
            return False
        if self._end is not None and value > self._end:
            return False
        
        return True


class CollectionSpecification(Specification[T]):
    """
    Specification for collection attributes.
    
    Example:
        has_tags = CollectionSpecification("tags", contains_any=["python", "java"])
    """
    
    def __init__(
        self,
        attribute: str,
        is_empty: Optional[bool] = None,
        has_count: Optional[int] = None,
        min_count: Optional[int] = None,
        max_count: Optional[int] = None,
        contains: Optional[Any] = None,
        contains_any: Optional[List[Any]] = None,
        contains_all: Optional[List[Any]] = None,
    ):
        self._attribute = attribute
        self._is_empty = is_empty
        self._has_count = has_count
        self._min_count = min_count
        self._max_count = max_count
        self._contains = contains
        self._contains_any = contains_any
        self._contains_all = contains_all
    
    def is_satisfied_by(self, candidate: T) -> bool:
        collection = getattr(candidate, self._attribute, None)
        
        if collection is None:
            return False
        
        if self._is_empty is not None:
            if self._is_empty and len(collection) > 0:
                return False
            if not self._is_empty and len(collection) == 0:
                return False
        
        if self._has_count is not None and len(collection) != self._has_count:
            return False
        
        if self._min_count is not None and len(collection) < self._min_count:
            return False
        
        if self._max_count is not None and len(collection) > self._max_count:
            return False
        
        if self._contains is not None and self._contains not in collection:
            return False
        
        if self._contains_any is not None:
            if not any(item in collection for item in self._contains_any):
                return False
        
        if self._contains_all is not None:
            if not all(item in collection for item in self._contains_all):
                return False
        
        return True


class CompositeSpecification(Specification[T]):
    """
    Composite specification with named parts.
    
    Example:
        spec = CompositeSpecification()
        spec.add("active", AttributeSpecification("status", "active"))
        spec.add("premium", AttributeSpecification("tier", "premium"))
    """
    
    def __init__(self):
        self._specs: Dict[str, Specification[T]] = {}
        self._mode: str = "and"
    
    def add(
        self,
        name: str,
        spec: Specification[T],
    ) -> "CompositeSpecification[T]":
        """Add a named specification."""
        self._specs[name] = spec
        return self
    
    def remove(self, name: str) -> "CompositeSpecification[T]":
        """Remove a named specification."""
        self._specs.pop(name, None)
        return self
    
    def use_and(self) -> "CompositeSpecification[T]":
        """Use AND mode (all must be satisfied)."""
        self._mode = "and"
        return self
    
    def use_or(self) -> "CompositeSpecification[T]":
        """Use OR mode (any must be satisfied)."""
        self._mode = "or"
        return self
    
    def is_satisfied_by(self, candidate: T) -> bool:
        if not self._specs:
            return True
        
        if self._mode == "and":
            return all(s.is_satisfied_by(candidate) for s in self._specs.values())
        else:
            return any(s.is_satisfied_by(candidate) for s in self._specs.values())
    
    def evaluate_all(
        self,
        candidate: T,
    ) -> Dict[str, bool]:
        """Evaluate all specifications and return results."""
        return {
            name: spec.is_satisfied_by(candidate)
            for name, spec in self._specs.items()
        }


@dataclass
class ValidationResult:
    """Result of specification validation."""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)


class ValidationSpecification(Specification[T]):
    """
    Specification with validation messages.
    
    Example:
        valid_user = ValidationSpecification(
            AttributeSpecification("email", lambda e: "@" in e),
            error_message="Invalid email format"
        )
    """
    
    def __init__(
        self,
        spec: Specification[T],
        error_message: str,
        is_warning: bool = False,
    ):
        self._spec = spec
        self._error_message = error_message
        self._is_warning = is_warning
    
    def is_satisfied_by(self, candidate: T) -> bool:
        return self._spec.is_satisfied_by(candidate)
    
    def validate(self, candidate: T) -> ValidationResult:
        """Validate and return result with message."""
        is_valid = self._spec.is_satisfied_by(candidate)
        
        if is_valid:
            return ValidationResult(is_valid=True)
        
        if self._is_warning:
            return ValidationResult(
                is_valid=True,
                warnings=[self._error_message],
            )
        else:
            return ValidationResult(
                is_valid=False,
                errors=[self._error_message],
            )


class ValidatorSpecification(Specification[T]):
    """
    Validator with multiple validation specifications.
    
    Example:
        validator = ValidatorSpecification()
        validator.add_rule(
            AttributeSpecification("name", lambda n: len(n) > 0),
            "Name is required"
        )
        validator.add_rule(
            AttributeSpecification("age", lambda a: a >= 18),
            "Must be 18 or older"
        )
        
        result = validator.validate(user)
    """
    
    def __init__(self):
        self._rules: List[ValidationSpecification[T]] = []
    
    def add_rule(
        self,
        spec: Specification[T],
        error_message: str,
        is_warning: bool = False,
    ) -> "ValidatorSpecification[T]":
        """Add a validation rule."""
        self._rules.append(ValidationSpecification(
            spec, error_message, is_warning
        ))
        return self
    
    def is_satisfied_by(self, candidate: T) -> bool:
        return all(r.is_satisfied_by(candidate) for r in self._rules)
    
    def validate(self, candidate: T) -> ValidationResult:
        """Validate and collect all errors/warnings."""
        errors: List[str] = []
        warnings: List[str] = []
        
        for rule in self._rules:
            result = rule.validate(candidate)
            errors.extend(result.errors)
            warnings.extend(result.warnings)
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )


class SpecificationRegistry:
    """
    Registry for reusable specifications.
    """
    
    def __init__(self):
        self._specs: Dict[str, Specification] = {}
    
    def register(
        self,
        name: str,
        spec: Specification,
    ) -> None:
        """Register a specification."""
        self._specs[name] = spec
    
    def get(self, name: str) -> Optional[Specification]:
        """Get a specification by name."""
        return self._specs.get(name)
    
    def combine_and(self, *names: str) -> Specification:
        """Combine specifications with AND."""
        specs = [self._specs[n] for n in names if n in self._specs]
        return AndSpecification(*specs)
    
    def combine_or(self, *names: str) -> Specification:
        """Combine specifications with OR."""
        specs = [self._specs[n] for n in names if n in self._specs]
        return OrSpecification(*specs)


# Global registry
_global_registry = SpecificationRegistry()


# Decorators
def specification(cls: Type[S]) -> Type[S]:
    """
    Class decorator to mark as specification.
    
    Example:
        @specification
        class ActiveUser(Specification[User]):
            def is_satisfied_by(self, user: User) -> bool:
                return user.status == "active"
    """
    # Register in global registry
    _global_registry.register(cls.__name__, cls())
    return cls


def rule(
    error_message: str,
    is_warning: bool = False,
) -> Callable[[Callable[[T], bool]], ValidationSpecification[T]]:
    """
    Decorator to create validation specification from function.
    
    Example:
        @rule("Email is required")
        def has_email(user: User) -> bool:
            return bool(user.email)
    """
    def decorator(func: Callable[[T], bool]) -> ValidationSpecification[T]:
        return ValidationSpecification(
            LambdaSpecification(func, func.__name__),
            error_message,
            is_warning,
        )
    
    return decorator


# Factory functions
def create_specification(
    predicate: Callable[[T], bool],
    name: Optional[str] = None,
) -> LambdaSpecification[T]:
    """Create specification from callable."""
    return LambdaSpecification(predicate, name)


def create_attribute_spec(
    attribute: str,
    value: Any,
) -> AttributeSpecification:
    """Create attribute specification."""
    return AttributeSpecification(attribute, value)


def create_comparison_spec(
    attribute: str,
    operator: ComparisonOperator,
    value: Any,
) -> ComparisonSpecification:
    """Create comparison specification."""
    return ComparisonSpecification(attribute, operator, value)


def create_range_spec(
    attribute: str,
    min_value: Optional[Any] = None,
    max_value: Optional[Any] = None,
    inclusive: bool = True,
) -> RangeSpecification:
    """Create range specification."""
    return RangeSpecification(attribute, min_value, max_value, inclusive)


def create_validator() -> ValidatorSpecification:
    """Create a validator specification."""
    return ValidatorSpecification()


def create_composite() -> CompositeSpecification:
    """Create composite specification."""
    return CompositeSpecification()


def get_specification(name: str) -> Optional[Specification]:
    """Get specification from global registry."""
    return _global_registry.get(name)


def register_specification(name: str, spec: Specification) -> None:
    """Register specification in global registry."""
    _global_registry.register(name, spec)


# Shorthand specifications
def equals(attribute: str, value: Any) -> AttributeSpecification:
    """Check attribute equals value."""
    return AttributeSpecification(attribute, value)


def not_equals(attribute: str, value: Any) -> NotSpecification:
    """Check attribute not equals value."""
    return NotSpecification(AttributeSpecification(attribute, value))


def greater_than(attribute: str, value: Any) -> ComparisonSpecification:
    """Check attribute greater than value."""
    return ComparisonSpecification(attribute, ComparisonOperator.GT, value)


def less_than(attribute: str, value: Any) -> ComparisonSpecification:
    """Check attribute less than value."""
    return ComparisonSpecification(attribute, ComparisonOperator.LT, value)


def in_list(attribute: str, values: List[Any]) -> ComparisonSpecification:
    """Check attribute in list of values."""
    return ComparisonSpecification(attribute, ComparisonOperator.IN, values)


def contains(attribute: str, value: Any) -> ComparisonSpecification:
    """Check attribute contains value."""
    return ComparisonSpecification(attribute, ComparisonOperator.CONTAINS, value)


def between(
    attribute: str,
    min_value: Any,
    max_value: Any,
) -> RangeSpecification:
    """Check attribute is between min and max."""
    return RangeSpecification(attribute, min_value, max_value)


__all__ = [
    # Exceptions
    "SpecificationError",
    # Base classes
    "Specification",
    "AndSpecification",
    "OrSpecification",
    "NotSpecification",
    "TrueSpecification",
    "FalseSpecification",
    # Specification types
    "LambdaSpecification",
    "AttributeSpecification",
    "ComparisonSpecification",
    "RangeSpecification",
    "DateRangeSpecification",
    "CollectionSpecification",
    "CompositeSpecification",
    # Validation
    "ValidationResult",
    "ValidationSpecification",
    "ValidatorSpecification",
    # Enums
    "ComparisonOperator",
    # Registry
    "SpecificationRegistry",
    # Decorators
    "specification",
    "rule",
    # Factory functions
    "create_specification",
    "create_attribute_spec",
    "create_comparison_spec",
    "create_range_spec",
    "create_validator",
    "create_composite",
    "get_specification",
    "register_specification",
    # Shorthand
    "equals",
    "not_equals",
    "greater_than",
    "less_than",
    "in_list",
    "contains",
    "between",
]
