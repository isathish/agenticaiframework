"""
Enterprise Webhook Receiver Module.

Provides webhook endpoints, payload validation,
signature verification, and event processing.

Example:
    # Create webhook receiver
    webhooks = create_webhook_receiver()
    
    # Register webhook handler
    @webhooks.handler("github", "push")
    async def handle_push(payload: dict, headers: dict):
        print(f"Push to {payload['repository']['name']}")
    
    # Configure provider
    webhooks.configure_provider(
        "github",
        secret="webhook_secret",
        signature_header="X-Hub-Signature-256",
    )
    
    # Process incoming webhook
    await webhooks.process(
        provider="github",
        payload=request_body,
        headers=request_headers,
    )
"""

from __future__ import annotations

import asyncio
import functools
import hashlib
import hmac
import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
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
    Type,
    TypeVar,
    Union,
)

T = TypeVar('T')


logger = logging.getLogger(__name__)


class WebhookError(Exception):
    """Webhook error."""
    pass


class SignatureError(WebhookError):
    """Signature verification error."""
    pass


class PayloadError(WebhookError):
    """Payload validation error."""
    pass


class ProcessingError(WebhookError):
    """Event processing error."""
    pass


class WebhookStatus(str, Enum):
    """Webhook processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


class SignatureAlgorithm(str, Enum):
    """Signature algorithms."""
    HMAC_SHA1 = "sha1"
    HMAC_SHA256 = "sha256"
    HMAC_SHA512 = "sha512"


@dataclass
class ProviderConfig:
    """Webhook provider configuration."""
    name: str
    secret: str
    signature_header: str = "X-Signature"
    signature_algorithm: SignatureAlgorithm = SignatureAlgorithm.HMAC_SHA256
    signature_prefix: str = ""  # e.g., "sha256="
    event_header: str = "X-Event-Type"
    id_header: str = "X-Webhook-ID"
    timestamp_header: str = ""
    timestamp_tolerance: int = 300  # seconds
    verify_signature: bool = True
    verify_timestamp: bool = False


@dataclass
class WebhookEvent:
    """Webhook event."""
    id: str
    provider: str
    event_type: str
    payload: Dict[str, Any]
    headers: Dict[str, str]
    received_at: datetime = field(default_factory=datetime.utcnow)
    status: WebhookStatus = WebhookStatus.PENDING
    retries: int = 0
    error: Optional[str] = None
    processed_at: Optional[datetime] = None


@dataclass
class ProcessingResult:
    """Webhook processing result."""
    event_id: str
    success: bool
    status: WebhookStatus
    response: Optional[Any] = None
    error: Optional[str] = None
    duration_ms: float = 0


@dataclass
class RetryConfig:
    """Retry configuration."""
    max_retries: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0


# Signature verification
class SignatureVerifier(ABC):
    """Signature verifier."""
    
    @abstractmethod
    def verify(
        self,
        payload: bytes,
        signature: str,
        secret: str,
    ) -> bool:
        """Verify signature."""
        pass


class HMACVerifier(SignatureVerifier):
    """HMAC signature verifier."""
    
    def __init__(
        self,
        algorithm: SignatureAlgorithm = SignatureAlgorithm.HMAC_SHA256,
        prefix: str = "",
    ):
        self._algorithm = algorithm
        self._prefix = prefix
    
    def verify(
        self,
        payload: bytes,
        signature: str,
        secret: str,
    ) -> bool:
        # Remove prefix if present
        sig = signature
        if self._prefix and sig.startswith(self._prefix):
            sig = sig[len(self._prefix):]
        
        # Get hash function
        hash_func = {
            SignatureAlgorithm.HMAC_SHA1: hashlib.sha1,
            SignatureAlgorithm.HMAC_SHA256: hashlib.sha256,
            SignatureAlgorithm.HMAC_SHA512: hashlib.sha512,
        }.get(self._algorithm, hashlib.sha256)
        
        # Compute expected signature
        expected = hmac.new(
            secret.encode(),
            payload,
            hash_func,
        ).hexdigest()
        
        # Constant-time comparison
        return hmac.compare_digest(expected, sig)


# Payload validation
class PayloadValidator(ABC):
    """Payload validator."""
    
    @abstractmethod
    def validate(
        self,
        payload: Dict[str, Any],
        event_type: str,
    ) -> Tuple[bool, Optional[str]]:
        """Validate payload. Returns (valid, error_message)."""
        pass


class SchemaValidator(PayloadValidator):
    """JSON schema validator."""
    
    def __init__(
        self,
        schemas: Dict[str, Dict[str, Any]],
    ):
        self._schemas = schemas
    
    def validate(
        self,
        payload: Dict[str, Any],
        event_type: str,
    ) -> Tuple[bool, Optional[str]]:
        schema = self._schemas.get(event_type)
        if not schema:
            return True, None  # No schema, assume valid
        
        # Basic schema validation (simplified)
        required = schema.get("required", [])
        for field in required:
            if field not in payload:
                return False, f"Missing required field: {field}"
        
        return True, None


class RequiredFieldsValidator(PayloadValidator):
    """Validates required fields exist."""
    
    def __init__(
        self,
        required_fields: Dict[str, List[str]],
    ):
        self._required_fields = required_fields
    
    def validate(
        self,
        payload: Dict[str, Any],
        event_type: str,
    ) -> Tuple[bool, Optional[str]]:
        fields = self._required_fields.get(event_type, [])
        
        for field in fields:
            if field not in payload:
                return False, f"Missing required field: {field}"
        
        return True, None


# Event store
class EventStore(ABC):
    """Event store for webhook events."""
    
    @abstractmethod
    async def store(self, event: WebhookEvent) -> None:
        """Store event."""
        pass
    
    @abstractmethod
    async def get(self, event_id: str) -> Optional[WebhookEvent]:
        """Get event by ID."""
        pass
    
    @abstractmethod
    async def update(self, event: WebhookEvent) -> None:
        """Update event."""
        pass
    
    @abstractmethod
    async def get_pending(self, limit: int = 100) -> List[WebhookEvent]:
        """Get pending events for retry."""
        pass


class InMemoryEventStore(EventStore):
    """In-memory event store."""
    
    def __init__(self, max_events: int = 10000):
        self._events: Dict[str, WebhookEvent] = {}
        self._max_events = max_events
    
    async def store(self, event: WebhookEvent) -> None:
        # Trim if needed
        if len(self._events) >= self._max_events:
            oldest = sorted(
                self._events.values(),
                key=lambda e: e.received_at,
            )[:100]
            for e in oldest:
                del self._events[e.id]
        
        self._events[event.id] = event
    
    async def get(self, event_id: str) -> Optional[WebhookEvent]:
        return self._events.get(event_id)
    
    async def update(self, event: WebhookEvent) -> None:
        self._events[event.id] = event
    
    async def get_pending(self, limit: int = 100) -> List[WebhookEvent]:
        pending = [
            e for e in self._events.values()
            if e.status in (WebhookStatus.PENDING, WebhookStatus.RETRYING)
        ]
        return sorted(pending, key=lambda e: e.received_at)[:limit]


# Middleware
class WebhookMiddleware(ABC):
    """Webhook middleware."""
    
    @abstractmethod
    async def process(
        self,
        event: WebhookEvent,
        next_handler: Callable,
    ) -> ProcessingResult:
        """Process event."""
        pass


class LoggingMiddleware(WebhookMiddleware):
    """Logging middleware."""
    
    async def process(
        self,
        event: WebhookEvent,
        next_handler: Callable,
    ) -> ProcessingResult:
        logger.info(
            f"Processing webhook: {event.provider}/{event.event_type} "
            f"(id={event.id})"
        )
        
        start_time = time.time()
        result = await next_handler(event)
        duration = (time.time() - start_time) * 1000
        
        if result.success:
            logger.info(
                f"Webhook processed successfully: {event.id} "
                f"({duration:.2f}ms)"
            )
        else:
            logger.error(
                f"Webhook processing failed: {event.id} - {result.error}"
            )
        
        return result


class RateLimitMiddleware(WebhookMiddleware):
    """Rate limiting middleware."""
    
    def __init__(
        self,
        max_per_second: int = 100,
    ):
        self._max_per_second = max_per_second
        self._counters: Dict[str, List[float]] = defaultdict(list)
    
    async def process(
        self,
        event: WebhookEvent,
        next_handler: Callable,
    ) -> ProcessingResult:
        now = time.time()
        key = f"{event.provider}:{event.event_type}"
        
        # Clean old entries
        self._counters[key] = [
            t for t in self._counters[key]
            if now - t < 1.0
        ]
        
        if len(self._counters[key]) >= self._max_per_second:
            return ProcessingResult(
                event_id=event.id,
                success=False,
                status=WebhookStatus.FAILED,
                error="Rate limit exceeded",
            )
        
        self._counters[key].append(now)
        return await next_handler(event)


class WebhookReceiver:
    """
    Webhook receiver and processor.
    """
    
    def __init__(
        self,
        event_store: Optional[EventStore] = None,
        retry_config: Optional[RetryConfig] = None,
    ):
        self._event_store = event_store or InMemoryEventStore()
        self._retry_config = retry_config or RetryConfig()
        
        self._providers: Dict[str, ProviderConfig] = {}
        self._handlers: Dict[str, Dict[str, List[Callable]]] = defaultdict(
            lambda: defaultdict(list)
        )
        self._validators: Dict[str, List[PayloadValidator]] = defaultdict(list)
        self._middlewares: List[WebhookMiddleware] = []
        
        self._running = False
        self._retry_task: Optional[asyncio.Task] = None
    
    async def start(self) -> None:
        """Start webhook receiver."""
        if self._running:
            return
        
        self._running = True
        self._retry_task = asyncio.create_task(self._retry_loop())
        logger.info("Webhook receiver started")
    
    async def stop(self) -> None:
        """Stop webhook receiver."""
        if not self._running:
            return
        
        self._running = False
        
        if self._retry_task:
            self._retry_task.cancel()
            try:
                await self._retry_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Webhook receiver stopped")
    
    async def _retry_loop(self) -> None:
        """Retry failed events."""
        while self._running:
            await asyncio.sleep(10)  # Check every 10 seconds
            
            pending = await self._event_store.get_pending()
            for event in pending:
                if event.retries >= self._retry_config.max_retries:
                    event.status = WebhookStatus.FAILED
                    await self._event_store.update(event)
                    continue
                
                # Calculate delay
                delay = min(
                    self._retry_config.initial_delay * (
                        self._retry_config.exponential_base ** event.retries
                    ),
                    self._retry_config.max_delay,
                )
                
                # Check if enough time has passed
                if event.processed_at:
                    elapsed = (datetime.utcnow() - event.processed_at).total_seconds()
                    if elapsed < delay:
                        continue
                
                # Retry
                event.status = WebhookStatus.RETRYING
                event.retries += 1
                await self._event_store.update(event)
                
                await self._process_event(event)
    
    # Provider configuration
    def configure_provider(
        self,
        name: str,
        secret: str,
        signature_header: str = "X-Signature",
        signature_algorithm: SignatureAlgorithm = SignatureAlgorithm.HMAC_SHA256,
        signature_prefix: str = "",
        event_header: str = "X-Event-Type",
        **kwargs,
    ) -> ProviderConfig:
        """Configure webhook provider."""
        config = ProviderConfig(
            name=name,
            secret=secret,
            signature_header=signature_header,
            signature_algorithm=signature_algorithm,
            signature_prefix=signature_prefix,
            event_header=event_header,
            **kwargs,
        )
        
        self._providers[name] = config
        return config
    
    def get_provider(self, name: str) -> Optional[ProviderConfig]:
        """Get provider config."""
        return self._providers.get(name)
    
    # Middleware
    def add_middleware(self, middleware: WebhookMiddleware) -> None:
        """Add middleware."""
        self._middlewares.append(middleware)
    
    # Validators
    def add_validator(
        self,
        provider: str,
        validator: PayloadValidator,
    ) -> None:
        """Add payload validator."""
        self._validators[provider].append(validator)
    
    # Handler registration
    def handler(
        self,
        provider: str,
        event_type: str,
    ) -> Callable:
        """Decorator to register webhook handler."""
        def decorator(func: Callable) -> Callable:
            self._handlers[provider][event_type].append(func)
            return func
        return decorator
    
    def register_handler(
        self,
        provider: str,
        event_type: str,
        handler: Callable,
    ) -> None:
        """Register webhook handler."""
        self._handlers[provider][event_type].append(handler)
    
    # Processing
    async def process(
        self,
        provider: str,
        payload: Union[bytes, str, Dict[str, Any]],
        headers: Dict[str, str],
    ) -> ProcessingResult:
        """
        Process incoming webhook.
        
        Args:
            provider: Webhook provider name
            payload: Raw payload (bytes, string, or dict)
            headers: Request headers
            
        Returns:
            Processing result
        """
        # Normalize headers to lowercase
        headers = {k.lower(): v for k, v in headers.items()}
        
        # Parse payload
        if isinstance(payload, bytes):
            raw_payload = payload
            payload_dict = json.loads(payload.decode())
        elif isinstance(payload, str):
            raw_payload = payload.encode()
            payload_dict = json.loads(payload)
        else:
            raw_payload = json.dumps(payload).encode()
            payload_dict = payload
        
        # Get provider config
        config = self._providers.get(provider)
        if not config:
            return ProcessingResult(
                event_id="",
                success=False,
                status=WebhookStatus.FAILED,
                error=f"Unknown provider: {provider}",
            )
        
        # Verify signature
        if config.verify_signature:
            signature = headers.get(config.signature_header.lower())
            if not signature:
                return ProcessingResult(
                    event_id="",
                    success=False,
                    status=WebhookStatus.FAILED,
                    error="Missing signature",
                )
            
            verifier = HMACVerifier(
                config.signature_algorithm,
                config.signature_prefix,
            )
            
            if not verifier.verify(raw_payload, signature, config.secret):
                return ProcessingResult(
                    event_id="",
                    success=False,
                    status=WebhookStatus.FAILED,
                    error="Invalid signature",
                )
        
        # Get event type
        event_type = headers.get(config.event_header.lower(), "unknown")
        
        # Get event ID
        event_id = headers.get(
            config.id_header.lower(),
            str(uuid.uuid4()),
        )
        
        # Validate payload
        for validator in self._validators.get(provider, []):
            valid, error = validator.validate(payload_dict, event_type)
            if not valid:
                return ProcessingResult(
                    event_id=event_id,
                    success=False,
                    status=WebhookStatus.FAILED,
                    error=error,
                )
        
        # Create event
        event = WebhookEvent(
            id=event_id,
            provider=provider,
            event_type=event_type,
            payload=payload_dict,
            headers=headers,
        )
        
        # Store event
        await self._event_store.store(event)
        
        # Process event
        return await self._process_event(event)
    
    async def _process_event(
        self,
        event: WebhookEvent,
    ) -> ProcessingResult:
        """Process webhook event."""
        event.status = WebhookStatus.PROCESSING
        await self._event_store.update(event)
        
        start_time = time.time()
        
        try:
            # Get handlers
            handlers = self._handlers.get(event.provider, {}).get(
                event.event_type, []
            )
            
            # Also check wildcard handlers
            handlers += self._handlers.get(event.provider, {}).get("*", [])
            
            if not handlers:
                logger.warning(
                    f"No handlers for {event.provider}/{event.event_type}"
                )
                event.status = WebhookStatus.COMPLETED
                event.processed_at = datetime.utcnow()
                await self._event_store.update(event)
                
                return ProcessingResult(
                    event_id=event.id,
                    success=True,
                    status=WebhookStatus.COMPLETED,
                )
            
            # Build handler chain with middleware
            async def final_handler(e: WebhookEvent) -> ProcessingResult:
                results = []
                for handler in handlers:
                    try:
                        result = await handler(e.payload, e.headers)
                        results.append(result)
                    except Exception as ex:
                        raise ProcessingError(str(ex))
                
                return ProcessingResult(
                    event_id=e.id,
                    success=True,
                    status=WebhookStatus.COMPLETED,
                    response=results,
                )
            
            handler_fn = final_handler
            for middleware in reversed(self._middlewares):
                handler_fn = self._wrap_middleware(middleware, handler_fn)
            
            result = await handler_fn(event)
            
            # Update event
            event.status = result.status
            event.processed_at = datetime.utcnow()
            await self._event_store.update(event)
            
            result.duration_ms = (time.time() - start_time) * 1000
            return result
            
        except Exception as e:
            event.status = WebhookStatus.RETRYING
            event.error = str(e)
            event.processed_at = datetime.utcnow()
            await self._event_store.update(event)
            
            return ProcessingResult(
                event_id=event.id,
                success=False,
                status=WebhookStatus.RETRYING,
                error=str(e),
                duration_ms=(time.time() - start_time) * 1000,
            )
    
    def _wrap_middleware(
        self,
        middleware: WebhookMiddleware,
        next_handler: Callable,
    ) -> Callable:
        """Wrap handler with middleware."""
        async def wrapped(event: WebhookEvent) -> ProcessingResult:
            return await middleware.process(event, next_handler)
        return wrapped
    
    # Event retrieval
    async def get_event(self, event_id: str) -> Optional[WebhookEvent]:
        """Get event by ID."""
        return await self._event_store.get(event_id)
    
    async def replay_event(self, event_id: str) -> ProcessingResult:
        """Replay event."""
        event = await self._event_store.get(event_id)
        if not event:
            return ProcessingResult(
                event_id=event_id,
                success=False,
                status=WebhookStatus.FAILED,
                error="Event not found",
            )
        
        event.retries = 0
        event.status = WebhookStatus.PENDING
        return await self._process_event(event)


# Decorators
def webhook_handler(
    provider: str,
    event_type: str,
    receiver: Optional[WebhookReceiver] = None,
) -> Callable:
    """Decorator to register webhook handler."""
    def decorator(func: Callable) -> Callable:
        func._webhook_provider = provider
        func._webhook_event_type = event_type
        
        if receiver:
            receiver.register_handler(provider, event_type, func)
        
        return func
    return decorator


def validate_payload(
    required_fields: List[str],
) -> Callable:
    """Decorator to validate payload fields."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(payload: dict, headers: dict):
            for field in required_fields:
                if field not in payload:
                    raise PayloadError(f"Missing required field: {field}")
            return await func(payload, headers)
        return wrapper
    return decorator


# Factory functions
def create_webhook_receiver(
    event_store: Optional[EventStore] = None,
    retry_config: Optional[RetryConfig] = None,
) -> WebhookReceiver:
    """Create webhook receiver."""
    return WebhookReceiver(
        event_store=event_store,
        retry_config=retry_config,
    )


def create_in_memory_store(max_events: int = 10000) -> InMemoryEventStore:
    """Create in-memory event store."""
    return InMemoryEventStore(max_events)


def create_retry_config(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
) -> RetryConfig:
    """Create retry configuration."""
    return RetryConfig(
        max_retries=max_retries,
        initial_delay=initial_delay,
        max_delay=max_delay,
    )


def create_schema_validator(
    schemas: Dict[str, Dict[str, Any]],
) -> SchemaValidator:
    """Create schema validator."""
    return SchemaValidator(schemas)


def create_required_fields_validator(
    required_fields: Dict[str, List[str]],
) -> RequiredFieldsValidator:
    """Create required fields validator."""
    return RequiredFieldsValidator(required_fields)


def create_logging_middleware() -> LoggingMiddleware:
    """Create logging middleware."""
    return LoggingMiddleware()


def create_rate_limit_middleware(
    max_per_second: int = 100,
) -> RateLimitMiddleware:
    """Create rate limit middleware."""
    return RateLimitMiddleware(max_per_second)


# Provider presets
def configure_github_provider(
    receiver: WebhookReceiver,
    secret: str,
) -> ProviderConfig:
    """Configure GitHub webhook provider."""
    return receiver.configure_provider(
        name="github",
        secret=secret,
        signature_header="X-Hub-Signature-256",
        signature_algorithm=SignatureAlgorithm.HMAC_SHA256,
        signature_prefix="sha256=",
        event_header="X-GitHub-Event",
        id_header="X-GitHub-Delivery",
    )


def configure_stripe_provider(
    receiver: WebhookReceiver,
    secret: str,
) -> ProviderConfig:
    """Configure Stripe webhook provider."""
    return receiver.configure_provider(
        name="stripe",
        secret=secret,
        signature_header="Stripe-Signature",
        signature_algorithm=SignatureAlgorithm.HMAC_SHA256,
        event_header="",  # Event type is in payload
    )


def configure_slack_provider(
    receiver: WebhookReceiver,
    secret: str,
) -> ProviderConfig:
    """Configure Slack webhook provider."""
    return receiver.configure_provider(
        name="slack",
        secret=secret,
        signature_header="X-Slack-Signature",
        signature_algorithm=SignatureAlgorithm.HMAC_SHA256,
        signature_prefix="v0=",
        event_header="",  # Event type is in payload
    )


__all__ = [
    # Exceptions
    "WebhookError",
    "SignatureError",
    "PayloadError",
    "ProcessingError",
    # Enums
    "WebhookStatus",
    "SignatureAlgorithm",
    # Data classes
    "ProviderConfig",
    "WebhookEvent",
    "ProcessingResult",
    "RetryConfig",
    # Signature verification
    "SignatureVerifier",
    "HMACVerifier",
    # Payload validation
    "PayloadValidator",
    "SchemaValidator",
    "RequiredFieldsValidator",
    # Event store
    "EventStore",
    "InMemoryEventStore",
    # Middleware
    "WebhookMiddleware",
    "LoggingMiddleware",
    "RateLimitMiddleware",
    # Receiver
    "WebhookReceiver",
    # Decorators
    "webhook_handler",
    "validate_payload",
    # Factory functions
    "create_webhook_receiver",
    "create_in_memory_store",
    "create_retry_config",
    "create_schema_validator",
    "create_required_fields_validator",
    "create_logging_middleware",
    "create_rate_limit_middleware",
    # Provider presets
    "configure_github_provider",
    "configure_stripe_provider",
    "configure_slack_provider",
]
