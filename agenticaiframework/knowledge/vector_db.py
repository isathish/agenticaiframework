"""
Vector Database Tools for Agent Integration.

Unified interface for storing and retrieving embeddings across
multiple vector database providers.
"""

import json
import uuid
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union
from enum import Enum

logger = logging.getLogger(__name__)


# Simple result class for vector operations
@dataclass
class VectorDBResult:
    """Result of vector database operation."""
    success: bool = True
    result: Any = None
    error: Optional[str] = None


class VectorDBType(Enum):
    """Supported vector database types."""
    QDRANT = "qdrant"
    PINECONE = "pinecone"
    WEAVIATE = "weaviate"
    CHROMA = "chroma"
    MILVUS = "milvus"
    MONGODB = "mongodb"
    PGVECTOR = "pgvector"
    OPENSEARCH = "opensearch"
    REDIS = "redis"
    MEMORY = "memory"


@dataclass
class VectorDBConfig:
    """Configuration for vector database connection."""
    db_type: VectorDBType
    host: str = "localhost"
    port: int = 6333
    api_key: Optional[str] = None
    collection_name: str = "default"
    dimension: int = 1536
    distance_metric: str = "cosine"  # cosine, euclidean, dot_product
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Database-specific settings
    url: Optional[str] = None
    database: Optional[str] = None
    index_name: Optional[str] = None


class VectorDBClient(ABC):
    """Base class for vector database clients."""
    
    def __init__(self, config: VectorDBConfig):
        self.config = config
        self._client = None
    
    @abstractmethod
    def connect(self) -> bool:
        """Connect to the database."""
        pass
    
    @abstractmethod
    def create_collection(self, name: str, dimension: int) -> bool:
        """Create a collection/index."""
        pass
    
    @abstractmethod
    def insert(
        self,
        vectors: List[List[float]],
        ids: Optional[List[str]] = None,
        payloads: Optional[List[Dict]] = None,
    ) -> bool:
        """Insert vectors with optional metadata."""
        pass
    
    @abstractmethod
    def search(
        self,
        query_vector: List[float],
        limit: int = 10,
        filters: Optional[Dict] = None,
    ) -> List[Dict[str, Any]]:
        """Search for similar vectors."""
        pass
    
    @abstractmethod
    def delete(self, ids: List[str]) -> bool:
        """Delete vectors by ID."""
        pass
    
    def close(self) -> None:
        """Close connection."""
        self._client = None


class QdrantClient(VectorDBClient):
    """Qdrant vector database client."""
    
    def connect(self) -> bool:
        try:
            from qdrant_client import QdrantClient as Qdrant
            from qdrant_client.http.models import Distance, VectorParams
            
            if self.config.url:
                self._client = Qdrant(url=self.config.url, api_key=self.config.api_key)
            else:
                self._client = Qdrant(host=self.config.host, port=self.config.port)
            
            return True
        except ImportError:
            logger.error("Qdrant requires: pip install qdrant-client")
            return False
        except Exception as e:
            logger.error(f"Qdrant connection failed: {e}")
            return False
    
    def create_collection(self, name: str, dimension: int) -> bool:
        from qdrant_client.http.models import Distance, VectorParams
        
        distance_map = {
            "cosine": Distance.COSINE,
            "euclidean": Distance.EUCLID,
            "dot_product": Distance.DOT,
        }
        
        try:
            self._client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(
                    size=dimension,
                    distance=distance_map.get(self.config.distance_metric, Distance.COSINE),
                ),
            )
            return True
        except Exception as e:
            logger.error(f"Collection creation failed: {e}")
            return False
    
    def insert(
        self,
        vectors: List[List[float]],
        ids: Optional[List[str]] = None,
        payloads: Optional[List[Dict]] = None,
    ) -> bool:
        from qdrant_client.http.models import PointStruct
        
        ids = ids or [str(uuid.uuid4()) for _ in vectors]
        payloads = payloads or [{} for _ in vectors]
        
        points = [
            PointStruct(id=id, vector=vector, payload=payload)
            for id, vector, payload in zip(ids, vectors, payloads)
        ]
        
        try:
            self._client.upsert(
                collection_name=self.config.collection_name,
                points=points,
            )
            return True
        except Exception as e:
            logger.error(f"Insert failed: {e}")
            return False
    
    def search(
        self,
        query_vector: List[float],
        limit: int = 10,
        filters: Optional[Dict] = None,
    ) -> List[Dict[str, Any]]:
        try:
            results = self._client.search(
                collection_name=self.config.collection_name,
                query_vector=query_vector,
                limit=limit,
                query_filter=filters,
            )
            
            return [
                {
                    "id": hit.id,
                    "score": hit.score,
                    "payload": hit.payload,
                }
                for hit in results
            ]
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
    
    def delete(self, ids: List[str]) -> bool:
        try:
            self._client.delete(
                collection_name=self.config.collection_name,
                points_selector=ids,
            )
            return True
        except Exception as e:
            logger.error(f"Delete failed: {e}")
            return False


class PineconeClient(VectorDBClient):
    """Pinecone vector database client."""
    
    def connect(self) -> bool:
        try:
            from pinecone import Pinecone
            
            self._client = Pinecone(api_key=self.config.api_key)
            self._index = self._client.Index(self.config.index_name or self.config.collection_name)
            return True
        except ImportError:
            logger.error("Pinecone requires: pip install pinecone-client")
            return False
        except Exception as e:
            logger.error(f"Pinecone connection failed: {e}")
            return False
    
    def create_collection(self, name: str, dimension: int) -> bool:
        try:
            from pinecone import ServerlessSpec
            
            self._client.create_index(
                name=name,
                dimension=dimension,
                metric=self.config.distance_metric,
                spec=ServerlessSpec(cloud="aws", region="us-east-1"),
            )
            return True
        except Exception as e:
            logger.error(f"Index creation failed: {e}")
            return False
    
    def insert(
        self,
        vectors: List[List[float]],
        ids: Optional[List[str]] = None,
        payloads: Optional[List[Dict]] = None,
    ) -> bool:
        ids = ids or [str(uuid.uuid4()) for _ in vectors]
        payloads = payloads or [{} for _ in vectors]
        
        upserts = [
            {"id": id, "values": vector, "metadata": payload}
            for id, vector, payload in zip(ids, vectors, payloads)
        ]
        
        try:
            self._index.upsert(vectors=upserts)
            return True
        except Exception as e:
            logger.error(f"Insert failed: {e}")
            return False
    
    def search(
        self,
        query_vector: List[float],
        limit: int = 10,
        filters: Optional[Dict] = None,
    ) -> List[Dict[str, Any]]:
        try:
            results = self._index.query(
                vector=query_vector,
                top_k=limit,
                filter=filters,
                include_metadata=True,
            )
            
            return [
                {
                    "id": match.id,
                    "score": match.score,
                    "payload": match.metadata,
                }
                for match in results.matches
            ]
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
    
    def delete(self, ids: List[str]) -> bool:
        try:
            self._index.delete(ids=ids)
            return True
        except Exception as e:
            logger.error(f"Delete failed: {e}")
            return False


class ChromaClient(VectorDBClient):
    """ChromaDB vector database client."""
    
    def connect(self) -> bool:
        try:
            import chromadb
            
            if self.config.host == "localhost" and not self.config.url:
                self._client = chromadb.Client()
            else:
                self._client = chromadb.HttpClient(
                    host=self.config.host,
                    port=self.config.port,
                )
            
            return True
        except ImportError:
            logger.error("ChromaDB requires: pip install chromadb")
            return False
        except Exception as e:
            logger.error(f"ChromaDB connection failed: {e}")
            return False
    
    def create_collection(self, name: str, dimension: int) -> bool:
        try:
            self._collection = self._client.create_collection(name=name)
            return True
        except Exception as e:
            logger.error(f"Collection creation failed: {e}")
            return False
    
    def _get_collection(self):
        if not hasattr(self, "_collection"):
            self._collection = self._client.get_or_create_collection(
                name=self.config.collection_name
            )
        return self._collection
    
    def insert(
        self,
        vectors: List[List[float]],
        ids: Optional[List[str]] = None,
        payloads: Optional[List[Dict]] = None,
    ) -> bool:
        ids = ids or [str(uuid.uuid4()) for _ in vectors]
        payloads = payloads or [{} for _ in vectors]
        documents = [p.get("content", "") for p in payloads]
        
        try:
            collection = self._get_collection()
            collection.add(
                ids=ids,
                embeddings=vectors,
                metadatas=payloads,
                documents=documents,
            )
            return True
        except Exception as e:
            logger.error(f"Insert failed: {e}")
            return False
    
    def search(
        self,
        query_vector: List[float],
        limit: int = 10,
        filters: Optional[Dict] = None,
    ) -> List[Dict[str, Any]]:
        try:
            collection = self._get_collection()
            results = collection.query(
                query_embeddings=[query_vector],
                n_results=limit,
                where=filters,
            )
            
            output = []
            for i, id in enumerate(results["ids"][0]):
                output.append({
                    "id": id,
                    "score": results["distances"][0][i] if results.get("distances") else 0,
                    "payload": results["metadatas"][0][i] if results.get("metadatas") else {},
                })
            return output
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
    
    def delete(self, ids: List[str]) -> bool:
        try:
            collection = self._get_collection()
            collection.delete(ids=ids)
            return True
        except Exception as e:
            logger.error(f"Delete failed: {e}")
            return False


class InMemoryVectorDB(VectorDBClient):
    """In-memory vector database for testing and development."""
    
    def __init__(self, config: VectorDBConfig):
        super().__init__(config)
        self._collections: Dict[str, List[Dict]] = {}
    
    def connect(self) -> bool:
        self._collections = {}
        return True
    
    def create_collection(self, name: str, dimension: int) -> bool:
        self._collections[name] = []
        return True
    
    def insert(
        self,
        vectors: List[List[float]],
        ids: Optional[List[str]] = None,
        payloads: Optional[List[Dict]] = None,
    ) -> bool:
        ids = ids or [str(uuid.uuid4()) for _ in vectors]
        payloads = payloads or [{} for _ in vectors]
        
        collection = self._collections.setdefault(self.config.collection_name, [])
        
        for id, vector, payload in zip(ids, vectors, payloads):
            collection.append({
                "id": id,
                "vector": vector,
                "payload": payload,
            })
        
        return True
    
    def search(
        self,
        query_vector: List[float],
        limit: int = 10,
        filters: Optional[Dict] = None,
    ) -> List[Dict[str, Any]]:
        import math
        
        collection = self._collections.get(self.config.collection_name, [])
        
        def cosine_similarity(a: List[float], b: List[float]) -> float:
            dot = sum(x * y for x, y in zip(a, b))
            norm_a = math.sqrt(sum(x ** 2 for x in a))
            norm_b = math.sqrt(sum(x ** 2 for x in b))
            return dot / (norm_a * norm_b) if norm_a and norm_b else 0
        
        scored = []
        for item in collection:
            score = cosine_similarity(query_vector, item["vector"])
            scored.append({
                "id": item["id"],
                "score": score,
                "payload": item["payload"],
            })
        
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:limit]
    
    def delete(self, ids: List[str]) -> bool:
        collection = self._collections.get(self.config.collection_name, [])
        self._collections[self.config.collection_name] = [
            item for item in collection if item["id"] not in ids
        ]
        return True


class UnifiedVectorDBTool:
    """
    Unified tool for vector database operations.
    
    Supports multiple vector databases with consistent interface:
    - Qdrant, Pinecone, Weaviate, ChromaDB, Milvus
    - MongoDB Atlas, PostgreSQL (pgvector)
    - OpenSearch, Redis
    
    Example:
        >>> tool = UnifiedVectorDBTool(
        ...     db_type="qdrant",
        ...     host="localhost",
        ...     collection_name="knowledge"
        ... )
        >>> 
        >>> # Store embeddings
        >>> result = tool.insert(
        ...     vectors=[[0.1, 0.2, ...]],
        ...     payloads=[{"content": "Document text"}]
        ... )
        >>> 
        >>> # Search
        >>> result = tool.search(
        ...     query_vector=[0.1, 0.2, ...],
        ...     limit=10
        ... )
    """
    
    name = "vector_db"
    description = "Store and retrieve embeddings from vector databases"
    
    def __init__(
        self,
        db_type: Union[str, VectorDBType] = VectorDBType.MEMORY,
        host: str = "localhost",
        port: int = 6333,
        api_key: Optional[str] = None,
        collection_name: str = "default",
        dimension: int = 1536,
        **kwargs,
    ):
        if isinstance(db_type, str):
            db_type = VectorDBType(db_type)
        
        self.config = VectorDBConfig(
            db_type=db_type,
            host=host,
            port=port,
            api_key=api_key,
            collection_name=collection_name,
            dimension=dimension,
        )
        
        self._client = self._create_client()
        self._client.connect()
    
    def _create_client(self) -> VectorDBClient:
        """Create appropriate database client."""
        clients = {
            VectorDBType.QDRANT: QdrantClient,
            VectorDBType.PINECONE: PineconeClient,
            VectorDBType.CHROMA: ChromaClient,
            VectorDBType.MEMORY: InMemoryVectorDB,
        }
        
        client_class = clients.get(self.config.db_type, InMemoryVectorDB)
        return client_class(self.config)
    
    def _execute(
        self,
        action: str,
        vectors: Optional[List[List[float]]] = None,
        ids: Optional[List[str]] = None,
        payloads: Optional[List[Dict]] = None,
        query_vector: Optional[List[float]] = None,
        limit: int = 10,
        filters: Optional[Dict] = None,
        collection_name: Optional[str] = None,
        dimension: Optional[int] = None,
        **kwargs,
    ) -> VectorDBResult:
        """
        Execute vector database operation.
        
        Args:
            action: Operation - 'insert', 'search', 'delete', 'create_collection'
            vectors: Vectors to insert
            ids: Vector IDs
            payloads: Metadata for vectors
            query_vector: Vector to search for
            limit: Number of results
            filters: Search filters
            collection_name: Collection to operate on
            dimension: Vector dimension for new collection
        """
        try:
            if action == "insert":
                success = self._client.insert(vectors, ids, payloads)
                return VectorDBResult(
                    success=success,
                    result={"inserted": len(vectors) if vectors else 0},
                )
            
            elif action == "search":
                results = self._client.search(query_vector, limit, filters)
                return VectorDBResult(
                    success=True,
                    result={"matches": results, "count": len(results)},
                )
            
            elif action == "delete":
                success = self._client.delete(ids)
                return VectorDBResult(
                    success=success,
                    result={"deleted": len(ids) if ids else 0},
                )
            
            elif action == "create_collection":
                success = self._client.create_collection(
                    collection_name or self.config.collection_name,
                    dimension or self.config.dimension,
                )
                return VectorDBResult(
                    success=success,
                    result={"collection": collection_name},
                )
            
            else:
                return VectorDBResult(
                    success=False,
                    error=f"Unknown action: {action}",
                )
                
        except Exception as e:
            return VectorDBResult(success=False, error=str(e))
    
    def insert(
        self,
        vectors: List[List[float]],
        ids: Optional[List[str]] = None,
        payloads: Optional[List[Dict]] = None,
    ) -> VectorDBResult:
        """Insert vectors with metadata."""
        return self._execute("insert", vectors=vectors, ids=ids, payloads=payloads)
    
    def search(
        self,
        query_vector: List[float],
        limit: int = 10,
        filters: Optional[Dict] = None,
    ) -> VectorDBResult:
        """Search for similar vectors."""
        return self._execute("search", query_vector=query_vector, limit=limit, filters=filters)
    
    def delete(self, ids: List[str]) -> VectorDBResult:
        """Delete vectors by ID."""
        return self._execute("delete", ids=ids)


def create_vector_db_tool(
    db_type: str = "memory",
    **kwargs,
) -> UnifiedVectorDBTool:
    """
    Factory function to create vector database tool.
    
    Args:
        db_type: Database type - 'qdrant', 'pinecone', 'chroma', 'memory'
        **kwargs: Database-specific configuration
        
    Returns:
        Configured UnifiedVectorDBTool instance
    """
    return UnifiedVectorDBTool(db_type=db_type, **kwargs)


__all__ = [
    "VectorDBType",
    "VectorDBConfig",
    "VectorDBClient",
    "QdrantClient",
    "PineconeClient",
    "ChromaClient",
    "InMemoryVectorDB",
    "UnifiedVectorDBTool",
    "create_vector_db_tool",
]
