"""
Enterprise Import Module.

Provides data import capabilities from various formats
including CSV, JSON, Excel, XML, and more.

Example:
    # Create importer
    importer = create_importer("csv")
    
    # Import data
    data = await importer.import_file("data.csv")
    
    # With schema validation
    importer = create_importer("json", schema=UserSchema)
    users = await importer.import_file("users.json")
    
    # Streaming import for large files
    async for batch in importer.stream("large.csv", batch_size=1000):
        await process_batch(batch)
    
    # With transformation
    @import_handler("csv")
    def process_import(data: List[dict]) -> List[User]:
        return [User(**row) for row in data]
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
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
    IO,
    Iterator,
    List,
    Optional,
    TextIO,
    Tuple,
    Type,
    TypeVar,
    Union,
)

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ImportError(Exception):
    """Import error."""
    pass


class ParseError(ImportError):
    """Parse error."""
    pass


class ValidationError(ImportError):
    """Validation error during import."""
    pass


class ImportFormat(str, Enum):
    """Import formats."""
    CSV = "csv"
    JSON = "json"
    JSONL = "jsonl"
    XML = "xml"
    YAML = "yaml"
    TSV = "tsv"
    INI = "ini"
    ENV = "env"
    PROPERTIES = "properties"


@dataclass
class ImportConfig:
    """Import configuration."""
    format: ImportFormat = ImportFormat.JSON
    encoding: str = "utf-8"
    skip_empty: bool = True
    skip_errors: bool = False
    trim_whitespace: bool = True
    date_formats: List[str] = field(default_factory=lambda: [
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
    ])


@dataclass
class ImportResult(Generic[T]):
    """Import result."""
    data: T
    source: str
    format: ImportFormat
    record_count: int
    duration_ms: float
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class FieldSpec:
    """Field specification for import."""
    name: str
    source: Optional[str] = None
    type: Optional[type] = None
    required: bool = False
    default: Any = None
    transform: Optional[Callable] = None
    validators: List[Callable] = field(default_factory=list)


@dataclass
class ImportStats:
    """Import statistics."""
    total_imports: int = 0
    total_records: int = 0
    failed_records: int = 0
    total_bytes: int = 0


class Importer(ABC):
    """Abstract importer."""
    
    @abstractmethod
    async def import_file(
        self,
        source: Union[str, IO],
    ) -> ImportResult:
        """Import data from file."""
        pass
    
    @abstractmethod
    def import_file_sync(
        self,
        source: Union[str, IO],
    ) -> ImportResult:
        """Synchronous import."""
        pass


class CSVImporter(Importer):
    """CSV importer."""
    
    def __init__(
        self,
        config: Optional[ImportConfig] = None,
        fields: Optional[List[FieldSpec]] = None,
        delimiter: str = ",",
        has_header: bool = True,
    ):
        self._config = config or ImportConfig(format=ImportFormat.CSV)
        self._fields = fields
        self._delimiter = delimiter
        self._has_header = has_header
    
    async def import_file(
        self,
        source: Union[str, IO],
    ) -> ImportResult[List[Dict[str, Any]]]:
        """Import CSV file."""
        return await asyncio.get_event_loop().run_in_executor(
            None, self.import_file_sync, source
        )
    
    def import_file_sync(
        self,
        source: Union[str, IO],
    ) -> ImportResult[List[Dict[str, Any]]]:
        """Synchronous CSV import."""
        import time
        start = time.time()
        
        records = []
        errors = []
        warnings = []
        
        should_close = False
        if isinstance(source, str):
            f = open(source, 'r', encoding=self._config.encoding)
            should_close = True
            source_name = source
        else:
            f = source
            source_name = getattr(source, 'name', '<stream>')
        
        try:
            reader = csv.DictReader(f, delimiter=self._delimiter)
            
            for row_num, row in enumerate(reader, start=1):
                try:
                    processed = self._process_row(row)
                    
                    if processed or not self._config.skip_empty:
                        records.append(processed)
                
                except Exception as e:
                    error_msg = f"Row {row_num}: {str(e)}"
                    errors.append(error_msg)
                    
                    if not self._config.skip_errors:
                        raise ParseError(error_msg)
            
            duration_ms = (time.time() - start) * 1000
            
            return ImportResult(
                data=records,
                source=source_name,
                format=ImportFormat.CSV,
                record_count=len(records),
                duration_ms=duration_ms,
                errors=errors,
                warnings=warnings,
            )
        
        finally:
            if should_close:
                f.close()
    
    def _process_row(
        self,
        row: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Process a single row."""
        if not self._fields:
            # Return row with trimmed values
            return {
                k: v.strip() if self._config.trim_whitespace and isinstance(v, str) else v
                for k, v in row.items()
            }
        
        result = {}
        
        for field_spec in self._fields:
            source_name = field_spec.source or field_spec.name
            value = row.get(source_name, field_spec.default)
            
            # Trim whitespace
            if self._config.trim_whitespace and isinstance(value, str):
                value = value.strip()
            
            # Handle empty values
            if value == '' or value is None:
                if field_spec.required:
                    raise ValidationError(f"Missing required field: {field_spec.name}")
                value = field_spec.default
            
            # Type conversion
            if field_spec.type and value is not None:
                value = self._convert_type(value, field_spec.type)
            
            # Transform
            if field_spec.transform:
                value = field_spec.transform(value)
            
            # Validate
            for validator in field_spec.validators:
                if not validator(value):
                    raise ValidationError(
                        f"Validation failed for field: {field_spec.name}"
                    )
            
            result[field_spec.name] = value
        
        return result
    
    def _convert_type(self, value: Any, target_type: type) -> Any:
        """Convert value to target type."""
        if target_type == str:
            return str(value)
        elif target_type == int:
            return int(float(value))
        elif target_type == float:
            return float(value)
        elif target_type == bool:
            return value.lower() in ('true', '1', 'yes', 'on')
        elif target_type == datetime:
            return self._parse_date(value)
        return value
    
    def _parse_date(self, value: str) -> datetime:
        """Parse date string."""
        for fmt in self._config.date_formats:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        raise ParseError(f"Cannot parse date: {value}")
    
    async def stream(
        self,
        source: str,
        batch_size: int = 1000,
    ) -> AsyncIterator[List[Dict[str, Any]]]:
        """Stream CSV file in batches."""
        with open(source, 'r', encoding=self._config.encoding) as f:
            reader = csv.DictReader(f, delimiter=self._delimiter)
            batch = []
            
            for row in reader:
                try:
                    processed = self._process_row(row)
                    batch.append(processed)
                    
                    if len(batch) >= batch_size:
                        yield batch
                        batch = []
                
                except Exception:
                    if not self._config.skip_errors:
                        raise
            
            if batch:
                yield batch


class JSONImporter(Importer):
    """JSON importer."""
    
    def __init__(
        self,
        config: Optional[ImportConfig] = None,
        schema: Optional[Type[T]] = None,
    ):
        self._config = config or ImportConfig(format=ImportFormat.JSON)
        self._schema = schema
    
    async def import_file(
        self,
        source: Union[str, IO],
    ) -> ImportResult:
        """Import JSON file."""
        return await asyncio.get_event_loop().run_in_executor(
            None, self.import_file_sync, source
        )
    
    def import_file_sync(
        self,
        source: Union[str, IO],
    ) -> ImportResult:
        """Synchronous JSON import."""
        import time
        start = time.time()
        
        if isinstance(source, str):
            with open(source, 'r', encoding=self._config.encoding) as f:
                data = json.load(f)
            source_name = source
        else:
            data = json.load(source)
            source_name = getattr(source, 'name', '<stream>')
        
        # Validate against schema if provided
        if self._schema:
            data = self._validate_schema(data)
        
        record_count = len(data) if isinstance(data, list) else 1
        
        return ImportResult(
            data=data,
            source=source_name,
            format=ImportFormat.JSON,
            record_count=record_count,
            duration_ms=(time.time() - start) * 1000,
        )
    
    def import_string(self, content: str) -> Any:
        """Import from JSON string."""
        return json.loads(content)
    
    def _validate_schema(self, data: Any) -> Any:
        """Validate data against schema."""
        # Simple validation - can be extended
        if self._schema and hasattr(self._schema, '__dataclass_fields__'):
            if isinstance(data, list):
                return [self._schema(**item) for item in data]
            return self._schema(**data)
        return data


class JSONLImporter(Importer):
    """JSON Lines importer."""
    
    def __init__(
        self,
        config: Optional[ImportConfig] = None,
    ):
        self._config = config or ImportConfig(format=ImportFormat.JSONL)
    
    async def import_file(
        self,
        source: Union[str, IO],
    ) -> ImportResult[List[Any]]:
        """Import JSONL file."""
        return await asyncio.get_event_loop().run_in_executor(
            None, self.import_file_sync, source
        )
    
    def import_file_sync(
        self,
        source: Union[str, IO],
    ) -> ImportResult[List[Any]]:
        """Synchronous JSONL import."""
        import time
        start = time.time()
        
        records = []
        errors = []
        
        should_close = False
        if isinstance(source, str):
            f = open(source, 'r', encoding=self._config.encoding)
            should_close = True
            source_name = source
        else:
            f = source
            source_name = getattr(source, 'name', '<stream>')
        
        try:
            for line_num, line in enumerate(f, start=1):
                line = line.strip()
                
                if not line:
                    continue
                
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as e:
                    error_msg = f"Line {line_num}: {str(e)}"
                    errors.append(error_msg)
                    
                    if not self._config.skip_errors:
                        raise ParseError(error_msg)
            
            return ImportResult(
                data=records,
                source=source_name,
                format=ImportFormat.JSONL,
                record_count=len(records),
                duration_ms=(time.time() - start) * 1000,
                errors=errors,
            )
        
        finally:
            if should_close:
                f.close()
    
    async def stream(
        self,
        source: str,
        batch_size: int = 1000,
    ) -> AsyncIterator[List[Any]]:
        """Stream JSONL file in batches."""
        with open(source, 'r', encoding=self._config.encoding) as f:
            batch = []
            
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                try:
                    batch.append(json.loads(line))
                    
                    if len(batch) >= batch_size:
                        yield batch
                        batch = []
                
                except json.JSONDecodeError:
                    if not self._config.skip_errors:
                        raise
            
            if batch:
                yield batch


class XMLImporter(Importer):
    """XML importer."""
    
    def __init__(
        self,
        config: Optional[ImportConfig] = None,
        item_tag: str = "item",
    ):
        self._config = config or ImportConfig(format=ImportFormat.XML)
        self._item_tag = item_tag
    
    async def import_file(
        self,
        source: Union[str, IO],
    ) -> ImportResult:
        """Import XML file."""
        return await asyncio.get_event_loop().run_in_executor(
            None, self.import_file_sync, source
        )
    
    def import_file_sync(
        self,
        source: Union[str, IO],
    ) -> ImportResult:
        """Synchronous XML import."""
        import time
        import xml.etree.ElementTree as ET
        
        start = time.time()
        
        if isinstance(source, str):
            tree = ET.parse(source)
            source_name = source
        else:
            tree = ET.parse(source)
            source_name = getattr(source, 'name', '<stream>')
        
        root = tree.getroot()
        records = self._parse_element(root)
        
        record_count = len(records) if isinstance(records, list) else 1
        
        return ImportResult(
            data=records,
            source=source_name,
            format=ImportFormat.XML,
            record_count=record_count,
            duration_ms=(time.time() - start) * 1000,
        )
    
    def _parse_element(self, element) -> Any:
        """Parse XML element to dict."""
        result = {}
        
        # Attributes
        if element.attrib:
            result.update(element.attrib)
        
        # Children
        children = list(element)
        
        if not children:
            # Leaf node
            text = element.text
            if text:
                text = text.strip()
                if text:
                    if result:
                        result['_text'] = text
                    else:
                        return text
            return result if result else None
        
        # Parse children
        for child in children:
            child_data = self._parse_element(child)
            
            if child.tag in result:
                # Convert to list
                if not isinstance(result[child.tag], list):
                    result[child.tag] = [result[child.tag]]
                result[child.tag].append(child_data)
            else:
                result[child.tag] = child_data
        
        return result


class EnvImporter(Importer):
    """Environment file (.env) importer."""
    
    def __init__(
        self,
        config: Optional[ImportConfig] = None,
    ):
        self._config = config or ImportConfig(format=ImportFormat.ENV)
    
    async def import_file(
        self,
        source: Union[str, IO],
    ) -> ImportResult[Dict[str, str]]:
        """Import .env file."""
        return await asyncio.get_event_loop().run_in_executor(
            None, self.import_file_sync, source
        )
    
    def import_file_sync(
        self,
        source: Union[str, IO],
    ) -> ImportResult[Dict[str, str]]:
        """Synchronous .env import."""
        import time
        start = time.time()
        
        env_vars = {}
        
        should_close = False
        if isinstance(source, str):
            f = open(source, 'r', encoding=self._config.encoding)
            should_close = True
            source_name = source
        else:
            f = source
            source_name = getattr(source, 'name', '<stream>')
        
        try:
            for line in f:
                line = line.strip()
                
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue
                
                # Parse KEY=VALUE
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # Remove quotes
                    if (value.startswith('"') and value.endswith('"')) or \
                       (value.startswith("'") and value.endswith("'")):
                        value = value[1:-1]
                    
                    env_vars[key] = value
            
            return ImportResult(
                data=env_vars,
                source=source_name,
                format=ImportFormat.ENV,
                record_count=len(env_vars),
                duration_ms=(time.time() - start) * 1000,
            )
        
        finally:
            if should_close:
                f.close()


class DataLoader:
    """
    High-level data loader with automatic format detection.
    """
    
    FORMAT_EXTENSIONS = {
        '.csv': ImportFormat.CSV,
        '.json': ImportFormat.JSON,
        '.jsonl': ImportFormat.JSONL,
        '.ndjson': ImportFormat.JSONL,
        '.xml': ImportFormat.XML,
        '.tsv': ImportFormat.TSV,
        '.env': ImportFormat.ENV,
    }
    
    def __init__(
        self,
        config: Optional[ImportConfig] = None,
    ):
        self._config = config or ImportConfig()
    
    async def load(
        self,
        source: str,
        format: Optional[ImportFormat] = None,
    ) -> ImportResult:
        """Load data from file with auto-detection."""
        if format is None:
            format = self._detect_format(source)
        
        importer = create_importer(format)
        return await importer.import_file(source)
    
    def load_sync(
        self,
        source: str,
        format: Optional[ImportFormat] = None,
    ) -> ImportResult:
        """Synchronous load."""
        if format is None:
            format = self._detect_format(source)
        
        importer = create_importer(format)
        return importer.import_file_sync(source)
    
    def _detect_format(self, source: str) -> ImportFormat:
        """Detect format from file extension."""
        ext = Path(source).suffix.lower()
        
        if ext in self.FORMAT_EXTENSIONS:
            return self.FORMAT_EXTENSIONS[ext]
        
        raise ImportError(f"Cannot detect format for: {source}")


class BatchImporter:
    """
    Import multiple files in batch.
    """
    
    def __init__(
        self,
        loader: Optional[DataLoader] = None,
    ):
        self._loader = loader or DataLoader()
    
    async def import_directory(
        self,
        directory: str,
        pattern: str = "*",
        recursive: bool = False,
    ) -> List[ImportResult]:
        """Import all matching files in directory."""
        from pathlib import Path
        
        path = Path(directory)
        
        if recursive:
            files = list(path.rglob(pattern))
        else:
            files = list(path.glob(pattern))
        
        results = []
        
        for file_path in files:
            if file_path.is_file():
                try:
                    result = await self._loader.load(str(file_path))
                    results.append(result)
                except Exception as e:
                    logger.warning(f"Failed to import {file_path}: {e}")
        
        return results
    
    async def import_files(
        self,
        files: List[str],
    ) -> List[ImportResult]:
        """Import multiple files."""
        tasks = [self._loader.load(f) for f in files]
        return await asyncio.gather(*tasks, return_exceptions=True)


# Factory functions
def create_importer(
    format: Union[str, ImportFormat],
    **kwargs: Any,
) -> Importer:
    """Create an importer for the specified format."""
    if isinstance(format, str):
        format = ImportFormat(format.lower())
    
    importers = {
        ImportFormat.CSV: CSVImporter,
        ImportFormat.TSV: lambda **kw: CSVImporter(delimiter='\t', **kw),
        ImportFormat.JSON: JSONImporter,
        ImportFormat.JSONL: JSONLImporter,
        ImportFormat.XML: XMLImporter,
        ImportFormat.ENV: EnvImporter,
    }
    
    if format not in importers:
        raise ImportError(f"Unsupported format: {format}")
    
    return importers[format](**kwargs)


def create_data_loader(
    config: Optional[ImportConfig] = None,
) -> DataLoader:
    """Create a data loader."""
    return DataLoader(config)


def create_batch_importer() -> BatchImporter:
    """Create a batch importer."""
    return BatchImporter()


# Decorators
def import_handler(
    format: Union[str, ImportFormat],
    **importer_kwargs: Any,
) -> Callable:
    """
    Decorator to create an import handler.
    
    Example:
        @import_handler("csv")
        def process_csv(data: List[dict]) -> List[User]:
            return [User(**row) for row in data]
    """
    def decorator(func: Callable) -> Callable:
        importer = create_importer(format, **importer_kwargs)
        
        @wraps(func)
        async def wrapper(source: str) -> Any:
            result = await importer.import_file(source)
            return func(result.data)
        
        return wrapper
    
    return decorator


def validate_import(
    validator: Callable[[Any], bool],
) -> Callable:
    """
    Decorator to validate imported data.
    
    Example:
        @validate_import(lambda data: len(data) > 0)
        async def process(data):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(data: Any, *args: Any, **kwargs: Any) -> Any:
            if not validator(data):
                raise ValidationError("Import validation failed")
            return await func(data, *args, **kwargs)
        
        return wrapper
    
    return decorator


__all__ = [
    # Exceptions
    "ImportError",
    "ParseError",
    "ValidationError",
    # Enums
    "ImportFormat",
    # Data classes
    "ImportConfig",
    "ImportResult",
    "FieldSpec",
    "ImportStats",
    # Core classes
    "Importer",
    "CSVImporter",
    "JSONImporter",
    "JSONLImporter",
    "XMLImporter",
    "EnvImporter",
    "DataLoader",
    "BatchImporter",
    # Factory functions
    "create_importer",
    "create_data_loader",
    "create_batch_importer",
    # Decorators
    "import_handler",
    "validate_import",
]
