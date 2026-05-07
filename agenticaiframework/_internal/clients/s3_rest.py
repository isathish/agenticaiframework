"""Pure-Python AWS S3 client (stdlib-only) using SigV4.

Implements the small subset used by ``agenticaiframework.enterprise.adapters``:

* ``upload(bucket, key, data, content_type)``
* ``download(bucket, key) -> bytes``
* ``delete(bucket, key)``
* ``list_objects(bucket, prefix) -> List[str]``
* ``exists(bucket, key) -> bool``

Region defaults to ``us-east-1``. Path-style URLs are used for maximum
compatibility (works against MinIO too).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import List, Optional

from .. import http as _http
from . import aws_sigv4 as _sigv4


_S3_NS = "{http://s3.amazonaws.com/doc/2006-03-01/}"


@dataclass
class S3Client:
    credentials: _sigv4.AWSCredentials
    region: str = "us-east-1"
    endpoint: Optional[str] = None  # e.g. "https://s3.amazonaws.com" or MinIO URL
    _http: _http.Client = field(default_factory=_http.Client)

    @property
    def _base(self) -> str:
        if self.endpoint:
            return self.endpoint.rstrip("/")
        if self.region == "us-east-1":
            return "https://s3.amazonaws.com"
        return f"https://s3.{self.region}.amazonaws.com"

    def _url(self, bucket: str, key: str = "") -> str:
        url = f"{self._base}/{bucket}"
        if key:
            url += "/" + key.lstrip("/")
        return url

    def upload(
        self,
        bucket: str,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> None:
        url = self._url(bucket, key)
        headers = _sigv4.sign_request(
            method="PUT",
            url=url,
            region=self.region,
            service="s3",
            credentials=self.credentials,
            headers={"Content-Type": content_type},
            body=data,
        )
        self._http.put(url, data=data, headers=headers).raise_for_status()

    def download(self, bucket: str, key: str) -> bytes:
        url = self._url(bucket, key)
        headers = _sigv4.sign_request(
            method="GET",
            url=url,
            region=self.region,
            service="s3",
            credentials=self.credentials,
        )
        return self._http.get(url, headers=headers).raise_for_status().content

    def delete(self, bucket: str, key: str) -> None:
        url = self._url(bucket, key)
        headers = _sigv4.sign_request(
            method="DELETE",
            url=url,
            region=self.region,
            service="s3",
            credentials=self.credentials,
        )
        self._http.delete(url, headers=headers).raise_for_status()

    def exists(self, bucket: str, key: str) -> bool:
        url = self._url(bucket, key)
        headers = _sigv4.sign_request(
            method="HEAD",
            url=url,
            region=self.region,
            service="s3",
            credentials=self.credentials,
        )
        resp = self._http.request("HEAD", url, headers=headers)
        return resp.status == 200

    def list_objects(self, bucket: str, prefix: str = "") -> List[str]:
        keys: List[str] = []
        continuation: Optional[str] = None
        while True:
            params = ["list-type=2"]
            if prefix:
                params.append(f"prefix={prefix}")
            if continuation:
                from urllib.parse import quote
                params.append(f"continuation-token={quote(continuation, safe='')}")
            url = f"{self._url(bucket)}?{'&'.join(params)}"
            headers = _sigv4.sign_request(
                method="GET",
                url=url,
                region=self.region,
                service="s3",
                credentials=self.credentials,
            )
            resp = self._http.get(url, headers=headers).raise_for_status()
            root = ET.fromstring(resp.content)
            for c in root.findall(f"{_S3_NS}Contents"):
                k = c.find(f"{_S3_NS}Key")
                if k is not None and k.text is not None:
                    keys.append(k.text)
            truncated = root.find(f"{_S3_NS}IsTruncated")
            if truncated is None or (truncated.text or "").lower() != "true":
                break
            tok = root.find(f"{_S3_NS}NextContinuationToken")
            continuation = tok.text if tok is not None else None
            if not continuation:
                break
        return keys


__all__ = ["S3Client"]
