---
tags:
  - FAQ
  - help
  - troubleshooting
  - questions
---

# ❓ Frequently Asked Questions (FAQ)

<div class="annotate" markdown>

**Quick answers to common questions**

Find solutions and learn best practices

</div>

## 🎯 Quick Navigation

<div class="grid cards" markdown>

-   :material-information:{ .lg } **General**
    
    About the framework
    
    [:octicons-arrow-right-24: Learn More](#general-questions)

-   :material-rocket-launch:{ .lg } **Getting Started**
    
    Installation and setup
    
    [:octicons-arrow-right-24: Get Started](#getting-started)

-   :material-bug:{ .lg } **Troubleshooting**
    
    Common issues and fixes
    
    [:octicons-arrow-right-24: Fix Issues](#troubleshooting)

-   :material-code-tags:{ .lg } **Usage**
    
    How-to questions
    
    [:octicons-arrow-right-24: Learn How](#agent-questions)

</div>


## 📊 General Questions

### What is AgenticAI Framework?

AgenticAI Framework is an enterprise-grade Python SDK for building intelligent agentic applications. It provides a comprehensive toolkit for creating, managing, and orchestrating AI agents with advanced features like memory management, multi-agent collaboration, guardrails, and evaluation systems.

### Who should use AgenticAI Framework?

- **AI/ML Engineers** building production agent systems
- **Software Developers** creating AI-powered applications
- **Data Scientists** implementing agentic workflows
- **Enterprise Teams** requiring scalable agent orchestration
- **Researchers** experimenting with multi-agent systems

### What are the system requirements?

- **Python**: 3.8 or higher (3.11+ recommended)
- **Memory**: Minimum 4GB RAM (8GB+ recommended)
- **OS**: Linux, macOS, or Windows
- **Dependencies**: See `requirements.txt`

### How does it compare to other frameworks?

| Feature | AgenticAI | CrewAI | LangChain | AutoGPT |
|---------|-----------|---------|-----------|---------|
| Multi-Agent Orchestration | ✅ | ✅ | ⚠️ | ✅ |
| Memory Management | ✅ | ⚠️ | ✅ | ⚠️ |
| Advanced Evaluation | ✅ | ❌ | ❌ | ❌ |
| Guardrails & Safety | ✅ | ❌ | ⚠️ | ❌ |
| Production-Ready Monitoring | ✅ | ❌ | ⚠️ | ❌ |
| MCP Tools Support | ✅ | ❌ | ❌ | ❌ |
| Agent Hub | ✅ | ❌ | ❌ | ❌ |
| 12-Tier Evaluation | ✅ | ❌ | ❌ | ❌ |


## 🚀 Getting Started

### How do I install AgenticAI Framework?

```bash
# Basic installation
pip install agenticaiframework

# With all extras
pip install agenticaiframework[all]

# Development installation
git clone https://github.com/isathish/agenticaiframework.git
cd agenticaiframework
pip install -e .[dev]
```

### Do I need API keys?

Yes, for LLM providers:

- **OpenAI**: `OPENAI_API_KEY` ([Get key](https://platform.openai.com/api-keys))
- **Anthropic**: `ANTHROPIC_API_KEY` ([Get key](https://console.anthropic.com/))
- **Azure OpenAI**: `AZURE_OPENAI_KEY` and `AZURE_OPENAI_ENDPOINT`

```bash
# Set environment variables
export OPENAI_API_KEY="sk-your-key-here"
export ANTHROPIC_API_KEY="sk-ant-your-key"
```

### What's the quickest way to create an agent?

```python
from agenticaiframework.agents import Agent

# Create an agent in 3 lines
agent = Agent(name="assistant", role="helper", capabilities=["chat"])
agent.start()
result = agent.execute_task(lambda: "Hello!")
```

### Where can I find examples?

- **Documentation**: [Examples Section](EXAMPLES.md)
- **GitHub**: [examples/ directory](https://github.com/isathish/agenticaiframework/tree/main/examples)
- **Tutorials**: [Quick Start Guide](quick-start.md)


## 🤖 Agent Questions

### How many agents can I run simultaneously?

Default: 50 agents. Configurable via:

```python
from agenticaiframework.agents import AgentManager

manager = AgentManager(max_agents=100)  # Increase limit
```

Actual limit depends on:
- Available system resources
- Task complexity
- LLM API rate limits

### Can agents communicate with each other?

Yes! Multiple patterns:

```python
# 1. Direct messaging
agent1.send_message(agent2, "Process this data")

# 2. Broadcast
agent_manager.broadcast("System alert")

# 3. Pub/Sub
pubsub.subscribe("topic", agent.handle_message)
pubsub.publish("topic", {"data": "value"})
```

### How do I handle agent failures?

```python
from agenticaiframework.agents import Agent

agent = Agent(
    name="resilient_agent",
    retry_attempts=3,
    retry_delay=5,
    fallback_strategy="graceful"
)

try:
    result = agent.execute_task(risky_function)
except Exception as e:
    # Handle failure
    logger.error(f"Agent failed: {e}")
```

### Can I use custom LLMs?

Yes! Implement the LLM interface:

```python
from agenticaiframework.llms import BaseLLM

class CustomLLM(BaseLLM):
    def generate(self, prompt: str, **kwargs):
        # Your custom implementation
        return response

agent = Agent(name="agent", llm=CustomLLM())
```


## 💾 Memory Questions

### What memory backends are supported?

- **In-Memory**: Fast, volatile (default)
- **Redis**: Fast, persistent, distributed
- **SQLite**: Lightweight, file-based
- **PostgreSQL**: Production-grade, scalable
- **MongoDB**: Document-based

```python
from agenticaiframework.memory import MemoryManager

# Redis backend
memory = MemoryManager(backend="redis", redis_url="redis://localhost:6379")

# PostgreSQL backend
memory = MemoryManager(backend="postgres", postgres_url="postgresql://...")
```

### How long is memory retained?

Configurable via TTL (Time-To-Live):

```python
memory.store(
    key="session_data",
    value={"user": "john"},
    ttl=3600  # 1 hour
)
```

### Can I search through memory?

Yes! Multiple search options:

```python
# Semantic search
results = memory.search_semantic(
    query="customer support conversations",
    top_k=10
)

# Keyword search
results = memory.search_keyword(
    keywords=["support", "urgent"],
    limit=20
)

# Metadata filtering
results = memory.retrieve(
    filter={"agent_id": "agent_001", "status": "completed"}
)
```


## 🧠 LLM Questions

### Which LLM providers are supported?

- **OpenAI**: GPT-4, GPT-3.5
- **Anthropic**: Claude 3 (Opus, Sonnet, Haiku)
- **Azure OpenAI**: GPT-4, GPT-3.5
- **Google**: PaLM 2, Gemini (via API)
- **Local Models**: Via Ollama, LM Studio

### How do I reduce LLM costs?

1. **Use Cheaper Models**:
```python
llm_manager.set_model("gpt-3.5-turbo")  # vs gpt-4
```

2. **Enable Caching**:
```python
llm_manager.enable_cache(ttl=3600)
```

3. **Reduce Token Usage**:
```python
# Shorter prompts
llm_manager.generate(prompt, max_tokens=500)  # vs 4000
```

4. **Batch Requests**:
```python
responses = llm_manager.generate_batch(prompts)
```

### Do you support streaming responses?

Yes!

```python
async for chunk in llm_manager.generate_stream(prompt):
    print(chunk, end="", flush=True)
```

### Can I use local models?

Yes, via Ollama:

```python
from agenticaiframework.llms import LLMManager

llm = LLMManager(
    provider="ollama",
    base_url="http://localhost:11434",
    model="llama2"
)
```


## 📊 Performance Questions

### What's the typical latency?

| Operation | Latency (P50) | Latency (P95) |
|-----------|---------------|---------------|
| Agent Creation | < 10ms | < 50ms |
| Task Execution | 100-500ms | 1-2s |
| Memory Retrieval | < 5ms | < 20ms |
| LLM Call | 500ms-2s | 2-5s |

*Latencies depend on LLM provider, task complexity, and system resources.*

### How do I optimize performance?

See [Performance Guide](performance.md) for detailed strategies:

1. **Enable Caching**
2. **Use Connection Pooling**
3. **Batch Operations**
4. **Async I/O**
5. **Optimize Prompts**

### Can it handle production load?

Yes! Designed for production:

- **Horizontal Scaling**: Run multiple instances
- **Load Balancing**: Built-in support
- **Circuit Breakers**: Prevent cascade failures
- **Rate Limiting**: Protect APIs
- **Monitoring**: Prometheus/Grafana integration


## 🛡️ Security Questions

### Is it secure for production use?

Yes! Security features:

- **Input Validation**: Prevent injection attacks
- **API Key Management**: Secure secret handling
- **Content Moderation**: Guardrails for safe outputs
- **Rate Limiting**: Prevent abuse
- **Audit Logging**: Track all operations

### How are API keys stored?

Never hardcode keys! Use:

1. **Environment Variables**:
```bash
export OPENAI_API_KEY="sk-your-key"
```

2. **Secret Managers**:
```python
# AWS Secrets Manager
api_key = get_secret("openai-api-key")

# Azure Key Vault
api_key = get_azure_secret(vault_url, "openai-key")
```

### Does it filter harmful content?

Yes, via Guardrails:

```python
from agenticaiframework.guardrails import GuardrailManager

guardrails = GuardrailManager()
guardrails.add_rule("toxicity", threshold=0.7)
guardrails.add_rule("pii_detection", enabled=True)

# Validate content
is_safe = guardrails.validate(user_input)
```


## 🧪 Testing Questions

### How do I test my agents?

```python
import pytest
from agenticaiframework.agents import Agent

def test_agent_creation():
    agent = Agent(name="test_agent", role="tester")
    assert agent.name == "test_agent"
    assert agent.status == "initialized"

def test_agent_task_execution():
    agent = Agent(name="test_agent", role="tester")
    result = agent.execute_task(lambda: "success")
    assert result == "success"
```

### Are there built-in test utilities?

Yes!

```python
from agenticaiframework.testing import MockLLM, MockMemory

# Mock LLM for testing
mock_llm = MockLLM(responses=["Test response"])
agent = Agent(name="test", llm=mock_llm)

# Mock memory
mock_memory = MockMemory()
agent = Agent(name="test", memory=mock_memory)
```

### What's the test coverage?

Current coverage: **66%**

Run tests:
```bash
# Run all tests
pytest

# With coverage
pytest --cov=agenticaiframework

# Specific module
pytest tests/test_agents.py
```


## 🐛 Troubleshooting

### Agent not starting?

Common causes:

1. **Missing API Key**:
```python
# Check environment
import os
print(os.getenv("OPENAI_API_KEY"))
```

2. **Invalid Configuration**:
```python
# Validate config
config_manager.validate()
```

3. **Resource Limits**:
```python
# Check resource usage
monitor.get_system_stats()
```

### Memory issues?

```python
# Clear stale memories
memory_manager.clear_expired()

# Reduce TTL
memory_manager.set_default_ttl(1800)  # 30 minutes

# Use disk-based backend
memory_manager.switch_backend("sqlite")
```

### LLM rate limiting?

```python
from agenticaiframework.llms import LLMManager

llm = LLMManager(
    rate_limit=10,  # requests per minute
    retry_on_rate_limit=True,
    backoff_factor=2
)
```

### Where can I get help?

- **Documentation**: [https://isathish.github.io/agenticaiframework/](https://isathish.github.io/agenticaiframework/)
- **GitHub Issues**: [Report bugs](https://github.com/isathish/agenticaiframework/issues)
- **Discussions**: [Ask questions](https://github.com/isathish/agenticaiframework/discussions)
- **Discord**: Coming soon!


## 📚 Advanced Topics

### Can I deploy to production?

Yes! See [Deployment Guide](deployment.md):

- **Docker**: Containerized deployment
- **Kubernetes**: Scalable orchestration
- **AWS/Azure/GCP**: Cloud deployment
- **Serverless**: Lambda/Functions

### How do I monitor in production?

```python
from agenticaiframework.monitoring import MonitoringManager

monitor = MonitoringManager()
monitor.enable_prometheus_export(port=9090)
monitor.enable_grafana_integration()

# Track metrics
monitor.record_metric("agent_execution_time", duration)
monitor.record_error("llm_timeout", error_details)
```

### Can I create custom evaluators?

Yes!

```python
from agenticaiframework.evaluation import BaseEvaluator

class CustomEvaluator(BaseEvaluator):
    def evaluate(self, data):
        # Your evaluation logic
        score = calculate_score(data)
        return {"score": score, "passed": score > 0.8}

evaluator = CustomEvaluator()
result = evaluator.evaluate(test_data)
```

### Is there enterprise support?

Currently open-source. Enterprise support coming soon:
- Priority support
- Custom features
- SLA guarantees
- Training & onboarding


## 💡 Best Practices

### Agent Design

- ✅ Single responsibility per agent
- ✅ Clear role definition
- ✅ Comprehensive error handling
- ✅ Appropriate timeout values
- ❌ Don't create too many agents
- ❌ Avoid circular dependencies

### Memory Management

- ✅ Set appropriate TTLs
- ✅ Use tiered storage (hot/warm/cold)
- ✅ Regular cleanup of stale data
- ✅ Monitor memory usage
- ❌ Don't store large objects
- ❌ Avoid memory leaks

### LLM Usage

- ✅ Cache responses
- ✅ Use appropriate models
- ✅ Optimize prompts
- ✅ Handle rate limits
- ❌ Don't use GPT-4 for simple tasks
- ❌ Avoid redundant API calls


## 🔗 Additional Resources

- **Quick Start**: [Get started in 5 minutes](quick-start.md)
- **API Reference**: [Complete API docs](API_REFERENCE.md)
- **Examples**: [Real-world examples](EXAMPLES.md)
- **Best Practices**: [Production guidelines](best-practices.md)
- **Architecture**: [System design](architecture.md)
- **Contributing**: [Contribution guide](contributing.md)


## ❓ Still Have Questions?

**Can't find your answer?**

1. Search the [documentation](https://isathish.github.io/agenticaiframework/)
2. Check [existing issues](https://github.com/isathish/agenticaiframework/issues)
3. Ask in [discussions](https://github.com/isathish/agenticaiframework/discussions)
4. Open a [new issue](https://github.com/isathish/agenticaiframework/issues/new)


<div align="center">

**[⬆ Back to Top](#-frequently-asked-questions-faq)**

</div>
