"""OpenAI Provider Adapter — stdlib-only implementation.

This module no longer requires the ``openai`` PyPI package. It uses the
framework's own REST client (``agenticaiframework._internal.clients.openai_rest``)
which talks to the OpenAI-compatible HTTP API directly via ``urllib`` /
``http.client``.

Public API (``provider_name``, ``supported_models``, ``generate``,
``generate_chat``, ``generate_with_tools``, ``stream``, ``count_tokens``) is
preserved for backward compatibility.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Iterator, List, Optional

from ..._internal.clients.openai_rest import OpenAIClient
from ..._internal.tokenizer import count_tokens as _count_tokens
from .base import BaseLLMProvider, LLMMessage, LLMResponse, ProviderConfig

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseLLMProvider):
    """OpenAI Chat Completions provider using stdlib-only HTTP."""

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

    # -- factory ----------------------------------------------------------

    @classmethod
    def from_env(cls, model: Optional[str] = None) -> "OpenAIProvider":
        config = ProviderConfig(
            api_key=os.getenv("OPENAI_API_KEY"),
            api_base=os.getenv("OPENAI_API_BASE"),
            organization=os.getenv("OPENAI_ORGANIZATION"),
            default_model=model or os.getenv("OPENAI_MODEL", cls.DEFAULT_MODEL),
            timeout=float(os.getenv("OPENAI_TIMEOUT", "60")),
            max_retries=int(os.getenv("OPENAI_MAX_RETRIES", "3")),
        )
        return cls(config)

    # -- metadata ---------------------------------------------------------

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def supported_models(self) -> List[str]:
        return self.SUPPORTED_MODELS

    # -- client lifecycle -------------------------------------------------

    def _initialize_client(self) -> None:
        if not self.config.api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not configured. Set OPENAI_API_KEY in the "
                "environment or pass api_key= via ProviderConfig."
            )
        base_url = self.config.api_base or "https://api.openai.com"
        self._client = OpenAIClient(
            api_key=self.config.api_key,
            base_url=base_url,
            organization=self.config.organization,
            timeout=self.config.timeout,
            max_retries=self.config.max_retries,
        )
        logger.info("OpenAI REST client initialized (base=%s)", base_url)

    # -- helpers ----------------------------------------------------------

    @staticmethod
    def _build_response(provider: str, raw: Dict[str, Any]) -> LLMResponse:
        choice = (raw.get("choices") or [{}])[0]
        message = choice.get("message", {}) or {}
        usage = raw.get("usage") or {}
        return LLMResponse(
            content=message.get("content") or "",
            model=raw.get("model", ""),
            provider=provider,
            finish_reason=choice.get("finish_reason", "stop"),
            tool_calls=message.get("tool_calls"),
            usage={
                "prompt_tokens": int(usage.get("prompt_tokens", 0)),
                "completion_tokens": int(usage.get("completion_tokens", 0)),
                "total_tokens": int(usage.get("total_tokens", 0)),
            },
            raw_response=raw,
        )

    def _common_kwargs(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        passthrough = {}
        for k in ("top_p", "frequency_penalty", "presence_penalty", "seed", "response_format"):
            if k in kwargs:
                passthrough[k] = kwargs[k]
        return passthrough

    # -- generation -------------------------------------------------------

    def generate(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stop: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        self._ensure_initialized()
        messages = [{"role": "user", "content": prompt}]
        if "system_prompt" in kwargs:
            messages.insert(0, {"role": "system", "content": kwargs.pop("system_prompt")})
        raw = self._client.chat_completions(
            model=model or self.config.default_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stop=stop,
            extra=self._common_kwargs(kwargs),
        )
        return self._build_response(self.provider_name, raw)

    def generate_chat(
        self,
        messages: List[LLMMessage],
        *,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        self._ensure_initialized()
        raw = self._client.chat_completions(
            model=model or self.config.default_model,
            messages=[m.to_dict() for m in messages],
            temperature=temperature,
            max_tokens=max_tokens,
            extra=self._common_kwargs(kwargs),
        )
        return self._build_response(self.provider_name, raw)

    def generate_with_tools(
        self,
        prompt: str,
        tools: List[Dict[str, Any]],
        *,
        model: Optional[str] = None,
        temperature: float = 0.7,
        tool_choice: str = "auto",
        **kwargs: Any,
    ) -> LLMResponse:
        self._ensure_initialized()
        messages = [{"role": "user", "content": prompt}]
        if "system_prompt" in kwargs:
            messages.insert(0, {"role": "system", "content": kwargs.pop("system_prompt")})
        openai_tools = [
            t if "type" in t else {"type": "function", "function": t}
            for t in tools
        ]
        raw = self._client.chat_completions(
            model=model or self.config.default_model,
            messages=messages,
            temperature=temperature,
            tools=openai_tools or None,
            tool_choice=tool_choice if openai_tools else None,
            extra=self._common_kwargs(kwargs),
        )
        return self._build_response(self.provider_name, raw)

    def stream(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> Iterator[str]:
        self._ensure_initialized()
        messages = [{"role": "user", "content": prompt}]
        if "system_prompt" in kwargs:
            messages.insert(0, {"role": "system", "content": kwargs.pop("system_prompt")})
        for chunk in self._client.chat_completions(
            model=model or self.config.default_model,
            messages=messages,
            temperature=temperature,
            stream=True,
        ):
            delta = chunk.content_delta
            if delta:
                yield delta

    def count_tokens(self, text: str, model: Optional[str] = None) -> int:
        return _count_tokens(text, model or (self.config.default_model or ""))


__all__ = ["OpenAIProvider"]
