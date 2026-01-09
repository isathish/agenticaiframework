"""
Vector Database Search Tools.
"""

import logging
from typing import Any, Dict, List, Optional

from ..base import BaseTool, ToolConfig

logger = logging.getLogger(__name__)


class QdrantVectorSearchTool(BaseTool):
    """
    Tool for vector search using Qdrant.
    
    Features:
    - Vector similarity search
    - Filtered search
    - Collection management
    """
    
    def __init__(
        self,
        config: Optional[ToolConfig] = None,
        url: str = 'http://localhost:6333',
        api_key: Optional[str] = None,
        collection_name: str = 'default',
    ):
        super().__init__(config or ToolConfig(
            name="QdrantVectorSearchTool",
            description="Vector search using Qdrant"
        ))
        self.url = url
        self.api_key = api_key or self.config.api_key
        self.collection_name = collection_name
        self._client = None
    
    def _get_client(self):
        """Get Qdrant client."""
        if self._client:
            return self._client
        
        try:
            from qdrant_client import QdrantClient
        except ImportError:
            raise ImportError("Qdrant requires: pip install qdrant-client")
        
        self._client = QdrantClient(url=self.url, api_key=self.api_key)
        return self._client
    
    def _execute(
        self,
        query_vector: List[float],
        collection: Optional[str] = None,
        limit: int = 10,
        filters: Optional[Dict] = None,
        with_payload: bool = True,
    ) -> Dict[str, Any]:
        """
        Search vectors in Qdrant.
        
        Args:
            query_vector: Query embedding vector
            collection: Collection name
            limit: Maximum results
            filters: Filter conditions
            with_payload: Include payload in results
            
        Returns:
            Dict with search results
        """
        client = self._get_client()
        collection_name = collection or self.collection_name
        
        search_params = {
            'collection_name': collection_name,
            'query_vector': query_vector,
            'limit': limit,
            'with_payload': with_payload,
        }
        
        if filters:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            
            conditions = []
            for key, value in filters.items():
                conditions.append(
                    FieldCondition(key=key, match=MatchValue(value=value))
                )
            search_params['query_filter'] = Filter(must=conditions)
        
        results = client.search(**search_params)
        
        return {
            'collection': collection_name,
            'results': [
                {
                    'id': hit.id,
                    'score': hit.score,
                    'payload': hit.payload if with_payload else None,
                }
                for hit in results
            ],
            'total': len(results),
        }
    
    def upsert(
        self,
        vectors: List[Dict[str, Any]],
        collection: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Upsert vectors to collection.
        
        Args:
            vectors: List of {'id': str, 'vector': List[float], 'payload': Dict}
            collection: Collection name
            
        Returns:
            Dict with upsert status
        """
        client = self._get_client()
        collection_name = collection or self.collection_name
        
        from qdrant_client.models import PointStruct
        
        points = [
            PointStruct(
                id=v['id'],
                vector=v['vector'],
                payload=v.get('payload', {}),
            )
            for v in vectors
        ]
        
        client.upsert(collection_name=collection_name, points=points)
        
        return {
            'status': 'success',
            'collection': collection_name,
            'points_upserted': len(points),
        }


class WeaviateVectorSearchTool(BaseTool):
    """
    Tool for vector search using Weaviate.
    
    Features:
    - Vector and hybrid search
    - GraphQL queries
    - Schema management
    """
    
    def __init__(
        self,
        config: Optional[ToolConfig] = None,
        url: str = 'http://localhost:8080',
        api_key: Optional[str] = None,
        class_name: str = 'Document',
    ):
        super().__init__(config or ToolConfig(
            name="WeaviateVectorSearchTool",
            description="Vector search using Weaviate"
        ))
        self.url = url
        self.api_key = api_key or self.config.api_key
        self.class_name = class_name
        self._client = None
    
    def _get_client(self):
        """Get Weaviate client."""
        if self._client:
            return self._client
        
        try:
            import weaviate
        except ImportError:
            raise ImportError("Weaviate requires: pip install weaviate-client")
        
        auth_config = None
        if self.api_key:
            auth_config = weaviate.AuthApiKey(api_key=self.api_key)
        
        self._client = weaviate.Client(url=self.url, auth_client_secret=auth_config)
        return self._client
    
    def _execute(
        self,
        query: str = None,
        query_vector: List[float] = None,
        class_name: Optional[str] = None,
        limit: int = 10,
        properties: Optional[List[str]] = None,
        filters: Optional[Dict] = None,
        search_type: str = 'hybrid',
    ) -> Dict[str, Any]:
        """
        Search in Weaviate.
        
        Args:
            query: Text query for hybrid/keyword search
            query_vector: Vector for nearVector search
            class_name: Class to search
            limit: Maximum results
            properties: Properties to return
            filters: Where filters
            search_type: 'hybrid', 'vector', or 'keyword'
            
        Returns:
            Dict with search results
        """
        client = self._get_client()
        class_nm = class_name or self.class_name
        props = properties or ['content', 'title']
        
        query_builder = client.query.get(class_nm, props)
        
        if search_type == 'vector' and query_vector:
            query_builder = query_builder.with_near_vector({'vector': query_vector})
        elif search_type == 'keyword' and query:
            query_builder = query_builder.with_bm25(query=query)
        elif search_type == 'hybrid' and query:
            query_builder = query_builder.with_hybrid(query=query)
        
        if filters:
            where_filter = self._build_where_filter(filters)
            query_builder = query_builder.with_where(where_filter)
        
        query_builder = query_builder.with_limit(limit)
        query_builder = query_builder.with_additional(['score', 'id'])
        
        result = query_builder.do()
        
        objects = result.get('data', {}).get('Get', {}).get(class_nm, [])
        
        return {
            'class': class_nm,
            'search_type': search_type,
            'results': [
                {
                    'properties': {k: v for k, v in obj.items() if k != '_additional'},
                    'id': obj.get('_additional', {}).get('id'),
                    'score': obj.get('_additional', {}).get('score'),
                }
                for obj in objects
            ],
            'total': len(objects),
        }
    
    def _build_where_filter(self, filters: Dict) -> Dict:
        """Build Weaviate where filter."""
        operands = []
        for key, value in filters.items():
            operands.append({
                'path': [key],
                'operator': 'Equal',
                'valueText': str(value) if isinstance(value, str) else None,
                'valueInt': value if isinstance(value, int) else None,
            })
        
        if len(operands) == 1:
            return operands[0]
        return {'operator': 'And', 'operands': operands}


class MongoDBVectorSearchTool(BaseTool):
    """
    Tool for vector search using MongoDB Atlas.
    
    Features:
    - Atlas Vector Search
    - Aggregation pipelines
    - Index management
    """
    
    def __init__(
        self,
        config: Optional[ToolConfig] = None,
        connection_string: Optional[str] = None,
        database: str = 'default',
        collection: str = 'documents',
        vector_field: str = 'embedding',
        index_name: str = 'vector_index',
    ):
        super().__init__(config or ToolConfig(
            name="MongoDBVectorSearchTool",
            description="Vector search using MongoDB Atlas"
        ))
        self.connection_string = connection_string or self.config.base_url
        self.database_name = database
        self.collection_name = collection
        self.vector_field = vector_field
        self.index_name = index_name
        self._client = None
    
    def _get_client(self):
        """Get MongoDB client."""
        if self._client:
            return self._client
        
        try:
            from pymongo import MongoClient
        except ImportError:
            raise ImportError("MongoDB requires: pip install pymongo")
        
        if not self.connection_string:
            raise ValueError("MongoDB connection string required")
        
        self._client = MongoClient(self.connection_string)
        return self._client
    
    def _execute(
        self,
        query_vector: List[float],
        database: Optional[str] = None,
        collection: Optional[str] = None,
        limit: int = 10,
        filters: Optional[Dict] = None,
        num_candidates: int = 100,
    ) -> Dict[str, Any]:
        """
        Vector search in MongoDB Atlas.
        
        Args:
            query_vector: Query embedding
            database: Database name
            collection: Collection name
            limit: Maximum results
            filters: Pre-filter conditions
            num_candidates: Number of candidates to consider
            
        Returns:
            Dict with search results
        """
        client = self._get_client()
        db = client[database or self.database_name]
        coll = db[collection or self.collection_name]
        
        # Build vector search stage
        vector_search_stage = {
            '$vectorSearch': {
                'index': self.index_name,
                'path': self.vector_field,
                'queryVector': query_vector,
                'numCandidates': num_candidates,
                'limit': limit,
            }
        }
        
        if filters:
            vector_search_stage['$vectorSearch']['filter'] = filters
        
        # Build pipeline
        pipeline = [
            vector_search_stage,
            {
                '$project': {
                    '_id': 1,
                    'content': 1,
                    'metadata': 1,
                    'score': {'$meta': 'vectorSearchScore'},
                }
            },
        ]
        
        results = list(coll.aggregate(pipeline))
        
        return {
            'database': database or self.database_name,
            'collection': collection or self.collection_name,
            'results': [
                {
                    'id': str(doc.get('_id')),
                    'content': doc.get('content'),
                    'metadata': doc.get('metadata'),
                    'score': doc.get('score'),
                }
                for doc in results
            ],
            'total': len(results),
        }
    
    def insert_vectors(
        self,
        documents: List[Dict[str, Any]],
        database: Optional[str] = None,
        collection: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Insert documents with vectors.
        
        Args:
            documents: List of documents with 'embedding' field
            database: Database name
            collection: Collection name
            
        Returns:
            Dict with insert status
        """
        client = self._get_client()
        db = client[database or self.database_name]
        coll = db[collection or self.collection_name]
        
        result = coll.insert_many(documents)
        
        return {
            'status': 'success',
            'inserted_count': len(result.inserted_ids),
            'ids': [str(id) for id in result.inserted_ids],
        }
    
    def close(self):
        """Close MongoDB connection."""
        if self._client:
            self._client.close()
            self._client = None


__all__ = [
    'QdrantVectorSearchTool',
    'WeaviateVectorSearchTool',
    'MongoDBVectorSearchTool',
]
