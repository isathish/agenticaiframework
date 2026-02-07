"""
LLM Manager.

Enhanced LLM Manager with reliability and monitoring features:
- Model registry with metadata
- Retry with exponential backoff
- Circuit breaker pattern
- Response caching
- Token usage tracking
- Fallback chain
- Performance metrics
- Auto-configuration from environment variables
"""

import os
import time
import hashlib
import logging
from typing import Dict, Any, Callable, Optional, List, TYPE_CHECKING
from collections import defaultdict

from .circuit_breaker import CircuitBreaker
from ..exceptions import CircuitBreakerOpenError

if TYPE_CHECKING:
    from .providers import BaseLLMProvider

logger = logging.getLogger(__name__)


class LLMManager:
    """
    Enhanced LLM Manager with reliability and monitoring features.
    
    Features:
    - Model registry with metadata
    - Retry with exponential backoff
    - Circuit breaker pattern
    - Response caching
    - Token usage tracking
    - Fallback chain
    - Performance metrics
    """
    
    def __init__(self, 
                 max_retries: int = 3,
                 enable_caching: bool = True):
        self.models: Dict[str, Callable[[str, Dict[str, Any]], str]] = {}
        self.model_metadata: Dict[str, Dict[str, Any]] = {}
        self.active_model: Optional[str] = None
        self.fallback_chain: List[str] = []
        
        # Features
        self.max_retries = max_retries
        self.enable_caching = enable_caching
        
        # Circuit breakers per model
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        # Response cache
        self.cache: Dict[str, Any] = {}
        
        # Metrics
        self.metrics = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'cache_hits': 0,
            'total_retries': 0,
            'total_tokens': 0
        }
        
        self.model_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            'requests': 0,
            'successes': 0,
            'failures': 0,
            'total_latency': 0.0,
            'avg_latency': 0.0
        })

    def register_model(self, 
                      name: str, 
                      inference_fn: Callable[[str, Dict[str, Any]], str],
                      metadata: Dict[str, Any] = None):
        """
        Register an LLM model.
        
        Args:
            name: Model name
            inference_fn: Function to call for inference
            metadata: Model metadata (max_tokens, cost_per_token, etc.)
        """
        self.models[name] = inference_fn
        self.model_metadata[name] = metadata or {}
        self.circuit_breakers[name] = CircuitBreaker()
        self._log(f"Registered LLM model '{name}'")

    def set_active_model(self, name: str):
        """Set the active model."""
        if name in self.models:
            self.active_model = name
            self._log(f"Active LLM model set to '{name}'")
        else:
            self._log(f"Model '{name}' not found")
    
    def set_fallback_chain(self, model_names: List[str]):
        """
        Set fallback chain for model failures.
        
        Args:
            model_names: List of model names in order of preference
        """
        valid_models = [name for name in model_names if name in self.models]
        self.fallback_chain = valid_models
        self._log(f"Set fallback chain: {valid_models}")

    @classmethod
    def from_environment(
        cls,
        auto_select: bool = True,
        preferred_provider: Optional[str] = None,
    ) -> 'LLMManager':
        """
        Create LLMManager auto-configured from environment variables.
        
        Detects and registers providers based on available API keys:
        - OPENAI_API_KEY -> OpenAI models
        - ANTHROPIC_API_KEY -> Anthropic Claude models
        - GOOGLE_API_KEY / GEMINI_API_KEY -> Google Gemini models
        
        Args:
            auto_select: Automatically set the first available as active
            preferred_provider: Preferred provider ('openai', 'anthropic', 'google')
            
        Returns:
            Configured LLMManager instance
            
        Example:
            >>> llm = LLMManager.from_environment()
            >>> response = llm.generate("Hello, world!")
        """
        from .providers import (
            OpenAIProvider,
            AnthropicProvider,
            GoogleProvider,
        )
        
        manager = cls()
        registered = []
        
        # Register OpenAI if available
        if os.getenv("OPENAI_API_KEY"):
            provider = OpenAIProvider.from_env()
            manager.register_provider(provider, "openai")
            registered.append("openai")
        
        # Register Anthropic if available
        if os.getenv("ANTHROPIC_API_KEY"):
            provider = AnthropicProvider.from_env()
            manager.register_provider(provider, "anthropic")
            registered.append("anthropic")
        
        # Register Google if available
        if os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"):
            provider = GoogleProvider.from_env()
            manager.register_provider(provider, "google")
            registered.append("google")
        
        if not registered:
            logger.warning(
                "No LLM provider API keys found. "
                "Set OPENAI_API_KEY, ANTHROPIC_API_KEY, or GOOGLE_API_KEY"
            )
            return manager
        
        # Set active model
        if auto_select:
            if preferred_provider and preferred_provider in registered:
                manager.set_active_model(preferred_provider)
            else:
                manager.set_active_model(registered[0])
        
        # Set fallback chain
        manager.set_fallback_chain(registered)
        
        logger.info("LLMManager configured with providers: %s", registered)
        return manager

    def register_provider(
        self,
        provider: 'BaseLLMProvider',
        name: Optional[str] = None,
    ) -> None:
        """
        Register an LLM provider adapter.
        
        Args:
            provider: Provider instance (OpenAIProvider, AnthropicProvider, etc.)
            name: Name to register under (defaults to provider_name)
            
        Example:
            >>> from agenticaiframework.llms.providers import OpenAIProvider
            >>> provider = OpenAIProvider.from_env()
            >>> llm.register_provider(provider)
        """
        name = name or provider.provider_name
        
        # Create inference function wrapper
        def inference_fn(prompt: str, kwargs: Dict[str, Any]) -> str:
            response = provider.generate(prompt, **kwargs)
            return response.content
        
        # Get metadata from provider
        metadata = {
            'provider': provider.provider_name,
            'default_model': provider.config.default_model,
            'supported_models': provider.supported_models,
        }
        
        self.register_model(name, inference_fn, metadata)
        
        # Store provider reference for advanced features
        if not hasattr(self, '_providers'):
            self._providers: Dict[str, 'BaseLLMProvider'] = {}
        self._providers[name] = provider

    def get_provider(self, name: str) -> Optional['BaseLLMProvider']:
        """Get a registered provider by name."""
        if hasattr(self, '_providers'):
            return self._providers.get(name)
        return None

    def generate(self, 
                prompt: str, 
                use_cache: bool = True,
                **kwargs) -> Optional[str]:
        """
        Generate response with retry and fallback.
        
        Args:
            prompt: Input prompt
            use_cache: Whether to use response cache
            **kwargs: Additional parameters
            
        Returns:
            Generated response or None
        """
        if not self.active_model:
            self._log("No active model set")
            return None
        
        self.metrics['total_requests'] += 1
        
        # Check cache
        if use_cache and self.enable_caching:
            cache_key = self._get_cache_key(prompt, kwargs)
            if cache_key in self.cache:
                self.metrics['cache_hits'] += 1
                self._log("Cache hit for prompt")
                return self.cache[cache_key]
        
        # Try active model with fallback chain
        models_to_try = [self.active_model] + self.fallback_chain
        models_to_try = list(dict.fromkeys(models_to_try))  # Remove duplicates
        
        for model_name in models_to_try:
            result = self._generate_with_retry(model_name, prompt, **kwargs)
            
            if result is not None:
                # Cache successful response
                if self.enable_caching:
                    cache_key = self._get_cache_key(prompt, kwargs)
                    self.cache[cache_key] = result
                
                self.metrics['successful_requests'] += 1
                return result
            
            self._log(f"Model '{model_name}' failed, trying next in chain")
        
        # All models failed
        self.metrics['failed_requests'] += 1
        self._log("All models in chain failed")
        return None
    
    def _generate_with_retry(self, 
                            model_name: str,
                            prompt: str,
                            **kwargs) -> Optional[str]:
        """Generate with exponential backoff retry."""
        circuit_breaker = self.circuit_breakers[model_name]
        stats = self.model_stats[model_name]
        stats['requests'] += 1
        
        for attempt in range(self.max_retries):
            try:
                start_time = time.time()
                
                # Use circuit breaker
                result = circuit_breaker.call(
                    self.models[model_name],
                    prompt,
                    kwargs
                )
                
                # Update metrics
                latency = time.time() - start_time
                stats['successes'] += 1
                stats['total_latency'] += latency
                stats['avg_latency'] = stats['total_latency'] / stats['successes']
                
                # Estimate tokens (rough approximation)
                estimated_tokens = len(prompt.split()) + len(str(result).split())
                self.metrics['total_tokens'] += estimated_tokens
                
                return result
                
            except CircuitBreakerOpenError:
                stats['failures'] += 1
                self._log(f"Circuit breaker OPEN for model '{model_name}'")
                return None
            except (TypeError, ValueError, KeyError, AttributeError, RuntimeError) as e:
                stats['failures'] += 1
                self.metrics['total_retries'] += 1
                
                if attempt < self.max_retries - 1:
                    # Exponential backoff
                    wait_time = 2 ** attempt
                    self._log(f"Attempt {attempt + 1} failed, retrying in {wait_time}s: {e}")
                    time.sleep(wait_time)
                else:
                    self._log(f"All {self.max_retries} attempts failed for model '{model_name}': {e}")
            except Exception as e:  # noqa: BLE001 - Catch-all for unknown inference errors
                stats['failures'] += 1
                self.metrics['total_retries'] += 1
                self._log(f"Unexpected error for model '{model_name}': {e}")
                if attempt >= self.max_retries - 1:
                    break
        
        return None
    
    def _get_cache_key(self, prompt: str, kwargs: Dict[str, Any]) -> str:
        """Generate cache key from prompt and parameters."""
        # Create deterministic hash
        cache_string = f"{prompt}:{sorted(kwargs.items())}"
        return hashlib.md5(cache_string.encode()).hexdigest()
    
    def clear_cache(self):
        """Clear response cache."""
        self.cache.clear()
        self._log("Cleared response cache")
    
    def get_model_info(self, model_name: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific model."""
        if model_name not in self.models:
            return None
        
        return {
            'name': model_name,
            'metadata': self.model_metadata.get(model_name, {}),
            'stats': dict(self.model_stats[model_name]),
            'circuit_breaker_state': self.circuit_breakers[model_name].state
        }
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get overall metrics."""
        success_rate = 0.0
        if self.metrics['total_requests'] > 0:
            success_rate = self.metrics['successful_requests'] / self.metrics['total_requests']
        
        cache_hit_rate = 0.0
        if self.metrics['total_requests'] > 0:
            cache_hit_rate = self.metrics['cache_hits'] / self.metrics['total_requests']
        
        return {
            **self.metrics,
            'success_rate': success_rate,
            'cache_hit_rate': cache_hit_rate,
            'active_model': self.active_model,
            'fallback_chain': self.fallback_chain
        }
    
    def reset_circuit_breaker(self, model_name: str):
        """Manually reset circuit breaker for a model."""
        if model_name in self.circuit_breakers:
            self.circuit_breakers[model_name].reset()
            self._log(f"Reset circuit breaker for model '{model_name}'")

    def list_models(self) -> List[str]:
        """List all registered models."""
        return list(self.models.keys())

    def _log(self, message: str):
        """Log a message."""
        logger.info("[LLMManager] %s", message)


__all__ = ['LLMManager']
