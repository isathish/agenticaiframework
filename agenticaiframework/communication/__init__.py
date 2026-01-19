"""
Agent Communication Module.

Provides multi-protocol agent-to-agent communication:
- STDIO: Standard input/output for local process communication
- HTTP/HTTPS: RESTful communication for remote agents
- SSE: Server-Sent Events for real-time streaming
- MQTT: Message queue for IoT and distributed systems
- WebSocket: Bidirectional real-time communication
"""

from .protocols import (
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

__all__ = [
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
