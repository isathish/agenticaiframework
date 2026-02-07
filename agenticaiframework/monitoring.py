"""Monitoring system with thread-safe metrics, bounded event storage, and GC-aware tracking."""

from __future__ import annotations

import gc
import logging
import threading
import time
from collections import deque
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Configurable limits
_MAX_EVENTS = 10_000
_MAX_LOGS = 5_000


class MonitoringSystem:
    """Thread-safe monitoring with bounded storage and GC management."""

    __slots__ = ("_metrics", "_logs", "_events", "_lock")

    def __init__(self, max_events: int = _MAX_EVENTS, max_logs: int = _MAX_LOGS) -> None:
        self._metrics: Dict[str, Any] = {}
        self._logs: deque[str] = deque(maxlen=max_logs)
        self._events: deque[Dict[str, Any]] = deque(maxlen=max_events)
        self._lock = threading.Lock()

    def record_metric(self, name: str, value: Any) -> None:
        with self._lock:
            self._metrics[name] = value
        logger.debug("Metric recorded: %s = %s", name, value)

    def get_metric(self, name: str) -> Any:
        with self._lock:
            return self._metrics.get(name)

    def log_event(self, event_type: str, details: Dict[str, Any]) -> None:
        event = {"type": event_type, "details": details, "timestamp": time.time()}
        with self._lock:
            self._events.append(event)
        logger.debug("Event logged: %s", event_type)

    def get_events(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._events)

    def log_message(self, message: str) -> None:
        timestamped = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}"
        with self._lock:
            self._logs.append(timestamped)
        logger.info("%s", message)

    def get_logs(self) -> List[str]:
        with self._lock:
            return list(self._logs)

    def get_metrics(self) -> Dict[str, Any]:
        """Get a snapshot of all recorded metrics."""
        with self._lock:
            return self._metrics.copy()

    def get_gc_stats(self) -> Dict[str, Any]:
        """Return garbage-collection statistics for diagnostics."""
        counts = gc.get_count()
        return {
            "gc_gen0": counts[0],
            "gc_gen1": counts[1],
            "gc_gen2": counts[2],
            "gc_threshold": gc.get_threshold(),
            "gc_enabled": gc.isenabled(),
        }

    def force_gc(self) -> int:
        """Trigger a full garbage-collection sweep; return objects collected."""
        collected = gc.collect()
        logger.info("Forced GC collected %d objects", collected)
        return collected

    def clear(self) -> None:
        """Clear all metrics, events, and logs."""
        with self._lock:
            self._metrics.clear()
            self._events.clear()
            self._logs.clear()
        logger.info("MonitoringSystem cleared")
