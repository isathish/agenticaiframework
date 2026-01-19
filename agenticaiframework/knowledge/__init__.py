"""
Knowledge Module - Build and Manage Knowledge Bases.

Create knowledge bases from various sources and generate embeddings
for vector database storage.

Sources:
- Web search results (Serper, DuckDuckGo)
- Web pages and URLs
- Documents (PDF, DOCX, TXT, Markdown)
- Images (OCR with Tesseract or GPT-4 Vision)
- APIs and JSON data
- CSV and Excel files
- Code files

Embedding Providers:
- OpenAI (text-embedding-3-small, text-embedding-3-large)
- Azure OpenAI
- HuggingFace (sentence-transformers)
- Cohere

Vector Databases:
- Qdrant
- Pinecone  
- ChromaDB
- Milvus
- MongoDB Atlas
- PostgreSQL (pgvector)
- OpenSearch
- Redis

Example:
    >>> from agenticaiframework.knowledge import KnowledgeBuilder, UnifiedVectorDBTool
    >>> 
    >>> # Build knowledge base from multiple sources
    >>> builder = KnowledgeBuilder(
    ...     embedding_provider="openai",
    ...     embedding_model="text-embedding-3-small"
    ... )
    >>> 
    >>> # Add from various sources
    >>> builder.add_from_file("docs/manual.pdf")
    >>> builder.add_from_url("https://example.com/article")
    >>> builder.add_from_web_search("machine learning best practices")
    >>> builder.add_from_api("https://api.example.com/data")
    >>> builder.add_from_image("diagram.png", ocr_provider="openai_vision")
    >>> 
    >>> # Get embeddings for vector database
    >>> embeddings = builder.get_embeddings()
    >>> 
    >>> # Store in vector database
    >>> db = UnifiedVectorDBTool(db_type="qdrant", collection_name="knowledge")
    >>> for emb in embeddings:
    ...     db.insert([emb.embedding], payloads=[{"content": emb.content}])
    >>> 
    >>> # Or use format-specific converters
    >>> qdrant_points = [e.to_qdrant_point() for e in embeddings]
    >>> pinecone_vectors = [e.to_pinecone_vector() for e in embeddings]
    >>> chroma_docs = [e.to_chroma_document() for e in embeddings]
"""

# Legacy retriever for backward compatibility
from .retriever import KnowledgeRetriever

from .builder import (
    # Types
    SourceType,
    KnowledgeChunk,
    EmbeddingOutput,
    # Embedding Providers
    EmbeddingProvider,
    OpenAIEmbedding,
    AzureOpenAIEmbedding,
    HuggingFaceEmbedding,
    CohereEmbedding,
    # Source Loaders
    SourceLoader,
    TextLoader,
    MarkdownLoader,
    PDFLoader,
    DocxLoader,
    ImageLoader,
    WebLoader,
    WebSearchLoader,
    APILoader,
    JSONLoader,
    CSVLoader,
    # Main Builder
    KnowledgeBuilder,
)

from .vector_db import (
    # Types
    VectorDBType,
    VectorDBConfig,
    VectorDBResult,
    # Clients
    VectorDBClient,
    QdrantClient,
    PineconeClient,
    ChromaClient,
    InMemoryVectorDB,
    # Tools
    UnifiedVectorDBTool,
    create_vector_db_tool,
)

__all__ = [
    # Legacy
    "KnowledgeRetriever",
    # Source Types
    "SourceType",
    "KnowledgeChunk",
    "EmbeddingOutput",
    # Embedding Providers
    "EmbeddingProvider",
    "OpenAIEmbedding",
    "AzureOpenAIEmbedding",
    "HuggingFaceEmbedding",
    "CohereEmbedding",
    # Source Loaders
    "SourceLoader",
    "TextLoader",
    "MarkdownLoader",
    "PDFLoader",
    "DocxLoader",
    "ImageLoader",
    "WebLoader",
    "WebSearchLoader",
    "APILoader",
    "JSONLoader",
    "CSVLoader",
    # Main Builder
    "KnowledgeBuilder",
    # Vector DB Types
    "VectorDBType",
    "VectorDBConfig",
    "VectorDBResult",
    # Vector DB Clients
    "VectorDBClient",
    "QdrantClient",
    "PineconeClient",
    "ChromaClient",
    "InMemoryVectorDB",
    # Vector DB Tools
    "UnifiedVectorDBTool",
    "create_vector_db_tool",
]
