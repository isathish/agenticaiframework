"""
Enterprise Cost Tracker Module.

Resource cost tracking, budget management, alerts,
and cost optimization recommendations.

Example:
    # Create cost tracker
    tracker = create_cost_tracker()
    
    # Record cost
    await tracker.record(
        resource="compute",
        amount=10.50,
        currency="USD",
        tags={"project": "api", "env": "prod"},
    )
    
    # Set budget
    await tracker.set_budget(
        name="monthly_compute",
        limit=1000.00,
        period="monthly",
        resources=["compute"],
    )
    
    # Get cost summary
    summary = await tracker.get_summary(period_days=30)
"""

from __future__ import annotations

import asyncio
import logging
import time
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
    List,
    Optional,
    Set,
    Tuple,
    Union,
)

logger = logging.getLogger(__name__)


class CostError(Exception):
    """Cost tracking error."""
    pass


class BudgetExceeded(CostError):
    """Budget exceeded error."""
    pass


class Currency(str, Enum):
    """Supported currencies."""
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    JPY = "JPY"
    CNY = "CNY"


class BudgetPeriod(str, Enum):
    """Budget period."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class AlertSeverity(str, Enum):
    """Alert severity."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class CostCategory(str, Enum):
    """Cost categories."""
    COMPUTE = "compute"
    STORAGE = "storage"
    NETWORK = "network"
    DATABASE = "database"
    AI_ML = "ai_ml"
    API = "api"
    OTHER = "other"


@dataclass
class CostEntry:
    """Cost entry."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    resource: str = ""
    category: CostCategory = CostCategory.OTHER
    amount: Decimal = Decimal("0.00")
    currency: Currency = Currency.USD
    quantity: float = 1.0
    unit: str = ""
    tags: Dict[str, str] = field(default_factory=dict)
    recorded_at: datetime = field(default_factory=datetime.utcnow)
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Budget:
    """Budget definition."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    limit: Decimal = Decimal("0.00")
    currency: Currency = Currency.USD
    period: BudgetPeriod = BudgetPeriod.MONTHLY
    resources: List[str] = field(default_factory=list)
    categories: List[CostCategory] = field(default_factory=list)
    tags: Dict[str, str] = field(default_factory=dict)
    alert_thresholds: List[float] = field(default_factory=lambda: [0.5, 0.75, 0.9, 1.0])
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class BudgetStatus:
    """Budget status."""
    budget: Budget = field(default_factory=Budget)
    spent: Decimal = Decimal("0.00")
    remaining: Decimal = Decimal("0.00")
    percentage: float = 0.0
    period_start: datetime = field(default_factory=datetime.utcnow)
    period_end: datetime = field(default_factory=datetime.utcnow)
    is_exceeded: bool = False
    forecast: Decimal = Decimal("0.00")


@dataclass
class CostAlert:
    """Cost alert."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    budget_id: str = ""
    budget_name: str = ""
    severity: AlertSeverity = AlertSeverity.WARNING
    threshold: float = 0.0
    actual: float = 0.0
    message: str = ""
    triggered_at: datetime = field(default_factory=datetime.utcnow)
    acknowledged: bool = False


@dataclass
class CostSummary:
    """Cost summary."""
    total: Decimal = Decimal("0.00")
    currency: Currency = Currency.USD
    by_resource: Dict[str, Decimal] = field(default_factory=dict)
    by_category: Dict[str, Decimal] = field(default_factory=dict)
    by_tag: Dict[str, Dict[str, Decimal]] = field(default_factory=dict)
    daily_costs: Dict[str, Decimal] = field(default_factory=dict)
    period_start: datetime = field(default_factory=datetime.utcnow)
    period_end: datetime = field(default_factory=datetime.utcnow)
    entry_count: int = 0


@dataclass
class CostOptimization:
    """Cost optimization recommendation."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    resource: str = ""
    category: str = ""
    title: str = ""
    description: str = ""
    potential_savings: Decimal = Decimal("0.00")
    effort: str = "low"  # low, medium, high
    priority: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)


# Cost store
class CostStore(ABC):
    """Cost storage."""
    
    @abstractmethod
    async def save(self, entry: CostEntry) -> None:
        pass
    
    @abstractmethod
    async def get(self, entry_id: str) -> Optional[CostEntry]:
        pass
    
    @abstractmethod
    async def list_entries(
        self,
        start_date: datetime,
        end_date: datetime,
        resources: Optional[List[str]] = None,
        categories: Optional[List[CostCategory]] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> List[CostEntry]:
        pass
    
    @abstractmethod
    async def delete(self, entry_id: str) -> bool:
        pass


class InMemoryCostStore(CostStore):
    """In-memory cost store."""
    
    def __init__(self, max_entries: int = 100000):
        self._entries: Dict[str, CostEntry] = {}
        self._max_entries = max_entries
    
    async def save(self, entry: CostEntry) -> None:
        self._entries[entry.id] = entry
        
        # Trim old entries
        if len(self._entries) > self._max_entries:
            sorted_entries = sorted(
                self._entries.values(),
                key=lambda e: e.recorded_at,
            )
            for e in sorted_entries[:len(self._entries) - self._max_entries]:
                del self._entries[e.id]
    
    async def get(self, entry_id: str) -> Optional[CostEntry]:
        return self._entries.get(entry_id)
    
    async def list_entries(
        self,
        start_date: datetime,
        end_date: datetime,
        resources: Optional[List[str]] = None,
        categories: Optional[List[CostCategory]] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> List[CostEntry]:
        results = []
        
        for entry in self._entries.values():
            if entry.recorded_at < start_date or entry.recorded_at > end_date:
                continue
            
            if resources and entry.resource not in resources:
                continue
            
            if categories and entry.category not in categories:
                continue
            
            if tags:
                match = all(
                    entry.tags.get(k) == v
                    for k, v in tags.items()
                )
                if not match:
                    continue
            
            results.append(entry)
        
        return sorted(results, key=lambda e: e.recorded_at, reverse=True)
    
    async def delete(self, entry_id: str) -> bool:
        if entry_id in self._entries:
            del self._entries[entry_id]
            return True
        return False


# Budget store
class BudgetStore(ABC):
    """Budget storage."""
    
    @abstractmethod
    async def save(self, budget: Budget) -> None:
        pass
    
    @abstractmethod
    async def get(self, budget_id: str) -> Optional[Budget]:
        pass
    
    @abstractmethod
    async def get_by_name(self, name: str) -> Optional[Budget]:
        pass
    
    @abstractmethod
    async def list_all(self) -> List[Budget]:
        pass
    
    @abstractmethod
    async def delete(self, budget_id: str) -> bool:
        pass


class InMemoryBudgetStore(BudgetStore):
    """In-memory budget store."""
    
    def __init__(self):
        self._budgets: Dict[str, Budget] = {}
        self._by_name: Dict[str, str] = {}
    
    async def save(self, budget: Budget) -> None:
        self._budgets[budget.id] = budget
        self._by_name[budget.name] = budget.id
    
    async def get(self, budget_id: str) -> Optional[Budget]:
        return self._budgets.get(budget_id)
    
    async def get_by_name(self, name: str) -> Optional[Budget]:
        budget_id = self._by_name.get(name)
        if budget_id:
            return self._budgets.get(budget_id)
        return None
    
    async def list_all(self) -> List[Budget]:
        return list(self._budgets.values())
    
    async def delete(self, budget_id: str) -> bool:
        budget = self._budgets.get(budget_id)
        if budget:
            del self._budgets[budget_id]
            self._by_name.pop(budget.name, None)
            return True
        return False


# Period calculator
class PeriodCalculator:
    """Budget period calculator."""
    
    @staticmethod
    def get_period_range(
        period: BudgetPeriod,
        reference: Optional[datetime] = None,
    ) -> Tuple[datetime, datetime]:
        """Get period start and end dates."""
        ref = reference or datetime.utcnow()
        
        if period == BudgetPeriod.DAILY:
            start = ref.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1) - timedelta(microseconds=1)
        
        elif period == BudgetPeriod.WEEKLY:
            start = ref - timedelta(days=ref.weekday())
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=7) - timedelta(microseconds=1)
        
        elif period == BudgetPeriod.MONTHLY:
            start = ref.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if ref.month == 12:
                end = start.replace(year=ref.year + 1, month=1)
            else:
                end = start.replace(month=ref.month + 1)
            end = end - timedelta(microseconds=1)
        
        elif period == BudgetPeriod.QUARTERLY:
            quarter = (ref.month - 1) // 3
            start_month = quarter * 3 + 1
            start = ref.replace(month=start_month, day=1, hour=0, minute=0, second=0, microsecond=0)
            end_month = start_month + 3
            if end_month > 12:
                end = start.replace(year=ref.year + 1, month=end_month - 12)
            else:
                end = start.replace(month=end_month)
            end = end - timedelta(microseconds=1)
        
        elif period == BudgetPeriod.YEARLY:
            start = ref.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            end = start.replace(year=ref.year + 1) - timedelta(microseconds=1)
        
        else:
            start = ref.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1) - timedelta(microseconds=1)
        
        return start, end


# Cost tracker
class CostTracker:
    """Cost tracker."""
    
    def __init__(
        self,
        cost_store: Optional[CostStore] = None,
        budget_store: Optional[BudgetStore] = None,
        default_currency: Currency = Currency.USD,
    ):
        self._cost_store = cost_store or InMemoryCostStore()
        self._budget_store = budget_store or InMemoryBudgetStore()
        self._default_currency = default_currency
        self._alert_handlers: List[Callable] = []
        self._alerts: List[CostAlert] = []
        self._triggered_thresholds: Dict[str, Set[float]] = {}
    
    async def record(
        self,
        resource: str,
        amount: Union[float, Decimal],
        currency: Optional[Currency] = None,
        category: CostCategory = CostCategory.OTHER,
        quantity: float = 1.0,
        unit: str = "",
        tags: Optional[Dict[str, str]] = None,
        description: str = "",
        **metadata,
    ) -> CostEntry:
        """Record cost entry."""
        entry = CostEntry(
            resource=resource,
            category=category,
            amount=Decimal(str(amount)),
            currency=currency or self._default_currency,
            quantity=quantity,
            unit=unit,
            tags=tags or {},
            description=description,
            metadata=metadata,
        )
        
        await self._cost_store.save(entry)
        
        logger.debug(f"Cost recorded: {resource} {amount} {currency or self._default_currency}")
        
        # Check budgets
        await self._check_budgets()
        
        return entry
    
    async def set_budget(
        self,
        name: str,
        limit: Union[float, Decimal],
        period: Union[str, BudgetPeriod] = BudgetPeriod.MONTHLY,
        currency: Optional[Currency] = None,
        resources: Optional[List[str]] = None,
        categories: Optional[List[CostCategory]] = None,
        tags: Optional[Dict[str, str]] = None,
        alert_thresholds: Optional[List[float]] = None,
    ) -> Budget:
        """Set budget."""
        if isinstance(period, str):
            period = BudgetPeriod(period)
        
        budget = Budget(
            name=name,
            limit=Decimal(str(limit)),
            currency=currency or self._default_currency,
            period=period,
            resources=resources or [],
            categories=categories or [],
            tags=tags or {},
            alert_thresholds=alert_thresholds or [0.5, 0.75, 0.9, 1.0],
        )
        
        await self._budget_store.save(budget)
        
        logger.info(f"Budget set: {name} = {limit} {budget.currency}/{period}")
        
        return budget
    
    async def get_budget_status(self, name: str) -> Optional[BudgetStatus]:
        """Get budget status."""
        budget = await self._budget_store.get_by_name(name)
        
        if not budget:
            return None
        
        period_start, period_end = PeriodCalculator.get_period_range(budget.period)
        
        entries = await self._cost_store.list_entries(
            start_date=period_start,
            end_date=period_end,
            resources=budget.resources or None,
            categories=budget.categories or None,
            tags=budget.tags or None,
        )
        
        spent = sum(e.amount for e in entries)
        remaining = max(Decimal("0"), budget.limit - spent)
        percentage = float(spent / budget.limit * 100) if budget.limit > 0 else 0.0
        
        # Calculate forecast
        now = datetime.utcnow()
        days_elapsed = max(1, (now - period_start).days)
        days_in_period = max(1, (period_end - period_start).days)
        daily_rate = spent / days_elapsed
        forecast = daily_rate * days_in_period
        
        return BudgetStatus(
            budget=budget,
            spent=spent,
            remaining=remaining,
            percentage=percentage,
            period_start=period_start,
            period_end=period_end,
            is_exceeded=spent > budget.limit,
            forecast=forecast,
        )
    
    async def list_budgets(self) -> List[Budget]:
        """List all budgets."""
        return await self._budget_store.list_all()
    
    async def delete_budget(self, name: str) -> bool:
        """Delete budget."""
        budget = await self._budget_store.get_by_name(name)
        
        if budget:
            return await self._budget_store.delete(budget.id)
        
        return False
    
    async def get_summary(
        self,
        period_days: int = 30,
        resources: Optional[List[str]] = None,
        categories: Optional[List[CostCategory]] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> CostSummary:
        """Get cost summary."""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=period_days)
        
        entries = await self._cost_store.list_entries(
            start_date=start_date,
            end_date=end_date,
            resources=resources,
            categories=categories,
            tags=tags,
        )
        
        total = Decimal("0")
        by_resource: Dict[str, Decimal] = {}
        by_category: Dict[str, Decimal] = {}
        by_tag: Dict[str, Dict[str, Decimal]] = {}
        daily_costs: Dict[str, Decimal] = {}
        
        for entry in entries:
            total += entry.amount
            
            # By resource
            by_resource[entry.resource] = by_resource.get(entry.resource, Decimal("0")) + entry.amount
            
            # By category
            cat = entry.category.value
            by_category[cat] = by_category.get(cat, Decimal("0")) + entry.amount
            
            # By tag
            for tag_key, tag_value in entry.tags.items():
                if tag_key not in by_tag:
                    by_tag[tag_key] = {}
                by_tag[tag_key][tag_value] = by_tag[tag_key].get(tag_value, Decimal("0")) + entry.amount
            
            # Daily
            day = entry.recorded_at.strftime("%Y-%m-%d")
            daily_costs[day] = daily_costs.get(day, Decimal("0")) + entry.amount
        
        return CostSummary(
            total=total,
            currency=self._default_currency,
            by_resource=by_resource,
            by_category=by_category,
            by_tag=by_tag,
            daily_costs=daily_costs,
            period_start=start_date,
            period_end=end_date,
            entry_count=len(entries),
        )
    
    async def get_optimizations(self) -> List[CostOptimization]:
        """Get cost optimization recommendations."""
        summary = await self.get_summary(period_days=30)
        optimizations = []
        
        # Find high-cost resources
        if summary.by_resource:
            sorted_resources = sorted(
                summary.by_resource.items(),
                key=lambda x: x[1],
                reverse=True,
            )
            
            for resource, cost in sorted_resources[:3]:
                if cost > summary.total * Decimal("0.2"):
                    optimizations.append(CostOptimization(
                        resource=resource,
                        category="high_cost",
                        title=f"Review high-cost resource: {resource}",
                        description=f"{resource} represents {float(cost / summary.total * 100):.1f}% of total costs",
                        potential_savings=cost * Decimal("0.1"),
                        effort="medium",
                        priority=1,
                    ))
        
        # Check for idle resources (simplified heuristic)
        daily_costs = summary.daily_costs
        if len(daily_costs) > 7:
            recent_days = list(daily_costs.values())[-7:]
            avg_cost = sum(recent_days) / len(recent_days)
            
            for day, cost in daily_costs.items():
                if cost < avg_cost * Decimal("0.1"):
                    optimizations.append(CostOptimization(
                        resource="system",
                        category="idle_resources",
                        title="Potential idle resources detected",
                        description=f"Low activity on {day} suggests possible idle resources",
                        potential_savings=avg_cost * Decimal("0.05"),
                        effort="low",
                        priority=2,
                    ))
                    break
        
        return optimizations
    
    def add_alert_handler(self, handler: Callable) -> None:
        """Add alert handler."""
        self._alert_handlers.append(handler)
    
    async def _check_budgets(self) -> None:
        """Check all budgets for alerts."""
        budgets = await self._budget_store.list_all()
        
        for budget in budgets:
            if not budget.enabled:
                continue
            
            status = await self.get_budget_status(budget.name)
            
            if not status:
                continue
            
            # Check thresholds
            for threshold in budget.alert_thresholds:
                threshold_pct = threshold * 100
                
                if status.percentage >= threshold_pct:
                    key = f"{budget.id}:{threshold}"
                    
                    if budget.id not in self._triggered_thresholds:
                        self._triggered_thresholds[budget.id] = set()
                    
                    if threshold not in self._triggered_thresholds[budget.id]:
                        self._triggered_thresholds[budget.id].add(threshold)
                        
                        severity = (
                            AlertSeverity.CRITICAL if threshold >= 1.0 else
                            AlertSeverity.WARNING if threshold >= 0.75 else
                            AlertSeverity.INFO
                        )
                        
                        alert = CostAlert(
                            budget_id=budget.id,
                            budget_name=budget.name,
                            severity=severity,
                            threshold=threshold_pct,
                            actual=status.percentage,
                            message=f"Budget '{budget.name}' has reached {status.percentage:.1f}% of limit",
                        )
                        
                        self._alerts.append(alert)
                        await self._notify_alert(alert)
    
    async def _notify_alert(self, alert: CostAlert) -> None:
        """Notify alert handlers."""
        logger.warning(f"Cost alert: {alert.message}")
        
        for handler in self._alert_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(alert)
                else:
                    handler(alert)
            except Exception as e:
                logger.error(f"Alert handler error: {e}")
    
    def get_alerts(self, include_acknowledged: bool = False) -> List[CostAlert]:
        """Get alerts."""
        if include_acknowledged:
            return self._alerts.copy()
        return [a for a in self._alerts if not a.acknowledged]
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge alert."""
        for alert in self._alerts:
            if alert.id == alert_id:
                alert.acknowledged = True
                return True
        return False


# Factory functions
def create_cost_tracker(
    default_currency: Currency = Currency.USD,
) -> CostTracker:
    """Create cost tracker."""
    return CostTracker(default_currency=default_currency)


def create_cost_entry(
    resource: str,
    amount: Union[float, Decimal],
    **kwargs,
) -> CostEntry:
    """Create cost entry."""
    return CostEntry(
        resource=resource,
        amount=Decimal(str(amount)),
        **kwargs,
    )


def create_budget(
    name: str,
    limit: Union[float, Decimal],
    **kwargs,
) -> Budget:
    """Create budget."""
    return Budget(
        name=name,
        limit=Decimal(str(limit)),
        **kwargs,
    )


__all__ = [
    # Exceptions
    "CostError",
    "BudgetExceeded",
    # Enums
    "Currency",
    "BudgetPeriod",
    "AlertSeverity",
    "CostCategory",
    # Data classes
    "CostEntry",
    "Budget",
    "BudgetStatus",
    "CostAlert",
    "CostSummary",
    "CostOptimization",
    # Stores
    "CostStore",
    "InMemoryCostStore",
    "BudgetStore",
    "InMemoryBudgetStore",
    # Classes
    "PeriodCalculator",
    "CostTracker",
    # Factory functions
    "create_cost_tracker",
    "create_cost_entry",
    "create_budget",
]
