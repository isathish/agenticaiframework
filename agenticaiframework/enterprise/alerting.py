"""
Enterprise Alerting Module.

Provides alert management, thresholds, notifications,
escalation policies, and alert routing.

Example:
    # Create alert manager
    alerts = create_alert_manager()
    
    # Define alert rule
    rule = alerts.define_rule(
        name="high_cpu",
        condition=lambda m: m.get("cpu_usage", 0) > 80,
        severity=AlertSeverity.WARNING,
    )
    
    # Add notification channel
    alerts.add_channel(SlackChannel(webhook_url="..."))
    
    # Check metrics and fire alerts
    await alerts.evaluate({"cpu_usage": 95})
"""

from __future__ import annotations

import asyncio
import functools
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    Tuple,
    TypeVar,
)

T = TypeVar('T')


logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    """Alert severity level."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertState(str, Enum):
    """Alert state."""
    PENDING = "pending"
    FIRING = "firing"
    RESOLVED = "resolved"
    SILENCED = "silenced"
    ACKNOWLEDGED = "acknowledged"


@dataclass
class AlertLabels:
    """Alert labels."""
    labels: Dict[str, str] = field(default_factory=dict)
    
    def matches(self, pattern: Dict[str, str]) -> bool:
        """Check if labels match pattern."""
        return all(
            self.labels.get(k) == v
            for k, v in pattern.items()
        )


@dataclass
class Alert:
    """Alert instance."""
    id: str
    name: str
    severity: AlertSeverity
    message: str
    state: AlertState = AlertState.PENDING
    labels: AlertLabels = field(default_factory=AlertLabels)
    annotations: Dict[str, str] = field(default_factory=dict)
    value: Optional[float] = None
    threshold: Optional[float] = None
    started_at: datetime = field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    notification_count: int = 0
    last_notification: Optional[datetime] = None


@dataclass
class AlertRuleConfig:
    """Alert rule configuration."""
    name: str
    condition: Callable[[Dict[str, Any]], bool]
    severity: AlertSeverity = AlertSeverity.WARNING
    message_template: str = "Alert: {name}"
    labels: Dict[str, str] = field(default_factory=dict)
    annotations: Dict[str, str] = field(default_factory=dict)
    for_duration: timedelta = field(default_factory=lambda: timedelta(seconds=0))
    repeat_interval: timedelta = field(default_factory=lambda: timedelta(minutes=5))
    enabled: bool = True


@dataclass
class ThresholdConfig:
    """Threshold configuration."""
    metric_name: str
    operator: str  # >, <, >=, <=, ==, !=
    value: float
    severity: AlertSeverity = AlertSeverity.WARNING
    message: str = ""


@dataclass
class EscalationLevel:
    """Escalation level configuration."""
    level: int
    channels: List[str]
    wait_time: timedelta
    repeat: bool = False


@dataclass
class EscalationPolicy:
    """Escalation policy."""
    name: str
    levels: List[EscalationLevel] = field(default_factory=list)
    enabled: bool = True


@dataclass
class Silence:
    """Alert silence configuration."""
    id: str
    matchers: Dict[str, str]
    starts_at: datetime
    ends_at: datetime
    created_by: str
    comment: str = ""


class NotificationChannel(ABC):
    """Abstract notification channel."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Channel name."""
        pass
    
    @abstractmethod
    async def send(self, alert: Alert) -> bool:
        """Send notification."""
        pass


class LogChannel(NotificationChannel):
    """Log notification channel."""
    
    def __init__(self, logger_name: Optional[str] = None):
        self._logger = logging.getLogger(logger_name or __name__)
    
    @property
    def name(self) -> str:
        return "log"
    
    async def send(self, alert: Alert) -> bool:
        level = {
            AlertSeverity.INFO: logging.INFO,
            AlertSeverity.WARNING: logging.WARNING,
            AlertSeverity.ERROR: logging.ERROR,
            AlertSeverity.CRITICAL: logging.CRITICAL,
        }.get(alert.severity, logging.WARNING)
        
        self._logger.log(
            level,
            f"[{alert.severity.value.upper()}] {alert.name}: {alert.message}",
        )
        return True


class WebhookChannel(NotificationChannel):
    """Webhook notification channel."""
    
    def __init__(
        self,
        name: str,
        url: str,
        method: str = "POST",
        headers: Optional[Dict[str, str]] = None,
    ):
        self._name = name
        self._url = url
        self._method = method
        self._headers = headers or {}
    
    @property
    def name(self) -> str:
        return self._name
    
    async def send(self, alert: Alert) -> bool:
        try:
            import aiohttp
            
            payload = {
                "id": alert.id,
                "name": alert.name,
                "severity": alert.severity.value,
                "message": alert.message,
                "state": alert.state.value,
                "labels": alert.labels.labels,
                "started_at": alert.started_at.isoformat(),
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    self._method,
                    self._url,
                    json=payload,
                    headers=self._headers,
                ) as response:
                    return response.status < 400
                    
        except ImportError:
            logger.warning("aiohttp not installed, cannot send webhook")
            return False
        except Exception as e:
            logger.error(f"Failed to send webhook: {e}")
            return False


class EmailChannel(NotificationChannel):
    """Email notification channel."""
    
    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        sender: str,
        recipients: List[str],
        username: Optional[str] = None,
        password: Optional[str] = None,
        use_tls: bool = True,
    ):
        self._smtp_host = smtp_host
        self._smtp_port = smtp_port
        self._sender = sender
        self._recipients = recipients
        self._username = username
        self._password = password
        self._use_tls = use_tls
    
    @property
    def name(self) -> str:
        return "email"
    
    async def send(self, alert: Alert) -> bool:
        try:
            import smtplib
            from email.mime.text import MIMEText
            
            subject = f"[{alert.severity.value.upper()}] {alert.name}"
            body = f"""
Alert: {alert.name}
Severity: {alert.severity.value}
Message: {alert.message}
State: {alert.state.value}
Started: {alert.started_at.isoformat()}
Labels: {alert.labels.labels}
            """.strip()
            
            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = self._sender
            msg["To"] = ", ".join(self._recipients)
            
            # Run in thread pool for async
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self._send_email,
                msg,
            )
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False
    
    def _send_email(self, msg) -> None:
        import smtplib
        
        with smtplib.SMTP(self._smtp_host, self._smtp_port) as server:
            if self._use_tls:
                server.starttls()
            if self._username and self._password:
                server.login(self._username, self._password)
            server.send_message(msg)


class CallbackChannel(NotificationChannel):
    """Callback notification channel."""
    
    def __init__(
        self,
        name: str,
        callback: Callable[[Alert], Awaitable[bool]],
    ):
        self._name = name
        self._callback = callback
    
    @property
    def name(self) -> str:
        return self._name
    
    async def send(self, alert: Alert) -> bool:
        return await self._callback(alert)


class AlertRule:
    """
    Alert rule for defining conditions and actions.
    """
    
    def __init__(self, config: AlertRuleConfig):
        self._config = config
        self._pending_since: Optional[datetime] = None
        self._current_alert: Optional[Alert] = None
        self._firing = False
    
    @property
    def name(self) -> str:
        return self._config.name
    
    @property
    def config(self) -> AlertRuleConfig:
        return self._config
    
    @property
    def is_firing(self) -> bool:
        return self._firing
    
    @property
    def current_alert(self) -> Optional[Alert]:
        return self._current_alert
    
    def evaluate(self, metrics: Dict[str, Any]) -> Optional[Alert]:
        """Evaluate rule against metrics."""
        if not self._config.enabled:
            return None
        
        try:
            condition_met = self._config.condition(metrics)
        except Exception as e:
            logger.error(f"Error evaluating rule {self.name}: {e}")
            return None
        
        now = datetime.utcnow()
        
        if condition_met:
            if not self._pending_since:
                self._pending_since = now
            
            # Check if pending duration has passed
            elapsed = now - self._pending_since
            if elapsed >= self._config.for_duration:
                if not self._firing:
                    self._firing = True
                    self._current_alert = Alert(
                        id=f"{self.name}-{now.timestamp()}",
                        name=self.name,
                        severity=self._config.severity,
                        message=self._config.message_template.format(
                            name=self.name,
                            **metrics,
                        ),
                        state=AlertState.FIRING,
                        labels=AlertLabels(self._config.labels.copy()),
                        annotations=self._config.annotations.copy(),
                        started_at=self._pending_since,
                    )
                    return self._current_alert
        else:
            # Condition not met - resolve
            if self._firing and self._current_alert:
                self._current_alert.state = AlertState.RESOLVED
                self._current_alert.resolved_at = now
                resolved_alert = self._current_alert
                self._current_alert = None
                self._firing = False
                self._pending_since = None
                return resolved_alert
            
            self._pending_since = None
        
        return None
    
    def should_notify(self) -> bool:
        """Check if should send notification."""
        if not self._current_alert or not self._firing:
            return False
        
        if self._current_alert.last_notification is None:
            return True
        
        elapsed = datetime.utcnow() - self._current_alert.last_notification
        return elapsed >= self._config.repeat_interval


class ThresholdRule(AlertRule):
    """
    Threshold-based alert rule.
    """
    
    def __init__(
        self,
        config: ThresholdConfig,
        for_duration: timedelta = timedelta(seconds=0),
    ):
        self._threshold = config
        
        # Build condition function
        operators = {
            ">": lambda x, t: x > t,
            "<": lambda x, t: x < t,
            ">=": lambda x, t: x >= t,
            "<=": lambda x, t: x <= t,
            "==": lambda x, t: x == t,
            "!=": lambda x, t: x != t,
        }
        
        op_fn = operators.get(config.operator, operators[">"])
        
        def condition(metrics: Dict[str, Any]) -> bool:
            value = metrics.get(config.metric_name)
            if value is None:
                return False
            return op_fn(float(value), config.value)
        
        rule_config = AlertRuleConfig(
            name=f"{config.metric_name}_{config.operator}_{config.value}",
            condition=condition,
            severity=config.severity,
            message_template=config.message or f"{config.metric_name} {config.operator} {config.value}",
            for_duration=for_duration,
        )
        
        super().__init__(rule_config)
        self._threshold_config = config


class AlertRouter:
    """
    Routes alerts to appropriate channels based on rules.
    """
    
    def __init__(self):
        self._routes: List[Tuple[Dict[str, str], List[str]]] = []
        self._default_channels: List[str] = []
    
    def add_route(
        self,
        matchers: Dict[str, str],
        channels: List[str],
    ) -> None:
        """Add a routing rule."""
        self._routes.append((matchers, channels))
    
    def set_default(self, channels: List[str]) -> None:
        """Set default channels."""
        self._default_channels = channels
    
    def get_channels(self, alert: Alert) -> List[str]:
        """Get channels for an alert."""
        for matchers, channels in self._routes:
            if alert.labels.matches(matchers):
                return channels
        return self._default_channels


class AlertManager:
    """
    Alert manager for coordinating alerts and notifications.
    """
    
    def __init__(self):
        self._rules: Dict[str, AlertRule] = {}
        self._channels: Dict[str, NotificationChannel] = {}
        self._router = AlertRouter()
        self._silences: Dict[str, Silence] = {}
        self._escalation_policies: Dict[str, EscalationPolicy] = {}
        self._alerts: Dict[str, Alert] = {}
        self._alert_history: List[Alert] = []
    
    def define_rule(
        self,
        name: str,
        condition: Callable[[Dict[str, Any]], bool],
        severity: AlertSeverity = AlertSeverity.WARNING,
        message: str = "",
        labels: Optional[Dict[str, str]] = None,
        for_duration: timedelta = timedelta(seconds=0),
    ) -> AlertRule:
        """Define an alert rule."""
        config = AlertRuleConfig(
            name=name,
            condition=condition,
            severity=severity,
            message_template=message or f"Alert: {name}",
            labels=labels or {},
            for_duration=for_duration,
        )
        rule = AlertRule(config)
        self._rules[name] = rule
        return rule
    
    def define_threshold(
        self,
        metric_name: str,
        operator: str,
        value: float,
        severity: AlertSeverity = AlertSeverity.WARNING,
        message: str = "",
        for_duration: timedelta = timedelta(seconds=0),
    ) -> AlertRule:
        """Define a threshold-based rule."""
        config = ThresholdConfig(
            metric_name=metric_name,
            operator=operator,
            value=value,
            severity=severity,
            message=message,
        )
        rule = ThresholdRule(config, for_duration)
        self._rules[rule.name] = rule
        return rule
    
    def add_channel(self, channel: NotificationChannel) -> None:
        """Add notification channel."""
        self._channels[channel.name] = channel
    
    def add_route(
        self,
        matchers: Dict[str, str],
        channels: List[str],
    ) -> None:
        """Add routing rule."""
        self._router.add_route(matchers, channels)
    
    def set_default_channels(self, channels: List[str]) -> None:
        """Set default notification channels."""
        self._router.set_default(channels)
    
    def add_silence(
        self,
        matchers: Dict[str, str],
        duration: timedelta,
        created_by: str,
        comment: str = "",
    ) -> Silence:
        """Add silence for matching alerts."""
        now = datetime.utcnow()
        silence = Silence(
            id=f"silence-{now.timestamp()}",
            matchers=matchers,
            starts_at=now,
            ends_at=now + duration,
            created_by=created_by,
            comment=comment,
        )
        self._silences[silence.id] = silence
        return silence
    
    def remove_silence(self, silence_id: str) -> None:
        """Remove a silence."""
        self._silences.pop(silence_id, None)
    
    def add_escalation_policy(self, policy: EscalationPolicy) -> None:
        """Add escalation policy."""
        self._escalation_policies[policy.name] = policy
    
    def is_silenced(self, alert: Alert) -> bool:
        """Check if alert is silenced."""
        now = datetime.utcnow()
        
        for silence in self._silences.values():
            if silence.starts_at <= now <= silence.ends_at:
                if alert.labels.matches(silence.matchers):
                    return True
        
        return False
    
    async def evaluate(self, metrics: Dict[str, Any]) -> List[Alert]:
        """Evaluate all rules against metrics."""
        alerts = []
        
        for rule in self._rules.values():
            alert = rule.evaluate(metrics)
            
            if alert:
                alerts.append(alert)
                self._alerts[alert.id] = alert
                
                # Check if should notify
                if alert.state == AlertState.FIRING:
                    if not self.is_silenced(alert) and rule.should_notify():
                        await self._notify(alert)
                        alert.notification_count += 1
                        alert.last_notification = datetime.utcnow()
                
                elif alert.state == AlertState.RESOLVED:
                    if not self.is_silenced(alert):
                        await self._notify(alert)
                    self._alert_history.append(alert)
                    self._alerts.pop(alert.id, None)
        
        return alerts
    
    async def _notify(self, alert: Alert) -> None:
        """Send notifications for alert."""
        channel_names = self._router.get_channels(alert)
        
        for name in channel_names:
            channel = self._channels.get(name)
            if channel:
                try:
                    await channel.send(alert)
                except Exception as e:
                    logger.error(f"Failed to send notification via {name}: {e}")
    
    def acknowledge(self, alert_id: str, acknowledged_by: str) -> Optional[Alert]:
        """Acknowledge an alert."""
        alert = self._alerts.get(alert_id)
        if alert:
            alert.state = AlertState.ACKNOWLEDGED
            alert.acknowledged_at = datetime.utcnow()
            alert.acknowledged_by = acknowledged_by
        return alert
    
    def get_firing_alerts(self) -> List[Alert]:
        """Get all firing alerts."""
        return [
            a for a in self._alerts.values()
            if a.state == AlertState.FIRING
        ]
    
    def get_all_alerts(self) -> List[Alert]:
        """Get all active alerts."""
        return list(self._alerts.values())
    
    def get_alert_history(
        self,
        limit: int = 100,
        severity: Optional[AlertSeverity] = None,
    ) -> List[Alert]:
        """Get alert history."""
        history = self._alert_history
        
        if severity:
            history = [a for a in history if a.severity == severity]
        
        return history[-limit:]


# Global manager
_global_manager: Optional[AlertManager] = None


# Decorators
def alert_on_error(
    name: str,
    severity: AlertSeverity = AlertSeverity.ERROR,
    message: Optional[str] = None,
) -> Callable:
    """
    Decorator to create alert on function error.
    
    Example:
        @alert_on_error("process_failed")
        async def process_data(data):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                manager = get_global_manager()
                alert = Alert(
                    id=f"{name}-{datetime.utcnow().timestamp()}",
                    name=name,
                    severity=severity,
                    message=message or f"Error in {func.__name__}: {str(e)}",
                    state=AlertState.FIRING,
                )
                await manager._notify(alert)
                raise
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                manager = get_global_manager()
                alert = Alert(
                    id=f"{name}-{datetime.utcnow().timestamp()}",
                    name=name,
                    severity=severity,
                    message=message or f"Error in {func.__name__}: {str(e)}",
                    state=AlertState.FIRING,
                )
                # Run notification in background
                asyncio.create_task(manager._notify(alert))
                raise
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


def alert_on_slow(
    name: str,
    threshold_seconds: float,
    severity: AlertSeverity = AlertSeverity.WARNING,
) -> Callable:
    """
    Decorator to create alert on slow execution.
    
    Example:
        @alert_on_slow("slow_query", threshold_seconds=5.0)
        async def query_database():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            import time
            start = time.perf_counter()
            
            try:
                return await func(*args, **kwargs)
            finally:
                duration = time.perf_counter() - start
                if duration > threshold_seconds:
                    manager = get_global_manager()
                    alert = Alert(
                        id=f"{name}-{datetime.utcnow().timestamp()}",
                        name=name,
                        severity=severity,
                        message=f"{func.__name__} took {duration:.2f}s (threshold: {threshold_seconds}s)",
                        state=AlertState.FIRING,
                        value=duration,
                        threshold=threshold_seconds,
                    )
                    await manager._notify(alert)
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            import time
            start = time.perf_counter()
            
            try:
                return func(*args, **kwargs)
            finally:
                duration = time.perf_counter() - start
                if duration > threshold_seconds:
                    manager = get_global_manager()
                    alert = Alert(
                        id=f"{name}-{datetime.utcnow().timestamp()}",
                        name=name,
                        severity=severity,
                        message=f"{func.__name__} took {duration:.2f}s (threshold: {threshold_seconds}s)",
                        state=AlertState.FIRING,
                        value=duration,
                        threshold=threshold_seconds,
                    )
                    asyncio.create_task(manager._notify(alert))
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


# Factory functions
def create_alert_manager() -> AlertManager:
    """Create an alert manager."""
    return AlertManager()


def create_threshold_rule(
    metric_name: str,
    operator: str,
    value: float,
    severity: AlertSeverity = AlertSeverity.WARNING,
    message: str = "",
) -> ThresholdConfig:
    """Create a threshold configuration."""
    return ThresholdConfig(
        metric_name=metric_name,
        operator=operator,
        value=value,
        severity=severity,
        message=message,
    )


def create_log_channel(logger_name: Optional[str] = None) -> LogChannel:
    """Create log notification channel."""
    return LogChannel(logger_name)


def create_webhook_channel(
    name: str,
    url: str,
    method: str = "POST",
) -> WebhookChannel:
    """Create webhook notification channel."""
    return WebhookChannel(name, url, method)


def create_callback_channel(
    name: str,
    callback: Callable[[Alert], Awaitable[bool]],
) -> CallbackChannel:
    """Create callback notification channel."""
    return CallbackChannel(name, callback)


def create_escalation_policy(
    name: str,
    levels: Optional[List[Tuple[List[str], timedelta]]] = None,
) -> EscalationPolicy:
    """Create escalation policy."""
    policy_levels = []
    if levels:
        for i, (channels, wait) in enumerate(levels):
            policy_levels.append(EscalationLevel(
                level=i + 1,
                channels=channels,
                wait_time=wait,
            ))
    
    return EscalationPolicy(name=name, levels=policy_levels)


def get_global_manager() -> AlertManager:
    """Get global alert manager."""
    global _global_manager
    if _global_manager is None:
        _global_manager = create_alert_manager()
    return _global_manager


__all__ = [
    # Enums
    "AlertSeverity",
    "AlertState",
    # Data classes
    "AlertLabels",
    "Alert",
    "AlertRuleConfig",
    "ThresholdConfig",
    "EscalationLevel",
    "EscalationPolicy",
    "Silence",
    # Channels
    "NotificationChannel",
    "LogChannel",
    "WebhookChannel",
    "EmailChannel",
    "CallbackChannel",
    # Rules
    "AlertRule",
    "ThresholdRule",
    # Router
    "AlertRouter",
    # Manager
    "AlertManager",
    # Decorators
    "alert_on_error",
    "alert_on_slow",
    # Factory functions
    "create_alert_manager",
    "create_threshold_rule",
    "create_log_channel",
    "create_webhook_channel",
    "create_callback_channel",
    "create_escalation_policy",
    "get_global_manager",
]
