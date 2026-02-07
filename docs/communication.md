---
title: Communication Protocols
description: 6 communication protocols for connecting agents - HTTP, WebSocket, SSE, MQTT, gRPC, STDIO
---

# Communication Protocols

AgenticAI Framework supports **6 communication protocols** for connecting agents to external services, each other, and client applications.

!!! tip "Enterprise Messaging"

    The framework also includes **12 enterprise messaging & events modules** for Pub/Sub, Event Sourcing, CQRS, and Kafka integration.

---

## Protocol Overview

<div class="grid cards" markdown>

- :globe_with_meridians:{ .lg } **HTTP**

    ---

    REST API communication for standard web services

    [:octicons-arrow-right-24: Learn HTTP](#http-protocol)

- :zap:{ .lg } **WebSocket**

    ---

    Real-time bidirectional communication

    [:octicons-arrow-right-24: Learn WebSocket](#websocket-protocol)

- :satellite:{ .lg } **SSE**

    ---

    Server-Sent Events for streaming responses

    [:octicons-arrow-right-24: Learn SSE](#sse-protocol)

- :envelope:{ .lg } **MQTT**

    ---

    Lightweight IoT message queuing

    [:octicons-arrow-right-24: Learn MQTT](#mqtt-protocol)

- :rocket:{ .lg } **gRPC**

    ---

    High-performance RPC with Protocol Buffers

    [:octicons-arrow-right-24: Learn gRPC](#grpc-protocol)

- :computer:{ .lg } **STDIO**

    ---

    Standard input/output for process communication

    [:octicons-arrow-right-24: Learn STDIO](#stdio-protocol)

</div>

---

## Protocol Comparison

| Protocol | Pattern | Best For | Latency | Streaming |
|----------|---------|----------|---------|-----------|
| **HTTP** | Request-Response | REST APIs, webhooks | Medium | No |
| **WebSocket** | Bidirectional | Real-time chat, live updates | Low | Yes |
| **SSE** | Server-Push | Streaming responses, notifications | Low | Yes |
| **MQTT** | Pub-Sub | IoT, sensor data, events | Low | Yes |
| **gRPC** | RPC | Microservices, high-throughput | Very Low | Yes |
| **STDIO** | Pipes | CLI tools, local processes | Minimal | Yes |

---

## HTTP Protocol

The HTTP client provides robust REST API communication with connection pooling, retry logic, and authentication support.

### Basic Usage

```python
import logging

logger = logging.getLogger(__name__)

from agenticaiframework.communication import HTTPClient

# Simple request
async with HTTPClient() as client:
    response = await client.get("https://api.example.com/data")
    data = response.json()
    logger.info(data)
```

### Request Methods

```python
async with HTTPClient() as client:
    # GET request
    response = await client.get(
        "https://api.example.com/users",
        params={"limit": 10, "offset": 0}
    )

    # POST request with JSON body
    response = await client.post(
        "https://api.example.com/users",
        json={"name": "Alice", "email": "alice@example.com"}
    )

    # PUT request
    response = await client.put(
        "https://api.example.com/users/123",
        json={"name": "Alice Updated"}
    )

    # DELETE request
    response = await client.delete("https://api.example.com/users/123")

    # PATCH request
    response = await client.patch(
        "https://api.example.com/users/123",
        json={"status": "active"}
    )
```

### Configuration

```python
from agenticaiframework.communication import HTTPClient, HTTPConfig

config = HTTPConfig(
    # Timeouts
    timeout_seconds=30,
    connect_timeout=10,

    # Retry settings
    max_retries=3,
    retry_delay=1.0,
    retry_backoff=2.0,
    retry_on_status=[429, 500, 502, 503, 504],

    # Connection pooling
    pool_connections=10,
    pool_maxsize=100,

    # SSL/TLS
    verify_ssl=True,
    cert_path="/path/to/cert.pem"
)

client = HTTPClient(config=config)
```

### Authentication

=== "API Key"
    ```python
    client = HTTPClient(
        headers={"X-API-Key": "your-api-key"}
    )
    ```

=== "Bearer Token"
    ```python
    client = HTTPClient(
        auth={"type": "bearer", "token": "your-jwt-token"}
    )
    ```

=== "Basic Auth"
    ```python
    client = HTTPClient(
        auth={"type": "basic", "username": "user", "password": "pass"}
    )
    ```

=== "OAuth2"
    ```python
    from agenticaiframework.communication import OAuth2Auth

    auth = OAuth2Auth(
        client_id="your-client-id",
        client_secret="your-secret",
        token_url="https://auth.example.com/token"
    )

    client = HTTPClient(auth=auth)
    ```

### Response Handling

```python
import logging

logger = logging.getLogger(__name__)

async with HTTPClient() as client:
    response = await client.get("https://api.example.com/data")

    # Check status
    if response.is_success:
        data = response.json()
    elif response.status_code == 404:
        logger.info("Resource not found")
    else:
        logger.info(f"Error: {response.status_code}")

    # Access headers
    content_type = response.headers.get("content-type")

    # Get raw content
    text = response.text
    binary = response.content
```

---

## WebSocket Protocol

WebSocket provides full-duplex, real-time communication for interactive applications.

### Basic Usage

```python
import logging

logger = logging.getLogger(__name__)

from agenticaiframework.communication import WebSocketClient

async with WebSocketClient("wss://api.example.com/ws") as ws:
    # Send message
    await ws.send({"type": "subscribe", "channel": "updates"})

    # Receive messages
    async for message in ws:
        logger.info(f"Received: {message}")

        if message.get("type") == "done":
            break
```

### Configuration

```python
from agenticaiframework.communication import WebSocketClient, WebSocketConfig

config = WebSocketConfig(
    # Connection settings
    ping_interval=30,
    ping_timeout=10,
    close_timeout=5,

    # Reconnection
    auto_reconnect=True,
    reconnect_delay=1.0,
    max_reconnect_attempts=5,

    # Message handling
    max_message_size=1024 * 1024, # 1MB
    compression=True
)

ws = WebSocketClient("wss://api.example.com/ws", config=config)
```

### Event Handling

```python
import logging

logger = logging.getLogger(__name__)

from agenticaiframework.communication import WebSocketClient

ws = WebSocketClient("wss://api.example.com/ws")

@ws.on("open")
async def on_open():
    logger.info("Connection opened")
    await ws.send({"type": "hello"})

@ws.on("message")
async def on_message(data):
    logger.info(f"Received: {data}")

@ws.on("close")
async def on_close(code, reason):
    logger.info(f"Connection closed: {code} - {reason}")

@ws.on("error")
async def on_error(error):
    logger.info(f"Error: {error}")

# Start connection
await ws.connect()
```

### Chat-Style Communication

```python
import logging

logger = logging.getLogger(__name__)

async with WebSocketClient("wss://chat.example.com/ws") as ws:
    # Send chat message
    await ws.send({
        "type": "chat",
        "message": "Hello, how can you help me?",
        "user_id": "user_123"
    })

    # Receive streaming response
    response_text = ""
    async for message in ws:
        if message["type"] == "token":
            response_text += message["content"]
            print(message["content"], end="", flush=True)
        elif message["type"] == "done":
            break

    logger.info(f"\nFull response: {response_text}")
```

---

## SSE Protocol

Server-Sent Events (SSE) provides one-way streaming from server to client, perfect for AI response streaming.

### Basic Usage

```python
import logging

logger = logging.getLogger(__name__)

from agenticaiframework.communication import SSEClient

async with SSEClient("https://api.example.com/events") as sse:
    async for event in sse:
        logger.info(f"Event: {event.event}")
        logger.info(f"Data: {event.data}")
        logger.info(f"ID: {event.id}")
```

### Configuration

```python
from agenticaiframework.communication import SSEClient, SSEConfig

config = SSEConfig(
    # Connection settings
    timeout_seconds=0, # No timeout (long-lived)

    # Reconnection
    auto_reconnect=True,
    reconnect_delay=3.0,

    # Headers
    headers={"Authorization": "Bearer token"}
)

sse = SSEClient("https://api.example.com/events", config=config)
```

### Event Types

```python
import logging

logger = logging.getLogger(__name__)

async with SSEClient("https://api.example.com/events") as sse:
    async for event in sse:
        if event.event == "message":
            logger.info(f"Message: {event.data}")
        elif event.event == "token":
            logger.info(event.data, end="", flush=True)
        elif event.event == "error":
            logger.info(f"Error: {event.data}")
        elif event.event == "done":
            logger.info("\nStream completed")
            break
```

### Streaming AI Responses

```python
import logging

logger = logging.getLogger(__name__)

from agenticaiframework.communication import SSEClient

async def stream_completion(prompt: str):
    """Stream AI completion tokens."""
    async with SSEClient(
        "https://api.example.com/completions",
        method="POST",
        json={"prompt": prompt, "stream": True}
    ) as sse:
        full_response = ""
        async for event in sse:
            if event.event == "token":
                token = event.data
                full_response += token
                yield token
            elif event.event == "done":
                break

        return full_response

# Usage
async for token in stream_completion("Tell me a story"):
    logger.info(token, end="", flush=True)
```

---

## MQTT Protocol

MQTT provides lightweight publish-subscribe messaging, ideal for IoT and event-driven architectures.

### Basic Usage

```python
import logging

logger = logging.getLogger(__name__)

from agenticaiframework.communication import MQTTClient

async with MQTTClient("mqtt://broker.example.com:1883") as mqtt:
    # Subscribe to topic
    await mqtt.subscribe("agents/+/status")

    # Publish message
    await mqtt.publish(
        topic="agents/agent_01/status",
        payload={"status": "online", "timestamp": "2024-01-15T10:30:00Z"}
    )

    # Receive messages
    async for message in mqtt:
        logger.info(f"Topic: {message.topic}")
        logger.info(f"Payload: {message.payload}")
```

### Configuration

```python
from agenticaiframework.communication import MQTTClient, MQTTConfig

config = MQTTConfig(
    # Connection
    host="broker.example.com",
    port=1883,
    client_id="agent_client_01",

    # Authentication
    username="user",
    password="password",

    # TLS/SSL
    use_tls=True,
    ca_certs="/path/to/ca.pem",

    # Quality of Service
    default_qos=1, # 0: At most once, 1: At least once, 2: Exactly once

    # Keep alive
    keepalive=60,

    # Clean session
    clean_session=True
)

mqtt = MQTTClient(config=config)
```

### Topic Patterns

```python
async with MQTTClient(broker_url) as mqtt:
    # Subscribe to single topic
    await mqtt.subscribe("agents/agent_01/status")

    # Subscribe with single-level wildcard (+)
    await mqtt.subscribe("agents/+/status") # Any agent's status

    # Subscribe with multi-level wildcard (#)
    await mqtt.subscribe("agents/#") # All agent messages

    # Multiple subscriptions
    await mqtt.subscribe([("agents/+/status", 1), # QoS 1
        ("tasks/+/result", 2), # QoS 2
    ])
```

### Message Handling

```python
import logging

logger = logging.getLogger(__name__)

from agenticaiframework.communication import MQTTClient

mqtt = MQTTClient(broker_url)

@mqtt.on_message("agents/+/status")
async def handle_agent_status(topic, payload):
    agent_id = topic.split("/")[1]
    logger.info(f"Agent {agent_id} status: {payload}")

@mqtt.on_message("tasks/+/result")
async def handle_task_result(topic, payload):
    task_id = topic.split("/")[1]
    logger.info(f"Task {task_id} result: {payload}")

await mqtt.connect()
await mqtt.start_listening()
```

---

## gRPC Protocol

gRPC provides high-performance RPC communication with Protocol Buffers, ideal for microservices.

### Basic Usage

```python
import logging

logger = logging.getLogger(__name__)

from agenticaiframework.communication import GRPCClient

# Connect to gRPC server
async with GRPCClient("localhost:50051") as client:
    # Unary RPC
    response = await client.call(
        service="AgentService",
        method="ExecuteTask",
        request={"task_id": "123", "input": "Process this"}
    )
    logger.info(response)
```

### Configuration

```python
from agenticaiframework.communication import GRPCClient, GRPCConfig

config = GRPCConfig(
    # Connection
    target="localhost:50051",

    # TLS/SSL
    secure=True,
    root_certificates="/path/to/ca.pem",
    private_key="/path/to/key.pem",
    certificate_chain="/path/to/cert.pem",

    # Options
    max_message_length=4 * 1024 * 1024, # 4MB
    compression="gzip",

    # Timeouts
    timeout_seconds=30,

    # Retry
    max_retries=3,
    retry_delay=1.0
)

client = GRPCClient(config=config)
```

### Streaming RPCs

=== "Server Streaming"
    ```python
    async with GRPCClient(target) as client:
        # Server streams responses
        async for response in client.stream_call(
            service="AgentService",
            method="StreamTokens",
            request={"prompt": "Tell me a story"}
        ):
            print(response["token"], end="", flush=True)
    ```

=== "Client Streaming"
    ```python
    async with GRPCClient(target) as client:
        # Client streams requests
        async def generate_chunks():
            for chunk in data_chunks:
                yield {"chunk": chunk}

        response = await client.stream_send(
            service="DataService",
            method="UploadData",
            requests=generate_chunks()
        )
    ```

=== "Bidirectional Streaming"
    ```python
import logging

logger = logging.getLogger(__name__)

    async with GRPCClient(target) as client:
        # Both sides stream
        async def chat_stream():
            yield {"message": "Hello"}
            yield {"message": "How are you?"}

        async for response in client.bidirectional_stream(
            service="ChatService",
            method="Chat",
            requests=chat_stream()
        ):
            logger.info(f"Response: {response['message']}")
    ```

### Service Definition

```python
# Generate from .proto file
from agenticaiframework.communication import generate_grpc_client

# Auto-generate client from proto
client = generate_grpc_client(
    proto_file="agent_service.proto",
    target="localhost:50051"
)

# Use generated methods
response = await client.AgentService.ExecuteTask(
    task_id="123",
    input="Process this"
)
```

---

## STDIO Protocol

STDIO provides process-based communication through standard input/output, perfect for CLI tools and local integrations.

### Basic Usage

```python
import logging

logger = logging.getLogger(__name__)

from agenticaiframework.communication import STDIOClient

# Communicate with subprocess
async with STDIOClient(
    command=["python", "worker.py"],
    working_dir="./workers"
) as stdio:
    # Send input
    await stdio.send({"task": "process", "data": input_data})

    # Receive output
    response = await stdio.receive()
    logger.info(response)
```

### Configuration

```python
from agenticaiframework.communication import STDIOClient, STDIOConfig

config = STDIOConfig(
    # Process settings
    command=["node", "agent.js"],
    working_dir="./agents",
    env={"NODE_ENV": "production"},

    # I/O settings
    encoding="utf-8",
    line_buffered=True,

    # Timeouts
    startup_timeout=10,
    response_timeout=60,

    # Message format
    message_format="json", # Options: json, line, raw
    delimiter="\n"
)

stdio = STDIOClient(config=config)
```

### Interactive Mode

```python
import logging

logger = logging.getLogger(__name__)

async with STDIOClient(command=["python", "-i"]) as stdio:
    # Interactive Python session
    await stdio.send("x = 42")
    await stdio.send("print(x * 2)")

    response = await stdio.receive()
    logger.info(response) # "84"
```

### MCP Server Communication

```python
import logging

logger = logging.getLogger(__name__)

from agenticaiframework.communication import STDIOClient

# Connect to MCP server
async with STDIOClient(
    command=["npx", "@modelcontextprotocol/server-filesystem"],
    message_format="jsonrpc"
) as mcp:
    # Initialize MCP session
    await mcp.send({
        "jsonrpc": "2.0",
        "method": "initialize",
        "params": {"capabilities": {}},
        "id": 1
    })

    init_response = await mcp.receive()
    logger.info(f"MCP initialized: {init_response}")

    # List tools
    await mcp.send({
        "jsonrpc": "2.0",
        "method": "tools/list",
        "id": 2
    })

    tools = await mcp.receive()
    logger.info(f"Available tools: {tools}")
```

---

## Connection Management

### Connection Pooling

```python
from agenticaiframework.communication import ConnectionPool

# Create connection pool
pool = ConnectionPool(
    protocol="http",
    max_connections=10,
    max_connections_per_host=5,
    connection_timeout=30,
    idle_timeout=300
)

# Use pooled connections
async with pool.get_connection("https://api.example.com") as conn:
    response = await conn.get("/data")
```

### Health Checks

```python
import logging

logger = logging.getLogger(__name__)

from agenticaiframework.communication import ConnectionManager

manager = ConnectionManager()

# Register connections
manager.register("api", HTTPClient("https://api.example.com"))
manager.register("broker", MQTTClient("mqtt://broker.example.com"))

# Health check all connections
health = await manager.health_check()
for name, status in health.items():
    logger.info(f"{name}: {'healthy' if status.is_healthy else 'unhealthy'}")
```

---

## API Reference

For complete API documentation, see:

- [HTTPClient API](API_REFERENCE.md#httpclient)
- [WebSocketClient API](API_REFERENCE.md#websocketclient)
- [SSEClient API](API_REFERENCE.md#sseclient)
- [MQTTClient API](API_REFERENCE.md#mqttclient)
- [GRPCClient API](API_REFERENCE.md#grpcclient)
- [STDIOClient API](API_REFERENCE.md#stdioclient)
