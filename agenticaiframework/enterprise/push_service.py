"""
Enterprise Push Notification Service Module.

Provides push notification sending, multi-provider support,
device registration, and notification templating.

Example:
    # Create push service
    push = create_push_service(
        providers={
            "fcm": create_fcm_provider(api_key="..."),
            "apns": create_apns_provider(key_file="..."),
        }
    )
    
    # Register device
    await push.register_device(
        user_id="user123",
        device_token="abc123...",
        platform="ios",
    )
    
    # Send notification
    await push.send(
        user_id="user123",
        title="New Message",
        body="You have a new message!",
        data={"message_id": "456"},
    )
"""

from __future__ import annotations

import asyncio
import functools
import logging
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
    TypeVar,
    Union,
)

T = TypeVar('T')


logger = logging.getLogger(__name__)


class PushError(Exception):
    """Push notification error."""
    pass


class DeviceNotFoundError(PushError):
    """Device not found."""
    pass


class DeliveryError(PushError):
    """Notification delivery error."""
    pass


class Platform(str, Enum):
    """Device platforms."""
    IOS = "ios"
    ANDROID = "android"
    WEB = "web"


class NotificationPriority(str, Enum):
    """Notification priority."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class DeliveryStatus(str, Enum):
    """Delivery status."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    OPENED = "opened"
    FAILED = "failed"
    INVALID_TOKEN = "invalid_token"


@dataclass
class Device:
    """Device registration."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    token: str = ""
    platform: Platform = Platform.ANDROID
    app_version: str = ""
    os_version: str = ""
    device_model: str = ""
    locale: str = "en"
    timezone: str = "UTC"
    active: bool = True
    tags: Dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_active_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Notification:
    """Push notification."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    body: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    image_url: str = ""
    icon: str = ""
    sound: str = "default"
    badge: Optional[int] = None
    priority: NotificationPriority = NotificationPriority.NORMAL
    ttl: int = 86400  # 24 hours
    collapse_key: str = ""
    channel_id: str = ""  # Android notification channel
    category: str = ""  # iOS category
    thread_id: str = ""  # iOS thread
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class DeliveryResult:
    """Notification delivery result."""
    notification_id: str
    device_id: str
    success: bool
    status: DeliveryStatus
    provider_id: Optional[str] = None
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class BulkResult:
    """Bulk send result."""
    notification_id: str
    total: int
    success_count: int
    failure_count: int
    results: List[DeliveryResult] = field(default_factory=list)


# Push providers
class PushProvider(ABC):
    """Abstract push provider."""
    
    @property
    @abstractmethod
    def platform(self) -> Platform:
        """Supported platform."""
        pass
    
    @abstractmethod
    async def send(
        self,
        device: Device,
        notification: Notification,
    ) -> DeliveryResult:
        """Send notification to device."""
        pass
    
    @abstractmethod
    async def send_batch(
        self,
        devices: List[Device],
        notification: Notification,
    ) -> List[DeliveryResult]:
        """Send notification to multiple devices."""
        pass


class FCMProvider(PushProvider):
    """Firebase Cloud Messaging provider."""
    
    def __init__(
        self,
        api_key: str,
        project_id: str = "",
    ):
        self._api_key = api_key
        self._project_id = project_id
    
    @property
    def platform(self) -> Platform:
        return Platform.ANDROID
    
    async def send(
        self,
        device: Device,
        notification: Notification,
    ) -> DeliveryResult:
        """Send via FCM."""
        try:
            # Would use firebase-admin in real implementation
            logger.info(
                f"Sending FCM notification {notification.id} "
                f"to device {device.id}"
            )
            
            return DeliveryResult(
                notification_id=notification.id,
                device_id=device.id,
                success=True,
                status=DeliveryStatus.SENT,
                provider_id=f"fcm-{uuid.uuid4().hex[:16]}",
            )
            
        except Exception as e:
            return DeliveryResult(
                notification_id=notification.id,
                device_id=device.id,
                success=False,
                status=DeliveryStatus.FAILED,
                error=str(e),
            )
    
    async def send_batch(
        self,
        devices: List[Device],
        notification: Notification,
    ) -> List[DeliveryResult]:
        """Send batch via FCM."""
        return [
            await self.send(device, notification)
            for device in devices
        ]


class APNSProvider(PushProvider):
    """Apple Push Notification Service provider."""
    
    def __init__(
        self,
        key_file: str = "",
        key_id: str = "",
        team_id: str = "",
        bundle_id: str = "",
        use_sandbox: bool = False,
    ):
        self._key_file = key_file
        self._key_id = key_id
        self._team_id = team_id
        self._bundle_id = bundle_id
        self._use_sandbox = use_sandbox
    
    @property
    def platform(self) -> Platform:
        return Platform.IOS
    
    async def send(
        self,
        device: Device,
        notification: Notification,
    ) -> DeliveryResult:
        """Send via APNS."""
        try:
            # Would use httpx with JWT in real implementation
            logger.info(
                f"Sending APNS notification {notification.id} "
                f"to device {device.id}"
            )
            
            return DeliveryResult(
                notification_id=notification.id,
                device_id=device.id,
                success=True,
                status=DeliveryStatus.SENT,
                provider_id=f"apns-{uuid.uuid4().hex[:16]}",
            )
            
        except Exception as e:
            return DeliveryResult(
                notification_id=notification.id,
                device_id=device.id,
                success=False,
                status=DeliveryStatus.FAILED,
                error=str(e),
            )
    
    async def send_batch(
        self,
        devices: List[Device],
        notification: Notification,
    ) -> List[DeliveryResult]:
        """Send batch via APNS."""
        return [
            await self.send(device, notification)
            for device in devices
        ]


class WebPushProvider(PushProvider):
    """Web Push provider."""
    
    def __init__(
        self,
        vapid_private_key: str = "",
        vapid_public_key: str = "",
        vapid_subject: str = "",
    ):
        self._vapid_private_key = vapid_private_key
        self._vapid_public_key = vapid_public_key
        self._vapid_subject = vapid_subject
    
    @property
    def platform(self) -> Platform:
        return Platform.WEB
    
    async def send(
        self,
        device: Device,
        notification: Notification,
    ) -> DeliveryResult:
        """Send via Web Push."""
        try:
            # Would use pywebpush in real implementation
            logger.info(
                f"Sending Web Push notification {notification.id} "
                f"to device {device.id}"
            )
            
            return DeliveryResult(
                notification_id=notification.id,
                device_id=device.id,
                success=True,
                status=DeliveryStatus.SENT,
                provider_id=f"web-{uuid.uuid4().hex[:16]}",
            )
            
        except Exception as e:
            return DeliveryResult(
                notification_id=notification.id,
                device_id=device.id,
                success=False,
                status=DeliveryStatus.FAILED,
                error=str(e),
            )
    
    async def send_batch(
        self,
        devices: List[Device],
        notification: Notification,
    ) -> List[DeliveryResult]:
        """Send batch via Web Push."""
        return [
            await self.send(device, notification)
            for device in devices
        ]


class MockProvider(PushProvider):
    """Mock provider for testing."""
    
    def __init__(self, platform: Platform = Platform.ANDROID):
        self._platform = platform
        self._sent: List[Tuple[Device, Notification]] = []
    
    @property
    def platform(self) -> Platform:
        return self._platform
    
    async def send(
        self,
        device: Device,
        notification: Notification,
    ) -> DeliveryResult:
        self._sent.append((device, notification))
        
        return DeliveryResult(
            notification_id=notification.id,
            device_id=device.id,
            success=True,
            status=DeliveryStatus.DELIVERED,
            provider_id=f"mock-{uuid.uuid4().hex[:16]}",
        )
    
    async def send_batch(
        self,
        devices: List[Device],
        notification: Notification,
    ) -> List[DeliveryResult]:
        return [
            await self.send(device, notification)
            for device in devices
        ]
    
    def get_sent(self) -> List[Tuple[Device, Notification]]:
        return self._sent.copy()
    
    def clear(self) -> None:
        self._sent.clear()


# Device store
class DeviceStore(ABC):
    """Device registration store."""
    
    @abstractmethod
    async def register(self, device: Device) -> None:
        """Register device."""
        pass
    
    @abstractmethod
    async def get(self, device_id: str) -> Optional[Device]:
        """Get device by ID."""
        pass
    
    @abstractmethod
    async def get_by_token(self, token: str) -> Optional[Device]:
        """Get device by token."""
        pass
    
    @abstractmethod
    async def get_by_user(self, user_id: str) -> List[Device]:
        """Get devices by user ID."""
        pass
    
    @abstractmethod
    async def update(self, device: Device) -> None:
        """Update device."""
        pass
    
    @abstractmethod
    async def delete(self, device_id: str) -> bool:
        """Delete device."""
        pass
    
    @abstractmethod
    async def delete_by_token(self, token: str) -> bool:
        """Delete device by token."""
        pass


class InMemoryDeviceStore(DeviceStore):
    """In-memory device store."""
    
    def __init__(self):
        self._devices: Dict[str, Device] = {}
        self._by_token: Dict[str, str] = {}
        self._by_user: Dict[str, Set[str]] = defaultdict(set)
    
    async def register(self, device: Device) -> None:
        self._devices[device.id] = device
        self._by_token[device.token] = device.id
        self._by_user[device.user_id].add(device.id)
    
    async def get(self, device_id: str) -> Optional[Device]:
        return self._devices.get(device_id)
    
    async def get_by_token(self, token: str) -> Optional[Device]:
        device_id = self._by_token.get(token)
        if device_id:
            return self._devices.get(device_id)
        return None
    
    async def get_by_user(self, user_id: str) -> List[Device]:
        device_ids = self._by_user.get(user_id, set())
        return [
            self._devices[did]
            for did in device_ids
            if did in self._devices
        ]
    
    async def update(self, device: Device) -> None:
        device.last_active_at = datetime.utcnow()
        self._devices[device.id] = device
    
    async def delete(self, device_id: str) -> bool:
        if device_id in self._devices:
            device = self._devices[device_id]
            del self._devices[device_id]
            self._by_token.pop(device.token, None)
            self._by_user[device.user_id].discard(device_id)
            return True
        return False
    
    async def delete_by_token(self, token: str) -> bool:
        device_id = self._by_token.get(token)
        if device_id:
            return await self.delete(device_id)
        return False


# Template engine
class NotificationTemplateEngine(ABC):
    """Notification template engine."""
    
    @abstractmethod
    def render(
        self,
        template: str,
        context: Dict[str, Any],
    ) -> str:
        """Render template."""
        pass


class SimpleTemplateEngine(NotificationTemplateEngine):
    """Simple template engine."""
    
    def __init__(
        self,
        templates: Optional[Dict[str, str]] = None,
    ):
        self._templates = templates or {}
    
    def add_template(self, name: str, content: str) -> None:
        self._templates[name] = content
    
    def render(
        self,
        template: str,
        context: Dict[str, Any],
    ) -> str:
        if template in self._templates:
            template = self._templates[template]
        
        result = template
        for key, value in context.items():
            result = result.replace(f"{{{{{key}}}}}", str(value))
        
        return result


class PushService:
    """
    Push notification service.
    """
    
    def __init__(
        self,
        providers: Dict[str, PushProvider],
        device_store: Optional[DeviceStore] = None,
        template_engine: Optional[NotificationTemplateEngine] = None,
    ):
        self._providers = providers
        self._device_store = device_store or InMemoryDeviceStore()
        self._template_engine = template_engine or SimpleTemplateEngine()
        
        # Build platform to provider mapping
        self._platform_providers: Dict[Platform, PushProvider] = {}
        for name, provider in providers.items():
            self._platform_providers[provider.platform] = provider
    
    def add_template(self, name: str, content: str) -> None:
        """Add notification template."""
        if isinstance(self._template_engine, SimpleTemplateEngine):
            self._template_engine.add_template(name, content)
    
    # Device management
    async def register_device(
        self,
        user_id: str,
        device_token: str,
        platform: Union[str, Platform],
        app_version: str = "",
        os_version: str = "",
        device_model: str = "",
        locale: str = "en",
        timezone: str = "UTC",
        tags: Optional[Dict[str, str]] = None,
    ) -> Device:
        """Register device for push notifications."""
        if isinstance(platform, str):
            platform = Platform(platform)
        
        # Check if device already exists
        existing = await self._device_store.get_by_token(device_token)
        
        if existing:
            # Update existing device
            existing.user_id = user_id
            existing.platform = platform
            existing.app_version = app_version
            existing.os_version = os_version
            existing.device_model = device_model
            existing.locale = locale
            existing.timezone = timezone
            existing.active = True
            if tags:
                existing.tags.update(tags)
            
            await self._device_store.update(existing)
            return existing
        
        # Create new device
        device = Device(
            user_id=user_id,
            token=device_token,
            platform=platform,
            app_version=app_version,
            os_version=os_version,
            device_model=device_model,
            locale=locale,
            timezone=timezone,
            tags=tags or {},
        )
        
        await self._device_store.register(device)
        return device
    
    async def unregister_device(
        self,
        device_token: str,
    ) -> bool:
        """Unregister device."""
        return await self._device_store.delete_by_token(device_token)
    
    async def get_user_devices(
        self,
        user_id: str,
    ) -> List[Device]:
        """Get user's registered devices."""
        return await self._device_store.get_by_user(user_id)
    
    # Sending notifications
    async def send(
        self,
        user_id: str,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        image_url: str = "",
        priority: NotificationPriority = NotificationPriority.NORMAL,
        **kwargs,
    ) -> BulkResult:
        """
        Send notification to user's devices.
        
        Args:
            user_id: Target user ID
            title: Notification title
            body: Notification body
            data: Custom data payload
            image_url: Image URL
            priority: Notification priority
            **kwargs: Additional notification options
            
        Returns:
            Bulk result with delivery status
        """
        notification = Notification(
            title=title,
            body=body,
            data=data or {},
            image_url=image_url,
            priority=priority,
            **kwargs,
        )
        
        devices = await self._device_store.get_by_user(user_id)
        devices = [d for d in devices if d.active]
        
        if not devices:
            return BulkResult(
                notification_id=notification.id,
                total=0,
                success_count=0,
                failure_count=0,
            )
        
        return await self._send_to_devices(devices, notification)
    
    async def send_to_device(
        self,
        device_token: str,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> DeliveryResult:
        """Send notification to specific device."""
        device = await self._device_store.get_by_token(device_token)
        
        if not device:
            raise DeviceNotFoundError(f"Device not found: {device_token}")
        
        notification = Notification(
            title=title,
            body=body,
            data=data or {},
            **kwargs,
        )
        
        provider = self._platform_providers.get(device.platform)
        
        if not provider:
            return DeliveryResult(
                notification_id=notification.id,
                device_id=device.id,
                success=False,
                status=DeliveryStatus.FAILED,
                error=f"No provider for platform: {device.platform}",
            )
        
        return await provider.send(device, notification)
    
    async def send_template(
        self,
        user_id: str,
        template: str,
        context: Dict[str, Any],
        title_template: Optional[str] = None,
        **kwargs,
    ) -> BulkResult:
        """
        Send notification using template.
        
        Args:
            user_id: Target user ID
            template: Body template name or content
            context: Template context
            title_template: Title template
            **kwargs: Additional notification options
            
        Returns:
            Bulk result
        """
        body = self._template_engine.render(template, context)
        
        title = kwargs.get("title", "")
        if title_template:
            title = self._template_engine.render(title_template, context)
        
        return await self.send(
            user_id=user_id,
            title=title,
            body=body,
            **kwargs,
        )
    
    async def broadcast(
        self,
        title: str,
        body: str,
        platform: Optional[Platform] = None,
        data: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> BulkResult:
        """
        Broadcast notification to all devices.
        
        Args:
            title: Notification title
            body: Notification body
            platform: Optional platform filter
            data: Custom data payload
            **kwargs: Additional notification options
            
        Returns:
            Bulk result
        """
        # Would implement with pagination in real implementation
        # For now, this is a placeholder
        notification = Notification(
            title=title,
            body=body,
            data=data or {},
            **kwargs,
        )
        
        return BulkResult(
            notification_id=notification.id,
            total=0,
            success_count=0,
            failure_count=0,
        )
    
    async def _send_to_devices(
        self,
        devices: List[Device],
        notification: Notification,
    ) -> BulkResult:
        """Send notification to multiple devices."""
        results = []
        
        # Group by platform
        by_platform: Dict[Platform, List[Device]] = defaultdict(list)
        for device in devices:
            by_platform[device.platform].append(device)
        
        # Send to each platform
        for platform, platform_devices in by_platform.items():
            provider = self._platform_providers.get(platform)
            
            if not provider:
                for device in platform_devices:
                    results.append(DeliveryResult(
                        notification_id=notification.id,
                        device_id=device.id,
                        success=False,
                        status=DeliveryStatus.FAILED,
                        error=f"No provider for platform: {platform}",
                    ))
                continue
            
            batch_results = await provider.send_batch(
                platform_devices,
                notification,
            )
            results.extend(batch_results)
        
        success_count = sum(1 for r in results if r.success)
        
        return BulkResult(
            notification_id=notification.id,
            total=len(results),
            success_count=success_count,
            failure_count=len(results) - success_count,
            results=results,
        )


# Decorators
def push_notification(
    title: str,
    body_template: str,
    service: Optional[PushService] = None,
) -> Callable:
    """Decorator to send push notification after function."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            
            if service and isinstance(result, dict):
                user_id = result.get("user_id")
                if user_id:
                    await service.send_template(
                        user_id=user_id,
                        template=body_template,
                        context=result,
                        title=title,
                    )
            
            return result
        return wrapper
    return decorator


# Factory functions
def create_push_service(
    providers: Dict[str, PushProvider],
    device_store: Optional[DeviceStore] = None,
    template_engine: Optional[NotificationTemplateEngine] = None,
) -> PushService:
    """Create push notification service."""
    return PushService(
        providers=providers,
        device_store=device_store,
        template_engine=template_engine,
    )


def create_fcm_provider(
    api_key: str,
    project_id: str = "",
) -> FCMProvider:
    """Create FCM provider."""
    return FCMProvider(api_key, project_id)


def create_apns_provider(
    key_file: str = "",
    key_id: str = "",
    team_id: str = "",
    bundle_id: str = "",
    use_sandbox: bool = False,
) -> APNSProvider:
    """Create APNS provider."""
    return APNSProvider(
        key_file=key_file,
        key_id=key_id,
        team_id=team_id,
        bundle_id=bundle_id,
        use_sandbox=use_sandbox,
    )


def create_web_push_provider(
    vapid_private_key: str = "",
    vapid_public_key: str = "",
    vapid_subject: str = "",
) -> WebPushProvider:
    """Create Web Push provider."""
    return WebPushProvider(
        vapid_private_key=vapid_private_key,
        vapid_public_key=vapid_public_key,
        vapid_subject=vapid_subject,
    )


def create_mock_provider(
    platform: Platform = Platform.ANDROID,
) -> MockProvider:
    """Create mock provider for testing."""
    return MockProvider(platform)


def create_in_memory_device_store() -> InMemoryDeviceStore:
    """Create in-memory device store."""
    return InMemoryDeviceStore()


def create_template_engine(
    templates: Optional[Dict[str, str]] = None,
) -> SimpleTemplateEngine:
    """Create template engine."""
    return SimpleTemplateEngine(templates)


def create_notification(
    title: str,
    body: str,
    data: Optional[Dict[str, Any]] = None,
    **kwargs,
) -> Notification:
    """Create notification object."""
    return Notification(
        title=title,
        body=body,
        data=data or {},
        **kwargs,
    )


__all__ = [
    # Exceptions
    "PushError",
    "DeviceNotFoundError",
    "DeliveryError",
    # Enums
    "Platform",
    "NotificationPriority",
    "DeliveryStatus",
    # Data classes
    "Device",
    "Notification",
    "DeliveryResult",
    "BulkResult",
    # Providers
    "PushProvider",
    "FCMProvider",
    "APNSProvider",
    "WebPushProvider",
    "MockProvider",
    # Device store
    "DeviceStore",
    "InMemoryDeviceStore",
    # Template engine
    "NotificationTemplateEngine",
    "SimpleTemplateEngine",
    # Service
    "PushService",
    # Decorators
    "push_notification",
    # Factory functions
    "create_push_service",
    "create_fcm_provider",
    "create_apns_provider",
    "create_web_push_provider",
    "create_mock_provider",
    "create_in_memory_device_store",
    "create_template_engine",
    "create_notification",
]
