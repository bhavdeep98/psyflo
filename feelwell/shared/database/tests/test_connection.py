"""Tests for database connection manager."""
import pytest
from unittest.mock import MagicMock, patch

from feelwell.shared.utils import configure_pii_salt
from feelwell.shared.database.connection import (
    DatabaseConfig,
    ConnectionManager,
    MockConnection,
    MockCursor,
)


@pytest.fixture(autouse=True)
def setup_pii_salt():
    configure_pii_salt("test_salt_that_is_at_least_32_characters_long")


class TestDatabaseConfig:
    """Tests for DatabaseConfig dataclass."""
    
    def test_default_values(self):
        config = DatabaseConfig(host="localhost")
        
        assert config.host == "localhost"
        assert config.port == 5432
        assert config.database == "feelwell"
        assert config.min_connections == 2
        assert config.max_connections == 10
        assert config.ssl_mode == "require"
    
    def test_custom_values(self):
        config = DatabaseConfig(
            host="db.example.com",
            port=5433,
            database="test_db",
            username="user",
            password="pass",
            min_connections=5,
            max_connections=20,
        )
        
        assert config.host == "db.example.com"
        assert config.port == 5433
        assert config.database == "test_db"
        assert config.min_connections == 5
        assert config.max_connections == 20
    
    def test_from_env(self):
        with patch.dict("os.environ", {
            "DB_HOST": "env-host",
            "DB_PORT": "5434",
            "DB_NAME": "env_db",
            "DB_USER": "env_user",
            "DB_PASSWORD": "env_pass",
        }):
            config = DatabaseConfig.from_env()
            
            assert config.host == "env-host"
            assert config.port == 5434
            assert config.database == "env_db"
            assert config.username == "env_user"
            assert config.password == "env_pass"
    
    def test_from_env_defaults(self):
        with patch.dict("os.environ", {}, clear=True):
            config = DatabaseConfig.from_env()
            
            assert config.host == "localhost"
            assert config.port == 5432
            assert config.database == "feelwell"


class TestConnectionManager:
    """Tests for ConnectionManager class."""
    
    def test_initialization(self):
        config = DatabaseConfig(host="localhost")
        manager = ConnectionManager(config)
        
        assert manager.config == config
        assert manager._initialized is False
    
    def test_initialize_without_psycopg2(self):
        """Should fall back to mock when psycopg2 not available."""
        config = DatabaseConfig(host="localhost")
        manager = ConnectionManager(config)
        
        # This will use mock since psycopg2 may not be installed
        manager.initialize()
        
        assert manager._initialized is True
    
    def test_get_connection_returns_mock(self):
        """Without psycopg2, should return MockConnection."""
        config = DatabaseConfig(host="localhost")
        manager = ConnectionManager(config)
        manager.initialize()
        manager._pool = None  # Force mock mode
        
        with manager.get_connection() as conn:
            assert isinstance(conn, MockConnection)
    
    def test_health_check_not_initialized(self):
        config = DatabaseConfig(host="localhost")
        manager = ConnectionManager(config)
        
        health = manager.health_check()
        
        assert health["status"] == "not_initialized"
        assert health["healthy"] is False
    
    def test_health_check_mock_mode(self):
        config = DatabaseConfig(host="localhost")
        manager = ConnectionManager(config)
        manager._initialized = True
        manager._pool = None
        
        health = manager.health_check()
        
        assert health["status"] == "mock_mode"
        assert health["healthy"] is True
    
    def test_close(self):
        config = DatabaseConfig(host="localhost")
        manager = ConnectionManager(config)
        manager._initialized = True
        
        manager.close()
        
        assert manager._initialized is False


class TestMockConnection:
    """Tests for MockConnection class."""
    
    def test_cursor(self):
        conn = MockConnection()
        cursor = conn.cursor()
        
        assert isinstance(cursor, MockCursor)
    
    def test_commit(self):
        conn = MockConnection()
        conn.commit()  # Should not raise
    
    def test_rollback(self):
        conn = MockConnection()
        conn.rollback()  # Should not raise


class TestMockCursor:
    """Tests for MockCursor class."""
    
    def test_execute(self):
        cursor = MockCursor()
        cursor.execute("SELECT * FROM test")  # Should not raise
    
    def test_execute_with_params(self):
        cursor = MockCursor()
        cursor.execute("SELECT * FROM test WHERE id = %s", (1,))
    
    def test_fetchone(self):
        cursor = MockCursor()
        result = cursor.fetchone()
        
        assert result is None
    
    def test_fetchall(self):
        cursor = MockCursor()
        result = cursor.fetchall()
        
        assert result == []
    
    def test_context_manager(self):
        cursor = MockCursor()
        
        with cursor as c:
            c.execute("SELECT 1")
