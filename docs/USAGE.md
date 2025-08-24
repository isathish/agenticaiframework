# Using AgenticAI

This guide explains how to install, configure, and use the **AgenticAI** package with practical examples.

---

## 1. Installation

Install AgenticAI from PyPI:

```bash
pip install agenticai
```

Or install from source:

```bash
git clone https://github.com/isathish/AgenticAI.git
cd AgenticAI
pip install .
```

---

## 2. Basic Usage

### Creating and Running an Agent

```python
from agenticai.agents import Agent
from agenticai.hub import register_agent, get_agent

class EchoAgent(Agent):
    def act(self, input_data):
        return f"Echo: {input_data}"

register_agent("echo", EchoAgent)

agent = get_agent("echo")
print(agent.act("Hello World"))
```

---

## 3. Using Built-in Agents

AgenticAI comes with prebuilt agents. You can load them via the hub:

```python
from agenticai.hub import get_agent

agent = get_agent("default_agent")
response = agent.act("Summarize this text.")
print(response)
```

---

## 4. Configuring the System

Edit `configurations.py` or pass configuration at runtime:

```python
from agenticai.configurations import set_config

set_config("llm_provider", "openai")
set_config("api_key", "your_api_key_here")
```

---

## 5. Using Tools

```python
from agenticai.hub import get_tool

sentiment_tool = get_tool("sentiment_analysis")
result = sentiment_tool("I love this product!")
print(result)
```

---

## 6. Running Processes

```python
from agenticai.processes import run_process

result = run_process("data_analysis", {"dataset": "data.csv"})
print(result)
```

---

## 7. Memory Usage

```python
from agenticai.memory import Memory

mem = Memory()
mem.store("user_name", "Alice")
print(mem.retrieve("user_name"))
```

---

## 8. Example Workflow

```python
from agenticai.hub import get_agent, get_tool

agent = get_agent("default_agent")
tool = get_tool("sentiment_analysis")

text = "The movie was fantastic!"
analysis = tool(text)
response = agent.act(f"Summarize the sentiment: {analysis}")
print(response)
```

---

## 9. Testing

Run tests with:

```bash
pytest
```

---

## 10. Additional Resources

- [Extending AgenticAI](EXTENDING.md)
- [Examples](EXAMPLES.md)
