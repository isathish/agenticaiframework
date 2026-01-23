"""
Enterprise Webhook Module.

Provides webhook endpoints, signature verification,
retry logic, and delivery tracking.

Example:
    # Create webhook manager
    webhooks = create_webhook_manager()
    
    # Register webhook
    webhook = await webhooks.register(
        url="https://example.com/hook",
        events=["order.created", "order.updated"],
        secret="webhook_secret_123"
    )
    
    # Trigger webhook
    await webhooks.trigger("order.created", {"order_id": 123})
    
    # Verify incoming webhook
    @verify_webhook(secret="shared_secret")
    async def handle_webhook(payload: dict):
        ...
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
    Set,
)

logger = logging.getLogger(__name__)


class WebhookError(Exception):
    """Webhook error."""
    pass


class SignatureError(WebhookError):
    """Signature verification failed."""
    pass


class DeliveryError(WebhookError):
    """Webhook delivery failed."""
    pass


class WebhookStatus(str, Enum):
    """Webhook status."""
    ACTIVE = "active"
    PAUSED = "paused"
    DISABLED = "disabled"


class DeliveryStatus(str, Enum):
    """Delivery status."""
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"


class SignatureAlgorithm(str, Enum):
    """Signature algorithms."""
    SHA256 = "sha256"
    SHA512 = "sha512"
    SHA1 = "sha1"


@dataclass
class Webhook:
    """Webhook definition."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    url: str = ""
    events: List[str] = field(default_factory=list)
    secret: str = ""
    status: WebhookStatus = WebhookStatus.ACTIVE
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    headers: Dict[str, str] = field(default_factory=dict)
    retry_count: int = 3
    timeout_seconds: int = 30
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "url": self.url,
            "events": self.events,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "headers": self.headers,
            "retry_count": self.retry_count,
            "timeout_seconds": self.timeout_seconds,
            "metadata": self.metadata,
        }


@dataclass
class DeliveryAttempt:
    """Webhook delivery attempt."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    webhook_id: str = ""
    event: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    status: DeliveryStatus = DeliveryStatus.PENDING
    attempt_number: int = 1
    status_code: Optional[int] = None
    response_body: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    duration_ms: float = 0.0


@dataclass
class DeliveryResult:
    """Result of webhook delivery."""
    webhook_id: str
    event: str
    success: bool
    attempts: int
    status_code: Optional[int] = None
    error: Optional[str] = None
    duration_ms: float = 0.0


@dataclass
class WebhookStats:
    """Webhook statistics."""
    total_webhooks: int = 0
    active_webhooks: int = 0
    total_deliveries: int = 0
    successful_deliveries: int = 0
    failed_deliveries: int = 0
    avg_delivery_time_ms: float = 0.0


class SignatureGenerator:
    """Generate and verify webhook signatures."""
    
    def __init__(
        self,
        algorithm: SignatureAlgorithm = SignatureAlgorithm.SHA256,
        header_name: str = "X-Signature",
    ):
        self._algorithm = algorithm
        self._header_name = header_name
    
    def generate(
        self,
        payload: bytes,
        secret: str,
        timestamp: Optional[int] = None,
    ) -> str:
        """Generate signature for payload."""
        ts = timestamp or int(time.time())
        message = f"{ts}.{payload.decode()}"
        
        if self._algorithm == SignatureAlgorithm.SHA256:
            signature = hmac.new(
                secret.encode(),
                message.encode(),
                hashlib.sha256,
            ).hexdigest()
        elif self._algorithm == SignatureAlgorithm.SHA512:
            signature = hmac.new(
                secret.encode(),
                message.encode(),
                hashlib.sha512,
            ).hexdigest()
        else:
            signature = hmac.new(
                secret.encode(),
                message.encode(),
                hashlib.sha1,
            ).hexdigest()
        
        return f"t={ts},v1={signature}"
    
    def verify(
        self,
        payload: bytes,
        signature: str,
        secret: str,
        tolerance_seconds: int = 300,
    ) -> bool:
        """Verify signature."""
        try:
            parts = dict(p.split("=", 1) for p in signature.split(","))
            timestamp = int(parts.get("t", "0"))
            received_sig = parts.get("v1", "")
            
            # Check timestamp
            now = int(time.time())
            if abs(now - timestamp) > tolerance_seconds:
                logger.warning("Webhook signature timestamp expired")
                return False
            
            # Generate expected signature
            expected = self.generate(payload, secret, timestamp)
            expected_sig = dict(p.split("=", 1) for p in expected.split(",")).get("v1", "")
            
            return hmac.compare_digest(received_sig, expected_sig)
            
        except Exception as e:
            logger.error(f"Signature verification failed: {e}")
            return False
    
    @property
    def header_name(self) -> str:
        """Get the header name."""
        return self._header_name


class WebhookDelivery(ABC):
    """Abstract webhook delivery interface."""
    
    @abstractmethod
    async def deliver(
        self,
        webhook: Webhook,
        event: str,
        payload: Dict[str, Any],
    ) -> DeliveryResult:
        """Deliver webhook."""
        pass


class HTTPWebhookDelivery(WebhookDelivery):
    """HTTP-based webhook delivery."""
    
    def __init__(
        self,
        signature_generator: Optional[SignatureGenerator] = None,
    ):
        self._signer = signature_generator or SignatureGenerator()
    
    async def deliver(
        self,
        webhook: Webhook,
        event: str,
        payload: Dict[str, Any],
    ) -> DeliveryResult:
        """Deliver webhook via HTTP."""
        start = time.time()
        last_error = None
        status_code = None
        
        for attempt in range(1, webhook.retry_count + 1):
            try:
                result = await self._send_request(webhook, event, payload)
                
                return DeliveryResult(
                    webhook_id=webhook.id,
                    event=event,
                    success=True,
                    attempts=attempt,
                    status_code=result.get("status_code"),
                    duration_ms=(time.time() - start) * 1000,
                )
                
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Webhook delivery attempt {attempt} failed: {e}")
                
                if attempt < webhook.retry_count:
                    # Exponential backoff
                    await asyncio.sleep(2 ** attempt)
        
        return DeliveryResult(
            webhook_id=webhook.id,
            event=event,
            success=False,
            attempts=webhook.retry_count,
            status_code=status_code,
            error=last_error,
            duration_ms=(time.time() - start) * 1000,
        )
    
    async def _send_request(
        self,
        webhook: Webhook,
        event: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Send HTTP request (mock implementation)."""
        # Build request
        body = json.dumps({
            "event": event,
            "data": payload,
            "timestamp": datetime.now().isoformat(),
            "webhook_id": webhook.id,
        })
        
        # Generate signature
        signature = self._signer.generate(body.encode(), webhook.secret)
        
        headers = {
            "Content-Type": "application/json",
            self._signer.header_name: signature,
            **webhook.headers,
        }
        
        # In production, use aiohttp or httpx
        # For now, simulate successful delivery
        logger.info(f"Delivered webhook to {webhook.url}: {event}")
        
        return {
            "status_code": 200,
            "body": "OK",
        }


class WebhookManager:
    """
    Manage webhooks registration, delivery, and tracking.
    """
    
    def __init__(
        self,
        delivery: Optional[WebhookDelivery] = None,
        signature_generator: Optional[SignatureGenerator] = None,
    ):
        self._webhooks: Dict[str, Webhook] = {}
        self._event_subscriptions: Dict[str, Set[str]] = {}
        self._delivery_history: List[DeliveryAttempt] = []
        self._delivery = delivery or HTTPWebhookDelivery(signature_generator)
        self._signer = signature_generator or SignatureGenerator()
        self._stats = WebhookStats()
    
    async def register(
        self,
        url: str,
        events: List[str],
        secret: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs: Any,
    ) -> Webhook:
        """Register a new webhook."""
        webhook = Webhook(
            url=url,
            events=events,
            secret=secret or str(uuid.uuid4()),
            headers=headers or {},
            **kwargs,
        )
        
        self._webhooks[webhook.id] = webhook
        
        # Track event subscriptions
        for event in events:
            if event not in self._event_subscriptions:
                self._event_subscriptions[event] = set()
            self._event_subscriptions[event].add(webhook.id)
        
        self._stats.total_webhooks += 1
        self._stats.active_webhooks += 1
        
        logger.info(f"Registered webhook {webhook.id} for events: {events}")
        return webhook
    
    async def unregister(self, webhook_id: str) -> bool:
        """Unregister a webhook."""
        if webhook_id not in self._webhooks:
            return False
        
        webhook = self._webhooks[webhook_id]
        
        # Remove from event subscriptions
        for event in webhook.events:
            if event in self._event_subscriptions:
                self._event_subscriptions[event].discard(webhook_id)
        
        del self._webhooks[webhook_id]
        self._stats.total_webhooks -= 1
        self._stats.active_webhooks -= 1
        
        return True
    
    async def update(
        self,
        webhook_id: str,
        **updates: Any,
    ) -> Optional[Webhook]:
        """Update a webhook."""
        if webhook_id not in self._webhooks:
            return None
        
        webhook = self._webhooks[webhook_id]
        
        for key, value in updates.items():
            if hasattr(webhook, key):
                setattr(webhook, key, value)
        
        webhook.updated_at = datetime.now()
        return webhook
    
    async def get(self, webhook_id: str) -> Optional[Webhook]:
        """Get a webhook by ID."""
        return self._webhooks.get(webhook_id)
    
    async def list_webhooks(
        self,
        status: Optional[WebhookStatus] = None,
    ) -> List[Webhook]:
        """List all webhooks."""
        webhooks = list(self._webhooks.values())
        
        if status:
            webhooks = [w for w in webhooks if w.status == status]
        
        return webhooks
    
    async def trigger(
        self,
        event: str,
        payload: Dict[str, Any],
    ) -> List[DeliveryResult]:
        """Trigger webhooks for an event."""
        results = []
        
        # Find matching webhooks
        webhook_ids = self._event_subscriptions.get(event, set())
        
        # Also check wildcard subscriptions
        for pattern, ids in self._event_subscriptions.items():
            if "*" in pattern:
                import fnmatch
                if fnmatch.fnmatch(event, pattern):
                    webhook_ids.update(ids)
        
        # Deliver to each webhook
        for webhook_id in webhook_ids:
            webhook = self._webhooks.get(webhook_id)
            
            if not webhook or webhook.status != WebhookStatus.ACTIVE:
                continue
            
            result = await self._delivery.deliver(webhook, event, payload)
            results.append(result)
            
            # Update stats
            self._stats.total_deliveries += 1
            if result.success:
                self._stats.successful_deliveries += 1
            else:
                self._stats.failed_deliveries += 1
            
            # Update average delivery time
            total = self._stats.total_deliveries
            self._stats.avg_delivery_time_ms = (
                (self._stats.avg_delivery_time_ms * (total - 1) + result.duration_ms)
                / total
            )
        
        return results
    
    async def trigger_async(
        self,
        event: str,
        payload: Dict[str, Any],
    ) -> None:
        """Trigger webhooks asynchronously (fire and forget)."""
        asyncio.create_task(self.trigger(event, payload))
    
    async def pause(self, webhook_id: str) -> bool:
        """Pause a webhook."""
        webhook = self._webhooks.get(webhook_id)
        if webhook:
            webhook.status = WebhookStatus.PAUSED
            self._stats.active_webhooks -= 1
            return True
        return False
    
    async def resume(self, webhook_id: str) -> bool:
        """Resume a paused webhook."""
        webhook = self._webhooks.get(webhook_id)
        if webhook and webhook.status == WebhookStatus.PAUSED:
            webhook.status = WebhookStatus.ACTIVE
            self._stats.active_webhooks += 1
            return True
        return False
    
    async def get_stats(self) -> WebhookStats:
        """Get webhook statistics."""
        return self._stats
    
    def verify_signature(
        self,
        payload: bytes,
        signature: str,
        secret: str,
    ) -> bool:
        """Verify incoming webhook signature."""
        return self._signer.verify(payload, signature, secret)


class WebhookEndpoint:
    """
    Webhook endpoint handler for receiving webhooks.
    """
    
    def __init__(
        self,
        secret: str,
        signer: Optional[SignatureGenerator] = None,
    ):
        self._secret = secret
        self._signer = signer or SignatureGenerator()
        self._handlers: Dict[str, Callable[[Dict[str, Any]], Awaitable[None]]] = {}
    
    def on(
        self,
        event: str,
        handler: Callable[[Dict[str, Any]], Awaitable[None]],
    ) -> None:
        """Register event handler."""
        self._handlers[event] = handler
    
    async def handle(
        self,
        payload: bytes,
        signature: str,
    ) -> Dict[str, Any]:
        """Handle incoming webhook."""
        # Verify signature
        if not self._signer.verify(payload, signature, self._secret):
            raise SignatureError("Invalid webhook signature")
        
        # Parse payload
        data = json.loads(payload)
        event = data.get("event", "")
        
        # Find handler
        handler = self._handlers.get(event)
        if not handler:
            # Try wildcard
            for pattern, h in self._handlers.items():
                if "*" in pattern:
                    import fnmatch
                    if fnmatch.fnmatch(event, pattern):
                        handler = h
                        break
        
        if handler:
            await handler(data.get("data", {}))
        
        return {"status": "ok", "event": event}


# Decorators
def verify_webhook(
    secret: str,
    signature_header: str = "X-Signature",
) -> Callable:
    """
    Decorator to verify incoming webhook signatures.
    
    Example:
        @verify_webhook(secret="shared_secret")
        async def handle_webhook(payload: dict):
            ...
    """
    signer = SignatureGenerator(header_name=signature_header)
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(
            payload: bytes,
            signature: str,
            *args: Any,
            **kwargs: Any,
        ) -> Any:
            if not signer.verify(payload, signature, secret):
                raise SignatureError("Invalid webhook signature")
            
            data = json.loads(payload)
            return await func(data, *args, **kwargs)
        
        return wrapper
    
    return decorator


def webhook_handler(event: str) -> Callable:
    """
    Decorator to mark a function as a webhook handler.
    
    Example:
        @webhook_handler("order.created")
        async def on_order_created(data: dict):
            ...
    """
    def decorator(func: Callable[[Dict[str, Any]], Awaitable[None]]) -> Callable:
        func._webhook_event = event
        return func
    
    return decorator


# Factory functions
def create_webhook_manager(
    signature_algorithm: SignatureAlgorithm = SignatureAlgorithm.SHA256,
    **kwargs: Any,
) -> WebhookManager:
    """Create a webhook manager."""
    signer = SignatureGenerator(algorithm=signature_algorithm)
    delivery = HTTPWebhookDelivery(signer)
    return WebhookManager(delivery, signer)


def create_webhook_endpoint(
    secret: str,
    algorithm: SignatureAlgorithm = SignatureAlgorithm.SHA256,
) -> WebhookEndpoint:
    """Create a webhook endpoint handler."""
    signer = SignatureGenerator(algorithm=algorithm)
    return WebhookEndpoint(secret, signer)


def create_signature_generator(
    algorithm: SignatureAlgorithm = SignatureAlgorithm.SHA256,
    header_name: str = "X-Signature",
) -> SignatureGenerator:
    """Create a signature generator."""
    return SignatureGenerator(algorithm, header_name)


__all__ = [
    # Exceptions
    "WebhookError",
    "SignatureError",
    "DeliveryError",
    # Enums
    "WebhookStatus",
    "DeliveryStatus",
    "SignatureAlgorithm",
    # Data classes
    "Webhook",
    "DeliveryAttempt",
    "DeliveryResult",
    "WebhookStats",
    # Core classes
    "SignatureGenerator",
    "WebhookDelivery",
    "HTTPWebhookDelivery",
    "WebhookManager",
    "WebhookEndpoint",
    # Decorators
    "verify_webhook",
    "webhook_handler",
    # Factory
    "create_webhook_manager",
    "create_webhook_endpoint",
    "create_signature_generator",
]
