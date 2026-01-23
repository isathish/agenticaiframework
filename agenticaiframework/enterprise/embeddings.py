"""
Enterprise Embeddings Module.

Provides text embeddings, similarity search, embedding caching,
and vector operations for agent applications.

Example:
    # Create embedder
    embedder = OpenAIEmbedder(client=openai_client)
    
    # Get embeddings
    vector = await embedder.embed("Hello world")
    vectors = await embedder.embed_batch(["Hello", "World"])
    
    # Cached embeddings
    cached = CachedEmbedder(embedder, cache=InMemoryCache())
    
    # Similarity
    score = cosine_similarity(v1, v2)
"""

from __future__ import annotations

import asyncio
import hashlib
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Tuple,
    TypeVar,
    Union,
)
from datetime import datetime
from functools import wraps
from enum import Enum
import logging
import time

logger = logging.getLogger(__name__)

T = TypeVar('T')

# Type alias for embeddings
Vector = List[float]


class EmbeddingError(Exception):
    """Embedding error."""
    pass


class DimensionMismatchError(EmbeddingError):
    """Vector dimension mismatch."""
    pass


class EmbeddingModel(str, Enum):
    """Common embedding models."""
    TEXT_EMBEDDING_3_SMALL = "text-embedding-3-small"
    TEXT_EMBEDDING_3_LARGE = "text-embedding-3-large"
    TEXT_EMBEDDING_ADA_002 = "text-embedding-ada-002"
    VOYAGE_2 = "voyage-2"
    VOYAGE_LARGE_2 = "voyage-large-2"
    COHERE_EMBED_V3 = "embed-english-v3.0"


@dataclass
class EmbeddingResult:
    """Result of embedding operation."""
    text: str
    vector: Vector
    model: str
    dimensions: int
    tokens: int = 0
    duration_ms: float = 0.0
    
    @property
    def magnitude(self) -> float:
        """Get vector magnitude."""
        return math.sqrt(sum(x * x for x in self.vector))
    
    def normalized(self) -> Vector:
        """Get L2 normalized vector."""
        mag = self.magnitude
        if mag == 0:
            return self.vector
        return [x / mag for x in self.vector]


@dataclass
class BatchEmbeddingResult:
    """Result of batch embedding."""
    results: List[EmbeddingResult]
    total_tokens: int = 0
    duration_ms: float = 0.0
    
    @property
    def vectors(self) -> List[Vector]:
        """Get all vectors."""
        return [r.vector for r in self.results]
    
    def __len__(self) -> int:
        return len(self.results)
    
    def __iter__(self):
        return iter(self.results)


@dataclass
class SimilarityResult:
    """Result of similarity comparison."""
    text1: str
    text2: str
    score: float
    method: str = "cosine"


# Vector operations
def cosine_similarity(a: Vector, b: Vector) -> float:
    """
    Calculate cosine similarity between two vectors.
    
    Args:
        a: First vector
        b: Second vector
        
    Returns:
        Similarity score between -1 and 1
    """
    if len(a) != len(b):
        raise DimensionMismatchError(f"Vectors have different dimensions: {len(a)} vs {len(b)}")
    
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    
    if norm_a == 0 or norm_b == 0:
        return 0.0
    
    return dot / (norm_a * norm_b)


def euclidean_distance(a: Vector, b: Vector) -> float:
    """
    Calculate Euclidean distance between two vectors.
    """
    if len(a) != len(b):
        raise DimensionMismatchError(f"Vectors have different dimensions: {len(a)} vs {len(b)}")
    
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def dot_product(a: Vector, b: Vector) -> float:
    """Calculate dot product of two vectors."""
    if len(a) != len(b):
        raise DimensionMismatchError(f"Vectors have different dimensions: {len(a)} vs {len(b)}")
    
    return sum(x * y for x, y in zip(a, b))


def l2_normalize(v: Vector) -> Vector:
    """L2 normalize a vector."""
    mag = math.sqrt(sum(x * x for x in v))
    if mag == 0:
        return v
    return [x / mag for x in v]


def average_vectors(vectors: List[Vector]) -> Vector:
    """Average multiple vectors."""
    if not vectors:
        return []
    
    dim = len(vectors[0])
    result = [0.0] * dim
    
    for v in vectors:
        for i, val in enumerate(v):
            result[i] += val
    
    n = len(vectors)
    return [x / n for x in result]


class Embedder(ABC):
    """Abstract embedder interface."""
    
    @property
    @abstractmethod
    def model(self) -> str:
        """Get model name."""
        pass
    
    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Get vector dimensions."""
        pass
    
    @abstractmethod
    async def embed(self, text: str) -> Vector:
        """Embed a single text."""
        pass
    
    @abstractmethod
    async def embed_batch(self, texts: List[str]) -> List[Vector]:
        """Embed multiple texts."""
        pass
    
    async def similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between texts."""
        v1 = await self.embed(text1)
        v2 = await self.embed(text2)
        return cosine_similarity(v1, v2)


class OpenAIEmbedder(Embedder):
    """OpenAI embeddings."""
    
    def __init__(
        self,
        client: Any,
        model: str = "text-embedding-3-small",
        dimensions: Optional[int] = None,
    ):
        self._client = client
        self._model = model
        self._dimensions = dimensions or self._default_dimensions(model)
    
    @staticmethod
    def _default_dimensions(model: str) -> int:
        """Get default dimensions for model."""
        defaults = {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536,
        }
        return defaults.get(model, 1536)
    
    @property
    def model(self) -> str:
        return self._model
    
    @property
    def dimensions(self) -> int:
        return self._dimensions
    
    async def embed(self, text: str) -> Vector:
        """Embed text using OpenAI."""
        response = await self._client.embeddings.create(
            model=self._model,
            input=text,
            dimensions=self._dimensions,
        )
        return response.data[0].embedding
    
    async def embed_batch(self, texts: List[str]) -> List[Vector]:
        """Embed batch using OpenAI."""
        response = await self._client.embeddings.create(
            model=self._model,
            input=texts,
            dimensions=self._dimensions,
        )
        return [item.embedding for item in response.data]


class MockEmbedder(Embedder):
    """Mock embedder for testing."""
    
    def __init__(
        self,
        dimensions: int = 384,
        model: str = "mock-embedder",
    ):
        self._dimensions = dimensions
        self._model = model
        self._cache: Dict[str, Vector] = {}
    
    @property
    def model(self) -> str:
        return self._model
    
    @property
    def dimensions(self) -> int:
        return self._dimensions
    
    async def embed(self, text: str) -> Vector:
        """Generate deterministic mock embedding."""
        if text in self._cache:
            return self._cache[text]
        
        # Generate deterministic vector from text hash
        hash_bytes = hashlib.sha256(text.encode()).digest()
        vector = []
        
        for i in range(self._dimensions):
            byte_idx = i % len(hash_bytes)
            value = (hash_bytes[byte_idx] - 128) / 128.0
            vector.append(value)
        
        # Normalize
        vector = l2_normalize(vector)
        self._cache[text] = vector
        
        return vector
    
    async def embed_batch(self, texts: List[str]) -> List[Vector]:
        """Embed batch."""
        return [await self.embed(text) for text in texts]


class CachedEmbedder(Embedder):
    """Embedder with caching."""
    
    def __init__(
        self,
        embedder: Embedder,
        cache: Optional[Any] = None,
        ttl: Optional[int] = None,
    ):
        self._embedder = embedder
        self._cache = cache or {}
        self._ttl = ttl
        self._stats = {"hits": 0, "misses": 0}
    
    @property
    def model(self) -> str:
        return self._embedder.model
    
    @property
    def dimensions(self) -> int:
        return self._embedder.dimensions
    
    @property
    def stats(self) -> Dict[str, int]:
        return self._stats.copy()
    
    def _cache_key(self, text: str) -> str:
        """Generate cache key."""
        return hashlib.md5(f"{self._embedder.model}:{text}".encode()).hexdigest()
    
    async def embed(self, text: str) -> Vector:
        """Embed with caching."""
        key = self._cache_key(text)
        
        # Check cache
        if isinstance(self._cache, dict):
            if key in self._cache:
                self._stats["hits"] += 1
                return self._cache[key]
        elif hasattr(self._cache, "get"):
            cached = await self._cache.get(key)
            if cached is not None:
                self._stats["hits"] += 1
                return cached
        
        # Miss - compute embedding
        self._stats["misses"] += 1
        vector = await self._embedder.embed(text)
        
        # Cache
        if isinstance(self._cache, dict):
            self._cache[key] = vector
        elif hasattr(self._cache, "set"):
            await self._cache.set(key, vector, ttl=self._ttl)
        
        return vector
    
    async def embed_batch(self, texts: List[str]) -> List[Vector]:
        """Embed batch with caching."""
        results = []
        to_embed = []
        to_embed_indices = []
        
        # Check cache for each
        for i, text in enumerate(texts):
            key = self._cache_key(text)
            cached = None
            
            if isinstance(self._cache, dict):
                cached = self._cache.get(key)
            elif hasattr(self._cache, "get"):
                cached = await self._cache.get(key)
            
            if cached is not None:
                results.append((i, cached))
                self._stats["hits"] += 1
            else:
                to_embed.append(text)
                to_embed_indices.append(i)
                self._stats["misses"] += 1
        
        # Embed uncached
        if to_embed:
            vectors = await self._embedder.embed_batch(to_embed)
            
            for idx, text, vector in zip(to_embed_indices, to_embed, vectors):
                key = self._cache_key(text)
                
                if isinstance(self._cache, dict):
                    self._cache[key] = vector
                elif hasattr(self._cache, "set"):
                    await self._cache.set(key, vector, ttl=self._ttl)
                
                results.append((idx, vector))
        
        # Sort by original index
        results.sort(key=lambda x: x[0])
        return [v for _, v in results]
    
    def clear_cache(self) -> None:
        """Clear the cache."""
        if isinstance(self._cache, dict):
            self._cache.clear()
        elif hasattr(self._cache, "clear"):
            asyncio.create_task(self._cache.clear())


class ChunkedEmbedder(Embedder):
    """Embedder that handles long texts by chunking."""
    
    def __init__(
        self,
        embedder: Embedder,
        chunk_size: int = 512,
        overlap: int = 50,
        combine_strategy: str = "average",
    ):
        self._embedder = embedder
        self._chunk_size = chunk_size
        self._overlap = overlap
        self._combine_strategy = combine_strategy
    
    @property
    def model(self) -> str:
        return self._embedder.model
    
    @property
    def dimensions(self) -> int:
        return self._embedder.dimensions
    
    def _chunk_text(self, text: str) -> List[str]:
        """Split text into chunks."""
        words = text.split()
        
        if len(words) <= self._chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(words):
            end = start + self._chunk_size
            chunk = " ".join(words[start:end])
            chunks.append(chunk)
            start = end - self._overlap
        
        return chunks
    
    async def embed(self, text: str) -> Vector:
        """Embed text, chunking if needed."""
        chunks = self._chunk_text(text)
        
        if len(chunks) == 1:
            return await self._embedder.embed(text)
        
        vectors = await self._embedder.embed_batch(chunks)
        
        if self._combine_strategy == "average":
            return average_vectors(vectors)
        elif self._combine_strategy == "first":
            return vectors[0]
        elif self._combine_strategy == "weighted":
            # Weight by position (earlier chunks weighted more)
            weights = [1.0 / (i + 1) for i in range(len(vectors))]
            total_weight = sum(weights)
            weights = [w / total_weight for w in weights]
            
            dim = len(vectors[0])
            result = [0.0] * dim
            
            for v, w in zip(vectors, weights):
                for i, val in enumerate(v):
                    result[i] += val * w
            
            return result
        
        return average_vectors(vectors)
    
    async def embed_batch(self, texts: List[str]) -> List[Vector]:
        """Embed batch with chunking."""
        return [await self.embed(text) for text in texts]


class EmbeddingIndex:
    """
    Simple in-memory embedding index for similarity search.
    """
    
    def __init__(self, embedder: Embedder):
        self._embedder = embedder
        self._items: List[Tuple[str, str, Vector, Dict[str, Any]]] = []  # (id, text, vector, metadata)
    
    async def add(
        self,
        id: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add item to index."""
        vector = await self._embedder.embed(text)
        self._items.append((id, text, vector, metadata or {}))
    
    async def add_with_vector(
        self,
        id: str,
        text: str,
        vector: Vector,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add item with pre-computed vector."""
        self._items.append((id, text, vector, metadata or {}))
    
    async def search(
        self,
        query: str,
        k: int = 5,
        threshold: float = 0.0,
    ) -> List[Tuple[str, str, float, Dict[str, Any]]]:
        """
        Search for similar items.
        
        Returns list of (id, text, score, metadata).
        """
        query_vector = await self._embedder.embed(query)
        return await self.search_by_vector(query_vector, k, threshold)
    
    async def search_by_vector(
        self,
        vector: Vector,
        k: int = 5,
        threshold: float = 0.0,
    ) -> List[Tuple[str, str, float, Dict[str, Any]]]:
        """Search by vector."""
        scores = []
        
        for id, text, item_vector, metadata in self._items:
            score = cosine_similarity(vector, item_vector)
            if score >= threshold:
                scores.append((id, text, score, metadata))
        
        scores.sort(key=lambda x: x[2], reverse=True)
        return scores[:k]
    
    def remove(self, id: str) -> bool:
        """Remove item from index."""
        for i, (item_id, _, _, _) in enumerate(self._items):
            if item_id == id:
                self._items.pop(i)
                return True
        return False
    
    def clear(self) -> None:
        """Clear the index."""
        self._items.clear()
    
    def __len__(self) -> int:
        return len(self._items)


# Decorators
def with_embeddings(
    embedder: Embedder,
    field: str = "text",
    output_field: str = "embedding",
) -> Callable:
    """
    Decorator to add embeddings to function output.
    
    Example:
        @with_embeddings(embedder, field="content")
        async def get_documents():
            return [{"content": "..."}]
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = await func(*args, **kwargs)
            
            if isinstance(result, list):
                texts = [item.get(field, "") for item in result]
                vectors = await embedder.embed_batch(texts)
                
                for item, vector in zip(result, vectors):
                    item[output_field] = vector
            
            elif isinstance(result, dict):
                text = result.get(field, "")
                vector = await embedder.embed(text)
                result[output_field] = vector
            
            return result
        
        return wrapper
    
    return decorator


# Factory functions
def create_embedder(
    provider: str = "openai",
    client: Optional[Any] = None,
    model: Optional[str] = None,
    **kwargs: Any,
) -> Embedder:
    """
    Factory function to create an embedder.
    
    Args:
        provider: Provider name ('openai', 'mock')
        client: API client
        model: Model name
        **kwargs: Additional arguments
    """
    if provider == "openai":
        if client is None:
            raise ValueError("OpenAI client required")
        return OpenAIEmbedder(
            client=client,
            model=model or "text-embedding-3-small",
            **kwargs,
        )
    
    elif provider == "mock":
        return MockEmbedder(**kwargs)
    
    else:
        raise ValueError(f"Unknown provider: {provider}")


__all__ = [
    # Exceptions
    "EmbeddingError",
    "DimensionMismatchError",
    # Enums
    "EmbeddingModel",
    # Data classes
    "EmbeddingResult",
    "BatchEmbeddingResult",
    "SimilarityResult",
    # Vector operations
    "cosine_similarity",
    "euclidean_distance",
    "dot_product",
    "l2_normalize",
    "average_vectors",
    # Embedders
    "Embedder",
    "OpenAIEmbedder",
    "MockEmbedder",
    "CachedEmbedder",
    "ChunkedEmbedder",
    # Index
    "EmbeddingIndex",
    # Decorators
    "with_embeddings",
    # Factory
    "create_embedder",
    # Type alias
    "Vector",
]
