"""
Enterprise QR Code Generator Module.

Provides QR code generation with styling,
logos, multiple formats, and customization.

Example:
    # Create QR generator
    qr = create_qr_generator()
    
    # Generate simple QR
    image = await qr.generate("https://example.com")
    
    # Generate styled QR with logo
    image = await qr.generate(
        "https://example.com",
        style=QRStyle(
            size=300,
            color="#000000",
            background="#FFFFFF",
            error_correction=ErrorCorrection.HIGH,
        ),
        logo_path="/path/to/logo.png",
        logo_size=0.25,
    )
    
    # Batch generation
    codes = await qr.generate_batch([
        {"data": "url1", "filename": "qr1.png"},
        {"data": "url2", "filename": "qr2.png"},
    ])
"""

from __future__ import annotations

import asyncio
import base64
import functools
import io
import json
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
    TypeVar,
    Union,
)

T = TypeVar('T')


logger = logging.getLogger(__name__)


class QRError(Exception):
    """QR code error."""
    pass


class GenerationError(QRError):
    """QR generation error."""
    pass


class ErrorCorrection(str, Enum):
    """QR error correction levels."""
    LOW = "L"      # ~7% correction
    MEDIUM = "M"   # ~15% correction
    QUARTILE = "Q" # ~25% correction
    HIGH = "H"     # ~30% correction


class OutputFormat(str, Enum):
    """Output formats."""
    PNG = "png"
    SVG = "svg"
    JPEG = "jpeg"
    PDF = "pdf"
    EPS = "eps"
    BASE64 = "base64"


class QRType(str, Enum):
    """QR content types."""
    URL = "url"
    TEXT = "text"
    EMAIL = "email"
    PHONE = "phone"
    SMS = "sms"
    WIFI = "wifi"
    VCARD = "vcard"
    CALENDAR = "calendar"
    GEO = "geo"


@dataclass
class QRStyle:
    """QR code styling."""
    size: int = 300
    color: str = "#000000"
    background: str = "#FFFFFF"
    error_correction: ErrorCorrection = ErrorCorrection.MEDIUM
    border: int = 4
    module_drawer: str = "square"  # square, rounded, circle, gapped
    eye_drawer: str = "square"     # square, circle, rounded
    eye_color: Optional[str] = None
    gradient: bool = False
    gradient_start: str = "#000000"
    gradient_end: str = "#333333"
    gradient_direction: str = "vertical"  # vertical, horizontal, diagonal


@dataclass
class LogoConfig:
    """Logo configuration."""
    path: Optional[str] = None
    data: Optional[bytes] = None
    size_ratio: float = 0.25  # Logo size relative to QR
    border: int = 2
    border_color: str = "#FFFFFF"
    shape: str = "square"  # square, circle, rounded


@dataclass
class WifiConfig:
    """WiFi QR configuration."""
    ssid: str = ""
    password: str = ""
    encryption: str = "WPA"  # WPA, WEP, nopass
    hidden: bool = False


@dataclass
class VCardConfig:
    """vCard QR configuration."""
    first_name: str = ""
    last_name: str = ""
    phone: str = ""
    email: str = ""
    organization: str = ""
    title: str = ""
    url: str = ""
    address: str = ""
    note: str = ""


@dataclass
class CalendarConfig:
    """Calendar event QR configuration."""
    title: str = ""
    start: datetime = field(default_factory=datetime.utcnow)
    end: Optional[datetime] = None
    location: str = ""
    description: str = ""
    all_day: bool = False


@dataclass
class GeoConfig:
    """Geo location QR configuration."""
    latitude: float = 0.0
    longitude: float = 0.0
    altitude: Optional[float] = None


@dataclass
class GeneratedQR:
    """Generated QR code."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    data: str = ""
    content: bytes = b""
    format: OutputFormat = OutputFormat.PNG
    width: int = 0
    height: int = 0
    generated_at: datetime = field(default_factory=datetime.utcnow)


# QR Encoder
class QREncoder(ABC):
    """Abstract QR encoder."""
    
    @abstractmethod
    async def encode(
        self,
        data: str,
        style: QRStyle,
        format: OutputFormat,
        logo: Optional[LogoConfig] = None,
    ) -> bytes:
        """Encode data to QR code."""
        pass


class MockQREncoder(QREncoder):
    """Mock QR encoder for testing."""
    
    async def encode(
        self,
        data: str,
        style: QRStyle,
        format: OutputFormat,
        logo: Optional[LogoConfig] = None,
    ) -> bytes:
        """Generate mock QR data."""
        qr_info = {
            "data": data,
            "size": style.size,
            "color": style.color,
            "background": style.background,
            "error_correction": style.error_correction.value,
            "format": format.value,
            "has_logo": logo is not None,
            "generated_at": datetime.utcnow().isoformat(),
        }
        
        if format == OutputFormat.SVG:
            # Generate simple SVG
            svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{style.size}" height="{style.size}">
    <rect width="100%" height="100%" fill="{style.background}"/>
    <text x="50%" y="50%" text-anchor="middle" fill="{style.color}">
        [QR: {data[:20]}...]
    </text>
</svg>'''
            return svg.encode()
        
        elif format == OutputFormat.BASE64:
            return base64.b64encode(json.dumps(qr_info).encode())
        
        else:
            # Return JSON for mock
            return json.dumps(qr_info, indent=2).encode()


# Data formatters
class QRDataFormatter:
    """Format data for QR codes."""
    
    @staticmethod
    def format_url(url: str) -> str:
        """Format URL."""
        if not url.startswith(("http://", "https://", "ftp://")):
            url = f"https://{url}"
        return url
    
    @staticmethod
    def format_email(
        email: str,
        subject: str = "",
        body: str = "",
    ) -> str:
        """Format email."""
        result = f"mailto:{email}"
        params = []
        if subject:
            params.append(f"subject={subject}")
        if body:
            params.append(f"body={body}")
        if params:
            result += "?" + "&".join(params)
        return result
    
    @staticmethod
    def format_phone(phone: str) -> str:
        """Format phone number."""
        return f"tel:{phone}"
    
    @staticmethod
    def format_sms(
        phone: str,
        message: str = "",
    ) -> str:
        """Format SMS."""
        result = f"sms:{phone}"
        if message:
            result += f"?body={message}"
        return result
    
    @staticmethod
    def format_wifi(config: WifiConfig) -> str:
        """Format WiFi configuration."""
        hidden = "true" if config.hidden else "false"
        return (
            f"WIFI:T:{config.encryption};"
            f"S:{config.ssid};"
            f"P:{config.password};"
            f"H:{hidden};;"
        )
    
    @staticmethod
    def format_vcard(config: VCardConfig) -> str:
        """Format vCard."""
        lines = [
            "BEGIN:VCARD",
            "VERSION:3.0",
            f"N:{config.last_name};{config.first_name}",
            f"FN:{config.first_name} {config.last_name}",
        ]
        
        if config.phone:
            lines.append(f"TEL:{config.phone}")
        if config.email:
            lines.append(f"EMAIL:{config.email}")
        if config.organization:
            lines.append(f"ORG:{config.organization}")
        if config.title:
            lines.append(f"TITLE:{config.title}")
        if config.url:
            lines.append(f"URL:{config.url}")
        if config.address:
            lines.append(f"ADR:{config.address}")
        if config.note:
            lines.append(f"NOTE:{config.note}")
        
        lines.append("END:VCARD")
        
        return "\n".join(lines)
    
    @staticmethod
    def format_calendar(config: CalendarConfig) -> str:
        """Format calendar event (iCalendar)."""
        def format_dt(dt: datetime) -> str:
            return dt.strftime("%Y%m%dT%H%M%SZ")
        
        end = config.end or config.start
        
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "BEGIN:VEVENT",
            f"SUMMARY:{config.title}",
            f"DTSTART:{format_dt(config.start)}",
            f"DTEND:{format_dt(end)}",
        ]
        
        if config.location:
            lines.append(f"LOCATION:{config.location}")
        if config.description:
            lines.append(f"DESCRIPTION:{config.description}")
        
        lines.extend([
            "END:VEVENT",
            "END:VCALENDAR",
        ])
        
        return "\n".join(lines)
    
    @staticmethod
    def format_geo(config: GeoConfig) -> str:
        """Format geo location."""
        result = f"geo:{config.latitude},{config.longitude}"
        if config.altitude is not None:
            result += f",{config.altitude}"
        return result


class QRGenerator:
    """
    QR code generation service.
    """
    
    def __init__(
        self,
        encoder: Optional[QREncoder] = None,
        default_style: Optional[QRStyle] = None,
    ):
        self._encoder = encoder or MockQREncoder()
        self._default_style = default_style or QRStyle()
        self._formatter = QRDataFormatter()
        self._templates: Dict[str, Dict[str, Any]] = {}
    
    async def generate(
        self,
        data: str,
        style: Optional[QRStyle] = None,
        format: OutputFormat = OutputFormat.PNG,
        logo: Optional[LogoConfig] = None,
    ) -> GeneratedQR:
        """
        Generate QR code.
        
        Args:
            data: Content to encode
            style: QR styling options
            format: Output format
            logo: Logo configuration
            
        Returns:
            Generated QR code
        """
        style = style or self._default_style
        
        content = await self._encoder.encode(data, style, format, logo)
        
        return GeneratedQR(
            data=data,
            content=content,
            format=format,
            width=style.size,
            height=style.size,
        )
    
    async def generate_url(
        self,
        url: str,
        **kwargs,
    ) -> GeneratedQR:
        """Generate URL QR code."""
        formatted = self._formatter.format_url(url)
        return await self.generate(formatted, **kwargs)
    
    async def generate_email(
        self,
        email: str,
        subject: str = "",
        body: str = "",
        **kwargs,
    ) -> GeneratedQR:
        """Generate email QR code."""
        formatted = self._formatter.format_email(email, subject, body)
        return await self.generate(formatted, **kwargs)
    
    async def generate_phone(
        self,
        phone: str,
        **kwargs,
    ) -> GeneratedQR:
        """Generate phone QR code."""
        formatted = self._formatter.format_phone(phone)
        return await self.generate(formatted, **kwargs)
    
    async def generate_sms(
        self,
        phone: str,
        message: str = "",
        **kwargs,
    ) -> GeneratedQR:
        """Generate SMS QR code."""
        formatted = self._formatter.format_sms(phone, message)
        return await self.generate(formatted, **kwargs)
    
    async def generate_wifi(
        self,
        config: WifiConfig,
        **kwargs,
    ) -> GeneratedQR:
        """Generate WiFi QR code."""
        formatted = self._formatter.format_wifi(config)
        return await self.generate(formatted, **kwargs)
    
    async def generate_vcard(
        self,
        config: VCardConfig,
        **kwargs,
    ) -> GeneratedQR:
        """Generate vCard QR code."""
        formatted = self._formatter.format_vcard(config)
        return await self.generate(formatted, **kwargs)
    
    async def generate_calendar(
        self,
        config: CalendarConfig,
        **kwargs,
    ) -> GeneratedQR:
        """Generate calendar event QR code."""
        formatted = self._formatter.format_calendar(config)
        return await self.generate(formatted, **kwargs)
    
    async def generate_geo(
        self,
        config: GeoConfig,
        **kwargs,
    ) -> GeneratedQR:
        """Generate geo location QR code."""
        formatted = self._formatter.format_geo(config)
        return await self.generate(formatted, **kwargs)
    
    async def generate_batch(
        self,
        items: List[Dict[str, Any]],
        style: Optional[QRStyle] = None,
        format: OutputFormat = OutputFormat.PNG,
    ) -> List[GeneratedQR]:
        """
        Generate multiple QR codes.
        
        Args:
            items: List of items with 'data' key
            style: QR styling options
            format: Output format
            
        Returns:
            List of generated QR codes
        """
        tasks = []
        
        for item in items:
            data = item.get("data", "")
            item_style = item.get("style", style)
            item_format = item.get("format", format)
            logo = item.get("logo")
            
            tasks.append(
                self.generate(data, item_style, item_format, logo)
            )
        
        return await asyncio.gather(*tasks)
    
    async def save(
        self,
        qr: GeneratedQR,
        path: Union[str, Path],
    ) -> Path:
        """Save QR code to file."""
        path = Path(path)
        path.write_bytes(qr.content)
        return path
    
    def to_base64(self, qr: GeneratedQR) -> str:
        """Convert QR to base64 string."""
        return base64.b64encode(qr.content).decode()
    
    def to_data_uri(self, qr: GeneratedQR) -> str:
        """Convert QR to data URI."""
        b64 = self.to_base64(qr)
        mime = self._get_mime_type(qr.format)
        return f"data:{mime};base64,{b64}"
    
    def _get_mime_type(self, format: OutputFormat) -> str:
        """Get MIME type for format."""
        mime_types = {
            OutputFormat.PNG: "image/png",
            OutputFormat.JPEG: "image/jpeg",
            OutputFormat.SVG: "image/svg+xml",
            OutputFormat.PDF: "application/pdf",
            OutputFormat.EPS: "application/postscript",
            OutputFormat.BASE64: "text/plain",
        }
        return mime_types.get(format, "application/octet-stream")
    
    # Templates
    def register_template(
        self,
        name: str,
        style: QRStyle,
        logo: Optional[LogoConfig] = None,
    ) -> None:
        """Register QR template."""
        self._templates[name] = {
            "style": style,
            "logo": logo,
        }
    
    async def from_template(
        self,
        template_name: str,
        data: str,
        format: OutputFormat = OutputFormat.PNG,
    ) -> GeneratedQR:
        """Generate QR from template."""
        template = self._templates.get(template_name)
        if not template:
            raise QRError(f"Template not found: {template_name}")
        
        return await self.generate(
            data,
            style=template["style"],
            format=format,
            logo=template.get("logo"),
        )


# Decorators
def qr_response(
    format: OutputFormat = OutputFormat.PNG,
) -> Callable:
    """Decorator for QR code response."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            
            if isinstance(result, GeneratedQR):
                return {
                    "content": result.content,
                    "content_type": {
                        OutputFormat.PNG: "image/png",
                        OutputFormat.SVG: "image/svg+xml",
                        OutputFormat.JPEG: "image/jpeg",
                        OutputFormat.PDF: "application/pdf",
                    }.get(result.format, "application/octet-stream"),
                }
            
            return result
        
        return wrapper
    return decorator


# Factory functions
def create_qr_generator(
    encoder: Optional[QREncoder] = None,
    default_style: Optional[QRStyle] = None,
) -> QRGenerator:
    """Create QR generator."""
    return QRGenerator(encoder, default_style)


def create_qr_style(
    size: int = 300,
    color: str = "#000000",
    background: str = "#FFFFFF",
    error_correction: ErrorCorrection = ErrorCorrection.MEDIUM,
    **kwargs,
) -> QRStyle:
    """Create QR style."""
    return QRStyle(
        size=size,
        color=color,
        background=background,
        error_correction=error_correction,
        **kwargs,
    )


def create_logo_config(
    path: Optional[str] = None,
    data: Optional[bytes] = None,
    size_ratio: float = 0.25,
    **kwargs,
) -> LogoConfig:
    """Create logo configuration."""
    return LogoConfig(
        path=path,
        data=data,
        size_ratio=size_ratio,
        **kwargs,
    )


def create_wifi_config(
    ssid: str,
    password: str = "",
    encryption: str = "WPA",
    hidden: bool = False,
) -> WifiConfig:
    """Create WiFi configuration."""
    return WifiConfig(
        ssid=ssid,
        password=password,
        encryption=encryption,
        hidden=hidden,
    )


def create_vcard_config(
    first_name: str,
    last_name: str = "",
    **kwargs,
) -> VCardConfig:
    """Create vCard configuration."""
    return VCardConfig(
        first_name=first_name,
        last_name=last_name,
        **kwargs,
    )


def create_calendar_config(
    title: str,
    start: datetime,
    **kwargs,
) -> CalendarConfig:
    """Create calendar configuration."""
    return CalendarConfig(
        title=title,
        start=start,
        **kwargs,
    )


def create_geo_config(
    latitude: float,
    longitude: float,
    altitude: Optional[float] = None,
) -> GeoConfig:
    """Create geo configuration."""
    return GeoConfig(
        latitude=latitude,
        longitude=longitude,
        altitude=altitude,
    )


__all__ = [
    # Exceptions
    "QRError",
    "GenerationError",
    # Enums
    "ErrorCorrection",
    "OutputFormat",
    "QRType",
    # Data classes
    "QRStyle",
    "LogoConfig",
    "WifiConfig",
    "VCardConfig",
    "CalendarConfig",
    "GeoConfig",
    "GeneratedQR",
    # Encoder
    "QREncoder",
    "MockQREncoder",
    # Formatter
    "QRDataFormatter",
    # Generator
    "QRGenerator",
    # Decorators
    "qr_response",
    # Factory functions
    "create_qr_generator",
    "create_qr_style",
    "create_logo_config",
    "create_wifi_config",
    "create_vcard_config",
    "create_calendar_config",
    "create_geo_config",
]
