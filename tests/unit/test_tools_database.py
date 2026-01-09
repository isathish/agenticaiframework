"""
Tests for database tools module.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from agenticaiframework.tools.database.sql_tools import (
    BaseSQLTool,
    MySQLRAGSearchTool,
    PostgreSQLRAGSearchTool,
    NL2SQLTool,
)
from agenticaiframework.tools.base import ToolConfig


class TestBaseSQLTool:
    """Tests for BaseSQLTool - using MySQLRAGSearchTool as concrete implementation."""
    
    def test_mysql_has_connection_string(self):
        """Test MySQLRAGSearchTool has connection attributes."""
        tool = MySQLRAGSearchTool()
        assert tool._connection is None
    
    def test_close_no_connection(self):
        """Test closing when no connection exists."""
        tool = MySQLRAGSearchTool()
        tool.close()  # Should not raise
        assert tool._connection is None
    
    def test_close_with_connection(self):
        """Test closing existing connection."""
        tool = MySQLRAGSearchTool()
        mock_conn = Mock()
        tool._connection = mock_conn
        
        tool.close()
        
        mock_conn.close.assert_called_once()
        assert tool._connection is None


class TestMySQLRAGSearchTool:
    """Tests for MySQLRAGSearchTool."""
    
    def test_init_default(self):
        """Test default initialization."""
        tool = MySQLRAGSearchTool()
        assert tool.host == 'localhost'
        assert tool.port == 3306
        assert tool.database == ''
        assert tool.user == ''
        assert tool.config.name == "MySQLRAGSearchTool"
    
    def test_init_custom(self):
        """Test custom initialization."""
        tool = MySQLRAGSearchTool(
            host='db.example.com',
            port=3307,
            database='testdb',
            user='admin',
            password='secret',
        )
        assert tool.host == 'db.example.com'
        assert tool.port == 3307
        assert tool.database == 'testdb'
        assert tool.user == 'admin'
        assert tool.password == 'secret'


class TestPostgreSQLRAGSearchTool:
    """Tests for PostgreSQLRAGSearchTool."""
    
    def test_init_default(self):
        """Test default initialization."""
        tool = PostgreSQLRAGSearchTool()
        assert tool.host == 'localhost'
        assert tool.port == 5432
        assert tool.database == ''
        assert tool.user == ''
        assert tool.config.name == "PostgreSQLRAGSearchTool"
    
    def test_init_custom(self):
        """Test custom initialization."""
        tool = PostgreSQLRAGSearchTool(
            host='pg.example.com',
            port=5433,
            database='pgdb',
            user='pguser',
            password='pgpass',
        )
        assert tool.host == 'pg.example.com'
        assert tool.port == 5433
        assert tool.database == 'pgdb'
        assert tool.user == 'pguser'


class TestNL2SQLTool:
    """Tests for NL2SQLTool."""
    
    def test_init_default(self):
        """Test default initialization."""
        tool = NL2SQLTool()
        assert tool.config.name == "NL2SQLTool"
    
    def test_init_custom_config(self):
        """Test custom config initialization."""
        config = ToolConfig(name="CustomNL2SQL", description="Custom NL2SQL tool")
        tool = NL2SQLTool(config=config)
        assert tool.config.name == "CustomNL2SQL"


class TestVectorTools:
    """Tests for vector database tools."""
    
    def test_vector_tool_import(self):
        """Test that vector tools can be imported."""
        from agenticaiframework.tools.database.vector_tools import (
            QdrantVectorSearchTool,
            WeaviateVectorSearchTool,
            MongoDBVectorSearchTool,
        )
        assert QdrantVectorSearchTool is not None
        assert WeaviateVectorSearchTool is not None
        assert MongoDBVectorSearchTool is not None
    
    def test_qdrant_init(self):
        """Test QdrantVectorSearchTool initialization."""
        from agenticaiframework.tools.database.vector_tools import QdrantVectorSearchTool
        tool = QdrantVectorSearchTool()
        assert tool.config.name == "QdrantVectorSearchTool"
    
    def test_weaviate_init(self):
        """Test WeaviateVectorSearchTool initialization."""
        from agenticaiframework.tools.database.vector_tools import WeaviateVectorSearchTool
        tool = WeaviateVectorSearchTool()
        assert tool.config.name == "WeaviateVectorSearchTool"
    
    def test_mongodb_init(self):
        """Test MongoDBVectorSearchTool initialization."""
        from agenticaiframework.tools.database.vector_tools import MongoDBVectorSearchTool
        tool = MongoDBVectorSearchTool()
        assert tool.config.name == "MongoDBVectorSearchTool"


class TestSnowflakeTools:
    """Tests for Snowflake tools."""
    
    def test_snowflake_import(self):
        """Test that Snowflake tools can be imported."""
        from agenticaiframework.tools.database.snowflake_tools import (
            SnowflakeSearchTool,
            SingleStoreSearchTool,
        )
        assert SnowflakeSearchTool is not None
        assert SingleStoreSearchTool is not None
    
    def test_snowflake_search_init(self):
        """Test SnowflakeSearchTool initialization."""
        from agenticaiframework.tools.database.snowflake_tools import SnowflakeSearchTool
        tool = SnowflakeSearchTool()
        assert tool.config.name == "SnowflakeSearchTool"
    
    def test_snowflake_custom_config(self):
        """Test SnowflakeSearchTool with custom config."""
        from agenticaiframework.tools.database.snowflake_tools import SnowflakeSearchTool
        config = ToolConfig(name="CustomSnowflake", description="Custom Snowflake tool")
        tool = SnowflakeSearchTool(config=config)
        assert tool.config.name == "CustomSnowflake"
    
    def test_singlestore_init(self):
        """Test SingleStoreSearchTool initialization."""
        from agenticaiframework.tools.database.snowflake_tools import SingleStoreSearchTool
        tool = SingleStoreSearchTool()
        assert tool.config.name == "SingleStoreSearchTool"


class TestSQLToolExecuteQuery:
    """Tests for SQL tool query execution."""
    
    def test_execute_query_with_results(self):
        """Test executing query that returns results."""
        tool = MySQLRAGSearchTool()
        
        # Mock connection and cursor
        mock_cursor = Mock()
        mock_cursor.description = [('id',), ('name',)]
        mock_cursor.fetchall.return_value = [(1, 'Alice'), (2, 'Bob')]
        
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        tool._connection = mock_conn
        
        # Override _get_connection to return our mock
        tool._get_connection = Mock(return_value=mock_conn)
        
        results = tool.execute_query("SELECT * FROM users")
        
        assert len(results) == 2
        assert results[0]['id'] == 1
        assert results[0]['name'] == 'Alice'
        mock_cursor.close.assert_called_once()
    
    def test_execute_query_with_params(self):
        """Test executing query with parameters."""
        tool = MySQLRAGSearchTool()
        
        mock_cursor = Mock()
        mock_cursor.description = None  # No results
        
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        tool._connection = mock_conn
        tool._get_connection = Mock(return_value=mock_conn)
        
        results = tool.execute_query(
            "INSERT INTO users (name) VALUES (?)",
            params=('Alice',)
        )
        
        assert results == []
        mock_cursor.execute.assert_called_once_with(
            "INSERT INTO users (name) VALUES (?)",
            ('Alice',)
        )
    
    def test_execute_query_no_results(self):
        """Test executing query that returns no results."""
        tool = MySQLRAGSearchTool()
        
        mock_cursor = Mock()
        mock_cursor.description = None
        
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        tool._connection = mock_conn
        tool._get_connection = Mock(return_value=mock_conn)
        
        results = tool.execute_query("DELETE FROM users WHERE id = 1")
        
        assert results == []


class TestDatabaseToolInheritance:
    """Tests for database tool inheritance."""
    
    def test_mysql_inherits_base_sql(self):
        """Test MySQLRAGSearchTool inherits from BaseSQLTool."""
        tool = MySQLRAGSearchTool()
        assert isinstance(tool, BaseSQLTool)
    
    def test_postgres_inherits_base_sql(self):
        """Test PostgreSQLRAGSearchTool inherits from BaseSQLTool."""
        tool = PostgreSQLRAGSearchTool()
        assert isinstance(tool, BaseSQLTool)
    
    def test_mysql_inherits_base_tool(self):
        """Test MySQLRAGSearchTool inherits from BaseTool."""
        from agenticaiframework.tools.base import BaseTool
        tool = MySQLRAGSearchTool()
        assert isinstance(tool, BaseTool)
