"""Minimal PEM / DER parser for PKCS#1 and PKCS#8 RSA private keys.

Returns the components needed for signing: ``(n, e, d)``. Only RSA is supported.

This is a tiny ASN.1 DER decoder — sufficient for ``openssl rsa`` /
service-account JSON keys. Not a general-purpose ASN.1 library.
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class RSAPrivateKey:
    n: int
    e: int
    d: int


# ---------------------------------------------------------------------------
# DER decoding
# ---------------------------------------------------------------------------

def _read_length(data: bytes, idx: int) -> Tuple[int, int]:
    first = data[idx]
    idx += 1
    if first & 0x80 == 0:
        return first, idx
    n_bytes = first & 0x7F
    length = int.from_bytes(data[idx: idx + n_bytes], "big")
    return length, idx + n_bytes


def _read_tlv(data: bytes, idx: int) -> Tuple[int, bytes, int]:
    tag = data[idx]
    idx += 1
    length, idx = _read_length(data, idx)
    value = data[idx: idx + length]
    return tag, value, idx + length


def _read_int(data: bytes, idx: int) -> Tuple[int, int]:
    tag, value, idx = _read_tlv(data, idx)
    if tag != 0x02:
        raise ValueError(f"Expected INTEGER tag, got {tag:#x}")
    return int.from_bytes(value, "big", signed=False), idx


# ---------------------------------------------------------------------------
# PEM
# ---------------------------------------------------------------------------

_PEM_RE = re.compile(
    r"-----BEGIN (?P<label>[A-Z0-9 ]+)-----\s+(?P<body>[A-Za-z0-9+/=\s]+?)-----END (?P=label)-----",
    re.DOTALL,
)


def parse_pem(text: str) -> List[Tuple[str, bytes]]:
    """Return ``[(label, der_bytes), ...]`` from a PEM string."""
    results: List[Tuple[str, bytes]] = []
    for m in _PEM_RE.finditer(text):
        body = re.sub(r"\s+", "", m.group("body"))
        results.append((m.group("label"), base64.b64decode(body)))
    if not results:
        raise ValueError("No PEM blocks found")
    return results


def load_rsa_private_key(text_or_bytes) -> RSAPrivateKey:
    """Load an RSA private key from PEM (PKCS#1 or PKCS#8) or raw DER."""
    if isinstance(text_or_bytes, bytes):
        try:
            text = text_or_bytes.decode("ascii")
        except UnicodeDecodeError:
            return _parse_pkcs1_der(text_or_bytes)
    else:
        text = text_or_bytes
    blocks = parse_pem(text)
    label, der = blocks[0]
    if "RSA PRIVATE KEY" in label:
        return _parse_pkcs1_der(der)
    if "PRIVATE KEY" in label:
        return _parse_pkcs8_der(der)
    raise ValueError(f"Unsupported PEM label: {label}")


def _parse_pkcs1_der(der: bytes) -> RSAPrivateKey:
    """RSAPrivateKey ::= SEQUENCE { version, n, e, d, ... }"""
    tag, body, _ = _read_tlv(der, 0)
    if tag != 0x30:
        raise ValueError("Expected SEQUENCE")
    idx = 0
    _version, idx = _read_int(body, idx)
    n, idx = _read_int(body, idx)
    e, idx = _read_int(body, idx)
    d, idx = _read_int(body, idx)
    return RSAPrivateKey(n=n, e=e, d=d)


def _parse_pkcs8_der(der: bytes) -> RSAPrivateKey:
    """PrivateKeyInfo ::= SEQUENCE { version, AlgorithmIdentifier, OCTET STRING (key) }"""
    tag, body, _ = _read_tlv(der, 0)
    if tag != 0x30:
        raise ValueError("Expected SEQUENCE")
    idx = 0
    _version, idx = _read_int(body, idx)
    _alg_tag, _alg, idx = _read_tlv(body, idx)
    key_tag, key_octets, _ = _read_tlv(body, idx)
    if key_tag != 0x04:
        raise ValueError("Expected OCTET STRING")
    return _parse_pkcs1_der(key_octets)


__all__ = ["RSAPrivateKey", "load_rsa_private_key", "parse_pem"]
