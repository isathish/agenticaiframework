"""
Enterprise File Storage Module.

Provides file storage abstraction, upload/download handling,
multiple backend support, and file metadata management.

Example:
    # Create storage with local backend
    storage = create_file_storage(
        backend=create_local_backend("/data/uploads")
    )
    
    # Upload file
    file_info = await storage.upload(
        content=file_bytes,
        filename="document.pdf",
        content_type="application/pdf",
    )
    
    # Download file
    content = await storage.download(file_info.id)
    
    # Get signed URL
    url = await storage.get_url(file_info.id, expires_in=3600)
"""

from __future__ import annotations

import asyncio
import functools
import hashlib
import logging
import mimetypes
import os
import shutil
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    AsyncIterator,
    Awaitable,
    BinaryIO,
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

T = TypeVar('T')


logger = logging.getLogger(__name__)


class StorageError(Exception):
    """Storage error."""
    pass


class FileNotFoundError(StorageError):
    """File not found error."""
    pass


class QuotaExceededError(StorageError):
    """Storage quota exceeded."""
    pass


class UploadError(StorageError):
    """File upload error."""
    pass


class StorageType(str, Enum):
    """Storage backend types."""
    LOCAL = "local"
    S3 = "s3"
    AZURE_BLOB = "azure_blob"
    GCS = "gcs"
    MEMORY = "memory"


class Visibility(str, Enum):
    """File visibility."""
    PUBLIC = "public"
    PRIVATE = "private"


@dataclass
class FileMetadata:
    """File metadata."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    filename: str = ""
    original_filename: str = ""
    content_type: str = "application/octet-stream"
    size: int = 0
    checksum: str = ""
    checksum_algorithm: str = "md5"
    visibility: Visibility = Visibility.PRIVATE
    path: str = ""
    bucket: str = ""
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def extension(self) -> str:
        """Get file extension."""
        return Path(self.filename).suffix.lower()


@dataclass
class UploadResult:
    """Upload result."""
    file: FileMetadata
    success: bool
    error: Optional[str] = None
    url: str = ""


@dataclass
class StorageStats:
    """Storage statistics."""
    total_files: int = 0
    total_size: int = 0
    files_by_type: Dict[str, int] = field(default_factory=dict)
    size_by_type: Dict[str, int] = field(default_factory=dict)


@dataclass
class UploadConfig:
    """Upload configuration."""
    max_file_size: int = 100 * 1024 * 1024  # 100MB
    allowed_types: Optional[List[str]] = None
    blocked_types: List[str] = field(default_factory=lambda: [
        "application/x-executable",
        "application/x-msdownload",
    ])
    generate_unique_name: bool = True
    preserve_filename: bool = False


# Storage backends
class StorageBackend(ABC):
    """Abstract storage backend."""
    
    @abstractmethod
    async def store(
        self,
        content: bytes,
        path: str,
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, str]] = None,
    ) -> str:
        """Store content and return path."""
        pass
    
    @abstractmethod
    async def retrieve(self, path: str) -> bytes:
        """Retrieve content by path."""
        pass
    
    @abstractmethod
    async def delete(self, path: str) -> bool:
        """Delete file by path."""
        pass
    
    @abstractmethod
    async def exists(self, path: str) -> bool:
        """Check if file exists."""
        pass
    
    @abstractmethod
    async def get_url(
        self,
        path: str,
        expires_in: int = 3600,
    ) -> str:
        """Get signed URL for file."""
        pass
    
    @abstractmethod
    async def list_files(
        self,
        prefix: str = "",
        limit: int = 100,
    ) -> List[str]:
        """List files by prefix."""
        pass


class LocalBackend(StorageBackend):
    """Local filesystem backend."""
    
    def __init__(
        self,
        root_path: Union[str, Path],
        base_url: str = "/files",
    ):
        self._root = Path(root_path)
        self._root.mkdir(parents=True, exist_ok=True)
        self._base_url = base_url.rstrip("/")
    
    async def store(
        self,
        content: bytes,
        path: str,
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, str]] = None,
    ) -> str:
        full_path = self._root / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        full_path.write_bytes(content)
        
        return path
    
    async def retrieve(self, path: str) -> bytes:
        full_path = self._root / path
        
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        
        return full_path.read_bytes()
    
    async def delete(self, path: str) -> bool:
        full_path = self._root / path
        
        if full_path.exists():
            full_path.unlink()
            return True
        
        return False
    
    async def exists(self, path: str) -> bool:
        return (self._root / path).exists()
    
    async def get_url(
        self,
        path: str,
        expires_in: int = 3600,
    ) -> str:
        # For local, just return the path
        return f"{self._base_url}/{path}"
    
    async def list_files(
        self,
        prefix: str = "",
        limit: int = 100,
    ) -> List[str]:
        search_path = self._root / prefix if prefix else self._root
        
        if not search_path.exists():
            return []
        
        files = []
        for path in search_path.rglob("*"):
            if path.is_file():
                rel_path = str(path.relative_to(self._root))
                files.append(rel_path)
                
                if len(files) >= limit:
                    break
        
        return files


class MemoryBackend(StorageBackend):
    """In-memory storage backend for testing."""
    
    def __init__(self):
        self._files: Dict[str, bytes] = {}
        self._metadata: Dict[str, Dict[str, str]] = {}
    
    async def store(
        self,
        content: bytes,
        path: str,
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, str]] = None,
    ) -> str:
        self._files[path] = content
        self._metadata[path] = metadata or {}
        return path
    
    async def retrieve(self, path: str) -> bytes:
        if path not in self._files:
            raise FileNotFoundError(f"File not found: {path}")
        return self._files[path]
    
    async def delete(self, path: str) -> bool:
        if path in self._files:
            del self._files[path]
            self._metadata.pop(path, None)
            return True
        return False
    
    async def exists(self, path: str) -> bool:
        return path in self._files
    
    async def get_url(
        self,
        path: str,
        expires_in: int = 3600,
    ) -> str:
        return f"memory://{path}"
    
    async def list_files(
        self,
        prefix: str = "",
        limit: int = 100,
    ) -> List[str]:
        files = [
            p for p in self._files.keys()
            if p.startswith(prefix)
        ]
        return files[:limit]
    
    def clear(self) -> None:
        """Clear all files."""
        self._files.clear()
        self._metadata.clear()


# Metadata store
class MetadataStore(ABC):
    """File metadata store."""
    
    @abstractmethod
    async def store(self, file: FileMetadata) -> None:
        """Store file metadata."""
        pass
    
    @abstractmethod
    async def get(self, file_id: str) -> Optional[FileMetadata]:
        """Get file metadata by ID."""
        pass
    
    @abstractmethod
    async def update(self, file: FileMetadata) -> None:
        """Update file metadata."""
        pass
    
    @abstractmethod
    async def delete(self, file_id: str) -> bool:
        """Delete file metadata."""
        pass
    
    @abstractmethod
    async def search(
        self,
        tags: Optional[Dict[str, str]] = None,
        content_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[FileMetadata]:
        """Search files by criteria."""
        pass


class InMemoryMetadataStore(MetadataStore):
    """In-memory metadata store."""
    
    def __init__(self):
        self._files: Dict[str, FileMetadata] = {}
    
    async def store(self, file: FileMetadata) -> None:
        self._files[file.id] = file
    
    async def get(self, file_id: str) -> Optional[FileMetadata]:
        return self._files.get(file_id)
    
    async def update(self, file: FileMetadata) -> None:
        file.updated_at = datetime.utcnow()
        self._files[file.id] = file
    
    async def delete(self, file_id: str) -> bool:
        if file_id in self._files:
            del self._files[file_id]
            return True
        return False
    
    async def search(
        self,
        tags: Optional[Dict[str, str]] = None,
        content_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[FileMetadata]:
        results = []
        
        for file in self._files.values():
            # Filter by content type
            if content_type and not file.content_type.startswith(content_type):
                continue
            
            # Filter by tags
            if tags:
                match = all(
                    file.tags.get(k) == v
                    for k, v in tags.items()
                )
                if not match:
                    continue
            
            results.append(file)
            
            if len(results) >= limit:
                break
        
        return results


# Processors
class FileProcessor(ABC):
    """File processor."""
    
    @abstractmethod
    async def process(
        self,
        content: bytes,
        metadata: FileMetadata,
    ) -> Tuple[bytes, FileMetadata]:
        """Process file content."""
        pass


class ImageResizer(FileProcessor):
    """Image resizing processor."""
    
    def __init__(
        self,
        max_width: int = 1920,
        max_height: int = 1080,
        quality: int = 85,
    ):
        self._max_width = max_width
        self._max_height = max_height
        self._quality = quality
    
    async def process(
        self,
        content: bytes,
        metadata: FileMetadata,
    ) -> Tuple[bytes, FileMetadata]:
        # Check if image
        if not metadata.content_type.startswith("image/"):
            return content, metadata
        
        # Would use Pillow in real implementation
        # For now, just return unchanged
        return content, metadata


class FileStorage:
    """
    File storage service.
    """
    
    def __init__(
        self,
        backend: StorageBackend,
        metadata_store: Optional[MetadataStore] = None,
        config: Optional[UploadConfig] = None,
        default_bucket: str = "default",
    ):
        self._backend = backend
        self._metadata_store = metadata_store or InMemoryMetadataStore()
        self._config = config or UploadConfig()
        self._default_bucket = default_bucket
        
        self._processors: List[FileProcessor] = []
    
    def add_processor(self, processor: FileProcessor) -> None:
        """Add file processor."""
        self._processors.append(processor)
    
    async def upload(
        self,
        content: Union[bytes, BinaryIO],
        filename: str,
        content_type: Optional[str] = None,
        visibility: Visibility = Visibility.PRIVATE,
        bucket: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> UploadResult:
        """
        Upload file.
        
        Args:
            content: File content (bytes or file-like object)
            filename: Original filename
            content_type: MIME type (auto-detected if not provided)
            visibility: File visibility
            bucket: Storage bucket
            tags: File tags
            metadata: Custom metadata
            
        Returns:
            Upload result
        """
        # Read content if file-like
        if hasattr(content, "read"):
            content = content.read()
        
        # Validate size
        if len(content) > self._config.max_file_size:
            return UploadResult(
                file=FileMetadata(filename=filename),
                success=False,
                error=f"File exceeds maximum size of {self._config.max_file_size} bytes",
            )
        
        # Auto-detect content type
        if not content_type:
            content_type, _ = mimetypes.guess_type(filename)
            content_type = content_type or "application/octet-stream"
        
        # Validate content type
        if self._config.allowed_types and content_type not in self._config.allowed_types:
            return UploadResult(
                file=FileMetadata(filename=filename),
                success=False,
                error=f"Content type {content_type} not allowed",
            )
        
        if content_type in self._config.blocked_types:
            return UploadResult(
                file=FileMetadata(filename=filename),
                success=False,
                error=f"Content type {content_type} is blocked",
            )
        
        # Generate unique filename
        file_id = str(uuid.uuid4())
        ext = Path(filename).suffix
        
        if self._config.generate_unique_name:
            stored_filename = f"{file_id}{ext}"
        else:
            stored_filename = filename
        
        # Calculate checksum
        checksum = hashlib.md5(content).hexdigest()
        
        # Create metadata
        bucket = bucket or self._default_bucket
        path = f"{bucket}/{stored_filename}"
        
        file_meta = FileMetadata(
            id=file_id,
            filename=stored_filename,
            original_filename=filename,
            content_type=content_type,
            size=len(content),
            checksum=checksum,
            visibility=visibility,
            path=path,
            bucket=bucket,
            tags=tags or {},
            metadata=metadata or {},
        )
        
        # Process file
        for processor in self._processors:
            content, file_meta = await processor.process(content, file_meta)
        
        try:
            # Store file
            await self._backend.store(
                content=content,
                path=path,
                content_type=content_type,
                metadata={"id": file_id},
            )
            
            # Store metadata
            await self._metadata_store.store(file_meta)
            
            # Get URL
            url = await self._backend.get_url(path)
            
            return UploadResult(
                file=file_meta,
                success=True,
                url=url,
            )
            
        except Exception as e:
            return UploadResult(
                file=file_meta,
                success=False,
                error=str(e),
            )
    
    async def download(self, file_id: str) -> bytes:
        """Download file by ID."""
        file_meta = await self._metadata_store.get(file_id)
        
        if not file_meta:
            raise FileNotFoundError(f"File not found: {file_id}")
        
        return await self._backend.retrieve(file_meta.path)
    
    async def stream(
        self,
        file_id: str,
        chunk_size: int = 8192,
    ) -> AsyncIterator[bytes]:
        """Stream file content."""
        content = await self.download(file_id)
        
        for i in range(0, len(content), chunk_size):
            yield content[i:i + chunk_size]
    
    async def delete(self, file_id: str) -> bool:
        """Delete file."""
        file_meta = await self._metadata_store.get(file_id)
        
        if not file_meta:
            return False
        
        # Delete from backend
        await self._backend.delete(file_meta.path)
        
        # Delete metadata
        await self._metadata_store.delete(file_id)
        
        return True
    
    async def get_metadata(self, file_id: str) -> Optional[FileMetadata]:
        """Get file metadata."""
        return await self._metadata_store.get(file_id)
    
    async def update_metadata(
        self,
        file_id: str,
        tags: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[FileMetadata]:
        """Update file metadata."""
        file_meta = await self._metadata_store.get(file_id)
        
        if not file_meta:
            return None
        
        if tags:
            file_meta.tags.update(tags)
        
        if metadata:
            file_meta.metadata.update(metadata)
        
        await self._metadata_store.update(file_meta)
        
        return file_meta
    
    async def get_url(
        self,
        file_id: str,
        expires_in: int = 3600,
    ) -> str:
        """Get signed URL for file."""
        file_meta = await self._metadata_store.get(file_id)
        
        if not file_meta:
            raise FileNotFoundError(f"File not found: {file_id}")
        
        return await self._backend.get_url(file_meta.path, expires_in)
    
    async def exists(self, file_id: str) -> bool:
        """Check if file exists."""
        file_meta = await self._metadata_store.get(file_id)
        
        if not file_meta:
            return False
        
        return await self._backend.exists(file_meta.path)
    
    async def search(
        self,
        tags: Optional[Dict[str, str]] = None,
        content_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[FileMetadata]:
        """Search files."""
        return await self._metadata_store.search(
            tags=tags,
            content_type=content_type,
            limit=limit,
        )
    
    async def copy(
        self,
        file_id: str,
        new_filename: Optional[str] = None,
        new_bucket: Optional[str] = None,
    ) -> Optional[FileMetadata]:
        """Copy file."""
        file_meta = await self._metadata_store.get(file_id)
        
        if not file_meta:
            return None
        
        # Download content
        content = await self._backend.retrieve(file_meta.path)
        
        # Upload copy
        result = await self.upload(
            content=content,
            filename=new_filename or file_meta.original_filename,
            content_type=file_meta.content_type,
            visibility=file_meta.visibility,
            bucket=new_bucket or file_meta.bucket,
            tags=file_meta.tags.copy(),
            metadata=file_meta.metadata.copy(),
        )
        
        return result.file if result.success else None


# Decorators
def validate_upload(
    max_size: Optional[int] = None,
    allowed_types: Optional[List[str]] = None,
) -> Callable:
    """Decorator to validate file upload."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            content = kwargs.get("content") or args[0] if args else None
            filename = kwargs.get("filename")
            
            if content and max_size and len(content) > max_size:
                raise UploadError(f"File exceeds maximum size of {max_size} bytes")
            
            if filename and allowed_types:
                content_type, _ = mimetypes.guess_type(filename)
                if content_type and content_type not in allowed_types:
                    raise UploadError(f"Content type {content_type} not allowed")
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


# Factory functions
def create_file_storage(
    backend: StorageBackend,
    metadata_store: Optional[MetadataStore] = None,
    config: Optional[UploadConfig] = None,
    default_bucket: str = "default",
) -> FileStorage:
    """Create file storage."""
    return FileStorage(
        backend=backend,
        metadata_store=metadata_store,
        config=config,
        default_bucket=default_bucket,
    )


def create_local_backend(
    root_path: Union[str, Path],
    base_url: str = "/files",
) -> LocalBackend:
    """Create local storage backend."""
    return LocalBackend(root_path, base_url)


def create_memory_backend() -> MemoryBackend:
    """Create memory storage backend."""
    return MemoryBackend()


def create_upload_config(
    max_file_size: int = 100 * 1024 * 1024,
    allowed_types: Optional[List[str]] = None,
    blocked_types: Optional[List[str]] = None,
    generate_unique_name: bool = True,
) -> UploadConfig:
    """Create upload configuration."""
    config = UploadConfig(
        max_file_size=max_file_size,
        allowed_types=allowed_types,
        generate_unique_name=generate_unique_name,
    )
    if blocked_types:
        config.blocked_types = blocked_types
    return config


def create_in_memory_metadata_store() -> InMemoryMetadataStore:
    """Create in-memory metadata store."""
    return InMemoryMetadataStore()


def create_image_resizer(
    max_width: int = 1920,
    max_height: int = 1080,
    quality: int = 85,
) -> ImageResizer:
    """Create image resizer processor."""
    return ImageResizer(max_width, max_height, quality)


__all__ = [
    # Exceptions
    "StorageError",
    "FileNotFoundError",
    "QuotaExceededError",
    "UploadError",
    # Enums
    "StorageType",
    "Visibility",
    # Data classes
    "FileMetadata",
    "UploadResult",
    "StorageStats",
    "UploadConfig",
    # Backends
    "StorageBackend",
    "LocalBackend",
    "MemoryBackend",
    # Metadata store
    "MetadataStore",
    "InMemoryMetadataStore",
    # Processors
    "FileProcessor",
    "ImageResizer",
    # Storage
    "FileStorage",
    # Decorators
    "validate_upload",
    # Factory functions
    "create_file_storage",
    "create_local_backend",
    "create_memory_backend",
    "create_upload_config",
    "create_in_memory_metadata_store",
    "create_image_resizer",
]
