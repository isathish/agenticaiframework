"""
Agentic Framework Monitoring and Observability Module

This module provides classes and utilities for monitoring and observability within the Agentic Framework.
Monitoring and Observability ensure visibility into the performance, health, and behavior of agents, tools,
and the overall framework. They provide actionable insights for debugging, optimization, and compliance.
Monitoring focuses on tracking predefined metrics and events, while observability emphasizes understanding
the internal state of the system through outputs, traces, and logs.

Key Features:
- Events and Traces: Capturing system events and execution traces to understand behavior.
- Metrics: Quantitative measurements for performance monitoring (latency, throughput, error rates).
- Real-Time Dashboards: Visualizing metrics and events for live monitoring.
- Alerting and Notifications: Triggering alerts for thresholds or anomalies.
- Log Management: Collecting and analyzing logs for debugging and auditing.
- Distributed Tracing: Tracking requests across multiple agents and services.
- Anomaly Detection: Detecting unusual patterns or behaviors.
- Historical Analysis: Reviewing past performance data for trends.
- Monitoring Integrations: Connecting with external platforms (Prometheus, Grafana).
- Security Monitoring: Tracking access patterns and potential threats.
"""

from typing import Any, Dict, List, Optional, Callable, Set, Tuple
from datetime import datetime
import time
import threading
import uuid
import json
import os
import statistics
from abc import ABC, abstractmethod
from collections import defaultdict, deque

# Custom exceptions for Monitoring and Observability
class MonitoringError(Exception):
    """Exception raised for errors related to monitoring operations."""
    pass

class AlertError(MonitoringError):
    """Exception raised when alert operations fail."""
    pass

class TraceError(MonitoringError):
    """Exception raised when tracing operations fail."""
    pass

class MetricError(MonitoringError):
    """Exception raised when metric collection or processing fails."""
    pass

class Monitor(ABC):
    """
    Abstract base class for monitoring components in the Agentic Framework.
    Monitors collect and process data about system performance and behavior.
    """
    def __init__(self, name: str, description: str = "", config: Optional[Dict[str, Any]] = None):
        """
        Initialize a Monitor with basic metadata and configuration.
        
        Args:
            name (str): The name of the monitor.
            description (str): A brief description of the monitor's purpose.
            config (Dict[str, Any], optional): Configuration parameters for the monitor.
        """
        self.name = name
        self.description = description
        self.config = config or {}
        self.monitor_id = str(uuid.uuid4())
        self.active = False
        self.last_updated = 0.0
        self.data_points = 0
        self.lock = threading.Lock()

    @abstractmethod
    def collect_data(self, target: Any, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Collect monitoring data from the target entity.
        
        Args:
            target (Any): The entity to monitor (e.g., agent, tool, process).
            context (Dict[str, Any], optional): Additional contextual information.
        
        Returns:
            Dict[str, Any]: Collected monitoring data.
        """
        pass

    def activate(self) -> bool:
        """
        Activate the monitor for data collection.
        
        Returns:
            bool: True if activation was successful, False otherwise.
        """
        with self.lock:
            if not self.active:
                self.active = True
                self.last_updated = time.time()
                return True
            return False

    def deactivate(self) -> bool:
        """
        Deactivate the monitor to stop data collection.
        
        Returns:
            bool: True if deactivation was successful, False otherwise.
        """
        with self.lock:
            if self.active:
                self.active = False
                self.last_updated = time.time()
                return True
            return False

    def update_config(self, new_config: Dict[str, Any]) -> bool:
        """
        Update the monitor's configuration parameters.
        
        Args:
            new_config (Dict[str, Any]): The new configuration to apply.
        
        Returns:
            bool: True if the configuration update was successful.
        """
        with self.lock:
            self.config.update(new_config)
            self.last_updated = time.time()
            return True

    def get_status(self) -> Dict[str, Any]:
        """
        Retrieve the current status of the monitor.
        
        Returns:
            Dict[str, Any]: Status information including activity and last update.
        """
        with self.lock:
            return {
                "monitor_id": self.monitor_id,
                "name": self.name,
                "active": self.active,
                "description": self.description,
                "last_updated": datetime.fromtimestamp(self.last_updated).isoformat() if self.last_updated > 0 else "Never",
                "data_points_collected": self.data_points
            }


class PerformanceMonitor(Monitor):
    """
    A monitor for collecting performance metrics such as latency, throughput, and error rates.
    """
    def __init__(self, name: str, description: str = "Performance Monitor",
                 config: Optional[Dict[str, Any]] = None):
        """
        Initialize a Performance Monitor.
        
        Args:
            name (str): The name of the monitor.
            description (str): A brief description of the monitor's purpose.
            config (Dict[str, Any], optional): Configuration parameters.
        """
        super().__init__(name, description, config)
        self.metrics = defaultdict(list)
        self.metric_history_limit = self.config.get("metric_history_limit", 1000)

    def collect_data(self, target: Any, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Collect performance metrics from the target entity.
        
        Args:
            target (Any): The entity to monitor (e.g., agent, tool).
            context (Dict[str, Any], optional): Additional contextual information.
        
        Returns:
            Dict[str, Any]: Collected performance metrics.
        """
        if not self.active:
            raise MonitoringError(f"Performance Monitor {self.name} is not active")
        with self.lock:
            try:
                # Extract performance data if target supports it
                if hasattr(target, "get_monitoring_data"):
                    data = target.get_monitoring_data()
                    if "performance_metrics" in data:
                        metrics = data["performance_metrics"]
                        for metric_name, value in metrics.items():
                            self.metrics[metric_name].append(value)
                            if len(self.metrics[metric_name]) > self.metric_history_limit:
                                self.metrics[metric_name].pop(0)
                        self.data_points += 1
                        self.last_updated = time.time()
                        return {
                            "timestamp": datetime.now().isoformat(),
                            "target": getattr(target, "name", str(target)),
                            "metrics": metrics
                        }
                # Default metrics collection if no specific data available
                start_time = time.time()
                # Simulate some metric collection logic
                latency = context.get("latency", 0.0) if context else 0.0
                error_rate = context.get("error_rate", 0.0) if context else 0.0
                throughput = context.get("throughput", 0.0) if context else 0.0
                end_time = time.time()
                self.metrics["latency"].append(latency + (end_time - start_time))
                self.metrics["error_rate"].append(error_rate)
                self.metrics["throughput"].append(throughput)
                if len(self.metrics["latency"]) > self.metric_history_limit:
                    self.metrics["latency"].pop(0)
                if len(self.metrics["error_rate"]) > self.metric_history_limit:
                    self.metrics["error_rate"].pop(0)
                if len(self.metrics["throughput"]) > self.metric_history_limit:
                    self.metrics["throughput"].pop(0)
                self.data_points += 1
                self.last_updated = time.time()
                return {
                    "timestamp": datetime.now().isoformat(),
                    "target": getattr(target, "name", str(target)),
                    "metrics": {
                        "latency": latency + (end_time - start_time),
                        "error_rate": error_rate,
                        "throughput": throughput
                    }
                }
            except Exception as e:
                raise MetricError(f"Error collecting performance data for {self.name}: {str(e)}")

    def get_aggregated_metrics(self) -> Dict[str, Any]:
        """
        Aggregate collected metrics for summary reporting.
        
        Returns:
            Dict[str, Any]: Aggregated metrics (average, min, max, etc.).
        """
        with self.lock:
            aggregated = {}
            for metric_name, values in self.metrics.items():
                if values:
                    aggregated[metric_name] = {
                        "average": sum(values) / len(values) if values else 0.0,
                        "min": min(values) if values else 0.0,
                        "max": max(values) if values else 0.0,
                        "count": len(values)
                    }
                else:
                    aggregated[metric_name] = {
                        "average": 0.0,
                        "min": 0.0,
                        "max": 0.0,
                        "count": 0
                    }
            return aggregated


class EventTracer(Monitor):
    """
    A monitor for capturing and tracing events within the system to understand workflows and behaviors.
    """
    def __init__(self, name: str, description: str = "Event Tracer",
                 config: Optional[Dict[str, Any]] = None):
        """
        Initialize an Event Tracer.
        
        Args:
            name (str): The name of the tracer.
            description (str): A brief description of the tracer's purpose.
            config (Dict[str, Any], optional): Configuration parameters.
        """
        super().__init__(name, description, config)
        self.events = deque(maxlen=self.config.get("event_history_limit", 1000))
        self.trace_id_map = defaultdict(list)

    def collect_data(self, target: Any, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Collect event data from the target entity.
        
        Args:
            target (Any): The entity to monitor for events.
            context (Dict[str, Any], optional): Additional contextual information including trace ID.
        
        Returns:
            Dict[str, Any]: Recorded event data.
        """
        if not self.active:
            raise MonitoringError(f"Event Tracer {self.name} is not active")
        with self.lock:
            try:
                event_id = str(uuid.uuid4())
                trace_id = context.get("trace_id", str(uuid.uuid4())) if context else str(uuid.uuid4())
                timestamp = datetime.now().isoformat()
                event_type = context.get("event_type", "generic_event") if context else "generic_event"
                event_details = context.get("details", {}) if context else {}
                event_data = {
                    "event_id": event_id,
                    "trace_id": trace_id,
                    "timestamp": timestamp,
                    "event_type": event_type,
                    "target": getattr(target, "name", str(target)),
                    "details": event_details
                }
                self.events.append(event_data)
                self.trace_id_map[trace_id].append(event_data)
                self.data_points += 1
                self.last_updated = time.time()
                return event_data
            except Exception as e:
                raise TraceError(f"Error tracing event for {self.name}: {str(e)}")

    def get_trace(self, trace_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve all events associated with a specific trace ID.
        
        Args:
            trace_id (str): The trace ID to look up.
        
        Returns:
            List[Dict[str, Any]]: List of events in the trace.
        """
        with self.lock:
            return self.trace_id_map.get(trace_id, [])

    def get_recent_events(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Retrieve the most recent events.
        
        Args:
            limit (int): Maximum number of events to return.
        
        Returns:
            List[Dict[str, Any]]: List of recent events.
        """
        with self.lock:
            return list(self.events)[-limit:]


class AlertManager:
    """
    Manages alerting and notifications based on monitoring data and predefined thresholds.
    """
    def __init__(self, name: str = "Alert Manager", config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Alert Manager.
        
        Args:
            name (str): The name of the alert manager.
            config (Dict[str, Any], optional): Configuration parameters.
        """
        self.name = name
        self.config = config or {}
        self.alert_rules = self.config.get("alert_rules", {})
        self.alert_history = deque(maxlen=self.config.get("alert_history_limit", 1000))
        self.active = False
        self.last_alert_time = 0.0
        self.alert_count = 0
        self.notification_handler = self.config.get("notification_handler", lambda x: print(f"Alert: {x}"))
        self.lock = threading.Lock()

    def activate(self) -> bool:
        """
        Activate the Alert Manager.
        
        Returns:
            bool: True if activation was successful.
        """
        with self.lock:
            self.active = True
            return True

    def deactivate(self) -> bool:
        """
        Deactivate the Alert Manager.
        
        Returns:
            bool: True if deactivation was successful.
        """
        with self.lock:
            self.active = False
            return True

    def update_alert_rules(self, new_rules: Dict[str, Any]) -> bool:
        """
        Update the alert rules.
        
        Args:
            new_rules (Dict[str, Any]): New alert rules to apply.
        
        Returns:
            bool: True if update was successful.
        """
        with self.lock:
            self.alert_rules.update(new_rules)
            return True

    def check_alerts(self, monitoring_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Check monitoring data against alert rules and trigger notifications if needed.
        
        Args:
            monitoring_data (Dict[str, Any]): Data from monitors to check for alert conditions.
        
        Returns:
            List[Dict[str, Any]]: List of triggered alerts.
        """
        if not self.active:
            return []
        with self.lock:
            triggered_alerts = []
            for rule_name, rule in self.alert_rules.items():
                metric = rule.get("metric", "")
                threshold = rule.get("threshold", 0.0)
                condition = rule.get("condition", "greater_than")
                message = rule.get("message", f"Alert: {metric} threshold breached")
                if metric in monitoring_data:
                    value = monitoring_data.get(metric, 0.0)
                    if (condition == "greater_than" and value > threshold) or \
                       (condition == "less_than" and value < threshold) or \
                       (condition == "equal_to" and value == threshold):
                        alert_data = {
                            "alert_id": str(uuid.uuid4()),
                            "rule_name": rule_name,
                            "timestamp": datetime.now().isoformat(),
                            "metric": metric,
                            "value": value,
                            "threshold": threshold,
                            "condition": condition,
                            "message": message
                        }
                        triggered_alerts.append(alert_data)
                        self.alert_history.append(alert_data)
                        self.alert_count += 1
                        self.last_alert_time = time.time()
                        try:
                            self.notification_handler(message)
                        except Exception as e:
                            # Log error but don't fail the alert process
                            print(f"Notification handler error: {e}")
            return triggered_alerts

    def get_alert_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Retrieve recent alert history.
        
        Args:
            limit (int): Maximum number of alerts to return.
        
        Returns:
            List[Dict[str, Any]]: List of recent alerts.
        """
        with self.lock:
            return list(self.alert_history)[-limit:]


class Dashboard:
    """
    Provides real-time visualization of monitoring data through dashboards.
    """
    def __init__(self, name: str = "Dashboard", config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Dashboard.
        
        Args:
            name (str): The name of the dashboard.
            config (Dict[str, Any], optional): Configuration parameters.
        """
        self.name = name
        self.config = config or {}
        self.widgets = self.config.get("widgets", [])
        self.active = False
        self.last_refreshed = 0.0
        self.refresh_interval = self.config.get("refresh_interval", 60.0)  # seconds
        self.data_source = None
        self.lock = threading.Lock()

    def activate(self, data_source: Optional[Callable[[], Dict[str, Any]]] = None) -> bool:
        """
        Activate the Dashboard with an optional data source.
        
        Args:
            data_source (Callable, optional): Function to fetch dashboard data.
        
        Returns:
            bool: True if activation was successful.
        """
        with self.lock:
            self.active = True
            self.data_source = data_source
            self.last_refreshed = time.time()
            return True

    def deactivate(self) -> bool:
        """
        Deactivate the Dashboard.
        
        Returns:
            bool: True if deactivation was successful.
        """
        with self.lock:
            self.active = False
            return True

    def update_widgets(self, new_widgets: List[Dict[str, Any]]) -> bool:
        """
        Update the dashboard widgets.
        
        Args:
            new_widgets (List[Dict[str, Any]]): New widget configurations.
        
        Returns:
            bool: True if update was successful.
        """
        with self.lock:
            self.widgets = new_widgets
            return True

    def refresh(self) -> Dict[str, Any]:
        """
        Refresh the dashboard with the latest data.
        
        Returns:
            Dict[str, Any]: Current dashboard data.
        """
        if not self.active:
            return {"status": "Dashboard not active"}
        with self.lock:
            if time.time() - self.last_refreshed >= self.refresh_interval or self.last_refreshed == 0.0:
                dashboard_data = {"timestamp": datetime.now().isoformat(), "widgets": []}
                if self.data_source:
                    try:
                        raw_data = self.data_source()
                        for widget in self.widgets:
                            widget_type = widget.get("type", "metric")
                            metric = widget.get("metric", "")
                            title = widget.get("title", metric)
                            if widget_type == "metric" and metric in raw_data:
                                dashboard_data["widgets"].append({
                                    "title": title,
                                    "type": widget_type,
                                    "value": raw_data[metric]
                                })
                            elif widget_type == "chart":
                                # Placeholder for chart data processing
                                dashboard_data["widgets"].append({
                                    "title": title,
                                    "type": widget_type,
                                    "data": raw_data.get(metric, [])
                                })
                    except Exception as e:
                        dashboard_data["error"] = f"Data source error: {str(e)}"
                self.last_refreshed = time.time()
                return dashboard_data
            return {"status": "Dashboard data not refreshed yet", "last_refreshed": datetime.fromtimestamp(self.last_refreshed).isoformat()}


class AnomalyDetector:
    """
    Detects anomalies in monitoring data using statistical or AI-based methods.
    """
    def __init__(self, name: str = "Anomaly Detector", config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Anomaly Detector.
        
        Args:
            name (str): The name of the anomaly detector.
            config (Dict[str, Any], optional): Configuration parameters.
        """
        self.name = name
        self.config = config or {}
        self.history = defaultdict(deque)
        self.history_limit = self.config.get("history_limit", 1000)
        self.thresholds = self.config.get("thresholds", {})
        self.active = False
        self.anomaly_count = 0
        self.last_anomaly_time = 0.0
        self.lock = threading.Lock()

    def activate(self) -> bool:
        """
        Activate the Anomaly Detector.
        
        Returns:
            bool: True if activation was successful.
        """
        with self.lock:
            self.active = True
            return True

    def deactivate(self) -> bool:
        """
        Deactivate the Anomaly Detector.
        
        Returns:
            bool: True if deactivation was successful.
        """
        with self.lock:
            self.active = False
            return True

    def update_thresholds(self, new_thresholds: Dict[str, Any]) -> bool:
        """
        Update anomaly detection thresholds.
        
        Args:
            new_thresholds (Dict[str, Any]): New thresholds for anomaly detection.
        
        Returns:
            bool: True if update was successful.
        """
        with self.lock:
            self.thresholds.update(new_thresholds)
            return True

    def detect(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Detect anomalies in the provided data.
        
        Args:
            data (Dict[str, Any]): Monitoring data to analyze for anomalies.
        
        Returns:
            List[Dict[str, Any]]: List of detected anomalies.
        """
        if not self.active:
            return []
        with self.lock:
            anomalies = []
            for metric, value in data.items():
                if isinstance(value, (int, float)):
                    self.history[metric].append(value)
                    if len(self.history[metric]) > self.history_limit:
                        self.history[metric].popleft()
                    if len(self.history[metric]) > 10:  # Need some history for meaningful analysis
                        mean = statistics.mean(self.history[metric])
                        stdev = statistics.stdev(self.history[metric]) if len(self.history[metric]) > 1 else 0.0
                        threshold = self.thresholds.get(metric, {}).get("stdev_multiplier", 3.0)
                        if stdev > 0 and abs(value - mean) > (stdev * threshold):
                            anomaly = {
                                "anomaly_id": str(uuid.uuid4()),
                                "timestamp": datetime.now().isoformat(),
                                "metric": metric,
                                "value": value,
                                "mean": mean,
                                "stdev": stdev,
                                "threshold": threshold,
                                "message": f"Anomaly detected in {metric}: value {value} deviates significantly from mean {mean}"
                            }
                            anomalies.append(anomaly)
                            self.anomaly_count += 1
                            self.last_anomaly_time = time.time()
            return anomalies

    def get_anomaly_stats(self) -> Dict[str, Any]:
        """
        Retrieve statistics about detected anomalies.
        
        Returns:
            Dict[str, Any]: Anomaly detection statistics.
        """
        with self.lock:
            return {
                "name": self.name,
                "active": self.active,
                "total_anomalies": self.anomaly_count,
                "last_anomaly_time": datetime.fromtimestamp(self.last_anomaly_time).isoformat() if self.last_anomaly_time > 0 else "Never"
            }


class MonitoringManager:
    """
    Central manager for all monitoring and observability components in the Agentic Framework.
    Coordinates monitors, tracers, alerts, dashboards, and anomaly detectors.
    """
    def __init__(self, name: str = "Monitoring Manager", config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Monitoring Manager.
        
        Args:
            name (str): The name of the manager.
            config (Dict[str, Any], optional): Configuration parameters.
        """
        self.name = name
        self.config = config or {}
        self.monitors: Dict[str, Monitor] = {}
        self.alert_manager: Optional[AlertManager] = None
        self.dashboard: Optional[Dashboard] = None
        self.anomaly_detector: Optional[AnomalyDetector] = None
        self.active = False
        self.last_updated = 0.0
        self.monitoring_log = deque(maxlen=self.config.get("log_limit", 1000))
        self.lock = threading.Lock()

    def activate(self) -> bool:
        """
        Activate the Monitoring Manager and initialize components.
        
        Returns:
            bool: True if activation was successful.
        """
        with self.lock:
            if not self.active:
                self.active = True
                # Initialize default components if not already set
                if not self.alert_manager:
                    self.alert_manager = AlertManager(config=self.config.get("alert_config", {}))
                    self.alert_manager.activate()
                if not self.dashboard:
                    self.dashboard = Dashboard(config=self.config.get("dashboard_config", {}))
                    self.dashboard.activate(data_source=self.get_monitoring_summary)
                if not self.anomaly_detector:
                    self.anomaly_detector = AnomalyDetector(config=self.config.get("anomaly_config", {}))
                    self.anomaly_detector.activate()
                # Activate all monitors
                for monitor in self.monitors.values():
                    monitor.activate()
                self.last_updated = time.time()
                self.monitoring_log.append(f"Monitoring Manager {self.name} activated at {datetime.now().isoformat()}")
            return True

    def deactivate(self) -> bool:
        """
        Deactivate the Monitoring Manager and all components.
        
        Returns:
            bool: True if deactivation was successful.
        """
        with self.lock:
            if self.active:
                for monitor in self.monitors.values():
                    monitor.deactivate()
                if self.alert_manager:
                    self.alert_manager.deactivate()
                if self.dashboard:
                    self.dashboard.deactivate()
                if self.anomaly_detector:
                    self.anomaly_detector.deactivate()
                self.active = False
                self.last_updated = time.time()
                self.monitoring_log.append(f"Monitoring Manager {self.name} deactivated at {datetime.now().isoformat()}")
            return True

    def register_monitor(self, monitor: Monitor) -> bool:
        """
        Register a new monitor with the manager.
        
        Args:
            monitor (Monitor): The monitor to register.
        
        Returns:
            bool: True if registration was successful.
        """
        if not self.active:
            raise MonitoringError(f"Monitoring Manager {self.name} is not active")
        with self.lock:
            self.monitors[monitor.name] = monitor
            if self.active:
                monitor.activate()
            self.last_updated = time.time()
            self.monitoring_log.append(f"Monitor {monitor.name} registered with {self.name} at {datetime.now().isoformat()}")
            return True

    def collect_monitoring_data(self, target: Any, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Collect data from all registered monitors for the target entity.
        
        Args:
            target (Any): The entity to monitor.
            context (Dict[str, Any], optional): Additional contextual information.
        
        Returns:
            Dict[str, Any]: Combined monitoring data from all monitors.
        """
        if not self.active:
            raise MonitoringError(f"Monitoring Manager {self.name} is not active")
        with self.lock:
            monitoring_data = {"timestamp": datetime.now().isoformat(), "target": getattr(target, "name", str(target))}
            for monitor_name, monitor in self.monitors.items():
                try:
                    data = monitor.collect_data(target, context)
                    monitoring_data[monitor_name] = data
                except MonitoringError as e:
                    monitoring_data[monitor_name] = {"error": str(e)}
                    self.monitoring_log.append(f"Error collecting data from monitor {monitor_name}: {str(e)} at {datetime.now().isoformat()}")
            # Check for alerts based on collected data
            if self.alert_manager:
                try:
                    # Flatten some data for alert checking
                    alert_check_data = {}
                    for m_name, m_data in monitoring_data.items():
                        if m_name != "timestamp" and m_name != "target":
                            if "metrics" in m_data:
                                for metric, value in m_data.get("metrics", {}).items():
                                    alert_check_data[f"{m_name}.{metric}"] = value
                    alerts = self.alert_manager.check_alerts(alert_check_data)
                    if alerts:
                        monitoring_data["alerts"] = alerts
                        self.monitoring_log.append(f"Alerts triggered for {target}: {len(alerts)} alerts at {datetime.now().isoformat()}")
                except AlertError as e:
                    monitoring_data["alerts"] = {"error": str(e)}
                    self.monitoring_log.append(f"Alert check error: {str(e)} at {datetime.now().isoformat()}")
            # Check for anomalies
            if self.anomaly_detector:
                try:
                    anomaly_check_data = {}
                    for m_name, m_data in monitoring_data.items():
                        if m_name != "timestamp" and m_name != "target" and "metrics" in m_data:
                            for metric, value in m_data.get("metrics", {}).items():
                                if isinstance(value, (int, float)):
                                    anomaly_check_data[metric] = value
                    anomalies = self.anomaly_detector.detect(anomaly_check_data)
                    if anomalies:
                        monitoring_data["anomalies"] = anomalies
                        self.monitoring_log.append(f"Anomalies detected for {target}: {len(anomalies)} anomalies at {datetime.now().isoformat()}")
                except Exception as e:
                    monitoring_data["anomalies"] = {"error": str(e)}
                    self.monitoring_log.append(f"Anomaly detection error: {str(e)} at {datetime.now().isoformat()}")
            self.last_updated = time.time()
            return monitoring_data

    def get_monitoring_summary(self) -> Dict[str, Any]:
        """
        Retrieve a summary of monitoring data for dashboard or reporting.
        
        Returns:
            Dict[str, Any]: Summary of monitoring data.
        """
        with self.lock:
            summary = {
                "manager_name": self.name,
                "active": self.active,
                "last_updated": datetime.fromtimestamp(self.last_updated).isoformat() if self.last_updated > 0 else "Never",
                "monitors": {},
                "alerts": [],
                "anomalies": {}
            }
            for monitor_name, monitor in self.monitors.items():
                summary["monitors"][monitor_name] = monitor.get_status()
                if isinstance(monitor, PerformanceMonitor):
                    summary["monitors"][monitor_name]["aggregated_metrics"] = monitor.get_aggregated_metrics()
                elif isinstance(monitor, EventTracer):
                    summary["monitors"][monitor_name]["recent_events"] = monitor.get_recent_events(limit=5)
            if self.alert_manager:
                summary["alerts"] = self.alert_manager.get_alert_history(limit=5)
            if self.anomaly_detector:
                summary["anomalies"] = self.anomaly_detector.get_anomaly_stats()
            return summary

    def refresh_dashboard(self) -> Dict[str, Any]:
        """
        Refresh the dashboard with the latest data.
        
        Returns:
            Dict[str, Any]: Current dashboard data.
        """
        if not self.active or not self.dashboard:
            return {"status": "Dashboard not available or manager not active"}
        with self.lock:
            return self.dashboard.refresh()

    def integrate_external_monitoring(self, platform: str, config: Dict[str, Any]) -> bool:
        """
        Integrate with external monitoring platforms like Prometheus or Grafana.
        
        Args:
            platform (str): The name of the external platform.
            config (Dict[str, Any]): Configuration for integration.
        
        Returns:
            bool: True if integration setup was successful.
        """
        if not self.active:
            return False
        with self.lock:
            # Placeholder for actual integration logic
            self.monitoring_log.append(f"Integrated with external monitoring platform {platform} at {datetime.now().isoformat()}")
            self.last_updated = time.time()
            return True

    def security_monitoring(self, security_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Monitor security-related events and data for potential threats.
        
        Args:
            security_data (Dict[str, Any]): Security-related data to analyze.
        
        Returns:
            Dict[str, Any]: Security monitoring results.
        """
        if not self.active:
            return {"status": "Security monitoring not active"}
        with self.lock:
            results = {
                "timestamp": datetime.now().isoformat(),
                "security_issues": []
            }
            failed_attempts = security_data.get("failed_auth_attempts", 0)
            if failed_attempts > self.config.get("security_thresholds", {}).get("failed_auth_attempts", 5):
                issue = {
                    "issue_id": str(uuid.uuid4()),
                    "type": "Excessive Failed Authentication Attempts",
                    "severity": "High",
                    "details": f"Detected {failed_attempts} failed authentication attempts"
                }
                results["security_issues"].append(issue)
                self.monitoring_log.append(f"Security issue detected: {issue['type']} at {datetime.now().isoformat()}")
            suspicious_access = security_data.get("suspicious_access_patterns", [])
            if suspicious_access:
                issue = {
                    "issue_id": str(uuid.uuid4()),
                    "type": "Suspicious Access Patterns",
                    "severity": "Medium",
                    "details": f"Detected suspicious access patterns: {suspicious_access}"
                }
                results["security_issues"].append(issue)
                self.monitoring_log.append(f"Security issue detected: {issue['type']} at {datetime.now().isoformat()}")
            if self.alert_manager and results["security_issues"]:
                try:
                    alerts = self.alert_manager.check_alerts({
                        "security_issues_count": len(results["security_issues"])
                    })
                    if alerts:
                        results["alerts"] = alerts
                except AlertError as e:
                    results["alerts"] = {"error": str(e)}
            self.last_updated = time.time()
            return results


# Example usage and testing
if __name__ == "__main__":
    # Create a monitoring manager
    monitoring_config = {
        "alert_config": {
            "alert_rules": {
                "high_latency": {
                    "metric": "PerformanceMonitor.latency",
                    "threshold": 0.5,
                    "condition": "greater_than",
                    "message": "High latency detected in system performance"
                }
            },
            "notification_handler": lambda msg: print(f"ALERT NOTIFICATION: {msg}")
        },
        "dashboard_config": {
            "widgets": [
                {"type": "metric", "metric": "PerformanceMonitor.latency", "title": "System Latency"},
                {"type": "metric", "metric": "PerformanceMonitor.error_rate", "title": "Error Rate"}
            ],
            "refresh_interval": 10.0
        },
        "anomaly_config": {
            "thresholds": {
                "latency": {"stdev_multiplier": 2.0},
                "error_rate": {"stdev_multiplier": 3.0}
            }
        }
    }
    monitoring_manager = MonitoringManager("TestMonitoringManager", config=monitoring_config)

    # Register monitors
    perf_monitor = PerformanceMonitor("PerformanceMonitor")
    event_tracer = EventTracer("EventTracer")
    monitoring_manager.register_monitor(perf_monitor)
    monitoring_manager.register_monitor(event_tracer)

    # Activate monitoring
    monitoring_manager.activate()

    # Simulate a target entity for monitoring
    class TestTarget:
        def __init__(self, name):
            self.name = name
            self.performance_metrics = {
                "total_executions": 10,
                "successful_executions": 8,
                "failed_executions": 2,
                "average_execution_time": 0.3
            }

        def get_monitoring_data(self):
            return {"performance_metrics": self.performance_metrics}

    target = TestTarget("TestAgent")

    # Collect monitoring data
    data = monitoring_manager.collect_monitoring_data(target, context={"latency": 0.6, "error_rate": 0.2, "throughput": 100.0})
    print(f"Monitoring Data: {json.dumps(data, indent=2)[:500]}... (truncated)")

    # Trace an event
    event_data = event_tracer.collect_data(target, context={"event_type": "task_completion", "trace_id": "trace123", "details": {"task_id": "task456"}})
    print(f"Event Data: {event_data}")

    # Check trace
    trace_events = event_tracer.get_trace("trace123")
    print(f"Trace Events for trace123: {trace_events}")

    # Refresh dashboard
    dashboard_data = monitoring_manager.refresh_dashboard()
    print(f"Dashboard Data: {dashboard_data}")

    # Simulate security monitoring
    security_data = {
        "failed_auth_attempts": 6,
        "suspicious_access_patterns": ["unusual_ip", "rapid_access"]
    }
    security_results = monitoring_manager.security_monitoring(security_data)
    print(f"Security Monitoring Results: {security_results}")

    # Get overall monitoring summary
    summary = monitoring_manager.get_monitoring_summary()
    print(f"Monitoring Summary: {json.dumps(summary, indent=2)[:500]}... (truncated)")
