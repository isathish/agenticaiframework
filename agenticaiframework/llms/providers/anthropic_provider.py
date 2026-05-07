"""Anthropic Provider Adapter — stdlib-only implementation.

Replaces the ``anthropic`` PyPI client with the framework's own REST client
(``agenticaiframework._internal.clients.anthropic_rest``).
"""

from __future__ import annotations

import json as _json
import logging
import os
from typing import Any, Dict, Iterator, List, Optional

from ..._internal.clients.anthropic_rest import AnthropicClient
from ..._internal.tokenizer import count_tokens as _count_tokens
from .base import BaseLLMProvider, LLMMessage, LLMResponse, ProviderConfig

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude (Messages API) provider using stdlib-only HTTP."""

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
    def from_env(cls, model: Optional[str] = None) -> "AnthropicProvider":
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
        if not self.config.api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not configured. Set it in the environment "
                "or pass api_key= via ProviderConfig."
            )
        base_url = self.config.api_base or "https://api.anthropic.com"
        self._client = AnthropicClient(
            api_key=self.config.api_key,
            base_url=base_url,
            timeout=self.config.timeout,
            max_retries=self.config.max_retries,
        )
        logger.info("Anthropic REST client initialized (base=%s)", base_url)

    # -- helpers ---------------------------------------------------------

    @staticmethod
    def _parse_response(raw: Dict[str, Any], provider: str) -> LLMResponse:
        content = ""
        tool_calls: Optional[List[Dict[str, Any]]] = None
        for block in raw.get("content") or []:
            btype = block.get("type")
            if btype == "text":
                content += block.get("text") or ""
            elif btype == "tool_use":
                tool_calls = tool_calls or []
                tool_calls.append(
                    {
                        "id": block.get("id"),
                        "type": "function",
                        "function": {
                            "name": block.get("name"),
                            "arguments": _json.dumps(block.get("input") or {}),
                        },
                    }
                )
        usage = raw.get("usage") or {}
        prompt_tokens = int(usage.get("input_tokens", 0))
        completion_tokens = int(usage.get("output_tokens", 0))
        return LLMResponse(
            content=content,
            model=raw.get("model", ""),
            provider=provider,
            finish_reason=raw.get("stop_reason") or "stop",
            tool_calls=tool_calls,
            usage={
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
            raw_response=raw,
        )

    @staticmethod
    def _to_anthropic_tools(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for tool in tools:
            if "function" in tool:
                func = tool["function"]
                out.append(
                    {
                        "name": func["name"],
                        "description": func.get("description", ""),
                        "input_schema": func.get("parameters", {"type": "object", "properties": {}}),
                    }
                )
            else:
                out.append(
                    {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "input_schema": tool.get("parameters", {"type": "object", "properties": {}}),
                    }
                )
        return out

    # -- generation ------------------------------------------------------

    def generate(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = 4096,
        stop: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        self._ensure_initialized()
        system = kwargs.pop("system_prompt", None)
        raw = self._client.messages(
            model=model or self.config.default_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens or 4096,
            system=system,
            temperature=temperature,
            stop_sequences=stop,
        )
        return self._parse_response(raw, self.provider_name)

    def generate_chat(
        self,
        messages: List[LLMMessage],
        *,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = 4096,
        **kwargs: Any,
    ) -> LLMResponse:
        self._ensure_initialized()
        system: Optional[str] = None
        anth_messages: List[Dict[str, Any]] = []
        for m in messages:
            if m.role == "system":
                system = m.content
            else:
                anth_messages.append({"role": m.role, "content": m.content})
        raw = self._client.messages(
            model=model or self.config.default_model,
            messages=anth_messages,
            max_tokens=max_tokens or 4096,
            system=system,
            temperature=temperature,
        )
        return self._parse_response(raw, self.provider_name)

    def generate_with_tools(
        self,
        prompt: str,
        tools: List[Dict[str, Any]],
        *,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = 4096,
        **kwargs: Any,
    ) -> LLMResponse:
        self._ensure_initialized()
        raw = self._client.messages(
            model=model or self.config.default_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens or 4096,
            system=kwargs.pop("system_prompt", None),
            temperature=temperature,
            tools=self._to_anthropic_tools(tools) or None,
        )
        return self._parse_response(raw, self.provider_name)

    def stream(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = 4096,
        **kwargs: Any,
    ) -> Iterator[str]:
        self._ensure_initialized()
        for event in self._client.messages(
            model=model or self.config.default_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens or 4096,
            system=kwargs.pop("system_prompt", None),
            temperature=temperature,
            stream=True,
        ):
            text = event.text_delta
            if text:
                yield text

    def count_tokens(self, text: str, model: Optional[str] = None) -> int:
        return _count_tokens(text, model or (self.config.default_model or ""))


__all__ = ["AnthropicProvider"]
