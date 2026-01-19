"""
Output Formatting Module for Agent Responses.

Format agent outputs in various formats:
- Markdown (headings, lists, tables, code blocks)
- Code (syntax highlighting, language detection)
- JSON (pretty print, schema validation)
- HTML (rich formatting)
- Table (ASCII, CSV, formatted)
- Plain text

Example:
    >>> from agenticaiframework.formatting import OutputFormatter, FormatType
    >>> 
    >>> formatter = OutputFormatter()
    >>> 
    >>> # Format as markdown
    >>> result = formatter.format(
    ...     content="Hello World",
    ...     format_type=FormatType.MARKDOWN,
    ...     template="heading"
    ... )
    >>> print(result.formatted)
    # Hello World
    >>> 
    >>> # Format code with syntax highlighting
    >>> code_result = formatter.format_code(
    ...     code="print('hello')",
    ...     language="python"
    ... )
    >>> 
    >>> # Format as table
    >>> table_result = formatter.format_table(
    ...     data=[{"name": "Alice", "age": 30}],
    ...     format="markdown"
    ... )
"""

from .formatter import (
    # Types
    FormatType,
    OutputFormat,
    FormattedOutput,
    CodeBlock,
    TableFormat,
    # Formatters
    BaseFormatter,
    MarkdownFormatter,
    CodeFormatter,
    JSONFormatter,
    HTMLFormatter,
    TableFormatter,
    PlainTextFormatter,
    # Main class
    OutputFormatter,
)

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
