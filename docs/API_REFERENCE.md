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
