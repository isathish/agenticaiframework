"""
Enterprise Encryption Module.

Provides field-level encryption, envelope encryption, and key rotation
for secure data handling in agent applications.

Example:
    # Field-level encryption
    encryptor = FieldEncryptor(key=secret_key)
    encrypted = encryptor.encrypt_field(data, "credit_card")
    
    # Envelope encryption
    envelope = EnvelopeEncryptor(kms_client)
    encrypted_data = await envelope.encrypt(large_data)
    
    # Key rotation
    rotator = KeyRotator(key_provider)
    await rotator.rotate_key("api_key")
"""

from __future__ import annotations

import os
import base64
import hashlib
import secrets
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Type,
    TypeVar,
    Union,
)
from datetime import datetime, timedelta
from enum import Enum
import logging

logger = logging.getLogger(__name__)

T = TypeVar("T")


class EncryptionError(Exception):
    """Encryption operation failed."""
    pass


class DecryptionError(Exception):
    """Decryption operation failed."""
    pass


class KeyError(Exception):
    """Key management error."""
    pass


class Algorithm(str, Enum):
    """Encryption algorithms."""
    AES_256_GCM = "aes-256-gcm"
    AES_256_CBC = "aes-256-cbc"
    CHACHA20_POLY1305 = "chacha20-poly1305"
    FERNET = "fernet"


@dataclass
class EncryptedValue:
    """Encrypted value with metadata."""
    ciphertext: bytes
    algorithm: Algorithm
    key_id: str
    iv: Optional[bytes] = None
    tag: Optional[bytes] = None
    created_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "ciphertext": base64.b64encode(self.ciphertext).decode(),
            "algorithm": self.algorithm.value,
            "key_id": self.key_id,
            "iv": base64.b64encode(self.iv).decode() if self.iv else None,
            "tag": base64.b64encode(self.tag).decode() if self.tag else None,
            "created_at": self.created_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EncryptedValue':
        """Create from dictionary."""
        return cls(
            ciphertext=base64.b64decode(data["ciphertext"]),
            algorithm=Algorithm(data["algorithm"]),
            key_id=data["key_id"],
            iv=base64.b64decode(data["iv"]) if data.get("iv") else None,
            tag=base64.b64decode(data["tag"]) if data.get("tag") else None,
            created_at=data.get("created_at", time.time()),
        )
    
    def to_string(self) -> str:
        """Encode to compact string."""
        return base64.b64encode(
            json.dumps(self.to_dict()).encode()
        ).decode()
    
    @classmethod
    def from_string(cls, data: str) -> 'EncryptedValue':
        """Decode from compact string."""
        decoded = json.loads(base64.b64decode(data))
        return cls.from_dict(decoded)


@dataclass
class KeyInfo:
    """Information about an encryption key."""
    key_id: str
    algorithm: Algorithm
    created_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None
    is_active: bool = True
    version: int = 1
    
    @property
    def is_expired(self) -> bool:
        """Check if key is expired."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at


class KeyProvider(ABC):
    """Abstract key provider interface."""
    
    @abstractmethod
    async def get_key(self, key_id: str) -> bytes:
        """Get encryption key by ID."""
        pass
    
    @abstractmethod
    async def create_key(
        self,
        key_id: str,
        algorithm: Algorithm = Algorithm.AES_256_GCM,
    ) -> KeyInfo:
        """Create a new encryption key."""
        pass
    
    @abstractmethod
    async def rotate_key(self, key_id: str) -> KeyInfo:
        """Rotate an existing key."""
        pass
    
    @abstractmethod
    async def list_keys(self) -> List[KeyInfo]:
        """List all available keys."""
        pass


class InMemoryKeyProvider(KeyProvider):
    """In-memory key provider for development."""
    
    def __init__(self):
        self._keys: Dict[str, bytes] = {}
        self._info: Dict[str, KeyInfo] = {}
    
    async def get_key(self, key_id: str) -> bytes:
        """Get key from memory."""
        if key_id not in self._keys:
            raise KeyError(f"Key not found: {key_id}")
        return self._keys[key_id]
    
    async def create_key(
        self,
        key_id: str,
        algorithm: Algorithm = Algorithm.AES_256_GCM,
    ) -> KeyInfo:
        """Create new key in memory."""
        # Generate key based on algorithm
        if algorithm in (Algorithm.AES_256_GCM, Algorithm.AES_256_CBC):
            key = secrets.token_bytes(32)  # 256 bits
        elif algorithm == Algorithm.CHACHA20_POLY1305:
            key = secrets.token_bytes(32)
        else:
            key = secrets.token_bytes(32)
        
        self._keys[key_id] = key
        info = KeyInfo(key_id=key_id, algorithm=algorithm)
        self._info[key_id] = info
        return info
    
    async def rotate_key(self, key_id: str) -> KeyInfo:
        """Rotate key in memory."""
        if key_id not in self._info:
            raise KeyError(f"Key not found: {key_id}")
        
        old_info = self._info[key_id]
        
        # Archive old key
        old_key_id = f"{key_id}_v{old_info.version}"
        self._keys[old_key_id] = self._keys[key_id]
        
        # Create new key
        new_key = secrets.token_bytes(32)
        self._keys[key_id] = new_key
        
        new_info = KeyInfo(
            key_id=key_id,
            algorithm=old_info.algorithm,
            version=old_info.version + 1,
        )
        self._info[key_id] = new_info
        
        # Mark old key as inactive
        old_info.is_active = False
        self._info[old_key_id] = old_info
        
        return new_info
    
    async def list_keys(self) -> List[KeyInfo]:
        """List all keys."""
        return list(self._info.values())


class Encryptor(ABC):
    """Abstract encryptor interface."""
    
    @abstractmethod
    async def encrypt(self, plaintext: bytes, key_id: Optional[str] = None) -> EncryptedValue:
        """Encrypt data."""
        pass
    
    @abstractmethod
    async def decrypt(self, encrypted: EncryptedValue) -> bytes:
        """Decrypt data."""
        pass


class AESGCMEncryptor(Encryptor):
    """AES-GCM encryptor."""
    
    def __init__(
        self,
        key_provider: KeyProvider,
        default_key_id: str = "default",
    ):
        self.key_provider = key_provider
        self.default_key_id = default_key_id
        self._crypto = None
    
    def _get_crypto(self):
        """Lazy import cryptography."""
        if self._crypto is None:
            try:
                from cryptography.hazmat.primitives.ciphers.aead import AESGCM
                self._crypto = AESGCM
            except ImportError:
                raise ImportError("cryptography package required for AESGCMEncryptor")
        return self._crypto
    
    async def encrypt(self, plaintext: bytes, key_id: Optional[str] = None) -> EncryptedValue:
        """Encrypt using AES-GCM."""
        AESGCM = self._get_crypto()
        key_id = key_id or self.default_key_id
        
        try:
            key = await self.key_provider.get_key(key_id)
            iv = secrets.token_bytes(12)  # 96-bit IV for GCM
            
            aesgcm = AESGCM(key)
            ciphertext = aesgcm.encrypt(iv, plaintext, None)
            
            return EncryptedValue(
                ciphertext=ciphertext,
                algorithm=Algorithm.AES_256_GCM,
                key_id=key_id,
                iv=iv,
            )
        except Exception as e:
            raise EncryptionError(f"AES-GCM encryption failed: {e}") from e
    
    async def decrypt(self, encrypted: EncryptedValue) -> bytes:
        """Decrypt using AES-GCM."""
        AESGCM = self._get_crypto()
        
        try:
            key = await self.key_provider.get_key(encrypted.key_id)
            aesgcm = AESGCM(key)
            
            return aesgcm.decrypt(encrypted.iv, encrypted.ciphertext, None)
        except Exception as e:
            raise DecryptionError(f"AES-GCM decryption failed: {e}") from e


class FernetEncryptor(Encryptor):
    """Fernet symmetric encryptor (simpler API)."""
    
    def __init__(
        self,
        key_provider: KeyProvider,
        default_key_id: str = "default",
    ):
        self.key_provider = key_provider
        self.default_key_id = default_key_id
        self._fernet = None
    
    def _get_fernet(self):
        """Lazy import Fernet."""
        if self._fernet is None:
            try:
                from cryptography.fernet import Fernet
                self._fernet = Fernet
            except ImportError:
                raise ImportError("cryptography package required for FernetEncryptor")
        return self._fernet
    
    async def encrypt(self, plaintext: bytes, key_id: Optional[str] = None) -> EncryptedValue:
        """Encrypt using Fernet."""
        Fernet = self._get_fernet()
        key_id = key_id or self.default_key_id
        
        try:
            key = await self.key_provider.get_key(key_id)
            # Fernet requires base64-encoded 32-byte key
            fernet_key = base64.urlsafe_b64encode(key[:32])
            f = Fernet(fernet_key)
            
            ciphertext = f.encrypt(plaintext)
            
            return EncryptedValue(
                ciphertext=ciphertext,
                algorithm=Algorithm.FERNET,
                key_id=key_id,
            )
        except Exception as e:
            raise EncryptionError(f"Fernet encryption failed: {e}") from e
    
    async def decrypt(self, encrypted: EncryptedValue) -> bytes:
        """Decrypt using Fernet."""
        Fernet = self._get_fernet()
        
        try:
            key = await self.key_provider.get_key(encrypted.key_id)
            fernet_key = base64.urlsafe_b64encode(key[:32])
            f = Fernet(fernet_key)
            
            return f.decrypt(encrypted.ciphertext)
        except Exception as e:
            raise DecryptionError(f"Fernet decryption failed: {e}") from e


class FieldEncryptor:
    """
    Field-level encryptor for sensitive data in dictionaries.
    """
    
    def __init__(
        self,
        encryptor: Encryptor,
        sensitive_fields: Optional[List[str]] = None,
    ):
        """
        Initialize field encryptor.
        
        Args:
            encryptor: Underlying encryptor
            sensitive_fields: List of field names to encrypt
        """
        self.encryptor = encryptor
        self.sensitive_fields = sensitive_fields or [
            "password", "secret", "token", "api_key", "credit_card",
            "ssn", "email", "phone", "address",
        ]
    
    async def encrypt_fields(
        self,
        data: Dict[str, Any],
        fields: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Encrypt specified fields in a dictionary.
        
        Args:
            data: Dictionary with data
            fields: Fields to encrypt (defaults to sensitive_fields)
            
        Returns:
            Dictionary with encrypted fields
        """
        result = dict(data)
        fields_to_encrypt = fields or self.sensitive_fields
        
        for field in fields_to_encrypt:
            if field in result and result[field] is not None:
                value = result[field]
                if isinstance(value, str):
                    value = value.encode()
                elif not isinstance(value, bytes):
                    value = json.dumps(value).encode()
                
                encrypted = await self.encryptor.encrypt(value)
                result[field] = encrypted.to_string()
        
        return result
    
    async def decrypt_fields(
        self,
        data: Dict[str, Any],
        fields: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Decrypt specified fields in a dictionary.
        
        Args:
            data: Dictionary with encrypted data
            fields: Fields to decrypt (defaults to sensitive_fields)
            
        Returns:
            Dictionary with decrypted fields
        """
        result = dict(data)
        fields_to_decrypt = fields or self.sensitive_fields
        
        for field in fields_to_decrypt:
            if field in result and result[field] is not None:
                try:
                    encrypted = EncryptedValue.from_string(result[field])
                    decrypted = await self.encryptor.decrypt(encrypted)
                    
                    # Try to parse as JSON
                    try:
                        result[field] = json.loads(decrypted)
                    except json.JSONDecodeError:
                        result[field] = decrypted.decode()
                        
                except Exception as e:
                    logger.warning(f"Could not decrypt field {field}: {e}")
        
        return result
    
    async def encrypt_field(
        self,
        data: Dict[str, Any],
        field: str,
    ) -> Dict[str, Any]:
        """Encrypt a single field."""
        return await self.encrypt_fields(data, [field])
    
    async def decrypt_field(
        self,
        data: Dict[str, Any],
        field: str,
    ) -> Dict[str, Any]:
        """Decrypt a single field."""
        return await self.decrypt_fields(data, [field])


@dataclass
class EnvelopeData:
    """Envelope-encrypted data."""
    encrypted_key: bytes
    encrypted_data: EncryptedValue
    key_id: str
    created_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "encrypted_key": base64.b64encode(self.encrypted_key).decode(),
            "encrypted_data": self.encrypted_data.to_dict(),
            "key_id": self.key_id,
            "created_at": self.created_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EnvelopeData':
        """Create from dictionary."""
        return cls(
            encrypted_key=base64.b64decode(data["encrypted_key"]),
            encrypted_data=EncryptedValue.from_dict(data["encrypted_data"]),
            key_id=data["key_id"],
            created_at=data.get("created_at", time.time()),
        )


class EnvelopeEncryptor:
    """
    Envelope encryption for large data.
    
    Uses a data encryption key (DEK) to encrypt data,
    and a key encryption key (KEK) to encrypt the DEK.
    """
    
    def __init__(
        self,
        key_provider: KeyProvider,
        master_key_id: str = "master",
    ):
        """
        Initialize envelope encryptor.
        
        Args:
            key_provider: Provider for master key
            master_key_id: ID of master key for encrypting DEKs
        """
        self.key_provider = key_provider
        self.master_key_id = master_key_id
        self._crypto = None
    
    def _get_crypto(self):
        """Lazy import cryptography."""
        if self._crypto is None:
            try:
                from cryptography.hazmat.primitives.ciphers.aead import AESGCM
                self._crypto = AESGCM
            except ImportError:
                raise ImportError("cryptography package required")
        return self._crypto
    
    async def encrypt(self, plaintext: bytes) -> EnvelopeData:
        """
        Encrypt data using envelope encryption.
        
        Args:
            plaintext: Data to encrypt
            
        Returns:
            EnvelopeData with encrypted DEK and data
        """
        AESGCM = self._get_crypto()
        
        try:
            # Generate random DEK
            dek = secrets.token_bytes(32)
            iv = secrets.token_bytes(12)
            
            # Encrypt data with DEK
            aesgcm = AESGCM(dek)
            ciphertext = aesgcm.encrypt(iv, plaintext, None)
            
            encrypted_data = EncryptedValue(
                ciphertext=ciphertext,
                algorithm=Algorithm.AES_256_GCM,
                key_id="dek",
                iv=iv,
            )
            
            # Encrypt DEK with master key
            master_key = await self.key_provider.get_key(self.master_key_id)
            kek_iv = secrets.token_bytes(12)
            kek_aesgcm = AESGCM(master_key)
            encrypted_dek = kek_aesgcm.encrypt(kek_iv, dek, None)
            
            # Combine IV with encrypted DEK
            encrypted_key = kek_iv + encrypted_dek
            
            return EnvelopeData(
                encrypted_key=encrypted_key,
                encrypted_data=encrypted_data,
                key_id=self.master_key_id,
            )
            
        except Exception as e:
            raise EncryptionError(f"Envelope encryption failed: {e}") from e
    
    async def decrypt(self, envelope: EnvelopeData) -> bytes:
        """
        Decrypt envelope-encrypted data.
        
        Args:
            envelope: Envelope data to decrypt
            
        Returns:
            Decrypted plaintext
        """
        AESGCM = self._get_crypto()
        
        try:
            # Decrypt DEK
            master_key = await self.key_provider.get_key(envelope.key_id)
            kek_iv = envelope.encrypted_key[:12]
            encrypted_dek = envelope.encrypted_key[12:]
            
            kek_aesgcm = AESGCM(master_key)
            dek = kek_aesgcm.decrypt(kek_iv, encrypted_dek, None)
            
            # Decrypt data with DEK
            aesgcm = AESGCM(dek)
            plaintext = aesgcm.decrypt(
                envelope.encrypted_data.iv,
                envelope.encrypted_data.ciphertext,
                None,
            )
            
            return plaintext
            
        except Exception as e:
            raise DecryptionError(f"Envelope decryption failed: {e}") from e


class KeyRotator:
    """
    Key rotation manager.
    """
    
    def __init__(
        self,
        key_provider: KeyProvider,
        encryptor: Encryptor,
        rotation_period: timedelta = timedelta(days=90),
    ):
        """
        Initialize key rotator.
        
        Args:
            key_provider: Key provider for rotation
            encryptor: Encryptor for re-encryption
            rotation_period: Period between rotations
        """
        self.key_provider = key_provider
        self.encryptor = encryptor
        self.rotation_period = rotation_period
    
    async def rotate_key(self, key_id: str) -> KeyInfo:
        """
        Rotate an encryption key.
        
        Args:
            key_id: Key to rotate
            
        Returns:
            New key info
        """
        return await self.key_provider.rotate_key(key_id)
    
    async def re_encrypt(
        self,
        encrypted: EncryptedValue,
        new_key_id: str,
    ) -> EncryptedValue:
        """
        Re-encrypt data with a new key.
        
        Args:
            encrypted: Currently encrypted data
            new_key_id: New key to use
            
        Returns:
            Newly encrypted data
        """
        # Decrypt with old key
        plaintext = await self.encryptor.decrypt(encrypted)
        
        # Encrypt with new key
        return await self.encryptor.encrypt(plaintext, new_key_id)
    
    async def check_rotation_needed(self, key_id: str) -> bool:
        """Check if a key needs rotation."""
        keys = await self.key_provider.list_keys()
        
        for key in keys:
            if key.key_id == key_id:
                age = time.time() - key.created_at
                return age > self.rotation_period.total_seconds()
        
        return False


def hash_value(value: str, salt: Optional[str] = None) -> str:
    """
    Hash a value using SHA-256.
    
    Args:
        value: Value to hash
        salt: Optional salt
        
    Returns:
        Hex-encoded hash
    """
    if salt:
        value = f"{salt}{value}"
    return hashlib.sha256(value.encode()).hexdigest()


def derive_key(
    password: str,
    salt: Optional[bytes] = None,
    iterations: int = 100000,
) -> tuple[bytes, bytes]:
    """
    Derive encryption key from password.
    
    Args:
        password: Password to derive from
        salt: Optional salt (generated if not provided)
        iterations: PBKDF2 iterations
        
    Returns:
        Tuple of (key, salt)
    """
    import hashlib
    
    if salt is None:
        salt = secrets.token_bytes(16)
    
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        salt,
        iterations,
        dklen=32,
    )
    
    return key, salt


__all__ = [
    # Exceptions
    "EncryptionError",
    "DecryptionError",
    "KeyError",
    # Enums
    "Algorithm",
    # Data classes
    "EncryptedValue",
    "KeyInfo",
    "EnvelopeData",
    # Key providers
    "KeyProvider",
    "InMemoryKeyProvider",
    # Encryptors
    "Encryptor",
    "AESGCMEncryptor",
    "FernetEncryptor",
    "FieldEncryptor",
    "EnvelopeEncryptor",
    # Key rotation
    "KeyRotator",
    # Utility functions
    "hash_value",
    "derive_key",
]
