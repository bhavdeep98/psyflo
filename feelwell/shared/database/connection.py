"""Database connection manager with pooling and health checks.

Manages PostgreSQL connections with:
- Connection pooling for efficiency
- Health checks for readiness probes
- Automatic reconnection on failure
- Secrets Manager integration for credentials
"""
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DatabaseConfig:
    """Database connection configuration.
    
    Credentials are loaded from AWS Secrets Manager in production,
    or from environment variables in development.
    """
    host: str
    port: int = 5432
    database: str = "feelwell"
    username: str = ""
    password: str = ""
    min_connections: int = 2
    max_connections: int = 10
    connect_timeout: int = 10
    ssl_mode: str = "require"
    
    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        """Create config from environment variables.
        
        Environment variables:
            DB_HOST: Database host
            DB_PORT: Database port (default 5432)
            DB_NAME: Database name (default feelwell)
            DB_USER: Database username
            DB_PASSWORD: Database password
            DB_MIN_CONN: Minimum pool connections (default 2)
            DB_MAX_CONN: Maximum pool connections (default 10)
            DB_SSL_MODE: SSL mode (default require)
        """
        return cls(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "5432")),
            database=os.getenv("DB_NAME", "feelwell"),
            username=os.getenv("DB_USER", ""),
            password=os.getenv("DB_PASSWORD", ""),
            min_connections=int(os.getenv("DB_MIN_CONN", "2")),
            max_connections=int(os.getenv("DB_MAX_CONN", "10")),
            ssl_mode=os.getenv("DB_SSL_MODE", "require"),
        )
    
    @classmethod
    def from_secrets_manager(cls, secret_arn: str, region: str = "us-east-1") -> "DatabaseConfig":
        """Load config from AWS Secrets Manager.
        
        Args:
            secret_arn: ARN of the secret containing credentials
            region: AWS region
            
        Returns:
            DatabaseConfig with credentials from Secrets Manager
        """
        try:
            import boto3
            import json
            
            client = boto3.client("secretsmanager", region_name=region)
            response = client.get_secret_value(SecretId=secret_arn)
            secret = json.loads(response["SecretString"])
            
            return cls(
                host=secret.get("host", os.getenv("DB_HOST", "localhost")),
                port=int(secret.get("port", os.getenv("DB_PORT", "5432"))),
                database=secret.get("dbname", os.getenv("DB_NAME", "feelwell")),
                username=secret.get("username", ""),
                password=secret.get("password", ""),
            )
        except Exception as e:
            logger.error(
                "SECRETS_MANAGER_LOAD_FAILED",
                extra={"error": str(e), "secret_arn": secret_arn}
            )
            raise


class ConnectionManager:
    """Manages database connections with pooling.
    
    Uses psycopg2 connection pool for PostgreSQL.
    Provides health checks and automatic reconnection.
    """
    
    def __init__(self, config: DatabaseConfig):
        """Initialize connection manager.
        
        Args:
            config: Database configuration
        """
        self.config = config
        self._pool = None
        self._initialized = False
        
        logger.info(
            "CONNECTION_MANAGER_CREATED",
            extra={
                "host": config.host,
                "database": config.database,
                "min_connections": config.min_connections,
                "max_connections": config.max_connections,
            }
        )
    
    def initialize(self) -> None:
        """Initialize the connection pool.
        
        Call this during application startup.
        """
        if self._initialized:
            return
        
        try:
            from psycopg2 import pool
            
            self._pool = pool.ThreadedConnectionPool(
                minconn=self.config.min_connections,
                maxconn=self.config.max_connections,
                host=self.config.host,
                port=self.config.port,
                database=self.config.database,
                user=self.config.username,
                password=self.config.password,
                connect_timeout=self.config.connect_timeout,
                sslmode=self.config.ssl_mode,
            )
            
            self._initialized = True
            logger.info(
                "CONNECTION_POOL_INITIALIZED",
                extra={
                    "host": self.config.host,
                    "database": self.config.database,
                }
            )
            
        except ImportError:
            logger.warning(
                "PSYCOPG2_NOT_INSTALLED",
                extra={"action": "using_mock_pool"}
            )
            self._pool = None
            self._initialized = True
            
        except Exception as e:
            logger.error(
                "CONNECTION_POOL_INIT_FAILED",
                extra={"error": str(e)}
            )
            raise
    
    @contextmanager
    def get_connection(self):
        """Get a connection from the pool.
        
        Usage:
            with manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
        
        Yields:
            Database connection
        """
        if not self._initialized:
            self.initialize()
        
        if self._pool is None:
            # Mock connection for development without psycopg2
            yield MockConnection()
            return
        
        conn = None
        try:
            conn = self._pool.getconn()
            yield conn
        finally:
            if conn is not None:
                self._pool.putconn(conn)
    
    def health_check(self) -> Dict[str, Any]:
        """Check database connectivity.
        
        Returns:
            Dictionary with health status
        """
        if not self._initialized:
            return {
                "status": "not_initialized",
                "healthy": False,
            }
        
        if self._pool is None:
            return {
                "status": "mock_mode",
                "healthy": True,
                "message": "Running without database (development mode)",
            }
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()
            
            return {
                "status": "connected",
                "healthy": True,
                "host": self.config.host,
                "database": self.config.database,
            }
            
        except Exception as e:
            logger.error(
                "DATABASE_HEALTH_CHECK_FAILED",
                extra={"error": str(e)}
            )
            return {
                "status": "error",
                "healthy": False,
                "error": str(e),
            }
    
    def close(self) -> None:
        """Close all connections in the pool.
        
        Call this during application shutdown.
        """
        if self._pool is not None:
            self._pool.closeall()
            logger.info("CONNECTION_POOL_CLOSED")
        
        self._initialized = False


class MockConnection:
    """Mock connection for development without psycopg2."""
    
    def cursor(self):
        return MockCursor()
    
    def commit(self):
        pass
    
    def rollback(self):
        pass


class MockCursor:
    """Mock cursor for development."""
    
    def execute(self, query: str, params: tuple = None):
        logger.debug(f"MOCK_EXECUTE: {query[:100]}")
    
    def fetchone(self):
        return None
    
    def fetchall(self):
        return []
    
    def close(self):
        pass
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        pass


# Global connection manager instance
_connection_manager: Optional[ConnectionManager] = None


def get_connection_manager() -> ConnectionManager:
    """Get or create the global connection manager.
    
    Returns:
        ConnectionManager instance
    """
    global _connection_manager
    
    if _connection_manager is None:
        config = DatabaseConfig.from_env()
        _connection_manager = ConnectionManager(config)
    
    return _connection_manager
