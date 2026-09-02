"""
Enterprise Encryption Service Module.

Provides encryption, decryption, key management,
and secure storage using AES and RSA algorithms.

Example:
    # Create encryption service
    crypto = create_encryption_service()
    
    # Symmetric encryption (AES)
    encrypted = await crypto.encrypt(data, key="secret_key")
    decrypted = await crypto.decrypt(encrypted, key="secret_key")
    
    # Asymmetric encryption (RSA)
    public_key, private_key = await crypto.generate_rsa_keypair()
    encrypted = await crypto.rsa_encrypt(data, public_key)
    decrypted = await crypto.rsa_decrypt(encrypted, private_key)
    
    # Key derivation
    derived_key = await crypto.derive_key("password", salt=b"...")
    
    # Hashing
    hash_value = await crypto.hash(data, algorithm="sha256")
"""

from __future__ import annotations

import asyncio
import base64
import functools
import hashlib
import hmac
import json
import logging
import os
import secrets
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
    TypeVar,
    Union,
)

from agenticaiframework._internal import aes as _aes
from agenticaiframework._internal import aes_gcm as _aes_gcm
from agenticaiframework._internal import pem as _pem

T = TypeVar('T')


logger = logging.getLogger(__name__)


class CryptoError(Exception):
    """Cryptography error."""
    pass


class EncryptionError(CryptoError):
    """Encryption error."""
    pass


class DecryptionError(CryptoError):
    """Decryption error."""
    pass


class KeyError(CryptoError):
    """Key error."""
    pass


class Algorithm(str, Enum):
    """Encryption algorithms."""
    AES_128_CBC = "aes-128-cbc"
    AES_256_CBC = "aes-256-cbc"
    AES_128_GCM = "aes-128-gcm"
    AES_256_GCM = "aes-256-gcm"
    RSA_OAEP = "rsa-oaep"
    RSA_PKCS1 = "rsa-pkcs1"


class HashAlgorithm(str, Enum):
    """Hash algorithms."""
    MD5 = "md5"
    SHA1 = "sha1"
    SHA256 = "sha256"
    SHA384 = "sha384"
    SHA512 = "sha512"
    BLAKE2B = "blake2b"
    BLAKE2S = "blake2s"


class KeyType(str, Enum):
    """Key types."""
    SYMMETRIC = "symmetric"
    PUBLIC = "public"
    PRIVATE = "private"
    DERIVED = "derived"


@dataclass
class EncryptionKey:
    """Encryption key."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: KeyType = KeyType.SYMMETRIC
    algorithm: str = "aes-256-gcm"
    key: bytes = b""
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class KeyPair:
    """RSA key pair."""
    public_key: bytes = b""
    private_key: bytes = b""
    key_size: int = 2048
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class EncryptedData:
    """Encrypted data container."""
    ciphertext: bytes = b""
    iv: bytes = b""  # Initialization vector
    tag: bytes = b""  # Auth tag for GCM
    algorithm: str = "aes-256-gcm"
    key_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HashResult:
    """Hash result."""
    value: bytes = b""
    algorithm: HashAlgorithm = HashAlgorithm.SHA256
    hex: str = ""
    base64: str = ""


@dataclass
class DerivedKey:
    """Derived key from password."""
    key: bytes = b""
    salt: bytes = b""
    iterations: int = 100000
    algorithm: str = "pbkdf2"
    hash_algorithm: HashAlgorithm = HashAlgorithm.SHA256


# Key Store
class KeyStore(ABC):
    """Abstract key storage."""
    
    @abstractmethod
    async def store(
        self,
        key_id: str,
        key: EncryptionKey,
    ) -> None:
        """Store key."""
        pass
    
    @abstractmethod
    async def get(self, key_id: str) -> Optional[EncryptionKey]:
        """Get key."""
        pass
    
    @abstractmethod
    async def delete(self, key_id: str) -> bool:
        """Delete key."""
        pass
    
    @abstractmethod
    async def list(self) -> List[str]:
        """List key IDs."""
        pass


class InMemoryKeyStore(KeyStore):
    """In-memory key store."""
    
    def __init__(self):
        self._keys: Dict[str, EncryptionKey] = {}
    
    async def store(
        self,
        key_id: str,
        key: EncryptionKey,
    ) -> None:
        self._keys[key_id] = key
    
    async def get(self, key_id: str) -> Optional[EncryptionKey]:
        return self._keys.get(key_id)
    
    async def delete(self, key_id: str) -> bool:
        if key_id in self._keys:
            del self._keys[key_id]
            return True
        return False
    
    async def list(self) -> List[str]:
        return list(self._keys.keys())


class EncryptionService:
    """
    Encryption service.
    """
    
    def __init__(
        self,
        key_store: Optional[KeyStore] = None,
        default_algorithm: Algorithm = Algorithm.AES_256_GCM,
    ):
        self._key_store = key_store or InMemoryKeyStore()
        self._default_algorithm = default_algorithm
    
    # Key generation
    async def generate_key(
        self,
        algorithm: Algorithm = Algorithm.AES_256_GCM,
        key_id: Optional[str] = None,
        expires_in: Optional[timedelta] = None,
    ) -> EncryptionKey:
        """
        Generate encryption key.
        
        Args:
            algorithm: Encryption algorithm
            key_id: Optional key ID
            expires_in: Key expiration
            
        Returns:
            Generated key
        """
        # Determine key size
        key_size = 32  # 256 bits
        if "128" in algorithm.value:
            key_size = 16
        
        key_bytes = secrets.token_bytes(key_size)
        
        key = EncryptionKey(
            id=key_id or str(uuid.uuid4()),
            type=KeyType.SYMMETRIC,
            algorithm=algorithm.value,
            key=key_bytes,
            expires_at=datetime.utcnow() + expires_in if expires_in else None,
        )
        
        # Store key
        await self._key_store.store(key.id, key)
        
        return key
    
    async def generate_rsa_keypair(
        self,
        key_size: int = 2048,
    ) -> KeyPair:
        """
        Generate RSA key pair.
        
        Args:
            key_size: Key size in bits
            
        Returns:
            Key pair (PEM-encoded public / private keys)
        """
        # Prime generation is CPU-bound; keep the event loop responsive.
        priv, p, q = await asyncio.to_thread(_pem.generate_rsa_key, key_size)
        return KeyPair(
            public_key=_pem.public_key_to_pem(priv.public_key()).encode(),
            private_key=_pem.private_key_to_pem(priv, p=p, q=q).encode(),
            key_size=key_size,
        )
    
    async def derive_key(
        self,
        password: str,
        salt: Optional[bytes] = None,
        iterations: int = 100000,
        key_length: int = 32,
        hash_algorithm: HashAlgorithm = HashAlgorithm.SHA256,
    ) -> DerivedKey:
        """
        Derive key from password using PBKDF2.
        
        Args:
            password: Password
            salt: Salt (generated if not provided)
            iterations: Number of iterations
            key_length: Derived key length
            hash_algorithm: Hash algorithm
            
        Returns:
            Derived key
        """
        salt = salt or secrets.token_bytes(16)
        
        # Use hashlib for PBKDF2
        key = hashlib.pbkdf2_hmac(
            hash_algorithm.value,
            password.encode(),
            salt,
            iterations,
            dklen=key_length,
        )
        
        return DerivedKey(
            key=key,
            salt=salt,
            iterations=iterations,
            algorithm="pbkdf2",
            hash_algorithm=hash_algorithm,
        )
    
    # Symmetric encryption (AES)
    async def encrypt(
        self,
        data: Union[bytes, str],
        key: Optional[Union[bytes, str, EncryptionKey]] = None,
        key_id: Optional[str] = None,
        algorithm: Optional[Algorithm] = None,
    ) -> EncryptedData:
        """
        Encrypt data with AES.
        
        Args:
            data: Data to encrypt
            key: Encryption key
            key_id: Key ID (if using key store)
            algorithm: Encryption algorithm
            
        Returns:
            Encrypted data
        """
        # Convert string to bytes
        if isinstance(data, str):
            data = data.encode()
        
        # Resolve key
        key_bytes, resolved_key_id = await self._resolve_key(key, key_id)
        
        algorithm = algorithm or self._default_algorithm
        key_bytes = self._fit_key(key_bytes, algorithm)
        
        if "gcm" in algorithm.value:
            iv = secrets.token_bytes(12)
            ct_and_tag = _aes_gcm.encrypt(key_bytes, iv, data)
            ciphertext, tag = ct_and_tag[:-16], ct_and_tag[-16:]
        else:
            iv = secrets.token_bytes(16)
            ciphertext = _aes.encrypt_cbc(key_bytes, iv, data)
            # Encrypt-then-MAC so CBC ciphertexts are tamper-evident too.
            tag = hmac.new(key_bytes, iv + ciphertext, hashlib.sha256).digest()[:16]
        
        return EncryptedData(
            ciphertext=ciphertext,
            iv=iv,
            tag=tag,
            algorithm=algorithm.value,
            key_id=resolved_key_id,
        )
    
    async def decrypt(
        self,
        encrypted: EncryptedData,
        key: Optional[Union[bytes, str, EncryptionKey]] = None,
        key_id: Optional[str] = None,
    ) -> bytes:
        """
        Decrypt data.
        
        Args:
            encrypted: Encrypted data
            key: Decryption key
            key_id: Key ID
            
        Returns:
            Decrypted data
        """
        # Resolve key
        key_bytes, _ = await self._resolve_key(
            key,
            key_id or encrypted.key_id,
        )
        try:
            algorithm = Algorithm(encrypted.algorithm)
        except ValueError:
            raise DecryptionError(f"Unsupported algorithm: {encrypted.algorithm}")
        key_bytes = self._fit_key(key_bytes, algorithm)
        
        if "gcm" in algorithm.value:
            try:
                return _aes_gcm.decrypt(key_bytes, encrypted.iv, encrypted.ciphertext + encrypted.tag)
            except _aes_gcm.InvalidTag:
                raise DecryptionError("Authentication failed")
        
        if encrypted.tag:
            expected_tag = hmac.new(
                key_bytes, encrypted.iv + encrypted.ciphertext, hashlib.sha256
            ).digest()[:16]
            if not hmac.compare_digest(encrypted.tag, expected_tag):
                raise DecryptionError("Authentication failed")
        try:
            return _aes.decrypt_cbc(key_bytes, encrypted.iv, encrypted.ciphertext)
        except ValueError as exc:
            raise DecryptionError(str(exc))
    
    @staticmethod
    def _fit_key(key: bytes, algorithm: Algorithm) -> bytes:
        """Coerce arbitrary key material to the exact AES key length."""
        size = 16 if "128" in algorithm.value else 32
        if len(key) == size:
            return key
        return hashlib.sha256(key).digest()[:size]
    
    async def _resolve_key(
        self,
        key: Optional[Union[bytes, str, EncryptionKey]],
        key_id: Optional[str],
    ) -> Tuple[bytes, Optional[str]]:
        """Resolve key to bytes."""
        if isinstance(key, EncryptionKey):
            return key.key, key.id
        
        if isinstance(key, str):
            # Hash string key to fixed size
            return hashlib.sha256(key.encode()).digest(), None
        
        if isinstance(key, bytes):
            return key, None
        
        if key_id:
            stored_key = await self._key_store.get(key_id)
            if stored_key:
                return stored_key.key, key_id
            raise KeyError(f"Key not found: {key_id}")
        
        raise KeyError("No key provided")
    
    # RSA encryption
    async def rsa_encrypt(
        self,
        data: Union[bytes, str],
        public_key: bytes,
    ) -> bytes:
        """
        Encrypt with RSA public key.
        
        Args:
            data: Data to encrypt
            public_key: RSA public key
            
        Returns:
            Encrypted data
        """
        if isinstance(data, str):
            data = data.encode()
        
        try:
            pub = _pem.load_rsa_public_key(public_key)
        except ValueError as exc:
            raise EncryptionError(f"Invalid RSA public key: {exc}")
        # Hybrid scheme for payloads larger than the OAEP limit: wrap a random
        # AES-256-GCM key with RSA-OAEP and prefix it to the GCM ciphertext.
        max_direct = pub.key_size - 2 * 32 - 2
        if len(data) <= max_direct:
            return b"\x00" + _pem.rsa_oaep_encrypt(pub, data)
        cek = secrets.token_bytes(32)
        nonce = secrets.token_bytes(12)
        wrapped = _pem.rsa_oaep_encrypt(pub, cek)
        return b"\x01" + wrapped + nonce + _aes_gcm.encrypt(cek, nonce, data)
    
    async def rsa_decrypt(
        self,
        data: bytes,
        private_key: bytes,
    ) -> bytes:
        """
        Decrypt with RSA private key.
        
        Args:
            data: Encrypted data
            private_key: RSA private key
            
        Returns:
            Decrypted data
        """
        try:
            priv = _pem.load_rsa_private_key(private_key)
        except ValueError as exc:
            raise DecryptionError(f"Invalid RSA private key: {exc}")
        if not data:
            raise DecryptionError("Empty ciphertext")
        mode, body = data[0], data[1:]
        try:
            if mode == 0:
                return _pem.rsa_oaep_decrypt(priv, body)
            if mode == 1:
                k = priv.key_size
                cek = _pem.rsa_oaep_decrypt(priv, body[:k])
                nonce = body[k:k + 12]
                return _aes_gcm.decrypt(cek, nonce, body[k + 12:])
        except (ValueError, _aes_gcm.InvalidTag) as exc:
            raise DecryptionError(f"RSA decryption failed: {exc}")
        raise DecryptionError("Unknown RSA envelope format")
    
    # Hashing
    async def hash(
        self,
        data: Union[bytes, str],
        algorithm: HashAlgorithm = HashAlgorithm.SHA256,
    ) -> HashResult:
        """
        Hash data.
        
        Args:
            data: Data to hash
            algorithm: Hash algorithm
            
        Returns:
            Hash result
        """
        if isinstance(data, str):
            data = data.encode()
        
        if algorithm == HashAlgorithm.BLAKE2B:
            h = hashlib.blake2b(data)
        elif algorithm == HashAlgorithm.BLAKE2S:
            h = hashlib.blake2s(data)
        else:
            h = hashlib.new(algorithm.value, data)
        
        digest = h.digest()
        
        return HashResult(
            value=digest,
            algorithm=algorithm,
            hex=digest.hex(),
            base64=base64.b64encode(digest).decode(),
        )
    
    async def hash_password(
        self,
        password: str,
        salt: Optional[bytes] = None,
    ) -> Tuple[str, bytes]:
        """
        Hash password securely.
        
        Args:
            password: Password to hash
            salt: Salt (generated if not provided)
            
        Returns:
            Tuple of (hash, salt)
        """
        salt = salt or secrets.token_bytes(16)
        
        derived = await self.derive_key(
            password,
            salt=salt,
            iterations=100000,
        )
        
        return base64.b64encode(derived.key).decode(), salt
    
    async def verify_password(
        self,
        password: str,
        hash_value: str,
        salt: bytes,
    ) -> bool:
        """
        Verify password against hash.
        
        Args:
            password: Password to verify
            hash_value: Stored hash
            salt: Salt used for hashing
            
        Returns:
            True if password matches
        """
        computed_hash, _ = await self.hash_password(password, salt)
        return hmac.compare_digest(computed_hash, hash_value)
    
    # HMAC
    async def hmac(
        self,
        data: Union[bytes, str],
        key: Union[bytes, str],
        algorithm: HashAlgorithm = HashAlgorithm.SHA256,
    ) -> HashResult:
        """
        Generate HMAC.
        
        Args:
            data: Data to sign
            key: HMAC key
            algorithm: Hash algorithm
            
        Returns:
            HMAC result
        """
        if isinstance(data, str):
            data = data.encode()
        if isinstance(key, str):
            key = key.encode()
        
        h = hmac.new(key, data, algorithm.value)
        digest = h.digest()
        
        return HashResult(
            value=digest,
            algorithm=algorithm,
            hex=digest.hex(),
            base64=base64.b64encode(digest).decode(),
        )
    
    async def verify_hmac(
        self,
        data: Union[bytes, str],
        key: Union[bytes, str],
        signature: Union[bytes, str],
        algorithm: HashAlgorithm = HashAlgorithm.SHA256,
    ) -> bool:
        """
        Verify HMAC signature.
        
        Args:
            data: Data that was signed
            key: HMAC key
            signature: Signature to verify
            algorithm: Hash algorithm
            
        Returns:
            True if valid
        """
        result = await self.hmac(data, key, algorithm)
        
        if isinstance(signature, str):
            signature = bytes.fromhex(signature)
        
        return hmac.compare_digest(result.value, signature)
    
    # Utilities
    def generate_random_bytes(self, length: int = 32) -> bytes:
        """Generate random bytes."""
        return secrets.token_bytes(length)
    
    def generate_random_string(self, length: int = 32) -> str:
        """Generate random string."""
        return secrets.token_urlsafe(length)
    
    def encode_base64(self, data: bytes) -> str:
        """Encode to base64."""
        return base64.b64encode(data).decode()
    
    def decode_base64(self, data: str) -> bytes:
        """Decode from base64."""
        return base64.b64decode(data)
    
    # Serialization
    def serialize_encrypted(self, encrypted: EncryptedData) -> str:
        """Serialize encrypted data to string."""
        return json.dumps({
            "ciphertext": base64.b64encode(encrypted.ciphertext).decode(),
            "iv": base64.b64encode(encrypted.iv).decode(),
            "tag": base64.b64encode(encrypted.tag).decode() if encrypted.tag else "",
            "algorithm": encrypted.algorithm,
            "key_id": encrypted.key_id,
            "metadata": encrypted.metadata,
        })
    
    def deserialize_encrypted(self, data: str) -> EncryptedData:
        """Deserialize encrypted data from string."""
        parsed = json.loads(data)
        return EncryptedData(
            ciphertext=base64.b64decode(parsed["ciphertext"]),
            iv=base64.b64decode(parsed["iv"]),
            tag=base64.b64decode(parsed["tag"]) if parsed["tag"] else b"",
            algorithm=parsed["algorithm"],
            key_id=parsed.get("key_id"),
            metadata=parsed.get("metadata", {}),
        )


# Decorators
def encrypted_field(
    key: Optional[str] = None,
    algorithm: Algorithm = Algorithm.AES_256_GCM,
) -> Callable:
    """Decorator for encrypted field."""
    def decorator(func: Callable) -> Callable:
        func._encrypted = True
        func._encryption_key = key
        func._encryption_algorithm = algorithm
        return func
    return decorator


def hash_on_save(
    algorithm: HashAlgorithm = HashAlgorithm.SHA256,
) -> Callable:
    """Decorator to hash value on save."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            
            if isinstance(result, (str, bytes)):
                crypto = EncryptionService()
                hash_result = await crypto.hash(result, algorithm)
                return hash_result.hex
            
            return result
        
        return wrapper
    return decorator


# Factory functions
def create_encryption_service(
    key_store: Optional[KeyStore] = None,
    default_algorithm: Algorithm = Algorithm.AES_256_GCM,
) -> EncryptionService:
    """Create encryption service."""
    return EncryptionService(key_store, default_algorithm)


def create_key_store() -> InMemoryKeyStore:
    """Create in-memory key store."""
    return InMemoryKeyStore()


def create_encryption_key(
    key_bytes: Optional[bytes] = None,
    algorithm: str = "aes-256-gcm",
    key_id: Optional[str] = None,
) -> EncryptionKey:
    """Create encryption key."""
    return EncryptionKey(
        id=key_id or str(uuid.uuid4()),
        type=KeyType.SYMMETRIC,
        algorithm=algorithm,
        key=key_bytes or secrets.token_bytes(32),
    )


__all__ = [
    # Exceptions
    "CryptoError",
    "EncryptionError",
    "DecryptionError",
    "KeyError",
    # Enums
    "Algorithm",
    "HashAlgorithm",
    "KeyType",
    # Data classes
    "EncryptionKey",
    "KeyPair",
    "EncryptedData",
    "HashResult",
    "DerivedKey",
    # Key Store
    "KeyStore",
    "InMemoryKeyStore",
    # Service
    "EncryptionService",
    # Decorators
    "encrypted_field",
    "hash_on_save",
    # Factory functions
    "create_encryption_service",
    "create_key_store",
    "create_encryption_key",
]
