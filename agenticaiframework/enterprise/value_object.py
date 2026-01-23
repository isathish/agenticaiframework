"""
Enterprise Value Object Module.

Provides immutable value objects, equality by value,
and self-validation for DDD architectures.

Example:
    # Define a value object
    @value_object
    class Money:
        amount: Decimal
        currency: str
        
        def add(self, other: "Money") -> "Money":
            if self.currency != other.currency:
                raise ValueError("Currency mismatch")
            return Money(self.amount + other.amount, self.currency)
    
    # Use value object
    price = Money(Decimal("99.99"), "USD")
    tax = Money(Decimal("8.00"), "USD")
    total = price.add(tax)
"""

from __future__ import annotations

import copy
import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, fields as dataclass_fields
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import Enum
from functools import total_ordering
from typing import (
    Any,
    Callable,
    Dict,
    FrozenSet,
    Generic,
    List,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
)

T = TypeVar('T')
V = TypeVar('V', bound='ValueObject')


class ValueObjectError(Exception):
    """Value object error."""
    pass


class ValidationError(ValueObjectError):
    """Validation error."""
    pass


class ImmutabilityError(ValueObjectError):
    """Immutability violation error."""
    pass


class ValueObject(ABC):
    """
    Base class for value objects.
    
    Value objects are defined by their attributes and are immutable.
    Two value objects are equal if all their attributes are equal.
    """
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, self.__class__):
            return False
        return self._get_equality_components() == other._get_equality_components()
    
    def __hash__(self) -> int:
        return hash(self._get_equality_components())
    
    @abstractmethod
    def _get_equality_components(self) -> tuple:
        """Get components for equality comparison."""
        pass
    
    def copy_with(self, **changes: Any) -> "ValueObject":
        """Create a copy with changes."""
        # Must be implemented by subclasses
        raise NotImplementedError


@dataclass(frozen=True)
class SimpleValueObject(ValueObject):
    """
    Simple value object using dataclass.
    
    Example:
        @dataclass(frozen=True)
        class Email(SimpleValueObject):
            address: str
            
            def __post_init__(self):
                if "@" not in self.address:
                    raise ValidationError("Invalid email")
    """
    
    def _get_equality_components(self) -> tuple:
        return tuple(
            getattr(self, f.name)
            for f in dataclass_fields(self)
        )
    
    def copy_with(self, **changes: Any) -> "SimpleValueObject":
        """Create a copy with changes."""
        current = {
            f.name: getattr(self, f.name)
            for f in dataclass_fields(self)
        }
        current.update(changes)
        return self.__class__(**current)


# Common Value Objects
@dataclass(frozen=True)
@total_ordering
class Money(SimpleValueObject):
    """Money value object."""
    amount: Decimal
    currency: str = "USD"
    
    def __post_init__(self):
        if not isinstance(self.amount, Decimal):
            object.__setattr__(self, 'amount', Decimal(str(self.amount)))
    
    def __lt__(self, other: "Money") -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        if self.currency != other.currency:
            raise ValueObjectError("Cannot compare different currencies")
        return self.amount < other.amount
    
    def add(self, other: "Money") -> "Money":
        """Add money amounts."""
        if self.currency != other.currency:
            raise ValueObjectError("Currency mismatch")
        return Money(self.amount + other.amount, self.currency)
    
    def subtract(self, other: "Money") -> "Money":
        """Subtract money amounts."""
        if self.currency != other.currency:
            raise ValueObjectError("Currency mismatch")
        return Money(self.amount - other.amount, self.currency)
    
    def multiply(self, factor: Union[int, float, Decimal]) -> "Money":
        """Multiply by a factor."""
        return Money(
            self.amount * Decimal(str(factor)),
            self.currency,
        )
    
    def is_positive(self) -> bool:
        """Check if amount is positive."""
        return self.amount > 0
    
    def is_zero(self) -> bool:
        """Check if amount is zero."""
        return self.amount == 0
    
    @classmethod
    def zero(cls, currency: str = "USD") -> "Money":
        """Create zero money."""
        return cls(Decimal("0"), currency)
    
    def __str__(self) -> str:
        return f"{self.currency} {self.amount:.2f}"


@dataclass(frozen=True)
class EmailAddress(SimpleValueObject):
    """Email address value object."""
    address: str
    
    def __post_init__(self):
        if not self.address or "@" not in self.address:
            raise ValidationError(f"Invalid email address: {self.address}")
        
        local, domain = self.address.rsplit("@", 1)
        if not local or not domain or "." not in domain:
            raise ValidationError(f"Invalid email address: {self.address}")
    
    @property
    def local_part(self) -> str:
        return self.address.rsplit("@", 1)[0]
    
    @property
    def domain(self) -> str:
        return self.address.rsplit("@", 1)[1]
    
    def __str__(self) -> str:
        return self.address


@dataclass(frozen=True)
class PhoneNumber(SimpleValueObject):
    """Phone number value object."""
    number: str
    country_code: str = "+1"
    
    def __post_init__(self):
        # Clean the number
        cleaned = "".join(c for c in self.number if c.isdigit())
        if len(cleaned) < 7:
            raise ValidationError(f"Invalid phone number: {self.number}")
        object.__setattr__(self, 'number', cleaned)
    
    @property
    def formatted(self) -> str:
        if len(self.number) == 10:
            return f"{self.country_code} ({self.number[:3]}) {self.number[3:6]}-{self.number[6:]}"
        return f"{self.country_code} {self.number}"
    
    def __str__(self) -> str:
        return self.formatted


@dataclass(frozen=True)
class Address(SimpleValueObject):
    """Address value object."""
    street: str
    city: str
    state: str
    postal_code: str
    country: str = "USA"
    apartment: Optional[str] = None
    
    def __post_init__(self):
        if not self.street or not self.city:
            raise ValidationError("Street and city are required")
    
    @property
    def full_address(self) -> str:
        parts = [self.street]
        if self.apartment:
            parts.append(f"Apt {self.apartment}")
        parts.append(f"{self.city}, {self.state} {self.postal_code}")
        parts.append(self.country)
        return "\n".join(parts)
    
    def __str__(self) -> str:
        return f"{self.street}, {self.city}, {self.state} {self.postal_code}"


@dataclass(frozen=True)
class DateRange(SimpleValueObject):
    """Date range value object."""
    start: date
    end: date
    
    def __post_init__(self):
        if self.end < self.start:
            raise ValidationError("End date must be after start date")
    
    @property
    def days(self) -> int:
        return (self.end - self.start).days
    
    def contains(self, d: date) -> bool:
        """Check if date is in range."""
        return self.start <= d <= self.end
    
    def overlaps(self, other: "DateRange") -> bool:
        """Check if ranges overlap."""
        return self.start <= other.end and other.start <= self.end
    
    def merge(self, other: "DateRange") -> "DateRange":
        """Merge overlapping ranges."""
        if not self.overlaps(other):
            raise ValueObjectError("Ranges do not overlap")
        return DateRange(
            min(self.start, other.start),
            max(self.end, other.end),
        )


@dataclass(frozen=True)
class Percentage(SimpleValueObject):
    """Percentage value object."""
    value: Decimal
    
    def __post_init__(self):
        if not isinstance(self.value, Decimal):
            object.__setattr__(self, 'value', Decimal(str(self.value)))
        if self.value < 0 or self.value > 100:
            raise ValidationError("Percentage must be between 0 and 100")
    
    def apply_to(self, amount: Decimal) -> Decimal:
        """Apply percentage to an amount."""
        return amount * (self.value / 100)
    
    @classmethod
    def from_fraction(cls, fraction: float) -> "Percentage":
        """Create from fraction (0-1)."""
        return cls(Decimal(str(fraction * 100)))
    
    def __str__(self) -> str:
        return f"{self.value}%"


@dataclass(frozen=True)
class Quantity(SimpleValueObject):
    """Quantity value object."""
    value: int
    unit: str = "pcs"
    
    def __post_init__(self):
        if self.value < 0:
            raise ValidationError("Quantity cannot be negative")
    
    def add(self, other: "Quantity") -> "Quantity":
        """Add quantities."""
        if self.unit != other.unit:
            raise ValueObjectError("Unit mismatch")
        return Quantity(self.value + other.value, self.unit)
    
    def subtract(self, other: "Quantity") -> "Quantity":
        """Subtract quantities."""
        if self.unit != other.unit:
            raise ValueObjectError("Unit mismatch")
        result = self.value - other.value
        if result < 0:
            raise ValueObjectError("Result would be negative")
        return Quantity(result, self.unit)
    
    def is_zero(self) -> bool:
        return self.value == 0
    
    @classmethod
    def zero(cls, unit: str = "pcs") -> "Quantity":
        return cls(0, unit)
    
    def __str__(self) -> str:
        return f"{self.value} {self.unit}"


@dataclass(frozen=True)
class Coordinate(SimpleValueObject):
    """Geographic coordinate value object."""
    latitude: float
    longitude: float
    
    def __post_init__(self):
        if not (-90 <= self.latitude <= 90):
            raise ValidationError("Latitude must be between -90 and 90")
        if not (-180 <= self.longitude <= 180):
            raise ValidationError("Longitude must be between -180 and 180")
    
    def distance_to(self, other: "Coordinate") -> float:
        """Calculate approximate distance in kilometers."""
        from math import radians, sin, cos, sqrt, atan2
        
        R = 6371  # Earth's radius in km
        
        lat1, lon1 = radians(self.latitude), radians(self.longitude)
        lat2, lon2 = radians(other.latitude), radians(other.longitude)
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        return R * c
    
    def __str__(self) -> str:
        return f"({self.latitude}, {self.longitude})"


@dataclass(frozen=True)
class URL(SimpleValueObject):
    """URL value object."""
    value: str
    
    def __post_init__(self):
        if not self.value:
            raise ValidationError("URL cannot be empty")
        if not (self.value.startswith("http://") or self.value.startswith("https://")):
            raise ValidationError("URL must start with http:// or https://")
    
    @property
    def is_secure(self) -> bool:
        return self.value.startswith("https://")
    
    @property
    def domain(self) -> str:
        from urllib.parse import urlparse
        return urlparse(self.value).netloc
    
    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Password(SimpleValueObject):
    """Password value object with hashing."""
    _hash: str
    
    @classmethod
    def create(cls, plain_text: str, min_length: int = 8) -> "Password":
        """Create password from plain text."""
        if len(plain_text) < min_length:
            raise ValidationError(f"Password must be at least {min_length} characters")
        
        # Simple hash - in production use proper password hashing
        hash_value = hashlib.sha256(plain_text.encode()).hexdigest()
        return cls(hash_value)
    
    def verify(self, plain_text: str) -> bool:
        """Verify password."""
        hash_value = hashlib.sha256(plain_text.encode()).hexdigest()
        return self._hash == hash_value
    
    def __str__(self) -> str:
        return "********"
    
    def __repr__(self) -> str:
        return "Password(***)"


class ValueCollection(ValueObject, Generic[T]):
    """
    Immutable collection value object.
    
    Example:
        tags = ValueCollection[str](["python", "ddd", "enterprise"])
    """
    
    def __init__(self, items: List[T]):
        self._items: Tuple[T, ...] = tuple(items)
    
    @property
    def items(self) -> Tuple[T, ...]:
        return self._items
    
    def __iter__(self):
        return iter(self._items)
    
    def __len__(self) -> int:
        return len(self._items)
    
    def __contains__(self, item: T) -> bool:
        return item in self._items
    
    def _get_equality_components(self) -> tuple:
        return self._items
    
    def add(self, item: T) -> "ValueCollection[T]":
        """Return new collection with added item."""
        return ValueCollection(list(self._items) + [item])
    
    def remove(self, item: T) -> "ValueCollection[T]":
        """Return new collection without item."""
        items = [i for i in self._items if i != item]
        return ValueCollection(items)
    
    def filter(self, predicate: Callable[[T], bool]) -> "ValueCollection[T]":
        """Return filtered collection."""
        return ValueCollection([i for i in self._items if predicate(i)])
    
    def copy_with(self, **changes: Any) -> "ValueCollection[T]":
        return ValueCollection(list(self._items))


# Decorators
def value_object(cls: Type) -> Type:
    """
    Class decorator to mark as value object.
    
    Makes the class immutable (frozen dataclass) and adds equality.
    
    Example:
        @value_object
        class Color:
            red: int
            green: int
            blue: int
    """
    # Convert to frozen dataclass
    cls = dataclass(frozen=True)(cls)
    
    # Add value object methods
    def _get_equality_components(self) -> tuple:
        return tuple(getattr(self, f.name) for f in dataclass_fields(self))
    
    def copy_with(self, **changes):
        current = {f.name: getattr(self, f.name) for f in dataclass_fields(self)}
        current.update(changes)
        return self.__class__(**current)
    
    cls._get_equality_components = _get_equality_components
    cls.copy_with = copy_with
    
    return cls


def validated(validator: Callable[[Any], bool], message: str = "Validation failed"):
    """
    Decorator to add validation to value object.
    
    Example:
        @validated(lambda x: x.value > 0, "Value must be positive")
        @value_object
        class PositiveNumber:
            value: int
    """
    def decorator(cls: Type) -> Type:
        original_init = getattr(cls, '__post_init__', None)
        
        def __post_init__(self):
            if original_init:
                original_init(self)
            if not validator(self):
                raise ValidationError(message)
        
        cls.__post_init__ = __post_init__
        return cls
    
    return decorator


def immutable(cls: Type) -> Type:
    """
    Class decorator to make a class immutable.
    
    Example:
        @immutable
        class Config:
            host: str
            port: int
    """
    def __setattr__(self, name: str, value: Any):
        if hasattr(self, '_initialized'):
            raise ImmutabilityError(f"Cannot modify immutable attribute: {name}")
        object.__setattr__(self, name, value)
    
    def __delattr__(self, name: str):
        raise ImmutabilityError(f"Cannot delete immutable attribute: {name}")
    
    original_init = cls.__init__
    
    def __init__(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        object.__setattr__(self, '_initialized', True)
    
    cls.__setattr__ = __setattr__
    cls.__delattr__ = __delattr__
    cls.__init__ = __init__
    
    return cls


# Factory functions
def create_money(
    amount: Union[int, float, str, Decimal],
    currency: str = "USD",
) -> Money:
    """Create money value object."""
    return Money(Decimal(str(amount)), currency)


def create_email(address: str) -> EmailAddress:
    """Create email address value object."""
    return EmailAddress(address)


def create_phone(
    number: str,
    country_code: str = "+1",
) -> PhoneNumber:
    """Create phone number value object."""
    return PhoneNumber(number, country_code)


def create_address(
    street: str,
    city: str,
    state: str,
    postal_code: str,
    country: str = "USA",
    apartment: Optional[str] = None,
) -> Address:
    """Create address value object."""
    return Address(street, city, state, postal_code, country, apartment)


def create_date_range(
    start: date,
    end: date,
) -> DateRange:
    """Create date range value object."""
    return DateRange(start, end)


def create_percentage(value: Union[int, float, Decimal]) -> Percentage:
    """Create percentage value object."""
    return Percentage(Decimal(str(value)))


def create_quantity(value: int, unit: str = "pcs") -> Quantity:
    """Create quantity value object."""
    return Quantity(value, unit)


def create_coordinate(latitude: float, longitude: float) -> Coordinate:
    """Create coordinate value object."""
    return Coordinate(latitude, longitude)


def create_url(value: str) -> URL:
    """Create URL value object."""
    return URL(value)


def create_password(plain_text: str, min_length: int = 8) -> Password:
    """Create password value object."""
    return Password.create(plain_text, min_length)


def create_collection(items: List[T]) -> ValueCollection[T]:
    """Create value collection."""
    return ValueCollection(items)


__all__ = [
    # Exceptions
    "ValueObjectError",
    "ValidationError",
    "ImmutabilityError",
    # Base classes
    "ValueObject",
    "SimpleValueObject",
    "ValueCollection",
    # Common value objects
    "Money",
    "EmailAddress",
    "PhoneNumber",
    "Address",
    "DateRange",
    "Percentage",
    "Quantity",
    "Coordinate",
    "URL",
    "Password",
    # Decorators
    "value_object",
    "validated",
    "immutable",
    # Factory functions
    "create_money",
    "create_email",
    "create_phone",
    "create_address",
    "create_date_range",
    "create_percentage",
    "create_quantity",
    "create_coordinate",
    "create_url",
    "create_password",
    "create_collection",
]
