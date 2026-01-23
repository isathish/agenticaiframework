"""
Enterprise Search Module.

Provides full-text search, indexing, query parsing,
faceting, and search result ranking.

Example:
    # Create search engine
    engine = create_search_engine()
    
    # Index documents
    await engine.index("doc1", {"title": "Hello World", "body": "..."})
    await engine.index("doc2", {"title": "Python Guide", "body": "..."})
    
    # Search
    results = await engine.search("hello python", limit=10)
    
    # With filters and facets
    results = await engine.search(
        "python",
        filters={"category": "tutorial"},
        facets=["category", "author"]
    )
"""

from __future__ import annotations

import asyncio
import logging
import math
import re
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from functools import wraps
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    Tuple,
    TypeVar,
    Union,
)

logger = logging.getLogger(__name__)

T = TypeVar('T')


class SearchError(Exception):
    """Search error."""
    pass


class IndexError(SearchError):
    """Index error."""
    pass


class QueryError(SearchError):
    """Query parsing error."""
    pass


class MatchType(str, Enum):
    """Match types."""
    EXACT = "exact"
    PREFIX = "prefix"
    FUZZY = "fuzzy"
    WILDCARD = "wildcard"
    PHRASE = "phrase"


class SortOrder(str, Enum):
    """Sort order."""
    ASC = "asc"
    DESC = "desc"
    RELEVANCE = "relevance"


class QueryOperator(str, Enum):
    """Query operators."""
    AND = "AND"
    OR = "OR"
    NOT = "NOT"


@dataclass
class SearchHit:
    """Search result hit."""
    id: str
    score: float
    document: Dict[str, Any]
    highlights: Dict[str, List[str]] = field(default_factory=dict)
    matched_terms: List[str] = field(default_factory=list)


@dataclass
class FacetValue:
    """Facet value with count."""
    value: Any
    count: int


@dataclass
class Facet:
    """Facet results."""
    field: str
    values: List[FacetValue] = field(default_factory=list)


@dataclass
class SearchResult:
    """Search result."""
    hits: List[SearchHit]
    total: int
    took_ms: float
    facets: Dict[str, Facet] = field(default_factory=dict)
    query: str = ""
    page: int = 1
    page_size: int = 10
    
    @property
    def has_more(self) -> bool:
        """Check if there are more results."""
        return self.page * self.page_size < self.total


@dataclass
class IndexStats:
    """Index statistics."""
    document_count: int = 0
    term_count: int = 0
    field_count: int = 0
    index_size_bytes: int = 0


class Tokenizer(ABC):
    """Abstract tokenizer."""
    
    @abstractmethod
    def tokenize(self, text: str) -> List[str]:
        """Tokenize text."""
        pass


class SimpleTokenizer(Tokenizer):
    """Simple whitespace tokenizer."""
    
    def __init__(self, lowercase: bool = True, min_length: int = 2):
        self._lowercase = lowercase
        self._min_length = min_length
    
    def tokenize(self, text: str) -> List[str]:
        """Tokenize on whitespace and punctuation."""
        if self._lowercase:
            text = text.lower()
        
        # Split on non-alphanumeric characters
        tokens = re.split(r'[^\w\d]+', text)
        
        # Filter by minimum length
        return [t for t in tokens if len(t) >= self._min_length]


class Analyzer(ABC):
    """Abstract text analyzer."""
    
    @abstractmethod
    def analyze(self, text: str) -> List[str]:
        """Analyze text into terms."""
        pass


class StandardAnalyzer(Analyzer):
    """Standard text analyzer."""
    
    STOP_WORDS = {
        'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for',
        'from', 'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on',
        'that', 'the', 'to', 'was', 'were', 'will', 'with',
    }
    
    def __init__(
        self,
        tokenizer: Optional[Tokenizer] = None,
        stop_words: Optional[Set[str]] = None,
        stemming: bool = False,
    ):
        self._tokenizer = tokenizer or SimpleTokenizer()
        self._stop_words = stop_words if stop_words is not None else self.STOP_WORDS
        self._stemming = stemming
    
    def analyze(self, text: str) -> List[str]:
        """Analyze text."""
        tokens = self._tokenizer.tokenize(text)
        
        # Remove stop words
        tokens = [t for t in tokens if t not in self._stop_words]
        
        # Simple stemming (Porter-like suffix removal)
        if self._stemming:
            tokens = [self._stem(t) for t in tokens]
        
        return tokens
    
    def _stem(self, word: str) -> str:
        """Simple stemming."""
        if len(word) <= 3:
            return word
        
        suffixes = ['ing', 'ed', 'es', 's', 'ly', 'ness']
        
        for suffix in suffixes:
            if word.endswith(suffix) and len(word) - len(suffix) >= 3:
                return word[:-len(suffix)]
        
        return word


class QueryParser:
    """Parse search queries."""
    
    def __init__(self, default_operator: QueryOperator = QueryOperator.OR):
        self._default_operator = default_operator
    
    def parse(self, query: str) -> 'ParsedQuery':
        """Parse a search query."""
        must = []
        should = []
        must_not = []
        
        # Simple parsing: handle + (must), - (must_not), and regular terms
        tokens = query.split()
        
        for token in tokens:
            if token.startswith('+'):
                must.append(token[1:])
            elif token.startswith('-'):
                must_not.append(token[1:])
            elif token.upper() in ('AND', 'OR', 'NOT'):
                continue
            else:
                if self._default_operator == QueryOperator.AND:
                    must.append(token)
                else:
                    should.append(token)
        
        return ParsedQuery(
            must=must,
            should=should,
            must_not=must_not,
            original=query,
        )


@dataclass
class ParsedQuery:
    """Parsed query."""
    must: List[str] = field(default_factory=list)
    should: List[str] = field(default_factory=list)
    must_not: List[str] = field(default_factory=list)
    original: str = ""
    
    @property
    def all_terms(self) -> List[str]:
        """Get all query terms."""
        return self.must + self.should


class InvertedIndex:
    """In-memory inverted index."""
    
    def __init__(self, analyzer: Optional[Analyzer] = None):
        self._analyzer = analyzer or StandardAnalyzer()
        self._index: Dict[str, Dict[str, List[int]]] = {}  # term -> {doc_id -> positions}
        self._documents: Dict[str, Dict[str, Any]] = {}
        self._doc_lengths: Dict[str, int] = {}
        self._field_doc_counts: Dict[str, int] = defaultdict(int)
        self._avg_doc_length = 0.0
    
    def add(
        self,
        doc_id: str,
        document: Dict[str, Any],
        fields: Optional[List[str]] = None,
    ) -> None:
        """Add a document to the index."""
        self._documents[doc_id] = document
        
        total_terms = 0
        
        for field_name, value in document.items():
            if fields and field_name not in fields:
                continue
            
            if not isinstance(value, str):
                continue
            
            terms = self._analyzer.analyze(value)
            total_terms += len(terms)
            self._field_doc_counts[field_name] += 1
            
            for position, term in enumerate(terms):
                if term not in self._index:
                    self._index[term] = {}
                
                if doc_id not in self._index[term]:
                    self._index[term][doc_id] = []
                
                self._index[term][doc_id].append(position)
        
        self._doc_lengths[doc_id] = total_terms
        self._update_avg_length()
    
    def remove(self, doc_id: str) -> bool:
        """Remove a document from the index."""
        if doc_id not in self._documents:
            return False
        
        del self._documents[doc_id]
        
        if doc_id in self._doc_lengths:
            del self._doc_lengths[doc_id]
        
        # Remove from inverted index
        empty_terms = []
        for term, postings in self._index.items():
            if doc_id in postings:
                del postings[doc_id]
            if not postings:
                empty_terms.append(term)
        
        for term in empty_terms:
            del self._index[term]
        
        self._update_avg_length()
        return True
    
    def _update_avg_length(self) -> None:
        """Update average document length."""
        if self._doc_lengths:
            self._avg_doc_length = sum(self._doc_lengths.values()) / len(self._doc_lengths)
        else:
            self._avg_doc_length = 0.0
    
    def search(
        self,
        query: ParsedQuery,
        limit: int = 10,
        offset: int = 0,
    ) -> Tuple[List[Tuple[str, float]], int]:
        """Search the index."""
        # Collect matching documents
        doc_scores: Dict[str, float] = defaultdict(float)
        
        all_terms = query.all_terms
        n_docs = len(self._documents)
        
        # Score documents using BM25
        for term in all_terms:
            if term not in self._index:
                continue
            
            postings = self._index[term]
            df = len(postings)
            idf = math.log((n_docs - df + 0.5) / (df + 0.5) + 1)
            
            for doc_id, positions in postings.items():
                tf = len(positions)
                doc_len = self._doc_lengths.get(doc_id, 1)
                
                # BM25 scoring
                k1 = 1.2
                b = 0.75
                
                score = idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * doc_len / max(self._avg_doc_length, 1)))
                
                if term in query.must:
                    doc_scores[doc_id] += score * 2  # Boost must terms
                else:
                    doc_scores[doc_id] += score
        
        # Filter by must terms
        if query.must:
            valid_docs = set(self._documents.keys())
            for term in query.must:
                if term in self._index:
                    valid_docs &= set(self._index[term].keys())
                else:
                    valid_docs = set()
            
            doc_scores = {k: v for k, v in doc_scores.items() if k in valid_docs}
        
        # Filter by must_not terms
        for term in query.must_not:
            if term in self._index:
                for doc_id in self._index[term]:
                    doc_scores.pop(doc_id, None)
        
        # Sort by score
        sorted_docs = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)
        total = len(sorted_docs)
        
        # Apply pagination
        paginated = sorted_docs[offset:offset + limit]
        
        return paginated, total
    
    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get a document by ID."""
        return self._documents.get(doc_id)
    
    def get_stats(self) -> IndexStats:
        """Get index statistics."""
        return IndexStats(
            document_count=len(self._documents),
            term_count=len(self._index),
            field_count=len(self._field_doc_counts),
        )


class SearchEngine:
    """
    Full-text search engine.
    """
    
    def __init__(
        self,
        analyzer: Optional[Analyzer] = None,
        highlight_tag: str = "<em>",
    ):
        self._analyzer = analyzer or StandardAnalyzer()
        self._index = InvertedIndex(self._analyzer)
        self._query_parser = QueryParser()
        self._highlight_tag = highlight_tag
    
    async def index(
        self,
        doc_id: str,
        document: Dict[str, Any],
        fields: Optional[List[str]] = None,
    ) -> None:
        """Index a document."""
        self._index.add(doc_id, document, fields)
    
    async def index_batch(
        self,
        documents: List[Tuple[str, Dict[str, Any]]],
        fields: Optional[List[str]] = None,
    ) -> int:
        """Index multiple documents."""
        count = 0
        for doc_id, document in documents:
            self._index.add(doc_id, document, fields)
            count += 1
        return count
    
    async def delete(self, doc_id: str) -> bool:
        """Delete a document."""
        return self._index.remove(doc_id)
    
    async def search(
        self,
        query: str,
        limit: int = 10,
        offset: int = 0,
        filters: Optional[Dict[str, Any]] = None,
        facets: Optional[List[str]] = None,
        highlight: bool = True,
        sort: Optional[SortOrder] = None,
    ) -> SearchResult:
        """
        Search for documents.
        """
        start = time.time()
        
        # Parse query
        parsed = self._query_parser.parse(query)
        
        # Search index
        results, total = self._index.search(parsed, limit=limit * 10, offset=0)  # Get more for filtering
        
        # Build hits
        hits = []
        
        for doc_id, score in results:
            document = self._index.get_document(doc_id)
            
            if not document:
                continue
            
            # Apply filters
            if filters and not self._matches_filters(document, filters):
                continue
            
            # Build hit
            hit = SearchHit(
                id=doc_id,
                score=score,
                document=document,
                matched_terms=parsed.all_terms,
            )
            
            # Add highlights
            if highlight:
                hit.highlights = self._highlight_document(document, parsed.all_terms)
            
            hits.append(hit)
            
            if len(hits) >= limit:
                break
        
        # Build facets
        facet_results = {}
        if facets:
            facet_results = self._build_facets(results, facets)
        
        # Sort if needed
        if sort == SortOrder.ASC:
            hits.sort(key=lambda h: h.score)
        # DESC and RELEVANCE are default (already sorted)
        
        # Apply final pagination
        paginated_hits = hits[offset:offset + limit]
        
        return SearchResult(
            hits=paginated_hits,
            total=total,
            took_ms=(time.time() - start) * 1000,
            facets=facet_results,
            query=query,
            page=offset // limit + 1 if limit > 0 else 1,
            page_size=limit,
        )
    
    def _matches_filters(
        self,
        document: Dict[str, Any],
        filters: Dict[str, Any],
    ) -> bool:
        """Check if document matches filters."""
        for field, value in filters.items():
            doc_value = document.get(field)
            
            if isinstance(value, list):
                if doc_value not in value:
                    return False
            elif doc_value != value:
                return False
        
        return True
    
    def _highlight_document(
        self,
        document: Dict[str, Any],
        terms: List[str],
    ) -> Dict[str, List[str]]:
        """Highlight matching terms in document."""
        highlights = {}
        
        for field, value in document.items():
            if not isinstance(value, str):
                continue
            
            field_highlights = []
            
            for term in terms:
                pattern = re.compile(re.escape(term), re.IGNORECASE)
                matches = list(pattern.finditer(value))
                
                for match in matches[:3]:  # Limit highlights per term
                    start = max(0, match.start() - 50)
                    end = min(len(value), match.end() + 50)
                    
                    snippet = value[start:end]
                    
                    # Add highlight tags
                    highlighted = pattern.sub(
                        f"{self._highlight_tag}\\g<0></{self._highlight_tag.strip('<>')}",
                        snippet,
                    )
                    
                    if start > 0:
                        highlighted = "..." + highlighted
                    if end < len(value):
                        highlighted = highlighted + "..."
                    
                    field_highlights.append(highlighted)
            
            if field_highlights:
                highlights[field] = field_highlights
        
        return highlights
    
    def _build_facets(
        self,
        results: List[Tuple[str, float]],
        facet_fields: List[str],
    ) -> Dict[str, Facet]:
        """Build facets from search results."""
        facets = {}
        
        for field in facet_fields:
            value_counts: Dict[Any, int] = defaultdict(int)
            
            for doc_id, _ in results:
                document = self._index.get_document(doc_id)
                if document and field in document:
                    value = document[field]
                    value_counts[value] += 1
            
            facet_values = [
                FacetValue(value=v, count=c)
                for v, c in sorted(value_counts.items(), key=lambda x: x[1], reverse=True)
            ]
            
            facets[field] = Facet(field=field, values=facet_values)
        
        return facets
    
    async def suggest(
        self,
        prefix: str,
        field: Optional[str] = None,
        limit: int = 10,
    ) -> List[str]:
        """Get search suggestions."""
        suggestions = []
        
        prefix_lower = prefix.lower()
        
        for term in self._index._index.keys():
            if term.startswith(prefix_lower):
                suggestions.append(term)
                if len(suggestions) >= limit:
                    break
        
        return suggestions
    
    async def get_stats(self) -> IndexStats:
        """Get search engine statistics."""
        return self._index.get_stats()


# Decorators
def searchable(*fields: str) -> Callable:
    """
    Decorator to mark a class as searchable.
    
    Example:
        @searchable("title", "content")
        class Article:
            ...
    """
    def decorator(cls: type) -> type:
        cls._searchable_fields = list(fields)
        return cls
    
    return decorator


def search_field(
    boost: float = 1.0,
    analyzer: Optional[str] = None,
) -> Callable:
    """
    Decorator to configure a search field.
    
    Example:
        class Article:
            @search_field(boost=2.0)
            def title(self) -> str:
                ...
    """
    def decorator(func: Callable) -> Callable:
        func._search_boost = boost
        func._search_analyzer = analyzer
        return func
    
    return decorator


# Factory functions
def create_search_engine(
    analyzer: Optional[Analyzer] = None,
    highlight_tag: str = "<em>",
) -> SearchEngine:
    """Create a search engine."""
    return SearchEngine(analyzer, highlight_tag)


def create_analyzer(
    stop_words: Optional[Set[str]] = None,
    stemming: bool = False,
) -> StandardAnalyzer:
    """Create a standard analyzer."""
    return StandardAnalyzer(stop_words=stop_words, stemming=stemming)


def create_tokenizer(
    lowercase: bool = True,
    min_length: int = 2,
) -> SimpleTokenizer:
    """Create a tokenizer."""
    return SimpleTokenizer(lowercase, min_length)


def create_query_parser(
    default_operator: QueryOperator = QueryOperator.OR,
) -> QueryParser:
    """Create a query parser."""
    return QueryParser(default_operator)


__all__ = [
    # Exceptions
    "SearchError",
    "IndexError",
    "QueryError",
    # Enums
    "MatchType",
    "SortOrder",
    "QueryOperator",
    # Data classes
    "SearchHit",
    "FacetValue",
    "Facet",
    "SearchResult",
    "IndexStats",
    "ParsedQuery",
    # Core classes
    "Tokenizer",
    "SimpleTokenizer",
    "Analyzer",
    "StandardAnalyzer",
    "QueryParser",
    "InvertedIndex",
    "SearchEngine",
    # Decorators
    "searchable",
    "search_field",
    # Factory
    "create_search_engine",
    "create_analyzer",
    "create_tokenizer",
    "create_query_parser",
]
