"""
Enterprise Secrets Manager Module.

Provides secrets management, encryption, rotation,
vault integration, and secure access patterns.

Example:
    # Create secrets manager
    secrets = create_secrets_manager()
    
    # Store secret
    await secrets.set("database/password", "secret123")
    
    # Retrieve secret
    password = await secrets.get("database/password")
    
    # Use decorator
    @inject_secrets({"db_pass": "database/password"})
    async def connect_db(db_pass: str):
        ...
"""

from __future__ import annotations

import asyncio
import base64
import functools
import hashlib
import json
import logging
import os
import secrets as python_secrets
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    Tuple,
    TypeVar,
)

T = TypeVar('T')


logger = logging.getLogger(__name__)


class SecretError(Exception):
    """Base secret error."""
    pass


class SecretNotFoundError(SecretError):
    """Secret not found."""
    pass


class SecretAccessDeniedError(SecretError):
    """Secret access denied."""
    pass


class EncryptionError(SecretError):
    """Encryption error."""
    pass


class SecretType(str, Enum):
    """Secret type."""
    PASSWORD = "password"
    API_KEY = "api_key"
    CERTIFICATE = "certificate"
    SSH_KEY = "ssh_key"
    TOKEN = "token"
    GENERIC = "generic"


@dataclass
class SecretMetadata:
    """Secret metadata."""
    key: str
    type: SecretType = SecretType.GENERIC
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    version: int = 1
    expires_at: Optional[datetime] = None
    rotation_interval: Optional[timedelta] = None
    last_rotated: Optional[datetime] = None
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class SecretVersion:
    """Secret version."""
    version: int
    value: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str = ""
    is_current: bool = True


@dataclass
class SecretConfig:
    """Secrets manager configuration."""
    encryption_key: Optional[str] = None
    default_ttl: Optional[timedelta] = None
    auto_rotate: bool = False
    cache_enabled: bool = True
    cache_ttl: timedelta = field(default_factory=lambda: timedelta(minutes=5))


@dataclass
class AccessPolicy:
    """Secret access policy."""
    name: str
    paths: List[str] = field(default_factory=list)
    actions: List[str] = field(default_factory=lambda: ["read"])
    conditions: Dict[str, Any] = field(default_factory=dict)


class Encryptor(ABC):
    """Abstract encryptor."""
    
    @abstractmethod
    def encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext."""
        pass
    
    @abstractmethod
    def decrypt(self, ciphertext: str) -> str:
        """Decrypt ciphertext."""
        pass


class FernetEncryptor(Encryptor):
    """Fernet encryption (AES-128-CBC)."""
    
    def __init__(self, key: Optional[str] = None):
        try:
            from cryptography.fernet import Fernet
            
            if key:
                self._key = key.encode() if isinstance(key, str) else key
            else:
                self._key = Fernet.generate_key()
            
            self._fernet = Fernet(self._key)
        except ImportError:
            raise ImportError("cryptography package required for Fernet encryption")
    
    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()
    
    def decrypt(self, ciphertext: str) -> str:
        return self._fernet.decrypt(ciphertext.encode()).decode()
    
    @classmethod
    def generate_key(cls) -> str:
        """Generate a new encryption key."""
        from cryptography.fernet import Fernet
        return Fernet.generate_key().decode()


class Base64Encryptor(Encryptor):
    """Simple base64 encoding (NOT SECURE - for development only)."""
    
    def __init__(self, salt: str = ""):
        self._salt = salt
    
    def encrypt(self, plaintext: str) -> str:
        salted = f"{self._salt}{plaintext}"
        return base64.b64encode(salted.encode()).decode()
    
    def decrypt(self, ciphertext: str) -> str:
        decoded = base64.b64decode(ciphertext.encode()).decode()
        return decoded[len(self._salt):]


class NoopEncryptor(Encryptor):
    """No encryption (plaintext)."""
    
    def encrypt(self, plaintext: str) -> str:
        return plaintext
    
    def decrypt(self, ciphertext: str) -> str:
        return ciphertext


class SecretStore(ABC):
    """Abstract secret store."""
    
    @abstractmethod
    async def get(self, key: str) -> Optional[str]:
        """Get secret value."""
        pass
    
    @abstractmethod
    async def set(self, key: str, value: str, metadata: Optional[SecretMetadata] = None) -> None:
        """Set secret value."""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete secret."""
        pass
    
    @abstractmethod
    async def list(self, prefix: str = "") -> List[str]:
        """List secret keys."""
        pass
    
    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if secret exists."""
        pass


class InMemorySecretStore(SecretStore):
    """In-memory secret store."""
    
    def __init__(self):
        self._secrets: Dict[str, str] = {}
        self._metadata: Dict[str, SecretMetadata] = {}
        self._versions: Dict[str, List[SecretVersion]] = {}
    
    async def get(self, key: str) -> Optional[str]:
        return self._secrets.get(key)
    
    async def set(
        self,
        key: str,
        value: str,
        metadata: Optional[SecretMetadata] = None,
    ) -> None:
        # Handle versioning
        if key in self._secrets:
            old_value = self._secrets[key]
            if key not in self._versions:
                self._versions[key] = []
            
            # Mark old versions as not current
            for v in self._versions[key]:
                v.is_current = False
            
            # Get next version number
            version = len(self._versions[key]) + 1
            
            self._versions[key].append(SecretVersion(
                version=version,
                value=old_value,
                is_current=False,
            ))
        
        self._secrets[key] = value
        
        if metadata:
            self._metadata[key] = metadata
        elif key not in self._metadata:
            self._metadata[key] = SecretMetadata(key=key)
        else:
            self._metadata[key].updated_at = datetime.utcnow()
            self._metadata[key].version += 1
    
    async def delete(self, key: str) -> None:
        self._secrets.pop(key, None)
        self._metadata.pop(key, None)
        self._versions.pop(key, None)
    
    async def list(self, prefix: str = "") -> List[str]:
        return [k for k in self._secrets.keys() if k.startswith(prefix)]
    
    async def exists(self, key: str) -> bool:
        return key in self._secrets
    
    async def get_metadata(self, key: str) -> Optional[SecretMetadata]:
        return self._metadata.get(key)
    
    async def get_versions(self, key: str) -> List[SecretVersion]:
        return self._versions.get(key, [])


class EnvironmentSecretStore(SecretStore):
    """Environment variable secret store."""
    
    def __init__(self, prefix: str = "SECRET_"):
        self._prefix = prefix
    
    def _env_key(self, key: str) -> str:
        return f"{self._prefix}{key.upper().replace('/', '_').replace('-', '_')}"
    
    async def get(self, key: str) -> Optional[str]:
        return os.environ.get(self._env_key(key))
    
    async def set(
        self,
        key: str,
        value: str,
        metadata: Optional[SecretMetadata] = None,
    ) -> None:
        os.environ[self._env_key(key)] = value
    
    async def delete(self, key: str) -> None:
        env_key = self._env_key(key)
        if env_key in os.environ:
            del os.environ[env_key]
    
    async def list(self, prefix: str = "") -> List[str]:
        result = []
        full_prefix = f"{self._prefix}{prefix.upper().replace('/', '_')}"
        
        for key in os.environ.keys():
            if key.startswith(full_prefix):
                # Convert back to secret key format
                secret_key = key[len(self._prefix):].lower().replace('_', '/')
                result.append(secret_key)
        
        return result
    
    async def exists(self, key: str) -> bool:
        return self._env_key(key) in os.environ


class FileSecretStore(SecretStore):
    """File-based secret store."""
    
    def __init__(self, directory: str, encryptor: Optional[Encryptor] = None):
        self._directory = directory
        self._encryptor = encryptor or NoopEncryptor()
        os.makedirs(directory, exist_ok=True)
    
    def _file_path(self, key: str) -> str:
        # Convert key to safe filename
        safe_key = key.replace('/', '_').replace('\\', '_')
        return os.path.join(self._directory, f"{safe_key}.secret")
    
    async def get(self, key: str) -> Optional[str]:
        path = self._file_path(key)
        
        if not os.path.exists(path):
            return None
        
        with open(path, 'r') as f:
            data = json.load(f)
        
        return self._encryptor.decrypt(data['value'])
    
    async def set(
        self,
        key: str,
        value: str,
        metadata: Optional[SecretMetadata] = None,
    ) -> None:
        path = self._file_path(key)
        
        data = {
            'key': key,
            'value': self._encryptor.encrypt(value),
            'created_at': datetime.utcnow().isoformat(),
        }
        
        if metadata:
            data['metadata'] = {
                'type': metadata.type.value,
                'tags': metadata.tags,
            }
        
        with open(path, 'w') as f:
            json.dump(data, f)
    
    async def delete(self, key: str) -> None:
        path = self._file_path(key)
        if os.path.exists(path):
            os.remove(path)
    
    async def list(self, prefix: str = "") -> List[str]:
        result = []
        
        for filename in os.listdir(self._directory):
            if filename.endswith('.secret'):
                key = filename[:-7].replace('_', '/')
                if key.startswith(prefix):
                    result.append(key)
        
        return result
    
    async def exists(self, key: str) -> bool:
        return os.path.exists(self._file_path(key))


class SecretCache:
    """Secret cache with TTL."""
    
    def __init__(self, ttl: timedelta = timedelta(minutes=5)):
        self._cache: Dict[str, Tuple[str, datetime]] = {}
        self._ttl = ttl
    
    def get(self, key: str) -> Optional[str]:
        if key in self._cache:
            value, expires_at = self._cache[key]
            if datetime.utcnow() < expires_at:
                return value
            else:
                del self._cache[key]
        return None
    
    def set(self, key: str, value: str) -> None:
        expires_at = datetime.utcnow() + self._ttl
        self._cache[key] = (value, expires_at)
    
    def delete(self, key: str) -> None:
        self._cache.pop(key, None)
    
    def clear(self) -> None:
        self._cache.clear()


class SecretRotator:
    """
    Secret rotation manager.
    """
    
    def __init__(self, manager: "SecretsManager"):
        self._manager = manager
        self._generators: Dict[SecretType, Callable[[], str]] = {
            SecretType.PASSWORD: self._generate_password,
            SecretType.API_KEY: self._generate_api_key,
            SecretType.TOKEN: self._generate_token,
            SecretType.GENERIC: self._generate_generic,
        }
        self._running = False
    
    def register_generator(
        self,
        secret_type: SecretType,
        generator: Callable[[], str],
    ) -> None:
        """Register a custom secret generator."""
        self._generators[secret_type] = generator
    
    async def rotate(self, key: str) -> str:
        """Rotate a secret."""
        metadata = await self._manager.get_metadata(key)
        
        if not metadata:
            raise SecretNotFoundError(f"Secret not found: {key}")
        
        generator = self._generators.get(metadata.type, self._generate_generic)
        new_value = generator()
        
        await self._manager.set(key, new_value)
        metadata.last_rotated = datetime.utcnow()
        
        logger.info(f"Rotated secret: {key}")
        return new_value
    
    async def check_and_rotate(self) -> List[str]:
        """Check all secrets and rotate if needed."""
        rotated = []
        
        keys = await self._manager.list()
        
        for key in keys:
            metadata = await self._manager.get_metadata(key)
            
            if metadata and metadata.rotation_interval:
                last_rotated = metadata.last_rotated or metadata.created_at
                next_rotation = last_rotated + metadata.rotation_interval
                
                if datetime.utcnow() >= next_rotation:
                    await self.rotate(key)
                    rotated.append(key)
        
        return rotated
    
    def _generate_password(self) -> str:
        """Generate a random password."""
        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*"
        return ''.join(python_secrets.choice(alphabet) for _ in range(32))
    
    def _generate_api_key(self) -> str:
        """Generate a random API key."""
        return python_secrets.token_urlsafe(32)
    
    def _generate_token(self) -> str:
        """Generate a random token."""
        return python_secrets.token_hex(32)
    
    def _generate_generic(self) -> str:
        """Generate a random generic secret."""
        return python_secrets.token_urlsafe(24)


class SecretsManager:
    """
    Secrets manager with encryption, caching, and rotation.
    """
    
    def __init__(
        self,
        store: Optional[SecretStore] = None,
        encryptor: Optional[Encryptor] = None,
        config: Optional[SecretConfig] = None,
    ):
        self._store = store or InMemorySecretStore()
        self._encryptor = encryptor or NoopEncryptor()
        self._config = config or SecretConfig()
        self._cache = SecretCache(self._config.cache_ttl) if self._config.cache_enabled else None
        self._rotator = SecretRotator(self)
        self._access_policies: Dict[str, AccessPolicy] = {}
    
    @property
    def rotator(self) -> SecretRotator:
        return self._rotator
    
    async def get(
        self,
        key: str,
        default: Optional[str] = None,
    ) -> Optional[str]:
        """Get a secret value."""
        # Check cache first
        if self._cache:
            cached = self._cache.get(key)
            if cached is not None:
                return cached
        
        # Get from store
        encrypted = await self._store.get(key)
        
        if encrypted is None:
            return default
        
        # Decrypt
        value = self._encryptor.decrypt(encrypted)
        
        # Cache
        if self._cache:
            self._cache.set(key, value)
        
        return value
    
    async def set(
        self,
        key: str,
        value: str,
        secret_type: SecretType = SecretType.GENERIC,
        tags: Optional[Dict[str, str]] = None,
        rotation_interval: Optional[timedelta] = None,
    ) -> None:
        """Set a secret value."""
        # Encrypt
        encrypted = self._encryptor.encrypt(value)
        
        # Create metadata
        metadata = SecretMetadata(
            key=key,
            type=secret_type,
            tags=tags or {},
            rotation_interval=rotation_interval,
        )
        
        # Store
        await self._store.set(key, encrypted, metadata)
        
        # Update cache
        if self._cache:
            self._cache.set(key, value)
    
    async def delete(self, key: str) -> None:
        """Delete a secret."""
        await self._store.delete(key)
        
        if self._cache:
            self._cache.delete(key)
    
    async def list(self, prefix: str = "") -> List[str]:
        """List secret keys."""
        return await self._store.list(prefix)
    
    async def exists(self, key: str) -> bool:
        """Check if secret exists."""
        return await self._store.exists(key)
    
    async def get_metadata(self, key: str) -> Optional[SecretMetadata]:
        """Get secret metadata."""
        if isinstance(self._store, InMemorySecretStore):
            return await self._store.get_metadata(key)
        return None
    
    def add_policy(self, policy: AccessPolicy) -> None:
        """Add access policy."""
        self._access_policies[policy.name] = policy
    
    def check_access(self, key: str, action: str) -> bool:
        """Check if action is allowed on key."""
        for policy in self._access_policies.values():
            for path in policy.paths:
                if key.startswith(path) and action in policy.actions:
                    return True
        
        # Default allow if no policies
        return len(self._access_policies) == 0


# Global manager
_global_manager: Optional[SecretsManager] = None


# Decorators
def inject_secrets(mapping: Dict[str, str]) -> Callable:
    """
    Decorator to inject secrets as function arguments.
    
    Example:
        @inject_secrets({"password": "database/password"})
        async def connect(password: str):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            manager = get_global_manager()
            
            for arg_name, secret_key in mapping.items():
                if arg_name not in kwargs:
                    value = await manager.get(secret_key)
                    if value is not None:
                        kwargs[arg_name] = value
            
            return await func(*args, **kwargs)
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For sync functions, we need to run async in event loop
            async def get_secrets():
                manager = get_global_manager()
                for arg_name, secret_key in mapping.items():
                    if arg_name not in kwargs:
                        value = await manager.get(secret_key)
                        if value is not None:
                            kwargs[arg_name] = value
            
            asyncio.get_event_loop().run_until_complete(get_secrets())
            return func(*args, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


def require_secret(key: str, env_fallback: Optional[str] = None) -> Callable:
    """
    Decorator to require a secret to be set.
    
    Example:
        @require_secret("api/key", env_fallback="API_KEY")
        async def call_api():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            manager = get_global_manager()
            value = await manager.get(key)
            
            if value is None and env_fallback:
                value = os.environ.get(env_fallback)
            
            if value is None:
                raise SecretNotFoundError(f"Required secret not found: {key}")
            
            return await func(*args, **kwargs)
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            async def check():
                manager = get_global_manager()
                return await manager.get(key)
            
            value = asyncio.get_event_loop().run_until_complete(check())
            
            if value is None and env_fallback:
                value = os.environ.get(env_fallback)
            
            if value is None:
                raise SecretNotFoundError(f"Required secret not found: {key}")
            
            return func(*args, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


# Factory functions
def create_secrets_manager(
    store: Optional[SecretStore] = None,
    encryptor: Optional[Encryptor] = None,
    cache_enabled: bool = True,
) -> SecretsManager:
    """Create a secrets manager."""
    config = SecretConfig(cache_enabled=cache_enabled)
    return SecretsManager(store, encryptor, config)


def create_in_memory_store() -> InMemorySecretStore:
    """Create in-memory secret store."""
    return InMemorySecretStore()


def create_environment_store(prefix: str = "SECRET_") -> EnvironmentSecretStore:
    """Create environment secret store."""
    return EnvironmentSecretStore(prefix)


def create_file_store(
    directory: str,
    encryption_key: Optional[str] = None,
) -> FileSecretStore:
    """Create file secret store."""
    encryptor = FernetEncryptor(encryption_key) if encryption_key else None
    return FileSecretStore(directory, encryptor)


def create_fernet_encryptor(key: Optional[str] = None) -> FernetEncryptor:
    """Create Fernet encryptor."""
    return FernetEncryptor(key)


def create_access_policy(
    name: str,
    paths: List[str],
    actions: List[str] = None,
) -> AccessPolicy:
    """Create access policy."""
    return AccessPolicy(
        name=name,
        paths=paths,
        actions=actions or ["read"],
    )


def generate_encryption_key() -> str:
    """Generate a new encryption key."""
    return FernetEncryptor.generate_key()


def get_global_manager() -> SecretsManager:
    """Get global secrets manager."""
    global _global_manager
    if _global_manager is None:
        _global_manager = create_secrets_manager()
    return _global_manager


__all__ = [
    # Exceptions
    "SecretError",
    "SecretNotFoundError",
    "SecretAccessDeniedError",
    "EncryptionError",
    # Enums
    "SecretType",
    # Data classes
    "SecretMetadata",
    "SecretVersion",
    "SecretConfig",
    "AccessPolicy",
    # Encryptors
    "Encryptor",
    "FernetEncryptor",
    "Base64Encryptor",
    "NoopEncryptor",
    # Stores
    "SecretStore",
    "InMemorySecretStore",
    "EnvironmentSecretStore",
    "FileSecretStore",
    # Cache
    "SecretCache",
    # Rotator
    "SecretRotator",
    # Manager
    "SecretsManager",
    # Decorators
    "inject_secrets",
    "require_secret",
    # Factory functions
    "create_secrets_manager",
    "create_in_memory_store",
    "create_environment_store",
    "create_file_store",
    "create_fernet_encryptor",
    "create_access_policy",
    "generate_encryption_key",
    "get_global_manager",
]
