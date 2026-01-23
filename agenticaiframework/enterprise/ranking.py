"""
Enterprise Ranking Module.

Provides relevance scoring, re-ranking, result ordering,
and ranking algorithms for search and retrieval.

Example:
    # Create ranker
    ranker = CrossEncoderRanker(client=openai_client)
    
    # Rank results
    results = await ranker.rank(query="best pizza", documents=[...])
    
    # Rerank existing results
    reranked = await ranker.rerank(query, search_results)
"""

from __future__ import annotations

import asyncio
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

logger = logging.getLogger(__name__)

T = TypeVar('T')


class RankingError(Exception):
    """Ranking error."""
    pass


class RankingStrategy(str, Enum):
    """Ranking strategies."""
    RELEVANCE = "relevance"       # By relevance score
    RECENCY = "recency"           # By timestamp
    POPULARITY = "popularity"     # By engagement metrics
    DIVERSITY = "diversity"       # Maximize diversity
    PERSONALIZED = "personalized" # User-specific
    HYBRID = "hybrid"             # Combination


class AggregationMethod(str, Enum):
    """Score aggregation methods."""
    SUM = "sum"
    MEAN = "mean"
    MAX = "max"
    MIN = "min"
    WEIGHTED = "weighted"
    RECIPROCAL_RANK = "rrf"


@dataclass
class RankedItem(Generic[T]):
    """A ranked item with score."""
    item: T
    score: float
    rank: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __lt__(self, other: 'RankedItem') -> bool:
        return self.score < other.score
    
    def __eq__(self, other: Any) -> bool:
        if isinstance(other, RankedItem):
            return self.score == other.score
        return False


@dataclass
class RankingResult(Generic[T]):
    """Result of ranking operation."""
    items: List[RankedItem[T]]
    query: Optional[str] = None
    strategy: RankingStrategy = RankingStrategy.RELEVANCE
    duration_ms: float = 0.0
    
    @property
    def ranked_items(self) -> List[T]:
        """Get items in ranked order."""
        return [item.item for item in self.items]
    
    @property
    def scores(self) -> List[float]:
        """Get scores."""
        return [item.score for item in self.items]
    
    def top_k(self, k: int) -> List[T]:
        """Get top k items."""
        return [item.item for item in self.items[:k]]
    
    def __len__(self) -> int:
        return len(self.items)
    
    def __iter__(self):
        return iter(self.items)


@dataclass
class ScoringWeights:
    """Weights for hybrid scoring."""
    relevance: float = 1.0
    recency: float = 0.0
    popularity: float = 0.0
    personalization: float = 0.0
    
    def normalize(self) -> 'ScoringWeights':
        """Normalize weights to sum to 1."""
        total = self.relevance + self.recency + self.popularity + self.personalization
        if total == 0:
            return self
        return ScoringWeights(
            relevance=self.relevance / total,
            recency=self.recency / total,
            popularity=self.popularity / total,
            personalization=self.personalization / total,
        )


class Ranker(ABC, Generic[T]):
    """Abstract ranker interface."""
    
    @abstractmethod
    async def rank(
        self,
        items: List[T],
        query: Optional[str] = None,
        **kwargs: Any,
    ) -> RankingResult[T]:
        """Rank items."""
        pass


class ScoreBasedRanker(Ranker[T]):
    """Ranker that sorts by existing scores."""
    
    def __init__(
        self,
        score_field: str = "score",
        descending: bool = True,
    ):
        self._score_field = score_field
        self._descending = descending
    
    async def rank(
        self,
        items: List[T],
        query: Optional[str] = None,
        **kwargs: Any,
    ) -> RankingResult[T]:
        """Rank by existing scores."""
        import time
        start = time.time()
        
        ranked = []
        for item in items:
            if isinstance(item, dict):
                score = item.get(self._score_field, 0.0)
            elif hasattr(item, self._score_field):
                score = getattr(item, self._score_field, 0.0)
            else:
                score = 0.0
            
            ranked.append(RankedItem(item=item, score=score))
        
        # Sort
        ranked.sort(key=lambda x: x.score, reverse=self._descending)
        
        # Assign ranks
        for i, item in enumerate(ranked):
            item.rank = i + 1
        
        return RankingResult(
            items=ranked,
            query=query,
            strategy=RankingStrategy.RELEVANCE,
            duration_ms=(time.time() - start) * 1000,
        )


class LLMRanker(Ranker[T]):
    """LLM-based ranker for semantic relevance."""
    
    def __init__(
        self,
        client: Any,
        model: Optional[str] = None,
        content_field: str = "content",
    ):
        self._client = client
        self._model = model
        self._content_field = content_field
    
    def _get_content(self, item: T) -> str:
        """Extract content from item."""
        if isinstance(item, str):
            return item
        if isinstance(item, dict):
            return item.get(self._content_field, str(item))
        if hasattr(item, self._content_field):
            return getattr(item, self._content_field)
        return str(item)
    
    async def rank(
        self,
        items: List[T],
        query: Optional[str] = None,
        **kwargs: Any,
    ) -> RankingResult[T]:
        """Rank using LLM."""
        import time
        import json
        start = time.time()
        
        if not query:
            raise RankingError("Query required for LLM ranking")
        
        # Build prompt
        docs = []
        for i, item in enumerate(items):
            content = self._get_content(item)
            docs.append(f"[{i}] {content[:500]}")
        
        docs_str = "\n\n".join(docs)
        
        prompt = f"""Given the query and documents, rank the documents by relevance.
Return a JSON array of document indices in order of relevance (most relevant first).

Query: {query}

Documents:
{docs_str}

Return ONLY a JSON array like [2, 0, 1, 3] (no explanation):"""
        
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        
        try:
            content = response.choices[0].message.content
            import re
            match = re.search(r'\[[\d,\s]+\]', content)
            if match:
                order = json.loads(match.group())
                
                # Build ranked results
                ranked = []
                for rank, idx in enumerate(order):
                    if 0 <= idx < len(items):
                        score = 1.0 - (rank / len(order))  # Higher rank = higher score
                        ranked.append(RankedItem(
                            item=items[idx],
                            score=score,
                            rank=rank + 1,
                        ))
                
                # Add any items not in ranking
                ranked_indices = set(order)
                for i, item in enumerate(items):
                    if i not in ranked_indices:
                        ranked.append(RankedItem(
                            item=item,
                            score=0.0,
                            rank=len(ranked) + 1,
                        ))
                
                return RankingResult(
                    items=ranked,
                    query=query,
                    strategy=RankingStrategy.RELEVANCE,
                    duration_ms=(time.time() - start) * 1000,
                )
        except Exception as e:
            logger.error(f"Failed to parse LLM ranking: {e}")
        
        # Fallback to original order
        return await ScoreBasedRanker().rank(items, query)


class ReciprocalRankFusion(Ranker[T]):
    """Reciprocal Rank Fusion for combining multiple rankings."""
    
    def __init__(
        self,
        rankers: List[Ranker[T]],
        k: int = 60,
    ):
        self._rankers = rankers
        self._k = k
    
    async def rank(
        self,
        items: List[T],
        query: Optional[str] = None,
        **kwargs: Any,
    ) -> RankingResult[T]:
        """Combine rankings using RRF."""
        import time
        start = time.time()
        
        # Get rankings from all rankers
        rankings = await asyncio.gather(*[
            ranker.rank(items, query, **kwargs)
            for ranker in self._rankers
        ])
        
        # Calculate RRF scores
        scores: Dict[int, float] = {}  # item index -> score
        
        for ranking in rankings:
            for ranked_item in ranking.items:
                # Find original index
                for i, item in enumerate(items):
                    if item == ranked_item.item:
                        rrf_score = 1.0 / (self._k + ranked_item.rank)
                        scores[i] = scores.get(i, 0) + rrf_score
                        break
        
        # Sort by combined score
        sorted_indices = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
        
        ranked = []
        for rank, idx in enumerate(sorted_indices):
            ranked.append(RankedItem(
                item=items[idx],
                score=scores[idx],
                rank=rank + 1,
            ))
        
        return RankingResult(
            items=ranked,
            query=query,
            strategy=RankingStrategy.HYBRID,
            duration_ms=(time.time() - start) * 1000,
        )


class DiversityRanker(Ranker[T]):
    """Ranker that maximizes result diversity."""
    
    def __init__(
        self,
        similarity_fn: Callable[[T, T], float],
        diversity_weight: float = 0.3,
        base_ranker: Optional[Ranker[T]] = None,
    ):
        self._similarity_fn = similarity_fn
        self._diversity_weight = diversity_weight
        self._base_ranker = base_ranker or ScoreBasedRanker()
    
    async def rank(
        self,
        items: List[T],
        query: Optional[str] = None,
        **kwargs: Any,
    ) -> RankingResult[T]:
        """Rank with diversity consideration (MMR-like)."""
        import time
        start = time.time()
        
        # Get base ranking
        base_result = await self._base_ranker.rank(items, query, **kwargs)
        
        if len(items) <= 1:
            return base_result
        
        # MMR-style reranking
        selected = []
        remaining = list(range(len(base_result.items)))
        
        # Select first item (highest relevance)
        first_idx = remaining.pop(0)
        selected.append(first_idx)
        
        # Iteratively select remaining items
        while remaining:
            best_idx = None
            best_score = float('-inf')
            
            for idx in remaining:
                item = base_result.items[idx]
                relevance = item.score
                
                # Calculate max similarity to selected items
                max_similarity = 0.0
                for sel_idx in selected:
                    sel_item = base_result.items[sel_idx].item
                    
                    if asyncio.iscoroutinefunction(self._similarity_fn):
                        sim = await self._similarity_fn(item.item, sel_item)
                    else:
                        sim = self._similarity_fn(item.item, sel_item)
                    
                    max_similarity = max(max_similarity, sim)
                
                # MMR score
                mmr_score = (1 - self._diversity_weight) * relevance - self._diversity_weight * max_similarity
                
                if mmr_score > best_score:
                    best_score = mmr_score
                    best_idx = idx
            
            if best_idx is not None:
                remaining.remove(best_idx)
                selected.append(best_idx)
        
        # Build result
        ranked = []
        for rank, idx in enumerate(selected):
            orig_item = base_result.items[idx]
            ranked.append(RankedItem(
                item=orig_item.item,
                score=orig_item.score,
                rank=rank + 1,
            ))
        
        return RankingResult(
            items=ranked,
            query=query,
            strategy=RankingStrategy.DIVERSITY,
            duration_ms=(time.time() - start) * 1000,
        )


class RecencyRanker(Ranker[T]):
    """Ranker that considers recency."""
    
    def __init__(
        self,
        timestamp_field: str = "timestamp",
        decay_rate: float = 0.1,
        base_ranker: Optional[Ranker[T]] = None,
    ):
        self._timestamp_field = timestamp_field
        self._decay_rate = decay_rate
        self._base_ranker = base_ranker or ScoreBasedRanker()
    
    def _get_timestamp(self, item: T) -> datetime:
        """Extract timestamp from item."""
        if isinstance(item, dict):
            ts = item.get(self._timestamp_field)
        elif hasattr(item, self._timestamp_field):
            ts = getattr(item, self._timestamp_field)
        else:
            ts = None
        
        if isinstance(ts, datetime):
            return ts
        if isinstance(ts, str):
            return datetime.fromisoformat(ts)
        
        return datetime.now()
    
    async def rank(
        self,
        items: List[T],
        query: Optional[str] = None,
        **kwargs: Any,
    ) -> RankingResult[T]:
        """Rank with recency decay."""
        import time
        start = time.time()
        
        # Get base ranking
        base_result = await self._base_ranker.rank(items, query, **kwargs)
        
        now = datetime.now()
        ranked = []
        
        for ranked_item in base_result.items:
            ts = self._get_timestamp(ranked_item.item)
            age_hours = (now - ts).total_seconds() / 3600
            
            # Exponential decay
            recency_score = math.exp(-self._decay_rate * age_hours)
            
            # Combine scores
            combined_score = ranked_item.score * recency_score
            
            ranked.append(RankedItem(
                item=ranked_item.item,
                score=combined_score,
                metadata={"recency_score": recency_score},
            ))
        
        # Re-sort
        ranked.sort(key=lambda x: x.score, reverse=True)
        
        for i, item in enumerate(ranked):
            item.rank = i + 1
        
        return RankingResult(
            items=ranked,
            query=query,
            strategy=RankingStrategy.RECENCY,
            duration_ms=(time.time() - start) * 1000,
        )


class WeightedRanker(Ranker[T]):
    """Ranker with weighted scoring."""
    
    def __init__(
        self,
        scorers: Dict[str, Callable[[T, Optional[str]], float]],
        weights: Dict[str, float],
    ):
        self._scorers = scorers
        self._weights = weights
    
    async def rank(
        self,
        items: List[T],
        query: Optional[str] = None,
        **kwargs: Any,
    ) -> RankingResult[T]:
        """Rank using weighted scores."""
        import time
        start = time.time()
        
        ranked = []
        
        for item in items:
            scores = {}
            total_score = 0.0
            total_weight = 0.0
            
            for name, scorer in self._scorers.items():
                weight = self._weights.get(name, 1.0)
                
                if asyncio.iscoroutinefunction(scorer):
                    score = await scorer(item, query)
                else:
                    score = scorer(item, query)
                
                scores[name] = score
                total_score += score * weight
                total_weight += weight
            
            if total_weight > 0:
                final_score = total_score / total_weight
            else:
                final_score = 0.0
            
            ranked.append(RankedItem(
                item=item,
                score=final_score,
                metadata={"component_scores": scores},
            ))
        
        # Sort
        ranked.sort(key=lambda x: x.score, reverse=True)
        
        for i, item in enumerate(ranked):
            item.rank = i + 1
        
        return RankingResult(
            items=ranked,
            query=query,
            strategy=RankingStrategy.HYBRID,
            duration_ms=(time.time() - start) * 1000,
        )


class ReRanker:
    """
    Re-ranker for post-retrieval ranking.
    """
    
    def __init__(
        self,
        ranker: Ranker,
        top_k: Optional[int] = None,
    ):
        self._ranker = ranker
        self._top_k = top_k
    
    async def rerank(
        self,
        query: str,
        items: List[Any],
        k: Optional[int] = None,
    ) -> List[Any]:
        """Re-rank items and return top k."""
        result = await self._ranker.rank(items, query)
        
        k = k or self._top_k or len(items)
        return result.top_k(k)


# Decorator
def ranked(
    ranker: Ranker,
    k: Optional[int] = None,
) -> Callable:
    """
    Decorator to rank function results.
    
    Example:
        @ranked(ranker, k=10)
        async def search(query: str) -> List[Document]:
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(query: str, *args: Any, **kwargs: Any) -> RankingResult:
            items = await func(query, *args, **kwargs)
            result = await ranker.rank(items, query)
            
            if k:
                result.items = result.items[:k]
            
            return result
        
        return wrapper
    
    return decorator


# Factory functions
def create_ranker(
    strategy: str = "score",
    llm_client: Optional[Any] = None,
    model: Optional[str] = None,
    **kwargs: Any,
) -> Ranker:
    """
    Factory function to create a ranker.
    
    Args:
        strategy: Ranking strategy
        llm_client: LLM client for semantic ranking
        model: Model name
    """
    if strategy == "score":
        return ScoreBasedRanker(**kwargs)
    elif strategy == "llm":
        if not llm_client:
            raise ValueError("LLM client required for LLM ranker")
        return LLMRanker(llm_client, model, **kwargs)
    elif strategy == "recency":
        return RecencyRanker(**kwargs)
    else:
        return ScoreBasedRanker(**kwargs)


__all__ = [
    # Exceptions
    "RankingError",
    # Enums
    "RankingStrategy",
    "AggregationMethod",
    # Data classes
    "RankedItem",
    "RankingResult",
    "ScoringWeights",
    # Rankers
    "Ranker",
    "ScoreBasedRanker",
    "LLMRanker",
    "ReciprocalRankFusion",
    "DiversityRanker",
    "RecencyRanker",
    "WeightedRanker",
    # Re-ranker
    "ReRanker",
    # Decorators
    "ranked",
    # Factory
    "create_ranker",
]
