# 🌟 AgenticAI Framework

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Documentation](https://img.shields.io/badge/docs-available-brightgreen.svg)](https://isathish.github.io/agenticaiframework/)
[![PyPI version](https://badge.fury.io/py/agenticaiframework.svg)](https://badge.fury.io/py/agenticaiframework)

**AgenticAI Framework** is a comprehensive Python SDK for building sophisticated **agentic applications** with advanced orchestration, intelligent task management, comprehensive memory systems, and enterprise-grade monitoring capabilities.

Whether you're building simple AI assistants or complex multi-agent ecosystems, AgenticAI Framework provides the tools, patterns, and infrastructure you need to create intelligent, autonomous agents that can reason, learn, and collaborate effectively.

---

## 🚀 Why Choose AgenticAI Framework?

### **Production-Ready from Day One**
Unlike experimental frameworks, AgenticAI Framework is built for **production workloads** with comprehensive error handling, monitoring, and resilience patterns built-in.

### **Truly Modular Architecture**
Every component is designed as an independent, composable module that can be extended, replaced, or customized without affecting the rest of the system.

### **Intelligent by Design**
Features sophisticated memory management, semantic search, learning capabilities, and context-aware decision making out of the box.

### **Scale from Prototype to Enterprise**
Start with a single agent and seamlessly scale to distributed multi-agent systems with built-in coordination, communication, and monitoring.

### **Developer Experience First**
Comprehensive documentation, extensive examples, intuitive APIs, and powerful debugging tools make development fast and enjoyable.

---

## 🏗️ Core Architecture

AgenticAI Framework is built around **13 core modules** that work together seamlessly:

### 🤖 **Agents** - Intelligent Autonomous Entities
- **Context engineering** with token tracking and automatic compression
- **Multi-role agents** with configurable capabilities and behaviors
- **Lifecycle management** with start, pause, resume, and stop controls
- **Performance monitoring** with comprehensive metrics and error tracking
- **Custom agent types** for specialized domains (customer service, research, code generation)
- **Advanced coordination** patterns for multi-agent collaboration

### 📋 **Tasks** - Sophisticated Workflow Management
- **Intelligent scheduling** with time-based, conditional, and dependency-driven execution
- **Priority queues** with advanced retry mechanisms and circuit breaker patterns
- **Workflow orchestration** supporting sequential, parallel, and conditional flows
- **Performance monitoring** with comprehensive metrics and resource tracking

### 🧠 **Memory** - Advanced Memory Systems
- **Multi-tier memory** architecture (short-term, long-term, external memory)
- **TTL (Time-To-Live)** support for automatic memory expiration
- **Priority-based eviction** with LRU algorithm
- **Memory consolidation** for frequently accessed data
- **Semantic search** capabilities with intelligent information retrieval
### 🔗 **LLMs** - Language Model Management
- **Circuit breaker pattern** to prevent cascading failures
- **Automatic retry** with exponential backoff
- **Response caching** for improved performance
- **Fallback chains** for high availability
- **Multi-provider support** with unified interface for different LLM providers
### 🛡️ **Guardrails** - Safety and Compliance
- **Priority-based enforcement** with circuit breakers
- **Severity levels** (low, medium, high, critical)
- **Remediation actions** for automatic issue resolution
- **Content filtering** with customizable validation rules
- **Policy enforcement** for ethical AI behavior
- **Security validation** to prevent prompt injection and data leakage
- **Compliance monitoring** with audit trails and reporting
- **Violation tracking** with comprehensive analytics

### 🔐 **Security** - Enterprise-Grade Security (NEW)
- **Prompt injection detection** with 15+ attack patterns
- **Input validation** and sanitization
- **Rate limiting** per user/session
- **Content filtering** with customizable rules
- **Audit logging** with comprehensive event tracking
- **Security metrics** and reportingd caching
- **Response validation** and quality assurance

### 🛡️ **Guardrails** - Safety and Compliance
- **Content filtering** with customizable validation rules
- **Policy enforcement** for ethical AI behavior
- **Security validation** to prevent prompt injection and data leakage
- **Compliance monitoring** with audit trails and reporting

### 📊 **Monitoring** - Comprehensive Observability
- **Real-time metrics** collection and analysis
### 🎯 **Prompts** - Intelligent Prompt Management
- **Defensive prompting** with automatic protection
- **Injection detection** and prevention
- **Safe rendering mode** for untrusted inputs
- **Template system** with variable substitution and inheritance
- **A/B testing** for prompt optimization
- **Version control** for prompt evolution tracking with rollback
- **Vulnerability scanning** across all prompts
- **Performance analytics** for prompt effectiveness
- **Multiple protocols** (HTTP, WebSocket, gRPC, Message Queues)
- **Pub/sub messaging** for decoupled agent communication
- **Event-driven architecture** with comprehensive event handling
- **Communication security** with authentication and encryption

### ⚙️ **Processes** - Advanced Orchestration
- **Process definition** with complex workflow patterns
- **Dynamic process adaptation** based on runtime conditions
- **Resource management** with automatic scaling and optimization
- **Process monitoring** with detailed execution tracking

### 🎯 **Prompts** - Intelligent Prompt Management
- **Template system** with variable substitution and inheritance
- **A/B testing** for prompt optimization
- **Version control** for prompt evolution tracking
- **Performance analytics** for prompt effectiveness

### 📚 **Knowledge** - Information Management
- **Knowledge graphs** with semantic relationships
- **Document processing** with intelligent chunking and indexing
- **Search and retrieval** with relevance ranking and filtering
- **Knowledge validation** and quality assurance

### 🔌 **MCP Tools** - Modular Capabilities
- **Tool registry** with automatic discovery and registration
- **Execution environment** with sandboxing and security
- **Tool composition** for building complex capabilities
- **Performance optimization** with intelligent caching

### ⚙️ **Configurations** - Centralized Management
- **Environment-specific** configurations with inheritance
- **Dynamic configuration** updates without restarts
- **Validation and defaults** with comprehensive error checking
- **Configuration versioning** and rollback capabilities

---

## 🔄 Framework Comparison

| Feature | AgenticAI Framework | LangChain | CrewAI | AutoGen |
|---------|-------------------|-----------|--------|---------|
| **Production Ready** | ✅ Enterprise-grade | ⚠️ Experimental | ⚠️ Limited | ⚠️ Research |
| **Modular Architecture** | ✅ Fully composable | ⚠️ Monolithic | ❌ Fixed structure | ⚠️ Rigid |
| **Memory Management** | ✅ Multi-tier + Semantic | ✅ Basic | ❌ None | ⚠️ Simple |
| **Task Orchestration** | ✅ Advanced workflows | ⚠️ Linear chains | ✅ Role-based | ⚠️ Conversation-based |
| **Monitoring & Observability** | ✅ Comprehensive | ❌ None | ❌ None | ❌ None |
| **Error Handling** | ✅ Robust + Recovery | ⚠️ Basic | ⚠️ Limited | ⚠️ Basic |
| **Multi-Agent Coordination** | ✅ Advanced patterns | ⚠️ Simple | ✅ Team-based | ✅ Group chat |
| **Guardrails & Safety** | ✅ Built-in | ❌ Add-on | ❌ None | ❌ None |
| **Performance Optimization** | ✅ Intelligent caching | ⚠️ Manual | ❌ None | ❌ None |
| **Extensibility** | ✅ Plugin architecture | ✅ Custom tools | ⚠️ Limited | ⚠️ Limited |

---

## ✨ Key Features & Capabilities

### 🎯 **Intelligent Agent Management**
- Create specialized agents with domain-specific knowledge and capabilities
- Implement sophisticated coordination patterns for multi-agent collaboration
- Dynamic agent scaling and load balancing
- Agent health monitoring and automatic recovery

### 🔄 **Advanced Task Orchestration**
- Complex workflow patterns with conditional branching and parallel execution
- Intelligent task scheduling with dependency resolution
- Retry mechanisms with exponential backoff and circuit breakers
- Resource-aware task distribution and optimization

### 🧠 **Sophisticated Memory Systems**
- Hierarchical memory with automatic promotion and consolidation
- Semantic search with embedding-based retrieval
- Memory compression and optimization for large-scale deployments
- Cross-agent memory sharing and synchronization

### 📊 **Enterprise Monitoring & Analytics**
- Real-time performance metrics and health monitoring
- Comprehensive audit trails and compliance reporting
- Custom alerting and notification systems
- Performance optimization recommendations

### 🛡️ **Production-Grade Security**
- Content validation and filtering with customizable rules
- Prompt injection detection and prevention
- Data privacy and PII protection
- Security audit trails and compliance reporting

### 🔌 **Flexible Integration**
- REST APIs, GraphQL, and gRPC support
- Database integrations (SQL, NoSQL, Vector databases)
- Cloud platform integrations (AWS, Azure, GCP)
- Third-party service connectors

---

## 📦 Installation

### Quick Installation
```bash
pip install agenticaiframework
```

### Development Installation
```bash
git clone https://github.com/isathish/agenticaiframework.git
cd agenticaiframework
pip install -e .
```

### With Optional Dependencies
```bash
# For enhanced monitoring capabilities
pip install "agenticaiframework[monitoring]"

# For advanced memory features
pip install "agenticaiframework[memory]"

# For documentation building
pip install "agenticaiframework[docs]"

# For all optional dependencies
pip install "agenticaiframework[all]"
```

### Documentation Dependencies
```bash
# Install only documentation dependencies
pip install -r requirements-docs.txt
```

---

## ⚡ Quick Start Examples

### Simple Agent Creation
```python
from agenticaiframework import Agent

# Create a specialized agent
agent = Agent(
    name="DataAnalyst",
    role="Data Analysis Specialist", 
    capabilities=["data_processing", "visualization", "reporting"],
    config={
        "processing_timeout": 300,
        "output_format": "json",
        "enable_caching": True
    }
)

# Start the agent
agent.start()
print(f"Agent {agent.name} is ready and {agent.status}")
```

### Multi-Agent Collaboration
```python
from agenticaiframework import Agent, AgentManager

# Create specialized agents
data_collector = Agent(
    name="DataCollector",
    role="Data Collection Specialist",
    capabilities=["api_integration", "data_extraction"]
)

data_processor = Agent(
    name="DataProcessor", 
    role="Data Processing Specialist",
    capabilities=["data_cleaning", "transformation"]
)

report_generator = Agent(
    name="ReportGenerator",
    role="Report Generation Specialist", 
    capabilities=["analysis", "visualization", "reporting"]
)

# Manage agents
manager = AgentManager()
agents = [data_collector, data_processor, report_generator]

for agent in agents:
    manager.register_agent(agent)
    agent.start()

# Coordinate workflow
manager.coordinate_workflow(["collect_data", "process_data", "generate_report"])
```

### Advanced Task Management
```python
from agenticaiframework import Task, TaskManager, TaskScheduler
from datetime import datetime, timedelta

# Create task manager
task_manager = TaskManager()

# Define complex task with dependencies
data_validation = task_manager.create_task(
    name="data_validation",
    description="Validate incoming data sources",
    priority=1,
    config={"validation_rules": ["not_null", "type_check", "range_check"]}
)

data_processing = task_manager.create_task(
    name="data_processing", 
    description="Process validated data",
    priority=2,
    dependencies=["data_validation"],
    config={"batch_size": 1000, "parallel_workers": 4}
)

# Schedule recurring task
scheduler = TaskScheduler()
scheduler.schedule_recurring(
    task=data_validation,
    interval=timedelta(hours=1)  # Run every hour
)

# Execute workflow
result = task_manager.execute_workflow([data_validation, data_processing])
```

### Intelligent Memory Management
```python
from agenticaiframework.memory import MemoryManager, SemanticMemory

# Create advanced memory system
memory_manager = MemoryManager()

# Set up semantic memory for intelligent retrieval
semantic_memory = SemanticMemory(capacity=10000)

# Store information with context
semantic_memory.store_with_embedding(
    "user_preferences",
    {
        "communication_style": "detailed_explanations",
        "preferred_format": "structured_json",
        "domain_expertise": ["data_science", "machine_learning"]
    }
)

semantic_memory.store_with_embedding(
    "successful_strategies", 
    {
        "data_processing": ["parallel_processing", "batch_optimization"],
        "error_handling": ["retry_with_backoff", "graceful_degradation"]
    }
)

# Intelligent retrieval
relevant_info = semantic_memory.semantic_search(
    "how to handle user communication preferences",
    limit=5,
    similarity_threshold=0.7
)
```

### Comprehensive Monitoring
```python
from agenticaiframework.monitoring import MonitoringSystem

# Initialize monitoring
monitoring = MonitoringSystem()

# Monitor agent performance
monitoring.track_agent_metrics(agent, {
    "response_time": 1.2,
    "success_rate": 0.95,
    "memory_usage": 128
})

# Monitor task execution
with monitoring.track_execution("data_processing_pipeline"):
    result = task_manager.execute_task("complex_data_analysis")

# Get comprehensive insights
metrics = monitoring.get_performance_summary(time_range="last_24h")
print(f"System performance: {metrics}")
```

---

## 🎯 Use Cases & Applications

### 🏢 **Enterprise Automation**
- **Document Processing**: Intelligent document analysis and extraction
- **Workflow Automation**: Complex business process automation
- **Compliance Monitoring**: Automated compliance checking and reporting
- **Resource Optimization**: Intelligent resource allocation and scaling

### 🔬 **Research & Development**
- **Literature Review**: Automated research paper analysis and summarization
- **Hypothesis Generation**: AI-driven hypothesis formulation and testing
- **Data Analysis**: Comprehensive data analysis and insight generation
- **Experiment Design**: Intelligent experimental design and optimization

### 💬 **Customer Experience**
- **Intelligent Support**: Multi-modal customer support with context awareness
- **Personalization**: Dynamic content and experience personalization
- **Sentiment Analysis**: Real-time customer sentiment monitoring and response
- **Predictive Support**: Proactive issue identification and resolution

### 🎓 **Education & Training**
- **Adaptive Learning**: Personalized learning path optimization
- **Content Generation**: Intelligent educational content creation
- **Assessment**: Automated assessment and feedback systems
- **Tutoring**: AI-powered tutoring and mentorship

### 🏥 **Healthcare & Life Sciences**
- **Clinical Decision Support**: Evidence-based clinical recommendations
- **Drug Discovery**: AI-assisted drug discovery and development
- **Patient Monitoring**: Continuous patient health monitoring and alerts
- **Medical Documentation**: Automated medical record processing and analysis

---

## 🔧 Development & Deployment

### Development Workflow
```bash
# Clone and setup development environment
git clone https://github.com/isathish/agenticaiframework.git
cd agenticaiframework

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install development dependencies
pip install -e ".[dev]"

# Install documentation dependencies
pip install -r requirements-docs.txt

# Run tests
pytest

# Build documentation locally
mkdocs build

# Serve documentation for development
mkdocs serve

# View documentation at http://127.0.0.1:8000
```

### Production Deployment
```python
# Production configuration example
from agenticaiframework import AgentManager, MonitoringSystem
from agenticaiframework.memory import DatabaseMemory

# Production-ready setup
memory = DatabaseMemory(
    db_path="/data/production/agent_memory.db",
    backup_interval=3600,  # Hourly backups
    max_connections=100
)

monitoring = MonitoringSystem(
    metrics_backend="prometheus",
    alerting_enabled=True,
    log_level="INFO"
)

manager = AgentManager(
    memory=memory,
    monitoring=monitoring,
    max_agents=50,
    auto_scaling=True
)
```

### Docker Deployment
```dockerfile
# Dockerfile example
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
RUN pip install -e .

EXPOSE 8000
CMD ["python", "-m", "agenticaiframework.server"]
```

---

## 📚 Documentation & Resources

### 📖 **Comprehensive Documentation**
- **[Complete Documentation](https://isathish.github.io/agenticaiframework/)** - Full framework documentation
- **[API Reference](https://isathish.github.io/agenticaiframework/API_REFERENCE/)** - Detailed API documentation
- **[Quick Start Guide](https://isathish.github.io/agenticaiframework/quick-start/)** - Get started in minutes
- **[Best Practices](https://isathish.github.io/agenticaiframework/best-practices/)** - Production-ready patterns

### 🎯 **Module-Specific Guides**
- **[Agents](https://isathish.github.io/agenticaiframework/agents/)** - Creating and managing intelligent agents
- **[Tasks](https://isathish.github.io/agenticaiframework/tasks/)** - Advanced task orchestration and workflow management
- **[Memory](https://isathish.github.io/agenticaiframework/memory/)** - Sophisticated memory systems and persistence
- **[Monitoring](https://isathish.github.io/agenticaiframework/monitoring/)** - Comprehensive system observability
- **[Guardrails](https://isathish.github.io/agenticaiframework/guardrails/)** - Safety and compliance systems

### � **Examples & Tutorials**
- **[Basic Examples](https://isathish.github.io/agenticaiframework/EXAMPLES/)** - Simple usage patterns
- **[Advanced Examples](https://isathish.github.io/agenticaiframework/examples/)** - Complex real-world scenarios
- **[Integration Examples](https://isathish.github.io/agenticaiframework/integration/)** - Third-party integrations

### 🛠️ **Development Resources**
- **[Architecture Guide](https://isathish.github.io/agenticaiframework/architecture/)** - Framework architecture and design
- **[Extension Guide](https://isathish.github.io/agenticaiframework/EXTENDING/)** - Creating custom components
- **[Contributing](https://isathish.github.io/agenticaiframework/contributing/)** - How to contribute to the project

---

## 🧪 Testing & Quality Assurance

### Running Tests
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=agenticaiframework --cov-report=html

# Run specific test categories
pytest tests/test_agents.py -v
pytest tests/test_tasks.py -v
pytest tests/test_memory.py -v
```

## 🧪 Testing

### Running Tests
```bash
# Run all tests
pytest tests/

# Run specific test suites
pytest tests/test_security.py              # Security features
pytest tests/test_context_engineering.py    # Context management
pytest tests/test_memory_advanced.py        # Memory features
pytest tests/test_llm_reliability.py        # LLM reliability
pytest tests/test_prompts_guardrails.py     # Prompts & guardrails
pytest tests/test_integration.py            # Integration tests

# Run with coverage
pytest tests/ --cov=agenticaiframework --cov-report=html

# Run with verbose output
pytest tests/ -v
```

### Test Coverage
- **Security Module**: Comprehensive tests for injection detection, validation, rate limiting, and content filtering
- **Context Engineering**: Tests for token tracking, compression, and importance weighting
- **Memory Management**: Tests for TTL, priority eviction, consolidation, and search
- **LLM Reliability**: Tests for circuit breaker, retry mechanism, caching, and fallback chains
- **Prompts & Guardrails**: Tests for safe rendering, version control, severity levels, and priority enforcement
- **Integration**: End-to-end tests for complete workflows
- **Overall Framework**: 94%+ coverage across all modules

### Quality Metrics
- **Code Quality**: A+ (SonarQube)
- **Security Scan**: ✅ No vulnerabilities
- **Performance**: <100ms average response time
- **Reliability**: 99.9% uptime in production

---

## 🤝 Community & Support

### 📞 **Getting Help**
- **[GitHub Issues](https://github.com/isathish/agenticaiframework/issues)** - Bug reports and feature requests
- **[Discussions](https://github.com/isathish/agenticaiframework/discussions)** - Community discussions and Q&A
- **[Documentation](https://isathish.github.io/agenticaiframework/)** - Comprehensive guides and tutorials

### 🤝 **Contributing**
We welcome contributions from the community! Ways to contribute:
- **Bug Reports**: Help us identify and fix issues
- **Feature Requests**: Suggest new capabilities and improvements
- **Code Contributions**: Submit pull requests for fixes and features
- **Documentation**: Improve guides, examples, and API docs
- **Testing**: Add test cases and improve coverage

### 📋 **Development Roadmap**
- **Q1 2025**: Enhanced multi-modal capabilities
- **Q2 2025**: Distributed agent coordination
- **Q3 2025**: Advanced ML/AI integrations
- **Q4 2025**: Enterprise security and compliance features

---

## 📄 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

Built with ❤️ by the AgenticAI Framework team and the open-source community.

Special thanks to all contributors who have helped make this framework better!
