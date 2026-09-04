"""
Enterprise Vector Database Module.

Vector storage and similarity search for embeddings,
semantic search, and AI/ML applications.

Example:
    # Create vector database
    vecdb = create_vector_database(dimensions=1536)
    
    # Create collection
    collection = await vecdb.create_collection(
        name="documents",
        dimensions=1536,
        metric="cosine",
    )
    
    # Insert vectors
    await vecdb.insert(
        collection="documents",
        id="doc1",
        vector=embedding,
        metadata={"title": "Hello World"},
    )
    
    # Search
    results = await vecdb.search(
        collection="documents",
        vector=query_embedding,
        top_k=10,
    )
"""

from __future__ import annotations

import asyncio
import functools
import hashlib
import logging
import math
import os
import re
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    Iterator,
    List,
    Optional,
    Set,
    Tuple,
    TypeVar,
    Union,
)

from .._internal import array as _aaf_array
from .._internal import http as _http


T = TypeVar('T')

# NDArray alias removed: we use plain list[float] for vectors. The name is
# preserved for type-hint compatibility with existing call sites.
NDArray = List[float]  # type: ignore[misc]


logger = logging.getLogger(__name__)


class VectorError(Exception):
    """Vector database error."""
    pass


class CollectionNotFoundError(VectorError):
    """Collection not found."""
    pass


class VectorNotFoundError(VectorError):
    """Vector not found."""
    pass


class DimensionMismatchError(VectorError):
    """Dimension mismatch."""
    pass


class DistanceMetric(str, Enum):
    """Distance metrics."""
    COSINE = "cosine"
    EUCLIDEAN = "euclidean"
    DOT_PRODUCT = "dot_product"
    MANHATTAN = "manhattan"


class IndexType(str, Enum):
    """Index types."""
    FLAT = "flat"
    IVF = "ivf"
    HNSW = "hnsw"


Vector = Union[List[float], NDArray]


@dataclass
class VectorRecord:
    """Vector record."""
    id: str
    vector: NDArray
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SearchResult:
    """Search result."""
    id: str
    score: float
    vector: Optional[NDArray] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchResults:
    """Search results container."""
    results: List[SearchResult] = field(default_factory=list)
    total: int = 0
    query_time_ms: float = 0.0
    
    def __iter__(self) -> Iterator[SearchResult]:
        return iter(self.results)
    
    def __len__(self) -> int:
        return len(self.results)


@dataclass
class CollectionConfig:
    """Collection configuration."""
    name: str
    dimensions: int
    metric: DistanceMetric = DistanceMetric.COSINE
    index_type: IndexType = IndexType.FLAT
    hnsw_m: int = 16
    hnsw_ef_construction: int = 200
    hnsw_ef_search: int = 50


@dataclass
class CollectionStats:
    """Collection statistics."""
    name: str
    dimensions: int
    vector_count: int = 0
    storage_bytes: int = 0
    index_type: IndexType = IndexType.FLAT


@dataclass
class DatabaseStats:
    """Database statistics."""
    total_collections: int = 0
    total_vectors: int = 0
    total_storage_bytes: int = 0
    collections: Dict[str, CollectionStats] = field(default_factory=dict)


# Vector index interface
class VectorIndex(ABC):
    """Abstract vector index."""
    
    @abstractmethod
    async def add(
        self,
        id: str,
        vector: NDArray,
        metadata: Dict[str, Any],
    ) -> None:
        """Add vector."""
        pass
    
    @abstractmethod
    async def search(
        self,
        vector: NDArray,
        top_k: int,
        filter_func: Optional[Callable[[Dict[str, Any]], bool]],
    ) -> List[SearchResult]:
        """Search for similar vectors."""
        pass
    
    @abstractmethod
    async def delete(self, id: str) -> bool:
        """Delete vector."""
        pass
    
    @abstractmethod
    async def get(self, id: str) -> Optional[VectorRecord]:
        """Get vector by ID."""
        pass
    
    @abstractmethod
    def count(self) -> int:
        """Get vector count."""
        pass


class FlatIndex(VectorIndex):
    """Flat (brute force) index."""
    
    def __init__(
        self,
        dimensions: int,
        metric: DistanceMetric = DistanceMetric.COSINE,
    ):
        self._dimensions = dimensions
        self._metric = metric
        self._vectors: Dict[str, VectorRecord] = {}
    
    async def add(
        self,
        id: str,
        vector: NDArray,
        metadata: Dict[str, Any],
    ) -> None:
        self._vectors[id] = VectorRecord(
            id=id,
            vector=vector,
            metadata=metadata,
        )
    
    async def search(
        self,
        vector: NDArray,
        top_k: int,
        filter_func: Optional[Callable[[Dict[str, Any]], bool]] = None,
    ) -> List[SearchResult]:
        scores: List[Tuple[str, float]] = []
        
        for vid, record in self._vectors.items():
            if filter_func and not filter_func(record.metadata):
                continue
            
            score = self._compute_similarity(vector, record.vector)
            scores.append((vid, score))
        
        # Sort by score (higher is better for similarity)
        scores.sort(key=lambda x: x[1], reverse=True)
        
        results = []
        for vid, score in scores[:top_k]:
            record = self._vectors[vid]
            results.append(SearchResult(
                id=vid,
                score=score,
                vector=record.vector,
                metadata=record.metadata,
            ))
        
        return results
    
    def _compute_similarity(
        self,
        a: NDArray,
        b: NDArray,
    ) -> float:
        """Compute similarity between vectors."""
        if self._metric == DistanceMetric.COSINE:
            return float(_aaf_array.cosine(a, b))

        if self._metric == DistanceMetric.DOT_PRODUCT:
            return float(_aaf_array.dot(a, b))

        if self._metric == DistanceMetric.EUCLIDEAN:
            distance = float(_aaf_array.euclidean(a, b))
            return 1.0 / (1.0 + distance)

        if self._metric == DistanceMetric.MANHATTAN:
            distance = float(sum(abs(float(x) - float(y)) for x, y in zip(a, b)))
            return 1.0 / (1.0 + distance)

        return 0.0
    
    async def delete(self, id: str) -> bool:
        if id in self._vectors:
            del self._vectors[id]
            return True
        return False
    
    async def get(self, id: str) -> Optional[VectorRecord]:
        return self._vectors.get(id)
    
    def count(self) -> int:
        return len(self._vectors)


class HNSWIndex(VectorIndex):
    """
    Hierarchical Navigable Small World index.
    Simplified implementation for demonstration.
    """
    
    def __init__(
        self,
        dimensions: int,
        metric: DistanceMetric = DistanceMetric.COSINE,
        m: int = 16,
        ef_construction: int = 200,
        ef_search: int = 50,
    ):
        self._dimensions = dimensions
        self._metric = metric
        self._m = m
        self._ef_construction = ef_construction
        self._ef_search = ef_search
        
        # Use flat index internally for simplicity
        self._flat = FlatIndex(dimensions, metric)
    
    async def add(
        self,
        id: str,
        vector: NDArray,
        metadata: Dict[str, Any],
    ) -> None:
        await self._flat.add(id, vector, metadata)
    
    async def search(
        self,
        vector: NDArray,
        top_k: int,
        filter_func: Optional[Callable[[Dict[str, Any]], bool]] = None,
    ) -> List[SearchResult]:
        return await self._flat.search(vector, top_k, filter_func)
    
    async def delete(self, id: str) -> bool:
        return await self._flat.delete(id)
    
    async def get(self, id: str) -> Optional[VectorRecord]:
        return await self._flat.get(id)
    
    def count(self) -> int:
        return self._flat.count()


# Vector collection
class VectorCollection:
    """
    Vector collection.
    """
    
    def __init__(
        self,
        config: CollectionConfig,
    ):
        self.config = config
        
        if config.index_type == IndexType.HNSW:
            self._index: VectorIndex = HNSWIndex(
                dimensions=config.dimensions,
                metric=config.metric,
                m=config.hnsw_m,
                ef_construction=config.hnsw_ef_construction,
                ef_search=config.hnsw_ef_search,
            )
        else:
            self._index = FlatIndex(
                dimensions=config.dimensions,
                metric=config.metric,
            )
    
    async def insert(
        self,
        id: str,
        vector: Vector,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Insert vector."""
        vec = self._normalize_vector(vector)
        
        if len(vec) != self.config.dimensions:
            raise DimensionMismatchError(
                f"Expected {self.config.dimensions} dimensions, got {len(vec)}"
            )
        
        await self._index.add(id, vec, metadata or {})
    
    async def insert_batch(
        self,
        vectors: List[Tuple[str, Vector, Optional[Dict[str, Any]]]],
    ) -> int:
        """Insert batch of vectors."""
        count = 0
        
        for id, vector, metadata in vectors:
            await self.insert(id, vector, metadata)
            count += 1
        
        return count
    
    async def search(
        self,
        vector: Vector,
        top_k: int = 10,
        filter: Optional[Dict[str, Any]] = None,
        include_vectors: bool = False,
    ) -> SearchResults:
        """Search for similar vectors."""
        import time
        start = time.perf_counter()
        
        vec = self._normalize_vector(vector)
        
        if len(vec) != self.config.dimensions:
            raise DimensionMismatchError(
                f"Expected {self.config.dimensions} dimensions, got {len(vec)}"
            )
        
        filter_func = None
        if filter:
            filter_func = lambda m: all(
                m.get(k) == v for k, v in filter.items()
            )
        
        results = await self._index.search(vec, top_k, filter_func)
        
        if not include_vectors:
            for r in results:
                r.vector = None
        
        return SearchResults(
            results=results,
            total=len(results),
            query_time_ms=(time.perf_counter() - start) * 1000,
        )
    
    async def get(self, id: str) -> Optional[VectorRecord]:
        """Get vector by ID."""
        return await self._index.get(id)
    
    async def delete(self, id: str) -> bool:
        """Delete vector."""
        return await self._index.delete(id)
    
    async def update_metadata(
        self,
        id: str,
        metadata: Dict[str, Any],
    ) -> bool:
        """Update vector metadata."""
        record = await self._index.get(id)
        
        if not record:
            return False
        
        record.metadata.update(metadata)
        return True
    
    def count(self) -> int:
        """Get vector count."""
        return self._index.count()
    
    def _normalize_vector(self, vector: Vector) -> NDArray:
        """Normalize vector to a plain ``list[float]``.

        The framework no longer requires numpy. If a numpy array is supplied
        (legacy callers) it is converted to a list lazily without importing
        numpy at module load time.
        """
        if hasattr(vector, "tolist") and callable(vector.tolist):
            return [float(x) for x in vector.tolist()]
        return [float(x) for x in vector]
    
    def get_stats(self) -> CollectionStats:
        """Get collection statistics."""
        return CollectionStats(
            name=self.config.name,
            dimensions=self.config.dimensions,
            vector_count=self.count(),
            storage_bytes=self.count() * self.config.dimensions * 4,
            index_type=self.config.index_type,
        )


# Vector database
class VectorDatabase:
    """
    Vector database service.
    """
    
    def __init__(self):
        self._collections: Dict[str, VectorCollection] = {}
    
    async def create_collection(
        self,
        name: str,
        dimensions: int,
        metric: DistanceMetric = DistanceMetric.COSINE,
        index_type: IndexType = IndexType.FLAT,
        **kwargs,
    ) -> VectorCollection:
        """
        Create a collection.
        
        Args:
            name: Collection name
            dimensions: Vector dimensions
            metric: Distance metric
            index_type: Index type
            **kwargs: Additional index config
            
        Returns:
            Collection
        """
        config = CollectionConfig(
            name=name,
            dimensions=dimensions,
            metric=metric,
            index_type=index_type,
            hnsw_m=kwargs.get("hnsw_m", 16),
            hnsw_ef_construction=kwargs.get("hnsw_ef_construction", 200),
            hnsw_ef_search=kwargs.get("hnsw_ef_search", 50),
        )
        
        collection = VectorCollection(config)
        self._collections[name] = collection
        
        return collection
    
    async def get_collection(
        self,
        name: str,
    ) -> Optional[VectorCollection]:
        """Get collection by name."""
        return self._collections.get(name)
    
    async def delete_collection(self, name: str) -> bool:
        """Delete collection."""
        if name in self._collections:
            del self._collections[name]
            return True
        return False
    
    async def list_collections(self) -> List[str]:
        """List all collections."""
        return list(self._collections.keys())
    
    async def insert(
        self,
        collection: str,
        id: str,
        vector: Vector,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Insert vector into collection.
        
        Args:
            collection: Collection name
            id: Vector ID
            vector: Vector data
            metadata: Optional metadata
        """
        coll = self._collections.get(collection)
        
        if not coll:
            raise CollectionNotFoundError(f"Collection {collection} not found")
        
        await coll.insert(id, vector, metadata)
    
    async def insert_batch(
        self,
        collection: str,
        vectors: List[Tuple[str, Vector, Optional[Dict[str, Any]]]],
    ) -> int:
        """Insert batch of vectors."""
        coll = self._collections.get(collection)
        
        if not coll:
            raise CollectionNotFoundError(f"Collection {collection} not found")
        
        return await coll.insert_batch(vectors)
    
    async def search(
        self,
        collection: str,
        vector: Vector,
        top_k: int = 10,
        filter: Optional[Dict[str, Any]] = None,
        include_vectors: bool = False,
    ) -> SearchResults:
        """
        Search for similar vectors.
        
        Args:
            collection: Collection name
            vector: Query vector
            top_k: Number of results
            filter: Metadata filter
            include_vectors: Include vectors in results
            
        Returns:
            Search results
        """
        coll = self._collections.get(collection)
        
        if not coll:
            raise CollectionNotFoundError(f"Collection {collection} not found")
        
        return await coll.search(vector, top_k, filter, include_vectors)
    
    async def get(
        self,
        collection: str,
        id: str,
    ) -> Optional[VectorRecord]:
        """Get vector by ID."""
        coll = self._collections.get(collection)
        
        if not coll:
            raise CollectionNotFoundError(f"Collection {collection} not found")
        
        return await coll.get(id)
    
    async def delete(
        self,
        collection: str,
        id: str,
    ) -> bool:
        """Delete vector."""
        coll = self._collections.get(collection)
        
        if not coll:
            raise CollectionNotFoundError(f"Collection {collection} not found")
        
        return await coll.delete(id)
    
    async def get_stats(self) -> DatabaseStats:
        """Get database statistics."""
        stats = DatabaseStats(total_collections=len(self._collections))
        
        for name, coll in self._collections.items():
            coll_stats = coll.get_stats()
            stats.collections[name] = coll_stats
            stats.total_vectors += coll_stats.vector_count
            stats.total_storage_bytes += coll_stats.storage_bytes
        
        return stats


# Embedding utilities
_TOKEN_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)


class EmbeddingService:
    """
    Embedding generation service.

    Resolution order for each call:

    1. ``provider`` - any object exposing ``async embed(text)`` (and optionally
       ``async embed_batch(texts)``), e.g. an :class:`Embedder` from
       ``enterprise.embeddings``.
    2. OpenAI-compatible ``/v1/embeddings`` API when ``api_key`` (or the
       ``OPENAI_API_KEY`` environment variable) is set.
    3. Local feature-hashing embedding: tokens are hashed into ``dimensions``
       signed buckets and the vector is L2-normalized. Deterministic, offline,
       and dimension-agnostic; suitable for lexical similarity, not semantics.
    """
    
    def __init__(
        self,
        model: str = "text-embedding-ada-002",
        dimensions: int = 1536,
        provider: Optional[Any] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 60.0,
        api_key_env: str = "OPENAI_API_KEY",
    ):
        self._model = model
        self._dimensions = dimensions
        self._provider = provider
        self._api_key = api_key or os.environ.get(api_key_env) or None
        self._base_url = (base_url or os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com").rstrip("/")
        self._timeout = timeout
        self._http: Optional[_http.AsyncClient] = None

    @property
    def model(self) -> str:
        return self._model

    @property
    def dimensions(self) -> int:
        return self._dimensions

    @property
    def backend(self) -> str:
        """Which backend ``embed`` will use: ``provider``, ``api`` or ``local``."""
        if self._provider is not None:
            return "provider"
        if self._api_key:
            return "api"
        return "local"

    # -- API backend --------------------------------------------------------

    def _client(self) -> _http.AsyncClient:
        if self._http is None:
            self._http = _http.AsyncClient(
                base_url=self._base_url,
                headers={"authorization": f"Bearer {self._api_key}"},
                timeout=self._timeout,
            )
        return self._http

    async def _embed_api(self, texts: List[str]) -> List[NDArray]:
        payload: Dict[str, Any] = {"model": self._model, "input": texts, "encoding_format": "float"}
        # Only the text-embedding-3 family accepts a dimensions override.
        if "embedding-3" in self._model:
            payload["dimensions"] = self._dimensions
        resp = await self._client().post("/v1/embeddings", json=payload)
        if not resp.ok:
            raise VectorError(f"Embedding API error HTTP {resp.status}: {resp.text[:200]}")
        body = resp.json()
        data = body.get("data") if isinstance(body, dict) else None
        if not isinstance(data, list) or len(data) != len(texts):
            raise VectorError("Embedding API returned malformed response")
        ordered = sorted(data, key=lambda item: item.get("index", 0))
        vectors = [[float(x) for x in item["embedding"]] for item in ordered]
        for vec in vectors:
            if len(vec) != self._dimensions:
                raise DimensionMismatchError(
                    f"Model {self._model} returned {len(vec)} dimensions, expected {self._dimensions}"
                )
        return vectors

    # -- Local backend -------------------------------------------------------

    def _embed_local(self, text: str) -> NDArray:
        dims = self._dimensions
        vec = [0.0] * dims
        for token in _TOKEN_RE.findall(text.lower()):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            value = int.from_bytes(digest, "big")
            bucket = (value >> 1) % dims
            vec[bucket] += 1.0 if value & 1 else -1.0
        norm = math.sqrt(sum(x * x for x in vec))
        if norm:
            vec = [x / norm for x in vec]
        return vec

    # -- Public API ---------------------------------------------------------

    async def embed(self, text: str) -> NDArray:
        """Generate embedding for text."""
        if self._provider is not None:
            return [float(x) for x in await self._provider.embed(text)]
        if self._api_key:
            return (await self._embed_api([text]))[0]
        return self._embed_local(text)
    
    async def embed_batch(self, texts: List[str]) -> List[NDArray]:
        """Generate embeddings for batch of texts."""
        if not texts:
            return []
        if self._provider is not None:
            batch = getattr(self._provider, "embed_batch", None)
            if callable(batch):
                return [[float(x) for x in v] for v in await batch(list(texts))]
            return [await self.embed(text) for text in texts]
        if self._api_key:
            return await self._embed_api(list(texts))
        return [self._embed_local(text) for text in texts]


# Decorators
def vectorize(
    collection: str,
    vecdb: VectorDatabase,
    embedder: Optional[EmbeddingService] = None,
    id_field: str = "id",
    text_field: str = "text",
):
    """
    Decorator to auto-vectorize function results.
    
    Args:
        collection: Collection name
        vecdb: Vector database
        embedder: Embedding service
        id_field: ID field name
        text_field: Text field name
    """
    embed_service = embedder or EmbeddingService()
    
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            
            if isinstance(result, dict):
                id_val = result.get(id_field, str(uuid.uuid4()))
                text = result.get(text_field, "")
                
                if text:
                    vector = await embed_service.embed(text)
                    await vecdb.insert(
                        collection,
                        str(id_val),
                        vector,
                        result,
                    )
            
            return result
        
        return wrapper
    
    return decorator


# Factory functions
def create_vector_database() -> VectorDatabase:
    """Create vector database."""
    return VectorDatabase()


def create_collection_config(
    name: str,
    dimensions: int,
    metric: DistanceMetric = DistanceMetric.COSINE,
    index_type: IndexType = IndexType.FLAT,
    **kwargs,
) -> CollectionConfig:
    """Create collection config."""
    return CollectionConfig(
        name=name,
        dimensions=dimensions,
        metric=metric,
        index_type=index_type,
        **kwargs,
    )


def create_embedding_service(
    model: str = "text-embedding-ada-002",
    dimensions: int = 1536,
    provider: Optional[Any] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
) -> EmbeddingService:
    """Create embedding service."""
    return EmbeddingService(
        model=model,
        dimensions=dimensions,
        provider=provider,
        api_key=api_key,
        base_url=base_url,
    )


__all__ = [
    # Exceptions
    "VectorError",
    "CollectionNotFoundError",
    "VectorNotFoundError",
    "DimensionMismatchError",
    # Enums
    "DistanceMetric",
    "IndexType",
    # Types
    "Vector",
    # Data classes
    "VectorRecord",
    "SearchResult",
    "SearchResults",
    "CollectionConfig",
    "CollectionStats",
    "DatabaseStats",
    # Index
    "VectorIndex",
    "FlatIndex",
    "HNSWIndex",
    # Collection
    "VectorCollection",
    # Database
    "VectorDatabase",
    # Services
    "EmbeddingService",
    # Decorators
    "vectorize",
    # Factory functions
    "create_vector_database",
    "create_collection_config",
    "create_embedding_service",
]
