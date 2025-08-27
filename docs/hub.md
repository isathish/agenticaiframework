# AgenticAI Framework — Hub Module Documentation

## Overview
The `hub` module acts as the central registry for agents, tools, and processes in the AgenticAI Framework. It enables dynamic registration, retrieval, and management of these components, allowing for flexible and modular system design.

---

## Key Functions

### Agent Management
- `register_agent(name, cls)` — Register an agent class with a unique name.
- `get_agent(name)` — Retrieve an instance of a registered agent.

### Tool Management
- `register_tool(name, func)` — Register a tool function with a unique name.
- `get_tool(name)` — Retrieve a registered tool function.

### Process Management
- `register_process(name, func)` — Register a process function.
- `get_process(name)` — Retrieve a registered process function.

---

## Example Usage

### Registering and Retrieving an Agent
```python
from agenticaiframework.hub import register_agent, get_agent
from agenticaiframework.agents import Agent

class MyAgent(Agent):
    def act(self, input_data):
        return f"Processed: {input_data}"

register_agent("my_agent", MyAgent)
agent = get_agent("my_agent")
print(agent.act("Hello"))
```

### Registering and Using a Tool
```python
from agenticaiframework.hub import register_tool, get_tool

def word_count_tool(text):
    return {"word_count": len(text.split())}

register_tool("word_count", word_count_tool)
tool = get_tool("word_count")
print(tool("This is a test sentence."))
```

---

## Use Cases

- **Dynamic Agent Loading** — Load agents at runtime without hardcoding.
- **Tool Sharing** — Share tools between multiple agents.
- **Process Orchestration** — Centralize process definitions for reuse.

---

## Best Practices

- Use descriptive names for agents, tools, and processes to avoid conflicts.
- Register components during application initialization.
- Keep tools and processes stateless for easier reuse.

---

## Related Documentation
- [Agents Module](agents.md)
- [Processes Module](processes.md)
- [Memory Module](memory.md)
