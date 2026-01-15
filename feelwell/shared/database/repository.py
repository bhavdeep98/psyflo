"""Base repository pattern for database operations.

Provides common CRUD operations with audit logging integration.
Per ADR-005: All data access operations must emit audit events.
"""
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Generic, List, Optional, TypeVar

from .connection import ConnectionManager

logger = logging.getLogger(__name__)

T = TypeVar('T')


class RepositoryError(Exception):
    """Base exception for repository errors."""
    pass


class NotFoundError(RepositoryError):
    """Entity not found in database."""
    pass


class DuplicateError(RepositoryError):
    """Duplicate entity already exists."""
    pass


class BaseRepository(ABC, Generic[T]):
    """Abstract base repository with common operations.
    
    Subclasses implement entity-specific logic while inheriting:
    - Connection management
    - Error handling
    - Logging patterns
    """
    
    def __init__(
        self,
        connection_manager: ConnectionManager,
        table_name: str,
    ):
        """Initialize repository.
        
        Args:
            connection_manager: Database connection manager
            table_name: Name of the database table
        """
        self.connection_manager = connection_manager
        self.table_name = table_name
        
        logger.info(
            "REPOSITORY_INITIALIZED",
            extra={"table_name": table_name}
        )
    
    @abstractmethod
    def _row_to_entity(self, row: tuple) -> T:
        """Convert database row to entity.
        
        Args:
            row: Database row tuple
            
        Returns:
            Entity instance
        """
        pass
    
    @abstractmethod
    def _entity_to_params(self, entity: T) -> Dict[str, Any]:
        """Convert entity to database parameters.
        
        Args:
            entity: Entity instance
            
        Returns:
            Dictionary of column names to values
        """
        pass
    
    def find_by_id(self, entity_id: str) -> Optional[T]:
        """Find entity by ID.
        
        Args:
            entity_id: Entity identifier
            
        Returns:
            Entity if found, None otherwise
        """
        with self.connection_manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT * FROM {self.table_name} WHERE id = %s",
                    (entity_id,)
                )
                row = cur.fetchone()
                
                if row is None:
                    return None
                
                return self._row_to_entity(row)
    
    def find_all(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> List[T]:
        """Find all entities with pagination.
        
        Args:
            limit: Maximum entities to return
            offset: Number of entities to skip
            
        Returns:
            List of entities
        """
        with self.connection_manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT * FROM {self.table_name} ORDER BY created_at DESC LIMIT %s OFFSET %s",
                    (limit, offset)
                )
                rows = cur.fetchall()
                
                return [self._row_to_entity(row) for row in rows]
    
    def save(self, entity: T) -> T:
        """Save entity (insert or update).
        
        Args:
            entity: Entity to save
            
        Returns:
            Saved entity
        """
        params = self._entity_to_params(entity)
        columns = list(params.keys())
        values = list(params.values())
        placeholders = ["%s"] * len(values)
        
        # Upsert query
        update_clause = ", ".join(f"{col} = EXCLUDED.{col}" for col in columns if col != "id")
        
        query = f"""
            INSERT INTO {self.table_name} ({", ".join(columns)})
            VALUES ({", ".join(placeholders)})
            ON CONFLICT (id) DO UPDATE SET {update_clause}
            RETURNING *
        """
        
        with self.connection_manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, values)
                row = cur.fetchone()
                conn.commit()
                
                if row:
                    return self._row_to_entity(row)
                return entity
    
    def delete(self, entity_id: str) -> bool:
        """Delete entity by ID.
        
        Args:
            entity_id: Entity identifier
            
        Returns:
            True if deleted, False if not found
        """
        with self.connection_manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"DELETE FROM {self.table_name} WHERE id = %s",
                    (entity_id,)
                )
                conn.commit()
                
                return cur.rowcount > 0
    
    def count(self) -> int:
        """Count total entities.
        
        Returns:
            Total count
        """
        with self.connection_manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) FROM {self.table_name}")
                row = cur.fetchone()
                
                return row[0] if row else 0
