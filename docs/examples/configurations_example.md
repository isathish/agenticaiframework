# Configurations Example

This example demonstrates how to use the `ConfigManager` in the `agenticaiframework` package to set and retrieve configuration values.

---

## Configuration
No special configuration is required. Ensure `agenticaiframework` is installed and accessible in your Python environment.

---

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

---

## Step-by-Step Execution

1. **Import** `ConfigManager` from `agenticaiframework.configurations`.
2. **Instantiate** the configuration manager.
3. **Set** a configuration value using `set(key, value)`.
4. **Retrieve** the configuration value using `get(key)`.
5. **Print** the retrieved value.

---

## Expected Input
No user input is required; the script uses hardcoded values for demonstration.

---

## Expected Output

```
API Key: 123456
```

---

## How to Run

```bash
python examples/configurations_example.py
