# MCP Tools Example

This example demonstrates how to create, register, and execute a custom MCP tool using the `MCPToolManager` and `MCPTool` classes from the `agenticaiframework` package.

---

## Configuration
No special configuration is required. Ensure `agenticaiframework` is installed and accessible in your Python environment.

---

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

---

## Step-by-Step Execution

1. **Import** `MCPToolManager` and `MCPTool` from `agenticaiframework.mcp_tools`.
2. **Define** a function (`greet_tool`) that implements the tool's functionality.
3. **Instantiate** the `MCPToolManager`.
4. **Create** an `MCPTool` object with a name, capability, and execution function.
5. **Register** the tool with the manager using `register_tool`.
6. **List** all registered tools.
7. **Execute** the tool by name with the required arguments.

---

## Expected Input
No user input is required; the script uses hardcoded values for demonstration.

---

## Expected Output

```
[YYYY-MM-DD HH:MM:SS] [MCPToolManager] Registered MCP tool 'greet' with ID <UUID>
Available Tools: ['greet']
[YYYY-MM-DD HH:MM:SS] [MCPToolManager] Executing MCP tool 'greet'
Tool Execution Result: Hello, Alice! Welcome to MCP Tools.
```

---

## How to Run

```bash
python examples/mcp_tools_example.py
