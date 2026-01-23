# AgenticAI Framework Examples

Organized examples demonstrating the framework's capabilities.

> **380+ Modules** | **237 Enterprise Features** | **35+ Built-in Tools** | **12-Tier Evaluation**

## 📁 Directory Structure

```
examples/
├── agents/          # Agent creation, lifecycle, and management
├── core/            # Prompts, tasks, processes, configurations
├── memory/          # Memory, knowledge, context engineering
├── guardrails/      # Input/output validation and safety
├── llm/             # LLM management, reliability, routing
├── evaluation/      # Model and agent evaluation
├── security/        # Security features, prompt injection protection
├── tools/           # Tool integration, MCP compatibility
└── integration/     # Enterprise features, monitoring, workflows
```

## 🚀 Running Examples

Run any example from the project root:

```bash
# Activate virtual environment
source .venv/bin/activate

# Run an example
python examples/<category>/<example>.py
```

## 📚 Categories

### Agents (`agents/`)
- `agents_example.py` - Basic agent creation and lifecycle
- `agent_manager_example.py` - Managing multiple agents
- `research_agent.py` - Research agent implementation
- `customer_support_bot.py` - Customer support bot

### Core (`core/`)
- `prompts_example.py` - Prompt templates and rendering
- `prompt_manager_example.py` - Prompt management
- `tasks_example.py` - Task creation and execution
- `task_manager_example.py` - Task orchestration
- `processes_example.py` - Process workflows
- `process_advanced_example.py` - Advanced process patterns
- `configurations_example.py` - Configuration management
- `configuration_manager_example.py` - Config manager usage
- `hub_example.py` - Hub for component sharing

### Memory (`memory/`)
- `memory_example.py` - Basic memory operations
- `memory_manager_example.py` - Memory management
- `memory_advanced_example.py` - Advanced memory patterns
- `knowledge_example.py` - Knowledge retrieval
- `knowledge_retrieval.py` - RAG implementation
- `context_engineering_example.py` - Context window management

### Guardrails (`guardrails/`)
- `guardrails_example.py` - Input/output validation
- `guardrail_manager_example.py` - Guardrail orchestration

### LLM (`llm/`)
- `llms_example.py` - LLM basics
- `llm_manager_example.py` - LLM management
- `llm_reliability_example.py` - Circuit breakers, retries, fallbacks

### Evaluation (`evaluation/`)
- `evaluation_example.py` - Model and agent evaluation

### Security (`security/`)
- `security_example.py` - Security features overview
- `prompt_injection_protection_example.py` - Injection protection

### Tools (`tools/`)
- `mcp_tools_example.py` - MCP tool basics
- `mcp_tools_manager_example.py` - MCP tool management
- `agent_tools_example.py` - **Complete tool framework demo**
  - Tool registration and discovery
  - Agent-tool binding
  - Sequential and parallel execution
  - MCP protocol compatibility

### Integration (`integration/`)
- `monitoring_example.py` - Basic monitoring
- `monitoring_system_example.py` - Full monitoring system
- `communication_example.py` - Agent communication
- `code_generation_pipeline.py` - Code generation workflow
- `enterprise_features_example.py` - Enterprise features
- `comprehensive_integration_example.py` - Full integration demo

## 💡 Recommended Starting Points

1. **New to the framework?** Start with `agents/agents_example.py`
2. **Want to use tools?** Check `tools/agent_tools_example.py`
3. **Building an enterprise app?** See `integration/enterprise_features_example.py`
4. **Need security?** Look at `security/prompt_injection_protection_example.py`
