"""
LLM Provider Base Interface.

Defines the common interface for all LLM provider adapters.
"""

import os
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, Iterator, List, Optional, Union

logger = logging.getLogger(__name__)


@dataclass
class LLMMessage:
    """Represents a message in a conversation."""
    role: str  # 'system', 'user', 'assistant', 'tool'
    content: str
    name: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        d = {'role': self.role, 'content': self.content}
        if self.name:
            d['name'] = self.name
        if self.tool_call_id:
            d['tool_call_id'] = self.tool_call_id
        if self.tool_calls:
            d['tool_calls'] = self.tool_calls
        return d


@dataclass
class LLMResponse:
    """Standardized response from LLM providers."""
    content: str
    model: str
    provider: str
    finish_reason: str = "stop"
    tool_calls: Optional[List[Dict[str, Any]]] = None
    usage: Dict[str, int] = field(default_factory=dict)
    raw_response: Optional[Any] = None
    
    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)


@dataclass
class ProviderConfig:
    """Configuration for an LLM provider."""
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    organization: Optional[str] = None
    default_model: Optional[str] = None
    timeout: float = 60.0
    max_retries: int = 3
    extra: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_env(cls, prefix: str = "") -> 'ProviderConfig':
        """Create config from environment variables."""
        return cls(
            api_key=os.getenv(f"{prefix}API_KEY"),
            api_base=os.getenv(f"{prefix}API_BASE"),
            organization=os.getenv(f"{prefix}ORGANIZATION"),
            default_model=os.getenv(f"{prefix}DEFAULT_MODEL"),
            timeout=float(os.getenv(f"{prefix}TIMEOUT", "60")),
            max_retries=int(os.getenv(f"{prefix}MAX_RETRIES", "3")),
        )


class BaseLLMProvider(ABC):
    """
    Base class for LLM provider adapters.
    
    All providers must implement:
    - generate(): Synchronous text generation
    - generate_with_tools(): Tool-augmented generation
    
    Optional:
    - stream(): Streaming generation
    - agenerate(): Async generation
    """
    
    def __init__(self, config: Optional[ProviderConfig] = None):
        self.config = config or ProviderConfig()
        self._client: Any = None
        self._initialized = False
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the provider (e.g., 'openai', 'anthropic')."""
        pass
    
    @property
    @abstractmethod
    def supported_models(self) -> List[str]:
        """List of supported model identifiers."""
        pass
    
    @abstractmethod
    def _initialize_client(self) -> None:
        """Initialize the provider's client library."""
        pass
    
    def _ensure_initialized(self) -> None:
        """Ensure the client is initialized."""
        if not self._initialized:
            self._initialize_client()
            self._initialized = True
    
    @abstractmethod
    def generate(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stop: Optional[List[str]] = None,
        **kwargs,
    ) -> LLMResponse:
        """
        Generate a response from the LLM.
        
        Args:
            prompt: The input prompt
            model: Model to use (defaults to config.default_model)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            stop: Stop sequences
            **kwargs: Provider-specific parameters
            
        Returns:
            LLMResponse with the generated content
        """
        pass
    
    @abstractmethod
    def generate_with_tools(
        self,
        prompt: str,
        tools: List[Dict[str, Any]],
        *,
        model: Optional[str] = None,
        temperature: float = 0.7,
        **kwargs,
    ) -> LLMResponse:
        """
        Generate a response with tool/function calling support.
        
        Args:
            prompt: The input prompt
            tools: List of tool schemas (OpenAI function format)
            model: Model to use
            temperature: Sampling temperature
            **kwargs: Provider-specific parameters
            
        Returns:
            LLMResponse with content and/or tool_calls
        """
        pass
    
    def generate_chat(
        self,
        messages: List[LLMMessage],
        *,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> LLMResponse:
        """
        Generate from a list of messages (chat format).
        
        Default implementation converts to single prompt.
        Override for native chat support.
        """
        # Simple conversion - providers should override
        prompt = "\n".join(f"{m.role}: {m.content}" for m in messages)
        return self.generate(prompt, model=model, temperature=temperature, 
                           max_tokens=max_tokens, **kwargs)
    
    def stream(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        temperature: float = 0.7,
        **kwargs,
    ) -> Iterator[str]:
        """
        Stream tokens as they are generated.
        
        Default: yields complete response at once.
        Override for true streaming.
        """
        response = self.generate(prompt, model=model, temperature=temperature, **kwargs)
        yield response.content
    
    async def agenerate(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        temperature: float = 0.7,
        **kwargs,
    ) -> LLMResponse:
        """
        Async generation. Default runs sync in executor.
        Override for native async support.
        """
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, 
            lambda: self.generate(prompt, model=model, temperature=temperature, **kwargs)
        )
    
    def count_tokens(self, text: str, model: Optional[str] = None) -> int:
        """
        Count tokens in text. Default uses rough estimate.
        Override for accurate counting.
        """
        # Rough estimate: 1 token ≈ 4 characters
        return len(text) // 4
    
    def is_available(self) -> bool:
        """Check if the provider is configured and available."""
        return bool(self.config.api_key)
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(provider={self.provider_name})"


__all__ = [
    'LLMMessage',
    'LLMResponse', 
    'ProviderConfig',
    'BaseLLMProvider',
]
