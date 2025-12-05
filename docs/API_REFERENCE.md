# API Reference

Complete API reference for the AgenticAI Framework.

---

## Module Overview

### agenticaiframework.agents

**Classes:**
- `Agent(name, role, capabilities, config)` – Base agent class
- `AgentManager()` – Multi-agent orchestration
- `ContextManager(max_tokens)` – Context window management

**Agent Methods:**
- `start()` – Start the agent
- `pause()` – Pause agent execution
- `resume()` – Resume agent execution
- `stop()` – Stop the agent
- `execute_task(task_callable, *args, **kwargs)` – Execute a task

**AgentManager Methods:**
- `register_agent(agent)` – Register an agent
- `get_agent(agent_id)` – Get agent by ID
- `list_agents()` – List all agents
- `remove_agent(agent_id)` – Remove an agent
- `broadcast(message)` – Broadcast to all agents

**ContextManager Methods:**
- `add_context(content, importance)` – Add context with importance weighting
- `get_context_summary()` – Get context summary
- `get_stats()` – Get context statistics
- `clear()` – Clear context

### agenticaiframework.communication

**Classes:**
- `CommunicationManager()` – Protocol-based communication

**Methods:**
- `register_protocol(name, handler_fn)` – Register communication protocol
- `register_handler(handler_fn, name)` – Register handler (alias)
- `send(protocol, data)` – Send data via protocol
- `send_message(message, protocol)` – Send message
- `list_protocols()` – List registered protocols

### agenticaiframework.configurations

**Classes:**
- `ConfigurationManager()` – Configuration management

**Methods:**
- `set(key, value)` – Set configuration value
- `get(key, default)` – Get configuration value
- `update(config_dict)` – Update multiple values
- `remove(key)` – Remove configuration
- `list_configs()` – List all configurations

### agenticaiframework.evaluation

**Classes:**
- `EvaluationSystem()` – Evaluation and scoring

**Methods:**
- `define_metric(name, evaluator_fn)` – Define evaluation metric
- `evaluate(data)` – Evaluate data against metrics
- `get_metrics()` – Get defined metrics

### agenticaiframework.guardrails

**Classes:**
- `Guardrail(name, validation_fn, policy, severity)` – Single guardrail
- `GuardrailManager()` – Guardrail orchestration

**Guardrail Methods:**
- `validate(data)` – Validate data
- `get_stats()` – Get guardrail statistics

**GuardrailManager Methods:**
- `register_guardrail(guardrail)` – Register guardrail
- `enforce_guardrails(data)` – Enforce all guardrails
- `get_guardrail_by_name(name)` – Get guardrail by name
- `list_guardrails()` – List all guardrails

### agenticaiframework.hub

**Classes:**
- `Hub()` – Agent and tool registry

**Methods:**
- `register_agent(name, agent_class)` – Register agent class
- `get_agent(name)` – Get registered agent
- `list_agents()` – List agents
- `remove_agent(name)` – Remove agent
- `register_tool(name, tool_fn)` – Register tool
- `get_tool(name)` – Get tool

### agenticaiframework.knowledge

**Classes:**
- `KnowledgeRetriever()` – Knowledge base operations

**Methods:**
- `register_source(name, source_fn)` – Register knowledge source
- `retrieve(query, source)` – Retrieve knowledge
- `clear_cache()` – Clear retrieval cache

### agenticaiframework.llms

**Classes:**
- `LLMManager()` – LLM lifecycle management
- `CircuitBreaker(failure_threshold)` – Circuit breaker for reliability

**LLMManager Methods:**
- `register_model(name, model_instance)` – Register LLM
- `set_active_model(name)` – Set active model
- `generate(prompt, **kwargs)` – Generate response
- `list_models()` – List registered models

**CircuitBreaker Methods:**
- `call(fn, *args, **kwargs)` – Execute with circuit breaker
- `reset()` – Reset circuit breaker state

### agenticaiframework.mcp_tools

**Classes:**
- `MCPToolManager()` – MCP tool management

**Methods:**
- `register_tool(name, tool_fn)` – Register MCP tool
- `invoke_tool(name, *args, **kwargs)` – Invoke tool
- `list_tools()` – List registered tools

### agenticaiframework.memory

**Classes:**
- `MemoryEntry(key, value, ttl, priority, metadata)` – Memory entry
- `MemoryManager(short_term_limit, long_term_limit)` – Multi-tier memory

**MemoryManager Methods:**
- `store(key, value, memory_type, ttl, priority, metadata)` – Store memory
- `retrieve(key)` – Retrieve memory
- `search(query)` – Search memories
- `consolidate()` – Consolidate memories
- `get_stats()` – Get memory statistics
- `clear_short_term()` – Clear short-term memory
- `clear_long_term()` – Clear long-term memory
- `clear_external()` – Clear external memory
- `clear_all()` – Clear all memory

### agenticaiframework.monitoring

**Classes:**
- `MonitoringSystem()` – System monitoring

**Methods:**
- `log(message, level)` – Log message
- `track_metric(name, value)` – Track metric
- `create_alert(name, condition_fn)` – Create alert
- `get_metrics()` – Get metrics

### agenticaiframework.processes

**Classes:**
- `Process(name, steps)` – Process definition

**Methods:**
- `run(*args, **kwargs)` – Run process
- `run_async(*args, **kwargs)` – Run process asynchronously

### agenticaiframework.prompts

**Classes:**
- `Prompt(template, metadata, enable_security)` – Prompt template
- `PromptManager(enable_security)` – Prompt management

**Prompt Methods:**
- `render(**kwargs)` – Render prompt
- `render_safe(**kwargs)` – Render with sanitization
- `update_template(new_template)` – Update template

**PromptManager Methods:**
- `register_prompt(prompt)` – Register prompt
- `get_prompt(prompt_id)` – Get prompt by ID
- `render_prompt(prompt_id, **kwargs)` – Render prompt
- `list_prompts()` – List prompts
- `delete_prompt(prompt_id)` – Delete prompt

### agenticaiframework.security

**Classes:**
- `PromptInjectionDetector(enable_logging, custom_patterns)` – Injection detection
- `InputValidator(max_length, allow_html, allow_scripts)` – Input validation
- `RateLimiter(max_requests, window_seconds, strategy)` – Rate limiting
- `ContentFilter(blocked_words, categories, severity_threshold)` – Content filtering
- `AuditLogger(log_file, retention_days, log_level)` – Audit logging
- `SecurityManager(enable_*)` – Unified security management

**PromptInjectionDetector Methods:**
- `detect(text)` – Detect injection attempts
- `add_pattern(pattern, severity)` – Add detection pattern
- `get_stats()` – Get detection statistics

**InputValidator Methods:**
- `validate(text)` – Validate input
- `sanitize(text)` – Sanitize input
- `sanitize_html(text)` – Remove HTML
- `sanitize_sql(text)` – Remove SQL injection patterns

**RateLimiter Methods:**
- `check_rate_limit(identifier)` – Check rate limit
- `get_remaining(identifier)` – Get remaining requests
- `reset(identifier)` – Reset rate limit

**ContentFilter Methods:**
- `filter_text(text)` – Filter content
- `add_blocked_word(word, category)` – Add blocked word
- `get_stats()` – Get filter statistics

**AuditLogger Methods:**
- `log_event(event_type, details)` – Log security event
- `query_logs(filters)` – Query logs
- `clear_old_logs()` – Clear old logs

**SecurityManager Methods:**
- `validate_input(text, user_id)` – Comprehensive validation
- `get_security_report()` – Get security report

### agenticaiframework.tasks

**Classes:**
- `Task(name, description, callable_fn)` – Task definition
- `TaskManager()` – Task orchestration

**Task Methods:**
- `run(*args, **kwargs)` – Run task
- `get_result()` – Get task result

**TaskManager Methods:**
- `register_task(task)` – Register task
- `run_task(task_id, *args, **kwargs)` – Run task
- `run_all()` – Run all tasks
- `list_tasks()` – List tasks

---

## 7. Advanced Usage Examples

### Using Multiple Modules Together
```python
from agenticaiframework import Agent
from agenticaiframework.hub import register_agent, get_agent, register_tool
from agenticaiframework.memory import Memory

class EchoAgent(Agent):
    def act(self, input_data):
        return f"Echo: {input_data}"

register_agent("echo", EchoAgent)

memory = Memory()
memory.store("greeting", "Hello")

agent = get_agent("echo")
print(agent.act(memory.retrieve("greeting")))
```

### Custom Process with Guardrails
```python
from agenticaiframework.guardrails import add_guardrail
from agenticaiframework.processes import run_process

def no_numbers(input_data):
    if any(char.isdigit() for char in input_data):
        raise ValueError("Numbers are not allowed!")
    return input_data

add_guardrail(no_numbers)

def greet():
    return "Hello, World!"

print(run_process(greet))
```

---

## 8. Notes on API Stability

- Public APIs follow semantic versioning.
- Experimental APIs are marked in the documentation and may change.
# AgenticAI API Reference

This document provides a reference for the main classes, functions, and modules in **AgenticAI**.

---

## 1. Modules Overview

- **agenticaiframework.agents** – Agent base classes and implementations.
- **agenticaiframework.communication** – Communication utilities.
- **agenticaiframework.configurations** – Configuration management.
- **agenticaiframework.evaluation** – Evaluation and scoring.
- **agenticaiframework.guardrails** – Safety and compliance checks.
- **agenticaiframework.hub** – Registry for agents, tools, and processes.
- **agenticaiframework.knowledge** – Knowledge base management.
- **agenticaiframework.llms** – LLM integrations.
- **agenticaiframework.mcp_tools** – MCP tool integrations.
- **agenticaiframework.memory** – Memory management.
- **agenticaiframework.monitoring** – Monitoring and logging.
- **agenticaiframework.processes** – Workflow orchestration.
- **agenticaiframework.prompts** – Prompt templates.
- **agenticaiframework.tasks** – Task management.

---

## 2. Core Classes

### `Agent`
**Location:** `agenticaiframework.agents`

**Methods:**
- `act(input_data)` – Perform an action based on input.
- `observe(data)` – Observe environment or input.
- `plan()` – Plan next steps.

---

### `Memory`
**Location:** `agenticaiframework.memory`

**Methods:**
- `store(key, value)` – Store a value.
- `retrieve(key)` – Retrieve a value.
- `clear()` – Clear memory.

---

### `Hub`
**Location:** `agenticaiframework.hub`

**Functions:**
- `register_agent(name, cls)` – Register an agent.
- `get_agent(name)` – Retrieve an agent instance.
- `register_tool(name, func)` – Register a tool.
- `get_tool(name)` – Retrieve a tool.

---

## 3. Utility Functions

### `set_config(key, value)`
**Location:** `agenticaiframework.configurations`

Set a configuration value.

---

### `run_process(name, params)`
**Location:** `agenticaiframework.processes`

Run a registered process.

---

## 4. Example Usage

```python
from agenticaiframework.hub import get_agent

agent = get_agent("default_agent")
print(agent.act("Hello"))
```

---

## 5. Notes

- All public APIs are subject to semantic versioning.
- Internal APIs may change without notice.
