# AgenticAI Examples

This document provides practical examples of using **AgenticAI** for various tasks.

---

## 1. Simple Agent Example

```python
from agenticai.agents import Agent
from agenticai.hub import register_agent, get_agent

class ReverseAgent(Agent):
    def act(self, input_data):
        return input_data[::-1]

register_agent("reverse", ReverseAgent)

agent = get_agent("reverse")
print(agent.act("Hello"))  # Output: olleH
```

---

## 2. Using a Tool

```python
from agenticai.hub import register_tool, get_tool

def word_count_tool(text):
    return {"word_count": len(text.split())}

register_tool("word_count", word_count_tool)

tool = get_tool("word_count")
print(tool("This is a test sentence."))
```

---

## 3. Combining Agents and Tools

```python
from agenticai.hub import register_agent, get_agent, register_tool, get_tool
from agenticai.agents import Agent

class UpperCaseAgent(Agent):
    def act(self, input_data):
        return input_data.upper()

register_agent("upper", UpperCaseAgent)

def exclaim_tool(text):
    return text + "!!!"

register_tool("exclaim", exclaim_tool)

agent = get_agent("upper")
tool = get_tool("exclaim")

text = "hello world"
result = tool(agent.act(text))
print(result)  # Output: HELLO WORLD!!!
```

---

## 4. Using Memory

```python
from agenticai.memory import Memory

memory = Memory()
memory.store("session_id", "12345")
print(memory.retrieve("session_id"))
```

---

## 5. Running a Process

```python
from agenticai.processes import run_process

result = run_process("data_cleaning", {"file": "data.csv"})
print(result)
```

---

## 6. LLM Integration Example

```python
from agenticai.llms import OpenAIModel

llm = OpenAIModel(api_key="your_api_key_here")
response = llm.generate("Write a haiku about AI.")
print(response)
```

---

## 7. Guardrails Example

```python
from agenticai.guardrails import add_guardrail

def block_sensitive_data(input_data):
    if "password" in input_data.lower():
        raise ValueError("Sensitive data detected!")
    return input_data

add_guardrail(block_sensitive_data)
```

---

## 8. Full Workflow Example

```python
from agenticai.hub import get_agent, get_tool

agent = get_agent("default_agent")
tool = get_tool("sentiment_analysis")

text = "I absolutely love this product!"
analysis = tool(text)
response = agent.act(f"Summarize the sentiment: {analysis}")
print(response)
```

---

## 9. Testing Your Code

```bash
pytest
```

---

## 10. Next Steps

- Explore [USAGE.md](USAGE.md) for more details.
- Learn how to extend the package in [EXTENDING.md](EXTENDING.md).
