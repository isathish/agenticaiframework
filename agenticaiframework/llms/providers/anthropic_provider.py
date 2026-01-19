"""
Anthropic Provider Adapter.

Provides integration with Anthropic's Claude API including:
- Claude 3.5, Claude 3 models
- Tool use
- Streaming
"""

import os
import logging
from typing import Any, Dict, Iterator, List, Optional

from .base import BaseLLMProvider, LLMMessage, LLMResponse, ProviderConfig

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseLLMProvider):
    """
    Anthropic Claude API provider adapter.
    
    Auto-configures from environment:
    - ANTHROPIC_API_KEY
    - ANTHROPIC_API_BASE (optional)
    
    Example:
        >>> provider = AnthropicProvider.from_env()
        >>> response = provider.generate("Hello, world!")
        >>> print(response.content)
    """
    
    DEFAULT_MODEL = "claude-sonnet-4-20250514"
    
    SUPPORTED_MODELS = [
        "claude-sonnet-4-20250514",
        "claude-opus-4-20250514",
        "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-20241022",
        "claude-3-opus-20240229",
        "claude-3-sonnet-20240229",
        "claude-3-haiku-20240307",
    ]
    
    def __init__(self, config: Optional[ProviderConfig] = None):
        super().__init__(config)
        if self.config.default_model is None:
            self.config.default_model = self.DEFAULT_MODEL
    
    @classmethod
    def from_env(cls, model: Optional[str] = None) -> 'AnthropicProvider':
        """Create provider from environment variables."""
        config = ProviderConfig(
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            api_base=os.getenv("ANTHROPIC_API_BASE"),
            default_model=model or os.getenv("ANTHROPIC_MODEL", cls.DEFAULT_MODEL),
            timeout=float(os.getenv("ANTHROPIC_TIMEOUT", "60")),
            max_retries=int(os.getenv("ANTHROPIC_MAX_RETRIES", "3")),
        )
        return cls(config)
    
    @property
    def provider_name(self) -> str:
        return "anthropic"
    
    @property
    def supported_models(self) -> List[str]:
        return self.SUPPORTED_MODELS
    
    def _initialize_client(self) -> None:
        """Initialize Anthropic client."""
        try:
            from anthropic import Anthropic
            
            kwargs = {"api_key": self.config.api_key}
            if self.config.api_base:
                kwargs["base_url"] = self.config.api_base
            if self.config.timeout:
                kwargs["timeout"] = self.config.timeout
            if self.config.max_retries:
                kwargs["max_retries"] = self.config.max_retries
            
            self._client = Anthropic(**kwargs)
            logger.info("Anthropic client initialized")
        except ImportError:
            raise ImportError(
                "Anthropic package not installed. Install with: pip install anthropic"
            )
        except Exception as e:
            logger.error("Failed to initialize Anthropic client: %s", e)
            raise
    
    def generate(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = 4096,
        stop: Optional[List[str]] = None,
        **kwargs,
    ) -> LLMResponse:
        """Generate text using Anthropic API."""
        self._ensure_initialized()
        
        model = model or self.config.default_model
        
        request_kwargs = {
            "model": model,
            "max_tokens": max_tokens or 4096,
            "messages": [{"role": "user", "content": prompt}],
        }
        
        # Temperature only for non-o1 models
        if temperature is not None:
            request_kwargs["temperature"] = temperature
        
        if stop:
            request_kwargs["stop_sequences"] = stop
        
        # Handle system prompt
        if "system_prompt" in kwargs:
            request_kwargs["system"] = kwargs.pop("system_prompt")
        
        try:
            response = self._client.messages.create(**request_kwargs)
            
            content = ""
            if response.content:
                for block in response.content:
                    if hasattr(block, 'text'):
                        content += block.text
            
            return LLMResponse(
                content=content,
                model=response.model,
                provider=self.provider_name,
                finish_reason=response.stop_reason or "stop",
                usage={
                    "prompt_tokens": response.usage.input_tokens if response.usage else 0,
                    "completion_tokens": response.usage.output_tokens if response.usage else 0,
                    "total_tokens": (
                        (response.usage.input_tokens + response.usage.output_tokens)
                        if response.usage else 0
                    ),
                },
                raw_response=response,
            )
        except Exception as e:
            logger.error("Anthropic generation failed: %s", e)
            raise
    
    def generate_chat(
        self,
        messages: List[LLMMessage],
        *,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = 4096,
        **kwargs,
    ) -> LLMResponse:
        """Generate from chat messages."""
        self._ensure_initialized()
        
        model = model or self.config.default_model
        
        # Convert messages, handling system separately
        anthropic_messages = []
        system_prompt = None
        
        for m in messages:
            if m.role == "system":
                system_prompt = m.content
            else:
                anthropic_messages.append({
                    "role": m.role,
                    "content": m.content,
                })
        
        request_kwargs = {
            "model": model,
            "max_tokens": max_tokens or 4096,
            "messages": anthropic_messages,
            "temperature": temperature,
        }
        
        if system_prompt:
            request_kwargs["system"] = system_prompt
        
        try:
            response = self._client.messages.create(**request_kwargs)
            
            content = ""
            tool_calls = None
            
            for block in response.content:
                if hasattr(block, 'text'):
                    content += block.text
                elif hasattr(block, 'type') and block.type == 'tool_use':
                    if tool_calls is None:
                        tool_calls = []
                    tool_calls.append({
                        "id": block.id,
                        "type": "function",
                        "function": {
                            "name": block.name,
                            "arguments": str(block.input),
                        }
                    })
            
            return LLMResponse(
                content=content,
                model=response.model,
                provider=self.provider_name,
                finish_reason=response.stop_reason or "stop",
                tool_calls=tool_calls,
                usage={
                    "prompt_tokens": response.usage.input_tokens if response.usage else 0,
                    "completion_tokens": response.usage.output_tokens if response.usage else 0,
                    "total_tokens": (
                        (response.usage.input_tokens + response.usage.output_tokens)
                        if response.usage else 0
                    ),
                },
                raw_response=response,
            )
        except Exception as e:
            logger.error("Anthropic chat generation failed: %s", e)
            raise
    
    def generate_with_tools(
        self,
        prompt: str,
        tools: List[Dict[str, Any]],
        *,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = 4096,
        **kwargs,
    ) -> LLMResponse:
        """Generate with tool use."""
        self._ensure_initialized()
        
        model = model or self.config.default_model
        
        # Convert OpenAI-style tools to Anthropic format
        anthropic_tools = []
        for tool in tools:
            if "function" in tool:
                func = tool["function"]
                anthropic_tools.append({
                    "name": func["name"],
                    "description": func.get("description", ""),
                    "input_schema": func.get("parameters", {"type": "object", "properties": {}}),
                })
            else:
                anthropic_tools.append({
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "input_schema": tool.get("parameters", {"type": "object", "properties": {}}),
                })
        
        request_kwargs = {
            "model": model,
            "max_tokens": max_tokens or 4096,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
        }
        
        if anthropic_tools:
            request_kwargs["tools"] = anthropic_tools
        
        if "system_prompt" in kwargs:
            request_kwargs["system"] = kwargs.pop("system_prompt")
        
        try:
            response = self._client.messages.create(**request_kwargs)
            
            content = ""
            tool_calls = None
            
            for block in response.content:
                if hasattr(block, 'text'):
                    content += block.text
                elif hasattr(block, 'type') and block.type == 'tool_use':
                    if tool_calls is None:
                        tool_calls = []
                    import json
                    tool_calls.append({
                        "id": block.id,
                        "type": "function",
                        "function": {
                            "name": block.name,
                            "arguments": json.dumps(block.input) if isinstance(block.input, dict) else str(block.input),
                        }
                    })
            
            return LLMResponse(
                content=content,
                model=response.model,
                provider=self.provider_name,
                finish_reason=response.stop_reason or "stop",
                tool_calls=tool_calls,
                usage={
                    "prompt_tokens": response.usage.input_tokens if response.usage else 0,
                    "completion_tokens": response.usage.output_tokens if response.usage else 0,
                    "total_tokens": (
                        (response.usage.input_tokens + response.usage.output_tokens)
                        if response.usage else 0
                    ),
                },
                raw_response=response,
            )
        except Exception as e:
            logger.error("Anthropic tool generation failed: %s", e)
            raise
    
    def stream(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = 4096,
        **kwargs,
    ) -> Iterator[str]:
        """Stream tokens as they are generated."""
        self._ensure_initialized()
        
        model = model or self.config.default_model
        
        request_kwargs = {
            "model": model,
            "max_tokens": max_tokens or 4096,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
        }
        
        if "system_prompt" in kwargs:
            request_kwargs["system"] = kwargs.pop("system_prompt")
        
        try:
            with self._client.messages.stream(**request_kwargs) as stream:
                for text in stream.text_stream:
                    yield text
        except Exception as e:
            logger.error("Anthropic streaming failed: %s", e)
            raise
    
    def count_tokens(self, text: str, model: Optional[str] = None) -> int:
        """Count tokens (rough estimate for Claude)."""
        # Claude uses a different tokenizer, rough estimate
        # ~3.5 characters per token for English
        return len(text) // 4


__all__ = ['AnthropicProvider']
