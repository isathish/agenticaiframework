"""
Enterprise OnCall Manager Module.

On-call scheduling, rotation management, escalation
policies, and notification handling.

Example:
    # Create oncall manager
    oncall = create_oncall_manager()
    
    # Create schedule
    schedule = await oncall.create_schedule(
        name="Platform Team",
        timezone="America/New_York",
    )
    
    # Add rotation
    await oncall.add_rotation(
        schedule.id,
        name="Weekly Primary",
        rotation_type=RotationType.WEEKLY,
        members=["alice@example.com", "bob@example.com"],
    )
    
    # Get current oncall
    current = await oncall.get_current_oncall(schedule.id)
"""

from __future__ import annotations

import asyncio
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
    List,
    Optional,
    Tuple,
)

logger = logging.getLogger(__name__)


class OnCallError(Exception):
    """OnCall error."""
    pass


class RotationType(str, Enum):
    """Rotation type."""
    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"


class HandoffType(str, Enum):
    """Handoff type."""
    IMMEDIATE = "immediate"
    SCHEDULED = "scheduled"
    GRADUAL = "gradual"


class EscalationLevel(str, Enum):
    """Escalation level."""
    PRIMARY = "primary"
    SECONDARY = "secondary"
    TERTIARY = "tertiary"
    MANAGER = "manager"


class OverrideType(str, Enum):
    """Override type."""
    FULL = "full"  # Complete takeover
    PARTIAL = "partial"  # Share with primary
    SHADOW = "shadow"  # Backup only


class NotificationType(str, Enum):
    """Notification type."""
    SMS = "sms"
    EMAIL = "email"
    PUSH = "push"
    SLACK = "slack"
    PAGERDUTY = "pagerduty"
    PHONE = "phone"


@dataclass
class Member:
    """Team member."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    email: str = ""
    name: str = ""
    phone: str = ""
    timezone: str = "UTC"
    
    # Notification preferences
    notification_methods: List[NotificationType] = field(
        default_factory=lambda: [NotificationType.EMAIL]
    )
    
    # Availability
    available: bool = True
    unavailable_until: Optional[datetime] = None
    
    # Metadata
    role: str = ""
    team: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Rotation:
    """On-call rotation."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    schedule_id: str = ""
    name: str = ""
    description: str = ""
    
    # Rotation settings
    rotation_type: RotationType = RotationType.WEEKLY
    custom_days: int = 7  # For custom rotation
    
    # Members
    members: List[str] = field(default_factory=list)  # Member IDs/emails
    current_index: int = 0
    
    # Timing
    start_date: datetime = field(default_factory=datetime.utcnow)
    handoff_time: str = "09:00"  # HH:MM format
    handoff_day: int = 1  # 0=Monday, 6=Sunday (for weekly)
    
    # Configuration
    handoff_type: HandoffType = HandoffType.SCHEDULED
    virtual_member: bool = False  # For gap coverage
    
    # Status
    active: bool = True
    last_handoff: Optional[datetime] = None
    next_handoff: Optional[datetime] = None


@dataclass
class Schedule:
    """On-call schedule."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    timezone: str = "UTC"
    
    # Rotations
    rotations: List[Rotation] = field(default_factory=list)
    
    # Escalation
    escalation_policy_id: Optional[str] = None
    
    # Team
    team_id: str = ""
    
    # Status
    active: bool = True
    
    # Dates
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Override:
    """On-call override."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    schedule_id: str = ""
    
    # Override details
    override_type: OverrideType = OverrideType.FULL
    original_member: str = ""
    replacement_member: str = ""
    
    # Duration
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: datetime = field(default_factory=datetime.utcnow)
    
    # Metadata
    reason: str = ""
    created_by: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class EscalationStep:
    """Escalation step."""
    level: EscalationLevel = EscalationLevel.PRIMARY
    delay_minutes: int = 5
    targets: List[str] = field(default_factory=list)  # Member IDs
    notification_methods: List[NotificationType] = field(
        default_factory=lambda: [NotificationType.EMAIL]
    )
    repeat_count: int = 1


@dataclass
class EscalationPolicy:
    """Escalation policy."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    
    # Steps
    steps: List[EscalationStep] = field(default_factory=list)
    
    # Configuration
    repeat_policy: bool = True
    max_repeats: int = 3
    
    # Status
    active: bool = True
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class OnCallShift:
    """On-call shift."""
    member: str = ""
    schedule_id: str = ""
    rotation_id: str = ""
    level: EscalationLevel = EscalationLevel.PRIMARY
    
    # Timing
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: datetime = field(default_factory=datetime.utcnow)
    
    # Override
    is_override: bool = False
    override_id: Optional[str] = None


@dataclass
class OnCallEvent:
    """On-call event."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    schedule_id: str = ""
    event_type: str = ""  # handoff, override, escalation
    description: str = ""
    from_member: str = ""
    to_member: str = ""
    occurred_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OnCallStats:
    """On-call statistics."""
    total_schedules: int = 0
    active_schedules: int = 0
    total_members: int = 0
    active_overrides: int = 0
    upcoming_handoffs: int = 0


# Schedule store
class ScheduleStore(ABC):
    """Schedule storage."""
    
    @abstractmethod
    async def save(self, schedule: Schedule) -> None:
        pass
    
    @abstractmethod
    async def get(self, schedule_id: str) -> Optional[Schedule]:
        pass
    
    @abstractmethod
    async def list_all(self) -> List[Schedule]:
        pass
    
    @abstractmethod
    async def delete(self, schedule_id: str) -> bool:
        pass


class InMemoryScheduleStore(ScheduleStore):
    """In-memory schedule store."""
    
    def __init__(self):
        self._schedules: Dict[str, Schedule] = {}
    
    async def save(self, schedule: Schedule) -> None:
        self._schedules[schedule.id] = schedule
    
    async def get(self, schedule_id: str) -> Optional[Schedule]:
        return self._schedules.get(schedule_id)
    
    async def list_all(self) -> List[Schedule]:
        return list(self._schedules.values())
    
    async def delete(self, schedule_id: str) -> bool:
        if schedule_id in self._schedules:
            del self._schedules[schedule_id]
            return True
        return False


# Member store
class MemberStore(ABC):
    """Member storage."""
    
    @abstractmethod
    async def save(self, member: Member) -> None:
        pass
    
    @abstractmethod
    async def get(self, member_id: str) -> Optional[Member]:
        pass
    
    @abstractmethod
    async def get_by_email(self, email: str) -> Optional[Member]:
        pass
    
    @abstractmethod
    async def list_all(self) -> List[Member]:
        pass


class InMemoryMemberStore(MemberStore):
    """In-memory member store."""
    
    def __init__(self):
        self._members: Dict[str, Member] = {}
        self._by_email: Dict[str, str] = {}
    
    async def save(self, member: Member) -> None:
        self._members[member.id] = member
        if member.email:
            self._by_email[member.email] = member.id
    
    async def get(self, member_id: str) -> Optional[Member]:
        return self._members.get(member_id)
    
    async def get_by_email(self, email: str) -> Optional[Member]:
        member_id = self._by_email.get(email)
        if member_id:
            return self._members.get(member_id)
        return None
    
    async def list_all(self) -> List[Member]:
        return list(self._members.values())


# Override store
class OverrideStore(ABC):
    """Override storage."""
    
    @abstractmethod
    async def save(self, override: Override) -> None:
        pass
    
    @abstractmethod
    async def get_active(
        self,
        schedule_id: str,
        at_time: datetime,
    ) -> List[Override]:
        pass
    
    @abstractmethod
    async def list_by_schedule(self, schedule_id: str) -> List[Override]:
        pass


class InMemoryOverrideStore(OverrideStore):
    """In-memory override store."""
    
    def __init__(self):
        self._overrides: Dict[str, Override] = {}
        self._by_schedule: Dict[str, List[str]] = {}
    
    async def save(self, override: Override) -> None:
        self._overrides[override.id] = override
        
        if override.schedule_id not in self._by_schedule:
            self._by_schedule[override.schedule_id] = []
        
        if override.id not in self._by_schedule[override.schedule_id]:
            self._by_schedule[override.schedule_id].append(override.id)
    
    async def get_active(
        self,
        schedule_id: str,
        at_time: datetime,
    ) -> List[Override]:
        override_ids = self._by_schedule.get(schedule_id, [])
        active = []
        
        for oid in override_ids:
            override = self._overrides.get(oid)
            if override:
                if override.start_time <= at_time <= override.end_time:
                    active.append(override)
        
        return active
    
    async def list_by_schedule(self, schedule_id: str) -> List[Override]:
        override_ids = self._by_schedule.get(schedule_id, [])
        return [self._overrides[oid] for oid in override_ids if oid in self._overrides]


# Policy store
class PolicyStore(ABC):
    """Policy storage."""
    
    @abstractmethod
    async def save(self, policy: EscalationPolicy) -> None:
        pass
    
    @abstractmethod
    async def get(self, policy_id: str) -> Optional[EscalationPolicy]:
        pass
    
    @abstractmethod
    async def list_all(self) -> List[EscalationPolicy]:
        pass


class InMemoryPolicyStore(PolicyStore):
    """In-memory policy store."""
    
    def __init__(self):
        self._policies: Dict[str, EscalationPolicy] = {}
    
    async def save(self, policy: EscalationPolicy) -> None:
        self._policies[policy.id] = policy
    
    async def get(self, policy_id: str) -> Optional[EscalationPolicy]:
        return self._policies.get(policy_id)
    
    async def list_all(self) -> List[EscalationPolicy]:
        return list(self._policies.values())


# Notifier
class Notifier(ABC):
    """Notification sender."""
    
    @abstractmethod
    async def notify(
        self,
        member: Member,
        method: NotificationType,
        subject: str,
        message: str,
    ) -> bool:
        pass


class LogNotifier(Notifier):
    """Log notifier (for testing)."""
    
    async def notify(
        self,
        member: Member,
        method: NotificationType,
        subject: str,
        message: str,
    ) -> bool:
        logger.info(
            f"Notification to {member.email} via {method.value}: "
            f"{subject} - {message}"
        )
        return True


# Rotation calculator
class RotationCalculator:
    """Rotation calculator."""
    
    @staticmethod
    def get_rotation_days(rotation_type: RotationType, custom_days: int = 7) -> int:
        """Get days per rotation."""
        if rotation_type == RotationType.DAILY:
            return 1
        elif rotation_type == RotationType.WEEKLY:
            return 7
        elif rotation_type == RotationType.BIWEEKLY:
            return 14
        elif rotation_type == RotationType.MONTHLY:
            return 30
        elif rotation_type == RotationType.CUSTOM:
            return custom_days
        return 7
    
    @staticmethod
    def get_current_member_index(
        rotation: Rotation,
        at_time: datetime,
    ) -> int:
        """Calculate current member index."""
        if not rotation.members:
            return 0
        
        days = RotationCalculator.get_rotation_days(
            rotation.rotation_type,
            rotation.custom_days,
        )
        
        elapsed = (at_time - rotation.start_date).days
        rotations = elapsed // days
        
        return (rotation.current_index + rotations) % len(rotation.members)
    
    @staticmethod
    def get_next_handoff(rotation: Rotation) -> datetime:
        """Calculate next handoff time."""
        days = RotationCalculator.get_rotation_days(
            rotation.rotation_type,
            rotation.custom_days,
        )
        
        now = datetime.utcnow()
        
        # Parse handoff time
        hour, minute = map(int, rotation.handoff_time.split(":"))
        
        # Find next handoff
        current = rotation.start_date
        while current <= now:
            current += timedelta(days=days)
        
        return current.replace(hour=hour, minute=minute, second=0, microsecond=0)


# OnCall manager
class OnCallManager:
    """OnCall manager."""
    
    def __init__(
        self,
        schedule_store: Optional[ScheduleStore] = None,
        member_store: Optional[MemberStore] = None,
        override_store: Optional[OverrideStore] = None,
        policy_store: Optional[PolicyStore] = None,
        notifier: Optional[Notifier] = None,
    ):
        self._schedule_store = schedule_store or InMemoryScheduleStore()
        self._member_store = member_store or InMemoryMemberStore()
        self._override_store = override_store or InMemoryOverrideStore()
        self._policy_store = policy_store or InMemoryPolicyStore()
        self._notifier = notifier or LogNotifier()
        self._listeners: List[Callable] = []
        self._events: List[OnCallEvent] = []
    
    async def create_schedule(
        self,
        name: str,
        timezone: str = "UTC",
        description: str = "",
        team_id: str = "",
        **kwargs,
    ) -> Schedule:
        """Create on-call schedule."""
        schedule = Schedule(
            name=name,
            timezone=timezone,
            description=description,
            team_id=team_id,
            **kwargs,
        )
        
        await self._schedule_store.save(schedule)
        
        logger.info(f"Schedule created: {name}")
        
        return schedule
    
    async def get_schedule(self, schedule_id: str) -> Optional[Schedule]:
        """Get schedule."""
        return await self._schedule_store.get(schedule_id)
    
    async def list_schedules(self, active_only: bool = True) -> List[Schedule]:
        """List schedules."""
        schedules = await self._schedule_store.list_all()
        
        if active_only:
            schedules = [s for s in schedules if s.active]
        
        return schedules
    
    async def add_member(
        self,
        email: str,
        name: str = "",
        phone: str = "",
        timezone: str = "UTC",
        **kwargs,
    ) -> Member:
        """Add team member."""
        member = Member(
            email=email,
            name=name or email.split("@")[0],
            phone=phone,
            timezone=timezone,
            **kwargs,
        )
        
        await self._member_store.save(member)
        
        logger.info(f"Member added: {email}")
        
        return member
    
    async def get_member(self, email: str) -> Optional[Member]:
        """Get member by email."""
        return await self._member_store.get_by_email(email)
    
    async def add_rotation(
        self,
        schedule_id: str,
        name: str,
        rotation_type: Union[str, RotationType] = RotationType.WEEKLY,
        members: Optional[List[str]] = None,
        handoff_time: str = "09:00",
        handoff_day: int = 1,
        **kwargs,
    ) -> Optional[Rotation]:
        """Add rotation to schedule."""
        schedule = await self._schedule_store.get(schedule_id)
        
        if not schedule:
            return None
        
        if isinstance(rotation_type, str):
            rotation_type = RotationType(rotation_type)
        
        # Calculate next handoff
        rotation = Rotation(
            schedule_id=schedule_id,
            name=name,
            rotation_type=rotation_type,
            members=members or [],
            handoff_time=handoff_time,
            handoff_day=handoff_day,
            **kwargs,
        )
        
        rotation.next_handoff = RotationCalculator.get_next_handoff(rotation)
        
        schedule.rotations.append(rotation)
        schedule.updated_at = datetime.utcnow()
        
        await self._schedule_store.save(schedule)
        
        logger.info(f"Rotation added: {name} to {schedule.name}")
        
        return rotation
    
    async def get_current_oncall(
        self,
        schedule_id: str,
        at_time: Optional[datetime] = None,
    ) -> List[OnCallShift]:
        """Get current on-call members."""
        schedule = await self._schedule_store.get(schedule_id)
        
        if not schedule:
            return []
        
        now = at_time or datetime.utcnow()
        shifts = []
        
        # Check for active overrides
        overrides = await self._override_store.get_active(schedule_id, now)
        override_members = {o.replacement_member for o in overrides}
        
        for rotation in schedule.rotations:
            if not rotation.active or not rotation.members:
                continue
            
            # Get scheduled member
            idx = RotationCalculator.get_current_member_index(rotation, now)
            member_email = rotation.members[idx]
            
            # Check if overridden
            for override in overrides:
                if override.original_member == member_email:
                    member_email = override.replacement_member
                    break
            
            shift = OnCallShift(
                member=member_email,
                schedule_id=schedule_id,
                rotation_id=rotation.id,
                level=EscalationLevel.PRIMARY,
                start_time=now,
                end_time=rotation.next_handoff or now + timedelta(days=7),
                is_override=member_email in override_members,
            )
            
            shifts.append(shift)
        
        return shifts
    
    async def create_override(
        self,
        schedule_id: str,
        original_member: str,
        replacement_member: str,
        start_time: datetime,
        end_time: datetime,
        reason: str = "",
        created_by: str = "",
    ) -> Optional[Override]:
        """Create on-call override."""
        schedule = await self._schedule_store.get(schedule_id)
        
        if not schedule:
            return None
        
        override = Override(
            schedule_id=schedule_id,
            original_member=original_member,
            replacement_member=replacement_member,
            start_time=start_time,
            end_time=end_time,
            reason=reason,
            created_by=created_by,
        )
        
        await self._override_store.save(override)
        
        logger.info(
            f"Override created: {original_member} -> {replacement_member} "
            f"({start_time} to {end_time})"
        )
        
        # Record event
        event = OnCallEvent(
            schedule_id=schedule_id,
            event_type="override",
            description=f"Override: {original_member} -> {replacement_member}",
            from_member=original_member,
            to_member=replacement_member,
        )
        self._events.append(event)
        
        # Notify members
        await self._notify_override(override)
        
        return override
    
    async def get_overrides(
        self,
        schedule_id: str,
        include_past: bool = False,
    ) -> List[Override]:
        """Get overrides for schedule."""
        overrides = await self._override_store.list_by_schedule(schedule_id)
        
        if not include_past:
            now = datetime.utcnow()
            overrides = [o for o in overrides if o.end_time >= now]
        
        return sorted(overrides, key=lambda o: o.start_time)
    
    async def create_escalation_policy(
        self,
        name: str,
        steps: Optional[List[Dict[str, Any]]] = None,
        description: str = "",
    ) -> EscalationPolicy:
        """Create escalation policy."""
        policy_steps = []
        
        for step_data in (steps or []):
            step = EscalationStep(
                level=EscalationLevel(step_data.get("level", "primary")),
                delay_minutes=step_data.get("delay_minutes", 5),
                targets=step_data.get("targets", []),
            )
            policy_steps.append(step)
        
        policy = EscalationPolicy(
            name=name,
            description=description,
            steps=policy_steps,
        )
        
        await self._policy_store.save(policy)
        
        logger.info(f"Escalation policy created: {name}")
        
        return policy
    
    async def get_upcoming_shifts(
        self,
        member_email: str,
        days_ahead: int = 30,
    ) -> List[OnCallShift]:
        """Get upcoming shifts for member."""
        schedules = await self._schedule_store.list_all()
        shifts = []
        
        now = datetime.utcnow()
        end_date = now + timedelta(days=days_ahead)
        
        for schedule in schedules:
            for rotation in schedule.rotations:
                if member_email not in rotation.members:
                    continue
                
                # Calculate shifts
                days_per_rotation = RotationCalculator.get_rotation_days(
                    rotation.rotation_type,
                    rotation.custom_days,
                )
                
                member_idx = rotation.members.index(member_email)
                current = rotation.start_date
                
                while current <= end_date:
                    current_idx = RotationCalculator.get_current_member_index(
                        rotation,
                        current,
                    )
                    
                    if current_idx == member_idx and current >= now:
                        shift_end = current + timedelta(days=days_per_rotation)
                        shifts.append(OnCallShift(
                            member=member_email,
                            schedule_id=schedule.id,
                            rotation_id=rotation.id,
                            level=EscalationLevel.PRIMARY,
                            start_time=current,
                            end_time=shift_end,
                        ))
                    
                    current += timedelta(days=days_per_rotation)
        
        return sorted(shifts, key=lambda s: s.start_time)
    
    async def handoff(
        self,
        schedule_id: str,
        rotation_id: str,
    ) -> bool:
        """Perform rotation handoff."""
        schedule = await self._schedule_store.get(schedule_id)
        
        if not schedule:
            return False
        
        rotation = None
        for r in schedule.rotations:
            if r.id == rotation_id:
                rotation = r
                break
        
        if not rotation or not rotation.members:
            return False
        
        old_idx = rotation.current_index
        old_member = rotation.members[old_idx]
        
        # Advance rotation
        rotation.current_index = (old_idx + 1) % len(rotation.members)
        new_member = rotation.members[rotation.current_index]
        
        rotation.last_handoff = datetime.utcnow()
        rotation.next_handoff = RotationCalculator.get_next_handoff(rotation)
        
        schedule.updated_at = datetime.utcnow()
        await self._schedule_store.save(schedule)
        
        logger.info(f"Handoff: {old_member} -> {new_member}")
        
        # Record event
        event = OnCallEvent(
            schedule_id=schedule_id,
            event_type="handoff",
            description=f"Rotation handoff: {old_member} -> {new_member}",
            from_member=old_member,
            to_member=new_member,
        )
        self._events.append(event)
        
        # Notify
        await self._notify_handoff(rotation, old_member, new_member)
        
        return True
    
    async def set_member_unavailable(
        self,
        email: str,
        until: datetime,
    ) -> Optional[Member]:
        """Set member as unavailable."""
        member = await self._member_store.get_by_email(email)
        
        if not member:
            return None
        
        member.available = False
        member.unavailable_until = until
        
        await self._member_store.save(member)
        
        logger.info(f"Member unavailable: {email} until {until}")
        
        return member
    
    async def get_events(
        self,
        schedule_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[OnCallEvent]:
        """Get on-call events."""
        events = self._events
        
        if schedule_id:
            events = [e for e in events if e.schedule_id == schedule_id]
        
        return sorted(events, key=lambda e: e.occurred_at, reverse=True)[:limit]
    
    async def get_stats(self) -> OnCallStats:
        """Get on-call statistics."""
        schedules = await self._schedule_store.list_all()
        members = await self._member_store.list_all()
        
        stats = OnCallStats(
            total_schedules=len(schedules),
            active_schedules=len([s for s in schedules if s.active]),
            total_members=len(members),
        )
        
        now = datetime.utcnow()
        
        for schedule in schedules:
            overrides = await self._override_store.get_active(schedule.id, now)
            stats.active_overrides += len(overrides)
            
            for rotation in schedule.rotations:
                if rotation.next_handoff and rotation.next_handoff <= now + timedelta(days=7):
                    stats.upcoming_handoffs += 1
        
        return stats
    
    async def _notify_override(self, override: Override) -> None:
        """Notify about override."""
        original = await self._member_store.get_by_email(override.original_member)
        replacement = await self._member_store.get_by_email(override.replacement_member)
        
        if original:
            for method in original.notification_methods:
                await self._notifier.notify(
                    original,
                    method,
                    "On-Call Override",
                    f"Your on-call shift has been covered by {override.replacement_member}",
                )
        
        if replacement:
            for method in replacement.notification_methods:
                await self._notifier.notify(
                    replacement,
                    method,
                    "On-Call Override",
                    f"You are now covering on-call for {override.original_member}",
                )
    
    async def _notify_handoff(
        self,
        rotation: Rotation,
        old_member: str,
        new_member: str,
    ) -> None:
        """Notify about handoff."""
        old = await self._member_store.get_by_email(old_member)
        new = await self._member_store.get_by_email(new_member)
        
        if old:
            for method in old.notification_methods:
                await self._notifier.notify(
                    old,
                    method,
                    "On-Call Handoff Complete",
                    f"Your on-call shift for {rotation.name} has ended",
                )
        
        if new:
            for method in new.notification_methods:
                await self._notifier.notify(
                    new,
                    method,
                    "On-Call Shift Starting",
                    f"Your on-call shift for {rotation.name} is starting",
                )
    
    def add_listener(self, listener: Callable) -> None:
        """Add event listener."""
        self._listeners.append(listener)


# Factory functions
def create_oncall_manager() -> OnCallManager:
    """Create on-call manager."""
    return OnCallManager()


def create_schedule(name: str, **kwargs) -> Schedule:
    """Create schedule."""
    return Schedule(name=name, **kwargs)


def create_rotation(
    name: str,
    members: List[str],
    **kwargs,
) -> Rotation:
    """Create rotation."""
    return Rotation(name=name, members=members, **kwargs)


__all__ = [
    # Exceptions
    "OnCallError",
    # Enums
    "RotationType",
    "HandoffType",
    "EscalationLevel",
    "OverrideType",
    "NotificationType",
    # Data classes
    "Member",
    "Rotation",
    "Schedule",
    "Override",
    "EscalationStep",
    "EscalationPolicy",
    "OnCallShift",
    "OnCallEvent",
    "OnCallStats",
    # Stores
    "ScheduleStore",
    "InMemoryScheduleStore",
    "MemberStore",
    "InMemoryMemberStore",
    "OverrideStore",
    "InMemoryOverrideStore",
    "PolicyStore",
    "InMemoryPolicyStore",
    # Notifier
    "Notifier",
    "LogNotifier",
    # Utilities
    "RotationCalculator",
    # Manager
    "OnCallManager",
    # Factory functions
    "create_oncall_manager",
    "create_schedule",
    "create_rotation",
]
