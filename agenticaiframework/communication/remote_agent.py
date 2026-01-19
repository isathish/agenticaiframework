"""
Remote Agent Communication - Client and Server.

Enables agents to:
- Expose themselves as remote services
- Call other remote agents
- Handle multiple protocols (HTTP, SSE, MQTT, WebSocket)
"""

import json
import uuid
import time
import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterator, List, Optional, Type, Union
from enum import Enum
from datetime import datetime
from queue import Queue

from .protocols import (
    ProtocolType,
    ProtocolConfig,
    CommunicationProtocol,
    HTTPProtocol,
    SSEProtocol,
    MQTTProtocol,
    WebSocketProtocol,
    STDIOProtocol,
)

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """Types of agent messages."""
    QUERY = "query"
    RESPONSE = "response"
    STREAM = "stream"
    STREAM_END = "stream_end"
    HANDOFF = "handoff"
    HEARTBEAT = "heartbeat"
    ERROR = "error"
    ACK = "ack"


@dataclass
class AgentMessage:
    """Message structure for agent communication."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: MessageType = MessageType.QUERY
    sender: str = ""
    recipient: str = ""
    content: Any = None
    context: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    reply_to: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "type": self.type.value,
            "sender": self.sender,
            "recipient": self.recipient,
            "content": self.content,
            "context": self.context,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "reply_to": self.reply_to,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentMessage":
        """Create from dictionary."""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            type=MessageType(data.get("type", "query")),
            sender=data.get("sender", ""),
            recipient=data.get("recipient", ""),
            content=data.get("content"),
            context=data.get("context", {}),
            metadata=data.get("metadata", {}),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            reply_to=data.get("reply_to"),
        )


@dataclass
class AgentEndpoint:
    """Configuration for a remote agent endpoint."""
    agent_id: str
    protocol: ProtocolType = ProtocolType.HTTP
    host: str = "localhost"
    port: int = 8080
    path: str = "/agent"
    auth_token: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # MQTT-specific
    mqtt_topic: Optional[str] = None
    
    # STDIO-specific
    command: Optional[List[str]] = None


class RemoteAgentClient:
    """
    Client for calling remote agents over various protocols.
    
    Example:
        >>> # HTTP/HTTPS
        >>> client = RemoteAgentClient()
        >>> client.register_endpoint(AgentEndpoint(
        ...     agent_id="analyzer",
        ...     protocol=ProtocolType.HTTPS,
        ...     host="analyzer.example.com",
        ...     port=443
        ... ))
        >>> response = client.call("analyzer", "Analyze this document")
        
        >>> # MQTT
        >>> client.register_endpoint(AgentEndpoint(
        ...     agent_id="iot-agent",
        ...     protocol=ProtocolType.MQTT,
        ...     host="mqtt.example.com",
        ...     mqtt_topic="agents/iot"
        ... ))
        >>> response = client.call("iot-agent", "Get sensor data")
        
        >>> # Streaming with SSE
        >>> for chunk in client.call_stream("summarizer", "Summarize article"):
        ...     print(chunk)
    """
    
    def __init__(self, agent_id: Optional[str] = None):
        self.agent_id = agent_id or f"client-{uuid.uuid4().hex[:8]}"
        self._endpoints: Dict[str, AgentEndpoint] = {}
        self._protocols: Dict[str, CommunicationProtocol] = {}
        self._connected: Dict[str, bool] = {}
    
    def register_endpoint(self, endpoint: AgentEndpoint) -> None:
        """Register a remote agent endpoint."""
        self._endpoints[endpoint.agent_id] = endpoint
        logger.info(f"Registered endpoint: {endpoint.agent_id} ({endpoint.protocol.value})")
    
    def register_endpoints(self, endpoints: List[AgentEndpoint]) -> None:
        """Register multiple endpoints."""
        for endpoint in endpoints:
            self.register_endpoint(endpoint)
    
    def connect(self, agent_id: str) -> bool:
        """Connect to a specific remote agent."""
        if agent_id not in self._endpoints:
            logger.error(f"Unknown agent: {agent_id}")
            return False
        
        endpoint = self._endpoints[agent_id]
        protocol = self._create_protocol(endpoint)
        
        if protocol.connect():
            self._protocols[agent_id] = protocol
            self._connected[agent_id] = True
            logger.info(f"Connected to: {agent_id}")
            return True
        return False
    
    def disconnect(self, agent_id: str) -> bool:
        """Disconnect from a remote agent."""
        if agent_id in self._protocols:
            result = self._protocols[agent_id].disconnect()
            del self._protocols[agent_id]
            self._connected[agent_id] = False
            return result
        return True
    
    def disconnect_all(self) -> None:
        """Disconnect from all agents."""
        for agent_id in list(self._protocols.keys()):
            self.disconnect(agent_id)
    
    def call(
        self,
        agent_id: str,
        prompt: Union[str, Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Call a remote agent and get response.
        
        Args:
            agent_id: Target agent identifier
            prompt: Query or message to send
            context: Additional context
            timeout: Response timeout
            
        Returns:
            Agent response dictionary
        """
        # Auto-connect if needed
        if agent_id not in self._protocols:
            if not self.connect(agent_id):
                return {"error": f"Cannot connect to agent: {agent_id}"}
        
        protocol = self._protocols[agent_id]
        
        # Build message
        message = AgentMessage(
            type=MessageType.QUERY,
            sender=self.agent_id,
            recipient=agent_id,
            content=prompt if isinstance(prompt, dict) else {"prompt": prompt},
            context=context or {},
        )
        
        # Set timeout if specified
        if timeout:
            protocol.config.timeout = timeout
        
        # Send and get response
        response = protocol.send(message.to_dict())
        
        return response
    
    def call_stream(
        self,
        agent_id: str,
        prompt: Union[str, Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
    ) -> Iterator[Dict[str, Any]]:
        """
        Call a remote agent and stream the response.
        
        Uses SSE or WebSocket for streaming.
        """
        if agent_id not in self._endpoints:
            yield {"error": f"Unknown agent: {agent_id}"}
            return
        
        endpoint = self._endpoints[agent_id]
        
        # Use SSE for streaming
        if endpoint.protocol in [ProtocolType.SSE, ProtocolType.HTTP, ProtocolType.HTTPS]:
            protocol = SSEProtocol(
                host=endpoint.host,
                port=endpoint.port,
                path=endpoint.path,
                use_ssl=(endpoint.protocol == ProtocolType.HTTPS),
            )
            
            if not protocol.connect():
                yield {"error": "Failed to connect for streaming"}
                return
            
            message = AgentMessage(
                type=MessageType.QUERY,
                sender=self.agent_id,
                recipient=agent_id,
                content=prompt if isinstance(prompt, dict) else {"prompt": prompt},
                context=context or {},
                metadata={"stream": True},
            )
            
            try:
                for event in protocol.send_and_stream(message.to_dict()):
                    yield event
            finally:
                protocol.disconnect()
        
        # Use WebSocket for streaming
        elif endpoint.protocol == ProtocolType.WEBSOCKET:
            if agent_id not in self._protocols:
                if not self.connect(agent_id):
                    yield {"error": "Failed to connect"}
                    return
            
            protocol = self._protocols[agent_id]
            
            message = AgentMessage(
                type=MessageType.QUERY,
                sender=self.agent_id,
                recipient=agent_id,
                content=prompt if isinstance(prompt, dict) else {"prompt": prompt},
                context=context or {},
                metadata={"stream": True},
            )
            
            protocol.send_nowait(message.to_dict())
            
            while True:
                response = protocol.receive(timeout=30.0)
                if not response:
                    break
                yield response
                if response.get("type") == MessageType.STREAM_END.value:
                    break
    
    def handoff(
        self,
        from_agent: str,
        to_agent: str,
        context: Dict[str, Any],
        reason: str = "",
    ) -> Dict[str, Any]:
        """
        Handoff execution from one agent to another.
        
        Args:
            from_agent: Source agent
            to_agent: Target agent
            context: Conversation/execution context to transfer
            reason: Reason for handoff
        """
        message = AgentMessage(
            type=MessageType.HANDOFF,
            sender=from_agent,
            recipient=to_agent,
            content={
                "reason": reason,
                "handoff_context": context,
            },
            context=context,
        )
        
        return self.call(to_agent, message.to_dict())
    
    def broadcast(
        self,
        agent_ids: List[str],
        prompt: Union[str, Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Broadcast message to multiple agents.
        
        Returns:
            Dictionary mapping agent_id to response
        """
        results = {}
        for agent_id in agent_ids:
            results[agent_id] = self.call(agent_id, prompt, context)
        return results
    
    def _create_protocol(self, endpoint: AgentEndpoint) -> CommunicationProtocol:
        """Create protocol instance for endpoint."""
        config = ProtocolConfig(
            protocol_type=endpoint.protocol,
            host=endpoint.host,
            port=endpoint.port,
            path=endpoint.path,
            auth_token=endpoint.auth_token,
        )
        
        if endpoint.protocol == ProtocolType.HTTP:
            return HTTPProtocol(
                host=endpoint.host,
                port=endpoint.port,
                path=endpoint.path,
                use_ssl=False,
                config=config,
            )
        
        elif endpoint.protocol == ProtocolType.HTTPS:
            return HTTPProtocol(
                host=endpoint.host,
                port=endpoint.port,
                path=endpoint.path,
                use_ssl=True,
                config=config,
            )
        
        elif endpoint.protocol == ProtocolType.SSE:
            return SSEProtocol(
                host=endpoint.host,
                port=endpoint.port,
                path=endpoint.path,
                config=config,
            )
        
        elif endpoint.protocol == ProtocolType.MQTT:
            return MQTTProtocol(
                broker=endpoint.host,
                port=endpoint.port,
                topic=endpoint.mqtt_topic or f"agents/{endpoint.agent_id}",
                config=config,
            )
        
        elif endpoint.protocol == ProtocolType.WEBSOCKET:
            return WebSocketProtocol(
                host=endpoint.host,
                port=endpoint.port,
                path=endpoint.path,
                config=config,
            )
        
        elif endpoint.protocol == ProtocolType.STDIO:
            return STDIOProtocol(
                command=endpoint.command,
                config=config,
            )
        
        else:
            raise ValueError(f"Unsupported protocol: {endpoint.protocol}")


class RemoteAgentServer:
    """
    Server to expose an agent as a remote service.
    
    Example:
        >>> from agenticaiframework import Agent
        >>> 
        >>> agent = Agent(name="my-agent", model="gpt-4")
        >>> 
        >>> server = RemoteAgentServer(agent)
        >>> server.start(host="0.0.0.0", port=8080)
        
        >>> # With Flask
        >>> app = server.create_flask_app()
        >>> app.run(port=8080)
        
        >>> # With FastAPI
        >>> app = server.create_fastapi_app()
        >>> uvicorn.run(app, port=8080)
    """
    
    def __init__(
        self,
        agent: Any,  # Agent instance
        agent_id: Optional[str] = None,
    ):
        self.agent = agent
        self.agent_id = agent_id or getattr(agent, "name", str(uuid.uuid4()))
        self._handlers: Dict[MessageType, Callable] = {}
        self._running = False
        
        # Register default handlers
        self._setup_default_handlers()
    
    def _setup_default_handlers(self) -> None:
        """Set up default message handlers."""
        self._handlers[MessageType.QUERY] = self._handle_query
        self._handlers[MessageType.HANDOFF] = self._handle_handoff
        self._handlers[MessageType.HEARTBEAT] = self._handle_heartbeat
    
    def on_message(
        self,
        message_type: MessageType,
    ) -> Callable:
        """Decorator to register custom message handlers."""
        def decorator(func: Callable) -> Callable:
            self._handlers[message_type] = func
            return func
        return decorator
    
    def handle_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Process incoming message and return response."""
        try:
            agent_msg = AgentMessage.from_dict(message)
            handler = self._handlers.get(agent_msg.type, self._handle_query)
            return handler(agent_msg)
        except Exception as e:
            logger.error(f"Message handling error: {e}")
            return {
                "type": MessageType.ERROR.value,
                "error": str(e),
            }
    
    def _handle_query(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle query messages."""
        try:
            content = message.content
            prompt = content.get("prompt") if isinstance(content, dict) else str(content)
            
            # Get context
            context = message.context
            
            # Call agent
            if hasattr(self.agent, "run"):
                result = self.agent.run(prompt, context=context)
            elif hasattr(self.agent, "invoke"):
                result = self.agent.invoke(prompt)
            elif callable(self.agent):
                result = self.agent(prompt)
            else:
                result = {"error": "Agent not callable"}
            
            return AgentMessage(
                type=MessageType.RESPONSE,
                sender=self.agent_id,
                recipient=message.sender,
                content=result,
                reply_to=message.id,
            ).to_dict()
            
        except Exception as e:
            return {
                "type": MessageType.ERROR.value,
                "error": str(e),
                "reply_to": message.id,
            }
    
    def _handle_handoff(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle handoff messages."""
        try:
            content = message.content
            handoff_context = content.get("handoff_context", {})
            
            # Update agent's context if supported
            if hasattr(self.agent, "set_context"):
                self.agent.set_context(handoff_context)
            
            return AgentMessage(
                type=MessageType.ACK,
                sender=self.agent_id,
                recipient=message.sender,
                content={"status": "handoff_accepted"},
                reply_to=message.id,
            ).to_dict()
            
        except Exception as e:
            return {"type": MessageType.ERROR.value, "error": str(e)}
    
    def _handle_heartbeat(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle heartbeat messages."""
        return AgentMessage(
            type=MessageType.ACK,
            sender=self.agent_id,
            recipient=message.sender,
            content={"status": "alive", "timestamp": datetime.now().isoformat()},
            reply_to=message.id,
        ).to_dict()
    
    def create_flask_app(self):
        """Create Flask app for HTTP server."""
        try:
            from flask import Flask, request, jsonify, Response
        except ImportError:
            raise ImportError("Flask required: pip install flask")
        
        app = Flask(f"agent-{self.agent_id}")
        
        @app.route("/health", methods=["GET"])
        def health():
            return jsonify({"status": "healthy", "agent_id": self.agent_id})
        
        @app.route("/agent", methods=["POST"])
        def agent_endpoint():
            message = request.json
            response = self.handle_message(message)
            return jsonify(response)
        
        @app.route("/agent/stream", methods=["POST"])
        def agent_stream():
            message = request.json
            
            def generate():
                agent_msg = AgentMessage.from_dict(message)
                content = agent_msg.content
                prompt = content.get("prompt") if isinstance(content, dict) else str(content)
                
                if hasattr(self.agent, "stream"):
                    for chunk in self.agent.stream(prompt):
                        yield f"data: {json.dumps({'chunk': chunk})}\n\n"
                else:
                    result = self._handle_query(agent_msg)
                    yield f"data: {json.dumps(result)}\n\n"
                
                yield f"data: {json.dumps({'type': 'stream_end'})}\n\n"
            
            return Response(generate(), mimetype="text/event-stream")
        
        return app
    
    def create_fastapi_app(self):
        """Create FastAPI app for HTTP server."""
        try:
            from fastapi import FastAPI
            from fastapi.responses import StreamingResponse
            from pydantic import BaseModel
        except ImportError:
            raise ImportError("FastAPI required: pip install fastapi uvicorn")
        
        app = FastAPI(title=f"Agent: {self.agent_id}")
        
        @app.get("/health")
        def health():
            return {"status": "healthy", "agent_id": self.agent_id}
        
        @app.post("/agent")
        def agent_endpoint(message: dict):
            return self.handle_message(message)
        
        @app.post("/agent/stream")
        def agent_stream(message: dict):
            async def generate():
                agent_msg = AgentMessage.from_dict(message)
                content = agent_msg.content
                prompt = content.get("prompt") if isinstance(content, dict) else str(content)
                
                if hasattr(self.agent, "stream"):
                    for chunk in self.agent.stream(prompt):
                        yield f"data: {json.dumps({'chunk': chunk})}\n\n"
                else:
                    result = self._handle_query(agent_msg)
                    yield f"data: {json.dumps(result)}\n\n"
                
                yield f"data: {json.dumps({'type': 'stream_end'})}\n\n"
            
            return StreamingResponse(generate(), media_type="text/event-stream")
        
        return app
    
    def create_mqtt_handler(
        self,
        broker: str = "localhost",
        port: int = 1883,
        topic: Optional[str] = None,
    ):
        """Create MQTT message handler."""
        protocol = MQTTProtocol(
            broker=broker,
            port=port,
            topic=topic or f"agents/{self.agent_id}/requests",
        )
        
        response_topic = f"agents/{self.agent_id}/responses"
        
        def on_message(message: Dict[str, Any]) -> None:
            payload = message.get("payload", {})
            response = self.handle_message(payload)
            protocol.send(response, topic=response_topic)
        
        protocol.on_message(on_message)
        protocol.connect()
        protocol.subscribe(topic or f"agents/{self.agent_id}/requests")
        
        return protocol
    
    def start_stdio(self) -> None:
        """Start STDIO server for subprocess communication."""
        import sys
        
        self._running = True
        logger.info(f"STDIO server started for agent: {self.agent_id}")
        
        while self._running:
            try:
                line = sys.stdin.readline()
                if not line:
                    break
                
                message = json.loads(line.strip())
                response = self.handle_message(message)
                
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
                
            except json.JSONDecodeError:
                pass
            except KeyboardInterrupt:
                break
            except Exception as e:
                error_response = {"type": "error", "error": str(e)}
                sys.stdout.write(json.dumps(error_response) + "\n")
                sys.stdout.flush()
    
    def stop(self) -> None:
        """Stop the server."""
        self._running = False


__all__ = [
    "MessageType",
    "AgentMessage",
    "AgentEndpoint",
    "RemoteAgentClient",
    "RemoteAgentServer",
]
