"""
Enterprise Booking Engine Module.

Reservation system, availability management,
appointment scheduling, and resource booking.

Example:
    # Create booking engine
    booking = create_booking_engine()
    
    # Add bookable resource
    resource = await booking.add_resource(
        name="Meeting Room A",
        type="room",
        capacity=10,
    )
    
    # Create booking
    reservation = await booking.book(
        resource_id=resource.id,
        user_id="user_123",
        start=datetime(2024, 1, 15, 14, 0),
        end=datetime(2024, 1, 15, 15, 0),
    )
    
    # Check availability
    slots = await booking.get_availability(
        resource_id=resource.id,
        date=date(2024, 1, 15),
        duration=60,
    )
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, date, time
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


class BookingError(Exception):
    """Booking error."""
    pass


class ResourceNotFoundError(BookingError):
    """Resource not found."""
    pass


class SlotUnavailableError(BookingError):
    """Slot unavailable."""
    pass


class BookingStatus(str, Enum):
    """Booking status."""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"


class ResourceType(str, Enum):
    """Resource type."""
    ROOM = "room"
    EQUIPMENT = "equipment"
    VEHICLE = "vehicle"
    PERSON = "person"
    SERVICE = "service"
    TABLE = "table"
    COURT = "court"


class BookingMode(str, Enum):
    """Booking mode."""
    SINGLE = "single"
    RECURRING = "recurring"
    SERIES = "series"


@dataclass
class BusinessHours:
    """Business hours."""
    monday: Tuple[time, time] = (time(9, 0), time(17, 0))
    tuesday: Tuple[time, time] = (time(9, 0), time(17, 0))
    wednesday: Tuple[time, time] = (time(9, 0), time(17, 0))
    thursday: Tuple[time, time] = (time(9, 0), time(17, 0))
    friday: Tuple[time, time] = (time(9, 0), time(17, 0))
    saturday: Optional[Tuple[time, time]] = None
    sunday: Optional[Tuple[time, time]] = None
    
    def get_hours(self, weekday: int) -> Optional[Tuple[time, time]]:
        """Get hours for weekday (0=Monday)."""
        days = [
            self.monday, self.tuesday, self.wednesday,
            self.thursday, self.friday, self.saturday, self.sunday
        ]
        return days[weekday] if weekday < 7 else None


@dataclass
class Resource:
    """Bookable resource."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    type: ResourceType = ResourceType.ROOM
    description: str = ""
    capacity: int = 1
    location: str = ""
    price_per_hour: float = 0.0
    currency: str = "USD"
    min_duration: int = 30  # minutes
    max_duration: int = 480  # minutes (8 hours)
    buffer_before: int = 0  # minutes
    buffer_after: int = 0  # minutes
    business_hours: BusinessHours = field(default_factory=BusinessHours)
    requires_approval: bool = False
    max_advance_days: int = 90
    amenities: List[str] = field(default_factory=list)
    images: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Booking:
    """Booking reservation."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    resource_id: str = ""
    user_id: str = ""
    title: str = ""
    notes: str = ""
    start: datetime = field(default_factory=datetime.utcnow)
    end: datetime = field(default_factory=datetime.utcnow)
    status: BookingStatus = BookingStatus.PENDING
    mode: BookingMode = BookingMode.SINGLE
    series_id: Optional[str] = None
    attendees: int = 1
    price: float = 0.0
    currency: str = "USD"
    payment_id: Optional[str] = None
    confirmation_code: str = ""
    reminder_sent: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def duration_minutes(self) -> int:
        """Get duration in minutes."""
        return int((self.end - self.start).total_seconds() / 60)


@dataclass
class TimeSlot:
    """Available time slot."""
    start: datetime = field(default_factory=datetime.utcnow)
    end: datetime = field(default_factory=datetime.utcnow)
    available: bool = True
    price: float = 0.0


@dataclass
class BlockedTime:
    """Blocked time period."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    resource_id: str = ""
    start: datetime = field(default_factory=datetime.utcnow)
    end: datetime = field(default_factory=datetime.utcnow)
    reason: str = ""
    recurring: bool = False


@dataclass
class BookingConfig:
    """Booking configuration."""
    allow_same_day: bool = True
    require_payment: bool = False
    send_confirmation: bool = True
    send_reminder: bool = True
    reminder_hours_before: int = 24
    cancellation_hours_before: int = 24
    allow_modifications: bool = True
    overbooking_allowed: bool = False
    max_bookings_per_user_per_day: int = 5


@dataclass
class BookingStats:
    """Booking statistics."""
    total_resources: int = 0
    total_bookings: int = 0
    confirmed_bookings: int = 0
    cancelled_bookings: int = 0
    revenue: float = 0.0


# Resource store
class ResourceStore(ABC):
    """Resource storage."""
    
    @abstractmethod
    async def save(self, resource: Resource) -> None:
        pass
    
    @abstractmethod
    async def get(self, resource_id: str) -> Optional[Resource]:
        pass
    
    @abstractmethod
    async def list(
        self,
        type: Optional[ResourceType] = None,
        active_only: bool = True,
    ) -> List[Resource]:
        pass
    
    @abstractmethod
    async def delete(self, resource_id: str) -> bool:
        pass


class InMemoryResourceStore(ResourceStore):
    """In-memory resource store."""
    
    def __init__(self):
        self._resources: Dict[str, Resource] = {}
    
    async def save(self, resource: Resource) -> None:
        self._resources[resource.id] = resource
    
    async def get(self, resource_id: str) -> Optional[Resource]:
        return self._resources.get(resource_id)
    
    async def list(
        self,
        type: Optional[ResourceType] = None,
        active_only: bool = True,
    ) -> List[Resource]:
        resources = list(self._resources.values())
        
        if type:
            resources = [r for r in resources if r.type == type]
        if active_only:
            resources = [r for r in resources if r.is_active]
        
        return resources
    
    async def delete(self, resource_id: str) -> bool:
        return self._resources.pop(resource_id, None) is not None


# Booking store
class BookingStore(ABC):
    """Booking storage."""
    
    @abstractmethod
    async def save(self, booking: Booking) -> None:
        pass
    
    @abstractmethod
    async def get(self, booking_id: str) -> Optional[Booking]:
        pass
    
    @abstractmethod
    async def query(
        self,
        resource_id: Optional[str] = None,
        user_id: Optional[str] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        status: Optional[BookingStatus] = None,
    ) -> List[Booking]:
        pass
    
    @abstractmethod
    async def delete(self, booking_id: str) -> bool:
        pass


class InMemoryBookingStore(BookingStore):
    """In-memory booking store."""
    
    def __init__(self):
        self._bookings: Dict[str, Booking] = {}
    
    async def save(self, booking: Booking) -> None:
        booking.updated_at = datetime.utcnow()
        self._bookings[booking.id] = booking
    
    async def get(self, booking_id: str) -> Optional[Booking]:
        return self._bookings.get(booking_id)
    
    async def query(
        self,
        resource_id: Optional[str] = None,
        user_id: Optional[str] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        status: Optional[BookingStatus] = None,
    ) -> List[Booking]:
        results = []
        
        for booking in self._bookings.values():
            if resource_id and booking.resource_id != resource_id:
                continue
            if user_id and booking.user_id != user_id:
                continue
            if start and booking.end < start:
                continue
            if end and booking.start > end:
                continue
            if status and booking.status != status:
                continue
            results.append(booking)
        
        return sorted(results, key=lambda b: b.start)
    
    async def delete(self, booking_id: str) -> bool:
        return self._bookings.pop(booking_id, None) is not None


# Booking engine
class BookingEngine:
    """Booking engine."""
    
    def __init__(
        self,
        resource_store: Optional[ResourceStore] = None,
        booking_store: Optional[BookingStore] = None,
        config: Optional[BookingConfig] = None,
    ):
        self._resources = resource_store or InMemoryResourceStore()
        self._bookings = booking_store or InMemoryBookingStore()
        self._config = config or BookingConfig()
        self._blocked: Dict[str, List[BlockedTime]] = {}
        self._stats = BookingStats()
    
    # Resource management
    async def add_resource(
        self,
        name: str,
        type: ResourceType = ResourceType.ROOM,
        capacity: int = 1,
        price_per_hour: float = 0.0,
        **kwargs,
    ) -> Resource:
        """Add bookable resource."""
        resource = Resource(
            name=name,
            type=type,
            capacity=capacity,
            price_per_hour=price_per_hour,
            **kwargs,
        )
        await self._resources.save(resource)
        self._stats.total_resources += 1
        
        logger.info(f"Resource added: {name}")
        
        return resource
    
    async def get_resource(self, resource_id: str) -> Optional[Resource]:
        """Get resource."""
        return await self._resources.get(resource_id)
    
    async def list_resources(
        self,
        type: Optional[ResourceType] = None,
    ) -> List[Resource]:
        """List resources."""
        return await self._resources.list(type=type)
    
    async def update_resource(
        self,
        resource_id: str,
        **updates,
    ) -> Optional[Resource]:
        """Update resource."""
        resource = await self._resources.get(resource_id)
        if not resource:
            return None
        
        for key, value in updates.items():
            if hasattr(resource, key):
                setattr(resource, key, value)
        
        await self._resources.save(resource)
        return resource
    
    # Booking management
    async def book(
        self,
        resource_id: str,
        user_id: str,
        start: datetime,
        end: Optional[datetime] = None,
        duration: Optional[int] = None,  # minutes
        title: str = "",
        attendees: int = 1,
        **kwargs,
    ) -> Booking:
        """Create booking."""
        resource = await self._resources.get(resource_id)
        if not resource:
            raise ResourceNotFoundError(f"Resource not found: {resource_id}")
        
        # Calculate end time
        if end is None:
            if duration:
                end = start + timedelta(minutes=duration)
            else:
                end = start + timedelta(minutes=resource.min_duration)
        
        # Validate duration
        duration_minutes = int((end - start).total_seconds() / 60)
        if duration_minutes < resource.min_duration:
            raise BookingError(
                f"Duration too short. Minimum: {resource.min_duration} minutes"
            )
        if duration_minutes > resource.max_duration:
            raise BookingError(
                f"Duration too long. Maximum: {resource.max_duration} minutes"
            )
        
        # Check capacity
        if attendees > resource.capacity:
            raise BookingError(
                f"Exceeds capacity. Maximum: {resource.capacity}"
            )
        
        # Check availability
        if not await self._is_available(resource_id, start, end):
            raise SlotUnavailableError("Time slot is not available")
        
        # Calculate price
        hours = duration_minutes / 60
        price = hours * resource.price_per_hour
        
        # Generate confirmation code
        confirmation = self._generate_confirmation_code()
        
        booking = Booking(
            resource_id=resource_id,
            user_id=user_id,
            title=title or f"Booking: {resource.name}",
            start=start,
            end=end,
            status=BookingStatus.PENDING if resource.requires_approval else BookingStatus.CONFIRMED,
            attendees=attendees,
            price=price,
            currency=resource.currency,
            confirmation_code=confirmation,
            **kwargs,
        )
        
        await self._bookings.save(booking)
        self._stats.total_bookings += 1
        if booking.status == BookingStatus.CONFIRMED:
            self._stats.confirmed_bookings += 1
        
        logger.info(f"Booking created: {confirmation}")
        
        return booking
    
    async def confirm_booking(self, booking_id: str) -> Optional[Booking]:
        """Confirm booking."""
        booking = await self._bookings.get(booking_id)
        if not booking:
            return None
        
        booking.status = BookingStatus.CONFIRMED
        await self._bookings.save(booking)
        self._stats.confirmed_bookings += 1
        
        return booking
    
    async def cancel_booking(
        self,
        booking_id: str,
        reason: str = "",
    ) -> Optional[Booking]:
        """Cancel booking."""
        booking = await self._bookings.get(booking_id)
        if not booking:
            return None
        
        booking.status = BookingStatus.CANCELLED
        if reason:
            booking.notes = f"{booking.notes}\nCancellation: {reason}".strip()
        
        await self._bookings.save(booking)
        self._stats.cancelled_bookings += 1
        
        return booking
    
    async def complete_booking(self, booking_id: str) -> Optional[Booking]:
        """Mark booking as completed."""
        booking = await self._bookings.get(booking_id)
        if not booking:
            return None
        
        booking.status = BookingStatus.COMPLETED
        self._stats.revenue += booking.price
        
        await self._bookings.save(booking)
        
        return booking
    
    async def get_booking(self, booking_id: str) -> Optional[Booking]:
        """Get booking."""
        return await self._bookings.get(booking_id)
    
    async def get_bookings(
        self,
        resource_id: Optional[str] = None,
        user_id: Optional[str] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        status: Optional[BookingStatus] = None,
    ) -> List[Booking]:
        """Get bookings."""
        return await self._bookings.query(
            resource_id=resource_id,
            user_id=user_id,
            start=start,
            end=end,
            status=status,
        )
    
    # Availability
    async def get_availability(
        self,
        resource_id: str,
        date: date,
        duration: int = 60,  # minutes
        slot_interval: int = 30,  # minutes
    ) -> List[TimeSlot]:
        """Get available time slots."""
        resource = await self._resources.get(resource_id)
        if not resource:
            return []
        
        # Get business hours
        hours = resource.business_hours.get_hours(date.weekday())
        if not hours:
            return []
        
        start_time = datetime.combine(date, hours[0])
        end_time = datetime.combine(date, hours[1])
        
        # Get existing bookings
        bookings = await self._bookings.query(
            resource_id=resource_id,
            start=start_time,
            end=end_time,
            status=BookingStatus.CONFIRMED,
        )
        
        # Generate slots
        slots: List[TimeSlot] = []
        current = start_time
        
        while current + timedelta(minutes=duration) <= end_time:
            slot_end = current + timedelta(minutes=duration)
            
            # Check if slot overlaps with any booking
            is_available = True
            for booking in bookings:
                if current < booking.end and slot_end > booking.start:
                    is_available = False
                    break
            
            # Check blocked times
            if is_available and resource_id in self._blocked:
                for blocked in self._blocked[resource_id]:
                    if current < blocked.end and slot_end > blocked.start:
                        is_available = False
                        break
            
            slots.append(TimeSlot(
                start=current,
                end=slot_end,
                available=is_available,
                price=resource.price_per_hour * (duration / 60),
            ))
            
            current += timedelta(minutes=slot_interval)
        
        return slots
    
    async def _is_available(
        self,
        resource_id: str,
        start: datetime,
        end: datetime,
    ) -> bool:
        """Check if time slot is available."""
        # Check existing bookings
        bookings = await self._bookings.query(
            resource_id=resource_id,
            start=start,
            end=end,
            status=BookingStatus.CONFIRMED,
        )
        
        for booking in bookings:
            if start < booking.end and end > booking.start:
                return False
        
        # Check blocked times
        if resource_id in self._blocked:
            for blocked in self._blocked[resource_id]:
                if start < blocked.end and end > blocked.start:
                    return False
        
        return True
    
    # Block time
    async def block_time(
        self,
        resource_id: str,
        start: datetime,
        end: datetime,
        reason: str = "",
    ) -> BlockedTime:
        """Block time period."""
        blocked = BlockedTime(
            resource_id=resource_id,
            start=start,
            end=end,
            reason=reason,
        )
        
        if resource_id not in self._blocked:
            self._blocked[resource_id] = []
        
        self._blocked[resource_id].append(blocked)
        
        return blocked
    
    async def unblock_time(
        self,
        resource_id: str,
        blocked_id: str,
    ) -> bool:
        """Unblock time period."""
        if resource_id not in self._blocked:
            return False
        
        self._blocked[resource_id] = [
            b for b in self._blocked[resource_id]
            if b.id != blocked_id
        ]
        
        return True
    
    def _generate_confirmation_code(self) -> str:
        """Generate confirmation code."""
        import random
        import string
        chars = string.ascii_uppercase + string.digits
        return ''.join(random.choices(chars, k=8))
    
    # Stats
    def get_stats(self) -> BookingStats:
        """Get statistics."""
        return self._stats


# Factory functions
def create_booking_engine(
    config: Optional[BookingConfig] = None,
) -> BookingEngine:
    """Create booking engine."""
    return BookingEngine(config=config)


def create_resource(
    name: str,
    type: ResourceType = ResourceType.ROOM,
    **kwargs,
) -> Resource:
    """Create resource."""
    return Resource(name=name, type=type, **kwargs)


def create_booking_config(**kwargs) -> BookingConfig:
    """Create booking config."""
    return BookingConfig(**kwargs)


def create_business_hours(**kwargs) -> BusinessHours:
    """Create business hours."""
    return BusinessHours(**kwargs)


__all__ = [
    # Exceptions
    "BookingError",
    "ResourceNotFoundError",
    "SlotUnavailableError",
    # Enums
    "BookingStatus",
    "ResourceType",
    "BookingMode",
    # Data classes
    "BusinessHours",
    "Resource",
    "Booking",
    "TimeSlot",
    "BlockedTime",
    "BookingConfig",
    "BookingStats",
    # Stores
    "ResourceStore",
    "InMemoryResourceStore",
    "BookingStore",
    "InMemoryBookingStore",
    # Engine
    "BookingEngine",
    # Factory functions
    "create_booking_engine",
    "create_resource",
    "create_booking_config",
    "create_business_hours",
]
