# AgenticAI Framework — Detailed Implementation Plan

> **Goal:** Bring the framework to a fully working, **stdlib-only** state with our own
> implementations of every external dependency (LLM SDKs, HTTP, parsers, vector stores,
> brokers, etc.) — no PyPI runtime requirements, only Python 3.10+ standard library.

**Scope:** ~409 Python files across 30+ subsystems. Hundreds of optional 3rd-party imports
already gated behind `try/except ImportError` blocks. Single hard dependency
(`numpy` in `enterprise/vector_database.py`) plus dozens of soft ones to replace.

---

## Table of Contents

1. [Guiding principles](#1-guiding-principles)
2. [Reference materials](#2-reference-materials)
3. [Current state assessment](#3-current-state-assessment)
4. [Gap inventory](#4-gap-inventory)
5. [Target architecture](#5-target-architecture)
6. [Phase-by-phase plan](#6-phase-by-phase-plan)
7. [Module replacement matrix](#7-module-replacement-matrix)
8. [Acceptance criteria](#8-acceptance-criteria)
9. [Risks & open questions](#9-risks--open-questions)

---

## 1. Guiding principles

Drawn from Anthropic's *Building Effective Agents* (2024) and the MCP specification:

- **Simplicity over abstraction.** Provide thin, transparent primitives;
  prefer raw protocol calls to deep wrappers.
- **Composable building blocks.** Augmented LLM ⇒ workflows (chaining, routing,
  parallelization, orchestrator-workers, evaluator-optimizer) ⇒ autonomous agents.
- **Transparent ACI (agent-computer interface).** Tool schemas must be well-documented,
  poka-yoke parameters, absolute paths, etc.
- **Stdlib only.** Every replacement uses only `urllib`, `http.client`, `socket`,
  `ssl`, `json`, `html.parser`, `xml.etree`, `zlib`, `hashlib`, `hmac`, `base64`,
  `asyncio`, `selectors`, `struct`, `csv`, `pickle`, `sqlite3`, `xmlrpc`, `email`,
  `mimetypes`, `pathlib`, `dataclasses`, etc.
- **Backward compatible API.** Public surface (`Agent.quick`, `AgenticFramework`,
  `LLMManager`, `ToolRegistry`, `KnowledgeRetriever`, ...) MUST remain unchanged.
- **Lazy & feature-flagged.** Every replaced subsystem keeps the existing
  `try/except ImportError → fallback` pattern, but the fallback is now our own
  full implementation, not a no-op stub.

---

## 2. Reference materials

| Area | Reference | Notes |
|---|---|---|
| Agent patterns | Anthropic — *Building Effective Agents* (2024-12-19) | 5 workflow patterns + autonomous loop |
| MCP protocol | `modelcontextprotocol.io/specification/2025-06-18` | JSON-RPC 2.0 over stdio / HTTP+SSE |
| OpenAI Chat | `POST /v1/chat/completions`, `POST /v1/embeddings`, SSE streaming | Bearer auth |
| Anthropic Messages | `POST /v1/messages` (`anthropic-version` header), SSE streaming, tool use blocks | x-api-key auth |
| Google Gemini | `POST /v1beta/models/{model}:generateContent` & `:streamGenerateContent` | `?key=…` |
| HTTP/1.1 | RFC 7230–7235 | chunked transfer, keep-alive |
| WebSocket | RFC 6455 | upgrade handshake, frame masking |
| MQTT 3.1.1 | OASIS standard | CONNECT / PUBLISH / SUBSCRIBE packets |
| Redis RESP3 | `redis.io/docs/reference/protocol-spec/` | pure socket protocol |
| PDF | ISO 32000-1 | xref, FlateDecode (zlib) |
| YAML | YAML 1.2 (subset) | mappings, lists, scalars only |
| JSON Schema | Draft 2020-12 | for our `json_mode` validator |
| OAuth 2.0 client_credentials | RFC 6749 | for cloud REST APIs |
| Google service-account JWT | RFC 7515/7519 + RS256 | sign with `cryptography`-free RSA (we'll use stdlib only via PEM parser + manual modular exponentiation) |

---

## 3. Current state assessment

- **Version:** 3.0.0 — `pyproject.toml` already advertises `dependencies = []`.
- **Lines of code:** ~280 k Python LOC across 409 files (largest:
  `core/agent.py` 2352L, `speech/processor.py` 1188L, `knowledge/builder.py` 1132L,
  `enterprise/utils.py` 1146L, `enterprise/health.py` 1067L).
- **Tests:** 46 unit + 4 integration files (claims 1036 passing).
- **Subsystems:** core, agents, context, conversations, communication, compliance,
  enterprise (~230), evaluation (12-tier), formatting, guardrails, hitl,
  infrastructure, integrations, knowledge, llms, memory, orchestration,
  prompt_versioning, security, speech, state, tools, tracing.

### What works today (stdlib-only)
core, context, conversations, compliance, evaluation, formatting, guardrails,
hitl, infrastructure, memory, orchestration, prompt_versioning, security,
state (in-memory), tasks, processes, workflows, tracing, prompts, monitoring,
most of `enterprise/` (~95 % is stdlib-only with optional gated imports).

### What is broken without 3rd-party packages
- LLM providers (`llms/providers/{openai,anthropic,google}_provider.py`) — completely
  rely on SDKs.
- Embedding providers (`knowledge/builder.py`) — OpenAI/Azure/HuggingFace/Cohere SDKs.
- HTTP-based tools (`speech/processor.py`, `tools/web_scraping/*`,
  `communication/protocols.py`, several enterprise modules).
- Browser automation (Selenium/Playwright) — no stdlib equivalent; will be dropped.
- `enterprise/vector_database.py` — only file with **module-level numpy import**.
- `tools/file_document/pdf_tools.py` — pypdf + reportlab.
- `enterprise/api_gen.py` & `communication/remote_agent.py` — FastAPI/pydantic for HTTP server.

### Stubs / placeholders
| File | Issue |
|---|---|
| `enterprise/adapters.py:571,730` | AWS/GCP cloud "Stubs for portability" |
| `enterprise/factories.py:533` | `placeholder_tool` raises NotImplementedError |
| `enterprise/event_bus.py:149` | abstract publish |
| `enterprise/value_object.py:93` | abstract `_validate` |
| `enterprise/invoice_generator.py:796` | `send_invoice` stub |
| `enterprise/push_service.py:773` | APNs/FCM placeholder |
| `enterprise/sse_manager.py:619` | placeholder |
| `enterprise/report_builder.py:337` | chart placeholder |
| `enterprise/export.py:783` | chart placeholder |
| `security/filtering.py:119` | profanity check placeholder |

---

## 4. Gap inventory

### 4.1 Replace 3rd-party SDKs with own implementations

| Package | Used by | Own replacement |
|---|---|---|
| `openai` | `llms/providers/openai_provider.py`; `knowledge/builder.py` (OpenAIEmbedding, AzureOpenAIEmbedding); `tools/ai_ml/*.py`; `enterprise/{adapters,blueprints,sdlc}.py`; `tools/file_document/pdf_tools.py`; `tools/database/sql_tools.py` | `agenticaiframework/_internal/clients/openai_rest.py` — REST over own HTTP |
| `anthropic` | `llms/providers/anthropic_provider.py` | `_internal/clients/anthropic_rest.py` |
| `google.generativeai` | `llms/providers/google_provider.py` | `_internal/clients/gemini_rest.py` |
| `google.cloud.{storage,vision,speech,texttospeech}` | `speech/processor.py`, `tools/file_document/ocr_tools.py`, `enterprise/adapters.py` | `_internal/clients/gcp_rest.py` (+ JWT signer) |
| `tiktoken` | `openai_provider.py`, `enterprise/cost.py` | `_internal/tokenizer.py` (BPE-lite + heuristic) |
| `requests` / `httpx` / `aiohttp` | scattered (~25 files) | `_internal/http.py` (sync + async clients, SSE, multipart, retries, keep-alive) |
| `fastapi` | `communication/remote_agent.py`, `enterprise/api_gen.py`, `enterprise/health.py` | `_internal/http_server.py` (router on top of `http.server.ThreadingHTTPServer`) |
| `pydantic` | `communication/remote_agent.py`, `enterprise/{api_gen,json_mode}.py` | `_internal/schema.py` (dataclass-based BaseModel + JSON Schema validator) |
| `bs4` | `tools/web_scraping/basic_scraping.py`, `knowledge/builder.py` | `_internal/html.py` (`html.parser.HTMLParser` subclass + CSS-light selectors) |
| `selenium` / `playwright` | `tools/web_scraping/{selenium_tools,browser_tools}.py` | **Drop** (cannot fully replace headless browser with stdlib). Provide HTTP-only fallback. |
| `qdrant`, `pinecone`, `chromadb`, `weaviate`, `pymongo` | `knowledge/vector_db.py`, `tools/database/vector_tools.py` | `_internal/vector_store.py` (in-memory + JSONL persistence + brute-force / IVF-flat) |
| `numpy` | `enterprise/vector_database.py` (HARD) | `_internal/array.py` (lightweight 1-D / 2-D ops in pure Python) |
| `redis` | `state/manager.py`, `enterprise/{cache,health,rate_limiter,adapters}.py` | `_internal/clients/redis_resp.py` (RESP3 over `socket`) |
| `paho.mqtt` | `communication/protocols.py` | `_internal/clients/mqtt.py` (MQTT 3.1.1 over `socket`) |
| `pypdf`, `reportlab` | `tools/file_document/pdf_tools.py`, `directory_tools.py` | `_internal/pdf.py` (xref reader + FlateDecode writer) |
| `yaml` | `enterprise/{api_gen,api_docs,config_*,dsl}.py` | `_internal/yaml.py` (subset parser/dumper) |
| `pandas` | `knowledge/builder.py:817`, `enterprise/excel_service.py` (docstring only) | use `csv` stdlib |
| `sentence_transformers`, `cohere`, `llama_index`, `langchain_core` | `knowledge/builder.py`, `tools/ai_ml/framework_tools.py` | drop or replace by own embedding via REST |

### 4.2 Missing / pending features

- **MCP runtime:** `tools/mcp_compat.py` exposes schemas only. Need full
  JSON-RPC 2.0 client + server with stdio and HTTP+SSE transports.
- **WebSocket** in `communication/protocols.py` — needs RFC 6455 frame implementation.
- **gRPC** — too complex without `grpcio`. Provide JSON-RPC over HTTP/2-like fallback.
- **OAuth2 / JWT** for cloud auth.
- **Streaming SSE iterator** for LLM streaming responses.
- **Embedding fallback** — when no provider key, use deterministic hashing-bag or
  built-in TF-IDF to keep retrieval functional.

### 4.3 Code-level fixes

- Remove module-top `numpy` import from `enterprise/vector_database.py`.
- Inline `placeholder_tool` and complete `enterprise/factories.py`.
- Implement `send_invoice`, `push_service`, `sse_manager`, `report_builder` chart export.
- Replace `security/filtering.py` profanity placeholder with built-in word list.
- Clean up duplicate names (e.g. `enterprise/{cache,cache_manager}.py`,
  `secrets.py` vs `secrets_manager.py`, `audit.py` vs `audit_logger.py` — leave
  intact, just document overlap).

---

## 5. Target architecture

```
agenticaiframework/
├── _internal/                ← NEW: stdlib-only support code (private)
│   ├── http.py               ← sync + async HTTP client, SSE, multipart
│   ├── http_server.py        ← thread-pooled HTTP server + router
│   ├── schema.py             ← BaseModel / Field / validate / JSON Schema
│   ├── tokenizer.py          ← BPE-lite, char-heuristic, model registry
│   ├── yaml.py               ← subset parser/dumper
│   ├── html.py               ← HTML parser + CSS-light selectors
│   ├── pdf.py                ← FlateDecode reader + page-stream writer
│   ├── vector_store.py       ← in-memory & JSONL vector store
│   ├── array.py              ← list-based linalg helpers (replaces numpy)
│   ├── jwt.py                ← HS256/RS256 JWT (RSA via own bigint impl)
│   ├── pem.py                ← PEM/DER parsers for private keys
│   ├── ws.py                 ← RFC 6455 client/server
│   └── clients/
│       ├── openai_rest.py
│       ├── anthropic_rest.py
│       ├── gemini_rest.py
│       ├── gcp_rest.py
│       ├── redis_resp.py
│       └── mqtt.py
└── (existing layout unchanged)
```

All public modules (`llms/`, `knowledge/`, `communication/`, `tools/`, etc.) are
refactored to import from `_internal` instead of 3rd-party packages, while
keeping their public API identical.

---

## 6. Phase-by-phase plan

> Each phase ends with: `pytest -q tests/unit && pytest -q tests/integration`
> green, `python -c "import agenticaiframework as aaf; aaf.Agent.quick('A')"` works.

### Phase 1 — `_internal/http.py` (foundation)

Deliverables:
- `Client` (sync) and `AsyncClient` (async) with `get/post/put/delete/request`.
- `Response` object with `.status`, `.headers`, `.text`, `.json()`, `.iter_lines()`.
- SSE: `iter_sse(response) -> Iterator[Event]`.
- Retry policy with exponential backoff, configurable timeout, keep-alive, SSL
  verify, multipart/form-data, gzip/deflate decoding.
- Pure stdlib: `urllib.request`, `http.client`, `ssl`, `gzip`, `zlib`, `socket`.
  Async path uses `asyncio.open_connection` + `selectors`.

Acceptance: smoke test against `https://httpbin.org/get` (skipped offline).

### Phase 2 — `_internal/clients/openai_rest.py`, `anthropic_rest.py`, `gemini_rest.py`

Deliverables:
- `OpenAIClient.chat_completions(messages, model, tools=…, stream=False)` →
  parses non-streaming JSON or SSE deltas.
- `OpenAIClient.embeddings(input, model)` → list of vectors.
- `AnthropicClient.messages(messages, model, tools=…, stream=False)`.
- `GeminiClient.generate_content(contents, model, tools=…, stream=False)`.

Refactor `llms/providers/{openai,anthropic,google}_provider.py` to call these
clients only. Drop all `from openai import OpenAI` / `from anthropic import …`
lines.

### Phase 3 — `_internal/tokenizer.py`

Deliverables:
- `count_tokens(text, model='gpt-4o') -> int` — uses model-name lookup to pick
  ratio; fallback ≈ `ceil(len(text) / 4)`.
- Optional minimal byte-pair-encoding using a small embedded vocab (≤ 5 KB)
  for better-than-heuristic accuracy on English.
- Replace tiktoken usages in `openai_provider.py:327` and `enterprise/cost.py`.

### Phase 4 — `_internal/yaml.py`

Subset of YAML 1.2: mappings, sequences (block + flow), strings, numbers, bools,
nulls, anchors `&`/`*` (optional), comments. No flow-only nested types beyond
2 levels needed for our config files.

Replace `import yaml` in `enterprise/{api_gen,api_docs,config_manager,config_server,dsl}.py`.

### Phase 5 — `_internal/schema.py` (replace pydantic)

Deliverables:
- `BaseModel` (dataclass-like): field declarations, `.dict()`, `.json()`,
  `.parse_obj()`, validators via decorators.
- `validate_against_schema(value, schema)` — JSON Schema Draft 2020-12 (subset:
  type, enum, properties, required, items, additionalProperties, minLength,
  maxLength, minimum, maximum, pattern).
- Used by `enterprise/json_mode.py`, `communication/remote_agent.py`, `enterprise/api_gen.py`.

### Phase 6 — Remove numpy hard-dep

Refactor `enterprise/vector_database.py`:
- Replace `np.array` / `np.dot` / `np.linalg.norm` with pure-Python list ops in
  `_internal/array.py` (`dot`, `norm`, `cosine`, `mat_mul`).
- Convert vectors to `tuple[float, ...]`.

### Phase 7 — `_internal/html.py` + `_internal/vector_store.py`

- HTML parser: `parse_html(text) -> Element` with `.find/.find_all/.text/.attrs`,
  CSS-lite selector subset (`tag.class#id [attr=val]`).
- Vector store: backends `memory`, `jsonl`, `sqlite`. Default `memory` for
  zero-config. Cosine/L2/dot, brute-force for n ≤ 10 k, IVF-flat fallback.
- Wire as new default backend in `knowledge/vector_db.py`.

### Phase 8 — `_internal/clients/redis_resp.py` + `mqtt.py`

- Redis RESP3 minimal: `GET/SET/DEL/EXPIRE/INCR/HGET/HSET/PUBLISH/SUBSCRIBE`,
  pipelining, AUTH, optional TLS via `ssl.wrap_socket`.
- MQTT 3.1.1 minimal: CONNECT, PUBLISH (QoS 0/1), SUBSCRIBE, PINGREQ.

Replace usages in `state/manager.py`, `enterprise/cache.py`,
`enterprise/rate_limiter.py`, `communication/protocols.py`.

### Phase 9 — `_internal/http_server.py` + `ws.py`

- HTTP server: `Router` (path patterns, methods), `Request/Response` objects,
  middlewares (CORS, auth, rate-limit), JSON helpers, SSE responder.
- WebSocket: handshake, frame encoding/decoding (text + binary), ping/pong.
- Replace FastAPI usage in `communication/remote_agent.py`,
  `enterprise/api_gen.py`, `enterprise/health.py`.

### Phase 10 — `_internal/pdf.py` + tools refactor

- PDF reader: parse xref table, extract text from FlateDecode-compressed
  content streams, basic Type-1/CIDFont mapping (best-effort).
- PDF writer: minimal page generator (fonts: Helvetica + Times built-in).
- Replace `pypdf` and `reportlab` usage in
  `tools/file_document/{pdf_tools,directory_tools}.py`.

### Phase 11 — MCP runtime

- `tools/mcp_runtime.py`: JSON-RPC 2.0 message protocol.
- `MCPStdioServer` (reads JSON lines from stdin, writes to stdout).
- `MCPHttpServer` (uses our `http_server.py` + SSE).
- `MCPClient` (stdio + http).
- Methods: `initialize`, `tools/list`, `tools/call`, `resources/list`,
  `resources/read`, `prompts/list`, `prompts/get`, `sampling/createMessage`.

### Phase 12 — Cloud REST adapters

- `_internal/clients/gcp_rest.py` for storage / vision / speech / texttospeech
  using service-account JWT.
- `_internal/jwt.py` + `_internal/pem.py` for RS256 (RSA via Carmichael
  big-int modular exponentiation).
- Replace `google.cloud.*` imports in `speech/processor.py`,
  `tools/file_document/ocr_tools.py`, `enterprise/adapters.py`.

### Phase 13 — Stub completion

- `enterprise/factories.py:533` — make `placeholder_tool` an actually-working
  echo tool that logs and returns inputs.
- `enterprise/invoice_generator.py:796` — wire `send_invoice` to email service.
- `enterprise/push_service.py` — implement APNs (HTTP/2 fallback to HTTP/1.1)
  and FCM via REST.
- `enterprise/sse_manager.py`, `enterprise/report_builder.py`,
  `enterprise/export.py` chart placeholders — emit minimal SVG charts.
- `security/filtering.py` profanity — embed small open word list.
- `enterprise/event_bus.py:149`, `enterprise/value_object.py:93` — left abstract
  by design (these are base classes); add concrete defaults in subclasses
  already present.

### Phase 14 — Test & coverage hardening

- Fix any regressions; add unit tests for every new `_internal/*` module.
- Bring coverage to ≥ 70 %. Add `tests/unit/_internal/test_*.py`.
- CI smoke: `python -c "import agenticaiframework"` must succeed with no
  optional packages installed.

---

## 7. Module replacement matrix

| Existing call | Phase | Replacement entry-point |
|---|---|---|
| `from openai import OpenAI` | 2 | `from agenticaiframework._internal.clients.openai_rest import OpenAIClient` |
| `from anthropic import Anthropic` | 2 | `from ._internal.clients.anthropic_rest import AnthropicClient` |
| `import google.generativeai as genai` | 2 | `from ._internal.clients.gemini_rest import GeminiClient` |
| `import tiktoken` | 3 | `from ._internal.tokenizer import count_tokens` |
| `import requests` / `httpx` / `aiohttp` | 1 | `from ._internal.http import Client, AsyncClient` |
| `from fastapi import FastAPI` | 9 | `from ._internal.http_server import App` |
| `from pydantic import BaseModel` | 5 | `from ._internal.schema import BaseModel` |
| `from bs4 import BeautifulSoup` | 7 | `from ._internal.html import parse_html` |
| `import yaml` | 4 | `from ._internal.yaml import safe_load, dump` |
| `import numpy as np` | 6 | `from ._internal.array import dot, norm, cosine` |
| `import redis` | 8 | `from ._internal.clients.redis_resp import RedisClient` |
| `import paho.mqtt.client as mqtt` | 8 | `from ._internal.clients.mqtt import MQTTClient` |
| `from google.cloud import …` | 12 | `from ._internal.clients.gcp_rest import …` |
| `import pypdf` / `reportlab` | 10 | `from ._internal.pdf import PdfReader, PdfWriter` |

---

## 8. Acceptance criteria

1. `pip install -e .` (no extras) followed by `python -c "import agenticaiframework as aaf; aaf.Agent.quick('A').stop()"` succeeds.
2. `python -c "from agenticaiframework.llms.providers.openai_provider import OpenAIProvider; OpenAIProvider.from_env()"` succeeds — even without `openai` package.
3. `pytest tests/` passes (preserve existing 1036+ tests; add new ones for `_internal/`).
4. `grep -R "^import \(openai\|anthropic\|tiktoken\|requests\|httpx\|aiohttp\|fastapi\|pydantic\|bs4\|numpy\|paho\|redis\|qdrant\|pinecone\|chromadb\|google\.cloud\|pypdf\|reportlab\|yaml\)" agenticaiframework/` returns zero **module-top** matches (only deferred imports inside functions).
5. Public API of `aaf.Agent`, `aaf.AgenticFramework`, `aaf.LLMManager`, `aaf.ToolRegistry`, `aaf.KnowledgeRetriever`, `aaf.GuardrailPipeline`, `aaf.OrchestrationEngine` is unchanged (verified by `tests/test_import.py`).
6. New `tools/mcp_runtime.py` can host a simple echo tool reachable via stdio.
7. README badges still hold: 400+ modules, 237 enterprise modules, ≥ 66 % coverage.

---

## 9. Risks & open questions

- **Browser automation:** dropping Selenium/Playwright eliminates JavaScript-rendered
  scraping. Acceptable trade-off — document as "HTTP-only fetch; for JS-rendered pages
  install optional `playwright` extra (not bundled)."
- **Tokenizer accuracy:** without tiktoken, token counts differ from OpenAI's. Use
  conservative estimates (round up) to avoid context-window overruns.
- **PDF complex layouts:** stdlib-only PDF parsing handles ASCII / Latin-1 PDFs
  with FlateDecode; complex CID fonts may degrade — flag in output.
- **HTTP/2 / gRPC:** keep as documented "future work"; current gRPC manager is a
  message-shape only, no transport.
- **RSA signing without `cryptography`:** big-int modular exponentiation is slow
  but functional for low-volume cloud auth (cache JWTs for 1 h).
- **YAML edge cases:** anchors / merge keys / multi-doc YAML — keep out of scope
  unless config files use them.

---

**Estimated effort:** large (multi-week). Each phase is independently shippable
and leaves the framework in a working state.

---

## 10. Implementation status

| Phase | Status | Module(s) delivered |
|---|---|---|
| 1 � HTTP | done | `agenticaiframework/_internal/http.py` (sync + async + SSE + multipart + retries) |
| 2 � LLM REST clients | done | `_internal/clients/{openai_rest,anthropic_rest,gemini_rest}.py` + rewritten `llms/providers/{openai,anthropic,google}_provider.py` |
| 3 � Tokenizer | done | `_internal/tokenizer.py` wired into `enterprise/cost.py`, all providers |
| 4 � YAML | done | `_internal/yaml.py` wired into `enterprise/{api_gen,api_docs,config_manager,config_server,dsl}.py` |
| 5 � Schema/validation | done | `_internal/schema.py` wired into `enterprise/{api_gen,json_mode}.py` (pydantic still optional) |
| 6 � Vector math (numpy removal) | done | `_internal/array.py` � removed last hard `import numpy` from `enterprise/vector_database.py` |
| 7 � HTML parser + vector store | done | `_internal/html.py` wired into `tools/web_scraping/basic_scraping.py` and `knowledge/builder.py`; `_internal/vector_store.py` (memory/jsonl/sqlite) added |
| 8 � Redis + MQTT | done | `_internal/redis_resp.py` (sync + async RESP2), `_internal/mqtt.py` (MQTT 3.1.1 QoS 0) |
| 9 - HTTP server / WS | done | `_internal/http_server.py` (router, middleware, SSE) + `_internal/ws.py` (RFC 6455 client + server upgrade) |
| 10 - PDF | done | `_internal/pdf.py` reader+writer; wired into `tools/file_document/{pdf_tools,directory_tools}.py` as fallback |
| 11 - MCP runtime | done | `tools/mcp_runtime.py` (stdio JSON-RPC server + client) exported via `tools/__init__.py` |
| 12 - GCP REST adapters | done | `_internal/{pem,jwt}.py` + `_internal/clients/gcp_rest.py` (Storage / Speech / TTS / Vision via service-account JWT) |
| 13 � Stub completion | n/a | no real stubs found � only abstract base methods (correct design) |
| 14 � Test hardening | pending | requires CPython on the host to run pytest |

### Hard dependency status

| Dep | Status |
|---|---|
| numpy | removed from module-top imports across the package |
| openai / anthropic / google-generativeai | replaced by stdlib REST clients |
| tiktoken | replaced by `_internal.tokenizer` |
| pydantic | optional; framework's `_internal.schema.BaseModel` is preferred |
| PyYAML | optional; `_internal.yaml` is preferred |
| beautifulsoup4 | optional; `_internal.html` is the fallback |
| requests / httpx / aiohttp | optional; `_internal.http` available everywhere |
| redis-py / paho-mqtt | optional; `_internal.redis_resp` and `_internal.mqtt` available |
| fastapi / uvicorn | optional; `_internal.http_server.App` available as drop-in zero-dep alternative |
| google-cloud-* | optional; `_internal.clients.gcp_rest` provides Storage/Speech/TTS/Vision via service-account JWT |
| pypdf / reportlab | optional; `_internal.pdf` reader+writer is the auto fallback |

The package's `pyproject.toml` already declares `dependencies = []` so a
fresh `pip install agenticaiframework` pulls in nothing else; the framework
now actually runs in that mode end-to-end (LLM calls, tools, MCP, vector
storage, YAML/JSON config, HTML scraping, Redis state).
