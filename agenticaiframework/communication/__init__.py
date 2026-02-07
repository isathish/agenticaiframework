"""
Agent Communication Module.

Provides multi-protocol agent-to-agent communication:

Protocols:
- STDIO: Standard input/output for local process communication (MCP-style)
- HTTP/HTTPS: RESTful communication for remote agents
- SSE: Server-Sent Events for real-time streaming responses
- MQTT: Message queue for IoT and distributed agent systems
- WebSocket: Bidirectional real-time communication

Features:
- RemoteAgentClient: Call remote agents over any protocol
- RemoteAgentServer: Expose agents as services (Flask, FastAPI, MQTT)
- AgentCommunicationManager: Central hub for all agent communications
- Message routing, broadcasting, and handoff support

Example:
    >>> from agenticaiframework.communication import (
    ...     AgentCommunicationManager,
    ...     RemoteAgentClient,
    ...     AgentEndpoint,
    ...     ProtocolType,
    ... )
    >>> 
    >>> # Using the manager (recommended)
    >>> manager = AgentCommunicationManager(agent_id="orchestrator")
    >>> manager.register_agent("analyzer", "https://analyzer.example.com/agent")
    >>> response = manager.send("analyzer", "Analyze this document")
    >>> 
    >>> # Using client directly
    >>> client = RemoteAgentClient()
    >>> client.register_endpoint(AgentEndpoint(
    ...     agent_id="summarizer",
    ...     protocol=ProtocolType.SSE,
    ...     host="summarizer.example.com"
    ... ))
    >>> for chunk in client.call_stream("summarizer", "Summarize article"):
    ...     print(chunk)
"""

from .protocols import (
    ProtocolType,
    ProtocolConfig,
    CommunicationProtocol,
    STDIOProtocol,
    HTTPProtocol,
    SSEProtocol,
    MQTTProtocol,
    WebSocketProtocol,
)
from .agent_channel import (
    AgentChannel,
    AgentMessage,
    MessageType,
)
from .remote_agent import (
    RemoteAgentClient,
    RemoteAgentServer,
    AgentEndpoint,
)
from .manager import AgentCommunicationManager


# Legacy CommunicationManager for backward compatibility
class CommunicationManager:
    """
    Legacy CommunicationManager for backward compatibility.
    
    For new code, use AgentCommunicationManager instead.
    """
    
    def __init__(self):
        from typing import Dict, Any, Callable
        self.protocols: Dict[str, Callable[[Any], Any]] = {}
    
    def _log(self, message: str):
        import time
        import logging as _logging
        _logging.getLogger(__name__).info("[CommunicationManager] %s", message)

    def register_protocol(self, name: str, handler_fn):
        self.protocols[name] = handler_fn
        self._log(f"Registered communication protocol '{name}'")

    def register_handler(self, handler_fn, name: str = None):
        """Alternative method for registering handlers"""
        protocol_name = name or f"handler_{len(self.protocols)}"
        self.register_protocol(protocol_name, handler_fn)

    def send(self, protocol: str, data):
        if protocol in self.protocols:
            try:
                return self.protocols[protocol](data)
            except (TypeError, ValueError, RuntimeError, ConnectionError, OSError) as e:
                self._log(f"Error sending data via '{protocol}': {e}")
                return None
        self._log(f"Protocol '{protocol}' not found")
        return None

    def list_protocols(self):
        return list(self.protocols.keys())

    def send_message(self, message, protocol: str = None):
        """Send a message using the first available protocol or specified protocol"""
        if protocol:
            return self.send(protocol, message)
        elif self.protocols:
            first_protocol = next(iter(self.protocols))
            return self.send(first_protocol, message)
        return None


__all__ = [
    # Legacy (backward compatibility)
    "CommunicationManager",
    # Protocol Types
    "ProtocolType",
    "ProtocolConfig",
    # Protocols
    "CommunicationProtocol",
    "STDIOProtocol",
    "HTTPProtocol",
    "SSEProtocol",
    "MQTTProtocol",
    "WebSocketProtocol",
    # Channel & Messages
    "AgentChannel",
    "AgentMessage",
    "MessageType",
    # Remote Agent
    "RemoteAgentClient",
    "RemoteAgentServer",
    "AgentEndpoint",
    # Manager
    "AgentCommunicationManager",
]
