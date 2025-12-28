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


## 9. Creating Custom Communication Protocols

You can extend `communication.py` to support new protocols.

Example: Adding MQTT support
```python
import paho.mqtt.client as mqtt

class MQTTCommunication:
    def __init__(self, broker, port):
        self.client = mqtt.Client()
        self.client.connect(broker, port)

    def publish(self, topic, message):
        self.client.publish(topic, message)

    def subscribe(self, topic, callback):
        self.client.subscribe(topic)
        self.client.on_message = lambda client, userdata, msg: callback(msg.payload.decode())
```


## 10. Adding New Process Types

Extend `processes.py` to add new orchestration patterns.

Example: Conditional process execution
```python
def conditional_process(condition, process_a, process_b):
    if condition():
        return process_a()
    else:
        return process_b()
```


## 11. Extending Knowledge Base

Add new retrieval strategies in `knowledge.py`:
```python
class CustomKnowledgeBase:
    def __init__(self):
        self.data = {}

    def add_document(self, key, content):
        self.data[key] = content

    def search(self, query):
        return [v for k, v in self.data.items() if query.lower() in v.lower()]
```


## 12. Advanced Guardrails

Implement multi-step guardrails:
```python
from agenticaiframework.guardrails import add_guardrail

def profanity_filter(input_data):
    banned_words = ["badword"]
    for word in banned_words:
        if word in input_data.lower():
            raise ValueError("Inappropriate content detected!")
    return input_data

add_guardrail(profanity_filter)
```


## 13. Packaging Extensions

- Place your extensions in a separate module.
- Add `__init__.py` to make it importable.
- Document your extension in `EXTENDING.md`.


## 14. Testing Extensions

- Write unit tests for each new feature.
- Use mocks for external API calls.
- Run `pytest --cov` to ensure coverage.
# Extending AgenticAI

This guide explains how to extend the **AgenticAI** package to add new capabilities, integrate with external systems, and customize its behavior.


## 1. Understanding the Architecture

AgenticAI is organized into several core modules:

- **agents.py** – Defines agent classes and their orchestration logic.
- **communication.py** – Handles inter-agent and external communication.
- **configurations.py** – Manages configuration settings.
- **evaluation.py** – Provides evaluation and scoring mechanisms.
- **guardrails.py** – Implements safety and compliance checks.
- **hub.py** – Central registry for agents, tools, and processes.
- **knowledge.py** – Manages knowledge bases and retrieval.
- **llms.py** – Interfaces with large language models.
- **mcp_tools.py** – Integrates with Model Context Protocol tools.
- **memory.py** – Handles short-term and long-term memory.
- **monitoring.py** – Tracks performance and logs.
- **processes.py** – Defines workflows and process orchestration.
- **prompts.py** – Stores and manages prompt templates.
- **tasks.py** – Defines and manages tasks.


## 2. Adding a New Agent

1. Create a new class in `agenticaiframework/agents.py` or a new file in `agenticaiframework/agents/` if modularizing.
2. Inherit from the base `Agent` class.
3. Implement required methods such as `act()`, `observe()`, and `plan()`.
4. Register the agent in `hub.py` so it can be discovered.

**Example:**
```python
from agenticaiframework.agents import Agent
from agenticaiframework.hub import register_agent

class MyCustomAgent(Agent):
    def act(self, input_data):
        return f"Processed: {input_data}"

register_agent("my_custom_agent", MyCustomAgent)
```


## 3. Adding a New Tool

1. Create a new function or class in `mcp_tools.py`.
2. Follow the MCP tool interface requirements.
3. Register the tool in `hub.py`.

**Example:**
```python
from agenticaiframework.hub import register_tool

def sentiment_analysis_tool(text):
    # Implement sentiment analysis logic
    return {"sentiment": "positive"}

register_tool("sentiment_analysis", sentiment_analysis_tool)
```


## 4. Extending Memory

To add a new memory backend:

1. Create a new class in `memory.py`.
2. Implement methods like `store()`, `retrieve()`, and `clear()`.
3. Update configuration to use the new backend.


## 5. Extending LLM Integrations

To integrate a new LLM provider:

1. Add a new class in `llms.py`.
2. Implement the `generate()` method.
3. Update configuration to select the new provider.


## 6. Adding Guardrails

To add new safety checks:

1. Add a function in `guardrails.py`.
2. Ensure it runs before agent actions.
3. Register it in the guardrail pipeline.


## 7. Testing Extensions

- Add tests in `tests/` following the naming convention `test_*.py`.
- Use `pytest` to run tests:
```bash
pytest
```


## 8. Best Practices

- Keep extensions modular.
- Write unit tests for all new features.
- Follow PEP8 coding standards.
- Document your changes in `CHANGELOG.md`.
