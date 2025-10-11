from typing import Dict, Any
import time


class MemoryManager:
    def __init__(self):
        self.short_term: Dict[str, Any] = {}
        self.long_term: Dict[str, Any] = {}
        self.external: Dict[str, Any] = {}

    def store_short_term(self, key: str, value: Any):
        self.short_term[key] = value
        self._log(f"Stored short-term memory: {key}")

    def store(self, key: str, value: Any, memory_type: str = "short_term"):
        """Generic store method that defaults to short-term memory"""
        if memory_type == "long_term":
            self.store_long_term(key, value)
        elif memory_type == "external":
            self.store_external(key, value)
        else:
            self.store_short_term(key, value)

    def store_long_term(self, key: str, value: Any):
        self.long_term[key] = value
        self._log(f"Stored long-term memory: {key}")

    def store_external(self, key: str, value: Any):
        self.external[key] = value
        self._log(f"Stored external memory: {key}")

    def retrieve(self, key: str) -> Any:
        if key in self.short_term:
            return self.short_term[key]
        if key in self.long_term:
            return self.long_term[key]
        if key in self.external:
            return self.external[key]
        return None

    def clear_short_term(self):
        self.short_term.clear()
        self._log("Cleared short-term memory")

    def clear_long_term(self):
        self.long_term.clear()
        self._log("Cleared long-term memory")

    def clear_external(self):
        self.external.clear()
        self._log("Cleared external memory")

    def _log(self, message: str):
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [MemoryManager] {message}")
