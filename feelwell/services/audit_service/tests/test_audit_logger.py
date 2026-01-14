"""Tests for AuditLogger - immutable audit trail per ADR-005."""
import pytest
from feelwell.shared.utils import configure_pii_salt
from feelwell.services.audit_service.audit_logger import (
    AuditLogger,
    AuditAction,
    AuditEntity,
    AuditEntry,
)


@pytest.fixture(autouse=True)
def setup_pii_salt():
    configure_pii_salt("test_salt_that_is_at_least_32_characters_long")


@pytest.fixture
def logger():
    return AuditLogger()


class TestAuditEntryCreation:
    def test_log_creates_entry(self, logger):
        entry = logger.log(
            action=AuditAction.VIEW_CONVERSATION,
            entity_type=AuditEntity.STUDENT,
            entity_id="hash_abc123",
            actor_id="counselor_123",
            actor_role="counselor",
        )
        
        assert entry.entry_id.startswith("audit_")
        assert entry.action == AuditAction.VIEW_CONVERSATION
        assert entry.entity_type == AuditEntity.STUDENT
        assert entry.entity_id == "hash_abc123"
        assert entry.actor_id == "counselor_123"
    
    def test_entry_has_hash(self, logger):
        entry = logger.log(
            action=AuditAction.VIEW_STUDENT_PROFILE,
            entity_type=AuditEntity.STUDENT,
            entity_id="hash_xyz",
            actor_id="admin_001",
            actor_role="admin",
        )
        
        assert entry.entry_hash != ""
        assert len(entry.entry_hash) == 64  # SHA-256 hex
    
    def test_entry_is_immutable(self, logger):
        entry = logger.log(
            action=AuditAction.VIEW_CONVERSATION,
            entity_type=AuditEntity.STUDENT,
            entity_id="hash_abc",
            actor_id="user_123",
            actor_role="counselor",
        )
        
        with pytest.raises(Exception):  # FrozenInstanceError
            entry.action = AuditAction.DELETE_DATA


class TestHashChain:
    def test_entries_form_chain(self, logger):
        entry1 = logger.log(
            action=AuditAction.CREATE_SESSION,
            entity_type=AuditEntity.SESSION,
            entity_id="sess_001",
            actor_id="student_hash",
            actor_role="student",
        )
        
        entry2 = logger.log(
            action=AuditAction.END_SESSION,
            entity_type=AuditEntity.SESSION,
            entity_id="sess_001",
            actor_id="student_hash",
            actor_role="student",
        )
        
        # Second entry should reference first entry's hash
        assert entry2.previous_hash == entry1.entry_hash
    
    def test_chain_verification_passes(self, logger):
        # Create several entries
        for i in range(5):
            logger.log(
                action=AuditAction.VIEW_CONVERSATION,
                entity_type=AuditEntity.STUDENT,
                entity_id=f"hash_{i}",
                actor_id="counselor_123",
                actor_role="counselor",
            )
        
        assert logger.verify_chain() is True
    
    def test_empty_chain_is_valid(self):
        empty_logger = AuditLogger()
        assert empty_logger.verify_chain() is True


class TestDataAccessLogging:
    def test_log_data_access(self, logger):
        entry = logger.log_data_access(
            action=AuditAction.VIEW_CONVERSATION,
            student_id_hash="hash_student_123",
            accessor_id="counselor_456",
            accessor_role="counselor",
            school_id="school_001",
            justification="routine_check",
        )
        
        assert entry.entity_type == AuditEntity.STUDENT
        assert entry.entity_id == "hash_student_123"
        assert entry.details["justification"] == "routine_check"


class TestCrisisEventLogging:
    def test_log_crisis_detected(self, logger):
        entry = logger.log_crisis_event(
            action=AuditAction.CRISIS_DETECTED,
            crisis_id="crisis_abc123",
            student_id_hash="hash_student_789",
            actor_id="system",
            actor_role="system",
            school_id="school_001",
            details={"trigger_source": "safety_service"},
        )
        
        assert entry.entity_type == AuditEntity.CRISIS_EVENT
        assert entry.entity_id == "crisis_abc123"
        assert entry.details["student_id_hash"] == "hash_student_789"
    
    def test_log_crisis_acknowledged(self, logger):
        entry = logger.log_crisis_event(
            action=AuditAction.CRISIS_ACKNOWLEDGED,
            crisis_id="crisis_abc123",
            student_id_hash="hash_student_789",
            actor_id="counselor_123",
            actor_role="counselor",
        )
        
        assert entry.action == AuditAction.CRISIS_ACKNOWLEDGED


class TestQueryAuditEntries:
    def test_query_by_entity_type(self, logger):
        # Create mixed entries
        logger.log(
            action=AuditAction.VIEW_CONVERSATION,
            entity_type=AuditEntity.STUDENT,
            entity_id="hash_1",
            actor_id="user_1",
            actor_role="counselor",
        )
        logger.log(
            action=AuditAction.CREATE_SESSION,
            entity_type=AuditEntity.SESSION,
            entity_id="sess_1",
            actor_id="user_2",
            actor_role="student",
        )
        
        student_entries = logger.query(entity_type=AuditEntity.STUDENT)
        
        assert all(e.entity_type == AuditEntity.STUDENT for e in student_entries)
    
    def test_query_by_action(self, logger):
        logger.log(
            action=AuditAction.VIEW_CONVERSATION,
            entity_type=AuditEntity.STUDENT,
            entity_id="hash_1",
            actor_id="user_1",
            actor_role="counselor",
        )
        logger.log(
            action=AuditAction.EXPORT_DATA,
            entity_type=AuditEntity.STUDENT,
            entity_id="hash_2",
            actor_id="user_2",
            actor_role="admin",
        )
        
        view_entries = logger.query(action=AuditAction.VIEW_CONVERSATION)
        
        assert all(e.action == AuditAction.VIEW_CONVERSATION for e in view_entries)
    
    def test_query_by_entity_id(self, logger):
        logger.log(
            action=AuditAction.VIEW_CONVERSATION,
            entity_type=AuditEntity.STUDENT,
            entity_id="specific_hash",
            actor_id="user_1",
            actor_role="counselor",
        )
        
        entries = logger.query(entity_id="specific_hash")
        
        assert len(entries) >= 1
        assert all(e.entity_id == "specific_hash" for e in entries)
