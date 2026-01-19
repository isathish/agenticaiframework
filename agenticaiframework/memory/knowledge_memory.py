"""
Knowledge Memory Management.

Provides memory for knowledge base operations:
- Embedding cache
- Query result cache  
- Retrieval history
- Document tracking
"""

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from .manager import MemoryManager

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingCache:
    """Cached embedding for text."""
    cache_key: str
    text_hash: str
    embedding: List[float]
    model: str
    dimension: int
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    expires_at: Optional[str] = None
    hit_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "cache_key": self.cache_key,
            "text_hash": self.text_hash,
            "embedding": self.embedding,
            "model": self.model,
            "dimension": self.dimension,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "hit_count": self.hit_count,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EmbeddingCache":
        return cls(
            cache_key=data["cache_key"],
            text_hash=data["text_hash"],
            embedding=data["embedding"],
            model=data["model"],
            dimension=data.get("dimension", len(data["embedding"])),
            created_at=data.get("created_at", datetime.now().isoformat()),
            expires_at=data.get("expires_at"),
            hit_count=data.get("hit_count", 0),
        )
    
    @property
    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        return datetime.fromisoformat(self.expires_at) < datetime.now()


@dataclass
class QueryResult:
    """Cached query result."""
    query_hash: str
    query: str
    results: List[Dict[str, Any]]  # chunks with scores
    total_results: int
    kb_id: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    expires_at: Optional[str] = None
    hit_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "query_hash": self.query_hash,
            "query": self.query,
            "results": self.results,
            "total_results": self.total_results,
            "kb_id": self.kb_id,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "hit_count": self.hit_count,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QueryResult":
        return cls(
            query_hash=data["query_hash"],
            query=data["query"],
            results=data["results"],
            total_results=data.get("total_results", len(data["results"])),
            kb_id=data["kb_id"],
            created_at=data.get("created_at", datetime.now().isoformat()),
            expires_at=data.get("expires_at"),
            hit_count=data.get("hit_count", 0),
        )
    
    @property
    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        return datetime.fromisoformat(self.expires_at) < datetime.now()


@dataclass
class RetrievalRecord:
    """Record of a retrieval operation."""
    retrieval_id: str
    query: str
    kb_id: str
    results_count: int
    top_score: float
    avg_score: float
    latency_ms: int
    agent_id: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    feedback: Optional[str] = None  # relevant, partial, irrelevant
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "retrieval_id": self.retrieval_id,
            "query": self.query,
            "kb_id": self.kb_id,
            "results_count": self.results_count,
            "top_score": self.top_score,
            "avg_score": self.avg_score,
            "latency_ms": self.latency_ms,
            "agent_id": self.agent_id,
            "timestamp": self.timestamp,
            "feedback": self.feedback,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RetrievalRecord":
        return cls(
            retrieval_id=data["retrieval_id"],
            query=data["query"],
            kb_id=data["kb_id"],
            results_count=data["results_count"],
            top_score=data.get("top_score", 0.0),
            avg_score=data.get("avg_score", 0.0),
            latency_ms=data.get("latency_ms", 0),
            agent_id=data.get("agent_id"),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            feedback=data.get("feedback"),
        )


@dataclass
class DocumentMemory:
    """Memory about a processed document."""
    doc_id: str
    source_path: str
    doc_type: str
    chunk_count: int
    total_tokens: int
    processed_at: str
    last_accessed: str
    access_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "source_path": self.source_path,
            "doc_type": self.doc_type,
            "chunk_count": self.chunk_count,
            "total_tokens": self.total_tokens,
            "processed_at": self.processed_at,
            "last_accessed": self.last_accessed,
            "access_count": self.access_count,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DocumentMemory":
        return cls(
            doc_id=data["doc_id"],
            source_path=data["source_path"],
            doc_type=data["doc_type"],
            chunk_count=data["chunk_count"],
            total_tokens=data.get("total_tokens", 0),
            processed_at=data["processed_at"],
            last_accessed=data.get("last_accessed", data["processed_at"]),
            access_count=data.get("access_count", 0),
            metadata=data.get("metadata", {}),
        )


class KnowledgeMemoryManager:
    """
    Manages memory for knowledge base operations.
    
    Example:
        >>> kb_memory = KnowledgeMemoryManager()
        >>> 
        >>> # Cache embedding
        >>> kb_memory.cache_embedding("Hello world", [0.1, 0.2, ...], model="openai")
        >>> 
        >>> # Get cached embedding
        >>> embedding = kb_memory.get_cached_embedding("Hello world", model="openai")
        >>> 
        >>> # Cache query results
        >>> kb_memory.cache_query_result("What is AI?", results, kb_id="kb-1")
        >>> 
        >>> # Record retrieval
        >>> kb_memory.record_retrieval(query, kb_id, results, latency_ms=50)
    """
    
    def __init__(
        self,
        memory_manager: MemoryManager = None,
        embedding_cache_ttl: int = 86400,  # 24 hours
        query_cache_ttl: int = 3600,  # 1 hour
        max_retrieval_history: int = 1000,
    ):
        self.memory = memory_manager or MemoryManager()
        self.embedding_cache_ttl = embedding_cache_ttl
        self.query_cache_ttl = query_cache_ttl
        self.max_retrieval_history = max_retrieval_history
        
        # In-memory caches
        self._embedding_cache: Dict[str, EmbeddingCache] = {}
        self._query_cache: Dict[str, QueryResult] = {}
        self._retrieval_history: List[RetrievalRecord] = []
        self._documents: Dict[str, DocumentMemory] = {}
    
    def _hash_text(self, text: str) -> str:
        """Create hash from text."""
        return hashlib.sha256(text.encode()).hexdigest()[:16]
    
    def _embedding_key(self, text: str, model: str) -> str:
        """Generate cache key for embedding."""
        text_hash = self._hash_text(text)
        return f"emb:{model}:{text_hash}"
    
    def _query_key(self, query: str, kb_id: str) -> str:
        """Generate cache key for query."""
        query_hash = self._hash_text(query)
        return f"query:{kb_id}:{query_hash}"
    
    # =========================================================================
    # Embedding Cache
    # =========================================================================
    
    def cache_embedding(
        self,
        text: str,
        embedding: List[float],
        model: str,
        ttl: int = None,
    ) -> str:
        """Cache an embedding."""
        cache_key = self._embedding_key(text, model)
        
        expires_at = None
        if ttl or self.embedding_cache_ttl:
            ttl = ttl or self.embedding_cache_ttl
            expires_at = (datetime.now() + timedelta(seconds=ttl)).isoformat()
        
        entry = EmbeddingCache(
            cache_key=cache_key,
            text_hash=self._hash_text(text),
            embedding=embedding,
            model=model,
            dimension=len(embedding),
            expires_at=expires_at,
        )
        
        self._embedding_cache[cache_key] = entry
        
        # Persist to long-term (embeddings are expensive to compute)
        self.memory.store_long_term(
            f"knowledge:{cache_key}",
            entry.to_dict(),
            priority=8,
        )
        
        return cache_key
    
    def get_cached_embedding(
        self,
        text: str,
        model: str,
    ) -> Optional[List[float]]:
        """Get cached embedding if available."""
        cache_key = self._embedding_key(text, model)
        
        # Check in-memory cache
        if cache_key in self._embedding_cache:
            entry = self._embedding_cache[cache_key]
            if not entry.is_expired:
                entry.hit_count += 1
                return entry.embedding
            else:
                del self._embedding_cache[cache_key]
        
        # Check persistent cache
        data = self.memory.retrieve(f"knowledge:{cache_key}")
        if data:
            entry = EmbeddingCache.from_dict(data)
            if not entry.is_expired:
                entry.hit_count += 1
                self._embedding_cache[cache_key] = entry
                return entry.embedding
        
        return None
    
    def batch_cache_embeddings(
        self,
        texts: List[str],
        embeddings: List[List[float]],
        model: str,
    ) -> List[str]:
        """Cache multiple embeddings."""
        keys = []
        for text, embedding in zip(texts, embeddings):
            key = self.cache_embedding(text, embedding, model)
            keys.append(key)
        return keys
    
    def get_cached_embeddings_batch(
        self,
        texts: List[str],
        model: str,
    ) -> Tuple[List[List[float]], List[int]]:
        """
        Get cached embeddings for multiple texts.
        
        Returns:
            Tuple of (found embeddings, indices of texts not in cache)
        """
        embeddings = []
        missing_indices = []
        
        for i, text in enumerate(texts):
            emb = self.get_cached_embedding(text, model)
            if emb is not None:
                embeddings.append(emb)
            else:
                embeddings.append(None)
                missing_indices.append(i)
        
        return embeddings, missing_indices
    
    def clear_embedding_cache(self, model: str = None) -> int:
        """Clear embedding cache."""
        count = 0
        keys_to_remove = []
        
        for key, entry in self._embedding_cache.items():
            if model is None or entry.model == model:
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self._embedding_cache[key]
            count += 1
        
        return count
    
    # =========================================================================
    # Query Result Cache
    # =========================================================================
    
    def cache_query_result(
        self,
        query: str,
        results: List[Dict[str, Any]],
        kb_id: str,
        ttl: int = None,
    ) -> str:
        """Cache query results."""
        cache_key = self._query_key(query, kb_id)
        
        expires_at = None
        if ttl or self.query_cache_ttl:
            ttl = ttl or self.query_cache_ttl
            expires_at = (datetime.now() + timedelta(seconds=ttl)).isoformat()
        
        entry = QueryResult(
            query_hash=self._hash_text(query),
            query=query,
            results=results,
            total_results=len(results),
            kb_id=kb_id,
            expires_at=expires_at,
        )
        
        self._query_cache[cache_key] = entry
        
        # Persist to short-term (query results change more often)
        self.memory.store_short_term(
            f"knowledge:{cache_key}",
            entry.to_dict(),
            ttl=ttl or self.query_cache_ttl,
            priority=5,
        )
        
        return cache_key
    
    def get_cached_query_result(
        self,
        query: str,
        kb_id: str,
    ) -> Optional[List[Dict[str, Any]]]:
        """Get cached query results if available."""
        cache_key = self._query_key(query, kb_id)
        
        # Check in-memory cache
        if cache_key in self._query_cache:
            entry = self._query_cache[cache_key]
            if not entry.is_expired:
                entry.hit_count += 1
                return entry.results
            else:
                del self._query_cache[cache_key]
        
        # Check persistent cache
        data = self.memory.retrieve(f"knowledge:{cache_key}")
        if data:
            entry = QueryResult.from_dict(data)
            if not entry.is_expired:
                entry.hit_count += 1
                self._query_cache[cache_key] = entry
                return entry.results
        
        return None
    
    def invalidate_query_cache(self, kb_id: str = None) -> int:
        """Invalidate query cache."""
        count = 0
        keys_to_remove = []
        
        for key, entry in self._query_cache.items():
            if kb_id is None or entry.kb_id == kb_id:
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self._query_cache[key]
            count += 1
        
        return count
    
    # =========================================================================
    # Retrieval History
    # =========================================================================
    
    def record_retrieval(
        self,
        query: str,
        kb_id: str,
        results: List[Dict[str, Any]],
        latency_ms: int,
        agent_id: str = None,
    ) -> RetrievalRecord:
        """Record a retrieval operation."""
        import uuid
        
        scores = [r.get("score", 0.0) for r in results]
        top_score = max(scores) if scores else 0.0
        avg_score = sum(scores) / len(scores) if scores else 0.0
        
        record = RetrievalRecord(
            retrieval_id=f"ret-{uuid.uuid4().hex[:8]}",
            query=query,
            kb_id=kb_id,
            results_count=len(results),
            top_score=top_score,
            avg_score=avg_score,
            latency_ms=latency_ms,
            agent_id=agent_id,
        )
        
        self._retrieval_history.append(record)
        
        # Limit history
        while len(self._retrieval_history) > self.max_retrieval_history:
            self._retrieval_history.pop(0)
        
        # Persist
        self.memory.store_long_term(
            "knowledge:retrieval_history",
            [r.to_dict() for r in self._retrieval_history[-100:]],  # Last 100
            priority=5,
        )
        
        return record
    
    def add_retrieval_feedback(
        self,
        retrieval_id: str,
        feedback: str,  # relevant, partial, irrelevant
    ) -> bool:
        """Add feedback to a retrieval record."""
        for record in self._retrieval_history:
            if record.retrieval_id == retrieval_id:
                record.feedback = feedback
                return True
        return False
    
    def get_retrieval_history(
        self,
        kb_id: str = None,
        agent_id: str = None,
        last_n: int = None,
    ) -> List[RetrievalRecord]:
        """Get retrieval history."""
        if not self._retrieval_history:
            data = self.memory.retrieve("knowledge:retrieval_history", [])
            self._retrieval_history = [RetrievalRecord.from_dict(r) for r in data]
        
        history = self._retrieval_history
        
        if kb_id:
            history = [r for r in history if r.kb_id == kb_id]
        
        if agent_id:
            history = [r for r in history if r.agent_id == agent_id]
        
        if last_n:
            history = history[-last_n:]
        
        return history
    
    def get_retrieval_stats(self, kb_id: str = None) -> Dict[str, Any]:
        """Get retrieval statistics."""
        history = self.get_retrieval_history(kb_id=kb_id)
        
        if not history:
            return {
                "total_retrievals": 0,
                "avg_latency_ms": 0,
                "avg_results": 0,
                "avg_top_score": 0,
            }
        
        return {
            "total_retrievals": len(history),
            "avg_latency_ms": sum(r.latency_ms for r in history) / len(history),
            "avg_results": sum(r.results_count for r in history) / len(history),
            "avg_top_score": sum(r.top_score for r in history) / len(history),
            "feedback_counts": {
                "relevant": len([r for r in history if r.feedback == "relevant"]),
                "partial": len([r for r in history if r.feedback == "partial"]),
                "irrelevant": len([r for r in history if r.feedback == "irrelevant"]),
            },
        }
    
    # =========================================================================
    # Document Tracking
    # =========================================================================
    
    def track_document(
        self,
        doc_id: str,
        source_path: str,
        doc_type: str,
        chunk_count: int,
        total_tokens: int = 0,
        metadata: Dict = None,
    ) -> DocumentMemory:
        """Track a processed document."""
        now = datetime.now().isoformat()
        
        doc = DocumentMemory(
            doc_id=doc_id,
            source_path=source_path,
            doc_type=doc_type,
            chunk_count=chunk_count,
            total_tokens=total_tokens,
            processed_at=now,
            last_accessed=now,
            metadata=metadata or {},
        )
        
        self._documents[doc_id] = doc
        
        self.memory.store_long_term(
            f"knowledge:doc:{doc_id}",
            doc.to_dict(),
            priority=6,
        )
        
        return doc
    
    def access_document(self, doc_id: str) -> Optional[DocumentMemory]:
        """Record document access."""
        if doc_id in self._documents:
            doc = self._documents[doc_id]
        else:
            data = self.memory.retrieve(f"knowledge:doc:{doc_id}")
            if not data:
                return None
            doc = DocumentMemory.from_dict(data)
            self._documents[doc_id] = doc
        
        doc.last_accessed = datetime.now().isoformat()
        doc.access_count += 1
        
        self.memory.store_long_term(
            f"knowledge:doc:{doc_id}",
            doc.to_dict(),
        )
        
        return doc
    
    def get_document_info(self, doc_id: str) -> Optional[DocumentMemory]:
        """Get document info."""
        if doc_id in self._documents:
            return self._documents[doc_id]
        
        data = self.memory.retrieve(f"knowledge:doc:{doc_id}")
        if data:
            doc = DocumentMemory.from_dict(data)
            self._documents[doc_id] = doc
            return doc
        
        return None
    
    def get_frequently_accessed_docs(
        self,
        top_k: int = 10,
    ) -> List[DocumentMemory]:
        """Get most frequently accessed documents."""
        docs = list(self._documents.values())
        docs.sort(key=lambda d: d.access_count, reverse=True)
        return docs[:top_k]
    
    # =========================================================================
    # Stats & Cleanup
    # =========================================================================
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        embedding_hits = sum(e.hit_count for e in self._embedding_cache.values())
        query_hits = sum(q.hit_count for q in self._query_cache.values())
        
        return {
            "embedding_cache_size": len(self._embedding_cache),
            "embedding_cache_hits": embedding_hits,
            "query_cache_size": len(self._query_cache),
            "query_cache_hits": query_hits,
            "retrieval_history_size": len(self._retrieval_history),
            "tracked_documents": len(self._documents),
        }
    
    def cleanup_expired(self) -> Dict[str, int]:
        """Clean up expired cache entries."""
        embedding_cleaned = 0
        query_cleaned = 0
        
        # Clean embedding cache
        expired_emb = [k for k, v in self._embedding_cache.items() if v.is_expired]
        for key in expired_emb:
            del self._embedding_cache[key]
            embedding_cleaned += 1
        
        # Clean query cache
        expired_query = [k for k, v in self._query_cache.items() if v.is_expired]
        for key in expired_query:
            del self._query_cache[key]
            query_cleaned += 1
        
        return {
            "embeddings_cleaned": embedding_cleaned,
            "queries_cleaned": query_cleaned,
        }


__all__ = [
    "EmbeddingCache",
    "QueryResult",
    "RetrievalRecord",
    "DocumentMemory",
    "KnowledgeMemoryManager",
]
