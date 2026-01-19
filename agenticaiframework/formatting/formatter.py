"""
Output Formatter Implementation.

Provides comprehensive formatting for agent outputs including
Markdown, Code, JSON, HTML, Tables, and Plain Text.
"""

import json
import re
import html
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Callable

logger = logging.getLogger(__name__)


class FormatType(Enum):
    """Supported output format types."""
    MARKDOWN = "markdown"
    CODE = "code"
    JSON = "json"
    HTML = "html"
    TABLE = "table"
    PLAIN = "plain"
    XML = "xml"
    YAML = "yaml"


class TableFormat(Enum):
    """Table output formats."""
    MARKDOWN = "markdown"
    ASCII = "ascii"
    CSV = "csv"
    TSV = "tsv"
    HTML = "html"
    LATEX = "latex"


@dataclass
class OutputFormat:
    """Output format configuration."""
    format_type: FormatType
    options: Dict[str, Any] = field(default_factory=dict)
    template: Optional[str] = None
    syntax_highlight: bool = True
    line_numbers: bool = False
    max_width: int = 120
    indent: int = 2


@dataclass
class FormattedOutput:
    """Formatted output result."""
    content: str
    formatted: str
    format_type: FormatType
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def __str__(self) -> str:
        return self.formatted
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "formatted": self.formatted,
            "format_type": self.format_type.value,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


@dataclass
class CodeBlock:
    """Code block with language and metadata."""
    code: str
    language: str = "text"
    filename: Optional[str] = None
    line_start: int = 1
    highlight_lines: List[int] = field(default_factory=list)
    
    def to_markdown(self) -> str:
        """Convert to markdown code block."""
        header = f"```{self.language}"
        if self.filename:
            header += f" title=\"{self.filename}\""
        return f"{header}\n{self.code}\n```"
    
    def to_html(self) -> str:
        """Convert to HTML code block."""
        escaped = html.escape(self.code)
        lang_class = f"language-{self.language}" if self.language else ""
        return f'<pre><code class="{lang_class}">{escaped}</code></pre>'


class BaseFormatter(ABC):
    """Abstract base formatter."""
    
    @abstractmethod
    def format(self, content: Any, **options) -> str:
        """Format content."""
        pass
    
    @abstractmethod
    def can_format(self, content: Any) -> bool:
        """Check if content can be formatted."""
        pass


class MarkdownFormatter(BaseFormatter):
    """
    Markdown formatter for rich text output.
    
    Supports:
    - Headings (h1-h6)
    - Lists (ordered, unordered, checklists)
    - Tables
    - Code blocks
    - Links and images
    - Blockquotes
    - Horizontal rules
    - Bold, italic, strikethrough
    """
    
    def can_format(self, content: Any) -> bool:
        return isinstance(content, (str, dict, list))
    
    def format(self, content: Any, **options) -> str:
        """Format content as markdown."""
        template = options.get("template", "paragraph")
        
        if template == "heading":
            level = options.get("level", 1)
            return self.heading(str(content), level)
        elif template == "list":
            return self.list_items(content if isinstance(content, list) else [content], 
                                   ordered=options.get("ordered", False))
        elif template == "checklist":
            return self.checklist(content if isinstance(content, list) else [content])
        elif template == "table":
            return self.table(content)
        elif template == "blockquote":
            return self.blockquote(str(content))
        elif template == "code":
            return self.code_block(str(content), options.get("language", ""))
        elif template == "link":
            return self.link(str(content), options.get("url", ""))
        else:
            return str(content)
    
    def heading(self, text: str, level: int = 1) -> str:
        """Create markdown heading."""
        level = max(1, min(6, level))
        return f"{'#' * level} {text}"
    
    def list_items(self, items: List[Any], ordered: bool = False, indent: int = 0) -> str:
        """Create markdown list."""
        lines = []
        prefix = "  " * indent
        for i, item in enumerate(items, 1):
            if isinstance(item, list):
                # Nested list
                lines.append(self.list_items(item, ordered, indent + 1))
            else:
                marker = f"{i}." if ordered else "-"
                lines.append(f"{prefix}{marker} {item}")
        return "\n".join(lines)
    
    def checklist(self, items: List[Union[str, tuple]]) -> str:
        """Create markdown checklist."""
        lines = []
        for item in items:
            if isinstance(item, tuple):
                text, checked = item
            else:
                text, checked = item, False
            checkbox = "[x]" if checked else "[ ]"
            lines.append(f"- {checkbox} {text}")
        return "\n".join(lines)
    
    def table(self, data: Union[List[Dict], Dict[str, List]]) -> str:
        """Create markdown table."""
        if not data:
            return ""
        
        if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
            # List of dicts
            headers = list(data[0].keys())
            rows = [[str(row.get(h, "")) for h in headers] for row in data]
        elif isinstance(data, dict):
            # Dict of lists
            headers = list(data.keys())
            max_len = max(len(v) if isinstance(v, list) else 1 for v in data.values())
            rows = []
            for i in range(max_len):
                row = []
                for h in headers:
                    vals = data[h] if isinstance(data[h], list) else [data[h]]
                    row.append(str(vals[i]) if i < len(vals) else "")
                rows.append(row)
        else:
            return str(data)
        
        # Build table
        header_line = "| " + " | ".join(headers) + " |"
        separator = "| " + " | ".join(["---"] * len(headers)) + " |"
        data_lines = ["| " + " | ".join(row) + " |" for row in rows]
        
        return "\n".join([header_line, separator] + data_lines)
    
    def blockquote(self, text: str) -> str:
        """Create markdown blockquote."""
        lines = text.split("\n")
        return "\n".join(f"> {line}" for line in lines)
    
    def code_block(self, code: str, language: str = "") -> str:
        """Create markdown code block."""
        return f"```{language}\n{code}\n```"
    
    def inline_code(self, code: str) -> str:
        """Create inline code."""
        return f"`{code}`"
    
    def link(self, text: str, url: str, title: str = "") -> str:
        """Create markdown link."""
        if title:
            return f'[{text}]({url} "{title}")'
        return f"[{text}]({url})"
    
    def image(self, alt: str, url: str, title: str = "") -> str:
        """Create markdown image."""
        if title:
            return f'![{alt}]({url} "{title}")'
        return f"![{alt}]({url})"
    
    def bold(self, text: str) -> str:
        return f"**{text}**"
    
    def italic(self, text: str) -> str:
        return f"*{text}*"
    
    def strikethrough(self, text: str) -> str:
        return f"~~{text}~~"
    
    def horizontal_rule(self) -> str:
        return "---"


class CodeFormatter(BaseFormatter):
    """
    Code formatter with syntax highlighting support.
    
    Features:
    - Language detection
    - Line numbers
    - Syntax highlighting (for terminal output)
    - Diff formatting
    """
    
    # Common language patterns for detection
    LANGUAGE_PATTERNS = {
        "python": [r"^\s*def\s+\w+", r"^\s*class\s+\w+", r"import\s+\w+", r"from\s+\w+\s+import"],
        "javascript": [r"^\s*function\s+\w+", r"^\s*const\s+\w+\s*=", r"^\s*let\s+\w+\s*=", r"=>\s*{"],
        "typescript": [r":\s*(string|number|boolean|any)\s*[;=]", r"interface\s+\w+", r"type\s+\w+\s*="],
        "java": [r"^\s*public\s+class", r"^\s*private\s+\w+", r"System\.out\.println"],
        "csharp": [r"^\s*namespace\s+", r"^\s*public\s+class", r"Console\.WriteLine"],
        "go": [r"^\s*func\s+\w+", r"^\s*package\s+\w+", r"fmt\.Println"],
        "rust": [r"^\s*fn\s+\w+", r"^\s*let\s+mut\s+", r"println!\s*\("],
        "sql": [r"^\s*SELECT\s+", r"^\s*INSERT\s+INTO", r"^\s*CREATE\s+TABLE"],
        "html": [r"<!DOCTYPE\s+html>", r"<html", r"<body"],
        "css": [r"^\s*\.\w+\s*{", r"^\s*#\w+\s*{", r"@media\s+"],
        "json": [r"^\s*\{", r'"\w+":\s*'],
        "yaml": [r"^\s*\w+:\s*\n", r"^\s*-\s+\w+"],
        "bash": [r"^#!/bin/bash", r"^\s*echo\s+", r"\$\(\w+\)"],
        "powershell": [r"^\$\w+\s*=", r"Get-\w+", r"Set-\w+"],
    }
    
    def can_format(self, content: Any) -> bool:
        return isinstance(content, str)
    
    def format(self, content: Any, **options) -> str:
        """Format code with options."""
        code = str(content)
        language = options.get("language") or self.detect_language(code)
        line_numbers = options.get("line_numbers", False)
        highlight_lines = options.get("highlight_lines", [])
        
        if line_numbers:
            code = self.add_line_numbers(code, highlight_lines)
        
        if options.get("markdown_wrap", True):
            return f"```{language}\n{code}\n```"
        
        return code
    
    def detect_language(self, code: str) -> str:
        """Detect programming language from code content."""
        for language, patterns in self.LANGUAGE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, code, re.MULTILINE | re.IGNORECASE):
                    return language
        return "text"
    
    def add_line_numbers(self, code: str, highlight_lines: List[int] = None) -> str:
        """Add line numbers to code."""
        highlight_lines = highlight_lines or []
        lines = code.split("\n")
        max_width = len(str(len(lines)))
        
        numbered_lines = []
        for i, line in enumerate(lines, 1):
            marker = ">" if i in highlight_lines else " "
            numbered_lines.append(f"{marker}{i:>{max_width}} | {line}")
        
        return "\n".join(numbered_lines)
    
    def format_diff(self, old_code: str, new_code: str, context_lines: int = 3) -> str:
        """Format code diff."""
        import difflib
        
        old_lines = old_code.splitlines(keepends=True)
        new_lines = new_code.splitlines(keepends=True)
        
        diff = difflib.unified_diff(
            old_lines, new_lines,
            fromfile="original",
            tofile="modified",
            n=context_lines
        )
        
        return "".join(diff)
    
    def extract_code_blocks(self, text: str) -> List[CodeBlock]:
        """Extract code blocks from markdown text."""
        pattern = r"```(\w*)\n(.*?)```"
        matches = re.findall(pattern, text, re.DOTALL)
        
        blocks = []
        for language, code in matches:
            blocks.append(CodeBlock(
                code=code.strip(),
                language=language or "text"
            ))
        
        return blocks


class JSONFormatter(BaseFormatter):
    """
    JSON formatter with pretty printing and validation.
    """
    
    def can_format(self, content: Any) -> bool:
        if isinstance(content, (dict, list)):
            return True
        if isinstance(content, str):
            try:
                json.loads(content)
                return True
            except json.JSONDecodeError:
                return False
        return False
    
    def format(self, content: Any, **options) -> str:
        """Format as pretty JSON."""
        indent = options.get("indent", 2)
        sort_keys = options.get("sort_keys", False)
        ensure_ascii = options.get("ensure_ascii", False)
        
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except json.JSONDecodeError:
                return content
        
        return json.dumps(
            content,
            indent=indent,
            sort_keys=sort_keys,
            ensure_ascii=ensure_ascii,
            default=str
        )
    
    def minify(self, content: Any) -> str:
        """Minify JSON."""
        if isinstance(content, str):
            content = json.loads(content)
        return json.dumps(content, separators=(",", ":"))
    
    def validate(self, content: str, schema: Optional[Dict] = None) -> tuple:
        """Validate JSON and optionally against schema."""
        try:
            data = json.loads(content)
            if schema:
                try:
                    import jsonschema
                    jsonschema.validate(data, schema)
                except ImportError:
                    logger.warning("jsonschema not installed, skipping schema validation")
                except jsonschema.ValidationError as e:
                    return False, str(e)
            return True, None
        except json.JSONDecodeError as e:
            return False, str(e)


class HTMLFormatter(BaseFormatter):
    """
    HTML formatter for rich web output.
    """
    
    def can_format(self, content: Any) -> bool:
        return True
    
    def format(self, content: Any, **options) -> str:
        """Format content as HTML."""
        template = options.get("template", "paragraph")
        
        if template == "paragraph":
            return self.paragraph(str(content))
        elif template == "heading":
            level = options.get("level", 1)
            return self.heading(str(content), level)
        elif template == "list":
            return self.list_items(content if isinstance(content, list) else [content],
                                   ordered=options.get("ordered", False))
        elif template == "table":
            return self.table(content)
        elif template == "code":
            return self.code(str(content), options.get("language", ""))
        elif template == "card":
            return self.card(str(content), options.get("title", ""))
        else:
            return self.escape(str(content))
    
    def escape(self, text: str) -> str:
        """Escape HTML special characters."""
        return html.escape(text)
    
    def paragraph(self, text: str) -> str:
        return f"<p>{self.escape(text)}</p>"
    
    def heading(self, text: str, level: int = 1) -> str:
        level = max(1, min(6, level))
        return f"<h{level}>{self.escape(text)}</h{level}>"
    
    def list_items(self, items: List[Any], ordered: bool = False) -> str:
        tag = "ol" if ordered else "ul"
        items_html = "\n".join(f"  <li>{self.escape(str(item))}</li>" for item in items)
        return f"<{tag}>\n{items_html}\n</{tag}>"
    
    def table(self, data: Union[List[Dict], Dict]) -> str:
        """Create HTML table."""
        if not data:
            return "<table></table>"
        
        if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
            headers = list(data[0].keys())
            rows = [[str(row.get(h, "")) for h in headers] for row in data]
        else:
            return f"<table><tr><td>{self.escape(str(data))}</td></tr></table>"
        
        header_html = "<tr>" + "".join(f"<th>{self.escape(h)}</th>" for h in headers) + "</tr>"
        rows_html = "\n".join(
            "<tr>" + "".join(f"<td>{self.escape(cell)}</td>" for cell in row) + "</tr>"
            for row in rows
        )
        
        return f"<table>\n  <thead>\n    {header_html}\n  </thead>\n  <tbody>\n    {rows_html}\n  </tbody>\n</table>"
    
    def code(self, code: str, language: str = "") -> str:
        class_attr = f' class="language-{language}"' if language else ""
        return f"<pre><code{class_attr}>{self.escape(code)}</code></pre>"
    
    def card(self, content: str, title: str = "") -> str:
        title_html = f"<div class='card-title'>{self.escape(title)}</div>" if title else ""
        return f"""<div class="card">
  {title_html}
  <div class="card-content">{self.escape(content)}</div>
</div>"""
    
    def link(self, text: str, url: str, target: str = "_blank") -> str:
        return f'<a href="{self.escape(url)}" target="{target}">{self.escape(text)}</a>'
    
    def image(self, src: str, alt: str = "", width: str = "", height: str = "") -> str:
        attrs = [f'src="{self.escape(src)}"', f'alt="{self.escape(alt)}"']
        if width:
            attrs.append(f'width="{width}"')
        if height:
            attrs.append(f'height="{height}"')
        return f"<img {' '.join(attrs)} />"


class TableFormatter(BaseFormatter):
    """
    Table formatter supporting multiple output formats.
    """
    
    def can_format(self, content: Any) -> bool:
        return isinstance(content, (list, dict))
    
    def format(self, content: Any, **options) -> str:
        """Format data as table."""
        table_format = options.get("format", TableFormat.MARKDOWN)
        if isinstance(table_format, str):
            table_format = TableFormat(table_format)
        
        formatters = {
            TableFormat.MARKDOWN: self._format_markdown,
            TableFormat.ASCII: self._format_ascii,
            TableFormat.CSV: self._format_csv,
            TableFormat.TSV: self._format_tsv,
            TableFormat.HTML: self._format_html,
            TableFormat.LATEX: self._format_latex,
        }
        
        formatter = formatters.get(table_format, self._format_markdown)
        return formatter(content, **options)
    
    def _extract_data(self, content: Any) -> tuple:
        """Extract headers and rows from content."""
        if isinstance(content, list) and len(content) > 0:
            if isinstance(content[0], dict):
                headers = list(content[0].keys())
                rows = [[str(row.get(h, "")) for h in headers] for row in content]
            elif isinstance(content[0], (list, tuple)):
                headers = [f"Col{i+1}" for i in range(len(content[0]))]
                rows = [[str(cell) for cell in row] for row in content]
            else:
                headers = ["Value"]
                rows = [[str(item)] for item in content]
        elif isinstance(content, dict):
            headers = ["Key", "Value"]
            rows = [[str(k), str(v)] for k, v in content.items()]
        else:
            headers = ["Value"]
            rows = [[str(content)]]
        
        return headers, rows
    
    def _format_markdown(self, content: Any, **options) -> str:
        headers, rows = self._extract_data(content)
        
        header_line = "| " + " | ".join(headers) + " |"
        separator = "| " + " | ".join(["---"] * len(headers)) + " |"
        data_lines = ["| " + " | ".join(row) + " |" for row in rows]
        
        return "\n".join([header_line, separator] + data_lines)
    
    def _format_ascii(self, content: Any, **options) -> str:
        headers, rows = self._extract_data(content)
        
        # Calculate column widths
        widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                widths[i] = max(widths[i], len(cell))
        
        # Build table
        separator = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
        
        def format_row(row):
            cells = [f" {cell:<{widths[i]}} " for i, cell in enumerate(row)]
            return "|" + "|".join(cells) + "|"
        
        lines = [separator, format_row(headers), separator]
        for row in rows:
            lines.append(format_row(row))
        lines.append(separator)
        
        return "\n".join(lines)
    
    def _format_csv(self, content: Any, **options) -> str:
        import csv
        import io
        
        headers, rows = self._extract_data(content)
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)
        writer.writerows(rows)
        
        return output.getvalue()
    
    def _format_tsv(self, content: Any, **options) -> str:
        headers, rows = self._extract_data(content)
        
        lines = ["\t".join(headers)]
        for row in rows:
            lines.append("\t".join(row))
        
        return "\n".join(lines)
    
    def _format_html(self, content: Any, **options) -> str:
        html_formatter = HTMLFormatter()
        return html_formatter.table(content)
    
    def _format_latex(self, content: Any, **options) -> str:
        headers, rows = self._extract_data(content)
        
        col_format = "|" + "|".join(["c"] * len(headers)) + "|"
        
        lines = [
            "\\begin{tabular}{" + col_format + "}",
            "\\hline",
            " & ".join(headers) + " \\\\",
            "\\hline",
        ]
        
        for row in rows:
            lines.append(" & ".join(row) + " \\\\")
        
        lines.extend(["\\hline", "\\end{tabular}"])
        
        return "\n".join(lines)


class PlainTextFormatter(BaseFormatter):
    """
    Plain text formatter with word wrapping.
    """
    
    def can_format(self, content: Any) -> bool:
        return True
    
    def format(self, content: Any, **options) -> str:
        """Format as plain text."""
        text = str(content)
        max_width = options.get("max_width", 80)
        
        if options.get("wrap", False):
            text = self.wrap_text(text, max_width)
        
        return text
    
    def wrap_text(self, text: str, width: int = 80) -> str:
        """Wrap text at specified width."""
        import textwrap
        
        paragraphs = text.split("\n\n")
        wrapped = []
        
        for para in paragraphs:
            wrapped.append(textwrap.fill(para, width=width))
        
        return "\n\n".join(wrapped)
    
    def strip_formatting(self, text: str) -> str:
        """Remove markdown/HTML formatting."""
        # Remove markdown links
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
        # Remove markdown bold/italic
        text = re.sub(r'\*\*([^\*]+)\*\*', r'\1', text)
        text = re.sub(r'\*([^\*]+)\*', r'\1', text)
        # Remove markdown code
        text = re.sub(r'`([^`]+)`', r'\1', text)
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        return text


class OutputFormatter:
    """
    Main output formatter combining all format types.
    
    Example:
        >>> formatter = OutputFormatter()
        >>> 
        >>> # Format as markdown heading
        >>> result = formatter.format(
        ...     "Hello World",
        ...     format_type=FormatType.MARKDOWN,
        ...     template="heading",
        ...     level=1
        ... )
        >>> print(result.formatted)
        # Hello World
        >>> 
        >>> # Format code
        >>> code_result = formatter.format_code(
        ...     "print('hello')",
        ...     language="python",
        ...     line_numbers=True
        ... )
        >>> 
        >>> # Format table
        >>> table_result = formatter.format_table(
        ...     [{"name": "Alice", "age": 30}],
        ...     format=TableFormat.MARKDOWN
        ... )
    """
    
    def __init__(self):
        self._formatters: Dict[FormatType, BaseFormatter] = {
            FormatType.MARKDOWN: MarkdownFormatter(),
            FormatType.CODE: CodeFormatter(),
            FormatType.JSON: JSONFormatter(),
            FormatType.HTML: HTMLFormatter(),
            FormatType.TABLE: TableFormatter(),
            FormatType.PLAIN: PlainTextFormatter(),
        }
        
        # Custom formatters
        self._custom_formatters: Dict[str, Callable] = {}
    
    def register_formatter(self, name: str, formatter: Union[BaseFormatter, Callable]) -> None:
        """Register custom formatter."""
        if isinstance(formatter, BaseFormatter):
            self._custom_formatters[name] = formatter.format
        else:
            self._custom_formatters[name] = formatter
    
    def format(
        self,
        content: Any,
        format_type: FormatType = FormatType.PLAIN,
        **options
    ) -> FormattedOutput:
        """
        Format content with specified format type.
        
        Args:
            content: Content to format
            format_type: Output format type
            **options: Format-specific options
        
        Returns:
            FormattedOutput with original and formatted content
        """
        formatter = self._formatters.get(format_type, self._formatters[FormatType.PLAIN])
        
        try:
            formatted = formatter.format(content, **options)
            
            return FormattedOutput(
                content=str(content),
                formatted=formatted,
                format_type=format_type,
                metadata={"options": options}
            )
        except Exception as e:
            logger.error(f"Formatting error: {e}")
            return FormattedOutput(
                content=str(content),
                formatted=str(content),
                format_type=format_type,
                metadata={"error": str(e)}
            )
    
    def format_markdown(self, content: Any, **options) -> FormattedOutput:
        """Format as markdown."""
        return self.format(content, FormatType.MARKDOWN, **options)
    
    def format_code(
        self,
        code: str,
        language: str = "",
        line_numbers: bool = False,
        highlight_lines: List[int] = None,
        **options
    ) -> FormattedOutput:
        """Format code with syntax highlighting."""
        options.update({
            "language": language,
            "line_numbers": line_numbers,
            "highlight_lines": highlight_lines or [],
        })
        return self.format(code, FormatType.CODE, **options)
    
    def format_json(self, data: Any, indent: int = 2, sort_keys: bool = False) -> FormattedOutput:
        """Format as pretty JSON."""
        return self.format(data, FormatType.JSON, indent=indent, sort_keys=sort_keys)
    
    def format_html(self, content: Any, **options) -> FormattedOutput:
        """Format as HTML."""
        return self.format(content, FormatType.HTML, **options)
    
    def format_table(
        self,
        data: Union[List[Dict], Dict],
        format: TableFormat = TableFormat.MARKDOWN,
        **options
    ) -> FormattedOutput:
        """Format data as table."""
        options["format"] = format
        return self.format(data, FormatType.TABLE, **options)
    
    def format_plain(self, content: Any, max_width: int = 80, wrap: bool = False) -> FormattedOutput:
        """Format as plain text."""
        return self.format(content, FormatType.PLAIN, max_width=max_width, wrap=wrap)
    
    # Convenience methods for markdown
    def heading(self, text: str, level: int = 1) -> str:
        """Create markdown heading."""
        return self._formatters[FormatType.MARKDOWN].heading(text, level)
    
    def bullet_list(self, items: List[Any]) -> str:
        """Create markdown bullet list."""
        return self._formatters[FormatType.MARKDOWN].list_items(items, ordered=False)
    
    def numbered_list(self, items: List[Any]) -> str:
        """Create markdown numbered list."""
        return self._formatters[FormatType.MARKDOWN].list_items(items, ordered=True)
    
    def code_block(self, code: str, language: str = "") -> str:
        """Create markdown code block."""
        return self._formatters[FormatType.MARKDOWN].code_block(code, language)
    
    def table(self, data: Union[List[Dict], Dict]) -> str:
        """Create markdown table."""
        return self._formatters[FormatType.MARKDOWN].table(data)
    
    def blockquote(self, text: str) -> str:
        """Create markdown blockquote."""
        return self._formatters[FormatType.MARKDOWN].blockquote(text)


__all__ = [
    # Types
    "FormatType",
    "OutputFormat",
    "FormattedOutput",
    "CodeBlock",
    "TableFormat",
    # Formatters
    "BaseFormatter",
    "MarkdownFormatter",
    "CodeFormatter",
    "JSONFormatter",
    "HTMLFormatter",
    "TableFormatter",
    "PlainTextFormatter",
    # Main class
    "OutputFormatter",
]
