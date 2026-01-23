"""
Enterprise Document Generator Module.

PDF/Word generation, templates, mail merge,
and document management.

Example:
    # Create document generator
    docs = create_document_generator()
    
    # Register template
    docs.register_template(
        "invoice",
        "<html><body>Invoice {{invoice_number}}</body></html>",
        format="html",
    )
    
    # Generate document
    doc = await docs.generate(
        template_name="invoice",
        data={"invoice_number": "INV-001", "total": 100.00},
        output_format="pdf",
    )
    
    # Mail merge
    results = await docs.mail_merge(
        template_name="letter",
        records=[{"name": "John"}, {"name": "Jane"}],
    )
"""

from __future__ import annotations

import base64
import hashlib
import io
import logging
import re
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from string import Template
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


class DocumentError(Exception):
    """Document error."""
    pass


class TemplateNotFoundError(DocumentError):
    """Template not found."""
    pass


class GenerationError(DocumentError):
    """Generation error."""
    pass


class OutputFormat(str, Enum):
    """Output format."""
    PDF = "pdf"
    HTML = "html"
    MARKDOWN = "markdown"
    TEXT = "text"
    JSON = "json"


class TemplateFormat(str, Enum):
    """Template format."""
    HTML = "html"
    MARKDOWN = "markdown"
    TEXT = "text"
    JINJA2 = "jinja2"


class DocumentStatus(str, Enum):
    """Document status."""
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class DocumentTemplate:
    """Document template."""
    name: str = ""
    content: str = ""
    format: TemplateFormat = TemplateFormat.HTML
    description: str = ""
    variables: List[str] = field(default_factory=list)
    styles: str = ""
    header: str = ""
    footer: str = ""
    page_size: str = "A4"
    orientation: str = "portrait"
    margins: Dict[str, float] = field(default_factory=lambda: {
        "top": 1.0, "right": 1.0, "bottom": 1.0, "left": 1.0
    })
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class GeneratedDocument:
    """Generated document."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    template_name: str = ""
    status: DocumentStatus = DocumentStatus.PENDING
    output_format: OutputFormat = OutputFormat.HTML
    content: bytes = b""
    content_base64: str = ""
    filename: str = ""
    size_bytes: int = 0
    checksum: str = ""
    data_used: Dict[str, Any] = field(default_factory=dict)
    error_message: str = ""
    generated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MailMergeResult:
    """Mail merge result."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    template_name: str = ""
    total_records: int = 0
    success_count: int = 0
    failure_count: int = 0
    documents: List[GeneratedDocument] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


@dataclass
class DocumentStats:
    """Document statistics."""
    templates_count: int = 0
    documents_generated: int = 0
    total_size_bytes: int = 0


# Template engine
class TemplateEngine(ABC):
    """Template engine."""
    
    @abstractmethod
    def render(self, template: str, data: Dict[str, Any]) -> str:
        pass
    
    @abstractmethod
    def extract_variables(self, template: str) -> List[str]:
        pass


class SimpleTemplateEngine(TemplateEngine):
    """Simple template engine using {{variable}} syntax."""
    
    VARIABLE_PATTERN = re.compile(r'\{\{\s*(\w+)\s*\}\}')
    
    def render(self, template: str, data: Dict[str, Any]) -> str:
        """Render template with data."""
        def replace_var(match):
            var_name = match.group(1)
            value = data.get(var_name, match.group(0))
            return str(value) if value is not None else ""
        
        return self.VARIABLE_PATTERN.sub(replace_var, template)
    
    def extract_variables(self, template: str) -> List[str]:
        """Extract variables from template."""
        return list(set(self.VARIABLE_PATTERN.findall(template)))


class PythonTemplateEngine(TemplateEngine):
    """Python string.Template engine using $variable syntax."""
    
    VARIABLE_PATTERN = re.compile(r'\$\{?(\w+)\}?')
    
    def render(self, template: str, data: Dict[str, Any]) -> str:
        """Render template with data."""
        try:
            return Template(template).safe_substitute(data)
        except Exception as e:
            logger.error(f"Template render error: {e}")
            return template
    
    def extract_variables(self, template: str) -> List[str]:
        """Extract variables from template."""
        return list(set(self.VARIABLE_PATTERN.findall(template)))


# PDF generator
class PDFGenerator(ABC):
    """PDF generator interface."""
    
    @abstractmethod
    async def generate(
        self,
        html: str,
        options: Dict[str, Any] = None,
    ) -> bytes:
        pass


class MockPDFGenerator(PDFGenerator):
    """Mock PDF generator for testing."""
    
    async def generate(
        self,
        html: str,
        options: Dict[str, Any] = None,
    ) -> bytes:
        """Generate mock PDF."""
        # Return a minimal valid PDF structure
        pdf_content = f"""
%PDF-1.4
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
trailer
<< /Size 4 /Root 1 0 R >>
startxref
%%EOF
""".strip()
        return pdf_content.encode('utf-8')


# Document store
class DocumentStore(ABC):
    """Document storage."""
    
    @abstractmethod
    async def save(self, document: GeneratedDocument) -> None:
        pass
    
    @abstractmethod
    async def get(self, document_id: str) -> Optional[GeneratedDocument]:
        pass
    
    @abstractmethod
    async def list(
        self,
        template_name: Optional[str] = None,
        limit: int = 100,
    ) -> List[GeneratedDocument]:
        pass


class InMemoryDocumentStore(DocumentStore):
    """In-memory document store."""
    
    def __init__(self):
        self._documents: Dict[str, GeneratedDocument] = {}
    
    async def save(self, document: GeneratedDocument) -> None:
        self._documents[document.id] = document
    
    async def get(self, document_id: str) -> Optional[GeneratedDocument]:
        return self._documents.get(document_id)
    
    async def list(
        self,
        template_name: Optional[str] = None,
        limit: int = 100,
    ) -> List[GeneratedDocument]:
        results = list(self._documents.values())
        
        if template_name:
            results = [d for d in results if d.template_name == template_name]
        
        return sorted(results, key=lambda d: d.generated_at, reverse=True)[:limit]


# Document generator
class DocumentGenerator:
    """Document generator."""
    
    def __init__(
        self,
        store: Optional[DocumentStore] = None,
        pdf_generator: Optional[PDFGenerator] = None,
        template_engine: Optional[TemplateEngine] = None,
    ):
        self._store = store or InMemoryDocumentStore()
        self._pdf = pdf_generator or MockPDFGenerator()
        self._engine = template_engine or SimpleTemplateEngine()
        self._templates: Dict[str, DocumentTemplate] = {}
        self._stats = DocumentStats()
    
    def register_template(
        self,
        name: str,
        content: str,
        format: TemplateFormat = TemplateFormat.HTML,
        **kwargs,
    ) -> DocumentTemplate:
        """Register template."""
        template = DocumentTemplate(
            name=name,
            content=content,
            format=format,
            **kwargs,
        )
        
        # Extract variables
        template.variables = self._engine.extract_variables(content)
        
        self._templates[name] = template
        self._stats.templates_count += 1
        
        logger.info(f"Template registered: {name}")
        
        return template
    
    def get_template(self, name: str) -> Optional[DocumentTemplate]:
        """Get template."""
        return self._templates.get(name)
    
    def list_templates(self) -> List[DocumentTemplate]:
        """List templates."""
        return list(self._templates.values())
    
    async def generate(
        self,
        template_name: str,
        data: Dict[str, Any],
        output_format: OutputFormat = OutputFormat.HTML,
        filename: Optional[str] = None,
    ) -> GeneratedDocument:
        """Generate document."""
        template = self._templates.get(template_name)
        if not template:
            raise TemplateNotFoundError(f"Template not found: {template_name}")
        
        document = GeneratedDocument(
            template_name=template_name,
            output_format=output_format,
            data_used=data,
            status=DocumentStatus.GENERATING,
        )
        
        try:
            # Render template
            rendered = self._render_template(template, data)
            
            # Convert to output format
            if output_format == OutputFormat.PDF:
                content = await self._generate_pdf(rendered, template)
            elif output_format == OutputFormat.HTML:
                content = self._wrap_html(rendered, template).encode('utf-8')
            elif output_format == OutputFormat.MARKDOWN:
                content = rendered.encode('utf-8')
            elif output_format == OutputFormat.TEXT:
                content = self._strip_html(rendered).encode('utf-8')
            else:
                content = rendered.encode('utf-8')
            
            document.content = content
            document.content_base64 = base64.b64encode(content).decode('utf-8')
            document.size_bytes = len(content)
            document.checksum = hashlib.sha256(content).hexdigest()
            document.status = DocumentStatus.COMPLETED
            
            # Generate filename
            ext = output_format.value
            document.filename = filename or f"{template_name}_{document.id[:8]}.{ext}"
        
        except Exception as e:
            document.status = DocumentStatus.FAILED
            document.error_message = str(e)
            logger.error(f"Document generation failed: {e}")
        
        await self._store.save(document)
        
        self._stats.documents_generated += 1
        self._stats.total_size_bytes += document.size_bytes
        
        logger.info(f"Document generated: {document.filename}")
        
        return document
    
    def _render_template(
        self,
        template: DocumentTemplate,
        data: Dict[str, Any],
    ) -> str:
        """Render template with data."""
        # Add default data
        full_data = {
            "_date": datetime.utcnow().strftime("%Y-%m-%d"),
            "_datetime": datetime.utcnow().isoformat(),
            "_timestamp": int(datetime.utcnow().timestamp()),
            **data,
        }
        
        return self._engine.render(template.content, full_data)
    
    def _wrap_html(
        self,
        content: str,
        template: DocumentTemplate,
    ) -> str:
        """Wrap content in HTML document."""
        styles = template.styles or ""
        header = self._engine.render(template.header, {}) if template.header else ""
        footer = self._engine.render(template.footer, {}) if template.footer else ""
        
        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>{styles}</style>
</head>
<body>
    {header}
    {content}
    {footer}
</body>
</html>"""
    
    def _strip_html(self, html: str) -> str:
        """Strip HTML tags."""
        return re.sub(r'<[^>]+>', '', html)
    
    async def _generate_pdf(
        self,
        html: str,
        template: DocumentTemplate,
    ) -> bytes:
        """Generate PDF from HTML."""
        wrapped = self._wrap_html(html, template)
        
        options = {
            "page_size": template.page_size,
            "orientation": template.orientation,
            "margins": template.margins,
        }
        
        return await self._pdf.generate(wrapped, options)
    
    async def mail_merge(
        self,
        template_name: str,
        records: List[Dict[str, Any]],
        output_format: OutputFormat = OutputFormat.HTML,
    ) -> MailMergeResult:
        """Perform mail merge."""
        result = MailMergeResult(
            template_name=template_name,
            total_records=len(records),
        )
        
        for i, record in enumerate(records):
            try:
                doc = await self.generate(
                    template_name=template_name,
                    data=record,
                    output_format=output_format,
                )
                
                if doc.status == DocumentStatus.COMPLETED:
                    result.success_count += 1
                    result.documents.append(doc)
                else:
                    result.failure_count += 1
                    result.errors.append(f"Record {i}: {doc.error_message}")
            
            except Exception as e:
                result.failure_count += 1
                result.errors.append(f"Record {i}: {str(e)}")
        
        result.completed_at = datetime.utcnow()
        
        logger.info(f"Mail merge completed: {result.success_count}/{result.total_records} success")
        
        return result
    
    async def get_document(
        self,
        document_id: str,
    ) -> Optional[GeneratedDocument]:
        """Get document."""
        return await self._store.get(document_id)
    
    async def list_documents(
        self,
        template_name: Optional[str] = None,
        limit: int = 100,
    ) -> List[GeneratedDocument]:
        """List documents."""
        return await self._store.list(template_name, limit)
    
    def preview(
        self,
        template_name: str,
        data: Dict[str, Any],
    ) -> str:
        """Preview rendered template."""
        template = self._templates.get(template_name)
        if not template:
            return ""
        
        return self._render_template(template, data)
    
    def validate_data(
        self,
        template_name: str,
        data: Dict[str, Any],
    ) -> List[str]:
        """Validate data against template variables."""
        template = self._templates.get(template_name)
        if not template:
            return [f"Template not found: {template_name}"]
        
        missing = []
        for var in template.variables:
            if var not in data and not var.startswith("_"):
                missing.append(f"Missing variable: {var}")
        
        return missing
    
    def get_stats(self) -> DocumentStats:
        """Get statistics."""
        return self._stats


# Factory functions
def create_document_generator() -> DocumentGenerator:
    """Create document generator."""
    return DocumentGenerator()


def create_template(
    name: str,
    content: str,
    **kwargs,
) -> DocumentTemplate:
    """Create template."""
    return DocumentTemplate(name=name, content=content, **kwargs)


__all__ = [
    # Exceptions
    "DocumentError",
    "TemplateNotFoundError",
    "GenerationError",
    # Enums
    "OutputFormat",
    "TemplateFormat",
    "DocumentStatus",
    # Data classes
    "DocumentTemplate",
    "GeneratedDocument",
    "MailMergeResult",
    "DocumentStats",
    # Template engines
    "TemplateEngine",
    "SimpleTemplateEngine",
    "PythonTemplateEngine",
    # PDF generator
    "PDFGenerator",
    "MockPDFGenerator",
    # Stores
    "DocumentStore",
    "InMemoryDocumentStore",
    # Generator
    "DocumentGenerator",
    # Factory functions
    "create_document_generator",
    "create_template",
]
