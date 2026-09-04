---
title: Installation and Usage
description: Install AgenticAI Framework with pip, uv or poetry, choose extras, set environment variables, add optional third-party packages and verify the installation.
tags:
  - getting-started
---

# Installation and Usage

`agenticaiframework` is a single wheel with no runtime dependencies. This page covers supported Python versions, the three extras defined in `pyproject.toml`, the environment variables the framework reads, the optional third-party packages that unlock extra backends, running from a source checkout, and how to verify an installation. For a guided tour of the API, start with the [Quick Start](quick-start.md).

## Requirements

| Requirement | Value |
|---|---|
| Python | 3.10, 3.11, 3.12 or 3.13 (`requires-python = ">=3.10"`) |
| Operating system | Any platform CPython runs on |
| Runtime dependencies | None. `pip install agenticaiframework` installs one package |
| Network | Only needed when an agent calls a hosted model or a remote tool |

## Install

=== "pip"

    ```bash
    python -m venv .venv && source .venv/bin/activate
    pip install agenticaiframework
    ```

=== "uv"

    ```bash
    uv venv && source .venv/bin/activate
    uv pip install agenticaiframework
    # or, inside a uv project:
    uv add agenticaiframework
    ```

=== "poetry"

    ```bash
    poetry add agenticaiframework
    ```

Upgrade with `pip install -U agenticaiframework`. Pin a version in `requirements.txt` or `pyproject.toml` the same way as any other package; the project follows semantic versioning and the [changelog](changelog.md) lists breaking changes per release.

## Extras

Three extras are defined. None of them is needed to run agents; they are for contributors and for building the documentation.

| Extra | Installs | Use when |
|---|---|---|
| `dev` | pytest, pytest-cov, pytest-asyncio, pytest-timeout, pytest-xdist, ruff, mypy, black, isort, pre-commit | Running the test suite, linting, type checking |
| `docs` | mkdocs, mkdocs-material, mkdocstrings[python], pymdown-extensions, git-revision-date plugin, minify plugin, glightbox | Building this documentation site |
| `all` | `dev` + `docs` | Full contributor setup |

```bash
pip install "agenticaiframework[dev]"
pip install "agenticaiframework[docs]"
pip install "agenticaiframework[all]"
```

There are no feature extras such as `[llm]` or `[memory]`. Provider clients, vector stores and protocol implementations ship in the base package on the standard library; the packages in [Optional third-party packages](#optional-third-party-packages) are installed separately if you want them.

## Verify the installation

```bash
python -c "import agenticaiframework as aaf; print(aaf.__version__)"
```

A slightly longer check that exercises the lazy export table, the tool registry and an offline agent run:

```python
import agenticaiframework as aaf
from agenticaiframework.tools import ToolRegistry

print(aaf.__version__, len(aaf.__all__))          # e.g. 3.0.11 430

registry = ToolRegistry()
print(len(registry.discover()))                    # 46 built-in tools

agent = aaf.Agent.quick("Probe")
output = agent.invoke("ping")
print(output.status, output.error)                 # ERROR "LLM generation failed" without an API key
```

The last two lines confirm that the agent pipeline runs end to end even without a provider; with a key set, `output.status` becomes `AgentStatus.SUCCESS`.

## Environment variables

`aaf.configure()` (with the default `from_environment=True`) and `LLMManager.from_environment()` read the following variables. Everything can also be set in code; see [Configuration](CONFIGURATION.md) and the [Configuration reference](configuration-reference.md).

### Provider credentials

| Variable | Read by | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | `LLMManager.from_environment`, `OpenAIProvider.from_env` | Registers the OpenAI provider |
| `OPENAI_API_BASE` | `OpenAIProvider.from_env` | Base URL for OpenAI-compatible servers (Azure OpenAI, Ollama, vLLM, LM Studio) |
| `OPENAI_MODEL`, `OPENAI_ORGANIZATION`, `OPENAI_TIMEOUT`, `OPENAI_MAX_RETRIES` | `OpenAIProvider.from_env` | Default model, organisation header, request timeout in seconds, retry count |
| `ANTHROPIC_API_KEY` | `LLMManager.from_environment`, `AnthropicProvider.from_env` | Registers the Anthropic provider |
| `ANTHROPIC_API_BASE`, `ANTHROPIC_MODEL`, `ANTHROPIC_TIMEOUT`, `ANTHROPIC_MAX_RETRIES` | `AnthropicProvider.from_env` | Base URL, default model, timeout, retries |
| `GOOGLE_API_KEY` or `GEMINI_API_KEY` | `LLMManager.from_environment`, `GoogleProvider.from_env` | Registers the Google Gemini provider |
| `GEMINI_MODEL`, `GEMINI_TIMEOUT` | `GoogleProvider.from_env` | Default model, timeout |
| `COHERE_API_KEY` | `KnowledgeBuilder` Cohere embeddings, `_internal.clients.cohere_rest` | Cohere embeddings and chat client |

The first provider registered becomes active; the others form the fallback chain in the order OpenAI, Anthropic, Google. Pass `provider=` to `aaf.configure()` or `Agent.quick()` to choose a different active provider.

### Framework settings

| Variable | Default | `FrameworkConfig` field |
|---|---|---|
| `AGENTIC_DEFAULT_PROVIDER` | `auto` | `default_provider` |
| `AGENTIC_DEFAULT_MODEL` | unset | `default_model` |
| `AGENTIC_TEMPERATURE` | `0.7` | `temperature` |
| `AGENTIC_MAX_RETRIES` | `3` | `max_retries` |
| `AGENTIC_GUARDRAILS` | `true` | `guardrails_enabled` |
| `AGENTIC_GUARDRAILS_PRESET` | `minimal` | `guardrails_preset` (`minimal`, `standard`, `strict`) |
| `AGENTIC_TRACING` | `true` | `tracing_enabled` |
| `AGENTIC_TRACE_SAMPLING` | `1.0` | `trace_sampling_rate` |
| `AGENTIC_AUTO_DISCOVER_TOOLS` | `true` | `auto_discover_tools` |
| `AGENTIC_MAX_CONTEXT_TOKENS` | `4096` | `max_context_tokens` |
| `AGENTIC_LOG_LEVEL` | `INFO` | `log_level` |
| `AGENTIC_VERBOSE` | `false` | `verbose` |

```python
import agenticaiframework as aaf

config = aaf.get_config()          # FrameworkConfig built from the variables above
print(config.default_provider, config.guardrails_preset, config.log_level)
```

Keys are read once when the configuration is first built. Set them before importing the framework, or call `aaf.configure(...)` explicitly.

## Optional third-party packages

The framework imports these packages inside `try: import X except ImportError: X = None` blocks and only uses them when present. Each row states which module imports the package and what becomes available. Nothing here is required for agents, teams, memory, guardrails, evaluation or tracing.

| Package | Imported by | Unlocks |
|---|---|---|
| `openai` | `tools/ai_ml/generation_tools.py`, `tools/ai_ml/rag_tools.py`, `tools/database/sql_tools.py`, `tools/file_document/pdf_tools.py`, `knowledge/builder.py`, `enterprise/adapters.py` | Official SDK path for the DALL-E, RAG, text-to-SQL and PDF tools and for OpenAI/Azure OpenAI embeddings in `KnowledgeBuilder`. The `LLMManager` providers themselves use the standard-library client in `_internal/clients/openai_rest.py` and do not need this package |
| `cohere` | `knowledge/builder.py` | Cohere embeddings through the official SDK (a REST fallback exists in `_internal/clients/cohere_rest.py`) |
| `redis` | `state/manager.py`, `enterprise/cache.py`, `enterprise/rate_limiter.py`, `enterprise/health.py`, `enterprise/adapters.py` | `RedisBackend` for state stores, Redis-backed cache, distributed rate limiting and health checks |
| `chromadb` | `knowledge/vector_db.py` | Chroma vector store for `KnowledgeBuilder` |
| `qdrant-client` | `knowledge/vector_db.py`, `tools/database/vector_tools.py` | Qdrant vector store and the Qdrant search tool |
| `weaviate-client` | `tools/database/vector_tools.py` | Weaviate search tool |
| `pinecone` | `knowledge/vector_db.py` | Pinecone vector store |
| `pymongo` | `tools/database/vector_tools.py` | MongoDB Atlas vector search tool |
| `psycopg2` | `tools/database/sql_tools.py` | PostgreSQL access from the SQL tools (the framework also ships a native wire-protocol client in `_internal/clients/postgres_wire.py`) |
| `mysql-connector-python` | `tools/database/sql_tools.py`, `tools/database/snowflake_tools.py` | MySQL access from the SQL tools (native fallback in `_internal/clients/mysql_wire.py`) |
| `snowflake-connector-python` | `tools/database/snowflake_tools.py` | Snowflake query tool |
| `pypdf` or `PyPDF2` | `knowledge/builder.py`, `tools/file_document/pdf_tools.py`, `tools/file_document/directory_tools.py` | Third-party PDF text extraction (fallback: `_internal/pdf.py`) |
| `python-docx` | `knowledge/builder.py`, `tools/file_document/document_tools.py`, `tools/file_document/directory_tools.py` | DOCX loading through python-docx (fallback: `_internal/docx.py`) |
| `requests`, `httpx`, `aiohttp` | `communication/protocols.py`, `knowledge/builder.py`, `speech/processor.py`, several `enterprise/*` modules | Third-party HTTP clients where present; otherwise `_internal/http.py` is used |
| `paho-mqtt` | `communication/protocols.py` | `MQTTProtocol` over the paho client (fallback: `_internal/mqtt.py`) |
| `boto3` | `enterprise/adapters.py`, `tools/file_document/ocr_tools.py` | S3 adapter and AWS Textract OCR through the SDK (S3 also works through the SigV4 client in `_internal/clients/s3_rest.py`) |
| `azure-storage-blob`, `azure-servicebus`, `azure-cosmos`, `azure-identity`, `azure-keyvault-secrets` | `enterprise/adapters.py`, `enterprise/secrets.py` | Azure Blob, Service Bus, Cosmos DB adapters and Key Vault secrets through the Azure SDKs |
| `google-cloud-speech`, `google-cloud-texttospeech`, `google-cloud-vision`, `google-cloud-storage` | `speech/processor.py`, `tools/file_document/ocr_tools.py`, `enterprise/adapters.py` | Google speech, OCR and storage through the Google SDKs |
| `langchain`, `llama-index` | `tools/ai_ml/framework_tools.py` | `LangChainTool` and `LlamaIndexTool` bridges |

Packages that are **not** used even if installed: `anthropic` and `google-generativeai` (the Anthropic and Gemini providers are implemented on `_internal/clients/anthropic_rest.py` and `gemini_rest.py`), `opentelemetry-*` (the OTLP exporter in `enterprise/tracing_otel.py` posts OTLP JSON over HTTP itself), `psycopg` v3, `prometheus-client` and `datadog` (the exporters format the wire protocols directly).

Install only what your deployment needs, for example:

```bash
pip install agenticaiframework redis chromadb
```

## Import surface

Everything commonly used is exported from the top-level package and loaded on first access:

```python
import agenticaiframework as aaf

agent = aaf.Agent.quick("Assistant")
task = aaf.Task(name="double", objective="Double a number", executor=lambda x: x * 2, inputs={"x": 21})
memory = aaf.MemoryManager()
monitor = aaf.MonitoringSystem()
retriever = aaf.KnowledgeRetriever()
print(task.run(), aaf.__version__)
```

Sub-packages can be imported directly when you want a narrower import, for example `from agenticaiframework.guardrails import GuardrailManager` or `from agenticaiframework.enterprise.circuit_breaker import CircuitBreaker`. Anything under `agenticaiframework._internal` is an implementation detail and may change between minor versions.

## Running from source

```bash
git clone https://github.com/isathish/agenticaiframework.git
cd agenticaiframework
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m pytest tests -x -o addopts="" -q     # 2,028 tests, no network needed
```

`-o addopts=""` clears the `addopts` set in `pyproject.toml` so the summary line is printed once. Lint and type-check with `ruff check agenticaiframework tests` and `mypy agenticaiframework`. To build the documentation, `pip install -e ".[docs]"` and run `mkdocs serve`. See [Testing](TESTING.md) and [Contributing](contributing.md).

## Logging

The framework logs through the standard `logging` module under the `agenticaiframework` logger hierarchy. `AGENTIC_LOG_LEVEL` or `aaf.configure(log_level=...)` sets the level; attach handlers as you would for any library:

```python
import logging
import agenticaiframework as aaf

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
aaf.configure(log_level="INFO")
logging.getLogger("agenticaiframework.llms").setLevel(logging.WARNING)
```

## Troubleshooting installation

| Symptom | Cause and fix |
|---|---|
| `ModuleNotFoundError: agenticaiframework` | The interpreter running your script is not the one you installed into. Run `python -m pip install agenticaiframework` with the same `python` |
| `output.error == "LLM generation failed"` | No provider key visible to the process. Export `OPENAI_API_KEY` (or another key) before starting Python, or pass `Agent.from_config({"llm": {"provider": ..., "model": ..., "api_key": ...}})` |
| `RuntimeError: COHERE_API_KEY is required` | Cohere embeddings were selected in `KnowledgeBuilder` without a key |
| A vector store or database tool reports the client is unavailable | Install the matching optional package from the table above |
| `pip` resolves a very old version | Your Python is older than 3.10; upgrade the interpreter |

More in [Troubleshooting](TROUBLESHOOTING.md) and the [FAQ](faq.md).

## Related

- [Quick Start](quick-start.md) - ten-minute tutorial
- [Configuration](CONFIGURATION.md) and [Configuration reference](configuration-reference.md)
- [LLM providers](llms.md) - provider classes, model registry, routing
- [Deployment](deployment.md) - containers, serverless, multi-region
- [Testing](TESTING.md) and [Contributing](contributing.md)
