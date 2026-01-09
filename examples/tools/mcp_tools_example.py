from agenticaiframework.mcp_tools import MCPToolManager, MCPTool

# Example: Using MCPToolManager to register and execute tools
# -----------------------------------------------------------
# This example demonstrates how to:
# 1. Create an MCPToolManager instance
# 2. Register a simulated MCP tool
# 3. List available tools
# 4. Execute a tool with arguments
#
# Expected Output:
# - Confirmation of tool registration
# - List of registered tools
# - Execution result of the tool

if __name__ == "__main__":
    # Create MCPToolManager instance
    mcp_manager = MCPToolManager()

    # Register a simulated tool
    def greet_tool(name: str) -> str:
        return f"Hello, {name}! Welcome to MCP Tools."

    greet_mcp_tool = MCPTool(name="greet", capability="greeting", execute_fn=greet_tool)
    mcp_manager.register_tool(greet_mcp_tool)

    # List available tools
    tools = mcp_manager.list_tools()
    print("Available Tools:", [tool.name for tool in tools])

    # Execute the tool
    result = mcp_manager.execute_tool(greet_mcp_tool.id, name="Alice")
    print("Tool Execution Result:", result)
