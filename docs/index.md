---
title: AgenticAI Framework
description: The Enterprise-Grade Framework for Building Production AI Agent Systems
hide:
  - navigation
  - toc
---

<style>
.md-content__inner {
  max-width: 1400px;
  margin: 0 auto;
}
</style>

<div class="hero-section">
  <h1>🤖 AgenticAI Framework</h1>
  <p class="hero-subtitle">The Enterprise-Grade Python Framework for Building Production AI Agent Systems</p>
  
  <div class="hero-badges">
    <a href="https://pypi.org/project/agenticaiframework/"><img src="https://img.shields.io/pypi/v/agenticaiframework.svg?style=for-the-badge&logo=python&logoColor=white&color=6366f1" alt="PyPI Version"></a>
    <a href="https://github.com/sathishbabu89/agenticaiframework/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-10b981.svg?style=for-the-badge" alt="License"></a>
    <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.8+-06b6d4.svg?style=for-the-badge&logo=python&logoColor=white" alt="Python"></a>
    <a href="https://github.com/sathishbabu89/agenticaiframework"><img src="https://img.shields.io/badge/Enterprise-Ready-f59e0b.svg?style=for-the-badge" alt="Enterprise Ready"></a>
  </div>
  
  <div style="position: relative; z-index: 1;">
    <a href="quick-start/" class="md-button md-button--primary">🚀 Get Started</a>
    <a href="https://github.com/sathishbabu89/agenticaiframework" class="md-button" style="margin-left: 1rem;">⭐ Star on GitHub</a>
  </div>
</div>

## 📊 Framework at a Glance

<div class="stats-grid">
  <div class="stat-card">
    <div class="stat-number">380+</div>
    <div class="stat-label">Total Modules</div>
  </div>
  <div class="stat-card">
    <div class="stat-number">237</div>
    <div class="stat-label">Enterprise Modules</div>
  </div>
  <div class="stat-card">
    <div class="stat-number">35+</div>
    <div class="stat-label">Built-in Tools</div>
  </div>
  <div class="stat-card">
    <div class="stat-number">12</div>
    <div class="stat-label">Evaluation Tiers</div>
  </div>
  <div class="stat-card">
    <div class="stat-number">6</div>
    <div class="stat-label">Communication Protocols</div>
  </div>
  <div class="stat-card">
    <div class="stat-number">14</div>
    <div class="stat-label">Enterprise Categories</div>
  </div>
</div>

---

## 🌟 Why AgenticAI Framework?

<div class="grid cards" markdown>

-   :brain:{ .lg .middle } **Advanced Memory System**

    ---

    7 specialized memory managers with semantic search, compression, and persistence. Never lose context again.

    [:octicons-arrow-right-24: Explore Memory](memory.md)

-   :arrows_counterclockwise:{ .lg .middle } **Multi-Agent Orchestration**

    ---

    Build complex AI teams with hierarchical workflows, parallel execution, and intelligent routing.

    [:octicons-arrow-right-24: Learn Orchestration](orchestration.md)

-   :satellite:{ .lg .middle } **6 Communication Protocols**

    ---

    HTTP, WebSocket, SSE, MQTT, gRPC, and STDIO - connect agents any way you need.

    [:octicons-arrow-right-24: View Protocols](communication.md)

-   :hammer_and_wrench:{ .lg .middle } **35+ Production Tools**

    ---

    Search, code execution, file operations, database queries, web scraping, and more built-in.

    [:octicons-arrow-right-24: Browse Tools](tools.md)

-   :shield:{ .lg .middle } **Enterprise Security**

    ---

    Secrets management, input validation, output sanitization, RBAC, and compliance auditing.

    [:octicons-arrow-right-24: Security Guide](security.md)

-   :chart_with_upwards_trend:{ .lg .middle } **12-Tier Evaluation**

    ---

    Comprehensive testing framework for model quality, security, cost, and business metrics.

    [:octicons-arrow-right-24: Evaluation System](evaluation.md)

</div>

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        AgenticAI Framework Architecture                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │   Agent 1   │  │   Agent 2   │  │   Agent 3   │  │   Agent N   │        │
│  │  (Leader)   │  │ (Researcher)│  │  (Writer)   │  │ (Specialist)│        │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘        │
│         │                │                │                │               │
│         └────────────────┼────────────────┼────────────────┘               │
│                          │                │                                 │
│  ┌───────────────────────┴────────────────┴───────────────────────┐        │
│  │                    Orchestration Layer                          │        │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │        │
│  │  │  Workflow   │  │    Team     │  │   Router    │              │        │
│  │  │  Manager    │  │   Manager   │  │   Engine    │              │        │
│  │  └─────────────┘  └─────────────┘  └─────────────┘              │        │
│  └─────────────────────────────────────────────────────────────────┘        │
│                                    │                                        │
│  ┌─────────────────────────────────┴─────────────────────────────────┐     │
│  │                        Core Services Layer                         │     │
│  ├────────────┬────────────┬────────────┬────────────┬───────────────┤     │
│  │  Memory    │  State     │ Knowledge  │   Tool     │  LLM          │     │
│  │  Managers  │  Managers  │  Base      │   Registry │  Providers    │     │
│  │  (7 types) │  (7 types) │            │  (35+)     │  (Multiple)   │     │
│  └────────────┴────────────┴────────────┴────────────┴───────────────┘     │
│                                    │                                        │
│  ┌─────────────────────────────────┴─────────────────────────────────┐     │
│  │                    Infrastructure Layer                            │     │
│  ├──────────────┬──────────────┬──────────────┬──────────────────────┤     │
│  │ Communication│  Tracing &   │  Security &  │  Guardrails &        │     │
│  │ (6 protocols)│  Monitoring  │  Compliance  │  Validation          │     │
│  └──────────────┴──────────────┴──────────────┴──────────────────────┘     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Installation

```bash
pip install agenticaiframework
```

### Create Your First Agent

```python
from agenticaiframework import Agent, AgentConfig, MemoryManager

# Initialize memory management
memory = MemoryManager()

# Configure your agent
config = AgentConfig(
    name="research_assistant",
    role="Research Analyst",
    goal="Find and synthesize information accurately",
    model="gpt-4o-mini"
)

# Create and run the agent
agent = Agent(config=config, memory=memory)
result = agent.execute("Research the latest trends in AI agents")
print(result.output)
```

### Build a Multi-Agent Team

```python
from agenticaiframework import Agent, Team, WorkflowManager

# Create specialized agents
researcher = Agent(
    config=AgentConfig(name="researcher", role="Research Expert")
)
writer = Agent(
    config=AgentConfig(name="writer", role="Content Writer")
)
editor = Agent(
    config=AgentConfig(name="editor", role="Quality Editor")
)

# Build and run the team
team = Team(
    name="content_team",
    agents=[researcher, writer, editor],
    workflow=WorkflowManager.sequential()
)

result = team.execute("Create a comprehensive guide on AI safety")
```

[:octicons-arrow-right-24: See Full Quick Start Guide](quick-start.md)

---

## 💡 Core Modules

<div class="grid cards" markdown>

-   :robot:{ .lg } **Agents**

    ---

    Create intelligent agents with customizable roles, goals, tools, and behaviors.

    ```python
    from agenticaiframework import Agent, AgentConfig
    
    agent = Agent(config=AgentConfig(
        name="assistant",
        role="AI Assistant",
        tools=["search", "calculator"]
    ))
    ```

    [:octicons-arrow-right-24: Learn More](agents.md)

-   :floppy_disk:{ .lg } **Memory**

    ---

    7 specialized memory managers for different use cases.

    | Manager | Purpose |
    |---------|---------|
    | `MemoryManager` | General-purpose memory |
    | `AgentMemoryManager` | Agent-specific memories |
    | `WorkflowMemoryManager` | Workflow state tracking |
    | `OrchestrationMemoryManager` | Multi-agent coordination |
    | `KnowledgeMemoryManager` | Knowledge base storage |
    | `ToolMemoryManager` | Tool execution history |
    | `SpeechMemoryManager` | Voice interaction data |

    [:octicons-arrow-right-24: Explore Memory](memory.md)

-   :gear:{ .lg } **State Management**

    ---

    7 dedicated state managers for complete system control.

    - `AgentStateManager` - Agent lifecycle
    - `WorkflowStateManager` - Workflow execution
    - `ConversationStateManager` - Conversation context
    - `TaskStateManager` - Task tracking
    - `ContextStateManager` - Context windows
    - `ToolStateManager` - Tool states
    - `MemoryStateManager` - Memory states

    [:octicons-arrow-right-24: State Guide](state.md)

-   :satellite_antenna:{ .lg } **Communication**

    ---

    6 protocols for any integration scenario.

    - **HTTP** - REST API communication
    - **WebSocket** - Real-time bidirectional
    - **SSE** - Server-sent events streaming
    - **MQTT** - IoT message queuing
    - **gRPC** - High-performance RPC
    - **STDIO** - Process communication

    [:octicons-arrow-right-24: Protocols](communication.md)

</div>

---

## 🔧 35+ Built-in Tools

<div class="grid" markdown>

=== "Search & Information"
    - :mag: **Web Search** - Multi-engine search
    - :newspaper: **News Search** - Real-time news
    - :book: **Wikipedia** - Encyclopedia access
    - :link: **URL Fetch** - Web scraping
    - :globe_with_meridians: **DNS Lookup** - Network tools

=== "Code & Development"
    - :snake: **Python REPL** - Code execution
    - :package: **Package Manager** - Dependency management
    - :test_tube: **Test Runner** - Automated testing
    - :memo: **Code Analysis** - Static analysis
    - :bug: **Debugger** - Issue diagnosis

=== "File & Data"
    - :file_folder: **File Operations** - CRUD operations
    - :floppy_disk: **CSV Handler** - Tabular data
    - :page_facing_up: **JSON Tools** - JSON manipulation
    - :bar_chart: **Data Analysis** - Statistical analysis
    - :mag_right: **Text Search** - Content search

=== "Database & Storage"
    - :elephant: **PostgreSQL** - SQL databases
    - :leaves: **MongoDB** - NoSQL storage
    - :zap: **Redis** - Cache operations
    - :card_file_box: **Vector Store** - Embeddings
    - :cloud: **Cloud Storage** - S3, GCS, Azure

=== "AI & ML"
    - :brain: **Embeddings** - Vector generation
    - :art: **Image Generation** - DALL-E, Stable Diffusion
    - :microphone: **Speech-to-Text** - Audio transcription
    - :speaker: **Text-to-Speech** - Voice synthesis
    - :eyes: **Vision** - Image analysis

=== "Utilities"
    - :calendar: **DateTime** - Time operations
    - :lock: **Encryption** - Security tools
    - :envelope: **Email** - SMTP/IMAP
    - :bell: **Notifications** - Alerts & webhooks
    - :clipboard: **Clipboard** - System clipboard

</div>

[:octicons-arrow-right-24: Complete Tool Reference](tools.md)

---

## 📈 12-Tier Evaluation System

Comprehensive evaluation framework for production AI systems:

| Tier | Category | Evaluates |
|------|----------|-----------|
| 1 | **Model Quality** | Accuracy, coherence, hallucination detection |
| 2 | **Task Performance** | Completion rate, efficiency, error handling |
| 3 | **Tool Effectiveness** | Tool selection, execution success, latency |
| 4 | **Memory & RAG** | Retrieval accuracy, context relevance |
| 5 | **Autonomy** | Decision quality, self-correction |
| 6 | **Security** | Prompt injection, data leakage, PII handling |
| 7 | **Cost Optimization** | Token usage, API costs, resource efficiency |
| 8 | **Human Alignment** | Feedback incorporation, preference matching |
| 9 | **Drift Detection** | Performance degradation, distribution shift |
| 10 | **A/B Testing** | Variant comparison, statistical significance |
| 11 | **Canary Deployment** | Gradual rollout, risk mitigation |
| 12 | **Workflow Analytics** | End-to-end metrics, bottleneck detection |

[:octicons-arrow-right-24: Full Evaluation Guide](evaluation.md)

---

## 🛡️ Enterprise Features

<div class="grid cards" markdown>

-   :shield:{ .lg } **Security & Compliance**

    ---

    - Secrets management with encryption
    - Input validation & sanitization
    - RBAC with fine-grained permissions
    - Audit logging & compliance trails
    - PII detection & masking
    - SOC 2, HIPAA, GDPR ready

-   :chart_with_upwards_trend:{ .lg } **Monitoring & Observability**

    ---

    - OpenTelemetry integration
    - Distributed tracing
    - Custom metrics & dashboards
    - Real-time alerting
    - Performance profiling
    - Error tracking & analysis

-   :zap:{ .lg } **Scalability & Performance**

    ---

    - Async execution support
    - Connection pooling
    - Caching layers
    - Load balancing ready
    - Rate limiting
    - Circuit breakers

-   :rocket:{ .lg } **DevOps & Deployment**

    ---

    - Docker & Kubernetes ready
    - CI/CD pipeline templates
    - Infrastructure as Code
    - Multi-environment configs
    - Blue-green deployments
    - Rollback mechanisms

</div>

---

## 🎤 Speech Processing

Full-featured speech-to-text and text-to-speech capabilities:

```python
from agenticaiframework import SpeechMemoryManager, AgentConfig

# Initialize speech-enabled agent
speech_memory = SpeechMemoryManager()
agent = Agent(
    config=AgentConfig(
        name="voice_assistant",
        speech_enabled=True
    ),
    speech_memory=speech_memory
)

# Process voice input
transcript = agent.transcribe_audio("user_audio.wav")
response = agent.execute(transcript)
audio = agent.synthesize_speech(response.output)
```

**Supported Providers:**

- OpenAI Whisper (STT)
- Google Cloud Speech (STT/TTS)
- Azure Cognitive Services (STT/TTS)
- Amazon Transcribe/Polly (STT/TTS)
- ElevenLabs (TTS)

[:octicons-arrow-right-24: Speech Documentation](speech.md)

---

## 📚 Documentation

<div class="grid cards" markdown>

-   :rocket:{ .lg } **Getting Started**

    ---

    - [Quick Start Guide](quick-start.md)
    - [Installation](quick-start.md#installation)
    - [First Agent](quick-start.md#create-your-first-agent)
    - [Configuration](configuration-reference.md)

-   :book:{ .lg } **Core Concepts**

    ---

    - [Agents](agents.md)
    - [Memory Management](memory.md)
    - [State Management](state.md)
    - [Orchestration](orchestration.md)

-   :hammer_and_wrench:{ .lg } **Advanced Topics**

    ---

    - [Custom Tools](tools.md#custom-tools)
    - [Evaluation](evaluation.md)
    - [Security](security.md)
    - [Performance](performance.md)

-   :books:{ .lg } **Reference**

    ---

    - [API Reference](API_REFERENCE.md)
    - [Configuration](configuration-reference.md)
    - [CLI Reference](cli-reference.md)
    - [Changelog](changelog.md)

</div>

---

## 🤝 Community & Support

<div class="quick-links">
  <a href="https://github.com/sathishbabu89/agenticaiframework">
    :material-github: GitHub
  </a>
  <a href="https://github.com/sathishbabu89/agenticaiframework/issues">
    :material-bug: Issues
  </a>
  <a href="https://github.com/sathishbabu89/agenticaiframework/discussions">
    :material-forum: Discussions
  </a>
  <a href="contributing.md">
    :material-heart: Contributing
  </a>
</div>

---

## 📄 License

AgenticAI Framework is released under the **MIT License**.

```
MIT License

Copyright (c) 2024 Sathish Babu

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software...
```

[:octicons-arrow-right-24: Full License](https://github.com/sathishbabu89/agenticaiframework/blob/main/LICENSE)

---

<div style="text-align: center; margin-top: 3rem;">
  <p style="font-size: 1.25rem; color: var(--md-default-fg-color--light);">
    Built with ❤️ for the AI Agent Community
  </p>
  <p>
    <a href="quick-start/" class="md-button md-button--primary">Get Started Now</a>
  </p>
</div>
