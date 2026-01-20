---
title: Quick Start Guide
description: Get started with AgenticAI Framework in minutes
---

# 🚀 Quick Start Guide

Get up and running with AgenticAI Framework in under 5 minutes. This guide covers installation, basic agent creation, and key concepts.

---

## 📦 Installation

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

=== "With Vector Stores"
    ```bash
    pip install agenticaiframework[vectors]
    # Includes: chromadb, pinecone, qdrant
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

## ⚙️ Configuration

### Environment Variables

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

### Configuration File

Alternatively, use a YAML configuration file:

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

memory:
  default_backend: in-memory
  max_entries: 1000
  enable_compression: true

security:
  enable_input_validation: true
  enable_output_sanitization: true
  mask_pii: true
```

---

## 🤖 Your First Agent

### Basic Agent

```python
from agenticaiframework import Agent, AgentConfig

# Create a simple agent
config = AgentConfig(
    name="my_assistant",
    role="Helpful AI Assistant",
    goal="Help users with their questions accurately and helpfully"
)

agent = Agent(config=config)

# Execute a task
result = agent.execute("What is the capital of France?")
print(result.output)
# Output: The capital of France is Paris.
```

### Agent with Memory

```python
from agenticaiframework import Agent, AgentConfig, MemoryManager

# Initialize memory manager
memory = MemoryManager()

# Create agent with memory
config = AgentConfig(
    name="remembering_assistant",
    role="Personal Assistant",
    goal="Help users while remembering previous interactions"
)

agent = Agent(config=config, memory=memory)

# First interaction
result1 = agent.execute("My name is Alice")
print(result1.output)
# Output: Nice to meet you, Alice! How can I help you today?

# Second interaction - agent remembers!
result2 = agent.execute("What's my name?")
print(result2.output)
# Output: Your name is Alice.
```

### Agent with Tools

```python
from agenticaiframework import Agent, AgentConfig
from agenticaiframework.tools import SearchTool, CalculatorTool, PythonREPLTool

# Create agent with tools
config = AgentConfig(
    name="research_assistant",
    role="Research Analyst",
    goal="Research topics and provide accurate analysis",
    tools=[
        SearchTool(),
        CalculatorTool(),
        PythonREPLTool()
    ]
)

agent = Agent(config=config)

# Agent can use tools to answer
result = agent.execute("Search for the current population of Japan and calculate the percentage of global population")
print(result.output)
```

---

## 👥 Multi-Agent Teams

### Sequential Workflow

```python
from agenticaiframework import Agent, AgentConfig, Team, WorkflowManager

# Create specialized agents
researcher = Agent(
    config=AgentConfig(
        name="researcher",
        role="Research Analyst",
        goal="Gather comprehensive information on topics"
    )
)

writer = Agent(
    config=AgentConfig(
        name="writer",
        role="Content Writer",
        goal="Transform research into engaging content"
    )
)

editor = Agent(
    config=AgentConfig(
        name="editor",
        role="Quality Editor",
        goal="Ensure content is polished and error-free"
    )
)

# Create team with sequential workflow
team = Team(
    name="content_team",
    agents=[researcher, writer, editor],
    workflow=WorkflowManager.sequential()
)

# Execute team task
result = team.execute("Create an article about the future of renewable energy")
print(result.final_output)
```

### Parallel Workflow

```python
from agenticaiframework import Team, WorkflowManager

# Agents working in parallel
team = Team(
    name="parallel_research",
    agents=[market_analyst, tech_analyst, competitor_analyst],
    workflow=WorkflowManager.parallel()
)

# All agents work simultaneously
result = team.execute("Analyze the AI industry landscape")
```

### Hierarchical Team

```python
from agenticaiframework import Team, WorkflowManager

# Create a leader agent
leader = Agent(
    config=AgentConfig(
        name="team_leader",
        role="Project Manager",
        goal="Coordinate team members and synthesize results"
    )
)

# Create team with hierarchical structure
team = Team(
    name="managed_team",
    leader=leader,
    agents=[researcher, writer, editor],
    workflow=WorkflowManager.hierarchical()
)

# Leader coordinates the work
result = team.execute("Create a comprehensive market report")
```

---

## 💾 Memory Management

### Using Different Memory Managers

=== "MemoryManager"
    ```python
    from agenticaiframework import MemoryManager
    
    # General-purpose memory
    memory = MemoryManager()
    
    # Store a memory
    memory.store(
        content="User prefers concise responses",
        metadata={"type": "preference", "user_id": "alice"}
    )
    
    # Search memories
    results = memory.search("user preferences", top_k=5)
    ```

=== "AgentMemoryManager"
    ```python
    from agenticaiframework import AgentMemoryManager
    
    # Agent-specific memory
    agent_memory = AgentMemoryManager(agent_id="researcher_01")
    
    # Store agent context
    agent_memory.store_context(
        task="market research",
        findings=["trend1", "trend2"],
        confidence=0.85
    )
    ```

=== "WorkflowMemoryManager"
    ```python
    from agenticaiframework import WorkflowMemoryManager
    
    # Workflow state tracking
    workflow_memory = WorkflowMemoryManager(workflow_id="content_pipeline")
    
    # Track step completion
    workflow_memory.record_step(
        step_name="research",
        status="completed",
        output=research_data
    )
    ```

=== "KnowledgeMemoryManager"
    ```python
    from agenticaiframework import KnowledgeMemoryManager
    
    # Knowledge base storage
    knowledge = KnowledgeMemoryManager()
    
    # Add knowledge documents
    knowledge.add_document(
        content=document_text,
        source="company_policy.pdf",
        category="policies"
    )
    
    # Query knowledge base
    answer = knowledge.query("What is the vacation policy?")
    ```

---

## 🔌 Communication Protocols

### HTTP Client

```python
from agenticaiframework.communication import HTTPClient

async with HTTPClient() as client:
    # Send request
    response = await client.post(
        "https://api.example.com/data",
        json={"query": "test"}
    )
    print(response.json())
```

### WebSocket Connection

```python
from agenticaiframework.communication import WebSocketClient

async with WebSocketClient("wss://api.example.com/ws") as ws:
    # Send message
    await ws.send({"type": "subscribe", "channel": "updates"})
    
    # Receive messages
    async for message in ws:
        print(f"Received: {message}")
```

### Server-Sent Events (SSE)

```python
from agenticaiframework.communication import SSEClient

async with SSEClient("https://api.example.com/events") as sse:
    async for event in sse:
        print(f"Event: {event.data}")
```

---

## 📊 Evaluation

### Basic Evaluation

```python
from agenticaiframework import EvaluationManager, ModelQualityEvaluator

# Create evaluation manager
evaluator = EvaluationManager()

# Add evaluators
evaluator.add(ModelQualityEvaluator())

# Run evaluation
results = evaluator.evaluate(
    agent=my_agent,
    test_cases=[
        {"input": "What is 2+2?", "expected": "4"},
        {"input": "Capital of Japan?", "expected": "Tokyo"}
    ]
)

print(f"Accuracy: {results.accuracy}")
print(f"Latency: {results.avg_latency}ms")
```

### Comprehensive Evaluation

```python
from agenticaiframework.evaluation import (
    ModelQualityEvaluator,
    SecurityEvaluator,
    CostEvaluator,
    ToolEffectivenessEvaluator
)

evaluator = EvaluationManager()
evaluator.add(ModelQualityEvaluator())
evaluator.add(SecurityEvaluator())
evaluator.add(CostEvaluator())
evaluator.add(ToolEffectivenessEvaluator())

# Run full evaluation suite
results = evaluator.run_full_evaluation(agent)
results.generate_report("evaluation_report.html")
```

---

## 🛡️ Security

### Input Validation

```python
from agenticaiframework.security import InputValidator

validator = InputValidator()

# Validate user input
is_safe, sanitized = validator.validate(user_input)

if is_safe:
    result = agent.execute(sanitized)
else:
    print("Input blocked due to security concerns")
```

### Secrets Management

```python
from agenticaiframework.security import SecretsManager

# Initialize secrets manager
secrets = SecretsManager()

# Store secrets securely
secrets.set("api_key", "your-secret-key", encrypted=True)

# Retrieve secrets
api_key = secrets.get("api_key")
```

### PII Masking

```python
from agenticaiframework.compliance import PIIMasker

masker = PIIMasker()

# Mask PII in text
masked_text = masker.mask("Contact John at john@email.com or 555-1234")
# Output: Contact [NAME] at [EMAIL] or [PHONE]
```

---

## 🔍 Tracing & Monitoring

### Enable Tracing

```python
from agenticaiframework.tracing import TracingManager

# Initialize tracing
tracer = TracingManager(
    service_name="my-agent-service",
    exporter="jaeger",
    endpoint="http://localhost:14268/api/traces"
)

# Traces are automatically captured during agent execution
with tracer.span("agent_execution"):
    result = agent.execute("Process this task")
```

### Custom Metrics

```python
from agenticaiframework.monitoring import MetricsCollector

metrics = MetricsCollector()

# Record custom metrics
metrics.record("task_completion_time", duration_ms)
metrics.increment("tasks_completed")
metrics.gauge("active_agents", active_count)
```

---

## 📁 Project Structure

Recommended project structure for AgenticAI applications:

```
my_agent_project/
├── agents/
│   ├── __init__.py
│   ├── researcher.py
│   ├── writer.py
│   └── editor.py
├── tools/
│   ├── __init__.py
│   └── custom_tools.py
├── workflows/
│   ├── __init__.py
│   └── content_pipeline.py
├── config/
│   ├── agents.yaml
│   └── tools.yaml
├── tests/
│   ├── test_agents.py
│   └── test_workflows.py
├── main.py
├── requirements.txt
└── .env
```

---

## 🎯 Next Steps

<div class="grid cards" markdown>

-   :robot:{ .lg } **Deep Dive into Agents**

    ---

    Learn about advanced agent configuration, custom behaviors, and lifecycle management.

    [:octicons-arrow-right-24: Agents Guide](agents.md)

-   :brain:{ .lg } **Master Memory Management**

    ---

    Explore all 7 memory managers and advanced memory patterns.

    [:octicons-arrow-right-24: Memory Guide](memory.md)

-   :arrows_counterclockwise:{ .lg } **Multi-Agent Orchestration**

    ---

    Build complex multi-agent workflows and teams.

    [:octicons-arrow-right-24: Orchestration Guide](orchestration.md)

-   :hammer_and_wrench:{ .lg } **Custom Tools**

    ---

    Create powerful custom tools for your agents.

    [:octicons-arrow-right-24: Tools Guide](tools.md)

</div>

---

## ❓ Common Issues

??? question "Agent not responding as expected?"
    - Check your API key is correctly set
    - Verify the model name is correct
    - Review the agent's role and goal for clarity
    - Enable debug logging: `AGENTIC_LOG_LEVEL=DEBUG`

??? question "Memory not persisting?"
    - Default memory is in-memory (cleared on restart)
    - Configure persistent backend: `memory = MemoryManager(backend="redis")`
    - Check backend connection settings

??? question "Tools not being used?"
    - Ensure tools are properly added to agent config
    - Verify tool descriptions are clear
    - Check tool permissions and API keys

??? question "Performance issues?"
    - Enable caching: `AGENTIC_CACHE_ENABLED=true`
    - Use async execution for concurrent tasks
    - Consider batching similar requests

---

## 💬 Getting Help

- **GitHub Issues**: [Report bugs or request features](https://github.com/sathishbabu89/agenticaiframework/issues)
- **Discussions**: [Ask questions and share ideas](https://github.com/sathishbabu89/agenticaiframework/discussions)
- **Documentation**: [Full documentation](index.md)
