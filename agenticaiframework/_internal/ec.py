"""NIST P-256 (secp256r1) primitives — stdlib-only.

Provides what the framework needs for APNs / VAPID (``ES256`` JWTs) and
RFC 8291 Web Push encryption (ECDH + HKDF):

* :func:`generate_private_key`, :func:`public_key_from_private`
* :func:`ecdsa_sign` / :func:`ecdsa_verify` (raw ``r||s`` and DER forms)
* :func:`ecdh_shared_secret`
* :func:`hkdf_sha256`
* SEC1 / PKCS#8 PEM loading and raw uncompressed-point encode/decode

Not constant-time; intended for low-volume token signing, not for
high-assurance key protection.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from typing import Optional, Tuple

from . import pem as _pem

# Curve parameters
P = 0xFFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFF
A = P - 3
B = 0x5AC635D8AA3A93E7B3EBBD55769886BC651D06B0CC53B0F63BCE3C3E27D2604B
N = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551
GX = 0x6B17D1F2E12C4247F8BCE6E563A440F277037D812DEB33A0F4A13945D898C296
GY = 0x4FE342E2FE1A7F9B8EE7EB4A7C0F9E162BCE33576B315ECECBB6406837BF51F5
G = (GX, GY)

Point = Optional[Tuple[int, int]]  # None = point at infinity

_EC_OID = "1.2.840.10045.2.1"
_P256_OID = "1.2.840.10045.3.1.7"


class ECError(Exception):
    pass


# ---------------------------------------------------------------------------
# Field / point arithmetic (Jacobian would be faster; affine is fine here)
# ---------------------------------------------------------------------------

def _inv(x: int, m: int = P) -> int:
    return pow(x, -1, m)


def point_add(p1: Point, p2: Point) -> Point:
    if p1 is None:
        return p2
    if p2 is None:
        return p1
    x1, y1 = p1
    x2, y2 = p2
    if x1 == x2:
        if (y1 + y2) % P == 0:
            return None
        lam = (3 * x1 * x1 + A) * _inv(2 * y1) % P
    else:
        lam = (y2 - y1) * _inv(x2 - x1) % P
    x3 = (lam * lam - x1 - x2) % P
    y3 = (lam * (x1 - x3) - y1) % P
    return (x3, y3)


def point_mul(k: int, point: Point = G) -> Point:
    result: Point = None
    addend = point
    k %= N
    while k:
        if k & 1:
            result = point_add(result, addend)
        addend = point_add(addend, addend)
        k >>= 1
    return result


def is_on_curve(point: Point) -> bool:
    if point is None:
        return True
    x, y = point
    return (y * y - (x * x * x + A * x + B)) % P == 0


# ---------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------

@dataclass
class ECPrivateKey:
    d: int

    def public_key(self) -> "ECPublicKey":
        pt = point_mul(self.d)
        assert pt is not None
        return ECPublicKey(pt[0], pt[1])

    def to_bytes(self) -> bytes:
        return self.d.to_bytes(32, "big")


@dataclass
class ECPublicKey:
    x: int
    y: int

    def to_bytes(self) -> bytes:
        """Uncompressed SEC1 point (65 bytes, ``0x04 || X || Y``)."""
        return b"\x04" + self.x.to_bytes(32, "big") + self.y.to_bytes(32, "big")

    def to_b64url(self) -> str:
        return base64.urlsafe_b64encode(self.to_bytes()).rstrip(b"=").decode()

    @classmethod
    def from_bytes(cls, data: bytes) -> "ECPublicKey":
        if len(data) != 65 or data[0] != 0x04:
            raise ECError("Expected 65-byte uncompressed P-256 point")
        pt = (int.from_bytes(data[1:33], "big"), int.from_bytes(data[33:], "big"))
        if not is_on_curve(pt):
            raise ECError("Point not on curve")
        return cls(*pt)

    @classmethod
    def from_b64url(cls, value: str) -> "ECPublicKey":
        return cls.from_bytes(base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)))


def generate_private_key() -> ECPrivateKey:
    return ECPrivateKey(secrets.randbelow(N - 1) + 1)


def public_key_from_private(priv: ECPrivateKey) -> ECPublicKey:
    return priv.public_key()


# ---------------------------------------------------------------------------
# ECDSA
# ---------------------------------------------------------------------------

def _rfc6979_k(priv: int, h1: bytes) -> int:
    """Deterministic nonce (RFC 6979, SHA-256)."""
    qlen = 32
    x = priv.to_bytes(qlen, "big")
    h1_int = int.from_bytes(h1, "big") % N
    h1 = h1_int.to_bytes(qlen, "big")
    v = b"\x01" * 32
    k = b"\x00" * 32
    k = hmac.new(k, v + b"\x00" + x + h1, hashlib.sha256).digest()
    v = hmac.new(k, v, hashlib.sha256).digest()
    k = hmac.new(k, v + b"\x01" + x + h1, hashlib.sha256).digest()
    v = hmac.new(k, v, hashlib.sha256).digest()
    while True:
        v = hmac.new(k, v, hashlib.sha256).digest()
        cand = int.from_bytes(v, "big")
        if 1 <= cand < N:
            return cand
        k = hmac.new(k, v + b"\x00", hashlib.sha256).digest()
        v = hmac.new(k, v, hashlib.sha256).digest()


def ecdsa_sign(priv: ECPrivateKey, message: bytes, *, deterministic: bool = True) -> bytes:
    """ECDSA-SHA256 signature as raw ``r || s`` (64 bytes) — the JWS format."""
    digest = hashlib.sha256(message).digest()
    z = int.from_bytes(digest, "big")
    while True:
        k = _rfc6979_k(priv.d, digest) if deterministic else secrets.randbelow(N - 1) + 1
        pt = point_mul(k)
        assert pt is not None
        r = pt[0] % N
        if r == 0:
            deterministic = False
            continue
        s = (_inv(k, N) * (z + r * priv.d)) % N
        if s == 0:
            deterministic = False
            continue
        # low-s normalisation is harmless and matches most libraries
        if s > N // 2:
            s = N - s
        return r.to_bytes(32, "big") + s.to_bytes(32, "big")


def ecdsa_verify(pub: ECPublicKey, message: bytes, signature: bytes) -> bool:
    if len(signature) != 64:
        try:
            signature = der_to_raw_signature(signature)
        except ECError:
            return False
    r = int.from_bytes(signature[:32], "big")
    s = int.from_bytes(signature[32:], "big")
    if not (1 <= r < N and 1 <= s < N):
        return False
    z = int.from_bytes(hashlib.sha256(message).digest(), "big")
    w = _inv(s, N)
    u1 = (z * w) % N
    u2 = (r * w) % N
    pt = point_add(point_mul(u1), point_mul(u2, (pub.x, pub.y)))
    return pt is not None and pt[0] % N == r


def raw_to_der_signature(sig: bytes) -> bytes:
    r = int.from_bytes(sig[:32], "big")
    s = int.from_bytes(sig[32:], "big")
    return _pem._der_seq(_pem._der_int(r) + _pem._der_int(s))  # noqa: SLF001


def der_to_raw_signature(der: bytes) -> bytes:
    try:
        tag, body, _ = _pem._read_tlv(der, 0)  # noqa: SLF001
        if tag != 0x30:
            raise ECError("bad DER signature")
        r, idx = _pem._read_int(body, 0)  # noqa: SLF001
        s, _ = _pem._read_int(body, idx)  # noqa: SLF001
    except (IndexError, ValueError) as exc:
        raise ECError(f"bad DER signature: {exc}") from exc
    return r.to_bytes(32, "big") + s.to_bytes(32, "big")


# ---------------------------------------------------------------------------
# ECDH / HKDF
# ---------------------------------------------------------------------------

def ecdh_shared_secret(priv: ECPrivateKey, peer: ECPublicKey) -> bytes:
    pt = point_mul(priv.d, (peer.x, peer.y))
    if pt is None:
        raise ECError("ECDH produced point at infinity")
    return pt[0].to_bytes(32, "big")


def hkdf_sha256(salt: bytes, ikm: bytes, info: bytes, length: int) -> bytes:
    prk = hmac.new(salt or b"\x00" * 32, ikm, hashlib.sha256).digest()
    out, t, counter = b"", b"", 1
    while len(out) < length:
        t = hmac.new(prk, t + info + bytes([counter]), hashlib.sha256).digest()
        out += t
        counter += 1
    return out[:length]


# ---------------------------------------------------------------------------
# PEM / raw loading
# ---------------------------------------------------------------------------

def load_private_key(data) -> ECPrivateKey:
    """Accepts PEM (``EC PRIVATE KEY`` / PKCS#8 ``PRIVATE KEY``), raw 32-byte
    scalar, or a base64url-encoded 32-byte scalar (VAPID convention)."""
    if isinstance(data, ECPrivateKey):
        return data
    if isinstance(data, bytes) and len(data) == 32:
        return ECPrivateKey(int.from_bytes(data, "big"))
    text = data.decode("ascii") if isinstance(data, bytes) else data
    if "-----BEGIN" in text:
        label, der = _pem.parse_pem(text)[0]
        if "EC PRIVATE KEY" in label:
            return _parse_sec1(der)
        if "PRIVATE KEY" in label:
            return _parse_pkcs8(der)
        raise ECError(f"Unsupported PEM label: {label}")
    # base64url scalar
    raw = base64.urlsafe_b64decode(text.strip() + "=" * (-len(text.strip()) % 4))
    if len(raw) != 32:
        raise ECError("Expected 32-byte P-256 private scalar")
    return ECPrivateKey(int.from_bytes(raw, "big"))


def _parse_sec1(der: bytes) -> ECPrivateKey:
    """ECPrivateKey ::= SEQUENCE { version, privateKey OCTET STRING, ... }"""
    tag, body, _ = _pem._read_tlv(der, 0)  # noqa: SLF001
    if tag != 0x30:
        raise ECError("Expected SEQUENCE")
    _ver, idx = _pem._read_int(body, 0)  # noqa: SLF001
    ktag, scalar, _ = _pem._read_tlv(body, idx)  # noqa: SLF001
    if ktag != 0x04:
        raise ECError("Expected OCTET STRING")
    return ECPrivateKey(int.from_bytes(scalar, "big"))


def _parse_pkcs8(der: bytes) -> ECPrivateKey:
    tag, body, _ = _pem._read_tlv(der, 0)  # noqa: SLF001
    if tag != 0x30:
        raise ECError("Expected SEQUENCE")
    _ver, idx = _pem._read_int(body, 0)  # noqa: SLF001
    _atag, _alg, idx = _pem._read_tlv(body, idx)  # noqa: SLF001
    ktag, inner, _ = _pem._read_tlv(body, idx)  # noqa: SLF001
    if ktag != 0x04:
        raise ECError("Expected OCTET STRING")
    return _parse_sec1(inner)


def private_key_to_pem(priv: ECPrivateKey) -> str:
    """PKCS#8 ``-----BEGIN PRIVATE KEY-----`` for a P-256 key."""
    pub = priv.public_key().to_bytes()
    sec1 = _pem._der_seq(  # noqa: SLF001
        _pem._der_int(1)  # noqa: SLF001
        + _pem._der_tlv(0x04, priv.to_bytes())  # noqa: SLF001
        + _pem._der_tlv(0xA1, _pem._der_tlv(0x03, b"\x00" + pub))  # noqa: SLF001
    )
    alg = _pem._der_seq(_pem._der_oid(_EC_OID) + _pem._der_oid(_P256_OID))  # noqa: SLF001
    pkcs8 = _pem._der_seq(_pem._der_int(0) + alg + _pem._der_tlv(0x04, sec1))  # noqa: SLF001
    return _pem._to_pem("PRIVATE KEY", pkcs8)  # noqa: SLF001


def public_key_to_pem(pub: ECPublicKey) -> str:
    alg = _pem._der_seq(_pem._der_oid(_EC_OID) + _pem._der_oid(_P256_OID))  # noqa: SLF001
    spki = _pem._der_seq(alg + _pem._der_tlv(0x03, b"\x00" + pub.to_bytes()))  # noqa: SLF001
    return _pem._to_pem("PUBLIC KEY", spki)  # noqa: SLF001


def load_public_key(data) -> ECPublicKey:
    if isinstance(data, ECPublicKey):
        return data
    if isinstance(data, bytes) and len(data) == 65:
        return ECPublicKey.from_bytes(data)
    text = data.decode("ascii") if isinstance(data, bytes) else data
    if "-----BEGIN" in text:
        _label, der = _pem.parse_pem(text)[0]
        tag, body, _ = _pem._read_tlv(der, 0)  # noqa: SLF001
        _atag, _alg, idx = _pem._read_tlv(body, 0)  # noqa: SLF001
        btag, bits, _ = _pem._read_tlv(body, idx)  # noqa: SLF001
        if btag != 0x03:
            raise ECError("Expected BIT STRING")
        return ECPublicKey.from_bytes(bits[1:])
    return ECPublicKey.from_b64url(text.strip())


__all__ = [
    "ECError", "ECPrivateKey", "ECPublicKey", "generate_private_key",
    "public_key_from_private", "ecdsa_sign", "ecdsa_verify",
    "raw_to_der_signature", "der_to_raw_signature", "ecdh_shared_secret",
    "hkdf_sha256", "load_private_key", "load_public_key",
    "private_key_to_pem", "public_key_to_pem",
]
