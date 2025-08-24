from typing import Dict, Any, List
import time


class Hub:
    def __init__(self):
        self.agents: Dict[str, Any] = {}
        self.prompts: Dict[str, Any] = {}
        self.tools: Dict[str, Any] = {}
        self.guardrails: Dict[str, Any] = {}
        self.llms: Dict[str, Any] = {}

    def register(self, category: str, name: str, item: Any):
        if hasattr(self, category):
            getattr(self, category)[name] = item
            self._log(f"Registered {category[:-1]} '{name}'")
        else:
            self._log(f"Invalid category '{category}'")

    def get(self, category: str, name: str) -> Any:
        if hasattr(self, category):
            return getattr(self, category).get(name)
        return None

    def list_items(self, category: str) -> List[str]:
        if hasattr(self, category):
            return list(getattr(self, category).keys())
        return []

    def remove(self, category: str, name: str):
        if hasattr(self, category) and name in getattr(self, category):
            del getattr(self, category)[name]
            self._log(f"Removed {category[:-1]} '{name}'")

    def _log(self, message: str):
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [Hub] {message}")
