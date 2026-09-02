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
class RSAPublicKey:
    n: int
    e: int

    @property
    def key_size(self) -> int:
        return (self.n.bit_length() + 7) // 8

    def verify(self, signature: bytes, data: bytes, hash_algo: str = "SHA-256") -> bool:
        """Verify an RSASSA-PKCS1-v1_5 signature over ``data``."""
        if hash_algo not in _DIGEST_INFO_PREFIX:
            raise ValueError(f"Unsupported hash algorithm: {hash_algo}")
        k = self.key_size
        if len(signature) != k:
            return False
        s = int.from_bytes(signature, "big")
        if s >= self.n:
            return False
        em = pow(s, self.e, self.n).to_bytes(k, "big")
        digest = _HASHERS[hash_algo](data).digest()
        t_block = _DIGEST_INFO_PREFIX[hash_algo] + digest
        ps_len = k - len(t_block) - 3
        if ps_len < 8:
            return False
        expected = b"\x00\x01" + (b"\xff" * ps_len) + b"\x00" + t_block
        # constant-time compare
        result = 0
        for a, b in zip(em, expected):
            result |= a ^ b
        return result == 0 and len(em) == len(expected)


@dataclass
class RSAPrivateKey:
    n: int
    e: int
    d: int

    def public_key(self) -> "RSAPublicKey":
        return RSAPublicKey(n=self.n, e=self.e)

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


# ---------------------------------------------------------------------------
# Public keys
# ---------------------------------------------------------------------------

def _parse_rsa_public_pkcs1_der(der: bytes) -> RSAPublicKey:
    """RSAPublicKey ::= SEQUENCE { modulus INTEGER, publicExponent INTEGER }"""
    tag, body, _ = _read_tlv(der, 0)
    if tag != 0x30:
        raise ValueError("Expected SEQUENCE")
    n, idx = _read_int(body, 0)
    e, _ = _read_int(body, idx)
    return RSAPublicKey(n=n, e=e)


def _parse_spki_der(der: bytes) -> RSAPublicKey:
    """SubjectPublicKeyInfo ::= SEQUENCE { AlgorithmIdentifier, BIT STRING }"""
    tag, body, _ = _read_tlv(der, 0)
    if tag != 0x30:
        raise ValueError("Expected SEQUENCE")
    _alg_tag, _alg, idx = _read_tlv(body, 0)
    bs_tag, bit_string, _ = _read_tlv(body, idx)
    if bs_tag != 0x03:
        raise ValueError("Expected BIT STRING")
    # first byte of BIT STRING = number of unused bits (0 for RSA)
    return _parse_rsa_public_pkcs1_der(bit_string[1:])


def _parse_x509_cert_der(der: bytes) -> RSAPublicKey:
    """Extract the RSA public key from a DER X.509 certificate."""
    tag, cert, _ = _read_tlv(der, 0)
    if tag != 0x30:
        raise ValueError("Expected SEQUENCE")
    tbs_tag, tbs, _ = _read_tlv(cert, 0)
    if tbs_tag != 0x30:
        raise ValueError("Expected tbsCertificate SEQUENCE")
    idx = 0
    # optional explicit [0] version
    if tbs[idx] == 0xA0:
        _t, _v, idx = _read_tlv(tbs, idx)
    _serial, idx = _read_int(tbs, idx)
    _sig_alg_tag, _sig_alg, idx = _read_tlv(tbs, idx)      # signature AlgorithmIdentifier
    _issuer_tag, _issuer, idx = _read_tlv(tbs, idx)        # issuer Name
    _validity_tag, _validity, idx = _read_tlv(tbs, idx)    # validity
    _subject_tag, _subject, idx = _read_tlv(tbs, idx)      # subject Name
    spki_tag, spki_body, _ = _read_tlv(tbs, idx)
    if spki_tag != 0x30:
        raise ValueError("Expected SubjectPublicKeyInfo")
    return _parse_spki_der(_der_seq(spki_body))


def load_rsa_public_key(text_or_bytes) -> RSAPublicKey:
    """Load an RSA public key from PEM (``PUBLIC KEY`` / ``RSA PUBLIC KEY`` /
    ``CERTIFICATE``), raw DER, or a JWK ``dict`` with ``n``/``e`` members."""
    if isinstance(text_or_bytes, dict):
        jwk = text_or_bytes
        if jwk.get("kty", "RSA") != "RSA":
            raise ValueError("JWK kty must be RSA")
        def _b64url(v: str) -> int:
            return int.from_bytes(base64.urlsafe_b64decode(v + "=" * (-len(v) % 4)), "big")
        return RSAPublicKey(n=_b64url(jwk["n"]), e=_b64url(jwk["e"]))
    if isinstance(text_or_bytes, bytes):
        try:
            text = text_or_bytes.decode("ascii")
        except UnicodeDecodeError:
            try:
                return _parse_spki_der(text_or_bytes)
            except ValueError:
                return _parse_rsa_public_pkcs1_der(text_or_bytes)
    else:
        text = text_or_bytes
    blocks = parse_pem(text)
    label, der = blocks[0]
    if "RSA PUBLIC KEY" in label:
        return _parse_rsa_public_pkcs1_der(der)
    if "PUBLIC KEY" in label:
        return _parse_spki_der(der)
    if "CERTIFICATE" in label:
        return _parse_x509_cert_der(der)
    if "PRIVATE KEY" in label:
        return load_rsa_private_key(text).public_key()
    raise ValueError(f"Unsupported PEM label: {label}")


# ---------------------------------------------------------------------------
# PEM serialisation
# ---------------------------------------------------------------------------

def _to_pem(label: str, der: bytes) -> str:
    body = base64.b64encode(der).decode("ascii")
    lines = [body[i:i + 64] for i in range(0, len(body), 64)]
    return f"-----BEGIN {label}-----\n" + "\n".join(lines) + f"\n-----END {label}-----\n"


def public_key_to_pem(key: RSAPublicKey) -> str:
    """Serialise as ``-----BEGIN PUBLIC KEY-----`` (SubjectPublicKeyInfo)."""
    rsa_pubkey = _der_seq(_der_int(key.n) + _der_int(key.e))
    algorithm_id = _der_seq(_der_oid("1.2.840.113549.1.1.1") + b"\x05\x00")
    spki = _der_seq(algorithm_id + _der_tlv(0x03, b"\x00" + rsa_pubkey))
    return _to_pem("PUBLIC KEY", spki)


def private_key_to_pem(key: RSAPrivateKey, *, p: int = 0, q: int = 0) -> str:
    """Serialise as PKCS#1 ``-----BEGIN RSA PRIVATE KEY-----``.

    When ``p``/``q`` are supplied the CRT parameters are emitted so the key is
    loadable by OpenSSL; otherwise they are written as zero (still loadable by
    :func:`load_rsa_private_key`)."""
    n, e, d = key.n, key.e, key.d
    if p and q:
        dp = d % (p - 1)
        dq = d % (q - 1)
        qinv = pow(q, -1, p)
    else:
        dp = dq = qinv = 0
    body = b"".join(_der_int(v) for v in (0, n, e, d, p, q, dp, dq, qinv))
    return _to_pem("RSA PRIVATE KEY", _der_seq(body))


# ---------------------------------------------------------------------------
# Key generation (Miller-Rabin) + RSAES-OAEP
# ---------------------------------------------------------------------------

_SMALL_PRIMES = [p for p in range(3, 2000, 2) if all(p % q for q in range(3, int(p ** 0.5) + 1, 2))]


def _is_probable_prime(n: int, rounds: int = 32) -> bool:
    import secrets as _secrets
    if n < 2:
        return False
    for sp in _SMALL_PRIMES:
        if n % sp == 0:
            return n == sp
    d, r = n - 1, 0
    while d % 2 == 0:
        d //= 2
        r += 1
    for _ in range(rounds):
        a = _secrets.randbelow(n - 3) + 2
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(r - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True


def _random_prime(bits: int) -> int:
    import secrets as _secrets
    while True:
        cand = _secrets.randbits(bits) | (1 << (bits - 1)) | 1
        if _is_probable_prime(cand):
            return cand


def generate_rsa_key(bits: int = 2048, e: int = 65537) -> Tuple[RSAPrivateKey, int, int]:
    """Generate an RSA key pair. Returns ``(private_key, p, q)``."""
    if bits < 512:
        raise ValueError("RSA key size must be >= 512 bits")
    half = bits // 2
    while True:
        p = _random_prime(half)
        q = _random_prime(bits - half)
        if p == q:
            continue
        n = p * q
        if n.bit_length() != bits:
            continue
        phi = (p - 1) * (q - 1)
        if phi % e == 0:
            continue
        d = pow(e, -1, phi)
        return RSAPrivateKey(n=n, e=e, d=d), p, q


def _mgf1(seed: bytes, length: int, hasher) -> bytes:
    out = b""
    counter = 0
    while len(out) < length:
        out += hasher(seed + counter.to_bytes(4, "big")).digest()
        counter += 1
    return out[:length]


def _xor(a: bytes, b: bytes) -> bytes:
    return bytes(x ^ y for x, y in zip(a, b))


def rsa_oaep_encrypt(pub: RSAPublicKey, message: bytes, *, label: bytes = b"",
                     hash_algo: str = "SHA-256") -> bytes:
    """RSAES-OAEP encryption (RFC 8017 §7.1.1)."""
    import secrets as _secrets
    hasher = _HASHERS[hash_algo]
    h_len = hasher().digest_size
    k = pub.key_size
    if len(message) > k - 2 * h_len - 2:
        raise ValueError("message too long for RSA-OAEP with this key size")
    l_hash = hasher(label).digest()
    ps = b"\x00" * (k - len(message) - 2 * h_len - 2)
    db = l_hash + ps + b"\x01" + message
    seed = _secrets.token_bytes(h_len)
    db_mask = _mgf1(seed, k - h_len - 1, hasher)
    masked_db = _xor(db, db_mask)
    seed_mask = _mgf1(masked_db, h_len, hasher)
    masked_seed = _xor(seed, seed_mask)
    em = b"\x00" + masked_seed + masked_db
    c = pow(int.from_bytes(em, "big"), pub.e, pub.n)
    return c.to_bytes(k, "big")


def rsa_oaep_decrypt(priv: RSAPrivateKey, ciphertext: bytes, *, label: bytes = b"",
                     hash_algo: str = "SHA-256") -> bytes:
    """RSAES-OAEP decryption (RFC 8017 §7.1.2)."""
    hasher = _HASHERS[hash_algo]
    h_len = hasher().digest_size
    k = priv.key_size
    if len(ciphertext) != k or k < 2 * h_len + 2:
        raise ValueError("decryption error")
    c = int.from_bytes(ciphertext, "big")
    if c >= priv.n:
        raise ValueError("decryption error")
    em = pow(c, priv.d, priv.n).to_bytes(k, "big")
    y, masked_seed, masked_db = em[0], em[1:1 + h_len], em[1 + h_len:]
    seed = _xor(masked_seed, _mgf1(masked_db, h_len, hasher))
    db = _xor(masked_db, _mgf1(seed, k - h_len - 1, hasher))
    l_hash = hasher(label).digest()
    l_hash_prime, rest = db[:h_len], db[h_len:]
    idx = rest.find(b"\x01")
    valid = (y == 0) and (l_hash_prime == l_hash) and idx != -1 and all(b == 0 for b in rest[:idx])
    if not valid:
        raise ValueError("decryption error")
    return rest[idx + 1:]


__all__ = [
    "RSAPrivateKey", "RSAPublicKey", "load_rsa_private_key", "load_rsa_public_key",
    "parse_pem", "public_key_to_pem", "private_key_to_pem", "generate_rsa_key",
    "rsa_oaep_encrypt", "rsa_oaep_decrypt",
]
