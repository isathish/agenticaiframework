---
title: Usage Guide
description: Comprehensive usage guide for AgenticAI Framework v2.0
tags:
  - usage
  - guide
  - tutorial
---

# :material-book-open: Usage Guide

This guide covers everyday patterns for building AI agent systems with
**AgenticAI Framework v2.0**.

---

## Installation

```bash
pip install agenticaiframework
```

**Requirements**: Python >= 3.10

---

## Core Imports

```python
from agenticaiframework import (
    Agent,
    Task,
    Process,
    Hub,
    MonitoringSystem,
    KnowledgeRetriever,
    Workflow,
)
```

---

## Creating Agents

```python
from agenticaiframework import Agent

agent = Agent(
    name="researcher",
    role="Research Assistant",
    goal="Find and summarise relevant information",
    backstory="Expert researcher with deep analytical skills",
)
```

---

## Defining Tasks

```python
from agenticaiframework import Task

task = Task(
    description="Summarise the latest AI research papers",
    agent=agent,
    expected_output="A concise summary of 3-5 key papers",
)
```

---

## Running Processes

### Sequential

```python
from agenticaiframework import Process

proc = Process(name="research_pipeline", strategy="sequential")
proc.add_task(fetch_papers, "arxiv")
proc.add_task(summarise, papers)
results = proc.execute()
```

### Parallel

```python
proc = Process(name="multi_fetch", strategy="parallel", max_workers=4)
for source in ["arxiv", "scholar", "semantic"]:
    proc.add_task(fetch_papers, source)
results = proc.execute()
```

---

## Using the Hub

```python
from agenticaiframework import Hub

hub = Hub()

# Register components
hub.register("agents", "researcher", agent)
hub.register("tools", "search", search_tool)

# Retrieve
researcher = hub.get("agents", "researcher")
```

---

## Knowledge Retrieval

```python
from agenticaiframework import KnowledgeRetriever

retriever = KnowledgeRetriever()
retriever.register_source("docs", my_search_function)

result = retriever.retrieve("docs", "How to configure agents?")
# Cached automatically on second call
```

---

## Monitoring

```python
from agenticaiframework import MonitoringSystem

monitor = MonitoringSystem()
monitor.record_metric("latency_ms", 42.5)
monitor.log_event("task_completed", {"task": "summarise"})

metrics = monitor.get_metrics()
events = monitor.get_events()
gc_stats = monitor.get_gc_stats()
```

---

## MCP Tools

```python
from agenticaiframework.mcp_tools import MCPTool, MCPToolManager

tool = MCPTool(
    id="calculator",
    name="Calculator",
    capability="Perform arithmetic operations",
    execute_fn=lambda a, b: a + b,
)

manager = MCPToolManager()
manager.register_tool(tool)
result = manager.execute_tool("calculator", a=5, b=3)
```

---

## Workflows

```python
from agenticaiframework import Workflow

workflow = Workflow(name="data_pipeline")
workflow.add_step("extract", extract_fn)
workflow.add_step("transform", transform_fn)
workflow.add_step("load", load_fn)

results = workflow.run()
```

---

## Configuration

```python
from agenticaiframework import Configurations

config = Configurations()
config.set("llm.provider", "openai")
config.set("llm.model", "gpt-4o")
config.set("llm.temperature", 0.7)

provider = config.get("llm.provider")
```

---

## Guardrails

```python
from agenticaiframework.guardrails import InputGuardrail, OutputGuardrail

# Validate inputs before agent processing
input_guard = InputGuardrail(
    name="length_check",
    validator=lambda text: len(text) < 10000,
    error_message="Input too long",
)

# Validate outputs before returning to user
output_guard = OutputGuardrail(
    name="pii_check",
    validator=lambda text: "SSN" not in text,
    error_message="Output contains PII",
)
```

---

## Error Handling

```python
from agenticaiframework.exceptions import (
    AgenticAIError,
    ConfigurationError,
    ProcessExecutionError,
)

try:
    results = process.execute()
except ProcessExecutionError as e:
    logger.error("Process failed: %s", e)
except AgenticAIError as e:
    logger.error("Framework error: %s", e)
```

---

## Logging

The framework uses Python's built-in `logging` module. Configure the log
level to control output:

```python
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agenticaiframework")
logger.setLevel(logging.DEBUG)
```

---

## Best Practices

1. **Use structured logging** — the framework logs via `logging`, not `print()`.
2. **Register components in the Hub** — enables discovery and dependency injection.
3. **Set `max_workers` explicitly** for parallel processes.
4. **Clear caches** after data changes (`retriever.clear_cache()`).
5. **Handle exceptions** at the process level for graceful degradation.
6. **Use `__slots__`** in custom classes for memory-efficient agents.

---

## Related Documentation

- [Quick Start](quick-start.md) — get started in 5 minutes
- [Configuration](CONFIGURATION.md) — framework configuration
- [API Reference](API_REFERENCE.md) — full API docs
- [Examples](EXAMPLES.md) — code samples
- [Best Practices](best-practices.md) — production patterns
