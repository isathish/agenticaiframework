---
title: MCP Tools Example
description: Create, register, and execute MCP tools with MCPToolManager
tags:
  - example
  - mcp-tools
  - integration
  - tutorial
---

# 🔧 MCP Tools Integration Example

This guide provides a **professional, step-by-step walkthrough** for creating, registering, and executing a custom MCP (Model Context Protocol) tool using the `MCPToolManager` and `MCPTool` classes from the `agenticaiframework` package.  
It is intended for developers who want to extend their agent's capabilities with modular, reusable tools.

!!! tip "35+ Built-in Tools"
    Part of **380+ modules** with 35+ built-in tools and 18 external connectors. See [MCP Tools Documentation](../mcp_tools.md).


## Prerequisites & Configuration

- **Installation**: Ensure `agenticaiframework` is installed and accessible in your Python environment.
- **No additional configuration** is required for this example.
- **Python Version**: Compatible with Python 3.8+.


## Code

```python
from agenticaiframework.mcp_tools import MCPToolManager, MCPTool

def greet_tool(name: str) -> str:
    return f"Hello, {name}! Welcome to MCP Tools."

if __name__ == "__main__":
    mcp_manager = MCPToolManager()

    # Create and register the MCP tool
    greet_mcp_tool = MCPTool(name="greet", capability="greeting", execute_fn=greet_tool)
    mcp_manager.register_tool(greet_mcp_tool)

    # List available tools
    print("Available Tools:", [tool.name for tool in mcp_manager.tools])

    # Execute the tool
    result = mcp_manager.execute_tool("greet", "Alice")
    print("Tool Execution Result:", result)
```


## Step-by-Step Execution

1. **Import Required Classes**  
   Import `MCPToolManager` and `MCPTool` from `agenticaiframework.mcp_tools`.

2. **Define the Tool Function**  
   Create a Python function (e.g., `greet_tool`) that implements the tool's logic.

3. **Instantiate the Tool Manager**  
   Create an instance of `MCPToolManager` to manage tool registration and execution.

4. **Create the MCP Tool Object**  
   Instantiate `MCPTool` with:
   - `name`: Unique identifier for the tool.
   - `capability`: A short description of what the tool does.
   - `execute_fn`: The function to execute when the tool is called.

5. **Register the Tool**  
   Use `register_tool` to make the tool available for execution.

6. **List Available Tools**  
   Access the `tools` list to verify registration.

7. **Execute the Tool**  
   Call `execute_tool` with the tool name and required arguments.

> **Best Practice:** Keep tool functions small and focused on a single responsibility for better maintainability.


## Expected Input

No user input is required; the script uses hardcoded values for demonstration purposes. In production, arguments could be dynamically generated from user input, API responses, or other runtime data.


## Expected Output

```
[YYYY-MM-DD HH:MM:SS] [MCPToolManager] Registered MCP tool 'greet' with ID <UUID>
Available Tools: ['greet']
[YYYY-MM-DD HH:MM:SS] [MCPToolManager] Executing MCP tool 'greet'
Tool Execution Result: Hello, Alice! Welcome to MCP Tools.
```


## How to Run

Run the example from the project root:

```bash
python examples/mcp_tools_example.py
```

If installed as a package, you can also run it from anywhere:

```bash
python -m examples.mcp_tools_example
```

> **Tip:** Use descriptive tool names and capabilities to make it easier for other developers to understand and reuse your tools.
