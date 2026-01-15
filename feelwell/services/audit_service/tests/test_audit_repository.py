"""Tests for audit repository with QLDB/PostgreSQL integration."""
import pytest
from datetime import datetime, timedelta

from feelwell.shared.utils import configure_pii_salt
from feelwell.services.audit_service.audit_logger import (
    AuditEntry,
    AuditAction,
    AuditEntity,
)
from feelwell.services.audit_service.audit_repository import AuditRepository


@pytest.fixture(autouse=True)
def setup_pii_salt():
    configure_pii_salt("test_salt_that_is_at_least_32_characters_long")


@pytest.fixture
def repository():
    """Create repository with in-memory storage."""
    return AuditRepository()


@pytest.fixture
def sample_entry():
    """Create a sample audit entry."""
    entry = AuditEntry(
        entry_id="audit_test123",
        timestamp=datetime.utcnow(),
        action=AuditAction.VIEW_CONVERSATION,
        entity_type=AuditEntity.STUDENT,
        entity_id="student_hash_123",
        actor_id="counselor_001",
        actor_role="counselor",
        school_id="school_001",
        details={"justification": "routine_check"},
        previous_hash="genesis",
    )
    # Compute and set hash
    entry_hash = entry.compute_hash()
    return AuditEntry(
        entry_id=entry.entry_id,
        timestamp=entry.timestamp,
        action=entry.action,
        entity_type=entry.entity_type,
        entity_id=entry.entity_id,
        actor_id=entry.actor_id,
        actor_role=entry.actor_role,
        school_id=entry.school_id,
        details=entry.details,
        previous_hash=entry.previous_hash,
        entry_hash=entry_hash,
    )


class TestAuditRepositoryInitialization:
    """Tests for repository initialization."""
    
    def test_default_initialization(self):
        repo = AuditRepository()
        
        assert repo.use_qldb is False
        assert repo._memory_store == []
    
    def test_qldb_initialization(self):
        repo = AuditRepository(qldb_ledger="test-ledger", use_qldb=True)
        
        assert repo.use_qldb is True
        assert repo.qldb_ledger == "test-ledger"


class TestAuditRepositoryAppend:
    """Tests for append operations."""
    
    def test_append_to_memory(self, repository, sample_entry):
        result = repository.append(sample_entry)
        
        assert result is True
        assert len(repository._memory_store) == 1
        assert repository._memory_store[0].entry_id == sample_entry.entry_id
    
    def test_append_multiple_entries(self, repository):
        for i in range(5):
            entry = AuditEntry(
                entry_id=f"audit_{i}",
                timestamp=datetime.utcnow(),
                action=AuditAction.VIEW_CONVERSATION,
                entity_type=AuditEntity.STUDENT,
                entity_id=f"student_{i}",
                actor_id="counselor_001",
                actor_role="counselor",
                school_id="school_001",
                previous_hash="genesis",
                entry_hash="hash",
            )
            repository.append(entry)
        
        assert len(repository._memory_store) == 5


class TestAuditRepositoryQuery:
    """Tests for query operations."""
    
    def test_query_empty_repository(self, repository):
        results = repository.query()
        
        assert results == []
    
    def test_query_by_entity_type(self, repository):
        # Add entries with different entity types
        student_entry = AuditEntry(
            entry_id="audit_1",
            timestamp=datetime.utcnow(),
            action=AuditAction.VIEW_CONVERSATION,
            entity_type=AuditEntity.STUDENT,
            entity_id="student_hash_123",
            actor_id="counselor_001",
            actor_role="counselor",
            school_id="school_001",
            previous_hash="genesis",
            entry_hash="hash1",
        )
        crisis_entry = AuditEntry(
            entry_id="audit_2",
            timestamp=datetime.utcnow(),
            action=AuditAction.CRISIS_DETECTED,
            entity_type=AuditEntity.CRISIS_EVENT,
            entity_id="crisis_1",
            actor_id="system",
            actor_role="system",
            school_id="school_001",
            previous_hash="hash1",
            entry_hash="hash2",
        )
        
        repository.append(student_entry)
        repository.append(crisis_entry)
        
        results = repository.query(entity_type=AuditEntity.STUDENT)
        
        assert len(results) == 1
        assert results[0].entity_type == AuditEntity.STUDENT
    
    def test_query_by_action(self, repository):
        view_entry = AuditEntry(
            entry_id="audit_1",
            timestamp=datetime.utcnow(),
            action=AuditAction.VIEW_CONVERSATION,
            entity_type=AuditEntity.STUDENT,
            entity_id="student_1",
            actor_id="counselor_001",
            actor_role="counselor",
            school_id="school_001",
            previous_hash="genesis",
            entry_hash="hash1",
        )
        crisis_entry = AuditEntry(
            entry_id="audit_2",
            timestamp=datetime.utcnow(),
            action=AuditAction.CRISIS_DETECTED,
            entity_type=AuditEntity.CRISIS_EVENT,
            entity_id="crisis_1",
            actor_id="system",
            actor_role="system",
            school_id="school_001",
            previous_hash="hash1",
            entry_hash="hash2",
        )
        
        repository.append(view_entry)
        repository.append(crisis_entry)
        
        results = repository.query(action=AuditAction.CRISIS_DETECTED)
        
        assert len(results) == 1
        assert results[0].action == AuditAction.CRISIS_DETECTED
    
    def test_query_by_date_range(self, repository):
        old_entry = AuditEntry(
            entry_id="audit_old",
            timestamp=datetime.utcnow() - timedelta(days=10),
            action=AuditAction.VIEW_CONVERSATION,
            entity_type=AuditEntity.STUDENT,
            entity_id="student_1",
            actor_id="counselor_001",
            actor_role="counselor",
            school_id="school_001",
            previous_hash="genesis",
            entry_hash="hash1",
        )
        new_entry = AuditEntry(
            entry_id="audit_new",
            timestamp=datetime.utcnow(),
            action=AuditAction.VIEW_CONVERSATION,
            entity_type=AuditEntity.STUDENT,
            entity_id="student_2",
            actor_id="counselor_001",
            actor_role="counselor",
            school_id="school_001",
            previous_hash="hash1",
            entry_hash="hash2",
        )
        
        repository.append(old_entry)
        repository.append(new_entry)
        
        # Query for entries in last 5 days
        results = repository.query(
            start_date=datetime.utcnow() - timedelta(days=5)
        )
        
        assert len(results) == 1
        assert results[0].entry_id == "audit_new"
    
    def test_query_with_limit(self, repository):
        for i in range(10):
            entry = AuditEntry(
                entry_id=f"audit_{i}",
                timestamp=datetime.utcnow(),
                action=AuditAction.VIEW_CONVERSATION,
                entity_type=AuditEntity.STUDENT,
                entity_id=f"student_{i}",
                actor_id="counselor_001",
                actor_role="counselor",
                school_id="school_001",
                previous_hash="genesis",
                entry_hash=f"hash_{i}",
            )
            repository.append(entry)
        
        results = repository.query(limit=5)
        
        assert len(results) == 5
    
    def test_query_by_school_id(self, repository):
        school1_entry = AuditEntry(
            entry_id="audit_1",
            timestamp=datetime.utcnow(),
            action=AuditAction.VIEW_CONVERSATION,
            entity_type=AuditEntity.STUDENT,
            entity_id="student_1",
            actor_id="counselor_001",
            actor_role="counselor",
            school_id="school_001",
            previous_hash="genesis",
            entry_hash="hash1",
        )
        school2_entry = AuditEntry(
            entry_id="audit_2",
            timestamp=datetime.utcnow(),
            action=AuditAction.VIEW_CONVERSATION,
            entity_type=AuditEntity.STUDENT,
            entity_id="student_2",
            actor_id="counselor_002",
            actor_role="counselor",
            school_id="school_002",
            previous_hash="hash1",
            entry_hash="hash2",
        )
        
        repository.append(school1_entry)
        repository.append(school2_entry)
        
        results = repository.query(school_id="school_001")
        
        assert len(results) == 1
        assert results[0].school_id == "school_001"


class TestAuditChainVerification:
    """Tests for audit chain integrity verification."""
    
    def test_verify_empty_chain(self, repository):
        result = repository.verify_chain()
        
        assert result is True
    
    def test_verify_valid_chain(self, repository):
        # Create a valid chain
        prev_hash = "genesis"
        for i in range(3):
            entry = AuditEntry(
                entry_id=f"audit_{i}",
                timestamp=datetime.utcnow(),
                action=AuditAction.VIEW_CONVERSATION,
                entity_type=AuditEntity.STUDENT,
                entity_id=f"student_{i}",
                actor_id="counselor_001",
                actor_role="counselor",
                school_id="school_001",
                previous_hash=prev_hash,
            )
            entry_hash = entry.compute_hash()
            entry = AuditEntry(
                entry_id=entry.entry_id,
                timestamp=entry.timestamp,
                action=entry.action,
                entity_type=entry.entity_type,
                entity_id=entry.entity_id,
                actor_id=entry.actor_id,
                actor_role=entry.actor_role,
                school_id=entry.school_id,
                details=entry.details,
                previous_hash=entry.previous_hash,
                entry_hash=entry_hash,
            )
            repository.append(entry)
            prev_hash = entry_hash
        
        result = repository.verify_chain()
        
        assert result is True
    
    def test_verify_broken_chain(self, repository):
        # Create entries with broken chain
        entry1 = AuditEntry(
            entry_id="audit_1",
            timestamp=datetime.utcnow(),
            action=AuditAction.VIEW_CONVERSATION,
            entity_type=AuditEntity.STUDENT,
            entity_id="student_1",
            actor_id="counselor_001",
            actor_role="counselor",
            school_id="school_001",
            previous_hash="genesis",
            entry_hash="hash1",
        )
        entry2 = AuditEntry(
            entry_id="audit_2",
            timestamp=datetime.utcnow(),
            action=AuditAction.VIEW_CONVERSATION,
            entity_type=AuditEntity.STUDENT,
            entity_id="student_2",
            actor_id="counselor_001",
            actor_role="counselor",
            school_id="school_001",
            previous_hash="wrong_hash",  # Broken chain
            entry_hash="hash2",
        )
        
        repository.append(entry1)
        repository.append(entry2)
        
        result = repository.verify_chain()
        
        assert result is False
