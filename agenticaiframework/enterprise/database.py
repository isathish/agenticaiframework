"""
Enterprise Database Module.

Provides database connection pooling, query builders,
repository patterns, and migration utilities for agents.

Example:
    # Create connection pool
    pool = ConnectionPool(url="postgresql://...")
    
    # Query builder
    query = (
        QueryBuilder("users")
        .select("id", "name", "email")
        .where("active", True)
        .order_by("created_at", "desc")
        .limit(10)
    )
    
    # Repository pattern
    @repository(pool)
    class UserRepository:
        async def find_by_email(self, email: str) -> User:
            ...
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import (
    Any,
    AsyncIterator,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
)
from datetime import datetime
from functools import wraps
from enum import Enum
import logging
import time

logger = logging.getLogger(__name__)

T = TypeVar('T')
ModelT = TypeVar('ModelT')


class DatabaseError(Exception):
    """Database operation error."""
    pass


class ConnectionError(DatabaseError):
    """Connection error."""
    pass


class QueryError(DatabaseError):
    """Query execution error."""
    pass


class TransactionError(DatabaseError):
    """Transaction error."""
    pass


class DatabaseType(str, Enum):
    """Supported database types."""
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    SQLITE = "sqlite"
    MONGODB = "mongodb"
    REDIS = "redis"


class Operator(str, Enum):
    """SQL operators."""
    EQ = "="
    NE = "!="
    LT = "<"
    LE = "<="
    GT = ">"
    GE = ">="
    LIKE = "LIKE"
    ILIKE = "ILIKE"
    IN = "IN"
    NOT_IN = "NOT IN"
    IS_NULL = "IS NULL"
    IS_NOT_NULL = "IS NOT NULL"
    BETWEEN = "BETWEEN"


class JoinType(str, Enum):
    """Join types."""
    INNER = "INNER JOIN"
    LEFT = "LEFT JOIN"
    RIGHT = "RIGHT JOIN"
    OUTER = "FULL OUTER JOIN"


@dataclass
class ConnectionConfig:
    """Database connection configuration."""
    url: str
    pool_size: int = 10
    max_overflow: int = 5
    pool_timeout: float = 30.0
    pool_recycle: int = 3600
    echo: bool = False
    ssl: bool = False
    
    @property
    def database_type(self) -> DatabaseType:
        """Detect database type from URL."""
        url = self.url.lower()
        if url.startswith("postgresql") or url.startswith("postgres"):
            return DatabaseType.POSTGRESQL
        elif url.startswith("mysql"):
            return DatabaseType.MYSQL
        elif url.startswith("sqlite"):
            return DatabaseType.SQLITE
        elif url.startswith("mongodb"):
            return DatabaseType.MONGODB
        elif url.startswith("redis"):
            return DatabaseType.REDIS
        raise ValueError(f"Unknown database type: {self.url}")


@dataclass
class QueryResult:
    """Query result wrapper."""
    rows: List[Dict[str, Any]]
    row_count: int
    columns: List[str] = field(default_factory=list)
    duration_ms: float = 0.0
    
    @property
    def first(self) -> Optional[Dict[str, Any]]:
        """Get first row."""
        return self.rows[0] if self.rows else None
    
    @property
    def scalar(self) -> Any:
        """Get first value of first row."""
        if self.rows and self.columns:
            return self.rows[0].get(self.columns[0])
        return None
    
    def __iter__(self):
        return iter(self.rows)
    
    def __len__(self):
        return len(self.rows)


class Connection(ABC):
    """Abstract database connection."""
    
    @abstractmethod
    async def execute(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> QueryResult:
        """Execute a query."""
        pass
    
    @abstractmethod
    async def fetch_one(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Fetch one row."""
        pass
    
    @abstractmethod
    async def fetch_all(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch all rows."""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Close the connection."""
        pass


class InMemoryConnection(Connection):
    """In-memory mock connection for testing."""
    
    def __init__(self):
        self._tables: Dict[str, List[Dict[str, Any]]] = {}
        self._closed = False
    
    async def execute(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> QueryResult:
        """Execute a query (mock)."""
        start = time.time()
        
        # Simple parsing for basic operations
        query_lower = query.lower().strip()
        
        if query_lower.startswith("insert"):
            # Mock insert
            return QueryResult(
                rows=[],
                row_count=1,
                duration_ms=(time.time() - start) * 1000,
            )
        
        if query_lower.startswith("update"):
            return QueryResult(
                rows=[],
                row_count=1,
                duration_ms=(time.time() - start) * 1000,
            )
        
        if query_lower.startswith("delete"):
            return QueryResult(
                rows=[],
                row_count=1,
                duration_ms=(time.time() - start) * 1000,
            )
        
        return QueryResult(
            rows=[],
            row_count=0,
            duration_ms=(time.time() - start) * 1000,
        )
    
    async def fetch_one(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Fetch one row (mock)."""
        return None
    
    async def fetch_all(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch all rows (mock)."""
        return []
    
    async def close(self) -> None:
        """Close the connection."""
        self._closed = True
    
    def add_table(self, name: str, rows: List[Dict[str, Any]]) -> None:
        """Add a mock table."""
        self._tables[name] = rows


class ConnectionPool(ABC):
    """Abstract connection pool."""
    
    @abstractmethod
    async def acquire(self) -> Connection:
        """Acquire a connection."""
        pass
    
    @abstractmethod
    async def release(self, conn: Connection) -> None:
        """Release a connection."""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Close the pool."""
        pass
    
    @asynccontextmanager
    async def connection(self) -> AsyncIterator[Connection]:
        """Context manager for connection."""
        conn = await self.acquire()
        try:
            yield conn
        finally:
            await self.release(conn)


class SimpleConnectionPool(ConnectionPool):
    """Simple in-memory connection pool."""
    
    def __init__(
        self,
        config: Optional[ConnectionConfig] = None,
        connection_factory: Optional[Callable[[], Connection]] = None,
    ):
        self._config = config
        self._factory = connection_factory or (lambda: InMemoryConnection())
        self._pool: asyncio.Queue = asyncio.Queue()
        self._connections: List[Connection] = []
        self._initialized = False
        self._size = config.pool_size if config else 5
    
    async def _initialize(self) -> None:
        """Initialize the pool."""
        if self._initialized:
            return
        
        for _ in range(self._size):
            conn = self._factory()
            self._connections.append(conn)
            await self._pool.put(conn)
        
        self._initialized = True
    
    async def acquire(self) -> Connection:
        """Acquire a connection."""
        if not self._initialized:
            await self._initialize()
        
        try:
            timeout = self._config.pool_timeout if self._config else 30.0
            return await asyncio.wait_for(self._pool.get(), timeout=timeout)
        except asyncio.TimeoutError:
            raise ConnectionError("Connection pool timeout")
    
    async def release(self, conn: Connection) -> None:
        """Release a connection."""
        await self._pool.put(conn)
    
    async def close(self) -> None:
        """Close all connections."""
        for conn in self._connections:
            await conn.close()
        self._connections.clear()
        self._initialized = False


class QueryBuilder:
    """
    SQL query builder with fluent interface.
    """
    
    def __init__(self, table: str):
        self._table = table
        self._select_cols: List[str] = ["*"]
        self._where_clauses: List[Tuple[str, Operator, Any]] = []
        self._order_by_cols: List[Tuple[str, str]] = []
        self._group_by_cols: List[str] = []
        self._having_clauses: List[str] = []
        self._joins: List[Tuple[JoinType, str, str]] = []
        self._limit_val: Optional[int] = None
        self._offset_val: Optional[int] = None
        self._params: Dict[str, Any] = {}
        self._param_counter = 0
    
    def select(self, *columns: str) -> 'QueryBuilder':
        """Set columns to select."""
        self._select_cols = list(columns) if columns else ["*"]
        return self
    
    def where(
        self,
        column: str,
        value: Any,
        operator: Operator = Operator.EQ,
    ) -> 'QueryBuilder':
        """Add a WHERE clause."""
        self._where_clauses.append((column, operator, value))
        return self
    
    def where_null(self, column: str) -> 'QueryBuilder':
        """Add IS NULL condition."""
        return self.where(column, None, Operator.IS_NULL)
    
    def where_not_null(self, column: str) -> 'QueryBuilder':
        """Add IS NOT NULL condition."""
        return self.where(column, None, Operator.IS_NOT_NULL)
    
    def where_in(self, column: str, values: List[Any]) -> 'QueryBuilder':
        """Add IN condition."""
        return self.where(column, values, Operator.IN)
    
    def where_like(self, column: str, pattern: str) -> 'QueryBuilder':
        """Add LIKE condition."""
        return self.where(column, pattern, Operator.LIKE)
    
    def order_by(
        self,
        column: str,
        direction: str = "asc",
    ) -> 'QueryBuilder':
        """Add ORDER BY clause."""
        self._order_by_cols.append((column, direction.upper()))
        return self
    
    def group_by(self, *columns: str) -> 'QueryBuilder':
        """Add GROUP BY clause."""
        self._group_by_cols.extend(columns)
        return self
    
    def having(self, condition: str) -> 'QueryBuilder':
        """Add HAVING clause."""
        self._having_clauses.append(condition)
        return self
    
    def join(
        self,
        table: str,
        condition: str,
        join_type: JoinType = JoinType.INNER,
    ) -> 'QueryBuilder':
        """Add a JOIN clause."""
        self._joins.append((join_type, table, condition))
        return self
    
    def left_join(self, table: str, condition: str) -> 'QueryBuilder':
        """Add LEFT JOIN."""
        return self.join(table, condition, JoinType.LEFT)
    
    def limit(self, count: int) -> 'QueryBuilder':
        """Set LIMIT."""
        self._limit_val = count
        return self
    
    def offset(self, count: int) -> 'QueryBuilder':
        """Set OFFSET."""
        self._offset_val = count
        return self
    
    def _next_param(self) -> str:
        """Get next parameter name."""
        self._param_counter += 1
        return f"p{self._param_counter}"
    
    def build(self) -> Tuple[str, Dict[str, Any]]:
        """Build the SQL query."""
        parts = []
        
        # SELECT
        parts.append(f"SELECT {', '.join(self._select_cols)}")
        
        # FROM
        parts.append(f"FROM {self._table}")
        
        # JOINS
        for join_type, table, condition in self._joins:
            parts.append(f"{join_type.value} {table} ON {condition}")
        
        # WHERE
        if self._where_clauses:
            where_parts = []
            for column, operator, value in self._where_clauses:
                if operator in (Operator.IS_NULL, Operator.IS_NOT_NULL):
                    where_parts.append(f"{column} {operator.value}")
                elif operator == Operator.IN:
                    param = self._next_param()
                    self._params[param] = value
                    placeholders = ", ".join(f":{param}_{i}" for i in range(len(value)))
                    for i, v in enumerate(value):
                        self._params[f"{param}_{i}"] = v
                    where_parts.append(f"{column} IN ({placeholders})")
                else:
                    param = self._next_param()
                    self._params[param] = value
                    where_parts.append(f"{column} {operator.value} :{param}")
            
            parts.append(f"WHERE {' AND '.join(where_parts)}")
        
        # GROUP BY
        if self._group_by_cols:
            parts.append(f"GROUP BY {', '.join(self._group_by_cols)}")
        
        # HAVING
        if self._having_clauses:
            parts.append(f"HAVING {' AND '.join(self._having_clauses)}")
        
        # ORDER BY
        if self._order_by_cols:
            order_parts = [f"{col} {dir}" for col, dir in self._order_by_cols]
            parts.append(f"ORDER BY {', '.join(order_parts)}")
        
        # LIMIT/OFFSET
        if self._limit_val is not None:
            parts.append(f"LIMIT {self._limit_val}")
        
        if self._offset_val is not None:
            parts.append(f"OFFSET {self._offset_val}")
        
        return " ".join(parts), self._params
    
    def __str__(self) -> str:
        query, _ = self.build()
        return query


class InsertBuilder:
    """INSERT query builder."""
    
    def __init__(self, table: str):
        self._table = table
        self._columns: List[str] = []
        self._values: List[Dict[str, Any]] = []
        self._returning: List[str] = []
    
    def columns(self, *cols: str) -> 'InsertBuilder':
        """Set columns."""
        self._columns = list(cols)
        return self
    
    def values(self, **kwargs: Any) -> 'InsertBuilder':
        """Add a row of values."""
        self._values.append(kwargs)
        if not self._columns:
            self._columns = list(kwargs.keys())
        return self
    
    def returning(self, *cols: str) -> 'InsertBuilder':
        """Add RETURNING clause."""
        self._returning = list(cols)
        return self
    
    def build(self) -> Tuple[str, Dict[str, Any]]:
        """Build INSERT query."""
        if not self._values:
            raise QueryError("No values to insert")
        
        params = {}
        value_groups = []
        
        for i, row in enumerate(self._values):
            placeholders = []
            for col in self._columns:
                param_name = f"v{i}_{col}"
                params[param_name] = row.get(col)
                placeholders.append(f":{param_name}")
            value_groups.append(f"({', '.join(placeholders)})")
        
        query = f"INSERT INTO {self._table} ({', '.join(self._columns)}) VALUES {', '.join(value_groups)}"
        
        if self._returning:
            query += f" RETURNING {', '.join(self._returning)}"
        
        return query, params


class UpdateBuilder:
    """UPDATE query builder."""
    
    def __init__(self, table: str):
        self._table = table
        self._sets: Dict[str, Any] = {}
        self._where_clauses: List[Tuple[str, Operator, Any]] = []
        self._returning: List[str] = []
    
    def set(self, **kwargs: Any) -> 'UpdateBuilder':
        """Set column values."""
        self._sets.update(kwargs)
        return self
    
    def where(
        self,
        column: str,
        value: Any,
        operator: Operator = Operator.EQ,
    ) -> 'UpdateBuilder':
        """Add WHERE clause."""
        self._where_clauses.append((column, operator, value))
        return self
    
    def returning(self, *cols: str) -> 'UpdateBuilder':
        """Add RETURNING clause."""
        self._returning = list(cols)
        return self
    
    def build(self) -> Tuple[str, Dict[str, Any]]:
        """Build UPDATE query."""
        if not self._sets:
            raise QueryError("No values to update")
        
        params = {}
        set_parts = []
        
        for col, value in self._sets.items():
            param_name = f"set_{col}"
            params[param_name] = value
            set_parts.append(f"{col} = :{param_name}")
        
        query = f"UPDATE {self._table} SET {', '.join(set_parts)}"
        
        if self._where_clauses:
            where_parts = []
            for i, (col, op, val) in enumerate(self._where_clauses):
                param_name = f"where_{i}"
                params[param_name] = val
                where_parts.append(f"{col} {op.value} :{param_name}")
            query += f" WHERE {' AND '.join(where_parts)}"
        
        if self._returning:
            query += f" RETURNING {', '.join(self._returning)}"
        
        return query, params


class Repository(Generic[ModelT], ABC):
    """Abstract repository base class."""
    
    def __init__(self, pool: ConnectionPool, table: str):
        self._pool = pool
        self._table = table
    
    @abstractmethod
    async def find_by_id(self, id: Any) -> Optional[ModelT]:
        """Find by ID."""
        pass
    
    @abstractmethod
    async def find_all(self) -> List[ModelT]:
        """Find all records."""
        pass
    
    @abstractmethod
    async def save(self, entity: ModelT) -> ModelT:
        """Save an entity."""
        pass
    
    @abstractmethod
    async def delete(self, id: Any) -> bool:
        """Delete by ID."""
        pass


class GenericRepository(Repository[Dict[str, Any]]):
    """Generic dictionary-based repository."""
    
    def __init__(
        self,
        pool: ConnectionPool,
        table: str,
        id_column: str = "id",
    ):
        super().__init__(pool, table)
        self._id_column = id_column
    
    async def find_by_id(self, id: Any) -> Optional[Dict[str, Any]]:
        """Find by ID."""
        query, params = (
            QueryBuilder(self._table)
            .where(self._id_column, id)
            .limit(1)
            .build()
        )
        
        async with self._pool.connection() as conn:
            return await conn.fetch_one(query, params)
    
    async def find_all(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Find all records."""
        builder = QueryBuilder(self._table)
        
        if limit:
            builder.limit(limit)
        if offset:
            builder.offset(offset)
        
        query, params = builder.build()
        
        async with self._pool.connection() as conn:
            return await conn.fetch_all(query, params)
    
    async def find_by(self, **criteria: Any) -> List[Dict[str, Any]]:
        """Find by criteria."""
        builder = QueryBuilder(self._table)
        
        for column, value in criteria.items():
            builder.where(column, value)
        
        query, params = builder.build()
        
        async with self._pool.connection() as conn:
            return await conn.fetch_all(query, params)
    
    async def save(self, entity: Dict[str, Any]) -> Dict[str, Any]:
        """Save an entity."""
        id_value = entity.get(self._id_column)
        
        if id_value:
            # Update
            builder = UpdateBuilder(self._table)
            for key, value in entity.items():
                if key != self._id_column:
                    builder.set(**{key: value})
            builder.where(self._id_column, id_value)
            query, params = builder.build()
        else:
            # Insert
            builder = InsertBuilder(self._table)
            builder.values(**entity)
            builder.returning(self._id_column)
            query, params = builder.build()
        
        async with self._pool.connection() as conn:
            result = await conn.execute(query, params)
            return entity
    
    async def delete(self, id: Any) -> bool:
        """Delete by ID."""
        query = f"DELETE FROM {self._table} WHERE {self._id_column} = :id"
        
        async with self._pool.connection() as conn:
            result = await conn.execute(query, {"id": id})
            return result.row_count > 0


# Decorators
def repository(
    pool: ConnectionPool,
    table: Optional[str] = None,
) -> Callable:
    """
    Decorator to create a repository class.
    
    Example:
        @repository(pool, table="users")
        class UserRepository(GenericRepository):
            ...
    """
    def decorator(cls: Type) -> Type:
        original_init = cls.__init__
        
        def new_init(self, *args: Any, **kwargs: Any):
            tbl = table or cls.__name__.lower().replace("repository", "") + "s"
            GenericRepository.__init__(self, pool, tbl)
            if original_init != object.__init__:
                original_init(self, *args, **kwargs)
        
        cls.__init__ = new_init
        return cls
    
    return decorator


def transactional(pool: ConnectionPool) -> Callable:
    """
    Decorator for transactional operations.
    
    Example:
        @transactional(pool)
        async def transfer_funds(...):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            async with pool.connection() as conn:
                try:
                    await conn.execute("BEGIN")
                    result = await func(*args, conn=conn, **kwargs)
                    await conn.execute("COMMIT")
                    return result
                except Exception as e:
                    await conn.execute("ROLLBACK")
                    raise TransactionError(f"Transaction failed: {e}") from e
        
        return wrapper
    
    return decorator


# Factory functions
def create_pool(
    url: str,
    pool_size: int = 10,
    **kwargs: Any,
) -> ConnectionPool:
    """
    Factory function to create a connection pool.
    """
    config = ConnectionConfig(url=url, pool_size=pool_size, **kwargs)
    return SimpleConnectionPool(config)


def query(table: str) -> QueryBuilder:
    """Start a SELECT query."""
    return QueryBuilder(table)


def insert(table: str) -> InsertBuilder:
    """Start an INSERT query."""
    return InsertBuilder(table)


def update(table: str) -> UpdateBuilder:
    """Start an UPDATE query."""
    return UpdateBuilder(table)


__all__ = [
    # Exceptions
    "DatabaseError",
    "ConnectionError",
    "QueryError",
    "TransactionError",
    # Enums
    "DatabaseType",
    "Operator",
    "JoinType",
    # Data classes
    "ConnectionConfig",
    "QueryResult",
    # Connection
    "Connection",
    "InMemoryConnection",
    # Pool
    "ConnectionPool",
    "SimpleConnectionPool",
    # Query builders
    "QueryBuilder",
    "InsertBuilder",
    "UpdateBuilder",
    # Repository
    "Repository",
    "GenericRepository",
    # Decorators
    "repository",
    "transactional",
    # Factory
    "create_pool",
    "query",
    "insert",
    "update",
]
