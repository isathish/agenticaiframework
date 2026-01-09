"""
Memory Package for the Agentic AI Framework.

Provides multi-tier memory management with TTL, eviction, and consolidation.
"""

from .types import MemoryEntry, MemoryStats
from .manager import MemoryManager

__all__ = [
    # Types
    'MemoryEntry',
    'MemoryStats',
    
    # Manager
    'MemoryManager',
    
    # Global instance
    'memory_manager',
]

# Global instance for convenience
memory_manager = MemoryManager()
