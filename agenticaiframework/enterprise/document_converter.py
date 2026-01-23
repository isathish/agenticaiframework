"""
Enterprise Document Converter Module.

Provides document format conversion between
DOCX, PDF, HTML, Markdown, and other formats.

Example:
    # Create document converter
    docs = create_document_converter()
    
    # Convert Markdown to HTML
    html = await docs.md_to_html(markdown_content)
    
    # Convert HTML to PDF
    pdf = await docs.html_to_pdf(html_content)
    
    # Convert DOCX to PDF
    pdf = await docs.convert(docx_bytes, from_format="docx", to_format="pdf")
    
    # Batch conversion
    results = await docs.batch_convert(files, to_format="pdf")
"""

from __future__ import annotations

import asyncio
import base64
import functools
import io
import json
import logging
import re
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


class ConversionError(Exception):
    """Document conversion error."""
    pass


class FormatError(ConversionError):
    """Format error."""
    pass


class UnsupportedFormatError(ConversionError):
    """Unsupported format error."""
    pass


class DocumentFormat(str, Enum):
    """Document formats."""
    # Text formats
    TXT = "txt"
    MARKDOWN = "md"
    HTML = "html"
    RTF = "rtf"
    # Office formats
    DOCX = "docx"
    DOC = "doc"
    ODT = "odt"
    # Presentation
    PPTX = "pptx"
    PPT = "ppt"
    ODP = "odp"
    # Spreadsheet
    XLSX = "xlsx"
    XLS = "xls"
    CSV = "csv"
    ODS = "ods"
    # PDF
    PDF = "pdf"
    # Other
    EPUB = "epub"
    LATEX = "tex"
    RST = "rst"
    JSON = "json"
    XML = "xml"


@dataclass
class DocumentInfo:
    """Document information."""
    format: DocumentFormat
    size_bytes: int = 0
    page_count: int = 0
    word_count: int = 0
    char_count: int = 0
    title: str = ""
    author: str = ""
    created_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversionOptions:
    """Conversion options."""
    from_format: Optional[DocumentFormat] = None
    to_format: DocumentFormat = DocumentFormat.PDF
    page_size: str = "A4"
    orientation: str = "portrait"
    margin_top: float = 1.0  # inches
    margin_bottom: float = 1.0
    margin_left: float = 1.0
    margin_right: float = 1.0
    header: Optional[str] = None
    footer: Optional[str] = None
    font_family: str = "Arial"
    font_size: int = 12
    embed_images: bool = True
    table_of_contents: bool = False
    syntax_highlighting: bool = True


@dataclass
class ConvertedDocument:
    """Converted document result."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: bytes = b""
    format: DocumentFormat = DocumentFormat.PDF
    original_format: Optional[DocumentFormat] = None
    size_bytes: int = 0
    page_count: int = 0
    converted_at: datetime = field(default_factory=datetime.utcnow)


# Format converters
class FormatConverter(ABC):
    """Abstract format converter."""
    
    @property
    @abstractmethod
    def supported_from(self) -> List[DocumentFormat]:
        """Formats this converter can read."""
        pass
    
    @property
    @abstractmethod
    def supported_to(self) -> List[DocumentFormat]:
        """Formats this converter can write."""
        pass
    
    @abstractmethod
    async def convert(
        self,
        data: bytes,
        from_format: DocumentFormat,
        to_format: DocumentFormat,
        options: ConversionOptions,
    ) -> bytes:
        """Convert document."""
        pass


class MarkdownConverter(FormatConverter):
    """Markdown converter."""
    
    @property
    def supported_from(self) -> List[DocumentFormat]:
        return [DocumentFormat.MARKDOWN]
    
    @property
    def supported_to(self) -> List[DocumentFormat]:
        return [DocumentFormat.HTML]
    
    async def convert(
        self,
        data: bytes,
        from_format: DocumentFormat,
        to_format: DocumentFormat,
        options: ConversionOptions,
    ) -> bytes:
        """Convert Markdown to HTML."""
        text = data.decode()
        
        # Basic Markdown to HTML conversion
        html = self._markdown_to_html(text, options)
        
        return html.encode()
    
    def _markdown_to_html(
        self,
        text: str,
        options: ConversionOptions,
    ) -> str:
        """Convert Markdown to HTML."""
        lines = text.split('\n')
        html_lines = []
        in_code_block = False
        in_list = False
        list_type = None
        
        for line in lines:
            # Code blocks
            if line.startswith('```'):
                if in_code_block:
                    html_lines.append('</code></pre>')
                    in_code_block = False
                else:
                    lang = line[3:].strip()
                    html_lines.append(f'<pre><code class="language-{lang}">')
                    in_code_block = True
                continue
            
            if in_code_block:
                html_lines.append(self._escape_html(line))
                continue
            
            # Headers
            if line.startswith('#'):
                level = len(line.split()[0])
                text_content = line[level:].strip()
                html_lines.append(f'<h{level}>{text_content}</h{level}>')
                continue
            
            # Bold and italic
            line = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', line)
            line = re.sub(r'\*(.+?)\*', r'<em>\1</em>', line)
            line = re.sub(r'__(.+?)__', r'<strong>\1</strong>', line)
            line = re.sub(r'_(.+?)_', r'<em>\1</em>', line)
            
            # Links
            line = re.sub(
                r'\[(.+?)\]\((.+?)\)',
                r'<a href="\2">\1</a>',
                line,
            )
            
            # Images
            line = re.sub(
                r'!\[(.+?)\]\((.+?)\)',
                r'<img src="\2" alt="\1">',
                line,
            )
            
            # Inline code
            line = re.sub(r'`(.+?)`', r'<code>\1</code>', line)
            
            # Lists
            if line.startswith('- ') or line.startswith('* '):
                if not in_list or list_type != 'ul':
                    if in_list:
                        html_lines.append(f'</{list_type}>')
                    html_lines.append('<ul>')
                    in_list = True
                    list_type = 'ul'
                html_lines.append(f'<li>{line[2:]}</li>')
                continue
            
            if re.match(r'^\d+\. ', line):
                if not in_list or list_type != 'ol':
                    if in_list:
                        html_lines.append(f'</{list_type}>')
                    html_lines.append('<ol>')
                    in_list = True
                    list_type = 'ol'
                text_content = re.sub(r'^\d+\. ', '', line)
                html_lines.append(f'<li>{text_content}</li>')
                continue
            
            # Close list if needed
            if in_list and line.strip() == '':
                html_lines.append(f'</{list_type}>')
                in_list = False
                list_type = None
            
            # Horizontal rule
            if line.strip() in ('---', '***', '___'):
                html_lines.append('<hr>')
                continue
            
            # Blockquote
            if line.startswith('> '):
                html_lines.append(f'<blockquote>{line[2:]}</blockquote>')
                continue
            
            # Paragraph
            if line.strip():
                html_lines.append(f'<p>{line}</p>')
            else:
                html_lines.append('')
        
        # Close any open list
        if in_list:
            html_lines.append(f'</{list_type}>')
        
        # Wrap in HTML document
        html_content = '\n'.join(html_lines)
        
        return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: {options.font_family}; font-size: {options.font_size}px; margin: 40px; }}
        pre {{ background: #f4f4f4; padding: 10px; border-radius: 5px; }}
        code {{ background: #f4f4f4; padding: 2px 5px; border-radius: 3px; }}
        blockquote {{ border-left: 3px solid #ccc; padding-left: 15px; color: #666; }}
    </style>
</head>
<body>
{html_content}
</body>
</html>'''
    
    def _escape_html(self, text: str) -> str:
        """Escape HTML characters."""
        return (
            text.replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
        )


class HTMLConverter(FormatConverter):
    """HTML converter."""
    
    @property
    def supported_from(self) -> List[DocumentFormat]:
        return [DocumentFormat.HTML]
    
    @property
    def supported_to(self) -> List[DocumentFormat]:
        return [DocumentFormat.TXT, DocumentFormat.MARKDOWN]
    
    async def convert(
        self,
        data: bytes,
        from_format: DocumentFormat,
        to_format: DocumentFormat,
        options: ConversionOptions,
    ) -> bytes:
        """Convert HTML."""
        text = data.decode()
        
        if to_format == DocumentFormat.TXT:
            result = self._html_to_text(text)
        elif to_format == DocumentFormat.MARKDOWN:
            result = self._html_to_markdown(text)
        else:
            raise UnsupportedFormatError(f"Cannot convert to {to_format}")
        
        return result.encode()
    
    def _html_to_text(self, html: str) -> str:
        """Convert HTML to plain text."""
        # Remove script and style
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        
        # Replace common elements
        text = re.sub(r'<br\s*/?>', '\n', text)
        text = re.sub(r'</p>', '\n\n', text)
        text = re.sub(r'</div>', '\n', text)
        text = re.sub(r'</h\d>', '\n\n', text)
        text = re.sub(r'</li>', '\n', text)
        
        # Remove tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Decode entities
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&quot;', '"')
        
        # Clean up whitespace
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = text.strip()
        
        return text
    
    def _html_to_markdown(self, html: str) -> str:
        """Convert HTML to Markdown."""
        text = html
        
        # Headers
        for i in range(1, 7):
            text = re.sub(
                rf'<h{i}[^>]*>(.*?)</h{i}>',
                rf'{"#" * i} \1\n',
                text,
                flags=re.DOTALL,
            )
        
        # Bold and italic
        text = re.sub(r'<strong[^>]*>(.*?)</strong>', r'**\1**', text)
        text = re.sub(r'<b[^>]*>(.*?)</b>', r'**\1**', text)
        text = re.sub(r'<em[^>]*>(.*?)</em>', r'*\1*', text)
        text = re.sub(r'<i[^>]*>(.*?)</i>', r'*\1*', text)
        
        # Links
        text = re.sub(
            r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
            r'[\2](\1)',
            text,
        )
        
        # Images
        text = re.sub(
            r'<img[^>]*src=["\']([^"\']+)["\'][^>]*alt=["\']([^"\']*)["\'][^>]*/?>',
            r'![\2](\1)',
            text,
        )
        
        # Lists
        text = re.sub(r'<li[^>]*>(.*?)</li>', r'- \1\n', text, flags=re.DOTALL)
        text = re.sub(r'</?[uo]l[^>]*>', '', text)
        
        # Code
        text = re.sub(r'<code[^>]*>(.*?)</code>', r'`\1`', text)
        text = re.sub(
            r'<pre[^>]*><code[^>]*>(.*?)</code></pre>',
            r'```\n\1\n```',
            text,
            flags=re.DOTALL,
        )
        
        # Blockquote
        text = re.sub(
            r'<blockquote[^>]*>(.*?)</blockquote>',
            lambda m: '> ' + m.group(1).replace('\n', '\n> '),
            text,
            flags=re.DOTALL,
        )
        
        # Paragraphs and line breaks
        text = re.sub(r'<br\s*/?>', '\n', text)
        text = re.sub(r'<p[^>]*>(.*?)</p>', r'\1\n\n', text, flags=re.DOTALL)
        
        # Remove remaining tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Decode entities
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        
        # Clean up
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = text.strip()
        
        return text


class MockPDFConverter(FormatConverter):
    """Mock PDF converter for testing."""
    
    @property
    def supported_from(self) -> List[DocumentFormat]:
        return [DocumentFormat.HTML, DocumentFormat.MARKDOWN, DocumentFormat.TXT]
    
    @property
    def supported_to(self) -> List[DocumentFormat]:
        return [DocumentFormat.PDF]
    
    async def convert(
        self,
        data: bytes,
        from_format: DocumentFormat,
        to_format: DocumentFormat,
        options: ConversionOptions,
    ) -> bytes:
        """Mock PDF conversion."""
        info = {
            "conversion": f"{from_format.value} -> {to_format.value}",
            "page_size": options.page_size,
            "orientation": options.orientation,
            "original_size": len(data),
            "converted_at": datetime.utcnow().isoformat(),
        }
        return json.dumps(info, indent=2).encode()


class DocumentConverter:
    """
    Document conversion service.
    """
    
    def __init__(
        self,
        converters: Optional[List[FormatConverter]] = None,
    ):
        self._converters = converters or [
            MarkdownConverter(),
            HTMLConverter(),
            MockPDFConverter(),
        ]
    
    def _get_converter(
        self,
        from_format: DocumentFormat,
        to_format: DocumentFormat,
    ) -> Optional[FormatConverter]:
        """Find converter for formats."""
        for converter in self._converters:
            if (
                from_format in converter.supported_from
                and to_format in converter.supported_to
            ):
                return converter
        return None
    
    def can_convert(
        self,
        from_format: DocumentFormat,
        to_format: DocumentFormat,
    ) -> bool:
        """Check if conversion is supported."""
        return self._get_converter(from_format, to_format) is not None
    
    def get_supported_conversions(self) -> List[Tuple[DocumentFormat, DocumentFormat]]:
        """Get list of supported conversions."""
        conversions = []
        for converter in self._converters:
            for from_fmt in converter.supported_from:
                for to_fmt in converter.supported_to:
                    conversions.append((from_fmt, to_fmt))
        return conversions
    
    async def convert(
        self,
        data: bytes,
        from_format: Optional[Union[str, DocumentFormat]] = None,
        to_format: Union[str, DocumentFormat] = DocumentFormat.PDF,
        options: Optional[ConversionOptions] = None,
    ) -> ConvertedDocument:
        """
        Convert document.
        
        Args:
            data: Document bytes
            from_format: Source format (auto-detect if None)
            to_format: Target format
            options: Conversion options
            
        Returns:
            Converted document
        """
        # Normalize formats
        if isinstance(from_format, str):
            from_format = DocumentFormat(from_format)
        if isinstance(to_format, str):
            to_format = DocumentFormat(to_format)
        
        # Auto-detect format if not provided
        if from_format is None:
            from_format = self._detect_format(data)
        
        options = options or ConversionOptions(
            from_format=from_format,
            to_format=to_format,
        )
        
        # Find converter
        converter = self._get_converter(from_format, to_format)
        
        if not converter:
            # Try multi-step conversion
            content = await self._multi_step_convert(
                data, from_format, to_format, options
            )
        else:
            content = await converter.convert(
                data, from_format, to_format, options
            )
        
        return ConvertedDocument(
            content=content,
            format=to_format,
            original_format=from_format,
            size_bytes=len(content),
        )
    
    async def _multi_step_convert(
        self,
        data: bytes,
        from_format: DocumentFormat,
        to_format: DocumentFormat,
        options: ConversionOptions,
    ) -> bytes:
        """Try multi-step conversion."""
        # Try converting through HTML
        if from_format == DocumentFormat.MARKDOWN and to_format == DocumentFormat.PDF:
            # MD -> HTML -> PDF
            html = await self.md_to_html(data.decode())
            return (await self.html_to_pdf(html)).content
        
        raise UnsupportedFormatError(
            f"Cannot convert from {from_format} to {to_format}"
        )
    
    def _detect_format(self, data: bytes) -> DocumentFormat:
        """Detect document format."""
        # Try to decode as text
        try:
            text = data.decode()
            
            # Check for HTML
            if '<html' in text.lower() or '<!doctype html' in text.lower():
                return DocumentFormat.HTML
            
            # Check for Markdown indicators
            if re.search(r'^#{1,6}\s', text, re.MULTILINE):
                return DocumentFormat.MARKDOWN
            
            return DocumentFormat.TXT
            
        except:
            pass
        
        # Check magic bytes
        if data.startswith(b'%PDF'):
            return DocumentFormat.PDF
        
        if data.startswith(b'PK'):
            # Could be DOCX, XLSX, PPTX
            return DocumentFormat.DOCX
        
        return DocumentFormat.TXT
    
    # Convenience methods
    async def md_to_html(
        self,
        markdown: str,
        options: Optional[ConversionOptions] = None,
    ) -> str:
        """Convert Markdown to HTML."""
        result = await self.convert(
            markdown.encode(),
            from_format=DocumentFormat.MARKDOWN,
            to_format=DocumentFormat.HTML,
            options=options,
        )
        return result.content.decode()
    
    async def html_to_pdf(
        self,
        html: str,
        options: Optional[ConversionOptions] = None,
    ) -> ConvertedDocument:
        """Convert HTML to PDF."""
        return await self.convert(
            html.encode(),
            from_format=DocumentFormat.HTML,
            to_format=DocumentFormat.PDF,
            options=options,
        )
    
    async def html_to_text(
        self,
        html: str,
    ) -> str:
        """Convert HTML to plain text."""
        result = await self.convert(
            html.encode(),
            from_format=DocumentFormat.HTML,
            to_format=DocumentFormat.TXT,
        )
        return result.content.decode()
    
    async def html_to_md(
        self,
        html: str,
    ) -> str:
        """Convert HTML to Markdown."""
        result = await self.convert(
            html.encode(),
            from_format=DocumentFormat.HTML,
            to_format=DocumentFormat.MARKDOWN,
        )
        return result.content.decode()
    
    async def md_to_pdf(
        self,
        markdown: str,
        options: Optional[ConversionOptions] = None,
    ) -> ConvertedDocument:
        """Convert Markdown to PDF."""
        # First convert to HTML
        html = await self.md_to_html(markdown, options)
        
        # Then convert to PDF
        return await self.html_to_pdf(html, options)
    
    async def batch_convert(
        self,
        files: List[Tuple[str, bytes]],
        to_format: DocumentFormat,
        options: Optional[ConversionOptions] = None,
    ) -> List[ConvertedDocument]:
        """
        Batch convert files.
        
        Args:
            files: List of (filename, content) tuples
            to_format: Target format
            options: Conversion options
            
        Returns:
            List of converted documents
        """
        tasks = []
        
        for filename, content in files:
            # Detect format from extension
            ext = Path(filename).suffix.lstrip('.')
            try:
                from_format = DocumentFormat(ext)
            except ValueError:
                from_format = None
            
            tasks.append(
                self.convert(content, from_format, to_format, options)
            )
        
        return await asyncio.gather(*tasks, return_exceptions=True)
    
    async def save(
        self,
        document: ConvertedDocument,
        path: Union[str, Path],
    ) -> Path:
        """Save converted document."""
        path = Path(path)
        path.write_bytes(document.content)
        return path


# Factory functions
def create_document_converter(
    converters: Optional[List[FormatConverter]] = None,
) -> DocumentConverter:
    """Create document converter."""
    return DocumentConverter(converters)


def create_conversion_options(
    to_format: DocumentFormat = DocumentFormat.PDF,
    page_size: str = "A4",
    **kwargs,
) -> ConversionOptions:
    """Create conversion options."""
    return ConversionOptions(to_format=to_format, page_size=page_size, **kwargs)


__all__ = [
    # Exceptions
    "ConversionError",
    "FormatError",
    "UnsupportedFormatError",
    # Enums
    "DocumentFormat",
    # Data classes
    "DocumentInfo",
    "ConversionOptions",
    "ConvertedDocument",
    # Converters
    "FormatConverter",
    "MarkdownConverter",
    "HTMLConverter",
    "MockPDFConverter",
    # Service
    "DocumentConverter",
    # Factory functions
    "create_document_converter",
    "create_conversion_options",
]
