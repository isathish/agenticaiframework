"""
Enterprise Dashboard Generator Module.

Dynamic dashboards, widgets, charts,
and real-time data visualization.

Example:
    # Create dashboard
    dashboard = create_dashboard("System Overview")
    
    # Add widgets
    dashboard.add_widget(
        MetricWidget("CPU Usage", metric="cpu_percent", type=WidgetType.GAUGE)
    )
    dashboard.add_widget(
        ChartWidget("Request Rate", query="requests_total", type=ChartType.LINE)
    )
    dashboard.add_widget(
        TableWidget("Top Endpoints", data=endpoint_stats)
    )
    
    # Render dashboard
    html = dashboard.render_html()
    json_data = dashboard.render_json()
"""

from __future__ import annotations

import json
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
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


class DashboardError(Exception):
    """Dashboard error."""
    pass


class WidgetType(str, Enum):
    """Widget types."""
    METRIC = "metric"
    GAUGE = "gauge"
    COUNTER = "counter"
    SPARKLINE = "sparkline"
    CHART = "chart"
    TABLE = "table"
    TEXT = "text"
    HTML = "html"
    STATUS = "status"
    LIST = "list"
    MAP = "map"
    HEATMAP = "heatmap"


class ChartType(str, Enum):
    """Chart types."""
    LINE = "line"
    BAR = "bar"
    AREA = "area"
    PIE = "pie"
    DONUT = "donut"
    SCATTER = "scatter"
    HISTOGRAM = "histogram"


class RefreshRate(int, Enum):
    """Refresh rates in seconds."""
    REALTIME = 5
    FAST = 15
    NORMAL = 30
    SLOW = 60
    MANUAL = 0


class ColorScheme(str, Enum):
    """Color schemes."""
    DEFAULT = "default"
    DARK = "dark"
    LIGHT = "light"
    COLORFUL = "colorful"
    MONOCHROME = "monochrome"


@dataclass
class DataSource:
    """Data source configuration."""
    name: str
    type: str = "metrics"
    query: str = ""
    refresh_seconds: int = 30
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Threshold:
    """Value threshold."""
    value: float
    color: str = "red"
    label: str = ""


@dataclass
class WidgetPosition:
    """Widget position in grid."""
    row: int = 0
    col: int = 0
    width: int = 4
    height: int = 2


@dataclass
class WidgetStyle:
    """Widget styling."""
    background: str = "#ffffff"
    text_color: str = "#333333"
    border_color: str = "#e0e0e0"
    font_size: str = "14px"
    padding: str = "10px"


# Base widget
@dataclass
class Widget:
    """Base widget."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    widget_type: WidgetType = WidgetType.TEXT
    position: WidgetPosition = field(default_factory=WidgetPosition)
    style: WidgetStyle = field(default_factory=WidgetStyle)
    data_source: Optional[DataSource] = None
    thresholds: List[Threshold] = field(default_factory=list)
    visible: bool = True
    description: str = ""
    
    def render(self) -> Dict[str, Any]:
        """Render widget data."""
        return {
            "id": self.id,
            "title": self.title,
            "type": self.widget_type.value,
            "position": {
                "row": self.position.row,
                "col": self.position.col,
                "width": self.position.width,
                "height": self.position.height,
            },
            "style": {
                "background": self.style.background,
                "textColor": self.style.text_color,
                "borderColor": self.style.border_color,
            },
        }


@dataclass
class MetricWidget(Widget):
    """Metric display widget."""
    metric: str = ""
    value: Any = None
    unit: str = ""
    format: str = "{value}"
    trend: Optional[str] = None
    sparkline_data: List[float] = field(default_factory=list)
    
    def __post_init__(self):
        self.widget_type = WidgetType.METRIC
    
    def set_value(self, value: Any) -> None:
        """Set metric value."""
        self.value = value
        if self.sparkline_data:
            self.sparkline_data.append(float(value))
            self.sparkline_data = self.sparkline_data[-50:]  # Keep last 50
    
    def render(self) -> Dict[str, Any]:
        data = super().render()
        data.update({
            "metric": self.metric,
            "value": self.value,
            "unit": self.unit,
            "format": self.format,
            "trend": self.trend,
            "sparkline": self.sparkline_data,
        })
        return data


@dataclass
class GaugeWidget(Widget):
    """Gauge widget."""
    value: float = 0
    min_value: float = 0
    max_value: float = 100
    unit: str = "%"
    
    def __post_init__(self):
        self.widget_type = WidgetType.GAUGE
    
    def set_value(self, value: float) -> None:
        """Set gauge value."""
        self.value = max(self.min_value, min(self.max_value, value))
    
    def get_color(self) -> str:
        """Get color based on thresholds."""
        for threshold in sorted(self.thresholds, key=lambda t: t.value, reverse=True):
            if self.value >= threshold.value:
                return threshold.color
        return "#4caf50"  # Green
    
    def render(self) -> Dict[str, Any]:
        data = super().render()
        data.update({
            "value": self.value,
            "minValue": self.min_value,
            "maxValue": self.max_value,
            "unit": self.unit,
            "color": self.get_color(),
            "percentage": (self.value - self.min_value) / (self.max_value - self.min_value) * 100,
        })
        return data


@dataclass
class ChartWidget(Widget):
    """Chart widget."""
    chart_type: ChartType = ChartType.LINE
    series: List[Dict[str, Any]] = field(default_factory=list)
    labels: List[str] = field(default_factory=list)
    x_axis_label: str = ""
    y_axis_label: str = ""
    show_legend: bool = True
    stacked: bool = False
    
    def __post_init__(self):
        self.widget_type = WidgetType.CHART
    
    def add_series(
        self,
        name: str,
        data: List[float],
        color: Optional[str] = None,
    ) -> None:
        """Add data series."""
        self.series.append({
            "name": name,
            "data": data,
            "color": color,
        })
    
    def set_labels(self, labels: List[str]) -> None:
        """Set axis labels."""
        self.labels = labels
    
    def render(self) -> Dict[str, Any]:
        data = super().render()
        data.update({
            "chartType": self.chart_type.value,
            "series": self.series,
            "labels": self.labels,
            "xAxisLabel": self.x_axis_label,
            "yAxisLabel": self.y_axis_label,
            "showLegend": self.show_legend,
            "stacked": self.stacked,
        })
        return data


@dataclass
class TableWidget(Widget):
    """Table widget."""
    columns: List[Dict[str, str]] = field(default_factory=list)
    rows: List[Dict[str, Any]] = field(default_factory=list)
    sortable: bool = True
    paginated: bool = True
    page_size: int = 10
    
    def __post_init__(self):
        self.widget_type = WidgetType.TABLE
    
    def set_columns(self, columns: List[str]) -> None:
        """Set column definitions."""
        self.columns = [{"key": c, "label": c.title()} for c in columns]
    
    def set_data(self, data: List[Dict[str, Any]]) -> None:
        """Set table data."""
        self.rows = data
    
    def render(self) -> Dict[str, Any]:
        data = super().render()
        data.update({
            "columns": self.columns,
            "rows": self.rows,
            "sortable": self.sortable,
            "paginated": self.paginated,
            "pageSize": self.page_size,
        })
        return data


@dataclass
class StatusWidget(Widget):
    """Status indicator widget."""
    status: str = "unknown"
    message: str = ""
    last_updated: Optional[datetime] = None
    
    STATUS_COLORS = {
        "healthy": "#4caf50",
        "warning": "#ff9800",
        "error": "#f44336",
        "unknown": "#9e9e9e",
    }
    
    def __post_init__(self):
        self.widget_type = WidgetType.STATUS
    
    def set_status(
        self,
        status: str,
        message: str = "",
    ) -> None:
        """Set status."""
        self.status = status
        self.message = message
        self.last_updated = datetime.utcnow()
    
    def render(self) -> Dict[str, Any]:
        data = super().render()
        data.update({
            "status": self.status,
            "message": self.message,
            "color": self.STATUS_COLORS.get(self.status, "#9e9e9e"),
            "lastUpdated": self.last_updated.isoformat() if self.last_updated else None,
        })
        return data


@dataclass
class TextWidget(Widget):
    """Text/markdown widget."""
    content: str = ""
    format: str = "text"  # text, markdown, html
    
    def __post_init__(self):
        self.widget_type = WidgetType.TEXT
    
    def render(self) -> Dict[str, Any]:
        data = super().render()
        data.update({
            "content": self.content,
            "format": self.format,
        })
        return data


@dataclass
class ListWidget(Widget):
    """List widget."""
    items: List[Dict[str, Any]] = field(default_factory=list)
    item_template: str = "{label}: {value}"
    max_items: int = 10
    
    def __post_init__(self):
        self.widget_type = WidgetType.LIST
    
    def add_item(
        self,
        label: str,
        value: Any,
        color: Optional[str] = None,
        icon: Optional[str] = None,
    ) -> None:
        """Add list item."""
        self.items.append({
            "label": label,
            "value": value,
            "color": color,
            "icon": icon,
        })
        self.items = self.items[-self.max_items:]
    
    def render(self) -> Dict[str, Any]:
        data = super().render()
        data.update({
            "items": self.items,
            "itemTemplate": self.item_template,
        })
        return data


# Dashboard
@dataclass
class Dashboard:
    """Dashboard container."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    widgets: List[Widget] = field(default_factory=list)
    refresh_rate: RefreshRate = RefreshRate.NORMAL
    color_scheme: ColorScheme = ColorScheme.DEFAULT
    grid_columns: int = 12
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    tags: List[str] = field(default_factory=list)
    variables: Dict[str, Any] = field(default_factory=dict)
    
    def add_widget(self, widget: Widget) -> None:
        """Add widget to dashboard."""
        self.widgets.append(widget)
        self.updated_at = datetime.utcnow()
    
    def remove_widget(self, widget_id: str) -> bool:
        """Remove widget."""
        for i, widget in enumerate(self.widgets):
            if widget.id == widget_id:
                self.widgets.pop(i)
                self.updated_at = datetime.utcnow()
                return True
        return False
    
    def get_widget(self, widget_id: str) -> Optional[Widget]:
        """Get widget by ID."""
        for widget in self.widgets:
            if widget.id == widget_id:
                return widget
        return None
    
    def render_json(self) -> Dict[str, Any]:
        """Render dashboard as JSON."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "widgets": [w.render() for w in self.widgets if w.visible],
            "refreshRate": self.refresh_rate.value,
            "colorScheme": self.color_scheme.value,
            "gridColumns": self.grid_columns,
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
            "tags": self.tags,
            "variables": self.variables,
        }
    
    def render_html(self) -> str:
        """Render dashboard as HTML."""
        widgets_html = ""
        
        for widget in self.widgets:
            if not widget.visible:
                continue
            
            pos = widget.position
            style = f"""
                grid-column: {pos.col + 1} / span {pos.width};
                grid-row: {pos.row + 1} / span {pos.height};
                background: {widget.style.background};
                color: {widget.style.text_color};
                border: 1px solid {widget.style.border_color};
                padding: {widget.style.padding};
                border-radius: 4px;
            """
            
            content = self._render_widget_content(widget)
            
            widgets_html += f"""
                <div class="widget widget-{widget.widget_type.value}" 
                     id="widget-{widget.id}" style="{style}">
                    <div class="widget-title">{widget.title}</div>
                    <div class="widget-content">{content}</div>
                </div>
            """
        
        return f"""
<!DOCTYPE html>
<html>
<head>
    <title>{self.name}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background: {'#1a1a2e' if self.color_scheme == ColorScheme.DARK else '#f5f5f5'};
            color: {'#ffffff' if self.color_scheme == ColorScheme.DARK else '#333333'};
        }}
        .dashboard-title {{
            font-size: 24px;
            font-weight: bold;
            margin-bottom: 20px;
        }}
        .dashboard-grid {{
            display: grid;
            grid-template-columns: repeat({self.grid_columns}, 1fr);
            gap: 10px;
            auto-rows: minmax(100px, auto);
        }}
        .widget {{
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .widget-title {{
            font-weight: bold;
            margin-bottom: 10px;
            font-size: 14px;
            opacity: 0.8;
        }}
        .widget-content {{
            font-size: 24px;
        }}
        .gauge-value {{
            font-size: 36px;
            font-weight: bold;
        }}
        .status-indicator {{
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }}
        th, td {{
            text-align: left;
            padding: 8px;
            border-bottom: 1px solid #ddd;
        }}
    </style>
</head>
<body>
    <div class="dashboard-title">{self.name}</div>
    <div class="dashboard-grid">
        {widgets_html}
    </div>
    <script>
        // Auto-refresh
        {f'setInterval(() => location.reload(), {self.refresh_rate.value * 1000});' if self.refresh_rate != RefreshRate.MANUAL else ''}
    </script>
</body>
</html>
        """
    
    def _render_widget_content(self, widget: Widget) -> str:
        """Render widget content HTML."""
        if isinstance(widget, MetricWidget):
            return f'<div class="metric-value">{widget.value} {widget.unit}</div>'
        
        elif isinstance(widget, GaugeWidget):
            return f'''
                <div class="gauge-value" style="color: {widget.get_color()}">
                    {widget.value:.1f}{widget.unit}
                </div>
                <div class="gauge-bar" style="
                    width: 100%; 
                    height: 8px; 
                    background: #e0e0e0; 
                    border-radius: 4px;
                ">
                    <div style="
                        width: {(widget.value - widget.min_value) / (widget.max_value - widget.min_value) * 100}%;
                        height: 100%;
                        background: {widget.get_color()};
                        border-radius: 4px;
                    "></div>
                </div>
            '''
        
        elif isinstance(widget, StatusWidget):
            return f'''
                <div>
                    <span class="status-indicator" 
                          style="background: {widget.STATUS_COLORS.get(widget.status, '#9e9e9e')}">
                    </span>
                    {widget.status.upper()}
                </div>
                <div style="font-size: 14px; opacity: 0.8;">{widget.message}</div>
            '''
        
        elif isinstance(widget, TableWidget):
            headers = "".join(f"<th>{c.get('label', c['key'])}</th>" for c in widget.columns)
            rows = ""
            for row in widget.rows[:widget.page_size]:
                cells = "".join(f"<td>{row.get(c['key'], '')}</td>" for c in widget.columns)
                rows += f"<tr>{cells}</tr>"
            return f"<table><thead><tr>{headers}</tr></thead><tbody>{rows}</tbody></table>"
        
        elif isinstance(widget, TextWidget):
            return f'<div style="font-size: 14px;">{widget.content}</div>'
        
        elif isinstance(widget, ListWidget):
            items = "".join(
                f'<li>{item.get("label")}: {item.get("value")}</li>'
                for item in widget.items
            )
            return f'<ul style="margin: 0; padding-left: 20px;">{items}</ul>'
        
        return ""


# Dashboard manager
class DashboardManager:
    """Dashboard management service."""
    
    def __init__(self):
        self._dashboards: Dict[str, Dashboard] = {}
    
    def create(
        self,
        name: str,
        description: str = "",
        **kwargs,
    ) -> Dashboard:
        """Create dashboard."""
        dashboard = Dashboard(
            name=name,
            description=description,
            **kwargs,
        )
        self._dashboards[dashboard.id] = dashboard
        return dashboard
    
    def get(self, dashboard_id: str) -> Optional[Dashboard]:
        """Get dashboard."""
        return self._dashboards.get(dashboard_id)
    
    def list(self) -> List[Dashboard]:
        """List all dashboards."""
        return list(self._dashboards.values())
    
    def delete(self, dashboard_id: str) -> bool:
        """Delete dashboard."""
        if dashboard_id in self._dashboards:
            del self._dashboards[dashboard_id]
            return True
        return False
    
    def clone(self, dashboard_id: str, new_name: str) -> Optional[Dashboard]:
        """Clone dashboard."""
        original = self.get(dashboard_id)
        if not original:
            return None
        
        clone = Dashboard(
            name=new_name,
            description=original.description,
            widgets=[w for w in original.widgets],
            refresh_rate=original.refresh_rate,
            color_scheme=original.color_scheme,
            grid_columns=original.grid_columns,
            tags=original.tags.copy(),
            variables=original.variables.copy(),
        )
        
        self._dashboards[clone.id] = clone
        return clone


# Factory functions
def create_dashboard(
    name: str,
    description: str = "",
    **kwargs,
) -> Dashboard:
    """Create dashboard."""
    return Dashboard(name=name, description=description, **kwargs)


def create_metric_widget(
    title: str,
    metric: str,
    **kwargs,
) -> MetricWidget:
    """Create metric widget."""
    return MetricWidget(title=title, metric=metric, **kwargs)


def create_gauge_widget(
    title: str,
    value: float = 0,
    max_value: float = 100,
    **kwargs,
) -> GaugeWidget:
    """Create gauge widget."""
    return GaugeWidget(title=title, value=value, max_value=max_value, **kwargs)


def create_chart_widget(
    title: str,
    chart_type: ChartType = ChartType.LINE,
    **kwargs,
) -> ChartWidget:
    """Create chart widget."""
    return ChartWidget(title=title, chart_type=chart_type, **kwargs)


def create_table_widget(
    title: str,
    columns: List[str],
    **kwargs,
) -> TableWidget:
    """Create table widget."""
    widget = TableWidget(title=title, **kwargs)
    widget.set_columns(columns)
    return widget


def create_status_widget(
    title: str,
    status: str = "unknown",
    **kwargs,
) -> StatusWidget:
    """Create status widget."""
    widget = StatusWidget(title=title, **kwargs)
    widget.set_status(status)
    return widget


def create_dashboard_manager() -> DashboardManager:
    """Create dashboard manager."""
    return DashboardManager()


__all__ = [
    # Exceptions
    "DashboardError",
    # Enums
    "WidgetType",
    "ChartType",
    "RefreshRate",
    "ColorScheme",
    # Data classes
    "DataSource",
    "Threshold",
    "WidgetPosition",
    "WidgetStyle",
    # Widgets
    "Widget",
    "MetricWidget",
    "GaugeWidget",
    "ChartWidget",
    "TableWidget",
    "StatusWidget",
    "TextWidget",
    "ListWidget",
    # Dashboard
    "Dashboard",
    "DashboardManager",
    # Factory functions
    "create_dashboard",
    "create_metric_widget",
    "create_gauge_widget",
    "create_chart_widget",
    "create_table_widget",
    "create_status_widget",
    "create_dashboard_manager",
]
