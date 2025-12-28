---
tags:
  - prompts
  - templates
  - prompt-engineering
---

# 📝 Prompts Module

<div class="annotate" markdown>

**Comprehensive prompt management with security and versioning**

Create, manage, and render safe prompts for LLMs

</div>

## 🎯 Quick Navigation

<div class="grid cards" markdown>

-   :material-file-document-edit:{ .lg } **Templates**
    
    Create reusable prompt templates
    
    [:octicons-arrow-right-24: Create](#prompt-templates)

-   :material-shield-lock:{ .lg } **Security**
    
    Injection detection and sanitization
    
    [:octicons-arrow-right-24: Secure](#security-features)

-   :material-source-branch:{ .lg } **Versioning**
    
    Track prompt versions
    
    [:octicons-arrow-right-24: Manage](#version-control)

-   :material-book-open:{ .lg } **Examples**
    
    Prompt engineering patterns
    
    [:octicons-arrow-right-24: View Examples](#examples)

</div>

## 📖 Overview

!!! abstract "What is the Prompts Module?"
    
    The Prompts module provides comprehensive prompt management with security features, version control, and safe rendering for Large Language Models (LLMs).

<div class="grid" markdown>

:material-code-braces:{ .lg } **Template Variables**
:   Dynamic placeholder substitution

:material-shield-alert:{ .lg } **Injection Prevention**
:   Detect and block prompt injections

:material-tag-multiple:{ .lg } **Metadata Support**
:   Tags, descriptions, and versioning

:material-history:{ .lg } **Version History**
:   Track prompt changes over time

</div>

## Core Components

### Prompt Class

The `Prompt` class represents a prompt template with security and versioning features.

#### Constructor

```python
Prompt(
    template: str,
    metadata: Dict[str, Any] = None,
    enable_security: bool = True
)
```

**Parameters:**

- **`template`** *(str)*: The prompt template with `{variable}` placeholders
- **`metadata`** *(Dict[str, Any])*: Additional metadata (tags, description, etc.)
- **`enable_security`** *(bool)*: Enable injection detection and sanitization

#### Methods

```python
def render(**kwargs) -> str
def render_safe(**kwargs) -> str
def update_template(new_template: str) -> None
```

**Example:**

```python
from agenticaiframework.prompts import Prompt

# Create a prompt with security enabled
prompt = Prompt(
    template="Hello {name}, your task is: {task}",
    metadata={"category": "greeting", "version": "1.0"},
    enable_security=True
)

# Render with variables
result = prompt.render(name="Alice", task="analyze data")
print(result)

# Safe rendering with automatic sanitization
safe_result = prompt.render_safe(
    name="Bob",
    task="<script>alert('xss')</script>"
)
print(safe_result)  # Script tags removed
```

### PromptManager Class

The `PromptManager` manages a collection of prompts with security and versioning.

#### Constructor

```python
PromptManager(enable_security: bool = True)
```

#### Key Methods

```python
def register_prompt(prompt: Prompt) -> None
def get_prompt(prompt_id: str) -> Optional[Prompt]
def render_prompt(prompt_id: str, **kwargs) -> str
def list_prompts() -> List[str]
def delete_prompt(prompt_id: str) -> None
```

**Example:**

```python
from agenticaiframework.prompts import Prompt, PromptManager

# Create manager with security enabled
manager = PromptManager(enable_security=True)

# Register multiple prompts
greeting_prompt = Prompt(
    template="Welcome {user}! How can I help you today?",
    metadata={"type": "greeting"}
)
manager.register_prompt(greeting_prompt)

task_prompt = Prompt(
    template="Task: {task}\nContext: {context}\nOutput format: {format}",
    metadata={"type": "task"}
)
manager.register_prompt(task_prompt)

# Render by ID
result = manager.render_prompt(
    greeting_prompt.id,
    user="Alice"
)
print(result)

# List all prompts
prompts = manager.list_prompts()
print(f"Registered prompts: {len(prompts)}")
```

## Use Cases
- Creating consistent prompts for chatbots and virtual assistants.
- Dynamically generating prompts based on user input or context.
- Optimizing prompts for specific LLM providers.
- Managing large prompt libraries for enterprise applications.

## Best Practices
- Keep prompts concise and clear to avoid ambiguity.
- Use placeholders for dynamic values to improve reusability.
- Test prompts with different LLMs to ensure compatibility.
- Store prompts in version-controlled files for maintainability.

## Related Documentation
- [LLMs Module](llms.md)
- [Knowledge Module](knowledge.md)
- [Agents Module](agents.md)
