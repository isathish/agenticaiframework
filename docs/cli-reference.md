# 💻 CLI Reference

<div align="center">

[![Version](https://img.shields.io/badge/version-1.2.0-blue.svg)](https://github.com/isathish/agenticaiframework)
[![CLI](https://img.shields.io/badge/CLI-Command--Line-success.svg)](https://github.com/isathish/agenticaiframework)
[![Documentation](https://img.shields.io/badge/docs-latest-blue.svg)](https://isathish.github.io/agenticaiframework/)

</div>


## 📊 Overview

Complete command-line interface (CLI) reference for AgenticAI Framework. This guide covers all CLI commands, options, and usage examples for managing agents, tasks, and configurations.


## 🚀 Installation

```bash
# Install AgenticAI with CLI tools
pip install agenticaiframework[cli]

# Verify installation
agenticai --version

# Show help
agenticai --help
```


## 📖 Global Options

Options available for all commands:

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--version` | `-v` | Show version | - |
| `--help` | `-h` | Show help message | - |
| `--config` | `-c` | Path to config file | `agenticai.yaml` |
| `--verbose` | `-V` | Enable verbose output | false |
| `--quiet` | `-q` | Suppress output | false |
| `--log-level` | `-l` | Set log level | `INFO` |
| `--output` | `-o` | Output format (json, yaml, table) | `table` |

### Usage

```bash
# Show version
agenticai --version

# Use custom config
agenticai --config /path/to/config.yaml agent list

# Enable verbose mode
agenticai --verbose agent create --name my_agent

# JSON output
agenticai --output json agent list
```

## 🤖 Agent Commands

### `agenticai agent create`

Create a new agent.

```bash
agenticai agent create \
  --name "research_agent" \
  --role "researcher" \
  --capabilities "search,analyze,summarize" \
  --model "gpt-4" \
  --max-tokens 4000
```

**Options:**

| Option | Required | Type | Description |
|--------|----------|------|-------------|
| `--name` | Yes | string | Agent name |
| `--role` | Yes | string | Agent role |
| `--capabilities` | No | list | Comma-separated capabilities |
| `--model` | No | string | LLM model to use |
| `--max-tokens` | No | int | Maximum tokens per request |
| `--temperature` | No | float | Sampling temperature (0-2) |
| `--config` | No | string | Path to agent config file |

**Example:**

```bash
# Create simple agent
agenticai agent create --name analyst --role "data_analyst"

# Create agent with config file
agenticai agent create --config agents/research_agent.yaml

# Create agent with capabilities
agenticai agent create \
  --name coder \
  --role "developer" \
  --capabilities "code_generation,code_review,testing"
```

### `agenticai agent list`

List all agents.

```bash
agenticai agent list [OPTIONS]
```

**Options:**

| Option | Type | Description |
|--------|------|-------------|
| `--status` | string | Filter by status (active, paused, stopped) |
| `--role` | string | Filter by role |
| `--format` | string | Output format (table, json, yaml) |
| `--limit` | int | Limit number of results |

**Example:**

```bash
# List all agents
agenticai agent list

# List active agents
agenticai agent list --status active

# List in JSON format
agenticai agent list --format json

# Limit results
agenticai agent list --limit 10
```

### `agenticai agent show`

Show detailed information about an agent.

```bash
agenticai agent show <agent_id> [OPTIONS]
```

**Options:**

| Option | Type | Description |
|--------|------|-------------|
| `--format` | string | Output format |
| `--show-history` | bool | Include execution history |
| `--show-stats` | bool | Include statistics |

**Example:**

```bash
# Show agent details
agenticai agent show agent_001

# Show with history
agenticai agent show agent_001 --show-history

# JSON output
agenticai agent show agent_001 --format json
```

### `agenticai agent start`

Start an agent.

```bash
agenticai agent start <agent_id>
```

**Example:**

```bash
agenticai agent start agent_001
```

### `agenticai agent stop`

Stop an agent.

```bash
agenticai agent stop <agent_id> [--force]
```

**Options:**

| Option | Type | Description |
|--------|------|-------------|
| `--force` | bool | Force stop without graceful shutdown |

**Example:**

```bash
# Graceful stop
agenticai agent stop agent_001

# Force stop
agenticai agent stop agent_001 --force
```

### `agenticai agent delete`

Delete an agent.

```bash
agenticai agent delete <agent_id> [--confirm]
```

**Options:**

| Option | Type | Description |
|--------|------|-------------|
| `--confirm` | bool | Skip confirmation prompt |

**Example:**

```bash
# Delete with confirmation
agenticai agent delete agent_001

# Delete without confirmation
agenticai agent delete agent_001 --confirm
```


### `agenticai task create`

Create and execute a task.

```bash
agenticai task create \
  --name "Data Analysis" \
  --description "Analyze sales data" \
  --agent agent_001 \
  --priority 5 \
  --timeout 60
```

**Options:**

| Option | Required | Type | Description |
|--------|----------|------|-------------|
| `--name` | Yes | string | Task name |
| `--description` | No | string | Task description |
| `--agent` | Yes | string | Agent ID to execute task |
| `--priority` | No | int | Priority (1-10) |
| `--timeout` | No | int | Timeout in seconds |
| `--input` | No | string | Input data (JSON string) |
| `--input-file` | No | string | Path to input file |

**Example:**

```bash
# Create basic task
agenticai task create \
  --name "Analysis" \
  --agent agent_001

# Create with input data
agenticai task create \
  --name "Process Data" \
  --agent agent_001 \
  --input '{"data": [1,2,3,4,5]}'

# Create from file
agenticai task create \
  --name "Batch Processing" \
  --agent agent_001 \
  --input-file data/input.json
```

### `agenticai task list`

List all tasks.

```bash
agenticai task list [OPTIONS]
```

**Options:**

| Option | Type | Description |
|--------|------|-------------|
| `--status` | string | Filter by status (pending, running, completed, failed) |
| `--agent` | string | Filter by agent ID |
| `--priority` | int | Filter by priority |
| `--limit` | int | Limit results |

**Example:**

```bash
# List all tasks
agenticai task list

# List running tasks
agenticai task list --status running

# List tasks for specific agent
agenticai task list --agent agent_001
```

### `agenticai task show`

Show task details.

```bash
agenticai task show <task_id> [OPTIONS]
```

**Options:**

| Option | Type | Description |
|--------|------|-------------|
| `--format` | string | Output format |
| `--show-output` | bool | Include task output |
| `--show-logs` | bool | Include execution logs |

**Example:**

```bash
# Show task details
agenticai task show task_001

# Show with output
agenticai task show task_001 --show-output

# Show with logs
agenticai task show task_001 --show-logs
```

### `agenticai task cancel`

Cancel a running task.

```bash
agenticai task cancel <task_id>
```

**Example:**

```bash
agenticai task cancel task_001
```

### `agenticai task retry`

Retry a failed task.

```bash
agenticai task retry <task_id>
```

**Example:**

```bash
agenticai task retry task_001
```

### `agenticai memory store`

Store data in memory.

```bash
agenticai memory store \
  --key "user_profile_123" \
  --value '{"name": "John", "email": "john@example.com"}' \
  --ttl 3600
```

**Options:**

| Option | Required | Type | Description |
|--------|----------|------|-------------|
| `--key` | Yes | string | Memory key |
| `--value` | Yes | string | Value (JSON string) |
| `--value-file` | No | string | Path to value file |
| `--ttl` | No | int | Time-to-live (seconds) |
| `--tags` | No | list | Comma-separated tags |

**Example:**

```bash
# Store simple value
agenticai memory store --key config --value '{"setting": "value"}'

# Store from file
agenticai memory store --key data --value-file data.json

# Store with TTL and tags
agenticai memory store \
  --key session_123 \
  --value '{"user": "john"}' \
  --ttl 1800 \
  --tags "session,user"
```

### `agenticai memory get`

Retrieve data from memory.

```bash
agenticai memory get <key> [OPTIONS]
```

**Options:**

| Option | Type | Description |
|--------|------|-------------|
| `--format` | string | Output format |
| `--output-file` | string | Save to file |

**Example:**

```bash
# Get value
agenticai memory get user_profile_123

# Save to file
agenticai memory get user_profile_123 --output-file profile.json
```

### `agenticai memory delete`

Delete data from memory.

```bash
agenticai memory delete <key>
```

**Example:**

```bash
agenticai memory delete user_profile_123
```

### `agenticai memory list`

List all memory entries.

```bash
agenticai memory list [OPTIONS]
```

**Options:**

| Option | Type | Description |
|--------|------|-------------|
| `--tags` | list | Filter by tags |
| `--pattern` | string | Key pattern to match |
| `--limit` | int | Limit results |

**Example:**

```bash
# List all
agenticai memory list

# Filter by tags
agenticai memory list --tags "session,active"

# Match pattern
agenticai memory list --pattern "user_*"
```

### `agenticai memory clear`

Clear all memory entries.

```bash
agenticai memory clear [--confirm]
```

**Example:**

```bash
# Clear with confirmation
agenticai memory clear

# Clear without confirmation
agenticai memory clear --confirm
```

### `agenticai llm generate`

Generate text using LLM.

```bash
agenticai llm generate \
  --prompt "Explain quantum computing" \
  --model "gpt-4" \
  --max-tokens 500 \
  --temperature 0.7
```

**Options:**

| Option | Type | Description |
|--------|------|-------------|
| `--prompt` | string | Prompt text |
| `--prompt-file` | string | Path to prompt file |
| `--model` | string | Model to use |
| `--max-tokens` | int | Maximum tokens |
| `--temperature` | float | Temperature (0-2) |
| `--stream` | bool | Stream response |

**Example:**

```bash
# Simple generation
agenticai llm generate --prompt "Write a haiku about AI"

# From file
agenticai llm generate --prompt-file prompts/analysis.txt

# With streaming
agenticai llm generate \
  --prompt "Tell a story" \
  --stream
```

### `agenticai llm models`

List available models.

```bash
agenticai llm models [--provider openai]
```

**Example:**

```bash
# List all models
agenticai llm models

# List OpenAI models
agenticai llm models --provider openai
```


Show system status.

```bash
agenticai monitor status
```

**Example output:**

```
System Status
─────────────────────────────
Status: Healthy
Agents: 15 active, 3 paused
Tasks: 45 running, 120 completed
Memory Usage: 2.4 GB / 8 GB
CPU Usage: 45%
```

### `agenticai monitor metrics`

Show detailed metrics.

```bash
agenticai monitor metrics [OPTIONS]
```

**Options:**

| Option | Type | Description |
|--------|------|-------------|
| `--interval` | int | Refresh interval (seconds) |
| `--follow` | bool | Continuous monitoring |
| `--metrics` | list | Specific metrics to show |

**Example:**

```bash
# Show metrics once
agenticai monitor metrics

# Continuous monitoring
agenticai monitor metrics --follow --interval 5

# Specific metrics
agenticai monitor metrics --metrics "cpu,memory,tasks"
```

### `agenticai monitor logs`

View application logs.

```bash
agenticai monitor logs [OPTIONS]
```

**Options:**

| Option | Type | Description |
|--------|------|-------------|
| `--follow` | bool | Follow log output |
| `--lines` | int | Number of lines to show |
| `--level` | string | Log level filter |
| `--agent` | string | Filter by agent ID |

**Example:**

```bash
# View recent logs
agenticai monitor logs --lines 100

# Follow logs
agenticai monitor logs --follow

# Filter by level
agenticai monitor logs --level ERROR --follow

# Agent-specific logs
agenticai monitor logs --agent agent_001 --follow
```

## ⚙️ Config Commands
### `agenticai config show`
Show current configuration.

```bash
agenticai config show [--section agents]
```

**Example:**

```bash
# Show all config
agenticai config show

# Show specific section
agenticai config show --section agents

# JSON output
agenticai config show --format json
```

### `agenticai config set`

Set configuration value.

```bash
agenticai config set <key> <value>
```

**Example:**

```bash
# Set value
agenticai config set agents.max_agents 100

# Set nested value
agenticai config set llm.default_model gpt-4-turbo
```

### `agenticai config get`

Get configuration value.

```bash
agenticai config get <key>
```

**Example:**

```bash
# Get value
agenticai config get agents.max_agents

# Get nested value
agenticai config get llm.default_model
```

### `agenticai config validate`

Validate configuration.

```bash
agenticai config validate [--config config.yaml]
```

**Example:**

```bash
# Validate current config
agenticai config validate

# Validate specific file
agenticai config validate --config staging-config.yaml
```



Run test suite.

```bash
agenticai test run [OPTIONS]
```

**Options:**

| Option | Type | Description |
|--------|------|-------------|
| `--module` | string | Specific module to test |
| `--coverage` | bool | Generate coverage report |
| `--verbose` | bool | Verbose output |

**Example:**

```bash
# Run all tests
agenticai test run

# Run specific module
agenticai test run --module agents

# With coverage
agenticai test run --coverage
```

### `agenticai test benchmark`

Run performance benchmarks.

```bash
agenticai test benchmark [--suite performance]
```

**Example:**

```bash
# Run all benchmarks
agenticai test benchmark

# Run specific suite
agenticai test benchmark --suite performance
```

### `agenticai init`
Initialize a new project.

```bash
agenticai init [project_name] [OPTIONS]
```

**Options:**

| Option | Type | Description |
|--------|------|-------------|
| `--template` | string | Project template (basic, advanced, custom) |
| `--with-examples` | bool | Include example code |

**Example:**

```bash
# Initialize project
agenticai init my_project

# With template
agenticai init my_project --template advanced

# With examples
agenticai init my_project --with-examples
```

### `agenticai doctor`

Diagnose system issues.

```bash
agenticai doctor
```

**Example output:**

```
Running diagnostics...

✓ Python version: 3.11.5
✓ Dependencies: All installed
✓ Configuration: Valid
✓ API keys: Configured
✗ Redis connection: Failed (Connection refused)
⚠ Disk space: Low (15% remaining)

2 issues found, 4 checks passed
```

### `agenticai version`

Show version information.

```bash
agenticai version [--full]
```

**Example:**

```bash
# Short version
agenticai version

# Full version info
agenticai version --full
```



```bash
# 1. Initialize project
agenticai init my_agent_app --with-examples

# 2. Create agent
agenticai agent create \
  --name research_agent \
  --role researcher \
  --model gpt-4

# 3. Create and run task
agenticai task create \
  --name "Research AI trends" \
  --agent research_agent \
  --input '{"topic": "artificial intelligence", "year": 2024}'

# 4. Monitor execution
agenticai monitor logs --follow --agent research_agent

# 5. Check results
agenticai task show task_001 --show-output

# 6. View metrics
agenticai monitor metrics

# 7. Stop agent
agenticai agent stop research_agent
```

### Batch Operations

```bash
# Create multiple agents
for i in {1..5}; do
  agenticai agent create --name "agent_$i" --role worker
done

# List all agents
agenticai agent list --format json | jq '.[] | .id'

# Stop all agents
agenticai agent list --format json | jq -r '.[] | .id' | xargs -I {} agenticai agent stop {}
```


## 🔗 Shell Completion
```bash
# Bash
agenticai --install-completion bash
source ~/.bashrc

# Zsh
agenticai --install-completion zsh
source ~/.zshrc

# Fish
agenticai --install-completion fish
```

## 📚 Related Documentation

- [Examples](EXAMPLES.md) - Code examples



**[⬆ Back to Top](#-cli-reference)**
