"""
Knowledge retrieval system with bounded LRU cache and thread safety.
"""

from __future__ import annotations

import logging
import threading
from collections import OrderedDict
from typing import Any, Callable

from .exceptions import KnowledgeRetrievalError  # noqa: F401 - exported for library users

logger = logging.getLogger(__name__)

_MAX_CACHE_ENTRIES = 1024


class KnowledgeRetriever:
    """Thread-safe knowledge retriever with bounded LRU cache."""

    def __init__(self, max_cache_size: int = _MAX_CACHE_ENTRIES) -> None:
        self._lock = threading.Lock()
        self.sources: dict[str, Callable[[str], list[dict[str, Any]]]] = {}
        self._cache: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
        self._max_cache = max_cache_size
        self.knowledge_base: dict[str, str] = {}

    def register_source(
        self,
        name: str,
        retrieval_fn: Callable[[str], list[dict[str, Any]]],
    ) -> None:
        with self._lock:
            self.sources[name] = retrieval_fn
        logger.info("[KnowledgeRetriever] Registered source '%s'", name)

    def add_knowledge(self, key: str, content: str) -> None:
        """Add knowledge to the internal knowledge base."""
        with self._lock:
            self.knowledge_base[key] = content
        logger.info("[KnowledgeRetriever] Added knowledge for key '%s'", key)

    def retrieve(self, query: str, use_cache: bool = True) -> list[dict[str, Any]]:
        with self._lock:
            if use_cache and query in self._cache:
                self._cache.move_to_end(query)
                logger.debug("[KnowledgeRetriever] Cache hit for '%s'", query)
                return self._cache[query]

        results: list[dict[str, Any]] = []

        # Search internal knowledge base
        q = query.lower() if query else ""
        with self._lock:
            kb_snapshot = dict(self.knowledge_base)
        for key, content in kb_snapshot.items():
            if not query or q in key.lower() or q in content.lower():
                results.append({"source": "knowledge_base", "key": key, "content": content})

        with self._lock:
            sources_snapshot = dict(self.sources)
        for name, fn in sources_snapshot.items():
            try:
                source_results = fn(query)
                results.extend(source_results)
                logger.info("[KnowledgeRetriever] Retrieved %d items from '%s'", len(source_results), name)
            except (TypeError, ValueError, KeyError, ConnectionError) as e:
                logger.warning("Knowledge retrieval from '%s' failed: %s", name, e)
            except Exception:  # noqa: BLE001
                logger.exception("Unexpected error in knowledge source '%s'", name)

        # LRU cache with bounded size
        with self._lock:
            self._cache[query] = results
            self._cache.move_to_end(query)
            while len(self._cache) > self._max_cache:
                self._cache.popitem(last=False)

        return results

    @property
    def cache(self) -> dict[str, Any]:
        """Backward-compatible cache accessor."""
        return dict(self._cache)

    def clear_cache(self) -> None:
        with self._lock:
            self._cache.clear()
        logger.info("[KnowledgeRetriever] Cache cleared")
