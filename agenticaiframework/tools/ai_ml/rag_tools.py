"""
RAG (Retrieval-Augmented Generation) Tools.
"""

import logging
from typing import Any, Dict, List, Optional

from ..base import BaseTool, ToolConfig

logger = logging.getLogger(__name__)


class RAGTool(BaseTool):
    """
    Generic RAG tool for retrieval-augmented generation.
    
    Features:
    - Document ingestion
    - Vector store integration
    - Retrieval and generation
    - Multi-source support
    """
    
    def __init__(
        self,
        config: Optional[ToolConfig] = None,
        api_key: Optional[str] = None,
        embedding_model: str = 'text-embedding-ada-002',
        llm_model: str = 'gpt-4',
    ):
        super().__init__(config or ToolConfig(
            name="RAGTool",
            description="Retrieval-Augmented Generation tool"
        ))
        self.api_key = api_key or self.config.api_key
        self.embedding_model = embedding_model
        self.llm_model = llm_model
        self._documents: List[Dict] = []
        self._embeddings: List[List[float]] = []
    
    def _execute(
        self,
        query: str,
        documents: Optional[List[str]] = None,
        top_k: int = 5,
        include_sources: bool = True,
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Perform RAG query.
        
        Args:
            query: User query
            documents: Documents to search (or use indexed)
            top_k: Number of documents to retrieve
            include_sources: Include source documents in response
            system_prompt: Custom system prompt
            
        Returns:
            Dict with generated response and sources
        """
        # Index new documents if provided
        if documents:
            self.add_documents(documents)
        
        if not self._documents:
            return {
                'query': query,
                'status': 'error',
                'error': 'No documents indexed',
            }
        
        # Retrieve relevant documents
        relevant_docs = self._retrieve(query, top_k)
        
        # Generate response
        response = self._generate(query, relevant_docs, system_prompt)
        
        result = {
            'query': query,
            'status': 'success',
            'response': response,
            'documents_searched': len(self._documents),
        }
        
        if include_sources:
            result['sources'] = [
                {
                    'text': doc['text'][:500],
                    'score': doc.get('score', 0),
                    'metadata': doc.get('metadata', {}),
                }
                for doc in relevant_docs
            ]
        
        return result
    
    def add_documents(self, documents: List[str]):
        """Add documents to the index."""
        for doc in documents:
            # Create embedding
            embedding = self._get_embedding(doc)
            
            self._documents.append({
                'text': doc,
                'metadata': {},
            })
            self._embeddings.append(embedding)
    
    def _get_embedding(self, text: str) -> List[float]:
        """Get embedding for text."""
        if self.api_key:
            try:
                import openai
                client = openai.OpenAI(api_key=self.api_key)
                response = client.embeddings.create(
                    model=self.embedding_model,
                    input=text[:8000],  # Limit input size
                )
                return response.data[0].embedding
            except Exception as e:
                logger.warning(f"OpenAI embedding failed: {e}")
        
        # Fallback: simple hash-based embedding
        import hashlib
        hash_obj = hashlib.sha256(text.encode())
        hash_bytes = hash_obj.digest()
        return [b / 255.0 for b in hash_bytes]
    
    def _retrieve(self, query: str, top_k: int) -> List[Dict]:
        """Retrieve relevant documents."""
        query_embedding = self._get_embedding(query)
        
        # Calculate similarities
        scores = []
        for i, doc_embedding in enumerate(self._embeddings):
            score = self._cosine_similarity(query_embedding, doc_embedding)
            scores.append((i, score))
        
        # Sort by score
        scores.sort(key=lambda x: x[1], reverse=True)
        
        # Return top-k
        results = []
        for i, score in scores[:top_k]:
            doc = self._documents[i].copy()
            doc['score'] = score
            results.append(doc)
        
        return results
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity."""
        import math
        
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return dot / (norm_a * norm_b)
    
    def _generate(
        self,
        query: str,
        documents: List[Dict],
        system_prompt: Optional[str],
    ) -> str:
        """Generate response using LLM."""
        if not self.api_key:
            # Fallback: return concatenated documents
            return f"Based on the documents:\n\n" + "\n\n".join(
                d['text'][:200] for d in documents
            )
        
        try:
            import openai
        except ImportError:
            return "OpenAI package required for generation"
        
        client = openai.OpenAI(api_key=self.api_key)
        
        # Build context
        context = "\n\n---\n\n".join(d['text'] for d in documents)
        
        default_system = (
            "You are a helpful assistant. Answer questions based on the "
            "provided context. If the answer is not in the context, say so."
        )
        
        messages = [
            {"role": "system", "content": system_prompt or default_system},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"},
        ]
        
        response = client.chat.completions.create(
            model=self.llm_model,
            messages=messages,
            temperature=0.7,
        )
        
        return response.choices[0].message.content
    
    def clear_index(self):
        """Clear all indexed documents."""
        self._documents = []
        self._embeddings = []


class AIMindTool(BaseTool):
    """
    Tool for AI-powered knowledge management.
    
    Features:
    - Knowledge graph construction
    - Semantic memory
    - Reasoning chains
    - Context management
    """
    
    def __init__(
        self,
        config: Optional[ToolConfig] = None,
        api_key: Optional[str] = None,
    ):
        super().__init__(config or ToolConfig(
            name="AIMindTool",
            description="AI-powered knowledge management"
        ))
        self.api_key = api_key or self.config.api_key
        self._knowledge_graph: Dict[str, Dict] = {}
        self._memories: List[Dict] = []
    
    def _execute(
        self,
        action: str,
        content: Optional[str] = None,
        query: Optional[str] = None,
        entity: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Perform AI mind operation.
        
        Args:
            action: 'remember', 'recall', 'reason', 'add_knowledge'
            content: Content to remember or add
            query: Query for recall or reasoning
            entity: Entity for knowledge graph
            
        Returns:
            Dict with operation results
        """
        if action == 'remember':
            return self._remember(content)
        elif action == 'recall':
            return self._recall(query)
        elif action == 'reason':
            return self._reason(query)
        elif action == 'add_knowledge':
            return self._add_knowledge(entity, content)
        else:
            return {'status': 'error', 'error': f'Unknown action: {action}'}
    
    def _remember(self, content: str) -> Dict[str, Any]:
        """Store information in memory."""
        import time
        
        memory = {
            'content': content,
            'timestamp': time.time(),
            'type': 'episodic',
        }
        
        # Extract entities (simple approach)
        entities = self._extract_entities(content)
        memory['entities'] = entities
        
        self._memories.append(memory)
        
        return {
            'status': 'success',
            'action': 'remember',
            'memory_id': len(self._memories) - 1,
            'entities_extracted': entities,
        }
    
    def _recall(self, query: str) -> Dict[str, Any]:
        """Recall relevant memories."""
        if not self._memories:
            return {
                'status': 'success',
                'action': 'recall',
                'memories': [],
                'message': 'No memories stored',
            }
        
        # Simple keyword matching
        query_words = set(query.lower().split())
        
        scored_memories = []
        for i, memory in enumerate(self._memories):
            content_words = set(memory['content'].lower().split())
            overlap = len(query_words & content_words)
            
            if overlap > 0:
                scored_memories.append({
                    'id': i,
                    'content': memory['content'],
                    'score': overlap / len(query_words),
                    'timestamp': memory['timestamp'],
                })
        
        scored_memories.sort(key=lambda x: x['score'], reverse=True)
        
        return {
            'status': 'success',
            'action': 'recall',
            'query': query,
            'memories': scored_memories[:5],
        }
    
    def _reason(self, query: str) -> Dict[str, Any]:
        """Perform reasoning over knowledge."""
        if not self.api_key:
            return {
                'status': 'error',
                'error': 'API key required for reasoning',
            }
        
        try:
            import openai
        except ImportError:
            return {'status': 'error', 'error': 'OpenAI package required'}
        
        # Gather context
        memories = self._recall(query).get('memories', [])
        context = "\n".join(m['content'] for m in memories)
        
        knowledge = "\n".join(
            f"- {entity}: {info.get('description', '')}"
            for entity, info in self._knowledge_graph.items()
        )
        
        client = openai.OpenAI(api_key=self.api_key)
        
        prompt = f"""Based on the following context and knowledge, reason about the query.

Context (memories):
{context or 'No relevant memories'}

Knowledge Graph:
{knowledge or 'No knowledge stored'}

Query: {query}

Provide a reasoned response:"""
        
        response = client.chat.completions.create(
            model='gpt-4',
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        
        return {
            'status': 'success',
            'action': 'reason',
            'query': query,
            'reasoning': response.choices[0].message.content,
            'context_used': len(memories),
        }
    
    def _add_knowledge(self, entity: str, content: str) -> Dict[str, Any]:
        """Add knowledge to graph."""
        if not entity:
            return {'status': 'error', 'error': 'Entity required'}
        
        if entity not in self._knowledge_graph:
            self._knowledge_graph[entity] = {
                'description': content,
                'relations': [],
            }
        else:
            self._knowledge_graph[entity]['description'] = content
        
        return {
            'status': 'success',
            'action': 'add_knowledge',
            'entity': entity,
            'graph_size': len(self._knowledge_graph),
        }
    
    def _extract_entities(self, text: str) -> List[str]:
        """Extract named entities from text."""
        # Simple extraction: capitalized words
        words = text.split()
        entities = [
            w.strip('.,!?')
            for w in words
            if w[0].isupper() and len(w) > 2
        ]
        return list(set(entities))
    
    def get_knowledge_graph(self) -> Dict[str, Dict]:
        """Get the knowledge graph."""
        return self._knowledge_graph.copy()
    
    def clear(self):
        """Clear all memories and knowledge."""
        self._memories = []
        self._knowledge_graph = {}


__all__ = ['RAGTool', 'AIMindTool']
