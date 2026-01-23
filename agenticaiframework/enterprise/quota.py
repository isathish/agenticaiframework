"""
Enterprise Quota Module.

Provides quota management, usage tracking, billing integration,
and resource governance for agent operations.

Example:
    # Quota management
    quota_manager = QuotaManager()
    quota_manager.set_quota("api_calls", daily=10000, monthly=100000)
    
    async with quota_manager.track("api_calls"):
        result = await agent.run(prompt)
    
    # Decorators
    @enforce_quota("tokens", cost=lambda r: len(r))
    async def generate_text():
        ...
"""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    TypeVar,
    Generic,
    Union,
)
from datetime import datetime, timedelta
from functools import wraps
from enum import Enum
from contextlib import asynccontextmanager
import logging
import json

logger = logging.getLogger(__name__)

T = TypeVar('T')


class QuotaError(Exception):
    """Base quota error."""
    pass


class QuotaExceeded(QuotaError):
    """Quota has been exceeded."""
    
    def __init__(
        self,
        message: str,
        quota_name: str,
        current: float,
        limit: float,
        reset_time: Optional[float] = None,
    ):
        super().__init__(message)
        self.quota_name = quota_name
        self.current = current
        self.limit = limit
        self.reset_time = reset_time


class QuotaPeriod(str, Enum):
    """Quota time periods."""
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"
    TOTAL = "total"
    
    def to_seconds(self) -> Optional[int]:
        """Convert period to seconds."""
        mapping = {
            QuotaPeriod.MINUTE: 60,
            QuotaPeriod.HOUR: 3600,
            QuotaPeriod.DAY: 86400,
            QuotaPeriod.WEEK: 604800,
            QuotaPeriod.MONTH: 2592000,
            QuotaPeriod.YEAR: 31536000,
        }
        return mapping.get(self)


@dataclass
class QuotaLimit:
    """A single quota limit."""
    period: QuotaPeriod
    limit: float
    current: float = 0.0
    period_start: float = field(default_factory=time.time)
    
    @property
    def remaining(self) -> float:
        """Get remaining quota."""
        return max(0, self.limit - self.current)
    
    @property
    def usage_percent(self) -> float:
        """Get usage percentage."""
        if self.limit <= 0:
            return 100.0
        return (self.current / self.limit) * 100
    
    def is_exceeded(self) -> bool:
        """Check if quota is exceeded."""
        return self.current >= self.limit
    
    def reset_time(self) -> Optional[float]:
        """Get next reset time."""
        seconds = self.period.to_seconds()
        if seconds is None:
            return None
        return self.period_start + seconds
    
    def should_reset(self) -> bool:
        """Check if period has expired."""
        reset = self.reset_time()
        if reset is None:
            return False
        return time.time() >= reset
    
    def reset(self) -> None:
        """Reset the quota counter."""
        self.current = 0.0
        self.period_start = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "period": self.period.value,
            "limit": self.limit,
            "current": self.current,
            "remaining": self.remaining,
            "usage_percent": self.usage_percent,
            "reset_time": self.reset_time(),
        }


@dataclass
class UsageRecord:
    """Record of quota usage."""
    quota_name: str
    amount: float
    timestamp: float
    user_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "quota_name": self.quota_name,
            "amount": self.amount,
            "timestamp": self.timestamp,
            "user_id": self.user_id,
            "metadata": self.metadata,
        }


@dataclass
class QuotaStats:
    """Statistics for a quota."""
    quota_name: str
    limits: Dict[str, QuotaLimit]
    total_usage: float
    usage_history: List[UsageRecord]
    
    @property
    def is_exceeded(self) -> bool:
        """Check if any limit is exceeded."""
        return any(limit.is_exceeded() for limit in self.limits.values())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "quota_name": self.quota_name,
            "limits": {k: v.to_dict() for k, v in self.limits.items()},
            "total_usage": self.total_usage,
            "is_exceeded": self.is_exceeded,
            "history_count": len(self.usage_history),
        }


class UsageStore(ABC):
    """Abstract usage data store."""
    
    @abstractmethod
    async def record(self, record: UsageRecord) -> None:
        """Record usage."""
        pass
    
    @abstractmethod
    async def get_usage(
        self,
        quota_name: str,
        since: Optional[float] = None,
        user_id: Optional[str] = None,
    ) -> List[UsageRecord]:
        """Get usage records."""
        pass
    
    @abstractmethod
    async def get_total(
        self,
        quota_name: str,
        since: Optional[float] = None,
        user_id: Optional[str] = None,
    ) -> float:
        """Get total usage."""
        pass
    
    @abstractmethod
    async def clear(
        self,
        quota_name: Optional[str] = None,
        before: Optional[float] = None,
    ) -> int:
        """Clear old usage records."""
        pass


class InMemoryUsageStore(UsageStore):
    """In-memory usage store."""
    
    def __init__(self, max_records: int = 10000):
        self._records: List[UsageRecord] = []
        self._max_records = max_records
        self._lock = asyncio.Lock()
    
    async def record(self, record: UsageRecord) -> None:
        """Record usage."""
        async with self._lock:
            self._records.append(record)
            
            # Trim old records
            if len(self._records) > self._max_records:
                self._records = self._records[-self._max_records:]
    
    async def get_usage(
        self,
        quota_name: str,
        since: Optional[float] = None,
        user_id: Optional[str] = None,
    ) -> List[UsageRecord]:
        """Get usage records."""
        async with self._lock:
            records = [r for r in self._records if r.quota_name == quota_name]
            
            if since is not None:
                records = [r for r in records if r.timestamp >= since]
            
            if user_id is not None:
                records = [r for r in records if r.user_id == user_id]
            
            return records
    
    async def get_total(
        self,
        quota_name: str,
        since: Optional[float] = None,
        user_id: Optional[str] = None,
    ) -> float:
        """Get total usage."""
        records = await self.get_usage(quota_name, since, user_id)
        return sum(r.amount for r in records)
    
    async def clear(
        self,
        quota_name: Optional[str] = None,
        before: Optional[float] = None,
    ) -> int:
        """Clear old usage records."""
        async with self._lock:
            original = len(self._records)
            
            if quota_name is not None:
                self._records = [r for r in self._records if r.quota_name != quota_name]
            
            if before is not None:
                self._records = [r for r in self._records if r.timestamp >= before]
            
            return original - len(self._records)


class CostCalculator(ABC):
    """Abstract cost calculator."""
    
    @abstractmethod
    def calculate(self, value: Any) -> float:
        """Calculate cost for a value."""
        pass


class FixedCostCalculator(CostCalculator):
    """Fixed cost per operation."""
    
    def __init__(self, cost: float = 1.0):
        self.cost = cost
    
    def calculate(self, value: Any) -> float:
        return self.cost


class TokenCostCalculator(CostCalculator):
    """Token-based cost calculation."""
    
    def __init__(
        self,
        input_cost: float = 0.001,
        output_cost: float = 0.002,
    ):
        self.input_cost = input_cost
        self.output_cost = output_cost
    
    def calculate(self, value: Any) -> float:
        """Calculate cost based on token counts."""
        if isinstance(value, dict):
            input_tokens = value.get("input_tokens", 0)
            output_tokens = value.get("output_tokens", 0)
            return (input_tokens * self.input_cost) + (output_tokens * self.output_cost)
        
        if isinstance(value, str):
            # Rough token estimate
            return len(value.split()) * self.input_cost
        
        return 0.0


class CallableCostCalculator(CostCalculator):
    """Cost calculation using a custom function."""
    
    def __init__(self, func: Callable[[Any], float]):
        self.func = func
    
    def calculate(self, value: Any) -> float:
        return self.func(value)


class Quota:
    """
    A single quota with multiple period limits.
    """
    
    def __init__(
        self,
        name: str,
        limits: Optional[Dict[QuotaPeriod, float]] = None,
        cost_calculator: Optional[CostCalculator] = None,
    ):
        """
        Initialize quota.
        
        Args:
            name: Quota name
            limits: Period limits (e.g., {QuotaPeriod.DAY: 1000})
            cost_calculator: Optional cost calculator
        """
        self.name = name
        self._limits: Dict[QuotaPeriod, QuotaLimit] = {}
        self._cost_calculator = cost_calculator or FixedCostCalculator()
        self._lock = asyncio.Lock()
        
        if limits:
            for period, limit in limits.items():
                self._limits[period] = QuotaLimit(period=period, limit=limit)
    
    def set_limit(self, period: QuotaPeriod, limit: float) -> 'Quota':
        """Set a limit for a period."""
        self._limits[period] = QuotaLimit(period=period, limit=limit)
        return self
    
    def get_limit(self, period: QuotaPeriod) -> Optional[QuotaLimit]:
        """Get limit for a period."""
        return self._limits.get(period)
    
    async def check(self, amount: float = 1.0) -> bool:
        """Check if quota allows the amount."""
        async with self._lock:
            for limit in self._limits.values():
                if limit.should_reset():
                    limit.reset()
                
                if limit.current + amount > limit.limit:
                    return False
            
            return True
    
    async def consume(self, amount: float = 1.0) -> None:
        """Consume quota amount."""
        async with self._lock:
            for limit in self._limits.values():
                if limit.should_reset():
                    limit.reset()
                
                if limit.current + amount > limit.limit:
                    raise QuotaExceeded(
                        f"Quota '{self.name}' exceeded for period {limit.period.value}",
                        quota_name=self.name,
                        current=limit.current,
                        limit=limit.limit,
                        reset_time=limit.reset_time(),
                    )
            
            # Consume from all periods
            for limit in self._limits.values():
                limit.current += amount
    
    async def release(self, amount: float) -> None:
        """Release consumed quota (for refunds)."""
        async with self._lock:
            for limit in self._limits.values():
                limit.current = max(0, limit.current - amount)
    
    def remaining(self) -> Dict[QuotaPeriod, float]:
        """Get remaining quota for all periods."""
        return {
            period: limit.remaining
            for period, limit in self._limits.items()
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "limits": {
                period.value: limit.to_dict()
                for period, limit in self._limits.items()
            },
        }


class QuotaManager:
    """
    Central quota management system.
    """
    
    def __init__(self, usage_store: Optional[UsageStore] = None):
        """
        Initialize quota manager.
        
        Args:
            usage_store: Optional usage data store
        """
        self._quotas: Dict[str, Quota] = {}
        self._usage_store = usage_store or InMemoryUsageStore()
        self._listeners: List[Callable[[UsageRecord], None]] = []
    
    def set_quota(
        self,
        name: str,
        minute: Optional[float] = None,
        hour: Optional[float] = None,
        daily: Optional[float] = None,
        weekly: Optional[float] = None,
        monthly: Optional[float] = None,
        yearly: Optional[float] = None,
        total: Optional[float] = None,
        cost_calculator: Optional[CostCalculator] = None,
    ) -> Quota:
        """
        Set quota limits.
        
        Args:
            name: Quota name
            minute: Minute limit
            hour: Hour limit
            daily: Daily limit
            weekly: Weekly limit
            monthly: Monthly limit
            yearly: Yearly limit
            total: Total limit (never resets)
            cost_calculator: Optional cost calculator
            
        Returns:
            Created quota
        """
        limits = {}
        
        if minute is not None:
            limits[QuotaPeriod.MINUTE] = minute
        if hour is not None:
            limits[QuotaPeriod.HOUR] = hour
        if daily is not None:
            limits[QuotaPeriod.DAY] = daily
        if weekly is not None:
            limits[QuotaPeriod.WEEK] = weekly
        if monthly is not None:
            limits[QuotaPeriod.MONTH] = monthly
        if yearly is not None:
            limits[QuotaPeriod.YEAR] = yearly
        if total is not None:
            limits[QuotaPeriod.TOTAL] = total
        
        quota = Quota(name, limits, cost_calculator)
        self._quotas[name] = quota
        
        return quota
    
    def get_quota(self, name: str) -> Optional[Quota]:
        """Get a quota by name."""
        return self._quotas.get(name)
    
    async def check(self, name: str, amount: float = 1.0) -> bool:
        """Check if quota allows the amount."""
        quota = self._quotas.get(name)
        if quota is None:
            return True
        
        return await quota.check(amount)
    
    async def consume(
        self,
        name: str,
        amount: float = 1.0,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Consume quota and record usage.
        
        Args:
            name: Quota name
            amount: Amount to consume
            user_id: Optional user ID
            metadata: Optional metadata
        """
        quota = self._quotas.get(name)
        if quota is None:
            return
        
        await quota.consume(amount)
        
        # Record usage
        record = UsageRecord(
            quota_name=name,
            amount=amount,
            timestamp=time.time(),
            user_id=user_id,
            metadata=metadata or {},
        )
        
        await self._usage_store.record(record)
        
        # Notify listeners
        for listener in self._listeners:
            try:
                listener(record)
            except Exception as e:
                logger.warning(f"Listener error: {e}")
    
    @asynccontextmanager
    async def track(
        self,
        name: str,
        amount: float = 1.0,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Context manager to track quota usage.
        
        Example:
            async with quota_manager.track("api_calls"):
                result = await api_call()
        """
        await self.consume(name, amount, user_id, metadata)
        yield
    
    async def get_stats(self, name: str) -> Optional[QuotaStats]:
        """Get quota statistics."""
        quota = self._quotas.get(name)
        if quota is None:
            return None
        
        usage = await self._usage_store.get_usage(name)
        total = sum(r.amount for r in usage)
        
        return QuotaStats(
            quota_name=name,
            limits={
                period.value: limit
                for period, limit in quota._limits.items()
            },
            total_usage=total,
            usage_history=usage[-100:],  # Last 100 records
        )
    
    def add_listener(self, listener: Callable[[UsageRecord], None]) -> None:
        """Add usage listener."""
        self._listeners.append(listener)
    
    async def get_usage_report(
        self,
        since: Optional[float] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate usage report."""
        report = {
            "generated_at": datetime.now().isoformat(),
            "quotas": {},
        }
        
        for name, quota in self._quotas.items():
            total = await self._usage_store.get_total(name, since, user_id)
            report["quotas"][name] = {
                "total_usage": total,
                "limits": quota.to_dict()["limits"],
            }
        
        return report
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "quotas": {
                name: quota.to_dict()
                for name, quota in self._quotas.items()
            },
        }


class UserQuotaManager:
    """
    Per-user quota management.
    """
    
    def __init__(
        self,
        default_quotas: Optional[Dict[str, Dict[QuotaPeriod, float]]] = None,
        usage_store: Optional[UsageStore] = None,
    ):
        """
        Initialize user quota manager.
        
        Args:
            default_quotas: Default quota limits for new users
            usage_store: Optional usage store
        """
        self._default_quotas = default_quotas or {}
        self._user_managers: Dict[str, QuotaManager] = {}
        self._usage_store = usage_store or InMemoryUsageStore()
    
    def get_manager(self, user_id: str) -> QuotaManager:
        """Get quota manager for a user."""
        if user_id not in self._user_managers:
            manager = QuotaManager(self._usage_store)
            
            # Apply default quotas
            for name, limits in self._default_quotas.items():
                quota = Quota(name, limits)
                manager._quotas[name] = quota
            
            self._user_managers[user_id] = manager
        
        return self._user_managers[user_id]
    
    async def check(self, user_id: str, quota_name: str, amount: float = 1.0) -> bool:
        """Check if user quota allows the amount."""
        manager = self.get_manager(user_id)
        return await manager.check(quota_name, amount)
    
    async def consume(
        self,
        user_id: str,
        quota_name: str,
        amount: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Consume user quota."""
        manager = self.get_manager(user_id)
        await manager.consume(quota_name, amount, user_id, metadata)
    
    async def get_user_stats(
        self,
        user_id: str,
        quota_name: str,
    ) -> Optional[QuotaStats]:
        """Get stats for a specific user quota."""
        manager = self.get_manager(user_id)
        return await manager.get_stats(quota_name)


class BillingIntegration(ABC):
    """Abstract billing integration."""
    
    @abstractmethod
    async def record_usage(
        self,
        user_id: str,
        product: str,
        quantity: float,
        unit_price: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Record billable usage.
        
        Returns:
            Usage record ID
        """
        pass
    
    @abstractmethod
    async def get_invoice(self, user_id: str, period: str) -> Dict[str, Any]:
        """Get invoice for a user."""
        pass


class InMemoryBilling(BillingIntegration):
    """In-memory billing for testing."""
    
    def __init__(self):
        self._records: List[Dict[str, Any]] = []
        self._record_id = 0
    
    async def record_usage(
        self,
        user_id: str,
        product: str,
        quantity: float,
        unit_price: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Record billable usage."""
        self._record_id += 1
        record = {
            "id": str(self._record_id),
            "user_id": user_id,
            "product": product,
            "quantity": quantity,
            "unit_price": unit_price,
            "total": quantity * unit_price,
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat(),
        }
        self._records.append(record)
        return record["id"]
    
    async def get_invoice(self, user_id: str, period: str) -> Dict[str, Any]:
        """Get invoice for a user."""
        user_records = [r for r in self._records if r["user_id"] == user_id]
        total = sum(r["total"] for r in user_records)
        
        return {
            "user_id": user_id,
            "period": period,
            "items": user_records,
            "total": total,
        }


class BillableQuotaManager(QuotaManager):
    """
    Quota manager with billing integration.
    """
    
    def __init__(
        self,
        billing: BillingIntegration,
        usage_store: Optional[UsageStore] = None,
    ):
        """
        Initialize billable quota manager.
        
        Args:
            billing: Billing integration
            usage_store: Optional usage store
        """
        super().__init__(usage_store)
        self._billing = billing
        self._prices: Dict[str, float] = {}
    
    def set_price(self, quota_name: str, unit_price: float) -> 'BillableQuotaManager':
        """Set price per unit for a quota."""
        self._prices[quota_name] = unit_price
        return self
    
    async def consume(
        self,
        name: str,
        amount: float = 1.0,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Consume quota and record billing."""
        await super().consume(name, amount, user_id, metadata)
        
        # Record billing if price is set
        if name in self._prices and user_id:
            await self._billing.record_usage(
                user_id=user_id,
                product=name,
                quantity=amount,
                unit_price=self._prices[name],
                metadata=metadata,
            )


# Global quota manager
_quota_manager: Optional[QuotaManager] = None


def get_quota_manager() -> QuotaManager:
    """Get global quota manager."""
    global _quota_manager
    if _quota_manager is None:
        _quota_manager = QuotaManager()
    return _quota_manager


def enforce_quota(
    name: str,
    amount: float = 1.0,
    cost: Optional[Callable[[Any], float]] = None,
    user_id_param: Optional[str] = None,
) -> Callable:
    """
    Decorator to enforce quota limits.
    
    Example:
        @enforce_quota("api_calls")
        async def call_api():
            ...
        
        @enforce_quota("tokens", cost=lambda r: r.token_count)
        async def generate():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            manager = get_quota_manager()
            
            # Determine user ID
            uid = kwargs.get(user_id_param) if user_id_param else None
            
            # Pre-check quota
            if cost is None:
                await manager.consume(name, amount, uid)
                return await func(*args, **kwargs)
            else:
                # Post-calculate cost
                result = await func(*args, **kwargs)
                calculated_cost = cost(result)
                await manager.consume(name, calculated_cost, uid)
                return result
        
        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            return asyncio.run(async_wrapper(*args, **kwargs))
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


def require_quota(name: str, amount: float = 1.0) -> Callable:
    """
    Decorator to check quota before execution (no consumption).
    
    Example:
        @require_quota("premium_features")
        async def premium_operation():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            manager = get_quota_manager()
            
            if not await manager.check(name, amount):
                quota = manager.get_quota(name)
                raise QuotaExceeded(
                    f"Insufficient quota for '{name}'",
                    quota_name=name,
                    current=0,
                    limit=0,
                )
            
            return await func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            return asyncio.run(async_wrapper(*args, **kwargs))
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


__all__ = [
    # Exceptions
    "QuotaError",
    "QuotaExceeded",
    # Enums
    "QuotaPeriod",
    # Data classes
    "QuotaLimit",
    "UsageRecord",
    "QuotaStats",
    # Stores
    "UsageStore",
    "InMemoryUsageStore",
    # Cost calculators
    "CostCalculator",
    "FixedCostCalculator",
    "TokenCostCalculator",
    "CallableCostCalculator",
    # Quota
    "Quota",
    "QuotaManager",
    "UserQuotaManager",
    # Billing
    "BillingIntegration",
    "InMemoryBilling",
    "BillableQuotaManager",
    # Decorators
    "enforce_quota",
    "require_quota",
    # Utilities
    "get_quota_manager",
]
