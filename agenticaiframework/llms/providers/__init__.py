"""
LLM Provider Adapters.

Pre-built adapters for popular LLM providers with auto-configuration
from environment variables.

Supported Providers:
- OpenAI (GPT-4, GPT-4o, GPT-3.5)
- Anthropic (Claude 3.5, Claude 3)
- Google (Gemini 2.0, Gemini 1.5)

Usage:
    >>> from agenticaiframework.llms.providers import OpenAIProvider
    >>> provider = OpenAIProvider.from_env()
    >>> response = provider.generate("Hello!")
    
Or auto-detect from environment:
    >>> from agenticaiframework.llms.providers import auto_detect_provider
    >>> provider = auto_detect_provider()
"""

import os
import logging
from typing import List, Optional, Type

from .base import (
    BaseLLMProvider,
    LLMMessage,
    LLMResponse,
    ProviderConfig,
)
from .openai_provider import OpenAIProvider
from .anthropic_provider import AnthropicProvider
from .google_provider import GoogleProvider

logger = logging.getLogger(__name__)


# Provider detection order
PROVIDER_PRIORITY: List[Type[BaseLLMProvider]] = [
    OpenAIProvider,
    AnthropicProvider,
    GoogleProvider,
]

# Environment variable to provider mapping
ENV_TO_PROVIDER = {
    "OPENAI_API_KEY": OpenAIProvider,
    "ANTHROPIC_API_KEY": AnthropicProvider,
    "GOOGLE_API_KEY": GoogleProvider,
    "GEMINI_API_KEY": GoogleProvider,
}


def auto_detect_provider(
    preferred: Optional[str] = None,
) -> Optional[BaseLLMProvider]:
    """
    Auto-detect and create a provider from environment variables.
    
    Checks for API keys in order:
    1. OPENAI_API_KEY -> OpenAIProvider
    2. ANTHROPIC_API_KEY -> AnthropicProvider  
    3. GOOGLE_API_KEY or GEMINI_API_KEY -> GoogleProvider
    
    Args:
        preferred: Preferred provider name ('openai', 'anthropic', 'google')
        
    Returns:
        Configured provider or None if no API keys found
        
    Example:
        >>> provider = auto_detect_provider()
        >>> if provider:
        ...     response = provider.generate("Hello!")
    """
    # Check preferred first
    if preferred:
        preferred = preferred.lower()
        if preferred == "openai" and os.getenv("OPENAI_API_KEY"):
            return OpenAIProvider.from_env()
        elif preferred == "anthropic" and os.getenv("ANTHROPIC_API_KEY"):
            return AnthropicProvider.from_env()
        elif preferred in ("google", "gemini"):
            if os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"):
                return GoogleProvider.from_env()
    
    # Auto-detect from environment
    for env_var, provider_class in ENV_TO_PROVIDER.items():
        if os.getenv(env_var):
            logger.info("Auto-detected %s from %s", provider_class.__name__, env_var)
            return provider_class.from_env()
    
    logger.warning("No LLM provider API keys found in environment")
    return None


def get_provider(
    name: str,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    **kwargs,
) -> BaseLLMProvider:
    """
    Get a provider by name.
    
    Args:
        name: Provider name ('openai', 'anthropic', 'google')
        model: Default model to use
        api_key: API key (uses env var if not provided)
        **kwargs: Additional provider config
        
    Returns:
        Configured provider instance
        
    Raises:
        ValueError: If provider name is unknown
        
    Example:
        >>> provider = get_provider("openai", model="gpt-4o")
    """
    name = name.lower()
    
    if name == "openai":
        config = ProviderConfig(
            api_key=api_key or os.getenv("OPENAI_API_KEY"),
            default_model=model,
            **kwargs,
        )
        return OpenAIProvider(config)
    
    elif name == "anthropic":
        config = ProviderConfig(
            api_key=api_key or os.getenv("ANTHROPIC_API_KEY"),
            default_model=model,
            **kwargs,
        )
        return AnthropicProvider(config)
    
    elif name in ("google", "gemini"):
        config = ProviderConfig(
            api_key=api_key or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"),
            default_model=model,
            **kwargs,
        )
        return GoogleProvider(config)
    
    else:
        raise ValueError(
            f"Unknown provider: {name}. "
            f"Supported: openai, anthropic, google"
        )


def list_available_providers() -> List[str]:
    """
    List providers that have API keys configured.
    
    Returns:
        List of provider names with valid API keys
        
    Example:
        >>> available = list_available_providers()
        >>> print(available)  # ['openai', 'anthropic']
    """
    available = []
    
    if os.getenv("OPENAI_API_KEY"):
        available.append("openai")
    if os.getenv("ANTHROPIC_API_KEY"):
        available.append("anthropic")
    if os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"):
        available.append("google")
    
    return available


__all__ = [
    # Base classes
    "BaseLLMProvider",
    "LLMMessage",
    "LLMResponse",
    "ProviderConfig",
    # Providers
    "OpenAIProvider",
    "AnthropicProvider",
    "GoogleProvider",
    # Factory functions
    "auto_detect_provider",
    "get_provider",
    "list_available_providers",
]
