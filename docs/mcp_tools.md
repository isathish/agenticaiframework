# MCP Tools Module

## Overview
The `mcp_tools` module in the AgenticAI Framework provides integration with Model Context Protocol (MCP) tools, enabling AI agents to interact with external systems, APIs, and resources in a standardized way. It allows developers to extend agent capabilities by adding custom tools that can be invoked dynamically.

## Key Classes and Functions
- **MCPTool** — Base class for defining a new MCP tool.
- **ToolRegistry** — Manages registration and discovery of available tools.
- **execute_tool(name, **kwargs)** — Executes a registered tool by name.
- **list_tools()** — Returns a list of all available tools.
- **load_tools_from_config(config_path)** — Loads tool definitions from a configuration file.

## Example Usage
```python
from agenticaiframework.mcp_tools import MCPTool, ToolRegistry

# Define a custom tool
class WeatherTool(MCPTool):
    name = "get_weather"
    description = "Fetches weather information for a given city."

    def run(self, city: str):
        return f"Weather in {city}: Sunny, 25°C"

# Register the tool
registry = ToolRegistry()
registry.register(WeatherTool())

# Execute the tool
result = registry.execute_tool("get_weather", city="San Francisco")
print(result)
```

## Use Cases
- Integrating with external APIs (weather, finance, news, etc.).
- Automating system operations (file management, database queries).
- Extending AI agent capabilities with domain-specific tools.
- Enabling dynamic tool discovery and execution.

## Best Practices
- Keep tool interfaces simple and well-documented.
- Validate input parameters to prevent errors.
- Use secure authentication for tools that access sensitive data.
- Organize tools into logical categories for easier discovery.

## Related Documentation
- [Processes Module](processes.md)
- [Knowledge Module](knowledge.md)
- [Monitoring Module](monitoring.md)
