"""
Enterprise Subscription Manager Module.

Recurring billing, plan management,
usage metering, and subscription lifecycle.

Example:
    # Create subscription manager
    subs = create_subscription_manager()
    
    # Define plans
    await subs.create_plan(
        name="Pro",
        price=2999,
        interval="month",
        features=["unlimited_projects", "priority_support"],
    )
    
    # Subscribe customer
    subscription = await subs.subscribe(
        customer_id="cust_123",
        plan_id="plan_pro",
        trial_days=14,
    )
    
    # Record usage
    await subs.record_usage(
        subscription_id=subscription.id,
        metric="api_calls",
        quantity=1000,
    )
    
    # Get invoice
    invoice = await subs.generate_invoice(subscription.id)
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
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


class SubscriptionError(Exception):
    """Subscription error."""
    pass


class PlanNotFoundError(SubscriptionError):
    """Plan not found."""
    pass


class SubscriptionStatus(str, Enum):
    """Subscription status."""
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    UNPAID = "unpaid"
    PAUSED = "paused"
    EXPIRED = "expired"


class BillingInterval(str, Enum):
    """Billing interval."""
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"


class PricingModel(str, Enum):
    """Pricing model."""
    FLAT = "flat"
    PER_SEAT = "per_seat"
    TIERED = "tiered"
    USAGE = "usage"
    HYBRID = "hybrid"


class UsageType(str, Enum):
    """Usage aggregation type."""
    SUM = "sum"
    MAX = "max"
    LAST = "last"


@dataclass
class PriceTier:
    """Price tier."""
    up_to: Optional[int] = None  # None = infinity
    unit_price: int = 0  # cents per unit
    flat_fee: int = 0  # flat fee for tier


@dataclass
class UsageMetric:
    """Usage-based metric."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    unit: str = ""
    aggregation: UsageType = UsageType.SUM
    tiers: List[PriceTier] = field(default_factory=list)
    included_quantity: int = 0


@dataclass
class Feature:
    """Plan feature."""
    id: str = ""
    name: str = ""
    description: str = ""
    value: Any = True
    metered: bool = False
    limit: Optional[int] = None


@dataclass
class Plan:
    """Subscription plan."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    price: int = 0  # in cents
    currency: str = "USD"
    interval: BillingInterval = BillingInterval.MONTH
    interval_count: int = 1
    pricing_model: PricingModel = PricingModel.FLAT
    features: List[Feature] = field(default_factory=list)
    feature_ids: List[str] = field(default_factory=list)
    usage_metrics: List[UsageMetric] = field(default_factory=list)
    trial_days: int = 0
    setup_fee: int = 0
    min_quantity: int = 1
    max_quantity: Optional[int] = None
    tiers: List[PriceTier] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def calculate_price(self, quantity: int = 1) -> int:
        """Calculate price for quantity."""
        if self.pricing_model == PricingModel.FLAT:
            return self.price
        
        elif self.pricing_model == PricingModel.PER_SEAT:
            return self.price * quantity
        
        elif self.pricing_model == PricingModel.TIERED:
            total = 0
            remaining = quantity
            
            for tier in sorted(self.tiers, key=lambda t: t.up_to or float('inf')):
                tier_units = min(remaining, tier.up_to or remaining)
                total += tier.flat_fee + (tier_units * tier.unit_price)
                remaining -= tier_units
                
                if remaining <= 0:
                    break
            
            return total
        
        return self.price


@dataclass
class Subscription:
    """Subscription."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    customer_id: str = ""
    plan_id: str = ""
    plan: Optional[Plan] = None
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE
    quantity: int = 1
    current_period_start: datetime = field(default_factory=datetime.utcnow)
    current_period_end: Optional[datetime] = None
    trial_start: Optional[datetime] = None
    trial_end: Optional[datetime] = None
    canceled_at: Optional[datetime] = None
    cancel_at_period_end: bool = False
    ended_at: Optional[datetime] = None
    pause_start: Optional[datetime] = None
    pause_end: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def __post_init__(self):
        if not self.current_period_end and self.plan:
            self._calculate_period_end()
    
    def _calculate_period_end(self) -> None:
        """Calculate period end."""
        if not self.plan:
            return
        
        delta = {
            BillingInterval.DAY: timedelta(days=self.plan.interval_count),
            BillingInterval.WEEK: timedelta(weeks=self.plan.interval_count),
            BillingInterval.MONTH: timedelta(days=30 * self.plan.interval_count),
            BillingInterval.YEAR: timedelta(days=365 * self.plan.interval_count),
        }
        
        self.current_period_end = self.current_period_start + delta.get(
            self.plan.interval,
            timedelta(days=30),
        )
    
    @property
    def is_active(self) -> bool:
        """Check if active."""
        return self.status in [
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.TRIALING,
        ]
    
    @property
    def is_trialing(self) -> bool:
        """Check if in trial."""
        if self.status != SubscriptionStatus.TRIALING:
            return False
        if self.trial_end and datetime.utcnow() > self.trial_end:
            return False
        return True
    
    @property
    def days_until_renewal(self) -> int:
        """Days until renewal."""
        if not self.current_period_end:
            return 0
        delta = self.current_period_end - datetime.utcnow()
        return max(0, delta.days)


@dataclass
class UsageRecord:
    """Usage record."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    subscription_id: str = ""
    metric_id: str = ""
    metric_name: str = ""
    quantity: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UsageSummary:
    """Usage summary."""
    metric_id: str = ""
    metric_name: str = ""
    total_quantity: int = 0
    included_quantity: int = 0
    billable_quantity: int = 0
    unit_price: int = 0
    total_amount: int = 0
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None


@dataclass
class Invoice:
    """Subscription invoice."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    subscription_id: str = ""
    customer_id: str = ""
    amount: int = 0
    currency: str = "USD"
    period_start: datetime = field(default_factory=datetime.utcnow)
    period_end: Optional[datetime] = None
    line_items: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "pending"
    paid_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SubscriptionStats:
    """Subscription statistics."""
    total_subscriptions: int = 0
    active_subscriptions: int = 0
    trialing_subscriptions: int = 0
    canceled_subscriptions: int = 0
    mrr: int = 0  # Monthly Recurring Revenue
    arr: int = 0  # Annual Recurring Revenue
    churn_rate: float = 0.0
    by_plan: Dict[str, int] = field(default_factory=dict)


# Plan store
class PlanStore(ABC):
    """Plan storage."""
    
    @abstractmethod
    async def save(self, plan: Plan) -> None:
        """Save plan."""
        pass
    
    @abstractmethod
    async def get(self, plan_id: str) -> Optional[Plan]:
        """Get plan."""
        pass
    
    @abstractmethod
    async def list(self, active_only: bool = True) -> List[Plan]:
        """List plans."""
        pass
    
    @abstractmethod
    async def delete(self, plan_id: str) -> bool:
        """Delete plan."""
        pass


class InMemoryPlanStore(PlanStore):
    """In-memory plan store."""
    
    def __init__(self):
        self._plans: Dict[str, Plan] = {}
    
    async def save(self, plan: Plan) -> None:
        self._plans[plan.id] = plan
    
    async def get(self, plan_id: str) -> Optional[Plan]:
        return self._plans.get(plan_id)
    
    async def list(self, active_only: bool = True) -> List[Plan]:
        plans = list(self._plans.values())
        if active_only:
            plans = [p for p in plans if p.active]
        return sorted(plans, key=lambda p: p.price)
    
    async def delete(self, plan_id: str) -> bool:
        if plan_id in self._plans:
            del self._plans[plan_id]
            return True
        return False


# Subscription store
class SubscriptionStore(ABC):
    """Subscription storage."""
    
    @abstractmethod
    async def save(self, subscription: Subscription) -> None:
        """Save subscription."""
        pass
    
    @abstractmethod
    async def get(self, subscription_id: str) -> Optional[Subscription]:
        """Get subscription."""
        pass
    
    @abstractmethod
    async def get_by_customer(self, customer_id: str) -> List[Subscription]:
        """Get by customer."""
        pass
    
    @abstractmethod
    async def list(
        self,
        status: Optional[SubscriptionStatus] = None,
        plan_id: Optional[str] = None,
    ) -> List[Subscription]:
        """List subscriptions."""
        pass


class InMemorySubscriptionStore(SubscriptionStore):
    """In-memory subscription store."""
    
    def __init__(self):
        self._subscriptions: Dict[str, Subscription] = {}
    
    async def save(self, subscription: Subscription) -> None:
        subscription.updated_at = datetime.utcnow()
        self._subscriptions[subscription.id] = subscription
    
    async def get(self, subscription_id: str) -> Optional[Subscription]:
        return self._subscriptions.get(subscription_id)
    
    async def get_by_customer(self, customer_id: str) -> List[Subscription]:
        return [
            s for s in self._subscriptions.values()
            if s.customer_id == customer_id
        ]
    
    async def list(
        self,
        status: Optional[SubscriptionStatus] = None,
        plan_id: Optional[str] = None,
    ) -> List[Subscription]:
        results = []
        for sub in self._subscriptions.values():
            if status and sub.status != status:
                continue
            if plan_id and sub.plan_id != plan_id:
                continue
            results.append(sub)
        return results


# Usage store
class UsageStore(ABC):
    """Usage storage."""
    
    @abstractmethod
    async def record(self, record: UsageRecord) -> None:
        """Record usage."""
        pass
    
    @abstractmethod
    async def get_usage(
        self,
        subscription_id: str,
        metric_id: str,
        start_time: datetime,
        end_time: datetime,
    ) -> List[UsageRecord]:
        """Get usage records."""
        pass
    
    @abstractmethod
    async def summarize(
        self,
        subscription_id: str,
        start_time: datetime,
        end_time: datetime,
    ) -> List[UsageSummary]:
        """Summarize usage."""
        pass


class InMemoryUsageStore(UsageStore):
    """In-memory usage store."""
    
    def __init__(self):
        self._records: List[UsageRecord] = []
    
    async def record(self, record: UsageRecord) -> None:
        self._records.append(record)
    
    async def get_usage(
        self,
        subscription_id: str,
        metric_id: str,
        start_time: datetime,
        end_time: datetime,
    ) -> List[UsageRecord]:
        return [
            r for r in self._records
            if r.subscription_id == subscription_id
            and r.metric_id == metric_id
            and start_time <= r.timestamp <= end_time
        ]
    
    async def summarize(
        self,
        subscription_id: str,
        start_time: datetime,
        end_time: datetime,
    ) -> List[UsageSummary]:
        # Group by metric
        by_metric: Dict[str, List[UsageRecord]] = {}
        for r in self._records:
            if r.subscription_id != subscription_id:
                continue
            if not (start_time <= r.timestamp <= end_time):
                continue
            
            if r.metric_id not in by_metric:
                by_metric[r.metric_id] = []
            by_metric[r.metric_id].append(r)
        
        summaries = []
        for metric_id, records in by_metric.items():
            total = sum(r.quantity for r in records)
            summaries.append(UsageSummary(
                metric_id=metric_id,
                metric_name=records[0].metric_name if records else "",
                total_quantity=total,
                period_start=start_time,
                period_end=end_time,
            ))
        
        return summaries


# Subscription manager
class SubscriptionManager:
    """Subscription management service."""
    
    def __init__(
        self,
        plan_store: Optional[PlanStore] = None,
        subscription_store: Optional[SubscriptionStore] = None,
        usage_store: Optional[UsageStore] = None,
    ):
        self.plans = plan_store or InMemoryPlanStore()
        self.subscriptions = subscription_store or InMemorySubscriptionStore()
        self.usage = usage_store or InMemoryUsageStore()
        self._stats = SubscriptionStats()
        self._hooks: Dict[str, List[Callable]] = {}
    
    # Plan management
    async def create_plan(
        self,
        name: str,
        price: int,
        interval: BillingInterval = BillingInterval.MONTH,
        features: Optional[List[str]] = None,
        **kwargs,
    ) -> Plan:
        """Create plan."""
        plan = Plan(
            name=name,
            price=price,
            interval=interval,
            feature_ids=features or [],
            **kwargs,
        )
        await self.plans.save(plan)
        
        logger.info(f"Plan created: {plan.name} (${price/100:.2f}/{interval.value})")
        
        return plan
    
    async def get_plan(self, plan_id: str) -> Optional[Plan]:
        """Get plan."""
        return await self.plans.get(plan_id)
    
    async def list_plans(self, active_only: bool = True) -> List[Plan]:
        """List plans."""
        return await self.plans.list(active_only)
    
    async def update_plan(self, plan: Plan) -> Plan:
        """Update plan."""
        await self.plans.save(plan)
        return plan
    
    async def archive_plan(self, plan_id: str) -> Optional[Plan]:
        """Archive plan."""
        plan = await self.plans.get(plan_id)
        if plan:
            plan.active = False
            await self.plans.save(plan)
        return plan
    
    # Subscription management
    async def subscribe(
        self,
        customer_id: str,
        plan_id: str,
        quantity: int = 1,
        trial_days: Optional[int] = None,
        **kwargs,
    ) -> Subscription:
        """Create subscription."""
        plan = await self.plans.get(plan_id)
        if not plan:
            raise PlanNotFoundError(f"Plan not found: {plan_id}")
        
        now = datetime.utcnow()
        trial = trial_days if trial_days is not None else plan.trial_days
        
        subscription = Subscription(
            customer_id=customer_id,
            plan_id=plan_id,
            plan=plan,
            quantity=quantity,
            status=SubscriptionStatus.TRIALING if trial > 0 else SubscriptionStatus.ACTIVE,
            trial_start=now if trial > 0 else None,
            trial_end=now + timedelta(days=trial) if trial > 0 else None,
            **kwargs,
        )
        subscription._calculate_period_end()
        
        await self.subscriptions.save(subscription)
        
        # Update stats
        self._stats.total_subscriptions += 1
        if subscription.status == SubscriptionStatus.ACTIVE:
            self._stats.active_subscriptions += 1
            self._update_mrr(plan.price, quantity)
        elif subscription.status == SubscriptionStatus.TRIALING:
            self._stats.trialing_subscriptions += 1
        
        # Fire hook
        await self._fire_hook("subscription.created", subscription)
        
        logger.info(
            f"Subscription created: {subscription.id} "
            f"(customer: {customer_id}, plan: {plan.name})"
        )
        
        return subscription
    
    async def get_subscription(
        self,
        subscription_id: str,
    ) -> Optional[Subscription]:
        """Get subscription."""
        return await self.subscriptions.get(subscription_id)
    
    async def get_customer_subscriptions(
        self,
        customer_id: str,
    ) -> List[Subscription]:
        """Get customer subscriptions."""
        return await self.subscriptions.get_by_customer(customer_id)
    
    async def update_quantity(
        self,
        subscription_id: str,
        quantity: int,
    ) -> Optional[Subscription]:
        """Update subscription quantity."""
        subscription = await self.subscriptions.get(subscription_id)
        if not subscription:
            return None
        
        old_quantity = subscription.quantity
        subscription.quantity = quantity
        await self.subscriptions.save(subscription)
        
        # Update MRR
        if subscription.plan:
            self._update_mrr(
                subscription.plan.price,
                quantity - old_quantity,
            )
        
        return subscription
    
    async def change_plan(
        self,
        subscription_id: str,
        new_plan_id: str,
        prorate: bool = True,
    ) -> Optional[Subscription]:
        """Change subscription plan."""
        subscription = await self.subscriptions.get(subscription_id)
        if not subscription:
            return None
        
        new_plan = await self.plans.get(new_plan_id)
        if not new_plan:
            raise PlanNotFoundError(f"Plan not found: {new_plan_id}")
        
        old_plan = subscription.plan
        subscription.plan_id = new_plan_id
        subscription.plan = new_plan
        subscription._calculate_period_end()
        
        await self.subscriptions.save(subscription)
        
        # Update MRR
        if old_plan:
            self._update_mrr(-old_plan.price, subscription.quantity)
        self._update_mrr(new_plan.price, subscription.quantity)
        
        await self._fire_hook("subscription.plan_changed", subscription)
        
        logger.info(
            f"Subscription plan changed: {subscription_id} "
            f"({old_plan.name if old_plan else 'none'} -> {new_plan.name})"
        )
        
        return subscription
    
    async def cancel(
        self,
        subscription_id: str,
        at_period_end: bool = True,
        reason: str = "",
    ) -> Optional[Subscription]:
        """Cancel subscription."""
        subscription = await self.subscriptions.get(subscription_id)
        if not subscription:
            return None
        
        subscription.canceled_at = datetime.utcnow()
        subscription.cancel_at_period_end = at_period_end
        
        if not at_period_end:
            subscription.status = SubscriptionStatus.CANCELED
            subscription.ended_at = datetime.utcnow()
            
            if subscription.plan:
                self._update_mrr(
                    -subscription.plan.price,
                    subscription.quantity,
                )
            
            self._stats.active_subscriptions -= 1
            self._stats.canceled_subscriptions += 1
        
        await self.subscriptions.save(subscription)
        
        await self._fire_hook("subscription.canceled", subscription)
        
        logger.info(f"Subscription canceled: {subscription_id}")
        
        return subscription
    
    async def pause(
        self,
        subscription_id: str,
        resume_date: Optional[datetime] = None,
    ) -> Optional[Subscription]:
        """Pause subscription."""
        subscription = await self.subscriptions.get(subscription_id)
        if not subscription:
            return None
        
        subscription.status = SubscriptionStatus.PAUSED
        subscription.pause_start = datetime.utcnow()
        subscription.pause_end = resume_date
        
        await self.subscriptions.save(subscription)
        
        await self._fire_hook("subscription.paused", subscription)
        
        return subscription
    
    async def resume(self, subscription_id: str) -> Optional[Subscription]:
        """Resume paused subscription."""
        subscription = await self.subscriptions.get(subscription_id)
        if not subscription or subscription.status != SubscriptionStatus.PAUSED:
            return None
        
        subscription.status = SubscriptionStatus.ACTIVE
        subscription.pause_start = None
        subscription.pause_end = None
        
        await self.subscriptions.save(subscription)
        
        await self._fire_hook("subscription.resumed", subscription)
        
        return subscription
    
    # Usage tracking
    async def record_usage(
        self,
        subscription_id: str,
        metric: str,
        quantity: int = 1,
        timestamp: Optional[datetime] = None,
        **kwargs,
    ) -> UsageRecord:
        """Record usage."""
        record = UsageRecord(
            subscription_id=subscription_id,
            metric_id=metric,
            metric_name=metric,
            quantity=quantity,
            timestamp=timestamp or datetime.utcnow(),
            metadata=kwargs,
        )
        
        await self.usage.record(record)
        
        return record
    
    async def get_usage_summary(
        self,
        subscription_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[UsageSummary]:
        """Get usage summary."""
        subscription = await self.subscriptions.get(subscription_id)
        if not subscription:
            return []
        
        return await self.usage.summarize(
            subscription_id,
            start_time or subscription.current_period_start,
            end_time or datetime.utcnow(),
        )
    
    # Invoicing
    async def generate_invoice(
        self,
        subscription_id: str,
    ) -> Invoice:
        """Generate invoice for subscription."""
        subscription = await self.subscriptions.get(subscription_id)
        if not subscription:
            raise SubscriptionError(f"Subscription not found: {subscription_id}")
        
        plan = subscription.plan or await self.plans.get(subscription.plan_id)
        if not plan:
            raise SubscriptionError(f"Plan not found: {subscription.plan_id}")
        
        line_items = []
        
        # Base subscription
        base_amount = plan.calculate_price(subscription.quantity)
        line_items.append({
            "description": f"{plan.name} ({plan.interval.value}ly)",
            "quantity": subscription.quantity,
            "unit_price": plan.price,
            "amount": base_amount,
        })
        
        # Usage charges
        usage_summaries = await self.get_usage_summary(subscription_id)
        for summary in usage_summaries:
            if summary.billable_quantity > 0:
                line_items.append({
                    "description": f"Usage: {summary.metric_name}",
                    "quantity": summary.billable_quantity,
                    "unit_price": summary.unit_price,
                    "amount": summary.total_amount,
                })
        
        total = sum(item["amount"] for item in line_items)
        
        invoice = Invoice(
            subscription_id=subscription_id,
            customer_id=subscription.customer_id,
            amount=total,
            period_start=subscription.current_period_start,
            period_end=subscription.current_period_end,
            line_items=line_items,
        )
        
        return invoice
    
    # Hooks
    def on(self, event: str, handler: Callable) -> None:
        """Register event handler."""
        if event not in self._hooks:
            self._hooks[event] = []
        self._hooks[event].append(handler)
    
    async def _fire_hook(self, event: str, data: Any) -> None:
        """Fire event hooks."""
        for handler in self._hooks.get(event, []):
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(data)
                else:
                    handler(data)
            except Exception as e:
                logger.error(f"Hook error for {event}: {e}")
    
    def _update_mrr(self, amount: int, quantity: int = 1) -> None:
        """Update MRR."""
        self._stats.mrr += amount * quantity
        self._stats.arr = self._stats.mrr * 12
    
    def get_stats(self) -> SubscriptionStats:
        """Get statistics."""
        return self._stats


# Factory functions
def create_subscription_manager(
    plan_store: Optional[PlanStore] = None,
    subscription_store: Optional[SubscriptionStore] = None,
) -> SubscriptionManager:
    """Create subscription manager."""
    return SubscriptionManager(
        plan_store=plan_store,
        subscription_store=subscription_store,
    )


def create_plan(
    name: str,
    price: int,
    interval: BillingInterval = BillingInterval.MONTH,
    **kwargs,
) -> Plan:
    """Create plan."""
    return Plan(name=name, price=price, interval=interval, **kwargs)


def create_feature(
    id: str,
    name: str,
    **kwargs,
) -> Feature:
    """Create feature."""
    return Feature(id=id, name=name, **kwargs)


__all__ = [
    # Exceptions
    "SubscriptionError",
    "PlanNotFoundError",
    # Enums
    "SubscriptionStatus",
    "BillingInterval",
    "PricingModel",
    "UsageType",
    # Data classes
    "PriceTier",
    "UsageMetric",
    "Feature",
    "Plan",
    "Subscription",
    "UsageRecord",
    "UsageSummary",
    "Invoice",
    "SubscriptionStats",
    # Stores
    "PlanStore",
    "InMemoryPlanStore",
    "SubscriptionStore",
    "InMemorySubscriptionStore",
    "UsageStore",
    "InMemoryUsageStore",
    # Service
    "SubscriptionManager",
    # Factory functions
    "create_subscription_manager",
    "create_plan",
    "create_feature",
]
