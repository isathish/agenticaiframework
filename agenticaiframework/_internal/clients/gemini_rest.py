"""Google Gemini REST client built on the framework's stdlib HTTP."""

from __future__ import annotations

import json as _json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Mapping, Optional

from ..http import Client, HTTPError, stream_request

logger = logging.getLogger(__name__)


@dataclass
class GeminiClient:
    api_key: str
    base_url: str = "https://generativelanguage.googleapis.com"
    api_version: str = "v1beta"
    timeout: float = 60.0
    max_retries: int = 2
    extra_headers: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        headers: Dict[str, str] = {"content-type": "application/json"}
        headers.update(self.extra_headers)
        self._client = Client(
            base_url=self.base_url,
            headers=headers,
            timeout=self.timeout,
            max_retries=self.max_retries,
        )

    def _model_path(self, model: str, action: str) -> str:
        # Gemini accepts both "models/gemini-1.5-pro" and "gemini-1.5-pro"
        if not model.startswith("models/"):
            model = f"models/{model}"
        return f"/{self.api_version}/{model}:{action}"

    # -- generateContent ---------------------------------------------------

    def generate_content(
        self,
        *,
        model: str,
        contents: List[Mapping[str, Any]],
        system_instruction: Optional[Mapping[str, Any]] = None,
        generation_config: Optional[Mapping[str, Any]] = None,
        tools: Optional[List[Mapping[str, Any]]] = None,
        safety_settings: Optional[List[Mapping[str, Any]]] = None,
        stream: bool = False,
    ) -> Any:
        payload: Dict[str, Any] = {"contents": list(contents)}
        if system_instruction is not None:
            payload["systemInstruction"] = system_instruction
        if generation_config is not None:
            payload["generationConfig"] = dict(generation_config)
        if tools:
            payload["tools"] = list(tools)
        if safety_settings:
            payload["safetySettings"] = list(safety_settings)

        action = "streamGenerateContent" if stream else "generateContent"
        path = self._model_path(model, action)
        params = {"key": self.api_key}
        if stream:
            params["alt"] = "sse"
            return self._stream_generate(path, params, payload)

        resp = self._client.post(path, params=params, json=payload).raise_for_status()
        return resp.json()

    def _stream_generate(
        self, path: str, params: Mapping[str, Any], payload: Mapping[str, Any]
    ) -> Iterator[Dict[str, Any]]:
        with stream_request(
            self._client,
            "POST",
            path,
            json=payload,
            params=params,
            headers={"accept": "text/event-stream"},
        ) as resp:
            if not (200 <= resp.status < 300):
                raise HTTPError(resp.status, resp.reason)
            for event in resp.iter_sse():
                if not event.data:
                    continue
                try:
                    yield _json.loads(event.data)
                except _json.JSONDecodeError:
                    continue

    # -- embedContent ------------------------------------------------------

    def embed_content(
        self,
        *,
        model: str,
        text: str,
        task_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "content": {"parts": [{"text": text}]},
        }
        if task_type:
            payload["taskType"] = task_type
        path = self._model_path(model, "embedContent")
        resp = self._client.post(
            path, params={"key": self.api_key}, json=payload
        ).raise_for_status()
        return resp.json()

    # -- countTokens -------------------------------------------------------

    def count_tokens(
        self, *, model: str, contents: List[Mapping[str, Any]]
    ) -> Dict[str, Any]:
        path = self._model_path(model, "countTokens")
        payload = {"contents": list(contents)}
        resp = self._client.post(
            path, params={"key": self.api_key}, json=payload
        ).raise_for_status()
        return resp.json()


__all__ = ["GeminiClient"]
