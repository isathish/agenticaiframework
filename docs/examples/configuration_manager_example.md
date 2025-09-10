# Configuration Manager Example

This guide provides a **step-by-step walkthrough** for using the `ConfigurationManager` class from the `agenticaiframework` package to manage component configurations.

---

## Prerequisites & Configuration

- **Installation**: Ensure `agenticaiframework` is installed and accessible in your Python environment.
- **Python Version**: Compatible with Python 3.8+.

---

## Code

```python
from agenticaiframework.configurations import ConfigurationManager

if __name__ == "__main__":
    config_manager = ConfigurationManager()

    # Set a configuration
    config_manager.set_config("Database", {"host": "localhost", "port": 5432})
    print("Config set for Database.")

    # Retrieve the configuration
    db_config = config_manager.get_config("Database")
    print("Retrieved Database Config:", db_config)

    # Update the configuration
    config_manager.update_config("Database", {"port": 3306})
    print("Updated Database Config:", config_manager.get_config("Database"))

    # List all components
    print("All Configured Components:", config_manager.list_components())

    # Remove the configuration
    config_manager.remove_config("Database")
    print("Database config removed. Components now:", config_manager.list_components())
```

---

## Step-by-Step Execution

1. **Import Required Class**  
   Import `ConfigurationManager` from `agenticaiframework.configurations`.

2. **Instantiate the Configuration Manager**  
   Create an instance to handle configuration storage and retrieval.

3. **Set a Configuration**  
   Use `set_config` to store configuration data for a component.

4. **Retrieve a Configuration**  
   Use `get_config` to fetch stored configuration data.

5. **Update a Configuration**  
   Use `update_config` to modify existing configuration values.

6. **List All Components**  
   Use `list_components` to see all components with stored configurations.

7. **Remove a Configuration**  
   Use `remove_config` to delete a component's configuration.

---

## Expected Input

No user input is required; the script uses hardcoded values for demonstration purposes.

---

## Expected Output

```
Config set for Database.
Retrieved Database Config: {'host': 'localhost', 'port': 5432}
Updated Database Config: {'host': 'localhost', 'port': 3306}
All Configured Components: ['Database']
Database config removed. Components now: []
```

---

## How to Run

Run the example from the project root:

```bash
python examples/configuration_manager_example.py
```

If installed as a package, you can also run it from anywhere:

```bash
python -m examples.configuration_manager_example
```

> **Tip:** Use `ConfigurationManager` to centralize and manage settings for different components in your application.
