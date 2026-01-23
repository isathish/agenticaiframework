"""
Enterprise SMS Service Module.

Provides SMS sending, provider abstraction, templating,
delivery tracking, and batch messaging.

Example:
    # Create SMS service
    sms = create_sms_service(
        provider=create_twilio_provider(
            account_sid="AC...",
            auth_token="...",
            from_number="+1234567890",
        )
    )
    
    # Send SMS
    result = await sms.send(
        to="+1987654321",
        message="Your verification code is 123456",
    )
    
    # Send with template
    await sms.send_template(
        to="+1987654321",
        template="verification",
        context={"code": "123456"},
    )
"""

from __future__ import annotations

import asyncio
import functools
import logging
import re
import uuid
from abc import ABC, abstractmethod
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
    TypeVar,
    Union,
)

T = TypeVar('T')


logger = logging.getLogger(__name__)


class SMSError(Exception):
    """SMS error."""
    pass


class DeliveryError(SMSError):
    """SMS delivery error."""
    pass


class InvalidNumberError(SMSError):
    """Invalid phone number error."""
    pass


class MessageStatus(str, Enum):
    """SMS delivery status."""
    PENDING = "pending"
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    UNDELIVERED = "undelivered"


class MessageType(str, Enum):
    """Message types."""
    SMS = "sms"
    MMS = "mms"
    OTP = "otp"
    TRANSACTIONAL = "transactional"
    PROMOTIONAL = "promotional"


@dataclass
class PhoneNumber:
    """Phone number with validation."""
    number: str
    country_code: str = ""
    
    def __post_init__(self):
        # Normalize number
        self.number = re.sub(r"[^\d+]", "", self.number)
        
        if not self.country_code and self.number.startswith("+"):
            # Extract country code
            self.country_code = self.number[1:3]
    
    def __str__(self) -> str:
        return self.number
    
    @property
    def e164(self) -> str:
        """E.164 formatted number."""
        if self.number.startswith("+"):
            return self.number
        if self.country_code:
            return f"+{self.country_code}{self.number}"
        return self.number
    
    @classmethod
    def parse(cls, value: str) -> "PhoneNumber":
        """Parse phone number string."""
        return cls(number=value)
    
    def is_valid(self) -> bool:
        """Basic phone number validation."""
        normalized = re.sub(r"[^\d]", "", self.number)
        return 10 <= len(normalized) <= 15


@dataclass
class SMSMessage:
    """SMS message."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    from_number: Optional[PhoneNumber] = None
    to: PhoneNumber = field(default_factory=lambda: PhoneNumber(""))
    body: str = ""
    message_type: MessageType = MessageType.SMS
    media_urls: List[str] = field(default_factory=list)  # For MMS
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    status: MessageStatus = MessageStatus.PENDING
    segments: int = 1
    
    def __post_init__(self):
        # Calculate segments
        if len(self.body) > 160:
            self.segments = (len(self.body) + 152) // 153
        
        # Set message type for MMS
        if self.media_urls:
            self.message_type = MessageType.MMS


@dataclass
class DeliveryResult:
    """SMS delivery result."""
    message_id: str
    success: bool
    status: MessageStatus
    provider_id: Optional[str] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    price: float = 0.0
    currency: str = "USD"
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class DeliveryReport:
    """SMS delivery status report (callback)."""
    message_id: str
    provider_id: str
    status: MessageStatus
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderConfig:
    """SMS provider configuration."""
    name: str
    max_message_length: int = 1600
    supports_mms: bool = False
    supports_unicode: bool = True
    rate_limit: int = 100  # messages per second


# SMS Providers
class SMSProvider(ABC):
    """Abstract SMS provider."""
    
    @abstractmethod
    async def send(self, message: SMSMessage) -> DeliveryResult:
        """Send SMS."""
        pass
    
    @abstractmethod
    async def check_status(self, message_id: str) -> MessageStatus:
        """Check delivery status."""
        pass
    
    @abstractmethod
    def get_config(self) -> ProviderConfig:
        """Get provider configuration."""
        pass


class TwilioProvider(SMSProvider):
    """Twilio SMS provider."""
    
    def __init__(
        self,
        account_sid: str,
        auth_token: str,
        from_number: str,
    ):
        self._account_sid = account_sid
        self._auth_token = auth_token
        self._from_number = PhoneNumber.parse(from_number)
    
    async def send(self, message: SMSMessage) -> DeliveryResult:
        """Send SMS via Twilio."""
        try:
            # In real implementation, would use twilio-python
            # client = Client(self._account_sid, self._auth_token)
            # result = client.messages.create(...)
            
            logger.info(
                f"Sending SMS {message.id} to {message.to} via Twilio"
            )
            
            return DeliveryResult(
                message_id=message.id,
                success=True,
                status=MessageStatus.QUEUED,
                provider_id=f"SM{uuid.uuid4().hex[:32]}",
            )
            
        except Exception as e:
            return DeliveryResult(
                message_id=message.id,
                success=False,
                status=MessageStatus.FAILED,
                error=str(e),
            )
    
    async def check_status(self, message_id: str) -> MessageStatus:
        """Check message status via Twilio."""
        # Would fetch from Twilio API
        return MessageStatus.DELIVERED
    
    def get_config(self) -> ProviderConfig:
        return ProviderConfig(
            name="twilio",
            max_message_length=1600,
            supports_mms=True,
            supports_unicode=True,
        )


class MockProvider(SMSProvider):
    """Mock SMS provider for testing."""
    
    def __init__(self, from_number: str = "+15551234567"):
        self._from_number = PhoneNumber.parse(from_number)
        self._sent: List[SMSMessage] = []
    
    async def send(self, message: SMSMessage) -> DeliveryResult:
        message.from_number = self._from_number
        self._sent.append(message)
        
        return DeliveryResult(
            message_id=message.id,
            success=True,
            status=MessageStatus.DELIVERED,
            provider_id=message.id,
        )
    
    async def check_status(self, message_id: str) -> MessageStatus:
        return MessageStatus.DELIVERED
    
    def get_config(self) -> ProviderConfig:
        return ProviderConfig(
            name="mock",
            max_message_length=1600,
            supports_mms=True,
        )
    
    def get_sent(self) -> List[SMSMessage]:
        """Get sent messages."""
        return self._sent.copy()
    
    def clear(self) -> None:
        """Clear sent messages."""
        self._sent.clear()


# Template engine
class SMSTemplateEngine(ABC):
    """SMS template engine."""
    
    @abstractmethod
    def render(
        self,
        template: str,
        context: Dict[str, Any],
    ) -> str:
        """Render template."""
        pass


class SimpleTemplateEngine(SMSTemplateEngine):
    """Simple template engine."""
    
    def __init__(
        self,
        templates: Optional[Dict[str, str]] = None,
    ):
        self._templates = templates or {}
    
    def add_template(self, name: str, content: str) -> None:
        """Add template."""
        self._templates[name] = content
    
    def render(
        self,
        template: str,
        context: Dict[str, Any],
    ) -> str:
        """Render template."""
        if template in self._templates:
            template = self._templates[template]
        
        result = template
        for key, value in context.items():
            result = result.replace(f"{{{{{key}}}}}", str(value))
        
        return result


# Message store
class MessageStore(ABC):
    """SMS message store."""
    
    @abstractmethod
    async def store(self, message: SMSMessage) -> None:
        """Store message."""
        pass
    
    @abstractmethod
    async def get(self, message_id: str) -> Optional[SMSMessage]:
        """Get message by ID."""
        pass
    
    @abstractmethod
    async def update_status(
        self,
        message_id: str,
        status: MessageStatus,
    ) -> None:
        """Update message status."""
        pass
    
    @abstractmethod
    async def get_by_phone(
        self,
        phone: str,
        limit: int = 100,
    ) -> List[SMSMessage]:
        """Get messages by phone number."""
        pass


class InMemoryMessageStore(MessageStore):
    """In-memory message store."""
    
    def __init__(self, max_messages: int = 10000):
        self._messages: Dict[str, SMSMessage] = {}
        self._max_messages = max_messages
    
    async def store(self, message: SMSMessage) -> None:
        # Trim if needed
        if len(self._messages) >= self._max_messages:
            oldest = sorted(
                self._messages.values(),
                key=lambda m: m.created_at,
            )[:100]
            for m in oldest:
                del self._messages[m.id]
        
        self._messages[message.id] = message
    
    async def get(self, message_id: str) -> Optional[SMSMessage]:
        return self._messages.get(message_id)
    
    async def update_status(
        self,
        message_id: str,
        status: MessageStatus,
    ) -> None:
        if message_id in self._messages:
            self._messages[message_id].status = status
    
    async def get_by_phone(
        self,
        phone: str,
        limit: int = 100,
    ) -> List[SMSMessage]:
        normalized = re.sub(r"[^\d]", "", phone)
        
        matches = [
            m for m in self._messages.values()
            if normalized in str(m.to)
        ]
        
        return sorted(
            matches,
            key=lambda m: m.created_at,
            reverse=True,
        )[:limit]


# Middleware
class SMSMiddleware(ABC):
    """SMS middleware."""
    
    @abstractmethod
    async def process(
        self,
        message: SMSMessage,
        next_handler: Callable,
    ) -> DeliveryResult:
        """Process message."""
        pass


class RateLimitMiddleware(SMSMiddleware):
    """Rate limiting middleware."""
    
    def __init__(
        self,
        max_per_second: int = 100,
    ):
        self._max_per_second = max_per_second
        self._timestamps: List[float] = []
        import time
        self._time = time
    
    async def process(
        self,
        message: SMSMessage,
        next_handler: Callable,
    ) -> DeliveryResult:
        now = self._time.time()
        
        # Clean old timestamps
        self._timestamps = [
            t for t in self._timestamps
            if now - t < 1.0
        ]
        
        if len(self._timestamps) >= self._max_per_second:
            return DeliveryResult(
                message_id=message.id,
                success=False,
                status=MessageStatus.FAILED,
                error="Rate limit exceeded",
            )
        
        self._timestamps.append(now)
        return await next_handler(message)


class RetryMiddleware(SMSMiddleware):
    """Retry failed sends."""
    
    def __init__(
        self,
        max_retries: int = 3,
        delay: float = 1.0,
    ):
        self._max_retries = max_retries
        self._delay = delay
    
    async def process(
        self,
        message: SMSMessage,
        next_handler: Callable,
    ) -> DeliveryResult:
        last_error = None
        
        for attempt in range(self._max_retries + 1):
            result = await next_handler(message)
            
            if result.success:
                return result
            
            last_error = result.error
            
            if attempt < self._max_retries:
                await asyncio.sleep(self._delay * (2 ** attempt))
        
        return DeliveryResult(
            message_id=message.id,
            success=False,
            status=MessageStatus.FAILED,
            error=last_error,
        )


class LoggingMiddleware(SMSMiddleware):
    """Logging middleware."""
    
    async def process(
        self,
        message: SMSMessage,
        next_handler: Callable,
    ) -> DeliveryResult:
        logger.info(
            f"Sending SMS {message.id} to {message.to} "
            f"({len(message.body)} chars, {message.segments} segments)"
        )
        
        result = await next_handler(message)
        
        if result.success:
            logger.info(f"SMS {message.id} sent successfully")
        else:
            logger.error(f"SMS {message.id} failed: {result.error}")
        
        return result


class SMSService:
    """
    SMS service for sending and managing messages.
    """
    
    def __init__(
        self,
        provider: SMSProvider,
        template_engine: Optional[SMSTemplateEngine] = None,
        store: Optional[MessageStore] = None,
        default_from: Optional[str] = None,
    ):
        self._provider = provider
        self._template_engine = template_engine or SimpleTemplateEngine()
        self._store = store or InMemoryMessageStore()
        self._default_from = PhoneNumber.parse(default_from) if default_from else None
        
        self._middlewares: List[SMSMiddleware] = []
    
    @property
    def template_engine(self) -> SMSTemplateEngine:
        return self._template_engine
    
    def add_middleware(self, middleware: SMSMiddleware) -> None:
        """Add middleware."""
        self._middlewares.append(middleware)
    
    def add_template(self, name: str, content: str) -> None:
        """Add SMS template."""
        if isinstance(self._template_engine, SimpleTemplateEngine):
            self._template_engine.add_template(name, content)
    
    async def send(
        self,
        to: Union[str, PhoneNumber],
        message: str,
        from_number: Optional[Union[str, PhoneNumber]] = None,
        message_type: MessageType = MessageType.SMS,
        media_urls: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DeliveryResult:
        """
        Send SMS.
        
        Args:
            to: Recipient phone number
            message: Message body
            from_number: Sender phone number
            message_type: Type of message
            media_urls: Media URLs for MMS
            tags: Message tags
            metadata: Custom metadata
            
        Returns:
            Delivery result
        """
        # Normalize phone numbers
        if isinstance(to, str):
            to = PhoneNumber.parse(to)
        
        if from_number:
            if isinstance(from_number, str):
                from_number = PhoneNumber.parse(from_number)
        else:
            from_number = self._default_from
        
        # Validate recipient
        if not to.is_valid():
            return DeliveryResult(
                message_id="",
                success=False,
                status=MessageStatus.FAILED,
                error=f"Invalid phone number: {to}",
            )
        
        # Create message
        sms = SMSMessage(
            from_number=from_number,
            to=to,
            body=message,
            message_type=message_type,
            media_urls=media_urls or [],
            tags=tags or [],
            metadata=metadata or {},
        )
        
        # Store message
        await self._store.store(sms)
        
        # Build middleware chain
        async def final_handler(m: SMSMessage) -> DeliveryResult:
            return await self._provider.send(m)
        
        handler = final_handler
        for middleware in reversed(self._middlewares):
            handler = self._wrap_middleware(middleware, handler)
        
        result = await handler(sms)
        
        # Update status
        await self._store.update_status(sms.id, result.status)
        
        return result
    
    async def send_template(
        self,
        to: Union[str, PhoneNumber],
        template: str,
        context: Dict[str, Any],
        **kwargs,
    ) -> DeliveryResult:
        """
        Send SMS using template.
        
        Args:
            to: Recipient phone number
            template: Template name or content
            context: Template context
            **kwargs: Additional send arguments
            
        Returns:
            Delivery result
        """
        message = self._template_engine.render(template, context)
        return await self.send(to=to, message=message, **kwargs)
    
    async def send_bulk(
        self,
        recipients: List[Dict[str, Any]],
        message: Optional[str] = None,
        template: Optional[str] = None,
        default_context: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> List[DeliveryResult]:
        """
        Send bulk SMS.
        
        Args:
            recipients: List of dicts with 'to' and optional 'context'
            message: Message body (if not using template)
            template: Template name (if using template)
            default_context: Default template context
            **kwargs: Additional send arguments
            
        Returns:
            List of delivery results
        """
        results = []
        
        for recipient in recipients:
            to = recipient["to"]
            context = {**(default_context or {}), **recipient.get("context", {})}
            
            if template:
                result = await self.send_template(
                    to=to,
                    template=template,
                    context=context,
                    **kwargs,
                )
            else:
                result = await self.send(
                    to=to,
                    message=message or "",
                    **kwargs,
                )
            
            results.append(result)
        
        return results
    
    async def send_otp(
        self,
        to: Union[str, PhoneNumber],
        code: str,
        template: str = "Your verification code is: {{code}}",
        **kwargs,
    ) -> DeliveryResult:
        """
        Send OTP code.
        
        Args:
            to: Recipient phone number
            code: OTP code
            template: Message template
            **kwargs: Additional send arguments
            
        Returns:
            Delivery result
        """
        return await self.send_template(
            to=to,
            template=template,
            context={"code": code},
            message_type=MessageType.OTP,
            **kwargs,
        )
    
    async def get_message(self, message_id: str) -> Optional[SMSMessage]:
        """Get message by ID."""
        return await self._store.get(message_id)
    
    async def check_status(self, message_id: str) -> MessageStatus:
        """Check message delivery status."""
        return await self._provider.check_status(message_id)
    
    async def handle_delivery_report(
        self,
        report: DeliveryReport,
    ) -> None:
        """Handle delivery status callback."""
        logger.info(
            f"Delivery report for {report.message_id}: {report.status}"
        )
        
        # Update message status
        await self._store.update_status(report.message_id, report.status)
    
    def _wrap_middleware(
        self,
        middleware: SMSMiddleware,
        next_handler: Callable,
    ) -> Callable:
        """Wrap handler with middleware."""
        async def wrapped(message: SMSMessage) -> DeliveryResult:
            return await middleware.process(message, next_handler)
        return wrapped


# Decorators
def sms_template(name: str) -> Callable:
    """Decorator to register SMS template."""
    def decorator(func: Callable) -> Callable:
        func._sms_template_name = name
        return func
    return decorator


def send_sms(
    to_field: str = "phone",
    message_field: str = "message",
    service: Optional[SMSService] = None,
) -> Callable:
    """Decorator to send SMS after function."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            
            if service and isinstance(result, dict):
                to = result.get(to_field)
                message = result.get(message_field)
                
                if to and message:
                    await service.send(to=to, message=message)
            
            return result
        return wrapper
    return decorator


# Factory functions
def create_sms_service(
    provider: SMSProvider,
    template_engine: Optional[SMSTemplateEngine] = None,
    store: Optional[MessageStore] = None,
    default_from: Optional[str] = None,
) -> SMSService:
    """Create SMS service."""
    return SMSService(
        provider=provider,
        template_engine=template_engine,
        store=store,
        default_from=default_from,
    )


def create_twilio_provider(
    account_sid: str,
    auth_token: str,
    from_number: str,
) -> TwilioProvider:
    """Create Twilio provider."""
    return TwilioProvider(
        account_sid=account_sid,
        auth_token=auth_token,
        from_number=from_number,
    )


def create_mock_provider(
    from_number: str = "+15551234567",
) -> MockProvider:
    """Create mock provider for testing."""
    return MockProvider(from_number)


def create_template_engine(
    templates: Optional[Dict[str, str]] = None,
) -> SimpleTemplateEngine:
    """Create template engine."""
    return SimpleTemplateEngine(templates)


def create_in_memory_store(
    max_messages: int = 10000,
) -> InMemoryMessageStore:
    """Create in-memory store."""
    return InMemoryMessageStore(max_messages)


def create_rate_limit_middleware(
    max_per_second: int = 100,
) -> RateLimitMiddleware:
    """Create rate limit middleware."""
    return RateLimitMiddleware(max_per_second)


def create_retry_middleware(
    max_retries: int = 3,
    delay: float = 1.0,
) -> RetryMiddleware:
    """Create retry middleware."""
    return RetryMiddleware(max_retries, delay)


def create_logging_middleware() -> LoggingMiddleware:
    """Create logging middleware."""
    return LoggingMiddleware()


__all__ = [
    # Exceptions
    "SMSError",
    "DeliveryError",
    "InvalidNumberError",
    # Enums
    "MessageStatus",
    "MessageType",
    # Data classes
    "PhoneNumber",
    "SMSMessage",
    "DeliveryResult",
    "DeliveryReport",
    "ProviderConfig",
    # Providers
    "SMSProvider",
    "TwilioProvider",
    "MockProvider",
    # Template engine
    "SMSTemplateEngine",
    "SimpleTemplateEngine",
    # Store
    "MessageStore",
    "InMemoryMessageStore",
    # Middleware
    "SMSMiddleware",
    "RateLimitMiddleware",
    "RetryMiddleware",
    "LoggingMiddleware",
    # Service
    "SMSService",
    # Decorators
    "sms_template",
    "send_sms",
    # Factory functions
    "create_sms_service",
    "create_twilio_provider",
    "create_mock_provider",
    "create_template_engine",
    "create_in_memory_store",
    "create_rate_limit_middleware",
    "create_retry_middleware",
    "create_logging_middleware",
]
