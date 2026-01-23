"""
Enterprise Notification Module.

Provides multi-channel notifications, alerting, and messaging
for agent operations and monitoring.

Example:
    # Send notifications
    notifier = Notifier()
    notifier.add_channel(SlackChannel(webhook_url))
    notifier.add_channel(EmailChannel(smtp_config))
    
    await notifier.send(
        Notification(
            title="Agent Alert",
            message="High latency detected",
            severity=Severity.WARNING,
        )
    )
    
    # Decorators
    @notify_on_failure(channels=["slack"])
    async def critical_operation():
        ...
"""

from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Union,
)
from datetime import datetime
from functools import wraps
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class NotificationError(Exception):
    """Notification sending failed."""
    pass


class ChannelError(NotificationError):
    """Channel-specific error."""
    
    def __init__(self, message: str, channel: str, original: Optional[Exception] = None):
        super().__init__(message)
        self.channel = channel
        self.original = original


class Severity(str, Enum):
    """Notification severity levels."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class NotificationType(str, Enum):
    """Types of notifications."""
    ALERT = "alert"
    EVENT = "event"
    REPORT = "report"
    MESSAGE = "message"
    DIGEST = "digest"


@dataclass
class Notification:
    """A notification message."""
    title: str
    message: str
    severity: Severity = Severity.INFO
    notification_type: NotificationType = NotificationType.ALERT
    source: str = ""
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "message": self.message,
            "severity": self.severity.value,
            "type": self.notification_type.value,
            "source": self.source,
            "tags": self.tags,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }
    
    def to_text(self) -> str:
        """Convert to plain text."""
        return f"[{self.severity.value.upper()}] {self.title}\n{self.message}"
    
    def to_html(self) -> str:
        """Convert to HTML."""
        color = {
            Severity.DEBUG: "#6c757d",
            Severity.INFO: "#17a2b8",
            Severity.WARNING: "#ffc107",
            Severity.ERROR: "#dc3545",
            Severity.CRITICAL: "#721c24",
        }.get(self.severity, "#333")
        
        return f"""
        <div style="border-left: 4px solid {color}; padding: 10px; margin: 10px 0;">
            <h3 style="color: {color}; margin: 0;">{self.title}</h3>
            <p>{self.message}</p>
            <small style="color: #666;">{datetime.fromtimestamp(self.timestamp).isoformat()}</small>
        </div>
        """


@dataclass
class NotificationResult:
    """Result of sending a notification."""
    success: bool
    channel: str
    notification_id: Optional[str] = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "channel": self.channel,
            "notification_id": self.notification_id,
            "error": self.error,
        }


class NotificationChannel(ABC):
    """Abstract notification channel."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Get channel name."""
        pass
    
    @property
    @abstractmethod
    def supports_html(self) -> bool:
        """Check if channel supports HTML."""
        pass
    
    @abstractmethod
    async def send(self, notification: Notification) -> NotificationResult:
        """Send a notification."""
        pass
    
    async def send_batch(self, notifications: List[Notification]) -> List[NotificationResult]:
        """Send multiple notifications."""
        results = []
        for notification in notifications:
            result = await self.send(notification)
            results.append(result)
        return results


class ConsoleChannel(NotificationChannel):
    """Console/logging channel for development."""
    
    def __init__(self, name: str = "console"):
        self._name = name
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def supports_html(self) -> bool:
        return False
    
    async def send(self, notification: Notification) -> NotificationResult:
        """Log notification to console."""
        log_level = {
            Severity.DEBUG: logging.DEBUG,
            Severity.INFO: logging.INFO,
            Severity.WARNING: logging.WARNING,
            Severity.ERROR: logging.ERROR,
            Severity.CRITICAL: logging.CRITICAL,
        }.get(notification.severity, logging.INFO)
        
        logger.log(log_level, f"{notification.title}: {notification.message}")
        
        return NotificationResult(
            success=True,
            channel=self.name,
        )


class WebhookChannel(NotificationChannel):
    """Generic webhook notification channel."""
    
    def __init__(
        self,
        webhook_url: str,
        name: str = "webhook",
        headers: Optional[Dict[str, str]] = None,
        template: Optional[Callable[[Notification], Dict]] = None,
    ):
        """
        Initialize webhook channel.
        
        Args:
            webhook_url: Webhook URL
            name: Channel name
            headers: Additional HTTP headers
            template: Function to convert notification to payload
        """
        self._webhook_url = webhook_url
        self._name = name
        self._headers = headers or {}
        self._template = template
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def supports_html(self) -> bool:
        return False
    
    async def send(self, notification: Notification) -> NotificationResult:
        """Send notification via webhook."""
        try:
            import aiohttp
            
            if self._template:
                payload = self._template(notification)
            else:
                payload = notification.to_dict()
            
            headers = {
                "Content-Type": "application/json",
                **self._headers,
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self._webhook_url,
                    json=payload,
                    headers=headers,
                ) as response:
                    if response.status >= 400:
                        return NotificationResult(
                            success=False,
                            channel=self.name,
                            error=f"HTTP {response.status}",
                        )
                    
                    return NotificationResult(
                        success=True,
                        channel=self.name,
                    )
                    
        except ImportError:
            # Fallback to urllib
            import urllib.request
            import urllib.error
            
            if self._template:
                payload = self._template(notification)
            else:
                payload = notification.to_dict()
            
            try:
                req = urllib.request.Request(
                    self._webhook_url,
                    data=json.dumps(payload).encode(),
                    headers={
                        "Content-Type": "application/json",
                        **self._headers,
                    },
                    method="POST",
                )
                
                with urllib.request.urlopen(req) as response:
                    return NotificationResult(
                        success=True,
                        channel=self.name,
                    )
                    
            except urllib.error.HTTPError as e:
                return NotificationResult(
                    success=False,
                    channel=self.name,
                    error=str(e),
                )
                
        except Exception as e:
            return NotificationResult(
                success=False,
                channel=self.name,
                error=str(e),
            )


class SlackChannel(NotificationChannel):
    """Slack notification channel."""
    
    def __init__(
        self,
        webhook_url: str,
        name: str = "slack",
        username: str = "Agent Bot",
        icon_emoji: str = ":robot_face:",
    ):
        """
        Initialize Slack channel.
        
        Args:
            webhook_url: Slack webhook URL
            name: Channel name
            username: Bot username
            icon_emoji: Bot icon emoji
        """
        self._webhook_url = webhook_url
        self._name = name
        self._username = username
        self._icon_emoji = icon_emoji
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def supports_html(self) -> bool:
        return False
    
    def _build_payload(self, notification: Notification) -> Dict[str, Any]:
        """Build Slack message payload."""
        color = {
            Severity.DEBUG: "#6c757d",
            Severity.INFO: "#17a2b8",
            Severity.WARNING: "#ffc107",
            Severity.ERROR: "#dc3545",
            Severity.CRITICAL: "#721c24",
        }.get(notification.severity, "#333")
        
        return {
            "username": self._username,
            "icon_emoji": self._icon_emoji,
            "attachments": [
                {
                    "color": color,
                    "title": notification.title,
                    "text": notification.message,
                    "fields": [
                        {
                            "title": "Severity",
                            "value": notification.severity.value.upper(),
                            "short": True,
                        },
                        {
                            "title": "Source",
                            "value": notification.source or "Unknown",
                            "short": True,
                        },
                    ],
                    "footer": f"Agent Notification | {datetime.fromtimestamp(notification.timestamp).isoformat()}",
                }
            ],
        }
    
    async def send(self, notification: Notification) -> NotificationResult:
        """Send notification to Slack."""
        webhook = WebhookChannel(
            webhook_url=self._webhook_url,
            name=self._name,
            template=self._build_payload,
        )
        return await webhook.send(notification)


class EmailChannel(NotificationChannel):
    """Email notification channel."""
    
    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        username: str,
        password: str,
        from_email: str,
        to_emails: List[str],
        name: str = "email",
        use_tls: bool = True,
    ):
        """
        Initialize email channel.
        
        Args:
            smtp_host: SMTP server host
            smtp_port: SMTP server port
            username: SMTP username
            password: SMTP password
            from_email: Sender email
            to_emails: Recipient emails
            name: Channel name
            use_tls: Use TLS encryption
        """
        self._smtp_host = smtp_host
        self._smtp_port = smtp_port
        self._username = username
        self._password = password
        self._from_email = from_email
        self._to_emails = to_emails
        self._name = name
        self._use_tls = use_tls
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def supports_html(self) -> bool:
        return True
    
    async def send(self, notification: Notification) -> NotificationResult:
        """Send notification via email."""
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"[{notification.severity.value.upper()}] {notification.title}"
            msg["From"] = self._from_email
            msg["To"] = ", ".join(self._to_emails)
            
            # Add plain text and HTML versions
            msg.attach(MIMEText(notification.to_text(), "plain"))
            msg.attach(MIMEText(notification.to_html(), "html"))
            
            # Send email
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self._send_email,
                msg,
            )
            
            return NotificationResult(
                success=True,
                channel=self.name,
            )
            
        except Exception as e:
            return NotificationResult(
                success=False,
                channel=self.name,
                error=str(e),
            )
    
    def _send_email(self, msg) -> None:
        """Send email synchronously."""
        import smtplib
        
        with smtplib.SMTP(self._smtp_host, self._smtp_port) as server:
            if self._use_tls:
                server.starttls()
            server.login(self._username, self._password)
            server.send_message(msg)


class InMemoryChannel(NotificationChannel):
    """In-memory channel for testing."""
    
    def __init__(self, name: str = "memory"):
        self._name = name
        self._notifications: List[Notification] = []
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def supports_html(self) -> bool:
        return True
    
    @property
    def notifications(self) -> List[Notification]:
        """Get all stored notifications."""
        return self._notifications
    
    async def send(self, notification: Notification) -> NotificationResult:
        """Store notification in memory."""
        self._notifications.append(notification)
        return NotificationResult(
            success=True,
            channel=self.name,
            notification_id=str(len(self._notifications) - 1),
        )
    
    def clear(self) -> None:
        """Clear stored notifications."""
        self._notifications.clear()


class Notifier:
    """
    Central notification manager.
    """
    
    def __init__(self):
        self._channels: Dict[str, NotificationChannel] = {}
        self._filters: List[Callable[[Notification], bool]] = []
        self._transformers: List[Callable[[Notification], Notification]] = []
        self._default_severity_channels: Dict[Severity, List[str]] = {}
    
    def add_channel(
        self,
        channel: NotificationChannel,
        severities: Optional[List[Severity]] = None,
    ) -> 'Notifier':
        """
        Add a notification channel.
        
        Args:
            channel: Channel to add
            severities: Optional severity filter for this channel
        """
        self._channels[channel.name] = channel
        
        if severities:
            for severity in severities:
                if severity not in self._default_severity_channels:
                    self._default_severity_channels[severity] = []
                self._default_severity_channels[severity].append(channel.name)
        
        return self
    
    def remove_channel(self, name: str) -> bool:
        """Remove a channel."""
        if name in self._channels:
            del self._channels[name]
            return True
        return False
    
    def add_filter(self, filter_func: Callable[[Notification], bool]) -> 'Notifier':
        """Add a notification filter."""
        self._filters.append(filter_func)
        return self
    
    def add_transformer(
        self,
        transformer: Callable[[Notification], Notification],
    ) -> 'Notifier':
        """Add a notification transformer."""
        self._transformers.append(transformer)
        return self
    
    async def send(
        self,
        notification: Notification,
        channels: Optional[List[str]] = None,
    ) -> List[NotificationResult]:
        """
        Send notification to specified channels.
        
        Args:
            notification: Notification to send
            channels: Optional list of channel names (defaults to all)
            
        Returns:
            List of results per channel
        """
        # Apply filters
        for filter_func in self._filters:
            if not filter_func(notification):
                return []
        
        # Apply transformers
        for transformer in self._transformers:
            notification = transformer(notification)
        
        # Determine target channels
        if channels:
            target_channels = [
                self._channels[name]
                for name in channels
                if name in self._channels
            ]
        elif notification.severity in self._default_severity_channels:
            target_channels = [
                self._channels[name]
                for name in self._default_severity_channels[notification.severity]
                if name in self._channels
            ]
        else:
            target_channels = list(self._channels.values())
        
        # Send to all channels concurrently
        tasks = [channel.send(notification) for channel in target_channels]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert exceptions to results
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append(NotificationResult(
                    success=False,
                    channel=target_channels[i].name,
                    error=str(result),
                ))
            else:
                final_results.append(result)
        
        return final_results
    
    async def alert(
        self,
        title: str,
        message: str,
        severity: Severity = Severity.WARNING,
        **kwargs: Any,
    ) -> List[NotificationResult]:
        """Send an alert notification."""
        notification = Notification(
            title=title,
            message=message,
            severity=severity,
            notification_type=NotificationType.ALERT,
            **kwargs,
        )
        return await self.send(notification)
    
    async def info(self, title: str, message: str, **kwargs: Any) -> List[NotificationResult]:
        """Send an info notification."""
        return await self.alert(title, message, Severity.INFO, **kwargs)
    
    async def warning(self, title: str, message: str, **kwargs: Any) -> List[NotificationResult]:
        """Send a warning notification."""
        return await self.alert(title, message, Severity.WARNING, **kwargs)
    
    async def error(self, title: str, message: str, **kwargs: Any) -> List[NotificationResult]:
        """Send an error notification."""
        return await self.alert(title, message, Severity.ERROR, **kwargs)
    
    async def critical(self, title: str, message: str, **kwargs: Any) -> List[NotificationResult]:
        """Send a critical notification."""
        return await self.alert(title, message, Severity.CRITICAL, **kwargs)


# Global notifier instance
_notifier: Optional[Notifier] = None


def get_notifier() -> Notifier:
    """Get the global notifier instance."""
    global _notifier
    if _notifier is None:
        _notifier = Notifier()
    return _notifier


def notify_on_failure(
    channels: Optional[List[str]] = None,
    title: Optional[str] = None,
    severity: Severity = Severity.ERROR,
) -> Callable:
    """
    Decorator to send notification on function failure.
    
    Example:
        @notify_on_failure(channels=["slack"])
        async def critical_operation():
            ...
    """
    def decorator(func: Callable) -> Callable:
        func_name = func.__name__
        
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                notifier = get_notifier()
                await notifier.send(
                    Notification(
                        title=title or f"Error in {func_name}",
                        message=str(e),
                        severity=severity,
                        source=func_name,
                    ),
                    channels=channels,
                )
                raise
        
        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                notifier = get_notifier()
                asyncio.run(notifier.send(
                    Notification(
                        title=title or f"Error in {func_name}",
                        message=str(e),
                        severity=severity,
                        source=func_name,
                    ),
                    channels=channels,
                ))
                raise
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


def notify_on_success(
    channels: Optional[List[str]] = None,
    title: Optional[str] = None,
    severity: Severity = Severity.INFO,
) -> Callable:
    """
    Decorator to send notification on function success.
    
    Example:
        @notify_on_success(channels=["email"])
        async def important_operation():
            ...
    """
    def decorator(func: Callable) -> Callable:
        func_name = func.__name__
        
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            result = await func(*args, **kwargs)
            
            notifier = get_notifier()
            await notifier.send(
                Notification(
                    title=title or f"Completed: {func_name}",
                    message=f"Operation {func_name} completed successfully",
                    severity=severity,
                    source=func_name,
                    metadata={"result": str(result)[:100]},
                ),
                channels=channels,
            )
            
            return result
        
        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            result = func(*args, **kwargs)
            
            notifier = get_notifier()
            asyncio.run(notifier.send(
                Notification(
                    title=title or f"Completed: {func_name}",
                    message=f"Operation {func_name} completed successfully",
                    severity=severity,
                    source=func_name,
                ),
                channels=channels,
            ))
            
            return result
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


__all__ = [
    # Exceptions
    "NotificationError",
    "ChannelError",
    # Enums
    "Severity",
    "NotificationType",
    # Data classes
    "Notification",
    "NotificationResult",
    # Channels
    "NotificationChannel",
    "ConsoleChannel",
    "WebhookChannel",
    "SlackChannel",
    "EmailChannel",
    "InMemoryChannel",
    # Main class
    "Notifier",
    # Decorators
    "notify_on_failure",
    "notify_on_success",
    # Utility
    "get_notifier",
]
