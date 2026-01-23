"""
Enterprise Connection Pool Module.

Provides connection pooling, resource management,
health checks, and auto-scaling for database connections.

Example:
    # Create connection pool
    pool = create_connection_pool(
        factory=create_db_connection,
        min_size=5,
        max_size=20,
    )
    
    # Get connection
    async with pool.acquire() as conn:
        result = await conn.execute("SELECT * FROM users")
    
    # Use decorator
    @with_connection()
    async def query_users(conn):
        ...
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from abc import ABC, abstractmethod
from collections import deque
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    AsyncIterator,
    Callable,
    Deque,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    TypeVar,
)

T = TypeVar('T')


logger = logging.getLogger(__name__)


class PoolError(Exception):
    """Base pool error."""
    pass


class PoolExhaustedError(PoolError):
    """Pool is exhausted."""
    pass


class PoolClosedError(PoolError):
    """Pool is closed."""
    pass


class ConnectionError(PoolError):
    """Connection error."""
    pass


class PoolState(str, Enum):
    """Pool state."""
    CREATED = "created"
    RUNNING = "running"
    DRAINING = "draining"
    CLOSED = "closed"


class ConnectionState(str, Enum):
    """Connection state."""
    IDLE = "idle"
    IN_USE = "in_use"
    INVALID = "invalid"
    CLOSED = "closed"


@dataclass
class PoolConfig:
    """Pool configuration."""
    min_size: int = 1
    max_size: int = 10
    max_idle_time: float = 300.0  # seconds
    max_lifetime: float = 3600.0  # seconds
    acquire_timeout: float = 30.0  # seconds
    validation_interval: float = 60.0  # seconds
    health_check_interval: float = 30.0  # seconds


@dataclass
class ConnectionInfo:
    """Connection information."""
    id: str
    state: ConnectionState
    created_at: datetime
    last_used_at: datetime
    use_count: int = 0
    errors: int = 0
    
    @property
    def idle_time(self) -> float:
        return (datetime.utcnow() - self.last_used_at).total_seconds()
    
    @property
    def lifetime(self) -> float:
        return (datetime.utcnow() - self.created_at).total_seconds()


@dataclass
class PoolStats:
    """Pool statistics."""
    total_connections: int = 0
    idle_connections: int = 0
    in_use_connections: int = 0
    total_acquired: int = 0
    total_released: int = 0
    total_created: int = 0
    total_destroyed: int = 0
    acquire_wait_time: float = 0.0
    timeouts: int = 0
    errors: int = 0


class PooledConnection(Generic[T]):
    """
    Wrapper for pooled connection.
    """
    
    def __init__(
        self,
        connection: T,
        info: ConnectionInfo,
        pool: "ConnectionPool[T]",
    ):
        self._connection = connection
        self._info = info
        self._pool = pool
        self._released = False
    
    @property
    def connection(self) -> T:
        return self._connection
    
    @property
    def info(self) -> ConnectionInfo:
        return self._info
    
    @property
    def is_valid(self) -> bool:
        return (
            self._info.state != ConnectionState.INVALID
            and not self._released
        )
    
    async def release(self) -> None:
        """Release connection back to pool."""
        if not self._released:
            self._released = True
            await self._pool._release(self)
    
    def mark_invalid(self) -> None:
        """Mark connection as invalid."""
        self._info.state = ConnectionState.INVALID
    
    def __getattr__(self, name: str) -> Any:
        return getattr(self._connection, name)
    
    async def __aenter__(self) -> T:
        return self._connection
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type:
            self.mark_invalid()
        await self.release()


class ConnectionPool(ABC, Generic[T]):
    """
    Abstract connection pool.
    """
    
    @abstractmethod
    async def acquire(self, timeout: Optional[float] = None) -> PooledConnection[T]:
        """Acquire a connection from the pool."""
        pass
    
    @abstractmethod
    async def release(self, connection: PooledConnection[T]) -> None:
        """Release a connection back to the pool."""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Close the pool and all connections."""
        pass
    
    @abstractmethod
    async def stats(self) -> PoolStats:
        """Get pool statistics."""
        pass
    
    @asynccontextmanager
    async def connection(self) -> AsyncIterator[T]:
        """Context manager for acquiring connection."""
        conn = await self.acquire()
        try:
            yield conn.connection
        finally:
            await conn.release()


class SimpleConnectionPool(ConnectionPool[T]):
    """
    Simple in-memory connection pool.
    """
    
    def __init__(
        self,
        factory: Callable[[], T],
        config: Optional[PoolConfig] = None,
        validator: Optional[Callable[[T], bool]] = None,
    ):
        self._factory = factory
        self._config = config or PoolConfig()
        self._validator = validator
        
        self._state = PoolState.CREATED
        self._idle: Deque[PooledConnection[T]] = deque()
        self._in_use: Dict[str, PooledConnection[T]] = {}
        self._total_created = 0
        self._stats = PoolStats()
        
        self._lock = asyncio.Lock()
        self._condition = asyncio.Condition(self._lock)
        
        self._health_task: Optional[asyncio.Task] = None
    
    async def start(self) -> None:
        """Start the pool and create initial connections."""
        async with self._lock:
            if self._state != PoolState.CREATED:
                return
            
            # Create minimum connections
            for _ in range(self._config.min_size):
                conn = await self._create_connection()
                if conn:
                    self._idle.append(conn)
            
            self._state = PoolState.RUNNING
            
            # Start health check task
            self._health_task = asyncio.create_task(self._health_check_loop())
    
    async def acquire(self, timeout: Optional[float] = None) -> PooledConnection[T]:
        if self._state != PoolState.RUNNING:
            raise PoolClosedError("Pool is not running")
        
        timeout = timeout or self._config.acquire_timeout
        start_time = time.time()
        
        async with self._condition:
            while True:
                # Try to get idle connection
                while self._idle:
                    conn = self._idle.popleft()
                    
                    # Validate connection
                    if await self._validate_connection(conn):
                        conn._info.state = ConnectionState.IN_USE
                        conn._info.last_used_at = datetime.utcnow()
                        conn._info.use_count += 1
                        conn._released = False
                        
                        self._in_use[conn._info.id] = conn
                        self._stats.total_acquired += 1
                        self._stats.idle_connections -= 1
                        self._stats.in_use_connections += 1
                        
                        return conn
                    else:
                        await self._destroy_connection(conn)
                
                # Create new connection if possible
                total = len(self._idle) + len(self._in_use)
                if total < self._config.max_size:
                    conn = await self._create_connection()
                    if conn:
                        conn._info.state = ConnectionState.IN_USE
                        self._in_use[conn._info.id] = conn
                        self._stats.total_acquired += 1
                        self._stats.in_use_connections += 1
                        return conn
                
                # Wait for connection to become available
                elapsed = time.time() - start_time
                remaining = timeout - elapsed
                
                if remaining <= 0:
                    self._stats.timeouts += 1
                    raise PoolExhaustedError("Connection pool exhausted")
                
                try:
                    await asyncio.wait_for(
                        self._condition.wait(),
                        timeout=remaining,
                    )
                except asyncio.TimeoutError:
                    self._stats.timeouts += 1
                    raise PoolExhaustedError("Connection pool exhausted")
        
        self._stats.acquire_wait_time += time.time() - start_time
    
    async def _release(self, connection: PooledConnection[T]) -> None:
        """Internal release method."""
        async with self._condition:
            conn_id = connection._info.id
            
            if conn_id in self._in_use:
                del self._in_use[conn_id]
                self._stats.in_use_connections -= 1
            
            if connection.is_valid and await self._validate_connection(connection):
                connection._info.state = ConnectionState.IDLE
                connection._info.last_used_at = datetime.utcnow()
                self._idle.append(connection)
                self._stats.idle_connections += 1
            else:
                await self._destroy_connection(connection)
            
            self._stats.total_released += 1
            self._condition.notify()
    
    async def release(self, connection: PooledConnection[T]) -> None:
        await self._release(connection)
    
    async def close(self) -> None:
        """Close the pool."""
        async with self._lock:
            self._state = PoolState.DRAINING
            
            # Cancel health check
            if self._health_task:
                self._health_task.cancel()
                try:
                    await self._health_task
                except asyncio.CancelledError:
                    pass
            
            # Destroy all idle connections
            while self._idle:
                conn = self._idle.popleft()
                await self._destroy_connection(conn)
            
            # Destroy in-use connections
            for conn in list(self._in_use.values()):
                await self._destroy_connection(conn)
            self._in_use.clear()
            
            self._state = PoolState.CLOSED
    
    async def stats(self) -> PoolStats:
        return PoolStats(
            total_connections=len(self._idle) + len(self._in_use),
            idle_connections=len(self._idle),
            in_use_connections=len(self._in_use),
            total_acquired=self._stats.total_acquired,
            total_released=self._stats.total_released,
            total_created=self._stats.total_created,
            total_destroyed=self._stats.total_destroyed,
            acquire_wait_time=self._stats.acquire_wait_time,
            timeouts=self._stats.timeouts,
            errors=self._stats.errors,
        )
    
    async def _create_connection(self) -> Optional[PooledConnection[T]]:
        """Create a new connection."""
        try:
            if asyncio.iscoroutinefunction(self._factory):
                raw_conn = await self._factory()
            else:
                raw_conn = self._factory()
            
            info = ConnectionInfo(
                id=str(uuid.uuid4()),
                state=ConnectionState.IDLE,
                created_at=datetime.utcnow(),
                last_used_at=datetime.utcnow(),
            )
            
            conn = PooledConnection(raw_conn, info, self)
            self._total_created += 1
            self._stats.total_created += 1
            self._stats.total_connections += 1
            
            return conn
            
        except Exception as e:
            logger.error(f"Failed to create connection: {e}")
            self._stats.errors += 1
            return None
    
    async def _destroy_connection(self, connection: PooledConnection[T]) -> None:
        """Destroy a connection."""
        try:
            raw_conn = connection._connection
            
            if hasattr(raw_conn, 'close'):
                if asyncio.iscoroutinefunction(raw_conn.close):
                    await raw_conn.close()
                else:
                    raw_conn.close()
            
            connection._info.state = ConnectionState.CLOSED
            self._stats.total_destroyed += 1
            
        except Exception as e:
            logger.error(f"Error destroying connection: {e}")
    
    async def _validate_connection(self, connection: PooledConnection[T]) -> bool:
        """Validate a connection."""
        # Check state
        if connection._info.state == ConnectionState.INVALID:
            return False
        
        # Check lifetime
        if connection._info.lifetime > self._config.max_lifetime:
            return False
        
        # Custom validator
        if self._validator:
            try:
                if asyncio.iscoroutinefunction(self._validator):
                    return await self._validator(connection._connection)
                return self._validator(connection._connection)
            except Exception:
                return False
        
        return True
    
    async def _health_check_loop(self) -> None:
        """Background health check loop."""
        while self._state == PoolState.RUNNING:
            try:
                await asyncio.sleep(self._config.health_check_interval)
                await self._perform_health_check()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")
    
    async def _perform_health_check(self) -> None:
        """Perform health check on idle connections."""
        async with self._lock:
            to_remove = []
            
            for conn in self._idle:
                # Check idle time
                if conn._info.idle_time > self._config.max_idle_time:
                    to_remove.append(conn)
                    continue
                
                # Check lifetime
                if conn._info.lifetime > self._config.max_lifetime:
                    to_remove.append(conn)
                    continue
            
            # Remove expired connections
            for conn in to_remove:
                self._idle.remove(conn)
                self._stats.idle_connections -= 1
                await self._destroy_connection(conn)
            
            # Maintain minimum connections
            current = len(self._idle) + len(self._in_use)
            while current < self._config.min_size:
                conn = await self._create_connection()
                if conn:
                    self._idle.append(conn)
                    self._stats.idle_connections += 1
                    current += 1
                else:
                    break


class ConnectionPoolRegistry:
    """
    Registry for connection pools.
    """
    
    def __init__(self):
        self._pools: Dict[str, ConnectionPool] = {}
        self._default: Optional[str] = None
    
    def register(
        self,
        name: str,
        pool: ConnectionPool,
        default: bool = False,
    ) -> None:
        """Register a pool."""
        self._pools[name] = pool
        if default or self._default is None:
            self._default = name
    
    def get(self, name: Optional[str] = None) -> ConnectionPool:
        """Get a pool."""
        name = name or self._default
        if not name or name not in self._pools:
            raise PoolError(f"Pool not found: {name}")
        return self._pools[name]
    
    async def close_all(self) -> None:
        """Close all pools."""
        for pool in self._pools.values():
            await pool.close()
        self._pools.clear()


# Global registry
_global_registry = ConnectionPoolRegistry()


# Decorators
def with_connection(pool_name: Optional[str] = None) -> Callable:
    """
    Decorator to inject connection.
    
    Example:
        @with_connection()
        async def query_data(conn, user_id: str):
            ...
    """
    def decorator(func: Callable) -> Callable:
        async def wrapper(*args, **kwargs):
            pool = get_connection_pool(pool_name)
            async with pool.connection() as conn:
                if asyncio.iscoroutinefunction(func):
                    return await func(conn, *args, **kwargs)
                return func(conn, *args, **kwargs)
        return wrapper
    return decorator


def pooled(factory: Callable, **pool_kwargs) -> Callable:
    """
    Decorator to create pooled resource.
    
    Example:
        @pooled(create_db_connection, max_size=10)
        async def get_connection():
            ...
    """
    pool = None
    
    def decorator(func: Callable) -> Callable:
        nonlocal pool
        pool = SimpleConnectionPool(factory, PoolConfig(**pool_kwargs))
        
        async def wrapper(*args, **kwargs):
            if pool._state == PoolState.CREATED:
                await pool.start()
            return await pool.acquire()
        
        wrapper._pool = pool
        return wrapper
    
    return decorator


# Factory functions
def create_connection_pool(
    factory: Callable[[], T],
    min_size: int = 1,
    max_size: int = 10,
    max_idle_time: float = 300.0,
    max_lifetime: float = 3600.0,
    acquire_timeout: float = 30.0,
    validator: Optional[Callable[[T], bool]] = None,
) -> SimpleConnectionPool[T]:
    """Create a connection pool."""
    config = PoolConfig(
        min_size=min_size,
        max_size=max_size,
        max_idle_time=max_idle_time,
        max_lifetime=max_lifetime,
        acquire_timeout=acquire_timeout,
    )
    return SimpleConnectionPool(factory, config, validator)


def create_pool_config(
    min_size: int = 1,
    max_size: int = 10,
    max_idle_time: float = 300.0,
    max_lifetime: float = 3600.0,
    acquire_timeout: float = 30.0,
) -> PoolConfig:
    """Create a pool configuration."""
    return PoolConfig(
        min_size=min_size,
        max_size=max_size,
        max_idle_time=max_idle_time,
        max_lifetime=max_lifetime,
        acquire_timeout=acquire_timeout,
    )


def register_connection_pool(
    name: str,
    pool: ConnectionPool,
    default: bool = False,
) -> None:
    """Register pool in global registry."""
    _global_registry.register(name, pool, default)


def get_connection_pool(name: Optional[str] = None) -> ConnectionPool:
    """Get pool from global registry."""
    return _global_registry.get(name)


__all__ = [
    # Exceptions
    "PoolError",
    "PoolExhaustedError",
    "PoolClosedError",
    "ConnectionError",
    # Enums
    "PoolState",
    "ConnectionState",
    # Data classes
    "PoolConfig",
    "ConnectionInfo",
    "PoolStats",
    # Connection
    "PooledConnection",
    # Pool
    "ConnectionPool",
    "SimpleConnectionPool",
    # Registry
    "ConnectionPoolRegistry",
    # Decorators
    "with_connection",
    "pooled",
    # Factory functions
    "create_connection_pool",
    "create_pool_config",
    "register_connection_pool",
    "get_connection_pool",
]
