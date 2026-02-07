---
title: Knowledge
description: Knowledge retrieval with LRU caching, pluggable sources, and thread-safe operations
tags:
  - knowledge
  - retrieval
  - caching
  - rag
---

# :material-book-open-variant: Knowledge

**Pluggable knowledge retrieval with LRU caching and thread-safe operations.**

Register custom retrieval functions, query them by name, and benefit from
automatic caching via an `OrderedDict`-based LRU cache.

!!! tip "v2.0 Improvements"
    KnowledgeRetriever now uses an `OrderedDict` LRU cache (max 1024 entries),
    `threading.Lock` for thread safety, and structured logging.

---

## Overview

The `KnowledgeRetriever` class provides a unified interface for knowledge
retrieval across multiple sources:

| Feature | Description |
|---------|-------------|
| **Pluggable sources** | Register any callable as a retrieval function |
| **LRU cache** | Automatic caching with bounded `OrderedDict` (max 1024) |
| **Direct storage** | Add key-value knowledge entries directly |
| **Thread safety** | All operations protected by `threading.Lock` |

---

## Quick Start

```python
from agenticaiframework import KnowledgeRetriever

retriever = KnowledgeRetriever()

# Register a retrieval source
def search_docs(query: str) -> str:
    # Your retrieval logic (vector DB, API, file search, etc.)
    return f"Result for: {query}"

retriever.register_source("docs", search_docs)

# Query the source
result = retriever.retrieve("docs", "How do I configure agents?")

# Results are cached automatically — second call is instant
cached = retriever.retrieve("docs", "How do I configure agents?")
```

---

## Registering Sources

A source is any callable that accepts a query string and returns a result:

```python
# Simple function
def search_wiki(query: str) -> str:
    return wiki_api.search(query)

retriever.register_source("wiki", search_wiki)

# Lambda
retriever.register_source("echo", lambda q: f"Echo: {q}")

# Class method
class VectorDB:
    def search(self, query: str) -> list[dict]:
        return self.index.query(query, top_k=5)

db = VectorDB()
retriever.register_source("vectors", db.search)
```

---

## Direct Knowledge Storage

Add static knowledge entries directly without a retrieval function:

```python
retriever.add_knowledge("company_name", "Acme Corp")
retriever.add_knowledge("max_tokens", "4096")
```

---

## LRU Cache

The cache uses `OrderedDict` with a maximum of 1024 entries. When the limit is
reached, the least recently used entry is evicted.

```python
# Check cache contents
cache = retriever.cache

# Clear the cache (e.g. after updating source data)
retriever.clear_cache()
```

!!! info "Cache Key"
    The cache key is `(source_name, query)` — so the same query to different
    sources produces separate cache entries.

---

## Bypassing the Cache

Pass `use_cache=False` to skip the cache for a specific query:

```python
# Always fetch fresh data
fresh = retriever.retrieve("docs", "latest updates", use_cache=False)
```

---

## API Reference

### `KnowledgeRetriever`

#### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `register_source(name, retrieval_fn)` | `None` | Register a named retrieval function |
| `add_knowledge(key, content)` | `None` | Add a static knowledge entry |
| `retrieve(source, query, use_cache=True)` | `Any` | Query a source with optional caching |
| `clear_cache()` | `None` | Clear the LRU cache |

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| `cache` | `OrderedDict` | Current cache contents |

#### Internal

| Attribute | Type | Description |
|-----------|------|-------------|
| `_sources` | `dict` | Registered retrieval functions |
| `_knowledge` | `dict` | Direct knowledge entries |
| `_cache` | `OrderedDict` | LRU cache (max 1024) |
| `_lock` | `threading.Lock` | Thread synchronisation |

---

## Integration with RAG

Combine KnowledgeRetriever with an LLM for retrieval-augmented generation:

```python
from agenticaiframework import KnowledgeRetriever

retriever = KnowledgeRetriever()
retriever.register_source("docs", doc_search_fn)

# Retrieve context
context = retriever.retrieve("docs", user_question)

# Build prompt with context
prompt = f"Context: {context}\n\nQuestion: {user_question}\nAnswer:"
```

---

## Best Practices

!!! success "Do"
    - Register sources during application startup.
    - Use `clear_cache()` when underlying data changes.
    - Use `use_cache=False` for time-sensitive queries.
    - Keep retrieval functions fast — they block the calling thread.

!!! danger "Don't"
    - Register sources with the same name (the second overwrites the first).
    - Store large binary blobs via `add_knowledge()` — use object storage instead.
    - Forget to call `clear_cache()` after data updates.

---

## Related Documentation

- [Memory](memory.md) — persistent agent memory
- [Agents](agents.md) — agent lifecycle
- [Tools](tools.md) — tool definitions for agents
- [Hub](hub.md) — component registry
