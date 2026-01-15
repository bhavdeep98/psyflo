"""Tests for base repository pattern."""
import pytest
from unittest.mock import MagicMock
from dataclasses import dataclass
from typing import Any, Dict

from feelwell.shared.utils import configure_pii_salt
from feelwell.shared.database.connection import ConnectionManager, DatabaseConfig
from feelwell.shared.database.repository import (
    BaseRepository,
    RepositoryError,
    NotFoundError,
    DuplicateError,
)


@pytest.fixture(autouse=True)
def setup_pii_salt():
    configure_pii_salt("test_salt_that_is_at_least_32_characters_long")


@dataclass
class TestEntity:
    """Test entity for repository tests."""
    id: str
    name: str
    value: int


class TestRepository(BaseRepository[TestEntity]):
    """Concrete repository for testing."""
    
    def _row_to_entity(self, row: tuple) -> TestEntity:
        return TestEntity(id=row[0], name=row[1], value=row[2])
    
    def _entity_to_params(self, entity: TestEntity) -> Dict[str, Any]:
        return {
            "id": entity.id,
            "name": entity.name,
            "value": entity.value,
        }


class TestRepositoryExceptions:
    """Tests for repository exception classes."""
    
    def test_repository_error(self):
        error = RepositoryError("Test error")
        assert str(error) == "Test error"
    
    def test_not_found_error(self):
        error = NotFoundError("Entity not found")
        assert isinstance(error, RepositoryError)
    
    def test_duplicate_error(self):
        error = DuplicateError("Duplicate entity")
        assert isinstance(error, RepositoryError)


class TestBaseRepository:
    """Tests for BaseRepository class."""
    
    @pytest.fixture
    def mock_connection_manager(self):
        """Create mock connection manager."""
        config = DatabaseConfig(host="localhost")
        manager = ConnectionManager(config)
        manager._initialized = True
        manager._pool = None  # Use mock mode
        return manager
    
    @pytest.fixture
    def repository(self, mock_connection_manager):
        """Create test repository."""
        return TestRepository(mock_connection_manager, "test_table")
    
    def test_initialization(self, repository):
        assert repository.table_name == "test_table"
    
    def test_find_by_id_returns_none_for_mock(self, repository):
        """Mock cursor returns None for fetchone."""
        result = repository.find_by_id("test_id")
        
        # Mock returns None
        assert result is None
    
    def test_find_all_returns_empty_for_mock(self, repository):
        """Mock cursor returns empty list for fetchall."""
        result = repository.find_all()
        
        assert result == []
    
    def test_count_returns_zero_for_mock(self, repository):
        """Mock cursor returns None which becomes 0."""
        result = repository.count()
        
        # Mock fetchone returns None, so count is 0
        assert result == 0
    
    def test_row_to_entity(self, repository):
        """Test entity conversion."""
        row = ("id_1", "test_name", 42)
        entity = repository._row_to_entity(row)
        
        assert entity.id == "id_1"
        assert entity.name == "test_name"
        assert entity.value == 42
    
    def test_entity_to_params(self, repository):
        """Test params conversion."""
        entity = TestEntity(id="id_1", name="test", value=100)
        params = repository._entity_to_params(entity)
        
        assert params["id"] == "id_1"
        assert params["name"] == "test"
        assert params["value"] == 100
