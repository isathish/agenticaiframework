"""
Enterprise Session Module.

Provides session management, user context tracking,
and session storage with TTL support.

Example:
    # Create session manager
    sessions = create_session_manager()
    
    # Create session
    session = await sessions.create(user_id="user123")
    
    # Store data in session
    session.set("cart", ["item1", "item2"])
    session.set("preferences", {"theme": "dark"})
    
    # Retrieve session
    session = await sessions.get(session_id)
    cart = session.get("cart", default=[])
    
    # With decorator
    @require_session
    async def checkout(session: Session):
        cart = session.get("cart")
        ...
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import secrets
import time
import uuid
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    TypeVar,
    Union,
)

logger = logging.getLogger(__name__)

T = TypeVar('T')


class SessionError(Exception):
    """Session error."""
    pass


class SessionNotFoundError(SessionError):
    """Session not found."""
    pass


class SessionExpiredError(SessionError):
    """Session expired."""
    pass


class SessionStatus(str, Enum):
    """Session status."""
    ACTIVE = "active"
    EXPIRED = "expired"
    INVALIDATED = "invalidated"


@dataclass
class SessionConfig:
    """Session configuration."""
    ttl_seconds: int = 3600  # 1 hour
    max_sessions_per_user: int = 5
    secure_tokens: bool = True
    token_length: int = 32
    auto_extend: bool = True
    extend_threshold: float = 0.5  # Extend when 50% of TTL remaining


@dataclass
class SessionData:
    """Session data container."""
    data: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    accessed_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "data": self.data,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "accessed_at": self.accessed_at.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SessionData':
        """Create from dictionary."""
        return cls(
            data=data.get("data", {}),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.now(),
            accessed_at=datetime.fromisoformat(data["accessed_at"]) if data.get("accessed_at") else datetime.now(),
        )


class Session:
    """
    User session with data storage.
    """
    
    def __init__(
        self,
        session_id: str,
        user_id: Optional[str] = None,
        config: Optional[SessionConfig] = None,
    ):
        self._id = session_id
        self._user_id = user_id
        self._config = config or SessionConfig()
        self._data = SessionData()
        self._status = SessionStatus.ACTIVE
        self._expires_at = datetime.now() + timedelta(seconds=self._config.ttl_seconds)
        self._modified = False
    
    @property
    def id(self) -> str:
        """Get session ID."""
        return self._id
    
    @property
    def user_id(self) -> Optional[str]:
        """Get user ID."""
        return self._user_id
    
    @property
    def status(self) -> SessionStatus:
        """Get session status."""
        if self._status == SessionStatus.ACTIVE and self.is_expired:
            self._status = SessionStatus.EXPIRED
        return self._status
    
    @property
    def is_expired(self) -> bool:
        """Check if session is expired."""
        return datetime.now() > self._expires_at
    
    @property
    def is_active(self) -> bool:
        """Check if session is active."""
        return self.status == SessionStatus.ACTIVE
    
    @property
    def expires_at(self) -> datetime:
        """Get expiration time."""
        return self._expires_at
    
    @property
    def created_at(self) -> datetime:
        """Get creation time."""
        return self._data.created_at
    
    @property
    def updated_at(self) -> datetime:
        """Get last update time."""
        return self._data.updated_at
    
    @property
    def is_modified(self) -> bool:
        """Check if session was modified."""
        return self._modified
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from the session."""
        self._touch()
        return self._data.data.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set a value in the session."""
        self._data.data[key] = value
        self._data.updated_at = datetime.now()
        self._modified = True
        self._touch()
    
    def delete(self, key: str) -> bool:
        """Delete a key from the session."""
        if key in self._data.data:
            del self._data.data[key]
            self._data.updated_at = datetime.now()
            self._modified = True
            return True
        return False
    
    def clear(self) -> None:
        """Clear all session data."""
        self._data.data.clear()
        self._data.updated_at = datetime.now()
        self._modified = True
    
    def has(self, key: str) -> bool:
        """Check if key exists."""
        return key in self._data.data
    
    def keys(self) -> List[str]:
        """Get all keys."""
        return list(self._data.data.keys())
    
    def items(self) -> List[tuple]:
        """Get all items."""
        return list(self._data.data.items())
    
    def extend(self, seconds: Optional[int] = None) -> None:
        """Extend session expiration."""
        ttl = seconds or self._config.ttl_seconds
        self._expires_at = datetime.now() + timedelta(seconds=ttl)
    
    def invalidate(self) -> None:
        """Invalidate the session."""
        self._status = SessionStatus.INVALIDATED
        self._data.data.clear()
    
    def _touch(self) -> None:
        """Update access time and auto-extend if needed."""
        self._data.accessed_at = datetime.now()
        
        if self._config.auto_extend:
            remaining = (self._expires_at - datetime.now()).total_seconds()
            threshold = self._config.ttl_seconds * self._config.extend_threshold
            
            if remaining < threshold:
                self.extend()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self._id,
            "user_id": self._user_id,
            "status": self._status.value,
            "expires_at": self._expires_at.isoformat(),
            "data": self._data.to_dict(),
        }
    
    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        config: Optional[SessionConfig] = None,
    ) -> 'Session':
        """Create from dictionary."""
        session = cls(
            session_id=data["id"],
            user_id=data.get("user_id"),
            config=config,
        )
        session._status = SessionStatus(data.get("status", "active"))
        session._expires_at = datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else datetime.now()
        session._data = SessionData.from_dict(data.get("data", {}))
        return session


class SessionStore(ABC):
    """Abstract session store."""
    
    @abstractmethod
    async def save(self, session: Session) -> None:
        """Save a session."""
        pass
    
    @abstractmethod
    async def load(self, session_id: str) -> Optional[Session]:
        """Load a session."""
        pass
    
    @abstractmethod
    async def delete(self, session_id: str) -> bool:
        """Delete a session."""
        pass
    
    @abstractmethod
    async def get_user_sessions(self, user_id: str) -> List[Session]:
        """Get all sessions for a user."""
        pass
    
    @abstractmethod
    async def cleanup_expired(self) -> int:
        """Clean up expired sessions."""
        pass


class InMemorySessionStore(SessionStore):
    """In-memory session store."""
    
    def __init__(self, config: Optional[SessionConfig] = None):
        self._sessions: Dict[str, Session] = {}
        self._user_sessions: Dict[str, List[str]] = {}
        self._config = config or SessionConfig()
    
    async def save(self, session: Session) -> None:
        """Save a session."""
        self._sessions[session.id] = session
        
        if session.user_id:
            if session.user_id not in self._user_sessions:
                self._user_sessions[session.user_id] = []
            
            if session.id not in self._user_sessions[session.user_id]:
                self._user_sessions[session.user_id].append(session.id)
    
    async def load(self, session_id: str) -> Optional[Session]:
        """Load a session."""
        session = self._sessions.get(session_id)
        
        if session and session.is_expired:
            await self.delete(session_id)
            return None
        
        return session
    
    async def delete(self, session_id: str) -> bool:
        """Delete a session."""
        session = self._sessions.pop(session_id, None)
        
        if session and session.user_id:
            user_sessions = self._user_sessions.get(session.user_id, [])
            if session_id in user_sessions:
                user_sessions.remove(session_id)
        
        return session is not None
    
    async def get_user_sessions(self, user_id: str) -> List[Session]:
        """Get all sessions for a user."""
        session_ids = self._user_sessions.get(user_id, [])
        sessions = []
        
        for session_id in session_ids:
            session = await self.load(session_id)
            if session:
                sessions.append(session)
        
        return sessions
    
    async def cleanup_expired(self) -> int:
        """Clean up expired sessions."""
        expired = [
            sid for sid, session in self._sessions.items()
            if session.is_expired
        ]
        
        for session_id in expired:
            await self.delete(session_id)
        
        return len(expired)


class SessionManager:
    """
    Manages user sessions with storage and lifecycle.
    """
    
    def __init__(
        self,
        store: Optional[SessionStore] = None,
        config: Optional[SessionConfig] = None,
    ):
        self._store = store or InMemorySessionStore()
        self._config = config or SessionConfig()
        self._cleanup_task: Optional[asyncio.Task] = None
    
    async def create(
        self,
        user_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Session:
        """Create a new session."""
        # Generate session ID
        if self._config.secure_tokens:
            session_id = secrets.token_urlsafe(self._config.token_length)
        else:
            session_id = str(uuid.uuid4())
        
        # Check max sessions per user
        if user_id:
            user_sessions = await self._store.get_user_sessions(user_id)
            
            if len(user_sessions) >= self._config.max_sessions_per_user:
                # Remove oldest session
                oldest = min(user_sessions, key=lambda s: s.created_at)
                await self._store.delete(oldest.id)
        
        # Create session
        session = Session(
            session_id=session_id,
            user_id=user_id,
            config=self._config,
        )
        
        # Set initial data
        if data:
            for key, value in data.items():
                session.set(key, value)
        
        # Save session
        await self._store.save(session)
        
        logger.debug(f"Created session: {session_id}")
        return session
    
    async def get(self, session_id: str) -> Optional[Session]:
        """Get a session by ID."""
        session = await self._store.load(session_id)
        
        if session and session.is_modified:
            await self._store.save(session)
        
        return session
    
    async def get_or_create(
        self,
        session_id: str,
        user_id: Optional[str] = None,
    ) -> Session:
        """Get existing session or create new one."""
        session = await self.get(session_id)
        
        if not session:
            session = await self.create(user_id=user_id)
        
        return session
    
    async def save(self, session: Session) -> None:
        """Save a session."""
        await self._store.save(session)
    
    async def destroy(self, session_id: str) -> bool:
        """Destroy a session."""
        session = await self._store.load(session_id)
        
        if session:
            session.invalidate()
            return await self._store.delete(session_id)
        
        return False
    
    async def destroy_user_sessions(self, user_id: str) -> int:
        """Destroy all sessions for a user."""
        sessions = await self._store.get_user_sessions(user_id)
        count = 0
        
        for session in sessions:
            if await self.destroy(session.id):
                count += 1
        
        return count
    
    async def refresh(self, session_id: str) -> Optional[Session]:
        """Refresh a session's expiration."""
        session = await self.get(session_id)
        
        if session:
            session.extend()
            await self._store.save(session)
        
        return session
    
    async def get_user_sessions(self, user_id: str) -> List[Session]:
        """Get all sessions for a user."""
        return await self._store.get_user_sessions(user_id)
    
    async def start_cleanup_task(self, interval: int = 300) -> None:
        """Start background cleanup task."""
        async def cleanup_loop():
            while True:
                try:
                    await asyncio.sleep(interval)
                    count = await self._store.cleanup_expired()
                    if count > 0:
                        logger.info(f"Cleaned up {count} expired sessions")
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Session cleanup error: {e}")
        
        self._cleanup_task = asyncio.create_task(cleanup_loop())
    
    async def stop_cleanup_task(self) -> None:
        """Stop background cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
    
    @asynccontextmanager
    async def session_context(
        self,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ):
        """Context manager for session access."""
        if session_id:
            session = await self.get(session_id)
            if not session:
                session = await self.create(user_id=user_id)
        else:
            session = await self.create(user_id=user_id)
        
        try:
            yield session
        finally:
            if session.is_modified:
                await self.save(session)


class SessionMiddleware:
    """
    Session middleware for request handling.
    """
    
    def __init__(
        self,
        manager: SessionManager,
        cookie_name: str = "session_id",
        header_name: str = "X-Session-ID",
    ):
        self._manager = manager
        self._cookie_name = cookie_name
        self._header_name = header_name
    
    def get_session_id(self, request: Dict[str, Any]) -> Optional[str]:
        """Extract session ID from request."""
        # Try header first
        headers = request.get("headers", {})
        session_id = headers.get(self._header_name)
        
        if not session_id:
            # Try cookies
            cookies = request.get("cookies", {})
            session_id = cookies.get(self._cookie_name)
        
        return session_id
    
    async def process(
        self,
        request: Dict[str, Any],
        handler: Callable[[Dict[str, Any], Session], Awaitable[Any]],
    ) -> Any:
        """Process request with session."""
        session_id = self.get_session_id(request)
        
        if session_id:
            session = await self._manager.get(session_id)
        else:
            session = await self._manager.create()
        
        if not session:
            session = await self._manager.create()
        
        try:
            result = await handler(request, session)
            
            if session.is_modified:
                await self._manager.save(session)
            
            return result
            
        except Exception as e:
            logger.error(f"Request handler error: {e}")
            raise


# Decorators
def require_session(
    manager: Optional[SessionManager] = None,
    session_param: str = "session",
) -> Callable:
    """
    Decorator to require a valid session.
    
    Example:
        @require_session(manager)
        async def protected_route(session: Session):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            session_id = kwargs.get("session_id")
            
            if not session_id:
                raise SessionError("Session ID required")
            
            mgr = manager
            if not mgr:
                raise SessionError("Session manager not configured")
            
            session = await mgr.get(session_id)
            
            if not session:
                raise SessionNotFoundError(f"Session not found: {session_id}")
            
            if not session.is_active:
                raise SessionExpiredError(f"Session expired: {session_id}")
            
            kwargs[session_param] = session
            
            result = await func(*args, **kwargs)
            
            if session.is_modified:
                await mgr.save(session)
            
            return result
        
        return wrapper
    
    return decorator


def session_data(*keys: str) -> Callable:
    """
    Decorator to inject session data into function.
    
    Example:
        @session_data("user", "preferences")
        async def handler(user: dict, preferences: dict):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, session: Session, **kwargs: Any) -> Any:
            for key in keys:
                if key not in kwargs:
                    kwargs[key] = session.get(key)
            
            return await func(*args, **kwargs)
        
        return wrapper
    
    return decorator


# Factory functions
def create_session_manager(
    store: Optional[SessionStore] = None,
    ttl_seconds: int = 3600,
    **config_kwargs: Any,
) -> SessionManager:
    """Create a session manager."""
    config = SessionConfig(ttl_seconds=ttl_seconds, **config_kwargs)
    return SessionManager(store, config)


def create_session_store(
    provider: str = "memory",
    **kwargs: Any,
) -> SessionStore:
    """Create a session store."""
    if provider == "memory":
        return InMemorySessionStore(**kwargs)
    else:
        raise ValueError(f"Unknown session store provider: {provider}")


def create_session_middleware(
    manager: SessionManager,
    **kwargs: Any,
) -> SessionMiddleware:
    """Create session middleware."""
    return SessionMiddleware(manager, **kwargs)


__all__ = [
    # Exceptions
    "SessionError",
    "SessionNotFoundError",
    "SessionExpiredError",
    # Enums
    "SessionStatus",
    # Data classes
    "SessionConfig",
    "SessionData",
    # Core classes
    "Session",
    "SessionStore",
    "InMemorySessionStore",
    "SessionManager",
    "SessionMiddleware",
    # Decorators
    "require_session",
    "session_data",
    # Factory
    "create_session_manager",
    "create_session_store",
    "create_session_middleware",
]
