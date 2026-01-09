"""
Memory and RAG Evaluation systems.

Provides:
- MemoryEvaluator: Memory accuracy, context relevance, knowledge freshness
- RAGEvaluator: Retrieval accuracy, citation correctness, answer groundedness
"""

import uuid
import time
import logging
import statistics
from typing import Dict, Any, List
from collections import defaultdict

logger = logging.getLogger(__name__)


class MemoryEvaluator:
    """Memory & Context Evaluation system."""
    
    def __init__(self):
        self.memory_evaluations: List[Dict[str, Any]] = []
        self.memory_metrics: Dict[str, Any] = {
            'total_queries': 0,
            'relevant_retrievals': 0,
            'stale_data_usage': 0,
            'context_precision_scores': [],
            'memory_overwrite_errors': 0
        }
    
    def evaluate_memory_retrieval(self,
                                  query: str,
                                  retrieved_memories: List[Dict[str, Any]],
                                  relevant_memories: List[Dict[str, Any]] = None,
                                  _metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Evaluate memory retrieval quality."""
        evaluation = {
            'id': str(uuid.uuid4()),
            'query': query,
            'retrieved_count': len(retrieved_memories),
            'timestamp': time.time()
        }
        
        if relevant_memories:
            precision = self._calculate_precision(retrieved_memories, relevant_memories)
            recall = self._calculate_recall(retrieved_memories, relevant_memories)
            evaluation['precision'] = precision
            evaluation['recall'] = recall
            self.memory_metrics['context_precision_scores'].append(precision)
        
        stale_count = sum(1 for m in retrieved_memories if self._is_stale(m))
        evaluation['stale_count'] = stale_count
        
        if stale_count > 0:
            self.memory_metrics['stale_data_usage'] += 1
        
        self.memory_evaluations.append(evaluation)
        self.memory_metrics['total_queries'] += 1
        
        return evaluation
    
    def _calculate_precision(self, retrieved: List[Dict], relevant: List[Dict]) -> float:
        if not retrieved:
            return 0.0
        retrieved_ids = {m.get('id', str(m)) for m in retrieved}
        relevant_ids = {m.get('id', str(m)) for m in relevant}
        return len(retrieved_ids & relevant_ids) / len(retrieved_ids)
    
    def _calculate_recall(self, retrieved: List[Dict], relevant: List[Dict]) -> float:
        if not relevant:
            return 0.0
        retrieved_ids = {m.get('id', str(m)) for m in retrieved}
        relevant_ids = {m.get('id', str(m)) for m in relevant}
        return len(retrieved_ids & relevant_ids) / len(relevant_ids)
    
    def _is_stale(self, memory: Dict[str, Any]) -> bool:
        if 'timestamp' not in memory:
            return False
        age_seconds = time.time() - memory['timestamp']
        return age_seconds > (30 * 24 * 3600)
    
    def record_memory_error(self, error_type: str):
        """Record memory-related errors."""
        if error_type == 'overwrite':
            self.memory_metrics['memory_overwrite_errors'] += 1
    
    def get_memory_metrics(self) -> Dict[str, Any]:
        """Get memory evaluation metrics."""
        metrics = self.memory_metrics
        return {
            'total_queries': metrics['total_queries'],
            'stale_data_rate': metrics['stale_data_usage'] / metrics['total_queries'] if metrics['total_queries'] else 0,
            'avg_precision': statistics.mean(metrics['context_precision_scores']) if metrics['context_precision_scores'] else 0,
            'memory_errors': metrics['memory_overwrite_errors']
        }
    
    def evaluate_retrieval(self, query: str, retrieved_memories: List[Dict[str, Any]],
                          relevant_memories: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Evaluate memory retrieval (alias)."""
        return self.evaluate_memory_retrieval(query, retrieved_memories, relevant_memories)
    
    def record_stale_data_access(self, memory_data: Dict[str, Any] = None, _memory_data: Dict[str, Any] = None):
        """Record access to stale data."""
        # Support both memory_data and _memory_data for compatibility
        self.memory_metrics['stale_data_usage'] += 1
    
    def record_overwrite_error(self):
        """Record a memory overwrite error."""
        self.record_memory_error('overwrite')


class RAGEvaluator:
    """RAG (Retrieval-Augmented Generation) Evaluation system."""
    
    def __init__(self):
        self.rag_evaluations: List[Dict[str, Any]] = []
        self.rag_metrics: Dict[str, Any] = {
            'total_queries': 0,
            'precision_scores': [],
            'recall_scores': [],
            'faithfulness_scores': [],
            'groundedness_scores': []
        }
    
    def evaluate_rag_response(self,
                             query: str,
                             retrieved_docs: List[Dict[str, Any]],
                             generated_answer: str,
                             relevant_docs: List[Dict[str, Any]] = None,
                             _ground_truth_answer: str = None,
                             _metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Evaluate RAG response quality."""
        evaluation = {
            'id': str(uuid.uuid4()),
            'query': query,
            'num_retrieved': len(retrieved_docs),
            'answer_length': len(generated_answer),
            'timestamp': time.time()
        }
        
        if relevant_docs:
            precision = self._calculate_retrieval_precision(retrieved_docs, relevant_docs)
            recall = self._calculate_retrieval_recall(retrieved_docs, relevant_docs)
            evaluation['retrieval_precision'] = precision
            evaluation['retrieval_recall'] = recall
            self.rag_metrics['precision_scores'].append(precision)
            self.rag_metrics['recall_scores'].append(recall)
        
        faithfulness = self._assess_faithfulness(generated_answer, retrieved_docs)
        evaluation['faithfulness'] = faithfulness
        self.rag_metrics['faithfulness_scores'].append(faithfulness)
        
        groundedness = self._assess_groundedness(generated_answer, retrieved_docs)
        evaluation['groundedness'] = groundedness
        self.rag_metrics['groundedness_scores'].append(groundedness)
        
        evaluation['has_citations'] = self._has_citations(generated_answer)
        
        self.rag_evaluations.append(evaluation)
        self.rag_metrics['total_queries'] += 1
        
        return evaluation
    
    def _calculate_retrieval_precision(self, retrieved: List[Dict], relevant: List[Dict]) -> float:
        if not retrieved:
            return 0.0
        retrieved_ids = {str(d.get('id', d)) for d in retrieved}
        relevant_ids = {str(d.get('id', d)) for d in relevant}
        return len(retrieved_ids & relevant_ids) / len(retrieved_ids)
    
    def _calculate_retrieval_recall(self, retrieved: List[Dict], relevant: List[Dict]) -> float:
        if not relevant:
            return 0.0
        retrieved_ids = {str(d.get('id', d)) for d in retrieved}
        relevant_ids = {str(d.get('id', d)) for d in relevant}
        return len(retrieved_ids & relevant_ids) / len(relevant_ids)
    
    def _assess_faithfulness(self, answer: str, docs: List[Dict]) -> float:
        if not docs:
            return 0.0
        answer_tokens = set(answer.lower().split())
        doc_tokens = set()
        for doc in docs:
            content = doc.get('content', str(doc))
            doc_tokens.update(content.lower().split())
        if not doc_tokens:
            return 0.0
        overlap = len(answer_tokens & doc_tokens)
        return overlap / len(answer_tokens) if answer_tokens else 0.0
    
    def _assess_groundedness(self, answer: str, docs: List[Dict]) -> float:
        return self._assess_faithfulness(answer, docs)
    
    def _has_citations(self, answer: str) -> bool:
        citation_patterns = ['[', ']', 'source:', 'reference:', 'according to']
        return any(pattern in answer.lower() for pattern in citation_patterns)
    
    def get_rag_metrics(self) -> Dict[str, Any]:
        """Get RAG evaluation metrics."""
        metrics = self.rag_metrics
        return {
            'total_queries': metrics['total_queries'],
            'avg_retrieval_precision': statistics.mean(metrics['precision_scores']) if metrics['precision_scores'] else 0,
            'avg_retrieval_recall': statistics.mean(metrics['recall_scores']) if metrics['recall_scores'] else 0,
            'avg_faithfulness': statistics.mean(metrics['faithfulness_scores']) if metrics['faithfulness_scores'] else 0,
            'avg_groundedness': statistics.mean(metrics['groundedness_scores']) if metrics['groundedness_scores'] else 0
        }
    
    def evaluate_retrieval(self, query: str, retrieved_docs: List[Dict[str, Any]],
                          relevant_docs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Evaluate retrieval quality."""
        precision = self._calculate_retrieval_precision(retrieved_docs, relevant_docs)
        recall = self._calculate_retrieval_recall(retrieved_docs, relevant_docs)
        return {
            'query': query,
            'precision': precision,
            'recall': recall,
            'f1_score': 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0,
            'num_retrieved': len(retrieved_docs),
            'num_relevant': len(relevant_docs),
            'timestamp': time.time()
        }
    
    def evaluate_faithfulness(self, answer: str, retrieved_docs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Evaluate answer faithfulness."""
        return {
            'answer': answer,
            'faithfulness_score': self._assess_faithfulness(answer, retrieved_docs),
            'num_docs': len(retrieved_docs),
            'timestamp': time.time()
        }
    
    def evaluate_groundedness(self, answer: str, retrieved_docs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Evaluate answer groundedness."""
        return {
            'answer': answer,
            'groundedness_score': self._assess_groundedness(answer, retrieved_docs),
            'num_docs': len(retrieved_docs),
            'timestamp': time.time()
        }
    
    def check_citations(self, answer: str) -> Dict[str, Any]:
        """Check if answer contains citations."""
        return {
            'answer': answer,
            'has_citations': self._has_citations(answer),
            'timestamp': time.time()
        }


__all__ = ['MemoryEvaluator', 'RAGEvaluator']
