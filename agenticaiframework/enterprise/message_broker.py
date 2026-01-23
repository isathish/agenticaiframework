"""
Enterprise Message Broker Module.

Provides message broker abstraction, pub/sub patterns,
message routing, and reliable message delivery.

Example:
    # Create broker
    broker = create_message_broker()
    
    # Create producer
    producer = broker.create_producer("orders")
    await producer.send(OrderMessage(order_id="123"))
    
    # Create consumer
    consumer = broker.create_consumer("orders")
    async for message in consumer:
        print(f"Received: {message.payload}")
        await message.ack()
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    AsyncIterator,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    Type,
    TypeVar,
)

T = TypeVar('T')


logger = logging.getLogger(__name__)


class MessageBrokerError(Exception):
    """Message broker error."""
    pass


class PublishError(MessageBrokerError):
    """Publish error."""
    pass


class ConsumeError(MessageBrokerError):
    """Consume error."""
    pass


class AcknowledgeError(MessageBrokerError):
    """Acknowledge error."""
    pass


class DeliveryMode(str, Enum):
    """Message delivery mode."""
    PERSISTENT = "persistent"
    NON_PERSISTENT = "non_persistent"


class AckMode(str, Enum):
    """Acknowledgment mode."""
    AUTO = "auto"
    MANUAL = "manual"
    CLIENT = "client"


class MessageState(str, Enum):
    """Message state."""
    PENDING = "pending"
    DELIVERED = "delivered"
    ACKNOWLEDGED = "acknowledged"
    REJECTED = "rejected"
    REQUEUED = "requeued"
    DEAD_LETTERED = "dead_lettered"


@dataclass
class MessageHeaders:
    """Message headers."""
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: Optional[str] = None
    reply_to: Optional[str] = None
    content_type: str = "application/json"
    content_encoding: str = "utf-8"
    priority: int = 0
    ttl: Optional[int] = None  # Time to live in seconds
    timestamp: datetime = field(default_factory=datetime.now)
    custom: Dict[str, str] = field(default_factory=dict)


@dataclass
class Message:
    """Message with payload and metadata."""
    payload: Any
    headers: MessageHeaders = field(default_factory=MessageHeaders)
    topic: Optional[str] = None
    partition: Optional[int] = None
    offset: Optional[int] = None
    state: MessageState = MessageState.PENDING
    delivery_count: int = 0
    
    async def ack(self) -> None:
        """Acknowledge the message."""
        self.state = MessageState.ACKNOWLEDGED
    
    async def nack(self, requeue: bool = True) -> None:
        """Negative acknowledge the message."""
        if requeue:
            self.state = MessageState.REQUEUED
            self.delivery_count += 1
        else:
            self.state = MessageState.REJECTED
    
    async def reject(self) -> None:
        """Reject the message without requeuing."""
        self.state = MessageState.REJECTED


@dataclass
class TopicConfig:
    """Topic configuration."""
    name: str
    partitions: int = 1
    replication_factor: int = 1
    retention_ms: int = 604800000  # 7 days
    max_message_size: int = 1048576  # 1MB
    cleanup_policy: str = "delete"  # or "compact"


@dataclass
class ConsumerConfig:
    """Consumer configuration."""
    group_id: Optional[str] = None
    auto_offset_reset: str = "latest"  # or "earliest"
    enable_auto_commit: bool = True
    auto_commit_interval_ms: int = 5000
    max_poll_records: int = 500
    session_timeout_ms: int = 30000


@dataclass
class ProducerConfig:
    """Producer configuration."""
    acks: str = "all"  # "0", "1", or "all"
    retries: int = 3
    batch_size: int = 16384
    linger_ms: int = 0
    compression_type: str = "none"
    max_request_size: int = 1048576


class Serializer(ABC, Generic[T]):
    """
    Message serializer.
    """
    
    @abstractmethod
    def serialize(self, value: T) -> bytes:
        """Serialize value to bytes."""
        pass
    
    @abstractmethod
    def deserialize(self, data: bytes) -> T:
        """Deserialize bytes to value."""
        pass


class JsonSerializer(Serializer[Any]):
    """
    JSON serializer.
    """
    
    def serialize(self, value: Any) -> bytes:
        return json.dumps(value, default=str).encode('utf-8')
    
    def deserialize(self, data: bytes) -> Any:
        return json.loads(data.decode('utf-8'))


class Producer(ABC):
    """
    Abstract message producer.
    """
    
    @abstractmethod
    async def send(
        self,
        message: Any,
        key: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> str:
        """Send a message."""
        pass
    
    @abstractmethod
    async def send_batch(
        self,
        messages: List[Any],
    ) -> List[str]:
        """Send a batch of messages."""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Close the producer."""
        pass


class Consumer(ABC):
    """
    Abstract message consumer.
    """
    
    @abstractmethod
    async def receive(
        self,
        timeout: Optional[float] = None,
    ) -> Optional[Message]:
        """Receive a message."""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Close the consumer."""
        pass
    
    def __aiter__(self) -> AsyncIterator[Message]:
        return self
    
    async def __anext__(self) -> Message:
        message = await self.receive()
        if message is None:
            raise StopAsyncIteration
        return message


class MessageBroker(ABC):
    """
    Abstract message broker.
    """
    
    @abstractmethod
    async def create_topic(self, config: TopicConfig) -> None:
        """Create a topic."""
        pass
    
    @abstractmethod
    async def delete_topic(self, name: str) -> None:
        """Delete a topic."""
        pass
    
    @abstractmethod
    def create_producer(
        self,
        topic: str,
        config: Optional[ProducerConfig] = None,
    ) -> Producer:
        """Create a producer for a topic."""
        pass
    
    @abstractmethod
    def create_consumer(
        self,
        topic: str,
        config: Optional[ConsumerConfig] = None,
    ) -> Consumer:
        """Create a consumer for a topic."""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Close the broker connection."""
        pass


class InMemoryQueue:
    """
    In-memory message queue.
    """
    
    def __init__(self, max_size: int = 10000):
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=max_size)
        self._messages: List[Message] = []
        self._offset = 0
    
    async def put(self, message: Message) -> int:
        """Put a message in the queue."""
        message.offset = self._offset
        self._offset += 1
        self._messages.append(message)
        await self._queue.put(message)
        return message.offset
    
    async def get(
        self,
        timeout: Optional[float] = None,
    ) -> Optional[Message]:
        """Get a message from the queue."""
        try:
            if timeout:
                return await asyncio.wait_for(
                    self._queue.get(),
                    timeout=timeout,
                )
            return await self._queue.get()
        except asyncio.TimeoutError:
            return None
    
    def size(self) -> int:
        return self._queue.qsize()
    
    def is_empty(self) -> bool:
        return self._queue.empty()


class InMemoryProducer(Producer):
    """
    In-memory producer implementation.
    """
    
    def __init__(
        self,
        topic: str,
        queue: InMemoryQueue,
        serializer: Serializer,
    ):
        self._topic = topic
        self._queue = queue
        self._serializer = serializer
        self._closed = False
    
    async def send(
        self,
        message: Any,
        key: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> str:
        if self._closed:
            raise PublishError("Producer is closed")
        
        msg_headers = MessageHeaders()
        if headers:
            msg_headers.custom = headers
        
        msg = Message(
            payload=message,
            headers=msg_headers,
            topic=self._topic,
        )
        
        await self._queue.put(msg)
        return msg.headers.message_id
    
    async def send_batch(
        self,
        messages: List[Any],
    ) -> List[str]:
        ids = []
        for message in messages:
            msg_id = await self.send(message)
            ids.append(msg_id)
        return ids
    
    async def close(self) -> None:
        self._closed = True


class InMemoryConsumer(Consumer):
    """
    In-memory consumer implementation.
    """
    
    def __init__(
        self,
        topic: str,
        queue: InMemoryQueue,
        config: ConsumerConfig,
        serializer: Serializer,
    ):
        self._topic = topic
        self._queue = queue
        self._config = config
        self._serializer = serializer
        self._closed = False
        self._pending: List[Message] = []
    
    async def receive(
        self,
        timeout: Optional[float] = None,
    ) -> Optional[Message]:
        if self._closed:
            raise ConsumeError("Consumer is closed")
        
        message = await self._queue.get(timeout)
        
        if message and self._config.enable_auto_commit:
            await message.ack()
        
        return message
    
    async def commit(self) -> None:
        """Commit offsets."""
        for msg in self._pending:
            await msg.ack()
        self._pending.clear()
    
    async def close(self) -> None:
        self._closed = True


class InMemoryMessageBroker(MessageBroker):
    """
    In-memory message broker implementation.
    """
    
    def __init__(self):
        self._topics: Dict[str, InMemoryQueue] = {}
        self._topic_configs: Dict[str, TopicConfig] = {}
        self._serializer = JsonSerializer()
        self._closed = False
    
    async def create_topic(self, config: TopicConfig) -> None:
        if config.name in self._topics:
            return
        
        self._topics[config.name] = InMemoryQueue()
        self._topic_configs[config.name] = config
        logger.info(f"Created topic: {config.name}")
    
    async def delete_topic(self, name: str) -> None:
        self._topics.pop(name, None)
        self._topic_configs.pop(name, None)
        logger.info(f"Deleted topic: {name}")
    
    def create_producer(
        self,
        topic: str,
        config: Optional[ProducerConfig] = None,
    ) -> Producer:
        if topic not in self._topics:
            self._topics[topic] = InMemoryQueue()
        
        return InMemoryProducer(
            topic,
            self._topics[topic],
            self._serializer,
        )
    
    def create_consumer(
        self,
        topic: str,
        config: Optional[ConsumerConfig] = None,
    ) -> Consumer:
        if topic not in self._topics:
            self._topics[topic] = InMemoryQueue()
        
        return InMemoryConsumer(
            topic,
            self._topics[topic],
            config or ConsumerConfig(),
            self._serializer,
        )
    
    async def close(self) -> None:
        self._closed = True
        logger.info("Message broker closed")
    
    def get_topic_info(self, name: str) -> Optional[Dict[str, Any]]:
        """Get topic information."""
        if name not in self._topics:
            return None
        
        config = self._topic_configs.get(name)
        queue = self._topics[name]
        
        return {
            "name": name,
            "size": queue.size(),
            "config": config,
        }


class PubSubBroker:
    """
    Publish-subscribe pattern broker.
    """
    
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._patterns: List[tuple] = []  # (pattern, callback)
    
    def subscribe(
        self,
        topic: str,
        callback: Callable[[Message], Any],
    ) -> Callable[[], None]:
        """Subscribe to a topic."""
        self._subscribers[topic].append(callback)
        
        def unsubscribe():
            self._subscribers[topic].remove(callback)
        
        return unsubscribe
    
    def subscribe_pattern(
        self,
        pattern: str,
        callback: Callable[[Message], Any],
    ) -> Callable[[], None]:
        """Subscribe to topics matching a pattern."""
        import fnmatch
        self._patterns.append((pattern, callback))
        
        def unsubscribe():
            self._patterns.remove((pattern, callback))
        
        return unsubscribe
    
    async def publish(
        self,
        topic: str,
        payload: Any,
    ) -> int:
        """Publish to a topic."""
        import fnmatch
        
        message = Message(payload=payload, topic=topic)
        delivered = 0
        
        # Direct subscribers
        for callback in self._subscribers.get(topic, []):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(message)
                else:
                    callback(message)
                delivered += 1
            except Exception as e:
                logger.error(f"Subscriber error: {e}")
        
        # Pattern subscribers
        for pattern, callback in self._patterns:
            if fnmatch.fnmatch(topic, pattern):
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(message)
                    else:
                        callback(message)
                    delivered += 1
                except Exception as e:
                    logger.error(f"Pattern subscriber error: {e}")
        
        return delivered


class RequestReplyBroker:
    """
    Request-reply pattern broker.
    """
    
    def __init__(self, broker: MessageBroker):
        self._broker = broker
        self._pending: Dict[str, asyncio.Future] = {}
        self._reply_topic = f"reply.{uuid.uuid4()}"
        self._consumer: Optional[Consumer] = None
        self._running = False
    
    async def start(self) -> None:
        """Start the reply consumer."""
        if self._running:
            return
        
        self._consumer = self._broker.create_consumer(self._reply_topic)
        self._running = True
        asyncio.create_task(self._process_replies())
    
    async def stop(self) -> None:
        """Stop the reply consumer."""
        self._running = False
        if self._consumer:
            await self._consumer.close()
    
    async def _process_replies(self) -> None:
        """Process reply messages."""
        while self._running:
            try:
                message = await self._consumer.receive(timeout=1.0)
                if message:
                    correlation_id = message.headers.correlation_id
                    if correlation_id in self._pending:
                        future = self._pending.pop(correlation_id)
                        future.set_result(message)
            except Exception as e:
                logger.error(f"Reply processing error: {e}")
    
    async def request(
        self,
        topic: str,
        payload: Any,
        timeout: float = 30.0,
    ) -> Message:
        """Send a request and wait for reply."""
        correlation_id = str(uuid.uuid4())
        
        future: asyncio.Future = asyncio.Future()
        self._pending[correlation_id] = future
        
        producer = self._broker.create_producer(topic)
        await producer.send(
            payload,
            headers={
                "correlation_id": correlation_id,
                "reply_to": self._reply_topic,
            },
        )
        
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending.pop(correlation_id, None)
            raise MessageBrokerError("Request timed out")


class MessageRouter:
    """
    Message router for routing messages to handlers.
    """
    
    def __init__(self):
        self._routes: Dict[str, Callable] = {}
        self._default_handler: Optional[Callable] = None
    
    def route(
        self,
        topic: str,
        handler: Callable[[Message], Any],
    ) -> None:
        """Add a route."""
        self._routes[topic] = handler
    
    def default(
        self,
        handler: Callable[[Message], Any],
    ) -> None:
        """Set default handler."""
        self._default_handler = handler
    
    async def handle(self, message: Message) -> Any:
        """Handle a message."""
        handler = self._routes.get(message.topic)
        
        if not handler and self._default_handler:
            handler = self._default_handler
        
        if not handler:
            raise MessageBrokerError(f"No handler for topic: {message.topic}")
        
        if asyncio.iscoroutinefunction(handler):
            return await handler(message)
        return handler(message)


class BrokerRegistry:
    """
    Registry for message brokers.
    """
    
    def __init__(self):
        self._brokers: Dict[str, MessageBroker] = {}
        self._default: Optional[str] = None
    
    def register(
        self,
        name: str,
        broker: MessageBroker,
        default: bool = False,
    ) -> None:
        """Register a broker."""
        self._brokers[name] = broker
        if default or self._default is None:
            self._default = name
    
    def get(self, name: Optional[str] = None) -> MessageBroker:
        """Get a broker."""
        name = name or self._default
        if not name or name not in self._brokers:
            raise MessageBrokerError(f"Broker not found: {name}")
        return self._brokers[name]


# Global registry
_global_registry = BrokerRegistry()


# Decorators
def message_handler(topic: str) -> Callable:
    """
    Decorator to create a message handler.
    
    Example:
        @message_handler("orders")
        async def handle_order(message: Message):
            print(f"Order: {message.payload}")
    """
    def decorator(func: Callable[[Message], Any]) -> Callable[[Message], Any]:
        func._message_topic = topic
        return func
    
    return decorator


def subscribe_topic(
    topic: str,
    broker_name: Optional[str] = None,
) -> Callable:
    """
    Decorator to subscribe to a topic.
    
    Example:
        @subscribe_topic("orders")
        async def on_order(message: Message):
            ...
    """
    def decorator(func: Callable[[Message], Any]) -> Callable[[Message], Any]:
        # Registration would happen at startup
        func._subscribe_topic = topic
        func._broker_name = broker_name
        return func
    
    return decorator


# Factory functions
def create_message_broker() -> InMemoryMessageBroker:
    """Create an in-memory message broker."""
    return InMemoryMessageBroker()


def create_pubsub_broker() -> PubSubBroker:
    """Create a pub/sub broker."""
    return PubSubBroker()


def create_request_reply_broker(
    broker: MessageBroker,
) -> RequestReplyBroker:
    """Create a request-reply broker."""
    return RequestReplyBroker(broker)


def create_message_router() -> MessageRouter:
    """Create a message router."""
    return MessageRouter()


def create_topic_config(
    name: str,
    partitions: int = 1,
    retention_days: int = 7,
) -> TopicConfig:
    """Create topic configuration."""
    return TopicConfig(
        name=name,
        partitions=partitions,
        retention_ms=retention_days * 24 * 60 * 60 * 1000,
    )


def create_consumer_config(
    group_id: Optional[str] = None,
    auto_commit: bool = True,
) -> ConsumerConfig:
    """Create consumer configuration."""
    return ConsumerConfig(
        group_id=group_id,
        enable_auto_commit=auto_commit,
    )


def create_producer_config(
    acks: str = "all",
    retries: int = 3,
) -> ProducerConfig:
    """Create producer configuration."""
    return ProducerConfig(acks=acks, retries=retries)


def register_broker(
    name: str,
    broker: MessageBroker,
    default: bool = False,
) -> None:
    """Register broker in global registry."""
    _global_registry.register(name, broker, default)


def get_broker(name: Optional[str] = None) -> MessageBroker:
    """Get broker from global registry."""
    return _global_registry.get(name)


__all__ = [
    # Exceptions
    "MessageBrokerError",
    "PublishError",
    "ConsumeError",
    "AcknowledgeError",
    # Enums
    "DeliveryMode",
    "AckMode",
    "MessageState",
    # Data classes
    "MessageHeaders",
    "Message",
    "TopicConfig",
    "ConsumerConfig",
    "ProducerConfig",
    # Serializers
    "Serializer",
    "JsonSerializer",
    # Core interfaces
    "Producer",
    "Consumer",
    "MessageBroker",
    # Implementations
    "InMemoryQueue",
    "InMemoryProducer",
    "InMemoryConsumer",
    "InMemoryMessageBroker",
    # Patterns
    "PubSubBroker",
    "RequestReplyBroker",
    "MessageRouter",
    # Registry
    "BrokerRegistry",
    # Decorators
    "message_handler",
    "subscribe_topic",
    # Factory functions
    "create_message_broker",
    "create_pubsub_broker",
    "create_request_reply_broker",
    "create_message_router",
    "create_topic_config",
    "create_consumer_config",
    "create_producer_config",
    "register_broker",
    "get_broker",
]
