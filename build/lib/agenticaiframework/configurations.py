from typing import Dict, Any
import time


class ConfigurationManager:
    def __init__(self):
        self.configurations: Dict[str, Dict[str, Any]] = {}

    def set_config(self, component: str, config: Dict[str, Any]):
        self.configurations[component] = config
        self._log(f"Configuration set for '{component}'")

    def get_config(self, component: str) -> Dict[str, Any]:
        return self.configurations.get(component, {})

    def update_config(self, component: str, updates: Dict[str, Any]):
        if component in self.configurations:
            self.configurations[component].update(updates)
            self._log(f"Configuration updated for '{component}'")
        else:
            self.set_config(component, updates)

    def remove_config(self, component: str):
        if component in self.configurations:
            del self.configurations[component]
            self._log(f"Configuration removed for '{component}'")

    def list_components(self):
        return list(self.configurations.keys())

    def _log(self, message: str):
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [ConfigurationManager] {message}")
