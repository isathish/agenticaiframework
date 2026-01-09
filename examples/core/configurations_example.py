from agenticaiframework.configurations import ConfigurationManager

# Example: Using ConfigurationManager to manage component configurations
# ----------------------------------------------------------------------
# This example demonstrates how to:
# 1. Create a ConfigurationManager instance
# 2. Set configuration for a component (e.g., LLM)
# 3. Retrieve configuration
# 4. Update configuration
# 5. List configured components
# 6. Remove configuration
#
# Expected Output:
# - Confirmation of configuration set, updated, and removed
# - Retrieved configuration printed to console
# - List of configured components

if __name__ == "__main__":
    # Create a ConfigurationManager instance
    config_manager = ConfigurationManager()

    # Set configuration for LLM
    llm_config = {
        "model": "gpt-4",
        "temperature": 0.7,
        "max_tokens": 500
    }
    config_manager.set_config("LLM", llm_config)

    # Retrieve and print configuration
    retrieved_config = config_manager.get_config("LLM")
    print("Retrieved LLM Config:", retrieved_config)

    # Update configuration
    config_manager.update_config("LLM", {"temperature": 0.5})
    updated_config = config_manager.get_config("LLM")
    print("Updated LLM Config:", updated_config)

    # List configured components
    components = config_manager.list_components()
    print("Configured Components:", components)

    # Remove configuration
    config_manager.remove_config("LLM")
    print("Components after removal:", config_manager.list_components())
