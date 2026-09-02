"""
Data Platform Connectors.

Connectors for:
- Snowflake (SQL REST API v2 — key-pair JWT or password auth)
- Databricks (SQL Statement Execution API 2.0)

Both are stdlib-only and share a small DB-API-ish surface: ``connect()``,
``query(sql) -> list[dict]`` and ``write(table, rows)``.
"""

import json
import logging
import time
from typing import Dict, Any, List, Optional, Sequence
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class DataPlatformConnector(ABC):
    """Base class for data platform connectors."""
    
    @abstractmethod
    def connect(self) -> bool:
        """Connect to data platform."""
    
    @abstractmethod
    def query(self, query: str) -> List[Dict[str, Any]]:
        """Execute query."""
    
    @abstractmethod
    def write(self, table: str, data: List[Dict[str, Any]]) -> bool:
        """Write data."""
    
    # -- shared helpers ------------------------------------------------------------
    
    @staticmethod
    def _quote_ident(name: str) -> str:
        parts = [p.strip('"`') for p in name.split('.')]
        return '.'.join('"' + p.replace('"', '""') + '"' for p in parts)
    
    @staticmethod
    def _sql_literal(value: Any) -> str:
        if value is None:
            return 'NULL'
        if isinstance(value, bool):
            return 'TRUE' if value else 'FALSE'
        if isinstance(value, (int, float)):
            return repr(value)
        if isinstance(value, (dict, list)):
            value = json.dumps(value, default=str)
        return "'" + str(value).replace("'", "''") + "'"
    
    def _insert_sql(self, table: str, rows: Sequence[Dict[str, Any]], batch: Sequence[Dict[str, Any]]) -> str:
        columns = list(dict.fromkeys(k for row in rows for k in row))
        cols_sql = ', '.join(self._quote_ident(c) for c in columns)
        values_sql = ', '.join(
            '(' + ', '.join(self._sql_literal(row.get(c)) for c in columns) + ')' for row in batch
        )
        return f"INSERT INTO {self._quote_ident(table)} ({cols_sql}) VALUES {values_sql}"


class SnowflakeConnector(DataPlatformConnector):
    """Snowflake connector over the SQL REST API.

    Supply ``private_key_pem`` for key-pair (JWT) auth — recommended — or
    ``password`` for legacy auth. Values are typed using ``resultSetMetaData``.
    """
    
    def __init__(self, account: str, user: str, password: Optional[str] = None,
                 warehouse: Optional[str] = None, database: Optional[str] = None, schema: str = 'PUBLIC',
                 private_key_pem: Optional[str] = None, role: Optional[str] = None,
                 timeout: float = 60.0, batch_size: int = 1000):
        self.config = {
            'account': account,
            'user': user,
            'warehouse': warehouse,
            'database': database,
            'schema': schema,
            'role': role,
        }
        self._password = password
        self._private_key_pem = private_key_pem
        self._timeout = timeout
        self._batch_size = batch_size
        self._client = None
        self._connected = False
    
    def connect(self) -> bool:
        """Authenticate and verify with ``SELECT CURRENT_VERSION()``."""
        from agenticaiframework._internal.clients.snowflake_rest import SnowflakeRESTClient
        
        self._client = SnowflakeRESTClient(
            account=self.config['account'], user=self.config['user'],
            private_key_pem=self._private_key_pem, password=self._password,
            warehouse=self.config['warehouse'], database=self.config['database'],
            schema=self.config['schema'], role=self.config['role'], timeout=self._timeout,
        )
        cols, rows = self._client.execute("SELECT CURRENT_VERSION() AS v, CURRENT_ACCOUNT() AS a")
        self.config['server_version'] = rows[0][0] if rows else None
        self._connected = True
        logger.info("Connected to Snowflake: %s (v%s)", self.config['account'], self.config.get('server_version'))
        return True
    
    def query(self, query: str, params: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
        """Execute a Snowflake query and return rows as dictionaries."""
        if not self._connected or self._client is None:
            raise RuntimeError("Not connected")
        logger.info("Executing Snowflake query: %s...", query[:50])
        columns, rows = self._client.execute(query, params)
        return [dict(zip(columns, row)) for row in rows]
    
    def execute(self, statement: str, params: Optional[List[Any]] = None) -> int:
        """Run a DML/DDL statement; returns affected row count when Snowflake reports it."""
        rows = self.query(statement, params)
        if rows and len(rows[0]) == 1:
            try:
                return int(next(iter(rows[0].values())))
            except (TypeError, ValueError):
                pass
        return len(rows)
    
    def write(self, table: str, data: List[Dict[str, Any]]) -> bool:
        """Insert rows into a Snowflake table in batches."""
        if not self._connected or self._client is None:
            raise RuntimeError("Not connected")
        if not data:
            return True
        logger.info("Writing %d rows to Snowflake table %s", len(data), table)
        for i in range(0, len(data), self._batch_size):
            self._client.execute(self._insert_sql(table, data, data[i:i + self._batch_size]))
        return True
    
    def close(self) -> None:
        self._connected = False
        self._client = None


class DatabricksConnector(DataPlatformConnector):
    """Databricks connector over the SQL Statement Execution API.

    ``cluster_id`` is the SQL warehouse id (``warehouse_id`` alias accepted).
    """
    
    def __init__(self, workspace_url: str, token: str, cluster_id: Optional[str] = None,
                 warehouse_id: Optional[str] = None, catalog: Optional[str] = None,
                 schema: Optional[str] = None, timeout: float = 120.0, batch_size: int = 500):
        self.config = {
            'workspace_url': workspace_url.rstrip('/'),
            'cluster_id': warehouse_id or cluster_id,
            'catalog': catalog,
            'schema': schema,
        }
        self._token = token
        self._timeout = timeout
        self._batch_size = batch_size
        self._http = None
        self._connected = False
    
    def _client(self):
        from agenticaiframework._internal.http import Client
        if self._http is None:
            self._http = Client(base_url=self.config['workspace_url'], timeout=self._timeout,
                                headers={'Authorization': f'Bearer {self._token}', 'Content-Type': 'application/json'})
        return self._http
    
    def _api(self, method: str, path: str, **kw) -> Dict[str, Any]:
        resp = self._client().request(method, path, **kw)
        if not resp.ok:
            raise RuntimeError(f"Databricks API {method} {path} failed: HTTP {resp.status} {resp.text[:300]}")
        return resp.json() if resp.content else {}
    
    def connect(self) -> bool:
        """Verify the token and resolve the SQL warehouse."""
        me = self._api('GET', '/api/2.0/preview/scim/v2/Me')
        self.config['user'] = me.get('userName')
        if not self.config['cluster_id']:
            warehouses = self._api('GET', '/api/2.0/sql/warehouses').get('warehouses', [])
            running = [w for w in warehouses if w.get('state') == 'RUNNING'] or warehouses
            if not running:
                raise RuntimeError("No SQL warehouses available; pass warehouse_id explicitly")
            self.config['cluster_id'] = running[0]['id']
        self._connected = True
        logger.info("Connected to Databricks: %s as %s", self.config['workspace_url'], self.config.get('user'))
        return True
    
    def _submit(self, statement: str, params: Optional[List[Any]] = None) -> Dict[str, Any]:
        body: Dict[str, Any] = {
            'statement': statement,
            'warehouse_id': self.config['cluster_id'],
            'wait_timeout': '30s',
            'on_wait_timeout': 'CONTINUE',
            'format': 'JSON_ARRAY',
            'disposition': 'INLINE',
        }
        if self.config.get('catalog'):
            body['catalog'] = self.config['catalog']
        if self.config.get('schema'):
            body['schema'] = self.config['schema']
        if params:
            body['parameters'] = [{'name': f'p{i + 1}', 'value': None if v is None else str(v)} for i, v in enumerate(params)]
        result = self._api('POST', '/api/2.0/sql/statements/', json=body)
        deadline = time.time() + self._timeout
        while result.get('status', {}).get('state') in ('PENDING', 'RUNNING') and time.time() < deadline:
            time.sleep(1.0)
            result = self._api('GET', f"/api/2.0/sql/statements/{result['statement_id']}")
        state = result.get('status', {}).get('state')
        if state != 'SUCCEEDED':
            err = result.get('status', {}).get('error', {})
            raise RuntimeError(f"Databricks statement {state}: {err.get('message', err)}")
        return result
    
    @staticmethod
    def _coerce(value: Any, type_name: str) -> Any:
        if value is None:
            return None
        t = (type_name or '').upper()
        try:
            if t in ('INT', 'BIGINT', 'SMALLINT', 'TINYINT', 'LONG'):
                return int(value)
            if t in ('FLOAT', 'DOUBLE', 'DECIMAL'):
                return float(value)
            if t == 'BOOLEAN':
                return str(value).lower() == 'true'
            if t in ('ARRAY', 'MAP', 'STRUCT'):
                return json.loads(value)
        except (TypeError, ValueError):
            return value
        return value
    
    def query(self, query: str, params: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
        """Execute Databricks SQL and return typed rows as dictionaries."""
        if not self._connected:
            raise RuntimeError("Not connected")
        logger.info("Executing Databricks query: %s...", query[:50])
        result = self._submit(query, params)
        columns = result.get('manifest', {}).get('schema', {}).get('columns', [])
        names = [c['name'] for c in columns]
        types = [c.get('type_name', '') for c in columns]
        rows: List[Dict[str, Any]] = []
        chunk = result.get('result', {})
        while True:
            for raw in chunk.get('data_array', []) or []:
                rows.append({n: self._coerce(v, t) for n, t, v in zip(names, types, raw)})
            next_link = chunk.get('next_chunk_internal_link')
            if not next_link:
                break
            chunk = self._api('GET', next_link)
        return rows
    
    def execute(self, statement: str, params: Optional[List[Any]] = None) -> int:
        rows = self.query(statement, params)
        if rows and 'num_affected_rows' in rows[0]:
            return int(rows[0]['num_affected_rows'] or 0)
        return len(rows)
    
    def write(self, table: str, data: List[Dict[str, Any]]) -> bool:
        """Insert rows into a Databricks table in batches."""
        if not self._connected:
            raise RuntimeError("Not connected")
        if not data:
            return True
        logger.info("Writing %d rows to Databricks table %s", len(data), table)
        for i in range(0, len(data), self._batch_size):
            self._submit(self._insert_sql(table, data, data[i:i + self._batch_size]).replace('"', '`'))
        return True
    
    def close(self) -> None:
        self._connected = False
        self._http = None


__all__ = ['DataPlatformConnector', 'SnowflakeConnector', 'DatabricksConnector']
