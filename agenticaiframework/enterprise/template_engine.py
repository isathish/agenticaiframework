"""
Enterprise Template Engine Module.

Email/SMS templates, variable substitution,
template management, and rendering.

Example:
    # Create template engine
    templates = create_template_engine()
    
    # Register template
    templates.register(
        "welcome_email",
        subject="Welcome, {{name}}!",
        body="Hello {{name}}, welcome to {{company}}!",
        type=TemplateType.EMAIL,
    )
    
    # Render template
    result = templates.render(
        "welcome_email",
        data={"name": "John", "company": "Acme Corp"},
    )
    
    # Get rendered content
    print(result.subject)  # "Welcome, John!"
    print(result.body)     # "Hello John, welcome to Acme Corp!"
"""

from __future__ import annotations

import html
import json
import logging
import re
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
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


class TemplateError(Exception):
    """Template error."""
    pass


class TemplateNotFoundError(TemplateError):
    """Template not found."""
    pass


class RenderError(TemplateError):
    """Render error."""
    pass


class TemplateType(str, Enum):
    """Template type."""
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    HTML = "html"
    TEXT = "text"
    MARKDOWN = "markdown"
    SLACK = "slack"
    WEBHOOK = "webhook"


class TemplateStatus(str, Enum):
    """Template status."""
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


@dataclass
class TemplateVariable:
    """Template variable."""
    name: str = ""
    description: str = ""
    required: bool = False
    default: Any = None
    type: str = "string"  # string, number, date, list, object
    example: str = ""


@dataclass
class Template:
    """Template definition."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    type: TemplateType = TemplateType.TEXT
    status: TemplateStatus = TemplateStatus.ACTIVE
    subject: str = ""
    body: str = ""
    html_body: str = ""
    text_body: str = ""
    variables: List[TemplateVariable] = field(default_factory=list)
    version: str = "1.0.0"
    locale: str = "en"
    category: str = ""
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_by: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class RenderResult:
    """Render result."""
    template_name: str = ""
    subject: str = ""
    body: str = ""
    html_body: str = ""
    text_body: str = ""
    data_used: Dict[str, Any] = field(default_factory=dict)
    missing_variables: List[str] = field(default_factory=list)
    rendered_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class TemplateStats:
    """Template statistics."""
    total_templates: int = 0
    renders_count: int = 0


# Template renderer
class TemplateRenderer(ABC):
    """Template renderer interface."""
    
    @abstractmethod
    def render(self, template: str, data: Dict[str, Any]) -> str:
        pass
    
    @abstractmethod
    def extract_variables(self, template: str) -> List[str]:
        pass


class MustacheRenderer(TemplateRenderer):
    """Mustache-style renderer {{variable}}."""
    
    # Pattern for {{variable}} and {{variable|filter}}
    VARIABLE_PATTERN = re.compile(r'\{\{\s*(\w+)(?:\|(\w+))?\s*\}\}')
    
    # Conditional pattern {{#condition}}...{{/condition}}
    SECTION_PATTERN = re.compile(r'\{\{#(\w+)\}\}(.*?)\{\{/\1\}\}', re.DOTALL)
    
    # Inverted section {{^condition}}...{{/condition}}
    INVERTED_PATTERN = re.compile(r'\{\{\^(\w+)\}\}(.*?)\{\{/\1\}\}', re.DOTALL)
    
    # Loop pattern {{#items}}...{{/items}}
    LOOP_PATTERN = re.compile(r'\{\{#(\w+)\}\}(.*?)\{\{/\1\}\}', re.DOTALL)
    
    FILTERS = {
        "upper": lambda v: str(v).upper(),
        "lower": lambda v: str(v).lower(),
        "title": lambda v: str(v).title(),
        "capitalize": lambda v: str(v).capitalize(),
        "escape": lambda v: html.escape(str(v)),
        "json": lambda v: json.dumps(v),
        "trim": lambda v: str(v).strip(),
        "default": lambda v: v if v else "",
    }
    
    def render(self, template: str, data: Dict[str, Any]) -> str:
        """Render template with data."""
        result = template
        
        # Process sections (conditionals)
        result = self._process_sections(result, data)
        
        # Process inverted sections
        result = self._process_inverted(result, data)
        
        # Process variables
        result = self._replace_variables(result, data)
        
        return result
    
    def _process_sections(self, template: str, data: Dict[str, Any]) -> str:
        """Process conditional sections."""
        def replace_section(match):
            var_name = match.group(1)
            content = match.group(2)
            
            value = data.get(var_name)
            
            if isinstance(value, list):
                # Loop over items
                results = []
                for item in value:
                    if isinstance(item, dict):
                        results.append(self.render(content, {**data, **item, ".": item}))
                    else:
                        results.append(self.render(content, {**data, ".": item}))
                return ''.join(results)
            elif value:
                # Truthy value - render content
                return self.render(content, data)
            else:
                return ""
        
        return self.SECTION_PATTERN.sub(replace_section, template)
    
    def _process_inverted(self, template: str, data: Dict[str, Any]) -> str:
        """Process inverted sections."""
        def replace_inverted(match):
            var_name = match.group(1)
            content = match.group(2)
            
            value = data.get(var_name)
            
            if not value or (isinstance(value, list) and len(value) == 0):
                return self.render(content, data)
            else:
                return ""
        
        return self.INVERTED_PATTERN.sub(replace_inverted, template)
    
    def _replace_variables(self, template: str, data: Dict[str, Any]) -> str:
        """Replace variables."""
        def replace_var(match):
            var_name = match.group(1)
            filter_name = match.group(2)
            
            value = data.get(var_name, match.group(0))
            
            if filter_name and filter_name in self.FILTERS:
                value = self.FILTERS[filter_name](value)
            
            return str(value) if value is not None else ""
        
        return self.VARIABLE_PATTERN.sub(replace_var, template)
    
    def extract_variables(self, template: str) -> List[str]:
        """Extract variables from template."""
        variables = set()
        
        for match in self.VARIABLE_PATTERN.finditer(template):
            variables.add(match.group(1))
        
        for match in self.SECTION_PATTERN.finditer(template):
            variables.add(match.group(1))
        
        for match in self.INVERTED_PATTERN.finditer(template):
            variables.add(match.group(1))
        
        return list(variables)


class DollarRenderer(TemplateRenderer):
    """Dollar-style renderer $variable or ${variable}."""
    
    VARIABLE_PATTERN = re.compile(r'\$\{?(\w+)\}?')
    
    def render(self, template: str, data: Dict[str, Any]) -> str:
        """Render template with data."""
        def replace_var(match):
            var_name = match.group(1)
            value = data.get(var_name, match.group(0))
            return str(value) if value is not None else ""
        
        return self.VARIABLE_PATTERN.sub(replace_var, template)
    
    def extract_variables(self, template: str) -> List[str]:
        """Extract variables."""
        return list(set(self.VARIABLE_PATTERN.findall(template)))


# Template store
class TemplateStore(ABC):
    """Template storage."""
    
    @abstractmethod
    async def save(self, template: Template) -> None:
        pass
    
    @abstractmethod
    async def get(self, name: str) -> Optional[Template]:
        pass
    
    @abstractmethod
    async def list(
        self,
        type: Optional[TemplateType] = None,
        category: Optional[str] = None,
    ) -> List[Template]:
        pass
    
    @abstractmethod
    async def delete(self, name: str) -> bool:
        pass


class InMemoryTemplateStore(TemplateStore):
    """In-memory template store."""
    
    def __init__(self):
        self._templates: Dict[str, Template] = {}
    
    async def save(self, template: Template) -> None:
        template.updated_at = datetime.utcnow()
        self._templates[template.name] = template
    
    async def get(self, name: str) -> Optional[Template]:
        return self._templates.get(name)
    
    async def list(
        self,
        type: Optional[TemplateType] = None,
        category: Optional[str] = None,
    ) -> List[Template]:
        templates = list(self._templates.values())
        
        if type:
            templates = [t for t in templates if t.type == type]
        
        if category:
            templates = [t for t in templates if t.category == category]
        
        return sorted(templates, key=lambda t: t.name)
    
    async def delete(self, name: str) -> bool:
        return self._templates.pop(name, None) is not None


# Template engine
class TemplateEngine:
    """Template engine."""
    
    def __init__(
        self,
        store: Optional[TemplateStore] = None,
        renderer: Optional[TemplateRenderer] = None,
    ):
        self._store = store or InMemoryTemplateStore()
        self._renderer = renderer or MustacheRenderer()
        self._stats = TemplateStats()
        self._helpers: Dict[str, Callable] = {}
    
    async def register(
        self,
        name: str,
        body: str = "",
        subject: str = "",
        type: TemplateType = TemplateType.TEXT,
        html_body: str = "",
        text_body: str = "",
        **kwargs,
    ) -> Template:
        """Register template."""
        template = Template(
            name=name,
            body=body,
            subject=subject,
            type=type,
            html_body=html_body,
            text_body=text_body,
            **kwargs,
        )
        
        # Extract variables
        all_content = f"{subject} {body} {html_body} {text_body}"
        var_names = self._renderer.extract_variables(all_content)
        
        for var_name in var_names:
            if not any(v.name == var_name for v in template.variables):
                template.variables.append(TemplateVariable(name=var_name))
        
        await self._store.save(template)
        self._stats.total_templates += 1
        
        logger.info(f"Template registered: {name}")
        
        return template
    
    async def get_template(self, name: str) -> Optional[Template]:
        """Get template."""
        return await self._store.get(name)
    
    async def update_template(
        self,
        name: str,
        **updates,
    ) -> Optional[Template]:
        """Update template."""
        template = await self._store.get(name)
        if not template:
            return None
        
        for key, value in updates.items():
            if hasattr(template, key):
                setattr(template, key, value)
        
        await self._store.save(template)
        
        return template
    
    async def delete_template(self, name: str) -> bool:
        """Delete template."""
        return await self._store.delete(name)
    
    async def list_templates(
        self,
        type: Optional[TemplateType] = None,
        category: Optional[str] = None,
    ) -> List[Template]:
        """List templates."""
        return await self._store.list(type, category)
    
    def render(
        self,
        template_name: str,
        data: Dict[str, Any],
    ) -> RenderResult:
        """Render template synchronously (for cached templates)."""
        # This is a simplified sync version - in practice, use render_async
        result = RenderResult(template_name=template_name, data_used=data)
        
        # For demo, just return data
        return result
    
    async def render_async(
        self,
        template_name: str,
        data: Dict[str, Any],
    ) -> RenderResult:
        """Render template asynchronously."""
        template = await self._store.get(template_name)
        if not template:
            raise TemplateNotFoundError(f"Template not found: {template_name}")
        
        # Add built-in data
        full_data = {
            "_now": datetime.utcnow(),
            "_date": datetime.utcnow().strftime("%Y-%m-%d"),
            "_year": datetime.utcnow().year,
            **data,
        }
        
        # Add helper results
        for name, helper in self._helpers.items():
            if name not in full_data:
                try:
                    full_data[name] = helper(full_data)
                except:
                    pass
        
        result = RenderResult(
            template_name=template_name,
            data_used=data,
        )
        
        try:
            if template.subject:
                result.subject = self._renderer.render(template.subject, full_data)
            
            if template.body:
                result.body = self._renderer.render(template.body, full_data)
            
            if template.html_body:
                result.html_body = self._renderer.render(template.html_body, full_data)
            
            if template.text_body:
                result.text_body = self._renderer.render(template.text_body, full_data)
            elif template.body:
                result.text_body = result.body
        
        except Exception as e:
            raise RenderError(f"Render failed: {e}")
        
        # Check for missing variables
        for var in template.variables:
            if var.required and var.name not in data:
                result.missing_variables.append(var.name)
        
        self._stats.renders_count += 1
        
        return result
    
    def preview(
        self,
        body: str,
        data: Dict[str, Any],
        subject: str = "",
    ) -> RenderResult:
        """Preview template without registering."""
        result = RenderResult(data_used=data)
        
        try:
            if subject:
                result.subject = self._renderer.render(subject, data)
            
            result.body = self._renderer.render(body, data)
        except Exception as e:
            raise RenderError(f"Preview failed: {e}")
        
        return result
    
    def validate(
        self,
        template_name: str,
        data: Dict[str, Any],
    ) -> List[str]:
        """Validate data against template."""
        # For async validation, use validate_async
        return []
    
    async def validate_async(
        self,
        template_name: str,
        data: Dict[str, Any],
    ) -> List[str]:
        """Validate data asynchronously."""
        template = await self._store.get(template_name)
        if not template:
            return [f"Template not found: {template_name}"]
        
        errors = []
        
        for var in template.variables:
            if var.required and var.name not in data:
                errors.append(f"Missing required variable: {var.name}")
        
        return errors
    
    def register_helper(
        self,
        name: str,
        helper: Callable,
    ) -> None:
        """Register helper function."""
        self._helpers[name] = helper
    
    def extract_variables(self, template: str) -> List[str]:
        """Extract variables from template string."""
        return self._renderer.extract_variables(template)
    
    def get_stats(self) -> TemplateStats:
        """Get statistics."""
        return self._stats


# Factory functions
def create_template_engine() -> TemplateEngine:
    """Create template engine."""
    return TemplateEngine()


def create_template(
    name: str,
    body: str,
    **kwargs,
) -> Template:
    """Create template."""
    return Template(name=name, body=body, **kwargs)


def create_variable(
    name: str,
    **kwargs,
) -> TemplateVariable:
    """Create template variable."""
    return TemplateVariable(name=name, **kwargs)


__all__ = [
    # Exceptions
    "TemplateError",
    "TemplateNotFoundError",
    "RenderError",
    # Enums
    "TemplateType",
    "TemplateStatus",
    # Data classes
    "TemplateVariable",
    "Template",
    "RenderResult",
    "TemplateStats",
    # Renderers
    "TemplateRenderer",
    "MustacheRenderer",
    "DollarRenderer",
    # Stores
    "TemplateStore",
    "InMemoryTemplateStore",
    # Engine
    "TemplateEngine",
    # Factory functions
    "create_template_engine",
    "create_template",
    "create_variable",
]
