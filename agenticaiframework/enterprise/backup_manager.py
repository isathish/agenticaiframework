"""
Enterprise Backup Manager Module.

Automated backups, restore operations,
snapshots, and disaster recovery.

Example:
    # Create backup manager
    manager = create_backup_manager()
    
    # Create backup
    backup = await manager.backup(
        source="/data/database",
        name="daily-backup",
        compress=True,
    )
    
    # List backups
    backups = await manager.list_backups()
    
    # Restore from backup
    await manager.restore(backup.id, target="/data/restore")
    
    # Schedule automated backups
    await manager.schedule("0 2 * * *", source="/data")
"""

from __future__ import annotations

import asyncio
import functools
import gzip
import hashlib
import io
import json
import logging
import os
import shutil
import tarfile
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    BinaryIO,
    Callable,
    Dict,
    Generic,
    Iterator,
    List,
    Optional,
    Set,
    Tuple,
    TypeVar,
    Union,
)

T = TypeVar('T')


logger = logging.getLogger(__name__)


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
    """Backup type."""
    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"
    SNAPSHOT = "snapshot"


class BackupStatus(str, Enum):
    """Backup status."""
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
    ZSTD = "zstd"


@dataclass
class BackupMetadata:
    """Backup metadata."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    source: str = ""
    backup_type: BackupType = BackupType.FULL
    status: BackupStatus = BackupStatus.PENDING
    compression: CompressionType = CompressionType.GZIP
    size_bytes: int = 0
    file_count: int = 0
    checksum: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    retention_days: int = 30
    parent_backup_id: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RestoreResult:
    """Restore result."""
    success: bool
    backup_id: str
    target: str
    files_restored: int = 0
    size_bytes: int = 0
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


@dataclass
class ScheduledBackup:
    """Scheduled backup configuration."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    cron_expression: str = ""
    source: str = ""
    name_template: str = "backup-{date}"
    backup_type: BackupType = BackupType.FULL
    compression: CompressionType = CompressionType.GZIP
    retention_days: int = 30
    enabled: bool = True
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BackupStats:
    """Backup statistics."""
    total_backups: int = 0
    total_size_bytes: int = 0
    completed_backups: int = 0
    failed_backups: int = 0
    oldest_backup: Optional[datetime] = None
    newest_backup: Optional[datetime] = None
    backups_by_type: Dict[str, int] = field(default_factory=dict)


# Storage backend
class BackupStorage(ABC):
    """Abstract backup storage."""
    
    @abstractmethod
    async def store(
        self,
        backup_id: str,
        data: BinaryIO,
    ) -> str:
        """Store backup data."""
        pass
    
    @abstractmethod
    async def retrieve(
        self,
        backup_id: str,
    ) -> BinaryIO:
        """Retrieve backup data."""
        pass
    
    @abstractmethod
    async def delete(self, backup_id: str) -> bool:
        """Delete backup."""
        pass
    
    @abstractmethod
    async def exists(self, backup_id: str) -> bool:
        """Check if backup exists."""
        pass


class LocalBackupStorage(BackupStorage):
    """Local filesystem backup storage."""
    
    def __init__(self, base_path: str = "/tmp/backups"):
        self._base_path = Path(base_path)
        self._base_path.mkdir(parents=True, exist_ok=True)
    
    async def store(
        self,
        backup_id: str,
        data: BinaryIO,
    ) -> str:
        """Store backup locally."""
        path = self._base_path / f"{backup_id}.backup"
        
        with open(path, "wb") as f:
            shutil.copyfileobj(data, f)
        
        return str(path)
    
    async def retrieve(
        self,
        backup_id: str,
    ) -> BinaryIO:
        """Retrieve backup."""
        path = self._base_path / f"{backup_id}.backup"
        
        if not path.exists():
            raise BackupNotFoundError(f"Backup not found: {backup_id}")
        
        return open(path, "rb")
    
    async def delete(self, backup_id: str) -> bool:
        """Delete backup."""
        path = self._base_path / f"{backup_id}.backup"
        
        if path.exists():
            path.unlink()
            return True
        return False
    
    async def exists(self, backup_id: str) -> bool:
        """Check if backup exists."""
        path = self._base_path / f"{backup_id}.backup"
        return path.exists()


class InMemoryBackupStorage(BackupStorage):
    """In-memory backup storage for testing."""
    
    def __init__(self):
        self._backups: Dict[str, bytes] = {}
    
    async def store(
        self,
        backup_id: str,
        data: BinaryIO,
    ) -> str:
        """Store backup."""
        self._backups[backup_id] = data.read()
        return backup_id
    
    async def retrieve(
        self,
        backup_id: str,
    ) -> BinaryIO:
        """Retrieve backup."""
        if backup_id not in self._backups:
            raise BackupNotFoundError(f"Backup not found: {backup_id}")
        
        return io.BytesIO(self._backups[backup_id])
    
    async def delete(self, backup_id: str) -> bool:
        """Delete backup."""
        if backup_id in self._backups:
            del self._backups[backup_id]
            return True
        return False
    
    async def exists(self, backup_id: str) -> bool:
        """Check if backup exists."""
        return backup_id in self._backups


# Metadata store
class MetadataStore(ABC):
    """Abstract metadata store."""
    
    @abstractmethod
    async def save(self, metadata: BackupMetadata) -> None:
        """Save metadata."""
        pass
    
    @abstractmethod
    async def get(self, backup_id: str) -> Optional[BackupMetadata]:
        """Get metadata."""
        pass
    
    @abstractmethod
    async def list(
        self,
        source: Optional[str] = None,
        status: Optional[BackupStatus] = None,
        limit: int = 100,
    ) -> List[BackupMetadata]:
        """List backups."""
        pass
    
    @abstractmethod
    async def delete(self, backup_id: str) -> bool:
        """Delete metadata."""
        pass


class InMemoryMetadataStore(MetadataStore):
    """In-memory metadata store."""
    
    def __init__(self):
        self._backups: Dict[str, BackupMetadata] = {}
    
    async def save(self, metadata: BackupMetadata) -> None:
        self._backups[metadata.id] = metadata
    
    async def get(self, backup_id: str) -> Optional[BackupMetadata]:
        return self._backups.get(backup_id)
    
    async def list(
        self,
        source: Optional[str] = None,
        status: Optional[BackupStatus] = None,
        limit: int = 100,
    ) -> List[BackupMetadata]:
        results = []
        
        for backup in self._backups.values():
            if source and backup.source != source:
                continue
            if status and backup.status != status:
                continue
            
            results.append(backup)
        
        results.sort(key=lambda b: b.created_at, reverse=True)
        return results[:limit]
    
    async def delete(self, backup_id: str) -> bool:
        if backup_id in self._backups:
            del self._backups[backup_id]
            return True
        return False


# Backup manager
class BackupManager:
    """
    Backup management service.
    """
    
    def __init__(
        self,
        storage: Optional[BackupStorage] = None,
        metadata_store: Optional[MetadataStore] = None,
        default_retention_days: int = 30,
    ):
        self._storage = storage or InMemoryBackupStorage()
        self._metadata = metadata_store or InMemoryMetadataStore()
        self._default_retention_days = default_retention_days
        self._scheduled: Dict[str, ScheduledBackup] = {}
        self._scheduler_task: Optional[asyncio.Task] = None
        self._running = False
        self._hooks: Dict[str, List[Callable]] = {}
    
    async def backup(
        self,
        source: str,
        name: Optional[str] = None,
        backup_type: BackupType = BackupType.FULL,
        compression: CompressionType = CompressionType.GZIP,
        retention_days: Optional[int] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> BackupMetadata:
        """
        Create backup.
        
        Args:
            source: Source path or data
            name: Backup name
            backup_type: Type of backup
            compression: Compression type
            retention_days: Retention period
            tags: Backup tags
            metadata: Additional metadata
            
        Returns:
            Backup metadata
        """
        backup_meta = BackupMetadata(
            name=name or f"backup-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}",
            source=source,
            backup_type=backup_type,
            compression=compression,
            retention_days=retention_days or self._default_retention_days,
            tags=tags or [],
            metadata=metadata or {},
        )
        
        backup_meta.status = BackupStatus.IN_PROGRESS
        await self._metadata.save(backup_meta)
        
        await self._trigger("backup_started", backup_meta)
        
        try:
            # Create backup data
            data, file_count = await self._create_backup_data(
                source, compression
            )
            
            # Calculate checksum
            data.seek(0)
            checksum = hashlib.sha256(data.read()).hexdigest()
            data.seek(0)
            
            # Store backup
            await self._storage.store(backup_meta.id, data)
            
            # Update metadata
            data.seek(0, 2)  # Seek to end
            backup_meta.size_bytes = data.tell()
            backup_meta.file_count = file_count
            backup_meta.checksum = checksum
            backup_meta.status = BackupStatus.COMPLETED
            backup_meta.completed_at = datetime.utcnow()
            backup_meta.expires_at = (
                datetime.utcnow() + timedelta(days=backup_meta.retention_days)
            )
            
            await self._metadata.save(backup_meta)
            await self._trigger("backup_completed", backup_meta)
            
            logger.info(f"Backup created: {backup_meta.name} ({backup_meta.id})")
            
            return backup_meta
            
        except Exception as e:
            backup_meta.status = BackupStatus.FAILED
            backup_meta.metadata["error"] = str(e)
            await self._metadata.save(backup_meta)
            
            await self._trigger("backup_failed", backup_meta, e)
            
            logger.error(f"Backup failed: {e}")
            raise BackupError(f"Backup failed: {e}")
    
    async def _create_backup_data(
        self,
        source: str,
        compression: CompressionType,
    ) -> Tuple[BinaryIO, int]:
        """Create backup data from source."""
        buffer = io.BytesIO()
        file_count = 0
        
        source_path = Path(source)
        
        if source_path.exists():
            # Create tar archive
            if compression == CompressionType.GZIP:
                mode = "w:gz"
            else:
                mode = "w"
            
            with tarfile.open(fileobj=buffer, mode=mode) as tar:
                if source_path.is_file():
                    tar.add(str(source_path), arcname=source_path.name)
                    file_count = 1
                else:
                    for item in source_path.rglob("*"):
                        if item.is_file():
                            tar.add(
                                str(item),
                                arcname=str(item.relative_to(source_path)),
                            )
                            file_count += 1
        else:
            # Treat as data string
            data = source.encode()
            if compression == CompressionType.GZIP:
                data = gzip.compress(data)
            buffer.write(data)
            file_count = 1
        
        buffer.seek(0)
        return buffer, file_count
    
    async def restore(
        self,
        backup_id: str,
        target: str,
        verify: bool = True,
    ) -> RestoreResult:
        """
        Restore from backup.
        
        Args:
            backup_id: Backup ID
            target: Target path
            verify: Verify checksum
            
        Returns:
            Restore result
        """
        result = RestoreResult(
            success=False,
            backup_id=backup_id,
            target=target,
        )
        
        try:
            metadata = await self._metadata.get(backup_id)
            
            if not metadata:
                raise BackupNotFoundError(f"Backup not found: {backup_id}")
            
            if metadata.status != BackupStatus.COMPLETED:
                raise RestoreError(f"Cannot restore incomplete backup")
            
            await self._trigger("restore_started", metadata, target)
            
            # Retrieve backup data
            data = await self._storage.retrieve(backup_id)
            
            # Verify checksum
            if verify and metadata.checksum:
                data_content = data.read()
                actual_checksum = hashlib.sha256(data_content).hexdigest()
                
                if actual_checksum != metadata.checksum:
                    raise RestoreError("Checksum verification failed")
                
                data = io.BytesIO(data_content)
            
            # Extract backup
            target_path = Path(target)
            target_path.mkdir(parents=True, exist_ok=True)
            
            if metadata.compression == CompressionType.GZIP:
                mode = "r:gz"
            else:
                mode = "r"
            
            try:
                with tarfile.open(fileobj=data, mode=mode) as tar:
                    tar.extractall(target_path)
                    result.files_restored = len(tar.getmembers())
            except tarfile.ReadError:
                # Not a tar file, extract raw data
                data.seek(0)
                content = data.read()
                
                if metadata.compression == CompressionType.GZIP:
                    content = gzip.decompress(content)
                
                output_file = target_path / "restored_data"
                output_file.write_bytes(content)
                result.files_restored = 1
            
            result.success = True
            result.completed_at = datetime.utcnow()
            result.size_bytes = metadata.size_bytes
            
            await self._trigger("restore_completed", metadata, result)
            
            logger.info(f"Restored backup {backup_id} to {target}")
            
            return result
            
        except Exception as e:
            result.error = str(e)
            result.completed_at = datetime.utcnow()
            
            logger.error(f"Restore failed: {e}")
            raise RestoreError(f"Restore failed: {e}")
    
    async def list_backups(
        self,
        source: Optional[str] = None,
        status: Optional[BackupStatus] = None,
        limit: int = 100,
    ) -> List[BackupMetadata]:
        """List backups."""
        return await self._metadata.list(source, status, limit)
    
    async def get_backup(self, backup_id: str) -> Optional[BackupMetadata]:
        """Get backup metadata."""
        return await self._metadata.get(backup_id)
    
    async def delete_backup(self, backup_id: str) -> bool:
        """Delete backup."""
        if await self._storage.delete(backup_id):
            await self._metadata.delete(backup_id)
            logger.info(f"Deleted backup: {backup_id}")
            return True
        return False
    
    async def expire_backups(self) -> int:
        """Expire old backups."""
        now = datetime.utcnow()
        expired_count = 0
        
        backups = await self._metadata.list(
            status=BackupStatus.COMPLETED,
            limit=10000,
        )
        
        for backup in backups:
            if backup.expires_at and backup.expires_at < now:
                backup.status = BackupStatus.EXPIRED
                await self._metadata.save(backup)
                await self._storage.delete(backup.id)
                expired_count += 1
        
        if expired_count:
            logger.info(f"Expired {expired_count} backups")
        
        return expired_count
    
    async def schedule(
        self,
        cron_expression: str,
        source: str,
        name_template: str = "backup-{date}",
        backup_type: BackupType = BackupType.FULL,
        retention_days: Optional[int] = None,
    ) -> ScheduledBackup:
        """
        Schedule automated backup.
        
        Args:
            cron_expression: Cron expression
            source: Source path
            name_template: Name template
            backup_type: Backup type
            retention_days: Retention days
            
        Returns:
            Scheduled backup config
        """
        scheduled = ScheduledBackup(
            cron_expression=cron_expression,
            source=source,
            name_template=name_template,
            backup_type=backup_type,
            retention_days=retention_days or self._default_retention_days,
        )
        
        self._scheduled[scheduled.id] = scheduled
        
        logger.info(f"Scheduled backup: {cron_expression}")
        
        return scheduled
    
    async def unschedule(self, schedule_id: str) -> bool:
        """Remove scheduled backup."""
        if schedule_id in self._scheduled:
            del self._scheduled[schedule_id]
            return True
        return False
    
    async def start_scheduler(self) -> None:
        """Start backup scheduler."""
        self._running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info("Backup scheduler started")
    
    async def stop_scheduler(self) -> None:
        """Stop backup scheduler."""
        self._running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
        logger.info("Backup scheduler stopped")
    
    async def _scheduler_loop(self) -> None:
        """Scheduler loop."""
        while self._running:
            try:
                await self._check_scheduled_backups()
                await self.expire_backups()
                await asyncio.sleep(60)  # Check every minute
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
    
    async def _check_scheduled_backups(self) -> None:
        """Check and run scheduled backups."""
        now = datetime.utcnow()
        
        for scheduled in self._scheduled.values():
            if not scheduled.enabled:
                continue
            
            # Simple minute-based check
            if scheduled.next_run and now >= scheduled.next_run:
                try:
                    name = scheduled.name_template.format(
                        date=now.strftime("%Y%m%d-%H%M%S")
                    )
                    
                    await self.backup(
                        source=scheduled.source,
                        name=name,
                        backup_type=scheduled.backup_type,
                        retention_days=scheduled.retention_days,
                    )
                    
                    scheduled.last_run = now
                    # Set next run (simplified - add 1 day)
                    scheduled.next_run = now + timedelta(days=1)
                    
                except Exception as e:
                    logger.error(f"Scheduled backup failed: {e}")
    
    def on(self, event: str, handler: Callable) -> None:
        """Add event handler."""
        if event not in self._hooks:
            self._hooks[event] = []
        self._hooks[event].append(handler)
    
    async def _trigger(self, event: str, *args, **kwargs) -> None:
        """Trigger event."""
        for handler in self._hooks.get(event, []):
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(*args, **kwargs)
                else:
                    handler(*args, **kwargs)
            except Exception as e:
                logger.error(f"Hook error: {e}")
    
    async def get_stats(self) -> BackupStats:
        """Get backup statistics."""
        backups = await self._metadata.list(limit=10000)
        
        stats = BackupStats()
        
        for backup in backups:
            stats.total_backups += 1
            stats.total_size_bytes += backup.size_bytes
            
            if backup.status == BackupStatus.COMPLETED:
                stats.completed_backups += 1
            elif backup.status == BackupStatus.FAILED:
                stats.failed_backups += 1
            
            type_key = backup.backup_type.value
            stats.backups_by_type[type_key] = (
                stats.backups_by_type.get(type_key, 0) + 1
            )
            
            if not stats.oldest_backup or backup.created_at < stats.oldest_backup:
                stats.oldest_backup = backup.created_at
            if not stats.newest_backup or backup.created_at > stats.newest_backup:
                stats.newest_backup = backup.created_at
        
        return stats


# Factory functions
def create_backup_manager(
    storage_path: Optional[str] = None,
    retention_days: int = 30,
) -> BackupManager:
    """Create backup manager."""
    if storage_path:
        storage = LocalBackupStorage(storage_path)
    else:
        storage = InMemoryBackupStorage()
    
    return BackupManager(
        storage=storage,
        default_retention_days=retention_days,
    )


def create_local_storage(path: str) -> LocalBackupStorage:
    """Create local storage."""
    return LocalBackupStorage(path)


__all__ = [
    # Exceptions
    "BackupError",
    "RestoreError",
    "BackupNotFoundError",
    # Enums
    "BackupType",
    "BackupStatus",
    "CompressionType",
    # Data classes
    "BackupMetadata",
    "RestoreResult",
    "ScheduledBackup",
    "BackupStats",
    # Storage
    "BackupStorage",
    "LocalBackupStorage",
    "InMemoryBackupStorage",
    # Metadata
    "MetadataStore",
    "InMemoryMetadataStore",
    # Manager
    "BackupManager",
    # Factory functions
    "create_backup_manager",
    "create_local_storage",
]
