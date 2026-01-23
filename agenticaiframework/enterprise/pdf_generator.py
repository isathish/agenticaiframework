"""
Enterprise PDF Generator Module.

Provides PDF generation from HTML templates,
document merging, watermarking, and styling.

Example:
    # Create PDF generator
    pdf = create_pdf_generator()
    
    # Generate from HTML
    content = await pdf.from_html(
        '<h1>Hello World</h1>',
        options={'page-size': 'A4'},
    )
    
    # Generate from template
    content = await pdf.from_template(
        template='invoice',
        context={'items': [...], 'total': 100},
    )
    
    # Save to file
    await pdf.save(content, 'output.pdf')
"""

from __future__ import annotations

import asyncio
import base64
import functools
import logging
import os
import tempfile
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
    Generic,
    List,
    Optional,
    TypeVar,
    Union,
)

T = TypeVar('T')


logger = logging.getLogger(__name__)


class PDFError(Exception):
    """PDF generation error."""
    pass


class TemplateError(PDFError):
    """Template rendering error."""
    pass


class RenderError(PDFError):
    """PDF rendering error."""
    pass


class PageSize(str, Enum):
    """Page sizes."""
    A3 = "A3"
    A4 = "A4"
    A5 = "A5"
    LETTER = "Letter"
    LEGAL = "Legal"
    TABLOID = "Tabloid"


class Orientation(str, Enum):
    """Page orientation."""
    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"


@dataclass
class Margins:
    """Page margins in mm."""
    top: int = 10
    right: int = 10
    bottom: int = 10
    left: int = 10


@dataclass
class PageOptions:
    """PDF page options."""
    size: PageSize = PageSize.A4
    orientation: Orientation = Orientation.PORTRAIT
    margins: Margins = field(default_factory=Margins)
    header: str = ""
    footer: str = ""
    header_height: int = 0
    footer_height: int = 0


@dataclass
class PDFOptions:
    """PDF generation options."""
    page: PageOptions = field(default_factory=PageOptions)
    title: str = ""
    author: str = ""
    subject: str = ""
    keywords: List[str] = field(default_factory=list)
    compress: bool = True
    javascript: bool = False
    print_background: bool = True
    prefer_css_page_size: bool = False


@dataclass
class WatermarkOptions:
    """Watermark options."""
    text: str = ""
    image_path: str = ""
    opacity: float = 0.5
    rotation: int = 45
    font_size: int = 48
    color: str = "#888888"
    position: str = "center"  # center, top, bottom


@dataclass
class PDFDocument:
    """PDF document."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: bytes = b""
    pages: int = 0
    size: int = 0
    title: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_base64(self) -> str:
        """Convert to base64."""
        return base64.b64encode(self.content).decode()
    
    def to_data_uri(self) -> str:
        """Convert to data URI."""
        return f"data:application/pdf;base64,{self.to_base64()}"


# Template engine
class TemplateEngine(ABC):
    """Template engine."""
    
    @abstractmethod
    def render(
        self,
        template: str,
        context: Dict[str, Any],
    ) -> str:
        """Render template."""
        pass


class SimpleTemplateEngine(TemplateEngine):
    """Simple template engine."""
    
    def __init__(
        self,
        templates: Optional[Dict[str, str]] = None,
    ):
        self._templates = templates or {}
    
    def add_template(self, name: str, content: str) -> None:
        """Add template."""
        self._templates[name] = content
    
    def render(
        self,
        template: str,
        context: Dict[str, Any],
    ) -> str:
        if template in self._templates:
            template = self._templates[template]
        
        result = template
        for key, value in context.items():
            result = result.replace(f"{{{{{key}}}}}", str(value))
        
        return result


# PDF renderers
class PDFRenderer(ABC):
    """Abstract PDF renderer."""
    
    @abstractmethod
    async def render_html(
        self,
        html: str,
        options: PDFOptions,
    ) -> bytes:
        """Render HTML to PDF."""
        pass


class MockRenderer(PDFRenderer):
    """Mock renderer for testing."""
    
    async def render_html(
        self,
        html: str,
        options: PDFOptions,
    ) -> bytes:
        # Generate minimal valid PDF
        pdf_content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>
endobj
xref
0 4
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
trailer
<< /Size 4 /Root 1 0 R >>
startxref
196
%%EOF"""
        return pdf_content


class PDFGenerator:
    """
    PDF generation service.
    """
    
    def __init__(
        self,
        renderer: Optional[PDFRenderer] = None,
        template_engine: Optional[TemplateEngine] = None,
        default_options: Optional[PDFOptions] = None,
    ):
        self._renderer = renderer or MockRenderer()
        self._template_engine = template_engine or SimpleTemplateEngine()
        self._default_options = default_options or PDFOptions()
        
        self._styles: Dict[str, str] = {}
    
    def add_template(self, name: str, content: str) -> None:
        """Add HTML template."""
        if isinstance(self._template_engine, SimpleTemplateEngine):
            self._template_engine.add_template(name, content)
    
    def add_style(self, name: str, css: str) -> None:
        """Add CSS style."""
        self._styles[name] = css
    
    async def from_html(
        self,
        html: str,
        options: Optional[PDFOptions] = None,
        styles: Optional[List[str]] = None,
    ) -> PDFDocument:
        """
        Generate PDF from HTML.
        
        Args:
            html: HTML content
            options: PDF options
            styles: Style names to include
            
        Returns:
            PDF document
        """
        options = options or self._default_options
        
        # Add styles
        style_content = ""
        for style_name in (styles or []):
            if style_name in self._styles:
                style_content += f"<style>{self._styles[style_name]}</style>"
        
        # Wrap HTML if needed
        if not html.strip().lower().startswith("<!doctype"):
            html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{options.title}</title>
    {style_content}
</head>
<body>
{html}
</body>
</html>"""
        elif style_content:
            html = html.replace("</head>", f"{style_content}</head>")
        
        # Render
        content = await self._renderer.render_html(html, options)
        
        return PDFDocument(
            content=content,
            pages=1,  # Would be calculated in real implementation
            size=len(content),
            title=options.title,
        )
    
    async def from_template(
        self,
        template: str,
        context: Dict[str, Any],
        options: Optional[PDFOptions] = None,
        styles: Optional[List[str]] = None,
    ) -> PDFDocument:
        """
        Generate PDF from template.
        
        Args:
            template: Template name or content
            context: Template context
            options: PDF options
            styles: Style names to include
            
        Returns:
            PDF document
        """
        html = self._template_engine.render(template, context)
        return await self.from_html(html, options, styles)
    
    async def from_url(
        self,
        url: str,
        options: Optional[PDFOptions] = None,
    ) -> PDFDocument:
        """
        Generate PDF from URL.
        
        Args:
            url: URL to render
            options: PDF options
            
        Returns:
            PDF document
        """
        # Would fetch and render URL in real implementation
        return await self.from_html(f"<p>Content from {url}</p>", options)
    
    async def merge(
        self,
        documents: List[PDFDocument],
        options: Optional[PDFOptions] = None,
    ) -> PDFDocument:
        """
        Merge multiple PDF documents.
        
        Args:
            documents: List of documents to merge
            options: PDF options
            
        Returns:
            Merged document
        """
        if not documents:
            raise PDFError("No documents to merge")
        
        # Would use PyPDF2 or similar in real implementation
        merged_content = b"".join(doc.content for doc in documents)
        total_pages = sum(doc.pages for doc in documents)
        
        return PDFDocument(
            content=merged_content,
            pages=total_pages,
            size=len(merged_content),
        )
    
    async def add_watermark(
        self,
        document: PDFDocument,
        watermark: WatermarkOptions,
    ) -> PDFDocument:
        """
        Add watermark to PDF.
        
        Args:
            document: PDF document
            watermark: Watermark options
            
        Returns:
            Watermarked document
        """
        # Would use PyPDF2 or similar in real implementation
        return PDFDocument(
            content=document.content,
            pages=document.pages,
            size=document.size,
            title=document.title,
            metadata={**document.metadata, "watermarked": True},
        )
    
    async def add_page_numbers(
        self,
        document: PDFDocument,
        format_string: str = "Page {page} of {total}",
        position: str = "bottom-center",
    ) -> PDFDocument:
        """
        Add page numbers to PDF.
        
        Args:
            document: PDF document
            format_string: Page number format
            position: Position on page
            
        Returns:
            Document with page numbers
        """
        # Would use PyPDF2 or similar in real implementation
        return PDFDocument(
            content=document.content,
            pages=document.pages,
            size=document.size,
            title=document.title,
            metadata={**document.metadata, "page_numbers": True},
        )
    
    async def split(
        self,
        document: PDFDocument,
        page_ranges: Optional[List[tuple]] = None,
    ) -> List[PDFDocument]:
        """
        Split PDF into multiple documents.
        
        Args:
            document: PDF document
            page_ranges: List of (start, end) tuples
            
        Returns:
            List of split documents
        """
        if not page_ranges:
            # Split into individual pages
            page_ranges = [(i, i) for i in range(1, document.pages + 1)]
        
        # Would use PyPDF2 or similar in real implementation
        return [
            PDFDocument(
                content=document.content,
                pages=end - start + 1,
                size=len(document.content),
            )
            for start, end in page_ranges
        ]
    
    async def encrypt(
        self,
        document: PDFDocument,
        password: str,
        permissions: Optional[Dict[str, bool]] = None,
    ) -> PDFDocument:
        """
        Encrypt PDF with password.
        
        Args:
            document: PDF document
            password: Password
            permissions: Permission flags
            
        Returns:
            Encrypted document
        """
        # Would use PyPDF2 or similar in real implementation
        return PDFDocument(
            content=document.content,
            pages=document.pages,
            size=document.size,
            title=document.title,
            metadata={**document.metadata, "encrypted": True},
        )
    
    async def compress(
        self,
        document: PDFDocument,
    ) -> PDFDocument:
        """
        Compress PDF.
        
        Args:
            document: PDF document
            
        Returns:
            Compressed document
        """
        # Would use gs or similar in real implementation
        return document
    
    async def save(
        self,
        document: PDFDocument,
        path: Union[str, Path],
    ) -> None:
        """Save PDF to file."""
        Path(path).write_bytes(document.content)


# Decorators
def pdf_response(
    template: str,
    filename: str = "document.pdf",
) -> Callable:
    """Decorator to return PDF response."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            context = await func(*args, **kwargs)
            
            generator = create_pdf_generator()
            doc = await generator.from_template(template, context)
            
            return {
                "content": doc.content,
                "filename": filename,
                "content_type": "application/pdf",
            }
        return wrapper
    return decorator


# Factory functions
def create_pdf_generator(
    renderer: Optional[PDFRenderer] = None,
    template_engine: Optional[TemplateEngine] = None,
    default_options: Optional[PDFOptions] = None,
) -> PDFGenerator:
    """Create PDF generator."""
    return PDFGenerator(
        renderer=renderer,
        template_engine=template_engine,
        default_options=default_options,
    )


def create_pdf_options(
    size: PageSize = PageSize.A4,
    orientation: Orientation = Orientation.PORTRAIT,
    margins: Optional[Margins] = None,
    title: str = "",
    **kwargs,
) -> PDFOptions:
    """Create PDF options."""
    page = PageOptions(
        size=size,
        orientation=orientation,
        margins=margins or Margins(),
    )
    return PDFOptions(page=page, title=title, **kwargs)


def create_margins(
    top: int = 10,
    right: int = 10,
    bottom: int = 10,
    left: int = 10,
) -> Margins:
    """Create page margins."""
    return Margins(top=top, right=right, bottom=bottom, left=left)


def create_watermark(
    text: str = "",
    opacity: float = 0.5,
    rotation: int = 45,
    **kwargs,
) -> WatermarkOptions:
    """Create watermark options."""
    return WatermarkOptions(
        text=text,
        opacity=opacity,
        rotation=rotation,
        **kwargs,
    )


def create_template_engine(
    templates: Optional[Dict[str, str]] = None,
) -> SimpleTemplateEngine:
    """Create template engine."""
    return SimpleTemplateEngine(templates)


def create_mock_renderer() -> MockRenderer:
    """Create mock renderer for testing."""
    return MockRenderer()


__all__ = [
    # Exceptions
    "PDFError",
    "TemplateError",
    "RenderError",
    # Enums
    "PageSize",
    "Orientation",
    # Data classes
    "Margins",
    "PageOptions",
    "PDFOptions",
    "WatermarkOptions",
    "PDFDocument",
    # Template engine
    "TemplateEngine",
    "SimpleTemplateEngine",
    # Renderers
    "PDFRenderer",
    "MockRenderer",
    # Generator
    "PDFGenerator",
    # Decorators
    "pdf_response",
    # Factory functions
    "create_pdf_generator",
    "create_pdf_options",
    "create_margins",
    "create_watermark",
    "create_template_engine",
    "create_mock_renderer",
]
