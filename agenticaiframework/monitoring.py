from typing import Dict, Any, List
import time


class MonitoringSystem:
    def __init__(self):
        self.metrics: Dict[str, Any] = {}
        self.logs: List[str] = []
        self.events: List[Dict[str, Any]] = []

    def record_metric(self, name: str, value: Any):
        self.metrics[name] = value
        self._log(f"Metric recorded: {name} = {value}")

    def get_metric(self, name: str) -> Any:
        return self.metrics.get(name)

    def log_event(self, event_type: str, details: Dict[str, Any]):
        event = {"type": event_type, "details": details, "timestamp": time.time()}
        self.events.append(event)
        self._log(f"Event logged: {event_type} - {details}")

    def get_events(self) -> List[Dict[str, Any]]:
        return self.events

    def log_message(self, message: str):
        timestamped_message = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}"
        self.logs.append(timestamped_message)
        print(timestamped_message)

    def get_logs(self) -> List[str]:
        return self.logs

    def _log(self, message: str):
        self.log_message(f"[MonitoringSystem] {message}")
