"""
Enterprise Prompt Templates - Reusable prompt engineering.

Provides a template engine for prompts with versioning,
variables, and composition.

Features:
- Prompt templates with variables
- Template versioning
- Composition/inheritance
- Validation
- A/B testing support
"""

import hashlib
import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Type, Union

logger = logging.getLogger(__name__)


# =============================================================================
# Template Types
# =============================================================================

class TemplateType(Enum):
    """Types of prompt templates."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    FUNCTION = "function"
    COMPOSITE = "composite"


@dataclass
class TemplateVariable:
    """A variable in a prompt template."""
    name: str
    description: str = ""
    var_type: str = "string"  # string, number, boolean, list, object
    required: bool = True
    default: Any = None
    validation: Optional[str] = None  # Regex pattern
    examples: List[str] = field(default_factory=list)


@dataclass
class PromptTemplate:
    """A reusable prompt template."""
    name: str
    template: str
    description: str = ""
    template_type: TemplateType = TemplateType.USER
    version: str = "1.0.0"
    
    # Variables
    variables: List[TemplateVariable] = field(default_factory=list)
    
    # Inheritance
    extends: Optional[str] = None
    includes: List[str] = field(default_factory=list)
    
    # Metadata
    tags: List[str] = field(default_factory=list)
    author: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    # Performance
    token_estimate: Optional[int] = None
    
    def __post_init__(self):
        # Extract variables from template
        if not self.variables:
            self.variables = self._extract_variables()
    
    def _extract_variables(self) -> List[TemplateVariable]:
        """Extract variable names from template."""
        pattern = r"\{\{(\w+)\}\}"
        matches = re.findall(pattern, self.template)
        
        return [
            TemplateVariable(name=name)
            for name in set(matches)
        ]
    
    def render(
        self,
        **variables,
    ) -> str:
        """
        Render the template with variables.
        
        Usage:
            >>> template = PromptTemplate(
            ...     name="greeting",
            ...     template="Hello, {{name}}! You are a {{role}}.",
            ... )
            >>> template.render(name="Alice", role="developer")
            'Hello, Alice! You are a developer.'
        """
        result = self.template
        
        # Check required variables
        for var in self.variables:
            if var.required and var.name not in variables:
                if var.default is not None:
                    variables[var.name] = var.default
                else:
                    raise ValueError(f"Missing required variable: {var.name}")
        
        # Replace variables
        for name, value in variables.items():
            # Validate
            var_def = next((v for v in self.variables if v.name == name), None)
            if var_def and var_def.validation:
                if not re.match(var_def.validation, str(value)):
                    raise ValueError(f"Invalid value for {name}")
            
            # Format value
            if isinstance(value, (list, dict)):
                value = json.dumps(value, indent=2)
            else:
                value = str(value)
            
            result = result.replace(f"{{{{{name}}}}}", value)
        
        return result
    
    def get_hash(self) -> str:
        """Get a hash of the template content."""
        content = f"{self.name}:{self.version}:{self.template}"
        return hashlib.sha256(content.encode()).hexdigest()[:12]


# =============================================================================
# Template Library
# =============================================================================

class TemplateLibrary:
    """
    Library for managing prompt templates.
    
    Usage:
        >>> library = TemplateLibrary()
        >>> 
        >>> # Register template
        >>> library.register(PromptTemplate(
        ...     name="code-review",
        ...     template="Review this {{language}} code:\n{{code}}",
        ... ))
        >>> 
        >>> # Render
        >>> prompt = library.render("code-review", language="Python", code="...")
    """
    
    def __init__(self):
        self._templates: Dict[str, Dict[str, PromptTemplate]] = {}  # name -> version -> template
        self._aliases: Dict[str, str] = {}  # alias -> name
        
        # Load built-in templates
        self._load_builtins()
    
    def _load_builtins(self):
        """Load built-in templates."""
        builtins = [
            PromptTemplate(
                name="agent-system",
                template="""You are {{agent_name}}, an AI assistant.

Your role: {{role}}

{{#if tools}}
Available tools:
{{tools}}
{{/if}}

{{#if context}}
Context:
{{context}}
{{/if}}

Instructions:
{{instructions}}""",
                description="Standard agent system prompt",
                template_type=TemplateType.SYSTEM,
                tags=["agent", "system"],
            ),
            PromptTemplate(
                name="chain-of-thought",
                template="""Think through this step by step:

Task: {{task}}

Let's approach this systematically:
1. First, understand what's being asked
2. Break it down into steps
3. Work through each step
4. Verify the answer

{{#if examples}}
Examples:
{{examples}}
{{/if}}

Now solve the task:""",
                description="Chain of thought reasoning template",
                template_type=TemplateType.USER,
                tags=["reasoning", "cot"],
            ),
            PromptTemplate(
                name="few-shot",
                template="""{{#each examples}}
Input: {{this.input}}
Output: {{this.output}}

{{/each}}
Input: {{input}}
Output:""",
                description="Few-shot learning template",
                template_type=TemplateType.USER,
                tags=["few-shot", "learning"],
            ),
            PromptTemplate(
                name="json-output",
                template="""{{instruction}}

Respond with valid JSON matching this schema:
```json
{{schema}}
```

{{#if examples}}
Example output:
```json
{{examples}}
```
{{/if}}""",
                description="JSON output format template",
                template_type=TemplateType.USER,
                tags=["json", "structured"],
            ),
            PromptTemplate(
                name="code-generation",
                template="""Generate {{language}} code for the following:

Task: {{task}}

Requirements:
{{requirements}}

{{#if context}}
Existing code context:
```{{language}}
{{context}}
```
{{/if}}

Provide clean, well-documented code:""",
                description="Code generation template",
                template_type=TemplateType.USER,
                tags=["code", "generation"],
            ),
            PromptTemplate(
                name="summarization",
                template="""Summarize the following {{content_type}}:

{{content}}

Provide a {{length}} summary that captures the key points.""",
                description="Content summarization template",
                template_type=TemplateType.USER,
                tags=["summarization"],
            ),
            PromptTemplate(
                name="rag-query",
                template="""Answer the question using the provided context.

Context:
{{context}}

Question: {{question}}

{{#if instructions}}
{{instructions}}
{{/if}}

Provide a clear, accurate answer based only on the context above. If the context doesn't contain enough information, say so.""",
                description="RAG query template",
                template_type=TemplateType.USER,
                tags=["rag", "retrieval"],
            ),
        ]
        
        for template in builtins:
            self.register(template)
    
    def register(
        self,
        template: PromptTemplate,
        alias: Optional[str] = None,
    ):
        """Register a template."""
        if template.name not in self._templates:
            self._templates[template.name] = {}
        
        self._templates[template.name][template.version] = template
        
        if alias:
            self._aliases[alias] = template.name
    
    def get(
        self,
        name: str,
        version: Optional[str] = None,
    ) -> Optional[PromptTemplate]:
        """Get a template by name and optional version."""
        # Check alias
        name = self._aliases.get(name, name)
        
        if name not in self._templates:
            return None
        
        versions = self._templates[name]
        
        if version:
            return versions.get(version)
        else:
            # Return latest version
            latest = max(versions.keys())
            return versions[latest]
    
    def render(
        self,
        name: str,
        version: Optional[str] = None,
        **variables,
    ) -> str:
        """Render a template by name."""
        template = self.get(name, version)
        
        if not template:
            raise ValueError(f"Template not found: {name}")
        
        # Handle includes
        for include_name in template.includes:
            include = self.get(include_name)
            if include:
                variables[f"include_{include_name}"] = include.render(**variables)
        
        # Handle extends
        if template.extends:
            parent = self.get(template.extends)
            if parent:
                # Child template overrides parent sections
                pass
        
        return template.render(**variables)
    
    def list(
        self,
        tag: Optional[str] = None,
        template_type: Optional[TemplateType] = None,
    ) -> List[PromptTemplate]:
        """List templates with optional filtering."""
        templates = []
        
        for name, versions in self._templates.items():
            latest = max(versions.keys())
            template = versions[latest]
            
            if tag and tag not in template.tags:
                continue
            
            if template_type and template.template_type != template_type:
                continue
            
            templates.append(template)
        
        return templates
    
    def delete(self, name: str, version: Optional[str] = None):
        """Delete a template or specific version."""
        if name not in self._templates:
            return
        
        if version:
            if version in self._templates[name]:
                del self._templates[name][version]
        else:
            del self._templates[name]
    
    def export(self, path: str):
        """Export all templates to a directory."""
        export_path = Path(path)
        export_path.mkdir(parents=True, exist_ok=True)
        
        for name, versions in self._templates.items():
            for version, template in versions.items():
                file_path = export_path / f"{name}_{version}.json"
                
                data = {
                    "name": template.name,
                    "template": template.template,
                    "description": template.description,
                    "template_type": template.template_type.value,
                    "version": template.version,
                    "variables": [
                        {
                            "name": v.name,
                            "description": v.description,
                            "type": v.var_type,
                            "required": v.required,
                            "default": v.default,
                        }
                        for v in template.variables
                    ],
                    "tags": template.tags,
                    "author": template.author,
                }
                
                with open(file_path, "w") as f:
                    json.dump(data, f, indent=2)
    
    def import_from(self, path: str):
        """Import templates from a directory."""
        import_path = Path(path)
        
        for file_path in import_path.glob("*.json"):
            with open(file_path, "r") as f:
                data = json.load(f)
            
            template = PromptTemplate(
                name=data["name"],
                template=data["template"],
                description=data.get("description", ""),
                template_type=TemplateType(data.get("template_type", "user")),
                version=data.get("version", "1.0.0"),
                variables=[
                    TemplateVariable(**v)
                    for v in data.get("variables", [])
                ],
                tags=data.get("tags", []),
                author=data.get("author", ""),
            )
            
            self.register(template)


# =============================================================================
# Template Builder
# =============================================================================

class TemplateBuilder:
    """
    Builder pattern for creating prompt templates.
    
    Usage:
        >>> template = (TemplateBuilder("my-template")
        ...     .system("You are a helpful assistant")
        ...     .variable("task", required=True)
        ...     .variable("context", required=False)
        ...     .instruction("Complete the task carefully")
        ...     .build())
    """
    
    def __init__(self, name: str):
        self.name = name
        self._parts: List[str] = []
        self._variables: List[TemplateVariable] = []
        self._template_type = TemplateType.USER
        self._tags: List[str] = []
        self._version = "1.0.0"
        self._description = ""
    
    def text(self, text: str) -> "TemplateBuilder":
        """Add static text."""
        self._parts.append(text)
        return self
    
    def variable(
        self,
        name: str,
        required: bool = True,
        default: Any = None,
        description: str = "",
    ) -> "TemplateBuilder":
        """Add a variable placeholder."""
        self._parts.append(f"{{{{{name}}}}}")
        self._variables.append(TemplateVariable(
            name=name,
            required=required,
            default=default,
            description=description,
        ))
        return self
    
    def newline(self, count: int = 1) -> "TemplateBuilder":
        """Add newlines."""
        self._parts.append("\n" * count)
        return self
    
    def section(self, title: str, content: str) -> "TemplateBuilder":
        """Add a section with title."""
        self._parts.append(f"\n## {title}\n{content}")
        return self
    
    def instruction(self, text: str) -> "TemplateBuilder":
        """Add an instruction."""
        self._parts.append(f"\n{text}")
        return self
    
    def system(self, content: str) -> "TemplateBuilder":
        """Set as system prompt type."""
        self._template_type = TemplateType.SYSTEM
        self._parts.append(content)
        return self
    
    def tag(self, *tags: str) -> "TemplateBuilder":
        """Add tags."""
        self._tags.extend(tags)
        return self
    
    def version(self, version: str) -> "TemplateBuilder":
        """Set version."""
        self._version = version
        return self
    
    def description(self, description: str) -> "TemplateBuilder":
        """Set description."""
        self._description = description
        return self
    
    def build(self) -> PromptTemplate:
        """Build the template."""
        return PromptTemplate(
            name=self.name,
            template="".join(self._parts),
            description=self._description,
            template_type=self._template_type,
            version=self._version,
            variables=self._variables,
            tags=self._tags,
        )


# =============================================================================
# Template Decorator
# =============================================================================

def template(
    name: str,
    version: str = "1.0.0",
    description: str = "",
    tags: List[str] = None,
):
    """
    Decorator to define a template from a function docstring.
    
    Usage:
        >>> @template("code-review", version="1.0.0")
        ... def code_review(code: str, language: str = "python"):
        ...     '''Review the following {{language}} code:
        ...     
        ...     ```{{language}}
        ...     {{code}}
        ...     ```
        ...     
        ...     Provide detailed feedback.'''
        ...     pass
    """
    def decorator(fn: Callable):
        docstring = fn.__doc__ or ""
        
        # Create template
        tmpl = PromptTemplate(
            name=name,
            template=docstring.strip(),
            description=description,
            version=version,
            tags=tags or [],
        )
        
        # Register in global library
        get_template_library().register(tmpl)
        
        # Return function that renders template
        def wrapper(**kwargs):
            return tmpl.render(**kwargs)
        
        wrapper.template = tmpl
        return wrapper
    
    return decorator


# =============================================================================
# Global Library
# =============================================================================

_global_library: Optional[TemplateLibrary] = None


def get_template_library() -> TemplateLibrary:
    """Get the global template library."""
    global _global_library
    
    if _global_library is None:
        _global_library = TemplateLibrary()
    
    return _global_library


def set_template_library(library: TemplateLibrary):
    """Set the global template library."""
    global _global_library
    _global_library = library


# Convenience functions
def render_template(name: str, **variables) -> str:
    """Render a template from the global library."""
    return get_template_library().render(name, **variables)


def register_template(template: PromptTemplate):
    """Register a template in the global library."""
    get_template_library().register(template)


def get_template(name: str, version: str = None) -> Optional[PromptTemplate]:
    """Get a template from the global library."""
    return get_template_library().get(name, version)
