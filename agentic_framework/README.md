# Agentic Framework SDK

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/Python-3.6%2B-blue.svg)](https://www.python.org/downloads/)

A Python-based SDK for building agentic applications with lightweight, high-performance agents. The Agentic Framework simplifies the development of complex agent-driven operations by providing a comprehensive set of tools and components with built-in security, monitoring, observability, and fine-grained configuration options.

## Overview

The Agentic Framework SDK enables developers to create scalable and modular agentic applications for a wide range of use cases, from simple task automation to enterprise-grade systems. It supports single and multiple agents, flexible process orchestration (sequential, parallel, hybrid), and multimodal capabilities for processing text, images, voice, video, and more.

### Key Features

- **Python-based SDK**: Seamlessly integrates into existing Python projects for building agentic applications.
- **Lightweight and High-Performance Agents**: Efficient execution for handling varied workloads.
- **Built-in Security Mechanisms**: Authentication, authorization, encryption, and sandboxing for safe operations.
- **Integrated Monitoring and Observability**: Real-time insights with metrics, events, dashboards, and anomaly detection.
- **Fine-grained Configurable Parameters**: Detailed customization with environment-specific profiles.
- **Support for Single and Multiple Agents**: Collaborative workflows with inter-agent communication.
- **Flexible Process Orchestration**: Sequential, parallel, and hybrid execution strategies.
- **Extensible Architecture**: Hubs for agents, prompts, tools, guardrails, and LLMs.
- **Comprehensive Memory Management**: Short-term, long-term, and external memory with semantic indexing.
- **Multiple Communication Protocols**: Streamtable HTTP, WebSockets, gRPC, and more with secure encryption.
- **Configurable Guardrails and Evaluation**: Safety, compliance, and performance assessment mechanisms.
- **Scalable and Modular Design**: Suitable for enterprise-grade applications.
- **Multimodal Capabilities**: Support for text, images, voice, video, and structured data processing.
- **Cross-platform Deployment**: Cloud, on-premise, and edge environments.
- **Extensive Integration Support**: APIs, databases, external tools, and services.

## Core Components

The Agentic Framework SDK is built around a modular architecture with the following core components:

- **Agents**: Autonomous entities for task execution and decision-making with multimodal support.
- **Prompts**: Structured inputs to guide agent behavior with dynamic generation and chaining.
- **Process**: Workflow orchestration with sequential, parallel, and hybrid execution strategies.
- **Tasks**: Work units assigned to agents with prioritization and dependency handling.
- **MCP Tools**: Modular extensions to enhance agent capabilities with external integrations.
- **Monitoring and Observability**: Real-time insights into performance, health, and behavior.
- **Guardrails**: Safety and compliance mechanisms to enforce operational boundaries.
- **Evaluation**: Performance assessment with automated testing and human-in-the-loop review.
- **Knowledge Retrieval**: Retrieval-Augmented Generation (RAG) and semantic search for informed decision-making.
- **Large Language Models (LLMs)**: Integration with LLMs for advanced natural language processing.
- **Communication Protocols**: Secure and efficient data exchange with multiple protocol options.
- **Memory**: Short-term, long-term, and external memory for context retention and recall.
- **Hub**: Centralized repository for component management, discovery, and versioning.
- **Configurations**: Fine-grained settings for customizing component behavior.
- **Security**: Comprehensive mechanisms for authentication, encryption, and audit logging.

## Installation

To install the Agentic Framework SDK, clone the repository and install it locally:

```bash
git clone https://github.com/your-repo/agentic-framework.git
cd agentic-framework
pip install -e .
```

## Getting Started

Here's a quick example to initialize the framework and create a simple agent:

```python
from agentic_framework import initialize_framework, Agent, SecurityManager, SecurityLevel

# Initialize the framework with a configuration
config = {
    "secret_key": "your_secret_key",
    "security_level": SecurityLevel.MEDIUM,
    "guardrail_rules": {"max_length": 100}
}
framework = initialize_framework(config)

# Access initialized components
security = framework["security"]
agents = framework["agents"]

# Authenticate an agent
credentials = {'username': 'agent:default', 'password': 'secure_password_123'}
token = security.authenticate_component(credentials)

# Create and register an agent
agent = Agent(name="SimpleAgent", supported_modalities=["text"])
agents.register_agent(agent)
agent.start()

# Perform a task if access is granted
if security.check_access(token, "agent/SimpleAgent", "execute"):
    result = agent.perform_task("Simple task", modality="text")
    print(result)  # Output: Task Simple task performed by SimpleAgent using modality text
```

For detailed documentation, usage examples, and advanced configurations, refer to the [full documentation](docs/framework_documentation.md).

## Examples

### Multi-Agent Workflow

```python
from agentic_framework import initialize_framework, Agent, Task, Process

# Initialize framework
framework = initialize_framework()
agents = framework["agents"]
tasks = framework["tasks"]
processes = framework["processes"]

# Create agents
data_agent = Agent(name="DataCollector", supported_modalities=["text"])
analysis_agent = Agent(name="DataAnalyzer", supported_modalities=["text"])
agents.register_agent(data_agent)
agents.register_agent(analysis_agent)
data_agent.start()
analysis_agent.start()

# Create tasks
collect_task = Task(task_id="CollectData", description="Collect dataset", required_capabilities=["text"])
analyze_task = Task(task_id="AnalyzeData", description="Analyze dataset", required_capabilities=["text"])
tasks.register_task(collect_task)
tasks.register_task(analyze_task)
tasks.assign_task("CollectData", "DataCollector")
tasks.assign_task("AnalyzeData", "DataAnalyzer")

# Create a sequential process
process = Process(process_type="sequential", tasks=["CollectData", "AnalyzeData"])
processes.register_process(process)

# Execute the process
result = processes.execute_process(process.process_id)
print(result)  # Output: {'status': 'completed', 'results': [...]}
```

More examples are available in the [documentation](docs/framework_documentation.md).

## Contributing

We welcome contributions to the Agentic Framework SDK. To contribute:
1. Fork the repository.
2. Create a branch for your feature or bug fix.
3. Submit a pull request with a detailed description of your changes.

Please adhere to coding standards and include tests for new functionalities. For major changes, open an issue first to discuss the proposed feature.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contact

For questions, feedback, or support, please contact us at [contact@agenticframework.com](mailto:contact@agenticframework.com) or open an issue on GitHub.

---

*Agentic Framework SDK - Empowering Agent-Driven Innovation*
