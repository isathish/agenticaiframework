"""
Enterprise SLA Manager Module.

SLA tracking, uptime monitoring, breach alerts,
and service level reporting.

Example:
    # Create SLA manager
    sla = create_sla_manager()
    
    # Define SLA
    await sla.define(
        name="api_availability",
        target=99.9,
        metric_type=MetricType.UPTIME,
        period=SLAPeriod.MONTHLY,
    )
    
    # Record metric
    await sla.record(
        sla_name="api_availability",
        value=100.0,
        timestamp=datetime.utcnow(),
    )
    
    # Check compliance
    status = await sla.get_status("api_availability")
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


class SLAError(Exception):
    """SLA error."""
    pass


class SLABreach(SLAError):
    """SLA breach."""
    pass


class MetricType(str, Enum):
    """Metric type."""
    UPTIME = "uptime"
    LATENCY = "latency"
    ERROR_RATE = "error_rate"
    THROUGHPUT = "throughput"
    RESPONSE_TIME = "response_time"
    AVAILABILITY = "availability"
    MTTR = "mttr"  # Mean time to recover
    MTBF = "mtbf"  # Mean time between failures
    CUSTOM = "custom"


class SLAPeriod(str, Enum):
    """SLA period."""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class SLAStatus(str, Enum):
    """SLA status."""
    COMPLIANT = "compliant"
    AT_RISK = "at_risk"
    BREACHED = "breached"
    UNKNOWN = "unknown"


class AlertSeverity(str, Enum):
    """Alert severity."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class MetricRecord:
    """Metric record."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sla_id: str = ""
    value: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    source: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SLADefinition:
    """SLA definition."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    metric_type: MetricType = MetricType.UPTIME
    target: float = 99.9
    warning_threshold: float = 99.5
    period: SLAPeriod = SLAPeriod.MONTHLY
    
    # Comparison
    higher_is_better: bool = True  # For latency, lower is better
    
    # Service info
    service: str = ""
    owner: str = ""
    
    # Enabled
    enabled: bool = True
    
    # Dates
    created_at: datetime = field(default_factory=datetime.utcnow)
    effective_from: Optional[datetime] = None
    effective_until: Optional[datetime] = None
    
    # Metadata
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SLAStatusReport:
    """SLA status report."""
    sla_id: str = ""
    sla_name: str = ""
    status: SLAStatus = SLAStatus.UNKNOWN
    current_value: float = 0.0
    target: float = 0.0
    variance: float = 0.0
    period_start: datetime = field(default_factory=datetime.utcnow)
    period_end: datetime = field(default_factory=datetime.utcnow)
    records_count: int = 0
    is_breached: bool = False
    breach_duration: Optional[timedelta] = None
    error_budget_remaining: float = 100.0


@dataclass
class SLAAlert:
    """SLA alert."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sla_id: str = ""
    sla_name: str = ""
    severity: AlertSeverity = AlertSeverity.WARNING
    status: SLAStatus = SLAStatus.AT_RISK
    current_value: float = 0.0
    target: float = 0.0
    message: str = ""
    triggered_at: datetime = field(default_factory=datetime.utcnow)
    acknowledged: bool = False
    resolved: bool = False


@dataclass
class ErrorBudget:
    """Error budget."""
    sla_id: str = ""
    total_minutes: float = 0.0
    consumed_minutes: float = 0.0
    remaining_minutes: float = 0.0
    remaining_percentage: float = 100.0
    period_start: datetime = field(default_factory=datetime.utcnow)
    period_end: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SLAStats:
    """SLA statistics."""
    total_slas: int = 0
    compliant: int = 0
    at_risk: int = 0
    breached: int = 0
    avg_compliance: float = 0.0


# SLA store
class SLAStore(ABC):
    """SLA storage."""
    
    @abstractmethod
    async def save(self, sla: SLADefinition) -> None:
        pass
    
    @abstractmethod
    async def get(self, sla_id: str) -> Optional[SLADefinition]:
        pass
    
    @abstractmethod
    async def get_by_name(self, name: str) -> Optional[SLADefinition]:
        pass
    
    @abstractmethod
    async def list_all(self) -> List[SLADefinition]:
        pass
    
    @abstractmethod
    async def delete(self, sla_id: str) -> bool:
        pass


class InMemorySLAStore(SLAStore):
    """In-memory SLA store."""
    
    def __init__(self):
        self._slas: Dict[str, SLADefinition] = {}
        self._by_name: Dict[str, str] = {}
    
    async def save(self, sla: SLADefinition) -> None:
        self._slas[sla.id] = sla
        self._by_name[sla.name] = sla.id
    
    async def get(self, sla_id: str) -> Optional[SLADefinition]:
        return self._slas.get(sla_id)
    
    async def get_by_name(self, name: str) -> Optional[SLADefinition]:
        sla_id = self._by_name.get(name)
        if sla_id:
            return self._slas.get(sla_id)
        return None
    
    async def list_all(self) -> List[SLADefinition]:
        return list(self._slas.values())
    
    async def delete(self, sla_id: str) -> bool:
        sla = self._slas.get(sla_id)
        if sla:
            del self._slas[sla_id]
            self._by_name.pop(sla.name, None)
            return True
        return False


# Metric store
class MetricStore(ABC):
    """Metric storage."""
    
    @abstractmethod
    async def save(self, record: MetricRecord) -> None:
        pass
    
    @abstractmethod
    async def list_by_sla(
        self,
        sla_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> List[MetricRecord]:
        pass
    
    @abstractmethod
    async def get_average(
        self,
        sla_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> Optional[float]:
        pass


class InMemoryMetricStore(MetricStore):
    """In-memory metric store."""
    
    def __init__(self, max_records: int = 1000000):
        self._records: Dict[str, MetricRecord] = {}
        self._by_sla: Dict[str, List[str]] = {}
        self._max_records = max_records
    
    async def save(self, record: MetricRecord) -> None:
        self._records[record.id] = record
        
        if record.sla_id not in self._by_sla:
            self._by_sla[record.sla_id] = []
        
        self._by_sla[record.sla_id].append(record.id)
        
        # Trim old records
        if len(self._records) > self._max_records:
            oldest = list(self._records.keys())[0]
            del self._records[oldest]
    
    async def list_by_sla(
        self,
        sla_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> List[MetricRecord]:
        record_ids = self._by_sla.get(sla_id, [])
        records = []
        
        for record_id in record_ids:
            record = self._records.get(record_id)
            if record:
                if start_date <= record.timestamp <= end_date:
                    records.append(record)
        
        return sorted(records, key=lambda r: r.timestamp)
    
    async def get_average(
        self,
        sla_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> Optional[float]:
        records = await self.list_by_sla(sla_id, start_date, end_date)
        
        if not records:
            return None
        
        return sum(r.value for r in records) / len(records)


# Period calculator
class PeriodCalculator:
    """SLA period calculator."""
    
    @staticmethod
    def get_period_range(
        period: SLAPeriod,
        reference: Optional[datetime] = None,
    ) -> Tuple[datetime, datetime]:
        """Get period start and end dates."""
        ref = reference or datetime.utcnow()
        
        if period == SLAPeriod.HOURLY:
            start = ref.replace(minute=0, second=0, microsecond=0)
            end = start + timedelta(hours=1) - timedelta(microseconds=1)
        
        elif period == SLAPeriod.DAILY:
            start = ref.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1) - timedelta(microseconds=1)
        
        elif period == SLAPeriod.WEEKLY:
            start = ref - timedelta(days=ref.weekday())
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=7) - timedelta(microseconds=1)
        
        elif period == SLAPeriod.MONTHLY:
            start = ref.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if ref.month == 12:
                end = start.replace(year=ref.year + 1, month=1)
            else:
                end = start.replace(month=ref.month + 1)
            end = end - timedelta(microseconds=1)
        
        elif period == SLAPeriod.QUARTERLY:
            quarter = (ref.month - 1) // 3
            start_month = quarter * 3 + 1
            start = ref.replace(month=start_month, day=1, hour=0, minute=0, second=0, microsecond=0)
            end_month = start_month + 3
            if end_month > 12:
                end = start.replace(year=ref.year + 1, month=end_month - 12)
            else:
                end = start.replace(month=end_month)
            end = end - timedelta(microseconds=1)
        
        elif period == SLAPeriod.YEARLY:
            start = ref.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            end = start.replace(year=ref.year + 1) - timedelta(microseconds=1)
        
        else:
            start = ref.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1) - timedelta(microseconds=1)
        
        return start, end
    
    @staticmethod
    def get_period_minutes(period: SLAPeriod) -> float:
        """Get total minutes in period."""
        if period == SLAPeriod.HOURLY:
            return 60
        elif period == SLAPeriod.DAILY:
            return 24 * 60
        elif period == SLAPeriod.WEEKLY:
            return 7 * 24 * 60
        elif period == SLAPeriod.MONTHLY:
            return 30 * 24 * 60  # Approximate
        elif period == SLAPeriod.QUARTERLY:
            return 90 * 24 * 60
        elif period == SLAPeriod.YEARLY:
            return 365 * 24 * 60
        return 24 * 60


# SLA manager
class SLAManager:
    """SLA manager."""
    
    def __init__(
        self,
        sla_store: Optional[SLAStore] = None,
        metric_store: Optional[MetricStore] = None,
    ):
        self._sla_store = sla_store or InMemorySLAStore()
        self._metric_store = metric_store or InMemoryMetricStore()
        self._alert_handlers: List[Callable] = []
        self._alerts: List[SLAAlert] = []
        self._triggered_alerts: Set[str] = set()
    
    async def define(
        self,
        name: str,
        target: float,
        metric_type: Union[str, MetricType] = MetricType.UPTIME,
        period: Union[str, SLAPeriod] = SLAPeriod.MONTHLY,
        warning_threshold: Optional[float] = None,
        higher_is_better: bool = True,
        service: str = "",
        owner: str = "",
        **metadata,
    ) -> SLADefinition:
        """Define SLA."""
        if isinstance(metric_type, str):
            metric_type = MetricType(metric_type)
        if isinstance(period, str):
            period = SLAPeriod(period)
        
        if warning_threshold is None:
            # Default warning at 0.5% above target for uptime
            if metric_type == MetricType.UPTIME:
                warning_threshold = max(0, target - 0.4)
            else:
                warning_threshold = target * 0.95
        
        sla = SLADefinition(
            name=name,
            target=target,
            metric_type=metric_type,
            period=period,
            warning_threshold=warning_threshold,
            higher_is_better=higher_is_better,
            service=service,
            owner=owner,
            metadata=metadata,
        )
        
        await self._sla_store.save(sla)
        
        logger.info(f"SLA defined: {name} (target: {target}%)")
        
        return sla
    
    async def get(self, name: str) -> Optional[SLADefinition]:
        """Get SLA by name."""
        return await self._sla_store.get_by_name(name)
    
    async def list_slas(self) -> List[SLADefinition]:
        """List all SLAs."""
        return await self._sla_store.list_all()
    
    async def delete(self, name: str) -> bool:
        """Delete SLA."""
        sla = await self._sla_store.get_by_name(name)
        if sla:
            return await self._sla_store.delete(sla.id)
        return False
    
    async def record(
        self,
        sla_name: str,
        value: float,
        timestamp: Optional[datetime] = None,
        source: str = "",
        **metadata,
    ) -> Optional[MetricRecord]:
        """Record metric value."""
        sla = await self._sla_store.get_by_name(sla_name)
        
        if not sla:
            return None
        
        record = MetricRecord(
            sla_id=sla.id,
            value=value,
            timestamp=timestamp or datetime.utcnow(),
            source=source,
            metadata=metadata,
        )
        
        await self._metric_store.save(record)
        
        # Check for breaches
        await self._check_sla(sla)
        
        return record
    
    async def get_status(self, sla_name: str) -> Optional[SLAStatusReport]:
        """Get current SLA status."""
        sla = await self._sla_store.get_by_name(sla_name)
        
        if not sla:
            return None
        
        period_start, period_end = PeriodCalculator.get_period_range(sla.period)
        
        avg_value = await self._metric_store.get_average(
            sla.id,
            period_start,
            period_end,
        )
        
        records = await self._metric_store.list_by_sla(
            sla.id,
            period_start,
            period_end,
        )
        
        if avg_value is None:
            return SLAStatusReport(
                sla_id=sla.id,
                sla_name=sla.name,
                status=SLAStatus.UNKNOWN,
                target=sla.target,
                period_start=period_start,
                period_end=period_end,
            )
        
        # Determine status
        variance = avg_value - sla.target
        if not sla.higher_is_better:
            variance = -variance
        
        if sla.higher_is_better:
            is_compliant = avg_value >= sla.target
            is_at_risk = avg_value < sla.target and avg_value >= sla.warning_threshold
        else:
            is_compliant = avg_value <= sla.target
            is_at_risk = avg_value > sla.target and avg_value <= sla.warning_threshold
        
        if is_compliant:
            status = SLAStatus.COMPLIANT
        elif is_at_risk:
            status = SLAStatus.AT_RISK
        else:
            status = SLAStatus.BREACHED
        
        # Calculate error budget
        error_budget = await self.get_error_budget(sla_name)
        error_budget_remaining = error_budget.remaining_percentage if error_budget else 100.0
        
        return SLAStatusReport(
            sla_id=sla.id,
            sla_name=sla.name,
            status=status,
            current_value=avg_value,
            target=sla.target,
            variance=variance,
            period_start=period_start,
            period_end=period_end,
            records_count=len(records),
            is_breached=status == SLAStatus.BREACHED,
            error_budget_remaining=error_budget_remaining,
        )
    
    async def get_error_budget(self, sla_name: str) -> Optional[ErrorBudget]:
        """Calculate error budget."""
        sla = await self._sla_store.get_by_name(sla_name)
        
        if not sla:
            return None
        
        period_start, period_end = PeriodCalculator.get_period_range(sla.period)
        total_minutes = PeriodCalculator.get_period_minutes(sla.period)
        
        # Error budget = (100 - target) * total_minutes / 100
        allowed_downtime = (100 - sla.target) * total_minutes / 100
        
        # Get actual downtime from records
        records = await self._metric_store.list_by_sla(
            sla.id,
            period_start,
            period_end,
        )
        
        consumed = 0.0
        for record in records:
            if record.value < sla.target:
                # Simple calculation: assume each record represents 1 minute
                consumed += (sla.target - record.value) / 100
        
        remaining = max(0, allowed_downtime - consumed)
        remaining_pct = (remaining / allowed_downtime * 100) if allowed_downtime > 0 else 100
        
        return ErrorBudget(
            sla_id=sla.id,
            total_minutes=allowed_downtime,
            consumed_minutes=consumed,
            remaining_minutes=remaining,
            remaining_percentage=remaining_pct,
            period_start=period_start,
            period_end=period_end,
        )
    
    async def get_all_statuses(self) -> List[SLAStatusReport]:
        """Get status of all SLAs."""
        slas = await self._sla_store.list_all()
        statuses = []
        
        for sla in slas:
            if sla.enabled:
                status = await self.get_status(sla.name)
                if status:
                    statuses.append(status)
        
        return statuses
    
    async def get_breached_slas(self) -> List[SLAStatusReport]:
        """Get breached SLAs."""
        statuses = await self.get_all_statuses()
        return [s for s in statuses if s.status == SLAStatus.BREACHED]
    
    async def get_at_risk_slas(self) -> List[SLAStatusReport]:
        """Get at-risk SLAs."""
        statuses = await self.get_all_statuses()
        return [s for s in statuses if s.status == SLAStatus.AT_RISK]
    
    async def get_stats(self) -> SLAStats:
        """Get SLA statistics."""
        statuses = await self.get_all_statuses()
        
        stats = SLAStats(total_slas=len(statuses))
        
        compliance_values = []
        
        for status in statuses:
            if status.status == SLAStatus.COMPLIANT:
                stats.compliant += 1
            elif status.status == SLAStatus.AT_RISK:
                stats.at_risk += 1
            elif status.status == SLAStatus.BREACHED:
                stats.breached += 1
            
            if status.current_value > 0:
                compliance_values.append(status.current_value)
        
        if compliance_values:
            stats.avg_compliance = sum(compliance_values) / len(compliance_values)
        
        return stats
    
    def add_alert_handler(self, handler: Callable) -> None:
        """Add alert handler."""
        self._alert_handlers.append(handler)
    
    def get_alerts(self, include_resolved: bool = False) -> List[SLAAlert]:
        """Get alerts."""
        if include_resolved:
            return self._alerts.copy()
        return [a for a in self._alerts if not a.resolved]
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge alert."""
        for alert in self._alerts:
            if alert.id == alert_id:
                alert.acknowledged = True
                return True
        return False
    
    async def _check_sla(self, sla: SLADefinition) -> None:
        """Check SLA and trigger alerts."""
        status = await self.get_status(sla.name)
        
        if not status:
            return
        
        alert_key = f"{sla.id}:{status.status.value}"
        
        if status.status in (SLAStatus.AT_RISK, SLAStatus.BREACHED):
            if alert_key not in self._triggered_alerts:
                self._triggered_alerts.add(alert_key)
                
                severity = (
                    AlertSeverity.CRITICAL if status.status == SLAStatus.BREACHED
                    else AlertSeverity.WARNING
                )
                
                alert = SLAAlert(
                    sla_id=sla.id,
                    sla_name=sla.name,
                    severity=severity,
                    status=status.status,
                    current_value=status.current_value,
                    target=sla.target,
                    message=f"SLA '{sla.name}' is {status.status.value}: "
                            f"{status.current_value:.2f}% (target: {sla.target}%)",
                )
                
                self._alerts.append(alert)
                await self._notify_alert(alert)
        
        elif status.status == SLAStatus.COMPLIANT:
            # Clear triggered alerts for this SLA
            to_remove = [k for k in self._triggered_alerts if k.startswith(f"{sla.id}:")]
            for k in to_remove:
                self._triggered_alerts.discard(k)
    
    async def _notify_alert(self, alert: SLAAlert) -> None:
        """Notify alert handlers."""
        level = logging.WARNING if alert.severity == AlertSeverity.WARNING else logging.ERROR
        logger.log(level, f"SLA Alert: {alert.message}")
        
        for handler in self._alert_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(alert)
                else:
                    handler(alert)
            except Exception as e:
                logger.error(f"Alert handler error: {e}")


# Factory functions
def create_sla_manager() -> SLAManager:
    """Create SLA manager."""
    return SLAManager()


def create_sla_definition(
    name: str,
    target: float,
    **kwargs,
) -> SLADefinition:
    """Create SLA definition."""
    return SLADefinition(name=name, target=target, **kwargs)


__all__ = [
    # Exceptions
    "SLAError",
    "SLABreach",
    # Enums
    "MetricType",
    "SLAPeriod",
    "SLAStatus",
    "AlertSeverity",
    # Data classes
    "MetricRecord",
    "SLADefinition",
    "SLAStatusReport",
    "SLAAlert",
    "ErrorBudget",
    "SLAStats",
    # Stores
    "SLAStore",
    "InMemorySLAStore",
    "MetricStore",
    "InMemoryMetricStore",
    # Utilities
    "PeriodCalculator",
    # Manager
    "SLAManager",
    # Factory functions
    "create_sla_manager",
    "create_sla_definition",
]
