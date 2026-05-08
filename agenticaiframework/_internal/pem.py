"""Minimal PEM / DER parser for PKCS#1 and PKCS#8 RSA private keys.

Returns the components needed for signing: ``(n, e, d)``. Only RSA is supported.

This is a tiny ASN.1 DER decoder — sufficient for ``openssl rsa`` /
service-account JSON keys. Not a general-purpose ASN.1 library.
"""

from __future__ import annotations

import base64
import hashlib
import re
from dataclasses import dataclass
from typing import List, Tuple


# DER ASN.1 OID prefixes used in PKCS#1 v1.5 EMSA-PKCS1-v1_5 padding
_DIGEST_INFO_PREFIX = {
    "SHA-1":   bytes.fromhex("3021300906052b0e03021a05000414"),
    "SHA-256": bytes.fromhex("3031300d060960864801650304020105000420"),
    "SHA-384": bytes.fromhex("3041300d060960864801650304020205000430"),
    "SHA-512": bytes.fromhex("3051300d060960864801650304020305000440"),
}

_HASHERS = {
    "SHA-1": hashlib.sha1,
    "SHA-256": hashlib.sha256,
    "SHA-384": hashlib.sha384,
    "SHA-512": hashlib.sha512,
}


@dataclass
class RSAPrivateKey:
    n: int
    e: int
    d: int

    # ---- helpers used by callers (Snowflake REST, JWT signing, etc.) ----
    @property
    def key_size(self) -> int:
        return (self.n.bit_length() + 7) // 8

    def public_key_der(self) -> bytes:
        """Return the public key as a DER-encoded SubjectPublicKeyInfo (X.509)."""
        rsa_pubkey = _der_seq(_der_int(self.n) + _der_int(self.e))
        bit_string = b"\x00" + rsa_pubkey  # leading 0 = number of unused bits
        algorithm_id = _der_seq(
            _der_oid("1.2.840.113549.1.1.1")  # rsaEncryption
            + b"\x05\x00"                      # NULL parameters
        )
        return _der_seq(algorithm_id + _der_tlv(0x03, bit_string))

    def sign(self, data: bytes, hash_algo: str = "SHA-256") -> bytes:
        """RSASSA-PKCS1-v1_5 signature over ``data`` using ``hash_algo``."""
        if hash_algo not in _DIGEST_INFO_PREFIX:
            raise ValueError(f"Unsupported hash algorithm: {hash_algo}")
        digest = _HASHERS[hash_algo](data).digest()
        t_block = _DIGEST_INFO_PREFIX[hash_algo] + digest
        em_len = self.key_size
        ps_len = em_len - len(t_block) - 3
        if ps_len < 8:
            raise ValueError("RSA modulus too small for chosen hash")
        em = b"\x00\x01" + (b"\xff" * ps_len) + b"\x00" + t_block
        m = int.from_bytes(em, "big")
        s = pow(m, self.d, self.n)
        return s.to_bytes(em_len, "big")


# ---------------------------------------------------------------------------
# Tiny DER encoder (used for SubjectPublicKeyInfo)
# ---------------------------------------------------------------------------

def _der_len(length: int) -> bytes:
    if length < 0x80:
        return bytes([length])
    body = length.to_bytes((length.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(body)]) + body


def _der_tlv(tag: int, value: bytes) -> bytes:
    return bytes([tag]) + _der_len(len(value)) + value


def _der_seq(value: bytes) -> bytes:
    return _der_tlv(0x30, value)


def _der_int(value: int) -> bytes:
    body = value.to_bytes((value.bit_length() + 7) // 8 or 1, "big")
    if body[0] & 0x80:
        body = b"\x00" + body  # ensure positive
    return _der_tlv(0x02, body)


def _der_oid(oid_str: str) -> bytes:
    parts = [int(p) for p in oid_str.split(".")]
    first = bytes([parts[0] * 40 + parts[1]])
    body = bytearray(first)
    for arc in parts[2:]:
        chunk = bytearray()
        chunk.append(arc & 0x7F)
        arc >>= 7
        while arc:
            chunk.append(0x80 | (arc & 0x7F))
            arc >>= 7
        body.extend(reversed(chunk))
    return _der_tlv(0x06, bytes(body))


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
