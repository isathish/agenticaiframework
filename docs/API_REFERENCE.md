# AgenticAI API Reference

This document provides a reference for the main classes, functions, and modules in **AgenticAI**.

---

## 1. Modules Overview

- **agenticaiframeworkframework.agents** – Agent base classes and implementations.
- **agenticaiframeworkframework.communication** – Communication utilities.
- **agenticaiframeworkframework.configurations** – Configuration management.
- **agenticaiframeworkframework.evaluation** – Evaluation and scoring.
- **agenticaiframeworkframework.guardrails** – Safety and compliance checks.
- **agenticaiframeworkframework.hub** – Registry for agents, tools, and processes.
- **agenticaiframeworkframework.knowledge** – Knowledge base management.
- **agenticaiframeworkframework.llms** – LLM integrations.
- **agenticaiframeworkframework.mcp_tools** – MCP tool integrations.
- **agenticaiframeworkframework.memory** – Memory management.
- **agenticaiframeworkframework.monitoring** – Monitoring and logging.
- **agenticaiframeworkframework.processes** – Workflow orchestration.
- **agenticaiframeworkframework.prompts** – Prompt templates.
- **agenticaiframeworkframework.tasks** – Task management.

---

## 2. Core Classes

### `Agent`
**Location:** `agenticaiframeworkframework.agents`

**Methods:**
- `act(input_data)` – Perform an action based on input.
- `observe(data)` – Observe environment or input.
- `plan()` – Plan next steps.

---

### `Memory`
**Location:** `agenticaiframeworkframework.memory`

**Methods:**
- `store(key, value)` – Store a value.
- `retrieve(key)` – Retrieve a value.
- `clear()` – Clear memory.

---

### `Hub`
**Location:** `agenticaiframeworkframework.hub`

**Functions:**
- `register_agent(name, cls)` – Register an agent.
- `get_agent(name)` – Retrieve an agent instance.
- `register_tool(name, func)` – Register a tool.
- `get_tool(name)` – Retrieve a tool.

---

## 3. Utility Functions

### `set_config(key, value)`
**Location:** `agenticaiframeworkframework.configurations`

Set a configuration value.

---

### `run_process(name, params)`
**Location:** `agenticaiframeworkframework.processes`

Run a registered process.

---

## 4. Example Usage

```python
from agenticaiframeworkframework.hub import get_agent

agent = get_agent("default_agent")
print(agent.act("Hello"))
```

---

## 5. Notes

- All public APIs are subject to semantic versioning.
- Internal APIs may change without notice.
