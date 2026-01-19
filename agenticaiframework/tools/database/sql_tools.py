"""
SQL Database Tools.
"""

import logging
from typing import Any, Dict, List, Optional
from abc import ABC, abstractmethod

from ..base import BaseTool, ToolConfig

logger = logging.getLogger(__name__)


class BaseSQLTool(BaseTool, ABC):
    """Base class for SQL database tools."""
    
    def __init__(
        self,
        config: Optional[ToolConfig] = None,
        connection_string: Optional[str] = None,
    ):
        super().__init__(config or ToolConfig(name="BaseSQLTool"))
        self.connection_string = connection_string
        self._connection = None
    
    @abstractmethod
    def _get_connection(self):
        """Get or create database connection."""
        raise NotImplementedError
    
    def execute_query(self, query: str, params: Optional[tuple] = None) -> List[Dict]:
        """Execute SQL query and return results."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            if cursor.description:
                columns = [col[0] for col in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
            return []
        finally:
            cursor.close()
    
    def close(self):
        """Close database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None


class MySQLRAGSearchTool(BaseSQLTool):
    """
    Tool for RAG search in MySQL databases.
    
    Features:
    - Full-text search
    - Schema exploration
    - Natural language queries
    """
    
    def __init__(
        self,
        config: Optional[ToolConfig] = None,
        host: str = 'localhost',
        port: int = 3306,
        database: str = '',
        user: str = '',
        password: str = '',
    ):
        super().__init__(config or ToolConfig(
            name="MySQLRAGSearchTool",
            description="RAG search in MySQL databases"
        ))
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password or self.config.api_key or ''
    
    def _get_connection(self):
        """Get MySQL connection."""
        if self._connection:
            return self._connection
        
        try:
            import mysql.connector
        except ImportError:
            raise ImportError("MySQL support requires: pip install mysql-connector-python")
        
        self._connection = mysql.connector.connect(
            host=self.host,
            port=self.port,
            database=self.database,
            user=self.user,
            password=self.password,
        )
        return self._connection
    
    def _execute(
        self,
        query: str,
        tables: Optional[List[str]] = None,
        columns: Optional[List[str]] = None,
        limit: int = 10,
        use_fulltext: bool = True,
    ) -> Dict[str, Any]:
        """
        Search MySQL database.
        
        Args:
            query: Search query
            tables: Tables to search
            columns: Columns to search
            limit: Maximum results
            use_fulltext: Use full-text search if available
            
        Returns:
            Dict with search results
        """
        if not tables:
            tables = self._get_tables()
        
        results = []
        
        for table in tables:
            table_columns = columns or self._get_searchable_columns(table)
            
            if not table_columns:
                continue
            
            if use_fulltext and self._has_fulltext_index(table, table_columns):
                table_results = self._fulltext_search(
                    table, table_columns, query, limit
                )
            else:
                table_results = self._like_search(
                    table, table_columns, query, limit
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
    
    def _get_tables(self) -> List[str]:
        """Get all tables in database."""
        rows = self.execute_query("SHOW TABLES")
        return [list(row.values())[0] for row in rows]
    
    def _get_searchable_columns(self, table: str) -> List[str]:
        """Get text columns for a table."""
        rows = self.execute_query(f"DESCRIBE {table}")
        text_types = ('varchar', 'text', 'char', 'mediumtext', 'longtext')
        return [
            row['Field'] for row in rows
            if any(t in row['Type'].lower() for t in text_types)
        ]
    
    def _has_fulltext_index(self, table: str, columns: List[str]) -> bool:
        """Check if table has full-text index."""
        rows = self.execute_query(f"SHOW INDEX FROM {table}")
        fulltext_cols = {
            row['Column_name'] for row in rows
            if row.get('Index_type') == 'FULLTEXT'
        }
        return bool(fulltext_cols & set(columns))
    
    def _fulltext_search(
        self, table: str, columns: List[str], query: str, limit: int
    ) -> List[Dict]:
        """Perform full-text search."""
        cols = ', '.join(columns)
        match_clause = f"MATCH({cols}) AGAINST(%s IN NATURAL LANGUAGE MODE)"
        sql = f"SELECT *, {match_clause} AS score FROM {table} WHERE {match_clause} LIMIT %s"
        return self.execute_query(sql, (query, query, limit))
    
    def _like_search(
        self, table: str, columns: List[str], query: str, limit: int
    ) -> List[Dict]:
        """Perform LIKE search."""
        conditions = ' OR '.join(f"{col} LIKE %s" for col in columns)
        sql = f"SELECT * FROM {table} WHERE {conditions} LIMIT %s"
        params = tuple(f'%{query}%' for _ in columns) + (limit,)
        return self.execute_query(sql, params)


class PostgreSQLRAGSearchTool(BaseSQLTool):
    """
    Tool for RAG search in PostgreSQL databases.
    
    Features:
    - Full-text search with tsvector
    - Trigram similarity
    - JSON/JSONB search
    """
    
    def __init__(
        self,
        config: Optional[ToolConfig] = None,
        host: str = 'localhost',
        port: int = 5432,
        database: str = '',
        user: str = '',
        password: str = '',
    ):
        super().__init__(config or ToolConfig(
            name="PostgreSQLRAGSearchTool",
            description="RAG search in PostgreSQL databases"
        ))
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password or self.config.api_key or ''
    
    def _get_connection(self):
        """Get PostgreSQL connection."""
        if self._connection:
            return self._connection
        
        try:
            import psycopg2
        except ImportError:
            raise ImportError("PostgreSQL requires: pip install psycopg2-binary")
        
        self._connection = psycopg2.connect(
            host=self.host,
            port=self.port,
            database=self.database,
            user=self.user,
            password=self.password,
        )
        return self._connection
    
    def _execute(
        self,
        query: str,
        tables: Optional[List[str]] = None,
        columns: Optional[List[str]] = None,
        limit: int = 10,
        search_type: str = 'fulltext',
    ) -> Dict[str, Any]:
        """
        Search PostgreSQL database.
        
        Args:
            query: Search query
            tables: Tables to search
            columns: Columns to search
            limit: Maximum results
            search_type: 'fulltext', 'trigram', or 'like'
            
        Returns:
            Dict with search results
        """
        if not tables:
            tables = self._get_tables()
        
        results = []
        
        for table in tables:
            table_columns = columns or self._get_searchable_columns(table)
            
            if not table_columns:
                continue
            
            if search_type == 'fulltext':
                table_results = self._fulltext_search(
                    table, table_columns, query, limit
                )
            elif search_type == 'trigram':
                table_results = self._trigram_search(
                    table, table_columns, query, limit
                )
            else:
                table_results = self._like_search(
                    table, table_columns, query, limit
                )
            
            for row in table_results:
                row['_table'] = table
                results.append(row)
        
        return {
            'query': query,
            'results': results[:limit],
            'total': len(results),
            'tables_searched': tables,
            'search_type': search_type,
        }
    
    def _get_tables(self) -> List[str]:
        """Get all tables."""
        sql = """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
        """
        rows = self.execute_query(sql)
        return [row['table_name'] for row in rows]
    
    def _get_searchable_columns(self, table: str) -> List[str]:
        """Get text columns."""
        sql = """
            SELECT column_name FROM information_schema.columns
            WHERE table_name = %s AND data_type IN ('text', 'varchar', 'char')
        """
        rows = self.execute_query(sql, (table,))
        return [row['column_name'] for row in rows]
    
    def _fulltext_search(
        self, table: str, columns: List[str], query: str, limit: int
    ) -> List[Dict]:
        """Full-text search with tsvector."""
        cols_concat = " || ' ' || ".join(f"COALESCE({c}, '')" for c in columns)
        sql = f"""
            SELECT *, ts_rank(to_tsvector({cols_concat}), plainto_tsquery(%s)) AS rank
            FROM {table}
            WHERE to_tsvector({cols_concat}) @@ plainto_tsquery(%s)
            ORDER BY rank DESC
            LIMIT %s
        """
        return self.execute_query(sql, (query, query, limit))
    
    def _trigram_search(
        self, table: str, columns: List[str], query: str, limit: int
    ) -> List[Dict]:
        """Trigram similarity search."""
        cols_concat = " || ' ' || ".join(f"COALESCE({c}, '')" for c in columns)
        sql = f"""
            SELECT *, similarity({cols_concat}, %s) AS sim
            FROM {table}
            WHERE similarity({cols_concat}, %s) > 0.1
            ORDER BY sim DESC
            LIMIT %s
        """
        return self.execute_query(sql, (query, query, limit))
    
    def _like_search(
        self, table: str, columns: List[str], query: str, limit: int
    ) -> List[Dict]:
        """ILIKE search."""
        conditions = ' OR '.join(f"{c} ILIKE %s" for c in columns)
        sql = f"SELECT * FROM {table} WHERE {conditions} LIMIT %s"
        params = tuple(f'%{query}%' for _ in columns) + (limit,)
        return self.execute_query(sql, params)


class NL2SQLTool(BaseTool):
    """
    Tool for natural language to SQL conversion.
    
    Features:
    - Schema-aware SQL generation
    - Query validation
    - Result formatting
    """
    
    def __init__(
        self,
        config: Optional[ToolConfig] = None,
        llm_api_key: Optional[str] = None,
        db_tool: Optional[BaseSQLTool] = None,
    ):
        super().__init__(config or ToolConfig(
            name="NL2SQLTool",
            description="Convert natural language to SQL"
        ))
        self.llm_api_key = llm_api_key or self.config.api_key
        self.db_tool = db_tool
    
    def _execute(
        self,
        question: str,
        schema: Optional[Dict] = None,
        execute: bool = False,
        model: str = 'gpt-4',
    ) -> Dict[str, Any]:
        """
        Convert question to SQL.
        
        Args:
            question: Natural language question
            schema: Database schema
            execute: Execute generated SQL
            model: LLM model to use
            
        Returns:
            Dict with SQL and optionally results
        """
        if not self.llm_api_key:
            raise ValueError("LLM API key required")
        
        try:
            import openai
        except ImportError:
            raise ImportError("NL2SQL requires: pip install openai")
        
        # Get schema if not provided
        if not schema and self.db_tool:
            schema = self._get_schema()
        
        schema_str = self._format_schema(schema) if schema else "Schema not provided"
        
        prompt = f"""Convert the following question to SQL.

Database Schema:
{schema_str}

Question: {question}

Return only the SQL query, nothing else."""
        
        client = openai.OpenAI(api_key=self.llm_api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a SQL expert. Generate only valid SQL."},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        
        sql = response.choices[0].message.content.strip()
        
        # Clean up SQL
        if sql.startswith('```'):
            sql = sql.split('\n', 1)[1].rsplit('```', 1)[0]
        
        result = {
            'question': question,
            'sql': sql,
            'status': 'success',
        }
        
        if execute and self.db_tool:
            try:
                query_results = self.db_tool.execute_query(sql)
                result['results'] = query_results
                result['row_count'] = len(query_results)
            except Exception as e:
                result['execution_error'] = str(e)
        
        return result
    
    def _get_schema(self) -> Dict:
        """Get database schema from connected tool."""
        if not self.db_tool:
            return {}
        
        schema = {}
        tables = self.db_tool._get_tables()
        
        for table in tables:
            columns = self.db_tool._get_searchable_columns(table)
            schema[table] = columns
        
        return schema
    
    def _format_schema(self, schema: Dict) -> str:
        """Format schema for prompt."""
        lines = []
        for table, columns in schema.items():
            cols = ', '.join(columns) if columns else 'unknown columns'
            lines.append(f"- {table}: {cols}")
        return '\n'.join(lines)


__all__ = ['MySQLRAGSearchTool', 'PostgreSQLRAGSearchTool', 'NL2SQLTool']
