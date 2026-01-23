"""
Enterprise Secret Manager Module.

Credential storage, secret rotation,
encryption, and secure access.

Example:
    # Create secret manager
    secrets = create_secret_manager(encryption_key="...")
    
    # Store secrets
    await secrets.set("database.password", "secret123")
    await secrets.set("api.key", "key123", expires_in=3600)
    
    # Retrieve secrets
    password = await secrets.get("database.password")
    
    # Rotate secrets
    await secrets.rotate("database.password", new_value="newsecret")
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import os
import secrets as py_secrets
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    Callable,
    Coroutine,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    Tuple,
    TypeVar,
    Union,
)

T = TypeVar('T')

logger = logging.getLogger(__name__)


class SecretError(Exception):
    """Secret error."""
    pass


class SecretNotFound(SecretError):
    """Secret not found."""
    pass


class SecretExpired(SecretError):
    """Secret expired."""
    pass


class SecretAccessDenied(SecretError):
    """Secret access denied."""
    pass


class SecretType(str, Enum):
    """Secret type."""
    PASSWORD = "password"
    API_KEY = "api_key"
    TOKEN = "token"
    CERTIFICATE = "certificate"
    SSH_KEY = "ssh_key"
    DATABASE_CREDENTIAL = "database_credential"
    OAUTH_CLIENT = "oauth_client"
    GENERIC = "generic"


class AccessLevel(str, Enum):
    """Access level."""
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"


@dataclass
class Secret:
    """Secret entry."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    secret_type: SecretType = SecretType.GENERIC
    value: bytes = b""  # Encrypted value
    version: int = 1
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    rotation_period: Optional[int] = None  # seconds
    last_rotated: Optional[datetime] = None
    last_accessed: Optional[datetime] = None
    access_count: int = 0
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SecretVersion:
    """Secret version."""
    version: int = 1
    value: bytes = b""
    created_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str = ""
    reason: str = ""


@dataclass
class SecretAccess:
    """Secret access record."""
    secret_name: str = ""
    accessor: str = ""
    access_type: str = "read"
    accessed_at: datetime = field(default_factory=datetime.utcnow)
    ip_address: str = ""
    success: bool = True


@dataclass
class SecretStats:
    """Secret statistics."""
    total_secrets: int = 0
    expired_secrets: int = 0
    rotation_due: int = 0
    total_accesses: int = 0


# Encryptor
class Encryptor(ABC):
    """Secret encryptor."""
    
    @abstractmethod
    def encrypt(self, plaintext: str) -> bytes:
        pass
    
    @abstractmethod
    def decrypt(self, ciphertext: bytes) -> str:
        pass


class FernetEncryptor(Encryptor):
    """Fernet encryption (requires cryptography library)."""
    
    def __init__(self, key: bytes):
        try:
            from cryptography.fernet import Fernet
            self._fernet = Fernet(key)
        except ImportError:
            raise ImportError("cryptography library required for FernetEncryptor")
    
    def encrypt(self, plaintext: str) -> bytes:
        return self._fernet.encrypt(plaintext.encode())
    
    def decrypt(self, ciphertext: bytes) -> str:
        return self._fernet.decrypt(ciphertext).decode()


class SimpleEncryptor(Encryptor):
    """Simple XOR-based encryptor (for testing only)."""
    
    def __init__(self, key: str):
        self._key = hashlib.sha256(key.encode()).digest()
    
    def _xor(self, data: bytes, key: bytes) -> bytes:
        result = bytearray()
        for i, b in enumerate(data):
            result.append(b ^ key[i % len(key)])
        return bytes(result)
    
    def encrypt(self, plaintext: str) -> bytes:
        data = plaintext.encode()
        encrypted = self._xor(data, self._key)
        return base64.b64encode(encrypted)
    
    def decrypt(self, ciphertext: bytes) -> str:
        encrypted = base64.b64decode(ciphertext)
        decrypted = self._xor(encrypted, self._key)
        return decrypted.decode()


# Secret store
class SecretStore(ABC):
    """Secret storage backend."""
    
    @abstractmethod
    async def save(self, secret: Secret) -> None:
        pass
    
    @abstractmethod
    async def get(self, name: str) -> Optional[Secret]:
        pass
    
    @abstractmethod
    async def delete(self, name: str) -> bool:
        pass
    
    @abstractmethod
    async def list_all(self, prefix: str = "") -> List[Secret]:
        pass
    
    @abstractmethod
    async def save_version(self, name: str, version: SecretVersion) -> None:
        pass
    
    @abstractmethod
    async def get_versions(self, name: str) -> List[SecretVersion]:
        pass


class InMemorySecretStore(SecretStore):
    """In-memory secret store."""
    
    def __init__(self):
        self._secrets: Dict[str, Secret] = {}
        self._versions: Dict[str, List[SecretVersion]] = {}
    
    async def save(self, secret: Secret) -> None:
        self._secrets[secret.name] = secret
    
    async def get(self, name: str) -> Optional[Secret]:
        return self._secrets.get(name)
    
    async def delete(self, name: str) -> bool:
        if name in self._secrets:
            del self._secrets[name]
            self._versions.pop(name, None)
            return True
        return False
    
    async def list_all(self, prefix: str = "") -> List[Secret]:
        if not prefix:
            return list(self._secrets.values())
        return [s for s in self._secrets.values() if s.name.startswith(prefix)]
    
    async def save_version(self, name: str, version: SecretVersion) -> None:
        if name not in self._versions:
            self._versions[name] = []
        self._versions[name].append(version)
    
    async def get_versions(self, name: str) -> List[SecretVersion]:
        return self._versions.get(name, [])


# Access log
class AccessLog(ABC):
    """Secret access log."""
    
    @abstractmethod
    async def log(self, access: SecretAccess) -> None:
        pass
    
    @abstractmethod
    async def get_history(self, secret_name: str, limit: int = 100) -> List[SecretAccess]:
        pass


class InMemoryAccessLog(AccessLog):
    """In-memory access log."""
    
    def __init__(self, max_history: int = 1000):
        self._history: List[SecretAccess] = []
        self._by_secret: Dict[str, List[SecretAccess]] = {}
        self._max_history = max_history
    
    async def log(self, access: SecretAccess) -> None:
        self._history.append(access)
        
        if access.secret_name not in self._by_secret:
            self._by_secret[access.secret_name] = []
        
        self._by_secret[access.secret_name].append(access)
        
        # Trim history
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]
    
    async def get_history(self, secret_name: str, limit: int = 100) -> List[SecretAccess]:
        return self._by_secret.get(secret_name, [])[-limit:]


# Secret manager
class SecretManager:
    """Secret manager."""
    
    def __init__(
        self,
        store: Optional[SecretStore] = None,
        encryptor: Optional[Encryptor] = None,
        access_log: Optional[AccessLog] = None,
        encryption_key: Optional[str] = None,
    ):
        self._store = store or InMemorySecretStore()
        
        if encryptor:
            self._encryptor = encryptor
        elif encryption_key:
            self._encryptor = SimpleEncryptor(encryption_key)
        else:
            # Generate random key
            self._encryptor = SimpleEncryptor(py_secrets.token_hex(32))
        
        self._access_log = access_log or InMemoryAccessLog()
        self._stats = SecretStats()
    
    async def set(
        self,
        name: str,
        value: str,
        secret_type: SecretType = SecretType.GENERIC,
        description: str = "",
        expires_in: Optional[int] = None,
        rotation_period: Optional[int] = None,
        tags: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> Secret:
        """Set secret value."""
        # Encrypt value
        encrypted = self._encryptor.encrypt(value)
        
        # Check if exists
        existing = await self._store.get(name)
        version = (existing.version + 1) if existing else 1
        
        # Calculate expiry
        expires_at = None
        if expires_in:
            expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        
        secret = Secret(
            name=name,
            description=description,
            secret_type=secret_type,
            value=encrypted,
            version=version,
            expires_at=expires_at,
            rotation_period=rotation_period,
            tags=tags or {},
            **kwargs,
        )
        
        await self._store.save(secret)
        
        # Save version
        version_record = SecretVersion(
            version=version,
            value=encrypted,
            reason="set" if not existing else "update",
        )
        await self._store.save_version(name, version_record)
        
        self._stats.total_secrets = len(await self._store.list_all())
        
        logger.info(f"Secret set: {name} (v{version})")
        
        return secret
    
    async def get(
        self,
        name: str,
        version: Optional[int] = None,
        accessor: str = "",
    ) -> str:
        """Get secret value."""
        secret = await self._store.get(name)
        
        if not secret:
            raise SecretNotFound(f"Secret not found: {name}")
        
        # Check expiry
        if secret.expires_at and datetime.utcnow() > secret.expires_at:
            raise SecretExpired(f"Secret expired: {name}")
        
        # Get specific version
        if version and version != secret.version:
            versions = await self._store.get_versions(name)
            for v in versions:
                if v.version == version:
                    value = self._encryptor.decrypt(v.value)
                    break
            else:
                raise SecretNotFound(f"Secret version not found: {name} v{version}")
        else:
            value = self._encryptor.decrypt(secret.value)
        
        # Update access info
        secret.last_accessed = datetime.utcnow()
        secret.access_count += 1
        await self._store.save(secret)
        
        # Log access
        await self._access_log.log(SecretAccess(
            secret_name=name,
            accessor=accessor,
            access_type="read",
        ))
        
        self._stats.total_accesses += 1
        
        return value
    
    async def delete(
        self,
        name: str,
        accessor: str = "",
    ) -> bool:
        """Delete secret."""
        result = await self._store.delete(name)
        
        if result:
            await self._access_log.log(SecretAccess(
                secret_name=name,
                accessor=accessor,
                access_type="delete",
            ))
            
            logger.info(f"Secret deleted: {name}")
        
        return result
    
    async def rotate(
        self,
        name: str,
        new_value: Optional[str] = None,
        accessor: str = "",
    ) -> Secret:
        """Rotate secret value."""
        secret = await self._store.get(name)
        
        if not secret:
            raise SecretNotFound(f"Secret not found: {name}")
        
        # Generate new value if not provided
        if not new_value:
            new_value = py_secrets.token_urlsafe(32)
        
        # Encrypt new value
        encrypted = self._encryptor.encrypt(new_value)
        
        # Update secret
        secret.value = encrypted
        secret.version += 1
        secret.updated_at = datetime.utcnow()
        secret.last_rotated = datetime.utcnow()
        
        await self._store.save(secret)
        
        # Save version
        version_record = SecretVersion(
            version=secret.version,
            value=encrypted,
            created_by=accessor,
            reason="rotation",
        )
        await self._store.save_version(name, version_record)
        
        # Log access
        await self._access_log.log(SecretAccess(
            secret_name=name,
            accessor=accessor,
            access_type="rotate",
        ))
        
        logger.info(f"Secret rotated: {name} (v{secret.version})")
        
        return secret
    
    async def exists(self, name: str) -> bool:
        """Check if secret exists."""
        secret = await self._store.get(name)
        return secret is not None
    
    async def get_info(self, name: str) -> Optional[Secret]:
        """Get secret info without value."""
        secret = await self._store.get(name)
        
        if secret:
            # Return copy without value
            return Secret(
                id=secret.id,
                name=secret.name,
                description=secret.description,
                secret_type=secret.type,
                version=secret.version,
                created_at=secret.created_at,
                updated_at=secret.updated_at,
                expires_at=secret.expires_at,
                rotation_period=secret.rotation_period,
                last_rotated=secret.last_rotated,
                last_accessed=secret.last_accessed,
                access_count=secret.access_count,
                tags=secret.tags,
                metadata=secret.metadata,
            )
        
        return None
    
    async def list_secrets(self, prefix: str = "") -> List[str]:
        """List secret names."""
        secrets = await self._store.list_all(prefix)
        return [s.name for s in secrets]
    
    async def get_versions(self, name: str) -> List[SecretVersion]:
        """Get secret versions."""
        return await self._store.get_versions(name)
    
    async def get_access_history(
        self,
        name: str,
        limit: int = 100,
    ) -> List[SecretAccess]:
        """Get access history."""
        return await self._access_log.get_history(name, limit)
    
    async def check_rotation_due(self) -> List[str]:
        """Get secrets due for rotation."""
        secrets = await self._store.list_all()
        due = []
        now = datetime.utcnow()
        
        for secret in secrets:
            if secret.rotation_period and secret.last_rotated:
                next_rotation = secret.last_rotated + timedelta(seconds=secret.rotation_period)
                if now >= next_rotation:
                    due.append(secret.name)
            elif secret.rotation_period and not secret.last_rotated:
                # Never rotated, check against creation
                next_rotation = secret.created_at + timedelta(seconds=secret.rotation_period)
                if now >= next_rotation:
                    due.append(secret.name)
        
        self._stats.rotation_due = len(due)
        
        return due
    
    async def check_expired(self) -> List[str]:
        """Get expired secrets."""
        secrets = await self._store.list_all()
        expired = []
        now = datetime.utcnow()
        
        for secret in secrets:
            if secret.expires_at and now >= secret.expires_at:
                expired.append(secret.name)
        
        self._stats.expired_secrets = len(expired)
        
        return expired
    
    def generate_password(
        self,
        length: int = 32,
        include_special: bool = True,
    ) -> str:
        """Generate secure password."""
        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        
        if include_special:
            alphabet += "!@#$%^&*()-_=+[]{}|;:,.<>?"
        
        return "".join(py_secrets.choice(alphabet) for _ in range(length))
    
    def generate_token(self, length: int = 32) -> str:
        """Generate secure token."""
        return py_secrets.token_urlsafe(length)
    
    def generate_api_key(self, prefix: str = "") -> str:
        """Generate API key."""
        key = py_secrets.token_hex(32)
        return f"{prefix}{key}" if prefix else key
    
    def get_stats(self) -> SecretStats:
        """Get statistics."""
        return self._stats


# Factory functions
def create_secret_manager(
    encryption_key: Optional[str] = None,
) -> SecretManager:
    """Create secret manager."""
    return SecretManager(encryption_key=encryption_key)


def create_secret(
    name: str,
    value: str,
    secret_type: SecretType = SecretType.GENERIC,
    **kwargs,
) -> Secret:
    """Create secret (not encrypted, use manager for actual secrets)."""
    return Secret(
        name=name,
        value=value.encode(),
        secret_type=secret_type,
        **kwargs,
    )


def generate_encryption_key() -> str:
    """Generate encryption key."""
    return py_secrets.token_urlsafe(32)


__all__ = [
    # Exceptions
    "SecretError",
    "SecretNotFound",
    "SecretExpired",
    "SecretAccessDenied",
    # Enums
    "SecretType",
    "AccessLevel",
    # Data classes
    "Secret",
    "SecretVersion",
    "SecretAccess",
    "SecretStats",
    # Encryptors
    "Encryptor",
    "FernetEncryptor",
    "SimpleEncryptor",
    # Stores
    "SecretStore",
    "InMemorySecretStore",
    # Access log
    "AccessLog",
    "InMemoryAccessLog",
    # Manager
    "SecretManager",
    # Factory functions
    "create_secret_manager",
    "create_secret",
    "generate_encryption_key",
]
