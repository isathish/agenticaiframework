"""Pure-Python Azure Blob Storage client using Shared Key signing.

Implements the small subset used by ``agenticaiframework.enterprise.adapters``:

* ``upload(container, blob, data, content_type)``
* ``download(container, blob) -> bytes``
* ``delete(container, blob)``
* ``exists(container, blob) -> bool``
* ``list_blobs(container, prefix) -> List[str]``
* ``create_container(container)``

Connection string format (standard Azure):
    ``DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...;EndpointSuffix=core.windows.net``
"""

from __future__ import annotations

import base64
import datetime
import hashlib
import hmac
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote, urlparse

from .. import http as _http


_BLOB_API_VERSION = "2021-08-06"


def parse_connection_string(conn_str: str) -> Dict[str, str]:
    parts = {}
    for piece in conn_str.split(";"):
        if "=" in piece:
            k, v = piece.split("=", 1)
            parts[k.strip()] = v.strip()
    return parts


def _canonicalize_resource(account: str, path: str, query: str) -> str:
    base = f"/{account}{path}"
    if not query:
        return base
    # Group query params by lowercase name; sorted; values joined with comma.
    params: Dict[str, List[str]] = {}
    for piece in query.split("&"):
        if not piece:
            continue
        if "=" in piece:
            k, v = piece.split("=", 1)
        else:
            k, v = piece, ""
        from urllib.parse import unquote
        k_l = unquote(k).lower()
        params.setdefault(k_l, []).append(unquote(v))
    lines = [base]
    for k in sorted(params.keys()):
        lines.append(f"{k}:{','.join(sorted(params[k]))}")
    return "\n".join(lines)


def _canonicalize_headers(headers: Dict[str, str]) -> str:
    out = []
    for k in sorted(h.lower() for h in headers if h.lower().startswith("x-ms-")):
        out.append(f"{k}:{headers[k] if k in headers else headers[next(h for h in headers if h.lower() == k)]}".rstrip())
    return "\n".join(out)


def _sign(
    *,
    method: str,
    url: str,
    account: str,
    account_key: str,
    headers: Dict[str, str],
    content_length: int,
    content_type: str = "",
) -> str:
    parsed = urlparse(url)
    path = parsed.path
    query = parsed.query

    # CanonicalizedHeaders only contains x-ms-* headers, properly sorted.
    canon_headers_lines = []
    msheaders = {k.lower(): v for k, v in headers.items() if k.lower().startswith("x-ms-")}
    for k in sorted(msheaders.keys()):
        canon_headers_lines.append(f"{k}:{msheaders[k].strip()}")
    canon_headers = "\n".join(canon_headers_lines)

    canon_resource = _canonicalize_resource(account, path, query)

    string_to_sign = "\n".join([
        method.upper(),                   # VERB
        "",                                # Content-Encoding
        "",                                # Content-Language
        str(content_length) if content_length else "",  # Content-Length
        "",                                # Content-MD5
        content_type,                      # Content-Type
        "",                                # Date (use x-ms-date instead)
        "",                                # If-Modified-Since
        "",                                # If-Match
        "",                                # If-None-Match
        "",                                # If-Unmodified-Since
        "",                                # Range
        canon_headers,
        canon_resource,
    ])

    key_bytes = base64.b64decode(account_key)
    sig = hmac.new(key_bytes, string_to_sign.encode("utf-8"), hashlib.sha256).digest()
    return f"SharedKey {account}:{base64.b64encode(sig).decode('ascii')}"


@dataclass
class BlobServiceClient:
    account: str
    account_key: str
    endpoint: str  # e.g. "https://acct.blob.core.windows.net"

    @classmethod
    def from_connection_string(cls, conn_str: str) -> "BlobServiceClient":
        parts = parse_connection_string(conn_str)
        account = parts.get("AccountName", "")
        key = parts.get("AccountKey", "")
        protocol = parts.get("DefaultEndpointsProtocol", "https")
        suffix = parts.get("EndpointSuffix", "core.windows.net")
        endpoint = parts.get("BlobEndpoint") or f"{protocol}://{account}.blob.{suffix}"
        return cls(account=account, account_key=key, endpoint=endpoint.rstrip("/"))

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: bytes = b"",
        content_type: str = "",
        extra_headers: Optional[Dict[str, str]] = None,
    ):
        url = f"{self.endpoint}{path}"
        date = datetime.datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")
        headers: Dict[str, str] = {
            "x-ms-date": date,
            "x-ms-version": _BLOB_API_VERSION,
        }
        if extra_headers:
            headers.update(extra_headers)
        if content_type:
            headers["Content-Type"] = content_type
        auth = _sign(
            method=method,
            url=url,
            account=self.account,
            account_key=self.account_key,
            headers=headers,
            content_length=len(body) if body else 0,
            content_type=content_type,
        )
        headers["Authorization"] = auth
        client = _http.Client()
        if method.upper() == "HEAD":
            return client.request("HEAD", url, headers=headers)
        return client.request(method.upper(), url, data=body, headers=headers)

    # -- container ---------------------------------------------------

    def create_container(self, container: str) -> bool:
        path = f"/{quote(container)}?restype=container"
        resp = self._request("PUT", path)
        return resp.status in (201, 409)  # 409 = already exists

    # -- blob --------------------------------------------------------

    def upload(
        self,
        container: str,
        blob: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        path = f"/{quote(container)}/{quote(blob)}"
        resp = self._request(
            "PUT",
            path,
            body=data,
            content_type=content_type,
            extra_headers={"x-ms-blob-type": "BlockBlob"},
        )
        resp.raise_for_status()
        return f"{self.endpoint}{path}"

    def download(self, container: str, blob: str) -> bytes:
        path = f"/{quote(container)}/{quote(blob)}"
        resp = self._request("GET", path)
        resp.raise_for_status()
        return resp.content

    def delete(self, container: str, blob: str) -> None:
        path = f"/{quote(container)}/{quote(blob)}"
        resp = self._request("DELETE", path)
        if resp.status not in (200, 202, 204, 404):
            resp.raise_for_status()

    def exists(self, container: str, blob: str) -> bool:
        path = f"/{quote(container)}/{quote(blob)}"
        resp = self._request("HEAD", path)
        return resp.status == 200

    def list_blobs(self, container: str, prefix: str = "") -> List[str]:
        names: List[str] = []
        marker: Optional[str] = None
        while True:
            qs = ["restype=container", "comp=list"]
            if prefix:
                qs.append(f"prefix={quote(prefix)}")
            if marker:
                qs.append(f"marker={quote(marker)}")
            path = f"/{quote(container)}?{'&'.join(qs)}"
            resp = self._request("GET", path)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
            for blob in root.iter("Blob"):
                name_el = blob.find("Name")
                if name_el is not None and name_el.text:
                    names.append(name_el.text)
            next_marker_el = root.find("NextMarker")
            marker = next_marker_el.text if next_marker_el is not None else None
            if not marker:
                break
        return names


__all__ = ["BlobServiceClient", "parse_connection_string"]
