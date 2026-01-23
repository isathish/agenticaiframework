"""
Enterprise Archive Manager Module.

Provides archive creation, extraction, encryption,
and streaming for ZIP/TAR formats.

Example:
    # Create archive manager
    archives = create_archive_manager()
    
    # Create ZIP archive
    archive = await archives.create_zip(
        files=[
            ("doc.pdf", pdf_bytes),
            ("images/logo.png", logo_bytes),
        ],
        password="secret",
    )
    
    # Extract archive
    files = await archives.extract(archive_bytes)
    
    # Stream archive entries
    async for entry in archives.stream(archive_bytes):
        print(f"{entry.name}: {entry.size} bytes")
"""

from __future__ import annotations

import asyncio
import base64
import functools
import gzip
import io
import json
import logging
import os
import tarfile
import uuid
import zipfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    AsyncIterator,
    BinaryIO,
    Callable,
    Dict,
    Iterator,
    List,
    Optional,
    Tuple,
    TypeVar,
    Union,
)

T = TypeVar('T')


logger = logging.getLogger(__name__)


class ArchiveError(Exception):
    """Archive error."""
    pass


class ExtractionError(ArchiveError):
    """Extraction error."""
    pass


class CompressionError(ArchiveError):
    """Compression error."""
    pass


class ArchiveFormat(str, Enum):
    """Archive formats."""
    ZIP = "zip"
    TAR = "tar"
    TAR_GZ = "tar.gz"
    TAR_BZ2 = "tar.bz2"
    TAR_XZ = "tar.xz"
    GZIP = "gz"
    BZIP2 = "bz2"
    SEVENZ = "7z"


class CompressionLevel(int, Enum):
    """Compression levels."""
    STORE = 0
    FASTEST = 1
    FAST = 3
    NORMAL = 6
    BEST = 9


@dataclass
class ArchiveEntry:
    """Archive entry information."""
    name: str
    size: int = 0
    compressed_size: int = 0
    is_directory: bool = False
    is_file: bool = True
    modified_time: Optional[datetime] = None
    permissions: Optional[int] = None
    content: Optional[bytes] = None


@dataclass
class ArchiveInfo:
    """Archive information."""
    format: ArchiveFormat
    total_size: int = 0
    compressed_size: int = 0
    entry_count: int = 0
    is_encrypted: bool = False
    comment: str = ""
    entries: List[ArchiveEntry] = field(default_factory=list)


@dataclass
class CreateOptions:
    """Archive creation options."""
    format: ArchiveFormat = ArchiveFormat.ZIP
    compression: CompressionLevel = CompressionLevel.NORMAL
    password: Optional[str] = None
    comment: str = ""
    preserve_paths: bool = True
    base_path: str = ""


@dataclass
class ExtractOptions:
    """Extraction options."""
    password: Optional[str] = None
    pattern: Optional[str] = None  # Glob pattern
    flatten: bool = False
    max_size: Optional[int] = None  # Max extracted size


@dataclass
class CreatedArchive:
    """Created archive result."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: bytes = b""
    format: ArchiveFormat = ArchiveFormat.ZIP
    size: int = 0
    entry_count: int = 0
    is_encrypted: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ExtractedFile:
    """Extracted file."""
    name: str
    path: str
    content: bytes
    size: int
    modified_time: Optional[datetime] = None


class ArchiveManager:
    """
    Archive management service.
    """
    
    def __init__(
        self,
        temp_dir: Optional[Path] = None,
        max_size: int = 1024 * 1024 * 1024,  # 1 GB
    ):
        self._temp_dir = temp_dir or Path("/tmp")
        self._max_size = max_size
    
    async def get_info(
        self,
        data: bytes,
        password: Optional[str] = None,
    ) -> ArchiveInfo:
        """
        Get archive information.
        
        Args:
            data: Archive bytes
            password: Archive password
            
        Returns:
            Archive info
        """
        # Try ZIP first
        try:
            return await self._get_zip_info(data, password)
        except:
            pass
        
        # Try TAR
        try:
            return await self._get_tar_info(data)
        except:
            pass
        
        raise ArchiveError("Unknown archive format")
    
    async def _get_zip_info(
        self,
        data: bytes,
        password: Optional[str] = None,
    ) -> ArchiveInfo:
        """Get ZIP archive info."""
        buffer = io.BytesIO(data)
        
        with zipfile.ZipFile(buffer, 'r') as zf:
            entries = []
            total_size = 0
            compressed_size = 0
            
            for info in zf.infolist():
                entries.append(ArchiveEntry(
                    name=info.filename,
                    size=info.file_size,
                    compressed_size=info.compress_size,
                    is_directory=info.is_dir(),
                    is_file=not info.is_dir(),
                    modified_time=datetime(*info.date_time),
                ))
                total_size += info.file_size
                compressed_size += info.compress_size
            
            return ArchiveInfo(
                format=ArchiveFormat.ZIP,
                total_size=total_size,
                compressed_size=compressed_size,
                entry_count=len(entries),
                is_encrypted=any(info.flag_bits & 0x1 for info in zf.infolist()),
                comment=zf.comment.decode() if zf.comment else "",
                entries=entries,
            )
    
    async def _get_tar_info(self, data: bytes) -> ArchiveInfo:
        """Get TAR archive info."""
        buffer = io.BytesIO(data)
        
        # Determine format
        format = ArchiveFormat.TAR
        
        try:
            with tarfile.open(fileobj=buffer, mode='r:*') as tf:
                entries = []
                total_size = 0
                
                for member in tf.getmembers():
                    entries.append(ArchiveEntry(
                        name=member.name,
                        size=member.size,
                        compressed_size=member.size,
                        is_directory=member.isdir(),
                        is_file=member.isfile(),
                        modified_time=datetime.fromtimestamp(member.mtime),
                        permissions=member.mode,
                    ))
                    total_size += member.size
                
                return ArchiveInfo(
                    format=format,
                    total_size=total_size,
                    compressed_size=len(data),
                    entry_count=len(entries),
                    entries=entries,
                )
        except:
            raise ArchiveError("Not a valid TAR archive")
    
    async def create_zip(
        self,
        files: List[Tuple[str, bytes]],
        compression: CompressionLevel = CompressionLevel.NORMAL,
        password: Optional[str] = None,
        comment: str = "",
    ) -> CreatedArchive:
        """
        Create ZIP archive.
        
        Args:
            files: List of (name, content) tuples
            compression: Compression level
            password: Archive password
            comment: Archive comment
            
        Returns:
            Created archive
        """
        buffer = io.BytesIO()
        
        # Map compression level
        compression_type = zipfile.ZIP_DEFLATED
        if compression == CompressionLevel.STORE:
            compression_type = zipfile.ZIP_STORED
        
        with zipfile.ZipFile(
            buffer,
            'w',
            compression=compression_type,
            compresslevel=compression.value if compression != CompressionLevel.STORE else None,
        ) as zf:
            for name, content in files:
                zf.writestr(name, content)
            
            if comment:
                zf.comment = comment.encode()
        
        content = buffer.getvalue()
        
        return CreatedArchive(
            content=content,
            format=ArchiveFormat.ZIP,
            size=len(content),
            entry_count=len(files),
            is_encrypted=password is not None,
        )
    
    async def create_tar(
        self,
        files: List[Tuple[str, bytes]],
        compression: Optional[str] = "gz",
    ) -> CreatedArchive:
        """
        Create TAR archive.
        
        Args:
            files: List of (name, content) tuples
            compression: Compression type (gz, bz2, xz, or None)
            
        Returns:
            Created archive
        """
        buffer = io.BytesIO()
        
        mode = f"w:{compression}" if compression else "w"
        format = {
            "gz": ArchiveFormat.TAR_GZ,
            "bz2": ArchiveFormat.TAR_BZ2,
            "xz": ArchiveFormat.TAR_XZ,
            None: ArchiveFormat.TAR,
        }.get(compression, ArchiveFormat.TAR_GZ)
        
        with tarfile.open(fileobj=buffer, mode=mode) as tf:
            for name, content in files:
                info = tarfile.TarInfo(name=name)
                info.size = len(content)
                info.mtime = int(datetime.utcnow().timestamp())
                tf.addfile(info, io.BytesIO(content))
        
        content = buffer.getvalue()
        
        return CreatedArchive(
            content=content,
            format=format,
            size=len(content),
            entry_count=len(files),
        )
    
    async def create(
        self,
        files: List[Tuple[str, bytes]],
        options: Optional[CreateOptions] = None,
    ) -> CreatedArchive:
        """
        Create archive.
        
        Args:
            files: List of (name, content) tuples
            options: Creation options
            
        Returns:
            Created archive
        """
        options = options or CreateOptions()
        
        if options.format == ArchiveFormat.ZIP:
            return await self.create_zip(
                files,
                options.compression,
                options.password,
                options.comment,
            )
        elif options.format in (
            ArchiveFormat.TAR,
            ArchiveFormat.TAR_GZ,
            ArchiveFormat.TAR_BZ2,
            ArchiveFormat.TAR_XZ,
        ):
            compression = {
                ArchiveFormat.TAR: None,
                ArchiveFormat.TAR_GZ: "gz",
                ArchiveFormat.TAR_BZ2: "bz2",
                ArchiveFormat.TAR_XZ: "xz",
            }.get(options.format)
            return await self.create_tar(files, compression)
        else:
            raise ArchiveError(f"Unsupported format: {options.format}")
    
    async def extract(
        self,
        data: bytes,
        options: Optional[ExtractOptions] = None,
    ) -> List[ExtractedFile]:
        """
        Extract archive.
        
        Args:
            data: Archive bytes
            options: Extraction options
            
        Returns:
            List of extracted files
        """
        options = options or ExtractOptions()
        
        # Try ZIP first
        try:
            return await self._extract_zip(data, options)
        except zipfile.BadZipFile:
            pass
        
        # Try TAR
        try:
            return await self._extract_tar(data, options)
        except:
            pass
        
        raise ArchiveError("Unknown archive format")
    
    async def _extract_zip(
        self,
        data: bytes,
        options: ExtractOptions,
    ) -> List[ExtractedFile]:
        """Extract ZIP archive."""
        buffer = io.BytesIO(data)
        files = []
        
        with zipfile.ZipFile(buffer, 'r') as zf:
            # Set password if provided
            if options.password:
                zf.setpassword(options.password.encode())
            
            for info in zf.infolist():
                # Skip directories
                if info.is_dir():
                    continue
                
                # Check pattern
                if options.pattern:
                    import fnmatch
                    if not fnmatch.fnmatch(info.filename, options.pattern):
                        continue
                
                # Check max size
                if options.max_size and info.file_size > options.max_size:
                    continue
                
                # Extract
                content = zf.read(info)
                
                # Determine path
                if options.flatten:
                    path = os.path.basename(info.filename)
                else:
                    path = info.filename
                
                files.append(ExtractedFile(
                    name=os.path.basename(info.filename),
                    path=path,
                    content=content,
                    size=len(content),
                    modified_time=datetime(*info.date_time),
                ))
        
        return files
    
    async def _extract_tar(
        self,
        data: bytes,
        options: ExtractOptions,
    ) -> List[ExtractedFile]:
        """Extract TAR archive."""
        buffer = io.BytesIO(data)
        files = []
        
        with tarfile.open(fileobj=buffer, mode='r:*') as tf:
            for member in tf.getmembers():
                # Skip non-files
                if not member.isfile():
                    continue
                
                # Check pattern
                if options.pattern:
                    import fnmatch
                    if not fnmatch.fnmatch(member.name, options.pattern):
                        continue
                
                # Check max size
                if options.max_size and member.size > options.max_size:
                    continue
                
                # Extract
                f = tf.extractfile(member)
                if f:
                    content = f.read()
                    
                    # Determine path
                    if options.flatten:
                        path = os.path.basename(member.name)
                    else:
                        path = member.name
                    
                    files.append(ExtractedFile(
                        name=os.path.basename(member.name),
                        path=path,
                        content=content,
                        size=len(content),
                        modified_time=datetime.fromtimestamp(member.mtime),
                    ))
        
        return files
    
    async def extract_file(
        self,
        data: bytes,
        filename: str,
        password: Optional[str] = None,
    ) -> Optional[bytes]:
        """
        Extract single file from archive.
        
        Args:
            data: Archive bytes
            filename: File to extract
            password: Archive password
            
        Returns:
            File content or None
        """
        options = ExtractOptions(
            password=password,
            pattern=filename,
        )
        
        files = await self.extract(data, options)
        
        for file in files:
            if file.name == filename or file.path == filename:
                return file.content
        
        return None
    
    async def list_entries(
        self,
        data: bytes,
        password: Optional[str] = None,
    ) -> List[ArchiveEntry]:
        """List archive entries."""
        info = await self.get_info(data, password)
        return info.entries
    
    async def stream(
        self,
        data: bytes,
        password: Optional[str] = None,
    ) -> AsyncIterator[ArchiveEntry]:
        """
        Stream archive entries.
        
        Args:
            data: Archive bytes
            password: Archive password
            
        Yields:
            Archive entries with content
        """
        options = ExtractOptions(password=password)
        files = await self.extract(data, options)
        
        for file in files:
            yield ArchiveEntry(
                name=file.name,
                size=file.size,
                is_file=True,
                modified_time=file.modified_time,
                content=file.content,
            )
    
    async def add_to_archive(
        self,
        archive_data: bytes,
        files: List[Tuple[str, bytes]],
        format: ArchiveFormat = ArchiveFormat.ZIP,
    ) -> CreatedArchive:
        """
        Add files to existing archive.
        
        Args:
            archive_data: Existing archive
            files: New files to add
            format: Archive format
            
        Returns:
            Updated archive
        """
        # Extract existing files
        existing = await self.extract(archive_data)
        
        # Combine with new files
        all_files = [(f.path, f.content) for f in existing]
        all_files.extend(files)
        
        # Create new archive
        options = CreateOptions(format=format)
        return await self.create(all_files, options)
    
    async def compress(
        self,
        data: bytes,
        format: str = "gzip",
    ) -> bytes:
        """
        Compress data.
        
        Args:
            data: Data to compress
            format: Compression format (gzip, bz2)
            
        Returns:
            Compressed data
        """
        if format == "gzip":
            return gzip.compress(data)
        elif format == "bz2":
            import bz2
            return bz2.compress(data)
        else:
            raise ArchiveError(f"Unknown compression format: {format}")
    
    async def decompress(
        self,
        data: bytes,
        format: str = "gzip",
    ) -> bytes:
        """
        Decompress data.
        
        Args:
            data: Compressed data
            format: Compression format
            
        Returns:
            Decompressed data
        """
        if format == "gzip":
            return gzip.decompress(data)
        elif format == "bz2":
            import bz2
            return bz2.decompress(data)
        else:
            raise ArchiveError(f"Unknown compression format: {format}")
    
    async def save(
        self,
        archive: CreatedArchive,
        path: Union[str, Path],
    ) -> Path:
        """Save archive to file."""
        path = Path(path)
        path.write_bytes(archive.content)
        return path


# Builder
class ArchiveBuilder:
    """Fluent archive builder."""
    
    def __init__(
        self,
        format: ArchiveFormat = ArchiveFormat.ZIP,
    ):
        self._format = format
        self._files: List[Tuple[str, bytes]] = []
        self._options = CreateOptions(format=format)
        self._manager = ArchiveManager()
    
    def add_file(
        self,
        name: str,
        content: bytes,
    ) -> "ArchiveBuilder":
        """Add file to archive."""
        self._files.append((name, content))
        return self
    
    def add_files(
        self,
        files: List[Tuple[str, bytes]],
    ) -> "ArchiveBuilder":
        """Add multiple files."""
        self._files.extend(files)
        return self
    
    def add_directory(
        self,
        path: Union[str, Path],
        base_name: str = "",
    ) -> "ArchiveBuilder":
        """Add directory contents."""
        path = Path(path)
        
        for file_path in path.rglob("*"):
            if file_path.is_file():
                rel_path = file_path.relative_to(path)
                name = f"{base_name}/{rel_path}" if base_name else str(rel_path)
                self._files.append((name, file_path.read_bytes()))
        
        return self
    
    def set_password(self, password: str) -> "ArchiveBuilder":
        """Set archive password."""
        self._options.password = password
        return self
    
    def set_compression(
        self,
        level: CompressionLevel,
    ) -> "ArchiveBuilder":
        """Set compression level."""
        self._options.compression = level
        return self
    
    def set_comment(self, comment: str) -> "ArchiveBuilder":
        """Set archive comment."""
        self._options.comment = comment
        return self
    
    async def build(self) -> CreatedArchive:
        """Build archive."""
        return await self._manager.create(self._files, self._options)


# Factory functions
def create_archive_manager(
    temp_dir: Optional[Path] = None,
    max_size: int = 1024 * 1024 * 1024,
) -> ArchiveManager:
    """Create archive manager."""
    return ArchiveManager(temp_dir, max_size)


def create_archive_builder(
    format: ArchiveFormat = ArchiveFormat.ZIP,
) -> ArchiveBuilder:
    """Create archive builder."""
    return ArchiveBuilder(format)


def create_create_options(
    format: ArchiveFormat = ArchiveFormat.ZIP,
    compression: CompressionLevel = CompressionLevel.NORMAL,
    **kwargs,
) -> CreateOptions:
    """Create creation options."""
    return CreateOptions(format=format, compression=compression, **kwargs)


def create_extract_options(
    password: Optional[str] = None,
    pattern: Optional[str] = None,
    **kwargs,
) -> ExtractOptions:
    """Create extraction options."""
    return ExtractOptions(password=password, pattern=pattern, **kwargs)


__all__ = [
    # Exceptions
    "ArchiveError",
    "ExtractionError",
    "CompressionError",
    # Enums
    "ArchiveFormat",
    "CompressionLevel",
    # Data classes
    "ArchiveEntry",
    "ArchiveInfo",
    "CreateOptions",
    "ExtractOptions",
    "CreatedArchive",
    "ExtractedFile",
    # Manager
    "ArchiveManager",
    # Builder
    "ArchiveBuilder",
    # Factory functions
    "create_archive_manager",
    "create_archive_builder",
    "create_create_options",
    "create_extract_options",
]
