"""
Agent Communication Manager.

Central hub for managing all agent communications across protocols.
"""

import uuid
import logging
import threading
from typing import Any, Callable, Dict, List, Optional, Union
from dataclasses import dataclass, field

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
from .agent_channel import AgentChannel, AgentMessage, MessageType
from .remote_agent import RemoteAgentClient, RemoteAgentServer, AgentEndpoint

logger = logging.getLogger(__name__)


@dataclass
class CommunicationStats:
    """Statistics for agent communication."""
    messages_sent: int = 0
    messages_received: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0
    errors: int = 0
    active_connections: int = 0


class AgentCommunicationManager:
    """
    Central manager for all agent communication needs.
    
    Features:
    - Multi-protocol support (STDIO, HTTP, SSE, MQTT, WebSocket)
    - Remote agent discovery and registration
    - Message routing and load balancing
    - Connection pooling
    - Statistics and monitoring
    
    Example:
        >>> manager = AgentCommunicationManager(agent_id="orchestrator")
        >>> 
        >>> # Register remote agents
        >>> manager.register_agent("analyzer", "https://analyzer.example.com")
        >>> manager.register_agent("summarizer", "https://summarizer.example.com")
        >>> 
        >>> # Send messages
        >>> response = manager.send("analyzer", {"prompt": "Analyze this"})
        >>> 
        >>> # Stream responses
        >>> for chunk in manager.stream("summarizer", "Summarize document"):
        ...     print(chunk)
        >>> 
        >>> # Broadcast to all
        >>> manager.broadcast({"notification": "System update"})
    """
    
    def __init__(
        self,
        agent_id: Optional[str] = None,
        default_protocol: ProtocolType = ProtocolType.HTTP,
    ):
        self.agent_id = agent_id or f"agent-{uuid.uuid4().hex[:8]}"
        self.default_protocol = default_protocol
        
        self._client = RemoteAgentClient(agent_id=self.agent_id)
        self._channel = AgentChannel(agent_id=self.agent_id)
        self._local_agents: Dict[str, Any] = {}  # agent_id -> Agent instance
        self._stats = CommunicationStats()
        self._message_handlers: List[Callable] = []
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None
    
    def register_agent(
        self,
        agent_id: str,
        url: Optional[str] = None,
        protocol: Optional[ProtocolType] = None,
        host: str = "localhost",
        port: int = 8080,
        path: str = "/agent",
        auth_token: Optional[str] = None,
        agent_instance: Any = None,
    ) -> None:
        """
        Register an agent for communication.
        
        Args:
            agent_id: Unique identifier for the agent
            url: Full URL (will parse host/port/path from it)
            protocol: Communication protocol
            host: Agent host
            port: Agent port
            path: API path
            auth_token: Authentication token
            agent_instance: Local agent instance (for in-process communication)
        """
        if agent_instance:
            # Register as local agent
            self._local_agents[agent_id] = agent_instance
            logger.info(f"Registered local agent: {agent_id}")
        else:
            # Parse URL if provided
            if url:
                from urllib.parse import urlparse
                parsed = urlparse(url)
                host = parsed.hostname or host
                port = parsed.port or port
                path = parsed.path or path
                if parsed.scheme == "https":
                    protocol = ProtocolType.HTTPS
                elif parsed.scheme == "mqtt":
                    protocol = ProtocolType.MQTT
                elif parsed.scheme == "ws":
                    protocol = ProtocolType.WEBSOCKET
                elif parsed.scheme == "wss":
                    protocol = ProtocolType.WEBSOCKET
                else:
                    protocol = protocol or ProtocolType.HTTP
            
            endpoint = AgentEndpoint(
                agent_id=agent_id,
                protocol=protocol or self.default_protocol,
                host=host,
                port=port,
                path=path,
                auth_token=auth_token,
            )
            
            self._client.register_endpoint(endpoint)
            logger.info(f"Registered remote agent: {agent_id} at {host}:{port}")
    
    def unregister_agent(self, agent_id: str) -> bool:
        """Unregister an agent."""
        if agent_id in self._local_agents:
            del self._local_agents[agent_id]
            return True
        
        if agent_id in self._client._endpoints:
            self._client.disconnect(agent_id)
            del self._client._endpoints[agent_id]
            return True
        
        return False
    
    def send(
        self,
        agent_id: str,
        content: Any,
        context: Optional[Dict] = None,
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        """
        Send a message to an agent.
        
        Args:
            agent_id: Target agent ID
            content: Message content (string or dict)
            context: Additional context
            timeout: Response timeout
            
        Returns:
            Agent response
        """
        self._stats.messages_sent += 1
        
        # Check if local agent
        if agent_id in self._local_agents:
            return self._call_local_agent(agent_id, content, context)
        
        # Send to remote agent
        try:
            response = self._client.call(agent_id, content, context, timeout)
            self._stats.messages_received += 1
            return response
        except Exception as e:
            self._stats.errors += 1
            return {"error": str(e)}
    
    def stream(
        self,
        agent_id: str,
        content: Any,
        context: Optional[Dict] = None,
    ):
        """
        Stream response from an agent.
        
        Yields:
            Response chunks
        """
        self._stats.messages_sent += 1
        
        # Check if local agent
        if agent_id in self._local_agents:
            agent = self._local_agents[agent_id]
            if hasattr(agent, "stream"):
                prompt = content.get("prompt") if isinstance(content, dict) else str(content)
                for chunk in agent.stream(prompt):
                    self._stats.messages_received += 1
                    yield chunk
            else:
                result = self._call_local_agent(agent_id, content, context)
                yield result
            return
        
        # Stream from remote agent
        try:
            for chunk in self._client.call_stream(agent_id, content, context):
                self._stats.messages_received += 1
                yield chunk
        except Exception as e:
            self._stats.errors += 1
            yield {"error": str(e)}
    
    def broadcast(
        self,
        content: Any,
        context: Optional[Dict] = None,
        exclude: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Broadcast message to all registered agents.
        
        Args:
            content: Message content
            context: Additional context
            exclude: Agent IDs to exclude
            
        Returns:
            Responses from all agents
        """
        exclude = exclude or []
        responses = {}
        
        # Local agents
        for agent_id in self._local_agents:
            if agent_id not in exclude:
                responses[agent_id] = self._call_local_agent(agent_id, content, context)
        
        # Remote agents
        remote_ids = [
            aid for aid in self._client._endpoints
            if aid not in exclude
        ]
        
        remote_responses = self._client.broadcast(remote_ids, content, context)
        responses.update(remote_responses)
        
        return responses
    
    def handoff(
        self,
        to_agent: str,
        context: Dict[str, Any],
        reason: str = "",
    ) -> Dict[str, Any]:
        """
        Handoff execution to another agent with full context.
        
        Args:
            to_agent: Target agent ID
            context: Context to transfer
            reason: Reason for handoff
        """
        return self._client.handoff(self.agent_id, to_agent, context, reason)
    
    def on_message(self, handler: Callable[[AgentMessage], Any]) -> None:
        """Register a handler for incoming messages."""
        self._message_handlers.append(handler)
        self._channel.register_handler(MessageType.QUERY, handler)
    
    def start_listening(self) -> None:
        """Start background message processing."""
        if self._running:
            return
        
        self._running = True
        self._worker_thread = threading.Thread(target=self._message_loop, daemon=True)
        self._worker_thread.start()
        logger.info(f"Started listening for messages: {self.agent_id}")
    
    def stop_listening(self) -> None:
        """Stop background message processing."""
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=5)
    
    def _message_loop(self) -> None:
        """Background message processing loop."""
        while self._running:
            message = self._channel.receive(timeout=1.0)
            if message:
                self._process_message(message)
    
    def _process_message(self, message: AgentMessage) -> None:
        """Process an incoming message."""
        self._stats.messages_received += 1
        
        for handler in self._message_handlers:
            try:
                handler(message)
            except Exception as e:
                logger.error(f"Message handler error: {e}")
                self._stats.errors += 1
    
    def _call_local_agent(
        self,
        agent_id: str,
        content: Any,
        context: Optional[Dict],
    ) -> Dict[str, Any]:
        """Call a local agent instance."""
        agent = self._local_agents[agent_id]
        prompt = content.get("prompt") if isinstance(content, dict) else str(content)
        
        try:
            if hasattr(agent, "run"):
                result = agent.run(prompt, context=context)
            elif hasattr(agent, "invoke"):
                result = agent.invoke(prompt)
            elif callable(agent):
                result = agent(prompt)
            else:
                result = {"error": "Agent not callable"}
            
            return result if isinstance(result, dict) else {"response": result}
        except Exception as e:
            return {"error": str(e)}
    
    def get_stats(self) -> Dict[str, Any]:
        """Get communication statistics."""
        return {
            "agent_id": self.agent_id,
            "messages_sent": self._stats.messages_sent,
            "messages_received": self._stats.messages_received,
            "errors": self._stats.errors,
            "local_agents": list(self._local_agents.keys()),
            "remote_agents": list(self._client._endpoints.keys()),
            "active_connections": len(self._client._protocols),
        }
    
    def list_agents(self) -> Dict[str, List[str]]:
        """List all registered agents."""
        return {
            "local": list(self._local_agents.keys()),
            "remote": list(self._client._endpoints.keys()),
        }
    
    def close(self) -> None:
        """Close all connections and stop listening."""
        self.stop_listening()
        self._client.disconnect_all()
        self._local_agents.clear()


__all__ = [
    "AgentCommunicationManager",
    "CommunicationStats",
]
