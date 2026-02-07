from typing import Any, Dict
import logging
import threading

logger = logging.getLogger(__name__)


class ConfigurationManager:
    """Thread-safe configuration manager for framework components."""

    def __init__(self) -> None:
        self.configurations: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def set_config(self, component: str, config: Dict[str, Any]) -> None:
        with self._lock:
            self.configurations[component] = config
        logger.info("Configuration set for '%s'", component)

    def get_config(self, component: str) -> Dict[str, Any]:
        with self._lock:
            return self.configurations.get(component, {})

    def update_config(self, component: str, updates: Dict[str, Any]) -> None:
        with self._lock:
            if component in self.configurations:
                self.configurations[component].update(updates)
                logger.info("Configuration updated for '%s'", component)
            else:
                self.configurations[component] = updates
                logger.info("Configuration set for '%s'", component)

    def remove_config(self, component: str) -> None:
        with self._lock:
            if component in self.configurations:
                del self.configurations[component]
                logger.info("Configuration removed for '%s'", component)

    def list_components(self) -> list[str]:
        with self._lock:
            return list(self.configurations.keys())
