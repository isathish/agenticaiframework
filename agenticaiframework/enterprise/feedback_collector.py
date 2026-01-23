"""
Enterprise Feedback Collector Module.

User feedback, ratings, sentiment analysis,
categorization, and feedback management.

Example:
    # Create feedback collector
    feedback = create_feedback_collector()
    
    # Submit feedback
    entry = await feedback.submit(
        user_id="user_123",
        type=FeedbackType.SUGGESTION,
        title="Feature Request",
        message="Please add dark mode!",
        rating=4,
    )
    
    # Get feedback analysis
    analysis = await feedback.analyze(entry.id)
    
    # Get insights
    insights = await feedback.get_insights(period_days=30)
"""

from __future__ import annotations

import logging
import re
import uuid
from abc import ABC, abstractmethod
from collections import Counter, defaultdict
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


class FeedbackError(Exception):
    """Feedback error."""
    pass


class FeedbackNotFoundError(FeedbackError):
    """Feedback not found."""
    pass


class FeedbackType(str, Enum):
    """Feedback type."""
    BUG = "bug"
    SUGGESTION = "suggestion"
    COMPLAINT = "complaint"
    PRAISE = "praise"
    QUESTION = "question"
    OTHER = "other"


class FeedbackStatus(str, Enum):
    """Feedback status."""
    NEW = "new"
    REVIEWED = "reviewed"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"
    ARCHIVED = "archived"


class Priority(str, Enum):
    """Priority level."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Sentiment(str, Enum):
    """Sentiment classification."""
    VERY_NEGATIVE = "very_negative"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    POSITIVE = "positive"
    VERY_POSITIVE = "very_positive"


@dataclass
class Category:
    """Feedback category."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    parent_id: Optional[str] = None
    color: str = "#3B82F6"
    icon: str = ""


@dataclass
class FeedbackEntry:
    """Feedback entry."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    type: FeedbackType = FeedbackType.OTHER
    status: FeedbackStatus = FeedbackStatus.NEW
    priority: Priority = Priority.MEDIUM
    title: str = ""
    message: str = ""
    rating: Optional[int] = None  # 1-5
    sentiment: Optional[Sentiment] = None
    sentiment_score: float = 0.0
    categories: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    source: str = ""  # web, mobile, email, etc.
    page_url: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    attachments: List[str] = field(default_factory=list)
    assigned_to: Optional[str] = None
    resolution: str = ""
    internal_notes: List[str] = field(default_factory=list)
    response: str = ""
    responded_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class FeedbackFilter:
    """Feedback filter."""
    types: List[FeedbackType] = field(default_factory=list)
    statuses: List[FeedbackStatus] = field(default_factory=list)
    priorities: List[Priority] = field(default_factory=list)
    sentiments: List[Sentiment] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    user_id: Optional[str] = None
    assigned_to: Optional[str] = None
    rating_min: Optional[int] = None
    rating_max: Optional[int] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    source: Optional[str] = None
    search_query: Optional[str] = None


@dataclass
class SentimentAnalysis:
    """Sentiment analysis result."""
    sentiment: Sentiment = Sentiment.NEUTRAL
    score: float = 0.0
    confidence: float = 0.0
    keywords: List[str] = field(default_factory=list)
    positive_phrases: List[str] = field(default_factory=list)
    negative_phrases: List[str] = field(default_factory=list)


@dataclass
class FeedbackInsights:
    """Feedback insights."""
    total_count: int = 0
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    by_type: Dict[str, int] = field(default_factory=dict)
    by_status: Dict[str, int] = field(default_factory=dict)
    by_priority: Dict[str, int] = field(default_factory=dict)
    by_sentiment: Dict[str, int] = field(default_factory=dict)
    by_category: Dict[str, int] = field(default_factory=dict)
    by_source: Dict[str, int] = field(default_factory=dict)
    average_rating: float = 0.0
    average_sentiment_score: float = 0.0
    resolution_rate: float = 0.0
    average_resolution_time_hours: float = 0.0
    trend: Dict[str, int] = field(default_factory=dict)  # date -> count
    top_tags: List[Tuple[str, int]] = field(default_factory=list)
    top_keywords: List[Tuple[str, int]] = field(default_factory=list)


@dataclass
class FeedbackStats:
    """Feedback statistics."""
    total_entries: int = 0
    open_entries: int = 0
    resolved_entries: int = 0


# Feedback store
class FeedbackStore(ABC):
    """Feedback storage."""
    
    @abstractmethod
    async def save(self, entry: FeedbackEntry) -> None:
        pass
    
    @abstractmethod
    async def get(self, entry_id: str) -> Optional[FeedbackEntry]:
        pass
    
    @abstractmethod
    async def query(self, filter: FeedbackFilter) -> List[FeedbackEntry]:
        pass
    
    @abstractmethod
    async def delete(self, entry_id: str) -> bool:
        pass


class InMemoryFeedbackStore(FeedbackStore):
    """In-memory feedback store."""
    
    def __init__(self):
        self._entries: Dict[str, FeedbackEntry] = {}
    
    async def save(self, entry: FeedbackEntry) -> None:
        entry.updated_at = datetime.utcnow()
        self._entries[entry.id] = entry
    
    async def get(self, entry_id: str) -> Optional[FeedbackEntry]:
        return self._entries.get(entry_id)
    
    async def query(self, filter: FeedbackFilter) -> List[FeedbackEntry]:
        results = list(self._entries.values())
        
        if filter.types:
            results = [e for e in results if e.type in filter.types]
        
        if filter.statuses:
            results = [e for e in results if e.status in filter.statuses]
        
        if filter.priorities:
            results = [e for e in results if e.priority in filter.priorities]
        
        if filter.sentiments:
            results = [e for e in results if e.sentiment in filter.sentiments]
        
        if filter.categories:
            results = [e for e in results if any(c in filter.categories for c in e.categories)]
        
        if filter.tags:
            results = [e for e in results if any(t in filter.tags for t in e.tags)]
        
        if filter.user_id:
            results = [e for e in results if e.user_id == filter.user_id]
        
        if filter.assigned_to:
            results = [e for e in results if e.assigned_to == filter.assigned_to]
        
        if filter.rating_min is not None:
            results = [e for e in results if e.rating and e.rating >= filter.rating_min]
        
        if filter.rating_max is not None:
            results = [e for e in results if e.rating and e.rating <= filter.rating_max]
        
        if filter.start_date:
            results = [e for e in results if e.created_at >= filter.start_date]
        
        if filter.end_date:
            results = [e for e in results if e.created_at <= filter.end_date]
        
        if filter.source:
            results = [e for e in results if e.source == filter.source]
        
        if filter.search_query:
            query = filter.search_query.lower()
            results = [
                e for e in results
                if query in e.title.lower() or query in e.message.lower()
            ]
        
        return sorted(results, key=lambda e: e.created_at, reverse=True)
    
    async def delete(self, entry_id: str) -> bool:
        return self._entries.pop(entry_id, None) is not None


# Sentiment analyzer
class SentimentAnalyzer:
    """Simple sentiment analyzer."""
    
    # Word lists for sentiment
    POSITIVE_WORDS = {
        "good", "great", "excellent", "amazing", "awesome", "fantastic",
        "love", "like", "best", "wonderful", "helpful", "perfect",
        "thank", "thanks", "appreciate", "happy", "satisfied", "easy",
        "fast", "quick", "intuitive", "beautiful", "nice", "cool",
    }
    
    NEGATIVE_WORDS = {
        "bad", "terrible", "horrible", "awful", "poor", "worst",
        "hate", "dislike", "broken", "bug", "error", "crash",
        "slow", "difficult", "confusing", "frustrating", "annoying",
        "useless", "disappointed", "fail", "problem", "issue", "wrong",
    }
    
    INTENSIFIERS = {"very", "extremely", "really", "absolutely", "totally"}
    NEGATORS = {"not", "no", "never", "none", "don't", "doesn't", "didn't"}
    
    def analyze(self, text: str) -> SentimentAnalysis:
        """Analyze sentiment."""
        words = re.findall(r'\b\w+\b', text.lower())
        
        positive_count = 0
        negative_count = 0
        positive_phrases = []
        negative_phrases = []
        keywords = []
        
        negated = False
        intensified = False
        
        for i, word in enumerate(words):
            if word in self.NEGATORS:
                negated = True
                continue
            
            if word in self.INTENSIFIERS:
                intensified = True
                continue
            
            multiplier = 1.5 if intensified else 1.0
            
            if word in self.POSITIVE_WORDS:
                if negated:
                    negative_count += multiplier
                    negative_phrases.append(word)
                else:
                    positive_count += multiplier
                    positive_phrases.append(word)
                keywords.append(word)
            
            elif word in self.NEGATIVE_WORDS:
                if negated:
                    positive_count += multiplier
                    positive_phrases.append(word)
                else:
                    negative_count += multiplier
                    negative_phrases.append(word)
                keywords.append(word)
            
            negated = False
            intensified = False
        
        # Calculate score (-1 to 1)
        total = positive_count + negative_count
        if total > 0:
            score = (positive_count - negative_count) / total
        else:
            score = 0.0
        
        # Determine sentiment
        if score >= 0.5:
            sentiment = Sentiment.VERY_POSITIVE
        elif score >= 0.2:
            sentiment = Sentiment.POSITIVE
        elif score <= -0.5:
            sentiment = Sentiment.VERY_NEGATIVE
        elif score <= -0.2:
            sentiment = Sentiment.NEGATIVE
        else:
            sentiment = Sentiment.NEUTRAL
        
        # Confidence based on keyword count
        confidence = min(1.0, total / 5)
        
        return SentimentAnalysis(
            sentiment=sentiment,
            score=score,
            confidence=confidence,
            keywords=list(set(keywords)),
            positive_phrases=list(set(positive_phrases)),
            negative_phrases=list(set(negative_phrases)),
        )


# Feedback collector
class FeedbackCollector:
    """Feedback collector."""
    
    def __init__(
        self,
        store: Optional[FeedbackStore] = None,
        analyzer: Optional[SentimentAnalyzer] = None,
    ):
        self._store = store or InMemoryFeedbackStore()
        self._analyzer = analyzer or SentimentAnalyzer()
        self._categories: Dict[str, Category] = {}
        self._stats = FeedbackStats()
    
    async def submit(
        self,
        user_id: str,
        message: str,
        type: FeedbackType = FeedbackType.OTHER,
        title: str = "",
        rating: Optional[int] = None,
        source: str = "",
        **kwargs,
    ) -> FeedbackEntry:
        """Submit feedback."""
        entry = FeedbackEntry(
            user_id=user_id,
            type=type,
            title=title or message[:50],
            message=message,
            rating=rating,
            source=source,
            **kwargs,
        )
        
        # Auto-analyze sentiment
        analysis = self._analyzer.analyze(message)
        entry.sentiment = analysis.sentiment
        entry.sentiment_score = analysis.score
        
        # Auto-categorize
        entry.tags.extend(analysis.keywords)
        
        # Set priority based on type and sentiment
        if type == FeedbackType.BUG and entry.sentiment in (Sentiment.VERY_NEGATIVE, Sentiment.NEGATIVE):
            entry.priority = Priority.HIGH
        elif type == FeedbackType.COMPLAINT:
            entry.priority = Priority.HIGH
        
        await self._store.save(entry)
        
        self._stats.total_entries += 1
        self._stats.open_entries += 1
        
        logger.info(f"Feedback submitted: {entry.title}")
        
        return entry
    
    async def get(self, entry_id: str) -> Optional[FeedbackEntry]:
        """Get feedback entry."""
        return await self._store.get(entry_id)
    
    async def update(
        self,
        entry_id: str,
        **updates,
    ) -> Optional[FeedbackEntry]:
        """Update feedback entry."""
        entry = await self._store.get(entry_id)
        if not entry:
            return None
        
        old_status = entry.status
        
        for key, value in updates.items():
            if hasattr(entry, key):
                setattr(entry, key, value)
        
        # Track status changes
        if entry.status == FeedbackStatus.RESOLVED and old_status != FeedbackStatus.RESOLVED:
            entry.resolved_at = datetime.utcnow()
            self._stats.open_entries -= 1
            self._stats.resolved_entries += 1
        
        await self._store.save(entry)
        
        return entry
    
    async def respond(
        self,
        entry_id: str,
        response: str,
        close: bool = False,
    ) -> Optional[FeedbackEntry]:
        """Respond to feedback."""
        entry = await self._store.get(entry_id)
        if not entry:
            return None
        
        entry.response = response
        entry.responded_at = datetime.utcnow()
        entry.status = FeedbackStatus.RESOLVED if close else FeedbackStatus.REVIEWED
        
        if close:
            entry.resolved_at = datetime.utcnow()
        
        await self._store.save(entry)
        
        return entry
    
    async def assign(
        self,
        entry_id: str,
        assigned_to: str,
    ) -> Optional[FeedbackEntry]:
        """Assign feedback."""
        return await self.update(entry_id, assigned_to=assigned_to, status=FeedbackStatus.IN_PROGRESS)
    
    async def add_note(
        self,
        entry_id: str,
        note: str,
    ) -> Optional[FeedbackEntry]:
        """Add internal note."""
        entry = await self._store.get(entry_id)
        if not entry:
            return None
        
        entry.internal_notes.append(f"[{datetime.utcnow().isoformat()}] {note}")
        
        await self._store.save(entry)
        
        return entry
    
    async def search(
        self,
        filter: Optional[FeedbackFilter] = None,
        **kwargs,
    ) -> List[FeedbackEntry]:
        """Search feedback."""
        if not filter:
            filter = FeedbackFilter(**kwargs)
        
        return await self._store.query(filter)
    
    async def analyze(self, entry_id: str) -> Optional[SentimentAnalysis]:
        """Analyze feedback sentiment."""
        entry = await self._store.get(entry_id)
        if not entry:
            return None
        
        return self._analyzer.analyze(entry.message)
    
    async def get_insights(
        self,
        period_days: int = 30,
        filter: Optional[FeedbackFilter] = None,
    ) -> FeedbackInsights:
        """Get feedback insights."""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=period_days)
        
        if not filter:
            filter = FeedbackFilter()
        
        filter.start_date = start_date
        filter.end_date = end_date
        
        entries = await self._store.query(filter)
        
        insights = FeedbackInsights(
            total_count=len(entries),
            period_start=start_date,
            period_end=end_date,
        )
        
        if not entries:
            return insights
        
        # Aggregate by dimensions
        for entry in entries:
            insights.by_type[entry.type.value] = insights.by_type.get(entry.type.value, 0) + 1
            insights.by_status[entry.status.value] = insights.by_status.get(entry.status.value, 0) + 1
            insights.by_priority[entry.priority.value] = insights.by_priority.get(entry.priority.value, 0) + 1
            
            if entry.sentiment:
                insights.by_sentiment[entry.sentiment.value] = insights.by_sentiment.get(entry.sentiment.value, 0) + 1
            
            for cat in entry.categories:
                insights.by_category[cat] = insights.by_category.get(cat, 0) + 1
            
            if entry.source:
                insights.by_source[entry.source] = insights.by_source.get(entry.source, 0) + 1
            
            date_key = entry.created_at.strftime("%Y-%m-%d")
            insights.trend[date_key] = insights.trend.get(date_key, 0) + 1
        
        # Averages
        ratings = [e.rating for e in entries if e.rating is not None]
        if ratings:
            insights.average_rating = sum(ratings) / len(ratings)
        
        sentiments = [e.sentiment_score for e in entries]
        insights.average_sentiment_score = sum(sentiments) / len(sentiments)
        
        # Resolution metrics
        resolved = [e for e in entries if e.status == FeedbackStatus.RESOLVED]
        insights.resolution_rate = len(resolved) / len(entries) if entries else 0
        
        resolution_times = []
        for e in resolved:
            if e.resolved_at:
                hours = (e.resolved_at - e.created_at).total_seconds() / 3600
                resolution_times.append(hours)
        
        if resolution_times:
            insights.average_resolution_time_hours = sum(resolution_times) / len(resolution_times)
        
        # Top tags
        tag_counter = Counter()
        keyword_counter = Counter()
        
        for entry in entries:
            for tag in entry.tags:
                tag_counter[tag] += 1
                keyword_counter[tag] += 1
        
        insights.top_tags = tag_counter.most_common(10)
        insights.top_keywords = keyword_counter.most_common(20)
        
        return insights
    
    # Category management
    def add_category(self, category: Category) -> None:
        """Add category."""
        self._categories[category.id] = category
    
    def get_categories(self) -> List[Category]:
        """Get categories."""
        return list(self._categories.values())
    
    def get_stats(self) -> FeedbackStats:
        """Get statistics."""
        return self._stats


# Factory functions
def create_feedback_collector() -> FeedbackCollector:
    """Create feedback collector."""
    return FeedbackCollector()


def create_feedback_entry(
    user_id: str,
    message: str,
    **kwargs,
) -> FeedbackEntry:
    """Create feedback entry."""
    return FeedbackEntry(user_id=user_id, message=message, **kwargs)


def create_category(
    name: str,
    **kwargs,
) -> Category:
    """Create category."""
    return Category(name=name, **kwargs)


__all__ = [
    # Exceptions
    "FeedbackError",
    "FeedbackNotFoundError",
    # Enums
    "FeedbackType",
    "FeedbackStatus",
    "Priority",
    "Sentiment",
    # Data classes
    "Category",
    "FeedbackEntry",
    "FeedbackFilter",
    "SentimentAnalysis",
    "FeedbackInsights",
    "FeedbackStats",
    # Stores
    "FeedbackStore",
    "InMemoryFeedbackStore",
    # Analyzer
    "SentimentAnalyzer",
    # Collector
    "FeedbackCollector",
    # Factory functions
    "create_feedback_collector",
    "create_feedback_entry",
    "create_category",
]
