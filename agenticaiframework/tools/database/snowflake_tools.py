"""
Snowflake and SingleStore Database Tools.
"""

import logging
from typing import Any, Dict, List, Optional

from ..base import BaseTool, ToolConfig

logger = logging.getLogger(__name__)


class SnowflakeSearchTool(BaseTool):
    """
    Tool for searching data in Snowflake.
    
    Features:
    - Semantic search
    - Full-text search
    - Schema exploration
    """
    
    def __init__(
        self,
        config: Optional[ToolConfig] = None,
        account: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        warehouse: str = 'COMPUTE_WH',
        database: Optional[str] = None,
        schema: str = 'PUBLIC',
    ):
        super().__init__(config or ToolConfig(
            name="SnowflakeSearchTool",
            description="Search data in Snowflake"
        ))
        self.account = account or self.config.extra_config.get('account')
        self.user = user or self.config.extra_config.get('user')
        self.password = password or self.config.api_key
        self.warehouse = warehouse
        self.database = database
        self.schema = schema
        self._connection = None
    
    def _get_connection(self):
        """Get Snowflake connection."""
        if self._connection:
            return self._connection
        
        try:
            import snowflake.connector
        except ImportError:
            raise ImportError("Snowflake requires: pip install snowflake-connector-python")
        
        if not all([self.account, self.user, self.password]):
            raise ValueError("Snowflake credentials required")
        
        self._connection = snowflake.connector.connect(
            account=self.account,
            user=self.user,
            password=self.password,
            warehouse=self.warehouse,
            database=self.database,
            schema=self.schema,
        )
        return self._connection
    
    def _execute(
        self,
        query: str,
        tables: Optional[List[str]] = None,
        limit: int = 10,
        use_semantic: bool = False,
    ) -> Dict[str, Any]:
        """
        Search Snowflake.
        
        Args:
            query: Search query
            tables: Tables to search
            limit: Maximum results
            use_semantic: Use semantic search (requires Cortex)
            
        Returns:
            Dict with search results
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            if not tables:
                tables = self._get_tables(cursor)
            
            results = []
            
            for table in tables:
                if use_semantic:
                    table_results = self._semantic_search(
                        cursor, table, query, limit
                    )
                else:
                    table_results = self._text_search(
                        cursor, table, query, limit
                    )
                
                for row in table_results:
                    row['_table'] = table
                    results.append(row)
            
            return {
                'query': query,
                'results': results[:limit],
                'total': len(results),
                'tables_searched': tables,
            }
        finally:
            cursor.close()
    
    def _get_tables(self, cursor) -> List[str]:
        """Get all tables."""
        cursor.execute("SHOW TABLES")
        return [row[1] for row in cursor.fetchall()]
    
    def _get_text_columns(self, cursor, table: str) -> List[str]:
        """Get text columns for table."""
        cursor.execute(f"DESCRIBE TABLE {table}")
        text_types = ('VARCHAR', 'STRING', 'TEXT', 'CHAR')
        return [
            row[0] for row in cursor.fetchall()
            if any(t in row[1].upper() for t in text_types)
        ]
    
    def _text_search(
        self, cursor, table: str, query: str, limit: int
    ) -> List[Dict]:
        """Text search using LIKE."""
        columns = self._get_text_columns(cursor, table)
        if not columns:
            return []
        
        conditions = ' OR '.join(f"{c} ILIKE %s" for c in columns)
        sql = f"SELECT * FROM {table} WHERE {conditions} LIMIT %s"
        params = [f'%{query}%'] * len(columns) + [limit]
        
        cursor.execute(sql, params)
        
        col_names = [desc[0] for desc in cursor.description]
        return [dict(zip(col_names, row)) for row in cursor.fetchall()]
    
    def _semantic_search(
        self, cursor, table: str, query: str, limit: int
    ) -> List[Dict]:
        """Semantic search using Snowflake Cortex."""
        columns = self._get_text_columns(cursor, table)
        if not columns:
            return []
        
        # Concatenate text columns
        text_col = columns[0] if len(columns) == 1 else f"CONCAT({', '.join(columns)})"
        
        sql = f"""
            SELECT *, SNOWFLAKE.CORTEX.EMBED_TEXT_768('e5-base-v2', {text_col}) AS embedding
            FROM {table}
            ORDER BY VECTOR_L2_DISTANCE(
                embedding,
                SNOWFLAKE.CORTEX.EMBED_TEXT_768('e5-base-v2', %s)
            )
            LIMIT %s
        """
        
        try:
            cursor.execute(sql, (query, limit))
            col_names = [desc[0] for desc in cursor.description]
            return [dict(zip(col_names, row)) for row in cursor.fetchall()]
        except Exception as e:
            logger.warning(f"Semantic search failed, falling back to text: {e}")
            return self._text_search(cursor, table, query, limit)
    
    def execute_sql(self, sql: str) -> List[Dict]:
        """Execute raw SQL."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute(sql)
            if cursor.description:
                col_names = [desc[0] for desc in cursor.description]
                return [dict(zip(col_names, row)) for row in cursor.fetchall()]
            return []
        finally:
            cursor.close()
    
    def close(self):
        """Close connection."""
        if self._connection:
            self._connection.close()
            self._connection = None


class SingleStoreSearchTool(BaseTool):
    """
    Tool for searching data in SingleStore.
    
    Features:
    - Vector search
    - Full-text search
    - Hybrid search
    """
    
    def __init__(
        self,
        config: Optional[ToolConfig] = None,
        host: str = 'localhost',
        port: int = 3306,
        user: str = '',
        password: str = '',
        database: str = '',
    ):
        super().__init__(config or ToolConfig(
            name="SingleStoreSearchTool",
            description="Search data in SingleStore"
        ))
        self.host = host
        self.port = port
        self.user = user
        self.password = password or self.config.api_key or ''
        self.database = database
        self._connection = None
    
    def _get_connection(self):
        """Get SingleStore connection (MySQL compatible)."""
        if self._connection:
            return self._connection
        
        try:
            import mysql.connector
        except ImportError:
            raise ImportError("SingleStore requires: pip install mysql-connector-python")
        
        self._connection = mysql.connector.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=self.database,
        )
        return self._connection
    
    def _execute(
        self,
        query: str,
        table: Optional[str] = None,
        vector_column: Optional[str] = None,
        text_columns: Optional[List[str]] = None,
        limit: int = 10,
        search_type: str = 'text',
    ) -> Dict[str, Any]:
        """
        Search SingleStore.
        
        Args:
            query: Search query or vector
            table: Table to search
            vector_column: Column with vectors
            text_columns: Text columns for full-text search
            limit: Maximum results
            search_type: 'text', 'vector', or 'hybrid'
            
        Returns:
            Dict with search results
        """
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            if search_type == 'vector' and vector_column:
                results = self._vector_search(
                    cursor, table, vector_column, query, limit
                )
            elif search_type == 'hybrid':
                results = self._hybrid_search(
                    cursor, table, vector_column, text_columns, query, limit
                )
            else:
                results = self._text_search(
                    cursor, table, text_columns, query, limit
                )
            
            return {
                'query': query,
                'results': results,
                'total': len(results),
                'search_type': search_type,
            }
        finally:
            cursor.close()
    
    def _text_search(
        self, cursor, table: str, columns: Optional[List[str]], query: str, limit: int
    ) -> List[Dict]:
        """Full-text search."""
        if not columns:
            return []
        
        cols = ', '.join(columns)
        sql = f"""
            SELECT *, MATCH({cols}) AGAINST(%s) AS score
            FROM {table}
            WHERE MATCH({cols}) AGAINST(%s)
            ORDER BY score DESC
            LIMIT %s
        """
        cursor.execute(sql, (query, query, limit))
        return cursor.fetchall()
    
    def _vector_search(
        self, cursor, table: str, vector_col: str, query_vector: Any, limit: int
    ) -> List[Dict]:
        """Vector similarity search."""
        if isinstance(query_vector, str):
            # Assume it's a JSON string of the vector
            vector_str = query_vector
        else:
            import json
            vector_str = json.dumps(query_vector)
        
        sql = f"""
            SELECT *, DOT_PRODUCT({vector_col}, %s) AS similarity
            FROM {table}
            ORDER BY similarity DESC
            LIMIT %s
        """
        cursor.execute(sql, (vector_str, limit))
        return cursor.fetchall()
    
    def _hybrid_search(
        self, cursor, table: str, vector_col: Optional[str],
        text_cols: Optional[List[str]], query: str, limit: int
    ) -> List[Dict]:
        """Hybrid search combining text and vector."""
        text_results = []
        vector_results = []
        
        if text_cols:
            text_results = self._text_search(cursor, table, text_cols, query, limit)
        
        if vector_col:
            # Generate query embedding (simplified)
            import hashlib
            hash_bytes = hashlib.sha256(query.encode()).digest()[:128]
            query_vector = [b / 255.0 for b in hash_bytes]
            vector_results = self._vector_search(
                cursor, table, vector_col, query_vector, limit
            )
        
        # Merge results (simple approach)
        seen = set()
        merged = []
        
        for r in text_results + vector_results:
            key = str(r.get('id', r))
            if key not in seen:
                seen.add(key)
                merged.append(r)
        
        return merged[:limit]
    
    def close(self):
        """Close connection."""
        if self._connection:
            self._connection.close()
            self._connection = None


__all__ = ['SnowflakeSearchTool', 'SingleStoreSearchTool']
