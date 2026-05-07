"""Anthropic Messages REST client built on the framework's stdlib HTTP."""

from __future__ import annotations

import json as _json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Mapping, Optional

from ..http import Client, HTTPError, stream_request

logger = logging.getLogger(__name__)


@dataclass
class AnthropicEvent:
    """A single Server-Sent-Event from the Messages streaming endpoint."""

    type: str
    raw: Dict[str, Any]

    @property
    def text_delta(self) -> str:
        if self.type == "content_block_delta":
            delta = self.raw.get("delta") or {}
            if delta.get("type") == "text_delta":
                return delta.get("text", "") or ""
        return ""


@dataclass
class AnthropicClient:
    api_key: str
    base_url: str = "https://api.anthropic.com"
    anthropic_version: str = "2023-06-01"
    timeout: float = 60.0
    max_retries: int = 2
    extra_headers: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        headers: Dict[str, str] = {
            "x-api-key": self.api_key,
            "anthropic-version": self.anthropic_version,
            "content-type": "application/json",
        }
        headers.update(self.extra_headers)
        self._client = Client(
            base_url=self.base_url,
            headers=headers,
            timeout=self.timeout,
            max_retries=self.max_retries,
        )

    # -- messages ----------------------------------------------------------

    def messages(
        self,
        *,
        model: str,
        messages: List[Mapping[str, Any]],
        max_tokens: int = 1024,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        stop_sequences: Optional[List[str]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Dict[str, Any]] = None,
        stream: bool = False,
        extra: Optional[Mapping[str, Any]] = None,
    ) -> Any:
        payload: Dict[str, Any] = {
            "model": model,
            "messages": list(messages),
            "max_tokens": max_tokens,
        }
        if system is not None:
            payload["system"] = system
        if temperature is not None:
            payload["temperature"] = temperature
        if top_p is not None:
            payload["top_p"] = top_p
        if stop_sequences:
            payload["stop_sequences"] = stop_sequences
        if tools:
            payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        if extra:
            payload.update(extra)

        if not stream:
            resp = self._client.post("/v1/messages", json=payload).raise_for_status()
            return resp.json()

        payload["stream"] = True
        return self._stream_messages(payload)

    def _stream_messages(self, payload: Dict[str, Any]) -> Iterator[AnthropicEvent]:
        with stream_request(
            self._client,
            "POST",
            "/v1/messages",
            json=payload,
            headers={"accept": "text/event-stream"},
        ) as resp:
            if not (200 <= resp.status < 300):
                raise HTTPError(resp.status, resp.reason)
            for sse in resp.iter_sse():
                if not sse.data:
                    continue
                try:
                    obj = _json.loads(sse.data)
                except _json.JSONDecodeError:
                    continue
                yield AnthropicEvent(type=sse.event or obj.get("type", "message"), raw=obj)

    # -- token counting ----------------------------------------------------

    def count_tokens(self, *, model: str, messages: List[Mapping[str, Any]]) -> Dict[str, Any]:
        payload = {"model": model, "messages": list(messages)}
        resp = self._client.post("/v1/messages/count_tokens", json=payload).raise_for_status()
        return resp.json()


__all__ = ["AnthropicClient", "AnthropicEvent"]
