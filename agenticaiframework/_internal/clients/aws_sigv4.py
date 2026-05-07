"""AWS Signature Version 4 — pure-Python (stdlib-only).

Implements the request-signing algorithm described at
https://docs.aws.amazon.com/general/latest/gr/sigv4_signing.html.

Used by :mod:`agenticaiframework._internal.clients.s3_rest` and any future AWS
service client we might add (Bedrock, SQS, etc.).

Only the *Authorization-header* style is implemented. Pre-signed URL flow is
provided as :func:`presign_url` for cases where it is needed (e.g. browser
upload links).
"""

from __future__ import annotations

import datetime
import hashlib
import hmac
import os
from dataclasses import dataclass
from typing import Dict, Mapping, Optional, Tuple
from urllib.parse import quote, urlparse


_EMPTY_HASH = hashlib.sha256(b"").hexdigest()


@dataclass
class AWSCredentials:
    access_key_id: str
    secret_access_key: str
    session_token: Optional[str] = None

    @classmethod
    def from_env(cls) -> "AWSCredentials":
        ak = os.environ.get("AWS_ACCESS_KEY_ID")
        sk = os.environ.get("AWS_SECRET_ACCESS_KEY")
        if not ak or not sk:
            raise RuntimeError("AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY not set")
        return cls(
            access_key_id=ak,
            secret_access_key=sk,
            session_token=os.environ.get("AWS_SESSION_TOKEN"),
        )


def _hmac(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _signing_key(secret: str, datestamp: str, region: str, service: str) -> bytes:
    k_date = _hmac(("AWS4" + secret).encode("utf-8"), datestamp)
    k_region = _hmac(k_date, region)
    k_service = _hmac(k_region, service)
    return _hmac(k_service, "aws4_request")


def _canonical_query(query: str) -> str:
    if not query:
        return ""
    pairs = []
    for part in query.split("&"):
        if not part:
            continue
        if "=" in part:
            k, v = part.split("=", 1)
        else:
            k, v = part, ""
        pairs.append((quote(k, safe="-_.~"), quote(v, safe="-_.~")))
    pairs.sort()
    return "&".join(f"{k}={v}" for k, v in pairs)


def _canonical_uri(path: str, *, double_encode: bool) -> str:
    if not path:
        return "/"
    # S3 must NOT double-encode. Most other services should.
    safe = "/-_.~"
    encoded = quote(path, safe=safe)
    if double_encode:
        encoded = quote(encoded, safe=safe)
    return encoded


def sign_request(
    *,
    method: str,
    url: str,
    region: str,
    service: str,
    credentials: AWSCredentials,
    headers: Optional[Mapping[str, str]] = None,
    body: bytes = b"",
    payload_sha256: Optional[str] = None,
) -> Dict[str, str]:
    """Return a new headers dict including ``Authorization`` and ``x-amz-*`` headers.

    The caller is responsible for sending the request to ``url`` with the
    returned headers and the (unmodified) body.
    """
    parsed = urlparse(url)
    host = parsed.netloc
    path = parsed.path or "/"
    query = parsed.query

    now = datetime.datetime.utcnow()
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    datestamp = now.strftime("%Y%m%d")

    if payload_sha256 is None:
        payload_sha256 = hashlib.sha256(body).hexdigest() if body else _EMPTY_HASH

    out_headers: Dict[str, str] = {k: v for k, v in (headers or {}).items()}
    out_headers["host"] = host
    out_headers["x-amz-date"] = amz_date
    out_headers["x-amz-content-sha256"] = payload_sha256
    if credentials.session_token:
        out_headers["x-amz-security-token"] = credentials.session_token

    # Build canonical headers — lowercase name, trimmed value, sorted.
    norm_headers = {k.lower().strip(): str(v).strip() for k, v in out_headers.items()}
    signed_header_names = sorted(norm_headers.keys())
    canonical_headers = "".join(f"{n}:{norm_headers[n]}\n" for n in signed_header_names)
    signed_headers = ";".join(signed_header_names)

    double_encode = service != "s3"
    canonical_request = "\n".join([
        method.upper(),
        _canonical_uri(path, double_encode=double_encode),
        _canonical_query(query),
        canonical_headers,
        signed_headers,
        payload_sha256,
    ])

    credential_scope = f"{datestamp}/{region}/{service}/aws4_request"
    string_to_sign = "\n".join([
        "AWS4-HMAC-SHA256",
        amz_date,
        credential_scope,
        hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
    ])

    key = _signing_key(credentials.secret_access_key, datestamp, region, service)
    signature = hmac.new(key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    auth = (
        f"AWS4-HMAC-SHA256 "
        f"Credential={credentials.access_key_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, "
        f"Signature={signature}"
    )
    out_headers["Authorization"] = auth
    return out_headers


def presign_url(
    *,
    method: str,
    url: str,
    region: str,
    service: str,
    credentials: AWSCredentials,
    expires: int = 3600,
    headers: Optional[Mapping[str, str]] = None,
) -> str:
    """Generate a SigV4 presigned URL (query-string-style).

    Useful for time-limited S3 GET/PUT links.
    """
    parsed = urlparse(url)
    host = parsed.netloc
    path = parsed.path or "/"

    now = datetime.datetime.utcnow()
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    datestamp = now.strftime("%Y%m%d")
    credential_scope = f"{datestamp}/{region}/{service}/aws4_request"

    qs_pairs: list = []
    if parsed.query:
        for part in parsed.query.split("&"):
            if "=" in part:
                k, v = part.split("=", 1)
            else:
                k, v = part, ""
            qs_pairs.append((k, v))

    qs_pairs.extend([
        ("X-Amz-Algorithm", "AWS4-HMAC-SHA256"),
        ("X-Amz-Credential", quote(f"{credentials.access_key_id}/{credential_scope}", safe="")),
        ("X-Amz-Date", amz_date),
        ("X-Amz-Expires", str(expires)),
        ("X-Amz-SignedHeaders", "host"),
    ])
    if credentials.session_token:
        qs_pairs.append(("X-Amz-Security-Token", quote(credentials.session_token, safe="")))

    canonical_query = "&".join(f"{quote(k, safe='-_.~')}={quote(v, safe='-_.~')}"
                                for k, v in sorted(qs_pairs))
    canonical_headers = f"host:{host}\n"
    payload_hash = "UNSIGNED-PAYLOAD"
    canonical_request = "\n".join([
        method.upper(),
        _canonical_uri(path, double_encode=service != "s3"),
        canonical_query,
        canonical_headers,
        "host",
        payload_hash,
    ])
    string_to_sign = "\n".join([
        "AWS4-HMAC-SHA256",
        amz_date,
        credential_scope,
        hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
    ])
    key = _signing_key(credentials.secret_access_key, datestamp, region, service)
    signature = hmac.new(key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{parsed.scheme}://{host}{path}?{canonical_query}&X-Amz-Signature={signature}"


__all__ = [
    "AWSCredentials",
    "sign_request",
    "presign_url",
]
