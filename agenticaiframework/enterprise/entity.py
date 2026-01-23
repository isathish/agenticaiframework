"""
Enterprise Entity Module.

Provides entity base classes, identity management, lifecycle tracking,
and entity comparison for DDD architectures.

Example:
    # Define an entity
    class Order(Entity[OrderId]):
        def __init__(self, order_id: OrderId, customer_id: str):
            super().__init__(order_id)
            self.customer_id = customer_id
            self.items = []
        
        def add_item(self, item: OrderItem):
            self.items.append(item)
            self.mark_modified()
    
    # Use entity
    order = Order(OrderId("123"), customer_id="cust-456")
    order.add_item(OrderItem("product-1", 2))
"""

from __future__ import annotations

import copy
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from functools import total_ordering
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    Hashable,
    List,
    Optional,
    Type,
    TypeVar,
    Union,
)

ID = TypeVar('ID', bound='EntityId')
E = TypeVar('E', bound='Entity')


class EntityError(Exception):
    """Entity error."""
    pass


class InvalidIdError(EntityError):
    """Invalid identity error."""
    pass


class EntityStateError(EntityError):
    """Entity state error."""
    pass


class EntityLifecycle(str, Enum):
    """Entity lifecycle state."""
    NEW = "new"
    CLEAN = "clean"
    MODIFIED = "modified"
    DELETED = "deleted"


@total_ordering
class EntityId(ABC, Hashable):
    """
    Base class for entity identity.
    """
    
    @property
    @abstractmethod
    def value(self) -> Any:
        """Get the identity value."""
        pass
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, EntityId):
            return False
        return self.value == other.value
    
    def __lt__(self, other: object) -> bool:
        if not isinstance(other, EntityId):
            return NotImplemented
        return str(self.value) < str(other.value)
    
    def __hash__(self) -> int:
        return hash(self.value)
    
    def __str__(self) -> str:
        return str(self.value)
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.value!r})"


@dataclass
class StringId(EntityId):
    """String-based identity."""
    _value: str
    
    @property
    def value(self) -> str:
        return self._value
    
    @classmethod
    def generate(cls) -> "StringId":
        """Generate a new ID."""
        return cls(str(uuid.uuid4()))
    
    @classmethod
    def from_string(cls, value: str) -> "StringId":
        """Create from string."""
        if not value:
            raise InvalidIdError("ID cannot be empty")
        return cls(value)


@dataclass
class UuidId(EntityId):
    """UUID-based identity."""
    _value: uuid.UUID
    
    def __init__(self, value: Optional[Union[str, uuid.UUID]] = None):
        if value is None:
            self._value = uuid.uuid4()
        elif isinstance(value, uuid.UUID):
            self._value = value
        else:
            try:
                self._value = uuid.UUID(value)
            except ValueError as e:
                raise InvalidIdError(f"Invalid UUID: {value}") from e
    
    @property
    def value(self) -> uuid.UUID:
        return self._value
    
    @classmethod
    def generate(cls) -> "UuidId":
        """Generate a new ID."""
        return cls(uuid.uuid4())


@dataclass
class IntId(EntityId):
    """Integer-based identity."""
    _value: int
    
    @property
    def value(self) -> int:
        return self._value
    
    @classmethod
    def from_int(cls, value: int) -> "IntId":
        """Create from integer."""
        if value <= 0:
            raise InvalidIdError("ID must be positive")
        return cls(value)


@dataclass
class CompositeId(EntityId):
    """Composite identity made of multiple parts."""
    parts: tuple
    
    @property
    def value(self) -> tuple:
        return self.parts
    
    def __init__(self, *parts: Any):
        if not parts:
            raise InvalidIdError("Composite ID must have at least one part")
        self.parts = parts
    
    def __str__(self) -> str:
        return ":".join(str(p) for p in self.parts)


@dataclass
class EntityMetadata:
    """Entity metadata."""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    version: int = 1
    deleted_at: Optional[datetime] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class Entity(Generic[ID]):
    """
    Base entity class.
    
    Example:
        class User(Entity[UserId]):
            def __init__(self, user_id: UserId, name: str):
                super().__init__(user_id)
                self.name = name
    """
    
    def __init__(self, id: ID):
        self._id = id
        self._metadata = EntityMetadata()
        self._lifecycle = EntityLifecycle.NEW
        self._original_hash: Optional[int] = None
    
    @property
    def id(self) -> ID:
        """Get entity identity."""
        return self._id
    
    @property
    def metadata(self) -> EntityMetadata:
        """Get entity metadata."""
        return self._metadata
    
    @property
    def lifecycle(self) -> EntityLifecycle:
        """Get lifecycle state."""
        return self._lifecycle
    
    @property
    def is_new(self) -> bool:
        """Check if entity is new."""
        return self._lifecycle == EntityLifecycle.NEW
    
    @property
    def is_modified(self) -> bool:
        """Check if entity is modified."""
        return self._lifecycle == EntityLifecycle.MODIFIED
    
    @property
    def is_deleted(self) -> bool:
        """Check if entity is deleted."""
        return self._lifecycle == EntityLifecycle.DELETED
    
    @property
    def version(self) -> int:
        """Get entity version."""
        return self._metadata.version
    
    def mark_clean(self) -> None:
        """Mark entity as clean (persisted)."""
        self._lifecycle = EntityLifecycle.CLEAN
        self._original_hash = self._compute_hash()
    
    def mark_modified(self) -> None:
        """Mark entity as modified."""
        if self._lifecycle != EntityLifecycle.DELETED:
            self._lifecycle = EntityLifecycle.MODIFIED
            self._metadata.updated_at = datetime.now()
    
    def mark_deleted(self) -> None:
        """Mark entity as deleted."""
        self._lifecycle = EntityLifecycle.DELETED
        self._metadata.deleted_at = datetime.now()
    
    def increment_version(self) -> None:
        """Increment entity version."""
        self._metadata.version += 1
        self._metadata.updated_at = datetime.now()
    
    def has_changes(self) -> bool:
        """Check if entity has unsaved changes."""
        if self._lifecycle in (EntityLifecycle.NEW, EntityLifecycle.MODIFIED):
            return True
        
        if self._original_hash is None:
            return True
        
        return self._compute_hash() != self._original_hash
    
    def _compute_hash(self) -> int:
        """Compute hash of current state."""
        # Override in subclasses for proper comparison
        return hash(str(self.__dict__))
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Entity):
            return False
        return self._id == other._id
    
    def __hash__(self) -> int:
        return hash(self._id)
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(id={self._id})"


class AuditableEntity(Entity[ID]):
    """
    Entity with audit tracking.
    """
    
    def __init__(self, id: ID, created_by: Optional[str] = None):
        super().__init__(id)
        self._metadata.created_by = created_by
    
    def update_by(self, user_id: str) -> None:
        """Record update by user."""
        self._metadata.updated_by = user_id
        self.mark_modified()
    
    @property
    def created_by(self) -> Optional[str]:
        return self._metadata.created_by
    
    @property
    def updated_by(self) -> Optional[str]:
        return self._metadata.updated_by


class SoftDeleteEntity(Entity[ID]):
    """
    Entity with soft delete support.
    """
    
    @property
    def is_soft_deleted(self) -> bool:
        return self._metadata.deleted_at is not None
    
    def soft_delete(self) -> None:
        """Soft delete the entity."""
        self._metadata.deleted_at = datetime.now()
        self.mark_modified()
    
    def restore(self) -> None:
        """Restore a soft-deleted entity."""
        self._metadata.deleted_at = None
        self.mark_modified()


class VersionedEntity(Entity[ID]):
    """
    Entity with optimistic locking support.
    """
    
    def check_version(self, expected_version: int) -> bool:
        """Check if version matches."""
        return self._metadata.version == expected_version
    
    def assert_version(self, expected_version: int) -> None:
        """Assert version matches or raise error."""
        if not self.check_version(expected_version):
            raise EntityStateError(
                f"Version mismatch: expected {expected_version}, "
                f"got {self._metadata.version}"
            )


class EntityFactory(Generic[E, ID]):
    """
    Factory for creating entities.
    """
    
    def __init__(
        self,
        entity_class: Type[E],
        id_generator: Callable[[], ID],
    ):
        self._entity_class = entity_class
        self._id_generator = id_generator
    
    def create(self, **kwargs: Any) -> E:
        """Create a new entity."""
        entity_id = self._id_generator()
        return self._entity_class(entity_id, **kwargs)
    
    def create_with_id(self, id: ID, **kwargs: Any) -> E:
        """Create entity with specific ID."""
        return self._entity_class(id, **kwargs)


class EntityBuilder(Generic[E]):
    """
    Builder for entities.
    """
    
    def __init__(self, entity_class: Type[E]):
        self._entity_class = entity_class
        self._attributes: Dict[str, Any] = {}
        self._id: Optional[Any] = None
    
    def with_id(self, id: Any) -> "EntityBuilder[E]":
        """Set entity ID."""
        self._id = id
        return self
    
    def with_attribute(
        self,
        name: str,
        value: Any,
    ) -> "EntityBuilder[E]":
        """Set an attribute."""
        self._attributes[name] = value
        return self
    
    def with_attributes(
        self,
        **kwargs: Any,
    ) -> "EntityBuilder[E]":
        """Set multiple attributes."""
        self._attributes.update(kwargs)
        return self
    
    def build(self) -> E:
        """Build the entity."""
        if self._id is None:
            raise EntityError("Entity ID is required")
        
        return self._entity_class(self._id, **self._attributes)


class EntityRegistry:
    """
    Registry for tracking entity instances.
    """
    
    def __init__(self):
        self._entities: Dict[Any, Entity] = {}
        self._dirty: set = set()
        self._removed: set = set()
    
    def register(self, entity: Entity) -> None:
        """Register an entity."""
        self._entities[entity.id] = entity
    
    def get(self, id: Any) -> Optional[Entity]:
        """Get entity by ID."""
        return self._entities.get(id)
    
    def contains(self, id: Any) -> bool:
        """Check if entity is registered."""
        return id in self._entities
    
    def mark_dirty(self, entity: Entity) -> None:
        """Mark entity as dirty."""
        self._dirty.add(entity.id)
    
    def mark_removed(self, entity: Entity) -> None:
        """Mark entity for removal."""
        self._removed.add(entity.id)
    
    def get_dirty(self) -> List[Entity]:
        """Get dirty entities."""
        return [
            self._entities[id] for id in self._dirty
            if id in self._entities
        ]
    
    def get_removed(self) -> List[Entity]:
        """Get removed entities."""
        return [
            self._entities[id] for id in self._removed
            if id in self._entities
        ]
    
    def clear(self) -> None:
        """Clear registry."""
        self._entities.clear()
        self._dirty.clear()
        self._removed.clear()


class IdentityMap(Generic[ID, E]):
    """
    Identity map pattern for caching entities.
    """
    
    def __init__(self):
        self._map: Dict[ID, E] = {}
    
    def get(self, id: ID) -> Optional[E]:
        """Get entity by ID."""
        return self._map.get(id)
    
    def add(self, entity: E) -> None:
        """Add entity to map."""
        self._map[entity.id] = entity
    
    def remove(self, id: ID) -> None:
        """Remove entity from map."""
        self._map.pop(id, None)
    
    def contains(self, id: ID) -> bool:
        """Check if entity exists."""
        return id in self._map
    
    def get_or_add(
        self,
        id: ID,
        factory: Callable[[], E],
    ) -> E:
        """Get existing or create new entity."""
        if id not in self._map:
            self._map[id] = factory()
        return self._map[id]
    
    def clear(self) -> None:
        """Clear the map."""
        self._map.clear()
    
    def __len__(self) -> int:
        return len(self._map)


# Decorators
def entity(id_type: Type[EntityId]) -> Callable[[Type], Type]:
    """
    Class decorator to mark as entity.
    
    Example:
        @entity(UuidId)
        class Product:
            name: str
            price: float
    """
    def decorator(cls: Type) -> Type:
        cls._entity_id_type = id_type
        return cls
    
    return decorator


def auditable(cls: Type[E]) -> Type[E]:
    """
    Class decorator to add audit capabilities.
    
    Example:
        @auditable
        class Order(Entity[OrderId]):
            ...
    """
    original_init = cls.__init__
    
    def new_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self._audit_log = []
    
    def add_audit(self, action: str, details: Optional[Dict] = None):
        self._audit_log.append({
            "action": action,
            "timestamp": datetime.now(),
            "details": details or {},
        })
    
    cls.__init__ = new_init
    cls.add_audit = add_audit
    
    return cls


def versioned(cls: Type[E]) -> Type[E]:
    """
    Class decorator to add version tracking.
    
    Example:
        @versioned
        class Document(Entity[DocumentId]):
            ...
    """
    original_mark_modified = cls.mark_modified
    
    def new_mark_modified(self):
        original_mark_modified(self)
        self.increment_version()
    
    cls.mark_modified = new_mark_modified
    
    return cls


# Factory functions
def create_string_id(value: Optional[str] = None) -> StringId:
    """Create a string ID."""
    if value:
        return StringId.from_string(value)
    return StringId.generate()


def create_uuid_id(value: Optional[str] = None) -> UuidId:
    """Create a UUID ID."""
    if value:
        return UuidId(value)
    return UuidId.generate()


def create_int_id(value: int) -> IntId:
    """Create an integer ID."""
    return IntId.from_int(value)


def create_composite_id(*parts: Any) -> CompositeId:
    """Create a composite ID."""
    return CompositeId(*parts)


def create_entity_factory(
    entity_class: Type[E],
    id_class: Type[ID] = UuidId,
) -> EntityFactory[E, ID]:
    """Create an entity factory."""
    return EntityFactory(
        entity_class,
        id_class.generate,
    )


def create_identity_map() -> IdentityMap:
    """Create an identity map."""
    return IdentityMap()


def create_entity_registry() -> EntityRegistry:
    """Create an entity registry."""
    return EntityRegistry()


__all__ = [
    # Exceptions
    "EntityError",
    "InvalidIdError",
    "EntityStateError",
    # Enums
    "EntityLifecycle",
    # Identity classes
    "EntityId",
    "StringId",
    "UuidId",
    "IntId",
    "CompositeId",
    # Data classes
    "EntityMetadata",
    # Entity classes
    "Entity",
    "AuditableEntity",
    "SoftDeleteEntity",
    "VersionedEntity",
    # Utility classes
    "EntityFactory",
    "EntityBuilder",
    "EntityRegistry",
    "IdentityMap",
    # Decorators
    "entity",
    "auditable",
    "versioned",
    # Factory functions
    "create_string_id",
    "create_uuid_id",
    "create_int_id",
    "create_composite_id",
    "create_entity_factory",
    "create_identity_map",
    "create_entity_registry",
]
