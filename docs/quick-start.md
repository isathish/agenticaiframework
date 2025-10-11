# Quick Start Guide

This guide will help you get up and running with AgenticAI Framework in just a few minutes.

## Prerequisites

- Python 3.8 or higher
- pip package manager

## Installation

Install AgenticAI Framework using pip:

```bash
pip install agenticaiframework
```

## Basic Example: Your First Agent

Let's create a simple agent that can generate text responses:

```python
from agenticaiframework import Agent, Task, LLMManager

# Step 1: Set up the LLM Manager
llm_manager = LLMManager()

# Register a simple mock LLM for demonstration
def simple_llm(prompt, kwargs=None):
    return f"Response to: {prompt}"

llm_manager.register_model("simple-llm", simple_llm)
llm_manager.set_active_model("simple-llm")

# Step 2: Create an agent
agent = Agent(
    name="QuickStartAgent",
    role="Assistant",
    capabilities=["text_generation"],
    config={"llm": llm_manager}
)

# Step 3: Define and run a task
task = Task(
    name="GreetingTask",
    objective="Generate a friendly greeting",
    executor=lambda: llm_manager.generate("Say hello to the user!")
)

# Step 4: Start the agent and run the task
agent.start()
result = task.run()
print(f"Agent response: {result}")
```

## Multi-Agent Example

Here's how to create multiple agents that work together:

```python
from agenticaiframework import Agent, AgentManager, Task

# Create multiple agents
data_collector = Agent(
    name="DataCollector",
    role="Data Specialist",
    capabilities=["data_collection"],
    config={"source": "api"}
)

data_analyzer = Agent(
    name="DataAnalyzer", 
    role="Analysis Expert",
    capabilities=["analysis"],
    config={"method": "statistical"}
)

# Set up agent management
manager = AgentManager()
manager.register_agent(data_collector)
manager.register_agent(data_analyzer)

# Start all agents
data_collector.start()
data_analyzer.start()

# Coordinate agents
manager.broadcast("Starting collaborative workflow...")
```

## Memory Management

Store and retrieve information across agent interactions:

```python
from agenticaiframework.memory import MemoryManager

# Initialize memory manager
memory = MemoryManager()

# Store information
memory.store("user_name", "Alice")
memory.store("last_interaction", "greeting", memory_type="short_term")

# Retrieve information
user_name = memory.retrieve("user_name")
print(f"User name: {user_name}")

# List stored keys
keys = list(memory.short_term.keys())
print(f"Stored keys: {keys}")
```

## Adding Guardrails

Implement safety measures for your agents:

```python
from agenticaiframework.guardrails import Guardrail, GuardrailManager

# Create a guardrail manager
guardrail_manager = GuardrailManager()

# Define a safety check
def content_filter(text):
    unsafe_words = ["dangerous", "harmful"]
    return not any(word in text.lower() for word in unsafe_words)

# Create and register a guardrail
safety_guardrail = Guardrail(
    name="ContentSafety",
    validation_fn=content_filter
)

guardrail_manager.register_guardrail(safety_guardrail)

# Test the guardrail
is_safe = guardrail_manager.validate("ContentSafety", "This is safe content")
print(f"Content is safe: {is_safe}")
```

## Monitoring and Logging

Track your agents' performance:

```python
from agenticaiframework.monitoring import MonitoringSystem

# Initialize monitoring
monitor = MonitoringSystem()

# Record metrics
monitor.record_metric("response_time", 0.5)
monitor.record_metric("success_rate", 0.95)

# Log events
monitor.log_event("AgentStarted", {"agent": "QuickStartAgent"})
monitor.log_event("TaskCompleted", {"task": "GreetingTask", "status": "success"})

# Get monitoring data
metrics = monitor.get_metrics()
events = monitor.get_events()

print(f"Metrics: {metrics}")
print(f"Events: {len(events)} events logged")
```

## Configuration Management

Manage your application settings:

```python
from agenticaiframework.configurations import ConfigurationManager

# Initialize configuration manager
config = ConfigurationManager()

# Set configuration
config.set_config("AppSettings", {
    "max_agents": 10,
    "timeout": 30,
    "log_level": "INFO"
})

# Get configuration
settings = config.get_config("AppSettings")
print(f"App settings: {settings}")

# Update configuration
config.update_config("AppSettings", {"max_agents": 15})
updated_settings = config.get_config("AppSettings")
print(f"Updated settings: {updated_settings}")
```

## Next Steps

Now that you've got the basics down, explore these advanced topics:

- [Core Modules](agents.md) - Deep dive into each component
- [Examples](EXAMPLES.md) - Real-world usage examples
- [Best Practices](best-practices.md) - Production deployment guidelines
- [API Reference](API_REFERENCE.md) - Complete API documentation

## Common Issues

### Import Errors
If you encounter import errors, ensure you have the latest version:

```bash
pip install --upgrade agenticaiframework
```

### Memory Issues
For large-scale applications, consider using external memory backends:

```python
# Example with Redis (requires redis-py)
memory = MemoryManager()
memory.store("key", "value", memory_type="external")
```

### Performance
For better performance in production:

- Use asynchronous execution where possible
- Implement proper caching strategies
- Monitor resource usage with the monitoring system

## Getting Help

- Check the [Troubleshooting](TROUBLESHOOTING.md) guide
- Browse [Examples](EXAMPLES.md) for common patterns
- Visit our [GitHub repository](https://github.com/isathish/agenticaiframework) for issues and discussions