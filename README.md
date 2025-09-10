# 🌟 Agentic AI Framework

Agentic AI Framework (`agenticaiframework`) is a **next-generation Python SDK** for building **agentic applications** with advanced orchestration, monitoring, multimodal capabilities, and enterprise-grade scalability.  
It offers a **modular, extensible architecture** for creating intelligent agents that can interact, reason, and execute tasks across multiple domains — from simple automation to complex multi-agent ecosystems.

---

## 🚀 Why Agentic AI Framework?

Unlike other frameworks such as **LangChain**, **CrewAI**, and **AutoGen**, Agentic AI Framework is designed to be:

- **Lightweight & High-Performance** — Minimal overhead with optimized execution for real-time and large-scale workloads.
- **Fully Modular** — Every component (agents, prompts, tools, guardrails, LLMs) is pluggable and replaceable.
- **Enterprise-Ready** — Built-in monitoring, guardrails, and compliance features for production environments.
- **Multimodal** — Supports text, images, audio, and video processing.
- **Cross-Platform** — Works seamlessly on cloud, on-premise, and edge devices.
- **Integration-Friendly** — Easy to connect with APIs, databases, and external tools.
- **Security-Focused** — Built-in guardrails, validation, and policy enforcement.

---

## 🔍 Feature Comparison

| Feature / Framework       | Agentic AI Framework | LangChain | CrewAI | AutoGen |
|---------------------------|----------------------|-----------|--------|---------|
| Modular Architecture      | ✅ Fully Modular     | ⚠️ Partial| ⚠️ Partial | ⚠️ Partial |
| Multi-Agent Orchestration | ✅ Advanced          | ✅ Basic  | ✅     | ✅      |
| Built-in Guardrails       | ✅                   | ❌        | ⚠️ Limited | ❌      |
| Integrated Monitoring     | ✅                   | ❌        | ❌     | ❌      |
| Multimodal Support        | ✅ Text/Image/Audio/Video | ⚠️ Limited| ❌     | ⚠️ Limited |
| Cross-Platform Deployment | ✅                   | ⚠️ Limited| ❌     | ❌      |
| Memory Management         | ✅ Short/Long/External | ✅        | ⚠️ Limited | ✅      |
| Process Orchestration     | ✅ Sequential/Parallel/Hybrid | ⚠️ Limited| ✅     | ⚠️ Limited |
| Extensible Tooling        | ✅                   | ✅        | ⚠️ Limited | ⚠️ Limited |
| Security & Compliance     | ✅                   | ❌        | ❌     | ❌      |
| Knowledge Retrieval       | ✅                   | ⚠️ Limited| ❌     | ❌      |
| Evaluation System         | ✅                   | ❌        | ❌     | ❌      |

---

## ✨ Key Features

- **Agent Management** — Create, register, and control single or multiple agents.
- **Configuration Management** — Centralized configuration for all components.
- **Process Orchestration** — Sequential, parallel, and hybrid execution strategies.
- **Communication Layer** — Multiple protocols: HTTP, SSE, STDIO, WebSockets, gRPC, MQ.
- **Hub Architecture** — Central registry for agents, prompts, tools, and services.
- **Knowledge Retrieval** — Query and retrieve structured/unstructured knowledge.
- **Task Management** — Define, register, and execute tasks with inputs/outputs.
- **MCP Tools** — Modular tools with execution capabilities.
- **Prompt Management** — Create, store, and optimize prompts.
- **Monitoring System** — Metrics, events, and logs for observability.
- **Memory Management** — Short-term, long-term, and external memory storage.
- **Guardrails** — Validation and policy enforcement for safe execution.
- **LLM Management** — Register and use multiple LLMs with configurable parameters.
- **Evaluation System** — Define and run evaluation criteria for outputs.
- **Multimodal Capabilities** — Handle text, images, audio, and video.
- **Security & Compliance** — Built-in validation, logging, and policy enforcement.

---

## 📦 Installation

```bash
pip install agenticaiframework
```

---

## ⚡ Quick Start

```python
from agenticaiframework import Agent, AgentManager

# Create an agent
agent = Agent(
    name="ExampleAgent",
    role="assistant",
    capabilities=["text"],
    config={"temperature": 0.7}
)

# Manage agents
manager = AgentManager()
manager.register_agent(agent)

# Start the agent
agent.start()
```

---

## 📚 Examples

We provide **full working examples** for every module in the framework, including:

- Agent Management
- Configuration Management
- Processes (Basic & Advanced)
- Communication
- Hub
- Knowledge Retrieval
- Task Management
- MCP Tools
- Prompt Management
- Monitoring
- Memory Management
- Guardrails
- LLM Management
- Evaluation

See the [Full Examples Index](docs/examples/full_examples_index.md) for details.

---

## 📖 Documentation

Full documentation is available at: [https://isathish.github.io/agenticaiframework/](https://isathish.github.io/agenticaiframework/)

---

## 🧪 Testing

```bash
pytest
```

---

## 🤝 Contributing

We welcome contributions! Please see the contributing guidelines in the docs.

---

## 📄 License

MIT License - see the [LICENSE](LICENSE) file.
