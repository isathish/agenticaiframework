from typing import Dict, Any, Callable
import time


class CommunicationManager:
    def __init__(self):
        self.protocols: Dict[str, Callable[[Any], Any]] = {}

    def register_protocol(self, name: str, handler_fn: Callable[[Any], Any]):
        self.protocols[name] = handler_fn
        self._log(f"Registered communication protocol '{name}'")

    def send(self, protocol: str, data: Any):
        if protocol in self.protocols:
            try:
                return self.protocols[protocol](data)
            except Exception as e:
                self._log(f"Error sending data via '{protocol}': {e}")
        else:
            self._log(f"Protocol '{protocol}' not found")
        return None

    def list_protocols(self):
        return list(self.protocols.keys())

    def _log(self, message: str):
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [CommunicationManager] {message}")
