"""Pure-Python Fernet — stdlib-only.

Implements the Fernet specification: https://github.com/fernet/spec/blob/master/Spec.md

* Key: URL-safe base64 of 32 random bytes (16-byte signing key + 16-byte AES-128 key)
* Token: ``b"\\x80" || timestamp(8 BE) || iv(16) || ciphertext || hmac_sha256(32)``
* Cipher: AES-128 in CBC mode with PKCS#7 padding
* MAC: HMAC-SHA256 over (version || timestamp || iv || ciphertext)

Compatible with the ``cryptography.fernet.Fernet`` token format. AES is
implemented via :mod:`agenticaiframework._internal.aes` (slow, pure-Python).

Use this only as a fallback when the ``cryptography`` package is unavailable.
"""

from __future__ import annotations

import base64
import hmac
import os
import struct
import time
from hashlib import sha256
from typing import Optional, Union

from . import aes as _aes


class InvalidToken(Exception):
    """Raised when a token cannot be authenticated or decrypted."""


def _b64url_decode(value: Union[str, bytes]) -> bytes:
    if isinstance(value, str):
        value = value.encode("ascii")
    return base64.urlsafe_b64decode(value)


def _b64url_encode(value: bytes) -> bytes:
    return base64.urlsafe_b64encode(value)


class Fernet:
    """Fernet symmetric authenticated encryption."""

    def __init__(self, key: Union[str, bytes]) -> None:
        raw = _b64url_decode(key)
        if len(raw) != 32:
            raise ValueError("Fernet key must be 32 url-safe base64-encoded bytes")
        self._signing_key = raw[:16]
        self._encryption_key = raw[16:]

    # -- key generation ---------------------------------------------

    @classmethod
    def generate_key(cls) -> bytes:
        return _b64url_encode(os.urandom(32))

    # -- encryption -------------------------------------------------

    def encrypt(self, data: bytes) -> bytes:
        return self.encrypt_at_time(data, int(time.time()))

    def encrypt_at_time(self, data: bytes, current_time: int) -> bytes:
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError("data must be bytes")
        iv = os.urandom(16)
        ciphertext = _aes.encrypt_cbc(self._encryption_key, iv, bytes(data))
        basic_parts = (
            b"\x80"
            + struct.pack(">Q", current_time)
            + iv
            + ciphertext
        )
        h = hmac.new(self._signing_key, basic_parts, sha256).digest()
        return _b64url_encode(basic_parts + h)

    # -- decryption -------------------------------------------------

    def decrypt(self, token: Union[str, bytes], ttl: Optional[int] = None) -> bytes:
        timestamp, data = self._get_unverified_token_data(token)
        return self._decrypt_data(data, timestamp, ttl, int(time.time()))

    def decrypt_at_time(
        self, token: Union[str, bytes], ttl: Optional[int], current_time: int
    ) -> bytes:
        timestamp, data = self._get_unverified_token_data(token)
        return self._decrypt_data(data, timestamp, ttl, current_time)

    def extract_timestamp(self, token: Union[str, bytes]) -> int:
        timestamp, data = self._get_unverified_token_data(token)
        # Validate HMAC before returning timestamp
        h = hmac.new(self._signing_key, data[:-32], sha256).digest()
        if not hmac.compare_digest(h, data[-32:]):
            raise InvalidToken("Bad HMAC")
        return timestamp

    # -- helpers ----------------------------------------------------

    def _get_unverified_token_data(self, token: Union[str, bytes]):
        if isinstance(token, str):
            token = token.encode("ascii")
        try:
            data = _b64url_decode(token)
        except Exception as exc:  # noqa: BLE001
            raise InvalidToken("Token is not valid base64") from exc
        if not data or data[0] != 0x80 or len(data) < 1 + 8 + 16 + 32:
            raise InvalidToken("Malformed token")
        try:
            (timestamp,) = struct.unpack(">Q", data[1:9])
        except struct.error as exc:
            raise InvalidToken("Bad timestamp") from exc
        return timestamp, data

    def _decrypt_data(
        self,
        data: bytes,
        timestamp: int,
        ttl: Optional[int],
        current_time: int,
    ) -> bytes:
        # TTL validation
        if ttl is not None:
            if timestamp + ttl < current_time:
                raise InvalidToken("Token expired")
        if current_time + 60 < timestamp:
            raise InvalidToken("Token timestamp is in the future")

        h = hmac.new(self._signing_key, data[:-32], sha256).digest()
        if not hmac.compare_digest(h, data[-32:]):
            raise InvalidToken("Bad HMAC")
        iv = data[9:25]
        ciphertext = data[25:-32]
        if len(ciphertext) % 16 != 0:
            raise InvalidToken("Ciphertext is not aligned to block size")
        try:
            return _aes.decrypt_cbc(self._encryption_key, iv, ciphertext)
        except ValueError as exc:
            raise InvalidToken(str(exc)) from exc


class MultiFernet:
    """Try multiple keys; encrypt with the first."""

    def __init__(self, fernets):
        self._fernets = list(fernets)
        if not self._fernets:
            raise ValueError("MultiFernet requires at least one Fernet")

    def encrypt(self, data: bytes) -> bytes:
        return self._fernets[0].encrypt(data)

    def decrypt(self, token: Union[str, bytes], ttl: Optional[int] = None) -> bytes:
        last_exc: Optional[Exception] = None
        for f in self._fernets:
            try:
                return f.decrypt(token, ttl=ttl)
            except InvalidToken as exc:
                last_exc = exc
        raise InvalidToken("No matching key") from last_exc


__all__ = ["Fernet", "MultiFernet", "InvalidToken"]
