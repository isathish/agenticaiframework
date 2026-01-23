"""
Enterprise Filter Module.

Provides request/response filtering, content transformation,
and data sanitization for agent operations.

Example:
    # Filter pipeline
    pipeline = FilterPipeline()
    pipeline.add(PiiFilter())
    pipeline.add(ContentFilter())
    
    filtered_request = await pipeline.filter_request(request)
    filtered_response = await pipeline.filter_response(response)
    
    # Decorators
    @filter_input(PiiFilter())
    async def process_data(data):
        ...
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
    Generic,
    List,
    Optional,
    Pattern,
    Set,
    TypeVar,
    Union,
)
from datetime import datetime
from functools import wraps
from enum import Enum
import logging
import json
import hashlib

logger = logging.getLogger(__name__)

T = TypeVar('T')


class FilterError(Exception):
    """Filter error."""
    pass


class FilterBlockedError(FilterError):
    """Content was blocked by filter."""
    pass


class FilterAction(str, Enum):
    """Actions a filter can take."""
    PASS = "pass"
    MODIFY = "modify"
    BLOCK = "block"
    WARN = "warn"


@dataclass
class FilterResult:
    """Result of a filter operation."""
    action: FilterAction
    data: Any
    modified: bool = False
    blocked: bool = False
    warnings: List[str] = field(default_factory=list)
    modifications: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def passed(self) -> bool:
        """Check if content passed the filter."""
        return self.action in (FilterAction.PASS, FilterAction.MODIFY, FilterAction.WARN)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action.value,
            "modified": self.modified,
            "blocked": self.blocked,
            "warnings": self.warnings,
            "modifications": self.modifications,
            "metadata": self.metadata,
        }


class Filter(ABC, Generic[T]):
    """Abstract filter."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Get filter name."""
        pass
    
    @abstractmethod
    async def filter(self, data: T) -> FilterResult:
        """Apply filter to data."""
        pass
    
    async def filter_request(self, data: T) -> FilterResult:
        """Filter incoming request."""
        return await self.filter(data)
    
    async def filter_response(self, data: T) -> FilterResult:
        """Filter outgoing response."""
        return await self.filter(data)


class PiiFilter(Filter[str]):
    """
    Filter for detecting and masking PII (Personally Identifiable Information).
    """
    
    PATTERNS = {
        "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        "phone": r'\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b',
        "ssn": r'\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b',
        "credit_card": r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
        "ip_address": r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
    }
    
    def __init__(
        self,
        mask_char: str = "*",
        detect_only: bool = False,
        patterns: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize PII filter.
        
        Args:
            mask_char: Character to use for masking
            detect_only: Only detect, don't mask
            patterns: Custom regex patterns
        """
        self.mask_char = mask_char
        self.detect_only = detect_only
        self._patterns = {
            name: re.compile(pattern, re.IGNORECASE)
            for name, pattern in (patterns or self.PATTERNS).items()
        }
    
    @property
    def name(self) -> str:
        return "pii_filter"
    
    async def filter(self, data: str) -> FilterResult:
        """Filter PII from text."""
        if not isinstance(data, str):
            return FilterResult(action=FilterAction.PASS, data=data)
        
        modifications = []
        filtered_text = data
        
        for pii_type, pattern in self._patterns.items():
            matches = pattern.findall(data)
            
            if matches:
                modifications.append(f"Found {len(matches)} {pii_type} pattern(s)")
                
                if not self.detect_only:
                    filtered_text = pattern.sub(
                        lambda m: self.mask_char * len(m.group()),
                        filtered_text,
                    )
        
        if modifications:
            return FilterResult(
                action=FilterAction.MODIFY if not self.detect_only else FilterAction.WARN,
                data=filtered_text,
                modified=not self.detect_only and filtered_text != data,
                warnings=modifications if self.detect_only else [],
                modifications=modifications if not self.detect_only else [],
            )
        
        return FilterResult(action=FilterAction.PASS, data=data)


class ContentFilter(Filter[str]):
    """
    Filter for blocking or modifying inappropriate content.
    """
    
    def __init__(
        self,
        blocked_words: Optional[Set[str]] = None,
        replacement: str = "[FILTERED]",
        block_on_match: bool = False,
    ):
        """
        Initialize content filter.
        
        Args:
            blocked_words: Words to filter
            replacement: Replacement text
            block_on_match: Block entire content on match
        """
        self.blocked_words = blocked_words or set()
        self.replacement = replacement
        self.block_on_match = block_on_match
    
    @property
    def name(self) -> str:
        return "content_filter"
    
    async def filter(self, data: str) -> FilterResult:
        """Filter inappropriate content."""
        if not isinstance(data, str):
            return FilterResult(action=FilterAction.PASS, data=data)
        
        found_words = []
        filtered_text = data
        
        for word in self.blocked_words:
            pattern = re.compile(re.escape(word), re.IGNORECASE)
            if pattern.search(data):
                found_words.append(word)
                
                if self.block_on_match:
                    return FilterResult(
                        action=FilterAction.BLOCK,
                        data=data,
                        blocked=True,
                        modifications=[f"Blocked word found: {word}"],
                    )
                
                filtered_text = pattern.sub(self.replacement, filtered_text)
        
        if found_words:
            return FilterResult(
                action=FilterAction.MODIFY,
                data=filtered_text,
                modified=True,
                modifications=[f"Replaced {len(found_words)} blocked word(s)"],
            )
        
        return FilterResult(action=FilterAction.PASS, data=data)


class LengthFilter(Filter[str]):
    """
    Filter for limiting content length.
    """
    
    def __init__(
        self,
        max_length: int = 10000,
        truncate: bool = True,
        truncation_suffix: str = "...",
    ):
        """
        Initialize length filter.
        
        Args:
            max_length: Maximum allowed length
            truncate: Truncate if too long
            truncation_suffix: Suffix to add when truncating
        """
        self.max_length = max_length
        self.truncate = truncate
        self.truncation_suffix = truncation_suffix
    
    @property
    def name(self) -> str:
        return "length_filter"
    
    async def filter(self, data: str) -> FilterResult:
        """Filter by length."""
        if not isinstance(data, str):
            return FilterResult(action=FilterAction.PASS, data=data)
        
        if len(data) <= self.max_length:
            return FilterResult(action=FilterAction.PASS, data=data)
        
        if self.truncate:
            truncated = data[:self.max_length - len(self.truncation_suffix)] + self.truncation_suffix
            return FilterResult(
                action=FilterAction.MODIFY,
                data=truncated,
                modified=True,
                modifications=[f"Truncated from {len(data)} to {len(truncated)} chars"],
            )
        
        return FilterResult(
            action=FilterAction.BLOCK,
            data=data,
            blocked=True,
            modifications=[f"Content length {len(data)} exceeds limit {self.max_length}"],
        )


class JsonFilter(Filter[str]):
    """
    Filter for validating and sanitizing JSON.
    """
    
    def __init__(
        self,
        allowed_keys: Optional[Set[str]] = None,
        blocked_keys: Optional[Set[str]] = None,
        max_depth: int = 10,
    ):
        """
        Initialize JSON filter.
        
        Args:
            allowed_keys: Only allow these keys
            blocked_keys: Block these keys
            max_depth: Maximum nesting depth
        """
        self.allowed_keys = allowed_keys
        self.blocked_keys = blocked_keys or set()
        self.max_depth = max_depth
    
    @property
    def name(self) -> str:
        return "json_filter"
    
    def _filter_dict(
        self,
        data: Dict[str, Any],
        depth: int = 0,
    ) -> Dict[str, Any]:
        """Recursively filter dictionary."""
        if depth > self.max_depth:
            return {}
        
        filtered = {}
        
        for key, value in data.items():
            # Skip blocked keys
            if key in self.blocked_keys:
                continue
            
            # Check allowed keys
            if self.allowed_keys and key not in self.allowed_keys:
                continue
            
            # Recurse into nested dicts
            if isinstance(value, dict):
                filtered[key] = self._filter_dict(value, depth + 1)
            elif isinstance(value, list):
                filtered[key] = [
                    self._filter_dict(item, depth + 1) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                filtered[key] = value
        
        return filtered
    
    async def filter(self, data: str) -> FilterResult:
        """Filter JSON content."""
        try:
            parsed = json.loads(data) if isinstance(data, str) else data
        except json.JSONDecodeError as e:
            return FilterResult(
                action=FilterAction.BLOCK,
                data=data,
                blocked=True,
                modifications=[f"Invalid JSON: {e}"],
            )
        
        if isinstance(parsed, dict):
            filtered = self._filter_dict(parsed)
            filtered_str = json.dumps(filtered)
            
            if filtered != parsed:
                return FilterResult(
                    action=FilterAction.MODIFY,
                    data=filtered_str,
                    modified=True,
                    modifications=["Removed blocked/unauthorized keys"],
                )
            
            return FilterResult(action=FilterAction.PASS, data=data)
        
        return FilterResult(action=FilterAction.PASS, data=data)


class RegexFilter(Filter[str]):
    """
    Filter using regular expressions.
    """
    
    def __init__(
        self,
        patterns: List[Dict[str, Any]],
    ):
        """
        Initialize regex filter.
        
        Args:
            patterns: List of {"pattern": str, "action": str, "replacement": str}
        """
        self._patterns = []
        
        for p in patterns:
            self._patterns.append({
                "regex": re.compile(p["pattern"], re.IGNORECASE),
                "action": FilterAction(p.get("action", "modify")),
                "replacement": p.get("replacement", ""),
            })
    
    @property
    def name(self) -> str:
        return "regex_filter"
    
    async def filter(self, data: str) -> FilterResult:
        """Apply regex filters."""
        if not isinstance(data, str):
            return FilterResult(action=FilterAction.PASS, data=data)
        
        filtered_text = data
        modifications = []
        blocked = False
        
        for p in self._patterns:
            if p["regex"].search(data):
                if p["action"] == FilterAction.BLOCK:
                    blocked = True
                    modifications.append("Blocked by regex pattern")
                    break
                elif p["action"] == FilterAction.MODIFY:
                    filtered_text = p["regex"].sub(p["replacement"], filtered_text)
                    modifications.append("Modified by regex pattern")
                elif p["action"] == FilterAction.WARN:
                    modifications.append("Warning: regex pattern matched")
        
        if blocked:
            return FilterResult(
                action=FilterAction.BLOCK,
                data=data,
                blocked=True,
                modifications=modifications,
            )
        
        if modifications:
            return FilterResult(
                action=FilterAction.MODIFY if filtered_text != data else FilterAction.WARN,
                data=filtered_text,
                modified=filtered_text != data,
                warnings=[m for m in modifications if "Warning" in m],
                modifications=[m for m in modifications if "Warning" not in m],
            )
        
        return FilterResult(action=FilterAction.PASS, data=data)


class CompositeFilter(Filter[T]):
    """
    Composite filter that applies multiple filters.
    """
    
    def __init__(
        self,
        filters: Optional[List[Filter]] = None,
        stop_on_block: bool = True,
    ):
        """
        Initialize composite filter.
        
        Args:
            filters: List of filters to apply
            stop_on_block: Stop processing if any filter blocks
        """
        self._filters = list(filters) if filters else []
        self._stop_on_block = stop_on_block
    
    @property
    def name(self) -> str:
        return "composite_filter"
    
    def add(self, filter_: Filter) -> 'CompositeFilter':
        """Add a filter."""
        self._filters.append(filter_)
        return self
    
    async def filter(self, data: T) -> FilterResult:
        """Apply all filters."""
        current_data = data
        all_modifications = []
        all_warnings = []
        was_modified = False
        
        for f in self._filters:
            result = await f.filter(current_data)
            
            if result.blocked:
                return FilterResult(
                    action=FilterAction.BLOCK,
                    data=current_data,
                    blocked=True,
                    modifications=all_modifications + result.modifications,
                    warnings=all_warnings + result.warnings,
                    metadata={"blocked_by": f.name},
                )
            
            if result.modified:
                current_data = result.data
                was_modified = True
            
            all_modifications.extend(result.modifications)
            all_warnings.extend(result.warnings)
        
        return FilterResult(
            action=FilterAction.MODIFY if was_modified else FilterAction.PASS,
            data=current_data,
            modified=was_modified,
            modifications=all_modifications,
            warnings=all_warnings,
        )


class FilterPipeline:
    """
    Pipeline for filtering requests and responses.
    """
    
    def __init__(self):
        self._request_filters: List[Filter] = []
        self._response_filters: List[Filter] = []
    
    def add_request_filter(self, filter_: Filter) -> 'FilterPipeline':
        """Add a request filter."""
        self._request_filters.append(filter_)
        return self
    
    def add_response_filter(self, filter_: Filter) -> 'FilterPipeline':
        """Add a response filter."""
        self._response_filters.append(filter_)
        return self
    
    def add(self, filter_: Filter) -> 'FilterPipeline':
        """Add filter for both request and response."""
        self._request_filters.append(filter_)
        self._response_filters.append(filter_)
        return self
    
    async def filter_request(self, data: Any) -> FilterResult:
        """Filter incoming request."""
        composite = CompositeFilter(self._request_filters)
        return await composite.filter(data)
    
    async def filter_response(self, data: Any) -> FilterResult:
        """Filter outgoing response."""
        composite = CompositeFilter(self._response_filters)
        return await composite.filter(data)


class FilterMiddleware:
    """
    Middleware for agent filter pipeline.
    """
    
    def __init__(self, pipeline: FilterPipeline):
        self.pipeline = pipeline
    
    async def __call__(
        self,
        request: Any,
        next_handler: Callable,
    ) -> Any:
        """Process request through filter pipeline."""
        # Filter request
        request_result = await self.pipeline.filter_request(request)
        
        if request_result.blocked:
            raise FilterBlockedError(
                f"Request blocked: {request_result.modifications}"
            )
        
        # Call next handler
        response = await next_handler(request_result.data)
        
        # Filter response
        response_result = await self.pipeline.filter_response(response)
        
        if response_result.blocked:
            raise FilterBlockedError(
                f"Response blocked: {response_result.modifications}"
            )
        
        return response_result.data


def filter_input(
    *filters: Filter,
) -> Callable:
    """
    Decorator to filter function input.
    
    Example:
        @filter_input(PiiFilter(), ContentFilter())
        async def process(data):
            ...
    """
    composite = CompositeFilter(list(filters))
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            # Filter first argument
            if args:
                result = await composite.filter(args[0])
                if result.blocked:
                    raise FilterBlockedError(f"Input blocked: {result.modifications}")
                args = (result.data,) + args[1:]
            
            return await func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            if args:
                result = asyncio.run(composite.filter(args[0]))
                if result.blocked:
                    raise FilterBlockedError(f"Input blocked: {result.modifications}")
                args = (result.data,) + args[1:]
            
            return func(*args, **kwargs)
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


def filter_output(
    *filters: Filter,
) -> Callable:
    """
    Decorator to filter function output.
    
    Example:
        @filter_output(PiiFilter())
        async def generate():
            return "some data with email@example.com"
    """
    composite = CompositeFilter(list(filters))
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            result = await func(*args, **kwargs)
            
            filter_result = await composite.filter(result)
            if filter_result.blocked:
                raise FilterBlockedError(f"Output blocked: {filter_result.modifications}")
            
            return filter_result.data
        
        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            result = func(*args, **kwargs)
            
            filter_result = asyncio.run(composite.filter(result))
            if filter_result.blocked:
                raise FilterBlockedError(f"Output blocked: {filter_result.modifications}")
            
            return filter_result.data
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


__all__ = [
    # Exceptions
    "FilterError",
    "FilterBlockedError",
    # Enums
    "FilterAction",
    # Data classes
    "FilterResult",
    # Filters
    "Filter",
    "PiiFilter",
    "ContentFilter",
    "LengthFilter",
    "JsonFilter",
    "RegexFilter",
    "CompositeFilter",
    # Pipeline
    "FilterPipeline",
    "FilterMiddleware",
    # Decorators
    "filter_input",
    "filter_output",
]
