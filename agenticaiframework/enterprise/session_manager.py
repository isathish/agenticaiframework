"""
Enterprise Session Manager Module.

User session handling, token management,
authentication sessions, and security.

Example:
    # Create session manager
    sessions = create_session_manager()
    
    # Create session
    session = await sessions.create(
        user_id="user_123",
        data={"role": "admin"},
        ttl=3600,
    )
    
    # Validate session
    valid = await sessions.validate(session.token)
    
    # Get session data
    session = await sessions.get(session.id)
    
    # Refresh session
    session = await sessions.refresh(session.token)
    
    # Revoke session
    await sessions.revoke(session.id)
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import secrets
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    TypeVar,
    Union,
)

T = TypeVar('T')

logger = logging.getLogger(__name__)


class SessionError(Exception):
    """Session error."""
    pass


class SessionNotFoundError(SessionError):
    """Session not found."""
    pass


class SessionExpiredError(SessionError):
    """Session expired."""
    pass


class InvalidTokenError(SessionError):
    """Invalid token."""
    pass


class SessionStatus(str, Enum):
    """Session status."""
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    LOCKED = "locked"


class TokenType(str, Enum):
    """Token type."""
    ACCESS = "access"
    REFRESH = "refresh"
    API_KEY = "api_key"
    TEMPORARY = "temporary"


@dataclass
class DeviceInfo:
    """Device information."""
    id: str = ""
    type: str = ""  # web, mobile, desktop
    name: str = ""
    os: str = ""
    browser: str = ""
    ip_address: str = ""
    user_agent: str = ""


@dataclass
class GeoLocation:
    """Geolocation."""
    country: str = ""
    region: str = ""
    city: str = ""
    latitude: float = 0.0
    longitude: float = 0.0


@dataclass
class Session:
    """User session."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    token: str = ""
    refresh_token: str = ""
    token_type: TokenType = TokenType.ACCESS
    status: SessionStatus = SessionStatus.ACTIVE
    data: Dict[str, Any] = field(default_factory=dict)
    device: Optional[DeviceInfo] = None
    location: Optional[GeoLocation] = None
    expires_at: Optional[datetime] = None
    last_accessed_at: datetime = field(default_factory=datetime.utcnow)
    created_at: datetime = field(default_factory=datetime.utcnow)
    revoked_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_expired(self) -> bool:
        """Check if expired."""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at
    
    @property
    def is_active(self) -> bool:
        """Check if active."""
        return self.status == SessionStatus.ACTIVE and not self.is_expired
    
    @property
    def time_remaining(self) -> timedelta:
        """Time remaining."""
        if not self.expires_at:
            return timedelta(days=365)
        return max(timedelta(0), self.expires_at - datetime.utcnow())


@dataclass
class TokenPair:
    """Token pair."""
    access_token: str = ""
    refresh_token: str = ""
    token_type: str = "Bearer"
    expires_in: int = 3600
    scope: str = ""


@dataclass
class SessionConfig:
    """Session configuration."""
    access_token_ttl: int = 3600  # 1 hour
    refresh_token_ttl: int = 604800  # 7 days
    max_sessions_per_user: int = 10
    sliding_expiration: bool = True
    rotate_refresh_token: bool = True
    token_length: int = 32
    secret_key: str = ""
    algorithm: str = "HS256"


@dataclass
class SessionStats:
    """Session statistics."""
    total_sessions: int = 0
    active_sessions: int = 0
    expired_sessions: int = 0
    revoked_sessions: int = 0
    by_user: Dict[str, int] = field(default_factory=dict)
    by_device: Dict[str, int] = field(default_factory=dict)


# Token generator
class TokenGenerator(ABC):
    """Token generator."""
    
    @abstractmethod
    def generate(self, length: int = 32) -> str:
        """Generate token."""
        pass
    
    @abstractmethod
    def hash(self, token: str) -> str:
        """Hash token."""
        pass
    
    @abstractmethod
    def verify(self, token: str, hashed: str) -> bool:
        """Verify token."""
        pass


class SecureTokenGenerator(TokenGenerator):
    """Secure token generator."""
    
    def __init__(self, secret_key: str = ""):
        self._secret = secret_key or secrets.token_hex(32)
    
    def generate(self, length: int = 32) -> str:
        return secrets.token_urlsafe(length)
    
    def hash(self, token: str) -> str:
        return hmac.new(
            self._secret.encode(),
            token.encode(),
            hashlib.sha256,
        ).hexdigest()
    
    def verify(self, token: str, hashed: str) -> bool:
        return hmac.compare_digest(self.hash(token), hashed)


# Session store
class SessionStore(ABC):
    """Session storage."""
    
    @abstractmethod
    async def save(self, session: Session) -> None:
        """Save session."""
        pass
    
    @abstractmethod
    async def get(self, session_id: str) -> Optional[Session]:
        """Get session."""
        pass
    
    @abstractmethod
    async def get_by_token(self, token: str) -> Optional[Session]:
        """Get by token."""
        pass
    
    @abstractmethod
    async def get_by_user(self, user_id: str) -> List[Session]:
        """Get user sessions."""
        pass
    
    @abstractmethod
    async def delete(self, session_id: str) -> bool:
        """Delete session."""
        pass
    
    @abstractmethod
    async def delete_by_user(self, user_id: str) -> int:
        """Delete user sessions."""
        pass


class InMemorySessionStore(SessionStore):
    """In-memory session store."""
    
    def __init__(self):
        self._sessions: Dict[str, Session] = {}
        self._by_token: Dict[str, str] = {}  # token -> session_id
        self._by_user: Dict[str, Set[str]] = {}  # user_id -> session_ids
    
    async def save(self, session: Session) -> None:
        self._sessions[session.id] = session
        self._by_token[session.token] = session.id
        if session.refresh_token:
            self._by_token[session.refresh_token] = session.id
        
        if session.user_id not in self._by_user:
            self._by_user[session.user_id] = set()
        self._by_user[session.user_id].add(session.id)
    
    async def get(self, session_id: str) -> Optional[Session]:
        return self._sessions.get(session_id)
    
    async def get_by_token(self, token: str) -> Optional[Session]:
        session_id = self._by_token.get(token)
        if session_id:
            return self._sessions.get(session_id)
        return None
    
    async def get_by_user(self, user_id: str) -> List[Session]:
        session_ids = self._by_user.get(user_id, set())
        return [
            self._sessions[sid]
            for sid in session_ids
            if sid in self._sessions
        ]
    
    async def delete(self, session_id: str) -> bool:
        session = self._sessions.pop(session_id, None)
        if session:
            self._by_token.pop(session.token, None)
            if session.refresh_token:
                self._by_token.pop(session.refresh_token, None)
            if session.user_id in self._by_user:
                self._by_user[session.user_id].discard(session_id)
            return True
        return False
    
    async def delete_by_user(self, user_id: str) -> int:
        session_ids = self._by_user.pop(user_id, set())
        count = 0
        for sid in session_ids:
            session = self._sessions.pop(sid, None)
            if session:
                self._by_token.pop(session.token, None)
                if session.refresh_token:
                    self._by_token.pop(session.refresh_token, None)
                count += 1
        return count


# Session manager
class SessionManager:
    """Session management service."""
    
    def __init__(
        self,
        store: Optional[SessionStore] = None,
        token_generator: Optional[TokenGenerator] = None,
        config: Optional[SessionConfig] = None,
    ):
        self._store = store or InMemorySessionStore()
        self._tokens = token_generator or SecureTokenGenerator()
        self._config = config or SessionConfig()
        self._stats = SessionStats()
        self._hooks: Dict[str, List[Callable]] = {}
    
    async def create(
        self,
        user_id: str,
        data: Optional[Dict[str, Any]] = None,
        ttl: Optional[int] = None,
        device: Optional[DeviceInfo] = None,
        location: Optional[GeoLocation] = None,
        **kwargs,
    ) -> Session:
        """Create session."""
        # Check max sessions
        existing = await self._store.get_by_user(user_id)
        active = [s for s in existing if s.is_active]
        
        if len(active) >= self._config.max_sessions_per_user:
            # Revoke oldest
            oldest = min(active, key=lambda s: s.created_at)
            await self.revoke(oldest.id)
        
        access_ttl = ttl or self._config.access_token_ttl
        
        session = Session(
            user_id=user_id,
            token=self._tokens.generate(self._config.token_length),
            refresh_token=self._tokens.generate(self._config.token_length),
            data=data or {},
            device=device,
            location=location,
            expires_at=datetime.utcnow() + timedelta(seconds=access_ttl),
            **kwargs,
        )
        
        await self._store.save(session)
        
        # Update stats
        self._stats.total_sessions += 1
        self._stats.active_sessions += 1
        self._stats.by_user[user_id] = self._stats.by_user.get(user_id, 0) + 1
        
        if device:
            self._stats.by_device[device.type] = (
                self._stats.by_device.get(device.type, 0) + 1
            )
        
        await self._fire_hook("session.created", session)
        
        logger.info(f"Session created: {session.id} (user: {user_id})")
        
        return session
    
    async def get(self, session_id: str) -> Optional[Session]:
        """Get session."""
        session = await self._store.get(session_id)
        
        if session and self._config.sliding_expiration:
            session.last_accessed_at = datetime.utcnow()
            await self._store.save(session)
        
        return session
    
    async def get_by_token(self, token: str) -> Optional[Session]:
        """Get session by token."""
        session = await self._store.get_by_token(token)
        
        if session and self._config.sliding_expiration:
            session.last_accessed_at = datetime.utcnow()
            await self._store.save(session)
        
        return session
    
    async def get_user_sessions(self, user_id: str) -> List[Session]:
        """Get user sessions."""
        return await self._store.get_by_user(user_id)
    
    async def validate(self, token: str) -> bool:
        """Validate token."""
        session = await self._store.get_by_token(token)
        
        if not session:
            return False
        
        if session.is_expired:
            session.status = SessionStatus.EXPIRED
            await self._store.save(session)
            return False
        
        if session.status != SessionStatus.ACTIVE:
            return False
        
        # Update last accessed
        session.last_accessed_at = datetime.utcnow()
        await self._store.save(session)
        
        return True
    
    async def refresh(
        self,
        refresh_token: str,
    ) -> Optional[TokenPair]:
        """Refresh session tokens."""
        session = await self._store.get_by_token(refresh_token)
        
        if not session:
            raise InvalidTokenError("Invalid refresh token")
        
        if session.token_type == TokenType.REFRESH and session.is_expired:
            raise SessionExpiredError("Refresh token expired")
        
        # Generate new tokens
        new_access = self._tokens.generate(self._config.token_length)
        new_refresh = (
            self._tokens.generate(self._config.token_length)
            if self._config.rotate_refresh_token
            else session.refresh_token
        )
        
        # Update session
        session.token = new_access
        session.refresh_token = new_refresh
        session.expires_at = datetime.utcnow() + timedelta(
            seconds=self._config.access_token_ttl
        )
        session.last_accessed_at = datetime.utcnow()
        
        await self._store.save(session)
        
        await self._fire_hook("session.refreshed", session)
        
        return TokenPair(
            access_token=new_access,
            refresh_token=new_refresh,
            expires_in=self._config.access_token_ttl,
        )
    
    async def update_data(
        self,
        session_id: str,
        data: Dict[str, Any],
        merge: bool = True,
    ) -> Optional[Session]:
        """Update session data."""
        session = await self._store.get(session_id)
        if not session:
            return None
        
        if merge:
            session.data.update(data)
        else:
            session.data = data
        
        session.last_accessed_at = datetime.utcnow()
        await self._store.save(session)
        
        return session
    
    async def revoke(
        self,
        session_id: str,
        reason: str = "",
    ) -> bool:
        """Revoke session."""
        session = await self._store.get(session_id)
        if not session:
            return False
        
        session.status = SessionStatus.REVOKED
        session.revoked_at = datetime.utcnow()
        
        await self._store.save(session)
        
        # Update stats
        self._stats.active_sessions -= 1
        self._stats.revoked_sessions += 1
        
        await self._fire_hook("session.revoked", session)
        
        logger.info(f"Session revoked: {session_id}")
        
        return True
    
    async def revoke_all(
        self,
        user_id: str,
        except_current: Optional[str] = None,
    ) -> int:
        """Revoke all user sessions."""
        sessions = await self._store.get_by_user(user_id)
        count = 0
        
        for session in sessions:
            if except_current and session.id == except_current:
                continue
            if await self.revoke(session.id):
                count += 1
        
        return count
    
    async def delete(self, session_id: str) -> bool:
        """Delete session."""
        return await self._store.delete(session_id)
    
    async def cleanup_expired(self) -> int:
        """Cleanup expired sessions."""
        count = 0
        # In a real implementation, iterate all sessions
        # This is simplified for the in-memory store
        return count
    
    # Token pair generation
    def generate_token_pair(
        self,
        user_id: str,
        scope: str = "",
    ) -> TokenPair:
        """Generate token pair."""
        return TokenPair(
            access_token=self._tokens.generate(self._config.token_length),
            refresh_token=self._tokens.generate(self._config.token_length),
            expires_in=self._config.access_token_ttl,
            scope=scope,
        )
    
    # API key management
    async def create_api_key(
        self,
        user_id: str,
        name: str = "",
        scopes: Optional[List[str]] = None,
        expires_at: Optional[datetime] = None,
        **kwargs,
    ) -> Session:
        """Create API key."""
        session = Session(
            user_id=user_id,
            token=f"sk_{self._tokens.generate(40)}",
            token_type=TokenType.API_KEY,
            data={
                "name": name,
                "scopes": scopes or [],
            },
            expires_at=expires_at,
            **kwargs,
        )
        
        await self._store.save(session)
        
        logger.info(f"API key created: {name} (user: {user_id})")
        
        return session
    
    async def validate_api_key(self, api_key: str) -> Optional[Session]:
        """Validate API key."""
        if not api_key.startswith("sk_"):
            return None
        
        session = await self._store.get_by_token(api_key)
        
        if not session or session.token_type != TokenType.API_KEY:
            return None
        
        if session.is_expired or session.status != SessionStatus.ACTIVE:
            return None
        
        session.last_accessed_at = datetime.utcnow()
        await self._store.save(session)
        
        return session
    
    # Stats
    def get_stats(self) -> SessionStats:
        """Get statistics."""
        return self._stats
    
    # Hooks
    def on(self, event: str, handler: Callable) -> None:
        """Register event handler."""
        if event not in self._hooks:
            self._hooks[event] = []
        self._hooks[event].append(handler)
    
    async def _fire_hook(self, event: str, data: Any) -> None:
        """Fire event hooks."""
        for handler in self._hooks.get(event, []):
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(data)
                else:
                    handler(data)
            except Exception as e:
                logger.error(f"Hook error for {event}: {e}")


# Factory functions
def create_session_manager(
    config: Optional[SessionConfig] = None,
    store: Optional[SessionStore] = None,
) -> SessionManager:
    """Create session manager."""
    return SessionManager(
        config=config,
        store=store,
    )


def create_session_config(
    access_token_ttl: int = 3600,
    refresh_token_ttl: int = 604800,
    max_sessions_per_user: int = 10,
    **kwargs,
) -> SessionConfig:
    """Create session config."""
    return SessionConfig(
        access_token_ttl=access_token_ttl,
        refresh_token_ttl=refresh_token_ttl,
        max_sessions_per_user=max_sessions_per_user,
        **kwargs,
    )


def create_device_info(
    type: str = "",
    name: str = "",
    os: str = "",
    browser: str = "",
    ip_address: str = "",
    **kwargs,
) -> DeviceInfo:
    """Create device info."""
    return DeviceInfo(
        type=type,
        name=name,
        os=os,
        browser=browser,
        ip_address=ip_address,
        **kwargs,
    )


__all__ = [
    # Exceptions
    "SessionError",
    "SessionNotFoundError",
    "SessionExpiredError",
    "InvalidTokenError",
    # Enums
    "SessionStatus",
    "TokenType",
    # Data classes
    "DeviceInfo",
    "GeoLocation",
    "Session",
    "TokenPair",
    "SessionConfig",
    "SessionStats",
    # Token generator
    "TokenGenerator",
    "SecureTokenGenerator",
    # Stores
    "SessionStore",
    "InMemorySessionStore",
    # Manager
    "SessionManager",
    # Factory functions
    "create_session_manager",
    "create_session_config",
    "create_device_info",
]
