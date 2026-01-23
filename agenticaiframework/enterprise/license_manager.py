"""
Enterprise License Manager Module.

License tracking, usage monitoring, compliance,
and license expiration management.

Example:
    # Create license manager
    licenses = create_license_manager()
    
    # Add license
    license = await licenses.add(
        name="enterprise_api",
        license_type=LicenseType.SUBSCRIPTION,
        seats=100,
        expires_at=datetime(2025, 12, 31),
    )
    
    # Check out seat
    await licenses.checkout(
        license_name="enterprise_api",
        user_id="user123",
    )
    
    # Check compliance
    report = await licenses.check_compliance()
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
import uuid
from abc import ABC, abstractmethod
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
    Union,
)

logger = logging.getLogger(__name__)


class LicenseError(Exception):
    """License error."""
    pass


class LicenseExpired(LicenseError):
    """License expired."""
    pass


class NoSeatsAvailable(LicenseError):
    """No seats available."""
    pass


class LicenseType(str, Enum):
    """License type."""
    PERPETUAL = "perpetual"
    SUBSCRIPTION = "subscription"
    TRIAL = "trial"
    EVALUATION = "evaluation"
    OPEN_SOURCE = "open_source"
    CONCURRENT = "concurrent"
    NAMED_USER = "named_user"
    SITE = "site"


class LicenseStatus(str, Enum):
    """License status."""
    ACTIVE = "active"
    EXPIRED = "expired"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    PENDING = "pending"


class UsageEventType(str, Enum):
    """Usage event type."""
    CHECKOUT = "checkout"
    CHECKIN = "checkin"
    ACCESS = "access"
    FEATURE_USE = "feature_use"
    OVERAGE = "overage"


@dataclass
class UsageEvent:
    """License usage event."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    license_id: str = ""
    event_type: UsageEventType = UsageEventType.ACCESS
    user_id: str = ""
    feature: str = ""
    quantity: int = 1
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LicenseKey:
    """License key."""
    key: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    activated_at: Optional[datetime] = None
    machine_id: str = ""
    valid: bool = True


@dataclass
class License:
    """License."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    license_type: LicenseType = LicenseType.SUBSCRIPTION
    status: LicenseStatus = LicenseStatus.ACTIVE
    
    # Keys
    license_key: Optional[LicenseKey] = None
    
    # Limits
    seats: Optional[int] = None  # None = unlimited
    max_usage: Optional[int] = None
    
    # Features
    features: List[str] = field(default_factory=list)
    restrictions: Dict[str, Any] = field(default_factory=dict)
    
    # Users
    active_users: Set[str] = field(default_factory=set)
    
    # Dates
    issued_at: datetime = field(default_factory=datetime.utcnow)
    starts_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    
    # Vendor
    vendor: str = ""
    product: str = ""
    version: str = ""
    
    # Usage
    usage_count: int = 0
    
    # Metadata
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at
    
    @property
    def is_active(self) -> bool:
        return self.status == LicenseStatus.ACTIVE and not self.is_expired
    
    @property
    def available_seats(self) -> Optional[int]:
        if self.seats is None:
            return None
        return max(0, self.seats - len(self.active_users))
    
    @property
    def days_until_expiry(self) -> Optional[int]:
        if self.expires_at is None:
            return None
        delta = self.expires_at - datetime.utcnow()
        return max(0, delta.days)


@dataclass
class ComplianceIssue:
    """Compliance issue."""
    license_id: str = ""
    license_name: str = ""
    issue_type: str = ""
    severity: str = "warning"
    message: str = ""
    detected_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ComplianceReport:
    """Compliance report."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    generated_at: datetime = field(default_factory=datetime.utcnow)
    total_licenses: int = 0
    active_licenses: int = 0
    expired_licenses: int = 0
    compliant: bool = True
    issues: List[ComplianceIssue] = field(default_factory=list)
    usage_summary: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LicenseStats:
    """License statistics."""
    total_licenses: int = 0
    active_licenses: int = 0
    expired_licenses: int = 0
    total_seats: int = 0
    used_seats: int = 0
    by_type: Dict[str, int] = field(default_factory=dict)
    expiring_soon: List[str] = field(default_factory=list)


# License store
class LicenseStore(ABC):
    """License storage."""
    
    @abstractmethod
    async def save(self, license: License) -> None:
        pass
    
    @abstractmethod
    async def get(self, license_id: str) -> Optional[License]:
        pass
    
    @abstractmethod
    async def get_by_name(self, name: str) -> Optional[License]:
        pass
    
    @abstractmethod
    async def list_all(self) -> List[License]:
        pass
    
    @abstractmethod
    async def delete(self, license_id: str) -> bool:
        pass


class InMemoryLicenseStore(LicenseStore):
    """In-memory license store."""
    
    def __init__(self):
        self._licenses: Dict[str, License] = {}
        self._by_name: Dict[str, str] = {}
    
    async def save(self, license: License) -> None:
        self._licenses[license.id] = license
        self._by_name[license.name] = license.id
    
    async def get(self, license_id: str) -> Optional[License]:
        return self._licenses.get(license_id)
    
    async def get_by_name(self, name: str) -> Optional[License]:
        license_id = self._by_name.get(name)
        if license_id:
            return self._licenses.get(license_id)
        return None
    
    async def list_all(self) -> List[License]:
        return list(self._licenses.values())
    
    async def delete(self, license_id: str) -> bool:
        license = self._licenses.get(license_id)
        if license:
            del self._licenses[license_id]
            self._by_name.pop(license.name, None)
            return True
        return False


# Usage store
class UsageStore(ABC):
    """Usage event storage."""
    
    @abstractmethod
    async def save(self, event: UsageEvent) -> None:
        pass
    
    @abstractmethod
    async def list_by_license(
        self,
        license_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[UsageEvent]:
        pass
    
    @abstractmethod
    async def get_usage_count(
        self,
        license_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> int:
        pass


class InMemoryUsageStore(UsageStore):
    """In-memory usage store."""
    
    def __init__(self, max_events: int = 100000):
        self._events: Dict[str, UsageEvent] = {}
        self._by_license: Dict[str, List[str]] = {}
        self._max_events = max_events
    
    async def save(self, event: UsageEvent) -> None:
        self._events[event.id] = event
        
        if event.license_id not in self._by_license:
            self._by_license[event.license_id] = []
        
        self._by_license[event.license_id].append(event.id)
        
        # Trim
        if len(self._events) > self._max_events:
            oldest = list(self._events.keys())[0]
            del self._events[oldest]
    
    async def list_by_license(
        self,
        license_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[UsageEvent]:
        event_ids = self._by_license.get(license_id, [])
        events = []
        
        for event_id in event_ids:
            event = self._events.get(event_id)
            if event:
                if start_date and event.timestamp < start_date:
                    continue
                if end_date and event.timestamp > end_date:
                    continue
                events.append(event)
        
        return sorted(events, key=lambda e: e.timestamp, reverse=True)
    
    async def get_usage_count(
        self,
        license_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> int:
        events = await self.list_by_license(license_id, start_date, end_date)
        return sum(e.quantity for e in events)


# License key generator
class LicenseKeyGenerator:
    """License key generator."""
    
    @staticmethod
    def generate(
        license_id: str,
        secret: str = "default_secret",
        segments: int = 4,
        segment_length: int = 4,
    ) -> str:
        """Generate license key."""
        data = f"{license_id}:{secret}:{time.time()}"
        hash_bytes = hashlib.sha256(data.encode()).hexdigest()
        
        key_parts = []
        for i in range(segments):
            start = i * segment_length
            key_parts.append(hash_bytes[start:start + segment_length].upper())
        
        return "-".join(key_parts)
    
    @staticmethod
    def validate(
        key: str,
        min_segments: int = 4,
        segment_length: int = 4,
    ) -> bool:
        """Validate license key format."""
        parts = key.split("-")
        
        if len(parts) < min_segments:
            return False
        
        for part in parts:
            if len(part) != segment_length:
                return False
            if not all(c.isalnum() for c in part):
                return False
        
        return True


# License manager
class LicenseManager:
    """License manager."""
    
    def __init__(
        self,
        license_store: Optional[LicenseStore] = None,
        usage_store: Optional[UsageStore] = None,
    ):
        self._license_store = license_store or InMemoryLicenseStore()
        self._usage_store = usage_store or InMemoryUsageStore()
        self._key_generator = LicenseKeyGenerator()
        self._alert_handlers: List[Callable] = []
        self._expiry_threshold_days = 30
    
    async def add(
        self,
        name: str,
        license_type: Union[str, LicenseType] = LicenseType.SUBSCRIPTION,
        seats: Optional[int] = None,
        expires_at: Optional[datetime] = None,
        features: Optional[List[str]] = None,
        generate_key: bool = True,
        **metadata,
    ) -> License:
        """Add license."""
        if isinstance(license_type, str):
            license_type = LicenseType(license_type)
        
        license = License(
            name=name,
            license_type=license_type,
            seats=seats,
            expires_at=expires_at,
            features=features or [],
            metadata=metadata,
        )
        
        if generate_key:
            key = self._key_generator.generate(license.id)
            license.license_key = LicenseKey(
                key=key,
                activated_at=datetime.utcnow(),
            )
        
        await self._license_store.save(license)
        
        logger.info(f"License added: {name} ({license_type.value})")
        
        return license
    
    async def get(self, name: str) -> Optional[License]:
        """Get license by name."""
        return await self._license_store.get_by_name(name)
    
    async def get_by_id(self, license_id: str) -> Optional[License]:
        """Get license by ID."""
        return await self._license_store.get(license_id)
    
    async def update(
        self,
        name: str,
        **updates,
    ) -> Optional[License]:
        """Update license."""
        license = await self._license_store.get_by_name(name)
        
        if not license:
            return None
        
        for key, value in updates.items():
            if hasattr(license, key):
                setattr(license, key, value)
        
        await self._license_store.save(license)
        
        return license
    
    async def delete(self, name: str) -> bool:
        """Delete license."""
        license = await self._license_store.get_by_name(name)
        
        if license:
            return await self._license_store.delete(license.id)
        
        return False
    
    async def list_licenses(self) -> List[License]:
        """List all licenses."""
        return await self._license_store.list_all()
    
    async def checkout(
        self,
        license_name: str,
        user_id: str,
        feature: str = "",
    ) -> bool:
        """Check out license seat."""
        license = await self._license_store.get_by_name(license_name)
        
        if not license:
            raise LicenseError(f"License not found: {license_name}")
        
        if not license.is_active:
            if license.is_expired:
                raise LicenseExpired(f"License expired: {license_name}")
            raise LicenseError(f"License not active: {license_name}")
        
        # Check seats
        if license.seats is not None:
            if user_id not in license.active_users:
                if license.available_seats is not None and license.available_seats <= 0:
                    raise NoSeatsAvailable(f"No seats available: {license_name}")
        
        # Add user
        license.active_users.add(user_id)
        license.usage_count += 1
        
        await self._license_store.save(license)
        
        # Record usage
        event = UsageEvent(
            license_id=license.id,
            event_type=UsageEventType.CHECKOUT,
            user_id=user_id,
            feature=feature,
        )
        await self._usage_store.save(event)
        
        logger.debug(f"License checkout: {license_name} -> {user_id}")
        
        return True
    
    async def checkin(
        self,
        license_name: str,
        user_id: str,
    ) -> bool:
        """Check in license seat."""
        license = await self._license_store.get_by_name(license_name)
        
        if not license:
            return False
        
        if user_id in license.active_users:
            license.active_users.remove(user_id)
            await self._license_store.save(license)
            
            event = UsageEvent(
                license_id=license.id,
                event_type=UsageEventType.CHECKIN,
                user_id=user_id,
            )
            await self._usage_store.save(event)
            
            logger.debug(f"License checkin: {license_name} <- {user_id}")
            
            return True
        
        return False
    
    async def verify(
        self,
        license_name: str,
        user_id: Optional[str] = None,
        feature: Optional[str] = None,
    ) -> bool:
        """Verify license is valid."""
        license = await self._license_store.get_by_name(license_name)
        
        if not license:
            return False
        
        if not license.is_active:
            return False
        
        # Check feature
        if feature and license.features:
            if feature not in license.features:
                return False
        
        # Check user for named user license
        if license.license_type == LicenseType.NAMED_USER:
            if user_id and user_id not in license.active_users:
                return False
        
        return True
    
    async def has_feature(
        self,
        license_name: str,
        feature: str,
    ) -> bool:
        """Check if license has feature."""
        license = await self._license_store.get_by_name(license_name)
        
        if not license or not license.is_active:
            return False
        
        if not license.features:
            return True  # No restrictions
        
        return feature in license.features
    
    async def record_usage(
        self,
        license_name: str,
        user_id: str = "",
        feature: str = "",
        quantity: int = 1,
    ) -> None:
        """Record usage event."""
        license = await self._license_store.get_by_name(license_name)
        
        if not license:
            return
        
        event = UsageEvent(
            license_id=license.id,
            event_type=UsageEventType.ACCESS,
            user_id=user_id,
            feature=feature,
            quantity=quantity,
        )
        
        await self._usage_store.save(event)
        
        # Update usage count
        license.usage_count += quantity
        await self._license_store.save(license)
    
    async def get_usage(
        self,
        license_name: str,
        period_days: int = 30,
    ) -> Dict[str, Any]:
        """Get license usage."""
        license = await self._license_store.get_by_name(license_name)
        
        if not license:
            return {}
        
        start_date = datetime.utcnow() - timedelta(days=period_days)
        events = await self._usage_store.list_by_license(
            license.id,
            start_date=start_date,
        )
        
        by_type: Dict[str, int] = {}
        by_user: Dict[str, int] = {}
        by_feature: Dict[str, int] = {}
        
        for event in events:
            # By type
            event_type = event.event_type.value
            by_type[event_type] = by_type.get(event_type, 0) + event.quantity
            
            # By user
            if event.user_id:
                by_user[event.user_id] = by_user.get(event.user_id, 0) + event.quantity
            
            # By feature
            if event.feature:
                by_feature[event.feature] = by_feature.get(event.feature, 0) + event.quantity
        
        return {
            "license_name": license_name,
            "period_days": period_days,
            "total_events": len(events),
            "total_usage": sum(e.quantity for e in events),
            "by_type": by_type,
            "by_user": by_user,
            "by_feature": by_feature,
            "active_users": list(license.active_users),
        }
    
    async def check_compliance(self) -> ComplianceReport:
        """Check license compliance."""
        licenses = await self._license_store.list_all()
        
        report = ComplianceReport(
            total_licenses=len(licenses),
        )
        
        now = datetime.utcnow()
        
        for license in licenses:
            # Check active
            if license.is_active:
                report.active_licenses += 1
            
            # Check expired
            if license.is_expired:
                report.expired_licenses += 1
                report.issues.append(ComplianceIssue(
                    license_id=license.id,
                    license_name=license.name,
                    issue_type="expired",
                    severity="critical",
                    message=f"License expired on {license.expires_at}",
                ))
            
            # Check expiring soon
            elif license.days_until_expiry is not None:
                if license.days_until_expiry <= self._expiry_threshold_days:
                    report.issues.append(ComplianceIssue(
                        license_id=license.id,
                        license_name=license.name,
                        issue_type="expiring_soon",
                        severity="warning",
                        message=f"License expires in {license.days_until_expiry} days",
                    ))
            
            # Check seat overuse
            if license.seats is not None:
                used = len(license.active_users)
                if used > license.seats:
                    report.issues.append(ComplianceIssue(
                        license_id=license.id,
                        license_name=license.name,
                        issue_type="seat_overage",
                        severity="critical",
                        message=f"Using {used} seats but only {license.seats} licensed",
                    ))
            
            # Check usage limits
            if license.max_usage is not None:
                if license.usage_count > license.max_usage:
                    report.issues.append(ComplianceIssue(
                        license_id=license.id,
                        license_name=license.name,
                        issue_type="usage_overage",
                        severity="warning",
                        message=f"Usage {license.usage_count} exceeds limit {license.max_usage}",
                    ))
        
        # Determine overall compliance
        critical_issues = [i for i in report.issues if i.severity == "critical"]
        report.compliant = len(critical_issues) == 0
        
        return report
    
    async def get_expiring_licenses(
        self,
        days: int = 30,
    ) -> List[License]:
        """Get licenses expiring within days."""
        licenses = await self._license_store.list_all()
        expiring = []
        
        for license in licenses:
            if license.days_until_expiry is not None:
                if license.days_until_expiry <= days:
                    expiring.append(license)
        
        return sorted(expiring, key=lambda l: l.expires_at or datetime.max)
    
    async def get_stats(self) -> LicenseStats:
        """Get license statistics."""
        licenses = await self._license_store.list_all()
        
        stats = LicenseStats(
            total_licenses=len(licenses),
        )
        
        for license in licenses:
            # By status
            if license.is_active:
                stats.active_licenses += 1
            if license.is_expired:
                stats.expired_licenses += 1
            
            # By type
            ltype = license.license_type.value
            stats.by_type[ltype] = stats.by_type.get(ltype, 0) + 1
            
            # Seats
            if license.seats:
                stats.total_seats += license.seats
                stats.used_seats += len(license.active_users)
            
            # Expiring soon
            if license.days_until_expiry is not None:
                if license.days_until_expiry <= self._expiry_threshold_days:
                    stats.expiring_soon.append(license.name)
        
        return stats
    
    def add_alert_handler(self, handler: Callable) -> None:
        """Add alert handler."""
        self._alert_handlers.append(handler)


# Factory functions
def create_license_manager() -> LicenseManager:
    """Create license manager."""
    return LicenseManager()


def create_license(
    name: str,
    license_type: LicenseType = LicenseType.SUBSCRIPTION,
    **kwargs,
) -> License:
    """Create license."""
    return License(name=name, license_type=license_type, **kwargs)


__all__ = [
    # Exceptions
    "LicenseError",
    "LicenseExpired",
    "NoSeatsAvailable",
    # Enums
    "LicenseType",
    "LicenseStatus",
    "UsageEventType",
    # Data classes
    "UsageEvent",
    "LicenseKey",
    "License",
    "ComplianceIssue",
    "ComplianceReport",
    "LicenseStats",
    # Stores
    "LicenseStore",
    "InMemoryLicenseStore",
    "UsageStore",
    "InMemoryUsageStore",
    # Utilities
    "LicenseKeyGenerator",
    # Manager
    "LicenseManager",
    # Factory functions
    "create_license_manager",
    "create_license",
]
