---
tags:
  - usage
  - guide
  - getting-started
  - tutorial
---

# 📖 Usage Guide

<div align="center">

**Complete guide to using AgenticAI Framework**

[![PyPI Version](https://img.shields.io/pypi/v/agenticaiframework?color=blue&label=PyPI&logo=python&logoColor=white)](https://pypi.org/project/agenticaiframework/)
[![Downloads](https://img.shields.io/pypi/dm/agenticaiframework?color=green&label=Downloads&logo=python&logoColor=white)](https://pypi.org/project/agenticaiframework/)
[![Build](https://img.shields.io/github/actions/workflow/status/isathish/agenticaiframework/python-package.yml?branch=main&label=Build&logo=github)](https://github.com/isathish/agenticaiframework/actions)
[![Documentation](https://img.shields.io/badge/Documentation-Online-blue?logo=readthedocs&logoColor=white)](https://isathish.github.io/agenticaiframework/)

</div>

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

## 📦 Installation


## 11. Advanced Usage Patterns

### Multi-Agent Collaboration
You can orchestrate multiple agents to work together on complex tasks.

```python
from agenticaiframework import Agent, AgentManager

agent1 = Agent(name="Researcher", role="research", capabilities=["text"])
agent2 = Agent(name="Summarizer", role="summarize", capabilities=["text"])

manager = AgentManager()
manager.register_agent(agent1)
manager.register_agent(agent2)

research_result = agent1.act("Find the latest AI research papers on reinforcement learning.")
summary = agent2.act(f"Summarize this: {research_result}")
print(summary)
```

### Asynchronous Processing
For I/O-bound tasks, use asynchronous processes to improve performance.

```python
import asyncio
from agenticaiframework.processes import run_process_async

async def async_task():
    return "Completed async task"

result = asyncio.run(run_process_async(async_task))
print(result)
```

### Integrating External APIs
Agents can call external APIs as part of their workflow.

```python
import requests
from agenticaiframework.agents import Agent

class WeatherAgent(Agent):
    def act(self, location):
        response = requests.get(f"https://api.weatherapi.com/v1/current.json?q={location}&key=YOUR_KEY")
        return response.json()

weather_agent = WeatherAgent(name="WeatherBot", role="weather", capabilities=["data"])
print(weather_agent.act("New York"))
```


## 12. Deployment Scenarios

### Local Development
- Install dependencies with `pip install -e .[dev]`
- Run tests locally before deployment.

### Docker Deployment
Create a `Dockerfile`:
```dockerfile
FROM python:3.10
WORKDIR /app
COPY . .
RUN pip install .
CMD ["python", "main.py"]
```

### Cloud Deployment
Deploy to AWS Lambda, Google Cloud Functions, or Azure Functions by packaging the code and dependencies.


## 13. Security Considerations

- Always validate and sanitize inputs to agents.
- Use guardrails to prevent unsafe actions.
- Store API keys securely using environment variables or secret managers.
- Limit network access for agents running in untrusted environments.


## 14. Performance Optimization

- Use caching for repeated computations.
- Optimize prompt templates for LLMs to reduce token usage.
- Use batch processing for large datasets.
- Profile and monitor agent performance using `monitoring.py`.


## 15. Troubleshooting Complex Workflows

- Enable debug logging: `set_config("log_level", "DEBUG")`
- Break down workflows into smaller steps for easier debugging.
- Use `pytest -v` for verbose test output.


## 16. Contributing to AgenticAI

We welcome contributions!  
1. Fork the repository.  
2. Create a feature branch.  
3. Implement your changes with tests.  
4. Submit a pull request.  


## 17. Additional Resources

- [API Reference](API_REFERENCE.md)
- [Configuration Guide](CONFIGURATION.md)
- [Extending the Framework](EXTENDING.md)
- [Examples](EXAMPLES.md)
- [Troubleshooting](TROUBLESHOOTING.md)
# Using AgenticAI

This guide explains how to install, configure, and use the **AgenticAI** package with practical examples.


## 1. Installation

Install AgenticAI from PyPI:

```bash
pip install agenticaiframework
```

Or install from source:

```bash
git clone https://github.com/isathish/AgenticAI.git
cd AgenticAI
pip install .
```


## 2. Basic Usage

### Creating and Running an Agent

```python
from agenticaiframework.agents import Agent
from agenticaiframework.hub import register_agent, get_agent

class EchoAgent(Agent):
    def act(self, input_data):
        return f"Echo: {input_data}"

register_agent("echo", EchoAgent)

agent = get_agent("echo")
print(agent.act("Hello World"))
```


## 3. Using Built-in Agents

AgenticAI comes with prebuilt agents. You can load them via the hub:

```python
from agenticaiframework.hub import get_agent

agent = get_agent("default_agent")
response = agent.act("Summarize this text.")
print(response)
```


## 4. Configuring the System

Edit `configurations.py` or pass configuration at runtime:

```python
from agenticaiframework.configurations import set_config

set_config("llm_provider", "openai")
set_config("api_key", "your_api_key_here")
```


## 5. Using Tools

```python
from agenticaiframework.hub import get_tool

sentiment_tool = get_tool("sentiment_analysis")
result = sentiment_tool("I love this product!")
print(result)
```


## 6. Running Processes

```python
from agenticaiframework.processes import run_process

result = run_process("data_analysis", {"dataset": "data.csv"})
print(result)
```


## 7. Memory Usage

```python
from agenticaiframework.memory import Memory

mem = Memory()
mem.store("user_name", "Alice")
print(mem.retrieve("user_name"))
```


## 8. Example Workflow

```python
from agenticaiframework.hub import get_agent, get_tool

agent = get_agent("default_agent")
tool = get_tool("sentiment_analysis")

text = "The movie was fantastic!"
analysis = tool(text)
response = agent.act(f"Summarize the sentiment: {analysis}")
print(response)
```


## 9. Testing

Run tests with:

```bash
pytest
```


## 10. Additional Resources

- [Extending AgenticAI](EXTENDING.md)
- [Examples](EXAMPLES.md)
