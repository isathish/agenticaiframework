"""Google Gemini Provider Adapter — stdlib-only implementation.

Replaces the ``google.generativeai`` PyPI client with the framework's own
REST client (``agenticaiframework._internal.clients.gemini_rest``).
"""

from __future__ import annotations

import json as _json
import logging
import os
from typing import Any, Dict, Iterator, List, Optional

from ..._internal.clients.gemini_rest import GeminiClient
from ..._internal.tokenizer import count_tokens as _count_tokens
from .base import BaseLLMProvider, LLMMessage, LLMResponse, ProviderConfig

logger = logging.getLogger(__name__)


class GoogleProvider(BaseLLMProvider):
    """Google Gemini provider using stdlib-only HTTP."""

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
    def from_env(cls, model: Optional[str] = None) -> "GoogleProvider":
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
        if not self.config.api_key:
            raise RuntimeError(
                "GOOGLE_API_KEY / GEMINI_API_KEY is not configured."
            )
        self._client = GeminiClient(
            api_key=self.config.api_key,
            timeout=self.config.timeout,
            max_retries=self.config.max_retries,
        )
        logger.info("Google Gemini REST client initialized")

    # -- helpers --------------------------------------------------------

    @staticmethod
    def _parse_response(raw: Dict[str, Any], model: str, provider: str) -> LLMResponse:
        content = ""
        tool_calls: Optional[List[Dict[str, Any]]] = None
        for cand in raw.get("candidates") or []:
            cont = cand.get("content") or {}
            for part in cont.get("parts") or []:
                if "text" in part:
                    content += part.get("text") or ""
                elif "functionCall" in part:
                    tool_calls = tool_calls or []
                    fc = part["functionCall"]
                    tool_calls.append(
                        {
                            "id": f"call_{len(tool_calls)}",
                            "type": "function",
                            "function": {
                                "name": fc.get("name", ""),
                                "arguments": _json.dumps(fc.get("args") or {}),
                            },
                        }
                    )
        usage_meta = raw.get("usageMetadata") or {}
        usage = {
            "prompt_tokens": int(usage_meta.get("promptTokenCount", 0)),
            "completion_tokens": int(usage_meta.get("candidatesTokenCount", 0)),
            "total_tokens": int(usage_meta.get("totalTokenCount", 0)),
        }
        return LLMResponse(
            content=content,
            model=model,
            provider=provider,
            finish_reason=(raw.get("candidates") or [{}])[0].get("finishReason", "STOP"),
            tool_calls=tool_calls,
            usage=usage,
            raw_response=raw,
        )

    @staticmethod
    def _to_gemini_contents(messages: List[LLMMessage]) -> tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
        contents: List[Dict[str, Any]] = []
        system: Optional[Dict[str, Any]] = None
        for m in messages:
            if m.role == "system":
                system = {"parts": [{"text": m.content}]}
                continue
            role = "user" if m.role == "user" else "model"
            contents.append({"role": role, "parts": [{"text": m.content}]})
        return contents, system

    @staticmethod
    def _to_gemini_tools(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        decls = []
        for tool in tools:
            func = tool.get("function", tool)
            decls.append(
                {
                    "name": func["name"],
                    "description": func.get("description", ""),
                    "parameters": func.get("parameters", {"type": "object", "properties": {}}),
                }
            )
        return [{"functionDeclarations": decls}] if decls else []

    # -- generation -----------------------------------------------------

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
        gen_cfg: Dict[str, Any] = {"temperature": temperature}
        if max_tokens:
            gen_cfg["maxOutputTokens"] = max_tokens
        if stop:
            gen_cfg["stopSequences"] = stop
        system = kwargs.pop("system_prompt", None)
        sys_inst = {"parts": [{"text": system}]} if system else None
        used_model = model or self.config.default_model
        raw = self._client.generate_content(
            model=used_model,
            contents=[{"role": "user", "parts": [{"text": prompt}]}],
            system_instruction=sys_inst,
            generation_config=gen_cfg,
        )
        return self._parse_response(raw, used_model, self.provider_name)

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
        contents, sys_inst = self._to_gemini_contents(messages)
        gen_cfg: Dict[str, Any] = {"temperature": temperature}
        if max_tokens:
            gen_cfg["maxOutputTokens"] = max_tokens
        used_model = model or self.config.default_model
        raw = self._client.generate_content(
            model=used_model,
            contents=contents,
            system_instruction=sys_inst,
            generation_config=gen_cfg,
        )
        return self._parse_response(raw, used_model, self.provider_name)

    def generate_with_tools(
        self,
        prompt: str,
        tools: List[Dict[str, Any]],
        *,
        model: Optional[str] = None,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> LLMResponse:
        self._ensure_initialized()
        used_model = model or self.config.default_model
        raw = self._client.generate_content(
            model=used_model,
            contents=[{"role": "user", "parts": [{"text": prompt}]}],
            generation_config={"temperature": temperature},
            tools=self._to_gemini_tools(tools) or None,
        )
        return self._parse_response(raw, used_model, self.provider_name)

    def stream(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> Iterator[str]:
        self._ensure_initialized()
        for raw in self._client.generate_content(
            model=model or self.config.default_model,
            contents=[{"role": "user", "parts": [{"text": prompt}]}],
            generation_config={"temperature": temperature},
            stream=True,
        ):
            for cand in raw.get("candidates") or []:
                for part in (cand.get("content") or {}).get("parts") or []:
                    if "text" in part and part["text"]:
                        yield part["text"]

    def count_tokens(self, text: str, model: Optional[str] = None) -> int:
        return _count_tokens(text, model or (self.config.default_model or ""))


__all__ = ["GoogleProvider"]
