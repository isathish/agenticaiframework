"""Pure-Python Cohere REST client (stdlib-only).

Implements the small subset used by ``agenticaiframework.knowledge.builder``:

* ``embed(texts, model, input_type)`` → ``List[List[float]]``
* ``rerank(query, documents, model, top_n)`` → ``List[Dict]``
* ``generate(prompt, model, ...)`` → ``str``

API reference: https://docs.cohere.com/reference
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .. import http as _http


@dataclass
class CohereClient:
    api_key: Optional[str] = None
    base_url: str = "https://api.cohere.com"
    timeout: float = 60.0
    _client: _http.Client = field(init=False, repr=False)

    def __post_init__(self) -> None:
        key = self.api_key or os.environ.get("COHERE_API_KEY")
        if not key:
            raise RuntimeError("COHERE_API_KEY is required")
        self._client = _http.Client(
            base_url=self.base_url.rstrip("/"),
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            timeout=self.timeout,
        )

    def embed(
        self,
        texts: List[str],
        *,
        model: str = "embed-english-v3.0",
        input_type: str = "search_document",
        embedding_types: Optional[List[str]] = None,
    ) -> List[List[float]]:
        payload: Dict[str, Any] = {
            "texts": list(texts),
            "model": model,
            "input_type": input_type,
        }
        if embedding_types:
            payload["embedding_types"] = embedding_types
        resp = self._client.post("/v1/embed", json=payload).raise_for_status()
        data = resp.json()
        # v1: returns {embeddings: [[...], ...]} or {embeddings: {float: [...]}}
        emb = data.get("embeddings")
        if isinstance(emb, dict):
            return emb.get("float", [])
        return emb or []

    def rerank(
        self,
        query: str,
        documents: List[str],
        *,
        model: str = "rerank-english-v3.0",
        top_n: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        payload: Dict[str, Any] = {
            "query": query,
            "documents": list(documents),
            "model": model,
        }
        if top_n is not None:
            payload["top_n"] = top_n
        resp = self._client.post("/v1/rerank", json=payload).raise_for_status()
        return resp.json().get("results", [])

    def generate(
        self,
        prompt: str,
        *,
        model: str = "command-r",
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> str:
        payload = {
            "message": prompt,
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        resp = self._client.post("/v1/chat", json=payload).raise_for_status()
        data = resp.json()
        return data.get("text", "")


__all__ = ["CohereClient"]
