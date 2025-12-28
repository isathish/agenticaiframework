<!-- PROJECT LOGO -->
<br />
<div align="center">
  <a href="https://isathish.github.io/agenticaiframework/">
    <img src="https://img.shields.io/pypi/v/agenticaiframework?color=blue&label=PyPI%20Version&logo=python&logoColor=white" alt="PyPI Version">
  </a>
  <a href="https://pypi.org/project/agenticaiframework/">
    <img src="https://img.shields.io/pypi/dm/agenticaiframework?color=green&label=Downloads&logo=python&logoColor=white" alt="Downloads">
  </a>
  <a href="https://github.com/isathish/agenticaiframework/actions">
    <img src="https://img.shields.io/github/actions/workflow/status/isathish/agenticaiframework/python-package.yml?branch=main&label=Build&logo=github" alt="Build Status">
  </a>
  <a href="https://isathish.github.io/agenticaiframework/">
    <img src="https://img.shields.io/badge/Documentation-Online-blue?logo=readthedocs&logoColor=white" alt="Documentation">
  </a>
</div>


## 9. Environment-Specific Configurations

You can maintain separate configuration files for different environments:

- `config_dev.py` for development
- `config_staging.py` for staging
- `config_prod.py` for production

Load them dynamically based on an environment variable:

```python
import os
from agenticaiframework.configurations import set_config

env = os.getenv("AGENTICAI_ENV", "dev")
if env == "prod":
    from config_prod import CONFIG
elif env == "staging":
    from config_staging import CONFIG
else:
    from config_dev import CONFIG

for key, value in CONFIG.items():
    set_config(key, value)
```


## 10. Dynamic Configuration Updates

You can update configuration values at runtime without restarting the application:

```python
from agenticaiframework.configurations import set_config, get_config

set_config("log_level", "DEBUG")
print(get_config("log_level"))  # Output: DEBUG
```


## 11. Configuration Validation

Implement validation to ensure configuration values are correct:

```python
def validate_config():
    from agenticaiframework.configurations import get_config
    if not get_config("api_key"):
        raise ValueError("API key is missing!")
```


## 12. Secrets Management

For sensitive values like API keys, use a secrets manager:

- AWS Secrets Manager
- HashiCorp Vault
- Azure Key Vault
- Google Secret Manager

Example with AWS Secrets Manager:

```python
import boto3
import json

def get_secret(secret_name):
    client = boto3.client("secretsmanager")
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response["SecretString"])
```

## 13. Best Practices for Configuration

- Keep configuration files out of version control if they contain secrets.
- Use `.env` files for local development and load them with `python-dotenv`.
- Document all configuration keys in `CONFIGURATION.md`.
# AgenticAI Configuration Guide

This document explains how to configure **AgenticAI** for different environments and use cases.

## 1. Configuration Methods

You can configure AgenticAI in three ways:

1. **Programmatically** – Using `set_config()` from `agenticaiframework.configurations`.
2. **Configuration File** – Editing `configurations.py`.
3. **Environment Variables** – Setting variables before running your application.

## 2. Common Configuration Keys

| Key | Description | Example |
| --- | ----------- | ------- |
| `llm_provider` | LLM provider to use | `"openai"` |
| `api_key` | API key for LLM provider | `"sk-xxxx"` |
| `memory_backend` | Memory storage backend | `"in_memory"` |
| `log_level` | Logging verbosity | `"INFO"` |
| `default_agent` | Default agent name | `"default_agent"` |



```python
from agenticaiframework.configurations import set_config

set_config("llm_provider", "openai")
set_config("api_key", "your_api_key_here")
set_config("memory_backend", "in_memory")
```

## 4. Using Environment Variables
```bash
export AGENTICAI_LLM_PROVIDER=openai
export AGENTICAI_API_KEY=your_api_key_here
```




```python
CONFIG = {
    "llm_provider": "openai",
    "api_key": "",
    "memory_backend": "in_memory",
    "log_level": "INFO",
    "default_agent": "default_agent"
}
```


## 6. Advanced Configuration

- **Multiple LLM Providers** – You can register multiple providers and switch dynamically.
- **Custom Memory Backends** – Implement a new backend in `memory.py` and set it in config.
- **Logging** – Adjust `log_level` to `"DEBUG"` for detailed logs.


## 7. Verifying Configuration

```python
from agenticaiframework.configurations import get_config

print(get_config("llm_provider"))
```


## 8. Best Practices

- Store API keys securely (e.g., environment variables, secret managers).
- Avoid committing sensitive data to version control.
- Use different configurations for development, staging, and production.
