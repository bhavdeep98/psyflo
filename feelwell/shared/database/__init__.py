"""Database connection management for Feelwell services.

Provides connection pooling, health checks, and repository base classes
for PostgreSQL and QLDB integration.
"""

from .connection import (
    DatabaseConfig,
    ConnectionManager,
    get_connection_manager,
)
from .repository import (
    BaseRepository,
    RepositoryError,
    NotFoundError,
    DuplicateError,
)

__all__ = [
    "DatabaseConfig",
    "ConnectionManager",
    "get_connection_manager",
    "BaseRepository",
    "RepositoryError",
    "NotFoundError",
    "DuplicateError",
]
