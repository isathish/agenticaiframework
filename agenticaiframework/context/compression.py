"""
Strategies for context compression.
"""

import re
from typing import List

from .types import ContextPriority
from .items import ContextItem


class ContextCompressionStrategy:
    """Strategies for context compression."""
    
    @staticmethod
    def summarize(content: str, max_length: int = 500) -> str:
        """
        Summarize content to max length.
        
        Args:
            content: Content to summarize
            max_length: Maximum length of summary
            
        Returns:
            Summarized content
        """
        if len(content) <= max_length:
            return content
        
        # Simple extractive summarization (first sentences)
        sentences = re.split(r'(?<=[.!?])\s+', content)
        summary = []
        current_length = 0
        
        for sentence in sentences:
            if current_length + len(sentence) <= max_length:
                summary.append(sentence)
                current_length += len(sentence) + 1
            else:
                break
        
        return ' '.join(summary) if summary else content[:max_length]
    
    @staticmethod
    def extract_key_points(content: str, num_points: int = 5) -> str:
        """
        Extract key points from content.
        
        Args:
            content: Content to extract from
            num_points: Maximum number of key points
            
        Returns:
            Key points as string
        """
        lines = content.split('\n')
        key_points = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Detect bullet points or numbered items
            if re.match(r'^[\-\*•]\s+', line) or re.match(r'^\d+[\.\)]\s+', line):
                key_points.append(line)
            # Detect lines with keywords
            elif any(kw in line.lower() for kw in ['important', 'key', 'note', 'must', 'should', 'critical']):
                key_points.append(line)
        
        if len(key_points) > num_points:
            key_points = key_points[:num_points]
        
        return '\n'.join(key_points) if key_points else content[:500]
    
    @staticmethod
    def merge_similar(items: List[ContextItem], similarity_threshold: float = 0.8) -> List[ContextItem]:
        """
        Merge similar context items.
        
        Args:
            items: List of context items
            similarity_threshold: Threshold for merging
            
        Returns:
            List of merged items
        """
        if len(items) <= 1:
            return items
        
        merged = []
        used = set()
        
        for i, item in enumerate(items):
            if i in used:
                continue
            
            similar_items = [item]
            for j, other in enumerate(items[i + 1:], start=i + 1):
                if j in used:
                    continue
                
                # Simple similarity check (word overlap)
                similarity = item.compute_relevance_score(other.content)
                if similarity >= similarity_threshold:
                    similar_items.append(other)
                    used.add(j)
            
            if len(similar_items) > 1:
                # Merge into single item
                merged_content = '\n---\n'.join(it.content for it in similar_items)
                merged_item = ContextItem(
                    id=item.id,
                    content=merged_content,
                    context_type=item.context_type,
                    priority=max(it.priority for it in similar_items),
                    tokens=sum(it.tokens for it in similar_items),
                    importance=max(it.importance for it in similar_items),
                    timestamp=max(it.timestamp for it in similar_items),
                    metadata={'merged_count': len(similar_items)},
                    tags=list(set(tag for it in similar_items for tag in it.tags))
                )
                merged.append(merged_item)
            else:
                merged.append(item)
            
            used.add(i)
        
        return merged
    
    @staticmethod
    def truncate_by_priority(
        items: List[ContextItem],
        max_tokens: int
    ) -> List[ContextItem]:
        """
        Truncate items to fit within token budget, keeping highest priority.
        
        Args:
            items: List of context items
            max_tokens: Maximum total tokens
            
        Returns:
            Truncated list of items
        """
        # Sort by priority (descending)
        sorted_items = sorted(
            items,
            key=lambda x: (x.priority.value, x.importance),
            reverse=True
        )
        
        kept = []
        current_tokens = 0
        
        for item in sorted_items:
            if item.priority == ContextPriority.CRITICAL:
                kept.append(item)
                current_tokens += item.tokens
            elif current_tokens + item.tokens <= max_tokens:
                kept.append(item)
                current_tokens += item.tokens
        
        return kept
