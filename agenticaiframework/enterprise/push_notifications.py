"""
Enterprise Push Notification Module.

Push notifications for mobile and web,
device management, and delivery tracking.

Example:
    # Create push service
    push = create_push_service(fcm_credentials)
    
    # Send to device
    await push.send(
        token="device_token",
        title="New Message",
        body="You have a new message",
        data={"message_id": "123"},
    )
    
    # Send to topic
    await push.send_topic(
        topic="news",
        title="Breaking News",
        body="Important update...",
    )
    
    # Bulk send
    result = await push.bulk_send(
        tokens=device_tokens,
        notification=notification,
    )
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
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


class PushError(Exception):
    """Push notification error."""
    pass


class DeliveryStatus(str, Enum):
    """Delivery status."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    OPENED = "opened"
    FAILED = "failed"
    EXPIRED = "expired"
    UNREGISTERED = "unregistered"


class Platform(str, Enum):
    """Device platform."""
    IOS = "ios"
    ANDROID = "android"
    WEB = "web"
    UNKNOWN = "unknown"


class Priority(str, Enum):
    """Notification priority."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class PushCredentials:
    """Push provider credentials."""
    provider: str = "mock"
    api_key: str = ""
    project_id: str = ""
    credentials_file: str = ""
    options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Device:
    """Device registration."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    token: str = ""
    platform: Platform = Platform.UNKNOWN
    user_id: Optional[str] = None
    app_version: str = ""
    os_version: str = ""
    locale: str = "en"
    timezone: str = "UTC"
    tags: List[str] = field(default_factory=list)
    topics: List[str] = field(default_factory=list)
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    last_seen: Optional[datetime] = None


@dataclass
class Notification:
    """Push notification."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    body: str = ""
    image_url: Optional[str] = None
    icon: Optional[str] = None
    badge: Optional[int] = None
    sound: str = "default"
    data: Dict[str, Any] = field(default_factory=dict)
    action_url: Optional[str] = None
    actions: List[Dict[str, str]] = field(default_factory=list)
    priority: Priority = Priority.NORMAL
    ttl_seconds: int = 86400
    collapse_key: Optional[str] = None
    mutable_content: bool = False
    content_available: bool = False


@dataclass
class SendResult:
    """Send result."""
    notification_id: str
    success: bool
    status: DeliveryStatus
    recipient: str
    message_id: Optional[str] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    sent_at: Optional[datetime] = None


@dataclass
class BulkSendResult:
    """Bulk send result."""
    notification_id: str
    total: int = 0
    success: int = 0
    failed: int = 0
    results: List[SendResult] = field(default_factory=list)
    duration_seconds: float = 0


@dataclass
class PushStats:
    """Push statistics."""
    total_sent: int = 0
    delivered: int = 0
    opened: int = 0
    failed: int = 0
    unregistered: int = 0
    by_platform: Dict[str, int] = field(default_factory=dict)


# Push provider base
class PushProvider(ABC):
    """Base push provider."""
    
    @abstractmethod
    async def send(
        self,
        token: str,
        notification: Notification,
        platform: Platform = Platform.UNKNOWN,
    ) -> SendResult:
        """Send to device."""
        pass
    
    @abstractmethod
    async def send_topic(
        self,
        topic: str,
        notification: Notification,
    ) -> SendResult:
        """Send to topic."""
        pass
    
    @abstractmethod
    async def bulk_send(
        self,
        tokens: List[str],
        notification: Notification,
    ) -> BulkSendResult:
        """Bulk send."""
        pass


# Mock provider
class MockPushProvider(PushProvider):
    """Mock push provider for testing."""
    
    def __init__(self):
        self.sent_notifications: List[Tuple[str, Notification]] = []
        self.should_fail: bool = False
        self.invalid_tokens: Set[str] = set()
    
    async def send(
        self,
        token: str,
        notification: Notification,
        platform: Platform = Platform.UNKNOWN,
    ) -> SendResult:
        """Send (mock)."""
        if self.should_fail or token in self.invalid_tokens:
            return SendResult(
                notification_id=notification.id,
                success=False,
                status=DeliveryStatus.FAILED if self.should_fail else DeliveryStatus.UNREGISTERED,
                recipient=token,
                error="Mock failure" if self.should_fail else "Invalid token",
            )
        
        self.sent_notifications.append((token, notification))
        
        return SendResult(
            notification_id=notification.id,
            success=True,
            status=DeliveryStatus.SENT,
            recipient=token,
            message_id=str(uuid.uuid4()),
            sent_at=datetime.utcnow(),
        )
    
    async def send_topic(
        self,
        topic: str,
        notification: Notification,
    ) -> SendResult:
        """Send to topic (mock)."""
        if self.should_fail:
            return SendResult(
                notification_id=notification.id,
                success=False,
                status=DeliveryStatus.FAILED,
                recipient=f"topic:{topic}",
                error="Mock failure",
            )
        
        self.sent_notifications.append((f"topic:{topic}", notification))
        
        return SendResult(
            notification_id=notification.id,
            success=True,
            status=DeliveryStatus.SENT,
            recipient=f"topic:{topic}",
            message_id=str(uuid.uuid4()),
            sent_at=datetime.utcnow(),
        )
    
    async def bulk_send(
        self,
        tokens: List[str],
        notification: Notification,
    ) -> BulkSendResult:
        """Bulk send (mock)."""
        start = datetime.utcnow()
        results = []
        success = 0
        failed = 0
        
        for token in tokens:
            result = await self.send(token, notification)
            results.append(result)
            if result.success:
                success += 1
            else:
                failed += 1
        
        duration = (datetime.utcnow() - start).total_seconds()
        
        return BulkSendResult(
            notification_id=notification.id,
            total=len(tokens),
            success=success,
            failed=failed,
            results=results,
            duration_seconds=duration,
        )


# Device store
class DeviceStore(ABC):
    """Device storage."""
    
    @abstractmethod
    async def register(self, device: Device) -> None:
        """Register device."""
        pass
    
    @abstractmethod
    async def get(self, token: str) -> Optional[Device]:
        """Get device."""
        pass
    
    @abstractmethod
    async def get_by_user(self, user_id: str) -> List[Device]:
        """Get devices by user."""
        pass
    
    @abstractmethod
    async def get_by_topic(self, topic: str) -> List[Device]:
        """Get devices by topic."""
        pass
    
    @abstractmethod
    async def unregister(self, token: str) -> bool:
        """Unregister device."""
        pass
    
    @abstractmethod
    async def update(self, device: Device) -> None:
        """Update device."""
        pass


class InMemoryDeviceStore(DeviceStore):
    """In-memory device store."""
    
    def __init__(self):
        self._devices: Dict[str, Device] = {}
    
    async def register(self, device: Device) -> None:
        self._devices[device.token] = device
    
    async def get(self, token: str) -> Optional[Device]:
        return self._devices.get(token)
    
    async def get_by_user(self, user_id: str) -> List[Device]:
        return [d for d in self._devices.values() if d.user_id == user_id]
    
    async def get_by_topic(self, topic: str) -> List[Device]:
        return [d for d in self._devices.values() if topic in d.topics]
    
    async def unregister(self, token: str) -> bool:
        if token in self._devices:
            del self._devices[token]
            return True
        return False
    
    async def update(self, device: Device) -> None:
        device.updated_at = datetime.utcnow()
        self._devices[device.token] = device


# Notification history
class NotificationHistory(ABC):
    """Notification history storage."""
    
    @abstractmethod
    async def save(self, notification: Notification, result: SendResult) -> None:
        """Save notification."""
        pass
    
    @abstractmethod
    async def get(self, notification_id: str) -> Optional[Dict[str, Any]]:
        """Get notification."""
        pass
    
    @abstractmethod
    async def get_by_recipient(
        self,
        recipient: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get notifications for recipient."""
        pass


class InMemoryNotificationHistory(NotificationHistory):
    """In-memory notification history."""
    
    def __init__(self, max_size: int = 10000):
        self._history: List[Dict[str, Any]] = []
        self._max_size = max_size
    
    async def save(self, notification: Notification, result: SendResult) -> None:
        entry = {
            "notification_id": notification.id,
            "title": notification.title,
            "body": notification.body,
            "recipient": result.recipient,
            "status": result.status.value,
            "success": result.success,
            "error": result.error,
            "sent_at": result.sent_at.isoformat() if result.sent_at else None,
        }
        self._history.append(entry)
        
        # Trim
        if len(self._history) > self._max_size:
            self._history = self._history[-self._max_size:]
    
    async def get(self, notification_id: str) -> Optional[Dict[str, Any]]:
        for entry in reversed(self._history):
            if entry["notification_id"] == notification_id:
                return entry
        return None
    
    async def get_by_recipient(
        self,
        recipient: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        results = [
            e for e in reversed(self._history)
            if e["recipient"] == recipient
        ]
        return results[:limit]


# Push service
class PushService:
    """Push notification service."""
    
    def __init__(
        self,
        provider: PushProvider,
        device_store: Optional[DeviceStore] = None,
        history: Optional[NotificationHistory] = None,
    ):
        self.provider = provider
        self.device_store = device_store or InMemoryDeviceStore()
        self.history = history or InMemoryNotificationHistory()
        self._stats = PushStats()
    
    async def register_device(
        self,
        token: str,
        platform: Platform = Platform.UNKNOWN,
        user_id: Optional[str] = None,
        **kwargs,
    ) -> Device:
        """Register device."""
        device = Device(
            token=token,
            platform=platform,
            user_id=user_id,
            **kwargs,
        )
        await self.device_store.register(device)
        logger.info(f"Device registered: {token[:20]}...")
        return device
    
    async def unregister_device(self, token: str) -> bool:
        """Unregister device."""
        return await self.device_store.unregister(token)
    
    async def subscribe_topic(self, token: str, topic: str) -> bool:
        """Subscribe device to topic."""
        device = await self.device_store.get(token)
        if device and topic not in device.topics:
            device.topics.append(topic)
            await self.device_store.update(device)
            return True
        return False
    
    async def unsubscribe_topic(self, token: str, topic: str) -> bool:
        """Unsubscribe from topic."""
        device = await self.device_store.get(token)
        if device and topic in device.topics:
            device.topics.remove(topic)
            await self.device_store.update(device)
            return True
        return False
    
    async def send(
        self,
        token: str,
        title: str,
        body: str = "",
        data: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> SendResult:
        """Send notification to device."""
        notification = Notification(
            title=title,
            body=body,
            data=data or {},
            **kwargs,
        )
        
        # Get platform
        device = await self.device_store.get(token)
        platform = device.platform if device else Platform.UNKNOWN
        
        result = await self.provider.send(token, notification, platform)
        
        # Update stats
        if result.success:
            self._stats.total_sent += 1
            self._stats.by_platform[platform.value] = (
                self._stats.by_platform.get(platform.value, 0) + 1
            )
        else:
            self._stats.failed += 1
            if result.status == DeliveryStatus.UNREGISTERED:
                self._stats.unregistered += 1
                # Remove invalid device
                await self.unregister_device(token)
        
        # Save history
        await self.history.save(notification, result)
        
        return result
    
    async def send_notification(
        self,
        token: str,
        notification: Notification,
    ) -> SendResult:
        """Send notification object."""
        device = await self.device_store.get(token)
        platform = device.platform if device else Platform.UNKNOWN
        
        result = await self.provider.send(token, notification, platform)
        
        if result.success:
            self._stats.total_sent += 1
        else:
            self._stats.failed += 1
        
        await self.history.save(notification, result)
        return result
    
    async def send_to_user(
        self,
        user_id: str,
        title: str,
        body: str = "",
        data: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> BulkSendResult:
        """Send to all user's devices."""
        devices = await self.device_store.get_by_user(user_id)
        tokens = [d.token for d in devices if d.enabled]
        
        if not tokens:
            return BulkSendResult(
                notification_id=str(uuid.uuid4()),
                total=0,
                success=0,
                failed=0,
            )
        
        notification = Notification(
            title=title,
            body=body,
            data=data or {},
            **kwargs,
        )
        
        return await self.provider.bulk_send(tokens, notification)
    
    async def send_topic(
        self,
        topic: str,
        title: str,
        body: str = "",
        data: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> SendResult:
        """Send to topic."""
        notification = Notification(
            title=title,
            body=body,
            data=data or {},
            **kwargs,
        )
        
        result = await self.provider.send_topic(topic, notification)
        
        if result.success:
            self._stats.total_sent += 1
        else:
            self._stats.failed += 1
        
        return result
    
    async def bulk_send(
        self,
        tokens: List[str],
        title: str,
        body: str = "",
        data: Optional[Dict[str, Any]] = None,
        batch_size: int = 500,
        **kwargs,
    ) -> BulkSendResult:
        """Bulk send to devices."""
        notification = Notification(
            title=title,
            body=body,
            data=data or {},
            **kwargs,
        )
        
        start = datetime.utcnow()
        all_results: List[SendResult] = []
        success = 0
        failed = 0
        
        # Process in batches
        for i in range(0, len(tokens), batch_size):
            batch = tokens[i:i + batch_size]
            result = await self.provider.bulk_send(batch, notification)
            
            all_results.extend(result.results)
            success += result.success
            failed += result.failed
            
            # Remove unregistered devices
            for r in result.results:
                if r.status == DeliveryStatus.UNREGISTERED:
                    await self.unregister_device(r.recipient)
            
            # Small delay between batches
            if i + batch_size < len(tokens):
                await asyncio.sleep(0.1)
        
        duration = (datetime.utcnow() - start).total_seconds()
        
        self._stats.total_sent += success
        self._stats.failed += failed
        
        return BulkSendResult(
            notification_id=notification.id,
            total=len(tokens),
            success=success,
            failed=failed,
            results=all_results,
            duration_seconds=duration,
        )
    
    async def get_device(self, token: str) -> Optional[Device]:
        """Get device."""
        return await self.device_store.get(token)
    
    async def get_user_devices(self, user_id: str) -> List[Device]:
        """Get user's devices."""
        return await self.device_store.get_by_user(user_id)
    
    async def get_notification_history(
        self,
        recipient: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get notification history."""
        return await self.history.get_by_recipient(recipient, limit)
    
    def get_stats(self) -> PushStats:
        """Get statistics."""
        return self._stats


# Factory functions
def create_push_service(
    credentials: Optional[PushCredentials] = None,
    provider: Optional[PushProvider] = None,
    **kwargs,
) -> PushService:
    """Create push service."""
    if provider is None:
        provider = MockPushProvider()
    
    return PushService(provider=provider, **kwargs)


def create_notification(
    title: str,
    body: str = "",
    data: Optional[Dict[str, Any]] = None,
    **kwargs,
) -> Notification:
    """Create notification."""
    return Notification(
        title=title,
        body=body,
        data=data or {},
        **kwargs,
    )


def create_device(
    token: str,
    platform: Platform = Platform.UNKNOWN,
    **kwargs,
) -> Device:
    """Create device."""
    return Device(token=token, platform=platform, **kwargs)


__all__ = [
    # Exceptions
    "PushError",
    # Enums
    "DeliveryStatus",
    "Platform",
    "Priority",
    # Data classes
    "PushCredentials",
    "Device",
    "Notification",
    "SendResult",
    "BulkSendResult",
    "PushStats",
    # Providers
    "PushProvider",
    "MockPushProvider",
    # Device store
    "DeviceStore",
    "InMemoryDeviceStore",
    # History
    "NotificationHistory",
    "InMemoryNotificationHistory",
    # Service
    "PushService",
    # Factory functions
    "create_push_service",
    "create_notification",
    "create_device",
]
