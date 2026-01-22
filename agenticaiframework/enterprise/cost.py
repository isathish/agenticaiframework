"""
Enterprise Cost Estimation - Token counting and cost tracking.

Provides accurate token counting, cost estimation,
and usage analytics for LLM operations.

Features:
- Token counting
- Cost estimation
- Usage tracking
- Budget management
- Cost reports
"""

import asyncio
import logging
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# Model Pricing
# =============================================================================

@dataclass
class ModelPricing:
    """Pricing for a model."""
    model_name: str
    input_cost_per_1k: float  # USD per 1K input tokens
    output_cost_per_1k: float  # USD per 1K output tokens
    
    # Optional additional costs
    image_cost: Optional[float] = None  # Per image
    audio_cost_per_minute: Optional[float] = None
    
    # Context window info
    max_context_tokens: int = 128000
    max_output_tokens: int = 4096


# Default pricing (as of late 2024, update as needed)
DEFAULT_PRICING = {
    # OpenAI
    "gpt-4o": ModelPricing("gpt-4o", 0.0025, 0.01, max_context_tokens=128000),
    "gpt-4o-mini": ModelPricing("gpt-4o-mini", 0.00015, 0.0006, max_context_tokens=128000),
    "gpt-4-turbo": ModelPricing("gpt-4-turbo", 0.01, 0.03, max_context_tokens=128000),
    "gpt-4": ModelPricing("gpt-4", 0.03, 0.06, max_context_tokens=8192),
    "gpt-3.5-turbo": ModelPricing("gpt-3.5-turbo", 0.0005, 0.0015, max_context_tokens=16385),
    "o1-preview": ModelPricing("o1-preview", 0.015, 0.06, max_context_tokens=128000),
    "o1-mini": ModelPricing("o1-mini", 0.003, 0.012, max_context_tokens=128000),
    
    # Azure OpenAI (same pricing)
    "gpt-4o-azure": ModelPricing("gpt-4o-azure", 0.0025, 0.01),
    
    # Anthropic Claude
    "claude-3-opus": ModelPricing("claude-3-opus", 0.015, 0.075, max_context_tokens=200000),
    "claude-3-sonnet": ModelPricing("claude-3-sonnet", 0.003, 0.015, max_context_tokens=200000),
    "claude-3-haiku": ModelPricing("claude-3-haiku", 0.00025, 0.00125, max_context_tokens=200000),
    "claude-3.5-sonnet": ModelPricing("claude-3.5-sonnet", 0.003, 0.015, max_context_tokens=200000),
    
    # Google
    "gemini-pro": ModelPricing("gemini-pro", 0.00025, 0.0005, max_context_tokens=32000),
    "gemini-1.5-pro": ModelPricing("gemini-1.5-pro", 0.00125, 0.005, max_context_tokens=1000000),
    "gemini-1.5-flash": ModelPricing("gemini-1.5-flash", 0.000075, 0.0003, max_context_tokens=1000000),
}


# =============================================================================
# Token Counter
# =============================================================================

class TokenCounter(ABC):
    """Abstract interface for token counting."""
    
    @abstractmethod
    def count(self, text: str, model: str = "gpt-4o") -> int:
        """Count tokens in text."""
        pass
    
    @abstractmethod
    def count_messages(self, messages: List[Dict], model: str = "gpt-4o") -> int:
        """Count tokens in message format."""
        pass


class TiktokenCounter(TokenCounter):
    """Token counter using tiktoken library."""
    
    def __init__(self):
        self._encoders: Dict[str, Any] = {}
    
    def _get_encoder(self, model: str):
        """Get encoder for model."""
        if model not in self._encoders:
            try:
                import tiktoken
                
                # Map model to encoding
                if "gpt-4" in model or "gpt-3.5" in model:
                    encoding_name = "cl100k_base"
                elif "o1" in model:
                    encoding_name = "o200k_base"
                else:
                    encoding_name = "cl100k_base"
                
                self._encoders[model] = tiktoken.get_encoding(encoding_name)
            except ImportError:
                # Fallback: rough estimate
                return None
        
        return self._encoders.get(model)
    
    def count(self, text: str, model: str = "gpt-4o") -> int:
        """Count tokens in text."""
        encoder = self._get_encoder(model)
        
        if encoder:
            return len(encoder.encode(text))
        else:
            # Fallback: rough estimate (~4 chars per token)
            return len(text) // 4
    
    def count_messages(self, messages: List[Dict], model: str = "gpt-4o") -> int:
        """Count tokens in messages."""
        total = 0
        
        for message in messages:
            # Message overhead
            total += 4  # <|start|>role\n, \n<|end|>
            
            if "content" in message:
                total += self.count(message["content"], model)
            
            if "role" in message:
                total += 1
            
            if "name" in message:
                total += self.count(message["name"], model) + 1
        
        total += 2  # <|start|>assistant
        
        return total


class ApproximateCounter(TokenCounter):
    """Approximate token counter (no dependencies)."""
    
    def __init__(self, chars_per_token: float = 4.0):
        self.chars_per_token = chars_per_token
    
    def count(self, text: str, model: str = "gpt-4o") -> int:
        """Approximate token count."""
        return int(len(text) / self.chars_per_token)
    
    def count_messages(self, messages: List[Dict], model: str = "gpt-4o") -> int:
        """Approximate message token count."""
        total = 0
        
        for message in messages:
            total += 5  # overhead
            if "content" in message:
                total += self.count(message["content"])
        
        return total


def get_token_counter() -> TokenCounter:
    """Get the best available token counter."""
    try:
        import tiktoken
        return TiktokenCounter()
    except ImportError:
        return ApproximateCounter()


# =============================================================================
# Usage Record
# =============================================================================

@dataclass
class UsageRecord:
    """Record of LLM usage."""
    id: str
    timestamp: datetime
    
    # Model
    model: str
    provider: str = "openai"
    
    # Tokens
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    
    # Cost
    input_cost: float = 0.0
    output_cost: float = 0.0
    total_cost: float = 0.0
    
    # Context
    agent_name: Optional[str] = None
    workflow_name: Optional[str] = None
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "model": self.model,
            "provider": self.provider,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "input_cost": self.input_cost,
            "output_cost": self.output_cost,
            "total_cost": self.total_cost,
            "agent_name": self.agent_name,
            "workflow_name": self.workflow_name,
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "metadata": self.metadata,
        }


# =============================================================================
# Cost Estimator
# =============================================================================

class CostEstimator:
    """
    Estimates costs for LLM operations.
    
    Usage:
        >>> estimator = CostEstimator()
        >>> 
        >>> # Estimate before call
        >>> estimate = estimator.estimate("Hello, world!", model="gpt-4o")
        >>> print(f"Estimated cost: ${estimate.estimated_cost:.4f}")
        >>> 
        >>> # Calculate actual cost
        >>> cost = estimator.calculate(
        ...     input_tokens=100,
        ...     output_tokens=50,
        ...     model="gpt-4o",
        ... )
    """
    
    def __init__(
        self,
        pricing: Dict[str, ModelPricing] = None,
        counter: TokenCounter = None,
    ):
        self.pricing = pricing or DEFAULT_PRICING
        self.counter = counter or get_token_counter()
    
    def get_pricing(self, model: str) -> ModelPricing:
        """Get pricing for a model."""
        # Try exact match
        if model in self.pricing:
            return self.pricing[model]
        
        # Try partial match
        for key, pricing in self.pricing.items():
            if key in model or model in key:
                return pricing
        
        # Default to gpt-4o pricing
        return self.pricing.get("gpt-4o", ModelPricing("unknown", 0.0025, 0.01))
    
    def count_tokens(self, text: str, model: str = "gpt-4o") -> int:
        """Count tokens in text."""
        return self.counter.count(text, model)
    
    def estimate(
        self,
        prompt: str,
        model: str = "gpt-4o",
        expected_output_tokens: int = None,
    ) -> "CostEstimate":
        """Estimate cost for a prompt."""
        pricing = self.get_pricing(model)
        input_tokens = self.count_tokens(prompt, model)
        
        # Estimate output tokens if not provided
        if expected_output_tokens is None:
            # Rough estimate: output is typically 0.5-2x input
            expected_output_tokens = input_tokens
        
        input_cost = (input_tokens / 1000) * pricing.input_cost_per_1k
        output_cost = (expected_output_tokens / 1000) * pricing.output_cost_per_1k
        
        return CostEstimate(
            model=model,
            input_tokens=input_tokens,
            expected_output_tokens=expected_output_tokens,
            input_cost=input_cost,
            estimated_output_cost=output_cost,
            estimated_total_cost=input_cost + output_cost,
        )
    
    def calculate(
        self,
        input_tokens: int,
        output_tokens: int,
        model: str = "gpt-4o",
    ) -> float:
        """Calculate actual cost."""
        pricing = self.get_pricing(model)
        
        input_cost = (input_tokens / 1000) * pricing.input_cost_per_1k
        output_cost = (output_tokens / 1000) * pricing.output_cost_per_1k
        
        return input_cost + output_cost
    
    def create_record(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        **kwargs,
    ) -> UsageRecord:
        """Create a usage record with cost calculation."""
        import uuid
        
        pricing = self.get_pricing(model)
        input_cost = (input_tokens / 1000) * pricing.input_cost_per_1k
        output_cost = (output_tokens / 1000) * pricing.output_cost_per_1k
        
        return UsageRecord(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            input_cost=input_cost,
            output_cost=output_cost,
            total_cost=input_cost + output_cost,
            **kwargs,
        )


@dataclass
class CostEstimate:
    """Cost estimation result."""
    model: str
    input_tokens: int
    expected_output_tokens: int
    input_cost: float
    estimated_output_cost: float
    estimated_total_cost: float


# =============================================================================
# Usage Tracker
# =============================================================================

class UsageTracker:
    """
    Tracks LLM usage and costs.
    
    Usage:
        >>> tracker = UsageTracker()
        >>> 
        >>> # Track usage
        >>> tracker.track(
        ...     model="gpt-4o",
        ...     input_tokens=100,
        ...     output_tokens=50,
        ...     agent_name="my-agent",
        ... )
        >>> 
        >>> # Get summary
        >>> summary = tracker.get_summary()
        >>> print(f"Total cost: ${summary.total_cost:.2f}")
    """
    
    def __init__(
        self,
        estimator: CostEstimator = None,
        max_records: int = 100000,
    ):
        self.estimator = estimator or CostEstimator()
        self.max_records = max_records
        
        self._records: List[UsageRecord] = []
        self._lock = threading.RLock()
        
        # Budget tracking
        self._budgets: Dict[str, float] = {}  # scope -> limit
        self._spent: Dict[str, float] = {}  # scope -> spent
    
    def track(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        **kwargs,
    ) -> UsageRecord:
        """Track a usage record."""
        record = self.estimator.create_record(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            **kwargs,
        )
        
        with self._lock:
            self._records.append(record)
            
            # Trim if needed
            if len(self._records) > self.max_records:
                self._records = self._records[-self.max_records // 2:]
            
            # Update spent tracking
            for scope in self._get_scopes(record):
                self._spent[scope] = self._spent.get(scope, 0) + record.total_cost
        
        return record
    
    def _get_scopes(self, record: UsageRecord) -> List[str]:
        """Get budget scopes for a record."""
        scopes = ["global"]
        
        if record.tenant_id:
            scopes.append(f"tenant:{record.tenant_id}")
        
        if record.user_id:
            scopes.append(f"user:{record.user_id}")
        
        if record.agent_name:
            scopes.append(f"agent:{record.agent_name}")
        
        return scopes
    
    def set_budget(self, scope: str, limit: float):
        """Set a budget limit for a scope."""
        self._budgets[scope] = limit
    
    def check_budget(self, scope: str) -> Tuple[bool, float, float]:
        """Check if budget is exceeded. Returns (within_budget, spent, limit)."""
        limit = self._budgets.get(scope)
        spent = self._spent.get(scope, 0)
        
        if limit is None:
            return (True, spent, float("inf"))
        
        return (spent < limit, spent, limit)
    
    def get_summary(
        self,
        start_time: datetime = None,
        end_time: datetime = None,
        model: str = None,
        tenant_id: str = None,
        agent_name: str = None,
    ) -> "UsageSummary":
        """Get usage summary."""
        records = self._filter_records(
            start_time, end_time, model, tenant_id, agent_name
        )
        
        if not records:
            return UsageSummary(
                total_requests=0,
                total_input_tokens=0,
                total_output_tokens=0,
                total_tokens=0,
                total_cost=0.0,
            )
        
        return UsageSummary(
            total_requests=len(records),
            total_input_tokens=sum(r.input_tokens for r in records),
            total_output_tokens=sum(r.output_tokens for r in records),
            total_tokens=sum(r.total_tokens for r in records),
            total_cost=sum(r.total_cost for r in records),
            avg_tokens_per_request=sum(r.total_tokens for r in records) / len(records),
            avg_cost_per_request=sum(r.total_cost for r in records) / len(records),
            models_used=list(set(r.model for r in records)),
            first_request=min(r.timestamp for r in records),
            last_request=max(r.timestamp for r in records),
        )
    
    def get_breakdown(
        self,
        group_by: str = "model",
        start_time: datetime = None,
        end_time: datetime = None,
    ) -> Dict[str, "UsageSummary"]:
        """Get usage breakdown by group."""
        records = self._filter_records(start_time, end_time)
        
        groups: Dict[str, List[UsageRecord]] = {}
        
        for record in records:
            if group_by == "model":
                key = record.model
            elif group_by == "agent":
                key = record.agent_name or "unknown"
            elif group_by == "tenant":
                key = record.tenant_id or "default"
            elif group_by == "user":
                key = record.user_id or "unknown"
            elif group_by == "day":
                key = record.timestamp.strftime("%Y-%m-%d")
            else:
                key = "all"
            
            if key not in groups:
                groups[key] = []
            groups[key].append(record)
        
        return {
            key: self._summarize(records)
            for key, records in groups.items()
        }
    
    def _filter_records(
        self,
        start_time: datetime = None,
        end_time: datetime = None,
        model: str = None,
        tenant_id: str = None,
        agent_name: str = None,
    ) -> List[UsageRecord]:
        """Filter records by criteria."""
        records = self._records
        
        if start_time:
            records = [r for r in records if r.timestamp >= start_time]
        
        if end_time:
            records = [r for r in records if r.timestamp <= end_time]
        
        if model:
            records = [r for r in records if r.model == model]
        
        if tenant_id:
            records = [r for r in records if r.tenant_id == tenant_id]
        
        if agent_name:
            records = [r for r in records if r.agent_name == agent_name]
        
        return records
    
    def _summarize(self, records: List[UsageRecord]) -> "UsageSummary":
        """Summarize a list of records."""
        if not records:
            return UsageSummary(0, 0, 0, 0, 0.0)
        
        return UsageSummary(
            total_requests=len(records),
            total_input_tokens=sum(r.input_tokens for r in records),
            total_output_tokens=sum(r.output_tokens for r in records),
            total_tokens=sum(r.total_tokens for r in records),
            total_cost=sum(r.total_cost for r in records),
        )
    
    def export(self, format: str = "json") -> str:
        """Export usage records."""
        import json
        
        if format == "json":
            return json.dumps([r.to_dict() for r in self._records], indent=2)
        elif format == "csv":
            import csv
            import io
            
            output = io.StringIO()
            if self._records:
                writer = csv.DictWriter(output, fieldnames=self._records[0].to_dict().keys())
                writer.writeheader()
                for record in self._records:
                    writer.writerow(record.to_dict())
            
            return output.getvalue()
        else:
            raise ValueError(f"Unsupported format: {format}")


@dataclass
class UsageSummary:
    """Summary of usage."""
    total_requests: int
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    total_cost: float
    
    avg_tokens_per_request: float = 0.0
    avg_cost_per_request: float = 0.0
    models_used: List[str] = field(default_factory=list)
    first_request: Optional[datetime] = None
    last_request: Optional[datetime] = None


# =============================================================================
# Global Tracker
# =============================================================================

_global_tracker: Optional[UsageTracker] = None
_lock = threading.Lock()


def get_usage_tracker() -> UsageTracker:
    """Get the global usage tracker."""
    global _global_tracker
    
    if _global_tracker is None:
        with _lock:
            if _global_tracker is None:
                _global_tracker = UsageTracker()
    
    return _global_tracker


def set_usage_tracker(tracker: UsageTracker):
    """Set the global usage tracker."""
    global _global_tracker
    _global_tracker = tracker


# Convenience functions
def track_usage(model: str, input_tokens: int, output_tokens: int, **kwargs) -> UsageRecord:
    """Track usage in global tracker."""
    return get_usage_tracker().track(model, input_tokens, output_tokens, **kwargs)


def get_usage_summary(**kwargs) -> UsageSummary:
    """Get summary from global tracker."""
    return get_usage_tracker().get_summary(**kwargs)


def estimate_cost(prompt: str, model: str = "gpt-4o") -> CostEstimate:
    """Estimate cost for a prompt."""
    return CostEstimator().estimate(prompt, model)


def count_tokens(text: str, model: str = "gpt-4o") -> int:
    """Count tokens in text."""
    return get_token_counter().count(text, model)
