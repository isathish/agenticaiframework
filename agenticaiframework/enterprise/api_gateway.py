"""
Enterprise API Gateway Module.

Provides API gateway patterns, routing, authentication,
rate limiting, request/response transformation, and aggregation.

Example:
    # Create gateway
    gateway = create_api_gateway()
    
    # Define routes
    gateway.route("/users", UserService)
    gateway.route("/orders", OrderService)
    
    # Add middleware
    gateway.use(AuthMiddleware())
    gateway.use(RateLimitMiddleware())
    
    # Handle request
    response = await gateway.handle(request)
"""

from __future__ import annotations

import asyncio
import functools
import hashlib
import json
import logging
import re
import time
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
    Pattern,
    Set,
    Tuple,
    TypeVar,
    Union,
)

T = TypeVar('T')


logger = logging.getLogger(__name__)


class HttpMethod(str, Enum):
    """HTTP method."""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


class GatewayError(Exception):
    """Base gateway error."""
    pass


class RouteNotFoundError(GatewayError):
    """Route not found."""
    pass


class AuthenticationError(GatewayError):
    """Authentication failed."""
    pass


class RateLimitError(GatewayError):
    """Rate limit exceeded."""
    pass


@dataclass
class Request:
    """Gateway request."""
    method: HttpMethod
    path: str
    headers: Dict[str, str] = field(default_factory=dict)
    query_params: Dict[str, str] = field(default_factory=dict)
    body: Optional[Any] = None
    path_params: Dict[str, str] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    request_id: str = ""
    
    def __post_init__(self):
        if not self.request_id:
            self.request_id = hashlib.md5(
                f"{self.path}{self.timestamp.timestamp()}".encode()
            ).hexdigest()[:16]


@dataclass
class Response:
    """Gateway response."""
    status_code: int
    body: Optional[Any] = None
    headers: Dict[str, str] = field(default_factory=dict)
    content_type: str = "application/json"
    
    @classmethod
    def ok(cls, body: Any = None) -> "Response":
        return cls(status_code=200, body=body)
    
    @classmethod
    def created(cls, body: Any = None) -> "Response":
        return cls(status_code=201, body=body)
    
    @classmethod
    def no_content(cls) -> "Response":
        return cls(status_code=204)
    
    @classmethod
    def bad_request(cls, message: str = "Bad Request") -> "Response":
        return cls(status_code=400, body={"error": message})
    
    @classmethod
    def unauthorized(cls, message: str = "Unauthorized") -> "Response":
        return cls(status_code=401, body={"error": message})
    
    @classmethod
    def forbidden(cls, message: str = "Forbidden") -> "Response":
        return cls(status_code=403, body={"error": message})
    
    @classmethod
    def not_found(cls, message: str = "Not Found") -> "Response":
        return cls(status_code=404, body={"error": message})
    
    @classmethod
    def rate_limited(cls, retry_after: int = 60) -> "Response":
        return cls(
            status_code=429,
            body={"error": "Rate limit exceeded"},
            headers={"Retry-After": str(retry_after)},
        )
    
    @classmethod
    def error(cls, message: str = "Internal Server Error") -> "Response":
        return cls(status_code=500, body={"error": message})


@dataclass
class RouteConfig:
    """Route configuration."""
    path: str
    methods: List[HttpMethod] = field(default_factory=lambda: [HttpMethod.GET])
    handler: Optional[Callable] = None
    service: Optional[str] = None
    timeout: float = 30.0
    retries: int = 0
    cache_ttl: Optional[int] = None
    rate_limit: Optional[int] = None
    auth_required: bool = False


# Type for middleware next function
NextFn = Callable[[Request], Awaitable[Response]]


class Middleware(ABC):
    """Abstract middleware."""
    
    @abstractmethod
    async def __call__(self, request: Request, next_fn: NextFn) -> Response:
        """Process request."""
        pass


class AuthMiddleware(Middleware):
    """Authentication middleware."""
    
    def __init__(
        self,
        validator: Optional[Callable[[str], Awaitable[Optional[Dict]]]] = None,
        header_name: str = "Authorization",
        scheme: str = "Bearer",
    ):
        self._validator = validator
        self._header_name = header_name
        self._scheme = scheme
    
    async def __call__(self, request: Request, next_fn: NextFn) -> Response:
        auth_header = request.headers.get(self._header_name, "")
        
        if not auth_header:
            return Response.unauthorized("Missing authorization header")
        
        if not auth_header.startswith(f"{self._scheme} "):
            return Response.unauthorized("Invalid authorization scheme")
        
        token = auth_header[len(self._scheme) + 1:]
        
        if self._validator:
            user_info = await self._validator(token)
            if not user_info:
                return Response.unauthorized("Invalid token")
            request.context["user"] = user_info
        
        return await next_fn(request)


class RateLimitMiddleware(Middleware):
    """Rate limiting middleware."""
    
    def __init__(
        self,
        requests_per_minute: int = 60,
        key_fn: Optional[Callable[[Request], str]] = None,
    ):
        self._rpm = requests_per_minute
        self._key_fn = key_fn or (lambda r: r.headers.get("X-Client-ID", "default"))
        self._windows: Dict[str, List[float]] = {}
    
    async def __call__(self, request: Request, next_fn: NextFn) -> Response:
        key = self._key_fn(request)
        now = time.time()
        window_start = now - 60
        
        # Clean old entries
        if key in self._windows:
            self._windows[key] = [t for t in self._windows[key] if t > window_start]
        else:
            self._windows[key] = []
        
        # Check limit
        if len(self._windows[key]) >= self._rpm:
            return Response.rate_limited()
        
        # Record request
        self._windows[key].append(now)
        
        return await next_fn(request)


class LoggingMiddleware(Middleware):
    """Logging middleware."""
    
    def __init__(self, logger_name: Optional[str] = None):
        self._logger = logging.getLogger(logger_name or __name__)
    
    async def __call__(self, request: Request, next_fn: NextFn) -> Response:
        start = time.perf_counter()
        
        self._logger.info(
            f"[{request.request_id}] --> {request.method.value} {request.path}"
        )
        
        try:
            response = await next_fn(request)
            
            duration = (time.perf_counter() - start) * 1000
            self._logger.info(
                f"[{request.request_id}] <-- {response.status_code} ({duration:.2f}ms)"
            )
            
            return response
            
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            self._logger.error(
                f"[{request.request_id}] <-- ERROR: {e} ({duration:.2f}ms)"
            )
            raise


class CorsMiddleware(Middleware):
    """CORS middleware."""
    
    def __init__(
        self,
        allow_origins: List[str] = None,
        allow_methods: List[str] = None,
        allow_headers: List[str] = None,
        max_age: int = 86400,
    ):
        self._allow_origins = allow_origins or ["*"]
        self._allow_methods = allow_methods or ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
        self._allow_headers = allow_headers or ["Content-Type", "Authorization"]
        self._max_age = max_age
    
    async def __call__(self, request: Request, next_fn: NextFn) -> Response:
        origin = request.headers.get("Origin", "")
        
        # Handle preflight
        if request.method == HttpMethod.OPTIONS:
            return Response(
                status_code=204,
                headers=self._cors_headers(origin),
            )
        
        response = await next_fn(request)
        
        # Add CORS headers
        response.headers.update(self._cors_headers(origin))
        
        return response
    
    def _cors_headers(self, origin: str) -> Dict[str, str]:
        allowed_origin = origin if origin in self._allow_origins or "*" in self._allow_origins else ""
        
        return {
            "Access-Control-Allow-Origin": allowed_origin,
            "Access-Control-Allow-Methods": ", ".join(self._allow_methods),
            "Access-Control-Allow-Headers": ", ".join(self._allow_headers),
            "Access-Control-Max-Age": str(self._max_age),
        }


class TransformMiddleware(Middleware):
    """Request/Response transformation middleware."""
    
    def __init__(
        self,
        request_transform: Optional[Callable[[Request], Request]] = None,
        response_transform: Optional[Callable[[Response], Response]] = None,
    ):
        self._request_transform = request_transform
        self._response_transform = response_transform
    
    async def __call__(self, request: Request, next_fn: NextFn) -> Response:
        if self._request_transform:
            request = self._request_transform(request)
        
        response = await next_fn(request)
        
        if self._response_transform:
            response = self._response_transform(response)
        
        return response


class Route:
    """
    Route definition.
    """
    
    def __init__(self, config: RouteConfig):
        self._config = config
        self._pattern = self._compile_pattern(config.path)
        self._param_names = self._extract_params(config.path)
    
    @property
    def config(self) -> RouteConfig:
        return self._config
    
    @property
    def path(self) -> str:
        return self._config.path
    
    @property
    def methods(self) -> List[HttpMethod]:
        return self._config.methods
    
    def matches(self, method: HttpMethod, path: str) -> Optional[Dict[str, str]]:
        """Check if route matches request."""
        if method not in self._config.methods:
            return None
        
        match = self._pattern.match(path)
        if not match:
            return None
        
        return {name: match.group(name) for name in self._param_names}
    
    async def handle(self, request: Request) -> Response:
        """Handle request."""
        if self._config.handler:
            if asyncio.iscoroutinefunction(self._config.handler):
                return await self._config.handler(request)
            else:
                return self._config.handler(request)
        
        return Response.not_found()
    
    def _compile_pattern(self, path: str) -> Pattern:
        """Compile path to regex pattern."""
        # Convert {param} to named groups
        pattern = re.sub(r'\{(\w+)\}', r'(?P<\1>[^/]+)', path)
        return re.compile(f"^{pattern}$")
    
    def _extract_params(self, path: str) -> List[str]:
        """Extract parameter names from path."""
        return re.findall(r'\{(\w+)\}', path)


class Router:
    """
    Request router.
    """
    
    def __init__(self):
        self._routes: List[Route] = []
        self._not_found_handler: Optional[Callable] = None
    
    def add_route(self, config: RouteConfig) -> Route:
        """Add a route."""
        route = Route(config)
        self._routes.append(route)
        return route
    
    def route(
        self,
        path: str,
        methods: List[HttpMethod] = None,
        **kwargs,
    ) -> Callable:
        """Decorator to add route."""
        def decorator(handler: Callable) -> Callable:
            config = RouteConfig(
                path=path,
                methods=methods or [HttpMethod.GET],
                handler=handler,
                **kwargs,
            )
            self.add_route(config)
            return handler
        return decorator
    
    def match(self, method: HttpMethod, path: str) -> Optional[Tuple[Route, Dict[str, str]]]:
        """Find matching route."""
        for route in self._routes:
            params = route.matches(method, path)
            if params is not None:
                return route, params
        return None
    
    def set_not_found(self, handler: Callable) -> None:
        """Set 404 handler."""
        self._not_found_handler = handler


class ServiceRegistry:
    """
    Registry for backend services.
    """
    
    def __init__(self):
        self._services: Dict[str, List[str]] = {}
        self._index: Dict[str, int] = {}
    
    def register(self, name: str, url: str) -> None:
        """Register a service instance."""
        if name not in self._services:
            self._services[name] = []
            self._index[name] = 0
        self._services[name].append(url)
    
    def deregister(self, name: str, url: str) -> None:
        """Deregister a service instance."""
        if name in self._services:
            self._services[name] = [u for u in self._services[name] if u != url]
    
    def get(self, name: str) -> Optional[str]:
        """Get service URL (round-robin)."""
        instances = self._services.get(name, [])
        if not instances:
            return None
        
        idx = self._index.get(name, 0) % len(instances)
        self._index[name] = idx + 1
        
        return instances[idx]
    
    def get_all(self, name: str) -> List[str]:
        """Get all instances of a service."""
        return self._services.get(name, [])


class ResponseCache:
    """
    Simple response cache.
    """
    
    def __init__(self, default_ttl: int = 60):
        self._cache: Dict[str, Tuple[Response, float]] = {}
        self._default_ttl = default_ttl
    
    def _cache_key(self, request: Request) -> str:
        """Generate cache key."""
        return f"{request.method.value}:{request.path}:{json.dumps(request.query_params, sort_keys=True)}"
    
    def get(self, request: Request) -> Optional[Response]:
        """Get cached response."""
        key = self._cache_key(request)
        cached = self._cache.get(key)
        
        if cached:
            response, expires_at = cached
            if time.time() < expires_at:
                return response
            else:
                del self._cache[key]
        
        return None
    
    def set(self, request: Request, response: Response, ttl: Optional[int] = None) -> None:
        """Cache response."""
        key = self._cache_key(request)
        expires_at = time.time() + (ttl or self._default_ttl)
        self._cache[key] = (response, expires_at)
    
    def invalidate(self, pattern: str) -> None:
        """Invalidate cache entries matching pattern."""
        regex = re.compile(pattern)
        keys_to_delete = [k for k in self._cache.keys() if regex.match(k)]
        for key in keys_to_delete:
            del self._cache[key]


class ApiGateway:
    """
    API Gateway for routing, authentication, and request handling.
    """
    
    def __init__(self):
        self._router = Router()
        self._middleware: List[Middleware] = []
        self._services = ServiceRegistry()
        self._cache = ResponseCache()
    
    @property
    def router(self) -> Router:
        return self._router
    
    @property
    def services(self) -> ServiceRegistry:
        return self._services
    
    @property
    def cache(self) -> ResponseCache:
        return self._cache
    
    def use(self, middleware: Middleware) -> None:
        """Add middleware."""
        self._middleware.append(middleware)
    
    def route(
        self,
        path: str,
        methods: List[HttpMethod] = None,
        **kwargs,
    ) -> Callable:
        """Decorator to add route."""
        return self._router.route(path, methods, **kwargs)
    
    def add_route(self, config: RouteConfig) -> Route:
        """Add route configuration."""
        return self._router.add_route(config)
    
    async def handle(self, request: Request) -> Response:
        """Handle incoming request."""
        # Build middleware chain
        async def final_handler(req: Request) -> Response:
            return await self._dispatch(req)
        
        handler = final_handler
        for middleware in reversed(self._middleware):
            current_middleware = middleware
            next_handler = handler
            
            async def make_handler(m=current_middleware, n=next_handler):
                async def wrapped(req: Request) -> Response:
                    return await m(req, n)
                return wrapped
            
            handler = await make_handler()
        
        try:
            return await handler(request)
        except Exception as e:
            logger.exception(f"Error handling request: {e}")
            return Response.error(str(e))
    
    async def _dispatch(self, request: Request) -> Response:
        """Dispatch request to route handler."""
        result = self._router.match(request.method, request.path)
        
        if not result:
            return Response.not_found()
        
        route, params = result
        request.path_params = params
        
        # Check cache
        if request.method == HttpMethod.GET and route.config.cache_ttl:
            cached = self._cache.get(request)
            if cached:
                return cached
        
        # Handle request
        response = await route.handle(request)
        
        # Cache response
        if request.method == HttpMethod.GET and route.config.cache_ttl:
            self._cache.set(request, response, route.config.cache_ttl)
        
        return response


# Decorators
def api_route(
    path: str,
    methods: List[HttpMethod] = None,
    auth_required: bool = False,
    cache_ttl: Optional[int] = None,
) -> Callable:
    """
    Decorator to mark function as API route.
    
    Example:
        @api_route("/users/{id}", methods=[HttpMethod.GET])
        async def get_user(request: Request) -> Response:
            ...
    """
    def decorator(func: Callable) -> Callable:
        func._route_config = RouteConfig(
            path=path,
            methods=methods or [HttpMethod.GET],
            handler=func,
            auth_required=auth_required,
            cache_ttl=cache_ttl,
        )
        return func
    return decorator


def middleware(order: int = 100) -> Callable:
    """
    Decorator to mark class as middleware.
    
    Example:
        @middleware(order=10)
        class MyMiddleware(Middleware):
            ...
    """
    def decorator(cls: type) -> type:
        cls._middleware_order = order
        return cls
    return decorator


# Factory functions
def create_api_gateway() -> ApiGateway:
    """Create an API gateway."""
    return ApiGateway()


def create_request(
    method: HttpMethod,
    path: str,
    headers: Optional[Dict[str, str]] = None,
    body: Optional[Any] = None,
    query_params: Optional[Dict[str, str]] = None,
) -> Request:
    """Create a request."""
    return Request(
        method=method,
        path=path,
        headers=headers or {},
        body=body,
        query_params=query_params or {},
    )


def create_route_config(
    path: str,
    methods: List[HttpMethod] = None,
    handler: Optional[Callable] = None,
    **kwargs,
) -> RouteConfig:
    """Create route configuration."""
    return RouteConfig(
        path=path,
        methods=methods or [HttpMethod.GET],
        handler=handler,
        **kwargs,
    )


def create_auth_middleware(
    validator: Callable[[str], Awaitable[Optional[Dict]]],
) -> AuthMiddleware:
    """Create auth middleware."""
    return AuthMiddleware(validator=validator)


def create_rate_limit_middleware(
    requests_per_minute: int = 60,
) -> RateLimitMiddleware:
    """Create rate limit middleware."""
    return RateLimitMiddleware(requests_per_minute=requests_per_minute)


def create_cors_middleware(
    allow_origins: List[str] = None,
) -> CorsMiddleware:
    """Create CORS middleware."""
    return CorsMiddleware(allow_origins=allow_origins)


def create_logging_middleware() -> LoggingMiddleware:
    """Create logging middleware."""
    return LoggingMiddleware()


__all__ = [
    # Enums
    "HttpMethod",
    # Exceptions
    "GatewayError",
    "RouteNotFoundError",
    "AuthenticationError",
    "RateLimitError",
    # Data classes
    "Request",
    "Response",
    "RouteConfig",
    # Middleware
    "Middleware",
    "AuthMiddleware",
    "RateLimitMiddleware",
    "LoggingMiddleware",
    "CorsMiddleware",
    "TransformMiddleware",
    # Routing
    "Route",
    "Router",
    # Services
    "ServiceRegistry",
    "ResponseCache",
    # Gateway
    "ApiGateway",
    # Decorators
    "api_route",
    "middleware",
    # Factory functions
    "create_api_gateway",
    "create_request",
    "create_route_config",
    "create_auth_middleware",
    "create_rate_limit_middleware",
    "create_cors_middleware",
    "create_logging_middleware",
]
