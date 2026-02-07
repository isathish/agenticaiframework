---
title: Tools
description: 35+ built-in tools for search, code execution, file operations, and more
---

# Tools

AgenticAI Framework includes **35+ production-ready tools** that extend agent capabilities. From web search to code execution, database operations to AI services.

!!! success "Enterprise Integrations"

    The framework also includes **18 enterprise integration connectors** for ServiceNow, GitHub, Slack, Salesforce, AWS, Azure, GCP, and more.

---

## Tool Categories

<div class="grid cards" markdown>

- :mag:{ .lg } **Search & Information**

    ---

    Web search, news, Wikipedia, and more

    [:octicons-arrow-right-24: Browse](#search--information)

- :computer:{ .lg } **Code & Development**

    ---

    Code execution, analysis, and debugging

    [:octicons-arrow-right-24: Browse](#code--development)

- :file_folder:{ .lg } **File & Data**

    ---

    File operations, CSV, JSON handling

    [:octicons-arrow-right-24: Browse](#file--data)

- :floppy_disk:{ .lg } **Database & Storage**

    ---

    SQL, NoSQL, vector stores

    [:octicons-arrow-right-24: Browse](#database--storage)

- :brain:{ .lg } **AI & ML**

    ---

    Embeddings, image generation, vision

    [:octicons-arrow-right-24: Browse](#ai--ml)

- :wrench:{ .lg } **Utilities**

    ---

    DateTime, encryption, email, notifications

    [:octicons-arrow-right-24: Browse](#utilities)

</div>

---

## Tool Overview

| Category | Tools | Description |
|----------|-------|-------------|
| **Search & Information** | 8 | Web search, news, Wikipedia, URL fetching |
| **Code & Development** | 6 | Python REPL, code analysis, testing |
| **File & Data** | 6 | File operations, CSV, JSON, text search |
| **Database & Storage** | 6 | SQL, MongoDB, Redis, vector stores |
| **AI & ML** | 5 | Embeddings, image gen, STT/TTS, vision |
| **Utilities** | 6 | DateTime, encryption, email, clipboard |

---

## Search & Information

### SearchTool

Web search using multiple search engines.

```python
import logging

logger = logging.getLogger(__name__)

from agenticaiframework.tools import SearchTool

# Basic usage
search = SearchTool()
results = search.run("latest AI news")

# With configuration
search = SearchTool(
    engine="google", # google, bing, duckduckgo, serper
    max_results=10,
    include_snippets=True,
    safe_search=True
)

results = search.run("machine learning tutorials")
for result in results:
    logger.info(f"Title: {result['title']}")
    logger.info(f"URL: {result['url']}")
    logger.info(f"Snippet: {result['snippet']}")
```

### NewsSearchTool

Search for recent news articles.

```python
import logging

logger = logging.getLogger(__name__)

from agenticaiframework.tools import NewsSearchTool

news = NewsSearchTool(
    sources=["reuters", "bbc", "cnn"],
    max_results=20,
    sort_by="date"
)

articles = news.run("artificial intelligence")
for article in articles:
    logger.info(f"{article['title']} - {article['source']}")
    logger.info(f"Published: {article['published_date']}")
```

### WikipediaTool

Access Wikipedia content.

```python
import logging

logger = logging.getLogger(__name__)

from agenticaiframework.tools import WikipediaTool

wiki = WikipediaTool(
    language="en",
    max_chars=5000
)

# Search Wikipedia
content = wiki.run("Quantum computing")
logger.info(content)

# Get specific sections
content = wiki.run("Quantum computing", sections=["Applications", "History"])
```

### URLFetchTool

Fetch and parse web page content.

```python
import logging

logger = logging.getLogger(__name__)

from agenticaiframework.tools import URLFetchTool

fetcher = URLFetchTool(
    extract_main_content=True,
    include_metadata=True,
    timeout=30
)

content = fetcher.run("https://example.com/article")
logger.info(f"Title: {content['title']}")
logger.info(f"Text: {content['text'][:500]}...")
```

### DNSLookupTool

DNS and network lookups.

```python
import logging

logger = logging.getLogger(__name__)

from agenticaiframework.tools import DNSLookupTool

dns = DNSLookupTool()

# Lookup domain
result = dns.run("example.com", record_type="A")
logger.info(f"IP Addresses: {result['addresses']}")

# MX records
mx_records = dns.run("example.com", record_type="MX")
```

### WeatherTool

Get weather information.

```python
import logging

logger = logging.getLogger(__name__)

from agenticaiframework.tools import WeatherTool

weather = WeatherTool(provider="openweathermap")

current = weather.run("London, UK")
logger.info(f"Temperature: {current['temperature']}°C")
logger.info(f"Conditions: {current['conditions']}")

# Forecast
forecast = weather.run("London, UK", forecast_days=5)
```

### TranslationTool

Translate text between languages.

```python
import logging

logger = logging.getLogger(__name__)

from agenticaiframework.tools import TranslationTool

translator = TranslationTool(provider="google")

translated = translator.run(
    text="Hello, how are you?",
    source_lang="en",
    target_lang="es"
)
logger.info(translated) # "Hola, ¿cómo estás?"
```

### ArxivTool

Search academic papers on arXiv.

```python
import logging

logger = logging.getLogger(__name__)

from agenticaiframework.tools import ArxivTool

arxiv = ArxivTool(max_results=10)

papers = arxiv.run("large language models")
for paper in papers:
    logger.info(f"Title: {paper['title']}")
    logger.info(f"Authors: {', '.join(paper['authors'])}")
    logger.info(f"Abstract: {paper['abstract'][:200]}...")
```

---

## Code & Development

### PythonREPLTool

Execute Python code safely.

```python
import logging

logger = logging.getLogger(__name__)

from agenticaiframework.tools import PythonREPLTool

python = PythonREPLTool(
    timeout=30,
    max_output_length=10000,
    allowed_imports=["math", "json", "datetime", "pandas", "numpy"]
)

result = python.run("""
import math
import json

data = [1, 2, 3, 4, 5]
mean = sum(data) / len(data)
std = math.sqrt(sum((x - mean) ** 2 for x in data) / len(data))

result = {"mean": mean, "std": std}
logger.info(json.dumps(result, indent=2))
""")
logger.info(result)
```

### ShellTool

Execute shell commands.

```python
import logging

logger = logging.getLogger(__name__)

from agenticaiframework.tools import ShellTool

shell = ShellTool(
    timeout=60,
    working_dir="/tmp",
    allowed_commands=["ls", "cat", "grep", "find", "wc"]
)

result = shell.run("ls -la")
logger.info(result)
```

### CodeAnalysisTool

Static code analysis.

```python
import logging

logger = logging.getLogger(__name__)

from agenticaiframework.tools import CodeAnalysisTool

analyzer = CodeAnalysisTool(
    languages=["python", "javascript"],
    checks=["security", "style", "complexity"]
)

analysis = analyzer.run(code_content, language="python")
logger.info(f"Issues found: {len(analysis['issues'])}")
for issue in analysis['issues']:
    logger.info(f" Line {issue['line']}: {issue['message']}")
```

### TestRunnerTool

Run unit tests.

```python
import logging

logger = logging.getLogger(__name__)

from agenticaiframework.tools import TestRunnerTool

runner = TestRunnerTool(
    framework="pytest",
    coverage=True
)

results = runner.run("tests/")
logger.info(f"Passed: {results['passed']}")
logger.info(f"Failed: {results['failed']}")
logger.info(f"Coverage: {results['coverage']}%")
```

### GitTool

Git operations.

```python
from agenticaiframework.tools import GitTool

git = GitTool(repo_path="/path/to/repo")

# Get status
status = git.run("status")

# Get diff
diff = git.run("diff", args=["HEAD~1"])

# Get log
log = git.run("log", args=["--oneline", "-10"])
```

### PackageManagerTool

Manage packages.

```python
import logging

logger = logging.getLogger(__name__)

from agenticaiframework.tools import PackageManagerTool

pm = PackageManagerTool(manager="pip")

# Search packages
results = pm.run("search", package="requests")

# Get package info
info = pm.run("info", package="pandas")
logger.info(f"Version: {info['version']}")
logger.info(f"Dependencies: {info['dependencies']}")
```

---

## File & Data

### FileReadTool

Read file contents.

```python
import logging

logger = logging.getLogger(__name__)

from agenticaiframework.tools import FileReadTool

reader = FileReadTool(
    allowed_extensions=[".txt", ".py", ".json", ".md", ".csv"],
    max_file_size=10_000_000 # 10MB
)

content = reader.run("/path/to/file.txt")
logger.info(content)

# Read specific lines
content = reader.run("/path/to/file.txt", start_line=10, end_line=50)
```

### FileWriteTool

Write to files.

```python
from agenticaiframework.tools import FileWriteTool

writer = FileWriteTool(
    allowed_extensions=[".txt", ".json", ".md"],
    allowed_directories=["/tmp", "/data"]
)

writer.run(
    path="/tmp/output.txt",
    content="Hello, World!",
    mode="write" # or "append"
)
```

### DirectoryTool

Directory operations.

```python
import logging

logger = logging.getLogger(__name__)

from agenticaiframework.tools import DirectoryTool

dir_tool = DirectoryTool()

# List directory
files = dir_tool.run("list", path="/data")
for f in files:
    logger.info(f"{f['name']} - {f['size']} bytes")

# Create directory
dir_tool.run("create", path="/data/new_folder")

# Search files
matches = dir_tool.run("search", path="/data", pattern="*.json")
```

### CSVTool

CSV file operations.

```python
import logging

logger = logging.getLogger(__name__)

from agenticaiframework.tools import CSVTool

csv = CSVTool()

# Read CSV
data = csv.run("read", path="/data/sales.csv")
logger.info(f"Rows: {len(data)}")
logger.info(f"Columns: {data[0].keys()}")

# Filter CSV
filtered = csv.run(
    "filter",
    path="/data/sales.csv",
    condition="amount > 1000"
)

# Aggregate
summary = csv.run(
    "aggregate",
    path="/data/sales.csv",
    group_by="region",
    aggregations={"amount": "sum", "quantity": "mean"}
)
```

### JSONTool

JSON manipulation.

```python
from agenticaiframework.tools import JSONTool

json_tool = JSONTool()

# Read JSON
data = json_tool.run("read", path="/data/config.json")

# Query with JSONPath
result = json_tool.run(
    "query",
    data=data,
    path="$.users[?(@.active==true)].name"
)

# Transform
transformed = json_tool.run(
    "transform",
    data=data,
    template={"user_names": "$.users[*].name"}
)
```

### TextSearchTool

Search text content.

```python
from agenticaiframework.tools import TextSearchTool

search = TextSearchTool()

# Search in file
matches = search.run(
    path="/data/log.txt",
    pattern="ERROR",
    context_lines=2
)

# Regex search
matches = search.run(
    path="/data/log.txt",
    pattern=r"\d{4}-\d{2}-\d{2}",
    regex=True
)
```

---

## Database & Storage

### SQLTool

SQL database operations.

```python
import logging

logger = logging.getLogger(__name__)

from agenticaiframework.tools import SQLTool

sql = SQLTool(
    connection_string="postgresql://user:pass@localhost/db"
)

# Query
results = sql.run("SELECT * FROM users WHERE active = true LIMIT 10")
for row in results:
    logger.info(row)

# With parameters (safe from SQL injection)
results = sql.run(
    "SELECT * FROM users WHERE email = :email",
    params={"email": "alice@example.com"}
)
```

### MongoDBTool

MongoDB operations.

```python
from agenticaiframework.tools import MongoDBTool

mongo = MongoDBTool(
    connection_string="mongodb://localhost:27017",
    database="mydb"
)

# Find documents
docs = mongo.run(
    "find",
    collection="users",
    query={"status": "active"},
    limit=10
)

# Aggregate
pipeline = [{"$match": {"status": "active"}},
    {"$group": {"_id": "$region", "count": {"$sum": 1}}}
]
results = mongo.run("aggregate", collection="users", pipeline=pipeline)
```

### RedisTool

Redis cache operations.

```python
from agenticaiframework.tools import RedisTool

redis = RedisTool(host="localhost", port=6379)

# Get/Set
redis.run("set", key="user:123", value={"name": "Alice"}, ttl=3600)
value = redis.run("get", key="user:123")

# List operations
redis.run("push", key="queue", value="task1")
item = redis.run("pop", key="queue")
```

### VectorStoreTool

Vector database operations.

```python
import logging

logger = logging.getLogger(__name__)

from agenticaiframework.tools import VectorStoreTool

vectors = VectorStoreTool(
    provider="chromadb",
    collection="documents"
)

# Add documents
vectors.run(
    "add",
    documents=["Document 1 content", "Document 2 content"],
    metadatas=[{"source": "file1"}, {"source": "file2"}]
)

# Search
results = vectors.run(
    "search",
    query="machine learning",
    top_k=5
)
for result in results:
    logger.info(f"Score: {result['score']:.3f} - {result['content'][:100]}...")
```

### S3Tool

AWS S3 operations.

```python
from agenticaiframework.tools import S3Tool

s3 = S3Tool(bucket="my-bucket")

# List files
files = s3.run("list", prefix="data/")

# Download
content = s3.run("download", key="data/file.json")

# Upload
s3.run("upload", key="data/output.json", content=json.dumps(data))
```

### ElasticsearchTool

Elasticsearch operations.

```python
from agenticaiframework.tools import ElasticsearchTool

es = ElasticsearchTool(hosts=["localhost:9200"])

# Search
results = es.run(
    "search",
    index="documents",
    query={
        "match": {"content": "machine learning"}
    }
)

# Full-text search with filters
results = es.run(
    "search",
    index="documents",
    query={
        "bool": {
            "must": {"match": {"content": "AI"}},
            "filter": {"term": {"category": "technology"}}
        }
    }
)
```

---

## AI & ML

### EmbeddingsTool

Generate text embeddings.

```python
import logging

logger = logging.getLogger(__name__)

from agenticaiframework.tools import EmbeddingsTool

embeddings = EmbeddingsTool(
    provider="openai",
    model="text-embedding-3-small"
)

# Single embedding
vector = embeddings.run("Hello, world!")
logger.info(f"Dimensions: {len(vector)}")

# Batch embeddings
vectors = embeddings.run(["First document",
    "Second document",
    "Third document"
])
```

### ImageGenerationTool

Generate images from text.

```python
from agenticaiframework.tools import ImageGenerationTool

image_gen = ImageGenerationTool(
    provider="openai",
    model="dall-e-3"
)

# Generate image
result = image_gen.run(
    prompt="A futuristic city with flying cars",
    size="1024x1024",
    quality="hd"
)

# Save image
with open("city.png", "wb") as f:
    f.write(result["image_data"])
```

### VisionTool

Analyze images.

```python
import logging

logger = logging.getLogger(__name__)

from agenticaiframework.tools import VisionTool

vision = VisionTool(
    provider="openai",
    model="gpt-4-vision-preview"
)

# Analyze image
analysis = vision.run(
    image_path="/path/to/image.jpg",
    prompt="Describe this image in detail"
)
logger.info(analysis)

# From URL
analysis = vision.run(
    image_url="https://example.com/image.jpg",
    prompt="What objects are in this image?"
)
```

### SpeechToTextTool

Transcribe audio.

```python
import logging

logger = logging.getLogger(__name__)

from agenticaiframework.tools import SpeechToTextTool

stt = SpeechToTextTool(
    provider="openai",
    model="whisper-1"
)

# Transcribe
transcript = stt.run("/path/to/audio.wav")
logger.info(transcript["text"])
logger.info(f"Language: {transcript['language']}")
```

### TextToSpeechTool

Generate speech from text.

```python
from agenticaiframework.tools import TextToSpeechTool

tts = TextToSpeechTool(
    provider="openai",
    voice="nova"
)

# Generate speech
audio = tts.run("Hello, how can I help you today?")

# Save audio
with open("output.mp3", "wb") as f:
    f.write(audio)
```

---

## Utilities

### DateTimeTool

Date and time operations.

```python
import logging

logger = logging.getLogger(__name__)

from agenticaiframework.tools import DateTimeTool

dt = DateTimeTool()

# Current time
now = dt.run("now", timezone="America/New_York")
logger.info(f"Current time: {now}")

# Parse date
parsed = dt.run("parse", date_string="January 15, 2024")

# Calculate difference
diff = dt.run("diff", date1="2024-01-01", date2="2024-12-31")
logger.info(f"Days between: {diff['days']}")

# Add duration
future = dt.run("add", date="2024-01-15", days=30)
```

### CalculatorTool

Mathematical calculations.

```python
import logging

logger = logging.getLogger(__name__)

from agenticaiframework.tools import CalculatorTool

calc = CalculatorTool()

# Basic math
result = calc.run("2 + 2 * 3")
logger.info(result) # 8

# Advanced math
result = calc.run("sqrt(16) + sin(pi/2)")
logger.info(result) # 5.0

# Statistics
result = calc.run("mean([1, 2, 3, 4, 5])")
logger.info(result) # 3.0
```

### EncryptionTool

Encryption and hashing.

```python
from agenticaiframework.tools import EncryptionTool

crypto = EncryptionTool()

# Hash
hash_value = crypto.run("hash", data="password123", algorithm="sha256")

# Encrypt/Decrypt
encrypted = crypto.run("encrypt", data="secret message", key=secret_key)
decrypted = crypto.run("decrypt", data=encrypted, key=secret_key)

# Generate key
key = crypto.run("generate_key", length=32)
```

### EmailTool

Send emails.

```python
from agenticaiframework.tools import EmailTool

email = EmailTool(
    smtp_host="smtp.gmail.com",
    smtp_port=587,
    username="user@gmail.com",
    password="app_password"
)

# Send email
email.run(
    to="recipient@example.com",
    subject="Hello from AgenticAI",
    body="This is a test email.",
    attachments=["/path/to/file.pdf"]
)
```

### NotificationTool

Send notifications.

```python
from agenticaiframework.tools import NotificationTool

notify = NotificationTool()

# Slack notification
notify.run(
    channel="slack",
    webhook_url="https://hooks.slack.com/...",
    message="Task completed successfully!"
)

# Discord notification
notify.run(
    channel="discord",
    webhook_url="https://discord.com/api/webhooks/...",
    message="New alert!",
    embed={"title": "Alert", "color": 0xff0000}
)
```

### ClipboardTool

System clipboard operations.

```python
from agenticaiframework.tools import ClipboardTool

clipboard = ClipboardTool()

# Copy to clipboard
clipboard.run("copy", text="Hello, World!")

# Paste from clipboard
content = clipboard.run("paste")
```

---

## Creating Custom Tools

### Using Decorator

```python
from agenticaiframework.tools import tool

@tool
def get_stock_price(ticker: str) -> dict:
    """Get current stock price for a ticker symbol.

    Args:
        ticker: Stock ticker symbol (e.g., AAPL, GOOGL)

    Returns:
        Dictionary with price information
    """
    # Your implementation
    price = fetch_stock_price(ticker)
    return {
        "ticker": ticker,
        "price": price,
        "currency": "USD"
    }
```

### Using Tool Class

```python
from agenticaiframework.tools import Tool

class WeatherTool(Tool):
    name = "weather"
    description = "Get current weather for a location"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def _run(self, location: str, units: str = "celsius") -> dict:
        """
        Args:
            location: City name or coordinates
            units: Temperature units (celsius or fahrenheit)
        """
        # Synchronous implementation
        response = requests.get(
            f"https://api.weather.com/current",
            params={"location": location, "units": units},
            headers={"Authorization": f"Bearer {self.api_key}"}
        )
        return response.json()

    async def _arun(self, location: str, units: str = "celsius") -> dict:
        """Async implementation."""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.weather.com/current",
                params={"location": location, "units": units},
                headers={"Authorization": f"Bearer {self.api_key}"}
            ) as response:
                return await response.json()
```

### Tool with Schema

```python
from agenticaiframework.tools import Tool
from pydantic import BaseModel, Field

class StockInput(BaseModel):
    ticker: str = Field(..., description="Stock ticker symbol")
    include_history: bool = Field(False, description="Include price history")
    days: int = Field(7, description="Days of history to include")

class StockTool(Tool):
    name = "stock_price"
    description = "Get stock price and optional history"
    args_schema = StockInput

    def _run(self, ticker: str, include_history: bool = False, days: int = 7):
        # Implementation
        pass
```

---

## Tool Configuration

### Global Tool Settings

```python
from agenticaiframework.tools import ToolRegistry

# Configure global settings
ToolRegistry.configure(
    default_timeout=30,
    rate_limiting=True,
    caching=True,
    cache_ttl=300
)

# Register custom tools
ToolRegistry.register(WeatherTool())
ToolRegistry.register(StockTool())
```

### Tool Permissions

```python
from agenticaiframework import Agent, AgentConfig, ToolPermissions

agent = Agent(
    config=AgentConfig(
        name="restricted_agent",
        tools=ToolRegistry.all(),
        tool_permissions=ToolPermissions(
            allowed=["search", "calculator", "file_read"],
            denied=["shell", "file_write"],
            confirmation_required=["email"],
            rate_limits={
                "search": {"calls": 10, "window": 60}
            }
        )
    )
)
```

---

## API Reference

For complete API documentation, see:

- [Tool Base Class](API_REFERENCE.md#tool)
- [ToolRegistry](API_REFERENCE.md#toolregistry)
- [Custom Tool Creation](API_REFERENCE.md#custom-tools)
