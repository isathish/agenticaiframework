"""
Agent Communication Channel and Message Types.
"""

import uuid
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from enum import Enum
from datetime import datetime
from queue import Queue, Empty


class MessageType(Enum):
    """Types of messages between agents."""
    QUERY = "query"
    RESPONSE = "response"
    STREAM = "stream"
    STREAM_START = "stream_start"
    STREAM_END = "stream_end"
    HANDOFF = "handoff"
    HEARTBEAT = "heartbeat"
    ERROR = "error"
    ACK = "ack"
    BROADCAST = "broadcast"
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"


@dataclass
class AgentMessage:
    """Message structure for inter-agent communication."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: MessageType = MessageType.QUERY
    sender: str = ""
    recipient: str = ""
    content: Any = None
    context: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    reply_to: Optional[str] = None
    ttl: Optional[int] = None  # Time to live in seconds
    priority: int = 0  # Higher = more priority
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
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
            "ttl": self.ttl,
            "priority": self.priority,
        }
    
    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentMessage":
        """Deserialize from dictionary."""
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
            ttl=data.get("ttl"),
            priority=data.get("priority", 0),
        )
    
    @classmethod
    def from_json(cls, json_str: str) -> "AgentMessage":
        """Deserialize from JSON string."""
        return cls.from_dict(json.loads(json_str))
    
    def create_reply(
        self,
        content: Any,
        msg_type: MessageType = MessageType.RESPONSE,
    ) -> "AgentMessage":
        """Create a reply message."""
        return AgentMessage(
            type=msg_type,
            sender=self.recipient,
            recipient=self.sender,
            content=content,
            context=self.context,
            reply_to=self.id,
        )


class AgentChannel:
    """
    Communication channel for agent-to-agent messaging.
    
    Provides:
    - Message queuing
    - Pub/sub patterns
    - Request/response patterns
    - Message handlers
    
    Example:
        >>> channel = AgentChannel(agent_id="my-agent")
        >>> 
        >>> # Register message handler
        >>> @channel.on_message(MessageType.QUERY)
        >>> def handle_query(msg):
        ...     return {"response": "Hello!"}
        >>> 
        >>> # Send message
        >>> response = channel.send("other-agent", "Hello", wait_response=True)
    """
    
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self._inbox: Queue = Queue()
        self._handlers: Dict[MessageType, List[Callable]] = {}
        self._pending_responses: Dict[str, Queue] = {}
        self._subscribers: Dict[str, List[str]] = {}  # topic -> [agent_ids]
    
    def on_message(self, msg_type: MessageType) -> Callable:
        """Decorator to register message handler."""
        def decorator(func: Callable) -> Callable:
            if msg_type not in self._handlers:
                self._handlers[msg_type] = []
            self._handlers[msg_type].append(func)
            return func
        return decorator
    
    def register_handler(
        self,
        msg_type: MessageType,
        handler: Callable[[AgentMessage], Any],
    ) -> None:
        """Register a message handler."""
        if msg_type not in self._handlers:
            self._handlers[msg_type] = []
        self._handlers[msg_type].append(handler)
    
    def send(
        self,
        recipient: str,
        content: Any,
        msg_type: MessageType = MessageType.QUERY,
        context: Optional[Dict] = None,
        wait_response: bool = False,
        timeout: float = 30.0,
    ) -> Optional[AgentMessage]:
        """
        Send a message to another agent.
        
        Args:
            recipient: Target agent ID
            content: Message content
            msg_type: Message type
            context: Additional context
            wait_response: Whether to wait for response
            timeout: Response timeout in seconds
        """
        message = AgentMessage(
            type=msg_type,
            sender=self.agent_id,
            recipient=recipient,
            content=content,
            context=context or {},
        )
        
        if wait_response:
            # Create response queue
            self._pending_responses[message.id] = Queue()
        
        # Route message (in a real system, this would go through a router)
        self._route_message(message)
        
        if wait_response:
            try:
                response = self._pending_responses[message.id].get(timeout=timeout)
                return response
            except Empty:
                return None
            finally:
                del self._pending_responses[message.id]
        
        return None
    
    def receive(self, timeout: Optional[float] = None) -> Optional[AgentMessage]:
        """Receive a message from inbox."""
        try:
            return self._inbox.get(timeout=timeout)
        except Empty:
            return None
    
    def broadcast(
        self,
        topic: str,
        content: Any,
        context: Optional[Dict] = None,
    ) -> None:
        """Broadcast message to all subscribers of a topic."""
        subscribers = self._subscribers.get(topic, [])
        
        for subscriber in subscribers:
            message = AgentMessage(
                type=MessageType.BROADCAST,
                sender=self.agent_id,
                recipient=subscriber,
                content=content,
                context=context or {},
                metadata={"topic": topic},
            )
            self._route_message(message)
    
    def subscribe(self, topic: str) -> None:
        """Subscribe to a topic."""
        if topic not in self._subscribers:
            self._subscribers[topic] = []
        if self.agent_id not in self._subscribers[topic]:
            self._subscribers[topic].append(self.agent_id)
    
    def unsubscribe(self, topic: str) -> None:
        """Unsubscribe from a topic."""
        if topic in self._subscribers:
            self._subscribers[topic] = [
                s for s in self._subscribers[topic] if s != self.agent_id
            ]
    
    def process_message(self, message: AgentMessage) -> Optional[Any]:
        """Process an incoming message through handlers."""
        # Check if this is a response to a pending request
        if message.reply_to and message.reply_to in self._pending_responses:
            self._pending_responses[message.reply_to].put(message)
            return None
        
        # Find and call handlers
        handlers = self._handlers.get(message.type, [])
        
        results = []
        for handler in handlers:
            try:
                result = handler(message)
                results.append(result)
            except Exception as e:
                results.append({"error": str(e)})
        
        return results[0] if len(results) == 1 else results
    
    def _route_message(self, message: AgentMessage) -> None:
        """Route message to appropriate destination."""
        # In a simple implementation, just put in inbox
        # In a real system, this would route through a message broker
        self._inbox.put(message)


__all__ = [
    "MessageType",
    "AgentMessage",
    "AgentChannel",
]
