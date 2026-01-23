"""
Enterprise Export Module.

Provides data export capabilities to various formats
including CSV, JSON, Excel, XML, and more.

Example:
    # Create exporter
    exporter = create_exporter("csv")
    
    # Export data
    await exporter.export(data, "output.csv")
    
    # With streaming for large datasets
    async with exporter.stream("large_output.csv") as writer:
        async for record in records:
            await writer.write(record)
    
    # Report generation
    report = create_report_builder()
    report.title("Sales Report")
    report.add_section("Summary", summary_data)
    report.add_table("Details", detail_rows)
    await report.export_pdf("report.pdf")
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
    TypeVar,
    Union,
)

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ExportError(Exception):
    """Export error."""
    pass


class FormatError(ExportError):
    """Format conversion error."""
    pass


class ExportFormat(str, Enum):
    """Export formats."""
    CSV = "csv"
    JSON = "json"
    JSONL = "jsonl"  # JSON Lines
    XML = "xml"
    HTML = "html"
    MARKDOWN = "markdown"
    YAML = "yaml"
    TSV = "tsv"
    EXCEL = "excel"
    PARQUET = "parquet"


class Compression(str, Enum):
    """Compression types."""
    NONE = "none"
    GZIP = "gzip"
    ZIP = "zip"
    BZIP2 = "bzip2"


@dataclass
class ExportConfig:
    """Export configuration."""
    format: ExportFormat = ExportFormat.JSON
    compression: Compression = Compression.NONE
    encoding: str = "utf-8"
    pretty: bool = True
    include_headers: bool = True
    date_format: str = "%Y-%m-%d %H:%M:%S"
    null_value: str = ""


@dataclass
class ExportResult:
    """Export result."""
    path: str
    format: ExportFormat
    size_bytes: int
    record_count: int
    duration_ms: float
    compressed: bool = False


@dataclass
class ColumnConfig:
    """Column configuration for tabular export."""
    name: str
    source: Optional[str] = None  # Source field name
    width: Optional[int] = None
    format: Optional[str] = None
    transform: Optional[Callable] = None
    header: Optional[str] = None  # Display header


class Exporter(ABC):
    """Abstract exporter."""
    
    @abstractmethod
    async def export(
        self,
        data: Any,
        destination: Union[str, IO],
    ) -> ExportResult:
        """Export data to destination."""
        pass
    
    @abstractmethod
    def export_sync(
        self,
        data: Any,
        destination: Union[str, IO],
    ) -> ExportResult:
        """Synchronous export."""
        pass


class CSVExporter(Exporter):
    """CSV exporter."""
    
    def __init__(
        self,
        config: Optional[ExportConfig] = None,
        columns: Optional[List[ColumnConfig]] = None,
    ):
        self._config = config or ExportConfig(format=ExportFormat.CSV)
        self._columns = columns
    
    async def export(
        self,
        data: List[Dict[str, Any]],
        destination: Union[str, IO],
    ) -> ExportResult:
        """Export data to CSV."""
        return await asyncio.get_event_loop().run_in_executor(
            None, self.export_sync, data, destination
        )
    
    def export_sync(
        self,
        data: List[Dict[str, Any]],
        destination: Union[str, IO],
    ) -> ExportResult:
        """Synchronous CSV export."""
        import time
        start = time.time()
        
        if not data:
            raise ExportError("No data to export")
        
        # Determine columns
        if self._columns:
            fieldnames = [c.header or c.name for c in self._columns]
            source_fields = [c.source or c.name for c in self._columns]
        else:
            source_fields = list(data[0].keys())
            fieldnames = source_fields
        
        # Handle file or IO
        should_close = False
        if isinstance(destination, str):
            f = open(destination, 'w', newline='', encoding=self._config.encoding)
            should_close = True
        else:
            f = destination
        
        try:
            writer = csv.writer(f)
            
            # Write header
            if self._config.include_headers:
                writer.writerow(fieldnames)
            
            # Write data
            for row in data:
                values = []
                for i, field_name in enumerate(source_fields):
                    value = row.get(field_name, self._config.null_value)
                    
                    # Apply transform
                    if self._columns and self._columns[i].transform:
                        value = self._columns[i].transform(value)
                    
                    # Format value
                    value = self._format_value(value)
                    values.append(value)
                
                writer.writerow(values)
            
            # Get file size
            if isinstance(destination, str):
                size = os.path.getsize(destination)
            else:
                size = f.tell() if hasattr(f, 'tell') else 0
            
            return ExportResult(
                path=destination if isinstance(destination, str) else "<stream>",
                format=ExportFormat.CSV,
                size_bytes=size,
                record_count=len(data),
                duration_ms=(time.time() - start) * 1000,
            )
        
        finally:
            if should_close:
                f.close()
    
    def _format_value(self, value: Any) -> str:
        """Format value for CSV."""
        if value is None:
            return self._config.null_value
        elif isinstance(value, datetime):
            return value.strftime(self._config.date_format)
        elif isinstance(value, (list, dict)):
            return json.dumps(value)
        return str(value)


class JSONExporter(Exporter):
    """JSON exporter."""
    
    def __init__(
        self,
        config: Optional[ExportConfig] = None,
    ):
        self._config = config or ExportConfig(format=ExportFormat.JSON)
    
    async def export(
        self,
        data: Any,
        destination: Union[str, IO],
    ) -> ExportResult:
        """Export data to JSON."""
        return await asyncio.get_event_loop().run_in_executor(
            None, self.export_sync, data, destination
        )
    
    def export_sync(
        self,
        data: Any,
        destination: Union[str, IO],
    ) -> ExportResult:
        """Synchronous JSON export."""
        import time
        start = time.time()
        
        indent = 2 if self._config.pretty else None
        
        json_str = json.dumps(
            data,
            indent=indent,
            default=self._json_serializer,
            ensure_ascii=False,
        )
        
        if isinstance(destination, str):
            with open(destination, 'w', encoding=self._config.encoding) as f:
                f.write(json_str)
            size = os.path.getsize(destination)
        else:
            destination.write(json_str)
            size = len(json_str.encode(self._config.encoding))
        
        record_count = len(data) if isinstance(data, list) else 1
        
        return ExportResult(
            path=destination if isinstance(destination, str) else "<stream>",
            format=ExportFormat.JSON,
            size_bytes=size,
            record_count=record_count,
            duration_ms=(time.time() - start) * 1000,
        )
    
    def _json_serializer(self, obj: Any) -> Any:
        """Custom JSON serializer."""
        if isinstance(obj, datetime):
            return obj.strftime(self._config.date_format)
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


class JSONLExporter(Exporter):
    """JSON Lines exporter (one JSON object per line)."""
    
    def __init__(
        self,
        config: Optional[ExportConfig] = None,
    ):
        self._config = config or ExportConfig(format=ExportFormat.JSONL)
    
    async def export(
        self,
        data: List[Any],
        destination: Union[str, IO],
    ) -> ExportResult:
        """Export data to JSON Lines."""
        return await asyncio.get_event_loop().run_in_executor(
            None, self.export_sync, data, destination
        )
    
    def export_sync(
        self,
        data: List[Any],
        destination: Union[str, IO],
    ) -> ExportResult:
        """Synchronous JSONL export."""
        import time
        start = time.time()
        
        should_close = False
        if isinstance(destination, str):
            f = open(destination, 'w', encoding=self._config.encoding)
            should_close = True
        else:
            f = destination
        
        try:
            for item in data:
                line = json.dumps(item, default=str, ensure_ascii=False)
                f.write(line + '\n')
            
            if isinstance(destination, str):
                size = os.path.getsize(destination)
            else:
                size = f.tell() if hasattr(f, 'tell') else 0
            
            return ExportResult(
                path=destination if isinstance(destination, str) else "<stream>",
                format=ExportFormat.JSONL,
                size_bytes=size,
                record_count=len(data),
                duration_ms=(time.time() - start) * 1000,
            )
        finally:
            if should_close:
                f.close()


class XMLExporter(Exporter):
    """XML exporter."""
    
    def __init__(
        self,
        config: Optional[ExportConfig] = None,
        root_element: str = "data",
        row_element: str = "item",
    ):
        self._config = config or ExportConfig(format=ExportFormat.XML)
        self._root = root_element
        self._row = row_element
    
    async def export(
        self,
        data: Any,
        destination: Union[str, IO],
    ) -> ExportResult:
        """Export data to XML."""
        return await asyncio.get_event_loop().run_in_executor(
            None, self.export_sync, data, destination
        )
    
    def export_sync(
        self,
        data: Any,
        destination: Union[str, IO],
    ) -> ExportResult:
        """Synchronous XML export."""
        import time
        start = time.time()
        
        xml_str = self._to_xml(data)
        
        if isinstance(destination, str):
            with open(destination, 'w', encoding=self._config.encoding) as f:
                f.write(xml_str)
            size = os.path.getsize(destination)
        else:
            destination.write(xml_str)
            size = len(xml_str.encode(self._config.encoding))
        
        record_count = len(data) if isinstance(data, list) else 1
        
        return ExportResult(
            path=destination if isinstance(destination, str) else "<stream>",
            format=ExportFormat.XML,
            size_bytes=size,
            record_count=record_count,
            duration_ms=(time.time() - start) * 1000,
        )
    
    def _to_xml(self, data: Any) -> str:
        """Convert data to XML string."""
        lines = ['<?xml version="1.0" encoding="UTF-8"?>']
        lines.append(f'<{self._root}>')
        
        if isinstance(data, list):
            for item in data:
                lines.extend(self._element_to_xml(self._row, item, indent=2))
        else:
            lines.extend(self._element_to_xml(self._row, data, indent=2))
        
        lines.append(f'</{self._root}>')
        
        return '\n'.join(lines)
    
    def _element_to_xml(
        self,
        name: str,
        value: Any,
        indent: int = 0,
    ) -> List[str]:
        """Convert element to XML lines."""
        prefix = ' ' * indent
        
        if value is None:
            return [f'{prefix}<{name}/>']
        
        elif isinstance(value, dict):
            lines = [f'{prefix}<{name}>']
            for k, v in value.items():
                lines.extend(self._element_to_xml(k, v, indent + 2))
            lines.append(f'{prefix}</{name}>')
            return lines
        
        elif isinstance(value, list):
            lines = []
            for item in value:
                lines.extend(self._element_to_xml(name, item, indent))
            return lines
        
        else:
            escaped = self._escape_xml(str(value))
            return [f'{prefix}<{name}>{escaped}</{name}>']
    
    def _escape_xml(self, s: str) -> str:
        """Escape XML special characters."""
        return (s
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&apos;'))


class MarkdownExporter(Exporter):
    """Markdown table exporter."""
    
    def __init__(
        self,
        config: Optional[ExportConfig] = None,
        columns: Optional[List[ColumnConfig]] = None,
    ):
        self._config = config or ExportConfig(format=ExportFormat.MARKDOWN)
        self._columns = columns
    
    async def export(
        self,
        data: List[Dict[str, Any]],
        destination: Union[str, IO],
    ) -> ExportResult:
        """Export data to Markdown table."""
        return await asyncio.get_event_loop().run_in_executor(
            None, self.export_sync, data, destination
        )
    
    def export_sync(
        self,
        data: List[Dict[str, Any]],
        destination: Union[str, IO],
    ) -> ExportResult:
        """Synchronous Markdown export."""
        import time
        start = time.time()
        
        if not data:
            raise ExportError("No data to export")
        
        # Determine columns
        if self._columns:
            headers = [c.header or c.name for c in self._columns]
            fields = [c.source or c.name for c in self._columns]
        else:
            fields = list(data[0].keys())
            headers = fields
        
        # Build markdown table
        lines = []
        
        # Header row
        lines.append('| ' + ' | '.join(headers) + ' |')
        lines.append('| ' + ' | '.join(['---'] * len(headers)) + ' |')
        
        # Data rows
        for row in data:
            values = []
            for field_name in fields:
                value = row.get(field_name, '')
                values.append(str(value).replace('|', '\\|'))
            lines.append('| ' + ' | '.join(values) + ' |')
        
        content = '\n'.join(lines)
        
        if isinstance(destination, str):
            with open(destination, 'w', encoding=self._config.encoding) as f:
                f.write(content)
            size = os.path.getsize(destination)
        else:
            destination.write(content)
            size = len(content.encode(self._config.encoding))
        
        return ExportResult(
            path=destination if isinstance(destination, str) else "<stream>",
            format=ExportFormat.MARKDOWN,
            size_bytes=size,
            record_count=len(data),
            duration_ms=(time.time() - start) * 1000,
        )


class HTMLExporter(Exporter):
    """HTML table exporter."""
    
    def __init__(
        self,
        config: Optional[ExportConfig] = None,
        title: str = "Export",
        css: Optional[str] = None,
    ):
        self._config = config or ExportConfig(format=ExportFormat.HTML)
        self._title = title
        self._css = css or self._default_css()
    
    def _default_css(self) -> str:
        return """
        body { font-family: Arial, sans-serif; margin: 20px; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #4CAF50; color: white; }
        tr:nth-child(even) { background-color: #f2f2f2; }
        tr:hover { background-color: #ddd; }
        """
    
    async def export(
        self,
        data: List[Dict[str, Any]],
        destination: Union[str, IO],
    ) -> ExportResult:
        """Export data to HTML."""
        return await asyncio.get_event_loop().run_in_executor(
            None, self.export_sync, data, destination
        )
    
    def export_sync(
        self,
        data: List[Dict[str, Any]],
        destination: Union[str, IO],
    ) -> ExportResult:
        """Synchronous HTML export."""
        import time
        start = time.time()
        
        if not data:
            raise ExportError("No data to export")
        
        headers = list(data[0].keys())
        
        html_parts = [
            '<!DOCTYPE html>',
            '<html><head>',
            f'<title>{self._title}</title>',
            f'<style>{self._css}</style>',
            '</head><body>',
            f'<h1>{self._title}</h1>',
            '<table>',
            '<thead><tr>',
        ]
        
        # Headers
        for h in headers:
            html_parts.append(f'<th>{h}</th>')
        html_parts.append('</tr></thead>')
        
        # Body
        html_parts.append('<tbody>')
        for row in data:
            html_parts.append('<tr>')
            for h in headers:
                value = row.get(h, '')
                html_parts.append(f'<td>{self._escape_html(str(value))}</td>')
            html_parts.append('</tr>')
        html_parts.append('</tbody>')
        
        html_parts.extend(['</table>', '</body></html>'])
        
        content = '\n'.join(html_parts)
        
        if isinstance(destination, str):
            with open(destination, 'w', encoding=self._config.encoding) as f:
                f.write(content)
            size = os.path.getsize(destination)
        else:
            destination.write(content)
            size = len(content.encode(self._config.encoding))
        
        return ExportResult(
            path=destination if isinstance(destination, str) else "<stream>",
            format=ExportFormat.HTML,
            size_bytes=size,
            record_count=len(data),
            duration_ms=(time.time() - start) * 1000,
        )
    
    def _escape_html(self, s: str) -> str:
        """Escape HTML special characters."""
        return (s
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;'))


class StreamingExporter:
    """
    Streaming exporter for large datasets.
    """
    
    def __init__(
        self,
        exporter: Exporter,
        chunk_size: int = 1000,
    ):
        self._exporter = exporter
        self._chunk_size = chunk_size
    
    async def export_iterator(
        self,
        iterator: AsyncIterator[Dict[str, Any]],
        destination: str,
    ) -> ExportResult:
        """Export from async iterator."""
        import time
        start = time.time()
        
        chunk = []
        total_records = 0
        
        # First chunk determines headers
        first_chunk = True
        
        async for item in iterator:
            chunk.append(item)
            
            if len(chunk) >= self._chunk_size:
                await self._write_chunk(chunk, destination, first_chunk)
                total_records += len(chunk)
                chunk = []
                first_chunk = False
        
        # Write remaining
        if chunk:
            await self._write_chunk(chunk, destination, first_chunk)
            total_records += len(chunk)
        
        size = os.path.getsize(destination) if os.path.exists(destination) else 0
        
        return ExportResult(
            path=destination,
            format=ExportFormat.CSV,
            size_bytes=size,
            record_count=total_records,
            duration_ms=(time.time() - start) * 1000,
        )
    
    async def _write_chunk(
        self,
        chunk: List[Dict[str, Any]],
        destination: str,
        include_headers: bool,
    ) -> None:
        """Write a chunk to file."""
        mode = 'w' if include_headers else 'a'
        
        with open(destination, mode, newline='') as f:
            if chunk:
                writer = csv.DictWriter(f, fieldnames=chunk[0].keys())
                if include_headers:
                    writer.writeheader()
                writer.writerows(chunk)


class ReportBuilder:
    """
    Build reports with multiple sections.
    """
    
    def __init__(self, title: str = "Report"):
        self._title = title
        self._sections: List[Dict[str, Any]] = []
        self._metadata: Dict[str, Any] = {
            "created_at": datetime.now(),
            "author": "",
        }
    
    def title(self, title: str) -> "ReportBuilder":
        """Set report title."""
        self._title = title
        return self
    
    def author(self, author: str) -> "ReportBuilder":
        """Set author."""
        self._metadata["author"] = author
        return self
    
    def add_section(
        self,
        name: str,
        content: Any,
        section_type: str = "text",
    ) -> "ReportBuilder":
        """Add a section to the report."""
        self._sections.append({
            "name": name,
            "content": content,
            "type": section_type,
        })
        return self
    
    def add_table(
        self,
        name: str,
        data: List[Dict[str, Any]],
        columns: Optional[List[str]] = None,
    ) -> "ReportBuilder":
        """Add a table section."""
        self._sections.append({
            "name": name,
            "content": data,
            "type": "table",
            "columns": columns,
        })
        return self
    
    def add_chart(
        self,
        name: str,
        chart_type: str,
        data: Any,
    ) -> "ReportBuilder":
        """Add a chart section (placeholder for visualization)."""
        self._sections.append({
            "name": name,
            "content": data,
            "type": "chart",
            "chart_type": chart_type,
        })
        return self
    
    async def export_html(self, path: str) -> ExportResult:
        """Export report as HTML."""
        html = self._build_html()
        
        with open(path, 'w') as f:
            f.write(html)
        
        return ExportResult(
            path=path,
            format=ExportFormat.HTML,
            size_bytes=os.path.getsize(path),
            record_count=len(self._sections),
            duration_ms=0,
        )
    
    async def export_markdown(self, path: str) -> ExportResult:
        """Export report as Markdown."""
        md = self._build_markdown()
        
        with open(path, 'w') as f:
            f.write(md)
        
        return ExportResult(
            path=path,
            format=ExportFormat.MARKDOWN,
            size_bytes=os.path.getsize(path),
            record_count=len(self._sections),
            duration_ms=0,
        )
    
    def _build_html(self) -> str:
        """Build HTML report."""
        parts = [
            '<!DOCTYPE html>',
            '<html><head>',
            f'<title>{self._title}</title>',
            '<style>',
            'body { font-family: Arial; max-width: 1200px; margin: 0 auto; padding: 20px; }',
            'table { border-collapse: collapse; width: 100%; margin: 20px 0; }',
            'th, td { border: 1px solid #ddd; padding: 8px; }',
            'th { background: #f5f5f5; }',
            '</style>',
            '</head><body>',
            f'<h1>{self._title}</h1>',
            f'<p>Generated: {self._metadata["created_at"]}</p>',
        ]
        
        for section in self._sections:
            parts.append(f'<h2>{section["name"]}</h2>')
            
            if section["type"] == "table":
                parts.append(self._table_to_html(section["content"]))
            elif section["type"] == "text":
                parts.append(f'<p>{section["content"]}</p>')
        
        parts.extend(['</body></html>'])
        return '\n'.join(parts)
    
    def _build_markdown(self) -> str:
        """Build Markdown report."""
        parts = [
            f'# {self._title}',
            '',
            f'*Generated: {self._metadata["created_at"]}*',
            '',
        ]
        
        for section in self._sections:
            parts.append(f'## {section["name"]}')
            parts.append('')
            
            if section["type"] == "table":
                parts.append(self._table_to_markdown(section["content"]))
            elif section["type"] == "text":
                parts.append(str(section["content"]))
            
            parts.append('')
        
        return '\n'.join(parts)
    
    def _table_to_html(self, data: List[Dict]) -> str:
        """Convert table data to HTML."""
        if not data:
            return '<p>No data</p>'
        
        headers = list(data[0].keys())
        rows = ['<table><thead><tr>']
        rows.extend(f'<th>{h}</th>' for h in headers)
        rows.append('</tr></thead><tbody>')
        
        for row in data:
            rows.append('<tr>')
            for h in headers:
                rows.append(f'<td>{row.get(h, "")}</td>')
            rows.append('</tr>')
        
        rows.append('</tbody></table>')
        return ''.join(rows)
    
    def _table_to_markdown(self, data: List[Dict]) -> str:
        """Convert table data to Markdown."""
        if not data:
            return 'No data'
        
        headers = list(data[0].keys())
        lines = ['| ' + ' | '.join(headers) + ' |']
        lines.append('| ' + ' | '.join(['---'] * len(headers)) + ' |')
        
        for row in data:
            values = [str(row.get(h, '')) for h in headers]
            lines.append('| ' + ' | '.join(values) + ' |')
        
        return '\n'.join(lines)


# Factory functions
def create_exporter(
    format: Union[str, ExportFormat],
    **kwargs: Any,
) -> Exporter:
    """Create an exporter for the specified format."""
    if isinstance(format, str):
        format = ExportFormat(format.lower())
    
    exporters = {
        ExportFormat.CSV: CSVExporter,
        ExportFormat.JSON: JSONExporter,
        ExportFormat.JSONL: JSONLExporter,
        ExportFormat.XML: XMLExporter,
        ExportFormat.MARKDOWN: MarkdownExporter,
        ExportFormat.HTML: HTMLExporter,
    }
    
    if format not in exporters:
        raise ExportError(f"Unsupported format: {format}")
    
    return exporters[format](**kwargs)


def create_report_builder(title: str = "Report") -> ReportBuilder:
    """Create a report builder."""
    return ReportBuilder(title)


def create_streaming_exporter(
    format: Union[str, ExportFormat] = "csv",
    chunk_size: int = 1000,
) -> StreamingExporter:
    """Create a streaming exporter."""
    base = create_exporter(format)
    return StreamingExporter(base, chunk_size)


# Decorators
def export_result(
    format: ExportFormat = ExportFormat.JSON,
    path_fn: Optional[Callable] = None,
) -> Callable:
    """
    Decorator to export function result.
    
    Example:
        @export_result(ExportFormat.CSV, path_fn=lambda: f"output_{datetime.now()}.csv")
        async def generate_report():
            return [{"a": 1}, {"a": 2}]
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> ExportResult:
            result = await func(*args, **kwargs)
            
            path = path_fn() if path_fn else f"export_{datetime.now().timestamp()}.{format.value}"
            
            exporter = create_exporter(format)
            return await exporter.export(result, path)
        
        return wrapper
    
    return decorator


__all__ = [
    # Exceptions
    "ExportError",
    "FormatError",
    # Enums
    "ExportFormat",
    "Compression",
    # Data classes
    "ExportConfig",
    "ExportResult",
    "ColumnConfig",
    # Core classes
    "Exporter",
    "CSVExporter",
    "JSONExporter",
    "JSONLExporter",
    "XMLExporter",
    "MarkdownExporter",
    "HTMLExporter",
    "StreamingExporter",
    "ReportBuilder",
    # Factory functions
    "create_exporter",
    "create_report_builder",
    "create_streaming_exporter",
    # Decorators
    "export_result",
]
