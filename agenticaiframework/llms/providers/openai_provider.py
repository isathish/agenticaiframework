"""
OpenAI Provider Adapter.

Provides seamless integration with OpenAI's API including:
- GPT-4, GPT-4o, GPT-3.5 models
- Function/tool calling
- Streaming
- Token counting with tiktoken
"""

import os
import logging
from typing import Any, Dict, Iterator, List, Optional

from .base import BaseLLMProvider, LLMMessage, LLMResponse, ProviderConfig

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseLLMProvider):
    """
    OpenAI API provider adapter.
    
    Auto-configures from environment:
    - OPENAI_API_KEY
    - OPENAI_API_BASE (optional)
    - OPENAI_ORGANIZATION (optional)
    
    Example:
        >>> provider = OpenAIProvider.from_env()
        >>> response = provider.generate("Hello, world!")
        >>> print(response.content)
    """
    
    DEFAULT_MODEL = "gpt-4o"
    
    SUPPORTED_MODELS = [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
        "gpt-4",
        "gpt-3.5-turbo",
        "gpt-3.5-turbo-16k",
        "o1-preview",
        "o1-mini",
    ]
    
    def __init__(self, config: Optional[ProviderConfig] = None):
        super().__init__(config)
        if self.config.default_model is None:
            self.config.default_model = self.DEFAULT_MODEL
    
    @classmethod
    def from_env(cls, model: Optional[str] = None) -> 'OpenAIProvider':
        """Create provider from environment variables."""
        config = ProviderConfig(
            api_key=os.getenv("OPENAI_API_KEY"),
            api_base=os.getenv("OPENAI_API_BASE"),
            organization=os.getenv("OPENAI_ORGANIZATION"),
            default_model=model or os.getenv("OPENAI_MODEL", cls.DEFAULT_MODEL),
            timeout=float(os.getenv("OPENAI_TIMEOUT", "60")),
            max_retries=int(os.getenv("OPENAI_MAX_RETRIES", "3")),
        )
        return cls(config)
    
    @property
    def provider_name(self) -> str:
        return "openai"
    
    @property
    def supported_models(self) -> List[str]:
        return self.SUPPORTED_MODELS
    
    def _initialize_client(self) -> None:
        """Initialize OpenAI client."""
        try:
            from openai import OpenAI
            
            kwargs = {"api_key": self.config.api_key}
            if self.config.api_base:
                kwargs["base_url"] = self.config.api_base
            if self.config.organization:
                kwargs["organization"] = self.config.organization
            if self.config.timeout:
                kwargs["timeout"] = self.config.timeout
            if self.config.max_retries:
                kwargs["max_retries"] = self.config.max_retries
            
            self._client = OpenAI(**kwargs)
            logger.info("OpenAI client initialized")
        except ImportError:
            raise ImportError(
                "OpenAI package not installed. Install with: pip install openai"
            )
        except Exception as e:
            logger.error("Failed to initialize OpenAI client: %s", e)
            raise
    
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
        """Generate text using OpenAI API."""
        self._ensure_initialized()
        
        model = model or self.config.default_model
        
        messages = [{"role": "user", "content": prompt}]
        
        # Handle system prompt if provided
        if "system_prompt" in kwargs:
            messages.insert(0, {"role": "system", "content": kwargs.pop("system_prompt")})
        
        request_kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        
        if max_tokens:
            request_kwargs["max_tokens"] = max_tokens
        if stop:
            request_kwargs["stop"] = stop
        
        # Pass through additional kwargs
        for key in ["top_p", "frequency_penalty", "presence_penalty", "seed"]:
            if key in kwargs:
                request_kwargs[key] = kwargs[key]
        
        try:
            response = self._client.chat.completions.create(**request_kwargs)
            
            return LLMResponse(
                content=response.choices[0].message.content or "",
                model=response.model,
                provider=self.provider_name,
                finish_reason=response.choices[0].finish_reason,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0,
                },
                raw_response=response,
            )
        except Exception as e:
            logger.error("OpenAI generation failed: %s", e)
            raise
    
    def generate_chat(
        self,
        messages: List[LLMMessage],
        *,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> LLMResponse:
        """Generate from chat messages."""
        self._ensure_initialized()
        
        model = model or self.config.default_model
        
        # Convert to OpenAI format
        openai_messages = [m.to_dict() for m in messages]
        
        request_kwargs = {
            "model": model,
            "messages": openai_messages,
            "temperature": temperature,
        }
        
        if max_tokens:
            request_kwargs["max_tokens"] = max_tokens
        
        try:
            response = self._client.chat.completions.create(**request_kwargs)
            
            # Handle tool calls
            tool_calls = None
            message = response.choices[0].message
            if hasattr(message, 'tool_calls') and message.tool_calls:
                tool_calls = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        }
                    }
                    for tc in message.tool_calls
                ]
            
            return LLMResponse(
                content=message.content or "",
                model=response.model,
                provider=self.provider_name,
                finish_reason=response.choices[0].finish_reason,
                tool_calls=tool_calls,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0,
                },
                raw_response=response,
            )
        except Exception as e:
            logger.error("OpenAI chat generation failed: %s", e)
            raise
    
    def generate_with_tools(
        self,
        prompt: str,
        tools: List[Dict[str, Any]],
        *,
        model: Optional[str] = None,
        temperature: float = 0.7,
        tool_choice: str = "auto",
        **kwargs,
    ) -> LLMResponse:
        """Generate with function/tool calling."""
        self._ensure_initialized()
        
        model = model or self.config.default_model
        
        messages = [{"role": "user", "content": prompt}]
        
        if "system_prompt" in kwargs:
            messages.insert(0, {"role": "system", "content": kwargs.pop("system_prompt")})
        
        # Convert tools to OpenAI format if needed
        openai_tools = []
        for tool in tools:
            if "type" not in tool:
                openai_tools.append({
                    "type": "function",
                    "function": tool,
                })
            else:
                openai_tools.append(tool)
        
        try:
            response = self._client.chat.completions.create(
                model=model,
                messages=messages,
                tools=openai_tools if openai_tools else None,
                tool_choice=tool_choice if openai_tools else None,
                temperature=temperature,
            )
            
            message = response.choices[0].message
            tool_calls = None
            
            if hasattr(message, 'tool_calls') and message.tool_calls:
                tool_calls = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        }
                    }
                    for tc in message.tool_calls
                ]
            
            return LLMResponse(
                content=message.content or "",
                model=response.model,
                provider=self.provider_name,
                finish_reason=response.choices[0].finish_reason,
                tool_calls=tool_calls,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0,
                },
                raw_response=response,
            )
        except Exception as e:
            logger.error("OpenAI tool generation failed: %s", e)
            raise
    
    def stream(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        temperature: float = 0.7,
        **kwargs,
    ) -> Iterator[str]:
        """Stream tokens as they are generated."""
        self._ensure_initialized()
        
        model = model or self.config.default_model
        messages = [{"role": "user", "content": prompt}]
        
        if "system_prompt" in kwargs:
            messages.insert(0, {"role": "system", "content": kwargs.pop("system_prompt")})
        
        try:
            stream = self._client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                stream=True,
            )
            
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error("OpenAI streaming failed: %s", e)
            raise
    
    def count_tokens(self, text: str, model: Optional[str] = None) -> int:
        """Count tokens using tiktoken."""
        model = model or self.config.default_model
        
        try:
            import tiktoken
            
            try:
                encoding = tiktoken.encoding_for_model(model)
            except KeyError:
                encoding = tiktoken.get_encoding("cl100k_base")
            
            return len(encoding.encode(text))
        except ImportError:
            # Fallback to rough estimate
            return len(text) // 4


__all__ = ['OpenAIProvider']
