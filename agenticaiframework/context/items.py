"""
Context item representation for the Agentic Context Engine.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .types import ContextType, ContextPriority


@dataclass
class ContextItem:
    """Rich context item with metadata."""
    id: str
    content: str
    context_type: ContextType
    priority: ContextPriority
    tokens: int
    importance: float
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None
    parent_id: Optional[str] = None
    children_ids: List[str] = field(default_factory=list)
    ttl: Optional[float] = None  # Time-to-live in seconds
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)
    
    def is_expired(self) -> bool:
        """Check if context item has expired."""
        if self.ttl is None:
            return False
        age = (datetime.now() - self.timestamp).total_seconds()
        return age > self.ttl
    
    def compute_relevance_score(self, query: str) -> float:
        """Compute basic relevance score (word overlap)."""
        query_words = set(query.lower().split())
        content_words = set(self.content.lower().split())
        if not query_words:
            return 0.0
        overlap = len(query_words & content_words)
        return overlap / len(query_words)
    
    def mark_accessed(self) -> None:
        """Mark the item as accessed."""
        self.access_count += 1
        self.last_accessed = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'id': self.id,
            'content': self.content,
            'context_type': self.context_type.value,
            'priority': self.priority.name,
            'tokens': self.tokens,
            'importance': self.importance,
            'timestamp': self.timestamp.isoformat(),
            'ttl': self.ttl,
            'access_count': self.access_count,
            'tags': self.tags,
        }
