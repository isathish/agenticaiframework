"""
Enterprise Loyalty Program Module.

Points system, rewards catalog, tier management,
member benefits, and loyalty program operations.

Example:
    # Create loyalty program
    loyalty = create_loyalty_program()
    
    # Enroll member
    member = await loyalty.enroll(
        user_id="user_123",
        email="user@example.com",
    )
    
    # Earn points
    await loyalty.earn_points(
        member_id=member.id,
        points=500,
        source="purchase",
        reference_id="order_123",
    )
    
    # Redeem reward
    redemption = await loyalty.redeem(
        member_id=member.id,
        reward_id="reward_free_shipping",
    )
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, date
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


class LoyaltyError(Exception):
    """Loyalty error."""
    pass


class MemberNotFoundError(LoyaltyError):
    """Member not found."""
    pass


class InsufficientPointsError(LoyaltyError):
    """Insufficient points."""
    pass


class RewardNotFoundError(LoyaltyError):
    """Reward not found."""
    pass


class TierType(str, Enum):
    """Tier type."""
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
    PLATINUM = "platinum"
    DIAMOND = "diamond"


class PointsType(str, Enum):
    """Points transaction type."""
    EARNED = "earned"
    REDEEMED = "redeemed"
    EXPIRED = "expired"
    ADJUSTED = "adjusted"
    BONUS = "bonus"
    TRANSFERRED = "transferred"


class RewardType(str, Enum):
    """Reward type."""
    PRODUCT = "product"
    DISCOUNT = "discount"
    FREE_SHIPPING = "free_shipping"
    CASHBACK = "cashback"
    EXPERIENCE = "experience"
    VOUCHER = "voucher"
    UPGRADE = "upgrade"


@dataclass
class Tier:
    """Loyalty tier."""
    id: str = ""
    name: str = ""
    type: TierType = TierType.BRONZE
    min_points: int = 0
    max_points: Optional[int] = None
    multiplier: float = 1.0
    benefits: List[str] = field(default_factory=list)
    perks: Dict[str, Any] = field(default_factory=dict)
    color: str = ""
    badge_url: str = ""


@dataclass
class Member:
    """Loyalty member."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    email: str = ""
    name: str = ""
    phone: str = ""
    points_balance: int = 0
    lifetime_points: int = 0
    tier: TierType = TierType.BRONZE
    tier_points: int = 0
    tier_expires_at: Optional[datetime] = None
    member_since: datetime = field(default_factory=datetime.utcnow)
    birthday: Optional[date] = None
    preferences: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    is_active: bool = True
    referral_code: str = ""
    referred_by: Optional[str] = None


@dataclass
class PointsTransaction:
    """Points transaction."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    member_id: str = ""
    type: PointsType = PointsType.EARNED
    points: int = 0
    balance_before: int = 0
    balance_after: int = 0
    source: str = ""
    reference_id: str = ""
    description: str = ""
    expires_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Reward:
    """Reward catalog item."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    type: RewardType = RewardType.PRODUCT
    points_cost: int = 0
    value: float = 0.0
    currency: str = "USD"
    category: str = ""
    image_url: str = ""
    quantity_available: Optional[int] = None
    min_tier: Optional[TierType] = None
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    terms: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    is_active: bool = True


@dataclass
class Redemption:
    """Reward redemption."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    member_id: str = ""
    reward_id: str = ""
    reward_name: str = ""
    points_spent: int = 0
    code: str = ""
    status: str = "pending"  # pending, fulfilled, cancelled
    fulfilled_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class EarningRule:
    """Points earning rule."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    source: str = ""  # purchase, referral, birthday, review, etc.
    points_per_unit: float = 1.0
    unit: str = "dollar"  # dollar, item, action
    multiplier: float = 1.0
    max_points: Optional[int] = None
    min_amount: float = 0.0
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    tier_multipliers: Dict[str, float] = field(default_factory=dict)
    is_active: bool = True


@dataclass
class LoyaltyStats:
    """Loyalty statistics."""
    total_members: int = 0
    active_members: int = 0
    total_points_issued: int = 0
    total_points_redeemed: int = 0
    total_rewards_redeemed: int = 0


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
    async def get_by_user(self, user_id: str) -> Optional[Member]:
        pass
    
    @abstractmethod
    async def list(self, tier: Optional[TierType] = None) -> List[Member]:
        pass


class InMemoryMemberStore(MemberStore):
    """In-memory member store."""
    
    def __init__(self):
        self._members: Dict[str, Member] = {}
        self._user_index: Dict[str, str] = {}
    
    async def save(self, member: Member) -> None:
        self._members[member.id] = member
        self._user_index[member.user_id] = member.id
    
    async def get(self, member_id: str) -> Optional[Member]:
        return self._members.get(member_id)
    
    async def get_by_user(self, user_id: str) -> Optional[Member]:
        member_id = self._user_index.get(user_id)
        return self._members.get(member_id) if member_id else None
    
    async def list(self, tier: Optional[TierType] = None) -> List[Member]:
        members = list(self._members.values())
        
        if tier:
            members = [m for m in members if m.tier == tier]
        
        return members


# Loyalty program
class LoyaltyProgram:
    """Loyalty program."""
    
    # Default tiers
    DEFAULT_TIERS = {
        TierType.BRONZE: Tier(
            id="bronze", name="Bronze", type=TierType.BRONZE,
            min_points=0, max_points=999, multiplier=1.0,
            benefits=["Basic rewards access"],
            color="#CD7F32",
        ),
        TierType.SILVER: Tier(
            id="silver", name="Silver", type=TierType.SILVER,
            min_points=1000, max_points=4999, multiplier=1.25,
            benefits=["10% bonus points", "Early access to sales"],
            color="#C0C0C0",
        ),
        TierType.GOLD: Tier(
            id="gold", name="Gold", type=TierType.GOLD,
            min_points=5000, max_points=19999, multiplier=1.5,
            benefits=["25% bonus points", "Free shipping", "Birthday double points"],
            color="#FFD700",
        ),
        TierType.PLATINUM: Tier(
            id="platinum", name="Platinum", type=TierType.PLATINUM,
            min_points=20000, max_points=49999, multiplier=2.0,
            benefits=["50% bonus points", "Priority support", "Exclusive rewards"],
            color="#E5E4E2",
        ),
        TierType.DIAMOND: Tier(
            id="diamond", name="Diamond", type=TierType.DIAMOND,
            min_points=50000, max_points=None, multiplier=3.0,
            benefits=["Triple points", "VIP experiences", "Personal account manager"],
            color="#B9F2FF",
        ),
    }
    
    def __init__(
        self,
        member_store: Optional[MemberStore] = None,
        points_expiry_days: int = 365,
    ):
        self._members = member_store or InMemoryMemberStore()
        self._transactions: Dict[str, List[PointsTransaction]] = {}
        self._rewards: Dict[str, Reward] = {}
        self._redemptions: Dict[str, List[Redemption]] = {}
        self._earning_rules: Dict[str, EarningRule] = {}
        self._tiers = dict(self.DEFAULT_TIERS)
        self._points_expiry_days = points_expiry_days
        self._stats = LoyaltyStats()
        
        self._init_default_rewards()
        self._init_default_rules()
    
    def _init_default_rewards(self) -> None:
        """Initialize default rewards."""
        defaults = [
            Reward(
                id="reward_5_off",
                name="$5 Off",
                type=RewardType.DISCOUNT,
                points_cost=500,
                value=5.0,
            ),
            Reward(
                id="reward_10_off",
                name="$10 Off",
                type=RewardType.DISCOUNT,
                points_cost=1000,
                value=10.0,
            ),
            Reward(
                id="reward_25_off",
                name="$25 Off",
                type=RewardType.DISCOUNT,
                points_cost=2500,
                value=25.0,
            ),
            Reward(
                id="reward_free_shipping",
                name="Free Shipping",
                type=RewardType.FREE_SHIPPING,
                points_cost=300,
                value=9.99,
            ),
        ]
        
        for reward in defaults:
            self._rewards[reward.id] = reward
    
    def _init_default_rules(self) -> None:
        """Initialize default earning rules."""
        defaults = [
            EarningRule(
                id="rule_purchase",
                name="Purchase Points",
                source="purchase",
                points_per_unit=1.0,
                unit="dollar",
            ),
            EarningRule(
                id="rule_referral",
                name="Referral Bonus",
                source="referral",
                points_per_unit=500,
                unit="action",
            ),
            EarningRule(
                id="rule_review",
                name="Review Points",
                source="review",
                points_per_unit=50,
                unit="action",
            ),
            EarningRule(
                id="rule_birthday",
                name="Birthday Bonus",
                source="birthday",
                points_per_unit=200,
                unit="action",
            ),
        ]
        
        for rule in defaults:
            self._earning_rules[rule.id] = rule
    
    async def enroll(
        self,
        user_id: str,
        email: str = "",
        name: str = "",
        referred_by: Optional[str] = None,
        **kwargs,
    ) -> Member:
        """Enroll new member."""
        # Check if already enrolled
        existing = await self._members.get_by_user(user_id)
        if existing:
            return existing
        
        # Generate referral code
        referral_code = f"REF{uuid.uuid4().hex[:8].upper()}"
        
        member = Member(
            user_id=user_id,
            email=email,
            name=name,
            referred_by=referred_by,
            referral_code=referral_code,
            **kwargs,
        )
        
        await self._members.save(member)
        self._transactions[member.id] = []
        self._redemptions[member.id] = []
        self._stats.total_members += 1
        self._stats.active_members += 1
        
        logger.info(f"Member enrolled: {user_id}")
        
        # Award referral bonus if referred
        if referred_by:
            referrer = await self._members.get(referred_by)
            if referrer:
                await self.earn_points(
                    referrer.id,
                    points=500,
                    source="referral",
                    reference_id=member.id,
                    description=f"Referral bonus for {email}",
                )
        
        return member
    
    async def get_member(self, member_id: str) -> Optional[Member]:
        """Get member."""
        return await self._members.get(member_id)
    
    async def get_member_by_user(self, user_id: str) -> Optional[Member]:
        """Get member by user ID."""
        return await self._members.get_by_user(user_id)
    
    async def earn_points(
        self,
        member_id: str,
        points: int,
        source: str = "purchase",
        reference_id: str = "",
        description: str = "",
        amount: float = 0.0,
    ) -> PointsTransaction:
        """Earn points."""
        member = await self._members.get(member_id)
        if not member:
            raise MemberNotFoundError(f"Member not found: {member_id}")
        
        # Apply earning rules
        earned_points = points
        
        if amount > 0:
            rule = next(
                (r for r in self._earning_rules.values() if r.source == source and r.is_active),
                None,
            )
            if rule:
                earned_points = int(amount * rule.points_per_unit)
        
        # Apply tier multiplier
        tier = self._tiers.get(member.tier)
        if tier:
            earned_points = int(earned_points * tier.multiplier)
        
        # Create transaction
        transaction = PointsTransaction(
            member_id=member_id,
            type=PointsType.EARNED,
            points=earned_points,
            balance_before=member.points_balance,
            balance_after=member.points_balance + earned_points,
            source=source,
            reference_id=reference_id,
            description=description or f"Earned {earned_points} points from {source}",
            expires_at=datetime.utcnow() + timedelta(days=self._points_expiry_days),
        )
        
        # Update balance
        member.points_balance += earned_points
        member.lifetime_points += earned_points
        member.tier_points += earned_points
        
        # Check tier upgrade
        await self._check_tier_upgrade(member)
        
        await self._members.save(member)
        
        if member_id not in self._transactions:
            self._transactions[member_id] = []
        self._transactions[member_id].append(transaction)
        
        self._stats.total_points_issued += earned_points
        
        logger.info(f"Points earned: {member_id} +{earned_points}")
        
        return transaction
    
    async def redeem(
        self,
        member_id: str,
        reward_id: str,
    ) -> Redemption:
        """Redeem reward."""
        member = await self._members.get(member_id)
        if not member:
            raise MemberNotFoundError(f"Member not found: {member_id}")
        
        reward = self._rewards.get(reward_id)
        if not reward or not reward.is_active:
            raise RewardNotFoundError(f"Reward not found: {reward_id}")
        
        # Check tier requirement
        if reward.min_tier:
            tier_order = list(TierType)
            if tier_order.index(member.tier) < tier_order.index(reward.min_tier):
                raise LoyaltyError(f"Requires {reward.min_tier.value} tier or higher")
        
        # Check points
        if member.points_balance < reward.points_cost:
            raise InsufficientPointsError(
                f"Insufficient points. Need {reward.points_cost}, have {member.points_balance}"
            )
        
        # Check availability
        if reward.quantity_available is not None and reward.quantity_available <= 0:
            raise LoyaltyError("Reward out of stock")
        
        # Deduct points
        transaction = PointsTransaction(
            member_id=member_id,
            type=PointsType.REDEEMED,
            points=-reward.points_cost,
            balance_before=member.points_balance,
            balance_after=member.points_balance - reward.points_cost,
            source="redemption",
            reference_id=reward_id,
            description=f"Redeemed: {reward.name}",
        )
        
        member.points_balance -= reward.points_cost
        await self._members.save(member)
        
        if member_id not in self._transactions:
            self._transactions[member_id] = []
        self._transactions[member_id].append(transaction)
        
        # Create redemption
        redemption_code = f"RDM{uuid.uuid4().hex[:8].upper()}"
        
        redemption = Redemption(
            member_id=member_id,
            reward_id=reward_id,
            reward_name=reward.name,
            points_spent=reward.points_cost,
            code=redemption_code,
            status="pending",
            expires_at=datetime.utcnow() + timedelta(days=30),
        )
        
        if member_id not in self._redemptions:
            self._redemptions[member_id] = []
        self._redemptions[member_id].append(redemption)
        
        # Update reward quantity
        if reward.quantity_available is not None:
            reward.quantity_available -= 1
        
        self._stats.total_points_redeemed += reward.points_cost
        self._stats.total_rewards_redeemed += 1
        
        logger.info(f"Reward redeemed: {member_id} - {reward.name}")
        
        return redemption
    
    async def _check_tier_upgrade(self, member: Member) -> None:
        """Check and apply tier upgrade."""
        for tier_type, tier in sorted(
            self._tiers.items(),
            key=lambda x: x[1].min_points,
            reverse=True,
        ):
            if member.tier_points >= tier.min_points:
                if member.tier != tier_type:
                    old_tier = member.tier
                    member.tier = tier_type
                    member.tier_expires_at = datetime.utcnow() + timedelta(days=365)
                    
                    logger.info(f"Tier upgrade: {member.user_id} {old_tier} → {tier_type}")
                break
    
    async def get_balance(self, member_id: str) -> int:
        """Get points balance."""
        member = await self._members.get(member_id)
        return member.points_balance if member else 0
    
    async def get_transactions(
        self,
        member_id: str,
        type: Optional[PointsType] = None,
        limit: int = 50,
    ) -> List[PointsTransaction]:
        """Get transaction history."""
        transactions = self._transactions.get(member_id, [])
        
        if type:
            transactions = [t for t in transactions if t.type == type]
        
        return sorted(
            transactions,
            key=lambda t: t.created_at,
            reverse=True,
        )[:limit]
    
    async def get_rewards(
        self,
        member_id: Optional[str] = None,
        category: Optional[str] = None,
    ) -> List[Reward]:
        """Get available rewards."""
        rewards = [r for r in self._rewards.values() if r.is_active]
        
        if category:
            rewards = [r for r in rewards if r.category == category]
        
        if member_id:
            member = await self._members.get(member_id)
            if member:
                # Filter by tier
                tier_order = list(TierType)
                member_tier_idx = tier_order.index(member.tier)
                rewards = [
                    r for r in rewards
                    if not r.min_tier or tier_order.index(r.min_tier) <= member_tier_idx
                ]
        
        return sorted(rewards, key=lambda r: r.points_cost)
    
    async def add_reward(
        self,
        name: str,
        points_cost: int,
        type: RewardType = RewardType.PRODUCT,
        value: float = 0.0,
        **kwargs,
    ) -> Reward:
        """Add reward."""
        reward = Reward(
            name=name,
            points_cost=points_cost,
            type=type,
            value=value,
            **kwargs,
        )
        self._rewards[reward.id] = reward
        
        return reward
    
    async def get_redemptions(
        self,
        member_id: str,
        status: Optional[str] = None,
    ) -> List[Redemption]:
        """Get redemption history."""
        redemptions = self._redemptions.get(member_id, [])
        
        if status:
            redemptions = [r for r in redemptions if r.status == status]
        
        return sorted(
            redemptions,
            key=lambda r: r.created_at,
            reverse=True,
        )
    
    async def fulfill_redemption(self, redemption_id: str) -> bool:
        """Mark redemption as fulfilled."""
        for member_id, redemptions in self._redemptions.items():
            for redemption in redemptions:
                if redemption.id == redemption_id:
                    redemption.status = "fulfilled"
                    redemption.fulfilled_at = datetime.utcnow()
                    return True
        return False
    
    async def get_tier_info(self, tier: TierType) -> Optional[Tier]:
        """Get tier info."""
        return self._tiers.get(tier)
    
    async def get_all_tiers(self) -> List[Tier]:
        """Get all tiers."""
        return sorted(
            self._tiers.values(),
            key=lambda t: t.min_points,
        )
    
    async def add_earning_rule(
        self,
        name: str,
        source: str,
        points_per_unit: float = 1.0,
        **kwargs,
    ) -> EarningRule:
        """Add earning rule."""
        rule = EarningRule(
            name=name,
            source=source,
            points_per_unit=points_per_unit,
            **kwargs,
        )
        self._earning_rules[rule.id] = rule
        
        return rule
    
    def get_stats(self) -> LoyaltyStats:
        """Get statistics."""
        return self._stats


# Factory functions
def create_loyalty_program(
    points_expiry_days: int = 365,
) -> LoyaltyProgram:
    """Create loyalty program."""
    return LoyaltyProgram(points_expiry_days=points_expiry_days)


def create_member(
    user_id: str,
    **kwargs,
) -> Member:
    """Create member."""
    return Member(user_id=user_id, **kwargs)


def create_reward(
    name: str,
    points_cost: int,
    **kwargs,
) -> Reward:
    """Create reward."""
    return Reward(name=name, points_cost=points_cost, **kwargs)


__all__ = [
    # Exceptions
    "LoyaltyError",
    "MemberNotFoundError",
    "InsufficientPointsError",
    "RewardNotFoundError",
    # Enums
    "TierType",
    "PointsType",
    "RewardType",
    # Data classes
    "Tier",
    "Member",
    "PointsTransaction",
    "Reward",
    "Redemption",
    "EarningRule",
    "LoyaltyStats",
    # Stores
    "MemberStore",
    "InMemoryMemberStore",
    # Program
    "LoyaltyProgram",
    # Factory functions
    "create_loyalty_program",
    "create_member",
    "create_reward",
]
