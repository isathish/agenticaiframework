"""
Agent Communication Module.

Provides communication management for AI agents.
"""

from typing import Dict, Any, Callable
import logging
import time

logger = logging.getLogger(__name__)


class CommunicationManager:
    """Manages communication protocols for AI agents."""
    
    def __init__(self):
        self.protocols: Dict[str, Callable[[Any], Any]] = {}

    def register_protocol(self, name: str, handler_fn: Callable[[Any], Any]):
        """Register a communication protocol."""
        self.protocols[name] = handler_fn
        self._log(f"Registered communication protocol '{name}'")

    def register_handler(self, handler_fn: Callable[[Any], Any], name: str = None):
        """Alternative method for registering handlers - alias for register_protocol."""
        protocol_name = name or f"handler_{len(self.protocols)}"
        self.register_protocol(protocol_name, handler_fn)

    def send(self, protocol: str, data: Any):
        """Send data using a specific protocol."""
        if protocol in self.protocols:
            try:
                return self.protocols[protocol](data)
            except (TypeError, ValueError, ConnectionError, TimeoutError) as e:
                self._log(f"Error sending data via '{protocol}': {e}")
                logger.warning("Protocol '%s' communication failed: %s", protocol, e)
            except Exception as e:  # noqa: BLE001 - Log but don't crash
                self._log(f"Unexpected error sending data via '{protocol}': {e}")
                logger.exception("Unexpected error in protocol '%s'", protocol)
        else:
            self._log(f"Protocol '{protocol}' not found")
        return None

    def list_protocols(self):
        """List all registered protocols."""
        return list(self.protocols.keys())

    def send_message(self, message: Any, protocol: str = None):
        """Send a message using the first available protocol or specified protocol."""
        if protocol:
            return self.send(protocol, message)
        elif self.protocols:
            # Use the first available protocol
            first_protocol = next(iter(self.protocols))
            return self.send(first_protocol, message)
        else:
            self._log("No protocols available to send message")
            return None

    def _log(self, message: str):
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [CommunicationManager] {message}")


__all__ = [
    "CommunicationManager",
]
