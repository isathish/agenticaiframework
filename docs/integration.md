---
title: Integration Patterns
description: Connect to external systems with 18+ enterprise connectors for APIs, databases, and message queues
tags:
  - integration
  - external-services
  - APIs
  - patterns
  - servicenow
  - github
  - azure-devops
  - enterprise
---

# 🔌 Integration Patterns

<div class="annotate" markdown>

**Connect to external systems and services**

Comprehensive integration guide for APIs, databases, and message queues across **400+ modules**

</div>

!!! success "Enterprise Integrations"
    Part of **237 enterprise modules** with **18 pre-built connectors** for ServiceNow, GitHub, Azure DevOps, Slack, Salesforce, and more. See [Enterprise Documentation](enterprise.md).

---

## 🎯 Quick Navigation

<div class="grid cards" markdown>

-   :material-api:{ .lg } **REST APIs**
    
    HTTP/REST integration patterns
    
    [:octicons-arrow-right-24: Integrate](#rest-api-integration)

-   :material-database:{ .lg } **Databases**
    
    SQL and NoSQL connections
    
    [:octicons-arrow-right-24: Connect](#database-integration)

-   :material-message:{ .lg } **Message Queues**
    
    Kafka, RabbitMQ integration
    
    [:octicons-arrow-right-24: Setup](#message-queue-integration)

-   :material-office-building:{ .lg } **Enterprise**
    
    ServiceNow, GitHub, Azure DevOps
    
    [:octicons-arrow-right-24: Connect](#enterprise-integrations)

</div>


## 📊 Overview

This guide demonstrates various integration patterns for connecting AgenticAI Framework with external systems, APIs, databases, and services.

!!! success "Enterprise Connectors"
    
    The framework includes **18 pre-built enterprise integration connectors** for ServiceNow, GitHub, Azure DevOps, Slack, Teams, Salesforce, AWS, Azure, GCP, and more.


## 🎯 Integration Architecture

```mermaid
graph TB
    subgraph "AgenticAI Framework"
        AGENT[Agent Manager]
        TASK[Task Manager]
        MEMORY[Memory Manager]
    end
    
    subgraph "Integration Layer"
        API[API Connectors]
        DB[Database Adapters]
        MSG[Message Queue]
        WEBHOOK[Webhook Manager]
    end
    
    subgraph "External Systems"
        REST[REST APIs]
        GRAPHQL[GraphQL APIs]
        GRPC[gRPC Services]
        POSTGRES[(PostgreSQL)]
        MONGO[(MongoDB)]
        REDIS[(Redis)]
        KAFKA[Kafka]
        RABBITMQ[RabbitMQ]
        S3[S3/Blob Storage]
    end
    
    AGENT --> API
    AGENT --> DB
    TASK --> MSG
    MEMORY --> DB
    
    API --> REST & GRAPHQL & GRPC
    DB --> POSTGRES & MONGO & REDIS
    MSG --> KAFKA & RABBITMQ
    WEBHOOK --> REST
    
    S3 -.backup/restore.-> DB
    
    style AGENT fill:#4caf50
    style API fill:#2196f3
    style REST fill:#ff9800
```


## 🌐 REST API Integration

### 1. Basic HTTP Client

```python
import aiohttp
import asyncio

class RESTAPIClient:
    """Async REST API client"""
    
    def __init__(self, base_url: str, api_key: str = None):
        self.base_url = base_url
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}" if api_key else None
        }
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(headers=self.headers)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.close()
    
    async def get(self, endpoint: str, params: Dict = None) -> Dict:
        """GET request"""
        async with self.session.get(
            f"{self.base_url}/{endpoint}",
            params=params
        ) as response:
            response.raise_for_status()
            return await response.json()
    
    async def post(self, endpoint: str, data: Dict) -> Dict:
        """POST request"""
        async with self.session.post(
            f"{self.base_url}/{endpoint}",
            json=data
        ) as response:
            response.raise_for_status()
            return await response.json()
    
    async def put(self, endpoint: str, data: Dict) -> Dict:
        """PUT request"""
        async with self.session.put(
            f"{self.base_url}/{endpoint}",
            json=data
        ) as response:
            response.raise_for_status()
            return await response.json()
    
    async def delete(self, endpoint: str) -> Dict:
        """DELETE request"""
        async with self.session.delete(
            f"{self.base_url}/{endpoint}"
        ) as response:
            response.raise_for_status()
            return await response.json()

# Usage
async def fetch_data_example():
    async with RESTAPIClient("https://api.example.com", api_key="your-key") as client:
        # GET request
        users = await client.get("users", params={"limit": 10})
        
        # POST request
        new_user = await client.post("users", data={"name": "John", "email": "john@example.com"})
        
        return users, new_user
```

### 2. Agent with REST Integration

```python
from agenticaiframework.agents import Agent

class APIIntegrationAgent(Agent):
    """Agent that integrates with external APIs"""
    
    def __init__(self, name: str, api_client: RESTAPIClient):
        super().__init__(name=name, role="api_integrator", capabilities=["api_calls"])
        self.api_client = api_client
    
    async def fetch_user_data(self, user_id: str):
        """Fetch user data from external API"""
        try:
            user_data = await self.api_client.get(f"users/{user_id}")
            
            # Store in memory
            self.memory_manager.store(
                key=f"user_{user_id}",
                value=user_data
            )
            
            return user_data
        except Exception as e:
            self.logger.error(f"Failed to fetch user data: {e}")
            raise
    
    async def create_resource(self, resource_type: str, data: dict):
        """Create resource via API"""
        result = await self.api_client.post(resource_type, data=data)
        return result

# Usage
async def main():
    async with RESTAPIClient("https://api.example.com", "api-key") as client:
        agent = APIIntegrationAgent("api_agent", api_client=client)
        
        # Fetch data
        user = await agent.fetch_user_data("user_123")
        
        # Create resource
        resource = await agent.create_resource("projects", {
            "name": "New Project",
            "description": "AI-powered project"
        })
```


## 🔗 GraphQL Integration

### 1. GraphQL Client

```python
from gql import gql, Client
from gql.transport.aiohttp import AIOHTTPTransport

class GraphQLClient:
    """GraphQL API client"""
    
    def __init__(self, endpoint: str, api_key: str = None):
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        
        transport = AIOHTTPTransport(url=endpoint, headers=headers)
        self.client = Client(transport=transport, fetch_schema_from_transport=True)
    
    async def query(self, query_string: str, variables: dict = None):
        """Execute GraphQL query"""
        query = gql(query_string)
        result = await self.client.execute_async(query, variable_values=variables)
        return result
    
    async def mutate(self, mutation_string: str, variables: dict = None):
        """Execute GraphQL mutation"""
        mutation = gql(mutation_string)
        result = await self.client.execute_async(mutation, variable_values=variables)
        return result

# Usage
graphql_client = GraphQLClient("https://api.example.com/graphql", api_key="your-key")

# Query
query = """
    query GetUsers($limit: Int!) {
        users(limit: $limit) {
            id
            name
            email
        }
    }
"""
users = await graphql_client.query(query, variables={"limit": 10})

# Mutation
mutation = """
    mutation CreateUser($input: UserInput!) {
        createUser(input: $input) {
            id
            name
            email
        }
    }
"""
new_user = await graphql_client.mutate(mutation, variables={
    "input": {"name": "John", "email": "john@example.com"}
})
```


## 🗄️ Database Integration

### 1. PostgreSQL Integration

```python
import asyncpg

class PostgreSQLAdapter:
    """PostgreSQL database adapter"""
    
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.pool = None
    
    async def connect(self):
        """Create connection pool"""
        self.pool = await asyncpg.create_pool(
            self.connection_string,
            min_size=10,
            max_size=50,
            command_timeout=60
        )
    
    async def close(self):
        """Close connection pool"""
        await self.pool.close()
    
    async def execute(self, query: str, *args) -> str:
        """Execute query without returning results"""
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)
    
    async def fetch_one(self, query: str, *args) -> Dict:
        """Fetch single row"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, *args)
            return dict(row) if row else None
    
    async def fetch_all(self, query: str, *args) -> list[Dict]:
        """Fetch all rows"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *args)
            return [dict(row) for row in rows]
    
    async def transaction(self, queries: list[tuple]):
        """Execute multiple queries in transaction"""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                results = []
                for query, args in queries:
                    result = await conn.execute(query, *args)
                    results.append(result)
                return results

# Usage with Agent
class DatabaseAgent(Agent):
    """Agent with database integration"""
    
    def __init__(self, name: str, db_adapter: PostgreSQLAdapter):
        super().__init__(name=name, role="data_manager", capabilities=["database"])
        self.db = db_adapter
    
    async def store_result(self, task_id: str, result: dict):
        """Store task result in database"""
        query = """
            INSERT INTO task_results (task_id, result, created_at)
            VALUES ($1, $2, NOW())
            RETURNING id
        """
        result_id = await self.db.fetch_one(query, task_id, json.dumps(result))
        return result_id
    
    async def get_user_history(self, user_id: str):
        """Retrieve user history from database"""
        query = """
            SELECT * FROM user_history
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT 100
        """
        history = await self.db.fetch_all(query, user_id)
        return history
```

### 2. MongoDB Integration

```python
from motor.motor_asyncio import AsyncIOMotorClient

class MongoDBAdapter:
    """MongoDB database adapter"""
    
    def __init__(self, connection_string: str, database_name: str):
        self.client = AsyncIOMotorClient(connection_string)
        self.db = self.client[database_name]
    
    async def insert_one(self, collection: str, document: Dict) -> str:
        """Insert single document"""
        result = await self.db[collection].insert_one(document)
        return str(result.inserted_id)
    
    async def insert_many(self, collection: str, documents: list[Dict]) -> list[str]:
        """Insert multiple documents"""
        result = await self.db[collection].insert_many(documents)
        return [str(id) for id in result.inserted_ids]
    
    async def find_one(self, collection: str, filter: Dict) -> Dict:
        """Find single document"""
        document = await self.db[collection].find_one(filter)
        if document:
            document['_id'] = str(document['_id'])
        return document
    
    async def find_many(self, collection: str, filter: Dict, limit: int = 100) -> list[Dict]:
        """Find multiple documents"""
        cursor = self.db[collection].find(filter).limit(limit)
        documents = await cursor.to_list(length=limit)
        
        for doc in documents:
            doc['_id'] = str(doc['_id'])
        
        return documents
    
    async def update_one(self, collection: str, filter: Dict, update: Dict) -> int:
        """Update single document"""
        result = await self.db[collection].update_one(filter, {'$set': update})
        return result.modified_count
    
    async def delete_one(self, collection: str, filter: Dict) -> int:
        """Delete single document"""
        result = await self.db[collection].delete_one(filter)
        return result.deleted_count
    
    async def aggregate(self, collection: str, pipeline: list[Dict]) -> list[Dict]:
        """Execute aggregation pipeline"""
        cursor = self.db[collection].aggregate(pipeline)
        return await cursor.to_list(length=None)

# Usage
mongo = MongoDBAdapter("mongodb://localhost:27017", "agenticai")

# Insert document
doc_id = await mongo.insert_one("agents", {
    "name": "research_agent",
    "status": "active",
    "created_at": datetime.utcnow()
})

# Query documents
agents = await mongo.find_many("agents", {"status": "active"})
```

### 3. Redis Integration

```python
import aioredis
import json

class RedisAdapter:
    """Redis cache adapter"""
    
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.redis = None
    
    async def connect(self):
        """Connect to Redis"""
        self.redis = await aioredis.from_url(
            self.redis_url,
            encoding="utf-8",
            decode_responses=True
        )
    
    async def close(self):
        """Close Redis connection"""
        await self.redis.close()
    
    async def get(self, key: str) -> Any:
        """Get value from cache"""
        value = await self.redis.get(key)
        return json.loads(value) if value else None
    
    async def set(self, key: str, value: Any, ttl: int = None):
        """Set value in cache"""
        serialized = json.dumps(value)
        if ttl:
            await self.redis.setex(key, ttl, serialized)
        else:
            await self.redis.set(key, serialized)
    
    async def delete(self, key: str):
        """Delete key from cache"""
        await self.redis.delete(key)
    
    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        return await self.redis.exists(key)
    
    async def expire(self, key: str, ttl: int):
        """Set expiration on key"""
        await self.redis.expire(key, ttl)
    
    async def get_many(self, keys: list[str]) -> dict[str, Any]:
        """Get multiple values"""
        values = await self.redis.mget(keys)
        return {
            key: json.loads(value) if value else None
            for key, value in zip(keys, values)
        }
    
    async def set_many(self, mapping: dict[str, Any], ttl: int = None):
        """Set multiple values"""
        serialized = {k: json.dumps(v) for k, v in mapping.items()}
        await self.redis.mset(serialized)
        
        if ttl:
            for key in mapping.keys():
                await self.redis.expire(key, ttl)

# Usage with caching
class CachedAgent(Agent):
    """Agent with Redis caching"""
    
    def __init__(self, name: str, redis: RedisAdapter):
        super().__init__(name=name, role="cached_agent", capabilities=["caching"])
        self.redis = redis
    
    async def get_with_cache(self, key: str, fetch_fn):
        """Get data with caching"""
        # Check cache
        cached = await self.redis.get(key)
        if cached:
            return cached
        
        # Cache miss - fetch data
        data = await fetch_fn()
        
        # Store in cache (TTL: 1 hour)
        await self.redis.set(key, data, ttl=3600)
        
        return data
```


## 📨 Message Queue Integration

### 1. Kafka Integration

```python
import logging

logger = logging.getLogger(__name__)

from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
import json

class KafkaAdapter:
    """Kafka message broker adapter"""
    
    def __init__(self, bootstrap_servers: str):
        self.bootstrap_servers = bootstrap_servers
        self.producer = None
        self.consumers = {}
    
    async def connect_producer(self):
        """Connect Kafka producer"""
        self.producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        await self.producer.start()
    
    async def send_message(self, topic: str, message: dict, key: str = None):
        """Send message to topic"""
        await self.producer.send(
            topic,
            value=message,
            key=key.encode('utf-8') if key else None
        )
    
    async def connect_consumer(self, topic: str, group_id: str):
        """Connect Kafka consumer"""
        consumer = AIOKafkaConsumer(
            topic,
            bootstrap_servers=self.bootstrap_servers,
            group_id=group_id,
            value_deserializer=lambda m: json.loads(m.decode('utf-8'))
        )
        await consumer.start()
        self.consumers[topic] = consumer
        return consumer
    
    async def consume_messages(self, topic: str, callback):
        """Consume messages from topic"""
        consumer = self.consumers.get(topic)
        if not consumer:
            raise ValueError(f"No consumer for topic: {topic}")
        
        async for message in consumer:
            await callback(message.value)
    
    async def close(self):
        """Close all connections"""
        if self.producer:
            await self.producer.stop()
        
        for consumer in self.consumers.values():
            await consumer.stop()

# Usage
kafka = KafkaAdapter("localhost:9092")

# Producer
await kafka.connect_producer()
await kafka.send_message("agent_tasks", {
    "task_id": "task_001",
    "agent_id": "agent_001",
    "action": "process_data"
})

# Consumer
async def handle_task(message):
    logger.info(f"Processing task: {message}")
    # Process task

consumer = await kafka.connect_consumer("agent_tasks", group_id="agent_workers")
await kafka.consume_messages("agent_tasks", handle_task)
```

### 2. RabbitMQ Integration

```python
import logging

logger = logging.getLogger(__name__)

import aio_pika
import json

class RabbitMQAdapter:
    """RabbitMQ message broker adapter"""
    
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.connection = None
        self.channel = None
    
    async def connect(self):
        """Connect to RabbitMQ"""
        self.connection = await aio_pika.connect_robust(self.connection_string)
        self.channel = await self.connection.channel()
    
    async def publish(self, queue_name: str, message: dict):
        """Publish message to queue"""
        await self.channel.default_exchange.publish(
            aio_pika.Message(
                body=json.dumps(message).encode(),
                content_type="application/json"
            ),
            routing_key=queue_name
        )
    
    async def consume(self, queue_name: str, callback):
        """Consume messages from queue"""
        queue = await self.channel.declare_queue(queue_name, durable=True)
        
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    data = json.loads(message.body.decode())
                    await callback(data)
    
    async def close(self):
        """Close connection"""
        await self.connection.close()

# Usage
rabbitmq = RabbitMQAdapter("amqp://guest:guest@localhost/")
await rabbitmq.connect()

# Publish
await rabbitmq.publish("task_queue", {
    "task_id": "task_001",
    "priority": "high"
})

# Consume
async def process_task(task):
    logger.info(f"Processing: {task}")

await rabbitmq.consume("task_queue", process_task)
```


## 🔔 Webhook Integration

```python
import logging

logger = logging.getLogger(__name__)

from fastapi import FastAPI, Request, HTTPException
import hashlib
import hmac

class WebhookManager:
    """Webhook management system"""
    
    def __init__(self, app: FastAPI):
        self.app = app
        self.handlers = {}
        self.secrets = {}
    
    def register_webhook(self, path: str, secret: str, handler: Callable):
        """Register webhook endpoint"""
        self.handlers[path] = handler
        self.secrets[path] = secret
        
        @self.app.post(path)
        async def webhook_endpoint(request: Request):
            # Verify signature
            if not await self.verify_signature(request, path):
                raise HTTPException(status_code=401, detail="Invalid signature")
            
            # Get payload
            payload = await request.json()
            
            # Call handler
            result = await handler(payload)
            
            return {"status": "success", "result": result}
    
    async def verify_signature(self, request: Request, path: str) -> bool:
        """Verify webhook signature"""
        secret = self.secrets.get(path)
        if not secret:
            return False
        
        # Get signature from header
        signature_header = request.headers.get("X-Webhook-Signature")
        if not signature_header:
            return False
        
        # Calculate expected signature
        body = await request.body()
        expected_signature = hmac.new(
            secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature_header, expected_signature)
    
    async def send_webhook(self, url: str, payload: dict, secret: str = None):
        """Send webhook to external service"""
        headers = {"Content-Type": "application/json"}
        
        if secret:
            # Calculate signature
            body = json.dumps(payload).encode()
            signature = hmac.new(
                secret.encode(),
                body,
                hashlib.sha256
            ).hexdigest()
            headers["X-Webhook-Signature"] = signature
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as response:
                return await response.json()

# Usage
app = FastAPI()
webhook_manager = WebhookManager(app)

# Register incoming webhook
async def handle_github_webhook(payload: dict):
    """Handle GitHub webhook"""
    event_type = payload.get("action")
    repository = payload.get("repository", {}).get("name")
    
    logger.info(f"GitHub event: {event_type} on {repository}")
    
    # Process webhook
    # ...
    
    return {"processed": True}

webhook_manager.register_webhook(
    path="/webhooks/github",
    secret="your-webhook-secret",
    handler=handle_github_webhook
)

# Send outgoing webhook
await webhook_manager.send_webhook(
    url="https://hooks.slack.com/services/xxx",
    payload={"text": "Agent completed task"},
    secret="slack-webhook-secret"
)
```

---

## 🏢 Enterprise Integrations

The AgenticAI Framework provides built-in connectors for popular enterprise systems.

### Integration Manager

Central management for all integrations:

```python
import logging

logger = logging.getLogger(__name__)

from agenticaiframework.integrations import (
    IntegrationManager,
    IntegrationConfig,
    IntegrationStatus,
    integration_manager
)

# Add a ServiceNow integration
config = integration_manager.add_integration(
    name="production_snow",
    integration_type="servicenow",
    endpoint="https://yourinstance.service-now.com/api",
    auth_type="api_key",
    credentials={"api_key": "your-api-key"},
    settings={"timeout": 30}
)

# Connect
integration_manager.connect(config.integration_id)

# Health check
health = integration_manager.health_check(config.integration_id)
logger.info(f"Status: {health['status']}")

# List all integrations
all_integrations = integration_manager.list_integrations()
```

### ServiceNow Integration

ITSM integration for incident, change, and problem management:

```python
import logging

logger = logging.getLogger(__name__)

from agenticaiframework.integrations import (
    ServiceNowIntegration,
    IntegrationConfig,
    IntegrationStatus
)

# Create ServiceNow integration
config = IntegrationConfig(
    integration_id="snow-001",
    name="ServiceNow Production",
    integration_type="servicenow",
    endpoint="https://yourinstance.service-now.com/api",
    auth_type="api_key",
    credentials={"api_key": "your-key"},
    settings={},
    status=IntegrationStatus.PENDING,
    created_at=time.time()
)

snow = ServiceNowIntegration(config)
snow.connect()

# Create an incident
incident = snow.create_incident(
    short_description="AI Agent detected anomaly",
    description="Automated detection of performance degradation in production.",
    urgency=2,
    impact=2,
    assignment_group="IT-Operations",
    category="Performance"
)
logger.info(f"Created incident: {incident['number']}")

# Create a change request
change = snow.create_change_request(
    short_description="Deploy AI Agent update",
    description="Rolling deployment of AgenticAI Framework v1.2.13",
    change_type="standard",
    risk="low"
)
```

### GitHub Integration

Repository, issue, and pull request management:

```python
import logging

logger = logging.getLogger(__name__)

from agenticaiframework.integrations import GitHubIntegration, IntegrationConfig

config = IntegrationConfig(
    integration_id="gh-001",
    name="GitHub Enterprise",
    integration_type="github",
    endpoint="https://api.github.com",
    auth_type="token",
    credentials={"token": "ghp_xxxxxxxxxxxx"},
    settings={},
    status=IntegrationStatus.PENDING,
    created_at=time.time()
)

github = GitHubIntegration(config)
github.connect()

# Create an issue
issue = github.create_issue(
    owner="myorg",
    repo="myrepo",
    title="AI Agent identified bug",
    body="Automated bug detection by AgenticAI Framework.",
    labels=["bug", "ai-detected"],
    assignees=["developer1"]
)
logger.info(f"Created issue: {issue['html_url']}")

# Create a pull request
pr = github.create_pull_request(
    owner="myorg",
    repo="myrepo",
    title="AI-generated fix for #123",
    body="This PR was created by an AI agent.",
    head="feature/ai-fix",
    base="main"
)
```

### Azure DevOps Integration

Work items, repositories, and pipelines:

```python
from agenticaiframework.integrations import AzureDevOpsIntegration, IntegrationConfig

config = IntegrationConfig(
    integration_id="ado-001",
    name="Azure DevOps",
    integration_type="azure_devops",
    endpoint="https://dev.azure.com/yourorg",
    auth_type="pat",
    credentials={"pat": "your-personal-access-token"},
    settings={"project": "MyProject"},
    status=IntegrationStatus.PENDING,
    created_at=time.time()
)

ado = AzureDevOpsIntegration(config)
ado.connect()

# Create a work item
work_item = ado.create_work_item(
    work_item_type="Bug",
    title="AI-detected issue",
    description="Found during automated analysis.",
    assigned_to="developer@company.com"
)

# Trigger a pipeline
pipeline_run = ado.trigger_pipeline(
    pipeline_id=123,
    branch="main",
    parameters={"environment": "staging"}
)
```

### Data Platform Connectors

Connect to Snowflake and Databricks:

```python
from agenticaiframework.integrations import (
    SnowflakeConnector,
    DatabricksConnector
)

# Snowflake
snowflake = SnowflakeConnector(
    account="your-account",
    user="username",
    password="password",
    warehouse="COMPUTE_WH",
    database="ANALYTICS",
    schema="PUBLIC"
)

results = await snowflake.execute_query(
    "SELECT * FROM sales WHERE date > '2024-01-01'"
)

# Databricks
databricks = DatabricksConnector(
    workspace_url="https://your-workspace.cloud.databricks.com",
    token="dapi_xxxxx"
)

job_run = await databricks.run_job(
    job_id=12345,
    parameters={"input_path": "/data/raw"}
)
```

### Webhook Manager

Manage incoming and outgoing webhooks:

```python
from agenticaiframework.integrations import WebhookManager, webhook_manager

# Register a webhook endpoint
webhook_manager.register_endpoint(
    name="github-events",
    path="/webhooks/github",
    secret="webhook-secret",
    handler=async def(payload): 
        # Process webhook
        return {"status": "processed"}
)

# Send a webhook
await webhook_manager.send(
    url="https://api.slack.com/incoming-webhook",
    payload={"text": "Task completed by AI agent"},
    headers={"Authorization": "Bearer token"}
)
```


## 📚 Related Documentation

- [Deployment Guide](deployment.md) - Production deployment
- [Architecture Overview](architecture.md) - System design
- [Security](security.md) - Security best practices
- [Best Practices](best-practices.md) - Development guidelines


<div align="center">

**[⬆ Back to Top](#-integration-patterns)**

</div>
