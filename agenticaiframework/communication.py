"""
Communication manager for protocol-based message routing.

Thread-safe protocol registration and message dispatch.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable

from .exceptions import ProtocolError, ProtocolNotFoundError  # noqa: F401 - exported for library users

logger = logging.getLogger(__name__)


class CommunicationManager:
    """Thread-safe communication manager."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.protocols: dict[str, Callable[[Any], Any]] = {}

    def register_protocol(self, name: str, handler_fn: Callable[[Any], Any]) -> None:
        with self._lock:
            self.protocols[name] = handler_fn
        logger.info("[CommunicationManager] Registered protocol '%s'", name)

    def register_handler(self, handler_fn: Callable[[Any], Any], name: str | None = None) -> None:
        """Alternative method for registering handlers."""
        protocol_name = name or f"handler_{len(self.protocols)}"
        self.register_protocol(protocol_name, handler_fn)

    def send(self, protocol: str, data: Any) -> Any:
        with self._lock:
            handler = self.protocols.get(protocol)
        if handler:
            try:
                return handler(data)
            except (TypeError, ValueError, ConnectionError, TimeoutError) as e:
                logger.warning("Protocol '%s' communication failed: %s", protocol, e)
            except Exception:  # noqa: BLE001
                logger.exception("Unexpected error in protocol '%s'", protocol)
        else:
            logger.warning("[CommunicationManager] Protocol '%s' not found", protocol)
        return None

    def list_protocols(self) -> list[str]:
        with self._lock:
            return list(self.protocols.keys())

    def send_message(self, message: Any, protocol: str | None = None) -> Any:
        """Send a message using the specified or first available protocol."""
        if protocol:
            return self.send(protocol, message)
        with self._lock:
            first = next(iter(self.protocols), None)
        if first:
            return self.send(first, message)
        logger.warning("[CommunicationManager] No protocols available")
        return None
