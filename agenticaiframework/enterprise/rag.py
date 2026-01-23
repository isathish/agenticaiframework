"""
Enterprise RAG (Retrieval-Augmented Generation) Module.

Provides retrieval-augmented generation patterns, context injection,
document retrieval, and answer generation for agents.

Example:
    # Create RAG pipeline
    rag = RAGPipeline(
        retriever=VectorRetriever(store=vector_store),
        generator=LLMGenerator(client=openai_client),
    )
    
    # Query
    answer = await rag.query("What is RAG?")
    
    # With context builder
    context = await rag.retrieve("What is RAG?", k=5)
    response = await rag.generate(query, context)
"""

from __future__ import annotations

import asyncio
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


class RAGError(Exception):
    """RAG pipeline error."""
    pass


class RetrievalError(RAGError):
    """Document retrieval error."""
    pass


class GenerationError(RAGError):
    """Response generation error."""
    pass


class RetrievalStrategy(str, Enum):
    """Retrieval strategies."""
    DENSE = "dense"           # Vector similarity
    SPARSE = "sparse"         # BM25/keyword
    HYBRID = "hybrid"         # Dense + sparse
    RERANK = "rerank"         # With reranking


class ChunkStrategy(str, Enum):
    """Document chunking strategies."""
    FIXED = "fixed"           # Fixed token count
    SENTENCE = "sentence"     # Sentence boundaries
    PARAGRAPH = "paragraph"   # Paragraph boundaries
    SEMANTIC = "semantic"     # Semantic similarity


@dataclass
class Document:
    """A retrievable document."""
    id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    score: float = 0.0
    source: Optional[str] = None
    chunk_index: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "metadata": self.metadata,
            "score": self.score,
            "source": self.source,
        }


@dataclass
class RetrievalResult:
    """Result of document retrieval."""
    documents: List[Document]
    query: str
    strategy: RetrievalStrategy = RetrievalStrategy.DENSE
    duration_ms: float = 0.0
    
    @property
    def contents(self) -> List[str]:
        """Get document contents."""
        return [doc.content for doc in self.documents]
    
    @property
    def context(self) -> str:
        """Get combined context."""
        return "\n\n".join(self.contents)
    
    def __len__(self) -> int:
        return len(self.documents)


@dataclass
class RAGResponse:
    """RAG response with sources."""
    answer: str
    query: str
    sources: List[Document]
    context_used: str = ""
    model: str = ""
    duration_ms: float = 0.0
    tokens_used: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "answer": self.answer,
            "query": self.query,
            "sources": [doc.to_dict() for doc in self.sources],
            "model": self.model,
            "duration_ms": self.duration_ms,
        }


class Retriever(ABC):
    """Abstract retriever interface."""
    
    @abstractmethod
    async def retrieve(
        self,
        query: str,
        k: int = 5,
        filter: Optional[Dict[str, Any]] = None,
    ) -> List[Document]:
        """Retrieve relevant documents."""
        pass


class VectorRetriever(Retriever):
    """Vector-based retriever using embeddings."""
    
    def __init__(
        self,
        store: Any,  # VectorStore
        embedder: Optional[Any] = None,
    ):
        self._store = store
        self._embedder = embedder
    
    async def retrieve(
        self,
        query: str,
        k: int = 5,
        filter: Optional[Dict[str, Any]] = None,
    ) -> List[Document]:
        """Retrieve using vector similarity."""
        results = await self._store.search(query, k=k, filter=filter)
        
        return [
            Document(
                id=r.id if hasattr(r, 'id') else str(i),
                content=r.text if hasattr(r, 'text') else str(r),
                score=r.score if hasattr(r, 'score') else 0.0,
                metadata=r.metadata if hasattr(r, 'metadata') else {},
            )
            for i, r in enumerate(results)
        ]


class KeywordRetriever(Retriever):
    """Keyword-based retriever (BM25-like)."""
    
    def __init__(self, documents: List[Document]):
        self._documents = documents
        self._index: Dict[str, List[int]] = {}
        self._build_index()
    
    def _build_index(self) -> None:
        """Build inverted index."""
        for i, doc in enumerate(self._documents):
            words = doc.content.lower().split()
            for word in set(words):
                if word not in self._index:
                    self._index[word] = []
                self._index[word].append(i)
    
    async def retrieve(
        self,
        query: str,
        k: int = 5,
        filter: Optional[Dict[str, Any]] = None,
    ) -> List[Document]:
        """Retrieve using keyword matching."""
        words = query.lower().split()
        scores: Dict[int, float] = {}
        
        for word in words:
            if word in self._index:
                for doc_idx in self._index[word]:
                    scores[doc_idx] = scores.get(doc_idx, 0) + 1
        
        # Sort by score
        sorted_indices = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
        
        results = []
        for idx in sorted_indices[:k]:
            doc = self._documents[idx]
            doc.score = scores[idx]
            
            # Apply filter
            if filter:
                if not all(doc.metadata.get(key) == value for key, value in filter.items()):
                    continue
            
            results.append(doc)
        
        return results[:k]


class HybridRetriever(Retriever):
    """Hybrid retriever combining dense and sparse."""
    
    def __init__(
        self,
        dense_retriever: Retriever,
        sparse_retriever: Retriever,
        dense_weight: float = 0.7,
    ):
        self._dense = dense_retriever
        self._sparse = sparse_retriever
        self._dense_weight = dense_weight
    
    async def retrieve(
        self,
        query: str,
        k: int = 5,
        filter: Optional[Dict[str, Any]] = None,
    ) -> List[Document]:
        """Retrieve using hybrid approach."""
        # Retrieve from both
        dense_results, sparse_results = await asyncio.gather(
            self._dense.retrieve(query, k=k * 2, filter=filter),
            self._sparse.retrieve(query, k=k * 2, filter=filter),
        )
        
        # Combine scores using Reciprocal Rank Fusion
        scores: Dict[str, float] = {}
        docs: Dict[str, Document] = {}
        
        for rank, doc in enumerate(dense_results):
            rrf_score = self._dense_weight / (rank + 60)
            scores[doc.id] = scores.get(doc.id, 0) + rrf_score
            docs[doc.id] = doc
        
        sparse_weight = 1 - self._dense_weight
        for rank, doc in enumerate(sparse_results):
            rrf_score = sparse_weight / (rank + 60)
            scores[doc.id] = scores.get(doc.id, 0) + rrf_score
            if doc.id not in docs:
                docs[doc.id] = doc
        
        # Sort by combined score
        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
        
        results = []
        for doc_id in sorted_ids[:k]:
            doc = docs[doc_id]
            doc.score = scores[doc_id]
            results.append(doc)
        
        return results


class RerankingRetriever(Retriever):
    """Retriever with reranking."""
    
    def __init__(
        self,
        base_retriever: Retriever,
        reranker: Callable[[str, List[Document]], List[Document]],
        initial_k: int = 20,
    ):
        self._base = base_retriever
        self._reranker = reranker
        self._initial_k = initial_k
    
    async def retrieve(
        self,
        query: str,
        k: int = 5,
        filter: Optional[Dict[str, Any]] = None,
    ) -> List[Document]:
        """Retrieve and rerank."""
        # Get more candidates
        candidates = await self._base.retrieve(
            query, k=self._initial_k, filter=filter
        )
        
        # Rerank
        if asyncio.iscoroutinefunction(self._reranker):
            reranked = await self._reranker(query, candidates)
        else:
            reranked = self._reranker(query, candidates)
        
        return reranked[:k]


class Generator(ABC):
    """Abstract generator interface."""
    
    @abstractmethod
    async def generate(
        self,
        query: str,
        context: str,
        **kwargs: Any,
    ) -> str:
        """Generate response given query and context."""
        pass


class LLMGenerator(Generator):
    """LLM-based response generator."""
    
    DEFAULT_TEMPLATE = """Answer the question based on the following context.
If the answer cannot be found in the context, say "I don't have enough information to answer this question."

Context:
{context}

Question: {query}

Answer:"""
    
    def __init__(
        self,
        client: Any,
        model: Optional[str] = None,
        template: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ):
        self._client = client
        self._model = model
        self._template = template or self.DEFAULT_TEMPLATE
        self._temperature = temperature
        self._max_tokens = max_tokens
    
    async def generate(
        self,
        query: str,
        context: str,
        **kwargs: Any,
    ) -> str:
        """Generate response using LLM."""
        prompt = self._template.format(query=query, context=context)
        
        # Handle different client interfaces
        if hasattr(self._client, 'chat'):
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                temperature=kwargs.get("temperature", self._temperature),
                max_tokens=kwargs.get("max_tokens", self._max_tokens),
            )
            return response.choices[0].message.content
        
        if hasattr(self._client, 'generate'):
            return await self._client.generate(prompt=prompt, **kwargs)
        
        raise GenerationError(f"Unsupported client: {type(self._client)}")


class ContextBuilder:
    """Builds context from retrieved documents."""
    
    def __init__(
        self,
        max_tokens: int = 4000,
        token_counter: Optional[Callable[[str], int]] = None,
        include_metadata: bool = False,
        separator: str = "\n\n---\n\n",
    ):
        self._max_tokens = max_tokens
        self._token_counter = token_counter or (lambda s: len(s) // 4)
        self._include_metadata = include_metadata
        self._separator = separator
    
    def build(self, documents: List[Document]) -> str:
        """Build context from documents."""
        parts = []
        total_tokens = 0
        
        for i, doc in enumerate(documents):
            part = self._format_document(doc, i + 1)
            tokens = self._token_counter(part)
            
            if total_tokens + tokens > self._max_tokens:
                break
            
            parts.append(part)
            total_tokens += tokens
        
        return self._separator.join(parts)
    
    def _format_document(self, doc: Document, index: int) -> str:
        """Format a single document."""
        parts = [f"[{index}] {doc.content}"]
        
        if self._include_metadata and doc.metadata:
            meta_str = ", ".join(f"{k}: {v}" for k, v in doc.metadata.items())
            parts.append(f"Metadata: {meta_str}")
        
        if doc.source:
            parts.append(f"Source: {doc.source}")
        
        return "\n".join(parts)


class RAGPipeline:
    """
    Complete RAG pipeline.
    """
    
    def __init__(
        self,
        retriever: Retriever,
        generator: Generator,
        context_builder: Optional[ContextBuilder] = None,
        pre_processors: Optional[List[Callable[[str], str]]] = None,
        post_processors: Optional[List[Callable[[str], str]]] = None,
    ):
        self._retriever = retriever
        self._generator = generator
        self._context_builder = context_builder or ContextBuilder()
        self._pre_processors = pre_processors or []
        self._post_processors = post_processors or []
    
    async def query(
        self,
        query: str,
        k: int = 5,
        filter: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> RAGResponse:
        """
        Execute RAG query.
        
        Args:
            query: User query
            k: Number of documents to retrieve
            filter: Metadata filter
            **kwargs: Additional generation kwargs
        """
        start = time.time()
        
        # Pre-process query
        processed_query = query
        for processor in self._pre_processors:
            processed_query = processor(processed_query)
        
        # Retrieve
        documents = await self._retriever.retrieve(
            processed_query, k=k, filter=filter
        )
        
        # Build context
        context = self._context_builder.build(documents)
        
        # Generate
        answer = await self._generator.generate(
            processed_query, context, **kwargs
        )
        
        # Post-process
        for processor in self._post_processors:
            answer = processor(answer)
        
        duration = (time.time() - start) * 1000
        
        return RAGResponse(
            answer=answer,
            query=query,
            sources=documents,
            context_used=context,
            duration_ms=duration,
        )
    
    async def retrieve(
        self,
        query: str,
        k: int = 5,
        filter: Optional[Dict[str, Any]] = None,
    ) -> RetrievalResult:
        """Retrieve documents only."""
        start = time.time()
        
        documents = await self._retriever.retrieve(query, k=k, filter=filter)
        
        return RetrievalResult(
            documents=documents,
            query=query,
            duration_ms=(time.time() - start) * 1000,
        )
    
    async def generate(
        self,
        query: str,
        context: str,
        **kwargs: Any,
    ) -> str:
        """Generate response only."""
        return await self._generator.generate(query, context, **kwargs)


class DocumentChunker:
    """Chunk documents for indexing."""
    
    def __init__(
        self,
        strategy: ChunkStrategy = ChunkStrategy.FIXED,
        chunk_size: int = 512,
        overlap: int = 50,
    ):
        self._strategy = strategy
        self._chunk_size = chunk_size
        self._overlap = overlap
    
    def chunk(self, document: Document) -> List[Document]:
        """Chunk a document."""
        if self._strategy == ChunkStrategy.FIXED:
            return self._chunk_fixed(document)
        elif self._strategy == ChunkStrategy.SENTENCE:
            return self._chunk_sentence(document)
        elif self._strategy == ChunkStrategy.PARAGRAPH:
            return self._chunk_paragraph(document)
        else:
            return [document]
    
    def _chunk_fixed(self, document: Document) -> List[Document]:
        """Chunk by fixed token count."""
        words = document.content.split()
        chunks = []
        start = 0
        
        while start < len(words):
            end = start + self._chunk_size
            chunk_words = words[start:end]
            
            chunks.append(Document(
                id=f"{document.id}_chunk_{len(chunks)}",
                content=" ".join(chunk_words),
                metadata={**document.metadata, "parent_id": document.id},
                source=document.source,
                chunk_index=len(chunks),
            ))
            
            start = end - self._overlap
        
        return chunks
    
    def _chunk_sentence(self, document: Document) -> List[Document]:
        """Chunk by sentence boundaries."""
        import re
        sentences = re.split(r'(?<=[.!?])\s+', document.content)
        
        chunks = []
        current_chunk = []
        current_size = 0
        
        for sentence in sentences:
            words = len(sentence.split())
            
            if current_size + words > self._chunk_size and current_chunk:
                chunks.append(Document(
                    id=f"{document.id}_chunk_{len(chunks)}",
                    content=" ".join(current_chunk),
                    metadata={**document.metadata, "parent_id": document.id},
                    source=document.source,
                    chunk_index=len(chunks),
                ))
                current_chunk = []
                current_size = 0
            
            current_chunk.append(sentence)
            current_size += words
        
        if current_chunk:
            chunks.append(Document(
                id=f"{document.id}_chunk_{len(chunks)}",
                content=" ".join(current_chunk),
                metadata={**document.metadata, "parent_id": document.id},
                source=document.source,
                chunk_index=len(chunks),
            ))
        
        return chunks
    
    def _chunk_paragraph(self, document: Document) -> List[Document]:
        """Chunk by paragraph boundaries."""
        paragraphs = document.content.split("\n\n")
        
        chunks = []
        for i, para in enumerate(paragraphs):
            if para.strip():
                chunks.append(Document(
                    id=f"{document.id}_chunk_{i}",
                    content=para.strip(),
                    metadata={**document.metadata, "parent_id": document.id},
                    source=document.source,
                    chunk_index=i,
                ))
        
        return chunks


class ConversationalRAG:
    """
    RAG with conversation history.
    """
    
    def __init__(
        self,
        rag_pipeline: RAGPipeline,
        max_history: int = 5,
    ):
        self._rag = rag_pipeline
        self._max_history = max_history
        self._history: List[Tuple[str, str]] = []
    
    async def query(
        self,
        query: str,
        k: int = 5,
        **kwargs: Any,
    ) -> RAGResponse:
        """Query with conversation context."""
        # Build conversation-aware query
        if self._history:
            history_context = "\n".join(
                f"User: {q}\nAssistant: {a}"
                for q, a in self._history[-self._max_history:]
            )
            enhanced_query = f"Given this conversation:\n{history_context}\n\nNew question: {query}"
        else:
            enhanced_query = query
        
        # Execute RAG
        response = await self._rag.query(enhanced_query, k=k, **kwargs)
        
        # Update history
        self._history.append((query, response.answer))
        
        return response
    
    def clear_history(self) -> None:
        """Clear conversation history."""
        self._history.clear()


# Decorators
def with_rag(
    rag_pipeline: RAGPipeline,
    k: int = 5,
) -> Callable:
    """
    Decorator to enhance function with RAG.
    
    Example:
        @with_rag(rag_pipeline)
        async def answer_question(query: str) -> str:
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(query: str, *args: Any, **kwargs: Any) -> RAGResponse:
            return await rag_pipeline.query(query, k=k, **kwargs)
        
        return wrapper
    
    return decorator


# Factory functions
def create_rag_pipeline(
    vector_store: Any,
    llm_client: Any,
    model: Optional[str] = None,
    retrieval_k: int = 5,
    max_context_tokens: int = 4000,
    **kwargs: Any,
) -> RAGPipeline:
    """
    Factory function to create a RAG pipeline.
    
    Args:
        vector_store: Vector store for retrieval
        llm_client: LLM client for generation
        model: Model name
        retrieval_k: Default number of documents
        max_context_tokens: Max context size
    """
    retriever = VectorRetriever(store=vector_store)
    generator = LLMGenerator(client=llm_client, model=model, **kwargs)
    context_builder = ContextBuilder(max_tokens=max_context_tokens)
    
    return RAGPipeline(
        retriever=retriever,
        generator=generator,
        context_builder=context_builder,
    )


__all__ = [
    # Exceptions
    "RAGError",
    "RetrievalError",
    "GenerationError",
    # Enums
    "RetrievalStrategy",
    "ChunkStrategy",
    # Data classes
    "Document",
    "RetrievalResult",
    "RAGResponse",
    # Retrievers
    "Retriever",
    "VectorRetriever",
    "KeywordRetriever",
    "HybridRetriever",
    "RerankingRetriever",
    # Generators
    "Generator",
    "LLMGenerator",
    # Context
    "ContextBuilder",
    # Pipeline
    "RAGPipeline",
    # Chunking
    "DocumentChunker",
    # Conversational
    "ConversationalRAG",
    # Decorators
    "with_rag",
    # Factory
    "create_rag_pipeline",
]
