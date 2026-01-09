"""
Compatibility layer for legacy Memory API.

Provides mixin class with legacy method signatures for backward compatibility.
"""

from typing import Any
import time


class MemoryCompatMixin:
    """
    Mixin class providing legacy API compatibility.
    
    This mixin adds backward-compatible methods to MemoryManager
    for code that uses the older API.
    """
    
    def _compat_log(self, message: str):
        """Log a message for compatibility operations."""
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [MemoryManager] {message}")
    
    def set_memory(self, memory_type: str, key: str, value: Any):
        """Legacy API: Store in specified memory tier."""
        if memory_type == "short" or memory_type == "short_term":
            self.store_short_term(key, value)
        elif memory_type == "long" or memory_type == "long_term":
            self.store_long_term(key, value)
        elif memory_type == "external":
            self.store_external(key, value)
        else:
            self._compat_log(f"unknown memory type '{memory_type}', defaulting to short_term")
            self.store_short_term(key, value)
    
    def get_memory(self, memory_type: str, key: str, default: Any = None) -> Any:
        """Legacy API: Get from specified memory tier."""
        if memory_type == "short" or memory_type == "short_term":
            if key in self.short_term:
                return self.short_term[key].value
        elif memory_type == "long" or memory_type == "long_term":
            if key in self.long_term:
                return self.long_term[key].value
        elif memory_type == "external":
            if key in self.external:
                return self.external[key].value
        else:
            self._compat_log(f"unknown memory type '{memory_type}'")
        return default
    
    def clear_memory(self, memory_type: str):
        """Legacy API: Clear specified memory tier."""
        if memory_type == "short" or memory_type == "short_term":
            self.short_term.clear()
        elif memory_type == "long" or memory_type == "long_term":
            self.long_term.clear()
        elif memory_type == "external":
            self.external.clear()
    
    def clear_short_term(self):
        """Legacy API: Clear short-term memory."""
        self.short_term.clear()
    
    def clear_long_term(self):
        """Legacy API: Clear long-term memory."""
        self.long_term.clear()
    
    def clear_external(self):
        """Legacy API: Clear external memory."""
        self.external.clear()
    
    def clear_all(self):
        """Legacy API: Clear all memory tiers."""
        self.short_term.clear()
        self.long_term.clear()
        self.external.clear()
