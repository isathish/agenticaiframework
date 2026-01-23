"""
Enterprise Search Engine Module.

Full-text search with indexing, facets, autocomplete,
and advanced query capabilities.

Example:
    # Create search engine
    search = create_search_engine()
    
    # Index documents
    await search.index("products", {"id": "1", "name": "Widget", "price": 29.99})
    
    # Search
    results = await search.search("products", "widget", filters={"price": {"gte": 20}})
    
    # Autocomplete
    suggestions = await search.autocomplete("products", "wid", field="name")
    
    # Faceted search
    results = await search.search(
        "products",
        "electronics",
        facets=["category", "brand"],
    )
"""

from __future__ import annotations

import asyncio
import functools
import logging
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
    List,
    Optional,
    Set,
    Tuple,
    TypeVar,
    Union,
)

T = TypeVar('T')


logger = logging.getLogger(__name__)


class SearchError(Exception):
    """Search error."""
    pass


class IndexError(SearchError):
    """Index error."""
    pass


class QueryError(SearchError):
    """Query error."""
    pass


class SortOrder(str, Enum):
    """Sort order."""
    ASC = "asc"
    DESC = "desc"


class QueryOperator(str, Enum):
    """Query operator."""
    AND = "and"
    OR = "or"
    NOT = "not"


class FilterOperator(str, Enum):
    """Filter operator."""
    EQ = "eq"
    NE = "ne"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    IN = "in"
    NIN = "nin"
    CONTAINS = "contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    RANGE = "range"
    EXISTS = "exists"


@dataclass
class FieldConfig:
    """Field configuration."""
    name: str
    field_type: str = "text"  # text, keyword, numeric, date, boolean, geo
    searchable: bool = True
    filterable: bool = True
    sortable: bool = True
    facetable: bool = False
    weight: float = 1.0
    analyzer: str = "standard"


@dataclass
class IndexConfig:
    """Index configuration."""
    name: str
    fields: List[FieldConfig] = field(default_factory=list)
    id_field: str = "id"
    default_search_fields: List[str] = field(default_factory=list)
    stopwords: List[str] = field(default_factory=list)
    synonyms: Dict[str, List[str]] = field(default_factory=dict)


@dataclass
class SearchQuery:
    """Search query."""
    query: str = ""
    fields: List[str] = field(default_factory=list)
    filters: Dict[str, Any] = field(default_factory=dict)
    sort: List[Tuple[str, SortOrder]] = field(default_factory=list)
    offset: int = 0
    limit: int = 20
    operator: QueryOperator = QueryOperator.AND
    facets: List[str] = field(default_factory=list)
    highlight: bool = False
    highlight_tag: str = "em"
    min_score: float = 0.0


@dataclass
class SearchHit:
    """Search result hit."""
    id: str
    score: float
    document: Dict[str, Any]
    highlights: Dict[str, List[str]] = field(default_factory=dict)


@dataclass
class FacetValue:
    """Facet value."""
    value: Any
    count: int


@dataclass
class Facet:
    """Facet result."""
    field: str
    values: List[FacetValue] = field(default_factory=list)


@dataclass
class SearchResult:
    """Search result."""
    total: int = 0
    hits: List[SearchHit] = field(default_factory=list)
    facets: List[Facet] = field(default_factory=list)
    query_time_ms: float = 0.0
    offset: int = 0
    limit: int = 20


@dataclass
class Suggestion:
    """Autocomplete suggestion."""
    text: str
    score: float = 1.0
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AutocompleteResult:
    """Autocomplete result."""
    suggestions: List[Suggestion] = field(default_factory=list)
    query_time_ms: float = 0.0


# Search backend
class SearchBackend(ABC):
    """Abstract search backend."""
    
    @abstractmethod
    async def create_index(self, config: IndexConfig) -> bool:
        """Create index."""
        pass
    
    @abstractmethod
    async def delete_index(self, name: str) -> bool:
        """Delete index."""
        pass
    
    @abstractmethod
    async def index_exists(self, name: str) -> bool:
        """Check if index exists."""
        pass
    
    @abstractmethod
    async def index_document(
        self,
        index: str,
        document: Dict[str, Any],
        id: Optional[str] = None,
    ) -> str:
        """Index document."""
        pass
    
    @abstractmethod
    async def bulk_index(
        self,
        index: str,
        documents: List[Dict[str, Any]],
    ) -> int:
        """Bulk index documents."""
        pass
    
    @abstractmethod
    async def delete_document(self, index: str, id: str) -> bool:
        """Delete document."""
        pass
    
    @abstractmethod
    async def get_document(
        self,
        index: str,
        id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get document by ID."""
        pass
    
    @abstractmethod
    async def search(
        self,
        index: str,
        query: SearchQuery,
    ) -> SearchResult:
        """Search documents."""
        pass
    
    @abstractmethod
    async def autocomplete(
        self,
        index: str,
        prefix: str,
        field: str,
        limit: int = 10,
    ) -> AutocompleteResult:
        """Autocomplete suggestions."""
        pass


class InMemorySearchBackend(SearchBackend):
    """In-memory search backend."""
    
    def __init__(self):
        self._indexes: Dict[str, IndexConfig] = {}
        self._documents: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)
    
    async def create_index(self, config: IndexConfig) -> bool:
        """Create index."""
        self._indexes[config.name] = config
        self._documents[config.name] = {}
        return True
    
    async def delete_index(self, name: str) -> bool:
        """Delete index."""
        if name in self._indexes:
            del self._indexes[name]
            del self._documents[name]
            return True
        return False
    
    async def index_exists(self, name: str) -> bool:
        """Check if index exists."""
        return name in self._indexes
    
    async def index_document(
        self,
        index: str,
        document: Dict[str, Any],
        id: Optional[str] = None,
    ) -> str:
        """Index document."""
        if index not in self._indexes:
            await self.create_index(IndexConfig(name=index))
        
        config = self._indexes[index]
        doc_id = id or document.get(config.id_field) or str(uuid.uuid4())
        
        self._documents[index][doc_id] = {**document, config.id_field: doc_id}
        return doc_id
    
    async def bulk_index(
        self,
        index: str,
        documents: List[Dict[str, Any]],
    ) -> int:
        """Bulk index documents."""
        count = 0
        for doc in documents:
            await self.index_document(index, doc)
            count += 1
        return count
    
    async def delete_document(self, index: str, id: str) -> bool:
        """Delete document."""
        if index in self._documents and id in self._documents[index]:
            del self._documents[index][id]
            return True
        return False
    
    async def get_document(
        self,
        index: str,
        id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get document by ID."""
        if index in self._documents:
            return self._documents[index].get(id)
        return None
    
    async def search(
        self,
        index: str,
        query: SearchQuery,
    ) -> SearchResult:
        """Search documents."""
        import time
        start = time.time()
        
        if index not in self._documents:
            return SearchResult()
        
        docs = list(self._documents[index].values())
        hits = []
        
        # Text search
        search_terms = query.query.lower().split() if query.query else []
        
        for doc in docs:
            score = 0.0
            
            if search_terms:
                # Calculate score
                for term in search_terms:
                    for field, value in doc.items():
                        if isinstance(value, str) and term in value.lower():
                            score += 1.0
                
                if query.operator == QueryOperator.AND:
                    # All terms must match
                    all_match = all(
                        any(
                            term in str(v).lower()
                            for v in doc.values()
                        )
                        for term in search_terms
                    )
                    if not all_match:
                        continue
                elif score == 0:
                    continue
            else:
                score = 1.0
            
            # Apply filters
            if not self._matches_filters(doc, query.filters):
                continue
            
            # Apply min score
            if score < query.min_score:
                continue
            
            # Create hit
            hit = SearchHit(
                id=doc.get("id", str(uuid.uuid4())),
                score=score,
                document=doc,
            )
            
            # Highlighting
            if query.highlight and search_terms:
                hit.highlights = self._highlight(doc, search_terms, query.highlight_tag)
            
            hits.append(hit)
        
        # Sort
        if query.sort:
            for field, order in reversed(query.sort):
                reverse = order == SortOrder.DESC
                hits.sort(key=lambda h: h.document.get(field, ""), reverse=reverse)
        else:
            hits.sort(key=lambda h: h.score, reverse=True)
        
        total = len(hits)
        
        # Pagination
        hits = hits[query.offset:query.offset + query.limit]
        
        # Facets
        facets = []
        if query.facets:
            for facet_field in query.facets:
                facet = self._calculate_facet(docs, facet_field)
                facets.append(facet)
        
        return SearchResult(
            total=total,
            hits=hits,
            facets=facets,
            query_time_ms=(time.time() - start) * 1000,
            offset=query.offset,
            limit=query.limit,
        )
    
    def _matches_filters(
        self,
        doc: Dict[str, Any],
        filters: Dict[str, Any],
    ) -> bool:
        """Check if document matches filters."""
        for field, condition in filters.items():
            value = doc.get(field)
            
            if isinstance(condition, dict):
                for op, filter_value in condition.items():
                    if op in ("eq", "=", "==") and value != filter_value:
                        return False
                    if op in ("ne", "!=", "<>") and value == filter_value:
                        return False
                    if op in ("gt", ">") and not (value and value > filter_value):
                        return False
                    if op in ("gte", ">=") and not (value and value >= filter_value):
                        return False
                    if op in ("lt", "<") and not (value and value < filter_value):
                        return False
                    if op in ("lte", "<=") and not (value and value <= filter_value):
                        return False
                    if op == "in" and value not in filter_value:
                        return False
                    if op == "nin" and value in filter_value:
                        return False
                    if op == "contains" and filter_value not in str(value):
                        return False
            else:
                # Simple equality
                if value != condition:
                    return False
        
        return True
    
    def _highlight(
        self,
        doc: Dict[str, Any],
        terms: List[str],
        tag: str,
    ) -> Dict[str, List[str]]:
        """Generate highlights."""
        highlights = {}
        
        for field, value in doc.items():
            if isinstance(value, str):
                highlighted = value
                for term in terms:
                    pattern = re.compile(re.escape(term), re.IGNORECASE)
                    if pattern.search(highlighted):
                        highlighted = pattern.sub(
                            f"<{tag}>\\g<0></{tag}>",
                            highlighted,
                        )
                        if field not in highlights:
                            highlights[field] = []
                        highlights[field].append(highlighted)
        
        return highlights
    
    def _calculate_facet(
        self,
        docs: List[Dict[str, Any]],
        field: str,
    ) -> Facet:
        """Calculate facet values."""
        counts: Dict[Any, int] = defaultdict(int)
        
        for doc in docs:
            value = doc.get(field)
            if value is not None:
                if isinstance(value, list):
                    for v in value:
                        counts[v] += 1
                else:
                    counts[value] += 1
        
        values = [
            FacetValue(value=v, count=c)
            for v, c in sorted(counts.items(), key=lambda x: x[1], reverse=True)
        ]
        
        return Facet(field=field, values=values)
    
    async def autocomplete(
        self,
        index: str,
        prefix: str,
        field: str,
        limit: int = 10,
    ) -> AutocompleteResult:
        """Autocomplete suggestions."""
        import time
        start = time.time()
        
        if index not in self._documents:
            return AutocompleteResult()
        
        suggestions = []
        seen: Set[str] = set()
        
        prefix_lower = prefix.lower()
        
        for doc in self._documents[index].values():
            value = doc.get(field)
            if isinstance(value, str):
                if value.lower().startswith(prefix_lower):
                    if value not in seen:
                        seen.add(value)
                        suggestions.append(
                            Suggestion(
                                text=value,
                                score=1.0,
                                payload={"id": doc.get("id")},
                            )
                        )
        
        suggestions = suggestions[:limit]
        
        return AutocompleteResult(
            suggestions=suggestions,
            query_time_ms=(time.time() - start) * 1000,
        )


class SearchEngine:
    """
    Search engine service.
    """
    
    def __init__(
        self,
        backend: Optional[SearchBackend] = None,
    ):
        self._backend = backend or InMemorySearchBackend()
    
    async def create_index(
        self,
        name: str,
        fields: Optional[List[FieldConfig]] = None,
        **kwargs,
    ) -> bool:
        """
        Create search index.
        
        Args:
            name: Index name
            fields: Field configurations
            **kwargs: Additional config
            
        Returns:
            Success status
        """
        config = IndexConfig(
            name=name,
            fields=fields or [],
            **kwargs,
        )
        return await self._backend.create_index(config)
    
    async def delete_index(self, name: str) -> bool:
        """Delete index."""
        return await self._backend.delete_index(name)
    
    async def index_exists(self, name: str) -> bool:
        """Check if index exists."""
        return await self._backend.index_exists(name)
    
    async def index(
        self,
        index: str,
        document: Dict[str, Any],
        id: Optional[str] = None,
    ) -> str:
        """
        Index single document.
        
        Args:
            index: Index name
            document: Document to index
            id: Document ID
            
        Returns:
            Document ID
        """
        return await self._backend.index_document(index, document, id)
    
    async def bulk_index(
        self,
        index: str,
        documents: List[Dict[str, Any]],
    ) -> int:
        """
        Bulk index documents.
        
        Args:
            index: Index name
            documents: Documents to index
            
        Returns:
            Number of indexed documents
        """
        return await self._backend.bulk_index(index, documents)
    
    async def delete(self, index: str, id: str) -> bool:
        """Delete document."""
        return await self._backend.delete_document(index, id)
    
    async def get(self, index: str, id: str) -> Optional[Dict[str, Any]]:
        """Get document by ID."""
        return await self._backend.get_document(index, id)
    
    async def search(
        self,
        index: str,
        query: str = "",
        filters: Optional[Dict[str, Any]] = None,
        sort: Optional[List[Tuple[str, SortOrder]]] = None,
        offset: int = 0,
        limit: int = 20,
        facets: Optional[List[str]] = None,
        highlight: bool = False,
        **kwargs,
    ) -> SearchResult:
        """
        Search documents.
        
        Args:
            index: Index name
            query: Search query
            filters: Filter conditions
            sort: Sort order
            offset: Result offset
            limit: Result limit
            facets: Facet fields
            highlight: Enable highlighting
            
        Returns:
            Search results
        """
        search_query = SearchQuery(
            query=query,
            filters=filters or {},
            sort=sort or [],
            offset=offset,
            limit=limit,
            facets=facets or [],
            highlight=highlight,
            **kwargs,
        )
        
        return await self._backend.search(index, search_query)
    
    async def autocomplete(
        self,
        index: str,
        prefix: str,
        field: str,
        limit: int = 10,
    ) -> AutocompleteResult:
        """
        Autocomplete suggestions.
        
        Args:
            index: Index name
            prefix: Prefix to match
            field: Field to search
            limit: Max suggestions
            
        Returns:
            Autocomplete results
        """
        return await self._backend.autocomplete(index, prefix, field, limit)
    
    async def find_similar(
        self,
        index: str,
        document_id: str,
        limit: int = 10,
    ) -> SearchResult:
        """
        Find similar documents.
        
        Args:
            index: Index name
            document_id: Source document ID
            limit: Max results
            
        Returns:
            Similar documents
        """
        doc = await self.get(index, document_id)
        if not doc:
            return SearchResult()
        
        # Extract text from document
        text_parts = []
        for value in doc.values():
            if isinstance(value, str):
                text_parts.append(value)
        
        query = " ".join(text_parts[:100])  # Limit query length
        
        return await self.search(
            index,
            query,
            limit=limit + 1,  # +1 to exclude self
        )
    
    async def reindex(
        self,
        index: str,
        batch_size: int = 100,
    ) -> int:
        """
        Reindex all documents.
        
        Args:
            index: Index name
            batch_size: Batch size
            
        Returns:
            Number of reindexed documents
        """
        # Get all documents
        result = await self.search(index, limit=10000)
        documents = [hit.document for hit in result.hits]
        
        # Clear and reindex
        await self.delete_index(index)
        await self.create_index(index)
        
        return await self.bulk_index(index, documents)


# Decorator
def searchable(index: str, fields: Optional[List[str]] = None):
    """
    Decorator to make class searchable.
    
    Args:
        index: Index name
        fields: Fields to index
    """
    def decorator(cls):
        original_init = cls.__init__
        
        def new_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            self._search_index = index
            self._search_fields = fields
        
        cls.__init__ = new_init
        cls._is_searchable = True
        
        return cls
    
    return decorator


# Factory functions
def create_search_engine(
    backend: Optional[SearchBackend] = None,
) -> SearchEngine:
    """Create search engine."""
    return SearchEngine(backend)


def create_index_config(
    name: str,
    fields: Optional[List[Dict[str, Any]]] = None,
    **kwargs,
) -> IndexConfig:
    """Create index configuration."""
    field_configs = []
    if fields:
        for f in fields:
            field_configs.append(FieldConfig(**f))
    
    return IndexConfig(name=name, fields=field_configs, **kwargs)


def create_field_config(
    name: str,
    field_type: str = "text",
    **kwargs,
) -> FieldConfig:
    """Create field configuration."""
    return FieldConfig(name=name, field_type=field_type, **kwargs)


def create_search_query(
    query: str = "",
    **kwargs,
) -> SearchQuery:
    """Create search query."""
    return SearchQuery(query=query, **kwargs)


__all__ = [
    # Exceptions
    "SearchError",
    "IndexError",
    "QueryError",
    # Enums
    "SortOrder",
    "QueryOperator",
    "FilterOperator",
    # Data classes
    "FieldConfig",
    "IndexConfig",
    "SearchQuery",
    "SearchHit",
    "FacetValue",
    "Facet",
    "SearchResult",
    "Suggestion",
    "AutocompleteResult",
    # Backend
    "SearchBackend",
    "InMemorySearchBackend",
    # Service
    "SearchEngine",
    # Decorator
    "searchable",
    # Factory functions
    "create_search_engine",
    "create_index_config",
    "create_field_config",
    "create_search_query",
]
