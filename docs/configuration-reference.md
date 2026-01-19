---
tags:
  - configuration
  - reference
  - settings
  - setup
---

# ⚙️ Configuration Reference

<div align="center">

[![Version](https://img.shields.io/badge/version-1.2.11-blue.svg)](https://github.com/isathish/agenticaiframework)
[![Configuration](https://img.shields.io/badge/Configuration-Complete-success.svg)](https://github.com/isathish/agenticaiframework)
[![Documentation](https://img.shields.io/badge/docs-latest-blue.svg)](https://isathish.github.io/agenticaiframework/)

</div>


## 📊 Overview

Complete reference for all configuration options in AgenticAI Framework. This guide covers environment variables, configuration files, runtime settings, and best practices.


## 🎯 Configuration Hierarchy

```mermaid
graph TB
    subgraph "Configuration Sources (Priority Order)"
        CLI[Command Line<br/>Arguments<br/>Priority: 1]
        ENV[Environment<br/>Variables<br/>Priority: 2]
        FILE[Configuration<br/>Files<br/>Priority: 3]
        DEFAULT[Default<br/>Values<br/>Priority: 4]
    end
    
    subgraph "Configuration Manager"
        MANAGER[Configuration Manager]
        VALIDATOR[Config Validator]
        MERGER[Config Merger]
    end
    
    subgraph "Application"
        AGENTS[Agents]
        TASKS[Tasks]
        LLMS[LLMs]
        MEMORY[Memory]
    end
    
    CLI --> MANAGER
    ENV --> MANAGER
    FILE --> MANAGER
    DEFAULT --> MANAGER
    
    MANAGER --> VALIDATOR
    VALIDATOR --> MERGER
    MERGER --> AGENTS & TASKS & LLMS & MEMORY
    
    style CLI fill:#4caf50
    style MANAGER fill:#2196f3
    style AGENTS fill:#ff9800
```


## 📁 Configuration Files

### 1. Main Configuration File

**Location**: `config/agenticai.yaml` or `agenticai.yaml`

```yaml
# AgenticAI Framework Configuration
version: "1.2.11"

# Application Settings
app:
  name: "AgenticAI Application"
  environment: "production"  # development, staging, production
  debug: false
  log_level: "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL

# Agent Configuration
agents:
  max_agents: 50
  default_timeout: 30  # seconds
  enable_monitoring: true
  pool_size: 10
  warmup_agents: 5
  
# Task Configuration
tasks:
  max_queue_size: 1000
  default_priority: 5  # 1-10 scale
  retry_attempts: 3
  retry_delay: 5  # seconds
  timeout: 60  # seconds

# LLM Configuration
llm:
  default_provider: "openai"
  default_model: "gpt-4-turbo"
  max_tokens: 4000
  temperature: 0.7
  timeout: 30
  retry_attempts: 3
  
  # Provider-specific settings
  providers:
    openai:
      api_key: "${OPENAI_API_KEY}"
      organization: "${OPENAI_ORG_ID}"
      models:
        - gpt-4
        - gpt-4-turbo
        - gpt-3.5-turbo
    
    anthropic:
      api_key: "${ANTHROPIC_API_KEY}"
      models:
        - claude-3-opus
        - claude-3-sonnet
    
    azure:
      api_key: "${AZURE_OPENAI_KEY}"
      endpoint: "${AZURE_OPENAI_ENDPOINT}"
      api_version: "2024-02-01"

# Memory Configuration
memory:
  backend: "redis"  # redis, sqlite, memory, postgres
  ttl: 3600  # seconds
  max_size: 1000  # items
  
  # Redis settings
  redis:
    url: "${REDIS_URL}"
    db: 0
    pool_size: 10
  
  # PostgreSQL settings
  postgres:
    url: "${POSTGRES_URL}"
    pool_size: 20
    timeout: 30

# Knowledge Base Configuration
knowledge:
  backend: "faiss"  # faiss, pinecone, weaviate
  vector_dimension: 384
  index_type: "hnsw"
  
  # FAISS settings
  faiss:
    index_path: "data/knowledge/index.faiss"
    metric: "cosine"
  
  # Pinecone settings
  pinecone:
    api_key: "${PINECONE_API_KEY}"
    environment: "${PINECONE_ENV}"
    index_name: "agenticai"

# Monitoring Configuration
monitoring:
  enabled: true
  metrics_port: 9090
  health_check_interval: 30  # seconds
  
  # Prometheus settings
  prometheus:
    enabled: true
    port: 9090
  
  # Grafana settings
  grafana:
    enabled: false
    url: "${GRAFANA_URL}"

# Security Configuration
security:
  enable_authentication: true
  enable_authorization: true
  jwt_secret: "${JWT_SECRET}"
  jwt_expiry: 3600  # seconds
  
  # Rate limiting
  rate_limit:
    enabled: true
    requests_per_minute: 60
    burst_size: 10

# Guardrails Configuration
guardrails:
  enabled: true
  moderation_api: "openai"
  max_retries: 3
  
  # Content filters
  filters:
    - type: "toxicity"
      threshold: 0.7
    - type: "pii"
      enabled: true
    - type: "bias"
      threshold: 0.8

# Evaluation Configuration
evaluation:
  enabled: true
  metrics:
    - accuracy
    - latency
    - cost
  save_results: true
  results_path: "data/evaluation"
```

### 2. Environment-Specific Configs

```yaml
# config/development.yaml
app:
  environment: "development"
  debug: true
  log_level: "DEBUG"

llm:
  default_model: "gpt-3.5-turbo"  # Cheaper for dev
  max_tokens: 2000

monitoring:
  enabled: false

# config/production.yaml
app:
  environment: "production"
  debug: false
  log_level: "INFO"

llm:
  default_model: "gpt-4-turbo"
  max_tokens: 4000

monitoring:
  enabled: true
  
security:
  enable_authentication: true
  enable_authorization: true
```


## 🌍 Environment Variables

### Core Settings

```bash
# Application
AGENTICAI_ENV=production
AGENTICAI_DEBUG=false
AGENTICAI_LOG_LEVEL=INFO

# LLM Providers
OPENAI_API_KEY=sk-your-openai-key
OPENAI_ORG_ID=org-your-org-id
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key
AZURE_OPENAI_KEY=your-azure-key
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com

# Databases
REDIS_URL=redis://localhost:6379/0
POSTGRES_URL=postgresql://user:pass@localhost:5432/agenticai
MONGODB_URL=mongodb://localhost:27017/agenticai

# Vector Databases
PINECONE_API_KEY=your-pinecone-key
PINECONE_ENV=us-west1-gcp
WEAVIATE_URL=http://localhost:8080

# Security
JWT_SECRET=your-secret-key-here
ENCRYPTION_KEY=your-encryption-key

# Monitoring
PROMETHEUS_PORT=9090
GRAFANA_URL=http://localhost:3000

# External Services
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/xxx
GITHUB_TOKEN=ghp_your-github-token
```

### Configuration via Environment

```python
import os

# Load configuration from environment
config = {
    "app": {
        "environment": os.getenv("AGENTICAI_ENV", "development"),
        "debug": os.getenv("AGENTICAI_DEBUG", "false").lower() == "true",
        "log_level": os.getenv("AGENTICAI_LOG_LEVEL", "INFO")
    },
    "llm": {
        "openai_key": os.getenv("OPENAI_API_KEY"),
        "anthropic_key": os.getenv("ANTHROPIC_API_KEY")
    },
    "memory": {
        "redis_url": os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        "postgres_url": os.getenv("POSTGRES_URL")
    }
}
```


## 🔧 Configuration Manager API

### ConfigurationManager Class

```python
from agenticaiframework.configurations import ConfigurationManager

# Initialize with default config
config_manager = ConfigurationManager()

# Load from file
config_manager.load_from_file("config/agenticai.yaml")

# Load environment-specific config
config_manager.load_from_file(f"config/{env}.yaml")

# Set configuration
config_manager.set_config("AppSettings", {
    "max_agents": 50,
    "timeout": 30,
    "log_level": "INFO"
})

# Get configuration
settings = config_manager.get_config("AppSettings")

# Update configuration
config_manager.update_config("AppSettings", {
    "max_agents": 100
})

# Remove configuration
config_manager.remove_config("AppSettings")

# List all configurations
all_configs = config_manager.list_configs()

# Check if config exists
exists = config_manager.has_config("AppSettings")

# Get with default value
value = config_manager.get_config("Missing", default={"key": "value"})
```


## 📋 Configuration Options Reference

### Agent Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `max_agents` | int | 50 | Maximum number of concurrent agents |
| `default_timeout` | int | 30 | Default timeout for agent operations (seconds) |
| `enable_monitoring` | bool | true | Enable agent monitoring |
| `pool_size` | int | 10 | Agent pool size |
| `warmup_agents` | int | 5 | Number of agents to pre-initialize |
| `max_retries` | int | 3 | Maximum retry attempts |
| `retry_delay` | int | 5 | Delay between retries (seconds) |

### Task Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `max_queue_size` | int | 1000 | Maximum task queue size |
| `default_priority` | int | 5 | Default task priority (1-10) |
| `retry_attempts` | int | 3 | Retry attempts for failed tasks |
| `retry_delay` | int | 5 | Delay between retries (seconds) |
| `timeout` | int | 60 | Task execution timeout (seconds) |
| `enable_persistence` | bool | false | Persist tasks to database |
| `batch_size` | int | 10 | Batch processing size |

### LLM Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `default_provider` | str | openai | Default LLM provider |
| `default_model` | str | gpt-4-turbo | Default model |
| `max_tokens` | int | 4000 | Maximum token limit |
| `temperature` | float | 0.7 | Sampling temperature (0-2) |
| `top_p` | float | 1.0 | Nucleus sampling parameter |
| `frequency_penalty` | float | 0.0 | Frequency penalty (-2 to 2) |
| `presence_penalty` | float | 0.0 | Presence penalty (-2 to 2) |
| `timeout` | int | 30 | API request timeout (seconds) |
| `retry_attempts` | int | 3 | Number of retry attempts |
| `cache_enabled` | bool | true | Enable response caching |
| `stream_enabled` | bool | false | Enable streaming responses |

### Memory Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `backend` | str | redis | Storage backend (redis, sqlite, memory, postgres) |
| `ttl` | int | 3600 | Time-to-live for cached items (seconds) |
| `max_size` | int | 1000 | Maximum number of items |
| `compression` | bool | false | Enable data compression |
| `encryption` | bool | false | Enable data encryption |
| `eviction_policy` | str | lru | Eviction policy (lru, lfu, fifo) |
| `persist_to_disk` | bool | false | Persist memory to disk |

### Knowledge Base Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `backend` | str | faiss | Vector database backend |
| `vector_dimension` | int | 384 | Embedding vector dimension |
| `index_type` | str | hnsw | Index type (flat, hnsw, ivf) |
| `metric` | str | cosine | Distance metric |
| `ef_construction` | int | 200 | HNSW construction parameter |
| `m` | int | 16 | HNSW parameter M |
| `ef_search` | int | 50 | HNSW search parameter |

### Monitoring Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | bool | true | Enable monitoring |
| `metrics_port` | int | 9090 | Prometheus metrics port |
| `health_check_interval` | int | 30 | Health check interval (seconds) |
| `log_metrics` | bool | true | Log metrics to console |
| `export_metrics` | bool | true | Export metrics to Prometheus |
| `trace_sampling_rate` | float | 0.1 | Trace sampling rate (0-1) |

### Security Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enable_authentication` | bool | false | Enable authentication |
| `enable_authorization` | bool | false | Enable authorization |
| `jwt_secret` | str | - | JWT signing secret (required if auth enabled) |
| `jwt_expiry` | int | 3600 | JWT expiration time (seconds) |
| `rate_limit_enabled` | bool | true | Enable rate limiting |
| `requests_per_minute` | int | 60 | Rate limit threshold |
| `enable_encryption` | bool | false | Enable data encryption |
| `encryption_algorithm` | str | AES-256 | Encryption algorithm |

### Guardrails Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | bool | true | Enable guardrails |
| `moderation_api` | str | openai | Moderation API provider |
| `max_retries` | int | 3 | Max retries for moderation |
| `toxicity_threshold` | float | 0.7 | Toxicity detection threshold |
| `pii_detection` | bool | true | Enable PII detection |
| `bias_threshold` | float | 0.8 | Bias detection threshold |
| `custom_rules` | list | [] | Custom validation rules |

## 🎨 Configuration Examples

### Development Configuration

```python
from agenticaiframework.configurations import ConfigurationManager

config = ConfigurationManager()

# Development settings
config.set_config("development", {
    "app": {
        "debug": True,
        "log_level": "DEBUG",
        "hot_reload": True
    },
    "llm": {
        "default_model": "gpt-3.5-turbo",  # Cheaper
        "cache_enabled": True,
        "mock_responses": True  # For testing
    },
    "monitoring": {
        "enabled": False
    }
})
```

### Production Configuration

```python
config.set_config("production", {
    "app": {
        "debug": False,
        "log_level": "INFO",
        "hot_reload": False
    },
    "llm": {
        "default_model": "gpt-4-turbo",
        "cache_enabled": True,
        "retry_attempts": 5
    },
    "monitoring": {
        "enabled": True,
        "export_metrics": True
    },
    "security": {
        "enable_authentication": True,
        "enable_authorization": True,
        "rate_limit_enabled": True
    }
})
```

### High-Performance Configuration

```python
config.set_config("high_performance", {
    "agents": {
        "max_agents": 100,
        "pool_size": 50,
        "warmup_agents": 20
    },
    "tasks": {
        "batch_size": 50,
        "max_queue_size": 5000
    },
    "memory": {
        "backend": "redis",
        "ttl": 1800,
        "compression": True
    },
    "llm": {
        "cache_enabled": True,
        "stream_enabled": True,
        "parallel_requests": 10
    }
})
```


### Using Environment Variables

```bash
# .env file (never commit to git!)
OPENAI_API_KEY=sk-your-key
POSTGRES_PASSWORD=secure-password
JWT_SECRET=your-jwt-secret
```

### Using Cloud Secret Managers

```python
# AWS Secrets Manager
import boto3

def get_secret(secret_name):
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId=secret_name)
    return response['SecretString']

config.set_config("llm", {
    "api_key": get_secret("openai-api-key")
})

# Azure Key Vault
from azure.keyvault.secrets import SecretClient

def get_azure_secret(vault_url, secret_name):
    client = SecretClient(vault_url=vault_url, credential=credential)
    return client.get_secret(secret_name).value

# Google Secret Manager
from google.cloud import secretmanager

def get_gcp_secret(project_id, secret_id):
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode('UTF-8')
```


```python
from pydantic import BaseModel, Field, validator

class AgentConfig(BaseModel):
    """Agent configuration schema"""
    max_agents: int = Field(gt=0, le=1000, default=50)
    timeout: int = Field(gt=0, le=300, default=30)
    pool_size: int = Field(gt=0, le=100, default=10)
    
    @validator('pool_size')
    def pool_size_check(cls, v, values):
        if 'max_agents' in values and v > values['max_agents']:
            raise ValueError('pool_size cannot exceed max_agents')
        return v

# Validate configuration
try:
    agent_config = AgentConfig(**config.get_config("agents"))
except ValidationError as e:
    print(f"Configuration error: {e}")
```

## 📚 Related Documentation
- [Deployment](deployment.md) - Production deployment
- [Security](security.md) - Security best practices
- [Best Practices](best-practices.md) - Development guidelines

---
<div align="center">

</div>
