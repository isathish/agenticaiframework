"""
Enterprise Excel Export Service Module.

Provides Excel workbook generation with worksheets,
formulas, charts, styling, and data validation.

Example:
    # Create Excel service
    excel = create_excel_service()
    
    # Build workbook with fluent API
    workbook = (
        excel.create_workbook("Sales Report")
        .add_sheet("Summary")
        .set_cell("A1", "Total Sales")
        .set_cell("B1", 125000, style="currency")
        .add_chart("A5", chart_type="bar", data_range="A1:B10")
        .add_sheet("Details")
        .write_data(data_rows, headers=["Date", "Product", "Amount"])
        .build()
    )
    
    # Export
    content = await excel.export(workbook)
"""

from __future__ import annotations

import asyncio
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
    Iterator,
    List,
    Optional,
    Tuple,
    TypeVar,
    Union,
)

T = TypeVar('T')


logger = logging.getLogger(__name__)


class ExcelError(Exception):
    """Excel error."""
    pass


class ChartType(str, Enum):
    """Excel chart types."""
    BAR = "bar"
    COLUMN = "column"
    LINE = "line"
    PIE = "pie"
    AREA = "area"
    SCATTER = "scatter"
    DOUGHNUT = "doughnut"


class BorderStyle(str, Enum):
    """Cell border styles."""
    NONE = "none"
    THIN = "thin"
    MEDIUM = "medium"
    THICK = "thick"
    DASHED = "dashed"
    DOTTED = "dotted"
    DOUBLE = "double"


class HorizontalAlignment(str, Enum):
    """Horizontal alignment."""
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"
    JUSTIFY = "justify"


class VerticalAlignment(str, Enum):
    """Vertical alignment."""
    TOP = "top"
    CENTER = "center"
    BOTTOM = "bottom"


class NumberFormat(str, Enum):
    """Number formats."""
    GENERAL = "General"
    NUMBER = "0.00"
    INTEGER = "0"
    CURRENCY = "$#,##0.00"
    PERCENT = "0.00%"
    DATE = "YYYY-MM-DD"
    DATETIME = "YYYY-MM-DD HH:MM:SS"
    TEXT = "@"


@dataclass
class CellStyle:
    """Cell styling."""
    font_name: str = "Calibri"
    font_size: int = 11
    font_color: str = "#000000"
    bold: bool = False
    italic: bool = False
    underline: bool = False
    bg_color: Optional[str] = None
    number_format: str = "General"
    h_align: HorizontalAlignment = HorizontalAlignment.LEFT
    v_align: VerticalAlignment = VerticalAlignment.CENTER
    wrap_text: bool = False
    border: BorderStyle = BorderStyle.NONE
    border_color: str = "#000000"


@dataclass
class CellValue:
    """Cell with value and style."""
    value: Any = None
    formula: Optional[str] = None
    style: Optional[CellStyle] = None
    hyperlink: Optional[str] = None
    comment: Optional[str] = None


@dataclass
class ColumnConfig:
    """Column configuration."""
    width: int = 10
    hidden: bool = False
    style: Optional[CellStyle] = None


@dataclass
class RowConfig:
    """Row configuration."""
    height: int = 15
    hidden: bool = False
    style: Optional[CellStyle] = None


@dataclass
class ChartConfig:
    """Chart configuration."""
    type: ChartType = ChartType.BAR
    title: str = ""
    x_title: str = ""
    y_title: str = ""
    data_range: str = ""
    category_range: str = ""
    width: int = 400
    height: int = 300
    legend: bool = True
    position: str = "A1"


@dataclass
class DataValidation:
    """Data validation rule."""
    type: str = "list"  # list, whole, decimal, date, time, textLength
    formula: str = ""
    allow_blank: bool = True
    show_input: bool = True
    input_title: str = ""
    input_message: str = ""
    show_error: bool = True
    error_title: str = ""
    error_message: str = ""


@dataclass
class ConditionalFormat:
    """Conditional formatting rule."""
    type: str = "cellIs"  # cellIs, colorScale, dataBar, iconSet
    operator: str = "greaterThan"
    formula: str = ""
    format: Optional[CellStyle] = None
    priority: int = 1


@dataclass
class Worksheet:
    """Excel worksheet."""
    name: str
    cells: Dict[str, CellValue] = field(default_factory=dict)
    columns: Dict[str, ColumnConfig] = field(default_factory=dict)
    rows: Dict[int, RowConfig] = field(default_factory=dict)
    charts: List[ChartConfig] = field(default_factory=list)
    validations: Dict[str, DataValidation] = field(default_factory=dict)
    conditionals: List[Tuple[str, ConditionalFormat]] = field(default_factory=list)
    merged_cells: List[str] = field(default_factory=list)
    frozen_panes: Optional[str] = None
    auto_filter: Optional[str] = None
    print_area: Optional[str] = None
    protection: bool = False
    password: Optional[str] = None


@dataclass
class Workbook:
    """Excel workbook."""
    title: str = "Workbook"
    sheets: List[Worksheet] = field(default_factory=list)
    properties: Dict[str, str] = field(default_factory=dict)
    named_ranges: Dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


# Style presets
STYLE_PRESETS: Dict[str, CellStyle] = {
    "header": CellStyle(
        bold=True,
        bg_color="#4472C4",
        font_color="#FFFFFF",
        h_align=HorizontalAlignment.CENTER,
        border=BorderStyle.THIN,
    ),
    "title": CellStyle(
        bold=True,
        font_size=16,
        h_align=HorizontalAlignment.CENTER,
    ),
    "currency": CellStyle(
        number_format=NumberFormat.CURRENCY.value,
        h_align=HorizontalAlignment.RIGHT,
    ),
    "percent": CellStyle(
        number_format=NumberFormat.PERCENT.value,
        h_align=HorizontalAlignment.RIGHT,
    ),
    "date": CellStyle(
        number_format=NumberFormat.DATE.value,
    ),
    "number": CellStyle(
        number_format=NumberFormat.NUMBER.value,
        h_align=HorizontalAlignment.RIGHT,
    ),
    "total": CellStyle(
        bold=True,
        bg_color="#E2EFDA",
        border=BorderStyle.MEDIUM,
    ),
    "warning": CellStyle(
        bg_color="#FFEB9C",
        font_color="#9C5700",
    ),
    "error": CellStyle(
        bg_color="#FFC7CE",
        font_color="#9C0006",
    ),
    "success": CellStyle(
        bg_color="#C6EFCE",
        font_color="#006100",
    ),
}


class WorkbookBuilder:
    """Fluent workbook builder."""
    
    def __init__(self, title: str = "Workbook"):
        self._workbook = Workbook(title=title)
        self._current_sheet: Optional[Worksheet] = None
        self._current_row = 1
    
    def set_property(self, name: str, value: str) -> "WorkbookBuilder":
        """Set workbook property."""
        self._workbook.properties[name] = value
        return self
    
    def add_sheet(self, name: str) -> "WorkbookBuilder":
        """Add worksheet."""
        sheet = Worksheet(name=name)
        self._workbook.sheets.append(sheet)
        self._current_sheet = sheet
        self._current_row = 1
        return self
    
    def set_cell(
        self,
        cell: str,
        value: Any,
        style: Optional[Union[str, CellStyle]] = None,
        formula: Optional[str] = None,
        hyperlink: Optional[str] = None,
        comment: Optional[str] = None,
    ) -> "WorkbookBuilder":
        """Set cell value."""
        if not self._current_sheet:
            self.add_sheet("Sheet1")
        
        cell_style = None
        if isinstance(style, str) and style in STYLE_PRESETS:
            cell_style = STYLE_PRESETS[style]
        elif isinstance(style, CellStyle):
            cell_style = style
        
        self._current_sheet.cells[cell] = CellValue(
            value=value,
            formula=formula,
            style=cell_style,
            hyperlink=hyperlink,
            comment=comment,
        )
        
        return self
    
    def set_formula(
        self,
        cell: str,
        formula: str,
        style: Optional[Union[str, CellStyle]] = None,
    ) -> "WorkbookBuilder":
        """Set cell formula."""
        return self.set_cell(cell, None, style, formula=formula)
    
    def write_row(
        self,
        data: List[Any],
        row: Optional[int] = None,
        start_col: str = "A",
        style: Optional[Union[str, CellStyle]] = None,
    ) -> "WorkbookBuilder":
        """Write data row."""
        if not self._current_sheet:
            self.add_sheet("Sheet1")
        
        target_row = row or self._current_row
        col_num = ord(start_col.upper()) - ord('A')
        
        for i, value in enumerate(data):
            col = chr(ord('A') + col_num + i)
            cell = f"{col}{target_row}"
            self.set_cell(cell, value, style)
        
        if row is None:
            self._current_row += 1
        
        return self
    
    def write_data(
        self,
        data: List[List[Any]],
        headers: Optional[List[str]] = None,
        start_cell: str = "A1",
        header_style: str = "header",
    ) -> "WorkbookBuilder":
        """Write data with optional headers."""
        if not self._current_sheet:
            self.add_sheet("Sheet1")
        
        col = start_cell[0]
        row = int(start_cell[1:])
        
        if headers:
            self.write_row(headers, row, col, header_style)
            row += 1
        
        for data_row in data:
            self.write_row(data_row, row, col)
            row += 1
        
        self._current_row = row
        
        return self
    
    def set_column_width(
        self,
        column: str,
        width: int,
    ) -> "WorkbookBuilder":
        """Set column width."""
        if not self._current_sheet:
            self.add_sheet("Sheet1")
        
        self._current_sheet.columns[column] = ColumnConfig(width=width)
        return self
    
    def set_row_height(
        self,
        row: int,
        height: int,
    ) -> "WorkbookBuilder":
        """Set row height."""
        if not self._current_sheet:
            self.add_sheet("Sheet1")
        
        self._current_sheet.rows[row] = RowConfig(height=height)
        return self
    
    def merge_cells(self, cell_range: str) -> "WorkbookBuilder":
        """Merge cells."""
        if not self._current_sheet:
            self.add_sheet("Sheet1")
        
        self._current_sheet.merged_cells.append(cell_range)
        return self
    
    def freeze_panes(self, cell: str) -> "WorkbookBuilder":
        """Freeze panes at cell."""
        if not self._current_sheet:
            self.add_sheet("Sheet1")
        
        self._current_sheet.frozen_panes = cell
        return self
    
    def add_auto_filter(self, cell_range: str) -> "WorkbookBuilder":
        """Add auto filter."""
        if not self._current_sheet:
            self.add_sheet("Sheet1")
        
        self._current_sheet.auto_filter = cell_range
        return self
    
    def add_chart(
        self,
        position: str,
        chart_type: ChartType = ChartType.BAR,
        data_range: str = "",
        title: str = "",
        **kwargs,
    ) -> "WorkbookBuilder":
        """Add chart."""
        if not self._current_sheet:
            self.add_sheet("Sheet1")
        
        chart = ChartConfig(
            type=chart_type,
            position=position,
            data_range=data_range,
            title=title,
            **kwargs,
        )
        
        self._current_sheet.charts.append(chart)
        return self
    
    def add_validation(
        self,
        cell_range: str,
        validation_type: str = "list",
        formula: str = "",
        **kwargs,
    ) -> "WorkbookBuilder":
        """Add data validation."""
        if not self._current_sheet:
            self.add_sheet("Sheet1")
        
        validation = DataValidation(
            type=validation_type,
            formula=formula,
            **kwargs,
        )
        
        self._current_sheet.validations[cell_range] = validation
        return self
    
    def add_conditional_format(
        self,
        cell_range: str,
        format_type: str = "cellIs",
        operator: str = "greaterThan",
        formula: str = "",
        format: Optional[CellStyle] = None,
    ) -> "WorkbookBuilder":
        """Add conditional formatting."""
        if not self._current_sheet:
            self.add_sheet("Sheet1")
        
        cf = ConditionalFormat(
            type=format_type,
            operator=operator,
            formula=formula,
            format=format,
        )
        
        self._current_sheet.conditionals.append((cell_range, cf))
        return self
    
    def protect_sheet(
        self,
        password: Optional[str] = None,
    ) -> "WorkbookBuilder":
        """Protect current sheet."""
        if not self._current_sheet:
            self.add_sheet("Sheet1")
        
        self._current_sheet.protection = True
        self._current_sheet.password = password
        return self
    
    def add_named_range(
        self,
        name: str,
        reference: str,
    ) -> "WorkbookBuilder":
        """Add named range."""
        self._workbook.named_ranges[name] = reference
        return self
    
    def build(self) -> Workbook:
        """Build workbook."""
        return self._workbook


# Renderer
class ExcelRenderer(ABC):
    """Abstract Excel renderer."""
    
    @abstractmethod
    async def render(self, workbook: Workbook) -> bytes:
        """Render workbook to bytes."""
        pass


class MockExcelRenderer(ExcelRenderer):
    """Mock Excel renderer (returns JSON representation)."""
    
    async def render(self, workbook: Workbook) -> bytes:
        """Render workbook to JSON bytes."""
        output = {
            "title": workbook.title,
            "properties": workbook.properties,
            "named_ranges": workbook.named_ranges,
            "sheets": [],
        }
        
        for sheet in workbook.sheets:
            sheet_data = {
                "name": sheet.name,
                "cells": {},
                "charts": len(sheet.charts),
                "merged_cells": sheet.merged_cells,
                "frozen_panes": sheet.frozen_panes,
                "auto_filter": sheet.auto_filter,
            }
            
            for cell, cell_value in sheet.cells.items():
                sheet_data["cells"][cell] = {
                    "value": cell_value.value,
                    "formula": cell_value.formula,
                    "hyperlink": cell_value.hyperlink,
                }
            
            output["sheets"].append(sheet_data)
        
        return json.dumps(output, indent=2, default=str).encode()


class ExcelService:
    """
    Excel generation service.
    """
    
    def __init__(
        self,
        renderer: Optional[ExcelRenderer] = None,
    ):
        self._renderer = renderer or MockExcelRenderer()
        self._templates: Dict[str, Callable[..., WorkbookBuilder]] = {}
    
    def create_workbook(self, title: str = "Workbook") -> WorkbookBuilder:
        """Create workbook builder."""
        return WorkbookBuilder(title)
    
    def register_template(
        self,
        name: str,
        template_fn: Callable[..., WorkbookBuilder],
    ) -> None:
        """Register workbook template."""
        self._templates[name] = template_fn
    
    def template(self, name: str) -> Callable:
        """Decorator to register template."""
        def decorator(func: Callable[..., WorkbookBuilder]) -> Callable:
            self._templates[name] = func
            return func
        return decorator
    
    def from_template(
        self,
        name: str,
        **kwargs,
    ) -> WorkbookBuilder:
        """Create workbook from template."""
        template_fn = self._templates.get(name)
        if not template_fn:
            raise ExcelError(f"Template not found: {name}")
        
        return template_fn(**kwargs)
    
    async def export(
        self,
        workbook: Union[Workbook, WorkbookBuilder],
    ) -> bytes:
        """Export workbook to bytes."""
        if isinstance(workbook, WorkbookBuilder):
            workbook = workbook.build()
        
        return await self._renderer.render(workbook)
    
    async def save(
        self,
        workbook: Union[Workbook, WorkbookBuilder],
        path: Union[str, Path],
    ) -> Path:
        """Save workbook to file."""
        content = await self.export(workbook)
        
        path = Path(path)
        path.write_bytes(content)
        
        return path
    
    def from_data(
        self,
        data: List[Dict[str, Any]],
        title: str = "Data Export",
        sheet_name: str = "Data",
    ) -> WorkbookBuilder:
        """Create workbook from data list."""
        builder = self.create_workbook(title)
        builder.add_sheet(sheet_name)
        
        if data:
            headers = list(data[0].keys())
            rows = [[row.get(h) for h in headers] for row in data]
            builder.write_data(rows, headers=headers)
        
        return builder
    
    def from_dataframe(
        self,
        df: Any,  # pandas DataFrame
        title: str = "Data Export",
        sheet_name: str = "Data",
    ) -> WorkbookBuilder:
        """Create workbook from pandas DataFrame."""
        builder = self.create_workbook(title)
        builder.add_sheet(sheet_name)
        
        # Get headers from columns
        headers = list(df.columns)
        
        # Get rows from values
        rows = df.values.tolist()
        
        builder.write_data(rows, headers=headers)
        
        return builder


# Decorators
def excel_template(
    name: str,
    service: Optional[ExcelService] = None,
) -> Callable:
    """Decorator to define Excel template."""
    def decorator(func: Callable[..., WorkbookBuilder]) -> Callable:
        if service:
            service.register_template(name, func)
        func._template_name = name
        return func
    return decorator


def excel_export(
    filename: Optional[str] = None,
) -> Callable:
    """Decorator for Excel export endpoint."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            
            if isinstance(result, (Workbook, WorkbookBuilder)):
                service = ExcelService()
                content = await service.export(result)
                return {
                    "content": content,
                    "filename": filename or "export.xlsx",
                    "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                }
            
            return result
        
        return wrapper
    return decorator


# Factory functions
def create_excel_service(
    renderer: Optional[ExcelRenderer] = None,
) -> ExcelService:
    """Create Excel service."""
    return ExcelService(renderer)


def create_workbook_builder(title: str = "Workbook") -> WorkbookBuilder:
    """Create workbook builder."""
    return WorkbookBuilder(title)


def create_cell_style(
    preset: Optional[str] = None,
    **kwargs,
) -> CellStyle:
    """Create cell style."""
    if preset and preset in STYLE_PRESETS:
        base = STYLE_PRESETS[preset]
        return CellStyle(
            font_name=kwargs.get("font_name", base.font_name),
            font_size=kwargs.get("font_size", base.font_size),
            font_color=kwargs.get("font_color", base.font_color),
            bold=kwargs.get("bold", base.bold),
            italic=kwargs.get("italic", base.italic),
            underline=kwargs.get("underline", base.underline),
            bg_color=kwargs.get("bg_color", base.bg_color),
            number_format=kwargs.get("number_format", base.number_format),
            h_align=kwargs.get("h_align", base.h_align),
            v_align=kwargs.get("v_align", base.v_align),
            wrap_text=kwargs.get("wrap_text", base.wrap_text),
            border=kwargs.get("border", base.border),
            border_color=kwargs.get("border_color", base.border_color),
        )
    
    return CellStyle(**kwargs)


def create_chart_config(
    chart_type: ChartType = ChartType.BAR,
    data_range: str = "",
    **kwargs,
) -> ChartConfig:
    """Create chart configuration."""
    return ChartConfig(type=chart_type, data_range=data_range, **kwargs)


__all__ = [
    # Exceptions
    "ExcelError",
    # Enums
    "ChartType",
    "BorderStyle",
    "HorizontalAlignment",
    "VerticalAlignment",
    "NumberFormat",
    # Data classes
    "CellStyle",
    "CellValue",
    "ColumnConfig",
    "RowConfig",
    "ChartConfig",
    "DataValidation",
    "ConditionalFormat",
    "Worksheet",
    "Workbook",
    # Builder
    "WorkbookBuilder",
    # Renderer
    "ExcelRenderer",
    "MockExcelRenderer",
    # Service
    "ExcelService",
    # Style presets
    "STYLE_PRESETS",
    # Decorators
    "excel_template",
    "excel_export",
    # Factory functions
    "create_excel_service",
    "create_workbook_builder",
    "create_cell_style",
    "create_chart_config",
]
