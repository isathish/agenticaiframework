#!/usr/bin/env python3
"""
Example: Using Tools with Agents

Demonstrates the comprehensive tool integration:
- Tool registration and discovery
- Binding tools to agents
- Executing tools through agents
- MCP protocol compatibility
"""

import asyncio
from agenticaiframework import (
    # Core
    Agent,
    # Tool Base
    BaseTool,
    ToolConfig,
    ToolResult,
    ToolStatus,
    # Tool Registry
    ToolCategory,
    ToolMetadata,
    tool_registry,
    register_tool,
    # Tool Executor
    ExecutionContext,
    ExecutionPlan,
    tool_executor,
    # Agent Integration
    agent_tool_manager,
    AgentToolBinding,
    # MCP Compatibility
    mcp_bridge,
    convert_to_mcp,
    # Built-in Tools
    FileReadTool,
    ScrapeWebsiteTool,
    RAGTool,
)


# =============================================================================
# 1. Creating Custom Tools
# =============================================================================

@register_tool(
    category=ToolCategory.CUSTOM,
    tags=['example', 'demo'],
    version='1.0.0'
)
class CalculatorTool(BaseTool):
    """A simple calculator tool for demonstration."""
    
    def __init__(self, config: ToolConfig = None):
        super().__init__(config or ToolConfig(
            name="CalculatorTool",
            description="Performs basic arithmetic operations"
        ))
    
    def _execute(self, operation: str, a: float, b: float) -> float:
        """Execute calculation."""
        operations = {
            'add': lambda x, y: x + y,
            'subtract': lambda x, y: x - y,
            'multiply': lambda x, y: x * y,
            'divide': lambda x, y: x / y if y != 0 else float('inf'),
        }
        
        if operation not in operations:
            raise ValueError(f"Unknown operation: {operation}")
        
        return operations[operation](a, b)


@register_tool(category=ToolCategory.AI_ML, tags=['search', 'semantic'])
class SemanticSearchTool(BaseTool):
    """Semantic search across documents."""
    
    def __init__(self, config: ToolConfig = None):
        super().__init__(config or ToolConfig(
            name="SemanticSearchTool",
            description="Performs semantic search across documents"
        ))
        self._documents = []
    
    def add_document(self, doc: str):
        """Add a document to the search index."""
        self._documents.append(doc)
    
    def _execute(self, query: str, top_k: int = 5) -> list:
        """Search documents by query."""
        # Simple keyword matching for demo
        results = []
        query_terms = query.lower().split()
        
        for doc in self._documents:
            score = sum(1 for term in query_terms if term in doc.lower())
            if score > 0:
                results.append({'document': doc, 'score': score})
        
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:top_k]


# =============================================================================
# 2. Tool Registry Operations
# =============================================================================

def demonstrate_registry():
    """Demonstrate tool registry operations."""
    print("\n" + "="*60)
    print("TOOL REGISTRY DEMONSTRATION")
    print("="*60)
    
    # Register built-in tools
    tool_registry.register(FileReadTool, category=ToolCategory.FILE_DOCUMENT)
    tool_registry.register(ScrapeWebsiteTool, category=ToolCategory.WEB_SCRAPING)
    
    # List all registered tools
    print("\n📋 All Registered Tools:")
    for name in tool_registry.list_tools():
        metadata = tool_registry.get_metadata(name)
        print(f"  • {name} [{metadata.category.value}]")
    
    # List by category
    print("\n📂 Tools by Category:")
    by_category = tool_registry.list_by_category()
    for category, tools in by_category.items():
        print(f"  {category}: {len(tools)} tools")
    
    # Search tools
    print("\n🔍 Search 'search' tools:")
    search_results = tool_registry.search_tools("search")
    for name in search_results:
        print(f"  • {name}")
    
    # Get registry stats
    stats = tool_registry.get_stats()
    print(f"\n📊 Registry Stats: {stats['total_tools']} total tools")


# =============================================================================
# 3. Agent-Tool Integration
# =============================================================================

def demonstrate_agent_tools():
    """Demonstrate binding and using tools with agents."""
    print("\n" + "="*60)
    print("AGENT-TOOL INTEGRATION DEMONSTRATION")
    print("="*60)
    
    # Create an agent
    agent = Agent(
        name="ResearchAgent",
        role="Research and Analysis",
        capabilities=["search", "analyze", "calculate"],
        config={"model": "gpt-4"}
    )
    
    # Bind tools to agent
    binding = agent_tool_manager.bind_tools(
        agent,
        tool_names=["CalculatorTool", "SemanticSearchTool", "FileReadTool"],
        permissions={"file.read", "web.access"}
    )
    
    print(f"\n🤖 Agent: {agent.name}")
    print(f"   Bound tools: {list(binding.tools)}")
    
    # Discover available tools
    print("\n🔎 Discovering tools for agent:")
    available = agent_tool_manager.discover_tools(agent)
    for tool_info in available[:5]:
        bound_marker = "✓" if tool_info['bound'] else "○"
        print(f"   [{bound_marker}] {tool_info['name']}: {tool_info['description'][:50]}...")
    
    # Execute tool through agent
    print("\n⚡ Executing CalculatorTool through agent:")
    result = agent_tool_manager.execute_tool(
        agent,
        "CalculatorTool",
        operation="multiply",
        a=7,
        b=6
    )
    print(f"   Result: {result.data}")
    print(f"   Status: {result.status.value}")
    print(f"   Execution time: {result.execution_time:.4f}s")
    
    # Get usage stats
    usage = agent_tool_manager.get_usage_stats(agent.id)
    print(f"\n📈 Tool Usage: {usage}")


# =============================================================================
# 4. Tool Executor Features
# =============================================================================

def demonstrate_executor():
    """Demonstrate tool executor features."""
    print("\n" + "="*60)
    print("TOOL EXECUTOR DEMONSTRATION")
    print("="*60)
    
    # Direct tool execution
    print("\n⚡ Direct tool execution:")
    result = tool_executor.execute(
        "CalculatorTool",
        operation="add",
        a=10,
        b=20
    )
    print(f"   10 + 20 = {result.data}")
    
    # Batch execution
    print("\n📦 Batch execution (sequential):")
    plan = ExecutionPlan(
        tool_calls=[
            {'tool': 'CalculatorTool', 'params': {'operation': 'add', 'a': 5, 'b': 3}},
            {'tool': 'CalculatorTool', 'params': {'operation': 'multiply', 'a': 4, 'b': 7}},
        ],
        parallel=False,
        stop_on_error=True
    )
    
    results = tool_executor.execute_batch(plan)
    for i, r in enumerate(results):
        print(f"   Call {i+1}: {r.data}")
    
    # Parallel execution
    print("\n🚀 Parallel execution:")
    plan.parallel = True
    results = tool_executor.execute_batch(plan)
    for i, r in enumerate(results):
        print(f"   Call {i+1}: {r.data}")
    
    # Executor stats
    stats = tool_executor.get_stats()
    print(f"\n📊 Executor Stats:")
    print(f"   Total executions: {stats['total_executions']}")
    print(f"   Success rate: {stats['success_rate']:.1%}")


# =============================================================================
# 5. MCP Protocol Compatibility
# =============================================================================

def demonstrate_mcp_compatibility():
    """Demonstrate MCP protocol compatibility."""
    print("\n" + "="*60)
    print("MCP PROTOCOL COMPATIBILITY DEMONSTRATION")
    print("="*60)
    
    # Get MCP schemas for LLM function calling
    print("\n📝 MCP Tool Schemas (for LLM):")
    schemas = mcp_bridge.get_mcp_schemas()[:3]
    for schema in schemas:
        print(f"   • {schema['name']}: {schema['description'][:50]}...")
    
    # Execute using MCP format
    print("\n⚡ MCP-format execution:")
    response = mcp_bridge.execute_mcp_call(
        "CalculatorTool",
        {"operation": "subtract", "a": 100, "b": 42}
    )
    print(f"   Response: {response['content'][0]['text']}")
    print(f"   Is Error: {response['isError']}")
    
    # Convert tool to MCP adapter
    calc_tool = tool_registry.get_tool("CalculatorTool")
    if calc_tool:
        adapter = convert_to_mcp(calc_tool)
        print(f"\n🔄 MCP Adapter created:")
        print(f"   ID: {adapter.id}")
        print(f"   Name: {adapter.name}")
        print(f"   Schema: {adapter.to_mcp_schema()['name']}")


# =============================================================================
# 6. Async Operations
# =============================================================================

async def demonstrate_async_operations():
    """Demonstrate async tool operations."""
    print("\n" + "="*60)
    print("ASYNC OPERATIONS DEMONSTRATION")
    print("="*60)
    
    # Create agent
    agent = Agent(
        name="AsyncAgent",
        role="Async Operations",
        capabilities=["async"],
        config={}
    )
    
    # Bind tools
    agent_tool_manager.bind_tools(agent, ["CalculatorTool"])
    
    # Async execution through agent
    print("\n⚡ Async tool execution:")
    result = await agent_tool_manager.execute_tool_async(
        agent,
        "CalculatorTool",
        operation="divide",
        a=100,
        b=4
    )
    print(f"   100 / 4 = {result.data}")
    
    # Async batch execution
    print("\n📦 Async batch execution:")
    plan = ExecutionPlan(
        tool_calls=[
            {'tool': 'CalculatorTool', 'params': {'operation': 'add', 'a': 1, 'b': 1}},
            {'tool': 'CalculatorTool', 'params': {'operation': 'multiply', 'a': 2, 'b': 2}},
            {'tool': 'CalculatorTool', 'params': {'operation': 'subtract', 'a': 10, 'b': 3}},
        ],
        parallel=True
    )
    
    results = await tool_executor.execute_batch_async(plan)
    for i, r in enumerate(results):
        print(f"   Call {i+1}: {r.data}")


# =============================================================================
# 7. Real-World Workflow Example
# =============================================================================

def demonstrate_workflow():
    """Demonstrate a real-world multi-tool workflow."""
    print("\n" + "="*60)
    print("REAL-WORLD WORKFLOW EXAMPLE")
    print("="*60)
    
    # Create a research agent with multiple tools
    research_agent = Agent(
        name="DataResearcher",
        role="Data Research and Analysis",
        capabilities=["search", "analyze", "compute"],
        config={"model": "gpt-4", "temperature": 0.7}
    )
    
    # Bind all available tool categories
    print("\n📦 Setting up research agent...")
    
    # Bind file tools
    agent_tool_manager.bind_tools(
        research_agent,
        ["FileReadTool", "SemanticSearchTool", "CalculatorTool"],
        permissions={"file.read", "compute"}
    )
    
    # Setup semantic search with documents
    search_tool = tool_registry.get_tool("SemanticSearchTool")
    if search_tool:
        search_tool.add_document("Machine learning is a subset of AI focusing on learning from data.")
        search_tool.add_document("Deep learning uses neural networks with multiple layers.")
        search_tool.add_document("Natural language processing enables computers to understand text.")
        search_tool.add_document("Computer vision allows machines to interpret visual data.")
    
    # Workflow: Search -> Analyze -> Compute
    print("\n🔄 Executing research workflow:")
    
    # Step 1: Search for relevant documents
    print("\n   Step 1: Semantic Search")
    search_result = agent_tool_manager.execute_tool(
        research_agent,
        "SemanticSearchTool",
        query="machine learning neural networks",
        top_k=3
    )
    print(f"   Found {len(search_result.data)} relevant documents")
    for doc in search_result.data:
        print(f"      • Score {doc['score']}: {doc['document'][:50]}...")
    
    # Step 2: Compute some metrics
    print("\n   Step 2: Compute Metrics")
    compute_result = agent_tool_manager.execute_tool(
        research_agent,
        "CalculatorTool",
        operation="multiply",
        a=len(search_result.data),
        b=100  # relevance weight
    )
    print(f"   Relevance score: {compute_result.data}")
    
    # Get final stats
    print("\n📊 Workflow Statistics:")
    usage = agent_tool_manager.get_usage_stats(research_agent.id)
    print(f"   Tool usage: {usage}")
    
    exec_stats = tool_executor.get_stats()
    print(f"   Total executions: {exec_stats['total_executions']}")
    print(f"   Success rate: {exec_stats['success_rate']:.1%}")


# =============================================================================
# Main
# =============================================================================

def main():
    """Run all demonstrations."""
    print("\n" + "="*60)
    print("AGENTICAI TOOLS FRAMEWORK DEMONSTRATION")
    print("="*60)
    
    # Run demos
    demonstrate_registry()
    demonstrate_agent_tools()
    demonstrate_executor()
    demonstrate_mcp_compatibility()
    demonstrate_workflow()
    
    # Run async demos
    print("\n🔄 Running async demonstrations...")
    asyncio.run(demonstrate_async_operations())
    
    print("\n" + "="*60)
    print("✅ ALL DEMONSTRATIONS COMPLETED!")
    print("="*60)


if __name__ == "__main__":
    main()
