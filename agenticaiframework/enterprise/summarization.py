"""
Enterprise Summarization Module.

Provides text summarization, document compression,
abstractive and extractive summaries for agents.

Example:
    # Create summarizer
    summarizer = LLMSummarizer(client=openai_client)
    
    # Summarize text
    summary = await summarizer.summarize(long_text, max_length=200)
    
    # Bullet points
    bullets = await summarizer.bullet_points(text, max_points=5)
    
    # Document summarization
    doc_summary = await summarizer.summarize_document(doc)
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
    Tuple,
    Union,
)
from datetime import datetime
from functools import wraps
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class SummarizationError(Exception):
    """Summarization error."""
    pass


class SummaryType(str, Enum):
    """Types of summaries."""
    EXTRACTIVE = "extractive"     # Select key sentences
    ABSTRACTIVE = "abstractive"   # Generate new text
    MIXED = "mixed"               # Combination
    BULLET_POINTS = "bullets"     # Bullet point list
    HEADLINE = "headline"         # Single line
    KEY_POINTS = "key_points"     # Key takeaways


class CompressionLevel(str, Enum):
    """Compression levels."""
    MINIMAL = "minimal"     # ~75% of original
    MODERATE = "moderate"   # ~50% of original
    AGGRESSIVE = "aggressive"  # ~25% of original
    EXTREME = "extreme"     # ~10% of original


@dataclass
class Summary:
    """Summary result."""
    text: str
    original_length: int
    summary_length: int
    summary_type: SummaryType = SummaryType.ABSTRACTIVE
    compression_ratio: float = 0.0
    key_points: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.original_length > 0:
            self.compression_ratio = 1 - (self.summary_length / self.original_length)
    
    @property
    def word_count(self) -> int:
        return len(self.text.split())


@dataclass
class ChunkSummary:
    """Summary of a text chunk."""
    chunk_index: int
    original_text: str
    summary: str
    start_offset: int = 0
    end_offset: int = 0


@dataclass
class DocumentSummary:
    """Summary of a document."""
    title: Optional[str]
    summary: str
    sections: List[ChunkSummary] = field(default_factory=list)
    key_points: List[str] = field(default_factory=list)
    entities: List[str] = field(default_factory=list)
    topics: List[str] = field(default_factory=list)


class Summarizer(ABC):
    """Abstract summarizer interface."""
    
    @abstractmethod
    async def summarize(
        self,
        text: str,
        max_length: Optional[int] = None,
        **kwargs: Any,
    ) -> Summary:
        """Summarize text."""
        pass


class ExtractiveSummarizer(Summarizer):
    """Extractive summarizer using sentence scoring."""
    
    def __init__(
        self,
        sentence_scorer: Optional[Callable[[str, str], float]] = None,
    ):
        self._scorer = sentence_scorer or self._default_scorer
    
    @staticmethod
    def _default_scorer(sentence: str, full_text: str) -> float:
        """Default sentence scoring based on word frequency."""
        # Simple TF-based scoring
        words = full_text.lower().split()
        word_freq = {}
        for word in words:
            word_freq[word] = word_freq.get(word, 0) + 1
        
        sentence_words = sentence.lower().split()
        if not sentence_words:
            return 0.0
        
        score = sum(word_freq.get(w, 0) for w in sentence_words)
        return score / len(sentence_words)
    
    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        # Simple sentence splitting
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]
    
    async def summarize(
        self,
        text: str,
        max_length: Optional[int] = None,
        max_sentences: int = 5,
        **kwargs: Any,
    ) -> Summary:
        """Extract key sentences."""
        sentences = self._split_sentences(text)
        
        if len(sentences) <= max_sentences:
            return Summary(
                text=text,
                original_length=len(text),
                summary_length=len(text),
                summary_type=SummaryType.EXTRACTIVE,
            )
        
        # Score sentences
        scored = []
        for i, sentence in enumerate(sentences):
            if asyncio.iscoroutinefunction(self._scorer):
                score = await self._scorer(sentence, text)
            else:
                score = self._scorer(sentence, text)
            scored.append((i, sentence, score))
        
        # Sort by score
        scored.sort(key=lambda x: x[2], reverse=True)
        
        # Select top sentences
        selected = sorted(scored[:max_sentences], key=lambda x: x[0])
        
        summary_text = " ".join(s[1] for s in selected)
        
        # Apply max_length if specified
        if max_length and len(summary_text) > max_length:
            summary_text = summary_text[:max_length].rsplit(" ", 1)[0] + "..."
        
        return Summary(
            text=summary_text,
            original_length=len(text),
            summary_length=len(summary_text),
            summary_type=SummaryType.EXTRACTIVE,
        )


class LLMSummarizer(Summarizer):
    """LLM-based abstractive summarizer."""
    
    DEFAULT_PROMPT = """Summarize the following text concisely while preserving the key information.

Text:
{text}

Summary:"""
    
    BULLET_PROMPT = """Extract the key points from the following text as bullet points.

Text:
{text}

Key points (as bullet points):"""
    
    HEADLINE_PROMPT = """Write a single-line headline summarizing the following text.

Text:
{text}

Headline:"""
    
    def __init__(
        self,
        client: Any,
        model: Optional[str] = None,
        temperature: float = 0.3,
        prompt_template: Optional[str] = None,
    ):
        self._client = client
        self._model = model
        self._temperature = temperature
        self._prompt_template = prompt_template or self.DEFAULT_PROMPT
    
    async def summarize(
        self,
        text: str,
        max_length: Optional[int] = None,
        summary_type: SummaryType = SummaryType.ABSTRACTIVE,
        **kwargs: Any,
    ) -> Summary:
        """Summarize using LLM."""
        # Choose prompt based on type
        if summary_type == SummaryType.BULLET_POINTS:
            prompt = self.BULLET_PROMPT.format(text=text)
        elif summary_type == SummaryType.HEADLINE:
            prompt = self.HEADLINE_PROMPT.format(text=text)
        else:
            prompt = self._prompt_template.format(text=text)
        
        # Add length constraint
        if max_length:
            prompt += f"\n\nKeep the summary under {max_length} characters."
        
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self._temperature,
            max_tokens=kwargs.get("max_tokens"),
        )
        
        summary_text = response.choices[0].message.content.strip()
        
        # Extract key points if bullet format
        key_points = []
        if summary_type == SummaryType.BULLET_POINTS:
            key_points = [
                line.lstrip("•-* ").strip()
                for line in summary_text.split("\n")
                if line.strip() and line.strip()[0] in "•-*"
            ]
        
        return Summary(
            text=summary_text,
            original_length=len(text),
            summary_length=len(summary_text),
            summary_type=summary_type,
            key_points=key_points,
        )
    
    async def bullet_points(
        self,
        text: str,
        max_points: int = 5,
        **kwargs: Any,
    ) -> List[str]:
        """Extract bullet points."""
        prompt = f"""Extract up to {max_points} key points from the following text as bullet points.

Text:
{text}

Key points:"""
        
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        
        content = response.choices[0].message.content.strip()
        
        # Parse bullet points
        points = []
        for line in content.split("\n"):
            line = line.strip()
            if line and line[0] in "•-*0123456789":
                # Remove bullet/number prefix
                point = re.sub(r'^[\•\-\*\d]+[\.\)\s]+', '', line).strip()
                if point:
                    points.append(point)
        
        return points[:max_points]
    
    async def headline(self, text: str, **kwargs: Any) -> str:
        """Generate a headline."""
        summary = await self.summarize(
            text,
            summary_type=SummaryType.HEADLINE,
            **kwargs,
        )
        return summary.text
    
    async def tldr(self, text: str, max_words: int = 50, **kwargs: Any) -> str:
        """Generate a TL;DR summary."""
        prompt = f"""Provide a TL;DR summary of the following text in {max_words} words or less.

Text:
{text}

TL;DR:"""
        
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        
        return response.choices[0].message.content.strip()


class ChunkedSummarizer(Summarizer):
    """Summarizer for long documents using chunking."""
    
    def __init__(
        self,
        summarizer: Summarizer,
        chunk_size: int = 4000,
        overlap: int = 200,
    ):
        self._summarizer = summarizer
        self._chunk_size = chunk_size
        self._overlap = overlap
    
    def _chunk_text(self, text: str) -> List[Tuple[str, int, int]]:
        """Split text into chunks with offsets."""
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + self._chunk_size
            
            # Try to break at sentence boundary
            if end < len(text):
                # Look for sentence end near chunk boundary
                for i in range(min(200, end - start)):
                    if text[end - i - 1] in ".!?":
                        end = end - i
                        break
            
            chunk = text[start:end]
            chunks.append((chunk, start, end))
            start = end - self._overlap
        
        return chunks
    
    async def summarize(
        self,
        text: str,
        max_length: Optional[int] = None,
        **kwargs: Any,
    ) -> Summary:
        """Summarize long text using chunking."""
        chunks = self._chunk_text(text)
        
        # Summarize each chunk
        chunk_summaries = await asyncio.gather(*[
            self._summarizer.summarize(chunk, **kwargs)
            for chunk, _, _ in chunks
        ])
        
        # Combine summaries
        combined_text = " ".join(s.text for s in chunk_summaries)
        
        # If still too long, summarize again
        if max_length and len(combined_text) > max_length * 2:
            final_summary = await self._summarizer.summarize(
                combined_text,
                max_length=max_length,
                **kwargs,
            )
            return final_summary
        
        if max_length and len(combined_text) > max_length:
            combined_text = combined_text[:max_length].rsplit(" ", 1)[0] + "..."
        
        return Summary(
            text=combined_text,
            original_length=len(text),
            summary_length=len(combined_text),
            summary_type=SummaryType.ABSTRACTIVE,
        )


class HierarchicalSummarizer(Summarizer):
    """Hierarchical summarization for documents with structure."""
    
    def __init__(
        self,
        summarizer: Summarizer,
        section_pattern: str = r'\n##?\s+',
    ):
        self._summarizer = summarizer
        self._section_pattern = re.compile(section_pattern)
    
    def _split_sections(self, text: str) -> List[Tuple[str, str]]:
        """Split document into sections."""
        parts = self._section_pattern.split(text)
        sections = []
        
        for i, part in enumerate(parts):
            if i == 0 and part.strip():
                sections.append(("Introduction", part.strip()))
            elif part.strip():
                # Extract title from first line
                lines = part.split("\n", 1)
                title = lines[0].strip()
                content = lines[1].strip() if len(lines) > 1 else ""
                if content:
                    sections.append((title, content))
        
        return sections
    
    async def summarize(
        self,
        text: str,
        max_length: Optional[int] = None,
        **kwargs: Any,
    ) -> Summary:
        """Summarize document hierarchically."""
        sections = self._split_sections(text)
        
        if not sections:
            return await self._summarizer.summarize(text, max_length, **kwargs)
        
        # Summarize each section
        section_summaries = await asyncio.gather(*[
            self._summarizer.summarize(content, **kwargs)
            for _, content in sections
        ])
        
        # Build combined summary with section headers
        parts = []
        for (title, _), summary in zip(sections, section_summaries):
            parts.append(f"**{title}**: {summary.text}")
        
        combined_text = "\n\n".join(parts)
        
        # Final compression if needed
        if max_length and len(combined_text) > max_length:
            final_summary = await self._summarizer.summarize(
                combined_text,
                max_length=max_length,
                **kwargs,
            )
            return final_summary
        
        return Summary(
            text=combined_text,
            original_length=len(text),
            summary_length=len(combined_text),
            summary_type=SummaryType.ABSTRACTIVE,
        )
    
    async def summarize_document(
        self,
        text: str,
        title: Optional[str] = None,
        **kwargs: Any,
    ) -> DocumentSummary:
        """Create a structured document summary."""
        sections = self._split_sections(text)
        
        # Summarize sections
        chunk_summaries = []
        for i, (section_title, content) in enumerate(sections):
            summary = await self._summarizer.summarize(content, **kwargs)
            chunk_summaries.append(ChunkSummary(
                chunk_index=i,
                original_text=content,
                summary=summary.text,
            ))
        
        # Generate overall summary
        all_content = " ".join(s.summary for s in chunk_summaries)
        overall = await self._summarizer.summarize(all_content, **kwargs)
        
        # Extract key points
        key_points = []
        if hasattr(self._summarizer, 'bullet_points'):
            key_points = await self._summarizer.bullet_points(text, max_points=5)
        
        return DocumentSummary(
            title=title,
            summary=overall.text,
            sections=chunk_summaries,
            key_points=key_points,
        )


class ContextCompressor:
    """Compress context for LLM input limits."""
    
    def __init__(
        self,
        summarizer: Summarizer,
        max_tokens: int = 4000,
        token_counter: Optional[Callable[[str], int]] = None,
    ):
        self._summarizer = summarizer
        self._max_tokens = max_tokens
        self._token_counter = token_counter or (lambda s: len(s) // 4)
    
    async def compress(
        self,
        text: str,
        target_tokens: Optional[int] = None,
        preserve_structure: bool = True,
    ) -> str:
        """Compress text to fit token limit."""
        target = target_tokens or self._max_tokens
        current_tokens = self._token_counter(text)
        
        if current_tokens <= target:
            return text
        
        # Calculate target length
        ratio = target / current_tokens
        target_length = int(len(text) * ratio * 0.9)  # 10% buffer
        
        summary = await self._summarizer.summarize(
            text,
            max_length=target_length,
        )
        
        return summary.text
    
    async def compress_messages(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
    ) -> List[Dict[str, str]]:
        """Compress a list of messages."""
        target = max_tokens or self._max_tokens
        
        # Calculate current tokens
        total_tokens = sum(
            self._token_counter(m.get("content", ""))
            for m in messages
        )
        
        if total_tokens <= target:
            return messages
        
        # Compress older messages more aggressively
        compressed = []
        tokens_used = 0
        
        # Keep most recent messages intact
        recent_count = min(3, len(messages))
        recent_messages = messages[-recent_count:]
        remaining = messages[:-recent_count] if recent_count < len(messages) else []
        
        # Calculate tokens for recent
        recent_tokens = sum(
            self._token_counter(m.get("content", ""))
            for m in recent_messages
        )
        
        available = target - recent_tokens
        
        # Compress older messages
        if remaining and available > 0:
            combined = "\n".join(
                f"{m.get('role', 'user')}: {m.get('content', '')}"
                for m in remaining
            )
            
            compressed_text = await self.compress(combined, target_tokens=available)
            
            compressed.append({
                "role": "system",
                "content": f"[Previous conversation summary]\n{compressed_text}",
            })
        
        compressed.extend(recent_messages)
        return compressed


# Decorators
def summarize_output(
    summarizer: Summarizer,
    max_length: int = 500,
) -> Callable:
    """
    Decorator to summarize function output.
    
    Example:
        @summarize_output(summarizer, max_length=200)
        async def get_content() -> str:
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Summary:
            result = await func(*args, **kwargs)
            
            if isinstance(result, str):
                return await summarizer.summarize(result, max_length=max_length)
            
            return result
        
        return wrapper
    
    return decorator


# Factory functions
def create_summarizer(
    provider: str = "extractive",
    llm_client: Optional[Any] = None,
    model: Optional[str] = None,
    **kwargs: Any,
) -> Summarizer:
    """
    Factory function to create a summarizer.
    
    Args:
        provider: Type of summarizer
        llm_client: LLM client for abstractive summarization
        model: Model name
    """
    if provider == "extractive":
        return ExtractiveSummarizer(**kwargs)
    
    elif provider == "llm" or provider == "abstractive":
        if not llm_client:
            raise ValueError("LLM client required for abstractive summarizer")
        return LLMSummarizer(llm_client, model, **kwargs)
    
    elif provider == "chunked":
        if not llm_client:
            raise ValueError("LLM client required")
        base = LLMSummarizer(llm_client, model)
        return ChunkedSummarizer(base, **kwargs)
    
    elif provider == "hierarchical":
        if not llm_client:
            raise ValueError("LLM client required")
        base = LLMSummarizer(llm_client, model)
        return HierarchicalSummarizer(base, **kwargs)
    
    else:
        return ExtractiveSummarizer(**kwargs)


__all__ = [
    # Exceptions
    "SummarizationError",
    # Enums
    "SummaryType",
    "CompressionLevel",
    # Data classes
    "Summary",
    "ChunkSummary",
    "DocumentSummary",
    # Summarizers
    "Summarizer",
    "ExtractiveSummarizer",
    "LLMSummarizer",
    "ChunkedSummarizer",
    "HierarchicalSummarizer",
    # Context
    "ContextCompressor",
    # Decorators
    "summarize_output",
    # Factory
    "create_summarizer",
]
