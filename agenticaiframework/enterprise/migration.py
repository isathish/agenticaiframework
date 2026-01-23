"""
Enterprise Migration Module.

Provides schema migration, versioning, and rollback
capabilities for database and configuration changes.

Example:
    # Create migrator
    migrator = create_migrator()
    
    # Register migrations
    @migration(version="1.0.0")
    async def add_users_table(ctx):
        await ctx.execute("CREATE TABLE users ...")
    
    # Run migrations
    await migrator.migrate_to("latest")
    
    # Rollback
    await migrator.rollback(steps=1)
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from abc import ABC, abstractmethod
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
    TypeVar,
    Union,
)

logger = logging.getLogger(__name__)

T = TypeVar('T')


class MigrationError(Exception):
    """Migration error."""
    pass


class RollbackError(MigrationError):
    """Rollback error."""
    pass


class VersionConflictError(MigrationError):
    """Version conflict error."""
    pass


class MigrationStatus(str, Enum):
    """Migration status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class MigrationDirection(str, Enum):
    """Migration direction."""
    UP = "up"
    DOWN = "down"


@dataclass
class Version:
    """Semantic version."""
    major: int
    minor: int
    patch: int
    
    @classmethod
    def parse(cls, version_str: str) -> "Version":
        """Parse version string."""
        match = re.match(r"(\d+)\.(\d+)\.(\d+)", version_str)
        if not match:
            raise ValueError(f"Invalid version: {version_str}")
        
        return cls(
            major=int(match.group(1)),
            minor=int(match.group(2)),
            patch=int(match.group(3)),
        )
    
    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"
    
    def __lt__(self, other: "Version") -> bool:
        return (self.major, self.minor, self.patch) < (
            other.major, other.minor, other.patch
        )
    
    def __le__(self, other: "Version") -> bool:
        return self == other or self < other
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return False
        return (self.major, self.minor, self.patch) == (
            other.major, other.minor, other.patch
        )
    
    def __hash__(self) -> int:
        return hash((self.major, self.minor, self.patch))


@dataclass
class MigrationRecord:
    """Record of an applied migration."""
    migration_id: str
    version: str
    name: str
    status: MigrationStatus
    applied_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    checksum: Optional[str] = None
    execution_time_ms: int = 0
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MigrationDefinition:
    """Definition of a migration."""
    migration_id: str
    version: str
    name: str
    up: Callable
    down: Optional[Callable] = None
    description: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    checksum: Optional[str] = None


@dataclass
class MigrationContext:
    """Context for migration execution."""
    migration_id: str
    version: str
    direction: MigrationDirection
    dry_run: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    async def execute(self, statement: str) -> Any:
        """Execute a statement (to be implemented by executor)."""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would execute: {statement}")
            return None
        
        logger.info(f"Executing: {statement}")
        return None


@dataclass
class MigrationConfig:
    """Migration configuration."""
    table_name: str = "_migrations"
    lock_timeout_seconds: int = 60
    allow_out_of_order: bool = False
    validate_checksums: bool = True
    baseline_version: Optional[str] = None


class MigrationStore(ABC):
    """Abstract migration store."""
    
    @abstractmethod
    async def get_applied_migrations(self) -> List[MigrationRecord]:
        """Get all applied migrations."""
        pass
    
    @abstractmethod
    async def save_migration(
        self,
        record: MigrationRecord,
    ) -> None:
        """Save migration record."""
        pass
    
    @abstractmethod
    async def get_current_version(self) -> Optional[str]:
        """Get current version."""
        pass
    
    @abstractmethod
    async def delete_migration(
        self,
        migration_id: str,
    ) -> bool:
        """Delete migration record."""
        pass


class InMemoryMigrationStore(MigrationStore):
    """In-memory migration store."""
    
    def __init__(self):
        self._migrations: Dict[str, MigrationRecord] = {}
        self._lock = asyncio.Lock()
    
    async def get_applied_migrations(self) -> List[MigrationRecord]:
        return sorted(
            self._migrations.values(),
            key=lambda m: m.applied_at,
        )
    
    async def save_migration(
        self,
        record: MigrationRecord,
    ) -> None:
        async with self._lock:
            self._migrations[record.migration_id] = record
    
    async def get_current_version(self) -> Optional[str]:
        migrations = await self.get_applied_migrations()
        
        completed = [
            m for m in migrations
            if m.status == MigrationStatus.COMPLETED
        ]
        
        if completed:
            return completed[-1].version
        
        return None
    
    async def delete_migration(
        self,
        migration_id: str,
    ) -> bool:
        async with self._lock:
            if migration_id in self._migrations:
                del self._migrations[migration_id]
                return True
            return False


class MigrationRegistry:
    """Registry for migration definitions."""
    
    def __init__(self):
        self._migrations: Dict[str, MigrationDefinition] = {}
    
    def register(
        self,
        definition: MigrationDefinition,
    ) -> None:
        """Register a migration."""
        self._migrations[definition.migration_id] = definition
    
    def get(
        self,
        migration_id: str,
    ) -> Optional[MigrationDefinition]:
        """Get migration by ID."""
        return self._migrations.get(migration_id)
    
    def get_by_version(
        self,
        version: str,
    ) -> List[MigrationDefinition]:
        """Get migrations for a version."""
        return [
            m for m in self._migrations.values()
            if m.version == version
        ]
    
    def get_all(self) -> List[MigrationDefinition]:
        """Get all migrations sorted by version."""
        return sorted(
            self._migrations.values(),
            key=lambda m: Version.parse(m.version),
        )
    
    def get_pending(
        self,
        applied: Set[str],
    ) -> List[MigrationDefinition]:
        """Get pending migrations."""
        return [
            m for m in self.get_all()
            if m.migration_id not in applied
        ]


class Migrator:
    """
    Database/schema migrator.
    """
    
    def __init__(
        self,
        store: MigrationStore,
        registry: MigrationRegistry,
        config: Optional[MigrationConfig] = None,
    ):
        self._store = store
        self._registry = registry
        self._config = config or MigrationConfig()
        self._lock = asyncio.Lock()
    
    @property
    def registry(self) -> MigrationRegistry:
        return self._registry
    
    async def get_current_version(self) -> Optional[str]:
        """Get current version."""
        return await self._store.get_current_version()
    
    async def get_pending_migrations(self) -> List[MigrationDefinition]:
        """Get pending migrations."""
        applied = await self._store.get_applied_migrations()
        applied_ids = {m.migration_id for m in applied}
        
        return self._registry.get_pending(applied_ids)
    
    async def get_applied_migrations(self) -> List[MigrationRecord]:
        """Get applied migrations."""
        return await self._store.get_applied_migrations()
    
    async def migrate(
        self,
        dry_run: bool = False,
    ) -> List[MigrationRecord]:
        """Run all pending migrations."""
        async with self._lock:
            pending = await self.get_pending_migrations()
            results = []
            
            for definition in pending:
                try:
                    record = await self._run_migration(
                        definition,
                        MigrationDirection.UP,
                        dry_run,
                    )
                    results.append(record)
                    
                    if record.status == MigrationStatus.FAILED:
                        break
                
                except Exception as e:
                    logger.error(f"Migration failed: {e}")
                    break
            
            return results
    
    async def migrate_to(
        self,
        target_version: str,
        dry_run: bool = False,
    ) -> List[MigrationRecord]:
        """Migrate to specific version."""
        if target_version == "latest":
            return await self.migrate(dry_run)
        
        async with self._lock:
            current = await self.get_current_version()
            
            if current:
                current_v = Version.parse(current)
            else:
                current_v = Version(0, 0, 0)
            
            target_v = Version.parse(target_version)
            
            if target_v > current_v:
                # Migrate up
                pending = await self.get_pending_migrations()
                migrations = [
                    m for m in pending
                    if Version.parse(m.version) <= target_v
                ]
            else:
                # Migrate down
                applied = await self.get_applied_migrations()
                migrations = [
                    self._registry.get(m.migration_id)
                    for m in reversed(applied)
                    if Version.parse(m.version) > target_v
                ]
                return await self._rollback_migrations(
                    [m for m in migrations if m],
                    dry_run,
                )
            
            results = []
            
            for definition in migrations:
                record = await self._run_migration(
                    definition,
                    MigrationDirection.UP,
                    dry_run,
                )
                results.append(record)
                
                if record.status == MigrationStatus.FAILED:
                    break
            
            return results
    
    async def rollback(
        self,
        steps: int = 1,
        dry_run: bool = False,
    ) -> List[MigrationRecord]:
        """Rollback last N migrations."""
        async with self._lock:
            applied = await self.get_applied_migrations()
            
            if not applied:
                return []
            
            to_rollback = list(reversed(applied))[:steps]
            
            return await self._rollback_migrations(
                [
                    self._registry.get(m.migration_id)
                    for m in to_rollback
                    if self._registry.get(m.migration_id)
                ],
                dry_run,
            )
    
    async def _rollback_migrations(
        self,
        migrations: List[MigrationDefinition],
        dry_run: bool,
    ) -> List[MigrationRecord]:
        """Rollback a list of migrations."""
        results = []
        
        for definition in migrations:
            if not definition.down:
                raise RollbackError(
                    f"No down migration for {definition.migration_id}"
                )
            
            record = await self._run_migration(
                definition,
                MigrationDirection.DOWN,
                dry_run,
            )
            results.append(record)
            
            if record.status == MigrationStatus.FAILED:
                break
            
            # Delete migration record
            if not dry_run:
                await self._store.delete_migration(definition.migration_id)
        
        return results
    
    async def _run_migration(
        self,
        definition: MigrationDefinition,
        direction: MigrationDirection,
        dry_run: bool,
    ) -> MigrationRecord:
        """Run a single migration."""
        import time
        
        record = MigrationRecord(
            migration_id=definition.migration_id,
            version=definition.version,
            name=definition.name,
            status=MigrationStatus.RUNNING,
            checksum=definition.checksum,
        )
        
        if not dry_run:
            await self._store.save_migration(record)
        
        ctx = MigrationContext(
            migration_id=definition.migration_id,
            version=definition.version,
            direction=direction,
            dry_run=dry_run,
        )
        
        start = time.time()
        
        try:
            if direction == MigrationDirection.UP:
                if asyncio.iscoroutinefunction(definition.up):
                    await definition.up(ctx)
                else:
                    definition.up(ctx)
            else:
                if definition.down:
                    if asyncio.iscoroutinefunction(definition.down):
                        await definition.down(ctx)
                    else:
                        definition.down(ctx)
            
            record.status = MigrationStatus.COMPLETED
            record.completed_at = datetime.now()
            record.execution_time_ms = int((time.time() - start) * 1000)
            
            if not dry_run:
                await self._store.save_migration(record)
            
            logger.info(
                f"Migration {definition.migration_id} "
                f"({direction.value}) completed in {record.execution_time_ms}ms"
            )
        
        except Exception as e:
            record.status = MigrationStatus.FAILED
            record.error = str(e)
            record.execution_time_ms = int((time.time() - start) * 1000)
            
            if not dry_run:
                await self._store.save_migration(record)
            
            logger.error(
                f"Migration {definition.migration_id} failed: {e}"
            )
        
        return record
    
    async def validate(self) -> List[str]:
        """Validate migrations."""
        issues = []
        
        applied = await self.get_applied_migrations()
        
        for record in applied:
            definition = self._registry.get(record.migration_id)
            
            if not definition:
                issues.append(
                    f"Applied migration {record.migration_id} not found in registry"
                )
                continue
            
            if self._config.validate_checksums and record.checksum:
                if record.checksum != definition.checksum:
                    issues.append(
                        f"Checksum mismatch for {record.migration_id}"
                    )
        
        return issues


class MigrationBuilder:
    """
    Builder for creating migrations.
    """
    
    def __init__(self, version: str):
        self._version = version
        self._migrations: List[MigrationDefinition] = []
        self._up_statements: List[str] = []
        self._down_statements: List[str] = []
    
    def add_up(self, statement: str) -> "MigrationBuilder":
        """Add up statement."""
        self._up_statements.append(statement)
        return self
    
    def add_down(self, statement: str) -> "MigrationBuilder":
        """Add down statement."""
        self._down_statements.append(statement)
        return self
    
    def create_table(
        self,
        table_name: str,
        columns: Dict[str, str],
    ) -> "MigrationBuilder":
        """Add create table migration."""
        cols = ", ".join(f"{name} {dtype}" for name, dtype in columns.items())
        self._up_statements.append(
            f"CREATE TABLE {table_name} ({cols})"
        )
        self._down_statements.append(f"DROP TABLE {table_name}")
        return self
    
    def add_column(
        self,
        table_name: str,
        column_name: str,
        column_type: str,
    ) -> "MigrationBuilder":
        """Add column migration."""
        self._up_statements.append(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
        )
        self._down_statements.append(
            f"ALTER TABLE {table_name} DROP COLUMN {column_name}"
        )
        return self
    
    def drop_column(
        self,
        table_name: str,
        column_name: str,
    ) -> "MigrationBuilder":
        """Add drop column migration."""
        self._up_statements.append(
            f"ALTER TABLE {table_name} DROP COLUMN {column_name}"
        )
        return self
    
    def add_index(
        self,
        table_name: str,
        index_name: str,
        columns: List[str],
        unique: bool = False,
    ) -> "MigrationBuilder":
        """Add index migration."""
        unique_str = "UNIQUE " if unique else ""
        cols = ", ".join(columns)
        self._up_statements.append(
            f"CREATE {unique_str}INDEX {index_name} ON {table_name} ({cols})"
        )
        self._down_statements.append(f"DROP INDEX {index_name}")
        return self
    
    def build(self, name: str) -> MigrationDefinition:
        """Build migration definition."""
        migration_id = f"{self._version}_{name}"
        
        up_stmts = self._up_statements.copy()
        down_stmts = list(reversed(self._down_statements))
        
        async def up(ctx: MigrationContext):
            for stmt in up_stmts:
                await ctx.execute(stmt)
        
        async def down(ctx: MigrationContext):
            for stmt in down_stmts:
                await ctx.execute(stmt)
        
        checksum = hashlib.md5(
            "".join(up_stmts).encode()
        ).hexdigest()
        
        return MigrationDefinition(
            migration_id=migration_id,
            version=self._version,
            name=name,
            up=up,
            down=down if down_stmts else None,
            checksum=checksum,
        )


# Global registry
_global_registry = MigrationRegistry()


# Decorators
def migration(
    version: str,
    name: Optional[str] = None,
    dependencies: Optional[List[str]] = None,
) -> Callable:
    """
    Decorator to define a migration.
    
    Example:
        @migration(version="1.0.0")
        async def create_users_table(ctx):
            await ctx.execute("CREATE TABLE users ...")
    """
    def decorator(func: Callable) -> Callable:
        migration_name = name or func.__name__
        migration_id = f"{version}_{migration_name}"
        
        # Compute checksum from function source
        import inspect
        source = inspect.getsource(func)
        checksum = hashlib.md5(source.encode()).hexdigest()
        
        definition = MigrationDefinition(
            migration_id=migration_id,
            version=version,
            name=migration_name,
            up=func,
            dependencies=dependencies or [],
            checksum=checksum,
        )
        
        _global_registry.register(definition)
        
        # Store definition on function
        func._migration = definition
        
        return func
    
    return decorator


def rollback(up_func: Callable) -> Callable:
    """
    Decorator to define rollback for a migration.
    
    Example:
        @migration(version="1.0.0")
        async def create_users_table(ctx):
            await ctx.execute("CREATE TABLE users ...")
        
        @rollback(create_users_table)
        async def rollback_users_table(ctx):
            await ctx.execute("DROP TABLE users")
    """
    def decorator(func: Callable) -> Callable:
        if hasattr(up_func, "_migration"):
            up_func._migration.down = func
        
        return func
    
    return decorator


def versioned(
    version: str,
) -> Callable:
    """
    Decorator to mark a function as version-specific.
    
    Example:
        @versioned("2.0.0")
        def new_api_handler():
            ...
    """
    def decorator(func: Callable) -> Callable:
        func._version = version
        
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)
        
        return wrapper
    
    return decorator


# Factory functions
def create_migrator(
    store: Optional[MigrationStore] = None,
    registry: Optional[MigrationRegistry] = None,
) -> Migrator:
    """Create a migrator."""
    s = store or InMemoryMigrationStore()
    r = registry or _global_registry
    return Migrator(s, r)


def create_migration_builder(
    version: str,
) -> MigrationBuilder:
    """Create a migration builder."""
    return MigrationBuilder(version)


def create_migration(
    version: str,
    name: str,
    up: Callable,
    down: Optional[Callable] = None,
) -> MigrationDefinition:
    """Create a migration definition."""
    migration_id = f"{version}_{name}"
    
    return MigrationDefinition(
        migration_id=migration_id,
        version=version,
        name=name,
        up=up,
        down=down,
    )


def get_global_registry() -> MigrationRegistry:
    """Get global migration registry."""
    return _global_registry


__all__ = [
    # Exceptions
    "MigrationError",
    "RollbackError",
    "VersionConflictError",
    # Enums
    "MigrationStatus",
    "MigrationDirection",
    # Data classes
    "Version",
    "MigrationRecord",
    "MigrationDefinition",
    "MigrationContext",
    "MigrationConfig",
    # Stores
    "MigrationStore",
    "InMemoryMigrationStore",
    # Core classes
    "MigrationRegistry",
    "Migrator",
    "MigrationBuilder",
    # Decorators
    "migration",
    "rollback",
    "versioned",
    # Factory functions
    "create_migrator",
    "create_migration_builder",
    "create_migration",
    "get_global_registry",
]
