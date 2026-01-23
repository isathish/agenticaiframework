---
title: MCP Tools Manager Example
description: Register and execute MCP tools with MCPToolManager for extensibility
tags:
  - examples
  - mcp
  - tools
---

# 🔧 MCP Tools Manager Example

!!! success "35+ Built-in Tools"
    Part of **380+ modules** with 35+ built-in tools and 18 external connectors. See [MCP Tools Documentation](../mcp_tools.md).

```python
from agenticaiframework.mcp_tools import MCPTool, MCPToolManager

# Example: Using the MCPTool and MCPToolManager
# ----------------------------------------------
# This example demonstrates how to:
# 1. Create MCP tools
# 2. Register them with MCPToolManager
# 3. Execute tools by name
#
# Expected Output:
# - Logs showing tool execution results

if __name__ == "__main__":
    # Create an MCP tool manager
    tool_manager = MCPToolManager()

    # Define some example tools
    def echo_tool(input_text):
        return f"Echo: {input_text}"

    def multiply_tool(a, b):
        return a * b

    # Create MCPTool objects
    tool1 = MCPTool(name="EchoTool", capability="Echo input text", execute_fn=echo_tool)
    tool2 = MCPTool(name="MultiplyTool", capability="Multiply two numbers", execute_fn=multiply_tool)

    # Register tools
    tool_manager.register_tool(tool1)
    tool_manager.register_tool(tool2)

    # Execute tools
    print("EchoTool result:", tool_manager.execute_tool("EchoTool", "Hello MCP"))
    print("MultiplyTool result:", tool_manager.execute_tool("MultiplyTool", 6, 7))

```
