# Agentic AI Framework - Examples

This document contains runnable examples for various features of the `agenticaiframework` package.  
Each example is aligned with the actual API and uses the `agenticaiframework` namespace for imports.

---

## 1. Agents Example

```python
from agenticaiframework.agents import AgentManager, Agent

if __name__ == "__main__":
    agent_manager = AgentManager()

    example_agent = Agent(name="ExampleAgent")
    agent_manager.register_agent(example_agent)

    example_agent.start()
    example_agent.pause()
    example_agent.resume()
    example_agent.stop()

    print("Registered Agents:", [agent.name for agent in agent_manager.agents])
    retrieved_agent = agent_manager.get_agent("ExampleAgent")
    print("Retrieved Agent:", retrieved_agent.name)
```

---

## 2. Tasks Example

```python
from agenticaiframework.tasks import TaskManager, Task

if __name__ == "__main__":
    task_manager = TaskManager()

    class AdditionTask(Task):
        def run(self, a, b):
            result = a + b
            print(f"Task Result: {result}")
            return result

    addition_task = AdditionTask(name="AdditionTask")
    task_manager.register_task(addition_task)

    addition_task.run(5, 7)
    print("Registered Tasks:", [task.name for task in task_manager.tasks])
    retrieved_task = task_manager.get_task("AdditionTask")
    print("Retrieved Task:", retrieved_task.name)
```

---

## 3. LLMs Example

```python
from agenticaiframework.llms import LLMManager

if __name__ == "__main__":
    llm_manager = LLMManager()

    llm_manager.register_model("demo-llm", lambda prompt: f"[Demo LLM Response to: {prompt}]")
    llm_manager.set_active_model("demo-llm")

    print("Generated Text:", llm_manager.generate("Explain the concept of machine learning in simple terms."))
    print("Available Models:", list(llm_manager.models.keys()))
```

---

## 4. Guardrails Example

```python
from agenticaiframework.guardrails import GuardrailManager

if __name__ == "__main__":
    guardrail_manager = GuardrailManager()

    guardrail_manager.add_guardrail("No profanity", lambda text: "badword" not in text)
    print("Compliant Output Valid:", guardrail_manager.validate("This is clean text."))
    print("Non-Compliant Output Valid:", guardrail_manager.validate("This contains badword."))
```

---

## 5. Memory Example

```python
from agenticaiframework.memory import MemoryManager

if __name__ == "__main__":
    memory = MemoryManager()

    memory.store_short_term("user_name", "Alice")
    memory.store_short_term("last_query", "What is the capital of France?")

    print("Retrieved User Name:", memory.retrieve("user_name"))
    print("Retrieved Last Query:", memory.retrieve("last_query"))

    keys = list(memory.short_term.keys()) + list(memory.long_term.keys()) + list(memory.external.keys())
    print("Stored Keys:", keys)

    memory.clear_short_term()
    memory.clear_long_term()
    memory.clear_external()
    print("Memory cleared. Keys now:", list(memory.short_term.keys()) + list(memory.long_term.keys()) + list(memory.external.keys()))
```

---

## 6. MCP Tools Example

```python
from agenticaiframework.mcp_tools import MCPToolManager, MCPTool

def greet_tool(name: str) -> str:
    return f"Hello, {name}! Welcome to MCP Tools."

if __name__ == "__main__":
    mcp_manager = MCPToolManager()

    greet_mcp_tool = MCPTool(name="greet", capability="greeting", execute_fn=greet_tool)
    mcp_manager.register_tool(greet_mcp_tool)

    print("Available Tools:", [tool.name for tool in mcp_manager.tools])
    result = mcp_manager.execute_tool("greet", "Alice")
    print("Tool Execution Result:", result)
```

---

## 7. Monitoring Example

```python
from agenticaiframework.monitoring import MonitoringSystem

if __name__ == "__main__":
    monitor = MonitoringSystem()

    monitor.log_event("AgentStarted", {"agent_name": "ExampleAgent"})
    monitor.log_event("TaskCompleted", {"task_name": "AdditionTask", "status": "success"})

    monitor.record_metric("ResponseTime", 1.23)
    monitor.record_metric("Accuracy", 0.98)

    print("Logged Events:", monitor.events)
    print("Logged Metrics:", monitor.metrics)
```

---

## 8. Prompts Example

```python
from agenticaiframework.prompts import Prompt

if __name__ == "__main__":
    prompt_instance = Prompt(
        template="Write a {length} paragraph summary about {topic}."
    )

    rendered_prompt = prompt_instance.render(length="short", topic="artificial intelligence")
    print("Rendered Prompt:", rendered_prompt)
```

---

## 9. Configurations Example

```python
from agenticaiframework.configurations import ConfigManager

if __name__ == "__main__":
    config = ConfigManager()
    config.set("api_key", "123456")
    print("API Key:", config.get("api_key"))
```

---

**Usage:**  
Run any example with:
```bash
python examples/<example_name>.py
