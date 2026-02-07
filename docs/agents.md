---
title: Agents
description: Create intelligent AI agents with customizable roles, goals, tools, and behaviors
---

# Agents

Agents are the core building blocks of AgenticAI Framework. They are autonomous AI entities that can reason, plan, use tools, and execute complex tasks.

!!! success "Enterprise-Ready"

    Part of a **400+ module framework** with 237 enterprise modules, 7 memory managers, 7 state managers, and 35+ built-in tools.

---

## Quick Navigation

<div class="grid cards" markdown>

- :rocket:{ .lg } **Getting Started**

    ---

    Create your first agent in minutes

    [:octicons-arrow-right-24: Quick Start](#creating-agents)

- :gear:{ .lg } **Configuration**

    ---

    Customize agent behavior and capabilities

    [:octicons-arrow-right-24: Learn Config](#agent-configuration)

- :hammer_and_wrench:{ .lg } **Tools**

    ---

    Equip agents with powerful tools

    [:octicons-arrow-right-24: Add Tools](#agent-tools)

- :brain:{ .lg } **Behaviors**

    ---

    Control agent reasoning and actions

    [:octicons-arrow-right-24: Set Behaviors](#agent-behaviors)

</div>

---

## Agent Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Agent │
├─────────────────────────────────────────────────────────────┤
│ │
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ │
│ │ Config │ │ Memory │ │ State │ │
│ │ (Role/Goal) │ │ (Context) │ │ (Lifecycle) │ │
│ └──────────────┘ └──────────────┘ └──────────────┘ │
│ │
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ │
│ │ Tools │ │ LLM │ │ Guardrails │ │
│ │ (Actions) │ │ (Reasoning) │ │ (Validation) │ │
│ └──────────────┘ └──────────────┘ └──────────────┘ │
│ │
│ ┌─────────────────────────────────────────────────────────┐│
│ │ Execution Loop ││
│ │ Observe → Think → Plan → Act → Reflect → Repeat ││
│ └─────────────────────────────────────────────────────────┘│
│ │
└─────────────────────────────────────────────────────────────┘
```

---

## Creating Agents

### Basic Agent

```python
import logging

logger = logging.getLogger(__name__)

from agenticaiframework import Agent, AgentConfig

# Create a simple agent
config = AgentConfig(
    name="assistant",
    role="Helpful AI Assistant",
    goal="Help users with their questions accurately and helpfully"
)

agent = Agent(config=config)

# Execute a task
result = agent.execute("What is the capital of France?")
logger.info(result.output)
# Output: The capital of France is Paris.
```

### Agent with Memory

```python
import logging

logger = logging.getLogger(__name__)

from agenticaiframework import Agent, AgentConfig, MemoryManager

# Initialize memory
memory = MemoryManager()

# Create agent with memory
agent = Agent(
    config=AgentConfig(
        name="remembering_assistant",
        role="Personal Assistant",
        goal="Help users while remembering context"
    ),
    memory=memory
)

# Agent remembers across interactions
result1 = agent.execute("My name is Alice and I like Python")
result2 = agent.execute("What's my name and what do I like?")
logger.info(result2.output)
# Output: Your name is Alice and you like Python.
```

### Agent with Tools

```python
from agenticaiframework import Agent, AgentConfig
from agenticaiframework.tools import SearchTool, CalculatorTool

# Create agent with tools
agent = Agent(
    config=AgentConfig(
        name="research_assistant",
        role="Research Analyst",
        goal="Research topics and provide accurate analysis",
        tools=[SearchTool(), CalculatorTool()]
    )
)

# Agent uses tools to complete tasks
result = agent.execute("What's the population of Tokyo and what's 15% of it?")
```

---

## Agent Configuration

### AgentConfig Options

```python
from agenticaiframework import AgentConfig

config = AgentConfig(
    # Identity
    name="research_agent",
    role="Senior Research Analyst",
    goal="Conduct thorough research and provide accurate insights",
    backstory="An expert analyst with 10 years of experience in data research",

    # LLM Settings
    model="gpt-4o",
    temperature=0.7,
    max_tokens=4096,

    # Execution Settings
    max_iterations=10,
    max_execution_time=300, # seconds

    # Tools
    tools=["search", "calculator", "python_repl"],

    # Behavior
    verbose=True,
    allow_delegation=True,
    cache_responses=True,

    # Memory
    memory_enabled=True,
    memory_limit=100, # entries

    # Guardrails
    validate_inputs=True,
    sanitize_outputs=True
)
```

### Role and Goal Design

```python
# Good: Specific role and clear goal
config = AgentConfig(
    name="code_reviewer",
    role="Senior Software Engineer specializing in Python code review",
    goal="Review code for bugs, security issues, and best practices. "
         "Provide actionable feedback with examples.",
    backstory="A senior engineer with expertise in Python, security, "
              "and software architecture. Known for thorough but constructive reviews."
)

# Better: Include constraints and preferences
config = AgentConfig(
    name="code_reviewer",
    role="Senior Software Engineer specializing in Python code review",
    goal="Review code for bugs, security issues, and best practices",
    constraints=["Focus on actionable feedback",
        "Prioritize security issues",
        "Include code examples in suggestions"
    ],
    preferences={
        "style_guide": "PEP 8",
        "max_line_length": 88,
        "prefer_type_hints": True
    }
)
```

### Model Configuration

```python
from agenticaiframework import AgentConfig, LLMConfig

# Basic model config
config = AgentConfig(
    name="assistant",
    model="gpt-4o-mini"
)

# Advanced model config
config = AgentConfig(
    name="assistant",
    llm=LLMConfig(
        provider="openai",
        model="gpt-4o",
        temperature=0.7,
        max_tokens=4096,
        top_p=0.95,
        frequency_penalty=0.0,
        presence_penalty=0.0,
        stop_sequences=["###"],
        timeout=60
    )
)

# Using different providers
config = AgentConfig(
    name="claude_assistant",
    llm=LLMConfig(
        provider="anthropic",
        model="claude-3-5-sonnet-20241022",
        max_tokens=4096
    )
)
```

---

## Agent Tools

### Adding Built-in Tools

```python
from agenticaiframework import Agent, AgentConfig
from agenticaiframework.tools import (
    SearchTool,
    WikipediaTool,
    CalculatorTool,
    PythonREPLTool,
    FileReadTool,
    FileWriteTool
)

agent = Agent(
    config=AgentConfig(
        name="versatile_assistant",
        role="Multi-skilled Assistant",
        tools=[SearchTool(),
            WikipediaTool(),
            CalculatorTool(),
            PythonREPLTool(),
            FileReadTool(),
            FileWriteTool()
        ]
    )
)
```

### Creating Custom Tools

```python
from agenticaiframework.tools import Tool, tool

# Method 1: Using decorator
@tool
def get_weather(location: str) -> str:
    """Get current weather for a location.

    Args:
        location: City name or coordinates

    Returns:
        Current weather conditions
    """
    # Implementation
    return f"Weather in {location}: Sunny, 72°F"

# Method 2: Using Tool class
class StockPriceTool(Tool):
    name = "stock_price"
    description = "Get current stock price for a ticker symbol"

    def _run(self, ticker: str) -> dict:
        # Implementation
        return {"ticker": ticker, "price": 150.25}

    async def _arun(self, ticker: str) -> dict:
        # Async implementation
        return await self._fetch_price(ticker)

# Add custom tools to agent
agent = Agent(
    config=AgentConfig(
        name="financial_analyst",
        tools=[get_weather, StockPriceTool()]
    )
)
```

### Tool Permissions

```python
from agenticaiframework import AgentConfig, ToolPermissions

config = AgentConfig(
    name="restricted_agent",
    tools=["search", "calculator", "file_read", "file_write"],
    tool_permissions=ToolPermissions(
        allowed_tools=["search", "calculator"],
        denied_tools=["file_write"],
        confirmation_required=["file_read"],
        rate_limits={
            "search": {"max_calls": 10, "window_seconds": 60}
        }
    )
)
```

---

## Agent Behaviors

### Execution Modes

=== "Single Task"
    ```python
import logging

logger = logging.getLogger(__name__)

    # Execute single task and return
    result = agent.execute("Analyze this data")
    logger.info(result.output)
    ```

=== "Iterative"
    ```python
    # Execute with multiple iterations
    result = agent.execute(
        "Research and write a report",
        max_iterations=5
    )
    ```

=== "Streaming"
    ```python
import logging

logger = logging.getLogger(__name__)

    # Stream responses
    async for chunk in agent.stream("Tell me a story"):
        logger.info(chunk, end="", flush=True)
    ```

=== "Batch"
    ```python
    # Process multiple tasks
    tasks = ["Analyze sales data",
        "Generate report",
        "Send summary email"
    ]
    results = await agent.execute_batch(tasks)
    ```

### Reasoning Strategies

```python
from agenticaiframework import AgentConfig, ReasoningStrategy

# Chain of Thought
config = AgentConfig(
    name="analyst",
    reasoning=ReasoningStrategy.CHAIN_OF_THOUGHT
)

# ReAct (Reason + Act)
config = AgentConfig(
    name="researcher",
    reasoning=ReasoningStrategy.REACT
)

# Plan and Execute
config = AgentConfig(
    name="planner",
    reasoning=ReasoningStrategy.PLAN_AND_EXECUTE
)

# Reflection (Self-critique)
config = AgentConfig(
    name="writer",
    reasoning=ReasoningStrategy.REFLECTION
)
```

### Self-Correction

```python
import logging

logger = logging.getLogger(__name__)

from agenticaiframework import AgentConfig

config = AgentConfig(
    name="self_correcting_agent",
    enable_self_correction=True,
    max_self_correction_attempts=3,
    self_correction_triggers=["error",
        "inconsistency",
        "low_confidence"
    ]
)

agent = Agent(config=config)

# Agent will automatically retry and correct errors
result = agent.execute("Calculate complex analysis")
logger.info(f"Attempts: {result.attempts}")
logger.info(f"Self-corrections: {result.corrections}")
```

---

## Agent Lifecycle

### States

```python
import logging

logger = logging.getLogger(__name__)

from agenticaiframework import Agent, AgentState

agent = Agent(config=config)

# Check agent state
logger.info(agent.state) # AgentState.IDLE

# State transitions happen automatically
result = agent.execute("Task") # State: RUNNING → IDLE

# Manual state control
agent.pause() # AgentState.PAUSED
agent.resume() # AgentState.RUNNING
agent.stop() # AgentState.TERMINATED
```

### Lifecycle Hooks

```python
import logging

logger = logging.getLogger(__name__)

from agenticaiframework import Agent, AgentConfig

class CustomAgent(Agent):
    def on_start(self):
        """Called when agent starts executing."""
        logger.info("Agent starting...")
        self.start_time = time.time()

    def on_complete(self, result):
        """Called when task completes."""
        duration = time.time() - self.start_time
        logger.info(f"Completed in {duration:.2f}s")

    def on_error(self, error):
        """Called when an error occurs."""
        logger.info(f"Error: {error}")
        self.log_error(error)

    def on_tool_use(self, tool_name, input_data):
        """Called before tool execution."""
        logger.info(f"Using tool: {tool_name}")

    def on_tool_result(self, tool_name, result):
        """Called after tool execution."""
        logger.info(f"Tool result: {result}")

agent = CustomAgent(config=config)
```

### Context Management

```python
# Use agent as context manager
async with Agent(config=config) as agent:
    result = await agent.execute("Task 1")
    result = await agent.execute("Task 2")
# Agent automatically cleaned up
```

---

## Agent Communication

### Inter-Agent Messaging

```python
from agenticaiframework import Agent, AgentConfig, Messenger

# Create agents
researcher = Agent(config=AgentConfig(name="researcher"))
writer = Agent(config=AgentConfig(name="writer"))

# Set up messenger
messenger = Messenger()
researcher.set_messenger(messenger)
writer.set_messenger(messenger)

# Agent sends message
researcher.send_message(
    to="writer",
    content={"research_data": research_results}
)

# Other agent receives
messages = writer.receive_messages()
```

### Delegation

```python
from agenticaiframework import Agent, AgentConfig

# Leader agent that can delegate
leader = Agent(
    config=AgentConfig(
        name="leader",
        role="Team Lead",
        allow_delegation=True,
        delegate_to=["researcher", "writer"]
    )
)

# Worker agents
researcher = Agent(config=AgentConfig(name="researcher"))
writer = Agent(config=AgentConfig(name="writer"))

# Leader delegates sub-tasks automatically
result = leader.execute(
    "Research AI trends and write a summary",
    available_agents=[researcher, writer]
)
```

---

## Error Handling

### Retry Configuration

```python
from agenticaiframework import AgentConfig, RetryConfig

config = AgentConfig(
    name="resilient_agent",
    retry=RetryConfig(
        max_retries=3,
        retry_delay=1.0,
        retry_backoff=2.0,
        retry_on_exceptions=["RateLimitError",
            "TimeoutError",
            "ConnectionError"
        ]
    )
)
```

### Fallback Behavior

```python
from agenticaiframework import AgentConfig, FallbackConfig

config = AgentConfig(
    name="robust_agent",
    fallback=FallbackConfig(
        # Fallback model if primary fails
        fallback_model="gpt-3.5-turbo",

        # Fallback tools if primary tool fails
        tool_fallbacks={
            "web_search": "cached_search",
            "api_call": "mock_api"
        },

        # Default response on complete failure
        default_response="I'm unable to complete this task at the moment."
    )
)
```

### Exception Handling

```python
import logging

logger = logging.getLogger(__name__)

from agenticaiframework import Agent, AgentError, ToolError, LLMError

try:
    result = agent.execute("Complex task")
except ToolError as e:
    logger.info(f"Tool failed: {e.tool_name} - {e.message}")
except LLMError as e:
    logger.info(f"LLM error: {e.message}")
except AgentError as e:
    logger.info(f"Agent error: {e.message}")
```

---

## Monitoring & Observability

### Execution Metrics

```python
import logging

logger = logging.getLogger(__name__)

result = agent.execute("Task")

# Access metrics
logger.info(f"Duration: {result.metrics.duration_ms}ms")
logger.info(f"Tokens used: {result.metrics.total_tokens}")
logger.info(f"Tool calls: {result.metrics.tool_calls}")
logger.info(f"LLM calls: {result.metrics.llm_calls}")
logger.info(f"Cost: ${result.metrics.estimated_cost:.4f}")
```

### Tracing

```python
from agenticaiframework import Agent, AgentConfig
from agenticaiframework.tracing import TracingConfig

config = AgentConfig(
    name="traced_agent",
    tracing=TracingConfig(
        enabled=True,
        exporter="jaeger",
        endpoint="http://localhost:14268/api/traces",
        sample_rate=1.0
    )
)

agent = Agent(config=config)
# All executions are automatically traced
```

### Logging

```python
import logging
from agenticaiframework import Agent, AgentConfig

# Configure logging
logging.basicConfig(level=logging.INFO)

config = AgentConfig(
    name="logged_agent",
    verbose=True,
    log_level="DEBUG",
    log_tool_calls=True,
    log_llm_calls=True,
    log_thoughts=True
)

agent = Agent(config=config)
```

---

## Best Practices

### 1. Clear Role Definition

```python
# Good: Specific and focused
config = AgentConfig(
    name="python_expert",
    role="Python Developer specializing in data processing",
    goal="Write efficient, clean Python code for data pipelines"
)

# Avoid: Vague and broad
config = AgentConfig(
    name="helper",
    role="Assistant",
    goal="Help with stuff"
)
```

### 2. Appropriate Tool Selection

```python
# Only include tools the agent needs
config = AgentConfig(
    name="researcher",
    tools=[SearchTool(), WikipediaTool()] # Research-focused tools
)

# Don't overload with unnecessary tools
```

### 3. Set Reasonable Limits

```python
config = AgentConfig(
    name="bounded_agent",
    max_iterations=10, # Prevent infinite loops
    max_execution_time=300, # 5 minute timeout
    max_tokens=4096, # Token limit
    memory_limit=100 # Memory entries limit
)
```

### 4. Enable Appropriate Guardrails

```python
config = AgentConfig(
    name="safe_agent",
    validate_inputs=True,
    sanitize_outputs=True,
    pii_detection=True,
    content_filtering=True
)
```

---

## API Reference

For complete API documentation, see:

- [Agent API](API_REFERENCE.md#agent)
- [AgentConfig API](API_REFERENCE.md#agentconfig)
- [AgentState API](API_REFERENCE.md#agentstate)
- [Tool API](API_REFERENCE.md#tool)
