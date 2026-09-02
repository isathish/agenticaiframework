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
    """Firebase Cloud Messaging provider.

    Uses the FCM HTTP v1 API when a service account is supplied (``service_account``
    = path to JSON, JSON string, dict, or ``ServiceAccountCredentials``); falls
    back to the legacy ``fcm/send`` endpoint when only a server ``api_key`` is given.
    """
    
    _SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
    
    def __init__(
        self,
        api_key: str = "",
        project_id: str = "",
        service_account: Any = None,
        timeout: float = 30.0,
    ):
        self._api_key = api_key
        self._project_id = project_id
        self._timeout = timeout
        self._creds = None
        if service_account is not None or (not api_key and __import__("os").environ.get("GOOGLE_APPLICATION_CREDENTIALS")):
            self._creds = self._load_credentials(service_account)
            if not self._project_id and self._creds is not None:
                self._project_id = self._creds.project_id or ""
    
    @staticmethod
    def _load_credentials(source: Any):
        import json as _json
        import os as _os

        from .._internal.clients.gcp_rest import ServiceAccountCredentials

        if source is None:
            return ServiceAccountCredentials.from_env()
        if isinstance(source, ServiceAccountCredentials):
            return source
        if isinstance(source, dict):
            return ServiceAccountCredentials.from_info(source)
        text = str(source).strip()
        if text.startswith("{"):
            return ServiceAccountCredentials.from_info(_json.loads(text))
        if _os.path.exists(text):
            return ServiceAccountCredentials.from_file(text)
        raise PushError("service_account must be a path, JSON string, dict or ServiceAccountCredentials")
    
    @property
    def platform(self) -> Platform:
        return Platform.ANDROID
    
    def _v1_message(self, device: Device, notification: Notification) -> Dict[str, Any]:
        android: Dict[str, Any] = {
            "priority": "high" if notification.priority == NotificationPriority.HIGH else "normal",
            "ttl": f"{int(notification.ttl)}s",
        }
        if notification.collapse_key:
            android["collapse_key"] = notification.collapse_key
        android_notif: Dict[str, Any] = {}
        if notification.channel_id:
            android_notif["channel_id"] = notification.channel_id
        if notification.sound:
            android_notif["sound"] = notification.sound
        if notification.icon:
            android_notif["icon"] = notification.icon
        if notification.image_url:
            android_notif["image"] = notification.image_url
        if android_notif:
            android["notification"] = android_notif
        
        notif: Dict[str, Any] = {"title": notification.title, "body": notification.body}
        if notification.image_url:
            notif["image"] = notification.image_url
        
        return {
            "message": {
                "token": device.token,
                "notification": notif,
                "data": {str(k): str(v) for k, v in (notification.data or {}).items()},
                "android": android,
            }
        }
    
    async def send(
        self,
        device: Device,
        notification: Notification,
    ) -> DeliveryResult:
        """Send via FCM (HTTP v1 when credentials are available)."""
        try:
            from .._internal import http as _http

            if self._creds is not None:
                if not self._project_id:
                    raise PushError("FCM project_id is required for the HTTP v1 API")
                token = await asyncio.to_thread(self._creds.access_token, [self._SCOPE])
                url = f"https://fcm.googleapis.com/v1/projects/{self._project_id}/messages:send"
                payload = self._v1_message(device, notification)
                headers = {"Authorization": f"Bearer {token}"}
            else:
                if not self._api_key:
                    raise PushError("FCMProvider requires api_key or service_account")
                url = "https://fcm.googleapis.com/fcm/send"
                payload = {
                    "to": device.token,
                    "priority": "high" if notification.priority == NotificationPriority.HIGH else "normal",
                    "time_to_live": int(notification.ttl),
                    "notification": {
                        "title": notification.title,
                        "body": notification.body,
                        "image": notification.image_url or None,
                        "sound": notification.sound or None,
                    },
                    "data": notification.data or {},
                }
                headers = {"Authorization": f"key={self._api_key}"}
            
            client = _http.Client(timeout=self._timeout)
            resp = await asyncio.to_thread(client.post, url, json=payload, headers=headers)
            success = 200 <= resp.status < 300
            body: Dict[str, Any] = {}
            try:
                body = resp.json() if resp.content else {}
            except ValueError:
                pass
            
            status = DeliveryStatus.SENT
            error = None
            provider_id = None
            if success:
                provider_id = body.get("name") or (body.get("results", [{}])[0].get("message_id") if isinstance(body.get("results"), list) else None)
                # legacy API reports per-token errors inside a 200 response
                if isinstance(body.get("results"), list) and body["results"] and body["results"][0].get("error"):
                    success = False
                    error = body["results"][0]["error"]
            if not success:
                err_obj = body.get("error", {}) if isinstance(body.get("error"), dict) else {}
                error = error or err_obj.get("message") or resp.text[:500]
                details = err_obj.get("details", [])
                fcm_code = next((d.get("errorCode") for d in details if isinstance(d, dict) and d.get("errorCode")), None)
                status = DeliveryStatus.FAILED
                if fcm_code in ("UNREGISTERED", "INVALID_ARGUMENT") or error in ("NotRegistered", "InvalidRegistration") or resp.status == 404:
                    status = DeliveryStatus.INVALID_TOKEN
            
            logger.info("FCM send notif=%s device=%s status=%s", notification.id, device.id, resp.status)
            return DeliveryResult(
                notification_id=notification.id,
                device_id=device.id,
                success=success,
                status=status,
                provider_id=provider_id or (f"fcm-{uuid.uuid4().hex[:16]}" if success else None),
                error=error,
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
        """Send batch via FCM (concurrent, bounded)."""
        sem = asyncio.Semaphore(16)
        
        async def _one(d: Device) -> DeliveryResult:
            async with sem:
                return await self.send(d, notification)
        
        return list(await asyncio.gather(*(_one(d) for d in devices)))


class APNSProvider(PushProvider):
    """Apple Push Notification Service provider (token-based auth).

    Signs provider JWTs with the ``.p8`` key using ES256 (as Apple requires) and
    talks to APNs over HTTP/2 via :mod:`agenticaiframework._internal.h2`.
    """
    
    _TOKEN_TTL = 50 * 60  # Apple: refresh at least hourly, no more than every 20 min
    
    def __init__(
        self,
        key_file: str = "",
        key_id: str = "",
        team_id: str = "",
        bundle_id: str = "",
        use_sandbox: bool = False,
        key_pem: str = "",
        timeout: float = 30.0,
    ):
        self._key_file = key_file
        self._key_pem = key_pem
        self._key_id = key_id
        self._team_id = team_id
        self._bundle_id = bundle_id
        self._use_sandbox = use_sandbox
        self._timeout = timeout
        self._token: Optional[str] = None
        self._token_issued: float = 0.0
        self._lock = asyncio.Lock()
    
    @property
    def platform(self) -> Platform:
        return Platform.IOS
    
    @property
    def host(self) -> str:
        return "api.sandbox.push.apple.com" if self._use_sandbox else "api.push.apple.com"
    
    def _load_key(self) -> str:
        if self._key_pem:
            return self._key_pem
        if not self._key_file:
            raise PushError("APNSProvider requires key_file or key_pem")
        with open(self._key_file, "r", encoding="utf-8") as f:
            return f.read()
    
    async def _provider_token(self) -> str:
        import time as _time

        from .._internal import jwt as _jwt

        async with self._lock:
            now = _time.time()
            if self._token and now - self._token_issued < self._TOKEN_TTL:
                return self._token
            self._token = _jwt.encode(
                {"iss": self._team_id, "iat": int(now)},
                self._load_key(),
                algorithm="ES256",
                headers={"kid": self._key_id},
            )
            self._token_issued = now
            return self._token
    
    def _payload(self, notification: Notification) -> Dict[str, Any]:
        aps: Dict[str, Any] = {
            "alert": {"title": notification.title, "body": notification.body},
        }
        if notification.sound:
            aps["sound"] = notification.sound
        if notification.badge is not None:
            aps["badge"] = notification.badge
        if notification.category:
            aps["category"] = notification.category
        if notification.thread_id:
            aps["thread-id"] = notification.thread_id
        if notification.image_url:
            aps["mutable-content"] = 1
        payload: Dict[str, Any] = {"aps": aps}
        for k, v in (notification.data or {}).items():
            if k != "aps":
                payload[k] = v
        if notification.image_url:
            payload.setdefault("image_url", notification.image_url)
        return payload
    
    async def send(
        self,
        device: Device,
        notification: Notification,
    ) -> DeliveryResult:
        """Send via APNs (HTTP/2, ES256 provider token)."""
        try:
            import json as _json
            import time as _time

            from .._internal import h2 as _h2

            token = await self._provider_token()
            headers = {
                "authorization": f"bearer {token}",
                "apns-topic": self._bundle_id,
                "apns-push-type": "alert",
                "apns-priority": "10" if notification.priority == NotificationPriority.HIGH else "5",
                "apns-expiration": str(int(_time.time()) + int(notification.ttl)),
                "apns-id": notification.id if len(notification.id) == 36 else str(uuid.uuid4()),
                "content-type": "application/json",
            }
            if notification.collapse_key:
                headers["apns-collapse-id"] = notification.collapse_key[:64]
            body = _json.dumps(self._payload(notification), separators=(",", ":")).encode()
            
            resp = await asyncio.to_thread(
                _h2.request, "POST", f"https://{self.host}/3/device/{device.token}",
                headers=headers, body=body, timeout=self._timeout,
            )
            success = resp.ok
            reason = None
            if not success:
                try:
                    reason = (resp.json() or {}).get("reason")
                except ValueError:
                    reason = None
                reason = reason or f"HTTP {resp.status}"
            status = DeliveryStatus.SENT
            if not success:
                status = DeliveryStatus.INVALID_TOKEN if reason in ("BadDeviceToken", "Unregistered", "DeviceTokenNotForTopic") or resp.status == 410 else DeliveryStatus.FAILED
            logger.info("APNS send notif=%s device=%s status=%s reason=%s", notification.id, device.id, resp.status, reason)
            return DeliveryResult(
                notification_id=notification.id,
                device_id=device.id,
                success=success,
                status=status,
                provider_id=resp.headers.get("apns-id") or headers["apns-id"],
                error=reason,
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
        sem = asyncio.Semaphore(8)
        
        async def _one(d: Device) -> DeliveryResult:
            async with sem:
                return await self.send(d, notification)
        
        return list(await asyncio.gather(*(_one(d) for d in devices)))


class WebPushProvider(PushProvider):
    """Web Push provider (RFC 8030 + RFC 8291 ``aes128gcm`` + RFC 8292 VAPID).

    ``Device.token`` must hold the browser ``PushSubscription`` as JSON:
    ``{"endpoint": "...", "keys": {"p256dh": "...", "auth": "..."}}``.
    """
    
    def __init__(
        self,
        vapid_private_key: str = "",
        vapid_public_key: str = "",
        vapid_subject: str = "",
        timeout: float = 30.0,
    ):
        self._vapid_private_key = vapid_private_key
        self._vapid_public_key = vapid_public_key
        self._vapid_subject = vapid_subject
        self._timeout = timeout
    
    @property
    def platform(self) -> Platform:
        return Platform.WEB
    
    @staticmethod
    def generate_vapid_keys() -> Dict[str, str]:
        """Return a fresh ``{"private_key", "public_key"}`` pair (base64url)."""
        import base64 as _b64

        from .._internal import ec as _ec

        priv = _ec.generate_private_key()
        return {
            "private_key": _b64.urlsafe_b64encode(priv.to_bytes()).rstrip(b"=").decode(),
            "public_key": priv.public_key().to_b64url(),
        }
    
    @staticmethod
    def encrypt_payload(plaintext: bytes, p256dh: str, auth: str) -> bytes:
        """RFC 8291 ``aes128gcm`` encryption of ``plaintext`` for a subscription."""
        import base64 as _b64
        import secrets as _secrets
        import struct as _struct

        from .._internal import aes_gcm as _aes_gcm
        from .._internal import ec as _ec

        ua_public = _ec.ECPublicKey.from_b64url(p256dh)
        auth_secret = _b64.urlsafe_b64decode(auth + "=" * (-len(auth) % 4))
        as_priv = _ec.generate_private_key()
        as_public_bytes = as_priv.public_key().to_bytes()
        shared = _ec.ecdh_shared_secret(as_priv, ua_public)
        key_info = b"WebPush: info\x00" + ua_public.to_bytes() + as_public_bytes
        ikm = _ec.hkdf_sha256(auth_secret, shared, key_info, 32)
        salt = _secrets.token_bytes(16)
        cek = _ec.hkdf_sha256(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
        nonce = _ec.hkdf_sha256(salt, ikm, b"Content-Encoding: nonce\x00", 12)
        record_size = 4096
        if len(plaintext) + 1 + 16 > record_size:
            raise PushError("Web Push payload exceeds 4KB record size")
        ciphertext = _aes_gcm.encrypt(cek, nonce, plaintext + b"\x02")
        header = salt + _struct.pack(">I", record_size) + bytes([len(as_public_bytes)]) + as_public_bytes
        return header + ciphertext
    
    def _vapid_headers(self, endpoint: str) -> Dict[str, str]:
        import time as _time
        import urllib.parse as _up

        from .._internal import ec as _ec
        from .._internal import jwt as _jwt

        if not self._vapid_private_key:
            raise PushError("WebPushProvider requires vapid_private_key")
        priv = _ec.load_private_key(self._vapid_private_key)
        pub_b64 = self._vapid_public_key or priv.public_key().to_b64url()
        parsed = _up.urlsplit(endpoint)
        aud = f"{parsed.scheme}://{parsed.netloc}"
        token = _jwt.encode(
            {"aud": aud, "exp": int(_time.time()) + 12 * 3600, "sub": self._vapid_subject or "mailto:admin@example.com"},
            priv, algorithm="ES256",
        )
        return {"Authorization": f"vapid t={token}, k={pub_b64}"}
    
    async def send(
        self,
        device: Device,
        notification: Notification,
    ) -> DeliveryResult:
        """Send via Web Push."""
        try:
            import json as _json

            from .._internal import http as _http

            try:
                sub = _json.loads(device.token)
            except (TypeError, ValueError):
                raise PushError("Web Push device token must be a JSON PushSubscription")
            endpoint = sub.get("endpoint")
            keys = sub.get("keys") or {}
            if not endpoint or not keys.get("p256dh") or not keys.get("auth"):
                raise PushError("PushSubscription requires endpoint, keys.p256dh and keys.auth")
            
            payload = {
                "title": notification.title,
                "body": notification.body,
                "data": notification.data or {},
            }
            if notification.image_url:
                payload["image"] = notification.image_url
            if notification.icon:
                payload["icon"] = notification.icon
            body = self.encrypt_payload(_json.dumps(payload).encode(), keys["p256dh"], keys["auth"])
            headers = {
                "Content-Type": "application/octet-stream",
                "Content-Encoding": "aes128gcm",
                "TTL": str(int(notification.ttl)),
                "Urgency": {"low": "low", "normal": "normal", "high": "high"}[notification.priority.value],
                **self._vapid_headers(endpoint),
            }
            if notification.collapse_key:
                headers["Topic"] = notification.collapse_key[:32]
            
            client = _http.Client(timeout=self._timeout)
            resp = await asyncio.to_thread(client.post, endpoint, data=body, headers=headers)
            success = 200 <= resp.status < 300
            status = DeliveryStatus.SENT
            if not success:
                status = DeliveryStatus.INVALID_TOKEN if resp.status in (404, 410) else DeliveryStatus.FAILED
            logger.info("WebPush send notif=%s device=%s status=%s", notification.id, device.id, resp.status)
            return DeliveryResult(
                notification_id=notification.id,
                device_id=device.id,
                success=success,
                status=status,
                provider_id=resp.headers.get("location") or f"web-{uuid.uuid4().hex[:16]}",
                error=None if success else f"HTTP {resp.status}: {resp.text[:200]}",
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
        sem = asyncio.Semaphore(16)
        
        async def _one(d: Device) -> DeliveryResult:
            async with sem:
                return await self.send(d, notification)
        
        return list(await asyncio.gather(*(_one(d) for d in devices)))


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
    
    async def list_all(
        self,
        platform: Optional[Platform] = None,
        active_only: bool = True,
        offset: int = 0,
        limit: int = 1000,
    ) -> List[Device]:
        """Page through registered devices. Stores should override for efficiency."""
        return []


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
    
    async def list_all(
        self,
        platform: Optional[Platform] = None,
        active_only: bool = True,
        offset: int = 0,
        limit: int = 1000,
    ) -> List[Device]:
        devices = [
            d for d in self._devices.values()
            if (platform is None or d.platform == platform)
            and (not active_only or d.active)
        ]
        devices.sort(key=lambda d: d.created_at)
        return devices[offset:offset + limit]


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
        page_size: int = 500,
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
        notification = Notification(
            title=title,
            body=body,
            data=data or {},
            **kwargs,
        )
        
        results: List[DeliveryResult] = []
        offset = 0
        while True:
            page = await self._device_store.list_all(
                platform=platform, active_only=True, offset=offset, limit=page_size,
            )
            if not page:
                break
            batch = await self._send_to_devices(page, notification)
            results.extend(batch.results)
            # Deactivate devices whose tokens the provider rejected.
            for r in batch.results:
                if r.status == DeliveryStatus.INVALID_TOKEN:
                    device = await self._device_store.get(r.device_id)
                    if device:
                        device.active = False
                        await self._device_store.update(device)
            if len(page) < page_size:
                break
            offset += page_size
        
        success_count = sum(1 for r in results if r.success)
        return BulkResult(
            notification_id=notification.id,
            total=len(results),
            success_count=success_count,
            failure_count=len(results) - success_count,
            results=results,
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
    api_key: str = "",
    project_id: str = "",
    service_account: Any = None,
) -> FCMProvider:
    """Create FCM provider."""
    return FCMProvider(api_key, project_id, service_account=service_account)


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
