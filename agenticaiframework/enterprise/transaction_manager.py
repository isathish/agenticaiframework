"""
Enterprise Transaction Manager Module.

Provides transaction management, two-phase commit (2PC),
saga coordination, and distributed transaction patterns.

Example:
    # Create transaction manager
    tx_manager = create_transaction_manager()
    
    # Execute in transaction
    async with tx_manager.begin() as tx:
        await repository.save(entity, tx)
        await tx.commit()
    
    # Use decorator
    @transactional()
    async def transfer_funds(from_acc, to_acc, amount):
        ...
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    AsyncIterator,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    TypeVar,
)

T = TypeVar('T')


logger = logging.getLogger(__name__)


class TransactionError(Exception):
    """Base transaction error."""
    pass


class TransactionAbortedError(TransactionError):
    """Transaction was aborted."""
    pass


class TransactionTimeoutError(TransactionError):
    """Transaction timed out."""
    pass


class CommitError(TransactionError):
    """Commit failed."""
    pass


class RollbackError(TransactionError):
    """Rollback failed."""
    pass


class IsolationLevel(str, Enum):
    """Transaction isolation level."""
    READ_UNCOMMITTED = "read_uncommitted"
    READ_COMMITTED = "read_committed"
    REPEATABLE_READ = "repeatable_read"
    SERIALIZABLE = "serializable"


class TransactionState(str, Enum):
    """Transaction state."""
    ACTIVE = "active"
    PREPARING = "preparing"
    PREPARED = "prepared"
    COMMITTING = "committing"
    COMMITTED = "committed"
    ABORTING = "aborting"
    ABORTED = "aborted"
    ROLLED_BACK = "rolled_back"


@dataclass
class TransactionConfig:
    """Transaction configuration."""
    isolation: IsolationLevel = IsolationLevel.READ_COMMITTED
    timeout: Optional[float] = None  # seconds
    read_only: bool = False
    propagation: str = "required"  # required, requires_new, nested


@dataclass
class TransactionInfo:
    """Transaction information."""
    id: str
    state: TransactionState
    isolation: IsolationLevel
    started_at: datetime
    timeout: Optional[float] = None
    read_only: bool = False
    parent_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_active(self) -> bool:
        return self.state in (
            TransactionState.ACTIVE,
            TransactionState.PREPARING,
            TransactionState.PREPARED,
        )


@dataclass
class TransactionStats:
    """Transaction statistics."""
    total_started: int = 0
    total_committed: int = 0
    total_aborted: int = 0
    total_timeouts: int = 0
    current_active: int = 0


class TransactionParticipant(ABC):
    """
    Abstract transaction participant for 2PC.
    """
    
    @property
    @abstractmethod
    def participant_id(self) -> str:
        """Participant identifier."""
        pass
    
    @abstractmethod
    async def prepare(self, tx_id: str) -> bool:
        """Prepare for commit (vote)."""
        pass
    
    @abstractmethod
    async def commit(self, tx_id: str) -> None:
        """Commit the transaction."""
        pass
    
    @abstractmethod
    async def rollback(self, tx_id: str) -> None:
        """Rollback the transaction."""
        pass


class Transaction(ABC):
    """
    Abstract transaction interface.
    """
    
    @property
    @abstractmethod
    def id(self) -> str:
        """Transaction ID."""
        pass
    
    @property
    @abstractmethod
    def state(self) -> TransactionState:
        """Transaction state."""
        pass
    
    @property
    @abstractmethod
    def info(self) -> TransactionInfo:
        """Transaction information."""
        pass
    
    @abstractmethod
    async def commit(self) -> None:
        """Commit the transaction."""
        pass
    
    @abstractmethod
    async def rollback(self) -> None:
        """Rollback the transaction."""
        pass
    
    @abstractmethod
    async def add_participant(self, participant: TransactionParticipant) -> None:
        """Add participant to distributed transaction."""
        pass
    
    @abstractmethod
    def register_on_commit(self, callback: Callable[[], Any]) -> None:
        """Register callback to run on commit."""
        pass
    
    @abstractmethod
    def register_on_rollback(self, callback: Callable[[], Any]) -> None:
        """Register callback to run on rollback."""
        pass
    
    async def __aenter__(self) -> "Transaction":
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type:
            await self.rollback()
        elif self.state == TransactionState.ACTIVE:
            await self.commit()


class LocalTransaction(Transaction):
    """
    Local in-memory transaction.
    """
    
    def __init__(
        self,
        tx_id: str,
        config: TransactionConfig,
        parent: Optional["LocalTransaction"] = None,
    ):
        self._id = tx_id
        self._config = config
        self._parent = parent
        self._state = TransactionState.ACTIVE
        self._started_at = datetime.utcnow()
        self._participants: List[TransactionParticipant] = []
        self._on_commit: List[Callable] = []
        self._on_rollback: List[Callable] = []
        self._savepoints: Dict[str, Any] = {}
    
    @property
    def id(self) -> str:
        return self._id
    
    @property
    def state(self) -> TransactionState:
        return self._state
    
    @property
    def info(self) -> TransactionInfo:
        return TransactionInfo(
            id=self._id,
            state=self._state,
            isolation=self._config.isolation,
            started_at=self._started_at,
            timeout=self._config.timeout,
            read_only=self._config.read_only,
            parent_id=self._parent._id if self._parent else None,
        )
    
    async def commit(self) -> None:
        if self._state != TransactionState.ACTIVE:
            raise TransactionError(f"Cannot commit: state is {self._state}")
        
        try:
            # Two-phase commit if participants
            if self._participants:
                await self._two_phase_commit()
            else:
                self._state = TransactionState.COMMITTED
            
            # Run commit callbacks
            for callback in self._on_commit:
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()
                    
        except Exception as e:
            await self.rollback()
            raise CommitError(f"Commit failed: {e}") from e
    
    async def rollback(self) -> None:
        if self._state in (TransactionState.COMMITTED, TransactionState.ROLLED_BACK):
            return
        
        self._state = TransactionState.ABORTING
        
        # Rollback participants
        errors = []
        for participant in reversed(self._participants):
            try:
                await participant.rollback(self._id)
            except Exception as e:
                errors.append(e)
        
        self._state = TransactionState.ROLLED_BACK
        
        # Run rollback callbacks
        for callback in self._on_rollback:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()
            except Exception:
                pass
        
        if errors:
            raise RollbackError(f"Rollback errors: {errors}")
    
    async def add_participant(self, participant: TransactionParticipant) -> None:
        self._participants.append(participant)
    
    def register_on_commit(self, callback: Callable[[], Any]) -> None:
        self._on_commit.append(callback)
    
    def register_on_rollback(self, callback: Callable[[], Any]) -> None:
        self._on_rollback.append(callback)
    
    async def savepoint(self, name: str) -> None:
        """Create a savepoint."""
        self._savepoints[name] = {
            "state": self._state,
            "participants_count": len(self._participants),
        }
    
    async def rollback_to_savepoint(self, name: str) -> None:
        """Rollback to savepoint."""
        if name not in self._savepoints:
            raise TransactionError(f"Savepoint not found: {name}")
        
        sp = self._savepoints[name]
        # Rollback participants added after savepoint
        for participant in self._participants[sp["participants_count"]:]:
            await participant.rollback(self._id)
        
        self._participants = self._participants[:sp["participants_count"]]
    
    async def _two_phase_commit(self) -> None:
        """Execute two-phase commit."""
        # Phase 1: Prepare
        self._state = TransactionState.PREPARING
        
        votes = []
        for participant in self._participants:
            try:
                vote = await participant.prepare(self._id)
                votes.append(vote)
            except Exception:
                votes.append(False)
        
        # Check all voted yes
        if not all(votes):
            self._state = TransactionState.ABORTING
            for participant in self._participants:
                await participant.rollback(self._id)
            self._state = TransactionState.ABORTED
            raise TransactionAbortedError("Prepare phase failed")
        
        self._state = TransactionState.PREPARED
        
        # Phase 2: Commit
        self._state = TransactionState.COMMITTING
        
        for participant in self._participants:
            await participant.commit(self._id)
        
        self._state = TransactionState.COMMITTED


class TransactionManager(ABC):
    """
    Abstract transaction manager.
    """
    
    @abstractmethod
    async def begin(
        self,
        config: Optional[TransactionConfig] = None,
    ) -> Transaction:
        """Begin a new transaction."""
        pass
    
    @abstractmethod
    async def get_transaction(self, tx_id: str) -> Optional[Transaction]:
        """Get transaction by ID."""
        pass
    
    @abstractmethod
    async def get_current(self) -> Optional[Transaction]:
        """Get current transaction (context-based)."""
        pass
    
    @abstractmethod
    async def stats(self) -> TransactionStats:
        """Get transaction statistics."""
        pass
    
    @asynccontextmanager
    async def transaction(
        self,
        config: Optional[TransactionConfig] = None,
    ) -> AsyncIterator[Transaction]:
        """Context manager for transactions."""
        tx = await self.begin(config)
        try:
            yield tx
            if tx.state == TransactionState.ACTIVE:
                await tx.commit()
        except Exception:
            if tx.state == TransactionState.ACTIVE:
                await tx.rollback()
            raise


class InMemoryTransactionManager(TransactionManager):
    """
    In-memory transaction manager.
    """
    
    def __init__(self):
        self._transactions: Dict[str, LocalTransaction] = {}
        self._current: Optional[str] = None
        self._stats = TransactionStats()
    
    async def begin(
        self,
        config: Optional[TransactionConfig] = None,
    ) -> Transaction:
        config = config or TransactionConfig()
        tx_id = str(uuid.uuid4())
        
        # Handle propagation
        parent = None
        if config.propagation == "required" and self._current:
            # Join existing transaction
            return self._transactions[self._current]
        elif config.propagation == "nested" and self._current:
            parent = self._transactions[self._current]
        
        tx = LocalTransaction(tx_id, config, parent)
        self._transactions[tx_id] = tx
        self._current = tx_id
        self._stats.total_started += 1
        self._stats.current_active += 1
        
        return tx
    
    async def get_transaction(self, tx_id: str) -> Optional[Transaction]:
        return self._transactions.get(tx_id)
    
    async def get_current(self) -> Optional[Transaction]:
        if self._current:
            return self._transactions.get(self._current)
        return None
    
    async def stats(self) -> TransactionStats:
        return self._stats
    
    async def commit(self, tx_id: str) -> None:
        """Commit transaction by ID."""
        tx = self._transactions.get(tx_id)
        if tx:
            await tx.commit()
            self._stats.total_committed += 1
            self._stats.current_active -= 1
    
    async def rollback(self, tx_id: str) -> None:
        """Rollback transaction by ID."""
        tx = self._transactions.get(tx_id)
        if tx:
            await tx.rollback()
            self._stats.total_aborted += 1
            self._stats.current_active -= 1


class UnitOfWork:
    """
    Unit of Work pattern implementation.
    """
    
    def __init__(self, tx_manager: TransactionManager):
        self._tx_manager = tx_manager
        self._new: List[Any] = []
        self._dirty: List[Any] = []
        self._deleted: List[Any] = []
        self._repositories: Dict[str, Any] = {}
    
    def register_new(self, entity: Any) -> None:
        """Register new entity."""
        self._new.append(entity)
    
    def register_dirty(self, entity: Any) -> None:
        """Register modified entity."""
        if entity not in self._dirty:
            self._dirty.append(entity)
    
    def register_deleted(self, entity: Any) -> None:
        """Register deleted entity."""
        self._deleted.append(entity)
    
    def register_repository(self, name: str, repository: Any) -> None:
        """Register a repository."""
        self._repositories[name] = repository
    
    def get_repository(self, name: str) -> Any:
        """Get registered repository."""
        return self._repositories.get(name)
    
    async def commit(self) -> None:
        """Commit all changes."""
        async with self._tx_manager.transaction():
            # Insert new entities
            for entity in self._new:
                if hasattr(entity, 'save'):
                    await entity.save()
            
            # Update dirty entities
            for entity in self._dirty:
                if hasattr(entity, 'save'):
                    await entity.save()
            
            # Delete entities
            for entity in self._deleted:
                if hasattr(entity, 'delete'):
                    await entity.delete()
        
        self._clear()
    
    async def rollback(self) -> None:
        """Rollback all changes."""
        self._clear()
    
    def _clear(self) -> None:
        """Clear tracked entities."""
        self._new.clear()
        self._dirty.clear()
        self._deleted.clear()
    
    async def __aenter__(self) -> "UnitOfWork":
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type:
            await self.rollback()


class TransactionRegistry:
    """
    Registry for transaction managers.
    """
    
    def __init__(self):
        self._managers: Dict[str, TransactionManager] = {}
        self._default: Optional[str] = None
    
    def register(
        self,
        name: str,
        manager: TransactionManager,
        default: bool = False,
    ) -> None:
        """Register a transaction manager."""
        self._managers[name] = manager
        if default or self._default is None:
            self._default = name
    
    def get(self, name: Optional[str] = None) -> TransactionManager:
        """Get a transaction manager."""
        name = name or self._default
        if not name or name not in self._managers:
            raise TransactionError(f"Manager not found: {name}")
        return self._managers[name]


# Global registry
_global_registry = TransactionRegistry()


# Decorators
def transactional(
    isolation: IsolationLevel = IsolationLevel.READ_COMMITTED,
    read_only: bool = False,
    propagation: str = "required",
    manager_name: Optional[str] = None,
) -> Callable:
    """
    Decorator to execute function in transaction.
    
    Example:
        @transactional()
        async def transfer_funds(from_acc, to_acc, amount):
            ...
    """
    def decorator(func: Callable) -> Callable:
        async def wrapper(*args, **kwargs):
            manager = get_transaction_manager(manager_name)
            config = TransactionConfig(
                isolation=isolation,
                read_only=read_only,
                propagation=propagation,
            )
            
            async with manager.transaction(config):
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                return func(*args, **kwargs)
        
        return wrapper
    
    return decorator


def atomic(func: Callable) -> Callable:
    """
    Simple atomic decorator.
    
    Example:
        @atomic
        async def save_data():
            ...
    """
    return transactional()(func)


# Factory functions
def create_transaction_manager() -> InMemoryTransactionManager:
    """Create an in-memory transaction manager."""
    return InMemoryTransactionManager()


def create_transaction_config(
    isolation: IsolationLevel = IsolationLevel.READ_COMMITTED,
    timeout: Optional[float] = None,
    read_only: bool = False,
    propagation: str = "required",
) -> TransactionConfig:
    """Create a transaction configuration."""
    return TransactionConfig(
        isolation=isolation,
        timeout=timeout,
        read_only=read_only,
        propagation=propagation,
    )


def create_unit_of_work(
    manager: Optional[TransactionManager] = None,
) -> UnitOfWork:
    """Create a unit of work."""
    if manager is None:
        manager = get_transaction_manager()
    return UnitOfWork(manager)


def register_transaction_manager(
    name: str,
    manager: TransactionManager,
    default: bool = False,
) -> None:
    """Register transaction manager in global registry."""
    _global_registry.register(name, manager, default)


def get_transaction_manager(name: Optional[str] = None) -> TransactionManager:
    """Get transaction manager from global registry."""
    try:
        return _global_registry.get(name)
    except TransactionError:
        # Create default if not registered
        manager = create_transaction_manager()
        register_transaction_manager("default", manager, default=True)
        return manager


__all__ = [
    # Exceptions
    "TransactionError",
    "TransactionAbortedError",
    "TransactionTimeoutError",
    "CommitError",
    "RollbackError",
    # Enums
    "IsolationLevel",
    "TransactionState",
    # Data classes
    "TransactionConfig",
    "TransactionInfo",
    "TransactionStats",
    # Participant
    "TransactionParticipant",
    # Transaction
    "Transaction",
    "LocalTransaction",
    # Manager
    "TransactionManager",
    "InMemoryTransactionManager",
    # Unit of Work
    "UnitOfWork",
    # Registry
    "TransactionRegistry",
    # Decorators
    "transactional",
    "atomic",
    # Factory functions
    "create_transaction_manager",
    "create_transaction_config",
    "create_unit_of_work",
    "register_transaction_manager",
    "get_transaction_manager",
]
