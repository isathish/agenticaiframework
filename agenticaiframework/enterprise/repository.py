"""
Enterprise Repository Module.

Provides repository pattern for data access abstraction,
query encapsulation, and aggregate persistence.

Example:
    # Define a repository
    class UserRepository(Repository[User, UserId]):
        async def find_by_email(self, email: str) -> Optional[User]:
            return await self._store.find_one(email=email)
    
    # Use repository
    repo = create_repository(User, InMemoryStore())
    await repo.save(user)
    user = await repo.get(user_id)
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import (
    Any,
    AsyncIterator,
    Callable,
    Dict,
    Generic,
    Iterable,
    List,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
)

T = TypeVar('T')  # Entity type
ID = TypeVar('ID')  # Identity type
R = TypeVar('R', bound='Repository')


class RepositoryError(Exception):
    """Repository error."""
    pass


class EntityNotFoundError(RepositoryError):
    """Entity not found error."""
    pass


class DuplicateEntityError(RepositoryError):
    """Duplicate entity error."""
    pass


class ConcurrencyError(RepositoryError):
    """Concurrency conflict error."""
    pass


class SortDirection(str, Enum):
    """Sort direction."""
    ASC = "asc"
    DESC = "desc"


@dataclass
class SortCriteria:
    """Sort criteria."""
    field: str
    direction: SortDirection = SortDirection.ASC


@dataclass
class QueryOptions:
    """Query options for filtering, sorting, and pagination."""
    filters: Dict[str, Any] = field(default_factory=dict)
    sort: List[SortCriteria] = field(default_factory=list)
    skip: int = 0
    limit: Optional[int] = None
    include_deleted: bool = False


@dataclass
class PagedResult(Generic[T]):
    """Paged query result."""
    items: List[T]
    total: int
    page: int
    page_size: int
    has_next: bool
    has_previous: bool
    
    @property
    def total_pages(self) -> int:
        if self.page_size <= 0:
            return 0
        return (self.total + self.page_size - 1) // self.page_size


class Repository(ABC, Generic[T, ID]):
    """
    Base repository interface.
    """
    
    @abstractmethod
    async def get(self, id: ID) -> Optional[T]:
        """Get entity by ID."""
        pass
    
    @abstractmethod
    async def get_all(self) -> List[T]:
        """Get all entities."""
        pass
    
    @abstractmethod
    async def save(self, entity: T) -> T:
        """Save entity (insert or update)."""
        pass
    
    @abstractmethod
    async def delete(self, id: ID) -> bool:
        """Delete entity by ID."""
        pass
    
    @abstractmethod
    async def exists(self, id: ID) -> bool:
        """Check if entity exists."""
        pass
    
    @abstractmethod
    async def count(self) -> int:
        """Count all entities."""
        pass


class ReadOnlyRepository(ABC, Generic[T, ID]):
    """
    Read-only repository interface.
    """
    
    @abstractmethod
    async def get(self, id: ID) -> Optional[T]:
        """Get entity by ID."""
        pass
    
    @abstractmethod
    async def get_all(self) -> List[T]:
        """Get all entities."""
        pass
    
    @abstractmethod
    async def exists(self, id: ID) -> bool:
        """Check if entity exists."""
        pass
    
    @abstractmethod
    async def count(self) -> int:
        """Count all entities."""
        pass


class QueryRepository(Repository[T, ID]):
    """
    Repository with query capabilities.
    """
    
    @abstractmethod
    async def find(
        self,
        options: Optional[QueryOptions] = None,
    ) -> List[T]:
        """Find entities with options."""
        pass
    
    @abstractmethod
    async def find_one(self, **criteria: Any) -> Optional[T]:
        """Find single entity matching criteria."""
        pass
    
    @abstractmethod
    async def find_by(
        self,
        field: str,
        value: Any,
    ) -> List[T]:
        """Find entities by field value."""
        pass
    
    @abstractmethod
    async def find_paged(
        self,
        page: int,
        page_size: int,
        options: Optional[QueryOptions] = None,
    ) -> PagedResult[T]:
        """Find entities with pagination."""
        pass


class DataStore(ABC, Generic[T, ID]):
    """
    Abstract data store interface.
    """
    
    @abstractmethod
    async def get(self, id: ID) -> Optional[T]:
        pass
    
    @abstractmethod
    async def get_all(self) -> List[T]:
        pass
    
    @abstractmethod
    async def insert(self, entity: T) -> T:
        pass
    
    @abstractmethod
    async def update(self, entity: T) -> T:
        pass
    
    @abstractmethod
    async def delete(self, id: ID) -> bool:
        pass
    
    @abstractmethod
    async def exists(self, id: ID) -> bool:
        pass
    
    @abstractmethod
    async def count(self) -> int:
        pass
    
    @abstractmethod
    async def find(
        self,
        options: Optional[QueryOptions] = None,
    ) -> List[T]:
        pass


class InMemoryStore(DataStore[T, ID]):
    """
    In-memory data store implementation.
    """
    
    def __init__(self, id_getter: Optional[Callable[[T], ID]] = None):
        self._data: Dict[ID, T] = {}
        self._id_getter = id_getter or (lambda e: getattr(e, 'id'))
    
    async def get(self, id: ID) -> Optional[T]:
        return self._data.get(id)
    
    async def get_all(self) -> List[T]:
        return list(self._data.values())
    
    async def insert(self, entity: T) -> T:
        id = self._id_getter(entity)
        if id in self._data:
            raise DuplicateEntityError(f"Entity with ID {id} already exists")
        self._data[id] = entity
        return entity
    
    async def update(self, entity: T) -> T:
        id = self._id_getter(entity)
        if id not in self._data:
            raise EntityNotFoundError(f"Entity with ID {id} not found")
        self._data[id] = entity
        return entity
    
    async def delete(self, id: ID) -> bool:
        if id in self._data:
            del self._data[id]
            return True
        return False
    
    async def exists(self, id: ID) -> bool:
        return id in self._data
    
    async def count(self) -> int:
        return len(self._data)
    
    async def find(
        self,
        options: Optional[QueryOptions] = None,
    ) -> List[T]:
        result = list(self._data.values())
        
        if options:
            # Apply filters
            if options.filters:
                result = [
                    e for e in result
                    if self._matches_filters(e, options.filters)
                ]
            
            # Apply sorting
            if options.sort:
                for criteria in reversed(options.sort):
                    reverse = criteria.direction == SortDirection.DESC
                    result.sort(
                        key=lambda e: getattr(e, criteria.field, None),
                        reverse=reverse,
                    )
            
            # Apply pagination
            if options.skip:
                result = result[options.skip:]
            if options.limit:
                result = result[:options.limit]
        
        return result
    
    def _matches_filters(
        self,
        entity: T,
        filters: Dict[str, Any],
    ) -> bool:
        for field, value in filters.items():
            entity_value = getattr(entity, field, None)
            if entity_value != value:
                return False
        return True


class GenericRepository(QueryRepository[T, ID]):
    """
    Generic repository implementation.
    """
    
    def __init__(
        self,
        store: DataStore[T, ID],
        id_getter: Optional[Callable[[T], ID]] = None,
    ):
        self._store = store
        self._id_getter = id_getter or (lambda e: getattr(e, 'id'))
    
    async def get(self, id: ID) -> Optional[T]:
        return await self._store.get(id)
    
    async def get_all(self) -> List[T]:
        return await self._store.get_all()
    
    async def save(self, entity: T) -> T:
        id = self._id_getter(entity)
        if await self._store.exists(id):
            return await self._store.update(entity)
        else:
            return await self._store.insert(entity)
    
    async def delete(self, id: ID) -> bool:
        return await self._store.delete(id)
    
    async def exists(self, id: ID) -> bool:
        return await self._store.exists(id)
    
    async def count(self) -> int:
        return await self._store.count()
    
    async def find(
        self,
        options: Optional[QueryOptions] = None,
    ) -> List[T]:
        return await self._store.find(options)
    
    async def find_one(self, **criteria: Any) -> Optional[T]:
        options = QueryOptions(filters=criteria, limit=1)
        result = await self._store.find(options)
        return result[0] if result else None
    
    async def find_by(
        self,
        field: str,
        value: Any,
    ) -> List[T]:
        options = QueryOptions(filters={field: value})
        return await self._store.find(options)
    
    async def find_paged(
        self,
        page: int,
        page_size: int,
        options: Optional[QueryOptions] = None,
    ) -> PagedResult[T]:
        # Get total count
        total = await self._store.count()
        
        # Build options with pagination
        query_options = QueryOptions(
            filters=options.filters if options else {},
            sort=options.sort if options else [],
            skip=(page - 1) * page_size,
            limit=page_size,
        )
        
        items = await self._store.find(query_options)
        
        return PagedResult(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            has_next=page * page_size < total,
            has_previous=page > 1,
        )


class CachingRepository(QueryRepository[T, ID]):
    """
    Repository with caching layer.
    """
    
    def __init__(
        self,
        repository: QueryRepository[T, ID],
        cache_ttl: float = 300.0,
    ):
        self._repository = repository
        self._cache_ttl = cache_ttl
        self._cache: Dict[ID, Tuple[T, float]] = {}
        self._list_cache: Optional[Tuple[List[T], float]] = None
    
    async def get(self, id: ID) -> Optional[T]:
        # Check cache
        if id in self._cache:
            entity, cached_at = self._cache[id]
            if self._is_valid(cached_at):
                return entity
            del self._cache[id]
        
        # Fetch from repository
        entity = await self._repository.get(id)
        if entity:
            self._cache[id] = (entity, asyncio.get_event_loop().time())
        return entity
    
    async def get_all(self) -> List[T]:
        if self._list_cache:
            items, cached_at = self._list_cache
            if self._is_valid(cached_at):
                return items
        
        items = await self._repository.get_all()
        self._list_cache = (items, asyncio.get_event_loop().time())
        return items
    
    async def save(self, entity: T) -> T:
        result = await self._repository.save(entity)
        self._invalidate()
        return result
    
    async def delete(self, id: ID) -> bool:
        result = await self._repository.delete(id)
        self._invalidate()
        return result
    
    async def exists(self, id: ID) -> bool:
        return await self._repository.exists(id)
    
    async def count(self) -> int:
        return await self._repository.count()
    
    async def find(
        self,
        options: Optional[QueryOptions] = None,
    ) -> List[T]:
        return await self._repository.find(options)
    
    async def find_one(self, **criteria: Any) -> Optional[T]:
        return await self._repository.find_one(**criteria)
    
    async def find_by(
        self,
        field: str,
        value: Any,
    ) -> List[T]:
        return await self._repository.find_by(field, value)
    
    async def find_paged(
        self,
        page: int,
        page_size: int,
        options: Optional[QueryOptions] = None,
    ) -> PagedResult[T]:
        return await self._repository.find_paged(page, page_size, options)
    
    def _is_valid(self, cached_at: float) -> bool:
        return asyncio.get_event_loop().time() - cached_at < self._cache_ttl
    
    def _invalidate(self) -> None:
        self._cache.clear()
        self._list_cache = None


class SpecificationRepository(GenericRepository[T, ID]):
    """
    Repository with specification pattern support.
    """
    
    async def find_by_spec(
        self,
        specification: Any,  # Specification[T]
    ) -> List[T]:
        """Find entities matching specification."""
        all_entities = await self._store.get_all()
        return [e for e in all_entities if specification.is_satisfied_by(e)]
    
    async def find_one_by_spec(
        self,
        specification: Any,
    ) -> Optional[T]:
        """Find single entity matching specification."""
        result = await self.find_by_spec(specification)
        return result[0] if result else None
    
    async def count_by_spec(
        self,
        specification: Any,
    ) -> int:
        """Count entities matching specification."""
        return len(await self.find_by_spec(specification))


class AuditingRepository(GenericRepository[T, ID]):
    """
    Repository with audit logging.
    """
    
    def __init__(
        self,
        store: DataStore[T, ID],
        id_getter: Optional[Callable[[T], ID]] = None,
        audit_logger: Optional[Callable[[str, T], None]] = None,
    ):
        super().__init__(store, id_getter)
        self._audit = audit_logger or self._default_audit
    
    async def save(self, entity: T) -> T:
        id = self._id_getter(entity)
        exists = await self._store.exists(id)
        result = await super().save(entity)
        
        if exists:
            self._audit("UPDATE", result)
        else:
            self._audit("INSERT", result)
        
        return result
    
    async def delete(self, id: ID) -> bool:
        entity = await self._store.get(id)
        result = await super().delete(id)
        
        if result and entity:
            self._audit("DELETE", entity)
        
        return result
    
    def _default_audit(self, action: str, entity: T) -> None:
        logging.getLogger(__name__).info("[AUDIT] %s: %s", action, entity)


class BatchRepository(GenericRepository[T, ID]):
    """
    Repository with batch operations.
    """
    
    async def save_many(self, entities: List[T]) -> List[T]:
        """Save multiple entities."""
        results = []
        for entity in entities:
            result = await self.save(entity)
            results.append(result)
        return results
    
    async def delete_many(self, ids: List[ID]) -> int:
        """Delete multiple entities."""
        count = 0
        for id in ids:
            if await self.delete(id):
                count += 1
        return count
    
    async def get_many(self, ids: List[ID]) -> List[T]:
        """Get multiple entities by IDs."""
        results = []
        for id in ids:
            entity = await self.get(id)
            if entity:
                results.append(entity)
        return results


class SoftDeleteRepository(GenericRepository[T, ID]):
    """
    Repository with soft delete support.
    """
    
    def __init__(
        self,
        store: DataStore[T, ID],
        id_getter: Optional[Callable[[T], ID]] = None,
        deleted_field: str = "deleted_at",
    ):
        super().__init__(store, id_getter)
        self._deleted_field = deleted_field
    
    async def delete(self, id: ID) -> bool:
        entity = await self._store.get(id)
        if entity:
            setattr(entity, self._deleted_field, datetime.now())
            await self._store.update(entity)
            return True
        return False
    
    async def hard_delete(self, id: ID) -> bool:
        """Permanently delete entity."""
        return await self._store.delete(id)
    
    async def restore(self, id: ID) -> Optional[T]:
        """Restore soft-deleted entity."""
        entity = await self._store.get(id)
        if entity:
            setattr(entity, self._deleted_field, None)
            return await self._store.update(entity)
        return None
    
    async def get_deleted(self) -> List[T]:
        """Get all soft-deleted entities."""
        all_entities = await self._store.get_all()
        return [
            e for e in all_entities
            if getattr(e, self._deleted_field, None) is not None
        ]


class VersionedRepository(GenericRepository[T, ID]):
    """
    Repository with optimistic locking.
    """
    
    def __init__(
        self,
        store: DataStore[T, ID],
        id_getter: Optional[Callable[[T], ID]] = None,
        version_field: str = "version",
    ):
        super().__init__(store, id_getter)
        self._version_field = version_field
    
    async def save(self, entity: T) -> T:
        id = self._id_getter(entity)
        existing = await self._store.get(id)
        
        if existing:
            # Check version
            existing_version = getattr(existing, self._version_field, 0)
            entity_version = getattr(entity, self._version_field, 0)
            
            if entity_version != existing_version:
                raise ConcurrencyError(
                    f"Version conflict: expected {existing_version}, "
                    f"got {entity_version}"
                )
            
            # Increment version
            setattr(entity, self._version_field, existing_version + 1)
            return await self._store.update(entity)
        else:
            setattr(entity, self._version_field, 1)
            return await self._store.insert(entity)


class RepositoryRegistry:
    """
    Registry for repositories.
    """
    
    def __init__(self):
        self._repositories: Dict[Type, Repository] = {}
    
    def register(
        self,
        entity_type: Type[T],
        repository: Repository[T, Any],
    ) -> None:
        """Register a repository for an entity type."""
        self._repositories[entity_type] = repository
    
    def get(
        self,
        entity_type: Type[T],
    ) -> Optional[Repository[T, Any]]:
        """Get repository for an entity type."""
        return self._repositories.get(entity_type)
    
    def resolve(
        self,
        entity_type: Type[T],
    ) -> Repository[T, Any]:
        """Resolve repository or raise error."""
        repo = self._repositories.get(entity_type)
        if not repo:
            raise RepositoryError(
                f"No repository registered for {entity_type.__name__}"
            )
        return repo


# Global registry
_global_registry = RepositoryRegistry()


# Decorators
def repository(entity_type: Type) -> Callable[[Type[R]], Type[R]]:
    """
    Class decorator to register repository.
    
    Example:
        @repository(User)
        class UserRepository(GenericRepository[User, UserId]):
            pass
    """
    def decorator(cls: Type[R]) -> Type[R]:
        # Will be registered when instantiated
        cls._entity_type = entity_type
        return cls
    
    return decorator


def cached(ttl: float = 300.0):
    """
    Decorator to add caching to repository method.
    
    Example:
        class UserRepository(GenericRepository[User, UserId]):
            @cached(ttl=60.0)
            async def find_active(self) -> List[User]:
                ...
    """
    def decorator(func: Callable) -> Callable:
        cache: Dict[str, Tuple[Any, float]] = {}
        
        async def wrapper(self, *args, **kwargs):
            key = f"{func.__name__}:{args}:{kwargs}"
            
            if key in cache:
                result, cached_at = cache[key]
                if asyncio.get_event_loop().time() - cached_at < ttl:
                    return result
            
            result = await func(self, *args, **kwargs)
            cache[key] = (result, asyncio.get_event_loop().time())
            return result
        
        return wrapper
    
    return decorator


# Factory functions
def create_in_memory_store(
    id_getter: Optional[Callable[[T], ID]] = None,
) -> InMemoryStore[T, ID]:
    """Create in-memory data store."""
    return InMemoryStore(id_getter)


def create_repository(
    entity_type: Type[T],
    store: Optional[DataStore[T, ID]] = None,
    id_getter: Optional[Callable[[T], ID]] = None,
) -> GenericRepository[T, ID]:
    """Create a generic repository."""
    if store is None:
        store = InMemoryStore(id_getter)
    return GenericRepository(store, id_getter)


def create_caching_repository(
    repository: QueryRepository[T, ID],
    cache_ttl: float = 300.0,
) -> CachingRepository[T, ID]:
    """Create caching repository wrapper."""
    return CachingRepository(repository, cache_ttl)


def create_spec_repository(
    entity_type: Type[T],
    store: Optional[DataStore[T, ID]] = None,
) -> SpecificationRepository[T, ID]:
    """Create specification repository."""
    if store is None:
        store = InMemoryStore()
    return SpecificationRepository(store)


def create_batch_repository(
    entity_type: Type[T],
    store: Optional[DataStore[T, ID]] = None,
) -> BatchRepository[T, ID]:
    """Create batch repository."""
    if store is None:
        store = InMemoryStore()
    return BatchRepository(store)


def create_query_options(
    filters: Optional[Dict[str, Any]] = None,
    sort_by: Optional[str] = None,
    sort_direction: SortDirection = SortDirection.ASC,
    skip: int = 0,
    limit: Optional[int] = None,
) -> QueryOptions:
    """Create query options."""
    sort = []
    if sort_by:
        sort = [SortCriteria(sort_by, sort_direction)]
    
    return QueryOptions(
        filters=filters or {},
        sort=sort,
        skip=skip,
        limit=limit,
    )


def get_repository(entity_type: Type[T]) -> Optional[Repository[T, Any]]:
    """Get repository from global registry."""
    return _global_registry.get(entity_type)


def register_repository(
    entity_type: Type[T],
    repository: Repository[T, Any],
) -> None:
    """Register repository in global registry."""
    _global_registry.register(entity_type, repository)


__all__ = [
    # Exceptions
    "RepositoryError",
    "EntityNotFoundError",
    "DuplicateEntityError",
    "ConcurrencyError",
    # Enums
    "SortDirection",
    # Data classes
    "SortCriteria",
    "QueryOptions",
    "PagedResult",
    # Base interfaces
    "Repository",
    "ReadOnlyRepository",
    "QueryRepository",
    "DataStore",
    # Implementations
    "InMemoryStore",
    "GenericRepository",
    "CachingRepository",
    "SpecificationRepository",
    "AuditingRepository",
    "BatchRepository",
    "SoftDeleteRepository",
    "VersionedRepository",
    # Registry
    "RepositoryRegistry",
    # Decorators
    "repository",
    "cached",
    # Factory functions
    "create_in_memory_store",
    "create_repository",
    "create_caching_repository",
    "create_spec_repository",
    "create_batch_repository",
    "create_query_options",
    "get_repository",
    "register_repository",
]
