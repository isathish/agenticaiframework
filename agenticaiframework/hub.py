"""
Hub – central registry for agents, prompts, tools, guardrails, LLMs, and services.

Thread-safe implementation with proper logging.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

logger = logging.getLogger(__name__)


class Hub:
    """Thread-safe central registry for framework components."""

    _CATEGORIES = frozenset({"agents", "prompts", "tools", "guardrails", "llms", "services"})

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.agents: dict[str, Any] = {}
        self.prompts: dict[str, Any] = {}
        self.tools: dict[str, Any] = {}
        self.guardrails: dict[str, Any] = {}
        self.llms: dict[str, Any] = {}
        self.services: dict[str, Any] = {}

    def register(self, category: str, name: str, item: Any) -> None:
        if category not in self._CATEGORIES:
            logger.warning("[Hub] Invalid category '%s'", category)
            return
        with self._lock:
            getattr(self, category)[name] = item
        logger.info("[Hub] Registered %s '%s'", category[:-1], name)

    def register_service(self, name: str, service: Any) -> None:
        """Register a service in the hub."""
        with self._lock:
            self.services[name] = service
        logger.info("[Hub] Registered service '%s'", name)

    def get_service(self, name: str) -> Any:
        """Get a service by name."""
        with self._lock:
            return self.services.get(name)

    def get(self, category: str, name: str) -> Any:
        if category not in self._CATEGORIES:
            return None
        with self._lock:
            return getattr(self, category).get(name)

    def list_items(self, category: str) -> list[str]:
        if category not in self._CATEGORIES:
            return []
        with self._lock:
            return list(getattr(self, category).keys())

    def remove(self, category: str, name: str) -> None:
        if category not in self._CATEGORIES:
            return
        with self._lock:
            store = getattr(self, category)
            if name in store:
                del store[name]
                logger.info("[Hub] Removed %s '%s'", category[:-1], name)
