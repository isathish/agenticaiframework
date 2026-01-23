"""
Enterprise Notification Hub Module.

Multi-channel notifications (email, SMS, push, Slack, webhooks)
with templating, scheduling, and delivery tracking.

Example:
    # Create notification hub
    hub = create_notification_hub()
    
    # Register channels
    hub.register_channel("email", EmailChannel(smtp_config))
    hub.register_channel("sms", SMSChannel(twilio_config))
    
    # Send notification
    await hub.send(
        user_id="user123",
        channels=["email", "push"],
        template="welcome",
        data={"name": "John"},
    )
    
    # Schedule notification
    await hub.schedule(
        user_id="user123",
        template="reminder",
        send_at=datetime.now() + timedelta(hours=24),
    )
"""

from __future__ import annotations

import asyncio
import functools
import json
import logging
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    TypeVar,
    Union,
)

T = TypeVar('T')


logger = logging.getLogger(__name__)


class NotificationError(Exception):
    """Notification error."""
    pass


class ChannelError(NotificationError):
    """Channel error."""
    pass


class DeliveryError(NotificationError):
    """Delivery error."""
    pass


class TemplateError(NotificationError):
    """Template error."""
    pass


class NotificationStatus(str, Enum):
    """Notification status."""
    PENDING = "pending"
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    BOUNCED = "bounced"
    OPENED = "opened"
    CLICKED = "clicked"


class Priority(str, Enum):
    """Notification priority."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class ChannelType(str, Enum):
    """Channel types."""
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    SLACK = "slack"
    WEBHOOK = "webhook"
    IN_APP = "in_app"
    TEAMS = "teams"
    DISCORD = "discord"


@dataclass
class NotificationTemplate:
    """Notification template."""
    id: str
    name: str = ""
    subject: Optional[str] = None
    body: str = ""
    html_body: Optional[str] = None
    channel_templates: Dict[ChannelType, str] = field(default_factory=dict)
    variables: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Recipient:
    """Notification recipient."""
    id: str
    email: Optional[str] = None
    phone: Optional[str] = None
    device_tokens: List[str] = field(default_factory=list)
    slack_user_id: Optional[str] = None
    webhook_url: Optional[str] = None
    preferences: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NotificationPayload:
    """Notification payload."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    template_id: Optional[str] = None
    recipient: Optional[Recipient] = None
    channels: List[ChannelType] = field(default_factory=list)
    subject: str = ""
    body: str = ""
    html_body: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    priority: Priority = Priority.NORMAL
    scheduled_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DeliveryResult:
    """Delivery result."""
    notification_id: str
    channel: ChannelType
    status: NotificationStatus = NotificationStatus.PENDING
    provider_id: Optional[str] = None
    error: Optional[str] = None
    delivered_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NotificationRecord:
    """Notification record."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    recipient_id: str = ""
    template_id: Optional[str] = None
    payload: Optional[NotificationPayload] = None
    results: List[DeliveryResult] = field(default_factory=list)
    status: NotificationStatus = NotificationStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None


# Channel interface
class NotificationChannel(ABC):
    """Abstract notification channel."""
    
    @property
    @abstractmethod
    def channel_type(self) -> ChannelType:
        """Get channel type."""
        pass
    
    @abstractmethod
    async def send(
        self,
        recipient: Recipient,
        payload: NotificationPayload,
    ) -> DeliveryResult:
        """Send notification."""
        pass
    
    async def validate_recipient(self, recipient: Recipient) -> bool:
        """Validate recipient can receive notifications."""
        return True


class EmailChannel(NotificationChannel):
    """Email notification channel."""
    
    def __init__(
        self,
        smtp_host: str = "localhost",
        smtp_port: int = 587,
        username: Optional[str] = None,
        password: Optional[str] = None,
        from_address: str = "noreply@example.com",
        from_name: str = "Notification Service",
    ):
        self._smtp_host = smtp_host
        self._smtp_port = smtp_port
        self._username = username
        self._password = password
        self._from_address = from_address
        self._from_name = from_name
    
    @property
    def channel_type(self) -> ChannelType:
        return ChannelType.EMAIL
    
    async def send(
        self,
        recipient: Recipient,
        payload: NotificationPayload,
    ) -> DeliveryResult:
        """Send email notification."""
        if not recipient.email:
            return DeliveryResult(
                notification_id=payload.id,
                channel=ChannelType.EMAIL,
                status=NotificationStatus.FAILED,
                error="No email address",
            )
        
        # Mock sending - in production, use aiosmtplib
        logger.info(f"Sending email to {recipient.email}: {payload.subject}")
        
        return DeliveryResult(
            notification_id=payload.id,
            channel=ChannelType.EMAIL,
            status=NotificationStatus.SENT,
            provider_id=str(uuid.uuid4()),
            delivered_at=datetime.utcnow(),
        )
    
    async def validate_recipient(self, recipient: Recipient) -> bool:
        return bool(recipient.email)


class SMSChannel(NotificationChannel):
    """SMS notification channel."""
    
    def __init__(
        self,
        provider: str = "mock",
        api_key: Optional[str] = None,
        from_number: Optional[str] = None,
    ):
        self._provider = provider
        self._api_key = api_key
        self._from_number = from_number
    
    @property
    def channel_type(self) -> ChannelType:
        return ChannelType.SMS
    
    async def send(
        self,
        recipient: Recipient,
        payload: NotificationPayload,
    ) -> DeliveryResult:
        """Send SMS notification."""
        if not recipient.phone:
            return DeliveryResult(
                notification_id=payload.id,
                channel=ChannelType.SMS,
                status=NotificationStatus.FAILED,
                error="No phone number",
            )
        
        # Mock sending
        logger.info(f"Sending SMS to {recipient.phone}: {payload.body[:50]}")
        
        return DeliveryResult(
            notification_id=payload.id,
            channel=ChannelType.SMS,
            status=NotificationStatus.SENT,
            provider_id=str(uuid.uuid4()),
            delivered_at=datetime.utcnow(),
        )
    
    async def validate_recipient(self, recipient: Recipient) -> bool:
        return bool(recipient.phone)


class PushChannel(NotificationChannel):
    """Push notification channel."""
    
    def __init__(
        self,
        provider: str = "mock",
        api_key: Optional[str] = None,
    ):
        self._provider = provider
        self._api_key = api_key
    
    @property
    def channel_type(self) -> ChannelType:
        return ChannelType.PUSH
    
    async def send(
        self,
        recipient: Recipient,
        payload: NotificationPayload,
    ) -> DeliveryResult:
        """Send push notification."""
        if not recipient.device_tokens:
            return DeliveryResult(
                notification_id=payload.id,
                channel=ChannelType.PUSH,
                status=NotificationStatus.FAILED,
                error="No device tokens",
            )
        
        # Mock sending
        logger.info(f"Sending push to {len(recipient.device_tokens)} devices")
        
        return DeliveryResult(
            notification_id=payload.id,
            channel=ChannelType.PUSH,
            status=NotificationStatus.SENT,
            provider_id=str(uuid.uuid4()),
            delivered_at=datetime.utcnow(),
            metadata={"devices": len(recipient.device_tokens)},
        )
    
    async def validate_recipient(self, recipient: Recipient) -> bool:
        return bool(recipient.device_tokens)


class SlackChannel(NotificationChannel):
    """Slack notification channel."""
    
    def __init__(
        self,
        bot_token: Optional[str] = None,
        webhook_url: Optional[str] = None,
    ):
        self._bot_token = bot_token
        self._webhook_url = webhook_url
    
    @property
    def channel_type(self) -> ChannelType:
        return ChannelType.SLACK
    
    async def send(
        self,
        recipient: Recipient,
        payload: NotificationPayload,
    ) -> DeliveryResult:
        """Send Slack notification."""
        # Mock sending
        logger.info(f"Sending Slack message: {payload.body[:50]}")
        
        return DeliveryResult(
            notification_id=payload.id,
            channel=ChannelType.SLACK,
            status=NotificationStatus.SENT,
            provider_id=str(uuid.uuid4()),
            delivered_at=datetime.utcnow(),
        )


class WebhookChannel(NotificationChannel):
    """Webhook notification channel."""
    
    def __init__(
        self,
        default_url: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ):
        self._default_url = default_url
        self._headers = headers or {}
    
    @property
    def channel_type(self) -> ChannelType:
        return ChannelType.WEBHOOK
    
    async def send(
        self,
        recipient: Recipient,
        payload: NotificationPayload,
    ) -> DeliveryResult:
        """Send webhook notification."""
        url = recipient.webhook_url or self._default_url
        
        if not url:
            return DeliveryResult(
                notification_id=payload.id,
                channel=ChannelType.WEBHOOK,
                status=NotificationStatus.FAILED,
                error="No webhook URL",
            )
        
        # Mock sending
        logger.info(f"Sending webhook to {url}")
        
        return DeliveryResult(
            notification_id=payload.id,
            channel=ChannelType.WEBHOOK,
            status=NotificationStatus.SENT,
            provider_id=str(uuid.uuid4()),
            delivered_at=datetime.utcnow(),
        )


class InAppChannel(NotificationChannel):
    """In-app notification channel."""
    
    def __init__(self):
        self._notifications: Dict[str, List[Dict]] = defaultdict(list)
    
    @property
    def channel_type(self) -> ChannelType:
        return ChannelType.IN_APP
    
    async def send(
        self,
        recipient: Recipient,
        payload: NotificationPayload,
    ) -> DeliveryResult:
        """Store in-app notification."""
        notification = {
            "id": payload.id,
            "subject": payload.subject,
            "body": payload.body,
            "data": payload.data,
            "created_at": datetime.utcnow().isoformat(),
            "read": False,
        }
        
        self._notifications[recipient.id].append(notification)
        
        return DeliveryResult(
            notification_id=payload.id,
            channel=ChannelType.IN_APP,
            status=NotificationStatus.DELIVERED,
            delivered_at=datetime.utcnow(),
        )
    
    async def get_notifications(
        self,
        user_id: str,
        unread_only: bool = False,
    ) -> List[Dict]:
        """Get user's in-app notifications."""
        notifications = self._notifications.get(user_id, [])
        
        if unread_only:
            return [n for n in notifications if not n["read"]]
        
        return notifications
    
    async def mark_read(self, user_id: str, notification_id: str) -> bool:
        """Mark notification as read."""
        for notification in self._notifications.get(user_id, []):
            if notification["id"] == notification_id:
                notification["read"] = True
                return True
        return False


# Template engine
class TemplateEngine:
    """Simple template engine."""
    
    def render(
        self,
        template: str,
        data: Dict[str, Any],
    ) -> str:
        """Render template with data."""
        result = template
        
        for key, value in data.items():
            result = result.replace(f"{{{{{key}}}}}", str(value))
            result = result.replace(f"{{{{ {key} }}}}", str(value))
        
        return result


class NotificationHub:
    """
    Notification hub service.
    """
    
    def __init__(
        self,
        template_engine: Optional[TemplateEngine] = None,
    ):
        self._channels: Dict[ChannelType, NotificationChannel] = {}
        self._templates: Dict[str, NotificationTemplate] = {}
        self._template_engine = template_engine or TemplateEngine()
        self._records: Dict[str, NotificationRecord] = {}
        self._scheduled: List[NotificationPayload] = []
        self._user_preferences: Dict[str, Dict[str, Any]] = {}
        self._hooks: Dict[str, List[Callable]] = defaultdict(list)
    
    def register_channel(
        self,
        channel: NotificationChannel,
    ) -> None:
        """Register notification channel."""
        self._channels[channel.channel_type] = channel
    
    def get_channel(
        self,
        channel_type: ChannelType,
    ) -> Optional[NotificationChannel]:
        """Get channel by type."""
        return self._channels.get(channel_type)
    
    def register_template(
        self,
        template: NotificationTemplate,
    ) -> None:
        """Register notification template."""
        self._templates[template.id] = template
    
    def add_hook(
        self,
        event: str,
        handler: Callable,
    ) -> None:
        """Add event hook."""
        self._hooks[event].append(handler)
    
    async def _trigger_hooks(
        self,
        event: str,
        *args,
        **kwargs,
    ) -> None:
        """Trigger event hooks."""
        for handler in self._hooks[event]:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(*args, **kwargs)
                else:
                    handler(*args, **kwargs)
            except Exception as e:
                logger.error(f"Hook error: {e}")
    
    def set_user_preferences(
        self,
        user_id: str,
        preferences: Dict[str, Any],
    ) -> None:
        """Set user notification preferences."""
        self._user_preferences[user_id] = preferences
    
    def get_user_preferences(
        self,
        user_id: str,
    ) -> Dict[str, Any]:
        """Get user notification preferences."""
        return self._user_preferences.get(user_id, {})
    
    async def send(
        self,
        recipient: Union[str, Recipient],
        template: Optional[str] = None,
        channels: Optional[List[ChannelType]] = None,
        subject: Optional[str] = None,
        body: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        priority: Priority = Priority.NORMAL,
        **kwargs,
    ) -> NotificationRecord:
        """
        Send notification.
        
        Args:
            recipient: Recipient ID or object
            template: Template ID
            channels: Channels to use
            subject: Notification subject
            body: Notification body
            data: Template data
            priority: Priority level
            
        Returns:
            Notification record
        """
        # Resolve recipient
        if isinstance(recipient, str):
            recipient_obj = Recipient(id=recipient)
        else:
            recipient_obj = recipient
        
        # Create payload
        payload = NotificationPayload(
            template_id=template,
            recipient=recipient_obj,
            channels=channels or [ChannelType.EMAIL],
            subject=subject or "",
            body=body or "",
            data=data or {},
            priority=priority,
            **kwargs,
        )
        
        # Apply template
        if template and template in self._templates:
            tmpl = self._templates[template]
            if not payload.subject and tmpl.subject:
                payload.subject = self._template_engine.render(
                    tmpl.subject, payload.data
                )
            if not payload.body:
                payload.body = self._template_engine.render(
                    tmpl.body, payload.data
                )
            if not payload.html_body and tmpl.html_body:
                payload.html_body = self._template_engine.render(
                    tmpl.html_body, payload.data
                )
        
        # Check user preferences
        prefs = self.get_user_preferences(recipient_obj.id)
        if prefs.get("muted"):
            return NotificationRecord(
                recipient_id=recipient_obj.id,
                template_id=template,
                payload=payload,
                status=NotificationStatus.FAILED,
            )
        
        # Create record
        record = NotificationRecord(
            recipient_id=recipient_obj.id,
            template_id=template,
            payload=payload,
        )
        
        # Trigger pre-send hook
        await self._trigger_hooks("pre_send", record)
        
        # Send to channels
        for channel_type in payload.channels:
            if channel_type not in self._channels:
                record.results.append(DeliveryResult(
                    notification_id=payload.id,
                    channel=channel_type,
                    status=NotificationStatus.FAILED,
                    error="Channel not registered",
                ))
                continue
            
            channel = self._channels[channel_type]
            
            # Validate recipient
            if not await channel.validate_recipient(recipient_obj):
                record.results.append(DeliveryResult(
                    notification_id=payload.id,
                    channel=channel_type,
                    status=NotificationStatus.FAILED,
                    error="Invalid recipient for channel",
                ))
                continue
            
            try:
                result = await channel.send(recipient_obj, payload)
                record.results.append(result)
            except Exception as e:
                record.results.append(DeliveryResult(
                    notification_id=payload.id,
                    channel=channel_type,
                    status=NotificationStatus.FAILED,
                    error=str(e),
                ))
        
        # Update status
        if all(r.status == NotificationStatus.SENT for r in record.results):
            record.status = NotificationStatus.SENT
            record.sent_at = datetime.utcnow()
        elif any(r.status == NotificationStatus.SENT for r in record.results):
            record.status = NotificationStatus.SENT
            record.sent_at = datetime.utcnow()
        else:
            record.status = NotificationStatus.FAILED
        
        # Store record
        self._records[record.id] = record
        
        # Trigger post-send hook
        await self._trigger_hooks("post_send", record)
        
        return record
    
    async def send_bulk(
        self,
        recipients: List[Union[str, Recipient]],
        template: Optional[str] = None,
        channels: Optional[List[ChannelType]] = None,
        **kwargs,
    ) -> List[NotificationRecord]:
        """Send bulk notifications."""
        tasks = [
            self.send(
                recipient=r,
                template=template,
                channels=channels,
                **kwargs,
            )
            for r in recipients
        ]
        
        return await asyncio.gather(*tasks, return_exceptions=True)
    
    async def schedule(
        self,
        recipient: Union[str, Recipient],
        send_at: datetime,
        **kwargs,
    ) -> NotificationPayload:
        """
        Schedule notification.
        
        Args:
            recipient: Recipient ID or object
            send_at: Scheduled send time
            **kwargs: Notification parameters
            
        Returns:
            Scheduled payload
        """
        if isinstance(recipient, str):
            recipient_obj = Recipient(id=recipient)
        else:
            recipient_obj = recipient
        
        payload = NotificationPayload(
            recipient=recipient_obj,
            scheduled_at=send_at,
            **kwargs,
        )
        
        self._scheduled.append(payload)
        return payload
    
    async def get_scheduled(
        self,
        before: Optional[datetime] = None,
    ) -> List[NotificationPayload]:
        """Get scheduled notifications."""
        if before:
            return [
                p for p in self._scheduled
                if p.scheduled_at and p.scheduled_at <= before
            ]
        return self._scheduled
    
    async def process_scheduled(self) -> List[NotificationRecord]:
        """Process due scheduled notifications."""
        now = datetime.utcnow()
        due = [
            p for p in self._scheduled
            if p.scheduled_at and p.scheduled_at <= now
        ]
        
        records = []
        for payload in due:
            if payload.recipient:
                record = await self.send(
                    recipient=payload.recipient,
                    template=payload.template_id,
                    channels=payload.channels,
                    subject=payload.subject,
                    body=payload.body,
                    data=payload.data,
                )
                records.append(record)
            
            self._scheduled.remove(payload)
        
        return records
    
    async def get_record(
        self,
        notification_id: str,
    ) -> Optional[NotificationRecord]:
        """Get notification record."""
        return self._records.get(notification_id)
    
    async def get_user_history(
        self,
        user_id: str,
        limit: int = 50,
    ) -> List[NotificationRecord]:
        """Get user notification history."""
        records = [
            r for r in self._records.values()
            if r.recipient_id == user_id
        ]
        records.sort(key=lambda r: r.created_at, reverse=True)
        return records[:limit]


# Factory functions
def create_notification_hub(
    template_engine: Optional[TemplateEngine] = None,
) -> NotificationHub:
    """Create notification hub."""
    return NotificationHub(template_engine)


def create_email_channel(
    smtp_host: str = "localhost",
    **kwargs,
) -> EmailChannel:
    """Create email channel."""
    return EmailChannel(smtp_host=smtp_host, **kwargs)


def create_sms_channel(
    provider: str = "mock",
    **kwargs,
) -> SMSChannel:
    """Create SMS channel."""
    return SMSChannel(provider=provider, **kwargs)


def create_push_channel(
    provider: str = "mock",
    **kwargs,
) -> PushChannel:
    """Create push channel."""
    return PushChannel(provider=provider, **kwargs)


def create_notification_template(
    id: str,
    subject: str = "",
    body: str = "",
    **kwargs,
) -> NotificationTemplate:
    """Create notification template."""
    return NotificationTemplate(id=id, subject=subject, body=body, **kwargs)


def create_recipient(
    id: str,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    **kwargs,
) -> Recipient:
    """Create recipient."""
    return Recipient(id=id, email=email, phone=phone, **kwargs)


__all__ = [
    # Exceptions
    "NotificationError",
    "ChannelError",
    "DeliveryError",
    "TemplateError",
    # Enums
    "NotificationStatus",
    "Priority",
    "ChannelType",
    # Data classes
    "NotificationTemplate",
    "Recipient",
    "NotificationPayload",
    "DeliveryResult",
    "NotificationRecord",
    # Channels
    "NotificationChannel",
    "EmailChannel",
    "SMSChannel",
    "PushChannel",
    "SlackChannel",
    "WebhookChannel",
    "InAppChannel",
    # Engine
    "TemplateEngine",
    # Hub
    "NotificationHub",
    # Factory functions
    "create_notification_hub",
    "create_email_channel",
    "create_sms_channel",
    "create_push_channel",
    "create_notification_template",
    "create_recipient",
]
