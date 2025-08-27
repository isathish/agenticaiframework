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
  <a href="https://isathish.github.io/agenticaiframework/">
    <img src="https://img.shields.io/badge/Documentation-Online-blue?logo=readthedocs&logoColor=white" alt="Documentation">
  </a>
</div>

---

## 6. Detailed Module API

### agenticaiframework.agents
- `Agent` – Base class for all agents.
- `AgentManager` – Manages multiple agents.

### agenticaiframework.communication
- `send_message()` – Send a message to another agent or system.
- `receive_message()` – Receive a message.

### agenticaiframework.configurations
- `set_config(key, value)` – Set a configuration value.
- `get_config(key)` – Retrieve a configuration value.

### agenticaiframework.evaluation
- `evaluate_response(response)` – Evaluate the quality of a response.

### agenticaiframework.guardrails
- `add_guardrail(func)` – Add a guardrail function.
- `remove_guardrail(func)` – Remove a guardrail.

### agenticaiframework.hub
- `register_agent(name, cls)` – Register an agent.
- `get_agent(name)` – Retrieve an agent.
- `register_tool(name, func)` – Register a tool.
- `get_tool(name)` – Retrieve a tool.

### agenticaiframework.knowledge
- `KnowledgeBase` – Manage documents and search.

### agenticaiframework.llms
- `OpenAIModel` – Example LLM integration.

### agenticaiframework.mcp_tools
- `load_tool(name)` – Load an MCP tool.

### agenticaiframework.memory
- `Memory` – Store and retrieve key-value pairs.

### agenticaiframework.monitoring
- `log_event(message, level)` – Log an event.

### agenticaiframework.processes
- `run_process(name, params)` – Run a process.
- `run_process_async(func)` – Run a process asynchronously.

### agenticaiframework.prompts
- `PromptTemplate` – Manage prompt templates.

### agenticaiframework.tasks
- `Task` – Define and manage tasks.

---

## 7. Advanced Usage Examples

### Using Multiple Modules Together
```python
from agenticaiframework import Agent
from agenticaiframework.hub import register_agent, get_agent, register_tool
from agenticaiframework.memory import Memory

class EchoAgent(Agent):
    def act(self, input_data):
        return f"Echo: {input_data}"

register_agent("echo", EchoAgent)

memory = Memory()
memory.store("greeting", "Hello")

agent = get_agent("echo")
print(agent.act(memory.retrieve("greeting")))
```

### Custom Process with Guardrails
```python
from agenticaiframework.guardrails import add_guardrail
from agenticaiframework.processes import run_process

def no_numbers(input_data):
    if any(char.isdigit() for char in input_data):
        raise ValueError("Numbers are not allowed!")
    return input_data

add_guardrail(no_numbers)

def greet():
    return "Hello, World!"

print(run_process(greet))
```

---

## 8. Notes on API Stability

- Public APIs follow semantic versioning.
- Experimental APIs are marked in the documentation and may change.
# AgenticAI API Reference

This document provides a reference for the main classes, functions, and modules in **AgenticAI**.

---

## 1. Modules Overview

- **agenticaiframework.agents** – Agent base classes and implementations.
- **agenticaiframework.communication** – Communication utilities.
- **agenticaiframework.configurations** – Configuration management.
- **agenticaiframework.evaluation** – Evaluation and scoring.
- **agenticaiframework.guardrails** – Safety and compliance checks.
- **agenticaiframework.hub** – Registry for agents, tools, and processes.
- **agenticaiframework.knowledge** – Knowledge base management.
- **agenticaiframework.llms** – LLM integrations.
- **agenticaiframework.mcp_tools** – MCP tool integrations.
- **agenticaiframework.memory** – Memory management.
- **agenticaiframework.monitoring** – Monitoring and logging.
- **agenticaiframework.processes** – Workflow orchestration.
- **agenticaiframework.prompts** – Prompt templates.
- **agenticaiframework.tasks** – Task management.

---

## 2. Core Classes

### `Agent`
**Location:** `agenticaiframework.agents`

**Methods:**
- `act(input_data)` – Perform an action based on input.
- `observe(data)` – Observe environment or input.
- `plan()` – Plan next steps.

---

### `Memory`
**Location:** `agenticaiframework.memory`

**Methods:**
- `store(key, value)` – Store a value.
- `retrieve(key)` – Retrieve a value.
- `clear()` – Clear memory.

---

### `Hub`
**Location:** `agenticaiframework.hub`

**Functions:**
- `register_agent(name, cls)` – Register an agent.
- `get_agent(name)` – Retrieve an agent instance.
- `register_tool(name, func)` – Register a tool.
- `get_tool(name)` – Retrieve a tool.

---

## 3. Utility Functions

### `set_config(key, value)`
**Location:** `agenticaiframework.configurations`

Set a configuration value.

---

### `run_process(name, params)`
**Location:** `agenticaiframework.processes`

Run a registered process.

---

## 4. Example Usage

```python
from agenticaiframework.hub import get_agent

agent = get_agent("default_agent")
print(agent.act("Hello"))
```

---

## 5. Notes

- All public APIs are subject to semantic versioning.
- Internal APIs may change without notice.
