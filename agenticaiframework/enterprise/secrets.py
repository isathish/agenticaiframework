"""
Enterprise Secrets Management - Secure secrets handling.

Provides secure storage, access, and rotation of secrets
with support for multiple backends including Azure Key Vault.

Features:
- Secure secret storage
- Secret rotation
- Access logging
- Multiple backends
- Encryption at rest
"""

import asyncio
import base64
import hashlib
import json
import logging
import os
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# =============================================================================
# Secret Types
# =============================================================================

class SecretType(Enum):
    """Types of secrets."""
    API_KEY = "api_key"
    CONNECTION_STRING = "connection_string"
    PASSWORD = "password"
    CERTIFICATE = "certificate"
    PRIVATE_KEY = "private_key"
    TOKEN = "token"
    GENERIC = "generic"


@dataclass
class Secret:
    """A secret value with metadata."""
    name: str
    value: str
    secret_type: SecretType = SecretType.GENERIC
    version: str = "1"
    expires_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at
    
    def mask(self) -> str:
        """Return masked version of secret."""
        if len(self.value) <= 4:
            return "****"
        return self.value[:2] + "*" * (len(self.value) - 4) + self.value[-2:]


@dataclass
class SecretAccessLog:
    """Log entry for secret access."""
    secret_name: str
    action: str  # get, set, delete, rotate
    accessor: str
    timestamp: datetime = field(default_factory=datetime.now)
    success: bool = True
    error: Optional[str] = None


# =============================================================================
# Secret Backend Interface
# =============================================================================

class SecretBackend(ABC):
    """Abstract interface for secret backends."""
    
    @abstractmethod
    async def get(self, name: str, version: Optional[str] = None) -> Optional[Secret]:
        """Get a secret by name."""
        pass
    
    @abstractmethod
    async def set(self, secret: Secret):
        """Store a secret."""
        pass
    
    @abstractmethod
    async def delete(self, name: str):
        """Delete a secret."""
        pass
    
    @abstractmethod
    async def list(self, prefix: Optional[str] = None) -> List[str]:
        """List secret names."""
        pass
    
    async def rotate(
        self,
        name: str,
        new_value: str,
    ) -> Secret:
        """Rotate a secret to a new value."""
        existing = await self.get(name)
        
        if existing:
            new_version = str(int(existing.version) + 1)
            secret = Secret(
                name=name,
                value=new_value,
                secret_type=existing.secret_type,
                version=new_version,
                tags=existing.tags,
                metadata=existing.metadata,
            )
        else:
            secret = Secret(name=name, value=new_value)
        
        await self.set(secret)
        return secret


# =============================================================================
# Environment Backend
# =============================================================================

class EnvironmentBackend(SecretBackend):
    """
    Secret backend using environment variables.
    
    Usage:
        >>> backend = EnvironmentBackend(prefix="APP_")
        >>> # Reads from APP_DATABASE_URL, etc.
    """
    
    def __init__(self, prefix: str = ""):
        self.prefix = prefix
        self._cache: Dict[str, Secret] = {}
    
    def _env_name(self, name: str) -> str:
        """Convert secret name to env var name."""
        return f"{self.prefix}{name.upper().replace('-', '_').replace('.', '_')}"
    
    async def get(self, name: str, version: Optional[str] = None) -> Optional[Secret]:
        env_name = self._env_name(name)
        value = os.environ.get(env_name)
        
        if value is None:
            return None
        
        return Secret(name=name, value=value)
    
    async def set(self, secret: Secret):
        env_name = self._env_name(secret.name)
        os.environ[env_name] = secret.value
        self._cache[secret.name] = secret
    
    async def delete(self, name: str):
        env_name = self._env_name(name)
        if env_name in os.environ:
            del os.environ[env_name]
        if name in self._cache:
            del self._cache[name]
    
    async def list(self, prefix: Optional[str] = None) -> List[str]:
        names = []
        full_prefix = self._env_name(prefix or "")
        
        for key in os.environ:
            if key.startswith(full_prefix):
                name = key[len(self.prefix):].lower().replace("_", "-")
                names.append(name)
        
        return names


# =============================================================================
# In-Memory Backend
# =============================================================================

class InMemoryBackend(SecretBackend):
    """
    In-memory secret backend with optional encryption.
    
    Usage:
        >>> backend = InMemoryBackend(encryption_key="my-key")
        >>> await backend.set(Secret("api-key", "sk-xxx"))
    """
    
    def __init__(self, encryption_key: Optional[str] = None):
        self._secrets: Dict[str, Dict[str, Secret]] = {}
        self._encryption_key = encryption_key
        self._lock = asyncio.Lock()
    
    def _encrypt(self, value: str) -> str:
        """Simple encryption (for demo - use proper encryption in prod)."""
        if not self._encryption_key:
            return value
        
        # XOR-based obfuscation (NOT secure - use cryptography library)
        key_bytes = self._encryption_key.encode()
        value_bytes = value.encode()
        
        encrypted = bytes(
            v ^ key_bytes[i % len(key_bytes)]
            for i, v in enumerate(value_bytes)
        )
        
        return base64.b64encode(encrypted).decode()
    
    def _decrypt(self, value: str) -> str:
        """Decrypt a value."""
        if not self._encryption_key:
            return value
        
        encrypted = base64.b64decode(value.encode())
        key_bytes = self._encryption_key.encode()
        
        decrypted = bytes(
            v ^ key_bytes[i % len(key_bytes)]
            for i, v in enumerate(encrypted)
        )
        
        return decrypted.decode()
    
    async def get(self, name: str, version: Optional[str] = None) -> Optional[Secret]:
        async with self._lock:
            versions = self._secrets.get(name, {})
            
            if not versions:
                return None
            
            if version:
                secret = versions.get(version)
            else:
                # Get latest version
                latest_version = max(versions.keys(), key=lambda v: int(v))
                secret = versions[latest_version]
            
            if secret:
                # Decrypt value
                decrypted = Secret(
                    name=secret.name,
                    value=self._decrypt(secret.value),
                    secret_type=secret.secret_type,
                    version=secret.version,
                    expires_at=secret.expires_at,
                    created_at=secret.created_at,
                    updated_at=secret.updated_at,
                    tags=secret.tags,
                    metadata=secret.metadata,
                )
                return decrypted
            
            return None
    
    async def set(self, secret: Secret):
        async with self._lock:
            if secret.name not in self._secrets:
                self._secrets[secret.name] = {}
            
            # Encrypt and store
            encrypted = Secret(
                name=secret.name,
                value=self._encrypt(secret.value),
                secret_type=secret.secret_type,
                version=secret.version,
                expires_at=secret.expires_at,
                created_at=secret.created_at,
                updated_at=datetime.now(),
                tags=secret.tags,
                metadata=secret.metadata,
            )
            
            self._secrets[secret.name][secret.version] = encrypted
    
    async def delete(self, name: str):
        async with self._lock:
            if name in self._secrets:
                del self._secrets[name]
    
    async def list(self, prefix: Optional[str] = None) -> List[str]:
        async with self._lock:
            names = list(self._secrets.keys())
            
            if prefix:
                names = [n for n in names if n.startswith(prefix)]
            
            return names


# =============================================================================
# Azure Key Vault Backend
# =============================================================================

class AzureKeyVaultBackend(SecretBackend):
    """
    Azure Key Vault secret backend.
    
    Usage:
        >>> backend = AzureKeyVaultBackend("https://myvault.vault.azure.net")
        >>> secret = await backend.get("database-connection")
    """
    
    def __init__(self, vault_url: str, credential = None):
        self.vault_url = vault_url
        self._client = None
        self._credential = credential
    
    async def _get_client(self):
        """Lazy initialization of Key Vault client."""
        if self._client is None:
            try:
                from azure.identity.aio import DefaultAzureCredential
                from azure.keyvault.secrets.aio import SecretClient
                
                credential = self._credential or DefaultAzureCredential()
                self._client = SecretClient(
                    vault_url=self.vault_url,
                    credential=credential,
                )
            except ImportError:
                raise ImportError(
                    "azure-identity and azure-keyvault-secrets required. "
                    "Install with: pip install azure-identity azure-keyvault-secrets"
                )
        
        return self._client
    
    async def get(self, name: str, version: Optional[str] = None) -> Optional[Secret]:
        client = await self._get_client()
        
        try:
            kv_secret = await client.get_secret(name, version=version)
            
            return Secret(
                name=kv_secret.name,
                value=kv_secret.value,
                version=kv_secret.properties.version,
                expires_at=kv_secret.properties.expires_on,
                created_at=kv_secret.properties.created_on,
                updated_at=kv_secret.properties.updated_on,
                tags=kv_secret.properties.tags or {},
            )
        except Exception as e:
            logger.error(f"Failed to get secret {name}: {e}")
            return None
    
    async def set(self, secret: Secret):
        client = await self._get_client()
        
        await client.set_secret(
            secret.name,
            secret.value,
            expires_on=secret.expires_at,
            tags=secret.tags,
        )
    
    async def delete(self, name: str):
        client = await self._get_client()
        
        await client.begin_delete_secret(name)
    
    async def list(self, prefix: Optional[str] = None) -> List[str]:
        client = await self._get_client()
        
        names = []
        async for secret in client.list_properties_of_secrets():
            if prefix is None or secret.name.startswith(prefix):
                names.append(secret.name)
        
        return names


# =============================================================================
# Secret Manager
# =============================================================================

class SecretManager:
    """
    High-level secret management with access logging.
    
    Usage:
        >>> manager = SecretManager()
        >>> 
        >>> # Get secrets
        >>> api_key = await manager.get("openai-api-key")
        >>> 
        >>> # Set secrets
        >>> await manager.set("database-url", "postgresql://...")
        >>> 
        >>> # Rotate secrets
        >>> await manager.rotate("api-key", new_key)
    """
    
    def __init__(
        self,
        backend: Optional[SecretBackend] = None,
        accessor: str = "system",
        enable_logging: bool = True,
        cache_ttl: int = 300,  # 5 minutes
    ):
        self.backend = backend or EnvironmentBackend()
        self.accessor = accessor
        self.enable_logging = enable_logging
        self.cache_ttl = cache_ttl
        
        self._cache: Dict[str, tuple] = {}  # name -> (secret, expires_at)
        self._access_log: List[SecretAccessLog] = []
        self._rotation_callbacks: Dict[str, List[Callable]] = {}
        self._lock = asyncio.Lock()
    
    async def get(
        self,
        name: str,
        version: Optional[str] = None,
        use_cache: bool = True,
    ) -> Optional[str]:
        """Get a secret value."""
        # Check cache
        if use_cache and name in self._cache:
            secret, expires_at = self._cache[name]
            if datetime.now() < expires_at:
                return secret.value
        
        # Get from backend
        try:
            secret = await self.backend.get(name, version)
            
            if secret:
                # Update cache
                if use_cache:
                    async with self._lock:
                        self._cache[name] = (
                            secret,
                            datetime.now() + timedelta(seconds=self.cache_ttl),
                        )
                
                self._log(name, "get", True)
                return secret.value
            else:
                self._log(name, "get", False, "Not found")
                return None
                
        except Exception as e:
            self._log(name, "get", False, str(e))
            raise
    
    async def get_secret(
        self,
        name: str,
        version: Optional[str] = None,
    ) -> Optional[Secret]:
        """Get full secret object."""
        return await self.backend.get(name, version)
    
    async def set(
        self,
        name: str,
        value: str,
        secret_type: SecretType = SecretType.GENERIC,
        expires_at: Optional[datetime] = None,
        tags: Dict[str, str] = None,
    ):
        """Set a secret."""
        secret = Secret(
            name=name,
            value=value,
            secret_type=secret_type,
            expires_at=expires_at,
            tags=tags or {},
        )
        
        try:
            await self.backend.set(secret)
            
            # Invalidate cache
            async with self._lock:
                if name in self._cache:
                    del self._cache[name]
            
            self._log(name, "set", True)
            
        except Exception as e:
            self._log(name, "set", False, str(e))
            raise
    
    async def delete(self, name: str):
        """Delete a secret."""
        try:
            await self.backend.delete(name)
            
            async with self._lock:
                if name in self._cache:
                    del self._cache[name]
            
            self._log(name, "delete", True)
            
        except Exception as e:
            self._log(name, "delete", False, str(e))
            raise
    
    async def rotate(
        self,
        name: str,
        new_value: str,
    ) -> Secret:
        """Rotate a secret and notify callbacks."""
        try:
            secret = await self.backend.rotate(name, new_value)
            
            # Invalidate cache
            async with self._lock:
                if name in self._cache:
                    del self._cache[name]
            
            # Notify callbacks
            await self._notify_rotation(name, secret)
            
            self._log(name, "rotate", True)
            return secret
            
        except Exception as e:
            self._log(name, "rotate", False, str(e))
            raise
    
    async def list(self, prefix: Optional[str] = None) -> List[str]:
        """List secret names."""
        return await self.backend.list(prefix)
    
    def on_rotation(self, name: str):
        """Decorator to register rotation callback."""
        def decorator(fn: Callable):
            if name not in self._rotation_callbacks:
                self._rotation_callbacks[name] = []
            self._rotation_callbacks[name].append(fn)
            return fn
        return decorator
    
    async def _notify_rotation(self, name: str, secret: Secret):
        """Notify rotation callbacks."""
        callbacks = self._rotation_callbacks.get(name, [])
        
        for callback in callbacks:
            try:
                result = callback(secret)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Rotation callback error: {e}")
    
    def _log(self, name: str, action: str, success: bool, error: str = None):
        """Log secret access."""
        if not self.enable_logging:
            return
        
        log_entry = SecretAccessLog(
            secret_name=name,
            action=action,
            accessor=self.accessor,
            success=success,
            error=error,
        )
        
        self._access_log.append(log_entry)
        
        # Trim log
        if len(self._access_log) > 10000:
            self._access_log = self._access_log[-5000:]
    
    def get_access_log(
        self,
        name: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 100,
    ) -> List[SecretAccessLog]:
        """Get access log entries."""
        entries = self._access_log
        
        if name:
            entries = [e for e in entries if e.secret_name == name]
        
        if action:
            entries = [e for e in entries if e.action == action]
        
        return entries[-limit:]
    
    def clear_cache(self):
        """Clear the secret cache."""
        self._cache.clear()


# =============================================================================
# Global Secret Manager
# =============================================================================

_global_manager: Optional[SecretManager] = None
_lock = threading.Lock()


def get_secret_manager() -> SecretManager:
    """Get the global secret manager."""
    global _global_manager
    
    if _global_manager is None:
        with _lock:
            if _global_manager is None:
                _global_manager = SecretManager()
    
    return _global_manager


def set_secret_manager(manager: SecretManager):
    """Set the global secret manager."""
    global _global_manager
    _global_manager = manager


# Convenience functions
async def get_secret(name: str) -> Optional[str]:
    """Get a secret from the global manager."""
    return await get_secret_manager().get(name)


async def set_secret(name: str, value: str, **kwargs):
    """Set a secret in the global manager."""
    await get_secret_manager().set(name, value, **kwargs)


async def rotate_secret(name: str, new_value: str) -> Secret:
    """Rotate a secret in the global manager."""
    return await get_secret_manager().rotate(name, new_value)


# =============================================================================
# Secret Helpers
# =============================================================================

def secret_from_env(
    name: str,
    env_var: Optional[str] = None,
    default: Optional[str] = None,
) -> Optional[str]:
    """
    Get secret from environment variable.
    
    Usage:
        >>> api_key = secret_from_env("openai-api-key", "OPENAI_API_KEY")
    """
    env_name = env_var or name.upper().replace("-", "_")
    return os.environ.get(env_name, default)


def mask_secret(value: str, visible_chars: int = 4) -> str:
    """Mask a secret value for logging."""
    if len(value) <= visible_chars:
        return "*" * len(value)
    
    half = visible_chars // 2
    return value[:half] + "*" * (len(value) - visible_chars) + value[-half:]


def generate_secret(length: int = 32) -> str:
    """Generate a random secret."""
    import secrets
    return secrets.token_urlsafe(length)
