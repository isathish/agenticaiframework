"""
Advanced Context Manager implementing Agentic Context Engine (ACE).

Features:
- Intelligent token management
- Semantic context retrieval
- Priority-based eviction
- Context compression
- Memory-aware optimization
- Multi-turn conversation support
"""

import uuid
import logging
from collections import deque
from datetime import datetime
from typing import Any, Dict, List, Optional

from .types import ContextType, ContextPriority, ContextRetrievalStrategy
from .items import ContextItem
from .index import SemanticContextIndex
from .compression import ContextCompressionStrategy

logger = logging.getLogger(__name__)


class ContextManager:
    """
    Advanced Context Manager implementing Agentic Context Engine (ACE).
    
    Features:
    - Intelligent token management
    - Semantic context retrieval
    - Priority-based eviction
    - Context compression
    - Memory-aware optimization
    - Multi-turn conversation support
    """
    
    # Default type-specific token budgets
    DEFAULT_TYPE_BUDGETS = {
        ContextType.SYSTEM: 0.15,       # 15% for system prompts
        ContextType.KNOWLEDGE: 0.25,    # 25% for RAG knowledge
        ContextType.MEMORY: 0.15,       # 15% for memories
        ContextType.USER: 0.20,         # 20% for user messages
        ContextType.ASSISTANT: 0.15,    # 15% for assistant responses
        ContextType.TOOL_RESULT: 0.10,  # 10% for tool results
    }
    
    def __init__(self, 
                 max_tokens: int = 4096, 
                 compression_threshold: float = 0.8,
                 enable_semantic_search: bool = True,
                 default_retrieval_strategy: ContextRetrievalStrategy = ContextRetrievalStrategy.HYBRID):
        """
        Initialize context manager.
        
        Args:
            max_tokens: Maximum context window size in tokens
            compression_threshold: Threshold (0-1) at which to trigger compression
            enable_semantic_search: Enable semantic similarity search
            default_retrieval_strategy: Default strategy for context retrieval
        """
        self.max_tokens = max_tokens
        self.compression_threshold = compression_threshold
        self.enable_semantic_search = enable_semantic_search
        self.default_retrieval_strategy = default_retrieval_strategy
        
        self.current_tokens = 0
        self.context_history: deque = deque(maxlen=1000)
        self.important_context: List[ContextItem] = []
        
        # Semantic index
        self.semantic_index = SemanticContextIndex() if enable_semantic_search else None
        
        # Context graphs (for tracking relationships)
        self.context_graph: Dict[str, List[str]] = {}  # parent -> children
        
        # Statistics
        self.compression_stats = {
            'total_compressions': 0,
            'tokens_saved': 0,
            'items_merged': 0,
            'items_evicted': 0
        }
        
        # Type-specific token budgets
        self.type_budgets = self.DEFAULT_TYPE_BUDGETS.copy()
        
    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.
        Uses simple heuristic: ~4 characters per token.
        For production, use tiktoken or similar.
        """
        if not text:
            return 0
        return max(1, int(len(text.split()) * 1.3))
    
    def add_context(self, 
                    content: str, 
                    metadata: Optional[Dict[str, Any]] = None, 
                    importance: float = 0.5,
                    context_type: ContextType = ContextType.USER,
                    priority: ContextPriority = ContextPriority.MEDIUM,
                    embedding: Optional[List[float]] = None,
                    parent_id: Optional[str] = None,
                    ttl: Optional[float] = None,
                    tags: Optional[List[str]] = None) -> ContextItem:
        """
        Add content to context with rich metadata.
        
        Args:
            content: Context content
            metadata: Additional metadata
            importance: Importance score (0-1), higher = more important
            context_type: Type of context
            priority: Retention priority
            embedding: Optional embedding vector for semantic search
            parent_id: Parent context item ID (for hierarchical context)
            ttl: Time-to-live in seconds
            tags: Searchable tags
            
        Returns:
            Created ContextItem
        """
        tokens = self.estimate_tokens(content)
        
        # Auto-adjust priority based on importance
        if importance >= 0.9:
            priority = ContextPriority.CRITICAL
        elif importance >= 0.7:
            priority = ContextPriority.HIGH
        
        context_item = ContextItem(
            id=str(uuid.uuid4()),
            content=content,
            context_type=context_type,
            priority=priority,
            tokens=tokens,
            importance=importance,
            timestamp=datetime.now(),
            metadata=metadata or {},
            embedding=embedding,
            parent_id=parent_id,
            ttl=ttl,
            tags=tags or []
        )
        
        self.context_history.append(context_item)
        self.current_tokens += tokens
        
        # Update context graph
        if parent_id and parent_id in self.context_graph:
            self.context_graph[parent_id].append(context_item.id)
        self.context_graph[context_item.id] = []
        
        # Add to semantic index
        if self.semantic_index and embedding:
            self.semantic_index.add(context_item)
        
        # Mark as important if high importance score
        if importance >= 0.8:
            self.important_context.append(context_item)
        
        # Check if compression needed
        if self.current_tokens > self.max_tokens * self.compression_threshold:
            self._compress_context()
        
        return context_item
    
    def retrieve_context(self,
                        query: Optional[str] = None,
                        query_embedding: Optional[List[float]] = None,
                        strategy: Optional[ContextRetrievalStrategy] = None,
                        max_items: int = 10,
                        max_tokens: Optional[int] = None,
                        context_types: Optional[List[ContextType]] = None,
                        min_importance: float = 0.0,
                        tags: Optional[List[str]] = None) -> List[ContextItem]:
        """
        Retrieve context using specified strategy.
        
        Args:
            query: Text query for relevance-based retrieval
            query_embedding: Embedding for semantic search
            strategy: Retrieval strategy (defaults to instance default)
            max_items: Maximum items to retrieve
            max_tokens: Maximum total tokens to retrieve
            context_types: Filter by context types
            min_importance: Minimum importance threshold
            tags: Filter by tags
            
        Returns:
            List of relevant context items
        """
        strategy = strategy or self.default_retrieval_strategy
        items = list(self.context_history)
        
        # Apply filters
        items = self._filter_items(items, context_types, min_importance, tags)
        
        # Apply retrieval strategy
        items = self._apply_strategy(items, strategy, query, query_embedding, max_items)
        
        # Limit by tokens
        if max_tokens:
            items = self._limit_by_tokens(items, max_tokens)
        
        # Update access stats
        for item in items:
            item.mark_accessed()
        
        return items
    
    def _filter_items(self,
                     items: List[ContextItem],
                     context_types: Optional[List[ContextType]],
                     min_importance: float,
                     tags: Optional[List[str]]) -> List[ContextItem]:
        """Apply filters to items."""
        # Filter by type
        if context_types:
            items = [item for item in items if item.context_type in context_types]
        
        # Filter by importance
        items = [item for item in items if item.importance >= min_importance]
        
        # Filter by tags
        if tags:
            items = [item for item in items if any(tag in item.tags for tag in tags)]
        
        # Filter expired
        items = [item for item in items if not item.is_expired()]
        
        return items
    
    def _apply_strategy(self,
                       items: List[ContextItem],
                       strategy: ContextRetrievalStrategy,
                       query: Optional[str],
                       query_embedding: Optional[List[float]],
                       max_items: int) -> List[ContextItem]:
        """Apply retrieval strategy."""
        if strategy == ContextRetrievalStrategy.RECENCY:
            items.sort(key=lambda x: x.timestamp, reverse=True)
            
        elif strategy == ContextRetrievalStrategy.IMPORTANCE:
            items.sort(key=lambda x: (x.priority.value, x.importance), reverse=True)
            
        elif strategy == ContextRetrievalStrategy.RELEVANCE and query:
            items.sort(key=lambda x: x.compute_relevance_score(query), reverse=True)
            
        elif strategy == ContextRetrievalStrategy.SEMANTIC and query_embedding and self.semantic_index:
            results = self.semantic_index.search(query_embedding, top_k=max_items)
            return [item for item, _ in results]
            
        elif strategy == ContextRetrievalStrategy.HYBRID:
            items = self._apply_hybrid_scoring(items, query)
        
        return items[:max_items]
    
    def _apply_hybrid_scoring(self, items: List[ContextItem], query: Optional[str]) -> List[ContextItem]:
        """Apply hybrid scoring combining recency, importance, and relevance."""
        for item in items:
            recency_score = 1.0 / (1.0 + (datetime.now() - item.timestamp).total_seconds() / 3600)
            importance_score = item.importance
            relevance_score = item.compute_relevance_score(query) if query else 0.5
            item.metadata['_hybrid_score'] = (
                0.3 * recency_score + 
                0.4 * importance_score + 
                0.3 * relevance_score
            )
        items.sort(key=lambda x: x.metadata.get('_hybrid_score', 0), reverse=True)
        return items
    
    def _limit_by_tokens(self, items: List[ContextItem], max_tokens: int) -> List[ContextItem]:
        """Limit items by total token count."""
        filtered = []
        total_tokens = 0
        for item in items:
            if total_tokens + item.tokens <= max_tokens:
                filtered.append(item)
                total_tokens += item.tokens
            else:
                break
        return filtered
    
    def build_context_window(self,
                            query: Optional[str] = None,
                            include_system: bool = True,
                            include_memory: bool = True,
                            include_knowledge: bool = True) -> List[ContextItem]:
        """
        Build optimized context window for LLM call.
        
        Args:
            query: Current query for relevance scoring
            include_system: Include system prompts
            include_memory: Include memory context
            include_knowledge: Include RAG knowledge
            
        Returns:
            Optimized list of context items
        """
        window_items = []
        remaining_tokens = self.max_tokens - 500  # Reserve for response
        
        # 1. System context
        if include_system:
            system_items = self.retrieve_context(
                context_types=[ContextType.SYSTEM],
                strategy=ContextRetrievalStrategy.IMPORTANCE
            )
            for item in system_items:
                if item.tokens <= remaining_tokens:
                    window_items.append(item)
                    remaining_tokens -= item.tokens
        
        # 2. Knowledge (RAG)
        if include_knowledge:
            knowledge_budget = int(self.max_tokens * self.type_budgets.get(ContextType.KNOWLEDGE, 0.25))
            knowledge_items = self.retrieve_context(
                query=query,
                context_types=[ContextType.KNOWLEDGE],
                max_tokens=min(knowledge_budget, remaining_tokens),
                strategy=ContextRetrievalStrategy.RELEVANCE
            )
            for item in knowledge_items:
                if item.tokens <= remaining_tokens:
                    window_items.append(item)
                    remaining_tokens -= item.tokens
        
        # 3. Memories
        if include_memory:
            memory_budget = int(self.max_tokens * self.type_budgets.get(ContextType.MEMORY, 0.15))
            memory_items = self.retrieve_context(
                query=query,
                context_types=[ContextType.MEMORY],
                max_tokens=min(memory_budget, remaining_tokens),
                strategy=ContextRetrievalStrategy.HYBRID
            )
            for item in memory_items:
                if item.tokens <= remaining_tokens:
                    window_items.append(item)
                    remaining_tokens -= item.tokens
        
        # 4. Recent conversation
        conversation_items = self.retrieve_context(
            context_types=[ContextType.USER, ContextType.ASSISTANT],
            max_tokens=remaining_tokens,
            strategy=ContextRetrievalStrategy.RECENCY
        )
        window_items.extend(conversation_items)
        
        return window_items
    
    def _compress_context(self) -> None:
        """Compress context by removing less important items."""
        if not self.context_history:
            return
        
        # Clear expired items
        non_expired = []
        for item in self.context_history:
            if item.is_expired():
                self.current_tokens -= item.tokens
                self.compression_stats['items_evicted'] += 1
            else:
                non_expired.append(item)
        
        # Sort by importance
        sorted_context = sorted(
            non_expired,
            key=lambda x: (x.priority.value, x.importance),
            reverse=True
        )
        
        # Keep items that fit in budget
        target_tokens = int(self.max_tokens * 0.6)
        kept_items = ContextCompressionStrategy.truncate_by_priority(sorted_context, target_tokens)
        
        tokens_used = sum(item.tokens for item in kept_items)
        evicted_count = len(non_expired) - len(kept_items)
        
        self.context_history = deque(kept_items, maxlen=1000)
        self.compression_stats['tokens_saved'] += self.current_tokens - tokens_used
        self.compression_stats['items_evicted'] += evicted_count
        self.compression_stats['total_compressions'] += 1
        self.current_tokens = tokens_used
        
        logger.info("Context compressed: evicted %d items", evicted_count)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get context statistics."""
        type_distribution = {}
        priority_distribution = {}
        
        for item in self.context_history:
            type_distribution[item.context_type.value] = type_distribution.get(item.context_type.value, 0) + 1
            priority_distribution[item.priority.name] = priority_distribution.get(item.priority.name, 0) + 1
        
        return {
            'current_tokens': self.current_tokens,
            'max_tokens': self.max_tokens,
            'utilization': self.current_tokens / self.max_tokens if self.max_tokens > 0 else 0,
            'context_items': len(self.context_history),
            'important_items': len(self.important_context),
            'compression_stats': self.compression_stats,
            'type_distribution': type_distribution,
            'priority_distribution': priority_distribution,
            'semantic_index_size': len(self.semantic_index) if self.semantic_index else 0
        }
    
    def get_context_summary(self) -> str:
        """Get a summary of current context."""
        items = list(self.context_history)
        if not items:
            return "No context available."
        
        summary_parts = []
        for item in items[-10:]:
            summary_parts.append(f"- {item.content[:100]}")
        
        return "\n".join(summary_parts)
    
    def clear_context(self, context_type: Optional[ContextType] = None) -> None:
        """Clear context, optionally by type."""
        if context_type:
            items_to_keep = [item for item in self.context_history if item.context_type != context_type]
            removed_tokens = sum(
                item.tokens for item in self.context_history if item.context_type == context_type
            )
            self.context_history = deque(items_to_keep, maxlen=1000)
            self.current_tokens -= removed_tokens
        else:
            self.context_history.clear()
            self.important_context.clear()
            self.current_tokens = 0
            if self.semantic_index:
                self.semantic_index.clear()
