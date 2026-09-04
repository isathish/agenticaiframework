"""
Agent Communication Channel and Message Types.
"""

import uuid
import json
import threading
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
    
    Channels register themselves in a process-wide registry keyed by
    ``agent_id``. ``send()`` delivers to the recipient channel's inbox when
    the recipient is registered in the same process; otherwise the message is
    left in the sender's own inbox. An optional ``router`` callable replaces
    in-process delivery, e.g. to hand messages to an external broker.
    
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
    
    # Process-wide registries shared by all channels.
    _registry: Dict[str, "AgentChannel"] = {}
    _topics: Dict[str, List[str]] = {}  # topic -> [agent_ids]
    _lock = threading.RLock()
    
    def __init__(
        self,
        agent_id: str,
        router: Optional[Callable[[AgentMessage], None]] = None,
    ):
        self.agent_id = agent_id
        self._router = router
        self._inbox: Queue = Queue()
        self._handlers: Dict[MessageType, List[Callable]] = {}
        self._pending_responses: Dict[str, Queue] = {}
        self._closed = False
        with AgentChannel._lock:
            AgentChannel._registry[agent_id] = self
    
    @property
    def _subscribers(self) -> Dict[str, List[str]]:
        """Shared topic -> subscriber map (kept for backwards compatibility)."""
        return AgentChannel._topics
    
    @classmethod
    def get_channel(cls, agent_id: str) -> Optional["AgentChannel"]:
        """Look up a registered channel by agent ID."""
        with cls._lock:
            return cls._registry.get(agent_id)
    
    def unregister(self) -> None:
        """Remove this channel from the registry and all topic subscriptions."""
        with AgentChannel._lock:
            if AgentChannel._registry.get(self.agent_id) is self:
                del AgentChannel._registry[self.agent_id]
            for topic in list(AgentChannel._topics):
                self._remove_subscription(topic)
        self._closed = True
    
    def close(self) -> None:
        """Alias for :meth:`unregister`."""
        self.unregister()
    
    def __enter__(self) -> "AgentChannel":
        return self
    
    def __exit__(self, *exc: Any) -> None:
        self.close()
    
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
        with AgentChannel._lock:
            subscribers = list(AgentChannel._topics.get(topic, []))
        
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
        with AgentChannel._lock:
            subscribers = AgentChannel._topics.setdefault(topic, [])
            if self.agent_id not in subscribers:
                subscribers.append(self.agent_id)
    
    def unsubscribe(self, topic: str) -> None:
        """Unsubscribe from a topic."""
        with AgentChannel._lock:
            self._remove_subscription(topic)
    
    def _remove_subscription(self, topic: str) -> None:
        """Drop this agent from a topic; caller must hold the lock."""
        subscribers = AgentChannel._topics.get(topic)
        if subscribers is None:
            return
        if self.agent_id in subscribers:
            subscribers.remove(self.agent_id)
        if not subscribers:
            del AgentChannel._topics[topic]
    
    def reply(
        self,
        message: AgentMessage,
        content: Any,
        msg_type: MessageType = MessageType.RESPONSE,
    ) -> AgentMessage:
        """Send a reply to ``message`` back to its sender."""
        response = message.create_reply(content, msg_type=msg_type)
        response.sender = self.agent_id
        self._route_message(response)
        return response
    
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
        """
        Deliver a message.
        
        Uses the injected ``router`` when present. Otherwise the message goes
        to the registered recipient channel's inbox; if the recipient is this
        agent or is not registered, it is placed in this channel's own inbox.
        """
        if self._router is not None:
            self._router(message)
            return
        
        target: Optional[AgentChannel] = None
        if message.recipient and message.recipient != self.agent_id:
            target = AgentChannel.get_channel(message.recipient)
        
        if target is None:
            self._inbox.put(message)
            return
        
        if message.reply_to and message.reply_to in target._pending_responses:
            target._pending_responses[message.reply_to].put(message)
        else:
            target._inbox.put(message)


__all__ = [
    "MessageType",
    "AgentMessage",
    "AgentChannel",
]
