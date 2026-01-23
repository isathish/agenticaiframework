"""
Enterprise Secret Vault Module.

Secret management, rotation, encryption,
and secure access control.

Example:
    # Create secret vault
    vault = create_secret_vault()
    
    # Store secret
    await vault.set(
        "database/password",
        "super-secret-value",
        metadata={"rotation": "30d"},
    )
    
    # Retrieve secret
    secret = await vault.get("database/password")
    print(secret.value)
    
    # Rotate secret
    await vault.rotate("database/password", new_value="new-secret")
    
    # With decorator
    @vault.inject("database.url", "database.password")
    async def connect_db(url: str, password: str):
        ...
"""

from __future__ import annotations

import asyncio
import base64
import functools
import hashlib
import logging
import os
import secrets
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    Iterator,
    List,
    Optional,
    Set,
    Tuple,
    TypeVar,
)

T = TypeVar('T')


logger = logging.getLogger(__name__)


class VaultError(Exception):
    """Vault error."""
    pass


class SecretNotFoundError(VaultError):
    """Secret not found."""
    pass


class AccessDeniedError(VaultError):
    """Access denied."""
    pass


class EncryptionError(VaultError):
    """Encryption error."""
    pass


class RotationError(VaultError):
    """Rotation error."""
    pass


class SecretType(str, Enum):
    """Secret types."""
    PASSWORD = "password"
    API_KEY = "api_key"
    TOKEN = "token"
    CERTIFICATE = "certificate"
    PRIVATE_KEY = "private_key"
    CONNECTION_STRING = "connection_string"
    JSON = "json"
    BINARY = "binary"


class RotationStatus(str, Enum):
    """Rotation status."""
    ACTIVE = "active"
    PENDING = "pending"
    ROTATING = "rotating"
    EXPIRED = "expired"


@dataclass
class Secret:
    """Secret data."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    path: str = ""
    value: str = ""
    secret_type: SecretType = SecretType.PASSWORD
    version: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    rotation_status: RotationStatus = RotationStatus.ACTIVE
    
    @property
    def is_expired(self) -> bool:
        """Check if secret is expired."""
        if self.expires_at:
            return datetime.utcnow() > self.expires_at
        return False


@dataclass
class SecretVersion:
    """Secret version."""
    version: int
    value: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str = ""
    is_current: bool = True


@dataclass
class AccessPolicy:
    """Access policy."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    path_pattern: str = "*"
    permissions: Set[str] = field(default_factory=lambda: {"read"})
    principals: Set[str] = field(default_factory=set)
    
    def matches(self, path: str) -> bool:
        """Check if path matches pattern."""
        import fnmatch
        return fnmatch.fnmatch(path, self.path_pattern)
    
    def allows(self, permission: str) -> bool:
        """Check if permission is allowed."""
        return permission in self.permissions


@dataclass
class AuditLog:
    """Audit log entry."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action: str = ""
    path: str = ""
    principal: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    success: bool = True
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VaultStats:
    """Vault statistics."""
    total_secrets: int = 0
    secrets_by_type: Dict[str, int] = field(default_factory=dict)
    expiring_soon: int = 0
    total_versions: int = 0


# Encryption interface
class Encryptor(ABC):
    """Abstract encryptor."""
    
    @abstractmethod
    def encrypt(self, plaintext: str) -> str:
        """Encrypt value."""
        pass
    
    @abstractmethod
    def decrypt(self, ciphertext: str) -> str:
        """Decrypt value."""
        pass


class AESEncryptor(Encryptor):
    """AES encryption (simplified mock)."""
    
    def __init__(self, key: Optional[bytes] = None):
        self._key = key or secrets.token_bytes(32)
    
    def encrypt(self, plaintext: str) -> str:
        """Mock encryption - base64 encode."""
        # In production, use proper AES encryption
        encoded = base64.b64encode(plaintext.encode()).decode()
        return f"enc:{encoded}"
    
    def decrypt(self, ciphertext: str) -> str:
        """Mock decryption - base64 decode."""
        if ciphertext.startswith("enc:"):
            encoded = ciphertext[4:]
            return base64.b64decode(encoded).decode()
        return ciphertext


class NoEncryptor(Encryptor):
    """No-op encryptor for testing."""
    
    def encrypt(self, plaintext: str) -> str:
        return plaintext
    
    def decrypt(self, ciphertext: str) -> str:
        return ciphertext


# Storage interface
class SecretStorage(ABC):
    """Abstract secret storage."""
    
    @abstractmethod
    async def store(self, path: str, secret: Secret) -> None:
        """Store secret."""
        pass
    
    @abstractmethod
    async def retrieve(self, path: str) -> Optional[Secret]:
        """Retrieve secret."""
        pass
    
    @abstractmethod
    async def delete(self, path: str) -> bool:
        """Delete secret."""
        pass
    
    @abstractmethod
    async def list(self, prefix: str) -> List[str]:
        """List secret paths."""
        pass


class InMemoryStorage(SecretStorage):
    """In-memory secret storage."""
    
    def __init__(self):
        self._secrets: Dict[str, Secret] = {}
        self._versions: Dict[str, List[SecretVersion]] = defaultdict(list)
    
    async def store(self, path: str, secret: Secret) -> None:
        # Store version
        if path in self._secrets:
            old_secret = self._secrets[path]
            self._versions[path].append(SecretVersion(
                version=old_secret.version,
                value=old_secret.value,
                is_current=False,
            ))
        
        self._secrets[path] = secret
    
    async def retrieve(self, path: str) -> Optional[Secret]:
        return self._secrets.get(path)
    
    async def delete(self, path: str) -> bool:
        if path in self._secrets:
            del self._secrets[path]
            return True
        return False
    
    async def list(self, prefix: str) -> List[str]:
        return [
            path for path in self._secrets.keys()
            if path.startswith(prefix)
        ]
    
    async def get_versions(self, path: str) -> List[SecretVersion]:
        """Get secret versions."""
        versions = list(self._versions.get(path, []))
        
        if path in self._secrets:
            current = self._secrets[path]
            versions.append(SecretVersion(
                version=current.version,
                value=current.value,
                created_at=current.updated_at,
                is_current=True,
            ))
        
        return sorted(versions, key=lambda v: v.version)


# Secret vault
class SecretVault:
    """
    Secret vault service.
    """
    
    def __init__(
        self,
        storage: Optional[SecretStorage] = None,
        encryptor: Optional[Encryptor] = None,
        enable_audit: bool = True,
    ):
        self._storage = storage or InMemoryStorage()
        self._encryptor = encryptor or AESEncryptor()
        self._enable_audit = enable_audit
        self._policies: List[AccessPolicy] = []
        self._audit_logs: List[AuditLog] = []
        self._rotation_handlers: Dict[str, Callable] = {}
        self._current_principal: str = "system"
    
    def set_principal(self, principal: str) -> None:
        """Set current principal for access control."""
        self._current_principal = principal
    
    async def set(
        self,
        path: str,
        value: str,
        secret_type: SecretType = SecretType.PASSWORD,
        metadata: Optional[Dict[str, Any]] = None,
        ttl: Optional[timedelta] = None,
    ) -> Secret:
        """
        Store a secret.
        
        Args:
            path: Secret path
            value: Secret value
            secret_type: Secret type
            metadata: Additional metadata
            ttl: Time to live
            
        Returns:
            Stored secret
        """
        self._check_permission(path, "write")
        
        # Check for existing secret
        existing = await self._storage.retrieve(path)
        version = (existing.version + 1) if existing else 1
        
        # Encrypt value
        encrypted_value = self._encryptor.encrypt(value)
        
        # Create secret
        secret = Secret(
            path=path,
            value=encrypted_value,
            secret_type=secret_type,
            version=version,
            metadata=metadata or {},
            expires_at=(datetime.utcnow() + ttl) if ttl else None,
        )
        
        await self._storage.store(path, secret)
        
        self._audit("set", path, success=True)
        
        logger.info(f"Stored secret: {path} (version {version})")
        
        return secret
    
    async def get(
        self,
        path: str,
        version: Optional[int] = None,
    ) -> Secret:
        """
        Retrieve a secret.
        
        Args:
            path: Secret path
            version: Specific version (None for latest)
            
        Returns:
            Secret
            
        Raises:
            SecretNotFoundError: If not found
        """
        self._check_permission(path, "read")
        
        secret = await self._storage.retrieve(path)
        
        if not secret:
            self._audit("get", path, success=False)
            raise SecretNotFoundError(f"Secret not found: {path}")
        
        # Check expiration
        if secret.is_expired:
            self._audit("get", path, success=False, details={"reason": "expired"})
            raise SecretNotFoundError(f"Secret expired: {path}")
        
        # Decrypt value
        decrypted = Secret(
            id=secret.id,
            path=secret.path,
            value=self._encryptor.decrypt(secret.value),
            secret_type=secret.secret_type,
            version=secret.version,
            metadata=secret.metadata,
            created_at=secret.created_at,
            updated_at=secret.updated_at,
            expires_at=secret.expires_at,
            rotation_status=secret.rotation_status,
        )
        
        self._audit("get", path, success=True)
        
        return decrypted
    
    async def delete(self, path: str) -> bool:
        """
        Delete a secret.
        
        Args:
            path: Secret path
            
        Returns:
            True if deleted
        """
        self._check_permission(path, "delete")
        
        result = await self._storage.delete(path)
        
        self._audit("delete", path, success=result)
        
        if result:
            logger.info(f"Deleted secret: {path}")
        
        return result
    
    async def list(
        self,
        prefix: str = "",
    ) -> List[str]:
        """
        List secret paths.
        
        Args:
            prefix: Path prefix
            
        Returns:
            List of paths
        """
        self._check_permission(prefix or "*", "list")
        
        paths = await self._storage.list(prefix)
        
        self._audit("list", prefix or "*", success=True)
        
        return paths
    
    async def rotate(
        self,
        path: str,
        new_value: Optional[str] = None,
        generator: Optional[Callable[[], str]] = None,
    ) -> Secret:
        """
        Rotate a secret.
        
        Args:
            path: Secret path
            new_value: New value (or use generator)
            generator: Value generator function
            
        Returns:
            New secret version
        """
        self._check_permission(path, "rotate")
        
        # Get existing
        existing = await self._storage.retrieve(path)
        
        if not existing:
            raise SecretNotFoundError(f"Secret not found: {path}")
        
        # Generate new value
        if new_value is None:
            if generator:
                new_value = generator()
            elif path in self._rotation_handlers:
                new_value = await self._rotation_handlers[path]()
            else:
                new_value = self._generate_secret(existing.secret_type)
        
        # Update secret
        existing.rotation_status = RotationStatus.ROTATING
        await self._storage.store(path, existing)
        
        # Store new version
        new_secret = await self.set(
            path=path,
            value=new_value,
            secret_type=existing.secret_type,
            metadata=existing.metadata,
        )
        
        new_secret.rotation_status = RotationStatus.ACTIVE
        await self._storage.store(path, new_secret)
        
        self._audit("rotate", path, success=True)
        
        logger.info(f"Rotated secret: {path} (version {new_secret.version})")
        
        return new_secret
    
    def _generate_secret(
        self,
        secret_type: SecretType,
    ) -> str:
        """Generate secret value."""
        if secret_type == SecretType.PASSWORD:
            return secrets.token_urlsafe(32)
        elif secret_type == SecretType.API_KEY:
            return f"sk_{secrets.token_hex(24)}"
        elif secret_type == SecretType.TOKEN:
            return secrets.token_urlsafe(48)
        
        return secrets.token_urlsafe(32)
    
    async def get_versions(self, path: str) -> List[SecretVersion]:
        """Get all versions of a secret."""
        self._check_permission(path, "read")
        
        if isinstance(self._storage, InMemoryStorage):
            return await self._storage.get_versions(path)
        
        return []
    
    def add_policy(self, policy: AccessPolicy) -> None:
        """Add access policy."""
        self._policies.append(policy)
    
    def _check_permission(
        self,
        path: str,
        permission: str,
    ) -> None:
        """Check if current principal has permission."""
        if self._current_principal == "system":
            return
        
        for policy in self._policies:
            if self._current_principal in policy.principals:
                if policy.matches(path) and policy.allows(permission):
                    return
        
        raise AccessDeniedError(
            f"Access denied for {self._current_principal} to {path}"
        )
    
    def _audit(
        self,
        action: str,
        path: str,
        success: bool = True,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Create audit log entry."""
        if not self._enable_audit:
            return
        
        log = AuditLog(
            action=action,
            path=path,
            principal=self._current_principal,
            success=success,
            details=details or {},
        )
        
        self._audit_logs.append(log)
    
    def get_audit_logs(
        self,
        path: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 100,
    ) -> List[AuditLog]:
        """Get audit logs."""
        logs = self._audit_logs
        
        if path:
            logs = [l for l in logs if l.path == path]
        
        if action:
            logs = [l for l in logs if l.action == action]
        
        return logs[-limit:]
    
    def register_rotation_handler(
        self,
        path: str,
        handler: Callable,
    ) -> None:
        """Register rotation handler for path."""
        self._rotation_handlers[path] = handler
    
    async def check_expiring(
        self,
        within: timedelta = timedelta(days=7),
    ) -> List[Secret]:
        """Get secrets expiring within timeframe."""
        expiring = []
        threshold = datetime.utcnow() + within
        
        paths = await self._storage.list("")
        
        for path in paths:
            secret = await self._storage.retrieve(path)
            if secret and secret.expires_at and secret.expires_at < threshold:
                expiring.append(secret)
        
        return expiring
    
    async def get_stats(self) -> VaultStats:
        """Get vault statistics."""
        stats = VaultStats()
        
        paths = await self._storage.list("")
        stats.total_secrets = len(paths)
        
        for path in paths:
            secret = await self._storage.retrieve(path)
            if secret:
                secret_type = secret.secret_type.value
                stats.secrets_by_type[secret_type] = (
                    stats.secrets_by_type.get(secret_type, 0) + 1
                )
                
                if secret.expires_at:
                    if secret.expires_at < datetime.utcnow() + timedelta(days=7):
                        stats.expiring_soon += 1
        
        return stats
    
    def inject(self, *secret_paths: str) -> Callable:
        """
        Decorator to inject secrets.
        
        Args:
            *secret_paths: Paths to inject as arguments
            
        Returns:
            Decorator
        """
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                # Fetch secrets
                secrets_values = []
                
                for path in secret_paths:
                    secret = await self.get(path)
                    secrets_values.append(secret.value)
                
                # Inject as positional args
                return await func(*args, *secrets_values, **kwargs)
            
            return wrapper
        
        return decorator


# Factory functions
def create_secret_vault(
    encryptor: Optional[Encryptor] = None,
    enable_audit: bool = True,
) -> SecretVault:
    """Create secret vault."""
    return SecretVault(
        encryptor=encryptor,
        enable_audit=enable_audit,
    )


def create_access_policy(
    name: str,
    path_pattern: str,
    permissions: Optional[Set[str]] = None,
    principals: Optional[Set[str]] = None,
) -> AccessPolicy:
    """Create access policy."""
    return AccessPolicy(
        name=name,
        path_pattern=path_pattern,
        permissions=permissions or {"read"},
        principals=principals or set(),
    )


def create_aes_encryptor(
    key: Optional[bytes] = None,
) -> AESEncryptor:
    """Create AES encryptor."""
    return AESEncryptor(key=key)


__all__ = [
    # Exceptions
    "VaultError",
    "SecretNotFoundError",
    "AccessDeniedError",
    "EncryptionError",
    "RotationError",
    # Enums
    "SecretType",
    "RotationStatus",
    # Data classes
    "Secret",
    "SecretVersion",
    "AccessPolicy",
    "AuditLog",
    "VaultStats",
    # Encryption
    "Encryptor",
    "AESEncryptor",
    "NoEncryptor",
    # Storage
    "SecretStorage",
    "InMemoryStorage",
    # Vault
    "SecretVault",
    # Factory functions
    "create_secret_vault",
    "create_access_policy",
    "create_aes_encryptor",
]
