"""OpenAI REST client built on the framework's stdlib HTTP client.

Implements just enough of the OpenAI REST API for ``OpenAIProvider``:

- ``POST /v1/chat/completions`` (sync + streaming via SSE).
- ``POST /v1/embeddings``.
- ``POST /v1/audio/transcriptions`` (multipart).
- ``POST /v1/audio/speech``.
- ``POST /v1/images/generations``.

Authentication uses the ``Authorization: Bearer <key>`` header.
"""

from __future__ import annotations

import json as _json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Mapping, Optional

from ..http import Client, HTTPError, SSEEvent, stream_request

logger = logging.getLogger(__name__)


@dataclass
class OpenAIChunk:
    """A streaming chat-completion delta."""

    raw: Dict[str, Any]

    @property
    def content_delta(self) -> str:
        try:
            return self.raw["choices"][0]["delta"].get("content", "") or ""
        except (KeyError, IndexError):
            return ""

    @property
    def finish_reason(self) -> Optional[str]:
        try:
            return self.raw["choices"][0].get("finish_reason")
        except (KeyError, IndexError):
            return None

    @property
    def tool_calls(self) -> List[Dict[str, Any]]:
        try:
            return self.raw["choices"][0]["delta"].get("tool_calls") or []
        except (KeyError, IndexError):
            return []


@dataclass
class OpenAIClient:
    api_key: str
    base_url: str = "https://api.openai.com"
    organization: Optional[str] = None
    timeout: float = 60.0
    max_retries: int = 2
    extra_headers: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        headers: Dict[str, str] = {
            "authorization": f"Bearer {self.api_key}",
            "content-type": "application/json",
        }
        if self.organization:
            headers["openai-organization"] = self.organization
        headers.update(self.extra_headers)
        self._client = Client(
            base_url=self.base_url,
            headers=headers,
            timeout=self.timeout,
            max_retries=self.max_retries,
        )

    # -- chat completions --------------------------------------------------

    def chat_completions(
        self,
        *,
        model: str,
        messages: List[Mapping[str, Any]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        stop: Optional[List[str]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Any] = None,
        response_format: Optional[Dict[str, Any]] = None,
        seed: Optional[int] = None,
        stream: bool = False,
        extra: Optional[Mapping[str, Any]] = None,
    ) -> Any:
        payload: Dict[str, Any] = {"model": model, "messages": list(messages)}
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if top_p is not None:
            payload["top_p"] = top_p
        if stop is not None:
            payload["stop"] = stop
        if tools:
            payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        if response_format is not None:
            payload["response_format"] = response_format
        if seed is not None:
            payload["seed"] = seed
        if extra:
            payload.update(extra)

        if not stream:
            resp = self._client.post("/v1/chat/completions", json=payload).raise_for_status()
            return resp.json()

        payload["stream"] = True
        return self._stream_chat(payload)

    def _stream_chat(self, payload: Dict[str, Any]) -> Iterator[OpenAIChunk]:
        with stream_request(
            self._client,
            "POST",
            "/v1/chat/completions",
            json=payload,
            headers={"accept": "text/event-stream"},
        ) as resp:
            if not (200 <= resp.status < 300):
                raise HTTPError(resp.status, resp.reason)
            for event in resp.iter_sse():
                if not event.data:
                    continue
                if event.data.strip() == "[DONE]":
                    return
                try:
                    obj = _json.loads(event.data)
                except _json.JSONDecodeError:
                    logger.debug("Skipping non-JSON SSE chunk: %s", event.data[:80])
                    continue
                yield OpenAIChunk(raw=obj)

    # -- embeddings --------------------------------------------------------

    def embeddings(
        self,
        *,
        model: str,
        input: Any,  # noqa: A002 - mirror OpenAI param name
        encoding_format: str = "float",
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": model,
            "input": input,
            "encoding_format": encoding_format,
        }
        resp = self._client.post("/v1/embeddings", json=payload).raise_for_status()
        return resp.json()

    # -- images ------------------------------------------------------------

    def images_generate(
        self,
        *,
        model: str = "gpt-image-1",
        prompt: str,
        n: int = 1,
        size: str = "1024x1024",
        response_format: str = "url",
        quality: Optional[str] = None,
        style: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "n": n,
            "size": size,
            "response_format": response_format,
        }
        if quality:
            payload["quality"] = quality
        if style:
            payload["style"] = style
        resp = self._client.post("/v1/images/generations", json=payload).raise_for_status()
        return resp.json()

    # -- audio -------------------------------------------------------------

    def audio_transcriptions(
        self,
        *,
        file: bytes,
        filename: str = "audio.wav",
        model: str = "whisper-1",
        language: Optional[str] = None,
    ) -> Dict[str, Any]:
        files = {"file": (filename, file, "application/octet-stream")}
        data: Dict[str, Any] = {"model": model}
        if language:
            data["language"] = language
        resp = self._client.post(
            "/v1/audio/transcriptions",
            files=files,
            data=data,
            headers={"content-type": ""},  # let multipart encoder set it
        ).raise_for_status()
        return resp.json()

    def audio_speech(
        self,
        *,
        model: str = "tts-1",
        input: str,  # noqa: A002
        voice: str = "alloy",
        response_format: str = "mp3",
    ) -> bytes:
        payload = {
            "model": model,
            "input": input,
            "voice": voice,
            "response_format": response_format,
        }
        resp = self._client.post("/v1/audio/speech", json=payload).raise_for_status()
        return resp.content


__all__ = ["OpenAIChunk", "OpenAIClient"]
