"""
Sliding context window with intelligent management.
"""

from typing import List, Optional

from .types import ContextType, ContextPriority
from .items import ContextItem


class ContextWindow:
    """Sliding context window with intelligent management."""
    
    def __init__(self, max_tokens: int, reserve_tokens: int = 500):
        """
        Initialize context window.
        
        Args:
            max_tokens: Maximum tokens in window
            reserve_tokens: Tokens to reserve for response
        """
        self.max_tokens = max_tokens
        self.reserve_tokens = reserve_tokens
        self.items: List[ContextItem] = []
    
    @property
    def total_tokens(self) -> int:
        """Get total tokens used in window."""
        return sum(item.tokens for item in self.items)
    
    @property
    def available_tokens(self) -> int:
        """Get available tokens in window."""
        return self.max_tokens - self.reserve_tokens - self.total_tokens
    
    @property
    def utilization(self) -> float:
        """Get window utilization percentage."""
        if self.max_tokens <= 0:
            return 0.0
        return self.total_tokens / self.max_tokens
    
    def add(self, item: ContextItem) -> bool:
        """Add item if space available."""
        if item.tokens <= self.available_tokens:
            self.items.append(item)
            return True
        return False
    
    def remove(self, item_id: str) -> Optional[ContextItem]:
        """Remove item by ID."""
        for i, item in enumerate(self.items):
            if item.id == item_id:
                return self.items.pop(i)
        return None
    
    def evict_lowest_priority(self) -> Optional[ContextItem]:
        """Evict lowest priority non-critical item."""
        evictable = [
            item for item in self.items 
            if item.priority != ContextPriority.CRITICAL
        ]
        
        if not evictable:
            return None
        
        # Sort by priority (ascending) then by timestamp (oldest first)
        evictable.sort(key=lambda x: (x.priority.value, x.timestamp))
        item_to_evict = evictable[0]
        self.items.remove(item_to_evict)
        return item_to_evict
    
    def evict_until_available(self, required_tokens: int) -> List[ContextItem]:
        """Evict items until required tokens are available."""
        evicted = []
        while self.available_tokens < required_tokens:
            item = self.evict_lowest_priority()
            if item is None:
                break
            evicted.append(item)
        return evicted
    
    def get_by_type(self, context_type: ContextType) -> List[ContextItem]:
        """Get items by type."""
        return [item for item in self.items if item.context_type == context_type]
    
    def get_by_priority(self, min_priority: ContextPriority) -> List[ContextItem]:
        """Get items with at least the specified priority."""
        return [
            item for item in self.items 
            if item.priority.value >= min_priority.value
        ]
    
    def clear_expired(self) -> int:
        """Clear expired items and return count."""
        expired = [item for item in self.items if item.is_expired()]
        for item in expired:
            self.items.remove(item)
        return len(expired)
    
    def clear(self) -> None:
        """Clear all items from window."""
        self.items.clear()
    
    def __len__(self) -> int:
        """Return number of items in window."""
        return len(self.items)
