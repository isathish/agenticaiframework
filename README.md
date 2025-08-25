<!-- PROJECT LOGO -->
<br />
<div align="center">
  <a href="https://isathish.github.io/agenticaiframework/">
    <img src="https://img.shields.io/pypi/v/agenticaiframework?color=blue&label=PyPI%20Version&logo=python&logoColor=white" alt="PyPI Version">
  </a>
  <a href="https://pypi.org/project/agenticaiframework/">
    <img src="https://img.shields.io/pypi/dm/agenticaiframework?color=green&label=Downloads&logo=python&logoColor=white" alt="Downloads">
  </a>
  <a href="https://github.com/isathish/agenticaiframework/actions">
    <img src="https://img.shields.io/github/actions/workflow/status/isathish/agenticaiframework/python-package.yml?branch=main&label=Build&logo=github" alt="Build Status">
  </a>

</div>


<div align="center">
  <a href="https://isathish.github.io/agenticaiframework">
    <img src="https://img.shields.io/badge/Documentation-Online-blue?logo=readthedocs&logoColor=white" alt="Documentation">
  </a>

</div>
---
# AgenticAI Framework

AgenticAI Framework (`agenticaiframework`) is a **Python SDK** for building **agentic applications** with advanced orchestration, monitoring, multimodal capabilities, and enterprise-grade scalability.  
It provides a modular, extensible architecture for creating intelligent agents that can interact, reason, and execute tasks across multiple domains.

---

## 🚀 Features

- **Python-based SDK** for building agentic applications
- **Lightweight, high-performance agents** for efficient execution
- **Built-in security** mechanisms
- **Integrated monitoring and observability**
- **Fine-grained configurable parameters**
- **Single and multiple agent support**
- **Flexible process orchestration** (sequential, parallel, hybrid)
- **Extensible architecture** with hubs for agents, prompts, tools, guardrails, and LLMs
- **Comprehensive memory management**
- **Multiple communication protocols** (HTTP, SSE, STDIO, WebSockets, gRPC, MQ)
- **Configurable guardrails, evaluation, and knowledge retrieval**
- **Scalable and modular design**
- **Multimodal capabilities**: text, images, voice, video
- **Cross-platform deployment**: cloud, on-premise, edge
- **Extensive integration support**
- **Security and compliance ready**

---

## 📦 Installation

```bash
pip install agenticaiframework
```

---

## ⚡ Quick Start

```python
from agenticaiframework import Agent, AgentManager

# Create an agent
agent = Agent(
    name="ExampleAgent",
    role="assistant",
    capabilities=["text"],
    config={"temperature": 0.7}
)

# Manage agents
manager = AgentManager()
manager.register_agent(agent)

# Start the agent
agent.start()
```

---

## 📚 Usage Examples

### 1. Creating and Running an Agent
```python
from agenticaiframework import Agent

agent = Agent(name="HelperBot", role="assistant", capabilities=["text"])
agent.start()
```

### 2. Using the Hub to Register and Retrieve Agents
```python
from agenticaiframework.hub import register_agent, get_agent
from agenticaiframework import Agent

agent = Agent(name="DataBot", role="data_processor", capabilities=["data"])
register_agent(agent)

retrieved_agent = get_agent("DataBot")
print(retrieved_agent.name)  # Output: DataBot
```

### 3. Memory Management
```python
from agenticaiframework.memory import Memory

memory = Memory()
memory.store("user_name", "Alice")
print(memory.retrieve("user_name"))  # Output: Alice
```

### 4. Running Processes
```python
from agenticaiframework.processes import run_process

def greet():
    return "Hello, World!"

result = run_process(greet)
print(result)  # Output: Hello, World!
```

---

## 🛠 Configuration

You can configure agents and the framework using:
- **Programmatic configuration** via `agenticaiframework.configurations`
- **Environment variables**
- **Configuration files**

Example:
```python
from agenticaiframework.configurations import set_config

set_config("max_concurrent_tasks", 5)
```

---

## 🧪 Testing

Run the test suite with:
```bash
pytest
```

Run with coverage:
```bash
pytest --cov=agenticaiframework --cov-report=term-missing
```

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
