"""
Enterprise API Client Module.

Provides HTTP client abstraction with retry, circuit breaker,
request/response interceptors, and resilience patterns.

Example:
    # Create API client
    client = create_api_client(
        base_url="https://api.example.com",
        timeout=30.0,
    )
    
    # Make requests
    response = await client.get("/users/123")
    response = await client.post("/users", json={"name": "John"})
    
    # Use decorators
    @api_client("user-service")
    async def fetch_user(client: ApiClient, user_id: str):
        return await client.get(f"/users/{user_id}")
"""

from __future__ import annotations

import asyncio
import functools
import hashlib
import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    Tuple,
    TypeVar,
    Union,
)

T = TypeVar('T')


logger = logging.getLogger(__name__)


class ApiClientError(Exception):
    """Base API client error."""
    pass


class ConnectionError(ApiClientError):
    """Connection failed."""
    pass


class TimeoutError(ApiClientError):
    """Request timed out."""
    pass


class HttpError(ApiClientError):
    """HTTP error response."""
    def __init__(
        self,
        message: str,
        status_code: int,
        response: Optional["Response"] = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class RetryExhaustedError(ApiClientError):
    """All retries exhausted."""
    pass


class HttpMethod(str, Enum):
    """HTTP methods."""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


class RetryStrategy(str, Enum):
    """Retry strategy."""
    NONE = "none"
    FIXED = "fixed"
    EXPONENTIAL = "exponential"
    EXPONENTIAL_JITTER = "exponential_jitter"


@dataclass
class RetryConfig:
    """Retry configuration."""
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_JITTER
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    retry_on: Set[int] = field(default_factory=lambda: {500, 502, 503, 504})
    retry_on_timeout: bool = True
    retry_on_connection_error: bool = True


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""
    enabled: bool = True
    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    half_open_requests: int = 1


@dataclass
class ClientConfig:
    """API client configuration."""
    base_url: str = ""
    timeout: float = 30.0
    connect_timeout: float = 10.0
    headers: Dict[str, str] = field(default_factory=dict)
    retry: RetryConfig = field(default_factory=RetryConfig)
    circuit_breaker: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)
    verify_ssl: bool = True
    follow_redirects: bool = True
    max_redirects: int = 10


@dataclass
class Request:
    """HTTP request."""
    method: HttpMethod
    url: str
    headers: Dict[str, str] = field(default_factory=dict)
    params: Dict[str, Any] = field(default_factory=dict)
    json: Optional[Dict[str, Any]] = None
    data: Optional[Any] = None
    files: Optional[Dict[str, Any]] = None
    timeout: Optional[float] = None
    
    # Metadata
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def full_url(self, base_url: str = "") -> str:
        """Get full URL with base."""
        if self.url.startswith(("http://", "https://")):
            return self.url
        return f"{base_url.rstrip('/')}/{self.url.lstrip('/')}"


@dataclass
class Response:
    """HTTP response."""
    status_code: int
    headers: Dict[str, str] = field(default_factory=dict)
    body: bytes = b""
    json_data: Optional[Dict[str, Any]] = None
    request: Optional[Request] = None
    elapsed: float = 0.0
    
    @property
    def ok(self) -> bool:
        """Check if response is successful."""
        return 200 <= self.status_code < 300
    
    @property
    def text(self) -> str:
        """Get response as text."""
        return self.body.decode("utf-8", errors="replace")
    
    def json(self) -> Any:
        """Parse response as JSON."""
        if self.json_data is not None:
            return self.json_data
        return json.loads(self.body)
    
    def raise_for_status(self) -> None:
        """Raise exception for error status codes."""
        if not self.ok:
            raise HttpError(
                f"HTTP {self.status_code}",
                status_code=self.status_code,
                response=self,
            )


class RequestInterceptor(ABC):
    """Request interceptor."""
    
    @abstractmethod
    async def intercept(self, request: Request) -> Request:
        """Intercept and modify request."""
        pass


class ResponseInterceptor(ABC):
    """Response interceptor."""
    
    @abstractmethod
    async def intercept(
        self,
        response: Response,
        request: Request,
    ) -> Response:
        """Intercept and modify response."""
        pass


class AuthInterceptor(RequestInterceptor):
    """Authentication interceptor."""
    
    def __init__(
        self,
        token_provider: Callable[[], Awaitable[str]],
        header_name: str = "Authorization",
        prefix: str = "Bearer",
    ):
        self._token_provider = token_provider
        self._header_name = header_name
        self._prefix = prefix
    
    async def intercept(self, request: Request) -> Request:
        token = await self._token_provider()
        request.headers[self._header_name] = f"{self._prefix} {token}"
        return request


class LoggingInterceptor(RequestInterceptor, ResponseInterceptor):
    """Logging interceptor."""
    
    def __init__(self, log_body: bool = False):
        self._log_body = log_body
    
    async def intercept(self, request: Request) -> Request:
        logger.info(f"Request: {request.method} {request.url}")
        if self._log_body and request.json:
            logger.debug(f"Request body: {request.json}")
        return request
    
    async def intercept(
        self,
        response: Response,
        request: Request,
    ) -> Response:
        logger.info(
            f"Response: {response.status_code} "
            f"({response.elapsed:.3f}s)"
        )
        return response


class RetryInterceptor(ResponseInterceptor):
    """Retry response interceptor for specific conditions."""
    
    def __init__(
        self,
        should_retry: Callable[[Response], bool],
        max_retries: int = 3,
    ):
        self._should_retry = should_retry
        self._max_retries = max_retries
    
    async def intercept(
        self,
        response: Response,
        request: Request,
    ) -> Response:
        # Just mark for retry, actual retry handled by client
        return response


class CircuitBreaker:
    """Circuit breaker for API calls."""
    
    def __init__(self, config: CircuitBreakerConfig):
        self._config = config
        self._failures = 0
        self._last_failure: Optional[datetime] = None
        self._state = "closed"  # closed, open, half-open
    
    @property
    def state(self) -> str:
        return self._state
    
    def is_available(self) -> bool:
        """Check if circuit allows requests."""
        if self._state == "closed":
            return True
        
        if self._state == "open":
            # Check if recovery timeout has passed
            if self._last_failure:
                elapsed = (datetime.utcnow() - self._last_failure).total_seconds()
                if elapsed >= self._config.recovery_timeout:
                    self._state = "half-open"
                    return True
            return False
        
        # Half-open: allow limited requests
        return True
    
    def record_success(self) -> None:
        """Record successful call."""
        if self._state == "half-open":
            self._state = "closed"
            self._failures = 0
    
    def record_failure(self) -> None:
        """Record failed call."""
        self._failures += 1
        self._last_failure = datetime.utcnow()
        
        if self._failures >= self._config.failure_threshold:
            self._state = "open"
            logger.warning("Circuit breaker opened")
    
    def reset(self) -> None:
        """Reset circuit breaker."""
        self._state = "closed"
        self._failures = 0
        self._last_failure = None


class HttpTransport(ABC):
    """Abstract HTTP transport."""
    
    @abstractmethod
    async def send(self, request: Request) -> Response:
        """Send HTTP request."""
        pass


class MockHttpTransport(HttpTransport):
    """Mock HTTP transport for testing."""
    
    def __init__(self):
        self._responses: Dict[str, Response] = {}
        self._default_response = Response(status_code=200)
    
    def mock(
        self,
        method: HttpMethod,
        url: str,
        response: Response,
    ) -> None:
        """Mock a response."""
        key = f"{method}:{url}"
        self._responses[key] = response
    
    async def send(self, request: Request) -> Response:
        key = f"{request.method}:{request.url}"
        response = self._responses.get(key, self._default_response)
        response.request = request
        return response


class ApiClient:
    """
    HTTP API client with resilience patterns.
    """
    
    def __init__(
        self,
        config: Optional[ClientConfig] = None,
        transport: Optional[HttpTransport] = None,
    ):
        self._config = config or ClientConfig()
        self._transport = transport or MockHttpTransport()
        
        self._request_interceptors: List[RequestInterceptor] = []
        self._response_interceptors: List[ResponseInterceptor] = []
        
        self._circuit_breaker = CircuitBreaker(self._config.circuit_breaker)
    
    @property
    def base_url(self) -> str:
        return self._config.base_url
    
    def add_request_interceptor(self, interceptor: RequestInterceptor) -> None:
        """Add request interceptor."""
        self._request_interceptors.append(interceptor)
    
    def add_response_interceptor(self, interceptor: ResponseInterceptor) -> None:
        """Add response interceptor."""
        self._response_interceptors.append(interceptor)
    
    async def request(
        self,
        method: HttpMethod,
        url: str,
        **kwargs,
    ) -> Response:
        """Make HTTP request."""
        request = Request(
            method=method,
            url=url,
            headers={**self._config.headers, **kwargs.pop("headers", {})},
            params=kwargs.pop("params", {}),
            json=kwargs.pop("json", None),
            data=kwargs.pop("data", None),
            timeout=kwargs.pop("timeout", self._config.timeout),
        )
        
        # Apply request interceptors
        for interceptor in self._request_interceptors:
            request = await interceptor.intercept(request)
        
        # Check circuit breaker
        if self._config.circuit_breaker.enabled:
            if not self._circuit_breaker.is_available():
                raise ApiClientError("Circuit breaker is open")
        
        # Retry loop
        retry_config = self._config.retry
        attempt = 0
        last_exception: Optional[Exception] = None
        
        while attempt <= retry_config.max_retries:
            try:
                start_time = time.time()
                response = await self._send_request(request)
                response.elapsed = time.time() - start_time
                
                # Apply response interceptors
                for interceptor in self._response_interceptors:
                    response = await interceptor.intercept(response, request)
                
                # Check if should retry
                if (
                    not response.ok and
                    response.status_code in retry_config.retry_on and
                    attempt < retry_config.max_retries
                ):
                    attempt += 1
                    await self._wait_for_retry(attempt, retry_config)
                    continue
                
                # Record success
                if self._config.circuit_breaker.enabled:
                    self._circuit_breaker.record_success()
                
                return response
                
            except (ConnectionError, TimeoutError) as e:
                last_exception = e
                
                # Record failure
                if self._config.circuit_breaker.enabled:
                    self._circuit_breaker.record_failure()
                
                if attempt < retry_config.max_retries:
                    if (
                        (isinstance(e, TimeoutError) and retry_config.retry_on_timeout) or
                        (isinstance(e, ConnectionError) and retry_config.retry_on_connection_error)
                    ):
                        attempt += 1
                        await self._wait_for_retry(attempt, retry_config)
                        continue
                
                raise
        
        if last_exception:
            raise RetryExhaustedError(f"Retries exhausted: {last_exception}")
        
        raise RetryExhaustedError("All retries exhausted")
    
    async def _send_request(self, request: Request) -> Response:
        """Send request via transport."""
        return await self._transport.send(request)
    
    async def _wait_for_retry(
        self,
        attempt: int,
        config: RetryConfig,
    ) -> None:
        """Wait before retry."""
        if config.strategy == RetryStrategy.NONE:
            return
        
        if config.strategy == RetryStrategy.FIXED:
            delay = config.base_delay
        elif config.strategy == RetryStrategy.EXPONENTIAL:
            delay = min(
                config.base_delay * (2 ** (attempt - 1)),
                config.max_delay
            )
        else:  # EXPONENTIAL_JITTER
            import random
            base = min(
                config.base_delay * (2 ** (attempt - 1)),
                config.max_delay
            )
            delay = base * (0.5 + random.random())
        
        logger.debug(f"Retry attempt {attempt}, waiting {delay:.2f}s")
        await asyncio.sleep(delay)
    
    # Convenience methods
    async def get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Response:
        """Make GET request."""
        return await self.request(
            HttpMethod.GET,
            url,
            params=params or {},
            **kwargs,
        )
    
    async def post(
        self,
        url: str,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        **kwargs,
    ) -> Response:
        """Make POST request."""
        return await self.request(
            HttpMethod.POST,
            url,
            json=json,
            data=data,
            **kwargs,
        )
    
    async def put(
        self,
        url: str,
        json: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Response:
        """Make PUT request."""
        return await self.request(
            HttpMethod.PUT,
            url,
            json=json,
            **kwargs,
        )
    
    async def patch(
        self,
        url: str,
        json: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Response:
        """Make PATCH request."""
        return await self.request(
            HttpMethod.PATCH,
            url,
            json=json,
            **kwargs,
        )
    
    async def delete(
        self,
        url: str,
        **kwargs,
    ) -> Response:
        """Make DELETE request."""
        return await self.request(HttpMethod.DELETE, url, **kwargs)


class ServiceApiClient(ApiClient):
    """
    API client for service-to-service communication.
    """
    
    def __init__(
        self,
        service_name: str,
        config: Optional[ClientConfig] = None,
        service_registry: Optional[Any] = None,
    ):
        super().__init__(config)
        self._service_name = service_name
        self._service_registry = service_registry
    
    async def discover_base_url(self) -> str:
        """Discover service base URL."""
        if self._service_registry:
            instance = await self._service_registry.discover(self._service_name)
            return instance.base_url
        return self._config.base_url


# Global clients
_clients: Dict[str, ApiClient] = {}


# Decorators
def api_client(
    service_name: str,
    base_url: Optional[str] = None,
) -> Callable:
    """
    Decorator to inject API client.
    
    Example:
        @api_client("user-service", base_url="https://api.example.com")
        async def get_user(client: ApiClient, user_id: str):
            return await client.get(f"/users/{user_id}")
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            client = get_client(service_name, base_url)
            return await func(client, *args, **kwargs)
        
        return wrapper
    
    return decorator


def with_retry(
    max_retries: int = 3,
    retry_on: Optional[Set[int]] = None,
) -> Callable:
    """
    Decorator to add retry logic.
    
    Example:
        @with_retry(max_retries=5)
        async def call_api():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except HttpError as e:
                    if retry_on and e.status_code not in retry_on:
                        raise
                    last_error = e
                    
                    if attempt < max_retries:
                        await asyncio.sleep(2 ** attempt)
                except Exception as e:
                    last_error = e
                    
                    if attempt < max_retries:
                        await asyncio.sleep(2 ** attempt)
            
            raise RetryExhaustedError(f"Retries exhausted: {last_error}")
        
        return wrapper
    
    return decorator


# Factory functions
def create_api_client(
    base_url: str = "",
    timeout: float = 30.0,
    headers: Optional[Dict[str, str]] = None,
    max_retries: int = 3,
) -> ApiClient:
    """Create API client."""
    config = ClientConfig(
        base_url=base_url,
        timeout=timeout,
        headers=headers or {},
        retry=RetryConfig(max_retries=max_retries),
    )
    return ApiClient(config)


def create_service_client(
    service_name: str,
    base_url: str = "",
    service_registry: Optional[Any] = None,
) -> ServiceApiClient:
    """Create service API client."""
    config = ClientConfig(base_url=base_url)
    return ServiceApiClient(service_name, config, service_registry)


def create_client_config(
    base_url: str = "",
    timeout: float = 30.0,
    max_retries: int = 3,
) -> ClientConfig:
    """Create client configuration."""
    return ClientConfig(
        base_url=base_url,
        timeout=timeout,
        retry=RetryConfig(max_retries=max_retries),
    )


def create_auth_interceptor(
    token_provider: Callable[[], Awaitable[str]],
    header_name: str = "Authorization",
    prefix: str = "Bearer",
) -> AuthInterceptor:
    """Create auth interceptor."""
    return AuthInterceptor(token_provider, header_name, prefix)


def create_logging_interceptor(log_body: bool = False) -> LoggingInterceptor:
    """Create logging interceptor."""
    return LoggingInterceptor(log_body)


def create_mock_transport() -> MockHttpTransport:
    """Create mock transport for testing."""
    return MockHttpTransport()


def get_client(
    name: str,
    base_url: Optional[str] = None,
) -> ApiClient:
    """Get or create named client."""
    if name not in _clients:
        _clients[name] = create_api_client(base_url or "")
    return _clients[name]


__all__ = [
    # Exceptions
    "ApiClientError",
    "ConnectionError",
    "TimeoutError",
    "HttpError",
    "RetryExhaustedError",
    # Enums
    "HttpMethod",
    "RetryStrategy",
    # Data classes
    "RetryConfig",
    "CircuitBreakerConfig",
    "ClientConfig",
    "Request",
    "Response",
    # Interceptors
    "RequestInterceptor",
    "ResponseInterceptor",
    "AuthInterceptor",
    "LoggingInterceptor",
    "RetryInterceptor",
    # Circuit breaker
    "CircuitBreaker",
    # Transport
    "HttpTransport",
    "MockHttpTransport",
    # Clients
    "ApiClient",
    "ServiceApiClient",
    # Decorators
    "api_client",
    "with_retry",
    # Factory functions
    "create_api_client",
    "create_service_client",
    "create_client_config",
    "create_auth_interceptor",
    "create_logging_interceptor",
    "create_mock_transport",
    "get_client",
]
