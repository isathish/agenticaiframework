"""
Enterprise Report Generator Module.

Provides report generation with multiple formats,
data aggregation, charts, and scheduling.

Example:
    # Create report generator
    reports = create_report_generator()
    
    # Register report definition
    @reports.define("sales_report")
    async def sales_report(start_date: date, end_date: date):
        return {
            "title": "Sales Report",
            "sections": [
                {"type": "summary", "data": ...},
                {"type": "chart", "data": ...},
                {"type": "table", "data": ...},
            ],
        }
    
    # Generate report
    doc = await reports.generate(
        "sales_report",
        params={"start_date": "2024-01-01", "end_date": "2024-01-31"},
        format="pdf",
    )
"""

from __future__ import annotations

import asyncio
import csv
import functools
import io
import json
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    TypeVar,
    Union,
)

T = TypeVar('T')


logger = logging.getLogger(__name__)


class ReportError(Exception):
    """Report error."""
    pass


class GenerationError(ReportError):
    """Report generation error."""
    pass


class ReportFormat(str, Enum):
    """Report output formats."""
    PDF = "pdf"
    HTML = "html"
    CSV = "csv"
    EXCEL = "excel"
    JSON = "json"


class SectionType(str, Enum):
    """Report section types."""
    TITLE = "title"
    SUMMARY = "summary"
    TEXT = "text"
    TABLE = "table"
    CHART = "chart"
    IMAGE = "image"
    PAGEBREAK = "pagebreak"


class ChartType(str, Enum):
    """Chart types."""
    LINE = "line"
    BAR = "bar"
    PIE = "pie"
    AREA = "area"
    SCATTER = "scatter"


@dataclass
class ChartConfig:
    """Chart configuration."""
    type: ChartType = ChartType.BAR
    title: str = ""
    x_label: str = ""
    y_label: str = ""
    legend: bool = True
    width: int = 600
    height: int = 400
    colors: List[str] = field(default_factory=list)


@dataclass
class TableConfig:
    """Table configuration."""
    headers: List[str] = field(default_factory=list)
    column_widths: List[int] = field(default_factory=list)
    striped: bool = True
    bordered: bool = True
    sortable: bool = False
    pagination: bool = False
    page_size: int = 50


@dataclass
class ReportSection:
    """Report section."""
    type: SectionType
    title: str = ""
    data: Any = None
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReportDefinition:
    """Report definition."""
    id: str
    name: str
    description: str = ""
    generator: Optional[Callable] = None
    parameters: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    default_format: ReportFormat = ReportFormat.PDF
    template: str = ""
    styles: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ReportData:
    """Generated report data."""
    title: str = ""
    subtitle: str = ""
    sections: List[ReportSection] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    generated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class GeneratedReport:
    """Generated report output."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    report_id: str = ""
    format: ReportFormat = ReportFormat.PDF
    content: bytes = b""
    filename: str = ""
    size: int = 0
    parameters: Dict[str, Any] = field(default_factory=dict)
    generated_at: datetime = field(default_factory=datetime.utcnow)
    generation_time_ms: float = 0


@dataclass
class ScheduledReport:
    """Scheduled report."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    report_id: str = ""
    cron: str = ""  # Cron expression
    parameters: Dict[str, Any] = field(default_factory=dict)
    format: ReportFormat = ReportFormat.PDF
    recipients: List[str] = field(default_factory=list)
    enabled: bool = True
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None


# Formatters
class ReportFormatter(ABC):
    """Abstract report formatter."""
    
    @property
    @abstractmethod
    def format(self) -> ReportFormat:
        """Supported format."""
        pass
    
    @abstractmethod
    async def format_report(
        self,
        data: ReportData,
        definition: ReportDefinition,
    ) -> bytes:
        """Format report to output."""
        pass


class HTMLFormatter(ReportFormatter):
    """HTML report formatter."""
    
    @property
    def format(self) -> ReportFormat:
        return ReportFormat.HTML
    
    async def format_report(
        self,
        data: ReportData,
        definition: ReportDefinition,
    ) -> bytes:
        html_parts = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            f"<title>{data.title}</title>",
            "<style>",
            "body { font-family: Arial, sans-serif; margin: 40px; }",
            "h1 { color: #333; }",
            "h2 { color: #666; border-bottom: 1px solid #ddd; padding-bottom: 10px; }",
            "table { border-collapse: collapse; width: 100%; margin: 20px 0; }",
            "th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }",
            "th { background-color: #f4f4f4; }",
            "tr:nth-child(even) { background-color: #f9f9f9; }",
            ".summary { background-color: #f0f8ff; padding: 20px; border-radius: 5px; }",
            ".chart { margin: 20px 0; text-align: center; }",
            "</style>",
            "</head>",
            "<body>",
            f"<h1>{data.title}</h1>",
        ]
        
        if data.subtitle:
            html_parts.append(f"<p><em>{data.subtitle}</em></p>")
        
        for section in data.sections:
            html_parts.append(self._render_section(section))
        
        html_parts.append(
            f"<footer><p>Generated: {data.generated_at.isoformat()}</p></footer>"
        )
        html_parts.extend(["</body>", "</html>"])
        
        return "\n".join(html_parts).encode()
    
    def _render_section(self, section: ReportSection) -> str:
        if section.type == SectionType.TITLE:
            return f"<h2>{section.title}</h2>"
        
        elif section.type == SectionType.TEXT:
            return f"<p>{section.data}</p>"
        
        elif section.type == SectionType.SUMMARY:
            items = []
            if isinstance(section.data, dict):
                for key, value in section.data.items():
                    items.append(f"<p><strong>{key}:</strong> {value}</p>")
            return f'<div class="summary">{" ".join(items)}</div>'
        
        elif section.type == SectionType.TABLE:
            return self._render_table(section)
        
        elif section.type == SectionType.CHART:
            return f'<div class="chart"><p>[Chart: {section.title}]</p></div>'
        
        elif section.type == SectionType.PAGEBREAK:
            return '<div style="page-break-after: always;"></div>'
        
        return ""
    
    def _render_table(self, section: ReportSection) -> str:
        if not section.data:
            return ""
        
        config = TableConfig(**section.config) if section.config else TableConfig()
        
        html = ["<table>"]
        
        # Headers
        if config.headers:
            html.append("<thead><tr>")
            for header in config.headers:
                html.append(f"<th>{header}</th>")
            html.append("</tr></thead>")
        elif section.data and isinstance(section.data[0], dict):
            html.append("<thead><tr>")
            for key in section.data[0].keys():
                html.append(f"<th>{key}</th>")
            html.append("</tr></thead>")
        
        # Body
        html.append("<tbody>")
        for row in section.data:
            html.append("<tr>")
            if isinstance(row, dict):
                for value in row.values():
                    html.append(f"<td>{value}</td>")
            elif isinstance(row, (list, tuple)):
                for value in row:
                    html.append(f"<td>{value}</td>")
            html.append("</tr>")
        html.append("</tbody>")
        
        html.append("</table>")
        
        return "\n".join(html)


class CSVFormatter(ReportFormatter):
    """CSV report formatter."""
    
    @property
    def format(self) -> ReportFormat:
        return ReportFormat.CSV
    
    async def format_report(
        self,
        data: ReportData,
        definition: ReportDefinition,
    ) -> bytes:
        output = io.StringIO()
        writer = csv.writer(output)
        
        for section in data.sections:
            if section.type == SectionType.TABLE and section.data:
                # Write section title
                if section.title:
                    writer.writerow([section.title])
                    writer.writerow([])
                
                # Write headers
                config = TableConfig(**section.config) if section.config else TableConfig()
                
                if config.headers:
                    writer.writerow(config.headers)
                elif isinstance(section.data[0], dict):
                    writer.writerow(section.data[0].keys())
                
                # Write rows
                for row in section.data:
                    if isinstance(row, dict):
                        writer.writerow(row.values())
                    elif isinstance(row, (list, tuple)):
                        writer.writerow(row)
                
                writer.writerow([])
        
        return output.getvalue().encode()


class JSONFormatter(ReportFormatter):
    """JSON report formatter."""
    
    @property
    def format(self) -> ReportFormat:
        return ReportFormat.JSON
    
    async def format_report(
        self,
        data: ReportData,
        definition: ReportDefinition,
    ) -> bytes:
        output = {
            "title": data.title,
            "subtitle": data.subtitle,
            "generated_at": data.generated_at.isoformat(),
            "metadata": data.metadata,
            "sections": [],
        }
        
        for section in data.sections:
            output["sections"].append({
                "type": section.type.value,
                "title": section.title,
                "data": section.data,
                "config": section.config,
            })
        
        return json.dumps(output, indent=2, default=str).encode()


class ReportGenerator:
    """
    Report generation service.
    """
    
    def __init__(
        self,
        formatters: Optional[Dict[ReportFormat, ReportFormatter]] = None,
    ):
        self._definitions: Dict[str, ReportDefinition] = {}
        self._schedules: Dict[str, ScheduledReport] = {}
        
        # Initialize formatters
        self._formatters: Dict[ReportFormat, ReportFormatter] = formatters or {
            ReportFormat.HTML: HTMLFormatter(),
            ReportFormat.CSV: CSVFormatter(),
            ReportFormat.JSON: JSONFormatter(),
        }
    
    def define(
        self,
        report_id: str,
        name: Optional[str] = None,
        description: str = "",
        default_format: ReportFormat = ReportFormat.PDF,
        parameters: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Callable:
        """Decorator to define a report."""
        def decorator(func: Callable) -> Callable:
            definition = ReportDefinition(
                id=report_id,
                name=name or report_id,
                description=description,
                generator=func,
                parameters=parameters or {},
                default_format=default_format,
            )
            self._definitions[report_id] = definition
            return func
        return decorator
    
    def register(
        self,
        definition: ReportDefinition,
    ) -> None:
        """Register report definition."""
        self._definitions[definition.id] = definition
    
    def get_definition(
        self,
        report_id: str,
    ) -> Optional[ReportDefinition]:
        """Get report definition."""
        return self._definitions.get(report_id)
    
    def list_definitions(self) -> List[ReportDefinition]:
        """List all report definitions."""
        return list(self._definitions.values())
    
    async def generate(
        self,
        report_id: str,
        params: Optional[Dict[str, Any]] = None,
        format: Optional[ReportFormat] = None,
    ) -> GeneratedReport:
        """
        Generate report.
        
        Args:
            report_id: Report definition ID
            params: Report parameters
            format: Output format
            
        Returns:
            Generated report
        """
        import time
        start_time = time.time()
        
        definition = self._definitions.get(report_id)
        if not definition:
            raise ReportError(f"Report not found: {report_id}")
        
        format = format or definition.default_format
        
        # Generate report data
        if definition.generator:
            data = await definition.generator(**(params or {}))
            
            if isinstance(data, dict):
                data = ReportData(
                    title=data.get("title", definition.name),
                    subtitle=data.get("subtitle", ""),
                    sections=[
                        ReportSection(**s) if isinstance(s, dict) else s
                        for s in data.get("sections", [])
                    ],
                    metadata=data.get("metadata", {}),
                )
        else:
            data = ReportData(title=definition.name)
        
        # Format report
        formatter = self._formatters.get(format)
        if not formatter:
            raise ReportError(f"No formatter for format: {format}")
        
        content = await formatter.format_report(data, definition)
        
        generation_time = (time.time() - start_time) * 1000
        
        # Generate filename
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        ext = format.value
        filename = f"{report_id}_{timestamp}.{ext}"
        
        return GeneratedReport(
            report_id=report_id,
            format=format,
            content=content,
            filename=filename,
            size=len(content),
            parameters=params or {},
            generation_time_ms=generation_time,
        )
    
    async def generate_html(
        self,
        report_id: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> GeneratedReport:
        """Generate HTML report."""
        return await self.generate(report_id, params, ReportFormat.HTML)
    
    async def generate_csv(
        self,
        report_id: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> GeneratedReport:
        """Generate CSV report."""
        return await self.generate(report_id, params, ReportFormat.CSV)
    
    async def generate_json(
        self,
        report_id: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> GeneratedReport:
        """Generate JSON report."""
        return await self.generate(report_id, params, ReportFormat.JSON)
    
    # Scheduling
    def schedule(
        self,
        report_id: str,
        cron: str,
        params: Optional[Dict[str, Any]] = None,
        format: Optional[ReportFormat] = None,
        recipients: Optional[List[str]] = None,
    ) -> ScheduledReport:
        """Schedule report generation."""
        definition = self._definitions.get(report_id)
        if not definition:
            raise ReportError(f"Report not found: {report_id}")
        
        schedule = ScheduledReport(
            report_id=report_id,
            cron=cron,
            parameters=params or {},
            format=format or definition.default_format,
            recipients=recipients or [],
        )
        
        self._schedules[schedule.id] = schedule
        return schedule
    
    def unschedule(self, schedule_id: str) -> bool:
        """Remove scheduled report."""
        if schedule_id in self._schedules:
            del self._schedules[schedule_id]
            return True
        return False
    
    def list_schedules(self) -> List[ScheduledReport]:
        """List scheduled reports."""
        return list(self._schedules.values())


# Decorators
def report(
    report_id: str,
    name: Optional[str] = None,
    description: str = "",
    default_format: ReportFormat = ReportFormat.PDF,
) -> Callable:
    """Decorator to define a report (standalone)."""
    def decorator(func: Callable) -> Callable:
        func._report_id = report_id
        func._report_name = name or report_id
        func._report_description = description
        func._report_format = default_format
        return func
    return decorator


# Helper functions
def create_section(
    section_type: SectionType,
    title: str = "",
    data: Any = None,
    **config,
) -> ReportSection:
    """Create report section."""
    return ReportSection(
        type=section_type,
        title=title,
        data=data,
        config=config,
    )


def create_table_section(
    data: List[Dict[str, Any]],
    title: str = "",
    headers: Optional[List[str]] = None,
    **config,
) -> ReportSection:
    """Create table section."""
    if headers:
        config["headers"] = headers
    
    return ReportSection(
        type=SectionType.TABLE,
        title=title,
        data=data,
        config=config,
    )


def create_chart_section(
    data: Any,
    title: str = "",
    chart_type: ChartType = ChartType.BAR,
    **config,
) -> ReportSection:
    """Create chart section."""
    config["type"] = chart_type.value
    
    return ReportSection(
        type=SectionType.CHART,
        title=title,
        data=data,
        config=config,
    )


def create_summary_section(
    data: Dict[str, Any],
    title: str = "Summary",
) -> ReportSection:
    """Create summary section."""
    return ReportSection(
        type=SectionType.SUMMARY,
        title=title,
        data=data,
    )


# Factory functions
def create_report_generator(
    formatters: Optional[Dict[ReportFormat, ReportFormatter]] = None,
) -> ReportGenerator:
    """Create report generator."""
    return ReportGenerator(formatters)


def create_report_definition(
    report_id: str,
    name: str,
    generator: Callable,
    description: str = "",
    default_format: ReportFormat = ReportFormat.PDF,
    parameters: Optional[Dict[str, Dict[str, Any]]] = None,
) -> ReportDefinition:
    """Create report definition."""
    return ReportDefinition(
        id=report_id,
        name=name,
        description=description,
        generator=generator,
        parameters=parameters or {},
        default_format=default_format,
    )


def create_html_formatter() -> HTMLFormatter:
    """Create HTML formatter."""
    return HTMLFormatter()


def create_csv_formatter() -> CSVFormatter:
    """Create CSV formatter."""
    return CSVFormatter()


def create_json_formatter() -> JSONFormatter:
    """Create JSON formatter."""
    return JSONFormatter()


__all__ = [
    # Exceptions
    "ReportError",
    "GenerationError",
    # Enums
    "ReportFormat",
    "SectionType",
    "ChartType",
    # Data classes
    "ChartConfig",
    "TableConfig",
    "ReportSection",
    "ReportDefinition",
    "ReportData",
    "GeneratedReport",
    "ScheduledReport",
    # Formatters
    "ReportFormatter",
    "HTMLFormatter",
    "CSVFormatter",
    "JSONFormatter",
    # Generator
    "ReportGenerator",
    # Decorators
    "report",
    # Helper functions
    "create_section",
    "create_table_section",
    "create_chart_section",
    "create_summary_section",
    # Factory functions
    "create_report_generator",
    "create_report_definition",
    "create_html_formatter",
    "create_csv_formatter",
    "create_json_formatter",
]
