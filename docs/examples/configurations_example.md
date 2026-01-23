---
tags:
  - example
  - configuration
  - setup
  - basic
---

# Configuration Management Example

This guide provides a **professional, step-by-step walkthrough** for using the `ConfigManager` in the `agenticaiframework` package to set, retrieve, and manage configuration values.  
It is intended for developers who need a centralized way to handle application settings and environment-specific parameters.

!!! tip "Enterprise Configuration"
    Part of **380+ modules** supporting multi-tenant configurations, feature flags, and environment management. See [Configuration Reference](../configuration-reference.md).


## Prerequisites & Configuration

- **Installation**: Ensure `agenticaiframework` is installed and accessible in your Python environment.
- **No additional configuration** is required for this example.
- **Python Version**: Compatible with Python 3.8+.


## Code

```python
from agenticaiframework.configurations import ConfigManager

if __name__ == "__main__":
    config = ConfigManager()

    # Set a configuration value
    config.set("api_key", "123456")

    # Retrieve the configuration value
    print("API Key:", config.get("api_key"))
```


## Step-by-Step Execution

1. **Import the Class**  
   Import `ConfigManager` from `agenticaiframework.configurations`.

2. **Instantiate the Manager**  
   Create an instance of `ConfigManager` to handle configuration storage and retrieval.

3. **Set a Configuration Value**  
   Use `set(key, value)` to store a configuration parameter.

4. **Retrieve a Configuration Value**  
   Use `get(key)` to fetch the stored value.

5. **Output the Result**  
   Print or log the retrieved configuration value.

> **Best Practice:** Store sensitive configuration values (e.g., API keys) in environment variables or secure vaults, and load them into `ConfigManager` at runtime.


## Expected Input

No user input is required; the script uses hardcoded values for demonstration purposes. In production, configuration values could be loaded from environment variables, configuration files, or remote configuration services.


## Expected Output

```
API Key: 123456
```


## How to Run

Run the example from the project root:

```bash
python examples/configurations_example.py
```

If installed as a package, you can also run it from anywhere:

```bash
python -m examples.configurations_example
```

> **Tip:** Use `ConfigManager` as a single source of truth for configuration values to avoid inconsistencies across your application.
