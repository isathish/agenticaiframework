"""Google Cloud REST adapters — stdlib-only.

Implements service-account-JWT-based access-token flow plus thin REST clients
for Cloud Storage, Speech-to-Text, Text-to-Speech, and Vision OCR. Only the
endpoints used by the framework are implemented.

Authentication: load a service-account JSON file (the standard
``GOOGLE_APPLICATION_CREDENTIALS`` payload), build an RS256 JWT, exchange it
at ``https://oauth2.googleapis.com/token`` for a short-lived bearer token,
and cache that until ~5 min before expiry.
"""

from __future__ import annotations

import base64
import json
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .. import http as _http
from .. import jwt as _jwt
from .. import pem as _pem


OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"


# ---------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------

@dataclass
class ServiceAccountCredentials:
    client_email: str
    token_uri: str
    private_key: _pem.RSAPrivateKey
    project_id: Optional[str] = None
    _token: Optional[str] = field(default=None, init=False, repr=False)
    _expires_at: float = field(default=0.0, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    @classmethod
    def from_file(cls, path: str) -> "ServiceAccountCredentials":
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_info(json.load(f))

    @classmethod
    def from_env(cls, var: str = "GOOGLE_APPLICATION_CREDENTIALS") -> "ServiceAccountCredentials":
        path = os.environ.get(var)
        if not path:
            raise RuntimeError(f"{var} is not set")
        return cls.from_file(path)

    @classmethod
    def from_info(cls, info: Dict[str, Any]) -> "ServiceAccountCredentials":
        return cls(
            client_email=info["client_email"],
            token_uri=info.get("token_uri", OAUTH_TOKEN_URL),
            private_key=_pem.load_rsa_private_key(info["private_key"]),
            project_id=info.get("project_id"),
        )

    def access_token(self, scopes: List[str]) -> str:
        with self._lock:
            now = time.time()
            if self._token and self._expires_at - 300 > now:
                return self._token
            payload = {
                "iss": self.client_email,
                "scope": " ".join(scopes),
                "aud": self.token_uri,
                "iat": int(now),
                "exp": int(now + 3600),
            }
            assertion = _jwt.encode(payload, self.private_key, algorithm="RS256")
            body = (
                "grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer&assertion="
                + assertion
            )
            client = _http.Client()
            resp = client.post(
                self.token_uri,
                data=body.encode("utf-8"),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            data = resp.json()
            if "access_token" not in data:
                raise RuntimeError(f"Failed to mint access token: {data}")
            self._token = data["access_token"]
            self._expires_at = now + int(data.get("expires_in", 3600))
            return self._token


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

@dataclass
class GCSClient:
    credentials: ServiceAccountCredentials
    base_url: str = "https://storage.googleapis.com"

    def _auth_header(self) -> Dict[str, str]:
        token = self.credentials.access_token([
            "https://www.googleapis.com/auth/devstorage.read_write",
        ])
        return {"Authorization": f"Bearer {token}"}

    def upload(self, bucket: str, object_name: str, data: bytes,
               content_type: str = "application/octet-stream") -> Dict[str, Any]:
        url = (
            f"{self.base_url}/upload/storage/v1/b/{bucket}/o"
            f"?uploadType=media&name={object_name}"
        )
        client = _http.Client()
        headers = {"Content-Type": content_type, **self._auth_header()}
        return client.post(url, data=data, headers=headers).json()

    def download(self, bucket: str, object_name: str) -> bytes:
        url = f"{self.base_url}/storage/v1/b/{bucket}/o/{object_name}?alt=media"
        client = _http.Client()
        return client.get(url, headers=self._auth_header()).content

    def delete(self, bucket: str, object_name: str) -> None:
        url = f"{self.base_url}/storage/v1/b/{bucket}/o/{object_name}"
        client = _http.Client()
        client.request("DELETE", url, headers=self._auth_header())

    def list_objects(self, bucket: str, prefix: str = "") -> List[str]:
        from urllib.parse import urlencode

        url = f"{self.base_url}/storage/v1/b/{bucket}/o"
        if prefix:
            url += "?" + urlencode({"prefix": prefix})
        client = _http.Client()
        names: List[str] = []
        page_token: Optional[str] = None
        while True:
            req_url = url
            if page_token:
                sep = "&" if "?" in req_url else "?"
                req_url = f"{req_url}{sep}pageToken={page_token}"
            resp = client.get(req_url, headers=self._auth_header()).json()
            for item in resp.get("items", []) or []:
                names.append(item.get("name", ""))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return [n for n in names if n]

    def exists(self, bucket: str, object_name: str) -> bool:
        url = f"{self.base_url}/storage/v1/b/{bucket}/o/{object_name}"
        client = _http.Client()
        try:
            resp = client.get(url, headers=self._auth_header())
            return 200 <= resp.status < 300
        except Exception:
            return False


# ---------------------------------------------------------------------------
# Speech / TTS / Vision
# ---------------------------------------------------------------------------

@dataclass
class SpeechClient:
    credentials: ServiceAccountCredentials
    base_url: str = "https://speech.googleapis.com"

    def recognize(self, audio_bytes: bytes, *, language_code: str = "en-US",
                  encoding: str = "LINEAR16", sample_rate_hertz: int = 16000) -> Dict[str, Any]:
        token = self.credentials.access_token(["https://www.googleapis.com/auth/cloud-platform"])
        body = {
            "config": {
                "encoding": encoding,
                "sampleRateHertz": sample_rate_hertz,
                "languageCode": language_code,
            },
            "audio": {"content": base64.b64encode(audio_bytes).decode("ascii")},
        }
        client = _http.Client()
        return client.post(
            f"{self.base_url}/v1/speech:recognize",
            json=body,
            headers={"Authorization": f"Bearer {token}"},
        ).json()


@dataclass
class TextToSpeechClient:
    credentials: ServiceAccountCredentials
    base_url: str = "https://texttospeech.googleapis.com"

    def synthesize(self, text: str, *, voice: str = "en-US-Standard-A",
                   audio_encoding: str = "MP3",
                   language_code: Optional[str] = None,
                   voice_name: Optional[str] = None) -> bytes:
        token = self.credentials.access_token(["https://www.googleapis.com/auth/cloud-platform"])
        chosen_voice = voice_name or voice
        chosen_lang = (
            language_code
            or (chosen_voice.split("-Standard")[0] if "Standard" in chosen_voice else "-".join(chosen_voice.split("-")[:2]))
        )
        body = {
            "input": {"text": text},
            "voice": {"languageCode": chosen_lang, "name": chosen_voice},
            "audioConfig": {"audioEncoding": audio_encoding},
        }
        client = _http.Client()
        resp = client.post(
            f"{self.base_url}/v1/text:synthesize",
            json=body,
            headers={"Authorization": f"Bearer {token}"},
        ).json()
        return base64.b64decode(resp["audioContent"])


@dataclass
class VisionClient:
    credentials: ServiceAccountCredentials
    base_url: str = "https://vision.googleapis.com"

    def text_detection(self, image_bytes: bytes) -> Dict[str, Any]:
        token = self.credentials.access_token(["https://www.googleapis.com/auth/cloud-vision"])
        body = {
            "requests": [
                {
                    "image": {"content": base64.b64encode(image_bytes).decode("ascii")},
                    "features": [{"type": "TEXT_DETECTION"}],
                }
            ]
        }
        client = _http.Client()
        return client.post(
            f"{self.base_url}/v1/images:annotate",
            json=body,
            headers={"Authorization": f"Bearer {token}"},
        ).json()


# ---------------------------------------------------------------------------
# Vertex AI (Gemini + embeddings)
# ---------------------------------------------------------------------------

@dataclass
class VertexAIClient:
    credentials: ServiceAccountCredentials
    project: str
    location: str = "us-central1"

    @property
    def base_url(self) -> str:
        return f"https://{self.location}-aiplatform.googleapis.com"

    def _auth_header(self) -> Dict[str, str]:
        token = self.credentials.access_token(
            ["https://www.googleapis.com/auth/cloud-platform"]
        )
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def generate_content(
        self,
        model: str,
        contents: List[Dict[str, Any]],
        *,
        temperature: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
    ) -> Dict[str, Any]:
        url = (
            f"{self.base_url}/v1/projects/{self.project}/locations/{self.location}"
            f"/publishers/google/models/{model}:generateContent"
        )
        body: Dict[str, Any] = {"contents": contents}
        gen_cfg: Dict[str, Any] = {}
        if temperature is not None:
            gen_cfg["temperature"] = temperature
        if max_output_tokens is not None:
            gen_cfg["maxOutputTokens"] = max_output_tokens
        if top_p is not None:
            gen_cfg["topP"] = top_p
        if gen_cfg:
            body["generationConfig"] = gen_cfg
        client = _http.Client(timeout=120.0)
        return client.post(url, json=body, headers=self._auth_header()).json()

    def predict_embeddings(
        self,
        model: str,
        texts: List[str],
    ) -> List[List[float]]:
        url = (
            f"{self.base_url}/v1/projects/{self.project}/locations/{self.location}"
            f"/publishers/google/models/{model}:predict"
        )
        body = {"instances": [{"content": t} for t in texts]}
        client = _http.Client(timeout=120.0)
        resp = client.post(url, json=body, headers=self._auth_header()).json()
        out: List[List[float]] = []
        for pred in resp.get("predictions", []):
            emb = pred.get("embeddings", {}).get("values", [])
            out.append(emb)
        return out


__all__ = [
    "ServiceAccountCredentials",
    "GCSClient",
    "SpeechClient",
    "TextToSpeechClient",
    "VisionClient",
    "VertexAIClient",
]
