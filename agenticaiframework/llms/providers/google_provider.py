"""
Google Gemini Provider Adapter.

Provides integration with Google's Gemini API including:
- Gemini 2.0, 1.5 models
- Function calling
- Streaming
"""

import os
import logging
from typing import Any, Dict, Iterator, List, Optional

from .base import BaseLLMProvider, LLMMessage, LLMResponse, ProviderConfig

logger = logging.getLogger(__name__)


class GoogleProvider(BaseLLMProvider):
    """
    Google Gemini API provider adapter.
    
    Auto-configures from environment:
    - GOOGLE_API_KEY or GEMINI_API_KEY
    
    Example:
        >>> provider = GoogleProvider.from_env()
        >>> response = provider.generate("Hello, world!")
        >>> print(response.content)
    """
    
    DEFAULT_MODEL = "gemini-2.0-flash"
    
    SUPPORTED_MODELS = [
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-1.5-pro",
        "gemini-1.5-flash",
        "gemini-1.5-flash-8b",
    ]
    
    def __init__(self, config: Optional[ProviderConfig] = None):
        super().__init__(config)
        if self.config.default_model is None:
            self.config.default_model = self.DEFAULT_MODEL
    
    @classmethod
    def from_env(cls, model: Optional[str] = None) -> 'GoogleProvider':
        """Create provider from environment variables."""
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        config = ProviderConfig(
            api_key=api_key,
            default_model=model or os.getenv("GEMINI_MODEL", cls.DEFAULT_MODEL),
            timeout=float(os.getenv("GEMINI_TIMEOUT", "60")),
        )
        return cls(config)
    
    @property
    def provider_name(self) -> str:
        return "google"
    
    @property
    def supported_models(self) -> List[str]:
        return self.SUPPORTED_MODELS
    
    def _initialize_client(self) -> None:
        """Initialize Google Generative AI client."""
        try:
            import google.generativeai as genai
            
            genai.configure(api_key=self.config.api_key)
            self._genai = genai
            self._client = genai.GenerativeModel(self.config.default_model)
            logger.info("Google Gemini client initialized")
        except ImportError:
            raise ImportError(
                "Google Generative AI package not installed. "
                "Install with: pip install google-generativeai"
            )
        except Exception as e:
            logger.error("Failed to initialize Google client: %s", e)
            raise
    
    def _get_model(self, model: Optional[str] = None):
        """Get or create model instance."""
        model_name = model or self.config.default_model
        if model and model != self.config.default_model:
            return self._genai.GenerativeModel(model_name)
        return self._client
    
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
        """Generate text using Gemini API."""
        self._ensure_initialized()
        
        client = self._get_model(model)
        
        generation_config = {
            "temperature": temperature,
        }
        if max_tokens:
            generation_config["max_output_tokens"] = max_tokens
        if stop:
            generation_config["stop_sequences"] = stop
        
        try:
            response = client.generate_content(
                prompt,
                generation_config=generation_config,
            )
            
            # Extract text from response
            content = ""
            if response.text:
                content = response.text
            elif response.parts:
                content = "".join(part.text for part in response.parts if hasattr(part, 'text'))
            
            # Get usage if available
            usage = {}
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                usage = {
                    "prompt_tokens": response.usage_metadata.prompt_token_count,
                    "completion_tokens": response.usage_metadata.candidates_token_count,
                    "total_tokens": response.usage_metadata.total_token_count,
                }
            
            return LLMResponse(
                content=content,
                model=model or self.config.default_model,
                provider=self.provider_name,
                finish_reason="stop",
                usage=usage,
                raw_response=response,
            )
        except Exception as e:
            logger.error("Gemini generation failed: %s", e)
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
        
        client = self._get_model(model)
        
        # Convert messages to Gemini format
        gemini_history = []
        system_instruction = None
        
        for m in messages[:-1]:  # All but last
            if m.role == "system":
                system_instruction = m.content
            else:
                role = "user" if m.role == "user" else "model"
                gemini_history.append({
                    "role": role,
                    "parts": [{"text": m.content}],
                })
        
        # Get the last message as the prompt
        last_message = messages[-1] if messages else None
        prompt = last_message.content if last_message else ""
        
        generation_config = {"temperature": temperature}
        if max_tokens:
            generation_config["max_output_tokens"] = max_tokens
        
        try:
            # Create chat if there's history
            if gemini_history:
                chat = client.start_chat(history=gemini_history)
                response = chat.send_message(
                    prompt,
                    generation_config=generation_config,
                )
            else:
                response = client.generate_content(
                    prompt,
                    generation_config=generation_config,
                )
            
            content = response.text if response.text else ""
            
            usage = {}
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                usage = {
                    "prompt_tokens": response.usage_metadata.prompt_token_count,
                    "completion_tokens": response.usage_metadata.candidates_token_count,
                    "total_tokens": response.usage_metadata.total_token_count,
                }
            
            return LLMResponse(
                content=content,
                model=model or self.config.default_model,
                provider=self.provider_name,
                finish_reason="stop",
                usage=usage,
                raw_response=response,
            )
        except Exception as e:
            logger.error("Gemini chat generation failed: %s", e)
            raise
    
    def generate_with_tools(
        self,
        prompt: str,
        tools: List[Dict[str, Any]],
        *,
        model: Optional[str] = None,
        temperature: float = 0.7,
        **kwargs,
    ) -> LLMResponse:
        """Generate with function calling."""
        self._ensure_initialized()
        
        # Convert OpenAI-style tools to Gemini format
        gemini_tools = []
        for tool in tools:
            func = tool.get("function", tool)
            gemini_tools.append({
                "name": func["name"],
                "description": func.get("description", ""),
                "parameters": func.get("parameters", {"type": "object", "properties": {}}),
            })
        
        try:
            # Create model with tools
            client = self._genai.GenerativeModel(
                model or self.config.default_model,
                tools=gemini_tools if gemini_tools else None,
            )
            
            response = client.generate_content(
                prompt,
                generation_config={"temperature": temperature},
            )
            
            content = ""
            tool_calls = None
            
            if response.parts:
                for part in response.parts:
                    if hasattr(part, 'text') and part.text:
                        content += part.text
                    if hasattr(part, 'function_call') and part.function_call:
                        if tool_calls is None:
                            tool_calls = []
                        import json
                        tool_calls.append({
                            "id": f"call_{len(tool_calls)}",
                            "type": "function",
                            "function": {
                                "name": part.function_call.name,
                                "arguments": json.dumps(dict(part.function_call.args)),
                            }
                        })
            
            return LLMResponse(
                content=content,
                model=model or self.config.default_model,
                provider=self.provider_name,
                finish_reason="stop",
                tool_calls=tool_calls,
                raw_response=response,
            )
        except Exception as e:
            logger.error("Gemini tool generation failed: %s", e)
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
        
        client = self._get_model(model)
        
        try:
            response = client.generate_content(
                prompt,
                generation_config={"temperature": temperature},
                stream=True,
            )
            
            for chunk in response:
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            logger.error("Gemini streaming failed: %s", e)
            raise


__all__ = ['GoogleProvider']
