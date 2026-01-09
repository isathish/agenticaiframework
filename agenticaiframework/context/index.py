"""
Semantic index for context retrieval using embeddings.
"""

from typing import Dict, List, Tuple

from .items import ContextItem


class SemanticContextIndex:
    """Semantic index for context retrieval using embeddings."""
    
    def __init__(self):
        self.items: Dict[str, ContextItem] = {}
        self._embedding_cache: Dict[str, List[float]] = {}
    
    def add(self, item: ContextItem) -> None:
        """Add item to semantic index."""
        self.items[item.id] = item
        if item.embedding:
            self._embedding_cache[item.id] = item.embedding
    
    def remove(self, item_id: str) -> None:
        """Remove item from index."""
        self.items.pop(item_id, None)
        self._embedding_cache.pop(item_id, None)
    
    def clear(self) -> None:
        """Clear all items from index."""
        self.items.clear()
        self._embedding_cache.clear()
    
    def search(self, query_embedding: List[float], top_k: int = 5) -> List[Tuple[ContextItem, float]]:
        """Search for similar items using cosine similarity."""
        if not query_embedding or not self._embedding_cache:
            return []
        
        results = []
        for item_id, embedding in self._embedding_cache.items():
            if item_id in self.items:
                similarity = self._cosine_similarity(query_embedding, embedding)
                results.append((self.items[item_id], similarity))
        
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between vectors."""
        if len(a) != len(b):
            return 0.0
        
        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return dot_product / (norm_a * norm_b)
    
    def __len__(self) -> int:
        """Return number of items in index."""
        return len(self.items)
