---
title: Contributing
description: Contribute to AgenticAI Framework - report bugs, suggest features, submit code, and improve documentation
tags:
  - contributing
  - development
  - community
  - guide
---

# 🤝 Contributing

<div class="annotate" markdown>

**Join our community of contributors**

Help us build the most comprehensive AI agent framework with **400+ modules**

</div>

!!! success "Framework Statistics"
    - **400+ Total Modules** - Comprehensive coverage
    - **237 Enterprise Modules** - Production-ready
    - **1036+ Tests** - 66% coverage
    - **14 Enterprise Categories** - Full enterprise support

---

## 🎯 Quick Navigation

<div class="grid cards" markdown>

-   :material-bug:{ .lg } **Report Bugs**
    
    Found an issue? Let us know
    
    [:octicons-arrow-right-24: Report](#report-bugs)

-   :material-lightbulb:{ .lg } **Suggest Features**
    
    Have an idea? Share it
    
    [:octicons-arrow-right-24: Suggest](#suggest-features)

-   :material-code-braces:{ .lg } **Submit Code**
    
    Contribute code changes
    
    [:octicons-arrow-right-24: Contribute](#pull-request-process)

-   :material-book-edit:{ .lg } **Improve Docs**
    
    Enhance documentation
    
    [:octicons-arrow-right-24: Write](#improve-documentation)

</div>

<div align="center">

[![Contributors](https://img.shields.io/github/contributors/isathish/agenticaiframework)](https://github.com/isathish/agenticaiframework/graphs/contributors)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/isathish/agenticaiframework/pulls)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/isathish/agenticaiframework/blob/main/LICENSE)

</div>


## 👋 Welcome Contributors!

Thank you for your interest in contributing to AgenticAI Framework! This document provides guidelines and instructions for contributing to the project.


## 📋 Table of Contents

- [Community Guidelines](#community-guidelines)
- [Ways to Contribute](#ways-to-contribute)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Pull Request Process](#pull-request-process)
- [Coding Standards](#coding-standards)
- [Testing Guidelines](#testing-guidelines)
- [Documentation](#documentation)
- [Community](#community)


## 📜 Community Guidelines

We are committed to providing a welcoming and inclusive environment for all contributors. By participating in this project, you agree to:

- Be respectful and professional in all interactions
- Provide constructive feedback
- Accept constructive criticism gracefully
- Focus on what is best for the community
- Show empathy towards other community members

Please report any unacceptable behavior to the maintainers.


## 🎯 Ways to Contribute

### 🐛 Report Bugs

Found a bug? Help us fix it:

1. **Check existing issues** to avoid duplicates
2. **Use the bug report template**
3. **Provide detailed information**:
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment details
   - Error messages/logs
   - Code samples

[Report a Bug →](https://github.com/isathish/agenticaiframework/issues/new?template=bug_report.md)

### ✨ Suggest Features

Have an idea? Share it:

1. **Check existing feature requests**
2. **Use the feature request template**
3. **Explain the use case**
4. **Describe the proposed solution**

[Request a Feature →](https://github.com/isathish/agenticaiframework/issues/new?template=feature_request.md)

### 📖 Improve Documentation

Documentation is always welcome:

- Fix typos or unclear explanations
- Add examples and tutorials
- Improve API documentation
- Translate documentation

### 💻 Submit Code

Contribute code improvements:

- Fix bugs
- Implement features
- Optimize performance
- Add tests

### 🧪 Write Tests

Help improve test coverage:

- Unit tests
- Integration tests
- End-to-end tests
- Performance tests


## 🚀 Getting Started

### Prerequisites

- **Python 3.10+** (3.13+ recommended)
- **Git**
- **GitHub account**
- **Text editor/IDE** (VS Code, PyCharm, etc.)

### Fork and Clone

1. **Fork the repository** on GitHub
2. **Clone your fork**:

```bash
git clone https://github.com/YOUR_USERNAME/agenticaiframework.git
cd agenticaiframework
```

3. **Add upstream remote**:

```bash
git remote add upstream https://github.com/isathish/agenticaiframework.git
```


## 🛠 Development Setup

### 1. Create Virtual Environment

```bash
# Using venv
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Using conda
conda create -n agenticai python=3.11
conda activate agenticai
```

### 2. Install Dependencies

```bash
# Install in development mode with dev dependencies
pip install -e ".[dev]"

# Or install specific extras
pip install -e ".[dev,test,docs]"
```

### 3. Install Pre-commit Hooks

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

### 4. Verify Installation

```bash
# Run tests
pytest

# Check code style
ruff check .

# Check types
mypy agenticaiframework
```


## ✏️ Making Changes

### 1. Create a Branch

```bash
# Sync with upstream
git fetch upstream
git checkout main
git merge upstream/main

# Create feature branch
git checkout -b feature/amazing-feature

# Or bugfix branch
git checkout -b fix/bug-description
```

### Branch Naming Convention

- `feature/description` - New features
- `fix/description` - Bug fixes
- `docs/description` - Documentation changes
- `test/description` - Test additions/changes
- `refactor/description` - Code refactoring
- `perf/description` - Performance improvements

### 2. Make Your Changes

- Write clean, readable code
- Follow coding standards
- Add/update tests
- Update documentation
- Add docstrings

### 3. Commit Your Changes

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```bash
# Format: <type>(<scope>): <description>

git commit -m "feat(agents): add multi-agent collaboration"
git commit -m "fix(memory): resolve memory leak in cache"
git commit -m "docs(api): update API reference"
git commit -m "test(agents): add agent lifecycle tests"
```

**Commit Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `test`: Tests
- `refactor`: Code refactoring
- `perf`: Performance improvement
- `chore`: Maintenance


## 🔄 Pull Request Process

### 1. Push Your Changes

```bash
git push origin feature/amazing-feature
```

### 2. Create Pull Request

1. Go to your fork on GitHub
2. Click "Compare & pull request"
3. Fill out the PR template
4. Link related issues
5. Request reviews

### 3. PR Template Checklist

- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex code
- [ ] Documentation updated
- [ ] Tests added/updated
- [ ] All tests passing
- [ ] No merge conflicts

### 4. Code Review Process

- **Automated Checks**: CI/CD runs tests, linting, type checking
- **Peer Review**: At least one approval required
- **Maintainer Review**: Final review by maintainers
- **Changes Requested**: Address feedback and update PR

### 5. After Approval

- Maintainer will merge your PR
- Delete your feature branch
- Sync your fork

```bash
git checkout main
git pull upstream main
git push origin main
```


## 📝 Coding Standards

### Python Style Guide

Follow [PEP 8](https://pep8.org/) with these specifics:

```python
# Line length: 100 characters
# Indentation: 4 spaces
# Quotes: Double quotes for strings
# Import order: stdlib, third-party, local

# Good
def calculate_score(data: dict) -> float:
    """Calculate score from data.
    
    Args:
        data: Input data dictionary
        
    Returns:
        Calculated score
    """
    return sum(data.values()) / len(data)

# Bad
def calc(d):  # No type hints, no docstring
    return sum(d.values())/len(d)  # No spaces
```

### Code Formatting

We use automated formatters:

```bash
# Format code
ruff format .

# Check linting
ruff check .

# Fix auto-fixable issues
ruff check --fix .
```

### Type Hints

Use type hints for all functions:

```python
from typing import List, Dict, Optional

def process_agents(
    agents: List[Agent],
    config: Dict[str, Any],
    timeout: Optional[int] = None
) -> Dict[str, Any]:
    """Process agents with given configuration."""
    ...
```

### Docstrings

Use Google-style docstrings:

```python
def execute_task(self, task: Task, agent_id: str) -> TaskResult:
    """Execute a task using specified agent.
    
    Args:
        task: The task to execute
        agent_id: ID of the agent to use
        
    Returns:
        Result of task execution
        
    Raises:
        AgentNotFoundError: If agent_id doesn't exist
        TaskExecutionError: If task execution fails
        
    Example:
        ```python
        result = manager.execute_task(task, "agent_001")
        logger.info(result.output)
        ```
    """
    ...
```


## 🧪 Testing Guidelines

### Writing Tests

```python
import pytest
from agenticaiframework.agents import Agent

class TestAgent:
    """Test agent functionality."""
    
    def test_agent_creation(self):
        """Test agent can be created successfully."""
        agent = Agent(name="test_agent", role="tester")
        
        assert agent.name == "test_agent"
        assert agent.role == "tester"
        assert agent.status == "initialized"
    
    def test_agent_execution(self):
        """Test agent can execute tasks."""
        agent = Agent(name="test_agent", role="tester")
        result = agent.execute_task(lambda: "success")
        
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_async_execution(self):
        """Test async task execution."""
        agent = Agent(name="test_agent", role="tester")
        result = await agent.execute_task_async(async_function)
        
        assert result is not None
```

### Test Structure

```
tests/
├── unit/               # Unit tests
│   ├── test_agents.py
│   ├── test_tasks.py
│   └── test_memory.py
├── integration/        # Integration tests
│   ├── test_workflows.py
│   └── test_pipelines.py
├── e2e/               # End-to-end tests
│   └── test_scenarios.py
├── conftest.py        # Pytest fixtures
└── __init__.py
```

### Running Tests

```bash
# Run all tests
pytest

# Run specific file
pytest tests/unit/test_agents.py

# Run specific test
pytest tests/unit/test_agents.py::TestAgent::test_agent_creation

# Run with coverage
pytest --cov=agenticaiframework --cov-report=html

# Run with markers
pytest -m "not slow"

# Verbose output
pytest -v

# Stop on first failure
pytest -x
```

### Test Coverage

Target: **80%+ coverage**

```bash
# Generate coverage report
pytest --cov=agenticaiframework --cov-report=term-missing

# HTML report
pytest --cov=agenticaiframework --cov-report=html
open htmlcov/index.html
```


## 📚 Documentation

### Code Documentation

- **Docstrings**: All public APIs
- **Type hints**: All function signatures
- **Comments**: Complex logic only
- **Examples**: Usage examples in docstrings

### User Documentation

Located in `docs/`:

```
docs/
├── index.md              # Home page
├── quick-start.md        # Getting started
├── agents.md             # Agent guide
├── tasks.md              # Task guide
├── API_REFERENCE.md      # API docs
└── examples/             # Examples
```

### Building Documentation

```bash
# Install docs dependencies
pip install -e ".[docs]"

# Build docs
mkdocs build

# Serve locally
mkdocs serve

# Visit http://localhost:8000
```

### Documentation Style

- Clear, concise writing
- Code examples for concepts
- Visual aids (diagrams, tables)
- Links to related content
- Beginner-friendly


## 🌟 Community

### Communication Channels

- **GitHub Discussions**: [Ask questions](https://github.com/isathish/agenticaiframework/discussions)
- **GitHub Issues**: [Report bugs, request features](https://github.com/isathish/agenticaiframework/issues)
- **Discord**: Coming soon!
- **Twitter**: [@AgenticAI](https://twitter.com/AgenticAI) (Coming soon)

### Getting Help

1. **Search documentation**
2. **Check existing issues/discussions**
3. **Ask in discussions**
4. **Open an issue if needed**

### Recognition

Contributors are recognized:

- Recognition in our documentation and release notes
- Mentioned in release notes
- Featured in documentation
- Hall of Fame for top contributors


## 🎉 Your First Contribution

New to open source? Here's how to start:

1. **Find a good first issue**: Look for `good-first-issue` label
2. **Comment on the issue**: Let others know you're working on it
3. **Ask questions**: Don't hesitate to ask for help
4. **Submit small PRs**: Start with documentation or small fixes
5. **Learn and improve**: Each contribution teaches something new

[View Good First Issues →](https://github.com/isathish/agenticaiframework/labels/good-first-issue)


## 📋 Checklist

Before submitting your PR:

- [ ] Code follows style guidelines
- [ ] Type hints added
- [ ] Docstrings added/updated
- [ ] Tests added/updated
- [ ] All tests passing locally
- [ ] Documentation updated
- [ ] CHANGELOG.md updated (if applicable)
- [ ] Commit messages follow convention
- [ ] Branch up to date with main


## 🙏 Thank You!

Every contribution, no matter how small, makes AgenticAI Framework better. Thank you for being part of our community!


## 📞 Questions?

- **Documentation**: [https://isathish.github.io/agenticaiframework/](https://isathish.github.io/agenticaiframework/)
- **Discussions**: [GitHub Discussions](https://github.com/isathish/agenticaiframework/discussions)
- **Email**: [contributors@agenticai.dev](mailto:contributors@agenticai.dev)


<div align="center">

**Happy Contributing! 🚀**

**[⬆ Back to Top](#-contributing-to-agenticai-framework)**

</div>
