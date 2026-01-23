"""
Enterprise Recommendation Engine Module.

ML-based recommendations, collaborative filtering,
content-based filtering, and personalization.

Example:
    # Create recommendation engine
    engine = create_recommendation_engine()
    
    # Record user interactions
    await engine.record_interaction(
        user_id="user_123",
        item_id="product_456",
        interaction_type="purchase",
        weight=5.0,
    )
    
    # Get recommendations
    items = await engine.recommend(
        user_id="user_123",
        limit=10,
    )
    
    # Similar items
    similar = await engine.similar_items(
        item_id="product_456",
        limit=5,
    )
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
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

T = TypeVar('T')

logger = logging.getLogger(__name__)


class RecommendationError(Exception):
    """Recommendation error."""
    pass


class InteractionType(str, Enum):
    """Interaction type."""
    VIEW = "view"
    CLICK = "click"
    ADD_TO_CART = "add_to_cart"
    PURCHASE = "purchase"
    LIKE = "like"
    DISLIKE = "dislike"
    RATING = "rating"
    SHARE = "share"
    BOOKMARK = "bookmark"


class StrategyType(str, Enum):
    """Recommendation strategy."""
    COLLABORATIVE = "collaborative"
    CONTENT_BASED = "content_based"
    HYBRID = "hybrid"
    POPULAR = "popular"
    TRENDING = "trending"
    SIMILAR = "similar"
    PERSONALIZED = "personalized"


class SimilarityMetric(str, Enum):
    """Similarity metric."""
    COSINE = "cosine"
    PEARSON = "pearson"
    JACCARD = "jaccard"
    EUCLIDEAN = "euclidean"


@dataclass
class Item:
    """Recommendable item."""
    id: str = ""
    name: str = ""
    category: str = ""
    tags: List[str] = field(default_factory=list)
    features: Dict[str, Any] = field(default_factory=dict)
    embedding: List[float] = field(default_factory=list)
    popularity_score: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Interaction:
    """User-item interaction."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    item_id: str = ""
    interaction_type: InteractionType = InteractionType.VIEW
    weight: float = 1.0
    context: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class UserProfile:
    """User preference profile."""
    user_id: str = ""
    preferences: Dict[str, float] = field(default_factory=dict)
    category_affinities: Dict[str, float] = field(default_factory=dict)
    tag_affinities: Dict[str, float] = field(default_factory=dict)
    interacted_items: Set[str] = field(default_factory=set)
    last_updated: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Recommendation:
    """Recommendation result."""
    item_id: str = ""
    item: Optional[Item] = None
    score: float = 0.0
    reason: str = ""
    strategy: StrategyType = StrategyType.PERSONALIZED
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RecommendationConfig:
    """Recommendation configuration."""
    default_strategy: StrategyType = StrategyType.HYBRID
    similarity_metric: SimilarityMetric = SimilarityMetric.COSINE
    min_interactions: int = 5
    max_results: int = 100
    recency_weight: float = 0.5
    diversity_factor: float = 0.2
    interaction_weights: Dict[str, float] = field(default_factory=lambda: {
        InteractionType.VIEW.value: 1.0,
        InteractionType.CLICK.value: 2.0,
        InteractionType.ADD_TO_CART.value: 3.0,
        InteractionType.PURCHASE.value: 5.0,
        InteractionType.LIKE.value: 4.0,
        InteractionType.RATING.value: 4.0,
    })


@dataclass
class RecommendationStats:
    """Recommendation statistics."""
    total_recommendations: int = 0
    total_interactions: int = 0
    total_items: int = 0
    total_users: int = 0
    hit_rate: float = 0.0
    by_strategy: Dict[str, int] = field(default_factory=dict)


# Item store
class ItemStore(ABC):
    """Item storage."""
    
    @abstractmethod
    async def save(self, item: Item) -> None:
        """Save item."""
        pass
    
    @abstractmethod
    async def get(self, item_id: str) -> Optional[Item]:
        """Get item."""
        pass
    
    @abstractmethod
    async def get_many(self, item_ids: List[str]) -> List[Item]:
        """Get multiple items."""
        pass
    
    @abstractmethod
    async def list(
        self,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
    ) -> List[Item]:
        """List items."""
        pass
    
    @abstractmethod
    async def search(
        self,
        query: str,
        limit: int = 100,
    ) -> List[Item]:
        """Search items."""
        pass


class InMemoryItemStore(ItemStore):
    """In-memory item store."""
    
    def __init__(self):
        self._items: Dict[str, Item] = {}
    
    async def save(self, item: Item) -> None:
        self._items[item.id] = item
    
    async def get(self, item_id: str) -> Optional[Item]:
        return self._items.get(item_id)
    
    async def get_many(self, item_ids: List[str]) -> List[Item]:
        return [
            self._items[iid]
            for iid in item_ids
            if iid in self._items
        ]
    
    async def list(
        self,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
    ) -> List[Item]:
        items = list(self._items.values())
        
        if category:
            items = [i for i in items if i.category == category]
        
        if tags:
            items = [
                i for i in items
                if any(t in i.tags for t in tags)
            ]
        
        return items[:limit]
    
    async def search(
        self,
        query: str,
        limit: int = 100,
    ) -> List[Item]:
        query_lower = query.lower()
        results = []
        
        for item in self._items.values():
            if query_lower in item.name.lower():
                results.append(item)
            elif any(query_lower in tag.lower() for tag in item.tags):
                results.append(item)
        
        return results[:limit]


# Interaction store
class InteractionStore(ABC):
    """Interaction storage."""
    
    @abstractmethod
    async def save(self, interaction: Interaction) -> None:
        """Save interaction."""
        pass
    
    @abstractmethod
    async def get_user_interactions(
        self,
        user_id: str,
        limit: int = 1000,
    ) -> List[Interaction]:
        """Get user interactions."""
        pass
    
    @abstractmethod
    async def get_item_interactions(
        self,
        item_id: str,
        limit: int = 1000,
    ) -> List[Interaction]:
        """Get item interactions."""
        pass
    
    @abstractmethod
    async def get_user_item_matrix(self) -> Dict[str, Dict[str, float]]:
        """Get user-item matrix."""
        pass


class InMemoryInteractionStore(InteractionStore):
    """In-memory interaction store."""
    
    def __init__(self):
        self._interactions: List[Interaction] = []
        self._by_user: Dict[str, List[Interaction]] = defaultdict(list)
        self._by_item: Dict[str, List[Interaction]] = defaultdict(list)
    
    async def save(self, interaction: Interaction) -> None:
        self._interactions.append(interaction)
        self._by_user[interaction.user_id].append(interaction)
        self._by_item[interaction.item_id].append(interaction)
    
    async def get_user_interactions(
        self,
        user_id: str,
        limit: int = 1000,
    ) -> List[Interaction]:
        interactions = self._by_user.get(user_id, [])
        return sorted(
            interactions,
            key=lambda i: i.timestamp,
            reverse=True,
        )[:limit]
    
    async def get_item_interactions(
        self,
        item_id: str,
        limit: int = 1000,
    ) -> List[Interaction]:
        interactions = self._by_item.get(item_id, [])
        return sorted(
            interactions,
            key=lambda i: i.timestamp,
            reverse=True,
        )[:limit]
    
    async def get_user_item_matrix(self) -> Dict[str, Dict[str, float]]:
        matrix: Dict[str, Dict[str, float]] = defaultdict(dict)
        
        for interaction in self._interactions:
            current = matrix[interaction.user_id].get(interaction.item_id, 0)
            matrix[interaction.user_id][interaction.item_id] = (
                current + interaction.weight
            )
        
        return dict(matrix)


# Recommendation engine
class RecommendationEngine:
    """Recommendation engine."""
    
    def __init__(
        self,
        item_store: Optional[ItemStore] = None,
        interaction_store: Optional[InteractionStore] = None,
        config: Optional[RecommendationConfig] = None,
    ):
        self._items = item_store or InMemoryItemStore()
        self._interactions = interaction_store or InMemoryInteractionStore()
        self._config = config or RecommendationConfig()
        self._user_profiles: Dict[str, UserProfile] = {}
        self._item_similarity: Dict[str, Dict[str, float]] = {}
        self._stats = RecommendationStats()
    
    # Item management
    async def add_item(
        self,
        id: str,
        name: str,
        category: str = "",
        tags: Optional[List[str]] = None,
        features: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Item:
        """Add item."""
        item = Item(
            id=id,
            name=name,
            category=category,
            tags=tags or [],
            features=features or {},
            **kwargs,
        )
        await self._items.save(item)
        self._stats.total_items += 1
        return item
    
    async def get_item(self, item_id: str) -> Optional[Item]:
        """Get item."""
        return await self._items.get(item_id)
    
    # Interaction recording
    async def record_interaction(
        self,
        user_id: str,
        item_id: str,
        interaction_type: Union[InteractionType, str] = InteractionType.VIEW,
        weight: Optional[float] = None,
        context: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Interaction:
        """Record interaction."""
        if isinstance(interaction_type, str):
            interaction_type = InteractionType(interaction_type)
        
        # Get weight from config if not specified
        if weight is None:
            weight = self._config.interaction_weights.get(
                interaction_type.value, 1.0
            )
        
        interaction = Interaction(
            user_id=user_id,
            item_id=item_id,
            interaction_type=interaction_type,
            weight=weight,
            context=context or {},
            **kwargs,
        )
        
        await self._interactions.save(interaction)
        
        # Update user profile
        await self._update_user_profile(user_id, item_id, weight)
        
        # Update item popularity
        item = await self._items.get(item_id)
        if item:
            item.popularity_score += weight
            await self._items.save(item)
        
        self._stats.total_interactions += 1
        
        return interaction
    
    async def _update_user_profile(
        self,
        user_id: str,
        item_id: str,
        weight: float,
    ) -> None:
        """Update user profile."""
        if user_id not in self._user_profiles:
            self._user_profiles[user_id] = UserProfile(user_id=user_id)
            self._stats.total_users += 1
        
        profile = self._user_profiles[user_id]
        profile.interacted_items.add(item_id)
        profile.last_updated = datetime.utcnow()
        
        # Update affinities
        item = await self._items.get(item_id)
        if item:
            if item.category:
                current = profile.category_affinities.get(item.category, 0)
                profile.category_affinities[item.category] = current + weight
            
            for tag in item.tags:
                current = profile.tag_affinities.get(tag, 0)
                profile.tag_affinities[tag] = current + weight
    
    # Recommendations
    async def recommend(
        self,
        user_id: str,
        limit: int = 10,
        strategy: Optional[StrategyType] = None,
        exclude_interacted: bool = True,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Recommendation]:
        """Get recommendations."""
        strategy = strategy or self._config.default_strategy
        
        self._stats.total_recommendations += 1
        self._stats.by_strategy[strategy.value] = (
            self._stats.by_strategy.get(strategy.value, 0) + 1
        )
        
        if strategy == StrategyType.COLLABORATIVE:
            recs = await self._collaborative_recommendations(user_id, limit * 2)
        elif strategy == StrategyType.CONTENT_BASED:
            recs = await self._content_based_recommendations(user_id, limit * 2)
        elif strategy == StrategyType.POPULAR:
            recs = await self._popular_recommendations(limit * 2)
        elif strategy == StrategyType.TRENDING:
            recs = await self._trending_recommendations(limit * 2)
        elif strategy == StrategyType.HYBRID:
            recs = await self._hybrid_recommendations(user_id, limit * 2)
        else:
            recs = await self._personalized_recommendations(user_id, limit * 2)
        
        # Filter out interacted items
        if exclude_interacted:
            profile = self._user_profiles.get(user_id)
            if profile:
                recs = [
                    r for r in recs
                    if r.item_id not in profile.interacted_items
                ]
        
        # Apply filters
        if filters:
            recs = await self._apply_filters(recs, filters)
        
        # Enrich with item data
        for rec in recs:
            if not rec.item:
                rec.item = await self._items.get(rec.item_id)
        
        return recs[:limit]
    
    async def _collaborative_recommendations(
        self,
        user_id: str,
        limit: int,
    ) -> List[Recommendation]:
        """Collaborative filtering recommendations."""
        matrix = await self._interactions.get_user_item_matrix()
        
        if user_id not in matrix:
            return []
        
        user_items = matrix[user_id]
        
        # Find similar users
        user_similarities: List[Tuple[str, float]] = []
        for other_user, other_items in matrix.items():
            if other_user == user_id:
                continue
            
            similarity = self._compute_similarity(user_items, other_items)
            if similarity > 0:
                user_similarities.append((other_user, similarity))
        
        user_similarities.sort(key=lambda x: x[1], reverse=True)
        
        # Get items from similar users
        item_scores: Dict[str, float] = defaultdict(float)
        
        for similar_user, similarity in user_similarities[:50]:
            for item_id, weight in matrix[similar_user].items():
                if item_id not in user_items:
                    item_scores[item_id] += weight * similarity
        
        # Create recommendations
        recs = []
        for item_id, score in sorted(
            item_scores.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:limit]:
            recs.append(Recommendation(
                item_id=item_id,
                score=score,
                strategy=StrategyType.COLLABORATIVE,
                reason="Users with similar preferences liked this",
            ))
        
        return recs
    
    async def _content_based_recommendations(
        self,
        user_id: str,
        limit: int,
    ) -> List[Recommendation]:
        """Content-based recommendations."""
        profile = self._user_profiles.get(user_id)
        if not profile:
            return []
        
        # Get all items
        all_items = await self._items.list(limit=1000)
        
        # Score items based on user profile
        item_scores: List[Tuple[Item, float]] = []
        
        for item in all_items:
            score = 0.0
            
            # Category affinity
            if item.category in profile.category_affinities:
                score += profile.category_affinities[item.category]
            
            # Tag affinities
            for tag in item.tags:
                if tag in profile.tag_affinities:
                    score += profile.tag_affinities[tag]
            
            if score > 0:
                item_scores.append((item, score))
        
        item_scores.sort(key=lambda x: x[1], reverse=True)
        
        recs = []
        for item, score in item_scores[:limit]:
            recs.append(Recommendation(
                item_id=item.id,
                item=item,
                score=score,
                strategy=StrategyType.CONTENT_BASED,
                reason="Matches your interests",
            ))
        
        return recs
    
    async def _popular_recommendations(
        self,
        limit: int,
    ) -> List[Recommendation]:
        """Popular items recommendations."""
        items = await self._items.list(limit=limit * 2)
        items.sort(key=lambda i: i.popularity_score, reverse=True)
        
        recs = []
        for item in items[:limit]:
            recs.append(Recommendation(
                item_id=item.id,
                item=item,
                score=item.popularity_score,
                strategy=StrategyType.POPULAR,
                reason="Popular with other users",
            ))
        
        return recs
    
    async def _trending_recommendations(
        self,
        limit: int,
        window_hours: int = 24,
    ) -> List[Recommendation]:
        """Trending items recommendations."""
        cutoff = datetime.utcnow() - timedelta(hours=window_hours)
        
        # Get recent interactions
        item_scores: Dict[str, float] = defaultdict(float)
        
        matrix = await self._interactions.get_user_item_matrix()
        for user_items in matrix.values():
            for item_id, weight in user_items.items():
                item_scores[item_id] += weight
        
        # Get items
        items = await self._items.get_many(list(item_scores.keys()))
        
        recs = []
        for item in items:
            if item.id in item_scores:
                recs.append(Recommendation(
                    item_id=item.id,
                    item=item,
                    score=item_scores[item.id],
                    strategy=StrategyType.TRENDING,
                    reason="Trending now",
                ))
        
        recs.sort(key=lambda r: r.score, reverse=True)
        return recs[:limit]
    
    async def _hybrid_recommendations(
        self,
        user_id: str,
        limit: int,
    ) -> List[Recommendation]:
        """Hybrid recommendations."""
        # Get recommendations from multiple strategies
        collab = await self._collaborative_recommendations(user_id, limit // 2)
        content = await self._content_based_recommendations(user_id, limit // 2)
        popular = await self._popular_recommendations(limit // 4)
        
        # Merge and deduplicate
        seen: Set[str] = set()
        merged: List[Recommendation] = []
        
        for rec in collab + content + popular:
            if rec.item_id not in seen:
                seen.add(rec.item_id)
                rec.strategy = StrategyType.HYBRID
                merged.append(rec)
        
        return merged[:limit]
    
    async def _personalized_recommendations(
        self,
        user_id: str,
        limit: int,
    ) -> List[Recommendation]:
        """Personalized recommendations."""
        profile = self._user_profiles.get(user_id)
        
        if not profile or len(profile.interacted_items) < self._config.min_interactions:
            return await self._popular_recommendations(limit)
        
        return await self._hybrid_recommendations(user_id, limit)
    
    async def _apply_filters(
        self,
        recs: List[Recommendation],
        filters: Dict[str, Any],
    ) -> List[Recommendation]:
        """Apply filters to recommendations."""
        filtered = []
        
        for rec in recs:
            item = rec.item or await self._items.get(rec.item_id)
            if not item:
                continue
            
            match = True
            
            if "category" in filters and item.category != filters["category"]:
                match = False
            
            if "tags" in filters:
                if not any(t in item.tags for t in filters["tags"]):
                    match = False
            
            if match:
                filtered.append(rec)
        
        return filtered
    
    # Similar items
    async def similar_items(
        self,
        item_id: str,
        limit: int = 10,
    ) -> List[Recommendation]:
        """Get similar items."""
        item = await self._items.get(item_id)
        if not item:
            return []
        
        # Get items with similar features
        all_items = await self._items.list(limit=1000)
        
        similarities: List[Tuple[Item, float]] = []
        
        for other in all_items:
            if other.id == item_id:
                continue
            
            score = 0.0
            
            # Same category
            if other.category == item.category:
                score += 0.5
            
            # Common tags
            common_tags = set(item.tags) & set(other.tags)
            if common_tags:
                score += len(common_tags) / max(len(item.tags), len(other.tags), 1)
            
            # Embedding similarity
            if item.embedding and other.embedding:
                score += self._cosine_similarity(item.embedding, other.embedding)
            
            if score > 0:
                similarities.append((other, score))
        
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        recs = []
        for similar_item, score in similarities[:limit]:
            recs.append(Recommendation(
                item_id=similar_item.id,
                item=similar_item,
                score=score,
                strategy=StrategyType.SIMILAR,
                reason=f"Similar to {item.name}",
            ))
        
        return recs
    
    # Similarity computation
    def _compute_similarity(
        self,
        items1: Dict[str, float],
        items2: Dict[str, float],
    ) -> float:
        """Compute similarity between item sets."""
        if self._config.similarity_metric == SimilarityMetric.JACCARD:
            return self._jaccard_similarity(
                set(items1.keys()),
                set(items2.keys()),
            )
        elif self._config.similarity_metric == SimilarityMetric.COSINE:
            return self._dict_cosine_similarity(items1, items2)
        else:
            return self._jaccard_similarity(
                set(items1.keys()),
                set(items2.keys()),
            )
    
    def _jaccard_similarity(
        self,
        set1: Set[str],
        set2: Set[str],
    ) -> float:
        """Jaccard similarity."""
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        return intersection / union if union > 0 else 0.0
    
    def _cosine_similarity(
        self,
        vec1: List[float],
        vec2: List[float],
    ) -> float:
        """Cosine similarity."""
        if len(vec1) != len(vec2):
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def _dict_cosine_similarity(
        self,
        dict1: Dict[str, float],
        dict2: Dict[str, float],
    ) -> float:
        """Cosine similarity for dicts."""
        common_keys = set(dict1.keys()) & set(dict2.keys())
        
        if not common_keys:
            return 0.0
        
        dot_product = sum(dict1[k] * dict2[k] for k in common_keys)
        norm1 = math.sqrt(sum(v * v for v in dict1.values()))
        norm2 = math.sqrt(sum(v * v for v in dict2.values()))
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    # Stats
    def get_stats(self) -> RecommendationStats:
        """Get statistics."""
        return self._stats


# Factory functions
def create_recommendation_engine(
    config: Optional[RecommendationConfig] = None,
    item_store: Optional[ItemStore] = None,
) -> RecommendationEngine:
    """Create recommendation engine."""
    return RecommendationEngine(
        config=config,
        item_store=item_store,
    )


def create_recommendation_config(
    default_strategy: StrategyType = StrategyType.HYBRID,
    **kwargs,
) -> RecommendationConfig:
    """Create recommendation config."""
    return RecommendationConfig(
        default_strategy=default_strategy,
        **kwargs,
    )


def create_item(
    id: str,
    name: str,
    category: str = "",
    tags: Optional[List[str]] = None,
    **kwargs,
) -> Item:
    """Create item."""
    return Item(
        id=id,
        name=name,
        category=category,
        tags=tags or [],
        **kwargs,
    )


__all__ = [
    # Exceptions
    "RecommendationError",
    # Enums
    "InteractionType",
    "StrategyType",
    "SimilarityMetric",
    # Data classes
    "Item",
    "Interaction",
    "UserProfile",
    "Recommendation",
    "RecommendationConfig",
    "RecommendationStats",
    # Stores
    "ItemStore",
    "InMemoryItemStore",
    "InteractionStore",
    "InMemoryInteractionStore",
    # Engine
    "RecommendationEngine",
    # Factory functions
    "create_recommendation_engine",
    "create_recommendation_config",
    "create_item",
]
