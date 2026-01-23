"""
Enterprise Report Builder Module.

Dynamic report generation with templates,
data aggregation, and multiple export formats.

Example:
    # Create report builder
    builder = create_report_builder()
    
    # Define report
    report = builder.create("Monthly Sales Report")
    report.add_section(TextSection("Executive Summary", summary_text))
    report.add_section(TableSection("Sales by Region", sales_data))
    report.add_section(ChartSection("Trend Analysis", chart_config))
    
    # Generate report
    pdf = report.export("pdf")
    html = report.export("html")
    excel = report.export("xlsx")
"""

from __future__ import annotations

import io
import json
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from pathlib import Path
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

T = TypeVar('T')

logger = logging.getLogger(__name__)


class ReportError(Exception):
    """Report error."""
    pass


class ExportFormat(str, Enum):
    """Export formats."""
    HTML = "html"
    PDF = "pdf"
    EXCEL = "xlsx"
    CSV = "csv"
    JSON = "json"
    MARKDOWN = "md"
    TEXT = "txt"


class SectionType(str, Enum):
    """Section types."""
    TEXT = "text"
    TABLE = "table"
    CHART = "chart"
    IMAGE = "image"
    HEADER = "header"
    FOOTER = "footer"
    PAGE_BREAK = "page_break"
    TOC = "toc"
    SUMMARY = "summary"


class Alignment(str, Enum):
    """Text alignment."""
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"
    JUSTIFY = "justify"


class AggregationType(str, Enum):
    """Data aggregation types."""
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    COUNT = "count"
    FIRST = "first"
    LAST = "last"


@dataclass
class PageSettings:
    """Page configuration."""
    size: str = "A4"
    orientation: str = "portrait"
    margin_top: int = 20
    margin_bottom: int = 20
    margin_left: int = 20
    margin_right: int = 20
    header_height: int = 30
    footer_height: int = 30


@dataclass
class StyleSettings:
    """Style configuration."""
    font_family: str = "Arial, sans-serif"
    font_size: int = 12
    title_size: int = 24
    heading_size: int = 18
    primary_color: str = "#2196F3"
    secondary_color: str = "#757575"
    background_color: str = "#ffffff"
    text_color: str = "#333333"


@dataclass
class ColumnConfig:
    """Table column configuration."""
    key: str
    label: str = ""
    width: Optional[int] = None
    alignment: Alignment = Alignment.LEFT
    format: str = ""
    aggregate: Optional[AggregationType] = None
    
    def __post_init__(self):
        if not self.label:
            self.label = self.key.replace("_", " ").title()


# Base section
@dataclass
class Section:
    """Base report section."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    section_type: SectionType = SectionType.TEXT
    visible: bool = True
    page_break_before: bool = False
    page_break_after: bool = False
    
    def render_html(self) -> str:
        """Render as HTML."""
        return ""
    
    def render_text(self) -> str:
        """Render as text."""
        return ""
    
    def render_data(self) -> Dict[str, Any]:
        """Render as data dict."""
        return {"type": self.section_type.value, "title": self.title}


@dataclass
class TextSection(Section):
    """Text content section."""
    content: str = ""
    format: str = "text"  # text, markdown, html
    alignment: Alignment = Alignment.LEFT
    
    def __post_init__(self):
        self.section_type = SectionType.TEXT
    
    def render_html(self) -> str:
        title_html = f"<h2>{self.title}</h2>" if self.title else ""
        return f"""
            <div class="section section-text" style="text-align: {self.alignment.value}">
                {title_html}
                <div class="content">{self.content}</div>
            </div>
        """
    
    def render_text(self) -> str:
        lines = []
        if self.title:
            lines.append(f"\n{self.title}")
            lines.append("=" * len(self.title))
        lines.append(self.content)
        return "\n".join(lines)


@dataclass
class TableSection(Section):
    """Table data section."""
    data: List[Dict[str, Any]] = field(default_factory=list)
    columns: List[ColumnConfig] = field(default_factory=list)
    show_row_numbers: bool = False
    show_totals: bool = False
    striped: bool = True
    
    def __post_init__(self):
        self.section_type = SectionType.TABLE
    
    def set_data(
        self,
        data: List[Dict[str, Any]],
        columns: Optional[List[str]] = None,
    ) -> None:
        """Set table data."""
        self.data = data
        if columns:
            self.columns = [ColumnConfig(key=c) for c in columns]
        elif data and not self.columns:
            self.columns = [ColumnConfig(key=k) for k in data[0].keys()]
    
    def calculate_totals(self) -> Dict[str, Any]:
        """Calculate column totals."""
        totals = {}
        for col in self.columns:
            if col.aggregate:
                values = [r.get(col.key, 0) for r in self.data]
                if col.aggregate == AggregationType.SUM:
                    totals[col.key] = sum(values)
                elif col.aggregate == AggregationType.AVG:
                    totals[col.key] = sum(values) / len(values) if values else 0
                elif col.aggregate == AggregationType.MIN:
                    totals[col.key] = min(values) if values else 0
                elif col.aggregate == AggregationType.MAX:
                    totals[col.key] = max(values) if values else 0
                elif col.aggregate == AggregationType.COUNT:
                    totals[col.key] = len(values)
        return totals
    
    def render_html(self) -> str:
        title_html = f"<h2>{self.title}</h2>" if self.title else ""
        
        # Headers
        headers = "".join(
            f'<th style="text-align: {c.alignment.value}">{c.label}</th>'
            for c in self.columns
        )
        if self.show_row_numbers:
            headers = "<th>#</th>" + headers
        
        # Rows
        rows = ""
        for i, row in enumerate(self.data):
            row_class = "odd" if i % 2 and self.striped else "even"
            cells = "".join(
                f'<td style="text-align: {c.alignment.value}">{row.get(c.key, "")}</td>'
                for c in self.columns
            )
            if self.show_row_numbers:
                cells = f"<td>{i + 1}</td>" + cells
            rows += f'<tr class="{row_class}">{cells}</tr>'
        
        # Totals
        totals_row = ""
        if self.show_totals:
            totals = self.calculate_totals()
            totals_cells = "".join(
                f'<td><strong>{totals.get(c.key, "")}</strong></td>'
                for c in self.columns
            )
            if self.show_row_numbers:
                totals_cells = "<td></td>" + totals_cells
            totals_row = f'<tr class="totals">{totals_cells}</tr>'
        
        return f"""
            <div class="section section-table">
                {title_html}
                <table>
                    <thead><tr>{headers}</tr></thead>
                    <tbody>{rows}</tbody>
                    {f'<tfoot>{totals_row}</tfoot>' if totals_row else ''}
                </table>
            </div>
        """
    
    def render_text(self) -> str:
        lines = []
        if self.title:
            lines.append(f"\n{self.title}")
            lines.append("-" * len(self.title))
        
        # Calculate column widths
        widths = {}
        for col in self.columns:
            widths[col.key] = max(
                len(col.label),
                max((len(str(r.get(col.key, ""))) for r in self.data), default=0)
            )
        
        # Header
        header = " | ".join(
            col.label.ljust(widths[col.key])
            for col in self.columns
        )
        lines.append(header)
        lines.append("-" * len(header))
        
        # Rows
        for row in self.data:
            line = " | ".join(
                str(row.get(col.key, "")).ljust(widths[col.key])
                for col in self.columns
            )
            lines.append(line)
        
        return "\n".join(lines)


@dataclass
class ChartSection(Section):
    """Chart section."""
    chart_type: str = "bar"
    data: Dict[str, Any] = field(default_factory=dict)
    width: int = 600
    height: int = 400
    
    def __post_init__(self):
        self.section_type = SectionType.CHART
    
    def render_html(self) -> str:
        title_html = f"<h2>{self.title}</h2>" if self.title else ""
        chart_id = f"chart-{self.id}"
        
        return f"""
            <div class="section section-chart">
                {title_html}
                <div id="{chart_id}" style="width: {self.width}px; height: {self.height}px;">
                    <canvas></canvas>
                </div>
                <script>
                    // Chart placeholder - integrate with Chart.js or similar
                    console.log('Chart data:', {json.dumps(self.data)});
                </script>
            </div>
        """
    
    def render_text(self) -> str:
        lines = []
        if self.title:
            lines.append(f"\n{self.title}")
            lines.append("-" * len(self.title))
        lines.append(f"[Chart: {self.chart_type}]")
        return "\n".join(lines)


@dataclass
class HeaderSection(Section):
    """Page header section."""
    logo_url: Optional[str] = None
    company_name: str = ""
    report_date: datetime = field(default_factory=datetime.utcnow)
    
    def __post_init__(self):
        self.section_type = SectionType.HEADER
    
    def render_html(self) -> str:
        logo_html = f'<img src="{self.logo_url}" alt="Logo" />' if self.logo_url else ""
        return f"""
            <header class="report-header">
                {logo_html}
                <div class="header-text">
                    <div class="company-name">{self.company_name}</div>
                    <div class="report-title">{self.title}</div>
                    <div class="report-date">{self.report_date.strftime('%Y-%m-%d')}</div>
                </div>
            </header>
        """


@dataclass
class FooterSection(Section):
    """Page footer section."""
    show_page_numbers: bool = True
    copyright_text: str = ""
    
    def __post_init__(self):
        self.section_type = SectionType.FOOTER
    
    def render_html(self) -> str:
        return f"""
            <footer class="report-footer">
                <div class="footer-left">{self.copyright_text}</div>
                {'<div class="footer-right">Page <span class="page-number"></span></div>' if self.show_page_numbers else ''}
            </footer>
        """


@dataclass
class SummarySection(Section):
    """Summary/metrics section."""
    metrics: List[Dict[str, Any]] = field(default_factory=list)
    columns: int = 4
    
    def __post_init__(self):
        self.section_type = SectionType.SUMMARY
    
    def add_metric(
        self,
        label: str,
        value: Any,
        unit: str = "",
        change: Optional[float] = None,
        change_label: str = "",
    ) -> None:
        """Add summary metric."""
        self.metrics.append({
            "label": label,
            "value": value,
            "unit": unit,
            "change": change,
            "change_label": change_label,
        })
    
    def render_html(self) -> str:
        title_html = f"<h2>{self.title}</h2>" if self.title else ""
        
        metrics_html = ""
        for metric in self.metrics:
            change_html = ""
            if metric.get("change") is not None:
                color = "green" if metric["change"] >= 0 else "red"
                arrow = "↑" if metric["change"] >= 0 else "↓"
                change_html = f'<span style="color: {color}">{arrow} {abs(metric["change"])}% {metric.get("change_label", "")}</span>'
            
            metrics_html += f"""
                <div class="metric-card">
                    <div class="metric-value">{metric['value']}{metric.get('unit', '')}</div>
                    <div class="metric-label">{metric['label']}</div>
                    {change_html}
                </div>
            """
        
        return f"""
            <div class="section section-summary">
                {title_html}
                <div class="metrics-grid" style="display: grid; grid-template-columns: repeat({self.columns}, 1fr); gap: 20px;">
                    {metrics_html}
                </div>
            </div>
        """


# Report
@dataclass
class Report:
    """Report container."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: str = ""
    sections: List[Section] = field(default_factory=list)
    page_settings: PageSettings = field(default_factory=PageSettings)
    style_settings: StyleSettings = field(default_factory=StyleSettings)
    created_at: datetime = field(default_factory=datetime.utcnow)
    author: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_section(self, section: Section) -> None:
        """Add section."""
        self.sections.append(section)
    
    def remove_section(self, section_id: str) -> bool:
        """Remove section."""
        for i, section in enumerate(self.sections):
            if section.id == section_id:
                self.sections.pop(i)
                return True
        return False
    
    def export(self, format: Union[str, ExportFormat]) -> bytes:
        """Export report."""
        if isinstance(format, str):
            format = ExportFormat(format)
        
        exporters = {
            ExportFormat.HTML: self._export_html,
            ExportFormat.JSON: self._export_json,
            ExportFormat.TEXT: self._export_text,
            ExportFormat.MARKDOWN: self._export_markdown,
            ExportFormat.CSV: self._export_csv,
        }
        
        exporter = exporters.get(format)
        if not exporter:
            raise ReportError(f"Unsupported format: {format}")
        
        return exporter()
    
    def _export_html(self) -> bytes:
        """Export as HTML."""
        style = self.style_settings
        
        sections_html = ""
        for section in self.sections:
            if not section.visible:
                continue
            if section.page_break_before:
                sections_html += '<div class="page-break"></div>'
            sections_html += section.render_html()
            if section.page_break_after:
                sections_html += '<div class="page-break"></div>'
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{self.title}</title>
    <style>
        body {{
            font-family: {style.font_family};
            font-size: {style.font_size}px;
            color: {style.text_color};
            background: {style.background_color};
            margin: {self.page_settings.margin_top}mm {self.page_settings.margin_right}mm {self.page_settings.margin_bottom}mm {self.page_settings.margin_left}mm;
            line-height: 1.6;
        }}
        h1 {{ font-size: {style.title_size}px; color: {style.primary_color}; }}
        h2 {{ font-size: {style.heading_size}px; color: {style.secondary_color}; }}
        .section {{ margin-bottom: 30px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th {{ background: {style.primary_color}; color: white; padding: 12px; text-align: left; }}
        td {{ padding: 10px; border-bottom: 1px solid #ddd; }}
        tr.odd {{ background: #f9f9f9; }}
        .metric-card {{
            background: #f5f5f5;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }}
        .metric-value {{ font-size: 32px; font-weight: bold; color: {style.primary_color}; }}
        .metric-label {{ color: {style.secondary_color}; margin-top: 8px; }}
        .page-break {{ page-break-after: always; }}
        @media print {{
            body {{ margin: 0; }}
            .page-break {{ page-break-after: always; }}
        }}
    </style>
</head>
<body>
    <h1>{self.title}</h1>
    {f'<p class="description">{self.description}</p>' if self.description else ''}
    {sections_html}
    <footer style="margin-top: 40px; text-align: center; color: #999;">
        Generated on {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}
        {f' by {self.author}' if self.author else ''}
    </footer>
</body>
</html>
        """
        
        return html.encode('utf-8')
    
    def _export_json(self) -> bytes:
        """Export as JSON."""
        data = {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "createdAt": self.created_at.isoformat(),
            "author": self.author,
            "sections": [s.render_data() for s in self.sections if s.visible],
            "metadata": self.metadata,
        }
        return json.dumps(data, indent=2, default=str).encode('utf-8')
    
    def _export_text(self) -> bytes:
        """Export as plain text."""
        lines = [
            self.title,
            "=" * len(self.title),
            "",
        ]
        
        if self.description:
            lines.append(self.description)
            lines.append("")
        
        for section in self.sections:
            if section.visible:
                lines.append(section.render_text())
        
        lines.extend([
            "",
            f"Generated: {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
        ])
        
        return "\n".join(lines).encode('utf-8')
    
    def _export_markdown(self) -> bytes:
        """Export as Markdown."""
        lines = [
            f"# {self.title}",
            "",
        ]
        
        if self.description:
            lines.append(f"*{self.description}*")
            lines.append("")
        
        for section in self.sections:
            if not section.visible:
                continue
            
            if section.title:
                lines.append(f"## {section.title}")
                lines.append("")
            
            if isinstance(section, TextSection):
                lines.append(section.content)
            elif isinstance(section, TableSection):
                # Table header
                headers = " | ".join(c.label for c in section.columns)
                separator = " | ".join("---" for _ in section.columns)
                lines.append(f"| {headers} |")
                lines.append(f"| {separator} |")
                
                # Table rows
                for row in section.data:
                    cells = " | ".join(str(row.get(c.key, "")) for c in section.columns)
                    lines.append(f"| {cells} |")
            elif isinstance(section, SummarySection):
                for metric in section.metrics:
                    lines.append(f"- **{metric['label']}**: {metric['value']}{metric.get('unit', '')}")
            
            lines.append("")
        
        lines.append(f"---\n*Generated: {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}*")
        
        return "\n".join(lines).encode('utf-8')
    
    def _export_csv(self) -> bytes:
        """Export tables as CSV."""
        lines = []
        
        for section in self.sections:
            if not section.visible or not isinstance(section, TableSection):
                continue
            
            if section.title:
                lines.append(f"# {section.title}")
            
            # Headers
            headers = ",".join(c.label for c in section.columns)
            lines.append(headers)
            
            # Data
            for row in section.data:
                values = ",".join(
                    f'"{str(row.get(c.key, ""))}"'
                    for c in section.columns
                )
                lines.append(values)
            
            lines.append("")
        
        return "\n".join(lines).encode('utf-8')


# Report builder
class ReportBuilder:
    """Fluent report builder."""
    
    def __init__(self):
        self._report: Optional[Report] = None
    
    def create(self, title: str) -> 'ReportBuilder':
        """Start new report."""
        self._report = Report(title=title)
        return self
    
    def description(self, text: str) -> 'ReportBuilder':
        """Set description."""
        if self._report:
            self._report.description = text
        return self
    
    def author(self, name: str) -> 'ReportBuilder':
        """Set author."""
        if self._report:
            self._report.author = name
        return self
    
    def page_size(self, size: str) -> 'ReportBuilder':
        """Set page size."""
        if self._report:
            self._report.page_settings.size = size
        return self
    
    def orientation(self, orientation: str) -> 'ReportBuilder':
        """Set orientation."""
        if self._report:
            self._report.page_settings.orientation = orientation
        return self
    
    def primary_color(self, color: str) -> 'ReportBuilder':
        """Set primary color."""
        if self._report:
            self._report.style_settings.primary_color = color
        return self
    
    def add_text(
        self,
        title: str,
        content: str,
        **kwargs,
    ) -> 'ReportBuilder':
        """Add text section."""
        if self._report:
            self._report.add_section(TextSection(title=title, content=content, **kwargs))
        return self
    
    def add_table(
        self,
        title: str,
        data: List[Dict[str, Any]],
        columns: Optional[List[str]] = None,
        **kwargs,
    ) -> 'ReportBuilder':
        """Add table section."""
        if self._report:
            section = TableSection(title=title, **kwargs)
            section.set_data(data, columns)
            self._report.add_section(section)
        return self
    
    def add_chart(
        self,
        title: str,
        chart_type: str,
        data: Dict[str, Any],
        **kwargs,
    ) -> 'ReportBuilder':
        """Add chart section."""
        if self._report:
            self._report.add_section(
                ChartSection(title=title, chart_type=chart_type, data=data, **kwargs)
            )
        return self
    
    def add_summary(
        self,
        title: str,
        metrics: List[Dict[str, Any]],
        **kwargs,
    ) -> 'ReportBuilder':
        """Add summary section."""
        if self._report:
            section = SummarySection(title=title, metrics=metrics, **kwargs)
            self._report.add_section(section)
        return self
    
    def add_page_break(self) -> 'ReportBuilder':
        """Add page break."""
        if self._report:
            self._report.add_section(Section(section_type=SectionType.PAGE_BREAK))
        return self
    
    def build(self) -> Report:
        """Build report."""
        if not self._report:
            raise ReportError("No report created")
        return self._report


# Factory functions
def create_report(title: str, **kwargs) -> Report:
    """Create report."""
    return Report(title=title, **kwargs)


def create_report_builder() -> ReportBuilder:
    """Create report builder."""
    return ReportBuilder()


def create_text_section(title: str, content: str, **kwargs) -> TextSection:
    """Create text section."""
    return TextSection(title=title, content=content, **kwargs)


def create_table_section(
    title: str,
    data: List[Dict[str, Any]],
    columns: Optional[List[str]] = None,
    **kwargs,
) -> TableSection:
    """Create table section."""
    section = TableSection(title=title, **kwargs)
    section.set_data(data, columns)
    return section


def create_summary_section(
    title: str,
    metrics: Optional[List[Dict[str, Any]]] = None,
    **kwargs,
) -> SummarySection:
    """Create summary section."""
    return SummarySection(title=title, metrics=metrics or [], **kwargs)


__all__ = [
    # Exceptions
    "ReportError",
    # Enums
    "ExportFormat",
    "SectionType",
    "Alignment",
    "AggregationType",
    # Data classes
    "PageSettings",
    "StyleSettings",
    "ColumnConfig",
    # Sections
    "Section",
    "TextSection",
    "TableSection",
    "ChartSection",
    "HeaderSection",
    "FooterSection",
    "SummarySection",
    # Report
    "Report",
    "ReportBuilder",
    # Factory functions
    "create_report",
    "create_report_builder",
    "create_text_section",
    "create_table_section",
    "create_summary_section",
]
