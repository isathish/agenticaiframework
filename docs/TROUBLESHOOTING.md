---
tags:
  - troubleshooting
  - help
  - debugging
  - issues
---

# 🔧 Troubleshooting Guide

This guide lists common issues you may encounter when using **AgenticAI Framework** (380+ modules, 237 enterprise features) and how to resolve them.

---

## 1. Installation Issues

### Problem: `ModuleNotFoundError: No module named 'agenticaiframework'`

**Solution:**
```bash
# Install the package
pip install agenticaiframework

# Or from source
git clone https://github.com/isathish/agenticaiframework.git
cd agenticaiframework
pip install -e .
```

!!! tip "Virtual Environment"
    Always use a virtual environment:
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # macOS/Linux
    .venv\Scripts\activate     # Windows
    pip install agenticaiframework
    ```

---

## 2. API Key Errors

### Problem: `Invalid API key` or `Authentication failed`

**Solution:**
```bash
# Set environment variables for your LLM provider
export OPENAI_API_KEY="your-key-here"
export ANTHROPIC_API_KEY="your-key-here"
export AZURE_OPENAI_API_KEY="your-key-here"
```

Or in Python:
```python
import os
os.environ["OPENAI_API_KEY"] = "your-key-here"
```

---

## 3. Agent Not Found

### Problem: `ValueError: Agent 'xyz' not found`

**Solution:**
```python
from agenticaiframework import Agent, AgentManager

# Create and register the agent
agent = Agent(name="xyz", role="assistant", capabilities=["text"])
manager = AgentManager()
manager.register_agent(agent)

# Verify registration
print([a.name for a in manager.agents])
```

---

## 4. Tool Not Found

### Problem: `ValueError: Tool 'abc' not found`

**Solution:**
```python
from agenticaiframework.tools import tool_registry

# Check available tools
print(tool_registry.list_tools())

# Register a new tool
from agenticaiframework.tools import register_tool, BaseTool

@register_tool()
class MyTool(BaseTool):
    name = "abc"
    description = "My custom tool"
    
    def _run(self, input_data):
        return {"result": "success"}
```

---

## 5. LLM Provider Errors

### Problem: `Provider not supported`

**Solution:**
```python
from agenticaiframework.llms import LLMManager

llm = LLMManager()

# Check available models
print(llm.list_models())

# Register a custom model
def my_llm_function(prompt, **kwargs):
    return f"Response: {prompt}"

llm.register_model("my-model", my_llm_function)
llm.set_active_model("my-model")
```

---

## 6. Memory Issues

### Problem: Data not persisting

**Solution:**
```python
from agenticaiframework.memory import MemoryManager

memory = MemoryManager()

# Store in long-term memory for persistence
memory.store("key", "value", memory_type="long_term")

# Or consolidate short-term to long-term
memory.consolidate()
```

---

## 7. Process Execution Errors

### Problem: `Process 'xyz' not found`

**Solution:**
```python
from agenticaiframework.processes import ProcessManager

pm = ProcessManager()

# List available processes
print(pm.list_processes())

# Register your process
pm.register_process("xyz", my_process_function)
```

---

## 8. Performance Issues

### Problem: Slow agent responses

**Solution:**

1. **Optimize prompts** - Reduce token usage
2. **Enable caching** - Cache repeated LLM calls
3. **Use async** - Process multiple tasks concurrently

```python
from agenticaiframework.llms import LLMManager

llm = LLMManager(enable_caching=True)

# Cached responses are returned instantly
response1 = llm.generate("What is AI?")  # First call - slower
response2 = llm.generate("What is AI?")  # Cached - instant
```

---

## 9. Memory Leaks

### Problem: Increasing memory usage over time

**Solution:**
```python
from agenticaiframework.memory import MemoryManager

memory = MemoryManager()

# Clear old short-term memory periodically
memory.clear_short_term()

# Or set TTL when storing
memory.store("temp_key", "value", ttl=3600)  # Expires in 1 hour
```

---

## 10. Deployment Problems

### Problem: Application works locally but fails in production

**Checklist:**

- [ ] All environment variables are set correctly
- [ ] All dependencies are installed (`pip freeze > requirements.txt`)
- [ ] Network access for external APIs is available
- [ ] File paths use relative paths or environment variables
- [ ] Memory and CPU resources are sufficient

---

## 11. Debugging Tips

### Enable Debug Logging

```python
from agenticaiframework.configurations import ConfigurationManager

config = ConfigurationManager()
config.set_config("Logging", {"log_level": "DEBUG"})
```

### Use Monitoring System

```python
from agenticaiframework.monitoring import MonitoringSystem

monitor = MonitoringSystem()
monitor.log_event("DebugInfo", {"step": "processing", "data": data})
```

### Run Tests

```bash
pytest tests/ -v --cov=agenticaiframework
```

---

## 12. Getting Help

### Community Resources

- **Documentation**: [isathish.github.io/agenticaiframework](https://isathish.github.io/agenticaiframework/)
- **GitHub Issues**: [Report bugs](https://github.com/isathish/agenticaiframework/issues)
- **Discussions**: [Ask questions](https://github.com/isathish/agenticaiframework/discussions)

### Related Documentation

- [Quick Start Guide](quick-start.md)
- [FAQ](faq.md)
- [API Reference](API_REFERENCE.md)
- [Examples](EXAMPLES.md)
