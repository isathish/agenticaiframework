---
tags:
  - configuration
  - setup
  - guide
---

# ⚙️ AgenticAI Configuration Guide

This document explains how to configure **AgenticAI Framework** for different environments and use cases.

---

## 1. Configuration Methods

You can configure AgenticAI in three ways:

1. **Programmatically** – Using `set_config()` from `agenticaiframework.configurations`
2. **Configuration File** – Using the `ConfigurationManager` class
3. **Environment Variables** – Setting variables before running your application

---

## 2. Common Configuration Keys

| Key | Description | Example |
| --- | ----------- | ------- |
| `llm_provider` | LLM provider to use | `"openai"` |
| `api_key` | API key for LLM provider | `"sk-xxxx"` |
| `memory_backend` | Memory storage backend | `"in_memory"` |
| `log_level` | Logging verbosity | `"INFO"` |
| `default_agent` | Default agent name | `"default_agent"` |

---

## 3. Programmatic Configuration

```python
from agenticaiframework.configurations import ConfigurationManager

config = ConfigurationManager()
config.set_config("LLM", {"provider": "openai", "model": "gpt-4"})
config.set_config("Logging", {"log_level": "INFO"})
```

---

## 4. Using Environment Variables

```bash
export OPENAI_API_KEY=your_api_key_here
export ANTHROPIC_API_KEY=your_api_key_here
export AGENTICAI_LOG_LEVEL=INFO
```

---

## 5. Default Configuration

```python
CONFIG = {
    "llm_provider": "openai",
    "api_key": "",
    "memory_backend": "in_memory",
    "log_level": "INFO",
    "default_agent": "default_agent"
}
```

---

## 6. Advanced Configuration

- **Multiple LLM Providers** – Register multiple providers and switch dynamically
- **Custom Memory Backends** – Implement custom backends for persistence
- **Logging** – Adjust `log_level` to `"DEBUG"` for detailed logs

---

## 7. Verifying Configuration

```python
from agenticaiframework.configurations import ConfigurationManager

config = ConfigurationManager()
print(config.get_config("LLM"))
```

---

## 8. Environment-Specific Configurations

Maintain separate configurations for different environments:

- `config_dev.py` for development
- `config_staging.py` for staging  
- `config_prod.py` for production

Load dynamically based on environment:

```python
import os
from agenticaiframework.configurations import ConfigurationManager

env = os.getenv("AGENTICAI_ENV", "dev")
config = ConfigurationManager()

if env == "prod":
    config.set_config("Logging", {"log_level": "WARNING"})
else:
    config.set_config("Logging", {"log_level": "DEBUG"})
```

---

## 9. Dynamic Configuration Updates

Update configuration values at runtime:

```python
from agenticaiframework.configurations import ConfigurationManager

config = ConfigurationManager()
config.set_config("Logging", {"log_level": "DEBUG"})
print(config.get_config("Logging"))
```

---

## 10. Secrets Management

For sensitive values like API keys, use a secrets manager:

- **AWS Secrets Manager**
- **HashiCorp Vault**
- **Azure Key Vault**
- **Google Secret Manager**

```python
import os

# Load from environment (recommended)
api_key = os.getenv("OPENAI_API_KEY")
```

---

## 11. Best Practices

!!! tip "Configuration Best Practices"
    - Store API keys securely (environment variables or secret managers)
    - Never commit sensitive data to version control
    - Use different configurations for dev/staging/production
    - Document all configuration keys
    - Use `.env` files for local development with `python-dotenv`

---

## 📚 Related Documentation

- [Configuration Reference](configuration-reference.md) - Complete reference for all settings
- [Deployment](deployment.md) - Production deployment configuration
- [Security](security.md) - Security configuration best practices
