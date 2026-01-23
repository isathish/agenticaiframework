"""
Enterprise Analyzer Module.

Provides text analysis, sentiment detection, intent classification,
entity extraction, and content categorization for agents.

Example:
    # Analyze text
    analyzer = TextAnalyzer()
    result = await analyzer.analyze("I love this product!")
    print(result.sentiment)  # positive
    
    # Intent classification
    intent = await analyzer.classify_intent("Book a flight to NYC")
    print(intent.label)  # booking
    
    # Entity extraction
    entities = await analyzer.extract_entities("John works at Google")
"""

from __future__ import annotations

import asyncio
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Pattern,
    Set,
    Tuple,
    Union,
)
from datetime import datetime
from functools import wraps
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class AnalysisError(Exception):
    """Analysis error."""
    pass


class Sentiment(str, Enum):
    """Sentiment categories."""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    MIXED = "mixed"


class EntityType(str, Enum):
    """Entity types for NER."""
    PERSON = "PERSON"
    ORGANIZATION = "ORG"
    LOCATION = "LOC"
    DATE = "DATE"
    TIME = "TIME"
    MONEY = "MONEY"
    PERCENT = "PERCENT"
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    URL = "URL"
    PRODUCT = "PRODUCT"
    EVENT = "EVENT"


class ContentCategory(str, Enum):
    """Content categories."""
    QUESTION = "question"
    STATEMENT = "statement"
    COMMAND = "command"
    GREETING = "greeting"
    FAREWELL = "farewell"
    COMPLAINT = "complaint"
    PRAISE = "praise"
    REQUEST = "request"


@dataclass
class Entity:
    """An extracted entity."""
    text: str
    type: str
    start: int = 0
    end: int = 0
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "type": self.type,
            "start": self.start,
            "end": self.end,
            "confidence": self.confidence,
        }


@dataclass
class SentimentResult:
    """Sentiment analysis result."""
    sentiment: Sentiment
    score: float
    positive_score: float = 0.0
    negative_score: float = 0.0
    neutral_score: float = 0.0
    
    @property
    def is_positive(self) -> bool:
        return self.sentiment == Sentiment.POSITIVE
    
    @property
    def is_negative(self) -> bool:
        return self.sentiment == Sentiment.NEGATIVE


@dataclass
class IntentResult:
    """Intent classification result."""
    label: str
    confidence: float
    all_intents: List[Tuple[str, float]] = field(default_factory=list)
    
    @property
    def top_intents(self) -> List[Tuple[str, float]]:
        """Get top intents by confidence."""
        return sorted(self.all_intents, key=lambda x: x[1], reverse=True)


@dataclass
class KeyPhraseResult:
    """Key phrase extraction result."""
    phrases: List[str]
    scores: Dict[str, float] = field(default_factory=dict)


@dataclass
class AnalysisResult:
    """Complete text analysis result."""
    text: str
    sentiment: Optional[SentimentResult] = None
    intent: Optional[IntentResult] = None
    entities: List[Entity] = field(default_factory=list)
    key_phrases: List[str] = field(default_factory=list)
    category: Optional[ContentCategory] = None
    language: Optional[str] = None
    tokens: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text[:100] + "..." if len(self.text) > 100 else self.text,
            "sentiment": self.sentiment.sentiment.value if self.sentiment else None,
            "intent": self.intent.label if self.intent else None,
            "entities": [e.to_dict() for e in self.entities],
            "key_phrases": self.key_phrases,
            "category": self.category.value if self.category else None,
            "language": self.language,
        }


class Analyzer(ABC):
    """Abstract analyzer interface."""
    
    @abstractmethod
    async def analyze(self, text: str) -> AnalysisResult:
        """Analyze text."""
        pass


class SentimentAnalyzer(ABC):
    """Abstract sentiment analyzer."""
    
    @abstractmethod
    async def analyze(self, text: str) -> SentimentResult:
        """Analyze sentiment."""
        pass


class RuleBasedSentimentAnalyzer(SentimentAnalyzer):
    """Rule-based sentiment analyzer."""
    
    POSITIVE_WORDS = {
        "love", "great", "excellent", "amazing", "wonderful", "fantastic",
        "good", "happy", "joy", "like", "best", "awesome", "beautiful",
        "perfect", "brilliant", "outstanding", "superb", "delightful",
    }
    
    NEGATIVE_WORDS = {
        "hate", "bad", "terrible", "awful", "horrible", "worst",
        "sad", "angry", "disappointed", "poor", "ugly", "annoying",
        "frustrating", "boring", "useless", "pathetic", "disgusting",
    }
    
    INTENSIFIERS = {"very", "really", "extremely", "absolutely", "totally"}
    NEGATORS = {"not", "no", "never", "neither", "nobody", "nothing"}
    
    async def analyze(self, text: str) -> SentimentResult:
        """Analyze sentiment using rules."""
        words = text.lower().split()
        
        positive_count = 0
        negative_count = 0
        negated = False
        intensity = 1.0
        
        for i, word in enumerate(words):
            # Check for negation
            if word in self.NEGATORS:
                negated = True
                continue
            
            # Check for intensifiers
            if word in self.INTENSIFIERS:
                intensity = 1.5
                continue
            
            # Check sentiment words
            if word in self.POSITIVE_WORDS:
                if negated:
                    negative_count += intensity
                else:
                    positive_count += intensity
            elif word in self.NEGATIVE_WORDS:
                if negated:
                    positive_count += intensity
                else:
                    negative_count += intensity
            
            # Reset modifiers
            negated = False
            intensity = 1.0
        
        total = positive_count + negative_count
        
        if total == 0:
            return SentimentResult(
                sentiment=Sentiment.NEUTRAL,
                score=0.5,
                neutral_score=1.0,
            )
        
        positive_score = positive_count / total
        negative_score = negative_count / total
        
        if positive_count > negative_count * 1.5:
            sentiment = Sentiment.POSITIVE
            score = positive_score
        elif negative_count > positive_count * 1.5:
            sentiment = Sentiment.NEGATIVE
            score = negative_score
        elif total > 0:
            sentiment = Sentiment.MIXED
            score = 0.5
        else:
            sentiment = Sentiment.NEUTRAL
            score = 0.5
        
        return SentimentResult(
            sentiment=sentiment,
            score=score,
            positive_score=positive_score,
            negative_score=negative_score,
        )


class LLMSentimentAnalyzer(SentimentAnalyzer):
    """LLM-based sentiment analyzer."""
    
    def __init__(
        self,
        client: Any,
        model: Optional[str] = None,
    ):
        self._client = client
        self._model = model
    
    async def analyze(self, text: str) -> SentimentResult:
        """Analyze sentiment using LLM."""
        prompt = f"""Analyze the sentiment of the following text.
Return ONLY a JSON object with:
- sentiment: "positive", "negative", "neutral", or "mixed"
- score: confidence score from 0 to 1
- positive_score: positive sentiment score from 0 to 1
- negative_score: negative sentiment score from 0 to 1

Text: {text}

JSON:"""
        
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        
        try:
            import json
            content = response.choices[0].message.content
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                data = json.loads(match.group())
                return SentimentResult(
                    sentiment=Sentiment(data.get("sentiment", "neutral")),
                    score=data.get("score", 0.5),
                    positive_score=data.get("positive_score", 0),
                    negative_score=data.get("negative_score", 0),
                )
        except Exception as e:
            logger.error(f"Failed to parse sentiment: {e}")
        
        return SentimentResult(
            sentiment=Sentiment.NEUTRAL,
            score=0.5,
        )


class EntityExtractor(ABC):
    """Abstract entity extractor."""
    
    @abstractmethod
    async def extract(self, text: str) -> List[Entity]:
        """Extract entities from text."""
        pass


class PatternEntityExtractor(EntityExtractor):
    """Pattern-based entity extractor."""
    
    PATTERNS: Dict[str, Pattern] = {
        "EMAIL": re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
        "PHONE": re.compile(r'\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'),
        "URL": re.compile(r'https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*)?'),
        "DATE": re.compile(r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}\b', re.IGNORECASE),
        "TIME": re.compile(r'\b\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM|am|pm)?\b'),
        "MONEY": re.compile(r'\$[\d,]+(?:\.\d{2})?|\b\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:dollars?|USD|EUR|GBP)\b', re.IGNORECASE),
        "PERCENT": re.compile(r'\b\d+(?:\.\d+)?%\b'),
    }
    
    def __init__(self, patterns: Optional[Dict[str, Pattern]] = None):
        self._patterns = patterns or self.PATTERNS
    
    async def extract(self, text: str) -> List[Entity]:
        """Extract entities using patterns."""
        entities = []
        
        for entity_type, pattern in self._patterns.items():
            for match in pattern.finditer(text):
                entities.append(Entity(
                    text=match.group(),
                    type=entity_type,
                    start=match.start(),
                    end=match.end(),
                ))
        
        # Sort by position
        entities.sort(key=lambda e: e.start)
        return entities


class LLMEntityExtractor(EntityExtractor):
    """LLM-based entity extractor."""
    
    def __init__(
        self,
        client: Any,
        model: Optional[str] = None,
        entity_types: Optional[List[str]] = None,
    ):
        self._client = client
        self._model = model
        self._entity_types = entity_types or [
            "PERSON", "ORG", "LOC", "DATE", "PRODUCT", "EVENT"
        ]
    
    async def extract(self, text: str) -> List[Entity]:
        """Extract entities using LLM."""
        types_str = ", ".join(self._entity_types)
        
        prompt = f"""Extract named entities from the following text.
Entity types to extract: {types_str}

Return ONLY a JSON array of objects with:
- text: the entity text
- type: the entity type
- confidence: confidence score from 0 to 1

Text: {text}

JSON:"""
        
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        
        try:
            import json
            content = response.choices[0].message.content
            match = re.search(r'\[.*\]', content, re.DOTALL)
            if match:
                data = json.loads(match.group())
                return [
                    Entity(
                        text=e["text"],
                        type=e["type"],
                        confidence=e.get("confidence", 1.0),
                    )
                    for e in data
                ]
        except Exception as e:
            logger.error(f"Failed to parse entities: {e}")
        
        return []


class IntentClassifier(ABC):
    """Abstract intent classifier."""
    
    @abstractmethod
    async def classify(self, text: str) -> IntentResult:
        """Classify intent."""
        pass


class KeywordIntentClassifier(IntentClassifier):
    """Keyword-based intent classifier."""
    
    def __init__(self, intent_keywords: Dict[str, List[str]]):
        self._intent_keywords = intent_keywords
    
    async def classify(self, text: str) -> IntentResult:
        """Classify intent using keywords."""
        text_lower = text.lower()
        scores: Dict[str, float] = {}
        
        for intent, keywords in self._intent_keywords.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > 0:
                scores[intent] = score / len(keywords)
        
        if not scores:
            return IntentResult(label="unknown", confidence=0.0)
        
        # Sort by score
        sorted_intents = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top_intent, top_score = sorted_intents[0]
        
        return IntentResult(
            label=top_intent,
            confidence=top_score,
            all_intents=sorted_intents,
        )


class LLMIntentClassifier(IntentClassifier):
    """LLM-based intent classifier."""
    
    def __init__(
        self,
        client: Any,
        model: Optional[str] = None,
        intents: Optional[List[str]] = None,
    ):
        self._client = client
        self._model = model
        self._intents = intents or [
            "greeting", "farewell", "question", "request",
            "complaint", "booking", "information", "support"
        ]
    
    async def classify(self, text: str) -> IntentResult:
        """Classify intent using LLM."""
        intents_str = ", ".join(self._intents)
        
        prompt = f"""Classify the intent of the following text.
Possible intents: {intents_str}

Return ONLY a JSON object with:
- intent: the classified intent
- confidence: confidence score from 0 to 1
- all_intents: array of [intent, score] pairs

Text: {text}

JSON:"""
        
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        
        try:
            import json
            content = response.choices[0].message.content
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                data = json.loads(match.group())
                return IntentResult(
                    label=data.get("intent", "unknown"),
                    confidence=data.get("confidence", 0.5),
                    all_intents=[
                        tuple(item) for item in data.get("all_intents", [])
                    ],
                )
        except Exception as e:
            logger.error(f"Failed to parse intent: {e}")
        
        return IntentResult(label="unknown", confidence=0.0)


class TextAnalyzer(Analyzer):
    """
    Complete text analyzer combining multiple analysis methods.
    """
    
    def __init__(
        self,
        sentiment_analyzer: Optional[SentimentAnalyzer] = None,
        entity_extractor: Optional[EntityExtractor] = None,
        intent_classifier: Optional[IntentClassifier] = None,
    ):
        self._sentiment = sentiment_analyzer or RuleBasedSentimentAnalyzer()
        self._entities = entity_extractor or PatternEntityExtractor()
        self._intent = intent_classifier
    
    async def analyze(self, text: str) -> AnalysisResult:
        """Perform complete text analysis."""
        # Run analyses in parallel
        tasks = [
            self._sentiment.analyze(text),
            self._entities.extract(text),
        ]
        
        if self._intent:
            tasks.append(self._intent.classify(text))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        sentiment_result = results[0] if not isinstance(results[0], Exception) else None
        entities = results[1] if not isinstance(results[1], Exception) else []
        intent_result = None
        
        if self._intent and len(results) > 2:
            intent_result = results[2] if not isinstance(results[2], Exception) else None
        
        # Detect category
        category = self._detect_category(text)
        
        # Extract key phrases (simple approach)
        key_phrases = self._extract_key_phrases(text)
        
        return AnalysisResult(
            text=text,
            sentiment=sentiment_result,
            intent=intent_result,
            entities=entities,
            key_phrases=key_phrases,
            category=category,
            tokens=len(text.split()),
        )
    
    def _detect_category(self, text: str) -> ContentCategory:
        """Detect content category."""
        text_lower = text.lower().strip()
        
        # Question indicators
        if text_lower.endswith("?") or text_lower.startswith(("what", "who", "where", "when", "why", "how", "is", "are", "can", "do", "does")):
            return ContentCategory.QUESTION
        
        # Greeting indicators
        greetings = {"hello", "hi", "hey", "good morning", "good afternoon", "good evening"}
        if any(text_lower.startswith(g) for g in greetings):
            return ContentCategory.GREETING
        
        # Farewell indicators
        farewells = {"bye", "goodbye", "see you", "take care", "have a nice"}
        if any(f in text_lower for f in farewells):
            return ContentCategory.FAREWELL
        
        # Command indicators
        if text_lower.startswith(("please", "can you", "could you", "would you", "i need", "i want")):
            return ContentCategory.REQUEST
        
        return ContentCategory.STATEMENT
    
    def _extract_key_phrases(self, text: str, max_phrases: int = 5) -> List[str]:
        """Extract key phrases using simple heuristics."""
        # Remove common stop words
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "must", "shall",
            "can", "need", "dare", "ought", "used", "to", "of", "in",
            "for", "on", "with", "at", "by", "from", "as", "into", "through",
            "during", "before", "after", "above", "below", "between", "under",
            "again", "further", "then", "once", "here", "there", "when",
            "where", "why", "how", "all", "each", "few", "more", "most",
            "other", "some", "such", "no", "nor", "not", "only", "own",
            "same", "so", "than", "too", "very", "just", "and", "but",
            "if", "or", "because", "until", "while", "although", "this",
            "that", "these", "those", "i", "you", "he", "she", "it", "we",
            "they", "what", "which", "who", "whom", "whose", "my", "your",
        }
        
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        word_counts: Dict[str, int] = {}
        
        for word in words:
            if word not in stop_words:
                word_counts[word] = word_counts.get(word, 0) + 1
        
        # Sort by frequency
        sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
        
        return [word for word, _ in sorted_words[:max_phrases]]
    
    async def analyze_sentiment(self, text: str) -> SentimentResult:
        """Analyze sentiment only."""
        return await self._sentiment.analyze(text)
    
    async def extract_entities(self, text: str) -> List[Entity]:
        """Extract entities only."""
        return await self._entities.extract(text)
    
    async def classify_intent(self, text: str) -> Optional[IntentResult]:
        """Classify intent only."""
        if self._intent:
            return await self._intent.classify(text)
        return None


# Decorators
def analyze_input(
    analyzer: TextAnalyzer,
    inject_analysis: bool = True,
) -> Callable:
    """
    Decorator to analyze input before processing.
    
    Example:
        @analyze_input(analyzer)
        async def process(text: str, analysis: AnalysisResult = None):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(text: str, *args: Any, **kwargs: Any) -> Any:
            analysis = await analyzer.analyze(text)
            
            if inject_analysis:
                kwargs["analysis"] = analysis
            
            return await func(text, *args, **kwargs)
        
        return wrapper
    
    return decorator


# Factory functions
def create_analyzer(
    llm_client: Optional[Any] = None,
    model: Optional[str] = None,
    use_llm: bool = False,
) -> TextAnalyzer:
    """
    Factory function to create a text analyzer.
    
    Args:
        llm_client: LLM client for enhanced analysis
        model: Model name
        use_llm: Whether to use LLM for analysis
    """
    if use_llm and llm_client:
        return TextAnalyzer(
            sentiment_analyzer=LLMSentimentAnalyzer(llm_client, model),
            entity_extractor=LLMEntityExtractor(llm_client, model),
            intent_classifier=LLMIntentClassifier(llm_client, model),
        )
    
    return TextAnalyzer(
        sentiment_analyzer=RuleBasedSentimentAnalyzer(),
        entity_extractor=PatternEntityExtractor(),
    )


__all__ = [
    # Exceptions
    "AnalysisError",
    # Enums
    "Sentiment",
    "EntityType",
    "ContentCategory",
    # Data classes
    "Entity",
    "SentimentResult",
    "IntentResult",
    "KeyPhraseResult",
    "AnalysisResult",
    # Analyzers
    "Analyzer",
    "TextAnalyzer",
    # Sentiment
    "SentimentAnalyzer",
    "RuleBasedSentimentAnalyzer",
    "LLMSentimentAnalyzer",
    # Entities
    "EntityExtractor",
    "PatternEntityExtractor",
    "LLMEntityExtractor",
    # Intent
    "IntentClassifier",
    "KeywordIntentClassifier",
    "LLMIntentClassifier",
    # Decorators
    "analyze_input",
    # Factory
    "create_analyzer",
]
