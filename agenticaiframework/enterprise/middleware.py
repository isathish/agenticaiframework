"""
Enterprise Middleware - Request/response processing pipeline.

Middleware provides a way to intercept and process requests and responses
at various stages of the pipeline.

Features:
- Pre-processing hooks
- Post-processing hooks
- Error handling
- Logging middleware
- Metrics middleware
- Auth middleware
- Rate limiting middleware
- Caching middleware
"""

import asyncio
import functools
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union
import uuid

logger = logging.getLogger(__name__)

T = TypeVar("T")


# =============================================================================
# Request/Response Types
# =============================================================================

@dataclass
class Request:
    """A request to be processed."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    method: str = "invoke"
    data: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Context that can be modified by middleware
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Response:
    """A response from processing."""
    request_id: str = ""
    data: Any = None
    success: bool = True
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    duration_ms: float = 0.0


# =============================================================================
# Middleware Base
# =============================================================================

class Middleware(ABC):
    """
    Base class for middleware.
    
    Middleware can process requests before they are handled and
    responses after they are generated.
    """
    
    @abstractmethod
    async def process_request(self, request: Request) -> Request:
        """
        Process a request before it is handled.
        
        Args:
            request: The incoming request
            
        Returns:
            Modified request
        """
        return request
    
    @abstractmethod
    async def process_response(
        self,
        request: Request,
        response: Response,
    ) -> Response:
        """
        Process a response after it is generated.
        
        Args:
            request: The original request
            response: The generated response
            
        Returns:
            Modified response
        """
        return response
    
    async def process_error(
        self,
        request: Request,
        error: Exception,
    ) -> Optional[Response]:
        """
        Process an error that occurred during handling.
        
        Args:
            request: The original request
            error: The exception that occurred
            
        Returns:
            Optional error response, or None to propagate
        """
        return None


class MiddlewarePipeline:
    """
    Pipeline for chaining middleware.
    
    Usage:
        >>> pipeline = MiddlewarePipeline()
        >>> pipeline.add(LoggingMiddleware())
        >>> pipeline.add(AuthMiddleware())
        >>> pipeline.add(RateLimitMiddleware())
        >>> 
        >>> @pipeline.wrap
        >>> async def my_handler(request):
        ...     return Response(data="result")
    """
    
    def __init__(self):
        self._middleware: List[Middleware] = []
    
    def add(self, middleware: Middleware):
        """Add middleware to the pipeline."""
        self._middleware.append(middleware)
    
    def remove(self, middleware_type: Type[Middleware]):
        """Remove middleware of a specific type."""
        self._middleware = [
            m for m in self._middleware
            if not isinstance(m, middleware_type)
        ]
    
    async def process_request(self, request: Request) -> Request:
        """Process request through all middleware."""
        for middleware in self._middleware:
            request = await middleware.process_request(request)
        return request
    
    async def process_response(
        self,
        request: Request,
        response: Response,
    ) -> Response:
        """Process response through all middleware (reverse order)."""
        for middleware in reversed(self._middleware):
            response = await middleware.process_response(request, response)
        return response
    
    async def process_error(
        self,
        request: Request,
        error: Exception,
    ) -> Optional[Response]:
        """Process error through middleware."""
        for middleware in reversed(self._middleware):
            response = await middleware.process_error(request, error)
            if response is not None:
                return response
        return None
    
    def wrap(self, handler: Callable) -> Callable:
        """Wrap a handler with the middleware pipeline."""
        @functools.wraps(handler)
        async def wrapper(*args, **kwargs) -> Response:
            # Create request
            request = Request(
                method=handler.__name__,
                data={"args": args, "kwargs": kwargs},
            )
            
            start_time = time.time()
            
            try:
                # Process request
                request = await self.process_request(request)
                
                # Call handler
                result = await handler(*args, **kwargs)
                
                # Create response
                response = Response(
                    request_id=request.id,
                    data=result,
                    success=True,
                    duration_ms=(time.time() - start_time) * 1000,
                )
                
                # Process response
                response = await self.process_response(request, response)
                
                return response
                
            except Exception as e:
                # Try to handle error
                error_response = await self.process_error(request, e)
                
                if error_response:
                    return error_response
                
                # Re-raise if not handled
                raise
        
        return wrapper


# =============================================================================
# Built-in Middleware
# =============================================================================

class LoggingMiddleware(Middleware):
    """Middleware for logging requests and responses."""
    
    def __init__(
        self,
        log_request: bool = True,
        log_response: bool = True,
        log_errors: bool = True,
        include_data: bool = False,
    ):
        self.log_request = log_request
        self.log_response = log_response
        self.log_errors = log_errors
        self.include_data = include_data
    
    async def process_request(self, request: Request) -> Request:
        if self.log_request:
            data_str = f", data={request.data}" if self.include_data else ""
            logger.info(
                f"Request {request.id}: method={request.method}{data_str}"
            )
        return request
    
    async def process_response(
        self,
        request: Request,
        response: Response,
    ) -> Response:
        if self.log_response:
            status = "success" if response.success else "failed"
            logger.info(
                f"Response {request.id}: status={status}, "
                f"duration={response.duration_ms:.2f}ms"
            )
        return response
    
    async def process_error(
        self,
        request: Request,
        error: Exception,
    ) -> Optional[Response]:
        if self.log_errors:
            logger.error(f"Error {request.id}: {type(error).__name__}: {error}")
        return None


class MetricsMiddleware(Middleware):
    """Middleware for collecting metrics."""
    
    def __init__(self, metrics_collector=None):
        from .utils import metrics as default_metrics
        self.metrics = metrics_collector or default_metrics
    
    async def process_request(self, request: Request) -> Request:
        await self.metrics.increment(
            "requests_total",
            labels={"method": request.method},
        )
        request.context["start_time"] = time.time()
        return request
    
    async def process_response(
        self,
        request: Request,
        response: Response,
    ) -> Response:
        duration = time.time() - request.context.get("start_time", time.time())
        
        await self.metrics.histogram(
            "request_duration_seconds",
            duration,
            labels={"method": request.method},
        )
        
        status = "success" if response.success else "error"
        await self.metrics.increment(
            "responses_total",
            labels={"method": request.method, "status": status},
        )
        
        return response
    
    async def process_error(
        self,
        request: Request,
        error: Exception,
    ) -> Optional[Response]:
        await self.metrics.increment(
            "errors_total",
            labels={
                "method": request.method,
                "error_type": type(error).__name__,
            },
        )
        return None


class AuthMiddleware(Middleware):
    """Middleware for authentication."""
    
    def __init__(
        self,
        auth_fn: Optional[Callable[[Request], bool]] = None,
        token_header: str = "Authorization",
    ):
        self.auth_fn = auth_fn
        self.token_header = token_header
    
    async def process_request(self, request: Request) -> Request:
        # Check for auth token
        token = request.metadata.get(self.token_header)
        
        if self.auth_fn:
            if not self.auth_fn(request):
                raise AuthenticationError("Authentication failed")
        elif not token:
            raise AuthenticationError("No authentication token provided")
        
        # Extract user info (simplified)
        request.context["authenticated"] = True
        request.context["user_id"] = request.metadata.get("user_id")
        
        return request
    
    async def process_response(
        self,
        request: Request,
        response: Response,
    ) -> Response:
        return response


class RateLimitMiddleware(Middleware):
    """Middleware for rate limiting."""
    
    def __init__(
        self,
        requests_per_second: float = 10.0,
        burst_size: int = 20,
        per_user: bool = True,
    ):
        from .utils import RateLimiter, KeyedRateLimiter
        
        self.per_user = per_user
        if per_user:
            self._limiter = KeyedRateLimiter(requests_per_second, burst_size)
        else:
            self._limiter = RateLimiter(requests_per_second, burst_size)
    
    async def process_request(self, request: Request) -> Request:
        if self.per_user:
            key = request.context.get("user_id", "anonymous")
            await self._limiter.acquire(key)
        else:
            await self._limiter.acquire()
        
        return request
    
    async def process_response(
        self,
        request: Request,
        response: Response,
    ) -> Response:
        return response


class CachingMiddleware(Middleware):
    """Middleware for caching responses."""
    
    def __init__(
        self,
        cache=None,
        ttl: float = 300.0,
        key_fn: Optional[Callable[[Request], str]] = None,
    ):
        from .utils import AsyncCache
        
        self.cache = cache or AsyncCache(default_ttl=ttl)
        self.ttl = ttl
        self.key_fn = key_fn or self._default_key_fn
    
    def _default_key_fn(self, request: Request) -> str:
        """Generate default cache key."""
        import hashlib
        import json
        
        data = json.dumps({
            "method": request.method,
            "data": str(request.data),
        }, sort_keys=True)
        return hashlib.md5(data.encode()).hexdigest()
    
    async def process_request(self, request: Request) -> Request:
        cache_key = self.key_fn(request)
        cached = await self.cache.get(cache_key)
        
        if cached is not None:
            request.context["cached_response"] = cached
            request.context["cache_hit"] = True
        else:
            request.context["cache_key"] = cache_key
            request.context["cache_hit"] = False
        
        return request
    
    async def process_response(
        self,
        request: Request,
        response: Response,
    ) -> Response:
        # Return cached response if available
        if request.context.get("cache_hit"):
            return request.context["cached_response"]
        
        # Cache successful responses
        if response.success:
            cache_key = request.context.get("cache_key")
            if cache_key:
                await self.cache.set(cache_key, response)
        
        return response


class RetryMiddleware(Middleware):
    """Middleware for automatic retries."""
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        retryable_errors: tuple = (Exception,),
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.retryable_errors = retryable_errors
    
    async def process_request(self, request: Request) -> Request:
        request.context["retry_count"] = 0
        return request
    
    async def process_response(
        self,
        request: Request,
        response: Response,
    ) -> Response:
        return response
    
    async def process_error(
        self,
        request: Request,
        error: Exception,
    ) -> Optional[Response]:
        if not isinstance(error, self.retryable_errors):
            return None
        
        retry_count = request.context.get("retry_count", 0)
        
        if retry_count < self.max_retries:
            # Calculate delay with exponential backoff
            delay = min(
                self.base_delay * (2 ** retry_count),
                self.max_delay,
            )
            
            logger.warning(
                f"Retry {retry_count + 1}/{self.max_retries} "
                f"after {delay:.2f}s for request {request.id}"
            )
            
            request.context["retry_count"] = retry_count + 1
            await asyncio.sleep(delay)
            
            # Signal that request should be retried
            # In a real implementation, this would re-invoke the handler
            return None
        
        return None


class TracingMiddleware(Middleware):
    """Middleware for distributed tracing."""
    
    def __init__(self, tracer=None):
        self.tracer = tracer
    
    async def process_request(self, request: Request) -> Request:
        # Create span
        span_id = str(uuid.uuid4())[:16]
        trace_id = request.metadata.get("trace_id", str(uuid.uuid4())[:32])
        parent_id = request.metadata.get("span_id")
        
        request.context["span_id"] = span_id
        request.context["trace_id"] = trace_id
        request.context["parent_span_id"] = parent_id
        request.context["span_start"] = time.time()
        
        logger.debug(
            f"Span started: trace={trace_id}, span={span_id}, "
            f"parent={parent_id}, method={request.method}"
        )
        
        return request
    
    async def process_response(
        self,
        request: Request,
        response: Response,
    ) -> Response:
        duration = time.time() - request.context.get("span_start", time.time())
        
        logger.debug(
            f"Span ended: trace={request.context.get('trace_id')}, "
            f"span={request.context.get('span_id')}, "
            f"duration={duration*1000:.2f}ms"
        )
        
        # Add tracing info to response
        response.metadata["trace_id"] = request.context.get("trace_id")
        response.metadata["span_id"] = request.context.get("span_id")
        
        return response


class ValidationMiddleware(Middleware):
    """Middleware for request/response validation."""
    
    def __init__(
        self,
        request_schema: Optional[Type] = None,
        response_schema: Optional[Type] = None,
    ):
        self.request_schema = request_schema
        self.response_schema = response_schema
    
    async def process_request(self, request: Request) -> Request:
        if self.request_schema and request.data:
            try:
                # Validate using Pydantic-like validation
                if hasattr(self.request_schema, "model_validate"):
                    self.request_schema.model_validate(request.data)
                elif hasattr(self.request_schema, "__call__"):
                    self.request_schema(request.data)
            except Exception as e:
                raise ValidationError(f"Request validation failed: {e}")
        
        return request
    
    async def process_response(
        self,
        request: Request,
        response: Response,
    ) -> Response:
        if self.response_schema and response.data:
            try:
                if hasattr(self.response_schema, "model_validate"):
                    self.response_schema.model_validate(response.data)
                elif hasattr(self.response_schema, "__call__"):
                    self.response_schema(response.data)
            except Exception as e:
                raise ValidationError(f"Response validation failed: {e}")
        
        return response


# =============================================================================
# Hooks System
# =============================================================================

class HookType(Enum):
    """Types of hooks."""
    PRE_INVOKE = "pre_invoke"
    POST_INVOKE = "post_invoke"
    PRE_TOOL_CALL = "pre_tool_call"
    POST_TOOL_CALL = "post_tool_call"
    ON_ERROR = "on_error"
    ON_RETRY = "on_retry"


@dataclass
class HookContext:
    """Context passed to hooks."""
    hook_type: HookType
    data: Any
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[Exception] = None


class HooksManager:
    """
    Manager for lifecycle hooks.
    
    Usage:
        >>> hooks = HooksManager()
        >>> 
        >>> @hooks.on(HookType.PRE_INVOKE)
        >>> async def before_invoke(ctx: HookContext):
        ...     print(f"About to invoke with: {ctx.data}")
        >>> 
        >>> @hooks.on(HookType.POST_INVOKE)
        >>> async def after_invoke(ctx: HookContext):
        ...     print(f"Invocation complete: {ctx.data}")
    """
    
    def __init__(self):
        self._hooks: Dict[HookType, List[Callable]] = {
            hook_type: [] for hook_type in HookType
        }
    
    def on(self, hook_type: HookType):
        """Decorator to register a hook."""
        def decorator(fn: Callable) -> Callable:
            self._hooks[hook_type].append(fn)
            return fn
        return decorator
    
    def register(self, hook_type: HookType, fn: Callable):
        """Register a hook function."""
        self._hooks[hook_type].append(fn)
    
    def unregister(self, hook_type: HookType, fn: Callable):
        """Unregister a hook function."""
        if fn in self._hooks[hook_type]:
            self._hooks[hook_type].remove(fn)
    
    async def trigger(
        self,
        hook_type: HookType,
        data: Any = None,
        error: Optional[Exception] = None,
        **metadata,
    ) -> Any:
        """Trigger all hooks of a specific type."""
        context = HookContext(
            hook_type=hook_type,
            data=data,
            metadata=metadata,
            error=error,
        )
        
        for hook in self._hooks[hook_type]:
            try:
                if asyncio.iscoroutinefunction(hook):
                    result = await hook(context)
                else:
                    result = hook(context)
                
                # Allow hooks to modify data
                if result is not None:
                    context.data = result
            except Exception as e:
                logger.error(f"Hook error in {hook.__name__}: {e}")
        
        return context.data


# =============================================================================
# Exceptions
# =============================================================================

class MiddlewareError(Exception):
    """Base exception for middleware errors."""
    pass


class AuthenticationError(MiddlewareError):
    """Authentication failed."""
    pass


class AuthorizationError(MiddlewareError):
    """Authorization failed."""
    pass


class ValidationError(MiddlewareError):
    """Validation failed."""
    pass


class RateLimitExceeded(MiddlewareError):
    """Rate limit exceeded."""
    pass


# =============================================================================
# Pre-configured Pipelines
# =============================================================================

def create_standard_pipeline() -> MiddlewarePipeline:
    """Create a standard middleware pipeline."""
    pipeline = MiddlewarePipeline()
    pipeline.add(TracingMiddleware())
    pipeline.add(LoggingMiddleware())
    pipeline.add(MetricsMiddleware())
    return pipeline


def create_secure_pipeline(
    auth_fn: Optional[Callable] = None,
) -> MiddlewarePipeline:
    """Create a secure middleware pipeline with auth."""
    pipeline = MiddlewarePipeline()
    pipeline.add(TracingMiddleware())
    pipeline.add(LoggingMiddleware())
    pipeline.add(MetricsMiddleware())
    pipeline.add(AuthMiddleware(auth_fn=auth_fn))
    pipeline.add(RateLimitMiddleware())
    return pipeline


def create_cached_pipeline(
    ttl: float = 300.0,
) -> MiddlewarePipeline:
    """Create a cached middleware pipeline."""
    pipeline = MiddlewarePipeline()
    pipeline.add(TracingMiddleware())
    pipeline.add(LoggingMiddleware())
    pipeline.add(MetricsMiddleware())
    pipeline.add(CachingMiddleware(ttl=ttl))
    return pipeline


# Global hooks manager
hooks = HooksManager()
