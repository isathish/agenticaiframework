"""
Enterprise WebSocket Module.

Provides WebSocket connections, message handling,
room/channel management, and real-time communication.

Example:
    # Create WebSocket server
    ws = create_websocket_server()
    
    # Handle connections
    @ws.on_connect
    async def handle_connect(client: WebSocketClient):
        await client.send("Welcome!")
    
    @ws.on_message("chat")
    async def handle_chat(client: WebSocketClient, data: dict):
        await ws.broadcast("chat", data, room=data.get("room"))
    
    # Client usage
    client = await create_websocket_client("ws://localhost:8080")
    await client.send("chat", {"message": "Hello!"})
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from functools import wraps
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    TypeVar,
    Union,
)

logger = logging.getLogger(__name__)

T = TypeVar('T')


class WebSocketError(Exception):
    """WebSocket error."""
    pass


class ConnectionError(WebSocketError):
    """Connection error."""
    pass


class MessageError(WebSocketError):
    """Message error."""
    pass


class ConnectionState(str, Enum):
    """Connection states."""
    CONNECTING = "connecting"
    OPEN = "open"
    CLOSING = "closing"
    CLOSED = "closed"


class MessageType(str, Enum):
    """Message types."""
    TEXT = "text"
    BINARY = "binary"
    PING = "ping"
    PONG = "pong"
    CLOSE = "close"


@dataclass
class WebSocketMessage:
    """WebSocket message."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: str = ""
    data: Any = None
    timestamp: datetime = field(default_factory=datetime.now)
    client_id: Optional[str] = None
    room: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_json(self) -> str:
        """Convert to JSON."""
        return json.dumps({
            "id": self.id,
            "type": self.type,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        })
    
    @classmethod
    def from_json(cls, data: str) -> 'WebSocketMessage':
        """Create from JSON."""
        parsed = json.loads(data)
        return cls(
            id=parsed.get("id", str(uuid.uuid4())),
            type=parsed.get("type", ""),
            data=parsed.get("data"),
            timestamp=datetime.fromisoformat(parsed["timestamp"]) if parsed.get("timestamp") else datetime.now(),
            metadata=parsed.get("metadata", {}),
        )


@dataclass
class ClientInfo:
    """Client connection info."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    state: ConnectionState = ConnectionState.CONNECTING
    connected_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    rooms: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)
    messages_sent: int = 0
    messages_received: int = 0


@dataclass
class RoomInfo:
    """Room information."""
    name: str
    clients: Set[str] = field(default_factory=set)
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    max_clients: int = 0  # 0 = unlimited


@dataclass
class WebSocketStats:
    """WebSocket statistics."""
    total_connections: int = 0
    active_connections: int = 0
    messages_sent: int = 0
    messages_received: int = 0
    rooms: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0


class WebSocketClient(ABC):
    """Abstract WebSocket client."""
    
    @property
    @abstractmethod
    def id(self) -> str:
        """Get client ID."""
        pass
    
    @property
    @abstractmethod
    def state(self) -> ConnectionState:
        """Get connection state."""
        pass
    
    @abstractmethod
    async def send(
        self,
        message_type: str,
        data: Any = None,
        **metadata: Any,
    ) -> None:
        """Send a message."""
        pass
    
    @abstractmethod
    async def send_raw(self, data: Union[str, bytes]) -> None:
        """Send raw data."""
        pass
    
    @abstractmethod
    async def close(self, code: int = 1000, reason: str = "") -> None:
        """Close the connection."""
        pass
    
    @abstractmethod
    async def ping(self) -> float:
        """Send ping and return latency in ms."""
        pass


class MockWebSocketClient(WebSocketClient):
    """Mock WebSocket client for testing."""
    
    def __init__(self, client_id: Optional[str] = None):
        self._id = client_id or str(uuid.uuid4())
        self._state = ConnectionState.OPEN
        self._info = ClientInfo(id=self._id, state=self._state)
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._sent_messages: List[WebSocketMessage] = []
    
    @property
    def id(self) -> str:
        return self._id
    
    @property
    def state(self) -> ConnectionState:
        return self._state
    
    @property
    def info(self) -> ClientInfo:
        return self._info
    
    async def send(
        self,
        message_type: str,
        data: Any = None,
        **metadata: Any,
    ) -> None:
        """Send a message."""
        message = WebSocketMessage(
            type=message_type,
            data=data,
            client_id=self._id,
            metadata=metadata,
        )
        self._sent_messages.append(message)
        self._info.messages_sent += 1
        logger.debug(f"Client {self._id} sent: {message_type}")
    
    async def send_raw(self, data: Union[str, bytes]) -> None:
        """Send raw data."""
        self._info.messages_sent += 1
    
    async def receive(self, timeout: Optional[float] = None) -> WebSocketMessage:
        """Receive a message."""
        if timeout:
            return await asyncio.wait_for(self._message_queue.get(), timeout)
        return await self._message_queue.get()
    
    async def close(self, code: int = 1000, reason: str = "") -> None:
        """Close the connection."""
        self._state = ConnectionState.CLOSED
        self._info.state = ConnectionState.CLOSED
    
    async def ping(self) -> float:
        """Send ping."""
        return 1.0  # Mock 1ms latency
    
    def _receive_message(self, message: WebSocketMessage) -> None:
        """Simulate receiving a message."""
        self._message_queue.put_nowait(message)
        self._info.messages_received += 1
        self._info.last_activity = datetime.now()


class Room:
    """WebSocket room for group messaging."""
    
    def __init__(self, name: str, max_clients: int = 0):
        self._name = name
        self._clients: Dict[str, WebSocketClient] = {}
        self._info = RoomInfo(name=name, max_clients=max_clients)
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def info(self) -> RoomInfo:
        return self._info
    
    @property
    def clients(self) -> List[WebSocketClient]:
        return list(self._clients.values())
    
    @property
    def client_count(self) -> int:
        return len(self._clients)
    
    def add(self, client: WebSocketClient) -> bool:
        """Add client to room."""
        if self._info.max_clients > 0 and len(self._clients) >= self._info.max_clients:
            return False
        
        self._clients[client.id] = client
        self._info.clients.add(client.id)
        
        if hasattr(client, '_info'):
            client._info.rooms.add(self._name)
        
        return True
    
    def remove(self, client_id: str) -> bool:
        """Remove client from room."""
        if client_id in self._clients:
            client = self._clients.pop(client_id)
            self._info.clients.discard(client_id)
            
            if hasattr(client, '_info'):
                client._info.rooms.discard(self._name)
            
            return True
        return False
    
    async def broadcast(
        self,
        message_type: str,
        data: Any = None,
        exclude: Optional[Set[str]] = None,
        **metadata: Any,
    ) -> int:
        """Broadcast message to all clients in room."""
        exclude = exclude or set()
        count = 0
        
        for client in self._clients.values():
            if client.id not in exclude:
                try:
                    await client.send(message_type, data, **metadata)
                    count += 1
                except Exception as e:
                    logger.error(f"Broadcast to {client.id} failed: {e}")
        
        return count
    
    def has(self, client_id: str) -> bool:
        """Check if client is in room."""
        return client_id in self._clients


class WebSocketServer:
    """
    WebSocket server for managing connections and messaging.
    """
    
    def __init__(self):
        self._clients: Dict[str, WebSocketClient] = {}
        self._rooms: Dict[str, Room] = {}
        self._handlers: Dict[str, Callable] = {}
        self._middleware: List[Callable] = []
        self._stats = WebSocketStats()
        
        # Event handlers
        self._on_connect: Optional[Callable] = None
        self._on_disconnect: Optional[Callable] = None
        self._on_error: Optional[Callable] = None
    
    @property
    def clients(self) -> List[WebSocketClient]:
        """Get all connected clients."""
        return list(self._clients.values())
    
    @property
    def rooms(self) -> List[Room]:
        """Get all rooms."""
        return list(self._rooms.values())
    
    def on_connect(self, handler: Callable[[WebSocketClient], Awaitable[None]]) -> Callable:
        """Set connection handler."""
        self._on_connect = handler
        return handler
    
    def on_disconnect(self, handler: Callable[[WebSocketClient], Awaitable[None]]) -> Callable:
        """Set disconnection handler."""
        self._on_disconnect = handler
        return handler
    
    def on_error(self, handler: Callable[[WebSocketClient, Exception], Awaitable[None]]) -> Callable:
        """Set error handler."""
        self._on_error = handler
        return handler
    
    def on_message(self, message_type: str) -> Callable:
        """
        Decorator to handle specific message types.
        
        Example:
            @ws.on_message("chat")
            async def handle_chat(client, data):
                ...
        """
        def decorator(handler: Callable) -> Callable:
            self._handlers[message_type] = handler
            return handler
        return decorator
    
    def use(self, middleware: Callable) -> None:
        """Add middleware."""
        self._middleware.append(middleware)
    
    async def connect(self, client: WebSocketClient) -> None:
        """Handle new connection."""
        self._clients[client.id] = client
        self._stats.total_connections += 1
        self._stats.active_connections += 1
        
        if self._on_connect:
            await self._on_connect(client)
        
        logger.info(f"Client connected: {client.id}")
    
    async def disconnect(self, client_id: str) -> None:
        """Handle disconnection."""
        client = self._clients.pop(client_id, None)
        
        if client:
            # Remove from all rooms
            for room in list(self._rooms.values()):
                room.remove(client_id)
            
            self._stats.active_connections -= 1
            
            if self._on_disconnect:
                await self._on_disconnect(client)
            
            logger.info(f"Client disconnected: {client_id}")
    
    async def handle_message(
        self,
        client: WebSocketClient,
        raw_message: str,
    ) -> None:
        """Handle incoming message."""
        try:
            message = WebSocketMessage.from_json(raw_message)
            message.client_id = client.id
            
            self._stats.messages_received += 1
            self._stats.bytes_received += len(raw_message)
            
            # Apply middleware
            for mw in self._middleware:
                message = await mw(client, message)
                if message is None:
                    return
            
            # Find handler
            handler = self._handlers.get(message.type)
            
            if handler:
                await handler(client, message.data)
            else:
                # Try wildcard handler
                wildcard = self._handlers.get("*")
                if wildcard:
                    await wildcard(client, message)
            
        except Exception as e:
            logger.error(f"Message handling error: {e}")
            if self._on_error:
                await self._on_error(client, e)
    
    async def send(
        self,
        client_id: str,
        message_type: str,
        data: Any = None,
        **metadata: Any,
    ) -> bool:
        """Send message to specific client."""
        client = self._clients.get(client_id)
        
        if client and client.state == ConnectionState.OPEN:
            await client.send(message_type, data, **metadata)
            self._stats.messages_sent += 1
            return True
        
        return False
    
    async def broadcast(
        self,
        message_type: str,
        data: Any = None,
        room: Optional[str] = None,
        exclude: Optional[Set[str]] = None,
        **metadata: Any,
    ) -> int:
        """Broadcast message to clients."""
        exclude = exclude or set()
        count = 0
        
        if room:
            room_obj = self._rooms.get(room)
            if room_obj:
                count = await room_obj.broadcast(message_type, data, exclude, **metadata)
        else:
            for client in self._clients.values():
                if client.id not in exclude and client.state == ConnectionState.OPEN:
                    try:
                        await client.send(message_type, data, **metadata)
                        count += 1
                    except Exception as e:
                        logger.error(f"Broadcast to {client.id} failed: {e}")
        
        self._stats.messages_sent += count
        return count
    
    def create_room(self, name: str, max_clients: int = 0) -> Room:
        """Create a room."""
        room = Room(name, max_clients)
        self._rooms[name] = room
        self._stats.rooms += 1
        return room
    
    def get_room(self, name: str) -> Optional[Room]:
        """Get a room by name."""
        return self._rooms.get(name)
    
    def delete_room(self, name: str) -> bool:
        """Delete a room."""
        if name in self._rooms:
            del self._rooms[name]
            self._stats.rooms -= 1
            return True
        return False
    
    async def join_room(self, client_id: str, room_name: str) -> bool:
        """Add client to a room."""
        client = self._clients.get(client_id)
        room = self._rooms.get(room_name)
        
        if not room:
            room = self.create_room(room_name)
        
        if client:
            return room.add(client)
        
        return False
    
    async def leave_room(self, client_id: str, room_name: str) -> bool:
        """Remove client from a room."""
        room = self._rooms.get(room_name)
        
        if room:
            return room.remove(client_id)
        
        return False
    
    async def get_stats(self) -> WebSocketStats:
        """Get server statistics."""
        return self._stats
    
    def get_client(self, client_id: str) -> Optional[WebSocketClient]:
        """Get client by ID."""
        return self._clients.get(client_id)


class ConnectionManager:
    """
    Manage WebSocket connections with heartbeat and cleanup.
    """
    
    def __init__(
        self,
        server: WebSocketServer,
        heartbeat_interval: float = 30.0,
        client_timeout: float = 60.0,
    ):
        self._server = server
        self._heartbeat_interval = heartbeat_interval
        self._client_timeout = client_timeout
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    async def start(self) -> None:
        """Start connection management."""
        self._running = True
        self._task = asyncio.create_task(self._heartbeat_loop())
        logger.info("Connection manager started")
    
    async def stop(self) -> None:
        """Stop connection management."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
    
    async def _heartbeat_loop(self) -> None:
        """Heartbeat loop."""
        while self._running:
            try:
                await self._check_connections()
                await asyncio.sleep(self._heartbeat_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
    
    async def _check_connections(self) -> None:
        """Check all connections."""
        now = datetime.now()
        disconnected = []
        
        for client in self._server.clients:
            try:
                # Check if client has timed out
                if hasattr(client, '_info'):
                    last_activity = client._info.last_activity
                    elapsed = (now - last_activity).total_seconds()
                    
                    if elapsed > self._client_timeout:
                        disconnected.append(client.id)
                        continue
                
                # Send ping
                await client.ping()
                
            except Exception as e:
                logger.warning(f"Client {client.id} heartbeat failed: {e}")
                disconnected.append(client.id)
        
        # Disconnect timed out clients
        for client_id in disconnected:
            await self._server.disconnect(client_id)


# Decorators
def websocket_handler(message_type: str) -> Callable:
    """
    Decorator to mark a function as a WebSocket message handler.
    
    Example:
        @websocket_handler("chat")
        async def handle_chat(client: WebSocketClient, data: dict):
            ...
    """
    def decorator(func: Callable) -> Callable:
        func._ws_message_type = message_type
        return func
    
    return decorator


def require_room(room_name: str) -> Callable:
    """
    Decorator to require client to be in a specific room.
    
    Example:
        @require_room("vip")
        async def handle_vip_message(client, data):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(client: WebSocketClient, *args: Any, **kwargs: Any) -> Any:
            if hasattr(client, '_info') and room_name in client._info.rooms:
                return await func(client, *args, **kwargs)
            else:
                logger.warning(f"Client {client.id} not in room {room_name}")
                return None
        return wrapper
    return decorator


# Factory functions
def create_websocket_server() -> WebSocketServer:
    """Create a WebSocket server."""
    return WebSocketServer()


def create_mock_client(client_id: Optional[str] = None) -> MockWebSocketClient:
    """Create a mock WebSocket client for testing."""
    return MockWebSocketClient(client_id)


def create_room(name: str, max_clients: int = 0) -> Room:
    """Create a standalone room."""
    return Room(name, max_clients)


def create_connection_manager(
    server: WebSocketServer,
    heartbeat_interval: float = 30.0,
    client_timeout: float = 60.0,
) -> ConnectionManager:
    """Create a connection manager."""
    return ConnectionManager(server, heartbeat_interval, client_timeout)


__all__ = [
    # Exceptions
    "WebSocketError",
    "ConnectionError",
    "MessageError",
    # Enums
    "ConnectionState",
    "MessageType",
    # Data classes
    "WebSocketMessage",
    "ClientInfo",
    "RoomInfo",
    "WebSocketStats",
    # Core classes
    "WebSocketClient",
    "MockWebSocketClient",
    "Room",
    "WebSocketServer",
    "ConnectionManager",
    # Decorators
    "websocket_handler",
    "require_room",
    # Factory
    "create_websocket_server",
    "create_mock_client",
    "create_room",
    "create_connection_manager",
]
