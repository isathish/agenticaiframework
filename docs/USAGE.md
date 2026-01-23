---
title: Usage Guide
description: Complete guide to using AgenticAI Framework for building AI agent applications
tags:
  - usage
  - guide
  - getting-started
  - tutorial
---

# 📖 Usage Guide

<div align="center">

**Complete guide to using AgenticAI Framework (380+ Modules)**

[![Modules](https://img.shields.io/badge/modules-380%2B-brightgreen.svg)](https://github.com/isathish/agenticaiframework)
[![Enterprise](https://img.shields.io/badge/enterprise-237%20modules-gold.svg)](https://github.com/isathish/agenticaiframework)
[![PyPI Version](https://img.shields.io/pypi/v/agenticaiframework?color=blue&label=PyPI&logo=python&logoColor=white)](https://pypi.org/project/agenticaiframework/)

</div>

!!! success "Enterprise Framework"
    Part of **237 enterprise modules** with comprehensive features. See [Enterprise Documentation](enterprise.md).

---

## 🚀 Quick Navigation

<div class="grid cards" markdown>

-   :material-package-variant:{ .lg } **Installation**
    
    Get started in minutes
    
    [:octicons-arrow-right-24: Install](#installation)

-   :material-code-braces:{ .lg } **Quick Start**
    
    Your first agent
    
    [:octicons-arrow-right-24: Start Coding](#basic-usage)

-   :material-school:{ .lg } **Examples**
    
    25+ working examples
    
    [:octicons-arrow-right-24: View Examples](examples/full_examples_index.md)

-   :material-api:{ .lg } **API Reference**
    
    Complete documentation
    
    [:octicons-arrow-right-24: API Docs](API_REFERENCE.md)

</div>

---

## 📦 Installation

Install AgenticAI from PyPI:

```bash
pip install agenticaiframework
```

Or install from source:

```bash
git clone https://github.com/isathish/agenticaiframework.git
cd agenticaiframework
pip install -e .
```

---

## 🎯 Basic Usage

### Creating and Running an Agent

```python
from agenticaiframework import Agent, AgentManager

# Create an agent
agent = Agent(
    name="MyAgent",
    role="assistant",
    capabilities=["text", "analysis"]
)

# Register with manager
manager = AgentManager()
manager.register_agent(agent)

# Start the agent
agent.start()
result = agent.act("Analyze this text for sentiment")
print(result)
```

---

## ⚙️ Configuration

Configure AgenticAI programmatically or via environment variables:

```python
from agenticaiframework.configurations import ConfigurationManager

config = ConfigurationManager()
config.set_config("LLM", {"provider": "openai", "model": "gpt-4"})
config.set_config("Logging", {"log_level": "INFO"})
```

Or via environment variables:

```bash
export OPENAI_API_KEY=your_api_key_here
```

---

## 🔧 Using Tools

```python
from agenticaiframework.tools import tool_registry

# List available tools
print(tool_registry.list_tools())

# Get and use a tool
tool = tool_registry.get_tool("web_search")
result = tool.run({"query": "AI news"})
```

---

## 🧠 Memory Usage

```python
from agenticaiframework.memory import MemoryManager

memory = MemoryManager()

# Store data
memory.store("user_preference", "dark_mode")

# Retrieve data
pref = memory.retrieve("user_preference")
print(pref)
```

---

## 📋 Running Tasks

```python
from agenticaiframework import Task

def analyze_data(inputs):
    return {"result": f"Analyzed: {inputs['data']}"}

task = Task(
    name="DataAnalysis",
    objective="Analyze user data",
    executor=analyze_data,
    inputs={"data": "sample_data.csv"}
)

result = task.run()
print(result)
```

---

## 🤝 Multi-Agent Collaboration

Orchestrate multiple agents for complex tasks:

```python
from agenticaiframework import Agent, AgentManager

# Create specialized agents
researcher = Agent(name="Researcher", role="research", capabilities=["web", "text"])
summarizer = Agent(name="Summarizer", role="summarize", capabilities=["text"])

manager = AgentManager()
manager.register_agent(researcher)
manager.register_agent(summarizer)

# Agents can collaborate
research_result = researcher.act("Find the latest AI research papers")
summary = summarizer.act(f"Summarize: {research_result}")
```

---

## 🚀 Deployment

### Docker Deployment

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```

### Cloud Deployment

Deploy to AWS Lambda, Google Cloud Functions, or Azure Functions by packaging the code and dependencies.

---

## 🔒 Security

- Always validate and sanitize inputs to agents
- Use guardrails to prevent unsafe actions
- Store API keys securely using environment variables
- Limit network access for agents in untrusted environments

---

## ⚡ Performance Optimization

- Use caching for repeated computations
- Optimize prompt templates for LLMs to reduce token usage
- Use batch processing for large datasets
- Monitor performance using the monitoring module

---

## 🧪 Testing

Run tests with:

```bash
pytest tests/ -v
```

With coverage:

```bash
pytest tests/ --cov=agenticaiframework --cov-report=html
```

---

## 📚 Additional Resources

- [Quick Start Guide](quick-start.md)
- [API Reference](API_REFERENCE.md)
- [Configuration Guide](CONFIGURATION.md)
- [Extending the Framework](EXTENDING.md)
- [Examples](EXAMPLES.md)
- [Troubleshooting](TROUBLESHOOTING.md)
