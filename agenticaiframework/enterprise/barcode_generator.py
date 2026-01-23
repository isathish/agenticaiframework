"""
Enterprise Barcode Generator Module.

Provides barcode generation with multiple formats,
customization, and batch processing.

Example:
    # Create barcode generator
    barcodes = create_barcode_generator()
    
    # Generate Code128 barcode
    image = await barcodes.generate("ABC-12345", format=BarcodeFormat.CODE128)
    
    # Generate EAN13
    image = await barcodes.generate("5901234123457", format=BarcodeFormat.EAN13)
    
    # Batch generation
    results = await barcodes.generate_batch([
        {"data": "SKU001", "format": BarcodeFormat.CODE128},
        {"data": "SKU002", "format": BarcodeFormat.CODE128},
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


class BarcodeError(Exception):
    """Barcode error."""
    pass


class ValidationError(BarcodeError):
    """Barcode validation error."""
    pass


class GenerationError(BarcodeError):
    """Barcode generation error."""
    pass


class BarcodeFormat(str, Enum):
    """Barcode formats."""
    # 1D Barcodes
    CODE128 = "code128"
    CODE39 = "code39"
    CODE93 = "code93"
    EAN13 = "ean13"
    EAN8 = "ean8"
    UPCA = "upca"
    UPCE = "upce"
    ISBN10 = "isbn10"
    ISBN13 = "isbn13"
    ISSN = "issn"
    ITF = "itf"
    ITF14 = "itf14"
    PZN = "pzn"
    JAN = "jan"
    # 2D Barcodes
    QR = "qr"
    DATAMATRIX = "datamatrix"
    PDF417 = "pdf417"
    AZTEC = "aztec"


class OutputFormat(str, Enum):
    """Output formats."""
    PNG = "png"
    SVG = "svg"
    JPEG = "jpeg"
    EPS = "eps"
    PDF = "pdf"


class TextPosition(str, Enum):
    """Text position."""
    NONE = "none"
    BOTTOM = "bottom"
    TOP = "top"


@dataclass
class BarcodeStyle:
    """Barcode styling options."""
    width: int = 300
    height: int = 100
    module_width: float = 0.2
    module_height: float = 15.0
    quiet_zone: float = 6.5
    font_size: int = 10
    text_position: TextPosition = TextPosition.BOTTOM
    text_color: str = "#000000"
    bar_color: str = "#000000"
    background: str = "#FFFFFF"
    dpi: int = 300


@dataclass
class BarcodeInfo:
    """Barcode format information."""
    format: BarcodeFormat
    name: str
    description: str
    valid_chars: str
    min_length: int
    max_length: int
    checksum: bool


@dataclass
class GeneratedBarcode:
    """Generated barcode."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    data: str = ""
    format: BarcodeFormat = BarcodeFormat.CODE128
    output_format: OutputFormat = OutputFormat.PNG
    content: bytes = b""
    width: int = 0
    height: int = 0
    generated_at: datetime = field(default_factory=datetime.utcnow)


# Format specifications
BARCODE_SPECS: Dict[BarcodeFormat, BarcodeInfo] = {
    BarcodeFormat.CODE128: BarcodeInfo(
        format=BarcodeFormat.CODE128,
        name="Code 128",
        description="High-density alphanumeric barcode",
        valid_chars="ASCII 0-127",
        min_length=1,
        max_length=80,
        checksum=True,
    ),
    BarcodeFormat.CODE39: BarcodeInfo(
        format=BarcodeFormat.CODE39,
        name="Code 39",
        description="Alphanumeric barcode used in automotive and defense",
        valid_chars="A-Z 0-9 - . $ / + % SPACE",
        min_length=1,
        max_length=43,
        checksum=False,
    ),
    BarcodeFormat.EAN13: BarcodeInfo(
        format=BarcodeFormat.EAN13,
        name="EAN-13",
        description="European Article Number - worldwide retail",
        valid_chars="0-9",
        min_length=12,
        max_length=13,
        checksum=True,
    ),
    BarcodeFormat.EAN8: BarcodeInfo(
        format=BarcodeFormat.EAN8,
        name="EAN-8",
        description="Compact version of EAN-13",
        valid_chars="0-9",
        min_length=7,
        max_length=8,
        checksum=True,
    ),
    BarcodeFormat.UPCA: BarcodeInfo(
        format=BarcodeFormat.UPCA,
        name="UPC-A",
        description="Universal Product Code - North America",
        valid_chars="0-9",
        min_length=11,
        max_length=12,
        checksum=True,
    ),
    BarcodeFormat.ISBN13: BarcodeInfo(
        format=BarcodeFormat.ISBN13,
        name="ISBN-13",
        description="International Standard Book Number",
        valid_chars="0-9",
        min_length=12,
        max_length=13,
        checksum=True,
    ),
    BarcodeFormat.ITF: BarcodeInfo(
        format=BarcodeFormat.ITF,
        name="Interleaved 2 of 5",
        description="Numeric barcode for packaging",
        valid_chars="0-9",
        min_length=2,
        max_length=30,
        checksum=False,
    ),
}


# Validator
class BarcodeValidator:
    """Barcode data validator."""
    
    @staticmethod
    def validate(
        data: str,
        format: BarcodeFormat,
    ) -> Tuple[bool, str]:
        """
        Validate barcode data.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not data:
            return False, "Data cannot be empty"
        
        spec = BARCODE_SPECS.get(format)
        
        if spec:
            if len(data) < spec.min_length:
                return False, f"Data too short (min: {spec.min_length})"
            if len(data) > spec.max_length:
                return False, f"Data too long (max: {spec.max_length})"
        
        # Format-specific validation
        if format in (BarcodeFormat.EAN13, BarcodeFormat.EAN8, BarcodeFormat.UPCA):
            if not data.isdigit():
                return False, "Only digits allowed"
        
        elif format == BarcodeFormat.CODE39:
            valid_chars = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-. $/+%")
            if not all(c.upper() in valid_chars for c in data):
                return False, "Invalid characters for Code 39"
        
        return True, ""
    
    @staticmethod
    def calculate_checksum(
        data: str,
        format: BarcodeFormat,
    ) -> str:
        """Calculate checksum for barcode."""
        if format == BarcodeFormat.EAN13:
            return BarcodeValidator._ean_checksum(data, 12)
        elif format == BarcodeFormat.EAN8:
            return BarcodeValidator._ean_checksum(data, 7)
        elif format == BarcodeFormat.UPCA:
            return BarcodeValidator._upc_checksum(data)
        
        return ""
    
    @staticmethod
    def _ean_checksum(data: str, length: int) -> str:
        """Calculate EAN checksum."""
        if len(data) < length:
            data = data.zfill(length)
        
        data = data[:length]
        
        total = 0
        for i, digit in enumerate(data):
            if i % 2 == 0:
                total += int(digit)
            else:
                total += int(digit) * 3
        
        check = (10 - (total % 10)) % 10
        return str(check)
    
    @staticmethod
    def _upc_checksum(data: str) -> str:
        """Calculate UPC checksum."""
        if len(data) < 11:
            data = data.zfill(11)
        
        data = data[:11]
        
        odd = sum(int(d) for d in data[::2])
        even = sum(int(d) for d in data[1::2])
        total = odd * 3 + even
        
        check = (10 - (total % 10)) % 10
        return str(check)


# Encoder
class BarcodeEncoder(ABC):
    """Abstract barcode encoder."""
    
    @abstractmethod
    async def encode(
        self,
        data: str,
        format: BarcodeFormat,
        style: BarcodeStyle,
        output_format: OutputFormat,
    ) -> bytes:
        """Encode data to barcode."""
        pass


class MockBarcodeEncoder(BarcodeEncoder):
    """Mock barcode encoder for testing."""
    
    async def encode(
        self,
        data: str,
        format: BarcodeFormat,
        style: BarcodeStyle,
        output_format: OutputFormat,
    ) -> bytes:
        """Generate mock barcode data."""
        barcode_info = {
            "data": data,
            "format": format.value,
            "output_format": output_format.value,
            "width": style.width,
            "height": style.height,
            "text_position": style.text_position.value,
            "generated_at": datetime.utcnow().isoformat(),
        }
        
        if output_format == OutputFormat.SVG:
            # Generate simple SVG representation
            bars = self._generate_bars(data)
            svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{style.width}" height="{style.height}">
    <rect width="100%" height="100%" fill="{style.background}"/>
    <g fill="{style.bar_color}">
        {bars}
    </g>
    <text x="50%" y="{style.height - 5}" text-anchor="middle" 
          font-size="{style.font_size}" fill="{style.text_color}">
        {data}
    </text>
</svg>'''
            return svg.encode()
        
        return json.dumps(barcode_info, indent=2).encode()
    
    def _generate_bars(self, data: str) -> str:
        """Generate simple bar representation."""
        bars = []
        x = 10
        
        for i, char in enumerate(data[:20]):
            width = 2 if ord(char) % 2 == 0 else 3
            bars.append(
                f'<rect x="{x}" y="10" width="{width}" height="60"/>'
            )
            x += width + 2
        
        return "\n        ".join(bars)


class BarcodeGenerator:
    """
    Barcode generation service.
    """
    
    def __init__(
        self,
        encoder: Optional[BarcodeEncoder] = None,
        default_style: Optional[BarcodeStyle] = None,
        validate: bool = True,
    ):
        self._encoder = encoder or MockBarcodeEncoder()
        self._default_style = default_style or BarcodeStyle()
        self._validate = validate
        self._validator = BarcodeValidator()
    
    async def generate(
        self,
        data: str,
        format: BarcodeFormat = BarcodeFormat.CODE128,
        style: Optional[BarcodeStyle] = None,
        output_format: OutputFormat = OutputFormat.PNG,
        add_checksum: bool = False,
    ) -> GeneratedBarcode:
        """
        Generate barcode.
        
        Args:
            data: Data to encode
            format: Barcode format
            style: Styling options
            output_format: Output format
            add_checksum: Auto-add checksum
            
        Returns:
            Generated barcode
        """
        style = style or self._default_style
        
        # Validate
        if self._validate:
            is_valid, error = self._validator.validate(data, format)
            if not is_valid:
                raise ValidationError(error)
        
        # Add checksum if needed
        if add_checksum:
            checksum = self._validator.calculate_checksum(data, format)
            if checksum:
                data = data + checksum
        
        # Generate
        content = await self._encoder.encode(data, format, style, output_format)
        
        return GeneratedBarcode(
            data=data,
            format=format,
            output_format=output_format,
            content=content,
            width=style.width,
            height=style.height,
        )
    
    async def generate_code128(
        self,
        data: str,
        **kwargs,
    ) -> GeneratedBarcode:
        """Generate Code 128 barcode."""
        return await self.generate(data, BarcodeFormat.CODE128, **kwargs)
    
    async def generate_ean13(
        self,
        data: str,
        **kwargs,
    ) -> GeneratedBarcode:
        """Generate EAN-13 barcode."""
        return await self.generate(
            data,
            BarcodeFormat.EAN13,
            add_checksum=len(data) == 12,
            **kwargs,
        )
    
    async def generate_ean8(
        self,
        data: str,
        **kwargs,
    ) -> GeneratedBarcode:
        """Generate EAN-8 barcode."""
        return await self.generate(
            data,
            BarcodeFormat.EAN8,
            add_checksum=len(data) == 7,
            **kwargs,
        )
    
    async def generate_upca(
        self,
        data: str,
        **kwargs,
    ) -> GeneratedBarcode:
        """Generate UPC-A barcode."""
        return await self.generate(
            data,
            BarcodeFormat.UPCA,
            add_checksum=len(data) == 11,
            **kwargs,
        )
    
    async def generate_isbn(
        self,
        isbn: str,
        **kwargs,
    ) -> GeneratedBarcode:
        """Generate ISBN barcode."""
        # Strip hyphens
        isbn = isbn.replace("-", "").replace(" ", "")
        
        format = BarcodeFormat.ISBN13 if len(isbn) >= 12 else BarcodeFormat.ISBN10
        
        return await self.generate(isbn, format, **kwargs)
    
    async def generate_batch(
        self,
        items: List[Dict[str, Any]],
        default_format: BarcodeFormat = BarcodeFormat.CODE128,
        style: Optional[BarcodeStyle] = None,
        output_format: OutputFormat = OutputFormat.PNG,
    ) -> List[GeneratedBarcode]:
        """
        Generate multiple barcodes.
        
        Args:
            items: List of items with 'data' key
            default_format: Default barcode format
            style: Styling options
            output_format: Output format
            
        Returns:
            List of generated barcodes
        """
        tasks = []
        
        for item in items:
            data = item.get("data", "")
            item_format = item.get("format", default_format)
            item_style = item.get("style", style)
            item_output = item.get("output_format", output_format)
            add_checksum = item.get("add_checksum", False)
            
            tasks.append(
                self.generate(
                    data,
                    item_format,
                    item_style,
                    item_output,
                    add_checksum,
                )
            )
        
        return await asyncio.gather(*tasks, return_exceptions=True)
    
    async def save(
        self,
        barcode: GeneratedBarcode,
        path: Union[str, Path],
    ) -> Path:
        """Save barcode to file."""
        path = Path(path)
        path.write_bytes(barcode.content)
        return path
    
    def to_base64(self, barcode: GeneratedBarcode) -> str:
        """Convert barcode to base64 string."""
        return base64.b64encode(barcode.content).decode()
    
    def to_data_uri(self, barcode: GeneratedBarcode) -> str:
        """Convert barcode to data URI."""
        b64 = self.to_base64(barcode)
        mime = self._get_mime_type(barcode.output_format)
        return f"data:{mime};base64,{b64}"
    
    def _get_mime_type(self, format: OutputFormat) -> str:
        """Get MIME type for format."""
        mime_types = {
            OutputFormat.PNG: "image/png",
            OutputFormat.JPEG: "image/jpeg",
            OutputFormat.SVG: "image/svg+xml",
            OutputFormat.PDF: "application/pdf",
            OutputFormat.EPS: "application/postscript",
        }
        return mime_types.get(format, "application/octet-stream")
    
    def get_format_info(
        self,
        format: BarcodeFormat,
    ) -> Optional[BarcodeInfo]:
        """Get barcode format information."""
        return BARCODE_SPECS.get(format)
    
    def list_formats(self) -> List[BarcodeInfo]:
        """List all barcode formats."""
        return list(BARCODE_SPECS.values())
    
    def validate(
        self,
        data: str,
        format: BarcodeFormat,
    ) -> Tuple[bool, str]:
        """Validate barcode data."""
        return self._validator.validate(data, format)


# Decorators
def barcode_response(
    format: OutputFormat = OutputFormat.PNG,
) -> Callable:
    """Decorator for barcode response."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            
            if isinstance(result, GeneratedBarcode):
                return {
                    "content": result.content,
                    "content_type": {
                        OutputFormat.PNG: "image/png",
                        OutputFormat.SVG: "image/svg+xml",
                        OutputFormat.JPEG: "image/jpeg",
                        OutputFormat.PDF: "application/pdf",
                    }.get(result.output_format, "application/octet-stream"),
                }
            
            return result
        
        return wrapper
    return decorator


# Factory functions
def create_barcode_generator(
    encoder: Optional[BarcodeEncoder] = None,
    default_style: Optional[BarcodeStyle] = None,
    validate: bool = True,
) -> BarcodeGenerator:
    """Create barcode generator."""
    return BarcodeGenerator(encoder, default_style, validate)


def create_barcode_style(
    width: int = 300,
    height: int = 100,
    text_position: TextPosition = TextPosition.BOTTOM,
    **kwargs,
) -> BarcodeStyle:
    """Create barcode style."""
    return BarcodeStyle(
        width=width,
        height=height,
        text_position=text_position,
        **kwargs,
    )


def create_product_barcode(
    gtin: str,
) -> Tuple[BarcodeFormat, str]:
    """
    Determine barcode format from GTIN.
    
    Returns:
        Tuple of (format, cleaned_data)
    """
    # Clean input
    gtin = gtin.replace("-", "").replace(" ", "")
    
    if len(gtin) == 8:
        return BarcodeFormat.EAN8, gtin
    elif len(gtin) == 12:
        return BarcodeFormat.UPCA, gtin
    elif len(gtin) == 13:
        return BarcodeFormat.EAN13, gtin
    elif len(gtin) == 14:
        return BarcodeFormat.ITF14, gtin
    else:
        return BarcodeFormat.CODE128, gtin


__all__ = [
    # Exceptions
    "BarcodeError",
    "ValidationError",
    "GenerationError",
    # Enums
    "BarcodeFormat",
    "OutputFormat",
    "TextPosition",
    # Data classes
    "BarcodeStyle",
    "BarcodeInfo",
    "GeneratedBarcode",
    # Specifications
    "BARCODE_SPECS",
    # Validator
    "BarcodeValidator",
    # Encoder
    "BarcodeEncoder",
    "MockBarcodeEncoder",
    # Generator
    "BarcodeGenerator",
    # Decorators
    "barcode_response",
    # Factory functions
    "create_barcode_generator",
    "create_barcode_style",
    "create_product_barcode",
]
