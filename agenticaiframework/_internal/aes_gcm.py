"""Pure-Python AES-GCM (Galois/Counter Mode) — stdlib-only.

Wraps :mod:`agenticaiframework._internal.aes` with CTR mode encryption and
GHASH-based authentication. Implements the spec in NIST SP 800-38D.

This is an authenticated cipher: ``encrypt(key, nonce, plaintext, aad)`` returns
``ciphertext || tag(16 bytes)``, and ``decrypt`` validates the tag in constant
time before returning plaintext. Tampering raises :class:`InvalidTag`.

Note: pure-Python GHASH is *very* slow (constant-time GF(2^128) multiplication
per 16-byte block). Use as a fallback when ``cryptography`` is unavailable.
"""

from __future__ import annotations

import hmac
import struct
from typing import Optional

from . import aes as _aes


class InvalidTag(Exception):
    """Raised when GCM authentication fails."""


# ---------------------------------------------------------------------------
# GF(2^128) multiplication (right-shift method, NIST SP 800-38D)
# ---------------------------------------------------------------------------

_R = 0xE1 << 120


def _gf128_mul(x: int, y: int) -> int:
    z = 0
    v = y
    for i in range(127, -1, -1):
        if (x >> i) & 1:
            z ^= v
        if v & 1:
            v = (v >> 1) ^ _R
        else:
            v >>= 1
    return z


def _bytes_to_int(b: bytes) -> int:
    return int.from_bytes(b, "big")


def _int_to_bytes(n: int) -> bytes:
    return n.to_bytes(16, "big")


def _ghash(h_int: int, data: bytes) -> int:
    """GHASH with a precomputed H integer. ``data`` must be 16-byte aligned."""
    y = 0
    for i in range(0, len(data), 16):
        block = data[i : i + 16]
        if len(block) < 16:
            block = block + b"\x00" * (16 - len(block))
        y = _gf128_mul(y ^ _bytes_to_int(block), h_int)
    return y


def _pad16(data: bytes) -> bytes:
    rem = len(data) % 16
    if rem == 0:
        return data
    return data + b"\x00" * (16 - rem)


# ---------------------------------------------------------------------------
# CTR mode encryption (driven by AES block encrypt)
# ---------------------------------------------------------------------------

def _aes_ctr_xor(exp_key: bytes, nr: int, j0: bytes, data: bytes) -> bytes:
    """Encrypt-then-XOR: output = data ⊕ AES(j0+1) || AES(j0+2) || ...

    Per NIST SP 800-38D, only the rightmost 32 bits act as the counter; the
    leftmost 96 bits remain fixed to ``j0[:12]``. The counter wraps modulo 2^32.
    """
    fixed = j0[:12]
    init_ctr = int.from_bytes(j0[12:16], "big")
    out = bytearray(len(data))
    for i in range(0, len(data), 16):
        ctr = (init_ctr + 1 + (i // 16)) & 0xFFFFFFFF
        block_ctr = fixed + ctr.to_bytes(4, "big")
        keystream = _aes._encrypt_block(block_ctr, exp_key, nr)  # noqa: SLF001
        chunk = data[i : i + 16]
        for j, b in enumerate(chunk):
            out[i + j] = b ^ keystream[j]
    return bytes(out)


def _compute_j0(h_int: int, nonce: bytes) -> bytes:
    if len(nonce) == 12:
        return nonce + b"\x00\x00\x00\x01"
    # General case: J0 = GHASH(H, IV || 0^(s+64) || len(IV)_64)
    s = (16 - (len(nonce) % 16)) % 16
    padded = nonce + b"\x00" * s + b"\x00" * 8 + (len(nonce) * 8).to_bytes(8, "big")
    return _int_to_bytes(_ghash(h_int, padded))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def encrypt(
    key: bytes,
    nonce: bytes,
    plaintext: bytes,
    associated_data: bytes = b"",
) -> bytes:
    """AES-GCM encrypt. Returns ``ciphertext || 16-byte tag``."""
    exp_key, nr = _aes._key_expansion(key)  # noqa: SLF001
    h_bytes = _aes._encrypt_block(b"\x00" * 16, exp_key, nr)  # noqa: SLF001
    h_int = _bytes_to_int(h_bytes)
    j0 = _compute_j0(h_int, nonce)
    ciphertext = _aes_ctr_xor(exp_key, nr, j0, plaintext)

    aad_padded = _pad16(associated_data)
    ct_padded = _pad16(ciphertext)
    lengths = struct.pack(">QQ", len(associated_data) * 8, len(ciphertext) * 8)
    s = _ghash(h_int, aad_padded + ct_padded + lengths)

    e_j0 = _aes._encrypt_block(j0, exp_key, nr)  # noqa: SLF001
    tag = bytes(a ^ b for a, b in zip(_int_to_bytes(s), e_j0))
    return ciphertext + tag


def decrypt(
    key: bytes,
    nonce: bytes,
    ciphertext_and_tag: bytes,
    associated_data: bytes = b"",
) -> bytes:
    """AES-GCM decrypt. Verifies tag in constant time."""
    if len(ciphertext_and_tag) < 16:
        raise InvalidTag("Ciphertext too short to contain tag")
    ciphertext = ciphertext_and_tag[:-16]
    tag = ciphertext_and_tag[-16:]

    exp_key, nr = _aes._key_expansion(key)  # noqa: SLF001
    h_bytes = _aes._encrypt_block(b"\x00" * 16, exp_key, nr)  # noqa: SLF001
    h_int = _bytes_to_int(h_bytes)
    j0 = _compute_j0(h_int, nonce)

    aad_padded = _pad16(associated_data)
    ct_padded = _pad16(ciphertext)
    lengths = struct.pack(">QQ", len(associated_data) * 8, len(ciphertext) * 8)
    s = _ghash(h_int, aad_padded + ct_padded + lengths)
    e_j0 = _aes._encrypt_block(j0, exp_key, nr)  # noqa: SLF001
    expected = bytes(a ^ b for a, b in zip(_int_to_bytes(s), e_j0))

    if not hmac.compare_digest(expected, tag):
        raise InvalidTag("AES-GCM authentication failed")

    return _aes_ctr_xor(exp_key, nr, j0, ciphertext)


class AESGCM:
    """``cryptography.hazmat.primitives.ciphers.aead.AESGCM``-shaped wrapper."""

    def __init__(self, key: bytes) -> None:
        if len(key) not in (16, 24, 32):
            raise ValueError("AES-GCM key must be 16, 24 or 32 bytes")
        self._key = key

    def encrypt(self, nonce: bytes, data: bytes, associated_data: Optional[bytes]) -> bytes:
        return encrypt(self._key, nonce, data, associated_data or b"")

    def decrypt(self, nonce: bytes, data: bytes, associated_data: Optional[bytes]) -> bytes:
        return decrypt(self._key, nonce, data, associated_data or b"")


__all__ = ["AESGCM", "InvalidTag", "encrypt", "decrypt"]
