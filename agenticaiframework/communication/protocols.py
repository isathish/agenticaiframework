"""
Communication Protocols for Agent-to-Agent Communication.

Supports:
- STDIO: Standard input/output for subprocess communication
- HTTP/HTTPS: RESTful API calls
- SSE: Server-Sent Events for streaming
- MQTT: Message queue protocol
- WebSocket: Bidirectional streaming
"""

import os
import sys
import json
import uuid
import time
import logging
import threading
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterator, List, Optional, Union
from enum import Enum
from queue import Queue, Empty
from datetime import datetime

logger = logging.getLogger(__name__)


class ProtocolType(Enum):
    """Communication protocol types."""
    STDIO = "stdio"
    HTTP = "http"
    HTTPS = "https"
    SSE = "sse"
    MQTT = "mqtt"
    WEBSOCKET = "websocket"


@dataclass
class ProtocolConfig:
    """Configuration for communication protocols."""
    protocol_type: ProtocolType
    host: str = "localhost"
    port: int = 8080
    path: str = "/"
    timeout: float = 30.0
    retry_count: int = 3
    retry_delay: float = 1.0
    headers: Dict[str, str] = field(default_factory=dict)
    auth_token: Optional[str] = None
    ssl_verify: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


class CommunicationProtocol(ABC):
    """Base class for communication protocols."""
    
    def __init__(self, config: Optional[ProtocolConfig] = None):
        self.config = config or ProtocolConfig(protocol_type=ProtocolType.HTTP)
        self.is_connected = False
        self._message_handlers: List[Callable] = []
        self._connection_id = str(uuid.uuid4())
    
    @abstractmethod
    def connect(self) -> bool:
        """Establish connection."""
        pass
    
    @abstractmethod
    def disconnect(self) -> bool:
        """Close connection."""
        pass
    
    @abstractmethod
    def send(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Send a message and get response."""
        pass
    
    @abstractmethod
    def receive(self, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """Receive a message."""
        pass
    
    def on_message(self, handler: Callable[[Dict[str, Any]], None]) -> None:
        """Register a message handler."""
        self._message_handlers.append(handler)
    
    def _notify_handlers(self, message: Dict[str, Any]) -> None:
        """Notify all message handlers."""
        for handler in self._message_handlers:
            try:
                handler(message)
            except Exception as e:
                logger.error(f"Message handler error: {e}")


class STDIOProtocol(CommunicationProtocol):
    """
    STDIO Protocol for subprocess communication.
    
    Enables agent-to-agent communication via standard input/output,
    useful for local process communication and MCP-style tools.
    
    Example:
        >>> protocol = STDIOProtocol(command=["python", "remote_agent.py"])
        >>> protocol.connect()
        >>> response = protocol.send({"type": "query", "content": "Hello"})
    """
    
    def __init__(
        self,
        command: Optional[List[str]] = None,
        config: Optional[ProtocolConfig] = None,
        encoding: str = "utf-8",
    ):
        config = config or ProtocolConfig(protocol_type=ProtocolType.STDIO)
        super().__init__(config)
        self.command = command or []
        self.encoding = encoding
        self._process: Optional[subprocess.Popen] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._message_queue: Queue = Queue()
        self._running = False
    
    def connect(self) -> bool:
        """Start the subprocess."""
        if not self.command:
            logger.error("No command specified for STDIO protocol")
            return False
        
        try:
            self._process = subprocess.Popen(
                self.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding=self.encoding,
            )
            
            self._running = True
            self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
            self._reader_thread.start()
            
            self.is_connected = True
            logger.info(f"STDIO connected to: {' '.join(self.command)}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start STDIO process: {e}")
            return False
    
    def disconnect(self) -> bool:
        """Stop the subprocess."""
        self._running = False
        
        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
            self._process = None
        
        self.is_connected = False
        return True
    
    def send(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Send message via STDIN and wait for response from STDOUT."""
        if not self._process or not self._process.stdin:
            return {"error": "Not connected"}
        
        try:
            # Write JSON message + newline
            msg_str = json.dumps(message) + "\n"
            self._process.stdin.write(msg_str)
            self._process.stdin.flush()
            
            # Wait for response
            response = self.receive(timeout=self.config.timeout)
            return response or {"error": "No response"}
            
        except Exception as e:
            logger.error(f"STDIO send error: {e}")
            return {"error": str(e)}
    
    def receive(self, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """Receive message from queue."""
        try:
            return self._message_queue.get(timeout=timeout or self.config.timeout)
        except Empty:
            return None
    
    def _read_loop(self) -> None:
        """Background thread to read from STDOUT."""
        while self._running and self._process and self._process.stdout:
            try:
                line = self._process.stdout.readline()
                if line:
                    message = json.loads(line.strip())
                    self._message_queue.put(message)
                    self._notify_handlers(message)
            except json.JSONDecodeError:
                pass
            except Exception as e:
                if self._running:
                    logger.error(f"STDIO read error: {e}")
                break


class HTTPProtocol(CommunicationProtocol):
    """
    HTTP/HTTPS Protocol for REST-based agent communication.
    
    Example:
        >>> protocol = HTTPProtocol(
        ...     host="remote-agent.example.com",
        ...     port=443,
        ...     path="/api/agent",
        ...     use_ssl=True
        ... )
        >>> protocol.connect()
        >>> response = protocol.send({"prompt": "Hello", "action": "query"})
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 8080,
        path: str = "/",
        use_ssl: bool = False,
        config: Optional[ProtocolConfig] = None,
    ):
        protocol_type = ProtocolType.HTTPS if use_ssl else ProtocolType.HTTP
        config = config or ProtocolConfig(
            protocol_type=protocol_type,
            host=host,
            port=port,
            path=path,
        )
        super().__init__(config)
        self.use_ssl = use_ssl
        self._session = None
    
    @property
    def base_url(self) -> str:
        """Get base URL."""
        scheme = "https" if self.use_ssl else "http"
        return f"{scheme}://{self.config.host}:{self.config.port}"
    
    def connect(self) -> bool:
        """Initialize HTTP session."""
        try:
            import requests
            self._session = requests.Session()
            
            # Set default headers
            self._session.headers.update({
                "Content-Type": "application/json",
                "Accept": "application/json",
                **self.config.headers,
            })
            
            if self.config.auth_token:
                self._session.headers["Authorization"] = f"Bearer {self.config.auth_token}"
            
            # Verify connection with health check
            try:
                health_url = f"{self.base_url}/health"
                resp = self._session.get(health_url, timeout=5)
                if resp.status_code < 500:
                    self.is_connected = True
                    return True
            except Exception:  # noqa: BLE001 - Health check failure is non-critical
                pass
            
            # Even if health check fails, mark as connected
            self.is_connected = True
            return True
            
        except ImportError:
            logger.error("HTTP protocol requires: pip install requests")
            return False
        except Exception as e:
            logger.error(f"HTTP connection error: {e}")
            return False
    
    def disconnect(self) -> bool:
        """Close HTTP session."""
        if self._session:
            self._session.close()
            self._session = None
        self.is_connected = False
        return True
    
    def send(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Send HTTP POST request."""
        if not self._session:
            return {"error": "Not connected"}
        
        url = f"{self.base_url}{self.config.path}"
        
        for attempt in range(self.config.retry_count):
            try:
                response = self._session.post(
                    url,
                    json=message,
                    timeout=self.config.timeout,
                    verify=self.config.ssl_verify,
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    return {
                        "error": f"HTTP {response.status_code}",
                        "status_code": response.status_code,
                        "body": response.text[:500],
                    }
                    
            except Exception as e:
                if attempt < self.config.retry_count - 1:
                    time.sleep(self.config.retry_delay)
                else:
                    return {"error": str(e)}
        
        return {"error": "Max retries exceeded"}
    
    def receive(self, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """HTTP is request/response, so this polls an endpoint."""
        if not self._session:
            return None
        
        try:
            url = f"{self.base_url}{self.config.path}/receive"
            response = self._session.get(url, timeout=timeout or self.config.timeout)
            if response.status_code == 200:
                return response.json()
        except Exception:  # noqa: BLE001 - Receive failures return None
            pass
        return None
    
    def get(self, path: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Send HTTP GET request."""
        if not self._session:
            return {"error": "Not connected"}
        
        try:
            url = f"{self.base_url}{path}"
            response = self._session.get(url, params=params, timeout=self.config.timeout)
            return response.json() if response.status_code == 200 else {"error": response.text}
        except Exception as e:
            return {"error": str(e)}


class SSEProtocol(CommunicationProtocol):
    """
    Server-Sent Events Protocol for streaming agent communication.
    
    Ideal for:
    - Real-time agent responses
    - Streaming LLM output
    - Live updates from remote agents
    
    Example:
        >>> protocol = SSEProtocol(
        ...     host="agent.example.com",
        ...     path="/stream"
        ... )
        >>> protocol.connect()
        >>> for event in protocol.stream():
        ...     print(event)
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 8080,
        path: str = "/events",
        use_ssl: bool = False,
        config: Optional[ProtocolConfig] = None,
    ):
        config = config or ProtocolConfig(
            protocol_type=ProtocolType.SSE,
            host=host,
            port=port,
            path=path,
        )
        super().__init__(config)
        self.use_ssl = use_ssl
        self._session = None
        self._stream_response = None
        self._event_queue: Queue = Queue()
    
    @property
    def base_url(self) -> str:
        scheme = "https" if self.use_ssl else "http"
        return f"{scheme}://{self.config.host}:{self.config.port}"
    
    def connect(self) -> bool:
        """Initialize SSE connection."""
        try:
            import requests
            self._session = requests.Session()
            self._session.headers.update({
                "Accept": "text/event-stream",
                **self.config.headers,
            })
            
            if self.config.auth_token:
                self._session.headers["Authorization"] = f"Bearer {self.config.auth_token}"
            
            self.is_connected = True
            return True
            
        except ImportError:
            logger.error("SSE protocol requires: pip install requests")
            return False
    
    def disconnect(self) -> bool:
        """Close SSE connection."""
        if self._stream_response:
            self._stream_response.close()
        if self._session:
            self._session.close()
        self.is_connected = False
        return True
    
    def send(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Send message and return immediate acknowledgment."""
        if not self._session:
            return {"error": "Not connected"}
        
        try:
            url = f"{self.base_url}{self.config.path}"
            response = self._session.post(url, json=message, timeout=self.config.timeout)
            return response.json() if response.status_code == 200 else {"error": response.text}
        except Exception as e:
            return {"error": str(e)}
    
    def receive(self, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """Receive next event from queue."""
        try:
            return self._event_queue.get(timeout=timeout or 1.0)
        except Empty:
            return None
    
    def stream(self, path: Optional[str] = None) -> Iterator[Dict[str, Any]]:
        """
        Stream events from SSE endpoint.
        
        Yields:
            Parsed event dictionaries
        """
        if not self._session:
            return
        
        url = f"{self.base_url}{path or self.config.path}"
        
        try:
            response = self._session.get(url, stream=True, timeout=None)
            self._stream_response = response
            
            event_data = []
            event_type = "message"
            
            for line in response.iter_lines(decode_unicode=True):
                if line.startswith("event:"):
                    event_type = line[6:].strip()
                elif line.startswith("data:"):
                    event_data.append(line[5:].strip())
                elif line == "" and event_data:
                    # End of event
                    data_str = "\n".join(event_data)
                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        data = {"raw": data_str}
                    
                    event = {
                        "type": event_type,
                        "data": data,
                        "timestamp": datetime.now().isoformat(),
                    }
                    self._notify_handlers(event)
                    yield event
                    
                    event_data = []
                    event_type = "message"
                    
        except Exception as e:
            logger.error(f"SSE stream error: {e}")
    
    def send_and_stream(
        self,
        message: Dict[str, Any],
        path: Optional[str] = None,
    ) -> Iterator[Dict[str, Any]]:
        """Send a message and stream the response."""
        if not self._session:
            return
        
        url = f"{self.base_url}{path or self.config.path}"
        
        try:
            response = self._session.post(
                url,
                json=message,
                stream=True,
                headers={"Accept": "text/event-stream"},
            )
            
            for line in response.iter_lines(decode_unicode=True):
                if line.startswith("data:"):
                    data_str = line[5:].strip()
                    try:
                        yield json.loads(data_str)
                    except (json.JSONDecodeError, ValueError):
                        yield {"raw": data_str}
                        
        except Exception as e:
            logger.error(f"SSE send_and_stream error: {e}")


class MQTTProtocol(CommunicationProtocol):
    """
    MQTT Protocol for message queue-based agent communication.
    
    Ideal for:
    - IoT and edge agent communication
    - Pub/sub agent networks
    - Distributed agent systems
    
    Example:
        >>> protocol = MQTTProtocol(
        ...     broker="mqtt.example.com",
        ...     topic="agents/my-agent"
        ... )
        >>> protocol.connect()
        >>> protocol.subscribe("agents/+/responses")
        >>> protocol.send({"action": "query"})
    """
    
    def __init__(
        self,
        broker: str = "localhost",
        port: int = 1883,
        topic: str = "agents/default",
        client_id: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        use_ssl: bool = False,
        config: Optional[ProtocolConfig] = None,
    ):
        config = config or ProtocolConfig(
            protocol_type=ProtocolType.MQTT,
            host=broker,
            port=port,
        )
        super().__init__(config)
        self.broker = broker
        self.port = port
        self.topic = topic
        self.client_id = client_id or f"agent-{uuid.uuid4().hex[:8]}"
        self.username = username
        self.password = password
        self.use_ssl = use_ssl
        self._client = None
        self._message_queue: Queue = Queue()
        self._subscriptions: List[str] = []
    
    def connect(self) -> bool:
        """Connect to MQTT broker."""
        try:
            import paho.mqtt.client as mqtt
        except ImportError:
            logger.error("MQTT protocol requires: pip install paho-mqtt")
            return False
        
        try:
            self._client = mqtt.Client(client_id=self.client_id)
            
            if self.username and self.password:
                self._client.username_pw_set(self.username, self.password)
            
            if self.use_ssl:
                self._client.tls_set()
            
            # Set callbacks
            self._client.on_connect = self._on_connect
            self._client.on_message = self._on_message
            self._client.on_disconnect = self._on_disconnect
            
            self._client.connect(self.broker, self.port, keepalive=60)
            self._client.loop_start()
            
            # Wait for connection
            time.sleep(1)
            return self.is_connected
            
        except Exception as e:
            logger.error(f"MQTT connection error: {e}")
            return False
    
    def disconnect(self) -> bool:
        """Disconnect from MQTT broker."""
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
            self._client = None
        self.is_connected = False
        return True
    
    def send(self, message: Dict[str, Any], topic: Optional[str] = None) -> Dict[str, Any]:
        """Publish message to topic."""
        if not self._client:
            return {"error": "Not connected"}
        
        try:
            publish_topic = topic or self.topic
            payload = json.dumps(message)
            result = self._client.publish(publish_topic, payload)
            
            return {
                "status": "published",
                "topic": publish_topic,
                "message_id": result.mid,
            }
        except Exception as e:
            return {"error": str(e)}
    
    def receive(self, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """Receive message from subscription."""
        try:
            return self._message_queue.get(timeout=timeout or self.config.timeout)
        except Empty:
            return None
    
    def subscribe(self, topic: str, qos: int = 0) -> bool:
        """Subscribe to a topic."""
        if not self._client:
            return False
        
        try:
            self._client.subscribe(topic, qos)
            self._subscriptions.append(topic)
            logger.info(f"Subscribed to MQTT topic: {topic}")
            return True
        except Exception as e:
            logger.error(f"MQTT subscribe error: {e}")
            return False
    
    def unsubscribe(self, topic: str) -> bool:
        """Unsubscribe from a topic."""
        if not self._client:
            return False
        
        try:
            self._client.unsubscribe(topic)
            self._subscriptions.remove(topic)
            return True
        except (ValueError, KeyError, Exception):  # noqa: BLE001
            return False
    
    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.is_connected = True
            logger.info(f"MQTT connected to {self.broker}")
            # Re-subscribe to topics
            for topic in self._subscriptions:
                client.subscribe(topic)
        else:
            logger.error(f"MQTT connection failed: {rc}")
    
    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            message = {
                "topic": msg.topic,
                "payload": payload,
                "timestamp": datetime.now().isoformat(),
            }
            self._message_queue.put(message)
            self._notify_handlers(message)
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON in MQTT message: {msg.payload}")
    
    def _on_disconnect(self, client, userdata, rc):
        self.is_connected = False
        if rc != 0:
            logger.warning(f"MQTT unexpected disconnect: {rc}")


class WebSocketProtocol(CommunicationProtocol):
    """
    WebSocket Protocol for bidirectional real-time communication.
    
    Example:
        >>> protocol = WebSocketProtocol(
        ...     host="agent.example.com",
        ...     path="/ws/agent"
        ... )
        >>> protocol.connect()
        >>> response = protocol.send({"type": "query", "content": "Hello"})
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 8080,
        path: str = "/ws",
        use_ssl: bool = False,
        config: Optional[ProtocolConfig] = None,
    ):
        config = config or ProtocolConfig(
            protocol_type=ProtocolType.WEBSOCKET,
            host=host,
            port=port,
            path=path,
        )
        super().__init__(config)
        self.use_ssl = use_ssl
        self._ws = None
        self._message_queue: Queue = Queue()
        self._receiver_thread: Optional[threading.Thread] = None
        self._running = False
    
    @property
    def ws_url(self) -> str:
        scheme = "wss" if self.use_ssl else "ws"
        return f"{scheme}://{self.config.host}:{self.config.port}{self.config.path}"
    
    def connect(self) -> bool:
        """Connect to WebSocket server."""
        try:
            import websocket
        except ImportError:
            logger.error("WebSocket protocol requires: pip install websocket-client")
            return False
        
        try:
            headers = dict(self.config.headers)
            if self.config.auth_token:
                headers["Authorization"] = f"Bearer {self.config.auth_token}"
            
            self._ws = websocket.create_connection(
                self.ws_url,
                header=headers,
                timeout=self.config.timeout,
            )
            
            self._running = True
            self._receiver_thread = threading.Thread(target=self._receive_loop, daemon=True)
            self._receiver_thread.start()
            
            self.is_connected = True
            logger.info(f"WebSocket connected to: {self.ws_url}")
            return True
            
        except Exception as e:
            logger.error(f"WebSocket connection error: {e}")
            return False
    
    def disconnect(self) -> bool:
        """Close WebSocket connection."""
        self._running = False
        if self._ws:
            try:
                self._ws.close()
            except Exception:  # noqa: BLE001 - Ignore close errors
                pass
            self._ws = None
        self.is_connected = False
        return True
    
    def send(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Send message and wait for response."""
        if not self._ws:
            return {"error": "Not connected"}
        
        try:
            msg_id = str(uuid.uuid4())
            message["_msg_id"] = msg_id
            
            self._ws.send(json.dumps(message))
            
            # Wait for response with matching ID
            start = time.time()
            while time.time() - start < self.config.timeout:
                response = self.receive(timeout=0.5)
                if response and response.get("_reply_to") == msg_id:
                    return response
            
            return {"error": "Response timeout"}
            
        except Exception as e:
            return {"error": str(e)}
    
    def send_nowait(self, message: Dict[str, Any]) -> bool:
        """Send message without waiting for response."""
        if not self._ws:
            return False
        
        try:
            self._ws.send(json.dumps(message))
            return True
        except (OSError, ConnectionError, Exception):  # noqa: BLE001
            return False
    
    def receive(self, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """Receive message from queue."""
        try:
            return self._message_queue.get(timeout=timeout or 0.1)
        except Empty:
            return None
    
    def _receive_loop(self) -> None:
        """Background receiver loop."""
        while self._running and self._ws:
            try:
                data = self._ws.recv()
                if data:
                    message = json.loads(data)
                    self._message_queue.put(message)
                    self._notify_handlers(message)
            except json.JSONDecodeError:
                pass
            except Exception as e:
                if self._running:
                    logger.error(f"WebSocket receive error: {e}")
                break


__all__ = [
    "ProtocolType",
    "ProtocolConfig",
    "CommunicationProtocol",
    "STDIOProtocol",
    "HTTPProtocol",
    "SSEProtocol",
    "MQTTProtocol",
    "WebSocketProtocol",
]
