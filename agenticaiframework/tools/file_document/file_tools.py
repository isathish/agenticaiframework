"""
File Reading, Writing, and Directory Tools.
"""

import os
import glob
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ..base import BaseTool, ToolConfig

logger = logging.getLogger(__name__)


class FileReadTool(BaseTool):
    """
    Tool for reading file contents.
    
    Supports:
    - Text files (.txt, .md, .json, .yaml, etc.)
    - Binary file detection
    - Encoding handling
    - Large file streaming
    """
    
    def __init__(
        self,
        config: Optional[ToolConfig] = None,
        encoding: str = 'utf-8',
        max_size_mb: float = 10.0,
    ):
        super().__init__(config or ToolConfig(
            name="FileReadTool",
            description="Read contents of text files"
        ))
        self.encoding = encoding
        self.max_size_mb = max_size_mb
    
    def _execute(
        self,
        file_path: str,
        encoding: Optional[str] = None,
        lines: Optional[int] = None,
        start_line: int = 0,
    ) -> Dict[str, Any]:
        """
        Read file contents.
        
        Args:
            file_path: Path to the file
            encoding: File encoding (default: utf-8)
            lines: Number of lines to read (None = all)
            start_line: Line to start reading from
            
        Returns:
            Dict with content and metadata
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        if not path.is_file():
            raise ValueError(f"Not a file: {file_path}")
        
        # Check file size
        size_mb = path.stat().st_size / (1024 * 1024)
        if size_mb > self.max_size_mb:
            raise ValueError(
                f"File too large: {size_mb:.2f}MB > {self.max_size_mb}MB"
            )
        
        enc = encoding or self.encoding
        
        try:
            with open(path, 'r', encoding=enc) as f:
                if lines is not None:
                    content_lines = f.readlines()
                    end_line = start_line + lines
                    content = ''.join(content_lines[start_line:end_line])
                    total_lines = len(content_lines)
                else:
                    content = f.read()
                    total_lines = content.count('\n') + 1
        except UnicodeDecodeError:
            # Try binary read for detection
            with open(path, 'rb') as f:
                raw = f.read(1024)
                if b'\x00' in raw:
                    raise ValueError("Binary file detected, cannot read as text")
                raise
        
        return {
            'content': content,
            'file_path': str(path.absolute()),
            'file_name': path.name,
            'extension': path.suffix,
            'size_bytes': path.stat().st_size,
            'total_lines': total_lines,
            'encoding': enc,
        }


class FileWriteTool(BaseTool):
    """
    Tool for writing content to files.
    
    Supports:
    - Create new files
    - Overwrite existing files
    - Append mode
    - Create directories if needed
    """
    
    def __init__(
        self,
        config: Optional[ToolConfig] = None,
        encoding: str = 'utf-8',
        create_dirs: bool = True,
    ):
        super().__init__(config or ToolConfig(
            name="FileWriteTool",
            description="Write content to files"
        ))
        self.encoding = encoding
        self.create_dirs = create_dirs
    
    def _execute(
        self,
        file_path: str,
        content: str,
        mode: str = 'w',
        encoding: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Write content to file.
        
        Args:
            file_path: Path to write to
            content: Content to write
            mode: Write mode ('w' = overwrite, 'a' = append)
            encoding: File encoding
            
        Returns:
            Dict with write result
        """
        path = Path(file_path)
        
        if mode not in ('w', 'a'):
            raise ValueError(f"Invalid mode: {mode}. Use 'w' or 'a'")
        
        # Create directories if needed
        if self.create_dirs:
            path.parent.mkdir(parents=True, exist_ok=True)
        
        enc = encoding or self.encoding
        
        with open(path, mode, encoding=enc) as f:
            f.write(content)
        
        return {
            'file_path': str(path.absolute()),
            'file_name': path.name,
            'bytes_written': len(content.encode(enc)),
            'mode': mode,
            'encoding': enc,
        }


class DirectoryReadTool(BaseTool):
    """
    Tool for reading directory contents.
    
    Supports:
    - List files and directories
    - Recursive listing
    - Pattern matching (glob)
    - File metadata
    """
    
    def __init__(
        self,
        config: Optional[ToolConfig] = None,
        include_hidden: bool = False,
    ):
        super().__init__(config or ToolConfig(
            name="DirectoryReadTool",
            description="List directory contents"
        ))
        self.include_hidden = include_hidden
    
    def _execute(
        self,
        directory: str,
        pattern: str = "*",
        recursive: bool = False,
        include_files: bool = True,
        include_dirs: bool = True,
        max_depth: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Read directory contents.
        
        Args:
            directory: Directory path
            pattern: Glob pattern for filtering
            recursive: Include subdirectories
            include_files: Include files in results
            include_dirs: Include directories in results
            max_depth: Maximum recursion depth
            
        Returns:
            Dict with directory listing
        """
        dir_path = Path(directory)
        
        if not dir_path.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")
        
        if not dir_path.is_dir():
            raise ValueError(f"Not a directory: {directory}")
        
        items = []
        
        if recursive:
            glob_pattern = f"**/{pattern}"
        else:
            glob_pattern = pattern
        
        for item in dir_path.glob(glob_pattern):
            # Skip hidden files if configured
            if not self.include_hidden and item.name.startswith('.'):
                continue
            
            # Check depth limit
            if max_depth is not None and recursive:
                rel_path = item.relative_to(dir_path)
                if len(rel_path.parts) > max_depth:
                    continue
            
            is_file = item.is_file()
            is_dir = item.is_dir()
            
            if (is_file and include_files) or (is_dir and include_dirs):
                stat = item.stat()
                items.append({
                    'name': item.name,
                    'path': str(item.absolute()),
                    'relative_path': str(item.relative_to(dir_path)),
                    'is_file': is_file,
                    'is_directory': is_dir,
                    'size': stat.st_size if is_file else None,
                    'modified': stat.st_mtime,
                    'extension': item.suffix if is_file else None,
                })
        
        return {
            'directory': str(dir_path.absolute()),
            'pattern': pattern,
            'recursive': recursive,
            'total_items': len(items),
            'items': items,
        }


__all__ = ['FileReadTool', 'FileWriteTool', 'DirectoryReadTool']
