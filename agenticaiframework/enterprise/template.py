"""
Enterprise Template Module.

Provides template engine capabilities including Jinja-like
templates, variable substitution, and template rendering.

Example:
    # Create template engine
    engine = create_template_engine()
    
    # Render template
    result = engine.render(
        "Hello {{ name }}!",
        {"name": "World"}
    )
    
    # Load from file
    template = await engine.load("email.html")
    html = template.render(user=user, items=items)
    
    # With filters
    engine.add_filter("upper", str.upper)
    result = engine.render("{{ name | upper }}", {"name": "john"})
    # "JOHN"
    
    # Template inheritance
    @template("base.html")
    def render_page(context: dict) -> str:
        ...
"""

from __future__ import annotations

import asyncio
import html
import logging
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Pattern,
    Set,
    Tuple,
    TypeVar,
    Union,
)

logger = logging.getLogger(__name__)

T = TypeVar('T')


class TemplateError(Exception):
    """Template error."""
    pass


class RenderError(TemplateError):
    """Render error."""
    pass


class SyntaxError(TemplateError):
    """Template syntax error."""
    pass


class TemplateNotFoundError(TemplateError):
    """Template not found."""
    pass


@dataclass
class TemplateConfig:
    """Template configuration."""
    variable_start: str = "{{"
    variable_end: str = "}}"
    block_start: str = "{%"
    block_end: str = "%}"
    comment_start: str = "{#"
    comment_end: str = "#}"
    auto_escape: bool = True
    strict_undefined: bool = False
    trim_blocks: bool = False
    cache_enabled: bool = True


@dataclass
class RenderResult:
    """Render result."""
    content: str
    template_name: Optional[str] = None
    render_time_ms: float = 0.0
    variables_used: Set[str] = field(default_factory=set)


class Template:
    """
    A compiled template ready for rendering.
    """
    
    def __init__(
        self,
        source: str,
        name: Optional[str] = None,
        config: Optional[TemplateConfig] = None,
        filters: Optional[Dict[str, Callable]] = None,
    ):
        self._source = source
        self._name = name
        self._config = config or TemplateConfig()
        self._filters = filters or {}
        self._compiled: Optional[List[Tuple[str, Any]]] = None
        
        self._compile()
    
    def _compile(self) -> None:
        """Compile template into tokens."""
        self._compiled = []
        
        # Simple tokenization
        pattern = self._build_pattern()
        pos = 0
        
        for match in re.finditer(pattern, self._source):
            # Add literal text before match
            if match.start() > pos:
                literal = self._source[pos:match.start()]
                if literal:
                    self._compiled.append(('literal', literal))
            
            groups = match.groups()
            
            if groups[0]:  # Variable
                self._compiled.append(('variable', groups[0].strip()))
            elif groups[1]:  # Block
                self._compiled.append(('block', groups[1].strip()))
            elif groups[2]:  # Comment
                pass  # Ignore comments
            
            pos = match.end()
        
        # Add remaining literal
        if pos < len(self._source):
            self._compiled.append(('literal', self._source[pos:]))
    
    def _build_pattern(self) -> Pattern:
        """Build regex pattern for tokenization."""
        vs = re.escape(self._config.variable_start)
        ve = re.escape(self._config.variable_end)
        bs = re.escape(self._config.block_start)
        be = re.escape(self._config.block_end)
        cs = re.escape(self._config.comment_start)
        ce = re.escape(self._config.comment_end)
        
        return re.compile(
            f'{vs}\\s*(.+?)\\s*{ve}|'
            f'{bs}\\s*(.+?)\\s*{be}|'
            f'{cs}\\s*(.+?)\\s*{ce}',
            re.DOTALL
        )
    
    def render(
        self,
        context: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> str:
        """Render the template."""
        import time
        start = time.time()
        
        ctx = context or {}
        ctx.update(kwargs)
        
        parts = []
        variables_used = set()
        
        # Simple block handling
        skip_until = None
        
        for token_type, token_value in self._compiled:
            if skip_until:
                if token_type == 'block' and token_value.startswith(skip_until):
                    skip_until = None
                continue
            
            if token_type == 'literal':
                parts.append(token_value)
            
            elif token_type == 'variable':
                value = self._evaluate_expression(token_value, ctx)
                variables_used.add(token_value.split('|')[0].strip())
                
                if self._config.auto_escape and isinstance(value, str):
                    value = html.escape(value)
                
                parts.append(str(value) if value is not None else '')
            
            elif token_type == 'block':
                if token_value.startswith('if '):
                    condition = token_value[3:].strip()
                    if not self._evaluate_condition(condition, ctx):
                        skip_until = 'endif'
                
                elif token_value.startswith('for '):
                    # Basic for loop handling
                    match = re.match(r'for\s+(\w+)\s+in\s+(.+)', token_value)
                    if match:
                        var_name, iterable_expr = match.groups()
                        iterable = self._evaluate_expression(iterable_expr.strip(), ctx)
                        # Note: Full for loop requires more complex state management
        
        render_time = (time.time() - start) * 1000
        
        return ''.join(parts)
    
    def _evaluate_expression(
        self,
        expr: str,
        context: Dict[str, Any],
    ) -> Any:
        """Evaluate a template expression."""
        # Handle filters (e.g., "name | upper")
        if '|' in expr:
            parts = expr.split('|')
            value = self._evaluate_expression(parts[0].strip(), context)
            
            for filter_expr in parts[1:]:
                filter_name = filter_expr.strip()
                
                # Check for filter arguments
                if '(' in filter_name:
                    match = re.match(r'(\w+)\((.+)\)', filter_name)
                    if match:
                        filter_name = match.group(1)
                        # Parse arguments (simplified)
                
                if filter_name in self._filters:
                    value = self._filters[filter_name](value)
            
            return value
        
        # Handle dot notation (e.g., "user.name")
        parts = expr.split('.')
        value = context
        
        for part in parts:
            # Handle array access (e.g., "items[0]")
            match = re.match(r'(\w+)\[(\d+)\]', part)
            if match:
                key, index = match.groups()
                value = value.get(key, []) if isinstance(value, dict) else getattr(value, key, [])
                value = value[int(index)] if len(value) > int(index) else None
            else:
                if isinstance(value, dict):
                    value = value.get(part)
                else:
                    value = getattr(value, part, None)
            
            if value is None:
                if self._config.strict_undefined:
                    raise RenderError(f"Undefined variable: {expr}")
                return None
        
        return value
    
    def _evaluate_condition(
        self,
        condition: str,
        context: Dict[str, Any],
    ) -> bool:
        """Evaluate a condition."""
        # Simple truthy check
        value = self._evaluate_expression(condition, context)
        return bool(value)
    
    @property
    def source(self) -> str:
        """Get template source."""
        return self._source
    
    @property
    def name(self) -> Optional[str]:
        """Get template name."""
        return self._name


class TemplateLoader(ABC):
    """Abstract template loader."""
    
    @abstractmethod
    async def load(self, name: str) -> str:
        """Load template source by name."""
        pass


class FileSystemLoader(TemplateLoader):
    """Load templates from filesystem."""
    
    def __init__(
        self,
        search_paths: List[str],
        encoding: str = "utf-8",
    ):
        self._paths = [Path(p) for p in search_paths]
        self._encoding = encoding
    
    async def load(self, name: str) -> str:
        """Load template from filesystem."""
        for base_path in self._paths:
            template_path = base_path / name
            
            if template_path.exists():
                return template_path.read_text(encoding=self._encoding)
        
        raise TemplateNotFoundError(f"Template not found: {name}")
    
    def load_sync(self, name: str) -> str:
        """Synchronous load."""
        for base_path in self._paths:
            template_path = base_path / name
            
            if template_path.exists():
                return template_path.read_text(encoding=self._encoding)
        
        raise TemplateNotFoundError(f"Template not found: {name}")


class DictLoader(TemplateLoader):
    """Load templates from dictionary."""
    
    def __init__(self, templates: Dict[str, str]):
        self._templates = templates
    
    async def load(self, name: str) -> str:
        """Load template from dict."""
        if name in self._templates:
            return self._templates[name]
        raise TemplateNotFoundError(f"Template not found: {name}")


class TemplateEngine:
    """
    Main template engine.
    """
    
    def __init__(
        self,
        config: Optional[TemplateConfig] = None,
        loader: Optional[TemplateLoader] = None,
    ):
        self._config = config or TemplateConfig()
        self._loader = loader
        self._filters: Dict[str, Callable] = {}
        self._globals: Dict[str, Any] = {}
        self._cache: Dict[str, Template] = {}
        
        # Register built-in filters
        self._register_builtin_filters()
    
    def _register_builtin_filters(self) -> None:
        """Register built-in filters."""
        self._filters.update({
            'upper': str.upper,
            'lower': str.lower,
            'title': str.title,
            'capitalize': str.capitalize,
            'strip': str.strip,
            'trim': str.strip,
            'length': len,
            'reverse': lambda x: x[::-1] if isinstance(x, (str, list)) else x,
            'first': lambda x: x[0] if x else None,
            'last': lambda x: x[-1] if x else None,
            'join': lambda x, sep=', ': sep.join(str(i) for i in x),
            'default': lambda x, d='': x if x else d,
            'escape': html.escape,
            'safe': lambda x: x,  # Mark as safe (no escaping)
            'int': int,
            'float': float,
            'string': str,
            'list': list,
            'sort': sorted,
            'unique': lambda x: list(dict.fromkeys(x)),
            'abs': abs,
            'round': round,
            'sum': sum,
            'min': min,
            'max': max,
            'date': lambda x, fmt='%Y-%m-%d': x.strftime(fmt) if hasattr(x, 'strftime') else x,
        })
    
    def add_filter(
        self,
        name: str,
        func: Callable,
    ) -> "TemplateEngine":
        """Add a custom filter."""
        self._filters[name] = func
        return self
    
    def add_global(
        self,
        name: str,
        value: Any,
    ) -> "TemplateEngine":
        """Add a global variable."""
        self._globals[name] = value
        return self
    
    def render(
        self,
        source: str,
        context: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> str:
        """Render a template string."""
        template = Template(
            source,
            config=self._config,
            filters=self._filters,
        )
        
        ctx = dict(self._globals)
        if context:
            ctx.update(context)
        ctx.update(kwargs)
        
        return template.render(ctx)
    
    async def load(self, name: str) -> Template:
        """Load and compile a template."""
        if self._config.cache_enabled and name in self._cache:
            return self._cache[name]
        
        if not self._loader:
            raise TemplateError("No loader configured")
        
        source = await self._loader.load(name)
        
        template = Template(
            source,
            name=name,
            config=self._config,
            filters=self._filters,
        )
        
        if self._config.cache_enabled:
            self._cache[name] = template
        
        return template
    
    async def render_template(
        self,
        name: str,
        context: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> str:
        """Load and render a template by name."""
        template = await self.load(name)
        
        ctx = dict(self._globals)
        if context:
            ctx.update(context)
        ctx.update(kwargs)
        
        return template.render(ctx)
    
    def clear_cache(self) -> None:
        """Clear template cache."""
        self._cache.clear()


class StringTemplate:
    """
    Simple string template using Python's format.
    """
    
    def __init__(
        self,
        template: str,
        safe: bool = True,
    ):
        self._template = template
        self._safe = safe
    
    def render(
        self,
        context: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> str:
        """Render template."""
        ctx = context or {}
        ctx.update(kwargs)
        
        if self._safe:
            # Safe format - doesn't raise on missing keys
            return self._safe_format(self._template, ctx)
        
        return self._template.format(**ctx)
    
    def _safe_format(
        self,
        template: str,
        context: Dict[str, Any],
    ) -> str:
        """Safe format that handles missing keys."""
        import string
        
        class SafeDict(dict):
            def __missing__(self, key):
                return '{' + key + '}'
        
        formatter = string.Formatter()
        mapping = SafeDict(context)
        
        try:
            return formatter.vformat(template, (), mapping)
        except (KeyError, IndexError):
            return template


class SQLTemplate:
    """
    SQL template with parameter binding.
    """
    
    def __init__(
        self,
        template: str,
        param_style: str = "named",  # named, qmark, numeric
    ):
        self._template = template
        self._param_style = param_style
    
    def render(
        self,
        context: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Tuple[str, List[Any]]:
        """
        Render SQL template with parameters.
        
        Returns:
            Tuple of (sql_string, parameters)
        """
        ctx = context or {}
        ctx.update(kwargs)
        
        if self._param_style == "named":
            return self._template, ctx
        
        elif self._param_style == "qmark":
            # Convert :name to ?
            params = []
            
            def replace_param(match):
                name = match.group(1)
                params.append(ctx.get(name))
                return '?'
            
            sql = re.sub(r':(\w+)', replace_param, self._template)
            return sql, params
        
        elif self._param_style == "numeric":
            # Convert :name to $1, $2, etc.
            params = []
            param_map = {}
            
            def replace_param(match):
                name = match.group(1)
                if name not in param_map:
                    param_map[name] = len(params) + 1
                    params.append(ctx.get(name))
                return f'${param_map[name]}'
            
            sql = re.sub(r':(\w+)', replace_param, self._template)
            return sql, params
        
        return self._template, []


class EmailTemplate:
    """
    Email template with subject and body.
    """
    
    def __init__(
        self,
        subject_template: str,
        body_template: str,
        html_template: Optional[str] = None,
        engine: Optional[TemplateEngine] = None,
    ):
        self._subject = subject_template
        self._body = body_template
        self._html = html_template
        self._engine = engine or TemplateEngine()
    
    def render(
        self,
        context: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, str]:
        """
        Render email template.
        
        Returns:
            Dict with subject, body, and optionally html
        """
        ctx = context or {}
        ctx.update(kwargs)
        
        result = {
            'subject': self._engine.render(self._subject, ctx),
            'body': self._engine.render(self._body, ctx),
        }
        
        if self._html:
            result['html'] = self._engine.render(self._html, ctx)
        
        return result


class TemplateRegistry:
    """
    Registry for named templates.
    """
    
    _templates: Dict[str, Template] = {}
    
    @classmethod
    def register(
        cls,
        name: str,
        source: str,
        **kwargs: Any,
    ) -> Template:
        """Register a template."""
        template = Template(source, name=name, **kwargs)
        cls._templates[name] = template
        return template
    
    @classmethod
    def get(cls, name: str) -> Optional[Template]:
        """Get a template by name."""
        return cls._templates.get(name)
    
    @classmethod
    def render(
        cls,
        name: str,
        context: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> str:
        """Render a registered template."""
        template = cls.get(name)
        if not template:
            raise TemplateNotFoundError(f"Template not found: {name}")
        return template.render(context, **kwargs)
    
    @classmethod
    def clear(cls) -> None:
        """Clear all registered templates."""
        cls._templates.clear()


# Decorators
def template(
    name_or_source: str,
    from_file: bool = False,
) -> Callable:
    """
    Decorator to associate a template with a function.
    
    Example:
        @template("Hello {{ name }}!")
        def greet(name: str) -> str:
            return {"name": name}
    """
    def decorator(func: Callable) -> Callable:
        engine = TemplateEngine()
        
        if from_file:
            @wraps(func)
            async def wrapper(*args: Any, **kwargs: Any) -> str:
                context = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
                return await engine.render_template(name_or_source, context)
        else:
            @wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> str:
                context = func(*args, **kwargs)
                return engine.render(name_or_source, context)
        
        return wrapper
    
    return decorator


def register_template(name: str) -> Callable:
    """
    Decorator to register a template.
    
    Example:
        @register_template("greeting")
        def greeting_template():
            return "Hello {{ name }}!"
    """
    def decorator(func: Callable) -> Callable:
        source = func()
        TemplateRegistry.register(name, source)
        return func
    
    return decorator


# Factory functions
def create_template_engine(
    search_paths: Optional[List[str]] = None,
    config: Optional[TemplateConfig] = None,
) -> TemplateEngine:
    """Create a template engine."""
    loader = None
    if search_paths:
        loader = FileSystemLoader(search_paths)
    
    return TemplateEngine(config, loader)


def create_template(
    source: str,
    **kwargs: Any,
) -> Template:
    """Create a template from source."""
    return Template(source, **kwargs)


def create_string_template(
    template: str,
    safe: bool = True,
) -> StringTemplate:
    """Create a simple string template."""
    return StringTemplate(template, safe)


def create_sql_template(
    template: str,
    param_style: str = "named",
) -> SQLTemplate:
    """Create a SQL template."""
    return SQLTemplate(template, param_style)


def create_email_template(
    subject: str,
    body: str,
    html: Optional[str] = None,
) -> EmailTemplate:
    """Create an email template."""
    return EmailTemplate(subject, body, html)


# Utility functions
def render(
    template_str: str,
    context: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> str:
    """Quick render utility."""
    engine = TemplateEngine()
    return engine.render(template_str, context, **kwargs)


def render_string(
    template_str: str,
    **kwargs: Any,
) -> str:
    """Simple string format render."""
    return StringTemplate(template_str).render(**kwargs)


__all__ = [
    # Exceptions
    "TemplateError",
    "RenderError",
    "SyntaxError",
    "TemplateNotFoundError",
    # Data classes
    "TemplateConfig",
    "RenderResult",
    # Core classes
    "Template",
    "TemplateLoader",
    "FileSystemLoader",
    "DictLoader",
    "TemplateEngine",
    "StringTemplate",
    "SQLTemplate",
    "EmailTemplate",
    "TemplateRegistry",
    # Decorators
    "template",
    "register_template",
    # Factory functions
    "create_template_engine",
    "create_template",
    "create_string_template",
    "create_sql_template",
    "create_email_template",
    # Utility functions
    "render",
    "render_string",
]
