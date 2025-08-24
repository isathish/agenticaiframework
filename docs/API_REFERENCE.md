# AgenticAI API Reference

This document provides a reference for the main classes, functions, and modules in **AgenticAI**.

---

## 1. Modules Overview

- **agenticai.agents** – Agent base classes and implementations.
- **agenticai.communication** – Communication utilities.
- **agenticai.configurations** – Configuration management.
- **agenticai.evaluation** – Evaluation and scoring.
- **agenticai.guardrails** – Safety and compliance checks.
- **agenticai.hub** – Registry for agents, tools, and processes.
- **agenticai.knowledge** – Knowledge base management.
- **agenticai.llms** – LLM integrations.
- **agenticai.mcp_tools** – MCP tool integrations.
- **agenticai.memory** – Memory management.
- **agenticai.monitoring** – Monitoring and logging.
- **agenticai.processes** – Workflow orchestration.
- **agenticai.prompts** – Prompt templates.
- **agenticai.tasks** – Task management.

---

## 2. Core Classes

### `Agent`
**Location:** `agenticai.agents`

**Methods:**
- `act(input_data)` – Perform an action based on input.
- `observe(data)` – Observe environment or input.
- `plan()` – Plan next steps.

---

### `Memory`
**Location:** `agenticai.memory`

**Methods:**
- `store(key, value)` – Store a value.
- `retrieve(key)` – Retrieve a value.
- `clear()` – Clear memory.

---

### `Hub`
**Location:** `agenticai.hub`

**Functions:**
- `register_agent(name, cls)` – Register an agent.
- `get_agent(name)` – Retrieve an agent instance.
- `register_tool(name, func)` – Register a tool.
- `get_tool(name)` – Retrieve a tool.

---

## 3. Utility Functions

### `set_config(key, value)`
**Location:** `agenticai.configurations`

Set a configuration value.

---

### `run_process(name, params)`
**Location:** `agenticai.processes`

Run a registered process.

---

## 4. Example Usage

```python
from agenticai.hub import get_agent

agent = get_agent("default_agent")
print(agent.act("Hello"))
```

---

## 5. Notes

- All public APIs are subject to semantic versioning.
- Internal APIs may change without notice.
