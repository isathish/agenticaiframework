---
title: Cloud Integrations
description: Use AWS, Microsoft Azure and Google Cloud from AgenticAI Framework - S3, Bedrock, Azure Blob, Azure OpenAI, Cosmos DB, Service Bus, Key Vault, Cloud Storage and Vertex AI through one adapter interface, with or without vendor SDKs.
tags:
  - cloud
  - aws
  - azure
  - gcp
  - enterprise
---

# Cloud Integrations

The framework talks to the three major clouds through a small set of adapter interfaces in `agenticaiframework.enterprise`. Each interface has one implementation per provider, and a unified adapter per cloud groups them behind `storage`, `llm`, `vectordb`, `queue` and `cache` properties.

Vendor SDKs (`boto3`, `azure-storage-blob`, `google-cloud-storage`, and so on) are used when they are installed. When they are not, each adapter falls back to a standard-library client in `agenticaiframework._internal.clients`: SigV4 request signing for S3 and Bedrock, shared-key and SAS authentication for Azure Blob and Service Bus, and service-account JWT exchange for Google Cloud Storage and Vertex AI. The behaviour is the same either way; only the transport changes.

## At a glance

| Capability | AWS | Azure | Google Cloud |
|---|---|---|---|
| Object storage | `AWSS3Storage` | `AzureBlobStorage` | `GCPCloudStorage` |
| LLM and embeddings | `AWSBedrockLLM` | `AzureOpenAILLM` | `GCPVertexAILLM` |
| Vector database | — | `AzureCosmosVectorDB` | — |
| Message queue | — | `AzureServiceBusQueue` | — |
| Cache | — | `AzureRedisCache` | — |
| Secrets | — | `AzureKeyVaultBackend` | — |
| Speech | — | `AzureSTT`, `AzureTTS` | `GoogleSTT`, `GoogleTTS` |
| Dev / ITSM | — | `AzureDevOpsIntegration` | — |
| Unified adapter | `AWSAdapter` | `AzureAdapter` | `GCPAdapter` |
| Stdlib fallback client | `s3_rest`, `aws_sigv4` | `azure_blob_rest`, `azure_servicebus_rest`, `cosmos_rest`, `openai_rest` | `gcp_rest` (GCS, Vertex AI, Speech, Text-to-Speech, Vision) |

## Pick an adapter

`get_adapter()` returns the adapter for an explicit provider, or detects one from the environment.

```python
from agenticaiframework.enterprise import get_adapter, AWSAdapter, AzureAdapter, GCPAdapter

cloud = get_adapter("aws")          # explicit
cloud = get_adapter()               # detected from environment variables
```

Detection order and the variables checked:

| Order | Provider | Any of these variables set |
|---|---|---|
| 1 | Azure | `AZURE_OPENAI_API_KEY`, `AZURE_STORAGE_CONNECTION_STRING` |
| 2 | AWS | `AWS_ACCESS_KEY_ID`, `AWS_REGION` |
| 3 | Google Cloud | `GOOGLE_CLOUD_PROJECT`, `GOOGLE_APPLICATION_CREDENTIALS` |

If nothing matches, `get_adapter()` logs a warning and returns `AzureAdapter()`. Pass the provider explicitly in production code.

All adapter methods are coroutines. Blocking SDK calls are executed in a thread via `asyncio.to_thread`, so the adapters can be awaited from an event loop without stalling it.

## Amazon Web Services

### Credentials

| Variable | Used for |
|---|---|
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | SigV4 signing (required when `boto3` is not installed) |
| `AWS_SESSION_TOKEN` | Temporary credentials from STS or SSO |
| `AWS_REGION` | Region for S3 and Bedrock; defaults to `us-east-1` |

With `boto3` installed, the standard credential chain (profiles, instance roles, IRSA) applies.

### S3

```python
from agenticaiframework.enterprise import AWSAdapter

aws = AWSAdapter(bucket="agent-artifacts", region="eu-west-1")

url = await aws.storage.upload("runs/2026-09-04/report.md", report_markdown)
print(url)                                        # s3://agent-artifacts/runs/2026-09-04/report.md

text = await aws.storage.download("runs/2026-09-04/report.md")
keys = await aws.storage.list(prefix="runs/2026-09-04/")
await aws.storage.delete("runs/2026-09-04/report.md")
```

`AWSS3Storage(bucket_name, region)` can also be constructed directly. Downloads return `str` when the object decodes as UTF-8 and `bytes` otherwise.

### Bedrock

```python
aws = AWSAdapter(llm_model="anthropic.claude-3-sonnet-20240229-v1:0")

answer = await aws.llm.generate("Summarise the attached report in three bullets.", max_tokens=300)
reply = await aws.llm.chat(
    [{"role": "system", "content": "Answer tersely."},
     {"role": "user", "content": "What is SigV4?"}],
)
vectors = await aws.llm.embed(["first passage", "second passage"], model="amazon.titan-embed-text-v2:0")
```

Chat requests use the Anthropic messages schema (`anthropic_version: bedrock-2023-05-31`), so any Claude model ID on Bedrock works. Without `boto3`, requests are signed with SigV4 for the `bedrock` service and sent to `bedrock-runtime.<region>.amazonaws.com`.

## Microsoft Azure

### Credentials

| Variable | Used by |
|---|---|
| `AZURE_STORAGE_CONNECTION_STRING` | `AzureBlobStorage` |
| `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT` | `AzureOpenAILLM` |
| `COSMOS_CONNECTION_STRING` | `AzureCosmosVectorDB` |
| `SERVICE_BUS_CONNECTION_STRING` | `AzureServiceBusQueue` |
| `REDIS_HOST`, `REDIS_PASSWORD` | `AzureRedisCache` (port 6380, TLS) |
| `AZURE_SPEECH_KEY` | `AzureSTT`, `AzureTTS` |

`AzureKeyVaultBackend` uses `DefaultAzureCredential` from `azure-identity`, so managed identity, Azure CLI login and service principals all work.

### Blob Storage, Azure OpenAI, Cosmos DB, Service Bus and Redis

```python
from agenticaiframework.enterprise import AzureAdapter

az = AzureAdapter(
    storage_container="agent-artifacts",
    cosmos_database="vectors",
    queue_name="agent-jobs",
    llm_model="gpt-4o",
)

# Blob Storage
await az.storage.upload("prompts/system.md", system_prompt)
print(await az.storage.exists("prompts/system.md"))

# Azure OpenAI
text = await az.llm.generate("Draft a release note for v2.1.", temperature=0.3)
embedding = (await az.llm.embed("release note"))[0]

# Cosmos DB as a vector store
await az.vectordb.upsert("doc-1", embedding, metadata={"source": "release-notes"})
hits = await az.vectordb.search(embedding, top_k=5)

# Service Bus
message_id = await az.queue.send({"job": "summarise", "doc": "doc-1"})
for msg in await az.queue.receive(max_messages=10):
    ...
    await az.queue.acknowledge(msg["id"])

# Azure Cache for Redis
await az.cache.set("last_run", "2026-09-04T09:00:00Z", ttl=3600)
print(await az.cache.get("last_run"))
```

The `AzureOpenAILLM` adapter defaults to API version `2024-02-01`. Point it at a different deployment with `AzureOpenAILLM(endpoint=..., default_model="<deployment-name>")`.

### Key Vault as a secret backend

```python
from agenticaiframework.enterprise import AzureKeyVaultBackend, SecretManager

backend = AzureKeyVaultBackend("https://my-vault.vault.azure.net")
secrets = SecretManager(backend=backend)

openai_key = await secrets.get("openai-api-key")
```

Requires `azure-identity` and `azure-keyvault-secrets`. Use `EnvironmentBackend` or `InMemoryBackend` in tests.

### Azure DevOps

```python
from agenticaiframework.integrations import AzureDevOpsIntegration
```

Work items, pipelines and pull requests are exposed through the common `BaseIntegration` interface. See [Integration Patterns](integration.md).

### Speech

`AzureSTT` and `AzureTTS` implement the `STTProvider` and `TTSProvider` interfaces used by `SpeechProcessor`. See [Speech Processing](speech.md).

## Google Cloud

### Credentials

| Variable | Used for |
|---|---|
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to a service-account JSON key; used to mint OAuth tokens via JWT when the Google SDKs are absent |
| `GOOGLE_CLOUD_PROJECT` | Project ID for Cloud Storage and Vertex AI (falls back to the key file's `project_id`) |
| `GOOGLE_API_KEY` | Gemini through the public API (`GoogleProvider` in `agenticaiframework.llms`), not Vertex AI |

### Cloud Storage and Vertex AI

```python
from agenticaiframework.enterprise import GCPAdapter

gcp = GCPAdapter(bucket="agent-artifacts", project="my-project", location="us-central1",
                 llm_model="gemini-1.5-pro")

await gcp.storage.upload("transcripts/call-42.txt", transcript)
files = await gcp.storage.list(prefix="transcripts/")

summary = await gcp.llm.generate("Summarise this call transcript.", max_tokens=400)
vectors = await gcp.llm.embed(["passage one", "passage two"], model="textembedding-gecko@003")
```

Speech-to-Text, Text-to-Speech and Vision OCR use the same service-account credentials through `GoogleSTT`, `GoogleTTS` and the `VisionClient` in `agenticaiframework._internal.clients.gcp_rest`.

## Write a portable service

Because every implementation shares the same abstract base, application code can depend on the interfaces rather than on a cloud.

```python
from agenticaiframework.enterprise import StorageAdapter, LLMAdapter, get_adapter

class ReportService:
    def __init__(self, storage: StorageAdapter, llm: LLMAdapter):
        self.storage = storage
        self.llm = llm

    async def run(self, key: str) -> str:
        source = await self.storage.download(key)
        summary = await self.llm.generate(f"Summarise:\n\n{source}", max_tokens=300)
        await self.storage.upload(key.replace(".md", ".summary.md"), summary)
        return summary

cloud = get_adapter()                       # AWS, Azure or GCP
service = ReportService(cloud.storage, cloud.llm)
```

For tests, implement `StorageAdapter` and `LLMAdapter` in memory; no cloud credentials are needed.

## Deploying agents to cloud runtimes

The adapters cover data-plane access. For running the agents themselves, see:

- [Deployment](deployment.md) - containers, Kubernetes manifests, serverless packaging and environment configuration for AWS, Azure and Google Cloud
- [Infrastructure](infrastructure.md) - `MultiRegionManager`, `TenantManager` and `ServerlessExecutor`
- [Enterprise Features](enterprise.md) - secrets, RBAC, rate limiting, blue/green and canary rollout

## Related reference

- [`agenticaiframework.enterprise.adapters`](reference/agenticaiframework/enterprise/adapters.md)
- [`agenticaiframework.enterprise.secrets`](reference/agenticaiframework/enterprise/secrets.md)
- [`agenticaiframework.integrations`](reference/agenticaiframework/integrations/index.md)
- [`agenticaiframework.speech`](reference/agenticaiframework/speech/index.md)
