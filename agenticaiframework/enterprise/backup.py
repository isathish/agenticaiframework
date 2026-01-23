"""
Enterprise Backup Module.

Provides backup strategies, restore, and point-in-time recovery
for data protection and disaster recovery.

Example:
    # Create backup manager
    backup = create_backup_manager(
        storage="s3",
        retention_days=30
    )
    
    # Create backup
    backup_id = await backup.create_backup(source="db", type="full")
    
    # Restore from backup
    await backup.restore(backup_id, target="db_restored")
    
    # Point-in-time recovery
    await backup.restore_to_point_in_time(
        source="db",
        timestamp=datetime(2024, 1, 15, 10, 30)
    )
"""

from __future__ import annotations

import asyncio
import gzip
import hashlib
import json
import logging
import os
import shutil
import tempfile
import uuid
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from pathlib import Path
from typing import (
    Any,
    AsyncIterator,
    BinaryIO,
    Callable,
    Dict,
    Generic,
    Iterator,
    List,
    Optional,
    Set,
    TypeVar,
    Union,
)

logger = logging.getLogger(__name__)

T = TypeVar('T')


class BackupError(Exception):
    """Backup error."""
    pass


class RestoreError(BackupError):
    """Restore error."""
    pass


class BackupNotFoundError(BackupError):
    """Backup not found."""
    pass


class BackupType(str, Enum):
    """Type of backup."""
    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"
    SNAPSHOT = "snapshot"


class BackupState(str, Enum):
    """State of backup."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


class CompressionType(str, Enum):
    """Compression type."""
    NONE = "none"
    GZIP = "gzip"
    LZ4 = "lz4"


@dataclass
class BackupMetadata:
    """Backup metadata."""
    backup_id: str
    source: str
    backup_type: BackupType
    state: BackupState = BackupState.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    size_bytes: int = 0
    compressed_size_bytes: int = 0
    checksum: Optional[str] = None
    parent_backup_id: Optional[str] = None
    compression: CompressionType = CompressionType.GZIP
    encryption_key_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RestorePoint:
    """Point-in-time restore point."""
    point_id: str
    source: str
    timestamp: datetime
    backup_ids: List[str]
    wal_position: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BackupConfig:
    """Backup configuration."""
    retention_days: int = 30
    full_backup_interval_days: int = 7
    incremental_interval_hours: int = 1
    compression: CompressionType = CompressionType.GZIP
    encryption_enabled: bool = False
    max_concurrent_backups: int = 2


@dataclass
class BackupStats:
    """Backup statistics."""
    total_backups: int = 0
    successful_backups: int = 0
    failed_backups: int = 0
    total_size_bytes: int = 0
    oldest_backup: Optional[datetime] = None
    newest_backup: Optional[datetime] = None


class BackupStorage(ABC):
    """Abstract backup storage."""
    
    @abstractmethod
    async def save(
        self,
        backup_id: str,
        data: bytes,
    ) -> str:
        """Save backup data, return storage path."""
        pass
    
    @abstractmethod
    async def load(
        self,
        backup_id: str,
    ) -> bytes:
        """Load backup data."""
        pass
    
    @abstractmethod
    async def delete(
        self,
        backup_id: str,
    ) -> bool:
        """Delete backup data."""
        pass
    
    @abstractmethod
    async def exists(
        self,
        backup_id: str,
    ) -> bool:
        """Check if backup exists."""
        pass
    
    @abstractmethod
    async def list_backups(self) -> List[str]:
        """List all backup IDs."""
        pass


class LocalBackupStorage(BackupStorage):
    """Local filesystem backup storage."""
    
    def __init__(
        self,
        base_path: str = "/tmp/backups",
    ):
        self._base_path = Path(base_path)
        self._base_path.mkdir(parents=True, exist_ok=True)
    
    def _get_path(self, backup_id: str) -> Path:
        return self._base_path / f"{backup_id}.bak"
    
    async def save(
        self,
        backup_id: str,
        data: bytes,
    ) -> str:
        path = self._get_path(backup_id)
        path.write_bytes(data)
        return str(path)
    
    async def load(
        self,
        backup_id: str,
    ) -> bytes:
        path = self._get_path(backup_id)
        
        if not path.exists():
            raise BackupNotFoundError(f"Backup not found: {backup_id}")
        
        return path.read_bytes()
    
    async def delete(
        self,
        backup_id: str,
    ) -> bool:
        path = self._get_path(backup_id)
        
        if path.exists():
            path.unlink()
            return True
        
        return False
    
    async def exists(
        self,
        backup_id: str,
    ) -> bool:
        return self._get_path(backup_id).exists()
    
    async def list_backups(self) -> List[str]:
        return [
            p.stem for p in self._base_path.glob("*.bak")
        ]


class InMemoryBackupStorage(BackupStorage):
    """In-memory backup storage."""
    
    def __init__(self):
        self._storage: Dict[str, bytes] = {}
    
    async def save(
        self,
        backup_id: str,
        data: bytes,
    ) -> str:
        self._storage[backup_id] = data
        return f"memory://{backup_id}"
    
    async def load(
        self,
        backup_id: str,
    ) -> bytes:
        if backup_id not in self._storage:
            raise BackupNotFoundError(f"Backup not found: {backup_id}")
        
        return self._storage[backup_id]
    
    async def delete(
        self,
        backup_id: str,
    ) -> bool:
        if backup_id in self._storage:
            del self._storage[backup_id]
            return True
        return False
    
    async def exists(
        self,
        backup_id: str,
    ) -> bool:
        return backup_id in self._storage
    
    async def list_backups(self) -> List[str]:
        return list(self._storage.keys())


class BackupCatalog(ABC):
    """Abstract backup catalog."""
    
    @abstractmethod
    async def save_metadata(
        self,
        metadata: BackupMetadata,
    ) -> None:
        """Save backup metadata."""
        pass
    
    @abstractmethod
    async def get_metadata(
        self,
        backup_id: str,
    ) -> Optional[BackupMetadata]:
        """Get backup metadata."""
        pass
    
    @abstractmethod
    async def list_backups(
        self,
        source: Optional[str] = None,
        backup_type: Optional[BackupType] = None,
    ) -> List[BackupMetadata]:
        """List backup metadata."""
        pass
    
    @abstractmethod
    async def delete_metadata(
        self,
        backup_id: str,
    ) -> bool:
        """Delete backup metadata."""
        pass


class InMemoryBackupCatalog(BackupCatalog):
    """In-memory backup catalog."""
    
    def __init__(self):
        self._catalog: Dict[str, BackupMetadata] = {}
        self._lock = asyncio.Lock()
    
    async def save_metadata(
        self,
        metadata: BackupMetadata,
    ) -> None:
        async with self._lock:
            self._catalog[metadata.backup_id] = metadata
    
    async def get_metadata(
        self,
        backup_id: str,
    ) -> Optional[BackupMetadata]:
        return self._catalog.get(backup_id)
    
    async def list_backups(
        self,
        source: Optional[str] = None,
        backup_type: Optional[BackupType] = None,
    ) -> List[BackupMetadata]:
        backups = list(self._catalog.values())
        
        if source:
            backups = [b for b in backups if b.source == source]
        
        if backup_type:
            backups = [b for b in backups if b.backup_type == backup_type]
        
        return sorted(backups, key=lambda b: b.created_at, reverse=True)
    
    async def delete_metadata(
        self,
        backup_id: str,
    ) -> bool:
        async with self._lock:
            if backup_id in self._catalog:
                del self._catalog[backup_id]
                return True
            return False


class DataSource(ABC):
    """Abstract data source for backup."""
    
    @abstractmethod
    async def export_data(self) -> bytes:
        """Export data for backup."""
        pass
    
    @abstractmethod
    async def import_data(
        self,
        data: bytes,
    ) -> bool:
        """Import data from backup."""
        pass
    
    @abstractmethod
    async def get_changes_since(
        self,
        timestamp: datetime,
    ) -> bytes:
        """Get changes since timestamp (for incremental)."""
        pass


class DictDataSource(DataSource):
    """Simple dictionary data source."""
    
    def __init__(self):
        self._data: Dict[str, Any] = {}
        self._changes: List[Dict[str, Any]] = []
    
    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self._changes.append({
            "key": key,
            "value": value,
            "timestamp": datetime.now().isoformat(),
        })
    
    def get(self, key: str) -> Optional[Any]:
        return self._data.get(key)
    
    async def export_data(self) -> bytes:
        return json.dumps(self._data).encode()
    
    async def import_data(
        self,
        data: bytes,
    ) -> bool:
        self._data = json.loads(data.decode())
        return True
    
    async def get_changes_since(
        self,
        timestamp: datetime,
    ) -> bytes:
        changes = [
            c for c in self._changes
            if datetime.fromisoformat(c["timestamp"]) > timestamp
        ]
        return json.dumps(changes).encode()


class BackupManager:
    """
    Backup manager for creating and managing backups.
    """
    
    def __init__(
        self,
        storage: BackupStorage,
        catalog: BackupCatalog,
        config: Optional[BackupConfig] = None,
    ):
        self._storage = storage
        self._catalog = catalog
        self._config = config or BackupConfig()
        self._sources: Dict[str, DataSource] = {}
        self._semaphore = asyncio.Semaphore(
            self._config.max_concurrent_backups
        )
    
    def register_source(
        self,
        name: str,
        source: DataSource,
    ) -> None:
        """Register a data source."""
        self._sources[name] = source
    
    def unregister_source(self, name: str) -> None:
        """Unregister a data source."""
        self._sources.pop(name, None)
    
    async def create_backup(
        self,
        source: str,
        backup_type: BackupType = BackupType.FULL,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create a backup."""
        async with self._semaphore:
            if source not in self._sources:
                raise BackupError(f"Unknown source: {source}")
            
            data_source = self._sources[source]
            backup_id = str(uuid.uuid4())
            
            # Create metadata
            backup_meta = BackupMetadata(
                backup_id=backup_id,
                source=source,
                backup_type=backup_type,
                state=BackupState.IN_PROGRESS,
                compression=self._config.compression,
                metadata=metadata or {},
            )
            
            # Calculate expiration
            if self._config.retention_days > 0:
                backup_meta.expires_at = datetime.now() + timedelta(
                    days=self._config.retention_days
                )
            
            await self._catalog.save_metadata(backup_meta)
            
            try:
                # Export data
                if backup_type == BackupType.INCREMENTAL:
                    # Get last backup
                    backups = await self._catalog.list_backups(
                        source=source,
                        backup_type=BackupType.FULL,
                    )
                    
                    if backups:
                        last_backup = backups[0]
                        backup_meta.parent_backup_id = last_backup.backup_id
                        data = await data_source.get_changes_since(
                            last_backup.created_at
                        )
                    else:
                        # No full backup, do full instead
                        backup_meta.backup_type = BackupType.FULL
                        data = await data_source.export_data()
                else:
                    data = await data_source.export_data()
                
                backup_meta.size_bytes = len(data)
                
                # Compress
                if self._config.compression == CompressionType.GZIP:
                    data = gzip.compress(data)
                
                backup_meta.compressed_size_bytes = len(data)
                
                # Calculate checksum
                backup_meta.checksum = hashlib.sha256(data).hexdigest()
                
                # Save
                await self._storage.save(backup_id, data)
                
                backup_meta.state = BackupState.COMPLETED
                backup_meta.completed_at = datetime.now()
                
                await self._catalog.save_metadata(backup_meta)
                
                logger.info(
                    f"Backup created: {backup_id} "
                    f"({backup_meta.compressed_size_bytes} bytes)"
                )
                
                return backup_id
            
            except Exception as e:
                backup_meta.state = BackupState.FAILED
                backup_meta.metadata["error"] = str(e)
                await self._catalog.save_metadata(backup_meta)
                
                raise BackupError(f"Backup failed: {e}") from e
    
    async def restore(
        self,
        backup_id: str,
        target: Optional[str] = None,
    ) -> bool:
        """Restore from a backup."""
        metadata = await self._catalog.get_metadata(backup_id)
        
        if not metadata:
            raise BackupNotFoundError(f"Backup not found: {backup_id}")
        
        target_source = target or metadata.source
        
        if target_source not in self._sources:
            raise RestoreError(f"Unknown target: {target_source}")
        
        data_source = self._sources[target_source]
        
        try:
            # Load backup data
            data = await self._storage.load(backup_id)
            
            # Verify checksum
            if metadata.checksum:
                actual_checksum = hashlib.sha256(data).hexdigest()
                if actual_checksum != metadata.checksum:
                    raise RestoreError("Checksum mismatch")
            
            # Decompress
            if metadata.compression == CompressionType.GZIP:
                data = gzip.decompress(data)
            
            # Handle incremental
            if metadata.backup_type == BackupType.INCREMENTAL:
                # First restore parent
                if metadata.parent_backup_id:
                    await self.restore(metadata.parent_backup_id, target)
                
                # Then apply incremental changes
                changes = json.loads(data.decode())
                for change in changes:
                    if isinstance(data_source, DictDataSource):
                        data_source.set(change["key"], change["value"])
            else:
                # Full restore
                await data_source.import_data(data)
            
            logger.info(f"Restored from backup: {backup_id}")
            
            return True
        
        except Exception as e:
            raise RestoreError(f"Restore failed: {e}") from e
    
    async def restore_to_point_in_time(
        self,
        source: str,
        timestamp: datetime,
        target: Optional[str] = None,
    ) -> bool:
        """Restore to a specific point in time."""
        # Find backups before timestamp
        backups = await self._catalog.list_backups(source=source)
        
        eligible = [
            b for b in backups
            if b.created_at <= timestamp and b.state == BackupState.COMPLETED
        ]
        
        if not eligible:
            raise RestoreError(
                f"No backup found before {timestamp}"
            )
        
        # Find closest backup
        closest = max(eligible, key=lambda b: b.created_at)
        
        # Restore from closest backup
        return await self.restore(closest.backup_id, target)
    
    async def delete_backup(self, backup_id: str) -> bool:
        """Delete a backup."""
        await self._storage.delete(backup_id)
        await self._catalog.delete_metadata(backup_id)
        
        logger.info(f"Deleted backup: {backup_id}")
        
        return True
    
    async def cleanup_expired(self) -> int:
        """Clean up expired backups."""
        backups = await self._catalog.list_backups()
        
        deleted = 0
        now = datetime.now()
        
        for backup in backups:
            if backup.expires_at and backup.expires_at < now:
                await self.delete_backup(backup.backup_id)
                deleted += 1
        
        logger.info(f"Cleaned up {deleted} expired backups")
        
        return deleted
    
    async def get_stats(
        self,
        source: Optional[str] = None,
    ) -> BackupStats:
        """Get backup statistics."""
        backups = await self._catalog.list_backups(source=source)
        
        stats = BackupStats(
            total_backups=len(backups),
        )
        
        for backup in backups:
            if backup.state == BackupState.COMPLETED:
                stats.successful_backups += 1
                stats.total_size_bytes += backup.compressed_size_bytes
            elif backup.state == BackupState.FAILED:
                stats.failed_backups += 1
        
        if backups:
            dates = [b.created_at for b in backups]
            stats.oldest_backup = min(dates)
            stats.newest_backup = max(dates)
        
        return stats


class BackupScheduler:
    """
    Scheduler for automatic backups.
    """
    
    def __init__(
        self,
        manager: BackupManager,
        config: Optional[BackupConfig] = None,
    ):
        self._manager = manager
        self._config = config or BackupConfig()
        self._running = False
        self._tasks: Dict[str, asyncio.Task] = {}
    
    async def start(self) -> None:
        """Start backup scheduler."""
        if self._running:
            return
        
        self._running = True
        
        # Start full backup scheduler
        self._tasks["full"] = asyncio.create_task(
            self._full_backup_loop()
        )
        
        # Start incremental backup scheduler
        self._tasks["incremental"] = asyncio.create_task(
            self._incremental_backup_loop()
        )
        
        # Start cleanup scheduler
        self._tasks["cleanup"] = asyncio.create_task(
            self._cleanup_loop()
        )
        
        logger.info("Backup scheduler started")
    
    async def stop(self) -> None:
        """Stop backup scheduler."""
        self._running = False
        
        for task in self._tasks.values():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self._tasks.clear()
        
        logger.info("Backup scheduler stopped")
    
    async def _full_backup_loop(self) -> None:
        """Full backup loop."""
        interval = timedelta(days=self._config.full_backup_interval_days)
        
        while self._running:
            try:
                for source in list(self._manager._sources.keys()):
                    try:
                        await self._manager.create_backup(
                            source,
                            BackupType.FULL,
                        )
                    except Exception as e:
                        logger.error(f"Full backup failed for {source}: {e}")
                
                await asyncio.sleep(interval.total_seconds())
            
            except asyncio.CancelledError:
                break
    
    async def _incremental_backup_loop(self) -> None:
        """Incremental backup loop."""
        interval = timedelta(hours=self._config.incremental_interval_hours)
        
        while self._running:
            try:
                await asyncio.sleep(interval.total_seconds())
                
                for source in list(self._manager._sources.keys()):
                    try:
                        await self._manager.create_backup(
                            source,
                            BackupType.INCREMENTAL,
                        )
                    except Exception as e:
                        logger.error(
                            f"Incremental backup failed for {source}: {e}"
                        )
            
            except asyncio.CancelledError:
                break
    
    async def _cleanup_loop(self) -> None:
        """Cleanup loop."""
        while self._running:
            try:
                await asyncio.sleep(3600)  # Run every hour
                await self._manager.cleanup_expired()
            
            except asyncio.CancelledError:
                break


# Decorators
def backup_before(
    manager: BackupManager,
    source: str,
) -> Callable:
    """
    Decorator to create backup before operation.
    
    Example:
        @backup_before(backup_manager, "database")
        async def dangerous_migration():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            await manager.create_backup(source, BackupType.FULL)
            return await func(*args, **kwargs)
        
        return wrapper
    
    return decorator


def with_restore_on_failure(
    manager: BackupManager,
    source: str,
) -> Callable:
    """
    Decorator to restore from backup on failure.
    
    Example:
        @with_restore_on_failure(backup_manager, "database")
        async def risky_operation():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Create backup before
            backup_id = await manager.create_backup(
                source,
                BackupType.FULL,
            )
            
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Operation failed, restoring: {e}")
                await manager.restore(backup_id)
                raise
        
        return wrapper
    
    return decorator


# Factory functions
def create_backup_manager(
    storage: Optional[BackupStorage] = None,
    catalog: Optional[BackupCatalog] = None,
    retention_days: int = 30,
) -> BackupManager:
    """Create a backup manager."""
    s = storage or InMemoryBackupStorage()
    c = catalog or InMemoryBackupCatalog()
    config = BackupConfig(retention_days=retention_days)
    
    return BackupManager(s, c, config)


def create_backup_scheduler(
    manager: BackupManager,
    full_interval_days: int = 7,
    incremental_interval_hours: int = 1,
) -> BackupScheduler:
    """Create a backup scheduler."""
    config = BackupConfig(
        full_backup_interval_days=full_interval_days,
        incremental_interval_hours=incremental_interval_hours,
    )
    
    return BackupScheduler(manager, config)


def create_local_storage(
    base_path: str = "/tmp/backups",
) -> LocalBackupStorage:
    """Create local backup storage."""
    return LocalBackupStorage(base_path)


__all__ = [
    # Exceptions
    "BackupError",
    "RestoreError",
    "BackupNotFoundError",
    # Enums
    "BackupType",
    "BackupState",
    "CompressionType",
    # Data classes
    "BackupMetadata",
    "RestorePoint",
    "BackupConfig",
    "BackupStats",
    # Storage
    "BackupStorage",
    "LocalBackupStorage",
    "InMemoryBackupStorage",
    # Catalog
    "BackupCatalog",
    "InMemoryBackupCatalog",
    # Data sources
    "DataSource",
    "DictDataSource",
    # Core classes
    "BackupManager",
    "BackupScheduler",
    # Decorators
    "backup_before",
    "with_restore_on_failure",
    # Factory functions
    "create_backup_manager",
    "create_backup_scheduler",
    "create_local_storage",
]
