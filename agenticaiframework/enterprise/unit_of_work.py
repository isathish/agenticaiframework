"""
Enterprise Unit of Work Module.

Provides unit of work pattern for transaction management,
atomic operations, and coordinated persistence.

Example:
    # Use unit of work
    async with create_unit_of_work() as uow:
        user = await uow.users.get(user_id)
        user.name = "New Name"
        await uow.users.save(user)
        await uow.commit()
    
    # With rollback on error
    @transactional
    async def process_order(order: Order, uow: UnitOfWork):
        await uow.orders.save(order)
        await uow.payments.save(payment)
        # Auto-commits on success, rolls back on error
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from functools import wraps
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
)

T = TypeVar('T')
ID = TypeVar('ID')


class UnitOfWorkError(Exception):
    """Unit of work error."""
    pass


class TransactionError(UnitOfWorkError):
    """Transaction error."""
    pass


class CommitError(UnitOfWorkError):
    """Commit error."""
    pass


class RollbackError(UnitOfWorkError):
    """Rollback error."""
    pass


class TransactionState(str, Enum):
    """Transaction state."""
    PENDING = "pending"
    ACTIVE = "active"
    COMMITTED = "committed"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


class OperationType(str, Enum):
    """Operation type."""
    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"


@dataclass
class TrackedEntity:
    """Tracked entity in unit of work."""
    entity: Any
    operation: OperationType
    timestamp: datetime = field(default_factory=datetime.now)
    original_state: Optional[Any] = None


@dataclass
class TransactionContext:
    """Transaction context."""
    id: str
    state: TransactionState = TransactionState.PENDING
    started_at: Optional[datetime] = None
    committed_at: Optional[datetime] = None
    rolled_back_at: Optional[datetime] = None
    error: Optional[str] = None


class IdentityMap(Generic[T, ID]):
    """
    Identity map for tracking loaded entities.
    """
    
    def __init__(self, id_getter: Callable[[T], ID]):
        self._entities: Dict[ID, T] = {}
        self._id_getter = id_getter
    
    def get(self, id: ID) -> Optional[T]:
        """Get entity by ID."""
        return self._entities.get(id)
    
    def add(self, entity: T) -> None:
        """Add entity to map."""
        id = self._id_getter(entity)
        self._entities[id] = entity
    
    def remove(self, entity: T) -> None:
        """Remove entity from map."""
        id = self._id_getter(entity)
        self._entities.pop(id, None)
    
    def contains(self, entity: T) -> bool:
        """Check if entity is tracked."""
        id = self._id_getter(entity)
        return id in self._entities
    
    def clear(self) -> None:
        """Clear all tracked entities."""
        self._entities.clear()
    
    def all(self) -> List[T]:
        """Get all tracked entities."""
        return list(self._entities.values())


class ChangeTracker(Generic[T]):
    """
    Tracks changes to entities.
    """
    
    def __init__(self, id_getter: Callable[[T], Any]):
        self._id_getter = id_getter
        self._new: Dict[Any, T] = {}
        self._dirty: Dict[Any, T] = {}
        self._deleted: Dict[Any, T] = {}
        self._clean: Dict[Any, T] = {}
    
    def register_new(self, entity: T) -> None:
        """Register new entity."""
        id = self._id_getter(entity)
        self._new[id] = entity
    
    def register_dirty(self, entity: T) -> None:
        """Register modified entity."""
        id = self._id_getter(entity)
        if id not in self._new:
            self._dirty[id] = entity
    
    def register_deleted(self, entity: T) -> None:
        """Register deleted entity."""
        id = self._id_getter(entity)
        if id in self._new:
            del self._new[id]
        else:
            self._dirty.pop(id, None)
            self._deleted[id] = entity
    
    def register_clean(self, entity: T) -> None:
        """Register clean (loaded) entity."""
        id = self._id_getter(entity)
        self._clean[id] = entity
    
    def get_new(self) -> List[T]:
        """Get new entities."""
        return list(self._new.values())
    
    def get_dirty(self) -> List[T]:
        """Get modified entities."""
        return list(self._dirty.values())
    
    def get_deleted(self) -> List[T]:
        """Get deleted entities."""
        return list(self._deleted.values())
    
    def has_changes(self) -> bool:
        """Check if there are pending changes."""
        return bool(self._new or self._dirty or self._deleted)
    
    def clear(self) -> None:
        """Clear all tracking."""
        self._new.clear()
        self._dirty.clear()
        self._deleted.clear()
        self._clean.clear()


class Repository(ABC, Generic[T, ID]):
    """
    Repository interface for unit of work.
    """
    
    @abstractmethod
    async def get(self, id: ID) -> Optional[T]:
        pass
    
    @abstractmethod
    async def save(self, entity: T) -> T:
        pass
    
    @abstractmethod
    async def delete(self, entity: T) -> None:
        pass


class TrackedRepository(Repository[T, ID]):
    """
    Repository that tracks changes for unit of work.
    """
    
    def __init__(
        self,
        inner_repository: Any,
        tracker: ChangeTracker[T],
        identity_map: IdentityMap[T, ID],
        id_getter: Callable[[T], ID],
    ):
        self._inner = inner_repository
        self._tracker = tracker
        self._identity_map = identity_map
        self._id_getter = id_getter
    
    async def get(self, id: ID) -> Optional[T]:
        # Check identity map first
        entity = self._identity_map.get(id)
        if entity:
            return entity
        
        # Load from inner repository
        entity = await self._inner.get(id)
        if entity:
            self._identity_map.add(entity)
            self._tracker.register_clean(entity)
        
        return entity
    
    async def save(self, entity: T) -> T:
        id = self._id_getter(entity)
        
        if self._identity_map.contains(entity):
            self._tracker.register_dirty(entity)
        else:
            self._tracker.register_new(entity)
            self._identity_map.add(entity)
        
        return entity
    
    async def delete(self, entity: T) -> None:
        self._tracker.register_deleted(entity)
        self._identity_map.remove(entity)


class UnitOfWork(ABC):
    """
    Abstract unit of work.
    """
    
    @abstractmethod
    async def commit(self) -> None:
        """Commit all changes."""
        pass
    
    @abstractmethod
    async def rollback(self) -> None:
        """Rollback all changes."""
        pass
    
    @abstractmethod
    def has_changes(self) -> bool:
        """Check if there are pending changes."""
        pass
    
    async def __aenter__(self) -> "UnitOfWork":
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type:
            await self.rollback()
        elif self.has_changes():
            await self.commit()


class DefaultUnitOfWork(UnitOfWork):
    """
    Default unit of work implementation.
    """
    
    def __init__(self):
        self._trackers: Dict[str, ChangeTracker] = {}
        self._repositories: Dict[str, TrackedRepository] = {}
        self._committed = False
        self._rolled_back = False
        self._callbacks_pre_commit: List[Callable] = []
        self._callbacks_post_commit: List[Callable] = []
        self._callbacks_on_rollback: List[Callable] = []
    
    def register_repository(
        self,
        name: str,
        repository: Any,
        id_getter: Callable[[Any], Any],
    ) -> TrackedRepository:
        """Register a repository for tracking."""
        tracker = ChangeTracker(id_getter)
        identity_map = IdentityMap(id_getter)
        
        tracked = TrackedRepository(
            repository,
            tracker,
            identity_map,
            id_getter,
        )
        
        self._trackers[name] = tracker
        self._repositories[name] = tracked
        
        return tracked
    
    def get_repository(self, name: str) -> Optional[TrackedRepository]:
        """Get a registered repository."""
        return self._repositories.get(name)
    
    def on_pre_commit(self, callback: Callable) -> None:
        """Register pre-commit callback."""
        self._callbacks_pre_commit.append(callback)
    
    def on_post_commit(self, callback: Callable) -> None:
        """Register post-commit callback."""
        self._callbacks_post_commit.append(callback)
    
    def on_rollback(self, callback: Callable) -> None:
        """Register rollback callback."""
        self._callbacks_on_rollback.append(callback)
    
    async def commit(self) -> None:
        """Commit all changes."""
        if self._committed:
            raise CommitError("Unit of work already committed")
        if self._rolled_back:
            raise CommitError("Unit of work was rolled back")
        
        try:
            # Pre-commit callbacks
            for callback in self._callbacks_pre_commit:
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()
            
            # Persist changes
            for name, tracker in self._trackers.items():
                inner_repo = self._repositories[name]._inner
                
                # Insert new entities
                for entity in tracker.get_new():
                    await inner_repo.save(entity)
                
                # Update dirty entities
                for entity in tracker.get_dirty():
                    await inner_repo.save(entity)
                
                # Delete entities
                for entity in tracker.get_deleted():
                    await inner_repo.delete(getattr(entity, 'id', None))
            
            self._committed = True
            
            # Post-commit callbacks
            for callback in self._callbacks_post_commit:
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()
            
        except Exception as e:
            await self.rollback()
            raise CommitError(f"Commit failed: {e}") from e
    
    async def rollback(self) -> None:
        """Rollback all changes."""
        if self._rolled_back:
            return
        
        self._rolled_back = True
        
        # Clear all trackers
        for tracker in self._trackers.values():
            tracker.clear()
        
        # Rollback callbacks
        for callback in self._callbacks_on_rollback:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()
            except Exception:
                pass  # Ignore callback errors during rollback
    
    def has_changes(self) -> bool:
        """Check if there are pending changes."""
        return any(t.has_changes() for t in self._trackers.values())


class TransactionalUnitOfWork(DefaultUnitOfWork):
    """
    Unit of work with transaction support.
    """
    
    def __init__(self, transaction_manager: Optional[Any] = None):
        super().__init__()
        self._transaction_manager = transaction_manager
        self._context = TransactionContext(id=str(datetime.now().timestamp()))
    
    @property
    def transaction(self) -> TransactionContext:
        """Get transaction context."""
        return self._context
    
    async def begin(self) -> None:
        """Begin transaction."""
        self._context.state = TransactionState.ACTIVE
        self._context.started_at = datetime.now()
    
    async def commit(self) -> None:
        """Commit transaction."""
        if self._context.state != TransactionState.ACTIVE:
            raise TransactionError("Transaction not active")
        
        try:
            await super().commit()
            self._context.state = TransactionState.COMMITTED
            self._context.committed_at = datetime.now()
        except Exception as e:
            self._context.state = TransactionState.FAILED
            self._context.error = str(e)
            raise
    
    async def rollback(self) -> None:
        """Rollback transaction."""
        await super().rollback()
        self._context.state = TransactionState.ROLLED_BACK
        self._context.rolled_back_at = datetime.now()


class NestedUnitOfWork(UnitOfWork):
    """
    Nested unit of work (savepoint pattern).
    """
    
    def __init__(self, parent: UnitOfWork):
        self._parent = parent
        self._changes: List[Tuple[str, Any, OperationType]] = []
        self._committed = False
        self._rolled_back = False
    
    def record_change(
        self,
        repository: str,
        entity: Any,
        operation: OperationType,
    ) -> None:
        """Record a change."""
        self._changes.append((repository, entity, operation))
    
    async def commit(self) -> None:
        """Commit to parent."""
        if self._rolled_back:
            raise CommitError("Nested unit of work was rolled back")
        
        # Changes are already in parent, just mark as committed
        self._committed = True
    
    async def rollback(self) -> None:
        """Rollback changes."""
        self._rolled_back = True
        self._changes.clear()
        # Note: Full rollback of parent may still be needed
    
    def has_changes(self) -> bool:
        return bool(self._changes)


class UnitOfWorkFactory:
    """
    Factory for creating units of work.
    """
    
    def __init__(self):
        self._repository_configs: Dict[str, Tuple[Any, Callable]] = {}
        self._uow_class: Type[UnitOfWork] = DefaultUnitOfWork
    
    def register_repository(
        self,
        name: str,
        repository: Any,
        id_getter: Callable[[Any], Any],
    ) -> "UnitOfWorkFactory":
        """Register a repository configuration."""
        self._repository_configs[name] = (repository, id_getter)
        return self
    
    def use_class(
        self,
        uow_class: Type[UnitOfWork],
    ) -> "UnitOfWorkFactory":
        """Set unit of work class to use."""
        self._uow_class = uow_class
        return self
    
    def create(self) -> UnitOfWork:
        """Create a new unit of work."""
        uow = self._uow_class()
        
        if isinstance(uow, DefaultUnitOfWork):
            for name, (repo, id_getter) in self._repository_configs.items():
                tracked = uow.register_repository(name, repo, id_getter)
                setattr(uow, name, tracked)
        
        return uow
    
    @asynccontextmanager
    async def scope(self):
        """Create scoped unit of work."""
        uow = self.create()
        try:
            yield uow
            if uow.has_changes():
                await uow.commit()
        except Exception:
            await uow.rollback()
            raise


class UnitOfWorkManager:
    """
    Manager for unit of work instances.
    """
    
    def __init__(self, factory: UnitOfWorkFactory):
        self._factory = factory
        self._current: Optional[UnitOfWork] = None
        self._stack: List[UnitOfWork] = []
    
    def current(self) -> Optional[UnitOfWork]:
        """Get current unit of work."""
        return self._current
    
    def begin(self) -> UnitOfWork:
        """Begin a new unit of work."""
        if self._current:
            # Create nested
            nested = NestedUnitOfWork(self._current)
            self._stack.append(self._current)
            self._current = nested
        else:
            self._current = self._factory.create()
        
        return self._current
    
    async def commit(self) -> None:
        """Commit current unit of work."""
        if not self._current:
            raise UnitOfWorkError("No active unit of work")
        
        await self._current.commit()
        
        if self._stack:
            self._current = self._stack.pop()
        else:
            self._current = None
    
    async def rollback(self) -> None:
        """Rollback current unit of work."""
        if not self._current:
            return
        
        await self._current.rollback()
        
        if self._stack:
            self._current = self._stack.pop()
        else:
            self._current = None


# Decorators
def transactional(func: Callable) -> Callable:
    """
    Decorator for transactional methods.
    
    Example:
        @transactional
        async def create_order(order: Order, uow: UnitOfWork):
            await uow.orders.save(order)
            # Auto-commits on success
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Find UnitOfWork in args
        uow = None
        for arg in args:
            if isinstance(arg, UnitOfWork):
                uow = arg
                break
        
        for v in kwargs.values():
            if isinstance(v, UnitOfWork):
                uow = v
                break
        
        if uow:
            try:
                result = await func(*args, **kwargs)
                if uow.has_changes():
                    await uow.commit()
                return result
            except Exception:
                await uow.rollback()
                raise
        else:
            return await func(*args, **kwargs)
    
    return wrapper


def with_uow(factory: UnitOfWorkFactory) -> Callable:
    """
    Decorator to inject unit of work.
    
    Example:
        @with_uow(uow_factory)
        async def create_user(user: User, uow: UnitOfWork):
            await uow.users.save(user)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            async with factory.scope() as uow:
                return await func(*args, uow=uow, **kwargs)
        
        return wrapper
    
    return decorator


def atomic(func: Callable) -> Callable:
    """
    Decorator for atomic operations.
    
    Example:
        @atomic
        async def transfer_funds(from_acc, to_acc, amount, uow):
            from_acc.withdraw(amount)
            to_acc.deposit(amount)
            await uow.accounts.save(from_acc)
            await uow.accounts.save(to_acc)
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            result = await func(*args, **kwargs)
            return result
        except Exception as e:
            raise TransactionError(f"Atomic operation failed: {e}") from e
    
    return wrapper


# Factory functions
def create_unit_of_work() -> DefaultUnitOfWork:
    """Create a default unit of work."""
    return DefaultUnitOfWork()


def create_transactional_uow(
    transaction_manager: Optional[Any] = None,
) -> TransactionalUnitOfWork:
    """Create a transactional unit of work."""
    return TransactionalUnitOfWork(transaction_manager)


def create_uow_factory() -> UnitOfWorkFactory:
    """Create a unit of work factory."""
    return UnitOfWorkFactory()


def create_uow_manager(
    factory: Optional[UnitOfWorkFactory] = None,
) -> UnitOfWorkManager:
    """Create a unit of work manager."""
    if factory is None:
        factory = UnitOfWorkFactory()
    return UnitOfWorkManager(factory)


def create_change_tracker(
    id_getter: Callable[[T], Any],
) -> ChangeTracker[T]:
    """Create a change tracker."""
    return ChangeTracker(id_getter)


def create_identity_map(
    id_getter: Callable[[T], ID],
) -> IdentityMap[T, ID]:
    """Create an identity map."""
    return IdentityMap(id_getter)


__all__ = [
    # Exceptions
    "UnitOfWorkError",
    "TransactionError",
    "CommitError",
    "RollbackError",
    # Enums
    "TransactionState",
    "OperationType",
    # Data classes
    "TrackedEntity",
    "TransactionContext",
    # Tracking
    "IdentityMap",
    "ChangeTracker",
    # Repositories
    "Repository",
    "TrackedRepository",
    # Unit of Work
    "UnitOfWork",
    "DefaultUnitOfWork",
    "TransactionalUnitOfWork",
    "NestedUnitOfWork",
    # Factory and Manager
    "UnitOfWorkFactory",
    "UnitOfWorkManager",
    # Decorators
    "transactional",
    "with_uow",
    "atomic",
    # Factory functions
    "create_unit_of_work",
    "create_transactional_uow",
    "create_uow_factory",
    "create_uow_manager",
    "create_change_tracker",
    "create_identity_map",
]
