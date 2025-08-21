"""
Agentic Framework Communication Protocols Module

This module provides implementations for various communication protocols used within the Agentic Framework.
It supports Streamtable HTTP, SSE (Server-Sent Events), STDIO, WebSockets, gRPC, and Message Queues for reliable,
efficient, and secure data exchange between agents and other components. The module includes mechanisms for protocol
selection, security enforcement, and performance monitoring.
"""

from typing import Any, Dict, List, Optional, Callable, Set
from datetime import datetime
import time
import threading
import json
import asyncio
import websockets
import http.client
import grpc
from concurrent import futures
import queue
import sys
import os

# Custom exceptions for communication errors
class CommunicationError(Exception):
    """Base exception for communication-related errors."""
    pass

class ProtocolNotSupportedError(CommunicationError):
    """Raised when a requested protocol is not supported."""
    pass

class ConnectionFailedError(CommunicationError):
    """Raised when a connection attempt fails."""
    pass

class SecurityViolationError(CommunicationError):
    """Raised when a security policy is violated during communication."""
    pass

# Protocol interface for different communication methods
class CommunicationProtocol:
    """Base class for all communication protocols in the Agentic Framework."""
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.active = False
        self.security_enabled = config.get("security_enabled", True)
        self.encryption_method = config.get("encryption_method", "TLS")
        self.auth_method = config.get("auth_method", "OAuth2")
        self.performance_metrics = {
            "total_messages": 0,
            "successful_messages": 0,
            "failed_messages": 0,
            "average_latency_ms": 0.0,
            "last_message_time": 0.0
        }
        self.connection_log: List[str] = []
        self.last_updated = time.time()
        self.lock = threading.Lock()

    def activate(self) -> None:
        """Activate the protocol for use."""
        with self.lock:
            self.active = True
            self.connection_log.append(f"Protocol {self.name} activated at {datetime.now().isoformat()}")
            self.last_updated = time.time()

    def deactivate(self) -> None:
        """Deactivate the protocol."""
        with self.lock:
            self.active = False
            self.connection_log.append(f"Protocol {self.name} deactivated at {datetime.now().isoformat()}")
            self.last_updated = time.time()

    def send(self, data: Any, destination: str, context: Optional[Dict[str, Any]] = None) -> Any:
        """Send data to a destination using the protocol. To be implemented by subclasses."""
        raise NotImplementedError(f"Send method not implemented for protocol {self.name}")

    def receive(self, source: str, timeout: float = 10.0, context: Optional[Dict[str, Any]] = None) -> Any:
        """Receive data from a source using the protocol. To be implemented by subclasses."""
        raise NotImplementedError(f"Receive method not implemented for protocol {self.name}")

    def enforce_security(self, data: Any, operation: str) -> bool:
        """Enforce security policies on the data for the given operation (send/receive)."""
        if not self.security_enabled:
            return True
        # Placeholder for security checks (e.g., encryption, authentication)
        self.connection_log.append(f"Security check for {operation} on protocol {self.name} at {datetime.now().isoformat()}")
        return True

    def update_performance_metrics(self, start_time: float, end_time: float, success: bool) -> None:
        """Update performance metrics based on message transmission result."""
        with self.lock:
            latency = (end_time - start_time) * 1000  # Convert to milliseconds
            self.performance_metrics["total_messages"] += 1
            if success:
                self.performance_metrics["successful_messages"] += 1
            else:
                self.performance_metrics["failed_messages"] += 1
            total_time = self.performance_metrics["average_latency_ms"] * (self.performance_metrics["total_messages"] - 1)
            self.performance_metrics["average_latency_ms"] = (total_time + latency) / self.performance_metrics["total_messages"]
            self.performance_metrics["last_message_time"] = end_time
            self.last_updated = time.time()

# Implementation of Streamtable HTTP Protocol
class StreamtableHTTPProtocol(CommunicationProtocol):
    """Implementation of Streamtable HTTP protocol for real-time structured data streaming."""
    def __init__(self, config: Dict[str, Any]):
        super().__init__("StreamtableHTTP", config)
        self.host = config.get("host", "localhost")
        self.port = config.get("port", 8080)
        self.connection = None

    def activate(self) -> None:
        """Activate the Streamtable HTTP connection."""
        with self.lock:
            try:
                self.connection = http.client.HTTPConnection(self.host, self.port, timeout=10)
                self.active = True
                self.connection_log.append(f"StreamtableHTTP connection established to {self.host}:{self.port} at {datetime.now().isoformat()}")
            except Exception as e:
                self.connection_log.append(f"Failed to establish StreamtableHTTP connection: {str(e)} at {datetime.now().isoformat()}")
                raise ConnectionFailedError(f"Failed to connect StreamtableHTTP to {self.host}:{self.port}: {str(e)}")
            finally:
                self.last_updated = time.time()

    def deactivate(self) -> None:
        """Deactivate the Streamtable HTTP connection."""
        with self.lock:
            if self.connection:
                self.connection.close()
                self.connection = None
            self.active = False
            self.connection_log.append(f"StreamtableHTTP connection closed at {datetime.now().isoformat()}")
            self.last_updated = time.time()

    def send(self, data: Any, destination: str, context: Optional[Dict[str, Any]] = None) -> Any:
        """Send data using Streamtable HTTP protocol."""
        if not self.active:
            raise CommunicationError("StreamtableHTTP protocol is not active")
        if not self.enforce_security(data, "send"):
            raise SecurityViolationError("Security check failed for send operation on StreamtableHTTP")
        start_time = time.time()
        try:
            # Simulate sending data over HTTP with streaming support
            headers = {"Content-Type": "application/json", "Destination": destination}
            body = json.dumps({"data": data, "context": context or {}})
            self.connection.request("POST", "/stream", body=body, headers=headers)
            response = self.connection.getresponse()
            result = response.read().decode()
            end_time = time.time()
            self.update_performance_metrics(start_time, end_time, success=True)
            self.connection_log.append(f"StreamtableHTTP sent data to {destination} at {datetime.now().isoformat()}")
            return result
        except Exception as e:
            end_time = time.time()
            self.update_performance_metrics(start_time, end_time, success=False)
            self.connection_log.append(f"StreamtableHTTP send failed to {destination}: {str(e)} at {datetime.now().isoformat()}")
            raise CommunicationError(f"StreamtableHTTP send error: {str(e)}")

    def receive(self, source: str, timeout: float = 10.0, context: Optional[Dict[str, Any]] = None) -> Any:
        """Receive data using Streamtable HTTP protocol."""
        if not self.active:
            raise CommunicationError("StreamtableHTTP protocol is not active")
        start_time = time.time()
        try:
            # Simulate receiving streamed data over HTTP
            headers = {"Source": source, "Timeout": str(timeout)}
            self.connection.request("GET", "/stream", headers=headers)
            response = self.connection.getresponse()
            data = response.read().decode()
            end_time = time.time()
            if self.enforce_security(data, "receive"):
                self.update_performance_metrics(start_time, end_time, success=True)
                self.connection_log.append(f"StreamtableHTTP received data from {source} at {datetime.now().isoformat()}")
                return json.loads(data) if data else None
            else:
                self.update_performance_metrics(start_time, end_time, success=False)
                raise SecurityViolationError("Security check failed for receive operation on StreamtableHTTP")
        except Exception as e:
            end_time = time.time()
            self.update_performance_metrics(start_time, end_time, success=False)
            self.connection_log.append(f"StreamtableHTTP receive failed from {source}: {str(e)} at {datetime.now().isoformat()}")
            raise CommunicationError(f"StreamtableHTTP receive error: {str(e)}")

# Implementation of Server-Sent Events (SSE) Protocol
class SSEProtocol(CommunicationProtocol):
    """Implementation of Server-Sent Events protocol for unidirectional real-time updates."""
    def __init__(self, config: Dict[str, Any]):
        super().__init__("SSE", config)
        self.url = config.get("url", "http://localhost:8080/events")
        self.connection = None

    def activate(self) -> None:
        """Activate the SSE connection."""
        with self.lock:
            try:
                # Placeholder for establishing SSE connection
                self.active = True
                self.connection_log.append(f"SSE connection established to {self.url} at {datetime.now().isoformat()}")
            except Exception as e:
                self.connection_log.append(f"Failed to establish SSE connection: {str(e)} at {datetime.now().isoformat()}")
                raise ConnectionFailedError(f"Failed to connect SSE to {self.url}: {str(e)}")
            finally:
                self.last_updated = time.time()

    def deactivate(self) -> None:
        """Deactivate the SSE connection."""
        with self.lock:
            self.active = False
            self.connection_log.append(f"SSE connection closed at {datetime.now().isoformat()}")
            self.last_updated = time.time()

    def send(self, data: Any, destination: str, context: Optional[Dict[str, Any]] = None) -> Any:
        """Send data using SSE protocol (not typically supported as SSE is unidirectional from server to client)."""
        raise ProtocolNotSupportedError("SSE protocol does not support sending data from client")

    def receive(self, source: str, timeout: float = 10.0, context: Optional[Dict[str, Any]] = None) -> Any:
        """Receive data using SSE protocol."""
        if not self.active:
            raise CommunicationError("SSE protocol is not active")
        start_time = time.time()
        try:
            # Simulate receiving data via SSE
            end_time = time.time()
            dummy_data = {"event": "update", "data": f"Update from {source}", "context": context or {}}
            if self.enforce_security(dummy_data, "receive"):
                self.update_performance_metrics(start_time, end_time, success=True)
                self.connection_log.append(f"SSE received data from {source} at {datetime.now().isoformat()}")
                return dummy_data
            else:
                self.update_performance_metrics(start_time, end_time, success=False)
                raise SecurityViolationError("Security check failed for receive operation on SSE")
        except Exception as e:
            end_time = time.time()
            self.update_performance_metrics(start_time, end_time, success=False)
            self.connection_log.append(f"SSE receive failed from {source}: {str(e)} at {datetime.now().isoformat()}")
            raise CommunicationError(f"SSE receive error: {str(e)}")

# Implementation of STDIO Protocol
class STDIOProtocol(CommunicationProtocol):
    """Implementation of STDIO protocol for local process communication."""
    def __init__(self, config: Dict[str, Any]):
        super().__init__("STDIO", config)
        self.input_stream = sys.stdin
        self.output_stream = sys.stdout

    def activate(self) -> None:
        """Activate the STDIO protocol."""
        with self.lock:
            self.active = True
            self.connection_log.append(f"STDIO protocol activated at {datetime.now().isoformat()}")
            self.last_updated = time.time()

    def deactivate(self) -> None:
        """Deactivate the STDIO protocol."""
        with self.lock:
            self.active = False
            self.connection_log.append(f"STDIO protocol deactivated at {datetime.now().isoformat()}")
            self.last_updated = time.time()

    def send(self, data: Any, destination: str, context: Optional[Dict[str, Any]] = None) -> Any:
        """Send data using STDIO protocol."""
        if not self.active:
            raise CommunicationError("STDIO protocol is not active")
        if not self.enforce_security(data, "send"):
            raise SecurityViolationError("Security check failed for send operation on STDIO")
        start_time = time.time()
        try:
            message = json.dumps({"data": data, "destination": destination, "context": context or {}})
            print(message, file=self.output_stream, flush=True)
            end_time = time.time()
            self.update_performance_metrics(start_time, end_time, success=True)
            self.connection_log.append(f"STDIO sent data to {destination} at {datetime.now().isoformat()}")
            return True
        except Exception as e:
            end_time = time.time()
            self.update_performance_metrics(start_time, end_time, success=False)
            self.connection_log.append(f"STDIO send failed to {destination}: {str(e)} at {datetime.now().isoformat()}")
            raise CommunicationError(f"STDIO send error: {str(e)}")

    def receive(self, source: str, timeout: float = 10.0, context: Optional[Dict[str, Any]] = None) -> Any:
        """Receive data using STDIO protocol."""
        if not self.active:
            raise CommunicationError("STDIO protocol is not active")
        start_time = time.time()
        try:
            line = self.input_stream.readline().strip()
            end_time = time.time()
            if line:
                data = json.loads(line)
                if self.enforce_security(data, "receive"):
                    self.update_performance_metrics(start_time, end_time, success=True)
                    self.connection_log.append(f"STDIO received data from {source} at {datetime.now().isoformat()}")
                    return data
                else:
                    self.update_performance_metrics(start_time, end_time, success=False)
                    raise SecurityViolationError("Security check failed for receive operation on STDIO")
            else:
                self.update_performance_metrics(start_time, end_time, success=False)
                raise CommunicationError("No data received on STDIO")
        except Exception as e:
            end_time = time.time()
            self.update_performance_metrics(start_time, end_time, success=False)
            self.connection_log.append(f"STDIO receive failed from {source}: {str(e)} at {datetime.now().isoformat()}")
            raise CommunicationError(f"STDIO receive error: {str(e)}")

# Implementation of WebSockets Protocol
class WebSocketProtocol(CommunicationProtocol):
    """Implementation of WebSockets protocol for full-duplex communication."""
    def __init__(self, config: Dict[str, Any]):
        super().__init__("WebSocket", config)
        self.uri = config.get("uri", "ws://localhost:8765")
        self.websocket = None

    async def activate_async(self) -> None:
        """Asynchronously activate the WebSocket connection."""
        with self.lock:
            try:
                self.websocket = await websockets.connect(self.uri)
                self.active = True
                self.connection_log.append(f"WebSocket connection established to {self.uri} at {datetime.now().isoformat()}")
            except Exception as e:
                self.connection_log.append(f"Failed to establish WebSocket connection: {str(e)} at {datetime.now().isoformat()}")
                raise ConnectionFailedError(f"Failed to connect WebSocket to {self.uri}: {str(e)}")
            finally:
                self.last_updated = time.time()

    def activate(self) -> None:
        """Activate the WebSocket connection (synchronous wrapper)."""
        asyncio.run(self.activate_async())

    async def deactivate_async(self) -> None:
        """Asynchronously deactivate the WebSocket connection."""
        with self.lock:
            if self.websocket:
                await self.websocket.close()
                self.websocket = None
            self.active = False
            self.connection_log.append(f"WebSocket connection closed at {datetime.now().isoformat()}")
            self.last_updated = time.time()

    def deactivate(self) -> None:
        """Deactivate the WebSocket connection (synchronous wrapper)."""
        asyncio.run(self.deactivate_async())

    async def send_async(self, data: Any, destination: str, context: Optional[Dict[str, Any]] = None) -> Any:
        """Asynchronously send data using WebSocket protocol."""
        if not self.active:
            raise CommunicationError("WebSocket protocol is not active")
        if not self.enforce_security(data, "send"):
            raise SecurityViolationError("Security check failed for send operation on WebSocket")
        start_time = time.time()
        try:
            message = json.dumps({"data": data, "destination": destination, "context": context or {}})
            await self.websocket.send(message)
            response = await self.websocket.recv()
            end_time = time.time()
            self.update_performance_metrics(start_time, end_time, success=True)
            self.connection_log.append(f"WebSocket sent data to {destination} at {datetime.now().isoformat()}")
            return json.loads(response) if response else None
        except Exception as e:
            end_time = time.time()
            self.update_performance_metrics(start_time, end_time, success=False)
            self.connection_log.append(f"WebSocket send failed to {destination}: {str(e)} at {datetime.now().isoformat()}")
            raise CommunicationError(f"WebSocket send error: {str(e)}")

    def send(self, data: Any, destination: str, context: Optional[Dict[str, Any]] = None) -> Any:
        """Send data using WebSocket protocol (synchronous wrapper)."""
        return asyncio.run(self.send_async(data, destination, context))

    async def receive_async(self, source: str, timeout: float = 10.0, context: Optional[Dict[str, Any]] = None) -> Any:
        """Asynchronously receive data using WebSocket protocol."""
        if not self.active:
            raise CommunicationError("WebSocket protocol is not active")
        start_time = time.time()
        try:
            response = await asyncio.wait_for(self.websocket.recv(), timeout=timeout)
            end_time = time.time()
            data = json.loads(response) if response else None
            if self.enforce_security(data, "receive"):
                self.update_performance_metrics(start_time, end_time, success=True)
                self.connection_log.append(f"WebSocket received data from {source} at {datetime.now().isoformat()}")
                return data
            else:
                self.update_performance_metrics(start_time, end_time, success=False)
                raise SecurityViolationError("Security check failed for receive operation on WebSocket")
        except Exception as e:
            end_time = time.time()
            self.update_performance_metrics(start_time, end_time, success=False)
            self.connection_log.append(f"WebSocket receive failed from {source}: {str(e)} at {datetime.now().isoformat()}")
            raise CommunicationError(f"WebSocket receive error: {str(e)}")

    def receive(self, source: str, timeout: float = 10.0, context: Optional[Dict[str, Any]] = None) -> Any:
        """Receive data using WebSocket protocol (synchronous wrapper)."""
        return asyncio.run(self.receive_async(source, timeout, context))

# Implementation of gRPC Protocol (placeholder for actual gRPC service definition)
class GRPCProtocol(CommunicationProtocol):
    """Implementation of gRPC protocol for high-performance RPC communication."""
    def __init__(self, config: Dict[str, Any]):
        super().__init__("gRPC", config)
        self.server_address = config.get("server_address", "localhost:50051")
        self.server = None
        self.channel = None

    def activate(self) -> None:
        """Activate the gRPC connection."""
        with self.lock:
            try:
                self.channel = grpc.insecure_channel(self.server_address)
                self.active = True
                self.connection_log.append(f"gRPC connection established to {self.server_address} at {datetime.now().isoformat()}")
            except Exception as e:
                self.connection_log.append(f"Failed to establish gRPC connection: {str(e)} at {datetime.now().isoformat()}")
                raise ConnectionFailedError(f"Failed to connect gRPC to {self.server_address}: {str(e)}")
            finally:
                self.last_updated = time.time()

    def deactivate(self) -> None:
        """Deactivate the gRPC connection."""
        with self.lock:
            if self.channel:
                self.channel.close()
                self.channel = None
            self.active = False
            self.connection_log.append(f"gRPC connection closed at {datetime.now().isoformat()}")
            self.last_updated = time.time()

    def send(self, data: Any, destination: str, context: Optional[Dict[str, Any]] = None) -> Any:
        """Send data using gRPC protocol."""
        if not self.active:
            raise CommunicationError("gRPC protocol is not active")
        if not self.enforce_security(data, "send"):
            raise SecurityViolationError("Security check failed for send operation on gRPC")
        start_time = time.time()
        try:
            # Placeholder for gRPC stub call
            result = {"status": "success", "data": data, "destination": destination}
            end_time = time.time()
            self.update_performance_metrics(start_time, end_time, success=True)
            self.connection_log.append(f"gRPC sent data to {destination} at {datetime.now().isoformat()}")
            return result
        except Exception as e:
            end_time = time.time()
            self.update_performance_metrics(start_time, end_time, success=False)
            self.connection_log.append(f"gRPC send failed to {destination}: {str(e)} at {datetime.now().isoformat()}")
            raise CommunicationError(f"gRPC send error: {str(e)}")

    def receive(self, source: str, timeout: float = 10.0, context: Optional[Dict[str, Any]] = None) -> Any:
        """Receive data using gRPC protocol."""
        if not self.active:
            raise CommunicationError("gRPC protocol is not active")
        start_time = time.time()
        try:
            # Placeholder for gRPC response
            dummy_data = {"data": f"Response from {source}", "context": context or {}}
            end_time = time.time()
            if self.enforce_security(dummy_data, "receive"):
                self.update_performance_metrics(start_time, end_time, success=True)
                self.connection_log.append(f"gRPC received data from {source} at {datetime.now().isoformat()}")
                return dummy_data
            else:
                self.update_performance_metrics(start_time, end_time, success=False)
                raise SecurityViolationError("Security check failed for receive operation on gRPC")
        except Exception as e:
            end_time = time.time()
            self.update_performance_metrics(start_time, end_time, success=False)
            self.connection_log.append(f"gRPC receive failed from {source}: {str(e)} at {datetime.now().isoformat()}")
            raise CommunicationError(f"gRPC receive error: {str(e)}")

# Implementation of Message Queue Protocol (placeholder for systems like RabbitMQ, Kafka)
class MessageQueueProtocol(CommunicationProtocol):
    """Implementation of Message Queue protocol for asynchronous decoupled communication."""
    def __init__(self, config: Dict[str, Any]):
        super().__init__("MessageQueue", config)
        self.broker_url = config.get("broker_url", "localhost:5672")
        self.queue_name = config.get("queue_name", "agentic_queue")
        self.connection = None

    def activate(self) -> None:
        """Activate the Message Queue connection."""
        with self.lock:
            try:
                # Placeholder for establishing connection to message broker
                self.active = True
                self.connection_log.append(f"MessageQueue connection established to {self.broker_url} at {datetime.now().isoformat()}")
            except Exception as e:
                self.connection_log.append(f"Failed to establish MessageQueue connection: {str(e)} at {datetime.now().isoformat()}")
                raise ConnectionFailedError(f"Failed to connect MessageQueue to {self.broker_url}: {str(e)}")
            finally:
                self.last_updated = time.time()

    def deactivate(self) -> None:
        """Deactivate the Message Queue connection."""
        with self.lock:
            self.active = False
            self.connection_log.append(f"MessageQueue connection closed at {datetime.now().isoformat()}")
            self.last_updated = time.time()

    def send(self, data: Any, destination: str, context: Optional[Dict[str, Any]] = None) -> Any:
        """Send data using Message Queue protocol."""
        if not self.active:
            raise CommunicationError("MessageQueue protocol is not active")
        if not self.enforce_security(data, "send"):
            raise SecurityViolationError("Security check failed for send operation on MessageQueue")
        start_time = time.time()
        try:
            # Simulate publishing message to queue
            message = {"data": data, "destination": destination, "context": context or {}}
            end_time = time.time()
            self.update_performance_metrics(start_time, end_time, success=True)
            self.connection_log.append(f"MessageQueue sent data to {destination} on queue {self.queue_name} at {datetime.now().isoformat()}")
            return True
        except Exception as e:
            end_time = time.time()
            self.update_performance_metrics(start_time, end_time, success=False)
            self.connection_log.append(f"MessageQueue send failed to {destination}: {str(e)} at {datetime.now().isoformat()}")
            raise CommunicationError(f"MessageQueue send error: {str(e)}")

    def receive(self, source: str, timeout: float = 10.0, context: Optional[Dict[str, Any]] = None) -> Any:
        """Receive data using Message Queue protocol."""
        if not self.active:
            raise CommunicationError("MessageQueue protocol is not active")
        start_time = time.time()
        try:
            # Simulate consuming message from queue
            dummy_data = {"data": f"Message from {source}", "context": context or {}}
            end_time = time.time()
            if self.enforce_security(dummy_data, "receive"):
                self.update_performance_metrics(start_time, end_time, success=True)
                self.connection_log.append(f"MessageQueue received data from {source} on queue {self.queue_name} at {datetime.now().isoformat()}")
                return dummy_data
            else:
                self.update_performance_metrics(start_time, end_time, success=False)
                raise SecurityViolationError("Security check failed for receive operation on MessageQueue")
        except Exception as e:
            end_time = time.time()
            self.update_performance_metrics(start_time, end_time, success=False)
            self.connection_log.append(f"MessageQueue receive failed from {source}: {str(e)} at {datetime.now().isoformat()}")
            raise CommunicationError(f"MessageQueue receive error: {str(e)}")

# Manager class for handling multiple communication protocols
class CommunicationManager:
    """Manages multiple communication protocols, selecting the appropriate one based on context and requirements."""
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.protocols: Dict[str, CommunicationProtocol] = {}
        self.active = False
        self.lock = threading.Lock()
        self.performance_metrics = {
            "total_communications": 0,
            "successful_communications": 0,
            "failed_communications": 0,
            "average_communication_time": 0.0
        }
        self.operation_log: List[str] = []
        self.last_operation = time.time()
        self.protocol_selection_strategy = config.get("selection_strategy", "priority")
        self.protocol_priorities = config.get("protocol_priorities", {
            "StreamtableHTTP": 1,
            "WebSocket": 2,
            "gRPC": 3,
            "MessageQueue": 4,
            "SSE": 5,
            "STDIO": 6
        })

    def add_protocol(self, protocol: CommunicationProtocol) -> None:
        """Add a communication protocol to the manager."""
        with self.lock:
            self.protocols[protocol.name] = protocol
            self.operation_log.append(f"Added protocol {protocol.name} to manager {self.name} at {datetime.now().isoformat()}")
            self.last_operation = time.time()

    def remove_protocol(self, protocol_name: str) -> None:
        """Remove a communication protocol from the manager."""
        with self.lock:
            if protocol_name in self.protocols:
                protocol = self.protocols[protocol_name]
                if protocol.active:
                    protocol.deactivate()
                del self.protocols[protocol_name]
                self.operation_log.append(f"Removed protocol {protocol_name} from manager {self.name} at {datetime.now().isoformat()}")
            else:
                self.operation_log.append(f"Protocol {protocol_name} not found in manager {self.name} at {datetime.now().isoformat()}")
            self.last_operation = time.time()

    def activate(self) -> None:
        """Activate the communication manager and all protocols."""
        with self.lock:
            self.active = True
            for protocol_name, protocol in self.protocols.items():
                try:
                    if not protocol.active:
                        protocol.activate()
                    self.operation_log.append(f"Activated protocol {protocol_name} in manager {self.name} at {datetime.now().isoformat()}")
                except Exception as e:
                    self.operation_log.append(f"Failed to activate protocol {protocol_name}: {str(e)} at {datetime.now().isoformat()}")
            self.last_operation = time.time()

    def deactivate(self) -> None:
        """Deactivate the communication manager and all protocols."""
        with self.lock:
            self.active = False
            for protocol_name, protocol in self.protocols.items():
                try:
                    if protocol.active:
                        protocol.deactivate()
                    self.operation_log.append(f"Deactivated protocol {protocol_name} in manager {self.name} at {datetime.now().isoformat()}")
                except Exception as e:
                    self.operation_log.append(f"Failed to deactivate protocol {protocol_name}: {str(e)} at {datetime.now().isoformat()}")
            self.last_operation = time.time()

    def select_protocol(self, context: Dict[str, Any]) -> CommunicationProtocol:
        """Select the most appropriate protocol based on context and strategy."""
        if not self.active:
            raise CommunicationError(f"Communication Manager {self.name} is not active")
        with self.lock:
            if not self.protocols:
                raise CommunicationError(f"No protocols available in manager {self.name}")
            if self.protocol_selection_strategy == "priority":
                available_protocols = [p for p in self.protocols.values() if p.active]
                if not available_protocols:
                    raise CommunicationError(f"No active protocols available in manager {self.name}")
                selected_protocol = min(available_protocols, key=lambda p: self.protocol_priorities.get(p.name, 999))
                self.operation_log.append(f"Selected protocol {selected_protocol.name} based on priority at {datetime.now().isoformat()}")
                return selected_protocol
            else:
                # Placeholder for other selection strategies (e.g., latency-based, reliability-based)
                for protocol in self.protocols.values():
                    if protocol.active:
                        self.operation_log.append(f"Selected protocol {protocol.name} based on default at {datetime.now().isoformat()}")
                        return protocol
                raise CommunicationError(f"No suitable protocol selected in manager {self.name}")

    def send_data(self, data: Any, destination: str, context: Optional[Dict[str, Any]] = None,
                  protocol_name: Optional[str] = None) -> Any:
        """Send data to a destination using the selected or specified protocol."""
        if not self.active:
            raise CommunicationError(f"Communication Manager {self.name} is not active")
        with self.lock:
            start_time = time.time()
            try:
                if protocol_name:
                    if protocol_name not in self.protocols:
                        raise ProtocolNotSupportedError(f"Specified protocol {protocol_name} not found in manager {self.name}")
                    selected_protocol = self.protocols[protocol_name]
                    if not selected_protocol.active:
                        raise CommunicationError(f"Specified protocol {protocol_name} is not active in manager {self.name}")
                else:
                    selected_protocol = self.select_protocol(context or {})
                
                result = selected_protocol.send(data, destination, context)
                end_time = time.time()
                self.performance_metrics["total_communications"] += 1
                self.performance_metrics["successful_communications"] += 1
                total_time = self.performance_metrics["average_communication_time"] * (self.performance_metrics["total_communications"] - 1)
                self.performance_metrics["average_communication_time"] = (total_time + (end_time - start_time)) / self.performance_metrics["total_communications"]
                self.operation_log.append(f"Sent data using {selected_protocol.name} to {destination} at {datetime.now().isoformat()}")
                self.last_operation = time.time()
                return result
            except CommunicationError as e:
                end_time = time.time()
                self.performance_metrics["total_communications"] += 1
                self.performance_metrics["failed_communications"] += 1
                total_time = self.performance_metrics["average_communication_time"] * (self.performance_metrics["total_communications"] - 1)
                self.performance_metrics["average_communication_time"] = (total_time + (end_time - start_time)) / self.performance_metrics["total_communications"]
                self.operation_log.append(f"Failed to send data: {str(e)} at {datetime.now().isoformat()}")
                raise
            except Exception as e:
                end_time = time.time()
                self.performance_metrics["total_communications"] += 1
                self.performance_metrics["failed_communications"] += 1
                total_time = self.performance_metrics["average_communication_time"] * (self.performance_metrics["total_communications"] - 1)
                self.performance_metrics["average_communication_time"] = (total_time + (end_time - start_time)) / self.performance_metrics["total_communications"]
                self.operation_log.append(f"Unexpected error sending data: {str(e)} at {datetime.now().isoformat()}")
                raise CommunicationError(f"Unexpected error in manager {self.name} while sending data: {str(e)}")

    def receive_data(self, source: str, timeout: float = 10.0, context: Optional[Dict[str, Any]] = None,
                     protocol_name: Optional[str] = None) -> Any:
        """Receive data from a source using the selected or specified protocol."""
        if not self.active:
            raise CommunicationError(f"Communication Manager {self.name} is not active")
        with self.lock:
            start_time = time.time()
            try:
                if protocol_name:
                    if protocol_name not in self.protocols:
                        raise ProtocolNotSupportedError(f"Specified protocol {protocol_name} not found in manager {self.name}")
                    selected_protocol = self.protocols[protocol_name]
                    if not selected_protocol.active:
                        raise CommunicationError(f"Specified protocol {protocol_name} is not active in manager {self.name}")
                else:
                    selected_protocol = self.select_protocol(context or {})
                
                result = selected_protocol.receive(source, timeout, context)
                end_time = time.time()
                self.performance_metrics["total_communications"] += 1
                self.performance_metrics["successful_communications"] += 1
                total_time = self.performance_metrics["average_communication_time"] * (self.performance_metrics["total_communications"] - 1)
                self.performance_metrics["average_communication_time"] = (total_time + (end_time - start_time)) / self.performance_metrics["total_communications"]
                self.operation_log.append(f"Received data using {selected_protocol.name} from {source} at {datetime.now().isoformat()}")
                self.last_operation = time.time()
                return result
            except CommunicationError as e:
                end_time = time.time()
                self.performance_metrics["total_communications"] += 1
                self.performance_metrics["failed_communications"] += 1
                total_time = self.performance_metrics["average_communication_time"] * (self.performance_metrics["total_communications"] - 1)
                self.performance_metrics["average_communication_time"] = (total_time + (end_time - start_time)) / self.performance_metrics["total_communications"]
                self.operation_log.append(f"Failed to receive data: {str(e)} at {datetime.now().isoformat()}")
                raise
            except Exception as e:
                end_time = time.time()
                self.performance_metrics["total_communications"] += 1
                self.performance_metrics["failed_communications"] += 1
                total_time = self.performance_metrics["average_communication_time"] * (self.performance_metrics["total_communications"] - 1)
                self.performance_metrics["average_communication_time"] = (total_time + (end_time - start_time)) / self.performance_metrics["total_communications"]
                self.operation_log.append(f"Unexpected error receiving data: {str(e)} at {datetime.now().isoformat()}")
                raise CommunicationError(f"Unexpected error in manager {self.name} while receiving data: {str(e)}")

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get aggregated performance metrics for all protocols."""
        with self.lock:
            aggregated_metrics = {
                "manager_metrics": self.performance_metrics,
                "protocol_metrics": {name: proto.performance_metrics for name, proto in self.protocols.items()}
            }
            return aggregated_metrics

# Example usage and initialization
def initialize_communication_manager(config: Dict[str, Any]) -> CommunicationManager:
    """Initialize a Communication Manager with all supported protocols."""
    manager = CommunicationManager("DefaultCommunicationManager", config)
    
    # Add various protocols with their configurations
    streamtable_config = config.get("streamtable_http", {"host": "localhost", "port": 8080})
    sse_config = config.get("sse", {"url": "http://localhost:8080/events"})
    stdio_config = config.get("stdio", {})
    websocket_config = config.get("websocket", {"uri": "ws://localhost:8765"})
    grpc_config = config.get("grpc", {"server_address": "localhost:50051"})
    mq_config = config.get("message_queue", {"broker_url": "localhost:5672", "queue_name": "agentic_queue"})
    
    manager.add_protocol(StreamtableHTTPProtocol(streamtable_config))
    manager.add_protocol(SSEProtocol(sse_config))
    manager.add_protocol(STDIOProtocol(stdio_config))
    manager.add_protocol(WebSocketProtocol(websocket_config))
    manager.add_protocol(GRPCProtocol(grpc_config))
    manager.add_protocol(MessageQueueProtocol(mq_config))
    
    return manager

if __name__ == "__main__":
    # Example configuration
    communication_config = {
        "selection_strategy": "priority",
        "protocol_priorities": {
            "StreamtableHTTP": 1,
            "WebSocket": 2,
            "gRPC": 3,
            "MessageQueue": 4,
            "SSE": 5,
            "STDIO": 6
        },
        "streamtable_http": {"host": "localhost", "port": 8080, "security_enabled": True},
        "sse": {"url": "http://localhost:8080/events", "security_enabled": True},
        "stdio": {"security_enabled": False},
        "websocket": {"uri": "ws://localhost:8765", "security_enabled": True},
        "grpc": {"server_address": "localhost:50051", "security_enabled": True},
        "message_queue": {"broker_url": "localhost:5672", "queue_name": "agentic_queue", "security_enabled": True}
    }
    
    # Initialize manager
    comm_manager = initialize_communication_manager(communication_config)
    
    # Activate manager and protocols
    comm_manager.activate()
    
    try:
        # Example send operation
        result = comm_manager.send_data("Hello, Agentic Framework!", "test_destination", {"task_id": "123"})
        print(f"Send result: {result}")
        
        # Example receive operation
        data = comm_manager.receive_data("test_source", timeout=5.0, context={"task_id": "123"})
        print(f"Received data: {data}")
    except CommunicationError as e:
        print(f"Communication error: {e}")
    finally:
        # Deactivate manager and protocols
        comm_manager.deactivate()
