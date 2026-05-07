"""Tiny JWT (JSON Web Token) signer/verifier — stdlib-only.

Supports HS256 / HS384 / HS512 (HMAC) and RS256 / RS384 / RS512 (RSA via
:mod:`agenticaiframework._internal.pem` — uses Python's built-in big-int
modular exponentiation; signing a 2048-bit key takes O(50 ms)).

Public API::

    encode(payload, key, *, algorithm='HS256', headers=None) -> str
    decode(token, key, *, algorithms=['HS256']) -> dict
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any, Dict, Iterable, Optional, Tuple, Union

from . import pem as _pem

_HASHES = {
    "HS256": hashlib.sha256, "HS384": hashlib.sha384, "HS512": hashlib.sha512,
    "RS256": hashlib.sha256, "RS384": hashlib.sha384, "RS512": hashlib.sha512,
}

_DIGEST_INFO_PREFIX = {
    "RS256": bytes.fromhex("3031300d060960864801650304020105000420"),
    "RS384": bytes.fromhex("3041300d060960864801650304020205000430"),
    "RS512": bytes.fromhex("3051300d060960864801650304020305000440"),
}


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def _json_dumps(obj: Any) -> bytes:
    return json.dumps(obj, separators=(",", ":"), sort_keys=False).encode("utf-8")


# ---------------------------------------------------------------------------
# RSA primitive (PKCS#1 v1.5)
# ---------------------------------------------------------------------------

def _rsa_sign_pkcs1_v15(message: bytes, key: _pem.RSAPrivateKey, algorithm: str) -> bytes:
    digest = _HASHES[algorithm](message).digest()
    em_prefix = _DIGEST_INFO_PREFIX[algorithm] + digest
    k = (key.n.bit_length() + 7) // 8
    if len(em_prefix) > k - 11:
        raise ValueError("RSA key too small for signature")
    ps = b"\xff" * (k - len(em_prefix) - 3)
    em = b"\x00\x01" + ps + b"\x00" + em_prefix
    m = int.from_bytes(em, "big")
    sig_int = pow(m, key.d, key.n)
    return sig_int.to_bytes(k, "big")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class JWTError(Exception):
    pass


def encode(payload: Dict[str, Any], key: Union[str, bytes, _pem.RSAPrivateKey], *,
           algorithm: str = "HS256", headers: Optional[Dict[str, Any]] = None) -> str:
    if algorithm not in _HASHES:
        raise JWTError(f"Unsupported algorithm: {algorithm}")
    header = {"alg": algorithm, "typ": "JWT"}
    if headers:
        header.update(headers)
    head_b64 = _b64url_encode(_json_dumps(header))
    body_b64 = _b64url_encode(_json_dumps(payload))
    signing_input = (head_b64 + "." + body_b64).encode("ascii")

    if algorithm.startswith("HS"):
        if isinstance(key, str):
            key_bytes = key.encode("utf-8")
        else:
            key_bytes = key  # type: ignore[assignment]
        sig = hmac.new(key_bytes, signing_input, _HASHES[algorithm]).digest()
    else:
        if isinstance(key, (str, bytes)):
            rsa_key = _pem.load_rsa_private_key(key)
        else:
            rsa_key = key
        sig = _rsa_sign_pkcs1_v15(signing_input, rsa_key, algorithm)

    return head_b64 + "." + body_b64 + "." + _b64url_encode(sig)


def decode(token: str, key: Union[str, bytes, _pem.RSAPrivateKey], *,
           algorithms: Iterable[str] = ("HS256",), verify_exp: bool = True) -> Dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3:
        raise JWTError("Malformed JWT")
    head_b64, body_b64, sig_b64 = parts
    header = json.loads(_b64url_decode(head_b64))
    payload = json.loads(_b64url_decode(body_b64))
    sig = _b64url_decode(sig_b64)
    alg = header.get("alg")
    if alg not in algorithms:
        raise JWTError(f"Algorithm {alg!r} not allowed")

    signing_input = (head_b64 + "." + body_b64).encode("ascii")
    if alg.startswith("HS"):
        key_bytes = key.encode("utf-8") if isinstance(key, str) else key  # type: ignore[union-attr]
        expected = hmac.new(key_bytes, signing_input, _HASHES[alg]).digest()
        if not hmac.compare_digest(expected, sig):
            raise JWTError("Signature verification failed")
    else:
        # Verify-only RSA path is not commonly needed by the framework — we
        # currently support sign-only for cloud auth. Reject explicitly.
        raise JWTError("RSA verify not implemented")

    if verify_exp and "exp" in payload and payload["exp"] < time.time():
        raise JWTError("Token expired")
    return payload


__all__ = ["encode", "decode", "JWTError"]
