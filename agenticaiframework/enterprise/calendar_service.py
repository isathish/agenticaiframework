"""
Enterprise Calendar Service Module.

Scheduling, recurring events, timezone handling,
availability, and calendar management.

Example:
    # Create calendar service
    calendar = create_calendar_service()
    
    # Create event
    event = await calendar.create_event(
        title="Team Meeting",
        start=datetime(2024, 1, 15, 10, 0),
        end=datetime(2024, 1, 15, 11, 0),
        timezone="America/New_York",
        recurrence="FREQ=WEEKLY;BYDAY=MO,WE,FR",
    )
    
    # Get events for date range
    events = await calendar.get_events(
        start=datetime(2024, 1, 1),
        end=datetime(2024, 1, 31),
    )
    
    # Check availability
    available = await calendar.check_availability(
        user_id="user_123",
        start=datetime(2024, 1, 15, 14, 0),
        duration=60,  # minutes
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

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

T = TypeVar('T')

logger = logging.getLogger(__name__)


class CalendarError(Exception):
    """Calendar error."""
    pass


class EventNotFoundError(CalendarError):
    """Event not found."""
    pass


class ConflictError(CalendarError):
    """Scheduling conflict."""
    pass


class EventStatus(str, Enum):
    """Event status."""
    CONFIRMED = "confirmed"
    TENTATIVE = "tentative"
    CANCELLED = "cancelled"


class RecurrenceFrequency(str, Enum):
    """Recurrence frequency."""
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    YEARLY = "YEARLY"


class Weekday(str, Enum):
    """Weekday."""
    MONDAY = "MO"
    TUESDAY = "TU"
    WEDNESDAY = "WE"
    THURSDAY = "TH"
    FRIDAY = "FR"
    SATURDAY = "SA"
    SUNDAY = "SU"


@dataclass
class Attendee:
    """Event attendee."""
    email: str = ""
    name: str = ""
    status: str = "needs_action"  # accepted, declined, tentative, needs_action
    required: bool = True


@dataclass
class Reminder:
    """Event reminder."""
    minutes_before: int = 15
    method: str = "popup"  # popup, email, sms


@dataclass
class RecurrenceRule:
    """Recurrence rule."""
    frequency: RecurrenceFrequency = RecurrenceFrequency.WEEKLY
    interval: int = 1
    count: Optional[int] = None
    until: Optional[datetime] = None
    by_day: List[Weekday] = field(default_factory=list)
    by_month_day: List[int] = field(default_factory=list)
    by_month: List[int] = field(default_factory=list)
    
    def to_rrule_string(self) -> str:
        """Convert to RRULE string."""
        parts = [f"FREQ={self.frequency.value}"]
        
        if self.interval != 1:
            parts.append(f"INTERVAL={self.interval}")
        
        if self.count:
            parts.append(f"COUNT={self.count}")
        
        if self.until:
            parts.append(f"UNTIL={self.until.strftime('%Y%m%dT%H%M%SZ')}")
        
        if self.by_day:
            parts.append(f"BYDAY={','.join(d.value for d in self.by_day)}")
        
        if self.by_month_day:
            parts.append(f"BYMONTHDAY={','.join(str(d) for d in self.by_month_day)}")
        
        if self.by_month:
            parts.append(f"BYMONTH={','.join(str(m) for m in self.by_month)}")
        
        return ";".join(parts)
    
    @classmethod
    def from_rrule_string(cls, rrule: str) -> "RecurrenceRule":
        """Parse from RRULE string."""
        rule = cls()
        
        for part in rrule.split(";"):
            if "=" not in part:
                continue
            
            key, value = part.split("=", 1)
            
            if key == "FREQ":
                rule.frequency = RecurrenceFrequency(value)
            elif key == "INTERVAL":
                rule.interval = int(value)
            elif key == "COUNT":
                rule.count = int(value)
            elif key == "UNTIL":
                rule.until = datetime.strptime(value, "%Y%m%dT%H%M%SZ")
            elif key == "BYDAY":
                rule.by_day = [Weekday(d) for d in value.split(",")]
            elif key == "BYMONTHDAY":
                rule.by_month_day = [int(d) for d in value.split(",")]
            elif key == "BYMONTH":
                rule.by_month = [int(m) for m in value.split(",")]
        
        return rule


@dataclass
class Event:
    """Calendar event."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    calendar_id: str = ""
    title: str = ""
    description: str = ""
    location: str = ""
    start: datetime = field(default_factory=datetime.utcnow)
    end: datetime = field(default_factory=datetime.utcnow)
    all_day: bool = False
    timezone: str = "UTC"
    status: EventStatus = EventStatus.CONFIRMED
    attendees: List[Attendee] = field(default_factory=list)
    reminders: List[Reminder] = field(default_factory=list)
    recurrence: Optional[RecurrenceRule] = None
    recurrence_id: Optional[str] = None
    color: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_by: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def duration(self) -> timedelta:
        """Get event duration."""
        return self.end - self.start
    
    @property
    def duration_minutes(self) -> int:
        """Get duration in minutes."""
        return int(self.duration.total_seconds() / 60)
    
    def overlaps(self, other: "Event") -> bool:
        """Check if overlaps with another event."""
        return self.start < other.end and self.end > other.start


@dataclass
class Calendar:
    """Calendar."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    owner_id: str = ""
    color: str = "#4285F4"
    timezone: str = "UTC"
    is_primary: bool = False
    is_shared: bool = False
    shared_with: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class TimeSlot:
    """Time slot."""
    start: datetime = field(default_factory=datetime.utcnow)
    end: datetime = field(default_factory=datetime.utcnow)
    available: bool = True
    event_id: Optional[str] = None


@dataclass
class Availability:
    """User availability."""
    user_id: str = ""
    slots: List[TimeSlot] = field(default_factory=list)
    working_hours: Dict[str, Tuple[time, time]] = field(default_factory=dict)
    timezone: str = "UTC"


@dataclass
class CalendarStats:
    """Calendar statistics."""
    total_calendars: int = 0
    total_events: int = 0
    recurring_events: int = 0
    events_this_week: int = 0


# Event store
class EventStore(ABC):
    """Event storage."""
    
    @abstractmethod
    async def save(self, event: Event) -> None:
        """Save event."""
        pass
    
    @abstractmethod
    async def get(self, event_id: str) -> Optional[Event]:
        """Get event."""
        pass
    
    @abstractmethod
    async def query(
        self,
        calendar_id: Optional[str] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> List[Event]:
        """Query events."""
        pass
    
    @abstractmethod
    async def delete(self, event_id: str) -> bool:
        """Delete event."""
        pass


class InMemoryEventStore(EventStore):
    """In-memory event store."""
    
    def __init__(self):
        self._events: Dict[str, Event] = {}
    
    async def save(self, event: Event) -> None:
        event.updated_at = datetime.utcnow()
        self._events[event.id] = event
    
    async def get(self, event_id: str) -> Optional[Event]:
        return self._events.get(event_id)
    
    async def query(
        self,
        calendar_id: Optional[str] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> List[Event]:
        results = []
        
        for event in self._events.values():
            if calendar_id and event.calendar_id != calendar_id:
                continue
            if start and event.end < start:
                continue
            if end and event.start > end:
                continue
            
            results.append(event)
        
        return sorted(results, key=lambda e: e.start)
    
    async def delete(self, event_id: str) -> bool:
        return self._events.pop(event_id, None) is not None


# Calendar store
class CalendarStore(ABC):
    """Calendar storage."""
    
    @abstractmethod
    async def save(self, calendar: Calendar) -> None:
        """Save calendar."""
        pass
    
    @abstractmethod
    async def get(self, calendar_id: str) -> Optional[Calendar]:
        """Get calendar."""
        pass
    
    @abstractmethod
    async def list(self, owner_id: Optional[str] = None) -> List[Calendar]:
        """List calendars."""
        pass
    
    @abstractmethod
    async def delete(self, calendar_id: str) -> bool:
        """Delete calendar."""
        pass


class InMemoryCalendarStore(CalendarStore):
    """In-memory calendar store."""
    
    def __init__(self):
        self._calendars: Dict[str, Calendar] = {}
    
    async def save(self, calendar: Calendar) -> None:
        self._calendars[calendar.id] = calendar
    
    async def get(self, calendar_id: str) -> Optional[Calendar]:
        return self._calendars.get(calendar_id)
    
    async def list(self, owner_id: Optional[str] = None) -> List[Calendar]:
        calendars = list(self._calendars.values())
        if owner_id:
            calendars = [c for c in calendars if c.owner_id == owner_id]
        return calendars
    
    async def delete(self, calendar_id: str) -> bool:
        return self._calendars.pop(calendar_id, None) is not None


# Calendar service
class CalendarService:
    """Calendar service."""
    
    def __init__(
        self,
        event_store: Optional[EventStore] = None,
        calendar_store: Optional[CalendarStore] = None,
        default_timezone: str = "UTC",
    ):
        self._events = event_store or InMemoryEventStore()
        self._calendars = calendar_store or InMemoryCalendarStore()
        self._default_timezone = default_timezone
        self._stats = CalendarStats()
    
    # Calendar management
    async def create_calendar(
        self,
        name: str,
        owner_id: str,
        description: str = "",
        timezone: Optional[str] = None,
        **kwargs,
    ) -> Calendar:
        """Create calendar."""
        calendar = Calendar(
            name=name,
            owner_id=owner_id,
            description=description,
            timezone=timezone or self._default_timezone,
            **kwargs,
        )
        await self._calendars.save(calendar)
        self._stats.total_calendars += 1
        
        logger.info(f"Calendar created: {name}")
        
        return calendar
    
    async def get_calendar(self, calendar_id: str) -> Optional[Calendar]:
        """Get calendar."""
        return await self._calendars.get(calendar_id)
    
    async def list_calendars(
        self,
        owner_id: Optional[str] = None,
    ) -> List[Calendar]:
        """List calendars."""
        return await self._calendars.list(owner_id)
    
    async def delete_calendar(self, calendar_id: str) -> bool:
        """Delete calendar."""
        result = await self._calendars.delete(calendar_id)
        if result:
            self._stats.total_calendars -= 1
        return result
    
    # Event management
    async def create_event(
        self,
        title: str,
        start: datetime,
        end: Optional[datetime] = None,
        duration: Optional[int] = None,  # minutes
        calendar_id: str = "",
        timezone: Optional[str] = None,
        recurrence: Optional[str] = None,
        attendees: Optional[List[Dict[str, str]]] = None,
        **kwargs,
    ) -> Event:
        """Create event."""
        if end is None:
            if duration:
                end = start + timedelta(minutes=duration)
            else:
                end = start + timedelta(hours=1)
        
        event = Event(
            calendar_id=calendar_id,
            title=title,
            start=start,
            end=end,
            timezone=timezone or self._default_timezone,
            attendees=[
                Attendee(**a) for a in (attendees or [])
            ],
            **kwargs,
        )
        
        # Parse recurrence
        if recurrence:
            event.recurrence = RecurrenceRule.from_rrule_string(recurrence)
            self._stats.recurring_events += 1
        
        await self._events.save(event)
        self._stats.total_events += 1
        
        logger.info(f"Event created: {title}")
        
        return event
    
    async def get_event(self, event_id: str) -> Optional[Event]:
        """Get event."""
        return await self._events.get(event_id)
    
    async def update_event(
        self,
        event_id: str,
        **updates,
    ) -> Optional[Event]:
        """Update event."""
        event = await self._events.get(event_id)
        if not event:
            return None
        
        for key, value in updates.items():
            if hasattr(event, key):
                setattr(event, key, value)
        
        await self._events.save(event)
        
        return event
    
    async def delete_event(
        self,
        event_id: str,
        delete_series: bool = False,
    ) -> bool:
        """Delete event."""
        event = await self._events.get(event_id)
        if not event:
            return False
        
        if delete_series and event.recurrence:
            # Delete all instances
            events = await self._events.query(calendar_id=event.calendar_id)
            for e in events:
                if e.recurrence_id == event_id or e.id == event_id:
                    await self._events.delete(e.id)
        else:
            await self._events.delete(event_id)
        
        self._stats.total_events -= 1
        return True
    
    async def get_events(
        self,
        calendar_id: Optional[str] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        expand_recurring: bool = True,
    ) -> List[Event]:
        """Get events."""
        events = await self._events.query(
            calendar_id=calendar_id,
            start=start,
            end=end,
        )
        
        if expand_recurring and start and end:
            expanded = []
            for event in events:
                if event.recurrence:
                    instances = self._expand_recurring(event, start, end)
                    expanded.extend(instances)
                else:
                    expanded.append(event)
            events = expanded
        
        return sorted(events, key=lambda e: e.start)
    
    def _expand_recurring(
        self,
        event: Event,
        range_start: datetime,
        range_end: datetime,
    ) -> List[Event]:
        """Expand recurring event."""
        instances: List[Event] = []
        
        if not event.recurrence:
            return [event]
        
        rule = event.recurrence
        current = event.start
        count = 0
        max_instances = rule.count or 365
        
        while current < range_end and count < max_instances:
            if current >= range_start:
                instance = Event(
                    id=f"{event.id}_{current.isoformat()}",
                    calendar_id=event.calendar_id,
                    title=event.title,
                    description=event.description,
                    location=event.location,
                    start=current,
                    end=current + event.duration,
                    timezone=event.timezone,
                    status=event.status,
                    attendees=event.attendees,
                    recurrence_id=event.id,
                    color=event.color,
                    metadata=event.metadata,
                )
                instances.append(instance)
            
            # Advance to next occurrence
            if rule.frequency == RecurrenceFrequency.DAILY:
                current += timedelta(days=rule.interval)
            elif rule.frequency == RecurrenceFrequency.WEEKLY:
                current += timedelta(weeks=rule.interval)
            elif rule.frequency == RecurrenceFrequency.MONTHLY:
                # Simple month increment
                month = current.month + rule.interval
                year = current.year + (month - 1) // 12
                month = ((month - 1) % 12) + 1
                try:
                    current = current.replace(year=year, month=month)
                except ValueError:
                    # Handle end of month
                    current = current.replace(year=year, month=month + 1, day=1)
            elif rule.frequency == RecurrenceFrequency.YEARLY:
                current = current.replace(year=current.year + rule.interval)
            
            count += 1
            
            if rule.until and current > rule.until:
                break
        
        return instances
    
    # Availability
    async def check_availability(
        self,
        user_id: str,
        start: datetime,
        duration: int,  # minutes
        calendar_id: Optional[str] = None,
    ) -> bool:
        """Check if time slot is available."""
        end = start + timedelta(minutes=duration)
        
        events = await self.get_events(
            calendar_id=calendar_id,
            start=start,
            end=end,
        )
        
        # Filter by user
        user_events = [
            e for e in events
            if e.created_by == user_id or any(
                a.email == user_id for a in e.attendees
            )
        ]
        
        return len(user_events) == 0
    
    async def find_available_slots(
        self,
        user_id: str,
        date: date,
        duration: int,  # minutes
        working_hours: Tuple[time, time] = (time(9, 0), time(17, 0)),
        calendar_id: Optional[str] = None,
    ) -> List[TimeSlot]:
        """Find available time slots."""
        start = datetime.combine(date, working_hours[0])
        end = datetime.combine(date, working_hours[1])
        
        events = await self.get_events(
            calendar_id=calendar_id,
            start=start,
            end=end,
        )
        
        # Find gaps
        slots: List[TimeSlot] = []
        current = start
        
        for event in sorted(events, key=lambda e: e.start):
            if event.start > current:
                # There's a gap
                gap_minutes = int((event.start - current).total_seconds() / 60)
                if gap_minutes >= duration:
                    slots.append(TimeSlot(
                        start=current,
                        end=event.start,
                        available=True,
                    ))
            current = max(current, event.end)
        
        # Check remaining time
        if current < end:
            gap_minutes = int((end - current).total_seconds() / 60)
            if gap_minutes >= duration:
                slots.append(TimeSlot(
                    start=current,
                    end=end,
                    available=True,
                ))
        
        return slots
    
    # Timezone handling
    def convert_timezone(
        self,
        dt: datetime,
        from_tz: str,
        to_tz: str,
    ) -> datetime:
        """Convert datetime between timezones."""
        from_zone = ZoneInfo(from_tz)
        to_zone = ZoneInfo(to_tz)
        
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=from_zone)
        
        return dt.astimezone(to_zone)
    
    def now(self, timezone: Optional[str] = None) -> datetime:
        """Get current time in timezone."""
        tz = ZoneInfo(timezone or self._default_timezone)
        return datetime.now(tz)
    
    # Stats
    def get_stats(self) -> CalendarStats:
        """Get statistics."""
        return self._stats


# Factory functions
def create_calendar_service(
    default_timezone: str = "UTC",
) -> CalendarService:
    """Create calendar service."""
    return CalendarService(default_timezone=default_timezone)


def create_calendar(
    name: str,
    owner_id: str = "",
    **kwargs,
) -> Calendar:
    """Create calendar."""
    return Calendar(name=name, owner_id=owner_id, **kwargs)


def create_event(
    title: str,
    start: datetime,
    end: Optional[datetime] = None,
    **kwargs,
) -> Event:
    """Create event."""
    return Event(
        title=title,
        start=start,
        end=end or (start + timedelta(hours=1)),
        **kwargs,
    )


def create_recurrence(
    frequency: RecurrenceFrequency = RecurrenceFrequency.WEEKLY,
    interval: int = 1,
    **kwargs,
) -> RecurrenceRule:
    """Create recurrence rule."""
    return RecurrenceRule(
        frequency=frequency,
        interval=interval,
        **kwargs,
    )


__all__ = [
    # Exceptions
    "CalendarError",
    "EventNotFoundError",
    "ConflictError",
    # Enums
    "EventStatus",
    "RecurrenceFrequency",
    "Weekday",
    # Data classes
    "Attendee",
    "Reminder",
    "RecurrenceRule",
    "Event",
    "Calendar",
    "TimeSlot",
    "Availability",
    "CalendarStats",
    # Stores
    "EventStore",
    "InMemoryEventStore",
    "CalendarStore",
    "InMemoryCalendarStore",
    # Service
    "CalendarService",
    # Factory functions
    "create_calendar_service",
    "create_calendar",
    "create_event",
    "create_recurrence",
]
