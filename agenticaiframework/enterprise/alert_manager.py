"""
Enterprise Alert Manager Module.

Alerting rules, notifications, escalation,
and incident management.

Example:
    # Create alert manager
    alerts = create_alert_manager()
    
    # Define alert rule
    alerts.add_rule(
        name="high_cpu",
        condition="cpu_usage > 90",
        severity=AlertSeverity.WARNING,
        for_duration=timedelta(minutes=5),
    )
    
    # Add notification channel
    alerts.add_channel(SlackChannel(webhook_url="..."))
    
    # Evaluate and send alerts
    await alerts.evaluate({"cpu_usage": 95})
    
    # Acknowledge alert
    await alerts.acknowledge(alert_id, by="admin")
"""

from __future__ import annotations

import asyncio
import functools
import json
import logging
import operator
import re
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Pattern,
    Set,
    Tuple,
    TypeVar,
    Union,
)

T = TypeVar('T')


logger = logging.getLogger(__name__)


class AlertError(Exception):
    """Alert error."""
    pass


class AlertNotFoundError(AlertError):
    """Alert not found."""
    pass


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertState(str, Enum):
    """Alert states."""
    PENDING = "pending"
    FIRING = "firing"
    RESOLVED = "resolved"
    ACKNOWLEDGED = "acknowledged"
    SILENCED = "silenced"


class EscalationLevel(int, Enum):
    """Escalation levels."""
    L1 = 1
    L2 = 2
    L3 = 3


@dataclass
class AlertRule:
    """Alert rule definition."""
    name: str
    condition: str
    severity: AlertSeverity = AlertSeverity.WARNING
    description: str = ""
    for_duration: timedelta = field(default_factory=lambda: timedelta(minutes=0))
    labels: Dict[str, str] = field(default_factory=dict)
    annotations: Dict[str, str] = field(default_factory=dict)
    enabled: bool = True
    channels: List[str] = field(default_factory=list)
    escalation_policy: Optional[str] = None
    runbook_url: Optional[str] = None


@dataclass
class Alert:
    """Active alert."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    rule_name: str = ""
    state: AlertState = AlertState.PENDING
    severity: AlertSeverity = AlertSeverity.WARNING
    message: str = ""
    description: str = ""
    labels: Dict[str, str] = field(default_factory=dict)
    annotations: Dict[str, str] = field(default_factory=dict)
    value: Any = None
    threshold: Any = None
    started_at: datetime = field(default_factory=datetime.utcnow)
    fired_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    silenced_until: Optional[datetime] = None
    notification_count: int = 0
    last_notified_at: Optional[datetime] = None
    escalation_level: EscalationLevel = EscalationLevel.L1
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Silence:
    """Alert silence."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    matchers: Dict[str, str] = field(default_factory=dict)
    starts_at: datetime = field(default_factory=datetime.utcnow)
    ends_at: Optional[datetime] = None
    created_by: str = ""
    comment: str = ""


@dataclass
class EscalationPolicy:
    """Escalation policy."""
    name: str
    levels: List["EscalationStep"] = field(default_factory=list)
    repeat_interval: timedelta = field(default_factory=lambda: timedelta(hours=1))


@dataclass
class EscalationStep:
    """Escalation step."""
    level: EscalationLevel
    delay: timedelta
    channels: List[str] = field(default_factory=list)
    users: List[str] = field(default_factory=list)


@dataclass
class NotificationResult:
    """Notification result."""
    success: bool
    channel: str
    alert_id: str
    sent_at: datetime = field(default_factory=datetime.utcnow)
    error: Optional[str] = None


@dataclass
class AlertStats:
    """Alert statistics."""
    total_alerts: int = 0
    firing_alerts: int = 0
    resolved_alerts: int = 0
    acknowledged_alerts: int = 0
    alerts_by_severity: Dict[str, int] = field(default_factory=dict)
    alerts_by_rule: Dict[str, int] = field(default_factory=dict)


# Notification channels
class NotificationChannel(ABC):
    """Abstract notification channel."""
    
    name: str = "channel"
    
    @abstractmethod
    async def send(self, alert: Alert) -> NotificationResult:
        """Send notification."""
        pass


class LogChannel(NotificationChannel):
    """Log notification channel."""
    
    name = "log"
    
    async def send(self, alert: Alert) -> NotificationResult:
        """Log alert."""
        logger.warning(
            f"[{alert.severity.value.upper()}] {alert.rule_name}: {alert.message}"
        )
        return NotificationResult(
            success=True,
            channel=self.name,
            alert_id=alert.id,
        )


class WebhookChannel(NotificationChannel):
    """Webhook notification channel."""
    
    def __init__(self, url: str, headers: Optional[Dict[str, str]] = None):
        self.url = url
        self.headers = headers or {}
        self.name = "webhook"
    
    async def send(self, alert: Alert) -> NotificationResult:
        """Send webhook notification."""
        try:
            # Simple HTTP client without external dependencies
            import urllib.request
            
            payload = json.dumps({
                "alert_id": alert.id,
                "rule_name": alert.rule_name,
                "severity": alert.severity.value,
                "message": alert.message,
                "state": alert.state.value,
                "labels": alert.labels,
                "started_at": alert.started_at.isoformat(),
            }).encode()
            
            req = urllib.request.Request(
                self.url,
                data=payload,
                headers={"Content-Type": "application/json", **self.headers},
                method="POST",
            )
            
            with urllib.request.urlopen(req, timeout=10) as resp:
                success = resp.status < 400
            
            return NotificationResult(
                success=success,
                channel=self.name,
                alert_id=alert.id,
            )
        except Exception as e:
            return NotificationResult(
                success=False,
                channel=self.name,
                alert_id=alert.id,
                error=str(e),
            )


class EmailChannel(NotificationChannel):
    """Email notification channel (mock)."""
    
    def __init__(
        self,
        recipients: List[str],
        smtp_host: str = "localhost",
        smtp_port: int = 25,
    ):
        self.recipients = recipients
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.name = "email"
    
    async def send(self, alert: Alert) -> NotificationResult:
        """Send email notification (mock)."""
        logger.info(
            f"Email: [{alert.severity.value}] {alert.rule_name} -> {self.recipients}"
        )
        return NotificationResult(
            success=True,
            channel=self.name,
            alert_id=alert.id,
        )


class SlackChannel(NotificationChannel):
    """Slack notification channel."""
    
    def __init__(self, webhook_url: str, channel: Optional[str] = None):
        self.webhook_url = webhook_url
        self.channel = channel
        self.name = "slack"
    
    async def send(self, alert: Alert) -> NotificationResult:
        """Send Slack notification."""
        try:
            import urllib.request
            
            color = {
                AlertSeverity.INFO: "#36a64f",
                AlertSeverity.WARNING: "#ff9800",
                AlertSeverity.ERROR: "#ff5722",
                AlertSeverity.CRITICAL: "#f44336",
            }.get(alert.severity, "#808080")
            
            payload = json.dumps({
                "attachments": [{
                    "color": color,
                    "title": f"[{alert.severity.value.upper()}] {alert.rule_name}",
                    "text": alert.message,
                    "fields": [
                        {"title": "State", "value": alert.state.value, "short": True},
                        {"title": "Started", "value": alert.started_at.isoformat(), "short": True},
                    ],
                }]
            }).encode()
            
            req = urllib.request.Request(
                self.webhook_url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            
            with urllib.request.urlopen(req, timeout=10):
                pass
            
            return NotificationResult(
                success=True,
                channel=self.name,
                alert_id=alert.id,
            )
        except Exception as e:
            return NotificationResult(
                success=False,
                channel=self.name,
                alert_id=alert.id,
                error=str(e),
            )


# Condition evaluator
class ConditionEvaluator:
    """Evaluate alert conditions."""
    
    OPERATORS = {
        ">": operator.gt,
        "<": operator.lt,
        ">=": operator.ge,
        "<=": operator.le,
        "==": operator.eq,
        "!=": operator.ne,
    }
    
    def evaluate(
        self,
        condition: str,
        values: Dict[str, Any],
    ) -> Tuple[bool, Any, Any]:
        """
        Evaluate condition.
        
        Returns:
            (result, actual_value, threshold)
        """
        # Parse simple conditions like "cpu_usage > 90"
        pattern = r"(\w+)\s*(>|<|>=|<=|==|!=)\s*(\d+\.?\d*)"
        match = re.match(pattern, condition.strip())
        
        if not match:
            return False, None, None
        
        metric, op_str, threshold_str = match.groups()
        threshold = float(threshold_str)
        
        if metric not in values:
            return False, None, threshold
        
        value = values[metric]
        op_func = self.OPERATORS.get(op_str, operator.gt)
        
        try:
            result = op_func(float(value), threshold)
            return result, value, threshold
        except (TypeError, ValueError):
            return False, value, threshold


# Alert manager
class AlertManager:
    """
    Alert management service.
    """
    
    def __init__(
        self,
        evaluation_interval: float = 60.0,
        notification_interval: float = 300.0,
    ):
        self._rules: Dict[str, AlertRule] = {}
        self._alerts: Dict[str, Alert] = {}
        self._silences: Dict[str, Silence] = {}
        self._channels: Dict[str, NotificationChannel] = {
            "log": LogChannel(),
        }
        self._policies: Dict[str, EscalationPolicy] = {}
        self._evaluator = ConditionEvaluator()
        self._evaluation_interval = evaluation_interval
        self._notification_interval = notification_interval
        self._pending_since: Dict[str, datetime] = {}
        self._running = False
        self._evaluation_task: Optional[asyncio.Task] = None
        self._hooks: Dict[str, List[Callable]] = defaultdict(list)
    
    def add_rule(
        self,
        name: str,
        condition: str,
        severity: AlertSeverity = AlertSeverity.WARNING,
        description: str = "",
        for_duration: timedelta = timedelta(minutes=0),
        channels: Optional[List[str]] = None,
        **kwargs,
    ) -> AlertRule:
        """
        Add alert rule.
        
        Args:
            name: Rule name
            condition: Alert condition
            severity: Alert severity
            description: Rule description
            for_duration: Duration before firing
            channels: Notification channels
            **kwargs: Additional options
            
        Returns:
            Alert rule
        """
        rule = AlertRule(
            name=name,
            condition=condition,
            severity=severity,
            description=description,
            for_duration=for_duration,
            channels=channels or ["log"],
            **kwargs,
        )
        
        self._rules[name] = rule
        return rule
    
    def remove_rule(self, name: str) -> bool:
        """Remove rule."""
        if name in self._rules:
            del self._rules[name]
            return True
        return False
    
    def add_channel(
        self,
        channel: NotificationChannel,
        name: Optional[str] = None,
    ) -> None:
        """Add notification channel."""
        channel_name = name or channel.name
        self._channels[channel_name] = channel
    
    def add_escalation_policy(
        self,
        name: str,
        levels: List[EscalationStep],
        repeat_interval: timedelta = timedelta(hours=1),
    ) -> EscalationPolicy:
        """Add escalation policy."""
        policy = EscalationPolicy(
            name=name,
            levels=levels,
            repeat_interval=repeat_interval,
        )
        self._policies[name] = policy
        return policy
    
    def add_silence(
        self,
        matchers: Dict[str, str],
        duration: timedelta,
        created_by: str = "",
        comment: str = "",
    ) -> Silence:
        """Add silence."""
        silence = Silence(
            matchers=matchers,
            ends_at=datetime.utcnow() + duration,
            created_by=created_by,
            comment=comment,
        )
        self._silences[silence.id] = silence
        return silence
    
    def remove_silence(self, silence_id: str) -> bool:
        """Remove silence."""
        if silence_id in self._silences:
            del self._silences[silence_id]
            return True
        return False
    
    async def evaluate(
        self,
        values: Dict[str, Any],
    ) -> List[Alert]:
        """
        Evaluate all rules against values.
        
        Args:
            values: Metric values
            
        Returns:
            List of triggered alerts
        """
        triggered = []
        now = datetime.utcnow()
        
        for rule in self._rules.values():
            if not rule.enabled:
                continue
            
            result, value, threshold = self._evaluator.evaluate(
                rule.condition, values
            )
            
            if result:
                # Condition is true
                if rule.name not in self._pending_since:
                    self._pending_since[rule.name] = now
                
                pending_duration = now - self._pending_since[rule.name]
                
                if pending_duration >= rule.for_duration:
                    # Create or update alert
                    alert = await self._fire_alert(rule, value, threshold)
                    triggered.append(alert)
            else:
                # Condition is false - resolve if firing
                if rule.name in self._pending_since:
                    del self._pending_since[rule.name]
                
                await self._resolve_by_rule(rule.name)
        
        return triggered
    
    async def _fire_alert(
        self,
        rule: AlertRule,
        value: Any,
        threshold: Any,
    ) -> Alert:
        """Fire or update alert."""
        # Find existing alert for this rule
        existing = None
        for alert in self._alerts.values():
            if alert.rule_name == rule.name and alert.state in (
                AlertState.PENDING, AlertState.FIRING
            ):
                existing = alert
                break
        
        if existing:
            # Update existing
            alert = existing
            if alert.state == AlertState.PENDING:
                alert.state = AlertState.FIRING
                alert.fired_at = datetime.utcnow()
        else:
            # Create new
            alert = Alert(
                rule_name=rule.name,
                state=AlertState.FIRING,
                severity=rule.severity,
                message=f"{rule.name}: {rule.condition}",
                description=rule.description,
                labels=rule.labels.copy(),
                annotations=rule.annotations.copy(),
                value=value,
                threshold=threshold,
                fired_at=datetime.utcnow(),
            )
            self._alerts[alert.id] = alert
        
        # Check silence
        if self._is_silenced(alert):
            alert.state = AlertState.SILENCED
            return alert
        
        # Send notifications
        await self._notify(alert, rule)
        
        await self._trigger_hooks("alert_fired", alert)
        
        return alert
    
    def _is_silenced(self, alert: Alert) -> bool:
        """Check if alert is silenced."""
        now = datetime.utcnow()
        
        for silence in self._silences.values():
            if silence.ends_at and silence.ends_at < now:
                continue
            
            match = all(
                alert.labels.get(k) == v
                for k, v in silence.matchers.items()
            )
            
            if match:
                return True
        
        return False
    
    async def _notify(
        self,
        alert: Alert,
        rule: AlertRule,
    ) -> List[NotificationResult]:
        """Send notifications."""
        results = []
        now = datetime.utcnow()
        
        # Check notification interval
        if alert.last_notified_at:
            since_last = now - alert.last_notified_at
            if since_last.total_seconds() < self._notification_interval:
                return results
        
        for channel_name in rule.channels:
            channel = self._channels.get(channel_name)
            if not channel:
                continue
            
            try:
                result = await channel.send(alert)
                results.append(result)
            except Exception as e:
                results.append(NotificationResult(
                    success=False,
                    channel=channel_name,
                    alert_id=alert.id,
                    error=str(e),
                ))
        
        alert.notification_count += 1
        alert.last_notified_at = now
        
        return results
    
    async def _resolve_by_rule(self, rule_name: str) -> None:
        """Resolve alerts for a rule."""
        for alert in self._alerts.values():
            if (
                alert.rule_name == rule_name and
                alert.state in (AlertState.PENDING, AlertState.FIRING)
            ):
                alert.state = AlertState.RESOLVED
                alert.resolved_at = datetime.utcnow()
                
                await self._trigger_hooks("alert_resolved", alert)
    
    async def acknowledge(
        self,
        alert_id: str,
        by: str,
        comment: Optional[str] = None,
    ) -> Alert:
        """Acknowledge alert."""
        if alert_id not in self._alerts:
            raise AlertNotFoundError(f"Alert not found: {alert_id}")
        
        alert = self._alerts[alert_id]
        alert.state = AlertState.ACKNOWLEDGED
        alert.acknowledged_at = datetime.utcnow()
        alert.acknowledged_by = by
        
        if comment:
            alert.annotations["ack_comment"] = comment
        
        await self._trigger_hooks("alert_acknowledged", alert)
        
        return alert
    
    async def resolve(self, alert_id: str) -> Alert:
        """Manually resolve alert."""
        if alert_id not in self._alerts:
            raise AlertNotFoundError(f"Alert not found: {alert_id}")
        
        alert = self._alerts[alert_id]
        alert.state = AlertState.RESOLVED
        alert.resolved_at = datetime.utcnow()
        
        await self._trigger_hooks("alert_resolved", alert)
        
        return alert
    
    def get_alert(self, alert_id: str) -> Optional[Alert]:
        """Get alert by ID."""
        return self._alerts.get(alert_id)
    
    def get_alerts(
        self,
        state: Optional[AlertState] = None,
        severity: Optional[AlertSeverity] = None,
        rule_name: Optional[str] = None,
    ) -> List[Alert]:
        """Get alerts with filters."""
        results = []
        
        for alert in self._alerts.values():
            if state and alert.state != state:
                continue
            if severity and alert.severity != severity:
                continue
            if rule_name and alert.rule_name != rule_name:
                continue
            results.append(alert)
        
        return sorted(results, key=lambda a: a.started_at, reverse=True)
    
    def get_firing_alerts(self) -> List[Alert]:
        """Get all firing alerts."""
        return self.get_alerts(state=AlertState.FIRING)
    
    async def start(self) -> None:
        """Start alert manager."""
        self._running = True
        logger.info("Alert manager started")
    
    async def stop(self) -> None:
        """Stop alert manager."""
        self._running = False
        if self._evaluation_task:
            self._evaluation_task.cancel()
        logger.info("Alert manager stopped")
    
    def on(self, event: str, handler: Callable) -> None:
        """Add event handler."""
        self._hooks[event].append(handler)
    
    async def _trigger_hooks(self, event: str, *args, **kwargs) -> None:
        """Trigger event hooks."""
        for handler in self._hooks[event]:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(*args, **kwargs)
                else:
                    handler(*args, **kwargs)
            except Exception as e:
                logger.error(f"Hook error: {e}")
    
    def get_stats(self) -> AlertStats:
        """Get alert statistics."""
        stats = AlertStats(total_alerts=len(self._alerts))
        
        for alert in self._alerts.values():
            if alert.state == AlertState.FIRING:
                stats.firing_alerts += 1
            elif alert.state == AlertState.RESOLVED:
                stats.resolved_alerts += 1
            elif alert.state == AlertState.ACKNOWLEDGED:
                stats.acknowledged_alerts += 1
            
            sev_key = alert.severity.value
            stats.alerts_by_severity[sev_key] = (
                stats.alerts_by_severity.get(sev_key, 0) + 1
            )
            
            stats.alerts_by_rule[alert.rule_name] = (
                stats.alerts_by_rule.get(alert.rule_name, 0) + 1
            )
        
        return stats


# Factory functions
def create_alert_manager(
    evaluation_interval: float = 60.0,
    notification_interval: float = 300.0,
) -> AlertManager:
    """Create alert manager."""
    return AlertManager(
        evaluation_interval=evaluation_interval,
        notification_interval=notification_interval,
    )


def create_webhook_channel(
    url: str,
    headers: Optional[Dict[str, str]] = None,
) -> WebhookChannel:
    """Create webhook channel."""
    return WebhookChannel(url, headers)


def create_email_channel(
    recipients: List[str],
    smtp_host: str = "localhost",
) -> EmailChannel:
    """Create email channel."""
    return EmailChannel(recipients, smtp_host)


def create_slack_channel(webhook_url: str) -> SlackChannel:
    """Create Slack channel."""
    return SlackChannel(webhook_url)


__all__ = [
    # Exceptions
    "AlertError",
    "AlertNotFoundError",
    # Enums
    "AlertSeverity",
    "AlertState",
    "EscalationLevel",
    # Data classes
    "AlertRule",
    "Alert",
    "Silence",
    "EscalationPolicy",
    "EscalationStep",
    "NotificationResult",
    "AlertStats",
    # Channels
    "NotificationChannel",
    "LogChannel",
    "WebhookChannel",
    "EmailChannel",
    "SlackChannel",
    # Evaluator
    "ConditionEvaluator",
    # Manager
    "AlertManager",
    # Factory functions
    "create_alert_manager",
    "create_webhook_channel",
    "create_email_channel",
    "create_slack_channel",
]
