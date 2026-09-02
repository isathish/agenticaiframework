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
import re
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


_PAGE_POINTS = {
    PageSize.A3: (842, 1191),
    PageSize.A4: (595, 842),
    PageSize.A5: (420, 595),
    PageSize.LETTER: (612, 792),
    PageSize.LEGAL: (612, 1008),
    PageSize.TABLOID: (792, 1224),
}


def _page_points(page: PageOptions) -> tuple:
    w, h = _PAGE_POINTS.get(page.size, (612, 792))
    if page.orientation == Orientation.LANDSCAPE:
        w, h = h, w
    return w, h


def html_to_text(html: str) -> str:
    """Flatten HTML into readable plain text (headings, paragraphs, lists, tables)."""
    from html import unescape

    from agenticaiframework._internal.html import Element, parse_html

    root = parse_html(html)
    lines: List[str] = []
    buf: List[str] = []
    
    def flush() -> None:
        text = " ".join("".join(buf).split())
        if text:
            lines.append(text)
        buf.clear()
    
    block = {"p", "div", "section", "article", "header", "footer", "ul", "ol", "table", "tr",
             "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "pre", "hr", "br", "li", "title", "body", "html", "main", "nav", "aside"}
    skip = {"script", "style", "head", "meta", "link", "noscript"}
    
    def walk(el, depth: int = 0, list_index: Optional[List[int]] = None) -> None:
        if el.tag in skip:
            return
        if el.tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            flush()
            lines.append(el.text.upper() if el.tag in ("h1", "h2") else el.text)
            lines.append("")
            return
        if el.tag == "hr":
            flush()
            lines.append("-" * 40)
            return
        if el.tag == "br":
            flush()
            return
        if el.tag in ("ul", "ol"):
            flush()
            counter = [0]
            for child in el.children:
                if isinstance(child, Element) and child.tag == "li":
                    counter[0] += 1
                    marker = f"{counter[0]}." if el.tag == "ol" else "\u2022"
                    buf.append("  " * depth + f"{marker} ")
                    for grand in child.children:
                        if isinstance(grand, str):
                            buf.append(unescape(grand))
                        else:
                            walk(grand, depth + 1)
                    flush()
            lines.append("")
            return
        if el.tag == "tr":
            flush()
            cells = [c.text for c in el.children if isinstance(c, Element) and c.tag in ("td", "th")]
            lines.append(" | ".join(cells))
            return
        if el.tag == "pre":
            flush()
            lines.extend(el.text.splitlines())
            lines.append("")
            return
        if el.tag in block:
            flush()
        for child in el.children:
            if isinstance(child, str):
                buf.append(unescape(child))
            else:
                walk(child, depth)
        if el.tag in block:
            flush()
            if el.tag in ("p", "div", "table", "blockquote"):
                lines.append("")
    
    walk(root)
    flush()
    # collapse runs of blank lines
    out: List[str] = []
    for line in lines:
        if line == "" and (not out or out[-1] == ""):
            continue
        out.append(line)
    return "\n".join(out).strip()


class TextRenderer(PDFRenderer):
    """Stdlib renderer: HTML -> plain text -> paginated Helvetica PDF.

    Honours page size / orientation / margins, header & footer text, and
    writes document metadata. CSS is ignored beyond structural HTML.
    """
    
    def __init__(self, font_size: int = 11):
        self._font_size = font_size
    
    async def render_html(
        self,
        html: str,
        options: PDFOptions,
    ) -> bytes:
        from agenticaiframework._internal import pdf as _pdf

        text = html_to_text(html)
        width, height = _page_points(options.page)
        m = options.page.margins
        pt = lambda mm: mm * 72 / 25.4  # noqa: E731
        left, right, top, bottom = pt(m.left), pt(m.right), pt(m.top), pt(m.bottom)
        font_size = self._font_size
        leading = font_size * 1.35
        usable_w = max(72.0, width - left - right)
        header_h = leading * 2 if options.page.header else 0
        footer_h = leading * 2 if options.page.footer else 0
        usable_h = max(leading, height - top - bottom - header_h - footer_h)
        max_chars = max(20, int(usable_w / (font_size * 0.5)))
        lines_per_page = max(1, int(usable_h // leading))
        
        wrapped: List[str] = []
        for raw in text.splitlines() or [""]:
            if not raw:
                wrapped.append("")
                continue
            while len(raw) > max_chars:
                cut = raw.rfind(" ", 0, max_chars)
                cut = cut if cut > 0 else max_chars
                wrapped.append(raw[:cut])
                raw = raw[cut:].lstrip()
            wrapped.append(raw)
        pages = [wrapped[i:i + lines_per_page] for i in range(0, len(wrapped), lines_per_page)] or [[""]]
        
        doc = _pdf.PdfDocument()
        doc.version = b"1.4"
        font_id = doc.new_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
        pages_id = doc.new_object(b"PLACEHOLDER")
        page_ids: List[int] = []
        for idx, page_lines in enumerate(pages):
            content = self._content_stream(page_lines, idx + 1, len(pages), width, height, left, top, bottom,
                                           font_size, leading, options)
            cid = doc.new_object(b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream")
            page_ids.append(doc.new_object(
                b"<< /Type /Page /Parent " + f"{pages_id} 0 R".encode()
                + b" /MediaBox [0 0 " + f"{width:g} {height:g}".encode() + b"]"
                + b" /Resources << /Font << /F1 " + f"{font_id} 0 R".encode() + b" >> >>"
                + b" /Contents " + f"{cid} 0 R".encode() + b" >>"
            ))
        kids = b" ".join(f"{p} 0 R".encode() for p in page_ids)
        doc.objects[pages_id] = b"<< /Type /Pages /Count " + str(len(page_ids)).encode() + b" /Kids [" + kids + b"] >>"
        doc.root = doc.new_object(b"<< /Type /Catalog /Pages " + f"{pages_id} 0 R".encode() + b" >>")
        doc.set_info(Title=options.title, Author=options.author, Subject=options.subject,
                     Keywords=", ".join(options.keywords), Producer="agenticaiframework")
        return doc.to_bytes()
    
    @staticmethod
    def _content_stream(lines, page_no, total, width, height, left, top, bottom, font_size, leading, options) -> bytes:
        from agenticaiframework._internal.pdf import escape_pdf_text

        parts = [b"BT", f"/F1 {font_size} Tf".encode(), f"{leading:g} TL".encode()]
        y = height - top
        if options.page.header:
            hdr = options.page.header.replace("{page}", str(page_no)).replace("{total}", str(total))
            parts.append(f"{left:g} {y - font_size:g} Td (".encode() + escape_pdf_text(hdr) + b") Tj")
            parts.append(b"ET BT")
            parts.append(f"/F1 {font_size} Tf {leading:g} TL".encode())
            y -= leading * 2
        parts.append(f"{left:g} {y - font_size:g} Td".encode())
        for i, line in enumerate(lines):
            if i:
                parts.append(b"T*")
            parts.append(b"(" + escape_pdf_text(line) + b") Tj")
        parts.append(b"ET")
        if options.page.footer:
            ftr = options.page.footer.replace("{page}", str(page_no)).replace("{total}", str(total))
            parts.append(b"BT " + f"/F1 {max(font_size - 2, 6)} Tf {left:g} {bottom:g} Td (".encode() + escape_pdf_text(ftr) + b") Tj ET")
        return b"\n".join(parts)


def _hex_to_rgb(color: str) -> tuple:
    color = color.lstrip("#")
    if len(color) == 3:
        color = "".join(c * 2 for c in color)
    try:
        return tuple(int(color[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except ValueError:
        return (0.5, 0.5, 0.5)


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
        self._renderer = renderer or TextRenderer()
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
            pages=self._count_pages(content),
            size=len(content),
            title=options.title,
        )
    
    @staticmethod
    def _count_pages(content: bytes) -> int:
        from agenticaiframework._internal import pdf as _pdf

        try:
            return _pdf.PdfDocument.parse(content).num_pages
        except Exception:  # noqa: BLE001 - fall back to heuristic for exotic files
            return max(1, len(re.findall(rb"/Type\s*/Page\b", content)))
    
    @staticmethod
    def _load(document: PDFDocument):
        from agenticaiframework._internal import pdf as _pdf

        try:
            return _pdf.PdfDocument.parse(document.content)
        except _pdf.PdfError as e:
            raise PDFError(str(e)) from e
    
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
        from agenticaiframework._internal.http import AsyncClient

        response = await AsyncClient(timeout=30.0).get(url)
        if not response.ok:
            raise RenderError(f"Failed to fetch {url}: HTTP {response.status}")
        ctype = response.headers.get("content-type", "")
        if "pdf" in ctype or response.content.startswith(b"%PDF"):
            return PDFDocument(content=response.content, pages=self._count_pages(response.content),
                               size=len(response.content), title=(options or self._default_options).title,
                               metadata={"source_url": url})
        opts = options or self._default_options
        if not opts.title:
            m = re.search(r"<title[^>]*>(.*?)</title>", response.text, re.IGNORECASE | re.DOTALL)
            if m:
                opts = PDFOptions(page=opts.page, title=" ".join(m.group(1).split()), author=opts.author,
                                  subject=opts.subject, keywords=opts.keywords)
        doc = await self.from_html(response.text, opts)
        doc.metadata["source_url"] = url
        return doc
    
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
        
        from agenticaiframework._internal import pdf as _pdf

        merged = _pdf.merge_documents([self._load(d) for d in documents])
        if options and options.title:
            merged.set_info(Title=options.title, Author=options.author)
        content = merged.to_bytes()
        
        return PDFDocument(
            content=content,
            pages=merged.num_pages,
            size=len(content),
            title=(options.title if options else "") or documents[0].title,
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
        from agenticaiframework._internal.pdf import escape_pdf_text

        if not watermark.text:
            raise PDFError("Only text watermarks are supported")
        pdf = self._load(document)
        r, g, b = _hex_to_rgb(watermark.color)
        import math
        angle = math.radians(watermark.rotation)
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        
        def content(_idx, _total, w, h) -> bytes:
            text_w = len(watermark.text) * watermark.font_size * 0.5
            if watermark.position == "top":
                cx, cy = w / 2, h - watermark.font_size * 2
            elif watermark.position == "bottom":
                cx, cy = w / 2, watermark.font_size * 2
            else:
                cx, cy = w / 2, h / 2
            # translate to centre, rotate, then offset by half the text width
            x = cx - (text_w / 2) * cos_a
            y = cy - (text_w / 2) * sin_a
            return (
                b"q /AAFStampGS gs " + f"{r:.3f} {g:.3f} {b:.3f} rg BT /AAFStamp {watermark.font_size} Tf ".encode()
                + f"{cos_a:.4f} {sin_a:.4f} {-sin_a:.4f} {cos_a:.4f} {x:.2f} {y:.2f} Tm (".encode()
                + escape_pdf_text(watermark.text) + b") Tj ET Q"
            )
        
        pdf.stamp_pages(content)
        # opacity: patch the shared ExtGState we just created
        for num, body in pdf.objects.items():
            if b"/ExtGState" in body and b"/ca 0.5" in body:
                pdf.objects[num] = f"<< /Type /ExtGState /ca {watermark.opacity:.2f} /CA {watermark.opacity:.2f} >>".encode()
        content_bytes = pdf.to_bytes()
        return PDFDocument(
            content=content_bytes,
            pages=pdf.num_pages,
            size=len(content_bytes),
            title=document.title,
            metadata={**document.metadata, "watermarked": True, "watermark": watermark.text},
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
        from agenticaiframework._internal.pdf import escape_pdf_text

        pdf = self._load(document)
        font_size = 9
        
        def content(idx, total, w, h) -> bytes:
            label = format_string.format(page=idx + 1, total=total)
            text_w = len(label) * font_size * 0.5
            vertical, _, horizontal = position.partition("-")
            y = h - 30 if vertical == "top" else 20
            if horizontal == "left":
                x = 36
            elif horizontal == "right":
                x = w - 36 - text_w
            else:
                x = (w - text_w) / 2
            return (b"q 0 0 0 rg BT /AAFStamp " + f"{font_size} Tf {x:.2f} {y:.2f} Td (".encode()
                    + escape_pdf_text(label) + b") Tj ET Q")
        
        pdf.stamp_pages(content)
        content_bytes = pdf.to_bytes()
        return PDFDocument(
            content=content_bytes,
            pages=pdf.num_pages,
            size=len(content_bytes),
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
        pdf = self._load(document)
        page_objs = pdf.page_numbers()
        if not page_ranges:
            # Split into individual pages
            page_ranges = [(i, i) for i in range(1, len(page_objs) + 1)]
        
        results: List[PDFDocument] = []
        for start, end in page_ranges:
            if start < 1 or end > len(page_objs) or start > end:
                raise PDFError(f"Invalid page range ({start}, {end}) for {len(page_objs)}-page document")
            part = pdf.with_pages(page_objs[start - 1:end])
            content = part.to_bytes()
            results.append(PDFDocument(
                content=content,
                pages=end - start + 1,
                size=len(content),
                title=document.title,
                metadata={**document.metadata, "page_range": [start, end]},
            ))
        return results
    
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
        pdf = self._load(document)
        # Permission bits (PDF 1.7 table 22); default allows everything.
        perms = -1
        if permissions:
            bits = 0xFFFFF0C0  # reserved bits set
            flag_bits = {"print": 1 << 2, "modify": 1 << 3, "copy": 1 << 4, "annotate": 1 << 5,
                         "fill_forms": 1 << 8, "extract": 1 << 9, "assemble": 1 << 10, "print_high": 1 << 11}
            for name, bit in flag_bits.items():
                if permissions.get(name, True):
                    bits |= bit
            perms = bits
        owner = (permissions or {}).get("owner_password") if isinstance(permissions, dict) else None
        content = pdf.encrypt_rc4(password, owner_password=owner if isinstance(owner, str) else None, permissions=perms)
        return PDFDocument(
            content=content,
            pages=pdf.num_pages,
            size=len(content),
            title=document.title,
            metadata={**document.metadata, "encrypted": True, "cipher": "RC4-128"},
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
        import zlib

        pdf = self._load(document)
        changed = False
        for num, body in list(pdf.objects.items()):
            spos = body.find(b"stream")
            if spos == -1 or b"/Filter" in body[:spos]:
                continue
            start = spos + len(b"stream")
            if body[start:start + 2] == b"\r\n":
                start += 2
            elif body[start:start + 1] == b"\n":
                start += 1
            end = body.rfind(b"endstream")
            payload = body[start:end].rstrip(b"\r\n")
            compressed = zlib.compress(payload, 9)
            if len(compressed) >= len(payload):
                continue
            head = re.sub(rb"/Length\s+\d+", b"/Length " + str(len(compressed)).encode() + b" /Filter /FlateDecode", body[:spos], count=1)
            pdf.objects[num] = head + b"stream\n" + compressed + b"\nendstream"
            changed = True
        if not changed:
            return document
        content = pdf.to_bytes()
        return PDFDocument(
            content=content,
            pages=pdf.num_pages,
            size=len(content),
            title=document.title,
            metadata={**document.metadata, "compressed": True, "original_size": document.size},
        )
    
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
    "TextRenderer",
    "html_to_text",
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
