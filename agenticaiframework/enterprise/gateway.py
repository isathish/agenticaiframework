"""
Enterprise API Gateway Module.

Provides API gateway patterns, routing, request aggregation,
and cross-cutting concerns for microservices.

Example:
    # Create gateway
    gateway = create_api_gateway()
    
    # Register routes
    gateway.route("/users/{id}", "user-service", "/api/users/{id}")
    gateway.route("/orders/{id}", "order-service", "/api/orders/{id}")
    
    # Request aggregation
    @gateway.aggregate("/dashboard")
    async def dashboard(ctx: RequestContext):
        user = await ctx.call("user-service", "/profile")
        orders = await ctx.call("order-service", "/recent")
        return {"user": user, "orders": orders}
    
    # Run gateway
    response = await gateway.handle(request)
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Pattern,
    Set,
    Tuple,
    TypeVar,
)

logger = logging.getLogger(__name__)

T = TypeVar('T')


class GatewayError(Exception):
    """Gateway error."""
    pass


class RouteNotFoundError(GatewayError):
    """Route not found."""
    pass


class ServiceUnavailableError(GatewayError):
    """Backend service unavailable."""
    pass


class RateLimitExceededError(GatewayError):
    """Rate limit exceeded."""
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


@dataclass
class Request:
    """HTTP request representation."""
    method: HttpMethod
    path: str
    headers: Dict[str, str] = field(default_factory=dict)
    query_params: Dict[str, str] = field(default_factory=dict)
    body: Optional[Any] = None
    client_ip: Optional[str] = None
    request_id: Optional[str] = None
    
    def __post_init__(self):
        if not self.request_id:
            import uuid
            self.request_id = str(uuid.uuid4())


@dataclass
class Response:
    """HTTP response representation."""
    status_code: int
    headers: Dict[str, str] = field(default_factory=dict)
    body: Optional[Any] = None
    
    @classmethod
    def ok(cls, body: Any = None) -> 'Response':
        return cls(status_code=200, body=body)
    
    @classmethod
    def not_found(cls, message: str = "Not Found") -> 'Response':
        return cls(status_code=404, body={"error": message})
    
    @classmethod
    def error(cls, status: int, message: str) -> 'Response':
        return cls(status_code=status, body={"error": message})


@dataclass
class Route:
    """Route definition."""
    pattern: str
    service: str
    target_path: str
    methods: List[HttpMethod] = field(default_factory=lambda: list(HttpMethod))
    timeout_seconds: float = 30.0
    retry_count: int = 0
    strip_prefix: bool = False
    rewrite_path: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        # Compile pattern for path matching
        regex_pattern = re.sub(r'\{(\w+)\}', r'(?P<\1>[^/]+)', self.pattern)
        self._regex: Pattern = re.compile(f'^{regex_pattern}$')
    
    def matches(self, path: str) -> Optional[Dict[str, str]]:
        """Check if path matches route pattern."""
        match = self._regex.match(path)
        if match:
            return match.groupdict()
        return None


@dataclass
class RequestContext:
    """Context for request processing."""
    request: Request
    route: Optional[Route] = None
    path_params: Dict[str, str] = field(default_factory=dict)
    attributes: Dict[str, Any] = field(default_factory=dict)
    start_time: datetime = field(default_factory=datetime.now)
    
    def set(self, key: str, value: Any) -> None:
        """Set attribute."""
        self.attributes[key] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get attribute."""
        return self.attributes.get(key, default)


# Middleware
class GatewayMiddleware(ABC):
    """Abstract gateway middleware."""
    
    @abstractmethod
    async def process(
        self,
        context: RequestContext,
        next_handler: Callable[[RequestContext], Response],
    ) -> Response:
        """Process request."""
        pass


class LoggingMiddleware(GatewayMiddleware):
    """Request logging middleware."""
    
    async def process(
        self,
        context: RequestContext,
        next_handler: Callable[[RequestContext], Response],
    ) -> Response:
        start = time.time()
        
        logger.info(
            f"Request: {context.request.method} {context.request.path} "
            f"[{context.request.request_id}]"
        )
        
        response = await next_handler(context)
        
        duration = (time.time() - start) * 1000
        
        logger.info(
            f"Response: {response.status_code} in {duration:.2f}ms "
            f"[{context.request.request_id}]"
        )
        
        return response


class AuthenticationMiddleware(GatewayMiddleware):
    """Authentication middleware."""
    
    def __init__(
        self,
        token_validator: Callable[[str], bool],
        public_paths: Optional[List[str]] = None,
    ):
        self._validator = token_validator
        self._public_paths = public_paths or []
    
    async def process(
        self,
        context: RequestContext,
        next_handler: Callable[[RequestContext], Response],
    ) -> Response:
        # Check if path is public
        for path in self._public_paths:
            if context.request.path.startswith(path):
                return await next_handler(context)
        
        # Get token from header
        auth_header = context.request.headers.get("Authorization", "")
        
        if not auth_header.startswith("Bearer "):
            return Response.error(401, "Missing authentication token")
        
        token = auth_header[7:]  # Remove "Bearer "
        
        if asyncio.iscoroutinefunction(self._validator):
            valid = await self._validator(token)
        else:
            valid = self._validator(token)
        
        if not valid:
            return Response.error(401, "Invalid authentication token")
        
        return await next_handler(context)


class RateLimitMiddleware(GatewayMiddleware):
    """Rate limiting middleware."""
    
    def __init__(
        self,
        requests_per_minute: int = 60,
        key_extractor: Optional[Callable[[RequestContext], str]] = None,
    ):
        self._limit = requests_per_minute
        self._key_extractor = key_extractor or self._default_key
        self._buckets: Dict[str, List[float]] = {}
    
    def _default_key(self, context: RequestContext) -> str:
        """Default key: client IP."""
        return context.request.client_ip or "unknown"
    
    async def process(
        self,
        context: RequestContext,
        next_handler: Callable[[RequestContext], Response],
    ) -> Response:
        key = self._key_extractor(context)
        now = time.time()
        window_start = now - 60
        
        # Get or create bucket
        if key not in self._buckets:
            self._buckets[key] = []
        
        # Remove old entries
        self._buckets[key] = [
            t for t in self._buckets[key]
            if t > window_start
        ]
        
        # Check limit
        if len(self._buckets[key]) >= self._limit:
            return Response.error(429, "Rate limit exceeded")
        
        # Add request
        self._buckets[key].append(now)
        
        return await next_handler(context)


class CorsMiddleware(GatewayMiddleware):
    """CORS middleware."""
    
    def __init__(
        self,
        allowed_origins: List[str] = ["*"],
        allowed_methods: List[str] = ["GET", "POST", "PUT", "DELETE"],
        allowed_headers: List[str] = ["*"],
        max_age: int = 86400,
    ):
        self._origins = allowed_origins
        self._methods = allowed_methods
        self._headers = allowed_headers
        self._max_age = max_age
    
    async def process(
        self,
        context: RequestContext,
        next_handler: Callable[[RequestContext], Response],
    ) -> Response:
        origin = context.request.headers.get("Origin", "*")
        
        # Check if origin is allowed
        allowed_origin = "*" in self._origins or origin in self._origins
        
        if context.request.method == HttpMethod.OPTIONS:
            # Preflight request
            return Response(
                status_code=204,
                headers={
                    "Access-Control-Allow-Origin": origin if allowed_origin else "",
                    "Access-Control-Allow-Methods": ", ".join(self._methods),
                    "Access-Control-Allow-Headers": ", ".join(self._headers),
                    "Access-Control-Max-Age": str(self._max_age),
                },
            )
        
        response = await next_handler(context)
        
        if allowed_origin:
            response.headers["Access-Control-Allow-Origin"] = origin
        
        return response


class CachingMiddleware(GatewayMiddleware):
    """Response caching middleware."""
    
    def __init__(
        self,
        ttl_seconds: int = 60,
        cacheable_methods: List[HttpMethod] = [HttpMethod.GET],
    ):
        self._cache: Dict[str, Tuple[Response, datetime]] = {}
        self._ttl = timedelta(seconds=ttl_seconds)
        self._methods = cacheable_methods
    
    def _cache_key(self, context: RequestContext) -> str:
        """Generate cache key."""
        return hashlib.md5(
            f"{context.request.method}:{context.request.path}".encode()
        ).hexdigest()
    
    async def process(
        self,
        context: RequestContext,
        next_handler: Callable[[RequestContext], Response],
    ) -> Response:
        if context.request.method not in self._methods:
            return await next_handler(context)
        
        key = self._cache_key(context)
        
        # Check cache
        if key in self._cache:
            response, cached_at = self._cache[key]
            if datetime.now() - cached_at < self._ttl:
                response.headers["X-Cache"] = "HIT"
                return response
        
        response = await next_handler(context)
        
        # Cache successful responses
        if response.status_code == 200:
            self._cache[key] = (response, datetime.now())
            response.headers["X-Cache"] = "MISS"
        
        return response


# Service Backend
class ServiceBackend(ABC):
    """Abstract service backend."""
    
    @abstractmethod
    async def call(
        self,
        service: str,
        path: str,
        method: HttpMethod,
        headers: Dict[str, str],
        body: Optional[Any],
        timeout: float,
    ) -> Response:
        """Call backend service."""
        pass


class MockServiceBackend(ServiceBackend):
    """Mock service backend for testing."""
    
    def __init__(self):
        self._responses: Dict[str, Response] = {}
    
    def mock(
        self,
        service: str,
        path: str,
        response: Response,
    ) -> None:
        """Mock a service response."""
        key = f"{service}:{path}"
        self._responses[key] = response
    
    async def call(
        self,
        service: str,
        path: str,
        method: HttpMethod,
        headers: Dict[str, str],
        body: Optional[Any],
        timeout: float,
    ) -> Response:
        key = f"{service}:{path}"
        
        if key in self._responses:
            return self._responses[key]
        
        # Default mock response
        return Response.ok({"service": service, "path": path})


# API Gateway
class ApiGateway:
    """
    API Gateway for routing and request handling.
    """
    
    def __init__(
        self,
        backend: Optional[ServiceBackend] = None,
    ):
        self._backend = backend or MockServiceBackend()
        self._routes: List[Route] = []
        self._middleware: List[GatewayMiddleware] = []
        self._aggregators: Dict[str, Callable] = {}
    
    def route(
        self,
        pattern: str,
        service: str,
        target_path: Optional[str] = None,
        methods: Optional[List[HttpMethod]] = None,
        **kwargs: Any,
    ) -> 'ApiGateway':
        """Add a route."""
        route = Route(
            pattern=pattern,
            service=service,
            target_path=target_path or pattern,
            methods=methods or list(HttpMethod),
            **kwargs,
        )
        self._routes.append(route)
        return self
    
    def use(self, middleware: GatewayMiddleware) -> 'ApiGateway':
        """Add middleware."""
        self._middleware.append(middleware)
        return self
    
    def aggregate(
        self,
        pattern: str,
    ) -> Callable:
        """
        Decorator for request aggregation.
        
        Example:
            @gateway.aggregate("/dashboard")
            async def dashboard(ctx):
                ...
        """
        def decorator(func: Callable) -> Callable:
            self._aggregators[pattern] = func
            return func
        
        return decorator
    
    async def handle(self, request: Request) -> Response:
        """Handle incoming request."""
        context = RequestContext(request=request)
        
        # Build middleware chain
        async def final_handler(ctx: RequestContext) -> Response:
            return await self._route_request(ctx)
        
        chain = final_handler
        
        for middleware in reversed(self._middleware):
            chain = self._wrap_middleware(middleware, chain)
        
        return await chain(context)
    
    def _wrap_middleware(
        self,
        middleware: GatewayMiddleware,
        next_handler: Callable[[RequestContext], Response],
    ) -> Callable[[RequestContext], Response]:
        """Wrap handler with middleware."""
        async def wrapped(ctx: RequestContext) -> Response:
            return await middleware.process(ctx, next_handler)
        return wrapped
    
    async def _route_request(
        self,
        context: RequestContext,
    ) -> Response:
        """Route request to backend or aggregator."""
        path = context.request.path
        
        # Check aggregators first
        if path in self._aggregators:
            return await self._handle_aggregation(context)
        
        # Find matching route
        for route in self._routes:
            params = route.matches(path)
            
            if params is not None:
                # Check method
                if context.request.method not in route.methods:
                    continue
                
                context.route = route
                context.path_params = params
                
                return await self._forward_request(context)
        
        return Response.not_found(f"No route for: {path}")
    
    async def _forward_request(
        self,
        context: RequestContext,
    ) -> Response:
        """Forward request to backend service."""
        route = context.route
        
        if not route:
            return Response.error(500, "No route in context")
        
        # Build target path
        target_path = route.target_path
        for key, value in context.path_params.items():
            target_path = target_path.replace(f"{{{key}}}", value)
        
        # Apply path rewrite if configured
        if route.rewrite_path:
            target_path = route.rewrite_path
            for key, value in context.path_params.items():
                target_path = target_path.replace(f"{{{key}}}", value)
        
        # Strip prefix if configured
        if route.strip_prefix:
            prefix = route.pattern.split("{")[0].rstrip("/")
            if context.request.path.startswith(prefix):
                target_path = context.request.path[len(prefix):]
        
        # Forward headers
        headers = dict(context.request.headers)
        headers["X-Request-ID"] = context.request.request_id or ""
        headers["X-Forwarded-For"] = context.request.client_ip or ""
        
        # Call backend
        try:
            return await self._backend.call(
                service=route.service,
                path=target_path,
                method=context.request.method,
                headers=headers,
                body=context.request.body,
                timeout=route.timeout_seconds,
            )
        except Exception as e:
            logger.error(f"Backend error: {e}")
            return Response.error(502, f"Backend error: {str(e)}")
    
    async def _handle_aggregation(
        self,
        context: RequestContext,
    ) -> Response:
        """Handle aggregation request."""
        aggregator = self._aggregators.get(context.request.path)
        
        if not aggregator:
            return Response.not_found()
        
        # Create aggregation context
        agg_context = AggregationContext(
            request=context.request,
            backend=self._backend,
        )
        
        try:
            result = await aggregator(agg_context)
            return Response.ok(result)
        
        except Exception as e:
            logger.error(f"Aggregation error: {e}")
            return Response.error(500, str(e))


class AggregationContext:
    """Context for request aggregation."""
    
    def __init__(
        self,
        request: Request,
        backend: ServiceBackend,
    ):
        self.request = request
        self._backend = backend
    
    async def call(
        self,
        service: str,
        path: str,
        method: HttpMethod = HttpMethod.GET,
        body: Optional[Any] = None,
        timeout: float = 30.0,
    ) -> Any:
        """Call a backend service."""
        response = await self._backend.call(
            service=service,
            path=path,
            method=method,
            headers=dict(self.request.headers),
            body=body,
            timeout=timeout,
        )
        
        if response.status_code >= 400:
            raise GatewayError(
                f"Service {service} returned {response.status_code}"
            )
        
        return response.body
    
    async def parallel(
        self,
        *calls: Tuple[str, str],
    ) -> List[Any]:
        """Make parallel calls to services."""
        tasks = [
            self.call(service, path)
            for service, path in calls
        ]
        return await asyncio.gather(*tasks, return_exceptions=True)


# Decorators
def gateway_route(
    pattern: str,
    service: str,
    methods: Optional[List[HttpMethod]] = None,
) -> Callable:
    """
    Decorator to define a gateway route handler.
    
    Example:
        @gateway_route("/users/{id}", "user-service")
        async def get_user(context: RequestContext):
            ...
    """
    def decorator(func: Callable) -> Callable:
        func._gateway_route = {
            "pattern": pattern,
            "service": service,
            "methods": methods,
        }
        return func
    
    return decorator


def requires_auth(
    roles: Optional[List[str]] = None,
) -> Callable:
    """
    Decorator to require authentication.
    
    Example:
        @requires_auth(roles=["admin"])
        async def admin_endpoint(ctx):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(context: RequestContext, *args: Any, **kwargs: Any) -> Any:
            # Check if authenticated (set by middleware)
            if not context.get("authenticated", False):
                return Response.error(401, "Authentication required")
            
            if roles:
                user_roles = context.get("user_roles", [])
                if not any(r in user_roles for r in roles):
                    return Response.error(403, "Insufficient permissions")
            
            return await func(context, *args, **kwargs)
        
        return wrapper
    
    return decorator


# Factory functions
def create_api_gateway(
    backend: Optional[ServiceBackend] = None,
) -> ApiGateway:
    """Create an API gateway."""
    return ApiGateway(backend)


def create_mock_backend() -> MockServiceBackend:
    """Create a mock service backend."""
    return MockServiceBackend()


def create_logging_middleware() -> LoggingMiddleware:
    """Create logging middleware."""
    return LoggingMiddleware()


def create_rate_limit_middleware(
    requests_per_minute: int = 60,
) -> RateLimitMiddleware:
    """Create rate limiting middleware."""
    return RateLimitMiddleware(requests_per_minute)


def create_cors_middleware(
    allowed_origins: Optional[List[str]] = None,
) -> CorsMiddleware:
    """Create CORS middleware."""
    return CorsMiddleware(allowed_origins or ["*"])


__all__ = [
    # Exceptions
    "GatewayError",
    "RouteNotFoundError",
    "ServiceUnavailableError",
    "RateLimitExceededError",
    # Enums
    "HttpMethod",
    # Data classes
    "Request",
    "Response",
    "Route",
    "RequestContext",
    # Middleware
    "GatewayMiddleware",
    "LoggingMiddleware",
    "AuthenticationMiddleware",
    "RateLimitMiddleware",
    "CorsMiddleware",
    "CachingMiddleware",
    # Backend
    "ServiceBackend",
    "MockServiceBackend",
    # Gateway
    "ApiGateway",
    "AggregationContext",
    # Decorators
    "gateway_route",
    "requires_auth",
    # Factory functions
    "create_api_gateway",
    "create_mock_backend",
    "create_logging_middleware",
    "create_rate_limit_middleware",
    "create_cors_middleware",
]
