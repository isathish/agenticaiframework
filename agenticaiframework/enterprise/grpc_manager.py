"""
Enterprise gRPC Manager Module.

Provides gRPC service definition, client/server management,
streaming support, and interceptors.

Example:
    # Create gRPC server
    server = create_grpc_server(port=50051)
    
    # Register service
    @server.service("UserService")
    class UserServiceImpl:
        @server.method("GetUser")
        async def get_user(self, request: GetUserRequest) -> User:
            return await fetch_user(request.user_id)
    
    # Start server
    await server.start()
    
    # Create client
    client = create_grpc_client("localhost:50051")
    user = await client.call("UserService", "GetUser", {"user_id": "123"})
"""

from __future__ import annotations

import asyncio
import functools
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import (
    Any,
    AsyncIterator,
    Awaitable,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
)

T = TypeVar('T')
RequestT = TypeVar('RequestT')
ResponseT = TypeVar('ResponseT')


logger = logging.getLogger(__name__)


class GrpcError(Exception):
    """Base gRPC error."""
    def __init__(
        self,
        code: "StatusCode",
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


class StatusCode(str, Enum):
    """gRPC status codes."""
    OK = "OK"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"
    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    DEADLINE_EXCEEDED = "DEADLINE_EXCEEDED"
    NOT_FOUND = "NOT_FOUND"
    ALREADY_EXISTS = "ALREADY_EXISTS"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    RESOURCE_EXHAUSTED = "RESOURCE_EXHAUSTED"
    FAILED_PRECONDITION = "FAILED_PRECONDITION"
    ABORTED = "ABORTED"
    OUT_OF_RANGE = "OUT_OF_RANGE"
    UNIMPLEMENTED = "UNIMPLEMENTED"
    INTERNAL = "INTERNAL"
    UNAVAILABLE = "UNAVAILABLE"
    DATA_LOSS = "DATA_LOSS"
    UNAUTHENTICATED = "UNAUTHENTICATED"


class StreamType(str, Enum):
    """RPC stream types."""
    UNARY = "UNARY"
    SERVER_STREAMING = "SERVER_STREAMING"
    CLIENT_STREAMING = "CLIENT_STREAMING"
    BIDIRECTIONAL = "BIDIRECTIONAL"


@dataclass
class Metadata:
    """gRPC metadata (headers/trailers)."""
    entries: Dict[str, str] = field(default_factory=dict)
    
    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        return self.entries.get(key.lower(), default)
    
    def set(self, key: str, value: str) -> None:
        self.entries[key.lower()] = value
    
    def add(self, key: str, value: str) -> None:
        self.entries[key.lower()] = value
    
    def __iter__(self):
        return iter(self.entries.items())


@dataclass
class MethodDescriptor:
    """gRPC method descriptor."""
    service_name: str
    method_name: str
    request_type: Type
    response_type: Type
    stream_type: StreamType = StreamType.UNARY
    handler: Optional[Callable] = None


@dataclass
class ServiceDescriptor:
    """gRPC service descriptor."""
    name: str
    methods: Dict[str, MethodDescriptor] = field(default_factory=dict)
    implementation: Optional[Any] = None


@dataclass
class CallContext:
    """gRPC call context."""
    metadata: Metadata = field(default_factory=Metadata)
    deadline: Optional[datetime] = None
    cancelled: bool = False
    peer: str = ""
    
    def is_active(self) -> bool:
        """Check if call is still active."""
        if self.cancelled:
            return False
        if self.deadline and datetime.utcnow() > self.deadline:
            return False
        return True


@dataclass
class ClientConfig:
    """gRPC client configuration."""
    target: str
    timeout: float = 30.0
    max_retries: int = 3
    retry_delay: float = 0.1
    compression: bool = False
    load_balance: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class ServerConfig:
    """gRPC server configuration."""
    port: int = 50051
    host: str = "0.0.0.0"
    max_workers: int = 10
    max_concurrent_rpcs: int = 100
    max_message_size: int = 4 * 1024 * 1024  # 4MB
    reflection: bool = True


# Interceptors
class ServerInterceptor(ABC):
    """Server-side interceptor."""
    
    @abstractmethod
    async def intercept(
        self,
        method: MethodDescriptor,
        request: Any,
        context: CallContext,
        handler: Callable,
    ) -> Any:
        """Intercept server call."""
        pass


class ClientInterceptor(ABC):
    """Client-side interceptor."""
    
    @abstractmethod
    async def intercept(
        self,
        method: str,
        request: Any,
        metadata: Metadata,
        invoker: Callable,
    ) -> Any:
        """Intercept client call."""
        pass


class LoggingInterceptor(ServerInterceptor):
    """Server logging interceptor."""
    
    async def intercept(
        self,
        method: MethodDescriptor,
        request: Any,
        context: CallContext,
        handler: Callable,
    ) -> Any:
        start_time = datetime.utcnow()
        
        try:
            result = await handler(request, context)
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            
            logger.info(
                f"gRPC {method.service_name}/{method.method_name} "
                f"completed in {elapsed:.3f}s"
            )
            
            return result
        except Exception as e:
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            logger.error(
                f"gRPC {method.service_name}/{method.method_name} "
                f"failed after {elapsed:.3f}s: {e}"
            )
            raise


class AuthInterceptor(ServerInterceptor):
    """Authentication interceptor."""
    
    def __init__(
        self,
        validator: Callable[[str], Awaitable[bool]],
        metadata_key: str = "authorization",
    ):
        self._validator = validator
        self._metadata_key = metadata_key
    
    async def intercept(
        self,
        method: MethodDescriptor,
        request: Any,
        context: CallContext,
        handler: Callable,
    ) -> Any:
        token = context.metadata.get(self._metadata_key)
        
        if not token:
            raise GrpcError(
                StatusCode.UNAUTHENTICATED,
                "Missing authentication token"
            )
        
        if not await self._validator(token):
            raise GrpcError(
                StatusCode.UNAUTHENTICATED,
                "Invalid authentication token"
            )
        
        return await handler(request, context)


class RetryInterceptor(ClientInterceptor):
    """Client retry interceptor."""
    
    def __init__(
        self,
        max_retries: int = 3,
        retry_codes: Optional[List[StatusCode]] = None,
    ):
        self._max_retries = max_retries
        self._retry_codes = retry_codes or [
            StatusCode.UNAVAILABLE,
            StatusCode.DEADLINE_EXCEEDED,
        ]
    
    async def intercept(
        self,
        method: str,
        request: Any,
        metadata: Metadata,
        invoker: Callable,
    ) -> Any:
        last_error = None
        
        for attempt in range(self._max_retries + 1):
            try:
                return await invoker(method, request, metadata)
            except GrpcError as e:
                if e.code not in self._retry_codes:
                    raise
                
                last_error = e
                if attempt < self._max_retries:
                    await asyncio.sleep(0.1 * (2 ** attempt))
        
        raise last_error or GrpcError(StatusCode.UNKNOWN, "Unknown error")


class GrpcServer:
    """
    gRPC server manager.
    """
    
    def __init__(self, config: ServerConfig):
        self._config = config
        self._services: Dict[str, ServiceDescriptor] = {}
        self._interceptors: List[ServerInterceptor] = []
        self._running = False
    
    @property
    def is_running(self) -> bool:
        return self._running
    
    def service(
        self,
        name: str,
    ) -> Callable:
        """Decorator to register service."""
        def decorator(cls: Type) -> Type:
            descriptor = ServiceDescriptor(name=name)
            self._services[name] = descriptor
            
            # Register as implementation
            descriptor.implementation = cls()
            
            return cls
        
        return decorator
    
    def method(
        self,
        method_name: str,
        stream_type: StreamType = StreamType.UNARY,
        request_type: Optional[Type] = None,
        response_type: Optional[Type] = None,
    ) -> Callable:
        """Decorator to register method."""
        def decorator(func: Callable) -> Callable:
            # Get service from enclosing class
            service_name = None
            for name, desc in self._services.items():
                if desc.implementation and hasattr(desc.implementation, func.__name__):
                    service_name = name
                    break
            
            if service_name:
                method_desc = MethodDescriptor(
                    service_name=service_name,
                    method_name=method_name,
                    request_type=request_type or dict,
                    response_type=response_type or dict,
                    stream_type=stream_type,
                    handler=func,
                )
                self._services[service_name].methods[method_name] = method_desc
            
            return func
        
        return decorator
    
    def add_interceptor(self, interceptor: ServerInterceptor) -> None:
        """Add server interceptor."""
        self._interceptors.append(interceptor)
    
    def register_service(
        self,
        service: ServiceDescriptor,
    ) -> None:
        """Register service descriptor."""
        self._services[service.name] = service
    
    async def start(self) -> None:
        """Start gRPC server."""
        if self._running:
            return
        
        self._running = True
        logger.info(
            f"gRPC server started on {self._config.host}:{self._config.port}"
        )
        
        # In real implementation, would start actual gRPC server
        # This is a simplified version
    
    async def stop(self, grace_period: float = 5.0) -> None:
        """Stop gRPC server."""
        if not self._running:
            return
        
        self._running = False
        logger.info("gRPC server stopped")
    
    async def handle_call(
        self,
        service_name: str,
        method_name: str,
        request: Any,
        context: CallContext,
    ) -> Any:
        """Handle incoming RPC call."""
        service = self._services.get(service_name)
        if not service:
            raise GrpcError(
                StatusCode.NOT_FOUND,
                f"Service not found: {service_name}"
            )
        
        method = service.methods.get(method_name)
        if not method:
            raise GrpcError(
                StatusCode.UNIMPLEMENTED,
                f"Method not found: {method_name}"
            )
        
        # Build handler chain with interceptors
        async def final_handler(req: Any, ctx: CallContext) -> Any:
            if method.handler:
                return await method.handler(service.implementation, req)
            raise GrpcError(StatusCode.UNIMPLEMENTED, "No handler")
        
        handler = final_handler
        for interceptor in reversed(self._interceptors):
            handler = self._wrap_interceptor(interceptor, method, handler)
        
        return await handler(request, context)
    
    def _wrap_interceptor(
        self,
        interceptor: ServerInterceptor,
        method: MethodDescriptor,
        next_handler: Callable,
    ) -> Callable:
        """Wrap handler with interceptor."""
        async def wrapped(request: Any, context: CallContext) -> Any:
            return await interceptor.intercept(
                method, request, context, next_handler
            )
        return wrapped


class GrpcClient:
    """
    gRPC client manager.
    """
    
    def __init__(self, config: ClientConfig):
        self._config = config
        self._interceptors: List[ClientInterceptor] = []
        self._connected = False
    
    @property
    def is_connected(self) -> bool:
        return self._connected
    
    def add_interceptor(self, interceptor: ClientInterceptor) -> None:
        """Add client interceptor."""
        self._interceptors.append(interceptor)
    
    async def connect(self) -> None:
        """Connect to server."""
        if self._connected:
            return
        
        self._connected = True
        logger.debug(f"Connected to gRPC server at {self._config.target}")
    
    async def disconnect(self) -> None:
        """Disconnect from server."""
        if not self._connected:
            return
        
        self._connected = False
        logger.debug("Disconnected from gRPC server")
    
    async def call(
        self,
        service: str,
        method: str,
        request: Any,
        metadata: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        """Make unary RPC call."""
        if not self._connected:
            await self.connect()
        
        meta = Metadata(entries={
            **self._config.metadata,
            **(metadata or {}),
        })
        
        full_method = f"/{service}/{method}"
        
        # Build invoker chain with interceptors
        async def final_invoker(m: str, req: Any, meta: Metadata) -> Any:
            # In real implementation, would make actual gRPC call
            return {}
        
        invoker = final_invoker
        for interceptor in reversed(self._interceptors):
            invoker = self._wrap_interceptor(interceptor, invoker)
        
        return await invoker(full_method, request, meta)
    
    async def call_stream(
        self,
        service: str,
        method: str,
        request: Any,
    ) -> AsyncIterator[Any]:
        """Make server streaming RPC call."""
        if not self._connected:
            await self.connect()
        
        # Simplified - yields empty responses
        yield {}
    
    async def send_stream(
        self,
        service: str,
        method: str,
        requests: AsyncIterator[Any],
    ) -> Any:
        """Make client streaming RPC call."""
        if not self._connected:
            await self.connect()
        
        # Collect all requests and return response
        async for _ in requests:
            pass
        
        return {}
    
    async def bidirectional_stream(
        self,
        service: str,
        method: str,
        requests: AsyncIterator[Any],
    ) -> AsyncIterator[Any]:
        """Make bidirectional streaming RPC call."""
        if not self._connected:
            await self.connect()
        
        async for _ in requests:
            yield {}
    
    def _wrap_interceptor(
        self,
        interceptor: ClientInterceptor,
        next_invoker: Callable,
    ) -> Callable:
        """Wrap invoker with interceptor."""
        async def wrapped(method: str, request: Any, metadata: Metadata) -> Any:
            return await interceptor.intercept(
                method, request, metadata, next_invoker
            )
        return wrapped


class ServiceStub(Generic[RequestT, ResponseT]):
    """
    Type-safe service stub.
    """
    
    def __init__(
        self,
        client: GrpcClient,
        service_name: str,
    ):
        self._client = client
        self._service_name = service_name
    
    async def call(
        self,
        method: str,
        request: RequestT,
        **kwargs,
    ) -> ResponseT:
        """Call service method."""
        return await self._client.call(
            self._service_name,
            method,
            request,
            **kwargs,
        )


# Decorators
def grpc_service(name: str) -> Callable:
    """Decorator to mark class as gRPC service."""
    def decorator(cls: Type) -> Type:
        cls._grpc_service_name = name
        return cls
    return decorator


def grpc_method(
    name: Optional[str] = None,
    stream_type: StreamType = StreamType.UNARY,
) -> Callable:
    """Decorator to mark method as gRPC method."""
    def decorator(func: Callable) -> Callable:
        func._grpc_method_name = name or func.__name__
        func._grpc_stream_type = stream_type
        return func
    return decorator


def unary(name: Optional[str] = None) -> Callable:
    """Decorator for unary method."""
    return grpc_method(name, StreamType.UNARY)


def server_streaming(name: Optional[str] = None) -> Callable:
    """Decorator for server streaming method."""
    return grpc_method(name, StreamType.SERVER_STREAMING)


def client_streaming(name: Optional[str] = None) -> Callable:
    """Decorator for client streaming method."""
    return grpc_method(name, StreamType.CLIENT_STREAMING)


def bidirectional(name: Optional[str] = None) -> Callable:
    """Decorator for bidirectional streaming method."""
    return grpc_method(name, StreamType.BIDIRECTIONAL)


# Factory functions
def create_grpc_server(
    port: int = 50051,
    host: str = "0.0.0.0",
    max_workers: int = 10,
    **kwargs,
) -> GrpcServer:
    """Create gRPC server."""
    config = ServerConfig(
        port=port,
        host=host,
        max_workers=max_workers,
        **kwargs,
    )
    return GrpcServer(config)


def create_grpc_client(
    target: str,
    timeout: float = 30.0,
    **kwargs,
) -> GrpcClient:
    """Create gRPC client."""
    config = ClientConfig(
        target=target,
        timeout=timeout,
        **kwargs,
    )
    return GrpcClient(config)


def create_service_stub(
    client: GrpcClient,
    service_name: str,
) -> ServiceStub:
    """Create type-safe service stub."""
    return ServiceStub(client, service_name)


def create_auth_interceptor(
    validator: Callable[[str], Awaitable[bool]],
    metadata_key: str = "authorization",
) -> AuthInterceptor:
    """Create auth interceptor."""
    return AuthInterceptor(validator, metadata_key)


def create_logging_interceptor() -> LoggingInterceptor:
    """Create logging interceptor."""
    return LoggingInterceptor()


def create_retry_interceptor(
    max_retries: int = 3,
    retry_codes: Optional[List[StatusCode]] = None,
) -> RetryInterceptor:
    """Create retry interceptor."""
    return RetryInterceptor(max_retries, retry_codes)


__all__ = [
    # Exceptions
    "GrpcError",
    # Enums
    "StatusCode",
    "StreamType",
    # Data classes
    "Metadata",
    "MethodDescriptor",
    "ServiceDescriptor",
    "CallContext",
    "ClientConfig",
    "ServerConfig",
    # Interceptors
    "ServerInterceptor",
    "ClientInterceptor",
    "LoggingInterceptor",
    "AuthInterceptor",
    "RetryInterceptor",
    # Server/Client
    "GrpcServer",
    "GrpcClient",
    "ServiceStub",
    # Decorators
    "grpc_service",
    "grpc_method",
    "unary",
    "server_streaming",
    "client_streaming",
    "bidirectional",
    # Factory functions
    "create_grpc_server",
    "create_grpc_client",
    "create_service_stub",
    "create_auth_interceptor",
    "create_logging_interceptor",
    "create_retry_interceptor",
]
