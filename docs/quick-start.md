---
title: Quick Start Guide
description: Get started with AgenticAI Framework in minutes
---

# :rocket: Quick Start Guide

Get up and running with AgenticAI Framework in under 5 minutes.

!!! success "Framework Overview"
    AgenticAI Framework includes **400+ modules** with **237 enterprise-grade
    features** covering agents, security, ML/AI infrastructure, and more.

---

## :package: Installation

### Basic Installation

```bash
pip install agenticaiframework
```

### Full Installation (All Features)

```bash
pip install agenticaiframework[all]
```

### Feature-Specific Installation

=== "Core Only"
    ```bash
    pip install agenticaiframework
    ```

=== "With LLM Providers"
    ```bash
    pip install agenticaiframework[llm]
    # Includes: openai, anthropic, google-generativeai
    ```

=== "With Monitoring"
    ```bash
    pip install agenticaiframework[monitoring]
    # Includes: opentelemetry, prometheus-client
    ```

=== "Development"
    ```bash
    pip install agenticaiframework[dev]
    # Includes: pytest, black, mypy, ruff
    ```

---

## :gear: Configuration

Create a `.env` file in your project root:

```bash
# LLM Provider API Keys
OPENAI_API_KEY=your_openai_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here
GOOGLE_API_KEY=your_google_key_here

# Optional: Framework Settings
AGENTIC_LOG_LEVEL=INFO
AGENTIC_ENABLE_TRACING=true
AGENTIC_CACHE_ENABLED=true
```

Or use a YAML configuration file:

```yaml title="agentic_config.yaml"
framework:
  log_level: INFO
  enable_tracing: true
  cache_enabled: true

llm:
  default_provider: openai
  default_model: gpt-4o-mini
  temperature: 0.7
  max_tokens: 4096
```

---

## :robot: Your First Agent

### Quick Factory (Recommended)

The fastest way to create an agent — one line, sensible defaults:

```python
from agenticaiframework import Agent

# Minimal setup — auto-configures LLM from environment variables
agent = Agent.quick("Assistant")
output = agent.invoke("What is the capital of France?")
```

### With Role Templates

Built-in role templates: `assistant`, `analyst`, `coder`, `writer`, `researcher`.

```python
from agenticaiframework import Agent

# Create a research agent
researcher = Agent.quick(
    "ResearchBot",
    role="researcher",
    provider="openai",
)
output = researcher.invoke("Summarise the latest trends in AI safety")

# Create a coding agent
coder = Agent.quick(
    "CodeHelper",
    role="coder",
    provider="anthropic",
)
output = coder.invoke("Write a Python function to merge two sorted lists")
```

### Full Constructor

For complete control, use the `Agent` constructor directly:

```python
from agenticaiframework import Agent

agent = Agent(
    name="research_assistant",
    role="Expert researcher with deep analytical skills",
    capabilities=["search", "summarization", "reasoning"],
    config={"llm": "gpt-4o", "temperature": 0.7},
    max_context_tokens=8192,
)

result = agent.execute("Analyse the current state of quantum computing")
```

---

## :arrows_counterclockwise: Multi-Agent Teams

### Using AgentTeam

```python
from agenticaiframework import Agent
from agenticaiframework.orchestration import AgentTeam

researcher = Agent.quick("Researcher", role="researcher")
writer = Agent.quick("Writer", role="writer")

team = AgentTeam(name="content_team")
team.add_member(researcher)
team.add_member(writer)
```

### Using AgentSupervisor

```python
from agenticaiframework.orchestration import AgentSupervisor

supervisor = AgentSupervisor(
    name="project_lead",
    agents=[researcher, writer],
)
```

---

## :zap: Running Processes

### Sequential Pipeline

```python
from agenticaiframework import Process

proc = Process(name="etl_pipeline", strategy="sequential")
proc.add_task(fetch_data, "source_url")
proc.add_task(transform_data, raw_data)
proc.add_task(load_data, cleaned_data)

results = proc.execute()
```

### Parallel Execution

```python
from agenticaiframework import Process

proc = Process(name="multi_fetch", strategy="parallel", max_workers=4)
for source in ["arxiv", "scholar", "semantic"]:
    proc.add_task(fetch_papers, source)

results = proc.execute()  # All sources fetched concurrently
```

---

## :floppy_disk: Memory Management

```python
from agenticaiframework.memory import MemoryManager

memory = MemoryManager()

# Store a memory
memory.store(
    content="User prefers concise responses",
    metadata={"type": "preference", "user_id": "alice"},
)

# Search memories
results = memory.search("user preferences", top_k=5)
```

---

## :book: Knowledge Retrieval

```python
from agenticaiframework import KnowledgeRetriever

retriever = KnowledgeRetriever()
retriever.register_source("docs", my_search_function)

# Query with automatic LRU caching
result = retriever.retrieve("docs", "How to configure agents?")
```

---

## :bar_chart: Monitoring

```python
from agenticaiframework import MonitoringSystem

monitor = MonitoringSystem()

# Record metrics
monitor.record_metric("latency_ms", 42.5)
monitor.log_event("task_completed", {"task": "summarise"})

# Retrieve data
metrics = monitor.get_metrics()
events = monitor.get_events()
gc_stats = monitor.get_gc_stats()
```

---

## :shield: Security

### Input Validation

```python
from agenticaiframework.security import InputValidator

validator = InputValidator()
is_safe, sanitized = validator.validate(user_input)

if is_safe:
    result = agent.execute(sanitized)
```

### PII Masking

```python
from agenticaiframework.compliance import PIIMasker

masker = PIIMasker()
masked_text = masker.mask("Contact John at john@email.com or 555-1234")
# Output: Contact [NAME] at [EMAIL] or [PHONE]
```

---

## :mag: Tracing

```python
from agenticaiframework.tracing import TracingManager

tracer = TracingManager(
    service_name="my-agent-service",
)

with tracer.span("agent_execution"):
    result = agent.execute("Process this task")
```

---

## :tools: MCP Tools

```python
from agenticaiframework.mcp_tools import MCPTool, MCPToolManager

tool = MCPTool(
    id="calculator",
    name="Calculator",
    capability="Perform arithmetic",
    execute_fn=lambda a, b: a + b,
)

manager = MCPToolManager()
manager.register_tool(tool)
result = manager.execute_tool("calculator", a=5, b=3)  # 8
```

---

## :hub: Hub Registry

```python
from agenticaiframework import Hub

hub = Hub()
hub.register("agents", "researcher", researcher)
hub.register("tools", "search", search_tool)

agent = hub.get("agents", "researcher")
```

---

## :file_folder: Project Structure

Recommended project structure:

```
my_agent_project/
\u251c\u2500\u2500 agents/
\u2502   \u251c\u2500\u2500 __init__.py
\u2502   \u251c\u2500\u2500 researcher.py
\u2502   \u2514\u2500\u2500 writer.py
\u251c\u2500\u2500 tools/
\u2502   \u251c\u2500\u2500 __init__.py
\u2502   \u2514\u2500\u2500 custom_tools.py
\u251c\u2500\u2500 config/
\u2502   \u2514\u2500\u2500 agents.yaml
\u251c\u2500\u2500 tests/
\u2502   \u2514\u2500\u2500 test_agents.py
\u251c\u2500\u2500 main.py
\u251c\u2500\u2500 requirements.txt
\u2514\u2500\u2500 .env
```

---

## :dart: Next Steps

<div class="grid cards" markdown>

-   :robot:{ .lg } **Deep Dive into Agents**

    ---

    Advanced agent configuration, custom behaviours, and lifecycle management.

    [:octicons-arrow-right-24: Agents Guide](agents.md)

-   :brain:{ .lg } **Memory Management**

    ---

    Explore memory managers and advanced memory patterns.

    [:octicons-arrow-right-24: Memory Guide](memory.md)

-   :arrows_counterclockwise:{ .lg } **Orchestration**

    ---

    Build complex multi-agent workflows and teams.

    [:octicons-arrow-right-24: Orchestration Guide](orchestration.md)

-   :hammer_and_wrench:{ .lg } **Tools**

    ---

    Create custom tools and use MCP tools.

    [:octicons-arrow-right-24: Tools Guide](tools.md)

</div>

---

## :question: Common Issues

??? question "Agent not responding as expected?"
    - Check your API key is correctly set
    - Verify the model name is correct
    - Review the agent's role and goal for clarity
    - Enable debug logging: `AGENTIC_LOG_LEVEL=DEBUG`

??? question "Memory not persisting?"
    - Default memory is in-memory (cleared on restart)
    - Configure persistent backend: `memory = MemoryManager(backend="redis")`
    - Check backend connection settings

??? question "Performance issues?"
    - Enable caching: `AGENTIC_CACHE_ENABLED=true`
    - Use `parallel` strategy in Process for concurrent tasks
    - Set `max_workers` explicitly for CPU-bound work
    - Consider batching similar requests

---

## :speech_balloon: Getting Help

- **GitHub Issues**: [Report bugs or request features](https://github.com/isathish/agenticaiframework/issues)
- **Discussions**: [Ask questions and share ideas](https://github.com/isathish/agenticaiframework/discussions)
- **Documentation**: [Full documentation](index.md)
