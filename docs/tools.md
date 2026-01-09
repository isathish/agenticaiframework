---
tags:
  - tools
  - automation
  - integration
  - file-operations
  - web-scraping
  - database
  - ai-ml
---

# 🛠️ Tools Framework

<div class="annotate" markdown>

**Comprehensive collection of 35+ tools for AI agents**

Extend agent capabilities with file operations, web scraping, database access, and AI/ML tools

</div>

## 🎯 Quick Navigation

<div class="grid cards" markdown>

-   :material-file:{ .lg } **File & Document**
    
    Read, write, and process documents
    
    [:octicons-arrow-right-24: Learn More](#file-document-tools)

-   :material-web:{ .lg } **Web Scraping**
    
    Extract data from websites
    
    [:octicons-arrow-right-24: Explore](#web-scraping-tools)

-   :material-database:{ .lg } **Database**
    
    SQL, NoSQL, and vector search
    
    [:octicons-arrow-right-24: Connect](#database-tools)

-   :material-robot:{ .lg } **AI/ML**
    
    Vision, generation, and RAG
    
    [:octicons-arrow-right-24: Integrate](#aiml-tools)

</div>

## 📊 Overview

!!! abstract "Tools Framework"
    
    The Tools Framework provides a unified interface for agent interactions with external systems, files, databases, and AI services. All tools follow a consistent pattern with validation, error handling, and result formatting.

### Architecture

```mermaid
graph TB
    subgraph "Agent Layer"
        A[Agent]
        ATM[AgentToolManager]
    end
    
    subgraph "Tools Framework"
        REG[ToolRegistry]
        EXE[ToolExecutor]
        BASE[BaseTool / AsyncBaseTool]
    end
    
    subgraph "Tool Categories"
        FILE[File & Document<br/>📄 13 tools]
        WEB[Web Scraping<br/>🌐 13 tools]
        DB[Database<br/>📦 8 tools]
        AI[AI/ML<br/>🤖 7 tools]
    end
    
    A --> ATM
    ATM --> REG
    REG --> EXE
    EXE --> BASE
    BASE --> FILE & WEB & DB & AI
    
    style REG fill:#e3f2fd,stroke:#1976d2
    style EXE fill:#f3e5f5,stroke:#7b1fa2
```

## 🏗️ Core Components

### BaseTool

All tools inherit from `BaseTool` (sync) or `AsyncBaseTool` (async):

```python
from agenticaiframework.tools import BaseTool, ToolResult, ToolConfig

class MyCustomTool(BaseTool):
    """Custom tool implementation."""
    
    name = "my_custom_tool"
    description = "Performs custom operations"
    
    def __init__(self, config: ToolConfig = None):
        super().__init__(config)
    
    def _run(self, input_data: str) -> ToolResult:
        """Execute the tool."""
        result = self.process(input_data)
        return ToolResult(
            success=True,
            data=result,
            message="Operation completed"
        )
    
    def process(self, data: str) -> dict:
        # Your custom logic here
        return {"processed": data}
```

### ToolRegistry

Centralized tool management and discovery:

```python
from agenticaiframework.tools import (
    ToolRegistry, 
    tool_registry,
    register_tool,
    ToolCategory
)

# Register a tool
@register_tool(category=ToolCategory.CUSTOM)
class DataProcessorTool(BaseTool):
    name = "data_processor"
    description = "Processes data"
    
    def _run(self, data: str) -> ToolResult:
        return ToolResult(success=True, data={"processed": data})

# Get all registered tools
all_tools = tool_registry.list_tools()

# Get tools by category
file_tools = tool_registry.get_by_category(ToolCategory.FILE_DOCUMENT)

# Get a specific tool
tool = tool_registry.get_tool("data_processor")
```

### ToolExecutor

Execute tools with context and validation:

```python
from agenticaiframework.tools import (
    ToolExecutor,
    tool_executor,
    ExecutionContext,
    ExecutionPlan
)

# Create execution context
context = ExecutionContext(
    agent_id="agent-001",
    session_id="session-123",
    metadata={"user": "admin"}
)

# Execute a single tool
result = tool_executor.execute(
    tool_name="file_read",
    inputs={"path": "/data/config.json"},
    context=context
)

# Execute multiple tools in sequence
plan = ExecutionPlan(
    tools=["file_read", "json_parse", "validate_schema"],
    inputs_chain=True
)
results = tool_executor.execute_plan(plan, context)
```

### AgentToolManager

Bind tools to agents:

```python
from agenticaiframework.tools import (
    AgentToolManager,
    agent_tool_manager,
    AgentToolBinding
)

# Bind tools to an agent
agent_tool_manager.bind_tools(
    agent_id="data-analyst",
    tool_names=["file_read", "csv_rag_search", "mysql_search"]
)

# Get agent's available tools
tools = agent_tool_manager.get_agent_tools("data-analyst")

# Check if agent can use a tool
can_use = agent_tool_manager.can_use_tool("data-analyst", "file_write")
```

---

## 📄 File & Document Tools

### FileReadTool

Read file contents:

```python
from agenticaiframework.tools import FileReadTool

tool = FileReadTool()
result = tool.run(path="/data/document.txt")
print(result.data)  # File contents
```

### FileWriteTool

Write content to files:

```python
from agenticaiframework.tools import FileWriteTool

tool = FileWriteTool()
result = tool.run(
    path="/output/result.txt",
    content="Analysis complete",
    mode="w"  # 'w' for write, 'a' for append
)
```

### DirectoryReadTool

List directory contents:

```python
from agenticaiframework.tools import DirectoryReadTool

tool = DirectoryReadTool()
result = tool.run(
    path="/data",
    pattern="*.json",
    recursive=True
)
print(result.data)  # List of matching files
```

### OCRTool

Extract text from images:

```python
from agenticaiframework.tools import OCRTool

tool = OCRTool()
result = tool.run(
    image_path="/images/document.png",
    language="eng"
)
print(result.data)  # Extracted text
```

### PDFTextWritingTool

Create PDF documents:

```python
from agenticaiframework.tools import PDFTextWritingTool

tool = PDFTextWritingTool()
result = tool.run(
    output_path="/output/report.pdf",
    content="# Report\n\nContent here...",
    title="Monthly Report"
)
```

### RAG Search Tools

Search within documents using RAG:

```python
from agenticaiframework.tools import (
    PDFRAGSearchTool,
    DOCXRAGSearchTool,
    JSONRAGSearchTool,
    CSVRAGSearchTool
)

# PDF search
pdf_tool = PDFRAGSearchTool()
result = pdf_tool.run(
    file_path="/docs/manual.pdf",
    query="installation instructions",
    top_k=5
)

# JSON search
json_tool = JSONRAGSearchTool()
result = json_tool.run(
    file_path="/data/config.json",
    query="database settings"
)

# CSV search
csv_tool = CSVRAGSearchTool()
result = csv_tool.run(
    file_path="/data/sales.csv",
    query="top performing products"
)
```

### Complete File Tools List

| Tool | Description |
|------|-------------|
| `FileReadTool` | Read file contents |
| `FileWriteTool` | Write content to files |
| `DirectoryReadTool` | List directory contents |
| `OCRTool` | Extract text from images |
| `PDFTextWritingTool` | Create PDF documents |
| `PDFRAGSearchTool` | Search PDF documents |
| `DOCXRAGSearchTool` | Search Word documents |
| `MDXRAGSearchTool` | Search Markdown files |
| `XMLRAGSearchTool` | Search XML files |
| `TXTRAGSearchTool` | Search text files |
| `JSONRAGSearchTool` | Search JSON files |
| `CSVRAGSearchTool` | Search CSV files |
| `DirectoryRAGSearchTool` | Search across directories |

---

## 🌐 Web Scraping Tools

### ScrapeWebsiteTool

Basic website scraping:

```python
from agenticaiframework.tools import ScrapeWebsiteTool

tool = ScrapeWebsiteTool()
result = await tool.run(
    url="https://example.com",
    extract_text=True,
    extract_links=True
)
```

### ScrapeElementTool

Extract specific elements:

```python
from agenticaiframework.tools import ScrapeElementTool

tool = ScrapeElementTool()
result = tool.run(
    url="https://example.com",
    selector="div.article-content",
    attribute="text"
)
```

### SeleniumScraperTool

JavaScript-rendered pages:

```python
from agenticaiframework.tools import SeleniumScraperTool

tool = SeleniumScraperTool()
result = tool.run(
    url="https://spa-example.com",
    wait_for="div.loaded-content",
    timeout=30
)
```

### FirecrawlCrawlWebsiteTool

Crawl entire websites:

```python
from agenticaiframework.tools import FirecrawlCrawlWebsiteTool

tool = FirecrawlCrawlWebsiteTool()
result = await tool.run(
    url="https://docs.example.com",
    max_pages=100,
    include_patterns=["/api/*", "/guide/*"]
)
```

### Complete Web Scraping Tools List

| Tool | Description |
|------|-------------|
| `ScrapeWebsiteTool` | Basic async web scraping |
| `ScrapeElementTool` | Extract specific DOM elements |
| `ScrapflyScrapeWebsiteTool` | Scrapfly API integration |
| `SeleniumScraperTool` | Browser automation scraping |
| `ScrapegraphScrapeTool` | Scrapegraph AI scraping |
| `SpiderScraperTool` | Spider.cloud integration |
| `BrowserbaseWebLoaderTool` | Browserbase cloud browsers |
| `HyperbrowserLoadTool` | Hyperbrowser integration |
| `StagehandTool` | Stagehand browser automation |
| `FirecrawlCrawlWebsiteTool` | Website crawling |
| `FirecrawlScrapeWebsiteTool` | Single page scraping |
| `OxylabsScraperTool` | Oxylabs proxy scraping |
| `BrightDataTool` | Bright Data integration |

---

## 📦 Database Tools

### SQL Tools

```python
from agenticaiframework.tools import (
    MySQLRAGSearchTool,
    PostgreSQLRAGSearchTool,
    NL2SQLTool
)

# MySQL search
mysql_tool = MySQLRAGSearchTool()
result = mysql_tool.run(
    connection_string="mysql://user:pass@host/db",
    query="Find customers with orders > $1000"
)

# PostgreSQL search
pg_tool = PostgreSQLRAGSearchTool()
result = pg_tool.run(
    connection_string="postgresql://user:pass@host/db",
    query="Recent user activity"
)

# Natural Language to SQL
nl2sql = NL2SQLTool()
result = nl2sql.run(
    schema="users(id, name, email), orders(id, user_id, total)",
    natural_query="Show me top 10 customers by order value"
)
print(result.data["sql"])  # Generated SQL query
```

### Vector Search Tools

```python
from agenticaiframework.tools import (
    QdrantVectorSearchTool,
    WeaviateVectorSearchTool,
    MongoDBVectorSearchTool
)

# Qdrant vector search
qdrant = QdrantVectorSearchTool()
result = qdrant.run(
    collection="documents",
    query_vector=[0.1, 0.2, ...],
    top_k=10
)

# Weaviate search
weaviate = WeaviateVectorSearchTool()
result = weaviate.run(
    class_name="Document",
    query="semantic search query",
    limit=10
)

# MongoDB Atlas Vector Search
mongo = MongoDBVectorSearchTool()
result = mongo.run(
    collection="embeddings",
    query_text="similar documents",
    num_candidates=100
)
```

### Data Platform Tools

```python
from agenticaiframework.tools import (
    SnowflakeSearchTool,
    SingleStoreSearchTool
)

# Snowflake
snowflake = SnowflakeSearchTool()
result = snowflake.run(
    account="myaccount",
    query="SELECT * FROM sales WHERE date > '2024-01-01'"
)

# SingleStore
singlestore = SingleStoreSearchTool()
result = singlestore.run(
    connection_string="singlestore://...",
    query="Real-time analytics query"
)
```

### Complete Database Tools List

| Tool | Description |
|------|-------------|
| `MySQLRAGSearchTool` | MySQL database search |
| `PostgreSQLRAGSearchTool` | PostgreSQL search |
| `SnowflakeSearchTool` | Snowflake data warehouse |
| `NL2SQLTool` | Natural language to SQL |
| `QdrantVectorSearchTool` | Qdrant vector database |
| `WeaviateVectorSearchTool` | Weaviate vector search |
| `MongoDBVectorSearchTool` | MongoDB Atlas vector search |
| `SingleStoreSearchTool` | SingleStore database |

---

## 🤖 AI/ML Tools

### DALLETool

Generate images:

```python
from agenticaiframework.tools import DALLETool

tool = DALLETool()
result = await tool.run(
    prompt="A futuristic city with flying cars",
    size="1024x1024",
    quality="hd"
)
print(result.data["image_url"])
```

### VisionTool

Analyze images:

```python
from agenticaiframework.tools import VisionTool

tool = VisionTool()
result = tool.run(
    image_path="/images/chart.png",
    prompt="Describe this chart and extract key data points"
)
print(result.data["analysis"])
```

### RAGTool

Retrieval-Augmented Generation:

```python
from agenticaiframework.tools import RAGTool

tool = RAGTool()
result = tool.run(
    documents=["/docs/manual.pdf", "/docs/faq.md"],
    query="How do I configure authentication?",
    top_k=5
)
print(result.data["answer"])
print(result.data["sources"])
```

### CodeInterpreterTool

Execute code:

```python
from agenticaiframework.tools import CodeInterpreterTool

tool = CodeInterpreterTool()
result = tool.run(
    code="""
import pandas as pd
df = pd.read_csv('/data/sales.csv')
print(df.describe())
""",
    language="python",
    timeout=30
)
print(result.data["output"])
```

### Framework Integration Tools

```python
from agenticaiframework.tools import (
    LlamaIndexTool,
    LangChainTool,
    AIMindTool
)

# LlamaIndex integration
llama_tool = LlamaIndexTool()
result = llama_tool.run(
    index_path="/indexes/knowledge_base",
    query="What are the main features?"
)

# LangChain integration
langchain_tool = LangChainTool()
result = langchain_tool.run(
    chain_type="qa_with_sources",
    query="Explain the architecture"
)
```

### Complete AI/ML Tools List

| Tool | Description |
|------|-------------|
| `DALLETool` | DALL-E image generation |
| `VisionTool` | Image analysis and understanding |
| `AIMindTool` | AI Mind knowledge integration |
| `LlamaIndexTool` | LlamaIndex RAG integration |
| `LangChainTool` | LangChain chain execution |
| `RAGTool` | Generic RAG operations |
| `CodeInterpreterTool` | Code execution sandbox |

---

## 🔌 MCP Compatibility

Bridge legacy MCP tools to the new framework:

```python
from agenticaiframework.tools import (
    MCPToolAdapter,
    MCPBridge,
    wrap_mcp_tool,
    convert_to_mcp,
    mcp_bridge
)

# Wrap an MCP tool
from some_mcp_library import OldMCPTool

wrapped = wrap_mcp_tool(OldMCPTool())

# Convert new tool to MCP format
mcp_compatible = convert_to_mcp(MyNewTool())

# Use the bridge
mcp_bridge.register_legacy_tool(old_tool)
result = mcp_bridge.execute("old_tool_name", inputs={...})
```

---

## 📊 Tool Categories Summary

| Category | Tools | Description |
|----------|-------|-------------|
| **File & Document** | 13 | File I/O, OCR, PDF, document search |
| **Web Scraping** | 13 | HTTP scraping, browser automation, APIs |
| **Database** | 8 | SQL, NoSQL, vector search |
| **AI/ML** | 7 | Vision, generation, RAG, frameworks |
| **Total** | **41** | Comprehensive tool suite |

---

## 🎯 Best Practices

!!! tip "Tool Usage Guidelines"
    
    1. **Use the right tool** - Match tool capabilities to your task
    2. **Handle errors** - Always check `result.success` before using data
    3. **Validate inputs** - Use ToolConfig for input validation
    4. **Async when possible** - Use AsyncBaseTool for I/O operations
    5. **Register custom tools** - Use `@register_tool` for discoverability

!!! warning "Security Considerations"
    
    - Validate file paths to prevent directory traversal
    - Sanitize SQL queries to prevent injection
    - Use secure connections for database tools
    - Implement rate limiting for web scraping

---

## 📚 Related Documentation

- [MCP Tools Module](mcp_tools.md) - Model Context Protocol integration
- [Agents](agents.md) - Agent tool binding
- [Integration Patterns](integration.md) - External system integration
- [Security](security.md) - Tool security best practices
