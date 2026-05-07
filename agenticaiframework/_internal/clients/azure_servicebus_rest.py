"""Pure-Python Azure Service Bus REST client (stdlib-only).

Implements the small subset used by ``agenticaiframework.enterprise.adapters``:

* ``send(queue, body)`` — POST a single message
* ``receive(queue, max_messages, peek_lock=True)`` — POST to /messages/head, returns list
* ``complete(queue, lock_token)`` — DELETE a held lock

Auth: Shared Access Signature (SAS) generated from a connection string of the
form ``Endpoint=sb://...;SharedAccessKeyName=...;SharedAccessKey=...``.

Reference: https://learn.microsoft.com/en-us/rest/api/servicebus/
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import urllib.parse
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .. import http as _http


def parse_connection_string(conn_str: str) -> Dict[str, str]:
    parts: Dict[str, str] = {}
    for piece in conn_str.split(";"):
        if "=" in piece:
            k, v = piece.split("=", 1)
            parts[k.strip()] = v.strip()
    return parts


def _generate_sas(uri: str, key_name: str, key: str, expiry: int) -> str:
    encoded_uri = urllib.parse.quote_plus(uri)
    string_to_sign = f"{encoded_uri}\n{expiry}"
    sig = hmac.new(key.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha256).digest()
    sig_b64 = urllib.parse.quote_plus(base64.b64encode(sig).decode("ascii"))
    return (
        f"SharedAccessSignature sr={encoded_uri}&sig={sig_b64}"
        f"&se={expiry}&skn={key_name}"
    )


@dataclass
class ServiceBusClient:
    namespace: str  # e.g. "myns.servicebus.windows.net"
    key_name: str
    key: str
    timeout: float = 60.0

    @classmethod
    def from_connection_string(cls, conn_str: str) -> "ServiceBusClient":
        parts = parse_connection_string(conn_str)
        endpoint = parts.get("Endpoint", "")
        # Endpoint like: sb://myns.servicebus.windows.net/
        host = endpoint.replace("sb://", "").rstrip("/")
        return cls(
            namespace=host,
            key_name=parts.get("SharedAccessKeyName", ""),
            key=parts.get("SharedAccessKey", ""),
        )

    def _auth_header(self, resource_uri: str) -> str:
        expiry = int(time.time()) + 3600
        return _generate_sas(resource_uri, self.key_name, self.key, expiry)

    def _base(self, queue: str) -> str:
        return f"https://{self.namespace}/{queue}"

    def send(self, queue: str, body: Any, *, content_type: str = "application/json") -> str:
        url = f"{self._base(queue)}/messages"
        if not isinstance(body, (bytes, str)):
            body = json.dumps(body)
        if isinstance(body, str):
            body_bytes = body.encode("utf-8")
        else:
            body_bytes = body
        headers = {
            "Authorization": self._auth_header(self._base(queue)),
            "Content-Type": content_type,
        }
        client = _http.Client(timeout=self.timeout)
        resp = client.post(url, data=body_bytes, headers=headers)
        resp.raise_for_status()
        return resp.headers.get("BrokerProperties") or "sent"

    def receive(
        self,
        queue: str,
        *,
        max_messages: int = 1,
        timeout_seconds: int = 30,
        peek_lock: bool = True,
    ) -> List[Dict[str, Any]]:
        """Receive up to ``max_messages`` messages.

        Service Bus REST receives one at a time per call to /messages/head.
        We loop ``max_messages`` times.
        """
        results: List[Dict[str, Any]] = []
        client = _http.Client(timeout=self.timeout)
        for _ in range(max_messages):
            url = f"{self._base(queue)}/messages/head?timeout={timeout_seconds}"
            headers = {"Authorization": self._auth_header(self._base(queue))}
            method = "POST" if peek_lock else "DELETE"
            resp = client.request(method, url, headers=headers)
            if resp.status == 204 or resp.status == 200 and not resp.content:
                break  # no more messages
            if resp.status >= 400:
                resp.raise_for_status()
            try:
                content = json.loads(resp.text)
            except (json.JSONDecodeError, ValueError):
                content = resp.text
            broker_properties = resp.headers.get("BrokerProperties")
            msg_id: Optional[str] = None
            lock_token: Optional[str] = None
            if broker_properties:
                try:
                    bp = json.loads(broker_properties)
                    msg_id = bp.get("MessageId")
                    lock_token = bp.get("LockToken")
                except (json.JSONDecodeError, ValueError):
                    pass
            results.append({
                "id": msg_id or "",
                "content": content,
                "lock_token": lock_token,
                "location": resp.headers.get("Location"),
            })
        return results

    def complete(self, queue: str, message_id: str, lock_token: str) -> None:
        """Mark a peek-locked message as completed (delete it)."""
        url = f"{self._base(queue)}/messages/{message_id}/{lock_token}"
        headers = {"Authorization": self._auth_header(self._base(queue))}
        _http.Client(timeout=self.timeout).delete(url, headers=headers).raise_for_status()


__all__ = ["ServiceBusClient", "parse_connection_string"]
