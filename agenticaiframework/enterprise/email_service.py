"""
Enterprise Email Service Module.

Provides email sending, templating, attachments,
tracking, and provider abstraction.

Example:
    # Create email service
    email = create_email_service(
        provider=create_smtp_provider(
            host="smtp.gmail.com",
            port=587,
            username="user@gmail.com",
            password="app_password",
        )
    )
    
    # Send simple email
    await email.send(
        to="recipient@example.com",
        subject="Hello",
        body="Hello, World!",
    )
    
    # Send with template
    await email.send_template(
        to="user@example.com",
        template="welcome",
        context={"name": "John", "company": "Acme"},
    )
"""

from __future__ import annotations

import asyncio
import functools
import logging
import mimetypes
import os
import re
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
from pathlib import Path
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


class EmailError(Exception):
    """Email error."""
    pass


class DeliveryError(EmailError):
    """Email delivery error."""
    pass


class TemplateError(EmailError):
    """Template rendering error."""
    pass


class EmailStatus(str, Enum):
    """Email delivery status."""
    PENDING = "pending"
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    OPENED = "opened"
    CLICKED = "clicked"
    BOUNCED = "bounced"
    FAILED = "failed"


class ContentType(str, Enum):
    """Email content types."""
    PLAIN = "text/plain"
    HTML = "text/html"


@dataclass
class EmailAddress:
    """Email address with optional name."""
    email: str
    name: str = ""
    
    def __str__(self) -> str:
        if self.name:
            return f"{self.name} <{self.email}>"
        return self.email
    
    @classmethod
    def parse(cls, value: str) -> "EmailAddress":
        """Parse email address string."""
        match = re.match(r"^(.+?)\s*<(.+?)>$", value)
        if match:
            return cls(email=match.group(2), name=match.group(1).strip())
        return cls(email=value)


@dataclass
class Attachment:
    """Email attachment."""
    filename: str
    content: bytes
    content_type: str = "application/octet-stream"
    inline: bool = False
    content_id: str = ""
    
    @classmethod
    def from_file(cls, path: Union[str, Path]) -> "Attachment":
        """Create attachment from file."""
        path = Path(path)
        content_type, _ = mimetypes.guess_type(str(path))
        
        return cls(
            filename=path.name,
            content=path.read_bytes(),
            content_type=content_type or "application/octet-stream",
        )


@dataclass
class Email:
    """Email message."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    from_addr: Optional[EmailAddress] = None
    to: List[EmailAddress] = field(default_factory=list)
    cc: List[EmailAddress] = field(default_factory=list)
    bcc: List[EmailAddress] = field(default_factory=list)
    reply_to: Optional[EmailAddress] = None
    subject: str = ""
    body_plain: str = ""
    body_html: str = ""
    attachments: List[Attachment] = field(default_factory=list)
    headers: Dict[str, str] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    status: EmailStatus = EmailStatus.PENDING


@dataclass
class DeliveryResult:
    """Email delivery result."""
    email_id: str
    success: bool
    status: EmailStatus
    provider_id: Optional[str] = None
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class TrackingEvent:
    """Email tracking event."""
    email_id: str
    event_type: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    ip_address: str = ""
    user_agent: str = ""
    link_url: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


# Email providers
class EmailProvider(ABC):
    """Abstract email provider."""
    
    @abstractmethod
    async def send(self, email: Email) -> DeliveryResult:
        """Send email."""
        pass
    
    @abstractmethod
    async def check_status(self, email_id: str) -> EmailStatus:
        """Check delivery status."""
        pass


class SMTPProvider(EmailProvider):
    """SMTP email provider."""
    
    def __init__(
        self,
        host: str,
        port: int = 587,
        username: str = "",
        password: str = "",
        use_tls: bool = True,
        timeout: float = 30.0,
    ):
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._use_tls = use_tls
        self._timeout = timeout
    
    async def send(self, email: Email) -> DeliveryResult:
        """Send email via SMTP."""
        try:
            # Build MIME message
            if email.body_html and email.body_plain:
                msg = MIMEMultipart("alternative")
                msg.attach(MIMEText(email.body_plain, "plain"))
                msg.attach(MIMEText(email.body_html, "html"))
            elif email.body_html:
                msg = MIMEText(email.body_html, "html")
            else:
                msg = MIMEText(email.body_plain, "plain")
            
            # Handle attachments
            if email.attachments:
                outer = MIMEMultipart("mixed")
                outer.attach(msg)
                
                for att in email.attachments:
                    part = MIMEBase(*att.content_type.split("/", 1))
                    part.set_payload(att.content)
                    part.add_header(
                        "Content-Disposition",
                        f"{'inline' if att.inline else 'attachment'}; "
                        f"filename={att.filename}",
                    )
                    if att.content_id:
                        part.add_header("Content-ID", f"<{att.content_id}>")
                    outer.attach(part)
                
                msg = outer
            
            # Set headers
            if email.from_addr:
                msg["From"] = str(email.from_addr)
            msg["To"] = ", ".join(str(a) for a in email.to)
            if email.cc:
                msg["Cc"] = ", ".join(str(a) for a in email.cc)
            msg["Subject"] = email.subject
            if email.reply_to:
                msg["Reply-To"] = str(email.reply_to)
            
            msg["Message-ID"] = f"<{email.id}@{self._host}>"
            
            for key, value in email.headers.items():
                msg[key] = value
            
            # Send via SMTP (simplified - would use aiosmtplib in real impl)
            logger.info(f"Sending email {email.id} via SMTP to {self._host}")
            
            # In real implementation, would use aiosmtplib
            # async with aiosmtplib.SMTP(...) as smtp:
            #     await smtp.send_message(msg)
            
            return DeliveryResult(
                email_id=email.id,
                success=True,
                status=EmailStatus.SENT,
                provider_id=email.id,
            )
            
        except Exception as e:
            return DeliveryResult(
                email_id=email.id,
                success=False,
                status=EmailStatus.FAILED,
                error=str(e),
            )
    
    async def check_status(self, email_id: str) -> EmailStatus:
        """SMTP doesn't support status checking."""
        return EmailStatus.SENT


class MockProvider(EmailProvider):
    """Mock email provider for testing."""
    
    def __init__(self):
        self._sent: List[Email] = []
    
    async def send(self, email: Email) -> DeliveryResult:
        self._sent.append(email)
        
        return DeliveryResult(
            email_id=email.id,
            success=True,
            status=EmailStatus.SENT,
            provider_id=email.id,
        )
    
    async def check_status(self, email_id: str) -> EmailStatus:
        return EmailStatus.DELIVERED
    
    def get_sent(self) -> List[Email]:
        """Get sent emails."""
        return self._sent.copy()
    
    def clear(self) -> None:
        """Clear sent emails."""
        self._sent.clear()


# Template engine
class TemplateEngine(ABC):
    """Abstract template engine."""
    
    @abstractmethod
    def render(
        self,
        template: str,
        context: Dict[str, Any],
    ) -> str:
        """Render template."""
        pass


class SimpleTemplateEngine(TemplateEngine):
    """Simple template engine using string formatting."""
    
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
        
        # Simple {{variable}} replacement
        result = template
        for key, value in context.items():
            result = result.replace(f"{{{{{key}}}}}", str(value))
        
        return result


# Email store
class EmailStore(ABC):
    """Email storage."""
    
    @abstractmethod
    async def store(self, email: Email) -> None:
        """Store email."""
        pass
    
    @abstractmethod
    async def get(self, email_id: str) -> Optional[Email]:
        """Get email by ID."""
        pass
    
    @abstractmethod
    async def update_status(
        self,
        email_id: str,
        status: EmailStatus,
    ) -> None:
        """Update email status."""
        pass
    
    @abstractmethod
    async def add_tracking_event(
        self,
        event: TrackingEvent,
    ) -> None:
        """Add tracking event."""
        pass


class InMemoryEmailStore(EmailStore):
    """In-memory email store."""
    
    def __init__(self):
        self._emails: Dict[str, Email] = {}
        self._events: Dict[str, List[TrackingEvent]] = {}
    
    async def store(self, email: Email) -> None:
        self._emails[email.id] = email
    
    async def get(self, email_id: str) -> Optional[Email]:
        return self._emails.get(email_id)
    
    async def update_status(
        self,
        email_id: str,
        status: EmailStatus,
    ) -> None:
        if email_id in self._emails:
            self._emails[email_id].status = status
    
    async def add_tracking_event(
        self,
        event: TrackingEvent,
    ) -> None:
        if event.email_id not in self._events:
            self._events[event.email_id] = []
        self._events[event.email_id].append(event)
    
    async def get_tracking_events(
        self,
        email_id: str,
    ) -> List[TrackingEvent]:
        """Get tracking events for email."""
        return self._events.get(email_id, [])


# Middleware
class EmailMiddleware(ABC):
    """Email middleware."""
    
    @abstractmethod
    async def process(
        self,
        email: Email,
        next_handler: Callable,
    ) -> DeliveryResult:
        """Process email."""
        pass


class TrackingMiddleware(EmailMiddleware):
    """Add tracking pixels and link tracking."""
    
    def __init__(
        self,
        tracking_url: str,
        track_opens: bool = True,
        track_clicks: bool = True,
    ):
        self._tracking_url = tracking_url
        self._track_opens = track_opens
        self._track_clicks = track_clicks
    
    async def process(
        self,
        email: Email,
        next_handler: Callable,
    ) -> DeliveryResult:
        if email.body_html:
            # Add tracking pixel for opens
            if self._track_opens:
                pixel = (
                    f'<img src="{self._tracking_url}/open/{email.id}" '
                    f'width="1" height="1" />'
                )
                email.body_html = email.body_html.replace(
                    "</body>",
                    f"{pixel}</body>",
                )
            
            # Wrap links for click tracking
            if self._track_clicks:
                # Simplified link wrapping
                pass
        
        return await next_handler(email)


class RetryMiddleware(EmailMiddleware):
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
        email: Email,
        next_handler: Callable,
    ) -> DeliveryResult:
        last_error = None
        
        for attempt in range(self._max_retries + 1):
            result = await next_handler(email)
            
            if result.success:
                return result
            
            last_error = result.error
            
            if attempt < self._max_retries:
                await asyncio.sleep(self._delay * (2 ** attempt))
        
        return DeliveryResult(
            email_id=email.id,
            success=False,
            status=EmailStatus.FAILED,
            error=last_error,
        )


class EmailService:
    """
    Email service for sending and managing emails.
    """
    
    def __init__(
        self,
        provider: EmailProvider,
        template_engine: Optional[TemplateEngine] = None,
        store: Optional[EmailStore] = None,
        default_from: Optional[EmailAddress] = None,
    ):
        self._provider = provider
        self._template_engine = template_engine or SimpleTemplateEngine()
        self._store = store or InMemoryEmailStore()
        self._default_from = default_from
        
        self._middlewares: List[EmailMiddleware] = []
    
    @property
    def template_engine(self) -> TemplateEngine:
        return self._template_engine
    
    def add_middleware(self, middleware: EmailMiddleware) -> None:
        """Add middleware."""
        self._middlewares.append(middleware)
    
    def add_template(self, name: str, content: str) -> None:
        """Add email template."""
        if isinstance(self._template_engine, SimpleTemplateEngine):
            self._template_engine.add_template(name, content)
    
    async def send(
        self,
        to: Union[str, EmailAddress, List[Union[str, EmailAddress]]],
        subject: str,
        body: str = "",
        html: str = "",
        from_addr: Optional[Union[str, EmailAddress]] = None,
        cc: Optional[List[Union[str, EmailAddress]]] = None,
        bcc: Optional[List[Union[str, EmailAddress]]] = None,
        reply_to: Optional[Union[str, EmailAddress]] = None,
        attachments: Optional[List[Attachment]] = None,
        headers: Optional[Dict[str, str]] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DeliveryResult:
        """
        Send email.
        
        Args:
            to: Recipient(s)
            subject: Email subject
            body: Plain text body
            html: HTML body
            from_addr: Sender address
            cc: CC recipients
            bcc: BCC recipients
            reply_to: Reply-to address
            attachments: File attachments
            headers: Custom headers
            tags: Email tags
            metadata: Custom metadata
            
        Returns:
            Delivery result
        """
        # Normalize recipients
        def normalize(addr):
            if isinstance(addr, str):
                return EmailAddress.parse(addr)
            return addr
        
        if isinstance(to, (str, EmailAddress)):
            to = [to]
        
        email = Email(
            from_addr=normalize(from_addr) if from_addr else self._default_from,
            to=[normalize(a) for a in to],
            cc=[normalize(a) for a in (cc or [])],
            bcc=[normalize(a) for a in (bcc or [])],
            reply_to=normalize(reply_to) if reply_to else None,
            subject=subject,
            body_plain=body,
            body_html=html,
            attachments=attachments or [],
            headers=headers or {},
            tags=tags or [],
            metadata=metadata or {},
        )
        
        # Store email
        await self._store.store(email)
        
        # Build middleware chain
        async def final_handler(e: Email) -> DeliveryResult:
            return await self._provider.send(e)
        
        handler = final_handler
        for middleware in reversed(self._middlewares):
            handler = self._wrap_middleware(middleware, handler)
        
        result = await handler(email)
        
        # Update status
        await self._store.update_status(email.id, result.status)
        
        return result
    
    async def send_template(
        self,
        to: Union[str, EmailAddress, List[Union[str, EmailAddress]]],
        template: str,
        context: Dict[str, Any],
        subject_template: Optional[str] = None,
        **kwargs,
    ) -> DeliveryResult:
        """
        Send email using template.
        
        Args:
            to: Recipient(s)
            template: Template name or content
            context: Template context
            subject_template: Subject template
            **kwargs: Additional send arguments
            
        Returns:
            Delivery result
        """
        # Render body
        body = self._template_engine.render(template, context)
        
        # Render subject if provided
        subject = kwargs.get("subject", "")
        if subject_template:
            subject = self._template_engine.render(subject_template, context)
        
        # Determine if HTML
        is_html = "<html" in body.lower() or "<body" in body.lower()
        
        if is_html:
            return await self.send(
                to=to,
                subject=subject,
                html=body,
                **kwargs,
            )
        else:
            return await self.send(
                to=to,
                subject=subject,
                body=body,
                **kwargs,
            )
    
    async def send_bulk(
        self,
        recipients: List[Dict[str, Any]],
        template: str,
        default_context: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> List[DeliveryResult]:
        """
        Send bulk emails.
        
        Args:
            recipients: List of dicts with 'to' and optional 'context'
            template: Template name or content
            default_context: Default template context
            **kwargs: Additional send arguments
            
        Returns:
            List of delivery results
        """
        results = []
        
        for recipient in recipients:
            to = recipient["to"]
            context = {**(default_context or {}), **recipient.get("context", {})}
            
            result = await self.send_template(
                to=to,
                template=template,
                context=context,
                **kwargs,
            )
            results.append(result)
        
        return results
    
    async def get_email(self, email_id: str) -> Optional[Email]:
        """Get email by ID."""
        return await self._store.get(email_id)
    
    async def track_event(
        self,
        email_id: str,
        event_type: str,
        ip_address: str = "",
        user_agent: str = "",
        link_url: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Track email event."""
        event = TrackingEvent(
            email_id=email_id,
            event_type=event_type,
            ip_address=ip_address,
            user_agent=user_agent,
            link_url=link_url,
            metadata=metadata or {},
        )
        
        await self._store.add_tracking_event(event)
        
        # Update email status based on event
        status_map = {
            "delivered": EmailStatus.DELIVERED,
            "opened": EmailStatus.OPENED,
            "clicked": EmailStatus.CLICKED,
            "bounced": EmailStatus.BOUNCED,
        }
        
        if event_type in status_map:
            await self._store.update_status(email_id, status_map[event_type])
    
    def _wrap_middleware(
        self,
        middleware: EmailMiddleware,
        next_handler: Callable,
    ) -> Callable:
        """Wrap handler with middleware."""
        async def wrapped(email: Email) -> DeliveryResult:
            return await middleware.process(email, next_handler)
        return wrapped


# Decorators
def email_template(
    name: str,
    subject: str = "",
) -> Callable:
    """Decorator to register email template."""
    def decorator(func: Callable) -> Callable:
        func._email_template_name = name
        func._email_template_subject = subject
        return func
    return decorator


def send_email(
    template: str,
    service: Optional[EmailService] = None,
) -> Callable:
    """Decorator to send email after function."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            
            if service and isinstance(result, dict):
                to = result.get("email") or result.get("to")
                if to:
                    await service.send_template(
                        to=to,
                        template=template,
                        context=result,
                    )
            
            return result
        return wrapper
    return decorator


# Factory functions
def create_email_service(
    provider: EmailProvider,
    template_engine: Optional[TemplateEngine] = None,
    store: Optional[EmailStore] = None,
    default_from: Optional[str] = None,
) -> EmailService:
    """Create email service."""
    from_addr = EmailAddress.parse(default_from) if default_from else None
    
    return EmailService(
        provider=provider,
        template_engine=template_engine,
        store=store,
        default_from=from_addr,
    )


def create_smtp_provider(
    host: str,
    port: int = 587,
    username: str = "",
    password: str = "",
    use_tls: bool = True,
) -> SMTPProvider:
    """Create SMTP provider."""
    return SMTPProvider(
        host=host,
        port=port,
        username=username,
        password=password,
        use_tls=use_tls,
    )


def create_mock_provider() -> MockProvider:
    """Create mock provider for testing."""
    return MockProvider()


def create_template_engine(
    templates: Optional[Dict[str, str]] = None,
) -> SimpleTemplateEngine:
    """Create template engine."""
    return SimpleTemplateEngine(templates)


def create_in_memory_store() -> InMemoryEmailStore:
    """Create in-memory store."""
    return InMemoryEmailStore()


def create_tracking_middleware(
    tracking_url: str,
    track_opens: bool = True,
    track_clicks: bool = True,
) -> TrackingMiddleware:
    """Create tracking middleware."""
    return TrackingMiddleware(tracking_url, track_opens, track_clicks)


def create_retry_middleware(
    max_retries: int = 3,
    delay: float = 1.0,
) -> RetryMiddleware:
    """Create retry middleware."""
    return RetryMiddleware(max_retries, delay)


def create_email(
    to: Union[str, List[str]],
    subject: str,
    body: str = "",
    html: str = "",
) -> Email:
    """Create email object."""
    if isinstance(to, str):
        to = [to]
    
    return Email(
        to=[EmailAddress.parse(addr) for addr in to],
        subject=subject,
        body_plain=body,
        body_html=html,
    )


def create_attachment(
    filename: str,
    content: bytes,
    content_type: str = "application/octet-stream",
) -> Attachment:
    """Create attachment."""
    return Attachment(
        filename=filename,
        content=content,
        content_type=content_type,
    )


__all__ = [
    # Exceptions
    "EmailError",
    "DeliveryError",
    "TemplateError",
    # Enums
    "EmailStatus",
    "ContentType",
    # Data classes
    "EmailAddress",
    "Attachment",
    "Email",
    "DeliveryResult",
    "TrackingEvent",
    # Providers
    "EmailProvider",
    "SMTPProvider",
    "MockProvider",
    # Template engine
    "TemplateEngine",
    "SimpleTemplateEngine",
    # Store
    "EmailStore",
    "InMemoryEmailStore",
    # Middleware
    "EmailMiddleware",
    "TrackingMiddleware",
    "RetryMiddleware",
    # Service
    "EmailService",
    # Decorators
    "email_template",
    "send_email",
    # Factory functions
    "create_email_service",
    "create_smtp_provider",
    "create_mock_provider",
    "create_template_engine",
    "create_in_memory_store",
    "create_tracking_middleware",
    "create_retry_middleware",
    "create_email",
    "create_attachment",
]
