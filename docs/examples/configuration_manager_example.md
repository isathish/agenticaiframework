---
title: Configuration Manager Example
description: Set, update, and retrieve configurations with ConfigurationManager
tags:
  - examples
  - configuration
  - settings
---

# ⚙️ Configuration Manager Example

!!! tip "Enterprise Configuration"
    Part of **380+ modules** supporting multi-environment configs, feature flags, and secrets management. See [Configuration Reference](../configuration-reference.md).

```python
from agenticaiframework.configurations import ConfigurationManager

# Example: Using the ConfigurationManager
# ----------------------------------------
# This example demonstrates how to:
# 1. Create a ConfigurationManager
# 2. Set, update, retrieve, and remove configurations
#
# Expected Output:
# - Display of configuration changes and retrieval results

if __name__ == "__main__":
    # Create a configuration manager
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
